# Epic 1: Foundation & Core Infrastructure

**Expanded Goal**: Establish the RustyBT development foundation by forking Zipline-Reloaded, setting up comprehensive CI/CD pipeline with testing and coverage tracking, mapping the existing architecture for modification points, and extending Tier 1 features (data pipeline, backtest engine, order management, performance metrics). This epic delivers a functional enhanced backtesting platform with improved order types and metrics, providing immediate value while establishing the quality infrastructure for all subsequent development. Testing, examples, and documentation are integrated throughout.

---

## Story 1.1: Fork Repository and Establish Development Environment

**As a** developer,
**I want** to fork Zipline-Reloaded and set up a clean RustyBT development environment,
**so that** I have a stable foundation to begin implementing enhancements.

### Acceptance Criteria

1. Zipline-Reloaded repository forked from github.com/stefan-jansen/zipline-reloaded to new RustyBT repository
2. Python 3.12+ virtual environment created with all Zipline-Reloaded dependencies installed
3. Additional dependencies installed (Polars, Hypothesis, pytest, mypy, structlog)
4. All existing Zipline-Reloaded tests pass in the forked environment (88.26% baseline coverage confirmed)
5. Git repository configured with appropriate .gitignore for Python, IDE files, and build artifacts
6. README updated with RustyBT branding and initial project description
7. Development environment setup documented in CONTRIBUTING.md

---

## Story 1.2: Configure CI/CD Pipeline

**As a** developer,
**I want** automated CI/CD pipeline with testing, linting, coverage tracking, and type checking,
**so that** code quality is enforced automatically and regressions are caught early.

### Acceptance Criteria

1. GitHub Actions workflow created for pull request validation
2. Automated test suite execution on every commit (pytest with parallel execution)
3. Code coverage tracking configured (Coverage.py) with ≥90% threshold enforcement
4. Type checking integrated (mypy --strict mode) with failures blocking merge
5. Linting configured (ruff or pylint) with consistent code style enforcement
6. Coverage reports uploaded to Codecov or similar service for visualization
7. Build status badge added to README showing CI/CD status
8. Workflow runs successfully on Linux, macOS, and Windows environments

---

## Story 1.3: Map Existing Architecture and Identify Extension Points

**As a** developer,
**I want** comprehensive documentation of Zipline-Reloaded's architecture and identified modification points,
**so that** I understand where to implement Tier 1 enhancements without breaking existing functionality.

### Acceptance Criteria

1. Architecture diagram created showing major modules (data, execution, performance, pipeline, trading calendar)
2. Module dependency map documented showing relationships between components
3. Extension points identified for Tier 1 features (data pipeline, order types, performance metrics)
4. Data flow documented from ingestion → storage → backtest → performance calculation
5. Test coverage map shows which modules have high coverage (safe to modify) vs. low coverage (risky)
6. Key classes and interfaces documented (TradingAlgorithm, DataPortal, Blotter, PerformanceTracker)
7. Architecture documentation saved to docs/architecture/ for architect reference

---

## Story 1.4: Extend Data Pipeline with Metadata Tracking

**As a** quantitative trader,
**I want** enhanced data bundle system with metadata tracking for data provenance,
**so that** I can trace data sources, validate data quality, and understand data lineage.

### Acceptance Criteria

1. Metadata schema extended to track data source, fetch timestamp, version, and checksum for each bundle
2. Bundle ingestion records provenance metadata (source URL, API version, download time)
3. Data quality metadata stored (row count, date range, missing data gaps, outlier count)
4. Metadata queryable via Python API (e.g., `catalog.get_bundle_metadata('my_bundle')`)
5. Timezone handling improved with explicit UTC storage and conversion helpers
6. Gap detection implemented to identify missing trading days in continuous datasets
7. All metadata stored in SQLite catalog database with indexed queries
8. Tests validate metadata correctness for sample bundle ingestion

---

## Story 1.5: Add Advanced Order Types

**As a** quantitative trader,
**I want** support for Stop-Loss, Stop-Limit, Trailing Stop, OCO, and Bracket orders,
**so that** I can implement realistic risk management strategies in backtests.

### Acceptance Criteria

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

## Story 1.6: Implement Additional Performance Metrics

**As a** quantitative trader,
**I want** advanced performance metrics (Sortino, Calmar, CVaR, VaR, win rate, profit factor),
**so that** I can comprehensively evaluate strategy risk-adjusted returns and robustness.

### Acceptance Criteria

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

## Story 1.7: Enhance Backtest Engine Event System

**As a** developer,
**I want** improved event system with custom triggers and sub-second resolution support,
**so that** the engine can support high-frequency strategies and flexible event-driven logic.

### Acceptance Criteria

1. Simulation clock extended to support millisecond and microsecond resolutions
2. Custom event triggers implementable via plugin API (e.g., `on_price_threshold`, `on_time_interval`)
3. Event priority system implemented to control event processing order within same timestamp
4. Event system maintains temporal isolation (events cannot see future data)
5. Real-time mode switching capability added for live trading preparation
6. Performance impact measured: sub-second resolution adds <10% overhead vs. daily resolution
7. Tests validate event ordering and temporal isolation with sub-second data
8. Example strategy demonstrates custom event trigger usage

---
