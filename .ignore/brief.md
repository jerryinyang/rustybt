# Project Brief: RustyBT - Production-Grade Python/Rust Trading Platform

**Version:** 2.0
**Date:** 2025-09-30
**Author:** Business Analyst Mary
**Status:** Draft for Review

---

## Executive Summary

RustyBT is a production-grade backtesting and live trading platform forked from Zipline-Reloaded to address critical gaps in existing trading frameworks. The platform delivers financial-grade Decimal arithmetic, modern data architecture (Polars/Parquet), comprehensive live trading with direct broker integrations, and strategic Rust optimization for performance-critical operations. Development follows a milestone-driven approach organized into three implementation tiers based on required code creation/modification effort, targeting quantitative traders requiring audit-compliant financial accuracy and seamless backtest-to-live deployment.

**Key Value Proposition:** First open-source Python-native trading platform with Decimal arithmetic throughout, temporal isolation guarantees, unified data catalog with intelligent local caching, and production-ready broker integrations—bridging the gap between academic backtesting tools and live trading systems.

**Note:** RustyBT is an independent platform that happens to fork Zipline-Reloaded as a development accelerator. It is not a variant and makes no commitment to API compatibility.

---

## Problem Statement

### Current State & Pain Points

Existing Python backtesting frameworks suffer from fundamental limitations that prevent production deployment:

1. **Financial Integrity Crisis**: Both Zipline and Backtrader use Python `float` for all financial calculations, leading to rounding errors that accumulate over time. This is unacceptable for audit compliance and can produce materially incorrect results in long-running backtests or live trading. Neither framework maintainers have prioritized fixing this (Zipline Issue #56 rejected, Backtrader PR #416 never merged).

2. **Temporal Isolation Violations**: Frameworks lack rigorous guarantees against lookahead bias, data leakage, and forward-looking information contamination—producing deceptively optimistic backtest results that fail catastrophically in live trading.

3. **Data Architecture Obsolescence**: Zipline uses HDF5 for data storage, which is slow for large datasets (hours to ingest thousands of assets), lacks intelligent caching for repeated backtests, and has poor interoperability with contemporary data tools like Polars and PyArrow.

4. **Limited Live Trading**: Zipline has minimal live trading support requiring external forks. Backtrader has better live trading but was abandoned in April 2023. No framework provides production-grade broker integrations with comprehensive order types, state management, and reconciliation.

5. **Performance Bottlenecks**: Pure Python implementation creates performance limitations for complex strategies, large universes, or high-frequency simulations. Strategies with thousands of assets become impractically slow, preventing proper optimization and robustness testing.

### Impact of the Problem

- **Risk Exposure**: Float-based calculations introduce financial inaccuracies that can lead to incorrect position sizing, flawed risk management, and audit failures
- **Backtest Integrity Compromise**: Temporal isolation violations produce biased results that dramatically overestimate strategy profitability
- **Development Inefficiency**: Traders spend weeks building workarounds, custom data pipelines, and manual broker integrations rather than focusing on strategy development
- **Production Friction**: Gap between backtest and live trading environments creates dangerous discrepancies, requiring complex migration paths and extensive manual testing

### Why Existing Solutions Fall Short

**Zipline-Reloaded**: Active maintenance (v3.1.1, July 2025), superior architecture (88.26% test coverage), Python 3.12 support, but missing Decimal arithmetic, modern data layer, live trading capabilities, and performance optimization.

**Backtrader**: Better live trading support but abandoned since 2023, limited to Python 3.7 officially, unknown test coverage, and also lacks Decimal arithmetic.

**VectorBT**: Vectorized approach for speed but limited order types, no Decimal support, weak live trading integration, less focus on temporal integrity.

**QuantConnect**: Cloud-only, proprietary, expensive for serious usage ($20-400/month), vendor lock-in, limited customization.

### Urgency & Importance

The convergence of three factors creates a strategic window:

1. **Active Zipline-Reloaded Maintenance**: Stefan Jansen's continued development provides stable fork foundation with modern Python support
2. **Rust Ecosystem Maturity**: PyO3 0.26+ and rust-decimal 1.37+ provide production-ready Python/Rust integration with Python 3.12-3.14 support
3. **Market Demand**: Growing quantitative trading community needs open-source production-grade tools (evidenced by Zipline's 17k+ stars and Backtrader's 16k+ stars despite abandonment)

Building now on Zipline-Reloaded's foundation, before potential future abandonment, is critical. The alternative is building from scratch (12+ additional months).

---

## Proposed Solution

### Core Concept

RustyBT forks Zipline-Reloaded as a development accelerator and implements comprehensive enhancements across 10 core functional areas, transforming it into a production-grade platform with:

1. **Financial-Grade Decimal Arithmetic**: Complete replacement of `float` with `Decimal` throughout calculation engine, order execution, performance metrics, and data pipelines—with configurable precision (8 decimals for crypto, 2 for equities, 4 for forex)

2. **Unified Data Catalog with Local Caching**: Polars/Parquet-based data catalog that intelligently caches price data locally by backtest, enabling instant subsequent retrieval for that backtest or any other using the same data—eliminating repeated API calls and ingestion overhead

3. **Comprehensive Live Trading**: Production-ready live trading engine built natively (not via forks), with direct broker integrations (Interactive Brokers via ib_async, Binance via binance-connector, Bybit via pybit, Hyperliquid via official Python SDK, plus 100+ exchanges via CCXT), state management, position reconciliation, and scheduled calculations

4. **Advanced Order Types & Realistic Costs**: Professional order types (Market, Limit, Stop-Loss, Stop-Limit, Trailing Stop, OCO, Bracket), realistic transaction cost modeling (latency simulation, partial fills, volume-based slippage, tiered commissions, borrow costs, overnight financing)

5. **Multi-Strategy Portfolio Management**: Portfolio allocator supporting multiple concurrent strategies with sophisticated capital allocation (Fixed, Dynamic, Risk-Parity, Kelly Criterion, Drawdown-Based), cross-strategy risk management, and order aggregation

6. **Strategic Rust Performance Layer**: Rust reimplementation of profiled bottlenecks (identified after Python implementation complete), targeting Decimal arithmetic hot paths, indicator calculations, data processing pipelines—using PyO3 0.26+ for seamless Python integration

7. **Strategy Optimization & Robustness Testing**: Comprehensive optimization algorithms (Grid Search, Random Search, Bayesian, Genetic, Walk-Forward), parallel processing framework, overfitting prevention (Combinatorially Purged Cross-Validation, parameter stability analysis), and robustness testing tools

8. **RESTful API & WebSocket Interface**: Professional APIs for remote strategy execution, real-time monitoring, portfolio updates, trade notifications, and external system integration

9. **Analytics & Reporting**: Interactive reporting dashboard, advanced performance attribution, risk analytics (VaR, CVaR, stress testing), trade analysis, and optimization recommendations

10. **Security, Reliability & Type Safety**: Comprehensive error handling, audit logging (structured logs with trade-by-trade tracking), multi-layer data validation, type safety (mypy --strict compliance), and production best practices

### Core Principle: Temporal Isolation & Backtest Integrity

**Non-Negotiable Requirement**: RustyBT guarantees temporal isolation against lookahead bias, data leakage, and forward-looking information contamination. Every data access, calculation, and decision must be strictly time-aware, preventing deceptive, bias-impaired backtest results.

**Implementation**:
- Strict timestamp validation in data pipelines
- Forward-looking data prevention in indicator calculations
- Purging and embargo in cross-validation splits (CPCV)
- Temporal consistency checks in corporate action adjustments
- Audit trail tracking for all time-series operations

### Key Differentiators

**vs. Zipline-Reloaded**: Adds Decimal arithmetic (audit-compliant), modern Polars/Parquet data architecture with intelligent local caching, native live trading with production broker integrations, Rust performance optimization, REST/WebSocket APIs, multi-strategy portfolio management, comprehensive optimization tools

**vs. Backtrader**: Active maintenance, Python 3.12+ support, superior test coverage foundation (88.26%), cleaner architecture, Decimal arithmetic, modern data layer, continued development

**vs. Commercial Solutions**: Open-source, self-hosted, no vendor lock-in, full customization, transparent methodology, local development (no cloud dependency), extensible architecture

### Why This Solution Will Succeed

1. **Proven Foundation**: Zipline-Reloaded's 88.26% test coverage and clean architecture enable safe major refactoring
2. **Python-First Philosophy**: Pure Python development with Rust only for profiled bottlenecks maintains accessibility and rapid iteration
3. **Right Technology Stack**: Python 3.12+, Polars 1.x (5-10x faster than Pandas), Rust 1.90+ with PyO3 0.26+, rust-decimal 1.37+
4. **Milestone-Driven Development**: Progress-based milestones (not time-based) organized by implementation effort prevent unrealistic scheduling
5. **Financial Integrity First**: Decimal arithmetic and temporal isolation are foundational, not afterthoughts
6. **Direct Broker Integrations**: Using trusted, maintained libraries (ib_async for Interactive Brokers, official binance-connector, pybit for Bybit, hyperliquid SDK, CCXT for broad coverage) with fork-and-modify option when more control needed

---

## Target Users

### Primary User Segment: Individual Quantitative Traders & Researchers

**Profile:**
- Solo or small team (1-5 people)
- Python proficiency (intermediate to advanced)
- Financial markets experience (stocks, crypto, forex, futures)
- Strategy development focus (alpha research, systematic trading)
- Self-hosting preference (local development, VPS deployment)

**Current Behaviors:**
- Prototyping strategies in Jupyter notebooks
- Using Zipline, Backtrader, or VectorBT for backtesting
- Manually implementing financial calculations to avoid float errors
- Building custom data pipelines and broker integrations
- Struggling with backtest-to-live transition
- Spending weeks on infrastructure rather than strategy development

**Specific Needs:**
- Audit-compliant financial accuracy (Decimal arithmetic throughout)
- Fast iteration cycle (quick backtests, easy data integration, instant re-runs with cached data)
- Confidence in results (high test coverage, transparent calculations, temporal isolation guarantees)
- Seamless backtest-to-live workflow (same code, same results)
- Self-hosted solution (data privacy, full control, local development)
- Comprehensive optimization and robustness testing (walk-forward, parameter stability, CPCV)

**Goals:**
- Develop profitable trading strategies with confidence
- Validate strategies with realistic, unbiased simulations
- Deploy to live trading quickly and safely
- Avoid costly implementation errors and bias-impaired backtests
- Maintain full control over infrastructure and data

---

### Secondary User Segment: Proprietary Trading Firms & Quantitative Hedge Funds

**Profile:**
- Small to mid-size firms (5-50 traders/researchers)
- Professional engineering teams
- Multi-strategy operations
- Regulatory compliance requirements
- Infrastructure budget ($50k-$500k+/year)

**Current Behaviors:**
- Using mix of commercial tools (QuantConnect, Bloomberg) and internal systems
- Maintaining expensive legacy backtesting infrastructure
- Extensive manual testing before production deployment
- Building custom solutions for compliance and audit requirements
- Evaluating open-source alternatives to reduce costs

**Specific Needs:**
- Financial accuracy for audit trails (Decimal arithmetic mandatory)
- High performance (large universes, complex strategies, fast optimization)
- Multi-strategy portfolio management (capital allocation, risk aggregation)
- Production reliability (uptime, error handling, state management)
- Comprehensive testing and validation (prevent costly failures)

**Goals:**
- Reduce infrastructure costs vs. commercial solutions
- Accelerate strategy research velocity (more backtests, faster iteration)
- Improve backtest-to-production reliability (reduce manual testing)
- Meet regulatory compliance requirements (audit trails, Decimal precision)
- Scale platform with firm growth without vendor lock-in

---

## Goals & Success Metrics

### Business Objectives

- **Objective 1**: Achieve Decimal arithmetic implementation with <30% performance overhead vs. float-based baseline (pure original implementation) through strategic Rust optimization
  - **Metric**: Performance benchmarks show Decimal overhead mitigated to target level, financial calculations accurate to 8+ decimal places

- **Objective 2**: Deliver unified data catalog with local caching demonstrating instant retrieval for repeated backtests using same data
  - **Metric**: Second backtest using cached data loads in <1 second vs. minutes for initial API fetch/ingestion

- **Objective 3**: Enable production live trading deployment with 5+ broker integrations and seamless backtest-to-live transition
  - **Metric**: Same strategy code runs in backtest and live modes with >99% behavioral correlation (paper trading validation)

- **Objective 4**: Build active open-source community with sustainable contributions
  - **Metric**: 1,000+ GitHub stars, 50+ contributors, 10+ community PRs merged

### User Success Metrics

- **Metric 1**: Time from idea to validated backtest reduced by 60%
  - Target: <30 minutes for typical strategy implementation and initial backtest, <10 seconds for subsequent backtests using cached data

- **Metric 2**: Financial calculation accuracy verified to 8+ decimal places with zero rounding errors
  - Target: Perfect Decimal precision in audit testing, property-based testing passes (Hypothesis)

- **Metric 3**: Backtest-to-live strategy behavior correlation >99%
  - Target: Same strategy produces nearly identical results in backtest vs. paper trading (accounting for realistic slippage/commissions)

- **Metric 4**: Strategy optimization completion time reduced by 10x through parallelization
  - Target: Walk-forward optimization across 5 years of data with 100 parameter combinations completes in <30 minutes on 8-core machine

### Key Performance Indicators (KPIs)

- **Test Coverage**: ≥90% overall, ≥95% for financial calculation modules (maintain/improve Zipline-Reloaded's 88.26%)
- **Performance**: Typical backtest (2 years daily data, 50 assets, moderate complexity) <30s; Rust-optimized operations achieve parity with pure float baseline
- **Reliability**: 99.9% uptime for live trading engine (excluding planned maintenance), zero financial calculation errors
- **Community Growth**: 100+ stars/month after initial launch, 10+ active contributors
- **Documentation Quality**: 100% public API documented, 30+ tutorials/examples, comprehensive architecture guide

---

## Core Concepts & Features

All 10 phases from the brainstorming document represent **core, essential functionality**—not MVP vs. post-MVP distinction. Instead, features are organized into **3 implementation tiers** based on how much code creation/modification is required to integrate them into the forked framework.

### Implementation Tier Classification

**Tier 1 - Minimal Modification (Foundation Already Exists)**
Features where Zipline-Reloaded already has substantial infrastructure; requires primarily configuration, extension, and refinement rather than ground-up implementation.

**Tier 2 - Moderate Creation (Partial Infrastructure Exists)**
Features where some foundational components exist but significant new code, architecture, and integration work is required.

**Tier 3 - Major Creation (Build From Scratch)**
Features with little to no existing infrastructure in the forked codebase; requires comprehensive new implementation.

---

### Tier 1: Minimal Modification (Foundation Already Exists)

These features leverage existing Zipline-Reloaded infrastructure, requiring extension and refinement rather than ground-up implementation.

#### 1.1 Data Pipeline Foundation (Existing: Bundle System, Data Loading)

**What Exists**: Zipline-Reloaded has robust data bundle system, ingestion framework, Pipeline API for data access, and trading calendar support.

**What's Needed**:
- Extend bundle system to support custom schemas
- Add metadata tracking for data provenance
- Enhance timezone handling and gap detection
- Improve corporate action adjustment handling
- **Estimated Effort**: 2-3 weeks (extension, not creation)

#### 1.2 Backtest Engine Core (Existing: Simulation Loop, Order Execution)

**What Exists**: Zipline has complete backtesting engine with simulation clock, event-driven architecture, order matching, portfolio tracking, performance metrics.

**What's Needed**:
- Enhance simulation clock for sub-second resolutions
- Add real-time mode switching for live trading
- Improve event system for custom triggers
- **Estimated Effort**: 2-3 weeks (refinement)

#### 1.3 Order Management Basics (Existing: Market/Limit Orders)

**What Exists**: Order object model, basic order lifecycle, simple commission models, basic slippage.

**What's Needed**:
- Extend order types (Stop-Loss, Stop-Limit, Trailing Stop, OCO, Bracket)
- Add order state machine with comprehensive states
- Enhance commission/slippage model pluggability
- **Estimated Effort**: 3-4 weeks (extension of existing system)

#### 1.4 Performance Metrics Foundation (Existing: Returns, Sharpe, Drawdown)

**What Exists**: Core performance metrics (returns, Sharpe ratio, max drawdown, volatility), risk-free rate handling, benchmark comparison.

**What's Needed**:
- Add advanced metrics (Sortino, Calmar, CVaR, win rate, profit factor)
- Enhance risk metrics (VaR, conditional metrics)
- Add performance attribution framework
- **Estimated Effort**: 2-3 weeks (adding metrics to existing framework)

**Tier 1 Total Estimated Effort**: 9-13 weeks

---

### Tier 2: Moderate Creation (Partial Infrastructure Exists)

These features have some foundational components but require significant new architecture and integration work.

#### 2.1 Decimal Arithmetic Implementation (Partial: Calculation Framework Exists)

**What Exists**: Calculation infrastructure (portfolio value, position sizing, metrics), well-tested calculation logic (88.26% coverage), clear separation of financial calculations.

**What's Needed**:
- Systematic replacement of `float` with `Decimal` throughout codebase
- Configuration system for precision by asset class
- Decimal context management (rounding modes)
- Conversion layers for external libraries expecting float
- Comprehensive property-based testing (Hypothesis)
- Performance profiling and optimization
- **Estimated Effort**: 6-9 weeks (major refactoring with existing test harness providing safety net)

#### 2.2 Modern Data Catalog (Polars/Parquet) (Partial: Ingestion Framework Exists)

**What Exists**: Bundle ingestion architecture, data source abstraction, metadata storage (SQLite), asset database schema.

**What's Needed**:
- **Complete replacement of HDF5 storage with Parquet** (columnar format, better compression)
- **Polars integration for fast querying** (lazy evaluation, predicate pushdown)
- **Local caching system with backtest linkage**: When a backtest runs, store price data with custom schema such that subsequent backtests using same data retrieve it instantly from local cache (eliminate repeated API calls)
- Metadata catalog tracking cached datasets (symbols, date ranges, resolutions, checksums)
- Two-tier caching (in-memory Polars + disk Parquet)
- Schema validation and versioning
- **Estimated Effort**: 8-12 weeks (replacing storage layer, implementing intelligent caching)

#### 2.3 Data Source Adapters (Partial: Adapter Pattern Exists)

**What Exists**: Data source adapter abstraction, bundle ingestion interface, example data readers (CSV, Quandl).

**What's Needed**:
- **Base adapter class** with standardized interface (fetch, validate, standardize)
- **YFinance adapter** - Free stock/ETF/forex data (using yfinance library)
- **CCXT adapter** - Unified crypto exchange data (100+ exchanges, critical for crypto strategies, using ccxt library v4.x+)
- **CSV adapter** - Custom data import with flexible schema mapping
- **Polygon adapter** - Professional market data (optional, for users with subscriptions)
- **Alpaca adapter** - Commission-free broker data (optional)
- **WebSocket adapter** - Real-time streaming data (foundation for live trading)
- **CloudStorage adapter** - S3/GCS/Azure integration (optional, for cloud workflows)
- Multi-resolution aggregation system (sub-second to monthly)
- OHLCV relationship validation
- Outlier detection and temporal consistency checks
- **Estimated Effort**: 10-14 weeks (building adapter architecture + 7 implementations, prioritize CCXT and YFinance)

#### 2.4 Advanced Transaction Costs (Partial: Basic Slippage/Commission Exists)

**What Exists**: Simple percentage-based commission, basic slippage models, pluggable cost model architecture.

**What's Needed**:
- Latency simulation (network + broker + exchange latency, realistic timing)
- Partial fill model (based on order size vs. volume)
- Multiple slippage models (volume-share, fixed bps, bid-ask spread)
- Multiple commission models (per-share, percentage, tiered, maker/taker for crypto)
- Borrow cost model (short selling interest)
- Overnight financing model (leveraged positions)
- **Estimated Effort**: 4-6 weeks (extending existing cost modeling framework)

#### 2.5 Multi-Strategy Portfolio System (Partial: Single Strategy Framework Exists)

**What Exists**: Single strategy execution, portfolio tracking, capital management.

**What's Needed**:
- Portfolio allocator supporting multiple concurrent strategies
- Capital allocation algorithms (Fixed, Dynamic, Risk-Parity, Kelly Criterion, Max Drawdown-Based)
- Cross-strategy risk management (portfolio-level limits, correlation-aware sizing)
- Order aggregation (netting positions across strategies)
- Per-strategy performance tracking
- Strategy weighting rebalancer
- **Estimated Effort**: 6-8 weeks (building multi-strategy orchestration layer)

#### 2.6 Strategy Optimization Tools (Partial: Testing Infrastructure Exists)

**What Exists**: Testing framework, parameter passing system, performance metric calculation.

**What's Needed**:
- **5 optimization algorithms**: Grid Search, Random Search, Bayesian (scikit-optimize), Genetic (DEAP), Walk-Forward
- Parallel processing framework (Ray for distributed computing, multiprocessing for local)
- Overfitting prevention tools:
  - Train/Validation/Test splitting
  - Combinatorially Purged Cross-Validation (CPCV) - prevents data leakage in time series
  - Parameter stability analysis across windows
- Optimization result visualization and ranking
- Best practices guide and example notebooks
- **Estimated Effort**: 8-10 weeks (building optimization framework + 5 algorithms + validation tools)

#### 2.7 Testing & Quality Assurance Enhancement (Partial: 88.26% Coverage Exists)

**What Exists**: Comprehensive unit test suite (88.26% coverage), CI/CD infrastructure, pytest framework.

**What's Needed**:
- **Improve coverage to ≥90%** overall, ≥95% for financial modules
- Property-based testing for financial calculations (Hypothesis)
- Integration test suite (end-to-end backtest scenarios)
- Regression test suite (prevent performance degradation)
- Lookahead bias detection tests (temporal isolation validation)
- Stress testing (edge cases, extreme market conditions)
- Data quality testing (OHLCV validation, outlier detection)
- **Estimated Effort**: Ongoing throughout development, ~10-12 weeks dedicated effort

**Tier 2 Total Estimated Effort**: 52-71 weeks

---

### Tier 3: Major Creation (Build From Scratch)

These features have minimal existing infrastructure and require comprehensive new implementation.

#### 3.1 Live Trading Engine (None: Must Build Natively)

**What Exists**: Virtually nothing—Zipline-Reloaded has no native live trading support.

**What's Needed**:
- **Real-time trading engine** (event-driven, async architecture)
- **State management system** (persist strategy state, portfolio state, order state)
  - Save/restore on shutdown/startup
  - Crash recovery
  - Position reconciliation with broker
- **Scheduled calculations** (cron-like scheduling for strategy logic)
  - Market open/close triggers
  - Custom time-based triggers
  - Flexible scheduling expressions
- **Paper trading mode** (simulated broker with real market data, realistic latency/fills)
- **Broker integration framework** with adapters for:
  - **Interactive Brokers** (via ib_async - successor to ib_insync, maintained)
  - **Binance** (via binance-connector 3.12+ - official Python library)
  - **Bybit** (via pybit - official Bybit Python SDK)
  - **Hyperliquid** (via hyperliquid-python-sdk - official DEX SDK)
  - **CCXT** (100+ exchanges, unified API, ccxt v4.x+)
- Real-time data feed integration (WebSocket streams)
- Order routing and execution
- Fill confirmation handling
- Error recovery and circuit breakers
- Monitoring and alerting
- **Estimated Effort**: 18-24 weeks (ground-up implementation)

#### 3.2 Rust Performance Layer (None: No Rust Integration)

**What Exists**: Nothing—Zipline-Reloaded is pure Python.

**What's Needed**:
- **Important Note**: Rust integration happens AFTER profiling Python implementation. Do not optimize prematurely.
- **Workflow**: Implement in Python → Profile to identify bottlenecks → Reimplement hot paths in Rust
- PyO3 0.26+ integration setup (Python 3.12+ support)
- Rust project structure (Cargo workspace, maturin for building)
- **Decimal arithmetic optimization** (rust-decimal 1.37+ for hot paths)
- **Indicator calculations** (technical indicators in Rust)
- **Data processing pipelines** (Polars-like performance for custom operations)
- Python/Rust conversion layers
- Comprehensive benchmarking suite
- **Performance target**: Achieve parity with pure float baseline (not arbitrary 10-100x goals)
- CI/CD integration (build, test Rust modules)
- **Estimated Effort**: 12-16 weeks (after profiling identifies targets)

#### 3.3 RESTful API & WebSocket Interface (None: No API Layer)

**What Exists**: Nothing—Zipline-Reloaded is a library, not a service.

**What's Needed**:
- **FastAPI REST API** (async, modern Python framework)
  - Strategy execution endpoints (start, stop, status)
  - Portfolio queries (positions, cash, value)
  - Order management (submit, cancel, status)
  - Performance metrics retrieval
  - Data catalog queries
  - Authentication and authorization
  - Rate limiting
- **WebSocket API** (real-time updates)
  - Live portfolio updates
  - Trade notifications
  - Order fill confirmations
  - Market data streaming
- **OpenAPI/Swagger documentation**
- Multi-client support (concurrent connections)
- **Estimated Effort**: 10-14 weeks (building API layer from scratch)

#### 3.4 Analytics & Reporting Dashboard (None: No Visualization Layer)

**What Exists**: Raw performance metrics only—no visualization or interactive analysis.

**What's Needed**:
- **Note**: Full web dashboard may be unnecessary for Python-first framework. Consider prioritizing:
  - **Jupyter notebook integration** (interactive analysis in familiar environment)
  - **Programmatic report generation** (matplotlib/seaborn based, exportable)
  - **Optional**: Streamlit dashboard (rapid prototyping, Python-native)
- Advanced performance attribution
- Risk analytics (VaR, CVaR, stress testing, scenario analysis)
- Trade analysis (entry/exit quality, holding periods, win/loss distribution)
- Equity curve visualization with drawdown periods
- Correlation matrix and factor exposure
- Monte Carlo simulation results
- **Estimated Effort**: 8-12 weeks (if implementing full dashboard; 4-6 weeks for notebook integration + programmatic reports)

#### 3.5 Security & Reliability Hardening (Partial: Basic Error Handling)

**What Exists**: Basic Python exception handling, some input validation.

**What's Needed**:
- **Comprehensive exception hierarchy** (custom exception types for all error categories)
- **Graceful error handling** (recovery strategies, fallback behaviors)
- **Structured audit logging** (structlog)
  - Trade-by-trade logging (every order, fill, modification, cancellation)
  - Strategy decision logging (signals, position changes)
  - System event logging (startup, shutdown, errors)
  - Searchable, parseable logs (JSON format)
- **Multi-layer data validation**:
  - Layer 1: Schema validation (correct types, required fields)
  - Layer 2: OHLCV relationship validation (High ≥ Low, High ≥ Open/Close, etc.)
  - Layer 3: Outlier detection (price spike detection, volume anomalies)
  - Layer 4: Temporal consistency (sorted timestamps, no duplicates, gap detection)
- **Type safety** (mypy --strict compliance across codebase)
- **Security best practices**:
  - Input sanitization (prevent injection attacks)
  - Credential management (environment variables, secrets management)
  - API key encryption
  - Rate limiting
- **Estimated Effort**: 8-10 weeks (comprehensive hardening)

**Tier 3 Total Estimated Effort**: 56-76 weeks

---

### Total Estimated Effort Summary

- **Tier 1 (Minimal Modification)**: 9-13 weeks
- **Tier 2 (Moderate Creation)**: 52-71 weeks
- **Tier 3 (Major Creation)**: 56-76 weeks

**Grand Total**: 117-160 weeks (27-37 months for single full-time developer)

**Note**: These are sequential effort estimates. With parallel work streams (e.g., one developer on data layer while another on live trading), calendar time can be compressed. Estimates assume experienced Python developer with financial domain knowledge.

---

## Development Milestones (Progress-Based)

Development is organized into milestones based on functional completion, not arbitrary time periods. Each milestone represents a coherent set of capabilities that can be tested and validated.

### Milestone 1: Foundation & Core Infrastructure

**Objectives**:
- Fork repository and establish development environment
- Map existing architecture and identify modification points
- Establish testing framework and CI/CD
- Begin Tier 1 extensions

**Deliverables**:
- Forked repository with CI/CD (GitHub Actions)
- Architecture documentation (module map, extension points)
- Development environment setup guide
- Enhanced data pipeline (extended bundle system, metadata tracking)
- Improved backtest engine (sub-second support, enhanced event system)
- Extended order management (Stop-Loss, Stop-Limit, Trailing Stop, OCO, Bracket)
- Additional performance metrics (Sortino, Calmar, CVaR, VaR, win rate, profit factor)

**Completion Criteria**:
- All Tier 1 features implemented and tested
- CI/CD passing with ≥90% test coverage
- Documentation complete

---

### Milestone 2: Financial Integrity - Decimal Arithmetic

**Objectives**:
- Implement Decimal arithmetic throughout platform
- Establish configurable precision system
- Validate financial accuracy with property-based testing

**Deliverables**:
- Complete `float` → `Decimal` replacement in:
  - Core calculation engine (portfolio value, position sizing, returns)
  - Order execution system (prices, quantities, commissions, slippage)
  - Performance metrics (Sharpe, Sortino, drawdown, PnL)
  - Data pipelines (price data, corporate actions)
- Precision configuration (8 decimals crypto, 2 equities, 4 forex)
- Decimal context management (rounding modes)
- Conversion layers for external libraries
- Property-based testing suite (Hypothesis)
- Performance baseline benchmarks (establish reference for Rust optimization)

**Completion Criteria**:
- Zero rounding errors in financial calculations (verified by property-based tests)
- All financial tests pass with Decimal
- ≥95% test coverage for financial modules
- Performance benchmarks documented (baseline for future optimization)

---

### Milestone 3: Modern Data Architecture

**Objectives**:
- Replace HDF5 with Polars/Parquet data catalog
- Implement intelligent local caching system
- Build extensible data source adapter framework
- Prioritize CCXT (crypto) and YFinance (stocks) adapters

**Deliverables**:
- Polars/Parquet unified data catalog
  - SQLite metadata database
  - Parquet columnar storage
  - Polars lazy query engine
  - Two-tier caching (in-memory + disk)
- **Local caching system**: Backtest-linked price data storage enabling instant retrieval for subsequent backtests using same data
- Base data source adapter class (standardized interface)
- **CCXT adapter** (priority: crypto trading, 100+ exchanges)
- **YFinance adapter** (priority: free stock/ETF data)
- **CSV adapter** (custom data import)
- WebSocket adapter foundation (for live trading)
- Multi-resolution aggregation system (sub-second to monthly)
- OHLCV validation and outlier detection
- Timezone management and gap handling

**Completion Criteria**:
- Parquet storage operational, HDF5 fully replaced
- Second backtest using cached data loads in <1 second
- CCXT and YFinance adapters pass integration tests with live data
- Multi-resolution aggregation validates OHLCV relationships
- ≥90% test coverage for data layer

---

### Milestone 4: Enhanced Transaction Costs & Multi-Strategy Support

**Objectives**:
- Implement realistic transaction cost modeling
- Build multi-strategy portfolio management system

**Deliverables**:
- **Advanced transaction costs**:
  - Latency simulation (network + broker + exchange)
  - Partial fill model (volume-based)
  - Multiple slippage models (volume-share, fixed bps, bid-ask spread)
  - Multiple commission models (per-share, percentage, tiered, maker/taker)
  - Borrow cost model (short selling)
  - Overnight financing model (leveraged positions)
- **Multi-strategy portfolio system**:
  - Portfolio allocator (multiple concurrent strategies)
  - Capital allocation algorithms (Fixed, Dynamic, Risk-Parity, Kelly, Drawdown-Based)
  - Cross-strategy risk management (portfolio-level limits, correlation-aware sizing)
  - Order aggregation (net positions across strategies)
  - Per-strategy performance tracking

**Completion Criteria**:
- Transaction cost models validated against real broker fee schedules
- Multi-strategy system runs 5+ concurrent strategies with correct capital allocation
- Cross-strategy risk limits enforced correctly
- ≥90% test coverage

---

### Milestone 5: Strategy Optimization & Robustness Testing

**Objectives**:
- Implement comprehensive optimization algorithms
- Build overfitting prevention tools
- Enable parallel processing for fast optimization

**Deliverables**:
- **5 optimization algorithms**:
  - Grid Search (exhaustive)
  - Random Search (faster for high dimensions)
  - Bayesian Optimization (scikit-optimize)
  - Genetic Algorithm (DEAP)
  - Walk-Forward (overfitting prevention)
- Parallel processing framework (Ray + multiprocessing)
- **Overfitting prevention**:
  - Train/Validation/Test splitting
  - Combinatorially Purged Cross-Validation (CPCV)
  - Parameter stability analysis
- Optimization result visualization and ranking
- Best practices guide and example notebooks (10+ examples)

**Completion Criteria**:
- Walk-forward optimization across 5 years, 100 parameter combinations completes in <30 minutes (8-core machine)
- CPCV prevents data leakage (validated with intentional lookahead test)
- Parameter stability analysis identifies unstable parameters
- ≥90% test coverage for optimization modules

---

### Milestone 6: Live Trading Engine & Broker Integrations

**Objectives**:
- Build production-ready live trading engine
- Implement broker integrations for major platforms
- Enable seamless backtest-to-live deployment

**Deliverables**:
- **Real-time trading engine**:
  - Event-driven async architecture
  - State management (save/restore, crash recovery)
  - Position reconciliation with broker
  - Scheduled calculations (market open/close, custom triggers)
  - Circuit breakers and risk controls
- **Paper trading mode** (simulated broker with realistic fills)
- **Broker integrations**:
  - **Interactive Brokers** (ib_async)
  - **Binance** (binance-connector 3.12+)
  - **Bybit** (pybit)
  - **Hyperliquid** (hyperliquid-python-sdk)
  - **CCXT** (100+ exchanges via unified API)
- Real-time data feed integration (WebSocket streams)
- Order routing and execution
- Fill confirmation and error recovery
- Monitoring and alerting

**Completion Criteria**:
- Same strategy code runs in backtest and live (paper trading) modes with >99% behavioral correlation
- 5 broker integrations pass live connection tests
- State persistence and recovery work correctly (survives restart)
- Paper trading mode matches backtest results (accounting for realistic slippage/commissions)
- ≥90% test coverage (unit tests; integration tests with paper trading accounts)

---

### Milestone 7: Testing & Quality Assurance Maturity

**Objectives**:
- Achieve ≥90% overall test coverage, ≥95% for financial modules
- Implement property-based testing for critical paths
- Build regression and stress testing suites
- Validate temporal isolation guarantees

**Deliverables**:
- Enhanced test coverage (≥90% overall, ≥95% financial)
- Property-based testing for financial calculations (Hypothesis)
- Integration test suite (50+ end-to-end scenarios)
- Regression test suite (prevent performance degradation)
- **Lookahead bias detection tests** (validate temporal isolation)
- Stress testing (edge cases, extreme market conditions, flash crashes)
- Data quality testing (OHLCV validation, outlier detection, gap handling)
- Continuous integration (all tests run on every commit)

**Completion Criteria**:
- Test coverage metrics met (≥90% overall, ≥95% financial)
- Zero test failures in CI/CD pipeline
- Property-based tests discover and fix edge cases
- Temporal isolation validated (no lookahead bias in backtests)
- Stress tests pass with graceful degradation

---

### Milestone 8: Performance Optimization - Rust Integration

**Objectives**:
- Profile Python implementation to identify bottlenecks
- Reimplement hot paths in Rust for performance
- Achieve parity with pure float baseline (mitigate Decimal overhead)

**Deliverables**:
- **Performance profiling results** (identify bottlenecks: Decimal arithmetic, indicators, data processing)
- PyO3 0.26+ integration (Python 3.12+ support)
- Rust project structure (Cargo workspace, maturin builds)
- **Rust-optimized modules**:
  - Decimal arithmetic hot paths (rust-decimal 1.37+)
  - Technical indicator calculations
  - Data processing pipelines
- Python/Rust conversion layers (seamless integration)
- Comprehensive benchmarking suite
- **Performance validation**: Achieve parity with pure float baseline

**Completion Criteria**:
- Profiling identifies bottlenecks consuming >5% of backtest time
- Rust-optimized operations achieve targeted performance (≤30% overhead vs. float baseline)
- Typical backtest (2 years daily, 50 assets) completes in <30 seconds
- Zero functional regressions (Rust and Python implementations produce identical results)
- Benchmarks documented and tracked in CI/CD

---

### Milestone 9: RESTful API & WebSocket Interface

**Objectives**:
- Build professional API layer for external integration
- Enable remote strategy execution and monitoring
- Support multi-client concurrent access

**Deliverables**:
- **FastAPI REST API**:
  - Strategy execution endpoints (start, stop, status)
  - Portfolio queries (positions, cash, value, history)
  - Order management (submit, cancel, modify, status)
  - Performance metrics retrieval
  - Data catalog queries
  - Authentication and authorization
  - Rate limiting
- **WebSocket API** (real-time updates):
  - Live portfolio updates
  - Trade notifications
  - Order fill confirmations
  - Market data streaming (if applicable)
- OpenAPI/Swagger documentation
- Multi-client support (concurrent connections)
- Client SDKs (Python, TypeScript - optional)

**Completion Criteria**:
- REST API supports full remote control of backtests and live trading
- WebSocket updates deliver <100ms latency
- API documentation complete (Swagger UI)
- Multi-client load testing passes (10+ concurrent clients)
- Authentication and rate limiting prevent abuse

---

### Milestone 10: Analytics, Security & Production Readiness

**Objectives**:
- Implement advanced analytics and reporting
- Harden security and reliability for production deployment
- Achieve production-ready quality standards

**Deliverables**:
- **Analytics & Reporting**:
  - Jupyter notebook integration (interactive analysis)
  - Programmatic report generation (matplotlib/seaborn)
  - Advanced performance attribution
  - Risk analytics (VaR, CVaR, stress testing, scenario analysis)
  - Trade analysis (entry/exit quality, win/loss distribution)
  - Equity curve visualization with drawdown periods
  - Optional: Streamlit dashboard (rapid prototyping)
- **Security & Reliability**:
  - Comprehensive exception hierarchy
  - Graceful error handling and recovery
  - Structured audit logging (trade-by-trade, searchable JSON logs)
  - Multi-layer data validation (schema, OHLCV, outliers, temporal)
  - Type safety (mypy --strict compliance)
  - Security best practices (credential encryption, input sanitization, rate limiting)
- Production deployment guide
- Monitoring and alerting setup guide

**Completion Criteria**:
- Analytics generate publication-quality reports
- All code passes mypy --strict type checking
- Audit logs capture every trade and decision (searchable, parseable)
- Security audit passes (no credential leaks, injection vulnerabilities)
- Production deployment guide tested on clean environment
- Platform runs production workload (live trading) with 99.9% uptime over 1-month validation period

---

## Technology Stack

### Core Technologies

**Python**:
- **Version**: Python 3.12+ (required)
  - Latest stable: Python 3.12.11 (June 2025)
  - Rationale: Modern type hints, performance improvements, walrus operator, structural pattern matching

**Polars**:
- **Version**: Polars 1.x latest
  - Performance: 5-10x faster than Pandas for common operations (filtering, aggregations, CSV loading)
  - Memory: 5-10x more efficient (2-4x dataset size vs. Pandas 5-10x)
  - Features: Lazy evaluation, query optimization, parallel execution, columnar format
  - Rationale: Modern, performant DataFrame library with excellent Parquet integration
  - **Alternative Analysis vs. Pandas**:
    - **Pandas 2.0**: Mature ecosystem, excellent ML library integration, familiar API
    - **Polars Advantages**: Rust implementation (faster), parallel execution (multi-core), lazy evaluation (query optimization), better memory efficiency, modern API
    - **Trade-offs**: Polars ecosystem still growing, some ML libraries expect Pandas (conversion needed)
    - **Decision**: Polars for data catalog (performance critical), with Pandas conversion layer for ML integrations if needed

**Rust**:
- **Version**: Rust 1.90+ (stable channel)
  - Latest stable: Rust 1.90 (September 2025)
  - Rationale: Performance optimization for bottlenecks, mature tooling, excellent PyO3 support

**PyO3**:
- **Version**: PyO3 0.26+
  - Latest: v0.26.0 (August 2025)
  - Python support: 3.12-3.14 (including free-threaded Python 3.14t)
  - Rationale: Mature Python/Rust bindings, production-proven (used by Polars, Ruff)

**rust-decimal**:
- **Version**: rust-decimal 1.37+
  - Latest: 1.37.2 (June 2025)
  - Rationale: High-precision decimal arithmetic in Rust, PyO3 compatible

### Data & Broker Integrations

**Data Sources**:
- **CCXT**: v4.x+ (100+ crypto exchanges, unified API, Python/JS/PHP support)
- **yfinance**: Latest (free stock/ETF/forex data from Yahoo Finance)
- **Polygon.io**: Optional (professional market data, subscription required)
- **Alpaca**: Optional (commission-free broker data)

**Broker Libraries**:
- **ib_async**: Latest (Interactive Brokers - successor to ib_insync, actively maintained)
- **binance-connector**: 3.12+ (official Binance Python library, released January 2025)
- **pybit**: Latest (official Bybit Python SDK, supports derivatives and spot)
- **hyperliquid-python-sdk**: Latest (official Hyperliquid DEX SDK, Python 3.9-3.13)
- **CCXT**: v4.x+ (100+ exchanges for broad coverage)

**Rationale for Broker Libraries**: Use trusted, maintained official/community libraries. Fork and modify if more control needed (approach prioritizes rapid development over NIH syndrome).

### Storage & Databases

**Parquet**: Columnar storage format
- Better compression than HDF5 (50-80% smaller)
- Interoperability (Python, Rust, R, cloud-native)
- Fast columnar queries with predicate pushdown

**SQLite**: Metadata catalog
- Embedded (no server required)
- Excellent for local metadata (symbols, date ranges, checksums)
- Production-proven, zero-config

### APIs & Web (Optional/Future)

**FastAPI**: REST API framework
- Async support (high concurrency)
- OpenAPI/Swagger auto-generation
- Modern Python (type hints, Pydantic validation)

**WebSocket**: Real-time updates
- Standard library `websockets` or FastAPI WebSocket support

**Streamlit**: Optional dashboard (Python-native, rapid prototyping)

### Testing & Quality

**pytest**: Testing framework (industry standard)
**Hypothesis**: Property-based testing (financial calculation validation)
**mypy**: Static type checking (--strict mode)
**structlog**: Structured logging (JSON format, searchable)
**Ray**: Distributed computing (parallel optimization)

### Development Tools

**GitHub Actions**: CI/CD (free for open-source)
**maturin**: Rust/Python build tool (PyO3 integration)
**Docker**: Containerization (optional, for deployment)
**Coverage.py**: Code coverage tracking

---

## Risks & Open Questions

### Key Risks

- **Decimal Performance Too Slow (High Impact, High Probability)**:
  - *Description*: Decimal arithmetic is ~100x slower than float. Even with Rust optimization, platform may be too slow for complex strategies.
  - *Impact*: Platform unusable for production, adoption failure
  - *Mitigation*: Early profiling, Rust rust-decimal from start after profiling identifies bottlenecks, benchmark suite tracks performance, fallback hybrid approach (Decimal for financial, float for indicators if absolutely necessary)

- **Broker Integration Complexity (Medium Impact, Medium Probability)**:
  - *Description*: Broker APIs are complex, inconsistent, poorly documented, subject to breaking changes
  - *Impact*: Development delays, fragile integrations, live trading failures
  - *Mitigation*: Start with well-maintained libraries (ib_async, binance-connector, pybit, hyperliquid SDK, CCXT), fork and modify if needed, comprehensive integration testing with paper trading accounts, maintain version pins

- **Live Trading Bugs (CRITICAL Impact, Medium Probability)**:
  - *Description*: Bugs in live trading engine cause financial losses for users
  - *Impact*: Reputation damage, potential legal liability, user trust loss, project failure
  - *Mitigation*: Extensive testing (unit, integration, property-based), mandatory paper trading validation phase, circuit breakers and position limits, comprehensive audit logging, clear disclaimers and risk warnings, phased rollout to trusted users first

- **Temporal Isolation Violations (High Impact, Low Probability)**:
  - *Description*: Subtle bugs introduce lookahead bias or data leakage, producing biased backtests
  - *Impact*: Users deploy strategies based on false confidence, lose money in live trading, project credibility destroyed
  - *Mitigation*: Comprehensive temporal isolation tests, strict timestamp validation, forward-looking data detection, CPCV with purging/embargo, external audits of critical code paths

- **Community Adoption Failure (Medium Impact, Medium Probability)**:
  - *Description*: Open-source community doesn't materialize, limited user adoption, no contributors
  - *Impact*: Maintenance burden on core team, slower development, eventual abandonment
  - *Mitigation*: Excellent documentation from day one, responsive to issues/PRs, clear contribution guidelines, regular blog posts/tutorials, engage existing Zipline community, highlight early adopters

### Open Questions

- **What is the optimal caching strategy for the data catalog?** How do we handle cache invalidation when upstream data changes (e.g., corporate actions, data corrections)?
  - *Decision needed by*: Milestone 3 (Modern Data Architecture)

- **Should Rust integration target Decimal arithmetic first, or indicators/data processing?**
  - *Trade-off*: Decimal optimization highest value but hardest; indicators easier but potentially lower impact
  - *Resolution*: Profile first (Milestone 8), optimize biggest bottleneck identified
  - *Decision needed by*: After Milestone 2 complete (Decimal implemented in Python)

- **How do we handle broker API rate limits without degrading user experience?**
  - *Options*: Aggressive caching, request queuing, user-configurable rate limit buffers
  - *Decision needed by*: Milestone 6 (Live Trading)

- **Should we build a full web dashboard, or focus on Jupyter notebook integration?**
  - *Trade-off*: Web dashboard (wider appeal, more work) vs. Jupyter (Python-native, faster development)
  - *Resolution*: Start with Jupyter + programmatic reports (Milestone 10), optional Streamlit dashboard if user demand
  - *Decision needed by*: Milestone 10 (Analytics)

### Areas Needing Further Research

- **Decimal Performance Profiling**: Benchmark Zipline with Decimal to identify hottest paths and estimate Rust optimization targets
- **Broker API Reliability**: Research reliability of ib_async, binance-connector, pybit, hyperliquid SDK (uptime, breaking changes, community support)
- **CPCV Implementation**: Study López de Prado's Combinatorially Purged Cross-Validation in depth for correct implementation
- **User Interviews**: Talk to 20+ quantitative traders about pain points, feature priorities, willingness to switch platforms
- **Competitive Landscape**: Evaluate emerging platforms (new entrants since 2025)

---

## Next Steps

### Immediate Actions (Milestone 1 Start)

1. **Fork repository and set up development environment**
   - Fork github.com/stefan-jansen/zipline-reloaded
   - Create RustyBT repository (public or private)
   - Set up Python 3.12 environment
   - Install dependencies (Polars, Hypothesis, pytest, mypy)

2. **Configure CI/CD pipeline**
   - GitHub Actions workflow (tests, linting, coverage, type checking)
   - Coverage tracking (maintain ≥90% target)
   - Automated benchmarking (performance regression detection)

3. **Map existing architecture**
   - Document module structure (data, execution, performance, pipeline)
   - Identify modification points for Tier 1 features
   - Create architecture diagram

4. **Begin Tier 1 extensions**
   - Start with data pipeline enhancements (extend bundle system)
   - Add advanced order types (Stop-Loss, Stop-Limit, Trailing Stop)
   - Implement additional performance metrics (Sortino, Calmar, CVaR)

5. **Establish testing standards**
   - Write property-based tests for existing financial calculations
   - Set up temporal isolation test framework
   - Document testing best practices

---

## Appendices

### A. Technology Research Summary

**Polars vs. Pandas Analysis**:
- **Performance**: Polars 5-10x faster for common operations (filtering, aggregations, CSV loading), 22x faster for some aggregations
- **Memory**: Polars uses 2-4x dataset size vs. Pandas 5-10x (example: 179MB vs. 1.4GB)
- **Architecture**: Polars written in Rust with parallel execution, lazy evaluation, query optimization; Pandas single-core Python
- **Ecosystem**: Pandas superior for ML library integration (scikit-learn, XGBoost expect Pandas); Polars growing rapidly with plotly, matplotlib, seaborn, altair support
- **Decision**: Polars for data catalog (performance critical), conversion layer for ML if needed

**Broker Integration Libraries**:
- **Interactive Brokers**: ib_async (successor to ib_insync, actively maintained, Pythonic API)
- **Binance**: binance-connector 3.12.0 (official, released January 2025, supports Spot/Futures/WebSocket)
- **Bybit**: pybit (official, supports V5 unified API, derivatives and spot)
- **Hyperliquid**: hyperliquid-python-sdk (official DEX SDK, Python 3.9-3.13, CCXT also supports)
- **CCXT**: v4.x+ (100+ exchanges, unified API, multiple languages, MIT license, actively maintained)

**Latest Stable Versions (September 2025)**:
- Python 3.12.11 (June 2025, security fixes only stage)
- Rust 1.90 (latest stable)
- PyO3 0.26.0 (August 2025, Python 3.14t free-threaded support)
- rust-decimal 1.37.2 (June 2025)
- Polars 1.x (latest stable)
- CCXT v4.x+ (active development, commit activity through September 2025)

### B. Stakeholder Input

**Primary Stakeholder**: Project lead (quantitative trader)
- **Priority**: Financial accuracy (Decimal arithmetic) and temporal isolation (unbiased backtests) over performance
- **Use case**: Self-hosted platform for proprietary strategy development (stocks, crypto, futures)
- **Constraint**: Individual or small team initially (limited resources)
- **Philosophy**: Python-first, local development, no vendor lock-in

**Clarifications from User**:
- Individual traders first (institutions secondary)
- Backward compatibility with Zipline not required (fork is development accelerator only)
- Rust optimization comes after profiling (don't optimize prematurely)
- Business model deferred (focus on building excellent product first)
- Use trusted broker libraries, fork if more control needed
- Web support unnecessary (Python-native framework, local development)
- Milestones based on progress, not arbitrary time periods

### C. References

**Core Documentation**:
- Zipline-Reloaded: https://zipline.ml4trading.io/
- Zipline-Reloaded GitHub: https://github.com/stefan-jansen/zipline-reloaded
- PyO3 Documentation: https://pyo3.rs/
- rust-decimal: https://docs.rs/rust_decimal/
- Polars: https://pola-rs.github.io/polars/

**Broker Libraries**:
- ib_async: https://github.com/ib-api-reloaded/ib_async
- binance-connector: https://github.com/binance/binance-connector-python
- pybit: https://github.com/bybit-exchange/pybit
- hyperliquid-python-sdk: https://github.com/hyperliquid-dex/hyperliquid-python-sdk
- CCXT: https://github.com/ccxt/ccxt

**Books & Research**:
- "Machine Learning for Algorithmic Trading" - Stefan Jansen (Zipline-Reloaded maintainer)
- "Advances in Financial Machine Learning" - Marcos López de Prado (CPCV, overfitting prevention)
- "Algorithmic Trading" - Ernie Chan

**Technical Tools**:
- Hypothesis (property-based testing): https://hypothesis.readthedocs.io/
- PyArrow: https://arrow.apache.org/docs/python/
- Ray (distributed computing): https://www.ray.io/

---

**Document Status**: Draft for Review
**Next Review Date**: 2025-10-07
**Approver**: Project Lead

---

*Generated by Business Analyst Mary 📊*
*Based on brainstorming session results from 2025-09-30 and comprehensive technology research*
