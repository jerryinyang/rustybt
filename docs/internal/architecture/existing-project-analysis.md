# Existing Project Analysis

Based on comprehensive analysis of the Zipline-Reloaded codebase at `deps/zipline-reloaded-reference/`, the following represents the current state:

## Current Project State

- **Primary Purpose:** Event-driven algorithmic trading backtesting platform
- **Current Tech Stack:** Python 3.10-3.13, pandas 1.3-3.0, NumPy 1.23+/2.0+, bcolz for OHLCV storage, SQLite/SQLAlchemy for metadata, Cython for performance (19 files)
- **Architecture Style:** Monolithic Python library with event-driven simulation engine
- **Deployment Method:** pip/conda package (zipline-reloaded)

## Available Documentation

- **README.md:** Comprehensive overview, quickstart, examples
- **docs/ folder:** Sphinx documentation site
- **pyproject.toml:** Detailed dependency specifications with tox matrix for Python 3.10-3.13, pandas 1.5-2.3, NumPy 1.x/2.x compatibility
- **Test Coverage:** 88.26% across 79 test files (4,000+ test cases)

## Identified Constraints

- **Numeric Precision:** Uses float64 throughout financial calculations (ledger, position, order modules)
- **Data Storage:** bcolz-zipline for OHLCV (columnar compressed format), HDF5 alternative
- **Backtest-Only:** No live trading engine or broker integrations
- **Asset Types:** Equity and Future focused, no cryptocurrency support
- **Synchronous:** Single-threaded execution despite Cython optimizations
- **Calendar Dependency:** Relies on exchange-calendars (not 24/7 crypto-friendly)

## Zipline-Reloaded Architecture Overview

**Module Structure (12 major modules, 40K LOC):**

| Module | Purpose | Key Files |
|--------|---------|-----------|
| **algorithm** | Core algorithm execution engine | `algorithm.py` (2,800 LOC, TradingAlgorithm class) |
| **finance** | Trading mechanics, order management, portfolio accounting | 18 files: blotter, commission, slippage, ledger, controls |
| **data** | Data ingestion, storage, and retrieval | 22 files: bundles, readers (bcolz, HDF5), data_portal |
| **pipeline** | Factor-based screening and computation framework | 21 files: engine, loaders, factors, filters, classifiers |
| **assets** | Asset metadata management and database | 13 files: AssetFinder, AssetDBWriter, continuous_futures |
| **gens** | Event generators and simulation clock | tradesimulation.py, sim_engine.pyx (Cython clock) |
| **utils** | Shared utilities | 35 files: events, validation, calendar utils |
| **lib** | Performance-critical primitives | 16 Cython files for windows, adjustments, ranking |
| **testing** | Testing fixtures and utilities | 10 files: core.py (51KB), fixtures.py (81KB) |

**Event-Driven Architecture:**
```
MinuteSimulationClock (Cython) → AlgorithmSimulator → TradingAlgorithm → User Strategy
                                         ↓
                                   MetricsTracker
                                         ↓
                                   Blotter (order execution)
```

**Data Flow:**
```
DataPortal (unified interface)
├── equity_daily_reader (BcolzDailyBarReader)
├── equity_minute_reader (BcolzMinuteBarReader)
├── adjustment_reader (SQLiteAdjustmentReader)
└── asset_finder (AssetFinder)
```

---
