# RustyBT Product Requirements Document (PRD)

**Version:** 1.0
**Date:** 2025-09-30
**Author:** PM John
**Status:** Ready for Architecture

---

## Goals and Background Context

### Goals

- Deliver financial-grade Decimal arithmetic throughout the platform to eliminate float rounding errors and ensure audit-compliant financial accuracy
- Build unified data catalog with intelligent local caching enabling instant retrieval for repeated backtests using the same data
- Enable production-grade live trading with 5+ direct broker integrations and seamless backtest-to-live transition with >99% behavioral correlation
- Achieve comprehensive temporal isolation guarantees preventing lookahead bias and data leakage
- Provide strategic Rust performance optimization targeting <30% overhead vs. float baseline through profiling-driven optimization of bottlenecks (Decimal arithmetic, loops, subprocesses, data processing)

### Background Context

RustyBT addresses critical gaps in existing Python backtesting frameworks that prevent production deployment. Current tools like Zipline and Backtrader use float for financial calculations, creating audit-compliance issues and materially incorrect results. They also lack rigorous temporal isolation guarantees, use obsolete data architectures (HDF5), and provide minimal live trading support. By forking Zipline-Reloaded's stable foundation (88.26% test coverage) and implementing 10 core functional enhancements across 3 implementation tiers, RustyBT bridges the gap between academic backtesting tools and production-ready live trading systems.

The platform targets individual quantitative traders and small teams requiring audit-compliant accuracy, fast iteration cycles with cached data, and self-hosted deployment without vendor lock-in. Development follows milestone-driven progress organized by implementation complexity rather than arbitrary timelines.

### Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2025-09-30 | 1.0 | Initial PRD draft | PM John |

---

## MVP Scope

The Minimum Viable Product (MVP) focuses on validating the core value proposition: financial-grade Decimal arithmetic + intelligent caching + modern data architecture + professional-grade optimization and transaction cost modeling.

**MVP = Epics 1-5**:
- **Epic 1**: Foundation & Core Infrastructure
- **Epic 2**: Financial Integrity - Decimal Arithmetic
- **Epic 3**: Modern Data Architecture (CCXT + YFinance + CSV adapters)
- **Epic 4**: Enhanced Transaction Costs & Multi-Strategy Portfolio
- **Epic 5**: Strategy Optimization & Robustness Testing

**MVP Delivers**:
- Functional enhanced backtester with audit-compliant Decimal arithmetic
- Intelligent caching enabling instant data retrieval for repeated backtests
- Core data sources for crypto (CCXT) and equities (YFinance) plus custom data (CSV)
- Realistic transaction cost modeling and multi-strategy support
- Comprehensive optimization and robustness testing tools
- Complete testing, examples, and documentation integrated throughout all epics

**Out of MVP Scope** (Epics 6-9):
- **Epic 6**: Live Trading Engine & Broker Integrations
- **Epic 7**: Performance Optimization - Rust Integration
- **Epic 8**: Analytics & Production Readiness
- **Epic 9**: RESTful API & WebSocket Interface (lowest priority)

**Phasing Strategy**: All epics will be implemented incrementally, but Epics 1-5 establish the validated foundation before proceeding to production deployment capabilities (Epics 6-9).

---

## Out of Scope

The following are explicitly excluded from this PRD:

- **Mobile applications** (iOS, Android native apps)
- **Desktop GUI application** (native windowed interface)
- **Cloud-hosted SaaS offering** (managed hosting, multi-tenancy)
- **Pre-built trading strategies or alpha generation** (users build their own strategies)
- **Social trading / strategy marketplace** (sharing or selling strategies)
- **Automated strategy discovery or ML-based strategy generation** (users design strategies manually)
- **Portfolio optimization beyond capital allocation** (no AI/ML-based portfolio optimization)
- **Algorithmic execution optimization** (smart order routing, TWAP/VWAP, etc.)
- **Backtesting web dashboard** (focus on Jupyter notebooks and programmatic reports)

---

## Requirements

### Functional Requirements

1. **FR1**: The platform SHALL implement financial-grade Decimal arithmetic throughout all calculation modules (portfolio value, position sizing, order execution, performance metrics, data pipelines) with configurable precision per data provider specifications

2. **FR2**: The platform SHALL provide a unified data catalog using Polars/Parquet with intelligent local caching that stores price data by backtest, enabling instant retrieval (<1 second) for subsequent backtests using the same data

3. **FR3**: The platform SHALL support comprehensive order types including Market, Limit, Stop-Loss, Stop-Limit, Trailing Stop, OCO (One-Cancels-Other), and Bracket orders with full lifecycle management

4. **FR4**: The platform SHALL provide live trading engine with direct broker integrations for at least 5 major brokers including Interactive Brokers, Binance, Bybit, and CCXT-supported exchanges

5. **FR5**: The platform SHALL support paper trading mode with simulated broker using real market data, realistic latency simulation, and partial fill modeling

6. **FR6**: The platform SHALL implement state management system for live trading with save/restore on shutdown/startup, crash recovery, and position reconciliation with broker

7. **FR7**: The platform SHALL provide data source adapters including extensible adapter framework for data API providers (e.g., Polygon, Alpaca, Alpha Vantage), CCXT (crypto exchanges), YFinance (stocks/ETFs/forex), CSV (custom data import), and WebSocket (real-time streaming)

8. **FR8**: The platform SHALL support multi-resolution time series data from sub-second to monthly bars with automatic aggregation and OHLCV relationship validation

9. **FR9**: The platform SHALL implement realistic transaction cost modeling including latency simulation, partial fills based on volume, multiple slippage models (volume-share, fixed bps, bid-ask spread), tiered commission models, borrow costs for shorts, and overnight financing for leveraged positions

10. **FR10**: The platform SHALL provide multi-strategy portfolio management supporting concurrent strategies with capital allocation algorithms (Fixed, Dynamic, Risk-Parity, Kelly Criterion, Drawdown-Based), cross-strategy risk management, and order aggregation

11. **FR11**: The platform SHALL implement parameter search algorithms including Grid Search, Random Search, Bayesian Optimization, and Genetic Algorithm with parallel processing support

12. **FR12**: The platform SHALL provide robustness testing and validation tools including walk-forward optimization framework (supporting any search algorithm for time-series train/validation/test), parameter sensitivity/stability analysis, and Monte Carlo simulation with data permutation and noise infusion

13. **FR13**: The platform SHALL implement scheduled calculations for live trading with market open/close triggers, custom time-based triggers, and flexible scheduling expressions

14. **FR14**: The platform SHALL provide advanced performance metrics including returns, Sharpe ratio, Sortino ratio, Calmar ratio, maximum drawdown, VaR, CVaR, win rate, profit factor, and performance attribution

15. **FR15**: The platform SHALL implement comprehensive audit logging with structured logs (JSON format) capturing trade-by-trade tracking, strategy decisions, and system events in searchable format

16. **FR16**: The platform SHALL guarantee temporal isolation as a system-wide constraint across all modules (data access, calculations, validations) with strict timestamp validation, forward-looking data prevention, and comprehensive lookahead bias detection tests

17. **FR17**: The platform SHALL provide RESTful API (FastAPI) with endpoints for strategy execution, portfolio queries, order management, performance metrics, and data catalog access with authentication and rate limiting, enabling remote monitoring and multi-user team workflows

18. **FR18**: The platform SHALL provide WebSocket API for real-time updates including live portfolio changes, trade notifications, order fill confirmations, and market data streaming for production deployment monitoring

### Non-Functional Requirements

1. **NFR1**: The platform SHALL achieve ≥90% overall test coverage and ≥95% coverage for financial calculation modules, maintaining or improving the forked Zipline-Reloaded baseline of 88.26%

2. **NFR2**: The platform SHALL complete typical backtests (2 years daily data, 50 assets, moderate complexity strategy) with acceptable performance *(target subject to baseline profiling)*

3. **NFR3**: The platform SHALL achieve Decimal arithmetic performance with <30% overhead vs. float-based baseline through strategic Rust optimization of profiled bottlenecks *(target subject to baseline profiling)*

4. **NFR4**: The platform SHALL demonstrate >99% behavioral correlation between backtest mode and paper trading mode for identical strategies (accounting for realistic slippage/commissions)

5. **NFR5**: The platform SHALL achieve zero financial calculation rounding errors as validated by property-based testing (Hypothesis framework)

6. **NFR6**: The platform SHALL support Python 3.12+ with type safety enforced via mypy --strict compliance across the codebase

7. **NFR7**: The platform SHALL achieve 99.9% uptime for live trading engine excluding planned maintenance, with graceful error handling and recovery strategies

8. **NFR8**: The platform SHALL complete walk-forward optimization with reasonable performance for production use *(target subject to baseline profiling)*

9. **NFR9**: The platform SHALL implement multi-layer data validation including schema validation, OHLCV relationship checks, outlier detection, and temporal consistency verification

10. **NFR10**: The platform SHALL provide comprehensive documentation including 100% public API documentation, 30+ tutorial examples, and architecture guide

11. **NFR11**: The platform SHALL support self-hosted deployment with no vendor lock-in, no cloud dependencies for core functionality, and full local development capability

12. **NFR12**: The platform SHALL implement security best practices including credential encryption, input sanitization, API key management, and rate limiting to prevent abuse

---

## Technical Assumptions

### Repository Structure: Monorepo

RustyBT will use a **Monorepo** structure containing:
- Python package (rustybt core)
- Rust performance modules (optional, added post-profiling)
- Documentation and examples
- Integration tests

**Rationale**: Monorepo simplifies dependency management between Python and Rust components, enables atomic cross-component changes, and provides unified CI/CD. Given the tight integration between Python and Rust optimization layers, separate repositories would create versioning complexity.

### Service Architecture

**Monolithic Python Library with Optional Rust Extensions**

The platform is fundamentally a Python library (not a service) with optional Rust-optimized modules for performance-critical paths identified through profiling.

**Rationale**:
- Target users (individual traders, small teams) prefer local development and self-hosted deployment
- Library architecture maintains flexibility - users can embed in Jupyter notebooks, scripts, or build services on top
- Rust integration via PyO3 remains seamless within monorepo structure
- Aligns with "Python-first philosophy" from brief (Rust only for profiled bottlenecks)

### Testing Requirements

**Comprehensive Testing Pyramid with Property-Based Testing**

Testing, examples, and documentation creation are integrated throughout all epics, not isolated in a single epic:

- **Unit Tests**: ≥90% overall coverage, ≥95% for financial modules (pytest)
- **Property-Based Tests**: Financial calculations validated with Hypothesis framework
- **Integration Tests**: End-to-end backtest scenarios, broker integration tests with paper accounts
- **Regression Tests**: Performance benchmarking to prevent degradation
- **Temporal Isolation Tests**: Lookahead bias detection, forward-looking data prevention

**Rationale**: Given the financial nature and live trading risk, comprehensive testing is non-negotiable. Property-based testing is critical for Decimal arithmetic validation. High coverage inherits from Zipline-Reloaded's 88.26% foundation.

### Additional Technical Assumptions and Requests

**Core Technologies** (from brief's Technology Stack):

- **Python**: 3.12+ required (modern type hints, performance improvements, structural pattern matching)
- **Polars**: 1.x latest for data catalog (5-10x faster than Pandas, lazy evaluation, parallel execution)
- **Rust**: 1.90+ stable channel (only after profiling identifies bottlenecks)
- **PyO3**: 0.26+ for Python/Rust bindings (supports Python 3.12-3.14 including free-threaded)
- **rust-decimal**: 1.37+ for high-precision Decimal arithmetic in Rust
- **Parquet**: Columnar storage format (50-80% smaller than HDF5, better interoperability)
- **SQLite**: Embedded metadata catalog (zero-config, production-proven)

**Data & Broker Integration Libraries**:

- **Data Sources**: CCXT v4.x+, yfinance, Polygon.io (optional), Alpaca (optional), Alpha Vantage (optional)
- **Broker Libraries**: Select per FR4 based on complexity/flexibility/speed tradeoff:
  - **Interactive Brokers**: ib_async (if most efficient) OR custom REST/WebSocket
  - **Binance**: binance-connector 3.12+ (official) OR custom if faster
  - **Bybit**: pybit (official SDK) OR custom implementation
  - **Hyperliquid**: hyperliquid-python-sdk (official) OR custom
  - **CCXT**: v4.x+ for broad exchange coverage (100+ exchanges)
  - **Decision Criteria**: Prioritize native/official libraries when efficient; use custom API code when simpler/faster for execution speed

**API & Web** (Optional, Epic 9):

- **FastAPI**: REST API framework (async, OpenAPI auto-generation)
- **WebSocket**: Standard library or FastAPI WebSocket support for real-time updates
- **No web dashboard**: Focus on Jupyter notebook integration, programmatic reports (matplotlib/seaborn), optional Streamlit if user demand emerges

**Testing & Quality Tools**:

- **pytest**: Testing framework
- **Hypothesis**: Property-based testing for financial calculations
- **mypy**: Static type checking (--strict mode compliance)
- **structlog**: Structured logging (JSON format, searchable)
- **Ray**: Distributed computing for parallel optimization
- **Coverage.py**: Code coverage tracking

**Development & CI/CD**:

- **GitHub Actions**: CI/CD pipeline (free for open-source)
- **maturin**: Rust/Python build tool for PyO3 integration
- **Docker**: Optional for deployment containerization

**Development Philosophy**:

- **Python-First**: Pure Python implementation initially; Rust only for profiled bottlenecks (don't optimize prematurely)
- **Fork Foundation**: Zipline-Reloaded provides 88.26% test coverage baseline and clean architecture
- **Self-Hosted**: No cloud dependencies for core functionality, full local development capability
- **Type Safety**: mypy --strict compliance across codebase
- **Financial Integrity First**: Decimal arithmetic and temporal isolation are foundational, not afterthoughts

**Performance Optimization Strategy**:

**Philosophy**: Implement all features in Python first, profile to identify bottlenecks, then strategically reimplement hot paths in Rust.

**Process**:
1. Implement complete functionality in Python
2. Profile to identify bottlenecks consuming >5% of execution time (not limited to Decimal - includes loops, subprocesses, data processing pipelines, indicator calculations)
3. Reimplement identified hot paths in Rust using PyO3 0.26+
4. Target: <30% overhead vs. float baseline (subject to baseline profiling)
5. Benchmark suite tracks performance in CI/CD

**Rust Optimization Targets** (determined by profiling):
- Decimal arithmetic operations (if bottleneck)
- Computational loops (iteration-heavy calculations)
- Subprocess coordination (if applicable)
- Technical indicator calculations
- Data processing pipelines (aggregation, filtering, transformation)
- Any other profiled bottleneck >5% runtime

**Contingency Plan** (if Rust optimization cannot achieve <30% overhead target):
- **Option A**: Cython optimization for Python bottlenecks (easier Python/C integration, less rewrite)
- **Option B**: Pure Rust rewrite of RustyBT core with Python bindings (if Cython insufficient, complete performance overhaul)
- **Option C**: Hybrid approach (Decimal for financial calculations only, float for non-financial operations like indicators)

**Constraint from Brief**: Platform is independent (not Zipline variant), makes no commitment to API compatibility with Zipline-Reloaded.

---

## Epic List

### MVP Scope (Epics 1-5): Foundation and Core Differentiation

**Epic 1: Foundation & Core Infrastructure**
Establish project setup, fork integration, CI/CD pipeline, and enhanced backtest engine with extended order types and performance metrics - delivering a functional enhanced backtesting platform with integrated testing, examples, and documentation.

**Epic 2: Financial Integrity - Decimal Arithmetic**
Replace float with Decimal throughout all financial calculations with configurable precision, property-based testing validation, and performance baseline benchmarking. Testing, examples, and documentation integrated throughout.

**Epic 3: Modern Data Architecture - MVP Data Sources**
Implement Polars/Parquet unified data catalog with intelligent local caching, and core data source adapters: CCXT (crypto), YFinance (stocks/ETFs), CSV (custom data import). Multi-resolution support and OHLCV validation included. Testing, examples, and documentation integrated throughout.

**Epic 4: Enhanced Transaction Costs & Multi-Strategy Portfolio**
Build realistic transaction cost modeling and multi-strategy portfolio management system with capital allocation algorithms. Testing, examples, and documentation integrated throughout.

**Epic 5: Strategy Optimization & Robustness Testing**
Implement parameter search algorithms with parallel processing, walk-forward optimization framework, parameter sensitivity analysis, and Monte Carlo simulation tools. Testing, examples, and documentation integrated throughout.

---

### Out of MVP Scope (Epics 6-9): Production Deployment and Scale

**Epic 6: Live Trading Engine & Broker Integrations**
Build production-ready live trading engine with state management, scheduled calculations, paper trading mode, and direct integrations for 5+ brokers. Includes data API providers and WebSocket streaming adapters deferred from Epic 3. Testing, examples, and documentation integrated throughout.

**Epic 7: Performance Optimization - Rust Integration**
Profile Python implementation to identify bottlenecks (Decimal arithmetic, loops, subprocesses, data processing), then reimplement hot paths in Rust for performance. Target <30% overhead vs. float baseline. Testing, benchmarking, and documentation integrated throughout.

**Epic 8: Analytics & Production Readiness**
Implement Jupyter notebook integration, programmatic reporting, advanced analytics (performance attribution, risk metrics, trade analysis), comprehensive security hardening (audit logging, type safety, credential encryption), and production deployment guide. Testing and documentation integrated throughout.

**Epic 9: RESTful API & WebSocket Interface (Lowest Priority)**
Build FastAPI REST API and WebSocket interface for remote strategy execution and real-time monitoring. Optional - evaluate necessity after Epic 6 live trading validates scheduled/triggered operations sufficiency. Testing and documentation integrated throughout.

---

## Epic 1: Foundation & Core Infrastructure

**Expanded Goal**: Establish the RustyBT development foundation by forking Zipline-Reloaded, setting up comprehensive CI/CD pipeline with testing and coverage tracking, mapping the existing architecture for modification points, and extending Tier 1 features (data pipeline, backtest engine, order management, performance metrics). This epic delivers a functional enhanced backtesting platform with improved order types and metrics, providing immediate value while establishing the quality infrastructure for all subsequent development. Testing, examples, and documentation are integrated throughout.

---

### Story 1.1: Fork Repository and Establish Development Environment

**As a** developer,
**I want** to fork Zipline-Reloaded and set up a clean RustyBT development environment,
**so that** I have a stable foundation to begin implementing enhancements.

#### Acceptance Criteria

1. Zipline-Reloaded repository forked from github.com/stefan-jansen/zipline-reloaded to new RustyBT repository
2. Python 3.12+ virtual environment created with all Zipline-Reloaded dependencies installed
3. Additional dependencies installed (Polars, Hypothesis, pytest, mypy, structlog)
4. All existing Zipline-Reloaded tests pass in the forked environment (88.26% baseline coverage confirmed)
5. Git repository configured with appropriate .gitignore for Python, IDE files, and build artifacts
6. README updated with RustyBT branding and initial project description
7. Development environment setup documented in CONTRIBUTING.md

---

### Story 1.2: Configure CI/CD Pipeline

**As a** developer,
**I want** automated CI/CD pipeline with testing, linting, coverage tracking, and type checking,
**so that** code quality is enforced automatically and regressions are caught early.

#### Acceptance Criteria

1. GitHub Actions workflow created for pull request validation
2. Automated test suite execution on every commit (pytest with parallel execution)
3. Code coverage tracking configured (Coverage.py) with ≥90% threshold enforcement
4. Type checking integrated (mypy --strict mode) with failures blocking merge
5. Linting configured (ruff or pylint) with consistent code style enforcement
6. Coverage reports uploaded to Codecov or similar service for visualization
7. Build status badge added to README showing CI/CD status
8. Workflow runs successfully on Linux, macOS, and Windows environments

---

### Story 1.3: Map Existing Architecture and Identify Extension Points

**As a** developer,
**I want** comprehensive documentation of Zipline-Reloaded's architecture and identified modification points,
**so that** I understand where to implement Tier 1 enhancements without breaking existing functionality.

#### Acceptance Criteria

1. Architecture diagram created showing major modules (data, execution, performance, pipeline, trading calendar)
2. Module dependency map documented showing relationships between components
3. Extension points identified for Tier 1 features (data pipeline, order types, performance metrics)
4. Data flow documented from ingestion → storage → backtest → performance calculation
5. Test coverage map shows which modules have high coverage (safe to modify) vs. low coverage (risky)
6. Key classes and interfaces documented (TradingAlgorithm, DataPortal, Blotter, PerformanceTracker)
7. Architecture documentation saved to docs/architecture/ for architect reference

---

### Story 1.4: Extend Data Pipeline with Metadata Tracking

**As a** quantitative trader,
**I want** enhanced data bundle system with metadata tracking for data provenance,
**so that** I can trace data sources, validate data quality, and understand data lineage.

#### Acceptance Criteria

1. Metadata schema extended to track data source, fetch timestamp, version, and checksum for each bundle
2. Bundle ingestion records provenance metadata (source URL, API version, download time)
3. Data quality metadata stored (row count, date range, missing data gaps, outlier count)
4. Metadata queryable via Python API (e.g., `catalog.get_bundle_metadata('my_bundle')`)
5. Timezone handling improved with explicit UTC storage and conversion helpers
6. Gap detection implemented to identify missing trading days in continuous datasets
7. All metadata stored in SQLite catalog database with indexed queries
8. Tests validate metadata correctness for sample bundle ingestion

---

### Story 1.5: Add Advanced Order Types

**As a** quantitative trader,
**I want** support for Stop-Loss, Stop-Limit, Trailing Stop, OCO, and Bracket orders,
**so that** I can implement realistic risk management strategies in backtests.

#### Acceptance Criteria

1. Stop-Loss order type implemented with trigger price and execution logic
2. Stop-Limit order type implemented combining stop trigger with limit price
3. Trailing Stop order implemented with trailing percentage/amount logic
4. OCO (One-Cancels-Other) order type implemented with linked order cancellation
5. Bracket order type implemented (entry + stop-loss + take-profit as single unit)
6. Order state machine extended to handle all new order states (Triggered, PartiallyFilled, Canceled, Rejected)
7. Order lifecycle tests validate correct state transitions for each order type
8. Commission and slippage models apply correctly to all new order types
9. Documentation added with examples for each order type usage
10. Integration tests demonstrate realistic strategy using advanced orders (e.g., bracket order for entry with risk management)

---

### Story 1.6: Implement Additional Performance Metrics

**As a** quantitative trader,
**I want** advanced performance metrics (Sortino, Calmar, CVaR, VaR, win rate, profit factor),
**so that** I can comprehensively evaluate strategy risk-adjusted returns and robustness.

#### Acceptance Criteria

1. Sortino ratio calculated using downside deviation instead of total volatility
2. Calmar ratio calculated as annualized return / maximum drawdown
3. CVaR (Conditional Value at Risk) calculated at 95% and 99% confidence levels
4. VaR (Value at Risk) calculated at 95% and 99% confidence levels
5. Win rate calculated as percentage of profitable trades
6. Profit factor calculated as gross profits / gross losses
7. All metrics integrate into existing PerformanceTracker without breaking existing metrics
8. Performance summary report includes all new metrics alongside existing ones (Sharpe, max drawdown, returns)
9. Property-based tests validate metric calculations using Hypothesis with synthetic data
10. Documentation explains each metric with interpretation guidance

---

### Story 1.7: Enhance Backtest Engine Event System

**As a** developer,
**I want** improved event system with custom triggers and sub-second resolution support,
**so that** the engine can support high-frequency strategies and flexible event-driven logic.

#### Acceptance Criteria

1. Simulation clock extended to support millisecond and microsecond resolutions
2. Custom event triggers implementable via plugin API (e.g., `on_price_threshold`, `on_time_interval`)
3. Event priority system implemented to control event processing order within same timestamp
4. Event system maintains temporal isolation (events cannot see future data)
5. Real-time mode switching capability added for live trading preparation
6. Performance impact measured: sub-second resolution adds <10% overhead vs. daily resolution
7. Tests validate event ordering and temporal isolation with sub-second data
8. Example strategy demonstrates custom event trigger usage

---

## Epic 2: Financial Integrity - Decimal Arithmetic

**Expanded Goal**: Implement financial-grade Decimal arithmetic throughout the entire RustyBT platform, replacing all float-based calculations with configurable-precision Decimal in the core calculation engine, order execution system, performance metrics, and data pipelines. This epic establishes audit-compliant financial accuracy with zero rounding errors, validated through comprehensive property-based testing, and establishes performance baselines for future Rust optimization (Epic 7). This is the foundational differentiator that enables production deployment with financial integrity. Testing, examples, and documentation are integrated throughout.

---

### Story 2.1: Design Decimal Precision Configuration System

**As a** developer,
**I want** a configurable precision management system for Decimal arithmetic,
**so that** different asset classes (crypto, equities, forex, futures) can use appropriate precision per data provider specifications.

#### Acceptance Criteria

1. Configuration schema designed for per-asset-class precision settings (precision digits, rounding mode)
2. DecimalConfig class implemented with methods to get/set precision per asset type
3. Default precision presets provided for common cases (but configurable, not hardcoded)
4. Rounding mode options supported (ROUND_HALF_UP, ROUND_DOWN, ROUND_HALF_EVEN per Python decimal module)
5. Configuration loadable from file (YAML/JSON) or programmatically via API
6. Validation ensures precision values are reasonable (e.g., 0-18 digits)
7. Thread-safe context management for Decimal contexts in multi-threaded scenarios
8. Documentation explains precision configuration with examples for different asset classes
9. Tests validate configuration loading and context switching

---

### Story 2.2: Replace Float with Decimal in Core Calculation Engine

**As a** quantitative trader,
**I want** portfolio value, position sizing, and returns calculations to use Decimal,
**so that** my account balances and performance metrics are financially accurate with zero rounding errors.

#### Acceptance Criteria

1. Portfolio value calculation converted from float to Decimal
2. Position sizing calculations (shares/contracts from dollar allocation) converted to Decimal
3. Cash balance tracking uses Decimal throughout
4. Returns calculation (daily, cumulative) uses Decimal
5. Leverage calculations use Decimal
6. All internal calculations in PerformanceTracker converted to Decimal
7. Conversion layers implemented for external libraries expecting float (with explicit warnings)
8. Existing unit tests updated to use Decimal assertions
9. Property-based tests (Hypothesis) validate Decimal precision (e.g., sum of parts equals whole)
10. Performance baseline measured: capture execution time for typical backtest

---

### Story 2.3: Replace Float with Decimal in Order Execution System

**As a** quantitative trader,
**I want** order prices, quantities, commissions, and slippage to use Decimal,
**so that** order execution accuracy matches real-world broker precision.

#### Acceptance Criteria

1. Order price (limit price, stop price, fill price) stored and calculated as Decimal
2. Order quantity (shares/contracts) stored as Decimal
3. Commission calculations converted to Decimal
4. Slippage calculations converted to Decimal
5. Fill calculations (partial fills, average fill price) use Decimal
6. Order value calculations (price × quantity) use Decimal precision
7. All order types (Market, Limit, Stop, etc.) handle Decimal correctly
8. Blotter (order management system) uses Decimal throughout
9. Tests validate precision for fractional shares (crypto allows 0.00000001 BTC orders)
10. Property-based tests ensure commission + slippage calculations never lose precision

---

### Story 2.4: Replace Float with Decimal in Performance Metrics

**As a** quantitative trader,
**I want** all performance metrics (Sharpe, Sortino, drawdown, VaR, etc.) calculated with Decimal,
**so that** performance reporting is audit-compliant and financially accurate.

#### Acceptance Criteria

1. Sharpe ratio calculation converted to Decimal (returns, volatility, risk-free rate)
2. Sortino ratio calculation converted to Decimal (downside deviation)
3. Maximum drawdown calculation uses Decimal
4. Calmar ratio calculation uses Decimal
5. VaR and CVaR calculations use Decimal
6. Win rate, profit factor calculations use Decimal
7. Performance attribution calculations use Decimal
8. Benchmark comparison calculations use Decimal
9. All performance summary reports display Decimal values with appropriate formatting
10. Property-based tests validate metric invariants (e.g., Sharpe ratio = (return - rf) / volatility)

---

### Story 2.5: Replace Float with Decimal in Data Pipelines

**As a** quantitative trader,
**I want** price data (OHLCV) stored and processed as Decimal throughout data pipelines,
**so that** historical data maintains full precision from source to backtest execution.

#### Acceptance Criteria

1. Bundle ingestion converts incoming price data to Decimal
2. Parquet schema uses Decimal type for price columns (Open, High, Low, Close, Volume)
3. DataPortal serves price data as Decimal to algorithm
4. Adjustments (splits, dividends) calculated in Decimal
5. Pipeline API returns Decimal values for price-based factors
6. Multi-resolution aggregation (e.g., minute → daily) maintains Decimal precision
7. OHLCV relationship validation uses Decimal comparison
8. Data quality checks (outlier detection) use Decimal-safe thresholds
9. Tests validate no precision loss during ingestion → storage → retrieval roundtrip
10. Performance measured: Decimal data loading overhead vs. float baseline

---

### Story 2.6: Implement Property-Based Testing for Financial Calculations

**As a** developer,
**I want** comprehensive property-based tests using Hypothesis framework,
**so that** Decimal implementation correctness is validated across wide input ranges.

#### Acceptance Criteria

1. Hypothesis test suite created for core financial calculations
2. Portfolio value property: sum(position_values) + cash == total_portfolio_value (invariant)
3. Returns property: (end_value / start_value) - 1 == returns (consistent calculation)
4. Commission property: commission >= 0 and commission <= order_value (bounds check)
5. Drawdown property: max_drawdown <= 0 and max_drawdown >= -1.0 (valid range)
6. Decimal precision property: operations maintain configured precision without silent rounding
7. Associativity property: (a + b) + c == a + (b + c) for Decimal operations
8. Order execution property: fill_value = fill_price × fill_quantity (exact, no rounding error)
9. Tests run with Hypothesis shrinking to find minimal failing cases
10. All property-based tests pass with 1000+ generated examples per test

---

### Story 2.7: Document Performance Baselines for Rust Optimization

**As a** developer,
**I want** comprehensive performance benchmarks comparing Decimal vs. float implementations,
**so that** Epic 7 (Rust optimization) has clear targets for optimization efforts.

#### Acceptance Criteria

1. Benchmark suite created using pytest-benchmark or timeit
2. Baseline measured: typical backtest with float (pre-Epic 2)
3. Post-Decimal measured: same backtest with Decimal implementation
4. Overhead calculated: (Decimal_time / float_time - 1) × 100%
5. Per-module overhead measured: calculation engine, order execution, metrics, data pipeline
6. Memory overhead measured: Decimal vs. float memory consumption
7. Hotspot profiling performed: identify top 10 time-consuming functions with Decimal
8. Benchmark results documented in docs/performance/decimal-baseline.md
9. CI/CD integration: benchmarks run on every release to track regression
10. Target established: Epic 7 must bring overhead to <30% vs. float baseline

---

## Epic 3: Modern Data Architecture - MVP Data Sources

**Expanded Goal**: Replace Zipline-Reloaded's HDF5 storage with modern Polars/Parquet-based unified data catalog featuring intelligent local caching. Implement core data source adapters for MVP validation: CCXT (crypto exchanges), YFinance (stocks/ETFs), and CSV (custom data import). Add multi-resolution time series support with OHLCV validation. WebSocket streaming, data API providers (Polygon, Alpaca, Alpha Vantage), and additional adapters deferred to Epic 6. Testing, examples, and documentation integrated throughout.

---

### Story 3.1: Design Unified Data Catalog Architecture

**As a** developer,
**I want** architectural design for Polars/Parquet data catalog with local caching system,
**so that** implementation follows a coherent plan with clear interfaces and data flows.

#### Acceptance Criteria

1. Architecture diagram created showing catalog components (SQLite metadata, Parquet storage, Polars query layer, cache manager)
2. Data schema designed for Parquet storage (OHLCV + metadata columns with Decimal types)
3. Metadata schema designed for SQLite catalog (symbols, date ranges, resolutions, checksums, backtest linkage)
4. Caching strategy documented (two-tier: in-memory Polars DataFrame + disk Parquet)
5. Cache key design specified (how to identify "same data" across backtests)
6. Cache invalidation strategy defined (when upstream data changes detected)
7. Interface contracts defined for DataCatalog, CacheManager, DataAdapter base class
8. Migration plan documented from HDF5 to Parquet (conversion utilities)
9. Architecture documentation saved to docs/architecture/data-catalog.md
10. Design reviewed and approved before implementation begins

---

### Story 3.2: Implement Parquet Storage Layer with Metadata Catalog

**As a** quantitative trader,
**I want** price data stored in Parquet format with SQLite metadata catalog,
**so that** data storage is efficient, queryable, and interoperable with modern tools.

#### Acceptance Criteria

1. Parquet storage directory structure created (organized by symbol, resolution, date range)
2. Parquet schema implemented with Decimal types for OHLCV columns
3. SQLite metadata database created with tables for datasets, symbols, date_ranges, checksums
4. Write path implemented: OHLCV data → Parquet file + metadata entry in SQLite
5. Read path implemented: query metadata → locate Parquet files → load via Polars
6. Compression enabled (Snappy or ZSTD) for Parquet files (50-80% size reduction vs. HDF5)
7. Metadata indexing implemented for fast queries (symbol, date range, resolution)
8. Dataset versioning supported (track schema version for backward compatibility)
9. Tests validate write → read roundtrip maintains Decimal precision
10. Migration utility created to convert existing HDF5 bundles to Parquet

---

### Story 3.3: Implement Intelligent Local Caching System

**As a** quantitative trader,
**I want** intelligent caching that links price data to backtests,
**so that** subsequent backtests using the same data retrieve it instantly (<1 second) without re-fetching from API.

#### Acceptance Criteria

1. Cache metadata schema extended with backtest_id, cache_timestamp, last_accessed fields
2. Cache key generation implemented (based on symbols, date range, resolution, data source)
3. Cache lookup implemented: check if requested data exists in cache with valid checksum
4. Cache hit returns data from Parquet in <1 second for typical dataset
5. Cache miss triggers data fetch from adapter, stores in cache with backtest linkage
6. Two-tier caching: hot data in-memory (Polars DataFrame), cold data on disk (Parquet)
7. Cache eviction policy implemented (LRU or size-based, configurable max cache size)
8. Cache statistics tracked (hit rate, miss rate, storage size) and queryable via API
9. Tests validate cache hit/miss scenarios and performance targets
10. Documentation explains caching behavior and configuration options

---

### Story 3.4: Implement Base Data Adapter Framework

**As a** developer,
**I want** extensible base adapter class with standardized interface,
**so that** new data sources can be integrated consistently with minimal code.

#### Acceptance Criteria

1. BaseDataAdapter abstract class created with required methods (fetch, validate, standardize)
2. Adapter interface defined: fetch(symbols, start_date, end_date, resolution) → DataFrame
3. Standardization layer implemented: convert provider-specific formats to unified OHLCV schema
4. Validation layer integrated: OHLCV relationship checks, outlier detection, temporal consistency
5. Error handling standardized across adapters (network errors, rate limits, invalid data)
6. Retry logic with exponential backoff for transient failures
7. Rate limiting support (configurable per-adapter to respect API limits)
8. Adapter registration system implemented (discover and load adapters dynamically)
9. Tests validate adapter interface compliance and error handling
10. Developer guide created for implementing new adapters

---

### Story 3.5: Implement CCXT Data Adapter (Priority: MVP - Crypto)

**As a** quantitative trader,
**I want** CCXT adapter for 100+ crypto exchanges,
**so that** I can backtest crypto strategies with data from Binance, Coinbase, Kraken, etc.

#### Acceptance Criteria

1. CCXT library integrated (v4.x+) with dependency added to requirements
2. CCXTAdapter implements BaseDataAdapter interface
3. Exchange selection supported (Binance, Coinbase, Kraken, etc. via CCXT unified API)
4. OHLCV data fetched via CCXT `fetch_ohlcv()` method
5. Multiple resolutions supported (1m, 5m, 15m, 1h, 4h, 1d)
6. Rate limiting configured per exchange (respect CCXT rate limit metadata)
7. Data standardization converts CCXT format to unified schema with Decimal precision
8. Error handling covers exchange-specific issues (maintenance, delisted pairs)
9. Integration tests fetch live data from 3+ exchanges and validate schema
10. Example notebook demonstrates crypto backtest using CCXT data

---

### Story 3.6: Implement YFinance Data Adapter (Priority: MVP - Stocks/ETFs)

**As a** quantitative trader,
**I want** YFinance adapter for free stock/ETF/forex data,
**so that** I can backtest equity strategies without requiring paid data subscriptions.

#### Acceptance Criteria

1. yfinance library integrated with dependency added to requirements
2. YFinanceAdapter implements BaseDataAdapter interface
3. Stock, ETF, forex symbol support (e.g., AAPL, SPY, EURUSD=X)
4. Multiple resolutions supported (1m, 5m, 15m, 30m, 1h, 1d, 1wk, 1mo)
5. Dividend and split data fetched separately (for adjustment calculations)
6. Data standardization converts yfinance format to unified schema with Decimal precision
7. Error handling covers invalid symbols, delisted tickers, data gaps
8. Rate limiting implemented to avoid YFinance blocking (conservative delays)
9. Integration tests fetch live data for 5+ tickers and validate schema
10. Example notebook demonstrates equity backtest using YFinance data

---

### Story 3.7: Implement CSV Data Adapter with Schema Mapping (Priority: MVP)

**As a** quantitative trader,
**I want** flexible CSV import with custom schema mapping,
**so that** I can use proprietary or custom data sources not available via APIs.

#### Acceptance Criteria

1. CSVAdapter implements BaseDataAdapter interface
2. Schema mapping configuration supported (map CSV columns to OHLCV fields)
3. Date parsing flexible (multiple formats supported: ISO8601, MM/DD/YYYY, epoch timestamps)
4. Delimiter detection (comma, tab, semicolon, pipe)
5. Header row handling (with or without headers, custom header names)
6. Data type inference with Decimal conversion for price columns
7. Timezone specification supported (convert to UTC internally)
8. Missing data handling (skip rows, interpolate, or fail based on configuration)
9. Tests validate various CSV formats (different delimiters, date formats, missing headers)
10. Example CSV files provided with documentation showing supported formats

---

### Story 3.8: Implement Multi-Resolution Aggregation with OHLCV Validation

**As a** quantitative trader,
**I want** automatic aggregation from high-resolution to low-resolution data with validation,
**so that** I can use 1-minute data to generate daily bars with confidence in accuracy.

#### Acceptance Criteria

1. Aggregation functions implemented (minute → hourly, hourly → daily, daily → weekly/monthly)
2. OHLCV aggregation logic: Open=first, High=max, Low=min, Close=last, Volume=sum
3. OHLCV relationship validation post-aggregation (High ≥ Low, High ≥ Open/Close, Low ≤ Open/Close)
4. Timezone handling during aggregation (align to trading session boundaries, not calendar days)
5. Gap detection during aggregation (warn if missing data would make aggregation unreliable)
6. Performance optimized using Polars lazy evaluation and parallel aggregation
7. Validation detects outliers (price spikes >3 standard deviations flagged for review)
8. Temporal consistency checks (timestamps sorted, no duplicates, no future data)
9. Tests validate aggregation accuracy with known-correct examples
10. Property-based tests ensure aggregation invariants (e.g., aggregated volume == sum of source volumes)

---

## Epic 4: Enhanced Transaction Costs & Multi-Strategy Portfolio

**Expanded Goal**: Implement realistic transaction cost modeling including latency simulation, partial fills based on volume, multiple slippage models, tiered commission structures, borrow costs for short selling, and overnight financing for leveraged positions. Build multi-strategy portfolio management system supporting concurrent strategies with capital allocation algorithms (Fixed, Dynamic, Risk-Parity, Kelly Criterion, Drawdown-Based), cross-strategy risk management, and order aggregation, enabling professional-grade backtesting and multi-strategy live trading. Testing, examples, and documentation integrated throughout.

---

### Story 4.1: Implement Latency Simulation

**As a** quantitative trader,
**I want** realistic latency simulation (network + broker + exchange),
**so that** backtests account for order submission delays and reflect live trading conditions.

#### Acceptance Criteria

1. Latency model configurable (fixed, random distribution, or historical latency data)
2. Network latency component simulated (e.g., 5-50ms based on geographic distance)
3. Broker processing latency simulated (e.g., 1-10ms for order validation and routing)
4. Exchange matching latency simulated (e.g., 0.1-5ms for order matching)
5. Total latency applied to order submission: order_submission_time + latency = actual_execution_time
6. Price movement during latency period affects fill price (market orders filled at price after latency)
7. Configuration API allows per-broker latency profiles
8. Tests validate latency impact on order execution timing and fill prices
9. Performance overhead measured: latency simulation adds <5% to backtest time
10. Documentation explains latency configuration with realistic examples per broker type

---

### Story 4.2: Implement Partial Fill Model

**As a** quantitative trader,
**I want** partial fill simulation based on order size vs. available volume,
**so that** backtests reflect reality of large orders that cannot be fully filled immediately.

#### Acceptance Criteria

1. Volume-based partial fill logic: if order_size > available_volume × fill_ratio, partially fill
2. Fill ratio configurable (e.g., can fill up to 10% of bar's volume without impact)
3. Multi-bar fill simulation: unfilled portion persists to next bar(s) until fully filled or timeout
4. Order state tracking for partial fills (PartiallyFilled state, cumulative fill quantity)
5. Average fill price calculated across multiple partial fills
6. Market impact modeled: larger orders relative to volume get worse average prices
7. Configuration supports different fill models (aggressive: fill more quickly, conservative: fill slower)
8. Tests validate partial fill behavior with large orders in low-volume scenarios
9. Integration test demonstrates realistic partial fill across multiple bars
10. Documentation explains partial fill logic and configuration options

---

### Story 4.3: Implement Multiple Slippage Models

**As a** quantitative trader,
**I want** multiple slippage models (volume-share, fixed bps, bid-ask spread),
**so that** I can choose the most appropriate model for different markets and strategies.

#### Acceptance Criteria

1. VolumeShareSlippage model: slippage = f(order_size / bar_volume) × volatility
2. FixedBasisPointSlippage model: slippage = price × fixed_bps (e.g., 0.05% = 5 bps)
3. BidAskSpreadSlippage model: slippage = spread / 2 for market orders crossing spread
4. CustomSlippage base class for user-defined models
5. Slippage applied directionally: buy orders slip upward, sell orders slip downward
6. Configuration API allows per-asset or per-strategy slippage model selection
7. Slippage affects fill price: fill_price = quoted_price ± slippage
8. Tests validate each slippage model with known inputs/outputs
9. Property-based tests ensure slippage always worsens execution (never improves)
10. Documentation compares models with guidance on when to use each

---

### Story 4.4: Implement Tiered Commission Models

**As a** quantitative trader,
**I want** tiered commission structures (per-share, percentage, maker/taker for crypto),
**so that** backtests accurately reflect broker fee schedules including volume discounts.

#### Acceptance Criteria

1. PerShareCommission model: fee = shares × rate_per_share (e.g., $0.005/share)
2. PercentageCommission model: fee = trade_value × percentage (e.g., 0.1%)
3. TieredCommission model: fee varies by cumulative monthly volume (volume discounts)
4. MakerTakerCommission model: different rates for maker (add liquidity) vs. taker (take liquidity) orders
5. MinimumCommission enforced: fee = max(calculated_fee, minimum_fee)
6. Commission configuration per broker (load from broker profile configs)
7. Commission tracking accumulated for tier calculations (monthly volume resets)
8. All commissions calculated using Decimal for precision
9. Tests validate each commission model with realistic broker fee schedules
10. Documentation includes examples from major brokers (Interactive Brokers, Binance, etc.)

---

### Story 4.5: Implement Borrow Cost Model for Short Selling

**As a** quantitative trader,
**I want** borrow cost simulation for short positions,
**so that** backtests account for stock borrow fees that impact short strategy profitability.

#### Acceptance Criteria

1. BorrowCostModel calculates daily interest on short position value
2. Borrow rate configurable per asset (easy-to-borrow: 0.3%, hard-to-borrow: 5-50%+)
3. Borrow cost accrues daily and debits from cash balance
4. Borrow rate lookup supports external data sources (e.g., CSV with symbol → rate mapping)
5. Default borrow rate applied when specific rate unavailable
6. Borrow cost tracked separately in performance reporting (itemized cost breakdown)
7. Tests validate daily accrual calculation accuracy using Decimal arithmetic
8. Integration test demonstrates short strategy with borrow costs over extended period
9. Property-based test ensures borrow cost always reduces short position profitability
10. Documentation explains borrow cost impact with example calculations

---

### Story 4.6: Implement Overnight Financing for Leveraged Positions

**As a** quantitative trader,
**I want** overnight financing cost/credit for leveraged positions (margin interest, swap rates),
**so that** backtests reflect carrying costs of leveraged strategies.

#### Acceptance Criteria

1. OvernightFinancingModel calculates daily financing on leveraged exposure
2. Long leverage: pays interest (debit from cash)
3. Short leverage in forex/crypto: may pay or receive interest (swap rates)
4. Financing rate configurable (e.g., broker margin rate: 5% annualized)
5. Daily accrual calculation: exposure × rate / 365 (or 360 for some markets)
6. Financing applied at end-of-day (or rollover time for forex/crypto)
7. Financing tracked separately in performance reporting
8. Tests validate daily accrual for long and short leveraged positions
9. Integration test demonstrates leveraged strategy with financing costs
10. Documentation explains financing mechanics for different asset classes

---

### Story 4.7: Implement Portfolio Allocator for Multi-Strategy Management

**As a** quantitative trader,
**I want** portfolio allocator supporting multiple concurrent strategies,
**so that** I can run diversified strategy portfolios with sophisticated capital allocation.

#### Acceptance Criteria

1. PortfolioAllocator class manages multiple Strategy instances concurrently
2. Capital allocation to each strategy tracked and enforced
3. Strategy isolation: each strategy operates on its allocated capital independently
4. Portfolio-level cash management: aggregate cash across strategies
5. Strategy performance tracked individually (per-strategy returns, drawdowns, metrics)
6. Portfolio-level performance aggregated (combined returns, diversification benefit)
7. Rebalancing support: reallocate capital between strategies based on performance
8. Strategy start/stop control (add/remove strategies dynamically during live trading)
9. Tests validate multi-strategy execution with capital allocation enforcement
10. Example demonstrates 3-strategy portfolio (long equity, short equity, market-neutral)

---

### Story 4.8: Implement Capital Allocation Algorithms

**As a** quantitative trader,
**I want** multiple capital allocation algorithms (Fixed, Dynamic, Risk-Parity, Kelly, Drawdown-Based),
**so that** I can optimize portfolio capital distribution across strategies.

#### Acceptance Criteria

1. FixedAllocation: static percentage per strategy (e.g., 30% / 40% / 30%)
2. DynamicAllocation: adjust based on recent performance (winners get more capital)
3. RiskParityAllocation: allocate inversely proportional to strategy volatility (equal risk contribution)
4. KellyCriterionAllocation: allocate based on expected return / variance (optimal growth)
5. DrawdownBasedAllocation: reduce allocation to strategies in drawdown, increase to recovering strategies
6. Allocation constraints enforced (min/max per strategy, sum = 100%)
7. Rebalancing frequency configurable (daily, weekly, monthly)
8. All allocations calculated using Decimal precision
9. Tests validate each algorithm with synthetic strategy performance data
10. Documentation explains each algorithm with mathematical formulas and use cases

---

### Story 4.9: Implement Cross-Strategy Risk Management

**As a** quantitative trader,
**I want** portfolio-level risk limits and correlation-aware position sizing,
**so that** I can control aggregate risk across multiple strategies.

#### Acceptance Criteria

1. Portfolio-level position limits (max total leverage, max single asset exposure)
2. Correlation-aware sizing: reduce allocation when strategies are highly correlated
3. Drawdown limits: halt all strategies if portfolio drawdown exceeds threshold (e.g., -15%)
4. Volatility targeting: adjust strategy allocations to maintain target portfolio volatility
5. Concentration limits: max exposure to single asset across all strategies
6. Risk limit violations trigger alerts and optionally halt trading
7. Risk metrics calculated in real-time (portfolio beta, VaR, correlation matrix)
8. Tests validate risk limit enforcement with simulated limit violations
9. Integration test demonstrates risk limits preventing excessive drawdown
10. Documentation explains risk management configuration and best practices

---

### Story 4.10: Implement Order Aggregation Across Strategies

**As a** quantitative trader,
**I want** intelligent order aggregation that nets positions across strategies,
**so that** I minimize transaction costs by combining offsetting orders before execution.

#### Acceptance Criteria

1. Order aggregation engine collects orders from all strategies before execution
2. Netting logic: cancel offsetting orders (Strategy A buys 100, Strategy B sells 50 → net buy 50)
3. Aggregation respects order types: only compatible orders aggregated (both Market, or same limit price)
4. Order attribution maintained: track which strategies contributed to aggregated order
5. Fill allocation: distribute fills back to originating strategies proportionally
6. Commission savings from aggregation tracked and reported
7. Tests validate netting logic with various offsetting order scenarios
8. Integration test demonstrates multi-strategy portfolio with order aggregation savings
9. Property-based test ensures aggregation never increases transaction costs
10. Documentation explains aggregation rules and limitations

---

## Epic 5: Strategy Optimization & Robustness Testing

**Expanded Goal**: Implement comprehensive strategy optimization infrastructure with four parameter search algorithms (Grid Search, Random Search, Bayesian Optimization, Genetic Algorithm) and parallel processing framework. Build walk-forward optimization framework for time-series train/validation/test, parameter sensitivity/stability analysis, and Monte Carlo simulation with data permutation and noise infusion. Enable systematic strategy validation preventing overfitting and ensuring robustness. Testing, examples, and documentation integrated throughout.

---

### Story 5.1: Design Optimization Framework Architecture

**As a** developer,
**I want** architectural design for optimization framework with pluggable search algorithms,
**so that** implementation follows cohesive design with clear separation of concerns.

#### Acceptance Criteria

1. Architecture diagram showing Optimizer, SearchAlgorithm interface, ParameterSpace, ObjectiveFunction
2. Interface contracts defined for SearchAlgorithm base class (required methods: suggest, update, is_complete)
3. ParameterSpace design (support continuous, discrete, categorical parameters)
4. Parallel execution architecture designed (Ray for distributed, multiprocessing for local)
5. Result storage design (optimization history, parameter→result mapping, best parameters tracking)
6. Checkpoint/resume support designed (save/restore optimization progress)
7. Integration with backtest engine defined (how optimization runs backtests with different parameters)
8. Architecture documentation saved to docs/architecture/optimization.md
9. Design reviewed for extensibility (easy to add new search algorithms)
10. Design approved before implementation begins

---

### Story 5.2: Implement Grid Search Algorithm

**As a** quantitative trader,
**I want** exhaustive grid search over parameter space,
**so that** I can systematically explore all parameter combinations for small parameter sets.

#### Acceptance Criteria

1. GridSearchAlgorithm implements SearchAlgorithm interface
2. Parameter grid specification (discrete values per parameter: e.g., lookback=[10, 20, 30])
3. Exhaustive combination generation (Cartesian product of all parameter values)
4. Progress tracking (N/M combinations complete)
5. Early stopping optional (stop if best result plateaus)
6. Results sorted by objective function (e.g., Sharpe ratio descending)
7. Parallel execution supported (distribute grid cells across workers)
8. Tests validate complete grid coverage and result ordering
9. Example notebook demonstrates grid search on simple moving average crossover strategy
10. Documentation warns about combinatorial explosion for large parameter spaces

---

### Story 5.3: Implement Random Search Algorithm

**As a** quantitative trader,
**I want** random sampling from parameter space,
**so that** I can efficiently explore high-dimensional spaces where grid search is impractical.

#### Acceptance Criteria

1. RandomSearchAlgorithm implements SearchAlgorithm interface
2. Parameter distributions supported (uniform, log-uniform, normal, categorical)
3. Sample count configurable (e.g., 100 random samples)
4. Reproducible sampling (seed parameter for deterministic results)
5. Duplicate prevention (don't test same parameters twice)
6. Best result tracking during sampling
7. Parallel execution supported (distribute samples across workers)
8. Tests validate sampling distribution and duplicate prevention
9. Performance comparison vs. Grid Search demonstrated in documentation
10. Documentation explains when Random Search outperforms Grid Search (high dimensions)

---

### Story 5.4: Implement Bayesian Optimization Algorithm

**As a** quantitative trader,
**I want** intelligent Bayesian optimization using Gaussian Process models,
**so that** I can efficiently find optimal parameters with fewer evaluations than grid/random search.

#### Acceptance Criteria

1. BayesianOptimizer implements SearchAlgorithm interface using scikit-optimize library
2. Acquisition function configurable (Expected Improvement, Probability of Improvement, Upper Confidence Bound)
3. Prior knowledge supported (seed with known good parameters)
4. Exploration/exploitation tradeoff configurable (kappa parameter for UCB)
5. Surrogate model trained on completed evaluations to suggest next parameters
6. Convergence detection (stop when acquisition function improvement < threshold)
7. Visualization support (plot acquisition function and parameter importance)
8. Tests validate Bayesian optimization finds near-optimal parameters with <50% evaluations of grid search
9. Example demonstrates Bayesian optimization on 5-parameter strategy
10. Documentation explains Gaussian Process intuition and acquisition function selection

---

### Story 5.5: Implement Genetic Algorithm Optimization

**As a** quantitative trader,
**I want** genetic algorithm optimization inspired by natural selection,
**so that** I can explore complex parameter landscapes with crossover and mutation operators.

#### Acceptance Criteria

1. GeneticAlgorithm implements SearchAlgorithm interface using DEAP library
2. Population size configurable (e.g., 50 individuals)
3. Selection operator configurable (tournament, roulette, rank-based)
4. Crossover operator implemented (combine parameters from two parents)
5. Mutation operator implemented (randomly perturb parameters)
6. Elite preservation (keep top N individuals across generations)
7. Termination criteria (max generations, fitness plateau, or time limit)
8. Population diversity tracking (prevent premature convergence)
9. Tests validate GA finds good solutions and population evolves over generations
10. Example demonstrates GA on non-smooth objective function (where Bayesian struggles)

---

### Story 5.6: Implement Parallel Processing Framework

**As a** quantitative trader,
**I want** parallel optimization execution across multiple cores/machines,
**so that** I can achieve significant speedup for optimization campaigns.

#### Acceptance Criteria

1. ParallelOptimizer wraps SearchAlgorithm with parallel execution
2. Local parallelization using multiprocessing (utilize all CPU cores)
3. Distributed parallelization using Ray (scale across multiple machines optional)
4. Worker pool management (spawn, monitor, restart failed workers)
5. Task queue management (distribute parameter evaluations to workers)
6. Result aggregation from parallel workers (thread-safe result collection)
7. Progress monitoring (live updates of optimization progress across workers)
8. Resource limits configurable (max CPUs, max memory per worker)
9. Tests validate parallel execution produces identical results to serial (deterministic)
10. Benchmark demonstrates near-linear speedup up to available cores for typical optimization

---

### Story 5.7: Implement Walk-Forward Optimization Framework

**As a** quantitative trader,
**I want** walk-forward optimization for time-series train/validation/test,
**so that** I can validate strategy robustness and detect overfitting in temporal data.

#### Acceptance Criteria

1. WalkForwardOptimizer implements rolling or expanding window walk-forward analysis
2. Window configuration (train period, validation period, test period, step size)
3. In-sample optimization: optimize parameters on train window, validate on validation window
4. Out-of-sample testing: apply best parameters from train to test window (never seen during optimization)
5. Rolling window: fixed window size slides forward in time
6. Expanding window: train set grows, test window fixed size
7. Performance aggregation across all walk-forward windows (average Sharpe, max drawdown)
8. Parameter stability analysis: track how optimal parameters change across windows
9. Tests validate walk-forward prevents lookahead bias (test data never influences training)
10. Example demonstrates walk-forward showing parameter stability over time

---

### Story 5.8: Implement Parameter Sensitivity and Stability Analysis

**As a** quantitative trader,
**I want** sensitivity analysis showing performance variance across parameter ranges,
**so that** I can identify robust parameters vs. overfit parameters sensitive to small changes.

#### Acceptance Criteria

1. SensitivityAnalyzer varies each parameter independently while holding others constant
2. Performance surface visualization (1D/2D plots showing parameter vs. objective function)
3. Stability metric calculated: performance variance across parameter neighborhood
4. Robust parameter identification: parameters with flat performance surface = robust
5. Sensitive parameter flagging: parameters with sharp performance cliffs = likely overfit
6. Interaction analysis: detect parameter interactions (2D heatmaps)
7. Confidence intervals calculated for each parameter (bootstrap or analytical)
8. Report generation with recommendations (prefer parameters in stable regions)
9. Tests validate sensitivity analysis with synthetic functions (known stable/unstable regions)
10. Documentation explains how to interpret sensitivity plots and identify overfitting

---

### Story 5.9: Implement Monte Carlo Simulation with Data Permutation

**As a** quantitative trader,
**I want** Monte Carlo simulation with data permutation (shuffling trade order),
**so that** I can validate strategy performance isn't due to lucky trade sequencing.

#### Acceptance Criteria

1. MonteCarloSimulator runs N simulations with randomized trade sequences
2. Permutation method: shuffle trade order while preserving trade outcomes (win/loss/size)
3. Bootstrap method: resample trades with replacement to generate alternative sequences
4. Performance distribution generated across all simulations (histogram of Sharpe ratios)
5. Confidence intervals calculated (e.g., 95% CI for expected Sharpe ratio)
6. Statistical significance test: is observed performance > Nth percentile of random?
7. Tests validate permutation preserves trade statistics (same total return, different sequence)
8. Integration test demonstrates Monte Carlo on completed backtest
9. Visualization shows performance distribution vs. original backtest result
10. Documentation explains interpretation: if backtest outside 95% CI → likely robust

---

### Story 5.10: Implement Monte Carlo Simulation with Noise Infusion

**As a** quantitative trader,
**I want** Monte Carlo simulation with noise infusion (perturb price data),
**so that** I can validate strategy isn't overfit to specific historical price patterns.

#### Acceptance Criteria

1. NoiseInfusionSimulator adds synthetic noise to price data and re-runs backtest
2. Noise models supported: Gaussian noise (add random returns), bootstrap historical returns
3. Noise amplitude configurable (e.g., ±1% price perturbation per bar)
4. Temporal structure preserved (don't break autocorrelation or trend patterns completely)
5. Multiple noise realizations generated (N simulations with different noise seeds)
6. Performance distribution generated showing robustness to noisy data
7. Degradation analysis: how much does performance degrade with noise?
8. Tests validate noise infusion doesn't break OHLCV relationships or temporal ordering
9. Example demonstrates strategy robust to noise vs. strategy failing with noise
10. Documentation explains noise infusion as robustness test (like regularization in ML)

---

## Epic 6: Live Trading Engine & Broker Integrations

**Expanded Goal**: Build production-ready live trading engine with event-driven async architecture, state management (save/restore, crash recovery, position reconciliation), scheduled calculations (market triggers, custom schedules), and paper trading mode. Implement direct broker integrations for 5+ major brokers, data API provider adapters (Polygon, Alpaca, Alpha Vantage), and WebSocket streaming foundation (deferred from Epic 3). Enable seamless backtest-to-live transition with >99% behavioral correlation validated through paper trading. Testing, examples, and documentation integrated throughout.

---

### Story 6.1: Design Live Trading Engine Architecture

**As a** developer,
**I want** architectural design for event-driven live trading engine,
**so that** implementation follows production-ready patterns with clear concurrency and error handling strategies.

#### Acceptance Criteria

1. Architecture diagram showing EventLoop, OrderManager, DataFeed, BrokerAdapter, StateManager, Scheduler
2. Async/await design specified (asyncio for I/O-bound operations, threading for CPU-bound)
3. Event types defined (MarketData, OrderFill, OrderReject, ScheduledTrigger, SystemError)
4. State persistence design (what to save: strategy state, positions, orders, cash)
5. Crash recovery design (restore from last checkpoint, reconcile with broker)
6. Threading/concurrency model documented (avoid race conditions, use thread-safe queues)
7. Error handling strategy defined (retry logic, circuit breakers, graceful degradation)
8. Monitoring and alerting hooks designed (emit events for external monitoring)
9. Architecture documentation saved to docs/architecture/live-trading.md
10. Design reviewed for production readiness before implementation

---

### Story 6.2: Implement Event-Driven Async Trading Engine Core

**As a** developer,
**I want** async event loop with order management and data feed coordination,
**so that** live trading can handle real-time market data and order execution concurrently.

#### Acceptance Criteria

1. TradingEngine class with async event loop (asyncio-based)
2. Event queue implemented (prioritized queue for different event types)
3. Event dispatcher routes events to appropriate handlers (market data → strategy, order fills → portfolio)
4. OrderManager tracks active orders (submitted, pending, filled, canceled)
5. DataFeed integration (subscribe to market data, dispatch to strategy on updates)
6. Strategy execution triggers (on_data, on_order_fill, on_scheduled_event)
7. Graceful shutdown handling (cleanup resources, persist state before exit)
8. Tests validate event loop processes events in correct order
9. Performance tested: engine handles 1000+ events/second with <10ms latency
10. Example demonstrates simple live strategy responding to market data events

---

### Story 6.3: Implement State Management with Save/Restore

**As a** quantitative trader,
**I want** automatic state persistence and restore on restart,
**so that** my live trading strategies survive crashes and restarts without losing positions.

#### Acceptance Criteria

1. StateManager saves strategy state, positions, open orders, cash balance to disk (JSON or pickle)
2. State saved periodically (e.g., every 1 minute) and on shutdown
3. State restored on engine startup (load last checkpoint)
4. State includes timestamps to detect stale state (warn if state >1 hour old)
5. Position reconciliation with broker after restore (compare local state vs. broker positions)
6. Discrepancy handling (if local != broker, log warning and optionally sync to broker state)
7. Atomic state writes (use temporary file + rename to prevent corruption)
8. Tests validate save → crash → restore scenario
9. Integration test simulates crash and validates correct state restoration
10. Documentation explains state management and reconciliation process

---

### Story 6.4: Implement Position Reconciliation with Broker

**As a** quantitative trader,
**I want** automatic position reconciliation comparing local state vs. broker positions,
**so that** I can detect and resolve discrepancies before they cause trading errors.

#### Acceptance Criteria

1. Reconciliation runs on engine startup and periodically during operation (e.g., every 5 minutes)
2. Fetch positions from broker via API
3. Compare local positions vs. broker positions (symbol, quantity, side)
4. Discrepancy detection (differences flagged with severity: minor vs. critical)
5. Reconciliation strategies configurable (sync_to_broker, sync_to_local, halt_and_alert)
6. Cash balance reconciliation (compare local cash vs. broker account balance)
7. Order reconciliation (compare local pending orders vs. broker open orders)
8. Reconciliation report generated (summary of discrepancies and actions taken)
9. Tests validate reconciliation with simulated discrepancies
10. Documentation explains reconciliation logic and configuration options

---

### Story 6.5: Implement Scheduled Calculations and Triggers

**As a** quantitative trader,
**I want** flexible scheduling for strategy calculations (market open/close, custom intervals),
**so that** I can run periodic rebalancing, risk checks, or strategy signals on defined schedules.

#### Acceptance Criteria

1. Scheduler supports cron-like expressions (e.g., "0 9 30 * * MON-FRI" for market open)
2. Market event triggers (market_open, market_close, pre_market, after_hours)
3. Custom time-based triggers (every N minutes, specific times, custom cron expressions)
4. Trading calendar integration (skip non-trading days, handle holidays)
5. Timezone-aware scheduling (convert triggers to exchange local time)
6. Callback registration (strategy registers callbacks for scheduled events)
7. Missed trigger handling (if engine offline during scheduled time, handle on startup)
8. Tests validate scheduling accuracy (<1 second deviation from scheduled time)
9. Integration test demonstrates strategy with scheduled daily rebalancing
10. Documentation provides examples for common scheduling patterns

---

### Story 6.6: Implement Paper Trading Mode

**As a** quantitative trader,
**I want** paper trading mode simulating broker with real market data,
**so that** I can validate live strategy behavior before risking real capital.

#### Acceptance Criteria

1. PaperBroker implements BrokerAdapter interface mimicking real broker
2. Real-time market data consumed (via WebSocket adapters from Story 6.8)
3. Simulated order execution with realistic fills (market orders fill at current price)
4. Latency simulation applied (same as backtest latency models)
5. Partial fills simulated based on volume (same as backtest partial fill model)
6. Commission and slippage applied (same models as backtest)
7. Paper positions tracked separately (not sent to real broker)
8. Paper account balance tracked (starting capital configurable)
9. Tests validate paper trading produces expected results (matches backtest for same data)
10. Example demonstrates backtest → paper trading comparison showing >99% correlation

---

### Story 6.7: Implement Interactive Brokers Integration

**As a** quantitative trader,
**I want** Interactive Brokers integration for stocks/options/futures/forex trading,
**so that** I can deploy strategies on a professional-grade broker with global market access.

#### Acceptance Criteria

1. Decision made: use ib_async library (if most efficient) OR custom TWS API implementation (if faster)
2. IBBrokerAdapter implements BrokerAdapter interface
3. Authentication with TWS/IB Gateway (handle connection, login, session management)
4. Order submission for all asset types (stocks, options, futures, forex)
5. Order status tracking (submitted, filled, canceled, rejected)
6. Position queries (fetch current positions)
7. Account balance queries (fetch cash, buying power, margin)
8. Real-time market data subscription (via ib_async or native API)
9. Error handling (connection loss, order rejections, API errors)
10. Integration test with IB paper trading account validates order submission and fills

---

### Story 6.8: Implement WebSocket Data Adapter Foundation (Moved from Epic 3)

**As a** developer,
**I want** WebSocket adapter base class for real-time streaming data,
**so that** live trading can integrate real-time market data feeds.

#### Acceptance Criteria

1. BaseWebSocketAdapter created for real-time data streaming
2. Connection management implemented (connect, disconnect, reconnect on failure)
3. Subscription management (subscribe to symbols/channels, unsubscribe)
4. Message parsing framework (standardize exchange-specific WebSocket messages to OHLCV)
5. Buffering system implemented (accumulate ticks into OHLCV bars for configured resolution)
6. Heartbeat/keepalive handling (maintain connection, detect stale connections)
7. Error handling covers disconnections, invalid messages, rate limits
8. Example WebSocket adapter implemented for one exchange (e.g., Binance WebSocket)
9. Tests validate connection lifecycle and message parsing (using mock WebSocket server)
10. Documentation explains WebSocket adapter architecture for extension

---

### Story 6.9: Implement Data API Provider Adapter Framework (Moved from Epic 3)

**As a** quantitative trader,
**I want** adapter framework for professional data API providers (Polygon, Alpaca, Alpha Vantage),
**so that** I can use paid data services for higher quality and more comprehensive data.

#### Acceptance Criteria

1. BaseAPIProviderAdapter created extending BaseDataAdapter with authentication support
2. API key management implemented (load from environment variables or config file)
3. Polygon adapter implemented (stocks, options, forex, crypto via REST API)
4. Alpaca adapter implemented (stocks via market data API v2)
5. Alpha Vantage adapter implemented (stocks, forex, crypto via REST API)
6. Each adapter handles provider-specific authentication (API keys, OAuth if applicable)
7. Rate limiting configured per provider (respect tier limits: free vs. paid subscriptions)
8. Error handling covers authentication failures, quota exceeded, invalid symbols
9. Integration tests use test/demo API keys (documented in README)
10. Documentation explains setup for each provider with example configuration

---

### Story 6.10: Implement Binance, Bybit, Hyperliquid, and CCXT Broker Integrations

**As a** quantitative trader,
**I want** integrations for Binance, Bybit, Hyperliquid, and CCXT-supported exchanges,
**so that** I have broad exchange coverage for crypto strategies.

#### Acceptance Criteria

1. BinanceBrokerAdapter implements BrokerAdapter (using binance-connector 3.12+ OR custom API)
2. BybitBrokerAdapter implements BrokerAdapter (using pybit OR custom API)
3. HyperliquidBrokerAdapter implements BrokerAdapter (using hyperliquid-python-sdk OR custom)
4. CCXTBrokerAdapter implements BrokerAdapter (using CCXT unified API for 100+ exchanges)
5. All adapters support order submission, position queries, balance queries
6. All adapters handle exchange-specific order types and constraints
7. WebSocket integration for real-time data where available
8. Error handling for exchange-specific issues (maintenance, delisted pairs, rate limits)
9. Rate limiting per exchange (respect individual exchange limits)
10. Integration tests with testnet/demo accounts for each exchange

---

### Story 6.11: Implement Circuit Breakers and Monitoring

**As a** quantitative trader,
**I want** circuit breakers and comprehensive monitoring for live trading,
**so that** I can prevent catastrophic losses and detect issues before they escalate.

#### Acceptance Criteria

1. DrawdownCircuitBreaker halts trading if portfolio drawdown exceeds threshold (e.g., -10%)
2. DailyLossCircuitBreaker halts trading if daily loss exceeds limit
3. OrderRateCircuitBreaker prevents runaway order submission (e.g., max 100 orders/minute)
4. ErrorRateCircuitBreaker halts on repeated errors (e.g., 10 order rejections in 1 minute)
5. Manual circuit breaker (emergency stop button or API endpoint)
6. Circuit breaker state tracked (NORMAL, TRIPPED, MANUALLY_HALTED)
7. Alert system (email, SMS, webhook) when circuit breaker trips
8. Monitoring dashboard (optional Streamlit/Grafana) shows live positions, PnL, circuit breaker status
9. Tests validate circuit breakers trip correctly under adverse conditions
10. Documentation explains circuit breaker configuration and best practices for risk management

---

## Epic 7: Performance Optimization - Rust Integration

**Expanded Goal**: Profile Python implementation to identify bottlenecks consuming >5% of backtest time (not limited to Decimal arithmetic - includes loops, subprocesses, data processing, indicator calculations), then reimplement hot paths in Rust for performance. Target <30% overhead vs. float baseline (subject to profiling validation), validated through comprehensive benchmarking suite integrated into CI/CD. Testing, benchmarking, and documentation integrated throughout.

---

### Story 7.1: Profile Python Implementation to Identify Bottlenecks

**As a** developer,
**I want** comprehensive profiling of Python implementation,
**so that** I can identify the highest-impact targets for Rust optimization.

#### Acceptance Criteria

1. Profiling performed using cProfile and py-spy on representative backtests
2. Bottlenecks identified: functions consuming >5% of total execution time
3. Profiling covers typical scenarios (daily data, hourly data, minute data)
4. Hotspot report generated: top 20 time-consuming functions with call counts
5. Module-level analysis: which modules dominate runtime (calculations, data, metrics)
6. Bottleneck categories identified: Decimal arithmetic, loops, subprocesses, data processing, indicators
7. Memory profiling performed (memory_profiler): identify high-allocation functions
8. Profiling results documented in docs/performance/profiling-results.md
9. Optimization targets prioritized (highest impact first based on profile results)
10. Profiling repeated after each Rust optimization to measure impact

---

### Story 7.2: Set Up Rust Integration with PyO3

**As a** developer,
**I want** Rust project integrated with Python via PyO3 and maturin,
**so that** I can write Rust modules callable from Python seamlessly.

#### Acceptance Criteria

1. Rust project created in repository (Cargo workspace at rust/ directory)
2. PyO3 0.26+ added as dependency (supports Python 3.12-3.14)
3. maturin configured for building Python extensions from Rust
4. CI/CD updated to build Rust modules (install Rust toolchain, run maturin build)
5. Python package setup.py or pyproject.toml updated to include Rust extension
6. Example Rust function callable from Python (e.g., `rustybt.rust_sum(a, b)`)
7. Tests validate Python → Rust → Python roundtrip works correctly
8. Build documentation explains Rust setup for contributors
9. Development workflow documented (edit Rust, rebuild, test from Python)
10. Cross-platform builds tested (Linux, macOS, Windows)

---

### Story 7.3: Implement Rust-Optimized Modules for Profiled Bottlenecks

**As a** developer,
**I want** Rust reimplementation of profiled bottlenecks,
**so that** performance overhead is reduced to target levels.

#### Acceptance Criteria

1. rust-decimal 1.37+ integrated for high-precision arithmetic (if Decimal is bottleneck)
2. Rust functions implemented for identified hot-paths (based on profiling: could be Decimal operations, loops, data processing, indicators)
3. PyO3 bindings expose Rust functions to Python (seamless integration)
4. Configuration passed from Python to Rust (precision, rounding modes, parameters)
5. Benchmarks show Rust optimization achieves measurable speedup for targeted operations
6. Tests validate Rust and Python implementations produce identical results
7. Gradual rollout: make Rust optional (fallback to Python if Rust not available)
8. Documentation explains which operations use Rust optimization
9. Performance impact measured: overhead reduction per module
10. Profiling repeated to identify next optimization targets if needed

---

### Story 7.4: Validate Performance Target Achievement

**As a** developer,
**I want** validation that Rust optimizations achieve <30% overhead vs. float baseline,
**so that** we confirm Decimal viability for production use.

#### Acceptance Criteria

1. Baseline reestablished: typical backtest with pure float (pre-Epic 2) runtime
2. Post-Rust runtime measured: same backtest with Decimal + Rust optimizations
3. Overhead calculated: (Decimal+Rust_time / float_time - 1) × 100%
4. Target validated: overhead acceptable for production use
5. If target not met: profile further, identify remaining bottlenecks, iterate or activate contingency
6. Module-level overhead breakdown: calculation engine, order execution, metrics, data
7. Performance report generated comparing float baseline vs. Decimal+Rust
8. Report documented in docs/performance/rust-optimization-results.md
9. CI/CD integration: performance regression tests validate ongoing compliance with target
10. Contingency activated if target unreachable (Cython optimization → Pure Rust rewrite)

---

### Story 7.5: Implement Comprehensive Benchmarking Suite

**As a** developer,
**I want** extensive benchmark suite tracking performance across releases,
**so that** regressions are caught early and optimizations validated.

#### Acceptance Criteria

1. Benchmark scenarios covering common use cases (daily, hourly, minute strategies)
2. Benchmarks test different strategy complexities (simple SMA crossover vs. complex multi-indicator)
3. Benchmarks test different portfolio sizes (10, 50, 100, 500 assets)
4. Benchmark results stored historically (track trends over time)
5. Automated benchmark execution in CI/CD (nightly builds)
6. Performance graphs generated (execution time vs. release version)
7. Regression alerts: notify if performance degrades >5% vs. previous release
8. Benchmarks compare Python-only vs. Rust-optimized (quantify Rust benefit)
9. Memory benchmarks included (track memory usage over time)
10. Benchmark dashboard (optional Grafana/Streamlit) visualizes performance trends

---

## Epic 8: Analytics & Production Readiness

**Expanded Goal**: Implement comprehensive analytics and reporting with Jupyter notebook integration, programmatic report generation (matplotlib/seaborn), advanced performance attribution, risk analytics (VaR, CVaR, stress testing), and trade analysis. Harden security with comprehensive exception handling, structured audit logging (trade-by-trade tracking), multi-layer data validation, type safety (mypy --strict), credential encryption, and input sanitization. Deliver production deployment guide validating platform readiness for live trading with 99.9% uptime target. Testing and documentation integrated throughout.

---

### Story 8.1: Implement Jupyter Notebook Integration

**As a** quantitative trader,
**I want** seamless Jupyter notebook integration for interactive analysis,
**so that** I can explore backtest results, visualize performance, and iterate quickly.

#### Acceptance Criteria

1. Backtest results exportable to Pandas DataFrame (for compatibility with notebook tools)
2. Helper functions for common visualizations (equity curve, drawdown, returns distribution)
3. Example notebooks provided (10+ covering common workflows: backtest, optimization, analysis)
4. Notebook-friendly repr (rich display for Strategy, Portfolio, PerformanceMetrics objects)
5. Interactive plotting using plotly or bokeh (hover tooltips, zoom, pan)
6. Integration with existing notebook ecosystems (works in Jupyter Lab, VS Code notebooks, Google Colab)
7. Async execution support for long-running backtests in notebooks
8. Progress bars for backtest execution (tqdm integration)
9. Documentation explains notebook workflows and provides tutorials
10. Example notebook demonstrates full workflow: data ingestion → backtest → analysis → optimization

---

### Story 8.2: Implement Programmatic Report Generation

**As a** quantitative trader,
**I want** automated report generation with charts and metrics,
**so that** I can produce professional backtest reports without manual effort.

#### Acceptance Criteria

1. ReportGenerator class creates PDF or HTML reports
2. Report includes equity curve, drawdown chart, returns distribution histogram
3. Report includes performance metrics table (Sharpe, Sortino, max drawdown, etc.)
4. Report includes trade statistics (win rate, average win/loss, profit factor)
5. Report includes position distribution (top holdings, sector exposure if applicable)
6. Report customizable (select sections, add custom charts)
7. Report generation uses matplotlib/seaborn for charts (publication-quality)
8. Report exportable as PDF (using reportlab or matplotlib PDF backend) or HTML
9. Tests validate report generation completes without errors
10. Example demonstrates generating report for completed backtest

---

### Story 8.3: Implement Advanced Performance Attribution

**As a** quantitative trader,
**I want** performance attribution breaking down returns by source,
**so that** I can understand what drove strategy performance (skill vs. luck, factor exposures).

#### Acceptance Criteria

1. Attribution analysis decomposes returns into components (alpha, beta, factor exposures)
2. Factor exposure analysis (momentum, value, volatility, size, etc. if applicable)
3. Timing attribution (skill in entry/exit timing)
4. Selection attribution (skill in asset selection)
5. Interaction attribution (skill in combining timing and selection)
6. Attribution over time (rolling attribution windows)
7. Visualization of attribution components (stacked bar charts, time series)
8. Statistical significance testing (is alpha significant or noise?)
9. Tests validate attribution sums to total returns (accounting identity)
10. Documentation explains attribution methodology and interpretation

---

### Story 8.4: Implement Risk Analytics (VaR, CVaR, Stress Testing)

**As a** quantitative trader,
**I want** comprehensive risk analytics to understand strategy risk profile,
**so that** I can make informed decisions about position sizing and risk limits.

#### Acceptance Criteria

1. VaR (Value at Risk) calculated at 95% and 99% confidence levels (parametric, historical, Monte Carlo methods)
2. CVaR (Conditional VaR / Expected Shortfall) calculated (average loss beyond VaR threshold)
3. Stress testing: simulate extreme scenarios (2008 crisis, COVID crash, flash crash)
4. Scenario analysis: user-defined scenarios (e.g., "what if rates rise 2%?")
5. Correlation analysis: portfolio correlation matrix, factor correlation
6. Beta analysis: portfolio beta vs. benchmark (market sensitivity)
7. Tail risk metrics: skewness, kurtosis, max loss in worst N days
8. Risk decomposition: which positions contribute most to portfolio risk?
9. Tests validate risk calculations with known scenarios
10. Visualization of risk metrics (VaR distribution, stress test results)

---

### Story 8.5: Implement Trade Analysis and Diagnostics

**As a** quantitative trader,
**I want** detailed trade analysis showing entry/exit quality and patterns,
**so that** I can identify strategy weaknesses and improve execution.

#### Acceptance Criteria

1. Trade log with all trades (entry/exit time, price, PnL, duration)
2. Entry/exit quality analysis (how close to optimal entry/exit points?)
3. Holding period distribution (histogram of trade durations)
4. Win/loss distribution (histogram of trade PnLs)
5. MAE/MFE analysis (Maximum Adverse Excursion / Maximum Favorable Excursion)
6. Trade clustering analysis (are trades concentrated in time/assets?)
7. Slippage analysis (realized slippage vs. expected)
8. Commission impact analysis (how much do fees erode returns?)
9. Tests validate trade analysis with synthetic trade data
10. Visualization of trade patterns (scatter plots, heatmaps)

---

### Story 8.6: Implement Comprehensive Exception Handling

**As a** developer,
**I want** robust exception handling with custom exception hierarchy,
**so that** errors are caught gracefully and provide actionable information.

#### Acceptance Criteria

1. Custom exception hierarchy defined (RustyBTError base, specific subclasses)
2. Exception categories: DataError, OrderError, BrokerError, StrategyError, ValidationError
3. All external API calls wrapped in try/except with retries for transient errors
4. Unrecoverable errors logged and raised (don't silently fail)
5. Recoverable errors logged and handled (graceful degradation)
6. User-facing errors provide clear messages (not stack traces)
7. Developer errors provide full context (stack trace, relevant state)
8. Tests validate exception handling for various error scenarios
9. Documentation explains exception hierarchy and handling patterns
10. Error handling best practices guide for contributors

---

### Story 8.7: Implement Structured Audit Logging

**As a** quantitative trader,
**I want** comprehensive trade-by-trade audit logging in searchable format,
**so that** I can review all system actions and debug issues.

#### Acceptance Criteria

1. structlog integrated for structured logging (JSON format)
2. Trade logging: every order submission, fill, modification, cancellation logged with full details
3. Strategy decision logging: signals, reasons for trades, parameter values at decision time
4. System event logging: startup, shutdown, errors, circuit breaker trips
5. Log context includes timestamp, strategy ID, asset, order ID, user (if applicable)
6. Logs searchable (JSON format enables easy filtering with jq, grep, or log aggregation tools)
7. Log rotation configured (prevent unbounded log growth)
8. Sensitive data masked (API keys, credentials not logged)
9. Tests validate logging coverage for critical events
10. Documentation explains log format and querying examples

---

### Story 8.8: Implement Multi-Layer Data Validation

**As a** quantitative trader,
**I want** comprehensive data validation preventing invalid data from causing errors,
**so that** I can trust data quality throughout the system.

#### Acceptance Criteria

1. Layer 1 - Schema validation: correct types, required fields, value ranges (Pydantic models)
2. Layer 2 - OHLCV relationship validation: High ≥ Low, High ≥ Open/Close, Low ≤ Open/Close, Volume ≥ 0
3. Layer 3 - Outlier detection: price spikes, volume anomalies flagged for review
4. Layer 4 - Temporal consistency: timestamps sorted, no duplicates, no future data, gap detection
5. Validation runs on data ingestion (prevent bad data from entering catalog)
6. Validation runs on strategy execution (detect corrupted data before causing errors)
7. Validation errors logged with severity (ERROR for critical, WARN for suspicious)
8. Validation configurable (thresholds adjustable per asset class)
9. Tests validate each validation layer with synthetic bad data
10. Documentation explains validation layers and configuration

---

### Story 8.9: Enforce Type Safety with mypy --strict

**As a** developer,
**I want** strict type checking enforced across the codebase,
**so that** type-related bugs are caught at development time, not runtime.

#### Acceptance Criteria

1. mypy --strict enabled in CI/CD (builds fail on type errors)
2. All functions and methods have type hints (parameters and return types)
3. Type hints cover collections (List[str], Dict[str, Decimal], etc.)
4. Optional types used explicitly (Optional[int] for nullable)
5. Generic types used where applicable (TypeVar for generic functions)
6. External library stubs installed where available (types-* packages)
7. Any types eliminated or explicitly marked as intentional (# type: ignore with justification)
8. Tests validate type hints are correct (mypy passes with no errors)
9. Pre-commit hooks run mypy on changed files (catch errors before commit)
10. Documentation explains type hinting conventions and best practices

---

### Story 8.10: Create Production Deployment Guide and Validate Readiness

**As a** quantitative trader,
**I want** comprehensive deployment guide and validated production readiness,
**so that** I can deploy live trading with confidence in platform reliability.

#### Acceptance Criteria

1. Deployment guide covers environment setup (Python, Rust, dependencies)
2. Guide covers configuration (brokers, data sources, API keys, risk limits)
3. Guide covers security hardening (firewall, API authentication, credential encryption)
4. Guide covers monitoring setup (logs, alerts, dashboards)
5. Guide covers backup and disaster recovery (state persistence, restore procedures)
6. Production checklist provided (all items must pass before live trading)
7. 99.9% uptime validation: run paper trading for extended period, measure uptime and error rate
8. Performance validation: ensure production hardware meets performance requirements
9. Security audit: review code for vulnerabilities (use bandit, safety for Python)
10. Documentation includes troubleshooting guide for common deployment issues

---

## Epic 9: RESTful API & WebSocket Interface (Lowest Priority)

**Expanded Goal**: Build FastAPI REST API and WebSocket interface for remote strategy execution and real-time monitoring. **Priority: Lowest - Evaluate necessity after Epic 6 validates that scheduled/triggered operations provide sufficient live trading control. If Epic 6's scheduled calculations and live trading engine meet all operational needs, this epic may be deferred indefinitely or removed.** Testing and documentation integrated throughout.

---

### Story 9.1: Design API Architecture and Endpoints

**As a** developer,
**I want** comprehensive API design with clear endpoint specifications,
**so that** implementation follows RESTful best practices and meets user needs.

#### Acceptance Criteria

1. API architecture documented (FastAPI app structure, routing, middleware)
2. Endpoint specifications defined for strategy execution (POST /strategies, GET /strategies/{id}, DELETE /strategies/{id})
3. Endpoint specifications for portfolio queries (GET /portfolio, GET /portfolio/positions, GET /portfolio/history)
4. Endpoint specifications for order management (POST /orders, GET /orders, DELETE /orders/{id})
5. Endpoint specifications for performance metrics (GET /performance, GET /performance/metrics)
6. Endpoint specifications for data catalog (GET /catalog, GET /catalog/datasets/{id})
7. Authentication scheme defined (API keys, JWT tokens, or OAuth2)
8. Rate limiting strategy defined (per-user limits, throttling rules)
9. OpenAPI/Swagger spec generated automatically by FastAPI
10. API design documented in docs/api/rest-api-spec.md

---

### Story 9.2: Implement FastAPI REST API Core

**As a** developer,
**I want** FastAPI application with routing, middleware, and error handling,
**so that** API endpoints can be implemented against a robust foundation.

#### Acceptance Criteria

1. FastAPI application created with versioned routes (e.g., /v1/...)
2. Pydantic models defined for request/response validation
3. Error handling middleware (catch exceptions, return structured error responses)
4. CORS middleware configured (allow cross-origin requests for web clients)
5. Logging middleware (log all requests with timestamps, user, endpoint)
6. OpenAPI documentation auto-generated (Swagger UI available at /docs)
7. Health check endpoint (GET /health returns status, version, uptime)
8. Tests validate middleware functionality and error handling
9. Development server runnable (uvicorn for async FastAPI serving)
10. Documentation explains API core architecture for contributors

---

### Story 9.3: Implement Strategy Execution Endpoints

**As a** quantitative trader,
**I want** REST API endpoints to start, stop, and monitor strategies remotely,
**so that** I can control live trading from external tools or dashboards.

#### Acceptance Criteria

1. POST /strategies endpoint starts new strategy (accepts strategy code or reference)
2. GET /strategies lists all active strategies with status (running, stopped, error)
3. GET /strategies/{id} returns specific strategy details (status, parameters, PnL)
4. DELETE /strategies/{id} stops and removes strategy
5. PUT /strategies/{id}/pause pauses strategy execution
6. PUT /strategies/{id}/resume resumes paused strategy
7. Authentication required for all strategy endpoints
8. Strategy state persisted (survives API server restart)
9. Tests validate strategy lifecycle (start → pause → resume → stop)
10. Example client script demonstrates remote strategy control

---

### Story 9.4: Implement Portfolio Query Endpoints

**As a** quantitative trader,
**I want** REST API endpoints to query portfolio state (positions, cash, history),
**so that** I can monitor portfolio from external tools or build custom dashboards.

#### Acceptance Criteria

1. GET /portfolio returns portfolio summary (total value, cash, positions count, PnL)
2. GET /portfolio/positions returns all current positions (symbol, quantity, price, value)
3. GET /portfolio/history returns historical portfolio values (time series for charting)
4. Query parameters supported (date range filters, symbol filters, resolution)
5. Response format JSON with Decimal values serialized as strings (preserve precision)
6. Pagination supported for large result sets (positions, history)
7. Authentication required for all portfolio endpoints
8. Tests validate correct portfolio state returned for various scenarios
9. Performance tested: queries return in reasonable time
10. Example client demonstrates fetching portfolio and rendering chart

---

### Story 9.5: Implement Order Management Endpoints

**As a** quantitative trader,
**I want** REST API endpoints to submit, cancel, and query orders,
**so that** I can manage orders programmatically from external tools.

#### Acceptance Criteria

1. POST /orders submits new order (symbol, quantity, order type, limit price, etc.)
2. GET /orders returns all orders with status (pending, filled, canceled, rejected)
3. GET /orders/{id} returns specific order details
4. DELETE /orders/{id} cancels pending order
5. PUT /orders/{id} modifies pending order (e.g., change limit price)
6. Order validation before submission (symbol exists, quantity valid, sufficient cash)
7. Authentication required for all order endpoints
8. Tests validate order lifecycle (submit → fill/cancel → query status)
9. Integration test with paper broker validates orders submitted via API execute correctly
10. Documentation explains order submission parameters and order types

---

### Story 9.6: Implement Performance Metrics Endpoints

**As a** quantitative trader,
**I want** REST API endpoints to retrieve performance metrics,
**so that** I can analyze strategy performance from external tools or dashboards.

#### Acceptance Criteria

1. GET /performance returns performance summary (Sharpe, Sortino, max drawdown, returns, etc.)
2. GET /performance/metrics returns all available metrics (comprehensive list)
3. Query parameters support filtering (date range, strategy filter)
4. Metrics calculated on-demand or cached (configurable)
5. Benchmark comparison supported (vs. SPY, BTC, or custom benchmark)
6. Response format JSON with Decimal precision preserved
7. Authentication required for all performance endpoints
8. Tests validate correct metrics calculated for known scenarios
9. Performance tested: metrics queries return in reasonable time
10. Example client demonstrates fetching metrics and rendering report

---

### Story 9.7: Implement WebSocket API for Real-Time Updates

**As a** quantitative trader,
**I want** WebSocket API streaming real-time portfolio and trade updates,
**so that** I can monitor live trading with low latency.

#### Acceptance Criteria

1. WebSocket endpoint at /ws supports client connections
2. Authentication via token or API key on WebSocket handshake
3. Subscription model: clients subscribe to channels (portfolio_updates, trade_notifications, order_fills)
4. Portfolio updates pushed on position changes, PnL updates
5. Trade notifications pushed on every trade execution (fill events)
6. Order fill confirmations pushed immediately after broker confirmation
7. Heartbeat/keepalive messages maintain connection
8. Multi-client support (many clients can connect simultaneously)
9. Tests validate WebSocket connection lifecycle and message delivery
10. Example client demonstrates WebSocket subscription and real-time display

---

### Story 9.8: Implement Authentication and Authorization

**As a** developer,
**I want** secure authentication and role-based authorization,
**so that** API access is controlled and users can only access their own data.

#### Acceptance Criteria

1. API key authentication implemented (users obtain API keys from config/dashboard)
2. JWT token authentication implemented (alternative to API keys)
3. User management: create, list, delete users (admin-only endpoint)
4. Role-based access control: admin, user, read-only roles
5. Authorization checks on all endpoints (verify user has permission)
6. API keys stored securely (hashed, not plaintext)
7. Token expiration and refresh logic (JWT tokens expire, refresh tokens issued)
8. Tests validate authentication rejection for invalid/missing credentials
9. Tests validate authorization rejection for insufficient permissions
10. Documentation explains authentication setup and API key generation

---

### Story 9.9: Implement Rate Limiting

**As a** developer,
**I want** rate limiting to prevent API abuse,
**so that** excessive requests don't degrade service for legitimate users.

#### Acceptance Criteria

1. Rate limiting middleware implemented (e.g., slowapi or custom)
2. Per-user rate limits configurable (e.g., 100 requests/minute)
3. Per-endpoint rate limits (e.g., order submission limited to 10/minute)
4. Rate limit headers returned (X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset)
5. HTTP 429 (Too Many Requests) returned when rate limit exceeded
6. Rate limit tracking persisted (survive server restart)
7. Admin endpoints bypass rate limits (or have higher limits)
8. Tests validate rate limit enforcement
9. Configuration allows adjusting rate limits without code changes
10. Documentation explains rate limiting policy and limits

---

### Story 9.10: Implement Multi-Client Support and Load Testing

**As a** developer,
**I want** validated multi-client support under load,
**so that** API scales to production usage patterns.

#### Acceptance Criteria

1. Load testing performed with 10+ concurrent clients
2. WebSocket tested with 50+ simultaneous connections
3. API handles substantial requests without degradation
4. Response times measured under load
5. Memory and CPU usage measured under load (identify resource limits)
6. Connection pooling optimized (database, broker connections)
7. Async operations validated (ensure no blocking calls degrade throughput)
8. Load test results documented (throughput, latency, resource usage)
9. Bottlenecks identified and optimized (if any found)
10. Production deployment guide includes load testing recommendations

---

## Checklist Results Report

### Executive Summary

**Overall PRD Completeness**: 95%

**MVP Scope Appropriateness**: Just Right - MVP clearly defined as Epics 1-5, with Epics 6-9 as production deployment phase

**Readiness for Architecture Phase**: Ready - PRD is comprehensive, well-structured, with clear MVP scope and technical guidance

**Most Critical Strengths**:
1. ✅ MVP vs. Full Vision clearly separated (Epics 1-5 vs. 6-9)
2. ✅ Out-of-scope features explicitly documented
3. ✅ Rust optimization strategy clarified (profile-driven, not limited to Decimal)
4. ✅ Testing/docs distributed across all epics (not isolated)
5. ✅ Epic 9 marked as lowest priority with conditional evaluation

---

### Category Analysis Table

| Category                         | Status | Critical Issues |
| -------------------------------- | ------ | --------------- |
| 1. Problem Definition & Context  | PASS   | None - Goals and Background clearly articulate problem |
| 2. MVP Scope Definition          | PASS   | MVP = Epics 1-5, Out-of-MVP = Epics 6-9, Out-of-scope documented |
| 3. User Experience Requirements  | N/A    | Intentionally skipped (Python library, no UI) |
| 4. Functional Requirements       | PASS   | 18 FRs comprehensive, testable, refined |
| 5. Non-Functional Requirements   | PASS   | 12 NFRs with performance targets subject to profiling |
| 6. Epic & Story Structure        | PASS   | 9 epics well-structured, stories appropriately sized, ACs testable |
| 7. Technical Guidance            | PASS   | Comprehensive technical assumptions, Rust strategy clarified |
| 8. Cross-Functional Requirements | PASS   | Data, integrations, operations covered across epics |
| 9. Clarity & Communication       | PASS   | Clear language, structured, comprehensive |

---

### Final Decision

**✅ READY FOR ARCHITECT**

The PRD is comprehensive, properly structured, and ready for architectural design with:
- Clear MVP scope (Epics 1-5)
- Well-defined requirements and acceptance criteria
- Comprehensive technical guidance
- Distributed testing/documentation approach
- Clarified Rust optimization strategy (profile-driven, any bottleneck)
- Contingency plans for performance targets

**Architect should begin with Epic 1 (Foundation) design, treating Epics 1-5 as validated MVP scope.**

---

## Next Steps

### UX Expert Prompt

**Note**: UX/UI design goals were intentionally skipped as RustyBT is a Python library framework without graphical user interface. The focus is on programmatic API design, Jupyter notebook integration, and CLI usability rather than visual design.

If UX analysis is needed for developer experience (DX), Jupyter notebook workflows, or API ergonomics, the UX Expert can review this PRD focusing on:
- Python API design patterns and usability
- Jupyter notebook integration and interactive workflows
- CLI command design and documentation structure
- Error message clarity and developer guidance

### Architect Prompt

You are the Architect for RustyBT, a production-grade Python/Rust trading platform. Review the attached PRD ([docs/prd.md](docs/prd.md)) and [docs/brief.md](docs/brief.md), then design the architecture for **MVP scope (Epics 1-5)** with extensibility for Epics 6-9.

**Your tasks**:
1. Design system architecture for Epics 1-5 (Foundation, Decimal, Data Catalog, Transaction Costs, Optimization)
2. Define module structure, interfaces, and data flows
3. Specify technology integration (Polars, Parquet, SQLite, Decimal, PyO3 preparation)
4. Design data catalog with intelligent caching system
5. Plan for future extensibility (live trading, Rust optimization, APIs)
6. Identify technical risks and mitigation strategies
7. Create architecture documentation with diagrams

**Key considerations**:
- Fork Zipline-Reloaded foundation (88.26% test coverage) and extend, don't rebuild
- Python-first: Pure Python implementation, Rust only after profiling identifies bottlenecks (Epic 7)
- Temporal isolation is non-negotiable: prevent lookahead bias at architectural level
- Design for testing: Every component must be testable in isolation
- Monorepo structure: Python package + future Rust modules + docs + tests

**Start with**: Epic 1 (Foundation & Core Infrastructure) detailed design, treating it as the architectural foundation for all subsequent epics.
