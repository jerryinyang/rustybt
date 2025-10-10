"""Unified DataSource abstraction for RustyBT.

This module provides a unified interface for all data sources in RustyBT,
enabling consistent handling of data ingestion from various providers
(YFinance, CCXT, Polygon, Alpaca, AlphaVantage, CSV) for both backtesting
and live trading.

Example:
    >>> from rustybt.data.sources import DataSourceRegistry
    >>> source = DataSourceRegistry.get_source("yfinance")
    >>> await source.fetch(["AAPL"], start, end, "1d")
    >>> source.ingest_to_bundle("my-bundle", ["AAPL"], start, end, "1d")
"""

from rustybt.data.sources.base import (
    DataSource,
    DataSourceConfig,
    DataSourceMetadata,
)
from rustybt.data.sources.registry import DataSourceRegistry

__all__ = [
    "DataSource",
    "DataSourceConfig",
    "DataSourceMetadata",
    "DataSourceRegistry",
]
