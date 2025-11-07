"""Cython-optimized minute-to-session OHLCV resampling.

This module provides highly optimized functions for aggregating minute-level
OHLCV data into session-level (daily) bars. Critical for performance when
working with minute data.

Cython optimizations:
- Inline C loops for aggregation (no Python overhead)
- Direct memoryview access to NumPy arrays
- Specialized functions for each OHLCV field
- NaN handling without Python exceptions

Example:
    >>> # Aggregate minute data to daily
    >>> close_locs = np.array([389, 779, 1169])  # Minute 389, 779, 1169
    >>> minute_closes = np.array([...])  # All minute closes
    >>> daily_closes = np.empty(3)
    >>> _minute_to_session_close(close_locs, minute_closes, daily_closes)
"""

import numpy as np
import pandas as pd

def _minute_to_session_open(
    columns: list[str],
    close_locs: np.ndarray,
    data: np.ndarray,
    out: np.ndarray,
) -> None: ...

def _minute_to_session_high(
    columns: list[str],
    close_locs: np.ndarray,
    data: np.ndarray,
    out: np.ndarray,
) -> None: ...

def _minute_to_session_low(
    columns: list[str],
    close_locs: np.ndarray,
    data: np.ndarray,
    out: np.ndarray,
) -> None: ...

def _minute_to_session_close(
    columns: list[str],
    close_locs: np.ndarray,
    data: np.ndarray,
    out: np.ndarray,
) -> None: ...

def _minute_to_session_volume(
    columns: list[str],
    close_locs: np.ndarray,
    data: np.ndarray,
    out: np.ndarray,
) -> None: ...
