"""Data quality metrics calculation for bundle validation."""

import time
from typing import Any

import pandas as pd
import polars as pl
from exchange_calendars import ExchangeCalendar

from rustybt.utils.gap_detection import (
    detect_missing_days,
    format_missing_days_list,
)


def calculate_quality_metrics(
    data: pl.DataFrame,
    calendar: ExchangeCalendar | None = None,
    date_column: str = "date",
) -> dict[str, Any]:
    """Calculate data quality metrics for bundle data.

    Args:
        data: DataFrame with OHLCV data
        calendar: Exchange calendar for gap detection (optional)
        date_column: Name of date column

    Returns:
        Dictionary with quality metrics:
            - row_count: Number of rows in data
            - start_date: First date timestamp
            - end_date: Last date timestamp
            - missing_days_count: Count of missing trading days (if calendar provided)
            - missing_days_list: JSON list of missing dates (if calendar provided)
            - outlier_count: Count of outlier rows
            - ohlcv_violations: Count of rows violating OHLCV relationships
            - validation_timestamp: Unix timestamp of validation
            - validation_passed: Boolean indicating if validation passed

    Raises:
        ValueError: If required columns are missing
    """
    required_cols = ["open", "high", "low", "close", "volume"]
    missing_cols = [col for col in required_cols if col not in data.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")

    # Handle case where date column is not found
    if date_column not in data.columns:
        # Try common alternative column names
        alternative_names = ["timestamp", "datetime", "Date", "Timestamp"]
        found_column = None

        for alt_name in alternative_names:
            if alt_name in data.columns:
                found_column = alt_name
                break

        if found_column:
            # Use the alternative column name
            date_column = found_column
        else:
            # Check if it's in the index (common after transformation)
            if hasattr(data, "index") and isinstance(data.index, (pd.DatetimeIndex, pd.Index)):
                # Reset index to make date a column for analysis
                data_with_date = data.reset_index()
                if "index" in data_with_date.columns:
                    data_with_date = data_with_date.rename(columns={"index": date_column})
                elif date_column in data_with_date.columns:
                    # Already has the right column name after reset_index
                    pass
                else:
                    raise ValueError(f"Date column '{date_column}' not found in data or index")
                data = data_with_date
            else:
                raise ValueError(f"Date column '{date_column}' not found in data")

    # Calculate row count
    row_count = len(data)

    # Calculate date range
    dates_series = (
        data[date_column].to_pandas()
        if hasattr(data[date_column], "to_pandas")
        else data[date_column]
    )
    if not isinstance(dates_series.iloc[0], pd.Timestamp):
        dates_series = pd.to_datetime(dates_series)

    start_date = dates_series.min()
    end_date = dates_series.max()

    # Calculate missing days if calendar provided
    missing_days_count = 0
    missing_days_list = "[]"
    if calendar is not None:
        missing_days = detect_missing_days(data, calendar, date_column)
        missing_days_count = len(missing_days)
        missing_days_list = format_missing_days_list(missing_days)

    # Detect outliers using IQR method
    outlier_count = _detect_outliers(data)

    # Validate OHLCV relationships
    ohlcv_violations = _validate_ohlcv_relationships(data)

    # Determine if validation passed
    validation_passed = ohlcv_violations == 0

    return {
        "row_count": row_count,
        "start_date": int(start_date.timestamp()),
        "end_date": int(end_date.timestamp()),
        "missing_days_count": missing_days_count,
        "missing_days_list": missing_days_list,
        "outlier_count": outlier_count,
        "ohlcv_violations": ohlcv_violations,
        "validation_timestamp": int(time.time()),
        "validation_passed": validation_passed,
    }


def _detect_outliers(data: pl.DataFrame) -> int:
    """Detect outliers using IQR method (values >3 IQR from quartiles).

    Args:
        data: DataFrame with OHLCV data

    Returns:
        Count of rows with outliers in any OHLCV column
    """
    outlier_count = 0

    # Check each price column
    for col in ["open", "high", "low", "close"]:
        if col not in data.columns:
            continue

        # Calculate quartiles and IQR
        q1 = data[col].quantile(0.25)
        q3 = data[col].quantile(0.75)
        iqr = q3 - q1

        # Define outlier bounds (3 * IQR)
        lower_bound = q1 - 3 * iqr
        upper_bound = q3 + 3 * iqr

        # Count outliers
        outliers = data.filter((pl.col(col) < lower_bound) | (pl.col(col) > upper_bound))
        outlier_count += len(outliers)

    return outlier_count


def _validate_ohlcv_relationships(data: pl.DataFrame) -> int:
    """Validate OHLCV relationship constraints.

    Validates:
    - high >= max(open, close)
    - low <= min(open, close)
    - high >= low
    - volume >= 0

    Args:
        data: DataFrame with OHLCV data

    Returns:
        Count of rows violating OHLCV relationships
    """
    # Check high >= max(open, close)
    invalid_high = data.filter(
        (pl.col("high") < pl.col("open")) | (pl.col("high") < pl.col("close"))
    )

    # Check low <= min(open, close)
    invalid_low = data.filter((pl.col("low") > pl.col("open")) | (pl.col("low") > pl.col("close")))

    # Check high >= low
    invalid_high_low = data.filter(pl.col("high") < pl.col("low"))

    # Check volume >= 0
    invalid_volume = data.filter(pl.col("volume") < 0) if "volume" in data.columns else []

    # Use set to avoid double-counting rows with multiple violations
    invalid_row_indices = set()
    invalid_row_indices.update(invalid_high.select(pl.int_range(pl.len())).to_series().to_list())
    invalid_row_indices.update(invalid_low.select(pl.int_range(pl.len())).to_series().to_list())
    invalid_row_indices.update(
        invalid_high_low.select(pl.int_range(pl.len())).to_series().to_list()
    )
    if len(invalid_volume) > 0:
        invalid_row_indices.update(
            invalid_volume.select(pl.int_range(pl.len())).to_series().to_list()
        )

    return len(invalid_row_indices)


def generate_quality_report(metrics: dict[str, Any]) -> str:
    """Generate human-readable quality report from metrics.

    Args:
        metrics: Quality metrics dictionary

    Returns:
        Formatted quality report string
    """
    start_date = pd.Timestamp(metrics["start_date"], unit="s").strftime("%Y-%m-%d")
    end_date = pd.Timestamp(metrics["end_date"], unit="s").strftime("%Y-%m-%d")
    validation_time = pd.Timestamp(metrics["validation_timestamp"], unit="s").strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    report = f"""
Data Quality Report
===================
Row Count: {metrics["row_count"]:,}
Date Range: {start_date} to {end_date}
Missing Trading Days: {metrics["missing_days_count"]}
Outliers Detected: {metrics["outlier_count"]}
OHLCV Violations: {metrics["ohlcv_violations"]}
Validation Status: {"PASSED" if metrics["validation_passed"] else "FAILED"}
Validated At: {validation_time}
"""

    if metrics["ohlcv_violations"] > 0:
        report += f"\nWARNING: {metrics['ohlcv_violations']} rows violate OHLCV relationships\n"

    if metrics["missing_days_count"] > 0:
        report += f"\nWARNING: {metrics['missing_days_count']} trading days missing from data\n"

    return report.strip()
