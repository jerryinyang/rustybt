# .zipline Folder Organization

**Status**: Documented
**Date**: 2025-10-20
**Related Issues**: #4

## Overview

This document describes the organization of the `.zipline` folder, which contains all user data for RustyBT including bundles, backtests, and configuration files.

## Directory Structure

```
~/.zipline/
├── assets-{version}.db          # Global asset database (shared by traditional bundles)
├── backtests/                   # Backtest outputs and artifacts
│   └── {backtest_id}/          # Individual backtest directory
│       ├── code/               # Captured source code snapshot
│       ├── metadata/           # Backtest metadata JSON
│       └── results/            # Performance metrics and results
├── data/                       # Data storage root
│   └── bundles/                # Bundle storage
│       ├── {bundle_name}/      # Individual bundle directory
│       │   ├── daily_bars/     # Daily OHLCV data (Parquet bundles)
│       │   │   └── year=YYYY/
│       │   │       └── month=MM/
│       │   │           └── data.parquet
│       │   ├── minute_bars/    # Minute OHLCV data (Parquet bundles)
│       │   ├── metadata.db     # Parquet bundle metadata (symbols, quality metrics)
│       │   └── {timestamp}/    # Traditional Bcolz bundles (timestamped)
│       │       ├── adjustments.sqlite
│       │       ├── assets-{version}.sqlite
│       │       ├── daily_equities.bcolz/
│       │       └── minute_equities.bcolz/
│       └── .cache/             # Bundle cache files
└── extension.py                # User extensions (optional)
```

## Bundle Types

### 1. Parquet Bundles (New Format)

**Created by**: `rustybt ingest-unified`

**Structure**:
```
~/.zipline/data/bundles/{bundle_name}/
├── daily_bars/                 # Partitioned Parquet files
│   └── year=YYYY/month=MM/data.parquet
├── minute_bars/                # Minute data (if ingested)
└── metadata.db                 # SQLite database with:
                                # - Symbol mappings (symbol → sid)
                                # - Dataset metadata
                                # - Quality metrics
                                # - Date ranges
```

**Characteristics**:
- No timestamp directories
- Metadata stored in `metadata.db` instead of `assets.db`
- Parquet format for efficient columnar storage
- Year/month partitioning for daily bars
- Supports multiple data sources (yfinance, CCXT, CSV, etc.)

**Example**:
```bash
rustybt ingest-unified yfinance --bundle mag-7 --symbols AAPL,GOOG,AMZN,AVGO,META,MSFT,NVDA,TSLA --start 2000-01-01 --end 2025-01-01 --frequency 1d
```

Creates:
```
~/.zipline/data/bundles/mag-7/
├── daily_bars/
│   ├── year=2000/month=01/data.parquet
│   ├── year=2000/month=02/data.parquet
│   └── ...
└── metadata.db
```

### 2. Traditional Bcolz Bundles (Legacy Format)

**Created by**: `rustybt ingest -b {bundle_name}`

**Structure**:
```
~/.zipline/data/bundles/{bundle_name}/
└── {timestamp}/                # e.g., 2025-10-20T16:30:45.123456
    ├── assets-{version}.sqlite # Asset metadata
    ├── adjustments.sqlite      # Corporate actions
    ├── daily_equities.bcolz/   # Daily OHLCV (Bcolz format)
    └── minute_equities.bcolz/  # Minute OHLCV (Bcolz format)
```

**Characteristics**:
- Timestamp directories allow multiple ingestions
- Bcolz compressed columnar format
- Assets stored in separate SQLite database
- Traditional Zipline format (maintained for compatibility)

## Metadata Database Schemas

### Parquet Bundle metadata.db

**Tables**:

1. **datasets** - Dataset provenance
   ```sql
   CREATE TABLE datasets (
       dataset_id INTEGER PRIMARY KEY,
       source TEXT NOT NULL,
       resolution TEXT NOT NULL,
       schema_version INTEGER NOT NULL,
       created_at INTEGER NOT NULL,
       updated_at INTEGER NOT NULL
   );
   ```

2. **symbols** - Symbol to SID mapping
   ```sql
   CREATE TABLE symbols (
       symbol_id INTEGER PRIMARY KEY,
       dataset_id INTEGER,
       symbol TEXT NOT NULL,
       asset_type TEXT,
       exchange TEXT,
       FOREIGN KEY(dataset_id) REFERENCES datasets(dataset_id)
   );
   ```

3. **date_ranges** - Data availability
   ```sql
   CREATE TABLE date_ranges (
       id INTEGER PRIMARY KEY,
       dataset_id INTEGER,
       start_date INTEGER NOT NULL,
       end_date INTEGER NOT NULL,
       FOREIGN KEY(dataset_id) REFERENCES datasets(dataset_id)
   );
   ```

4. **checksums** - Data integrity
   ```sql
   CREATE TABLE checksums (
       id INTEGER PRIMARY KEY,
       dataset_id INTEGER,
       parquet_path TEXT NOT NULL,
       checksum TEXT NOT NULL,
       last_updated INTEGER NOT NULL,
       FOREIGN KEY(dataset_id) REFERENCES datasets(dataset_id)
   );
   ```

### Global assets-{version}.db

**Used for**: Traditional Bcolz bundles and unified metadata across all bundles

**Tables** (subset):
- `bundle_metadata` - Bundle provenance and quality metrics
- `bundle_symbols` - Symbol tracking across all bundles
- `bundle_cache` - Cache management

## Bundle Management Commands

### List Bundles

```bash
rustybt bundles
```

Output shows both Parquet and Bcolz bundles with their metadata.

### Ingest Data

**Parquet (Recommended)**:
```bash
rustybt ingest-unified {source} --bundle {name} --symbols {list} --start {date} --end {date}
```

**Traditional Bcolz**:
```bash
rustybt ingest -b {bundle_name}
```

### Clean Bundles

```bash
rustybt clean {bundle_name} --keep-last 3
```

## Integration with run_algorithm()

Both bundle types work seamlessly with `run_algorithm()`:

```python
from rustybt.utils.run_algo import run_algorithm
import pandas as pd

result = run_algorithm(
    initialize=initialize,
    handle_data=handle_data,
    bundle="mag-7",  # Works with Parquet bundles now!
    start=pd.Timestamp("2024-01-01"),
    end=pd.Timestamp("2024-12-31"),
    capital_base=10000,
)
```

**How it works**:
1. `bundles.load()` detects bundle type by checking for `metadata.db`
2. For Parquet bundles:
   - Creates `ParquetAssetFinder` (reads from `metadata.db`)
   - Creates `ParquetDailyBarReader` (reads Parquet files)
   - Returns `BundleData` with Parquet-compatible readers
3. For Bcolz bundles:
   - Uses traditional `AssetFinder` and `BcolzDailyBarReader`
   - Returns `BundleData` with Bcolz readers

## Migration Path

### From Bcolz to Parquet

Currently, users can:
1. **Keep existing Bcolz bundles** - They continue to work
2. **Create new Parquet bundles** - Use `ingest-unified` for new data
3. **Gradual transition** - No immediate migration required

Future enhancement (planned):
```bash
rustybt migrate-bundle {bcolz_bundle_name} --to-parquet
```

## Limitations and Future Work

### Current Limitations

1. **Parquet bundles**:
   - ✅ Daily bars: Fully supported
   - ⚠️ Minute bars: Structure exists, reader not yet integrated with `run_algorithm()`
   - ⚠️ Adjustments: Not yet supported (returns `None`)
   - ⚠️ Futures/Options: Not yet supported

2. **Traditional Bcolz bundles**:
   - ✅ Fully supported for all asset types
   - ⚠️ Bcolz dependency unmaintained

### Planned Enhancements

1. **Epic X4**: Full minute bar support for Parquet bundles
2. **Epic X5**: Corporate adjustments integration for Parquet
3. **Epic X6**: Futures and options support for Parquet
4. **Epic X7**: Bundle migration tools (Bcolz → Parquet)
5. **Epic X8**: Bundle versioning and rollback

## Best Practices

1. **Use Parquet for new bundles**: Better performance, modern format, actively maintained
2. **Keep Bcolz for legacy data**: No need to migrate immediately
3. **Organize bundles by purpose**:
   - `yfinance-daily` - General equities
   - `crypto-hourly` - Cryptocurrency data
   - `custom-strategies` - Custom data sources
4. **Regular cleanup**: Use `rustybt clean` to remove old ingestions
5. **Backup metadata**: Critical for Parquet bundles
   ```bash
   cp ~/.zipline/data/bundles/{bundle}/metadata.db ~/backups/
   ```

## Troubleshooting

### Bundle Not Found

```
ValueError: No bundle named 'my-bundle' found
```

**Solution**: List bundles with `rustybt bundles` to see available bundles.

### Bundle Corrupted

```
ValueError: Bundle 'my-bundle' metadata is missing start_date or end_date
```

**Solution**: Re-ingest the bundle with `rustybt ingest-unified` or `rustybt ingest`.

### Wrong Bundle Type

If you try to use a Bcolz bundle command on a Parquet bundle or vice versa, the system will auto-detect and use the correct readers.

## References

- [Data Ingestion Guide](../../guides/data-ingestion.md)
- [Bundle Integration Status](./parquet-bundle-integration-status.md)
- [Active Debug Session](./active-session.md)
