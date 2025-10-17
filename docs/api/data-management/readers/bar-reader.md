# Bar Readers

Bar readers provide the low-level interface for reading OHLCV data from various storage formats. They abstract away format-specific details and present a unified API for data access.

## Overview

RustyBT's bar reader system consists of three layers:

1. **Abstract Interface** (`BarReader`) - Defines the contract all readers must implement
2. **Dispatch Layer** (`AssetDispatchBarReader`) - Routes requests to appropriate readers based on asset type
3. **Format Implementations** - Concrete readers for specific storage formats (Parquet, Bcolz, HDF5)

This architecture allows mixing different data sources and formats in a single backtest.

## Architecture

### Layer 1: Abstract Bar Reader Interface

The `BarReader` abstract base class defines the interface all readers must implement:

```python
from rustybt.data.bar_reader import BarReader

class MyCustomReader(BarReader):
    @property
    def data_frequency(self):
        """Return 'daily' or 'minute'"""
        return "daily"

    def load_raw_arrays(self, columns, start_date, end_date, assets):
        """Load raw OHLCV arrays"""
        pass

    @property
    def last_available_dt(self):
        """Last timestamp with data"""
        pass

    @property
    def trading_calendar(self):
        """Trading calendar used by this reader"""
        pass

    @property
    def first_trading_day(self):
        """First trading day with data"""
        pass

    def get_value(self, sid, dt, field):
        """Get single value"""
        pass

    def get_last_traded_dt(self, asset, dt):
        """Get last traded timestamp"""
        pass
```

### Layer 2: Dispatch System

The dispatch system routes data requests to the appropriate reader based on asset type:

```
DataPortal
    ↓
AssetDispatchBarReader (Minute or Session)
    ↓
┌────────────┬─────────────┬──────────────┐
│  Equity    │   Future    │  Continuous  │
│  Reader    │   Reader    │   Future     │
│            │             │   Reader     │
└────────────┴─────────────┴──────────────┘
```

**Key Features:**
- Maps asset types to specific readers
- Handles mixed asset types in single request
- Ensures calendar alignment across readers
- Aggregates results into unified arrays

### Layer 3: Format Implementations

Concrete readers for specific storage formats:

| Reader | Format | Frequency | Precision | Use Case |
|--------|--------|-----------|-----------|----------|
| `PolarsParquetDailyReader` | Parquet | Daily | Decimal | Modern, recommended |
| `PolarsParquetMinuteReader` | Parquet | Minute | Decimal | Modern, recommended |
| `BcolzDailyBarReader` | Bcolz | Daily | float64 | Legacy Zipline |
| `BcolzMinuteBarReader` | Bcolz | Minute | float64 | Legacy Zipline |
| `HDF5DailyBarReader` | HDF5 | Daily | float64 | Legacy |

## API Reference

### Class: `BarReader` (Abstract)

**Location**: `rustybt.data.bar_reader`

Base interface for all bar readers.

#### Abstract Methods

##### `load_raw_arrays()`

Load raw OHLCV arrays for multiple assets and date range.

```python
def load_raw_arrays(
    columns: list[str],
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    assets: list[int]
) -> list[np.ndarray]
```

**Parameters**:
- `columns` (list[str]): Fields to load - 'open', 'high', 'low', 'close', 'volume'
- `start_date` (pd.Timestamp): Start of date range (inclusive)
- `end_date` (pd.Timestamp): End of date range (inclusive)
- `assets` (list[int]): Asset IDs (sids) to load

**Returns**: List of numpy arrays, one per column. Shape: `(num_dates, num_assets)`

**Example**:
```python
# Load close and volume for 3 assets
arrays = reader.load_raw_arrays(
    columns=["close", "volume"],
    start_date=pd.Timestamp("2024-01-01"),
    end_date=pd.Timestamp("2024-01-31"),
    assets=[1, 2, 3]
)

close_array = arrays[0]  # Shape: (num_trading_days, 3)
volume_array = arrays[1]  # Shape: (num_trading_days, 3)
```

---

##### `get_value()`

Get single field value for one asset at specific timestamp.

```python
def get_value(
    sid: int,
    dt: pd.Timestamp,
    field: str
) -> float
```

**Parameters**:
- `sid` (int): Asset ID
- `dt` (pd.Timestamp): Timestamp to query
- `field` (str): Field name - 'open', 'high', 'low', 'close', 'volume'

**Returns**: float - Field value

**Raises**:
- `NoDataOnDate`: If no data available for timestamp

**Example**:
```python
# Get closing price for asset 1 on specific date
close_price = reader.get_value(
    sid=1,
    dt=pd.Timestamp("2024-01-15"),
    field="close"
)
```

---

##### `get_last_traded_dt()`

Get last timestamp when asset traded on or before given timestamp.

```python
def get_last_traded_dt(
    asset: Asset,
    dt: pd.Timestamp
) -> pd.Timestamp
```

**Parameters**:
- `asset` (Asset): Asset object
- `dt` (pd.Timestamp): Reference timestamp

**Returns**: pd.Timestamp - Last traded timestamp, or pd.NaT if never traded

**Example**:
```python
# Find when asset last traded
last_traded = reader.get_last_traded_dt(
    asset=asset,
    dt=pd.Timestamp("2024-01-15")
)

if pd.notna(last_traded):
    print(f"Last traded: {last_traded}")
```

---

#### Abstract Properties

##### `data_frequency`

Data frequency of this reader.

```python
@property
def data_frequency(self) -> str
```

**Returns**: 'daily' or 'minute'

---

##### `last_available_dt`

Last timestamp with available data.

```python
@property
def last_available_dt(self) -> pd.Timestamp
```

**Returns**: Last available timestamp

---

##### `first_trading_day`

First trading day with available data.

```python
@property
def first_trading_day(self) -> pd.Timestamp
```

**Returns**: First trading day

---

##### `trading_calendar`

Trading calendar used by this reader.

```python
@property
def trading_calendar(self) -> TradingCalendar
```

**Returns**: TradingCalendar instance

---

### Class: `AssetDispatchBarReader` (Abstract)

**Location**: `rustybt.data.dispatch_bar_reader`

Routes bar requests to appropriate readers based on asset type.

#### Constructor

```python
AssetDispatchBarReader(
    trading_calendar: TradingCalendar,
    asset_finder: AssetFinder,
    readers: dict[type, BarReader],
    last_available_dt: pd.Timestamp | None = None
)
```

**Parameters**:
- `trading_calendar` (TradingCalendar): Shared trading calendar
- `asset_finder` (AssetFinder): Asset lookup
- `readers` (dict): Mapping of asset type to reader instance
- `last_available_dt` (pd.Timestamp, optional): Override last available timestamp

**Example**:
```python
from rustybt.assets import Equity, Future
from rustybt.data.dispatch_bar_reader import AssetDispatchSessionBarReader

# Create readers for different asset types
equity_reader = PolarsParquetDailyReader("bundles/equities")
future_reader = PolarsParquetDailyReader("bundles/futures")

# Create dispatch reader
dispatch = AssetDispatchSessionBarReader(
    trading_calendar=calendar,
    asset_finder=finder,
    readers={
        Equity: equity_reader,
        Future: future_reader
    }
)

# Now dispatch routes requests automatically
# Equities go to equity_reader, futures to future_reader
data = dispatch.load_raw_arrays(["close"], start, end, [equity_sid, future_sid])
```

---

#### Method: `get_value()`

Get value for any asset type (routes to appropriate reader).

```python
def get_value(
    sid: int,
    dt: pd.Timestamp,
    field: str
) -> float
```

**Example**:
```python
# Works for any asset type registered in readers dict
equity_price = dispatch.get_value(equity_sid, dt, "close")
future_price = dispatch.get_value(future_sid, dt, "close")
```

---

#### Method: `load_raw_arrays()`

Load arrays for mixed asset types (dispatches and aggregates).

```python
def load_raw_arrays(
    fields: list[str],
    start_dt: pd.Timestamp,
    end_dt: pd.Timestamp,
    sids: list[int]
) -> list[np.ndarray]
```

**How It Works**:
1. Groups sids by asset type
2. Dispatches to appropriate readers
3. Aggregates results maintaining original sid order

**Example**:
```python
# Mix of equity and future sids
mixed_sids = [equity1, equity2, future1, equity3]

# Dispatch automatically routes each to correct reader
arrays = dispatch.load_raw_arrays(
    fields=["close", "volume"],
    start_dt=start,
    end_dt=end,
    sids=mixed_sids
)

# Result maintains original order:
# [equity1, equity2, future1, equity3]
```

---

### Concrete Implementations

#### Class: `AssetDispatchMinuteBarReader`

Dispatch reader for minute-frequency data.

```python
from rustybt.data.dispatch_bar_reader import AssetDispatchMinuteBarReader

dispatch = AssetDispatchMinuteBarReader(
    trading_calendar=calendar,
    asset_finder=finder,
    readers={Equity: minute_reader}
)
```

---

#### Class: `AssetDispatchSessionBarReader`

Dispatch reader for daily/session-frequency data.

```python
from rustybt.data.dispatch_bar_reader import AssetDispatchSessionBarReader

dispatch = AssetDispatchSessionBarReader(
    trading_calendar=calendar,
    asset_finder=finder,
    readers={Equity: daily_reader}
)
```

---

## Usage Patterns

### Pattern 1: Single Format, Single Asset Type

Simplest case - one reader for one asset type:

```python
from rustybt.data.polars import PolarsParquetDailyReader
from rustybt.data.dispatch_bar_reader import AssetDispatchSessionBarReader
from rustybt.assets import Equity

# Single reader
equity_reader = PolarsParquetDailyReader("bundles/equities")

# Wrap in dispatch for DataPortal compatibility
dispatch = AssetDispatchSessionBarReader(
    trading_calendar=calendar,
    asset_finder=finder,
    readers={Equity: equity_reader}
)
```

### Pattern 2: Multiple Asset Types

Different readers for different asset types:

```python
from rustybt.assets import Equity, Future
from rustybt.data.polars import PolarsParquetDailyReader

# Separate readers for each asset type
equity_reader = PolarsParquetDailyReader("bundles/equities")
future_reader = PolarsParquetDailyReader("bundles/futures")

# Dispatch routes based on asset type
dispatch = AssetDispatchSessionBarReader(
    trading_calendar=calendar,
    asset_finder=finder,
    readers={
        Equity: equity_reader,
        Future: future_reader
    }
)

# Queries with mixed asset types work seamlessly
mixed_data = dispatch.load_raw_arrays(
    fields=["close"],
    start_dt=start,
    end_dt=end,
    sids=[equity_sid, future_sid]  # Mix of types
)
```

### Pattern 3: Multiple Formats

Different formats for same asset type (e.g., migration scenario):

```python
# Legacy bcolz data for old dates
old_reader = BcolzDailyBarReader("bundles/old_data")

# New Parquet data for recent dates
new_reader = PolarsParquetDailyReader("bundles/new_data")

# Custom dispatch logic to choose reader by date
class DateRangeDispatch(AssetDispatchSessionBarReader):
    def get_value(self, sid, dt, field):
        if dt < pd.Timestamp("2023-01-01"):
            return old_reader.get_value(sid, dt, field)
        else:
            return new_reader.get_value(sid, dt, field)
```

### Pattern 4: Custom Reader Implementation

Implement custom reader for special data source:

```python
from rustybt.data.bar_reader import BarReader
import requests

class APIDataReader(BarReader):
    """Read bars from REST API"""

    def __init__(self, api_url, api_key):
        self.api_url = api_url
        self.api_key = api_key
        self._calendar = get_calendar("NYSE")

    @property
    def data_frequency(self):
        return "daily"

    @property
    def trading_calendar(self):
        return self._calendar

    def load_raw_arrays(self, columns, start_date, end_date, assets):
        # Fetch from API
        response = requests.get(
            f"{self.api_url}/bars",
            params={
                "assets": ",".join(map(str, assets)),
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "fields": ",".join(columns)
            },
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
        data = response.json()

        # Convert to numpy arrays
        # ... implementation ...

        return arrays

    # Implement other required methods...
```

### Pattern 5: Reader Composition

Combine multiple readers with fallback logic:

```python
class FallbackReader(BarReader):
    """Try primary reader, fall back to secondary if no data"""

    def __init__(self, primary, secondary):
        self.primary = primary
        self.secondary = secondary

    def get_value(self, sid, dt, field):
        try:
            return self.primary.get_value(sid, dt, field)
        except NoDataOnDate:
            logger.warning(f"No data in primary, trying secondary")
            return self.secondary.get_value(sid, dt, field)

    @property
    def data_frequency(self):
        return self.primary.data_frequency

    # Implement other methods with fallback logic...
```

## Performance Considerations

### Reader Selection

Choose appropriate reader based on use case:

```python
# GOOD: Parquet for new projects (fast, standard, Decimal precision)
reader = PolarsParquetDailyReader("bundles/my_data")

# LEGACY: Bcolz only for existing Zipline projects
reader = BcolzDailyBarReader("bundles/legacy_data")

# AVOID: HDF5 (slow, deprecated)
# reader = HDF5DailyBarReader("bundles/old_data")
```

### Batch Loading

Load data in batches for better performance:

```python
# GOOD: Load all assets at once
arrays = reader.load_raw_arrays(
    columns=["close", "volume"],
    start_date=start,
    end_date=end,
    assets=all_sids  # Load all at once
)

# AVOID: Loading one asset at a time
for sid in all_sids:
    array = reader.load_raw_arrays(
        columns=["close"],
        start_date=start,
        end_date=end,
        assets=[sid]  # Inefficient!
    )
```

### Date Range Optimization

Request only the data you need:

```python
# GOOD: Precise date range
history = reader.load_raw_arrays(
    columns=["close"],
    start_date=start,  # Only 20 days
    end_date=end,
    assets=sids
)

# AVOID: Loading excess data
history = reader.load_raw_arrays(
    columns=["close"],
    start_date=start - pd.Timedelta(days=365),  # Loading too much!
    end_date=end,
    assets=sids
)
```

## Exceptions

### `NoDataOnDate`

Raised when requested data not available for timestamp.

**Common causes**:
- Market closed (weekend, holiday)
- Asset not yet trading
- Asset delisted

**Example**:
```python
from rustybt.data.bar_reader import NoDataOnDate

try:
    price = reader.get_value(sid=1, dt=weekend_date, field="close")
except NoDataOnDate:
    print("No data - market closed")
```

### `NoDataBeforeDate`

Raised when requesting data before first available date.

### `NoDataAfterDate`

Raised when requesting data after last available date.

### `NoDataForSid`

Raised when asset ID not found in dataset.

## See Also

- [Data Portal](data-portal.md) - High-level data access interface
- [PolarsDataPortal](polars-data-portal.md) - Modern portal using bar readers
- [Daily Bar Readers](daily-bars.md) - Daily frequency implementations
- [Bundle System](../catalog/bundle-system.md) - Data bundle management
