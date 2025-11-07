"""Cython-optimized sliding window for int64/datetime64 data with adjustments.

Specialized version of AdjustedArrayWindow for int64 and datetime64 data types.
Identical interface to _float64window but optimized for integer/datetime operations.

See Also:
    _float64window: Float64 version with same interface
"""

import numpy as np
from rustybt.lib.adjustment import Adjustment

class AdjustedArrayWindow:
    """Sliding window over an int64 array with adjustments."""

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

    def __getitem__(self, item: int) -> int: ...
    def __len__(self) -> int: ...
