# Changelog

All notable changes to RustyBT will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Documentation deployment via GitHub Pages and ReadTheDocs
- Comprehensive MkDocs-based documentation site
- GitHub Actions workflow for automatic documentation deployment

## [0.1.0] - 2024-10-XX (In Development)

### Epic 5: Strategy Optimization ✅ Complete

#### Added
- Grid search optimization algorithm
- Random search optimization algorithm
- Bayesian optimization using Gaussian processes
- Genetic algorithm optimization with DEAP
- Parallel processing framework for optimization
- Walk-forward optimization with rolling windows
- Parameter sensitivity and stability analysis
- Monte Carlo data permutation for robustness testing
- Monte Carlo noise infusion for strategy validation

### Epic 4: Transaction Costs & Multi-Strategy ✅ Complete

#### Added
- Latency simulation for realistic execution modeling
- Partial fill model with configurable fill rates
- Multiple slippage models (fixed, percentage, volume-based, market impact)
- Tiered commission models with volume-based pricing
- Borrow cost model for short selling
- Overnight financing for leveraged positions
- Portfolio allocator for multi-strategy management
- Capital allocation algorithms (equal-weight, volatility-parity, risk-parity)
- Cross-strategy risk management
- Order aggregation and netting across strategies

### Epic 3: Modern Data Architecture ✅ Complete

#### Added
- Unified data catalog architecture with Parquet storage
- Intelligent local caching system with freshness strategies
- Base data adapter framework with standardized interface
- CCXT data adapter for cryptocurrency exchanges
- yFinance data adapter for traditional equities
- CSV data adapter with schema mapping
- Multi-resolution aggregation with OHLCV validation

### Epic 2: Decimal Precision ✅ Complete

#### Added
- Decimal precision configuration system
- Decimal arithmetic in core calculation engine
- Decimal support in order execution system
- Decimal integration in data pipelines
- Property-based testing for financial calculations using Hypothesis
- Performance baselines for Rust optimization planning

### Epic 1: Foundation ✅ Complete

#### Added
- Forked repository from Zipline-Reloaded
- CI/CD pipeline configuration with GitHub Actions
- Architecture mapping and extension points identification
- Data pipeline with metadata tracking
- Advanced order types (stop-loss, take-profit, trailing-stop, OCO, bracket)
- Additional performance metrics (Sortino, Calmar, Omega ratios)
- Enhanced backtest engine event system

#### Changed
- Updated Python requirement to 3.12+
- Migrated data engine from pandas to Polars
- Replaced bcolz/HDF5 with Parquet storage

## Release History

### Version Numbering

RustyBT follows semantic versioning:
- **Major**: Breaking API changes
- **Minor**: New features, backward compatible
- **Patch**: Bug fixes, backward compatible

### Planned Releases

- **0.1.0**: MVP with Epics 1-5 (current development)
- **0.2.0**: Live trading support (Epic 6)
- **0.3.0**: Analytics and production readiness (Epic 8)
- **0.4.0**: Rust optimizations (Epic 7)
- **1.0.0**: Production-ready stable release

## Migration Guides

### From Zipline-Reloaded

RustyBT maintains API compatibility with Zipline-Reloaded for most use cases:

```python
# Your existing Zipline strategies work as-is
from rustybt.api import order_target, record, symbol

def initialize(context):
    context.asset = symbol('AAPL')

def handle_data(context, data):
    order_target(context.asset, 100)
```

#### Key Differences

1. **Data Format**: Parquet instead of bcolz
2. **Numeric Type**: Decimal instead of float64 (optional, configurable)
3. **Data Engine**: Polars instead of pandas (pandas compatible)

See [Migration Guide](../guides/migrating-to-unified-data.md) for detailed instructions.

## Links

- [GitHub Repository](https://github.com/jerryinyang/rustybt)
- [Documentation](https://rustybt.readthedocs.io)
- [Issue Tracker](https://github.com/jerryinyang/rustybt/issues)
- [Discussions](https://github.com/jerryinyang/rustybt/discussions)
