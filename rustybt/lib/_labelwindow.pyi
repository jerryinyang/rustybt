"""Type stubs for rustybt.lib._labelwindow - Compiled Cython module."""

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
