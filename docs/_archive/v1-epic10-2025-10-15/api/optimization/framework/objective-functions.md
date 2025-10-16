# Objective Functions

Designing effective objective functions for strategy optimization.

## Overview

The objective function evaluates parameter configurations by running backtests and calculating performance metrics. A well-designed objective function is crucial for finding robust, generalizable parameters.

## Basic Structure

### Minimal Example

```python
from decimal import Decimal

def objective_function(params):
    """
    Evaluate strategy with given parameters.

    Args:
        params: Dict of parameter values

    Returns:
        Decimal: Performance score (higher is better)
    """
    result = run_backtest(
        strategy=MyStrategy(**params),
        start_date='2020-01-01',
        end_date='2023-12-31'
    )

    sharpe_ratio = calculate_sharpe(result)
    return Decimal(str(sharpe_ratio))
```

### Complete Example

## Metric Selection

### Common Metrics

| Metric | Use When | Pros | Cons |
|--------|----------|------|------|
| **Sharpe Ratio** | General purpose | Risk-adjusted, widely understood | Assumes normal returns |
| **Sortino Ratio** | Downside risk focus | Penalizes only negative volatility | Requires more data |
| **Calmar Ratio** | Drawdown averse | Focuses on worst-case | Sensitive to single events |
| **Omega Ratio** | Non-normal returns | No distribution assumptions | Computationally expensive |
| **Information Ratio** | Benchmark relative | Measures skill vs benchmark | Requires good benchmark |

### Sharpe Ratio

Most common choice for optimization:

```python
def sharpe_objective(params):
    result = run_backtest(params)

    returns = result['returns']
    mean_return = returns.mean() * 252  # Annualized
    std_return = returns.std() * np.sqrt(252)  # Annualized

    if std_return == 0:
        return Decimal('0')

    sharpe = mean_return / std_return
    return Decimal(str(sharpe))
```

**Advantages**:
- Risk-adjusted performance
- Widely understood
- Easy to calculate

**Limitations**:
- Penalizes upside volatility equally
- Assumes returns are normally distributed
- Sensitive to outliers

### Sortino Ratio

Focuses on downside risk:

```python
def sortino_objective(params):
    result = run_backtest(params)

    returns = result['returns']
    mean_return = returns.mean() * 252

    # Downside deviation (only negative returns)
    downside_returns = returns[returns < 0]
    downside_dev = downside_returns.std() * np.sqrt(252)

    if downside_dev == 0:
        return Decimal('0')

    sortino = mean_return / downside_dev
    return Decimal(str(sortino))
```

**Advantages**:
- Only penalizes downside volatility
- Better for asymmetric return distributions
- Aligns with investor risk perception

**Limitations**:
- Requires more data for stability
- Less widely used than Sharpe

### Calmar Ratio

Return divided by maximum drawdown:

```python
def calmar_objective(params):
    result = run_backtest(params)

    annual_return = result['annual_return']
    max_drawdown = abs(result['max_drawdown'])

    if max_drawdown == 0:
        return Decimal('0')

    calmar = annual_return / max_drawdown
    return Decimal(str(calmar))
```

**Advantages**:
- Focuses on worst-case drawdown
- Intuitive interpretation
- Good for risk-averse strategies

**Limitations**:
- Dominated by single worst drawdown
- Can be unstable with limited data

## Composite Objectives

### Weighted Combination

Combine multiple metrics:

```python
def composite_objective(params):
    result = run_backtest(params)

    sharpe = calculate_sharpe(result)
    sortino = calculate_sortino(result)
    max_dd = abs(calculate_max_drawdown(result))

    # Weighted combination
    score = (
        0.50 * sharpe +
        0.30 * sortino -
        0.20 * max_dd  # Penalty for large drawdowns
    )

    return Decimal(str(score))
```

**Advantages**:
- Captures multiple objectives
- Customizable to strategy goals
- More robust than single metric

**Limitations**:
- Weight selection is subjective
- Can obscure individual metric performance

### Constrained Optimization

Optimize one metric subject to constraints:

```python
def constrained_objective(params):
    result = run_backtest(params)

    sharpe = calculate_sharpe(result)
    max_dd = abs(calculate_max_drawdown(result))
    num_trades = result['num_trades']

    # Hard constraints
    if max_dd > 0.30:  # Max 30% drawdown
        return Decimal('-Infinity')

    if num_trades < 30:  # Minimum trade count
        return Decimal('-Infinity')

    # Optimize Sharpe subject to constraints
    return Decimal(str(sharpe))
```

**Advantages**:
- Clear constraint violations
- Focuses optimization on primary metric
- Easy to interpret

**Limitations**:
- Binary constraint evaluation
- May exclude near-constraint solutions

## Practical Considerations

### Minimum Trade Count

Ensure statistical significance:

```python
def min_trade_objective(params):
    result = run_backtest(params)

    # Require minimum 30 trades for significance
    if result['num_trades'] < 30:
        return Decimal('-Infinity')

    return calculate_sharpe(result)
```

**Rule of thumb**:
- <30 trades: High risk of overfitting
- 30-100 trades: Acceptable
- >100 trades: Good statistical power

### Handling Errors

Graceful error handling prevents optimization failures:

```python
def robust_objective(params):
    try:
        result = run_backtest(params)
        return calculate_metric(result)
    except InsufficientDataError:
        # Parameters require more data than available
        return Decimal('-Infinity')
    except InvalidParameterError as e:
        # Invalid parameter combination
        logger.warning(f"Invalid params: {e}")
        return Decimal('-Infinity')
    except Exception as e:
        # Unexpected error
        logger.error(f"Backtest failed: {e}")
        return Decimal('-Infinity')
```

### Normalization

Normalize metrics to comparable scales:

```python
def normalized_objective(params):
    result = run_backtest(params)

    # Raw metrics
    sharpe = calculate_sharpe(result)
    max_dd = calculate_max_drawdown(result)

    # Normalize to [0, 1] scale
    sharpe_norm = max(0, min(1, sharpe / 3.0))  # Assume max Sharpe ~3
    dd_norm = 1 - abs(max_dd)  # Invert drawdown (lower is better)

    # Combine normalized metrics
    score = 0.7 * sharpe_norm + 0.3 * dd_norm
    return Decimal(str(score))
```

## Anti-Patterns

### ❌ Data Snooping

Don't use future data:

```python
# WRONG: Uses full dataset for metric calculation
def snooping_objective(params):
    full_result = run_backtest(params, '2010-01-01', '2023-12-31')
    # This includes future data!
    return calculate_sharpe(full_result)

# RIGHT: Use only training period
def proper_objective(params, train_start, train_end):
    result = run_backtest(params, train_start, train_end)
    return calculate_sharpe(result)
```

### ❌ Ignoring Transaction Costs

Always include realistic costs:

```python
# WRONG: No transaction costs
def no_cost_objective(params):
    result = run_backtest(params, commission=0, slippage=0)
    return calculate_sharpe(result)

# RIGHT: Realistic costs
def realistic_objective(params):
    result = run_backtest(
        params,
        commission=PerShareCommission(0.01),  # $0.01/share
        slippage=FixedSlippage(0.001)  # 10 bps
    )
    return calculate_sharpe(result)
```

### ❌ Optimizing on Total Return

Don't optimize absolute returns without risk adjustment:

```python
# WRONG: Ignores risk
def return_only_objective(params):
    result = run_backtest(params)
    return result['total_return']  # Can be arbitrarily high with leverage!

# RIGHT: Risk-adjusted return
def risk_adjusted_objective(params):
    result = run_backtest(params)
    return calculate_sharpe(result)  # Adjusts for volatility
```

### ❌ Single-Period Optimization

Don't optimize on single period:

```python
# WRONG: Single test period
def single_period_objective(params):
    result = run_backtest(params, '2020-01-01', '2020-12-31')
    return calculate_sharpe(result)  # Might just be lucky!

# RIGHT: Multiple periods or walk-forward
def robust_objective(params):
    sharpes = []
    for year in range(2015, 2024):
        result = run_backtest(params, f'{year}-01-01', f'{year}-12-31')
        sharpes.append(calculate_sharpe(result))

    # Return average or minimum
    return Decimal(str(min(sharpes)))  # Pessimistic: worst year
```

## Advanced Techniques

### Multi-Objective Optimization

Optimize multiple objectives simultaneously:

### Time-Weighted Objectives

Weight recent performance more heavily:

```python
def time_weighted_objective(params):
    """Recent performance weighted more heavily."""
    result = run_backtest(params)

    # Split into periods
    periods = [
        ('2015-01-01', '2017-12-31', 0.1),  # Early: 10% weight
        ('2018-01-01', '2020-12-31', 0.3),  # Mid: 30% weight
        ('2021-01-01', '2023-12-31', 0.6),  # Recent: 60% weight
    ]

    weighted_sharpe = Decimal('0')
    for start, end, weight in periods:
        period_result = result.loc[start:end]
        sharpe = calculate_sharpe(period_result)
        weighted_sharpe += Decimal(str(weight)) * sharpe

    return weighted_sharpe
```

### Regime-Specific Objectives

Optimize for specific market conditions:

```python
def regime_objective(params):
    """Optimize for performance in high-volatility regimes."""
    result = run_backtest(params)

    # Identify high-volatility periods
    rolling_vol = result['returns'].rolling(20).std()
    high_vol_mask = rolling_vol > rolling_vol.median()

    # Calculate performance in high-vol periods only
    high_vol_returns = result['returns'][high_vol_mask]
    sharpe = calculate_sharpe(high_vol_returns)

    return Decimal(str(sharpe))
```

## Testing Objective Functions

### Validate Monotonicity

Ensure better strategies score higher:

```python
def test_objective_monotonicity():
    """Better parameters should score higher."""
    # Known good parameters
    good_params = {'lookback': 50, 'threshold': 0.05}
    good_score = objective_function(good_params)

    # Known poor parameters
    poor_params = {'lookback': 5, 'threshold': 0.50}
    poor_score = objective_function(poor_params)

    assert good_score > poor_score
```

### Validate Sensitivity

Ensure objective responds to parameter changes:

```python
def test_objective_sensitivity():
    """Objective should change with parameters."""
    base_params = {'lookback': 50}
    base_score = objective_function(base_params)

    varied_params = {'lookback': 100}
    varied_score = objective_function(varied_params)

    assert base_score != varied_score  # Should be different
```

### Validate Stability

Ensure consistent results with same parameters:

```python
def test_objective_stability():
    """Same parameters should give same score."""
    params = {'lookback': 50, 'threshold': 0.05}

    score1 = objective_function(params)
    score2 = objective_function(params)

    assert score1 == score2  # Deterministic
```

## See Also

- [Parameter Spaces](parameter-spaces.md)
- Architecture
- [Overfitting Prevention](../best-practices/overfitting-prevention.md)
- [Walk-Forward Validation](../walk-forward/framework.md)
