# CCXT Adapter

The CCXT adapter provides access to cryptocurrency data from 100+ exchanges through the unified CCXT library interface.

## Overview

**Best for**: Cryptocurrency trading strategies, multi-exchange analysis, DeFi data

**Supported Exchanges**: 100+ including Binance, Coinbase, Kraken, Bybit, OKX, Huobi, and more

**Data Types**:
- Spot market OHLCV
- Perpetual futures OHLCV
- Funding rates (exchange-specific)
- Order book snapshots
- Recent trades

## Quick Start

```python
from rustybt.data.adapters import CCXTAdapter
import pandas as pd

# Create adapter for Binance
adapter = CCXTAdapter(exchange_id='binance')

# Fetch Bitcoin and Ethereum data
df = await adapter.fetch(
    symbols=['BTC/USDT', 'ETH/USDT'],
    start_date=pd.Timestamp('2024-01-01'),
    end_date=pd.Timestamp('2024-01-31'),
    resolution='1h'
)

print(df.head())
```

## Configuration

### Basic Configuration

```python
from rustybt.data.adapters import CCXTAdapter

adapter = CCXTAdapter(
    exchange_id='binance',           # Exchange identifier
    testnet=False,                   # Use testnet/sandbox
    api_key=None,                    # API key (optional for public data)
    api_secret=None                  # API secret (optional)
)
```

### Exchange-Specific Configuration

```python
# Binance with API credentials
binance = CCXTAdapter(
    exchange_id='binance',
    api_key=os.getenv('BINANCE_API_KEY'),
    api_secret=os.getenv('BINANCE_API_SECRET')
)

# Coinbase Pro
coinbase = CCXTAdapter(
    exchange_id='coinbasepro',
    api_key=os.getenv('COINBASE_KEY'),
    api_secret=os.getenv('COINBASE_SECRET')
)

# Kraken
kraken = CCXTAdapter(
    exchange_id='kraken',
    api_key=os.getenv('KRAKEN_KEY'),
    api_secret=os.getenv('KRAKEN_SECRET')
)
```

### Testnet Usage

```python
# Use Binance testnet for development
adapter = CCXTAdapter(
    exchange_id='binance',
    testnet=True,
    api_key='testnet_key',
    api_secret='testnet_secret'
)
```

## Supported Resolutions

| Resolution | CCXT Format | Availability | Typical Limit |
|-----------|-------------|--------------|---------------|
| 1 minute | `1m` | Most exchanges | Last 1-7 days |
| 5 minutes | `5m` | Most exchanges | Last 30 days |
| 15 minutes | `15m` | Most exchanges | Last 90 days |
| 30 minutes | `30m` | Some exchanges | Last 180 days |
| 1 hour | `1h` | All exchanges | Last 1-2 years |
| 4 hours | `4h` | All exchanges | Last 2-3 years |
| 1 day | `1d` | All exchanges | Full history |
| 1 week | `1w` | Some exchanges | Full history |

**Note**: Historical data availability varies by exchange. Newer exchanges may have limited history.

## Symbol Format

CCXT uses unified symbol format: `BASE/QUOTE`

### Common Symbol Patterns

```python
# Spot markets
'BTC/USDT'   # Bitcoin vs Tether
'ETH/USDT'   # Ethereum vs Tether
'BTC/USD'    # Bitcoin vs USD
'ETH/BTC'    # Ethereum vs Bitcoin

# Perpetual futures (exchange-specific suffixes)
'BTC/USDT:USDT'  # Binance perpetual
'BTC/USD:BTC'    # BitMEX perpetual
'ETH/USDT:USDT'  # Bybit perpetual

# Futures contracts (with expiry)
'BTC/USDT:USDT-240329'  # March 29, 2024 expiry
```

### Symbol Lookup

```python
# List available markets on an exchange
adapter = CCXTAdapter(exchange_id='binance')
markets = adapter.exchange.load_markets()

# Filter for spot markets
spot_symbols = [
    symbol for symbol, market in markets.items()
    if market['spot']
]

# Filter for perpetual futures
perp_symbols = [
    symbol for symbol, market in markets.items()
    if market.get('future') and market.get('type') == 'swap'
]

print(f"Spot markets: {len(spot_symbols)}")
print(f"Perpetuals: {len(perp_symbols)}")
```

## Usage Examples

### Example 1: Fetch Single Asset

```python
import asyncio
from rustybt.data.adapters import CCXTAdapter
import pandas as pd

async def fetch_bitcoin():
    adapter = CCXTAdapter(exchange_id='binance')

    df = await adapter.fetch(
        symbols=['BTC/USDT'],
        start_date=pd.Timestamp('2024-01-01'),
        end_date=pd.Timestamp('2024-01-31'),
        resolution='1h'
    )

    print(f"Fetched {len(df)} bars")
    print(df.head())

    return df

# Run async function
df = asyncio.run(fetch_bitcoin())
```

### Example 2: Fetch Multiple Assets

```python
async def fetch_crypto_basket():
    adapter = CCXTAdapter(exchange_id='binance')

    # Major cryptocurrencies
    symbols = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'ADA/USDT']

    df = await adapter.fetch_batch(
        symbols=symbols,
        start_date=pd.Timestamp('2024-01-01'),
        end_date=pd.Timestamp('2024-01-31'),
        resolution='1d',
        batch_size=5
    )

    # Group by symbol
    for symbol in symbols:
        symbol_data = df.filter(pl.col('symbol') == symbol)
        print(f"{symbol}: {len(symbol_data)} bars")

    return df

df = asyncio.run(fetch_crypto_basket())
```

### Example 3: Compare Exchanges

```python
async def compare_exchanges():
    """Compare BTC price across multiple exchanges."""
    exchanges = ['binance', 'coinbasepro', 'kraken']

    results = {}
    for exchange_id in exchanges:
        adapter = CCXTAdapter(exchange_id=exchange_id)

        try:
            df = await adapter.fetch(
                symbols=['BTC/USDT'],
                start_date=pd.Timestamp('2024-01-01'),
                end_date=pd.Timestamp('2024-01-02'),
                resolution='1h'
            )
            results[exchange_id] = df['close'].mean()
        except Exception as e:
            print(f"Error fetching from {exchange_id}: {e}")
            results[exchange_id] = None

    print("Average BTC price by exchange:")
    for exchange, avg_price in results.items():
        if avg_price:
            print(f"{exchange}: ${avg_price:,.2f}")

asyncio.run(compare_exchanges())
```

### Example 4: Funding Rate Data (Perpetuals)

```python
async def fetch_funding_rates():
    """Fetch funding rates for perpetual futures."""
    adapter = CCXTAdapter(exchange_id='binance')

    # Note: Funding rates require exchange-specific methods
    exchange = adapter.exchange

    # Fetch current funding rate
    funding = exchange.fetch_funding_rate('BTC/USDT:USDT')

    print(f"Current funding rate: {funding['fundingRate']:.4%}")
    print(f"Next funding time: {funding['fundingTimestamp']}")

    # Fetch historical funding rates
    history = exchange.fetch_funding_rate_history(
        'BTC/USDT:USDT',
        since=int(pd.Timestamp('2024-01-01').timestamp() * 1000),
        limit=100
    )

    # Convert to DataFrame
    df = pl.DataFrame({
        'timestamp': [pd.Timestamp(r['timestamp'], unit='ms') for r in history],
        'funding_rate': [r['fundingRate'] for r in history]
    })

    print(f"Average funding rate: {df['funding_rate'].mean():.4%}")
    return df

df = asyncio.run(fetch_funding_rates())
```

## Rate Limiting

### Understanding Exchange Rate Limits

Each exchange has different rate limits. CCXT handles this automatically, but understanding the limits helps optimize performance.

| Exchange | Public Endpoint | Private Endpoint | Weight System |
|----------|----------------|------------------|---------------|
| Binance | 1200/min | 6000/min | ✅ Yes |
| Coinbase Pro | 3/sec | 5/sec | ❌ No |
| Kraken | 1/sec | 2/sec | ❌ No |
| Bybit | 10/sec | 10/sec | ❌ No |
| OKX | 20/sec | 20/sec | ❌ No |

### Configuring Rate Limiting

```python
# Use conservative rate limiting
adapter = CCXTAdapter(
    exchange_id='binance',
    rate_limit_per_second=10  # Max 10 requests/second
)

# Let CCXT handle rate limiting automatically
adapter = CCXTAdapter(exchange_id='binance')
# CCXT will use exchange-specific rate limits
```

### Handling Rate Limit Errors

```python
from rustybt.data.adapters.base import RateLimitError
import asyncio

async def fetch_with_retry():
    adapter = CCXTAdapter(exchange_id='binance')

    max_retries = 3
    for attempt in range(max_retries):
        try:
            df = await adapter.fetch(
                symbols=['BTC/USDT'],
                start_date=pd.Timestamp('2024-01-01'),
                end_date=pd.Timestamp('2024-01-31')
            )
            return df
        except RateLimitError as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                print(f"Rate limited, waiting {wait_time}s")
                await asyncio.sleep(wait_time)
            else:
                raise
```

## Error Handling

### Common Errors

```python
from rustybt.data.adapters.base import (
    NetworkError,
    RateLimitError,
    InvalidDataError
)
import ccxt

async def robust_fetch():
    adapter = CCXTAdapter(exchange_id='binance')

    try:
        df = await adapter.fetch(
            symbols=['BTC/USDT'],
            start_date=pd.Timestamp('2024-01-01'),
            end_date=pd.Timestamp('2024-01-31')
        )
        return df

    except RateLimitError as e:
        print(f"Rate limit exceeded: {e}")
        # Wait and retry

    except NetworkError as e:
        print(f"Network error: {e}")
        # Check internet connection

    except ccxt.ExchangeNotAvailable as e:
        print(f"Exchange unavailable: {e}")
        # Try different exchange

    except ccxt.InvalidOrder as e:
        print(f"Invalid order parameters: {e}")
        # Fix symbol format or parameters

    except InvalidDataError as e:
        print(f"Data validation failed: {e}")
        # Data quality issue
```

## Performance Optimization

### Parallel Fetching

```python
import asyncio

async def parallel_fetch_example():
    """Fetch data from multiple exchanges in parallel."""

    exchanges = ['binance', 'coinbasepro', 'kraken']
    symbol = 'BTC/USDT'

    async def fetch_from_exchange(exchange_id: str):
        adapter = CCXTAdapter(exchange_id=exchange_id)
        return await adapter.fetch(
            symbols=[symbol],
            start_date=pd.Timestamp('2024-01-01'),
            end_date=pd.Timestamp('2024-01-02'),
            resolution='1h'
        )

    # Run all fetches in parallel
    tasks = [fetch_from_exchange(ex) for ex in exchanges]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Handle results
    for exchange_id, result in zip(exchanges, results):
        if isinstance(result, Exception):
            print(f"{exchange_id}: Error - {result}")
        else:
            print(f"{exchange_id}: {len(result)} bars fetched")

asyncio.run(parallel_fetch_example())
```

### Caching

```python
from rustybt.data.polars.cache_manager import CacheManager

# Enable caching for expensive API calls
cache = CacheManager(max_memory_mb=512)

@cache.cached(ttl_seconds=3600)  # Cache for 1 hour
async def fetch_with_cache(symbol: str, exchange_id: str):
    adapter = CCXTAdapter(exchange_id=exchange_id)
    return await adapter.fetch(
        symbols=[symbol],
        start_date=pd.Timestamp('2024-01-01'),
        end_date=pd.Timestamp('2024-01-31'),
        resolution='1h'
    )

# First call hits API
df1 = await fetch_with_cache('BTC/USDT', 'binance')  # API call

# Second call uses cache
df2 = await fetch_with_cache('BTC/USDT', 'binance')  # From cache
```

## Best Practices

### 1. Symbol Validation

```python
async def validate_symbols():
    """Validate symbols before fetching."""
    adapter = CCXTAdapter(exchange_id='binance')

    # Load markets
    markets = adapter.exchange.load_markets()

    # Check if symbol exists
    symbol = 'BTC/USDT'
    if symbol in markets:
        df = await adapter.fetch(symbols=[symbol], ...)
    else:
        print(f"Symbol {symbol} not found on exchange")
        # Find similar symbols
        similar = [s for s in markets.keys() if 'BTC' in s and 'USDT' in s]
        print(f"Similar symbols: {similar}")
```

### 2. Date Range Splitting

```python
async def fetch_large_date_range():
    """Split large date ranges into chunks for reliability."""
    adapter = CCXTAdapter(exchange_id='binance')

    # Split into monthly chunks
    start = pd.Timestamp('2020-01-01')
    end = pd.Timestamp('2024-01-01')

    date_ranges = pd.date_range(start, end, freq='ME')  # Month end

    all_data = []
    for i in range(len(date_ranges) - 1):
        chunk_start = date_ranges[i]
        chunk_end = date_ranges[i + 1]

        df_chunk = await adapter.fetch(
            symbols=['BTC/USDT'],
            start_date=chunk_start,
            end_date=chunk_end,
            resolution='1d'
        )
        all_data.append(df_chunk)

        # Small delay between chunks
        await asyncio.sleep(0.1)

    # Combine all chunks
    df = pl.concat(all_data)
    return df
```

### 3. Error Recovery

```python
async def fetch_with_fallback():
    """Fetch with fallback to alternative exchanges."""
    exchanges = ['binance', 'coinbasepro', 'kraken']
    symbol = 'BTC/USDT'

    for exchange_id in exchanges:
        try:
            adapter = CCXTAdapter(exchange_id=exchange_id)
            df = await adapter.fetch(
                symbols=[symbol],
                start_date=pd.Timestamp('2024-01-01'),
                end_date=pd.Timestamp('2024-01-31')
            )
            print(f"Successfully fetched from {exchange_id}")
            return df
        except Exception as e:
            print(f"Failed to fetch from {exchange_id}: {e}")
            continue

    raise RuntimeError(f"Failed to fetch {symbol} from all exchanges")
```

## API Reference

### CCXTAdapter Class

```python
class CCXTAdapter(BaseDataAdapter, DataSource):
    """CCXT adapter for cryptocurrency data."""

    def __init__(
        self,
        exchange_id: str = "binance",
        testnet: bool = False,
        api_key: str | None = None,
        api_secret: str | None = None,
    ) -> None:
        """Initialize CCXT adapter."""

    async def fetch(
        self,
        symbols: list[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        resolution: str = "1d"
    ) -> pl.DataFrame:
        """Fetch OHLCV data for symbols."""

    async def fetch_batch(
        self,
        symbols: list[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        resolution: str = "1d",
        batch_size: int = 10
    ) -> pl.DataFrame:
        """Fetch data for multiple symbols in batches."""
```

## See Also

- [Adapter Overview](overview.md) - Common adapter functionality
- [Data Catalog](../catalog/bundles.md) - Storing fetched data
- [Binance Documentation](https://binance-docs.github.io/apidocs/) - Binance API reference
- [CCXT Documentation](https://docs.ccxt.com/) - CCXT library documentation
