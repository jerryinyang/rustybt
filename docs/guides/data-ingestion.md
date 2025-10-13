# Data Ingestion Guide

**Last Updated**: 2024-10-11

## Quick Start

Ingest stock data from Yahoo Finance in one line:

```bash
rustybt ingest-unified yfinance --symbols AAPL,MSFT,GOOGL --bundle my-stocks \
  --start 2023-01-01 --end 2023-12-31 --frequency 1d
```

Or using Python API:

```python
from rustybt.data.sources import DataSourceRegistry
import pandas as pd
import asyncio

async def main():
    source = DataSourceRegistry.get_source("yfinance")
    await source.ingest_to_bundle(
        bundle_name="my-stocks",
        symbols=["AAPL", "MSFT", "GOOGL"],
        start=pd.Timestamp("2023-01-01"),
        end=pd.Timestamp("2023-12-31"),
        frequency="1d"
    )

asyncio.run(main())
```

---

## Overview

The unified data ingestion system supports multiple data sources through a consistent API. All adapters implement the same `DataSource` interface, making it easy to switch between providers.

### Supported Data Sources

| Source | Type | Live Support | Rate Limit | API Key Required |
|--------|------|--------------|------------|------------------|
| **yfinance** | Equities/ETFs | ❌ | 2000 req/hr | ❌ |
| **ccxt** | Crypto | ✅ | Varies by exchange | ⚠️ Depends on exchange |
| **polygon** | Equities/Options | ✅ | Plan-dependent | ✅ |
| **alpaca** | Equities | ✅ | 200 req/min | ✅ |
| **alphavantage** | Equities/Forex | ❌ | 5 req/min (free) | ✅ |
| **csv** | Any | ❌ | N/A | ❌ |

---

## Per-Adapter Examples

### YFinance (Free Equities/ETFs)

**Best for**: Historical backtesting, US equities, no API key needed

```python
from rustybt.data.sources import DataSourceRegistry
import pandas as pd
import asyncio

async def main():
    source = DataSourceRegistry.get_source("yfinance")
    await source.ingest_to_bundle(
        bundle_name="tech-stocks",
        symbols=["AAPL", "MSFT", "GOOGL", "AMZN"],
        start=pd.Timestamp("2020-01-01"),
        end=pd.Timestamp("2023-12-31"),
        frequency="1d"
    )

asyncio.run(main())
```

**CLI equivalent**:
```bash
rustybt ingest-unified yfinance \
    --symbols AAPL,MSFT,GOOGL,AMZN \
    --start 2020-01-01 \
    --end 2023-12-31 \
    --frequency 1d \
    --bundle tech-stocks
```

---

### CCXT (Crypto Exchanges)

**Best for**: Cryptocurrency data from 100+ exchanges

```python
from rustybt.data.sources import DataSourceRegistry
import pandas as pd
import asyncio

async def main():
    source = DataSourceRegistry.get_source("ccxt", exchange="binance")
    await source.ingest_to_bundle(
        bundle_name="crypto-hourly",
        symbols=["BTC/USDT", "ETH/USDT", "SOL/USDT"],
        start=pd.Timestamp("2024-01-01"),
        end=pd.Timestamp("2024-12-31"),
        frequency="1h"
    )

asyncio.run(main())
```

**CLI equivalent**:
```bash
rustybt ingest-unified ccxt \
    --exchange binance \
    --symbols BTC/USDT,ETH/USDT,SOL/USDT \
    --start 2024-01-01 \
    --end 2024-12-31 \
    --frequency 1h \
    --bundle crypto-hourly
```

**Supported exchanges**: Run `rustybt ingest-unified ccxt --list-exchanges`

---

### Polygon (Premium Equities/Options)

**Best for**: High-quality data, minute bars, options chains

```python
from rustybt.data.sources import DataSourceRegistry
import pandas as pd
import asyncio

async def main():
    source = DataSourceRegistry.get_source(
        "polygon",
        api_key="YOUR_API_KEY"
    )
    await source.ingest_to_bundle(
        bundle_name="intraday-stocks",
        symbols=["AAPL", "TSLA"],
        start=pd.Timestamp("2024-01-01"),
        end=pd.Timestamp("2024-01-31"),
        frequency="1m"
    )

asyncio.run(main())
```

**Note**: Polygon API key required. Get one at [polygon.io](https://polygon.io)

---

### Alpaca (US Equities with Live Support)

**Best for**: Live trading + backtesting with same API

```python
from rustybt.data.sources import DataSourceRegistry
import pandas as pd
import asyncio

async def main():
    source = DataSourceRegistry.get_source(
        "alpaca",
        api_key="YOUR_API_KEY",
        api_secret="YOUR_API_SECRET"
    )
    await source.ingest_to_bundle(
        bundle_name="alpaca-stocks",
        symbols=["SPY", "QQQ", "IWM"],
        start=pd.Timestamp("2023-01-01"),
        end=pd.Timestamp("2023-12-31"),
        frequency="1d"
    )

asyncio.run(main())
```

**Note**: Supports both paper trading and live accounts

---

### AlphaVantage (Equities + Forex)

**Best for**: Forex pairs, fundamental data

```python
from rustybt.data.sources import DataSourceRegistry
import pandas as pd
import asyncio

async def main():
    source = DataSourceRegistry.get_source(
        "alphavantage",
        api_key="YOUR_API_KEY"
    )
    await source.ingest_to_bundle(
        bundle_name="forex-pairs",
        symbols=["EUR/USD", "GBP/USD", "USD/JPY"],
        start=pd.Timestamp("2023-01-01"),
        end=pd.Timestamp("2023-12-31"),
        frequency="1d"
    )

asyncio.run(main())
```

**Note**: Free tier limited to 5 requests/minute

---

### CSV (Local Files)

**Best for**: Custom data, proprietary sources

```python
from rustybt.data.sources import DataSourceRegistry
import pandas as pd
import asyncio

async def main():
    source = DataSourceRegistry.get_source(
        "csv",
        csv_dir="/path/to/csv/files"
    )
    # Ingest from CSV files
    # Expected format: {symbol}.csv with columns: date,open,high,low,close,volume
    await source.ingest_to_bundle(
        bundle_name="custom-data",
        symbols=["SYM1", "SYM2"],
        start=pd.Timestamp("2020-01-01"),
        end=pd.Timestamp("2023-12-31"),
        frequency="1d"
    )

asyncio.run(main())
```

**CSV format requirements**:
- Filename: `{symbol}.csv` (e.g., `AAPL.csv`)
- Required columns: `date`, `open`, `high`, `low`, `close`, `volume`
- Date format: ISO 8601 (`2023-01-15`)
- Decimal precision: Use string or Decimal for prices

---

## CLI Reference

### General Syntax

```bash
rustybt ingest-unified <source> [options]
```

### Common Options

| Option | Description | Example |
|--------|-------------|---------|
| `--symbols` | Comma-separated symbols | `--symbols AAPL,MSFT` |
| `--start` | Start date (ISO 8601) | `--start 2023-01-01` |
| `--end` | End date (ISO 8601) | `--end 2023-12-31` |
| `--frequency` | Data frequency | `--frequency 1d` |
| `--bundle` | Bundle name | `--bundle my-data` |
| `--api-key` | API key (if required) | `--api-key YOUR_KEY` |
| `--no-cache` | Disable caching | `--no-cache` |
| `--validate` | Validate after ingestion | `--validate` |

### Frequency Options

| Value | Description | Example Use Case |
|-------|-------------|------------------|
| `1d` | Daily bars | Long-term backtests |
| `1h` | Hourly bars | Intraday strategies |
| `5m` | 5-minute bars | High-frequency strategies |
| `1m` | 1-minute bars | Ultra high-frequency |

---

## Advanced Usage

### Batch Ingestion

Ingest multiple bundles in one script:

```python
import asyncio
import pandas as pd
from rustybt.data.sources import DataSourceRegistry

async def main():
    configs = [
        {
            "source": "yfinance",
            "bundle": "us-equities",
            "symbols": ["AAPL", "MSFT", "GOOGL"],
        },
        {
            "source": "ccxt",
            "bundle": "crypto",
            "symbols": ["BTC/USDT", "ETH/USDT"],
            "exchange": "binance",
        },
    ]

    for config in configs:
        source = DataSourceRegistry.get_source(config["source"], **config.get("params", {}))
        await source.ingest_to_bundle(
            bundle_name=config["bundle"],
            symbols=config["symbols"],
            start=pd.Timestamp("2023-01-01"),
            end=pd.Timestamp("2023-12-31"),
            frequency="1d"
        )

asyncio.run(main())
```

### Incremental Updates

Update existing bundle with new data:

```python
import asyncio
import pandas as pd
from rustybt.data.sources import DataSourceRegistry
from rustybt.data.bundles.metadata import BundleMetadata

async def main():
    # Load existing bundle metadata
    metadata = BundleMetadata.load("my-stocks")
    last_date = metadata.end_date

    # Get data source
    source = DataSourceRegistry.get_source("yfinance")

    # Ingest only new data
    await source.ingest_to_bundle(
        bundle_name="my-stocks",
        symbols=metadata.symbols,
        start=last_date + pd.Timedelta(days=1),
        end=pd.Timestamp.now(),
        frequency="1d",
        mode="append"  # Append to existing bundle
    )

asyncio.run(main())
```

### Validation After Ingestion

```python
import asyncio
import pandas as pd
from rustybt.data.sources import DataSourceRegistry
from rustybt.data.bundles.metadata import BundleMetadata

async def main():
    source = DataSourceRegistry.get_source("yfinance")

    await source.ingest_to_bundle(
        bundle_name="my-stocks",
        symbols=["AAPL"],
        start=pd.Timestamp("2023-01-01"),
        end=pd.Timestamp("2023-12-31"),
        frequency="1d"
    )

    # Validate bundle
    metadata = BundleMetadata.load("my-stocks")
    assert metadata.quality_score > 0.95, "Low quality data detected"
    assert metadata.missing_data_pct < 0.05, "Too much missing data"

asyncio.run(main())
```

---

## Troubleshooting

### Rate Limit Errors

**Error**: `RateLimitExceeded: Too many requests to API`

**Solution**: Use caching or slow down ingestion:
```python
import asyncio
import pandas as pd
from rustybt.data.sources import DataSourceRegistry

async def main():
    source = DataSourceRegistry.get_source("yfinance")
    symbols = ["AAPL", "MSFT", "GOOGL"]

    for symbol in symbols:
        await source.ingest_to_bundle(
            bundle_name=f"bundle-{symbol}",
            symbols=[symbol],
            start=pd.Timestamp("2023-01-01"),
            end=pd.Timestamp("2023-12-31"),
            frequency="1d"
        )
        await asyncio.sleep(1)  # 1 second delay between symbols

asyncio.run(main())
```

### Missing Data

**Error**: `NoDataAvailableError: Symbol AAPL has no data for 2023-01-15`

**Possible causes**:
- Market holiday (no trading)
- Symbol delisted or renamed
- API downtime

**Solution**: Check metadata quality score:
```python
metadata = BundleMetadata.load("my-bundle")
print(f"Missing data: {metadata.missing_data_pct*100:.2f}%")
```

### API Authentication Errors

**Error**: `AuthenticationError: Invalid API key`

**Solution**: Set API key via environment variable:
```bash
export POLYGON_API_KEY="your_key_here"
export ALPACA_API_KEY="your_key_here"
export ALPACA_API_SECRET="your_secret_here"
```

---

## Next Steps

- [Caching Guide](caching-guide.md) - Optimize performance with caching
- [Migration Guide](migrating-to-unified-data.md) - Upgrade from old APIs
- [API Reference](../api/datasource-api.md) - Full DataSource API documentation
