# Data Adapters

**Module**: `rustybt.data.adapters`

## Overview

The RustyBT data adapter framework provides a standardized, extensible architecture for fetching market data from various sources (exchanges, APIs, CSV files). All adapters implement a common interface with built-in rate limiting, retry logic, error handling, and data validation.

## Architecture

The adapter framework consists of two abstract base classes:

1. **BaseDataAdapter** - Core adapter interface for all data sources
2. **BaseAPIProviderAdapter** - Extended adapter for API-based providers with authentication

### Key Features

- **Standardized OHLCV Schema**: All adapters output Polars DataFrames with Decimal precision
- **Automatic Rate Limiting**: Token bucket algorithm prevents API quota exhaustion
- **Retry Logic**: Exponential backoff with jitter for transient errors
- **Data Validation**: Multi-layer validation ensures OHLCV relationship integrity
- **Outlier Detection**: MAD-based outlier detection for data quality
- **Async/Await**: Full async support for concurrent data fetching

## Available Adapters

| Adapter | Data Source | Best For | Rate Limits |
|---------|-------------|----------|-------------|
| **CCXTAdapter** | 100+ crypto exchanges | Cryptocurrency data | Exchange-specific |
| **YFinanceAdapter** | Yahoo Finance | Stocks, ETFs, indices | ~2000 req/hour |
| **CSVAdapter** | Local CSV files | Custom data, backtesting | None (local) |
| **PolygonAdapter** | Polygon.io API | US equities, options, forex | Tier-dependent |
| **AlpacaAdapter** | Alpaca Markets API | US equities, crypto | 200 req/min |
| **AlphaVantageAdapter** | Alpha Vantage API | Global stocks, forex, crypto | 5 req/min (free) |

## Standard Schema

All adapters return data in this standardized Polars schema:

```python
import polars as pl

# Standard OHLCV schema
schema = {
    "timestamp": pl.Datetime("us"),      # Microsecond precision UTC timestamps
    "symbol": pl.Utf8,                   # Asset symbol/ticker
    "open": pl.Decimal(precision=18, scale=8),    # Opening price
    "high": pl.Decimal(precision=18, scale=8),    # Highest price
    "low": pl.Decimal(precision=18, scale=8),     # Lowest price
    "close": pl.Decimal(precision=18, scale=8),   # Closing price
    "volume": pl.Decimal(precision=18, scale=8),  # Trading volume
}
```

## Quick Start

### Basic Usage

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

async def fetch_stock_data():
    # Initialize adapter
    adapter = YFinanceAdapter(request_delay=1.0)

    # Fetch data
    data = await adapter.fetch(
        symbols=["AAPL", "MSFT"],
        start_date=pd.Timestamp("2024-01-02"),
        end_date=pd.Timestamp("2024-01-05"),
        resolution="1d"
    )

    # Data is validated and in standard schema
    print(data.head())
    # ┌─────────────────────────┬────────┬──────────┬──────────┬──────────┬──────────┬────────────┐
    # │ timestamp               │ symbol │ open     │ high     │ low      │ close    │ volume     │
    # ├─────────────────────────┼────────┼──────────┼──────────┼──────────┼──────────┼────────────┤
    # │ 2024-01-02 00:00:00     │ AAPL   │ 185.64   │ 186.95   │ 185.17   │ 186.89   │ 45274200   │
    # │ 2024-01-03 00:00:00     │ AAPL   │ 186.84   │ 187.73   │ 186.06   │ 186.33   │ 37628400   │
    # └─────────────────────────┴────────┴──────────┴──────────┴──────────┴──────────┴────────────┘

    return data

# Run the async function
data = asyncio.run(fetch_stock_data())
```

### With Validation and Outlier Detection

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter
from rustybt.data.adapters.base import detect_outliers

async def fetch_and_validate():
    adapter = YFinanceAdapter()

    # Fetch and validate
    data = await adapter.fetch(
        symbols=["AAPL"],
        start_date=pd.Timestamp("2024-01-02"),
        end_date=pd.Timestamp("2024-01-31"),
        resolution="1d"
    )

    # Check for outliers
    outliers = detect_outliers(data, threshold=3.0)
    if len(outliers) > 0:
        print(f"⚠️  Found {len(outliers)} potential data quality issues")
        print(outliers)

    return data

# Run the async function
data = asyncio.run(fetch_and_validate())
```

## Next Steps

- [Base Adapter Framework](./base-adapter.md) - Detailed BaseDataAdapter reference
- [CCXT Adapter](./ccxt-adapter.md) - Crypto exchange data
- [YFinance Adapter](./yfinance-adapter.md) - Stock and ETF data
- [CSV Adapter](./csv-adapter.md) - Local file data

## See Also

- [Data Catalog](../catalog/README.md) - Bundle metadata management
- [Data Readers](../readers/README.md) - Efficient data access
- [Pipeline System](../pipeline/README.md) - Data transformations
