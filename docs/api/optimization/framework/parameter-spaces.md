# Parameter Spaces

Defining search spaces for strategy optimization.

## Overview

A parameter space defines the domain of possible parameter values for optimization. RustyBT supports three parameter types: continuous, discrete, and categorical.

## Parameter Types

### Continuous Parameters

Float or Decimal parameters with continuous range.

```python
from rustybt.optimization.parameter_space import ContinuousParameter

threshold = ContinuousParameter(
    name='threshold',
    min_value=0.01,
    max_value=0.10,
    prior='uniform'  # or 'log-uniform', 'normal'
)
```

**Use cases**:
- Thresholds (e.g., signal threshold from 0.01 to 0.10)
- Multipliers (e.g., position sizing multiplier from 0.5 to 2.0)
- Volatility targets (e.g., target volatility from 0.10 to 0.30)

**Prior distributions**:
- `'uniform'`: Equal probability across range (default)
- `'log-uniform'`: Log-scaled sampling (good for parameters spanning orders of magnitude)
- `'normal'`: Normal distribution centered at midpoint

```python
# Log-uniform for parameters spanning orders of magnitude
learning_rate = ContinuousParameter(
    name='learning_rate',
    min_value=1e-4,
    max_value=1e-1,
    prior='log-uniform'  # Samples more densely at lower values
)
```

### Discrete Parameters

Integer parameters with step size.

```python
from rustybt.optimization.parameter_space import DiscreteParameter

lookback = DiscreteParameter(
    name='lookback',
    min_value=10,
    max_value=100,
    step=5
)
# Valid values: [10, 15, 20, 25, ..., 95, 100]
```

**Use cases**:
- Lookback periods (e.g., moving average length from 10 to 100 days)
- Position sizes (e.g., shares from 100 to 1000, step 100)
- Rebalancing frequencies (e.g., days between rebalancing from 1 to 30)

**Step size considerations**:
- Smaller steps = finer granularity but more combinations
- Larger steps = faster optimization but coarser results
- Rule of thumb: 5-20 values per parameter

```python
# Example with different step sizes
fine_grained = DiscreteParameter('fine', 10, 100, step=1)  # 91 values
coarse_grained = DiscreteParameter('coarse', 10, 100, step=10)  # 10 values
```

### Categorical Parameters

Parameters with fixed set of choices.

```python
from rustybt.optimization.parameter_space import CategoricalParameter

signal_type = CategoricalParameter(
    name='signal_type',
    choices=['momentum', 'mean_reversion', 'breakout']
)
```

**Use cases**:
- Algorithm variants (e.g., 'ema' vs 'sma' vs 'wma')
- Signal types (e.g., 'momentum' vs 'mean_reversion')
- Execution styles (e.g., 'market' vs 'limit')

**Design considerations**:
- Keep choices to 2-5 options when possible
- More options = exponential growth in combinations
- Consider separate optimizations if >5 choices

## Creating Parameter Spaces

### Basic Creation

```python
from rustybt.optimization.parameter_space import ParameterSpace

param_space = ParameterSpace(parameters=[
    DiscreteParameter('lookback_short', 10, 50, step=5),
    DiscreteParameter('lookback_long', 50, 200, step=25),
    ContinuousParameter('threshold', 0.01, 0.10),
    CategoricalParameter('signal', choices=['momentum', 'mean_reversion'])
])
```

### Builder Pattern

Fluent interface for building parameter spaces:

```python
param_space = (
    ParameterSpace()
    .add_discrete('lookback_short', 10, 50, step=5)
    .add_discrete('lookback_long', 50, 200, step=25)
    .add_continuous('threshold', 0.01, 0.10, prior='uniform')
    .add_categorical('signal', ['momentum', 'mean_reversion'])
)
```

## Parameter Constraints

### Simple Constraints

Ensure parameter relationships:

```python
param_space = ParameterSpace(
    parameters=[
        DiscreteParameter('lookback_short', 10, 50),
        DiscreteParameter('lookback_long', 50, 200)
    ],
    constraints=[
        lambda p: p['lookback_short'] < p['lookback_long']
    ]
)
```

### Complex Constraints

Multiple conditions:

```python
def validate_parameters(params):
    """Complex validation logic."""
    # Short lookback must be less than long
    if params['lookback_short'] >= params['lookback_long']:
        return False

    # Ratio constraint
    if params['lookback_long'] / params['lookback_short'] < 2:
        return False

    # Conditional constraint
    if params['signal'] == 'momentum' and params['threshold'] < 0.02:
        return False

    return True

param_space = ParameterSpace(
    parameters=[...],
    constraints=[validate_parameters]
)
```

## Cardinality Calculation

Calculate total number of parameter combinations:

```python
space = ParameterSpace(parameters=[
    DiscreteParameter('x', 10, 100, step=10),  # 10 values
    DiscreteParameter('y', 20, 50, step=5),     # 7 values
    CategoricalParameter('z', ['a', 'b', 'c'])  # 3 values
])

total_combinations = space.cardinality()
# Result: 10 * 7 * 3 = 210 combinations
```

**Note**: Returns `-1` if space contains continuous parameters (infinite combinations).

## Sampling Strategies

### Random Sampling

Sample uniformly from parameter space:

```python
# Random sample respects parameter priors
params = param_space.sample(n=100)
```

### Latin Hypercube Sampling

Better space coverage than random:

```python
from rustybt.optimization.sampling import latin_hypercube_sample

params = latin_hypercube_sample(param_space, n_samples=100)
```

**Benefits**:
- More uniform coverage of parameter space
- Reduces clustering of samples
- Better for high-dimensional spaces

### Sobol Sequences

Low-discrepancy sequence for quasi-random sampling:

```python
from rustybt.optimization.sampling import sobol_sample

params = sobol_sample(param_space, n_samples=100)
```

**Benefits**:
- Even better space coverage than Latin hypercube
- Deterministic (reproducible)
- Ideal for sensitivity analysis

## Design Guidelines

### Parameter Count

Rule of thumb based on available data:

| Trades Available | Max Parameters | Rationale |
|------------------|----------------|-----------|
| <100 | 1-2 | High overfitting risk |
| 100-500 | 2-4 | Moderate risk |
| 500-1000 | 4-6 | Acceptable |
| >1000 | 6-10 | Lower risk |

⚠️ **More parameters = higher overfitting risk!**

### Parameter Ranges

**Too narrow**:
```python
# Bad: Might miss optimal region
DiscreteParameter('lookback', 45, 55, step=5)  # Only 3 values
```

**Too wide**:
```python
# Bad: Too many combinations, includes unreasonable values
DiscreteParameter('lookback', 1, 1000, step=1)  # 1000 values
```

**Just right**:
```python
# Good: Reasonable range, coarse initial search
DiscreteParameter('lookback', 10, 200, step=10)  # 20 values
```

### Parameter Independence

Prefer independent parameters:

❌ **Correlated parameters** (bad):
```python
ParameterSpace(parameters=[
    DiscreteParameter('ma_period', 10, 100),
    DiscreteParameter('ma_period_doubled', 20, 200)  # Redundant!
])
```

✅ **Independent parameters** (good):
```python
ParameterSpace(parameters=[
    DiscreteParameter('ma_short', 10, 50),
    DiscreteParameter('ma_long', 50, 200)
])
```

## Advanced Techniques

### Hierarchical Parameter Spaces

Conditional parameters based on choices:

```python
class HierarchicalParameterSpace:
    def __init__(self):
        self.base_space = ParameterSpace(parameters=[
            CategoricalParameter('strategy_type', ['momentum', 'mean_reversion'])
        ])

        self.momentum_space = ParameterSpace(parameters=[
            DiscreteParameter('momentum_lookback', 10, 50)
        ])

        self.mean_reversion_space = ParameterSpace(parameters=[
            DiscreteParameter('mean_period', 20, 100),
            ContinuousParameter('entry_threshold', 1.5, 3.0)
        ])

    def sample(self):
        base_params = self.base_space.sample()

        if base_params['strategy_type'] == 'momentum':
            specific_params = self.momentum_space.sample()
        else:
            specific_params = self.mean_reversion_space.sample()

        return {**base_params, **specific_params}
```

### Dynamic Parameter Ranges

Adjust ranges based on asset characteristics:

```python
def create_param_space_for_asset(asset):
    """Create parameter space tailored to asset volatility."""
    volatility = calculate_volatility(asset)

    if volatility > 0.30:  # High volatility
        lookback_range = (5, 30)  # Shorter lookbacks
        threshold_range = (0.02, 0.10)  # Wider thresholds
    else:  # Low volatility
        lookback_range = (20, 100)  # Longer lookbacks
        threshold_range = (0.005, 0.030)  # Tighter thresholds

    return ParameterSpace(parameters=[
        DiscreteParameter('lookback', *lookback_range, step=5),
        ContinuousParameter('threshold', *threshold_range)
    ])
```

### Multi-Resolution Search

Start coarse, then refine:

```python
# Stage 1: Coarse search
coarse_space = ParameterSpace(parameters=[
    DiscreteParameter('lookback', 10, 100, step=20)  # 5 values
])

coarse_result = optimize(coarse_space)
best_lookback = coarse_result.best_params['lookback']

# Stage 2: Fine search around best
fine_space = ParameterSpace(parameters=[
    DiscreteParameter(
        'lookback',
        max(10, best_lookback - 10),
        min(100, best_lookback + 10),
        step=2  # Finer granularity
    )
])

fine_result = optimize(fine_space)
```

## Common Patterns

### Moving Average Crossover

```python
param_space = ParameterSpace(parameters=[
    DiscreteParameter('ma_short', 10, 50, step=5),
    DiscreteParameter('ma_long', 50, 200, step=10)
], constraints=[
    lambda p: p['ma_short'] < p['ma_long'],
    lambda p: p['ma_long'] / p['ma_short'] >= 2  # Minimum ratio
])
```

### Mean Reversion

```python
param_space = ParameterSpace(parameters=[
    DiscreteParameter('lookback', 20, 100, step=10),
    ContinuousParameter('entry_threshold', 1.5, 3.0),  # Std devs
    ContinuousParameter('exit_threshold', 0.0, 1.0),
    DiscreteParameter('holding_period_max', 5, 30, step=5)
])
```

### Momentum

```python
param_space = ParameterSpace(parameters=[
    DiscreteParameter('lookback', 10, 60, step=5),
    ContinuousParameter('signal_threshold', 0.01, 0.10),
    CategoricalParameter('price_type', ['close', 'typical', 'weighted']),
    DiscreteParameter('rebalance_freq', 1, 10, step=1)  # Days
])
```

## Validation

### Pre-Optimization Validation

Check parameter space before optimization:

```python
def validate_param_space(space):
    """Validate parameter space design."""
    # Check cardinality
    cardinality = space.cardinality()
    if cardinality > 10000:
        print(f"Warning: Large space ({cardinality} combinations)")

    # Check parameter count
    n_params = len(space.parameters)
    if n_params > 6:
        print(f"Warning: Many parameters ({n_params}), overfitting risk")

    # Sample and validate
    samples = [space.sample() for _ in range(100)]
    if len(set(str(s) for s in samples)) < 50:
        print("Warning: Low diversity in samples")
```

## See Also

- [Architecture](architecture.md)
- [Objective Functions](objective-functions.md)
- [Grid Search](../algorithms/grid-search.md)
- [Overfitting Prevention](../best-practices/overfitting-prevention.md)
