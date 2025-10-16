# RustyBT Brownfield Enhancement Architecture

**Version:** 1.1
**Date:** 2025-09-30
**Author:** Winston (Architect)
**Status:** ✅ Complete - Ready for Development with Strict Quality Enforcement

---

## Introduction

This document outlines the architectural approach for enhancing **Zipline-Reloaded** with RustyBT's production-grade capabilities. Its primary goal is to serve as the guiding architectural blueprint for AI-driven development of new features while ensuring seamless integration with the existing system.

**Relationship to Existing Architecture:**
This document supplements the existing Zipline-Reloaded architecture by defining how new components will integrate with current systems. Where conflicts arise between new and existing patterns, this document provides guidance on maintaining consistency while implementing enhancements.

---

## Existing Project Analysis

Based on comprehensive analysis of the Zipline-Reloaded codebase at `deps/zipline-reloaded-reference/`, the following represents the current state:

### Current Project State

- **Primary Purpose:** Event-driven algorithmic trading backtesting platform
- **Current Tech Stack:** Python 3.10-3.13, pandas 1.3-3.0, NumPy 1.23+/2.0+, bcolz for OHLCV storage, SQLite/SQLAlchemy for metadata, Cython for performance (19 files)
- **Architecture Style:** Monolithic Python library with event-driven simulation engine
- **Deployment Method:** pip/conda package (zipline-reloaded)

### Available Documentation

- **README.md:** Comprehensive overview, quickstart, examples
- **docs/ folder:** Sphinx documentation site
- **pyproject.toml:** Detailed dependency specifications with tox matrix for Python 3.10-3.13, pandas 1.5-2.3, NumPy 1.x/2.x compatibility
- **Test Coverage:** 88.26% across 79 test files (4,000+ test cases)

### Identified Constraints

- **Numeric Precision:** Uses float64 throughout financial calculations (ledger, position, order modules)
- **Data Storage:** bcolz-zipline for OHLCV (columnar compressed format), HDF5 alternative
- **Backtest-Only:** No live trading engine or broker integrations
- **Asset Types:** Equity and Future focused, no cryptocurrency support
- **Synchronous:** Single-threaded execution despite Cython optimizations
- **Calendar Dependency:** Relies on exchange-calendars (not 24/7 crypto-friendly)

### Zipline-Reloaded Architecture Overview

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

## Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2025-09-30 | 0.1 | Initial brownfield architecture draft with existing project analysis | Winston (Architect) |
| 2025-09-30 | 1.0 | Complete architecture with all sections, checklist validation, ready for development | Winston (Architect) |
| 2025-09-30 | 1.1 | Added Zero-Mock Enforcement and 10 Code Quality Guardrails (mandatory) | Winston (Architect) |

---

## Enhancement Scope and Integration Strategy

### Enhancement Overview

**Enhancement Type:** Systematic transformation of existing backtesting platform into production-grade live trading system

**Scope:**
- Fork Zipline-Reloaded v3.x as foundation (currently at v3.0.5)
- Transform 10 core functional areas across 3 implementation tiers
- MVP (Epics 1-5): Foundation, Decimal arithmetic, modern data architecture, transaction costs, optimization
- Post-MVP (Epics 6-9): Live trading, Rust optimization, analytics, API layer

**Integration Impact Level:** **HIGH**

Core modules require substantial modification:
- **finance/** → Decimal arithmetic replacement (ledger, position, order, transaction)
- **data/** → Polars/Parquet data layer replacing bcolz
- **gens/** → Extended for live trading mode with real-time clock
- **New modules** → Live trading engine, broker integrations, RESTful API

### Integration Approach

#### Code Integration Strategy

**Parallel Implementation (Epics 1-5):**
- Keep Zipline's float64 implementations alongside new Decimal variants
- Feature flags: `RUSTYBT_USE_DECIMAL`, `RUSTYBT_USE_POLARS`
- Gradual test migration from Zipline fixtures to RustyBT fixtures
- CI runs both legacy and new implementations until validation complete

**Additive Enhancement (Epics 6-9):**
- New modules for live trading, API layer, advanced analytics
- Integration hooks into existing algorithm execution lifecycle
- Maintain backward compatibility for pure backtesting use cases

#### Database Integration

**Preserve:**
- SQLite asset database schema (Zipline ASSET_DB_VERSION 8)
- Asset table structure: equities, futures, exchanges, symbol_mappings

**Extend:**
- New tables for live trading:
  - `broker_connections`: API keys, connection configs
  - `live_positions`: Real-time position tracking with reconciliation timestamps
  - `order_audit_log`: Trade-by-trade audit trail (JSON structured logs)
  - `strategy_state`: Checkpoints for crash recovery

**Migrate:**
- Data bundles: bcolz → Parquet (one-time conversion utility)
- Provide `rustybt bundle migrate <bundle_name>` CLI command
- Support dual-format reads during transition period

#### API Integration

**Preserve (Backtest API):**
- `initialize(context)`: Strategy setup
- `handle_data(context, data)`: Bar-by-bar processing
- `before_trading_start(context, data)`: Pre-market calculations
- `analyze(context, results)`: Post-backtest analysis

**Extend (Live Trading Hooks):**
- `on_order_fill(context, order, transaction)`: Real-time fill notifications
- `on_order_cancel(context, order, reason)`: Cancellation handling
- `on_order_reject(context, order, reason)`: Rejection handling
- `on_broker_message(context, message)`: Custom broker events

**Add (External Integration - Epic 9):**
- RESTful API for remote monitoring and control
- WebSocket API for real-time updates

#### UI Integration

**N/A** - RustyBT remains a library, not an application
- Primary interface: Jupyter notebooks (same as Zipline)
- Optional: Web dashboard for live trading monitoring (Epic 9, lowest priority)

### Compatibility Requirements

#### Existing API Compatibility

**BREAKING CHANGES** - RustyBT does not guarantee Zipline API compatibility (per PRD):
- Users must migrate strategies to use Decimal types for financial calculations
- Data bundle format changes (bcolz → Parquet)
- Some method signatures change (e.g., `order(asset, amount)` amount becomes Decimal)
- **Migration Guide**: Provide comprehensive migration documentation

#### Database Schema Compatibility

**PARTIAL COMPATIBILITY:**
- ✅ Asset database schema preserved (can reuse existing `assets-8.sqlite`)
- ✅ Exchange calendar data compatible
- ❌ Bundle format requires migration (provide conversion tool)
- ❌ Adjustment format may change (Parquet-optimized storage)

#### UI/UX Consistency

**N/A** - Library interface, not end-user application

#### Performance Impact

**Target:** <30% overhead for Decimal vs. float64 (per NFR3)

**Mitigation Strategies:**
1. Profile bottlenecks after Python implementation complete (Epic 7)
2. Apply Rust optimization strategically to hot paths:
   - Decimal arithmetic operations (portfolio value, P&L calculations)
   - Data processing pipelines (resampling, aggregation)
   - Pipeline engine execution (factor computation loops)
3. Polars performance gains expected to offset some Decimal overhead (5-10x faster than pandas)

---

## Tech Stack

### Existing Technology Stack (Preserved from Zipline-Reloaded)

| Category | Technology | Version | Purpose | RustyBT Status |
|----------|-----------|---------|---------|----------------|
| **Language** | Python | 3.12+ | Primary development language | ✅ Keep (require 3.12+ for modern features) |
| **Database** | SQLite | 3.x | Asset metadata, adjustments | ✅ Keep (add live trading tables) |
| **ORM** | SQLAlchemy | >= 2.0 | Database abstraction | ✅ Keep (proven, well-tested) |
| **Calendars** | exchange-calendars | >= 4.2.4 | Trading calendar data | ✅ Keep (extend for 24/7 crypto) |
| **Statistics** | scipy | >= 0.17.1 | Scientific computing | ✅ Keep |
| **Statistics** | statsmodels | >= 0.6.1 | Statistical models | ✅ Keep |
| **Metrics** | empyrical-reloaded | >= 0.5.7 | Performance metrics | ✅ Keep |
| **CLI** | click | >= 4.0.0 | Command-line interface | ✅ Keep (extend with RustyBT commands) |
| **Build** | setuptools + setuptools_scm | Latest | Build system | ✅ Keep (proven workflow) |
| **Testing** | pytest | >= 7.2.0 | Test framework | ✅ Keep |
| **Testing** | pytest-cov | >= 3.0.0 | Coverage reporting | ✅ Keep |
| **Testing** | pytest-xdist | >= 2.5.0 | Parallel testing | ✅ Keep |
| **Linting** | ruff | >= 0.11.12 | Fast linter | ✅ Keep |
| **Type Checking** | mypy | >= 1.10.0 | Static type checker | ✅ Keep (enforce --strict) |
| **Formatting** | black | 24.1+ | Code formatter | ✅ Keep |

### New Technology Additions (RustyBT Enhancements)

| Category | Technology | Version | Purpose | Rationale |
|----------|-----------|---------|---------|-----------|
| **Numeric** | Python Decimal | stdlib | Financial-grade arithmetic | Audit-compliant precision, no rounding errors |
| **DataFrames** | Polars | 1.x (latest) | Fast dataframe operations | 5-10x faster than pandas, lazy evaluation, better memory |
| **Storage** | Parquet | via pyarrow 18.x+ | Columnar OHLCV storage | 50-80% smaller than HDF5, better interoperability, standard format |
| **Arrow** | pyarrow | 18.x+ | Zero-copy data interchange | Polars/Parquet backend, efficient data transfer |
| **Broker APIs** | ccxt | 4.x+ | Unified crypto exchange API | 100+ exchanges, standardized interface |
| **Broker APIs** | ib_async | 1.x+ | Interactive Brokers | Pythonic async interface, proven for stocks/futures |
| **Broker APIs** | binance-connector | 3.x+ | Binance native | Official Python SDK, better than CCXT for Binance |
| **Broker APIs** | pybit | 5.x+ | Bybit native | Official Python SDK |
| **Broker APIs** | hyperliquid-python-sdk | Latest | Hyperliquid DEX | Official SDK for decentralized perpetuals |
| **Data** | yfinance | 0.2.x+ | Yahoo Finance | Free equities/ETFs/forex data |
| **REST API** | FastAPI | 0.115.x+ | RESTful API framework | Modern, fast, auto-documentation (Epic 9) |
| **WebSocket** | websockets | 14.x+ | Real-time API | Live portfolio updates (Epic 9) |
| **Async** | asyncio | stdlib | Async I/O | Broker API calls, live data feeds |
| **Scheduling** | APScheduler | 3.x+ | Task scheduling | Market open/close triggers, custom intervals |
| **Validation** | pydantic | 2.x+ | Data validation | API request/response validation, config management |
| **Property Testing** | hypothesis | 6.x+ | Property-based tests | Decimal arithmetic validation (NFR5) |
| **Rust** | Rust | 1.90+ | Performance optimization | Post-profiling optimization (Epic 7) |
| **Rust Bindings** | PyO3 | 0.26+ | Python/Rust bridge | Python 3.12-3.14 support, free-threaded |
| **Rust Decimal** | rust-decimal | 1.37+ | Rust Decimal type | Performance-critical Decimal operations |

### Technology Stack Rationale

#### Polars over Pandas
- **Performance**: 5-10x faster for large datasets, lazy evaluation, parallel execution
- **Memory**: Columnar memory layout, efficient for OHLCV data
- **Interoperability**: Arrow backend enables zero-copy with Parquet
- **Modern**: Active development, first-class Rust core

#### Parquet over bcolz/HDF5
- **Standardization**: Industry-standard columnar format (Apache Arrow ecosystem)
- **Size**: 50-80% smaller than HDF5 with comparable compression
- **Interoperability**: Works with Spark, DuckDB, Polars, pandas, countless tools
- **Maintenance**: Active ecosystem vs. bcolz (unmaintained since 2018)

#### FastAPI for REST API (Epic 9)
- **Performance**: Comparable to Go/Node.js, async-native
- **Developer Experience**: Auto-generated OpenAPI docs, Pydantic validation
- **Modern**: Type hints, async/await, WebSocket support

#### Multiple Broker Libraries (Not Just CCXT)
- **Flexibility**: CCXT for broad exchange support, native SDKs for performance/features
- **Reliability**: Native SDKs often more stable, better error handling
- **Features**: Native SDKs expose exchange-specific features CCXT doesn't standardize

### Removed Technologies (Deprecated from Zipline)

| Technology | Reason for Removal |
|------------|-------------------|
| **bcolz-zipline** | Unmaintained since 2018, replaced by Parquet/Polars |
| **h5py / tables (PyTables)** | Slow for large datasets, poor interoperability, replaced by Parquet |
| **pandas** (as primary) | Still supported for compatibility but Polars is primary |
| **numpy** (for storage) | Still used for numerical operations but not primary data structure |
| **Cython** (for new code) | Rust provides better performance and safety, keep existing Cython modules until profiled |

---

## Data Models and Schema Changes

### New Database Tables (Extend Zipline Asset DB)

#### broker_connections
Stores broker API credentials and connection configurations for live trading.

```sql
CREATE TABLE broker_connections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    broker_name TEXT NOT NULL,              -- 'binance', 'interactive_brokers', etc.
    connection_type TEXT NOT NULL,          -- 'live', 'paper', 'testnet'
    api_key_encrypted BLOB NOT NULL,        -- Encrypted API key
    api_secret_encrypted BLOB,              -- Encrypted API secret (if applicable)
    additional_credentials TEXT,            -- JSON for extra fields (account_id, passphrase, etc.)
    base_url TEXT,                          -- Custom API endpoint if needed
    is_active BOOLEAN DEFAULT 1,
    created_at INTEGER NOT NULL,            -- Unix timestamp
    updated_at INTEGER NOT NULL,
    last_connected_at INTEGER,
    UNIQUE(broker_name, connection_type)
);
```

**Integration:** Referenced by `LiveTradingEngine` for broker authentication.

#### live_positions
Real-time position tracking with broker reconciliation for live trading mode.

```sql
CREATE TABLE live_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id TEXT NOT NULL,              -- Strategy identifier
    broker_connection_id INTEGER NOT NULL,  -- FK to broker_connections
    asset_sid INTEGER NOT NULL,             -- FK to equities/futures_contracts
    amount TEXT NOT NULL,                   -- Decimal as TEXT (e.g., "1.23456789")
    cost_basis TEXT NOT NULL,               -- Decimal as TEXT
    last_sale_price TEXT NOT NULL,          -- Decimal as TEXT
    last_sale_date INTEGER NOT NULL,        -- Unix timestamp
    broker_reported_amount TEXT,            -- Decimal from broker reconciliation
    broker_reported_price TEXT,             -- Decimal from broker reconciliation
    reconciliation_status TEXT,             -- 'matched', 'mismatch', 'pending'
    last_reconciled_at INTEGER,             -- Unix timestamp
    updated_at INTEGER NOT NULL,
    FOREIGN KEY(broker_connection_id) REFERENCES broker_connections(id),
    FOREIGN KEY(asset_sid) REFERENCES asset_router(sid)
);

CREATE INDEX idx_live_positions_strategy ON live_positions(strategy_id);
CREATE INDEX idx_live_positions_asset ON live_positions(asset_sid);
```

**Integration:** Extends Zipline's `Position` class with broker reconciliation fields. Queried by `LiveTradingEngine` for position synchronization.

#### order_audit_log
Comprehensive trade-by-trade audit trail in JSON format for regulatory compliance.

```sql
CREATE TABLE order_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id TEXT NOT NULL,
    broker_connection_id INTEGER,
    order_id TEXT NOT NULL,                 -- Internal order ID
    broker_order_id TEXT,                   -- Broker's order ID
    asset_sid INTEGER NOT NULL,
    event_type TEXT NOT NULL,               -- 'submitted', 'filled', 'partially_filled', 'canceled', 'rejected'
    event_timestamp INTEGER NOT NULL,       -- Unix timestamp (microsecond precision)
    event_data TEXT NOT NULL,               -- JSON: full order state snapshot
    FOREIGN KEY(broker_connection_id) REFERENCES broker_connections(id),
    FOREIGN KEY(asset_sid) REFERENCES asset_router(sid)
);

CREATE INDEX idx_audit_log_order ON order_audit_log(order_id);
CREATE INDEX idx_audit_log_timestamp ON order_audit_log(event_timestamp);
CREATE INDEX idx_audit_log_strategy ON order_audit_log(strategy_id);
```

**Event Data JSON Schema:**
```json
{
  "order_type": "limit",
  "side": "buy",
  "amount": "100.50",
  "price": "42.125",
  "fill_price": "42.130",
  "filled_amount": "100.50",
  "commission": "0.105",
  "slippage": "0.005",
  "reason": "filled_by_broker",
  "latency_ms": 125
}
```

**Integration:** Written by `LiveBlotter` and `SimulationBlotter` (in audit mode). Queryable via RESTful API for compliance reporting.

#### strategy_state
Checkpoint storage for crash recovery in live trading.

```sql
CREATE TABLE strategy_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id TEXT NOT NULL UNIQUE,
    state_data TEXT NOT NULL,               -- JSON: serialized strategy state
    checkpoint_timestamp INTEGER NOT NULL,  -- Unix timestamp
    portfolio_value TEXT NOT NULL,          -- Decimal as TEXT
    cash TEXT NOT NULL,                     -- Decimal as TEXT
    positions_snapshot TEXT NOT NULL,       -- JSON: list of positions
    pending_orders_snapshot TEXT NOT NULL,  -- JSON: list of pending orders
    custom_state TEXT                       -- JSON: user-defined state from strategy
);

CREATE INDEX idx_strategy_state_timestamp ON strategy_state(checkpoint_timestamp DESC);
```

**State Data JSON Schema:**
```json
{
  "algorithm_state": {
    "portfolio_value": "1000000.00",
    "cash": "250000.00",
    "leverage": "1.5"
  },
  "positions": [
    {"asset_sid": 24, "amount": "100.0", "cost_basis": "42.00"}
  ],
  "pending_orders": [
    {"order_id": "abc123", "asset_sid": 24, "amount": "50.0", "limit_price": "43.00"}
  ],
  "custom_state": {
    "moving_average_50": "42.35",
    "signal_strength": "0.85"
  }
}
```

**Integration:** Saved by `LiveTradingEngine` at configurable intervals (default: every trade + every 5 minutes). Loaded on strategy restart.

### Decimal Finance Models (Replaces float64)

#### DecimalLedger
Extends Zipline's `Ledger` class with Decimal arithmetic.

**Key Fields:**
```python
from decimal import Decimal
from dataclasses import dataclass
from typing import Dict

@dataclass
class DecimalLedger:
    """Maintains portfolio accounting with Decimal precision."""

    portfolio_value: Decimal          # Total portfolio value
    positions_value: Decimal          # Sum of all position values
    cash: Decimal                     # Available cash
    starting_cash: Decimal            # Initial capital
    leverage: Decimal                 # Current leverage ratio
    pnl: Decimal                      # Unrealized P&L
    returns: Decimal                  # Period returns

    # Transaction costs (tracked separately)
    cumulative_commission: Decimal
    cumulative_slippage: Decimal
    cumulative_borrow_cost: Decimal
    cumulative_financing_cost: Decimal
```

**Integration:** Replaces Zipline's `finance/ledger.py::Ledger` class. All calculations use Decimal context with configurable precision.

#### DecimalPosition
Extends Zipline's `Position` class with Decimal types.

```python
@dataclass
class DecimalPosition:
    """Position tracking with Decimal precision."""

    asset: Asset                      # Asset reference (unchanged)
    amount: Decimal                   # Number of shares/contracts
    cost_basis: Decimal               # Average price paid
    last_sale_price: Decimal          # Current market price
    last_sale_date: pd.Timestamp      # Timestamp of last price update

    @property
    def market_value(self) -> Decimal:
        """Calculate position market value."""
        return self.amount * self.last_sale_price

    @property
    def unrealized_pnl(self) -> Decimal:
        """Calculate unrealized profit/loss."""
        return (self.last_sale_price - self.cost_basis) * self.amount
```

**Integration:** Replaces Zipline's `finance/position.py::Position`. Used by `DecimalLedger` and `PositionTracker`.

#### DecimalTransaction
Extends Zipline's `Transaction` class with Decimal precision.

```python
@dataclass
class DecimalTransaction:
    """Transaction record with Decimal precision."""

    asset: Asset
    amount: Decimal                   # Signed quantity (positive = buy, negative = sell)
    dt: pd.Timestamp
    price: Decimal                    # Execution price
    order_id: str
    commission: Decimal               # Commission paid
    slippage: Decimal                 # Slippage cost

    @property
    def transaction_value(self) -> Decimal:
        """Total transaction value including costs."""
        base_value = abs(self.amount) * self.price
        return base_value + self.commission + self.slippage
```

**Integration:** Replaces Zipline's `finance/transaction.py::Transaction`. Created by `Blotter` on order fills.

### Polars Data Layer Models

#### PolarsBarReader
Replaces Zipline's `BcolzDailyBarReader` and `BcolzMinuteBarReader` with Polars-based readers.

**Interface:**
```python
from abc import ABC, abstractmethod
import polars as pl
from typing import List, Optional

class PolarsBarReader(ABC):
    """Base class for Polars-based bar readers."""

    @abstractmethod
    def load_raw_arrays(
        self,
        sids: List[int],
        fields: List[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp
    ) -> Dict[str, pl.DataFrame]:
        """Load OHLCV data as Polars DataFrames with Decimal columns."""
        pass

    @abstractmethod
    def get_last_traded_dt(self, asset: Asset, dt: pd.Timestamp) -> Optional[pd.Timestamp]:
        """Get last traded datetime for asset before dt."""
        pass
```

**Implementation:**
- `PolarsParquetDailyReader`: Reads daily bars from Parquet files
- `PolarsParquetMinuteReader`: Reads minute bars from Parquet files with partition pruning
- Lazy loading via Polars `scan_parquet()` for efficient memory usage
- Decimal columns for OHLCV data: `Decimal128(18, 8)` dtype

**Integration:** Drop-in replacement for Zipline's `BcolzDailyBarReader` and `BcolzMinuteBarReader`. Used by `DataPortal`.

#### PolarsDataPortal
Extends Zipline's `DataPortal` to work with Polars readers.

**Key Changes:**
- Returns Polars DataFrames instead of pandas DataFrames (with fallback conversion)
- Decimal columns preserved throughout data pipeline
- Supports zero-copy Arrow interchange with data adapters

**Integration:** Replaces Zipline's `data/data_portal.py::DataPortal`. Feature flag: `RUSTYBT_USE_POLARS`.

### Asset Model Extensions

#### Cryptocurrency Asset Type
Extends Zipline's Asset types to support crypto.

```python
@dataclass
class Cryptocurrency(Asset):
    """Cryptocurrency asset metadata."""

    base_currency: str                # 'BTC', 'ETH', etc.
    quote_currency: str               # 'USD', 'USDT', etc.
    exchange: str                     # 'binance', 'coinbase', etc.
    tick_size: Decimal                # Minimum price increment
    lot_size: Decimal                 # Minimum order size
    precision_price: int              # Decimal places for price
    precision_amount: int             # Decimal places for amount
    trading_enabled: bool
    margin_enabled: bool
```

**Database Schema Addition:**
```sql
CREATE TABLE cryptocurrencies (
    sid INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,               -- 'BTC/USDT'
    base_currency TEXT NOT NULL,
    quote_currency TEXT NOT NULL,
    exchange TEXT NOT NULL,
    tick_size TEXT NOT NULL,            -- Decimal as TEXT
    lot_size TEXT NOT NULL,             -- Decimal as TEXT
    precision_price INTEGER,
    precision_amount INTEGER,
    trading_enabled BOOLEAN DEFAULT 1,
    margin_enabled BOOLEAN DEFAULT 0,
    start_date INTEGER,
    end_date INTEGER,
    FOREIGN KEY(sid) REFERENCES asset_router(sid)
);
```

**Integration:** Registered with `AssetFinder`. Used by broker adapters for order validation.

---

## Component Architecture

### Decimal Finance Components

#### DecimalLedger
**Purpose:** Portfolio accounting with Decimal arithmetic
**Location:** `rustybt/finance/decimal/ledger.py`
**Zipline Integration:** Extends `zipline.finance.ledger.Ledger`

**Key Responsibilities:**
- Track portfolio value, cash, positions with Decimal precision
- Calculate returns, P&L, leverage with zero rounding errors
- Maintain transaction cost breakdown (commission, slippage, borrow, financing)
- Support configurable precision per asset class

**Dependencies:**
- `DecimalPosition`: Position tracking
- `DecimalTransaction`: Transaction records
- `decimal.Context`: Precision management

**Integration Points:**
- Used by `TradingAlgorithm` for portfolio state
- Updated by `Blotter` on transaction execution
- Queried by `MetricsTracker` for performance calculation

#### DecimalPosition
**Purpose:** Position tracking with Decimal precision
**Location:** `rustybt/finance/decimal/position.py`
**Zipline Integration:** Replaces `zipline.finance.position.Position`

**Key Responsibilities:**
- Store position amount, cost basis, market price as Decimal
- Calculate market value, unrealized P&L with precision
- Handle splits, dividends with Decimal accuracy
- Support fractional shares for crypto (0.00000001 BTC)

**Integration Points:**
- Created/updated by `PositionTracker` in `DecimalLedger`
- Referenced by `Order` execution logic
- Exposed via `context.portfolio.positions` in user strategies

#### DecimalTransaction
**Purpose:** Transaction record with Decimal precision
**Location:** `rustybt/finance/decimal/transaction.py`
**Zipline Integration:** Replaces `zipline.finance.transaction.Transaction`

**Key Responsibilities:**
- Record trade execution details (price, amount, commission, slippage)
- Store all monetary values as Decimal
- Provide transaction value calculation
- Support audit logging with full precision

**Integration Points:**
- Created by `Blotter` on order fill
- Stored in `order_audit_log` table
- Used by `DecimalLedger` to update positions and cash

### Polars Data Components

#### PolarsParquetDailyReader
**Purpose:** Read daily OHLCV bars from Parquet with Decimal columns
**Location:** `rustybt/data/polars/parquet_daily_bars.py`
**Zipline Integration:** Replaces `zipline.data.bcolz_daily_bars.BcolzDailyBarReader`

**Key Responsibilities:**
- Load daily bars from Parquet files partitioned by (year, month)
- Return Polars DataFrames with Decimal columns
- Support lazy loading via `scan_parquet()` for memory efficiency
- Provide date range queries with partition pruning

**Parquet Schema:**
```python
{
    "date": pl.Date,
    "sid": pl.Int64,
    "open": pl.Decimal(precision=18, scale=8),
    "high": pl.Decimal(precision=18, scale=8),
    "low": pl.Decimal(precision=18, scale=8),
    "close": pl.Decimal(precision=18, scale=8),
    "volume": pl.Decimal(precision=18, scale=8),
}
```

**Directory Structure:**
```
data/bundles/quandl/
├── daily_bars/
│   ├── year=2022/
│   │   ├── month=01/
│   │   │   └── data.parquet
│   │   └── month=02/
│   │       └── data.parquet
│   └── year=2023/
│       └── ...
└── metadata.db (SQLite)
```

**Integration Points:**
- Loaded by `PolarsDataPortal`
- Registered with `AssetFinder` for date range queries
- Used by backtesting engine for historical data

#### PolarsParquetMinuteReader
**Purpose:** Read minute OHLCV bars from Parquet with Decimal columns
**Location:** `rustybt/data/polars/parquet_minute_bars.py`
**Zipline Integration:** Replaces `zipline.data.bcolz_minute_bars.BcolzMinuteBarReader`

**Key Responsibilities:**
- Load minute bars partitioned by (year, month, day) for efficient queries
- Support sub-second resolution for crypto (microsecond timestamps)
- Lazy evaluation for large date ranges
- Cache hot data in memory using Polars DataFrames

**Partition Strategy:**
```
minute_bars/
├── year=2023/
│   ├── month=01/
│   │   ├── day=01/
│   │   │   └── data.parquet  (~500MB/day for 3000 assets)
│   │   └── day=02/
│   │       └── data.parquet
```

**Integration Points:**
- Used by `PolarsDataPortal` for minute-resolution backtests
- Supports multi-resolution aggregation (minute → daily)
- Queried by live trading engine for recent bar data

#### PolarsDataPortal
**Purpose:** Unified data access layer with Polars backend
**Location:** `rustybt/data/polars/data_portal.py`
**Zipline Integration:** Extends `zipline.data.data_portal.DataPortal`

**Key Responsibilities:**
- Provide unified interface to daily/minute readers
- Return Polars DataFrames with Decimal columns
- Support current() and history() methods from Zipline API
- Handle currency conversion for multi-currency portfolios

**API Compatibility:**
```python
class PolarsDataPortal(DataPortal):
    def get_spot_value(
        self, assets: List[Asset], field: str, dt: pd.Timestamp, data_frequency: str
    ) -> pl.Series:
        """Get current field values as Polars Series (Decimal dtype)."""

    def get_history_window(
        self, assets: List[Asset], end_dt: pd.Timestamp, bar_count: int,
        frequency: str, field: str, data_frequency: str
    ) -> pl.DataFrame:
        """Get historical window as Polars DataFrame (Decimal columns)."""
```

**Integration Points:**
- Created by `TradingAlgorithm` during initialization
- Accessed via `data.current()`, `data.history()` in user strategies
- Used by Pipeline engine for factor computation

### Live Trading Components

#### LiveTradingEngine
**Purpose:** Orchestrate live trading execution with broker integration
**Location:** `rustybt/live/engine.py`
**Zipline Integration:** New component (no Zipline equivalent)

**Key Responsibilities:**
- Initialize broker connections via adapter pattern
- Maintain real-time portfolio state with broker reconciliation
- Execute scheduled calculations (market open/close, custom triggers)
- Handle order lifecycle (submit → fill/cancel/reject)
- Checkpoint strategy state for crash recovery
- Coordinate between user strategy and broker adapter

**Architecture:**
```python
class LiveTradingEngine:
    def __init__(
        self,
        strategy: TradingAlgorithm,
        broker_adapter: BrokerAdapter,
        data_portal: PolarsDataPortal,
        scheduler: APScheduler
    ):
        self.strategy = strategy
        self.broker = broker_adapter
        self.data_portal = data_portal
        self.scheduler = scheduler
        self.position_reconciler = PositionReconciler(broker_adapter)
        self.state_manager = StateManager()

    async def run(self):
        """Main live trading loop."""
        # Load saved state if exists
        self.state_manager.load_checkpoint(self.strategy.name)

        # Schedule strategy callbacks
        self.scheduler.add_job(
            self.on_market_open, trigger='cron', hour=9, minute=30
        )
        self.scheduler.add_job(
            self.on_market_close, trigger='cron', hour=16, minute=0
        )

        # Start real-time data feed
        await self.broker.subscribe_market_data(self.strategy.assets)

        # Event loop
        while True:
            event = await self.broker.get_next_event()
            await self.process_event(event)
```

**Integration Points:**
- Instantiated by user script for live trading
- Uses `BrokerAdapter` for broker communication
- Calls `TradingAlgorithm` lifecycle methods
- Writes to `strategy_state` and `order_audit_log` tables

#### BrokerAdapter (Abstract Base)
**Purpose:** Standardized interface for broker integrations
**Location:** `rustybt/live/brokers/base.py`
**Zipline Integration:** New component (no Zipline equivalent)

**Interface:**
```python
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from decimal import Decimal

class BrokerAdapter(ABC):
    """Abstract base class for broker integrations."""

    @abstractmethod
    async def connect(self, credentials: Dict[str, str]) -> bool:
        """Establish connection to broker API."""

    @abstractmethod
    async def submit_order(
        self, asset: Asset, amount: Decimal, order_type: str,
        limit_price: Optional[Decimal] = None
    ) -> str:
        """Submit order to broker, return broker_order_id."""

    @abstractmethod
    async def cancel_order(self, broker_order_id: str) -> bool:
        """Cancel pending order."""

    @abstractmethod
    async def get_positions(self) -> List[Dict]:
        """Fetch current positions from broker."""

    @abstractmethod
    async def get_account_info(self) -> Dict[str, Decimal]:
        """Fetch account balance, buying power, margin info."""

    @abstractmethod
    async def subscribe_market_data(self, assets: List[Asset]):
        """Subscribe to real-time market data stream."""

    @abstractmethod
    async def get_next_event(self) -> Dict:
        """Get next event (fill, cancel, price update) from broker."""
```

**Implementations:**
- `CCXTAdapter`: Generic crypto exchange adapter (100+ exchanges)
- `IBAdapter`: Interactive Brokers (stocks, futures, options, forex)
- `BinanceAdapter`: Binance-specific (uses binance-connector)
- `BybitAdapter`: Bybit-specific (uses pybit)
- `HyperliquidAdapter`: Hyperliquid DEX (uses hyperliquid-python-sdk)

**Error Handling:**
- Retry logic with exponential backoff for transient errors
- Rate limiting per broker API specifications
- Disconnect/reconnect handling with state preservation

#### CCXTAdapter
**Purpose:** Unified crypto exchange integration via CCXT
**Location:** `rustybt/live/brokers/ccxt_adapter.py`
**Zipline Integration:** New component

**Key Features:**
- Support 100+ exchanges via CCXT unified API
- Configurable exchange selection (Binance, Coinbase, Kraken, etc.)
- WebSocket support for real-time data (where available)
- Automatic rate limiting per exchange metadata
- Order type mapping (Market, Limit, Stop, Stop-Limit)

**Implementation:**
```python
import ccxt
from typing import Dict, Decimal

class CCXTAdapter(BrokerAdapter):
    def __init__(self, exchange_id: str, testnet: bool = False):
        self.exchange_id = exchange_id
        self.testnet = testnet
        self.exchange: Optional[ccxt.Exchange] = None

    async def connect(self, credentials: Dict[str, str]) -> bool:
        exchange_class = getattr(ccxt, self.exchange_id)
        self.exchange = exchange_class({
            'apiKey': credentials['api_key'],
            'secret': credentials['api_secret'],
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}  # or 'future'
        })

        if self.testnet:
            self.exchange.set_sandbox_mode(True)

        # Test connection
        await self.exchange.fetch_balance()
        return True

    async def submit_order(
        self, asset: Cryptocurrency, amount: Decimal, order_type: str,
        limit_price: Optional[Decimal] = None
    ) -> str:
        symbol = f"{asset.base_currency}/{asset.quote_currency}"

        order = await self.exchange.create_order(
            symbol=symbol,
            type=order_type.lower(),  # 'market', 'limit'
            side='buy' if amount > 0 else 'sell',
            amount=str(abs(amount)),
            price=str(limit_price) if limit_price else None
        )

        return order['id']
```

**Integration Points:**
- Registered with `LiveTradingEngine`
- Used by crypto-focused strategies
- Supports both spot and futures markets

#### IBAdapter
**Purpose:** Interactive Brokers integration for stocks/futures/options
**Location:** `rustybt/live/brokers/ib_adapter.py`
**Zipline Integration:** New component

**Key Features:**
- Uses ib_async for Pythonic async interface
- Support stocks, futures, options, forex
- Real-time market data via IB streaming
- Order types: Market, Limit, Stop, Stop-Limit, Trailing Stop, Bracket
- TWS/Gateway connection with automatic reconnection

**Implementation:**
```python
from ib_async import IB, Stock, Future, Order, util
from typing import Decimal

class IBAdapter(BrokerAdapter):
    def __init__(self, host: str = '127.0.0.1', port: int = 7497):
        self.ib = IB()
        self.host = host
        self.port = port

    async def connect(self, credentials: Dict[str, str]) -> bool:
        await self.ib.connectAsync(self.host, self.port, clientId=1)

        # Subscribe to events
        self.ib.orderStatusEvent += self.on_order_status
        self.ib.execDetailsEvent += self.on_execution

        return self.ib.isConnected()

    async def submit_order(
        self, asset: Asset, amount: Decimal, order_type: str,
        limit_price: Optional[Decimal] = None
    ) -> str:
        # Create IB contract
        if isinstance(asset, Equity):
            contract = Stock(asset.symbol, asset.exchange, 'USD')
        elif isinstance(asset, Future):
            contract = Future(asset.symbol, asset.exchange)

        # Create IB order
        order = Order()
        order.action = 'BUY' if amount > 0 else 'SELL'
        order.totalQuantity = abs(float(amount))
        order.orderType = order_type.upper()

        if limit_price:
            order.lmtPrice = float(limit_price)

        trade = self.ib.placeOrder(contract, order)
        return str(trade.order.orderId)
```

**Integration Points:**
- Requires TWS or IB Gateway running locally
- Used for traditional asset classes (stocks, futures, options)
- Supports paper trading mode via paper trading account

### Data Adapter Components

#### BaseDataAdapter
**Purpose:** Extensible framework for data source integrations
**Location:** `rustybt/data/adapters/base.py`
**Zipline Integration:** New component

**Interface:**
```python
from abc import ABC, abstractmethod
import polars as pl
from typing import List

class BaseDataAdapter(ABC):
    """Base class for data source adapters."""

    @abstractmethod
    async def fetch(
        self, symbols: List[str], start_date: pd.Timestamp,
        end_date: pd.Timestamp, resolution: str
    ) -> pl.DataFrame:
        """Fetch OHLCV data and return Polars DataFrame with Decimal columns."""

    @abstractmethod
    def validate(self, df: pl.DataFrame) -> bool:
        """Validate OHLCV relationships and data quality."""

    @abstractmethod
    def standardize(self, df: pl.DataFrame) -> pl.DataFrame:
        """Convert provider-specific format to RustyBT standard schema."""
```

**Standard Schema:**
```python
{
    "timestamp": pl.Datetime("us"),       # Microsecond precision
    "symbol": pl.Utf8,
    "open": pl.Decimal(18, 8),
    "high": pl.Decimal(18, 8),
    "low": pl.Decimal(18, 8),
    "close": pl.Decimal(18, 8),
    "volume": pl.Decimal(18, 8),
}
```

**Validation Logic:**
- OHLCV relationships: `high >= max(open, close)`, `low <= min(open, close)`
- Outlier detection: flag price changes >3 standard deviations
- Temporal consistency: timestamps sorted, no duplicates
- Completeness: no NULL values in required fields

#### CCXTDataAdapter
**Purpose:** Fetch crypto OHLCV data via CCXT
**Location:** `rustybt/data/adapters/ccxt_adapter.py`
**Zipline Integration:** New component

**Features:**
- Support 100+ exchanges for historical data
- Resolutions: 1m, 5m, 15m, 1h, 4h, 1d, 1w
- Rate limiting per exchange
- Retry logic for transient failures

**Integration Points:**
- Used by `DataCatalog` to ingest crypto data
- Cached locally in Parquet format
- Queried during backtest initialization

#### YFinanceAdapter
**Purpose:** Fetch stock/ETF/forex data via yfinance
**Location:** `rustybt/data/adapters/yfinance_adapter.py`
**Zipline Integration:** New component

**Features:**
- Free data for stocks, ETFs, forex, indices
- Resolutions: 1m, 5m, 15m, 30m, 1h, 1d, 1wk, 1mo
- Dividend and split data included
- Adjusted and unadjusted prices

**Integration Points:**
- Used by `DataCatalog` for equity backtests
- Cached with checksum validation
- Supports both live and historical data

#### CSVAdapter
**Purpose:** Import custom data from CSV files
**Location:** `rustybt/data/adapters/csv_adapter.py`
**Zipline Integration:** Extends Zipline's `csvdir` bundle concept

**Features:**
- Flexible schema mapping (configure column names)
- Multiple date formats (ISO8601, MM/DD/YYYY, epoch)
- Delimiter detection (comma, tab, semicolon, pipe)
- Missing data handling (skip, interpolate, fail)

**Configuration:**
```yaml
csv_adapter:
  file_path: "/data/custom_data.csv"
  schema_mapping:
    date_column: "Date"
    open_column: "Open"
    high_column: "High"
    low_column: "Low"
    close_column: "Close"
    volume_column: "Volume"
  date_format: "%Y-%m-%d"
  delimiter: ","
  timezone: "UTC"
```

**Integration Points:**
- Used for proprietary data sources
- Converts to Parquet for consistent storage
- Validates against standard schema

---

## External API Integration

### Broker API Integration

#### Interactive Brokers (ib_async)
**Library:** `ib_async` (Pythonic async wrapper for IB API)
**Use Case:** Stocks, futures, options, forex for traditional markets
**Connection:** TWS or IB Gateway (localhost or remote)

**Authentication:**
```python
credentials = {
    "host": "127.0.0.1",
    "port": 7497,        # 7497=live, 7496=paper
    "client_id": 1
}
```

**Supported Order Types:**
- Market, Limit, Stop, Stop-Limit, Trailing Stop
- Bracket (entry + stop-loss + take-profit)
- OCO (One-Cancels-Other)

**Rate Limits:**
- 50 requests/second for market data
- 100 orders/second for order submission
- No API key required (local connection)

**Error Handling:**
- Connection timeout: 30s
- Reconnection with exponential backoff
- Order status polling for confirmation

#### Binance (binance-connector)
**Library:** `binance-connector` (official Python SDK)
**Use Case:** Spot and futures crypto trading
**Endpoint:** `https://api.binance.com` (live), `https://testnet.binance.vision` (testnet)

**Authentication:**
```python
credentials = {
    "api_key": "...",
    "api_secret": "...",
    "testnet": False
}
```

**Supported Order Types:**
- Market, Limit, Stop-Loss, Stop-Loss-Limit, Take-Profit, Take-Profit-Limit
- OCO (One-Cancels-Other)
- Iceberg (partial quantity display)

**Rate Limits:**
- REST API: 1200 requests/minute (weight-based)
- WebSocket: 5 connections per IP
- Order placement: 100 orders/10s per symbol

**Error Codes:**
- `-1021`: Timestamp out of sync (adjust local clock)
- `-1022`: Invalid signature (check secret)
- `-2010`: Insufficient balance
- `-2011`: Order would trigger immediately (market order on limit-only market)

#### Bybit (pybit)
**Library:** `pybit` (official Python SDK)
**Use Case:** Spot and derivatives crypto trading
**Endpoint:** `https://api.bybit.com` (live), `https://api-testnet.bybit.com` (testnet)

**Authentication:**
```python
credentials = {
    "api_key": "...",
    "api_secret": "...",
    "testnet": True
}
```

**Supported Order Types:**
- Market, Limit, Conditional (stop/take-profit)
- Post-Only (maker-only)
- Reduce-Only (close positions)

**Rate Limits:**
- REST API: 120 requests/minute
- WebSocket: 10 messages/second
- Order placement: 100 orders/second per symbol

#### Hyperliquid (hyperliquid-python-sdk)
**Library:** `hyperliquid-python-sdk` (official SDK)
**Use Case:** Decentralized perpetual futures
**Endpoint:** `https://api.hyperliquid.xyz`

**Authentication:**
```python
credentials = {
    "private_key": "...",  # Ethereum private key
    "account_address": "0x..."
}
```

**Supported Order Types:**
- Market, Limit, Stop-Market, Stop-Limit
- Post-Only (maker-only)
- Reduce-Only (close positions)

**Rate Limits:**
- REST API: 600 requests/minute
- WebSocket: Real-time updates (no polling needed)
- Order placement: 20 orders/second

**Unique Features:**
- On-chain settlement (L1 Arbitrum)
- No KYC required
- Sub-account support
- Perpetual futures only (no spot)

#### CCXT (Generic Multi-Exchange)
**Library:** `ccxt` v4.x+
**Use Case:** 100+ crypto exchanges with unified API
**Supported Exchanges:** Binance, Coinbase, Kraken, FTX, Huobi, OKX, Bitfinex, etc.

**Authentication:**
```python
import ccxt
exchange = ccxt.binance({
    'apiKey': '...',
    'secret': '...',
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'}  # or 'future'
})
```

**Unified Order Types:**
- Market, Limit (standardized across exchanges)
- Stop, Stop-Limit (where supported)
- Exchange-specific types via `exchange.create_order(type='exchange_specific_type')`

**Rate Limiting:**
- Automatic per-exchange rate limiting via `enableRateLimit: True`
- Respects exchange metadata for limits
- Built-in queue and delay management

**Error Handling:**
- `ccxt.NetworkError`: Connection issues, retry
- `ccxt.ExchangeError`: Exchange-specific errors
- `ccxt.InsufficientFunds`: Insufficient balance
- `ccxt.InvalidOrder`: Order validation failed

### Data API Integration

#### Yahoo Finance (yfinance)
**Library:** `yfinance` 0.2.x+
**Use Case:** Free historical and live data for stocks, ETFs, forex, indices
**Cost:** Free (no API key required)

**Data Coverage:**
- Stocks: NYSE, NASDAQ, global exchanges
- ETFs: US and international
- Forex: Major currency pairs (EURUSD=X)
- Indices: S&P 500 (^GSPC), Dow Jones (^DJI)
- Commodities: Gold (GC=F), Oil (CL=F)

**Resolutions:**
- Intraday: 1m, 2m, 5m, 15m, 30m, 60m, 90m (max 60 days history)
- Daily: 1d (unlimited history)
- Weekly/Monthly: 1wk, 1mo, 3mo

**API Usage:**
```python
import yfinance as yf

# Single ticker
ticker = yf.Ticker("AAPL")
hist = ticker.history(period="1mo", interval="1d")

# Multiple tickers
data = yf.download(
    tickers="AAPL MSFT GOOGL",
    start="2023-01-01",
    end="2023-12-31",
    interval="1d"
)
```

**Rate Limits:**
- No official rate limit, but recommended: <2000 requests/hour
- Implement 1-second delay between requests
- Yahoo may block aggressive scraping

**Data Quality:**
- Adjusted prices for splits and dividends
- Corporate actions data included
- Occasional missing bars (gaps)
- 15-20 minute delay for live data

#### CCXT (Market Data)
**Library:** `ccxt` v4.x+
**Use Case:** Historical crypto OHLCV data from 100+ exchanges
**Cost:** Free (some exchanges require API key even for public data)

**Data Coverage:**
- OHLCV: All trading pairs per exchange
- Resolutions: 1m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M
- History: Varies by exchange (typically 500-1000 bars per request)

**API Usage:**
```python
import ccxt
exchange = ccxt.binance()

# Fetch OHLCV
ohlcv = exchange.fetch_ohlcv(
    symbol='BTC/USDT',
    timeframe='1h',
    since=exchange.parse8601('2023-01-01T00:00:00Z'),
    limit=1000
)
```

**Rate Limits:**
- Per-exchange (Binance: 1200 req/min, Coinbase: 10 req/sec)
- Use `exchange.enableRateLimit = True` for automatic throttling

**Data Quality:**
- Real-time data where supported
- Historical gaps for low-liquidity pairs
- Timestamp alignment varies by exchange (align to UTC)

#### Optional: Polygon.io, Alpaca, Alpha Vantage
**Status:** Out of MVP scope (Epic 6)
**Use Case:** Premium data sources with higher quality and more features

**Polygon.io:**
- Stocks, options, forex, crypto
- Real-time and historical data
- Cost: $29-$399/month
- Websocket streaming

**Alpaca:**
- Commission-free stock trading
- Real-time market data
- Free for paper trading
- Cost: $0-$99/month for live data

**Alpha Vantage:**
- Stocks, forex, crypto, technical indicators
- Free tier: 5 requests/minute, 500 requests/day
- Premium: $49.99-$499/month

**Integration:** Same `BaseDataAdapter` interface, prioritize post-MVP.

### WebSocket Streaming (Epic 6)
**Purpose:** Real-time market data for live trading
**Status:** Deferred to Epic 6 (out of MVP)

**Supported Brokers:**
- Binance: `wss://stream.binance.com:9443`
- Bybit: `wss://stream.bybit.com/v5/public/spot`
- Hyperliquid: `wss://api.hyperliquid.xyz/ws`
- Interactive Brokers: via ib_async subscription

**Features:**
- Subscribe to orderbook updates (bid/ask)
- Trade stream for tick-by-tick data
- Kline (candlestick) stream for bar data
- Account updates for position changes

**Implementation:**
```python
import websockets
import json

async def subscribe_binance_kline(symbol: str, interval: str):
    uri = "wss://stream.binance.com:9443/ws"
    async with websockets.connect(uri) as ws:
        subscribe_msg = {
            "method": "SUBSCRIBE",
            "params": [f"{symbol.lower()}@kline_{interval}"],
            "id": 1
        }
        await ws.send(json.dumps(subscribe_msg))

        async for message in ws:
            data = json.loads(message)
            if 'k' in data:
                kline = data['k']
                # Process kline data
                yield {
                    "timestamp": kline['t'],
                    "open": Decimal(kline['o']),
                    "high": Decimal(kline['h']),
                    "low": Decimal(kline['l']),
                    "close": Decimal(kline['c']),
                    "volume": Decimal(kline['v'])
                }
```

---

## Source Tree

### RustyBT Directory Structure

```
rustybt/                                  # Root package
├── __init__.py
├── __main__.py                          # CLI entry point
├── version.py
│
├── finance/                             # Financial calculations (Decimal)
│   ├── __init__.py
│   ├── decimal/                         # NEW: Decimal-based modules
│   │   ├── __init__.py
│   │   ├── ledger.py                   # DecimalLedger
│   │   ├── position.py                 # DecimalPosition
│   │   ├── transaction.py              # DecimalTransaction
│   │   ├── blotter.py                  # DecimalBlotter
│   │   └── context.py                  # Decimal precision config
│   ├── commission.py                    # EXTEND: Decimal commission models
│   ├── slippage.py                      # EXTEND: Decimal slippage models
│   ├── execution.py                     # EXTEND: Advanced order types
│   ├── controls.py                      # KEEP: Trading controls (from Zipline)
│   ├── trading.py                       # KEEP: Trading calendar integration
│   └── metrics/                         # EXTEND: Decimal metrics
│       ├── __init__.py
│       ├── core.py                      # Decimal performance metrics
│       └── tracker.py                   # Decimal metrics tracker
│
├── data/                                # Data management (Polars)
│   ├── __init__.py
│   ├── polars/                          # NEW: Polars-based data layer
│   │   ├── __init__.py
│   │   ├── parquet_daily_bars.py       # PolarsParquetDailyReader
│   │   ├── parquet_minute_bars.py      # PolarsParquetMinuteReader
│   │   ├── data_portal.py              # PolarsDataPortal
│   │   └── catalog.py                  # DataCatalog with caching
│   ├── adapters/                        # NEW: Data source adapters
│   │   ├── __init__.py
│   │   ├── base.py                     # BaseDataAdapter
│   │   ├── ccxt_adapter.py             # CCXTDataAdapter
│   │   ├── yfinance_adapter.py         # YFinanceAdapter
│   │   ├── csv_adapter.py              # CSVAdapter
│   │   └── registry.py                 # Adapter registration
│   ├── bundles/                         # KEEP: Bundle management (from Zipline)
│   │   ├── __init__.py
│   │   ├── core.py                     # EXTEND: Add Parquet bundle writer
│   │   ├── csvdir.py                   # KEEP: CSV bundle support
│   │   └── migration.py                # NEW: bcolz → Parquet migration
│   ├── bar_reader.py                    # KEEP: Abstract BarReader interface
│   ├── adjustments.py                   # KEEP: Corporate actions (from Zipline)
│   └── resample.py                      # EXTEND: Polars-based resampling
│
├── live/                                # NEW: Live trading engine
│   ├── __init__.py
│   ├── engine.py                        # LiveTradingEngine
│   ├── reconciler.py                    # PositionReconciler (broker sync)
│   ├── state_manager.py                 # StateManager (checkpointing)
│   ├── scheduler.py                     # TradingScheduler (market triggers)
│   ├── brokers/                         # Broker adapters
│   │   ├── __init__.py
│   │   ├── base.py                     # BrokerAdapter (abstract)
│   │   ├── ccxt_adapter.py             # CCXTAdapter (100+ exchanges)
│   │   ├── ib_adapter.py               # IBAdapter (Interactive Brokers)
│   │   ├── binance_adapter.py          # BinanceAdapter (native SDK)
│   │   ├── bybit_adapter.py            # BybitAdapter (native SDK)
│   │   ├── hyperliquid_adapter.py      # HyperliquidAdapter (DEX)
│   │   └── paper_broker.py             # PaperBroker (simulation)
│   └── streaming/                       # NEW: WebSocket data feeds (Epic 6)
│       ├── __init__.py
│       ├── base.py                     # BaseStreamAdapter
│       └── binance_stream.py           # BinanceStreamAdapter
│
├── assets/                              # Asset management (extended)
│   ├── __init__.py
│   ├── assets.py                        # EXTEND: Add Cryptocurrency class
│   ├── asset_db_schema.py              # EXTEND: Add cryptocurrencies table
│   ├── asset_writer.py                 # EXTEND: Write crypto assets
│   ├── asset_finder.py                 # KEEP: AssetFinder (from Zipline)
│   ├── futures.py                       # KEEP: Futures contracts
│   └── continuous_futures.py           # KEEP: Continuous futures
│
├── algorithm.py                         # EXTEND: TradingAlgorithm with live hooks
├── api.py                               # EXTEND: Add live trading API functions
│
├── pipeline/                            # KEEP: Pipeline framework (from Zipline)
│   ├── __init__.py
│   ├── engine.py                        # EXTEND: Polars-compatible pipeline engine
│   ├── factors/                         # KEEP: Factor library
│   ├── filters/                         # KEEP: Filter library
│   └── classifiers/                     # KEEP: Classifier library
│
├── gens/                                # EXTEND: Event generators
│   ├── __init__.py
│   ├── tradesimulation.py              # KEEP: Simulation mode (from Zipline)
│   ├── live_simulation.py              # NEW: Live trading mode
│   └── clock.py                         # NEW: Unified clock (sim + live)
│
├── utils/                               # KEEP: Shared utilities (from Zipline)
│   ├── __init__.py
│   ├── events.py                        # KEEP: Event system
│   ├── calendar_utils.py               # EXTEND: 24/7 crypto calendars
│   ├── validation.py                    # EXTEND: Decimal validation
│   └── security.py                      # NEW: Credential encryption
│
├── optimization/                        # NEW: Strategy optimization (Epic 5)
│   ├── __init__.py
│   ├── optimizer.py                     # Optimizer framework
│   ├── search/                          # Search algorithms
│   │   ├── __init__.py
│   │   ├── grid_search.py
│   │   ├── random_search.py
│   │   ├── bayesian_search.py
│   │   └── genetic_algorithm.py
│   ├── walk_forward.py                  # Walk-forward optimization
│   ├── monte_carlo.py                   # Monte Carlo simulation
│   └── sensitivity.py                   # Parameter sensitivity analysis
│
├── api_layer/                           # NEW: RESTful/WebSocket API (Epic 9)
│   ├── __init__.py
│   ├── app.py                           # FastAPI application
│   ├── routes/                          # API endpoints
│   │   ├── __init__.py
│   │   ├── strategies.py               # Strategy management
│   │   ├── portfolio.py                # Portfolio queries
│   │   ├── orders.py                   # Order management
│   │   └── data.py                     # Data catalog access
│   ├── websocket.py                     # WebSocket server
│   └── auth.py                          # Authentication/authorization
│
├── analytics/                           # NEW: Advanced analytics (Epic 8)
│   ├── __init__.py
│   ├── attribution.py                   # Performance attribution
│   ├── risk.py                          # Risk metrics (VaR, CVaR, beta)
│   ├── trade_analysis.py               # Trade-level analysis
│   └── reports.py                       # Report generation
│
├── testing/                             # KEEP: Testing utilities (from Zipline)
│   ├── __init__.py
│   ├── fixtures.py                      # EXTEND: Add Decimal fixtures
│   ├── core.py                          # KEEP: Test utilities
│   └── property_tests.py               # NEW: Hypothesis property tests
│
├── cli/                                 # EXTEND: CLI commands
│   ├── __init__.py
│   ├── commands.py                      # EXTEND: Add RustyBT commands
│   ├── run.py                           # KEEP: Run backtest command
│   ├── bundle.py                        # EXTEND: Add migration command
│   └── live.py                          # NEW: Live trading commands
│
└── rust/                                # NEW: Rust optimization modules (Epic 7)
    ├── Cargo.toml                       # Rust package manifest
    ├── src/
    │   ├── lib.rs                       # PyO3 module entry point
    │   ├── decimal.rs                   # Decimal arithmetic operations
    │   ├── data.rs                      # Data processing pipelines
    │   └── indicators.rs                # Technical indicators
    └── build.rs                         # Build script
```

### Integration with Zipline Structure

**Preserved Zipline Modules:**
- `algorithm.py`: Extended with live trading hooks
- `assets/`: Extended with cryptocurrency support
- `data/bundles/`: Extended with Parquet support
- `pipeline/`: Extended with Polars compatibility
- `utils/`: Extended with additional utilities
- `testing/`: Extended with Decimal fixtures

**New RustyBT Modules:**
- `finance/decimal/`: Decimal arithmetic layer
- `data/polars/`: Polars/Parquet data layer
- `data/adapters/`: Data source adapters
- `live/`: Live trading engine
- `optimization/`: Optimization framework
- `api_layer/`: REST/WebSocket API
- `analytics/`: Advanced analytics
- `rust/`: Rust performance modules

**Migration Path:**
1. Epics 1-5: Parallel implementation (Zipline float + RustyBT Decimal coexist)
2. Epic 6: Add live trading (no Zipline equivalent)
3. Epic 7: Add Rust optimization (transparent to users)
4. Epic 8-9: Add analytics and API (additive features)

---

## Infrastructure and Deployment Integration

### Self-Hosted Deployment Strategy

**Philosophy:** RustyBT is a library for self-hosted deployment with no cloud dependencies. Users maintain full control over infrastructure, data, and execution.

#### Deployment Modes

**1. Local Development (Jupyter Notebooks)**
- **Environment:** Laptop/desktop with Python 3.12+ virtual environment
- **Use Case:** Strategy development, backtesting, research
- **Setup:**
  ```bash
  python -m venv rustybt-env
  source rustybt-env/bin/activate
  pip install rustybt
  jupyter lab
  ```
- **Data Storage:** Local Parquet files in `~/.rustybt/data/`
- **Database:** SQLite in `~/.rustybt/assets.db`

**2. Live Trading Server (Single Strategy)**
- **Environment:** Dedicated Linux VPS or bare-metal server
- **Use Case:** Production live trading for single strategy
- **Recommended Specs:**
  - CPU: 4+ cores
  - RAM: 8GB+ (16GB for high-frequency strategies)
  - Disk: 100GB+ SSD (for data caching)
  - Network: Low latency to broker (co-location preferred for HFT)
- **Setup:**
  ```bash
  # Install as systemd service
  sudo systemctl enable rustybt-strategy1
  sudo systemctl start rustybt-strategy1
  ```
- **Monitoring:** Logs to `journalctl`, metrics to local Prometheus instance
- **Data Storage:** Local Parquet files, SQLite database
- **Backup:** Daily backup of `strategy_state` table to S3/local NAS

**3. Multi-Strategy Server (Portfolio)**
- **Environment:** Dedicated server running multiple strategies
- **Use Case:** Production multi-strategy portfolio
- **Recommended Specs:**
  - CPU: 16+ cores
  - RAM: 32GB+
  - Disk: 500GB+ SSD
  - Network: Low latency, high bandwidth
- **Setup:** Multiple RustyBT processes (one per strategy) with shared data cache
- **Monitoring:** Centralized logging via rsyslog, Grafana dashboards
- **Data Storage:** Shared Parquet cache, separate SQLite per strategy
- **Backup:** Hourly state snapshots, daily full backups

**4. Docker Containerized Deployment**
- **Environment:** Docker containers for reproducible deployments
- **Use Case:** Development/production parity, easy deployment
- **Dockerfile:**
  ```dockerfile
  FROM python:3.12-slim

  RUN apt-get update && apt-get install -y gcc g++ && rm -rf /var/lib/apt/lists/*

  WORKDIR /app
  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt

  COPY . .
  RUN pip install --no-cache-dir .

  CMD ["python", "-m", "rustybt", "live", "--config", "/config/strategy.yaml"]
  ```
- **Docker Compose:**
  ```yaml
  version: '3.8'
  services:
    strategy1:
      build: .
      volumes:
        - ./config:/config
        - ./data:/data
        - ./logs:/logs
      environment:
        - RUSTYBT_DATA_DIR=/data
        - RUSTYBT_LOG_LEVEL=INFO
      restart: unless-stopped
  ```

**5. Kubernetes Deployment (Advanced)**
- **Environment:** Kubernetes cluster for high availability
- **Use Case:** Enterprise multi-strategy deployment
- **Features:**
  - Rolling updates without downtime
  - Auto-restart on crash
  - Resource limits and scaling
  - Centralized logging and monitoring

#### Infrastructure Components

**Data Storage:**
- **Parquet Files:** Store historical OHLCV data
  - Location: `/data/bundles/<bundle_name>/`
  - Retention: Unlimited (compressed, ~10GB per year per 1000 assets)
  - Backup: Optional (can re-download from source)
- **SQLite Database:** Asset metadata, live positions, audit logs
  - Location: `/data/assets.db`, `/data/strategy_state.db`
  - Size: 10-100MB typical
  - Backup: Daily full backup, hourly state snapshots

**Logging:**
- **Structured Logs:** JSON format via `structlog`
- **Log Rotation:** 100MB per file, keep 30 days
- **Levels:**
  - INFO: Trade executions, strategy signals
  - WARNING: Failed API calls, reconciliation mismatches
  - ERROR: Order rejections, connection failures
  - DEBUG: Detailed calculations (disabled in production)
- **Storage:** `/logs/rustybt-<strategy>.log`

**Monitoring:**
- **Metrics:** Prometheus-compatible metrics endpoint (Epic 9)
  - Portfolio value, P&L, Sharpe ratio
  - Order fill rate, latency, error rate
  - Data cache hit rate
- **Alerts:** Alert on error rate spike, position mismatch, connectivity loss
- **Dashboards:** Grafana dashboards for live monitoring

**Security:**
- **Credential Storage:** Encrypted at rest using `cryptography` library
  - Encryption key: Environment variable or hardware security module
  - Broker API keys stored in `broker_connections` table (encrypted BLOB)
- **Network Security:**
  - TLS for all broker API calls
  - Firewall rules: Allow only necessary ports
  - VPN for remote server access
- **Access Control:**
  - Restrict file permissions: `chmod 600` for config files
  - Separate user account for RustyBT process
  - No root access required

**Backup Strategy:**
- **Critical Data:**
  - `strategy_state` table: Hourly snapshots
  - `order_audit_log` table: Daily backups
  - Configuration files: Version controlled in git
- **Data Recovery:**
  - Restore state from latest checkpoint
  - Re-download historical data if lost (cached data is reproducible)
- **Backup Locations:**
  - Local NAS
  - Cloud storage (S3, Backblaze) with encryption
  - Offsite backup for disaster recovery

#### High Availability Setup

**Multi-Instance Deployment:**
- Primary instance: Active trading
- Secondary instance: Hot standby, monitors primary
- Failover: Secondary takes over if primary fails (requires manual intervention for safety)

**State Synchronization:**
- Primary writes state to shared storage (NFS or S3)
- Secondary reads state every minute
- Broker position reconciliation on failover

**Health Checks:**
- HTTP health endpoint: `/health` returns 200 if alive
- Heartbeat file: Updated every 30 seconds
- External monitor (e.g., UptimeRobot) pings health endpoint

#### Performance Considerations

**Latency Optimization:**
- Co-location: Deploy server near broker data center
- Network: 10Gbps+ Ethernet, low-latency provider
- Disable swap: Ensure all data in RAM for predictable latency

**CPU Optimization:**
- Rust modules for hot paths (Epic 7)
- Parallel processing for optimization (Ray)
- CPU affinity: Pin processes to specific cores

**Memory Optimization:**
- Polars lazy evaluation: Process data without loading entirely into memory
- Parquet compression: 50-80% smaller than HDF5
- Cache eviction: LRU cache with configurable max size

**Disk I/O Optimization:**
- SSD for data storage
- Separate disk for logs (avoid I/O contention)
- Parquet partition pruning: Read only required date ranges

---

## Coding Standards

### Python Coding Standards

**Language Version:**
- Python 3.12+ required
- Use modern features: structural pattern matching, type hints, asyncio

**Type Hints:**
- 100% type hint coverage for public APIs
- `mypy --strict` compliance enforced in CI/CD
- Use `typing` module for complex types: `List`, `Dict`, `Optional`, `Union`, `Callable`
- Example:
  ```python
  from decimal import Decimal
  from typing import List, Optional

  def calculate_portfolio_value(
      positions: List[DecimalPosition],
      cash: Decimal
  ) -> Decimal:
      """Calculate total portfolio value."""
      positions_value = sum(p.market_value for p in positions, Decimal(0))
      return positions_value + cash
  ```

**Code Formatting:**
- **black** for code formatting (line length: 100)
- **ruff** for linting (replaces flake8, isort, pyupgrade)
- Configuration in `pyproject.toml`:
  ```toml
  [tool.black]
  line-length = 100
  target-version = ['py312']

  [tool.ruff]
  line-length = 100
  target-version = "py312"
  select = ["E", "F", "W", "I", "N", "UP", "ANN", "B", "A", "C4", "DTZ", "T20", "SIM"]
  ```

**Naming Conventions:**
- Classes: `PascalCase` (e.g., `DecimalLedger`, `PolarsDataPortal`)
- Functions/methods: `snake_case` (e.g., `calculate_returns`, `fetch_ohlcv`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `MAX_LEVERAGE`, `DEFAULT_PRECISION`)
- Private members: prefix with `_` (e.g., `_internal_state`, `_validate_order`)

**Docstrings:**
- All public classes, functions, methods require docstrings
- Use Google-style docstrings:
  ```python
  def submit_order(
      self,
      asset: Asset,
      amount: Decimal,
      order_type: str,
      limit_price: Optional[Decimal] = None
  ) -> str:
      """Submit order to broker.

      Args:
          asset: Asset to trade
          amount: Order quantity (positive=buy, negative=sell)
          order_type: 'market', 'limit', 'stop', 'stop-limit'
          limit_price: Limit price for limit/stop-limit orders

      Returns:
          Broker order ID as string

      Raises:
          BrokerError: If order submission fails
          ValidationError: If order parameters invalid
      """
  ```

**Decimal Precision:**
- Import: `from decimal import Decimal, getcontext`
- Set context: `getcontext().prec = 28` (configurable per asset class)
- String construction: `Decimal("42.123")` (never `Decimal(42.123)` to avoid float rounding)
- Comparison: Use Decimal comparison directly (`a > b`), avoid float conversion

**Error Handling:**
- Specific exceptions: Create custom exception classes (e.g., `BrokerError`, `DataAdapterError`)
- Exception hierarchy:
  ```python
  class RustyBTError(Exception):
      """Base exception for RustyBT."""

  class BrokerError(RustyBTError):
      """Broker API error."""

  class OrderRejectedError(BrokerError):
      """Order rejected by broker."""
  ```
- Logging: Always log exceptions with context:
  ```python
  import structlog
  logger = structlog.get_logger()

  try:
      order_id = broker.submit_order(...)
  except BrokerError as e:
      logger.error("order_submission_failed", asset=asset, amount=amount, error=str(e))
      raise
  ```

**Async/Await:**
- Use `async`/`await` for all broker API calls and I/O operations
- Event loop: asyncio (standard library)
- Example:
  ```python
  async def fetch_positions(self) -> List[Dict]:
      async with aiohttp.ClientSession() as session:
          async with session.get(self.positions_url) as response:
              return await response.json()
  ```

**Logging:**
- Use `structlog` for structured logging
- Log levels:
  - DEBUG: Detailed calculations, internal state
  - INFO: Trade executions, strategy signals, state checkpoints
  - WARNING: Retries, reconciliation mismatches, degraded performance
  - ERROR: Order rejections, connection failures, exceptions
- Example:
  ```python
  logger.info(
      "order_filled",
      order_id=order.id,
      asset=order.asset.symbol,
      fill_price=str(order.fill_price),
      amount=str(order.amount),
      commission=str(order.commission)
  )
  ```

### Zero-Mock Enforcement (MANDATORY)

**The Five Absolutes - NEVER:**
1. **NEVER** return hardcoded values in production code
2. **NEVER** write validation that always succeeds
3. **NEVER** simulate when you should calculate
4. **NEVER** stub when you should implement
5. **NEVER** claim completion for incomplete work
6. **NEVER** simplify a test to avoid an error

**Pre-Commit Checklist (BLOCKING):**

Before EVERY commit, CI/CD will verify:
- ❌ No TODO/FIXME/HACK comments without issue tracking
- ❌ No hardcoded return values (e.g., `return 10`, `return 1.0`, `return True`)
- ❌ No empty `except` blocks or `pass` statements in production code
- ❌ No "mock", "fake", "stub", "dummy" in variable/function names
- ❌ No simplified implementations without SIMPLIFIED warning blocks
- ✅ All tests exercise real functionality, not mocks
- ✅ All validations perform actual checks

**Forbidden Patterns:**

```python
# ❌ ABSOLUTELY FORBIDDEN
def calculate_sharpe_ratio(returns):
    return 1.5  # Mock value

def validate_data(data):
    return True  # Always passes

try:
    risky_operation()
except:
    pass  # Silently swallows errors

# ✅ CORRECT IMPLEMENTATION
def calculate_sharpe_ratio(returns: pl.Series) -> Decimal:
    """Calculate actual Sharpe ratio from returns series."""
    if len(returns) < 2:
        raise ValueError("Insufficient data for Sharpe ratio calculation")
    mean_return = returns.mean()
    std_return = returns.std()
    if std_return == 0:
        return Decimal(0)
    return Decimal(str(mean_return / std_return))

def validate_ohlcv_data(data: pl.DataFrame) -> bool:
    """Validate OHLCV data constraints."""
    # Check required columns exist
    required_cols = ['open', 'high', 'low', 'close', 'volume']
    if not all(col in data.columns for col in required_cols):
        raise ValidationError(f"Missing required columns: {required_cols}")

    # Validate OHLCV relationships
    invalid_rows = data.filter(
        (pl.col('high') < pl.col('low')) |
        (pl.col('high') < pl.col('open')) |
        (pl.col('high') < pl.col('close')) |
        (pl.col('low') > pl.col('open')) |
        (pl.col('low') > pl.col('close'))
    )
    if len(invalid_rows) > 0:
        raise ValidationError(f"Invalid OHLCV relationships in {len(invalid_rows)} rows")

    return True

try:
    order_id = broker.submit_order(asset, amount)
except BrokerConnectionError as e:
    logger.error("broker_connection_failed", error=str(e), broker=broker.name)
    raise BrokerError(f"Failed to connect to {broker.name}: {e}") from e
except OrderRejectedError as e:
    logger.warning("order_rejected", asset=asset, amount=amount, reason=str(e))
    raise
```

**Automated Enforcement in CI/CD:**

```yaml
# Required in .github/workflows/quality-enforcement.yml
jobs:
  zero-mock-enforcement:
    runs-on: ubuntu-latest
    steps:
      - name: Detect mock patterns (BLOCKING)
        run: |
          python scripts/detect_mocks.py --strict
          # Returns exit code 1 if ANY mocks found

      - name: Validate hardcoded values (BLOCKING)
        run: |
          python scripts/detect_hardcoded_values.py --fail-on-found

      - name: Check validation functions (BLOCKING)
        run: |
          python scripts/verify_validations.py --ensure-real-checks

      - name: Test result uniqueness (BLOCKING)
        run: |
          pytest tests/ --unique-results-check
          # Ensures different inputs produce different outputs
```

**Pre-Commit Hook (Installed Automatically):**

```python
#!/usr/bin/env python
# .git/hooks/pre-commit (auto-generated)

import subprocess
import sys

def check_for_violations():
    """Prevent commits with mock code or hardcoded values."""
    checks = [
        ('Mock detection', ['python', 'scripts/detect_mocks.py', '--quick']),
        ('Hardcoded values', ['python', 'scripts/detect_hardcoded_values.py', '--quick']),
        ('Empty except blocks', ['python', 'scripts/check_error_handling.py']),
    ]

    violations = []
    for check_name, command in checks:
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            violations.append((check_name, result.stdout))

    if violations:
        print("❌ COMMIT BLOCKED: Quality violations detected!\n")
        for name, output in violations:
            print(f"\n[{name}]")
            print(output)
        print("\nTo override (NOT RECOMMENDED): git commit --no-verify")
        return False

    print("✅ Pre-commit checks passed")
    return True

if __name__ == "__main__":
    if not check_for_violations():
        sys.exit(1)
```

**Story Completion Criteria (BLOCKING):**

No story can be marked complete without passing:

1. **Mock Scan**: `scripts/detect_mocks.py` returns 0 violations
2. **Validation Test**: All validators reject invalid data
3. **Unique Results Test**: Different inputs produce different outputs
4. **Performance Validation**: Computation shows measurable time (not instant)
5. **Code Review**: Senior developer sign-off on implementation quality

**Consequences:**

- **First Violation**: Mandatory code review training + all code requires senior review for 2 weeks
- **Second Violation**: Removed from critical path stories
- **Third Violation**: Removed from project development team

### Code Quality Guardrails (MANDATORY)

**1. Complexity Limits:**
- Maximum cyclomatic complexity: 10 per function
- Maximum function length: 50 lines
- Maximum file length: 500 lines
- Enforce via `ruff` with complexity checks:
  ```toml
  [tool.ruff.lint.mccabe]
  max-complexity = 10
  ```

**2. Import Organization:**
- Standard library imports first
- Third-party imports second
- Local imports third
- Example:
  ```python
  # Standard library
  from decimal import Decimal
  from typing import List, Optional

  # Third-party
  import polars as pl
  from ccxt import Exchange

  # Local
  from rustybt.finance.decimal import DecimalLedger
  from rustybt.data.polars import PolarsBarReader
  ```

**3. Mutation Safety:**
- Immutable data structures preferred (use `dataclasses(frozen=True)`)
- Functions should not mutate input arguments
- Example:
  ```python
  from dataclasses import dataclass

  @dataclass(frozen=True)
  class DecimalPosition:
      asset: Asset
      amount: Decimal
      cost_basis: Decimal
      last_sale_price: Decimal
  ```

**4. Null Safety:**
- Explicit `Optional` types for nullable values
- No implicit `None` returns
- Example:
  ```python
  def find_position(asset: Asset) -> Optional[DecimalPosition]:
      """Find position for asset, returns None if not found."""
      return self._positions.get(asset.sid)

  # Usage with null check
  position = ledger.find_position(asset)
  if position is not None:
      # Safe to use position
      return position.market_value
  else:
      return Decimal(0)
  ```

**5. Performance Assertions:**
- All performance-critical functions must have benchmarks
- Regression tests fail if performance degrades >20%
- Example:
  ```python
  @pytest.mark.benchmark
  def test_decimal_ledger_performance(benchmark):
      """Ensure ledger updates complete in <1ms."""
      result = benchmark(ledger.process_transaction, transaction)
      assert result.duration < 0.001  # 1ms threshold
  ```

**6. Temporal Integrity Enforcement:**
- All data access must be timestamp-validated
- Forward-looking data access raises `LookaheadError`
- Example:
  ```python
  def get_price(self, asset: Asset, dt: pd.Timestamp) -> Decimal:
      """Get price at timestamp, raises if future data accessed."""
      if dt > self.current_simulation_time:
          raise LookaheadError(
              f"Attempted to access future price at {dt}, "
              f"current time is {self.current_simulation_time}"
          )
      return self._data_portal.get_price(asset, dt)
  ```

**7. Mandatory Code Reviews:**
- All PRs require 2 approvals:
  - 1 from senior developer
  - 1 from financial domain expert (for finance/ modules)
- PR checklist enforced via GitHub Actions:
  - [ ] All tests pass (90%+ coverage)
  - [ ] Mock detection returns 0 violations
  - [ ] Performance benchmarks pass
  - [ ] Documentation updated
  - [ ] CHANGELOG.md entry added

**8. Documentation Requirements:**
- Public API: 100% docstring coverage
- Complex algorithms: Inline comments explaining approach
- Non-obvious decisions: ADR (Architecture Decision Record) in `docs/adr/`
- Example ADR:
  ```markdown
  # ADR-001: Use Decimal for Financial Calculations

  ## Status
  Accepted

  ## Context
  Python float64 causes rounding errors in financial calculations.

  ## Decision
  Use Decimal throughout finance modules.

  ## Consequences
  - ✅ Audit-compliant precision
  - ✅ No rounding errors
  - ❌ 30% performance overhead (mitigated by Rust optimization)
  ```

**9. Security Guardrails:**
- Secrets detection in CI/CD (truffleHog, detect-secrets)
- All API keys must be in environment variables, never hardcoded
- SQL queries use parameterized statements (SQLAlchemy ORM)
- Input sanitization for all external data (Pydantic validation)

**10. Dependency Management:**
- Pin exact versions in `pyproject.toml`
- Weekly `pip-audit` security scan in CI/CD
- Quarterly dependency update review
- No GPL-licensed dependencies (Apache 2.0/MIT only)

### Testing Standards

**Test Coverage:**
- Overall: ≥90%
- Financial modules: ≥95%
- Property-based tests: 1000+ examples per test
- No mocking of production code (unit tests use real implementations)

**Test Organization:**
- Mirror source structure: `tests/finance/test_decimal_ledger.py` → `rustybt/finance/decimal/ledger.py`
- Test file naming: `test_<module>.py`
- Test function naming: `test_<function_name>_<scenario>`

**Test Types:**

**Unit Tests:**
```python
import pytest
from decimal import Decimal
from rustybt.finance.decimal import DecimalLedger, DecimalPosition

def test_portfolio_value_calculation():
    ledger = DecimalLedger(starting_cash=Decimal("100000"))
    position = DecimalPosition(
        asset=Asset(...),
        amount=Decimal("100"),
        cost_basis=Decimal("50"),
        last_sale_price=Decimal("55")
    )
    ledger.positions[position.asset] = position

    expected_value = Decimal("100") * Decimal("55") + Decimal("100000")
    assert ledger.portfolio_value == expected_value
```

**Property-Based Tests:**
```python
from hypothesis import given, strategies as st
from decimal import Decimal

@given(
    starting_cash=st.decimals(min_value=Decimal("1000"), max_value=Decimal("1000000")),
    position_value=st.decimals(min_value=Decimal("0"), max_value=Decimal("500000"))
)
def test_portfolio_value_invariant(starting_cash, position_value):
    """Portfolio value must equal cash + sum of position values."""
    ledger = DecimalLedger(starting_cash=starting_cash)
    # ... add position worth position_value

    assert ledger.portfolio_value == ledger.cash + ledger.positions_value
```

**Integration Tests:**
```python
@pytest.mark.integration
async def test_live_trading_order_lifecycle():
    """Test complete order lifecycle: submit → fill → position update."""
    engine = LiveTradingEngine(strategy=..., broker=PaperBroker())

    # Submit order
    order_id = await engine.submit_order(asset=AAPL, amount=Decimal("100"), order_type="market")

    # Wait for fill
    await asyncio.sleep(1)

    # Verify position
    position = engine.get_position(AAPL)
    assert position.amount == Decimal("100")
    assert position.cost_basis > Decimal("0")
```

**Fixtures:**
```python
@pytest.fixture
def sample_strategy():
    """Create sample strategy for testing."""
    class SampleStrategy(TradingAlgorithm):
        def initialize(self, context):
            context.asset = self.symbol('AAPL')

        def handle_data(self, context, data):
            self.order(context.asset, 100)

    return SampleStrategy()

def test_strategy_execution(sample_strategy):
    # Use fixture in test
    ...
```

### Documentation Standards

**Public API Documentation:**
- 100% docstring coverage for public APIs
- Sphinx-compatible reStructuredText format
- Include examples in docstrings:
  ```python
  def order(self, asset: Asset, amount: Decimal, **kwargs) -> str:
      """Place order for asset.

      Example:
          >>> order(context.asset, Decimal("100"), order_type="limit", limit_price=Decimal("42.50"))
          'order-123'
      """
  ```

**Tutorial Examples:**
- ≥30 tutorial notebooks (Jupyter)
- Categories:
  - Getting Started (5 notebooks)
  - Backtesting Strategies (10 notebooks)
  - Live Trading (8 notebooks)
  - Optimization (5 notebooks)
  - Advanced Topics (2 notebooks)
- Hosted on documentation site with Binder integration

**Architecture Documentation:**
- Keep `docs/architecture.md` updated with major changes
- Add diagrams using Mermaid or PlantUML
- Document integration points between components

**Changelog:**
- Maintain `CHANGELOG.md` following Keep a Changelog format
- Semantic versioning: MAJOR.MINOR.PATCH
- Document breaking changes prominently

---

## Testing Strategy

### Test Coverage Targets

**Overall Coverage:** ≥90% (maintain/improve from Zipline's 88.26%)
**Financial Modules:** ≥95% (critical for correctness)
**New Components:** ≥90% (strict enforcement)

### Test Pyramid

**Unit Tests (70%):**
- Fast, isolated tests for individual functions/classes
- Mock external dependencies (broker APIs, data sources)
- Run on every commit (~5 seconds total)

**Integration Tests (25%):**
- Test component interactions (e.g., LiveTradingEngine + BrokerAdapter)
- Use paper trading accounts for broker integration tests
- Run on pull requests (~2 minutes total)

**End-to-End Tests (5%):**
- Complete workflows (backtest, optimization, live trading)
- Use realistic data and scenarios
- Run nightly (~10 minutes total)

### Property-Based Testing (Hypothesis)

**Purpose:** Validate Decimal arithmetic invariants and financial calculation correctness

**Key Properties:**

**Portfolio Value Invariant:**
```python
from hypothesis import given, strategies as st
from decimal import Decimal

@given(
    cash=st.decimals(min_value=Decimal("0"), max_value=Decimal("10000000")),
    positions=st.lists(
        st.tuples(
            st.decimals(min_value=Decimal("0"), max_value=Decimal("1000")),  # amount
            st.decimals(min_value=Decimal("1"), max_value=Decimal("1000"))   # price
        ),
        max_size=10
    )
)
def test_portfolio_value_equals_cash_plus_positions(cash, positions):
    ledger = DecimalLedger(starting_cash=cash)

    positions_value = Decimal(0)
    for amount, price in positions:
        positions_value += amount * price

    expected_value = cash + positions_value
    assert ledger.portfolio_value == expected_value
```

**Commission Never Exceeds Order Value:**
```python
@given(
    order_value=st.decimals(min_value=Decimal("1"), max_value=Decimal("100000")),
    commission_rate=st.decimals(min_value=Decimal("0"), max_value=Decimal("0.1"))
)
def test_commission_bounded(order_value, commission_rate):
    commission = calculate_commission(order_value, commission_rate)
    assert Decimal(0) <= commission <= order_value
```

**Decimal Precision Preservation:**
```python
@given(
    values=st.lists(
        st.decimals(min_value=Decimal("-1000"), max_value=Decimal("1000")),
        min_size=2, max_size=100
    )
)
def test_decimal_sum_associativity(values):
    """Sum order should not affect result due to Decimal precision."""
    sum_forward = sum(values, Decimal(0))
    sum_reverse = sum(reversed(values), Decimal(0))
    assert sum_forward == sum_reverse
```

**1000+ Examples:** Each property test runs with ≥1000 random examples to ensure robustness.

### Regression Testing

**Performance Benchmarks:**
- Track execution time for standard backtest scenarios
- Fail CI if performance degrades >10%
- Benchmark suite run on every release

**Benchmark Scenarios:**
```python
import pytest

@pytest.mark.benchmark(group="backtest")
def test_daily_backtest_performance(benchmark):
    """Benchmark 2-year daily backtest with 50 assets."""
    def run_backtest():
        result = run_algorithm(
            start='2021-01-01',
            end='2022-12-31',
            data_frequency='daily',
            bundle='quandl',
            capital_base=100000
        )
        return result

    result = benchmark(run_backtest)
    assert result.portfolio_value[-1] > 0  # Sanity check
```

**Stored Results:**
- Store benchmark results in CI artifacts
- Track performance trends over time
- Alert on significant regressions

### Temporal Isolation Tests

**Lookahead Bias Detection:**
- Verify no strategy has access to future data
- Timestamp validation at data access layer
- Tests for common mistakes (e.g., `.shift(-1)` on price data)

**Example Test:**
```python
def test_no_future_data_access():
    """Verify data.current() never returns future data."""

    class FutureDataAttempt(TradingAlgorithm):
        def handle_data(self, context, data):
            current_time = self.get_datetime()
            current_price = data.current(context.asset, 'close')

            # Attempt to access future data (should fail)
            with pytest.raises(DataNotAvailableError):
                future_price = data.current(
                    context.asset, 'close',
                    dt=current_time + pd.Timedelta(days=1)
                )

    run_algorithm(
        algorithm=FutureDataAttempt(),
        start='2023-01-01',
        end='2023-12-31'
    )
```

### Continuous Integration

**CI Pipeline (GitHub Actions):**

```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python-version: ['3.12', '3.13']

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"

      - name: Run tests
        run: |
          pytest -v --cov=rustybt --cov-report=xml --cov-report=term

      - name: Type check
        run: |
          mypy --strict rustybt

      - name: Lint
        run: |
          ruff check rustybt

      - name: Format check
        run: |
          black --check rustybt

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
```

**Coverage Enforcement:**
- Fail PR if coverage drops below 90%
- Require 95%+ coverage for financial modules
- Coverage reports uploaded to Codecov

**Pre-commit Hooks:**
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.1.0
    hooks:
      - id: black
        language_version: python3.12

  - repo: https://github.com/charliermarsh/ruff-pre-commit
    rev: v0.11.12
    hooks:
      - id: ruff

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
```

### Test Data Management

**Fixtures:**
- Stored in `tests/resources/`
- Small datasets only (<10MB)
- Use synthetic data where possible

**Live Data Integration Tests:**
- Require explicit opt-in: `pytest --run-live`
- Use testnet/paper accounts only
- Rate-limited to avoid API abuse

**Mocking:**
- Mock broker APIs using `pytest-mock` or `responses`
- Mock expensive operations (data downloads)
- Example:
  ```python
  def test_broker_order_submission(mocker):
      mock_broker = mocker.Mock(spec=BrokerAdapter)
      mock_broker.submit_order.return_value = "order-123"

      engine = LiveTradingEngine(broker=mock_broker)
      order_id = engine.submit_order(...)

      assert order_id == "order-123"
      mock_broker.submit_order.assert_called_once()
  ```

---

## Security Integration

### Credential Management

**Encryption at Rest:**
- All broker API keys encrypted using `cryptography.fernet`
- Encryption key stored in environment variable: `RUSTYBT_ENCRYPTION_KEY`
- Key generation: `python -m rustybt keygen`

**Implementation:**
```python
from cryptography.fernet import Fernet
import os

def encrypt_credential(plaintext: str) -> bytes:
    """Encrypt API key/secret."""
    key = os.environ.get("RUSTYBT_ENCRYPTION_KEY")
    if not key:
        raise ValueError("RUSTYBT_ENCRYPTION_KEY not set")

    f = Fernet(key.encode())
    return f.encrypt(plaintext.encode())

def decrypt_credential(ciphertext: bytes) -> str:
    """Decrypt API key/secret."""
    key = os.environ.get("RUSTYBT_ENCRYPTION_KEY")
    if not key:
        raise ValueError("RUSTYBT_ENCRYPTION_KEY not set")

    f = Fernet(key.encode())
    return f.decrypt(ciphertext).decode()
```

**Storage:**
- Encrypted credentials in `broker_connections.api_key_encrypted` column
- Never log or expose credentials in plaintext
- Rotate encryption key periodically (recommend: quarterly)

**Key Management Best Practices:**
- Production: Store encryption key in hardware security module (HSM) or cloud KMS
- Development: Store in `.env` file (never commit to git)
- Disaster Recovery: Backup encryption key securely offsite

### API Rate Limiting

**Purpose:** Prevent abuse of RESTful API (Epic 9) and protect against brute-force attacks

**Implementation:**
- Use `slowapi` for FastAPI rate limiting
- Limits:
  - Anonymous: 100 requests/hour
  - Authenticated: 10,000 requests/hour
  - WebSocket: 10 connections per user

**Example:**
```python
from fastapi import FastAPI
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/api/portfolio")
@limiter.limit("100/hour")
async def get_portfolio(request: Request):
    return {"portfolio_value": "1000000.00"}
```

**Broker API Rate Limiting:**
- Respect broker-specific rate limits (see External API Integration section)
- Implement token bucket algorithm for smooth rate limiting
- Retry with exponential backoff on rate limit errors

### Audit Logging

**Comprehensive Trade-by-Trade Logging:**
- All orders logged to `order_audit_log` table (JSON format)
- Searchable via SQL queries
- Immutable (append-only, no updates/deletes)

**Log Retention:**
- Regulatory requirement: 7 years (configurable)
- Automatic archival to cold storage after 1 year
- Compressed archives with integrity checksums

**Audit Log Query Example:**
```sql
-- Find all trades for AAPL in January 2023
SELECT
    event_timestamp,
    event_type,
    json_extract(event_data, '$.fill_price') as fill_price,
    json_extract(event_data, '$.filled_amount') as filled_amount
FROM order_audit_log
WHERE
    asset_sid = (SELECT sid FROM equities WHERE symbol = 'AAPL')
    AND event_timestamp BETWEEN 1672531200 AND 1675209600
    AND event_type = 'filled'
ORDER BY event_timestamp;
```

**Regulatory Compliance:**
- MiFID II (Europe): Trade reporting, record keeping
- SEC Rule 17a-4 (US): Broker-dealer record retention
- GDPR (Europe): Data protection, user privacy (if applicable)

### Input Validation and Sanitization

**Data Validation:**
- Use Pydantic models for all external inputs (API requests, config files)
- Validate OHLCV data: relationships, outliers, temporal consistency
- Reject malformed inputs with clear error messages

**Example:**
```python
from pydantic import BaseModel, Field, validator
from decimal import Decimal

class OrderRequest(BaseModel):
    asset_symbol: str = Field(..., min_length=1, max_length=20)
    amount: Decimal = Field(..., gt=0)
    order_type: str = Field(..., regex="^(market|limit|stop)$")
    limit_price: Optional[Decimal] = Field(None, gt=0)

    @validator('limit_price')
    def limit_price_required_for_limit_orders(cls, v, values):
        if values.get('order_type') == 'limit' and v is None:
            raise ValueError('limit_price required for limit orders')
        return v
```

**SQL Injection Prevention:**
- Use parameterized queries via SQLAlchemy ORM
- Never construct SQL strings with user input
- Example:
  ```python
  # CORRECT: Parameterized query
  result = session.query(Order).filter(Order.asset_sid == asset_sid).all()

  # INCORRECT: String concatenation (NEVER DO THIS)
  # result = session.execute(f"SELECT * FROM orders WHERE asset_sid = {asset_sid}")
  ```

### Network Security

**TLS Everywhere:**
- All broker API calls use HTTPS/WSS
- WebSocket API (Epic 9) uses WSS (TLS-encrypted WebSockets)
- Certificate validation enabled (no `verify=False`)

**Firewall Rules:**
- Allow outbound HTTPS (443) to broker APIs
- Allow inbound only on API port (default: 8000) if exposing API
- Block all other inbound traffic

**VPN for Remote Access:**
- Require VPN for remote server administration
- Use key-based SSH authentication (disable password auth)
- Restrict SSH to specific IP ranges

### Secrets Management

**Environment Variables:**
- Store sensitive config in environment variables, not code
- Use `.env` files locally (never commit)
- Use secrets management in production (AWS Secrets Manager, HashiCorp Vault)

**Configuration:**
```python
import os
from dotenv import load_dotenv

load_dotenv()

ENCRYPTION_KEY = os.environ["RUSTYBT_ENCRYPTION_KEY"]
DATABASE_URL = os.environ.get("RUSTYBT_DATABASE_URL", "sqlite:///~/.rustybt/assets.db")
LOG_LEVEL = os.environ.get("RUSTYBT_LOG_LEVEL", "INFO")
```

**Secrets Scanning:**
- Use `truffleHog` or `git-secrets` to scan for leaked credentials
- Pre-commit hooks to prevent accidental commits
- Regular scans of repository history

### Security Updates

**Dependency Scanning:**
- Use `safety` to check for known vulnerabilities
- Run on every CI build: `safety check`
- Update vulnerable dependencies promptly

**Patch Management:**
- Subscribe to security advisories for dependencies
- Monthly security update cycle
- Critical vulnerabilities patched within 48 hours

---

## Checklist Results Report

### Executive Summary

**Architecture Readiness:** ✅ **HIGH** - Architecture is comprehensive and ready for development

**Project Type:** Backend Library with Optional API Layer (Frontend sections skipped)

**Critical Strengths:**
1. Comprehensive brownfield analysis of Zipline-Reloaded foundation
2. Clear integration strategy with phased implementation (MVP Epics 1-5, then 6-9)
3. Well-defined tech stack with specific versions and rationale
4. Detailed component architecture with Decimal finance modules and Polars data layer
5. Production-ready security measures for live trading

**Critical Risks Identified:**
1. Decimal arithmetic performance overhead (mitigated by Rust optimization plan)
2. Data migration complexity (bcolz → Parquet requires conversion tooling)
3. Breaking API changes require comprehensive migration guide

### Section Analysis

| Section | Pass Rate | Status | Notes |
|---------|-----------|--------|-------|
| **Requirements Alignment** | 100% | ✅ PASS | All functional requirements (FR1-FR18) and non-functional requirements (NFR1-NFR12) addressed |
| **Architecture Fundamentals** | 100% | ✅ PASS | Clear component boundaries, event-driven pattern preserved, Mermaid diagrams included |
| **Technical Stack & Decisions** | 100% | ✅ PASS | Specific versions defined, alternatives considered, justification provided |
| **Frontend Design** | N/A | ⊘ SKIPPED | Backend library project, no UI components |
| **Resilience & Operational** | 100% | ✅ PASS | Comprehensive error handling, live trading state recovery, deployment strategies |
| **Security & Compliance** | 100% | ✅ PASS | Credential encryption, audit logging (7-year retention), rate limiting |
| **Implementation Guidance** | 100% | ✅ PASS | Python 3.12+ standards, mypy --strict, testing strategy with 88.26%+ coverage |
| **Dependency Management** | 100% | ✅ PASS | External APIs documented (5+ brokers), versioning strategy defined |
| **AI Agent Suitability** | 100% | ✅ PASS | Clear module boundaries, consistent patterns, implementation examples provided |
| **Accessibility** | N/A | ⊘ SKIPPED | Backend library project |

**Overall Pass Rate:** 9/9 applicable sections (100%)

### Top 5 Risks and Mitigations

**1. Decimal Arithmetic Performance (MEDIUM RISK)**
- **Risk:** <30% overhead target (NFR3) may be challenging with pure Python Decimal
- **Mitigation:** Epic 7 Rust optimization with profiling-driven approach, Polars performance gains offset overhead
- **Timeline Impact:** No impact on MVP (Epics 1-5), addressed post-MVP

**2. Data Migration Complexity (MEDIUM RISK)**
- **Risk:** Users have large bcolz bundles that need conversion to Parquet
- **Mitigation:** `rustybt bundle migrate` CLI tool with dual-format read support during transition
- **Timeline Impact:** Requires Epic 3 completion before users can migrate

**3. Breaking API Compatibility (LOW RISK)**
- **Risk:** Zipline users must rewrite strategies for Decimal types
- **Mitigation:** Comprehensive migration guide, example conversions, gradual adoption via feature flags
- **Timeline Impact:** Documentation effort in Epic 1

**4. Live Trading State Recovery (MEDIUM RISK)**
- **Risk:** Crash during order execution could result in position mismatch
- **Mitigation:** Order audit log with transaction-level granularity, broker reconciliation on startup
- **Timeline Impact:** Epic 6 implementation complexity

**5. Broker API Rate Limits (LOW RISK)**
- **Risk:** Exceeding broker rate limits during live trading
- **Mitigation:** APScheduler with configurable intervals, exponential backoff, circuit breakers
- **Timeline Impact:** Epic 6 testing requirements

### Recommendations

**Must-Fix Before Development:**
- ✅ All items addressed in current architecture

**Should-Fix for Better Quality:**
1. **Add sequence diagrams** for live trading order flow (Epic 6) - Currently only component diagrams
2. **Specify Parquet schema versions** - Currently implicit, should be versioned like asset DB
3. **Define Rust module API** - Epic 7 Rust optimization needs clearer Python/Rust boundary

**Nice-to-Have Improvements:**
1. Performance benchmarking targets with specific metrics (e.g., "2-year backtest on 50 assets in <10 minutes")
2. Disaster recovery runbook for live trading server failures
3. Multi-strategy portfolio allocation algorithm comparison matrix

### AI Implementation Readiness

**✅ EXCELLENT** - Architecture is highly suitable for AI agent implementation

**Strengths:**
1. Clear module boundaries with single responsibilities
2. Consistent patterns (BarReader interface, BrokerAdapter abstraction)
3. Comprehensive code examples (DecimalLedger, PolarsBarReader, CCXTAdapter)
4. Explicit integration points with Zipline modules (KEEP, EXTEND, NEW markers)
5. Detailed source tree structure with file placement guidance

**Areas Needing Additional Clarification:**
1. **Decimal precision rules:** Document when to use `ROUND_HALF_EVEN` vs `ROUND_DOWN` (add to coding standards)
2. **Polars lazy evaluation:** Specify when to call `.collect()` to materialize results
3. **Async/await boundaries:** Clarify which components use async (broker adapters, data feeds) vs sync (algorithm callbacks)

**Complexity Hotspots:**
1. **PolarsDataPortal** - Complex adjustment application logic (Zipline's AdjustedArray pattern)
2. **LiveTradingEngine** - State machine for order lifecycle management
3. **Pipeline engine integration** - Polars compatibility with existing pipeline computations

**Recommendations:**
- Break PolarsDataPortal into smaller sub-components (AdjustmentEngine, HistoryManager, BarDispatcher)
- Provide state diagram for LiveTradingEngine order lifecycle
- Create Epic 4 spike story for Pipeline + Polars integration feasibility

### Validation Checklist Details

**Section 1: Requirements Alignment ✅**
- All FR1-FR18 functional requirements mapped to components
- NFR1-NFR12 non-functional requirements addressed with concrete solutions
- Technical constraints (Python 3.12+, self-hosted deployment, no vendor lock-in) satisfied

**Section 2: Architecture Fundamentals ✅**
- Event-driven architecture preserved from Zipline (AlgorithmSimulator → TradingAlgorithm)
- Component diagrams for Decimal finance, Polars data, live trading modules
- Clear separation: data layer (Polars) → finance layer (Decimal) → execution layer (Blotter/Broker)

**Section 3: Technical Stack & Decisions ✅**
- Specific versions: Python 3.12+, Polars 1.x, PyO3 0.26+, rust-decimal 1.37+
- Alternatives documented: Parquet vs bcolz/HDF5, Polars vs pandas, FastAPI vs Flask
- Justification provided for each technology choice

**Section 5: Resilience & Operational Readiness ✅**
- Error handling: Retry policies, circuit breakers, exponential backoff
- Monitoring: Structured logging (JSON), audit trail (7-year retention), performance metrics
- Deployment: 5 deployment modes from local dev to Kubernetes

**Section 6: Security & Compliance ✅**
- Credential encryption: cryptography.fernet with key management
- Rate limiting: FastAPI slowapi + broker-specific limits
- Audit logging: Trade-by-trade JSON logs with 7-year retention

**Section 7: Implementation Guidance ✅**
- Coding standards: Python 3.12+, mypy --strict, black/ruff formatting
- Testing: 90% overall coverage, 95% financial modules, Hypothesis property testing
- Documentation: 100% public API, 30+ tutorial notebooks

**Section 8: Dependency & Integration Management ✅**
- External dependencies: 5+ broker APIs (CCXT, IB, Binance, Bybit, Hyperliquid)
- Versioning: setuptools_scm for git-based versioning
- Integration: BrokerAdapter abstraction with async/await pattern

**Section 9: AI Agent Implementation Suitability ✅**
- Modular design: Clear interfaces (BarReader, Blotter, BrokerAdapter)
- Predictable patterns: Consistent naming (Decimal prefix, Polars prefix)
- Implementation examples: Complete code for DecimalLedger, PolarsBarReader, CCXTAdapter

---

## Next Steps

### Handoff to Development Teams

**Epic 1-5 (MVP):**
1. Development team reviews architecture document
2. Architect conducts architecture walkthrough session
3. Team breaks down epics into implementation tasks
4. Assign tasks to developers based on expertise
5. Begin implementation with Epic 1 (Foundation)

**Epic 6-9 (Post-MVP):**
1. Validate MVP with real-world backtests
2. Collect user feedback on API design
3. Re-assess priorities based on user needs
4. Plan Epic 6 (Live Trading) when MVP complete

### Architecture Validation

**Review Checklist:**
- [ ] All stakeholders reviewed architecture document
- [ ] Technical feasibility confirmed for each component
- [ ] Integration points clearly defined
- [ ] Performance targets achievable
- [ ] Security requirements met
- [ ] Testing strategy comprehensive
- [ ] Deployment strategy practical

**Approval:**
- PM: ___________  Date: _________
- Architect: ___________  Date: _________
- Lead Developer: ___________  Date: _________

### Continuous Architecture Updates

**Update Triggers:**
- Major component design changes
- New epics added/removed
- Integration point modifications
- Performance target revisions

**Versioning:**
- Increment version number on significant changes
- Maintain changelog section
- Archive old versions for reference

---

**End of Document**
