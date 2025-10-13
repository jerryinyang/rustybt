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
    def wrapper(func):
        func.__signature__ = signature
        return func

    return wrapper


@wrap_with_signature(inspect.signature(ec_get_calendar))
def get_calendar(*args, **kwargs):
    if args[0] in ["us_futures", "CMES", "XNYS", "NYSE"]:
        return ec_get_calendar(*args, side="right", start=pd.Timestamp("1990-01-01"))
    return ec_get_calendar(*args, side="right")


# get_calendar = compose(partial(get_calendar, side="right"), "XNYS")
# NOTE Sessions are now timezone-naive (previously UTC).
# Schedule columns now have timezone set as UTC
# (whilst the times have always been defined in terms of UTC,
# previously the dtype was timezone-naive).
