# YFinance Adapter

The YFinance adapter provides free access to historical and near-real-time market data for stocks, ETFs, indices, forex, and commodities through Yahoo Finance.

## Overview

**Best for**: Stock market backtesting, ETF strategies, educational purposes, prototyping

**Supported Assets**:
- Stocks (US and international)
- ETFs and mutual funds
- Major indices (S&P 500, NASDAQ, etc.)
- Forex pairs
- Commodities (gold, oil, etc.)
- Cryptocurrencies (major pairs only)

**Data Features**:
- Historical OHLCV data
- Dividend and split-adjusted prices
- Corporate actions (dividends, splits)
- 15-minute delayed real-time quotes

## Quick Start

```python
from rustybt.data.adapters import YFinanceAdapter
import pandas as pd
import asyncio

async def fetch_stock_data():
    adapter = YFinanceAdapter()

    df = await adapter.fetch(
        symbols=['AAPL', 'MSFT', 'GOOGL'],
        start_date=pd.Timestamp('2024-01-01'),
        end_date=pd.Timestamp('2024-01-31'),
        resolution='1d'
    )

    print(df.head())
    return df

# Run
df = asyncio.run(fetch_stock_data())
```

## Configuration

```python
from rustybt.data.adapters import YFinanceAdapter

adapter = YFinanceAdapter(
    request_delay=1.0,        # Delay between requests (seconds)
    fetch_dividends=True,     # Fetch dividend data
    fetch_splits=True         # Fetch stock split data
)
```

### Rate Limiting

YFinance doesn't publish official rate limits, but recommended practices:

```python
# Conservative: 1 request per second (default)
adapter = YFinanceAdapter(request_delay=1.0)

# Moderate: 2 requests per second
adapter = YFinanceAdapter(request_delay=0.5)

# Note: Too aggressive fetching may result in temporary IP blocks
```

## Supported Resolutions

| Resolution | YFinance Format | Historical Limit | Notes |
|-----------|----------------|------------------|-------|
| 1 minute | `1m` | 7 days | Intraday only |
| 5 minutes | `5m` | 60 days | Intraday only |
| 15 minutes | `15m` | 60 days | Intraday only |
| 30 minutes | `30m` | 60 days | Intraday only |
| 1 hour | `1h` | 730 days (2 years) | Intraday only |
| 1 day | `1d` | Full history | Recommended |
| 1 week | `1wk` | Full history | Available |
| 1 month | `1mo` | Full history | Available |

**Important**: Intraday resolutions (1m-1h) are limited to 60 days or less by Yahoo Finance API.

## Symbol Format

YFinance uses ticker symbols as they appear on Yahoo Finance.

### US Stocks

```python
symbols = [
    'AAPL',      # Apple Inc.
    'MSFT',      # Microsoft Corporation
    'GOOGL',     # Alphabet Class A
    'GOOG',      # Alphabet Class C
    'TSLA',      # Tesla Inc.
]
```

### International Stocks

```python
# Add exchange suffix for international stocks
symbols = [
    'VOD.L',     # Vodafone (London)
    '7203.T',    # Toyota (Tokyo)
    'SAP.DE',    # SAP (Germany)
    'SHOP.TO',   # Shopify (Toronto)
    '0700.HK',   # Tencent (Hong Kong)
]
```

### ETFs and Indices

```python
# ETFs
etfs = ['SPY', 'QQQ', 'IWM', 'DIA', 'VTI']

# Indices (use ^ prefix)
indices = [
    '^GSPC',     # S&P 500
    '^DJI',      # Dow Jones
    '^IXIC',     # NASDAQ Composite
    '^RUT',      # Russell 2000
    '^VIX',      # VIX Volatility Index
]
```

### Forex and Commodities

```python
# Forex (use format: XXX=YYY)
forex = [
    'EURUSD=X',  # Euro / US Dollar
    'GBPUSD=X',  # British Pound / US Dollar
    'USDJPY=X',  # US Dollar / Japanese Yen
]

# Commodities
commodities = [
    'GC=F',      # Gold futures
    'CL=F',      # Crude oil futures
    'SI=F',      # Silver futures
]
```

## Usage Examples

### Example 1: Fetch Stock Portfolio

```python
import asyncio
from rustybt.data.adapters import YFinanceAdapter
import pandas as pd

async def fetch_portfolio():
    adapter = YFinanceAdapter()

    portfolio = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA']

    df = await adapter.fetch(
        symbols=portfolio,
        start_date=pd.Timestamp('2023-01-01'),
        end_date=pd.Timestamp('2024-01-01'),
        resolution='1d'
    )

    # Calculate portfolio statistics
    for symbol in portfolio:
        symbol_data = df.filter(pl.col('symbol') == symbol)
        start_price = symbol_data['close'][0]
        end_price = symbol_data['close'][-1]
        returns = (end_price - start_price) / start_price
        print(f"{symbol}: {returns:.2%} return")

    return df

df = asyncio.run(fetch_portfolio())
```

### Example 2: Dividend Analysis

```python
async def analyze_dividends():
    adapter = YFinanceAdapter(fetch_dividends=True)

    # High dividend yield stocks
    dividend_stocks = ['KO', 'PG', 'JNJ', 'T', 'VZ']

    df = await adapter.fetch(
        symbols=dividend_stocks,
        start_date=pd.Timestamp('2023-01-01'),
        end_date=pd.Timestamp('2024-01-01'),
        resolution='1d'
    )

    # Note: Dividend data accessible through YFinance Ticker object
    import yfinance as yf

    for symbol in dividend_stocks:
        ticker = yf.Ticker(symbol)
        dividends = ticker.dividends

        if len(dividends) > 0:
            annual_dividend = dividends.last('1Y').sum()
            current_price = df.filter(pl.col('symbol') == symbol)['close'][-1]
            yield_pct = (annual_dividend / current_price) * 100
            print(f"{symbol}: ${annual_dividend:.2f}/share, {yield_pct:.2f}% yield")

asyncio.run(analyze_dividends())
```

### Example 3: Intraday Trading Data

```python
async def fetch_intraday():
    """Fetch recent intraday data (limited to 7 days for 1m resolution)."""
    adapter = YFinanceAdapter()

    # Get last 5 days of 5-minute data
    end_date = pd.Timestamp.now()
    start_date = end_date - pd.Timedelta(days=5)

    df = await adapter.fetch(
        symbols=['SPY'],  # S&P 500 ETF
        start_date=start_date,
        end_date=end_date,
        resolution='5m'
    )

    print(f"Fetched {len(df)} 5-minute bars")

    # Calculate intraday statistics
    df_with_returns = df.with_columns([
        (pl.col('close') / pl.col('open') - 1).alias('bar_return')
    ])

    print(f"Avg bar return: {df_with_returns['bar_return'].mean():.4f}")
    print(f"Max bar return: {df_with_returns['bar_return'].max():.4f}")
    print(f"Min bar return: {df_with_returns['bar_return'].min():.4f}")

    return df

df = asyncio.run(fetch_intraday())
```

### Example 4: International Markets

```python
async def fetch_global_stocks():
    """Fetch data from multiple international exchanges."""
    adapter = YFinanceAdapter()

    global_portfolio = [
        'AAPL',      # US - Apple
        'VOD.L',     # UK - Vodafone
        '7203.T',    # Japan - Toyota
        'SAP.DE',    # Germany - SAP
        'SHOP.TO',   # Canada - Shopify
    ]

    df = await adapter.fetch_batch(
        symbols=global_portfolio,
        start_date=pd.Timestamp('2024-01-01'),
        end_date=pd.Timestamp('2024-01-31'),
        resolution='1d',
        batch_size=5
    )

    # Group by exchange
    for symbol in global_portfolio:
        symbol_data = df.filter(pl.col('symbol') == symbol)
        print(f"{symbol}: {len(symbol_data)} bars")

    return df

df = asyncio.run(fetch_global_stocks())
```

### Example 5: Index Comparison

```python
async def compare_indices():
    """Compare performance of major market indices."""
    adapter = YFinanceAdapter()

    indices = {
        '^GSPC': 'S&P 500',
        '^DJI': 'Dow Jones',
        '^IXIC': 'NASDAQ',
        '^RUT': 'Russell 2000'
    }

    df = await adapter.fetch(
        symbols=list(indices.keys()),
        start_date=pd.Timestamp('2023-01-01'),
        end_date=pd.Timestamp('2024-01-01'),
        resolution='1d'
    )

    # Calculate returns for each index
    print("YTD Performance:")
    for symbol, name in indices.items():
        symbol_data = df.filter(pl.col('symbol') == symbol)
        if len(symbol_data) > 0:
            start_price = symbol_data['close'][0]
            end_price = symbol_data['close'][-1]
            returns = (end_price - start_price) / start_price
            print(f"{name}: {returns:.2%}")

asyncio.run(compare_indices())
```

## Corporate Actions

### Handling Splits

```python
import yfinance as yf

# Access split data directly through yfinance
ticker = yf.Ticker('AAPL')
splits = ticker.splits

print("Recent splits:")
print(splits.tail())

# Prices from adapter are already split-adjusted
adapter = YFinanceAdapter(fetch_splits=True)
df = await adapter.fetch(
    symbols=['AAPL'],
    start_date=pd.Timestamp('2020-01-01'),
    end_date=pd.Timestamp('2024-01-01'),
    resolution='1d'
)
# All prices are split-adjusted automatically
```

### Handling Dividends

```python
# Access dividend data through yfinance
ticker = yf.Ticker('AAPL')
dividends = ticker.dividends

print("Recent dividends:")
print(dividends.tail())

# Calculate total dividends for period
annual_dividends = dividends.last('1Y').sum()
print(f"Total dividends (last year): ${annual_dividends:.2f}")
```

## Error Handling

### Common Issues

```python
from rustybt.data.adapters import YFinanceAdapter
from rustybt.data.adapters.base import NetworkError, InvalidDataError

async def robust_fetch():
    adapter = YFinanceAdapter()

    try:
        df = await adapter.fetch(
            symbols=['AAPL', 'INVALID_SYMBOL'],
            start_date=pd.Timestamp('2024-01-01'),
            end_date=pd.Timestamp('2024-01-31')
        )
        return df

    except NetworkError as e:
        # Yahoo Finance may be temporarily unavailable
        print(f"Network error: {e}")
        # Retry with exponential backoff

    except InvalidDataError as e:
        # Invalid symbol or no data available
        print(f"Invalid data: {e}")
        # Filter out invalid symbols and retry

    except Exception as e:
        # Other errors (symbol not found, etc.)
        print(f"Error: {e}")
```

### Symbol Validation

```python
import yfinance as yf

def validate_symbol(symbol: str) -> bool:
    """Check if symbol exists on Yahoo Finance."""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        return 'regularMarketPrice' in info or 'previousClose' in info
    except:
        return False

# Validate before fetching
symbols = ['AAPL', 'MSFT', 'INVALID']
valid_symbols = [s for s in symbols if validate_symbol(s)]

df = await adapter.fetch(symbols=valid_symbols, ...)
```

## Performance Optimization

### Batch Fetching

```python
async def efficient_batch_fetch():
    """Efficiently fetch large symbol lists."""
    adapter = YFinanceAdapter(request_delay=0.5)

    # Large symbol list (e.g., S&P 500 components)
    sp500_symbols = [...]  # 500 symbols

    # Fetch in batches of 50
    df = await adapter.fetch_batch(
        symbols=sp500_symbols,
        start_date=pd.Timestamp('2024-01-01'),
        end_date=pd.Timestamp('2024-01-31'),
        resolution='1d',
        batch_size=50  # Process 50 at a time
    )

    return df
```

### Caching

```python
from rustybt.data.polars.cache_manager import CacheManager

cache = CacheManager(max_memory_mb=512)

@cache.cached(ttl_seconds=3600)  # Cache for 1 hour
async def fetch_with_cache(symbols: list[str]):
    adapter = YFinanceAdapter()
    return await adapter.fetch(
        symbols=symbols,
        start_date=pd.Timestamp('2024-01-01'),
        end_date=pd.Timestamp('2024-01-31'),
        resolution='1d'
    )
```

## Best Practices

### 1. Respect Rate Limits

```python
# Use conservative delays
adapter = YFinanceAdapter(request_delay=1.0)

# For large datasets, add delays between batches
async def fetch_with_delays():
    for batch in symbol_batches:
        df = await adapter.fetch(symbols=batch, ...)
        await asyncio.sleep(2.0)  # Extra delay between batches
```

### 2. Handle Missing Data

```python
# Check for data availability
df = await adapter.fetch(symbols=['AAPL'], ...)

if len(df) == 0:
    print("No data returned for symbol")
elif len(df) < expected_bars:
    print(f"Warning: Expected {expected_bars} bars, got {len(df)}")
```

### 3. Use Appropriate Resolutions

```python
# For backtesting: use daily data
df_daily = await adapter.fetch(
    symbols=['AAPL'],
    start_date=pd.Timestamp('2020-01-01'),
    end_date=pd.Timestamp('2024-01-01'),
    resolution='1d'  # Full history available
)

# For recent analysis: use intraday
df_intraday = await adapter.fetch(
    symbols=['AAPL'],
    start_date=pd.Timestamp.now() - pd.Timedelta(days=5),
    end_date=pd.Timestamp.now(),
    resolution='5m'  # Limited to 60 days
)
```

## Limitations

### Known Limitations

1. **Real-time Data**: 15-minute delay for real-time quotes
2. **Intraday History**: Limited to 7-60 days depending on resolution
3. **Rate Limits**: Aggressive fetching may result in temporary blocks
4. **Data Quality**: Occasional gaps or errors in historical data
5. **International Data**: Limited data for some international exchanges
6. **Delisted Stocks**: Data may not be available for delisted companies

### Workarounds

```python
# For real-time data, use a professional data provider
from rustybt.data.adapters import PolygonAdapter

# For extensive intraday history, use alternative sources

# For reliable international data

```

## API Reference

```python
class YFinanceAdapter(BaseDataAdapter, DataSource):
    """YFinance adapter for stock market data."""

    def __init__(
        self,
        request_delay: float = 1.0,
        fetch_dividends: bool = True,
        fetch_splits: bool = True,
    ) -> None:
        """Initialize YFinance adapter."""

    async def fetch(
        self,
        symbols: list[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        resolution: str = "1d"
    ) -> pl.DataFrame:
        """Fetch OHLCV data."""
```

## See Also

- [Adapter Overview](overview.md) - Common adapter features
- [Polygon Adapter](polygon.md) - Professional-grade alternative
- [Alpaca Adapter](alpaca.md) - Real-time data with brokerage
- [Yahoo Finance](https://finance.yahoo.com) - Data source
