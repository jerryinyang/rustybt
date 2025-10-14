# Migrating to Unified Data Architecture

**Last Updated**: 2025-10-08
**Target Audience**: Existing RustyBT users upgrading from pre-Epic-8 versions

## Overview

Epic X1 introduced a unified data architecture that consolidates multiple data APIs into a single, consistent interface. This guide helps you migrate from the old APIs to the new system.

**Deprecation Timeline**:
- **v1.x (Current)**: Old APIs work with deprecation warnings
- **v2.0 (Q2 2026)**: Old APIs removed, must use new system

---

## What Changed?

### Before (Old System)

- **Multiple APIs**: `DataCatalog`, `ParquetMetadataCatalog`, bridge functions
- **Inconsistent interfaces**: Each adapter had different API
- **Manual metadata**: Had to track metadata separately
- **No caching**: Repeated fetches hit external APIs

### After (Unified System)

- **Single API**: `DataSource` interface for all adapters
- **Consistent interface**: Same API across YFinance, CCXT, Polygon, etc.
- **Auto metadata**: `BundleMetadata` populated automatically
- **Smart caching**: Transparent caching with freshness policies

---

## Migration Path

### Step 1: Update Code to Use DataSource

#### Old: Bridge Functions ❌

```python
from rustybt.data.bundles.adapter_bundles import yfinance_profiling_bundle

bundle_path = yfinance_profiling_bundle(
    symbols=["AAPL", "MSFT"],
    start_date="2023-01-01",
    end_date="2023-12-31"
)
```

#### New: DataSource API ✅

```python
from rustybt.data.sources import DataSourceRegistry
import pandas as pd

source = DataSourceRegistry.get_source("yfinance")
await source.ingest_to_bundle(
    bundle_name="my-stocks",
    symbols=["AAPL", "MSFT"],
    start=pd.Timestamp("2023-01-01"),
    end=pd.Timestamp("2023-12-31"),
    frequency="1d"
)
```

---

### Step 2: Migrate Metadata

#### Old: DataCatalog ❌

```python
from rustybt.data.catalog import DataCatalog

catalog = DataCatalog()
catalog.register_bundle("my-stocks", "/path/to/bundle")

# Query metadata
symbols = catalog.get_symbols("my-stocks")
date_range = catalog.get_date_range("my-stocks")
```

#### New: BundleMetadata ✅

```python
from rustybt.data.bundles.metadata import BundleMetadata

# Metadata auto-created during ingestion
metadata = BundleMetadata.load("my-stocks")

# Richer metadata available
print(f"Symbols: {metadata.symbols}")
print(f"Date range: {metadata.start_date} to {metadata.end_date}")
print(f"Quality score: {metadata.quality_score}")
print(f"Missing data: {metadata.missing_data_pct*100:.2f}%")
```

#### Old: ParquetMetadataCatalog ❌

```python
from rustybt.data.polars.metadata_catalog import ParquetMetadataCatalog

pcatalog = ParquetMetadataCatalog()
pcatalog.add_symbol("AAPL", file_path="/path/to/AAPL.parquet", start_date=...)
```

#### New: BundleMetadata (Auto-Populated) ✅

```python
# No manual metadata tracking needed!
# BundleMetadata auto-populated from Parquet file statistics during ingestion

metadata = BundleMetadata.load("my-stocks")
# Automatically includes: row_count, size_bytes, quality metrics
```

---

### Step 3: Update PolarsDataPortal Usage

#### Old: Legacy Readers ❌

```python
from rustybt.data.polars.parquet_daily_bars import PolarsParquetDailyReader
from rustybt.data.polars.data_portal import PolarsDataPortal

reader = PolarsParquetDailyReader("/path/to/bundle")
portal = PolarsDataPortal(daily_reader=reader)
```

#### New: Unified DataSource ✅

```python
from rustybt.data.polars.data_portal import PolarsDataPortal
from rustybt.data.sources import DataSourceRegistry

source = DataSourceRegistry.get_source("yfinance")
portal = PolarsDataPortal(
    data_source=source,
    use_cache=True  # Auto-wraps with CachedDataSource
)
```

---

## Automated Migration Script

We provide a migration script that auto-converts old catalogs to `BundleMetadata`:

### Step 1: Validate Migration (Dry Run)

```bash
python scripts/migrate_catalog_to_unified.py --validate
```

**Output**:
```
✓ Found 3 bundles in old DataCatalog
✓ Found 5 symbols in old ParquetMetadataCatalog
✓ Migration plan:
  - Convert 3 DataCatalog entries to BundleMetadata
  - Merge 5 ParquetMetadataCatalog entries
  - Estimated time: 2 seconds
✓ Validation passed
```

### Step 2: Backup Existing Data

```bash
# Script automatically creates backup at ~/.rustybt/backups/
# Manual backup (optional):
cp -r ~/.rustybt/bundles ~/.rustybt/bundles.backup
cp ~/.rustybt/catalog.db ~/.rustybt/catalog.db.backup
```

### Step 3: Apply Migration

```bash
python scripts/migrate_catalog_to_unified.py --apply
```

**Output**:
```
✓ Backup created: ~/.rustybt/backups/2025-10-08_142530/
✓ Migrating bundle 'my-stocks'...
✓ Migrating bundle 'crypto-hourly'...
✓ Migrating bundle 'forex-pairs'...
✓ Migration complete!
  - 3 bundles migrated
  - 5 symbols merged
  - 0 errors

Next steps:
1. Test your algorithms with new metadata
2. If issues occur, run: python scripts/migrate_catalog_to_unified.py --revert
3. After 7 days, backup will be deleted automatically
```

### Step 4: Verify Migration

```python
from rustybt.data.bundles.metadata import BundleMetadata

# Load migrated metadata
metadata = BundleMetadata.load("my-stocks")

# Verify data integrity
assert metadata.row_count > 0
assert len(metadata.symbols) > 0
assert metadata.quality_score >= 0.0

print("✓ Migration successful!")
```

### Rollback (If Needed)

```bash
# Revert to old system (must do within 7 days)
python scripts/migrate_catalog_to_unified.py --revert

# Or manually restore backup:
cp -r ~/.rustybt/backups/2025-10-08_142530/* ~/.rustybt/
```

---

## Compatibility Layer

For gradual migration, we provide backwards-compatible wrappers:

### Temporary: Keep Using Old APIs

```python
# Old API still works (with deprecation warning)
from rustybt.data.catalog import DataCatalog

catalog = DataCatalog()  # DeprecationWarning emitted
catalog.register_bundle("my-stocks", "/path")

# Under the hood, this now uses BundleMetadata
```

**Warning message**:
```
DeprecationWarning: DataCatalog is deprecated and will be removed in v2.0.
Please migrate to BundleMetadata. See: docs/guides/migrating-to-unified-data.md
```

---

## Common Migration Issues

### Issue 1: Missing API Keys

**Error**: `AuthenticationError: API key required for alpaca source`

**Cause**: New system requires explicit API keys (old bridge functions may have used defaults)

**Solution**: Set environment variables:
```bash
export ALPACA_API_KEY="your_key"
export POLYGON_API_KEY="your_key"
```

Or pass explicitly:
```python
source = DataSourceRegistry.get_source("alpaca", api_key="your_key")
```

---

### Issue 2: Async/Await Required

**Error**: `TypeError: object _Coroutine can't be used in 'await' expression`

**Cause**: New `DataSource.fetch()` and `.ingest_to_bundle()` are async

**Solution**: Add `async`/`await`:
```python
# Old (sync)
df = source.fetch(["AAPL"], start, end, "1d")  # ❌

# New (async)
df = await source.fetch(["AAPL"], start, end, "1d")  # ✅
```

Or run in async context:
```python
import asyncio

async def main():
    df = await source.fetch(["AAPL"], start, end, "1d")

asyncio.run(main())
```

---

### Issue 3: Bundle Not Found

**Error**: `FileNotFoundError: Bundle 'my-stocks' not found`

**Cause**: Old bundle location incompatible with new system

**Solution**: Re-ingest data with new system:
```python
source = DataSourceRegistry.get_source("yfinance")
await source.ingest_to_bundle(
    bundle_name="my-stocks",
    symbols=old_symbols,  # Use symbols from old bundle
    start=old_start,
    end=old_end,
    frequency="1d"
)
```

---

### Issue 4: Performance Regression

**Symptom**: Backtests slower after migration

**Cause**: Caching not enabled by default

**Solution**: Enable caching:
```python
from rustybt.data.sources.cached_source import CachedDataSource

source = DataSourceRegistry.get_source("yfinance")
cached_source = CachedDataSource(adapter=source)

# Or use PolarsDataPortal with use_cache=True
portal = PolarsDataPortal(data_source=source, use_cache=True)
```

---

## Testing After Migration

### 1. Smoke Test

```python
# Verify basic functionality
from rustybt.data.sources import DataSourceRegistry
import pandas as pd

source = DataSourceRegistry.get_source("yfinance")
df = await source.fetch(
    symbols=["AAPL"],
    start=pd.Timestamp("2024-01-01"),
    end=pd.Timestamp("2024-01-31"),
    frequency="1d"
)

assert len(df) > 0
assert "close" in df.columns
print("✓ Basic fetch works")
```

### 2. Backtest Comparison

```python
# Run same backtest with old and new system, compare results
old_results = run_backtest_with_old_api()
new_results = run_backtest_with_new_api()

assert old_results["total_return"] == new_results["total_return"]
print("✓ Results match")
```

### 3. Performance Test

```python
import time

start = time.time()
await source.fetch(["AAPL"], pd.Timestamp("2023-01-01"), pd.Timestamp("2023-12-31"), "1d")
first_fetch = time.time() - start

start = time.time()
await source.fetch(["AAPL"], pd.Timestamp("2023-01-01"), pd.Timestamp("2023-12-31"), "1d")
second_fetch = time.time() - start

assert second_fetch < first_fetch * 0.2  # Cache should be 5x+ faster
print(f"✓ Cache working (first: {first_fetch:.2f}s, second: {second_fetch:.2f}s)")
```

---

## Migration Checklist

- [ ] Read this guide thoroughly
- [ ] Run migration script in `--validate` mode
- [ ] Backup existing data
- [ ] Apply migration with `--apply`
- [ ] Update code to use `DataSource` API
- [ ] Replace `DataCatalog` with `BundleMetadata`
- [ ] Update `PolarsDataPortal` initialization
- [ ] Add `async`/`await` where needed
- [ ] Enable caching for performance
- [ ] Run smoke tests
- [ ] Run full backtest suite
- [ ] Monitor for deprecation warnings
- [ ] Schedule v2.0 upgrade plan (old APIs removed)

---

## Getting Help

**Documentation**:
- [Data Ingestion Guide](data-ingestion.md)
- [Caching Guide](caching-guide.md)
- [API Reference](../api/datasource-api.md)

**Support**:
- GitHub Issues: [rustybt/issues](https://github.com/rustybt/rustybt/issues)
- Discussions: [rustybt/discussions](https://github.com/rustybt/rustybt/discussions)

**Migration Support**:
- Post in GitHub Discussions with tag `migration-help`
- Include error messages and code snippets
- We aim to respond within 24 hours
