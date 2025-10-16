# Epic 2: Financial Integrity - Decimal Arithmetic

**Expanded Goal**: Implement financial-grade Decimal arithmetic throughout the entire RustyBT platform, replacing all float-based calculations with configurable-precision Decimal in the core calculation engine, order execution system, performance metrics, and data pipelines. This epic establishes audit-compliant financial accuracy with zero rounding errors, validated through comprehensive property-based testing, and establishes performance baselines for future Rust optimization (Epic 7). This is the foundational differentiator that enables production deployment with financial integrity. Testing, examples, and documentation are integrated throughout.

---

## Story 2.1: Design Decimal Precision Configuration System

**As a** developer,
**I want** a configurable precision management system for Decimal arithmetic,
**so that** different asset classes (crypto, equities, forex, futures) can use appropriate precision per data provider specifications.

### Acceptance Criteria

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

## Story 2.2: Replace Float with Decimal in Core Calculation Engine

**As a** quantitative trader,
**I want** portfolio value, position sizing, and returns calculations to use Decimal,
**so that** my account balances and performance metrics are financially accurate with zero rounding errors.

### Acceptance Criteria

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

## Story 2.3: Replace Float with Decimal in Order Execution System

**As a** quantitative trader,
**I want** order prices, quantities, commissions, and slippage to use Decimal,
**so that** order execution accuracy matches real-world broker precision.

### Acceptance Criteria

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

## Story 2.4: Replace Float with Decimal in Performance Metrics

**As a** quantitative trader,
**I want** all performance metrics (Sharpe, Sortino, drawdown, VaR, etc.) calculated with Decimal,
**so that** performance reporting is audit-compliant and financially accurate.

### Acceptance Criteria

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

## Story 2.5: Replace Float with Decimal in Data Pipelines

**As a** quantitative trader,
**I want** price data (OHLCV) stored and processed as Decimal throughout data pipelines,
**so that** historical data maintains full precision from source to backtest execution.

### Acceptance Criteria

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

## Story 2.6: Implement Property-Based Testing for Financial Calculations

**As a** developer,
**I want** comprehensive property-based tests using Hypothesis framework,
**so that** Decimal implementation correctness is validated across wide input ranges.

### Acceptance Criteria

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

## Story 2.7: Document Performance Baselines for Rust Optimization

**As a** developer,
**I want** comprehensive performance benchmarks comparing Decimal vs. float implementations,
**so that** Epic 7 (Rust optimization) has clear targets for optimization efforts.

### Acceptance Criteria

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
