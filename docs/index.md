# Welcome to RustyBT

**Modern Python backtesting engine built on Zipline-Reloaded, enhanced with Decimal precision, Polars data engine, and live trading capabilities**

[![PyPI version](https://img.shields.io/pypi/v/rustybt.svg)](https://pypi.org/project/rustybt/)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![CI](https://github.com/jerryinyang/rustybt/workflows/CI/badge.svg)](https://github.com/jerryinyang/rustybt/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/jerryinyang/rustybt/branch/main/graph/badge.svg)](https://codecov.io/gh/jerryinyang/rustybt)

## What is RustyBT?

RustyBT is a next-generation algorithmic trading framework that extends [Zipline-Reloaded](https://github.com/stefan-jansen/zipline-reloaded) with modern enhancements for professional traders and quantitative researchers.

### Key Features

✨ **Decimal Precision** - Financial-grade arithmetic using Python's `Decimal` type for audit-compliant calculations

⚡ **Polars Data Engine** - 5-10x faster data processing with lazy evaluation and efficient memory usage

💾 **Parquet Storage** - Industry-standard columnar format (50-80% smaller than HDF5)

📊 **Multi-Strategy Portfolio** - Advanced capital allocation and risk management across multiple strategies

🔧 **Strategy Optimization** - Grid search, Bayesian optimization, genetic algorithms, and walk-forward analysis

🔴 **Live Trading** - Production-ready engine for executing strategies in real-time markets (CCXT, Interactive Brokers, Binance, Bybit, Hyperliquid)

🐍 **Modern Python** - Requires Python 3.12+ for structural pattern matching and enhanced type hints

## Quick Start

### Installation

```bash
# Install from PyPI (recommended)
pip install rustybt

# Or with optional features
pip install rustybt[optimization]
```

[Full installation instructions →](getting-started/installation.md)

### Your First Backtest

**Step 1:** Create a strategy file `strategy.py`:

```python
from rustybt.api import order_target, record, symbol

def initialize(context):
    context.asset = symbol('AAPL')

def handle_data(context, data):
    # Simple moving average crossover
    short_mavg = data.history(context.asset, 'price',
                              bar_count=100, frequency="1d").mean()
    long_mavg = data.history(context.asset, 'price',
                             bar_count=300, frequency="1d").mean()

    if short_mavg > long_mavg:
        order_target(context.asset, 100)
    elif short_mavg < long_mavg:
        order_target(context.asset, 0)
```

**Step 2:** Ingest sample data (first time only):

```bash
rustybt ingest -b yfinance-profiling
```

This downloads free sample data from Yahoo Finance (20 top US stocks, 2 years of history). No API key required!

**Step 3:** Run the backtest:

```bash
rustybt run -f strategy.py -b yfinance-profiling --start 2024-01-01 --end 2025-09-30
```

!!! note "Dynamic Date Range"
    The **yfinance-profiling** bundle fetches the last 2 years of data from today. Adjust dates to match your ingested data timeframe.

**Alternative: Python API Execution**

You can also run strategies directly from Python without the CLI:

```python
# strategy.py
from rustybt.api import order_target, symbol
from rustybt.utils.run_algo import run_algorithm
import pandas as pd

def initialize(context):
    context.asset = symbol('AAPL')

def handle_data(context, data):
    short_mavg = data.history(context.asset, 'price', bar_count=100, frequency="1d").mean()
    long_mavg = data.history(context.asset, 'price', bar_count=300, frequency="1d").mean()

    if short_mavg > long_mavg:
        order_target(context.asset, 100)
    elif short_mavg < long_mavg:
        order_target(context.asset, 0)

if __name__ == "__main__":
    result = run_algorithm(
        initialize=initialize,
        handle_data=handle_data,
        bundle='yfinance-profiling',
        start=pd.Timestamp('2024-01-01'),
        end=pd.Timestamp('2025-09-30'),
        capital_base=10000
    )

    print(f"\nBacktest Complete!")
    print(f"Total return: {result['returns'].iloc[-1]:.2%}")
```

Then run with: `python strategy.py`

!!! tip "Troubleshooting"
    - **"no data for bundle"**: Run `rustybt ingest -b yfinance-profiling` first
    - **"fatal: bad revision 'HEAD'"**: Reinstall with `pip install --upgrade --force-reinstall rustybt`
    - **Segmentation fault**: Check Python version (3.12+ required) and reinstall

[Complete quick start guide →](getting-started/quickstart.md)

## Documentation Navigation

### 🚀 [Getting Started](getting-started/installation.md)
New to RustyBT? Start here!

- [Installation](getting-started/installation.md) - Set up RustyBT on your system
- [Quick Start](getting-started/quickstart.md) - Write your first trading strategy
- [Configuration](getting-started/configuration.md) - Configure RustyBT for your needs

### 📚 [User Guides](guides/decimal-precision-configuration.md)
In-depth guides for specific features:

- [Decimal Precision](guides/decimal-precision-configuration.md) - Financial-grade calculations
- [Caching System](guides/caching-system.md) - Optimize performance with intelligent caching
- [Creating Data Adapters](guides/creating-data-adapters.md) - Build custom data sources
- [CSV Data Import](guides/csv-data-import.md) - Import your own data
- [Testnet Setup](guides/testnet-setup-guide.md) - Test live trading safely

### 💡 [Examples & Tutorials](examples/README.md)
Learn by example with 13 Jupyter notebooks and 20+ Python examples:

**Interactive Tutorials:**
- Getting Started, Data Ingestion, Strategy Development
- Performance Analysis, Optimization, Walk-Forward Analysis
- Risk Analytics, Portfolio Construction, Paper Trading
- Full Workflow, Advanced Topics, Crypto & Equity Backtests

**Python Examples:**
- Data ingestion (Yahoo Finance, CCXT, CSV)
- Live trading & paper trading
- Portfolio allocation & transaction costs
- Strategy optimization (Grid, Bayesian, Genetic, Walk-Forward)
- Report generation & attribution analysis

[Browse all examples →](examples/README.md)

### 📖 [API Reference](api/datasource-api.md)
Complete API documentation:

- [Datasource API](api/datasource-api.md) - Data ingestion and management
- [Optimization API](api/optimization-api.md) - Strategy optimization tools
- [Analytics API](api/analytics-api.md) - Performance analysis and reporting

### ℹ️ [About](about/license.md)
Project information:

- [License](about/license.md) - Apache 2.0 license information
- [Contributing](about/contributing.md) - How to contribute to RustyBT
- [Changelog](about/changelog.md) - Release history and changes

## Key Differences from Zipline-Reloaded

| Feature | Zipline-Reloaded | RustyBT |
|---------|------------------|---------|
| Numeric Type | `float64` | `Decimal` (configurable precision) |
| Data Engine | `pandas` | `polars` (pandas compatible) |
| Storage Format | bcolz/HDF5 | Parquet (Arrow-based) |
| Python Version | 3.10+ | 3.12+ |
| Live Trading | No | Yes (multiple brokers) |
| Multi-Strategy | Limited | Advanced portfolio management |
| Optimization | Basic | Grid, Bayesian, Genetic, Walk-Forward |

## Feature Highlights

### Decimal Precision

```python
from decimal import Decimal
from rustybt.finance.decimal import DecimalLedger

# Financial calculations with audit-compliant precision
ledger = DecimalLedger(starting_cash=Decimal("100000.00"))
```

### Modern Data Architecture

```python
import polars as pl
from rustybt.data.adapters import YFinanceAdapter, CCXTAdapter

# Multiple data sources with intelligent caching
yf_adapter = YFinanceAdapter()
crypto_adapter = CCXTAdapter(exchange_id='binance')
```

### Multi-Strategy Portfolio Management

```python
from rustybt.portfolio import PortfolioAllocator
from rustybt.portfolio.allocation import RiskParityAllocation

# Manage multiple strategies with intelligent allocation
allocator = PortfolioAllocator(
    strategies=[strategy1, strategy2, strategy3],
    allocation_algorithm=RiskParityAllocation()
)
```

### Strategy Optimization

```python
from rustybt.optimization import Optimizer, WalkForwardOptimizer

# Optimize strategy parameters
optimizer = Optimizer(
    strategy=my_strategy,
    param_space={'fast_ma': (10, 50), 'slow_ma': (50, 200)}
)
results = optimizer.optimize()
```

### Live Trading

```python
from rustybt.live import LiveTradingEngine
from rustybt.live.brokers import CCXTBrokerAdapter

# Connect to exchange for live trading
broker = CCXTBrokerAdapter(
    exchange_id='binance',
    api_key='YOUR_API_KEY',
    api_secret='YOUR_API_SECRET',
    testnet=True,
)
engine = LiveTradingEngine(strategy=my_strategy, broker_adapter=broker)
engine.run()
```

## Community & Support

- 📖 **Documentation**: You're reading it!
- 🐛 **Issues**: [GitHub Issues](https://github.com/jerryinyang/rustybt/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/jerryinyang/rustybt/discussions)
- 📦 **Source Code**: [GitHub Repository](https://github.com/jerryinyang/rustybt)

## Project Status

### Completed ✅

- Epic 1: Project setup and architecture foundations
- Epic 2: Decimal precision financial calculations
- Epic 3: Modern data architecture (Polars/Parquet)
- Epic 4: Enhanced transaction costs and multi-strategy
- Epic 5: Strategy optimization framework
- Epic 6: Live trading engine with broker integrations
- Epic 8: Analytics and production readiness

### In Progress 🚧

- Epic 7: Rust performance optimizations
- Epic X2: Production readiness validation

### Planned 📋

- Epic 9: REST API and WebSocket interface
- v1.0.0: Production-ready stable release

## Acknowledgments

RustyBT is built on the shoulders of giants:

- **[Zipline](https://github.com/quantopian/zipline)** - Original backtesting library by Quantopian
- **[Zipline-Reloaded](https://github.com/stefan-jansen/zipline-reloaded)** - Maintained fork by Stefan Jansen
- **[Machine Learning for Algorithmic Trading](https://ml4trading.io)** - Comprehensive guide by Stefan Jansen

We are grateful to the Quantopian team, Stefan Jansen, and the entire open-source algorithmic trading community.

---

!!! note "Development Status"
    RustyBT is under active development. APIs may change until version 1.0.0.

**Ready to get started?** Head to the [Installation Guide](getting-started/installation.md) →
