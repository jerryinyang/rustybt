"""Base classes for Pipeline computation graph terms.

This module defines the core term types that make up a Pipeline's computation
graph. Terms represent nodes in the dependency graph, each producing output
data that can be consumed by other terms or returned as pipeline outputs.

The main term types are:

- **Term**: Abstract base class for all pipeline terms. Handles memoization,
  domain specification, and dependency tracking.

- **LoadableTerm**: Terms whose data comes from external loaders (e.g., price
  data from a database). These are leaves in the dependency graph.

- **ComputableTerm**: Terms that compute their output from other terms' outputs
  (e.g., factors, filters, classifiers). These form the interior nodes of the
  dependency graph.

Key concepts:

**Memoization**: Terms are memoized - constructing the same term twice with
the same parameters returns the same object instance. This is critical for
dependency resolution and ensures we only compute each unique term once.

**Dependencies**: Each term declares its dependencies (other terms needed as
inputs) and how many extra rows of each dependency are required (for lookback
windows).

**Domains**: Terms can be generic (work on any data domain) or specialized to
a specific domain (e.g., US equities). LoadableTerms must be specialized before
execution.

**Window Safety**: Window-safe terms produce outputs whose meaning is independent
of temporal context, making them safe to use as inputs to windowed computations.

Examples:
    Create a simple factor that's automatically memoized::

        >>> from rustybt.pipeline.data import EquityPricing
        >>> from rustybt.pipeline.factors import SimpleMovingAverage
        >>> sma1 = SimpleMovingAverage(inputs=[EquityPricing.close], window_length=20)
        >>> sma2 = SimpleMovingAverage(inputs=[EquityPricing.close], window_length=20)
        >>> assert sma1 is sma2  # Same parameters = same object

    Terms track their dependencies automatically::

        >>> sma = SimpleMovingAverage(inputs=[EquityPricing.close], window_length=20)
        >>> # sma.dependencies shows it needs 19 extra rows of close price
        >>> assert EquityPricing.close in sma.dependencies
        >>> assert sma.dependencies[EquityPricing.close] == 19  # window_length - 1

See Also:
    - :class:`rustybt.pipeline.Factor`: ComputableTerm producing numerical output
    - :class:`rustybt.pipeline.Filter`: ComputableTerm producing boolean output
    - :class:`rustybt.pipeline.Classifier`: ComputableTerm producing categorical output
    - :class:`rustybt.pipeline.data.BoundColumn`: LoadableTerm for dataset columns
"""

from abc import ABC, abstractmethod
from bisect import insort
from collections.abc import Mapping
from weakref import WeakValueDictionary

from numpy import (
    array,
    ndarray,
    record,
)
from numpy import (
    dtype as dtype_class,
)

from rustybt.assets import Asset
from rustybt.errors import (
    DTypeNotSpecified,
    InvalidOutputName,
    NonPipelineInputs,
    NonSliceableTerm,
    NonWindowSafeInput,
    NotDType,
    TermInputsNotSpecified,
    TermOutputsEmpty,
    UnsupportedDType,
    WindowLengthNotSpecified,
)
from rustybt.lib.adjusted_array import can_represent_dtype
from rustybt.lib.labelarray import LabelArray
from rustybt.utils.input_validation import expect_types
from rustybt.utils.memoize import classlazyval, lazyval
from rustybt.utils.numpy_utils import (
    bool_dtype,
    categorical_dtype,
    datetime64ns_dtype,
    default_missing_value_for_dtype,
    float64_dtype,
)
from rustybt.utils.sharedoc import (
    PIPELINE_ALIAS_NAME_DOC,
    PIPELINE_DOWNSAMPLING_FREQUENCY_DOC,
    templated_docstring,
)

from .domain import GENERIC, Domain, infer_domain
from .downsample_helpers import expect_downsample_frequency
from .sentinels import NotSpecified


class Term(ABC):
    """Abstract base class for all nodes in a Pipeline computation graph.

    Term is the foundation of the Pipeline API's expression system. Each term
    represents a computation that produces data (factors, filters, classifiers)
    or loads data from external sources (dataset columns). Terms are combined
    to build complex expressions that define a pipeline's logic.

    Core Attributes:
        dtype: The numpy dtype of this term's output (e.g., float64, bool).
        missing_value: The value used to represent missing/invalid data.
        domain: The data domain this term operates on (e.g., US equities).
        window_safe: Whether this term's output is safe for windowed operations.
        ndim: The dimensionality of output (1 for date-only, 2 for date x asset).
        params: Additional parameters that customize this term's behavior.

    Memoization:
        Terms are automatically memoized - constructing a term with the same
        parameters twice returns the same object instance. This is essential
        for dependency resolution and ensures each unique computation happens
        exactly once.

    Type System:
        Most users interact with Term through its concrete subclasses:

        - :class:`~rustybt.pipeline.data.BoundColumn`: Loadable dataset columns
        - :class:`~rustybt.pipeline.Factor`: Numerical computations
        - :class:`~rustybt.pipeline.Filter`: Boolean/filtering computations
        - :class:`~rustybt.pipeline.Classifier`: Categorical computations

    Examples:
        Terms are memoized - same parameters = same object::

            >>> from rustybt.pipeline.data import EquityPricing
            >>> from rustybt.pipeline.factors import SimpleMovingAverage
            >>> sma1 = SimpleMovingAverage(inputs=[EquityPricing.close], window_length=5)
            >>> sma2 = SimpleMovingAverage(inputs=[EquityPricing.close], window_length=5)
            >>> assert sma1 is sma2  # Same object returned

        Different parameters create different term instances::

            >>> sma3 = SimpleMovingAverage(inputs=[EquityPricing.close], window_length=10)
            >>> assert sma1 is not sma3  # Different window_length

        Terms combine to form expressions::

            >>> close = EquityPricing.close.latest
            >>> high = EquityPricing.high.latest
            >>> mid_price = (close + high) / 2  # Arithmetic creates new term
            >>> is_cheap = mid_price < 50.0  # Comparison creates Filter

    Warnings:
        Memoization means term attributes should be treated as immutable after
        construction. Modifying a term's attributes affects all references to
        that term throughout your pipeline, which can cause unexpected behavior.

    Notes:
        - Terms form a directed acyclic graph (DAG) of dependencies
        - LoadableTerms are leaves (no dependencies)
        - ComputableTerms are interior nodes (depend on other terms)
        - The engine executes terms in topological order
    """

    # These are NotSpecified because a subclass is required to provide them.
    dtype = NotSpecified
    missing_value = NotSpecified

    # Subclasses aren't required to provide `params`.  The default behavior is
    # no params.
    params = ()

    # All terms are generic by default.
    domain = GENERIC

    # Determines if a term is safe to be used as a windowed input.
    window_safe = False

    # The dimensions of the term's output (1D or 2D).
    ndim = 2

    _term_cache = WeakValueDictionary()

    def __new__(
        cls,
        domain=NotSpecified,
        dtype=NotSpecified,
        missing_value=NotSpecified,
        window_safe=NotSpecified,
        ndim=NotSpecified,
        # params is explicitly not allowed to be passed to an instance.
        *args,
        **kwargs,
    ):
        """
        Memoized constructor for Terms.

        Caching previously-constructed Terms is useful because it allows us to
        only compute equivalent sub-expressions once when traversing a Pipeline
        dependency graph.

        Caching previously-constructed Terms is **sane** because terms and
        their inputs are both conceptually immutable.
        """
        # Subclasses can override these class-level attributes to provide
        # different default values for instances.
        if domain is NotSpecified:
            domain = cls.domain
        if dtype is NotSpecified:
            dtype = cls.dtype
        if missing_value is NotSpecified:
            missing_value = cls.missing_value
        if ndim is NotSpecified:
            ndim = cls.ndim
        if window_safe is NotSpecified:
            window_safe = cls.window_safe

        dtype, missing_value = validate_dtype(
            cls.__name__,
            dtype,
            missing_value,
        )
        params = cls._pop_params(kwargs)

        identity = cls._static_identity(
            domain=domain,
            dtype=dtype,
            missing_value=missing_value,
            window_safe=window_safe,
            ndim=ndim,
            params=params,
            *args,
            **kwargs,
        )

        try:
            return cls._term_cache[identity]
        except KeyError:
            new_instance = cls._term_cache[identity] = (
                super(Term, cls)
                .__new__(cls)
                ._init(
                    domain=domain,
                    dtype=dtype,
                    missing_value=missing_value,
                    window_safe=window_safe,
                    ndim=ndim,
                    params=params,
                    *args,
                    **kwargs,
                )
            )
            return new_instance

    @classmethod
    def _pop_params(cls, kwargs):
        """
        Pop entries from the `kwargs` passed to cls.__new__ based on the values
        in `cls.params`.

        Parameters
        ----------
        kwargs : dict
            The kwargs passed to cls.__new__.

        Returns:
        -------
        params : list[(str, object)]
            A list of string, value pairs containing the entries in cls.params.

        Raises:
        ------
        TypeError
            Raised if any parameter values are not passed or not hashable.
        """
        params = cls.params
        if not isinstance(params, Mapping):
            params = dict.fromkeys(params, NotSpecified)
        param_values = []
        for key, default_value in params.items():
            try:
                value = kwargs.pop(key, default_value)
                if value is NotSpecified:
                    raise KeyError(key)

                # Check here that the value is hashable so that we fail here
                # instead of trying to hash the param values tuple later.
                hash(value)
            except KeyError as exc:
                raise TypeError(f"{cls.__name__} expected a keyword parameter {key!r}.") from exc
            except TypeError as exc:
                # Value wasn't hashable.
                raise TypeError(
                    f"{cls.__name__} expected a hashable value for parameter "
                    f"{key!r}, but got {value!r} instead."
                ) from exc

            param_values.append((key, value))
        return tuple(param_values)

    def __init__(self, *args, **kwargs):
        """
        Noop constructor to play nicely with our caching __new__.  Subclasses
        should implement _init instead of this method.

        When a class' __new__ returns an instance of that class, Python will
        automatically call __init__ on the object, even if a new object wasn't
        actually constructed.  Because we memoize instances, we often return an
        object that was already initialized from __new__, in which case we
        don't want to call __init__ again.

        Subclasses that need to initialize new instances should override _init,
        which is guaranteed to be called only once.
        """
        pass

    @expect_types(key=Asset)
    def __getitem__(self, key):
        if isinstance(self, LoadableTerm):
            raise NonSliceableTerm(term=self)

        from .mixins import SliceMixin

        slice_type = type(self)._with_mixin(SliceMixin)
        return slice_type(self, key)

    @classmethod
    def _static_identity(cls, domain, dtype, missing_value, window_safe, ndim, params):
        """
        Return the identity of the Term that would be constructed from the
        given arguments.

        Identities that compare equal will cause us to return a cached instance
        rather than constructing a new one.  We do this primarily because it
        makes dependency resolution easier.

        This is a classmethod so that it can be called from Term.__new__ to
        determine whether to produce a new instance.
        """
        return (cls, domain, dtype, missing_value, window_safe, ndim, params)

    def _init(self, domain, dtype, missing_value, window_safe, ndim, params):
        """
        Parameters
        ----------
        domain : zipline.pipeline.domain.Domain
            The domain of this term.
        dtype : np.dtype
            Dtype of this term's output.
        missing_value : object
            Missing value for this term.
        ndim : 1 or 2
            The dimensionality of this term.
        params : tuple[(str, hashable)]
            Tuple of key/value pairs of additional parameters.
        """
        self.domain = domain
        self.dtype = dtype
        self.missing_value = missing_value
        self.window_safe = window_safe
        self.ndim = ndim

        for name, _ in params:
            if hasattr(self, name):
                raise TypeError(
                    f"Parameter {name!r} conflicts with already-present"
                    f" attribute with value {getattr(self, name)!r}."
                )
            # TODO: Consider setting these values as attributes and replacing
            # the boilerplate in NumericalExpression, Rank, and
            # PercentileFilter.

        self.params = dict(params)

        # Make sure that subclasses call super() in their _validate() methods
        # by setting this flag.  The base class implementation of _validate
        # should set this flag to True.
        self._subclass_called_super_validate = False
        self._validate()
        assert self._subclass_called_super_validate, (
            "Term._validate() was not called.\n"
            "This probably means that you overrode _validate"
            " without calling super()."
        )
        del self._subclass_called_super_validate

        return self

    def _validate(self):
        """
        Assert that this term is well-formed.  This should be called exactly
        once, at the end of Term._init().
        """
        # mark that we got here to enforce that subclasses overriding _validate
        # call super().
        self._subclass_called_super_validate = True

    def compute_extra_rows(self, all_dates, start_date, end_date, min_extra_rows):
        """
        Calculate the number of extra rows needed to compute ``self``.

        Must return at least ``min_extra_rows``, and the default implementation
        is to just return ``min_extra_rows``.  This is overridden by
        downsampled terms to ensure that the first date computed is a
        recomputation date.

        Parameters
        ----------
        all_dates : pd.DatetimeIndex
            The trading sessions against which ``self`` will be computed.
        start_date : pd.Timestamp
            The first date for which final output is requested.
        end_date : pd.Timestamp
            The last date for which final output is requested.
        min_extra_rows : int
            The minimum number of extra rows required of ``self``, as
            determined by other terms that depend on ``self``.

        Returns:
        -------
        extra_rows : int
            The number of extra rows to compute.  Must be at least
            ``min_extra_rows``.
        """
        return min_extra_rows

    @property
    @abstractmethod
    def inputs(self):
        """
        A tuple of other Terms needed as inputs for ``self``.
        """
        raise NotImplementedError("inputs")

    @property
    @abstractmethod
    def windowed(self):
        """
        Boolean indicating whether this term is a trailing-window computation.
        """
        raise NotImplementedError("windowed")

    @property
    @abstractmethod
    def mask(self):
        """
        A :class:`~zipline.pipeline.Filter` representing asset/date pairs to
        while computing this Term. True means include; False means exclude.
        """
        raise NotImplementedError("mask")

    @property
    @abstractmethod
    def dependencies(self):
        """
        A dictionary mapping terms that must be computed before `self` to the
        number of extra rows needed for those terms.
        """
        raise NotImplementedError("dependencies")

    def graph_repr(self):
        """A short repr to use when rendering GraphViz graphs."""
        # Default graph_repr is just the name of the type.
        return type(self).__name__

    def recursive_repr(self):
        """A short repr to use when recursively rendering terms with inputs."""
        # Default recursive_repr is just the name of the type.
        return type(self).__name__


class AssetExists(Term):
    """Special term representing the existence mask for assets.

    AssetExists produces a boolean matrix indicating which assets existed
    (were tradeable) on which dates. This is the fundamental building block
    for pipeline computations - it defines the universe of valid (date, asset)
    pairs.

    This term serves as the default mask for all pipeline terms that don't
    explicitly specify a mask. It ensures computations only happen for assets
    that actually existed at the time.

    Implementation Details:
        - Computed directly by PipelineEngine, not through loaders
        - Always available in the workspace for any term to use
        - Based on asset lifetime data from the AssetFinder
        - Not a Filter subclass (special-cased by the engine)

    The lifetime data comes from each asset's start_date and end_date,
    which indicate when the asset began and ceased trading.

    Examples:
        AssetExists is used implicitly as the default mask::

            >>> from rustybt.pipeline.factors import SimpleMovingAverage
            >>> from rustybt.pipeline.data import EquityPricing
            >>> # This factor implicitly uses AssetExists() as its mask
            >>> sma = SimpleMovingAverage(inputs=[EquityPricing.close], window_length=20)
            >>> assert sma.mask is AssetExists()

        You can use a different mask to further restrict the universe::

            >>> from rustybt.pipeline.filters import StaticAssets
            >>> # Only compute for specific assets
            >>> my_mask = StaticAssets([asset1, asset2])
            >>> sma_masked = SimpleMovingAverage(
            ...     inputs=[EquityPricing.close],
            ...     window_length=20,
            ...     mask=my_mask
            ... )

    See Also:
        :class:`rustybt.assets.AssetFinder`: Provides asset lifetime data.
        :meth:`rustybt.pipeline.engine.SimplePipelineEngine._compute_root_mask`:
            Where AssetExists is actually computed.
    """

    dtype = bool_dtype
    dataset = None
    inputs = ()
    dependencies = {}
    mask = None
    windowed = False

    def __repr__(self):
        return "AssetExists()"

    graph_repr = __repr__

    def _compute(self, today, assets, out):
        raise NotImplementedError(
            "AssetExists cannot be computed directly. Check your PipelineEngine configuration."
        )


class InputDates(Term):
    """Special 1-dimensional term providing date labels for computations.

    InputDates produces a column vector of datetime64 values representing
    the trading dates for which a term is being computed. This is used by
    terms that need to know the actual dates they're computing for (e.g.,
    for date-based logic or for indexing into date-specific data).

    Unlike most terms which are 2-dimensional (dates x assets), InputDates
    is 1-dimensional (dates only). It's automatically available in the
    workspace for any term that needs it.

    Implementation Details:
        - Computed directly by PipelineEngine before term execution
        - Always available in the workspace
        - Has shape (len(dates), 1) - column vector not scalar
        - Window-safe (dates don't change meaning with context)

    Examples:
        InputDates is used internally by the engine::

            >>> # In _populate_initial_workspace:
            >>> workspace = {
            ...     root_mask_term: mask_values,
            ...     InputDates(): dates_column,  # Date labels
            ... }

        Custom terms can access dates through their inputs::

            >>> class DateAwareFactor(CustomFactor):
            ...     inputs = [EquityPricing.close]
            ...     window_length = 1
            ...
            ...     def compute(self, today, assets, out, close):
            ...         # today parameter gives you the date
            ...         if today.month == 12:
            ...             out[:] = close[-1] * 1.1  # Holiday bonus
            ...         else:
            ...             out[:] = close[-1]

    See Also:
        :class:`AssetExists`: The 2D asset existence mask.
        :meth:`rustybt.pipeline.engine.SimplePipelineEngine._populate_initial_workspace`:
            Where InputDates is added to the workspace.
    """

    ndim = 1
    dataset = None
    dtype = datetime64ns_dtype
    inputs = ()
    dependencies = {}
    mask = None
    windowed = False
    window_safe = True

    def __repr__(self):
        return "InputDates()"

    graph_repr = __repr__

    def _compute(self, today, assets, out):
        raise NotImplementedError(
            "InputDates cannot be computed directly. Check your PipelineEngine configuration."
        )


class LoadableTerm(Term):
    """Base class for terms whose data comes from external sources.

    LoadableTerms represent data that must be loaded from external data sources
    (databases, files, APIs, etc.) rather than computed from other terms. They
    are the leaves of the Pipeline computation graph - they have no inputs,
    only outputs.

    The PipelineEngine loads these terms by:
    1. Finding the appropriate PipelineLoader via get_loader()
    2. Specializing the term to the execution domain
    3. Calling the loader's load_adjusted_array() method
    4. Storing the result in the workspace

    Key Characteristics:
        - windowed = False: LoadableTerms provide raw data, not windowed views
        - inputs = (): No other terms as inputs
        - Must be specialized to a domain before execution
        - Loaded in batches when possible for efficiency

    The primary concrete subclass is BoundColumn, which represents columns
    from DataSets (like EquityPricing.close).

    Examples:
        BoundColumn is the most common LoadableTerm::

            >>> from rustybt.pipeline.data import EquityPricing
            >>> close = EquityPricing.close  # This is a BoundColumn (LoadableTerm)
            >>> assert isinstance(close, LoadableTerm)
            >>> assert close.dataset == EquityPricing
            >>> assert close.inputs == ()  # No inputs - data is loaded

        LoadableTerms must be specialized to a domain::

            >>> from rustybt.pipeline.domain import US_EQUITIES
            >>> generic_term = EquityPricing.close  # Generic initially
            >>> specialized = generic_term.specialize(US_EQUITIES)
            >>> assert specialized.domain is US_EQUITIES

        The engine batches loads from the same loader::

            >>> # These would be loaded together in one batch:
            >>> close = EquityPricing.close.latest
            >>> high = EquityPricing.high.latest
            >>> low = EquityPricing.low.latest
            >>> # Engine calls loader.load_adjusted_array([close, high, low], ...)

    See Also:
        :class:`rustybt.pipeline.data.BoundColumn`: Main LoadableTerm subclass.
        :class:`rustybt.pipeline.loaders.base.PipelineLoader`: Loader interface.
        :class:`ComputableTerm`: Terms that compute from other terms.
    """

    windowed = False
    inputs = ()

    @lazyval
    def dependencies(self):
        return {self.mask: 0}


class ComputableTerm(Term):
    """Base class for terms that compute their output from other terms.

    ComputableTerms represent computations - they take inputs (other terms)
    and produce output by applying a computation function. They form the
    interior nodes of the Pipeline computation graph, with LoadableTerms as
    leaves and ComputableTerms building up layers of derived computations.

    The computation process:
    1. Engine loads/computes all input terms first (dependency order)
    2. Engine calls _compute() with the input data
    3. Term produces output array matching expected shape and dtype
    4. Engine stores result in workspace for downstream terms to use

    Key Characteristics:
        - inputs: Tuple of terms whose outputs are needed for computation
        - window_length: How many rows of history are needed (0 for point-in-time)
        - mask: Filter determining which (date, asset) pairs to compute
        - windowed: Whether this term needs historical data (window_length > 0)

    The three main subclasses are:
        - **Factor**: Produces numerical output (float64, etc.)
        - **Filter**: Produces boolean output (bool)
        - **Classifier**: Produces categorical output (int64 labels)

    Examples:
        A simple moving average is a ComputableTerm::

            >>> from rustybt.pipeline.factors import SimpleMovingAverage
            >>> from rustybt.pipeline.data import EquityPricing
            >>> sma = SimpleMovingAverage(
            ...     inputs=[EquityPricing.close],
            ...     window_length=20
            ... )
            >>> # sma.inputs = (EquityPricing.close,)
            >>> # sma.windowed = True (window_length > 0)
            >>> # sma.dependencies = {EquityPricing.close: 19, AssetExists(): 0}

        ComputableTerms can have multiple inputs::

            >>> from rustybt.pipeline.factors import Returns
            >>> # Returns needs both open and close prices
            >>> returns = Returns(window_length=1)
            >>> assert len(returns.inputs) == 2  # open and close

        Terms build expression trees automatically::

            >>> close = EquityPricing.close.latest  # LoadableTerm
            >>> high = EquityPricing.high.latest    # LoadableTerm
            >>> spread = high - close               # ComputableTerm (subtraction)
            >>> pct_spread = spread / close * 100   # ComputableTerm (division, multiplication)
            >>> assert isinstance(pct_spread, ComputableTerm)
            >>> # Engine will compute: close -> high -> spread -> pct_spread

        Custom computations via CustomFactor::

            >>> from rustybt.pipeline.factors import CustomFactor
            >>> class Range(CustomFactor):
            ...     inputs = [EquityPricing.high, EquityPricing.low]
            ...     window_length = 1
            ...     def compute(self, today, assets, out, highs, lows):
            ...         out[:] = highs[-1] - lows[-1]

    See Also:
        :class:`rustybt.pipeline.Factor`: Numerical ComputableTerm.
        :class:`rustybt.pipeline.Filter`: Boolean ComputableTerm.
        :class:`rustybt.pipeline.Classifier`: Categorical ComputableTerm.
        :class:`LoadableTerm`: Terms that load data vs compute it.
    """

    inputs = NotSpecified
    outputs = NotSpecified
    window_length = NotSpecified
    mask = NotSpecified
    domain = NotSpecified

    def __new__(
        cls,
        inputs=inputs,
        outputs=outputs,
        window_length=window_length,
        mask=mask,
        domain=domain,
        *args,
        **kwargs,
    ):
        if inputs is NotSpecified:
            inputs = cls.inputs

        # Having inputs = NotSpecified is an error, but we handle it later
        # in self._validate rather than here.
        if inputs is not NotSpecified:
            # Allow users to specify lists as class-level defaults, but
            # normalize to a tuple so that inputs is hashable.
            inputs = tuple(inputs)

            # Make sure all our inputs are valid pipeline objects before trying
            # to infer a domain.
            non_terms = [t for t in inputs if not isinstance(t, Term)]
            if non_terms:
                raise NonPipelineInputs(cls.__name__, non_terms)

            if domain is NotSpecified:
                domain = infer_domain(inputs)

        if outputs is NotSpecified:
            outputs = cls.outputs
        if outputs is not NotSpecified:
            outputs = tuple(outputs)

        if mask is NotSpecified:
            mask = cls.mask
        if mask is NotSpecified:
            mask = AssetExists()

        if window_length is NotSpecified:
            window_length = cls.window_length

        return super(ComputableTerm, cls).__new__(
            cls,
            inputs=inputs,
            outputs=outputs,
            mask=mask,
            window_length=window_length,
            domain=domain,
            *args,
            **kwargs,
        )

    def _init(self, inputs, outputs, window_length, mask, *args, **kwargs):
        self.inputs = inputs
        self.outputs = outputs
        self.window_length = window_length
        self.mask = mask
        return super(ComputableTerm, self)._init(*args, **kwargs)

    @classmethod
    def _static_identity(cls, inputs, outputs, window_length, mask, *args, **kwargs):
        return (
            super(ComputableTerm, cls)._static_identity(*args, **kwargs),
            inputs,
            outputs,
            window_length,
            mask,
        )

    def _validate(self):
        super(ComputableTerm, self)._validate()

        # Check inputs.
        if self.inputs is NotSpecified:
            raise TermInputsNotSpecified(termname=type(self).__name__)

        if not isinstance(self.domain, Domain):
            raise TypeError(
                f"Expected {type(self).__name__}.domain to be an instance of Domain, "
                f"but got {type(self.domain)}."
            )

        # Check outputs.
        if self.outputs is NotSpecified:
            pass
        elif not self.outputs:
            raise TermOutputsEmpty(termname=type(self).__name__)
        else:
            # Raise an exception if there are any naming conflicts between the
            # term's output names and certain attributes.
            disallowed_names = [attr for attr in dir(ComputableTerm) if not attr.startswith("_")]

            # The name 'compute' is an added special case that is disallowed.
            # Use insort to add it to the list in alphabetical order.
            insort(disallowed_names, "compute")

            for output in self.outputs:
                if output.startswith("_") or output in disallowed_names:
                    raise InvalidOutputName(
                        output_name=output,
                        termname=type(self).__name__,
                        disallowed_names=disallowed_names,
                    )

        if self.window_length is NotSpecified:
            raise WindowLengthNotSpecified(termname=type(self).__name__)

        if self.mask is NotSpecified:
            # This isn't user error, this is a bug in our code.
            raise AssertionError(f"{self} has no mask")

        if self.window_length > 1:
            for child in self.inputs:
                if not child.window_safe:
                    raise NonWindowSafeInput(parent=self, child=child)

    def _compute(self, inputs, dates, assets, mask):
        """
        Subclasses should implement this to perform actual computation.

        This is named ``_compute`` rather than just ``compute`` because
        ``compute`` is reserved for user-supplied functions in
        CustomFilter/CustomFactor/CustomClassifier.
        """
        raise NotImplementedError("_compute")

    # NOTE: This is a method rather than a property because ABCMeta tries to
    #       access all abstract attributes of its child classes to see if
    #       they've been implemented. These accesses happen during subclass
    #       creation, before the new subclass has been bound to a name in its
    #       defining scope. Filter, Factor, and Classifier each implement this
    #       method to return themselves, but if the method is invoked before
    #       class definition is finished (which happens if this is a property),
    #       they fail with a NameError.
    @classmethod
    @abstractmethod
    def _principal_computable_term_type(cls):
        """
        Return the "principal" type for a ComputableTerm.

        This returns either Filter, Factor, or Classifier, depending on the
        type of ``cls``. It is used to implement behaviors like ``downsample``
        and ``if_then_else`` that are implemented on all ComputableTerms, but
        that need to produce different output types depending on the type of
        the receiver.
        """
        raise NotImplementedError("_principal_computable_term_type")

    @lazyval
    def windowed(self):
        """
        Whether or not this term represents a trailing window computation.

        If term.windowed is truthy, its compute_from_windows method will be
        called with instances of AdjustedArray as inputs.

        If term.windowed is falsey, its compute_from_baseline will be called
        with instances of np.ndarray as inputs.
        """
        return self.window_length is not NotSpecified and self.window_length > 0

    @lazyval
    def dependencies(self):
        """
        The number of extra rows needed for each of our inputs to compute this
        term.
        """
        extra_input_rows = max(0, self.window_length - 1)
        out = {}
        for term in self.inputs:
            out[term] = extra_input_rows
        out[self.mask] = 0
        return out

    @expect_types(data=ndarray)
    def postprocess(self, data):
        """
        Called with an result of ``self``, unravelled (i.e. 1-dimensional)
        after any user-defined screens have been applied.

        This is mostly useful for transforming the dtype of an output, e.g., to
        convert a LabelArray into a pandas Categorical.

        The default implementation is to just return data unchanged.
        """
        # starting with pandas 1.4, record arrays are no longer supported as DataFrame columns
        if isinstance(data[0], record):
            return [tuple(r) for r in data]
        return data

    def to_workspace_value(self, result, assets):
        """
        Called with a column of the result of a pipeline. This needs to put
        the data into a format that can be used in a workspace to continue
        doing computations.

        Parameters
        ----------
        result : pd.Series
            A multiindexed series with (dates, assets) whose values are the
            results of running this pipeline term over the dates.
        assets : pd.Index
            All of the assets being requested. This allows us to correctly
            shape the workspace value.

        Returns:
        -------
        workspace_value : array-like
            An array like value that the engine can consume.
        """
        return (
            result.unstack()
            .fillna(self.missing_value)
            .reindex(columns=assets, fill_value=self.missing_value)
            .values
        )

    @expect_downsample_frequency
    @templated_docstring(frequency=PIPELINE_DOWNSAMPLING_FREQUENCY_DOC)
    def downsample(self, frequency):
        """
        Make a term that computes from ``self`` at lower-than-daily frequency.

        Parameters
        ----------
        {frequency}
        """
        from .mixins import DownsampledMixin

        downsampled_type = type(self)._with_mixin(DownsampledMixin)
        return downsampled_type(term=self, frequency=frequency)

    @templated_docstring(name=PIPELINE_ALIAS_NAME_DOC)
    def alias(self, name):
        """
        Make a term from ``self`` that names the expression.

        Parameters
        ----------
        {name}

        Returns:
        -------
        aliased : Aliased
            ``self`` with a name.

        Notes:
        -----
        This is useful for giving a name to a numerical or boolean expression.
        """
        from .mixins import AliasedMixin

        aliased_type = type(self)._with_mixin(AliasedMixin)
        return aliased_type(term=self, name=name)

    def isnull(self):
        """
        A Filter producing True for values where this Factor has missing data.

        Equivalent to self.isnan() when ``self.dtype`` is float64.
        Otherwise equivalent to ``self.eq(self.missing_value)``.

        Returns:
        -------
        filter : zipline.pipeline.Filter
        """
        if self.dtype == bool_dtype:
            raise TypeError("isnull() is not supported for Filters")

        from .filters import NullFilter

        if self.dtype == float64_dtype:
            # Using isnan is more efficient when possible because we can fold
            # the isnan computation with other NumExpr expressions.
            return self.isnan()
        else:
            return NullFilter(self)

    def notnull(self):
        """
        A Filter producing True for values where this Factor has complete data.

        Equivalent to ``~self.isnan()` when ``self.dtype`` is float64.
        Otherwise equivalent to ``(self != self.missing_value)``.

        Returns:
        -------
        filter : zipline.pipeline.Filter
        """
        if self.dtype == bool_dtype:
            raise TypeError("notnull() is not supported for Filters")

        from .filters import NotNullFilter

        return NotNullFilter(self)

    def fillna(self, fill_value):
        """
        Create a new term that fills missing values of this term's output with
        ``fill_value``.

        Parameters
        ----------
        fill_value : zipline.pipeline.ComputableTerm, or object.
            Object to use as replacement for missing values.

            If a ComputableTerm (e.g. a Factor) is passed, that term's results
            will be used as fill values.

            If a scalar (e.g. a number) is passed, the scalar will be used as a
            fill value.

        Examples:
        --------
        **Filling with a Scalar:**

        Let ``f`` be a Factor which would produce the following output::

                         AAPL   MSFT    MCD     BK
            2017-03-13    1.0    NaN    3.0    4.0
            2017-03-14    1.5    2.5    NaN    NaN

        Then ``f.fillna(0)`` produces the following output::

                         AAPL   MSFT    MCD     BK
            2017-03-13    1.0    0.0    3.0    4.0
            2017-03-14    1.5    2.5    0.0    0.0

        **Filling with a Term:**

        Let ``f`` be as above, and let ``g`` be another Factor which would
        produce the following output::

                         AAPL   MSFT    MCD     BK
            2017-03-13   10.0   20.0   30.0   40.0
            2017-03-14   15.0   25.0   35.0   45.0

        Then, ``f.fillna(g)`` produces the following output::

                         AAPL   MSFT    MCD     BK
            2017-03-13    1.0   20.0    3.0    4.0
            2017-03-14    1.5    2.5   35.0   45.0

        Returns:
        -------
        filled : zipline.pipeline.ComputableTerm
            A term computing the same results as ``self``, but with missing
            values filled in using values from ``fill_value``.
        """
        if self.dtype == bool_dtype:
            raise TypeError("fillna() is not supported for Filters")

        if isinstance(fill_value, LoadableTerm):
            raise TypeError(
                f"Can't use expression {fill_value} as a fill value. Did you mean to "
                "append '.latest?'"
            )
        elif isinstance(fill_value, ComputableTerm):
            if_false = fill_value
        else:
            # Assume we got a scalar value. Make sure it's compatible with our
            # dtype.
            try:
                fill_value = _coerce_to_dtype(fill_value, self.dtype)
            except TypeError as exc:
                raise TypeError(
                    f"Fill value {fill_value!r} is not a valid choice "
                    f"for term {type(self).__name__} with dtype {self.dtype}.\n\n"
                    f"Coercion attempt failed with: {exc}"
                ) from exc

            if_false = self._constant_type(
                const=fill_value,
                dtype=self.dtype,
                missing_value=self.missing_value,
            )

        return self.notnull().if_else(if_true=self, if_false=if_false)

    @classlazyval
    def _constant_type(cls):
        from .mixins import ConstantMixin

        return cls._with_mixin(ConstantMixin)

    @classlazyval
    def _if_else_type(cls):
        from .mixins import IfElseMixin

        return cls._with_mixin(IfElseMixin)

    def __repr__(self):
        return ("{type}([{inputs}], {window_length})").format(
            type=type(self).__name__,
            inputs=", ".join(i.recursive_repr() for i in self.inputs),
            window_length=self.window_length,
        )

    def recursive_repr(self):
        return type(self).__name__ + "(...)"

    @classmethod
    def _with_mixin(cls, mixin_type):
        return mixin_type.universal_mixin_specialization(
            cls._principal_computable_term_type(),
        )


def validate_dtype(termname, dtype, missing_value):
    """
    Validate a `dtype` and `missing_value` passed to Term.__new__.

    Ensures that we know how to represent ``dtype``, and that missing_value
    is specified for types without default missing values.

    Returns:
    -------
    validated_dtype, validated_missing_value : np.dtype, any
        The dtype and missing_value to use for the new term.

    Raises:
    ------
    DTypeNotSpecified
        When no dtype was passed to the instance, and the class doesn't
        provide a default.
    NotDType
        When either the class or the instance provides a value not
        coercible to a numpy dtype.
    NoDefaultMissingValue
        When dtype requires an explicit missing_value, but
        ``missing_value`` is NotSpecified.
    """
    if dtype is NotSpecified:
        raise DTypeNotSpecified(termname=termname)

    try:
        dtype = dtype_class(dtype)
    except TypeError as exc:
        raise NotDType(dtype=dtype, termname=termname) from exc

    if not can_represent_dtype(dtype):
        raise UnsupportedDType(dtype=dtype, termname=termname)

    if missing_value is NotSpecified:
        missing_value = default_missing_value_for_dtype(dtype)

    try:
        _coerce_to_dtype(missing_value, dtype)
    except TypeError as exc:
        raise TypeError(
            f"Missing value {missing_value!r} is not a valid choice "
            f"for term {termname} with dtype {dtype}.\n\n"
            f"Coercion attempt failed with: {exc}"
        ) from exc

    return dtype, missing_value


def _assert_valid_categorical_missing_value(value):
    """
    Check that value is a valid categorical missing_value.

    Raises a TypeError if the value is cannot be used as the missing_value for
    a categorical_dtype Term.
    """
    label_types = LabelArray.SUPPORTED_SCALAR_TYPES
    if not isinstance(value, label_types):
        raise TypeError(
            "String-dtype classifiers can only produce {types}.".format(
                types=" or ".join([t.__name__ for t in label_types])
            )
        )


def _coerce_to_dtype(value, dtype):
    if dtype == categorical_dtype:
        # This check is necessary because we use object dtype for
        # categoricals, and numpy will allow us to promote numerical
        # values to object even though we don't support them.
        _assert_valid_categorical_missing_value(value)
        return value
    else:
        # For any other type, cast using the same rules as numpy's astype
        # function with casting='same_kind'.
        #
        # 'same_kind' allows casting between things like float32 and float64,
        # but not between str and int. Note that the name is somewhat
        # misleading, since it does allow conversion between different dtype
        # kinds in some cases. In particular, conversion from int to float is
        # allowed.
        return array([value]).astype(dtype=dtype, casting="same_kind")[0]
