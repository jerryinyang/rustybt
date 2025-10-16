# Drawdown Analysis

Understanding and analyzing peak-to-trough declines in portfolio value.

## Overview

Drawdown measures the decline from a historical peak to a subsequent trough. It's one of the most important risk metrics for traders because it represents actual loss experienced.

## Maximum Drawdown

### Definition

Maximum Drawdown (MDD) is the largest peak-to-trough decline in portfolio value.

```python
from rustybt.analytics import RiskAnalytics

risk = RiskAnalytics(backtest_result)
metrics = risk.calculate_risk_metrics()

max_dd = metrics['max_drawdown']
max_dd_duration = metrics['max_drawdown_duration']

print(f"Maximum Drawdown: {max_dd:.2%}")
print(f"Duration: {max_dd_duration} days")
```

### Calculation

```python
def calculate_max_drawdown(equity_curve):
    """Calculate maximum drawdown from equity curve."""
    # Calculate running maximum
    running_max = equity_curve.expanding().max()

    # Calculate drawdown at each point
    drawdown = (equity_curve - running_max) / running_max

    # Maximum drawdown
    max_dd = drawdown.min()

    return max_dd

# Example
equity = backtest_result['portfolio_value']
max_dd = calculate_max_drawdown(equity)
print(f"Max Drawdown: {max_dd:.2%}")  # e.g., -23.5%
```

## Drawdown Series

### Computing Drawdowns

```python
# Get full drawdown series
drawdowns = risk.calculate_drawdown_series()

# Plot
import matplotlib.pyplot as plt

plt.figure(figsize=(12, 6))
plt.fill_between(drawdowns.index, 0, drawdowns.values * 100,
                 alpha=0.3, color='red', label='Drawdown')
plt.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
plt.ylabel('Drawdown (%)')
plt.xlabel('Date')
plt.title('Portfolio Drawdown Over Time')
plt.legend()
plt.grid(True, alpha=0.3)
plt.show()
```

### Underwater Plot

Shows how long portfolio stays below previous peak:

```python
def plot_underwater(equity_curve):
    """Plot underwater periods (time below peak)."""
    running_max = equity_curve.expanding().max()
    drawdown = (equity_curve - running_max) / running_max

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    # Equity curve with peaks
    ax1.plot(equity_curve.index, equity_curve.values, label='Portfolio')
    ax1.plot(running_max.index, running_max.values,
            'r--', alpha=0.5, label='Peak')
    ax1.set_ylabel('Portfolio Value ($)')
    ax1.set_title('Equity Curve with Peaks')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Underwater plot
    ax2.fill_between(drawdown.index, 0, drawdown.values * 100,
                    color='red', alpha=0.3)
    ax2.set_ylabel('Drawdown (%)')
    ax2.set_xlabel('Date')
    ax2.set_title('Underwater Plot')
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    return fig
```

## Drawdown Periods

### Identifying Drawdown Periods

```python
# Get N largest drawdown periods
top_drawdowns = risk.get_largest_drawdowns(n=5)

for i, dd in enumerate(top_drawdowns, 1):
    print(f"\nDrawdown #{i}:")
    print(f"  Magnitude: {dd['drawdown']:.2%}")
    print(f"  Peak: {dd['start_date']}")
    print(f"  Trough: {dd['end_date']}")
    print(f"  Recovery: {dd['recovery_date']}")
    print(f"  Duration: {dd['duration']} days")
```

### Drawdown Characteristics

```python
def analyze_drawdown_period(start_date, end_date, equity_curve):
    """Analyze specific drawdown period."""
    period_equity = equity_curve.loc[start_date:end_date]

    # Peak and trough
    peak_value = period_equity.iloc[0]
    trough_value = period_equity.min()
    trough_date = period_equity.idxmin()

    # Metrics
    magnitude = (trough_value - peak_value) / peak_value
    duration = (trough_date - start_date).days

    # Recovery
    recovery_mask = period_equity >= peak_value
    if recovery_mask.any():
        recovery_date = period_equity[recovery_mask].index[0]
        recovery_days = (recovery_date - trough_date).days
    else:
        recovery_date = None
        recovery_days = None

    return {
        'peak_value': peak_value,
        'trough_value': trough_value,
        'trough_date': trough_date,
        'magnitude': magnitude,
        'duration_to_trough': duration,
        'recovery_date': recovery_date,
        'recovery_duration': recovery_days
    }
```

## Drawdown Metrics

### Average Drawdown

```python
def calculate_average_drawdown(equity_curve):
    """Calculate average drawdown."""
    running_max = equity_curve.expanding().max()
    drawdown = (equity_curve - running_max) / running_max

    # Average of all negative drawdowns
    avg_dd = drawdown[drawdown < 0].mean()
    return avg_dd
```

### Drawdown Duration

```python
def calculate_avg_drawdown_duration(equity_curve):
    """Calculate average time underwater."""
    running_max = equity_curve.expanding().max()
    at_peak = (equity_curve >= running_max)

    # Identify drawdown periods
    underwater_periods = []
    current_period = 0

    for is_peak in at_peak:
        if not is_peak:
            current_period += 1
        elif current_period > 0:
            underwater_periods.append(current_period)
            current_period = 0

    if current_period > 0:
        underwater_periods.append(current_period)

    return np.mean(underwater_periods) if underwater_periods else 0
```

### Calmar Ratio

Return divided by maximum drawdown:

```python
def calculate_calmar_ratio(returns, max_drawdown):
    """Calculate Calmar ratio: Annual return / |Max drawdown|."""
    annual_return = returns.mean() * 252
    calmar = annual_return / abs(max_drawdown)
    return calmar

# Example
calmar = metrics['calmar_ratio']
print(f"Calmar Ratio: {calmar:.2f}")

# Interpretation:
# > 1.0: Return exceeds worst drawdown (good)
# > 2.0: Excellent risk-adjusted return
```

## Practical Applications

### Risk Assessment

```python
# Evaluate if drawdown is acceptable
max_acceptable_dd = 0.25  # 25%

if abs(max_dd) > max_acceptable_dd:
    print(f"⚠ WARNING: Drawdown {abs(max_dd):.1%} exceeds limit {max_acceptable_dd:.1%}")
    print("Consider:")
    print("- Reducing position sizes")
    print("- Adding stop losses")
    print("- Diversifying strategies")
else:
    print(f"✓ Drawdown within acceptable limits")
```

### Position Sizing

```python
def kelly_criterion_with_dd(win_rate, avg_win, avg_loss, max_dd_tolerance):
    """Kelly criterion adjusted for drawdown tolerance."""
    # Standard Kelly
    kelly_fraction = win_rate - (1 - win_rate) / (avg_win / abs(avg_loss))

    # Adjust for drawdown tolerance
    # Conservative: Use fraction of Kelly
    dd_adjustment = max_dd_tolerance / 0.30  # Normalize to 30% DD
    adjusted_kelly = kelly_fraction * dd_adjustment * 0.5  # Half-Kelly

    return adjusted_kelly
```

### Strategy Comparison

```python
# Compare strategies by drawdown characteristics
strategies = ['momentum', 'mean_reversion']

for strategy_name in strategies:
    result = run_backtest(strategy_name)
    risk = RiskAnalytics(result)

    metrics = risk.calculate_risk_metrics()

    print(f"\n{strategy_name}:")
    print(f"  Max Drawdown: {metrics['max_drawdown']:.2%}")
    print(f"  Avg Drawdown: {calculate_average_drawdown(result):.2%}")
    print(f"  Max DD Duration: {metrics['max_drawdown_duration']} days")
    print(f"  Calmar Ratio: {metrics['calmar_ratio']:.2f}")
```

## Drawdown Guidelines

### Acceptable Levels

| Drawdown | Assessment | Action |
|----------|------------|--------|
| < 10% | Excellent | None |
| 10-20% | Good | Monitor |
| 20-30% | Acceptable | Review strategy |
| 30-40% | High | Reduce risk |
| > 40% | Severe | Major changes needed |

### Duration Guidelines

```python
# Maximum acceptable time underwater
max_acceptable_duration = 365  # 1 year

if max_dd_duration > max_acceptable_duration:
    print(f"⚠ WARNING: Underwater for {max_dd_duration} days")
    print("Strategy may take too long to recover")
```

## Best Practices

### 1. Monitor Multiple Drawdown Metrics

```python
# Don't just look at maximum drawdown
metrics = {
    'Max Drawdown': abs(metrics['max_drawdown']),
    'Avg Drawdown': abs(calculate_average_drawdown(equity)),
    'Max Duration': metrics['max_drawdown_duration'],
    'Avg Duration': calculate_avg_drawdown_duration(equity),
    'Calmar Ratio': metrics['calmar_ratio']
}

for metric, value in metrics.items():
    print(f"{metric}: {value:.2f}")
```

### 2. Analyze Drawdown Context

```python
# Understand what caused major drawdowns
for dd in top_drawdowns[:3]:
    print(f"\nDrawdown during {dd['start_date']} to {dd['end_date']}")
    print(f"Magnitude: {dd['drawdown']:.2%}")

    # Analyze market conditions during period
    market_return = get_market_return(dd['start_date'], dd['end_date'])
    print(f"Market return: {market_return:.2%}")

    if dd['drawdown'] < market_return:
        print("Strategy underperformed market significantly")
```

### 3. Stress Test for Future Drawdowns

```python
# Estimate potential future drawdowns
historical_max_dd = abs(metrics['max_drawdown'])

# Conservative estimate: 1.5x historical
estimated_future_dd = historical_max_dd * 1.5

print(f"Historical max DD: {historical_max_dd:.1%}")
print(f"Estimated future DD: {estimated_future_dd:.1%}")
print(f"\nCan you tolerate a {estimated_future_dd:.1%} loss?")
```

### 4. Set Stop-Loss Levels

```python
# Set portfolio-level stop-loss based on drawdown tolerance
def set_stop_loss(current_peak, max_drawdown_tolerance):
    """Calculate stop-loss level."""
    stop_loss_level = current_peak * (1 - max_drawdown_tolerance)
    return stop_loss_level

current_portfolio_value = 100000
max_tolerance = 0.20  # 20%

stop_loss = set_stop_loss(current_portfolio_value, max_tolerance)
print(f"Current value: ${current_portfolio_value:,.0f}")
print(f"Stop-loss level: ${stop_loss:,.0f}")
print(f"If portfolio falls below ${stop_loss:,.0f}, liquidate positions")
```

## See Also

- [Risk Metrics](metrics.md)
- [VaR & CVaR](var-cvar.md)
- [Main Analytics API](../../analytics-api.md)
