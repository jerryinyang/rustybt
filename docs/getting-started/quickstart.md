# Quick Start Guide

This guide will help you write and run your first trading strategy with RustyBT.

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

## Run the Backtest

```bash
rustybt run -f my_strategy.py --start 2020-01-01 --end 2023-12-31
```

## Understanding the Output

RustyBT will display:
- Trade execution logs
- Performance metrics
- Final portfolio statistics

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
