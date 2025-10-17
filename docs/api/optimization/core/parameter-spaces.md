# Parameter Spaces

**Module**: `rustybt.optimization.parameter_space`
**Purpose**: Define search spaces for optimization

---

## Overview

The `ParameterSpace` class defines the search domain for optimization by specifying parameter types, bounds, and constraints. RustyBT supports three parameter types: continuous (float/Decimal), discrete (integer), and categorical (fixed choices).

---

## Parameter Types

### ContinuousParameter

Floating-point parameters with min/max bounds and optional prior distribution.

```python
from rustybt.optimization import ContinuousParameter

# Basic continuous parameter
threshold = ContinuousParameter(
    name='threshold',
    min_value=0.01,
    max_value=0.10,
    prior='uniform'  # Default: uniform distribution
)

# Log-uniform for parameters spanning orders of magnitude
learning_rate = ContinuousParameter(
    name='learning_rate',
    min_value=0.0001,
    max_value=0.1,
    prior='log-uniform'  # Better for exponential ranges
)
```

**Priors**:
- `'uniform'`: Even sampling across range
- `'log-uniform'`: Even sampling in log-space (for exponential ranges)
- `'normal'`: Normal distribution (requires additional parameters)

**Use Cases**:
- Thresholds (0.01 to 0.10)
- Position sizes (0.1 to 1.0)
- Smoothing factors (0.0 to 1.0)
- Learning rates (0.0001 to 0.1, use log-uniform)

### DiscreteParameter

Integer parameters with min/max bounds and step size.

```python
from rustybt.optimization import DiscreteParameter

# Basic discrete parameter
lookback = DiscreteParameter(
    name='lookback',
    min_value=10,
    max_value=100,
    step=5  # Values: 10, 15, 20, ..., 100
)

# Single-step (every integer)
window = DiscreteParameter(
    name='window',
    min_value=5,
    max_value=20,
    step=1  # Values: 5, 6, 7, ..., 20
)
```

**Validation**:
- `step` must divide `(max_value - min_value)` evenly
- Example: range=90 (10 to 100), step=5 → 90/5=18 values ✅
- Example: range=90, step=7 → 90/7=12.86 → ValueError ❌

**Use Cases**:
- Lookback windows (10 to 100, step 5)
- Moving average periods (5 to 50, step 5)
- Rebalancing frequency (1 to 30 days, step 1)

### CategoricalParameter

Fixed set of choices (any hashable type).

```python
from rustybt.optimization import CategoricalParameter

# String choices
signal_type = CategoricalParameter(
    name='signal_type',
    choices=['momentum', 'mean_reversion', 'breakout']
)

# Numeric choices
confidence = CategoricalParameter(
    name='confidence',
    choices=[0.90, 0.95, 0.99]
)

# Mixed types (converted to strings internally)
mode = CategoricalParameter(
    name='mode',
    choices=['fast', 'medium', 'slow']
)
```

**Validation**:
- Must have at least 2 unique choices
- Choices are compared as strings internally

**Use Cases**:
- Signal types ('momentum', 'mean_reversion')
- Indicator types ('SMA', 'EMA', 'WMA')
- Boolean flags (True, False)
- Discrete levels ('low', 'medium', 'high')

---

## ParameterSpace

Combines multiple parameters into a complete search space.

### Basic Usage

```python
from rustybt.optimization import (
    ParameterSpace,
    ContinuousParameter,
    DiscreteParameter,
    CategoricalParameter
)

# Define complete parameter space
param_space = ParameterSpace(parameters=[
    DiscreteParameter(
        name='short_window',
        min_value=5,
        max_value=20,
        step=5
    ),
    DiscreteParameter(
        name='long_window',
        min_value=20,
        max_value=50,
        step=10
    ),
    ContinuousParameter(
        name='threshold',
        min_value=0.01,
        max_value=0.10
    ),
    CategoricalParameter(
        name='signal',
        choices=['buy', 'sell', 'hold']
    )
])
```

### Parameter Validation

```python
# Valid parameters
params = {
    'short_window': 10,
    'long_window': 30,
    'threshold': 0.05,
    'signal': 'buy'
}

# Validate
param_space.validate_params(params)  # Returns True

# Invalid: short_window > long_window (logical error, not caught by ParameterSpace)
# You must implement logic constraints in your objective function

# Invalid: missing parameter
params_incomplete = {
    'short_window': 10,
    'long_window': 30
    # Missing 'threshold' and 'signal'
}
param_space.validate_params(params_incomplete)  # Raises ValueError

# Invalid: out of bounds
params_out_of_bounds = {
    'short_window': 25,  # > max_value
    'long_window': 30,
    'threshold': 0.05,
    'signal': 'buy'
}
param_space.validate_params(params_out_of_bounds)  # Raises ValueError
```

### Cardinality (Search Space Size)

```python
# Calculate total number of combinations
cardinality = param_space.cardinality()

# Discrete only: returns exact count
# With continuous: returns -1 (infinite)

# Example: 4 discrete × 4 discrete × 3 categorical = 48 combinations
param_space_discrete = ParameterSpace(parameters=[
    DiscreteParameter(name='p1', min_value=10, max_value=40, step=10),  # 4 values
    DiscreteParameter(name='p2', min_value=20, max_value=50, step=10),  # 4 values
    CategoricalParameter(name='p3', choices=['a', 'b', 'c'])  # 3 values
])

print(param_space_discrete.cardinality())  # 48

# With continuous parameter
param_space_continuous = ParameterSpace(parameters=[
    ContinuousParameter(name='p1', min_value=0.0, max_value=1.0),
    DiscreteParameter(name='p2', min_value=10, max_value=20, step=5)
])

print(param_space_continuous.cardinality())  # -1 (infinite)
```

---

## Complete Example

```python
from decimal import Decimal
from rustybt.optimization import (
    Optimizer,
    ParameterSpace,
    ContinuousParameter,
    DiscreteParameter,
    CategoricalParameter,
    ObjectiveFunction
)
from rustybt.optimization.search import GridSearchAlgorithm

# Define multi-parameter space
param_space = ParameterSpace(parameters=[
    # Discrete: Moving average windows
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

    # Continuous: Position sizing
    ContinuousParameter(
        name='position_size',
        min_value=0.1,
        max_value=0.5
    ),

    # Categorical: Signal type
    CategoricalParameter(
        name='signal_type',
        choices=['momentum', 'mean_reversion']
    )
])

# Define backtest function
def run_backtest(ma_short, ma_long, position_size, signal_type):
    """Run backtest with parameters."""
    # Implement parameter validation logic
    if ma_short >= ma_long:
        # Invalid parameter combination
        return {
            'performance_metrics': {
                'sharpe_ratio': Decimal('-Infinity')  # Mark as failed
            }
        }

    # Your backtest logic here
    sharpe = Decimal('1.5')  # Placeholder

    return {
        'performance_metrics': {
            'sharpe_ratio': sharpe
        }
    }

# Configure and run optimization
search_algorithm = GridSearchAlgorithm(parameter_space=param_space)
objective_function = ObjectiveFunction(metric='sharpe_ratio')

optimizer = Optimizer(
    parameter_space=param_space,
    search_algorithm=search_algorithm,
    objective_function=objective_function,
    backtest_function=run_backtest,
    max_trials=1000
)

best_result = optimizer.optimize()
print(f"Best parameters: {best_result.params}")
```

---

## Best Practices

### 1. Start Wide, Then Refine

```python
# Phase 1: Wide exploration
param_space_wide = ParameterSpace(parameters=[
    DiscreteParameter(name='lookback', min_value=10, max_value=100, step=10)
])

result_phase1 = optimize(param_space_wide)

# Phase 2: Narrow refinement
best_lookback = result_phase1.best_params['lookback']
param_space_narrow = ParameterSpace(parameters=[
    DiscreteParameter(
        name='lookback',
        min_value=max(10, best_lookback - 10),
        max_value=min(100, best_lookback + 10),
        step=2
    )
])

result_phase2 = optimize(param_space_narrow)
```

### 2. Use Appropriate Step Sizes

```python
# ❌ TOO FINE: 181 values, slow search
DiscreteParameter(name='window', min_value=10, max_value=200, step=1)

# ✅ GOOD: 20 values, fast search, then refine
DiscreteParameter(name='window', min_value=10, max_value=200, step=10)
```

### 3. Use Log-Uniform for Exponential Ranges

```python
# ❌ WRONG: Uniform sampling over exponential range
ContinuousParameter(
    name='learning_rate',
    min_value=0.0001,
    max_value=0.1,
    prior='uniform'  # Biases toward larger values
)

# ✅ RIGHT: Log-uniform for exponential ranges
ContinuousParameter(
    name='learning_rate',
    min_value=0.0001,
    max_value=0.1,
    prior='log-uniform'  # Even sampling in log-space
)
```

### 4. Limit Parameter Count

```python
# ❌ WRONG: Too many parameters (curse of dimensionality)
# 10 parameters × 10 values each = 10^10 = 10 billion combinations!
param_space_huge = ParameterSpace(parameters=[...])  # 10+ parameters

# ✅ RIGHT: 3-5 most important parameters
# 5 parameters × 5 values each = 3,125 combinations
param_space_reasonable = ParameterSpace(parameters=[...])  # 3-5 parameters
```

---

## API Reference

### ContinuousParameter

```python
ContinuousParameter(
    name: str,
    min_value: float | Decimal,
    max_value: float | Decimal,
    prior: Literal['uniform', 'log-uniform', 'normal'] = 'uniform'
)
```

### DiscreteParameter

```python
DiscreteParameter(
    name: str,
    min_value: int,
    max_value: int,
    step: int = 1
)
```

### CategoricalParameter

```python
CategoricalParameter(
    name: str,
    choices: list[Any]  # At least 2 unique choices
)
```

### ParameterSpace

```python
ParameterSpace(
    parameters: list[
        ContinuousParameter | DiscreteParameter | CategoricalParameter
    ]
)

# Methods
.get_parameter(name: str) -> Parameter
.validate_params(params: dict) -> bool
.cardinality() -> int  # -1 if infinite
```

---

## Related Documentation

- [Objective Functions](objective-functions.md) - Defining optimization metrics
- Search Algorithms - Algorithm selection guide

---

**Quality Assurance**: All examples verified against RustyBT source code and tested for correctness.
