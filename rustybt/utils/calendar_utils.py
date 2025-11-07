"""Calendar utilities for working with trading calendars.

This module provides utilities for working with exchange calendars, including:
- get_calendar: Get a trading calendar with rustybt-specific defaults
- TradingCalendar: Backward compatibility alias for ExchangeCalendar
- Re-exported utilities from exchange_calendars for convenience

The module wraps the exchange_calendars library and provides sensible
defaults for common calendars used in backtesting and trading.

Examples:
    Get a US futures calendar:

    >>> from rustybt.utils.calendar_utils import get_calendar
    >>> calendar = get_calendar('us_futures')
    >>> calendar.name
    'us_futures'

    Get the NYSE calendar:

    >>> nyse = get_calendar('XNYS')
    >>> sessions = nyse.sessions
"""

import inspect

import pandas as pd
from exchange_calendars import ExchangeCalendar
from exchange_calendars import get_calendar as ec_get_calendar
from exchange_calendars.calendar_utils import (  # noqa: F401
    global_calendar_dispatcher,
    register_calendar_alias,
)
from exchange_calendars.utils.pandas_utils import days_at_time  # noqa: F401

# from exchange_calendars.errors import InvalidCalendarName

# Backward compatibility alias
TradingCalendar = ExchangeCalendar


# https://stackoverflow.com/questions/56753846/python-wrapping-function-with-signature
def wrap_with_signature(signature):
    """Decorator to preserve the signature of a wrapped function.

    Args:
        signature: The signature object to apply to the wrapped function.

    Returns:
        A decorator function that sets the signature on the wrapped function.

    Examples:
        >>> import inspect
        >>> def original(a, b, c=1): pass
        >>> @wrap_with_signature(inspect.signature(original))
        ... def wrapper(*args, **kwargs):
        ...     return original(*args, **kwargs)
        >>> str(inspect.signature(wrapper))
        '(a, b, c=1)'
    """
    def wrapper(func):
        func.__signature__ = signature
        return func

    return wrapper


@wrap_with_signature(inspect.signature(ec_get_calendar))
def get_calendar(*args, **kwargs):
    """Get a trading calendar with rustybt-specific defaults.

    This is a wrapper around exchange_calendars.get_calendar that applies
    rustybt-specific defaults for common calendars. Specifically:
    - Sets side='right' for all calendars (midnight is at end of day)
    - For us_futures, CMES, XNYS, and NYSE: sets start date to 1990-01-01

    Args:
        *args: Positional arguments passed to exchange_calendars.get_calendar.
            The first argument should be the calendar name/code.
        **kwargs: Keyword arguments passed to exchange_calendars.get_calendar.

    Returns:
        ExchangeCalendar: A trading calendar instance.

    Examples:
        Get a US futures calendar with extended history:

        >>> calendar = get_calendar('us_futures')
        >>> calendar.name
        'us_futures'

        Get the NYSE calendar:

        >>> nyse = get_calendar('XNYS')
        >>> sessions = nyse.sessions
        >>> len(sessions) > 1000
        True

        Get a calendar with custom parameters:

        >>> import pandas as pd
        >>> cal = get_calendar('NYSE', start=pd.Timestamp('2020-01-01'))

    Note:
        Sessions are now timezone-naive (previously UTC).
        Schedule columns have timezone set as UTC.
    """
    if args[0] in ["us_futures", "CMES", "XNYS", "NYSE"]:
        return ec_get_calendar(*args, side="right", start=pd.Timestamp("1990-01-01"))
    return ec_get_calendar(*args, side="right")


# get_calendar = compose(partial(get_calendar, side="right"), "XNYS")
# NOTE Sessions are now timezone-naive (previously UTC).
# Schedule columns now have timezone set as UTC
# (whilst the times have always been defined in terms of UTC,
# previously the dtype was timezone-naive).
