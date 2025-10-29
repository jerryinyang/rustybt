"""Type stubs for rustybt.lib._int64window - Compiled Cython module."""

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
