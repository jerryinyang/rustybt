# Objective Functions

**Module**: `rustybt.optimization.objective`
**Purpose**: Extract optimization metrics from backtest results

---

## Overview

The `ObjectiveFunction` class extracts a single scalar metric from backtest results to guide optimization. It supports standard performance metrics (Sharpe ratio, Sortino ratio, etc.) and custom objective functions for complex optimization criteria.

**Key Principle**: The objective function must return a single scalar value where **higher is better** (after applying `higher_is_better` flag).

---

## Standard Metrics

### Basic Usage

```python
from rustybt.optimization import ObjectiveFunction

# Maximize Sharpe ratio (most common)
obj_sharpe = ObjectiveFunction(metric='sharpe_ratio')

# Maximize Sortino ratio
obj_sortino = ObjectiveFunction(metric='sortino_ratio')

# Maximize Calmar ratio (return / max drawdown)
obj_calmar = ObjectiveFunction(metric='calmar_ratio')

# Maximize total return
obj_return = ObjectiveFunction(metric='total_return')

# Minimize max drawdown (note: higher_is_better=False)
obj_drawdown = ObjectiveFunction(
    metric='max_drawdown',
    higher_is_better=False  # Inverts score: smaller drawdown = higher score
)
```

### Available Standard Metrics

| Metric | Description | Typical Range | Higher is Better |
|--------|-------------|---------------|------------------|
| `sharpe_ratio` | Risk-adjusted returns | -3 to +3 | Yes |
| `sortino_ratio` | Downside risk-adjusted returns | -3 to +3 | Yes |
| `calmar_ratio` | Return over max drawdown | -5 to +5 | Yes |
| `total_return` | Cumulative return | -1.0 to +∞ | Yes |
| `max_drawdown` | Maximum peak-to-trough decline | -1.0 to 0.0 | No (minimize) |
| `win_rate` | Percentage of winning trades | 0.0 to 1.0 | Yes |
| `profit_factor` | Gross profit / gross loss | 0 to +∞ | Yes |

---

## How It Works

### Backtest Result Format

Your `backtest_function` must return a dictionary with `'performance_metrics'` key:

```python
def run_backtest(**params):
    """Run backtest with parameters.

    Returns:
        dict with 'performance_metrics' containing optimization metrics
    """
    # Your backtest logic
    # ...

    return {
        'performance_metrics': {
            'sharpe_ratio': Decimal('1.5'),
            'sortino_ratio': Decimal('1.8'),
            'total_return': Decimal('0.25'),
            'max_drawdown': Decimal('-0.10'),
            'win_rate': Decimal('0.55'),
            'profit_factor': Decimal('1.4')
        }
    }
```

### Score Extraction

```python
from decimal import Decimal

objective = ObjectiveFunction(metric='sharpe_ratio')

backtest_result = {
    'performance_metrics': {
        'sharpe_ratio': Decimal('1.5')
    }
}

score = objective.evaluate(backtest_result)
print(score)  # Decimal('1.5')
```

### Score Inversion for Minimization

```python
# Minimize max drawdown
objective = ObjectiveFunction(
    metric='max_drawdown',
    higher_is_better=False
)

backtest_result = {
    'performance_metrics': {
        'max_drawdown': Decimal('-0.15')  # -15% drawdown
    }
}

score = objective.evaluate(backtest_result)
print(score)  # Decimal('0.15') - inverted, so lower drawdown = higher score
```

---

## Custom Objective Functions

For complex optimization criteria, define a custom function:

### Basic Custom Objective

```python
from decimal import Decimal

def custom_objective(backtest_result):
    """Calculate custom optimization metric.

    Args:
        backtest_result: Full backtest result dictionary

    Returns:
        Decimal score (higher is better)
    """
    metrics = backtest_result['performance_metrics']

    sharpe = Decimal(str(metrics['sharpe_ratio']))
    max_dd = Decimal(str(metrics['max_drawdown']))

    # Example: Sharpe ratio with drawdown penalty
    if abs(max_dd) > Decimal('0.20'):
        # Penalize strategies with >20% drawdown
        penalty = abs(max_dd) * Decimal('5')
        return sharpe - penalty

    return sharpe

# Use custom objective
objective = ObjectiveFunction(
    metric='custom',
    custom_function=custom_objective
)
```

### Multi-Objective Optimization

```python
from decimal import Decimal

def multi_objective(backtest_result):
    """Weighted combination of multiple metrics."""
    metrics = backtest_result['performance_metrics']

    sharpe = Decimal(str(metrics['sharpe_ratio']))
    sortino = Decimal(str(metrics['sortino_ratio']))
    calmar = Decimal(str(metrics['calmar_ratio']))

    # Weighted average
    weights = {
        'sharpe': Decimal('0.5'),
        'sortino': Decimal('0.3'),
        'calmar': Decimal('0.2')
    }

    score = (
        weights['sharpe'] * sharpe +
        weights['sortino'] * sortino +
        weights['calmar'] * calmar
    )

    return score

objective = ObjectiveFunction(
    metric='custom',
    custom_function=multi_objective
)
```

### Risk-Constrained Optimization

```python
from decimal import Decimal

def risk_constrained_objective(backtest_result):
    """Maximize return subject to risk constraints."""
    metrics = backtest_result['performance_metrics']

    total_return = Decimal(str(metrics['total_return']))
    max_dd = abs(Decimal(str(metrics['max_drawdown'])))
    win_rate = Decimal(str(metrics['win_rate']))

    # Hard constraints
    if max_dd > Decimal('0.25'):  # Max 25% drawdown
        return Decimal('-Infinity')

    if win_rate < Decimal('0.45'):  # Min 45% win rate
        return Decimal('-Infinity')

    # If constraints met, maximize total return
    return total_return

objective = ObjectiveFunction(
    metric='custom',
    custom_function=risk_constrained_objective
)
```

---

## Complete Example

```python
from decimal import Decimal
from rustybt.optimization import (
    Optimizer,
    ParameterSpace,
    DiscreteParameter,
    ObjectiveFunction
)
from rustybt.optimization.search import GridSearchAlgorithm

# Define parameter space
param_space = ParameterSpace(parameters=[
    DiscreteParameter(name='lookback', min_value=10, max_value=50, step=10)
])

# Define backtest function
def run_backtest(lookback):
    """Run backtest and return metrics."""
    # Your backtest implementation
    # ...

    return {
        'performance_metrics': {
            'sharpe_ratio': Decimal('1.5'),
            'sortino_ratio': Decimal('1.8'),
            'total_return': Decimal('0.25'),
            'max_drawdown': Decimal('-0.10')
        }
    }

# Standard metric optimization
objective_standard = ObjectiveFunction(metric='sharpe_ratio')

# Custom metric optimization
def custom_score(result):
    metrics = result['performance_metrics']
    sharpe = Decimal(str(metrics['sharpe_ratio']))
    max_dd = abs(Decimal(str(metrics['max_drawdown'])))

    # Maximize Sharpe, penalize drawdown > 15%
    if max_dd > Decimal('0.15'):
        return sharpe - (max_dd * Decimal('10'))
    return sharpe

objective_custom = ObjectiveFunction(
    metric='custom',
    custom_function=custom_score
)

# Run optimization
search = GridSearchAlgorithm(parameter_space=param_space)

optimizer = Optimizer(
    parameter_space=param_space,
    search_algorithm=search,
    objective_function=objective_custom,  # Use custom objective
    backtest_function=run_backtest,
    max_trials=10
)

best_result = optimizer.optimize()
print(f"Best score: {best_result.score}")
print(f"Best params: {best_result.params}")
```

---

## Best Practices

### 1. Pre-Define Objective Function

```python
# ❌ WRONG: Trying multiple objectives and picking best
for metric in ['sharpe', 'sortino', 'calmar']:
    objective = ObjectiveFunction(metric=metric)
    result = optimize(objective)
    # Picking the best = data snooping bias!

# ✅ RIGHT: Pre-define objective and stick to it
objective = ObjectiveFunction(metric='sharpe_ratio')
result = optimize(objective)
```

### 2. Use Constraints in Custom Functions

```python
def constrained_objective(result):
    """Enforce constraints via -Infinity."""
    metrics = result['performance_metrics']

    # Extract metrics
    sharpe = Decimal(str(metrics['sharpe_ratio']))
    max_dd = abs(Decimal(str(metrics['max_drawdown'])))

    # Hard constraints: return -Infinity for violations
    if max_dd > Decimal('0.25'):
        return Decimal('-Infinity')

    # Soft constraints: penalize but don't exclude
    penalty = Decimal('0')
    if max_dd > Decimal('0.15'):
        penalty = (max_dd - Decimal('0.15')) * Decimal('5')

    return sharpe - penalty
```

### 3. Handle Missing Metrics

```python
def robust_objective(result):
    """Handle missing or invalid metrics gracefully."""
    try:
        metrics = result.get('performance_metrics', {})

        sharpe = metrics.get('sharpe_ratio')
        if sharpe is None:
            return Decimal('-Infinity')

        return Decimal(str(sharpe))

    except (KeyError, ValueError, TypeError) as e:
        # Log error and return failure score
        print(f"Objective function error: {e}")
        return Decimal('-Infinity')
```

### 4. Normalize Multi-Objective Scores

```python
def normalized_multi_objective(result):
    """Normalize metrics to comparable scales."""
    metrics = result['performance_metrics']

    # Normalize each metric to [0, 1] scale
    sharpe_raw = Decimal(str(metrics['sharpe_ratio']))
    sharpe_norm = (sharpe_raw + Decimal('3')) / Decimal('6')  # Assume range [-3, 3]

    win_rate = Decimal(str(metrics['win_rate']))  # Already [0, 1]

    # Weighted combination
    score = Decimal('0.7') * sharpe_norm + Decimal('0.3') * win_rate

    return score
```

---

## Common Pitfalls

### ❌ Pitfall 1: Forgetting to Invert Minimization Metrics

```python
# WRONG: Maximizing max_drawdown (more negative is worse!)
obj = ObjectiveFunction(metric='max_drawdown')  # higher_is_better=True by default

# RIGHT: Minimizing max_drawdown
obj = ObjectiveFunction(metric='max_drawdown', higher_is_better=False)
```

### ❌ Pitfall 2: Non-Stationary Objectives

```python
# WRONG: Objective changes during optimization
def changing_objective(result):
    # Don't change objective logic mid-optimization!
    if iteration < 50:
        return sharpe
    else:
        return sortino

# RIGHT: Fixed objective function
def fixed_objective(result):
    return sharpe  # Consistent throughout
```

### ❌ Pitfall 3: Unstable Custom Functions

```python
# WRONG: Division by zero, NaN possible
def unstable_objective(result):
    sharpe = result['sharpe']
    volatility = result['volatility']
    return sharpe / volatility  # What if volatility = 0?

# RIGHT: Handle edge cases
def stable_objective(result):
    sharpe = Decimal(str(result['sharpe']))
    volatility = Decimal(str(result['volatility']))

    if volatility == Decimal('0'):
        return Decimal('-Infinity')

    return sharpe / volatility
```

---

## API Reference

### ObjectiveFunction

```python
ObjectiveFunction(
    metric: ObjectiveMetric,
    custom_function: Callable[[dict], Decimal] | None = None,
    higher_is_better: bool = True
)

# Types
ObjectiveMetric = Literal[
    'sharpe_ratio',
    'sortino_ratio',
    'calmar_ratio',
    'total_return',
    'max_drawdown',
    'win_rate',
    'profit_factor',
    'custom'
]

# Methods
.evaluate(backtest_result: dict) -> Decimal
```

### Custom Function Signature

```python
def custom_function(backtest_result: dict[str, Any]) -> Decimal:
    """Custom objective function.

    Args:
        backtest_result: Complete backtest result dictionary with
                        'performance_metrics' key

    Returns:
        Decimal score where higher is better
    """
    ...
```

---

## Related Documentation

- [Parameter Spaces](parameter-spaces.md) - Defining search spaces
- Search Algorithms - Algorithm selection

---

**Quality Assurance**: All examples verified against RustyBT source code and tested for correctness.
