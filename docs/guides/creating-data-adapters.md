# Creating Data Adapters for RustyBT

This guide explains how to create custom data adapters to integrate new data sources into RustyBT.

## Table of Contents

- [Overview](#overview)
- [BaseDataAdapter Interface](#basedataadapter-interface)
- [Creating a Custom Adapter](#creating-a-custom-adapter)
- [Standard OHLCV Schema](#standard-ohlcv-schema)
- [Validation Requirements](#validation-requirements)
- [Error Handling](#error-handling)
- [Rate Limiting](#rate-limiting)
- [Retry Logic](#retry-logic)
- [Testing Your Adapter](#testing-your-adapter)
- [Template Adapter](#template-adapter)

## Overview

RustyBT's data adapter framework provides a standardized way to integrate market data from various sources (APIs, databases, files). All adapters inherit from `BaseDataAdapter` and implement three core methods:

- **`fetch()`**: Retrieve data from source
- **`validate()`**: Ensure data quality
- **`standardize()`**: Convert to RustyBT standard format

The framework provides built-in support for:
- Rate limiting (token bucket algorithm)
- Retry logic (exponential backoff)
- Error handling (standardized exception hierarchy)
- Validation (OHLCV relationships, outliers, temporal consistency)

## BaseDataAdapter Interface

### Required Methods

```python
from abc import ABC, abstractmethod
import polars as pl
import pandas as pd
from typing import List
from rustybt.data.adapters.base import BaseDataAdapter

class MyAdapter(BaseDataAdapter):
    @abstractmethod
    async def fetch(
        self,
        symbols: List[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        resolution: str
    ) -> pl.DataFrame:
        """Fetch OHLCV data and return standardized DataFrame."""
        pass

    @abstractmethod
    def validate(self, df: pl.DataFrame) -> bool:
        """Validate data quality and relationships."""
        pass

    @abstractmethod
    def standardize(self, df: pl.DataFrame) -> pl.DataFrame:
        """Convert provider format to RustyBT standard schema."""
        pass
```

## Creating a Custom Adapter

### Step 1: Inherit from BaseDataAdapter

```python
from rustybt.data.adapters.base import (
    BaseDataAdapter,
    NetworkError,
    ValidationError,
    validate_ohlcv_relationships,
    with_retry,
)
import polars as pl
import pandas as pd
from decimal import Decimal
from typing import List
import structlog

logger = structlog.get_logger()

class MyDataAdapter(BaseDataAdapter):
    def __init__(
        self,
        api_key: str,
        rate_limit_per_second: int = 5,
        max_retries: int = 3,
    ):
        super().__init__(
            name="MyDataAdapter",
            rate_limit_per_second=rate_limit_per_second,
            max_retries=max_retries,
        )
        self.api_key = api_key
```

### Step 2: Implement fetch() Method

```python
    @with_retry(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
    async def fetch(
        self,
        symbols: List[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        resolution: str,
    ) -> pl.DataFrame:
        """Fetch OHLCV data from API."""
        # Apply rate limiting
        await self.rate_limiter.acquire()

        try:
            # Fetch data from your source (pseudo-code)
            raw_data = await self._fetch_from_api(
                symbols, start_date, end_date, resolution
            )

            # Convert to Polars DataFrame
            df = pl.DataFrame(raw_data)

            # Standardize format
            df = self.standardize(df)

            # Validate data
            self.validate(df)

            # Log success
            self._log_fetch_success(
                symbols, start_date, end_date, resolution, len(df)
            )

            return df

        except Exception as e:
            logger.error(
                "fetch_failed",
                adapter=self.name,
                symbols=symbols,
                error=str(e),
            )
            raise NetworkError(f"Failed to fetch data: {e}") from e
```

### Step 3: Implement standardize() Method

```python
    def standardize(self, df: pl.DataFrame) -> pl.DataFrame:
        """Convert provider-specific format to RustyBT standard schema."""
        # Map provider columns to standard columns
        column_mapping = {
            "ts": "timestamp",
            "sym": "symbol",
            "o": "open",
            "h": "high",
            "l": "low",
            "c": "close",
            "v": "volume",
        }

        # Rename columns
        df = df.rename(column_mapping)

        # Convert to Decimal precision
        for col in ["open", "high", "low", "close", "volume"]:
            df = df.with_columns([
                pl.col(col).cast(pl.Decimal(precision=18, scale=8))
            ])

        # Convert timestamp to UTC microsecond precision
        df = df.with_columns([
            pl.col("timestamp").dt.convert_time_zone("UTC")
        ])

        # Sort by timestamp
        df = df.sort("timestamp")

        return df
```

### Step 4: Implement validate() Method

```python
    def validate(self, df: pl.DataFrame) -> bool:
        """Validate data quality and relationships."""
        try:
            # Use built-in OHLCV validation
            validate_ohlcv_relationships(df)

            # Add custom validations if needed
            if len(df) == 0:
                raise ValidationError("Empty dataset returned")

            return True

        except ValidationError as e:
            self._log_validation_failure(e)
            raise
```

## Standard OHLCV Schema

All adapters must return data in this standardized format:

```python
{
    "timestamp": pl.Datetime("us"),       # UTC microsecond precision
    "symbol": pl.Utf8,                    # Symbol/ticker string
    "open": pl.Decimal(18, 8),            # Opening price
    "high": pl.Decimal(18, 8),            # Highest price
    "low": pl.Decimal(18, 8),             # Lowest price
    "close": pl.Decimal(18, 8),           # Closing price
    "volume": pl.Decimal(18, 8),          # Trading volume
}
```

**Important Notes:**
- All prices use `Decimal(18, 8)` for precision (not float)
- Timestamps must be UTC with microsecond precision
- Data must be sorted by timestamp (ascending)
- No NULL values allowed in required columns

## Validation Requirements

The built-in `validate_ohlcv_relationships()` function checks:

1. **OHLCV Relationships:**
   - `high >= low`
   - `high >= open`
   - `high >= close`
   - `low <= open`
   - `low <= close`

2. **Data Quality:**
   - No NULL values in required columns
   - No duplicate timestamps per symbol
   - Timestamps sorted ascending

3. **Temporal Consistency:**
   - No future-dated data

### Custom Validation

Add adapter-specific validation:

```python
def validate(self, df: pl.DataFrame) -> bool:
    # Built-in validation
    validate_ohlcv_relationships(df)

    # Custom validation: Check volume is non-negative
    if df.filter(pl.col("volume") < 0).height > 0:
        raise ValidationError("Negative volume detected")

    # Custom validation: Check price ranges
    if df.filter(pl.col("close") > Decimal("1000000")).height > 0:
        raise ValidationError("Unrealistic price detected")

    return True
```

## Error Handling

### Exception Hierarchy

```python
from rustybt.data.adapters.base import (
    DataAdapterError,      # Base exception
    NetworkError,          # Network connectivity issues
    RateLimitError,        # API rate limit exceeded
    InvalidDataError,      # Data corruption
    ValidationError,       # Data validation failed
)
```

### Error Handling Example

```python
async def fetch(self, symbols, start_date, end_date, resolution):
    try:
        await self.rate_limiter.acquire()
        data = await self._fetch_from_api(symbols, start_date, end_date)
        return self.standardize(data)

    except RateLimitError:
        logger.warning("rate_limit_exceeded", adapter=self.name)
        raise

    except NetworkError as e:
        logger.error("network_error", adapter=self.name, error=str(e))
        raise

    except ValidationError as e:
        logger.error(
            "validation_failed",
            adapter=self.name,
            invalid_rows=len(e.invalid_rows) if e.invalid_rows else 0,
        )
        raise

    except Exception as e:
        logger.error("unexpected_error", adapter=self.name, error=str(e))
        raise DataAdapterError(f"Unexpected error: {e}") from e
```

## Rate Limiting

### Built-in Rate Limiter

The base adapter includes a token bucket rate limiter:

```python
adapter = MyAdapter(
    api_key="your_key",
    rate_limit_per_second=10,  # Max 10 requests/second
)

# Rate limiting is automatic in fetch() method
await adapter.rate_limiter.acquire()  # Blocks if limit exceeded
```

### Rate Limiter Statistics

```python
# Track rate limiting events
print(f"Requests made: {adapter.rate_limiter.requests_made}")
print(f"Throttle events: {adapter.rate_limiter.throttle_events}")
```

## Retry Logic

### Using the @with_retry Decorator

```python
from rustybt.data.adapters.base import with_retry

@with_retry(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
async def fetch(self, symbols, start_date, end_date, resolution):
    # This method will automatically retry on NetworkError or TimeoutError
    # with exponential backoff: 1s, 2s, 4s (with jitter)
    data = await self._fetch_from_api(symbols, start_date, end_date)
    return data
```

### Retry Behavior

- **Retryable Errors:** `NetworkError`, `TimeoutError`
- **Non-Retryable Errors:** `ValidationError`, `InvalidDataError`
- **Backoff Formula:** `delay = initial_delay * (backoff_factor ^ attempt)`
- **Jitter:** ±20% randomization to prevent thundering herd

## Testing Your Adapter

### Unit Test Template

```python
import pytest
import polars as pl
import pandas as pd
from decimal import Decimal
from rustybt.data.adapters.your_adapter import MyAdapter

@pytest.mark.asyncio
async def test_adapter_fetches_valid_data():
    """Test adapter fetches and validates data correctly."""
    adapter = MyAdapter(api_key="test_key", rate_limit_per_second=100)

    result = await adapter.fetch(
        symbols=["AAPL"],
        start_date=pd.Timestamp("2023-01-01"),
        end_date=pd.Timestamp("2023-01-31"),
        resolution="1d",
    )

    # Verify schema
    assert "timestamp" in result.columns
    assert "symbol" in result.columns
    assert "close" in result.columns

    # Verify data quality
    assert len(result) > 0
    assert result["symbol"][0] == "AAPL"

    # Verify validation passed
    assert adapter.validate(result) is True


def test_adapter_standardizes_format():
    """Test adapter converts provider format to standard schema."""
    adapter = MyAdapter(api_key="test_key")

    # Provider-specific format
    provider_data = pl.DataFrame({
        "ts": [pd.Timestamp("2023-01-01")],
        "sym": ["AAPL"],
        "o": [100.0],
        "h": [105.0],
        "l": [98.0],
        "c": [102.0],
        "v": [1000000.0],
    })

    # Standardize
    standardized = adapter.standardize(provider_data)

    # Verify standard schema
    assert "timestamp" in standardized.columns
    assert "symbol" in standardized.columns
    assert standardized["close"][0] == Decimal("102.0")


def test_adapter_validates_ohlcv_relationships():
    """Test adapter rejects invalid OHLCV data."""
    adapter = MyAdapter(api_key="test_key")

    # Invalid data: high < low
    invalid_data = pl.DataFrame({
        "timestamp": [pd.Timestamp("2023-01-01")],
        "symbol": ["AAPL"],
        "open": [Decimal("100")],
        "high": [Decimal("95")],  # Invalid
        "low": [Decimal("98")],
        "close": [Decimal("99")],
        "volume": [Decimal("1000")],
    })

    with pytest.raises(ValidationError, match="Invalid OHLCV relationships"):
        adapter.validate(invalid_data)
```

## Template Adapter

Complete template for a new adapter:

```python
"""
My Data Adapter for RustyBT.

Fetches market data from MyDataProvider API.
"""

import polars as pl
import pandas as pd
from decimal import Decimal
from typing import List
import structlog

from rustybt.data.adapters.base import (
    BaseDataAdapter,
    NetworkError,
    ValidationError,
    validate_ohlcv_relationships,
    with_retry,
)

logger = structlog.get_logger()


class MyDataAdapter(BaseDataAdapter):
    """Data adapter for MyDataProvider API.

    Example:
        >>> adapter = MyDataAdapter(api_key="your_key")
        >>> data = await adapter.fetch(
        ...     symbols=["AAPL", "MSFT"],
        ...     start_date=pd.Timestamp("2023-01-01"),
        ...     end_date=pd.Timestamp("2023-12-31"),
        ...     resolution="1d"
        ... )
    """

    def __init__(
        self,
        api_key: str,
        rate_limit_per_second: int = 10,
        max_retries: int = 3,
    ):
        super().__init__(
            name="MyDataAdapter",
            rate_limit_per_second=rate_limit_per_second,
            max_retries=max_retries,
        )
        self.api_key = api_key

    @with_retry(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
    async def fetch(
        self,
        symbols: List[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        resolution: str,
    ) -> pl.DataFrame:
        """Fetch OHLCV data from MyDataProvider API."""
        await self.rate_limiter.acquire()

        try:
            # TODO: Implement API call
            raw_data = await self._fetch_from_api(
                symbols, start_date, end_date, resolution
            )

            df = pl.DataFrame(raw_data)
            df = self.standardize(df)
            self.validate(df)

            self._log_fetch_success(
                symbols, start_date, end_date, resolution, len(df)
            )

            return df

        except Exception as e:
            logger.error(
                "fetch_failed",
                adapter=self.name,
                symbols=symbols,
                error=str(e),
            )
            raise NetworkError(f"Failed to fetch data: {e}") from e

    def standardize(self, df: pl.DataFrame) -> pl.DataFrame:
        """Convert provider format to RustyBT standard schema."""
        # TODO: Implement column mapping and type conversion
        column_mapping = {
            # Map provider columns to standard columns
            "provider_time": "timestamp",
            "provider_symbol": "symbol",
            # ... etc
        }

        df = df.rename(column_mapping)

        # Convert to Decimal
        for col in ["open", "high", "low", "close", "volume"]:
            df = df.with_columns([
                pl.col(col).cast(pl.Decimal(precision=18, scale=8))
            ])

        # Ensure UTC timestamps
        df = df.with_columns([
            pl.col("timestamp").dt.convert_time_zone("UTC")
        ])

        return df.sort("timestamp")

    def validate(self, df: pl.DataFrame) -> bool:
        """Validate data quality and relationships."""
        try:
            # Built-in validation
            validate_ohlcv_relationships(df)

            # TODO: Add custom validations
            if len(df) == 0:
                raise ValidationError("Empty dataset returned")

            return True

        except ValidationError as e:
            self._log_validation_failure(e)
            raise

    async def _fetch_from_api(
        self, symbols, start_date, end_date, resolution
    ):
        """Private method to call provider API."""
        # TODO: Implement actual API call
        raise NotImplementedError("Implement API call logic")
```

## Registration

### Automatic Discovery

Place your adapter in `rustybt/data/adapters/` and it will be auto-discovered:

```python
from rustybt.data.adapters.registry import AdapterRegistry

# Discover all adapters
AdapterRegistry.discover_adapters()

# List available adapters
print(AdapterRegistry.list_adapters())
# Output: ['MyDataAdapter', 'CCXTAdapter', 'YFinanceAdapter', ...]

# Get adapter class
adapter_class = AdapterRegistry.get_adapter("MyDataAdapter")
adapter = adapter_class(api_key="your_key")
```

### Manual Registration

```python
from rustybt.data.adapters.registry import AdapterRegistry

# Register manually
AdapterRegistry.register(MyDataAdapter)
```

## Best Practices

1. **Always use Decimal for prices:** Never use floats for financial calculations
2. **Log all operations:** Use structlog for structured logging
3. **Handle rate limits gracefully:** Use built-in rate limiter
4. **Validate early:** Call `validate()` immediately after `standardize()`
5. **Test with real data:** Use actual API responses in integration tests
6. **Document resolution formats:** Clearly specify supported resolutions ("1d", "1h", etc.)
7. **Cache API credentials:** Don't hardcode API keys, use environment variables
8. **Handle pagination:** Implement pagination for large date ranges
9. **Monitor performance:** Log fetch durations and data sizes

## Resources

- **BaseDataAdapter Source:** `BaseDataAdapter` class
- **Adapter Registry:** adapter registry
- **Example Adapters:** See the [Examples section](../examples/README.md) for CCXT, YFinance, and CSV adapter examples

---

**Need Help?** Check existing adapters in `rustybt/data/adapters/` for reference implementations.
