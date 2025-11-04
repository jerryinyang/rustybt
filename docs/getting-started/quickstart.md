# Quick Start Guide

This guide will help you write and run your first trading strategy with RustyBT.

## Installation

If you haven't installed RustyBT yet:

```bash
pip install rustybt
```

For more installation options, see the [Installation Guide](installation.md).

## Your First Strategy

Create a file called `my_strategy.py`:

```python
from rustybt.api import order_target, record, symbol

def initialize(context):
    """Initialize strategy - called once at start."""
    context.i = 0
    context.asset = symbol('AAPL')

def handle_data(context, data):
    """Handle each bar of data - called on every trading day."""
    # Skip first 300 days to get full windows
    context.i += 1
    if context.i < 300:
        return

    # Compute moving averages
    short_mavg = data.history(
        context.asset,
        'price',
        bar_count=100,
        frequency="1d"
    ).mean()

    long_mavg = data.history(
        context.asset,
        'price',
        bar_count=300,
        frequency="1d"
    ).mean()

    # Trading logic: Buy when short MA > long MA
    if short_mavg > long_mavg:
        order_target(context.asset, 100)
    elif short_mavg < long_mavg:
        order_target(context.asset, 0)

    # Record values for analysis
    record(
        AAPL=data.current(context.asset, 'price'),
        short_mavg=short_mavg,
        long_mavg=long_mavg
    )
```

## Ingest Sample Data

Before running your first backtest, you need to ingest some market data:

```bash
rustybt ingest -b yfinance-profiling
```

This downloads and caches free sample data from Yahoo Finance (20 top US stocks, 2 years of history). **No API key required!** You only need to do this once.

!!! note "Data Bundles"
    RustyBT supports multiple data sources:
    - **yfinance-profiling**: Free Yahoo Finance data (recommended for quick start)
    - **csvdir**: Your own CSV files - see [CSV Data Import](../guides/csv-data-import.md)
    - **Custom adapters**: Live data sources - see [Creating Data Adapters](../guides/creating-data-adapters.md)

## Run the Backtest

```bash
rustybt run -f my_strategy.py -b yfinance-profiling --start 2024-01-01 --end 2025-09-30
```

Note the `-b yfinance-profiling` flag to specify which data bundle to use.

!!! important "Bundle Date Range"
    The **yfinance-profiling** bundle fetches the last 2 years of data from today. The dates shown above (2024-01-01 to 2025-09-30) are examples that work with data ingested in October 2025.

    If you ingested data at a different time, adjust your dates accordingly. Use dates within the last year of your ingested data to ensure the 300-day moving average has enough historical data.

## Alternative: Python API Execution

You can also run strategies directly from Python without the CLI. This provides a more Pythonic workflow with better IDE integration and debugging support.

Update your `my_strategy.py` to include execution code:

```python
from rustybt.api import order_target, record, symbol
from rustybt.utils.run_algo import run_algorithm
import pandas as pd

def initialize(context):
    """Initialize strategy - called once at start."""
    context.i = 0
    context.asset = symbol('AAPL')

def handle_data(context, data):
    """Handle each bar of data - called on every trading day."""
    context.i += 1
    if context.i < 300:
        return

    # Compute moving averages
    short_mavg = data.history(context.asset, 'price', bar_count=100, frequency="1d").mean()
    long_mavg = data.history(context.asset, 'price', bar_count=300, frequency="1d").mean()

    # Trading logic
    if short_mavg > long_mavg:
        order_target(context.asset, 100)
    elif short_mavg < long_mavg:
        order_target(context.asset, 0)

    # Record values for analysis
    record(
        AAPL=data.current(context.asset, 'price'),
        short_mavg=short_mavg,
        long_mavg=long_mavg
    )

if __name__ == "__main__":
    result = run_algorithm(
        initialize=initialize,
        handle_data=handle_data,
        bundle='yfinance-profiling',
        start=pd.Timestamp('2024-01-01'),
        end=pd.Timestamp('2025-09-30'),
        capital_base=10000,
        data_frequency='daily'
    )

    print(f"\n{'='*50}")
    print("Backtest Results")
    print(f"{'='*50}")
    print(f"Total return: {result['returns'].iloc[-1]:.2%}")
    print(f"Sharpe ratio: {result['sharpe']:.2f}")
    print(f"Max drawdown: {result['max_drawdown']:.2%}")
    print(f"{'='*50}\n")
```

Then run with:

```bash
python my_strategy.py
```

**Benefits of Python API**:

- ✅ Standard Python development workflow
- ✅ Easy debugging with IDE breakpoints
- ✅ Better integration with notebooks and scripts
- ✅ Direct access to results DataFrame for analysis
- ✅ More Pythonic and familiar to Python developers

## Understanding the Output

RustyBT will display:
- Trade execution logs
- Performance metrics
- Final portfolio statistics

## Working with Multiple Assets

The examples above show trading a single hardcoded asset (`AAPL`). In practice, you often want to work with multiple assets or all assets in a bundle.

### Retrieve All Assets Programmatically

Instead of hardcoding symbols, retrieve all available assets from your bundle:

```python
from rustybt.api import order_target_percent, record
from rustybt.utils.run_algo import run_algorithm
import pandas as pd

def initialize(context):
    """Initialize with all assets in bundle."""
    # Get all asset identifiers
    all_sids = context.asset_finder.sids

    # Retrieve all asset objects
    all_assets = context.asset_finder.retrieve_all(all_sids)

    # Store for use in handle_data
    context.assets = all_assets

    print(f"Found {len(all_assets)} assets:")
    for asset in all_assets[:5]:  # Show first 5
        print(f"  - {asset.symbol}")

def handle_data(context, data):
    """Equal-weight portfolio across all assets."""
    # Calculate equal weight for each asset
    weight = 1.0 / len(context.assets)

    # Rebalance to equal weights
    for asset in context.assets:
        order_target_percent(asset, weight)

if __name__ == "__main__":
    result = run_algorithm(
        initialize=initialize,
        handle_data=handle_data,
        bundle='yfinance-profiling',
        start=pd.Timestamp('2024-06-01'),
        end=pd.Timestamp('2025-09-30'),
        capital_base=10000,
    )
```

### Select Specific Assets by Symbol

Look up specific assets instead of hardcoding:

```python
def initialize(context):
    """Select a custom watchlist."""
    # Define your watchlist
    watchlist_symbols = ['AAPL', 'GOOGL', 'MSFT', 'AMZN']

    # Look up assets
    context.watchlist = context.asset_finder.lookup_symbols(watchlist_symbols)

    print(f"Tracking {len(context.watchlist)} assets")

def handle_data(context, data):
    """Trade your custom watchlist."""
    for asset in context.watchlist:
        price = data.current(asset, 'price')
        # Your trading logic here
```

### Filter Assets Dynamically

Build custom filters to select assets:

```python
def initialize(context):
    """Select assets matching criteria."""
    # Get all assets
    all_assets = context.asset_finder.retrieve_all(context.asset_finder.sids)

    # Filter assets (example: select first 10)
    # In production, you might filter by market cap, volume, sector, etc.
    context.universe = all_assets[:10]

    print(f"Selected {len(context.universe)} assets for trading")
```

!!! tip "Performance Tip"
    Always look up assets once in `initialize()` and store them in `context`. Avoid looking up assets repeatedly in `handle_data()` - this is slow!

For complete API documentation, see [Asset Finder API](../api/data-management/asset-finder.md).

## Class-Based API (Alternative Style)

RustyBT also supports a **class-based API** for organizing complex strategies. This style is particularly useful when:
- You have multiple helper methods
- You're organizing code into reusable strategy classes
- You prefer object-oriented programming patterns

### Class-Based Example

Create a file called `my_class_strategy.py`:

```python
from rustybt import TradingAlgorithm
from rustybt.api import order_target, record, symbol

class MovingAverageStrategy(TradingAlgorithm):
    """
    Class-based moving average crossover strategy.

    IMPORTANT: Method signatures differ from functional API:
    - initialize(self) instead of initialize(context)
    - handle_data(self, context, data) instead of handle_data(context, data)
    """

    def initialize(self):
        """Initialize strategy - NO context parameter, just self."""
        self.asset = symbol('AAPL')
        self.i = 0

    def handle_data(self, context, data):
        """Handle each bar - note the self parameter first."""
        self.i += 1
        if self.i < 300:
            return

        # Use helper method (class-based advantage!)
        short_mavg, long_mavg = self.calculate_moving_averages(data)

        # Trading logic
        if short_mavg > long_mavg:
            order_target(self.asset, 100)
        elif short_mavg < long_mavg:
            order_target(self.asset, 0)

        # Record for analysis
        record(AAPL=data.current(self.asset, 'price'),
               short_mavg=short_mavg,
               long_mavg=long_mavg)

    def calculate_moving_averages(self, data):
        """Helper method - natural with class-based API."""
        short_mavg = data.history(
            self.asset, 'price', bar_count=100, frequency="1d"
        ).mean()

        long_mavg = data.history(
            self.asset, 'price', bar_count=300, frequency="1d"
        ).mean()

        return short_mavg, long_mavg
```

### Running Class-Based Strategies

Class-based strategies run via CLI:

```bash
rustybt run -f my_class_strategy.py -b quandl --start 2020-01-01 --end 2023-12-31
```

**The framework automatically detects your `TradingAlgorithm` subclass!**

!!! note "API Style Compatibility"
    - **CLI (`rustybt run -f`)**: Supports BOTH functional and class-based
    - **`run_algorithm()`**: Supports ONLY functional API
    - **Notebooks**: Prefer functional API with `run_algorithm()`

    See [API Styles Guide](../guides/api-styles.md) for complete comparison.

### Key Differences from Functional API

| Aspect | Functional API | Class-Based API |
|--------|---------------|-----------------|
| **Structure** | Top-level functions | `TradingAlgorithm` subclass |
| **initialize** | `def initialize(context)` | `def initialize(self)` |
| **handle_data** | `def handle_data(context, data)` | `def handle_data(self, context, data)` |
| **State storage** | `context.my_var = value` | `self.my_var = value` |
| **Helper methods** | Module-level functions | Class methods |
| **Best for** | Notebooks, quick prototypes | Complex strategies, CLI execution |

For complete details, see the [API Styles Guide](../guides/api-styles.md).

## Troubleshooting

### Common Issues

**"no data for bundle"**
```bash
# Solution: Ingest data first
rustybt ingest -b yfinance-profiling

# Then run with the bundle flag
rustybt run -f my_strategy.py -b yfinance-profiling --start 2024-01-01 --end 2025-09-30
```

**"Error: No bundle registered with the name 'yfinance-profiling'"**
```bash
# Solution: Upgrade to latest rustybt version
pip install --upgrade rustybt
```

**"fatal: bad revision 'HEAD'" or Segmentation Fault**
```bash
# Solution: Reinstall rustybt
pip install --upgrade --force-reinstall rustybt
```

This usually happens when installing from a non-git directory or with a corrupted installation.

**"ModuleNotFoundError" or Import Errors**
```bash
# Solution: Check Python version and reinstall
python --version  # Should be 3.12 or higher
pip install --upgrade rustybt
```

**"Quandl API key required"**

If you see errors about Quandl requiring an API key, you're using the old default bundle. Switch to the free Yahoo Finance bundle:

```bash
rustybt ingest -b yfinance-profiling
rustybt run -f my_strategy.py -b yfinance-profiling --start 2020-01-01 --end 2023-12-31
```

**Data Issues**
- For custom data: See [CSV Data Import Guide](../guides/csv-data-import.md)
- For live data: See [Creating Data Adapters Guide](../guides/creating-data-adapters.md)
- For debugging: See [Troubleshooting Guide](../guides/troubleshooting.md)

## Next Steps

### Learn More Features

- [Decimal Precision](../guides/decimal-precision-configuration.md) - Financial-grade calculations
- [Data Adapters](../guides/creating-data-adapters.md) - Import custom data
- [Order Types](../api/order-types.md) - Advanced order types

### Try Advanced Examples

- **Multi-Strategy Portfolio**: See `examples/allocation_algorithms_tutorial.py`
- **Strategy Optimization**: See `examples/optimization/`
- **Live Trading**: See [Testnet Setup Guide](../guides/testnet-setup-guide.md)

### Explore the API

- [Examples & Tutorials](../examples/README.md) - Learn by example
- [API Documentation](../api/order-types.md) - Complete API reference
- [User Guides](../guides/decimal-precision-configuration.md) - Feature guides
