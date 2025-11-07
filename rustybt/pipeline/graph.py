"""Dependency graph representation and execution planning for Pipeline terms.

This module provides classes for representing and analyzing the dependency
relationships between Pipeline terms. The dependency graph is used by the
PipelineEngine to determine execution order and manage memory efficiently.

Key Classes:

**TermGraph**: A basic directed acyclic graph (DAG) of term dependencies.
Provides topological sorting for execution order and visualization capabilities.
Used for simple analysis and debugging.

**ExecutionPlan**: An extended TermGraph that includes metadata about extra
rows needed for windowed computations. This is what the engine actually uses
to execute a pipeline, as it knows how many historical rows to load for each
term to satisfy all its dependents' lookback windows.

Concepts:

**Dependencies**: Each term declares which other terms it needs as inputs and
how many extra rows of each it requires (for lookback windows). The graph
captures these relationships.

**Topological Order**: Terms must be computed in an order that respects their
dependencies - a term can only be computed after all its inputs are available.
The graph provides this ordering.

**Reference Counting**: The engine tracks how many dependents each term has.
When a term's refcount hits zero, its data can be freed to conserve memory.

**Extra Rows**: Windowed terms (e.g., moving averages) need historical data.
The ExecutionPlan tracks how many extra rows to compute for each term to
satisfy all downstream requirements.

**Specialization**: LoadableTerms start generic and are specialized to a
domain during execution planning. The plan replaces generic terms with their
specialized versions.

Examples:
    Build a simple term graph::

        >>> from rustybt.pipeline import Pipeline
        >>> from rustybt.pipeline.data import EquityPricing
        >>> from rustybt.pipeline.factors import SimpleMovingAverage
        >>>
        >>> sma = SimpleMovingAverage(inputs=[EquityPricing.close], window_length=20)
        >>> pipe = Pipeline(columns={'sma': sma})
        >>> graph = pipe.to_simple_graph(AssetExists())
        >>>
        >>> # Graph contains: AssetExists -> EquityPricing.close -> SMA
        >>> assert EquityPricing.close in graph
        >>> assert sma in graph

    Analyze dependencies::

        >>> # Get execution order
        >>> for term in graph.ordered():
        ...     print(f"Compute: {term}")
        >>>
        >>> # Check what a term depends on
        >>> print(f"SMA depends on: {sma.dependencies}")
        >>> # {EquityPricing.close: 19, AssetExists(): 0}

    Create an execution plan with extra rows::

        >>> from rustybt.pipeline.domain import US_EQUITIES
        >>> plan = pipe.to_execution_plan(
        ...     domain=US_EQUITIES,
        ...     default_screen=AssetExists(),
        ...     start_date='2020-01-01',
        ...     end_date='2020-12-31',
        ... )
        >>>
        >>> # Plan knows how many extra rows each term needs
        >>> print(plan.extra_rows[EquityPricing.close])  # 19 for window_length=20

See Also:
    :class:`rustybt.pipeline.engine.SimplePipelineEngine`: Uses ExecutionPlan.
    :class:`rustybt.pipeline.Pipeline`: Creates graphs via to_execution_plan().
    :class:`rustybt.pipeline.term.Term`: Nodes in the dependency graph.
"""

import uuid

import networkx as nx

from rustybt.pipeline.visualize import display_graph
from rustybt.utils.memoize import lazyval

from .term import LoadableTerm


class CyclicDependency(Exception):
    pass


# This sentinel value is uniquely-generated at import time so that we can
# guarantee that it never conflicts with a user-provided column name.
#
# (Yes, technically, a user can import this file and pass this as the name of a
# column. If you do that you deserve whatever bizarre failure you cause.)
SCREEN_NAME = "screen_" + uuid.uuid4().hex


class TermGraph:
    """Directed acyclic graph (DAG) of Pipeline term dependencies.

    TermGraph represents the dependency relationships between pipeline terms
    without any execution-specific metadata. It's primarily useful for
    visualizing dependencies and understanding term relationships. For actual
    pipeline execution, use ExecutionPlan which extends this with metadata
    about extra rows needed for windowed computations.

    The graph is built by recursively traversing each output term's dependencies,
    adding edges from dependencies to dependents. The construction validates that
    no cycles exist (which would represent an impossible computation).

    Key Features:
        - Topological ordering for execution
        - Cycle detection during construction
        - Reference counting for memory management
        - Graph visualization (SVG/PNG/JPEG)

    Args:
        terms: Dictionary mapping output names to their corresponding terms.
            These are the terms that will be returned as pipeline outputs.

    Attributes:
        graph: NetworkX DiGraph containing the dependency structure.
        outputs: Dictionary of named output terms (same as input).

    Examples:
        Create a graph from a pipeline::

            >>> from rustybt.pipeline import Pipeline
            >>> from rustybt.pipeline.data import EquityPricing
            >>> from rustybt.pipeline.factors import SimpleMovingAverage
            >>>
            >>> sma = SimpleMovingAverage(inputs=[EquityPricing.close], window_length=20)
            >>> pipe = Pipeline(columns={'sma': sma})
            >>> graph = pipe.to_simple_graph(AssetExists())

        Get execution order::

            >>> order = list(graph.ordered())
            >>> # [AssetExists(), EquityPricing.close, SMA]

        Visualize the graph::

            >>> # In Jupyter notebook
            >>> graph  # Displays PNG visualization
            >>> # Or explicitly
            >>> graph.svg  # SVG format
            >>> graph.png  # PNG format

        Check reference counts::

            >>> refcounts = graph.initial_refcounts([])
            >>> # Each term's refcount = number of dependents + (1 if output)

    See Also:
        :class:`ExecutionPlan`: Extended graph with execution metadata.
        :meth:`Pipeline.to_simple_graph`: Create a TermGraph from a pipeline.
        :meth:`Pipeline.show_graph`: Visualize a pipeline's dependencies.
    """

    def __init__(self, terms):
        self.graph = nx.DiGraph()

        self._frozen = False
        parents = set()
        for term in terms.values():
            self._add_to_graph(term, parents)
            # No parents should be left between top-level terms.
            assert not parents

        self._outputs = terms

        # Mark that no more terms should be added to the graph.
        self._frozen = True

    def __contains__(self, term):
        return term in self.graph

    def _add_to_graph(self, term, parents):
        """
        Add a term and all its children to ``graph``.

        ``parents`` is the set of all the parents of ``term` that we've added
        so far. It is only used to detect dependency cycles.
        """
        if self._frozen:
            raise ValueError("Can't mutate %s after construction." % type(self).__name__)

        # If we've seen this node already as a parent of the current traversal,
        # it means we have an unsatisifiable dependency.  This should only be
        # possible if the term's inputs are mutated after construction.
        if term in parents:
            raise CyclicDependency(term)

        parents.add(term)

        self.graph.add_node(term)

        for dependency in term.dependencies:
            self._add_to_graph(dependency, parents)
            self.graph.add_edge(dependency, term)

        parents.remove(term)

    @property
    def outputs(self):
        """
        Dict mapping names to designated output terms.
        """
        return self._outputs

    @property
    def screen_name(self):
        """Name of the specially-designated ``screen`` term for the pipeline."""
        return SCREEN_NAME

    def execution_order(self, workspace, refcounts):
        """
        Return a topologically-sorted list of the terms in ``self`` which
        need to be computed.

        Filters out any terms that are already present in ``workspace``, as
        well as any terms with refcounts of 0.

        Parameters
        ----------
        workspace : dict[Term, np.ndarray]
            Initial state of workspace for a pipeline execution. May contain
            pre-computed values provided by ``populate_initial_workspace``.
        refcounts : dict[Term, int]
            Reference counts for terms to be computed. Terms with reference
            counts of 0 do not need to be computed.
        """
        return list(
            nx.topological_sort(
                self.graph.subgraph(
                    {
                        term
                        for term, refcount in refcounts.items()
                        if refcount > 0 and term not in workspace
                    },
                ),
            )
        )

    def ordered(self):
        return iter(nx.topological_sort(self.graph))

    @lazyval
    def loadable_terms(self):
        return {term for term in self.graph if isinstance(term, LoadableTerm)}

    @lazyval
    def jpeg(self):
        return display_graph(self, "jpeg")

    @lazyval
    def png(self):
        return display_graph(self, "png")

    @lazyval
    def svg(self):
        return display_graph(self, "svg")

    def _repr_png_(self):
        return self.png.data

    def initial_refcounts(self, initial_terms):
        """
        Calculate initial refcounts for execution of this graph.

        Parameters
        ----------
        initial_terms : iterable[Term]
            An iterable of terms that were pre-computed before graph execution.

        Each node starts with a refcount equal to its outdegree, and output
        nodes get one extra reference to ensure that they're still in the graph
        at the end of execution.
        """
        refcounts = dict(self.graph.out_degree())
        for t in self.outputs.values():
            refcounts[t] += 1

        for t in initial_terms:
            self._decref_dependencies_recursive(t, refcounts, set())

        return refcounts

    def _decref_dependencies_recursive(self, term, refcounts, garbage):
        """
        Decrement terms recursively.

        Notes:
        -----
        This should only be used to build the initial workspace, after that we
        should use:
        :meth:`~zipline.pipeline.graph.TermGraph.decref_dependencies`
        """
        # Edges are tuple of (from, to).
        for parent, _ in self.graph.in_edges([term]):
            refcounts[parent] -= 1
            # No one else depends on this term. Remove it from the
            # workspace to conserve memory.
            if refcounts[parent] == 0:
                garbage.add(parent)
                self._decref_dependencies_recursive(parent, refcounts, garbage)

    def decref_dependencies(self, term, refcounts):
        """
        Decrement in-edges for ``term`` after computation.

        Parameters
        ----------
        term : zipline.pipeline.Term
            The term whose parents should be decref'ed.
        refcounts : dict[Term -> int]
            Dictionary of refcounts.

        Return:
        ------
        garbage : set[Term]
            Terms whose refcounts hit zero after decrefing.
        """
        garbage = set()
        # Edges are tuple of (from, to).
        for parent, _ in self.graph.in_edges([term]):
            refcounts[parent] -= 1
            # No one else depends on this term. Remove it from the
            # workspace to conserve memory.
            if refcounts[parent] == 0:
                garbage.add(parent)
        return garbage

    def __len__(self):
        return len(self.graph)


class ExecutionPlan(TermGraph):
    """Extended TermGraph with execution metadata for windowed computations.

    ExecutionPlan builds on TermGraph by adding critical metadata about how
    many extra historical rows each term needs. This is essential for windowed
    computations (e.g., moving averages) that require lookback data.

    The plan determines extra rows by:
    1. Starting from output terms with their required dates
    2. For each term, computing how many extra rows it needs based on its
       window_length and the requirements of its dependents
    3. Propagating these requirements up the dependency graph
    4. Specializing all LoadableTerms to the execution domain

    Key Metadata:

    **extra_rows**: For each term, how many historical rows beyond the requested
    date range must be computed. For example, a 20-day SMA needs 19 extra rows
    of input data.

    **offset**: For each (parent, child) dependency pair, how many leading rows
    to skip when passing parent's output to child. Accounts for the difference
    in extra_rows requirements.

    **domain**: The specialized domain (e.g., US_EQUITIES) that all LoadableTerms
    have been specialized to.

    Args:
        domain: The execution domain (determines which assets and calendar to use).
        terms: Dictionary mapping output names to output terms.
        start_date: First date for which final output is requested.
        end_date: Last date for which final output is requested.
        min_extra_rows: Minimum extra rows to compute (default 0).

    Attributes:
        domain: The execution domain.
        extra_rows: Dict mapping each term to its extra_rows requirement.
        offset: Dict mapping (child, parent) pairs to row offset values.
        outputs: Dictionary of named output terms.

    Examples:
        Create an execution plan::

            >>> from rustybt.pipeline import Pipeline
            >>> from rustybt.pipeline.domain import US_EQUITIES
            >>> from rustybt.pipeline.data import EquityPricing
            >>> from rustybt.pipeline.factors import SimpleMovingAverage
            >>>
            >>> sma = SimpleMovingAverage(inputs=[EquityPricing.close], window_length=20)
            >>> pipe = Pipeline(columns={'sma': sma})
            >>> plan = pipe.to_execution_plan(
            ...     domain=US_EQUITIES,
            ...     default_screen=AssetExists(),
            ...     start_date='2020-01-01',
            ...     end_date='2020-12-31',
            ... )

        Inspect extra rows requirements::

            >>> # SMA needs 19 extra rows of close (window_length - 1)
            >>> print(plan.extra_rows[sma])  # 0 (it's an output)
            >>> print(plan.extra_rows[EquityPricing.close])  # 19

        Check offsets for proper input slicing::

            >>> # When passing close to sma, no offset needed
            >>> specialized_close = EquityPricing.close.specialize(US_EQUITIES)
            >>> offset = plan.offset[sma, specialized_close]
            >>> print(offset)  # 0 (close has exactly the rows sma needs)

        The plan specializes LoadableTerms::

            >>> # All LoadableTerms are specialized to the domain
            >>> for term in plan.loadable_terms:
            ...     assert term.domain is US_EQUITIES

    See Also:
        :class:`TermGraph`: Base dependency graph without execution metadata.
        :meth:`Pipeline.to_execution_plan`: Create plan from pipeline.
        :meth:`SimplePipelineEngine._run_pipeline_impl`: Uses ExecutionPlan.
    """

    def __init__(self, domain, terms, start_date, end_date, min_extra_rows=0):
        super(ExecutionPlan, self).__init__(terms)

        # Specialize all the LoadableTerms in the graph to our domain, so that
        # when the engine requests an execution order, we emit the specialized
        # versions of loadable terms.
        #
        # NOTE: We're explicitly avoiding using self.loadable_terms here.
        #
        # At this point the graph still contains un-specialized loadable terms,
        # and this is where we're actually going through and specializing all
        # of them. We don't want use self.loadable_terms because it's a
        # lazyval, and we don't want its result to be cached until after we've
        # specialized.
        specializations = {
            t: t.specialize(domain) for t in self.graph if isinstance(t, LoadableTerm)
        }
        self.graph = nx.relabel.relabel_nodes(self.graph, specializations)

        self.domain = domain

        sessions = domain.sessions()
        for term in terms.values():
            self.set_extra_rows(
                term,
                sessions,
                start_date,
                end_date,
                min_extra_rows=min_extra_rows,
            )

        self._assert_all_loadable_terms_specialized_to(domain)

    def set_extra_rows(self, term, all_dates, start_date, end_date, min_extra_rows):
        # Specialize any loadable terms before adding extra rows.
        term = maybe_specialize(term, self.domain)

        # A term can require that additional extra rows beyond the minimum be
        # computed.  This is most often used with downsampled terms, which need
        # to ensure that the first date is a computation date.
        extra_rows_for_term = term.compute_extra_rows(
            all_dates,
            start_date,
            end_date,
            min_extra_rows,
        )
        if extra_rows_for_term < min_extra_rows:
            raise ValueError(
                "term %s requested fewer rows than the minimum of %d"
                % (
                    term,
                    min_extra_rows,
                )
            )

        self._ensure_extra_rows(term, extra_rows_for_term)

        for dependency, additional_extra_rows in term.dependencies.items():
            self.set_extra_rows(
                dependency,
                all_dates,
                start_date,
                end_date,
                min_extra_rows=extra_rows_for_term + additional_extra_rows,
            )

    @lazyval
    def offset(self):
        """
        For all pairs (term, input) such that `input` is an input to `term`,
        compute a mapping::

            (term, input) -> offset(term, input)

        where ``offset(term, input)`` is the number of rows that ``term``
        should truncate off the raw array produced for ``input`` before using
        it. We compute this value as follows::

            offset(term, input) = (extra_rows_computed(input)
                                   - extra_rows_computed(term)
                                   - requested_extra_rows(term, input))

        Examples:
        --------
        Case 1
        ~~~~~~

        Factor A needs 5 extra rows of USEquityPricing.close, and Factor B
        needs 3 extra rows of the same.  Factor A also requires 5 extra rows of
        USEquityPricing.high, which no other Factor uses.  We don't require any
        extra rows of Factor A or Factor B

        We load 5 extra rows of both `price` and `high` to ensure we can
        service Factor A, and the following offsets get computed::

            offset[Factor A, USEquityPricing.close] == (5 - 0) - 5 == 0
            offset[Factor A, USEquityPricing.high]  == (5 - 0) - 5 == 0
            offset[Factor B, USEquityPricing.close] == (5 - 0) - 3 == 2
            offset[Factor B, USEquityPricing.high] raises KeyError.

        Case 2
        ~~~~~~

        Factor A needs 5 extra rows of USEquityPricing.close, and Factor B
        needs 3 extra rows of Factor A, and Factor B needs 2 extra rows of
        USEquityPricing.close.

        We load 8 extra rows of USEquityPricing.close (enough to load 5 extra
        rows of Factor A), and the following offsets get computed::

            offset[Factor A, USEquityPricing.close] == (8 - 3) - 5 == 0
            offset[Factor B, USEquityPricing.close] == (8 - 0) - 2 == 6
            offset[Factor B, Factor A]              == (3 - 0) - 3 == 0

        Notes:
        -----
        `offset(term, input) >= 0` for all valid pairs, since `input` must be
        an input to `term` if the pair appears in the mapping.

        This value is useful because we load enough rows of each input to serve
        all possible dependencies.  However, for any given dependency, we only
        want to compute using the actual number of required extra rows for that
        dependency.  We can do so by truncating off the first `offset` rows of
        the loaded data for `input`.

        See Also:
        --------
        :meth:`zipline.pipeline.graph.ExecutionPlan.offset`
        :meth:`zipline.pipeline.engine.ExecutionPlan.mask_and_dates_for_term`
        :meth:`zipline.pipeline.engine.SimplePipelineEngine._inputs_for_term`
        """
        extra = self.extra_rows

        out = {}
        for term in self.graph:
            for dep, requested_extra_rows in term.dependencies.items():
                specialized_dep = maybe_specialize(dep, self.domain)

                # How much bigger is the result for dep compared to term?
                size_difference = extra[specialized_dep] - extra[term]

                # Subtract the portion of that difference that was required by
                # term's lookback window.
                offset = size_difference - requested_extra_rows
                out[term, specialized_dep] = offset

        return out

    @lazyval
    def extra_rows(self):
        """
        A dict mapping `term` -> `# of extra rows to load/compute of `term`.

        Notes:
        ----
        This value depends on the other terms in the graph that require `term`
        **as an input**.  This is not to be confused with `term.dependencies`,
        which describes how many additional rows of `term`'s inputs we need to
        load, and which is determined entirely by `Term` itself.

        Examples:
        --------
        Our graph contains the following terms:

            A = SimpleMovingAverage([USEquityPricing.high], window_length=5)
            B = SimpleMovingAverage([USEquityPricing.high], window_length=10)
            C = SimpleMovingAverage([USEquityPricing.low], window_length=8)

        To compute N rows of A, we need N + 4 extra rows of `high`.
        To compute N rows of B, we need N + 9 extra rows of `high`.
        To compute N rows of C, we need N + 7 extra rows of `low`.

        We store the following extra_row requirements:

        self.extra_rows[high] = 9  # Ensures that we can service B.
        self.extra_rows[low] = 7

        See Also:
        --------
        :meth:`zipline.pipeline.graph.ExecutionPlan.offset`
        :meth:`zipline.pipeline.Term.dependencies`
        """
        return {term: self.graph.nodes[term]["extra_rows"] for term in self.graph.nodes}

    def _ensure_extra_rows(self, term, N):
        """
        Ensure that we're going to compute at least N extra rows of `term`.
        """
        attrs = dict(self.graph.nodes())[term]
        attrs["extra_rows"] = max(N, attrs.get("extra_rows", 0))

    def mask_and_dates_for_term(self, term, root_mask_term, workspace, all_dates):
        """
        Load mask and mask row labels for term.

        Parameters
        ----------
        term : Term
            The term to load the mask and labels for.
        root_mask_term : Term
            The term that represents the root asset exists mask.
        workspace : dict[Term, any]
            The values that have been computed for each term.
        all_dates : pd.DatetimeIndex
            All of the dates that are being computed for in the pipeline.

        Returns:
        -------
        mask : np.ndarray
            The correct mask for this term.
        dates : np.ndarray
            The slice of dates for this term.
        """
        mask = term.mask
        mask_offset = self.extra_rows[mask] - self.extra_rows[term]

        # This offset is computed against root_mask_term because that is what
        # determines the shape of the top-level dates array.
        dates_offset = self.extra_rows[root_mask_term] - self.extra_rows[term]

        return workspace[mask][mask_offset:], all_dates[dates_offset:]

    def _assert_all_loadable_terms_specialized_to(self, domain):
        """Make sure that we've specialized all loadable terms in the graph."""
        for term in self.graph.nodes():
            if isinstance(term, LoadableTerm):
                assert term.domain is domain


# XXX: This function exists because we currently only specialize LoadableTerms
#      when running a Pipeline on a given domain.
def maybe_specialize(term, domain):
    """Specialize a term if it's loadable."""
    if isinstance(term, LoadableTerm):
        return term.specialize(domain)
    return term
