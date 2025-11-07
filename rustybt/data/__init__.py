"""Data access and management for rustybt.

This module provides tools for loading, reading, and managing market data used in
backtesting simulations. It supports various data formats and frequencies (daily,
minute) with built-in adjustment handling for corporate actions.

Core Components:
    Bar Readers: Classes for reading OHLCV data at different frequencies
        - BcolzDailyBarReader: Efficient daily bar storage using bcolz
        - BcolzMinuteBarReader: Efficient minute bar storage using bcolz
        - HDF5DailyBarReader: Daily bars stored in HDF5 format
        - InMemoryDailyBarReader: In-memory daily bar storage

    Bar Writers: Classes for writing pricing data to disk
        - BcolzDailyBarWriter: Write daily bars in bcolz format
        - BcolzMinuteBarWriter: Write minute bars in bcolz format
        - HDF5DailyBarWriter: Write daily bars in HDF5 format

    Adjustments: Corporate action data handling
        - SQLiteAdjustmentReader: Read splits, mergers, and dividends
        - SQLiteAdjustmentWriter: Write adjustment data to SQLite

    Data Portal: Unified interface for data access during simulation
        - DataPortal: Main interface providing history windows and spot prices

    Loaders: Utilities for loading data from various sources
        - load_prices_from_csv: Load OHLCV data from CSV files
        - load_prices_from_csv_folder: Load data from directory of CSV files

Data Access Patterns:
    Basic CSV Loading:
        >>> from rustybt.data import load_prices_from_csv
        >>> df = load_prices_from_csv('prices.csv', identifier_col='date')

    Bundle Loading:
        >>> from rustybt.data import DataPortal
        >>> from rustybt.assets import AssetFinder
        >>> # Initialize with bundle readers
        >>> portal = DataPortal(
        ...     asset_finder=finder,
        ...     trading_calendar=calendar,
        ...     first_trading_day=start,
        ...     equity_daily_reader=daily_reader,
        ... )

    Spot Price Retrieval:
        >>> # Get current price for asset
        >>> price = portal.get_spot_value(
        ...     asset, 'close', dt, data_frequency='daily'
        ... )

    History Window:
        >>> # Get historical OHLCV window
        >>> history_df = portal.get_history_window(
        ...     assets=[asset1, asset2],
        ...     end_dt=current_dt,
        ...     bar_count=30,
        ...     frequency='1d',
        ...     field='close',
        ...     data_frequency='daily',
        ... )

See Also:
    rustybt.assets: Asset management and metadata
    rustybt.pipeline: Pipeline API for factor computation
    rustybt.utils.calendar_utils: Trading calendar utilities
"""

from . import loader
from .loader import (
    load_prices_from_csv,
    load_prices_from_csv_folder,
)

__all__ = [
    "load_prices_from_csv",
    "load_prices_from_csv_folder",
    "loader",
]
