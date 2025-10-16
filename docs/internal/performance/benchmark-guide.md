# Performance Benchmarking Guide

This guide explains how to run performance benchmarks and regression tests for RustyBT.

## Story 7.4: Performance Target Validation

**Objective**: Validate that Decimal + Rust optimizations achieve <30% overhead vs. float baseline.

## Quick Start

### 1. Setup Profiling Data

First, create the profiling bundles:

```bash
python scripts/profiling/setup_profiling_data.py
```

This creates synthetic data bundles for benchmarking:
- `profiling-daily`: 50 stocks, 3 years of daily data
- `profiling-hourly`: 20 assets, 7 months of hourly data
- `profiling-minute`: 10 assets, 2 months of minute data

### 2. Run Comprehensive Benchmarks

Run the full benchmark suite to compare float baseline vs. Decimal + Rust:

```bash
# Run all scenarios with 5 iterations each
python scripts/profiling/benchmark_overhead.py --scenario all --runs 5

# Run specific scenario
python scripts/profiling/benchmark_overhead.py --scenario daily --runs 3

# Run with more iterations for accuracy
python scripts/profiling/benchmark_overhead.py --scenario all --runs 10
```

**Output**:
- `docs/performance/benchmark-results.json`: Raw benchmark data
- `docs/performance/rust-optimization-results.md`: Comprehensive performance report

### 3. Review Results

Open the generated report:

```bash
cat docs/performance/rust-optimization-results.md
```

The report includes:
- Executive summary (target met/not met)
- Detailed benchmark results per scenario
- Overhead calculations
- Recommendations for next steps

## Performance Regression Tests

### Running Regression Tests

Performance regression tests ensure that performance doesn't degrade over time.

```bash
# Run all regression tests
pytest tests/regression/ -v -m regression

# Run specific test
pytest tests/regression/test_performance_regression.py::test_daily_backtest_performance_regression -v
```

### Creating Performance Baselines

After confirming that benchmarks meet targets, create baselines for regression testing:

```bash
# Create initial baselines
pytest tests/regression/test_performance_regression.py::test_create_baselines -v -s

# This creates: tests/regression/performance_baselines.json
```

**Baseline File Structure**:
```json
{
  "daily_backtest": {
    "decimal_rust": 12.5
  },
  "hourly_backtest": {
    "decimal_rust": 6.2
  },
  "minute_backtest": {
    "decimal_rust": 2.5
  }
}
```

### Updating Baselines

When intentional performance changes occur (e.g., new optimizations):

1. Run benchmarks to confirm expected performance:
   ```bash
   python scripts/profiling/benchmark_overhead.py --scenario all --runs 5
   ```

2. If results are as expected, update baselines:
   ```bash
   pytest tests/regression/test_performance_regression.py::test_create_baselines -v -s
   ```

3. Commit the updated `performance_baselines.json`:
   ```bash
   git add tests/regression/performance_baselines.json
   git commit -m "chore: update performance baselines after optimization"
   ```

## CI/CD Integration

### Automatic Performance Monitoring

Performance regression tests run automatically on every push to `main`:

```yaml
# .github/workflows/ci.yml
performance-regression:
  runs-on: ubuntu-latest
  if: github.ref == 'refs/heads/main'
  steps:
    - name: Run performance regression tests
      run: pytest tests/regression/ -v -m regression
```

### Thresholds

- **5% degradation**: Warning logged (test passes)
- **20% degradation**: Hard failure (test fails, blocks merge)

### Viewing Results

Check CI artifacts for performance results:
1. Go to GitHub Actions run
2. Click on "performance-regression" job
3. Download "performance-regression-results" artifact

## Interpreting Results

### Target Met (✅)

```
Average overhead: 24.7% (target: <30%)
✅ SUCCESS: Performance target met!
```

**Next Steps**:
- Enable Rust optimizations by default
- Proceed to next Epic
- Monitor production performance

### Target Not Met (❌)

```
Average overhead: 35.2% (target: <30%)
❌ TARGET NOT MET: Additional optimization needed
```

**Next Steps**:
1. Review module-level breakdown in report
2. Identify remaining bottlenecks
3. Choose contingency option:
   - **Option 1**: Additional Rust optimization (recommended)
   - **Option 2**: Cython optimization
   - **Option 3**: Pure Rust rewrite (high effort)

## Troubleshooting

### Bundle Not Found Error

```
BundleDataNotFoundError: No bundle 'profiling-daily' found
```

**Solution**: Run setup script:
```bash
python scripts/profiling/setup_profiling_data.py
```

### Import Errors

```
ModuleNotFoundError: No module named 'rustybt'
```

**Solution**: Install RustyBT in development mode:
```bash
pip install -e ".[dev,test]"
```

### Rust Extension Not Built

```
ImportError: Rust extension not available
```

**Solution**: Build Rust extension:
```bash
cd rust
cargo build --release
cd ..
pip install -e ".[dev,test]"
```

### Slow Benchmarks

Benchmarks can take 10-30 minutes depending on system performance.

**Tips**:
- Use fewer runs: `--runs 3` instead of `--runs 5`
- Run specific scenarios: `--scenario daily` instead of `--scenario all`
- Use faster hardware (CI uses GitHub Actions runners)

## Advanced Usage

### Custom Benchmark Scenarios

Edit `scripts/profiling/benchmark_overhead.py` to add custom scenarios:

```python
def run_custom_scenario(use_decimal: bool = False) -> Dict[str, Any]:
    """Custom benchmark scenario."""
    # Your strategy logic here
    pass

# Register in scenario_functions dict
scenario_functions = {
    "daily": run_daily_backtest,
    "custom": run_custom_scenario,  # Add custom scenario
}
```

### Module-Level Profiling

For detailed module-level analysis, use the profiler:

```bash
python scripts/profiling/run_profiler.py --scenario daily --profiler cprofile
```

Results in: `docs/performance/profiles/baseline/daily_cprofile.pstats`

### Comparing Profiles

Compare before/after optimization profiles:

```bash
python scripts/profiling/compare_profiles.py \
    docs/performance/profiles/baseline/ \
    docs/performance/profiles/post-rust/
```

## Performance Standards

From `docs/architecture/coding-standards.md`:

### Performance Assertions
- All performance-critical functions must have benchmarks
- Regression tests fail if performance degrades >20%
- Performance benchmarks run in CI/CD

### Zero-Mock Enforcement
- NEVER hardcode benchmark results
- ALWAYS measure actual performance
- NEVER simplify benchmarks to pass tests

## Related Documentation

- [Profiling Results](profiling-results.md): Detailed profiling analysis from Story 7.1
- [Rust Benchmarks](rust-benchmarks.md): Rust optimization benchmarks from Story 7.3
- [Coding Standards](../architecture/coding-standards.md): Performance requirements
- [Story 7.4](../stories/7.4.validate-performance-target-achievement.story.md): Full story details

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review existing benchmark results in `docs/performance/`
3. Consult Story 7.4 acceptance criteria
4. Ask in #performance Slack channel (if applicable)

---

**Last Updated**: 2025-01-09
**Story**: 7.4 - Validate Performance Target Achievement
**Author**: James (Full Stack Developer)
