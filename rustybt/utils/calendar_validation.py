"""Calendar-aware date validation utilities.

Ensures robust handling of date ranges across different asset types and their
corresponding trading calendars.
"""

import pandas as pd
import structlog
from exchange_calendars import get_calendar

logger = structlog.get_logger(__name__)


def get_calendar_for_asset_type(asset_type: str | None) -> str:
    """Get appropriate calendar name for asset type.

    Args:
        asset_type: Asset type ('forex', 'crypto', 'equity', 'future', or None)

    Returns:
        Calendar name for exchange_calendars

    Example:
        >>> get_calendar_for_asset_type("forex")
        '24/5'
    """
    if asset_type == "forex":
        return "24/5"
    elif asset_type == "crypto":
        return "24/7"
    else:
        # equity, future, unknown, None
        return "XNYS"


def validate_and_adjust_date_range(
    start: pd.Timestamp,
    end: pd.Timestamp,
    calendar_name: str,
    context: str = "operation",
) -> tuple[pd.Timestamp, pd.Timestamp, bool]:
    """Validate and adjust date range to calendar boundaries.

    Automatically adjusts dates that fall outside calendar's valid range,
    logging warnings to inform the user.

    Args:
        start: Requested start date
        end: Requested end date
        calendar_name: Trading calendar name (e.g., "24/5", "XNYS")
        context: Description of operation for logging (e.g., "ingestion", "backtest")

    Returns:
        Tuple of (adjusted_start, adjusted_end, was_adjusted)

    Raises:
        ValueError: If adjusted range is invalid or empty

    Example:
        >>> start = pd.Timestamp("2000-01-01")
        >>> end = pd.Timestamp("2024-01-01")
        >>> adjusted_start, adjusted_end, changed = validate_and_adjust_date_range(
        ...     start, end, "24/5", "ingestion"
        ... )
        >>> # Returns (Timestamp('2005-10-28'), Timestamp('2024-01-01'), True)
    """
    calendar = get_calendar(calendar_name)

    # Get calendar's valid session range
    first_session = calendar.first_session
    last_session = calendar.last_session

    adjusted_start = start
    adjusted_end = end
    was_adjusted = False

    # Check if start is before calendar's first session
    if start < first_session:
        logger.warning(
            "date_adjusted_to_calendar_start",
            context=context,
            requested_start=str(start),
            calendar_first_session=str(first_session),
            calendar=calendar_name,
            message=f"Requested start date {start.date()} is before calendar's first session. "
            f"Adjusting to {first_session.date()}",
        )
        adjusted_start = first_session
        was_adjusted = True

    # Check if end is after calendar's last session
    if end > last_session:
        logger.warning(
            "date_adjusted_to_calendar_end",
            context=context,
            requested_end=str(end),
            calendar_last_session=str(last_session),
            calendar=calendar_name,
            message=f"Requested end date {end.date()} is after calendar's last session. "
            f"Adjusting to {last_session.date()}",
        )
        adjusted_end = last_session
        was_adjusted = True

    # Validate adjusted range
    if adjusted_start > adjusted_end:
        raise ValueError(
            f"Invalid date range after adjustment: start {adjusted_start.date()} > "
            f"end {adjusted_end.date()}. Calendar: {calendar_name}, "
            f"valid range: {first_session.date()} to {last_session.date()}"
        )

    # Check if there are any trading sessions in the range
    sessions = calendar.sessions_in_range(adjusted_start, adjusted_end)
    if len(sessions) == 0:
        raise ValueError(
            f"No trading sessions found in date range {adjusted_start.date()} to "
            f"{adjusted_end.date()} for calendar '{calendar_name}'. "
            f"Calendar valid range: {first_session.date()} to {last_session.date()}"
        )

    if was_adjusted:
        logger.info(
            "date_range_adjusted",
            context=context,
            original_start=str(start),
            original_end=str(end),
            adjusted_start=str(adjusted_start),
            adjusted_end=str(adjusted_end),
            calendar=calendar_name,
            sessions_count=len(sessions),
        )

    return adjusted_start, adjusted_end, was_adjusted


def validate_backtest_dates(
    start: pd.Timestamp,
    end: pd.Timestamp,
    bundle_start: pd.Timestamp,
    bundle_end: pd.Timestamp,
    bundle_name: str,
    calendar_name: str,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Validate and adjust backtest dates to valid trading sessions.

    Ensures backtest dates are within both the bundle's data range and the
    calendar's valid range. Automatically adjusts dates to the nearest valid
    trading sessions if the requested dates fall on non-trading days.

    **Changed**: Now gracefully adjusts dates that fall outside the bundle's data range
    instead of raising an error. This allows backtests to start before the bundle's
    first available date (will auto-adjust to first available date) or end after the
    bundle's last available date (will auto-adjust to last available date).

    Args:
        start: Requested backtest start date
        end: Requested backtest end date
        bundle_start: Bundle's actual data start date
        bundle_end: Bundle's actual data end date
        bundle_name: Bundle name for error messages
        calendar_name: Trading calendar name

    Returns:
        Tuple of (adjusted_start, adjusted_end) where both are valid trading sessions

    Raises:
        ValueError: If adjusted date range is invalid or calendar range errors occur

    Example:
        >>> start = pd.Timestamp("2020-01-01")  # New Year's Day (holiday)
        >>> end = pd.Timestamp("2024-01-01")
        >>> bundle_start = pd.Timestamp("2010-01-01")
        >>> bundle_end = pd.Timestamp("2023-12-31")
        >>> validated_start, validated_end = validate_backtest_dates(
        ...     start, end, bundle_start, bundle_end, "forex-1d", "24/5"
        ... )
        >>> # Returns next/previous valid trading sessions
    """
    # Gracefully adjust dates to bundle's data range (instead of raising errors)
    adjusted_start = start
    adjusted_end = end

    if start < bundle_start:
        logger.warning(
            "backtest_start_before_bundle",
            requested_start=str(start.date()),
            bundle_start=str(bundle_start.date()),
            bundle_name=bundle_name,
            message=f"Backtest start date {start.date()} is before bundle's first available data. "
            f"Auto-adjusting to bundle start: {bundle_start.date()}",
        )
        adjusted_start = bundle_start

    if end > bundle_end:
        logger.warning(
            "backtest_end_after_bundle",
            requested_end=str(end.date()),
            bundle_end=str(bundle_end.date()),
            bundle_name=bundle_name,
            message=f"Backtest end date {end.date()} is after bundle's last available data. "
            f"Auto-adjusting to bundle end: {bundle_end.date()}",
        )
        adjusted_end = bundle_end

    # Validate that we still have a valid range after adjustment
    if adjusted_start > adjusted_end:
        raise ValueError(
            f"Invalid date range after adjustment: start {adjusted_start.date()} > end {adjusted_end.date()}. "
            f"Bundle '{bundle_name}' has data from {bundle_start.date()} to {bundle_end.date()}"
        )

    # Validate against calendar range and gracefully adjust if needed
    calendar = get_calendar(calendar_name)
    first_session = calendar.first_session
    last_session = calendar.last_session

    # Gracefully adjust to calendar boundaries (instead of raising errors)
    if adjusted_start < first_session:
        logger.warning(
            "backtest_start_before_calendar",
            requested_start=str(adjusted_start.date()),
            calendar_first=str(first_session.date()),
            calendar_name=calendar_name,
            message=f"Adjusted backtest start {adjusted_start.date()} is before calendar's first session. "
            f"Auto-adjusting to calendar start: {first_session.date()}",
        )
        adjusted_start = first_session

    if adjusted_end > last_session:
        logger.warning(
            "backtest_end_after_calendar",
            requested_end=str(adjusted_end.date()),
            calendar_last=str(last_session.date()),
            calendar_name=calendar_name,
            message=f"Adjusted backtest end {adjusted_end.date()} is after calendar's last session. "
            f"Auto-adjusting to calendar end: {last_session.date()}",
        )
        adjusted_end = last_session

    # Get all valid trading sessions in the calendar's range
    sessions = calendar.sessions_in_range(first_session, last_session)

    # Adjust start date to nearest valid session on or after adjusted_start
    if adjusted_start not in sessions:
        # Find the next valid session
        future_sessions = sessions[sessions >= adjusted_start]
        if len(future_sessions) == 0:
            raise ValueError(
                f"No valid trading sessions found on or after {adjusted_start.date()} "
                f"for calendar '{calendar_name}'"
            )
        adjusted_start = future_sessions[0]
        logger.warning(
            "backtest_start_adjusted_to_session",
            requested_start=str(start.date()),
            adjusted_start=str(adjusted_start.date()),
            calendar=calendar_name,
            message=f"Start date {adjusted_start.date()} is not a valid trading session. "
            f"Adjusted to next valid session: {adjusted_start.date()}",
        )

    # Adjust end date to nearest valid session on or before adjusted_end
    if adjusted_end not in sessions:
        # Find the previous valid session
        past_sessions = sessions[sessions <= adjusted_end]
        if len(past_sessions) == 0:
            raise ValueError(
                f"No valid trading sessions found on or before {adjusted_end.date()} "
                f"for calendar '{calendar_name}'"
            )
        adjusted_end = past_sessions[-1]
        logger.warning(
            "backtest_end_adjusted_to_session",
            requested_end=str(end.date()),
            adjusted_end=str(adjusted_end.date()),
            calendar=calendar_name,
            message=f"End date {adjusted_end.date()} is not a valid trading session. "
            f"Adjusted to previous valid session: {adjusted_end.date()}",
        )

    # Verify we have at least one trading day in the adjusted range
    if adjusted_start > adjusted_end:
        raise ValueError(
            f"No valid trading sessions between {start.date()} and {end.date()} "
            f"for calendar '{calendar_name}'"
        )

    # Log summary if any adjustments were made
    if adjusted_start != start or adjusted_end != end:
        logger.info(
            "backtest_dates_adjusted",
            original_start=str(start),
            original_end=str(end),
            adjusted_start=str(adjusted_start),
            adjusted_end=str(adjusted_end),
            calendar=calendar_name,
        )

    return adjusted_start, adjusted_end
