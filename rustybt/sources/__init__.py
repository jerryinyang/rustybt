"""Data sources for backtesting simulations.

This module provides data source implementations for generating and feeding
market data into backtesting algorithms. Sources can provide real historical
data, simulated data for testing, or benchmark data for performance comparison.

The primary export is SpecificEquityTrades, which generates test data for
specific equity securities over a given time range.

Examples:
    Generate test trade data for backtesting::

        from rustybt.sources import SpecificEquityTrades
        from datetime import datetime, timedelta

        source = SpecificEquityTrades(
            trading_calendar=calendar,
            asset_finder=finder,
            sids=[1, 2, 3],
            start=datetime(2020, 1, 1),
            end=datetime(2020, 12, 31),
            delta=timedelta(minutes=1)
        )
"""
from .test_source import SpecificEquityTrades

__all__ = [
    "SpecificEquityTrades",
]
