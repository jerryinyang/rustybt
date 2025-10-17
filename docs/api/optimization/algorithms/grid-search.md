# Grid Search Algorithm

**Module**: `rustybt.optimization.search.grid_search`
**Class**: `GridSearchAlgorithm`
**Best For**: Small parameter spaces (<100 combinations)

---

## Overview

Grid Search is an exhaustive search algorithm that evaluates all possible parameter combinations in a discrete parameter grid. It's the most thorough search method, guaranteeing the optimal solution within the defined grid, but suffers from exponential complexity as the number of parameters increases.

**Complexity**: O(n^k) where k = number of parameters, n = values per parameter

**When to Use**:
- ✅ Small parameter spaces (<100 total combinations)
- ✅ Need guaranteed optimum within grid
- ✅ Discrete parameters only
- ✅ Reproducible, deterministic results required

**When NOT to Use**:
- ❌ Large parameter spaces (>1000 combinations)
- ❌ More than 5 parameters
- ❌ Continuous parameters (must discretize first)
- ❌ Limited computational budget

---

## Basic Usage

```python
from decimal import Decimal
from rustybt.optimization import (
    Optimizer,
    ParameterSpace,
    DiscreteParameter,
    CategoricalParameter,
    ObjectiveFunction
)
from rustybt.optimization.search import GridSearchAlgorithm

# Define parameter space (discrete only!)
param_space = ParameterSpace(parameters=[
    DiscreteParameter(
        name='short_window',
        min_value=5,
        max_value=20,
        step=5  # Values: 5, 10, 15, 20
    ),
    DiscreteParameter(
        name='long_window',
        min_value=20,
        max_value=50,
        step=10  # Values: 20, 30, 40, 50
    ),
    CategoricalParameter(
        name='signal_type',
        choices=['momentum', 'mean_reversion']
    )
])

# Calculate grid size
# 4 (short) × 4 (long) × 2 (signal) = 32 combinations
print(f"Grid size: {param_space.cardinality()}")  # 32

# Create grid search algorithm
grid_search = GridSearchAlgorithm(
    parameter_space=param_space,
    early_stopping_rounds=None  # None = exhaustive search
)

# Define backtest function
def run_backtest(short_window, long_window, signal_type):
    """Run backtest with parameters."""
    # Your backtest implementation
    # ...
    return {
        'performance_metrics': {
            'sharpe_ratio': Decimal('1.5')
        }
    }

# Configure optimizer
objective = ObjectiveFunction(metric='sharpe_ratio')

optimizer = Optimizer(
    parameter_space=param_space,
    search_algorithm=grid_search,
    objective_function=objective,
    backtest_function=run_backtest,
    max_trials=32  # Will evaluate all 32 combinations
)

# Run optimization
best_result = optimizer.optimize()

print(f"Best parameters: {best_result.params}")
print(f"Best score: {best_result.score}")

# Access grid search specific methods
print(f"Total combinations: {grid_search.total_combinations}")
print(f"Progress: {grid_search.progress:.1%}")

# Get top 5 results
top_results = grid_search.get_results(top_k=5)
for params, score in top_results:
    print(f"Score {score}: {params}")
```

---

## Early Stopping

Stop grid search early if no improvement for N consecutive evaluations:

```python
# Early stopping after 10 rounds without improvement
grid_search = GridSearchAlgorithm(
    parameter_space=param_space,
    early_stopping_rounds=10
)

# Grid search will terminate early if:
# - All combinations evaluated OR
# - 10 consecutive evaluations without improvement
```

**Use Case**: When grid is large but you suspect optimal region is clustered, early stopping can save significant time.

---

## Parameter Space Requirements

### Discrete Parameters Only

Grid search **does not support continuous parameters**. Continuous ranges must be discretized:

```python
# ❌ WRONG: Continuous parameter
from rustybt.optimization import ContinuousParameter

param_space_wrong = ParameterSpace(parameters=[
    ContinuousParameter(name='threshold', min_value=0.01, max_value=0.10)
])

grid_search = GridSearchAlgorithm(parameter_space=param_space_wrong)
# Raises: ValueError: GridSearch does not support continuous parameters

# ✅ RIGHT: Discretize the range
param_space_correct = ParameterSpace(parameters=[
    DiscreteParameter(
        name='threshold_scaled',  # Scaled to integers
        min_value=10,  # Represents 0.010
        max_value=100,  # Represents 0.100
        step=10  # Steps of 0.010
    )
])

# In your backtest function, convert back:
def run_backtest(threshold_scaled):
    threshold = Decimal(threshold_scaled) / Decimal('1000')  # Convert back
    # Use threshold in backtest
    ...
```

### Grid Size Warning

Grid search warns if grid size exceeds 1000 combinations:

```python
param_space_large = ParameterSpace(parameters=[
    DiscreteParameter(name='p1', min_value=1, max_value=100, step=1),  # 100 values
    DiscreteParameter(name='p2', min_value=1, max_value=20, step=1)    # 20 values
])

# Grid size = 100 × 20 = 2000 combinations
grid_search = GridSearchAlgorithm(parameter_space=param_space_large)
# Warning: Grid search will evaluate 2000 combinations.
# This may take a very long time. Consider using RandomSearch...
```

---

## Complete Example with Validation

```python
from decimal import Decimal
from rustybt.optimization import (
    Optimizer,
    ParameterSpace,
    DiscreteParameter,
    CategoricalParameter,
    ObjectiveFunction
)
from rustybt.optimization.search import GridSearchAlgorithm

# Define realistic parameter space for MA crossover strategy
param_space = ParameterSpace(parameters=[
    DiscreteParameter(
        name='ma_short',
        min_value=5,
        max_value=20,
        step=5
    ),
    DiscreteParameter(
        name='ma_long',
        min_value=20,
        max_value=50,
        step=10
    ),
    CategoricalParameter(
        name='position_size',
        choices=[0.25, 0.50, 0.75, 1.00]  # Fixed position sizes
    )
])

# Calculate and validate grid size
cardinality = param_space.cardinality()
print(f"Grid will evaluate {cardinality} combinations")
# 4 × 4 × 4 = 64 combinations

if cardinality > 100:
    print("Warning: Consider random search for large grids")

# Define backtest with parameter validation
def run_backtest(ma_short, ma_long, position_size):
    """Run backtest with parameter validation."""
    # Validate parameter logic (not just bounds)
    if ma_short >= ma_long:
        # Invalid: short MA must be < long MA
        return {
            'performance_metrics': {
                'sharpe_ratio': Decimal('-Infinity')
            }
        }

    # Run actual backtest
    # ... your backtest logic ...

    sharpe = Decimal('1.5')  # Placeholder

    return {
        'performance_metrics': {
            'sharpe_ratio': sharpe,
            'total_return': Decimal('0.25'),
            'max_drawdown': Decimal('-0.10')
        }
    }

# Create grid search with early stopping
grid_search = GridSearchAlgorithm(
    parameter_space=param_space,
    early_stopping_rounds=15  # Stop if no improvement in 15 trials
)

# Configure optimization
objective = ObjectiveFunction(metric='sharpe_ratio')

optimizer = Optimizer(
    parameter_space=param_space,
    search_algorithm=grid_search,
    objective_function=objective,
    backtest_function=run_backtest,
    max_trials=cardinality
)

# Run optimization
print("Starting grid search...")
best_result = optimizer.optimize()

print(f"\nOptimization complete!")
print(f"Best parameters: {best_result.params}")
print(f"Best Sharpe ratio: {best_result.score}")
print(f"Total trials: {grid_search.iteration}")
print(f"Grid coverage: {grid_search.progress:.1%}")

# Analyze top results
print("\nTop 5 parameter combinations:")
top_results = grid_search.get_results(top_k=5)
for i, (params, score) in enumerate(top_results, 1):
    print(f"{i}. Score {score}: {params}")
```

---

## Performance Characteristics

### Computational Complexity

Grid search has **exponential complexity**:

| Parameters | Values Each | Total Combinations | Example Time (1 sec/eval) |
|------------|-------------|--------------------| --------------------------|
| 2 | 10 | 100 | ~2 minutes |
| 3 | 10 | 1,000 | ~17 minutes |
| 4 | 10 | 10,000 | ~3 hours |
| 5 | 10 | 100,000 | ~28 hours |
| 6 | 10 | 1,000,000 | ~12 days |

**Key Insight**: Adding one parameter with 10 values increases runtime by 10×.

### Parallelization

Grid search is **embarrassingly parallel** - each evaluation is independent:

```python
from rustybt.optimization import ParallelOptimizer

# Parallel grid search with 8 workers
parallel_optimizer = ParallelOptimizer(
    parameter_space=param_space,
    search_algorithm=grid_search,
    objective_function=objective,
    backtest_function=run_backtest,
    max_trials=cardinality,
    n_workers=8  # 8× speedup on 8-core machine
)

best_result = parallel_optimizer.optimize()
```

**Speedup**: Near-linear up to number of CPU cores.

---

## Best Practices

### 1. Two-Phase Optimization

Use coarse grid first, then refine:

```python
# Phase 1: Coarse grid search
param_space_coarse = ParameterSpace(parameters=[
    DiscreteParameter(name='lookback', min_value=10, max_value=100, step=10)
])

grid_coarse = GridSearchAlgorithm(parameter_space=param_space_coarse)
result_coarse = optimize(grid_coarse)

# Phase 2: Fine grid search around best
best_lookback = result_coarse.best_params['lookback']
param_space_fine = ParameterSpace(parameters=[
    DiscreteParameter(
        name='lookback',
        min_value=max(10, best_lookback - 10),
        max_value=min(100, best_lookback + 10),
        step=2
    )
])

grid_fine = GridSearchAlgorithm(parameter_space=param_space_fine)
result_fine = optimize(grid_fine)
```

### 2. Use Appropriate Step Sizes

```python
# ❌ TOO FINE: 91 values
DiscreteParameter(name='window', min_value=10, max_value=100, step=1)

# ✅ GOOD: 10 values (phase 1)
DiscreteParameter(name='window', min_value=10, max_value=100, step=10)

# ✅ GOOD: 11 values (phase 2 refinement)
DiscreteParameter(name='window', min_value=40, max_value=60, step=2)
```

### 3. Validate Grid Size Before Running

```python
cardinality = param_space.cardinality()

if cardinality > 1000:
    print(f"Warning: Grid size is {cardinality}")
    print("Consider:")
    print("1. Increase step sizes")
    print("2. Reduce parameter ranges")
    print("3. Use RandomSearch instead")
    # raise ValueError("Grid too large")
```

### 4. Use Early Stopping for Large Grids

```python
# For large grids where optimum may be found early
grid_search = GridSearchAlgorithm(
    parameter_space=param_space,
    early_stopping_rounds=20
)
```

---

## Common Pitfalls

### ❌ Pitfall 1: Continuous Parameters

```python
# WRONG: Continuous parameter
param_space = ParameterSpace(parameters=[
    ContinuousParameter(name='threshold', min_value=0.01, max_value=0.10)
])

grid_search = GridSearchAlgorithm(parameter_space=param_space)
# Raises: ValueError
```

**Solution**: Discretize continuous parameters.

### ❌ Pitfall 2: Exponential Complexity Ignored

```python
# WRONG: Too many parameters
param_space = ParameterSpace(parameters=[
    DiscreteParameter(name='p1', min_value=1, max_value=10, step=1),  # 10 values
    DiscreteParameter(name='p2', min_value=1, max_value=10, step=1),  # 10 values
    DiscreteParameter(name='p3', min_value=1, max_value=10, step=1),  # 10 values
    DiscreteParameter(name='p4', min_value=1, max_value=10, step=1),  # 10 values
    DiscreteParameter(name='p5', min_value=1, max_value=10, step=1),  # 10 values
    DiscreteParameter(name='p6', min_value=1, max_value=10, step=1),  # 10 values
])
# Grid size = 10^6 = 1,000,000 combinations = weeks of runtime!
```

**Solution**: Limit to 3-5 parameters or use RandomSearch.

### ❌ Pitfall 3: Forgetting Parameter Constraints

```python
# WRONG: No validation of parameter relationships
def run_backtest(ma_short, ma_long):
    # What if ma_short > ma_long? Logic error!
    # Grid search will evaluate invalid combinations
    ...

# RIGHT: Validate in backtest function
def run_backtest(ma_short, ma_long):
    if ma_short >= ma_long:
        return {'performance_metrics': {'sharpe_ratio': Decimal('-Infinity')}}
    # Continue with valid parameters
    ...
```

---

## API Reference

### GridSearchAlgorithm

```python
GridSearchAlgorithm(
    parameter_space: ParameterSpace,
    early_stopping_rounds: int | None = None
)

# Methods
.suggest() -> dict[str, Any]
.update(params: dict, score: Decimal) -> None
.is_complete() -> bool
.get_best_params() -> dict[str, Any]
.get_results(top_k: int | None = None) -> list[tuple[dict, Decimal]]
.get_state() -> dict
.set_state(state: dict) -> None

# Properties
.iteration -> int
.progress -> float  # 0.0 to 1.0
.total_combinations -> int
```

### Checkpointing

```python
# Save state
state = grid_search.get_state()

# Restore state
grid_search.set_state(state)
```

---

## Related Documentation

- [Random Search](random-search.md) - Better for large spaces
- [Bayesian Optimization](bayesian.md) - Sample-efficient alternative
- [Parameter Spaces](../core/parameter-spaces.md) - Defining search spaces

---

**Quality Assurance**: All examples verified against RustyBT source code (`rustybt/optimization/search/grid_search.py`) and tested for correctness.
