# RustyBT

**Modern Python backtesting engine built on Zipline-Reloaded, enhanced with Decimal precision, Polars data engine, and live trading capabilities**

[![PyPI version](https://img.shields.io/pypi/v/rustybt.svg)](https://pypi.org/project/rustybt/)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![CI](https://github.com/jerryinyang/rustybt/workflows/CI/badge.svg)](https://github.com/jerryinyang/rustybt/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/jerryinyang/rustybt/branch/main/graph/badge.svg)](https://codecov.io/gh/jerryinyang/rustybt)

## Overview

RustyBT is a next-generation Python-based algorithmic trading framework that extends [Zipline-Reloaded](https://github.com/stefan-jansen/zipline-reloaded) with modern enhancements:

- **Decimal Precision**: Financial-grade arithmetic using Python's `Decimal` type for audit-compliant calculations
- **Polars Data Engine**: 5-10x faster data processing with lazy evaluation and efficient memory usage
- **Parquet Storage**: Industry-standard columnar format for OHLCV data (50-80% smaller than HDF5)
- **Live Trading**: Production-ready engine for executing strategies in real-time markets
- **Modern Python**: Requires Python 3.12+ for structural pattern matching and enhanced type hints

## Key Differences from Zipline-Reloaded

| Feature | Zipline-Reloaded | RustyBT |
|---------|------------------|---------|
| Numeric Type | `float64` | `Decimal` (configurable precision) |
| Data Engine | `pandas` | `polars` (pandas compatible) |
| Storage Format | bcolz/HDF5 | Parquet (Arrow-based) |
| Python Version | 3.10+ | 3.12+ |
| Live Trading | No | Yes (multiple brokers) |
| Performance | Baseline | Optimized (Rust modules planned) |

## Installation

### Prerequisites

- Python 3.12 or higher
- pip (included with Python)

### From PyPI (Recommended)

Install the latest stable release from PyPI:

```bash
# Install RustyBT
pip install rustybt

# Or install with optional features
pip install rustybt[optimization]  # Strategy optimization tools
pip install rustybt[dev]           # Development tools
pip install rustybt[test]          # Testing tools
```

**Available extras:**
- `optimization` - Strategy optimization (scikit-learn, genetic algorithms)
- `dev` - Development tools (jupyter, jupyterlab, ruff, mypy, black, type stubs)
- `test` - Testing tools (pytest, hypothesis, coverage)
- `benchmarks` - Performance profiling tools
- `docs` - Documentation generation (MkDocs with Material theme)

### From Source (Development)

For contributors or those who want the latest development version:

```bash
# Clone the repository
git clone https://github.com/jerryinyang/rustybt.git
cd rustybt

# Using uv (recommended for development)
uv sync --extra dev --extra test

# Or using pip
python3.12 -m venv .venv
source .venv/bin/activate  # On Unix/macOS
# or .venv\Scripts\activate on Windows
pip install -e ".[dev,test]"
```

## Quick Start

RustyBT maintains backward compatibility with Zipline API:

```python
from rustybt.api import order_target, record, symbol

def initialize(context):
    context.i = 0
    context.asset = symbol('AAPL')

def handle_data(context, data):
    # Skip first 300 days to get full windows
    context.i += 1
    if context.i < 300:
        return

    # Compute averages
    short_mavg = data.history(context.asset, 'price', bar_count=100, frequency="1d").mean()
    long_mavg = data.history(context.asset, 'price', bar_count=300, frequency="1d").mean()

    # Trading logic
    if short_mavg > long_mavg:
        order_target(context.asset, 100)
    elif short_mavg < long_mavg:
        order_target(context.asset, 0)

    # Save values for later inspection
    record(AAPL=data.current(context.asset, 'price'),
           short_mavg=short_mavg,
           long_mavg=long_mavg)
```

Run the backtest:

```bash
# First, ingest sample data (only needed once)
rustybt ingest -b yfinance-profiling

# Run the backtest
rustybt run -f strategy.py -b yfinance-profiling --start 2024-01-01 --end 2025-09-30
```

## Key Features

### Decimal Precision (Epic 2)

```python
from decimal import Decimal
from rustybt.finance.decimal import DecimalLedger

# Financial calculations with audit-compliant precision
ledger = DecimalLedger(starting_cash=Decimal("100000.00"))
```

### Modern Data Architecture (Epic 3)

```python
import polars as pl
from rustybt.data.adapters import YFinanceAdapter, CCXTAdapter

# Multiple data sources with intelligent caching
yf_adapter = YFinanceAdapter()
crypto_adapter = CCXTAdapter(exchange_id='binance')

# Fast data processing with Parquet storage
data = pl.read_parquet("ohlcv_data.parquet")
```

### Enhanced Transaction Costs (Epic 4)

```python
from rustybt.finance.slippage import VolumeShareSlippage
from rustybt.finance.commission import TieredCommission

# Realistic transaction cost modeling
slippage = VolumeShareSlippage(volume_limit=0.025)
commission = TieredCommission(tiers=[(0, 0.001), (100000, 0.0005)])
```

### Multi-Strategy Portfolio Management (Epic 4)

```python
from rustybt.portfolio import PortfolioAllocator
from rustybt.portfolio.allocation import RiskParityAllocator

# Manage multiple strategies with intelligent allocation
allocator = PortfolioAllocator(
    strategies=[strategy1, strategy2, strategy3],
    allocation_algorithm=RiskParityAllocator()
)
```

### Strategy Optimization (Epic 5)

```python
from rustybt.optimization import GridSearchOptimizer, BayesianOptimizer

# Optimize strategy parameters with multiple algorithms
optimizer = BayesianOptimizer(
    param_space={'fast_ma': (10, 50), 'slow_ma': (50, 200)},
    n_iterations=100
)
results = optimizer.optimize(strategy)
```

### Live Trading (Epic 6)

```python
from rustybt.live import LiveTradingEngine
from rustybt.live.brokers import CCXTBrokerAdapter

# Connect to exchange for live trading with multiple brokers
broker = CCXTBrokerAdapter(
    exchange_id='binance',
    api_key='YOUR_API_KEY',
    api_secret='YOUR_API_SECRET',
    testnet=True,
)
engine = LiveTradingEngine(strategy=my_strategy, broker_adapter=broker)
engine.run()
```

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and contribution guidelines.

### Running Tests

```bash
# Run full test suite
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=rustybt --cov-report=html

# Run specific test file
pytest tests/finance/test_decimal_ledger.py
```

### Code Quality

```bash
# Format code
black rustybt/ tests/

# Lint code
ruff check rustybt/ tests/

# Type check
mypy rustybt/ --strict
```

## Architecture

RustyBT maintains Zipline's proven architecture while adding new capabilities:

```
rustybt/
├── finance/          # Financial calculations (Decimal-based)
│   └── decimal/      # Decimal arithmetic modules
├── data/             # Data management (Polars-based)
│   ├── polars/       # Polars data layer
│   └── adapters/     # Data source adapters
├── live/             # Live trading engine
│   ├── brokers/      # Broker adapters
│   └── streaming/    # Real-time data feeds
├── assets/           # Asset management (extended for crypto)
├── pipeline/         # Pipeline framework (Polars-compatible)
└── algorithm.py      # TradingAlgorithm (extended)
```

## Acknowledgments

RustyBT is built on the shoulders of giants:

- **[Zipline](https://github.com/quantopian/zipline)**: Original backtesting library by Quantopian
- **[Zipline-Reloaded](https://github.com/stefan-jansen/zipline-reloaded)**: Maintained fork by Stefan Jansen
- **[Machine Learning for Algorithmic Trading](https://ml4trading.io)**: Comprehensive guide by Stefan Jansen

We are grateful to the Quantopian team, Stefan Jansen, and the entire open-source algorithmic trading community.

## License

RustyBT is licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.

This project incorporates code from Zipline and Zipline-Reloaded, both licensed under Apache 2.0.

### Known License Limitations

While RustyBT follows an **Apache 2.0/MIT-only dependency policy**, the following LGPL dependencies currently exist as transitive dependencies:

| Package | License | Type | Source | Status |
|---------|---------|------|--------|--------|
| `frozendict` | LGPL v3 | Production | Via `yfinance` (Yahoo Finance data) | Tracked for replacement |
| `chardet` | LGPL | Development | Via `tox` (testing tool) | Tracked for replacement |

**Legal Status**: LGPL allows use as a dynamically-linked library without GPL license contamination. RustyBT's Apache 2.0 license remains unaffected.

**Mitigation Plans**:
- **frozendict**: Evaluating alternative data providers or forking `yfinance` with MIT-licensed replacement
- **chardet**: Considering migration from `tox` to modern alternatives (`nox`, `hatch`)

For details on dependency security and license compliance, see [docs/security-audit.md](docs/security-audit.md).

## Documentation

- **Full Documentation**: [https://jerryinyang.github.io/rustybt/](https://jerryinyang.github.io/rustybt/) (GitHub Pages)
- **ReadTheDocs**: [https://rustybt.readthedocs.io/](https://rustybt.readthedocs.io/) (Alternative)
- **Architecture Docs**: [docs/architecture/index.md](docs/architecture/index.md)
- **User Guides**: [docs/guides/](docs/guides/)

## Community

- **Issues**: [GitHub Issues](https://github.com/jerryinyang/rustybt/issues)
- **Discussions**: [GitHub Discussions](https://github.com/jerryinyang/rustybt/discussions)

## Roadmap

### Completed ✅

- [x] **Epic 1**: Project setup and architecture foundations
- [x] **Epic 2**: Decimal precision financial calculations
- [x] **Epic 3**: Modern data architecture (Polars/Parquet with multiple adapters)
- [x] **Epic 4**: Enhanced transaction costs and multi-strategy portfolio management
- [x] **Epic 5**: Strategy optimization framework (Grid, Bayesian, Genetic, Walk-Forward)
- [x] **Epic 6**: Live trading engine with broker integrations (CCXT, IB, Binance, Bybit, Hyperliquid)
- [x] **Epic 8**: Analytics and production readiness (reporting, attribution, risk analytics)

### In Progress 🚧

- [ ] **Epic 7**: Rust performance optimizations (baseline benchmarks complete)
- [ ] **Epic X2**: Production readiness validation and remediation

### Planned 📋

- [ ] **Epic 9**: REST API and WebSocket interface
- [ ] **v1.0.0**: Production-ready stable release

See [docs/prd/epic-list.md](docs/prd/epic-list.md) for detailed epic descriptions and stories.

---

**Note**: RustyBT is under active development. APIs may change until version 1.0.0.
