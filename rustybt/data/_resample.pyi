"""Type stubs for rustybt.data._resample - Compiled Cython module."""

import numpy as np
import pandas as pd

def _minute_to_session_open(
    columns: list[str],
    close_locs: np.ndarray,
    data: np.ndarray,
    out: np.ndarray,
) -> None: ...

def _minute_to_session_high(
    columns: list[str],
    close_locs: np.ndarray,
    data: np.ndarray,
    out: np.ndarray,
) -> None: ...

def _minute_to_session_low(
    columns: list[str],
    close_locs: np.ndarray,
    data: np.ndarray,
    out: np.ndarray,
) -> None: ...

def _minute_to_session_close(
    columns: list[str],
    close_locs: np.ndarray,
    data: np.ndarray,
    out: np.ndarray,
) -> None: ...

def _minute_to_session_volume(
    columns: list[str],
    close_locs: np.ndarray,
    data: np.ndarray,
    out: np.ndarray,
) -> None: ...
