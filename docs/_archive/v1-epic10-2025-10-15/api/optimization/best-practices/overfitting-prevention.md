# Overfitting Prevention

Critical techniques for avoiding overfitted parameters that won't generalize to live trading.

## The Overfitting Problem

**Overfitting** occurs when optimized parameters perform well on historical data but fail in live trading because they captured noise rather than signal.

### Example: Overfitted Strategy

```python
# Optimized parameters work perfectly on 2020-2023 data
optimal_params = {
    'ma_short': 37,  # Oddly specific
    'ma_long': 183,  # Not round number
    'threshold': 0.04271  # Too precise
}

# In-sample Sharpe: 3.5 (amazing!)
# Out-of-sample Sharpe: 0.2 (terrible!)
# Live trading: Loses money
```

**Why?** Parameters fit historical noise, not repeatable patterns.

## Warning Signs of Overfitting

### 1. Large Degradation

Significant drop from in-sample to out-of-sample:

```python
in_sample_sharpe = 3.0
out_of_sample_sharpe = 1.0

degradation = 1 - (out_of_sample_sharpe / in_sample_sharpe)
# = 1 - (1.0 / 3.0) = 0.67 = 67% degradation

# WARNING: >40% degradation suggests overfitting
```

### 2. Too Many Parameters

More parameters = higher overfitting risk:

```python
# High risk: 6 parameters on 150 trades = 25 trades per parameter
param_space = ParameterSpace(parameters=[
    DiscreteParameter('p1', ...),
    DiscreteParameter('p2', ...),
    DiscreteParameter('p3', ...),
    DiscreteParameter('p4', ...),
    DiscreteParameter('p5', ...),
    DiscreteParameter('p6', ...)
])
```

**Rule of thumb**: Need 30-50 trades per parameter for robustness.

### 3. Unstable Parameters

Parameters change dramatically between periods:

```python
# Window 1 best params: {'lookback': 20}
# Window 2 best params: {'lookback': 95}
# Window 3 best params: {'lookback': 15}

# Parameter stability: 80% variation
# WARNING: >50% suggests parameters capturing noise
```

### 4. Too-Precise Values

Unreasonably specific parameters:

```python
# Overfit: Too precise
{'threshold': 0.0427183, 'lookback': 47}

# Robust: Round values
{'threshold': 0.04, 'lookback': 50}
```

### 5. Unrealistic Performance

Too good to be true:

```python
# WARNING SIGNS:
sharpe_ratio = 5.0  # Rarely achievable
win_rate = 0.92  # Too high
max_drawdown = -0.03  # Too small
```

## Prevention Techniques

### 1. Walk-Forward Optimization

**Most important technique!**

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

# Only trust out-of-sample performance!
if result.degradation < 0.30:  # <30% degradation
    print("Parameters likely robust")
else:
    print("WARNING: High overfitting risk")
```

### 2. Limit Parameters

Fewer parameters = less overfitting:

```python
# GOOD: 2-3 parameters
param_space = ParameterSpace(parameters=[
    DiscreteParameter('ma_short', 10, 50, step=5),
    DiscreteParameter('ma_long', 50, 200, step=25)
])

# BAD: 6+ parameters
# ... much higher overfitting risk
```

### 3. Use Coarse Granularity

Don't over-optimize:

```python
# BAD: Too fine
DiscreteParameter('lookback', 10, 100, step=1)  # 91 values!

# GOOD: Coarse steps
DiscreteParameter('lookback', 10, 100, step=10)  # 10 values

# BEST: Even coarser for initial search
DiscreteParameter('lookback', 10, 100, step=20)  # 5 values
```

### 4. Minimum Trade Count

Ensure statistical significance:

```python
def objective_with_min_trades(params):
    result = run_backtest(params)

    # Require minimum 30 trades
    if result['num_trades'] < 30:
        return Decimal('-Infinity')

    return calculate_sharpe(result)
```

**Guidelines**:
- <30 trades: High risk
- 30-100 trades: Acceptable
- >100 trades: Good

### 5. Monte Carlo Robustness Testing

Test parameter stability with noise:

```python
from rustybt.optimization import MonteCarloSimulator

mc = MonteCarloSimulator(
    objective_function=run_backtest,
    base_params=best_params,
    n_simulations=1000
)

result = mc.run(noise_std=0.1)  # Add 10% noise

# Robust if performance stable with noise
if result.std_score / result.mean_score < 0.3:
    print("Parameters are robust to noise")
else:
    print("WARNING: Unstable parameters")
```

### 6. Cross-Validation

Validate on multiple time periods:

```python
def cross_validate_params(params, n_folds=5):
    """K-fold cross-validation on time series."""
    period_length = (end_date - start_date) / n_folds

    scores = []
    for i in range(n_folds):
        fold_start = start_date + i * period_length
        fold_end = fold_start + period_length

        result = run_backtest(params, fold_start, fold_end)
        scores.append(calculate_sharpe(result))

    # Return mean and stability
    mean_score = sum(scores) / len(scores)
    std_score = np.std(scores)

    return mean_score, std_score

# Accept only if stable across periods
mean, std = cross_validate_params(best_params)
if std / mean < 0.5:  # Coefficient of variation <50%
    print("Parameters stable across periods")
```

### 7. Simplicity Bias

Prefer simpler strategies when performance is similar:

```python
# Compare two strategies with similar performance
strategy_a = {'params': 2, 'sharpe': 1.8}
strategy_b = {'params': 5, 'sharpe': 1.9}

# Prefer strategy_a (simpler, similar performance)
if strategy_b['sharpe'] - strategy_a['sharpe'] < 0.3:
    print("Choose simpler strategy (A)")
```

**Occam's Razor**: Simpler explanations are more likely correct.

### 8. Include Transaction Costs

Always use realistic costs:

```python
from rustybt.finance.commission import PerShareCommission
from rustybt.finance.slippage import FixedSlippage

# WRONG: No costs
result = run_backtest(params)  # Overly optimistic

# RIGHT: Realistic costs
result = run_backtest(
    params,
    commission=PerShareCommission(cost=0.01),  # $0.01/share
    slippage=FixedSlippage(spread=0.001)  # 10 bps
)
```

### 9. Out-of-Sample Reserve

Hold out recent data for final validation:

```python
# Split data
training_period = ('2015-01-01', '2022-12-31')  # Optimize here
oos_reserve = ('2023-01-01', '2023-12-31')  # Final test (don't touch!)

# Step 1: Optimize on training period
wf = WalkForwardOptimizer(..., end_date='2022-12-31')
result = wf.optimize()
best_params = result.best_params

# Step 2: Final validation on reserved data (do only ONCE!)
final_result = run_backtest(best_params, '2023-01-01', '2023-12-31')
final_sharpe = calculate_sharpe(final_result)

# If final_sharpe << optimized_sharpe, likely overfitting
```

### 10. Consensus Parameters

Average parameters across windows:

```python
def consensus_parameters(walk_forward_result):
    """Average optimal parameters across windows."""
    param_values = {}

    for window in walk_forward_result.per_window_results:
        for param, value in window.best_params.items():
            if param not in param_values:
                param_values[param] = []
            param_values[param].append(value)

    # Return median (robust to outliers)
    consensus = {}
    for param, values in param_values.items():
        consensus[param] = np.median(values)

    return consensus

# Use consensus parameters instead of single-window best
consensus_params = consensus_parameters(wf_result)
```

## Validation Checklist

Before deploying optimized parameters, verify:

- [ ] **Walk-forward tested** with <30% degradation
- [ ] **Out-of-sample Sharpe** >1.0
- [ ] **Minimum 30 trades** in each test period
- [ ] **Parameter stability** <40% variation across windows
- [ ] **Monte Carlo tested** with <30% performance std/mean
- [ ] **Transaction costs** included in optimization
- [ ] **Final validation** on reserved out-of-sample data
- [ ] **Realistic performance** (Sharpe <3.0, win rate <70%)
- [ ] **Simple strategy** (≤5 parameters)
- [ ] **Round parameter values** (not overly precise)

## Case Study: Detecting Overfitting

### Scenario

Optimized moving average crossover strategy:

```python
# In-sample results (2018-2021):
in_sample_sharpe = 3.2
in_sample_return = 0.45
in_sample_max_dd = -0.08

# Parameters:
params = {
    'ma_short': 37,  # Oddly specific
    'ma_long': 183,  # Not round
    'threshold': 0.0427  # Too precise
}
```

### Red Flags

1. ❌ **Unrealistic Sharpe** (3.2 is very high)
2. ❌ **Oddly specific parameters** (37, 183, 0.0427)
3. ❌ **Too small drawdown** (-8% is suspiciously low)

### Proper Validation

```python
# Walk-forward test
wf = WalkForwardOptimizer(...)
result = wf.optimize()

# Out-of-sample results:
oos_sharpe = 0.9  # Much lower!
degradation = 1 - (0.9 / 3.2) = 0.72  # 72% degradation!

# Parameter stability:
# Window 1: ma_short=37, ma_long=183
# Window 2: ma_short=15, ma_long=75
# Window 3: ma_short=45, ma_long=195
# High instability!
```

### Conclusion

Strategy is **overfit**. Parameters captured historical noise, not robust signal.

### Fix: Simplify and Coarsen

```python
# Use coarser parameter space
param_space = ParameterSpace(parameters=[
    DiscreteParameter('ma_short', 10, 50, step=10),  # [10, 20, 30, 40, 50]
    DiscreteParameter('ma_long', 50, 200, step=50)   # [50, 100, 150, 200]
])

# Re-optimize with walk-forward
wf = WalkForwardOptimizer(...)
result = wf.optimize()

# New results:
# In-sample Sharpe: 1.8 (more realistic)
# Out-of-sample Sharpe: 1.4 (closer to in-sample)
# Degradation: 22% (acceptable!)
# Parameters: ma_short=30, ma_long=150 (round values)
```

Much better! More likely to work in live trading.

## Summary

### DO

✅ Use walk-forward optimization
✅ Limit to 2-5 parameters
✅ Require minimum 30 trades per test period
✅ Use coarse parameter steps
✅ Include realistic transaction costs
✅ Reserve out-of-sample data for final validation
✅ Test parameter robustness with Monte Carlo
✅ Prefer simpler strategies

### DON'T

❌ Trust single-period optimization
❌ Use >5 parameters without extensive validation
❌ Accept >40% degradation
❌ Optimize on total data
❌ Use overly precise parameter values
❌ Ignore transaction costs
❌ Deploy without walk-forward testing
❌ Trust unrealistic performance (Sharpe >3.0)

## See Also

- [Walk-Forward Framework](../walk-forward/framework.md)
- [Monte Carlo Testing](../monte-carlo/stability-testing.md)
- Validation Techniques (Coming soon)
- [Parameter Spaces](../framework/parameter-spaces.md)
