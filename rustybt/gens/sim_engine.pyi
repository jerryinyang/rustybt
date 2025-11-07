"""Cython-optimized simulation clock for minute-level backtesting.

This module provides a high-performance clock generator that yields market
minutes and session boundaries for driving the simulation loop. Uses Cython
for minimal overhead in the critical simulation path.

Cython optimizations:
- Int64 nanosecond arithmetic for timestamps
- Pre-computed minute ranges per session
- Inline comparisons for event detection
- Generator implemented as C iterator

Example:
    >>> clock = MinuteSimulationClock(
    ...     sessions=trading_calendar.all_sessions,
    ...     market_opens=trading_calendar.opens,
    ...     market_closes=trading_calendar.closes,
    ...     before_trading_start_minutes=[...]
    ... )
    >>> for dt, event in clock:
    ...     if event == SESSION_START:
    ...         # Handle session start
    ...     elif event == BAR:
    ...         # Process minute bar
"""

from typing import Iterator
import pandas as pd

class MinuteSimulationClock:
    """Clock for minute-level simulation."""

    sessions: pd.DatetimeIndex
    opens: pd.DatetimeIndex
    closes: pd.DatetimeIndex

    def __init__(
        self,
        sessions: pd.DatetimeIndex,
        opens: pd.DatetimeIndex,
        closes: pd.DatetimeIndex,
        execution_opens: pd.DatetimeIndex | None = None,
        execution_closes: pd.DatetimeIndex | None = None,
        before_trading_start_minutes: list[pd.Timestamp] | None = None,
    ) -> None: ...

    def __iter__(self) -> Iterator[tuple[pd.Timestamp, str]]: ...
