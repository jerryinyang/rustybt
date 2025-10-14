# Walk-Forward Window Sizing

Strategies for sizing training and testing windows in walk-forward optimization.

## Overview

Window sizing is critical for walk-forward optimization effectiveness. Windows must be large enough for statistical significance but small enough to capture regime changes.

## Window Types

### Rolling Windows

Fixed-size windows that move forward through time.

```python
# Example: 1-year training, 3-month testing
train_days = 252
test_days = 63

# Window 1: Train [0:252], Test [252:315]
# Window 2: Train [63:315], Test [315:378]
# Window 3: Train [126:378], Test [378:441]
```

**Advantages**:
- Recent data weighted more heavily
- Adapts to regime changes
- Fixed computational cost per window

**Disadvantages**:
- Less data per optimization
- May discard useful historical patterns

### Anchored Windows

Growing windows anchored at start date.

```python
# Example: Growing training window
train_start = 0
test_days = 63

# Window 1: Train [0:252], Test [252:315]
# Window 2: Train [0:315], Test [315:378]
# Window 3: Train [0:378], Test [378:441]
```

**Advantages**:
- More data = better optimization
- Captures long-term patterns
- More stable parameters

**Disadvantages**:
- Old data may be irrelevant
- Computational cost increases
- Less adaptive to regime changes

## Sizing Guidelines

### Training Window Size

**Minimum requirements**:
```python
# Based on trades
min_trades = 30  # Per parameter
n_parameters = 3
min_window_trades = min_trades * n_parameters  # 90 trades

# Based on days (assuming daily rebalancing)
min_trading_days = 90  # ~4 months

# Recommended
recommended_train_days = 252  # 1 year
```

**By strategy frequency**:
- High-frequency: 1-3 months
- Daily: 6-12 months
- Weekly: 1-3 years
- Monthly: 3-5 years

### Testing Window Size

**Practical guidelines**:
```python
# Short enough to stay relevant
test_days = train_days / 4  # 25% of training

# Long enough for significance
min_test_trades = 10
min_test_days = 21  # ~1 month

# Typical values
# Daily strategies: 21-63 days (1-3 months)
# Weekly strategies: 63-126 days (3-6 months)
```

### Reoptimization Frequency

How often to reoptimize parameters:

```python
# Conservative: Same as test period
reopt_frequency = test_days

# Aggressive: More frequent
reopt_frequency = test_days / 2

# Very conservative: Less frequent
reopt_frequency = test_days * 2
```

**Trade-offs**:
- More frequent = adaptive but higher overfitting risk
- Less frequent = stable but may miss regime changes

## Complete Example

```python
from rustybt.optimization import WalkForwardOptimizer

# Conservative: Long training, infrequent reoptimization
conservative = WalkForwardOptimizer(
    objective_function=run_backtest,
    parameter_space=param_space,
    train_period_days=504,  # 2 years
    test_period_days=126,   # 6 months
    reoptimize_frequency_days=126,  # Reoptimize every test period
    anchored=True  # Use all historical data
)

# Aggressive: Shorter training, frequent reoptimization
aggressive = WalkForwardOptimizer(
    objective_function=run_backtest,
    parameter_space=param_space,
    train_period_days=126,  # 6 months
    test_period_days=21,    # 1 month
    reoptimize_frequency_days=21,   # Reoptimize every month
    anchored=False  # Rolling window
)

# Balanced: Moderate approach
balanced = WalkForwardOptimizer(
    objective_function=run_backtest,
    parameter_space=param_space,
    train_period_days=252,  # 1 year
    test_period_days=63,    # 3 months
    reoptimize_frequency_days=63,   # Reoptimize every 3 months
    anchored=False
)
```

## See Also

- [Walk-Forward Framework](framework.md)
- [Out-of-Sample Validation](validation.md)
- [Overfitting Prevention](../best-practices/overfitting-prevention.md)
