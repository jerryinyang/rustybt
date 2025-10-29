"""Type stubs for rustybt.data._minute_bar_internal - Compiled Cython module."""

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
