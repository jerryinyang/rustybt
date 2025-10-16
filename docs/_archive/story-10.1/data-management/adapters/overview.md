# Data Adapters Overview

Data adapters provide standardized interfaces for fetching market data from various external sources. All adapters share common functionality (rate limiting, retry logic, validation) while supporting source-specific features.

## Quick Comparison

| Adapter | Asset Classes | Historical Data | Real-time | Rate Limiting | API Key Required |
|---------|---------------|-----------------|-----------|---------------|------------------|
| **[CCXT](ccxt.md)** | Crypto | ✅ Yes | ⚡ Partial | ✅ Per-exchange | ❌ Public data |
| **[YFinance](yfinance.md)** | Stocks, ETFs, Forex | ✅ Yes | ⚡ 15min delay | ✅ Built-in | ❌ No |
| **[CSV](csv.md)** | Any | ✅ Yes | ❌ No | ❌ N/A | ❌ No |
| **[Polygon](polygon.md)** | Stocks, Crypto, Forex | ✅ Yes | ✅ Yes | ✅ Built-in | ✅ Yes |
| **[Alpaca](alpaca.md)** | Stocks, Crypto | ✅ Yes | ✅ Yes | ✅ Built-in | ✅ Yes |
| **[AlphaVantage](alphavantage.md)** | Stocks, Forex, Crypto | ✅ Yes | ❌ No | ✅ Built-in | ✅ Yes |

## Adapter Selection Guide

### Use CCXT Adapter When:
- Trading or analyzing cryptocurrencies
- Need access to 100+ exchanges
- Require exchange-specific features (funding rates, perpetuals)
- Working with DeFi or spot markets

**Pros**: Unified API for all exchanges, comprehensive coverage, active development
**Cons**: Performance varies by exchange, rate limits differ per exchange

### Use YFinance Adapter When:
- Analyzing stocks, ETFs, or major indices
- Prototyping strategies without API costs
- Need dividend and split-adjusted data
- Working with forex major pairs

**Pros**: Free, no API key, extensive historical data, handles corporate actions
**Cons**: 15-minute delayed quotes, rate limits enforced by Yahoo, occasional reliability issues

### Use CSV Adapter When:
- Importing proprietary or custom datasets
- Working with backtesting data from external sources
- Need flexible schema mapping
- Processing one-time data imports

**Pros**: Maximum flexibility, no network dependencies, works with any format
**Cons**: Manual data updates, no built-in data validation from source

### Use Polygon Adapter When:
- Need professional-grade market data
- Require real-time stock/crypto/forex data
- Working with tick-level or second-level data
- Building production trading systems

**Pros**: High-quality data, real-time support, comprehensive coverage, excellent documentation
**Cons**: Requires paid subscription for most features

### Use Alpaca Adapter When:
- Building commission-free trading strategies
- Need integrated broker + data source
- Working with US equities or crypto
- Want paper trading with real data

**Pros**: Free real-time data for account holders, integrated broker, commission-free
**Cons**: Limited to US markets and specific crypto pairs

### Use AlphaVantage Adapter When:
- Need fundamental data (earnings, financials)
- Require technical indicators from API
- Working with international stocks
- Need forex and commodity data

**Pros**: Fundamental data included, indicators pre-calculated, global coverage
**Cons**: Strict rate limits on free tier, limited historical depth

## Common Adapter Interface

All adapters inherit from `BaseDataAdapter` and implement a common interface:

```python
from rustybt.data.adapters import BaseDataAdapter
import pandas as pd

class BaseDataAdapter:
    """Base interface for all data adapters."""

    async def fetch(
        self,
        symbols: list[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        resolution: str = "1d"
    ) -> pl.DataFrame:
        """Fetch OHLCV data for symbols.

        Args:
            symbols: List of ticker symbols to fetch
            start_date: Start timestamp (inclusive)
            end_date: End timestamp (inclusive)
            resolution: Data resolution ('1m', '5m', '1h', '1d', etc.)

        Returns:
            Polars DataFrame with standardized OHLCV schema

        Raises:
            NetworkError: Network connectivity issues
            RateLimitError: Rate limit exceeded
            InvalidDataError: Data validation failed
        """
        pass

    async def fetch_batch(
        self,
        symbols: list[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        resolution: str = "1d",
        batch_size: int = 10
    ) -> pl.DataFrame:
        """Fetch data for multiple symbols in batches."""
        pass

    def validate(self, data: pl.DataFrame) -> bool:
        """Validate fetched data against schema and relationships."""
        pass
```

## Standardized OHLCV Schema

All adapters return data in a standardized Polars DataFrame schema:

```python
schema = {
    'timestamp': pl.Datetime('us', 'UTC'),  # Microsecond precision UTC timestamp
    'symbol': pl.Utf8,                       # Normalized symbol
    'sid': pl.Int64,                         # Unique asset ID
    'open': pl.Decimal(precision=18, scale=8),   # Opening price
    'high': pl.Decimal(precision=18, scale=8),   # Highest price
    'low': pl.Decimal(precision=18, scale=8),    # Lowest price
    'close': pl.Decimal(precision=18, scale=8),  # Closing price
    'volume': pl.Decimal(precision=18, scale=8), # Trading volume
}
```

**Key Features:**
- **Decimal Precision**: All prices use Decimal(18,8) for financial accuracy
- **UTC Timestamps**: All times normalized to UTC with microsecond precision
- **Symbol Normalization**: Consistent symbol formatting across sources
- **Asset IDs**: Unique `sid` assigned for internal tracking

## Common Features

### 1. Rate Limiting

All adapters include built-in rate limiting to prevent API throttling:

```python
from rustybt.data.adapters import CCXTAdapter

# Configure rate limiting
adapter = CCXTAdapter(
    exchange_id='binance',
    rate_limit_per_second=10  # Max 10 requests/second
)

# Rate limiting handled automatically
df = await adapter.fetch(symbols=['BTC/USDT'], ...)
```

### 2. Retry Logic

Automatic retry with exponential backoff for transient errors:

```python
# Retry configuration in base adapter
retry_config = {
    'max_retries': 3,
    'backoff_factor': 2.0,  # 1s, 2s, 4s
    'retry_on': [NetworkError, RateLimitError]
}
```

### 3. Data Validation

Built-in validation ensures data integrity:

```python
# Automatic validation checks:
# - OHLCV relationships (high >= low, high >= open, etc.)
# - Temporal consistency (no gaps, proper ordering)
# - Schema compliance (correct types, required columns)
# - Decimal precision (financial accuracy)

# Validation happens automatically
df = await adapter.fetch(...)  # Raises InvalidDataError if validation fails
```

### 4. Batch Processing

Efficient batch fetching for multiple symbols:

```python
# Fetch 100 symbols efficiently
df = await adapter.fetch_batch(
    symbols=list_of_100_symbols,
    start_date=pd.Timestamp('2024-01-01'),
    end_date=pd.Timestamp('2024-01-31'),
    batch_size=10  # Process 10 at a time
)
```

### 5. Progress Tracking

Monitor progress for long-running operations:

```python
from rustybt.data.adapters import CCXTAdapter

adapter = CCXTAdapter(exchange_id='binance')

# Enable progress callback
def progress_callback(current: int, total: int, symbol: str):
    print(f"Progress: {current}/{total} - Fetching {symbol}")

adapter.set_progress_callback(progress_callback)

df = await adapter.fetch_batch(symbols=large_symbol_list, ...)
# Output:
# Progress: 1/100 - Fetching BTC/USDT
# Progress: 2/100 - Fetching ETH/USDT
# ...
```

## Error Handling

### Exception Hierarchy

```python
from rustybt.data.adapters.base import (
    DataAdapterError,      # Base exception
    NetworkError,          # Network issues
    RateLimitError,        # Rate limit exceeded
    InvalidDataError,      # Data validation failed
    ValidationError,       # Schema validation failed
)
```

### Common Error Patterns

```python
from rustybt.data.adapters import CCXTAdapter
from rustybt.data.adapters.base import NetworkError, RateLimitError

adapter = CCXTAdapter(exchange_id='binance')

try:
    df = await adapter.fetch(symbols=['BTC/USDT'], ...)
except RateLimitError as e:
    # Handle rate limit (e.g., wait and retry)
    logger.warning(f"Rate limited, waiting {e.reset_after}s")
    await asyncio.sleep(e.reset_after)
    df = await adapter.fetch(...)
except NetworkError as e:
    # Handle network issues
    logger.error(f"Network error: {e}")
    # Implement exponential backoff or alert
except InvalidDataError as e:
    # Data validation failed
    logger.error(f"Invalid data received: {e}")
    # Skip or use fallback data source
```

## Performance Considerations

### Memory Management

```python
# Use lazy evaluation for large datasets
adapter = YFinanceAdapter()

# Fetch in chunks to control memory
for chunk_start, chunk_end in date_ranges:
    df_chunk = await adapter.fetch(
        symbols=['AAPL'],
        start_date=chunk_start,
        end_date=chunk_end
    )
    # Process chunk immediately
    process_chunk(df_chunk)
```

### Parallel Fetching

```python
import asyncio
from rustybt.data.adapters import CCXTAdapter

adapter = CCXTAdapter(exchange_id='binance')

# Fetch multiple symbols in parallel
async def fetch_all_symbols(symbols: list[str]):
    tasks = [
        adapter.fetch(
            symbols=[symbol],
            start_date=start,
            end_date=end
        )
        for symbol in symbols
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results

# Run parallel fetch
dfs = await fetch_all_symbols(['BTC/USDT', 'ETH/USDT', 'SOL/USDT'])
```

### Caching

```python
from rustybt.data.polars.cache_manager import CacheManager

# Enable caching for expensive API calls
cache = CacheManager(max_memory_mb=512)

# Cached fetch
@cache.cached(ttl_seconds=3600)  # Cache for 1 hour
async def fetch_with_cache(symbol: str):
    return await adapter.fetch(symbols=[symbol], ...)

# First call hits API, subsequent calls use cache
df1 = await fetch_with_cache('BTC/USDT')  # API call
df2 = await fetch_with_cache('BTC/USDT')  # From cache
```

## Registration and Discovery

### Adapter Registry

```python
from rustybt.data.adapters.registry import AdapterRegistry

# Register custom adapter
registry = AdapterRegistry()
registry.register('my_adapter', MyCustomAdapter)

# Discover available adapters
adapters = registry.list_adapters()
print(adapters)  # ['ccxt', 'yfinance', 'csv', 'polygon', 'alpaca', 'alphavantage', 'my_adapter']

# Get adapter by name
adapter_class = registry.get_adapter('ccxt')
adapter = adapter_class(exchange_id='binance')
```

## Next Steps

- **[CCXT Adapter](ccxt.md)** - Detailed documentation for cryptocurrency data
- **[YFinance Adapter](yfinance.md)** - Stocks and ETFs data access
- **[CSV Adapter](csv.md)** - Custom data import
- **[Polygon Adapter](polygon.md)** - Professional market data
- **[Alpaca Adapter](alpaca.md)** - Commission-free trading data
- **[AlphaVantage Adapter](alphavantage.md)** - Fundamental and global data

## Examples

See `examples/data_adapters/` directory for complete working examples:
- `fetch_crypto_data.py` - Cryptocurrency data fetching
- `fetch_stock_data.py` - Stock data fetching
- `import_csv_data.py` - Custom CSV import
- `compare_adapters.py` - Adapter comparison benchmarks
