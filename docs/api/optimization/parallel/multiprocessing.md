# Parallel Optimization with Multiprocessing

Accelerate optimization by evaluating parameter combinations in parallel across multiple CPU cores.

## Overview

Parallel optimization distributes backtest evaluations across multiple processes, dramatically reducing optimization time for embarrassingly parallel algorithms (grid search, random search, genetic algorithms).

## When to Use

✅ **Use parallel optimization when**:
- Optimization takes >1 hour sequentially
- Each backtest evaluation is independent
- You have multiple CPU cores available
- Algorithm supports parallelization (grid, random, genetic)

❌ **Don't use parallel optimization when**:
- Optimization is already fast (<10 minutes)
- Algorithm requires sequential evaluation (Bayesian)
- System resources are limited
- Debugging optimization issues

## Basic Usage

```python
from rustybt.optimization import ParallelOptimizer
from rustybt.optimization.parameter_space import ParameterSpace, DiscreteParameter

# Define parameter space
param_space = ParameterSpace(parameters=[
    DiscreteParameter('lookback', 10, 100, step=10),
    DiscreteParameter('threshold_x100', 1, 10, step=1)
])

# Create parallel optimizer
parallel = ParallelOptimizer(
    objective_function=run_backtest,
    parameter_space=param_space,
    algorithm='grid',
    n_jobs=4  # Use 4 CPU cores
)

# Run optimization (automatically parallelized)
result = parallel.optimize()

print(f"Best params: {result.best_params}")
print(f"Best score: {result.best_score}")
print(f"Time saved: {result.speedup:.1f}x")
```

## Constructor

```python
ParallelOptimizer(
    objective_function: Callable,
    parameter_space: ParameterSpace,
    algorithm: Literal['grid', 'random', 'genetic'],
    n_iterations: int = 100,
    n_jobs: int = -1,
    backend: str = 'multiprocessing',
    **algorithm_kwargs
)
```

**Parameters**:
- `objective_function`: Function to optimize (must be picklable)
- `parameter_space`: Parameter space to search
- `algorithm`: Algorithm ('grid', 'random', 'genetic' - NOT 'bayesian')
- `n_iterations`: Total evaluations
- `n_jobs`: Number of parallel workers (-1 = all CPUs, -2 = all but one)
- `backend`: Parallelization backend ('multiprocessing', 'ray')
- `**algorithm_kwargs`: Algorithm-specific parameters

## Supported Algorithms

### Grid Search (Ideal for Parallelization)

```python
parallel_grid = ParallelOptimizer(
    objective_function=run_backtest,
    parameter_space=param_space,
    algorithm='grid',
    n_jobs=8
)

result = parallel_grid.optimize()
```

**Speedup**: Nearly linear (8 cores ≈ 8x faster)

### Random Search

```python
parallel_random = ParallelOptimizer(
    objective_function=run_backtest,
    parameter_space=param_space,
    algorithm='random',
    n_iterations=1000,
    n_jobs=8,
    random_seed=42
)

result = parallel_random.optimize()
```

**Speedup**: Nearly linear

### Genetic Algorithm

```python
parallel_ga = ParallelOptimizer(
    objective_function=run_backtest,
    parameter_space=param_space,
    algorithm='genetic',
    n_jobs=8,
    population_size=40,  # Parallelizes population evaluation
    n_generations=50
)

result = parallel_ga.optimize()
```

**Speedup**: Depends on population size (larger = better)

### ❌ Bayesian (Not Supported)

```python
# WRONG: Bayesian requires sequential evaluation
parallel = ParallelOptimizer(
    ...,
    algorithm='bayesian'  # NOT SUPPORTED
)
```

**Why not?** Bayesian optimization updates model sequentially based on previous evaluations.

## Complete Example

```python
from decimal import Decimal
from rustybt.optimization import ParallelOptimizer
from rustybt.optimization.parameter_space import ParameterSpace, DiscreteParameter
import time

# Define objective function (must be picklable)
def run_backtest_with_params(params):
    """
    Backtest function for parallel execution.

    IMPORTANT: Must be module-level function, not lambda or nested.
    """
    result = run_backtest(
        strategy=MACrossover(
            short_window=params['ma_short'],
            long_window=params['ma_long']
        ),
        start_date='2020-01-01',
        end_date='2023-12-31'
    )
    return Decimal(str(result['sharpe_ratio']))

# Define parameter space
param_space = ParameterSpace(parameters=[
    DiscreteParameter('ma_short', 10, 50, step=5),   # 9 values
    DiscreteParameter('ma_long', 50, 200, step=25)   # 7 values
])
# Total: 9 * 7 = 63 combinations

print(f"Total combinations: {param_space.cardinality()}")
print("Running sequential grid search...")

# Sequential baseline
start = time.time()
sequential = Optimizer(
    objective_function=run_backtest_with_params,
    parameter_space=param_space,
    algorithm='grid'
)
seq_result = sequential.optimize()
seq_time = time.time() - start

print(f"Sequential time: {seq_time:.1f}s")
print(f"Best Sharpe: {seq_result.best_score:.3f}")

# Parallel optimization
print("\nRunning parallel grid search...")
start = time.time()

parallel = ParallelOptimizer(
    objective_function=run_backtest_with_params,
    parameter_space=param_space,
    algorithm='grid',
    n_jobs=8  # 8 cores
)

par_result = parallel.optimize()
par_time = time.time() - start

print(f"Parallel time: {par_time:.1f}s")
print(f"Best Sharpe: {par_result.best_score:.3f}")
print(f"Speedup: {seq_time/par_time:.1f}x")

# Results should be identical
assert seq_result.best_params == par_result.best_params
assert seq_result.best_score == par_result.best_score
```

## Performance Optimization

### Optimal Worker Count

```python
import multiprocessing

# Number of CPU cores
n_cores = multiprocessing.cpu_count()

# Conservative (leave 1 core for system)
n_jobs = n_cores - 1

# Aggressive (use all cores)
n_jobs = n_cores

# Hyperthreading consideration
# If CPU has hyperthreading, physical cores often better
n_physical_cores = n_cores // 2
```

**Rule of thumb**:
- Local machine: `n_cores - 1`
- Dedicated server: `n_cores`
- Shared environment: `n_cores // 2`

### Batch Size

```python
parallel = ParallelOptimizer(
    ...,
    n_jobs=8,
    batch_size=10  # Evaluate 10 at a time per worker
)
```

**Considerations**:
- Larger batches = less overhead, but less responsive
- Smaller batches = more overhead, but better progress reporting
- Default (`None`) = automatic chunking

### Memory Management

```python
# Limit memory per worker
parallel = ParallelOptimizer(
    ...,
    n_jobs=4,  # Fewer workers if memory-constrained
    max_memory_per_worker='2GB'
)
```

## Distributed Computing

### Ray Backend

For multi-machine parallelization:

**Advantages**:
- Scales beyond single machine
- Fault tolerance
- Better resource management

**Setup**:
```bash
pip install ray
ray start --head  # Start Ray cluster
```

### Dask Backend

Alternative distributed backend:

## Progress Monitoring

### Progress Callback

```python
def progress_callback(iteration, total, best_score):
    """Called after each evaluation."""
    percent = iteration / total * 100
    print(f"[{percent:.1f}%] Iteration {iteration}/{total}, Best: {best_score:.3f}")

parallel = ParallelOptimizer(
    ...,
    callback=progress_callback
)
```

### Real-Time Dashboard

## Best Practices

### 1. Make Objective Function Picklable

```python
# ❌ WRONG: Lambda not picklable
objective = lambda p: run_backtest(p)['sharpe']

# ❌ WRONG: Nested function not picklable
def outer():
    def run_backtest_inner(params):
        return calculate_sharpe(...)
    return run_backtest_inner

# ✅ RIGHT: Module-level function
def run_backtest_picklable(params):
    """Module-level function can be pickled."""
    result = run_backtest(params)
    return Decimal(str(result['sharpe']))
```

### 2. Profile Before Parallelizing

```python
import cProfile

# Profile single evaluation
def profile_backtest():
    params = {'lookback': 50}
    cProfile.run('run_backtest(params)')

# Identify bottlenecks before parallelizing
```

### 3. Minimize Data Transfer

```python
# ❌ BAD: Sending large datasets to workers
def objective_bad(params):
    # large_dataset passed to each worker
    return backtest(params, data=large_dataset)

# ✅ GOOD: Load data in each worker
def objective_good(params):
    # Each worker loads data once
    data = load_cached_data()
    return backtest(params, data=data)
```

### 4. Handle Failures Gracefully

```python
def robust_objective(params):
    """Objective function with error handling."""
    try:
        result = run_backtest(params)
        return calculate_sharpe(result)
    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        return Decimal('-Infinity')

parallel = ParallelOptimizer(
    objective_function=robust_objective,
    ...,
    ignore_errors=True  # Continue on worker failures
)
```

## Benchmarking

### Speedup Measurement

```python
def benchmark_parallelization(param_space, n_jobs_list):
    """Benchmark different worker counts."""
    results = {}

    # Sequential baseline
    start = time.time()
    seq = Optimizer(objective_function=run_backtest,
                   parameter_space=param_space,
                   algorithm='grid')
    seq.optimize()
    baseline_time = time.time() - start

    print(f"Sequential: {baseline_time:.1f}s")

    # Test different worker counts
    for n_jobs in n_jobs_list:
        start = time.time()
        parallel = ParallelOptimizer(
            objective_function=run_backtest,
            parameter_space=param_space,
            algorithm='grid',
            n_jobs=n_jobs
        )
        parallel.optimize()
        parallel_time = time.time() - start

        speedup = baseline_time / parallel_time
        efficiency = speedup / n_jobs

        print(f"{n_jobs} workers: {parallel_time:.1f}s, "
              f"speedup={speedup:.2f}x, "
              f"efficiency={efficiency:.1%}")

        results[n_jobs] = {
            'time': parallel_time,
            'speedup': speedup,
            'efficiency': efficiency
        }

    return results

# Run benchmark
results = benchmark_parallelization(
    param_space=my_space,
    n_jobs_list=[2, 4, 8, 16]
)
```

### Expected Speedups

| Workers | Ideal Speedup | Typical Speedup | Efficiency |
|---------|---------------|-----------------|------------|
| 2 | 2.0x | 1.8x | 90% |
| 4 | 4.0x | 3.5x | 88% |
| 8 | 8.0x | 6.5x | 81% |
| 16 | 16.0x | 11.0x | 69% |

**Note**: Diminishing returns beyond 8-16 cores due to overhead.

## Common Pitfalls

### ❌ Non-Picklable Objects

```python
# WRONG: Class methods not picklable
class Strategy:
    def objective(self, params):
        return self.run_backtest(params)

parallel = ParallelOptimizer(
    objective_function=strategy.objective  # FAILS!
)

# RIGHT: Use module-level function
def objective(params):
    return run_backtest(params)
```

### ❌ Too Many Workers

```python
# WRONG: More workers than CPU cores
parallel = ParallelOptimizer(..., n_jobs=32)  # But only 8 cores!

# RIGHT: Match CPU count
parallel = ParallelOptimizer(..., n_jobs=8)
```

### ❌ Shared State

```python
# WRONG: Modifying shared state
global_cache = {}

def objective(params):
    global_cache[params] = result  # Race condition!

# RIGHT: No shared state or use locks
def objective(params):
    # Each worker independent
    return run_backtest(params)
```

## Troubleshooting

### Issue: Slower than Sequential

**Possible causes**:
- Overhead exceeds benefit (backtests too fast)
- Data transfer bottleneck
- Disk I/O contention

**Solutions**:
- Use caching to reduce I/O
- Increase batch size
- Reduce worker count

### Issue: Out of Memory

**Possible causes**:
- Too many workers
- Each worker loading large datasets

**Solutions**:
- Reduce `n_jobs`
- Use memory-mapped data
- Implement data streaming

### Issue: Inconsistent Results

**Possible causes**:
- Random seed not set
- Race conditions

**Solutions**:
```python
parallel = ParallelOptimizer(
    ...,
    random_seed=42,  # Ensure reproducibility
    deterministic=True
)
```

## See Also

- [Grid Search](../algorithms/grid-search.md)
- [Random Search](../algorithms/random-search.md)
- [Genetic Algorithms](../algorithms/genetic.md)
- [Main Optimization API](../../optimization-api.md)
