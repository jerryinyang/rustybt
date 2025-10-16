# Data Portal

The Data Portal provides a unified interface for accessing market data from bundles during backtests and live trading.

## Overview

The Data Portal abstracts away the complexity of different data formats (Parquet, HDF5, bcolz) and provides consistent data access through a simple API.

## Quick Start

```python
from rustybt.data.data_portal import DataPortal
from rustybt.data.bundles import load
import pandas as pd

# Load bundle
bundle_data = load('my_bundle')

# Create data portal
portal = DataPortal(
    asset_finder=bundle_data.asset_finder,
    trading_calendar=get_calendar('NYSE'),
    first_trading_day=pd.Timestamp('2023-01-01'),
    equity_daily_reader=bundle_data.equity_daily_bar_reader
)

# Get current price
asset = symbol('AAPL')
current_price = portal.get_spot_value(
    asset,
    'close',
    pd.Timestamp('2023-01-15')
)
```

## Core Methods

### get_spot_value()

Get single field value at specific timestamp:

```python
price = portal.get_spot_value(asset, 'close', dt)
volume = portal.get_spot_value(asset, 'volume', dt)
```

### get_history_window()

Get historical data for multiple assets:

```python
# Last 20 days of close prices
prices = portal.get_history_window(
    assets=[asset1, asset2],
    end_dt=pd.Timestamp('2023-01-15'),
    bar_count=20,
    frequency='1d',
    field='close'
)
```

### get_adjusted_value()

Get split/dividend-adjusted prices:

```python
adjusted_price = portal.get_adjusted_value(
    asset,
    'close',
    dt,
    perspective_dt=None  # Adjust as of latest perspective
)
```

## Data Access Patterns

### Pattern 1: Current Bar Access

```python
def handle_data(context, data):
    # Access current bar via data object (wraps portal)
    current_price = data.current(context.asset, 'close')
    current_volume = data.current(context.asset, 'volume')
```

### Pattern 2: Historical Window

```python
def handle_data(context, data):
    # Get last 20 bars
    prices = data.history(
        context.asset,
        fields='close',
        bar_count=20,
        frequency='1d'
    )

    # Calculate moving average
    sma_20 = prices.mean()
```

### Pattern 3: Multi-Asset History

```python
def before_trading_start(context, data):
    # Get history for multiple assets
    prices = data.history(
        [context.aapl, context.msft, context.googl],
        fields=['open', 'high', 'low', 'close'],
        bar_count=30,
        frequency='1d'
    )
```

## See [Bar Readers](bar-readers.md) for underlying reader implementations.
