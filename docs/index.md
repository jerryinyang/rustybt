# RustyBT Documentation Index

**Complete documentation index for RustyBT framework**

Last Updated: 2025-10-13

---

## 🚀 Getting Started

### New Users

Start here if you're new to RustyBT:

1. **[README.md](../README.md)** - Project overview and quick start
2. **[Installation Guide](guides/installation-guide.md)** - Setup instructions
3. **[Your First Backtest](tutorials/first-backtest.md)** - Tutorial
4. **[Example Gallery](../examples/README.md)** - Working examples

### Quick Links

- 📖 [API References](#api-references)
- 📚 [User Guides](#user-guides)
- 💡 [Examples](#examples)
- 🏗️ [Architecture](#architecture-documentation)
- 📋 [Stories & PRD](#-stories-prd)

---

## 📖 API References

Complete API documentation for all modules:

### Core APIs

- **[Live Trading API](api/live-trading-api.md)** ⭐ NEW
  - LiveTradingEngine
  - Broker adapters (Binance, Bybit, IB, etc.)
  - Position reconciliation
  - Shadow trading
  - Circuit breakers

- **[Optimization API](api/optimization-api.md)** ⭐ NEW
  - Grid/Random/Bayesian/Genetic algorithms
  - Walk-forward optimization
  - Parallel optimization
  - Sensitivity analysis

- **[Analytics API](api/analytics-api.md)** ⭐ NEW
  - Report generation (PDF/HTML)
  - Performance attribution
  - Risk analytics
  - Trade analysis

- **[DataSource API](api/datasource-api.md)**
  - Data adapter interface
  - Built-in adapters (YFinance, CCXT, Polygon, etc.)
  - Custom adapter development

### Supporting APIs

- **[Caching API](api/caching-api.md)**
  - Cache management
  - Freshness strategies
  - Performance optimization

- **[Bundle Metadata API](api/bundle-metadata-api.md)**
  - Bundle management
  - Quality metrics
  - Validation

- **[Order Types API](api/order-types.md)**
  - Market/Limit/Stop orders
  - Advanced order types
  - Order execution

### Coming Soon

- **[Finance API](api/finance-api.md)** - Decimal ledger, commission, slippage (coming soon)
- **[Algorithm API](api/algorithm-api.md)** - TradingAlgorithm class reference (coming soon)
- **[Pipeline API](api/pipeline-api.md)** - Pipeline framework (coming soon)

---

## 📚 User Guides

Step-by-step guides for common tasks:

### Data Management

- **[Data Ingestion Guide](guides/data-ingestion.md)** - Complete guide to ingesting data
- **[Caching Guide](guides/caching-guide.md)** - Optimize performance with caching
- **[CSV Data Import](guides/csv-data-import.md)** - Import custom CSV data
- **[Creating Data Adapters](guides/creating-data-adapters.md)** - Build custom adapters
- **[Migrating to Unified Data](guides/migrating-to-unified-data.md)** - Migration guide
- **[Data Validation Guide](guides/data-validation.md)** - Validate data quality

### Live Trading

- **[Broker Setup Guide](guides/broker-setup-guide.md)** ⭐ NEW - Complete broker setup
- **[Live vs Backtest Data](guides/live-vs-backtest-data.md)** - Understand the differences
- **[Testnet Setup Guide](guides/testnet-setup-guide.md)** - Test before live trading
- **[WebSocket Streaming Guide](guides/websocket-streaming-guide.md)** - Real-time data (coming soon)

### Production Readiness

- **[Exception Handling Guide](guides/exception-handling.md)** - Robust error handling
- **[Audit Logging Guide](guides/audit-logging.md)** - Structured logging
- **[Type Hinting Guide](guides/type-hinting.md)** - Type safety with mypy
- **[Decimal Precision Configuration](guides/decimal-precision-configuration.md)** - Financial accuracy

### Advanced Topics

- **[Pipeline API Guide](guides/pipeline-api-guide.md)** - Factor analysis (coming soon)
- **[Optimization Guide](guides/optimization-guide.md)** - Parameter tuning (coming soon)

---

## 💡 Examples

Runnable code examples for learning:

### Data Ingestion

- [ingest_yfinance.py](../examples/ingest_yfinance.py) - Yahoo Finance data
- [ingest_ccxt.py](../examples/ingest_ccxt.py) - Crypto data via CCXT
- [backtest_with_cache.py](../examples/backtest_with_cache.py) - Caching demo
- [cache_warming.py](../examples/cache_warming.py) - Cache optimization
- [custom_data_adapter.py](../examples/custom_data_adapter.py) ⭐ NEW - Custom adapter

### Live Trading

- [live_trading.py](../examples/live_trading.py) - Full live trading
- [live_trading_simple.py](../examples/live_trading_simple.py) - Simple version
- [paper_trading_simple.py](../examples/paper_trading_simple.py) - Paper trading
- [shadow_trading_simple.py](../examples/shadow_trading_simple.py) - Shadow mode
- [custom_broker_adapter.py](../examples/custom_broker_adapter.py) - Custom broker (coming soon)
- [websocket_streaming.py](../examples/websocket_streaming.py) - WebSocket streaming (coming soon)

### Analytics

- [generate_backtest_report.py](../examples/generate_backtest_report.py) - Report generation
- [attribution_analysis_example.py](../examples/attribution_analysis_example.py) - Attribution analysis

### Optimization

- [grid_search_ma_crossover.py](../examples/optimization/grid_search_ma_crossover.py) - Grid search
- [random_search_vs_grid.py](../examples/optimization/random_search_vs_grid.py) - Random search
- [bayesian_optimization_5param.py](../examples/optimization/bayesian_optimization_5param.py) - Bayesian opt
- [genetic_algorithm_nonsmooth.ipynb](../examples/optimization/genetic_algorithm_nonsmooth.ipynb) - Genetic algo
- [parallel_optimization_example.py](../examples/optimization/parallel_optimization_example.py) - Parallel opt
- [walk_forward_analysis.py](../examples/optimization/walk_forward_analysis.py) - Walk-forward
- [sensitivity_analysis.ipynb](../examples/optimization/sensitivity_analysis.ipynb) - Sensitivity
- [noise_infusion_robustness.ipynb](../examples/optimization/noise_infusion_robustness.ipynb) - Robustness

### Advanced Features

- [allocation_algorithms_tutorial.py](../examples/allocation_algorithms_tutorial.py) - Portfolio allocation
- [slippage_models_tutorial.py](../examples/slippage_models_tutorial.py) - Slippage modeling
- [latency_simulation_tutorial.py](../examples/latency_simulation_tutorial.py) - Latency
- [borrow_cost_tutorial.py](../examples/borrow_cost_tutorial.py) - Short selling costs
- [overnight_financing_tutorial.py](../examples/overnight_financing_tutorial.py) - Financing costs
- [pipeline_tutorial.py](../examples/pipeline_tutorial.py) - Pipeline API (coming soon)

### Jupyter Notebooks

See [examples/notebooks/](../examples/notebooks/) for interactive tutorials.

---

## 🏗️ Architecture Documentation

Technical architecture and design decisions:

### Overview

- **[Architecture Overview](architecture/index.md)** - System architecture
- **[Component Architecture](architecture/component-architecture.md)** - Component design
- **[Source Tree](architecture/source-tree.md)** - Directory structure
- **[Tech Stack](architecture/tech-stack.md)** - Technologies used

### Design Decisions

- **[ADR 001: Unified Data Source Abstraction](architecture/decisions/001-unified-data-source-abstraction.md)**
- **[ADR 002: Unified Metadata Schema](architecture/decisions/002-unified-metadata-schema.md)**
- **[ADR 003: Smart Caching Layer](architecture/decisions/003-smart-caching-layer.md)**
- **[ADR 004: Cache Freshness Strategies](architecture/decisions/004-cache-freshness-strategies.md)**
- **[ADR 005: Migration Rollback Safety](architecture/decisions/005-migration-rollback-safety.md)**

### Specific Topics

- **[Live Trading Architecture](architecture/live-trading.md)** - Live engine design
- **[Shadow Trading](architecture/shadow-trading-summary.md)** - Validation system
- **[Data Catalog](architecture/data-catalog.md)** - Data organization
- **[Optimization](architecture/optimization.md)** - Optimization framework
- **[Testing Strategy](architecture/testing-strategy.md)** - Testing approach
- **[Coding Standards](architecture/coding-standards.md)** - Code conventions
- **[Zero Mock Enforcement](architecture/zero-mock-enforcement.md)** - Testing philosophy

---

## 📋 Stories & PRD

Product requirements and implementation stories:

### Product Requirements (PRD)

- **[PRD Index](prd/index.md)** - Overview
- **[Epic List](prd/epic-list.md)** - All epics
- **[Epic 1: Foundation](prd/epic-1-foundation-core-infrastructure.md)** ✅ Complete
- **[Epic 2: Decimal Precision](prd/epic-2-financial-integrity-decimal-arithmetic.md)** ✅ Complete
- **[Epic 3: Modern Data Architecture](prd/epic-3-modern-data-architecture-mvp-data-sources.md)** ✅ Complete
- **[Epic 4: Transaction Costs](prd/epic-4-enhanced-transaction-costs-multi-strategy-portfolio.md)** ✅ Complete
- **[Epic 5: Optimization](prd/epic-5-strategy-optimization-robustness-testing.md)** ✅ Complete
- **[Epic 6: Live Trading](prd/epic-6-live-trading-engine-broker-integrations.md)** ✅ Complete
- **[Epic 7: Performance](prd/epic-7-performance-optimization-rust-integration.md)** ✅ Complete
- **[Epic 8: Analytics](prd/epic-8-analytics-production-readiness.md)** ✅ Complete
- **[Epic X1: Unified Data](prd/epic-X1-unified-data-architecture.md)** ✅ Complete
- **[Epic X2: Production Readiness](prd/epic-X2-production-readiness-remediation.story.md)** 🚧 In Progress

### Implementation Stories

Browse by epic:

- **[Epic 1 Stories](stories/completed/)** - Foundation stories (completed)
- **[Epic 6 Stories](stories/)** - Live trading stories (6.1-6.13)
- **[Epic 7 Stories](stories/)** - Performance stories (7.1-7.5)
- **[Epic 8 Stories](stories/)** - Analytics stories (8.1-8.10)
- **[Epic X1 Stories](stories/)** - Unified data stories (X1.1-X1.5)
- **[Epic X2 Stories](stories/)** - Production readiness stories (X2.1-X2.3)

---

## 🔍 Performance & Benchmarking

Performance analysis and optimization:

- **[Benchmarking Suite](performance/benchmarking-suite.md)** - Comprehensive benchmarks
- **[Benchmark Guide](performance/benchmark-guide.md)** - How to run benchmarks
- **[Profiling Setup](performance/profiling-setup.md)** - Profiling tools
- **[Profiling Results](performance/profiling-results.md)** - Performance analysis
- **[Rust Optimizations](performance/rust-optimizations.md)** - Rust integration
- **[Rust Benchmarks](performance/rust-benchmarks.md)** - Rust performance results
- **[Hotspots Analysis](performance/hotspots.md)** - Performance bottlenecks
- **[Decimal Baseline](performance/decimal-baseline.md)** - Decimal performance
- **[Story 7.4 Summary](performance/STORY-7.4-SUMMARY.md)** - Validation results

---

## 🧪 Testing & QA

Quality assurance and testing:

### Testing Docs

- **[Testing Strategy](architecture/testing-strategy.md)** - Overall strategy
- **[Property-Based Testing](testing/property-based-testing.md)** - Hypothesis testing
- **[Zero Mock Enforcement](architecture/zero-mock-enforcement.md)** - No mocks policy

### QA Reports

- **[QA Improvements Summary](qa/QA-IMPROVEMENTS-SUMMARY.md)** - QA enhancements
- **[Test Execution Results](qa/TEST-EXECUTION-RESULTS.md)** - Test results
- **[Enhancements Summary](qa/ENHANCEMENTS-SUMMARY.md)** - Improvements made

### QA Gates

Quality gates for each story (see [qa/gates/](qa/gates/)):
- Story 6.1-6.13 QA gates
- Story 7.1-7.5 QA gates
- Story 8.1-8.10 QA gates
- Story X1.1-X1.5 QA gates
- Story X2.1-X2.3 QA gates

---

## 📄 Pull Request Documentation

Detailed documentation for significant pull requests:

- **[PR Documentation Index](pr/README.md)** - Overview and naming conventions

### 🚨 Critical Issues

- **[2025-10-13: CI/CD Blocking Issues](pr/2025-10-13-CI-BLOCKING-dependency-issues.md)** 🟡 **IN PROGRESS**
  - All CI/CD workflows failing due to dependency/build issues
  - ✅ RESOLVED: Numpy/numexpr version conflicts (Python 3.12/3.13)
  - ✅ RESOLVED: Python version classifiers mismatch
  - ❌ BLOCKING: Editable install module import failures
  - Comprehensive analysis with attempted solutions and recommendations

### Recent Implementations

- **[2025-10-13-PR1: Test Suite Implementation](pr/2025-10-13-PR1-335f312-test-suite-implementation.md)** ⭐ NEW
  - Comprehensive test suite for rustybt.lib Cython modules
  - 112 tests covering 2,028 lines of code
  - Issues identified and fixes implemented

---

## 📊 Production Deployment

Production readiness documentation:

- **[Production Checklist](guides/production-checklist.md)** - Pre-launch checklist
- **[Production Readiness Gap Analysis](reviews/production-readiness-gap-analysis.md)** - Gap analysis
- **[Deployment Guide](guides/deployment-guide.md)** - Deployment instructions
- **[Security Audit](reviews/security-audit.md)** - Security review
- **[Troubleshooting Guide](guides/troubleshooting.md)** - Common issues

---

## 📝 Additional Resources

### Documentation Reviews

- **[Comprehensive Documentation Review](reviews/COMPREHENSIVE-DOCUMENTATION-REVIEW-REPORT.md)** ⭐ NEW - Full review
- **[Documentation Examples Review](reviews/documentation-examples-review.md)** - Examples review
- **[Documentation Fixes Summary](reviews/documentation-fixes-summary.md)** - Recent fixes

### Other

- **[Deprecation Timeline](prd/deprecation-timeline.md)** - Deprecated features
- **[Caching System](guides/caching-system.md)** - Cache architecture
- **[Epic 3 Implementation Sequence](prd/epic-3-implementation-sequence.md)** - Implementation plan
- **[Architecture (Full)](architecture.md)** - Complete architecture doc
- **[PRD (Full)](prd.md)** - Complete PRD document

---

## 🗺️ Learning Paths

### Path 1: Backtesting (Beginner)

1. Read [README.md](../README.md)
2. Follow [Data Ingestion Guide](guides/data-ingestion.md)
3. Try [ingest_yfinance.py](../examples/ingest_yfinance.py)
4. Try [backtest_with_cache.py](../examples/backtest_with_cache.py)
5. Generate report with [generate_backtest_report.py](../examples/generate_backtest_report.py)

### Path 2: Optimization (Intermediate)

1. Complete Path 1 (Backtesting)
2. Read [Optimization API](api/optimization-api.md)
3. Try [grid_search_ma_crossover.py](../examples/optimization/grid_search_ma_crossover.py)
4. Try [bayesian_optimization_5param.py](../examples/optimization/bayesian_optimization_5param.py)
5. Learn [walk_forward_analysis.py](../examples/optimization/walk_forward_analysis.py)

### Path 3: Live Trading (Advanced)

1. Complete Path 1 & 2
2. Read [Live Trading API](api/live-trading-api.md)
3. Read [Broker Setup Guide](guides/broker-setup-guide.md)
4. Setup testnet account
5. Try [paper_trading_simple.py](../examples/paper_trading_simple.py)
6. Try [shadow_trading_simple.py](../examples/shadow_trading_simple.py)
7. Monitor, validate, then go live

### Path 4: Custom Development (Expert)

1. Complete Path 1-3
2. Read [Architecture Overview](architecture/index.md)
3. Try [custom_data_adapter.py](../examples/custom_data_adapter.py)
4. Read [Creating Data Adapters](guides/creating-data-adapters.md)
5. Implement custom broker adapter
6. Contribute back to RustyBT!

---

## 🔗 External Links

- **GitHub Repository**: [github.com/your-org/rustybt](https://github.com/your-org/rustybt)
- **PyPI Package**: [pypi.org/project/rustybt](https://pypi.org/project/rustybt)
- **Documentation Site**: [docs.rustybt.io](https://docs.rustybt.io) (coming soon)
- **Community Discord**: [discord.gg/rustybt](https://discord.gg/rustybt) (coming soon)

---

## 📧 Getting Help

- **Issues**: [GitHub Issues](https://github.com/your-org/rustybt/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/rustybt/discussions)
- **Email**: support@rustybt.io

---

**Last Updated**: 2025-10-13
**Documentation Version**: 0.1.0
**Framework Version**: 0.1.0-dev

---

*This documentation is continuously updated. If you find any issues or have suggestions, please open an issue on GitHub.*
