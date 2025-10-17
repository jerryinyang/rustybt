# Daily Bar Readers

Daily bar readers provide access to end-of-day OHLCV data. RustyBT supports multiple storage formats with **Parquet/Polars** as the recommended modern implementation.

## Overview

Daily bar readers load one bar per trading day for each asset. They are used for:

- Daily frequency backtests
- End-of-day strategy execution
- Historical analysis and research
- Data rolled up from minute bars

### Available Implementations

| Reader | Format | Precision | Status | Recommended |
|--------|--------|-----------|--------|-------------|
| `PolarsParquetDailyReader` | Parquet | Decimal | Active | ✅ Yes |
| `BcolzDailyBarReader` | Bcolz | float64 | Legacy | ⚠️ Existing projects only |
| `HDF5DailyBarReader` | HDF5 | float64 | Deprecated | ❌ No |

## PolarsParquetDailyReader

**Modern, recommended implementation** with Decimal precision and Polars performance.

### Features

- **Decimal Precision**: Financial-grade arithmetic with Python `Decimal`
- **Lazy Loading**: Efficient partition pruning for fast queries
- **Partitioned Storage**: Year/month partitioning for scalability
- **Built-in Validation**: OHLCV relationship validation
- **Caching**: Optional in-memory caching for hot data
- **Metadata Integration**: Tracks data quality and provenance

### Storage Structure

```
data/bundles/<bundle_name>/daily_bars/
├── year=2022/
│   ├── month=01/
│   │   └── data.parquet
│   ├── month=02/
│   │   └── data.parquet
│   └── ...
├── year=2023/
│   ├── month=01/
│   │   └── data.parquet
│   └── ...
└── year=2024/
    └── ...
```

**Benefits of Partitioning**:
- Fast queries (only scans relevant partitions)
- Scalable to decades of data
- Easy data management (add/remove years)

### API Reference

#### Class: `PolarsParquetDailyReader`

**Location**: `rustybt.data.polars.parquet_daily_bars`

##### Constructor

```python
PolarsParquetDailyReader(
    bundle_path: str,
    enable_cache: bool = True,
    enable_metadata_catalog: bool = True
)
```

**Parameters**:
- `bundle_path` (str): Path to bundle directory (e.g., "data/bundles/quandl")
- `enable_cache` (bool, default=True): Enable in-memory caching for frequently accessed data
- `enable_metadata_catalog` (bool, default=True): Enable metadata catalog integration

**Example**:
```python
from rustybt.data.polars import PolarsParquetDailyReader

# Initialize with defaults (caching enabled)
reader = PolarsParquetDailyReader("data/bundles/my_bundle")

# Initialize without caching (for live data)
live_reader = PolarsParquetDailyReader(
    "data/bundles/live_bundle",
    enable_cache=False
)
```

---

##### Method: `load_daily_bars()`

Load daily bars for assets in date range.

```python
def load_daily_bars(
    sids: list[int],
    start_date: date,
    end_date: date,
    fields: list[str] | None = None
) -> pl.DataFrame
```

**Parameters**:
- `sids` (list[int]): Asset IDs to load
- `start_date` (date): Start date (inclusive)
- `end_date` (date): End date (inclusive)
- `fields` (list[str], optional): Columns to load (default: all OHLCV)

**Returns**: Polars DataFrame with schema:
- `date`: pl.Date
- `sid`: pl.Int64
- `open`: pl.Decimal(18, 8)
- `high`: pl.Decimal(18, 8)
- `low`: pl.Decimal(18, 8)
- `close`: pl.Decimal(18, 8)
- `volume`: pl.Decimal(18, 8)

**Raises**:
- `FileNotFoundError`: If bundle directory not found
- `DataError`: If no data found or validation fails

**Example**:
```python
from datetime import date

# Load 1 month of data for 3 assets
df = reader.load_daily_bars(
    sids=[1, 2, 3],
    start_date=date(2024, 1, 1),
    end_date=date(2024, 1, 31)
)

print(df.head())
# ┌────────────┬─────┬──────────┬──────────┬──────────┬──────────┬──────────┐
# │ date       ┆ sid ┆ open     ┆ high     ┆ low      ┆ close    ┆ volume   │
# │ ---        ┆ --- ┆ ---      ┆ ---      ┆ ---      ┆ ---      ┆ ---      │
# │ date       ┆ i64 ┆ decimal  ┆ decimal  ┆ decimal  ┆ decimal  ┆ decimal  │
# ╞════════════╪═════╪══════════╪══════════╪══════════╪══════════╪══════════╡
# │ 2024-01-02 ┆ 1   ┆ 185.28   ┆ 186.74   ┆ 184.35   ┆ 185.64   ┆ 82000000 │
# │ 2024-01-02 ┆ 2   ┆ 140.23   ┆ 141.05   ┆ 139.87   ┆ 140.93   ┆ 35000000 │
# │ ...        ┆ ... ┆ ...      ┆ ...      ┆ ...      ┆ ...      ┆ ...      │
# └────────────┴─────┴──────────┴──────────┴──────────┴──────────┴──────────┘

# Load only close prices (optimized)
close_df = reader.load_daily_bars(
    sids=[1, 2, 3],
    start_date=date(2024, 1, 1),
    end_date=date(2024, 1, 31),
    fields=["close"]  # Only load close column
)
```

---

##### Method: `load_spot_value()`

Load spot values at specific date.

```python
def load_spot_value(
    sids: list[int],
    target_date: date,
    field: str = "close"
) -> pl.DataFrame
```

**Parameters**:
- `sids` (list[int]): Asset IDs
- `target_date` (date): Target date
- `field` (str, default="close"): Field to retrieve

**Returns**: DataFrame with `sid` and field columns

**Example**:
```python
# Get closing prices for assets on specific date
prices = reader.load_spot_value(
    sids=[1, 2, 3],
    target_date=date(2024, 1, 15),
    field="close"
)

# ┌─────┬──────────┐
# │ sid ┆ close    │
# │ --- ┆ ---      │
# │ i64 ┆ decimal  │
# ╞═════╪══════════╡
# │ 1   ┆ 185.64   │
# │ 2   ┆ 140.93   │
# │ 3   ┆ 412.35   │
# └─────┴──────────┘

# Get volumes
volumes = reader.load_spot_value(
    sids=[1, 2, 3],
    target_date=date(2024, 1, 15),
    field="volume"
)
```

---

##### Method: `get_last_available_date()`

Get last available trading date for an asset.

```python
def get_last_available_date(sid: int) -> date | None
```

**Parameters**:
- `sid` (int): Asset ID

**Returns**: Last available date or None if no data

**Example**:
```python
# Check when asset last traded
last_date = reader.get_last_available_date(sid=1)

if last_date:
    print(f"Last data available: {last_date}")
else:
    print("No data found for asset")
```

---

##### Method: `get_first_available_date()`

Get first available trading date for an asset.

```python
def get_first_available_date(sid: int) -> date | None
```

**Parameters**:
- `sid` (int): Asset ID

**Returns**: First available date or None if no data

**Example**:
```python
# Check data coverage
first = reader.get_first_available_date(sid=1)
last = reader.get_last_available_date(sid=1)

print(f"Data coverage: {first} to {last}")
```

---

## Usage Patterns

### Pattern 1: Basic Daily Data Loading

```python
from datetime import date
from rustybt.data.polars import PolarsParquetDailyReader

# Initialize reader
reader = PolarsParquetDailyReader("data/bundles/equities")

# Load 1 year of daily data
df = reader.load_daily_bars(
    sids=[1, 2, 3, 4, 5],
    start_date=date(2023, 1, 1),
    end_date=date(2023, 12, 31)
)

# Calculate returns
returns = df.with_columns([
    pl.col("close").pct_change().over("sid").alias("returns")
])
```

### Pattern 2: Efficient Column Selection

```python
# Load only the columns you need
close_only = reader.load_daily_bars(
    sids=sids,
    start_date=start,
    end_date=end,
    fields=["close"]  # 5x faster than loading all columns
)

# Load OHLC without volume
ohlc = reader.load_daily_bars(
    sids=sids,
    start_date=start,
    end_date=end,
    fields=["open", "high", "low", "close"]
)
```

### Pattern 3: Spot Value Queries

```python
# Get latest prices for portfolio
current_prices = reader.load_spot_value(
    sids=[1, 2, 3, 4, 5],
    target_date=date.today(),
    field="close"
)

# Calculate portfolio value
portfolio_value = sum(
    row["close"] * holdings[row["sid"]]
    for row in current_prices.iter_rows(named=True)
)
```

### Pattern 4: Data Coverage Checks

```python
def check_data_coverage(reader, sids):
    """Check data availability for assets."""
    coverage = []

    for sid in sids:
        first = reader.get_first_available_date(sid)
        last = reader.get_last_available_date(sid)

        coverage.append({
            "sid": sid,
            "first_date": first,
            "last_date": last,
            "days": (last - first).days if first and last else 0
        })

    return pl.DataFrame(coverage)

# Check coverage
coverage_df = check_data_coverage(reader, [1, 2, 3, 4, 5])
print(coverage_df)
```

### Pattern 5: Caching for Performance

```python
# Enable caching for repeated queries
reader = PolarsParquetDailyReader(
    "data/bundles/my_data",
    enable_cache=True
)

# First load (reads from disk)
df1 = reader.load_daily_bars(sids=[1, 2], start, end)  # ~100ms

# Second load (uses cache)
df2 = reader.load_daily_bars(sids=[1, 2], start, end)  # ~1ms

# Cache is automatically managed (LRU eviction)
```

### Pattern 6: Integration with DataPortal

```python
from rustybt.data.polars.data_portal import PolarsDataPortal

# Reader used internally by portal
portal = PolarsDataPortal(
    daily_reader=PolarsParquetDailyReader("data/bundles/equities")
)

# Access via portal API
prices = portal.get_spot_value(
    assets=[asset1, asset2],
    field="close",
    dt=pd.Timestamp("2024-01-15"),
    data_frequency="daily"
)
```

### Pattern 7: Multi-Asset Analysis

```python
# Load data for portfolio
portfolio_sids = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

df = reader.load_daily_bars(
    sids=portfolio_sids,
    start_date=date(2023, 1, 1),
    end_date=date(2024, 1, 1),
    fields=["close"]
)

# Pivot for correlation analysis
pivot_df = df.pivot(
    values="close",
    index="date",
    columns="sid"
)

# Calculate correlation matrix
corr_matrix = pivot_df.corr()
```

## Performance Optimization

### 1. Partition Pruning

Polars automatically prunes partitions based on date filters:

```python
# Only scans year=2024/month=01 partition
jan_data = reader.load_daily_bars(
    sids=sids,
    start_date=date(2024, 1, 1),
    end_date=date(2024, 1, 31)
)

# Scans multiple partitions (slower but still efficient)
year_data = reader.load_daily_bars(
    sids=sids,
    start_date=date(2024, 1, 1),
    end_date=date(2024, 12, 31)
)
```

### 2. Column Selection

Load only needed columns:

```python
# GOOD: Load only close (fast)
close_df = reader.load_daily_bars(sids=sids, start=start, end=end, fields=["close"])

# GOOD: Load OHLC without volume (faster)
ohlc_df = reader.load_daily_bars(
    sids=sids, start=start, end=end,
    fields=["open", "high", "low", "close"]
)

# AVOID: Loading all columns when only need one
all_df = reader.load_daily_bars(sids=sids, start=start, end=end)  # Slower
close = all_df.select("close")  # Should have used fields parameter
```

### 3. Batch Asset Queries

Query multiple assets at once:

```python
# GOOD: Single batch query
df = reader.load_daily_bars(sids=[1, 2, 3, 4, 5], start, end)

# AVOID: Individual queries
dfs = []
for sid in [1, 2, 3, 4, 5]:
    df = reader.load_daily_bars(sids=[sid], start, end)  # Inefficient!
    dfs.append(df)
```

### 4. Cache Management

Use caching for repeated queries:

```python
# Enable caching for backtests (repeated data access)
backtest_reader = PolarsParquetDailyReader(
    bundle_path="data/bundles/backtest",
    enable_cache=True  # Cache hot data
)

# Disable caching for one-off queries
analysis_reader = PolarsParquetDailyReader(
    bundle_path="data/bundles/analysis",
    enable_cache=False  # Don't waste memory
)
```

## Data Validation

### Automatic OHLCV Validation

All data is validated on load:

```python
# Validates automatically
df = reader.load_daily_bars(sids=[1], start, end)

# Checks performed:
# 1. high >= low
# 2. high >= open
# 3. high >= close
# 4. low <= open
# 5. low <= close
# 6. volume >= 0

# Raises DataError if validation fails
```

### Manual Validation

```python
from rustybt.data.polars.validation import validate_ohlcv_relationships, DataError

try:
    df = reader.load_daily_bars(sids=[1], start, end)
except DataError as e:
    print(f"Invalid OHLCV data: {e}")
    # Handle bad data (skip, fix, alert, etc.)
```

## Exceptions

### `DataError`

Raised when data issues detected.

**Common causes**:
- No data found for date range
- OHLCV validation failed
- Corrupt Parquet files

**Example**:
```python
from rustybt.data.polars.validation import DataError

try:
    df = reader.load_daily_bars(
        sids=[999],  # Asset doesn't exist
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31)
    )
except DataError as e:
    print(f"Data error: {e}")
```

### `FileNotFoundError`

Raised when bundle directory not found.

**Example**:
```python
try:
    reader = PolarsParquetDailyReader("nonexistent/bundle")
    df = reader.load_daily_bars(sids=[1], start, end)
except FileNotFoundError as e:
    print(f"Bundle not found: {e}")
```

## Migration from Legacy Readers

### From BcolzDailyBarReader

**Before**:
```python
from rustybt.data.bcolz_daily_bars import BcolzDailyBarReader

reader = BcolzDailyBarReader("bundles/legacy_data")
arrays = reader.load_raw_arrays(
    columns=["close"],
    start_date=start,
    end_date=end,
    assets=[1, 2, 3]
)  # Returns numpy arrays with float64
```

**After**:
```python
from rustybt.data.polars import PolarsParquetDailyReader

reader = PolarsParquetDailyReader("bundles/new_data")
df = reader.load_daily_bars(
    sids=[1, 2, 3],
    start_date=start.date(),
    end_date=end.date(),
    fields=["close"]
)  # Returns Polars DataFrame with Decimal
```

## See Also

- [PolarsDataPortal](polars-data-portal.md) - High-level data access using daily readers
- [Bar Readers](bar-reader.md) - Bar reader interface and dispatch
- [Bundle System](../catalog/bundle-system.md) - Data bundle management
- [Data Ingestion](../catalog/README.md) - Creating daily bar bundles
