# Data Catalog & Bundle Management

Comprehensive guide to RustyBT's data catalog system and bundle management infrastructure.

## Overview

The RustyBT data catalog provides a unified system for managing bundle metadata, tracking data quality, and optimizing data access through intelligent caching. The catalog is built on SQLite with a class-based Python API.

## Architecture

### Core Components

1. **BundleMetadata** - Unified metadata catalog (CURRENT)
   - Provenance tracking (source, versions, timestamps)
   - Quality metrics (OHLCV validation, missing data)
   - Symbol tracking (asset types, exchanges)
   - Cache management (LRU eviction, statistics)
   - File metadata (checksums, sizes)

2. **BundleMetadataTracker** - Ingestion helper
   - Automated metadata collection during bundle creation
   - Quality metric calculation
   - Checksum computation

3. **Bundle Core System** - Bundle lifecycle management
   - Registration, ingestion, loading
   - Directory structure and file paths
   - Data writers (daily/minute bars, assets, adjustments)

### Database Schema

The catalog uses a single SQLite database (`assets-{VERSION}.db`) with four main tables:

#### 1. bundle_metadata
Core bundle information with foreign key to bundle_symbols.

**Fields**:
- **Provenance**: `source_type`, `source_url`, `api_version`, `fetch_timestamp`, `data_version`
- **Quality**: `row_count`, `start_date`, `end_date`, `missing_days_count`, `missing_days_list`, `outlier_count`, `ohlcv_violations`, `validation_passed`, `validation_timestamp`
- **File**: `file_checksum`, `file_size_bytes`, `timezone`
- **Timestamps**: `created_at`, `updated_at`

#### 2. bundle_symbols
Symbol tracking linked to bundles.

**Fields**:
- `bundle_name` (Foreign Key → bundle_metadata.bundle_name)
- `symbol` (e.g., "AAPL", "BTC/USDT")
- `asset_type` (e.g., "equity", "crypto", "future")
- `exchange` (e.g., "NYSE", "binance")

**Constraint**: Unique(bundle_name, symbol)

#### 3. bundle_cache
Cache entries for LRU eviction.

**Fields**:
- `cache_key` (Unique, indexed)
- `bundle_name`, `bundle_path`
- `symbols` (JSON list), `start`, `end`, `frequency`
- `fetch_timestamp`, `size_bytes`, `row_count`
- `last_accessed` (indexed for LRU)

#### 4. cache_statistics
Daily cache performance metrics.

**Fields**:
- `stat_date` (Primary Key - Unix timestamp, day granularity)
- `hit_count`, `miss_count`
- `total_size_mb`, `avg_fetch_latency_ms`

### Deprecated Components

⚠️ **Do NOT use these in new code**:
- **DataCatalog** (`rustybt.data.catalog`) - Removed in v2.0, use `BundleMetadata`
- **ParquetMetadataCatalog** (`rustybt.data.polars.metadata_catalog`) - Removed in v2.0, use `BundleMetadata`

These classes still exist for backward compatibility but delegate to `BundleMetadata`.

## Quick Start

### Basic Usage

```python
from rustybt.data.bundles.metadata import BundleMetadata

# Update bundle metadata with provenance and quality
BundleMetadata.update(
    bundle_name="yfinance-daily",
    source_type="yfinance",
    source_url="https://query1.finance.yahoo.com",
    api_version="v8",
    row_count=12000,
    start_date=1609459200,  # Unix timestamp
    end_date=1704067200,
    ohlcv_violations=0,
    validation_passed=True
)

# Add symbols to bundle
BundleMetadata.add_symbol("yfinance-daily", "AAPL", "equity", "NASDAQ")
BundleMetadata.add_symbol("yfinance-daily", "MSFT", "equity", "NASDAQ")

# Query metadata
metadata = BundleMetadata.get("yfinance-daily")
print(f"Source: {metadata['source_type']}")
print(f"Rows: {metadata['row_count']}")
print(f"Quality: {'PASS' if metadata['validation_passed'] else 'FAIL'}")

# List all bundles
bundles = BundleMetadata.list_bundles(source_type="yfinance")
for bundle in bundles:
    print(f"{bundle['bundle_name']}: {bundle['row_count']} rows")
```

### Using BundleMetadataTracker

```python
import time
import polars as pl
import tempfile
from pathlib import Path
from rustybt.data.metadata_tracker import BundleMetadataTracker
from exchange_calendars import get_calendar

# Initialize tracker
tracker = BundleMetadataTracker()

# Example: Track CSV bundle ingestion
# Create sample OHLCV data
data = pl.DataFrame({
    "date": ["2024-01-01", "2024-01-02"],
    "open": [100.0, 101.0],
    "high": [102.0, 103.0],
    "low": [99.0, 100.0],
    "close": [101.0, 102.0],
    "volume": [1000, 1100]
})

# Create temporary CSV directory
with tempfile.TemporaryDirectory() as tmpdir:
    csv_dir = Path(tmpdir)
    csv_file = csv_dir / "test.csv"
    data.write_csv(csv_file)

    calendar = get_calendar("NYSE")

    result = tracker.record_csv_bundle(
        bundle_name="my-stocks",
        csv_dir=csv_dir,
        data=data,
        calendar=calendar
    )

    print("Metadata:", result["metadata"])
    print("Quality Metrics:", result["quality_metrics"])
```

## Documentation Structure

- [Catalog API Reference](catalog-api.md) - Complete API documentation
- [Bundle Management](bundle-system.md) - Bundle lifecycle and operations
- [Metadata Tracking](metadata-tracking.md) - Ingestion metadata tracking
- [Migration Guide](migration-guide.md) - HDF5/bcolz to Parquet migration

## Key Features

### 1. Unified Metadata System
Single source of truth for all bundle metadata, replacing separate DataCatalog and ParquetMetadataCatalog.

### 2. Automatic Quality Tracking
Quality metrics calculated and stored during bundle ingestion:
- Row counts and date ranges
- Missing trading days detection
- OHLCV constraint violations
- Outlier detection

### 3. Smart Caching
LRU-based cache management with performance statistics:
- Automatic cache key generation
- Last-accessed tracking for eviction
- Daily hit/miss rate monitoring

### 4. Symbol Management
Track symbols across bundles with asset type and exchange information.

### 5. Provenance Tracking
Complete audit trail:
- Data source and API versions
- Fetch timestamps
- Data versions
- File checksums for integrity

## Design Principles

1. **Single Database** - All metadata in one SQLite database for performance
2. **Foreign Keys** - Proper relationships between bundles, symbols, and cache
3. **Indexed Queries** - Fast lookups by bundle name, symbol, timestamp
4. **Backward Compatible** - Old APIs delegate to new unified system
5. **Type Safety** - Automatic field normalization and validation

## Performance Characteristics

- **Bundle Metadata Lookup**: <5ms (indexed by bundle_name)
- **Symbol Queries**: <10ms (indexed by bundle_name and symbol)
- **Cache Lookup**: <10ms (indexed by cache_key)
- **Statistics Aggregation**: <50ms (daily stats for 30 days)

## Migration from Deprecated APIs

### DataCatalog → BundleMetadata

**Before (Deprecated)**:
```python
from rustybt.data.catalog import DataCatalog

catalog = DataCatalog()
catalog.store_metadata({
    "bundle_name": "test",
    "source_type": "yfinance"
})
```

**After (Current)**:
```python
from rustybt.data.bundles.metadata import BundleMetadata

BundleMetadata.update(
    bundle_name="test",
    source_type="yfinance"
)
```

### ParquetMetadataCatalog → BundleMetadata

**Before (Deprecated)**:
```python
from rustybt.data.polars.metadata_catalog import ParquetMetadataCatalog

catalog = ParquetMetadataCatalog("metadata.db")
dataset_id = catalog.create_dataset("yfinance", "1d")
catalog.add_symbol(dataset_id, "AAPL", "equity", "NASDAQ")
```

**After (Current)**:
```python
from rustybt.data.bundles.metadata import BundleMetadata

BundleMetadata.update(
    bundle_name="yfinance-daily",
    source_type="yfinance"
)
BundleMetadata.add_symbol("yfinance-daily", "AAPL", "equity", "NASDAQ")
```

## See Also

- [Data Adapters](../adapters/README.md) - Data source adapters
- [Bundle Ingestion](bundle-system.md) - Creating and managing bundles
