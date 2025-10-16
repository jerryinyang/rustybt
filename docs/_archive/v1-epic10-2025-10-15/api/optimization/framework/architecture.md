# Optimization Architecture

Understanding the architecture of RustyBT's optimization framework.

## Overview

The optimization framework is built on a modular architecture that separates concerns between parameter definition, search strategies, objective evaluation, and result analysis.

## Core Components

### 1. Parameter Space

Defines the search domain for optimization.

```python
from rustybt.optimization.parameter_space import (
    ParameterSpace,
    ContinuousParameter,
    DiscreteParameter,
    CategoricalParameter
)

param_space = ParameterSpace(parameters=[
    DiscreteParameter('lookback', min_value=10, max_value=100, step=10),
    ContinuousParameter('threshold', min_value=0.01, max_value=0.10),
    CategoricalParameter('signal', choices=['momentum', 'mean_reversion'])
])
```

**Responsibilities**:
- Define parameter types and bounds
- Validate parameter combinations
- Calculate cardinality (total combinations)
- Support constraints between parameters

### 2. Search Algorithm

Determines how to explore the parameter space.

```python
from rustybt.optimization.search import BayesianOptimizer

optimizer = BayesianOptimizer(
    parameter_space=param_space,
    n_iterations=100
)

while not optimizer.is_complete():
    params = optimizer.suggest()  # Get next parameters
    score = objective_function(params)  # Evaluate
    optimizer.update(params, score)  # Learn
```

**Responsibilities**:
- Suggest next parameter configuration
- Learn from evaluation results
- Manage exploration vs exploitation
- Determine termination criteria

### 3. Objective Function

Evaluates parameter configurations by running backtests.

```python
def objective_function(params):
    """Evaluate strategy with given parameters."""
    result = run_backtest(
        strategy=MyStrategy(**params),
        start_date='2020-01-01',
        end_date='2023-12-31'
    )
    return calculate_sharpe_ratio(result)
```

**Responsibilities**:
- Run backtest with parameters
- Calculate performance metrics
- Return single scalar score (higher = better)
- Handle errors gracefully

### 4. Result Analyzer

Processes and presents optimization results.

```python
result = optimizer.get_results(top_k=10)
for params, score in result:
    print(f"Sharpe {score:.2f}: {params}")

best_params = optimizer.get_best_params()
```

**Responsibilities**:
- Track all evaluations
- Sort by performance
- Provide statistical summaries
- Generate visualizations

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────┐
│                   Optimization Loop                       │
│                                                           │
│  ┌─────────────┐      ┌──────────────┐                  │
│  │  Parameter  │─────>│    Search    │                  │
│  │    Space    │      │  Algorithm   │                  │
│  └─────────────┘      └──────┬───────┘                  │
│                               │                          │
│                               │ suggest()                │
│                               v                          │
│                       ┌───────────────┐                  │
│                       │  Parameters   │                  │
│                       └───────┬───────┘                  │
│                               │                          │
│                               │ evaluate()               │
│                               v                          │
│                       ┌───────────────┐                  │
│                       │   Objective   │                  │
│                       │   Function    │                  │
│                       └───────┬───────┘                  │
│                               │                          │
│                               │ score                    │
│                               v                          │
│                       ┌───────────────┐                  │
│                       │    Update     │                  │
│                       │   Algorithm   │                  │
│                       └───────┬───────┘                  │
│                               │                          │
│                               │ is_complete()?           │
│                               └─> No: loop               │
│                                    Yes: exit             │
│                                                           │
│  ┌──────────────────────────────────────┐               │
│  │         Result Analysis               │               │
│  │  - Best parameters                    │               │
│  │  - Performance distribution           │               │
│  │  - Convergence plots                  │               │
│  └──────────────────────────────────────┘               │
└──────────────────────────────────────────────────────────┘
```

## Design Patterns

### Strategy Pattern

Different search algorithms implement the same `SearchAlgorithm` interface:

```python
class SearchAlgorithm(ABC):
    @abstractmethod
    def suggest(self) -> dict:
        """Suggest next parameters."""
        pass

    @abstractmethod
    def update(self, params: dict, score: Decimal) -> None:
        """Update with evaluation result."""
        pass

    @abstractmethod
    def is_complete(self) -> bool:
        """Check if optimization is complete."""
        pass
```

This allows easy swapping of algorithms:

```python
# Try different algorithms with same setup
for algo_type in ['grid', 'random', 'bayesian']:
    optimizer = Optimizer(
        objective_function=objective_fn,
        parameter_space=param_space,
        algorithm=algo_type
    )
    result = optimizer.optimize()
```

### Builder Pattern

`ParameterSpace` uses builder pattern for complex configurations:

```python
param_space = (
    ParameterSpace()
    .add_discrete('lookback_short', 10, 50, step=5)
    .add_discrete('lookback_long', 50, 200, step=25)
    .add_continuous('threshold', 0.01, 0.10)
    .add_constraint(lambda p: p['lookback_short'] < p['lookback_long'])
)
```

### Observer Pattern

Optimization progress can be monitored via callbacks:

```python
def on_evaluation(params, score, iteration):
    print(f"Iteration {iteration}: Sharpe {score:.2f}")

optimizer = Optimizer(
    objective_function=objective_fn,
    parameter_space=param_space,
    callbacks=[on_evaluation]
)
```

## Data Flow

### Forward Flow: Suggestion to Evaluation

1. **Algorithm suggests parameters** based on current state
2. **Parameter validation** ensures constraints satisfied
3. **Objective function execution** runs backtest
4. **Result extraction** calculates performance metric
5. **Score returned** to algorithm

### Backward Flow: Learning

1. **Algorithm receives score** for evaluated parameters
2. **Internal model update** (varies by algorithm)
3. **Exploration/exploitation balance** adjusted
4. **Next suggestion prepared** based on learning

## Extensibility Points

### Custom Search Algorithms

Implement `SearchAlgorithm` interface:

```python
from rustybt.optimization.base import SearchAlgorithm

class MyCustomAlgorithm(SearchAlgorithm):
    def __init__(self, parameter_space: ParameterSpace):
        self.param_space = parameter_space
        self.history = []

    def suggest(self) -> dict:
        # Your suggestion logic
        return suggested_params

    def update(self, params: dict, score: Decimal) -> None:
        # Your learning logic
        self.history.append((params, score))

    def is_complete(self) -> bool:
        # Your termination logic
        return len(self.history) >= 100
```

### Custom Objective Functions

Any callable that maps parameters to score:

```python
def multi_metric_objective(params):
    """Combine multiple metrics."""
    result = run_backtest(params)

    sharpe = calculate_sharpe(result)
    sortino = calculate_sortino(result)
    max_dd = calculate_max_drawdown(result)

    # Weighted combination
    score = 0.6 * sharpe + 0.3 * sortino - 0.1 * abs(max_dd)
    return Decimal(str(score))
```

### Custom Parameter Types

Extend base `Parameter` class:

```python
from rustybt.optimization.parameter_space import ContinuousParameter

class LogScaleParameter(Parameter):
    """Parameter sampled on log scale."""

    def sample(self) -> float:
        import numpy as np
        return np.exp(np.random.uniform(
            np.log(self.min_value),
            np.log(self.max_value)
        ))
```

## Thread Safety

⚠️ **Warning**: Sequential algorithms (Bayesian) are NOT thread-safe.

**Safe for parallelization**:
- Grid Search
- Random Search
- Genetic Algorithm (population-based)

**Not safe for parallelization**:
- Bayesian Optimization (requires sequential updates)

Use `ParallelOptimizer` for safe parallel execution:

```python
from rustybt.optimization import ParallelOptimizer

parallel = ParallelOptimizer(
    objective_function=objective_fn,
    parameter_space=param_space,
    algorithm='random',  # Only grid/random/genetic supported
    n_jobs=4
)
```

## Error Handling

### Graceful Degradation

If objective function fails, optimization continues:

```python
def robust_objective(params):
    try:
        result = run_backtest(params)
        return calculate_sharpe(result)
    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        return Decimal('-Infinity')  # Mark as failed
```

### Validation Errors

Parameter validation errors are raised immediately:

```python
try:
    param_space.validate_params({'lookback': 5})  # Below minimum
except ValueError as e:
    print(f"Invalid parameters: {e}")
```

## Performance Optimization

### Caching Results

Avoid re-evaluating identical parameters:

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def cached_objective(param_tuple):
    params = dict(param_tuple)
    return objective_function(params)

# Convert dict to hashable tuple for caching
def objective_wrapper(params):
    param_tuple = tuple(sorted(params.items()))
    return cached_objective(param_tuple)
```

### Early Stopping

Terminate unpromising evaluations early:

```python
def early_stopping_objective(params):
    result = run_backtest(params)

    # Check intermediate performance
    if result.sharpe_6m < 0:  # Poor 6-month performance
        return Decimal('-Infinity')  # Skip remaining evaluation

    return calculate_sharpe(result)
```

## Testing Strategies

### Unit Testing Components

Test each component independently:

```python
def test_parameter_space():
    space = ParameterSpace(parameters=[
        DiscreteParameter('x', 1, 10, step=1)
    ])
    assert space.cardinality() == 10

def test_grid_search():
    algo = GridSearchAlgorithm(param_space)
    params = algo.suggest()
    assert params in param_space.valid_values()
```

### Integration Testing

Test full optimization pipeline:

```python
def test_full_optimization():
    def simple_objective(params):
        # Known optimal at x=5
        return Decimal(str(-abs(params['x'] - 5)))

    optimizer = Optimizer(
        objective_function=simple_objective,
        parameter_space=param_space,
        algorithm='grid'
    )

    result = optimizer.optimize()
    assert result.best_params['x'] == 5
```

## See Also

- [Parameter Spaces](parameter-spaces.md)
- [Objective Functions](objective-functions.md)
- [Search Algorithms](../algorithms/grid-search.md)
- [Main Optimization API](../../optimization-api.md)
