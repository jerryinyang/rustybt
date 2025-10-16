# Metadata Tracking

Complete guide to RustyBT's metadata tracking system for bundle data quality, provenance, and integrity.

## Overview

The metadata tracking system provides automated collection and validation of bundle metadata during ingestion, ensuring data quality and enabling audit trails. It tracks:

1. **Provenance** - Data source, version, fetch timestamps
2. **Quality Metrics** - OHLCV validation, outlier detection, gap analysis
3. **Integrity** - File checksums for data verification
4. **Versioning** - API versions, data versions, schema versions

## Quick Start

### Basic Metadata Tracking

```python
import polars as pl
from pathlib import Path
from rustybt.data.metadata_tracker import BundleMetadataTracker
from exchange_calendars import get_calendar

# Create tracker
tracker = BundleMetadataTracker()

# Load OHLCV data
data = pl.read_parquet("stocks.parquet")

# Track metadata with quality validation
result = tracker.record_bundle_ingestion(
    bundle_name="my-stocks",
    source_type="yfinance",
    data_files=[Path("stocks.parquet")],
    data=data,
    source_url="https://query1.finance.yahoo.com",
    api_version="v8",
    calendar=get_calendar("NYSE")
)

# Access results
print("Provenance:", result["metadata"])
print("Quality:", result["quality_metrics"])
```

## Provenance Tracking

### Metadata Schema

Provenance metadata captures where data came from and when it was fetched.

**Fields**:
```python
{
    'bundle_name': str,          # Bundle identifier
    'source_type': str,          # Data source ('yfinance', 'ccxt', 'csv', etc.)
    'source_url': str | None,    # Source URL or file path
    'api_version': str | None,   # API version identifier
    'fetch_timestamp': int,      # Unix timestamp of data fetch
    'data_version': str | None,  # Data version from source
    'checksum': str,             # SHA256 checksum of data files
    'timezone': str,             # Data timezone (default: 'UTC')
}
```

### Example - API Provenance

```python
from rustybt.data.metadata_tracker import BundleMetadataTracker
from pathlib import Path

tracker = BundleMetadataTracker()

# Track API bundle metadata
result = tracker.record_api_bundle(
    bundle_name="crypto-btc",
    source_type="ccxt",
    data_file=Path("btc_hourly.parquet"),
    api_url="https://api.binance.com/api/v3/klines",
    api_version="v3",
    data_version="2024-01-15"
)

metadata = result["metadata"]
print(f"Source: {metadata['source_type']} v{metadata['api_version']}")
print(f"Fetched: {metadata['fetch_timestamp']}")
print(f"Checksum: {metadata['checksum']}")
```

### Example - CSV Provenance

```python
from rustybt.data.metadata_tracker import track_csv_bundle_metadata
from pathlib import Path

# Track CSV bundle
result = track_csv_bundle_metadata(
    bundle_name="historical-stocks",
    csv_dir="/data/stocks",
)

metadata = result["metadata"]
print(f"Source: {metadata['source_url']}")
print(f"Files checksum: {metadata['checksum']}")
```

---

## Quality Metrics

### Quality Schema

Quality metrics validate data correctness and completeness.

**Fields**:
```python
{
    'row_count': int,              # Total rows in dataset
    'start_date': int,             # First date (Unix timestamp)
    'end_date': int,               # Last date (Unix timestamp)
    'missing_days_count': int,     # Count of missing trading days
    'missing_days_list': str,      # JSON list of missing dates
    'outlier_count': int,          # Count of outlier rows
    'ohlcv_violations': int,       # Count of OHLCV constraint violations
    'validation_timestamp': int,   # Unix timestamp of validation
    'validation_passed': bool,     # Overall validation status
}
```

### OHLCV Validation

Validates financial data constraints:
- `high` >= max(`open`, `close`)
- `low` <= min(`open`, `close`)
- `high` >= `low`
- `volume` >= 0

**Example**:
```python
import polars as pl
from rustybt.data.quality import calculate_quality_metrics

# Sample data with violations
data = pl.DataFrame({
    "date": ["2024-01-01", "2024-01-02", "2024-01-03"],
    "open": [100.0, 101.0, 102.0],
    "high": [99.0, 103.0, 104.0],    # Violation: high < open on first day
    "low": [98.0, 100.0, 101.0],
    "close": [101.0, 102.0, 103.0],
    "volume": [1000, -50, 1200],      # Violation: negative volume
})

metrics = calculate_quality_metrics(data)

print(f"Rows: {metrics['row_count']}")
print(f"OHLCV Violations: {metrics['ohlcv_violations']}")
print(f"Validation: {'PASS' if metrics['validation_passed'] else 'FAIL'}")

# Expected output:
# Rows: 3
# OHLCV Violations: 1 (counts unique rows with violations)
# Validation: FAIL
```

### Outlier Detection

Uses IQR (Interquartile Range) method to detect extreme values.

**Algorithm**:
```
Q1 = 25th percentile
Q3 = 75th percentile
IQR = Q3 - Q1
Lower Bound = Q1 - 3 * IQR
Upper Bound = Q3 + 3 * IQR
Outlier = value < Lower Bound OR value > Upper Bound
```

**Example**:
```python
import polars as pl
from rustybt.data.quality import calculate_quality_metrics

# Data with price spike outlier
data = pl.DataFrame({
    "date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
    "open": [100.0, 101.0, 500.0, 102.0],  # 500.0 is outlier
    "high": [102.0, 103.0, 502.0, 104.0],
    "low": [99.0, 100.0, 498.0, 101.0],
    "close": [101.0, 102.0, 501.0, 103.0],
    "volume": [1000, 1100, 5000, 1200],
})

metrics = calculate_quality_metrics(data)

print(f"Outliers Detected: {metrics['outlier_count']}")
# Outliers Detected: 4  (one row, 4 price columns)
```

### Gap Detection

Identifies missing trading days using exchange calendars.

**Example**:
```python
import polars as pl
from rustybt.data.quality import calculate_quality_metrics
from exchange_calendars import get_calendar

# Data with missing day (2024-01-03 is a trading day but missing)
data = pl.DataFrame({
    "date": ["2024-01-02", "2024-01-04", "2024-01-05"],
    "open": [100.0, 102.0, 103.0],
    "high": [102.0, 104.0, 105.0],
    "low": [99.0, 101.0, 102.0],
    "close": [101.0, 103.0, 104.0],
    "volume": [1000, 1200, 1300],
})

calendar = get_calendar("NYSE")
metrics = calculate_quality_metrics(data, calendar=calendar)

print(f"Missing Days: {metrics['missing_days_count']}")
print(f"Missing Dates: {metrics['missing_days_list']}")
# Missing Days: 1
# Missing Dates: ["2024-01-03"]
```

### Quality Report Generation

```python
from rustybt.data.quality import calculate_quality_metrics, generate_quality_report
import polars as pl
from exchange_calendars import get_calendar

data = pl.read_parquet("stocks.parquet")
calendar = get_calendar("NYSE")

metrics = calculate_quality_metrics(data, calendar=calendar)
report = generate_quality_report(metrics)

print(report)
```

**Output**:
```
Data Quality Report
===================
Row Count: 252
Date Range: 2024-01-02 to 2024-12-31
Missing Trading Days: 3
Outliers Detected: 5
OHLCV Violations: 0
Validation Status: PASSED
Validated At: 2024-01-15 10:30:00
```

---

## Checksum Validation

### File Integrity

Checksums ensure data hasn't been corrupted or tampered with.

**Example - Single File**:
```python
from rustybt.utils.checksum import calculate_checksum
from pathlib import Path

# Calculate checksum
file_path = Path("stocks.parquet")
checksum = calculate_checksum(file_path)

print(f"File: {file_path.name}")
print(f"SHA256: {checksum}")
# SHA256: a1b2c3d4e5f6... (64 hex characters)
```

**Example - Multiple Files**:
```python
from rustybt.utils.checksum import calculate_checksum_multiple
from pathlib import Path

# Calculate combined checksum for multiple files
files = [
    Path("stocks_2023.csv"),
    Path("stocks_2024.csv"),
]

checksum = calculate_checksum_multiple(files)

print(f"Combined SHA256: {checksum}")
```

### Checksum Verification

```python
from rustybt.utils.checksum import calculate_checksum
from rustybt.data.bundles.metadata import BundleMetadata

# Get stored checksum from metadata
metadata = BundleMetadata.get("my-bundle")
stored_checksum = metadata['checksum']

# Recalculate checksum
current_checksum = calculate_checksum("data.parquet")

# Verify integrity
if current_checksum == stored_checksum:
    print("✓ Data integrity verified")
else:
    print("✗ WARNING: Data has been modified!")
    print(f"  Expected: {stored_checksum}")
    print(f"  Actual:   {current_checksum}")
```

---

## Gap Analysis

### Detect Missing Days

```python
import polars as pl
from rustybt.utils.gap_detection import detect_missing_days
from exchange_calendars import get_calendar

data = pl.read_parquet("stocks.parquet")
calendar = get_calendar("NYSE")

missing_days = detect_missing_days(data, calendar, date_column="date")

print(f"Found {len(missing_days)} missing trading days:")
for day in missing_days[:5]:  # Show first 5
    print(f"  - {day.strftime('%Y-%m-%d')}")
```

### Gap Report

```python
from rustybt.utils.gap_detection import detect_missing_days, generate_gap_report
import polars as pl
from exchange_calendars import get_calendar

data = pl.read_parquet("stocks.parquet")
calendar = get_calendar("NYSE")

missing_days = detect_missing_days(data, calendar)
gap_report = generate_gap_report(missing_days, threshold=3)

print(f"Total Gaps: {gap_report['total_gaps']}")
print(f"Gap Ranges: {len(gap_report['gap_ranges'])}")

for warning in gap_report['warnings']:
    print(f"⚠️  {warning}")
```

**Example Output**:
```
Total Gaps: 10
Gap Ranges: 3
⚠️  Gap of 5 consecutive days from 2024-03-15 to 2024-03-19
⚠️  Gap of 4 consecutive days from 2024-07-01 to 2024-07-04
```

### Parse Missing Days

```python
from rustybt.utils.gap_detection import parse_missing_days_list, format_missing_days_list
import pandas as pd

# From JSON string to timestamps
missing_json = '["2024-01-03", "2024-01-04", "2024-01-05"]'
missing_days = parse_missing_days_list(missing_json)

for day in missing_days:
    print(day.strftime("%Y-%m-%d"))

# Back to JSON
json_output = format_missing_days_list(missing_days)
print(json_output)  # ["2024-01-03", "2024-01-04", "2024-01-05"]
```

---

## Complete Workflow

### End-to-End Metadata Tracking

```python
import polars as pl
from pathlib import Path
from rustybt.data.metadata_tracker import BundleMetadataTracker
from rustybt.data.bundles.metadata import BundleMetadata
from rustybt.data.quality import generate_quality_report
from exchange_calendars import get_calendar

# Step 1: Fetch data (example with YFinance adapter)
from rustybt.data.adapters import YFinanceAdapter

adapter = YFinanceAdapter()
data = adapter.fetch_ohlcv(
    symbols=["AAPL", "MSFT"],
    start="2024-01-01",
    end="2024-12-31",
    resolution="1d"
)

# Save to file
data_file = Path("stocks.parquet")
data.write_parquet(data_file)

# Step 2: Track metadata with quality validation
tracker = BundleMetadataTracker()
calendar = get_calendar("NYSE")

result = tracker.record_bundle_ingestion(
    bundle_name="tech-stocks-2024",
    source_type="yfinance",
    data_files=[data_file],
    data=data,
    source_url="https://query1.finance.yahoo.com",
    api_version="v8",
    calendar=calendar
)

# Step 3: Review quality report
quality = result["quality_metrics"]
report = generate_quality_report(quality)
print(report)

# Step 4: Verify data integrity
from rustybt.utils.checksum import calculate_checksum

stored_checksum = result["metadata"]["checksum"]
current_checksum = calculate_checksum(data_file)

assert stored_checksum == current_checksum, "Checksum mismatch!"

# Step 5: Query metadata later
metadata = BundleMetadata.get("tech-stocks-2024")
quality_metrics = BundleMetadata.get_quality_metrics("tech-stocks-2024")

print(f"\nBundle: {metadata['bundle_name']}")
print(f"Source: {metadata['source_type']} v{metadata.get('api_version')}")
print(f"Quality: {'PASS' if quality_metrics['validation_passed'] else 'FAIL'}")
print(f"Rows: {quality_metrics['row_count']}")
print(f"Violations: {quality_metrics['ohlcv_violations']}")
```

---

## API Reference

### BundleMetadataTracker

Main class for tracking bundle metadata.

**Constructor**:
```python
tracker = BundleMetadataTracker(catalog=None)
```

**Methods**:
- `record_bundle_ingestion()` - General metadata tracking
- `record_csv_bundle()` - CSV-specific tracking
- `record_api_bundle()` - API-specific tracking

See [Catalog API Reference](catalog-api.md#bundlemetadatatracker) for detailed documentation.

---

### Quality Functions

#### calculate_quality_metrics()

Calculate all quality metrics for OHLCV data.

**Signature**:
```python
def calculate_quality_metrics(
    data: pl.DataFrame,
    calendar: ExchangeCalendar | None = None,
    date_column: str = "date"
) -> dict[str, Any]
```

**Parameters**:
- `data` (pl.DataFrame): OHLCV data
- `calendar` (ExchangeCalendar, optional): For gap detection
- `date_column` (str, optional): Date column name (default: "date")

**Returns**: Quality metrics dictionary

**Example**:
```python
import polars as pl
from rustybt.data.quality import calculate_quality_metrics
from exchange_calendars import get_calendar

data = pl.read_parquet("stocks.parquet")
calendar = get_calendar("NYSE")

metrics = calculate_quality_metrics(data, calendar=calendar)
print(f"Validation: {metrics['validation_passed']}")
```

---

#### generate_quality_report()

Generate human-readable quality report.

**Signature**:
```python
def generate_quality_report(metrics: dict[str, Any]) -> str
```

**Parameters**:
- `metrics` (dict): Quality metrics from `calculate_quality_metrics()`

**Returns**: Formatted report string

**Example**:
```python
from rustybt.data.quality import calculate_quality_metrics, generate_quality_report
import polars as pl

data = pl.read_parquet("stocks.parquet")
metrics = calculate_quality_metrics(data)
report = generate_quality_report(metrics)

print(report)
```

---

### Checksum Functions

#### calculate_checksum()

Calculate SHA256 checksum of a file.

**Signature**:
```python
def calculate_checksum(file_path: str | Path) -> str
```

**Parameters**:
- `file_path` (str | Path): File to checksum

**Returns**: 64-character hex string

**Example**:
```python
from rustybt.utils.checksum import calculate_checksum

checksum = calculate_checksum("data.parquet")
print(f"SHA256: {checksum}")
```

---

#### calculate_checksum_multiple()

Calculate combined checksum for multiple files.

**Signature**:
```python
def calculate_checksum_multiple(file_paths: list[str | Path]) -> str
```

**Parameters**:
- `file_paths` (list): Files to checksum

**Returns**: Combined 64-character hex string

**Example**:
```python
from rustybt.utils.checksum import calculate_checksum_multiple
from pathlib import Path

files = [Path("stocks_2023.csv"), Path("stocks_2024.csv")]
checksum = calculate_checksum_multiple(files)
print(f"Combined: {checksum}")
```

---

### Gap Detection Functions

#### detect_missing_days()

Detect missing trading days using calendar.

**Signature**:
```python
def detect_missing_days(
    data: pl.DataFrame,
    calendar: ExchangeCalendar,
    date_column: str = "date"
) -> list[pd.Timestamp]
```

**Parameters**:
- `data` (pl.DataFrame): Data with dates
- `calendar` (ExchangeCalendar): Trading calendar
- `date_column` (str, optional): Date column name

**Returns**: List of missing trading day timestamps

**Example**:
```python
import polars as pl
from rustybt.utils.gap_detection import detect_missing_days
from exchange_calendars import get_calendar

data = pl.read_parquet("stocks.parquet")
calendar = get_calendar("NYSE")

missing_days = detect_missing_days(data, calendar)
print(f"Missing {len(missing_days)} days")
```

---

#### generate_gap_report()

Analyze gaps and generate warnings.

**Signature**:
```python
def generate_gap_report(
    missing_days: list[pd.Timestamp],
    threshold: int = 5
) -> dict[str, Any]
```

**Parameters**:
- `missing_days` (list): Missing day timestamps
- `threshold` (int, optional): Days to trigger warning (default: 5)

**Returns**: Dictionary with gap analysis

**Example**:
```python
from rustybt.utils.gap_detection import generate_gap_report
import pandas as pd

missing_days = [
    pd.Timestamp("2024-01-03"),
    pd.Timestamp("2024-01-04"),
    pd.Timestamp("2024-01-05"),
]

report = generate_gap_report(missing_days, threshold=2)
print(f"Warnings: {report['warnings']}")
```

---

## Best Practices

### 1. Always Track Quality

```python
# Good: Include quality validation
result = tracker.record_bundle_ingestion(
    bundle_name="my-bundle",
    source_type="yfinance",
    data_files=[data_file],
    data=data,  # Enables quality validation
    calendar=calendar
)

# Avoid: Skipping quality validation
result = tracker.record_bundle_ingestion(
    bundle_name="my-bundle",
    source_type="yfinance",
    data_files=[data_file]
    # No data, no quality metrics!
)
```

### 2. Verify Checksums

```python
# Good: Verify data integrity before use
metadata = BundleMetadata.get("my-bundle")
current_checksum = calculate_checksum(data_file)

if current_checksum != metadata['checksum']:
    raise ValueError("Data integrity check failed!")
```

### 3. Use Calendars for Gap Detection

```python
# Good: Provide calendar for accurate gap detection
from exchange_calendars import get_calendar

calendar = get_calendar("NYSE")  # or "24/7" for crypto
metrics = calculate_quality_metrics(data, calendar=calendar)

# Avoid: No calendar means no gap detection
metrics = calculate_quality_metrics(data)  # missing_days_count always 0
```

### 4. Handle Validation Failures

```python
result = tracker.record_bundle_ingestion(...)

quality = result["quality_metrics"]
if not quality["validation_passed"]:
    print(f"⚠️  Quality validation FAILED!")
    print(f"   OHLCV violations: {quality['ohlcv_violations']}")
    print(f"   Outliers: {quality['outlier_count']}")

    # Decide whether to proceed or abort
    if quality['ohlcv_violations'] > 10:
        raise ValueError("Too many OHLCV violations - data may be corrupt")
```

---

## See Also

- [Catalog API Reference](catalog-api.md) - BundleMetadata and BundleMetadataTracker APIs
- [Catalog Architecture](architecture.md) - Database schema and design
- [Bundle System](bundle-system.md) - Bundle lifecycle and ingestion
- [Data Adapters](../adapters/README.md) - Data source adapters
