"""Type stubs for rustybt.data._equities - Compiled Cython module."""

from typing import Any
import numpy as np

def _compute_row_slices(dates: np.ndarray) -> list[tuple[int, int]]: ...

def _read_bcolz_data(
    table: Any, shape: tuple[int, int], columns: list[str], dtype: Any
) -> dict[str, np.ndarray]: ...
