"""Example trading algorithms demonstrating rustybt features.

This module provides a collection of example trading algorithms that demonstrate
various rustybt features and trading strategies. These examples are designed
to be educational and serve as starting points for developing custom algorithms.

Available Examples:
    - buy_and_hold: Simple buy-and-hold strategy for multiple stocks
    - buyapple: Basic example buying Apple stock repeatedly
    - dual_moving_average: Moving average crossover strategy
    - momentum_pipeline: Pipeline-based momentum strategy
    - olmar: Online Moving Average Reversion strategy
    - dual_ema_talib: EMA crossover using TA-Lib (requires talib)

Usage:
    Examples can be run individually or loaded programmatically for testing::

        from rustybt.examples import load_example_modules, run_example

        # Load all available examples
        examples = load_example_modules()

        # Run a specific example
        results = run_example(examples, 'buyapple', environ={})

Note:
    Some examples may require specific data bundles or have dependencies
    (like TA-Lib). Check individual example docstrings for requirements.
"""

import os
from importlib import import_module

# talib is not yet compatible with numpy 2.0
import numpy
from packaging.version import Version
from toolz import merge

from rustybt import run_algorithm
from rustybt.utils.calendar_utils import get_calendar, register_calendar_alias

NUMPY2 = Version(numpy.__version__) >= Version("2.0.0")
if not NUMPY2:
    try:
        import talib
    except ImportError:
        talib = None


# These are used by test_examples.py to discover the examples to run.
def load_example_modules():
    example_modules = {}
    for f in os.listdir(os.path.dirname(__file__)):
        if (NUMPY2 or talib is None) and f == "dual_ema_talib.py":
            continue
        if not f.endswith(".py") or f == "__init__.py" or f == "buyapple_ide.py":
            continue
        modname = f[: -len(".py")]
        mod = import_module("." + modname, package=__name__)
        example_modules[modname] = mod
        globals()[modname] = mod

        # Remove noise from loop variables.
        del f, modname, mod
    return example_modules


# Columns that we expect to be able to reliably deterministic
# Doesn't include fields that have UUIDS.
_cols_to_check = [
    "algo_volatility",
    "algorithm_period_return",
    "alpha",
    "benchmark_period_return",
    "benchmark_volatility",
    "beta",
    "capital_used",
    "ending_cash",
    "ending_exposure",
    "ending_value",
    "excess_return",
    "gross_leverage",
    "long_exposure",
    "long_value",
    "longs_count",
    "max_drawdown",
    "max_leverage",
    "net_leverage",
    "period_close",
    "period_label",
    "period_open",
    "pnl",
    "portfolio_value",
    "positions",
    "returns",
    "short_exposure",
    "short_value",
    "shorts_count",
    "sortino",
    "starting_cash",
    "starting_exposure",
    "starting_value",
    "trading_days",
    "treasury_period_return",
]


def run_example(example_modules, example_name, environ, benchmark_returns=None):
    """Run an example module from rustybt.examples."""
    mod = example_modules[example_name]

    register_calendar_alias("YAHOO", "NYSE", force=True)

    return run_algorithm(
        initialize=getattr(mod, "initialize", None),
        handle_data=getattr(mod, "handle_data", None),
        before_trading_start=getattr(mod, "before_trading_start", None),
        analyze=getattr(mod, "analyze", None),
        bundle="test",
        environ=environ,
        benchmark_returns=benchmark_returns,
        # Provide a default capital base, but allow the test to override.
        **merge({"capital_base": 1e7}, mod._test_args()),
    )
