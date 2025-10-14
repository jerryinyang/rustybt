# Performance Metrics

Complete guide to performance measurement and evaluation in RustyBT.

## Overview

RustyBT provides comprehensive performance metrics for evaluating trading strategies:

- **Returns**: Simple, log, time-weighted returns
- **Risk-Adjusted**: Sharpe, Sortino, Calmar ratios
- **Drawdown**: Maximum drawdown, duration, recovery
- **Risk Metrics**: Volatility, beta, alpha
- **Custom Metrics**: Build your own performance measures

## Quick Start

### Access Performance Metrics

```python
from rustybt import TradingAlgorithm

class MyStrategy(TradingAlgorithm):
    def analyze(self, context, perf):
        # Portfolio value over time
        print(f"Starting value: ${perf.portfolio_value[0]:,.2f}")
        print(f"Ending value: ${perf.portfolio_value[-1]:,.2f}")

        # Returns
        total_return = perf.returns[-1]
        print(f"Total return: {total_return:.2%}")

        # Risk metrics
        sharpe = perf.sharpe
        max_dd = perf.max_drawdown
        print(f"Sharpe ratio: {sharpe:.2f}")
        print(f"Max drawdown: {max_dd:.2%}")
```

## Returns Metrics

### Simple Returns

Percentage change in portfolio value.

```python
# Single period return
return_t = (portfolio_value_t - portfolio_value_{t-1}) / portfolio_value_{t-1}

# Total return (cumulative)
total_return = (final_value - initial_value) / initial_value

# Example:
# Start: $100,000
# End: $125,000
# Total return = ($125,000 - $100,000) / $100,000 = 25%
```

**Usage**:
```python
def analyze(self, context, perf):
    # Daily returns
    daily_returns = perf.returns

    # Total return
    total_return = (perf.portfolio_value[-1] / perf.portfolio_value[0]) - 1
    print(f"Total return: {total_return:.2%}")
```

### Log Returns

Natural logarithm of price ratio (time-additive).

```python
# Log return
log_return = ln(portfolio_value_t / portfolio_value_{t-1})

# Properties:
# - Time-additive: sum of log returns = total log return
# - More appropriate for compounding analysis
# - Symmetric for gains/losses
```

**Usage**:
```python
import numpy as np

def analyze(self, context, perf):
    # Calculate log returns
    portfolio_values = perf.portfolio_value
    log_returns = np.log(portfolio_values / portfolio_values.shift(1))

    # Total log return
    total_log_return = log_returns.sum()
    print(f"Total log return: {total_log_return:.4f}")
```

### Annualized Returns

Scale returns to annual basis for comparison.

```python
# Annualized return
annualized_return = (1 + total_return) ** (365 / days) - 1

# Or using daily returns:
daily_return_avg = returns.mean()
annualized_return = (1 + daily_return_avg) ** 252 - 1  # 252 trading days
```

**Usage**:
```python
def calculate_annualized_return(perf):
    """Calculate annualized return."""
    start_date = perf.index[0]
    end_date = perf.index[-1]
    days = (end_date - start_date).days

    total_return = (perf.portfolio_value[-1] / perf.portfolio_value[0]) - 1
    annualized = (1 + total_return) ** (365.0 / days) - 1

    return annualized

# Example:
# 25% return over 180 days
# Annualized = (1.25) ** (365/180) - 1 = 55.9%
```

## Risk-Adjusted Metrics

### Sharpe Ratio

Risk-adjusted return (return per unit of volatility).

```python
# Sharpe ratio
sharpe = (mean_return - risk_free_rate) / std_dev_return

# Annualized Sharpe
annualized_sharpe = sharpe * sqrt(252)  # Daily returns
```

**Interpretation**:
- `> 1.0`: Good risk-adjusted returns
- `> 2.0`: Very good
- `> 3.0`: Excellent (rare)
- `< 1.0`: Poor risk-adjusted returns

**Usage**:
```python
def calculate_sharpe_ratio(returns, risk_free_rate=0.0):
    """Calculate Sharpe ratio.

    Parameters
    ----------
    returns : pd.Series
        Daily returns
    risk_free_rate : float
        Annual risk-free rate (default 0%)

    Returns
    -------
    sharpe : float
        Annualized Sharpe ratio
    """
    excess_returns = returns - risk_free_rate / 252
    sharpe = excess_returns.mean() / excess_returns.std()
    annualized_sharpe = sharpe * np.sqrt(252)
    return annualized_sharpe

# Example:
# Mean daily return: 0.1% (10 bps)
# Std dev: 1.0%
# Sharpe = 0.001 / 0.01 = 0.1 daily
# Annualized = 0.1 * sqrt(252) = 1.59
```

### Sortino Ratio

Like Sharpe, but only penalizes downside volatility.

```python
# Sortino ratio
sortino = (mean_return - risk_free_rate) / downside_deviation

# Downside deviation (only negative returns)
downside_deviation = sqrt(mean(min(return - target, 0)^2))
```

**Interpretation**:
- Better than Sharpe for strategies with positive skew
- Doesn't penalize upside volatility
- Higher is better (same scale as Sharpe)

**Usage**:
```python
def calculate_sortino_ratio(returns, target_return=0.0):
    """Calculate Sortino ratio.

    Parameters
    ----------
    returns : pd.Series
        Daily returns
    target_return : float
        Minimum acceptable return (default 0%)

    Returns
    -------
    sortino : float
        Annualized Sortino ratio
    """
    excess_returns = returns - target_return
    downside_returns = excess_returns[excess_returns < 0]
    downside_std = downside_returns.std()

    sortino = excess_returns.mean() / downside_std
    annualized_sortino = sortino * np.sqrt(252)
    return annualized_sortino
```

### Calmar Ratio

Return relative to maximum drawdown.

```python
# Calmar ratio
calmar = annualized_return / abs(max_drawdown)
```

**Interpretation**:
- `> 1.0`: Good (return exceeds max drawdown)
- `> 3.0`: Excellent
- Useful for comparing drawdown-sensitive strategies

**Usage**:
```python
def calculate_calmar_ratio(perf):
    """Calculate Calmar ratio."""
    annualized_return = calculate_annualized_return(perf)
    max_drawdown = perf.max_drawdown

    calmar = annualized_return / abs(max_drawdown)
    return calmar

# Example:
# Annualized return: 30%
# Max drawdown: 15%
# Calmar = 0.30 / 0.15 = 2.0
```

## Drawdown Metrics

### Maximum Drawdown

Largest peak-to-trough decline.

```python
# Calculate drawdown at each point
cumulative_max = portfolio_value.cummax()
drawdown = (portfolio_value - cumulative_max) / cumulative_max

# Maximum drawdown
max_drawdown = drawdown.min()
```

**Usage**:
```python
def calculate_max_drawdown(portfolio_values):
    """Calculate maximum drawdown.

    Returns
    -------
    max_dd : float
        Maximum drawdown as decimal (e.g., -0.25 for 25% drawdown)
    max_dd_duration : int
        Duration of max drawdown in days
    recovery_time : int
        Days to recover from max drawdown
    """
    cummax = portfolio_values.cummax()
    drawdown = (portfolio_values - cummax) / cummax

    max_dd = drawdown.min()
    max_dd_date = drawdown.idxmin()

    # Find peak before max drawdown
    peak_date = portfolio_values[:max_dd_date].idxmax()

    # Find recovery (if any)
    recovery_dates = portfolio_values[max_dd_date:] >= portfolio_values[peak_date]
    if recovery_dates.any():
        recovery_date = recovery_dates.idxmax()
        recovery_time = (recovery_date - max_dd_date).days
    else:
        recovery_time = None  # Not recovered yet

    max_dd_duration = (max_dd_date - peak_date).days

    return max_dd, max_dd_duration, recovery_time

# Example output:
# Max drawdown: -18.5%
# Duration: 45 days
# Recovery: 120 days
```

### Drawdown Duration

Time spent in drawdown.

```python
def calculate_drawdown_stats(portfolio_values):
    """Comprehensive drawdown statistics."""
    cummax = portfolio_values.cummax()
    drawdown = (portfolio_values - cummax) / cummax

    # Time in drawdown (% of time portfolio below peak)
    time_in_drawdown = (drawdown < 0).sum() / len(drawdown)

    # Average drawdown depth when in drawdown
    avg_drawdown = drawdown[drawdown < 0].mean()

    return {
        'max_drawdown': drawdown.min(),
        'time_in_drawdown': time_in_drawdown,
        'avg_drawdown': avg_drawdown,
    }
```

### Underwater Plot

Visualize drawdown over time.

```python
import matplotlib.pyplot as plt

def plot_underwater(portfolio_values):
    """Plot drawdown over time."""
    cummax = portfolio_values.cummax()
    drawdown = (portfolio_values - cummax) / cummax

    plt.figure(figsize=(12, 6))
    plt.fill_between(drawdown.index, drawdown, 0, alpha=0.3, color='red')
    plt.plot(drawdown.index, drawdown, color='red', linewidth=1)
    plt.ylabel('Drawdown (%)')
    plt.xlabel('Date')
    plt.title('Underwater Plot - Drawdown Over Time')
    plt.grid(True)
    plt.show()
```

## Risk Metrics

### Volatility

Standard deviation of returns (annualized).

```python
# Daily volatility
daily_vol = returns.std()

# Annualized volatility
annual_vol = daily_vol * sqrt(252)
```

**Usage**:
```python
def calculate_volatility(returns):
    """Calculate annualized volatility."""
    daily_vol = returns.std()
    annual_vol = daily_vol * np.sqrt(252)
    return annual_vol

# Example:
# Daily std dev: 1.5%
# Annual vol = 1.5% * sqrt(252) = 23.8%
```

### Beta

Sensitivity to market movements.

```python
# Beta relative to benchmark
beta = covariance(strategy_returns, benchmark_returns) / variance(benchmark_returns)
```

**Interpretation**:
- `β = 1.0`: Moves with market
- `β > 1.0`: More volatile than market (amplified)
- `β < 1.0`: Less volatile than market (dampened)
- `β < 0.0`: Inverse correlation with market

**Usage**:
```python
def calculate_beta(strategy_returns, benchmark_returns):
    """Calculate beta relative to benchmark."""
    covariance = strategy_returns.cov(benchmark_returns)
    benchmark_variance = benchmark_returns.var()
    beta = covariance / benchmark_variance
    return beta

# Example:
# Beta = 1.5 means strategy moves 1.5x market moves
# If market up 10%, expect strategy up 15%
```

### Alpha

Excess return above benchmark (risk-adjusted).

```python
# Jensen's alpha
alpha = strategy_return - (risk_free_rate + beta * (benchmark_return - risk_free_rate))
```

**Interpretation**:
- `α > 0`: Outperformance (positive alpha generation)
- `α = 0`: Market return given risk taken
- `α < 0`: Underperformance

**Usage**:
```python
def calculate_alpha(strategy_returns, benchmark_returns, risk_free_rate=0.0):
    """Calculate Jensen's alpha (annualized)."""
    # Calculate beta
    beta = calculate_beta(strategy_returns, benchmark_returns)

    # Annualized returns
    strategy_annual = (1 + strategy_returns.mean()) ** 252 - 1
    benchmark_annual = (1 + benchmark_returns.mean()) ** 252 - 1

    # Jensen's alpha
    alpha = strategy_annual - (risk_free_rate + beta * (benchmark_annual - risk_free_rate))
    return alpha

# Example:
# Strategy return: 25%
# Benchmark return: 15%
# Beta: 1.2
# Risk-free rate: 3%
# Alpha = 25% - (3% + 1.2 × (15% - 3%)) = 7.6%
```

### Information Ratio

Excess return per unit of tracking error.

```python
# Information ratio
IR = (strategy_return - benchmark_return) / tracking_error

# Tracking error = std dev of (strategy_return - benchmark_return)
tracking_error = (strategy_returns - benchmark_returns).std()
```

**Usage**:
```python
def calculate_information_ratio(strategy_returns, benchmark_returns):
    """Calculate Information Ratio."""
    excess_returns = strategy_returns - benchmark_returns
    ir = excess_returns.mean() / excess_returns.std()
    annualized_ir = ir * np.sqrt(252)
    return annualized_ir
```

## Win/Loss Metrics

### Win Rate

Percentage of profitable trades.

```python
def calculate_win_rate(transactions):
    """Calculate win rate from transactions."""
    profitable = sum(1 for txn in transactions if txn.pnl > 0)
    total = len(transactions)
    win_rate = profitable / total if total > 0 else 0
    return win_rate
```

### Profit Factor

Ratio of gross profits to gross losses.

```python
def calculate_profit_factor(transactions):
    """Calculate profit factor."""
    gross_profit = sum(txn.pnl for txn in transactions if txn.pnl > 0)
    gross_loss = abs(sum(txn.pnl for txn in transactions if txn.pnl < 0))

    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    return profit_factor

# Interpretation:
# > 2.0: Strong (profits 2x losses)
# > 1.5: Good
# > 1.0: Profitable (more profit than loss)
# < 1.0: Losing system
```

### Average Win/Loss

```python
def calculate_avg_win_loss(transactions):
    """Calculate average win and loss sizes."""
    wins = [txn.pnl for txn in transactions if txn.pnl > 0]
    losses = [txn.pnl for txn in transactions if txn.pnl < 0]

    avg_win = np.mean(wins) if wins else 0
    avg_loss = np.mean(losses) if losses else 0

    # Win/Loss ratio
    win_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')

    return {
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'win_loss_ratio': win_loss_ratio
    }

# Example:
# Avg win: $500
# Avg loss: $250
# Win/Loss ratio: 2.0 (wins are 2x losses on average)
```

## Custom Metrics

### Create Custom Metric

```python
from rustybt.finance.metrics import MetricCalculator

class CustomMetric(MetricCalculator):
    """Custom performance metric."""

    def calculate(self, context, returns, positions):
        """Calculate custom metric.

        Parameters
        ----------
        context : Context
            Strategy context
        returns : pd.Series
            Daily returns
        positions : dict
            Current positions

        Returns
        -------
        metric_value : float
            Calculated metric
        """
        # Your custom calculation
        pass

# Register custom metric
algo.add_metric('custom', CustomMetric())
```

### Example: Omega Ratio

```python
class OmegaRatio(MetricCalculator):
    """Omega ratio: probability-weighted ratio of gains to losses."""

    def __init__(self, threshold=0.0):
        self.threshold = threshold

    def calculate(self, context, returns, positions):
        """Calculate Omega ratio."""
        excess_returns = returns - self.threshold

        gains = excess_returns[excess_returns > 0].sum()
        losses = abs(excess_returns[excess_returns < 0].sum())

        omega = gains / losses if losses > 0 else float('inf')
        return omega
```

## Performance Analysis Example

```python
class PerformanceAnalysis(TradingAlgorithm):
    def analyze(self, context, perf):
        """Comprehensive performance analysis."""

        print("=" * 60)
        print("PERFORMANCE SUMMARY")
        print("=" * 60)

        # Returns
        total_return = (perf.portfolio_value[-1] / perf.portfolio_value[0]) - 1
        annual_return = calculate_annualized_return(perf)

        print(f"\nReturns:")
        print(f"  Total Return: {total_return:.2%}")
        print(f"  Annualized Return: {annual_return:.2%}")

        # Risk metrics
        daily_returns = perf.returns
        volatility = calculate_volatility(daily_returns)
        sharpe = calculate_sharpe_ratio(daily_returns)
        sortino = calculate_sortino_ratio(daily_returns)

        print(f"\nRisk Metrics:")
        print(f"  Volatility (annual): {volatility:.2%}")
        print(f"  Sharpe Ratio: {sharpe:.2f}")
        print(f"  Sortino Ratio: {sortino:.2f}")

        # Drawdown
        max_dd, dd_duration, recovery = calculate_max_drawdown(perf.portfolio_value)
        calmar = annual_return / abs(max_dd)

        print(f"\nDrawdown:")
        print(f"  Max Drawdown: {max_dd:.2%}")
        print(f"  Drawdown Duration: {dd_duration} days")
        print(f"  Recovery Time: {recovery} days" if recovery else "  Not recovered")
        print(f"  Calmar Ratio: {calmar:.2f}")

        # Trading stats
        print(f"\nTrading Statistics:")
        print(f"  Total Trades: {len(perf.transactions)}")

        if len(perf.transactions) > 0:
            win_rate = calculate_win_rate(perf.transactions)
            profit_factor = calculate_profit_factor(perf.transactions)

            print(f"  Win Rate: {win_rate:.2%}")
            print(f"  Profit Factor: {profit_factor:.2f}")

        print("=" * 60)
```

## Best Practices

### ✅ DO

1. **Compare Against Benchmark**: Always evaluate relative to market/benchmark
2. **Use Multiple Metrics**: Don't rely on single metric (Sharpe alone insufficient)
3. **Consider Drawdowns**: High returns with huge drawdowns = high risk
4. **Annualize Metrics**: For comparison across strategies/time periods
5. **Account for Costs**: Include slippage and commissions in performance

### ❌ DON'T

1. **Ignore Risk**: High returns mean nothing without risk context
2. **Cherry-Pick Metrics**: Report all metrics, not just favorable ones
3. **Overfit to Sharpe**: Can be gamed with certain strategies
4. **Forget Context**: Market conditions affect all metrics
5. **Compare Apples to Oranges**: Match time periods and risk levels

## Related Documentation

- [Performance Calculations](calculations.md) - Detailed calculation methods
- [Performance Interpretation](interpretation.md) - Understanding metrics
- [Portfolio Management](../README.md) - Portfolio tracking
- [Analytics API](../../analytics-api.md) - Advanced analysis tools

## Next Steps

1. Study [Performance Calculations](calculations.md) for implementation details
2. Review [Interpretation Guide](interpretation.md) for metric analysis
3. Explore [Analytics API](../../analytics-api.md) for advanced metrics
