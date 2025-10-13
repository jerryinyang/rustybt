"""Multi-resolution aggregation for OHLCV data with Decimal precision.

This module provides functions to resample OHLCV data between different
time frequencies while preserving Decimal precision.

Aggregation Rules:
- open: first bar's open
- high: maximum of all highs
- low: minimum of all lows
- close: last bar's close
- volume: sum of all volumes
"""

import polars as pl
import structlog

from rustybt.data.polars.validation import validate_ohlcv_relationships

logger = structlog.get_logger(__name__)


class AggregationError(Exception):
    """Raised when aggregation fails."""


def resample_minute_to_daily(minute_df: pl.DataFrame) -> pl.DataFrame:
    """Resample minute bars to daily bars with Decimal precision.

    Args:
        minute_df: Minute bars DataFrame with Decimal columns
            Required columns: timestamp, sid, open, high, low, close, volume

    Returns:
        Daily bars DataFrame with Decimal columns
            Columns: date, sid, open, high, low, close, volume

    Raises:
        AggregationError: If aggregation fails or required columns missing

    Example:
        >>> from datetime import datetime
        >>> minute_df = pl.DataFrame({
        ...     "timestamp": [
        ...         datetime(2023, 1, 1, 9, 30),
        ...         datetime(2023, 1, 1, 9, 31),
        ...         datetime(2023, 1, 1, 9, 32),
        ...     ],
        ...     "sid": [1, 1, 1],
        ...     "open": [Decimal("100.01"), Decimal("100.02"), Decimal("100.03")],
        ...     "high": [Decimal("100.05"), Decimal("100.06"), Decimal("100.07")],
        ...     "low": [Decimal("99.99"), Decimal("99.98"), Decimal("99.97")],
        ...     "close": [Decimal("100.02"), Decimal("100.03"), Decimal("100.04")],
        ...     "volume": [Decimal("1000"), Decimal("1500"), Decimal("2000")],
        ... })
        >>> daily_df = resample_minute_to_daily(minute_df)
        >>> assert daily_df["open"][0] == Decimal("100.01")
        >>> assert daily_df["high"][0] == Decimal("100.07")
        >>> assert daily_df["low"][0] == Decimal("99.97")
        >>> assert daily_df["close"][0] == Decimal("100.04")
        >>> assert daily_df["volume"][0] == Decimal("4500")
    """
    # Validate required columns
    required_cols = ["timestamp", "sid", "open", "high", "low", "close", "volume"]
    missing_cols = set(required_cols) - set(minute_df.columns)
    if missing_cols:
        raise AggregationError(f"Missing required columns: {missing_cols}")

    if len(minute_df) == 0:
        logger.warning("resample_minute_to_daily_skipped", reason="empty_dataframe")
        return pl.DataFrame(
            schema={
                "date": pl.Date,
                "sid": pl.Int64,
                "open": pl.Decimal(precision=18, scale=8),
                "high": pl.Decimal(precision=18, scale=8),
                "low": pl.Decimal(precision=18, scale=8),
                "close": pl.Decimal(precision=18, scale=8),
                "volume": pl.Decimal(precision=18, scale=8),
            }
        )

    # Aggregate minute bars to daily
    daily_df = (
        minute_df.sort(["sid", "timestamp"])
        .group_by([pl.col("timestamp").cast(pl.Date).alias("date"), "sid"])
        .agg(
            [
                pl.col("open").first().alias("open"),
                pl.col("high").max().alias("high"),
                pl.col("low").min().alias("low"),
                pl.col("close").last().alias("close"),
                pl.col("volume").sum().alias("volume"),
            ]
        )
        .sort(["date", "sid"])
    )

    # Validate aggregated OHLCV relationships
    try:
        validate_ohlcv_relationships(daily_df)
    except Exception as e:
        raise AggregationError(f"Aggregated data failed validation: {e}") from e

    logger.info(
        "minute_to_daily_resampling_complete",
        input_rows=len(minute_df),
        output_rows=len(daily_df),
    )

    return daily_df


def resample_daily_to_weekly(daily_df: pl.DataFrame) -> pl.DataFrame:
    """Resample daily bars to weekly bars with Decimal precision.

    Args:
        daily_df: Daily bars DataFrame with Decimal columns
            Required columns: date, sid, open, high, low, close, volume

    Returns:
        Weekly bars DataFrame with Decimal columns
            Columns: week_start_date, sid, open, high, low, close, volume

    Raises:
        AggregationError: If aggregation fails or required columns missing

    Example:
        >>> from datetime import date
        >>> daily_df = pl.DataFrame({
        ...     "date": [date(2023, 1, 2), date(2023, 1, 3), date(2023, 1, 4)],
        ...     "sid": [1, 1, 1],
        ...     "open": [Decimal("100"), Decimal("101"), Decimal("102")],
        ...     "high": [Decimal("105"), Decimal("106"), Decimal("107")],
        ...     "low": [Decimal("95"), Decimal("96"), Decimal("97")],
        ...     "close": [Decimal("102"), Decimal("103"), Decimal("104")],
        ...     "volume": [Decimal("1000"), Decimal("1500"), Decimal("2000")],
        ... })
        >>> weekly_df = resample_daily_to_weekly(daily_df)
        >>> assert weekly_df["open"][0] == Decimal("100")
        >>> assert weekly_df["high"][0] == Decimal("107")
    """
    # Validate required columns
    required_cols = ["date", "sid", "open", "high", "low", "close", "volume"]
    missing_cols = set(required_cols) - set(daily_df.columns)
    if missing_cols:
        raise AggregationError(f"Missing required columns: {missing_cols}")

    if len(daily_df) == 0:
        logger.warning("resample_daily_to_weekly_skipped", reason="empty_dataframe")
        return pl.DataFrame(
            schema={
                "week_start_date": pl.Date,
                "sid": pl.Int64,
                "open": pl.Decimal(precision=18, scale=8),
                "high": pl.Decimal(precision=18, scale=8),
                "low": pl.Decimal(precision=18, scale=8),
                "close": pl.Decimal(precision=18, scale=8),
                "volume": pl.Decimal(precision=18, scale=8),
            }
        )

    # Add week column (Monday as start of week)
    weekly_df = (
        daily_df.sort(["sid", "date"])
        .with_columns(pl.col("date").dt.truncate("1w", offset="0d").alias("week_start_date"))
        .group_by(["week_start_date", "sid"])
        .agg(
            [
                pl.col("open").first().alias("open"),
                pl.col("high").max().alias("high"),
                pl.col("low").min().alias("low"),
                pl.col("close").last().alias("close"),
                pl.col("volume").sum().alias("volume"),
            ]
        )
        .sort(["week_start_date", "sid"])
    )

    # Validate aggregated OHLCV relationships
    try:
        validate_ohlcv_relationships(weekly_df)
    except Exception as e:
        raise AggregationError(f"Aggregated data failed validation: {e}") from e

    logger.info(
        "daily_to_weekly_resampling_complete",
        input_rows=len(daily_df),
        output_rows=len(weekly_df),
    )

    return weekly_df


def resample_daily_to_monthly(daily_df: pl.DataFrame) -> pl.DataFrame:
    """Resample daily bars to monthly bars with Decimal precision.

    Args:
        daily_df: Daily bars DataFrame with Decimal columns
            Required columns: date, sid, open, high, low, close, volume

    Returns:
        Monthly bars DataFrame with Decimal columns
            Columns: month_start_date, sid, open, high, low, close, volume

    Raises:
        AggregationError: If aggregation fails or required columns missing

    Example:
        >>> from datetime import date
        >>> daily_df = pl.DataFrame({
        ...     "date": [date(2023, 1, 2), date(2023, 1, 15), date(2023, 1, 30)],
        ...     "sid": [1, 1, 1],
        ...     "open": [Decimal("100"), Decimal("101"), Decimal("102")],
        ...     "high": [Decimal("105"), Decimal("106"), Decimal("107")],
        ...     "low": [Decimal("95"), Decimal("96"), Decimal("97")],
        ...     "close": [Decimal("102"), Decimal("103"), Decimal("104")],
        ...     "volume": [Decimal("1000"), Decimal("1500"), Decimal("2000")],
        ... })
        >>> monthly_df = resample_daily_to_monthly(daily_df)
        >>> assert monthly_df["open"][0] == Decimal("100")
        >>> assert monthly_df["volume"][0] == Decimal("4500")
    """
    # Validate required columns
    required_cols = ["date", "sid", "open", "high", "low", "close", "volume"]
    missing_cols = set(required_cols) - set(daily_df.columns)
    if missing_cols:
        raise AggregationError(f"Missing required columns: {missing_cols}")

    if len(daily_df) == 0:
        logger.warning("resample_daily_to_monthly_skipped", reason="empty_dataframe")
        return pl.DataFrame(
            schema={
                "month_start_date": pl.Date,
                "sid": pl.Int64,
                "open": pl.Decimal(precision=18, scale=8),
                "high": pl.Decimal(precision=18, scale=8),
                "low": pl.Decimal(precision=18, scale=8),
                "close": pl.Decimal(precision=18, scale=8),
                "volume": pl.Decimal(precision=18, scale=8),
            }
        )

    # Add month column (first day of month)
    monthly_df = (
        daily_df.sort(["sid", "date"])
        .with_columns(pl.col("date").dt.truncate("1mo").alias("month_start_date"))
        .group_by(["month_start_date", "sid"])
        .agg(
            [
                pl.col("open").first().alias("open"),
                pl.col("high").max().alias("high"),
                pl.col("low").min().alias("low"),
                pl.col("close").last().alias("close"),
                pl.col("volume").sum().alias("volume"),
            ]
        )
        .sort(["month_start_date", "sid"])
    )

    # Validate aggregated OHLCV relationships
    try:
        validate_ohlcv_relationships(monthly_df)
    except Exception as e:
        raise AggregationError(f"Aggregated data failed validation: {e}") from e

    logger.info(
        "daily_to_monthly_resampling_complete",
        input_rows=len(daily_df),
        output_rows=len(monthly_df),
    )

    return monthly_df


def resample_custom_interval(
    df: pl.DataFrame, interval: str, time_col: str = "timestamp"
) -> pl.DataFrame:
    """Resample OHLCV data to custom interval with Decimal precision.

    Args:
        df: OHLCV DataFrame with Decimal columns
        interval: Polars duration string (e.g., "5m", "15m", "4h", "1d")
        time_col: Name of time column ("timestamp" or "date")

    Returns:
        Resampled DataFrame with Decimal columns

    Raises:
        AggregationError: If aggregation fails

    Example:
        >>> from datetime import datetime
        >>> df = pl.DataFrame({
        ...     "timestamp": [datetime(2023, 1, 1, 9, i) for i in range(30, 45)],
        ...     "sid": [1] * 15,
        ...     "open": [Decimal(str(100 + i*0.1)) for i in range(15)],
        ...     "high": [Decimal(str(101 + i*0.1)) for i in range(15)],
        ...     "low": [Decimal(str(99 + i*0.1)) for i in range(15)],
        ...     "close": [Decimal(str(100.5 + i*0.1)) for i in range(15)],
        ...     "volume": [Decimal("1000")] * 15,
        ... })
        >>> resampled = resample_custom_interval(df, "5m")
        >>> assert len(resampled) == 3  # 15 minutes / 5-minute bars = 3 bars
    """
    # Validate required columns
    required_cols = [time_col, "sid", "open", "high", "low", "close", "volume"]
    missing_cols = set(required_cols) - set(df.columns)
    if missing_cols:
        raise AggregationError(f"Missing required columns: {missing_cols}")

    if len(df) == 0:
        logger.warning("resample_custom_interval_skipped", reason="empty_dataframe")
        schema_time_type = pl.Datetime("us") if time_col == "timestamp" else pl.Date
        return pl.DataFrame(
            schema={
                time_col: schema_time_type,
                "sid": pl.Int64,
                "open": pl.Decimal(precision=18, scale=8),
                "high": pl.Decimal(precision=18, scale=8),
                "low": pl.Decimal(precision=18, scale=8),
                "close": pl.Decimal(precision=18, scale=8),
                "volume": pl.Decimal(precision=18, scale=8),
            }
        )

    # Resample to custom interval
    resampled_df = (
        df.sort(["sid", time_col])
        .with_columns(pl.col(time_col).dt.truncate(interval).alias("interval_start"))
        .group_by(["interval_start", "sid"])
        .agg(
            [
                pl.col("open").first().alias("open"),
                pl.col("high").max().alias("high"),
                pl.col("low").min().alias("low"),
                pl.col("close").last().alias("close"),
                pl.col("volume").sum().alias("volume"),
            ]
        )
        .rename({"interval_start": time_col})
        .sort([time_col, "sid"])
    )

    # Validate aggregated OHLCV relationships
    try:
        validate_ohlcv_relationships(resampled_df)
    except Exception as e:
        raise AggregationError(f"Aggregated data failed validation: {e}") from e

    logger.info(
        "custom_interval_resampling_complete",
        interval=interval,
        input_rows=len(df),
        output_rows=len(resampled_df),
    )

    return resampled_df
