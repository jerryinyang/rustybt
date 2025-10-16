# CSV Adapter - Custom Data Import

**Module**: `rustybt.data.adapters.csv_adapter`

## Overview

`CSVAdapter` provides flexible CSV import capabilities for custom market data. Load historical data from CSV files with automatic schema mapping, delimiter detection, date parsing, timezone conversion, and missing data handling. Perfect for backtesting with proprietary data sources, research datasets, or data from third-party providers.

## Key Features

- **Flexible Schema Mapping**: Map any column names to standard OHLCV fields
- **Auto-Detection**: Automatic delimiter and date format detection
- **Timezone Handling**: Convert timestamps from any timezone to UTC
- **Missing Data Strategies**: Skip, interpolate, or fail on missing values
- **Financial Precision**: Automatic Decimal conversion for accurate calculations
- **Case-Insensitive**: Works with any column name casing
- **File Integrity**: SHA256 checksum computation for data validation

## Classes

### SchemaMapping

Configuration for mapping CSV columns to standard OHLCV schema.

```python
from dataclasses import dataclass

@dataclass
class SchemaMapping:
    """Configuration for CSV schema mapping."""

    date_column: str = "timestamp"
    open_column: str = "open"
    high_column: str = "high"
    low_column: str = "low"
    close_column: str = "close"
    volume_column: str = "volume"
    symbol_column: str | None = None
```

### CSVConfig

Comprehensive configuration for CSV import.

```python
from dataclasses import dataclass

@dataclass
class CSVConfig:
    """Configuration for CSV parsing."""

    file_path: str
    schema_mapping: SchemaMapping
    delimiter: str | None = None  # Auto-detect if None
    has_header: bool = True
    date_format: str | None = None  # Auto-detect if None
    timezone: str = "UTC"
    missing_data_strategy: str = "fail"  # 'skip', 'interpolate', 'fail'
```

## Class Definition

```python
from rustybt.data.adapters.csv_adapter import CSVAdapter

class CSVAdapter(BaseDataAdapter, DataSource):
    """CSV adapter for importing custom data files."""
```

## Constructor

```python
def __init__(self, config: CSVConfig) -> None:
```

### Parameters

- **config** (`CSVConfig`): Complete CSV configuration including schema mapping and parsing options

### Example

```python
from rustybt.data.adapters.csv_adapter import CSVAdapter, CSVConfig, SchemaMapping

# Basic configuration with standard column names
config_basic = CSVConfig(
    file_path="data/market_data.csv",
    schema_mapping=SchemaMapping()  # Uses defaults
)

adapter_basic = CSVAdapter(config_basic)
print(f"✅ Created CSV adapter for: {config_basic.file_path}")

# Custom schema mapping
config_custom = CSVConfig(
    file_path="data/custom_format.csv",
    schema_mapping=SchemaMapping(
        date_column="Date",
        open_column="Open",
        high_column="High",
        low_column="Low",
        close_column="Close",
        volume_column="Volume",
        symbol_column="Ticker"
    ),
    delimiter=",",
    date_format="%Y-%m-%d",
    timezone="America/New_York"
)

adapter_custom = CSVAdapter(config_custom)
print(f"✅ Created CSV adapter with custom schema")
```

## Supported Delimiters

The CSV adapter auto-detects common delimiters:

```python
# Comma-separated (most common)
# Date,Open,High,Low,Close,Volume
# 2024-01-01,100.0,102.0,99.0,101.5,1000000

# Tab-separated
# Date	Open	High	Low	Close	Volume
# 2024-01-01	100.0	102.0	99.0	101.5	1000000

# Semicolon-separated (European format)
# Date;Open;High;Low;Close;Volume
# 2024-01-01;100,0;102,0;99,0;101,5;1000000

# Pipe-separated
# Date|Open|High|Low|Close|Volume
# 2024-01-01|100.0|102.0|99.0|101.5|1000000

print("✅ Auto-detects: comma, tab, semicolon, pipe delimiters")
```

## Supported Date Formats

The CSV adapter auto-detects multiple date formats:

```python
# ISO 8601 date
# 2024-01-01

# ISO 8601 datetime
# 2024-01-01 09:30:00

# US format
# 01/15/2024

# European format
# 15/01/2024

# Unix epoch (seconds)
# 1704096000

# Unix epoch (milliseconds)
# 1704096000000

print("✅ Auto-detects: ISO8601, US/European formats, Unix epoch")
```

## Methods

### fetch()

```python
async def fetch(
    self,
    symbols: list[str],
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    resolution: str,
) -> pl.DataFrame:
```

Read OHLCV data from CSV file with filtering and validation.

**Parameters**:
- **symbols** (`list[str]`): List of symbols to filter (requires symbol column in CSV)
- **start_date** (`pd.Timestamp`): Start date for data range
- **end_date** (`pd.Timestamp`): End date for data range
- **resolution** (`str`): Not used for CSV (data resolution determined by file content)

**Returns**:
- `pl.DataFrame`: Polars DataFrame with standardized OHLCV schema

**Raises**:
- `InvalidDataError`: If CSV format is invalid or missing required columns

**Example**:

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.csv_adapter import CSVAdapter, CSVConfig, SchemaMapping

async def fetch_csv_data():
    # Configure adapter
    config = CSVConfig(
        file_path="docs/examples/data/sample_ohlcv.csv",
        schema_mapping=SchemaMapping(
            date_column="Date",
            open_column="Open",
            high_column="High",
            low_column="Low",
            close_column="Close",
            volume_column="Volume"
        ),
        delimiter=",",
        date_format="%Y-%m-%d",
        timezone="UTC"
    )

    adapter = CSVAdapter(config)

    # Fetch all data in date range
    data = await adapter.fetch(
        symbols=[],  # Empty list = all symbols
        start_date=pd.Timestamp("2024-01-01"),
        end_date=pd.Timestamp("2024-12-31"),
        resolution="1d"
    )

    print(f"✅ Loaded {len(data)} rows from CSV")
    print(f"Date range: {data['timestamp'].min()} to {data['timestamp'].max()}")
    print(f"\nFirst few rows:")
    print(data.head())

    return data

# Run
data = asyncio.run(fetch_csv_data())
```

### get_metadata()

```python
def get_metadata(self) -> DataSourceMetadata:
```

Get CSV file metadata including checksum for integrity verification.

**Returns**:
- `DataSourceMetadata`: Metadata object with file information

**Example**:

```python
from rustybt.data.adapters.csv_adapter import CSVAdapter, CSVConfig, SchemaMapping

# Create adapter
config = CSVConfig(
    file_path="docs/examples/data/sample_ohlcv.csv",
    schema_mapping=SchemaMapping()
)

adapter = CSVAdapter(config)
metadata = adapter.get_metadata()

print(f"✅ Source type: {metadata.source_type}")
print(f"File path: {metadata.source_url}")
print(f"Supports live: {metadata.supports_live}")
print(f"File size: {metadata.additional_info.get('file_size_bytes')} bytes")
print(f"Checksum: {metadata.additional_info.get('checksum_sha256')[:16]}...")
print(f"Delimiter: {metadata.additional_info.get('delimiter')}")
print(f"Timezone: {metadata.additional_info.get('timezone')}")
```

## Common Usage Patterns

### Basic CSV Import

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.csv_adapter import CSVAdapter, CSVConfig, SchemaMapping

async def basic_import():
    # Standard column names - no mapping needed
    config = CSVConfig(
        file_path="docs/examples/data/sample_ohlcv.csv",
        schema_mapping=SchemaMapping(
            date_column="timestamp",
            open_column="open",
            high_column="high",
            low_column="low",
            close_column="close",
            volume_column="volume"
        )
    )

    adapter = CSVAdapter(config)

    data = await adapter.fetch(
        symbols=[],
        start_date=pd.Timestamp("2020-01-01"),
        end_date=pd.Timestamp("2024-12-31"),
        resolution="1d"
    )

    print(f"✅ Imported {len(data)} rows")
    return data

# Run
data = asyncio.run(basic_import())
```

### Custom Column Names

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.csv_adapter import CSVAdapter, CSVConfig, SchemaMapping

async def custom_columns():
    # Map custom column names to standard schema
    config = CSVConfig(
        file_path="docs/examples/data/custom_format.csv",
        schema_mapping=SchemaMapping(
            date_column="Trading_Date",
            open_column="Opening_Price",
            high_column="High_Price",
            low_column="Low_Price",
            close_column="Closing_Price",
            volume_column="Total_Volume",
            symbol_column="Stock_Symbol"
        )
    )

    adapter = CSVAdapter(config)

    data = await adapter.fetch(
        symbols=[],
        start_date=pd.Timestamp("2024-01-01"),
        end_date=pd.Timestamp("2024-12-31"),
        resolution="1d"
    )

    print(f"✅ Imported {len(data)} rows with custom column mapping")
    return data

# Run
data = asyncio.run(custom_columns())
```

### Auto-Detection Mode

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.csv_adapter import CSVAdapter, CSVConfig, SchemaMapping

async def auto_detection():
    # Let adapter auto-detect delimiter and date format
    config = CSVConfig(
        file_path="docs/examples/data/unknown_format.csv",
        schema_mapping=SchemaMapping(
            date_column="Date",
            open_column="Open",
            high_column="High",
            low_column="Low",
            close_column="Close",
            volume_column="Volume"
        ),
        delimiter=None,  # Auto-detect
        date_format=None  # Auto-detect
    )

    adapter = CSVAdapter(config)

    data = await adapter.fetch(
        symbols=[],
        start_date=pd.Timestamp("2024-01-01"),
        end_date=pd.Timestamp("2024-12-31"),
        resolution="1d"
    )

    print(f"✅ Auto-detected format and imported {len(data)} rows")
    return data

# Run
data = asyncio.run(auto_detection())
```

### Timezone Conversion

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.csv_adapter import CSVAdapter, CSVConfig, SchemaMapping

async def timezone_conversion():
    # Convert from Eastern Time to UTC
    config = CSVConfig(
        file_path="docs/examples/data/et_timestamps.csv",
        schema_mapping=SchemaMapping(
            date_column="Date",
            open_column="Open",
            high_column="High",
            low_column="Low",
            close_column="Close",
            volume_column="Volume"
        ),
        timezone="America/New_York"  # Source timezone
    )

    adapter = CSVAdapter(config)

    data = await adapter.fetch(
        symbols=[],
        start_date=pd.Timestamp("2024-01-01"),
        end_date=pd.Timestamp("2024-12-31"),
        resolution="1d"
    )

    print(f"✅ Converted {len(data)} rows from ET to UTC")
    print(f"All timestamps now in UTC: {data['timestamp'].dtype}")
    return data

# Run
data = asyncio.run(timezone_conversion())
```

### Multi-Symbol CSV

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.csv_adapter import CSVAdapter, CSVConfig, SchemaMapping

async def multi_symbol_import():
    # CSV with symbol column
    config = CSVConfig(
        file_path="docs/examples/data/multi_symbol.csv",
        schema_mapping=SchemaMapping(
            date_column="Date",
            open_column="Open",
            high_column="High",
            low_column="Low",
            close_column="Close",
            volume_column="Volume",
            symbol_column="Symbol"  # Enable symbol filtering
        )
    )

    adapter = CSVAdapter(config)

    # Fetch specific symbols
    data = await adapter.fetch(
        symbols=["AAPL", "MSFT"],  # Filter to these symbols
        start_date=pd.Timestamp("2024-01-01"),
        end_date=pd.Timestamp("2024-12-31"),
        resolution="1d"
    )

    print(f"✅ Imported {len(data)} rows")
    print(f"Symbols: {data['symbol'].unique().to_list()}")

    # Count rows per symbol
    for symbol in ["AAPL", "MSFT"]:
        symbol_data = data.filter(pl.col("symbol") == symbol)
        print(f"{symbol}: {len(symbol_data)} rows")

    return data

# Run
import polars as pl
data = asyncio.run(multi_symbol_import())
```

## Missing Data Strategies

The CSV adapter provides three strategies for handling missing values:

### Strategy: fail (default)

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.csv_adapter import CSVAdapter, CSVConfig, SchemaMapping
from rustybt.data.adapters.base import InvalidDataError

async def strategy_fail():
    config = CSVConfig(
        file_path="docs/examples/data/with_nulls.csv",
        schema_mapping=SchemaMapping(),
        missing_data_strategy="fail"  # Raise error on missing values
    )

    adapter = CSVAdapter(config)

    try:
        data = await adapter.fetch(
            symbols=[],
            start_date=pd.Timestamp("2024-01-01"),
            end_date=pd.Timestamp("2024-12-31"),
            resolution="1d"
        )
    except InvalidDataError as e:
        print(f"✅ Error raised as expected: {e}")
        return None

# Run
asyncio.run(strategy_fail())
```

### Strategy: skip

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.csv_adapter import CSVAdapter, CSVConfig, SchemaMapping

async def strategy_skip():
    # Skip rows with any missing values
    config = CSVConfig(
        file_path="docs/examples/data/with_nulls.csv",
        schema_mapping=SchemaMapping(),
        missing_data_strategy="skip"  # Remove incomplete rows
    )

    adapter = CSVAdapter(config)

    data = await adapter.fetch(
        symbols=[],
        start_date=pd.Timestamp("2024-01-01"),
        end_date=pd.Timestamp("2024-12-31"),
        resolution="1d"
    )

    print(f"✅ Imported {len(data)} rows (incomplete rows removed)")
    print(f"No nulls remaining: {data.null_count().to_dicts()[0]}")
    return data

# Run
data = asyncio.run(strategy_skip())
```

### Strategy: interpolate

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.csv_adapter import CSVAdapter, CSVConfig, SchemaMapping

async def strategy_interpolate():
    # Forward-fill missing values
    config = CSVConfig(
        file_path="docs/examples/data/with_nulls.csv",
        schema_mapping=SchemaMapping(),
        missing_data_strategy="interpolate"  # Forward-fill missing values
    )

    adapter = CSVAdapter(config)

    data = await adapter.fetch(
        symbols=[],
        start_date=pd.Timestamp("2024-01-01"),
        end_date=pd.Timestamp("2024-12-31"),
        resolution="1d"
    )

    print(f"✅ Imported {len(data)} rows (missing values forward-filled)")
    print(f"Null counts after interpolation: {data.null_count().to_dicts()[0]}")
    return data

# Run
data = asyncio.run(strategy_interpolate())
```

## CSV Format Examples

### Standard Format (Recommended)

```csv
timestamp,symbol,open,high,low,close,volume
2024-01-01,AAPL,185.50,187.20,185.10,186.80,45000000
2024-01-02,AAPL,186.90,188.50,186.40,187.95,52000000
2024-01-03,AAPL,187.80,189.30,187.20,188.75,48000000
```

### Custom Column Names

```csv
Date,Ticker,Opening_Price,High_Price,Low_Price,Closing_Price,Total_Volume
2024-01-01,AAPL,185.50,187.20,185.10,186.80,45000000
2024-01-02,AAPL,186.90,188.50,186.40,187.95,52000000
2024-01-03,AAPL,187.80,189.30,187.20,188.75,48000000
```

### Tab-Separated Format

```
Date	Open	High	Low	Close	Volume
2024-01-01	185.50	187.20	185.10	186.80	45000000
2024-01-02	186.90	188.50	186.40	187.95	52000000
2024-01-03	187.80	189.30	187.20	188.75	48000000
```

### European Format (Semicolon)

```csv
Date;Open;High;Low;Close;Volume
2024-01-01;185,50;187,20;185,10;186,80;45000000
2024-01-02;186,90;188,50;186,40;187,95;52000000
2024-01-03;187,80;189,30;187,20;188,75;48000000
```

## Error Handling

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.csv_adapter import CSVAdapter, CSVConfig, SchemaMapping
from rustybt.data.adapters.base import InvalidDataError

async def handle_errors():
    # Missing required columns
    try:
        config = CSVConfig(
            file_path="docs/examples/data/incomplete.csv",
            schema_mapping=SchemaMapping(
                date_column="Date",
                open_column="Open",
                high_column="High",
                low_column="Low_Price",  # Wrong column name
                close_column="Close",
                volume_column="Volume"
            )
        )
        adapter = CSVAdapter(config)
        data = await adapter.fetch([], pd.Timestamp("2024-01-01"), pd.Timestamp("2024-12-31"), "1d")
    except InvalidDataError as e:
        print(f"✅ Caught missing column error: {e}")

    # Invalid date format
    try:
        config = CSVConfig(
            file_path="docs/examples/data/bad_dates.csv",
            schema_mapping=SchemaMapping(),
            date_format="%Y-%m-%d"  # Wrong format for file
        )
        adapter = CSVAdapter(config)
        data = await adapter.fetch([], pd.Timestamp("2024-01-01"), pd.Timestamp("2024-12-31"), "1d")
    except InvalidDataError as e:
        print(f"✅ Caught date parsing error: {e}")

    # File not found
    try:
        config = CSVConfig(
            file_path="nonexistent.csv",
            schema_mapping=SchemaMapping()
        )
        adapter = CSVAdapter(config)
        data = await adapter.fetch([], pd.Timestamp("2024-01-01"), pd.Timestamp("2024-12-31"), "1d")
    except InvalidDataError as e:
        print(f"✅ Caught file not found error: {e}")

    print("✅ Error handling demonstrated")

# Run
asyncio.run(handle_errors())
```

## Data Validation

All CSV data is automatically validated:

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.csv_adapter import CSVAdapter, CSVConfig, SchemaMapping

async def validate_csv_data():
    config = CSVConfig(
        file_path="docs/examples/data/sample_ohlcv.csv",
        schema_mapping=SchemaMapping(
            date_column="Date",
            open_column="Open",
            high_column="High",
            low_column="Low",
            close_column="Close",
            volume_column="Volume"
        )
    )

    adapter = CSVAdapter(config)

    # Data is automatically validated
    data = await adapter.fetch(
        symbols=[],
        start_date=pd.Timestamp("2024-01-01"),
        end_date=pd.Timestamp("2024-12-31"),
        resolution="1d"
    )

    print(f"✅ Data passed OHLCV validation")
    print(f"✅ High >= Low: {(data['high'] >= data['low']).all()}")
    print(f"✅ High >= Open: {(data['high'] >= data['open']).all()}")
    print(f"✅ High >= Close: {(data['high'] >= data['close']).all()}")
    print(f"✅ Low <= Open: {(data['low'] <= data['open']).all()}")
    print(f"✅ Low <= Close: {(data['low'] <= data['close']).all()}")

    return data

# Run
data = asyncio.run(validate_csv_data())
```

## Common Issues and Troubleshooting

### Issue: Column Not Found

**Problem**: `InvalidDataError: Missing required columns in CSV: {'low'}`

**Solution**: Check column names match schema mapping. Column matching is case-insensitive:

```python
from rustybt.data.adapters.csv_adapter import CSVConfig, SchemaMapping

# ❌ Wrong: Column name doesn't match
# config = CSVConfig(
#     file_path="data.csv",
#     schema_mapping=SchemaMapping(
#         low_column="Low_Price"  # Column is actually called "low"
#     )
# )

# ✅ Correct: Match actual column names
config = CSVConfig(
    file_path="data.csv",
    schema_mapping=SchemaMapping(
        date_column="Date",
        open_column="Open",
        high_column="High",
        low_column="Low",  # Matches CSV column
        close_column="Close",
        volume_column="Volume"
    )
)

print("✅ Always verify CSV column names before configuring schema")
```

### Issue: Date Parsing Failed

**Problem**: `InvalidDataError: Failed to auto-detect date format`

**Solution**: Specify date format explicitly:

```python
from rustybt.data.adapters.csv_adapter import CSVConfig, SchemaMapping

# ❌ Wrong: Let auto-detection fail on unusual format
# config = CSVConfig(
#     file_path="data.csv",
#     schema_mapping=SchemaMapping(),
#     date_format=None  # Auto-detect may fail on custom formats
# )

# ✅ Correct: Specify custom date format
config = CSVConfig(
    file_path="data.csv",
    schema_mapping=SchemaMapping(),
    date_format="%d-%b-%Y"  # e.g., "15-Jan-2024"
)

print("✅ Specify date format for non-standard date strings")
```

### Issue: Wrong Timezone

**Problem**: Timestamps are 5 hours off from expected values

**Solution**: Specify source timezone for conversion to UTC:

```python
from rustybt.data.adapters.csv_adapter import CSVConfig, SchemaMapping

# ❌ Wrong: Assumes UTC but data is in ET
# config = CSVConfig(
#     file_path="data.csv",
#     schema_mapping=SchemaMapping(),
#     timezone="UTC"  # Wrong if data is in Eastern Time
# )

# ✅ Correct: Specify source timezone
config = CSVConfig(
    file_path="data.csv",
    schema_mapping=SchemaMapping(),
    timezone="America/New_York"  # Data will be converted to UTC
)

print("✅ All timestamps stored in UTC internally")
```

### Issue: Decimal Precision Loss

**Problem**: Prices have rounding errors

**Solution**: The adapter automatically handles this by converting through strings:

```python
# The adapter does this internally:
# df = df.with_columns([
#     pl.col("open").cast(pl.Utf8).str.to_decimal(scale=8).alias("open"),
#     ...
# ])

print("✅ CSV adapter preserves full decimal precision automatically")
```

### Issue: Missing Data Causing Errors

**Problem**: `InvalidDataError: Missing values detected in CSV`

**Solution**: Choose appropriate missing data strategy:

```python
from rustybt.data.adapters.csv_adapter import CSVConfig, SchemaMapping

# For clean data - fail on any missing values (default)
config_strict = CSVConfig(
    file_path="data.csv",
    schema_mapping=SchemaMapping(),
    missing_data_strategy="fail"
)

# For data with occasional gaps - forward-fill
config_interpolate = CSVConfig(
    file_path="data.csv",
    schema_mapping=SchemaMapping(),
    missing_data_strategy="interpolate"
)

# For data with many gaps - remove incomplete rows
config_skip = CSVConfig(
    file_path="data.csv",
    schema_mapping=SchemaMapping(),
    missing_data_strategy="skip"
)

print("✅ Choose strategy based on data quality and requirements")
```

## Best Practices

### 1. Use Standard Column Names

```python
# ✅ DO: Use standard names in your CSV files
# timestamp,symbol,open,high,low,close,volume

# ❌ AVOID: Non-standard names require extra configuration
# Date,Ticker,O,H,L,C,V

print("✅ Standard column names simplify configuration")
```

### 2. Include Headers

```python
from rustybt.data.adapters.csv_adapter import CSVConfig, SchemaMapping

# ✅ DO: Always include header row
config = CSVConfig(
    file_path="data.csv",
    schema_mapping=SchemaMapping(),
    has_header=True  # Default
)

print("✅ Headers improve readability and reduce errors")
```

### 3. Use ISO 8601 Dates

```python
# ✅ DO: Use ISO 8601 format (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)
# 2024-01-01,AAPL,185.50,187.20,185.10,186.80,45000000

# ❌ AVOID: Ambiguous formats (01/02/2024 - US or European?)
# 01/02/2024,AAPL,185.50,187.20,185.10,186.80,45000000

print("✅ ISO 8601 dates are unambiguous and auto-detected")
```

### 4. Store Timestamps in UTC

```python
# ✅ DO: Store timestamps in UTC in your CSV files
# Specify source timezone only if data is NOT in UTC

from rustybt.data.adapters.csv_adapter import CSVConfig, SchemaMapping

config = CSVConfig(
    file_path="data.csv",
    schema_mapping=SchemaMapping(),
    timezone="UTC"  # Data already in UTC
)

print("✅ UTC timestamps avoid timezone confusion")
```

### 5. Validate Data Before Import

```python
# ✅ DO: Check CSV file before importing
# - Required columns present
# - Date format consistent
# - No duplicate timestamps
# - OHLCV relationships valid (High >= Low, etc.)

print("✅ Validate CSV structure before creating adapter")
```

## Performance Considerations

### Memory-Efficient Import

```python
import asyncio
import pandas as pd
from rustybt.data.adapters.csv_adapter import CSVAdapter, CSVConfig, SchemaMapping

async def memory_efficient():
    config = CSVConfig(
        file_path="large_dataset.csv",
        schema_mapping=SchemaMapping()
    )

    adapter = CSVAdapter(config)

    # Import in date range chunks for large files
    chunks = []

    for year in [2020, 2021, 2022, 2023, 2024]:
        chunk = await adapter.fetch(
            symbols=[],
            start_date=pd.Timestamp(f"{year}-01-01"),
            end_date=pd.Timestamp(f"{year}-12-31"),
            resolution="1d"
        )
        chunks.append(chunk)
        print(f"✅ Loaded {year}: {len(chunk)} rows")

    # Combine chunks if needed
    import polars as pl
    full_data = pl.concat(chunks)
    print(f"✅ Total: {len(full_data)} rows")

    return full_data

# Run
data = asyncio.run(memory_efficient())
```

### File Integrity Checking

```python
from rustybt.data.adapters.csv_adapter import CSVAdapter, CSVConfig, SchemaMapping

# Compute file checksum for integrity verification
config = CSVConfig(
    file_path="docs/examples/data/sample_ohlcv.csv",
    schema_mapping=SchemaMapping()
)

adapter = CSVAdapter(config)
metadata = adapter.get_metadata()

checksum = metadata.additional_info.get("checksum_sha256")
print(f"✅ File checksum: {checksum}")
print(f"Use checksum to verify file hasn't been modified")

# Store checksum for later verification
# Later, recompute and compare to detect file changes
```

## See Also

- [Base Adapter Framework](./base-adapter.md) - Core adapter interface
- [CCXT Adapter](./ccxt-adapter.md) - Cryptocurrency exchange data
- [YFinance Adapter](./yfinance-adapter.md) - Stock and ETF data
- [Data Catalog](../catalog/README.md) - Bundle metadata management
- [Data Readers](../readers/README.md) - Efficient data access
