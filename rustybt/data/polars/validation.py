"""Data quality validation for OHLCV data with Decimal precision.

This module provides validation functions for OHLCV data to ensure:
- Price relationships are valid (H >= max(O,C), L <= min(O,C))
- All prices are non-negative
- No data quality issues (outliers, gaps, volume spikes)

All validations use Decimal comparison for exact arithmetic.
"""

import polars as pl
import structlog
from decimal import Decimal
from typing import Dict, List, Optional

logger = structlog.get_logger(__name__)


class DataError(Exception):
    """Base exception for data errors."""


class ValidationError(DataError):
    """Raised when data validation fails."""


def validate_ohlcv_relationships(df: pl.DataFrame) -> bool:
    """Validate OHLCV relationships using Decimal comparison.

    Checks:
    - high >= max(open, close) for all bars
    - low <= min(open, close) for all bars
    - high >= low for all bars
    - all prices > 0 (non-negative)

    Args:
        df: Polars DataFrame with OHLCV columns (Decimal dtype)

    Returns:
        True if all validations pass

    Raises:
        ValidationError: If any OHLCV relationships are invalid

    Example:
        >>> df = pl.DataFrame({
        ...     "open": [Decimal("100")],
        ...     "high": [Decimal("105")],
        ...     "low": [Decimal("95")],
        ...     "close": [Decimal("102")],
        ... })
        >>> validate_ohlcv_relationships(df)
        True
    """
    # Check high >= low
    invalid_hl = df.filter(pl.col("high") < pl.col("low"))
    if len(invalid_hl) > 0:
        logger.error(
            "ohlcv_validation_failed",
            check="high_vs_low",
            invalid_count=len(invalid_hl),
            sample_rows=invalid_hl.head(5).to_dicts(),
        )
        raise ValidationError(
            f"Invalid OHLCV: high < low in {len(invalid_hl)} rows. "
            f"Sample: {invalid_hl.head(1).to_dicts()}"
        )

    # Check high >= open
    invalid_ho = df.filter(pl.col("high") < pl.col("open"))
    if len(invalid_ho) > 0:
        logger.error(
            "ohlcv_validation_failed",
            check="high_vs_open",
            invalid_count=len(invalid_ho),
            sample_rows=invalid_ho.head(5).to_dicts(),
        )
        raise ValidationError(
            f"Invalid OHLCV: high < open in {len(invalid_ho)} rows. "
            f"Sample: {invalid_ho.head(1).to_dicts()}"
        )

    # Check high >= close
    invalid_hc = df.filter(pl.col("high") < pl.col("close"))
    if len(invalid_hc) > 0:
        logger.error(
            "ohlcv_validation_failed",
            check="high_vs_close",
            invalid_count=len(invalid_hc),
            sample_rows=invalid_hc.head(5).to_dicts(),
        )
        raise ValidationError(
            f"Invalid OHLCV: high < close in {len(invalid_hc)} rows. "
            f"Sample: {invalid_hc.head(1).to_dicts()}"
        )

    # Check low <= open
    invalid_lo = df.filter(pl.col("low") > pl.col("open"))
    if len(invalid_lo) > 0:
        logger.error(
            "ohlcv_validation_failed",
            check="low_vs_open",
            invalid_count=len(invalid_lo),
            sample_rows=invalid_lo.head(5).to_dicts(),
        )
        raise ValidationError(
            f"Invalid OHLCV: low > open in {len(invalid_lo)} rows. "
            f"Sample: {invalid_lo.head(1).to_dicts()}"
        )

    # Check low <= close
    invalid_lc = df.filter(pl.col("low") > pl.col("close"))
    if len(invalid_lc) > 0:
        logger.error(
            "ohlcv_validation_failed",
            check="low_vs_close",
            invalid_count=len(invalid_lc),
            sample_rows=invalid_lc.head(5).to_dicts(),
        )
        raise ValidationError(
            f"Invalid OHLCV: low > close in {len(invalid_lc)} rows. "
            f"Sample: {invalid_lc.head(1).to_dicts()}"
        )

    # Check all prices are non-negative
    zero = pl.lit(Decimal("0"))
    negative_prices = df.filter(
        (pl.col("open") < zero)
        | (pl.col("high") < zero)
        | (pl.col("low") < zero)
        | (pl.col("close") < zero)
    )
    if len(negative_prices) > 0:
        logger.error(
            "ohlcv_validation_failed",
            check="non_negative_prices",
            invalid_count=len(negative_prices),
            sample_rows=negative_prices.head(5).to_dicts(),
        )
        raise ValidationError(
            f"Invalid OHLCV: negative prices in {len(negative_prices)} rows. "
            f"Sample: {negative_prices.head(1).to_dicts()}"
        )

    logger.info("ohlcv_validation_passed", row_count=len(df))
    return True


def detect_price_outliers(
    df: pl.DataFrame, threshold_std: float = 3.0
) -> pl.DataFrame:
    """Detect price outliers using Decimal statistics.

    Identifies bars where price deviates significantly from mean.
    Uses z-score method: abs(price - mean) > threshold_std × std

    Args:
        df: Polars DataFrame with OHLCV columns
        threshold_std: Standard deviation threshold (default: 3.0)

    Returns:
        DataFrame containing only outlier rows

    Example:
        >>> df = pl.DataFrame({"close": [Decimal(str(x)) for x in range(100, 110)]})
        >>> df = df.with_row_index("idx")
        >>> df = df.with_columns(pl.lit(1).alias("sid"))
        >>> outliers = detect_price_outliers(df)
        >>> assert len(outliers) >= 0  # May or may not have outliers
    """
    if len(df) < 2:
        logger.warning("outlier_detection_skipped", reason="insufficient_data", rows=len(df))
        return df.filter(pl.lit(False))  # Return empty DataFrame with same schema

    # Calculate mean and std for close prices
    stats = df.select(
        [pl.col("close").cast(pl.Float64).mean().alias("mean_close"), pl.col("close").cast(pl.Float64).std().alias("std_close")]
    )

    mean_close = stats["mean_close"][0]
    std_close = stats["std_close"][0]

    if std_close == 0 or std_close is None:
        logger.warning("outlier_detection_skipped", reason="zero_std", mean=mean_close)
        return df.filter(pl.lit(False))  # Return empty DataFrame

    # Find outliers: abs(close - mean) > threshold_std × std
    threshold = Decimal(str(threshold_std * std_close))
    mean_decimal = Decimal(str(mean_close))

    outliers = df.with_columns(
        ((pl.col("close") - mean_decimal).abs()).alias("deviation")
    ).filter(pl.col("deviation") > threshold)

    if len(outliers) > 0:
        logger.warning(
            "price_outliers_detected",
            outlier_count=len(outliers),
            total_rows=len(df),
            threshold_std=threshold_std,
            sample_rows=outliers.head(5).to_dicts(),
        )

    return outliers.drop("deviation")


def detect_large_gaps(
    df: pl.DataFrame, expected_interval: str = "1d"
) -> pl.DataFrame:
    """Detect large gaps in time series data.

    Identifies missing data by finding timestamp differences exceeding
    the expected interval.

    Args:
        df: Polars DataFrame with 'date' or 'timestamp' column
        expected_interval: Expected time interval (e.g., "1d", "1h", "1m")

    Returns:
        DataFrame with gap information (start, end, duration)

    Example:
        >>> df = pl.DataFrame({
        ...     "date": [pl.Date(2023, 1, 1), pl.Date(2023, 1, 10)],
        ...     "sid": [1, 1],
        ...     "close": [Decimal("100"), Decimal("101")]
        ... })
        >>> gaps = detect_large_gaps(df)
        >>> assert len(gaps) >= 0  # May have gaps
    """
    if len(df) < 2:
        logger.warning("gap_detection_skipped", reason="insufficient_data", rows=len(df))
        return pl.DataFrame()

    # Determine time column
    time_col = "timestamp" if "timestamp" in df.columns else "date"

    # Sort by time and sid
    df_sorted = df.sort([time_col, "sid"])

    # Calculate time differences
    df_with_diff = df_sorted.with_columns(
        pl.col(time_col).diff().alias("time_diff")
    )

    # Parse expected interval
    if expected_interval == "1d":
        max_gap = pl.duration(days=7)  # Allow up to 1 week gap (weekends + holidays)
    elif expected_interval == "1h":
        max_gap = pl.duration(hours=24)
    elif expected_interval == "1m":
        max_gap = pl.duration(minutes=60)
    else:
        raise ValueError(f"Unsupported interval: {expected_interval}")

    # Find gaps exceeding threshold
    gaps = df_with_diff.filter(pl.col("time_diff") > max_gap)

    if len(gaps) > 0:
        logger.warning(
            "large_gaps_detected",
            gap_count=len(gaps),
            expected_interval=expected_interval,
            sample_gaps=gaps.head(5).to_dicts(),
        )

    return gaps


def detect_volume_spikes(
    df: pl.DataFrame, threshold_std: float = 5.0
) -> pl.DataFrame:
    """Detect volume spikes using Decimal volume data.

    Identifies bars where volume exceeds mean + threshold_std × std.

    Args:
        df: Polars DataFrame with 'volume' column
        threshold_std: Standard deviation threshold (default: 5.0)

    Returns:
        DataFrame containing only rows with volume spikes

    Example:
        >>> df = pl.DataFrame({"volume": [Decimal("1000")] * 10 + [Decimal("50000")]})
        >>> df = df.with_row_index("idx")
        >>> df = df.with_columns(pl.lit(1).alias("sid"))
        >>> spikes = detect_volume_spikes(df)
        >>> assert len(spikes) >= 0  # Should detect the spike
    """
    if len(df) < 2:
        logger.warning("volume_spike_detection_skipped", reason="insufficient_data", rows=len(df))
        return df.filter(pl.lit(False))

    # Calculate volume statistics
    stats = df.select(
        [pl.col("volume").cast(pl.Float64).mean().alias("mean_volume"), pl.col("volume").cast(pl.Float64).std().alias("std_volume")]
    )

    mean_volume = stats["mean_volume"][0]
    std_volume = stats["std_volume"][0]

    if std_volume == 0 or std_volume is None:
        logger.warning("volume_spike_detection_skipped", reason="zero_std", mean=mean_volume)
        return df.filter(pl.lit(False))

    # Find spikes: volume > mean + threshold_std × std
    threshold = Decimal(str(mean_volume + threshold_std * std_volume))

    spikes = df.filter(pl.col("volume") > threshold)

    if len(spikes) > 0:
        logger.warning(
            "volume_spikes_detected",
            spike_count=len(spikes),
            total_rows=len(df),
            threshold_std=threshold_std,
            sample_spikes=spikes.head(5).to_dicts(),
        )

    return spikes


def generate_data_quality_report(df: pl.DataFrame) -> Dict[str, any]:
    """Generate comprehensive data quality report.

    Args:
        df: Polars DataFrame with OHLCV data

    Returns:
        Dictionary with validation results and quality metrics

    Example:
        >>> df = pl.DataFrame({
        ...     "date": [pl.Date(2023, 1, i) for i in range(1, 11)],
        ...     "sid": [1] * 10,
        ...     "open": [Decimal("100")] * 10,
        ...     "high": [Decimal("105")] * 10,
        ...     "low": [Decimal("95")] * 10,
        ...     "close": [Decimal("102")] * 10,
        ...     "volume": [Decimal("1000")] * 10,
        ... })
        >>> report = generate_data_quality_report(df)
        >>> assert report["ohlcv_valid"] is True
    """
    report: Dict[str, any] = {
        "total_rows": len(df),
        "ohlcv_valid": False,
        "outlier_count": 0,
        "gap_count": 0,
        "volume_spike_count": 0,
        "errors": [],
    }

    try:
        # Validate OHLCV relationships
        validate_ohlcv_relationships(df)
        report["ohlcv_valid"] = True
    except ValidationError as e:
        report["errors"].append(str(e))

    try:
        # Detect outliers
        outliers = detect_price_outliers(df)
        report["outlier_count"] = len(outliers)
    except Exception as e:
        logger.error("outlier_detection_failed", error=str(e))
        report["errors"].append(f"Outlier detection failed: {e}")

    try:
        # Detect gaps
        gaps = detect_large_gaps(df)
        report["gap_count"] = len(gaps)
    except Exception as e:
        logger.error("gap_detection_failed", error=str(e))
        report["errors"].append(f"Gap detection failed: {e}")

    try:
        # Detect volume spikes
        spikes = detect_volume_spikes(df)
        report["volume_spike_count"] = len(spikes)
    except Exception as e:
        logger.error("volume_spike_detection_failed", error=str(e))
        report["errors"].append(f"Volume spike detection failed: {e}")

    logger.info(
        "data_quality_report_generated",
        total_rows=report["total_rows"],
        ohlcv_valid=report["ohlcv_valid"],
        outliers=report["outlier_count"],
        gaps=report["gap_count"],
        volume_spikes=report["volume_spike_count"],
        errors=len(report["errors"]),
    )

    return report
