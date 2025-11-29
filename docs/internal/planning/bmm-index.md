# RustyBT Brownfield Project Documentation

**Generated:** 2025-11-23
**Project Type:** Python Library/Framework (Monolith)
**Status:** Active Development
**Purpose:** AI-Assisted Development Reference

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Quick Reference](#quick-reference)
3. [Technology Stack](#technology-stack)
4. [Architecture](#architecture)
5. [Module Structure](#module-structure)
6. [Key Workflows](#key-workflows)
7. [Development Setup](#development-setup)
8. [Testing Strategy](#testing-strategy)
9. [Known Issues & Notes](#known-issues--notes)

---

## Project Overview

**RustyBT** is a modern Python algorithmic trading backtesting framework built on Zipline-Reloaded, enhanced with:
- **Decimal precision** for financial-grade calculations
- **Polars data engine** (5-10x faster than pandas)
- **Live trading capabilities** (crypto, traditional brokers)
- **Advanced optimization** (Bayesian, genetic algorithms, BOHB)
- **Comprehensive analytics** with Jupyter integration

### Project Metadata
- **Python Version:** 3.12+ (3.13 supported)
- **License:** Apache 2.0
- **Repository:** https://github.com/jerryinyang/rustybt
- **Documentation:** https://jerryinyang.github.io/rustybt/
- **Files:** 332 Python files + 16 Cython extensions
- **Lines of Code:** ~100k+ LOC

### Core Value Propositions
1. **Financial Precision:** Decimal arithmetic prevents rounding errors in financial calculations
2. **Performance:** Polars data engine + Cython extensions for speed-critical paths
3. **Live Trading:** Production-ready live trading with multiple broker integrations
4. **Validation Ready:** Framework designed for benchmarking against Backtrader

---

## Quick Reference

### Entry Points
```bash
# CLI command
rustybt run -f strategy.py --start 2020-01-01 --end 2021-12-31

# Legacy compatibility
zipline run -f strategy.py --start 2020-01-01 --end 2021-12-31
```

### Python API
```python
from rustybt import run_algorithm
from rustybt.api import order, symbol, record

def initialize(context):
    context.asset = symbol('AAPL')

def handle_data(context, data):
    order(context.asset, 10)
    record(price=data.current(context.asset, 'price'))

result = run_algorithm(
    start='2020-01-01',
    end='2020-12-31',
    initialize=initialize,
    handle_data=handle_data,
    capital_base=10000,
    bundle='quandl'
)
```

### Key Directories
```
rustybt/
├── algorithm.py          # Core backtesting engine (TradingAlgorithm class)
├── api.py               # Public trading API
├── data/                # Data management layer
├── assets/              # Asset metadata and calendars
├── finance/             # Portfolio accounting, costs
├── backtest/            # Backtesting infrastructure
├── live/                # Live trading engine
├── portfolio/           # Portfolio management, risk
├── optimization/        # Strategy optimization
├── analytics/           # Performance analytics
├── pipeline/            # Factor analysis framework
├── utils/               # Utility functions
└── testing/             # Testing utilities
```

---

## Technology Stack

### Core Framework
| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Language | Python | 3.12+ | Core implementation |
| Base Framework | Zipline-Reloaded | Fork | Proven backtesting foundation |
| Extensions | Cython | 0.29-3.2 | Performance-critical modules |

### Data Architecture
| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Data Engine | Polars | >=1.0 | Fast data processing (5-10x pandas) |
| Storage | PyArrow/Parquet | >=18.0 | Columnar storage format |
| Numeric | NumPy | 1.26+/2.1+ | Array operations |
| Legacy Support | Pandas | 1.3-3.0 | Backward compatibility |
| Database | SQLAlchemy | >=2 | Metadata management |
| Precision | Python Decimal | Built-in | Financial arithmetic |

### Live Trading & Data
| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Crypto Exchanges | ccxt | >=4.0.0 | 100+ cryptocurrency exchanges |
| Bybit | pybit | >=5.0.0 | Bybit exchange |
| Hyperliquid | hyperliquid-python-sdk | >=0.1.0 | Hyperliquid DEX |
| Interactive Brokers | ib-insync | >=0.9.86 | Traditional broker |
| Market Data | yfinance | >=0.2.0 | Yahoo Finance data |
| Async IO | aiohttp, websockets | Latest | Real-time data feeds |
| Scheduling | APScheduler | >=3.0 | Strategy automation |

### Optimization & ML
| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| ML Framework | scikit-learn | >=1.3.0 | Sensitivity analysis |
| Bayesian Opt | scikit-optimize | >=0.9.0 | Smart parameter search |
| Genetic Alg | DEAP | >=1.4.0 | Evolutionary optimization |
| Multi-fidelity | HPBandSter | >=0.7.4 | BOHB optimization |
| JIT Compiler | numba | >=0.62.1 | Performance acceleration |

### Analytics & Visualization
| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Interactive | Plotly | >=5.0 | Interactive financial charts |
| Statistical | Seaborn | >=0.13.0 | Statistical visualizations |
| Classic | Matplotlib | >=3.5.0 | Publication charts |
| Reports | Jinja2 | >=3.0.0 | HTML report generation |

### Development & Quality
| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Testing | pytest | >=7.2.0 | Test framework |
| Property Testing | Hypothesis | >=6.0 | Property-based testing |
| Type Checking | mypy | >=1.10.0 | Static analysis (strict mode) |
| Linting | Ruff | >=0.11.12 | Fast Python linter |
| Formatting | Black | >=24.1 | Code formatter |
| Documentation | MkDocs + Material | Latest | Modern documentation |

---

## Architecture

### Design Pattern
**Layered Architecture** with clear separation of concerns:

```
┌─────────────────────────────────────────┐
│         User Strategy Layer             │  (algorithm.py, user code)
├─────────────────────────────────────────┤
│          Trading API Layer              │  (api.py, order management)
├─────────────────────────────────────────┤
│      Execution & Portfolio Layer        │  (backtest/, live/, portfolio/)
├─────────────────────────────────────────┤
│       Finance & Cost Layer              │  (finance/, decimal precision)
├─────────────────────────────────────────┤
│       Data Management Layer             │  (data/, assets/, pipeline/)
├─────────────────────────────────────────┤
│       Infrastructure Layer              │  (utils/, testing/, benchmarks/)
└─────────────────────────────────────────┘
```

### Core Execution Flow

```
1. Strategy Initialization
   ↓
2. Data Loading (Bundles/Adapters)
   ↓
3. Event Loop (Minute/Daily Bars)
   ↓
4. Strategy Logic (handle_data/before_trading_start)
   ↓
5. Order Processing (Blotter)
   ↓
6. Fill Simulation (Slippage/Commission)
   ↓
7. Portfolio Update (Positions/Cash)
   ↓
8. Metrics Tracking (Performance)
   ↓
9. Results Generation (Analytics)
```

### Key Design Decisions

1. **Dual Data Portal Architecture**
   - PolarsDataPortal: Modern, high-performance data access
   - LegacyDataPortal: Backward compatibility with Zipline
   - Abstraction layer allows transparent switching

2. **Decimal Financial Precision**
   - All financial calculations use Python Decimal
   - Prevents floating-point rounding errors
   - Audit-compliant precision tracking

3. **Lazy Loading Pattern**
   - Heavy modules (TradingAlgorithm, Blotter) loaded on first access
   - Reduces import time by ~60%
   - Improves CLI responsiveness

4. **Extension System**
   - Modular broker adapters (ccxt, IB, Bybit, Binance, Hyperliquid)
   - Pluggable data adapters (yfinance, CSV, alphavantage, databento)
   - Custom commission/slippage models

---

## Module Structure

### 1. Core Foundation (`rustybt/`)
**Purpose:** Core backtesting engine and public API

**Key Files:**
- `algorithm.py` (116KB, 3 classes) - TradingAlgorithm main class
- `api.py` (3.7KB) - Public trading API functions
- `__init__.py` (11KB) - Package exports and lazy loading
- `protocol.py` (22KB, 7 interfaces) - Abstract interfaces
- `errors.py` / `exceptions.py` (35KB + 15KB) - Error handling

**Responsibilities:**
- Algorithm lifecycle management (initialize, handle_data, analyze)
- Trading operations (order, order_target, history, current)
- Risk management (leverage limits, position controls)
- Scheduling (schedule_function, date_rules, time_rules)

### 2. Data Management (`rustybt/data/`)
**Purpose:** Data ingestion, storage, and retrieval

**Key Components:**
- `bundles/` - Data bundle system (quandl, CSV, adapter bundles)
- `polars/` - Modern Polars-based data infrastructure
  - `parquet_writer.py` - High-performance Parquet storage
  - `metadata_catalog.py` - Asset metadata management
  - `cache_manager.py` - Multi-tier caching
  - `data_portal.py` - Unified data access interface
- `adapters/` - External data source integrations
  - `ccxt_adapter.py` - Cryptocurrency data
  - `yfinance_adapter.py` - Yahoo Finance
  - `csv_adapter.py` - Custom CSV import
  - `databento_adapter.py` - Professional market data
  - `alphavantage_adapter.py` - Alpha Vantage
  - `alpaca_adapter.py` - Alpaca Markets
  - `polygon_adapter.py` - Polygon.io
- Cython extensions: `_adjustments.pyx`, `_equities.pyx` (performance)

**Data Flow:**
```
External Source → Adapter → Parquet Writer → Bundle
                                    ↓
                              Metadata Catalog
                                    ↓
                              Cache Manager
                                    ↓
                              Data Portal → Algorithm
```

### 3. Assets (`rustybt/assets/`)
**Purpose:** Asset metadata and trading calendar management

**Key Components:**
- `assets.py` (13 classes) - Asset types (Equity, Future, Option, Crypto)
- `asset_writer.py` (13 functions) - Asset database management
- `asset_db_migrations.py` (13 functions) - Schema migrations
- `exchange_info.py` - Exchange metadata
- `synthetic.py` (6 classes) - Synthetic assets for testing
- `roll_finder.py` (3 classes) - Futures contract rolling

**Asset Types:**
- Equity (stocks)
- Future (futures contracts with roll dates)
- Option (calls/puts)
- ContinuousFuture (auto-rolling futures)
- Crypto (cryptocurrency pairs)
- Forex (currency pairs)

### 4. Finance (`rustybt/finance/`)
**Purpose:** Portfolio accounting, costs, and financial calculations

**Key Components:**
- `blotter/` - Order management system
  - `blotter.py` - Abstract blotter interface
  - `simulation_blotter.py` - Backtesting order fills
- `decimal/` - Financial-precision arithmetic
  - `config.py` - Decimal precision configuration
  - `blotter.py` - Decimal-aware blotter
  - `position.py` - Decimal position tracking
  - `order.py` - Decimal order handling
  - `commission.py` - Decimal commission calculation
  - `slippage.py` - Decimal slippage models
- `commission.py` (19 classes) - Commission models
- `slippage.py` (17 classes) - Slippage models
- `execution.py` (34 classes) - Order execution algorithms
- `controls.py` (10 classes) - Trading controls/restrictions
- `metrics/` - Performance metric calculation

**Cost Models:**
- Commission: PerShare, PerTrade, PerDollar, Tiered
- Slippage: FixedBasisPoints, FixedSlippage, VolumeShareSlippage
- Execution: Market, Limit, Stop, StopLimit

### 5. Portfolio (`rustybt/portfolio/`)
**Purpose:** Portfolio management, risk, and capital allocation

**Key Components:**
- `allocator.py` (4 classes) - Multi-strategy portfolio allocation
- `allocation.py` (9 classes) - Capital allocation algorithms
- `aggregator.py` (5 classes) - Cross-strategy order aggregation
- `risk.py` (6 classes) - Risk management and metrics

**Allocation Strategies:**
- Equal weight
- Risk parity
- Mean-variance optimization
- Custom allocator interface

### 6. Backtest (`rustybt/backtest/`)
**Purpose:** Backtesting infrastructure and result management

**Key Components:**
- `code_capture.py` (4 functions) - Strategy code versioning
- `artifact_manager.py` (2 classes) - Backtest output management

**Features:**
- Automatic strategy code capture
- YAML configuration persistence
- Result organization by timestamp
- Metadata tracking

### 7. Live Trading (`rustybt/live/`)
**Purpose:** Production live trading engine

**Key Components:**
- `engine.py` - Main live trading engine
- `brokers/` - Broker integrations
  - `base.py` - Abstract broker interface
  - `ccxt_adapter.py` - Multi-exchange crypto trading
  - `ib_adapter.py` (3 classes) - Interactive Brokers
  - `bybit_adapter.py` (5 classes) - Bybit exchange
  - `binance_adapter.py` (5 classes) - Binance exchange
  - `hyperliquid_adapter.py` (5 classes) - Hyperliquid DEX
  - `paper_broker.py` (4 classes) - Paper trading simulation
- `streaming/` - Real-time data feeds
  - `base.py` (6 classes) - WebSocket base
  - `ccxt_stream.py` - CCXT WebSocket
  - `bybit_stream.py` - Bybit WebSocket
  - `binance_stream.py` - Binance WebSocket
  - `hyperliquid_stream.py` - Hyperliquid WebSocket
  - `bar_buffer.py` (2 classes) - Bar aggregation
- `shadow/` - Shadow trading validation
  - `engine.py` (3 classes) - Shadow trading engine
  - `signal_validator.py` - Signal comparison
  - `execution_tracker.py` - Execution tracking
- `scheduler.py` (3 classes) - Strategy scheduling
- `order_manager.py` (3 classes) - Live order management
- `state_manager.py` (3 classes) - State persistence
- `reconciler.py` (2 classes) - Position reconciliation
- `circuit_breakers.py` (12 classes) - Risk controls
- `alerts.py` (4 classes) - Alert system
- `events.py` (7 classes) - Event handling
- `dashboard.py` (3 classes) - Live monitoring

**Live Trading Flow:**
```
Strategy Signal
    ↓
Order Manager
    ↓
Risk Controls (Circuit Breakers)
    ↓
Broker Adapter
    ↓
Exchange/Broker API
    ↓
Order Confirmation
    ↓
Position Reconciliation
    ↓
State Persistence
```

### 8. Optimization (`rustybt/optimization/`)
**Purpose:** Strategy parameter optimization and robustness testing

**Key Components:**
- `optimizer.py` - Main optimization framework
- `search/`
  - `grid_search.py` - Exhaustive grid search
  - `random_search.py` - Random parameter sampling
  - `bayesian_search.py` - Bayesian optimization
  - `genetic_algorithm.py` - Genetic algorithm
- `walk_forward.py` (5 classes) - Walk-forward optimization
- `sensitivity.py` (4 classes) - Parameter sensitivity analysis
- `monte_carlo.py` (2 classes) - Monte Carlo permutation
- `noise_infusion.py` (2 classes) - Noise injection testing
- `parallel_optimizer.py` (4 classes) - Parallel execution
- `persistent_worker_pool.py` (3 classes) - Worker pool management
- `bundle_pool.py` (2 classes) - Bundle sharing across workers
- `caching.py` (9 classes) - Result caching
- `parameter_space.py` (4 classes) - Parameter space definition

**Optimization Algorithms:**
- Grid Search (exhaustive)
- Random Search (sampling)
- Bayesian Optimization (smart search)
- Genetic Algorithm (evolutionary)
- BOHB (multi-fidelity, experimental)

### 9. Analytics (`rustybt/analytics/`)
**Purpose:** Performance analysis and reporting

**Key Components:**
- `reports.py` (3 classes) - HTML/PDF report generation
- `risk.py` (3 classes) - Risk analytics
- `attribution.py` (3 classes) - Performance attribution
- `trade_analysis.py` (4 classes) - Trade-level analysis
- `visualization.py` (6 classes) - Chart generation
- `notebook.py` (5 classes) - Jupyter integration

**Metrics:**
- Returns (total, annual, monthly)
- Risk (volatility, max drawdown, Sharpe, Sortino)
- Trade analysis (win rate, profit factor)
- Attribution (factor contribution)

### 10. Pipeline (`rustybt/pipeline/`)
**Purpose:** Cross-sectional factor analysis framework

**Key Components:**
- `engine.py` (6 classes) - Pipeline execution engine
- `pipeline.py` - Pipeline definition
- `factors/` - Factor definitions
  - `factor.py` (19 classes) - Base factor classes
  - `basic.py` (18 classes) - Basic factors (SMA, EMA, RSI)
  - `technical.py` (8 classes) - Technical indicators
  - `statistical.py` (10 classes) - Statistical factors
  - `decimal_factors.py` (5 classes) - Decimal-precision factors
- `filters/` - Boolean filters
  - `filter.py` (16 classes) - Base filter classes
- `classifiers/` - Categorical classifiers
  - `classifier.py` (7 classes) - Base classifier classes
- `loaders/` - Data loaders
  - `equity_pricing_loader.py` - OHLCV data
  - `earnings_estimates.py` (12 classes) - Earnings data

**Pipeline Example:**
```python
from rustybt.pipeline import Pipeline
from rustybt.pipeline.factors import SimpleMovingAverage, RSI
from rustybt.pipeline.data import USEquityPricing

sma_20 = SimpleMovingAverage(inputs=[USEquityPricing.close], window_length=20)
rsi_14 = RSI(window_length=14)

pipeline = Pipeline(
    columns={
        'sma_20': sma_20,
        'rsi_14': rsi_14,
    }
)
```

### 11. Testing (`rustybt/testing/`)
**Purpose:** Testing utilities and fixtures

**Key Components:**
- `fixtures.py` (36 classes) - Test fixtures
- `core.py` (69 functions) - Core testing utilities
- `predicates.py` (26 functions) - Test assertions
- `slippage.py` - Test slippage models
- `debug.py` (6 functions) - Debugging helpers

### 12. Utilities (`rustybt/utils/`)
**Purpose:** Common utility functions

**Key Components:**
- `logging.py` (3 classes) - Structured logging (structlog)
- `error_handling.py` (5 classes) - Error handling utilities
- `cache.py` (6 classes) - Caching decorators
- `pandas_utils.py` (15 functions) - Pandas utilities
- `numpy_utils.py` (21 functions) - NumPy utilities
- `events.py` (31 classes) - Event scheduling system
- `calendar_utils.py` - Trading calendar utilities
- `date_utils.py` - Date/time utilities
- `input_validation.py` (20 functions) - Input validation
- `secure_pickle.py` (4 functions) - Secure serialization
- `paths.py` (18 functions) - Path management

### 13. Generators (`rustybt/gens/`)
**Purpose:** Event generation and simulation control

**Key Components:**
- `tradesimulation.py` - Main simulation generator
- `clock.py` (3 classes) - Simulation clock
- `events.py` (6 classes) - Event definitions
- `composites.py` (2 classes) - Composite generators
- `temporal_isolation.py` (2 classes) - Time isolation
- `utils.py` (4 functions) - Generator utilities

### 14. Sources (`rustybt/sources/`)
**Purpose:** Data source implementations

**Key Components:**
- `benchmark_source.py` - Benchmark data
- `test_source.py` (3 classes) - Test data sources

### 15. Benchmarks (`rustybt/benchmarks/`)
**Purpose:** Performance benchmarking infrastructure

**Key Components:**
- `profiling.py` (10 functions) - Profiling utilities
- `sequential.py` (5 classes) - Sequential benchmark runner
- `threshold.py` (5 classes) - Performance threshold checks
- `reporter.py` (3 classes) - Benchmark reporting
- `comparisons.py` (7 classes) - Cross-framework comparison
- `models.py` (7 classes) - Benchmark data models
- `exceptions.py` (8 classes) - Benchmark exceptions

**NOTE:** Per user feedback, existing benchmarks are incomplete or outdated.

### 16. Config (`rustybt/config/`)
**Purpose:** Configuration templates

**Subdirectories:**
- `broker_commission_profiles/` - Commission configurations
- `broker_latency_profiles/` - Latency simulations
- `borrow_rates/` - Short selling costs
- `financing_rates/` - Overnight financing

### 17. Resources (`rustybt/resources/`)
**Purpose:** Static resources and reference data

### 18. Examples (`rustybt/examples/`)
**Purpose:** Example strategies

**Key Examples:**
- `buyapple.py` (4 functions) - Buy and hold Apple
- `buy_and_hold.py` (3 functions) - Buy and hold strategy
- `dual_moving_average.py` (4 functions) - SMA crossover
- `dual_ema_talib.py` (4 functions) - EMA crossover with TA-Lib
- `momentum_pipeline.py` (5 functions) - Pipeline momentum strategy
- `olmar.py` (6 functions) - OLMAR (Online Moving Average Reversion)

### 19. Documentation (`rustybt/docs/`)
**Purpose:** In-source documentation files

### 20. Library (`rustybt/lib/`)
**Purpose:** Low-level Cython optimized modules

**Key Components:**
- `adjusted_array.py` (8 classes) - Adjusted arrays
- `labelarray.py` (7 classes) - Categorical arrays
- `quantiles.py` - Quantile calculations
- `normalize.py` - Data normalization

---

## Key Workflows

### 1. Running a Backtest

```python
from rustybt import run_algorithm
from rustybt.api import order, symbol, schedule_function, date_rules, time_rules

def initialize(context):
    context.asset = symbol('AAPL')
    schedule_function(
        rebalance,
        date_rules.month_start(),
        time_rules.market_open()
    )

def rebalance(context, data):
    order_target_percent(context.asset, 1.0)

result = run_algorithm(
    start='2020-01-01',
    end='2021-12-31',
    initialize=initialize,
    capital_base=100000,
    bundle='quandl'
)
```

### 2. Creating a Custom Bundle

```python
from rustybt.data.bundles import register
from rustybt.data.adapters import CSVAdapter

register(
    'my_bundle',
    CSVAdapter(
        directory='path/to/csv_files',
        asset_metadata='path/to/assets.csv'
    )
)
```

### 3. Live Trading Setup

```python
from rustybt.live import LiveTradingEngine
from rustybt.live.brokers import CCXTAdapter

broker = CCXTAdapter(
    exchange='binance',
    api_key='your_api_key',
    secret='your_secret'
)

engine = LiveTradingEngine(
    strategy=MyStrategy,
    broker=broker,
    data_frequency='minute'
)

engine.run()
```

### 4. Strategy Optimization

```python
from rustybt.optimization import BayesianOptimizer
from rustybt.optimization.parameter_space import ParameterSpace

space = ParameterSpace({
    'fast_period': (10, 50),
    'slow_period': (50, 200)
})

optimizer = BayesianOptimizer(
    strategy=MyStrategy,
    parameter_space=space,
    objective='sharpe_ratio',
    n_iterations=100
)

best_params = optimizer.optimize()
```

---

## Development Setup

### Prerequisites
```bash
# Python 3.12 or 3.13
python --version  # Should be 3.12+

# Install uv (recommended) or pip
pip install uv
```

### Installation

```bash
# Clone repository
git clone https://github.com/jerryinyang/rustybt.git
cd rustybt

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
uv pip install -e ".[dev,test]"

# Build Cython extensions
python setup.py build_ext --inplace
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=rustybt --cov-report=html

# Run specific test suite
pytest tests/backtest/
pytest tests/live/
pytest tests/optimization/

# Run benchmarks
pytest tests/benchmarks/ -m benchmark
```

### Code Quality

```bash
# Lint with ruff
ruff check .

# Format with black
black .

# Type check with mypy
mypy rustybt

# Pre-commit hooks
pre-commit install
pre-commit run --all-files
```

### Building Documentation

```bash
# Install docs dependencies
pip install -e ".[docs]"

# Build and serve
mkdocs serve

# Build static site
mkdocs build
```

---

## Testing Strategy

### Test Organization
```
tests/
├── unit/              # Unit tests (fast, isolated)
├── integration/       # Integration tests (slower, dependencies)
├── benchmarks/        # Performance benchmarks
├── property/          # Property-based tests (Hypothesis)
└── regression/        # Regression tests
```

### Test Markers
- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.slow` - Slow tests (skip in CI)
- `@pytest.mark.property` - Property-based tests
- `@pytest.mark.benchmark` - Performance benchmarks
- `@pytest.mark.live` - Requires live API access
- `@pytest.mark.ib_integration` - Requires IB paper account

### Test Coverage
- Target: 90%+ coverage
- Critical paths: 95%+ coverage (finance, execution, data)
- Generated files exempt (\_version.py)

### Property-Based Testing
Uses Hypothesis for:
- Financial calculation correctness
- Decimal precision validation
- Data integrity checks
- API contract verification

---

## Known Issues & Notes

### User-Reported Issues
1. **Benchmarks Status:** Existing benchmarks are incomplete or outdated (as of 2025-11-23)

### Architecture Notes

1. **Legacy Code Migration:**
   - Many modules have relaxed type checking (see pyproject.toml mypy overrides)
   - Gradual migration to strict typing in progress
   - Legacy Zipline code being incrementally modernized

2. **Performance Optimization:**
   - Cython extensions for critical paths
   - Polars for data processing (5-10x pandas)
   - Multi-tier caching (LRU, disk cache)
   - Lazy loading to reduce import time

3. **Decimal Precision:**
   - All financial calculations use Decimal type
   - Prevents floating-point rounding errors
   - Performance impact: ~2-3x slower than float (acceptable for correctness)
   - Configure via `rustybt.finance.decimal.config`

4. **Data Storage:**
   - Primary: Parquet (PyArrow format)
   - Legacy: HDF5 (deprecated, optional install)
   - Metadata: SQLite (asset database)

5. **Live Trading Maturity:**
   - CCXT adapter: Production-ready
   - IB adapter: Beta (paper trading recommended)
   - Bybit/Binance/Hyperliquid: Beta
   - Shadow trading recommended before live deployment

6. **Calendar Support:**
   - Uses exchange-calendars library
   - Supports NYSE, NASDAQ, LSE, TSX, and 20+ exchanges
   - Crypto: 24/7 calendar
   - Forex: 24/5 calendar

---

## Additional Resources

### User-Facing Documentation
- Main docs: /docs/index.md
- API Reference: /docs/api/
- Examples: /docs/examples/
- Guides: /docs/guides/

### Development Documentation
- Architecture (archived): /docs/archive/bmm-20251123-182208/internal/architecture/
- PRD (archived): /docs/archive/bmm-20251123-182208/internal/prd/
- Stories (archived): /docs/archive/bmm-20251123-182208/internal/stories/

### Configuration
- pyproject.toml - Project configuration, dependencies, tooling
- setup.py - Build configuration (Cython extensions)
- mkdocs.yml - Documentation site configuration
- .pre-commit-config.yaml - Git hooks
- pytest.ini - Test configuration

---

**Document Generated:** 2025-11-23
**For:** AI-Assisted Development (BMad Method)
**Workflow:** document-project (exhaustive scan)
**Project:** rustybt v3.0.0+
