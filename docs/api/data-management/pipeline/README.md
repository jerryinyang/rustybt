# Data Pipeline System

The RustyBT data pipeline system orchestrates the flow of market data from external sources through transformation, validation, and storage into production-ready bundles.

## Overview

RustyBT provides two complementary pipeline systems:

1. **Data Ingestion Pipeline** - Fetches, validates, and stores market data
2. **Computation Pipeline** - Processes data for strategy execution (Zipline Pipeline API)

This section focuses on the **Data Ingestion Pipeline** which transforms raw market data into validated, Decimal-precision bundles ready for backtesting and live trading.

## Architecture

### High-Level Data Flow

```
┌──────────────┐
│ Data Sources │  (Yahoo Finance, CCXT, Polygon, etc.)
└──────┬───────┘
       │
       ↓
┌──────────────┐
│   Adapters   │  (Unified DataSource API)
└──────┬───────┘
       │
       ↓
┌──────────────┐
│  Validation  │  (OHLCV checks, quality scoring)
└──────┬───────┘
       │
       ↓
┌──────────────┐
│   Transform  │  (Decimal conversion, partitioning)
└──────┬───────┘
       │
       ↓
┌──────────────┐
│    Storage   │  (Parquet bundles with metadata)
└──────────────┘
```

### Component Responsibilities

| Component | Responsibility | Output |
|-----------|---------------|--------|
| **Data Sources** | Fetch raw OHLCV data from external APIs | Raw DataFrames (float64) |
| **Adapters** | Normalize data format, handle API specifics | Standardized DataFrames |
| **Validation** | Check OHLCV relationships, detect gaps | Quality report |
| **Transform** | Convert to Decimal, partition by date | Validated DataFrames |
| **Storage** | Write Parquet files, track metadata | Production bundle |

## Pipeline Stages

### Stage 1: Data Fetching

```python
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

# Initialize source
source = YFinanceAdapter()

# Fetch raw data
df = await source.fetch(
    symbols=["AAPL", "GOOGL"],
    start=pd.Timestamp("2024-01-01"),
    end=pd.Timestamp("2024-12-31"),
    frequency="1d"
)
```

**What Happens**:
- API rate limiting enforced
- Retry logic for transient failures
- Data normalized to standard schema
- Timestamps converted to UTC

### Stage 2: Validation

```python
from rustybt.data.polars.validation import validate_ohlcv_relationships

# Validate OHLCV relationships
validate_ohlcv_relationships(df)  # Raises DataError if invalid

# Checks performed:
# - high >= low
# - high >= open, close
# - low <= open, close
# - volume >= 0
# - No negative prices
```

**What Happens**:
- OHLCV relationship validation
- Gap detection
- Duplicate detection
- Price continuity checks
- Quality score calculation

### Stage 3: Transformation

```python
# Convert to Decimal precision
df = df.with_columns([
    pl.col("open").cast(pl.Decimal(18, 8)),
    pl.col("high").cast(pl.Decimal(18, 8)),
    pl.col("low").cast(pl.Decimal(18, 8)),
    pl.col("close").cast(pl.Decimal(18, 8)),
    pl.col("volume").cast(pl.Decimal(18, 8))
])

# Add partitioning columns
df = df.with_columns([
    pl.col("date").dt.year().alias("year"),
    pl.col("date").dt.month().alias("month")
])
```

**What Happens**:
- float64 → Decimal conversion
- Date-based partitioning
- Symbol ID (sid) assignment
- Column standardization

### Stage 4: Storage

```python
from rustybt.data.polars.parquet_writer import ParquetWriter

# Write to partitioned Parquet
writer = ParquetWriter(bundle_path="data/bundles/my_bundle")
await writer.write_daily_bars(df)

# Creates structure:
# data/bundles/my_bundle/
# ├── daily_bars/
# │   ├── year=2024/
# │   │   ├── month=01/data.parquet
# │   │   └── month=02/data.parquet
# │   └── ...
# └── metadata.db
```

**What Happens**:
- Partitioned Parquet write
- Metadata catalog update
- Quality metrics recorded
- Checksums computed

### Stage 5: Metadata Tracking

```python
from rustybt.data.bundles.metadata import BundleMetadata

# Load metadata
metadata = BundleMetadata.load("my_bundle")

print(f"Symbols: {metadata.symbols}")
print(f"Date range: {metadata.start_date} to {metadata.end_date}")
print(f"Quality score: {metadata.quality_score:.2%}")
print(f"Missing data: {metadata.missing_data_pct:.2%}")
```

**What Happens**:
- Bundle statistics computed
- Data quality scored
- Lineage tracked
- Audit trail created

## Quick Start

### Basic Ingestion

```python
import asyncio
import pandas as pd
from rustybt.data.sources import DataSourceRegistry

async def ingest_stock_data():
    # Get data source
    source = DataSourceRegistry.get_source("yfinance")

    # Ingest to bundle
    bundle_path = await source.ingest_to_bundle(
        bundle_name="my_stocks",
        symbols=["AAPL", "MSFT", "GOOGL"],
        start=pd.Timestamp("2023-01-01"),
        end=pd.Timestamp("2023-12-31"),
        frequency="1d"
    )

    print(f"✓ Bundle created: {bundle_path}")

asyncio.run(ingest_stock_data())
```

### Crypto Ingestion

```python
async def ingest_crypto_data():
    # Get CCXT source for Binance
    source = DataSourceRegistry.get_source("ccxt", exchange="binance")

    # Ingest hourly crypto data
    bundle_path = await source.ingest_to_bundle(
        bundle_name="crypto_hourly",
        symbols=["BTC/USDT", "ETH/USDT"],
        start=pd.Timestamp("2024-01-01"),
        end=pd.Timestamp("2024-01-31"),
        frequency="1h"
    )

    print(f"✓ Crypto bundle created: {bundle_path}")

asyncio.run(ingest_crypto_data())
```

### Custom CSV Ingestion

```python
async def ingest_custom_data():
    # Get CSV source
    source = DataSourceRegistry.get_source("csv")

    # Ingest from CSV file
    bundle_path = await source.ingest_to_bundle(
        bundle_name="custom_data",
        csv_path="data/my_data.csv",
        symbol_column="ticker",
        date_column="date",
        price_columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume"
        }
    )

    print(f"✓ Custom bundle created: {bundle_path}")

asyncio.run(ingest_custom_data())
```

## Pipeline Configuration

### Configuration File

Create `pipeline_config.yaml` for repeatable ingestion:

```yaml
# Data sources to ingest
sources:
  - name: stocks
    adapter: yfinance
    symbols:
      - AAPL
      - MSFT
      - GOOGL
      - AMZN
    start_date: "2020-01-01"
    end_date: "2024-12-31"
    frequency: 1d
    bundle: stocks-daily

  - name: crypto
    adapter: ccxt
    exchange: binance
    symbols:
      - BTC/USDT
      - ETH/USDT
    start_date: "2024-01-01"
    end_date: "2024-12-31"
    frequency: 1h
    bundle: crypto-hourly

# Quality thresholds
quality:
  min_quality_score: 0.95
  max_missing_pct: 0.05
  fail_on_low_quality: true

# Validation rules
validation:
  check_ohlcv_relationships: true
  check_price_continuity: true
  detect_gaps: true
  max_gap_days: 7

# Storage settings
storage:
  partition_by:
    - year
    - month
  compression: snappy
  decimal_precision: 8
```

### Run from Configuration

```python
# Note: Advanced pipeline orchestration features are planned for future releases
```

## Quality Assurance

### Automated Quality Checks

Every pipeline run includes:

1. **OHLCV Validation**
   - High >= Low
   - High >= Open, Close
   - Low <= Open, Close
   - Volume >= 0

2. **Data Continuity**
   - Gap detection
   - Duplicate detection
   - Price jump detection

3. **Metadata Tracking**
   - Row counts
   - Date coverage
   - Symbol completeness
   - Quality scoring

### Quality Score Calculation

```python
quality_score = (
    (1.0 - missing_data_pct) * 0.4 +      # 40% weight: completeness
    (1.0 - duplicate_pct) * 0.2 +         # 20% weight: no duplicates
    (1.0 - gap_pct) * 0.2 +                # 20% weight: no gaps
    ohlcv_valid_pct * 0.2                  # 20% weight: valid OHLCV
)
```

**Score Interpretation**:
- **≥ 0.95**: Production ready
- **0.85-0.95**: Acceptable with warnings
- **< 0.85**: Requires review

## Monitoring

### Pipeline Metrics

Track pipeline health with built-in metrics:

```python
# Note: Advanced pipeline orchestration features are planned for future releases
```

### Alerting

Configure alerts for pipeline issues:

```python
# Note: Advanced pipeline orchestration features are planned for future releases
```

## Best Practices

### 1. Incremental Updates

Ingest new data incrementally instead of full reloads:

```python
# Get last ingested date
metadata = BundleMetadata.load("my_bundle")
last_date = metadata.end_date

# Ingest only new data
await source.ingest_to_bundle(
    bundle_name="my_bundle",
    symbols=symbols,
    start=last_date + pd.Timedelta(days=1),
    end=pd.Timestamp.now(),
    frequency="1d",
    mode="append"  # Append to existing bundle
)
```

### 2. Rate Limit Management

Respect API rate limits:

```python
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

# Configure rate limiting
source = YFinanceAdapter(
    rate_limit=1000,  # Requests per hour
    retry_count=3,
    retry_delay=5.0
)
```

### 3. Error Handling

Handle failures gracefully:

```python
from rustybt.data.polars.validation import DataError

try:
    bundle_path = await source.ingest_to_bundle(...)
except DataError as e:
    # Data quality issue
    logger.error(f"Data quality failure: {e}")
    # Retry with different parameters or alert team

except Exception as e:
    # Network or API issue
    logger.error(f"Ingestion failed: {e}")
    # Implement retry logic
```

### 4. Validation First

Always validate before storage:

```python
# Fetch data
df = await source.fetch(symbols, start, end)

# Validate BEFORE storage
try:
    validate_ohlcv_relationships(df)
except DataError as e:
    logger.error(f"Invalid data detected: {e}")
    # Fix or reject bad data
    raise

# Only store validated data
await writer.write_daily_bars(df)
```

### 5. Idempotent Pipelines

Make pipelines safe to re-run:

```python
async def safe_ingest(bundle_name, **kwargs):
    """Idempotent ingestion - safe to retry."""
    # Check if bundle exists
    if bundle_exists(bundle_name):
        # Clean existing data for date range
        await clean_bundle_range(bundle_name, kwargs["start"], kwargs["end"])

    # Ingest (will not duplicate)
    await source.ingest_to_bundle(bundle_name=bundle_name, **kwargs)
```

## Performance Optimization

### Parallel Ingestion

Ingest multiple symbols concurrently:

```python
import asyncio

async def ingest_parallel(symbols, **kwargs):
    """Ingest multiple symbols in parallel."""
    tasks = [
        source.fetch(symbols=[symbol], **kwargs)
        for symbol in symbols
    ]

    # Fetch concurrently
    results = await asyncio.gather(*tasks)

    # Combine and store
    df = pl.concat(results)
    await writer.write_daily_bars(df)
```

### Batch Processing

Process data in batches for large ingestions:

```python
# Split into batches
batch_size = 50
symbol_batches = [symbols[i:i+batch_size] for i in range(0, len(symbols), batch_size)]

for batch in symbol_batches:
    df = await source.fetch(batch, start, end)
    await writer.write_daily_bars(df)
    print(f"✓ Batch complete: {len(batch)} symbols")
```

## See Also

- [Data Sources](../adapters/README.md) - Available data sources and adapters
- [Bundle System](../catalog/bundle-system.md) - Bundle creation and management
- [Metadata Tracking](../catalog/metadata-tracking.md) - Quality tracking and lineage
- [Computation Pipeline](../../computation/pipeline-api.md) - Factors, filters, loaders, and expressions
- [Examples](../../../examples/README.md) - Complete ingestion examples
