"""Cython-optimized ranking functions for factor analysis.

This module provides high-performance ranking operations optimized for
quantitative finance applications, including masked ranking and grouped
ranking operations.

Cython optimizations:
- Fast 2D ranking via mergesort and inline loops
- Efficient NaN/missing value handling
- Optimized grouped operations with dict lookups
- Boundscheck/wraparound disabled for maximum speed

Example:
    >>> # Rank a 2D array (rows=dates, cols=assets)
    >>> data = np.random.randn(100, 500)  # 100 days, 500 assets
    >>> mask = ~np.isnan(data)
    >>> ranks = masked_rankdata_2d(data, mask, np.nan, 'ordinal', True)
"""

import numpy as np

def rankdata_1d_descending(data: np.ndarray) -> np.ndarray: ...

def masked_rankdata_2d(
    data: np.ndarray, mask: np.ndarray, missing_value: float, ascending: bool, method: str
) -> np.ndarray: ...

def rankdata_2d_ordinal(data: np.ndarray, missing_value: float, ascending: bool) -> np.ndarray: ...

def grouped_masked_is_maximal(
    data: np.ndarray, groupby: np.ndarray, mask: np.ndarray, missing_value: float
) -> np.ndarray: ...
