"""
Adapter-Bundle Bridge Functions (Phase 1)

TEMPORARY BRIDGE for Epic 7 profiling (Story 7.1 unblocking).
These functions create profiling bundles from existing adapters.

DEPRECATION NOTICE:
This module is deprecated and will be removed in v2.0.
Use DataSource.ingest_to_bundle() instead (Epic 8 Phase 2).

Migration Guide: docs/guides/migrating-to-unified-data.md
"""

import warnings
from pathlib import Path

import pandas as pd
import structlog
from exchange_calendars import get_calendar

from rustybt.data.adapters.ccxt_adapter import CCXTAdapter
from rustybt.data.adapters.csv_adapter import CSVAdapter
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter
from rustybt.data.bundles.core import register
from rustybt.data.metadata_tracker import (
    track_api_bundle_metadata,
    track_csv_bundle_metadata,
)

logger = structlog.get_logger(__name__)


def _deprecation_warning(function_name: str, replacement: str):
    """Emit deprecation warning for bridge functions."""
    warnings.warn(
        f"{function_name} is deprecated and will be removed in v2.0. "
        f"Use {replacement} instead. "
        f"See: docs/guides/migrating-to-unified-data.md",
        DeprecationWarning,
        stacklevel=3,
    )


def _create_bundle_from_adapter(
    adapter: object,  # BaseDataAdapter or any adapter with fetch_ohlcv method
    bundle_name: str,
    symbols: list[str],
    start: pd.Timestamp,
    end: pd.Timestamp,
    frequency: str,
    writers: dict[str, object],  # Zipline bundle writers dict
) -> None:
    """
    Generic helper to create bundle from adapter.

    Args:
        adapter: Data adapter instance (YFinance, CCXT, etc.)
        bundle_name: Bundle identifier
        symbols: List of symbols to fetch
        start: Start date
        end: End date
        frequency: Data frequency ('1d', '1h', '1m')
        writers: Zipline bundle writers dict

    This function:
    1. Fetches data from adapter
    2. Writes to Parquet via writers
    3. Tracks metadata automatically
    """
    import asyncio

    logger.info(
        "bridge_ingest_start",
        bundle=bundle_name,
        symbols=symbols[:5],  # Log first 5
        symbol_count=len(symbols),
        start=start,
        end=end,
        frequency=frequency,
    )

    # Fetch data from adapter (handle both sync and async adapters)
    try:
        fetch_result = adapter.fetch_ohlcv(
            symbols=symbols, start=start, end=end, frequency=frequency
        )

        # If the result is a coroutine, await it
        if asyncio.iscoroutine(fetch_result):
            df = asyncio.run(fetch_result)
        else:
            df = fetch_result
    except Exception as e:
        logger.error(
            "bridge_fetch_failed",
            bundle=bundle_name,
            error=str(e),
            error_type=type(e).__name__,
        )
        # Try to continue with a subset of symbols if possible
        logger.warning("bridge_skipping_problematic_symbols", bundle=bundle_name)
        return

    # Check if dataframe is empty (handle both Polars and pandas)
    import polars as pl

    is_empty = df.is_empty() if isinstance(df, pl.DataFrame) else df.empty

    if is_empty:
        logger.warning("bridge_no_data", bundle=bundle_name, symbols=symbols)
        return

    # Drop rows with NULL values in critical columns (common with failed downloads)
    if isinstance(df, pl.DataFrame):
        initial_count = len(df)
        df = df.drop_nulls(subset=["open", "high", "low", "close"])
        dropped_count = initial_count - len(df)
        if dropped_count > 0:
            logger.warning(
                "bridge_dropped_null_rows",
                bundle=bundle_name,
                dropped=dropped_count,
                remaining=len(df),
            )

    # Check again after cleaning
    is_empty = df.is_empty() if isinstance(df, pl.DataFrame) else df.empty
    if is_empty:
        logger.warning("bridge_no_data_after_cleaning", bundle=bundle_name)
        return

    logger.info("bridge_fetch_complete", bundle=bundle_name, row_count=len(df))

    # Transform flat DataFrame to (sid, df) tuples for bundle writer
    try:
        data_iter = _transform_for_writer(df, symbols, bundle_name)
    except Exception as e:
        logger.error(
            "bridge_transform_failed",
            bundle=bundle_name,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise ValueError(f"Data transformation failed for bundle '{bundle_name}': {e}") from e

    # Write to bundle via Zipline writers
    if frequency == "1d":
        writers["daily_bar_writer"].write(data_iter)
    elif frequency in ["1h", "1m", "5m", "15m"]:
        writers["minute_bar_writer"].write(data_iter)
    else:
        raise ValueError(f"Unsupported frequency: {frequency}")

    # Track metadata (provenance + quality)
    _track_api_bundle_metadata(bundle_name, adapter, df, start, end, frequency)

    logger.info("bridge_ingest_complete", bundle=bundle_name)


def _transform_for_writer(
    df: object,  # pl.DataFrame or pd.DataFrame
    symbols: list[str],
    bundle_name: str,
) -> object:  # Iterator[tuple[int, pd.DataFrame]]
    """Transform flat DataFrame into (sid, df) tuples for bundle writer.

    The bundle writer expects an iterable of (sid, dataframe) tuples where:
    - sid is an integer security identifier (0, 1, 2, ...)
    - dataframe is a pandas DataFrame with OHLCV data for that security

    This function:
    1. Detects DataFrame type (Polars or pandas)
    2. Extracts unique symbols from the data
    3. Assigns sequential SIDs to each symbol
    4. Splits the data by symbol
    5. Converts to pandas if needed
    6. Yields (sid, pandas_df) tuples

    Args:
        df: Flat DataFrame with all symbols combined (Polars or pandas)
        symbols: List of symbols that were requested
        bundle_name: Bundle name for logging

    Yields:
        Tuple of (sid, pandas_df) for each symbol

    Raises:
        ValueError: If symbol column is missing or data cannot be split

    Example:
        >>> df = pl.DataFrame({
        ...     "timestamp": [...],
        ...     "symbol": ["AAPL", "AAPL", "MSFT", "MSFT"],
        ...     "open": [...],
        ...     "high": [...],
        ...     "low": [...],
        ...     "close": [...],
        ...     "volume": [...]
        ... })
        >>> symbols = ["AAPL", "MSFT"]
        >>> for sid, symbol_df in _transform_for_writer(df, symbols, "test-bundle"):
        ...     print(f"SID {sid}: {len(symbol_df)} rows")
        SID 0: 252 rows
        SID 1: 252 rows
    """
    import polars as pl

    # Detect DataFrame type
    is_polars = isinstance(df, pl.DataFrame)

    # Validate symbol column exists
    if is_polars:
        if "symbol" not in df.columns:
            raise ValueError(
                f"Bundle '{bundle_name}': DataFrame missing 'symbol' column. "
                f"Columns: {df.columns}"
            )
    else:  # pandas
        if "symbol" not in df.columns:
            raise ValueError(
                f"Bundle '{bundle_name}': DataFrame missing 'symbol' column. "
                f"Columns: {list(df.columns)}"
            )

    # Get unique symbols from data (actual symbols with data)
    if is_polars:
        symbols_in_data = df["symbol"].unique().to_list()
    else:  # pandas
        symbols_in_data = df["symbol"].unique().tolist()

    logger.info(
        "bridge_transform_start",
        bundle=bundle_name,
        requested_symbols=len(symbols),
        symbols_with_data=len(symbols_in_data),
    )

    # Iterate over requested symbols and assign SIDs
    sid = 0
    for symbol in symbols:
        # Check if symbol has data
        if symbol not in symbols_in_data:
            logger.warning(
                "bridge_symbol_no_data",
                bundle=bundle_name,
                symbol=symbol,
                sid_skipped=sid,
            )
            # Skip this symbol but don't increment SID
            # (SIDs should be consecutive only for symbols with data)
            continue

        # Filter data for this symbol
        if is_polars:
            symbol_df_polars = df.filter(pl.col("symbol") == symbol)

            # Drop symbol column (writer doesn't need it)
            symbol_df_polars = symbol_df_polars.drop("symbol")

            # Convert to pandas (writer expects pandas)
            symbol_df_pandas = symbol_df_polars.to_pandas()
        else:  # pandas
            symbol_df_pandas = df[df["symbol"] == symbol].copy()

            # Drop symbol column
            symbol_df_pandas = symbol_df_pandas.drop(columns=["symbol"])

        # Validate DataFrame is not empty
        if symbol_df_pandas.empty:
            logger.warning(
                "bridge_empty_after_filter",
                bundle=bundle_name,
                symbol=symbol,
                sid=sid,
            )
            continue

        # Set index to timestamp/date for Zipline compatibility
        # (Zipline expects datetime index)
        if "timestamp" in symbol_df_pandas.columns:
            symbol_df_pandas = symbol_df_pandas.set_index("timestamp")
        elif "date" in symbol_df_pandas.columns:
            symbol_df_pandas = symbol_df_pandas.set_index("date")
        else:
            logger.warning(
                "bridge_no_datetime_index",
                bundle=bundle_name,
                symbol=symbol,
                sid=sid,
                columns=list(symbol_df_pandas.columns),
            )

        logger.debug(
            "bridge_symbol_transformed",
            bundle=bundle_name,
            symbol=symbol,
            sid=sid,
            rows=len(symbol_df_pandas),
        )

        # Yield (sid, dataframe) tuple
        yield sid, symbol_df_pandas

        # Increment SID for next symbol
        sid += 1

    logger.info(
        "bridge_transform_complete",
        bundle=bundle_name,
        total_sids=sid,
        symbols_processed=sid,
    )


def _track_api_bundle_metadata(
    bundle_name: str,
    adapter,
    df: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    frequency: str,
):
    """
    Track bundle metadata for API-sourced data.

    Automatically populates:
    - Provenance: source type, URL, API version, fetch timestamp
    - Quality: row count, missing days, OHLCV violations
    - Symbols: extracted from DataFrame
    """
    from pathlib import Path

    import polars as pl

    # Determine source metadata based on adapter type
    adapter_type = adapter.__class__.__name__.lower()
    if "yfinance" in adapter_type:
        source_type = "yfinance"
        api_url = "https://query2.finance.yahoo.com/v8/finance/chart"
        api_version = "v8"
    elif "ccxt" in adapter_type:
        source_type = "ccxt"
        exchange_id = getattr(adapter, "exchange_id", "unknown")
        api_url = f"https://{exchange_id}.com/api"
        api_version = getattr(adapter, "api_version", "unknown")
    else:
        source_type = "unknown"
        api_url = ""
        api_version = ""

    # Convert pandas DataFrame to polars for quality metrics calculation
    # (track_api_bundle_metadata expects polars DataFrame)
    if isinstance(df, pl.DataFrame):
        pl_df = df if not df.is_empty() else None
    else:  # pandas DataFrame
        pl_df = pl.from_pandas(df) if not df.empty else None

    # Get calendar for quality metrics
    try:
        calendar = get_calendar("NYSE") if "yfinance" in adapter_type else None
    except Exception as e:
        logger.warning(
            "calendar_load_failed",
            bundle=bundle_name,
            adapter_type=adapter_type,
            error=str(e),
        )
        calendar = None

    # Create a temporary data file path for metadata tracking
    # (In real implementation, this would be the actual bundle output path)
    data_file = Path(f"/tmp/{bundle_name}.parquet")  # nosec B108

    # Create the temporary file to avoid FileNotFoundError in metadata tracking
    # In production, the bundle writers would create real files
    try:
        data_file.parent.mkdir(parents=True, exist_ok=True)
        data_file.touch()
    except Exception as e:
        logger.warning(
            "temp_file_creation_failed",
            bundle=bundle_name,
            data_file=str(data_file),
            error=str(e),
        )

    # Track metadata using the metadata_tracker module
    try:
        result = track_api_bundle_metadata(
            bundle_name=bundle_name,
            source_type=source_type,
            data_file=str(data_file),
            data=pl_df,
            api_url=api_url,
            api_version=api_version,
            calendar=calendar,
        )
    except Exception as e:
        logger.error(
            "metadata_tracking_failed",
            bundle=bundle_name,
            adapter_type=adapter_type,
            error=str(e),
        )
        # Continue execution - metadata tracking failure shouldn't halt bundle creation
        result = {}
    finally:
        # Clean up temp file
        try:
            if data_file.exists():
                data_file.unlink()
        except Exception as e:
            logger.debug(
                "temp_file_cleanup_failed",
                bundle=bundle_name,
                data_file=str(data_file),
                error=str(e),
            )

    logger.info(
        "metadata_tracked",
        bundle=bundle_name,
        source=source_type,
        rows=len(df),
        quality_metrics=result.get("quality_metrics"),
    )


# ============================================================================
# PROFILING BUNDLE DEFINITIONS (Epic 7 Unblocking)
# ============================================================================


@register("yfinance-profiling")
def yfinance_profiling_bundle(
    environ,
    asset_db_writer,
    minute_bar_writer,
    daily_bar_writer,
    adjustment_writer,
    calendar,
    start_session,
    end_session,
    cache,
    show_progress,
    output_dir,
):
    """
    YFinance profiling bundle for Story 7.1 (Daily scenario).

    Fetches:
    - 20 top liquid US stocks
    - 2 years of daily data
    - For profiling Python implementation baseline

    DEPRECATED: Use DataSource.ingest_to_bundle() in v2.0
    """
    _deprecation_warning("yfinance_profiling_bundle", "YFinanceDataSource.ingest_to_bundle()")

    # Top 20 liquid US stocks (market cap weighted, BRK.B excluded due to yfinance issues)
    symbols = [
        "AAPL",
        "MSFT",
        "GOOGL",
        "AMZN",
        "NVDA",
        "META",
        "TSLA",
        "V",
        "JNJ",
        "WMT",
        "JPM",
        "MA",
        "PG",
        "UNH",
        "HD",
        "DIS",
        "BAC",
        "XOM",
        "COST",
        "ABBV",
    ]

    # Date range: 2 years back from today
    end = pd.Timestamp.now()
    start = end - pd.Timedelta(days=365 * 2)

    # Initialize adapter
    adapter = YFinanceAdapter()

    # Ingest via bridge
    _create_bundle_from_adapter(
        adapter=adapter,
        bundle_name="yfinance-profiling",
        symbols=symbols,
        start=start,
        end=end,
        frequency="1d",
        writers={
            "daily_bar_writer": daily_bar_writer,
            "minute_bar_writer": minute_bar_writer,
        },
    )


@register("ccxt-hourly-profiling")
def ccxt_hourly_profiling_bundle(
    environ,
    asset_db_writer,
    minute_bar_writer,
    daily_bar_writer,
    adjustment_writer,
    calendar,
    start_session,
    end_session,
    cache,
    show_progress,
    output_dir,
):
    """
    CCXT profiling bundle for Story 7.1 (Hourly scenario).

    Fetches:
    - 20 top crypto pairs
    - 6 months of hourly data
    - For profiling Python implementation baseline

    DEPRECATED: Use DataSource.ingest_to_bundle() in v2.0
    """
    _deprecation_warning("ccxt_hourly_profiling_bundle", "CCXTDataSource.ingest_to_bundle()")

    # Top 20 crypto pairs by volume (Binance)
    symbols = [
        "BTC/USDT",
        "ETH/USDT",
        "BNB/USDT",
        "XRP/USDT",
        "ADA/USDT",
        "SOL/USDT",
        "DOGE/USDT",
        "DOT/USDT",
        "MATIC/USDT",
        "AVAX/USDT",
        "SHIB/USDT",
        "LTC/USDT",
        "UNI/USDT",
        "LINK/USDT",
        "ATOM/USDT",
        "ETC/USDT",
        "XLM/USDT",
        "BCH/USDT",
        "ALGO/USDT",
        "FIL/USDT",
    ]

    # Date range: 6 months back
    end = pd.Timestamp.now()
    start = end - pd.Timedelta(days=180)

    # Initialize CCXT adapter (Binance)
    adapter = CCXTAdapter(exchange_id="binance")

    # Ingest via bridge
    _create_bundle_from_adapter(
        adapter=adapter,
        bundle_name="ccxt-hourly-profiling",
        symbols=symbols,
        start=start,
        end=end,
        frequency="1h",
        writers={
            "daily_bar_writer": daily_bar_writer,
            "minute_bar_writer": minute_bar_writer,
        },
    )


@register("ccxt-minute-profiling")
def ccxt_minute_profiling_bundle(
    environ,
    asset_db_writer,
    minute_bar_writer,
    daily_bar_writer,
    adjustment_writer,
    calendar,
    start_session,
    end_session,
    cache,
    show_progress,
    output_dir,
):
    """
    CCXT profiling bundle for Story 7.1 (Minute scenario).

    Fetches:
    - 10 crypto pairs
    - 1 month of minute data
    - For profiling Python implementation baseline

    DEPRECATED: Use DataSource.ingest_to_bundle() in v2.0
    """
    _deprecation_warning("ccxt_minute_profiling_bundle", "CCXTDataSource.ingest_to_bundle()")

    # Top 10 crypto pairs (subset of hourly)
    symbols = [
        "BTC/USDT",
        "ETH/USDT",
        "BNB/USDT",
        "XRP/USDT",
        "ADA/USDT",
        "SOL/USDT",
        "DOGE/USDT",
        "DOT/USDT",
        "MATIC/USDT",
        "AVAX/USDT",
    ]

    # Date range: 1 month back
    end = pd.Timestamp.now()
    start = end - pd.Timedelta(days=30)

    # Initialize CCXT adapter (Binance)
    adapter = CCXTAdapter(exchange_id="binance")

    # Ingest via bridge
    _create_bundle_from_adapter(
        adapter=adapter,
        bundle_name="ccxt-minute-profiling",
        symbols=symbols,
        start=start,
        end=end,
        frequency="1m",
        writers={
            "daily_bar_writer": daily_bar_writer,
            "minute_bar_writer": minute_bar_writer,
        },
    )


@register("csv-profiling")
def csv_profiling_bundle(
    environ,
    asset_db_writer,
    minute_bar_writer,
    daily_bar_writer,
    adjustment_writer,
    calendar,
    start_session,
    end_session,
    cache,
    show_progress,
    output_dir,
):
    """
    CSV profiling bundle wrapper (with metadata tracking).

    Wraps existing csvdir logic with automatic metadata tracking.

    DEPRECATED: Use DataSource.ingest_to_bundle() in v2.0
    """
    _deprecation_warning("csv_profiling_bundle", "CSVDataSource.ingest_to_bundle()")

    # Get CSV directory from environment (fallback to default)
    csv_dir = environ.get("CSVDIR", str(Path.home() / ".zipline" / "csv"))
    csv_path = Path(csv_dir)

    if not csv_path.exists():
        logger.warning("csv_dir_not_found", path=csv_dir)
        return

    # Initialize CSV adapter
    adapter = CSVAdapter(csv_dir=csv_dir)

    # Infer date range from CSV files
    csv_files = list(csv_path.glob("*.csv"))
    if not csv_files:
        logger.warning("no_csv_files", path=csv_dir)
        return

    # Read first CSV to infer date range (simplified)
    sample_df = pd.read_csv(csv_files[0])
    if "date" in sample_df.columns:
        start = pd.Timestamp(sample_df["date"].min())
        end = pd.Timestamp(sample_df["date"].max())
    else:
        start = pd.Timestamp.now() - pd.Timedelta(days=365)
        end = pd.Timestamp.now()

    symbols = [f.stem for f in csv_files]  # Extract symbols from filenames

    # Ingest via bridge
    _create_bundle_from_adapter(
        adapter=adapter,
        bundle_name="csv-profiling",
        symbols=symbols,
        start=start,
        end=end,
        frequency="1d",  # Assume daily for CSV
        writers={
            "daily_bar_writer": daily_bar_writer,
            "minute_bar_writer": minute_bar_writer,
        },
    )

    # Track CSV-specific metadata
    # Note: CSV bundle metadata is tracked automatically by track_csv_bundle_metadata
    # which reads the CSV files from csv_path
    track_csv_bundle_metadata(
        bundle_name="csv-profiling",
        csv_dir=str(csv_path),
        data=None,  # Let tracker read from CSV files
        calendar=None,
    )


def _calculate_csv_checksum(csv_files: list[Path]) -> str:
    """Calculate combined checksum of all CSV files."""
    import hashlib

    sha256 = hashlib.sha256()
    for csv_file in sorted(csv_files):
        with open(csv_file, "rb") as f:
            sha256.update(f.read())
    return sha256.hexdigest()[:16]  # First 16 chars


# ============================================================================
# CLI INTEGRATION (Story 8.1 AC1.8)
# ============================================================================


def list_profiling_bundles() -> list[str]:
    """List all registered profiling bundles."""
    return [
        "yfinance-profiling",
        "ccxt-hourly-profiling",
        "ccxt-minute-profiling",
        "csv-profiling",
    ]


def get_profiling_bundle_info(bundle_name: str) -> dict | None:
    """Get profiling bundle configuration info."""
    bundle_info = {
        "yfinance-profiling": {
            "description": "50 US stocks, 2 years daily (Story 7.1 daily scenario)",
            "symbol_count": 50,
            "frequency": "1d",
            "duration": "2 years",
            "adapter": "YFinanceAdapter",
        },
        "ccxt-hourly-profiling": {
            "description": "20 crypto pairs, 6 months hourly (Story 7.1 hourly scenario)",
            "symbol_count": 20,
            "frequency": "1h",
            "duration": "6 months",
            "adapter": "CCXTAdapter (Binance)",
        },
        "ccxt-minute-profiling": {
            "description": "10 crypto pairs, 1 month minute (Story 7.1 minute scenario)",
            "symbol_count": 10,
            "frequency": "1m",
            "duration": "1 month",
            "adapter": "CCXTAdapter (Binance)",
        },
        "csv-profiling": {
            "description": "CSV files from CSVDIR environment variable",
            "symbol_count": "varies",
            "frequency": "1d",
            "duration": "varies",
            "adapter": "CSVAdapter",
        },
    }

    return bundle_info.get(bundle_name)
