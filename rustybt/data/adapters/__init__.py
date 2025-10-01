"""Data source adapters for RustyBT.

This package provides extensible base adapter classes and implementations
for fetching market data from various sources (exchanges, APIs, files).
"""

from rustybt.data.adapters.base import (
    BaseDataAdapter,
    DataAdapterError,
    InvalidDataError,
    NetworkError,
    RateLimitError,
    ValidationError,
)
from rustybt.data.adapters.csv_adapter import CSVAdapter, CSVConfig, SchemaMapping
from rustybt.data.adapters.registry import AdapterRegistry
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

# Conditional import for CCXTAdapter (requires ccxt dependency)
try:
    from rustybt.data.adapters.ccxt_adapter import CCXTAdapter

    __all__ = [
        "BaseDataAdapter",
        "CCXTAdapter",
        "CSVAdapter",
        "CSVConfig",
        "SchemaMapping",
        "YFinanceAdapter",
        "DataAdapterError",
        "InvalidDataError",
        "NetworkError",
        "RateLimitError",
        "ValidationError",
        "AdapterRegistry",
    ]
except ImportError:
    # CCXTAdapter not available if ccxt not installed
    __all__ = [
        "BaseDataAdapter",
        "CSVAdapter",
        "CSVConfig",
        "SchemaMapping",
        "YFinanceAdapter",
        "DataAdapterError",
        "InvalidDataError",
        "NetworkError",
        "RateLimitError",
        "ValidationError",
        "AdapterRegistry",
    ]
