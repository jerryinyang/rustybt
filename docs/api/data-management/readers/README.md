# Data Reading Components

The data reading system provides unified access to OHLCV data across multiple storage formats and data frequencies. This section documents the Data Portal, Bar Readers, and History Loaders that form the core of RustyBT's data access layer.

## Overview

RustyBT provides two data reading architectures:

1. **Legacy Architecture** (Zipline-based):
   - `DataPortal` - Central data access interface
   - Format-specific bar readers (Bcolz, HDF5, Parquet)
   - Dispatch readers for multi-format support
   - History loaders with adjustment support

2. **Modern Architecture** (Polars-based):
   - `PolarsDataPortal` - Decimal-precision data portal
   - Unified DataSource abstraction
   - Native Parquet support
   - Optional caching layer

## Key Components

### Data Portal
Central interface for accessing market data during backtests and live trading.

- **[DataPortal](data-portal.md)** - Legacy pandas-based portal
- **[PolarsDataPortal](polars-data-portal.md)** - Modern Decimal-precision portal

### Bar Readers
Format-specific implementations for reading OHLCV bars.

- **[Bar Reader Interface](bar-reader.md)** - Abstract base class and dispatch system
- **[Daily Bar Readers](daily-bars.md)** - Daily and minute frequency readers

### Data Access Patterns
Common patterns for accessing market data efficiently are covered throughout:

- **[PolarsDataPortal Patterns](polars-data-portal.md#usage-patterns)** - Modern data access patterns
- **[Daily Bar Patterns](daily-bars.md#usage-patterns)** - Efficient bar loading techniques

## Quick Start

### Using PolarsDataPortal (Recommended)

```python
from rustybt.data.polars.data_portal import PolarsDataPortal
from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter
from rustybt.assets import Asset

# Initialize with unified data source
data_source = YFinanceAdapter()
portal = PolarsDataPortal(
    data_source=data_source,
    use_cache=True
)

# Get spot values
assets = [Asset(sid=1, symbol="AAPL")]
prices = portal.get_spot_value(
    assets=assets,
    field="close",
    dt=pd.Timestamp("2024-01-15"),
    data_frequency="daily"
)

# Get history window
history = portal.get_history_window(
    assets=assets,
    end_dt=pd.Timestamp("2024-01-15"),
    bar_count=20,
    frequency="1d",
    field="close",
    data_frequency="daily"
)
```

### Using DataPortal (Legacy)

```python
from rustybt.data.data_portal import DataPortal
from rustybt.data.bundles import load
from rustybt.assets import AssetFinder

# Load bundle
bundle_data = load("my_bundle")

# Create portal
portal = DataPortal(
    asset_finder=bundle_data.asset_finder,
    trading_calendar=bundle_data.calendar,
    first_trading_day=pd.Timestamp("2020-01-01"),
    equity_daily_reader=bundle_data.equity_daily_bar_reader
)

# Access data
price = portal.get_spot_value(
    assets=asset,
    field="close",
    dt=pd.Timestamp("2024-01-15"),
    data_frequency="daily"
)
```

## Architecture Comparison

| Feature | PolarsDataPortal | DataPortal (Legacy) |
|---------|------------------|---------------------|
| Data Precision | Decimal (financial-grade) | float64 |
| DataFrame Library | Polars | pandas |
| Data Sources | Unified DataSource API | Format-specific readers |
| Caching | Built-in optional | Manual |
| Async Support | Yes (native) | No |
| Performance | 5-10x faster | Baseline |
| Memory Usage | Lower (columnar) | Higher |
| Lookahead Protection | Built-in | Manual |

## When to Use Which

### Use PolarsDataPortal when:
- Starting new strategies
- Need Decimal precision for financial calculations
- Want unified data source abstraction
- Performance is critical
- Working with large datasets

### Use DataPortal (Legacy) when:
- Maintaining existing Zipline strategies
- Need specific Zipline features
- Compatibility with old bundle formats

## Common Use Cases

### Backtesting
Both portals integrate with `TradingAlgorithm` for backtesting:

```python
from rustybt.algorithm import TradingAlgorithm

class MyStrategy(TradingAlgorithm):
    def initialize(self, context):
        self.asset = self.symbol("AAPL")

    def handle_data(self, context, data):
        # Data portal used internally
        price = data.current(self.asset, "close")
        history = data.history(self.asset, "close", 20, "1d")
```

### Live Trading
```python
from rustybt.live import LiveTradingEngine

# Portal automatically created with real-time data
engine = LiveTradingEngine(
    strategy=MyStrategy(),
    data_source=YFinanceAdapter(),
    use_cache=False  # Disable caching for live data
)
```

### Research and Analysis
```python
# Direct portal usage for research
portal = PolarsDataPortal(data_source=YFinanceAdapter())

# Fetch historical data
data = portal.get_history_window(
    assets=[Asset(sid=1, symbol="AAPL")],
    end_dt=pd.Timestamp("2024-01-15"),
    bar_count=252,  # 1 year of daily data
    frequency="1d",
    field="close",
    data_frequency="daily"
)

# Analyze with Polars
returns = data.with_columns([
    (pl.col("close").pct_change()).alias("returns")
])
```

## Performance Considerations

### Caching
Enable caching for frequently accessed data:

```python
portal = PolarsDataPortal(
    data_source=data_source,
    use_cache=True  # Enables disk caching
)

# Check cache statistics
print(f"Cache hit rate: {portal.cache_hit_rate:.1f}%")
```

### Batch Queries
Query multiple assets at once for better performance:

```python
# GOOD: Single query for multiple assets
assets = [
    Asset(sid=1, symbol="AAPL"),
    Asset(sid=2, symbol="GOOGL"),
    Asset(sid=3, symbol="MSFT")
]
prices = portal.get_spot_value(assets, "close", dt, "daily")

# AVOID: Multiple queries for single assets
for asset in assets:
    price = portal.get_spot_value([asset], "close", dt, "daily")
```

### History Window Sizing
Request appropriate window sizes:

```python
# Efficient: Request exact window needed
window = portal.get_history_window(
    assets=assets,
    end_dt=end_dt,
    bar_count=20,  # Only 20 bars needed
    frequency="1d",
    field="close",
    data_frequency="daily"
)

# Inefficient: Requesting too much data
large_window = portal.get_history_window(
    assets=assets,
    bar_count=5000,  # Excessive if only need 20
    ...
)
```

## Error Handling

### Common Exceptions

```python
from rustybt.data.polars.data_portal import (
    NoDataAvailableError,
    LookaheadError
)

try:
    prices = portal.get_spot_value(assets, "close", dt, "daily")
except NoDataAvailableError as e:
    # Handle missing data (market closed, no data for date, etc.)
    logger.warning(f"No data available: {e}")
    prices = None
except LookaheadError as e:
    # Handle attempted future data access
    logger.error(f"Lookahead bias detected: {e}")
    raise
```

## Migration from pandas DataPortal

### Before (DataPortal)
```python
portal = DataPortal(
    asset_finder=finder,
    trading_calendar=calendar,
    first_trading_day=start,
    equity_daily_reader=reader
)

price = portal.get_spot_value(asset, "close", dt, "daily")  # float64
```

### After (PolarsDataPortal)
```python
portal = PolarsDataPortal(
    data_source=YFinanceAdapter(),
    use_cache=True
)

prices = portal.get_spot_value([asset], "close", dt, "daily")  # Decimal
```

## See Also

- [Data Portal Reference](data-portal.md) - Legacy DataPortal API
- [Polars Data Portal Reference](polars-data-portal.md) - Modern portal API
- [Bar Readers](bar-reader.md) - Bar reader interface and implementations
- [Daily Bar Readers](daily-bars.md) - Daily bar loading patterns and best practices
- [Bundle System](../catalog/bundle-system.md) - Data bundle management
