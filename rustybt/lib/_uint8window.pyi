"""Cython-optimized sliding window for uint8/boolean data with adjustments.

Specialized version of AdjustedArrayWindow for boolean data stored as uint8.
Used for boolean factors and filters in Pipeline computations.

See Also:
    _float64window: Numeric version with detailed documentation
"""

import numpy as np
from rustybt.lib.adjustment import Adjustment

class AdjustedArrayWindow:
    """Sliding window over a uint8/boolean array with adjustments."""

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

    def __getitem__(self, item: int) -> bool: ...
    def __len__(self) -> int: ...
