"""Type stubs for rustybt.data._adjustments - Compiled Cython module."""

from typing import Any
import pandas as pd
import sqlite3

def load_adjustments_from_sqlite(
    adjustments_db: sqlite3.Connection | str,
    dates: pd.DatetimeIndex,
    assets: pd.Int64Index,
    should_include_splits: bool,
    should_include_mergers: bool,
    should_include_dividends: bool,
    adjustment_type: str,
) -> dict[str, list[Any]]: ...
