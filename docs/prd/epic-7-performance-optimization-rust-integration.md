# Epic 7: Performance Optimization - Rust Integration

**Expanded Goal**: Profile Python implementation to identify bottlenecks consuming >5% of backtest time (not limited to Decimal arithmetic - includes loops, subprocesses, data processing, indicator calculations), then reimplement hot paths in Rust for performance. Target <30% overhead vs. float baseline (subject to profiling validation), validated through comprehensive benchmarking suite integrated into CI/CD. Testing, benchmarking, and documentation integrated throughout.

---

## Story 7.1: Profile Python Implementation to Identify Bottlenecks

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
