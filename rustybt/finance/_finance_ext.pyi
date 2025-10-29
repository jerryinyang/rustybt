"""Type stubs for rustybt.finance._finance_ext - Compiled Cython module."""

from typing import Any, Callable
import numpy as np
import pandas as pd

def update_position_last_sale_prices(
    positions: dict[Any, Any], get_price: Callable[[Any, pd.Timestamp], float], dt: pd.Timestamp
) -> None: ...

class PositionStats:
    """Container for position statistics."""

    net_value: float
    gross_value: float
    short_value: float
    long_value: float
    net_exposure: float
    short_exposure: float
    long_exposure: float
    shorts_count: int
    longs_count: int

    def __init__(
        self,
        net_value: float = 0.0,
        gross_value: float = 0.0,
        short_value: float = 0.0,
        long_value: float = 0.0,
        net_exposure: float = 0.0,
        short_exposure: float = 0.0,
        long_exposure: float = 0.0,
        shorts_count: int = 0,
        longs_count: int = 0,
    ) -> None: ...

def calculate_position_tracker_stats(positions: dict[Any, Any], stats: PositionStats) -> None: ...

def minute_annual_volatility(
    date_labels: np.ndarray, close: np.ndarray, dates: pd.DatetimeIndex, min_date_index: int
) -> np.ndarray: ...
