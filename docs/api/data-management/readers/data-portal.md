# DataPortal (Legacy)

The **DataPortal** is the legacy Zipline-based data access interface. While still functional, it is being phased out in favor of [PolarsDataPortal](polars-data-portal.md) which offers better performance and Decimal precision.

> **⚠️ Deprecation Notice**: This API is maintained for backward compatibility with existing Zipline strategies. New code should use [PolarsDataPortal](polars-data-portal.md).

## Overview

`DataPortal` provides the central interface for accessing market data during backtests. It supports:

- Multiple asset types (Equities, Futures, Continuous Futures)
- Multiple data frequencies (daily, minute)
- Multiple storage formats (Bcolz, HDF5, Parquet)
- Corporate action adjustments (splits, dividends, mergers)
- History windows with forward-filling
- Extra data sources (Fetcher API)

## Basic Usage

### Initialization

```python
from rustybt.data.data_portal import DataPortal
from rustybt.data.bundles import load
import pandas as pd

# Load bundle
bundle_data = load("quandl")

# Create portal
portal = DataPortal(
    asset_finder=bundle_data.asset_finder,
    trading_calendar=bundle_data.equity_daily_bar_reader.trading_calendar,
    first_trading_day=pd.Timestamp("2020-01-01"),
    equity_daily_reader=bundle_data.equity_daily_bar_reader,
    adjustment_reader=bundle_data.adjustment_reader
)
```

### Get Spot Value

```python
# Retrieve current price
price = portal.get_spot_value(
    assets=asset,  # Single Asset object
    field="close",
    dt=pd.Timestamp("2024-01-15"),
    data_frequency="daily"
)

# price is a float64 value
print(f"Close: ${price:.2f}")
```

### Get History Window

```python
# Get 20-day price history
history = portal.get_history_window(
    assets=[asset1, asset2],
    end_dt=pd.Timestamp("2024-01-15"),
    bar_count=20,
    frequency="1d",
    field="close",
    data_frequency="daily"
)

# history is a pandas DataFrame
print(history.head())
```

## API Reference

### Class: `DataPortal`

**Location**: `rustybt.data.data_portal`

#### Constructor

```python
DataPortal(
    asset_finder,
    trading_calendar,
    first_trading_day,
    equity_daily_reader=None,
    equity_minute_reader=None,
    future_daily_reader=None,
    future_minute_reader=None,
    adjustment_reader=None,
    last_available_session=None,
    last_available_minute=None,
    minute_history_prefetch_length=1560,
    daily_history_prefetch_length=40
)
```

**Parameters**:
- `asset_finder` (AssetFinder): Asset lookup and retrieval
- `trading_calendar` (TradingCalendar): Trading calendar for date/time operations
- `first_trading_day` (pd.Timestamp): First trading day for the simulation
- `equity_daily_reader` (BarReader, optional): Daily bar reader for equities
- `equity_minute_reader` (BarReader, optional): Minute bar reader for equities
- `future_daily_reader` (BarReader, optional): Daily bar reader for futures
- `future_minute_reader` (BarReader, optional): Minute bar reader for futures
- `adjustment_reader` (AdjustmentReader, optional): Corporate action adjustments
- `last_available_session` (pd.Timestamp, optional): Last available session
- `last_available_minute` (pd.Timestamp, optional): Last available minute
- `minute_history_prefetch_length` (int, default=1560): Minute history prefetch size
- `daily_history_prefetch_length` (int, default=40): Daily history prefetch size

**Example**:
```python
from rustybt.data.bundles import load

bundle_data = load("my_bundle")

portal = DataPortal(
    asset_finder=bundle_data.asset_finder,
    trading_calendar=bundle_data.equity_daily_bar_reader.trading_calendar,
    first_trading_day=pd.Timestamp("2020-01-01"),
    equity_daily_reader=bundle_data.equity_daily_bar_reader,
    equity_minute_reader=bundle_data.equity_minute_bar_reader,
    adjustment_reader=bundle_data.adjustment_reader
)
```

---

#### Method: `get_spot_value()`

Get current field value for asset(s) at a specific timestamp.

```python
def get_spot_value(
    assets,  # Asset or list[Asset]
    field: str,
    dt: pd.Timestamp,
    data_frequency: str
) -> float | list[float]
```

**Parameters**:
- `assets` (Asset or list[Asset]): Asset(s) to query
- `field` (str): Field name - 'open', 'high', 'low', 'close', 'volume', 'price', 'last_traded'
- `dt` (pd.Timestamp): Timestamp to query
- `data_frequency` (str): Data frequency - 'daily' or 'minute'

**Returns**:
- float if `assets` is a single Asset
- list[float] if `assets` is a list

**Special Fields**:
- `price`: Uses 'close' with forward-filling
- `last_traded`: Returns last traded timestamp (pd.Timestamp)

**Example**:
```python
# Single asset
close_price = portal.get_spot_value(
    assets=asset,
    field="close",
    dt=pd.Timestamp("2024-01-15"),
    data_frequency="daily"
)

# Multiple assets
prices = portal.get_spot_value(
    assets=[asset1, asset2, asset3],
    field="close",
    dt=pd.Timestamp("2024-01-15"),
    data_frequency="daily"
)  # Returns list of 3 prices

# Get last traded timestamp
last_traded = portal.get_spot_value(
    assets=asset,
    field="last_traded",
    dt=pd.Timestamp("2024-01-15"),
    data_frequency="daily"
)  # Returns pd.Timestamp
```

---

#### Method: `get_history_window()`

Get historical window as pandas DataFrame.

```python
def get_history_window(
    assets: list[Asset],
    end_dt: pd.Timestamp,
    bar_count: int,
    frequency: str,
    field: str,
    data_frequency: str,
    ffill: bool = True
) -> pd.DataFrame
```

**Parameters**:
- `assets` (list[Asset]): List of assets to query
- `end_dt` (pd.Timestamp): End timestamp (inclusive)
- `bar_count` (int): Number of bars to retrieve
- `frequency` (str): Frequency - '1d' (daily) or '1m' (minute)
- `field` (str): Field name - 'open', 'high', 'low', 'close', 'volume', 'price', 'sid'
- `data_frequency` (str): Source data frequency - 'daily' or 'minute'
- `ffill` (bool, default=True): Forward-fill missing price values

**Returns**: pandas DataFrame with:
- Index: DatetimeIndex of timestamps
- Columns: Asset objects
- Values: float64 field values

**Example**:
```python
# Get 20-day closing price history
history = portal.get_history_window(
    assets=[asset1, asset2],
    end_dt=pd.Timestamp("2024-01-15"),
    bar_count=20,
    frequency="1d",
    field="close",
    data_frequency="daily",
    ffill=True
)

# Result DataFrame:
#             Asset(1)  Asset(2)
# 2023-12-18   195.89    140.93
# 2023-12-19   196.94    141.80
# ...             ...       ...
# 2024-01-15   185.59    139.04
```

---

#### Method: `get_adjusted_value()`

Get adjusted field value applying splits, dividends, and mergers.

```python
def get_adjusted_value(
    asset: Asset,
    field: str,
    dt: pd.Timestamp,
    perspective_dt: pd.Timestamp,
    data_frequency: str,
    spot_value: float | None = None
) -> float
```

**Parameters**:
- `asset` (Asset): Asset to query
- `field` (str): Field name
- `dt` (pd.Timestamp): Timestamp of the original data
- `perspective_dt` (pd.Timestamp): Timestamp from which to view the data
- `data_frequency` (str): Data frequency - 'daily' or 'minute'
- `spot_value` (float, optional): Pre-fetched spot value (optimization)

**Returns**: float - Adjusted value

**Example**:
```python
# Get price adjusted for splits/dividends
adjusted_price = portal.get_adjusted_value(
    asset=asset,
    field="close",
    dt=pd.Timestamp("2020-01-15"),  # Historical price
    perspective_dt=pd.Timestamp("2024-01-15"),  # Adjust to this date
    data_frequency="daily"
)

# If stock had 2:1 split in 2022, historical price is adjusted
```

---

#### Method: `get_splits()`

Get splits for assets on a specific date.

```python
def get_splits(
    assets: list[Asset],
    dt: pd.Timestamp
) -> list[tuple[Asset, float]]
```

**Parameters**:
- `assets` (list[Asset]): Assets to check for splits
- `dt` (pd.Timestamp): Date to check (midnight UTC)

**Returns**: List of (asset, ratio) tuples for splits on that date

**Example**:
```python
# Check for splits on 2024-01-15
splits = portal.get_splits(
    assets=[asset1, asset2, asset3],
    dt=pd.Timestamp("2024-01-15")
)

for asset, ratio in splits:
    print(f"{asset.symbol}: {ratio}:1 split")
# Output: AAPL: 4.0:1 split (if 4:1 split occurred)
```

---

#### Method: `handle_extra_source()`

Register extra data source (Fetcher API).

```python
def handle_extra_source(
    source_df: pd.DataFrame,
    sim_params: SimulationParameters
) -> None
```

**Parameters**:
- `source_df` (pd.DataFrame): DataFrame with extra data (must have 'sid' column)
- `sim_params` (SimulationParameters): Simulation parameters

**Example**:
```python
# Add custom fundamental data
fundamentals = pd.DataFrame({
    "sid": [1, 1, 2, 2],
    "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-01", "2024-01-02"]),
    "pe_ratio": [25.3, 25.8, 30.1, 30.5],
    "market_cap": [2.5e12, 2.51e12, 1.2e12, 1.21e12]
})

portal.handle_extra_source(fundamentals, sim_params)

# Access in strategy
pe_ratio = context.portfolio.current_portfolio_weights.get("pe_ratio", asset.sid)
```

## Usage Patterns

### Pattern 1: Backtest with Adjustments

```python
# Initialize with adjustment reader
portal = DataPortal(
    asset_finder=finder,
    trading_calendar=calendar,
    first_trading_day=start_date,
    equity_daily_reader=daily_reader,
    adjustment_reader=adjustment_reader  # Enable adjustments
)

# Get adjusted history
history = portal.get_history_window(
    assets=[asset],
    end_dt=end_date,
    bar_count=252,
    frequency="1d",
    field="close",
    data_frequency="daily"
)

# History is automatically adjusted for splits/dividends
returns = history.pct_change()
```

### Pattern 2: Minute Data Backtests

```python
# Initialize with minute reader
portal = DataPortal(
    asset_finder=finder,
    trading_calendar=calendar,
    first_trading_day=start_date,
    equity_minute_reader=minute_reader
)

# Get minute bars
minute_bars = portal.get_history_window(
    assets=[asset],
    end_dt=pd.Timestamp("2024-01-15 15:00", tz="UTC"),
    bar_count=390,  # Full trading day
    frequency="1m",
    field="close",
    data_frequency="minute"
)
```

### Pattern 3: Multi-Asset Data Access

```python
# Get data for multiple assets
assets = [asset1, asset2, asset3, asset4]

# Get spot values (returns list)
current_prices = portal.get_spot_value(
    assets=assets,
    field="close",
    dt=current_dt,
    data_frequency="daily"
)

# Get history window (returns DataFrame)
price_history = portal.get_history_window(
    assets=assets,
    end_dt=current_dt,
    bar_count=20,
    frequency="1d",
    field="close",
    data_frequency="daily"
)
```

### Pattern 4: Futures and Continuous Futures

```python
# Initialize with futures readers
portal = DataPortal(
    asset_finder=finder,
    trading_calendar=calendar,
    first_trading_day=start_date,
    future_daily_reader=future_reader
)

# Access continuous futures
from rustybt.assets.continuous_futures import ContinuousFuture

cl_contract = ContinuousFuture(
    root_symbol="CL",  # Crude oil
    offset=0,  # Front month
    roll_style="volume"
)

# Get current contract price
price = portal.get_spot_value(
    assets=cl_contract,
    field="close",
    dt=current_dt,
    data_frequency="daily"
)

# Get contract chain
chain = portal.get_current_future_chain(cl_contract, current_dt)
```

## Limitations

### 1. Float64 Precision

DataPortal uses float64 for all price data, which can accumulate rounding errors in financial calculations:

```python
# Potential precision loss
price = portal.get_spot_value(asset, "close", dt, "daily")  # float64
# 123.456789012345 may become 123.45678901234500

# Solution: Use PolarsDataPortal with Decimal
from rustybt.data.polars.data_portal import PolarsDataPortal
portal = PolarsDataPortal(data_source=source)
price = portal.get_spot_value([asset], "close", dt, "daily")  # Decimal
```

### 2. Synchronous Only

DataPortal does not support async operations:

```python
# Not possible with DataPortal
# await portal.get_spot_value(...)  # No async support

# Solution: Use PolarsDataPortal
prices = await polars_portal.async_get_spot_value(...)
```

### 3. Format-Specific Readers Required

DataPortal requires separate readers for each format:

```python
# Must specify format-specific readers
portal = DataPortal(
    equity_daily_reader=BcolzDailyBarReader(...),  # Bcolz format
    equity_minute_reader=BcolzMinuteBarReader(...)  # Bcolz format
)

# Solution: PolarsDataPortal uses unified DataSource
portal = PolarsDataPortal(data_source=YFinanceAdapter())
```

## Migration to PolarsDataPortal

### Step 1: Replace Initialization

**Before**:
```python
from rustybt.data.data_portal import DataPortal
from rustybt.data.bundles import load

bundle = load("quandl")
portal = DataPortal(
    asset_finder=bundle.asset_finder,
    trading_calendar=bundle.equity_daily_bar_reader.trading_calendar,
    first_trading_day=start,
    equity_daily_reader=bundle.equity_daily_bar_reader
)
```

**After**:
```python
from rustybt.data.polars.data_portal import PolarsDataPortal
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

portal = PolarsDataPortal(
    data_source=YFinanceAdapter(),
    use_cache=True
)
```

### Step 2: Update API Calls

**Before**:
```python
# Single asset returns scalar
price = portal.get_spot_value(asset, "close", dt, "daily")  # float

# Multiple assets returns list
prices = portal.get_spot_value([asset1, asset2], "close", dt, "daily")  # list[float]
```

**After**:
```python
# Always returns Series
prices = portal.get_spot_value([asset], "close", dt, "daily")  # pl.Series
price = prices[0]  # Extract first value (Decimal)

# Multiple assets
prices = portal.get_spot_value([asset1, asset2], "close", dt, "daily")  # pl.Series
```

### Step 3: Handle Decimal Types

**Before**:
```python
price = portal.get_spot_value(asset, "close", dt, "daily")
portfolio_value = price * quantity  # float math
```

**After**:
```python
from decimal import Decimal

prices = portal.get_spot_value([asset], "close", dt, "daily")
price = prices[0]  # Decimal
portfolio_value = price * Decimal(str(quantity))  # Decimal math
```

## See Also

- [PolarsDataPortal](polars-data-portal.md) - Modern Decimal-precision portal (recommended)
- [Bar Readers](bar-reader.md) - Bar reader interface and implementations
- [Bundle System](../catalog/bundle-system.md) - Data bundle management
