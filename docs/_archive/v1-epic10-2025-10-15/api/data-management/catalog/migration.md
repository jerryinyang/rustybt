# Migration Guide

Guide for migrating data from HDF5/bcolz formats to Parquet.

## Why Migrate?

**Parquet Advantages**:
- 50-80% smaller file sizes
- 5-10x faster read performance
- Industry-standard format
- Better Arrow ecosystem support

## Migration Process

### Step 1: Backup Existing Data

```bash
# Backup current bundles
cp -r ~/.rustybt/data/my_bundle /backup/my_bundle
```

### Step 2: Re-ingest as Parquet

```python
from rustybt.data.bundles import register, ingest
from rustybt.data.adapters import YFinanceAdapter

# Re-register with Parquet format
register(
    bundle_name='my_bundle_parquet',
    adapter=YFinanceAdapter(),
    symbols=['AAPL', 'MSFT'],
    start_date='2020-01-01',
    end_date='2024-01-01',
    storage_format='parquet'  # New format
)

# Ingest
ingest('my_bundle_parquet')
```

### Step 3: Update Strategy Code

```python
# Old
result = run_algorithm(bundle='my_bundle', ...)

# New
result = run_algorithm(bundle='my_bundle_parquet', ...)
```

### Step 4: Verify and Clean

```python
# Verify new bundle
from rustybt.data.bundles import load
bundle_data = load('my_bundle_parquet')

# Clean old bundle
from rustybt.data.bundles import clean
clean('my_bundle', keep_last=0)  # Remove all
```

## Automated Migration

## See Catalog Overview (Coming soon) for more details.
