"""Type stubs for rustybt.lib.adjustment - Compiled Cython module."""

from typing import Any
import numpy as np
import pandas as pd

ADJUSTMENT_KIND_NAMES: dict[int, str]

class Adjustment:
    """Base class for adjustments."""

    first_row: int
    last_row: int
    first_col: int
    last_col: int
    kind: int

    def __init__(
        self, first_row: int, last_row: int, first_col: int, last_col: int, kind: int
    ) -> None: ...

class Float64Adjustment(Adjustment):
    """Base class for float64 adjustments."""

    value: float

class Float64Multiply(Float64Adjustment):
    """Multiply adjustment for float64 values."""

    def __init__(
        self, first_row: int, last_row: int, first_col: int, last_col: int, value: float
    ) -> None: ...

class Float64Overwrite(Float64Adjustment):
    """Overwrite adjustment for float64 values."""

    def __init__(
        self, first_row: int, last_row: int, first_col: int, last_col: int, value: float
    ) -> None: ...

class Float64Add(Float64Adjustment):
    """Add adjustment for float64 values."""

    def __init__(
        self, first_row: int, last_row: int, first_col: int, last_col: int, value: float
    ) -> None: ...

class ArrayAdjustment(Adjustment):
    """Base class for array adjustments."""

    value: np.ndarray

class Float641DArrayOverwrite(ArrayAdjustment):
    """Overwrite adjustment for 1D float64 arrays."""

    def __init__(
        self, first_row: int, last_row: int, first_col: int, last_col: int, value: np.ndarray
    ) -> None: ...

class Datetime641DArrayOverwrite(ArrayAdjustment):
    """Overwrite adjustment for 1D datetime64 arrays."""

    def __init__(
        self, first_row: int, last_row: int, first_col: int, last_col: int, value: np.ndarray
    ) -> None: ...

class Object1DArrayOverwrite(ArrayAdjustment):
    """Overwrite adjustment for 1D object arrays."""

    def __init__(
        self, first_row: int, last_row: int, first_col: int, last_col: int, value: np.ndarray
    ) -> None: ...

class Boolean1DArrayOverwrite(ArrayAdjustment):
    """Overwrite adjustment for 1D boolean arrays."""

    def __init__(
        self, first_row: int, last_row: int, first_col: int, last_col: int, value: np.ndarray
    ) -> None: ...

class Int64Overwrite(Adjustment):
    """Overwrite adjustment for int64 values."""

    value: int

    def __init__(
        self, first_row: int, last_row: int, first_col: int, last_col: int, value: int
    ) -> None: ...

class Datetime64Overwrite(Adjustment):
    """Overwrite adjustment for datetime64 values."""

    value: pd.Timestamp

    def __init__(
        self, first_row: int, last_row: int, first_col: int, last_col: int, value: pd.Timestamp
    ) -> None: ...

class ObjectOverwrite(Adjustment):
    """Overwrite adjustment for object values."""

    value: Any

    def __init__(
        self, first_row: int, last_row: int, first_col: int, last_col: int, value: Any
    ) -> None: ...

class BooleanOverwrite(Adjustment):
    """Overwrite adjustment for boolean values."""

    value: bool

    def __init__(
        self, first_row: int, last_row: int, first_col: int, last_col: int, value: bool
    ) -> None: ...

def make_adjustment_from_indices(
    dates_index: pd.DatetimeIndex,
    sids_index: pd.Int64Index,
    effective_date: pd.Timestamp,
    ratio: float,
    sid: int,
) -> Float64Multiply: ...

def make_adjustment_from_labels(
    dates_index: pd.DatetimeIndex,
    sids_index: pd.Int64Index,
    effective_date: pd.Timestamp,
    ratio: float,
    sid: int,
) -> Float64Multiply: ...

def choose_adjustment_type(value: Any) -> type[Adjustment]: ...
