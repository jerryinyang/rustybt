# AlphaVantage Adapter - Global Market Data

**Module**: `rustybt.data.adapters.alphavantage_adapter`

## Overview

`AlphaVantageAdapter` provides access to Alpha Vantage's API for global stocks, forex, and cryptocurrency data. Alpha Vantage offers both free and premium tiers with delayed market data across multiple asset classes.

## Supported Asset Classes

| Asset Class | Supported | Symbol Format |
|-------------|-----------|---------------|
| **Global Stocks** | ✅ Yes | `AAPL`, `MSFT`, `IBM.LON` |
| **Forex** | ✅ Yes | `EUR/USD`, `GBP/JPY` |
| **Crypto** | ✅ Yes | `BTC`, `ETH`, `SOL` |

## Class Definition

```python
from rustybt.data.adapters.alphavantage_adapter import AlphaVantageAdapter

class AlphaVantageAdapter(BaseAPIProviderAdapter, DataSource):
    """Alpha Vantage API adapter for stocks, forex, and crypto."""
```

## Constructor

```python
def __init__(
    self,
    tier: str = "free",
    asset_type: str = "stocks",
) -> None:
```

### Parameters

- **tier** (`str`, default="free"): Subscription tier - `"free"` or `"premium"`
- **asset_type** (`str`, default="stocks"): Asset type - `"stocks"`, `"forex"`, or `"crypto"`

### Tier Limits

| Tier | Requests/Minute | Requests/Day | Cost |
|------|-----------------|--------------|------|
| **Free** | 5 | 500 | Free |
| **Premium** | 75 | 1,200 | $49.99/month |

### Authentication

Requires `ALPHAVANTAGE_API_KEY` environment variable. Get your API key from [alphavantage.co](https://www.alphavantage.co/support/#api-key).

```bash
export ALPHAVANTAGE_API_KEY="your_api_key_here"
```

### Example

```python
import os
from rustybt.data.adapters.alphavantage_adapter import AlphaVantageAdapter

os.environ["ALPHAVANTAGE_API_KEY"] = "your_key"

# Stocks adapter (free tier)
adapter_stocks = AlphaVantageAdapter(tier="free", asset_type="stocks")
print(f"✅ Created stocks adapter: {adapter_stocks.tier} tier")

# Forex adapter (premium tier)
adapter_forex = AlphaVantageAdapter(tier="premium", asset_type="forex")
print(f"✅ Created forex adapter: {adapter_forex.tier} tier")

# Crypto adapter
adapter_crypto = AlphaVantageAdapter(tier="free", asset_type="crypto")
print(f"✅ Created crypto adapter")
```

## Supported Resolutions

```python
# Intraday intervals
INTRADAY_INTERVALS = {
    "1m": "1min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "60min",
}

# Daily data
# "1d" - daily bars

print(f"✅ Supported: {list(INTRADAY_INTERVALS.keys())} + ['1d']")
```

## Methods

### fetch_ohlcv()

```python
async def fetch_ohlcv(
    self,
    symbol: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    timeframe: str,
) -> pl.DataFrame:
```

Fetch OHLCV data from Alpha Vantage API.

**Parameters**:
- **symbol** (`str`): Symbol (stocks: `"AAPL"`, forex: `"EUR/USD"`, crypto: `"BTC"`)
- **start_date** (`pd.Timestamp`): Start date
- **end_date** (`pd.Timestamp`): End date
- **timeframe** (`str`): Time resolution

**Example**:

```python
import asyncio
import os
import pandas as pd
from rustybt.data.adapters.alphavantage_adapter import AlphaVantageAdapter

async def fetch_stock():
    os.environ["ALPHAVANTAGE_API_KEY"] = "your_key"

    adapter = AlphaVantageAdapter(tier="free", asset_type="stocks")

    data = await adapter.fetch_ohlcv(
        symbol="AAPL",
        start_date=pd.Timestamp("2024-01-02"),
        end_date=pd.Timestamp("2024-01-31"),
        timeframe="1d"
    )

    print(f"✅ Fetched {len(data)} daily bars")
    return data

data = asyncio.run(fetch_stock())
```

## Common Usage Patterns

### Fetch Global Stocks

```python
import asyncio
import os
import pandas as pd
from rustybt.data.adapters.alphavantage_adapter import AlphaVantageAdapter

async def fetch_global_stocks():
    os.environ["ALPHAVANTAGE_API_KEY"] = "your_key"

    adapter = AlphaVantageAdapter(tier="free", asset_type="stocks")

    # US stock
    data_us = await adapter.fetch_ohlcv(
        symbol="AAPL",
        start_date=pd.Timestamp("2024-01-02"),
        end_date=pd.Timestamp("2024-01-31"),
        timeframe="1d"
    )

    print(f"✅ US: {len(data_us)} bars")

    # London stock (suffix with exchange code)
    data_uk = await adapter.fetch_ohlcv(
        symbol="IBM.LON",
        start_date=pd.Timestamp("2024-01-02"),
        end_date=pd.Timestamp("2024-01-31"),
        timeframe="1d"
    )

    print(f"✅ UK: {len(data_uk)} bars")

data = asyncio.run(fetch_global_stocks())
```

### Fetch Forex Data

```python
import asyncio
import os
import pandas as pd
from rustybt.data.adapters.alphavantage_adapter import AlphaVantageAdapter

async def fetch_forex():
    os.environ["ALPHAVANTAGE_API_KEY"] = "your_key"

    # Forex adapter
    adapter = AlphaVantageAdapter(tier="free", asset_type="forex")

    # Fetch EUR/USD (must use slash format)
    data = await adapter.fetch_ohlcv(
        symbol="EUR/USD",
        start_date=pd.Timestamp("2024-01-02"),
        end_date=pd.Timestamp("2024-01-31"),
        timeframe="1d"
    )

    print(f"✅ Fetched {len(data)} daily forex bars")
    return data

data = asyncio.run(fetch_forex())
```

### Fetch Cryptocurrency Data

```python
import asyncio
import os
import pandas as pd
from rustybt.data.adapters.alphavantage_adapter import AlphaVantageAdapter

async def fetch_crypto():
    os.environ["ALPHAVANTAGE_API_KEY"] = "your_key"

    # Crypto adapter
    adapter = AlphaVantageAdapter(tier="free", asset_type="crypto")

    # Fetch BTC data (quotes in USD)
    data = await adapter.fetch_ohlcv(
        symbol="BTC",
        start_date=pd.Timestamp("2024-01-02"),
        end_date=pd.Timestamp("2024-01-31"),
        timeframe="1d"
    )

    print(f"✅ Fetched {len(data)} daily crypto bars")
    return data

data = asyncio.run(fetch_crypto())
```

### Intraday Data

```python
import asyncio
import os
import pandas as pd
from rustybt.data.adapters.alphavantage_adapter import AlphaVantageAdapter

async def fetch_intraday():
    os.environ["ALPHAVANTAGE_API_KEY"] = "your_key"

    adapter = AlphaVantageAdapter(tier="premium", asset_type="stocks")

    # Fetch 5-minute bars
    data = await adapter.fetch_ohlcv(
        symbol="SPY",
        start_date=pd.Timestamp("2024-01-02"),
        end_date=pd.Timestamp("2024-01-02"),
        timeframe="5m"
    )

    print(f"✅ Fetched {len(data)} 5-minute bars")
    return data

data = asyncio.run(fetch_intraday())
```

## Rate Limiting

Alpha Vantage has strict rate limits:

```python
# Free tier: Only 5 requests per minute!
# This is very restrictive - plan your requests carefully

print("⚠️  Free tier: 5 req/min, 500 req/day")
print("💡 Premium tier: 75 req/min, 1,200 req/day")
print("Consider premium tier for production systems")
```

## Error Handling

```python
import asyncio
import os
import pandas as pd
from rustybt.data.adapters.alphavantage_adapter import AlphaVantageAdapter
from rustybt.data.adapters.api_provider_base import (
    QuotaExceededError,
    SymbolNotFoundError,
    AuthenticationError
)

async def handle_errors():
    # Auth error
    try:
        os.environ.pop("ALPHAVANTAGE_API_KEY", None)
        adapter = AlphaVantageAdapter()
    except AuthenticationError as e:
        print(f"✅ Caught auth error: {e}")

    os.environ["ALPHAVANTAGE_API_KEY"] = "your_key"
    adapter = AlphaVantageAdapter(tier="free", asset_type="stocks")

    # Symbol not found
    try:
        data = await adapter.fetch_ohlcv(
            symbol="INVALID",
            start_date=pd.Timestamp("2024-01-02"),
            end_date=pd.Timestamp("2024-01-05"),
            timeframe="1d"
        )
    except SymbolNotFoundError as e:
        print(f"✅ Caught symbol error: {e}")

    # Rate limit exceeded
    try:
        # Make too many requests
        for i in range(10):
            data = await adapter.fetch_ohlcv(
                symbol="AAPL",
                start_date=pd.Timestamp("2024-01-02"),
                end_date=pd.Timestamp("2024-01-05"),
                timeframe="1d"
            )
    except QuotaExceededError as e:
        print(f"✅ Caught rate limit error: {e}")

asyncio.run(handle_errors())
```

## Best Practices

### 1. Free Tier is Very Restrictive

```python
# ❌ DON'T: Use free tier for production
# Only 5 requests per minute!

# ✅ DO: Use premium tier for production
adapter = AlphaVantageAdapter(tier="premium", asset_type="stocks")

print("⚠️  Free tier suitable for testing only")
```

### 2. Forex Requires Slash Format

```python
# ✅ DO: Use slash format for forex pairs
# adapter = AlphaVantageAdapter(asset_type="forex")
# data = await adapter.fetch_ohlcv("EUR/USD", ...)

# ❌ DON'T: Use other formats
# data = await adapter.fetch_ohlcv("EURUSD", ...)  # Will fail

print("✅ Forex symbols must be in XXX/YYY format")
```

### 3. Global Stock Exchange Codes

```python
# US stocks: no suffix
# symbol = "AAPL"

# London: .LON suffix
# symbol = "IBM.LON"

# Toronto: .TRT suffix
# symbol = "SHOP.TRT"

print("✅ Use exchange suffixes for non-US stocks")
```

## Common Issues

### Issue: Rate Limit Exceeded

**Problem**: `QuotaExceededError: Alpha Vantage rate limit exceeded`

**Solution**: Free tier has only 5 req/min. Space out requests or upgrade to premium.

### Issue: Invalid Forex Symbol

**Problem**: `ValueError: Forex symbol must be in format 'XXX/YYY'`

**Solution**: Use slash format: `"EUR/USD"`, not `"EURUSD"`

### Issue: No Live Streaming

**Problem**: Need real-time data

**Solution**: Alpha Vantage provides delayed data only. For real-time, use Polygon or Alpaca.

## See Also

- [Base Adapter Framework](./base-adapter.md) - Core adapter interface
- [Polygon Adapter](./polygon-adapter.md) - Real-time alternative
- [YFinance Adapter](./yfinance-adapter.md) - Free alternative for US stocks
