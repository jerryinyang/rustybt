"""Cython-optimized sliding window for float64 data with adjustments.

This module provides a high-performance sliding window iterator over float64
arrays that applies corporate action adjustments as it moves forward. Used
for historical data access in Pipeline and factor computations.

Cython optimizations:
- Direct memoryview access to underlying data
- Inline adjustment application
- No array copies during iteration
- Read-only views returned to prevent mutation

Example:
    >>> window = AdjustedArrayWindow(
    ...     data=price_data,
    ...     adjustments={100: [split_adj], 200: [dividend_adj]},
    ...     offset=0,
    ...     window_length=30
    ... )
    >>> for window_data in window:
    ...     # window_data is a 30-element view, adjusted correctly
    ...     sma = window_data.mean()
"""

import numpy as np
from rustybt.lib.adjustment import Adjustment

class AdjustedArrayWindow:
    """Sliding window over a float64 array with adjustments."""

    data: np.ndarray
    view: np.ndarray
    roffset: int
    offset: int

    def __init__(
        self,
        data: np.ndarray,
        view: np.ndarray,
        adjustments: list[Adjustment],
        offset: int,
        roffset: int,
    ) -> None: ...

    def __getitem__(self, item: int) -> float: ...
    def __len__(self) -> int: ...
