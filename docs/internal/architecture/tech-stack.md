# Tech Stack

## Existing Technology Stack (Preserved from Zipline-Reloaded)

| Category | Technology | Version | Purpose | RustyBT Status |
|----------|-----------|---------|---------|----------------|
| **Language** | Python | 3.12+ | Primary development language | ✅ Keep (require 3.12+ for modern features) |
| **Package Manager** | uv | 0.5.x+ | Fast Python package installer | ✅ Required (10-100x faster than pip) |
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

## New Technology Additions (RustyBT Enhancements)

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

## Technology Stack Rationale

### uv as Package Manager
- **Speed**: 10-100x faster than pip for package installation and resolution
- **Deterministic**: Lockfile-based dependency resolution for reproducible builds
- **Modern**: Written in Rust, actively developed by Astral (creators of ruff)
- **Developer Experience**: Single tool for virtual environment and package management
- **CI/CD Performance**: Significantly reduces GitHub Actions build times

### Polars over Pandas
- **Performance**: 5-10x faster for large datasets, lazy evaluation, parallel execution
- **Memory**: Columnar memory layout, efficient for OHLCV data
- **Interoperability**: Arrow backend enables zero-copy with Parquet
- **Modern**: Active development, first-class Rust core

### Parquet over bcolz/HDF5
- **Standardization**: Industry-standard columnar format (Apache Arrow ecosystem)
- **Size**: 50-80% smaller than HDF5 with comparable compression
- **Interoperability**: Works with Spark, DuckDB, Polars, pandas, countless tools
- **Maintenance**: Active ecosystem vs. bcolz (unmaintained since 2018)

### FastAPI for REST API (Epic 9)
- **Performance**: Comparable to Go/Node.js, async-native
- **Developer Experience**: Auto-generated OpenAPI docs, Pydantic validation
- **Modern**: Type hints, async/await, WebSocket support

### Multiple Broker Libraries (Not Just CCXT)
- **Flexibility**: CCXT for broad exchange support, native SDKs for performance/features
- **Reliability**: Native SDKs often more stable, better error handling
- **Features**: Native SDKs expose exchange-specific features CCXT doesn't standardize

## Removed Technologies (Deprecated from Zipline)

| Technology | Reason for Removal |
|------------|-------------------|
| **bcolz-zipline** | Unmaintained since 2018, replaced by Parquet/Polars |
| **h5py / tables (PyTables)** | Slow for large datasets, poor interoperability, replaced by Parquet |
| **pandas** (as primary) | Still supported for compatibility but Polars is primary |
| **numpy** (for storage) | Still used for numerical operations but not primary data structure |
| **Cython** (for new code) | Rust provides better performance and safety, keep existing Cython modules until profiled |

---
