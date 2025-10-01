# RustyBT

**Modern Python backtesting engine built on Zipline-Reloaded, enhanced with Decimal precision, Polars data engine, and live trading capabilities**

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
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Using uv (Recommended)

```bash
# Create virtual environment
uv venv --python 3.12

# Activate virtual environment
source .venv/bin/activate  # On Unix/macOS
# or
.venv\Scripts\activate  # On Windows

# Install RustyBT
uv pip install -e ".[dev,test]"
```

### Using pip

```bash
# Create virtual environment
python3.12 -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # On Unix/macOS

# Install RustyBT
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
rustybt run -f strategy.py --start 2020-01-01 --end 2023-12-31
```

## New Features

### Decimal Precision

```python
from decimal import Decimal
from rustybt.finance.decimal import DecimalLedger

# Financial calculations with audit-compliant precision
ledger = DecimalLedger(starting_cash=Decimal("100000.00"))
```

### Polars Data Engine

```python
import polars as pl
from rustybt.data.polars import PolarsDataPortal

# Fast data processing with lazy evaluation
data = pl.read_parquet("ohlcv_data.parquet")
```

### Live Trading

```python
from rustybt.live import LiveTradingEngine
from rustybt.live.brokers import CCXTAdapter

# Connect to exchange for live trading
engine = LiveTradingEngine(
    strategy=my_strategy,
    broker=CCXTAdapter(exchange='binance')
)
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

## Community

- **Documentation**: Coming soon
- **Issues**: [GitHub Issues](https://github.com/your-org/rustybt/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/rustybt/discussions)

## Roadmap

- [x] **Epic 1**: Project setup and architecture foundations
- [ ] **Epic 2**: Decimal precision financial calculations
- [ ] **Epic 3**: Polars/Parquet data engine
- [ ] **Epic 4**: Live trading capabilities
- [ ] **Epic 5**: Strategy optimization framework
- [ ] **Epic 6**: Advanced analytics and reporting
- [ ] **Epic 7**: Rust performance optimizations

---

**Note**: RustyBT is under active development. APIs may change until version 1.0.0.
