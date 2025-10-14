# Data Catalog Overview

The Data Catalog system provides centralized management of data bundles, metadata tracking, and data versioning for RustyBT.

## Overview

The catalog system consists of three main components:

1. **Bundle Registry**: Manages data bundle registration and discovery
2. **Metadata Tracking**: Tracks data quality, lineage, and versioning
3. **Bundle Storage**: Handles physical storage of market data

## Architecture

```
┌──────────────────────────────────────────────────┐
│              Trading Strategy                    │
└─────────────────┬────────────────────────────────┘
                  │
          ┌───────▼────────┐
          │  Data Portal   │
          └───────┬────────┘
                  │
          ┌───────▼────────┐
          │  Data Catalog  │
          │                │
          │  ┌──────────┐  │
          │  │ Registry │  │
          │  ├──────────┤  │
          │  │ Metadata │  │
          │  ├──────────┤  │
          │  │ Storage  │  │
          │  └──────────┘  │
          └────────────────┘
                  │
    ┌─────────────┼─────────────┐
    │             │             │
┌───▼───┐    ┌────▼────┐   ┌───▼────┐
│Parquet│    │  HDF5   │   │ bcolz  │
└───────┘    └─────────┘   └────────┘
```

## Quick Start

### Registering a Bundle

```python
from rustybt.data.bundles import register
from rustybt.data.adapters import YFinanceAdapter
import pandas as pd

# Register new bundle
register(
    bundle_name='my_stocks',
    adapter=YFinanceAdapter(),
    symbols=['AAPL', 'MSFT', 'GOOGL'],
    start_date='2020-01-01',
    end_date='2024-01-01',
    calendar_name='NYSE'
)
```

### Ingesting Data

```python
from rustybt.data.bundles import ingest

# Ingest registered bundle
ingest('my_stocks', show_progress=True)
```

### Using Bundle in Backtest

```python
from rustybt import run_algorithm

result = run_algorithm(
    start=pd.Timestamp('2023-01-01'),
    end=pd.Timestamp('2023-12-31'),
    bundle='my_stocks',  # Use ingested bundle
    initialize=initialize,
    handle_data=handle_data,
    capital_base=100000
)
```

## Key Concepts

### Bundles

A **bundle** is a named collection of market data stored in an optimized format:

```python
# Bundle structure:
my_bundle/
├── 2024-01-15T10;30;00.000000/     # Ingestion timestamp
│   ├── assets-8.sqlite              # Asset metadata
│   ├── daily_equities.parquet/      # Daily OHLCV data
│   ├── minute_equities.parquet/     # Minute OHLCV data (if applicable)
│   └── adjustments.sqlite           # Corporate actions
└── .cache/                          # Cache directory
```

### Ingestion

**Ingestion** is the process of:
1. Fetching data from source (adapter)
2. Validating data quality
3. Writing to optimized storage format
4. Recording metadata

```python
# Manual ingestion with options
from rustybt.data.bundles import ingest

ingest(
    'my_bundle',
    show_progress=True,
    keep_last=5,  # Keep last 5 ingestions
)
```

### Metadata

**Metadata** tracks information about bundles:
- Source information (adapter, API version)
- Data quality metrics (row count, gaps, outliers)
- Temporal coverage (start/end dates)
- Checksums and versioning
- Ingestion history

```python
from rustybt.data.bundles.metadata import BundleMetadata

# Query metadata
metadata = BundleMetadata.get('my_bundle')
print(f"Rows: {metadata['row_count']}")
print(f"Coverage: {metadata['start_date']} to {metadata['end_date']}")
print(f"Quality: {'PASSED' if metadata['validation_passed'] else 'FAILED'}")
```

## Bundle Registry

### Listing Available Bundles

```python
from rustybt.data.bundles import bundles

# List all registered bundles
available_bundles = bundles.keys()
print("Available bundles:", list(available_bundles))

# Get bundle details
bundle_info = bundles['my_bundle']
print(f"Calendar: {bundle_info.calendar_name}")
print(f"Start: {bundle_info.start_session}")
print(f"End: {bundle_info.end_session}")
```

### Unregistering Bundles

```python
from rustybt.data.bundles import unregister

unregister('old_bundle')
```

### Bundle Discovery

```python
from rustybt.data.bundles import ingestions_for_bundle

# List ingestion timestamps for a bundle
ingestions = ingestions_for_bundle('my_bundle')
print(f"Found {len(ingestions)} ingestions")
for ts in ingestions:
    print(f"  - {ts}")
```

## Data Formats

### Parquet (Recommended)

```python
from rustybt.data.bundles import register
from rustybt.data.adapters import CCXTAdapter

register(
    bundle_name='crypto_parquet',
    adapter=CCXTAdapter(exchange_id='binance'),
    symbols=['BTC/USDT', 'ETH/USDT'],
    start_date='2024-01-01',
    end_date='2024-01-31',
    storage_format='parquet'  # Default
)
```

**Advantages**:
- Fast read/write performance
- Excellent compression (50-80% smaller than HDF5)
- Industry-standard format
- Arrow ecosystem compatibility

### HDF5 (Legacy Support)

```python
register(
    bundle_name='stocks_hdf5',
    adapter=YFinanceAdapter(),
    symbols=['AAPL', 'MSFT'],
    start_date='2023-01-01',
    end_date='2023-12-31',
    storage_format='hdf5'
)
```

**Use Cases**:
- Backward compatibility with Zipline
- Existing HDF5 workflows
- Transitioning to Parquet

### bcolz (Deprecated)

```python
register(
    bundle_name='legacy_bcolz',
    storage_format='bcolz'  # Not recommended for new projects
)
```

**Status**: Maintained for backward compatibility, migrate to Parquet.

## Metadata Management

### Recording Custom Metadata

```python
from rustybt.data.bundles.metadata import BundleMetadata

BundleMetadata.update(
    'my_bundle',
    source_type='yfinance',
    source_url='https://finance.yahoo.com',
    data_version='1.0',
    custom_field='custom_value'
)
```

### Querying Metadata

```python
# Get all metadata
metadata = BundleMetadata.get('my_bundle')

# Check specific fields
if metadata and metadata.get('validation_passed'):
    print("Data quality checks passed")
else:
    print("Warning: Quality issues detected")
    print(f"OHLCV violations: {metadata.get('ohlcv_violations', 0)}")
    print(f"Missing days: {metadata.get('missing_days_count', 0)}")
```

### Quality Metrics

```python
# Get quality report
from rustybt.data.bundles.metadata import get_quality_report

report = get_quality_report('my_bundle')
print(f"""
Bundle: {report['bundle_name']}
Rows: {report['row_count']:,}
Coverage: {report['start_date']} to {report['end_date']}
Missing Days: {report['missing_days_count']}
OHLCV Violations: {report['ohlcv_violations']}
Outliers: {report['outlier_count']}
Status: {'✓ PASSED' if report['validation_passed'] else '✗ FAILED'}
""")
```

## Bundle Management Commands

### CLI Commands

```bash
# List all bundles
rustybt bundles

# Ingest specific bundle
rustybt ingest my_bundle

# Ingest with options
rustybt ingest my_bundle --show-progress --keep-last 3

# Clean old ingestions
rustybt clean my_bundle --keep 2

# Bundle info
rustybt bundle-info my_bundle
```

### Programmatic Management

```python
from rustybt.data.bundles import (
    ingest,
    clean,
    load,
    bundles
)

# Ingest bundle
ingest('my_bundle', show_progress=True)

# Clean old ingestions (keep last 3)
clean('my_bundle', keep_last=3)

# Load bundle data
bundle_data = load('my_bundle')
print(f"Assets: {len(bundle_data.asset_finder.retrieve_all())}")
```

## Performance Considerations

### Ingestion Performance

```python
# Parallel ingestion for multiple symbols
register(
    bundle_name='large_universe',
    adapter=YFinanceAdapter(),
    symbols=list_of_500_symbols,
    start_date='2020-01-01',
    end_date='2024-01-01',
    n_workers=8  # Parallel workers for data fetching
)

ingest('large_universe', show_progress=True)
```

### Storage Optimization

```python
# Use compression for Parquet
register(
    bundle_name='compressed_data',
    adapter=CCXTAdapter(exchange_id='binance'),
    symbols=['BTC/USDT'],
    start_date='2020-01-01',
    end_date='2024-01-01',
    compression='snappy'  # Options: 'snappy', 'gzip', 'zstd', 'lz4'
)
```

### Caching Strategy

```python
from rustybt.data.polars.cache_manager import CacheManager

# Configure bundle cache
cache = CacheManager(
    max_memory_mb=2048,  # 2GB memory cache
    disk_cache_path='/path/to/bundle/.cache'
)

# Cache is used automatically by bundle readers
```

## Best Practices

### 1. Bundle Naming Convention

```python
# Good naming conventions:
'stocks_us_daily_2020_2024'        # Clear time range
'crypto_binance_btc_eth_hourly'    # Exchange and resolution
'sp500_yfinance_daily_v2'          # Version tracking

# Avoid:
'data'                              # Too generic
'bundle1'                           # Not descriptive
'my_bundle'                         # Not informative
```

### 2. Version Management

```python
# Track data versions
register(
    bundle_name='stocks_v1',  # Version in name
    ...
)

# Update metadata with version info
BundleMetadata.update(
    'stocks_v1',
    data_version='1.0.0',
    change_description='Initial release'
)
```

### 3. Regular Ingestion

```python
import schedule
import time

def ingest_daily():
    """Daily ingestion job."""
    ingest('my_bundle', keep_last=7)  # Keep last week

# Schedule daily ingestion
schedule.every().day.at("02:00").do(ingest_daily)

while True:
    schedule.run_pending()
    time.sleep(60)
```

### 4. Data Validation

```python
from rustybt.data.polars.validation import DataValidator

def validate_after_ingest(bundle_name: str):
    """Validate data quality after ingestion."""
    metadata = BundleMetadata.get(bundle_name)

    if not metadata['validation_passed']:
        print(f"❌ Validation failed for {bundle_name}")
        print(f"OHLCV violations: {metadata['ohlcv_violations']}")
        print(f"Missing days: {metadata['missing_days_count']}")
        return False

    print(f"✓ Validation passed for {bundle_name}")
    return True

# Run validation
ingest('my_bundle')
if not validate_after_ingest('my_bundle'):
    # Handle validation failure
    pass
```

## Troubleshooting

### Issue: Bundle Not Found

```python
from rustybt.data.bundles import bundles

# Check if bundle is registered
if 'my_bundle' not in bundles:
    print("Bundle not registered")
    # Re-register bundle
    register('my_bundle', ...)
```

### Issue: Ingestion Fails

```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Retry ingestion
try:
    ingest('my_bundle', show_progress=True)
except Exception as e:
    print(f"Ingestion failed: {e}")
    # Check adapter configuration
    # Verify data source accessibility
    # Check disk space
```

### Issue: Data Quality Problems

```python
# Investigate quality issues
metadata = BundleMetadata.get('my_bundle')

if metadata['ohlcv_violations'] > 0:
    print("OHLCV relationship violations detected")
    # Re-ingest from source
    # Or use different adapter

if metadata['missing_days_count'] > 0:
    print(f"Missing {metadata['missing_days_count']} days of data")
    missing_days = metadata.get('missing_days_list', [])
    print(f"Missing dates: {missing_days}")
```

## Next Steps

- **[Bundle Creation](bundles.md)** - Detailed bundle registration and ingestion
- **[Metadata API](metadata.md)** - Comprehensive metadata management
- **[Migration Guide](migration.md)** - Migrating from HDF5/bcolz to Parquet

## See Also

- [Data Adapters](../adapters/overview.md) - Data sources
- [Bar Readers](../readers/bar-readers.md) - Reading bundle data
- [Data Portal](../readers/data-portal.md) - Unified data access
