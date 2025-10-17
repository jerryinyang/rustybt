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


def _filter_invalid_ohlcv_rows(df: object) -> tuple[object, object]:
    """
    Filter out rows with invalid OHLCV relationships.

    OHLCV validity rules:
    - high >= low (always)
    - high >= open (always)
    - high >= close (always)
    - low <= open (always)
    - low <= close (always)
    - All prices > 0 (non-negative)

    Args:
        df: DataFrame (Polars or pandas) with OHLCV data

    Returns:
        Tuple of (valid_df, invalid_df) where:
        - valid_df: Rows that pass all OHLCV validation checks
        - invalid_df: Rows that fail any OHLCV validation check

    Example:
        >>> valid, invalid = _filter_invalid_ohlcv_rows(df)
        >>> logger.warning(f"Dropped {len(invalid)} invalid rows")
    """
    import polars as pl

    # Convert to Polars if pandas
    is_pandas = not isinstance(df, pl.DataFrame)
    if is_pandas:
        df = pl.from_pandas(df)

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

    # Split into valid and invalid
    valid_df = df.filter(validity_mask)
    invalid_df = df.filter(~validity_mask)

    # Convert back to pandas if input was pandas
    if is_pandas:
        valid_df = valid_df.to_pandas()
        invalid_df = invalid_df.to_pandas()

    return valid_df, invalid_df


def _adjust_end_date_for_market_hours(end: pd.Timestamp, bundle_name: str) -> pd.Timestamp:
    """
    Adjust end date to avoid fetching incomplete current-day data during market hours.

    If the end date is today and we're during market hours, adjust to yesterday
    to avoid incomplete/invalid intraday data.

    Args:
        end: Requested end date
        bundle_name: Bundle name for logging

    Returns:
        Adjusted end date (yesterday if today and market open, otherwise unchanged)

    Example:
        >>> end = pd.Timestamp('2025-10-17')  # Today
        >>> adjusted = _adjust_end_date_for_market_hours(end, 'yfinance-profiling')
        >>> # If market is open: adjusted = '2025-10-16'
        >>> # If market is closed: adjusted = '2025-10-17'
    """
    import pandas as pd

    # Get current time
    now = pd.Timestamp.now(tz="UTC")
    today = now.normalize()

    # Normalize end date for comparison (remove time component)
    end_normalized = end.normalize()

    # Make both timezone-aware or both timezone-naive for comparison
    if end_normalized.tz is None and today.tz is not None:
        # end is naive, today is aware - localize end to UTC
        end_normalized = end_normalized.tz_localize("UTC")
    elif end_normalized.tz is not None and today.tz is None:
        # end is aware, today is naive - localize today to UTC
        today = today.tz_localize("UTC")

    # If end date is today (or in the future)
    if end_normalized >= today:
        # Check if we're during typical market hours (9:30 AM - 4:00 PM ET)
        # Convert to US/Eastern timezone
        now_et = now.tz_convert("US/Eastern")
        hour = now_et.hour
        minute = now_et.minute

        # Market hours: 9:30 AM - 4:00 PM ET
        market_open = (hour > 9) or (hour == 9 and minute >= 30)
        market_close = hour >= 16

        if market_open and not market_close:
            # During market hours - use yesterday
            adjusted_end = today - pd.Timedelta(days=1)
            logger.info(
                "adjusted_end_date_for_market_hours",
                bundle=bundle_name,
                original_end=str(end),
                adjusted_end=str(adjusted_end),
                reason="market_currently_open",
                current_time_et=now_et.strftime("%Y-%m-%d %H:%M:%S %Z"),
            )
            return adjusted_end

    return end


def _create_asset_metadata(
    df: object,  # pl.DataFrame or pd.DataFrame
    symbols: list[str],
    start: pd.Timestamp,
    end: pd.Timestamp,
    bundle_name: str,
) -> pd.DataFrame:
    """
    Create asset metadata DataFrame from OHLCV data.

    Args:
        df: DataFrame with OHLCV data (must have 'symbol' and 'timestamp'/'date' columns)
        symbols: List of symbols
        start: Requested start date
        end: Requested end date
        bundle_name: Bundle name for exchange field

    Returns:
        pandas DataFrame with asset metadata containing:
        - symbol: Symbol name
        - start_date: First date of data for this symbol
        - end_date: Last date of data for this symbol
        - exchange: Exchange name (derived from bundle_name)
        - auto_close_date: Date when asset stops trading (end_date + 1 day)

    Raises:
        ValueError: If required columns are missing or data is invalid
    """
    import numpy as np
    import polars as pl

    # Convert to pandas if needed
    if isinstance(df, pl.DataFrame):
        # Find the timestamp column (could be 'timestamp', 'date', 'Date', or 'Timestamp')
        timestamp_col = None
        for col in ["timestamp", "date", "Date", "Timestamp"]:
            if col in df.columns:
                timestamp_col = col
                break

        if timestamp_col is None:
            raise ValueError(f"No timestamp column found in DataFrame. Columns: {df.columns}")

        # Group by symbol and get min/max timestamps
        metadata_df = (
            df.group_by("symbol")
            .agg(
                [
                    pl.col(timestamp_col).min().alias("start_date"),
                    pl.col(timestamp_col).max().alias("end_date"),
                ]
            )
            .to_pandas()
        )
    else:
        # pandas DataFrame
        timestamp_col = None
        for col in ["timestamp", "date", "Date", "Timestamp"]:
            if col in df.columns:
                timestamp_col = col
                break

        if timestamp_col is None:
            # Try using the index if it's a DatetimeIndex
            if isinstance(df.index, pd.DatetimeIndex):
                metadata_df = df.groupby("symbol").agg({"index": [np.min, np.max]}).reset_index()
                metadata_df.columns = ["symbol", "start_date", "end_date"]
            else:
                raise ValueError(f"No timestamp column found in DataFrame. Columns: {df.columns}")
        else:
            metadata_df = df.groupby("symbol")[timestamp_col].agg(["min", "max"]).reset_index()
            metadata_df.columns = ["symbol", "start_date", "end_date"]

    # Ensure datetime types
    metadata_df["start_date"] = pd.to_datetime(metadata_df["start_date"])
    metadata_df["end_date"] = pd.to_datetime(metadata_df["end_date"])

    # Set exchange name (derived from bundle name)
    exchange_name = bundle_name.upper().replace("-", "_")
    metadata_df["exchange"] = exchange_name

    # Set auto_close_date (end_date + 1 day)
    metadata_df["auto_close_date"] = metadata_df["end_date"] + pd.Timedelta(days=1)

    logger.info(
        "asset_metadata_created",
        bundle=bundle_name,
        symbol_count=len(metadata_df),
        date_range=f"{metadata_df['start_date'].min()} to {metadata_df['end_date'].max()}",
    )

    return metadata_df


def _transform_splits_for_writer(
    splits_data: dict[str, object],  # dict[symbol -> pl.DataFrame]
    asset_metadata: pd.DataFrame,
) -> pd.DataFrame | None:
    """Transform adapter splits data to SQLiteAdjustmentWriter format.

    Args:
        splits_data: Dictionary mapping symbol to DataFrame with columns:
                     - date: Split effective date
                     - symbol: Ticker symbol
                     - split_ratio: Split ratio (e.g., 2.0 for 2:1 split)
        asset_metadata: Asset metadata DataFrame with symbol-to-index mapping

    Returns:
        pandas DataFrame with columns {sid, effective_date, ratio} or None if no splits

    Format expected by SQLiteAdjustmentWriter:
        - sid: int (asset ID, 0-based index from asset_metadata)
        - effective_date: datetime64 (split effective date)
        - ratio: float (split ratio for price adjustment)

    Example:
        >>> splits_data = {"AAPL": pl.DataFrame({"date": [...], "symbol": ["AAPL"], "split_ratio": [2.0]})}
        >>> asset_metadata = pd.DataFrame({"symbol": ["AAPL", "MSFT"], ...})
        >>> splits_df = _transform_splits_for_writer(splits_data, asset_metadata)
        >>> print(splits_df)
           sid effective_date  ratio
        0    0     2020-08-31    2.0
    """
    import polars as pl

    if not splits_data:
        logger.debug("adjustment_transform_no_splits")
        return None

    # Create symbol to SID mapping from asset_metadata
    symbol_to_sid = {symbol: sid for sid, symbol in enumerate(asset_metadata["symbol"])}

    all_splits = []
    for symbol, split_df in splits_data.items():
        if symbol not in symbol_to_sid:
            logger.warning(
                "adjustment_transform_unknown_symbol",
                symbol=symbol,
                data_type="splits",
                note="Symbol not in asset metadata, skipping",
            )
            continue

        sid = symbol_to_sid[symbol]

        # Convert Polars to pandas if needed
        if isinstance(split_df, pl.DataFrame):
            split_df_pd = split_df.to_pandas()
        else:
            split_df_pd = split_df

        # Transform to writer format
        for _, row in split_df_pd.iterrows():
            all_splits.append(
                {
                    "sid": sid,
                    "effective_date": pd.to_datetime(row["date"]),
                    "ratio": float(row["split_ratio"]),
                }
            )

    if not all_splits:
        logger.debug("adjustment_transform_no_splits_after_filtering")
        return None

    splits_df = pd.DataFrame(all_splits)
    logger.info("adjustment_transform_splits_complete", count=len(splits_df))
    return splits_df


def _transform_dividends_for_writer(
    dividends_data: dict[str, object],  # dict[symbol -> pl.DataFrame]
    asset_metadata: pd.DataFrame,
) -> pd.DataFrame | None:
    """Transform adapter dividends data to SQLiteAdjustmentWriter format.

    Args:
        dividends_data: Dictionary mapping symbol to DataFrame with columns:
                        - date: Dividend payment date
                        - symbol: Ticker symbol
                        - dividend: Dividend amount (Decimal or float)
        asset_metadata: Asset metadata DataFrame with symbol-to-index mapping

    Returns:
        pandas DataFrame with columns {sid, ex_date, declared_date, record_date, pay_date, amount}
        or None if no dividends

    Format expected by SQLiteAdjustmentWriter:
        - sid: int (asset ID, 0-based index from asset_metadata)
        - ex_date: datetime64 (ex-dividend date)
        - declared_date: datetime64 (or NaT if unknown)
        - record_date: datetime64 (or NaT if unknown)
        - pay_date: datetime64 (payment date)
        - amount: float (dividend amount per share)

    Note:
        YFinance only provides ex_date and amount. Other dates are set to NaT (Not a Time).
        SQLiteAdjustmentWriter handles NaT values correctly.

    Example:
        >>> dividends_data = {"AAPL": pl.DataFrame({"date": [...], "symbol": ["AAPL"], "dividend": [0.22]})}
        >>> asset_metadata = pd.DataFrame({"symbol": ["AAPL", "MSFT"], ...})
        >>> dividends_df = _transform_dividends_for_writer(dividends_data, asset_metadata)
        >>> print(dividends_df)
           sid    ex_date  ... pay_date  amount
        0    0 2023-08-11  ... 2023-08-11    0.22
    """
    import polars as pl

    if not dividends_data:
        logger.debug("adjustment_transform_no_dividends")
        return None

    # Create symbol to SID mapping from asset_metadata
    symbol_to_sid = {symbol: sid for sid, symbol in enumerate(asset_metadata["symbol"])}

    all_dividends = []
    for symbol, dividend_df in dividends_data.items():
        if symbol not in symbol_to_sid:
            logger.warning(
                "adjustment_transform_unknown_symbol",
                symbol=symbol,
                data_type="dividends",
                note="Symbol not in asset metadata, skipping",
            )
            continue

        sid = symbol_to_sid[symbol]

        # Convert Polars to pandas if needed
        if isinstance(dividend_df, pl.DataFrame):
            dividend_df_pd = dividend_df.to_pandas()
        else:
            dividend_df_pd = dividend_df

        # Transform to writer format
        for _, row in dividend_df_pd.iterrows():
            dividend_date = pd.to_datetime(row["date"])
            all_dividends.append(
                {
                    "sid": sid,
                    "ex_date": dividend_date,  # Use date as ex_date
                    "declared_date": pd.NaT,  # YFinance doesn't provide this
                    "record_date": pd.NaT,  # YFinance doesn't provide this
                    "pay_date": dividend_date,  # Use date as pay_date (best approximation)
                    "amount": float(row["dividend"]),
                }
            )

    if not all_dividends:
        logger.debug("adjustment_transform_no_dividends_after_filtering")
        return None

    dividends_df = pd.DataFrame(all_dividends)
    logger.info("adjustment_transform_dividends_complete", count=len(dividends_df))
    return dividends_df


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
    2. Creates asset metadata
    3. Writes asset database
    4. Transforms and writes bar data
    5. Tracks metadata automatically
    """
    import asyncio

    from rustybt.exceptions import DataValidationError

    # Smart date handling: Avoid fetching incomplete current-day data
    original_end = end
    end = _adjust_end_date_for_market_hours(end, bundle_name)

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
    except DataValidationError as e:
        # Validation failed completely - cannot recover
        logger.error(
            "bridge_validation_failed_cannot_recover",
            bundle=bundle_name,
            error=str(e),
            error_type=type(e).__name__,
            recommendation="Try adjusting date range or check data quality at source",
        )
        logger.warning("bridge_skipping_bundle_due_to_validation_failure", bundle=bundle_name)
        return
    except Exception as e:
        logger.error(
            "bridge_fetch_failed",
            bundle=bundle_name,
            error=str(e),
            error_type=type(e).__name__,
        )
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

    # Lenient validation: Filter out rows with invalid OHLCV relationships
    # This is a safety net to handle edge cases that passed the adapter's validation
    df_valid, df_invalid = _filter_invalid_ohlcv_rows(df)

    invalid_count = (
        len(df_invalid)
        if isinstance(df_invalid, pl.DataFrame)
        else len(df_invalid) if hasattr(df_invalid, "__len__") else 0
    )

    if invalid_count > 0:
        # Get affected symbols for logging
        if isinstance(df_invalid, pl.DataFrame):
            affected_symbols = df_invalid.select("symbol").unique().to_series().to_list()
        else:
            affected_symbols = df_invalid["symbol"].unique().tolist()

        logger.warning(
            "bridge_filtered_invalid_ohlcv_rows",
            bundle=bundle_name,
            invalid_count=invalid_count,
            valid_count=len(df_valid),
            affected_symbols=affected_symbols[:10],  # Log first 10
            total_affected_symbols=len(affected_symbols),
        )

        # Use the valid data only
        df = df_valid

        # Check if we have any valid data left
        is_empty = df.is_empty() if isinstance(df, pl.DataFrame) else df.empty
        if is_empty:
            logger.error(
                "bridge_no_valid_data_after_filtering",
                bundle=bundle_name,
                all_rows_invalid=True,
            )
            return

    logger.info("bridge_fetch_complete", bundle=bundle_name, row_count=len(df))

    # Create asset metadata before transformation (need full dataframe with all symbols)
    try:
        asset_metadata = _create_asset_metadata(df, symbols, start, end, bundle_name)
        logger.info(
            "bridge_asset_metadata_created", bundle=bundle_name, asset_count=len(asset_metadata)
        )
    except Exception as e:
        logger.error(
            "bridge_asset_metadata_failed",
            bundle=bundle_name,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise ValueError(f"Asset metadata creation failed for bundle '{bundle_name}': {e}") from e

    # Write asset database (required for bundle loading)
    try:
        # Create exchanges DataFrame
        exchange_name = bundle_name.upper().replace("-", "_")
        exchanges = pd.DataFrame(
            data=[[exchange_name, exchange_name, "US"]],
            columns=["exchange", "canonical_name", "country_code"],
        )
        writers["asset_db_writer"].write(equities=asset_metadata, exchanges=exchanges)
        logger.info("bridge_asset_db_written", bundle=bundle_name, exchange=exchange_name)
    except Exception as e:
        logger.error(
            "bridge_asset_db_write_failed",
            bundle=bundle_name,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise ValueError(f"Asset database write failed for bundle '{bundle_name}': {e}") from e

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

    # Fetch and write corporate actions (splits/dividends) if adapter supports them
    if (
        "adjustment_writer" in writers
        and hasattr(adapter, "fetch_splits")
        and hasattr(adapter, "fetch_dividends")
    ):
        try:
            logger.info(
                "bridge_fetching_adjustments", bundle=bundle_name, symbols_count=len(symbols)
            )

            # Fetch splits and dividends (handle async adapters)
            splits_result = adapter.fetch_splits(symbols)
            if asyncio.iscoroutine(splits_result):
                splits_data = asyncio.run(splits_result)
            else:
                splits_data = splits_result

            dividends_result = adapter.fetch_dividends(symbols)
            if asyncio.iscoroutine(dividends_result):
                dividends_data = asyncio.run(dividends_result)
            else:
                dividends_data = dividends_result

            # Transform to adjustment writer format (requires asset_metadata for SID mapping)
            splits_df = _transform_splits_for_writer(splits_data, asset_metadata)
            dividends_df = _transform_dividends_for_writer(dividends_data, asset_metadata)

            # Write adjustments to database
            writers["adjustment_writer"].write(
                splits=splits_df,
                dividends=dividends_df,
            )

            logger.info(
                "bridge_adjustments_written",
                bundle=bundle_name,
                splits_count=len(splits_df) if splits_df is not None and not splits_df.empty else 0,
                dividends_count=(
                    len(dividends_df) if dividends_df is not None and not dividends_df.empty else 0
                ),
            )

        except Exception as e:
            logger.warning(
                "bridge_adjustments_failed",
                bundle=bundle_name,
                error=str(e),
                error_type=type(e).__name__,
                note="Continuing without adjustments - strategies requiring corporate actions may fail",
            )
    elif "adjustment_writer" not in writers:
        logger.debug(
            "bridge_no_adjustment_writer",
            bundle=bundle_name,
            note="adjustment_writer not provided in writers dict",
        )
    else:
        logger.debug(
            "bridge_adapter_no_adjustments_support",
            bundle=bundle_name,
            adapter_type=type(adapter).__name__,
            note="Adapter does not support fetch_splits/fetch_dividends",
        )

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
            "asset_db_writer": asset_db_writer,
            "daily_bar_writer": daily_bar_writer,
            "minute_bar_writer": minute_bar_writer,
            "adjustment_writer": adjustment_writer,
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
            "asset_db_writer": asset_db_writer,
            "daily_bar_writer": daily_bar_writer,
            "minute_bar_writer": minute_bar_writer,
            "adjustment_writer": adjustment_writer,
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
            "asset_db_writer": asset_db_writer,
            "daily_bar_writer": daily_bar_writer,
            "minute_bar_writer": minute_bar_writer,
            "adjustment_writer": adjustment_writer,
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
            "asset_db_writer": asset_db_writer,
            "daily_bar_writer": daily_bar_writer,
            "minute_bar_writer": minute_bar_writer,
            "adjustment_writer": adjustment_writer,
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
