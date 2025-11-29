# Performance Profiling Methodology

**Feature**: Performance Benchmarking and Optimization (002)
**Created**: 2025-10-21
**Status**: Active

---

## Overview

This document describes the systematic methodology for profiling, analyzing, and optimizing the performance of RustyBT backtesting workflows. All profiling follows constitutional requirements and uses real data (CR-002: Zero-Mock Enforcement).

---

## Profiling Infrastructure

### Profiler Backends

We use three complementary profiling tools:

#### 1. cProfile (Function-Level Profiling)
- **Purpose**: Identify which functions consume the most time
- **Granularity**: Function-level
- **Overhead**: Low (~5-10%)
- **Output**: .stats file, JSON summary, text report
- **Use Case**: Initial bottleneck identification

**Usage**:
```python
from rustybt.benchmarks.profiling import profile_workflow

result, metrics = profile_workflow(
    workflow_fn=my_backtest_workflow,
    workflow_args=(params,),
    profiler_type='cprofile',
    output_dir='profiling-results',
    run_id='grid_search_baseline'
)
```

#### 2. line_profiler (Line-Level Profiling)
- **Purpose**: Identify which specific lines within a function are slow
- **Granularity**: Line-level
- **Overhead**: High (~50-100%)
- **Output**: Text report with line timings
- **Use Case**: Deep-dive analysis of specific bottleneck functions

**Installation**:
```bash
pip install line_profiler
```

**Usage**:
```python
result, metrics = profile_workflow(
    workflow_fn=my_bottleneck_function,
    workflow_args=(params,),
    profiler_type='line_profiler',
    output_dir='profiling-results'
)
```

#### 3. memory_profiler (Memory Tracking)
- **Purpose**: Track memory usage over time
- **Granularity**: Time-series sampling (0.1s intervals)
- **Overhead**: High (~50-100%)
- **Output**: JSON with memory usage timeline
- **Use Case**: Identify memory leaks or excessive allocations

**Installation**:
```bash
pip install memory_profiler
```

**Usage**:
```python
result, metrics = profile_workflow(
    workflow_fn=my_workflow,
    workflow_args=(params,),
    profiler_type='memory_profiler',
    output_dir='profiling-results'
)
```

---

## Bottleneck Analysis Workflow

### Step 1: Initial Profiling

Run cProfile on the complete workflow to identify top bottlenecks:

```python
from rustybt.benchmarks.profiling import profile_workflow
from rustybt.benchmarks.reporter import generate_bottleneck_report

# Profile the workflow
_, metrics = profile_workflow(
    workflow_fn=grid_search_optimization,
    workflow_args=(strategy, params),
    profiler_type='cprofile',
    output_dir='profiling-results',
    run_id='grid_search_production'
)

# Generate bottleneck analysis report
json_report, json_path, md_path = generate_bottleneck_report(
    profile_stats_path='profiling-results/grid_search_production_cprofile.stats',
    workflow_name='Grid Search Optimization',
    output_dir='benchmark-results'
)

# Review top bottlenecks
for bottleneck in json_report['summary']['top_5_bottlenecks']:
    print(f"{bottleneck['function']}: {bottleneck['percent_cumtime']:.2f}%")
```

### Step 2: Bottleneck Categorization

The analyzer automatically categorizes bottlenecks as:

- **Fixed Costs** (<10 calls): Initialization, setup, one-time operations
- **Variable Costs** (≥10 calls): Data processing, loops, repeated operations

**Example Output**:
```
TOP 5 BOTTLENECKS:
1. DataPortal.get_history(): 61.5% of runtime (150,000 calls) - VARIABLE
2. Strategy.__init__(): 12.3% of runtime (100 calls) - VARIABLE
3. load_bundle(): 8.7% of runtime (1 call) - FIXED
4. create_calendar(): 5.2% of runtime (1 call) - FIXED
5. compute_returns(): 3.8% of runtime (100 calls) - VARIABLE
```

### Step 3: Threshold Validation

Verify that all operations >0.5% of runtime are identified (FR-006):

```python
bottlenecks_gt_05 = [
    b for b in json_report['bottlenecks']
    if b['percent_cumtime'] >= 0.5
]

assert len(bottlenecks_gt_05) == json_report['summary']['bottlenecks_gt_05_percent']
print(f"✓ Identified {len(bottlenecks_gt_05)} bottlenecks >0.5% of runtime")
```

### Step 4: Deep-Dive Analysis

For critical bottlenecks (>10% of runtime), use line_profiler:

```python
# Profile specific bottleneck function
result, metrics = profile_workflow(
    workflow_fn=DataPortal.get_history,
    workflow_args=(assets, end_date, bar_count),
    profiler_type='line_profiler',
    output_dir='profiling-results',
    run_id='dataportal_deep_dive'
)

# Review line-by-line timings in:
# profiling-results/dataportal_deep_dive_line_profiler.txt
```

---

## Statistical Methodology for Independent Audit

### Overview

All performance benchmarks follow rigorous statistical methodology to ensure reproducibility and validity. This section documents the exact procedures used for confidence interval calculation and significance testing.

### Sample Size Requirements

**Minimum Sample Size**: 10 runs per benchmark
- **Rationale**: Sufficient for 95% confidence intervals with reasonable precision
- **Statistical Power**: Adequate for detecting differences ≥5% with α=0.05, β=0.20
- **Recommended**: 20+ runs for low-variance workloads or strict validation

### Confidence Interval Calculation

**95% Confidence Intervals** are calculated using the t-distribution (recommended for n<30):

```
CI = mean ± t(α/2, n-1) × (std_dev / √n)

Where:
- mean: Sample mean of execution times
- t(α/2, n-1): Critical t-value for 95% CI with n-1 degrees of freedom
- std_dev: Sample standard deviation
- n: Sample size (number of runs)
- α: Significance level (0.05 for 95% CI)
```

**Implementation**:
```python
import scipy.stats as stats
import numpy as np

# Calculate 95% CI
mean = np.mean(execution_times)
std_dev = np.std(execution_times, ddof=1)  # Use sample std dev
n = len(execution_times)
se = std_dev / np.sqrt(n)  # Standard error
t_critical = stats.t.ppf(0.975, n-1)  # Two-tailed 95% CI
ci_lower = mean - t_critical * se
ci_upper = mean + t_critical * se
```

**Interpretation**:
- We are 95% confident the true mean execution time lies within [ci_lower, ci_upper]
- Non-overlapping CIs between baseline and optimized indicate clear improvement

### Statistical Significance Testing

**Paired t-test** is used to compare baseline vs optimized performance:

```
Null Hypothesis (H₀): μ_baseline = μ_optimized (no difference)
Alternative Hypothesis (H₁): μ_baseline > μ_optimized (baseline is slower)
Significance Level: α = 0.05 (p < 0.05 required for rejection)
Test Type: One-tailed paired t-test
```

**Implementation**:
```python
from scipy.stats import ttest_rel

# Perform paired t-test (one-tailed)
t_statistic, p_value_two_tailed = ttest_rel(
    baseline_times,
    optimized_times,
    alternative='greater'  # baseline > optimized
)

# Decision
is_significant = p_value < 0.05
```

**Interpretation**:
- **p < 0.05**: Statistically significant improvement (reject H₀)
- **p ≥ 0.05**: No significant improvement (fail to reject H₀)
- Lower p-values indicate stronger evidence of improvement

### Effect Size Calculation

**Percentage Improvement**:
```
improvement_percent = ((baseline_mean - optimized_mean) / baseline_mean) × 100

Example:
- Baseline mean: 10.5s
- Optimized mean: 6.3s
- Improvement: ((10.5 - 6.3) / 10.5) × 100 = 40.0%
```

**Speedup Ratio**:
```
speedup_ratio = baseline_mean / optimized_mean

Example:
- Baseline mean: 10.5s
- Optimized mean: 6.3s
- Speedup: 10.5 / 6.3 = 1.67x (67% faster)
```

### Reproducibility Requirements

All benchmarks must be reproducible by independent auditors:

1. **Version Control**: All benchmark scripts in `scripts/benchmarks/` with git hash
2. **Data Requirements**: Documented dataset characteristics (size, date range, assets)
3. **Environment Specification**: Python version, dependency versions (`requirements.txt`)
4. **Execution Instructions**: Command-line instructions with all parameters
5. **Raw Data Archive**: All raw timing data saved to `profiling-results/raw_data/`
6. **Statistical Reports**: Complete statistical analysis with CI and p-values

### Benchmark Execution Workflow

All optimizations require **10+ runs** for statistical validity (per FR-004):

```python
from rustybt.benchmarks.profiling import run_benchmark_suite

# Baseline benchmarking
baseline_results = run_benchmark_suite(
    workflow_fn=grid_search_workflow,
    workflow_args=(strategy, params),
    num_runs=10,  # Minimum for 95% CI
    configuration_name="baseline_python",
    workflow_type="grid_search",
    output_dir='benchmark-results',
    dataset_size=252000,  # 1000 days × 252 bars
    parameter_combinations=100,
    backtest_count=100
)

# Optimized benchmarking
optimized_results = run_benchmark_suite(
    workflow_fn=grid_search_workflow_optimized,
    workflow_args=(strategy, params),
    num_runs=10,
    configuration_name="batch_init_optimized",
    workflow_type="grid_search",
    output_dir='benchmark-results',
    dataset_size=252000,
    parameter_combinations=100,
    backtest_count=100
)

# Statistical summary
print(f"Baseline mean: {baseline_results.execution_time_mean:.3f}s")
print(f"Optimized mean: {optimized_results.execution_time_mean:.3f}s")
print(f"95% CI (baseline): [{baseline_results.execution_time_ci_95[0]:.3f}, {baseline_results.execution_time_ci_95[1]:.3f}]")
print(f"95% CI (optimized): [{optimized_results.execution_time_ci_95[0]:.3f}, {optimized_results.execution_time_ci_95[1]:.3f}]")
print(f"Improvement: {((baseline_results.execution_time_mean - optimized_results.execution_time_mean) / baseline_results.execution_time_mean * 100):.2f}%")
```

### Workload Characteristics

For accurate benchmarking, specify workload characteristics:

- **dataset_size**: Number of data rows/bars processed
- **parameter_combinations**: Number of parameter sets tested (Grid/WF)
- **backtest_count**: Number of backtests executed

These metrics enable:
1. Normalization across different workload sizes
2. Fixed vs variable cost analysis
3. Scalability assessment

---

## Threshold Evaluation

### Threshold Configuration System

The optimization framework provides centralized threshold management through `OptimizationConfig`:

```python
from rustybt.optimization.config import OptimizationConfig

# Default configuration (5% improvement, 95% confidence, 10 runs)
config = OptimizationConfig.create_default()

# Strict configuration (10% improvement, 99% confidence, 20 runs)
strict_config = OptimizationConfig.create_strict()

# Lenient configuration (2% improvement, 90% confidence, 10 runs)
lenient_config = OptimizationConfig.create_lenient()

# Get threshold for specific workflow
threshold = config.get_threshold('grid_search', 'production')
print(f"Threshold: {threshold.min_improvement_percent}%")
```

#### Configuration Presets

**Default Configuration** (Production Use):
- Min improvement: 5% (balances measurability with achievability)
- Confidence level: 95% (p<0.05)
- Sample size: 10 runs (minimum for statistical validity)
- Memory limit: 2% increase (per acceptance criteria)
- Goal: 40% cumulative improvement

**Strict Configuration** (High-Stakes Validation):
- Min improvement: 10% (high bar for acceptance)
- Confidence level: 99% (p<0.01)
- Sample size: 20 runs (high statistical power)
- Memory limit: 1% increase (tight constraint)
- Goal: 50% cumulative improvement

**Lenient Configuration** (Experimentation):
- Min improvement: 2% (low bar for exploration)
- Confidence level: 90% (p<0.10)
- Sample size: 10 runs (maintains statistical validity)
- Memory limit: 10% increase (allows some caching overhead)
- Goal: 20% cumulative improvement
- Debug logging: Enabled

### Creating Custom Thresholds

For specific optimization needs:

```python
from rustybt.benchmarks.threshold import create_threshold
from decimal import Decimal

threshold = create_threshold(
    min_improvement_percent=Decimal('5.0'),  # 5% minimum
    workflow_type='grid_search',
    dataset_size_category='production',
    statistical_confidence=Decimal('0.95'),  # 95% confidence
    min_sample_size=10,  # 10 runs minimum
    max_memory_increase_percent=Decimal('2.0'),  # 2% increase max
    rationale="5% threshold balances measurability with achievability"
)

# Add to configuration
config = OptimizationConfig.create_default()
config.set_threshold(threshold)
```

### Statistical Validation Methods

The evaluation framework performs comprehensive statistical analysis:

**1. Mean Improvement Calculation**:
```
improvement_percent = ((baseline_mean - optimized_mean) / baseline_mean) × 100
speedup_ratio = baseline_mean / optimized_mean
```

**2. Statistical Significance Testing**:
- Paired t-test (scipy.stats.ttest_rel) for matched before/after runs
- One-tailed alternative hypothesis (baseline > optimized)
- Significance level: α = 1 - confidence_level
- Null hypothesis rejected if p-value < α

**3. Confidence Interval Analysis**:
- 95% CI calculated for both baseline and optimized means
- Uses z-score (1.96 for 95% CI) or t-distribution for small samples
- CI must not overlap baseline mean for clear improvement

**4. Memory Increase Validation**:
```
memory_increase_percent = ((optimized_memory_peak - baseline_memory_peak) / baseline_memory_peak) × 100
passes_memory_check = memory_increase_percent <= max_memory_increase_percent
```

### Decision Framework

Optimization is **ACCEPTED** if and only if **ALL** criteria met:
1. ✅ Improvement ≥ minimum threshold
2. ✅ Statistically significant (p < α)
3. ✅ Memory increase ≤ maximum percentage
4. ✅ Sample size ≥ minimum required

**Rationale Generation**:
- Accepted: Lists improvement, p-value, memory increase percentage
- Rejected: Explains which criteria failed and by how much

### Evaluating Performance

```python
from rustybt.benchmarks.threshold import evaluate_threshold

eval_result = evaluate_threshold(
    baseline_results=baseline_results,
    optimized_results=optimized_results,
    threshold=threshold,
    include_details=True  # Include detailed metrics
)

if eval_result['passes_threshold']:
    print(f"✓ ACCEPTED: {eval_result['improvement_percent']:.2f}% improvement")
    print(f"  Speedup: {eval_result['speedup_ratio']:.3f}x")
    print(f"  P-value: {eval_result['p_value']:.4f} (significant: {eval_result['statistical_significance']})")
    print(f"  Memory: {eval_result['memory_increase_percent']:.2f}% increase")
    print(f"  95% CI (baseline): [{eval_result['baseline_ci_95'][0]:.3f}, {eval_result['baseline_ci_95'][1]:.3f}]")
    print(f"  95% CI (optimized): [{eval_result['optimized_ci_95'][0]:.3f}, {eval_result['optimized_ci_95'][1]:.3f}])")
else:
    print(f"✗ REJECTED: {eval_result['decision_rationale']}")
```

---

## Sequential Optimization Workflow

Optimizations are evaluated **sequentially** in priority order until:
- Goal achieved (40% cumulative improvement)
- All optimizations evaluated
- Diminishing returns (last 2 rejected)

```python
from rustybt.benchmarks.sequential import evaluate_optimization_sequence

# Define optimizations in priority order (from research.md)
optimizations = [
    batch_init_optimization,      # Rank #1
    multi_tier_cache_optimization, # Rank #2
    persistent_workers_optimization # Rank #3
]

# Evaluation configs for each optimization
configs = {
    'batch_init_v1': {
        'baseline_fn': baseline_batch_init,
        'optimized_fn': optimized_batch_init,
        'test_cases': test_cases,
        'benchmark_workload_fn': grid_search_workflow,
        'benchmark_args': (strategy, params),
        'benchmark_kwargs': {}
    }
}

# Execute sequential evaluation
report = evaluate_optimization_sequence(
    optimizations=optimizations,
    threshold=threshold,
    evaluation_configs=configs,
    output_dir='benchmark-results',
    goal_improvement_percent=Decimal('40.0'),
    stop_on_goal_achieved=True
)

print(f"Cumulative improvement: {report.cumulative_improvement_percent}%")
print(f"Optimizations accepted: {len(report.accepted_optimizations)}")
print(f"Goal achieved: {report.goal_achieved}")
```

---

## Functional Equivalence Validation

**BLOCKING Requirement**: All optimizations must pass functional equivalence tests before performance benchmarking (FR-004).

```python
from rustybt.benchmarks.comparisons import test_functional_equivalence

# Generate test cases
test_cases = [
    (([1.0, 2.0, 3.0, 4.0, 5.0], 3), {}),  # SMA with window=3
    (([10.0] * 100, 20), {}),               # SMA with constant values
    # ... more test cases
]

# Test equivalence (BLOCKING)
try:
    test_functional_equivalence(
        baseline_fn=python_sma,
        optimized_fn=rust_sma,
        test_cases=test_cases,
        tolerance=Decimal('1e-10'),
        comparison_mode='array'
    )
    print("✓ Functional equivalence validated")
except FunctionalEquivalenceError as e:
    print(f"✗ BLOCKED: Functional equivalence failed: {e}")
    # Cannot proceed to performance testing
```

---

## Report Generation

### Bottleneck Report

Generated automatically from cProfile data:

**Markdown Output** (`*_bottlenecks.md`):
- Executive summary
- Top bottlenecks table
- Fixed vs variable cost breakdown
- Memory efficiency issues
- Actionable recommendations

**JSON Output** (`*_bottlenecks.json`):
- Complete bottleneck list
- Statistical metrics
- Machine-readable for further analysis

### Performance Report

Generated after sequential evaluation:

**Markdown Output** (`*_report.md`):
- Cumulative improvement metrics
- Accepted/rejected optimizations
- Decision rationale for each
- Recommendations for future work

**JSON Output** (`*_report.json`):
- Complete evaluation history
- Statistical significance data
- Threshold pass/fail details

---

## Best Practices

### 1. Profiling Environment

- **Consistent Hardware**: Run all benchmarks on same machine
- **Minimal Background**: Close unnecessary applications
- **Stable Load**: Avoid system updates during benchmarking
- **Warm-Up**: Run 1-2 iterations before benchmarking

### 2. Sample Size

- **Minimum**: 10 runs for 95% confidence interval
- **Recommended**: 20 runs for low-variance workloads
- **Required**: 30+ runs for high-variance workloads

### 3. Bottleneck Prioritization

Focus on:
1. **High Impact** (>10% of runtime)
2. **Low Complexity** (easier to optimize)
3. **Low Risk** (low functional consistency risk)

### 4. Decision Documentation

All accept/reject decisions must include:
- Percentage improvement
- Statistical significance (p-value)
- Memory increase percentage
- Functional equivalence status
- Rationale

---

## Constitutional Compliance

This methodology ensures:

✅ **CR-001**: All metrics use Decimal precision
✅ **CR-002**: Zero mocks - all profiling uses real execution
✅ **CR-004**: Complete type safety in all modules
✅ **CR-005**: 95%+ test coverage for infrastructure
✅ **CR-007**: Systematic workflow with decision audit trail

---

## Extended Heavy Operations Profiling

### Batch Initialization Profiling

Profile batch initialization overhead across varying bundle sizes:

**Script**: `scripts/benchmarks/profile_extended_heavy_operations.py`

**Scenarios**:
- 10 assets × 100 backtests
- 50 assets × 100 backtests
- 100 assets × 100 backtests
- 500 assets × 100 backtests

**Metrics Collected**:
- Total initialization time
- Bundle loading time per worker
- Memory usage during initialization
- Data structure creation overhead

**Example Results**:
```
| Assets | Total Time | CPU Time | Bundle Rows |
|--------|-----------|----------|-------------|
|   10   |   0.100s  |  0.517s  |    2,520    |
|   50   |   0.155s  |  0.568s  |   12,600    |
|  100   |   0.230s  |  0.655s  |   25,200    |
|  500   |   0.892s  |  1.311s  |  126,000    |
```

**Flame Graphs**: Generated for each bundle size in `profiling-results/flame_graphs/batch_init_*_assets.svg`

### Parallel Coordinator Efficiency

Profile parallel coordinator at different worker counts:

**Scenarios**:
- 2 workers × 100 tasks
- 4 workers × 100 tasks
- 8 workers × 100 tasks
- 16 workers × 100 tasks

**Metrics Collected**:
- Total execution time
- Worker utilization
- Coordinator overhead
- Task throughput (tasks/second)

**Example Results**:
```
| Workers | Total Time | CPU Time | Observations              |
|---------|-----------|----------|---------------------------|
|    2    |   2.649s  |  0.021s  | Good speedup              |
|    4    |   2.433s  |  0.022s  | Optimal for this workload |
|    8    |   2.784s  |  0.042s  | Coordination overhead     |
|   16    |   5.009s  |  0.089s  | Overhead dominates        |
```

**Key Findings**:
- Optimal worker count: 4 for 100 tasks
- Coordination overhead increases with >8 workers
- multiprocessing.Pool overhead visible in CPU time

**Flame Graphs**: Generated for each worker count in `profiling-results/flame_graphs/parallel_coord_*_workers.svg`

### Missing Components Documentation

**BOHB (Bayesian Optimization and HyperBand)**:
- Status: Not implemented
- Requirement: HpBandSter library integration
- Comparison: Deferred to future story
- Use Case: Multi-fidelity optimization with early stopping

**Ray Distributed Scheduler**:
- Status: Not implemented
- Current: Using multiprocessing.Pool
- Comparison: Deferred to future story when Ray is added
- Use Case: Distributed optimization across multiple machines

**Report Location**: `profiling-results/EXTENDED_OPERATIONS_PROFILING_REPORT.md`

---

## Flame Graph Visualization

All profiling generates SVG flame graphs for visual analysis:

**Color Coding**:
- **Red**: ≥10% of runtime (Critical bottlenecks)
- **Orange**: ≥5% of runtime (Major bottlenecks)
- **Yellow**: ≥1% of runtime (Notable bottlenecks)
- **Blue**: <1% of runtime (Minor bottlenecks)

**Generation**:
```python
from rustybt.benchmarks.profiling import generate_flame_graph

svg_path = generate_flame_graph(
    profile_stats_path='profiling-results/workflow_cprofile.stats',
    output_svg_path='profiling-results/flame_graphs/workflow.svg',
    title='Workflow Profiling',
    min_percent=0.5  # Show operations ≥0.5% runtime
)
```

**Location**: All flame graphs are saved to `profiling-results/flame_graphs/` directory

---

## References

- Story: `docs/internal/stories/X4.1.setup-validation-infrastructure.story.md`
- Consolidated Report: `profiling-results/CONSOLIDATED_PROFILING_REPORT.md`
- Extended Profiling Report: `profiling-results/EXTENDED_OPERATIONS_PROFILING_REPORT.md`
- Feature Specification: `specs/002-performance-benchmarking-optimization/spec.md`
- Research Analysis: `specs/002-performance-benchmarking-optimization/research.md`
- Data Model: `specs/002-performance-benchmarking-optimization/data-model.md`
- Implementation Plan: `specs/002-performance-benchmarking-optimization/plan.md`

---

*Last Updated*: 2025-10-22
*Version*: 1.1
*Status*: Active - Extended with X4.1 profiling scenarios
