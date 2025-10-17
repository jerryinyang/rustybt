"""YFinance data adapter for fetching stock/ETF/forex OHLCV data."""

import asyncio
import time
from decimal import Decimal
from pathlib import Path
from typing import ClassVar

import pandas as pd
import polars as pl
import structlog
import yfinance as yf

from rustybt.data.adapters.base import (
    BaseDataAdapter,
    InvalidDataError,
    NetworkError,
    validate_ohlcv_relationships,
)
from rustybt.data.adapters.utils import (
    build_symbol_sid_map,
    normalize_symbols,
    prepare_ohlcv_frame,
)
from rustybt.data.polars.parquet_writer import ParquetWriter
from rustybt.data.sources.base import DataSource, DataSourceMetadata
from rustybt.utils.paths import data_path, ensure_directory

logger = structlog.get_logger()


class YFinanceAdapter(BaseDataAdapter, DataSource):
    """YFinance adapter for fetching stock/ETF/forex OHLCV data.

    Provides access to Yahoo Finance data for stocks, ETFs, forex pairs, indices,
    and commodities. Supports multiple time resolutions from 1-minute intraday to
    monthly data.

    Implements both BaseDataAdapter and DataSource interfaces for backwards
    compatibility and unified data source access.

    Attributes:
        request_delay: Delay between requests in seconds
        fetch_dividends: Whether to fetch dividend data
        fetch_splits: Whether to fetch split data
        last_request_time: Timestamp of last request for rate limiting

    Example:
        >>> adapter = YFinanceAdapter(request_delay=1.0)
        >>> df = await adapter.fetch(
        ...     symbols=["AAPL", "MSFT"],
        ...     start_date=pd.Timestamp("2024-01-01"),
        ...     end_date=pd.Timestamp("2024-01-31"),
        ...     resolution="1d"
        ... )
    """

    # Resolution mapping from RustyBT to yfinance format
    RESOLUTION_MAPPING: ClassVar[dict[str, str]] = {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "1h",
        "1d": "1d",
        "1wk": "1wk",
        "1mo": "1mo",
    }

    # Intraday resolutions limited to 60 days by Yahoo Finance
    INTRADAY_RESOLUTIONS: ClassVar[set[str]] = {"1m", "5m", "15m", "30m", "1h"}
    MAX_INTRADAY_DAYS: ClassVar[int] = 60

    def __init__(
        self,
        request_delay: float = 1.0,
        fetch_dividends: bool = True,
        fetch_splits: bool = True,
    ) -> None:
        """Initialize YFinance adapter.

        Args:
            request_delay: Delay between requests in seconds (default: 1s)
            fetch_dividends: Whether to fetch dividend data
            fetch_splits: Whether to fetch split data
        """
        super().__init__(
            name="YFinanceAdapter",
            rate_limit_per_second=1,  # Conservative: 1 request/second
        )

        self.request_delay = request_delay
        self.fetch_dividends_flag = fetch_dividends
        self.fetch_splits_flag = fetch_splits
        self.last_request_time = 0.0

    async def fetch(
        self,
        symbols: list[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        resolution: str,
    ) -> pl.DataFrame:
        """Fetch OHLCV data from Yahoo Finance.

        Args:
            symbols: List of ticker symbols (e.g., ["AAPL", "MSFT", "SPY"])
            start_date: Start date for data range
            end_date: End date for data range
            resolution: Time resolution (e.g., "1d", "1h", "1m")

        Returns:
            Polars DataFrame with standardized OHLCV schema

        Raises:
            ValueError: If intraday resolution requested for >60 days
            NetworkError: If API request fails
            InvalidDataError: If symbol is invalid or delisted
        """
        # Map resolution to yfinance interval
        if resolution not in self.RESOLUTION_MAPPING:
            raise ValueError(
                f"Unsupported resolution: {resolution}. "
                f"Supported: {list(self.RESOLUTION_MAPPING.keys())}"
            )

        yf_interval = self.RESOLUTION_MAPPING[resolution]

        # Validate date range for intraday data
        if resolution in self.INTRADAY_RESOLUTIONS:
            days_diff = (end_date - start_date).days
            if days_diff > self.MAX_INTRADAY_DAYS:
                raise ValueError(
                    f"Intraday resolution '{resolution}' limited to "
                    f"{self.MAX_INTRADAY_DAYS} days. Requested: {days_diff} days"
                )

        # Normalize symbols
        symbols = [self._normalize_symbol(s) for s in symbols]

        # Apply rate limiting
        await self._rate_limit()

        # Fetch data
        try:
            if len(symbols) == 1:
                ticker = yf.Ticker(symbols[0])
                df_pandas = ticker.history(start=start_date, end=end_date, interval=yf_interval)

                # Add symbol column
                if not df_pandas.empty:
                    df_pandas["symbol"] = symbols[0]

            else:
                # Multi-ticker download
                df_pandas = yf.download(
                    tickers=" ".join(symbols),
                    start=start_date,
                    end=end_date,
                    interval=yf_interval,
                    group_by="ticker",
                    auto_adjust=False,  # Get raw prices for manual adjustment
                )

                # Reshape multi-index DataFrame
                df_pandas = self._reshape_multi_ticker(df_pandas, symbols)

        except Exception as e:
            raise NetworkError(f"YFinance fetch failed: {e}") from e

        # Check if data is empty (invalid symbol or delisted)
        if df_pandas.empty:
            raise InvalidDataError(
                f"No data returned for symbols {symbols}. Symbols may be invalid or delisted."
            )

        # Convert to Polars and standardize
        df_polars = self._pandas_to_polars(df_pandas)
        df_polars = self.standardize(df_polars)

        # Lenient validation: Filter out rows with invalid OHLCV relationships before validation
        # This prevents validation errors from incomplete/invalid intraday data
        df_polars = self._filter_invalid_rows_lenient(df_polars)

        # Now validate the cleaned data
        self.validate(df_polars)

        # Log successful fetch
        self._log_fetch_success(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            resolution=resolution,
            row_count=len(df_polars),
        )

        return df_polars

    async def fetch_dividends(self, symbols: list[str]) -> dict[str, pl.DataFrame]:
        """Fetch dividend data for symbols.

        Args:
            symbols: List of ticker symbols

        Returns:
            Dictionary mapping symbol to dividend DataFrame with columns:
            - date: Dividend payment date
            - symbol: Ticker symbol
            - dividend: Dividend amount (Decimal)

        Example:
            >>> dividends = await adapter.fetch_dividends(["AAPL", "MSFT"])
            >>> if "AAPL" in dividends:
            ...     print(dividends["AAPL"])
        """
        dividends = {}

        for symbol in symbols:
            await self._rate_limit()

            try:
                ticker = yf.Ticker(symbol)
                div_series = ticker.dividends

                if not div_series.empty:
                    div_df = pl.DataFrame(
                        {
                            "date": div_series.index.to_list(),
                            "symbol": [symbol] * len(div_series),
                            "dividend": [Decimal(str(d)) for d in div_series.values],
                        }
                    )
                    dividends[symbol] = div_df

                    logger.info(
                        "dividends_fetched",
                        symbol=symbol,
                        count=len(div_df),
                    )

            except (NetworkError, ValueError, KeyError) as e:
                logger.warning(
                    "dividend_fetch_failed",
                    symbol=symbol,
                    error=str(e),
                )

        return dividends

    async def fetch_splits(self, symbols: list[str]) -> dict[str, pl.DataFrame]:
        """Fetch split data for symbols.

        Args:
            symbols: List of ticker symbols

        Returns:
            Dictionary mapping symbol to split DataFrame with columns:
            - date: Split date
            - symbol: Ticker symbol
            - split_ratio: Split ratio (Decimal), e.g., 2.0 for 2:1 split

        Example:
            >>> splits = await adapter.fetch_splits(["AAPL", "TSLA"])
            >>> if "AAPL" in splits:
            ...     print(splits["AAPL"])
        """
        splits = {}

        for symbol in symbols:
            await self._rate_limit()

            try:
                ticker = yf.Ticker(symbol)
                split_series = ticker.splits

                if not split_series.empty:
                    split_df = pl.DataFrame(
                        {
                            "date": split_series.index.to_list(),
                            "symbol": [symbol] * len(split_series),
                            "split_ratio": [Decimal(str(s)) for s in split_series.values],
                        }
                    )
                    splits[symbol] = split_df

                    logger.info(
                        "splits_fetched",
                        symbol=symbol,
                        count=len(split_df),
                    )

            except (NetworkError, ValueError, KeyError) as e:
                logger.warning(
                    "split_fetch_failed",
                    symbol=symbol,
                    error=str(e),
                )

        return splits

    def validate(self, df: pl.DataFrame) -> bool:
        """Validate YFinance data using base OHLCV validation.

        Args:
            df: DataFrame to validate

        Returns:
            True if validation passes

        Raises:
            ValidationError: If data validation fails
        """
        return validate_ohlcv_relationships(df)

    def _filter_invalid_rows_lenient(self, df: pl.DataFrame) -> pl.DataFrame:
        """Filter out rows with invalid OHLCV relationships (lenient mode).

        This method removes rows that violate OHLCV constraints rather than failing.
        Useful for handling incomplete/invalid intraday data from yfinance.

        OHLCV validity rules:
        - high >= low (always)
        - high >= open (always)
        - high >= close (always)
        - low <= open (always)
        - low <= close (always)
        - All prices > 0 (non-negative)

        Args:
            df: DataFrame with potentially invalid rows

        Returns:
            DataFrame with only valid rows

        Example:
            >>> df_cleaned = adapter._filter_invalid_rows_lenient(df_raw)
        """
        initial_count = len(df)

        # Build validity mask (all conditions must be True)
        validity_mask = (
            (pl.col("high") >= pl.col("low"))
            & (pl.col("high") >= pl.col("open"))
            & (pl.col("high") >= pl.col("close"))
            & (pl.col("low") <= pl.col("open"))
            & (pl.col("low") <= pl.col("close"))
            & (pl.col("open") > 0)
            & (pl.col("high") > 0)
            & (pl.col("low") > 0)
            & (pl.col("close") > 0)
        )

        # Filter to keep only valid rows
        df_valid = df.filter(validity_mask)
        dropped_count = initial_count - len(df_valid)

        if dropped_count > 0:
            # Get invalid rows for logging
            df_invalid = df.filter(~validity_mask)
            affected_symbols = df_invalid.select("symbol").unique().to_series().to_list()

            logger.warning(
                "yfinance_filtered_invalid_rows",
                dropped_count=dropped_count,
                remaining_count=len(df_valid),
                affected_symbols=affected_symbols,
                reason="invalid_ohlcv_relationships",
            )

        return df_valid

    def standardize(self, df: pl.DataFrame) -> pl.DataFrame:
        """Convert to standard schema.

        Data is already standardized in _pandas_to_polars() method,
        so this is a pass-through.

        Args:
            df: DataFrame to standardize

        Returns:
            Standardized DataFrame
        """
        return df

    async def _rate_limit(self) -> None:
        """Apply rate limiting with delay between requests."""
        current_time = time.time()
        elapsed = current_time - self.last_request_time

        if elapsed < self.request_delay:
            wait_time = self.request_delay - elapsed
            await asyncio.sleep(wait_time)

        self.last_request_time = time.time()

    def _normalize_symbol(self, symbol: str) -> str:
        """Normalize ticker symbol to uppercase.

        Args:
            symbol: Raw symbol string

        Returns:
            Normalized symbol (uppercase, trimmed)
        """
        return symbol.upper().strip()

    def _reshape_multi_ticker(self, df: pd.DataFrame, symbols: list[str]) -> pd.DataFrame:
        """Reshape multi-ticker DataFrame with multi-index columns.

        YFinance returns multi-ticker data with a multi-index column structure
        where the first level is the ticker and the second level is the OHLCV field.
        This method reshapes it to a long format with a symbol column.

        Args:
            df: Multi-ticker DataFrame from yfinance.download()
            symbols: List of symbols that were requested

        Returns:
            Reshaped DataFrame in long format with symbol column
        """
        reshaped_rows = []

        for symbol in symbols:
            if symbol in df.columns.levels[0]:
                symbol_df = df[symbol].copy()
                symbol_df["symbol"] = symbol
                reshaped_rows.append(symbol_df)

        if reshaped_rows:
            return pd.concat(reshaped_rows)
        else:
            return pd.DataFrame()

    def _pandas_to_polars(self, df: pd.DataFrame) -> pl.DataFrame:
        """Convert pandas DataFrame to Polars with Decimal conversion.

        Converts yfinance pandas format to RustyBT standard schema with:
        - Datetime index → timestamp column (microsecond precision)
        - Float OHLCV columns → Decimal(18, 8)
        - Symbol column added

        Args:
            df: Pandas DataFrame from yfinance

        Returns:
            Polars DataFrame with Decimal columns and standard schema
        """
        # Reset index to convert datetime to column
        df = df.reset_index()

        # Rename columns to match schema
        column_mapping = {
            "Date": "timestamp",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }

        df = df.rename(columns=column_mapping)

        # Select required columns
        required_cols = ["timestamp", "symbol", "open", "high", "low", "close", "volume"]
        df = df[required_cols]

        # Convert to Polars
        df_polars = pl.from_pandas(df)

        # Convert float columns to Decimal
        # CRITICAL: Use string conversion to avoid float precision loss
        df_polars = df_polars.with_columns(
            [
                pl.col("open").cast(pl.Utf8).str.to_decimal(scale=8).alias("open"),
                pl.col("high").cast(pl.Utf8).str.to_decimal(scale=8).alias("high"),
                pl.col("low").cast(pl.Utf8).str.to_decimal(scale=8).alias("low"),
                pl.col("close").cast(pl.Utf8).str.to_decimal(scale=8).alias("close"),
                pl.col("volume").cast(pl.Utf8).str.to_decimal(scale=8).alias("volume"),
            ]
        )

        # Ensure timestamp is datetime with microsecond precision
        df_polars = df_polars.with_columns(
            [pl.col("timestamp").cast(pl.Datetime("us")).alias("timestamp")]
        )

        # Sort by timestamp and symbol to ensure proper ordering
        # (important for multi-symbol fetches)
        df_polars = df_polars.sort(["timestamp", "symbol"])

        return df_polars

    def _log_fetch_success(
        self,
        symbols: list[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        resolution: str,
        row_count: int,
    ) -> None:
        """Log successful data fetch with structured logging.

        Args:
            symbols: List of fetched symbols
            start_date: Start date of fetch
            end_date: End date of fetch
            resolution: Time resolution
            row_count: Number of rows fetched
        """
        logger.info(
            "yfinance_fetch_complete",
            symbols=symbols,
            rows=row_count,
            resolution=resolution,
            start_date=str(start_date),
            end_date=str(end_date),
        )

    # ========================================================================
    # DataSource Interface Implementation
    # ========================================================================

    def ingest_to_bundle(
        self,
        bundle_name: str,
        symbols: list[str],
        start: pd.Timestamp,
        end: pd.Timestamp,
        frequency: str,
        **kwargs,
    ) -> None:
        """Ingest YFinance data into bundle (Parquet + metadata).

        Args:
            bundle_name: Name of bundle to create/update
            symbols: List of symbols to ingest
            start: Start timestamp for data range
            end: End timestamp for data range
            frequency: Time resolution (e.g., "1d", "1h", "1m")
            **kwargs: Additional parameters (ignored for YFinance)

        Raises:
            NetworkError: If data fetch fails
            ValidationError: If data validation fails
            IOError: If bundle write fails
        """
        logger.info(
            "yfinance_ingest_start",
            bundle=bundle_name,
            symbols=symbols[:5] if len(symbols) > 5 else symbols,
            symbol_count=len(symbols),
            start=start,
            end=end,
            frequency=frequency,
        )

        normalized_symbols = normalize_symbols(symbols)

        df = asyncio.run(self.fetch(normalized_symbols, start, end, frequency))
        if df.is_empty():
            logger.warning(
                "yfinance_no_data",
                bundle=bundle_name,
                symbols=normalized_symbols,
                frequency=frequency,
            )
            return

        symbol_map = build_symbol_sid_map(normalized_symbols)
        df_prepared, frame_type = prepare_ohlcv_frame(df, symbol_map, frequency)

        bundle_dir = Path(data_path(["bundles", bundle_name]))
        ensure_directory(str(bundle_dir))

        writer = ParquetWriter(str(bundle_dir))

        metadata = self.get_metadata()
        source_metadata = {
            "source_type": metadata.source_type,
            "source_url": metadata.source_url,
            "api_version": metadata.api_version,
            "symbols": list(symbol_map.keys()),
            "timezone": "UTC",
        }

        if frame_type == "daily":
            writer.write_daily_bars(
                df_prepared,
                bundle_name=bundle_name,
                source_metadata=source_metadata,
            )
        else:
            writer.write_minute_bars(df_prepared)

        logger.info(
            "yfinance_ingest_complete",
            bundle=bundle_name,
            rows=len(df_prepared),
            frame_type=frame_type,
            bundle_path=str(bundle_dir),
        )

    def get_metadata(self) -> DataSourceMetadata:
        """Get YFinance source metadata.

        Returns:
            DataSourceMetadata with YFinance API information
        """
        return DataSourceMetadata(
            source_type="yfinance",
            source_url="https://query2.finance.yahoo.com/v8/finance/chart",
            api_version="v8",
            supports_live=False,
            rate_limit=2000,  # ~2000 requests per hour (conservative estimate)
            auth_required=False,
            data_delay=15,  # 15-minute delay for free tier
            supported_frequencies=list(self.RESOLUTION_MAPPING.keys()),
            additional_info={
                "max_intraday_days": self.MAX_INTRADAY_DAYS,
                "fetch_dividends": self.fetch_dividends_flag,
                "fetch_splits": self.fetch_splits_flag,
            },
        )

    def supports_live(self) -> bool:
        """YFinance does not support live streaming.

        Returns:
            False (15-minute delayed data only)
        """
        return False

    # Backwards compatibility alias
    async def fetch_ohlcv(
        self,
        symbols: list[str],
        start: pd.Timestamp,
        end: pd.Timestamp,
        frequency: str,
    ) -> pl.DataFrame:
        """Legacy method name for backwards compatibility.

        Delegates to fetch() method.

        Args:
            symbols: List of symbols to fetch
            start: Start timestamp
            end: End timestamp
            frequency: Time resolution

        Returns:
            Polars DataFrame with OHLCV data
        """
        return await self.fetch(symbols, start, end, frequency)
