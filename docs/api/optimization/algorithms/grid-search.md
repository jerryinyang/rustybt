# Grid Search Algorithm

Exhaustive search over all parameter combinations in a discrete grid.

## Overview

Grid search evaluates every possible combination of parameters in the search space. It's deterministic, complete, but computationally expensive for large spaces.

## When to Use

✅ **Use grid search when**:
- Parameter space is small (<1000 combinations)
- You need exhaustive coverage
- You want deterministic results
- You have sufficient computational resources
- You're doing final verification in a narrow region

❌ **Don't use grid search when**:
- Parameter space is large (>10,000 combinations)
- You have continuous parameters with fine granularity
- Computational budget is limited
- Initial exploration phase

## Basic Usage

```python
from rustybt.optimization.search import GridSearchAlgorithm
from rustybt.optimization.parameter_space import ParameterSpace, DiscreteParameter

# Define parameter space
param_space = ParameterSpace(parameters=[
    DiscreteParameter('lookback_short', 10, 50, step=10),  # 5 values
    DiscreteParameter('lookback_long', 50, 200, step=50)   # 4 values
])
# Total: 5 * 4 = 20 combinations

# Create grid search algorithm
grid = GridSearchAlgorithm(parameter_space=param_space)

# Optimization loop
while not grid.is_complete():
    params = grid.suggest()
    score = run_backtest(params)
    grid.update(params, score)

# Get best parameters
best_params = grid.get_best_params()
best_score = grid.get_best_score()

print(f"Best parameters: {best_params}")
print(f"Best Sharpe: {best_score}")
```

## Constructor

```python
GridSearchAlgorithm(
    parameter_space: ParameterSpace,
    early_stopping_rounds: Optional[int] = None
)
```

**Parameters**:
- `parameter_space`: ParameterSpace defining the grid
- `early_stopping_rounds`: Stop if no improvement for N consecutive evaluations (None = disabled)

## Methods

### suggest()

Returns next parameter combination to evaluate.

```python
params = grid.suggest()
# Returns: {'lookback_short': 10, 'lookback_long': 50}
```

**Behavior**:
- Iterates through combinations in deterministic order
- Raises `ValueError` if grid is complete

### update(params, score)

Updates internal state with evaluation result.

```python
grid.update(params, score)
```

**Parameters**:
- `params`: Parameter dict that was evaluated
- `score`: Decimal score (higher = better)

**Behavior**:
- Tracks best parameters and score
- Updates progress counter
- Checks early stopping condition

### is_complete()

Checks if all combinations have been evaluated.

```python
if grid.is_complete():
    print("Grid search finished!")
```

**Returns**: `True` if complete, `False` otherwise

### get_best_params()

Returns best parameters found.

```python
best = grid.get_best_params()
# Returns: {'lookback_short': 30, 'lookback_long': 150}
```

### get_results(top_k=None)

Returns all results sorted by score.

```python
top_5 = grid.get_results(top_k=5)
for params, score in top_5:
    print(f"Sharpe {score:.2f}: {params}")
```

## Properties

### total_combinations

Total number of combinations in grid.

```python
print(f"Total combinations: {grid.total_combinations}")
```

### progress

Current progress as fraction (0.0 to 1.0).

```python
print(f"Progress: {grid.progress * 100:.1f}%")
```

## Early Stopping

Stop optimization if no improvement for N iterations:

```python
grid = GridSearchAlgorithm(
    parameter_space=param_space,
    early_stopping_rounds=50  # Stop after 50 evals without improvement
)

while not grid.is_complete():
    params = grid.suggest()
    score = run_backtest(params)
    grid.update(params, score)

    if grid.early_stopped:
        print(f"Early stopped after {grid.evaluations_count} evaluations")
        break
```

**Use case**: Large grids where you want option to stop early if a clear winner emerges.

## Complete Example

```python
from decimal import Decimal
from rustybt.optimization.search import GridSearchAlgorithm
from rustybt.optimization.parameter_space import (
    ParameterSpace,
    DiscreteParameter,
    CategoricalParameter
)

# Define parameter space
param_space = ParameterSpace(parameters=[
    DiscreteParameter('lookback_short', 10, 50, step=10),
    DiscreteParameter('lookback_long', 50, 200, step=50),
    CategoricalParameter('signal_type', ['momentum', 'mean_reversion'])
])

print(f"Total combinations: {param_space.cardinality()}")  # 5 * 4 * 2 = 40

# Run grid search
def run_backtest(params):
    # Your backtest logic
    result = backtest_strategy(params)
    return Decimal(str(result['sharpe_ratio']))

grid = GridSearchAlgorithm(parameter_space=param_space)

print("Starting grid search...")
results = []

while not grid.is_complete():
    params = grid.suggest()
    score = run_backtest(params)
    grid.update(params, score)

    results.append((params, score))
    print(f"Progress: {grid.progress*100:.1f}% | "
          f"Current: {score:.2f} | "
          f"Best: {grid.get_best_score():.2f}")

# Analyze results
best_params = grid.get_best_params()
best_score = grid.get_best_score()

print(f"\n=== Grid Search Complete ===")
print(f"Best Sharpe Ratio: {best_score:.3f}")
print(f"Best Parameters: {best_params}")

# Top 5 results
print(f"\nTop 5 Results:")
for i, (params, score) in enumerate(grid.get_results(top_k=5), 1):
    print(f"{i}. Sharpe {score:.3f}: {params}")
```

## Visualization

### Heatmap for 2-Parameter Grid

```python
import matplotlib.pyplot as plt
import numpy as np

def plot_grid_heatmap(results, param_x, param_y):
    """Plot heatmap of grid search results."""
    # Extract unique parameter values
    x_values = sorted(set(r[0][param_x] for r in results))
    y_values = sorted(set(r[0][param_y] for r in results))

    # Create grid
    grid = np.zeros((len(y_values), len(x_values)))

    # Fill grid with scores
    for params, score in results:
        i = y_values.index(params[param_y])
        j = x_values.index(params[param_x])
        grid[i, j] = float(score)

    # Plot
    fig, ax = plt.subplots(figsize=(10, 8))
    im = ax.imshow(grid, cmap='RdYlGn', aspect='auto')

    ax.set_xticks(range(len(x_values)))
    ax.set_yticks(range(len(y_values)))
    ax.set_xticklabels(x_values)
    ax.set_yticklabels(y_values)

    ax.set_xlabel(param_x)
    ax.set_ylabel(param_y)
    ax.set_title('Grid Search Results Heatmap')

    # Add colorbar
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label('Sharpe Ratio')

    # Add text annotations
    for i in range(len(y_values)):
        for j in range(len(x_values)):
            text = ax.text(j, i, f'{grid[i, j]:.2f}',
                          ha="center", va="center", color="black", fontsize=8)

    plt.tight_layout()
    return fig

# Usage
results = grid.get_results()
fig = plot_grid_heatmap(results, 'lookback_short', 'lookback_long')
plt.show()
```

### Convergence Plot

```python
def plot_convergence(results):
    """Plot best score vs evaluations."""
    scores = [score for _, score in results]
    best_so_far = []
    current_best = float('-inf')

    for score in scores:
        if score > current_best:
            current_best = score
        best_so_far.append(current_best)

    plt.figure(figsize=(12, 6))
    plt.plot(best_so_far, linewidth=2)
    plt.xlabel('Evaluation Number')
    plt.ylabel('Best Sharpe Ratio')
    plt.title('Grid Search Convergence')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()

# Usage
plot_convergence(results)
```

## Performance Optimization

### Parallel Grid Search

Grid search is embarrassingly parallel:

```python
from rustybt.optimization import ParallelOptimizer

parallel_grid = ParallelOptimizer(
    objective_function=run_backtest,
    parameter_space=param_space,
    algorithm='grid',
    n_jobs=8  # Use 8 CPU cores
)

result = parallel_grid.optimize()
print(f"Best params: {result.best_params}")
```

**Speedup**: Nearly linear with number of cores for independent evaluations.

### Caching Results

Cache results to avoid re-evaluation:

```python
from functools import lru_cache

@lru_cache(maxsize=10000)
def cached_backtest(param_tuple):
    params = dict(param_tuple)
    return run_backtest(params)

def objective_wrapper(params):
    # Convert dict to hashable tuple
    param_tuple = tuple(sorted(params.items()))
    return cached_backtest(param_tuple)

# Use wrapper in grid search
grid = GridSearchAlgorithm(param_space)
# ... use objective_wrapper instead of run_backtest
```

## Best Practices

### 1. Start Coarse, Refine Later

```python
# Phase 1: Coarse grid
coarse_space = ParameterSpace(parameters=[
    DiscreteParameter('lookback', 10, 100, step=20)  # 5 values
])
coarse_grid = GridSearchAlgorithm(coarse_space)
coarse_result = coarse_grid.optimize()

# Phase 2: Fine grid around best
best = coarse_result.best_params['lookback']
fine_space = ParameterSpace(parameters=[
    DiscreteParameter('lookback', best-10, best+10, step=2)  # 11 values
])
fine_grid = GridSearchAlgorithm(fine_space)
final_result = fine_grid.optimize()
```

### 2. Use Constraints to Reduce Space

```python
# Without constraints: 10 * 10 = 100 combinations
# With constraint: ~50 combinations
param_space = ParameterSpace(
    parameters=[
        DiscreteParameter('ma_short', 10, 100, step=10),
        DiscreteParameter('ma_long', 10, 100, step=10)
    ],
    constraints=[
        lambda p: p['ma_short'] < p['ma_long']  # Reduces combinations
    ]
)
```

### 3. Monitor Progress

```python
import time

start_time = time.time()
evaluations = 0

while not grid.is_complete():
    params = grid.suggest()
    score = run_backtest(params)
    grid.update(params, score)

    evaluations += 1
    elapsed = time.time() - start_time
    evals_per_sec = evaluations / elapsed
    remaining = (grid.total_combinations - evaluations) / evals_per_sec

    print(f"Progress: {grid.progress*100:.1f}% | "
          f"ETA: {remaining/60:.1f} min | "
          f"Best: {grid.get_best_score():.3f}")
```

## Comparison with Other Algorithms

| Aspect | Grid Search | Random Search | Bayesian |
|--------|-------------|---------------|----------|
| **Coverage** | Complete | Partial | Focused |
| **Deterministic** | Yes | No | No |
| **Speed** | Slow | Fast | Medium |
| **Best For** | Small spaces | Large spaces | Expensive objectives |
| **Parallelizable** | Yes | Yes | Limited |

## Common Pitfalls

### ❌ Too Fine Granularity

```python
# Bad: Too many combinations (91 values!)
DiscreteParameter('lookback', 10, 100, step=1)

# Good: Reasonable granularity (10 values)
DiscreteParameter('lookback', 10, 100, step=10)
```

### ❌ Unbounded Continuous Parameters

```python
# Bad: Infinite combinations
ContinuousParameter('threshold', 0.01, 0.10)  # Can't grid search!

# Good: Discretize for grid search
DiscreteParameter('threshold_x100', 1, 10, step=1)  # Then divide by 100
```

### ❌ Too Many Parameters

```python
# Bad: 10^6 combinations!
param_space = ParameterSpace(parameters=[
    DiscreteParameter('p1', 1, 10, step=1),   # 10 values
    DiscreteParameter('p2', 1, 10, step=1),   # 10 values
    DiscreteParameter('p3', 1, 10, step=1),   # 10 values
    DiscreteParameter('p4', 1, 10, step=1),   # 10 values
    DiscreteParameter('p5', 1, 10, step=1),   # 10 values
    DiscreteParameter('p6', 1, 10, step=1),   # 10 values
])  # 10^6 = 1,000,000 combinations!

# Good: Fewer parameters or use random/Bayesian search
```

## See Also

- [Random Search](random-search.md)
- [Bayesian Optimization](bayesian.md)
- [Parallel Processing](../parallel/multiprocessing.md)
- [Parameter Spaces](../framework/parameter-spaces.md)
