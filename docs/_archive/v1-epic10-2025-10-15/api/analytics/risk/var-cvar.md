# Value at Risk (VaR) and Conditional VaR (CVaR)

Tail risk metrics for understanding potential losses.

## Overview

VaR and CVaR quantify downside risk by measuring potential losses at specified confidence levels. These are essential risk management tools used throughout finance.

## Value at Risk (VaR)

### Definition

VaR answers: "What is the maximum loss I can expect with X% confidence over a given time period?"

**Interpretation**: At 95% confidence, you expect to lose no more than VaR 95% of the time.

### Calculation Methods

#### Historical VaR

Based on actual historical returns:

```python
from rustybt.analytics import RiskAnalytics
import numpy as np

risk = RiskAnalytics(backtest_result)

# 95% VaR using historical method
var_95 = risk.calculate_var(confidence_level=0.95, method='historical')
print(f"VaR (95%): {var_95:.2%}")
```

**How it works**:
1. Sort historical returns
2. Find 5th percentile
3. VaR = negative of that percentile

```python
def historical_var(returns, confidence_level=0.95):
    """Calculate historical VaR."""
    # Sort returns (worst to best)
    sorted_returns = np.sort(returns)

    # Find percentile
    index = int((1 - confidence_level) * len(returns))
    var = -sorted_returns[index]

    return var

# Example
returns = backtest_result['returns']
var_95 = historical_var(returns, 0.95)
```

#### Parametric VaR

Assumes returns are normally distributed:

```python
var_95 = risk.calculate_var(confidence_level=0.95, method='parametric')
```

**How it works**:
```python
def parametric_var(returns, confidence_level=0.95):
    """Calculate parametric VaR assuming normality."""
    from scipy import stats

    mean = returns.mean()
    std = returns.std()

    # Z-score for confidence level
    z = stats.norm.ppf(1 - confidence_level)

    # VaR = -(mean + z * std)
    var = -(mean + z * std)

    return var
```

**Assumption**: Returns are normally distributed (often violated in finance).

### VaR Example

```python
from rustybt.analytics import RiskAnalytics

# Calculate VaR at multiple confidence levels
risk = RiskAnalytics(backtest_result)

for confidence in [0.90, 0.95, 0.99]:
    var = risk.calculate_var(confidence_level=confidence)
    print(f"VaR ({confidence:.0%}): {var:.2%}")

# Example output:
# VaR (90%): -2.3%  (expect to lose more than 2.3% only 10% of the time)
# VaR (95%): -3.1%  (expect to lose more than 3.1% only 5% of the time)
# VaR (99%): -4.5%  (expect to lose more than 4.5% only 1% of the time)
```

## Conditional VaR (CVaR)

### Definition

CVaR answers: "If VaR is exceeded, how bad will the loss be on average?"

Also called **Expected Shortfall** (ES) or **Average VaR**.

**Interpretation**: CVaR is the average loss in the worst X% of cases.

### Calculation

```python
# Calculate CVaR (Expected Shortfall)
cvar_95 = risk.calculate_cvar(confidence_level=0.95)
print(f"CVaR (95%): {cvar_95:.2%}")
```

**Implementation**:
```python
def calculate_cvar(returns, confidence_level=0.95):
    """Calculate Conditional VaR (Expected Shortfall)."""
    # Sort returns
    sorted_returns = np.sort(returns)

    # Find VaR cutoff
    cutoff_index = int((1 - confidence_level) * len(returns))

    # CVaR = average of returns worse than VaR
    cvar = -np.mean(sorted_returns[:cutoff_index])

    return cvar
```

### CVaR Example

```python
# Compare VaR and CVaR
var_95 = risk.calculate_var(confidence_level=0.95)
cvar_95 = risk.calculate_cvar(confidence_level=0.95)

print(f"VaR (95%): {var_95:.2%}")
print(f"CVaR (95%): {cvar_95:.2%}")

# Example output:
# VaR (95%): -3.1%   (5% chance of losing more than this)
# CVaR (95%): -4.8%  (average loss when VaR is exceeded)
```

**Key insight**: CVaR is always >= VaR, telling you about tail risk.

## Comparison

### VaR vs CVaR

| Aspect | VaR | CVaR |
|--------|-----|------|
| **Question** | "How bad could it get?" | "How bad is it when it's bad?" |
| **Measures** | Threshold loss | Average tail loss |
| **Properties** | Not coherent risk measure | Coherent risk measure |
| **Sensitivity** | Ignores tail shape | Captures tail risk |
| **Usefulness** | Regulatory reporting | Risk management |

### Coherent Risk Measures

CVaR satisfies all axioms of coherent risk measures:
1. **Monotonicity**: If X ≤ Y, then Risk(X) ≤ Risk(Y)
2. **Sub-additivity**: Risk(X + Y) ≤ Risk(X) + Risk(Y)
3. **Positive homogeneity**: Risk(λX) = λRisk(X)
4. **Translation invariance**: Risk(X + c) = Risk(X) + c

VaR fails sub-additivity, making CVaR theoretically superior.

## Practical Usage

### Risk Budgeting

```python
# Set risk budget based on CVaR
max_acceptable_cvar = 0.05  # 5%

cvar = risk.calculate_cvar(confidence_level=0.95)

if cvar > max_acceptable_cvar:
    print(f"⚠ Strategy exceeds risk budget: {cvar:.2%} > {max_acceptable_cvar:.2%}")
    # Reduce position sizes or leverage
else:
    print(f"✓ Strategy within risk budget")
```

### Position Sizing

```python
def calculate_position_size(capital, max_cvar, strategy_cvar):
    """Size position based on CVaR limit."""
    # If strategy CVaR is 10% and we want 5% portfolio CVaR:
    # Position size = 5% / 10% = 50% of capital

    position_size = capital * (max_cvar / strategy_cvar)
    return position_size

capital = 100000
max_portfolio_cvar = 0.05
strategy_cvar = 0.10

size = calculate_position_size(capital, max_portfolio_cvar, strategy_cvar)
print(f"Recommended position size: ${size:,.0f}")
```

### Comparative Analysis

```python
# Compare strategies by tail risk
strategies = ['momentum', 'mean_reversion', 'breakout']

for strategy_name in strategies:
    result = run_backtest(strategy_name)
    risk = RiskAnalytics(result)

    var = risk.calculate_var(confidence_level=0.95)
    cvar = risk.calculate_cvar(confidence_level=0.95)

    print(f"{strategy_name}:")
    print(f"  VaR (95%): {var:.2%}")
    print(f"  CVaR (95%): {cvar:.2%}")
    print(f"  Tail risk ratio: {cvar/var:.2f}")
```

## Limitations

### VaR Limitations

1. **Doesn't capture tail shape**: Only tells you the threshold, not how bad tails are
2. **Not sub-additive**: Diversification may not reduce portfolio VaR
3. **Backward-looking**: Based on historical data
4. **Model risk**: Parametric VaR assumes normality

### CVaR Limitations

1. **Backward-looking**: Assumes future similar to past
2. **Sample size dependent**: Needs sufficient data in tail
3. **Estimation error**: Uncertain with limited data
4. **Regime changes**: Past tails may not predict future

## Best Practices

### 1. Use Multiple Confidence Levels

```python
# Don't rely on single confidence level
for conf in [0.90, 0.95, 0.99]:
    var = risk.calculate_var(confidence_level=conf)
    cvar = risk.calculate_cvar(confidence_level=conf)
    print(f"{conf:.0%}: VaR={var:.2%}, CVaR={cvar:.2%}")
```

### 2. Prefer CVaR for Risk Management

```python
# For actual risk management, use CVaR
if cvar_95 > max_acceptable_risk:
    reduce_positions()
```

### 3. Stress Testing

```python
# Test VaR/CVaR under stress scenarios
def stress_test(strategy, stress_scenarios):
    """Test strategy under extreme scenarios."""
    for scenario_name, scenario_data in stress_scenarios.items():
        result = run_backtest(strategy, data=scenario_data)
        risk = RiskAnalytics(result)

        cvar = risk.calculate_cvar(confidence_level=0.95)
        print(f"{scenario_name}: CVaR={cvar:.2%}")
```

### 4. Combine with Other Metrics

```python
# Don't use VaR/CVaR in isolation
metrics = {
    'Sharpe': calculate_sharpe(result),
    'Max Drawdown': calculate_max_drawdown(result),
    'VaR (95%)': risk.calculate_var(0.95),
    'CVaR (95%)': risk.calculate_cvar(0.95)
}

# Comprehensive risk assessment
for metric, value in metrics.items():
    print(f"{metric}: {value:.3f}")
```

## See Also

- [Risk Metrics](metrics.md)
- [Drawdown Analysis](drawdown.md)
- [Main Analytics API](../../analytics-api.md)
