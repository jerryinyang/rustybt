

# Benchmarking Methodology

**Version:** 1.0
**Last Updated:** 2025-10-01
**Purpose:** Establish performance baseline for Epic 7 Rust optimization

## Overview

This document describes the benchmarking methodology used to measure Decimal implementation overhead compared to float baseline, identify performance hotspots, and establish optimization targets for Epic 7 (Rust Performance Optimization).

## Benchmarking Framework

### Tools

- **pytest-benchmark** (≥3.4.1): Statistical benchmarking framework
  - Automatic warmup and calibration
  - Statistical analysis (mean, median, std dev, confidence intervals)
  - Comparison with baseline results
  - JSON export for historical tracking

- **cProfile** (stdlib): Function-level profiling
  - Call count and cumulative time tracking
  - Integration with snakeviz for visualization

- **memory_profiler** (≥0.61.0): Memory usage tracking
  - Peak memory usage measurement
  - Memory overhead calculation

- **snakeviz** (≥2.2.0): Profile visualization
  - Interactive call graphs
  - Flame chart visualization

### Configuration

**pytest-benchmark settings** (`pyproject.toml`):

```toml
[tool.pytest-benchmark]
min_rounds = 10              # Minimum 10 statistical rounds
min_time = 0.1               # Minimum 100ms per round
max_time = 10.0              # Maximum 10s per round
calibration_precision = 10   # 10% calibration precision
warmup = true                # Enable warmup phase
warmup_iterations = 5        # 5 warmup iterations
```

### Benchmark Execution

Run benchmarks:

```bash
# Run all benchmarks
pytest benchmarks/ --benchmark-only

# Run with autosave and comparison
pytest benchmarks/ --benchmark-only --benchmark-autosave --benchmark-compare

# Run specific benchmark
pytest benchmarks/decimal_ledger_benchmark.py --benchmark-only

# Generate JSON results
pytest benchmarks/ --benchmark-only --benchmark-json=results/benchmark.json
```

## Benchmark Types

### 1. End-to-End Backtest Benchmarks

**Purpose:** Measure overall system performance

**Methodology:**
- Run identical backtests using float vs Decimal implementations
- Strategy: Simple moving average crossover (20/50 day)
- Data: 1 year daily bars, 100 assets
- Metrics: Total execution time, peak memory usage
- Iterations: 10 rounds minimum

**Files:**
- `benchmarks/baseline_float_backtest.py`
- `benchmarks/decimal_backtest.py`

### 2. Per-Module Micro-Benchmarks

**Purpose:** Isolate overhead sources per module

**Modules Benchmarked:**
- DecimalLedger: Portfolio calculations
- DecimalOrder: Order processing
- Decimal Metrics: Performance metrics
- Data Pipeline: Data loading and processing

**Methodology:**
- Benchmark individual operations (e.g., `portfolio_value`, `order_fill`)
- Use realistic data volumes (100-1000 positions, 252-1000 returns)
- Measure per-operation overhead in microseconds/milliseconds
- Compare with float equivalent implementations

### 3. Scalability Benchmarks

**Purpose:** Measure performance characteristics vs data size

**Methodology:**
- Parameterized tests with varying data sizes
- Test cases: 10, 100, 1000, 10000 positions/returns
- Measure complexity: O(n) linear, O(n²) quadratic, etc.
- Plot performance curves

**Example:**
```python
@pytest.mark.parametrize("num_positions", [10, 100, 1000, 10000])
def test_portfolio_value_scalability(benchmark, num_positions):
    ledger = create_portfolio_with_positions(num_positions)
    result = benchmark(lambda: ledger.portfolio_value)
```

### 4. Memory Overhead Benchmarks

**Purpose:** Measure memory consumption

**Methodology:**
- Use `tracemalloc` or `memory_profiler`
- Measure peak memory usage during operations
- Calculate overhead: `(Decimal_memory / float_memory - 1) × 100%`
- Expected: ~100-150% overhead (2-2.5x) due to Decimal size

### 5. Hotspot Profiling

**Purpose:** Identify optimization targets for Epic 7

**Methodology:**
- Run full backtest with cProfile enabled
- Sort by cumulative time
- Extract top 10-20 time-consuming functions
- Visualize with snakeviz flame charts
- Prioritize for Rust optimization

**Example:**
```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()
run_decimal_backtest()
profiler.disable()

stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)
```

## Metrics

### Primary Metrics

1. **Execution Time:**
   - Mean execution time (μ)
   - Median execution time (p50)
   - Standard deviation (σ)
   - 95th percentile (p95)

2. **Overhead Calculation:**
   ```
   Overhead% = (Decimal_time / float_time - 1) × 100
   ```

3. **Memory Usage:**
   - Peak memory (MB)
   - Memory overhead %

4. **Throughput:**
   - Operations per second
   - Transactions per second

### Statistical Rigor

- **Warmup:** 5 iterations to warm up caches
- **Calibration:** Automatic iteration count adjustment
- **Rounds:** Minimum 10 statistical rounds
- **Outlier Detection:** IQR method for outlier removal
- **Confidence Intervals:** 95% confidence intervals reported

## Hardware Environment

### CI/CD Benchmarks

- **Platform:** GitHub Actions Ubuntu runner
- **CPU:** 2-core Intel Xeon
- **Memory:** 7GB RAM
- **Python:** 3.12
- **Consistency:** Dedicated runner for reproducibility

### Local Development

- **Platform:** macOS/Linux/Windows
- **Note:** Results may vary, use CI/CD for official baselines

## Result Storage

### Directory Structure

```
benchmarks/results/
├── float_baseline.json         # Float implementation baseline
├── decimal_backtest.json       # Decimal implementation results
├── decimal_ledger.json         # DecimalLedger benchmarks
├── decimal_order.json          # DecimalOrder benchmarks
├── decimal_metrics.json        # Metrics calculation benchmarks
├── decimal_data_pipeline.json  # Data pipeline benchmarks
└── memory_overhead.json        # Memory usage results
```

### JSON Format

```json
{
  "rustybt_metadata": {
    "version": "1.0",
    "benchmark_type": "decimal_baseline",
    "purpose": "Epic 7 Rust optimization baseline"
  },
  "benchmarks": [
    {
      "name": "test_portfolio_value",
      "stats": {
        "mean": 0.000923,
        "median": 0.000912,
        "stddev": 0.000043,
        "min": 0.000876,
        "max": 0.001021
      }
    }
  ]
}
```

## Overhead Analysis

### Calculation Method

1. **Load baseline (float) results:**
   ```python
   with open("results/float_baseline.json") as f:
       float_results = json.load(f)
   float_time = float_results["benchmarks"][0]["stats"]["mean"]
   ```

2. **Load Decimal results:**
   ```python
   with open("results/decimal_backtest.json") as f:
       decimal_results = json.load(f)
   decimal_time = decimal_results["benchmarks"][0]["stats"]["mean"]
   ```

3. **Calculate overhead:**
   ```python
   overhead = (decimal_time / float_time - 1) * 100
   print(f"Overhead: {overhead:.1f}%")
   ```

### Interpretation

- **<10% overhead:** Excellent, minor optimization needed
- **10-30% overhead:** Acceptable, moderate optimization target
- **30-50% overhead:** High, priority optimization target
- **>50% overhead:** Critical, top priority for Rust optimization

## Epic 7 Optimization Targets

### Overall Target

**Goal:** Reduce overall Decimal overhead to <30% vs float baseline

### Module Targets

| Module | Current Overhead | Epic 7 Target | Reduction Needed |
|--------|------------------|---------------|------------------|
| DecimalLedger | ~30% | <15% | 50% reduction |
| DecimalOrder | ~25% | <10% | 60% reduction |
| Decimal Metrics | ~40% | <20% | 50% reduction |
| Data Pipeline | ~20% | <10% | 50% reduction |

### Optimization Priority

1. **Priority 1:** Decimal arithmetic operations (highest impact)
2. **Priority 2:** Metrics calculations (computationally intensive)
3. **Priority 3:** Data aggregation (large data volumes)

## Regression Tracking

### CI/CD Integration

- **Trigger:** On release tags, manual dispatch, weekly schedule
- **Baseline Comparison:** Compare with previous release
- **Regression Threshold:** Fail if performance degrades >10%
- **Historical Tracking:** Store results for trend analysis

### Benchmark Dashboard

- **Location:** GitHub Pages or custom dashboard
- **Metrics:**
  - Overhead % over time
  - Execution time trends
  - Memory usage trends
- **Alerts:** Email notification on regression

## Best Practices

### Writing Benchmarks

1. **Use realistic data:** Don't benchmark trivial operations
2. **Avoid caching:** Ensure benchmarks measure actual computation
3. **Verify correctness:** Assert results are correct, not just fast
4. **Document assumptions:** Specify data sizes, iterations
5. **Follow Zero-Mock:** Benchmark real implementations only

### Running Benchmarks

1. **Quiet environment:** Close unnecessary applications
2. **Consistent conditions:** Same hardware, OS, Python version
3. **Multiple runs:** Verify consistency across runs
4. **Save results:** Always save for comparison
5. **Version control:** Commit benchmark results to track history

## Troubleshooting

### High Variance

**Symptom:** Large standard deviation in results

**Solutions:**
- Increase `min_rounds` to 20-50
- Increase `min_time` to 0.5-1.0 seconds
- Run on quieter system (close background apps)
- Use dedicated benchmark runner

### Unrealistic Results

**Symptom:** Benchmark too fast (microseconds for complex operation)

**Solutions:**
- Verify not benchmarking cached result
- Check for hardcoded return values
- Ensure actual computation is performed
- Add assertions to verify correctness

### Memory Profiling Issues

**Symptom:** `memory_profiler` slow or inaccurate

**Solutions:**
- Use `tracemalloc` (faster, stdlib)
- Sample less frequently
- Profile smaller data subsets first

---

**References:**
- pytest-benchmark docs: https://pytest-benchmark.readthedocs.io/
- cProfile docs: https://docs.python.org/3/library/profile.html
- memory_profiler: https://github.com/pythonprofilers/memory_profiler
