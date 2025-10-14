# Random Search Algorithm

Random sampling-based optimization for large parameter spaces.

## Overview

Random search randomly samples parameter combinations from the search space. Despite its simplicity, it often outperforms grid search for high-dimensional problems and serves as an excellent baseline for more sophisticated algorithms.

## When to Use

✅ **Use random search when**:
- Parameter space is large or high-dimensional
- Initial exploration phase
- Need a fast baseline for comparison
- Grid search would take too long
- Some parameters more important than others

❌ **Don't use random search when**:
- Parameter space is small (<100 combinations) - use grid search
- Need deterministic, reproducible results - use grid search
- Sample efficiency critical - use Bayesian optimization
- Budget allows sophisticated methods

## Basic Usage

```python
from rustybt.optimization.search import RandomSearchAlgorithm
from rustybt.optimization.parameter_space import ParameterSpace, ContinuousParameter

# Define parameter space
param_space = ParameterSpace(parameters=[
    ContinuousParameter('threshold', 0.01, 0.10),
    ContinuousParameter('volatility_target', 0.10, 0.30)
])

# Create random search
random = RandomSearchAlgorithm(
    parameter_space=param_space,
    n_iterations=100,
    random_seed=42  # For reproducibility
)

# Optimization loop
while not random.is_complete():
    params = random.suggest()
    score = run_backtest(params)
    random.update(params, score)

# Get best parameters
best_params = random.get_best_params()
```

## Constructor

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
- `early_stopping_rounds`: Stop if no improvement for N iterations

## Sampling Strategies

### Uniform Sampling

Default strategy - equal probability across range:

```python
# Uniform sampling for continuous parameters
param = ContinuousParameter('threshold', 0.01, 0.10, prior='uniform')

# Sampling: P(x) = 1/(max-min) for all x in [min, max]
```

**Use when**: No prior knowledge about optimal region.

### Log-Uniform Sampling

For parameters spanning orders of magnitude:

```python
# Log-uniform sampling
param = ContinuousParameter(
    'learning_rate',
    min_value=1e-4,
    max_value=1e-1,
    prior='log-uniform'
)

# Sampling: More dense at lower values
# Good for: learning rates, regularization parameters
```

**Use when**: Parameter spans multiple orders of magnitude.

**Example**: Learning rate from 0.0001 to 0.1
- Uniform: equal chance of 0.05, 0.06, 0.07
- Log-uniform: more likely to sample 0.0001, 0.001, 0.01 than 0.09, 0.095, 0.099

### Discrete Uniform Sampling

For discrete/categorical parameters:

```python
# Discrete parameters sampled uniformly
lookback = DiscreteParameter('lookback', 10, 100, step=5)
# Equal chance: 10, 15, 20, ..., 95, 100

signal_type = CategoricalParameter('signal', ['momentum', 'mean_reversion'])
# 50% chance each
```

## Sample Size Determination

### Rule of Thumb

**Minimum samples**: 10 × number of parameters

```python
n_params = len(param_space.parameters)
min_iterations = 10 * n_params

random = RandomSearchAlgorithm(
    parameter_space=param_space,
    n_iterations=max(50, min_iterations)  # At least 50
)
```

### Sample Size by Dimension

| Dimensions | Minimum Samples | Recommended |
|-----------|----------------|-------------|
| 1-2 | 20 | 50 |
| 3-4 | 50 | 100 |
| 5-6 | 100 | 200 |
| 7-10 | 200 | 500 |
| >10 | 500 | 1000+ |

### Adaptive Sample Size

Estimate needed samples based on progress:

```python
def adaptive_sample_size(param_space, initial_samples=100):
    """Adaptively determine sample size."""
    random = RandomSearchAlgorithm(
        parameter_space=param_space,
        n_iterations=initial_samples
    )

    # Run initial samples
    for _ in range(initial_samples):
        params = random.suggest()
        score = run_backtest(params)
        random.update(params, score)

    # Analyze improvement rate
    scores = [s for _, s in random.get_results()]
    improvement_rate = (max(scores[-20:]) - max(scores[:20])) / max(scores[:20])

    # Continue if still improving significantly
    if improvement_rate > 0.10:  # >10% improvement
        return initial_samples * 2
    else:
        return initial_samples
```

## Convergence Criteria

### No Improvement Stopping

Stop when no improvement for N iterations:

```python
random = RandomSearchAlgorithm(
    parameter_space=param_space,
    n_iterations=1000,
    early_stopping_rounds=50  # Stop if no improvement for 50 iterations
)

while not random.is_complete():
    params = random.suggest()
    score = run_backtest(params)
    random.update(params, score)

    if random.early_stopped:
        print(f"Early stopped at iteration {random.current_iteration}")
        break
```

### Convergence Threshold

Stop when score reaches target:

```python
target_sharpe = Decimal('2.0')

while not random.is_complete():
    params = random.suggest()
    score = run_backtest(params)
    random.update(params, score)

    if score >= target_sharpe:
        print(f"Target reached at iteration {random.current_iteration}")
        break
```

### Time-Based Stopping

Stop after time limit:

```python
import time

max_duration = 3600  # 1 hour
start_time = time.time()

while not random.is_complete():
    if time.time() - start_time > max_duration:
        print("Time limit reached")
        break

    params = random.suggest()
    score = run_backtest(params)
    random.update(params, score)
```

## Complete Example

```python
from decimal import Decimal
from rustybt.optimization.search import RandomSearchAlgorithm
from rustybt.optimization.parameter_space import (
    ParameterSpace,
    DiscreteParameter,
    ContinuousParameter
)
import matplotlib.pyplot as plt

# Define parameter space
param_space = ParameterSpace(parameters=[
    DiscreteParameter('lookback', 10, 100, step=5),
    ContinuousParameter('threshold', 0.01, 0.10, prior='uniform'),
    ContinuousParameter('volatility_target', 0.10, 0.30, prior='uniform')
])

print(f"Parameter space dimensionality: {len(param_space.parameters)}")
recommended_samples = 100 * len(param_space.parameters)
print(f"Recommended samples: {recommended_samples}")

# Create random search
random = RandomSearchAlgorithm(
    parameter_space=param_space,
    n_iterations=300,  # 100x per parameter
    random_seed=42,
    early_stopping_rounds=50
)

# Run optimization
print("Starting random search...")
iteration = 0

while not random.is_complete():
    params = random.suggest()
    score = run_backtest(params)
    random.update(params, score)

    iteration += 1
    if iteration % 50 == 0:
        best_score = random.get_best_score()
        print(f"Iteration {iteration}: Best Sharpe = {best_score:.3f}")

    if random.early_stopped:
        print(f"Early stopped at iteration {iteration}")
        break

# Results
best_params = random.get_best_params()
best_score = random.get_best_score()

print(f"\n=== Optimization Complete ===")
print(f"Iterations: {iteration}")
print(f"Best Sharpe: {best_score:.3f}")
print(f"Best Parameters:")
for param, value in best_params.items():
    print(f"  {param}: {value}")

# Analyze convergence
results = random.get_results()
scores = [float(score) for _, score in results]
iterations = range(1, len(scores) + 1)

# Plot convergence
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

# All scores
ax1.scatter(iterations, scores, alpha=0.5, s=20)
ax1.set_xlabel('Iteration')
ax1.set_ylabel('Sharpe Ratio')
ax1.set_title('Random Search Exploration')
ax1.grid(True, alpha=0.3)

# Best score evolution
best_scores = []
current_best = float('-inf')
for score in scores:
    current_best = max(current_best, score)
    best_scores.append(current_best)

ax2.plot(iterations, best_scores, 'r-', linewidth=2)
ax2.set_xlabel('Iteration')
ax2.set_ylabel('Best Sharpe Ratio')
ax2.set_title('Best Score Evolution')
ax2.grid(True, alpha=0.3)

plt.tight_layout()
plt.show()
```

## Comparison with Grid Search

### When Random Beats Grid

**High-dimensional spaces**:
```python
# 5 parameters, 10 values each
# Grid: 10^5 = 100,000 evaluations
# Random: 500 evaluations (0.5% of grid)

# Random search likely finds 95% as good solution
# with 0.5% of the computation
```

**Continuous parameters**:
```python
# Continuous parameters
# Grid: Must discretize, arbitrary granularity
# Random: Natural continuous sampling
```

**Unequal importance**:
```python
# If threshold matters more than lookback:
# Grid: Wastes evaluations on unimportant dimensions
# Random: More likely to explore important dimension
```

### When Grid Beats Random

**Small spaces**:
```python
# 2 parameters, 5 values each = 25 combinations
# Grid: Guaranteed to find best in 25 evaluations
# Random: Might miss best even with 100 evaluations
```

**Determinism required**:
```python
# Grid: Deterministic, reproducible
# Random: Different run = different results (even with seed)
```

### Practical Comparison

| Aspect | Random Search | Grid Search |
|--------|---------------|-------------|
| **Speed** | Fast | Slow |
| **Dimensions** | Excellent for high-d | Poor for high-d |
| **Determinism** | No | Yes |
| **Coverage** | Probabilistic | Complete |
| **Continuous params** | Native | Must discretize |
| **Sample efficiency** | Medium | Low |

## Best Practices

### 1. Start with Random Search

Use random search for initial exploration:

```python
# Phase 1: Random exploration (fast)
random = RandomSearchAlgorithm(param_space, n_iterations=200)
result1 = random.optimize()

# Phase 2: Refine with Bayesian (expensive but efficient)
narrow_space = create_space_around(result1.best_params, radius=0.2)
bayes = BayesianOptimizer(narrow_space, n_iterations=50)
result2 = bayes.optimize()
```

### 2. Use Log-Uniform for Wide Ranges

```python
# WRONG: Uniform sampling over wide range
learning_rate = ContinuousParameter('lr', 0.0001, 0.1, prior='uniform')
# Most samples will be >0.05, missing good region

# RIGHT: Log-uniform for wide ranges
learning_rate = ContinuousParameter('lr', 0.0001, 0.1, prior='log-uniform')
# Samples spread across orders of magnitude
```

### 3. Set Appropriate Sample Size

```python
# Too few samples
random = RandomSearchAlgorithm(param_space, n_iterations=10)  # Risky!

# Good: 10-100x number of parameters
n_params = len(param_space.parameters)
n_iterations = 50 * n_params
random = RandomSearchAlgorithm(param_space, n_iterations=n_iterations)
```

### 4. Use Early Stopping

```python
# Save time with early stopping
random = RandomSearchAlgorithm(
    param_space,
    n_iterations=500,
    early_stopping_rounds=50  # Stop if no improvement
)
```

### 5. Analyze Results

```python
# Get multiple good solutions
top_10 = random.get_results(top_k=10)

# Check parameter distributions in top results
for param in param_space.parameters:
    values = [result[0][param.name] for result in top_10]
    print(f"{param.name}: {min(values):.3f} - {max(values):.3f}")
```

## Common Pitfalls

### ❌ Too Few Samples

```python
# BAD: Only 20 samples for 5 parameters
random = RandomSearchAlgorithm(param_space, n_iterations=20)

# GOOD: 50-100x per parameter
random = RandomSearchAlgorithm(param_space, n_iterations=250)
```

### ❌ No Random Seed

```python
# BAD: Non-reproducible
random = RandomSearchAlgorithm(param_space, n_iterations=100)

# GOOD: Reproducible with seed
random = RandomSearchAlgorithm(param_space, n_iterations=100, random_seed=42)
```

### ❌ Using Random for Small Spaces

```python
# BAD: Only 25 combinations, use grid
param_space = ParameterSpace(parameters=[
    DiscreteParameter('x', 1, 5, step=1),
    DiscreteParameter('y', 1, 5, step=1)
])
random = RandomSearchAlgorithm(param_space, n_iterations=100)

# GOOD: Use grid for small spaces
grid = GridSearchAlgorithm(param_space)  # Only 25 evaluations
```

### ❌ Ignoring Parameter Scaling

```python
# BAD: Uniform for parameters spanning orders of magnitude
param = ContinuousParameter('regularization', 0.0001, 10.0, prior='uniform')

# GOOD: Log-uniform for wide ranges
param = ContinuousParameter('regularization', 0.0001, 10.0, prior='log-uniform')
```

## Theoretical Background

### Why Random Search Works

**Key insight**: In high dimensions, most grid points contribute little.

**Bergstra & Bengio (2012)**: Random search more efficient than grid search when:
1. Some parameters more important than others
2. Dimensions >3
3. Objective function has low effective dimensionality

**Proof sketch**:
- Grid with n points per dimension: n^d total evaluations
- Random with n^d samples: Explores d×n unique values per dimension
- If only k << d dimensions matter: Random effectively searches k dimensions

### Sample Complexity

**Theorem**: With high probability, random search finds ε-optimal solution with:
```
n = O(d × log(1/ε))
```
samples, where d = dimensions, ε = optimality gap.

**Practical implication**: Random search scales linearly with dimensions (vs exponentially for grid).

## Advanced Techniques

### Importance Sampling

Sample more from promising regions:

```python
def importance_sampling(param_space, initial_samples=100):
    """Focus samples on promising regions."""
    # Phase 1: Uniform random sampling
    random1 = RandomSearchAlgorithm(param_space, n_iterations=initial_samples)
    # ... run optimization

    # Phase 2: Sample near good solutions
    top_10_params = [p for p, _ in random1.get_results(top_k=10)]

    # Create new parameter space centered on good regions
    refined_space = create_refined_space(top_10_params)
    random2 = RandomSearchAlgorithm(refined_space, n_iterations=initial_samples)
    # ... continue optimization
```

### Latin Hypercube Sampling

Better space coverage than pure random:

```python
from rustybt.optimization.sampling import latin_hypercube_sample

# Instead of pure random
samples = latin_hypercube_sample(param_space, n_samples=100)

# Ensures more uniform coverage of parameter space
```

## See Also

- [Grid Search](grid-search.md)
- [Bayesian Optimization](bayesian.md)
- [Parameter Spaces](../framework/parameter-spaces.md)
- [Parallel Processing](../parallel/multiprocessing.md)
