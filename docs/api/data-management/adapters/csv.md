# CSV Adapter

The CSV adapter provides flexible import capabilities for custom data files with schema mapping, automatic delimiter detection, and comprehensive validation.

## Overview

**Best for**: Custom datasets, proprietary data, one-time imports, backtesting with external data

**Features**:
- Flexible schema mapping
- Automatic delimiter detection
- Date format auto-detection
- Missing data handling strategies
- Multi-file batch import
- Symbol extraction from filenames or columns

## Quick Start

```python
from rustybt.data.adapters import CSVAdapter
from rustybt.data.adapters.csv_adapter import CSVConfig, SchemaMapping
import pandas as pd

# Basic import with default schema
adapter = CSVAdapter()

config = CSVConfig(
    file_path='/path/to/data.csv',
    schema_mapping=SchemaMapping(
        date_column='date',
        open_column='open',
        high_column='high',
        low_column='low',
        close_column='close',
        volume_column='volume'
    )
)

df = await adapter.load_csv(config)
print(df.head())
```

## Schema Mapping

### Default Schema

```python
from rustybt.data.adapters.csv_adapter import SchemaMapping

# Default mapping (case-insensitive)
schema = SchemaMapping(
    date_column='timestamp',    # or 'date', 'datetime', 'time'
    open_column='open',
    high_column='high',
    low_column='low',
    close_column='close',
    volume_column='volume',
    symbol_column=None          # Optional: extract from filename
)
```

### Custom Schema Mapping

```python
# Map non-standard column names
custom_schema = SchemaMapping(
    date_column='Date',
    open_column='Open Price',
    high_column='High Price',
    low_column='Low Price',
    close_column='Close Price',
    volume_column='Volume Traded',
    symbol_column='Ticker'
)

config = CSVConfig(
    file_path='/path/to/custom_data.csv',
    schema_mapping=custom_schema
)
```

## CSV Configuration

### Complete Configuration Example

```python
from rustybt.data.adapters.csv_adapter import CSVConfig, SchemaMapping

config = CSVConfig(
    file_path='/path/to/data.csv',
    schema_mapping=SchemaMapping(...),
    delimiter=',',                      # Auto-detect if None
    has_header=True,                    # First row is header
    date_format='%Y-%m-%d %H:%M:%S',   # Auto-detect if None
    timezone='UTC',                     # Convert to UTC
    missing_data_strategy='fail'        # 'skip', 'interpolate', 'fail'
)
```

### Delimiter Detection

```python
# Auto-detect delimiter (tries: ',', ';', '\t', '|')
config = CSVConfig(
    file_path='/path/to/data.csv',
    delimiter=None,  # Will auto-detect
    ...
)

# Or specify explicitly
config = CSVConfig(
    file_path='/path/to/data.tsv',
    delimiter='\t',  # Tab-separated
    ...
)
```

### Date Format Handling

```python
# Auto-detect date format
config = CSVConfig(
    file_path='/path/to/data.csv',
    date_format=None,  # Will try common formats
    ...
)

# Or specify format explicitly
config = CSVConfig(
    file_path='/path/to/data.csv',
    date_format='%Y-%m-%d %H:%M:%S',  # e.g., '2024-01-15 09:30:00'
    ...
)

# Common date formats:
# '%Y-%m-%d'              # 2024-01-15
# '%Y-%m-%d %H:%M:%S'     # 2024-01-15 09:30:00
# '%m/%d/%Y'              # 01/15/2024
# '%d/%m/%Y'              # 15/01/2024
# '%Y%m%d'                # 20240115
```

## Usage Examples

### Example 1: Simple Single-File Import

```python
from rustybt.data.adapters import CSVAdapter
from rustybt.data.adapters.csv_adapter import CSVConfig, SchemaMapping

async def import_single_file():
    adapter = CSVAdapter()

    config = CSVConfig(
        file_path='/data/AAPL.csv',
        schema_mapping=SchemaMapping(
            date_column='Date',
            open_column='Open',
            high_column='High',
            low_column='Low',
            close_column='Close',
            volume_column='Volume'
        ),
        timezone='America/New_York'  # NYSE timezone
    )

    df = await adapter.load_csv(config)
    print(f"Imported {len(df)} bars for AAPL")
    return df

df = asyncio.run(import_single_file())
```

### Example 2: Batch Import Multiple Files

```python
from pathlib import Path

async def import_directory():
    """Import all CSV files from a directory."""
    adapter = CSVAdapter()

    data_dir = Path('/data/stocks')
    all_data = []

    for csv_file in data_dir.glob('*.csv'):
        # Extract symbol from filename (e.g., 'AAPL.csv' -> 'AAPL')
        symbol = csv_file.stem

        config = CSVConfig(
            file_path=str(csv_file),
            schema_mapping=SchemaMapping(
                date_column='Date',
                open_column='Open',
                high_column='High',
                low_column='Low',
                close_column='Close',
                volume_column='Volume'
            )
        )

        df = await adapter.load_csv(config)

        # Add symbol column
        df = df.with_columns(pl.lit(symbol).alias('symbol'))
        all_data.append(df)

        print(f"Imported {symbol}: {len(df)} bars")

    # Combine all data
    combined_df = pl.concat(all_data)
    return combined_df

df = asyncio.run(import_directory())
```

### Example 3: Custom Delimiter and Format

```python
async def import_custom_format():
    """Import semicolon-separated file with European date format."""
    adapter = CSVAdapter()

    config = CSVConfig(
        file_path='/data/european_data.csv',
        schema_mapping=SchemaMapping(
            date_column='Datum',        # German: 'Date'
            open_column='Eröffnung',    # German: 'Open'
            high_column='Hoch',         # German: 'High'
            low_column='Tief',          # German: 'Low'
            close_column='Schluss',     # German: 'Close'
            volume_column='Volumen'     # German: 'Volume'
        ),
        delimiter=';',                  # European CSV format
        date_format='%d.%m.%Y',        # DD.MM.YYYY
        timezone='Europe/Frankfurt'
    )

    df = await adapter.load_csv(config)
    return df
```

### Example 4: Handling Missing Data

```python
async def import_with_gaps():
    """Import CSV with missing values."""
    adapter = CSVAdapter()

    # Strategy 1: Skip rows with missing data
    config_skip = CSVConfig(
        file_path='/data/data_with_gaps.csv',
        schema_mapping=SchemaMapping(...),
        missing_data_strategy='skip'
    )

    df_skip = await adapter.load_csv(config_skip)
    print(f"Rows after skipping: {len(df_skip)}")

    # Strategy 2: Interpolate missing values
    config_interp = CSVConfig(
        file_path='/data/data_with_gaps.csv',
        schema_mapping=SchemaMapping(...),
        missing_data_strategy='interpolate'
    )

    df_interp = await adapter.load_csv(config_interp)
    print(f"Rows after interpolation: {len(df_interp)}")

    # Strategy 3: Fail on missing data (default)
    config_fail = CSVConfig(
        file_path='/data/data_with_gaps.csv',
        schema_mapping=SchemaMapping(...),
        missing_data_strategy='fail'
    )

    try:
        df_fail = await adapter.load_csv(config_fail)
    except InvalidDataError as e:
        print(f"Import failed due to missing data: {e}")
```

### Example 5: Symbol from Filename or Column

```python
async def extract_symbols():
    """Extract symbols from different sources."""
    adapter = CSVAdapter()

    # Method 1: Symbol in dedicated column
    config_column = CSVConfig(
        file_path='/data/multi_symbol.csv',
        schema_mapping=SchemaMapping(
            date_column='Date',
            symbol_column='Ticker',  # Symbol in column
            ...
        )
    )
    df1 = await adapter.load_csv(config_column)

    # Method 2: Symbol from filename
    config_filename = CSVConfig(
        file_path='/data/AAPL.csv',  # Symbol = 'AAPL'
        schema_mapping=SchemaMapping(
            date_column='Date',
            symbol_column=None,  # Extract from filename
            ...
        )
    )
    df2 = await adapter.load_csv(config_filename)
    # Symbol automatically set to 'AAPL'

    return df1, df2
```

## Validation

### Automatic Validation

```python
# CSV adapter automatically validates:
# 1. OHLCV relationships (high >= low, etc.)
# 2. Temporal ordering (dates in sequence)
# 3. Required columns present
# 4. Data types correct
# 5. No duplicate timestamps

df = await adapter.load_csv(config)
# Raises InvalidDataError if validation fails
```

### Custom Validation

```python
async def import_with_custom_validation():
    adapter = CSVAdapter()

    df = await adapter.load_csv(config)

    # Additional custom checks
    if df['volume'].min() < 0:
        raise ValueError("Negative volume detected")

    if df['close'].max() > 1000000:
        raise ValueError("Suspicious price detected")

    # Check for data gaps
    dates = df['timestamp'].to_list()
    date_diffs = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
    max_gap = max(date_diffs)

    if max_gap > 7:  # Max 7-day gap
        print(f"Warning: Max gap of {max_gap} days detected")

    return df
```

## Integration with Bundle System

### Creating Bundle from CSV

```python
from rustybt.data.bundles import register
from rustybt.data.adapters import CSVAdapter
from rustybt.data.adapters.csv_adapter import CSVConfig, SchemaMapping

# Register CSV data as bundle
register(
    bundle_name='custom_csv_data',
    adapter=CSVAdapter(),
    config=CSVConfig(
        file_path='/data/AAPL.csv',
        schema_mapping=SchemaMapping(...)
    )
)

# Use in backtest
from rustybt.utils.run_algo import run_algorithm

run_algorithm(
    start=pd.Timestamp('2024-01-01'),
    end=pd.Timestamp('2024-12-31'),
    bundle='custom_csv_data',
    ...
)
```

## Performance Optimization

### Large File Handling

```python
async def import_large_file():
    """Import large CSV efficiently."""
    adapter = CSVAdapter()

    # Polars handles large files efficiently via streaming
    config = CSVConfig(
        file_path='/data/large_file.csv',
        schema_mapping=SchemaMapping(...)
    )

    # Load with lazy evaluation
    df_lazy = await adapter.load_csv_lazy(config)

    # Process in chunks
    chunk_size = 100000
    for offset in range(0, df_lazy.height, chunk_size):
        df_chunk = df_lazy.slice(offset, chunk_size).collect()
        process_chunk(df_chunk)
```

### Parallel Import

```python
import asyncio

async def parallel_import():
    """Import multiple files in parallel."""
    adapter = CSVAdapter()

    files = ['/data/file1.csv', '/data/file2.csv', '/data/file3.csv']

    configs = [
        CSVConfig(file_path=f, schema_mapping=SchemaMapping(...))
        for f in files
    ]

    # Load all files concurrently
    tasks = [adapter.load_csv(config) for config in configs]
    results = await asyncio.gather(*tasks)

    # Combine results
    combined_df = pl.concat(results)
    return combined_df
```

## Common CSV Formats

### Format 1: Yahoo Finance Export

```csv
Date,Open,High,Low,Close,Adj Close,Volume
2024-01-02,187.15,188.44,185.19,185.64,185.26,54137800
2024-01-03,184.35,185.40,183.43,184.25,183.87,47471700
```

```python
config = CSVConfig(
    file_path='yahoo_export.csv',
    schema_mapping=SchemaMapping(
        date_column='Date',
        open_column='Open',
        high_column='High',
        low_column='Low',
        close_column='Close',
        volume_column='Volume'
    ),
    date_format='%Y-%m-%d'
)
```

### Format 2: MetaTrader Export

```csv
Date;Time;Open;High;Low;Close;Volume
2024.01.02;00:00;1.0950;1.0975;1.0945;1.0960;15000
2024.01.02;01:00;1.0960;1.0980;1.0955;1.0970;18000
```

```python
config = CSVConfig(
    file_path='mt5_export.csv',
    schema_mapping=SchemaMapping(
        date_column='Date',  # Will combine Date and Time
        ...
    ),
    delimiter=';',
    date_format='%Y.%m.%d'
)
```

### Format 3: Custom Trading Platform

```csv
timestamp,symbol,o,h,l,c,v
1704153600000,BTCUSDT,42150.5,42380.0,42100.0,42300.5,1250.35
1704157200000,BTCUSDT,42300.5,42450.0,42250.0,42400.0,980.25
```

```python
config = CSVConfig(
    file_path='crypto_data.csv',
    schema_mapping=SchemaMapping(
        date_column='timestamp',  # Unix timestamp in ms
        symbol_column='symbol',
        open_column='o',
        high_column='h',
        low_column='l',
        close_column='c',
        volume_column='v'
    )
)
```

## Error Handling

```python
from rustybt.data.adapters.base import InvalidDataError

async def robust_import():
    adapter = CSVAdapter()

    try:
        df = await adapter.load_csv(config)
        return df

    except FileNotFoundError:
        print("CSV file not found")

    except InvalidDataError as e:
        print(f"Data validation failed: {e}")
        # Try with different strategy
        config.missing_data_strategy = 'skip'
        df = await adapter.load_csv(config)

    except ValueError as e:
        print(f"Date parsing failed: {e}")
        # Try with explicit date format
        config.date_format = '%Y-%m-%d'
        df = await adapter.load_csv(config)
```

## Best Practices

1. **Validate Data First**: Always inspect CSV structure before import
2. **Use Explicit Schemas**: Specify formats when auto-detection might fail
3. **Handle Timezones**: Convert to UTC for consistency
4. **Check for Gaps**: Validate temporal consistency
5. **Test with Sample**: Test import logic on small sample first

## API Reference

```python
class CSVAdapter(BaseDataAdapter):
    """CSV data import adapter."""

    async def load_csv(self, config: CSVConfig) -> pl.DataFrame:
        """Load CSV file with specified configuration."""

    async def load_csv_lazy(self, config: CSVConfig) -> pl.LazyFrame:
        """Load CSV with lazy evaluation for large files."""

    async def load_multiple_csv(
        self,
        configs: list[CSVConfig]
    ) -> pl.DataFrame:
        """Load and combine multiple CSV files."""
```

## See Also

- [Adapter Overview](overview.md) - Common adapter features
- [Data Catalog](../catalog/bundles.md) - Creating bundles from CSV
- [Schema Validation](../readers/bar-readers.md) - Data quality checks
