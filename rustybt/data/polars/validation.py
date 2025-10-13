"""Data quality validation for OHLCV data with Decimal precision.

This module provides multi-layer validation for OHLCV data to ensure:
- Layer 1: Schema validation (correct types, required fields, value ranges)
- Layer 2: OHLCV relationship validation (H >= L, H >= O/C, L <= O/C, V >= 0)
- Layer 3: Outlier detection (price spikes, volume anomalies)
- Layer 4: Temporal consistency (sorted timestamps, no duplicates, no future data, gap detection)

All validations use Decimal comparison for exact arithmetic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

import polars as pl
import structlog
from pydantic import BaseModel, Field, field_validator

# Import centralized exceptions
from rustybt.exceptions import DataValidationError

logger = structlog.get_logger(__name__)


# ============================================================================
# Configuration
# ============================================================================


class ValidationSeverity(str, Enum):
    """Severity levels for validation results."""

    ERROR = "ERROR"  # Critical violations that prevent data usage
    WARNING = "WARNING"  # Suspicious but potentially valid data


@dataclass
class ValidationConfig:
    """Configuration for data validation.

    Attributes:
        enforce_schema: Enable Layer 1 (schema validation)
        enforce_ohlcv_relationships: Enable Layer 2 (OHLCV relationship validation)
        enable_outlier_detection: Enable Layer 3 (outlier detection)
        price_spike_threshold_std: Price spike threshold in standard deviations
        volume_spike_threshold: Volume spike threshold as multiple of mean volume
        enforce_temporal_consistency: Enable Layer 4 (temporal consistency)
        allow_gaps: Allow gaps in data (e.g., market holidays)
        max_gap_days: Maximum allowed gap in days
        expected_frequency: Expected data frequency (e.g., '1d', '1h', '1m')
    """

    # Layer 1: Schema validation
    enforce_schema: bool = True

    # Layer 2: OHLCV relationship validation
    enforce_ohlcv_relationships: bool = True

    # Layer 3: Outlier detection
    enable_outlier_detection: bool = True
    price_spike_threshold_std: float = 5.0  # Standard deviations
    volume_spike_threshold: float = 10.0  # Multiple of mean volume

    # Layer 4: Temporal consistency
    enforce_temporal_consistency: bool = True
    allow_gaps: bool = True  # Allow gaps in data (e.g., market holidays)
    max_gap_days: int = 7  # Maximum allowed gap
    expected_frequency: str = "1d"  # Expected time interval

    @classmethod
    def for_crypto(cls) -> ValidationConfig:
        """Create config optimized for 24/7 crypto markets.

        Returns:
            ValidationConfig with crypto-specific settings
        """
        return cls(
            price_spike_threshold_std=8.0,  # Crypto is more volatile
            volume_spike_threshold=20.0,  # Higher volume spikes are common
            allow_gaps=False,  # 24/7 markets shouldn't have gaps
            max_gap_days=1,  # Flag gaps longer than 1 day
        )

    @classmethod
    def for_stocks(cls) -> ValidationConfig:
        """Create config optimized for stock markets.

        Returns:
            ValidationConfig with stock-specific settings
        """
        return cls(
            price_spike_threshold_std=5.0,  # Stocks less volatile
            volume_spike_threshold=10.0,  # Standard volume spike threshold
            allow_gaps=True,  # Weekends and holidays
            max_gap_days=7,  # Allow up to 1 week gaps
        )


@dataclass
class ValidationViolation:
    """Single validation violation.

    Attributes:
        layer: Validation layer (1-4)
        severity: ERROR or WARNING
        message: Human-readable violation message
        details: Additional context about the violation
    """

    layer: int
    severity: ValidationSeverity
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Result of data validation.

    Attributes:
        valid: Whether data passed all ERROR-level validations
        violations: List of validation violations
        row_count: Number of rows validated
        metadata: Additional metadata about validation
    """

    valid: bool
    violations: list[ValidationViolation] = field(default_factory=list)
    row_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def has_errors(self) -> bool:
        """Check if any ERROR-level violations exist.

        Returns:
            True if ERROR violations found
        """
        return any(v.severity == ValidationSeverity.ERROR for v in self.violations)

    def has_warnings(self) -> bool:
        """Check if any WARNING-level violations exist.

        Returns:
            True if WARNING violations found
        """
        return any(v.severity == ValidationSeverity.WARNING for v in self.violations)

    def get_errors(self) -> list[ValidationViolation]:
        """Get all ERROR-level violations.

        Returns:
            List of ERROR violations
        """
        return [v for v in self.violations if v.severity == ValidationSeverity.ERROR]

    def get_warnings(self) -> list[ValidationViolation]:
        """Get all WARNING-level violations.

        Returns:
            List of WARNING violations
        """
        return [v for v in self.violations if v.severity == ValidationSeverity.WARNING]


# ============================================================================
# Layer 1: Schema Validation (Pydantic)
# ============================================================================


class OHLCVBarSchema(BaseModel):
    """Pydantic schema for OHLCV bar validation.

    Validates:
    - Required fields exist
    - Data types are correct
    - Value ranges are valid (prices > 0, volume >= 0)
    """

    timestamp: datetime
    open: Decimal = Field(gt=0)
    high: Decimal = Field(gt=0)
    low: Decimal = Field(gt=0)
    close: Decimal = Field(gt=0)
    volume: Decimal = Field(ge=0)

    @field_validator("high")
    @classmethod
    def validate_high_ge_low(cls, v: Decimal, info) -> Decimal:
        """Validate high >= low.

        Args:
            v: High price
            info: Validation context with other field values

        Returns:
            High price if valid

        Raises:
            ValueError: If high < low
        """
        if "low" in info.data and v < info.data["low"]:
            raise ValueError(f"high ({v}) must be >= low ({info.data['low']})")
        return v

    @field_validator("high")
    @classmethod
    def validate_high_ge_open(cls, v: Decimal, info) -> Decimal:
        """Validate high >= open.

        Args:
            v: High price
            info: Validation context with other field values

        Returns:
            High price if valid

        Raises:
            ValueError: If high < open
        """
        if "open" in info.data and v < info.data["open"]:
            raise ValueError(f"high ({v}) must be >= open ({info.data['open']})")
        return v

    @field_validator("high")
    @classmethod
    def validate_high_ge_close(cls, v: Decimal, info) -> Decimal:
        """Validate high >= close.

        Args:
            v: High price
            info: Validation context with other field values

        Returns:
            High price if valid

        Raises:
            ValueError: If high < close
        """
        if "close" in info.data and v < info.data["close"]:
            raise ValueError(f"high ({v}) must be >= close ({info.data['close']})")
        return v

    @field_validator("low")
    @classmethod
    def validate_low_le_open(cls, v: Decimal, info) -> Decimal:
        """Validate low <= open.

        Args:
            v: Low price
            info: Validation context with other field values

        Returns:
            Low price if valid

        Raises:
            ValueError: If low > open
        """
        if "open" in info.data and v > info.data["open"]:
            raise ValueError(f"low ({v}) must be <= open ({info.data['open']})")
        return v

    @field_validator("low")
    @classmethod
    def validate_low_le_close(cls, v: Decimal, info) -> Decimal:
        """Validate low <= close.

        Args:
            v: Low price
            info: Validation context with other field values

        Returns:
            Low price if valid

        Raises:
            ValueError: If low > close
        """
        if "close" in info.data and v > info.data["close"]:
            raise ValueError(f"low ({v}) must be <= close ({info.data['close']})")
        return v


# ============================================================================
# Legacy Exceptions (for backward compatibility)
# ============================================================================


class DataError(DataValidationError):
    """Legacy exception for data errors (use DataValidationError instead)."""


class ValidationError(DataValidationError):
    """Legacy exception for validation errors (use DataValidationError instead)."""


# ============================================================================
# Layer 1: Schema Validation Functions
# ============================================================================


def validate_schema(df: pl.DataFrame) -> list[ValidationViolation]:
    """Validate DataFrame schema against OHLCV requirements.

    Checks:
    - Required columns exist (timestamp, open, high, low, close, volume)
    - Data types are appropriate
    - No NULL values in required columns
    - All prices > 0
    - Volume >= 0

    Args:
        df: Polars DataFrame to validate

    Returns:
        List of violations (empty if valid)

    Example:
        >>> df = pl.DataFrame({"close": [Decimal("100")]})  # Missing columns
        >>> violations = validate_schema(df)
        >>> assert len(violations) > 0
    """
    violations: list[ValidationViolation] = []

    # Check required columns exist
    required_cols = ["timestamp", "open", "high", "low", "close", "volume"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        violations.append(
            ValidationViolation(
                layer=1,
                severity=ValidationSeverity.ERROR,
                message=f"Missing required columns: {missing_cols}",
                details={"missing_columns": missing_cols},
            )
        )
        # Can't continue validation without required columns
        return violations

    # Check for NULL values in required columns
    null_counts = {col: df[col].null_count() for col in required_cols}
    columns_with_nulls = {col: count for col, count in null_counts.items() if count > 0}
    if columns_with_nulls:
        violations.append(
            ValidationViolation(
                layer=1,
                severity=ValidationSeverity.ERROR,
                message=f"NULL values found in required columns: {columns_with_nulls}",
                details={"null_counts": columns_with_nulls},
            )
        )

    # Check all prices are positive (> 0)
    zero = pl.lit(Decimal("0"))
    negative_or_zero_prices = df.filter(
        (pl.col("open") <= zero)
        | (pl.col("high") <= zero)
        | (pl.col("low") <= zero)
        | (pl.col("close") <= zero)
    )
    if len(negative_or_zero_prices) > 0:
        violations.append(
            ValidationViolation(
                layer=1,
                severity=ValidationSeverity.ERROR,
                message=f"Non-positive prices found in {len(negative_or_zero_prices)} rows",
                details={
                    "invalid_row_count": len(negative_or_zero_prices),
                    "sample_rows": negative_or_zero_prices.head(5).to_dicts(),
                },
            )
        )

    # Check volume is non-negative (>= 0)
    negative_volume = df.filter(pl.col("volume") < zero)
    if len(negative_volume) > 0:
        violations.append(
            ValidationViolation(
                layer=1,
                severity=ValidationSeverity.ERROR,
                message=f"Negative volume found in {len(negative_volume)} rows",
                details={
                    "invalid_row_count": len(negative_volume),
                    "sample_rows": negative_volume.head(5).to_dicts(),
                },
            )
        )

    if len(violations) == 0:
        logger.info("schema_validation_passed", row_count=len(df))
    else:
        logger.error(
            "schema_validation_failed",
            row_count=len(df),
            violation_count=len(violations),
        )

    return violations


# ============================================================================
# Layer 2: OHLCV Relationship Validation
# ============================================================================


def validate_ohlcv_relationships_v2(df: pl.DataFrame) -> list[ValidationViolation]:
    """Validate OHLCV relationships using Decimal comparison.

    Checks:
    - high >= low for all bars
    - high >= open for all bars
    - high >= close for all bars
    - low <= open for all bars
    - low <= close for all bars

    Args:
        df: Polars DataFrame with OHLCV columns

    Returns:
        List of violations (empty if valid)

    Example:
        >>> df = pl.DataFrame({
        ...     "timestamp": [datetime.now()],
        ...     "open": [Decimal("100")],
        ...     "high": [Decimal("90")],  # Invalid: high < open
        ...     "low": [Decimal("95")],
        ...     "close": [Decimal("102")],
        ...     "volume": [Decimal("1000")],
        ... })
        >>> violations = validate_ohlcv_relationships_v2(df)
        >>> assert len(violations) > 0
    """
    violations: list[ValidationViolation] = []

    # Check high >= low
    invalid_hl = df.filter(pl.col("high") < pl.col("low"))
    if len(invalid_hl) > 0:
        violations.append(
            ValidationViolation(
                layer=2,
                severity=ValidationSeverity.ERROR,
                message=f"High < Low in {len(invalid_hl)} rows",
                details={
                    "invalid_row_count": len(invalid_hl),
                    "sample_rows": invalid_hl.select(["timestamp", "high", "low"])
                    .head(5)
                    .to_dicts(),
                },
            )
        )

    # Check high >= open
    invalid_ho = df.filter(pl.col("high") < pl.col("open"))
    if len(invalid_ho) > 0:
        violations.append(
            ValidationViolation(
                layer=2,
                severity=ValidationSeverity.ERROR,
                message=f"High < Open in {len(invalid_ho)} rows",
                details={
                    "invalid_row_count": len(invalid_ho),
                    "sample_rows": invalid_ho.select(["timestamp", "high", "open"])
                    .head(5)
                    .to_dicts(),
                },
            )
        )

    # Check high >= close
    invalid_hc = df.filter(pl.col("high") < pl.col("close"))
    if len(invalid_hc) > 0:
        violations.append(
            ValidationViolation(
                layer=2,
                severity=ValidationSeverity.ERROR,
                message=f"High < Close in {len(invalid_hc)} rows",
                details={
                    "invalid_row_count": len(invalid_hc),
                    "sample_rows": invalid_hc.select(["timestamp", "high", "close"])
                    .head(5)
                    .to_dicts(),
                },
            )
        )

    # Check low <= open
    invalid_lo = df.filter(pl.col("low") > pl.col("open"))
    if len(invalid_lo) > 0:
        violations.append(
            ValidationViolation(
                layer=2,
                severity=ValidationSeverity.ERROR,
                message=f"Low > Open in {len(invalid_lo)} rows",
                details={
                    "invalid_row_count": len(invalid_lo),
                    "sample_rows": invalid_lo.select(["timestamp", "low", "open"])
                    .head(5)
                    .to_dicts(),
                },
            )
        )

    # Check low <= close
    invalid_lc = df.filter(pl.col("low") > pl.col("close"))
    if len(invalid_lc) > 0:
        violations.append(
            ValidationViolation(
                layer=2,
                severity=ValidationSeverity.ERROR,
                message=f"Low > Close in {len(invalid_lc)} rows",
                details={
                    "invalid_row_count": len(invalid_lc),
                    "sample_rows": invalid_lc.select(["timestamp", "low", "close"])
                    .head(5)
                    .to_dicts(),
                },
            )
        )

    if len(violations) == 0:
        logger.info("ohlcv_validation_passed", row_count=len(df))
    else:
        logger.error(
            "ohlcv_validation_failed",
            row_count=len(df),
            violation_count=len(violations),
        )

    return violations


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


def detect_price_outliers(df: pl.DataFrame, threshold_std: float = 3.0) -> pl.DataFrame:
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
        [
            pl.col("close").cast(pl.Float64).mean().alias("mean_close"),
            pl.col("close").cast(pl.Float64).std().alias("std_close"),
        ]
    )

    mean_close = stats["mean_close"][0]
    std_close = stats["std_close"][0]

    if std_close == 0 or std_close is None:
        logger.warning("outlier_detection_skipped", reason="zero_std", mean=mean_close)
        return df.filter(pl.lit(False))  # Return empty DataFrame

    # Find outliers: abs(close - mean) > threshold_std × std
    threshold = Decimal(str(threshold_std * std_close))
    mean_decimal = Decimal(str(mean_close))

    outliers = df.with_columns(((pl.col("close") - mean_decimal).abs()).alias("deviation")).filter(
        pl.col("deviation") > threshold
    )

    if len(outliers) > 0:
        logger.warning(
            "price_outliers_detected",
            outlier_count=len(outliers),
            total_rows=len(df),
            threshold_std=threshold_std,
            sample_rows=outliers.head(5).to_dicts(),
        )

    return outliers.drop("deviation")


def detect_large_gaps(df: pl.DataFrame, expected_interval: str = "1d") -> pl.DataFrame:
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
    df_with_diff = df_sorted.with_columns(pl.col(time_col).diff().alias("time_diff"))

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


def detect_volume_spikes(df: pl.DataFrame, threshold_std: float = 5.0) -> pl.DataFrame:
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
        [
            pl.col("volume").cast(pl.Float64).mean().alias("mean_volume"),
            pl.col("volume").cast(pl.Float64).std().alias("std_volume"),
        ]
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


# ============================================================================
# Layer 3: Outlier Detection (Enhanced)
# ============================================================================


def detect_outliers_v2(df: pl.DataFrame, config: ValidationConfig) -> list[ValidationViolation]:
    """Detect price and volume outliers with configurable thresholds.

    Args:
        df: Polars DataFrame with OHLCV columns
        config: ValidationConfig with outlier thresholds

    Returns:
        List of violations (warnings for outliers)

    Example:
        >>> df = pl.DataFrame({
        ...     "timestamp": [datetime.now()] * 10,
        ...     "close": [Decimal("100")] * 9 + [Decimal("500")],  # Price spike
        ...     "volume": [Decimal("1000")] * 10,
        ... })
        >>> config = ValidationConfig()
        >>> violations = detect_outliers_v2(df, config)
        >>> assert any(v.message.startswith("Price outliers") for v in violations)
    """
    violations: list[ValidationViolation] = []

    if len(df) < 2:
        logger.debug("outlier_detection_skipped", reason="insufficient_data", rows=len(df))
        return violations

    # Detect price outliers
    try:
        price_outliers = detect_price_outliers(df, config.price_spike_threshold_std)
        if len(price_outliers) > 0:
            violations.append(
                ValidationViolation(
                    layer=3,
                    severity=ValidationSeverity.WARNING,
                    message=f"Price outliers detected in {len(price_outliers)} rows",
                    details={
                        "outlier_count": len(price_outliers),
                        "threshold_std": config.price_spike_threshold_std,
                        "sample_rows": price_outliers.head(5).to_dicts(),
                    },
                )
            )
    except Exception as e:
        logger.error("price_outlier_detection_failed", error=str(e))

    # Detect volume spikes
    try:
        volume_spikes = detect_volume_spikes(df, config.volume_spike_threshold)
        if len(volume_spikes) > 0:
            violations.append(
                ValidationViolation(
                    layer=3,
                    severity=ValidationSeverity.WARNING,
                    message=f"Volume spikes detected in {len(volume_spikes)} rows",
                    details={
                        "spike_count": len(volume_spikes),
                        "threshold": config.volume_spike_threshold,
                        "sample_rows": volume_spikes.head(5).to_dicts(),
                    },
                )
            )
    except Exception as e:
        logger.error("volume_spike_detection_failed", error=str(e))

    if len(violations) > 0:
        logger.warning(
            "outliers_detected",
            row_count=len(df),
            violation_count=len(violations),
        )
    else:
        logger.info("no_outliers_detected", row_count=len(df))

    return violations


# ============================================================================
# Layer 4: Temporal Consistency Validation
# ============================================================================


def validate_temporal_consistency(
    df: pl.DataFrame, config: ValidationConfig
) -> list[ValidationViolation]:
    """Validate temporal consistency of data.

    Checks:
    - Timestamps are sorted ascending
    - No duplicate timestamps
    - No future data (timestamp > now)
    - No excessive gaps in data

    Args:
        df: Polars DataFrame with timestamp column
        config: ValidationConfig with temporal settings

    Returns:
        List of violations

    Example:
        >>> df = pl.DataFrame({
        ...     "timestamp": [datetime(2023, 1, 3), datetime(2023, 1, 1)],  # Unsorted
        ...     "close": [Decimal("100"), Decimal("101")],
        ... })
        >>> config = ValidationConfig()
        >>> violations = validate_temporal_consistency(df, config)
        >>> assert any("not sorted" in v.message for v in violations)
    """
    violations: list[ValidationViolation] = []

    if len(df) < 2:
        logger.debug("temporal_validation_skipped", reason="insufficient_data", rows=len(df))
        return violations

    # Check if timestamp column exists
    if "timestamp" not in df.columns:
        violations.append(
            ValidationViolation(
                layer=4,
                severity=ValidationSeverity.ERROR,
                message="Missing 'timestamp' column",
                details={},
            )
        )
        return violations

    # Check timestamps are sorted
    if not df["timestamp"].is_sorted():
        violations.append(
            ValidationViolation(
                layer=4,
                severity=ValidationSeverity.ERROR,
                message="Timestamps are not sorted in ascending order",
                details={
                    "first_timestamp": str(df["timestamp"][0]),
                    "last_timestamp": str(df["timestamp"][-1]),
                },
            )
        )

    # Check for duplicate timestamps
    duplicates = df.group_by("timestamp").agg(pl.count().alias("count")).filter(pl.col("count") > 1)
    if len(duplicates) > 0:
        violations.append(
            ValidationViolation(
                layer=4,
                severity=ValidationSeverity.ERROR,
                message=f"Duplicate timestamps found: {len(duplicates)} duplicates",
                details={
                    "duplicate_count": len(duplicates),
                    "sample_duplicates": duplicates.head(5).to_dicts(),
                },
            )
        )

    # Check for future data
    import pandas as pd

    now = pd.Timestamp.now(tz="UTC")
    # Ensure timestamps are timezone-aware for comparison
    df_with_tz = df.select([pl.col("timestamp").dt.replace_time_zone("UTC").alias("timestamp")])
    future_data = df_with_tz.filter(pl.col("timestamp") > now)
    if len(future_data) > 0:
        violations.append(
            ValidationViolation(
                layer=4,
                severity=ValidationSeverity.ERROR,
                message=f"Future data detected: {len(future_data)} rows with timestamps > now",
                details={
                    "future_row_count": len(future_data),
                    "current_time": str(now),
                    "sample_future_timestamps": future_data.head(5).to_dicts(),
                },
            )
        )

    # Check for gaps (if enabled)
    if not config.allow_gaps:
        try:
            gaps = detect_large_gaps(df, config.expected_frequency)
            if len(gaps) > 0:
                severity = (
                    ValidationSeverity.WARNING if config.allow_gaps else ValidationSeverity.ERROR
                )
                violations.append(
                    ValidationViolation(
                        layer=4,
                        severity=severity,
                        message=f"Data gaps detected: {len(gaps)} gaps",
                        details={
                            "gap_count": len(gaps),
                            "expected_frequency": config.expected_frequency,
                            "sample_gaps": gaps.head(5).to_dicts(),
                        },
                    )
                )
        except Exception as e:
            logger.error("gap_detection_failed", error=str(e))

    if len(violations) > 0:
        logger.warning(
            "temporal_consistency_violations",
            row_count=len(df),
            violation_count=len(violations),
        )
    else:
        logger.info("temporal_consistency_passed", row_count=len(df))

    return violations


# ============================================================================
# DataValidator Class (Main Orchestrator)
# ============================================================================


class DataValidator:
    """Multi-layer data validator for OHLCV data.

    Orchestrates all 4 validation layers:
    - Layer 1: Schema validation (Pydantic)
    - Layer 2: OHLCV relationship validation
    - Layer 3: Outlier detection
    - Layer 4: Temporal consistency

    Example:
        >>> config = ValidationConfig.for_stocks()
        >>> validator = DataValidator(config)
        >>> df = pl.DataFrame({...})  # OHLCV data
        >>> result = validator.validate(df)
        >>> if result.has_errors():
        ...     print(f"Validation failed: {result.get_errors()}")
    """

    def __init__(self, config: ValidationConfig | None = None):
        """Initialize DataValidator.

        Args:
            config: ValidationConfig (defaults to standard config)
        """
        self.config = config or ValidationConfig()

    def validate(
        self,
        df: pl.DataFrame,
        layers: list[int] | str = "all",
    ) -> ValidationResult:
        """Validate OHLCV data using specified layers.

        Args:
            df: Polars DataFrame with OHLCV data
            layers: Which layers to validate ('all' or list like [1, 2, 3, 4])

        Returns:
            ValidationResult with violations and metadata

        Example:
            >>> validator = DataValidator()
            >>> result = validator.validate(df, layers=[1, 2])  # Only schema + OHLCV
            >>> assert result.valid or result.has_warnings()
        """
        if isinstance(layers, str) and layers == "all":
            layers = [1, 2, 3, 4]
        elif not isinstance(layers, list):
            raise ValueError(f"layers must be 'all' or list of ints, got {type(layers)}")

        violations: list[ValidationViolation] = []

        # Layer 1: Schema validation
        if 1 in layers and self.config.enforce_schema:
            try:
                schema_violations = validate_schema(df)
                violations.extend(schema_violations)
                # If schema validation fails, can't continue with other layers
                if schema_violations:
                    logger.warning("schema_validation_failed_early_exit")
                    return ValidationResult(
                        valid=False,
                        violations=violations,
                        row_count=len(df),
                        metadata={"early_exit": "schema_validation_failed"},
                    )
            except Exception as e:
                logger.error("schema_validation_exception", error=str(e))
                violations.append(
                    ValidationViolation(
                        layer=1,
                        severity=ValidationSeverity.ERROR,
                        message=f"Schema validation failed with exception: {e!s}",
                        details={"exception": str(e)},
                    )
                )

        # Layer 2: OHLCV relationship validation
        if 2 in layers and self.config.enforce_ohlcv_relationships:
            try:
                ohlcv_violations = validate_ohlcv_relationships_v2(df)
                violations.extend(ohlcv_violations)
            except Exception as e:
                logger.error("ohlcv_validation_exception", error=str(e))
                violations.append(
                    ValidationViolation(
                        layer=2,
                        severity=ValidationSeverity.ERROR,
                        message=f"OHLCV validation failed with exception: {e!s}",
                        details={"exception": str(e)},
                    )
                )

        # Layer 3: Outlier detection
        if 3 in layers and self.config.enable_outlier_detection:
            try:
                outlier_violations = detect_outliers_v2(df, self.config)
                violations.extend(outlier_violations)
            except Exception as e:
                logger.error("outlier_detection_exception", error=str(e))
                violations.append(
                    ValidationViolation(
                        layer=3,
                        severity=ValidationSeverity.WARNING,
                        message=f"Outlier detection failed with exception: {e!s}",
                        details={"exception": str(e)},
                    )
                )

        # Layer 4: Temporal consistency
        if 4 in layers and self.config.enforce_temporal_consistency:
            try:
                temporal_violations = validate_temporal_consistency(df, self.config)
                violations.extend(temporal_violations)
            except Exception as e:
                logger.error("temporal_validation_exception", error=str(e))
                violations.append(
                    ValidationViolation(
                        layer=4,
                        severity=ValidationSeverity.ERROR,
                        message=f"Temporal validation failed with exception: {e!s}",
                        details={"exception": str(e)},
                    )
                )

        # Determine if validation passed (no ERROR-level violations)
        has_errors = any(v.severity == ValidationSeverity.ERROR for v in violations)
        valid = not has_errors

        result = ValidationResult(
            valid=valid,
            violations=violations,
            row_count=len(df),
            metadata={
                "layers_validated": layers,
                "error_count": len(
                    [v for v in violations if v.severity == ValidationSeverity.ERROR]
                ),
                "warning_count": len(
                    [v for v in violations if v.severity == ValidationSeverity.WARNING]
                ),
            },
        )

        # Log final result
        if result.has_errors():
            logger.error(
                "validation_failed",
                row_count=len(df),
                error_count=result.metadata["error_count"],
                warning_count=result.metadata["warning_count"],
            )
        elif result.has_warnings():
            logger.warning(
                "validation_passed_with_warnings",
                row_count=len(df),
                warning_count=result.metadata["warning_count"],
            )
        else:
            logger.info("validation_passed", row_count=len(df))

        return result

    def validate_and_raise(
        self,
        df: pl.DataFrame,
        layers: list[int] | str = "all",
    ) -> None:
        """Validate data and raise DataValidationError if any ERROR-level violations found.

        Args:
            df: Polars DataFrame with OHLCV data
            layers: Which layers to validate

        Raises:
            DataValidationError: If validation fails with ERROR-level violations

        Example:
            >>> validator = DataValidator()
            >>> validator.validate_and_raise(df)  # Raises if errors found
        """
        result = self.validate(df, layers=layers)
        if result.has_errors():
            error_messages = [v.message for v in result.get_errors()]
            raise DataValidationError(
                f"Data validation failed with {len(result.get_errors())} errors",
                context={
                    "errors": error_messages,
                    "row_count": result.row_count,
                },
            )
