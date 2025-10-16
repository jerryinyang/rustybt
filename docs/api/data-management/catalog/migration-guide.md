# Bundle Migration Guide

## Overview

This guide covers migrating legacy data bundles from HDF5 or bcolz formats to the modern Parquet-based storage with Decimal precision. The migration process preserves data integrity while providing improved performance, compression, and financial precision.

## Why Migrate?

### Benefits of Parquet Format

**Financial Precision**:
- Decimal(18, 8) precision for all price data
- No floating-point arithmetic errors
- Guaranteed accuracy for financial calculations

**Performance**:
- Columnar storage enables faster queries
- Better compression ratios (typically 5-10x smaller)
- Lazy loading with predicate pushdown
- Efficient memory usage with memory-mapped files

**Compatibility**:
- Standard format supported by Apache Arrow ecosystem
- Cross-language support (Python, Rust, R, etc.)
- Cloud-native storage integration

**Maintenance**:
- Self-describing schema with embedded metadata
- No index rebuilding required
- Atomic writes prevent corruption

### Legacy Format Limitations

**HDF5 Issues**:
- Float64 precision leads to rounding errors
- Requires full file locks for writes
- Limited compression options
- Python-centric tooling

**Bcolz Issues**:
- Deprecated library with limited maintenance
- Fixed chunk sizes limit flexibility
- No native Decimal support
- Requires index rebuilding

## Migration Architecture

### Migration Process Flow

```
┌─────────────────┐
│  Legacy Bundle  │
│  (HDF5/bcolz)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Read Legacy    │
│  (Pandas)       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Convert to     │
│  Polars+Decimal │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Write Parquet  │
│  (compressed)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Validate Data  │
│  Integrity      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Register in    │
│  Metadata       │
└─────────────────┘
```

### Components

**BundleMigrator**: Main migration class handling the workflow
- Reads legacy formats (HDF5, bcolz)
- Converts to Polars DataFrames with Decimal columns
- Writes Parquet with compression
- Validates data integrity
- Registers in metadata catalog

**ParquetWriter**: Handles Parquet writes with partitioning
- Year/month partitioning for daily data
- Compression (zstd, snappy, lz4)
- Schema validation
- Atomic writes

**BundleMetadata**: Tracks provenance and quality
- Source information
- Quality metrics
- Checksums for validation
- Symbol tracking

## Migration Workflow

### Step 1: Prepare Environment

First, ensure you have the required dependencies:

```python
# Required packages
import rustybt
from rustybt.data.bundles.migration import BundleMigrator, migrate_bundle
from pathlib import Path

# Optional: Install bcolz if migrating from bcolz
# pip install bcolz
```

### Step 2: Locate Legacy Bundle

Identify the bundle directory containing your legacy data:

```python
# Example bundle structure (HDF5)
# data/bundles/quandl/
#   ├── daily_bars.h5
#   ├── metadata.json
#   └── adjustments.h5

# Example bundle structure (bcolz)
# data/bundles/quantopian-quandl/
#   ├── daily_equities.bcolz/
#   ├── minute_equities.bcolz/
#   ├── adjustments.sqlite
#   └── metadata.json

bundle_path = "data/bundles/quandl"
```

### Step 3: Initialize Migrator

Create a BundleMigrator instance:

```python
from rustybt.data.bundles.migration import BundleMigrator

# Initialize migrator
migrator = BundleMigrator(bundle_path)
```

### Step 4: Migrate Daily Bars

Migrate daily bar data with validation:

```python
# Migrate daily bars from HDF5
daily_stats = migrator.migrate_daily_bars(
    source_format="hdf5",
    compression="zstd",  # Best compression ratio
    validate=True,       # Validate data integrity
    batch_size=100       # Process 100 assets at a time
)

print(f"Migrated {daily_stats['row_count']} rows")
print(f"Duration: {daily_stats['duration_seconds']:.2f} seconds")
```

**Compression Options**:
- `"zstd"`: Best compression ratio, moderate speed (recommended)
- `"snappy"`: Fastest, moderate compression
- `"lz4"`: Fast, good compression
- `None`: No compression (not recommended)

### Step 5: Migrate Minute Bars (Optional)

If you have minute bar data:

```python
# Migrate minute bars from bcolz
minute_stats = migrator.migrate_minute_bars(
    source_format="bcolz",
    compression="zstd",
    validate=True,
    start_date=None,  # Optional: filter by date range
    end_date=None
)

print(f"Migrated {minute_stats['row_count']} rows")
```

**Date Range Filtering**:
```python
from datetime import date

# Migrate only recent data
minute_stats = migrator.migrate_minute_bars(
    source_format="bcolz",
    start_date=date(2023, 1, 1),
    end_date=date(2023, 12, 31),
    validate=True
)
```

### Step 6: Verify Migration

After migration, verify the results:

```python
from rustybt.data.bundles.metadata import BundleMetadata

# Query metadata for migrated bundle
metadata = BundleMetadata.get(f"migrated-{bundle_path}")
if metadata:
    print(f"Row count: {metadata.row_count}")
    print(f"Date range: {metadata.start_date} to {metadata.end_date}")
    print(f"Validation passed: {metadata.validation_passed}")
    print(f"Checksum: {metadata.checksum}")
```

## Convenience Function

For simple migrations, use the `migrate_bundle()` convenience function:

```python
from rustybt.data.bundles.migration import migrate_bundle

# Migrate entire bundle in one call
stats = migrate_bundle(
    bundle_path="data/bundles/quandl",
    source_format="hdf5",
    compression="zstd",
    migrate_daily=True,   # Migrate daily bars
    migrate_minute=False, # Skip minute bars
    validate=True
)

# Access results
print(f"Daily bars: {stats['daily']['row_count']} rows")
if 'minute' in stats:
    print(f"Minute bars: {stats['minute']['row_count']} rows")
```

## Best Practices

### Before Migration

**1. Backup Legacy Data**

Always create a backup before migration:

```bash
# Backup bundle directory
cp -r data/bundles/quandl data/bundles/quandl.backup
```

**2. Check Available Disk Space**

Parquet files with compression are typically smaller, but you need space for both formats during migration:

```python
import shutil

# Check available space
stats = shutil.disk_usage("/")
available_gb = stats.free / (1024 ** 3)
print(f"Available space: {available_gb:.2f} GB")
```

**3. Verify Source Data Integrity**

Ensure your legacy data is not corrupted:

```python
import pandas as pd

# Test read HDF5
try:
    df = pd.read_hdf("data/bundles/quandl/daily_bars.h5")
    print(f"Source data OK: {len(df)} rows")
except Exception as e:
    print(f"Source data error: {e}")
```

### During Migration

**1. Use Validation**

Always enable validation for production migrations:

```python
stats = migrator.migrate_daily_bars(
    source_format="hdf5",
    validate=True  # IMPORTANT: Always validate
)
```

**2. Monitor Progress**

For large bundles, monitor progress with logging:

```python
import structlog

# Enable debug logging
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO)
)

# Now migration will log progress
migrator.migrate_daily_bars(source_format="hdf5")
```

**3. Handle Errors Gracefully**

Wrap migration in try-except for error handling:

```python
from rustybt.data.bundles.migration import MigrationError

try:
    stats = migrator.migrate_daily_bars("hdf5")
    print("Migration successful")
except MigrationError as e:
    print(f"Migration failed: {e}")
    # Restore from backup if needed
```

### After Migration

**1. Verify Data Integrity**

Spot-check migrated data:

```python
import polars as pl

# Read migrated Parquet
df = pl.read_parquet("data/bundles/quandl/daily_bars")

# Verify schema
assert df.schema["open"] == pl.Decimal(18, 8), "Incorrect precision"
assert df.schema["date"] == pl.Date, "Incorrect date type"

# Verify data
print(f"Total rows: {len(df)}")
print(f"Date range: {df['date'].min()} to {df['date'].max()}")
print(df.head())
```

**2. Update Bundle Registration**

Re-register the bundle if needed:

```python
from rustybt.data.bundles import register, unregister

# Unregister old bundle
try:
    unregister("quandl")
except:
    pass

# Register new Parquet bundle
from rustybt.data.bundles.csvdir import csvdir_equities

register(
    "quandl-parquet",
    csvdir_equities(
        ["daily"],
        "data/bundles/quandl"
    )
)
```

**3. Clean Up Legacy Data**

After verifying the migration, optionally remove legacy files:

```python
import os
from pathlib import Path

# ONLY after thorough verification
legacy_file = Path("data/bundles/quandl/daily_bars.h5")
if legacy_file.exists():
    # Move to archive instead of deleting
    archive_dir = Path("data/bundles/archive")
    archive_dir.mkdir(exist_ok=True)
    legacy_file.rename(archive_dir / legacy_file.name)
```

## Common Issues & Troubleshooting

### Issue: HDF5 File Not Found

**Error**: `MigrationError: HDF5 daily bars file not found`

**Solution**: Verify the file path and structure:

```python
from pathlib import Path

bundle_path = Path("data/bundles/quandl")
daily_bars = bundle_path / "daily_bars.h5"

if not daily_bars.exists():
    print(f"File not found: {daily_bars}")
    print("Available files:")
    for f in bundle_path.glob("*.h5"):
        print(f"  - {f.name}")
```

### Issue: Bcolz Not Installed

**Error**: `MigrationError: bcolz package not installed`

**Solution**: Install bcolz (note: requires Python 3.9 or earlier):

```bash
pip install bcolz
```

If bcolz is not compatible with your Python version, convert the data manually:

```python
# Alternative: Use legacy Python environment to export CSV
# Then use CSV adapter to ingest

import pandas as pd
import bcolz

# In legacy environment
ctable = bcolz.open("data/bundles/quandl/daily_equities.bcolz")
df = ctable.todataframe()
df.to_csv("exported_data.csv", index=False)

# Then use CSV adapter in new environment
from rustybt.data.adapters.csv_adapter import CSVAdapter
adapter = CSVAdapter(file_path="exported_data.csv")
```

### Issue: Schema Validation Failure

**Error**: `ValueError: Schema validation failed`

**Solution**: Check column names and types:

```python
import polars as pl

# Inspect DataFrame schema
df = pl.read_parquet("output.parquet")
print(df.schema)

# Expected schema for daily bars
from rustybt.data.polars.parquet_schema import DAILY_BARS_SCHEMA
print(DAILY_BARS_SCHEMA)
```

### Issue: Memory Issues with Large Bundles

**Error**: `MemoryError: Unable to allocate array`

**Solution**: Use batch processing:

```python
# Migrate in smaller batches
migrator.migrate_daily_bars(
    source_format="hdf5",
    batch_size=50,  # Reduce batch size
    validate=True
)
```

Or process date ranges separately:

```python
from datetime import date

# Migrate year by year
for year in range(2020, 2024):
    stats = migrator.migrate_minute_bars(
        source_format="bcolz",
        start_date=date(year, 1, 1),
        end_date=date(year, 12, 31),
        validate=True
    )
    print(f"Migrated {year}: {stats['row_count']} rows")
```

### Issue: Validation Fails

**Error**: `MigrationError: Value mismatch at index X`

**Solution**: Check for known data quality issues:

```python
# Some legacy data may have precision issues
# Review the validation tolerance
# Default tolerance: 1e-6

# If legacy data has known issues, disable validation
stats = migrator.migrate_daily_bars(
    source_format="hdf5",
    validate=False  # Skip validation
)

# Then manually verify critical data points
```

## Complete Migration Example

Here's a complete example migrating a Quandl bundle:

```python
from rustybt.data.bundles.migration import BundleMigrator, MigrationError
import structlog
from pathlib import Path

# Configure logging
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO)
)

# Migration configuration
BUNDLE_PATH = "data/bundles/quandl"
SOURCE_FORMAT = "hdf5"
COMPRESSION = "zstd"

def migrate_quandl_bundle():
    """Migrate Quandl bundle from HDF5 to Parquet."""

    # Validate bundle exists
    bundle_path = Path(BUNDLE_PATH)
    if not bundle_path.exists():
        raise ValueError(f"Bundle not found: {BUNDLE_PATH}")

    # Check disk space
    import shutil
    stats = shutil.disk_usage(bundle_path)
    if stats.free < 10 * (1024 ** 3):  # 10 GB minimum
        print("WARNING: Low disk space")

    # Initialize migrator
    migrator = BundleMigrator(BUNDLE_PATH)

    # Migrate daily bars
    print("Migrating daily bars...")
    try:
        daily_stats = migrator.migrate_daily_bars(
            source_format=SOURCE_FORMAT,
            compression=COMPRESSION,
            validate=True,
            batch_size=100
        )
        print(f"✓ Daily bars migrated: {daily_stats['row_count']} rows")
        print(f"  Output: {daily_stats['output_path']}")
        print(f"  Duration: {daily_stats['duration_seconds']:.2f}s")
        print(f"  Compression: {COMPRESSION}")
    except MigrationError as e:
        print(f"✗ Daily bars migration failed: {e}")
        return False

    # Migrate minute bars (if exists)
    minute_path = bundle_path / "minute_bars.h5"
    if minute_path.exists():
        print("\nMigrating minute bars...")
        try:
            minute_stats = migrator.migrate_minute_bars(
                source_format=SOURCE_FORMAT,
                compression=COMPRESSION,
                validate=True
            )
            print(f"✓ Minute bars migrated: {minute_stats['row_count']} rows")
            print(f"  Duration: {minute_stats['duration_seconds']:.2f}s")
        except MigrationError as e:
            print(f"✗ Minute bars migration failed: {e}")

    # Verify results
    print("\nVerifying migration...")
    from rustybt.data.bundles.metadata import BundleMetadata

    bundle_name = f"migrated-{BUNDLE_PATH}"
    metadata = BundleMetadata.get(bundle_name)
    if metadata:
        print(f"✓ Metadata registered")
        print(f"  Row count: {metadata.row_count}")
        print(f"  Validation: {'PASSED' if metadata.validation_passed else 'FAILED'}")

    print("\n✓ Migration complete!")
    return True

if __name__ == "__main__":
    success = migrate_quandl_bundle()
    exit(0 if success else 1)
```

## Migration Checklist

Use this checklist when performing migrations:

**Pre-Migration**:
- [ ] Backup source bundle directory
- [ ] Verify source data integrity
- [ ] Check available disk space (at least 2x source size)
- [ ] Install required dependencies (bcolz if needed)
- [ ] Review bundle structure and file locations

**During Migration**:
- [ ] Initialize BundleMigrator
- [ ] Migrate daily bars with validation enabled
- [ ] Migrate minute bars if present
- [ ] Monitor logs for errors or warnings
- [ ] Verify migration statistics (row counts, duration)

**Post-Migration**:
- [ ] Verify Parquet files created successfully
- [ ] Check BundleMetadata registration
- [ ] Spot-check migrated data for accuracy
- [ ] Compare file sizes (Parquet should be smaller)
- [ ] Test reading migrated data in backtest
- [ ] Update bundle registration if needed
- [ ] Archive or remove legacy files (after verification)
- [ ] Document migration in project changelog

## API Reference Summary

### BundleMigrator

Main migration class for converting bundles.

```python
from rustybt.data.bundles.migration import BundleMigrator

migrator = BundleMigrator(bundle_path: str)
```

**Methods**:
- `migrate_daily_bars(source_format, compression, validate, batch_size)` → dict
- `migrate_minute_bars(source_format, compression, validate, start_date, end_date)` → dict

### migrate_bundle()

Convenience function for simple migrations.

```python
from rustybt.data.bundles.migration import migrate_bundle

stats = migrate_bundle(
    bundle_path: str,
    source_format: Literal["hdf5", "bcolz"],
    compression: Literal["snappy", "zstd", "lz4"] | None = "zstd",
    migrate_daily: bool = True,
    migrate_minute: bool = False,
    validate: bool = True
) → dict
```

### MigrationError

Exception raised when migration fails.

```python
from rustybt.data.bundles.migration import MigrationError

try:
    migrator.migrate_daily_bars("hdf5")
except MigrationError as e:
    print(f"Migration failed: {e}")
```

## Related Documentation

- [Catalog System Overview](README.md)
- [Bundle System](bundle-system.md)
- [Metadata Tracking](metadata-tracking.md)
- [Catalog API](catalog-api.md)

## Next Steps

After migration, consider:

1. **Performance Testing**: Benchmark query performance with new Parquet format
2. **Monitoring**: Set up monitoring for bundle freshness and quality
3. **Automation**: Create automated migration scripts for new bundles
4. **Documentation**: Document your migration process for team reference
