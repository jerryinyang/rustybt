# Bayesian Optimization

Sample-efficient optimization using Gaussian processes and acquisition functions.

## Overview

Bayesian optimization builds a probabilistic model of the objective function and uses it to make intelligent decisions about which parameters to try next. It's particularly effective for expensive objective functions (long backtests).

## When to Use

✅ **Use Bayesian optimization when**:
- Objective function is expensive to evaluate (>1 minute per evaluation)
- Parameter space is continuous or mixed
- You want sample efficiency (fewer evaluations needed)
- Parameters have smooth relationships with objective

❌ **Don't use Bayesian optimization when**:
- Parameter space is purely categorical
- Objective function is very noisy
- You need perfectly reproducible results
- You want to parallelize many evaluations

## Basic Usage

```python
from rustybt.optimization.search import BayesianOptimizer
from rustybt.optimization.parameter_space import ParameterSpace, ContinuousParameter

# Define parameter space
param_space = ParameterSpace(parameters=[
    ContinuousParameter('threshold', 0.01, 0.10),
    ContinuousParameter('volatility_target', 0.10, 0.30)
])

# Create Bayesian optimizer
bayes = BayesianOptimizer(
    parameter_space=param_space,
    n_initial_points=10,      # Random initialization
    n_iterations=50,          # Total evaluations
    acquisition_function='EI' # Expected Improvement
)

# Optimization loop
while not bayes.is_complete():
    params = bayes.suggest()  # Suggests most promising parameters
    score = run_backtest(params)
    bayes.update(params, score)  # Updates Gaussian process model

# Get best parameters
best_params = bayes.get_best_params()
```

## Constructor

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
- `n_initial_points`: Random points before Gaussian process modeling
- `n_iterations`: Total evaluations (including initial points)
- `acquisition_function`: How to select next point
  - `'EI'`: Expected Improvement (balances exploration/exploitation)
  - `'PI'`: Probability of Improvement (more exploitative)
  - `'LCB'`: Lower Confidence Bound (more exploratory)
- `kappa`: Exploration parameter for LCB (higher = more exploration)
- `xi`: Exploration parameter for EI/PI (higher = more exploration)
- `random_seed`: Random seed for reproducibility

## Acquisition Functions

### Expected Improvement (EI)

Most commonly used, balances exploration and exploitation.

```python
bayes = BayesianOptimizer(
    parameter_space=param_space,
    acquisition_function='EI',
    xi=0.01  # Small value: exploit more
)
```

**How it works**: Maximizes expected improvement over current best.

**Use when**: General purpose optimization.

### Probability of Improvement (PI)

More exploitative than EI.

```python
bayes = BayesianOptimizer(
    parameter_space=param_space,
    acquisition_function='PI',
    xi=0.01
)
```

**How it works**: Maximizes probability of finding better point than current best.

**Use when**: You want to quickly find good (but not necessarily optimal) solutions.

### Lower Confidence Bound (LCB)

More exploratory, good for noisy objectives.

```python
bayes = BayesianOptimizer(
    parameter_space=param_space,
    acquisition_function='LCB',
    kappa=2.576  # Higher = more exploration
)
```

**How it works**: Balances mean prediction and uncertainty.

**Use when**: Objective function is noisy or you want thorough exploration.

## Complete Example

```python
from decimal import Decimal
from rustybt.optimization.search import BayesianOptimizer
from rustybt.optimization.parameter_space import (
    ParameterSpace,
    ContinuousParameter,
    DiscreteParameter
)

# Define parameter space
param_space = ParameterSpace(parameters=[
    ContinuousParameter('threshold', 0.01, 0.10, prior='uniform'),
    DiscreteParameter('lookback', 10, 100, step=5),
    ContinuousParameter('vol_target', 0.10, 0.30, prior='uniform')
])

# Create optimizer
bayes = BayesianOptimizer(
    parameter_space=param_space,
    n_initial_points=15,  # More initial points for 3 parameters
    n_iterations=100,
    acquisition_function='EI',
    random_seed=42
)

# Run optimization
print("Starting Bayesian optimization...")
iteration = 0

while not bayes.is_complete():
    params = bayes.suggest()
    score = run_backtest(params)
    bayes.update(params, score)

    iteration += 1
    if iteration <= bayes.n_initial_points:
        print(f"[Init {iteration}/{bayes.n_initial_points}] Exploring...")
    else:
        print(f"[{iteration}/{bayes.n_iterations}] "
              f"Current: {score:.3f} | Best: {bayes.get_best_score():.3f}")

# Results
best_params = bayes.get_best_params()
best_score = bayes.get_best_score()

print(f"\n=== Optimization Complete ===")
print(f"Best Sharpe: {best_score:.3f}")
print(f"Best Parameters:")
for param, value in best_params.items():
    print(f"  {param}: {value}")
```

## Visualization

### Convergence Plot

```python
import matplotlib.pyplot as plt

def plot_bayes_convergence(optimizer):
    """Plot convergence of Bayesian optimization."""
    results = optimizer.get_results()
    scores = [float(score) for _, score in results]

    # Best score at each iteration
    best_scores = []
    current_best = float('-inf')
    for score in scores:
        current_best = max(current_best, score)
        best_scores.append(current_best)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

    # All scores
    ax1.scatter(range(len(scores)), scores, alpha=0.5, label='Evaluated')
    ax1.plot(best_scores, 'r-', linewidth=2, label='Best so far')
    ax1.axvline(optimizer.n_initial_points, color='k', linestyle='--',
                label='End of initialization')
    ax1.set_xlabel('Iteration')
    ax1.set_ylabel('Sharpe Ratio')
    ax1.set_title('Bayesian Optimization Convergence')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Improvement per iteration
    improvements = [best_scores[i] - best_scores[i-1]
                   for i in range(1, len(best_scores))]
    ax2.bar(range(1, len(best_scores)), improvements, alpha=0.7)
    ax2.axvline(optimizer.n_initial_points, color='k', linestyle='--')
    ax2.set_xlabel('Iteration')
    ax2.set_ylabel('Improvement')
    ax2.set_title('Improvement per Iteration')
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    return fig
```

## Tuning Guidelines

### Number of Initial Points

**Rule of thumb**: 2-5 times the number of parameters

```python
n_params = len(param_space.parameters)
n_initial = max(10, 3 * n_params)  # At least 10, prefer 3x params
```

### Total Iterations

**Rule of thumb**: 20-50 times the number of parameters

```python
n_params = len(param_space.parameters)
n_iterations = min(200, 30 * n_params)  # Cap at 200
```

### Exploration vs Exploitation

**More exploration** (early phase, noisy objective):
```python
bayes = BayesianOptimizer(
    ...,
    acquisition_function='LCB',
    kappa=3.0  # High exploration
)
```

**More exploitation** (refinement phase):
```python
bayes = BayesianOptimizer(
    ...,
    acquisition_function='EI',
    xi=0.001  # Low exploration
)
```

## Advanced Techniques

### Two-Stage Optimization

Explore then exploit:

```python
# Stage 1: Exploration
bayes_explore = BayesianOptimizer(
    parameter_space=param_space,
    n_initial_points=20,
    n_iterations=50,
    acquisition_function='LCB',
    kappa=3.0  # High exploration
)
# ... run optimization

# Stage 2: Exploitation around best
best_region = create_narrow_space_around(bayes_explore.get_best_params())
bayes_exploit = BayesianOptimizer(
    parameter_space=best_region,
    n_initial_points=5,
    n_iterations=30,
    acquisition_function='EI',
    xi=0.001  # Low exploration
)
# ... run optimization
```

### Warm Start

Initialize with previous results:

```python
# Previous optimization
bayes1 = BayesianOptimizer(param_space, n_iterations=50)
# ... run

# New optimization with warm start
bayes2 = BayesianOptimizer(param_space, n_iterations=50)
for params, score in bayes1.get_results():
    bayes2.update(params, score)  # Load previous results

# Continue optimization
while not bayes2.is_complete():
    params = bayes2.suggest()
    score = run_backtest(params)
    bayes2.update(params, score)
```

## Comparison with Other Algorithms

| Aspect | Bayesian | Grid | Random | Genetic |
|--------|----------|------|--------|---------|
| **Sample Efficiency** | High | Low | Medium | Medium |
| **Speed per Iteration** | Medium | Fast | Fast | Medium |
| **Parallelizable** | Limited | Yes | Yes | Yes |
| **Continuous Params** | Excellent | Poor | Good | Good |
| **Noisy Objectives** | Medium | Good | Good | Good |

## Dependencies

Requires `scikit-optimize` package:

```bash
pip install scikit-optimize
```

## See Also

- [Grid Search](grid-search.md)
- [Random Search](random-search.md)
- [Parameter Spaces](../framework/parameter-spaces.md)
- [Overfitting Prevention](../best-practices/overfitting-prevention.md)
