# Catalog API Reference

Complete API reference for RustyBT's data catalog system.

## Overview

This document provides detailed API reference for:
- **BundleMetadata** - Core catalog operations (CRUD, symbols, cache)
- **BundleMetadataTracker** - Automated metadata collection during ingestion
- **DataCatalog** - Deprecated compatibility layer (use BundleMetadata instead)

## BundleMetadata

Class-based API for managing bundle metadata. All methods are class methods (no instance required).

**Import**:
```python
from rustybt.data.bundles.metadata import BundleMetadata
```

### Core Metadata Operations

#### BundleMetadata.update()

Update or create bundle metadata with provenance, quality, and file information.

**Signature**:
```python
@classmethod
def update(cls, bundle_name: str, **metadata: Any) -> None
```

**Parameters**:
- `bundle_name` (str, required): Name of the bundle
- `**metadata` (Any): Metadata fields to update:
  - **Provenance**: `source_type` (required for new), `source_url`, `api_version`, `fetch_timestamp`, `data_version`, `timezone`
  - **Quality**: `row_count`, `start_date`, `end_date`, `missing_days_count`, `missing_days_list`, `outlier_count`, `ohlcv_violations`, `validation_passed`, `validation_timestamp`
  - **File**: `file_checksum`, `file_size_bytes`, `checksum`

**Returns**: None

**Raises**:
- `ValueError`: If `source_type` missing when creating new bundle

**Example**:
```python
import time
from rustybt.data.bundles.metadata import BundleMetadata

# Create new bundle metadata
BundleMetadata.update(
    bundle_name="crypto-daily",
    source_type="ccxt",
    source_url="https://api.binance.com",
    api_version="v3",
    fetch_timestamp=int(time.time()),
    row_count=50000,
    start_date=1609459200,  # 2021-01-01 Unix timestamp
    end_date=1704067200,    # 2024-01-01 Unix timestamp
    ohlcv_violations=0,
    validation_passed=True
)

# Update existing bundle
BundleMetadata.update(
    bundle_name="crypto-daily",
    row_count=55000,  # Updated row count
    end_date=1706659200  # Extended date range
)

print("✓ Bundle metadata updated")
```

**Notes**:
- First call for a bundle requires `source_type`
- Subsequent calls can update any fields
- Fields not provided remain unchanged
- Timestamps are Unix timestamps (integers)
- `missing_days_list` can be list or JSON string

---

#### BundleMetadata.get()

Retrieve complete metadata for a bundle.

**Signature**:
```python
@classmethod
def get(cls, bundle_name: str) -> dict[str, Any] | None
```

**Parameters**:
- `bundle_name` (str): Name of the bundle

**Returns**:
- `dict[str, Any]`: Dictionary with all metadata fields
- `None`: If bundle not found

**Example**:
```python
from rustybt.data.bundles.metadata import BundleMetadata

# Retrieve bundle metadata
metadata = BundleMetadata.get("crypto-daily")

if metadata:
    print(f"Bundle: {metadata['bundle_name']}")
    print(f"Source: {metadata['source_type']}")
    print(f"Rows: {metadata['row_count']}")
    print(f"Date Range: {metadata['start_date']} to {metadata['end_date']}")
    print(f"Quality: {'PASS' if metadata['validation_passed'] else 'FAIL'}")
    print(f"OHLCV Violations: {metadata['ohlcv_violations']}")
else:
    print("Bundle not found")
```

**Returned Fields**:
```python
{
    'bundle_name': str,
    'source_type': str,
    'source_url': str | None,
    'api_version': str | None,
    'fetch_timestamp': int,
    'data_version': str | None,
    'timezone': str,
    'row_count': int | None,
    'start_date': int | None,
    'end_date': int | None,
    'missing_days_count': int,
    'missing_days_list': list,  # Deserialized from JSON
    'outlier_count': int,
    'ohlcv_violations': int,
    'validation_passed': bool,
    'validation_timestamp': int | None,
    'file_checksum': str | None,
    'file_size_bytes': int | None,
    'checksum': str | None,
    'created_at': int,
    'updated_at': int
}
```

---

#### BundleMetadata.list_bundles()

List all bundles with optional filtering by source type and date range.

**Signature**:
```python
@classmethod
def list_bundles(
    cls,
    source_type: str | None = None,
    start_date: int | None = None,
    end_date: int | None = None
) -> list[dict[str, Any]]
```

**Parameters**:
- `source_type` (str, optional): Filter by source type (e.g., "yfinance", "ccxt")
- `start_date` (int, optional): Filter bundles with data >= this date (Unix timestamp)
- `end_date` (int, optional): Filter bundles with data <= this date (Unix timestamp)

**Returns**:
- `list[dict[str, Any]]`: List of bundle metadata dictionaries

**Example**:
```python
from rustybt.data.bundles.metadata import BundleMetadata

# List all bundles
all_bundles = BundleMetadata.list_bundles()
print(f"Total bundles: {len(all_bundles)}")

# Filter by source type
yfinance_bundles = BundleMetadata.list_bundles(source_type="yfinance")
print(f"YFinance bundles: {len(yfinance_bundles)}")

# Filter by date range
recent_bundles = BundleMetadata.list_bundles(
    start_date=1672531200,  # 2023-01-01
    end_date=1704067200     # 2024-01-01
)

# Display results
for bundle in recent_bundles:
    print(f"{bundle['bundle_name']}: {bundle['row_count']} rows, "
          f"validation={'PASS' if bundle['validation_passed'] else 'FAIL'}")
```

**Returned Fields (per bundle)**:
```python
{
    'bundle_name': str,
    'source_type': str,
    'source_url': str | None,
    'fetch_timestamp': int,
    'checksum': str | None,
    'file_checksum': str | None,
    'file_size_bytes': int | None,
    'row_count': int | None,
    'start_date': int | None,
    'end_date': int | None,
    'validation_passed': bool
}
```

---

#### BundleMetadata.delete()

Delete bundle and all associated metadata (symbols, cache entries).

**Signature**:
```python
@classmethod
def delete(cls, bundle_name: str) -> bool
```

**Parameters**:
- `bundle_name` (str): Name of bundle to delete

**Returns**:
- `bool`: True if deleted, False if not found

**Example**:
```python
from rustybt.data.bundles.metadata import BundleMetadata

# Delete a bundle
deleted = BundleMetadata.delete("old-bundle")

if deleted:
    print("✓ Bundle deleted successfully")
else:
    print("✗ Bundle not found")
```

**Notes**:
- Cascading delete: Also removes symbols and cache entries
- Cannot be undone
- Physical data files (Parquet) are NOT deleted

---

### Symbol Management

#### BundleMetadata.add_symbol()

Add or update a symbol for a bundle.

**Signature**:
```python
@classmethod
def add_symbol(
    cls,
    bundle_name: str,
    symbol: str,
    asset_type: str | None = None,
    exchange: str | None = None
) -> int
```

**Parameters**:
- `bundle_name` (str): Bundle name
- `symbol` (str): Symbol string (e.g., "AAPL", "BTC/USDT")
- `asset_type` (str, optional): Asset type ("equity", "crypto", "future", etc.)
- `exchange` (str, optional): Exchange name ("NYSE", "binance", etc.)

**Returns**:
- `int`: Symbol ID (primary key)

**Example**:
```python
from rustybt.data.bundles.metadata import BundleMetadata

# Add stock symbols
symbol_id_1 = BundleMetadata.add_symbol(
    "stocks-daily",
    "AAPL",
    asset_type="equity",
    exchange="NASDAQ"
)

symbol_id_2 = BundleMetadata.add_symbol(
    "stocks-daily",
    "MSFT",
    asset_type="equity",
    exchange="NASDAQ"
)

# Add crypto symbols
BundleMetadata.add_symbol(
    "crypto-hourly",
    "BTC/USDT",
    asset_type="crypto",
    exchange="binance"
)

BundleMetadata.add_symbol(
    "crypto-hourly",
    "ETH/USDT",
    asset_type="crypto",
    exchange="binance"
)

print(f"✓ Added symbols (IDs: {symbol_id_1}, {symbol_id_2})")
```

**Notes**:
- Duplicate (bundle_name, symbol) updates existing entry
- `asset_type` and `exchange` are optional but recommended

---

#### BundleMetadata.get_symbols()

Retrieve all symbols for a bundle.

**Signature**:
```python
@classmethod
def get_symbols(cls, bundle_name: str) -> list[dict[str, Any]]
```

**Parameters**:
- `bundle_name` (str): Bundle name

**Returns**:
- `list[dict[str, Any]]`: List of symbol dictionaries

**Example**:
```python
from rustybt.data.bundles.metadata import BundleMetadata

# Get symbols for a bundle
symbols = BundleMetadata.get_symbols("stocks-daily")

print(f"Bundle has {len(symbols)} symbols:")
for symbol in symbols:
    print(f"  {symbol['symbol']}: {symbol['asset_type']} on {symbol['exchange']}")

# Example output:
#   AAPL: equity on NASDAQ
#   MSFT: equity on NASDAQ
#   GOOGL: equity on NASDAQ
```

**Returned Fields (per symbol)**:
```python
{
    'symbol_id': int,
    'bundle_name': str,
    'symbol': str,
    'asset_type': str | None,
    'exchange': str | None
}
```

---

### Quality Metrics

#### BundleMetadata.get_quality_metrics()

Retrieve quality metrics for a bundle.

**Signature**:
```python
@classmethod
def get_quality_metrics(cls, bundle_name: str) -> dict[str, Any] | None
```

**Parameters**:
- `bundle_name` (str): Bundle name

**Returns**:
- `dict[str, Any]`: Quality metrics dictionary
- `None`: If bundle not found

**Example**:
```python
from rustybt.data.bundles.metadata import BundleMetadata

# Get quality metrics
metrics = BundleMetadata.get_quality_metrics("stocks-daily")

if metrics:
    print("Quality Metrics:")
    print(f"  Rows: {metrics['row_count']}")
    print(f"  Date Range: {metrics['start_date']} to {metrics['end_date']}")
    print(f"  Missing Days: {metrics['missing_days_count']}")
    print(f"  Outliers: {metrics['outlier_count']}")
    print(f"  OHLCV Violations: {metrics['ohlcv_violations']}")
    print(f"  Validation: {'PASSED' if metrics['validation_passed'] else 'FAILED'}")
```

**Returned Fields**:
```python
{
    'bundle_name': str,
    'row_count': int | None,
    'start_date': int | None,
    'end_date': int | None,
    'missing_days_count': int,
    'missing_days_list': list,
    'outlier_count': int,
    'ohlcv_violations': int,
    'validation_timestamp': int | None,
    'validation_passed': bool
}
```

---

### Cache Management

#### BundleMetadata.add_cache_entry()

Add cache entry for bundle (used internally by caching system).

**Signature**:
```python
@classmethod
def add_cache_entry(
    cls,
    cache_key: str,
    bundle_name: str,
    parquet_path: str,
    size_bytes: int
) -> None
```

**Parameters**:
- `cache_key` (str): Unique cache key (SHA256 hash)
- `bundle_name` (str): Bundle name
- `parquet_path` (str): Path to cached Parquet file
- `size_bytes` (int): Size of cached file in bytes

**Returns**: None

**Example**:
```python
import hashlib
from rustybt.data.bundles.metadata import BundleMetadata

# Generate cache key
cache_key = hashlib.sha256(b"query-params").hexdigest()[:16]

# Add cache entry
BundleMetadata.add_cache_entry(
    cache_key=cache_key,
    bundle_name="stocks-daily",
    parquet_path="/cache/stocks-daily-AAPL.parquet",
    size_bytes=1024000
)

print(f"✓ Cache entry added: {cache_key}")
```

**Notes**:
- Updates `last_accessed` if entry exists
- Used for LRU cache management
- Typically called by caching layer, not user code

---

### Utility Methods

#### BundleMetadata.count_bundles()

Count total number of bundles in catalog.

**Signature**:
```python
@classmethod
def count_bundles(cls) -> int
```

**Returns**:
- `int`: Total bundle count

**Example**:
```python
from rustybt.data.bundles.metadata import BundleMetadata

count = BundleMetadata.count_bundles()
print(f"Total bundles in catalog: {count}")
```

---

#### BundleMetadata.count_symbols()

Count symbols for a specific bundle.

**Signature**:
```python
@classmethod
def count_symbols(cls, bundle_name: str) -> int
```

**Parameters**:
- `bundle_name` (str): Bundle name

**Returns**:
- `int`: Symbol count for bundle

**Example**:
```python
from rustybt.data.bundles.metadata import BundleMetadata

count = BundleMetadata.count_symbols("stocks-daily")
print(f"Bundle 'stocks-daily' has {count} symbols")
```

---

#### BundleMetadata.count_all_symbols()

Count total symbols across all bundles.

**Signature**:
```python
@classmethod
def count_all_symbols(cls) -> int
```

**Returns**:
- `int`: Total symbol count across all bundles

**Example**:
```python
from rustybt.data.bundles.metadata import BundleMetadata

total_symbols = BundleMetadata.count_all_symbols()
total_bundles = BundleMetadata.count_bundles()

print(f"Catalog contains {total_bundles} bundles with {total_symbols} symbols")
print(f"Average: {total_symbols / total_bundles:.1f} symbols per bundle")
```

---

#### BundleMetadata.count_quality_records()

Count bundles with quality metrics.

**Signature**:
```python
@classmethod
def count_quality_records(cls) -> int
```

**Returns**:
- `int`: Count of bundles with validation_timestamp set

**Example**:
```python
from rustybt.data.bundles.metadata import BundleMetadata

quality_count = BundleMetadata.count_quality_records()
total_count = BundleMetadata.count_bundles()

print(f"Quality metrics: {quality_count}/{total_count} bundles")
print(f"Coverage: {quality_count / total_count * 100:.1f}%")
```

---

#### BundleMetadata.set_db_path()

Set custom database path (useful for testing).

**Signature**:
```python
@classmethod
def set_db_path(cls, db_path: str) -> None
```

**Parameters**:
- `db_path` (str): Path to SQLite database file

**Returns**: None

**Example**:
```python
import tempfile
from pathlib import Path
from rustybt.data.bundles.metadata import BundleMetadata

# Use custom database for testing
with tempfile.TemporaryDirectory() as tmpdir:
    test_db = str(Path(tmpdir) / "test.db")
    BundleMetadata.set_db_path(test_db)

    # Now all operations use test database
    BundleMetadata.update(
        bundle_name="test-bundle",
        source_type="csv"
    )

    print(f"✓ Using test database: {test_db}")
```

**Notes**:
- Forces engine recreation with new path
- Primarily for testing isolation
- Default path: `~/.rustybt/data/assets-{VERSION}.db`

---

## BundleMetadataTracker

Helper class for automated metadata collection during bundle ingestion.

**Import**:
```python
from rustybt.data.metadata_tracker import BundleMetadataTracker
```

### Constructor

#### BundleMetadataTracker()

Initialize metadata tracker.

**Signature**:
```python
def __init__(self, catalog: DataCatalog | None = None)
```

**Parameters**:
- `catalog` (DataCatalog, optional): DataCatalog instance. If None, creates default.

**Example**:
```python
from rustybt.data.metadata_tracker import BundleMetadataTracker

# Create tracker with default catalog
tracker = BundleMetadataTracker()

# Or with custom catalog (for testing)
from rustybt.data.catalog import DataCatalog
custom_catalog = DataCatalog(db_path="test.db")
tracker = BundleMetadataTracker(catalog=custom_catalog)
```

---

### Ingestion Methods

#### BundleMetadataTracker.record_bundle_ingestion()

Record metadata and quality metrics for general bundle ingestion.

**Signature**:
```python
def record_bundle_ingestion(
    self,
    bundle_name: str,
    source_type: str,
    data_files: list[Path],
    data: pl.DataFrame | None = None,
    source_url: str | None = None,
    api_version: str | None = None,
    data_version: str | None = None,
    calendar: ExchangeCalendar | None = None,
    timezone: str = "UTC"
) -> dict[str, Any]
```

**Parameters**:
- `bundle_name` (str): Bundle name
- `source_type` (str): Source type ("csv", "yfinance", "ccxt", etc.)
- `data_files` (list[Path]): List of data file paths
- `data` (pl.DataFrame, optional): OHLCV DataFrame for quality analysis
- `source_url` (str, optional): URL or path to data source
- `api_version` (str, optional): API version identifier
- `data_version` (str, optional): Data version identifier
- `calendar` (ExchangeCalendar, optional): Trading calendar for gap detection
- `timezone` (str, optional): Data timezone (default: "UTC")

**Returns**:
- `dict[str, Any]`: Dictionary with `metadata` and `quality_metrics` keys

**Example**:
```python
import polars as pl
import tempfile
from pathlib import Path
from rustybt.data.metadata_tracker import BundleMetadataTracker
from exchange_calendars import get_calendar

# Create sample OHLCV data
data = pl.DataFrame({
    "date": ["2024-01-01", "2024-01-02", "2024-01-03"],
    "open": [100.0, 101.0, 102.0],
    "high": [102.0, 103.0, 104.0],
    "low": [99.0, 100.0, 101.0],
    "close": [101.0, 102.0, 103.0],
    "volume": [1000, 1100, 1200]
})

# Save to file
with tempfile.TemporaryDirectory() as tmpdir:
    data_file = Path(tmpdir) / "data.parquet"
    data.write_parquet(data_file)

    # Record ingestion
    tracker = BundleMetadataTracker()
    calendar = get_calendar("NYSE")

    result = tracker.record_bundle_ingestion(
        bundle_name="my-bundle",
        source_type="csv",
        data_files=[data_file],
        data=data,
        source_url="/data/stocks.csv",
        calendar=calendar,
        timezone="America/New_York"
    )

    print("Metadata:", result["metadata"])
    print("Quality Metrics:", result["quality_metrics"])
```

**Notes**:
- Calculates file checksums automatically
- Runs quality validation if `data` provided
- Stores both provenance and quality metrics

---

#### BundleMetadataTracker.record_csv_bundle()

Convenience method for CSV bundle ingestion.

**Signature**:
```python
def record_csv_bundle(
    self,
    bundle_name: str,
    csv_dir: Path,
    data: pl.DataFrame | None = None,
    calendar: ExchangeCalendar | None = None
) -> dict[str, Any]
```

**Parameters**:
- `bundle_name` (str): Bundle name
- `csv_dir` (Path): Directory containing CSV files
- `data` (pl.DataFrame, optional): OHLCV DataFrame
- `calendar` (ExchangeCalendar, optional): Trading calendar

**Returns**:
- `dict[str, Any]`: Dictionary with `metadata` and `quality_metrics`

**Example**:
```python
import polars as pl
import tempfile
from pathlib import Path
from rustybt.data.metadata_tracker import BundleMetadataTracker
from exchange_calendars import get_calendar

# Create sample data
data = pl.DataFrame({
    "date": ["2024-01-01", "2024-01-02"],
    "open": [100.0, 101.0],
    "high": [102.0, 103.0],
    "low": [99.0, 100.0],
    "close": [101.0, 102.0],
    "volume": [1000, 1100]
})

# Save to CSV directory
with tempfile.TemporaryDirectory() as tmpdir:
    csv_dir = Path(tmpdir)
    csv_file = csv_dir / "stocks.csv"
    data.write_csv(csv_file)

    # Record CSV bundle
    tracker = BundleMetadataTracker()
    calendar = get_calendar("NYSE")

    result = tracker.record_csv_bundle(
        bundle_name="csv-stocks",
        csv_dir=csv_dir,
        data=data,
        calendar=calendar
    )

    print(f"✓ Recorded CSV bundle: {result['metadata']['bundle_name']}")
    print(f"  Checksum: {result['metadata']['checksum'][:16]}...")
    print(f"  Rows: {result['quality_metrics']['row_count']}")
```

---

#### BundleMetadataTracker.record_api_bundle()

Convenience method for API-sourced bundle ingestion.

**Signature**:
```python
def record_api_bundle(
    self,
    bundle_name: str,
    source_type: str,
    data_file: Path,
    data: pl.DataFrame | None = None,
    api_url: str | None = None,
    api_version: str | None = None,
    data_version: str | None = None,
    calendar: ExchangeCalendar | None = None
) -> dict[str, Any]
```

**Parameters**:
- `bundle_name` (str): Bundle name
- `source_type` (str): API source type ("yfinance", "ccxt", etc.)
- `data_file` (Path): Path to saved API data file
- `data` (pl.DataFrame, optional): OHLCV DataFrame
- `api_url` (str, optional): API endpoint URL
- `api_version` (str, optional): API version
- `data_version` (str, optional): Data version from API
- `calendar` (ExchangeCalendar, optional): Trading calendar

**Returns**:
- `dict[str, Any]`: Dictionary with `metadata` and `quality_metrics`

**Example**:
```python
import polars as pl
import tempfile
from pathlib import Path
from rustybt.data.metadata_tracker import BundleMetadataTracker

# Simulate API data
data = pl.DataFrame({
    "date": ["2024-01-01", "2024-01-02"],
    "open": [100.0, 101.0],
    "high": [102.0, 103.0],
    "low": [99.0, 100.0],
    "close": [101.0, 102.0],
    "volume": [1000, 1100]
})

# Save data
with tempfile.TemporaryDirectory() as tmpdir:
    data_file = Path(tmpdir) / "api_data.parquet"
    data.write_parquet(data_file)

    # Record API bundle
    tracker = BundleMetadataTracker()

    result = tracker.record_api_bundle(
        bundle_name="yfinance-stocks",
        source_type="yfinance",
        data_file=data_file,
        data=data,
        api_url="https://query1.finance.yahoo.com/v8/finance",
        api_version="v8"
    )

    print(f"✓ Recorded API bundle from {result['metadata']['source_type']}")
```

---

## Deprecated APIs

### DataCatalog

**Status**: Deprecated in v1.0, will be removed in v2.0

**Migration**: Use `BundleMetadata` instead

**Import**:
```python
# Deprecated - use BundleMetadata instead
from rustybt.data.catalog import DataCatalog
```

All `DataCatalog` methods delegate to `BundleMetadata`. See [Migration Guide](migration-guide.md) for details.

---

## Complete Usage Example

```python
import time
import polars as pl
import tempfile
from pathlib import Path
from rustybt.data.bundles.metadata import BundleMetadata
from rustybt.data.metadata_tracker import BundleMetadataTracker
from exchange_calendars import get_calendar

# Step 1: Create bundle metadata
BundleMetadata.update(
    bundle_name="example-bundle",
    source_type="yfinance",
    source_url="https://query1.finance.yahoo.com",
    api_version="v8",
    fetch_timestamp=int(time.time())
)

# Step 2: Add symbols
BundleMetadata.add_symbol("example-bundle", "AAPL", "equity", "NASDAQ")
BundleMetadata.add_symbol("example-bundle", "MSFT", "equity", "NASDAQ")
BundleMetadata.add_symbol("example-bundle", "GOOGL", "equity", "NASDAQ")

# Step 3: Simulate data ingestion with quality tracking
data = pl.DataFrame({
    "date": ["2024-01-01", "2024-01-02", "2024-01-03"],
    "open": [100.0, 101.0, 102.0],
    "high": [102.0, 103.0, 104.0],
    "low": [99.0, 100.0, 101.0],
    "close": [101.0, 102.0, 103.0],
    "volume": [1000, 1100, 1200]
})

with tempfile.TemporaryDirectory() as tmpdir:
    data_file = Path(tmpdir) / "data.parquet"
    data.write_parquet(data_file)

    tracker = BundleMetadataTracker()
    calendar = get_calendar("NYSE")

    result = tracker.record_bundle_ingestion(
        bundle_name="example-bundle",
        source_type="yfinance",
        data_files=[data_file],
        data=data,
        calendar=calendar
    )

    # Step 4: Query metadata
    metadata = BundleMetadata.get("example-bundle")
    print(f"\nBundle: {metadata['bundle_name']}")
    print(f"Source: {metadata['source_type']}")
    print(f"Rows: {metadata['row_count']}")
    print(f"Quality: {'PASS' if metadata['validation_passed'] else 'FAIL'}")

    # Step 5: Query symbols
    symbols = BundleMetadata.get_symbols("example-bundle")
    print(f"\nSymbols ({len(symbols)}):")
    for symbol in symbols:
        print(f"  - {symbol['symbol']} ({symbol['asset_type']})")

    # Step 6: List all bundles
    all_bundles = BundleMetadata.list_bundles()
    print(f"\nTotal bundles in catalog: {len(all_bundles)}")

print("\n✅ Complete catalog workflow demonstrated")
```

## See Also

- [Catalog Architecture](architecture.md) - System design and database schema
- [Catalog Overview](README.md) - Introduction and quick start
- [Bundle Management](bundle-system.md) - Bundle lifecycle operations
- [Metadata Tracking](metadata-tracking.md) - Ingestion metadata
