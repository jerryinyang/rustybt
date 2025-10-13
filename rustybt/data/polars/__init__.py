"""Polars-based data layer for RustyBT.

This package provides Decimal-precision data handling using Polars DataFrames
and Parquet storage format.
"""

from rustybt.data.polars.aggregation import (
    AggregationError,
    resample_custom_interval,
    resample_daily_to_monthly,
    resample_daily_to_weekly,
    resample_minute_to_daily,
)
from rustybt.data.polars.parquet_daily_bars import PolarsParquetDailyReader
from rustybt.data.polars.parquet_minute_bars import PolarsParquetMinuteReader
from rustybt.data.polars.parquet_schema import (
    ADJUSTMENTS_SCHEMA,
    DAILY_BARS_SCHEMA,
    MINUTE_BARS_SCHEMA,
    get_schema_for_frequency,
    validate_schema,
)
from rustybt.data.polars.validation import (
    DataError,
    ValidationError,
    detect_large_gaps,
    detect_price_outliers,
    detect_volume_spikes,
    generate_data_quality_report,
    validate_ohlcv_relationships,
)

__all__ = [
    # Schemas
    "DAILY_BARS_SCHEMA",
    "MINUTE_BARS_SCHEMA",
    "ADJUSTMENTS_SCHEMA",
    "get_schema_for_frequency",
    "validate_schema",
    # Validation
    "DataError",
    "ValidationError",
    "validate_ohlcv_relationships",
    "detect_price_outliers",
    "detect_large_gaps",
    "detect_volume_spikes",
    "generate_data_quality_report",
    # Aggregation
    "AggregationError",
    "resample_minute_to_daily",
    "resample_daily_to_weekly",
    "resample_daily_to_monthly",
    "resample_custom_interval",
    # Readers
    "PolarsParquetDailyReader",
    "PolarsParquetMinuteReader",
]
