# Epic 7: Performance Optimization - Rust Integration

**Expanded Goal**: Profile Python implementation to identify bottlenecks consuming >5% of backtest time (not limited to Decimal arithmetic - includes loops, subprocesses, data processing, indicator calculations), then reimplement hot paths in Rust for performance. Target <30% overhead vs. float baseline (subject to profiling validation), validated through comprehensive benchmarking suite integrated into CI/CD. Testing, benchmarking, and documentation integrated throughout.

**⚠️ CRITICAL DEPENDENCY**: **Epic X1: Unified Data Architecture) must complete before Epic 7 can begin**.
- Epic 7 requires profiling bundles with realistic backtest data
- Current adapter infrastructure cannot create bundles (Epic X1 Story X1.1 resolves this)
- See [epic-X1-unified-data-architecture.md](epic-X1-unified-data-architecture.md) for details

**Epic Sequence**: Epic 8 → Epic 7

---

## Epic 8 Dependency (BLOCKER)

**Why Epic 7 is Blocked**:
- Story 7.1 (Profiling) requires representative backtest datasets:
  - Daily scenario: 50 stocks, 2 years
  - Hourly scenario: 20 crypto, 6 months
  - Minute scenario: 10 crypto, 1 month
- Current state: Adapters (YFinance, CCXT) fetch data but **cannot create bundles**
- No bundles = No profiling = Epic 7 cannot proceed

**Epic 8 Resolves**:
- Story X1.1 (1-2 days): Adapter-Bundle Bridge
  - Creates 3 profiling bundles using existing adapters
  - Unblocks Story 7.1 immediately
- Stories 8.2-8.5 (3 weeks): Full unified architecture
  - Optional for Epic 7, but improves long-term data management

**Recommended Approach**:
1. Complete Epic X1 Story X1.1 (Adapter-Bundle Bridge) - **1-2 days**
2. Begin Epic 7 (Profiling) - unblocked
3. Complete Epic X1 Stories X1.2-X1.5 in parallel or after Epic 7

---

## ~~Story 7.0: Unified Data Management Architecture~~

**Moved to Epic X1**. See [epic-X1-unified-data-architecture.md](epic-X1-unified-data-architecture.md).

Original Story 7.0 content has been restructured into Epic X1 Stories:
- Story X1.1: Adapter-Bundle Bridge (unblocks Epic 7)
- Story X1.2: Unified DataSource Abstraction
- Story X1.3: Smart Caching Layer
- Story X1.4: Unified Metadata Management
- Story X1.5: Integration and Documentation

---

**As a** developer,
**I want** unified data management architecture integrating Adapters, Bundles, and Catalog systems,
**so that** data sourcing, storage, and retrieval is fluid, scalable, and optimized for both backtesting and live trading.

### Acceptance Criteria

**Phase 1: Adapter-Bundle Bridge (Story 7.1 Unblocking - 1-2 days)**
1. Create adapter bridge module with helper functions for bundle creation from adapters
2. Implement `yfinance_profiling_bundle()` using YFinanceAdapter (50 stocks, 2 years, daily)
3. Implement `ccxt_hourly_profiling_bundle()` using CCXTAdapter (20 crypto, 6 months, hourly)
4. Implement `ccxt_minute_profiling_bundle()` using CCXTAdapter (10 crypto, 1 month, minute)
5. All profiling bundles automatically track metadata via `track_api_bundle_metadata()`
6. CLI command `rustybt ingest yfinance-profiling` creates profiling bundle
7. Integration tests validate end-to-end adapter → bundle → DataPortal flow
8. Documentation explains bridge pattern and usage

**Phase 2: Unified DataSource Abstraction (1 week)**
9. Create `DataSource` ABC with interface: `fetch()`, `ingest_to_bundle()`, `get_metadata()`, `supports_live()`
10. Refactor all 6 adapters to implement `DataSource` (backwards compatible)
11. Create `DataSourceRegistry` for dynamic source discovery
12. Unified CLI: `rustybt ingest <source> --bundle <name> [options]`
13. Single code path for all bundle creation (eliminates duplication)

**Phase 3: Smart Caching Layer (1 week)**
14. Create `CachedDataSource` wrapper with automatic cache lookup
15. Cache hit: read from Parquet (fast path), cache miss: fetch + write + catalog update
16. Cache freshness policies: daily (market close), hourly (1h), minute (5m)
17. LRU cache eviction with configurable max size (default 10GB)
18. Async cache warming pre-fetches next day's data
19. Cache statistics tracking (hit rate, latency)
20. Cache invalidation on data quality failure

**Phase 4: Unified Metadata Management (1 week)**
21. Merge `DataCatalog` and `ParquetMetadataCatalog` into `UnifiedCatalog`
22. Schema includes: datasets, symbols, date ranges, provenance, quality metrics, file metadata
23. Migration script converts old catalogs to unified catalog
24. CLI commands: `rustybt catalog list|info|validate`
25. Backwards compatibility with deprecation warnings

**Phase 5: Integration and Documentation (3 days)**
26. Update `PolarsDataPortal` to use `CachedDataSource`
27. Update `TradingAlgorithm` to accept `data_source` parameter
28. Live trading uses adapters directly, backtest uses cached sources
29. Architecture docs, user guides, migration guides, API reference
30. Example scripts and deprecation plan

---

## Story 7.1: Profile Python Implementation to Identify Bottlenecks

**Dependencies**: Story 7.0 Phase 1 must complete first (profiling bundles required)

**As a** developer,
**I want** comprehensive profiling of Python implementation,
**so that** I can identify the highest-impact targets for Rust optimization.

### Acceptance Criteria

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

## Story 7.2: Set Up Rust Integration with PyO3

**As a** developer,
**I want** Rust project integrated with Python via PyO3 and maturin,
**so that** I can write Rust modules callable from Python seamlessly.

### Acceptance Criteria

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

## Story 7.3: Implement Rust-Optimized Modules for Profiled Bottlenecks

**As a** developer,
**I want** Rust reimplementation of profiled bottlenecks,
**so that** performance overhead is reduced to target levels.

### Acceptance Criteria

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

## Story 7.4: Validate Performance Target Achievement

**As a** developer,
**I want** validation that Rust optimizations achieve <30% overhead vs. float baseline,
**so that** we confirm Decimal viability for production use.

### Acceptance Criteria

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

## Story 7.5: Implement Comprehensive Benchmarking Suite

**As a** developer,
**I want** extensive benchmark suite tracking performance across releases,
**so that** regressions are caught early and optimizations validated.

### Acceptance Criteria

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
