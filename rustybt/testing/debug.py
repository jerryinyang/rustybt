"""Debugging utilities for test development.

Provides tools for diagnosing and visualizing Method Resolution Order (MRO)
failures that can occur when using complex test fixture inheritance patterns.

Functions:
    debug_mro_failure: Generate detailed MRO failure diagnostics
    build_linearization_graph: Construct graph of class dependencies
    verbosify_label: Convert graph labels to readable format

Examples:
    Debug MRO failure::

        from rustybt.testing.debug import debug_mro_failure

        try:
            class BadClass(Base1, Base2, Base3):
                pass
        except TypeError as e:
            if '(MRO)' in str(e):
                msg = debug_mro_failure('BadClass', (Base1, Base2, Base3))
                print(msg)
                # Shows cycle and optionally renders GraphViz diagram
"""

import os
import subprocess

import networkx as nx


def debug_mro_failure(name, bases):
    """Generate detailed diagnostics for Method Resolution Order failures.

    When Python cannot compute a valid MRO for a class, this function
    analyzes the inheritance graph to identify cycles and provides
    detailed error messages. Optionally renders a GraphViz visualization.

    Args:
        name: Name of the class being created.
        bases: Tuple of base classes.

    Returns:
        str: Detailed error message explaining the MRO failure, including:
            - The cycle preventing linearization
            - For each edge in the cycle, why that ordering is required
            - Optional path to GraphViz rendering (if DRAW_MRO_FAILURES set)

    Examples:
        Diagnose inheritance conflict::

            from rustybt.testing.debug import debug_mro_failure

            error_msg = debug_mro_failure(
                'ProblemClass',
                (WithA, WithB, WithC)
            )
            print(error_msg)
            # Output shows: "Cycle found when trying to compute MRO..."
    """
    graph = build_linearization_graph(name, bases)
    cycles = sorted(nx.cycles.simple_cycles(graph), key=len)
    cycle = cycles[0]

    if os.environ.get("DRAW_MRO_FAILURES"):
        output_file = name + ".dot"
    else:
        output_file = None

    # Return a nicely formatted error describing the cycle.
    lines = [f"Cycle found when trying to compute MRO for {name}:\n"]
    for source, dest in list(zip(cycle, cycle[1:], strict=False)) + [(cycle[-1], cycle[0])]:
        label = verbosify_label(graph.get_edge_data(source, dest)["label"])
        lines.append(f"{source} comes before {dest}: cause={label}")

    # Either graphviz graph and tell the user where it went, or tell people how
    # to enable that feature.
    lines.append("")
    if output_file is None:
        lines.append(
            "Set the DRAW_MRO_FAILURES environment variable to"
            " render a GraphViz graph of this cycle."
        )
    else:
        try:
            nx.write_dot(graph.subgraph(cycle), output_file)
            subprocess.check_call(["dot", "-T", "svg", "-O", output_file])
            lines.append("GraphViz rendering written to " + output_file + ".svg")
        except Exception as e:
            lines.append(f"Failed to write GraphViz graph. Error was {e}")

    return "\n".join(lines)


def build_linearization_graph(child_name, bases):
    g = nx.DiGraph()
    _build_linearization_graph(g, type(child_name, (object,), {}), bases)
    return g


def _build_linearization_graph(g, child, bases):
    add_implicit_edges(g, child, bases)
    add_direct_edges(g, child, bases)


def add_direct_edges(g, child, bases):
    # Enforce that bases are ordered in the order that the appear in child's
    # class declaration.
    g.add_path([b.__name__ for b in bases], label=child.__name__ + "(O)")

    # Add direct edges.
    for base in bases:
        g.add_edge(child.__name__, base.__name__, label=child.__name__ + "(D)")
        add_direct_edges(g, base, base.__bases__)


def add_implicit_edges(g, child, bases):
    # Enforce that bases' previous linearizations are preserved.
    for base in bases:
        g.add_path(
            [b.__name__ for b in base.mro()],
            label=base.__name__ + "(L)",
        )


VERBOSE_LABELS = {
    "(D)": "(Direct Subclass)",
    "(O)": "(Parent Class Order)",
    "(L)": "(Linearization Order)",
}


def verbosify_label(label):
    prefix = label[:-3]
    suffix = label[-3:]
    return " ".join([prefix, VERBOSE_LABELS[suffix]])
