"""Cython-optimized bcolz data loading for equity OHLCV data.

This module provides high-performance functions for loading equity price/volume
data from bcolz tables. Critical for fast data access during backtesting.

Cython optimizations:
- Inline slice calculations avoiding Python overhead
- Direct memoryview access to bcolz arrays
- Batch loading with minimal array copies
- Efficient NaN handling for missing data

Example:
    >>> # Load data for multiple assets across a date range
    >>> first_rows, last_rows, offsets = _compute_row_slices(
    ...     asset_starts, asset_ends, asset_cal_starts,
    ...     query_start=0, query_end=100,
    ...     assets=pd.Int64Index([1, 2, 3])
    ... )
"""

from typing import Any
import numpy as np

def _compute_row_slices(dates: np.ndarray) -> list[tuple[int, int]]: ...

def _read_bcolz_data(
    table: Any, shape: tuple[int, int], columns: list[str], dtype: Any
) -> dict[str, np.ndarray]: ...
