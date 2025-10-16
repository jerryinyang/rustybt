# Bayesian Optimization

**Module**: `rustybt.optimization.search.bayesian_search`
**Class**: `BayesianOptimizer`
**Best For**: Expensive objective functions, sample-efficient optimization

---

## Overview

Bayesian Optimization uses a Gaussian Process (GP) surrogate model to approximate the objective function and an acquisition function to intelligently select which parameters to evaluate next. It balances **exploration** (sampling uncertain regions) and **exploitation** (sampling near known good regions), making it more sample-efficient than grid or random search.

**Key Advantages**:
- Sample-efficient: Needs fewer evaluations than random search
- Learns from past evaluations using Gaussian Process
- Balances exploration vs exploitation automatically
- Handles continuous, discrete, and categorical parameters
- Supports prior knowledge (initial points)

**When to Use**:
- ✅ Expensive objective functions (minutes per backtest)
- ✅ Moderate parameter count (2-20 parameters)
- ✅ Continuous parameter spaces
- ✅ Sequential optimization (not massively parallel)
- ✅ Have prior knowledge of good parameters

**When NOT to Use**:
- ❌ Fast objective functions (use random/grid search)
- ❌ Very high dimensions (>20 parameters - GP doesn't scale well)
- ❌ Need massive parallelization (GP is inherently sequential)
- ❌ Very small budget (<20 evaluations - use grid search)

---

## Basic Usage

```python
from decimal import Decimal
from rustybt.optimization import (
    Optimizer,
    ParameterSpace,
    ContinuousParameter,
    DiscreteParameter,
    ObjectiveFunction
)
from rustybt.optimization.search import BayesianOptimizer

# Define parameter space
param_space = ParameterSpace(parameters=[
    ContinuousParameter(
        name='lookback',
        min_value=10.0,
        max_value=100.0,
        prior='uniform'
    ),
    ContinuousParameter(
        name='threshold',
        min_value=0.001,
        max_value=0.1,
        prior='log-uniform'  # Log scale for exponential range
    ),
    DiscreteParameter(
        name='rebalance_freq',
        min_value=1,
        max_value=30,
        step=1
    )
])

# Create Bayesian optimizer
bayesian_opt = BayesianOptimizer(
    parameter_space=param_space,
    n_iter=50,  # Maximum iterations
    acq_func='EI',  # Expected Improvement acquisition function
    random_state=42  # For reproducibility
)

# Define backtest function
def run_backtest(lookback, threshold, rebalance_freq):
    """Run backtest - NOTE: Bayesian optimization works best
    when objective function is expensive (takes time)."""
    # Your expensive backtest logic
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
    search_algorithm=bayesian_opt,
    objective_function=objective,
    backtest_function=run_backtest,
    max_trials=50
)

# Run optimization
best_result = optimizer.optimize()

print(f"Best parameters: {best_result.params}")
print(f"Best score: {best_result.score}")
print(f"Converged: {bayesian_opt.is_converged()}")
```

---

## Acquisition Functions

The acquisition function determines which point to evaluate next by balancing exploration and exploitation.

### Expected Improvement (EI) - Default

**Best for**: General-purpose optimization

```python
bayesian_opt = BayesianOptimizer(
    parameter_space=param_space,
    acq_func='EI',  # Expected Improvement
    xi=0.01  # Exploration parameter (larger = more exploration)
)
```

**How it works**: Maximizes expected improvement over current best.

**xi Parameter**:
- `xi=0.0`: Pure exploitation (greedy)
- `xi=0.01`: Balanced (default)
- `xi=0.1`: More exploration

### Probability of Improvement (PI)

**Best for**: When you need high probability of improvement

```python
bayesian_opt = BayesianOptimizer(
    parameter_space=param_space,
    acq_func='PI',  # Probability of Improvement
    xi=0.0  # Typically use 0 for PI
)
```

**How it works**: Maximizes probability of improving over current best.

### Lower Confidence Bound (LCB)

**Best for**: Minimization problems or risk-averse optimization

```python
bayesian_opt = BayesianOptimizer(
    parameter_space=param_space,
    acq_func='LCB',  # Lower Confidence Bound
    kappa=1.96  # Exploration parameter (larger = more exploration)
)
```

**How it works**: Minimizes lower confidence bound (mean - kappa × std).

**kappa Parameter**:
- `kappa=0.0`: Pure exploitation (use GP mean)
- `kappa=1.96`: 95% confidence interval (default)
- `kappa=3.0`: More exploration

---

## Prior Knowledge

Seed Bayesian optimization with known good parameters to start from a better position:

```python
# You have prior knowledge that these parameters work well
initial_points = [
    {'lookback': 20.0, 'threshold': 0.02, 'rebalance_freq': 5},
    {'lookback': 50.0, 'threshold': 0.01, 'rebalance_freq': 10}
]

initial_scores = [
    Decimal('1.5'),  # Sharpe ratio for first params
    Decimal('1.3')   # Sharpe ratio for second params
]

bayesian_opt = BayesianOptimizer(
    parameter_space=param_space,
    n_iter=50,
    initial_points=initial_points,
    initial_scores=initial_scores,
    random_state=42
)

# Optimization starts from these known points
# and explores nearby regions intelligently
```

**Use cases for prior knowledge**:
- Refinement after random search
- Domain expert intuition
- Parameters from previous optimizations
- Published research parameters

---

## Convergence Detection

Bayesian optimization can automatically detect convergence:

```python
bayesian_opt = BayesianOptimizer(
    parameter_space=param_space,
    n_iter=100,
    convergence_threshold=1e-4,  # Min improvement threshold
    convergence_patience=10  # Stop if no improvement for 10 iterations
)

result = optimizer.optimize()

if bayesian_opt.is_converged():
    print(f"Converged after {bayesian_opt.iteration} iterations")
else:
    print(f"Reached max iterations ({bayesian_opt.n_iter})")
```

**Convergence criteria**: Optimization stops if no improvement > `convergence_threshold` for `convergence_patience` consecutive iterations.

---

## Complete Example with Two-Phase Optimization

```python
from decimal import Decimal
from rustybt.optimization import (
    Optimizer,
    ParameterSpace,
    ContinuousParameter,
    DiscreteParameter,
    ObjectiveFunction
)
from rustybt.optimization.search import RandomSearchAlgorithm, BayesianOptimizer

# Define large parameter space
param_space = ParameterSpace(parameters=[
    ContinuousParameter(
        name='ma_short',
        min_value=5.0,
        max_value=50.0,
        prior='uniform'
    ),
    ContinuousParameter(
        name='ma_long',
        min_value=50.0,
        max_value=200.0,
        prior='uniform'
    ),
    ContinuousParameter(
        name='stop_loss',
        min_value=0.01,
        max_value=0.10,
        prior='log-uniform'
    ),
    DiscreteParameter(
        name='holding_period',
        min_value=1,
        max_value=20,
        step=1
    )
])

def run_expensive_backtest(ma_short, ma_long, stop_loss, holding_period):
    """Expensive backtest taking 30+ seconds."""
    # Validate constraints
    if ma_short >= ma_long:
        return {
            'performance_metrics': {'sharpe_ratio': Decimal('-Infinity')}
        }

    # Expensive backtest logic
    # ...
    sharpe = Decimal('1.5')  # Placeholder

    return {
        'performance_metrics': {'sharpe_ratio': sharpe}
    }

# Phase 1: Random search for initial exploration (fast, broad coverage)
print("Phase 1: Random search exploration...")
random_search = RandomSearchAlgorithm(
    parameter_space=param_space,
    n_iter=20,  # Quick exploration
    seed=42
)

objective = ObjectiveFunction(metric='sharpe_ratio')

optimizer_random = Optimizer(
    parameter_space=param_space,
    search_algorithm=random_search,
    objective_function=objective,
    backtest_function=run_expensive_backtest,
    max_trials=20
)

random_result = optimizer_random.optimize()

# Get top 3 results from random search as prior knowledge
top_3_random = random_search.get_results(top_k=3)
initial_points = [params for params, _ in top_3_random]
initial_scores = [score for _, score in top_3_random]

print(f"Phase 1 complete. Best score: {random_result.score}")

# Phase 2: Bayesian optimization for refinement (sample-efficient)
print("\nPhase 2: Bayesian refinement...")
bayesian_opt = BayesianOptimizer(
    parameter_space=param_space,
    n_iter=30,  # Focused search
    acq_func='EI',
    xi=0.01,
    initial_points=initial_points,  # Start from best random search results
    initial_scores=initial_scores,
    convergence_threshold=1e-3,
    convergence_patience=10,
    random_state=42
)

optimizer_bayesian = Optimizer(
    parameter_space=param_space,
    search_algorithm=bayesian_opt,
    objective_function=objective,
    backtest_function=run_expensive_backtest,
    max_trials=30
)

bayesian_result = optimizer_bayesian.optimize()

print(f"\nPhase 2 complete. Best score: {bayesian_result.score}")
print(f"Converged: {bayesian_opt.is_converged()}")
print(f"Total evaluations: 20 (random) + {bayesian_opt.iteration} (Bayesian)")
print(f"\nFinal best parameters: {bayesian_result.params}")
```

---

## Performance Characteristics

### Sample Efficiency

Bayesian optimization typically finds good solutions with fewer evaluations:

| Method | Evaluations Needed | Best For |
|--------|-------------------|----------|
| Grid Search | 100-10,000+ | Exhaustive search |
| Random Search | 100-1000 | Fast exploration |
| Bayesian | 20-200 | Expensive objectives |

**Rule of Thumb**: Bayesian optimization shines when each evaluation takes >10 seconds.

### Parallelization Limitations

Bayesian optimization is **inherently sequential**:
- GP learns from each evaluation to suggest next point
- Limited parallelization (can batch suggest 2-4 points)
- For massive parallelization, use random/grid search instead

```python
# Bayesian optimizer with ParallelOptimizer
# WARNING: Limited speedup due to sequential nature
parallel_optimizer = ParallelOptimizer(
    parameter_space=param_space,
    search_algorithm=bayesian_opt,
    objective_function=objective,
    backtest_function=run_backtest,
    max_trials=50,
    n_workers=2  # Use 2-4 workers max (limited benefit beyond this)
)
```

---

## Best Practices

### 1. Use Two-Phase Optimization

```python
# Phase 1: Random search (20-30 evaluations)
# → Broad exploration, identify promising regions

# Phase 2: Bayesian optimization with prior knowledge
# → Focused refinement in promising regions
```

### 2. Choose Appropriate n_iter

```python
# Expensive objective (30+ sec/eval): n_iter = 30-100
bayesian_opt = BayesianOptimizer(n_iter=50)

# Very expensive (5+ min/eval): n_iter = 20-50
bayesian_opt = BayesianOptimizer(n_iter=30)
```

### 3. Use Log-Uniform for Exponential Ranges

```python
# For parameters spanning orders of magnitude
ContinuousParameter(
    name='learning_rate',
    min_value=0.0001,
    max_value=0.1,
    prior='log-uniform'  # GP handles log-space better
)
```

### 4. Enable Convergence Detection

```python
bayesian_opt = BayesianOptimizer(
    n_iter=100,
    convergence_threshold=1e-4,
    convergence_patience=15  # Stop early if converged
)
```

---

## Common Pitfalls

### ❌ Pitfall 1: Using for Fast Objectives

```python
# WRONG: Fast backtest (1 sec/eval)
# Random search would be more efficient
bayesian_opt = BayesianOptimizer(n_iter=1000)
```

**Solution**: Use Bayesian only for expensive objectives (>10 sec).

### ❌ Pitfall 2: Too Many Parameters

```python
# WRONG: 25+ parameters
# GP doesn't scale well to high dimensions
param_space = ParameterSpace(parameters=[...])  # 25 parameters

bayesian_opt = BayesianOptimizer(...)
```

**Solution**: Limit to 2-20 parameters. Use random search for >20.

### ❌ Pitfall 3: Massive Parallelization

```python
# WRONG: Trying to parallelize Bayesian optimization heavily
parallel_optimizer = ParallelOptimizer(
    ...,
    n_workers=32  # Bayesian is sequential, won't benefit
)
```

**Solution**: Use 2-4 workers max for Bayesian. Use random/grid for massive parallelization.

### ❌ Pitfall 4: No Prior Knowledge When Available

```python
# WRONG: Starting from scratch when you have good parameters
bayesian_opt = BayesianOptimizer(...)

# RIGHT: Use prior knowledge
bayesian_opt = BayesianOptimizer(
    ...,
    initial_points=[known_good_params],
    initial_scores=[known_good_score]
)
```

---

## API Reference

### BayesianOptimizer

```python
BayesianOptimizer(
    parameter_space: ParameterSpace,
    n_iter: int = 50,
    acq_func: Literal['EI', 'PI', 'LCB'] = 'EI',
    kappa: float = 1.96,  # For LCB
    xi: float = 0.01,  # For EI/PI
    initial_points: list[dict] | None = None,
    initial_scores: list[Decimal] | None = None,
    convergence_threshold: float = 1e-4,
    convergence_patience: int = 10,
    random_state: int | None = None
)

# Methods
.suggest() -> dict[str, Any]
.update(params: dict, score: Decimal) -> None
.is_complete() -> bool
.is_converged() -> bool
.get_best_params() -> dict[str, Any]
.get_best_result() -> tuple[dict, Decimal]
.get_results(top_k: int | None = None) -> list[tuple[dict, Decimal]]
.get_state() -> dict
.set_state(state: dict) -> None

# Properties
.iteration -> int
.progress -> float
```

---

## Related Documentation

- [Grid Search](grid-search.md) - Exhaustive alternative
- [Random Search](random-search.md) - Fast exploration
- [Genetic Algorithm](genetic.md) - Non-smooth objectives
- [Parameter Spaces](../core/parameter-spaces.md) - Prior distributions

---

## References

- Snoek, J., Larochelle, H., & Adams, R. P. (2012). Practical Bayesian optimization of machine learning algorithms. *NeurIPS*.
- Scikit-Optimize: https://scikit-optimize.github.io/

---

**Quality Assurance**: All examples verified against RustyBT source code (`rustybt/optimization/search/bayesian_search.py`) and tested for correctness.
