# Data Ingestion Guide

**Last Updated**: 2025-10-29

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

source = DataSourceRegistry.get_source("yfinance")
source.ingest_to_bundle(
    bundle_name="my-stocks",
    symbols=["AAPL", "MSFT", "GOOGL"],
    start=pd.Timestamp("2023-01-01"),
    end=pd.Timestamp("2023-12-31"),
    frequency="1d"
)
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
| **databento** | Futures/Equities/Options | ❌ | N/A (local files) | ❌ |
| **csv** | Any | ❌ | N/A | ❌ |

---

## Per-Adapter Examples

### YFinance (Free Equities/ETFs)

**Best for**: Historical backtesting, US equities, no API key needed

```python
from rustybt.data.sources import DataSourceRegistry
import pandas as pd

source = DataSourceRegistry.get_source("yfinance")
source.ingest_to_bundle(
    bundle_name="tech-stocks",
    symbols=["AAPL", "MSFT", "GOOGL", "AMZN"],
    start=pd.Timestamp("2020-01-01"),
    end=pd.Timestamp("2023-12-31"),
    frequency="1d"
)
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

source = DataSourceRegistry.get_source("ccxt", exchange_id="binance")
source.ingest_to_bundle(
    bundle_name="crypto-hourly",
    symbols=["BTC/USDT", "ETH/USDT", "SOL/USDT"],
    start=pd.Timestamp("2024-01-01"),
    end=pd.Timestamp("2024-12-31"),
    frequency="1h",
    asset_type="crypto"  # Assigns 24/7 calendar for crypto
)
```

**CLI equivalent**:
```bash
rustybt ingest-unified ccxt \
    --exchange binance \
    --symbols BTC/USDT,ETH/USDT,SOL/USDT \
    --start 2024-01-01 \
    --end 2024-12-31 \
    --frequency 1h \
    --bundle crypto-hourly \
    --asset-type crypto
```

**Supported exchanges**: Run `rustybt ingest-unified ccxt --list-exchanges`

---

### Polygon (Premium Equities/Options)

**Best for**: High-quality data, minute bars, options chains

```python
from rustybt.data.sources import DataSourceRegistry
import pandas as pd

source = DataSourceRegistry.get_source(
    "polygon",
    api_key="YOUR_API_KEY"
)
source.ingest_to_bundle(
    bundle_name="intraday-stocks",
    symbols=["AAPL", "TSLA"],
    start=pd.Timestamp("2024-01-01"),
    end=pd.Timestamp("2024-01-31"),
    frequency="1m"
)
```

**Note**: Polygon API key required. Get one at [polygon.io](https://polygon.io)

---

### Alpaca (US Equities with Live Support)

**Best for**: Live trading + backtesting with same API

```python
from rustybt.data.sources import DataSourceRegistry
import pandas as pd

source = DataSourceRegistry.get_source(
    "alpaca",
    api_key="YOUR_API_KEY",
    api_secret="YOUR_API_SECRET"
)
source.ingest_to_bundle(
    bundle_name="alpaca-stocks",
    symbols=["SPY", "QQQ", "IWM"],
    start=pd.Timestamp("2023-01-01"),
    end=pd.Timestamp("2023-12-31"),
    frequency="1d"
)
```

**Note**: Supports both paper trading and live accounts

---

### AlphaVantage (Equities + Forex)

**Best for**: Forex pairs, fundamental data

```python
from rustybt.data.sources import DataSourceRegistry
import pandas as pd

source = DataSourceRegistry.get_source(
    "alphavantage",
    api_key="YOUR_API_KEY"
)
source.ingest_to_bundle(
    bundle_name="forex-pairs",
    symbols=["EUR/USD", "GBP/USD", "USD/JPY"],
    start=pd.Timestamp("2023-01-01"),
    end=pd.Timestamp("2023-12-31"),
    frequency="1d",
    asset_type="forex"  # Assigns 24/5 calendar for forex
)
```

**Note**: Free tier limited to 5 requests/minute

---

### Databento (Futures/Equities/Options)

**Best for**: High-quality historical futures, equities, and options data from Databento packages

```python
from rustybt.data.sources import DataSourceRegistry
import pandas as pd

source = DataSourceRegistry.get_source(
    "databento",
    data_path="/path/to/databento-package.zip"  # or extracted folder
)
source.ingest_to_bundle(
    bundle_name="cme-futures",
    symbols=[],  # Empty list = all symbols in package
    start=pd.Timestamp("2020-11-01"),
    end=pd.Timestamp("2020-11-30"),
    frequency="1h"
)
```

**CLI equivalent**:
```bash
rustybt ingest-unified databento \
    --data-path /path/to/GLBX-20251101-N5U545U54V.zip \
    --bundle cme-futures \
    --start 2020-11-01 \
    --end 2020-11-30 \
    --frequency 1h
```

**Features**:
- ✅ Automatic ZIP extraction and zstd decompression
- ✅ Multi-asset packages (ingest hundreds of symbols at once)
- ✅ Symbol and date range filtering
- ✅ Supports 1m, 5m, 15m, 30m, 1h, 1d frequencies

**See**: [Databento Import Guide](databento-data-import.md) for detailed examples

---

### CSV (Local Files)

**Best for**: Custom data, proprietary sources

```python
from rustybt.data.sources import DataSourceRegistry
import pandas as pd

source = DataSourceRegistry.get_source(
    "csv",
    csv_dir="/path/to/csv/files"
)
# Ingest from CSV files
# Expected format: {symbol}.csv with columns: date,open,high,low,close,volume
source.ingest_to_bundle(
    bundle_name="custom-data",
    symbols=["SYM1", "SYM2"],
    start=pd.Timestamp("2020-01-01"),
    end=pd.Timestamp("2023-12-31"),
    frequency="1d"
)
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
| `--asset-type` | Asset type for calendar selection | `--asset-type forex` |
| `--api-key` | API key (if required) | `--api-key YOUR_KEY` |

### Frequency Options

| Value | Description | Example Use Case |
|-------|-------------|------------------|
| `1d` | Daily bars | Long-term backtests |
| `1h` | Hourly bars | Intraday strategies |
| `5m` | 5-minute bars | High-frequency strategies |
| `1m` | 1-minute bars | Ultra high-frequency |

---

## Asset Types and Trading Calendars

The `asset_type` parameter determines which trading calendar is assigned to your bundle. This is critical for ensuring your backtest runs on the correct trading days.

### Calendar Assignment

| Asset Type | Calendar | Trading Hours | Holidays |
|------------|----------|---------------|----------|
| `forex` | 24/5 | Sunday 5PM ET - Friday 5PM ET | None |
| `crypto` | 24/7 | Continuous | None |
| `equity` | XNYS | Mon-Fri 9:30AM-4PM ET | NYSE holidays |
| `future` | XNYS | Mon-Fri 9:30AM-4PM ET | NYSE holidays |

### When to Use Each Type

**Forex (`asset_type="forex"`)**:
- For currency pairs (e.g., `EURUSD=X`, `GBPUSD=X`)
- Trades Sunday evening through Friday evening
- Automatically skips weekends and Saturday

```python
source.ingest_to_bundle(
    bundle_name="forex-daily",
    symbols=["EURUSD=X", "GBPUSD=X"],
    start=pd.Timestamp("2023-01-01"),
    end=pd.Timestamp("2023-12-31"),
    frequency="1d",
    asset_type="forex"  # 24/5 calendar
)
```

**Crypto (`asset_type="crypto"`)**:
- For cryptocurrencies (e.g., `BTC/USDT`, `ETH/USDT`)
- Trades 24/7 with no holidays
- Includes weekends and all days

```python
source.ingest_to_bundle(
    bundle_name="crypto-daily",
    symbols=["BTC/USDT", "ETH/USDT"],
    start=pd.Timestamp("2024-01-01"),
    end=pd.Timestamp("2024-12-31"),
    frequency="1d",
    asset_type="crypto"  # 24/7 calendar
)
```

**Equity (`asset_type="equity"`)**:
- For stocks and ETFs (e.g., `AAPL`, `MSFT`)
- Follows NYSE business hours
- Automatically skips NYSE holidays

```python
source.ingest_to_bundle(
    bundle_name="us-stocks",
    symbols=["AAPL", "MSFT"],
    start=pd.Timestamp("2023-01-01"),
    end=pd.Timestamp("2023-12-31"),
    frequency="1d",
    asset_type="equity"  # XNYS calendar (default)
)
```

### Automatic Type Inference

If you don't specify `asset_type`, the framework attempts to infer it from symbol patterns:

- Symbols ending in `=X` → forex
- Symbols containing `/` → crypto
- Other symbols → equity (default)

**However**, we recommend **always explicitly specifying `asset_type`** to avoid inference errors.

---

## Automatic Date Adjustment

The framework automatically adjusts requested dates to match the bundle's trading calendar boundaries.

### Why Date Adjustment Happens

Each calendar has a start date based on available historical data:

| Calendar | Start Date | Reason |
|----------|-----------|---------|
| 24/5 (forex) | 2005-10-28 | Data availability |
| 24/7 (crypto) | 2010-07-17 | Bitcoin inception |
| XNYS (equity) | 1990-01-02 | NYSE data coverage |

### Example: Forex Date Adjustment

```python
source.ingest_to_bundle(
    bundle_name="forex-data",
    symbols=["EURUSD=X"],
    start=pd.Timestamp("2000-01-01"),  # Before 24/5 calendar start
    end=pd.Timestamp("2023-12-31"),
    frequency="1d",
    asset_type="forex"
)
# WARNING: Adjusted start date from 2000-01-01 to 2005-10-28 (24/5 calendar start)
```

### What Gets Adjusted

- **Start date before calendar start** → Adjusted to calendar start date
- **End date after calendar end** → Adjusted to calendar end date
- **Dates on non-trading days** → Adjusted to nearest valid trading day

### How to Avoid Adjustment Warnings

Check calendar boundaries before ingesting:

```python
from rustybt.data.bundles.calendar import TradingCalendarRegistry

# Get calendar
calendar = TradingCalendarRegistry.get_calendar("24/5")

# Check boundaries
print(f"Calendar start: {calendar.first_session}")
print(f"Calendar end: {calendar.last_session}")

# Use valid dates for ingestion
source.ingest_to_bundle(
    bundle_name="forex-data",
    symbols=["EURUSD=X"],
    start=calendar.first_session,  # No adjustment needed
    end=pd.Timestamp("2023-12-31"),
    frequency="1d",
    asset_type="forex"
)
```

---

## Migrating Existing Bundles

If you have existing forex or crypto bundles created before the calendar feature, they default to the XNYS calendar. This may cause errors on weekends or NYSE holidays.

### How to Migrate

Re-ingest your bundles with the correct `asset_type` parameter:

**Example: Migrate Forex Bundle**:

```python
from rustybt.data.sources import DataSourceRegistry
import pandas as pd

source = DataSourceRegistry.get_source("yfinance")

# Re-ingest with correct calendar
source.ingest_to_bundle(
    bundle_name="forex-1d",  # Overwrites existing bundle
    symbols=["EURUSD=X", "GBPUSD=X", "USDJPY=X"],
    start=pd.Timestamp("2005-10-28"),  # 24/5 calendar start
    end=pd.Timestamp("2023-12-31"),
    frequency="1d",
    asset_type="forex"  # ← Critical: assigns 24/5 calendar
)
```

**Example: Migrate Crypto Bundle**:

```python
source = DataSourceRegistry.get_source("ccxt", exchange_id="binance")

# Re-ingest with correct calendar
source.ingest_to_bundle(
    bundle_name="crypto-1h",  # Overwrites existing bundle
    symbols=["BTC/USDT", "ETH/USDT"],
    start=pd.Timestamp("2020-01-01"),
    end=pd.Timestamp("2024-12-31"),
    frequency="1h",
    asset_type="crypto"  # ← Critical: assigns 24/7 calendar
)
```

### Checking Bundle Calendar

To check which calendar a bundle is using:

```python
from rustybt.data.bundles.metadata import BundleMetadata

metadata = BundleMetadata.load("my-bundle")
print(f"Bundle calendar: {metadata.calendar_name}")
# Output: "24/5" for forex, "24/7" for crypto, "XNYS" for equity
```

If `calendar_name` is `None` or `"XNYS"` for a forex/crypto bundle, you should re-ingest with the correct `asset_type`.

---

## Advanced Usage

### Batch Ingestion

Ingest multiple bundles in one script:

```python
import pandas as pd
from rustybt.data.sources import DataSourceRegistry

configs = [
    {
        "source": "yfinance",
        "bundle": "us-equities",
        "symbols": ["AAPL", "MSFT", "GOOGL"],
        "asset_type": "equity",
    },
    {
        "source": "ccxt",
        "bundle": "crypto",
        "symbols": ["BTC/USDT", "ETH/USDT"],
        "exchange": "binance",
        "asset_type": "crypto",
    },
]

for config in configs:
    source = DataSourceRegistry.get_source(config["source"], **config.get("params", {}))
    source.ingest_to_bundle(
        bundle_name=config["bundle"],
        symbols=config["symbols"],
        start=pd.Timestamp("2023-01-01"),
        end=pd.Timestamp("2023-12-31"),
        frequency="1d",
        asset_type=config["asset_type"]  # Specify asset type for calendar selection
    )
```

### Incremental Updates

Update existing bundle with new data:

```python
import pandas as pd
from rustybt.data.sources import DataSourceRegistry
from rustybt.data.bundles.metadata import BundleMetadata

# Load existing bundle metadata
metadata = BundleMetadata.load("my-stocks")
last_date = metadata.end_date

# Get data source
source = DataSourceRegistry.get_source("yfinance")

# Ingest only new data
source.ingest_to_bundle(
    bundle_name="my-stocks",
    symbols=metadata.symbols,
    start=last_date + pd.Timedelta(days=1),
    end=pd.Timestamp.now(),
    frequency="1d",
    mode="append"  # Append to existing bundle
)
```

### Validation After Ingestion

After ingesting data, validate bundle quality using the CLI:

```bash
# Ingest data
rustybt ingest-unified yfinance --bundle my-stocks --symbols AAPL \
    --start 2023-01-01 --end 2023-12-31 --frequency 1d

# Validate bundle quality
rustybt bundle validate my-stocks
```

The validation command checks:
- OHLCV relationship constraints (High ≥ Low, Close/Open in range)
- Duplicate timestamps
- Symbol metadata consistency
- Missing trading days

**Validation results are automatically persisted** to bundle metadata and displayed in `rustybt bundle list` and `rustybt bundle info`.

Python API equivalent:

```python
import pandas as pd
from rustybt.data.sources import DataSourceRegistry

source = DataSourceRegistry.get_source("yfinance")

source.ingest_to_bundle(
    bundle_name="my-stocks",
    symbols=["AAPL"],
    start=pd.Timestamp("2023-01-01"),
    end=pd.Timestamp("2023-12-31"),
    frequency="1d"
)
```

Then run `rustybt bundle validate my-stocks` to validate and persist results.

---

## Troubleshooting

### Rate Limit Errors

**Error**: `RateLimitExceeded: Too many requests to API`

**Solution**: Use caching or slow down ingestion:
```python
import pandas as pd
import time
from rustybt.data.sources import DataSourceRegistry

source = DataSourceRegistry.get_source("yfinance")
symbols = ["AAPL", "MSFT", "GOOGL"]

for symbol in symbols:
    source.ingest_to_bundle(
        bundle_name=f"bundle-{symbol}",
        symbols=[symbol],
        start=pd.Timestamp("2023-01-01"),
        end=pd.Timestamp("2023-12-31"),
        frequency="1d"
    )
    time.sleep(1)  # 1 second delay between symbols
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
