# CSV Data Import Guide

This guide explains how to import custom data from CSV files using RustyBT's CSVAdapter.

## Overview

The CSVAdapter provides flexible CSV import capabilities with:

- **Schema mapping**: Map custom column names to OHLCV fields
- **Delimiter detection**: Auto-detect comma, tab, semicolon, pipe delimiters
- **Date parsing**: Support for multiple date formats (ISO8601, US, European, epoch)
- **Timezone handling**: Convert timestamps to UTC
- **Missing data strategies**: Skip, interpolate, or fail on missing values
- **Decimal precision**: Financial-grade precision for price data

## Quick Start

### Standard CSV Format

For CSV files with standard column names:

```python
from rustybt.data.adapters import CSVAdapter, CSVConfig, SchemaMapping
import pandas as pd

# Configure CSV adapter
config = CSVConfig(
    file_path="data/ohlcv.csv",
    schema_mapping=SchemaMapping(
        date_column="Date",
        open_column="Open",
        high_column="High",
        low_column="Low",
        close_column="Close",
        volume_column="Volume"
    )
)

# Create adapter and fetch data
adapter = CSVAdapter(config)
df = await adapter.fetch(
    symbols=[],
    start_date=pd.Timestamp('2023-01-01'),
    end_date=pd.Timestamp('2023-12-31'),
    resolution='1d'
)
```

### CSV File Format

```csv
Date,Open,High,Low,Close,Volume
2023-01-01,100.50,101.00,100.00,100.80,1000000
2023-01-02,100.80,102.00,100.50,101.50,1100000
2023-01-03,101.50,103.00,101.00,102.50,1200000
```

## Configuration Options

### Schema Mapping

Map your CSV column names to standard OHLCV fields:

```python
from rustybt.data.adapters import SchemaMapping

# Custom column names
mapping = SchemaMapping(
    date_column="trade_date",      # Your date column name
    open_column="o",                # Your open price column
    high_column="h",                # Your high price column
    low_column="l",                 # Your low price column
    close_column="c",               # Your close price column
    volume_column="vol",            # Your volume column
    symbol_column="ticker"          # Optional: symbol/ticker column
)
```

**Notes:**
- Column matching is case-insensitive
- All columns except `symbol_column` are required
- If no symbol column exists, data is labeled as "CSV_DATA"

### Date Formats

The adapter supports multiple date formats:

**ISO8601 (Recommended):**
```python
config = CSVConfig(
    file_path="data/ohlcv.csv",
    schema_mapping=SchemaMapping(),
    date_format="%Y-%m-%d"  # 2023-01-15
)
```

**ISO8601 with Time:**
```python
config = CSVConfig(
    file_path="data/ohlcv.csv",
    schema_mapping=SchemaMapping(),
    date_format="%Y-%m-%d %H:%M:%S"  # 2023-01-15 10:30:00
)
```

**US Format:**
```python
config = CSVConfig(
    file_path="data/ohlcv.csv",
    schema_mapping=SchemaMapping(),
    date_format="%m/%d/%Y"  # 01/15/2023
)
```

**European Format:**
```python
config = CSVConfig(
    file_path="data/ohlcv.csv",
    schema_mapping=SchemaMapping(),
    date_format="%d/%m/%Y"  # 15/01/2023
)
```

**Unix Epoch (Auto-detected):**
```python
config = CSVConfig(
    file_path="data/ohlcv.csv",
    schema_mapping=SchemaMapping(),
    date_format=None  # Auto-detect epoch timestamps
)
```

CSV with epoch timestamps:
```csv
timestamp,open,high,low,close,volume
1672531200,100.50,101.00,100.00,100.80,1000000
1672617600,100.80,102.00,100.50,101.50,1100000
```

**Auto-Detection:**
```python
config = CSVConfig(
    file_path="data/ohlcv.csv",
    schema_mapping=SchemaMapping(),
    date_format=None  # Try to auto-detect format
)
```

The adapter will try common formats in this order:
1. ISO8601 date (`%Y-%m-%d`)
2. ISO8601 datetime (`%Y-%m-%d %H:%M:%S`)
3. US format (`%m/%d/%Y`)
4. European format (`%d/%m/%Y`)
5. Unix epoch (seconds)
6. Unix epoch (milliseconds)

### Delimiter Options

**Auto-Detection (Recommended):**
```python
config = CSVConfig(
    file_path="data/ohlcv.csv",
    schema_mapping=SchemaMapping(),
    delimiter=None  # Auto-detect delimiter
)
```

**Explicit Delimiter:**
```python
# Comma
config = CSVConfig(..., delimiter=",")

# Tab
config = CSVConfig(..., delimiter="\t")

# Semicolon
config = CSVConfig(..., delimiter=";")

# Pipe
config = CSVConfig(..., delimiter="|")
```

### Timezone Handling

Convert timestamps from source timezone to UTC:

```python
config = CSVConfig(
    file_path="data/ohlcv.csv",
    schema_mapping=SchemaMapping(),
    timezone="America/New_York"  # Source timezone
)
```

**Supported Timezones:**
- Any valid pytz timezone name
- `"UTC"` for timestamps already in UTC
- `"America/New_York"` for US Eastern Time
- `"Europe/London"` for UK time
- `"Asia/Tokyo"` for Japan time
- See [pytz documentation](https://pythonhosted.org/pytz/) for full list

**Behavior:**
- All timestamps are converted to UTC internally
- If timezone is `"UTC"`, no conversion is performed
- Timezone-naive timestamps are assumed to be in the specified timezone

### Missing Data Strategies

Handle missing values in your CSV:

**Fail (Default):**
```python
config = CSVConfig(
    file_path="data/ohlcv.csv",
    schema_mapping=SchemaMapping(),
    missing_data_strategy="fail"  # Raise error if missing values detected
)
```

**Skip:**
```python
config = CSVConfig(
    file_path="data/ohlcv.csv",
    schema_mapping=SchemaMapping(),
    missing_data_strategy="skip"  # Remove rows with missing values
)
```

**Interpolate:**
```python
config = CSVConfig(
    file_path="data/ohlcv.csv",
    schema_mapping=SchemaMapping(),
    missing_data_strategy="interpolate"  # Forward-fill missing values
)
```

**Strategy Comparison:**

| Strategy | Behavior | Use Case |
|----------|----------|----------|
| `fail` | Raises `InvalidDataError` | Production (ensure data quality) |
| `skip` | Removes incomplete rows | Minor missing data acceptable |
| `interpolate` | Forward-fills missing values | Preserve time series continuity |

### Header Row Handling

**With Headers (Default):**
```python
config = CSVConfig(
    file_path="data/ohlcv.csv",
    schema_mapping=SchemaMapping(),
    has_header=True
)
```

**Without Headers:**
```python
# Use column indices as names
config = CSVConfig(
    file_path="data/no_headers.csv",
    schema_mapping=SchemaMapping(
        date_column="column_1",
        open_column="column_2",
        high_column="column_3",
        low_column="column_4",
        close_column="column_5",
        volume_column="column_6"
    ),
    has_header=False
)
```

## Example Configurations

### Example 1: Standard CSV with Headers

**CSV File:**
```csv
Date,Open,High,Low,Close,Volume
2023-01-01,100.50,101.00,100.00,100.80,1000000
2023-01-02,100.80,102.00,100.50,101.50,1100000
```

**Configuration:**
```python
config = CSVConfig(
    file_path="data/standard.csv",
    schema_mapping=SchemaMapping(
        date_column="Date",
        open_column="Open",
        high_column="High",
        low_column="Low",
        close_column="Close",
        volume_column="Volume"
    ),
    delimiter=",",
    has_header=True,
    date_format="%Y-%m-%d",
    timezone="UTC"
)
```

### Example 2: Custom Format with Multiple Symbols

**CSV File:**
```csv
trade_date|ticker|o|h|l|c|vol
01/01/2023|AAPL|100.50|101.00|100.00|100.80|1000000
01/02/2023|AAPL|100.80|102.00|100.50|101.50|1100000
01/01/2023|MSFT|200.50|201.00|200.00|200.80|2000000
01/02/2023|MSFT|200.80|202.00|200.50|201.50|2100000
```

**Configuration:**
```python
config = CSVConfig(
    file_path="data/custom.csv",
    schema_mapping=SchemaMapping(
        date_column="trade_date",
        open_column="o",
        high_column="h",
        low_column="l",
        close_column="c",
        volume_column="vol",
        symbol_column="ticker"
    ),
    delimiter="|",
    has_header=True,
    date_format="%m/%d/%Y",
    timezone="America/New_York"
)

# Fetch specific symbols
adapter = CSVAdapter(config)
df = await adapter.fetch(
    symbols=["AAPL"],  # Filter for AAPL only
    start_date=pd.Timestamp('2023-01-01'),
    end_date=pd.Timestamp('2023-01-31'),
    resolution='1d'
)
```

### Example 3: No Headers with Epoch Timestamps

**CSV File:**
```csv
1672531200,100.50,101.00,100.00,100.80,1000000
1672617600,100.80,102.00,100.50,101.50,1100000
1672704000,101.50,103.00,101.00,102.50,1200000
```

**Configuration:**
```python
config = CSVConfig(
    file_path="data/no_headers.csv",
    schema_mapping=SchemaMapping(
        date_column="column_1",
        open_column="column_2",
        high_column="column_3",
        low_column="column_4",
        close_column="column_5",
        volume_column="column_6"
    ),
    delimiter=",",
    has_header=False,
    date_format=None,  # Auto-detect epoch
    timezone="UTC",
    missing_data_strategy="skip"
)
```

### Example 4: Tab-Delimited with Time Series Gaps

**CSV File:**
```
Date	Open	High	Low	Close	Volume
2023-01-01	100.50	101.00	100.00	100.80	1000000
2023-01-02
2023-01-03	101.50	103.00	101.00	102.50	1200000
```

**Configuration:**
```python
config = CSVConfig(
    file_path="data/gaps.csv",
    schema_mapping=SchemaMapping(),
    delimiter="\t",
    has_header=True,
    date_format="%Y-%m-%d",
    timezone="UTC",
    missing_data_strategy="skip"  # Remove incomplete rows
)
```

## Data Validation

The CSVAdapter automatically validates data quality:

**OHLCV Relationship Checks:**
- High >= Low
- High >= Open
- High >= Close
- Low <= Open
- Low <= Close

**Data Quality Checks:**
- No NULL values in required columns (after missing data handling)
- Timestamps are sorted chronologically
- No duplicate timestamps per symbol

**Example Error Handling:**
```python
from rustybt.data.adapters.base import ValidationError, InvalidDataError

try:
    df = await adapter.fetch(
        symbols=[],
        start_date=pd.Timestamp('2023-01-01'),
        end_date=pd.Timestamp('2023-12-31'),
        resolution='1d'
    )
except ValidationError as e:
    print(f"Data validation failed: {e}")
    if e.invalid_rows is not None:
        print(f"Invalid rows:\n{e.invalid_rows}")
except InvalidDataError as e:
    print(f"CSV format error: {e}")
```

## Performance Tips

1. **Use Explicit Configuration**: Disable auto-detection by specifying delimiter and date_format
2. **Filter Date Range**: Narrow date range to only needed data
3. **Filter Symbols**: If CSV contains multiple symbols, filter to specific ones
4. **Optimize CSV Structure**: Sort by timestamp, remove unnecessary columns
5. **Use Parquet for Large Datasets**: Convert CSV to Parquet for better performance

## Sample Files

Example CSV files are provided in `examples/data/`:

- `sample_ohlcv.csv` - Standard format with comma delimiter
- `sample_ohlcv_tab.csv` - Tab-delimited format
- `sample_ohlcv_no_headers.csv` - No headers with epoch timestamps
- `sample_ohlcv_custom_format.csv` - Custom column names with pipe delimiter

## Troubleshooting

### Missing Required Columns

**Error:** `InvalidDataError: Missing required columns in CSV`

**Solution:** Verify column names match schema mapping (case-insensitive)

### Date Parsing Failed

**Error:** `InvalidDataError: Failed to auto-detect date format`

**Solution:** Specify `date_format` explicitly

### Invalid OHLCV Relationships

**Error:** `ValidationError: Invalid OHLCV relationships in X rows`

**Solution:** Check data quality - high must be >= low, etc.

### Timezone Conversion Failed

**Warning:** `timezone_conversion_failed, assuming_utc=True`

**Solution:** Verify timezone name is valid pytz timezone

## Integration with Data Catalog

Use CSVAdapter with the data catalog for caching:

```python
from rustybt.data.catalog import DataCatalog
from rustybt.data.adapters import CSVAdapter, CSVConfig, SchemaMapping

# Create adapter
csv_config = CSVConfig(
    file_path="data/custom.csv",
    schema_mapping=SchemaMapping(...)
)
csv_adapter = CSVAdapter(csv_config)

# Register with catalog
catalog = DataCatalog(cache_dir=".cache/data")
catalog.register_adapter("custom_data", csv_adapter)

# Fetch with caching
df = await catalog.get_data(
    adapter_name="custom_data",
    symbols=["AAPL"],
    start_date=pd.Timestamp('2023-01-01'),
    end_date=pd.Timestamp('2023-12-31'),
    resolution='1d'
)
```

## See Also

- [Creating Data Adapters](creating-data-adapters.md)
- [Caching System](caching-system.md)
