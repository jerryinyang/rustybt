"""Type stubs for rustybt.lib.rank - Compiled Cython module."""

import numpy as np

def rankdata_1d_descending(data: np.ndarray) -> np.ndarray: ...

def masked_rankdata_2d(
    data: np.ndarray, mask: np.ndarray, missing_value: float, ascending: bool, method: str
) -> np.ndarray: ...

def rankdata_2d_ordinal(data: np.ndarray, missing_value: float, ascending: bool) -> np.ndarray: ...

def grouped_masked_is_maximal(
    data: np.ndarray, groupby: np.ndarray, mask: np.ndarray, missing_value: float
) -> np.ndarray: ...
