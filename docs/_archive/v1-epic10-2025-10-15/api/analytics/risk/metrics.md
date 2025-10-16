# Risk Metrics

Comprehensive risk analysis metrics for strategy evaluation.

## Overview

Risk metrics quantify the risk characteristics of trading strategies, helping traders understand downside exposure, volatility, and tail risks.

## Core Risk Metrics

### Volatility

Annualized standard deviation of returns:

```python
from rustybt.analytics import RiskAnalytics

risk = RiskAnalytics(backtest_result)
metrics = risk.calculate_risk_metrics()

volatility = metrics['volatility']  # Annualized
print(f"Volatility: {volatility:.2%}")
```

**Interpretation**:
- <10%: Low volatility
- 10-20%: Moderate volatility
- >20%: High volatility

### Sharpe Ratio

Risk-adjusted return (excess return / volatility):

```python
sharpe = metrics['sharpe_ratio']
print(f"Sharpe Ratio: {sharpe:.2f}")
```

**Interpretation**:
- <1.0: Poor risk-adjusted returns
- 1.0-2.0: Good
- 2.0-3.0: Excellent
- >3.0: Exceptional (verify not overfitted)

### Sortino Ratio

Downside risk-adjusted return:

```python
sortino = metrics['sortino_ratio']
print(f"Sortino Ratio: {sortino:.2f}")
```

**Advantages** over Sharpe:
- Only penalizes downside volatility
- Better for asymmetric return distributions

### Maximum Drawdown

Largest peak-to-trough decline:

```python
max_dd = metrics['max_drawdown']
print(f"Max Drawdown: {max_dd:.2%}")
```

**Interpretation**:
- <10%: Excellent
- 10-20%: Good
- 20-30%: Acceptable
- >30%: High risk

### Value at Risk (VaR)

Potential loss at confidence level:

```python
var_95 = risk.calculate_var(confidence_level=0.95)
print(f"VaR (95%): {var_95:.2%}")
```

**Interpretation**: Expected to lose more than VaR only 5% of the time.

### Conditional VaR (CVaR)

Expected loss when VaR is exceeded:

```python
cvar_95 = risk.calculate_cvar(confidence_level=0.95)
print(f"CVaR (95%): {cvar_95:.2%}")
```

**Use case**: Tail risk assessment.

## Complete Example

```python
from rustybt.analytics import RiskAnalytics
from rustybt.utils.run_algo import run_algorithm
import pandas as pd

# Run backtest
result = run_algorithm(
    algorithm_class=MyStrategy,
    start=pd.Timestamp('2020-01-01'),
    end=pd.Timestamp('2023-12-31'),
    capital_base=100000
)

# Create risk analytics
risk = RiskAnalytics(
    backtest_result=result,
    benchmark_returns=spy_returns,  # Optional benchmark
    confidence_level=0.95
)

# Calculate all metrics
metrics = risk.calculate_risk_metrics()

# Print comprehensive risk report
print("=== Risk Metrics ===\n")

print(f"Volatility: {metrics['volatility']:.2%}")
print(f"Downside Deviation: {metrics['downside_deviation']:.2%}")
print(f"\nRisk-Adjusted Returns:")
print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
print(f"Sortino Ratio: {metrics['sortino_ratio']:.2f}")
print(f"Calmar Ratio: {metrics['calmar_ratio']:.2f}")

print(f"\nDrawdown Analysis:")
print(f"Max Drawdown: {metrics['max_drawdown']:.2%}")
print(f"Max DD Duration: {metrics['max_drawdown_duration']} days")

print(f"\nTail Risk:")
print(f"VaR (95%): {metrics['value_at_risk']:.2%}")
print(f"CVaR (95%): {metrics['conditional_var']:.2%}")

if 'beta' in metrics:
    print(f"\nMarket Exposure:")
    print(f"Beta: {metrics['beta']:.2f}")
    print(f"Correlation: {metrics['correlation']:.2f}")
```

## See Also

- [VaR & CVaR](var-cvar.md)
- [Drawdown Analysis](drawdown.md)
- [Main Analytics API](../../analytics-api.md)
