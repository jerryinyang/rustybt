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
rustybt run -f my_strategy.py -b yfinance-profiling --start 2020-01-01 --end 2023-12-31
```

Note the `-b yfinance-profiling` flag to specify which data bundle to use.

## Understanding the Output

RustyBT will display:
- Trade execution logs
- Performance metrics
- Final portfolio statistics

## Troubleshooting

### Common Issues

**"no data for bundle"**
```bash
# Solution: Ingest data first
rustybt ingest -b yfinance-profiling

# Then run with the bundle flag
rustybt run -f my_strategy.py -b yfinance-profiling --start 2020-01-01 --end 2023-12-31
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
