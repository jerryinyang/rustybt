# Polars Data Portal

The **PolarsDataPortal** is RustyBT's modern data access interface, providing Decimal-precision OHLCV data through a unified API. It replaces the legacy pandas-based DataPortal with better performance, financial-grade precision, and a cleaner architecture.

## Overview

`PolarsDataPortal` serves as the central gateway for accessing market data during backtests and live trading. Key features:

- **Decimal Precision**: All prices use Python `Decimal` for audit-compliant calculations
- **Polars Backend**: 5-10x faster than pandas with lower memory usage
- **Unified Data Sources**: Single API for all data providers (Y Finance, CCXT, CSV, etc.)
- **Built-in Caching**: Optional disk caching for improved performance
- **Async Support**: Native async/await for non-blocking data access
- **Lookahead Protection**: Prevents accidental future data access in backtests

## Basic Usage

### Initialization

```python
from rustybt.data.polars.data_portal import PolarsDataPortal
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

# Create data source
data_source = YFinanceAdapter()

# Initialize portal with caching
portal = PolarsDataPortal(
    data_source=data_source,
    use_cache=True,
    current_simulation_time=pd.Timestamp("2024-01-01")  # For backtesting
)
```

### Get Spot Values

```python
import pandas as pd
from rustybt.assets import Asset

# Define assets
assets = [
    Asset(sid=1, symbol="AAPL"),
    Asset(sid=2, symbol="GOOGL")
]

# Get latest closing prices
prices = portal.get_spot_value(
    assets=assets,
    field="close",
    dt=pd.Timestamp("2024-01-15"),
    data_frequency="daily"
)

# prices is a Polars Series with Decimal values
print(prices)  # Series of Decimal prices
```

### Get History Window

```python
# Get 20-day price history
history = portal.get_history_window(
    assets=assets,
    end_dt=pd.Timestamp("2024-01-15"),
    bar_count=20,
    frequency="1d",
    field="close",
    data_frequency="daily"
)

# history is a Polars DataFrame with columns: date, symbol, close
print(history.head())
```

## API Reference

### Class: `PolarsDataPortal`

**Location**: `rustybt.data.polars.data_portal`

#### Constructor

```python
PolarsDataPortal(
    daily_reader: PolarsParquetDailyReader | None = None,
    minute_reader: PolarsParquetMinuteReader | None = None,
    current_simulation_time: pd.Timestamp | None = None,
    data_source: DataSource | None = None,
    use_cache: bool = True,
    *,
    asset_finder: object | None = None,
    calendar: object | None = None,
    validator: DataValidator | None = None
)
```

**Parameters**:
- `data_source` (DataSource, optional): Unified data source for fetching data (recommended)
- `use_cache` (bool, default=True): Enable disk caching for better performance
- `current_simulation_time` (pd.Timestamp, optional): Current simulation time for lookahead prevention
- `daily_reader` (PolarsParquetDailyReader, optional): **DEPRECATED** - Use `data_source` instead
- `minute_reader` (PolarsParquetMinuteReader, optional): **DEPRECATED** - Use `data_source` instead
- `asset_finder` (object, optional): Asset finder instance
- `calendar` (object, optional): Trading calendar instance
- `validator` (DataValidator, optional): Optional data validator

**Returns**: Initialized PolarsDataPortal instance

**Example**:
```python
# Modern approach (recommended)
portal = PolarsDataPortal(
    data_source=YFinanceAdapter(),
    use_cache=True
)

# Legacy approach (deprecated)
from rustybt.data.polars import PolarsParquetDailyReader
reader = PolarsParquetDailyReader("/path/to/bundle")
portal = PolarsDataPortal(daily_reader=reader)  # Deprecated warning
```

---

#### Method: `get_spot_value()`

Get current field values for one or more assets at a specific timestamp.

```python
def get_spot_value(
    assets: list[Asset],
    field: str,
    dt: pd.Timestamp,
    data_frequency: str
) -> pl.Series
```

**Parameters**:
- `assets` (list[Asset]): List of assets to query
- `field` (str): Field name - one of: 'open', 'high', 'low', 'close', 'volume'
- `dt` (pd.Timestamp): Timestamp to query
- `data_frequency` (str): Data frequency - 'daily' or 'minute'

**Returns**: Polars Series with Decimal dtype (float64 for volume)

**Raises**:
- `ValueError`: If field or data_frequency is invalid
- `NoDataAvailableError`: If data not available for the timestamp
- `LookaheadError`: If attempting to access future data in backtest mode

**Example**:
```python
assets = [Asset(sid=1, symbol="AAPL")]

# Get closing price
close_prices = portal.get_spot_value(
    assets=assets,
    field="close",
    dt=pd.Timestamp("2024-01-15"),
    data_frequency="daily"
)

# Get volume
volumes = portal.get_spot_value(
    assets=assets,
    field="volume",
    dt=pd.Timestamp("2024-01-15"),
    data_frequency="daily"
)
```

---

#### Method: `async_get_spot_value()`

Async version of `get_spot_value()` for non-blocking data access.

```python
async def async_get_spot_value(
    assets: list[Asset],
    field: str,
    dt: pd.Timestamp,
    data_frequency: str
) -> pl.Series
```

**Parameters**: Same as `get_spot_value()`

**Returns**: Polars Series with Decimal dtype

**Example**:
```python
import asyncio

async def fetch_prices():
    prices = await portal.async_get_spot_value(
        assets=[Asset(sid=1, symbol="AAPL")],
        field="close",
        dt=pd.Timestamp("2024-01-15"),
        data_frequency="daily"
    )
    return prices

prices = asyncio.run(fetch_prices())
```

---

#### Method: `get_history_window()`

Get historical window as Polars DataFrame with Decimal columns.

```python
def get_history_window(
    assets: list[Asset],
    end_dt: pd.Timestamp,
    bar_count: int,
    frequency: str,
    field: str,
    data_frequency: str
) -> pl.DataFrame
```

**Parameters**:
- `assets` (list[Asset]): List of assets to query
- `end_dt` (pd.Timestamp): End timestamp (inclusive)
- `bar_count` (int): Number of bars to retrieve (looking backward from end_dt)
- `frequency` (str): Aggregation frequency ('1d', '1h', '1m', etc.)
- `field` (str): Field name - one of: 'open', 'high', 'low', 'close', 'volume'
- `data_frequency` (str): Source data frequency ('daily' or 'minute')

**Returns**: Polars DataFrame with columns:
- `date` or `timestamp`: pl.Date or pl.Datetime
- `symbol`: pl.Utf8
- `{field}`: pl.Decimal(18, 8) or pl.Int64 for volume

**Raises**:
- `ValueError`: If parameters invalid
- `NoDataAvailableError`: If insufficient data available
- `LookaheadError`: If attempting to access future data

**Example**:
```python
# Get 20 days of closing prices
history = portal.get_history_window(
    assets=[Asset(sid=1, symbol="AAPL"), Asset(sid=2, symbol="GOOGL")],
    end_dt=pd.Timestamp("2024-01-15"),
    bar_count=20,
    frequency="1d",
    field="close",
    data_frequency="daily"
)

# Result DataFrame:
# ┌────────────┬────────┬──────────┐
# │ date       ┆ symbol ┆ close    │
# │ ---        ┆ ---    ┆ ---      │
# │ date       ┆ str    ┆ decimal  │
# ╞════════════╪════════╪══════════╡
# │ 2023-12-18 ┆ AAPL   ┆ 195.89   │
# │ 2023-12-18 ┆ GOOGL  ┆ 140.93   │
# │ ...        ┆ ...    ┆ ...      │
# └────────────┴────────┴──────────┘
```

---

#### Method: `async_get_history_window()`

Async version of `get_history_window()` for non-blocking data access.

```python
async def async_get_history_window(
    assets: list[Asset],
    end_dt: pd.Timestamp,
    bar_count: int,
    frequency: str,
    field: str,
    data_frequency: str
) -> pl.DataFrame
```

**Parameters**: Same as `get_history_window()`

**Returns**: Polars DataFrame with Decimal columns

**Example**:
```python
async def fetch_history():
    history = await portal.async_get_history_window(
        assets=[Asset(sid=1, symbol="AAPL")],
        end_dt=pd.Timestamp("2024-01-15"),
        bar_count=20,
        frequency="1d",
        field="close",
        data_frequency="daily"
    )
    return history

history = asyncio.run(fetch_history())
```

---

#### Method: `set_simulation_time()`

Set current simulation time for lookahead prevention in backtests.

```python
def set_simulation_time(dt: pd.Timestamp) -> None
```

**Parameters**:
- `dt` (pd.Timestamp): Current simulation timestamp

**Example**:
```python
# In backtest loop
for dt in trading_days:
    portal.set_simulation_time(dt)  # Prevent lookahead

    # Now queries beyond dt will raise LookaheadError
    try:
        future_price = portal.get_spot_value(
            assets=[asset],
            field="close",
            dt=dt + pd.Timedelta(days=1),  # Future!
            data_frequency="daily"
        )
    except LookaheadError as e:
        print(f"Caught lookahead attempt: {e}")
```

---

#### Property: `cache_hit_rate`

Calculate cache hit rate percentage.

```python
@property
def cache_hit_rate() -> float
```

**Returns**: Cache hit rate as percentage (0-100), or 0 if no cache requests

**Example**:
```python
# Check cache performance
print(f"Cache hit rate: {portal.cache_hit_rate:.1f}%")
# Output: Cache hit rate: 87.3%

# Access raw counts
print(f"Hits: {portal.cache_hit_count}, Misses: {portal.cache_miss_count}")
```

---

## Usage Patterns

### Pattern 1: Backtesting with Lookahead Protection

```python
# Initialize portal with simulation time
portal = PolarsDataPortal(
    data_source=YFinanceAdapter(),
    current_simulation_time=pd.Timestamp("2023-01-01")
)

# Simulate trading days
for trading_day in trading_days:
    # Update simulation time (prevents lookahead)
    portal.set_simulation_time(trading_day)

    # Fetch data (only up to trading_day is accessible)
    prices = portal.get_spot_value(
        assets=assets,
        field="close",
        dt=trading_day,
        data_frequency="daily"
    )

    # Calculate signals and place orders
    signals = calculate_signals(prices)
```

### Pattern 2: Live Trading without Lookahead Protection

```python
# Initialize without simulation time (live mode)
portal = PolarsDataPortal(
    data_source=YFinanceAdapter(),
    current_simulation_time=None,  # Live mode
    use_cache=False  # Disable caching for real-time data
)

# Fetch latest prices (no lookahead restrictions)
latest_prices = portal.get_spot_value(
    assets=assets,
    field="close",
    dt=pd.Timestamp.now(),
    data_frequency="daily"
)
```

### Pattern 3: Multi-Asset History Analysis

```python
# Fetch history for portfolio of assets
assets = [
    Asset(sid=1, symbol="AAPL"),
    Asset(sid=2, symbol="GOOGL"),
    Asset(sid=3, symbol="MSFT"),
    Asset(sid=4, symbol="AMZN")
]

# Get 1 year of daily closes
history = portal.get_history_window(
    assets=assets,
    end_dt=pd.Timestamp("2024-01-15"),
    bar_count=252,  # ~1 trading year
    frequency="1d",
    field="close",
    data_frequency="daily"
)

# Calculate returns matrix
returns = history.with_columns([
    pl.col("close").pct_change().over("symbol").alias("returns")
])

# Pivot for correlation analysis
returns_pivot = returns.pivot(
    values="returns",
    index="date",
    columns="symbol"
)
```

### Pattern 4: Async Batch Fetching

```python
import asyncio

async def fetch_all_data(portal, assets, dates):
    """Fetch data for multiple dates concurrently."""
    tasks = [
        portal.async_get_spot_value(
            assets=assets,
            field="close",
            dt=dt,
            data_frequency="daily"
        )
        for dt in dates
    ]

    results = await asyncio.gather(*tasks)
    return results

# Fetch data for multiple dates in parallel
dates = pd.date_range("2024-01-01", "2024-01-31", freq="B")
all_prices = asyncio.run(fetch_all_data(portal, assets, dates))
```

### Pattern 5: Error Handling and Fallbacks

```python
from rustybt.data.polars.data_portal import NoDataAvailableError, LookaheadError

def safe_get_price(portal, asset, dt, field="close"):
    """Get price with fallback to previous trading day."""
    try:
        prices = portal.get_spot_value(
            assets=[asset],
            field=field,
            dt=dt,
            data_frequency="daily"
        )
        return prices[0]
    except NoDataAvailableError:
        # Try previous trading day
        try:
            prev_day = dt - pd.Timedelta(days=1)
            prices = portal.get_spot_value(
                assets=[asset],
                field=field,
                dt=prev_day,
                data_frequency="daily"
            )
            logger.warning(f"Using previous day price for {asset.symbol}")
            return prices[0]
        except NoDataAvailableError:
            logger.error(f"No data available for {asset.symbol}")
            return None
    except LookaheadError as e:
        logger.error(f"Lookahead bias detected: {e}")
        raise
```

## Performance Optimization

### Caching Strategy

```python
# Enable caching for backtests (repeated data access)
backtest_portal = PolarsDataPortal(
    data_source=YFinanceAdapter(),
    use_cache=True  # Disk caching enabled
)

# Disable caching for live trading (always fresh data)
live_portal = PolarsDataPortal(
    data_source=YFinanceAdapter(),
    use_cache=False  # No caching
)

# Monitor cache performance
print(f"Cache hit rate: {backtest_portal.cache_hit_rate:.1f}%")
```

### Batch Queries

```python
# GOOD: Single query for multiple assets
assets = [Asset(sid=i, symbol=sym) for i, sym in enumerate(symbols)]
prices = portal.get_spot_value(assets, "close", dt, "daily")

# AVOID: Multiple queries (inefficient)
prices = []
for asset in assets:
    price = portal.get_spot_value([asset], "close", dt, "daily")
    prices.append(price[0])
```

### Appropriate Window Sizes

```python
# Request only what you need
sma_window = 20  # Need 20 bars for SMA
history = portal.get_history_window(
    assets=assets,
    end_dt=dt,
    bar_count=sma_window,  # Exact window needed
    frequency="1d",
    field="close",
    data_frequency="daily"
)

# Calculate SMA
sma = history.group_by("symbol").agg([
    pl.col("close").tail(20).mean().alias("sma_20")
])
```

## Exceptions

### `NoDataAvailableError`

Raised when requested data is not available.

**Common causes**:
- Market closed on requested date
- Asset not trading on requested date
- Data not yet ingested for recent dates

**Example**:
```python
try:
    prices = portal.get_spot_value(
        assets=[Asset(sid=1, symbol="AAPL")],
        field="close",
        dt=pd.Timestamp("2024-01-01"),  # New Year's Day
        data_frequency="daily"
    )
except NoDataAvailableError as e:
    print(f"No data: {e}")  # Market closed
```

### `LookaheadError`

Raised when attempting to access future data in backtest mode.

**Common causes**:
- Querying beyond current_simulation_time
- Bug in backtest logic accessing future dates

**Example**:
```python
portal.set_simulation_time(pd.Timestamp("2024-01-15"))

try:
    # This will raise LookaheadError
    future_price = portal.get_spot_value(
        assets=[asset],
        field="close",
        dt=pd.Timestamp("2024-01-16"),  # Future!
        data_frequency="daily"
    )
except LookaheadError as e:
    print(f"Lookahead detected: {e}")
```

## Migration from Legacy DataPortal

### Before (pandas DataPortal)

```python
from rustybt.data.data_portal import DataPortal

portal = DataPortal(
    asset_finder=finder,
    trading_calendar=calendar,
    first_trading_day=start,
    equity_daily_reader=reader
)

# Get single asset price (float64)
price = portal.get_spot_value(
    assets=asset,  # Single asset
    field="close",
    dt=dt,
    data_frequency="daily"
)  # Returns float
```

### After (Polars DataPortal)

```python
from rustybt.data.polars.data_portal import PolarsDataPortal
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

portal = PolarsDataPortal(
    data_source=YFinanceAdapter(),
    use_cache=True
)

# Get asset price (Decimal)
prices = portal.get_spot_value(
    assets=[asset],  # List of assets
    field="close",
    dt=dt,
    data_frequency="daily"
)  # Returns pl.Series with Decimal

# Extract single value if needed
price = prices[0]  # Decimal
```

## See Also

- [Data Portal (Legacy)](data-portal.md) - pandas-based DataPortal reference
- [Data Sources](../adapters/README.md) - Available data sources
- [Bar Readers](bar-reader.md) - Bar reader interface
- [Daily Bar Readers](daily-bars.md) - Daily bar reader implementations
- [Readers Overview](README.md) - Architecture comparison and best practices
