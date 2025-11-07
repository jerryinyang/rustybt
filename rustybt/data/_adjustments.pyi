"""Cython-optimized loading of price adjustments from SQLite databases.

This module provides high-performance functions for loading corporate action
adjustments (splits, dividends, mergers) from SQLite databases. Uses Cython
for fast database queries and adjustment construction.

Cython optimizations:
- Efficient SQLite query batching to respect SQLITE_MAX_VARIABLE_NUMBER
- Fast dictionary lookups for date/asset indexing
- Inline adjustment object creation

Example:
    >>> adjustments = load_adjustments_from_sqlite(
    ...     db_connection,
    ...     dates=pd.date_range('2020-01-01', '2020-12-31'),
    ...     assets=pd.Int64Index([1, 2, 3]),
    ...     should_include_splits=True,
    ...     should_include_mergers=True,
    ...     should_include_dividends=True,
    ...     adjustment_type='price'
    ... )
"""

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
) -> dict[str, list[Any]]:
    """Load corporate action adjustments from a SQLite database.

    Efficiently queries and constructs adjustment objects for splits, dividends,
    and mergers from a SQLite adjustments database.

    Args:
        adjustments_db: SQLite connection or path to database.
        dates: Date range for which to load adjustments.
        assets: Assets for which to load adjustments.
        should_include_splits: Whether to include stock splits.
        should_include_mergers: Whether to include mergers/acquisitions.
        should_include_dividends: Whether to include cash/stock dividends.
        adjustment_type: Type of adjustments - 'price', 'volume', or 'all'.

    Returns:
        Dictionary mapping adjustment type ('price', 'volume') to lists of
        Adjustment objects indexed by date.

    Example:
        >>> adjs = load_adjustments_from_sqlite(
        ...     conn, dates, assets,
        ...     should_include_splits=True,
        ...     should_include_mergers=False,
        ...     should_include_dividends=True,
        ...     adjustment_type='price'
        ... )
        >>> price_adjs = adjs['price']

    Note:
        Cython-optimized with efficient batching to handle large asset universes
        while respecting SQLite's parameter limits.
    """
    ...
