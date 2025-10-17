# Alpaca Adapter - US Stock Data

**Module**: `rustybt.data.adapters.alpaca_adapter`

## Overview

`AlpacaAdapter` provides access to Alpaca Markets' US stock market data API. Alpaca offers both a free paper trading data feed (IEX) and a paid live trading data feed (SIP) with real-time quotes and historical bars.

## Supported Assets

| Asset Class | Supported | Data Feed |
|-------------|-----------|-----------|
| **US Stocks** | ✅ Yes | IEX (paper), SIP (live) |
| **Options** | ❌ No | N/A |
| **Forex** | ❌ No | N/A |
| **Crypto** | ❌ No | Use separate Alpaca Crypto API |

## Class Definition

```python
from rustybt.data.adapters.alpaca_adapter import AlpacaAdapter

class AlpacaAdapter(BaseAPIProviderAdapter, DataSource):
    """Alpaca Market Data API v2 adapter for US stocks."""
```

## Constructor

```python
def __init__(self, is_paper: bool = True) -> None:
```

### Parameters

- **is_paper** (`bool`, default=True): Use paper trading endpoint (free IEX feed) if True, live trading endpoint (paid SIP feed) if False

### Authentication

Requires both `ALPACA_API_KEY` and `ALPACA_API_SECRET` environment variables. Get your credentials from [alpaca.markets](https://alpaca.markets).

```bash
export ALPACA_API_KEY="your_api_key_here"
export ALPACA_API_SECRET="your_api_secret_here"
```

### Example

```python
import os
from rustybt.data.adapters.alpaca_adapter import AlpacaAdapter

# Set API credentials
os.environ["ALPACA_API_KEY"] = "your_key"
os.environ["ALPACA_API_SECRET"] = "your_secret"

# Paper trading (free IEX feed)
adapter_paper = AlpacaAdapter(is_paper=True)
print(f"✅ Created paper trading adapter (IEX feed)")

# Live trading (paid SIP feed)
adapter_live = AlpacaAdapter(is_paper=False)
print(f"✅ Created live trading adapter (SIP feed)")
```

## Supported Resolutions

```python
# Timeframe mapping
TIMEFRAME_MAP = {
    "1m": "1Min",
    "5m": "5Min",
    "15m": "15Min",
    "30m": "30Min",
    "1h": "1Hour",
    "1d": "1Day",
}

print(f"✅ Supported timeframes: {list(TIMEFRAME_MAP.keys())}")
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

Fetch OHLCV data for a single US stock symbol.

**Parameters**:
- **symbol** (`str`): Stock symbol (e.g., `"AAPL"`)
- **start_date** (`pd.Timestamp`): Start date
- **end_date** (`pd.Timestamp`): End date
- **timeframe** (`str`): Time resolution (e.g., `"1d"`, `"1h"`, `"1m"`)

**Returns**:
- `pl.DataFrame`: Polars DataFrame with OHLCV data

**Example**:

```python
import asyncio
import os
import pandas as pd
from rustybt.data.adapters.alpaca_adapter import AlpacaAdapter

async def fetch_stock():
    os.environ["ALPACA_API_KEY"] = "your_key"
    os.environ["ALPACA_API_SECRET"] = "your_secret"

    adapter = AlpacaAdapter(is_paper=True)

    data = await adapter.fetch_ohlcv(
        symbol="AAPL",
        start_date=pd.Timestamp("2024-01-02"),
        end_date=pd.Timestamp("2024-01-05"),
        timeframe="1d"
    )

    print(f"✅ Fetched {len(data)} daily bars for AAPL")
    print(data.head())
    return data

data = asyncio.run(fetch_stock())
```

### fetch()

```python
async def fetch(
    self,
    symbols: list[str],
    start: pd.Timestamp,
    end: pd.Timestamp,
    frequency: str,
) -> pl.DataFrame:
```

Fetch OHLCV data for multiple symbols.

**Example**:

```python
import asyncio
import os
import pandas as pd
from rustybt.data.adapters.alpaca_adapter import AlpacaAdapter

async def fetch_multiple():
    os.environ["ALPACA_API_KEY"] = "your_key"
    os.environ["ALPACA_API_SECRET"] = "your_secret"

    adapter = AlpacaAdapter(is_paper=True)

    data = await adapter.fetch(
        symbols=["AAPL", "MSFT", "GOOGL"],
        start=pd.Timestamp("2024-01-02"),
        end=pd.Timestamp("2024-01-05"),
        frequency="1d"
    )

    print(f"✅ Fetched {len(data)} total bars")
    print(f"Symbols: {data['symbol'].unique().to_list()}")
    return data

data = asyncio.run(fetch_multiple())
```

### get_metadata()

```python
def get_metadata(self) -> DataSourceMetadata:
```

Get Alpaca data source metadata.

**Example**:

```python
import os
from rustybt.data.adapters.alpaca_adapter import AlpacaAdapter

os.environ["ALPACA_API_KEY"] = "your_key"
os.environ["ALPACA_API_SECRET"] = "your_secret"

adapter = AlpacaAdapter(is_paper=True)
metadata = adapter.get_metadata()

print(f"✅ Source: {metadata.source_type}")
print(f"API version: {metadata.api_version}")
print(f"Rate limit: {metadata.rate_limit} req/min")
print(f"Supports live: {metadata.supports_live}")
print(f"Data delay: {metadata.data_delay} seconds")
print(f"Feed: {metadata.additional_info['feed']}")
```

## Common Usage Patterns

### Paper Trading (Free)

```python
import asyncio
import os
import pandas as pd
from rustybt.data.adapters.alpaca_adapter import AlpacaAdapter

async def paper_trading():
    os.environ["ALPACA_API_KEY"] = "your_key"
    os.environ["ALPACA_API_SECRET"] = "your_secret"

    # Paper trading uses free IEX feed
    adapter = AlpacaAdapter(is_paper=True)

    data = await adapter.fetch_ohlcv(
        symbol="SPY",
        start_date=pd.Timestamp("2024-01-02"),
        end_date=pd.Timestamp("2024-01-31"),
        timeframe="1d"
    )

    print(f"✅ Fetched {len(data)} daily bars from IEX feed")
    return data

data = asyncio.run(paper_trading())
```

### Live Trading (Paid)

```python
import asyncio
import os
import pandas as pd
from rustybt.data.adapters.alpaca_adapter import AlpacaAdapter

async def live_trading():
    os.environ["ALPACA_API_KEY"] = "your_key"
    os.environ["ALPACA_API_SECRET"] = "your_secret"

    # Live trading uses paid SIP feed (requires subscription)
    adapter = AlpacaAdapter(is_paper=False)

    data = await adapter.fetch_ohlcv(
        symbol="AAPL",
        start_date=pd.Timestamp("2024-01-02"),
        end_date=pd.Timestamp("2024-01-31"),
        timeframe="1h"
    )

    print(f"✅ Fetched {len(data)} hourly bars from SIP feed")
    return data

data = asyncio.run(live_trading())
```

### Intraday Data

```python
import asyncio
import os
import pandas as pd
from rustybt.data.adapters.alpaca_adapter import AlpacaAdapter

async def intraday_data():
    os.environ["ALPACA_API_KEY"] = "your_key"
    os.environ["ALPACA_API_SECRET"] = "your_secret"

    adapter = AlpacaAdapter(is_paper=True)

    # Fetch 1-minute bars
    data = await adapter.fetch_ohlcv(
        symbol="SPY",
        start_date=pd.Timestamp("2024-01-02 09:30:00"),
        end_date=pd.Timestamp("2024-01-02 16:00:00"),
        timeframe="1m"
    )

    print(f"✅ Fetched {len(data)} minute bars")
    print(f"Expected ~390 bars (6.5 trading hours)")
    return data

data = asyncio.run(intraday_data())
```

## Rate Limiting

Alpaca adapter includes automatic rate limiting at 200 requests/minute:

```python
import asyncio
import os
import pandas as pd
from rustybt.data.adapters.alpaca_adapter import AlpacaAdapter

async def rate_limited_requests():
    os.environ["ALPACA_API_KEY"] = "your_key"
    os.environ["ALPACA_API_SECRET"] = "your_secret"

    adapter = AlpacaAdapter(is_paper=True)

    # Rate limiter automatically spaces requests
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]

    for symbol in symbols:
        data = await adapter.fetch_ohlcv(
            symbol=symbol,
            start_date=pd.Timestamp("2024-01-02"),
            end_date=pd.Timestamp("2024-01-05"),
            timeframe="1d"
        )
        print(f"✅ Fetched {symbol}: {len(data)} bars")

    print("Rate limiter automatically respected 200 req/min limit")

asyncio.run(rate_limited_requests())
```

## Error Handling

```python
import asyncio
import os
import pandas as pd
from rustybt.data.adapters.alpaca_adapter import AlpacaAdapter
from rustybt.data.adapters.api_provider_base import (
    SymbolNotFoundError,
    AuthenticationError
)

async def handle_errors():
    # Authentication error
    try:
        os.environ.pop("ALPACA_API_KEY", None)
        adapter = AlpacaAdapter()
    except AuthenticationError as e:
        print(f"✅ Caught auth error: {e}")

    # Re-set credentials
    os.environ["ALPACA_API_KEY"] = "your_key"
    os.environ["ALPACA_API_SECRET"] = "your_secret"

    adapter = AlpacaAdapter(is_paper=True)

    # Symbol not found
    try:
        data = await adapter.fetch_ohlcv(
            symbol="INVALIDTICKER",
            start_date=pd.Timestamp("2024-01-02"),
            end_date=pd.Timestamp("2024-01-05"),
            timeframe="1d"
        )
    except SymbolNotFoundError as e:
        print(f"✅ Caught symbol error: {e}")

    # Invalid timeframe
    try:
        data = await adapter.fetch_ohlcv(
            symbol="AAPL",
            start_date=pd.Timestamp("2024-01-02"),
            end_date=pd.Timestamp("2024-01-05"),
            timeframe="3h"
        )
    except ValueError as e:
        print(f"✅ Caught timeframe error: {e}")

asyncio.run(handle_errors())
```

## Best Practices

### 1. Use Paper Trading for Development

```python
# ✅ DO: Use paper trading (free) for development and testing
adapter = AlpacaAdapter(is_paper=True)

# ❌ DON'T: Use live trading (paid) for testing
# adapter = AlpacaAdapter(is_paper=False)

print("✅ Paper trading is free and sufficient for development")
```

### 2. Corporate Actions Included

```python
# All data includes corporate action adjustments automatically
# (splits, dividends, etc.)
print("✅ Corporate actions are automatically adjusted")
```

### 3. US Stocks Only

```python
# ✅ DO: Use Alpaca for US stocks
# adapter = AlpacaAdapter()
# data = await adapter.fetch_ohlcv("AAPL", ...)

# ❌ DON'T: Try to fetch non-US stocks, forex, or crypto
# For crypto, use AlpacaCryptoAdapter or other adapters

print("✅ Alpaca is US stocks only")
```

## Common Issues

### Issue: Authentication Error

**Problem**: `AuthenticationError: ALPACA_API_KEY environment variable not set`

**Solution**: Set both required environment variables:

```bash
export ALPACA_API_KEY="your_key"
export ALPACA_API_SECRET="your_secret"
```

### Issue: Symbol Not Found

**Problem**: `SymbolNotFoundError: Symbol 'XYZ' not found`

**Solution**: Verify symbol is a valid US stock ticker on Alpaca

### Issue: IEX vs SIP Feed

**Problem**: Different data between paper and live

**Solution**: IEX (paper) and SIP (live) feeds have different data sources:
- IEX: Investors Exchange (subset of market data)
- SIP: Securities Information Processor (consolidated market data)

Use `is_paper=False` for production systems requiring full market data.

## See Also

- [Base Adapter Framework](./base-adapter.md) - Core adapter interface
- [Polygon Adapter](./polygon-adapter.md) - Alternative US stock data provider
- [YFinance Adapter](./yfinance-adapter.md) - Free alternative for US stocks
