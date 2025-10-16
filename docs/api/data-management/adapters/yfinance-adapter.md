# YFinance Adapter - Stock, ETF, and Index Data

**Module**: `rustybt.data.adapters.yfinance_adapter`

## Overview

`YFinanceAdapter` provides access to Yahoo Finance data for stocks, ETFs, forex pairs, indices, and commodities. Yahoo Finance is a widely-used free data source offering historical and near-real-time (15-minute delayed) market data across global markets.

## Supported Asset Classes

| Asset Class | Examples | Symbol Format |
|-------------|----------|---------------|
| **Stocks** | Apple, Microsoft, Tesla | `AAPL`, `MSFT`, `TSLA` |
| **ETFs** | S&P 500, Nasdaq 100 | `SPY`, `QQQ`, `IWM` |
| **Indices** | Market indices | `^GSPC`, `^DJI`, `^IXIC` |
| **Forex** | Currency pairs | `EURUSD=X`, `GBPJPY=X` |
| **Commodities** | Gold, oil, futures | `GC=F`, `CL=F`, `SI=F` |
| **Crypto** | Bitcoin, Ethereum | `BTC-USD`, `ETH-USD` |

## Class Definition

```python
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

class YFinanceAdapter(BaseDataAdapter, DataSource):
    """YFinance adapter for fetching stock/ETF/forex OHLCV data."""
```

## Constructor

```python
def __init__(
    self,
    request_delay: float = 1.0,
    fetch_dividends: bool = True,
    fetch_splits: bool = True,
) -> None:
```

### Parameters

- **request_delay** (`float`, default=1.0): Delay between requests in seconds for rate limiting
- **fetch_dividends** (`bool`, default=True): Whether to enable dividend data fetching
- **fetch_splits** (`bool`, default=True): Whether to enable split data fetching

### Example

```python
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

# Basic initialization with defaults
adapter = YFinanceAdapter()
print(f"✅ Created YFinance adapter with {adapter.request_delay}s delay")

# Custom rate limiting (faster requests)
adapter_fast = YFinanceAdapter(request_delay=0.5)
print(f"✅ Fast adapter with {adapter_fast.request_delay}s delay")

# Disable dividend/split fetching
adapter_simple = YFinanceAdapter(
    fetch_dividends=False,
    fetch_splits=False
)
print(f"✅ Simple adapter: dividends={adapter_simple.fetch_dividends_flag}, splits={adapter_simple.fetch_splits_flag}")
```

## Supported Resolutions

```python
import polars as pl

# Resolution mapping
RESOLUTION_MAPPING = {
    "1m": "1m",      # 1 minute (intraday, 60-day limit)
    "5m": "5m",      # 5 minutes (intraday, 60-day limit)
    "15m": "15m",    # 15 minutes (intraday, 60-day limit)
    "30m": "30m",    # 30 minutes (intraday, 60-day limit)
    "1h": "1h",      # 1 hour (intraday, 60-day limit)
    "1d": "1d",      # 1 day (daily data)
    "1wk": "1wk",    # 1 week (weekly data)
    "1mo": "1mo",    # 1 month (monthly data)
}

print(f"✅ Supported resolutions: {list(RESOLUTION_MAPPING.keys())}")
```

### Intraday Limitation

⚠️ **IMPORTANT**: Yahoo Finance restricts intraday data (`1m`, `5m`, `15m`, `30m`, `1h`) to **60 days maximum**. Attempting to fetch more will raise a `ValueError`.

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

async def demonstrate_intraday_limit():
    adapter = YFinanceAdapter()

    # ❌ This will fail - exceeds 60-day limit
    try:
        data = await adapter.fetch(
            symbols=["AAPL"],
            start_date=pd.Timestamp("2023-01-01"),
            end_date=pd.Timestamp("2024-01-01"),
            resolution="1h"  # Intraday resolution
        )
    except ValueError as e:
        print(f"✅ Expected error: {e}")

    # ✅ This works - within 60-day limit
    data = await adapter.fetch(
        symbols=["AAPL"],
        start_date=pd.Timestamp("2024-01-01"),
        end_date=pd.Timestamp("2024-02-15"),  # 45 days
        resolution="1h"
    )
    print(f"✅ Fetched {len(data)} hourly bars within 60-day limit")
    return data

# Run
data = asyncio.run(demonstrate_intraday_limit())
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

Fetch OHLCV data from Yahoo Finance with automatic rate limiting and validation.

**Parameters**:
- **symbols** (`list[str]`): Ticker symbols (e.g., `["AAPL", "MSFT", "SPY"]`)
- **start_date** (`pd.Timestamp`): Start date for data range
- **end_date** (`pd.Timestamp`): End date for data range
- **resolution** (`str`): Time resolution (e.g., `"1d"`, `"1h"`, `"1m"`)

**Returns**:
- `pl.DataFrame`: Polars DataFrame with standardized OHLCV schema

**Raises**:
- `ValueError`: If intraday resolution requested for >60 days or unsupported resolution
- `NetworkError`: If API request fails
- `InvalidDataError`: If symbol is invalid or delisted

**Example**:

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

async def fetch_stock_data():
    adapter = YFinanceAdapter(request_delay=1.0)

    # Fetch Apple and Microsoft daily data
    data = await adapter.fetch(
        symbols=["AAPL", "MSFT"],
        start_date=pd.Timestamp("2024-01-02"),
        end_date=pd.Timestamp("2024-01-05"),
        resolution="1d"
    )

    print(f"✅ Fetched {len(data)} rows")
    print(f"Symbols: {data['symbol'].unique().to_list()}")
    print(f"Date range: {data['timestamp'].min()} to {data['timestamp'].max()}")
    print(f"\nFirst few rows:")
    print(data.head())

    return data

# Run the async function
data = asyncio.run(fetch_stock_data())
```

### fetch_dividends()

```python
async def fetch_dividends(
    self,
    symbols: list[str]
) -> dict[str, pl.DataFrame]:
```

Fetch historical dividend data for symbols.

**Parameters**:
- **symbols** (`list[str]`): List of ticker symbols

**Returns**:
- `dict[str, pl.DataFrame]`: Dictionary mapping symbol to dividend DataFrame with columns:
  - `date`: Dividend payment date
  - `symbol`: Ticker symbol
  - `dividend`: Dividend amount (Decimal)

**Example**:

```python
import asyncio
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

async def fetch_dividend_data():
    adapter = YFinanceAdapter()

    # Fetch dividends for dividend-paying stocks
    dividends = await adapter.fetch_dividends(["AAPL", "MSFT", "JNJ"])

    for symbol, div_df in dividends.items():
        print(f"\n✅ {symbol}: {len(div_df)} dividend payments")
        print(div_df.tail(5))  # Show last 5 dividends

    return dividends

# Run
dividends = asyncio.run(fetch_dividend_data())
```

### fetch_splits()

```python
async def fetch_splits(
    self,
    symbols: list[str]
) -> dict[str, pl.DataFrame]:
```

Fetch historical stock split data for symbols.

**Parameters**:
- **symbols** (`list[str]`): List of ticker symbols

**Returns**:
- `dict[str, pl.DataFrame]`: Dictionary mapping symbol to split DataFrame with columns:
  - `date`: Split date
  - `symbol`: Ticker symbol
  - `split_ratio`: Split ratio (Decimal), e.g., 2.0 for 2:1 split

**Example**:

```python
import asyncio
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

async def fetch_split_data():
    adapter = YFinanceAdapter()

    # Fetch splits for stocks that have split recently
    splits = await adapter.fetch_splits(["AAPL", "TSLA", "GOOGL"])

    for symbol, split_df in splits.items():
        print(f"\n✅ {symbol}: {len(split_df)} stock splits")
        print(split_df)

    if not splits:
        print("ℹ️  No splits found for these symbols in their history")

    return splits

# Run
splits = asyncio.run(fetch_split_data())
```

### get_metadata()

```python
def get_metadata(self) -> DataSourceMetadata:
```

Get YFinance data source metadata.

**Returns**:
- `DataSourceMetadata`: Metadata object with source information

**Example**:

```python
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

adapter = YFinanceAdapter()
metadata = adapter.get_metadata()

print(f"✅ Source type: {metadata.source_type}")
print(f"API URL: {metadata.source_url}")
print(f"API version: {metadata.api_version}")
print(f"Rate limit: {metadata.rate_limit} req/hour")
print(f"Data delay: {metadata.data_delay} minutes")
print(f"Supports live: {metadata.supports_live}")
print(f"Auth required: {metadata.auth_required}")
print(f"Supported frequencies: {metadata.supported_frequencies}")
```

## Common Usage Patterns

### Fetch Stock Data

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

async def fetch_stocks():
    adapter = YFinanceAdapter()

    # Fetch tech stocks
    data = await adapter.fetch(
        symbols=["AAPL", "MSFT", "GOOGL", "AMZN"],
        start_date=pd.Timestamp("2024-01-02"),
        end_date=pd.Timestamp("2024-01-31"),
        resolution="1d"
    )

    print(f"✅ Fetched {len(data)} daily bars for tech stocks")

    # Calculate simple statistics
    for symbol in ["AAPL", "MSFT", "GOOGL", "AMZN"]:
        symbol_data = data.filter(pl.col("symbol") == symbol)
        avg_volume = symbol_data["volume"].mean()
        print(f"{symbol}: avg volume = {avg_volume}")

    return data

# Run
import polars as pl
data = asyncio.run(fetch_stocks())
```

### Fetch ETF Data

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

async def fetch_etfs():
    adapter = YFinanceAdapter()

    # Fetch popular ETFs
    data = await adapter.fetch(
        symbols=["SPY", "QQQ", "IWM", "DIA"],
        start_date=pd.Timestamp("2024-01-02"),
        end_date=pd.Timestamp("2024-01-31"),
        resolution="1d"
    )

    print(f"✅ Fetched {len(data)} daily bars for ETFs")
    print(f"ETFs: {data['symbol'].unique().to_list()}")

    return data

# Run
data = asyncio.run(fetch_etfs())
```

### Fetch Market Indices

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

async def fetch_indices():
    adapter = YFinanceAdapter()

    # Fetch major market indices (note the ^ prefix)
    data = await adapter.fetch(
        symbols=["^GSPC", "^DJI", "^IXIC"],  # S&P 500, Dow Jones, Nasdaq
        start_date=pd.Timestamp("2024-01-02"),
        end_date=pd.Timestamp("2024-01-31"),
        resolution="1d"
    )

    print(f"✅ Fetched {len(data)} daily bars for indices")
    print(data.head())

    return data

# Run
data = asyncio.run(fetch_indices())
```

### Fetch Forex Data

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

async def fetch_forex():
    adapter = YFinanceAdapter()

    # Fetch forex pairs (note the =X suffix)
    data = await adapter.fetch(
        symbols=["EURUSD=X", "GBPUSD=X", "USDJPY=X"],
        start_date=pd.Timestamp("2024-01-02"),
        end_date=pd.Timestamp("2024-01-31"),
        resolution="1d"
    )

    print(f"✅ Fetched {len(data)} daily bars for forex pairs")
    print(f"Currency pairs: {data['symbol'].unique().to_list()}")

    return data

# Run
data = asyncio.run(fetch_forex())
```

### Fetch Cryptocurrency Data

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

async def fetch_crypto():
    adapter = YFinanceAdapter()

    # Fetch crypto prices (note the -USD suffix)
    data = await adapter.fetch(
        symbols=["BTC-USD", "ETH-USD", "SOL-USD"],
        start_date=pd.Timestamp("2024-01-02"),
        end_date=pd.Timestamp("2024-01-31"),
        resolution="1d"
    )

    print(f"✅ Fetched {len(data)} daily bars for crypto")
    print(data.head())

    return data

# Run
data = asyncio.run(fetch_crypto())
```

### Intraday High-Frequency Data

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

async def fetch_intraday():
    adapter = YFinanceAdapter()

    # Fetch 1-minute data for a single trading day
    data = await adapter.fetch(
        symbols=["AAPL"],
        start_date=pd.Timestamp("2024-01-02 09:30:00"),
        end_date=pd.Timestamp("2024-01-02 16:00:00"),
        resolution="1m"
    )

    print(f"✅ Fetched {len(data)} minute bars")
    print(f"Expected ~390 bars (6.5 hours * 60 minutes)")
    print(f"Time range: {data['timestamp'].min()} to {data['timestamp'].max()}")

    return data

# Run
data = asyncio.run(fetch_intraday())
```

### Long Historical Data

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

async def fetch_long_history():
    adapter = YFinanceAdapter()

    # Fetch 10 years of daily data (no 60-day limit for daily data)
    data = await adapter.fetch(
        symbols=["AAPL"],
        start_date=pd.Timestamp("2014-01-01"),
        end_date=pd.Timestamp("2024-01-01"),
        resolution="1d"
    )

    print(f"✅ Fetched {len(data)} daily bars over 10 years")
    print(f"Expected ~2520 bars (10 years * ~252 trading days)")

    return data

# Run
data = asyncio.run(fetch_long_history())
```

### Fetch with Dividends and Splits

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

async def fetch_with_corporate_actions():
    adapter = YFinanceAdapter(
        fetch_dividends=True,
        fetch_splits=True
    )

    # Fetch OHLCV data
    ohlcv = await adapter.fetch(
        symbols=["AAPL"],
        start_date=pd.Timestamp("2023-01-01"),
        end_date=pd.Timestamp("2024-01-01"),
        resolution="1d"
    )

    # Fetch dividends
    dividends = await adapter.fetch_dividends(["AAPL"])

    # Fetch splits
    splits = await adapter.fetch_splits(["AAPL"])

    print(f"✅ OHLCV: {len(ohlcv)} bars")

    if "AAPL" in dividends:
        print(f"✅ Dividends: {len(dividends['AAPL'])} payments")
        print(dividends["AAPL"].tail(3))

    if "AAPL" in splits:
        print(f"✅ Splits: {len(splits['AAPL'])} splits")
        print(splits["AAPL"])

    return {"ohlcv": ohlcv, "dividends": dividends, "splits": splits}

# Run
data = asyncio.run(fetch_with_corporate_actions())
```

## Rate Limiting

The YFinance adapter implements automatic rate limiting to prevent API quota exhaustion:

```python
import asyncio
import time
import pandas as pd
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

async def demonstrate_rate_limiting():
    # Create adapter with 2-second delay
    adapter = YFinanceAdapter(request_delay=2.0)

    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]

    start_time = time.time()

    # Each symbol fetch will be delayed by 2 seconds
    for symbol in symbols:
        data = await adapter.fetch(
            symbols=[symbol],
            start_date=pd.Timestamp("2024-01-02"),
            end_date=pd.Timestamp("2024-01-05"),
            resolution="1d"
        )
        print(f"✅ Fetched {symbol}: {len(data)} bars")

    elapsed = time.time() - start_time
    print(f"\n✅ Total time: {elapsed:.1f}s (expected ~{2.0 * len(symbols)}s with 2s delay)")

# Run
asyncio.run(demonstrate_rate_limiting())
```

### Best Practices for Rate Limiting

```python
# ❌ DON'T: Use very short delays (risks rate limiting)
# adapter = YFinanceAdapter(request_delay=0.1)

# ✅ DO: Use conservative delays (1-2 seconds)
adapter = YFinanceAdapter(request_delay=1.0)

# ✅ DO: Fetch multiple symbols in a single request when possible
# data = await adapter.fetch(["AAPL", "MSFT", "GOOGL"], ...)  # Single request

# ❌ DON'T: Make separate requests for each symbol unnecessarily
# for symbol in symbols:
#     data = await adapter.fetch([symbol], ...)  # Multiple requests

print("✅ Use batch fetching and conservative rate limits")
```

## Error Handling

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter
from rustybt.data.adapters.base import NetworkError, InvalidDataError

async def handle_errors():
    adapter = YFinanceAdapter()

    # Handle invalid symbol
    try:
        data = await adapter.fetch(
            symbols=["INVALIDTICKER123"],
            start_date=pd.Timestamp("2024-01-02"),
            end_date=pd.Timestamp("2024-01-05"),
            resolution="1d"
        )
    except InvalidDataError as e:
        print(f"✅ Caught invalid symbol error: {e}")

    # Handle 60-day intraday limit
    try:
        data = await adapter.fetch(
            symbols=["AAPL"],
            start_date=pd.Timestamp("2023-01-01"),
            end_date=pd.Timestamp("2024-01-01"),
            resolution="1m"  # Intraday
        )
    except ValueError as e:
        print(f"✅ Caught 60-day limit error: {e}")

    # Handle unsupported resolution
    try:
        data = await adapter.fetch(
            symbols=["AAPL"],
            start_date=pd.Timestamp("2024-01-02"),
            end_date=pd.Timestamp("2024-01-05"),
            resolution="3h"  # Not supported
        )
    except ValueError as e:
        print(f"✅ Caught unsupported resolution error: {e}")

    print("✅ Error handling demonstrated")

# Run
asyncio.run(handle_errors())
```

## Data Quality and Validation

All data returned by YFinanceAdapter is automatically validated:

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter
from rustybt.data.adapters.base import detect_outliers

async def check_data_quality():
    adapter = YFinanceAdapter()

    # Fetch data
    data = await adapter.fetch(
        symbols=["AAPL"],
        start_date=pd.Timestamp("2024-01-02"),
        end_date=pd.Timestamp("2024-01-31"),
        resolution="1d"
    )

    # Data is automatically validated by adapter
    print(f"✅ Data passed OHLCV validation")
    print(f"✅ High >= Low: {(data['high'] >= data['low']).all()}")
    print(f"✅ High >= Open/Close: {((data['high'] >= data['open']) & (data['high'] >= data['close'])).all()}")

    # Check for outliers
    outliers = detect_outliers(data, threshold=3.0)
    if len(outliers) > 0:
        print(f"⚠️  Found {len(outliers)} potential outliers")
        print(outliers)
    else:
        print("✅ No outliers detected")

    return data

# Run
data = asyncio.run(check_data_quality())
```

## Common Issues and Troubleshooting

### Issue: 60-Day Intraday Limit

**Problem**: `ValueError: Intraday resolution '1m' limited to 60 days`

**Solution**: Yahoo Finance restricts intraday data. Use daily resolution for long history:

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

async def handle_intraday_limit():
    adapter = YFinanceAdapter()

    # ❌ This fails - 365 days of 1-minute data
    # data = await adapter.fetch(["AAPL"], pd.Timestamp("2023-01-01"), pd.Timestamp("2024-01-01"), "1m")

    # ✅ This works - use daily resolution for long history
    data_daily = await adapter.fetch(
        symbols=["AAPL"],
        start_date=pd.Timestamp("2023-01-01"),
        end_date=pd.Timestamp("2024-01-01"),
        resolution="1d"  # Daily resolution has no time limit
    )

    print(f"✅ Fetched {len(data_daily)} daily bars")

    # ✅ This works - recent 30 days of 1-minute data
    data_intraday = await adapter.fetch(
        symbols=["AAPL"],
        start_date=pd.Timestamp("2024-01-01"),
        end_date=pd.Timestamp("2024-01-30"),
        resolution="1m"  # Within 60-day limit
    )

    print(f"✅ Fetched {len(data_intraday)} minute bars")

    return {"daily": data_daily, "intraday": data_intraday}

# Run
data = asyncio.run(handle_intraday_limit())
```

### Issue: Symbol Not Found

**Problem**: `InvalidDataError: No data returned for symbols ['XYZ']`

**Possible causes**:
1. Symbol ticker is incorrect
2. Symbol is delisted
3. Symbol doesn't exist on Yahoo Finance

**Solution**: Verify symbol on Yahoo Finance website:

```python
# Check symbol format for different asset types:

# Stocks: Use plain ticker
# symbols = ["AAPL", "MSFT"]

# Indices: Use ^ prefix
# symbols = ["^GSPC", "^DJI"]

# Forex: Use =X suffix
# symbols = ["EURUSD=X"]

# Crypto: Use -USD suffix
# symbols = ["BTC-USD"]

# Futures: Use =F suffix
# symbols = ["GC=F"]

print("✅ Verify symbol format on finance.yahoo.com")
```

### Issue: Empty Weekend Data

**Problem**: No data returned for weekend dates

**Solution**: Stock markets are closed on weekends. Fetch weekday data:

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

async def handle_weekend_data():
    adapter = YFinanceAdapter()

    # Requesting data for Saturday will return empty
    # Yahoo Finance only returns trading day data
    data = await adapter.fetch(
        symbols=["AAPL"],
        start_date=pd.Timestamp("2024-01-01"),  # Monday
        end_date=pd.Timestamp("2024-01-05"),    # Friday
        resolution="1d"
    )

    print(f"✅ Fetched {len(data)} bars (weekdays only)")
    print(f"Timestamps: {data['timestamp'].to_list()}")

    return data

# Run
data = asyncio.run(handle_weekend_data())
```

### Issue: 15-Minute Data Delay

**Problem**: Most recent data is 15 minutes delayed

**Solution**: Yahoo Finance free tier has 15-minute delay. Use paid data providers for real-time data:

```python
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

adapter = YFinanceAdapter()
metadata = adapter.get_metadata()

print(f"⚠️  Data delay: {metadata.data_delay} minutes")
print(f"Supports live streaming: {metadata.supports_live}")
print("ℹ️  For real-time data, use Alpaca, Polygon, or other paid providers")
```

## Symbol Format Reference

```python
# Stock symbols
stock_symbols = ["AAPL", "MSFT", "TSLA", "GOOGL"]

# Index symbols (^ prefix)
index_symbols = [
    "^GSPC",   # S&P 500
    "^DJI",    # Dow Jones Industrial Average
    "^IXIC",   # NASDAQ Composite
    "^RUT",    # Russell 2000
]

# Forex symbols (=X suffix)
forex_symbols = [
    "EURUSD=X",   # Euro/US Dollar
    "GBPUSD=X",   # British Pound/US Dollar
    "USDJPY=X",   # US Dollar/Japanese Yen
    "AUDUSD=X",   # Australian Dollar/US Dollar
]

# Crypto symbols (-USD suffix)
crypto_symbols = [
    "BTC-USD",    # Bitcoin
    "ETH-USD",    # Ethereum
    "SOL-USD",    # Solana
    "AVAX-USD",   # Avalanche
]

# Futures symbols (=F suffix)
futures_symbols = [
    "GC=F",    # Gold futures
    "CL=F",    # Crude oil futures
    "SI=F",    # Silver futures
    "NG=F",    # Natural gas futures
]

# ETF symbols
etf_symbols = [
    "SPY",     # SPDR S&P 500 ETF
    "QQQ",     # Invesco QQQ Trust (Nasdaq-100)
    "IWM",     # iShares Russell 2000 ETF
    "DIA",     # SPDR Dow Jones Industrial Average ETF
]

print("✅ Symbol format reference for different asset classes")
```

## Performance Considerations

### Batch Fetching

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

async def batch_vs_individual():
    adapter = YFinanceAdapter()

    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN"]
    start = pd.Timestamp("2024-01-02")
    end = pd.Timestamp("2024-01-05")

    # ✅ FAST: Single batch request
    data_batch = await adapter.fetch(symbols, start, end, "1d")
    print(f"✅ Batch fetch: {len(data_batch)} rows")

    # ❌ SLOW: Individual requests (4x slower due to rate limiting)
    # all_data = []
    # for symbol in symbols:
    #     data = await adapter.fetch([symbol], start, end, "1d")
    #     all_data.append(data)

    print("✅ Use batch fetching when possible")

    return data_batch

# Run
data = asyncio.run(batch_vs_individual())
```

### Cache Historical Data

```python
import asyncio
import pandas as pd
import polars as pl
from pathlib import Path
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

async def cache_historical_data():
    adapter = YFinanceAdapter()
    cache_file = Path("data/cache/aapl_daily.parquet")

    # Check if cached data exists
    if cache_file.exists():
        print("✅ Loading from cache")
        data = pl.read_parquet(cache_file)
    else:
        print("Fetching from Yahoo Finance")
        data = await adapter.fetch(
            symbols=["AAPL"],
            start_date=pd.Timestamp("2023-01-01"),
            end_date=pd.Timestamp("2024-01-01"),
            resolution="1d"
        )

        # Cache for future use
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        data.write_parquet(cache_file)
        print(f"✅ Cached to {cache_file}")

    print(f"Data: {len(data)} rows")
    return data

# Run
data = asyncio.run(cache_historical_data())
```

## See Also

- [Base Adapter Framework](./base-adapter.md) - Core adapter interface
- [CCXT Adapter](./ccxt-adapter.md) - Cryptocurrency exchange data
- [CSV Adapter](./csv-adapter.md) - Local file data
- [Data Catalog](../catalog/README.md) - Bundle metadata management
- [Data Readers](../readers/README.md) - Efficient data access
