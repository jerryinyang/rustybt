# Optimization API Reference

**Last Updated**: 2024-10-11

## Overview

The Optimization framework provides systematic parameter tuning for trading strategies. It includes multiple search algorithms (grid, random, Bayesian, genetic), walk-forward testing, parallel optimization, and robustness analysis.

---

## Parameter Space

### ParameterSpace

Defines the search space for optimization.

```python
from rustybt.optimization.parameter_space import (
    ParameterSpace,
    ContinuousParameter,
    DiscreteParameter,
    CategoricalParameter
)

param_space = ParameterSpace(
    parameters=[
        DiscreteParameter(name='lookback', min_value=10, max_value=100, step=10),
        ContinuousParameter(name='threshold', min_value=0.01, max_value=0.10),
        CategoricalParameter(name='signal_type', choices=['momentum', 'mean_reversion'])
    ]
)
```

#### Constructor

```python
ParameterSpace(
    parameters: list[ContinuousParameter | DiscreteParameter | CategoricalParameter]
)
```

#### Methods

##### `get_parameter(name: str) -> Parameter`

Get parameter definition by name.

```python
param = param_space.get_parameter('lookback')
print(f"Min: {param.min_value}, Max: {param.max_value}")
```

##### `validate_params(params: dict) -> bool`

Validate parameter values against constraints.

```python
params = {'lookback': 50, 'threshold': 0.05, 'signal_type': 'momentum'}
param_space.validate_params(params)  # Returns True or raises ValueError
```

##### `cardinality() -> int`

Calculate total number of parameter combinations.

```python
total = param_space.cardinality()
print(f"Total combinations: {total}")
# Returns -1 if infinite (continuous parameters)
```

---

### ContinuousParameter

Continuous parameter (float/Decimal) with bounds.

```python
ContinuousParameter(
    name: str,
    min_value: float | Decimal,
    max_value: float | Decimal,
    prior: Literal['uniform', 'log-uniform', 'normal'] = 'uniform'
)
```

**Parameters**:
- `name`: Parameter name
- `min_value`: Minimum value (inclusive)
- `max_value`: Maximum value (inclusive)
- `prior`: Prior distribution for Bayesian optimization

**Example**:
```python
threshold = ContinuousParameter(
    name='threshold',
    min_value=0.01,
    max_value=0.10,
    prior='uniform'
)
```

---

### DiscreteParameter

Integer parameter with bounds and step size.

```python
DiscreteParameter(
    name: str,
    min_value: int,
    max_value: int,
    step: int = 1
)
```

**Parameters**:
- `name`: Parameter name
- `min_value`: Minimum value (inclusive)
- `max_value`: Maximum value (inclusive)
- `step`: Step size between values

**Example**:
```python
lookback = DiscreteParameter(
    name='lookback',
    min_value=10,
    max_value=100,
    step=10
)
# Values: [10, 20, 30, ..., 100]
```

---

### CategoricalParameter

Categorical parameter with fixed choices.

```python
CategoricalParameter(
    name: str,
    choices: list[Any]
)
```

**Parameters**:
- `name`: Parameter name
- `choices`: List of valid choices (must have >= 2 unique values)

**Example**:
```python
signal_type = CategoricalParameter(
    name='signal_type',
    choices=['momentum', 'mean_reversion', 'breakout']
)
```

---

## Search Algorithms

### SearchAlgorithm (Abstract Base Class)

All search algorithms implement this interface.

```python
from rustybt.optimization.base import SearchAlgorithm
```

#### Methods

##### `suggest() -> dict[str, Any]`

Suggest next parameter configuration to evaluate.

```python
params = optimizer.suggest()
# Returns: {'lookback': 50, 'threshold': 0.05}
```

**Returns**: Dictionary mapping parameter names to values

**Raises**:
- `ValueError`: If optimization is complete or not initialized

##### `update(params: dict[str, Any], score: Decimal) -> None`

Update algorithm with evaluation result.

```python
optimizer.update(params, score=Decimal("1.5"))  # Sharpe ratio
```

**Parameters**:
- `params`: Parameters that were evaluated
- `score`: Objective function value (higher is better)

##### `is_complete() -> bool`

Check if optimization should terminate.

```python
while not optimizer.is_complete():
    params = optimizer.suggest()
    score = evaluate(params)
    optimizer.update(params, score)
```

**Returns**: `True` if complete, `False` otherwise

##### `get_best_params() -> dict[str, Any]`

Get best parameters found so far.

```python
best_params = optimizer.get_best_params()
print(f"Best: {best_params}")
```

##### `get_results(top_k: int = None) -> list[tuple[dict, Decimal]]`

Get top-k results.

```python
top_5 = optimizer.get_results(top_k=5)
for params, score in top_5:
    print(f"Score: {score}, Params: {params}")
```

**Parameters**:
- `top_k`: Number of top results to return (None = all results)

**Returns**: List of (params, score) tuples sorted by score (descending)

---

### GridSearchAlgorithm

Exhaustive grid search over all parameter combinations.

```python
from rustybt.optimization.search import GridSearchAlgorithm

grid = GridSearchAlgorithm(
    parameter_space=param_space,
    early_stopping_rounds=None
)
```

#### Constructor

```python
GridSearchAlgorithm(
    parameter_space: ParameterSpace,
    early_stopping_rounds: Optional[int] = None
)
```

**Parameters**:
- `parameter_space`: Parameter space to search
- `early_stopping_rounds`: Stop if no improvement for N consecutive evaluations

#### Properties

##### `total_combinations: int`

Total number of combinations to evaluate.

```python
print(f"Grid size: {grid.total_combinations}")
```

##### `progress: float`

Progress as fraction (0.0 to 1.0).

```python
print(f"Progress: {grid.progress * 100:.1f}%")
```

#### Example

```python
from rustybt.optimization.search import GridSearchAlgorithm
from rustybt.optimization.parameter_space import DiscreteParameter, ParameterSpace

param_space = ParameterSpace(parameters=[
    DiscreteParameter(name='lookback_short', min_value=10, max_value=30, step=5),
    DiscreteParameter(name='lookback_long', min_value=50, max_value=150, step=25)
])

grid = GridSearchAlgorithm(parameter_space=param_space)

while not grid.is_complete():
    params = grid.suggest()
    score = run_backtest(params)
    grid.update(params, score)

best_params = grid.get_best_params()
```

**Use Case**: Small parameter spaces (<1000 combinations), need exhaustive search.

---

### RandomSearchAlgorithm

Random sampling from parameter space.

```python
from rustybt.optimization.search import RandomSearchAlgorithm

random_search = RandomSearchAlgorithm(
    parameter_space=param_space,
    n_iterations=100,
    random_seed=42
)
```

#### Constructor

```python
RandomSearchAlgorithm(
    parameter_space: ParameterSpace,
    n_iterations: int,
    random_seed: Optional[int] = None,
    early_stopping_rounds: Optional[int] = None
)
```

**Parameters**:
- `parameter_space`: Parameter space to search
- `n_iterations`: Number of random samples to evaluate
- `random_seed`: Random seed for reproducibility
- `early_stopping_rounds`: Stop if no improvement for N evaluations

#### Example

```python
random_search = RandomSearchAlgorithm(
    parameter_space=param_space,
    n_iterations=100,
    random_seed=42
)

while not random_search.is_complete():
    params = random_search.suggest()
    score = run_backtest(params)
    random_search.update(params, score)

best_params = random_search.get_best_params()
```

**Use Case**: Large parameter spaces, faster than grid search, exploration-focused.

---

### BayesianOptimizer

Bayesian optimization using Gaussian processes.

```python
from rustybt.optimization.search import BayesianOptimizer

bayes = BayesianOptimizer(
    parameter_space=param_space,
    n_initial_points=10,
    n_iterations=50,
    acquisition_function='EI',
    random_seed=42
)
```

#### Constructor

```python
BayesianOptimizer(
    parameter_space: ParameterSpace,
    n_initial_points: int = 10,
    n_iterations: int = 100,
    acquisition_function: Literal['EI', 'PI', 'LCB'] = 'EI',
    kappa: float = 2.576,
    xi: float = 0.01,
    random_seed: Optional[int] = None
)
```

**Parameters**:
- `parameter_space`: Parameter space to search
- `n_initial_points`: Number of random points before GP modeling
- `n_iterations`: Total iterations to run
- `acquisition_function`: Acquisition function (`'EI'` = Expected Improvement, `'PI'` = Probability of Improvement, `'LCB'` = Lower Confidence Bound)
- `kappa`: Exploration-exploitation tradeoff for LCB
- `xi`: Exploration constant for EI/PI
- `random_seed`: Random seed for reproducibility

#### Example

```python
bayes = BayesianOptimizer(
    parameter_space=param_space,
    n_initial_points=10,
    n_iterations=50,
    acquisition_function='EI'
)

while not bayes.is_complete():
    params = bayes.suggest()
    score = run_backtest(params)
    bayes.update(params, score)

best_params = bayes.get_best_params()
```

**Use Case**: Expensive objective functions (long backtests), smooth parameter spaces, exploitation-focused.

**Dependencies**: Requires `scikit-optimize` package.

---

### GeneticAlgorithm

Genetic algorithm optimization using evolutionary strategies.

```python
from rustybt.optimization.search import GeneticAlgorithm

genetic = GeneticAlgorithm(
    parameter_space=param_space,
    population_size=50,
    n_generations=100,
    mutation_rate=0.1,
    crossover_rate=0.7
)
```

#### Constructor

```python
GeneticAlgorithm(
    parameter_space: ParameterSpace,
    population_size: int = 50,
    n_generations: int = 100,
    mutation_rate: float = 0.1,
    crossover_rate: float = 0.7,
    tournament_size: int = 3,
    elitism_count: int = 2,
    random_seed: Optional[int] = None
)
```

**Parameters**:
- `parameter_space`: Parameter space to search
- `population_size`: Number of individuals per generation
- `n_generations`: Number of generations to evolve
- `mutation_rate`: Probability of mutation (0.0-1.0)
- `crossover_rate`: Probability of crossover (0.0-1.0)
- `tournament_size`: Tournament selection size
- `elitism_count`: Number of top individuals preserved each generation
- `random_seed`: Random seed for reproducibility

#### Example

```python
genetic = GeneticAlgorithm(
    parameter_space=param_space,
    population_size=50,
    n_generations=100
)

while not genetic.is_complete():
    params = genetic.suggest()
    score = run_backtest(params)
    genetic.update(params, score)

best_params = genetic.get_best_params()
```

**Use Case**: Non-smooth objective functions, discrete/categorical parameters, population-based search.

**Dependencies**: Requires `deap` package.

---

## High-Level Optimizers

### Optimizer

High-level optimizer that wraps search algorithms.

```python
from rustybt.optimization import Optimizer

optimizer = Optimizer(
    objective_function=run_backtest,
    parameter_space=param_space,
    algorithm='bayesian',
    n_iterations=50
)

results = optimizer.optimize()
```

#### Constructor

```python
Optimizer(
    objective_function: Callable,
    parameter_space: ParameterSpace,
    algorithm: Literal['grid', 'random', 'bayesian', 'genetic'],
    n_iterations: int = 100,
    **algorithm_kwargs
)
```

**Parameters**:
- `objective_function`: Function that takes params dict and returns score
- `parameter_space`: Parameter space to search
- `algorithm`: Search algorithm to use
- `n_iterations`: Number of iterations
- `**algorithm_kwargs`: Algorithm-specific parameters

#### Methods

##### `optimize() -> OptimizationResult`

Run optimization.

```python
result = optimizer.optimize()
print(f"Best params: {result.best_params}")
print(f"Best score: {result.best_score}")
```

**Returns**: `OptimizationResult` with best parameters and full results

---

### ParallelOptimizer

Parallel optimization using multiple processes.

```python
from rustybt.optimization import ParallelOptimizer

parallel = ParallelOptimizer(
    objective_function=run_backtest,
    parameter_space=param_space,
    algorithm='random',
    n_iterations=100,
    n_jobs=4
)

results = parallel.optimize()
```

#### Constructor

```python
ParallelOptimizer(
    objective_function: Callable,
    parameter_space: ParameterSpace,
    algorithm: Literal['grid', 'random', 'genetic'],
    n_iterations: int = 100,
    n_jobs: int = -1,
    **algorithm_kwargs
)
```

**Parameters**:
- `objective_function`: Function to optimize (must be picklable)
- `parameter_space`: Parameter space
- `algorithm`: Search algorithm (`'bayesian'` not supported in parallel mode)
- `n_iterations`: Total evaluations
- `n_jobs`: Number of parallel workers (-1 = all CPUs)

#### Example

```python
def run_backtest(params):
    # Backtest logic
    return sharpe_ratio

parallel = ParallelOptimizer(
    objective_function=run_backtest,
    parameter_space=param_space,
    algorithm='random',
    n_iterations=1000,
    n_jobs=8
)

result = parallel.optimize()
print(f"Best params: {result.best_params}")
```

**Use Case**: Expensive backtests, embarrassingly parallel workloads.

**Note**: Objective function must be picklable (no lambdas, module-level function).

---

### WalkForwardOptimizer

Walk-forward optimization for out-of-sample validation.

```python
from rustybt.optimization import WalkForwardOptimizer

wf_optimizer = WalkForwardOptimizer(
    objective_function=run_backtest,
    parameter_space=param_space,
    train_period_days=252,
    test_period_days=63,
    reoptimize_frequency_days=63,
    start_date='2020-01-01',
    end_date='2023-12-31'
)

results = wf_optimizer.optimize()
```

#### Constructor

```python
WalkForwardOptimizer(
    objective_function: Callable,
    parameter_space: ParameterSpace,
    train_period_days: int,
    test_period_days: int,
    reoptimize_frequency_days: int,
    start_date: str | pd.Timestamp,
    end_date: str | pd.Timestamp,
    algorithm: str = 'bayesian',
    n_iterations_per_window: int = 50,
    anchored: bool = False
)
```

**Parameters**:
- `objective_function`: Backtest function with `(params, start, end)` signature
- `parameter_space`: Parameter space
- `train_period_days`: Training window size
- `test_period_days`: Testing window size
- `reoptimize_frequency_days`: How often to reoptimize
- `start_date`: Overall start date
- `end_date`: Overall end date
- `algorithm`: Optimization algorithm for each window
- `n_iterations_per_window`: Iterations per training window
- `anchored`: If True, training window grows (anchored); if False, rolling window

#### Methods

##### `optimize() -> WalkForwardResult`

Run walk-forward optimization.

```python
result = wf_optimizer.optimize()
print(f"In-sample Sharpe: {result.in_sample_metrics['sharpe']}")
print(f"Out-of-sample Sharpe: {result.out_of_sample_metrics['sharpe']}")
```

**Returns**: `WalkForwardResult` with in-sample and out-of-sample metrics

#### Example

```python
def run_backtest(params, start, end):
    # Run backtest from start to end with params
    return sharpe_ratio

wf = WalkForwardOptimizer(
    objective_function=run_backtest,
    parameter_space=param_space,
    train_period_days=252,  # 1 year training
    test_period_days=63,    # 3 months testing
    reoptimize_frequency_days=63,  # Reoptimize every 3 months
    start_date='2020-01-01',
    end_date='2023-12-31',
    algorithm='bayesian'
)

result = wf.optimize()
```

**Use Case**: Robust optimization, avoid overfitting, simulate realistic trading.

---

## Robustness Testing

### SensitivityAnalyzer

Analyze parameter sensitivity.

```python
from rustybt.optimization import SensitivityAnalyzer

analyzer = SensitivityAnalyzer(
    objective_function=run_backtest,
    base_params={'lookback': 50, 'threshold': 0.05}
)

sensitivity = analyzer.analyze('lookback', values=[30, 40, 50, 60, 70])
```

#### Methods

##### `analyze(param_name: str, values: list) -> pd.DataFrame`

Analyze sensitivity of one parameter.

```python
results = analyzer.analyze('lookback', values=range(10, 101, 10))
print(results[['value', 'score']])
```

**Returns**: DataFrame with columns: `['value', 'score']`

##### `analyze_all(perturbation_pct: float = 0.2, n_points: int = 5) -> dict`

Analyze sensitivity of all parameters.

```python
all_sensitivity = analyzer.analyze_all(perturbation_pct=0.2, n_points=5)
for param, results in all_sensitivity.items():
    print(f"{param}: sensitivity = {results['sensitivity_score']}")
```

---

### MonteCarloSimulator

Monte Carlo noise infusion for robustness testing.

```python
from rustybt.optimization import MonteCarloSimulator

mc_simulator = MonteCarloSimulator(
    objective_function=run_backtest,
    base_params={'lookback': 50},
    n_simulations=1000
)

results = mc_simulator.run(noise_std=0.1)
```

#### Methods

##### `run(noise_std: float = 0.1) -> MonteCarloResult`

Run Monte Carlo simulations.

```python
result = mc_simulator.run(noise_std=0.1)
print(f"Mean score: {result.mean_score}")
print(f"Std score: {result.std_score}")
print(f"95% CI: [{result.ci_lower}, {result.ci_upper}]")
```

**Returns**: `MonteCarloResult` with statistics

---

## Complete Example

```python
from decimal import Decimal
from rustybt.optimization import Optimizer
from rustybt.optimization.parameter_space import (
    ParameterSpace,
    DiscreteParameter,
    ContinuousParameter,
    CategoricalParameter
)

# Define parameter space
param_space = ParameterSpace(parameters=[
    DiscreteParameter(name='lookback_short', min_value=10, max_value=50, step=5),
    DiscreteParameter(name='lookback_long', min_value=50, max_value=200, step=25),
    ContinuousParameter(name='threshold', min_value=0.01, max_value=0.10),
    CategoricalParameter(name='signal_type', choices=['momentum', 'mean_reversion'])
])

# Define objective function
def run_backtest(params):
    # Your backtest logic here
    # ...
    sharpe_ratio = calculate_sharpe(...)
    return Decimal(str(sharpe_ratio))

# Create optimizer
optimizer = Optimizer(
    objective_function=run_backtest,
    parameter_space=param_space,
    algorithm='bayesian',
    n_iterations=100
)

# Run optimization
result = optimizer.optimize()

# Get results
print(f"Best parameters: {result.best_params}")
print(f"Best Sharpe: {result.best_score}")

# Get top 5 results
for params, score in result.get_top_k(5):
    print(f"Sharpe {score}: {params}")
```

---

## Algorithm Selection Guide

| Algorithm | Use When | Pros | Cons |
|-----------|----------|------|------|
| **Grid Search** | <1000 combinations, need exhaustive search | Complete coverage, deterministic | Slow, curse of dimensionality |
| **Random Search** | Large spaces, exploration needed | Fast, good for high dimensions | No learning, less efficient |
| **Bayesian** | Expensive backtests, smooth parameters | Sample-efficient, exploitation-focused | Requires continuous parameters |
| **Genetic** | Non-smooth objectives, discrete/categorical | Robust, handles discontinuities | Requires population tuning |

**General Guidelines**:
- Start with Random Search for exploration
- Use Bayesian for refinement
- Use Grid Search for final verification in small region
- Always use Walk-Forward for production validation

---

## See Also

- <!-- Grid Search Example (Coming soon) -->
- <!-- Bayesian Optimization Example (Coming soon) -->
- <!-- Walk-Forward Example (Coming soon) -->
- <!-- Parallel Optimization Example (Coming soon) -->
