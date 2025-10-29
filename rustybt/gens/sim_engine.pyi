"""Type stubs for rustybt.gens.sim_engine - Compiled Cython module."""

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
