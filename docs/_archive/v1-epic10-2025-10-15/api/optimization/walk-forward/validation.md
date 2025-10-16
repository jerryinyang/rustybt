# Out-of-Sample Validation

Techniques for validating strategy parameters on unseen data.

## Overview

Out-of-sample (OOS) validation tests whether optimized parameters generalize to new data. This is the gold standard for preventing overfitting.

## Validation Approaches

### Simple Train/Test Split

Basic approach: optimize on training data, test on held-out data.

```python
# Split data
train_start = '2018-01-01'
train_end = '2021-12-31'
test_start = '2022-01-01'
test_end = '2023-12-31'

# Optimize on training data
optimizer = Optimizer(...)
result = optimizer.optimize(start=train_start, end=train_end)
best_params = result.best_params

# Test on out-of-sample data (DO ONLY ONCE!)
oos_result = run_backtest(best_params, start=test_start, end=test_end)
oos_sharpe = calculate_sharpe(oos_result)
```

**Critical**: Only test on OOS data once! Repeated testing = data snooping.

### Walk-Forward Validation

Multiple train/test windows through time.

```python
from rustybt.optimization import WalkForwardOptimizer

wf = WalkForwardOptimizer(
    objective_function=run_backtest,
    parameter_space=param_space,
    train_period_days=252,
    test_period_days=63,
    start_date='2018-01-01',
    end_date='2023-12-31'
)

result = wf.optimize()

# Compare in-sample vs out-of-sample
print(f"In-sample Sharpe: {result.in_sample_metrics['sharpe']:.3f}")
print(f"Out-of-sample Sharpe: {result.out_of_sample_metrics['sharpe']:.3f}")
print(f"Degradation: {result.degradation:.1%}")
```

### K-Fold Cross-Validation

Multiple non-overlapping test periods.

```python
def k_fold_validation(params, k=5):
    """K-fold cross-validation for time series."""
    start = pd.Timestamp('2018-01-01')
    end = pd.Timestamp('2023-12-31')
    total_days = (end - start).days
    fold_size = total_days // k

    scores = []
    for i in range(k):
        # Create train/test split
        test_start = start + pd.Timedelta(days=i * fold_size)
        test_end = test_start + pd.Timedelta(days=fold_size)

        # Train on all data except test fold
        train_data = get_data_excluding(test_start, test_end)

        # Test on fold
        result = run_backtest(params, test_start, test_end)
        scores.append(calculate_sharpe(result))

    return np.mean(scores), np.std(scores)
```

**Note**: For time series, respect temporal order - don't train on future data.

## Validation Metrics

### Performance Degradation

How much performance drops from in-sample to out-of-sample:

```python
degradation = 1 - (oos_sharpe / is_sharpe)

# Interpretation:
# < 20%: Excellent generalization
# 20-30%: Good generalization
# 30-50%: Acceptable
# > 50%: Likely overfit
```

### Consistency Metrics

```python
# Sharpe ratio consistency across periods
period_sharpes = [calculate_sharpe(period) for period in oos_periods]

# Coefficient of variation
consistency = np.std(period_sharpes) / np.mean(period_sharpes)

# Interpretation:
# < 0.30: Consistent
# 0.30-0.50: Moderate consistency
# > 0.50: Inconsistent
```

### Minimum Performance Threshold

```python
# Set minimum acceptable OOS performance
min_oos_sharpe = 1.0

if oos_sharpe >= min_oos_sharpe and degradation < 0.30:
    print("✓ Parameters validated for production")
else:
    print("✗ Parameters failed validation")
```

## Best Practices

### 1. Reserve Data

Always reserve final test data:

```python
# NEVER touch this data during optimization
reserved_start = '2024-01-01'
reserved_end = '2024-12-31'

# Optimize on everything before 2024
optimizer = Optimizer(..., end='2023-12-31')

# Final validation (do only once!)
final_test = run_backtest(best_params, reserved_start, reserved_end)
```

### 2. Multiple Time Periods

Test across different market regimes:

```python
# Test in different market conditions
bull_period = ('2019-01-01', '2021-12-31')
bear_period = ('2022-01-01', '2022-12-31')
sideways_period = ('2015-01-01', '2016-12-31')

for period_name, (start, end) in [('bull', bull_period), ...]:
    result = run_backtest(best_params, start, end)
    print(f"{period_name}: Sharpe = {calculate_sharpe(result):.2f}")
```

### 3. Statistical Significance

Ensure sufficient data:

```python
# Need enough trades for significance
oos_trades = count_trades(oos_result)

if oos_trades < 30:
    print("⚠ WARNING: Too few trades for statistical significance")
elif oos_trades < 100:
    print("⚠ CAUTION: Limited statistical power")
else:
    print("✓ Sufficient trades for validation")
```

## Common Pitfalls

### ❌ Data Snooping

```python
# WRONG: Testing multiple times on same OOS data
for params in candidate_params:
    oos_score = test_on_oos_data(params)  # Snooping!
    if oos_score > best:
        best = params

# RIGHT: Single final test
best_params = optimize_on_training_data()
final_score = test_on_oos_data(best_params)  # Once only
```

### ❌ Look-Ahead Bias

```python
# WRONG: Using future data in training
train_data = get_data('2018-01-01', '2021-12-31')
test_data = get_data('2020-01-01', '2020-12-31')  # Overlaps!

# RIGHT: Strict temporal separation
train_data = get_data('2018-01-01', '2019-12-31')
test_data = get_data('2020-01-01', '2020-12-31')  # No overlap
```

### ❌ Ignoring Transaction Costs

```python
# WRONG: Optimizing without costs
is_result = run_backtest(params, commission=0)

# RIGHT: Include realistic costs
is_result = run_backtest(params, commission=PerShareCommission(0.01))
```

## Validation Checklist

Before deploying parameters:

- [ ] Optimized on training data only
- [ ] Tested on true out-of-sample data
- [ ] Degradation < 30%
- [ ] OOS Sharpe > minimum threshold
- [ ] Tested across multiple market regimes
- [ ] Sufficient trades (>30) in OOS period
- [ ] Transaction costs included
- [ ] No data snooping violations
- [ ] Parameters make intuitive sense
- [ ] Results stable across nearby parameter values

## See Also

- [Walk-Forward Framework](framework.md)
- [Window Sizing](windows.md)
- [Overfitting Prevention](../best-practices/overfitting-prevention.md)
- [Monte Carlo Testing](../monte-carlo/stability-testing.md)
