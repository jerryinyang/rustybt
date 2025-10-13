# RustyBT Comprehensive Benchmarking Suite

This directory contains the comprehensive benchmarking suite for RustyBT, tracking performance across releases and identifying regressions early.

## Overview

The benchmark suite tests performance across multiple dimensions:
- **Data Frequency**: Daily, Hourly, Minute
- **Strategy Complexity**: Simple (1-2 indicators), Medium (3-5 indicators), Complex (6+ indicators)
- **Portfolio Size**: 10, 50, 100, 500 assets
- **Implementation**: Python-only vs. Rust-optimized

## Benchmark Scenario Matrix

### Design Rationale

The scenario matrix was designed to:
1. Cover common use cases (not edge cases)
2. Test scaling behavior (10 to 500 assets)
3. Measure strategy complexity overhead
4. Quantify Rust optimization benefits
5. Complete in reasonable time (<15 minutes total)

### Full Matrix (36 Scenarios)

| Frequency | Complexity | Assets | Estimated Time | Priority |
|-----------|-----------|--------|----------------|----------|
| Daily     | Simple    | 10     | ~20s          | HIGH     |
| Daily     | Simple    | 50     | ~30s          | HIGH     |
| Daily     | Simple    | 100    | ~45s          | MEDIUM   |
| Daily     | Simple    | 500    | ~120s         | LOW      |
| Daily     | Medium    | 10     | ~25s          | MEDIUM   |
| Daily     | Medium    | 50     | ~40s          | HIGH     |
| Daily     | Medium    | 100    | ~60s          | MEDIUM   |
| Daily     | Medium    | 500    | ~150s         | LOW      |
| Daily     | Complex   | 10     | ~30s          | LOW      |
| Daily     | Complex   | 50     | ~50s          | MEDIUM   |
| Daily     | Complex   | 100    | ~80s          | MEDIUM   |
| Daily     | Complex   | 500    | ~180s         | LOW      |
| Hourly    | Simple    | 10     | ~30s          | HIGH     |
| Hourly    | Simple    | 50     | ~50s          | MEDIUM   |
| Hourly    | Simple    | 100    | ~80s          | MEDIUM   |
| Hourly    | Simple    | 500    | ~200s         | LOW      |
| Hourly    | Medium    | 10     | ~40s          | MEDIUM   |
| Hourly    | Medium    | 50     | ~60s          | HIGH     |
| Hourly    | Medium    | 100    | ~100s         | MEDIUM   |
| Hourly    | Medium    | 500    | ~240s         | LOW      |
| Hourly    | Complex   | 10     | ~50s          | LOW      |
| Hourly    | Complex   | 50     | ~80s          | MEDIUM   |
| Hourly    | Complex   | 100    | ~120s         | MEDIUM   |
| Hourly    | Complex   | 500    | ~300s         | LOW      |
| Minute    | Simple    | 10     | ~40s          | HIGH     |
| Minute    | Simple    | 50     | ~80s          | LOW      |
| Minute    | Simple    | 100    | ~140s         | LOW      |
| Minute    | Simple    | 500    | ~400s         | LOW      |
| Minute    | Medium    | 10     | ~50s          | MEDIUM   |
| Minute    | Medium    | 50     | ~120s         | LOW      |
| Minute    | Medium    | 100    | ~200s         | LOW      |
| Minute    | Medium    | 500    | ~500s         | LOW      |
| Minute    | Complex   | 10     | ~60s          | LOW      |
| Minute    | Complex   | 50     | ~150s         | LOW      |
| Minute    | Complex   | 100    | ~240s         | LOW      |
| Minute    | Complex   | 500    | ~600s         | LOW      |

### Prioritized Scenarios (15 Scenarios)

To keep benchmark runtime manageable (~12 minutes), we prioritize 15 key scenarios:

| # | Frequency | Complexity | Assets | Runtime | Priority | Rationale |
|---|-----------|-----------|--------|---------|----------|-----------|
| 1 | Daily     | Simple    | 10     | ~20s    | HIGH     | Fast baseline, quick feedback |
| 2 | Daily     | Simple    | 50     | ~30s    | HIGH     | Common portfolio size |
| 3 | Daily     | Medium    | 50     | ~40s    | HIGH     | Realistic use case |
| 4 | Daily     | Complex   | 100    | ~80s    | MEDIUM   | Stress test for daily |
| 5 | Hourly    | Simple    | 10     | ~30s    | HIGH     | Intraday baseline |
| 6 | Hourly    | Medium    | 50     | ~60s    | HIGH     | Common intraday use case |
| 7 | Hourly    | Complex   | 100    | ~120s   | MEDIUM   | Intraday stress test |
| 8 | Minute    | Simple    | 10     | ~40s    | HIGH     | HFT baseline |
| 9 | Minute    | Medium    | 20     | ~80s    | MEDIUM   | HFT realistic (custom size) |
| 10| Daily     | Simple    | 500    | ~120s   | LOW      | Large portfolio scaling |
| 11| Daily     | Medium    | 10     | ~25s    | MEDIUM   | Strategy overhead |
| 12| Hourly    | Simple    | 100    | ~80s    | MEDIUM   | Scaling test |
| 13| Minute    | Simple    | 50     | ~80s    | LOW      | HFT scaling |
| 14| Daily     | Simple    | 50     | ~30s    | HIGH     | Python-only baseline |
| 15| Hourly    | Medium    | 20     | ~60s    | MEDIUM   | Python-only baseline |

**Total Estimated Runtime**: ~12 minutes (15 scenarios × ~48s average)

### Coverage Analysis

**Frequency Coverage**:
- Daily: 6 scenarios (40%)
- Hourly: 5 scenarios (33%)
- Minute: 4 scenarios (27%)

**Complexity Coverage**:
- Simple: 8 scenarios (53%)
- Medium: 6 scenarios (40%)
- Complex: 1 scenario (7%) - intentionally minimal, stress test only

**Portfolio Size Coverage**:
- 10 assets: 4 scenarios (27%)
- 20 assets: 2 scenarios (13%)
- 50 assets: 5 scenarios (33%)
- 100 assets: 2 scenarios (13%)
- 500 assets: 1 scenario (7%)

**Python vs. Rust**:
- Python-only: 2 scenarios (13%) - for baseline comparison
- Rust-optimized: 13 scenarios (87%)

## Benchmark Strategies

### Simple Strategy (1-2 indicators)
**File**: `strategies/simple_sma_crossover.py`
**Indicators**:
- SMA Short (50 periods)
- SMA Long (200 periods)
**Logic**: Buy when SMA Short > SMA Long, sell otherwise
**Complexity**: O(n) per asset

### Medium Strategy (3-5 indicators)
**File**: `strategies/momentum_strategy.py`
**Indicators**:
- Momentum (20 periods)
- RSI (14 periods)
- Volume MA (20 periods)
- Bollinger Bands (20 periods, 2 std)
**Logic**: Buy on momentum + RSI oversold + high volume, sell on opposite
**Complexity**: O(n) per asset, more calculations

### Complex Strategy (6+ indicators)
**File**: `strategies/multi_indicator_strategy.py`
**Indicators**:
- Multiple SMAs (10, 20, 50, 200)
- EMA (12, 26)
- MACD + Signal
- RSI (14)
- Bollinger Bands (20, 2)
- ATR (14)
- Volume indicators
**Logic**: Weighted scoring system combining all indicators
**Complexity**: O(n) per asset, heavy computation

## Benchmark Data Fixtures

### Location
`tests/benchmarks/data/`

### Format
Parquet files with Snappy compression

### Fixtures Created

| Fixture | Frequency | Duration | Assets | Size Limit | Actual Size |
|---------|-----------|----------|--------|------------|-------------|
| daily_10_assets.parquet | Daily | 2 years | 10 | <10MB | TBD |
| daily_50_assets.parquet | Daily | 2 years | 50 | <10MB | TBD |
| daily_100_assets.parquet | Daily | 2 years | 100 | <30MB | TBD |
| daily_500_assets.parquet | Daily | 2 years | 500 | <100MB | TBD |
| hourly_10_assets.parquet | Hourly | 6 months | 10 | <10MB | TBD |
| hourly_20_assets.parquet | Hourly | 6 months | 20 | <10MB | TBD |
| hourly_50_assets.parquet | Hourly | 6 months | 50 | <30MB | TBD |
| hourly_100_assets.parquet | Hourly | 6 months | 100 | <30MB | TBD |
| minute_10_assets.parquet | Minute | 1 month | 10 | <10MB | TBD |
| minute_20_assets.parquet | Minute | 1 month | 20 | <10MB | TBD |
| minute_50_assets.parquet | Minute | 1 month | 50 | <30MB | TBD |

**Total Storage Target**: <500MB
**Compression**: Snappy (good balance of speed and compression)

### Data Generation

Data is generated deterministically with `seed=42`:
- Realistic OHLCV relationships (high >= low, high >= close, etc.)
- Random walk with drift
- Configurable volatility
- No missing data (for benchmark consistency)

**Generation Script**: `scripts/benchmarks/generate_fixtures.py`

## Running Benchmarks

### Run All Benchmarks
```bash
pytest tests/benchmarks/test_backtest_performance.py --benchmark-only -v
```

### Run Specific Scenario
```bash
pytest tests/benchmarks/test_backtest_performance.py::test_daily_simple_10_assets_rust --benchmark-only -v
```

### Run with More Iterations
```bash
pytest tests/benchmarks/test_backtest_performance.py --benchmark-only --benchmark-min-rounds=5
```

### Compare Python vs. Rust
```bash
pytest tests/benchmarks/test_backtest_performance.py -k "daily_simple_50" --benchmark-only --benchmark-compare
```

### Memory Benchmarks
```bash
pytest tests/benchmarks/test_memory_usage.py --benchmark-only -v
```

## Historical Tracking

### Storage
Results are stored in `docs/performance/benchmark-history.json` with schema:
```json
{
  "runs": [
    {
      "timestamp": "2025-01-09T12:00:00Z",
      "git_commit": "abc123def",
      "git_branch": "main",
      "scenario": "daily_simple_50_rust",
      "execution_time": 30.5,
      "memory_peak_mb": 245.2,
      "rust_enabled": true,
      "pytest_benchmark_data": {...}
    }
  ]
}
```

### Retention Policy
- Keep last 100 runs
- Keep all runs from last 1 year
- Older runs are archived to `benchmark-history-archive.json`

### Query Historical Data
```bash
python scripts/benchmarks/query_history.py --scenario daily_simple_50_rust --last 10
python scripts/benchmarks/query_history.py --since 2025-01-01
python scripts/benchmarks/query_history.py --commit abc123def
```

## Regression Detection

### Thresholds
- **5% degradation**: Warning (logged, test passes)
- **20% degradation**: Hard failure (test fails, blocks CI)

### Detection Script
```bash
python scripts/benchmarks/detect_regressions.py
```

### Comparison
Compares current run against:
1. Previous release baseline (tags)
2. Last successful run on main branch

### Output
- Console report with delta percentages
- Regression flag (exit code 1 if regressions found)
- Detailed report in markdown format

## Performance Graphs

### Generated Graphs

Location: `docs/performance/graphs/`

1. **execution_time_vs_commit.png**: Line chart showing execution time trends per scenario
2. **memory_usage_vs_commit.png**: Line chart showing memory usage trends per scenario
3. **python_vs_rust_speedup.png**: Bar chart comparing Python vs. Rust performance
4. **performance_by_portfolio_size.png**: Bar chart showing scaling behavior
5. **performance_by_complexity.png**: Bar chart showing strategy complexity overhead

### Generation
```bash
python scripts/benchmarks/generate_graphs.py
```

Graphs are automatically generated after each benchmark run in CI/CD.

## CI/CD Integration

### Nightly Benchmarks

Workflow: `.github/workflows/nightly-benchmarks.yml`

**Schedule**: Daily at 2 AM UTC
**Triggers**:
- Scheduled (nightly)
- Manual trigger (workflow_dispatch)

**Steps**:
1. Setup environment
2. Install dependencies
3. Generate fixtures (if not cached)
4. Run benchmark suite
5. Store results in benchmark-history.json
6. Detect regressions
7. Generate graphs
8. Create GitHub issue if regressions detected
9. Upload artifacts

### PR Benchmarks (Optional)

Can be enabled in `.github/workflows/ci.yml` to run on PRs:
```yaml
benchmark-pr:
  runs-on: ubuntu-latest
  if: contains(github.event.pull_request.labels.*.name, 'benchmark')
  steps:
    - name: Run benchmarks on PR
      run: pytest tests/benchmarks/test_backtest_performance.py --benchmark-only
```

**Note**: Only run on PRs labeled with `benchmark` to avoid slowing down all PRs.

## Dashboard

### Static HTML Dashboard

Location: `docs/performance/dashboard.html`

**Features**:
- Embedded performance graphs
- Scenario comparison table
- Historical trend view
- Last 10 runs summary

**Access**: Open in browser or deploy to GitHub Pages

**Generation**:
```bash
python scripts/benchmarks/generate_dashboard.py
```

### Streamlit Dashboard (Future)

Interactive dashboard with:
- Date range filtering
- Scenario drill-down
- Commit comparison
- Export to CSV

**Run locally**:
```bash
streamlit run scripts/benchmarks/streamlit_dashboard.py
```

## Comparison Tools

### Compare Two Runs
```bash
python scripts/benchmarks/compare_benchmarks.py abc123def xyz789abc
```

Output: Markdown report showing delta per scenario

### Compare PR vs. Main
```bash
# Run benchmarks on PR branch
pytest tests/benchmarks/test_backtest_performance.py --benchmark-only --benchmark-save=pr

# Checkout main
git checkout main

# Run benchmarks on main
pytest tests/benchmarks/test_backtest_performance.py --benchmark-only --benchmark-save=main

# Compare
python scripts/benchmarks/compare_benchmarks.py --saved pr main
```

## Adding New Benchmarks

### 1. Create Strategy
Create new strategy file in `strategies/`:
```python
def initialize(context):
    context.assets = [symbol(f"ASSET{i:03d}") for i in range(context.n_assets)]
    # ... initialization logic

def handle_data(context, data):
    # ... strategy logic
```

### 2. Add Benchmark Test
Add test function in `test_backtest_performance.py`:
```python
@pytest.mark.benchmark(group="daily-new-strategy")
def test_daily_new_strategy_50_assets_rust(benchmark):
    """Benchmark new strategy with 50 assets."""
    result = benchmark(
        run_strategy,
        strategy=NewStrategy(),
        data=load_fixture("daily_50_assets"),
        use_rust=True
    )
    assert result.portfolio_value[-1] > 0
```

### 3. Update Matrix
Document new scenario in this README:
- Add to scenario matrix table
- Explain rationale for inclusion
- Update estimated runtime

### 4. Run and Validate
```bash
pytest tests/benchmarks/test_backtest_performance.py::test_daily_new_strategy_50_assets_rust --benchmark-only -v
```

## Performance Standards

From `docs/architecture/coding-standards.md`:

### Target
- **<30% overhead** vs. float baseline for Decimal + Rust optimizations

### Zero-Mock Enforcement
- NEVER hardcode benchmark results
- ALWAYS measure actual performance
- NEVER simplify benchmarks to pass tests

### Regression Thresholds
- **5% degradation**: Warning (logged)
- **20% degradation**: Hard failure (blocks merge)

## Troubleshooting

### Benchmarks Too Slow
- Reduce dataset size in fixtures
- Use fewer rounds: `--benchmark-min-rounds=1`
- Run subset of scenarios: `-k "daily_simple"`

### Memory Errors
- Check fixture sizes with `du -sh tests/benchmarks/data/`
- Compress fixtures with better compression
- Reduce number of assets in large fixtures

### Inconsistent Results
- Ensure deterministic data generation (same seed)
- Ensure deterministic strategy logic
- Run multiple rounds to average out noise
- Check system load during benchmarks

### Fixture Generation Fails
- Check disk space
- Verify parquet/pyarrow installation
- Check permissions on data/ directory

## Related Documentation

- [Benchmark Guide](../../docs/performance/benchmark-guide.md): Complete guide
- [Story 7.5](../../docs/stories/7.5.implement-comprehensive-benchmarking-suite.story.md): Full story details
- [Coding Standards](../../docs/architecture/coding-standards.md): Performance requirements
- [Regression Tests](../regression/): Performance regression tests

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review existing benchmark results in `docs/performance/`
3. Consult Story 7.5 acceptance criteria
4. Create issue with `benchmark` label

---

**Last Updated**: 2025-01-09
**Story**: 7.5 - Implement Comprehensive Benchmarking Suite
**Author**: James (Full Stack Developer)
**Status**: In Development
