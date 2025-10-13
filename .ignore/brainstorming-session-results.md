# Brainstorming Session Results

**Session Date:** 2025-09-30
**Facilitator:** Business Analyst Mary
**Participant:** Project Lead

---

## Executive Summary

**Topic:** Enhanced Python/Rust Trading Backtesting & Live Trading Platform

**Session Goals:** Organize ideas for forking and enhancing an existing backtesting platform (Zipline or Backtrader) into a production-grade trading platform with Python/Rust integration, comprehensive data handling, and live trading capabilities.

**Techniques Used:** Yolo Mode - Comprehensive Analysis & Structured Planning

**Total Ideas Generated:** 10 major implementation phases with 50+ specific features and enhancements

### Key Themes Identified:
- **Financial Integrity First**: Decimal arithmetic implementation is critical and missing from both base platforms
- **Active Maintenance Matters**: Zipline-Reloaded's active development trumps Backtrader's feature completeness
- **Phased Approach**: 33-month roadmap with clear priorities (MUST/SHOULD/NICE TO HAVE)
- **Rust for Performance**: Strategic Rust integration for bottlenecks, not wholesale rewrite
- **Production-Grade Focus**: Testing, security, audit logging, and reliability as core requirements

---

## Framework Selection Analysis

### Recommended Framework: Zipline-Reloaded

**Decision Rationale:**
After comprehensive comparative analysis, Zipline-Reloaded is recommended over Backtrader despite Backtrader's superior live trading support.

**Zipline-Reloaded Advantages:**
1. **Active Maintenance** - v3.1.1 (July 2025), quarterly releases
2. **Modern Python Support** - Python 3.9-3.12 (vs Backtrader's 3.7 max officially)
3. **Superior Test Coverage** - 88.26% (vs Backtrader's unknown coverage)
4. **Cleaner Architecture** - Better foundation for major modifications
5. **Active Community** - 1,311 stars, responsive maintainer (Stefan Jansen)

**Trade-offs Accepted:**
1. Limited live trading support (must build from scratch)
2. Weaker multi-timeframe support (improvable)
3. No Decimal arithmetic (neither framework has this - must implement)
4. No REST API (neither framework has this - must build)

**Comparative Scores:**
- Zipline-Reloaded: 152/200 points
- Backtrader: 138/200 points

**Critical Finding:** Neither framework uses Decimal arithmetic - both use Python `float`. This is the highest priority enhancement needed.

---

## Detailed Comparison: Zipline-Reloaded vs Backtrader

### Architecture & Design Philosophy

| Aspect | Zipline-Reloaded | Backtrader | Winner |
|--------|------------------|------------|--------|
| OOP Approach | Event-driven, clean separation with Pipeline API | Event-driven, modular with Cerebro engine | Zipline |
| Extensibility | Data bundle system, custom models | Highly pluggable, everything extensible | Backtrader |
| Modularity | Well-defined modules (finance, data, assets, pipeline) | Component-based (Strategy, Indicators, Analyzers, Broker) | Tie |
| Code Clarity | PEP-8 compliant, flake8 checked | OOP but complex, some legacy patterns | Zipline |

**Analysis:** Zipline provides better foundation for professional platform with clearer architectural patterns, while Backtrader offers more flexibility at cost of complexity.

---

### Data Handling Capabilities

| Aspect | Zipline-Reloaded | Backtrader | Winner |
|--------|------------------|------------|--------|
| Data Source Flexibility | Bundle ingest system, custom bundles | Multiple feed types (CSV, Pandas, live) | Tie |
| Storage Approach | HDF5-based bundles, optimized for speed | In-memory with optional persistence | Zipline |
| Multi-Resolution Support | Minute and daily bars via history API | Native multi-timeframe with resampling | Backtrader |
| Timezone Handling | TradingCalendar system, multi-country | Built-in timezone management (v1.5.0+) | Zipline |
| Large Dataset Performance | Can handle but slow (hours for thousands of assets) | ~12,473 candles/sec, 2M candles manageable | Backtrader |

**Analysis:** Split decision - Zipline excels at large datasets and international markets; Backtrader superior for multi-timeframe strategies.

---

### Financial Integrity - CRITICAL FINDING

| Aspect | Zipline-Reloaded | Backtrader | Status |
|--------|------------------|------------|--------|
| **Decimal Arithmetic** | ❌ Uses `float` (Issue #56 rejected) | ❌ Uses `float` (PR #416 not merged) | **NEITHER COMPLIANT** |
| Lookahead Bias Prevention | ✅ Excellent - core design feature | ✅ Good - negative array indexing | Zipline |
| Data Validation | ✅ Pipeline validation, adjustments handling | ⚠️ Basic validation, user-dependent | Zipline |
| OHLC Relationship Validation | ⚠️ Limited | ⚠️ Limited | Tie (both need work) |

**CRITICAL IMPLICATION:** You will need to implement Decimal arithmetic yourself in either framework. This is a 3-6 month major refactoring effort. Zipline's cleaner architecture and 88.26% test coverage make this refactoring more manageable.

---

### Live Trading Support

| Aspect | Zipline-Reloaded | Backtrader | Winner |
|--------|------------------|------------|--------|
| Real-time Data | Via zipline-trader fork, QuantRocket | Native support with IB, OANDA | Backtrader |
| Execution Capabilities | Requires external integration | Built-in broker connections | Backtrader |
| State Management | Limited | Seamless backtest-to-live transition | Backtrader |
| Production Readiness | External forks needed | Production-ready since v1.5.0 | Backtrader |

**Analysis:** Backtrader decisively superior for live trading - it's a core feature, not afterthought. However, Backtrader's inactive maintenance (since April 2023) undermines this advantage for long-term projects.

---

### Maintenance Status - CRITICAL DIFFERENCE

| Aspect | Zipline-Reloaded | Backtrader | Status |
|--------|------------------|------------|--------|
| **Active Development** | ✅ **ACTIVE** - Stefan Jansen maintains | ❌ **INACTIVE** since April 2023 | **CRITICAL** |
| Latest Version | v3.1.1 (July 2025), quarterly releases | v1.9.76.123 (April 2023) | Zipline |
| Python Version Support | **Python 3.9-3.12** | Python 3.7 (3.10 works with issues) | Zipline |
| Community | 1,311 stars, 239 forks, 120 contributors, active | 16,577 stars, 4,600 forks, inactive repo | Zipline |
| Dependencies | Pandas 2.0+, NumPy 2.0, SQLAlchemy 2.0 | Outdated dependencies | Zipline |

**Analysis:** This alone justifies choosing Zipline. Active maintenance is crucial for a fork project. Backtrader's popularity doesn't compensate for development abandonment.

---

### Code Quality & Testing

| Aspect | Zipline-Reloaded | Backtrader | Winner |
|--------|------------------|------------|--------|
| Test Coverage | **88.26%** (Coveralls verified) | Unknown (no public metrics) | Zipline |
| Documentation | Comprehensive Sphinx docs, tutorials | Extensive docs, praised by community | Tie |
| Contribution Guidelines | Well-documented, clear conventions | Community-driven, maintainer inactive | Zipline |
| Code Standards | PEP-8, flake8, commit conventions | Good but inconsistent | Zipline |

**Analysis:** Zipline's superior test coverage is critical for safely implementing major modifications like Decimal arithmetic.

---

## Implementation Roadmap: 10-Phase Plan

### Phase 1: Foundation & Setup (Months 1-3)

**Objective:** Establish solid foundation for development

**Tasks:**
1. Fork zipline-reloaded repository
2. Set up development environment (Python 3.11+)
3. Configure CI/CD pipelines (GitHub Actions)
4. Run full test suite (verify 88.26% baseline)
5. Map existing architecture and dependencies
6. Document all modules and extension points
7. Establish coding standards (extend Zipline's)
8. Set up issue tracking and project management
9. Create contribution guidelines
10. Establish version control strategy

**Deliverables:**
- Forked repository with CI/CD
- Complete architecture documentation
- Development environment setup guide
- Project roadmap and milestones

**Resource Requirements:**
- Core Developer (full-time)
- DevOps Engineer (part-time)

---

### Phase 2: Financial Integrity - Decimal Arithmetic (Months 4-9)

**Objective:** Implement Decimal arithmetic throughout platform - HIGHEST PRIORITY

**Critical Context:** Neither Zipline nor Backtrader uses Decimal arithmetic. This is the most important enhancement and biggest technical challenge.

#### Implementation Areas:

**1. Core Calculation Engine**
- Replace `float` with `Decimal` in:
  - Price calculations
  - Position sizing
  - Portfolio value computations
  - Order execution
- Configuration system for precision:
  - 8 decimal places for crypto
  - 2 decimal places for equities
  - 4 decimal places for forex
- Decimal context management (rounding modes, precision)

**2. Order Execution System**
- Decimal-based order matching engine
- Commission calculations (Decimal throughout)
- Slippage models (Decimal precision)
- Partial fill handling (Decimal quantities)
- Order book price levels (Decimal keys)

**3. Performance Metrics**
- Returns calculations (Decimal for intermediate steps)
- Sharpe/Sortino ratios (Decimal precision)
- Drawdown computations (Decimal accuracy)
- PnL tracking (Decimal for audit trail)
- Risk metrics (VaR, CVaR with Decimal)

**4. Data Pipeline Integration**
- Price data storage (Decimal compatible)
- Corporate actions (splits, dividends with Decimal)
- Currency conversions (Decimal precision)
- Historical adjustments (Decimal accuracy)

**5. Testing & Validation**
- Unit tests for Decimal precision edge cases:
  - Rounding behavior
  - Precision loss prevention
  - Large number handling
  - Division by zero
- Property-based testing (Hypothesis library):
  - Commutative property verification
  - Associative property verification
  - Distributive property verification
- Financial accuracy regression tests
- Performance benchmarking (Decimal vs float)

**Risks & Mitigations:**

**Risk:** Performance degradation (Decimal is ~100x slower than float)
**Mitigation:**
- Profile carefully before implementation
- Identify critical paths for optimization
- Plan Rust Decimal implementation for bottlenecks
- Consider hybrid approach (Decimal for financial, float for indicators)

**Risk:** Library compatibility (many libraries expect float)
**Mitigation:**
- Create conversion layer for external libraries
- Document conversion points
- Validate precision at boundaries

**Deliverables:**
- Decimal-based core calculation engine
- Comprehensive test suite (90%+ coverage for financial modules)
- Performance benchmarks and optimization guide
- Migration guide for users
- Documentation on precision handling

**Resource Requirements:**
- Core Developer (full-time)
- Financial domain expert (consultant)
- QA Engineer (part-time)

**Success Criteria:**
- Zero rounding errors in financial calculations
- All financial tests pass with Decimal
- Performance degradation <50% (target: <30% with optimization)
- 90%+ test coverage for Decimal modules

---

### Phase 3: Data Handling Enhancements (Months 6-12, Parallel with Phase 2)

**Objective:** Replace HDF5 with Polars/Parquet unified data catalog supporting multiple sources

#### 1. Unified Data Catalog with Polars/PyArrow

**Current State:** Zipline uses HDF5 bundle system
**Enhancement:** Modern Polars/Parquet-based storage layer

**Architecture:**
```python
# New module: zipline/data/polars_catalog.py

class PolarsCatalog:
    """Unified data catalog using Polars and Parquet"""

    def __init__(self, catalog_path: Path):
        self.catalog_path = catalog_path
        self.metadata_db = SQLiteMetadata(catalog_path / "catalog.db")
        self.cache = PolarsCache(max_memory="2GB")

    def register_source(self, source: DataSourceAdapter):
        """Register new data source"""

    def query(self, symbols, start_date, end_date, resolution):
        """Query data with lazy evaluation"""
        return self._build_lazy_query(symbols, start_date, end_date, resolution)

    def materialize(self, lazy_query):
        """Execute lazy query and return Polars DataFrame"""

    def cache_data(self, symbols, data):
        """Cache data to Parquet files"""
```

**Features:**
- **Storage:** Parquet files (better compression than HDF5, columnar format)
- **Query Engine:** Polars lazy frames (faster than Pandas)
- **Caching:** Two-tier (in-memory Polars + disk Parquet)
- **Metadata:** SQLite catalog for symbols, date ranges, sources
- **Schema Validation:** Automatic OHLCV schema enforcement
- **Versioning:** Data version control for reproducibility

**Benefits over HDF5:**
- Better compression (50-80% smaller than HDF5)
- Faster queries with predicate pushdown
- Interoperability (read from Python, Rust, R, etc.)
- Better ecosystem support
- Cloud-native (S3/GCS compatible)

#### 2. Subclassable Data Source Adapters

**Base Class:**
```python
# zipline/data/adapters/base.py

from abc import ABC, abstractmethod
from decimal import Decimal
import polars as pl

class DataSourceAdapter(ABC):
    """Base class for all data source adapters"""

    @abstractmethod
    def fetch(self, symbols: list[str], start: datetime,
              end: datetime, resolution: str) -> pl.DataFrame:
        """Fetch data from source"""

    @abstractmethod
    def validate(self, df: pl.DataFrame) -> pl.DataFrame:
        """Validate OHLC relationships and data quality"""

    @abstractmethod
    def standardize(self, df: pl.DataFrame) -> pl.DataFrame:
        """Convert to unified schema with Decimal types"""

    def fetch_and_prepare(self, symbols, start, end, resolution):
        """Complete pipeline: fetch -> validate -> standardize"""
        raw_data = self.fetch(symbols, start, end, resolution)
        validated = self.validate(raw_data)
        return self.standardize(validated)
```

**Adapters to Implement:**

**1. YFinanceAdapter** - Free stock/ETF data
```python
class YFinanceAdapter(DataSourceAdapter):
    """Yahoo Finance data source"""
    - Supports stocks, ETFs, indices, forex
    - Free tier limitations handling
    - Automatic retry with exponential backoff
    - Split/dividend adjustment
```

**2. CCXTAdapter** - Unified crypto exchange API
```python
class CCXTAdapter(DataSourceAdapter):
    """CCXT cryptocurrency data"""
    - 100+ exchange support
    - Multiple resolution support (1m to 1d)
    - Rate limiting per exchange
    - WebSocket support for real-time
```

**3. PolygonAdapter** - Professional market data
```python
class PolygonAdapter(DataSourceAdapter):
    """Polygon.io professional data"""
    - Stocks, options, forex, crypto
    - Tick-level data support
    - Corporate actions
    - Real-time and historical
```

**4. AlpacaAdapter** - Commission-free broker data
```python
class AlpacaAdapter(DataSourceAdapter):
    """Alpaca Markets data"""
    - Stock market data
    - Real-time quotes
    - Trade execution integration
    - Paper trading support
```

**5. CSVAdapter** - Custom data import
```python
class CSVAdapter(DataSourceAdapter):
    """Custom CSV data import"""
    - Flexible schema mapping
    - Automatic type detection
    - Missing data handling
    - Multiple file support
```

**6. WebSocketAdapter** - Real-time streaming
```python
class WebSocketAdapter(DataSourceAdapter):
    """Real-time WebSocket data"""
    - Async data streaming
    - Reconnection logic
    - Buffer management
    - Multiple stream aggregation
```

**7. CloudStorageAdapter** - S3/GCS integration
```python
class CloudStorageAdapter(DataSourceAdapter):
    """Cloud storage data source"""
    - S3/GCS/Azure support
    - Partitioned Parquet reading
    - Lazy loading
    - Credential management
```

#### 3. Multi-Resolution & Aggregation System

**Enhancement:** Improve Zipline's limited multi-timeframe support

**Resolution Support:**
- Sub-second: 100ms, 250ms, 500ms
- Seconds: 1s, 5s, 10s, 30s
- Minutes: 1m, 5m, 15m, 30m
- Hours: 1h, 2h, 4h, 6h, 12h
- Days: 1d
- Weeks: 1w
- Months: 1M

**Features:**
```python
class MultiResolutionManager:
    """Handle multiple timeframes with integrity"""

    def resample(self, data, from_resolution, to_resolution):
        """Resample data maintaining OHLCV relationships"""
        # Proper OHLCV aggregation:
        # O = first, H = max, L = min, C = last, V = sum

    def align_timeframes(self, primary, secondary):
        """Align different timeframes for multi-timeframe strategies"""

    def validate_aggregation(self, original, aggregated):
        """Validate OHLCV relationships after aggregation"""
```

**Timezone Management:**
- Automatic timezone detection
- Consistent UTC storage
- Display timezone conversion
- DST handling
- Exchange-specific trading hours

**Gap Detection & Handling:**
- Detect missing bars
- Holiday detection (exchange calendars)
- After-hours gap handling
- Forward-fill options (configurable)

**Corporate Action Adjustments:**
- Stock splits (proportional adjustment)
- Dividends (cash adjustment)
- Mergers/acquisitions
- Spin-offs
- Rights offerings

**Deliverables:**
- Polars/Parquet data catalog module
- 7 data source adapters (extensible architecture)
- Multi-resolution aggregation system
- Timezone management utilities
- Gap detection and handling
- Corporate action adjustments
- Comprehensive tests (unit + integration)
- Documentation and usage examples

**Resource Requirements:**
- Core Developer (full-time)
- Data Engineer (part-time)

---

### Phase 4: Python API Enhancements (Months 10-15)

**Objective:** Enhance Zipline's API with multi-strategy, advanced orders, realistic costs, and live trading foundation

#### 1. Multi-Strategy Portfolio System

**Current Limitation:** Zipline supports single strategy per run
**Enhancement:** Run multiple strategies with sophisticated allocation

**Architecture:**
```python
class PortfolioAllocator:
    """Manage multiple strategies with capital allocation"""

    def __init__(self, total_capital: Decimal):
        self.strategies: dict[str, Strategy] = {}
        self.allocations: dict[str, AllocationRule] = {}
        self.risk_manager = CrossStrategyRiskManager()

    def register_strategy(self, name: str, strategy: Strategy,
                         allocation: AllocationRule):
        """Register strategy with allocation rule"""

    def rebalance(self):
        """Rebalance capital across strategies"""

    def aggregate_orders(self):
        """Aggregate orders from all strategies (net positions)"""

    def generate_report(self):
        """Consolidated multi-strategy performance report"""
```

**Allocation Strategies:**
- **Fixed:** Each strategy gets fixed percentage
- **Dynamic:** Allocation based on recent performance
- **Risk-Parity:** Equal risk contribution from each strategy
- **Kelly Criterion:** Optimal allocation based on edge
- **Max Drawdown Based:** Reduce allocation after drawdowns

**Cross-Strategy Risk Management:**
- Portfolio-level position limits
- Correlation-aware position sizing
- Aggregate exposure monitoring
- Margin utilization tracking

#### 2. Advanced Order Types

**Current State:** Zipline supports Market and Limit orders
**Enhancement:** Professional order types

**Order Types to Implement:**

**1. Stop-Loss Order**
```python
class StopLossOrder(Order):
    def __init__(self, asset, quantity, stop_price: Decimal):
        self.stop_price = stop_price
        # Triggers market order when price <= stop_price
```

**2. Stop-Limit Order**
```python
class StopLimitOrder(Order):
    def __init__(self, asset, quantity, stop_price: Decimal,
                 limit_price: Decimal):
        self.stop_price = stop_price
        self.limit_price = limit_price
        # Triggers limit order when price hits stop
```

**3. Trailing Stop**
```python
class TrailingStopOrder(Order):
    def __init__(self, asset, quantity, trail_percent: Decimal = None,
                 trail_amount: Decimal = None):
        # Trails market price by percentage or absolute amount
        self.trail_percent = trail_percent
        self.trail_amount = trail_amount
```

**4. One-Cancels-Other (OCO)**
```python
class OCOOrder(Order):
    def __init__(self, order1: Order, order2: Order):
        # When one order fills, cancel the other
        self.orders = [order1, order2]
```

**5. Bracket Order**
```python
class BracketOrder(Order):
    def __init__(self, entry: Order, take_profit: Order,
                 stop_loss: Order):
        # Entry order + simultaneous TP and SL
        self.entry = entry
        self.take_profit = take_profit
        self.stop_loss = stop_loss
```

**6. Iceberg Order**
```python
class IcebergOrder(Order):
    def __init__(self, asset, total_quantity: Decimal,
                 visible_quantity: Decimal, limit_price: Decimal):
        # Large order split into smaller visible chunks
        self.total_quantity = total_quantity
        self.visible_quantity = visible_quantity
```

**Order State Management:**
- Pending, Submitted, Accepted, Partially Filled, Filled, Cancelled, Rejected
- Order lifecycle tracking
- Execution audit trail

#### 3. Realistic Transaction Cost Modeling

**Enhancement:** Move beyond simple percentage-based costs

**Latency Simulation:**
```python
class LatencySimulator:
    """Simulate realistic order latency"""

    def __init__(self):
        self.network_latency = NormalDistribution(mean=10ms, std=3ms)
        self.broker_latency = NormalDistribution(mean=50ms, std=20ms)
        self.exchange_latency = NormalDistribution(mean=5ms, std=2ms)

    def total_latency(self):
        """Total latency from order submission to fill"""
        return (self.network_latency.sample() +
                self.broker_latency.sample() +
                self.exchange_latency.sample())
```

**Partial Fill Simulation:**
```python
class PartialFillModel:
    """Simulate partial order fills based on volume"""

    def calculate_fill_probability(self, order_size, bar_volume,
                                   order_type):
        """Probability of full fill based on market conditions"""
        # Large orders relative to volume have lower fill probability
        # Aggressive orders (market) fill faster than passive (limit)

    def simulate_fill(self, order, current_bar):
        """Return filled quantity (may be partial)"""
```

**Slippage Models:**

**1. Volume-Share Slippage**
```python
class VolumeShareSlippage:
    """Slippage based on order size relative to volume"""
    def calculate(self, order_quantity, bar_volume, price):
        impact = (order_quantity / bar_volume) * self.impact_factor
        return price * (1 + impact) if buying else price * (1 - impact)
```

**2. Fixed Basis Points**
```python
class FixedBasisPointSlippage:
    """Simple fixed percentage slippage"""
    def calculate(self, price, basis_points=5):
        return price * (1 + basis_points / 10000)
```

**3. Bid-Ask Spread Model**
```python
class BidAskSpreadSlippage:
    """Slippage based on realistic bid-ask spread"""
    def calculate(self, price, spread_percentage):
        # Market buy: pay ask (price + spread/2)
        # Market sell: receive bid (price - spread/2)
```

**Commission Models:**
```python
class CommissionModel(ABC):
    @abstractmethod
    def calculate(self, order, fill_price, fill_quantity) -> Decimal:
        pass

class PerShareCommission(CommissionModel):
    """Interactive Brokers style: $0.005/share, $1 minimum"""

class PercentageCommission(CommissionModel):
    """Percentage of trade value"""

class TieredCommission(CommissionModel):
    """Volume-based commission tiers"""

class CryptoCommission(CommissionModel):
    """Maker/taker fee structure"""
```

**Borrowing Costs (Short Selling):**
```python
class BorrowCostModel:
    """Cost to borrow shares for short selling"""

    def calculate_daily_cost(self, asset, quantity, price):
        borrow_rate = self.get_borrow_rate(asset)  # Hard-to-borrow = higher rate
        return quantity * price * (borrow_rate / 365)
```

**Overnight Financing:**
```python
class OvernightFinancingModel:
    """Interest on leveraged positions (forex/CFD style)"""

    def calculate(self, position_value, leverage, days_held):
        financing_rate = self.get_rate(asset)
        return position_value * leverage * financing_rate * (days_held / 365)
```

#### 4. Live Trading Foundation

**Objective:** Build minimal live trading layer (full implementation in Phase 5)

**Core Components:**
```python
class LiveTradingEngine:
    """Real-time trading execution engine"""

    def __init__(self, strategy, broker, data_feed):
        self.strategy = strategy
        self.broker = broker
        self.data_feed = data_feed
        self.state_manager = StateManager()
        self.scheduler = ScheduledCalculations()

    def start(self):
        """Start live trading"""
        self.restore_state()  # Load saved state
        self.data_feed.subscribe(self.on_data)
        self.scheduler.start()

    def on_data(self, bar):
        """Handle incoming real-time data"""
        self.strategy.handle_data(bar)
        self.process_orders()
        self.save_state()

    def stop(self):
        """Gracefully stop live trading"""
        self.cancel_open_orders()
        self.save_state()
```

**State Management:**
```python
class StateManager:
    """Persist and restore strategy state"""

    def save_state(self, strategy_state, portfolio_state, order_state):
        """Save current state to disk (JSON/pickle)"""

    def restore_state(self):
        """Restore state from last session"""

    def reconcile_positions(self, broker_positions):
        """Reconcile internal state with broker positions"""
```

**Scheduled Calculations:**
```python
class ScheduledCalculations:
    """Cron-like scheduling for strategy calculations"""

    def schedule(self, func, cron_expression):
        """Schedule function (e.g., '0 9 * * 1-5' = 9am weekdays)"""

    def schedule_market_open(self, func):
        """Run at market open"""

    def schedule_market_close(self, func):
        """Run at market close"""
```

**Paper Trading Mode:**
```python
class PaperTradingBroker:
    """Simulated broker for paper trading"""

    def __init__(self, initial_capital: Decimal):
        self.portfolio = SimulatedPortfolio(initial_capital)
        self.real_data = True  # Use real market data
        self.real_latency = True  # Simulate realistic latency

    def submit_order(self, order):
        """Simulate order submission and fill"""
```

**Deliverables:**
- Multi-strategy portfolio allocator
- 6 advanced order types (Stop, Stop-Limit, Trailing, OCO, Bracket, Iceberg)
- Realistic latency simulator
- Partial fill model
- 3 slippage models
- 4 commission models
- Borrowing cost model
- Overnight financing model
- Live trading engine foundation
- State management system
- Scheduled calculations
- Paper trading broker
- Comprehensive tests
- Documentation and examples

**Resource Requirements:**
- Core Developer (full-time)
- QA Engineer (part-time)

---

### Phase 5: Rust Performance Layer (Months 16-21)

**Objective:** Identify performance bottlenecks and reimplement in Rust for 10-100x speedup

**Strategy:** Strategic Rust integration, not wholesale rewrite

#### 1. Performance Profiling

**Profiling Targets:**
```python
# Use cProfile, line_profiler, memory_profiler
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()
# Run backtest
profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(50)  # Top 50 slowest functions
```

**Areas to Profile:**
1. **Order Matching Engine** - Critical hot path
2. **Portfolio Value Calculations** - Runs every bar
3. **Indicator Computations** - Moving averages, RSI, etc.
4. **Decimal Arithmetic Operations** - Potentially 100x slower than float
5. **Data Aggregation/Resampling** - Multi-timeframe operations
6. **Risk Calculations** - VaR, CVaR, correlation matrices

**Profiling Metrics:**
- Total time spent in function
- Number of calls
- Time per call
- Memory allocation
- CPU cache misses (with perf)

#### 2. Rust Modules to Build

**Module 1: Order Matching Engine** (`rusty_matching`)

**Why Rust:**
- High-frequency operations
- Complex state management
- Zero-cost abstractions
- Memory safety critical

```rust
// crates/rusty_matching/src/lib.rs

use rust_decimal::Decimal;
use std::collections::BTreeMap;

/// High-performance limit order book
pub struct OrderBook {
    bids: BTreeMap<Decimal, Vec<Order>>,  // Price -> Orders (sorted)
    asks: BTreeMap<Decimal, Vec<Order>>,
    last_trade_price: Option<Decimal>,
}

impl OrderBook {
    pub fn new() -> Self { /* ... */ }

    pub fn add_order(&mut self, order: Order) -> OrderId {
        // Add order to appropriate side
    }

    pub fn cancel_order(&mut self, order_id: OrderId) -> Result<(), Error> {
        // Cancel order
    }

    pub fn match_order(&mut self, order: Order) -> Vec<Fill> {
        // Match order against book, return fills
    }

    pub fn get_best_bid(&self) -> Option<Decimal> {
        // Highest bid price
    }

    pub fn get_best_ask(&self) -> Option<Decimal> {
        // Lowest ask price
    }

    pub fn get_spread(&self) -> Option<Decimal> {
        // Bid-ask spread
    }
}

#[derive(Debug, Clone)]
pub struct Order {
    pub id: OrderId,
    pub side: Side,  // Buy or Sell
    pub price: Decimal,
    pub quantity: Decimal,
    pub order_type: OrderType,  // Market, Limit, Stop, etc.
    pub timestamp: i64,
}

#[derive(Debug)]
pub struct Fill {
    pub order_id: OrderId,
    pub price: Decimal,
    pub quantity: Decimal,
    pub timestamp: i64,
}

pub enum Side { Buy, Sell }
pub enum OrderType { Market, Limit, StopLoss, StopLimit }
```

**Module 2: Portfolio Engine** (`rusty_portfolio`)

**Why Rust:**
- Decimal arithmetic performance critical
- Called every bar (hot path)
- Complex calculations
- Numerical stability

```rust
// crates/rusty_portfolio/src/lib.rs

use rust_decimal::Decimal;
use std::collections::HashMap;

/// Portfolio with Decimal precision
pub struct Portfolio {
    cash: Decimal,
    positions: HashMap<AssetId, Position>,
    starting_cash: Decimal,
}

impl Portfolio {
    pub fn new(starting_cash: Decimal) -> Self { /* ... */ }

    /// Calculate total portfolio value
    pub fn calculate_value(&self, prices: &HashMap<AssetId, Decimal>) -> Decimal {
        let mut total = self.cash;
        for (asset_id, position) in &self.positions {
            if let Some(price) = prices.get(asset_id) {
                total += position.quantity * price;
            }
        }
        total
    }

    /// Calculate position PnL
    pub fn calculate_pnl(&self, asset_id: AssetId,
                         current_price: Decimal) -> Decimal {
        if let Some(position) = self.positions.get(&asset_id) {
            (current_price - position.cost_basis) * position.quantity
        } else {
            Decimal::ZERO
        }
    }

    /// Update position after trade
    pub fn update_position(&mut self, asset_id: AssetId,
                          quantity: Decimal, price: Decimal) {
        // Update position with FIFO/LIFO cost basis
    }
}

#[derive(Debug, Clone)]
pub struct Position {
    pub asset_id: AssetId,
    pub quantity: Decimal,
    pub cost_basis: Decimal,
    pub last_price: Decimal,
}

/// Performance metrics calculations
pub fn calculate_sharpe_ratio(returns: &[Decimal],
                             risk_free_rate: Decimal) -> Decimal {
    // Efficient Sharpe calculation
}

pub fn calculate_max_drawdown(portfolio_values: &[Decimal]) -> Decimal {
    // Efficient max drawdown calculation
}

pub fn calculate_sortino_ratio(returns: &[Decimal],
                               target_return: Decimal) -> Decimal {
    // Sortino ratio with downside deviation
}
```

**Module 3: Technical Indicators** (`rusty_indicators`)

**Why Rust:**
- Called frequently
- Vectorized operations
- Numerical precision
- SIMD opportunities

```rust
// crates/rusty_indicators/src/lib.rs

use rust_decimal::Decimal;

/// Simple Moving Average
pub fn sma(prices: &[Decimal], period: usize) -> Vec<Decimal> {
    let mut result = Vec::with_capacity(prices.len());

    for i in 0..prices.len() {
        if i < period - 1 {
            result.push(Decimal::ZERO);  // Not enough data
        } else {
            let sum: Decimal = prices[i - period + 1..=i].iter().sum();
            result.push(sum / Decimal::from(period));
        }
    }

    result
}

/// Exponential Moving Average
pub fn ema(prices: &[Decimal], period: usize) -> Vec<Decimal> {
    // EMA implementation with Decimal
}

/// Relative Strength Index
pub fn rsi(prices: &[Decimal], period: usize) -> Vec<Decimal> {
    // RSI implementation
}

/// Bollinger Bands
pub fn bollinger_bands(prices: &[Decimal], period: usize,
                      std_dev: Decimal) -> (Vec<Decimal>, Vec<Decimal>, Vec<Decimal>) {
    // Returns (upper_band, middle_band, lower_band)
}

/// MACD (Moving Average Convergence Divergence)
pub fn macd(prices: &[Decimal], fast: usize, slow: usize,
           signal: usize) -> (Vec<Decimal>, Vec<Decimal>, Vec<Decimal>) {
    // Returns (macd_line, signal_line, histogram)
}
```

**Module 4: Decimal Operations** (`rusty_decimal_ops`)

**Why Rust:**
- Python Decimal is slow
- Rust `rust_decimal` crate is faster
- Can use SIMD with careful implementation

```rust
// crates/rusty_decimal_ops/src/lib.rs

use rust_decimal::Decimal;

/// Fast vector operations on Decimal arrays
pub struct DecimalVector {
    data: Vec<Decimal>,
}

impl DecimalVector {
    pub fn sum(&self) -> Decimal {
        self.data.iter().copied().sum()
    }

    pub fn mean(&self) -> Decimal {
        self.sum() / Decimal::from(self.data.len())
    }

    pub fn variance(&self) -> Decimal {
        let mean = self.mean();
        let squared_diffs: Decimal = self.data.iter()
            .map(|x| (*x - mean).powi(2))
            .sum();
        squared_diffs / Decimal::from(self.data.len())
    }

    pub fn std_dev(&self) -> Decimal {
        // Decimal sqrt is expensive, consider precision tradeoffs
        self.variance().sqrt().unwrap_or(Decimal::ZERO)
    }
}
```

#### 3. Python-Rust Interface with PyO3

**Setup:**
```toml
# Cargo.toml

[package]
name = "rustybt"
version = "0.1.0"
edition = "2021"

[lib]
name = "rustybt"
crate-type = ["cdylib"]

[dependencies]
pyo3 = { version = "0.20", features = ["extension-module", "abi3-py39"] }
rust_decimal = "1.33"
rust_decimal_macros = "1.33"
```

**Python Bindings:**
```rust
// src/lib.rs

use pyo3::prelude::*;
use rust_decimal::Decimal;
use std::str::FromStr;

/// PyO3 wrapper for OrderBook
#[pyclass]
pub struct PyOrderBook {
    inner: OrderBook,
}

#[pymethods]
impl PyOrderBook {
    #[new]
    pub fn new() -> Self {
        PyOrderBook {
            inner: OrderBook::new(),
        }
    }

    pub fn add_order(&mut self, side: &str, price: &str,
                    quantity: &str) -> PyResult<u64> {
        let price = Decimal::from_str(price)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                format!("Invalid price: {}", e)))?;
        let quantity = Decimal::from_str(quantity)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                format!("Invalid quantity: {}", e)))?;

        // Add order and return order ID
        Ok(self.inner.add_order(/* ... */))
    }

    pub fn get_best_bid(&self) -> Option<String> {
        self.inner.get_best_bid().map(|d| d.to_string())
    }

    pub fn get_best_ask(&self) -> Option<String> {
        self.inner.get_best_ask().map(|d| d.to_string())
    }
}

/// Module initialization
#[pymodule]
fn rustybt(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<PyOrderBook>()?;
    // Add other classes
    Ok(())
}
```

**Python Usage:**
```python
# Transparent usage from Python
from decimal import Decimal
from rustybt import PyOrderBook

# Create order book
book = PyOrderBook()

# Add orders (prices as strings to preserve precision)
order_id = book.add_order("buy", "100.50", "10.0")

# Query book
best_bid = book.get_best_bid()  # Returns "100.50" as string
best_ask = book.get_best_ask()

# Convert back to Python Decimal
if best_bid:
    bid_price = Decimal(best_bid)
```

#### 4. Performance Benchmarking

**Benchmark Suite:**
```python
# benchmarks/bench_portfolio.py

import pytest
from decimal import Decimal
from rustybt import Portfolio as RustPortfolio
from zipline.finance.portfolio import Portfolio as PythonPortfolio

def bench_portfolio_value_python(benchmark):
    portfolio = PythonPortfolio(Decimal("100000"))
    # Add 1000 positions
    prices = {i: Decimal("100.50") for i in range(1000)}

    benchmark(portfolio.calculate_value, prices)

def bench_portfolio_value_rust(benchmark):
    portfolio = RustPortfolio(Decimal("100000"))
    # Add 1000 positions
    prices = {i: Decimal("100.50") for i in range(1000)}

    benchmark(portfolio.calculate_value, prices)

# Run with: pytest benchmarks/bench_portfolio.py --benchmark-compare
```

**Expected Speedups:**
- Order matching: 50-100x faster
- Portfolio calculations: 20-50x faster
- Indicators: 10-30x faster
- Decimal operations: 10-20x faster

**Deliverables:**
- 4 Rust crates (matching, portfolio, indicators, decimal_ops)
- PyO3 bindings for all modules
- Python wrapper layer (seamless integration)
- Comprehensive benchmarks (Python vs Rust)
- Performance optimization guide
- Integration tests (ensure correctness)
- Documentation

**Resource Requirements:**
- Rust Developer (full-time)
- Core Developer (Python integration)

---

### Phase 6: RESTful API & WebSocket Interface (Months 22-24)

**Objective:** Complete HTTP API for all framework operations plus real-time WebSocket streams

**Tech Stack:**
- **FastAPI** - Modern async web framework
- **Pydantic** - Request/response validation
- **WebSockets** - Real-time data streaming
- **JWT** - Authentication
- **Redis** - Caching and pub/sub

#### 1. REST API Design

**Architecture:**
```python
# api/main.py

from fastapi import FastAPI, Depends, HTTPException, WebSocket
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from decimal import Decimal
from datetime import datetime

app = FastAPI(
    title="RustyBT API",
    description="Python/Rust Trading Platform API",
    version="1.0.0"
)

security = HTTPBearer()
```

**API Endpoints:**

**Strategy Management:**
```python
# POST /api/v1/strategies - Create new strategy
class CreateStrategyRequest(BaseModel):
    name: str
    code: str  # Python strategy code
    parameters: dict[str, Any]

class StrategyResponse(BaseModel):
    id: str
    name: str
    status: str  # "created", "running", "stopped"
    created_at: datetime

@app.post("/api/v1/strategies", response_model=StrategyResponse)
async def create_strategy(req: CreateStrategyRequest,
                         credentials: HTTPAuthorizationCredentials = Depends(security)):
    # Validate token, create strategy
    pass

# GET /api/v1/strategies/{id} - Get strategy details
@app.get("/api/v1/strategies/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(strategy_id: str,
                      credentials: HTTPAuthorizationCredentials = Depends(security)):
    pass

# GET /api/v1/strategies - List all strategies
@app.get("/api/v1/strategies", response_model=list[StrategyResponse])
async def list_strategies(credentials: HTTPAuthorizationCredentials = Depends(security)):
    pass

# DELETE /api/v1/strategies/{id} - Delete strategy
@app.delete("/api/v1/strategies/{strategy_id}")
async def delete_strategy(strategy_id: str,
                         credentials: HTTPAuthorizationCredentials = Depends(security)):
    pass
```

**Backtesting:**
```python
# POST /api/v1/backtests - Run backtest
class BacktestRequest(BaseModel):
    strategy_id: str
    start_date: datetime
    end_date: datetime
    initial_capital: Decimal
    symbols: list[str]
    parameters: dict[str, Any] = {}

class BacktestResponse(BaseModel):
    backtest_id: str
    status: str  # "queued", "running", "completed", "failed"
    progress: float  # 0.0 to 1.0

@app.post("/api/v1/backtests", response_model=BacktestResponse)
async def run_backtest(req: BacktestRequest,
                      credentials: HTTPAuthorizationCredentials = Depends(security)):
    # Queue backtest job (async with Celery/RQ)
    pass

# GET /api/v1/backtests/{id} - Get backtest results
class BacktestResultsResponse(BaseModel):
    backtest_id: str
    status: str
    metrics: dict[str, Decimal]  # Sharpe, returns, drawdown, etc.
    trades: list[dict]
    equity_curve: list[dict[str, Any]]

@app.get("/api/v1/backtests/{backtest_id}",
         response_model=BacktestResultsResponse)
async def get_backtest_results(backtest_id: str,
                               credentials: HTTPAuthorizationCredentials = Depends(security)):
    pass

# GET /api/v1/backtests - List all backtests
@app.get("/api/v1/backtests", response_model=list[BacktestResponse])
async def list_backtests(credentials: HTTPAuthorizationCredentials = Depends(security)):
    pass
```

**Optimization:**
```python
# POST /api/v1/optimize - Parameter optimization
class OptimizationRequest(BaseModel):
    strategy_id: str
    start_date: datetime
    end_date: datetime
    initial_capital: Decimal
    symbols: list[str]
    parameters: dict[str, list[Any]]  # Parameter grid
    optimization_metric: str  # "sharpe", "returns", "sortino"
    algorithm: str  # "grid", "bayesian", "genetic"

class OptimizationResponse(BaseModel):
    optimization_id: str
    status: str
    best_parameters: dict[str, Any] | None
    best_score: Decimal | None

@app.post("/api/v1/optimize", response_model=OptimizationResponse)
async def optimize_strategy(req: OptimizationRequest,
                           credentials: HTTPAuthorizationCredentials = Depends(security)):
    pass

# GET /api/v1/optimize/{id} - Get optimization results
@app.get("/api/v1/optimize/{optimization_id}",
         response_model=OptimizationResponse)
async def get_optimization_results(optimization_id: str,
                                  credentials: HTTPAuthorizationCredentials = Depends(security)):
    pass
```

**Data Management:**
```python
# GET /api/v1/data/symbols - List available symbols
class SymbolInfo(BaseModel):
    symbol: str
    name: str
    asset_type: str  # "stock", "crypto", "forex"
    exchange: str
    start_date: datetime
    end_date: datetime

@app.get("/api/v1/data/symbols", response_model=list[SymbolInfo])
async def list_symbols(asset_type: str | None = None,
                      exchange: str | None = None,
                      credentials: HTTPAuthorizationCredentials = Depends(security)):
    pass

# GET /api/v1/data/symbols/{symbol}/ohlcv - Get historical data
class OHLCVResponse(BaseModel):
    symbol: str
    data: list[dict[str, Any]]  # timestamp, open, high, low, close, volume

@app.get("/api/v1/data/symbols/{symbol}/ohlcv",
         response_model=OHLCVResponse)
async def get_ohlcv(symbol: str, start_date: datetime, end_date: datetime,
                   resolution: str = "1d",
                   credentials: HTTPAuthorizationCredentials = Depends(security)):
    pass
```

**Live Trading:**
```python
# POST /api/v1/live/start - Start live trading
class LiveTradingRequest(BaseModel):
    strategy_id: str
    broker: str  # "alpaca", "interactive_brokers"
    mode: str  # "paper", "live"
    initial_capital: Decimal | None
    symbols: list[str]

class LiveTradingResponse(BaseModel):
    session_id: str
    status: str  # "starting", "running", "stopped"

@app.post("/api/v1/live/start", response_model=LiveTradingResponse)
async def start_live_trading(req: LiveTradingRequest,
                            credentials: HTTPAuthorizationCredentials = Depends(security)):
    pass

# POST /api/v1/live/stop - Stop live trading
@app.post("/api/v1/live/stop")
async def stop_live_trading(session_id: str,
                           credentials: HTTPAuthorizationCredentials = Depends(security)):
    pass

# GET /api/v1/portfolio - Get current portfolio
class PortfolioResponse(BaseModel):
    cash: Decimal
    positions: list[dict[str, Any]]
    total_value: Decimal
    daily_pnl: Decimal

@app.get("/api/v1/portfolio", response_model=PortfolioResponse)
async def get_portfolio(credentials: HTTPAuthorizationCredentials = Depends(security)):
    pass

# POST /api/v1/orders - Place order
class OrderRequest(BaseModel):
    symbol: str
    side: str  # "buy", "sell"
    order_type: str  # "market", "limit", "stop"
    quantity: Decimal
    price: Decimal | None

class OrderResponse(BaseModel):
    order_id: str
    status: str
    filled_quantity: Decimal
    average_price: Decimal | None

@app.post("/api/v1/orders", response_model=OrderResponse)
async def place_order(req: OrderRequest,
                     credentials: HTTPAuthorizationCredentials = Depends(security)):
    pass

# GET /api/v1/orders - List orders
@app.get("/api/v1/orders", response_model=list[OrderResponse])
async def list_orders(status: str | None = None,
                     credentials: HTTPAuthorizationCredentials = Depends(security)):
    pass
```

#### 2. WebSocket Interface

**Real-time Streams:**

**Portfolio Updates:**
```python
@app.websocket("/api/v1/ws/portfolio")
async def websocket_portfolio(websocket: WebSocket):
    await websocket.accept()

    # Authenticate
    token = await websocket.receive_text()
    if not validate_token(token):
        await websocket.close(code=1008)
        return

    # Stream portfolio updates
    async for update in portfolio_stream():
        await websocket.send_json({
            "type": "portfolio_update",
            "timestamp": datetime.utcnow().isoformat(),
            "cash": str(update.cash),
            "positions": update.positions,
            "total_value": str(update.total_value),
        })
```

**Order Status Updates:**
```python
@app.websocket("/api/v1/ws/orders")
async def websocket_orders(websocket: WebSocket):
    await websocket.accept()
    token = await websocket.receive_text()
    if not validate_token(token):
        await websocket.close(code=1008)
        return

    async for order_update in order_stream():
        await websocket.send_json({
            "type": "order_update",
            "order_id": order_update.order_id,
            "status": order_update.status,
            "filled_quantity": str(order_update.filled_quantity),
            "average_price": str(order_update.average_price),
        })
```

**Trade Executions:**
```python
@app.websocket("/api/v1/ws/trades")
async def websocket_trades(websocket: WebSocket):
    await websocket.accept()
    token = await websocket.receive_text()
    if not validate_token(token):
        await websocket.close(code=1008)
        return

    async for trade in trade_stream():
        await websocket.send_json({
            "type": "trade",
            "trade_id": trade.trade_id,
            "symbol": trade.symbol,
            "side": trade.side,
            "quantity": str(trade.quantity),
            "price": str(trade.price),
            "timestamp": trade.timestamp.isoformat(),
        })
```

**Market Data Stream:**
```python
@app.websocket("/api/v1/ws/market/{symbol}")
async def websocket_market_data(websocket: WebSocket, symbol: str):
    await websocket.accept()
    token = await websocket.receive_text()
    if not validate_token(token):
        await websocket.close(code=1008)
        return

    async for bar in market_data_stream(symbol):
        await websocket.send_json({
            "type": "bar",
            "symbol": symbol,
            "timestamp": bar.timestamp.isoformat(),
            "open": str(bar.open),
            "high": str(bar.high),
            "low": str(bar.low),
            "close": str(bar.close),
            "volume": str(bar.volume),
        })
```

#### 3. Authentication & Security

**JWT Token Authentication:**
```python
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import timedelta

SECRET_KEY = "your-secret-key"  # Load from environment
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        return username
    except JWTError:
        return None

# Login endpoint
class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/api/v1/auth/login")
async def login(req: LoginRequest):
    # Verify username/password
    if not authenticate_user(req.username, req.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token(
        data={"sub": req.username},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}
```

**API Key Management:**
```python
# Alternative to JWT for programmatic access
class APIKey(BaseModel):
    key: str
    secret: str
    permissions: list[str]
    expires_at: datetime | None

@app.post("/api/v1/auth/api-keys")
async def create_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    # Create new API key for user
    pass

@app.delete("/api/v1/auth/api-keys/{key}")
async def revoke_api_key(key: str,
                        credentials: HTTPAuthorizationCredentials = Depends(security)):
    pass
```

**Rate Limiting:**
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/api/v1/data/symbols")
@limiter.limit("100/minute")  # 100 requests per minute
async def list_symbols(request: Request):
    pass
```

**Request Validation:**
```python
# Pydantic automatically validates all requests
class OrderRequest(BaseModel):
    symbol: str
    side: str  # Validated against enum
    order_type: str
    quantity: Decimal  # Validated as Decimal
    price: Decimal | None

    @validator('side')
    def validate_side(cls, v):
        if v not in ['buy', 'sell']:
            raise ValueError('side must be "buy" or "sell"')
        return v

    @validator('quantity')
    def validate_quantity(cls, v):
        if v <= 0:
            raise ValueError('quantity must be positive')
        return v
```

**Audit Logging:**
```python
import structlog

logger = structlog.get_logger()

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info("api_request",
                method=request.method,
                url=str(request.url),
                user=request.state.user if hasattr(request.state, "user") else None)

    response = await call_next(request)

    logger.info("api_response",
                status_code=response.status_code,
                method=request.method,
                url=str(request.url))

    return response
```

#### 4. API Documentation

**OpenAPI/Swagger:**
```python
# Automatically generated by FastAPI
# Available at: http://localhost:8000/docs (Swagger UI)
# Available at: http://localhost:8000/redoc (ReDoc)

app = FastAPI(
    title="RustyBT Trading Platform API",
    description="""
    Complete API for backtesting and live trading.

    ## Features

    * **Strategy Management** - Create, run, and manage trading strategies
    * **Backtesting** - Historical strategy testing
    * **Optimization** - Parameter optimization
    * **Live Trading** - Real-time strategy execution
    * **Data Access** - Historical and real-time market data
    * **WebSockets** - Real-time updates
    """,
    version="1.0.0",
    contact={
        "name": "RustyBT Support",
        "email": "support@rustybt.io",
    },
    license_info={
        "name": "MIT",
    },
)
```

**Deliverables:**
- Complete FastAPI REST API
- WebSocket server for real-time streams
- JWT authentication system
- API key management
- Rate limiting
- Request validation (Pydantic)
- Audit logging
- OpenAPI/Swagger documentation
- API client libraries (Python, JavaScript)
- Comprehensive tests (pytest + httpx)
- Deployment guide (Docker, Kubernetes)

**Resource Requirements:**
- Core Developer (full-time)
- Frontend Developer (part-time, for API client libraries)

---

### Phase 7: Analytics & Reporting (Months 25-27)

**Objective:** Comprehensive performance metrics, interactive visualizations, and professional reports

#### 1. Performance Metrics Suite

**Risk Metrics:**
```python
# zipline/finance/metrics.py

from decimal import Decimal
import polars as pl

class PerformanceMetrics:
    """Comprehensive performance metrics"""

    def __init__(self, returns: pl.Series, portfolio_values: pl.Series):
        self.returns = returns
        self.portfolio_values = portfolio_values

    # Return Metrics
    def total_return(self) -> Decimal:
        """Total return over period"""
        return (self.portfolio_values[-1] / self.portfolio_values[0]) - 1

    def annualized_return(self, periods_per_year: int = 252) -> Decimal:
        """CAGR - Compound Annual Growth Rate"""
        n_periods = len(self.portfolio_values)
        years = n_periods / periods_per_year
        return (self.portfolio_values[-1] / self.portfolio_values[0]) ** (1 / years) - 1

    def monthly_returns(self) -> pl.DataFrame:
        """Monthly return breakdown"""

    # Risk Metrics
    def volatility(self, periods_per_year: int = 252) -> Decimal:
        """Annualized volatility"""
        return self.returns.std() * Decimal(periods_per_year).sqrt()

    def value_at_risk(self, confidence: Decimal = Decimal("0.95")) -> Decimal:
        """VaR - Value at Risk"""
        return self.returns.quantile(1 - confidence)

    def conditional_value_at_risk(self, confidence: Decimal = Decimal("0.95")) -> Decimal:
        """CVaR - Expected Shortfall"""
        var = self.value_at_risk(confidence)
        return self.returns[self.returns <= var].mean()

    # Risk-Adjusted Returns
    def sharpe_ratio(self, risk_free_rate: Decimal = Decimal("0.02"),
                    periods_per_year: int = 252) -> Decimal:
        """Sharpe Ratio"""
        excess_returns = self.returns.mean() - (risk_free_rate / periods_per_year)
        return (excess_returns / self.returns.std()) * Decimal(periods_per_year).sqrt()

    def sortino_ratio(self, target_return: Decimal = Decimal("0"),
                     periods_per_year: int = 252) -> Decimal:
        """Sortino Ratio - downside risk only"""
        excess_returns = self.returns.mean() - target_return
        downside_returns = self.returns[self.returns < target_return]
        downside_deviation = downside_returns.std()
        return (excess_returns / downside_deviation) * Decimal(periods_per_year).sqrt()

    def calmar_ratio(self) -> Decimal:
        """Calmar Ratio - return / max drawdown"""
        annual_return = self.annualized_return()
        max_dd = self.max_drawdown()
        return annual_return / abs(max_dd)

    # Drawdown Analysis
    def max_drawdown(self) -> Decimal:
        """Maximum drawdown"""
        cummax = self.portfolio_values.cummax()
        drawdowns = (self.portfolio_values - cummax) / cummax
        return drawdowns.min()

    def average_drawdown(self) -> Decimal:
        """Average drawdown"""
        cummax = self.portfolio_values.cummax()
        drawdowns = (self.portfolio_values - cummax) / cummax
        return drawdowns[drawdowns < 0].mean()

    def drawdown_periods(self) -> pl.DataFrame:
        """All drawdown periods with duration and recovery time"""

    def longest_drawdown_duration(self) -> int:
        """Longest drawdown duration in periods"""

    # Exposure Analysis
    def long_exposure(self, positions: pl.DataFrame) -> pl.Series:
        """Long exposure over time"""

    def short_exposure(self, positions: pl.DataFrame) -> pl.Series:
        """Short exposure over time"""

    def net_exposure(self, positions: pl.DataFrame) -> pl.Series:
        """Net exposure (long - short)"""

    def gross_exposure(self, positions: pl.DataFrame) -> pl.Series:
        """Gross exposure (long + short)"""

    # Trading Activity
    def turnover(self, trades: pl.DataFrame) -> Decimal:
        """Portfolio turnover rate"""

    def trade_count(self, trades: pl.DataFrame) -> int:
        """Total number of trades"""

    def win_rate(self, trades: pl.DataFrame) -> Decimal:
        """Percentage of profitable trades"""

    def profit_factor(self, trades: pl.DataFrame) -> Decimal:
        """Gross profit / Gross loss"""

    def average_win(self, trades: pl.DataFrame) -> Decimal:
        """Average winning trade"""

    def average_loss(self, trades: pl.DataFrame) -> Decimal:
        """Average losing trade"""

    def largest_win(self, trades: pl.DataFrame) -> Decimal:
        """Largest winning trade"""

    def largest_loss(self, trades: pl.DataFrame) -> Decimal:
        """Largest losing trade"""

    # Factor Attribution
    def beta(self, benchmark_returns: pl.Series) -> Decimal:
        """Beta relative to benchmark"""

    def alpha(self, benchmark_returns: pl.Series,
             risk_free_rate: Decimal = Decimal("0.02")) -> Decimal:
        """Alpha (excess return over benchmark)"""

    def correlation(self, benchmark_returns: pl.Series) -> Decimal:
        """Correlation with benchmark"""
```

**Walk-Forward Analysis:**
```python
class WalkForwardAnalysis:
    """Walk-forward testing results"""

    def __init__(self, results: list[BacktestResult]):
        self.results = results

    def parameter_stability(self) -> pl.DataFrame:
        """How stable are optimal parameters across windows?"""

    def out_of_sample_performance(self) -> pl.DataFrame:
        """Performance on out-of-sample periods"""

    def degradation_analysis(self) -> Decimal:
        """How much does performance degrade OOS?"""
```

#### 2. Interactive Visualization with Plotly

**Charts to Implement:**

**1. Equity Curve with Drawdowns:**
```python
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def plot_equity_curve(portfolio_values, drawdowns):
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.7, 0.3],
        subplot_titles=("Portfolio Value", "Drawdown")
    )

    # Equity curve
    fig.add_trace(
        go.Scatter(x=portfolio_values.index, y=portfolio_values.values,
                  name="Portfolio Value", line=dict(color="blue")),
        row=1, col=1
    )

    # Drawdown
    fig.add_trace(
        go.Scatter(x=drawdowns.index, y=drawdowns.values,
                  name="Drawdown", fill='tozeroy',
                  line=dict(color="red")),
        row=2, col=1
    )

    fig.update_layout(height=600, title_text="Portfolio Performance")
    return fig
```

**2. Monthly Returns Heatmap:**
```python
def plot_monthly_returns_heatmap(monthly_returns):
    """Heatmap of monthly returns by year"""
    pivot = monthly_returns.pivot_table(
        values='return',
        index='year',
        columns='month'
    )

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
           'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
        y=pivot.index,
        colorscale='RdYlGn',
        zmid=0,
        text=pivot.values,
        texttemplate='%{text:.1%}',
    ))

    fig.update_layout(title="Monthly Returns Heatmap")
    return fig
```

**3. Rolling Sharpe Ratio:**
```python
def plot_rolling_sharpe(returns, window=252):
    """Rolling Sharpe ratio over time"""
    rolling_sharpe = returns.rolling(window).apply(
        lambda x: (x.mean() / x.std()) * np.sqrt(252)
    )

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=rolling_sharpe.index,
        y=rolling_sharpe.values,
        name=f"{window}-day Rolling Sharpe"
    ))

    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    fig.update_layout(title="Rolling Sharpe Ratio")
    return fig
```

**4. Position Exposure Over Time:**
```python
def plot_exposure(long_exposure, short_exposure, net_exposure):
    """Long/short/net exposure over time"""
    fig = go.Figure()

    fig.add_trace(go.Scatter(x=long_exposure.index, y=long_exposure.values,
                            name="Long Exposure", fill='tozeroy',
                            line=dict(color="green")))

    fig.add_trace(go.Scatter(x=short_exposure.index, y=short_exposure.values,
                            name="Short Exposure", fill='tozeroy',
                            line=dict(color="red")))

    fig.add_trace(go.Scatter(x=net_exposure.index, y=net_exposure.values,
                            name="Net Exposure", line=dict(color="blue")))

    fig.update_layout(title="Portfolio Exposure Over Time")
    return fig
```

**5. Trade Analysis:**
```python
def plot_trade_analysis(trades):
    """Win/loss distribution and trade timeline"""
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=("Trade PnL Distribution", "Cumulative PnL")
    )

    # PnL histogram
    fig.add_trace(
        go.Histogram(x=trades['pnl'], name="PnL Distribution",
                    marker_color=['red' if x < 0 else 'green'
                                 for x in trades['pnl']]),
        row=1, col=1
    )

    # Cumulative PnL
    cumulative_pnl = trades['pnl'].cumsum()
    fig.add_trace(
        go.Scatter(x=trades.index, y=cumulative_pnl,
                  name="Cumulative PnL"),
        row=1, col=2
    )

    return fig
```

**6. Monte Carlo Simulation:**
```python
def plot_monte_carlo(simulations, actual_equity):
    """Monte Carlo simulation results"""
    fig = go.Figure()

    # Plot simulations (transparent)
    for sim in simulations:
        fig.add_trace(go.Scatter(
            y=sim, mode='lines',
            line=dict(color='gray', width=0.5),
            opacity=0.1,
            showlegend=False
        ))

    # Plot actual
    fig.add_trace(go.Scatter(
        y=actual_equity,
        name="Actual",
        line=dict(color='blue', width=3)
    ))

    fig.update_layout(title="Monte Carlo Simulation (1000 runs)")
    return fig
```

#### 3. Report Generation

**HTML Report Template:**
```python
from jinja2 import Template
import weasyprint  # For PDF generation

REPORT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Backtest Report - {{ strategy_name }}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        h1 { color: #333; }
        .metrics-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .metric { background: #f5f5f5; padding: 15px; border-radius: 5px; }
        .metric-label { font-weight: bold; color: #666; }
        .metric-value { font-size: 24px; color: #333; }
        .positive { color: green; }
        .negative { color: red; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #f0f0f0; }
    </style>
</head>
<body>
    <h1>Backtest Report: {{ strategy_name }}</h1>

    <h2>Executive Summary</h2>
    <div class="metrics-grid">
        <div class="metric">
            <div class="metric-label">Total Return</div>
            <div class="metric-value {{ 'positive' if metrics.total_return > 0 else 'negative' }}">
                {{ metrics.total_return | format_percent }}
            </div>
        </div>
        <div class="metric">
            <div class="metric-label">Sharpe Ratio</div>
            <div class="metric-value">{{ metrics.sharpe_ratio | round(2) }}</div>
        </div>
        <div class="metric">
            <div class="metric-label">Max Drawdown</div>
            <div class="metric-value negative">{{ metrics.max_drawdown | format_percent }}</div>
        </div>
        <div class="metric">
            <div class="metric-label">Win Rate</div>
            <div class="metric-value">{{ metrics.win_rate | format_percent }}</div>
        </div>
    </div>

    <h2>Equity Curve</h2>
    {{ equity_curve_chart | safe }}

    <h2>Monthly Returns</h2>
    {{ monthly_returns_chart | safe }}

    <h2>Performance Metrics</h2>
    <table>
        <tr><th>Metric</th><th>Value</th></tr>
        {% for key, value in all_metrics.items() %}
        <tr><td>{{ key }}</td><td>{{ value }}</td></tr>
        {% endfor %}
    </table>

    <h2>Trade Log</h2>
    <table>
        <tr><th>Date</th><th>Symbol</th><th>Side</th><th>Quantity</th><th>Price</th><th>PnL</th></tr>
        {% for trade in trades %}
        <tr>
            <td>{{ trade.date }}</td>
            <td>{{ trade.symbol }}</td>
            <td>{{ trade.side }}</td>
            <td>{{ trade.quantity }}</td>
            <td>{{ trade.price }}</td>
            <td class="{{ 'positive' if trade.pnl > 0 else 'negative' }}">{{ trade.pnl }}</td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
"""

class ReportGenerator:
    """Generate HTML/PDF reports"""

    def generate_html_report(self, backtest_result):
        """Generate HTML report"""
        template = Template(REPORT_TEMPLATE)

        # Generate charts as HTML
        equity_curve_chart = plot_equity_curve(...).to_html(full_html=False)
        monthly_returns_chart = plot_monthly_returns_heatmap(...).to_html(full_html=False)

        html = template.render(
            strategy_name=backtest_result.strategy_name,
            metrics=backtest_result.metrics,
            all_metrics=backtest_result.all_metrics_dict(),
            equity_curve_chart=equity_curve_chart,
            monthly_returns_chart=monthly_returns_chart,
            trades=backtest_result.trades
        )

        return html

    def generate_pdf_report(self, backtest_result):
        """Generate PDF report from HTML"""
        html = self.generate_html_report(backtest_result)
        pdf = weasyprint.HTML(string=html).write_pdf()
        return pdf
```

**Deliverables:**
- Comprehensive metrics library (50+ metrics)
- Interactive Plotly charts (equity curve, heatmaps, rolling metrics, exposure, trades, Monte Carlo)
- HTML/PDF report generator with professional templates
- Jupyter notebook examples
- Dashboard framework (Dash/Streamlit)
- Documentation

**Resource Requirements:**
- Core Developer (full-time)
- Data Visualization Specialist (part-time)

---

### Phase 8: Testing & Quality Assurance (Ongoing, All Phases)

**Objective:** Maintain 90%+ test coverage with comprehensive testing strategy

#### Test Types:

**1. Unit Tests (pytest)**
```python
# tests/test_decimal_arithmetic.py

from decimal import Decimal
import pytest
from zipline.finance.portfolio import Portfolio

class TestDecimalPrecision:
    """Test Decimal arithmetic precision"""

    def test_no_rounding_errors(self):
        """Verify no floating point rounding errors"""
        price = Decimal("0.1")
        quantity = Decimal("3")
        total = price * quantity
        assert total == Decimal("0.3")  # Would fail with float

    def test_large_numbers(self):
        """Handle large numbers accurately"""
        large = Decimal("999999999999.99")
        small = Decimal("0.01")
        result = large + small
        assert result == Decimal("1000000000000.00")

    def test_division_precision(self):
        """Division maintains precision"""
        numerator = Decimal("10")
        denominator = Decimal("3")
        result = numerator / denominator
        assert str(result).startswith("3.333333")  # Check precision
```

**2. Integration Tests**
```python
# tests/test_integration.py

def test_full_backtest_workflow():
    """Test complete backtest from start to finish"""
    # 1. Load data
    data_catalog = PolarsCatalog("test_data")
    symbols = ["AAPL", "GOOGL"]

    # 2. Create strategy
    strategy = BuyAndHoldStrategy()

    # 3. Run backtest
    result = run_backtest(
        strategy=strategy,
        symbols=symbols,
        start_date="2020-01-01",
        end_date="2023-12-31",
        initial_capital=Decimal("100000")
    )

    # 4. Verify results
    assert result.final_portfolio_value > 0
    assert len(result.trades) > 0
    assert result.metrics['sharpe_ratio'] is not None
```

**3. Contract Tests (API)**
```python
# tests/test_api_contracts.py

from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_create_strategy_contract():
    """Test strategy creation API contract"""
    response = client.post(
        "/api/v1/strategies",
        json={
            "name": "Test Strategy",
            "code": "class TestStrategy: pass",
            "parameters": {}
        },
        headers={"Authorization": "Bearer test_token"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "name" in data
    assert "status" in data
    assert data["name"] == "Test Strategy"
```

**4. Property-Based Tests (Hypothesis)**
```python
# tests/test_properties.py

from hypothesis import given, strategies as st
from decimal import Decimal

@given(
    price=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("10000")),
    quantity=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("1000"))
)
def test_order_value_commutative(price, quantity):
    """Order value calculation is commutative"""
    assert price * quantity == quantity * price

@given(
    prices=st.lists(st.decimals(min_value=Decimal("1"), max_value=Decimal("100")),
                   min_size=10, max_size=100)
)
def test_portfolio_value_non_negative(prices):
    """Portfolio value should never be negative"""
    portfolio = Portfolio(initial_capital=Decimal("10000"))
    # ... add positions ...
    value = portfolio.calculate_value(prices)
    assert value >= 0
```

**5. Performance Tests (pytest-benchmark)**
```python
# tests/test_performance.py

def test_portfolio_calculation_performance(benchmark):
    """Portfolio value calculation should be fast"""
    portfolio = create_large_portfolio(1000)  # 1000 positions
    prices = generate_prices(1000)

    result = benchmark(portfolio.calculate_value, prices)

    # Should complete in <10ms
    assert benchmark.stats['mean'] < 0.01

def test_backtest_speed(benchmark):
    """Full backtest should complete in reasonable time"""
    # 1 year, minute bars, 10 symbols = ~600k bars
    result = benchmark(run_small_backtest)

    # Should complete in <60 seconds
    assert benchmark.stats['mean'] < 60
```

#### CI/CD Pipeline (GitHub Actions):

```yaml
# .github/workflows/test.yml

name: Test Suite

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.9', '3.10', '3.11', '3.12']

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}

    - name: Install dependencies
      run: |
        pip install -e .[dev,test]

    - name: Lint (ruff)
      run: ruff check .

    - name: Type check (mypy)
      run: mypy zipline/

    - name: Run tests
      run: pytest --cov=zipline --cov-report=xml --cov-report=html

    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml

    - name: Performance benchmarks
      run: pytest benchmarks/ --benchmark-only
```

**Quality Gates:**
- ✅ All tests pass
- ✅ Coverage ≥90% for financial modules (zipline/finance/)
- ✅ No type errors (mypy --strict)
- ✅ No linting errors (ruff)
- ✅ Performance benchmarks stable (no >10% regression)
- ✅ Documentation updated

**Deliverables:**
- Comprehensive test suite (unit, integration, contract, property-based, performance)
- CI/CD pipeline (GitHub Actions)
- Coverage reporting (Codecov)
- Quality gates enforcement
- Testing documentation and best practices guide

---

### Phase 9: Optimization & Parameter Testing (Months 28-30)

**Objective:** Advanced optimization algorithms and overfitting prevention

#### 1. Optimization Algorithms

**Grid Search:**
```python
class GridSearchOptimizer:
    """Exhaustive parameter grid search"""

    def optimize(self, strategy, parameter_grid, data, metric='sharpe_ratio'):
        results = []

        # Generate all parameter combinations
        combinations = self._generate_combinations(parameter_grid)

        for params in combinations:
            result = self._run_backtest(strategy, params, data)
            results.append({
                'parameters': params,
                'score': result.metrics[metric]
            })

        return self._rank_results(results)
```

**Random Search:**
```python
class RandomSearchOptimizer:
    """Random parameter search (faster for high dimensions)"""

    def optimize(self, strategy, parameter_distributions, data,
                metric='sharpe_ratio', n_iterations=100):
        results = []

        for i in range(n_iterations):
            params = self._sample_parameters(parameter_distributions)
            result = self._run_backtest(strategy, params, data)
            results.append({
                'parameters': params,
                'score': result.metrics[metric]
            })

        return self._rank_results(results)
```

**Bayesian Optimization:**
```python
from skopt import gp_minimize
from skopt.space import Real, Integer, Categorical

class BayesianOptimizer:
    """Bayesian optimization using Gaussian Processes"""

    def optimize(self, strategy, parameter_space, data,
                metric='sharpe_ratio', n_calls=50):

        def objective(params):
            # Convert params to dict
            param_dict = self._params_to_dict(params, parameter_space)
            result = self._run_backtest(strategy, param_dict, data)
            return -result.metrics[metric]  # Minimize negative score

        result = gp_minimize(
            objective,
            dimensions=parameter_space,
            n_calls=n_calls,
            random_state=42
        )

        return {
            'best_parameters': self._params_to_dict(result.x, parameter_space),
            'best_score': -result.fun
        }
```

**Genetic Algorithm:**
```python
from deap import base, creator, tools, algorithms

class GeneticOptimizer:
    """Genetic algorithm optimization"""

    def optimize(self, strategy, parameter_ranges, data,
                metric='sharpe_ratio', population_size=50,
                generations=20):

        # Define fitness function
        def evaluate(individual):
            params = self._decode_individual(individual, parameter_ranges)
            result = self._run_backtest(strategy, params, data)
            return (result.metrics[metric],)  # Tuple for DEAP

        # Set up DEAP
        creator.create("FitnessMax", base.Fitness, weights=(1.0,))
        creator.create("Individual", list, fitness=creator.FitnessMax)

        toolbox = base.Toolbox()
        # Register genetic operators
        toolbox.register("evaluate", evaluate)
        toolbox.register("mate", tools.cxTwoPoint)
        toolbox.register("mutate", tools.mutGaussian, mu=0, sigma=1, indpb=0.1)
        toolbox.register("select", tools.selTournament, tournsize=3)

        # Run evolution
        population = self._initialize_population(population_size, parameter_ranges)
        result = algorithms.eaSimple(
            population, toolbox,
            cxpb=0.7, mutpb=0.2,
            ngen=generations,
            verbose=True
        )

        best = tools.selBest(population, k=1)[0]
        return self._decode_individual(best, parameter_ranges)
```

**Walk-Forward Optimization:**
```python
class WalkForwardOptimizer:
    """Walk-forward optimization to prevent overfitting"""

    def optimize(self, strategy, parameter_grid, data,
                in_sample_ratio=0.7, step_size=0.1):

        results = []

        # Split data into windows
        windows = self._create_windows(data, in_sample_ratio, step_size)

        for window in windows:
            # Optimize on in-sample data
            optimizer = GridSearchOptimizer()
            best_params = optimizer.optimize(
                strategy, parameter_grid, window['in_sample']
            )

            # Test on out-of-sample data
            oos_result = self._run_backtest(
                strategy, best_params, window['out_of_sample']
            )

            results.append({
                'window': window,
                'best_parameters': best_params,
                'in_sample_score': best_params['score'],
                'out_of_sample_score': oos_result.metrics['sharpe_ratio']
            })

        return self._analyze_walk_forward_results(results)
```

#### 2. Parallel Processing

**Multi-core Optimization:**
```python
from multiprocessing import Pool
import ray

class ParallelOptimizer:
    """Parallel parameter optimization"""

    def optimize_parallel(self, strategy, parameter_grid, data,
                         n_workers=8):

        combinations = self._generate_combinations(parameter_grid)

        # Use Ray for distributed computing
        ray.init(num_cpus=n_workers)

        @ray.remote
        def run_backtest_remote(params):
            return self._run_backtest(strategy, params, data)

        # Submit all jobs
        futures = [run_backtest_remote.remote(params)
                  for params in combinations]

        # Collect results
        results = ray.get(futures)

        ray.shutdown()
        return self._rank_results(results)
```

**Cloud Scaling (AWS/GCP):**
```python
class CloudOptimizer:
    """Scale optimization to cloud compute"""

    def optimize_on_aws(self, strategy, parameter_grid, data,
                       instance_type='c5.4xlarge', n_instances=10):

        # Use AWS Batch or similar
        # Submit optimization jobs to cloud
        # Aggregate results
        pass
```

#### 3. Overfitting Prevention

**Train/Validation/Test Split:**
```python
class DataSplitter:
    """Split data for proper validation"""

    def split(self, data, train_ratio=0.6, val_ratio=0.2, test_ratio=0.2):
        assert train_ratio + val_ratio + test_ratio == 1.0

        n = len(data)
        train_end = int(n * train_ratio)
        val_end = int(n * (train_ratio + val_ratio))

        return {
            'train': data[:train_end],
            'validation': data[train_end:val_end],
            'test': data[val_end:]
        }
```

**Combinatorially Purged Cross-Validation:**
```python
class CPCVSplitter:
    """CPCV to reduce overfitting (from López de Prado)"""

    def split(self, data, n_splits=5, embargo_pct=0.01):
        # Implement CPCV with purging and embargo
        # Prevents data leakage in time series
        pass
```

**Parameter Stability Analysis:**
```python
class ParameterStabilityAnalyzer:
    """Analyze parameter stability across windows"""

    def analyze(self, walk_forward_results):
        """Check if optimal parameters are consistent"""

        # Extract parameters from each window
        param_history = [w['best_parameters'] for w in walk_forward_results]

        # Calculate stability metrics
        stability = {}
        for param_name in param_history[0].keys():
            values = [params[param_name] for params in param_history]
            stability[param_name] = {
                'mean': np.mean(values),
                'std': np.std(values),
                'coefficient_of_variation': np.std(values) / np.mean(values)
            }

        return stability
```

**Deliverables:**
- 5 optimization algorithms (Grid, Random, Bayesian, Genetic, Walk-Forward)
- Parallel processing framework (multi-core and distributed)
- Overfitting prevention tools (CPCV, parameter stability analysis)
- Cloud optimization support
- Optimization best practices guide
- Example notebooks

**Resource Requirements:**
- Core Developer (full-time)
- Data Scientist (part-time)

---

### Phase 10: Security & Reliability (Months 30-33)

**Objective:** Production-grade security, error handling, and audit capabilities

#### 1. Type Safety

**Python Type Hints (mypy --strict):**
```python
from decimal import Decimal
from datetime import datetime
from typing import Protocol

class Portfolio:
    """Type-safe portfolio"""

    def __init__(self, initial_capital: Decimal) -> None:
        self.cash: Decimal = initial_capital
        self.positions: dict[str, Position] = {}

    def calculate_value(self, prices: dict[str, Decimal]) -> Decimal:
        total: Decimal = self.cash
        for symbol, position in self.positions.items():
            if symbol in prices:
                total += position.quantity * prices[symbol]
        return total
```

**Rust Type Safety (automatically enforced):**
```rust
// Rust compiler catches type errors at compile time
pub fn calculate_value(
    positions: &HashMap<AssetId, Position>,
    prices: &HashMap<AssetId, Decimal>
) -> Decimal {
    // Compiler ensures:
    // - No null pointer dereferences
    // - No data races
    // - No use-after-free
    // - Correct types throughout
}
```

#### 2. Error Handling

**Python Exception Hierarchy:**
```python
# zipline/exceptions.py

class ZiplineError(Exception):
    """Base exception for all Zipline errors"""
    pass

class DataError(ZiplineError):
    """Data-related errors"""
    pass

class OrderError(ZiplineError):
    """Order execution errors"""
    pass

class InsufficientFundsError(OrderError):
    """Not enough cash to place order"""
    pass

class InvalidOrderError(OrderError):
    """Invalid order parameters"""
    pass

class ConfigurationError(ZiplineError):
    """Configuration errors"""
    pass
```

**Graceful Error Handling:**
```python
class TradingEngine:
    """Trading engine with comprehensive error handling"""

    def execute_order(self, order: Order) -> Result[Fill, OrderError]:
        try:
            # Validate order
            self._validate_order(order)

            # Check funds
            if not self._has_sufficient_funds(order):
                return Err(InsufficientFundsError(
                    f"Insufficient funds for order {order.id}"
                ))

            # Execute
            fill = self._execute(order)

            # Log successful execution
            logger.info(f"Order executed: {order.id}")

            return Ok(fill)

        except InvalidOrderError as e:
            logger.error(f"Invalid order: {e}")
            return Err(e)

        except Exception as e:
            logger.exception(f"Unexpected error executing order: {e}")
            # Attempt recovery
            self._attempt_recovery(order, e)
            return Err(OrderError(f"Execution failed: {e}"))
```

**Rust Result Types:**
```rust
// Rust's Result type forces error handling

pub fn execute_order(order: Order) -> Result<Fill, OrderError> {
    // Validate
    validate_order(&order)?;  // ? operator propagates errors

    // Check funds
    if !has_sufficient_funds(&order) {
        return Err(OrderError::InsufficientFunds);
    }

    // Execute
    let fill = execute(&order)?;

    Ok(fill)
}

// Caller MUST handle Result:
match execute_order(order) {
    Ok(fill) => println!("Order executed: {:?}", fill),
    Err(e) => println!("Error: {:?}", e),
}
```

#### 3. Audit Trail

**Comprehensive Logging:**
```python
import structlog

# Structured logging for audit trail
logger = structlog.get_logger()

class AuditLogger:
    """Audit logging for compliance"""

    def log_order(self, order: Order, user_id: str):
        logger.info("order_submitted",
                   order_id=order.id,
                   user_id=user_id,
                   symbol=order.symbol,
                   side=order.side,
                   quantity=str(order.quantity),
                   price=str(order.price),
                   order_type=order.order_type,
                   timestamp=datetime.utcnow().isoformat())

    def log_fill(self, fill: Fill):
        logger.info("order_filled",
                   order_id=fill.order_id,
                   fill_id=fill.id,
                   quantity=str(fill.quantity),
                   price=str(fill.price),
                   timestamp=datetime.utcnow().isoformat())

    def log_strategy_decision(self, strategy_id: str, decision: dict):
        logger.info("strategy_decision",
                   strategy_id=strategy_id,
                   decision=decision,
                   timestamp=datetime.utcnow().isoformat())
```

**Trade-by-Trade Logs:**
```python
class TradeLogger:
    """Detailed trade logging"""

    def log_trade(self, trade: Trade):
        """Log every trade with full context"""
        log_entry = {
            'trade_id': trade.id,
            'order_id': trade.order_id,
            'strategy_id': trade.strategy_id,
            'symbol': trade.symbol,
            'side': trade.side,
            'quantity': str(trade.quantity),
            'price': str(trade.price),
            'commission': str(trade.commission),
            'slippage': str(trade.slippage),
            'pnl': str(trade.pnl),
            'portfolio_value_before': str(trade.portfolio_value_before),
            'portfolio_value_after': str(trade.portfolio_value_after),
            'timestamp': trade.timestamp.isoformat(),
            'context': trade.context  # Additional context (market conditions, etc.)
        }

        # Write to audit log
        self._write_audit_log(log_entry)
```

#### 4. Data Validation (Multi-layer)

**Layer 1: Schema Validation (Ingest)**
```python
import polars as pl

OHLCV_SCHEMA = {
    'timestamp': pl.Datetime,
    'symbol': pl.Utf8,
    'open': pl.Decimal,
    'high': pl.Decimal,
    'low': pl.Decimal,
    'close': pl.Decimal,
    'volume': pl.Decimal,
}

def validate_schema(df: pl.DataFrame) -> pl.DataFrame:
    """Validate data schema"""
    for col, dtype in OHLCV_SCHEMA.items():
        if col not in df.columns:
            raise DataError(f"Missing required column: {col}")
        if df[col].dtype != dtype:
            raise DataError(f"Invalid dtype for {col}: expected {dtype}, got {df[col].dtype}")
    return df
```

**Layer 2: OHLC Relationship Validation**
```python
def validate_ohlc_relationships(df: pl.DataFrame) -> pl.DataFrame:
    """Validate OHLC price relationships"""

    # O, H, L, C must all be positive
    if (df['open'] <= 0).any():
        raise DataError("Open prices must be positive")
    if (df['high'] <= 0).any():
        raise DataError("High prices must be positive")
    if (df['low'] <= 0).any():
        raise DataError("Low prices must be positive")
    if (df['close'] <= 0).any():
        raise DataError("Close prices must be positive")

    # High >= max(Open, Close)
    if not (df['high'] >= df['open'].max(df['close'])).all():
        raise DataError("High must be >= max(Open, Close)")

    # Low <= min(Open, Close)
    if not (df['low'] <= df['open'].min(df['close'])).all():
        raise DataError("Low must be <= min(Open, Close)")

    # Volume must be non-negative
    if (df['volume'] < 0).any():
        raise DataError("Volume must be non-negative")

    return df
```

**Layer 3: Outlier Detection**
```python
def detect_outliers(df: pl.DataFrame, n_std: Decimal = Decimal("5")) -> pl.DataFrame:
    """Detect and flag price outliers"""

    # Calculate returns
    returns = df['close'].pct_change()

    # Flag outliers (>5 std deviations)
    mean = returns.mean()
    std = returns.std()
    outliers = (returns - mean).abs() > (n_std * std)

    if outliers.any():
        logger.warning(f"Detected {outliers.sum()} potential outliers",
                      outlier_dates=df[outliers]['timestamp'].to_list())

    return df
```

**Layer 4: Temporal Consistency**
```python
def validate_temporal_consistency(df: pl.DataFrame) -> pl.DataFrame:
    """Validate timestamp consistency"""

    # Timestamps must be sorted
    if not df['timestamp'].is_sorted():
        raise DataError("Timestamps must be sorted")

    # No duplicate timestamps
    if df['timestamp'].is_duplicated().any():
        raise DataError("Duplicate timestamps found")

    # Check for gaps (missing bars)
    expected_frequency = self._infer_frequency(df['timestamp'])
    gaps = self._detect_gaps(df['timestamp'], expected_frequency)

    if gaps:
        logger.warning(f"Detected {len(gaps)} gaps in data",
                      gaps=gaps)

    return df
```

**Deliverables:**
- Full type hints (mypy --strict compliance)
- Comprehensive exception hierarchy
- Graceful error handling throughout
- Audit logging system (structured logs)
- Trade-by-trade logging
- Multi-layer data validation
- Security best practices documentation
- Reliability testing suite

**Resource Requirements:**
- Core Developer (full-time)
- Security Specialist (consultant)
- QA Engineer (part-time)

---

## 🔥 Critical Success Factors

### 1. Decimal Arithmetic Implementation (Highest Priority)
- **Why Critical:** Financial accuracy, audit compliance, prevents costly bugs
- **Challenge:** 100x performance degradation vs float
- **Mitigation:** Rust implementation for hot paths
- **Timeline:** Months 4-9 (6 months dedicated effort)

### 2. Test Coverage ≥90%
- **Why Critical:** Safe refactoring, regression prevention, confidence in changes
- **Strategy:** Write tests first, enforce coverage in CI/CD
- **Focus Areas:** Financial calculations, order execution, data integrity

### 3. Active Community Engagement
- **Why Critical:** Attract contributors, get feedback, build ecosystem
- **Actions:** Contribute to zipline-reloaded, engage on GitHub/Discord
- **Goal:** 10 contributors in Year 1, 1000 stars

### 4. Performance Monitoring
- **Why Critical:** Prevent performance regressions
- **Strategy:** Benchmark suite in CI/CD, track metrics over time
- **Targets:** <50% slowdown with Decimal, 10-100x speedup with Rust

### 5. Documentation Excellence
- **Why Critical:** Adoption, contribution, support reduction
- **Components:** API docs, tutorials, examples, architecture guide
- **Standard:** Every public function documented, every feature has example

---

## ⚠️ Risk Register

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Decimal performance too slow | High | High | Rust Decimal from start, profile early |
| Zipline-reloaded abandoned | High | Low | Build relationship with maintainer, prepare for independent fork |
| Scope creep | Medium | High | Strict prioritization, MVP approach |
| Rust integration complexity | Medium | Medium | Start small, use PyO3, comprehensive testing |
| Live trading bugs | **CRITICAL** | Medium | Extensive testing, paper trading phase, circuit breakers |
| Insufficient contributors | Medium | Medium | Community building, good documentation, responsive maintainers |
| Cloud costs | Low | Medium | Start local, scale gradually, monitor spending |

---

## 💰 Budget Estimate (2-Year Timeline)

**Team Costs (assuming full-time equivalent):**
- Core Developer: $200k/year × 2 years = $400k
- Rust Developer: $180k/year × 1.5 years = $270k
- QA Engineer: $120k/year × 0.5 FTE × 2 years = $120k
- DevOps Engineer: $140k/year × 0.25 FTE × 2 years = $70k
- **Total Team: $860k**

**Infrastructure:**
- Cloud compute (testing, CI/CD): $500/month × 24 = $12k
- Data providers (Polygon, etc.): $200/month × 24 = $4.8k
- Tools & Services: $1k/year × 2 = $2k
- **Total Infrastructure: $18.8k**

**Contingency (20%): $175.8k**

**Total 2-Year Budget: ~$1.05M**

---

## 📊 Metrics Dashboard (Track Progress)

**Development Metrics:**
- Lines of code (Python, Rust)
- Test coverage (overall, financial modules)
- Open issues / PRs
- Commit frequency

**Performance Metrics:**
- Backtest execution time (baseline vs current)
- Memory usage
- Decimal arithmetic overhead

**Quality Metrics:**
- Bug count (open, closed)
- Security vulnerabilities
- Documentation completeness

**Community Metrics:**
- GitHub stars
- Contributors
- Issues/PRs from community
- Downloads

---

## 🎯 Immediate Next Steps (Month 1)

1. **Fork zipline-reloaded** ✅
2. **Set up development environment** (Python 3.11+)
3. **Run test suite** (verify 88.26% baseline)
4. **Create GitHub repository** (public or private)
5. **Set up CI/CD** (GitHub Actions)
6. **Write project README** (introduce your fork)
7. **Design Decimal arithmetic approach** (Python vs Rust)
8. **Prototype Polars/Parquet catalog** (proof of concept)
9. **Engage zipline-reloaded community** (introduce your fork)
10. **Recruit team members** (if not solo)

---

## 📚 Key Resources

**Zipline-Reloaded:**
- Docs: https://zipline.ml4trading.io/
- GitHub: https://github.com/stefan-jansen/zipline-reloaded
- Stefan Jansen's Book: "Machine Learning for Algorithmic Trading"

**Rust + Python:**
- PyO3: https://pyo3.rs/
- rust-decimal: https://docs.rs/rust_decimal/

**Financial Engineering:**
- "Advances in Financial Machine Learning" (Marcos López de Prado)
- "Algorithmic Trading" (Ernie Chan)

**Testing:**
- Hypothesis (property-based): https://hypothesis.readthedocs.io/
- pytest: https://docs.pytest.org/

**Data Tools:**
- Polars: https://pola-rs.github.io/polars/
- PyArrow: https://arrow.apache.org/docs/python/

---

## 🎉 Conclusion

You have a clear, implementation-ready roadmap for building an enhanced Python/Rust trading platform by forking Zipline-Reloaded. The plan prioritizes:

1. ✅ **Financial integrity** (Decimal arithmetic)
2. ✅ **Modern foundation** (active maintenance, Python 3.9-3.12)
3. ✅ **Performance** (strategic Rust integration)
4. ✅ **Production-grade** (testing, security, reliability)
5. ✅ **Extensibility** (data sources, strategies, analytics)

**Your platform will differentiate through:**
- Decimal precision (unique in open-source trading platforms)
- Python + Rust performance
- Modern architecture (Polars/Parquet)
- RESTful API + WebSockets
- Comprehensive testing (90%+ coverage)
- Active development

**Timeline:** 33 months (2.75 years) to fully production-ready platform
**MVP:** 12 months (Phases 1-3: Foundation + Decimal + Data)

---

*Session facilitated using the BMAD-METHOD™ brainstorming framework*
