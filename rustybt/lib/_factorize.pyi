"""Type stubs for rustybt.lib._factorize - Compiled Cython module."""

from typing import Any
import numpy as np

def factorize_strings(
    strings: np.ndarray, missing_value: Any = None
) -> tuple[np.ndarray, np.ndarray, list[str]]: ...

def factorize_strings_known_categories(
    strings: np.ndarray, categories: list[str], missing_value: Any = None
) -> np.ndarray: ...
