"""Data source adapters for RustyBT.

This package provides extensible base adapter classes and implementations
for fetching market data from various sources (exchanges, APIs, files).
"""

from rustybt.data.adapters.alpaca_adapter import AlpacaAdapter
from rustybt.data.adapters.alphavantage_adapter import AlphaVantageAdapter

# API provider adapters
from rustybt.data.adapters.api_provider_base import (
    AuthenticationError,
    BaseAPIProviderAdapter,
    DataParsingError,
    QuotaExceededError,
    SymbolNotFoundError,
)
from rustybt.data.adapters.base import (
    BaseDataAdapter,
    NetworkError,  # Legacy data adapter specific
    RateLimitError,  # Legacy data adapter specific
)
from rustybt.data.adapters.csv_adapter import CSVAdapter, CSVConfig, SchemaMapping
from rustybt.data.adapters.polygon_adapter import PolygonAdapter
from rustybt.data.adapters.registry import AdapterRegistry
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter
from rustybt.exceptions import (
    DataAdapterError,
)
from rustybt.exceptions import (
    DataValidationError as InvalidDataError,  # Alias for backward compatibility
)
from rustybt.exceptions import (
    DataValidationError as ValidationError,  # Alias for backward compatibility
)

# Conditional import for CCXTAdapter (requires ccxt dependency)
try:
    from rustybt.data.adapters.ccxt_adapter import CCXTAdapter

    __all__ = [
        "AdapterRegistry",
        "AlpacaAdapter",
        "AlphaVantageAdapter",
        "AuthenticationError",
        "BaseAPIProviderAdapter",
        "BaseDataAdapter",
        "CCXTAdapter",
        "CSVAdapter",
        "CSVConfig",
        "DataAdapterError",
        "DataParsingError",
        "InvalidDataError",
        "NetworkError",
        "PolygonAdapter",
        "QuotaExceededError",
        "RateLimitError",
        "SchemaMapping",
        "SymbolNotFoundError",
        "ValidationError",
        "YFinanceAdapter",
    ]
except ImportError:
    # CCXTAdapter not available if ccxt not installed
    __all__ = [
        "AdapterRegistry",
        "AlpacaAdapter",
        "AlphaVantageAdapter",
        "AuthenticationError",
        "BaseAPIProviderAdapter",
        "BaseDataAdapter",
        "CSVAdapter",
        "CSVConfig",
        "DataAdapterError",
        "DataParsingError",
        "InvalidDataError",
        "NetworkError",
        "PolygonAdapter",
        "QuotaExceededError",
        "RateLimitError",
        "SchemaMapping",
        "SymbolNotFoundError",
        "ValidationError",
        "YFinanceAdapter",
    ]
