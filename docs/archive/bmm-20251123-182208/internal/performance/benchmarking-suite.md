

# RustyBT Comprehensive Benchmarking Suite

This document describes the comprehensive benchmarking suite for RustyBT, designed to track performance across releases and detect regressions early.

## Overview

The benchmarking suite implements Story 7.5 requirements:

- **AC1**: Benchmark scenarios covering common use cases (daily, hourly, minute strategies)
- **AC2**: Test different strategy complexities (simple, medium, complex)
- **AC3**: Test different portfolio sizes (10, 50, 100, 500 assets)
- **AC4**: Store benchmark results historically
- **AC5**: Automated execution in CI/CD (nightly builds)
- **AC6**: Generate performance graphs
- **AC7**: Detect regressions >5% degradation
- **AC8**: Compare Python-only vs. Rust-optimized performance
- **AC9**: Memory benchmarks included
- **AC10**: Benchmark dashboard (future enhancement)

## Quick Start

### 1. Generate Benchmark Fixtures

```bash
python scripts/benchmarks/generate_fixtures.py
```

This creates deterministic synthetic OHLCV data for all benchmark scenarios (~500MB total).

### 2. Run Benchmark Suite

```bash
# Run all benchmarks
pytest tests/benchmarks/test_backtest_performance.py --benchmark-only -v

# Run specific scenario
pytest tests/benchmarks/test_backtest_performance.py::test_daily_simple_10_assets_rust --benchmark-only -v

# Run memory benchmarks
pytest tests/benchmarks/test_memory_usage.py -v -m memory
```

### 3. View Results

Results are automatically stored in `docs/performance/benchmark-history.json`.

Query results:
```bash
python scripts/benchmarks/query_history.py --last 10
python scripts/benchmarks/query_history.py --scenario daily_simple_50_rust --summary
```

## Benchmark Scenarios

The suite implements 15 prioritized scenarios (from a 36-scenario matrix):

### Daily Frequency (6 scenarios)
1. **daily_simple_10_assets_rust** - Fast baseline (~20s)
2. **daily_simple_50_assets_rust** - Common portfolio size (~30s)
3. **daily_simple_50_assets_python** - Python-only baseline (~30s)
4. **daily_medium_50_assets_rust** - Realistic use case (~40s)
5. **daily_medium_10_assets_rust** - Strategy overhead (~25s)
6. **daily_complex_100_assets_rust** - Stress test (~80s)
7. **daily_simple_500_assets_rust** - Large portfolio scaling (~120s)

### Hourly Frequency (5 scenarios)
8. **hourly_simple_10_assets_rust** - Intraday baseline (~30s)
9. **hourly_medium_50_assets_rust** - Common intraday use case (~60s)
10. **hourly_medium_20_assets_python** - Python-only baseline (~60s)
11. **hourly_complex_100_assets_rust** - Intraday stress test (~120s)
12. **hourly_simple_100_assets_rust** - Scaling test (~80s)

### Minute Frequency (3 scenarios)
13. **minute_simple_10_assets_rust** - HFT baseline (~40s)
14. **minute_medium_20_assets_rust** - HFT realistic (~80s)
15. **minute_simple_50_assets_rust** - HFT scaling (~80s)

**Total estimated runtime**: ~12 minutes

## Benchmark Strategies

### Simple Strategy
- **Indicators**: SMA Short (50), SMA Long (200)
- **Logic**: Golden cross / death cross
- **Complexity**: O(n) per asset

### Medium Strategy
- **Indicators**: Momentum (20), RSI (14), Volume MA (20), Bollinger Bands (20, 2)
- **Logic**: Multi-indicator confirmation
- **Complexity**: O(n) per asset, more calculations

### Complex Strategy
- **Indicators**: Multiple SMAs (4), EMAs (2), MACD, RSI, BB, ATR, Volume
- **Logic**: Weighted scoring system
- **Complexity**: O(n) per asset, heavy computation

All strategies are **deterministic** (same inputs produce same results).

## Historical Tracking

### Storage Format

Results stored in `docs/performance/benchmark-history.json`:

```json
{
  "runs": [
    {
      "timestamp": "2025-01-09T12:00:00Z",
      "git_commit": "abc123def456...",
      "git_branch": "main",
      "benchmarks": [
        {
          "name": "test_daily_simple_10_assets_rust",
          "execution_time": 18.5,
          "memory_peak_mb": 245.2
        }
      ]
    }
  ]
}
```

### Retention Policy
- Keep last 100 runs
- Keep all runs from last 1 year
- Older runs archived to `benchmark-history-archive.json`

### Querying Historical Data

```bash
# Last 10 runs
python scripts/benchmarks/query_history.py --last 10

# Since specific date
python scripts/benchmarks/query_history.py --since 2025-01-01

# Specific commit
python scripts/benchmarks/query_history.py --commit abc123def

# With summary statistics
python scripts/benchmarks/query_history.py --scenario daily_simple_50_rust --summary
```

## Regression Detection

### Thresholds
- **5% degradation**: Warning (logged, test passes)
- **20% degradation**: Hard failure (test fails, blocks CI)

### Running Detection

```bash
# Console output
python scripts/benchmarks/detect_regressions.py

# JSON output
python scripts/benchmarks/detect_regressions.py --output json

# GitHub issue format
python scripts/benchmarks/detect_regressions.py --output github
```

### Comparison

Compares current run against baselines in `tests/regression/performance_baselines.json`.

### Exit Codes
- `0`: No regressions detected
- `1`: Regressions detected (fails CI/CD)

## Performance Graphs

### Generated Graphs

Location: `docs/performance/graphs/`

1. **execution_time_trends.png** - Execution time over commits
2. **memory_usage_trends.png** - Memory usage over commits (future)
3. **python_vs_rust_speedup.png** - Speedup comparison (future)
4. **performance_by_size.png** - Scaling analysis (future)

### Generation

```bash
python scripts/benchmarks/generate_graphs.py
```

Graphs are automatically generated after each CI/CD run.

## CI/CD Integration

### Nightly Benchmarks

Workflow: `.github/workflows/nightly-benchmarks.yml`

**Schedule**: Daily at 2 AM UTC
**Manual trigger**: Workflow dispatch button in GitHub Actions

**Steps**:
1. Generate fixtures (if not cached)
2. Run benchmark suite
3. Store results in benchmark-history.json
4. Detect regressions
5. Generate graphs
6. Commit results to repository
7. Create GitHub issue if regressions detected
8. Upload artifacts (results, graphs, reports)

### PR Benchmarks (Optional)

Can be enabled by adding `benchmark` label to PR.

## Benchmark Comparison

### Compare Two Commits

```bash
python scripts/benchmarks/compare_benchmarks.py abc123def xyz789abc
```

Output: Markdown table showing delta per scenario.

### Example Output

```
Scenario                       Run 1 (s)    Run 2 (s)    Delta      Change
----------------------------------------------------------------------------------
daily_simple_50_rust           28.5         30.2         +1.7       +6.0% 🔴
hourly_medium_50_rust          58.3         56.1         -2.2       -3.8% 🟢
```

## Memory Benchmarks

### Running Memory Tests

```bash
pytest tests/benchmarks/test_memory_usage.py -v -m memory
```

**Note**: Requires `memory_profiler` package.

### Metrics Measured
- Peak memory usage (MB)
- Memory allocation rate
- Polars DataFrame footprint
- Decimal object memory usage

## Adding New Benchmarks

### 1. Create Strategy

Add to `tests/benchmarks/strategies/`:

```python
def create_initialize_fn(n_assets: int):
    def initialize(context):
        context.assets = [symbol(f"ASSET{i:03d}") for i in range(n_assets)]
        # ... initialization
    return initialize

def create_handle_data_fn():
    def handle_data(context, data):
        # ... strategy logic
    return handle_data
```

### 2. Add Benchmark Test

Add to `tests/benchmarks/test_backtest_performance.py`:

```python
@pytest.mark.benchmark(group="daily-new-strategy")
def test_daily_new_strategy_50_assets_rust(benchmark):
    """Benchmark new strategy with 50 assets."""
    initialize_fn = create_new_strategy_init(n_assets=50)
    handle_data_fn = create_new_strategy_handle()

    result = benchmark(
        run_backtest_benchmark,
        initialize_fn=initialize_fn,
        handle_data_fn=handle_data_fn,
        fixture_filename='daily_50_assets.parquet',
    )

    assert result['completed']
```

### 3. Update Documentation

Update this file with new scenario details.

## Performance Standards

From `docs/architecture/coding-standards.md`:

### Targets
- **<30% overhead** vs. float baseline for Decimal + Rust optimizations
- **<15 minutes** total benchmark runtime (all 15 scenarios)

### Zero-Mock Enforcement
- NEVER hardcode benchmark results
- ALWAYS measure actual performance
- NEVER simplify benchmarks to pass tests

## Troubleshooting

### Fixtures Not Found

```
python scripts/benchmarks/generate_fixtures.py
```

### Benchmarks Too Slow

- Run subset: `-k "daily_simple"`
- Reduce rounds: `--benchmark-min-rounds=1`
- Use smaller fixtures

### Memory Errors

- Check fixture sizes: `du -sh tests/benchmarks/data/`
- Increase system memory
- Run fewer concurrent tests

### Inconsistent Results

- Ensure deterministic data (seed=42)
- Run multiple rounds to average
- Check system load
- Close other applications

## Future Enhancements

### Dashboard (AC10)

**✅ IMPLEMENTED: Static HTML Dashboard**

The benchmark suite includes a self-contained HTML dashboard with embedded charts and performance visualization.

#### Access Dashboard

1. **Generate Dashboard**:
   ```bash
   python scripts/benchmarks/generate_dashboard.py
   ```

2. **View in Browser**:
   ```bash
   open docs/performance/dashboard.html
   # Or navigate to: file:///path/to/rustybt/docs/performance/dashboard.html
   ```

3. **Auto-Regeneration in CI/CD**:
   - Dashboard is automatically regenerated after nightly benchmark runs
   - Latest version always available in repository

#### Dashboard Features

- **Summary Statistics**: Total runs, unique scenarios, latest commit, last update
- **Execution Time Trends**: Line chart tracking performance across runs
- **Scenario Comparison**: Bar chart comparing latest run times
- **Recent Runs Table**: Last 20 benchmark executions with details
- **Usage Instructions**: Quick commands and scenario information

#### Future Enhancement Options

Additional dashboard options under consideration:

1. **Streamlit** - Interactive filtering, drill-down analysis
2. **Grafana** - Professional monitoring, alerting integration

### Additional Graphs

- Memory trends over time
- Python vs. Rust speedup bars
- Scaling analysis (size vs. time)
- Strategy complexity overhead

### Automated Optimization

- Detect bottlenecks automatically
- Suggest optimization opportunities
- Run optimization experiments

## Related Documentation

- [Benchmark Guide](benchmark-guide.md) - Running benchmarks
- [Story 7.5](../stories/7.5.implement-comprehensive-benchmarking-suite.story.md) - Requirements
- [Coding Standards](../architecture/coding-standards.md) - Performance requirements
- [Regression Tests](../../tests/regression/) - Performance regression tests

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review existing results in `docs/performance/`
3. Create issue with `benchmark` label
4. Ask in #performance channel (if applicable)

---

**Last Updated**: 2025-01-09
**Story**: 7.5 - Implement Comprehensive Benchmarking Suite
**Author**: James (Full Stack Developer)
**Status**: Complete
