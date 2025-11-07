# Databento Data Import Guide

**Last Updated**: 2025-11-03

## ⚠️ Breaking Changes (v2.0+)

Starting with **version 2.0** (November 2025), the Databento adapter now uses **instrument IDs** to ensure data correctness:

- **Symbol Format Changed**: Symbols now include instrument IDs (e.g., `AAPL_13` instead of `AAPL`)
- **Why**: Prevents data collisions when symbols are reused (futures contracts, corporate actions, etc.)
- **Multi-File Support**: NASDAQ (XNAS) and other multi-file packages now process **all files** (previously only processed 1 file, losing 99.9% of data)
- **Symbology Parsing**: New feature for resolving symbol ambiguities and instrument lookups

**Migration Required**: Existing bundles created before v2.0 must be regenerated. See [Migration Guide](#migration-from-v1x-to-v2x) below.

**Legacy Mode**: To use old symbol format (not recommended), set `use_instrument_id=False` in config.

---

## Overview

Databento provides high-quality market data for futures, equities, options, and crypto. This guide shows you how to ingest Databento data packages into rustybt bundles.

**Key Features**:
- ✅ Automatic ZIP extraction
- ✅ zstd decompression
- ✅ **Multi-file package support** (e.g., NASDAQ with 1,888 daily files)
- ✅ **Instrument ID tracking** (prevents data collisions)
- ✅ **Symbology parsing** (symbol-to-instrument mapping)
- ✅ Multi-asset packages (ingest hundreds of symbols at once)
- ✅ Symbol filtering
- ✅ Date range filtering
- ✅ Metadata preservation

---

## Quick Start

### Inspect Available Columns First

Before ingesting, check what extra columns are available:

```python
from rustybt.data.adapters.databento_adapter import DatabentoAdapter, DatabentoConfig

adapter = DatabentoAdapter(DatabentoConfig(
    data_path="/path/to/databento-package.zip"
))

columns = adapter.get_available_columns()
print(f"Standard columns: {columns['standard']}")
print(f"Extra columns: {columns['extra']}")
# Output: Extra columns: ['rtype', 'publisher_id', 'instrument_id']
```

### Command Line

```bash
# Ingest entire Databento package (standard OHLCV only)
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
├── symbology.csv          # Symbol-to-instrument_id mapping (v2.0+: automatically parsed)
│   (or symbology.json)    # JSON variant (v2.0+: also supported)
└── *.ohlcv-*.csv.zst     # Compressed OHLCV data (v2.0+: all files processed)
```

**v2.0+ Enhancements**:
- **symbology.csv/json**: Now automatically parsed for symbol lookups
- **Multi-file support**: All `*.ohlcv-*.csv.zst` files are processed and concatenated
- **instrument_id tracking**: Prevents data collisions across files

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

## Preserving Extra Columns (Advanced)

By default, rustybt only ingests standard OHLCV columns. Databento packages often include extra metadata columns like `rtype`, `publisher_id`, `instrument_id`, and for equities: `sector`, `industry`, `market_cap`, etc.

### Step 1: Inspect Available Columns

Always inspect first to see what's available:

```python
from rustybt.data.adapters.databento_adapter import DatabentoAdapter, DatabentoConfig

adapter = DatabentoAdapter(DatabentoConfig(
    data_path="/path/to/databento-package.zip"
))

columns = adapter.get_available_columns()
print(f"Standard: {columns['standard']}")
print(f"Extra: {columns['extra']}")
```

**Example Output (Futures Package):**
```
Standard: ['timestamp', 'symbol', 'open', 'high', 'low', 'close', 'volume']
Extra: ['rtype', 'publisher_id', 'instrument_id']
```

### Step 2: Configure Extra Columns

Specify which extra columns to preserve:

```python
from rustybt.data.adapters.databento_adapter import DatabentoAdapter, DatabentoConfig
import pandas as pd

# Configure adapter with extra columns
config = DatabentoConfig(
    data_path="/path/to/databento-package.zip",
    extra_columns=["rtype", "publisher_id", "instrument_id"]  # Specify columns
)
adapter = DatabentoAdapter(config)

# Ingest with extra columns
adapter.ingest_to_bundle(
    bundle_name="futures-with-metadata",
    symbols=[],
    start=pd.Timestamp("2020-11-01"),
    end=pd.Timestamp("2020-11-30"),
    frequency="1h"
)
```

### Step 3: Access Extra Columns

Extra columns are stored in a separate metadata file for backward compatibility:

```python
import polars as pl

# Read standard OHLCV data
bundle_path = "~/.rustybt/data/bundles/futures-with-metadata"
df_ohlcv = pl.read_parquet(f"{bundle_path}/daily_bars/*.parquet")

# Read extra columns metadata
df_metadata = pl.read_parquet(f"{bundle_path}/metadata_columns.parquet")

# Join on timestamp and symbol
df_complete = df_ohlcv.join(
    df_metadata,
    on=["timestamp", "symbol"],
    how="left"
)

print(df_complete.head())
```

### Storage Structure

When extra columns are specified:

```
~/.rustybt/data/bundles/futures-with-metadata/
├── daily_bars/
│   └── data.parquet           # Standard OHLCV only
├── metadata_columns.parquet   # Extra columns (NEW)
└── metadata.db                # Bundle metadata
```

**Benefits:**
- ✅ **Backward compatible**: Existing code works unchanged
- ✅ **Optional**: Only created when extra columns specified
- ✅ **Efficient**: Separate storage allows independent querying
- ✅ **Flexible**: Easy to join when needed

### Example: Filter by Record Type

```python
# Ingest with rtype column
config = DatabentoConfig(
    data_path="/path/to/databento.zip",
    extra_columns=["rtype"]
)
adapter = DatabentoAdapter(config)

# Fetch data
df = await adapter.fetch(
    symbols=[],
    start=pd.Timestamp("2020-11-01"),
    end=pd.Timestamp("2020-11-30"),
    frequency="1h"
)

# Filter by record type
df_ohlcv_only = df.filter(pl.col("rtype") == 34)  # OHLCV records
print(f"OHLCV records: {len(df_ohlcv_only)}")
```

### Common Extra Columns

**Futures (GLBX.MDP3 example):**
- `rtype`: Record type (34 = OHLCV)
- `publisher_id`: Data publisher identifier
- `instrument_id`: Databento instrument ID

**Equities (if available):**
- `sector`: Industry sector
- `industry`: Specific industry
- `market_cap`: Market capitalization category
- `exchange`: Listing exchange

**Note**: Available columns vary by Databento dataset and schema. Always use `get_available_columns()` first.

---

## Instrument ID Tracking (v2.0+)

### Why Instrument IDs Matter

Databento assigns unique `instrument_id` values to differentiate between:
- **Futures contracts** with different expirations (e.g., ESH1, ESM1, ESZ1 all use symbol "ES")
- **Corporate actions** (stocks that changed tickers due to mergers/splits)
- **Symbol reuse** (when a symbol gets reassigned to a different instrument over time)

**Without instrument_id**: Data from different instruments gets incorrectly merged, causing data corruption.

### Default Behavior (v2.0+)

By default, rustybt now creates composite symbols using `instrument_id`:

```python
from rustybt.data.adapters.databento_adapter import DatabentoAdapter, DatabentoConfig

config = DatabentoConfig(
    data_path="/path/to/databento-package.zip",
    use_instrument_id=True  # DEFAULT in v2.0+
)
adapter = DatabentoAdapter(config)
```

**Symbol Format**: `{original_symbol}_{instrument_id}`
- Example: `AAPL_13`, `ESH1_12345`, `NQZ0_67890`

### Querying with Instrument IDs

```python
# Fetch specific instrument
df = await adapter.fetch(
    symbols=["AAPL_13"],  # Use composite symbol format
    start=pd.Timestamp("2023-01-01"),
    end=pd.Timestamp("2023-12-31"),
    frequency="1d"
)
```

### Preserving Original Symbols

The original symbol and instrument_id are preserved as metadata:

```python
config = DatabentoConfig(
    data_path="/path/to/package.zip",
    extra_columns=["instrument_id", "original_symbol"]  # Preserve as metadata
)
adapter = DatabentoAdapter(config)

adapter.ingest_to_bundle(
    bundle_name="with-original-symbols",
    symbols=[],
    start=pd.Timestamp("2023-01-01"),
    end=pd.Timestamp("2023-12-31"),
    frequency="1h"
)
```

**Access metadata**:
```python
import polars as pl

# Read OHLCV data (uses composite symbols)
df_ohlcv = pl.read_parquet("~/.rustybt/data/bundles/with-original-symbols/minute_bars/*.parquet")

# Read metadata to see original symbols
df_metadata = pl.read_parquet("~/.rustybt/data/bundles/with-original-symbols/metadata_columns.parquet")

# Join to get original symbols
df_complete = df_ohlcv.join(df_metadata, on=["timestamp", "symbol"], how="left")
print(df_complete.select(["timestamp", "symbol", "original_symbol", "instrument_id", "close"]))

# Output:
# timestamp            symbol        original_symbol  instrument_id  close
# 2023-01-01 00:00:00  ESH1_12345   ESH1            12345          4000.25
```

### Legacy Mode (Not Recommended)

To use the old symbol format without instrument IDs:

```python
config = DatabentoConfig(
    data_path="/path/to/package.zip",
    use_instrument_id=False  # Legacy mode (NOT RECOMMENDED)
)
```

**⚠️ Warning**: This may cause data collisions for futures and symbols that get reused.

---

## Symbology Parsing (v2.0+)

Databento packages include a `symbology.csv` (or `symbology.json`) file that maps symbols to instrument IDs over time.

### Automatic Parsing

The adapter automatically parses symbology files:

```python
adapter = DatabentoAdapter(DatabentoConfig(
    data_path="/path/to/package.zip"
))

# Symbology is automatically parsed during fetch/ingest
```

### Symbol Lookups

```python
# Find all instruments for a given symbol
instruments = adapter.get_instruments_for_symbol("ES")
print(f"Found {len(instruments)} instruments for 'ES'")
# Example: [{'instrument_id': 12345, 'date_range': '2020-01-01 to 2020-03-31'}, ...]

# Find symbol for a specific instrument
symbol_info = adapter.get_symbol_for_instrument(12345)
print(f"Instrument 12345: {symbol_info['symbol']}")
```

### Symbology Validation

Validate that symbology covers all OHLCV data:

```python
# During ingestion, symbology is automatically validated
# Warnings are logged if instruments are missing from symbology
```

**Performance**: Symbology files with 21M+ rows parse in ~3 seconds using Polars' optimized JSON/CSV readers.

---

## Multi-File Package Support (v2.0+)

### Background

Some Databento packages contain multiple OHLCV files instead of a single file:
- **NASDAQ (XNAS)**: 1,888 daily files (one per trading day)
- **Futures (GLBX)**: Often split by date ranges
- **Historical data**: Large date ranges split into manageable chunks

**v1.x Limitation**: Only the first file was processed, resulting in 99.9% data loss for multi-file packages.

**v2.0+ Fix**: All OHLCV files are now discovered and concatenated automatically.

### Automatic Multi-File Handling

```python
# Works the same for single-file and multi-file packages
adapter = DatabentoAdapter(DatabentoConfig(
    data_path="/path/to/XNAS-package.zip"  # 1,888 files
))

adapter.ingest_to_bundle(
    bundle_name="xnas-data",
    symbols=[],  # All symbols
    start=pd.Timestamp("2018-05-01"),
    end=pd.Timestamp("2023-10-18"),
    frequency="1d"
)

# All 1,888 files are automatically processed and concatenated
```

### Package Metadata

Multi-file packages include `split_duration` metadata:

```python
metadata = adapter._parse_metadata()
print(f"Split duration: {metadata.split_duration}")  # e.g., "day"
print(f"Split symbols: {metadata.split_symbols}")    # e.g., False
```

---

## Migration from v1.x to v2.x

### Breaking Changes Summary

| Change | v1.x | v2.x |
|--------|------|------|
| Symbol format | `AAPL` | `AAPL_13` (with instrument_id) |
| Multi-file packages | Only first file | All files processed |
| Symbology | Not parsed | Automatically parsed |
| instrument_id | Ignored | Used by default |

### Migration Steps

**Step 1: Delete Old Bundles**

```bash
# List existing bundles
rustybt bundles --list

# Remove old Databento bundles
rm -rf ~/.rustybt/data/bundles/old-databento-bundle
```

**Step 2: Re-ingest with v2.x**

```python
from rustybt.data.adapters.databento_adapter import DatabentoAdapter, DatabentoConfig

# v2.x automatically uses instrument IDs
adapter = DatabentoAdapter(DatabentoConfig(
    data_path="/path/to/databento-package.zip"
))

adapter.ingest_to_bundle(
    bundle_name="new-databento-bundle",
    symbols=[],
    start=pd.Timestamp("2023-01-01"),
    end=pd.Timestamp("2023-12-31"),
    frequency="1h"
)
```

**Step 3: Update Queries**

```python
# OLD (v1.x): Query by symbol alone
df = bundle.get_pricing(symbols=["AAPL"], ...)  # ❌ Won't work in v2.x

# NEW (v2.x): Query by composite symbol
df = bundle.get_pricing(symbols=["AAPL_13"], ...)  # ✅ Works

# OR: Use original_symbol metadata to find composite symbols
metadata = pl.read_parquet("~/.rustybt/data/bundles/new-databento-bundle/metadata_columns.parquet")
aapl_instruments = metadata.filter(pl.col("original_symbol") == "AAPL")["symbol"].unique().to_list()
print(f"AAPL instruments: {aapl_instruments}")  # ['AAPL_13', 'AAPL_14', ...]
```

### Backward Compatibility Option

If you must use the old format (not recommended):

```python
config = DatabentoConfig(
    data_path="/path/to/package.zip",
    use_instrument_id=False  # Forces v1.x behavior
)
```

**⚠️ Risks**:
- Data collisions for futures contracts
- Incorrect merging of different instruments
- Symbol reuse issues

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
| `symbol` | str | Composite symbol identifier (v2.0+: `SYMBOL_INSTRUMENTID`, e.g., `AAPL_13`) |
| `open` | float64 | Opening price |
| `high` | float64 | High price |
| `low` | float64 | Low price |
| `close` | float64 | Closing price |
| `volume` | int64 | Trading volume |

**v2.0+ Symbol Format**: Symbols include instrument_id to prevent data collisions (e.g., `ESH1_12345` instead of just `ESH1`).

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
- [Bundle System](../api/data-management/catalog/bundle-system.md) - Work with bundles

---

## See Also

- [Databento Documentation](https://databento.com/docs)
- [rustybt Data Sources](data-ingestion.md)
- [Creating Custom Adapters](creating-data-adapters.md)
