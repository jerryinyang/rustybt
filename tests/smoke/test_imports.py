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
