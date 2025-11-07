"""Cython-optimized sliding window for object/categorical data with adjustments.

Specialized version of AdjustedArrayWindow for object arrays (categorical/label data).
Handles string/object types efficiently for categorical factor computations.

See Also:
    _float64window: Numeric version with detailed documentation
"""

from typing import Any
import numpy as np
from rustybt.lib.adjustment import Adjustment

class AdjustedArrayWindow:
    """Sliding window over an object/label array with adjustments."""

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

    def __getitem__(self, item: int) -> Any: ...
    def __len__(self) -> int: ...
