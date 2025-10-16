# Risk Metrics

**Module**: `rustybt.finance.metrics.decimal_metrics`

**Source File**: `rustybt/finance/metrics/decimal_metrics.py` (596 lines)

**Last Updated**: 2025-10-16
**Confidence**: 100% (all APIs verified against source code)

---

## Overview

RustyBT provides a comprehensive suite of risk and performance metrics calculated with Decimal precision for audit-compliant financial analysis. All metrics use Python's `Decimal` type throughout the calculation pipeline to maintain precision and avoid floating-point errors.

### Key Features

- **Decimal Precision**: All calculations maintain Decimal precision (no float conversions)
- **Industry-Standard Metrics**: Sharpe, Sortino, VaR, CVaR, and more
- **Robust Error Handling**: Graceful handling of edge cases (zero volatility, insufficient data)
- **Polars Integration**: Efficient computation using Polars Series
- **Annualization Support**: Automatic annualization for daily, monthly, or custom frequencies
- **Benchmark Comparison**: Information ratio, tracking error, excess returns

---

## Exception Classes

**Source**: `decimal_metrics.py:32-42`

###

 MetricsError

Base exception for all metrics errors.

```python
from rustybt.finance.metrics.decimal_metrics import MetricsError
```

### InsufficientDataError

Raised when there is insufficient data for metric calculation.

```python
from rustybt.finance.metrics.decimal_metrics import InsufficientDataError

try:
    sharpe = calculate_sharpe_ratio(returns)
except InsufficientDataError as e:
    print(f"Not enough data: {e}")
```

### InvalidMetricError

Raised when metric calculation produces an invalid result.

```python
from rustybt.finance.metrics.decimal_metrics import InvalidMetricError

try:
    drawdown = calculate_max_drawdown(cumulative)
except InvalidMetricError as e:
    print(f"Invalid metric: {e}")
```

---

## Risk-Adjusted Return Metrics

### calculate_sharpe_ratio()

**Source**: `decimal_metrics.py:44-104`

Calculate the Sharpe ratio with Decimal precision.

```python
def calculate_sharpe_ratio(
    returns: pl.Series,
    risk_free_rate: Decimal = Decimal("0"),
    annualization_factor: int = 252,
    config: DecimalConfig | None = None,
) -> Decimal
```

**Parameters**:
- `returns`: Returns series as Polars Series with Decimal values
- `risk_free_rate`: Risk-free rate (e.g., `Decimal("0.02")` = 2% annual)
- `annualization_factor`: Days per year (252 for daily, 12 for monthly)
- `config`: DecimalConfig for precision (uses default if None)

**Returns**: Sharpe ratio as Decimal

**Raises**:
- `InsufficientDataError`: If returns series has fewer than 2 data points
- `InvalidMetricError`: If calculation produces invalid result

**Formula**:
```
Sharpe = (mean_return - risk_free_rate) / std_dev_return × √annualization_factor
```

**Example**:
```python
from rustybt.finance.metrics.decimal_metrics import calculate_sharpe_ratio
from decimal import Decimal
import polars as pl

# Calculate Sharpe ratio for daily returns
returns = pl.Series("returns", [
    Decimal("0.01"),   # +1%
    Decimal("-0.005"), # -0.5%
    Decimal("0.015"),  # +1.5%
    Decimal("0.002"),  # +0.2%
])

sharpe = calculate_sharpe_ratio(
    returns=returns,
    risk_free_rate=Decimal("0.02"),  # 2% annual risk-free rate
    annualization_factor=252,
)

print(f"Sharpe Ratio: {sharpe:.2f}")

# Without risk-free rate (excess Sharpe)
sharpe_excess = calculate_sharpe_ratio(
    returns=returns,
    risk_free_rate=Decimal("0"),  # No risk-free rate
    annualization_factor=252,
)

print(f"Excess Sharpe: {sharpe_excess:.2f}")
```

---

### calculate_sortino_ratio()

**Source**: `decimal_metrics.py:107-180`

Calculate the Sortino ratio with Decimal precision. The Sortino ratio is similar to Sharpe but uses **downside deviation** instead of total volatility, penalizing only downside risk.

```python
def calculate_sortino_ratio(
    returns: pl.Series,
    risk_free_rate: Decimal = Decimal("0"),
    annualization_factor: int = 252,
    config: DecimalConfig | None = None,
) -> Decimal
```

**Parameters**:
- `returns`: Returns series as Polars Series with Decimal values
- `risk_free_rate`: Risk-free rate (e.g., `Decimal("0.02")` = 2% annual)
- `annualization_factor`: Days per year (252 for daily, 12 for monthly)
- `config`: DecimalConfig for precision (uses default if None)

**Returns**: Sortino ratio as Decimal

**Raises**:
- `InsufficientDataError`: If returns series has fewer than 2 data points
- `InvalidMetricError`: If no negative returns exist

**Formula**:
```
Sortino = (mean_return - risk_free_rate) / downside_deviation × √annualization_factor
where downside_deviation = std_dev(returns where returns < 0)
```

**Example**:
```python
from rustybt.finance.metrics.decimal_metrics import calculate_sortino_ratio
from decimal import Decimal
import polars as pl

returns = pl.Series("returns", [
    Decimal("0.02"),   # +2% (upside)
    Decimal("-0.01"),  # -1% (downside)
    Decimal("0.03"),   # +3% (upside)
    Decimal("-0.015"), # -1.5% (downside)
    Decimal("0.025"),  # +2.5% (upside)
])

sortino = calculate_sortino_ratio(
    returns=returns,
    risk_free_rate=Decimal("0.02"),
    annualization_factor=252,
)

print(f"Sortino Ratio: {sortino:.2f}")

# Sortino is higher than Sharpe for strategies with:
# - Positive skew (large upside, small downside)
# - Asymmetric returns

# Edge case: All positive returns
all_positive = pl.Series("returns", [
    Decimal("0.01"), Decimal("0.02"), Decimal("0.015")
])

sortino_positive = calculate_sortino_ratio(all_positive)
# Returns Decimal("inf") - no downside risk!
```

---

### calculate_calmar_ratio()

**Source**: `decimal_metrics.py:250-307`

Calculate the Calmar ratio (annualized return / absolute max drawdown). The Calmar ratio measures risk-adjusted return using maximum drawdown as the risk measure.

```python
def calculate_calmar_ratio(
    cumulative_returns: pl.Series,
    periods_per_year: int = 252,
    config: DecimalConfig | None = None,
) -> Decimal
```

**Parameters**:
- `cumulative_returns`: Cumulative returns series as Polars Series with Decimal values
- `periods_per_year`: Number of periods per year (252 for daily, 12 for monthly)
- `config`: DecimalConfig for precision (uses default if None)

**Returns**: Calmar ratio as Decimal

**Raises**:
- `InsufficientDataError`: If insufficient data
- `InvalidMetricError`: If calculation produces invalid result

**Formula**:
```
Calmar = annualized_return / abs(max_drawdown)
```

**Example**:
```python
from rustybt.finance.metrics.decimal_metrics import calculate_calmar_ratio
from decimal import Decimal
import polars as pl

# Cumulative returns (starting at 1.0)
cumulative = pl.Series("cumulative", [
    Decimal("1.0"),    # Starting value
    Decimal("1.1"),    # +10%
    Decimal("1.05"),   # Drawdown to +5%
    Decimal("1.2"),    # New high +20%
    Decimal("1.15"),   # Drawdown to +15%
])

calmar = calculate_calmar_ratio(
    cumulative_returns=cumulative,
    periods_per_year=252,
)

print(f"Calmar Ratio: {calmar:.2f}")

# Higher Calmar ratio = better risk-adjusted return
# Calmar > 1.0 is good
# Calmar > 2.0 is excellent
```

---

## Drawdown Metrics

### calculate_max_drawdown()

**Source**: `decimal_metrics.py:183-247`

Calculate maximum drawdown from cumulative returns. Maximum drawdown is the largest peak-to-trough decline in portfolio value.

```python
def calculate_max_drawdown(
    cumulative_returns: pl.Series
) -> Decimal
```

**Parameters**:
- `cumulative_returns`: Cumulative returns series as Polars Series with Decimal values

**Returns**: Maximum drawdown as Decimal (negative value, e.g., `Decimal("-0.25")` = -25%)

**Raises**:
- `InsufficientDataError`: If returns series is empty
- `InvalidMetricError`: If drawdown is outside valid range [-1, 0]

**Formula**:
```
drawdown(t) = (cumulative_return(t) - running_max(t)) / running_max(t)
max_drawdown = min(drawdown(t)) for all t
```

**Example**:
```python
from rustybt.finance.metrics.decimal_metrics import calculate_max_drawdown
from decimal import Decimal
import polars as pl

# Example: Portfolio rises to 1.5, then falls to 1.2
cumulative = pl.Series("cumulative", [
    Decimal("1.0"),   # Start
    Decimal("1.2"),   # +20%
    Decimal("1.5"),   # Peak +50%
    Decimal("1.2"),   # Trough +20% (drawdown from peak)
    Decimal("1.3"),   # Recovery +30%
])

max_dd = calculate_max_drawdown(cumulative)

# Max DD = (1.2 - 1.5) / 1.5 = -0.2 = -20%
print(f"Max Drawdown: {max_dd:.2%}")

# Typical ranges:
# -5% to -10%: Low drawdown (defensive strategy)
# -10% to -20%: Moderate drawdown
# -20% to -30%: High drawdown (aggressive strategy)
# > -30%: Very high drawdown (high risk)
```

---

## Value at Risk (VaR) Metrics

### calculate_var()

**Source**: `decimal_metrics.py:310-348`

Calculate Value at Risk (VaR) at specified confidence level using historical simulation method.

```python
def calculate_var(
    returns: pl.Series,
    confidence_level: Decimal = Decimal("0.05"),
    config: DecimalConfig | None = None,
) -> Decimal
```

**Parameters**:
- `returns`: Returns series as Polars Series with Decimal values
- `confidence_level`: Percentile for VaR (e.g., `0.05` for 95% VaR, `0.01` for 99% VaR)
- `config`: DecimalConfig for precision (uses default if None)

**Returns**: VaR as Decimal (negative value representing loss)

**Raises**:
- `InsufficientDataError`: If insufficient data

**Formula**:
```
VaR = percentile(returns, confidence_level)
```

**Example**:
```python
from rustybt.finance.metrics.decimal_metrics import calculate_var
from decimal import Decimal
import polars as pl

returns = pl.Series("returns", [
    Decimal("-0.05"), Decimal("0.01"), Decimal("-0.02"),
    Decimal("0.03"), Decimal("-0.01"), Decimal("0.02"),
    Decimal("-0.03"), Decimal("0.015"), Decimal("-0.008"),
])

# 95% VaR (5th percentile)
var_95 = calculate_var(
    returns=returns,
    confidence_level=Decimal("0.05"),
)

print(f"95% VaR: {var_95:.2%}")
# Interpretation: "In the worst 5% of days, we lose at least {var_95}%"

# 99% VaR (1st percentile)
var_99 = calculate_var(
    returns=returns,
    confidence_level=Decimal("0.01"),
)

print(f"99% VaR: {var_99:.2%}")
# Interpretation: "In the worst 1% of days, we lose at least {var_99}%"

# VaR is always negative for losses
# More negative = higher risk
```

---

### calculate_cvar()

**Source**: `decimal_metrics.py:351-397`

Calculate Conditional Value at Risk (CVaR / Expected Shortfall). CVaR is the **expected loss** in the worst (confidence_level) of cases.

```python
def calculate_cvar(
    returns: pl.Series,
    confidence_level: Decimal = Decimal("0.05"),
    config: DecimalConfig | None = None,
) -> Decimal
```

**Parameters**:
- `returns`: Returns series as Polars Series with Decimal values
- `confidence_level`: Percentile for CVaR (e.g., `0.05` for 95% CVaR)
- `config`: DecimalConfig for precision (uses default if None)

**Returns**: CVaR as Decimal (negative value representing expected tail loss)

**Raises**:
- `InsufficientDataError`: If insufficient data

**Formula**:
```
CVaR = E[returns | returns <= VaR]
```

**Example**:
```python
from rustybt.finance.metrics.decimal_metrics import calculate_cvar, calculate_var
from decimal import Decimal
import polars as pl

returns = pl.Series("returns", [
    Decimal("-0.05"), Decimal("0.01"), Decimal("-0.02"),
    Decimal("0.03"), Decimal("-0.01"), Decimal("0.02"),
    Decimal("-0.03"), Decimal("0.015"), Decimal("-0.008"),
])

# 95% CVaR
cvar_95 = calculate_cvar(
    returns=returns,
    confidence_level=Decimal("0.05"),
)

var_95 = calculate_var(
    returns=returns,
    confidence_level=Decimal("0.05"),
)

print(f"95% VaR:  {var_95:.2%}")
print(f"95% CVaR: {cvar_95:.2%}")

# CVaR is ALWAYS worse (more negative) than VaR
# CVaR tells you the AVERAGE loss in the tail
# VaR tells you the THRESHOLD for the tail

# Interpretation:
# "In the worst 5% of days, we expect to lose {cvar_95}% on average"
```

---

## Trade Statistics

### calculate_win_rate()

**Source**: `decimal_metrics.py:400-434`

Calculate win rate (percentage of profitable trades).

```python
def calculate_win_rate(
    trade_returns: pl.Series
) -> Decimal
```

**Parameters**:
- `trade_returns`: Trade returns series as Polars Series with Decimal values

**Returns**: Win rate as Decimal in range [0, 1] (e.g., `Decimal("0.6")` = 60%)

**Raises**:
- `InsufficientDataError`: If no trades
- `InvalidMetricError`: If win rate is outside [0, 1]

**Formula**:
```
win_rate = count(returns > 0) / count(total_returns)
```

**Example**:
```python
from rustybt.finance.metrics.decimal_metrics import calculate_win_rate
from decimal import Decimal
import polars as pl

# Trade returns (per-trade, not daily)
trades = pl.Series("trades", [
    Decimal("0.05"),   # Win +5%
    Decimal("-0.02"),  # Loss -2%
    Decimal("0.03"),   # Win +3%
    Decimal("-0.01"),  # Loss -1%
    Decimal("0.07"),   # Win +7%
    Decimal("-0.015"), # Loss -1.5%
])

win_rate = calculate_win_rate(trades)

print(f"Win Rate: {win_rate:.2%}")
# Output: Win Rate: 50.00% (3 wins / 6 trades)

# Interpretation:
# - Win rate > 50%: More winners than losers
# - Win rate < 50%: Needs high profit factor to be profitable
# - Win rate = 100%: All trades profitable (unlikely in reality)
```

---

### calculate_profit_factor()

**Source**: `decimal_metrics.py:437-474`

Calculate profit factor (gross profits / gross losses).

```python
def calculate_profit_factor(
    trade_returns: pl.Series
) -> Decimal
```

**Parameters**:
- `trade_returns`: Trade returns series as Polars Series with Decimal values

**Returns**: Profit factor as Decimal (> 1 means profitable strategy)

**Raises**:
- `InsufficientDataError`: If no trades

**Formula**:
```
profit_factor = sum(returns where returns > 0) / abs(sum(returns where returns < 0))
```

**Example**:
```python
from rustybt.finance.metrics.decimal_metrics import calculate_profit_factor
from decimal import Decimal
import polars as pl

trades = pl.Series("trades", [
    Decimal("100"),   # Win $100
    Decimal("-50"),   # Loss $50
    Decimal("75"),    # Win $75
    Decimal("-25"),   # Loss $25
])

pf = calculate_profit_factor(trades)

# PF = (100 + 75) / (50 + 25) = 175 / 75 = 2.33
print(f"Profit Factor: {pf:.2f}")

# Interpretation:
# - PF > 1.0: Profitable strategy
# - PF = 2.0: For every $1 lost, you make $2
# - PF < 1.0: Losing strategy
# - PF = 1.0: Breakeven

# Example: Low win rate, high profit factor
asymmetric_trades = pl.Series("trades", [
    Decimal("-10"), Decimal("-10"), Decimal("-10"),  # 3 small losses
    Decimal("50"),                                    # 1 large win
])

pf_asymmetric = calculate_profit_factor(asymmetric_trades)
print(f"Asymmetric PF: {pf_asymmetric:.2f}")  # PF = 50/30 = 1.67

# Win rate = 25%, but still profitable!
```

---

## Benchmark Comparison Metrics

### calculate_excess_return()

**Source**: `decimal_metrics.py:477-502`

Calculate excess returns (strategy - benchmark).

```python
def calculate_excess_return(
    strategy_returns: pl.Series,
    benchmark_returns: pl.Series
) -> pl.Series
```

**Parameters**:
- `strategy_returns`: Strategy returns as Polars Series with Decimal values
- `benchmark_returns`: Benchmark returns as Polars Series with Decimal values

**Returns**: Excess returns as Polars Series with Decimal values

**Raises**:
- `InvalidMetricError`: If series lengths don't match

**Example**:
```python
from rustybt.finance.metrics.decimal_metrics import calculate_excess_return
from decimal import Decimal
import polars as pl

strategy = pl.Series("strategy", [
    Decimal("0.02"), Decimal("0.01"), Decimal("0.015")
])

spy = pl.Series("spy", [
    Decimal("0.015"), Decimal("0.005"), Decimal("0.012")
])

excess = calculate_excess_return(strategy, spy)

print(f"Excess Returns: {list(excess)}")
# Output: [Decimal("0.005"), Decimal("0.005"), Decimal("0.003")]

# Cumulative excess
cumulative_excess = Decimal("1")
for r in excess:
    cumulative_excess *= (Decimal("1") + r)

print(f"Cumulative Excess: {(cumulative_excess - Decimal('1')):.2%}")
```

---

### calculate_information_ratio()

**Source**: `decimal_metrics.py:505-553`

Calculate Information ratio (excess return / tracking error). The Information ratio measures **consistency of outperformance** vs benchmark.

```python
def calculate_information_ratio(
    strategy_returns: pl.Series,
    benchmark_returns: pl.Series,
    annualization_factor: int = 252,
) -> Decimal
```

**Parameters**:
- `strategy_returns`: Strategy returns as Polars Series with Decimal values
- `benchmark_returns`: Benchmark returns as Polars Series with Decimal values
- `annualization_factor`: Days per year (252 for daily, 12 for monthly)

**Returns**: Information ratio as Decimal

**Raises**:
- `InsufficientDataError`: If insufficient data
- `InvalidMetricError`: If tracking error is zero

**Formula**:
```
IR = mean(excess_returns) / std(excess_returns) × √annualization_factor
```

**Example**:
```python
from rustybt.finance.metrics.decimal_metrics import calculate_information_ratio
from decimal import Decimal
import polars as pl

strategy = pl.Series("strategy", [
    Decimal("0.02"), Decimal("0.01"), Decimal("0.015"),
    Decimal("0.005"), Decimal("0.018"), Decimal("0.012"),
])

spy = pl.Series("spy", [
    Decimal("0.015"), Decimal("0.005"), Decimal("0.012"),
    Decimal("0.001"), Decimal("0.014"), Decimal("0.010"),
])

ir = calculate_information_ratio(strategy, spy, annualization_factor=252)

print(f"Information Ratio: {ir:.2f}")

# Interpretation:
# - IR > 0.5: Good alpha generation
# - IR > 1.0: Excellent alpha generation
# - IR < 0: Underperforming benchmark

# IR is like Sharpe ratio for active returns
```

---

### calculate_tracking_error()

**Source**: `decimal_metrics.py:556-595`

Calculate tracking error (standard deviation of excess returns).

```python
def calculate_tracking_error(
    strategy_returns: pl.Series,
    benchmark_returns: pl.Series,
    annualization_factor: int = 252,
) -> Decimal
```

**Parameters**:
- `strategy_returns`: Strategy returns as Polars Series with Decimal values
- `benchmark_returns`: Benchmark returns as Polars Series with Decimal values
- `annualization_factor`: Days per year (252 for daily, 12 for monthly)

**Returns**: Tracking error as Decimal (annualized standard deviation)

**Raises**:
- `InsufficientDataError`: If insufficient data

**Formula**:
```
TE = std(strategy_returns - benchmark_returns) × √annualization_factor
```

**Example**:
```python
from rustybt.finance.metrics.decimal_metrics import calculate_tracking_error
from decimal import Decimal
import polars as pl

# Index fund (low tracking error)
index_fund = pl.Series("fund", [
    Decimal("0.010"), Decimal("0.005"), Decimal("0.012"),
])

spy = pl.Series("spy", [
    Decimal("0.0095"), Decimal("0.0052"), Decimal("0.0118"),
])

te_index = calculate_tracking_error(index_fund, spy)
print(f"Index Fund Tracking Error: {te_index:.2%}")
# Very low TE (< 1%) for index fund

# Active fund (high tracking error)
active_fund = pl.Series("active", [
    Decimal("0.020"), Decimal("-0.005"), Decimal("0.025"),
])

te_active = calculate_tracking_error(active_fund, spy)
print(f"Active Fund Tracking Error: {te_active:.2%}")
# Higher TE (3-8%) for active fund

# Interpretation:
# - Low TE (< 2%): Close to benchmark (index fund)
# - Medium TE (2-6%): Moderate active management
# - High TE (> 6%): Aggressive active management
```

---

## Production Examples

### Example 1: Complete Risk Profile

```python
from rustybt.finance.metrics.decimal_metrics import (
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_max_drawdown,
    calculate_var,
    calculate_cvar,
)
from decimal import Decimal
import polars as pl

# Strategy returns
returns = pl.Series("returns", [
    Decimal("0.01"), Decimal("-0.005"), Decimal("0.015"),
    Decimal("0.002"), Decimal("-0.008"), Decimal("0.012"),
    Decimal("0.005"), Decimal("-0.003"), Decimal("0.018"),
])

# Calculate cumulative returns for drawdown
cumulative = pl.Series("cumulative", [Decimal("1")])
for r in returns:
    cumulative.append(cumulative[-1] * (Decimal("1") + r))

# Comprehensive risk profile
risk_profile = {
    "sharpe_ratio": calculate_sharpe_ratio(returns, Decimal("0.02"), 252),
    "sortino_ratio": calculate_sortino_ratio(returns, Decimal("0.02"), 252),
    "max_drawdown": calculate_max_drawdown(cumulative),
    "var_95": calculate_var(returns, Decimal("0.05")),
    "cvar_95": calculate_cvar(returns, Decimal("0.05")),
    "var_99": calculate_var(returns, Decimal("0.01")),
    "cvar_99": calculate_cvar(returns, Decimal("0.01")),
}

# Display risk profile
for metric, value in risk_profile.items():
    print(f"{metric}: {value:.4f}")

# Risk assessment logic
if risk_profile["sharpe_ratio"] > Decimal("1.5"):
    print("✓ Strong risk-adjusted returns")

if risk_profile["max_drawdown"] > Decimal("-0.15"):
    print("✓ Acceptable drawdown")
else:
    print("⚠  High drawdown - review position sizing")
```

---

### Example 2: Trade Analysis

```python
from rustybt.finance.metrics.decimal_metrics import (
    calculate_win_rate,
    calculate_profit_factor,
)
from decimal import Decimal
import polars as pl

# Closed trades
trades = pl.Series("trades", [
    Decimal("0.05"), Decimal("-0.02"), Decimal("0.03"),
    Decimal("-0.01"), Decimal("0.07"), Decimal("-0.015"),
    Decimal("0.04"), Decimal("-0.025"), Decimal("0.06"),
])

win_rate = calculate_win_rate(trades)
profit_factor = calculate_profit_factor(trades)

print(f"Win Rate: {win_rate:.2%}")
print(f"Profit Factor: {profit_factor:.2f}")

# Trade quality assessment
avg_winner = sum(t for t in trades if t > 0) / len([t for t in trades if t > 0])
avg_loser = abs(sum(t for t in trades if t < 0) / len([t for t in trades if t < 0]))

print(f"Avg Winner: {avg_winner:.2%}")
print(f"Avg Loser: {avg_loser:.2%}")
print(f"Win/Loss Ratio: {(avg_winner / avg_loser):.2f}")

# Trading edge analysis
if win_rate > Decimal("0.5") and profit_factor > Decimal("1.5"):
    print("✓ Strong trading edge")
elif profit_factor > Decimal("2.0"):
    print("✓ High profit factor compensates for lower win rate")
else:
    print("⚠  Weak trading edge - review strategy")
```

---

### Example 3: Benchmark Comparison

```python
from rustybt.finance.metrics.decimal_metrics import (
    calculate_information_ratio,
    calculate_tracking_error,
    calculate_excess_return,
)
from decimal import Decimal
import polars as pl

# Strategy vs SPY
strategy = pl.Series("strategy", [
    Decimal("0.012"), Decimal("-0.008"), Decimal("0.015"),
    Decimal("0.002"), Decimal("-0.005"), Decimal("0.018"),
])

spy = pl.Series("spy", [
    Decimal("0.010"), Decimal("-0.006"), Decimal("0.013"),
    Decimal("0.001"), Decimal("-0.004"), Decimal("0.014"),
])

# Benchmark comparison metrics
excess = calculate_excess_return(strategy, spy)
ir = calculate_information_ratio(strategy, spy, 252)
te = calculate_tracking_error(strategy, spy, 252)

print(f"Information Ratio: {ir:.2f}")
print(f"Tracking Error: {te:.2%}")
print(f"Mean Excess Return: {Decimal(str(excess.mean())):.2%}")

# Alpha assessment
if ir > Decimal("0.5"):
    print("✓ Generating alpha consistently")
elif ir < Decimal("0"):
    print("⚠  Underperforming benchmark")

# Tracking error assessment
if te < Decimal("0.02"):
    print("✓ Low tracking error (index-like)")
elif te > Decimal("0.08"):
    print("⚠  High tracking error (aggressive active)")
```

---

### Example 4: Monthly vs Daily Metrics

```python
from rustybt.finance.metrics.decimal_metrics import (
    calculate_sharpe_ratio,
    calculate_var,
)
from decimal import Decimal
import polars as pl

# Daily returns (252 trading days)
daily_returns = pl.Series("daily", [
    Decimal(str(random.gauss(0.001, 0.015))) for _ in range(252)
])

# Monthly returns (12 months)
monthly_returns = pl.Series("monthly", [
    Decimal(str(random.gauss(0.02, 0.05))) for _ in range(12)
])

# Calculate Sharpe for both frequencies
sharpe_daily = calculate_sharpe_ratio(
    daily_returns,
    risk_free_rate=Decimal("0.02"),
    annualization_factor=252,  # Daily
)

sharpe_monthly = calculate_sharpe_ratio(
    monthly_returns,
    risk_free_rate=Decimal("0.02"),
    annualization_factor=12,  # Monthly
)

print(f"Sharpe (Daily):   {sharpe_daily:.2f}")
print(f"Sharpe (Monthly): {sharpe_monthly:.2f}")

# VaR for both frequencies
var_daily_95 = calculate_var(daily_returns, Decimal("0.05"))
var_monthly_95 = calculate_var(monthly_returns, Decimal("0.05"))

print(f"Daily 95% VaR:   {var_daily_95:.2%}")
print(f"Monthly 95% VaR: {var_monthly_95:.2%}")
```

---

## Best Practices

### 1. Use Appropriate Annualization Factor

```python
# Daily data
sharpe_daily = calculate_sharpe_ratio(returns, annualization_factor=252)

# Monthly data
sharpe_monthly = calculate_sharpe_ratio(returns, annualization_factor=12)

# Hourly crypto data
sharpe_hourly = calculate_sharpe_ratio(returns, annualization_factor=365*24)
```

### 2. Handle Edge Cases

```python
# Check for sufficient data
if len(returns) < 20:
    print("Warning: Insufficient data for reliable metrics")

# Handle zero volatility
try:
    sharpe = calculate_sharpe_ratio(returns)
except InsufficientDataError:
    sharpe = Decimal("0")
```

### 3. Use CVaR Over VaR for Risk Management

```python
# CVaR is preferred for risk limits
cvar_95 = calculate_cvar(returns, Decimal("0.05"))

# Risk limit: halt if CVaR exceeds -3%
if cvar_95 < Decimal("-0.03"):
    print("Risk limit breached!")
```

### 4. Combine Multiple Metrics

```python
# No single metric tells the full story
sharpe = calculate_sharpe_ratio(returns)
max_dd = calculate_max_drawdown(cumulative)
win_rate = calculate_win_rate(trades)

# Assess overall quality
if sharpe > Decimal("1.5") and max_dd > Decimal("-0.20") and win_rate > Decimal("0.5"):
    print("High-quality strategy")
```

---

## Related Documentation

- **Performance Tracking**: DecimalMetricsTracker for automatic metric calculation
- **Analytics Suite**: Attribution analysis and formatting utilities
- **Risk Management**: Portfolio-level risk management with limits
- **DecimalConfig**: Precision configuration for Decimal calculations

---

## Source Code References

All metrics documented above are verified against source code:

- `calculate_sharpe_ratio`: `decimal_metrics.py:44-104`
- `calculate_sortino_ratio`: `decimal_metrics.py:107-180`
- `calculate_max_drawdown`: `decimal_metrics.py:183-247`
- `calculate_calmar_ratio`: `decimal_metrics.py:250-307`
- `calculate_var`: `decimal_metrics.py:310-348`
- `calculate_cvar`: `decimal_metrics.py:351-397`
- `calculate_win_rate`: `decimal_metrics.py:400-434`
- `calculate_profit_factor`: `decimal_metrics.py:437-474`
- `calculate_excess_return`: `decimal_metrics.py:477-502`
- `calculate_information_ratio`: `decimal_metrics.py:505-553`
- `calculate_tracking_error`: `decimal_metrics.py:556-595`

---

**Last Verified**: 2025-10-16
**Source Version**: RustyBT v1.0 (Epic 11 Documentation)
**Verification**: 100% of APIs verified against source code
