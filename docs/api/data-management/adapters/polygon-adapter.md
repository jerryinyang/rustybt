# Polygon Adapter - Professional Market Data

**Module**: `rustybt.data.adapters.polygon_adapter`

## Overview

`PolygonAdapter` provides access to Polygon.io's professional-grade market data API for stocks, options, forex, and cryptocurrency. Polygon offers real-time and historical data with institutional-quality accuracy, making it ideal for production trading systems.

## Supported Asset Classes

| Asset Class | Symbol Format | Example | API Prefix |
|-------------|---------------|---------|------------|
| **Stocks** | Plain ticker | `AAPL`, `MSFT` | None |
| **Options** | OCC format | `O:SPY251219C00300000` | None |
| **Forex** | Currency pair | `EURUSD` | `C:` |
| **Crypto** | Crypto pair | `BTCUSD` | `X:` |

## Class Definition

```python
from rustybt.data.adapters.polygon_adapter import PolygonAdapter

class PolygonAdapter(BaseAPIProviderAdapter, DataSource):
    """Polygon.io data adapter for stocks, options, forex, and crypto."""
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

- **tier** (`str`, default="free"): Subscription tier - `"free"`, `"starter"`, or `"developer"`
- **asset_type** (`str`, default="stocks"): Asset type - `"stocks"`, `"options"`, `"forex"`, or `"crypto"`

### Tier Limits

| Tier | Requests/Minute | Cost | Best For |
|------|-----------------|------|----------|
| **Free** | 5 | Free | Testing, development |
| **Starter** | 10 | $29/month | Personal trading |
| **Developer** | 100 | $99/month | Production systems |

### Authentication

Requires `POLYGON_API_KEY` environment variable. Get your API key from [polygon.io](https://polygon.io).

```bash
export POLYGON_API_KEY="your_api_key_here"
```

### Example

```python
import os
from rustybt.data.adapters.polygon_adapter import PolygonAdapter

# Set API key
os.environ["POLYGON_API_KEY"] = "your_api_key"

# Create adapter for US stocks (free tier)
adapter_stocks = PolygonAdapter(tier="free", asset_type="stocks")
print(f"✅ Created Polygon adapter: {adapter_stocks.tier} tier, {adapter_stocks.asset_type}")

# Create adapter for forex (developer tier)
adapter_forex = PolygonAdapter(tier="developer", asset_type="forex")
print(f"✅ Created forex adapter: {adapter_forex.tier} tier")

# Create adapter for crypto
adapter_crypto = PolygonAdapter(tier="starter", asset_type="crypto")
print(f"✅ Created crypto adapter: {adapter_crypto.tier} tier")
```

## Supported Resolutions

```python
# Timeframe mapping
TIMEFRAME_MAP = {
    "1m": ("1", "minute"),
    "5m": ("5", "minute"),
    "15m": ("15", "minute"),
    "30m": ("30", "minute"),
    "1h": ("1", "hour"),
    "4h": ("4", "hour"),
    "1d": ("1", "day"),
    "1w": ("1", "week"),
    "1M": ("1", "month"),
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

Fetch OHLCV data for a single symbol from Polygon API.

**Parameters**:
- **symbol** (`str`): Symbol to fetch (no prefix needed, adapter adds it automatically)
- **start_date** (`pd.Timestamp`): Start date for data range
- **end_date** (`pd.Timestamp`): End date for data range
- **timeframe** (`str`): Time resolution (e.g., `"1d"`, `"1h"`, `"1m"`)

**Returns**:
- `pl.DataFrame`: Polars DataFrame with standardized OHLCV schema

**Raises**:
- `ValueError`: If timeframe is invalid
- `SymbolNotFoundError`: If symbol not found
- `DataParsingError`: If response parsing fails
- `AuthenticationError`: If API key is missing or invalid

**Example**:

```python
import asyncio
import os
import pandas as pd
from rustybt.data.adapters.polygon_adapter import PolygonAdapter

async def fetch_stock_data():
    # Set API key
    os.environ["POLYGON_API_KEY"] = "your_api_key"

    # Create adapter
    adapter = PolygonAdapter(tier="free", asset_type="stocks")

    # Fetch Apple stock data
    data = await adapter.fetch_ohlcv(
        symbol="AAPL",
        start_date=pd.Timestamp("2024-01-02"),
        end_date=pd.Timestamp("2024-01-05"),
        timeframe="1d"
    )

    print(f"✅ Fetched {len(data)} rows for AAPL")
    print(f"Date range: {data['timestamp'].min()} to {data['timestamp'].max()}")
    print(f"\nFirst few rows:")
    print(data.head())

    return data

# Run
data = asyncio.run(fetch_stock_data())
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

Fetch OHLCV data for multiple symbols (backwards compatibility method).

**Parameters**:
- **symbols** (`list[str]`): List of symbols to fetch
- **start** (`pd.Timestamp`): Start date
- **end** (`pd.Timestamp`): End date
- **frequency** (`str`): Time resolution

**Returns**:
- `pl.DataFrame`: Combined DataFrame for all symbols

**Example**:

```python
import asyncio
import os
import pandas as pd
from rustybt.data.adapters.polygon_adapter import PolygonAdapter

async def fetch_multiple_stocks():
    os.environ["POLYGON_API_KEY"] = "your_api_key"

    adapter = PolygonAdapter(tier="developer", asset_type="stocks")

    # Fetch multiple stocks
    data = await adapter.fetch(
        symbols=["AAPL", "MSFT", "GOOGL"],
        start=pd.Timestamp("2024-01-02"),
        end=pd.Timestamp("2024-01-05"),
        frequency="1d"
    )

    print(f"✅ Fetched {len(data)} total rows")
    print(f"Symbols: {data['symbol'].unique().to_list()}")

    return data

# Run
data = asyncio.run(fetch_multiple_stocks())
```

### get_metadata()

```python
def get_metadata(self) -> DataSourceMetadata:
```

Get Polygon data source metadata.

**Returns**:
- `DataSourceMetadata`: Metadata with tier and asset type information

**Example**:

```python
import os
from rustybt.data.adapters.polygon_adapter import PolygonAdapter

os.environ["POLYGON_API_KEY"] = "your_api_key"

adapter = PolygonAdapter(tier="developer", asset_type="stocks")
metadata = adapter.get_metadata()

print(f"✅ Source: {metadata.source_type}")
print(f"API URL: {metadata.source_url}")
print(f"API version: {metadata.api_version}")
print(f"Supports live: {metadata.supports_live}")
print(f"Data delay: {metadata.data_delay} minutes")
print(f"Rate limit: {metadata.rate_limit} req/min")
print(f"Tier: {metadata.additional_info['tier']}")
print(f"Asset type: {metadata.additional_info['asset_type']}")
```

## Common Usage Patterns

### Fetch US Stocks

```python
import asyncio
import os
import pandas as pd
from rustybt.data.adapters.polygon_adapter import PolygonAdapter

async def fetch_us_stocks():
    os.environ["POLYGON_API_KEY"] = "your_api_key"

    adapter = PolygonAdapter(tier="free", asset_type="stocks")

    # Fetch tech stocks
    data = await adapter.fetch_ohlcv(
        symbol="AAPL",
        start_date=pd.Timestamp("2024-01-02"),
        end_date=pd.Timestamp("2024-01-31"),
        timeframe="1d"
    )

    print(f"✅ Fetched {len(data)} daily bars for AAPL")
    return data

# Run
data = asyncio.run(fetch_us_stocks())
```

### Fetch Forex Data

```python
import asyncio
import os
import pandas as pd
from rustybt.data.adapters.polygon_adapter import PolygonAdapter

async def fetch_forex():
    os.environ["POLYGON_API_KEY"] = "your_api_key"

    # Create forex adapter
    adapter = PolygonAdapter(tier="developer", asset_type="forex")

    # Fetch EUR/USD data (adapter adds C: prefix automatically)
    data = await adapter.fetch_ohlcv(
        symbol="EURUSD",
        start_date=pd.Timestamp("2024-01-02"),
        end_date=pd.Timestamp("2024-01-31"),
        timeframe="1h"
    )

    print(f"✅ Fetched {len(data)} hourly bars for EUR/USD")
    print(f"Internal ticker format: C:EURUSD")
    return data

# Run
data = asyncio.run(fetch_forex())
```

### Fetch Cryptocurrency Data

```python
import asyncio
import os
import pandas as pd
from rustybt.data.adapters.polygon_adapter import PolygonAdapter

async def fetch_crypto():
    os.environ["POLYGON_API_KEY"] = "your_api_key"

    # Create crypto adapter
    adapter = PolygonAdapter(tier="starter", asset_type="crypto")

    # Fetch BTC/USD data (adapter adds X: prefix automatically)
    data = await adapter.fetch_ohlcv(
        symbol="BTCUSD",
        start_date=pd.Timestamp("2024-01-02"),
        end_date=pd.Timestamp("2024-01-31"),
        timeframe="1d"
    )

    print(f"✅ Fetched {len(data)} daily bars for BTC/USD")
    print(f"Internal ticker format: X:BTCUSD")
    return data

# Run
data = asyncio.run(fetch_crypto())
```

### Intraday High-Frequency Data

```python
import asyncio
import os
import pandas as pd
from rustybt.data.adapters.polygon_adapter import PolygonAdapter

async def fetch_intraday():
    os.environ["POLYGON_API_KEY"] = "your_api_key"

    # Need higher tier for high-frequency requests
    adapter = PolygonAdapter(tier="developer", asset_type="stocks")

    # Fetch 1-minute bars for a single day
    data = await adapter.fetch_ohlcv(
        symbol="SPY",
        start_date=pd.Timestamp("2024-01-02"),
        end_date=pd.Timestamp("2024-01-02"),
        timeframe="1m"
    )

    print(f"✅ Fetched {len(data)} minute bars for SPY")
    print(f"Expected ~390 bars (6.5 trading hours)")
    return data

# Run
data = asyncio.run(fetch_intraday())
```

## Rate Limiting

Polygon adapter includes automatic rate limiting based on tier:

```python
import asyncio
import os
import time
import pandas as pd
from rustybt.data.adapters.polygon_adapter import PolygonAdapter

async def demonstrate_rate_limiting():
    os.environ["POLYGON_API_KEY"] = "your_api_key"

    # Free tier: 5 requests/minute
    adapter = PolygonAdapter(tier="free", asset_type="stocks")

    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
    start_time = time.time()

    # Fetch multiple symbols - rate limiter will space requests
    for symbol in symbols:
        data = await adapter.fetch_ohlcv(
            symbol=symbol,
            start_date=pd.Timestamp("2024-01-02"),
            end_date=pd.Timestamp("2024-01-05"),
            timeframe="1d"
        )
        print(f"✅ Fetched {symbol}: {len(data)} bars")

    elapsed = time.time() - start_time
    print(f"\nTotal time: {elapsed:.1f}s")
    print(f"Rate limiter automatically spaced requests for free tier (5 req/min)")

# Run
asyncio.run(demonstrate_rate_limiting())
```

## Error Handling

```python
import asyncio
import os
import pandas as pd
from rustybt.data.adapters.polygon_adapter import PolygonAdapter
from rustybt.data.adapters.api_provider_base import (
    SymbolNotFoundError,
    DataParsingError,
    AuthenticationError
)

async def handle_errors():
    # Authentication error
    try:
        os.environ.pop("POLYGON_API_KEY", None)  # Remove key
        adapter = PolygonAdapter(tier="free", asset_type="stocks")
    except AuthenticationError as e:
        print(f"✅ Caught auth error: {e}")

    # Re-set key for other tests
    os.environ["POLYGON_API_KEY"] = "your_api_key"

    adapter = PolygonAdapter(tier="free", asset_type="stocks")

    # Symbol not found
    try:
        data = await adapter.fetch_ohlcv(
            symbol="INVALIDTICKER123",
            start_date=pd.Timestamp("2024-01-02"),
            end_date=pd.Timestamp("2024-01-05"),
            timeframe="1d"
        )
    except SymbolNotFoundError as e:
        print(f"✅ Caught symbol not found error: {e}")

    # Invalid timeframe
    try:
        data = await adapter.fetch_ohlcv(
            symbol="AAPL",
            start_date=pd.Timestamp("2024-01-02"),
            end_date=pd.Timestamp("2024-01-05"),
            timeframe="3h"  # Not supported
        )
    except ValueError as e:
        print(f"✅ Caught invalid timeframe error: {e}")

    print("✅ Error handling demonstrated")

# Run
asyncio.run(handle_errors())
```

## Best Practices

### 1. Choose Appropriate Tier

```python
# ❌ DON'T: Use free tier for production
# adapter = PolygonAdapter(tier="free", asset_type="stocks")  # Only 5 req/min

# ✅ DO: Use developer tier for production
adapter = PolygonAdapter(tier="developer", asset_type="stocks")  # 100 req/min

print("✅ Use developer tier for production systems")
```

### 2. Use Correct Asset Type

```python
import os
from rustybt.data.adapters.polygon_adapter import PolygonAdapter

os.environ["POLYGON_API_KEY"] = "your_api_key"

# ✅ DO: Create separate adapters for each asset type
stocks_adapter = PolygonAdapter(tier="developer", asset_type="stocks")
forex_adapter = PolygonAdapter(tier="developer", asset_type="forex")
crypto_adapter = PolygonAdapter(tier="developer", asset_type="crypto")

print("✅ Use dedicated adapters for each asset class")
```

### 3. Batch Requests Efficiently

```python
import asyncio
import os
import pandas as pd
from rustybt.data.adapters.polygon_adapter import PolygonAdapter

async def batch_efficiently():
    os.environ["POLYGON_API_KEY"] = "your_api_key"

    adapter = PolygonAdapter(tier="developer", asset_type="stocks")

    # ✅ DO: Fetch all symbols concurrently (respects rate limits)
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN"]
    tasks = [
        adapter.fetch_ohlcv(symbol, pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-31"), "1d")
        for symbol in symbols
    ]

    results = await asyncio.gather(*tasks)
    print(f"✅ Fetched {len(results)} symbols concurrently")

# Run
asyncio.run(batch_efficiently())
```

## Common Issues and Troubleshooting

### Issue: Authentication Error

**Problem**: `AuthenticationError: POLYGON_API_KEY environment variable not set`

**Solution**: Set the API key environment variable:

```bash
export POLYGON_API_KEY="your_api_key_here"
```

### Issue: Rate Limit Exceeded

**Problem**: Requests timing out or failing due to rate limits

**Solution**: Upgrade tier or reduce request frequency:

```python
# Upgrade to higher tier
adapter = PolygonAdapter(tier="developer", asset_type="stocks")  # 100 req/min
```

### Issue: Symbol Not Found

**Problem**: `SymbolNotFoundError: Symbol 'XYZ' not found`

**Solution**: Verify symbol exists on Polygon and use correct asset type:

```python
# Check asset type matches symbol
# Stocks: AAPL (no prefix)
# Forex: EURUSD (C: prefix added automatically)
# Crypto: BTCUSD (X: prefix added automatically)
```

### Issue: Empty Response

**Problem**: No data returned for valid date range

**Possible causes**:
1. Symbol delisted during requested period
2. Market closed (weekends, holidays)
3. Date range in future

**Solution**: Verify date range and symbol validity

## See Also

- [Base Adapter Framework](./base-adapter.md) - Core adapter interface
- [YFinance Adapter](./yfinance-adapter.md) - Free alternative for US stocks
- [Alpaca Adapter](./alpaca-adapter.md) - Another professional data provider
- [Data Catalog](../catalog/README.md) - Bundle metadata management
