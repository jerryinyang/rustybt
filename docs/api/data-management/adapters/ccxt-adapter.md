# CCXT Adapter - Cryptocurrency Exchange Data

**Module**: `rustybt.data.adapters.ccxt_adapter`

## Overview

`CCXTAdapter` provides unified access to 100+ cryptocurrency exchanges through the [CCXT library](https://github.com/ccxt/ccxt). Fetch historical OHLCV data from Binance, Coinbase, Kraken, and many other exchanges with a standardized interface, automatic pagination, rate limiting, and error handling.

## Supported Exchanges

The CCXT library supports 100+ exchanges. Common exchanges include:

| Exchange | ID | Rate Limits | Markets |
|----------|-----|-------------|---------|
| **Binance** | `binance` | ~1200 req/min | 2000+ pairs |
| **Coinbase** | `coinbase` | ~10 req/sec | 200+ pairs |
| **Kraken** | `kraken` | ~20 req/min | 500+ pairs |
| **Bybit** | `bybit` | ~120 req/min | 500+ pairs |
| **OKX** | `okx` | ~20 req/sec | 500+ pairs |
| **Bitfinex** | `bitfinex` | ~90 req/min | 300+ pairs |

**Full list**: See `ccxt.exchanges` or [CCXT documentation](https://docs.ccxt.com/#/README?id=supported-cryptocurrency-exchange-markets)

## Class Definition

```python
from rustybt.data.adapters.ccxt_adapter import CCXTAdapter

class CCXTAdapter(BaseDataAdapter, DataSource):
    """CCXT adapter for fetching crypto OHLCV data from 100+ exchanges."""
```

## Constructor

```python
def __init__(
    self,
    exchange_id: str = "binance",
    testnet: bool = False,
    api_key: str | None = None,
    api_secret: str | None = None,
) -> None:
```

### Parameters

- **exchange_id** (`str`, default="binance"): Exchange identifier (see CCXT documentation)
- **testnet** (`bool`, default=False): Use testnet/sandbox mode if available
- **api_key** (`str | None`, default=None): API key for private endpoints (optional)
- **api_secret** (`str | None`, default=None): API secret (optional)

### Raises

- **AttributeError**: If exchange_id not supported by CCXT

### Example

```python
from rustybt.data.adapters.ccxt_adapter import CCXTAdapter

# Initialize with default exchange (Binance)
adapter = CCXTAdapter()
print(f"✅ Created CCXT adapter for: {adapter.exchange_id}")

# Initialize with specific exchange
adapter_kraken = CCXTAdapter(exchange_id="kraken")
print(f"✅ Created CCXT adapter for: {adapter_kraken.exchange_id}")

# Initialize with testnet
adapter_testnet = CCXTAdapter(exchange_id="binance", testnet=True)
print(f"✅ Created CCXT adapter (testnet): {adapter_testnet.testnet}")
```

## Supported Resolutions

```python
import polars as pl

# Resolution mapping
RESOLUTION_MAPPING = {
    "1m": "1m",      # 1 minute
    "5m": "5m",      # 5 minutes
    "15m": "15m",    # 15 minutes
    "30m": "30m",    # 30 minutes
    "1h": "1h",      # 1 hour
    "2h": "2h",      # 2 hours
    "4h": "4h",      # 4 hours
    "1d": "1d",      # 1 day
    "1w": "1w",      # 1 week
}

print(f"✅ Supported resolutions: {list(RESOLUTION_MAPPING.keys())}")
```

## Methods

### fetch()

```python
async def fetch(
    self,
    symbols: list[str],
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    resolution: str,
) -> pl.DataFrame:
```

Fetch OHLCV data from CCXT exchange with automatic pagination.

**Parameters**:
- **symbols** (`list[str]`): Trading pairs (e.g., `["BTC/USDT", "ETH/USDT"]`)
- **start_date** (`pd.Timestamp`): Start date for data range
- **end_date** (`pd.Timestamp`): End date for data range
- **resolution** (`str`): Time resolution (e.g., `"1d"`, `"1h"`, `"1m"`)

**Returns**:
- `pl.DataFrame`: Polars DataFrame with standardized OHLCV schema

**Raises**:
- `NetworkError`: If API request fails
- `InvalidDataError`: If symbol is invalid or delisted
- `ValueError`: If resolution is not supported

**Example**:

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.ccxt_adapter import CCXTAdapter

async def fetch_crypto_data():
    # Initialize adapter for Binance
    adapter = CCXTAdapter(exchange_id="binance")

    # Fetch Bitcoin and Ethereum data
    data = await adapter.fetch(
        symbols=["BTC/USDT", "ETH/USDT"],
        start_date=pd.Timestamp("2024-01-01"),
        end_date=pd.Timestamp("2024-01-02"),
        resolution="1h"
    )

    print(f"✅ Fetched {len(data)} rows")
    print(f"Symbols: {data['symbol'].unique().to_list()}")
    print(f"Date range: {data['timestamp'].min()} to {data['timestamp'].max()}")
    print(f"\\nFirst few rows:")
    print(data.head())

    return data

# Run the async function
data = asyncio.run(fetch_crypto_data())
```

## Common Usage Patterns

### Basic Usage

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.ccxt_adapter import CCXTAdapter

async def basic_usage():
    # Create adapter
    adapter = CCXTAdapter(exchange_id="binance")

    # Fetch daily data
    data = await adapter.fetch(
        symbols=["BTC/USDT"],
        start_date=pd.Timestamp("2024-01-01"),
        end_date=pd.Timestamp("2024-01-31"),
        resolution="1d"
    )

    print(f"✅ Fetched {len(data)} daily bars for BTC/USDT")
    return data

# Run
data = asyncio.run(basic_usage())
```

### Multiple Exchanges

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.ccxt_adapter import CCXTAdapter

async def compare_exchanges():
    # Create adapters for different exchanges
    binance = CCXTAdapter(exchange_id="binance")
    kraken = CCXTAdapter(exchange_id="kraken")
    coinbase = CCXTAdapter(exchange_id="coinbase")

    # Fetch same data from different exchanges
    start = pd.Timestamp("2024-01-01")
    end = pd.Timestamp("2024-01-02")

    binance_data = await binance.fetch(["BTC/USDT"], start, end, "1h")
    kraken_data = await kraken.fetch(["BTC/USD"], start, end, "1h")
    coinbase_data = await coinbase.fetch(["BTC/USD"], start, end, "1h")

    print(f"✅ Binance: {len(binance_data)} bars")
    print(f"✅ Kraken: {len(kraken_data)} bars")
    print(f"✅ Coinbase: {len(coinbase_data)} bars")

    return {
        "binance": binance_data,
        "kraken": kraken_data,
        "coinbase": coinbase_data,
    }

# Run
data = asyncio.run(compare_exchanges())
```

### High-Frequency Data

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.ccxt_adapter import CCXTAdapter

async def fetch_minute_data():
    adapter = CCXTAdapter(exchange_id="binance")

    # Fetch 1-minute data (high frequency)
    data = await adapter.fetch(
        symbols=["BTC/USDT"],
        start_date=pd.Timestamp("2024-01-01 00:00:00"),
        end_date=pd.Timestamp("2024-01-01 06:00:00"),  # 6 hours
        resolution="1m"
    )

    print(f"✅ Fetched {len(data)} minute bars")
    print(f"Expected ~360 bars (6 hours * 60 minutes)")

    return data

# Run
data = asyncio.run(fetch_minute_data())
```

### Multiple Pairs from Same Exchange

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.ccxt_adapter import CCXTAdapter

async def fetch_multiple_pairs():
    adapter = CCXTAdapter(exchange_id="binance")

    # Fetch multiple trading pairs
    pairs = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT"]

    data = await adapter.fetch(
        symbols=pairs,
        start_date=pd.Timestamp("2024-01-01"),
        end_date=pd.Timestamp("2024-01-07"),
        resolution="1d"
    )

    # Group by symbol to see counts
    for symbol in pairs:
        symbol_data = data.filter(pl.col("symbol") == symbol)
        print(f"✅ {symbol}: {len(symbol_data)} bars")

    return data

# Run
import polars as pl
data = asyncio.run(fetch_multiple_pairs())
```

## Symbol Formats

The CCXT adapter automatically normalizes various symbol formats:

```python
from rustybt.data.adapters.ccxt_adapter import CCXTAdapter

adapter = CCXTAdapter(exchange_id="binance")

# All these formats work and are normalized to "BTC/USDT"
symbol_formats = [
    "BTC/USDT",     # ✅ Standard CCXT format
    "BTC-USDT",     # ✅ Dash format (converted)
    "BTCUSDT",      # ✅ Concatenated format (converted)
]

print(f"✅ Symbol normalization examples:")
for symbol in symbol_formats:
    normalized = adapter._normalize_symbol(symbol)
    print(f"  {symbol:12} → {normalized}")
```

## Rate Limiting

CCXT adapter uses exchange-specific rate limits automatically:

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.ccxt_adapter import CCXTAdapter

async def demonstrate_rate_limiting():
    # Initialize adapter (rate limits set automatically)
    adapter = CCXTAdapter(exchange_id="binance")

    # The adapter automatically spaces requests to respect rate limits
    symbols = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "ADA/USDT"]

    start = pd.Timestamp("2024-01-01")
    end = pd.Timestamp("2024-01-02")

    print("Fetching data with automatic rate limiting...")
    data = await adapter.fetch(symbols, start, end, "1h")

    print(f"✅ Fetched {len(data)} rows for {len(symbols)} symbols")
    print(f"Rate limiter automatically spaced requests")

    return data

# Run
data = asyncio.run(demonstrate_rate_limiting())
```

## Error Handling

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.ccxt_adapter import CCXTAdapter
from rustybt.data.adapters.base import NetworkError, InvalidDataError

async def handle_errors():
    adapter = CCXTAdapter(exchange_id="binance")

    try:
        # This will fail - invalid symbol
        data = await adapter.fetch(
            symbols=["INVALID/PAIR"],
            start_date=pd.Timestamp("2024-01-01"),
            end_date=pd.Timestamp("2024-01-02"),
            resolution="1d"
        )
    except InvalidDataError as e:
        print(f"✅ Caught invalid symbol error: {e}")

    try:
        # This will fail - unsupported resolution
        data = await adapter.fetch(
            symbols=["BTC/USDT"],
            start_date=pd.Timestamp("2024-01-01"),
            end_date=pd.Timestamp("2024-01-02"),
            resolution="3h"  # Not supported
        )
    except ValueError as e:
        print(f"✅ Caught unsupported resolution error: {e}")

    print("✅ Error handling demonstrated")

# Run
asyncio.run(handle_errors())
```

## Pagination

The CCXT adapter automatically handles pagination for large date ranges:

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.ccxt_adapter import CCXTAdapter

async def demonstrate_pagination():
    adapter = CCXTAdapter(exchange_id="binance")

    # Fetch large date range (will trigger pagination)
    # Most exchanges limit responses to 500-1000 bars per request
    data = await adapter.fetch(
        symbols=["BTC/USDT"],
        start_date=pd.Timestamp("2023-01-01"),
        end_date=pd.Timestamp("2024-01-01"),  # 1 year of daily data
        resolution="1d"
    )

    print(f"✅ Fetched {len(data)} bars with automatic pagination")
    print(f"Expected ~365 bars for 1 year of daily data")

    return data

# Run
data = asyncio.run(demonstrate_pagination())
```

## Testnet/Sandbox Mode

Some exchanges support testnet mode for testing without real money:

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.ccxt_adapter import CCXTAdapter

async def use_testnet():
    # Initialize with testnet mode
    adapter = CCXTAdapter(
        exchange_id="binance",
        testnet=True  # Use Binance testnet
    )

    print(f"✅ Testnet mode: {adapter.testnet}")
    print(f"Use testnet for development and testing without real funds")

# Run
asyncio.run(use_testnet())
```

## Best Practices

### 1. Use Appropriate Resolutions

```python
# ❌ DON'T: Request 1-minute data for years
# data = await adapter.fetch(symbols, pd.Timestamp("2020-01-01"), pd.Timestamp("2024-01-01"), "1m")

# ✅ DO: Use appropriate resolution for time range
# For years: use "1d" or "1w"
# For months: use "1h" or "1d"
# For days: use "1m", "5m", or "15m"

print("✅ Use resolution appropriate for time range")
```

### 2. Handle Exchange-Specific Limitations

```python
# Different exchanges have different limitations:
# - Binance: Good for high-frequency data (1m, 5m)
# - Kraken: Limited to 720 bars per request
# - Coinbase: Public endpoints have low rate limits

print("✅ Be aware of exchange-specific limitations")
```

### 3. Cache Data Locally

```python
# ❌ DON'T: Fetch same data repeatedly
# for i in range(10):
#     data = await adapter.fetch(...)  # Wasteful API calls

# ✅ DO: Cache data and reuse
# data = await adapter.fetch(...)
# data.write_parquet("cache/btc_usdt_daily.parquet")
# cached_data = pl.read_parquet("cache/btc_usdt_daily.parquet")

print("✅ Cache data locally to avoid redundant API calls")
```

## Common Issues and Troubleshooting

### Issue: Symbol Not Found

**Problem**: `InvalidDataError: Symbol BTC/USDT not found on kraken`

**Solution**: Different exchanges use different symbol formats:

```python
# Binance uses USDT
# symbols = ["BTC/USDT"]

# Kraken uses USD (not USDT)
# symbols = ["BTC/USD"]

# Coinbase uses USD
# symbols = ["BTC/USD"]

print("✅ Check exchange-specific symbol formats")
```

### Issue: Rate Limit Exceeded

**Problem**: `RateLimitError: Rate limit exceeded on binance`

**Solution**: The adapter has automatic rate limiting, but you may need to add delays:

```python
import asyncio

# Add delay between large requests
async def fetch_with_delay():
    adapter = CCXTAdapter(exchange_id="binance")

    all_data = []
    for symbol in ["BTC/USDT", "ETH/USDT", "BNB/USDT"]:
        data = await adapter.fetch([symbol], start, end, "1d")
        all_data.append(data)
        await asyncio.sleep(1)  # Additional delay between symbols

    return all_data

print("✅ Add delays between large requests if needed")
```

### Issue: Empty Data Returned

**Problem**: DataFrame is empty but no error raised

**Possible causes**:
1. Date range too recent (exchange doesn't have data yet)
2. Symbol delisted during requested period
3. Exchange doesn't support requested resolution

```python
# Check if data is empty
# if len(data) == 0:
#     print(f"No data returned - check date range and symbol validity")

print("✅ Validate date ranges and symbol availability")
```

## See Also

- [Base Adapter Framework](./base-adapter.md) - Core adapter interface
- [Data Catalog](../catalog/README.md) - Bundle metadata management
- [YFinance Adapter](./yfinance-adapter.md) - Stock and ETF data
- [CSV Adapter](./csv-adapter.md) - Local file data
