# Technical Assumptions

## Repository Structure: Monorepo

RustyBT will use a **Monorepo** structure containing:
- Python package (rustybt core)
- Rust performance modules (optional, added post-profiling)
- Documentation and examples
- Integration tests

**Rationale**: Monorepo simplifies dependency management between Python and Rust components, enables atomic cross-component changes, and provides unified CI/CD. Given the tight integration between Python and Rust optimization layers, separate repositories would create versioning complexity.

## Service Architecture

**Monolithic Python Library with Optional Rust Extensions**

The platform is fundamentally a Python library (not a service) with optional Rust-optimized modules for performance-critical paths identified through profiling.

**Rationale**:
- Target users (individual traders, small teams) prefer local development and self-hosted deployment
- Library architecture maintains flexibility - users can embed in Jupyter notebooks, scripts, or build services on top
- Rust integration via PyO3 remains seamless within monorepo structure
- Aligns with "Python-first philosophy" from brief (Rust only for profiled bottlenecks)

## Testing Requirements

**Comprehensive Testing Pyramid with Property-Based Testing**

Testing, examples, and documentation creation are integrated throughout all epics, not isolated in a single epic:

- **Unit Tests**: ≥90% overall coverage, ≥95% for financial modules (pytest)
- **Property-Based Tests**: Financial calculations validated with Hypothesis framework
- **Integration Tests**: End-to-end backtest scenarios, broker integration tests with paper accounts
- **Regression Tests**: Performance benchmarking to prevent degradation
- **Temporal Isolation Tests**: Lookahead bias detection, forward-looking data prevention

**Rationale**: Given the financial nature and live trading risk, comprehensive testing is non-negotiable. Property-based testing is critical for Decimal arithmetic validation. High coverage inherits from Zipline-Reloaded's 88.26% foundation.

## Additional Technical Assumptions and Requests

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
