# Performance Benchmarking & Validation

This directory contains performance benchmarking tools and results for RustyBT.

## Quick Links

- **[Benchmark Guide](benchmark-guide.md)**: Complete guide for running performance benchmarks
- **[Profiling Results](profiling-results.md)**: Detailed profiling analysis (Story 7.1)
- **[Rust Benchmarks](rust-benchmarks.md)**: Rust optimization benchmarks (Story 7.3)
- **[Rust Optimizations](rust-optimizations.md)**: Rust optimization documentation

## Story 7.4: Performance Target Validation

### Objective
Validate that Decimal + Rust optimizations achieve **<30% overhead** vs. float baseline.

### Running Benchmarks

```bash
# Setup profiling data
python scripts/profiling/setup_profiling_data.py

# Run comprehensive benchmarks
python scripts/profiling/benchmark_overhead.py --scenario all --runs 5

# View results
cat docs/performance/rust-optimization-results.md
```

### Performance Regression Tests

```bash
# Run regression tests
pytest tests/regression/ -v -m regression

# Create baselines (after confirming benchmarks meet targets)
pytest tests/regression/test_performance_regression.py::test_create_baselines -v -s
```

## Files in This Directory

### Benchmark Results
- `benchmark-results.json`: Raw benchmark data (generated)
- `rust-optimization-results.md`: Performance validation report (generated)

### Profiling Data
- `profiling-results.md`: CPU & memory profiling from Story 7.1
- `rust-benchmarks.md`: Rust optimization benchmarks from Story 7.3
- `profiles/`: Directory containing profiling output files

### Documentation
- `benchmark-guide.md`: Complete benchmarking documentation
- `rust-optimizations.md`: Rust optimization documentation
- `README.md`: This file

## Performance Standards

From `docs/architecture/coding-standards.md`:

### Target
- **<30% overhead** vs. float baseline for Decimal + Rust optimizations

### Regression Thresholds
- **5% degradation**: Warning (test passes with warning log)
- **20% degradation**: Hard failure (test fails, blocks merge)

### Zero-Mock Enforcement
- NEVER hardcode benchmark results
- ALWAYS measure actual performance with real backtests
- NEVER simplify benchmarks to pass tests

## CI/CD Integration

Performance regression tests run automatically on every push to `main` branch:

- **Job**: `performance-regression`
- **Timeout**: 45 minutes
- **Frequency**: Every push to main
- **Artifacts**: Results uploaded for analysis

## Profiling Scenarios

Three representative scenarios from Story 7.1:

1. **Daily**: 2 years, 10 assets, SMA crossover strategy
2. **Hourly**: 3 months, 5 assets, momentum strategy
3. **Minute**: 1 month, 3 assets, mean reversion strategy

## Next Steps

After benchmarks are run and targets validated:

### If Target Met (✅ <30% overhead)
1. Create regression baselines
2. Enable Rust optimizations by default
3. Proceed to Epic X1 (Unified Data Architecture)

### If Target Not Met (❌ >30% overhead)
1. Review module-level breakdown
2. Identify remaining bottlenecks
3. Choose contingency option:
   - Additional Rust optimization
   - Cython optimization
   - Pure Rust rewrite
4. Create follow-up story

## Support

For questions or issues:
1. Check [Benchmark Guide](benchmark-guide.md)
2. Review existing results in this directory
3. Consult [Story 7.4](../stories/7.4.validate-performance-target-achievement.story.md)

---

**Last Updated**: 2025-01-09
**Story**: 7.4 - Validate Performance Target Achievement
**Status**: Infrastructure complete, awaiting benchmark execution
