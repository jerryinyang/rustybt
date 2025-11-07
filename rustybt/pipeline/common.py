"""Common constants and field names used across the Pipeline API.

This module defines standardized field names used in pipeline computations,
particularly for event-driven data and fundamental datasets. These constants
ensure consistency when accessing event data, timestamps, and fundamental
attributes across different data sources.

Field Name Categories:
    - **Event Fields**: Fields related to corporate events and announcements
    - **Temporal Fields**: Date and timestamp fields
    - **Identity Fields**: Asset identification fields
    - **Fundamental Fields**: Financial statement fields

Constants:
    Event-Related Fields:
        - ANNOUNCEMENT_FIELD_NAME: Date when an event was announced
        - EVENT_DATE_FIELD_NAME: Actual date of the event
        - NEXT_ANNOUNCEMENT: Next scheduled announcement
        - PREVIOUS_ANNOUNCEMENT: Previous announcement
        - DAYS_SINCE_PREV: Days elapsed since previous event
        - DAYS_TO_NEXT: Days until next event

    Financial Fields:
        - FISCAL_QUARTER_FIELD_NAME: Fiscal quarter identifier
        - FISCAL_YEAR_FIELD_NAME: Fiscal year identifier
        - CASH_FIELD_NAME: Cash and cash equivalents
        - PREVIOUS_AMOUNT: Previous period amount

    Core Fields:
        - SID_FIELD_NAME: Security identifier (sid)
        - TS_FIELD_NAME: Timestamp
        - AD_FIELD_NAME: As-of date

Usage:
    >>> from rustybt.pipeline.common import ANNOUNCEMENT_FIELD_NAME, SID_FIELD_NAME
    >>> # These constants are used when defining custom loaders or datasets
    >>> print(ANNOUNCEMENT_FIELD_NAME)
    'announcement_date'
"""

AD_FIELD_NAME = "asof_date"
ANNOUNCEMENT_FIELD_NAME = "announcement_date"
CASH_FIELD_NAME = "cash"
DAYS_SINCE_PREV = "days_since_prev"
DAYS_TO_NEXT = "days_to_next"
FISCAL_QUARTER_FIELD_NAME = "fiscal_quarter"
FISCAL_YEAR_FIELD_NAME = "fiscal_year"
NEXT_ANNOUNCEMENT = "next_announcement"
PREVIOUS_AMOUNT = "previous_amount"
PREVIOUS_ANNOUNCEMENT = "previous_announcement"

EVENT_DATE_FIELD_NAME = "event_date"
SID_FIELD_NAME = "sid"
TS_FIELD_NAME = "timestamp"
