"""Gap detection utilities for identifying missing trading days."""

import json

import pandas as pd
import polars as pl
from exchange_calendars import ExchangeCalendar


def detect_missing_days(
    data: pl.DataFrame, calendar: ExchangeCalendar, date_column: str = "date"
) -> list[pd.Timestamp]:
    """Detect missing trading days in data using exchange calendar.

    Args:
        data: DataFrame containing date column
        calendar: Exchange calendar to use for expected trading days
        date_column: Name of the date column in data

    Returns:
        List of missing trading day timestamps

    Raises:
        ValueError: If date column not found in data
    """
    if date_column not in data.columns:
        raise ValueError(f"Date column '{date_column}' not found in data")

    if len(data) == 0:
        return []

    # Convert Polars to pandas for calendar compatibility
    dates_series = data[date_column].to_pandas()

    # Ensure dates are timestamps
    if not isinstance(dates_series.iloc[0], pd.Timestamp):
        dates_series = pd.to_datetime(dates_series)

    # Get date range
    start_date = dates_series.min()
    end_date = dates_series.max()

    # Get expected trading sessions from calendar
    expected_sessions = calendar.sessions_in_range(start_date, end_date)

    # Convert actual dates to set for fast lookup
    actual_dates_set = set(pd.to_datetime(dates_series.dt.date))

    # Find missing dates
    missing_dates = []
    for session in expected_sessions:
        session_date = pd.Timestamp(session.date())
        if session_date not in actual_dates_set:
            missing_dates.append(session_date)

    return missing_dates


def detect_missing_days_count(
    data: pl.DataFrame, calendar: ExchangeCalendar, date_column: str = "date"
) -> int:
    """Count missing trading days in data.

    Args:
        data: DataFrame containing date column
        calendar: Exchange calendar to use for expected trading days
        date_column: Name of the date column in data

    Returns:
        Count of missing trading days
    """
    missing_days = detect_missing_days(data, calendar, date_column)
    return len(missing_days)


def format_missing_days_list(missing_days: list[pd.Timestamp]) -> str:
    """Format missing days list as JSON string.

    Args:
        missing_days: List of missing day timestamps

    Returns:
        JSON array string of dates in YYYY-MM-DD format
    """
    if not missing_days:
        return "[]"

    date_strings = [day.strftime("%Y-%m-%d") for day in missing_days]
    return json.dumps(date_strings)


def parse_missing_days_list(missing_days_json: str | None) -> list[pd.Timestamp]:
    """Parse missing days JSON string into list of timestamps.

    Args:
        missing_days_json: JSON array string of dates

    Returns:
        List of missing day timestamps
    """
    if not missing_days_json or missing_days_json == "[]":
        return []

    date_strings = json.loads(missing_days_json)
    return [pd.Timestamp(date_str) for date_str in date_strings]


def generate_gap_report(missing_days: list[pd.Timestamp], threshold: int = 5) -> dict[str, any]:
    """Generate gap report showing missing date ranges and warnings.

    Args:
        missing_days: List of missing day timestamps
        threshold: Number of consecutive days to trigger warning

    Returns:
        Dictionary with gap analysis:
            - total_gaps: Total number of missing days
            - gap_ranges: List of (start, end, count) tuples for consecutive gaps
            - warnings: List of warnings for gaps exceeding threshold
    """
    if not missing_days:
        return {"total_gaps": 0, "gap_ranges": [], "warnings": []}

    sorted_days = sorted(missing_days)
    gap_ranges = []
    warnings = []

    # Find consecutive ranges
    current_start = sorted_days[0]
    current_end = sorted_days[0]
    current_count = 1

    for i in range(1, len(sorted_days)):
        days_diff = (sorted_days[i] - current_end).days
        if days_diff == 1:
            # Consecutive day
            current_end = sorted_days[i]
            current_count += 1
        else:
            # Gap in sequence, save current range
            gap_ranges.append((current_start, current_end, current_count))

            if current_count > threshold:
                warnings.append(
                    f"Gap of {current_count} consecutive days from "
                    f"{current_start.strftime('%Y-%m-%d')} to "
                    f"{current_end.strftime('%Y-%m-%d')}"
                )

            # Start new range
            current_start = sorted_days[i]
            current_end = sorted_days[i]
            current_count = 1

    # Add final range
    gap_ranges.append((current_start, current_end, current_count))
    if current_count > threshold:
        warnings.append(
            f"Gap of {current_count} consecutive days from "
            f"{current_start.strftime('%Y-%m-%d')} to "
            f"{current_end.strftime('%Y-%m-%d')}"
        )

    return {
        "total_gaps": len(missing_days),
        "gap_ranges": gap_ranges,
        "warnings": warnings,
    }
