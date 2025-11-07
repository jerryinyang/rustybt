"""Date and time utilities for working with trading sessions.

This module provides utilities for working with date ranges and timezones
in the context of trading sessions:
- compute_date_range_chunks: Split date ranges into processable chunks
- make_utc_aware: Ensure DateTimeIndex has UTC timezone

These utilities are useful for processing large date ranges in smaller
chunks and ensuring consistent timezone handling across the system.

Examples:
    Compute date range chunks for processing:

    >>> import pandas as pd
    >>> sessions = pd.date_range('2020-01-01', '2020-01-10', freq='D')
    >>> chunks = list(compute_date_range_chunks(
    ...     sessions, pd.Timestamp('2020-01-01'), pd.Timestamp('2020-01-10'), 3
    ... ))
    >>> len(chunks)
    4

    Make a timezone-naive index UTC-aware:

    >>> import pandas as pd
    >>> naive = pd.date_range('2020-01-01', periods=3, freq='D')
    >>> aware = make_utc_aware(naive)
    >>> aware.tz
    <UTC>
"""

from toolz import partition_all


def compute_date_range_chunks(sessions, start_date, end_date, chunksize):
    """Compute date range chunks for processing pipelines or backtests.

    This function splits a date range into smaller chunks for efficient
    processing. It's useful when you need to process data in batches
    rather than all at once.

    Args:
        sessions: The available trading dates as a DatetimeIndex.
            Must contain both start_date and end_date.
        start_date: The first date in the range to process.
        end_date: The last date in the range to process (inclusive).
        chunksize: The maximum number of sessions per chunk. If None,
            returns a single chunk containing the entire range.

    Returns:
        An iterable of (start, end) timestamp tuples, where each tuple
        represents a chunk of sessions to process.

    Raises:
        KeyError: If start_date or end_date is not in sessions.
        ValueError: If end_date precedes start_date.

    Examples:
        Basic chunking with a chunksize:

        >>> import pandas as pd
        >>> sessions = pd.date_range('2020-01-01', '2020-01-10', freq='D')
        >>> chunks = list(compute_date_range_chunks(
        ...     sessions,
        ...     pd.Timestamp('2020-01-01'),
        ...     pd.Timestamp('2020-01-10'),
        ...     chunksize=3
        ... ))
        >>> len(chunks)
        4
        >>> chunks[0]  # doctest: +SKIP
        (Timestamp('2020-01-01'), Timestamp('2020-01-03'))

        Without chunking (chunksize=None):

        >>> chunks = list(compute_date_range_chunks(
        ...     sessions,
        ...     pd.Timestamp('2020-01-01'),
        ...     pd.Timestamp('2020-01-05'),
        ...     chunksize=None
        ... ))
        >>> len(chunks)
        1
        >>> chunks[0]  # doctest: +SKIP
        (Timestamp('2020-01-01'), Timestamp('2020-01-05'))
    """
    if start_date not in sessions:
        raise KeyError(
            "Start date %s is not found in calendar." % (start_date.strftime("%Y-%m-%d"),)
        )
    if end_date not in sessions:
        raise KeyError("End date %s is not found in calendar." % (end_date.strftime("%Y-%m-%d"),))
    if end_date < start_date:
        raise ValueError(
            "End date %s cannot precede start date %s."
            % (end_date.strftime("%Y-%m-%d"), start_date.strftime("%Y-%m-%d"))
        )

    if chunksize is None:
        return [(start_date, end_date)]

    start_ix, end_ix = sessions.slice_locs(start_date, end_date)
    return ((r[0], r[-1]) for r in partition_all(chunksize, sessions[start_ix:end_ix]))


def make_utc_aware(dti):
    """Normalize a DateTimeIndex to be UTC-aware.

    This function ensures that a DateTimeIndex has UTC timezone information.
    If the input is already timezone-aware, it converts to UTC. If the input
    is timezone-naive, it localizes to UTC (interpreting times as UTC).

    Args:
        dti: A pandas DateTimeIndex that may be timezone-aware or naive.

    Returns:
        pd.DatetimeIndex: A DateTimeIndex with UTC timezone.

    Examples:
        Localize a timezone-naive index:

        >>> import pandas as pd
        >>> naive = pd.DatetimeIndex(['2020-01-01', '2020-01-02'])
        >>> aware = make_utc_aware(naive)
        >>> aware.tz
        <UTC>

        Convert a timezone-aware index to UTC:

        >>> import pytz
        >>> eastern = pd.DatetimeIndex(
        ...     ['2020-01-01 09:30:00'], tz=pytz.timezone('US/Eastern')
        ... )
        >>> utc = make_utc_aware(eastern)
        >>> utc.tz
        <UTC>
        >>> utc[0].hour
        14

    Note:
        - For timezone-naive inputs, times are interpreted as being in UTC.
        - For timezone-aware inputs, times are converted to UTC.
    """
    try:
        # ensure tz-aware Timestamp has tz UTC
        return dti.tz_convert(tz="UTC")
    except TypeError:
        # if naive, instead convert timestamp to UTC
        return dti.tz_localize(tz="UTC")
