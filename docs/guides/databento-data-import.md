# Databento Data Import Guide

**Last Updated**: 2025-11-01

## Overview

Databento provides high-quality market data for futures, equities, options, and crypto. This guide shows you how to ingest Databento data packages into rustybt bundles.

**Key Features**:
- ✅ Automatic ZIP extraction
- ✅ zstd decompression
- ✅ Multi-asset packages (ingest hundreds of symbols at once)
- ✅ Symbol filtering
- ✅ Date range filtering
- ✅ Metadata preservation

---

## Quick Start

### Command Line

```bash
# Ingest entire Databento package
rustybt ingest-unified databento \
  --data-path /path/to/databento-package.zip \
  --bundle futures-data \
  --start 2020-11-01 \
  --end 2020-11-30 \
  --frequency 1h
```

### Python API

```python
from rustybt.data.sources import DataSourceRegistry
import pandas as pd

# Create adapter
adapter = DataSourceRegistry.get_source(
    "databento",
    data_path="/path/to/databento-package.zip"
)

# Ingest to bundle
adapter.ingest_to_bundle(
    bundle_name="futures-data",
    symbols=[],  # Empty list = all symbols in package
    start=pd.Timestamp("2020-11-01"),
    end=pd.Timestamp("2020-11-30"),
    frequency="1h"
)
```

---

## Understanding Databento Packages

### Package Structure

Databento data comes packaged as ZIP files containing:

```
databento-package.zip
├── manifest.json          # File listing with hashes
├── metadata.json          # Query parameters and date range
├── condition.json         # Data availability by date
├── symbology.csv          # Symbol-to-instrument_id mapping
└── *.ohlcv-*.csv.zst     # Compressed OHLCV data
```

### Metadata Example

```json
{
  "dataset": "GLBX.MDP3",      // CME Globex futures
  "schema": "ohlcv-1h",         // 1-hour OHLCV bars
  "symbols": ["ES.FUT", "NQ.FUT", ...],  // 29 symbols
  "start": 1604188800000000000,  // 2020-11-01 (nanoseconds)
  "end": 1761955200000000000     // 2025-10-31 (nanoseconds)
}
```

---

## Python API Examples

### Example 1: Ingest Full Package

```python
from rustybt.data.adapters.databento_adapter import DatabentoAdapter, DatabentoConfig
import pandas as pd

# Configure adapter
config = DatabentoConfig(
    data_path="/path/to/GLBX-package.zip"
)
adapter = DatabentoAdapter(config)

# Ingest all data
adapter.ingest_to_bundle(
    bundle_name="cme-futures",
    symbols=[],  # All symbols in package
    start=pd.Timestamp("2023-01-01"),
    end=pd.Timestamp("2023-12-31"),
    frequency="1h"
)
```

### Example 2: Ingest Specific Symbols

```python
# Only ingest E-mini S&P 500 and Nasdaq futures
adapter.ingest_to_bundle(
    bundle_name="emini-futures",
    symbols=["ESZ0", "NQZ0"],  # Specific contracts
    start=pd.Timestamp("2020-12-01"),
    end=pd.Timestamp("2020-12-31"),
    frequency="1h"
)
```

### Example 3: Fetch Data Without Persisting

```python
import asyncio

# Fetch data for analysis
async def analyze_data():
    df = await adapter.fetch(
        symbols=["ESZ0"],
        start=pd.Timestamp("2020-11-01"),
        end=pd.Timestamp("2020-11-30"),
        frequency="1h"
    )

    print(f"Fetched {len(df)} rows")
    print(df.head())

    return df

# Run async function
df = asyncio.run(analyze_data())
```

### Example 4: Work with Extracted Folders

```python
# If you've already extracted the ZIP
config = DatabentoConfig(
    data_path="/path/to/extracted-folder/"
)
adapter = DatabentoAdapter(config)

# Works the same way
adapter.ingest_to_bundle(...)
```

---

## CLI Examples

### List Available Sources

```bash
rustybt ingest-unified --list-sources
# Output includes: databento
```

### Get Databento Source Info

```bash
rustybt ingest-unified --source-info databento
```

### Ingest from ZIP File

```bash
rustybt ingest-unified databento \
  --data-path ~/downloads/GLBX-20251101-N5U545U54V.zip \
  --bundle cme-futures-hourly \
  --start 2020-11-01 \
  --end 2020-12-31 \
  --frequency 1h
```

### Ingest from Extracted Folder

```bash
rustybt ingest-unified databento \
  --data-path ~/data/databento/GLBX-20251101-N5U545U54V/ \
  --bundle cme-futures-hourly \
  --start 2023-01-01 \
  --end 2023-12-31 \
  --frequency 1h
```

---

## Data Schema

### Input Format (Databento CSV)

```
ts_event,rtype,publisher_id,instrument_id,open,high,low,close,volume,symbol
2020-11-01T23:00:00.000000000Z,34,1,18581,0.749250000,0.749300000,...
```

### Output Format (rustybt Standard)

After ingestion, data is converted to rustybt's standard OHLCV schema:

| Column | Type | Description |
|--------|------|-------------|
| `timestamp` | datetime[μs, UTC] | Event timestamp in UTC |
| `symbol` | str | Symbol identifier |
| `open` | float64 | Opening price |
| `high` | float64 | High price |
| `low` | float64 | Low price |
| `close` | float64 | Closing price |
| `volume` | int64 | Trading volume |

---

## Supported Frequencies

Databento packages support various time resolutions:

- `1m` - 1-minute bars
- `5m` - 5-minute bars
- `15m` - 15-minute bars
- `30m` - 30-minute bars
- `1h` - 1-hour bars (most common)
- `1d` - Daily bars

**Note**: The frequency is encoded in the package filename (e.g., `ohlcv-1h` = 1-hour bars).

---

## Symbol Filtering

### Filter During Ingestion

```python
# Only ingest specific symbols
adapter.ingest_to_bundle(
    bundle_name="selected-futures",
    symbols=["ESH1", "NQH1", "RTY H1"],  # March 2021 contracts
    start=pd.Timestamp("2021-01-01"),
    end=pd.Timestamp("2021-03-31"),
    frequency="1h"
)
```

### Ingest All Symbols

```python
# Empty list = all symbols in package
adapter.ingest_to_bundle(
    bundle_name="all-futures",
    symbols=[],  # All symbols
    start=pd.Timestamp("2023-01-01"),
    end=pd.Timestamp("2023-12-31"),
    frequency="1h"
)
```

---

## Date Range Filtering

### Narrow Date Range

```python
# Only ingest November 2020
adapter.ingest_to_bundle(
    bundle_name="nov-2020",
    symbols=[],
    start=pd.Timestamp("2020-11-01"),
    end=pd.Timestamp("2020-11-30"),
    frequency="1h"
)
```

### Full Package Date Range

```python
# Ingest entire date range from metadata
metadata = adapter._parse_metadata()
import pandas as pd

# Convert nanosecond timestamps
start = pd.Timestamp(metadata.start, unit="ns")
end = pd.Timestamp(metadata.end, unit="ns")

adapter.ingest_to_bundle(
    bundle_name="full-range",
    symbols=[],
    start=start,
    end=end,
    frequency="1h"
)
```

---

## Advanced Usage

### Inspect Package Metadata

```python
from rustybt.data.adapters.databento_adapter import DatabentoAdapter, DatabentoConfig

config = DatabentoConfig(data_path="/path/to/package.zip")
adapter = DatabentoAdapter(config)

# Parse metadata
metadata = adapter._parse_metadata()

print(f"Dataset: {metadata.dataset}")
print(f"Schema: {metadata.schema}")
print(f"Symbols: {len(metadata.symbols)} symbols")
print(f"Date range: {metadata.start} to {metadata.end}")

# Parse manifest
manifest = adapter._parse_manifest()
print(f"Files: {len(manifest.files)}")
for file_info in manifest.files:
    print(f"  - {file_info.filename} ({file_info.size} bytes)")
```

### Custom Processing

```python
import asyncio

async def process_databento_data():
    adapter = DatabentoAdapter(DatabentoConfig(
        data_path="/path/to/package.zip"
    ))

    # Fetch raw data
    df = await adapter.fetch(
        symbols=[],
        start=pd.Timestamp("2020-11-01"),
        end=pd.Timestamp("2020-11-30"),
        frequency="1h"
    )

    # Custom processing
    df_filtered = df.filter(pl.col("volume") > 100)  # High volume only
    df_sorted = df_filtered.sort("timestamp")

    # Save to custom format
    df_sorted.write_parquet("custom_output.parquet")

    return df_sorted

df = asyncio.run(process_databento_data())
```

---

## Troubleshooting

### Issue: ZIP extraction fails

**Error**: `InvalidDataError: Invalid ZIP file`

**Solution**: Verify the ZIP file is not corrupted:
```bash
unzip -t databento-package.zip
```

### Issue: Missing zstandard library

**Error**: `ModuleNotFoundError: No module named 'zstandard'`

**Solution**: Install zstandard:
```bash
pip install zstandard
```

### Issue: Out of memory

**Error**: Large packages (>10GB) cause memory issues

**Solution**: Process in smaller date ranges:
```python
# Process month by month
for month in range(1, 13):
    start = pd.Timestamp(f"2023-{month:02d}-01")
    end = start + pd.DateOffset(months=1)

    adapter.ingest_to_bundle(
        bundle_name=f"futures-2023-{month:02d}",
        symbols=[],
        start=start,
        end=end,
        frequency="1h"
    )
```

### Issue: Symbol not found

**Error**: Symbol filtering returns empty DataFrame

**Solution**: Check available symbols in metadata:
```python
metadata = adapter._parse_metadata()
print("Available symbols:", metadata.symbols)
```

---

## Performance Tips

1. **Use extracted folders for repeated ingestion**
   ```python
   # Extract once
   import zipfile
   with zipfile.ZipFile("package.zip", "r") as zip_ref:
       zip_ref.extractall("extracted/")

   # Use extracted folder (faster)
   adapter = DatabentoAdapter(DatabentoConfig(data_path="extracted/"))
   ```

2. **Filter by date range early**
   - Large packages (5M+ rows) benefit from narrow date ranges
   - Ingesting 1 month vs 5 years: ~100x faster

3. **Use symbol filtering**
   - If you only need a few symbols, specify them explicitly
   - 1 symbol vs 1000 symbols: ~1000x less data

4. **Monitor decompression**
   - First run decompresses `.zst` file (slow)
   - Subsequent runs use decompressed CSV (fast)
   - Decompressed files are cached in the working directory

---

## Next Steps

- [Data Ingestion Guide](data-ingestion.md) - Overview of all data sources
- [Data Validation Guide](data-validation.md) - Validate ingested data
- [Bundle Management](../api/data/bundle-management.md) - Work with bundles

---

## See Also

- [Databento Documentation](https://databento.com/docs)
- [rustybt Data Sources](data-ingestion.md)
- [Creating Custom Adapters](creating-data-adapters.md)
