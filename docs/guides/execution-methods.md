# Execution Methods

This guide covers all the ways you can run trading strategies in RustyBT, helping you choose the right execution method for your workflow.

## Overview

RustyBT offers multiple execution methods to fit different development workflows:

| Method | Best For | Pros | Cons |
|--------|----------|------|------|
| **CLI** | Quick testing, production scripts | Simple, scriptable | Less IDE integration |
| **Python API** | Development, debugging | IDE support, Pythonic | Requires code changes |
| **Jupyter Notebooks** | Research, exploration | Interactive, visual | Not for production |
| **Class-based** | Complex strategies, Pipeline API | Organized, reusable | More boilerplate |
| **Function-based** | Simple strategies, quick tests | Minimal code | Limited structure |

## CLI Execution

### Basic Usage

The command-line interface provides the simplest way to run strategies:

```bash
rustybt run -f my_strategy.py -b yfinance-profiling --start 2020-01-01 --end 2023-12-31
```

### CLI Options

```bash
rustybt run [OPTIONS]

Options:
  -f, --file PATH              Strategy file (required)
  -b, --bundle TEXT            Data bundle name (default: quantopian-quandl)
  --start DATE                 Start date (YYYY-MM-DD)
  --end DATE                   End date (YYYY-MM-DD)
  --capital-base FLOAT         Starting capital (default: 10000)
  --data-frequency TEXT        'daily' or 'minute' (default: daily)
  -o, --output PATH            Output file for results
  --help                       Show help message
```

### Complete CLI Example

```python
# momentum_strategy.py
from rustybt.api import order_target_percent, symbol, record

def initialize(context):
    """Initialize strategy."""
    context.assets = [symbol('AAPL'), symbol('MSFT'), symbol('GOOGL')]
    context.lookback = 20

def handle_data(context, data):
    """Execute on each bar."""
    for asset in context.assets:
        # Calculate momentum
        prices = data.history(asset, 'price', context.lookback, '1d')
        momentum = (prices[-1] - prices[0]) / prices[0]

        # Trade on momentum signal
        if momentum > 0.02:  # 2% threshold
            order_target_percent(asset, 0.33)
        elif momentum < -0.02:
            order_target_percent(asset, 0)

        record(**{asset.symbol: prices[-1], f"{asset.symbol}_momentum": momentum})
```

Run with:

```bash
rustybt run -f momentum_strategy.py -b yfinance-profiling --start 2020-01-01 --end 2023-12-31 --capital-base 100000
```

### Advantages

✅ Simple one-line execution
✅ Easy to script and automate
✅ No code modifications needed
✅ Works with cron jobs and schedulers

### Limitations

❌ Limited IDE debugging support
❌ Results printed to console (need `-o` for file output)
❌ Less flexible for programmatic access

---

## Python API Execution

### Basic Usage

The Python API provides a more Pythonic way to run strategies with better IDE integration:

```python
from rustybt.utils.run_algo import run_algorithm
import pandas as pd

result = run_algorithm(
    initialize=initialize,
    handle_data=handle_data,
    bundle='yfinance-profiling',
    start=pd.Timestamp('2020-01-01'),
    end=pd.Timestamp('2023-12-31'),
    capital_base=10000
)
```

### Function Signature

```python
def run_algorithm(
    start: datetime,
    end: datetime,
    initialize: callable,
    capital_base: float,
    handle_data: callable = None,
    before_trading_start: callable = None,
    analyze: callable = None,
    data_frequency: str = 'daily',
    bundle: str = 'quantopian-quandl',
    bundle_timestamp: datetime = None,
    trading_calendar: TradingCalendar = None,
    metrics_set: str = 'default',
    benchmark_returns: pd.Series = None,
    blotter: str = 'default'
) -> pd.DataFrame
```

### Complete Python API Example

```python
# momentum_strategy.py
from rustybt.api import order_target_percent, symbol, record
from rustybt.utils.run_algo import run_algorithm
import pandas as pd

def initialize(context):
    """Initialize strategy."""
    context.assets = [symbol('AAPL'), symbol('MSFT'), symbol('GOOGL')]
    context.lookback = 20

def handle_data(context, data):
    """Execute on each bar."""
    for asset in context.assets:
        prices = data.history(asset, 'price', context.lookback, '1d')
        momentum = (prices[-1] - prices[0]) / prices[0]

        if momentum > 0.02:
            order_target_percent(asset, 0.33)
        elif momentum < -0.02:
            order_target_percent(asset, 0)

        record(**{asset.symbol: prices[-1], f"{asset.symbol}_momentum": momentum})

if __name__ == "__main__":
    result = run_algorithm(
        initialize=initialize,
        handle_data=handle_data,
        bundle='yfinance-profiling',
        start=pd.Timestamp('2020-01-01'),
        end=pd.Timestamp('2023-12-31'),
        capital_base=100000,
        data_frequency='daily'
    )

    # Access results directly
    print(f"\n{'='*60}")
    print("Backtest Results")
    print(f"{'='*60}")
    print(f"Total Return:    {result['returns'].iloc[-1]:.2%}")
    print(f"Sharpe Ratio:    {result['sharpe']:.2f}")
    print(f"Max Drawdown:    {result['max_drawdown']:.2%}")
    print(f"Final Value:     ${result['portfolio_value'].iloc[-1]:,.2f}")
    print(f"{'='*60}\n")

    # Save results
    result.to_csv('backtest_results.csv')

    # Advanced analysis
    import matplotlib.pyplot as plt
    result['portfolio_value'].plot(title='Portfolio Value Over Time')
    plt.savefig('portfolio_chart.png')
```

Run with:

```bash
python momentum_strategy.py
```

### Advantages

✅ Full IDE debugging support (breakpoints, step-through)
✅ Direct access to results DataFrame
✅ Easy integration with notebooks and scripts
✅ More Pythonic and familiar workflow
✅ Programmatic results handling

### Limitations

❌ Requires code modifications
❌ More verbose than CLI

---

## Class-Based vs Function-Based

### Function-Based Strategies

**Best for:** Simple strategies, quick prototypes, learning

```python
def initialize(context):
    context.asset = symbol('AAPL')

def handle_data(context, data):
    price = data.current(context.asset, 'price')
    if price > 150:
        order(context.asset, 100)

# Run with CLI or Python API
run_algorithm(initialize=initialize, handle_data=handle_data, ...)
```

**Advantages:**
- Minimal boilerplate
- Quick to write
- Easy to understand

**Limitations:**
- Limited organization for complex logic
- No class methods or inheritance
- Cannot use Pipeline API

### Class-Based Strategies

**Best for:** Complex strategies, Pipeline API, production code

```python
from rustybt.algorithm import TradingAlgorithm
from rustybt.pipeline import Pipeline

class MomentumStrategy(TradingAlgorithm):
    """Complex strategy using Pipeline API."""

    def initialize(self):
        """Initialize with state and pipeline."""
        self.lookback = 20
        self.threshold = 0.02

        # Attach pipeline for screening
        pipe = self.make_pipeline()
        self.attach_pipeline(pipe, 'momentum_screen')

        # Schedule functions
        self.schedule_function(
            self.rebalance,
            self.date_rules.week_start(),
            self.time_rules.market_open()
        )

    def make_pipeline(self):
        """Create data pipeline."""
        from rustybt.pipeline.factors import Returns
        momentum = Returns(window_length=self.lookback)
        return Pipeline(
            columns={'momentum': momentum},
            screen=momentum.top(50)
        )

    def rebalance(self, context, data):
        """Rebalance portfolio."""
        pipeline_data = self.pipeline_output('momentum_screen')
        target_assets = set(pipeline_data.index)

        # Equal weight allocation
        weight = 1.0 / len(target_assets) if target_assets else 0
        for asset in target_assets:
            self.order_target_percent(asset, weight)

    def handle_data(self, context, data):
        """Monitor and log."""
        self.log.info(f"Portfolio value: ${context.portfolio.portfolio_value:,.2f}")

# Save to momentum_strategy.py and run with CLI
# rustybt run -f momentum_strategy.py -b yfinance-profiling \
#   --start 2020-01-01 --end 2023-12-31 --capital-base 100000
```

!!! important "Class-Based Strategies Require CLI"
    Strategies inheriting from `TradingAlgorithm` **must** be run using the CLI (`rustybt run -f`). The Python API `run_algorithm()` function does not support class-based strategies.

**Advantages:**
- Organized code structure
- Supports Pipeline API
- Reusable through inheritance
- State encapsulation
- Method reuse

**Limitations:**
- More boilerplate
- Steeper learning curve

---

## Jupyter Notebook Execution

### Interactive Development

Jupyter notebooks provide an interactive environment for strategy development and analysis:

```python
# Cell 1: Imports and setup
from rustybt.api import order_target_percent, symbol
from rustybt.utils.run_algo import run_algorithm
import pandas as pd
import matplotlib.pyplot as plt

# Cell 2: Define strategy
def initialize(context):
    context.asset = symbol('AAPL')

def handle_data(context, data):
    price = data.current(context.asset, 'price')
    ma_20 = data.history(context.asset, 'price', 20, '1d').mean()

    if price > ma_20:
        order_target_percent(context.asset, 1.0)
    else:
        order_target_percent(context.asset, 0)

# Cell 3: Run backtest
result = run_algorithm(
    initialize=initialize,
    handle_data=handle_data,
    bundle='yfinance-profiling',
    start=pd.Timestamp('2020-01-01'),
    end=pd.Timestamp('2023-12-31'),
    capital_base=10000
)

# Cell 4: Analyze results
print(f"Total Return: {result['returns'].iloc[-1]:.2%}")
result['portfolio_value'].plot(figsize=(12, 6), title='Portfolio Value')
plt.show()

# Cell 5: Detailed analysis
result['returns'].hist(bins=50, figsize=(10, 6))
plt.title('Returns Distribution')
plt.show()

# Cell 6: Performance metrics
sharpe = result['sharpe']
max_dd = result['max_drawdown']
print(f"Sharpe Ratio: {sharpe:.2f}")
print(f"Max Drawdown: {max_dd:.2%}")
```

### Advantages

✅ Interactive development and testing
✅ Inline visualization and analysis
✅ Easy parameter exploration
✅ Shareable research notebooks
✅ Documentation with markdown cells

### Limitations

❌ Not suitable for production
❌ Version control challenges
❌ Execution order matters
❌ State management issues

### Best Practices

1. **Clear cell execution order** - Number cells, document dependencies
2. **Restart kernel frequently** - Avoid stale state
3. **Extract to .py files** - Move production code out of notebooks
4. **Use for exploration only** - Not for live trading

---

## Choosing the Right Method

### Decision Matrix

**Use CLI when:**
- Running existing strategies quickly
- Automating backtests in scripts
- Deploying to production servers
- You don't need result post-processing

**Use Python API when:**
- Developing strategies actively
- Need IDE debugging features
- Want programmatic result access
- Integrating with other Python code

**Use Class-based when:**
- Strategy is complex (>100 lines)
- Using Pipeline API
- Need state encapsulation
- Building reusable strategy templates

**Use Function-based when:**
- Strategy is simple (<100 lines)
- Quick prototyping
- Learning RustyBT
- Don't need Pipeline API

**Use Jupyter Notebooks when:**
- Exploring data and ideas
- Creating research reports
- Teaching or documentation
- Iterative development

---

## Complete Working Examples

### Example 1: Simple Moving Average (Function-Based, Python API)

```python
# sma_strategy.py
from rustybt.api import order_target, symbol, record
from rustybt.utils.run_algo import run_algorithm
import pandas as pd

def initialize(context):
    context.asset = symbol('AAPL')
    context.i = 0

def handle_data(context, data):
    context.i += 1
    if context.i < 300:
        return

    short_ma = data.history(context.asset, 'price', 100, '1d').mean()
    long_ma = data.history(context.asset, 'price', 300, '1d').mean()

    if short_ma > long_ma:
        order_target(context.asset, 100)
    elif short_ma < long_ma:
        order_target(context.asset, 0)

    record(short_ma=short_ma, long_ma=long_ma)

if __name__ == "__main__":
    result = run_algorithm(
        initialize=initialize,
        handle_data=handle_data,
        bundle='yfinance-profiling',
        start=pd.Timestamp('2020-01-01'),
        end=pd.Timestamp('2023-12-31'),
        capital_base=10000
    )
    print(f"Return: {result['returns'].iloc[-1]:.2%}")
```

### Example 2: Multi-Asset Portfolio (Class-Based, Python API)

```python
# portfolio_strategy.py
from rustybt.algorithm import TradingAlgorithm
from rustybt.api import order_target_percent, symbol
from rustybt.utils.run_algo import run_algorithm
import pandas as pd

class EqualWeightPortfolio(TradingAlgorithm):
    def initialize(self):
        self.assets = [
            symbol('AAPL'), symbol('MSFT'),
            symbol('GOOGL'), symbol('AMZN')
        ]
        self.schedule_function(
            self.rebalance,
            self.date_rules.month_start(),
            self.time_rules.market_open()
        )

    def rebalance(self, context, data):
        weight = 1.0 / len(self.assets)
        for asset in self.assets:
            order_target_percent(asset, weight)

if __name__ == "__main__":
    result = run_algorithm(
        algorithm_class=EqualWeightPortfolio,
        bundle='yfinance-profiling',
        start=pd.Timestamp('2020-01-01'),
        end=pd.Timestamp('2023-12-31'),
        capital_base=100000
    )
    print(f"Sharpe: {result['sharpe']:.2f}")
```

---

## Troubleshooting

### Common Issues

**"ModuleNotFoundError: No module named 'rustybt'"**

```bash
pip install rustybt
```

**"No data for bundle 'yfinance-profiling'"**

```bash
rustybt ingest -b yfinance-profiling
```

**"NameError: name 'symbol' is not defined"**

```python
# Add import
from rustybt.api import symbol
```

**"AttributeError: 'NoneType' object has no attribute 'iloc'"**

Check that `run_algorithm()` completed successfully. Add error handling:

```python
result = run_algorithm(...)
if result is not None:
    print(f"Return: {result['returns'].iloc[-1]:.2%}")
else:
    print("Backtest failed!")
```

---

## Next Steps

1. **Try the Quick Start** - [Quick Start Guide](../getting-started/quickstart.md)
2. **Explore Examples** - [Examples & Notebooks](../examples/README.md)
3. **Learn Pipeline API** - [Pipeline API Guide](pipeline-api-guide.md)
4. **Deploy to Production** - [Live Trading Guide](../api/live-trading/README.md)

---

**Last Updated:** 2025-10-17
**Related Documentation:**
- [Quick Start Guide](../getting-started/quickstart.md)
- [Order Types API](../api/order-management/order-types.md)
- [Portfolio Management API](../api/portfolio-management/README.md)
- [Pipeline API Guide](pipeline-api-guide.md)
