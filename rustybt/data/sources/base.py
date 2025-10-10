"""Base DataSource abstraction for unified data ingestion.

This module defines the abstract DataSource interface that all data adapters
must implement, providing a consistent API for fetching data, ingesting to
bundles, tracking metadata, and supporting live streaming.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import polars as pl


@dataclass(frozen=True)
class DataSourceConfig:
    """Configuration for initializing a DataSource.

    Attributes:
        source_name: Name of the data source (e.g., 'yfinance', 'ccxt')
        api_key: API key for authenticated sources (optional)
        api_secret: API secret for authenticated sources (optional)
        exchange: Exchange identifier for CCXT-based sources (optional)
        base_url: Custom API base URL (optional)
        rate_limit_per_second: Maximum requests per second (default: 10)
        enable_caching: Whether to cache responses (default: False)
        additional_params: Additional provider-specific parameters

    Example:
        >>> config = DataSourceConfig(
        ...     source_name="ccxt",
        ...     exchange="binance",
        ...     rate_limit_per_second=5
        ... )
    """

    source_name: str
    api_key: str | None = None
    api_secret: str | None = None
    exchange: str | None = None
    base_url: str | None = None
    rate_limit_per_second: int = 10
    enable_caching: bool = False
    additional_params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DataSourceMetadata:
    """Metadata describing a DataSource for provenance tracking.

    Attributes:
        source_type: Type of source (e.g., 'yfinance', 'ccxt', 'csv')
        source_url: API endpoint URL or file path
        api_version: API version identifier (if applicable)
        supports_live: Whether source supports live streaming
        rate_limit: Requests per minute limit (if applicable)
        auth_required: Whether API key authentication is required
        data_delay: Data delay in minutes (0 for real-time, None for unknown)
        supported_frequencies: List of supported time resolutions
        additional_info: Additional provider-specific metadata

    Example:
        >>> metadata = DataSourceMetadata(
        ...     source_type="yfinance",
        ...     source_url="https://query2.finance.yahoo.com",
        ...     api_version="v8",
        ...     supports_live=False,
        ...     rate_limit=2000,
        ...     auth_required=False,
        ...     data_delay=15,
        ...     supported_frequencies=["1d", "1h", "5m"]
        ... )
    """

    source_type: str
    source_url: str
    api_version: str
    supports_live: bool
    rate_limit: int | None = None
    auth_required: bool = False
    data_delay: int | None = None
    supported_frequencies: list[str] = field(default_factory=list)
    additional_info: dict[str, Any] = field(default_factory=dict)


class DataSource(ABC):
    """Abstract base class for unified data source interface.

    All data adapters (YFinance, CCXT, Polygon, Alpaca, AlphaVantage, CSV)
    must implement this interface to provide consistent data access for
    backtesting and live trading.

    The DataSource interface provides four core methods:
    1. fetch() - Fetch OHLCV data as Polars DataFrame
    2. ingest_to_bundle() - Ingest data into Parquet bundle with metadata
    3. get_metadata() - Get source metadata for provenance tracking
    4. supports_live() - Whether source supports live streaming

    Example:
        >>> class YFinanceDataSource(DataSource):
        ...     async def fetch(self, symbols, start, end, frequency):
        ...         # Fetch from Yahoo Finance API
        ...         return df
        ...
        ...     def ingest_to_bundle(self, bundle_name, symbols, start, end, frequency):
        ...         # Write to Parquet bundle
        ...         pass
        ...
        ...     def get_metadata(self):
        ...         return DataSourceMetadata(...)
        ...
        ...     def supports_live(self):
        ...         return False
    """

    @abstractmethod
    async def fetch(
        self,
        symbols: list[str],
        start: pd.Timestamp,
        end: pd.Timestamp,
        frequency: str,
    ) -> pl.DataFrame:
        """Fetch OHLCV data and return Polars DataFrame.

        Args:
            symbols: List of symbols to fetch (e.g., ["AAPL", "MSFT"])
            start: Start timestamp for data range
            end: End timestamp for data range
            frequency: Time resolution (e.g., "1d", "1h", "1m")

        Returns:
            Polars DataFrame with standardized OHLCV schema:
            - timestamp: pl.Datetime("us")
            - symbol: pl.Utf8
            - open: pl.Decimal(precision=18, scale=8)
            - high: pl.Decimal(precision=18, scale=8)
            - low: pl.Decimal(precision=18, scale=8)
            - close: pl.Decimal(precision=18, scale=8)
            - volume: pl.Decimal(precision=18, scale=8)

        Raises:
            NetworkError: If API request fails
            RateLimitError: If rate limit exceeded
            InvalidDataError: If received data is invalid
            ValidationError: If data validation fails

        Example:
            >>> source = DataSourceRegistry.get_source("yfinance")
            >>> df = await source.fetch(
            ...     ["AAPL", "MSFT"],
            ...     pd.Timestamp("2023-01-01"),
            ...     pd.Timestamp("2023-12-31"),
            ...     "1d"
            ... )
            >>> print(df.head())
        """
        pass

    @abstractmethod
    def ingest_to_bundle(
        self,
        bundle_name: str,
        symbols: list[str],
        start: pd.Timestamp,
        end: pd.Timestamp,
        frequency: str,
        **kwargs: Any,
    ) -> None:
        """Ingest data into bundle (Parquet + metadata).

        Fetches data via fetch() method and writes to Parquet bundle with
        metadata tracking. Creates bundle directory structure and writes
        metadata.json for provenance tracking.

        Args:
            bundle_name: Name of bundle to create/update
            symbols: List of symbols to ingest
            start: Start timestamp for data range
            end: End timestamp for data range
            frequency: Time resolution (e.g., "1d", "1h", "1m")
            **kwargs: Additional provider-specific parameters

        Raises:
            NetworkError: If data fetch fails
            ValidationError: If data validation fails
            IOError: If bundle write fails

        Example:
            >>> source = DataSourceRegistry.get_source("yfinance")
            >>> source.ingest_to_bundle(
            ...     bundle_name="my-stocks",
            ...     symbols=["AAPL", "MSFT"],
            ...     start=pd.Timestamp("2023-01-01"),
            ...     end=pd.Timestamp("2023-12-31"),
            ...     frequency="1d"
            ... )
            >>> # Bundle created at: ~/.rustybt/data/bundles/my-stocks/
        """
        pass

    @abstractmethod
    def get_metadata(self) -> DataSourceMetadata:
        """Get source metadata for provenance tracking.

        Returns metadata describing the data source, including API version,
        rate limits, supported frequencies, and authentication requirements.

        Returns:
            DataSourceMetadata instance with source information

        Example:
            >>> source = DataSourceRegistry.get_source("yfinance")
            >>> metadata = source.get_metadata()
            >>> print(f"Source: {metadata.source_type}")
            >>> print(f"Live: {metadata.supports_live}")
            >>> print(f"Delay: {metadata.data_delay} minutes")
        """
        pass

    @abstractmethod
    def supports_live(self) -> bool:
        """Whether source supports live streaming.

        Returns:
            True if source supports real-time WebSocket streaming,
            False if source only provides historical data or has delays

        Example:
            >>> source = DataSourceRegistry.get_source("ccxt")
            >>> if source.supports_live():
            ...     print("Can use for live trading")
            >>> else:
            ...     print("Backtest only")
        """
        pass
