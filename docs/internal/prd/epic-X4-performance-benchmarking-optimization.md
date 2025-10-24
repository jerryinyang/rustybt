# Epic X4: Performance Benchmarking and Optimization - Brownfield Enhancement PRD

**Epic ID**: X4
**Epic Name**: Performance Benchmarking and Optimization
**Branch**: `002-performance-benchmarking-optimization`
**Status**: Phase 3 Complete (36/258 tasks, 14%)
**Created**: 2025-10-22
**Version**: 1.0

---

## Intro Project Analysis and Context

### Existing Project Overview

**Analysis Source**: Document-project output available at `docs/internal/architecture/` + Epic 002 specification at `specs/002-performance-benchmarking-optimization/` + Phase 3 profiling results at `profiling-results/CONSOLIDATED_PROFILING_REPORT.md`

**Key Specification Documents**:
- **Progress Tracking**: `specs/002-performance-benchmarking-optimization/PROGRESS.md` - Current status: 36/258 tasks (14% complete)
- **Optimization Ranking**: `specs/002-performance-benchmarking-optimization/research.md` - Impact-to-effort ratios justifying Phase 6A prioritization
- **Tasks Breakdown**: `specs/002-performance-benchmarking-optimization/tasks.md` - Complete 258-task implementation plan

**Current Project State**:
RustyBT is an event-driven algorithmic trading backtesting platform built on Zipline-Reloaded with modern enhancements including Decimal precision financial calculations, Polars/Parquet data engine (5-10x faster than pandas), live trading capabilities across multiple broker integrations (CCXT, Interactive Brokers, Binance, Bybit, Hyperliquid), and strategy optimization frameworks (Grid Search, Random Search, Bayesian Optimization, Genetic Algorithms, Walk Forward). The platform has completed Epics 1-6 and Epic 8, achieving a production-ready feature set with 88%+ test coverage across 79 test files and 4,000+ test cases.

**Project Architecture**: 12 major modules (40K LOC) following event-driven architecture with `TradingAlgorithm` core engine, `PolarsDataPortal` unified data interface, `DecimalLedger` for financial precision, and `LiveTradingEngine` for production execution.

### Available Documentation Analysis

✅ **Using existing project analysis from document-project output:**

**Documentation Available:**
- ✅ Tech Stack Documentation (Python 3.12+, Polars 1.x, Parquet via pyarrow 18.x, Decimal stdlib, pytest 7.x, Hypothesis 6.x)
- ✅ Source Tree/Architecture (rustybt/ with 12 modules: finance/, data/, live/, assets/, pipeline/, optimization/, analytics/, benchmarks/)
- ✅ Coding Standards (zero-mock enforcement, Decimal precision for financial calculations, Python 3.12+ structural pattern matching)
- ✅ API Documentation (comprehensive inline docstrings, Google-style)
- ✅ External API Documentation (broker integration specs for CCXT, IB, native SDKs)
- ✅ Technical Debt Documentation (profiling results identify 87% user code overhead, 58.4% DataPortal overhead, 40.41% bundle loading fixed costs)
- ✅ Performance Benchmarking Documentation (methodology in docs/internal/benchmarks/methodology.md, flame graphs in profiling-results/flame_graphs/)

**Additional Epic-Specific Documentation:**
- Phase 3 profiling completed: `profiling-results/CONSOLIDATED_PROFILING_REPORT.md` (comprehensive bottleneck analysis with percentage contributions)
- Flame graph visualizations: `profiling-results/flame_graphs/*.svg` (Grid Search, Walk Forward, DataPortal isolation)
- Benchmarking infrastructure: `rustybt/benchmarks/` (7 dataclasses, profiling utilities, threshold evaluation, sequential optimization framework)
- Test coverage: `tests/benchmarks/` (32 tests, 100% pass rate for Phases 1-3)

### Enhancement Scope Definition

#### Enhancement Type
- ✅ **Performance/Scalability Improvements**

**Rationale**: Optimization workflows (Grid Search, Walk Forward) run hundreds of backtests sequentially, causing severe performance bottlenecks in production usage. Each 100-parameter Grid Search takes 1000+ seconds due to repetitive data wrangling operations (87% overhead), inefficient DataFrame construction in DataPortal API (58.4% overhead), and redundant bundle loading per worker (40.41% fixed cost).

#### Enhancement Description
Optimize RustyBT's Grid Search and Walk Forward optimization workflows by eliminating 87% user code data wrangling overhead (asset list caching, data pre-grouping), reducing 58.4% DataPortal framework overhead (NumPy array returns, multi-tier LRU caching), and removing 84% of bundle loading fixed costs (connection pooling) through evidence-based optimizations discovered via comprehensive profiling of production-scale workloads. Target: 90-95% cumulative speedup (3-5x faster, minimum acceptable 40%) while maintaining 100% functional equivalence with <2% memory overhead.

**Key Profiling Findings**:
- **87% user code overhead**: Asset extraction (48.5%), data filtering (39.1%), type conversions (6.1%)
- **58.4% DataPortal overhead**: DataFrame construction (19.35%), calendar ops (20.74%), history windows (17.28%)
- **40.41% bundle loading**: Calendar init (37.78%), bar reader init (37.82%), total 313ms per worker
- **0.6% actual computation**: NumPy operations already optimal (DO NOT optimize further)
- **Overhead-to-computation ratio**: 74:1 (optimization target: <5:1)

#### Impact Assessment
- ✅ **Significant Impact (substantial existing code changes)**

**Details**:
- **New Modules**: `rustybt/optimization/caching.py`, `rustybt/optimization/dataportal_ext.py`, `rustybt/optimization/bundle_pool.py`, `rustybt/optimization/cache_invalidation.py` (Phase 6A optimizations)
- **Modified Modules**: `rustybt/data/data_portal.py` (extend `history()` with `return_type` parameter), `rustybt/data/bundles/core.py` (integrate bundle connection pool), `rustybt/optimization/parallel_optimizer.py` (integrate accepted optimizations)
- **Removed Modules**: `rust/` directory entirely (Rust micro-operations provide <2% end-to-end impact)
- **No Breaking Changes**: Backward-compatible API (default `return_type='dataframe'`), 100% test suite pass rate required
- **Performance-Focused**: Zero functional changes, all optimizations maintain identical results to pure Python baseline

### Goals and Background Context

#### Goals
1. Eliminate 87% user code data wrangling overhead through asset list caching (functools.lru_cache with SHA256 bundle version tracking) and data pre-grouping (asset-indexed NumPy array dict with LRU eviction, 2GB default limit)
2. Reduce 58.4% DataPortal overhead through NumPy array returns (skip DataFrame construction when `return_type='array'`) and multi-tier LRU caching (permanent cache for windows [20, 50, 200], LRU maxsize=256 for variable windows)
3. Remove 84% bundle loading fixed costs through connection pooling (313ms → <50ms worker initialization after first load via singleton BundleConnectionPool with lazy initialization)
4. Achieve 90-95% cumulative speedup in Grid Search and Walk Forward workflows (aspirational target; 40% minimum acceptable)
5. Maintain 100% functional equivalence with zero regressions, <2% memory overhead, and statistical validation (≥10 runs, 95% CI, p<0.05)

#### Background Context
RustyBT is a quantitative finance backtesting framework forked from Zipline-Reloaded with performance bottlenecks in optimization workflows. Grid Search and Walk Forward optimization run hundreds of backtests sequentially (100+ parameter combinations, 5+ windows with 50+ trials each), causing severe slowdowns in production usage where quantitative researchers need rapid strategy iteration.

**Initial Hypothesis (October 21, 2025)**: Rust micro-operations would provide significant speedup. Epic 002 originally planned to leverage existing Rust components (indicators.rs, data_ops.rs, decimal_ops.rs) for performance gains.

**Reality Discovered Through Phase 3 Profiling (October 21-22, 2025)**: Comprehensive profiling of production-scale workloads (Grid Search with 100 backtests, Walk Forward with 5 windows) using cProfile, line_profiler, memory_profiler, and flame graph analysis revealed:

1. **Rust has <2% impact on end-to-end workflows**: Micro-operations (SMA, EMA, window slice, Decimal operations) contribute <1% individually to total workflow time. These operations are already optimal in pure Python using NumPy and Polars (Rust-backed internally).

2. **Real bottlenecks are in data access layer** with overhead-to-computation ratio of 74:1:
   - **User Code Data Wrangling (87% overhead)**: `data['asset'].unique().to_list()` called 100 times (14.85ms each = 1,485ms), data filtering per asset (11.95ms × 100 backtests × 10 assets = 11,950ms), type conversions Polars→NumPy (1.85ms × 100 × 10 = 1,850ms)
   - **Framework DataPortal API (58.4% overhead)**: `history()` called 2,000+ times per workflow with DataFrame construction (0.075ms × 2,002 calls = 150ms), calendar operations (20.74%), history window computation (17.28%)
   - **Bundle Loading Fixed Costs (40.41%)**: Each worker initialization loads bundle from scratch (313ms: 37.78% calendar init + 37.82% bar reader init)

3. **Actual Computation is Only 0.6% of Runtime**: NumPy moving average calculations are already optimal. Optimizing computation further would have negligible impact.

**Critical Insight**: Simple caching and pre-grouping strategies can yield 70%+ gains by eliminating repetitive operations, while framework-level optimizations add another 20-25% through NumPy returns and intelligent caching. This reprioritized the epic from "Rust heavy operations" to "profiling-derived optimizations" (Phase 6A) with heavy operations deferred to Phase 6B.

**This enhancement implements evidence-based optimizations** discovered through comprehensive profiling, targeting the actual bottlenecks rather than assumed ones. Rust micro-operations will be removed entirely (Phase 4), establishing a pure Python baseline for benchmarking.

#### Change Log

| Change | Date | Version | Description | Author |
|--------|------|---------|-------------|--------|
| Initial Creation | 2025-10-22 | v1.0 | Created brownfield PRD for Epic X4 Performance Optimization with profiling-derived targets | PM Agent |

---

## Requirements

### Functional Requirements

**Phase 3 Extension: Heavy Operation Profiling**
- **FR-001**: System SHALL extend profiling scope to heavy operation scenarios not covered by Phase 3 baseline, including batch initialization overhead (100+ backtests, varying bundle sizes 10-500 assets), parallel coordinator efficiency (2-16 workers), BOHB multi-fidelity vs Grid Search, and Ray distributed scheduler vs multiprocessing.Pool

**Phase 4: Rust Removal (BLOCKING for Phase 6A - Establish Pure Python Baseline)**
- **FR-002**: System SHALL identify all actively-used Rust micro-operation functions (indicators.rs: SMA/EMA, data_ops.rs: window_slice/fillna, decimal_ops.rs: sum/multiply) in codebase and document call sites
- **FR-003**: System SHALL implement pure Python replacements using NumPy (indicators), Polars (data operations), and Decimal (precision) with numerically equivalent outputs and syntactically identical APIs
- **FR-004**: System SHALL remove ALL Rust build infrastructure (Cargo.toml, rust/ directory, PyO3 bindings, maturin config, GitHub Actions Rust steps)
- **FR-005**: System SHALL validate Rust removal causes <2% change to end-to-end workflow time, demonstrating Rust micro-operations had negligible impact

**CRITICAL**: Phase 4 MUST be completed before Phase 6A. Pure Python baseline is required for benchmarking all optimization layers.

**Phase 5: Threshold Framework**
- **FR-006**: System SHALL define performance threshold requiring minimum 5% improvement to total end-to-end workflow time on production-scale workloads (100+ backtests, 10+ assets, 1-10 years data)
- **FR-007**: System SHALL implement statistical evaluation with 95% confidence intervals, ≥10 benchmark runs, t-test for significance (p<0.05)

**Phase 6A: Profiling-Derived Optimizations (CRITICAL)**

**Layer 1: User Code Optimizations (70% Target)**
- **FR-008**: Asset list extraction SHALL be cached using @functools.lru_cache with bundle version tracking (SHA256 hash of bundle metadata: asset list + date range + schema version) to eliminate 48.5% overhead (1,485ms → <15ms for 100 backtests)
- **FR-009**: Data SHALL be pre-grouped into asset-indexed dictionary cache (Dict[asset_id, np.ndarray]) with NumPy arrays (shape: n_bars × 5 for OHLCV) and LRU eviction (default 2GB memory limit) to eliminate 45.2% overhead (13,800ms → <140ms: 39.1% filtering + 6.1% conversion)
- **FR-010**: Cache invalidation SHALL trigger on bundle version changes detected via SHA256 hash comparison to prevent stale data errors

**Layer 2: Framework DataPortal Optimizations (20-25% Target)**
- **FR-011**: DataPortal.history() method SHALL support optional `return_type` parameter (Literal['dataframe', 'array'], default='dataframe') to skip DataFrame construction overhead when array-consuming strategies don't need DataFrame features
- **FR-012**: NumPy array construction path SHALL provide direct array slice from internal cache when `return_type='array'`, eliminating 19.35% DataFrame overhead (150ms → <16ms per backtest for 2,000 calls)
- **FR-013**: Multi-tier LRU cache SHALL provide Tier 1 permanent cache (never-evicted common lookback windows: 20, 50, 200 periods) and Tier 2 LRU cache (OrderedDict, maxsize=256, variable windows) with CacheKey structure (asset_id, field, bar_count, end_date)
- **FR-014**: Cache hit/miss rate monitoring SHALL track metrics with hit_rate calculation (hits / (hits + misses)) and export to benchmark reports, targeting >60% cache hit rate

**Layer 3: Bundle Loading Optimizations (8-12% Target)**
- **FR-015**: Bundle connection pool SHALL implement singleton pattern (BundleConnectionPool) with thread-safe access (threading.Lock), lazy initialization, and version-based invalidation (SHA256 checksum) to reduce worker initialization from 313ms to <50ms (84% reduction) after first load

**Phase 6B: Heavy Operation Optimizations (DEFERRED - Conditional)**
- **FR-016**: Heavy operation optimizations are DEFERRED pending Phase 6A validation. IF Phase 6A achieves 90-95% aspirational target, Phase 6B will be SKIPPED. IF Phase 6A does NOT achieve target, THEN evaluate heavy operations sequentially (Shared Bundle Context, Persistent Worker Pool, BOHB Multi-Fidelity, Ray Distributed Scheduler) per research.md ranking (impact-to-effort ratio).

**Testing and Validation (All Phases)**
- **FR-017**: ALL optimizations SHALL maintain 100% functional equivalence validated through comprehensive test suite (existing tests pass without modification) and property-based tests (Hypothesis with 1000+ examples)
- **FR-018**: Performance regression testing SHALL be integrated into CI pipeline with automatic failure on >10% degradation from baseline for production-scale workflows
- **FR-019**: Sequential optimization evaluation framework SHALL accept/reject each optimization based on 5% minimum improvement threshold with 95% CI (≥10 runs, p<0.05)
- **FR-020**: All optimization decisions, profiling results, benchmark data, and selection rationale SHALL be version-controlled in docs/internal/benchmarks/decisions/ with flame graphs and supporting evidence

### Non-Functional Requirements

**Performance Requirements**
- **NFR-001**: Phase 6A Layer 1 (asset caching + pre-grouping) MUST achieve ≥70% speedup in Grid Search and Walk Forward workflows validated through production-scale benchmarks (100+ backtests, 10+ assets, 1-10 years data)
- **NFR-002**: Phase 6A Layer 2 (NumPy returns + multi-tier cache) MUST achieve ≥20% additional speedup beyond Layer 1 gains for array-consuming strategies
- **NFR-003**: Phase 6A Layer 3 (bundle connection pooling) MUST reduce worker initialization time to <50ms from 313ms baseline (≥84% reduction) measured after first load across 10+ runs with 95% CI
- **NFR-004**: Cumulative Phase 6A speedup MUST achieve ≥90% (aspirational target) or ≥40% (minimum acceptable) validated with ≥10 runs, 95% confidence interval, statistical significance p<0.05
- **NFR-005**: Overhead-to-computation ratio MUST improve from 74:1 baseline to <5:1 after Phase 6A optimizations
- **NFR-006**: Each optimization in Phase 6B (if executed) MUST independently meet 5% minimum improvement threshold to be accepted

**Quality Requirements**
- **NFR-007**: Memory overhead from all caching mechanisms MUST remain <2% increase over baseline with configurable limits (default 2GB for pre-grouped data cache, 256 entries for LRU cache)
- **NFR-008**: Cache hit rate for multi-tier LRU cache MUST exceed 60% for common lookback windows (20, 50, 200 bars) measured across production workflows
- **NFR-009**: Test coverage MUST maintain ≥90% overall (≥95% for new benchmarking and optimization modules)
- **NFR-010**: All performance claims MUST be reproducible through independent audit with documented profiling methodology and benchmark scripts

**Validation Requirements**
- **NFR-011**: Property-based tests (Hypothesis) MUST validate cache correctness with 1000+ generated examples covering edge cases (bundle updates, concurrent access, cache eviction)
- **NFR-012**: Rust removal (Phase 4) MUST cause <2% change to end-to-end workflow time, confirming Rust micro-operations had negligible impact
- **NFR-013**: Functional equivalence MUST be validated BEFORE performance measurement for each optimization (BLOCKING requirement)
- **NFR-014**: All accepted optimizations MUST produce identical results to pure Python baseline on comprehensive test suite (100% pass rate)

**Scalability Requirements**
- **NFR-015**: Optimizations MUST work correctly with production-scale datasets (1-10 years OHLCV data, 10-500 assets, daily/minute bars)
- **NFR-016**: Bundle connection pooling MUST function correctly in distributed scenarios (8-16 workers) with thread-safe access
- **NFR-017**: Multi-tier cache MUST handle variable window sizes (1-1000 bars) without performance degradation

### Compatibility Requirements

**API Compatibility**
- **CR-001**: Existing DataPortal API compatibility - `DataPortal.history()` default behavior MUST remain unchanged with `return_type='dataframe'` as default, ensuring zero breaking changes for existing strategies that rely on DataFrame methods (`.mean()`, `.std()`, `.plot()`)
- **CR-002**: Backward compatibility with Rust-enabled baseline - Pure Python baseline MUST maintain identical functional behavior to previous Rust-enabled version validated through existing test suite 100% pass rate (4,000+ tests)
- **CR-003**: TradingAlgorithm API MUST remain consistent after all optimizations - no changes to `initialize()`, `handle_data()`, `before_trading_start()` signatures or behavior

**Framework Consistency**
- **CR-004**: All optimizations MUST follow existing architectural principles: zero-mock enforcement (no hardcoded values), Decimal precision for financial calculations (monetary values use `Decimal` type), event-driven architecture (no mode-specific behavior)
- **CR-005**: Strategy reusability guarantee MUST be preserved - optimizations work identically in backtest, paper, and live modes without mode-specific code paths
- **CR-006**: Type safety excellence MUST be maintained - Python 3.12+ type hints, mypy --strict compliance, Google-style docstrings for all public APIs

**Data and Integration Compatibility**
- **CR-007**: Database schema compatibility - No database schema changes required; all optimizations are in-memory caching and API extensions only
- **CR-008**: Bundle loading optimizations MUST work correctly with all existing bundle formats (Parquet primary, CSV legacy) and data adapters (YFinanceAdapter, CCXTAdapter, CSVAdapter)
- **CR-009**: Multi-tier cache MUST serialize/deserialize Decimal precision correctly when caching financial data (OHLCV prices, portfolio values)

**Testing and Build Compatibility**
- **CR-010**: Testing compatibility - All existing tests MUST pass without modification after Rust removal (Phase 4) and before performance optimizations are applied (Phase 6A baseline)
- **CR-011**: CI/CD compatibility - Framework MUST build successfully without Rust toolchain after Phase 4 (no maturin, no PyO3, no cargo)
- **CR-012**: Python version compatibility - Optimizations MUST maintain Python 3.12+ requirement (constitutional requirement, using structural pattern matching and enhanced type hints)

**Documentation and Migration Compatibility**
- **CR-013**: API documentation MUST be updated for all public API changes (DataPortal.history() `return_type` parameter, optimization configuration)
- **CR-014**: Migration path MUST be documented for users relying on Rust micro-operations (though transparent due to identical API)
- **CR-015**: Performance characteristics documentation MUST explain when to use `return_type='array'` vs default `'dataframe'` based on strategy requirements

---

## Technical Constraints and Integration Requirements

### Existing Technology Stack

**Languages and Core Dependencies**:
- **Python**: 3.12+ (constitutional requirement, structural pattern matching, enhanced type hints)
- **Data Processing**: Polars 1.x (primary, lazy evaluation, 5-10x faster than pandas), NumPy 2.x (numerical operations, array returns), Pandas 2.x (backward compatibility only)
- **Financial Precision**: Decimal (stdlib, audit-compliant arithmetic for monetary values)
- **Testing**: pytest 7.x (no mocks), Hypothesis 6.x (property-based tests, 1000+ examples for cache validation)
- **Profiling**: cProfile (call graph), line_profiler (line-by-line), memory_profiler (memory usage), py-spy (flame graphs)
- **Storage**: Parquet (OHLCV data via pyarrow 18.x, columnar format, Decimal columns)

**Framework Architecture**:
- **Algorithm Engine**: TradingAlgorithm (event-driven core, 2,800 LOC)
- **Data Layer**: PolarsDataPortal (unified interface, Parquet readers, adjustment handling)
- **Financial Layer**: DecimalLedger, DecimalPosition (Decimal precision throughout)
- **Optimization Layer**: ParallelOptimizer (multiprocessing.Pool, Grid/Random/Bayesian/Genetic/Walk Forward)
- **Benchmarking Infrastructure**: rustybt/benchmarks/ (7 dataclasses, profiling, threshold evaluation, sequential optimization)

### Integration Approach

**Database Integration Strategy**:
- **No Schema Changes Required**: All optimizations are in-memory caching and API extensions
- **Existing Database Usage**: SQLite for asset metadata (AssetFinder), adjustments (AdjustmentReader)
- **Cache Persistence**: Optional disk cache for multi-tier LRU (considered but NOT in Phase 6A scope)

**API Integration Strategy**:
- **DataPortal Extension**: Add `return_type` parameter to `history()` method with default `'dataframe'` for backward compatibility
- **Optimization Configuration**: New `OptimizationConfig` dataclass in rustybt/optimization/config.py for cache limits, LRU size, bundle pool settings
- **Cache Invalidation API**: BundleVersionMetadata for SHA256 hash tracking and automatic invalidation on bundle updates

**Frontend Integration Strategy**:
- **N/A**: Backend framework, no UI changes
- **CLI Impact**: Existing `rustybt run` and optimization commands unchanged
- **API Layer Impact**: If Epic 9 (REST API) is implemented, cache configuration exposed via API endpoints

**Testing Integration Strategy**:
- **Existing Test Suite**: 100% pass rate required before and after optimizations (4,000+ tests across 79 files)
- **New Test Modules**: tests/optimization/test_caching.py, tests/optimization/test_dataportal_ext.py, tests/benchmarks/test_regression.py
- **Property-Based Tests**: Hypothesis for cache correctness (1000+ examples, edge cases: bundle updates, concurrent access, eviction)
- **Regression Tests**: Automated performance regression detection in CI (fail on >10% degradation)

### Code Organization and Standards

**File Structure Approach**:
```
rustybt/
├── optimization/           # NEW: Phase 6A optimizations
│   ├── __init__.py
│   ├── caching.py         # CachedAssetList, PreGroupedData
│   ├── dataportal_ext.py  # HistoryCache (multi-tier LRU)
│   ├── bundle_pool.py     # BundleConnectionPool
│   ├── cache_invalidation.py  # BundleVersionMetadata, SHA256
│   └── config.py          # OptimizationConfig
├── benchmarks/            # EXISTING: Phase 1-3 infrastructure
│   ├── models.py          # PerformanceThreshold, BenchmarkResult, etc.
│   ├── profiling.py       # Profiling utilities
│   ├── reporter.py        # Report generation
│   ├── threshold.py       # Threshold evaluation
│   ├── sequential.py      # Sequential optimization eval
│   └── baseline/          # Pure Python baselines
└── data/
    └── data_portal.py     # MODIFIED: history() with return_type
```

**Naming Conventions**:
- **Classes**: PascalCase (CachedAssetList, BundleConnectionPool)
- **Functions**: snake_case (get_cached_assets, compute_bundle_hash)
- **Constants**: UPPER_SNAKE_CASE (DEFAULT_CACHE_SIZE_GB, SHA256_HASH_LENGTH)
- **Type Hints**: Full annotations with mypy --strict compliance

**Coding Standards**:
- **Line Length**: 100 characters (black formatter)
- **Function Complexity**: ≤50 lines per function, cyclomatic complexity ≤10
- **Docstrings**: Google-style for all public APIs (Args, Returns, Raises, Examples)
- **Type Safety**: 100% type hint coverage, mypy --strict
- **Zero-Mock Enforcement**: No mocks/stubs/fakes in production code, no hardcoded return values

**Documentation Standards**:
- **API Documentation**: Google-style docstrings with type hints
- **User Guides**: docs/user-guide/optimization.md (when to use return_type='array')
- **Methodology**: docs/internal/benchmarks/methodology.md (profiling approach, statistical methods)
- **Decision Rationale**: docs/internal/benchmarks/decisions/ (accept/reject decisions for each optimization)

### Deployment and Operations

**Build Process Integration**:
- **Phase 4 Change**: Remove Rust compilation (Cargo.toml, maturin, PyO3) from pyproject.toml and .github/workflows/ci.yml
- **Pure Python Build**: Standard setuptools + setuptools_scm workflow
- **Dependency Management**: uv (10-100x faster than pip for package installation)

**Deployment Strategy**:
- **PyPI Release**: Standard pip install rustybt (no Rust toolchain required after Phase 4)
- **Optional Extras**: pip install rustybt[optimization] (if additional dependencies needed for Phase 6B)
- **Backward Compatibility**: Existing installations continue working (API unchanged, default behavior preserved)

**Monitoring and Logging**:
- **Cache Hit Rate Logging**: HistoryCache exports metrics to BenchmarkResult for monitoring
- **Performance Regression Detection**: CI fails on >10% degradation for production-scale workflows
- **Profiling Outputs**: SVG flame graphs, JSON profiling data version-controlled in profiling-results/

**Configuration Management**:
- **OptimizationConfig**: Dataclass for cache limits (default 2GB pre-grouped data, 256 LRU entries)
- **Environment Variables**: Optional overrides for RUSTYBT_CACHE_SIZE_GB, RUSTYBT_LRU_SIZE
- **Bundle Version Tracking**: Automatic SHA256 hash computation, no user configuration required

### Risk Assessment and Mitigation

**Technical Risks**:
- **Risk 1**: Cache invalidation bugs causing stale data errors in production workflows
  - **Mitigation**: SHA256 hash of bundle metadata (asset list + date range + schema version) for automatic invalidation, comprehensive property-based tests (Hypothesis, 1000+ examples covering bundle updates)
- **Risk 2**: Memory overhead from caching exceeds acceptable bounds (<2% requirement)
  - **Mitigation**: Configurable 2GB limit with LRU eviction, memory profiling during benchmarking, monitoring in CI
- **Risk 3**: NumPy array return API breaks existing strategies relying on DataFrame methods
  - **Mitigation**: Backward-compatible default (`return_type='dataframe'`), 100% test suite validation before release

**Integration Risks**:
- **Risk 4**: DataPortal API changes cause subtle behavioral differences in edge cases
  - **Mitigation**: Comprehensive functional equivalence testing with property-based tests, 100% existing test pass rate requirement
- **Risk 5**: Bundle connection pooling fails in distributed scenarios (8-16 workers)
  - **Mitigation**: Thread-safe singleton with threading.Lock, extensive testing with multiprocessing scenarios

**Deployment Risks**:
- **Risk 6**: Rust removal breaks user code that directly imported Rust functions (unlikely but possible)
  - **Mitigation**: Pure Python replacements maintain identical APIs, migration documentation, deprecation warnings (if needed)
- **Risk 7**: Performance optimizations introduce platform-specific behavior (macOS vs Linux)
  - **Mitigation**: Cross-platform CI testing (Linux, macOS, Windows), platform-agnostic implementation (pure Python, stdlib only)

**Performance Risks**:
- **Risk 8**: Optimizations don't achieve 40% minimum acceptable target
  - **Mitigation**: Sequential evaluation with early stopping if goals met, Phase 6B heavy operations as fallback
- **Risk 9**: Cache hit rate <60% due to unpredictable strategy access patterns
  - **Mitigation**: Multi-tier design (permanent common windows + LRU variable), configurable cache size, monitoring and tuning based on real usage

**Mitigation Strategies Summary**:
1. **Comprehensive Testing**: 100% functional equivalence before performance measurement (BLOCKING)
2. **Statistical Validation**: ≥10 runs, 95% CI, p<0.05 for all performance claims
3. **Backward Compatibility**: Default behavior unchanged, optional opt-in for new features
4. **Monitoring**: Cache hit rate, memory overhead, performance regression in CI
5. **Rollback Plan**: Feature flags for cache enablement, easy revert to pure Python baseline

---

## Epic and Story Structure

### Epic Approach

**Epic Structure Decision**: Single comprehensive epic for brownfield performance enhancement

**Rationale Based on Actual Project Analysis**:
1. **Unified Goal**: All phases deliver one objective: "Achieve 90-95% speedup in optimization workflows"
2. **Incremental Layers**: Optimizations build on each other (Phase 6A Layer 1 → Layer 2 → Layer 3) rather than independent features
3. **Sequential Evaluation**: Phases must execute in order (profiling → Rust removal → threshold → optimizations) due to dependencies
4. **Integrated Testing**: Functional equivalence and performance benchmarking apply to all optimizations uniformly
5. **Project Size**: 258 tasks over 8 phases (excluding Constitution Compliance) justify comprehensive epic structure

**Epic Integration Requirements**: All optimizations integrate into existing `ParallelOptimizer`, `GridSearch`, and `WalkForward` workflows without breaking changes. Each layer builds on previous layers' gains.

---

## Epic Details: Epic X4 - Performance Benchmarking and Optimization

**Epic Goal**: Deliver 90-95% cumulative speedup (aspirational, 40% minimum acceptable) in Grid Search and Walk Forward optimization workflows through evidence-based optimizations targeting actual bottlenecks (87% user code overhead, 58.4% DataPortal overhead, 40.41% bundle loading fixed costs) while maintaining 100% functional equivalence and <2% memory overhead.

**Epic Integration Requirements**:
- Optimizations integrate transparently into existing optimization workflows (`ParallelOptimizer`, `GridSearch`, `WalkForward`)
- No breaking changes to user-facing APIs (`TradingAlgorithm`, `DataPortal`, strategy interfaces)
- Backward-compatible API extensions (DataPortal `return_type` parameter defaults to `'dataframe'`)
- Cross-mode consistency (backtest/paper/live produce identical results)

---

### Story X4.1: Setup and Validation Infrastructure

**As a** framework developer,
**I want** comprehensive benchmarking infrastructure and extended profiling of heavy operations,
**so that** I have a solid foundation for evaluating all optimizations with statistical rigor and complete coverage of batch initialization, parallel coordination, BOHB, and Ray scenarios.

#### Acceptance Criteria

1. **Setup Complete**:
   - Project structure created (rustybt/benchmarks/, tests/benchmarks/, profiling-results/)
   - 7 dataclasses implemented (PerformanceThreshold, BenchmarkResult, BenchmarkResultSet, OptimizationComponent, BaselineImplementation, PerformanceReport, AlternativeSolution)
   - Profiling infrastructure functional (cProfile, line_profiler, memory_profiler, flame graphs)

2. **Heavy Operation Profiling**:
   - Batch initialization profiled across 100+ backtests with varying bundle sizes (10-500 assets)
   - Parallel coordinator efficiency measured at 2, 4, 8, 16 workers
   - BOHB multi-fidelity vs Grid Search comparison complete
   - Ray distributed vs multiprocessing.Pool benchmarked
   - Comprehensive comparative report generated with percentage contributions

3. **Validation**:
   - Profiling identifies all operations >0.5% runtime with exact percentages
   - Flame graphs generated (SVG format) for all scenarios
   - Methodology documented in docs/internal/benchmarks/methodology.md

#### Integration Verification

- **IV1**: Existing functionality verification - Profiling runs on existing optimization workflows without modifications
- **IV2**: Integration point verification - Profiling hooks integrate cleanly with ParallelOptimizer, GridSearch, WalkForward
- **IV3**: Performance impact verification - Profiling overhead <5% when disabled (no runtime cost in production)

#### Rollback Plan
If profiling infrastructure has bugs:
1. Disable profiling hooks (feature flag)
2. Revert to Phase 3 baseline profiling (already complete)
3. Fix issues in isolated branch, re-merge when validated

---

### Story X4.2: Establish Pure Python Baseline

**As a** framework maintainer,
**I want** all Rust micro-operations removed and replaced with pure Python equivalents,
**so that** I have a clean baseline for benchmarking optimizations and simplified build infrastructure without Rust toolchain dependencies.

#### Acceptance Criteria

1. **Rust Identification**:
   - All actively-used Rust functions documented (SMA, EMA, rolling, window_slice, fillna, decimal sum/multiply)
   - Call sites identified via grep/Grep tool

2. **Pure Python Implementation**:
   - NumPy-based indicators (python_sma, python_ema, python_rolling)
   - Polars-based data operations (python_window_slice, python_fillna)
   - Decimal-based operations (python_decimal_sum, python_decimal_multiply)
   - 100% functional equivalence validated (numerically equivalent outputs, identical API signatures)

3. **Rust Removal**:
   - rust/ directory removed entirely
   - Cargo.toml, PyO3, maturin removed from pyproject.toml
   - GitHub Actions Rust compilation steps removed from .github/workflows/ci.yml
   - Framework builds successfully without Rust toolchain

4. **Validation**:
   - 100% test pass rate (4,000+ tests) without modifications
   - <2% change to end-to-end workflow time (confirms Rust had negligible impact)

#### Integration Verification

- **IV1**: Existing functionality remains intact - All existing tests pass without modifications (100% pass rate)
- **IV2**: Integration points working correctly - Pure Python functions drop-in replace Rust functions with identical behavior
- **IV3**: Performance impact acceptable - End-to-end workflow time changes by <2% (validates Rust removal justified)

#### Rollback Plan
If pure Python replacements have correctness issues:
1. Revert Python implementation commits
2. Restore Rust functions temporarily (git revert)
3. Fix equivalence bugs in isolated branch
4. Re-validate with comprehensive test suite before re-merge

---

### Story X4.3: Threshold Framework and Acceptance Criteria

**As a** framework architect,
**I want** a clearly defined performance threshold system with statistical validation,
**so that** optimization decisions are objective and based on 95% confidence intervals with p<0.05 significance.

#### Acceptance Criteria

1. **Threshold Configuration**:
   - 5% minimum improvement threshold defined for end-to-end workflow time
   - Grid Search and Walk Forward thresholds configured separately (same 5% but different workload scales)

2. **Statistical Validation**:
   - 95% confidence interval calculation implemented (t-test, ≥10 runs)
   - Statistical significance testing (p<0.05 requirement)
   - Memory overhead threshold checking (<2% increase)

3. **Decision Framework**:
   - Accept/reject logic based on threshold evaluation
   - Rationale generation for all decisions
   - Sequential evaluation tracking (cumulative improvement, diminishing returns detection)

4. **Testing**:
   - Property-based tests (Hypothesis) for statistical calculations
   - Positive test: Optimization with 12% improvement accepted
   - Negative test: Optimization with 3% improvement rejected

#### Integration Verification

- **IV1**: Existing functionality unaffected - Threshold framework is new infrastructure, no changes to existing code
- **IV2**: Integration with benchmarking - PerformanceReport correctly uses thresholds for accept/reject decisions
- **IV3**: Statistical validity - Confidence intervals and p-values match scipy.stats calculations (cross-validation)

#### Rollback Plan
If threshold framework has bugs:
1. Threshold evaluation is gating mechanism only (doesn't affect runtime)
2. Manual review of optimization decisions as fallback
3. Fix statistical calculation bugs, re-run evaluations
4. No production code rollback needed (infrastructure only)

---

### Story X4.4: User Code Optimizations (Layer 1 - 70% Target)

**As a** quantitative analyst running optimization workflows,
**I want** data wrangling operations (asset extraction, filtering, type conversion) cached and pre-grouped,
**so that** I eliminate 87% of user code overhead and achieve 70% faster backtest execution.

#### Acceptance Criteria

1. **Asset List Caching**:
   - CachedAssetList dataclass implemented in rustybt/optimization/caching.py
   - @functools.lru_cache with SHA256 bundle version tracking (maxsize=128)
   - Cache invalidation on bundle version changes (SHA256 hash comparison)
   - 48.5% overhead eliminated (1,485ms → <15ms for 100 backtests)

2. **Data Pre-Grouping**:
   - PreGroupedData dataclass with Dict[asset_id, np.ndarray] storage
   - LRU eviction policy (default 2GB limit, configurable)
   - Decimal precision preserved through controlled float64 conversion
   - 45.2% overhead eliminated (13,800ms → <140ms: 39.1% filtering + 6.1% conversion)

3. **Functional Equivalence**:
   - 100% pass rate on existing test suite (no modifications)
   - Property-based tests (Hypothesis, 1000+ examples) for cache correctness
   - Numerical precision validation (tolerance 1e-10)

4. **Performance Validation**:
   - Benchmark shows ≥70% cumulative speedup (≥10 runs, 95% CI, p<0.05)
   - Memory overhead <1.5x baseline

#### Integration Verification

- **IV1**: Existing functionality remains intact - Cached data produces identical results to uncached path
- **IV2**: Integration with optimization workflows - ParallelOptimizer, GridSearch, WalkForward use cached assets/data transparently
- **IV3**: Performance impact as expected - Profiling confirms 48.5% + 45.2% overhead eliminated (flame graph comparison)

#### Rollback Plan
If Layer 1 optimizations have correctness issues:
1. Disable caching via feature flag (OptimizationConfig.enable_caching=False)
2. Revert to baseline data wrangling path
3. Fix cache invalidation or precision bugs
4. Re-validate functional equivalence before re-enabling

---

### Story X4.5: Framework DataPortal Optimizations (Layer 2 - 20-25% Target)

**As a** strategy developer consuming OHLCV data,
**I want** DataPortal to return NumPy arrays when I don't need DataFrame features,
**so that** I skip 19.35% DataFrame construction overhead and achieve 20-25% additional speedup.

#### Acceptance Criteria

1. **NumPy Array Return API**:
   - DataPortal.history() extended with `return_type` parameter (Literal['dataframe', 'array'], default='dataframe')
   - NumPy array construction path skips DataFrame overhead (direct array slice from internal cache)
   - Backward compatibility validated (100% test suite passes with default='dataframe')
   - Type hints validated (mypy --strict compliance)

2. **Multi-Tier LRU Cache**:
   - HistoryCache class in rustybt/optimization/dataportal_ext.py
   - Tier 1: Permanent cache for windows [20, 50, 200] (never evicted)
   - Tier 2: LRU cache (OrderedDict, maxsize=256) for variable windows
   - Cache hit/miss rate monitoring with hit_rate calculation

3. **Functional Equivalence**:
   - Existing test suite passes 100% with default='dataframe' (no behavior changes)
   - Array return path produces identical NumPy arrays to DataFrame.values (numerical equivalence)

4. **Performance Validation**:
   - NumPy return achieves ≥20% speedup vs DataFrame construction for array-consuming strategies
   - Multi-tier cache achieves >60% cache hit rate for common lookback windows
   - Benchmark shows ≥20-25% additional speedup beyond Layer 1 (cumulative 85-90%)
   - Memory overhead <200MB

#### Integration Verification

- **IV1**: Existing functionality remains intact - Default behavior unchanged, all existing strategies work without modifications
- **IV2**: Integration with strategies - Array-consuming strategies (NumPy-based indicators) use return_type='array' transparently
- **IV3**: Performance impact as expected - Profiling confirms 19.35% DataFrame overhead eliminated for array returns

#### Rollback Plan
If Layer 2 optimizations break existing code:
1. Disable array return path via feature flag (force return_type='dataframe')
2. Disable multi-tier cache (fall back to existing memoization)
3. Revert DataPortal.history() changes
4. Fix API compatibility issues, re-validate with full test suite

---

### Story X4.6: Bundle Loading Optimization (Layer 3 - 8-12% Target)

**As a** user running distributed optimization workflows,
**I want** bundle connections pooled and reused across workers,
**so that** I eliminate 84% of worker initialization overhead (313ms → <50ms).

#### Acceptance Criteria

1. **Bundle Connection Pool**:
   - BundleConnectionPool singleton in rustybt/optimization/bundle_pool.py
   - Thread-safe access (threading.Lock)
   - Lazy initialization (first access loads bundle)
   - Version-based invalidation (SHA256 checksum of bundle metadata)

2. **Performance Validation**:
   - Worker initialization reduced to <50ms after first load (from 313ms baseline)
   - 84% reduction validated (≥10 runs, 95% CI, p<0.05)
   - Works correctly in distributed scenarios (8-16 workers)

3. **Functional Equivalence**:
   - Pooled connections produce identical results to per-worker bundle loading
   - Concurrent access handled correctly (thread-safe)

4. **Cumulative Validation**:
   - Phase 6A cumulative speedup ≥90% (Layer 1 + Layer 2 + Layer 3)
   - Overhead-to-computation ratio improves from 74:1 to <5:1

#### Integration Verification

- **IV1**: Existing functionality remains intact - Bundle loading behavior unchanged for single-process scenarios
- **IV2**: Integration with parallel workflows - ParallelOptimizer uses connection pool transparently in multiprocessing scenarios
- **IV3**: Performance impact as expected - Profiling confirms 84% init time reduction (flame graph: 313ms → <50ms)

#### Rollback Plan
If connection pool has concurrency issues:
1. Disable pooling via feature flag (OptimizationConfig.enable_bundle_pooling=False)
2. Revert to per-worker bundle loading
3. Fix thread-safety or invalidation bugs
4. Re-validate with stress tests (16+ workers, concurrent access)

---

### Story X4.7: Heavy Operations Optimization (DEFERRED - Conditional Phase 6B)

**As a** user running large-scale optimization workflows,
**I want** heavy operations (batch initialization, parallel coordination, BOHB, Ray) optimized if Phase 6A doesn't meet aspirational target,
**so that** I can achieve additional speedup beyond profiling-derived gains.

**Note**: This story is DEFERRED and executes conditionally. It executes ONLY IF Phase 6A cumulative speedup <90% (aspirational target not met). If Phase 6A achieves 90-95%, this story is SKIPPED.

#### Acceptance Criteria

1. **Sequential Evaluation**:
   - Each optimization (Shared Bundle Context, Persistent Worker Pool, BOHB, Ray) evaluated independently
   - Functional equivalence validated BEFORE performance measurement (BLOCKING)
   - Accept if meets 5% threshold, reject if fails
   - Continue until goal achieved (cumulative >90%) or diminishing returns (<2% from last 2)

2. **Optimization Implementation** (if accepted):
   - Shared Bundle Context (Rank #1 from research.md): 13% expected improvement
   - Persistent Worker Pool (Rank #3): 11% expected improvement
   - BOHB Multi-Fidelity (Rank #4): 40% expected improvement
   - Ray Distributed Scheduler (Rank #5): 10% expected improvement

3. **Cumulative Tracking**:
   - Cumulative improvement tracked in PerformanceReport
   - Each accepted optimization documented in docs/internal/benchmarks/decisions/

#### Integration Verification

- **IV1**: Existing functionality remains intact - Each optimization independently validated for functional equivalence
- **IV2**: Integration points working correctly - Accepted optimizations integrate into ParallelOptimizer without breaking existing workflows
- **IV3**: Performance impact validated - Each optimization meets 5% minimum threshold before acceptance

#### Rollback Plan
If Phase 6B optimization introduces bugs:
1. Disable specific optimization via feature flag (per-optimization control)
2. Revert to previous cumulative state
3. Fix issues in isolated branch
4. Re-validate functional equivalence before re-enabling

---

### Story X4.8: Integration, Testing, and Documentation

**As a** framework contributor,
**I want** comprehensive testing, independent audit, and complete documentation,
**so that** all performance claims are reproducible and the feature is production-ready.

#### Acceptance Criteria

1. **Testing**:
   - Comprehensive test suite (unit, integration, end-to-end) achieves 100% pass rate
   - Test coverage ≥90% overall (≥95% for benchmarking/optimization modules)
   - Property-based tests (Hypothesis) for cache validation (1000+ examples)
   - Performance regression tests integrated into CI (fail on >10% degradation)

2. **Audit**:
   - Independent audit validates all performance claims are reproducible
   - Profiling methodology documented (95% CI, ≥10 runs, p<0.05)
   - Benchmark scripts version-controlled and executable
   - Flame graphs and profiling data archived in profiling-results/

3. **Documentation**:
   - API docs updated (Google-style docstrings for all public APIs)
   - User guide created (docs/user-guide/optimization.md: when to use return_type='array')
   - Migration notes updated (docs/migration/rust-removal.md: transparent change)
   - Performance characteristics documented (docs/performance/characteristics.md)

4. **Integration Validation**:
   - Grid Search and Walk Forward achieve cumulative speedup (40% minimum or 90-95% aspirational)
   - 100% functional equivalence (identical results to baseline)
   - CPU efficiency measured at 8 workers (parallel efficiency improvement)

#### Integration Verification

- **IV1**: Existing functionality verified - Full regression testing on production-scale workflows (100+ backtests, multi-window Walk Forward)
- **IV2**: Integration points validated - All accepted optimizations work together without conflicts
- **IV3**: Performance impact documented - Final performance report with before/after comparisons, flame graphs, statistical validation

#### Rollback Plan
If integration issues discovered:
1. Disable problematic optimizations via feature flags
2. Isolate issue to specific optimization layer
3. Fix integration bugs, re-test in isolation then combined
4. Full validation before final release

---

## Success Metrics

**Quantitative Targets**:
- **Minimum Acceptable**: 40% cumulative speedup in Grid Search and Walk Forward workflows
- **Aspirational Goal**: 90-95% cumulative speedup (3-5x faster than baseline)
- **Phase 6A Target**: 70% (Layer 1) + 20-25% (Layer 2) + 8-12% (Layer 3) = 90-95% cumulative
- **Memory Efficiency**: <2% overhead increase over baseline
- **Cache Hit Rate**: >60% for multi-tier LRU cache (common lookback windows)
- **Overhead-to-Computation Ratio**: <5:1 (from 74:1 baseline)

**Validation Requirements**:
- **Statistical Rigor**: ≥10 benchmark runs, 95% confidence interval, p<0.05 significance
- **Functional Equivalence**: 100% test pass rate for all optimizations (4,000+ tests)
- **Cross-Mode Consistency**: Backtest/paper/live produce identical results
- **Regression Detection**: CI fails on >10% degradation for production-scale workflows

**Quality Gates**:
- Each optimization validated for functional equivalence BEFORE performance measurement (BLOCKING)
- Sequential evaluation continues until minimum 40% achieved or aspirational 90-95% reached
- Memory overhead monitored but not blocking (<2% target, reported for informational purposes)
- All performance claims reproducible through independent audit

---

## Risk Assessment

**Technical Risks**:
1. **Cache invalidation bugs** → Mitigation: SHA256 hash, property-based tests (Hypothesis, 1000+ examples)
2. **Memory overhead exceeds bounds** → Mitigation: 2GB limit, LRU eviction, monitoring in CI
3. **NumPy array API breaks strategies** → Mitigation: Backward-compatible default, 100% test validation

**Integration Risks**:
4. **DataPortal changes cause edge case bugs** → Mitigation: Comprehensive functional equivalence testing
5. **Bundle pooling fails in distributed scenarios** → Mitigation: Thread-safe singleton, extensive multiprocessing tests

**Performance Risks**:
6. **Optimizations don't achieve 40% minimum** → Mitigation: Sequential evaluation, Phase 6B heavy operations as fallback
7. **Cache hit rate <60%** → Mitigation: Multi-tier design, configurable size, monitoring and tuning

**Project Risks**:
8. **Scope creep (Phase 6B complexity)** → Mitigation: Clear stopping criteria (90-95% achieved → skip Phase 6B)
9. **Timeline delays (258 tasks)** → Mitigation: Parallel task execution where possible, early Phase 6A validation

---

## Implementation Timeline

**Phase 1**: Setup (4 tasks, ✅ Complete)
**Phase 2**: Foundational (15 tasks, ✅ Complete)
**Phase 3**: Profiling (17 tasks, ✅ Complete)
**Phase 3 Extension**: Heavy Operation Profiling (5 tasks, Week 1)
**Phase 4**: Rust Removal (30 tasks, Week 2)
**Phase 5**: Threshold Framework (13 tasks, Week 3)
**Phase 6A**: Profiling-Derived Optimizations (20 tasks, Weeks 4-5) ⭐ CRITICAL
**Phase 6B**: Heavy Operations (56 tasks, Conditional - Weeks 6-8 if needed)
**Phase 7**: Workflow Enhancement (14 tasks, Week 9)
**Phase 8**: Testing & Documentation (26 tasks, Week 10)
**Phase FINAL**: Constitution Compliance (55 tasks, Week 11)

**Total Timeline**: 11 weeks (optimistic if Phase 6B skipped: 7-8 weeks)

---

## Dependencies

**External Dependencies**: None (pure Python, stdlib + existing dependencies)
**Internal Dependencies**: Sequential execution required (profiling → Rust removal → threshold → optimizations)
**Blocking Requirements**: Functional equivalence MUST be validated before performance measurement (Phase 6A/6B)

**Key Decision Points**:
- **After Phase 4**: Validate <2% performance change from Rust removal
- **After Phase 5**: Confirm 5% threshold acceptance criteria
- **After Phase 6A**: Evaluate if Phase 6B necessary (if 90-95% already achieved, skip)
- **After Phase 6B**: Sequential evaluation determines when diminishing returns reached

---

## Constitutional Compliance

**All 7 Constitutional Principles Apply**:

1. **Decimal Financial Computing**: ✅ Baseline implementations use Decimal, cache preserves precision
2. **Zero-Mock Enforcement**: ✅ All benchmarks use real data and computations (no synthetic timing)
3. **Strategy Reusability Guarantee**: ✅ Optimizations transparent across backtest/paper/live modes
4. **Type Safety Excellence**: ✅ Python 3.12+, mypy --strict, 100% type hint coverage
5. **Test-Driven Development**: ✅ 90%+ coverage (95%+ for financial modules), property-based tests
6. **Modern Data Architecture**: ✅ Polars primary, Parquet OHLCV storage, Decimal columns
7. **Sprint Debug Discipline**: ✅ Pre-flight checklist, verification before commits, decision documentation

---

**END OF PRD**
