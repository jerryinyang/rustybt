"""
Smoke test: Verify all critical imports work.

This test provides fast feedback in CI by checking that the package
and all critical dependencies can be imported successfully.
"""

import pytest


def test_rustybt_imports():
    """Test that rustybt core module imports successfully."""
    import rustybt

    assert rustybt is not None
    assert hasattr(rustybt, "__version__")


def test_rustybt_api_imports():
    """Test that rustybt API imports successfully."""
    import rustybt.api

    assert rustybt.api is not None
    # Check key API functions exist
    assert hasattr(rustybt.api, "order")
    assert hasattr(rustybt.api, "symbol")
    assert hasattr(rustybt.api, "record")


def test_new_dependencies_import():
    """Test that new RustyBT dependencies import successfully."""
    import hypothesis
    import polars
    import pyarrow
    import pydantic
    import structlog

    assert polars is not None
    assert hypothesis is not None
    assert structlog is not None
    assert pydantic is not None
    assert pyarrow is not None


def test_core_zipline_dependencies_import():
    """Test that core Zipline dependencies still import."""
    import numpy
    import pandas
    import sqlalchemy

    assert pandas is not None
    assert numpy is not None
    assert sqlalchemy is not None


def test_rustybt_algorithm_import():
    """Test that TradingAlgorithm imports."""
    from rustybt.algorithm import TradingAlgorithm

    assert TradingAlgorithm is not None


def test_rustybt_pipeline_import():
    """Test that Pipeline framework imports."""
    from rustybt.pipeline import Pipeline
    from rustybt.pipeline.data import USEquityPricing

    assert Pipeline is not None
    assert USEquityPricing is not None


def test_rustybt_assets_import():
    """Test that asset classes import."""
    from rustybt.assets import Asset, Equity, Future

    assert Equity is not None
    assert Future is not None
    assert Asset is not None


def test_rustybt_finance_import():
    """Test that finance modules import."""
    from rustybt.finance.execution import LimitOrder, MarketOrder, StopOrder
    from rustybt.finance.trading import SimulationParameters

    assert SimulationParameters is not None
    assert LimitOrder is not None
    assert MarketOrder is not None
    assert StopOrder is not None


@pytest.mark.parametrize(
    "module_name",
    [
        "rustybt.data",
        "rustybt.utils",
        "rustybt.testing",
        "rustybt.gens",
    ],
)
def test_rustybt_submodules_import(module_name):
    """Test that all major submodules import successfully."""
    import importlib

    module = importlib.import_module(module_name)
    assert module is not None


def test_python_version():
    """Verify Python version is 3.12+."""
    import sys

    assert sys.version_info >= (3, 12), f"Python 3.12+ required, got {sys.version_info}"


def test_rustybt_version_format():
    """Verify version string has expected format."""
    import rustybt

    version = rustybt.__version__
    assert isinstance(version, str)
    assert len(version) > 0
    # Should contain numbers (development versions like 0.1.dev0+dirty are OK)
    assert any(char.isdigit() for char in version)


def test_lazy_loaded_symbols_accessible():
    """Verify lazy-loaded symbols from __all__ are accessible at runtime."""
    import rustybt

    # These should be accessible via lazy loading (__getattr__)
    assert hasattr(rustybt, "TradingAlgorithm")
    assert hasattr(rustybt, "Blotter")
    assert hasattr(rustybt, "run_algorithm")

    # Actually access them to trigger lazy loading
    trading_algo = rustybt.TradingAlgorithm
    blotter = rustybt.Blotter
    run_algo = rustybt.run_algorithm

    # Verify they are the correct types (callable classes/functions)
    assert callable(trading_algo)
    assert callable(blotter)
    assert callable(run_algo)


def test_type_hints_available_for_static_analysis():
    """Verify TYPE_CHECKING imports enable type hints for IDEs/type checkers.

    This test verifies that:
    1. The symbols exist in the module's type annotations
    2. Static type checkers can find them
    3. IDEs can provide autocomplete

    Note: This test validates the presence of the symbols, not the actual
    static analysis (which happens in mypy/pyright/IDE tooling).
    """
    from typing import get_type_hints

    import rustybt

    # Verify symbols are in __all__ (public API)
    assert "TradingAlgorithm" in rustybt.__all__
    assert "Blotter" in rustybt.__all__
    assert "run_algorithm" in rustybt.__all__

    # Verify __getattr__ handles lazy loading correctly
    # (Should not raise AttributeError)
    assert rustybt.TradingAlgorithm is not None
    assert rustybt.Blotter is not None
    assert rustybt.run_algorithm is not None

    # Verify the actual classes have docstrings (for IDE hover)
    assert rustybt.TradingAlgorithm.__doc__ is not None
    assert len(rustybt.TradingAlgorithm.__doc__) > 0


def test_type_checking_block_exists():
    """Verify TYPE_CHECKING imports exist in __init__.py source.

    This ensures the TYPE_CHECKING pattern is correctly implemented,
    which enables static type checkers and IDEs to discover types
    without importing heavy modules at runtime.
    """
    from pathlib import Path

    import rustybt

    # Read __init__.py source
    init_file = Path(rustybt.__file__)
    source = init_file.read_text()

    # Verify TYPE_CHECKING import exists
    assert "from typing import TYPE_CHECKING" in source

    # Verify TYPE_CHECKING block exists
    assert "if TYPE_CHECKING:" in source

    # Verify the key imports are in the TYPE_CHECKING block
    # (This ensures type checkers can see them)
    lines = source.split("\n")
    in_type_checking = False
    found_trading_algorithm = False
    found_blotter = False
    found_run_algorithm = False

    for line in lines:
        if "if TYPE_CHECKING:" in line:
            in_type_checking = True
        elif in_type_checking:
            if line.startswith("if ") or (line and not line.startswith((" ", "\t"))):
                # Exited the TYPE_CHECKING block
                break
            if "TradingAlgorithm" in line:
                found_trading_algorithm = True
            if "Blotter" in line:
                found_blotter = True
            if "run_algorithm" in line:
                found_run_algorithm = True

    assert found_trading_algorithm, "TradingAlgorithm not in TYPE_CHECKING block"
    assert found_blotter, "Blotter not in TYPE_CHECKING block"
    assert found_run_algorithm, "run_algorithm not in TYPE_CHECKING block"
