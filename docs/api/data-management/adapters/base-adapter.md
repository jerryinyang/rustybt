# BaseDataAdapter - Core Adapter Interface

**Module**: `rustybt.data.adapters.base`

## Overview

`BaseDataAdapter` is the abstract base class for all RustyBT data adapters. It provides a standardized interface for fetching, validating, and standardizing market data from any source with built-in rate limiting, retry logic, and error handling.

## Class Definition

```python
from abc import ABC
from rustybt.data.adapters.base import BaseDataAdapter

class BaseDataAdapter(ABC):
    """Base class for data source adapters.

    Provides standardized interface for fetching, validating, and standardizing
    market data from various sources. Includes built-in rate limiting, retry logic,
    and error handling.
    """
```

## Standard Schema

All adapters must return data in this standardized Polars DataFrame schema:

```python
import polars as pl

# Standard OHLCV schema for all adapters
STANDARD_SCHEMA = {
    "timestamp": pl.Datetime("us"),                    # UTC timestamps (microsecond precision)
    "symbol": pl.Utf8,                                 # Asset symbol/ticker
    "open": pl.Decimal(precision=18, scale=8),         # Opening price
    "high": pl.Decimal(precision=18, scale=8),         # Highest price
    "low": pl.Decimal(precision=18, scale=8),          # Lowest price
    "close": pl.Decimal(precision=18, scale=8),        # Closing price
    "volume": pl.Decimal(precision=18, scale=8),       # Trading volume
}
```

**Key Points**:
- **Decimal Precision**: All prices use `Decimal` type (18 digits precision, 8 decimal places)
- **UTC Timestamps**: All timestamps are in UTC timezone
- **Sorted**: Data must be sorted by timestamp within each symbol
- **No Duplicates**: No duplicate symbol-timestamp pairs allowed

## Constructor

```python
from typing import Optional

# Constructor signature (called from subclass)
def __init__(
    self,
    name: str,
    rate_limit_per_second: int = 10,
    max_retries: int = 3,
    initial_retry_delay: float = 1.0,
    backoff_factor: float = 2.0,
    validator: Optional['DataValidator'] = None,
) -> None:
    """Initialize base data adapter."""
    pass
```

### Parameters

- **name** (`str`): Adapter name for logging and identification
- **rate_limit_per_second** (`int`, default=10): Maximum requests per second
- **max_retries** (`int`, default=3): Maximum retry attempts for transient errors
- **initial_retry_delay** (`float`, default=1.0): Initial delay before first retry (seconds)
- **backoff_factor** (`float`, default=2.0): Multiplier for exponential backoff
- **validator** (`Optional[DataValidator]`, default=None): Optional multi-layer data validator

### Example

```python
from rustybt.data.adapters.base import BaseDataAdapter

class MyAdapter(BaseDataAdapter):
    def __init__(self):
        super().__init__(
            name="MyAdapter",
            rate_limit_per_second=5,     # Conservative rate limit
            max_retries=3,                # Retry failed requests
            backoff_factor=2.0            # Exponential backoff
        )
```

## Abstract Methods

Subclasses **must** implement these methods:

### fetch()

```python
from abc import abstractmethod
import pandas as pd
import polars as pl

# Abstract method signature (implement in subclass)
@abstractmethod
async def fetch(
    self,
    symbols: list[str],
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    resolution: str,
) -> pl.DataFrame:
    """Fetch OHLCV data and return Polars DataFrame with Decimal columns."""
    pass
```

Fetch OHLCV data and return Polars DataFrame with Decimal columns.

**Parameters**:
- **symbols** (`list[str]`): List of symbols to fetch (e.g., `["AAPL", "MSFT"]`)
- **start_date** (`pd.Timestamp`): Start date for data range
- **end_date** (`pd.Timestamp`): End date for data range
- **resolution** (`str`): Time resolution (e.g., `"1d"`, `"1h"`, `"1m"`)

**Returns**:
- `pl.DataFrame`: Polars DataFrame with standardized OHLCV schema

**Raises**:
- `NetworkError`: If API request fails
- `RateLimitError`: If rate limit exceeded
- `InvalidDataError`: If received data is invalid
- `ValidationError`: If data validation fails

### standardize()

```python
from abc import abstractmethod
import polars as pl

# Abstract method signature (implement in subclass)
@abstractmethod
def standardize(self, df: pl.DataFrame) -> pl.DataFrame:
    """Convert provider-specific format to RustyBT standard schema."""
    pass
```

Convert provider-specific format to RustyBT standard schema.

**Parameters**:
- **df** (`pl.DataFrame`): DataFrame in provider-specific format

**Returns**:
- `pl.DataFrame`: DataFrame with standardized schema and Decimal columns

## Optional Methods

Subclasses can override these methods for custom behavior:

### validate()

```python
import polars as pl
from rustybt.data.adapters.base import validate_ohlcv_relationships

# Optional method signature (override in subclass if needed)
def validate(self, df: pl.DataFrame) -> bool:
    """Validate OHLCV data quality and relationships."""
    return validate_ohlcv_relationships(df)
```

Validate OHLCV data quality and relationships. Default implementation uses `validate_ohlcv_relationships()`.

**Parameters**:
- **df** (`pl.DataFrame`): DataFrame to validate

**Returns**:
- `bool`: True if validation passes

**Raises**:
- `ValidationError`: If data validation fails

## Built-in Features

### Rate Limiting

Automatic rate limiting using token bucket algorithm:

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

async def fetch_multiple_symbols():
    # Rate limiter automatically throttles requests
    adapter = YFinanceAdapter(request_delay=0.2)  # 5 requests per second

    start_date = pd.Timestamp("2024-01-01")
    end_date = pd.Timestamp("2024-01-31")

    # This will automatically space out requests
    for symbol in ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META"]:
        data = await adapter.fetch([symbol], start_date, end_date, "1d")
        print(f"Fetched {len(data)} rows for {symbol}")
        # Requests are automatically spaced to respect rate limit

# Run the async function
asyncio.run(fetch_multiple_symbols())
```

### Retry Logic

Automatic retry with exponential backoff for transient errors:

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

async def fetch_with_retry():
    adapter = YFinanceAdapter(
        request_delay=1.0,          # Base request delay
        # Note: max_retries is set in BaseDataAdapter (default 3)
    )

    start_date = pd.Timestamp("2024-01-01")
    end_date = pd.Timestamp("2024-01-31")

    # Transient errors (NetworkError, TimeoutError) are automatically retried
    # with exponential backoff: 1s, 2s, 4s
    data = await adapter.fetch(["AAPL"], start_date, end_date, "1d")

    return data

# Run the async function
data = asyncio.run(fetch_with_retry())
```

### Data Validation

Automatic validation of OHLCV relationships:

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

async def fetch_with_validation():
    adapter = YFinanceAdapter()

    start_date = pd.Timestamp("2024-01-01")
    end_date = pd.Timestamp("2024-01-31")

    # Validation happens automatically in fetch()
    data = await adapter.fetch(["AAPL"], start_date, end_date, "1d")

    # Validation checks:
    # ✅ Required columns exist (timestamp, symbol, open, high, low, close, volume)
    # ✅ OHLCV relationships valid (high >= low, high >= open/close, etc.)
    # ✅ No NULL values in required columns
    # ✅ Timestamps are sorted
    # ✅ No duplicate timestamps per symbol

    return data

# Run the async function
data = asyncio.run(fetch_with_validation())
```

## Utility Functions

### validate_ohlcv_relationships()

```python
import pandas as pd
import polars as pl
from rustybt.data.adapters.base import validate_ohlcv_relationships

# Create sample data
df = pl.DataFrame({
    "timestamp": [pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-03")],
    "symbol": ["AAPL", "AAPL"],
    "open": ["185.64", "186.84"],
    "high": ["186.95", "187.73"],
    "low": ["185.17", "186.06"],
    "close": ["186.89", "186.33"],
    "volume": ["45274200", "37628400"],
}).with_columns([
    pl.col("open").cast(str).str.to_decimal(scale=8),
    pl.col("high").cast(str).str.to_decimal(scale=8),
    pl.col("low").cast(str).str.to_decimal(scale=8),
    pl.col("close").cast(str).str.to_decimal(scale=8),
    pl.col("volume").cast(str).str.to_decimal(scale=8),
])

# Validate OHLCV data manually
is_valid = validate_ohlcv_relationships(df)
print(f"Data is valid: {is_valid}")
```

Validates:
- Required columns exist
- OHLCV relationships (high ≥ low, high ≥ open/close, etc.)
- No NULL values
- Timestamps sorted
- No duplicate timestamps per symbol

### detect_outliers()

```python
import pandas as pd
import polars as pl
from rustybt.data.adapters.base import detect_outliers

# Create sample data with potential outlier
data = pl.DataFrame({
    "timestamp": [pd.Timestamp(f"2024-01-{i:02d}") for i in range(2, 7)],
    "symbol": ["AAPL"] * 5,
    "open": ["185", "186", "187", "188", "189"],
    "high": ["186", "187", "188", "189", "190"],
    "low": ["184", "185", "186", "187", "188"],
    "close": ["185.5", "186.5", "187.5", "188.5", "189.5"],
    "volume": ["1000000"] * 5,
}).with_columns([
    pl.col("open").cast(str).str.to_decimal(scale=8),
    pl.col("high").cast(str).str.to_decimal(scale=8),
    pl.col("low").cast(str).str.to_decimal(scale=8),
    pl.col("close").cast(str).str.to_decimal(scale=8),
    pl.col("volume").cast(str).str.to_decimal(scale=8),
])

# Detect price outliers using MAD
outliers = detect_outliers(data, threshold=3.0)

if len(outliers) > 0:
    print(f"Found {len(outliers)} potential data quality issues")
    print(outliers[["timestamp", "symbol", "close", "pct_change"]])
else:
    print("No outliers detected")
```

Uses Median Absolute Deviation (MAD) to detect anomalous price movements.

**Parameters**:
- **df** (`pl.DataFrame`): DataFrame with OHLCV data
- **threshold** (`float`, default=3.0): Number of MADs for outlier detection

**Returns**:
- `pl.DataFrame`: DataFrame containing only outlier rows

## Exception Hierarchy

```python
from rustybt.data.adapters.base import (
    NetworkError,        # Network connectivity error
    RateLimitError,     # API rate limit exceeded
    InvalidDataError,   # Invalid data received
    ValidationError,    # Data validation failed
)

# All inherit from DataAdapterError
from rustybt.exceptions import DataAdapterError
```

## Creating Custom Adapters

### Minimal Example

```python
import pandas as pd
import polars as pl
from rustybt.data.adapters.base import BaseDataAdapter

class MyCustomAdapter(BaseDataAdapter):
    """Custom adapter for my data source."""

    def __init__(self):
        super().__init__(name="MyCustomAdapter", rate_limit_per_second=10)

    async def fetch(
        self,
        symbols: list[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        resolution: str,
    ) -> pl.DataFrame:
        """Fetch data from my source."""
        # 1. Fetch raw data from source
        raw_data = await self._fetch_from_source(symbols, start_date, end_date, resolution)

        # 2. Convert to Polars DataFrame
        df = pl.DataFrame(raw_data)

        # 3. Standardize to RustyBT schema
        df = self.standardize(df)

        # 4. Validate (automatic)
        self.validate(df)

        # 5. Log success
        self._log_fetch_success(symbols, start_date, end_date, resolution, len(df))

        return df

    def standardize(self, df: pl.DataFrame) -> pl.DataFrame:
        """Convert my format to standard schema."""
        return df.select([
            pl.col("dt").alias("timestamp").cast(pl.Datetime("us")),
            pl.col("ticker").alias("symbol"),
            pl.col("o").cast(str).str.to_decimal(scale=8).alias("open"),
            pl.col("h").cast(str).str.to_decimal(scale=8).alias("high"),
            pl.col("l").cast(str).str.to_decimal(scale=8).alias("low"),
            pl.col("c").cast(str).str.to_decimal(scale=8).alias("close"),
            pl.col("v").cast(str).str.to_decimal(scale=8).alias("volume"),
        ])

    async def _fetch_from_source(self, symbols, start_date, end_date, resolution):
        """Fetch from actual data source (implement based on your source)."""
        # Example stub - replace with actual API/database calls
        return {
            "dt": [start_date],
            "ticker": [symbols[0]],
            "o": ["100.00"],
            "h": ["101.00"],
            "l": ["99.00"],
            "c": ["100.50"],
            "v": ["1000000"],
        }

# Example usage
async def main():
    adapter = MyCustomAdapter()
    data = await adapter.fetch(
        ["AAPL"],
        pd.Timestamp("2024-01-02"),
        pd.Timestamp("2024-01-03"),
        "1d"
    )
    print(f"Fetched {len(data)} rows")

# Uncomment to run: asyncio.run(main())
```

### Full Example with Error Handling

```python
import pandas as pd
import polars as pl
from rustybt.data.adapters.base import (
    BaseDataAdapter,
    NetworkError,
    InvalidDataError,
    with_retry,
)
import structlog

logger = structlog.get_logger()

class RobustAdapter(BaseDataAdapter):
    """Production-grade adapter with error handling."""

    def __init__(self):
        super().__init__(
            name="RobustAdapter",
            rate_limit_per_second=5,
            max_retries=3,
            backoff_factor=2.0,
        )

    @with_retry(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
    async def fetch(
        self,
        symbols: list[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        resolution: str,
    ) -> pl.DataFrame:
        """Fetch with automatic retry on transient errors."""

        # Rate limiting (automatic via self.rate_limiter)
        await self.rate_limiter.acquire()

        try:
            # Fetch raw data
            raw_data = await self._api_call(symbols, start_date, end_date, resolution)

            # Convert and standardize
            df = pl.DataFrame(raw_data)
            df = self.standardize(df)

            # Validate
            self.validate(df)

            # Log success
            self._log_fetch_success(symbols, start_date, end_date, resolution, len(df))

            return df

        except ValueError as e:
            # Non-retryable error
            logger.error("invalid_data", error=str(e), symbols=symbols)
            raise InvalidDataError(f"Invalid data received: {e}")

        except Exception as e:
            # Unexpected error
            logger.error("fetch_failed", error=str(e), symbols=symbols)
            raise NetworkError(f"Fetch failed: {e}")

    def standardize(self, df: pl.DataFrame) -> pl.DataFrame:
        """Standardize schema with proper type conversions."""
        return df.select([
            pl.col("timestamp").cast(pl.Datetime("us")),
            pl.col("symbol"),
            pl.col("open").cast(str).str.to_decimal(scale=8),
            pl.col("high").cast(str).str.to_decimal(scale=8),
            pl.col("low").cast(str).str.to_decimal(scale=8),
            pl.col("close").cast(str).str.to_decimal(scale=8),
            pl.col("volume").cast(str).str.to_decimal(scale=8),
        ]).sort("timestamp", "symbol")

    async def _api_call(self, symbols, start_date, end_date, resolution):
        """Example API call - replace with actual implementation."""
        # Stub implementation
        return {
            "timestamp": [start_date],
            "symbol": [symbols[0]],
            "open": ["100.00"],
            "high": ["101.00"],
            "low": ["99.00"],
            "close": ["100.50"],
            "volume": ["1000000"],
        }

# Example usage
async def main():
    adapter = RobustAdapter()
    data = await adapter.fetch(
        ["AAPL"],
        pd.Timestamp("2024-01-02"),
        pd.Timestamp("2024-01-03"),
        "1d"
    )
    print(f"Fetched {len(data)} rows with error handling")

# Uncomment to run: asyncio.run(main())
```

## Best Practices

### 1. Conservative Rate Limits

```python
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

# ❌ Don't be aggressive with rate limits
# adapter = YFinanceAdapter(request_delay=0.01)  # Too fast! (100 req/s)

# ✅ Start conservative, increase if needed
adapter = YFinanceAdapter(request_delay=0.2)   # Safe default (5 req/s)
print(f"✅ Created adapter with safe rate limit: {adapter.request_delay}s delay")
```

### 2. Proper Decimal Conversion

```python
import polars as pl

# Create sample data
df = pl.DataFrame({"close": [100.123456789]})

# ❌ Don't convert floats directly to Decimal
# df_bad = df.with_columns(pl.col("close").cast(pl.Decimal))  # Loses precision!

# ✅ Convert through string to preserve precision
df_good = df.with_columns(pl.col("close").cast(str).str.to_decimal(scale=8))
print(f"✅ Proper decimal conversion: {df_good['close'][0]}")
```

### 3. Always Validate

```python
# Educational pattern - showing best practices for validation

# ❌ DON'T: Skip validation
# async def fetch(self, symbols, start_date, end_date, resolution):
#     df = await self._get_data()
#     return df  # No validation - data quality issues may slip through!

# ✅ DO: Always validate before returning
# async def fetch(self, symbols, start_date, end_date, resolution):
#     df = await self._get_data()
#     df = self.standardize(df)
#     self.validate(df)  # Catches data quality issues early
#     return df

print("✅ Pattern demonstrated: Always validate data before returning")
```

### 4. Log Important Events

```python
# Educational pattern - showing best practices for logging

# ❌ DON'T: Silent failures
# async def fetch(self, symbols, start_date, end_date, resolution):
#     try:
#         return await self._get_data()
#     except Exception:
#         return pl.DataFrame()  # Silent failure - no logs, no debugging info!

# ✅ DO: Log errors and successes
# async def fetch(self, symbols, start_date, end_date, resolution):
#     try:
#         df = await self._get_data()
#         self._log_fetch_success(symbols, start_date, end_date, resolution, len(df))
#         return df
#     except Exception as e:
#         logger.error("fetch_failed", error=str(e), symbols=symbols)
#         raise

print("✅ Pattern demonstrated: Always log important events for debugging")
```

## See Also

- [YFinance Adapter](./yfinance-adapter.md) - Production example
- [CSV Adapter](./csv-adapter.md) - File-based adapter example
