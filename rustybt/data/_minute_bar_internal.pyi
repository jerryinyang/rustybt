"""Cython-optimized minute bar indexing and lookups.

This module provides ultra-fast functions for converting between minute positions
and minute values in market data. Uses integer arithmetic for maximum speed.

Cython optimizations:
- C division/modulo operations (cdivision=True)
- Inline functions for position calculations
- Binary search via searchsorted
- No Python object creation in hot loops

Example:
    >>> # Convert position 450 to actual minute value
    >>> market_opens = np.array([...])  # Market open times
    >>> minute_val = minute_value(market_opens, pos=450, minutes_per_day=390)
"""

from typing import Any
import pandas as pd

def minute_value(
    column: Any, minute: pd.Timestamp, start: pd.Timestamp, end: pd.Timestamp
) -> Any: ...

def find_position_of_minute(
    market_open: pd.Timestamp,
    market_close: pd.Timestamp,
    minute: pd.Timestamp,
    minutes_per_day: int,
    forward_fill: bool = True,
) -> int: ...

def find_last_traded_position_internal(
    dts: list[pd.Timestamp],
    dt: pd.Timestamp,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> int: ...
