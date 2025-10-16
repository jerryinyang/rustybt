# Risk Analytics

Comprehensive risk analysis framework for backt

est results, including Value at Risk (VaR), Conditional VaR (CVaR), stress testing, beta analysis, and tail risk metrics.

## Overview

**Purpose**: Quantify portfolio risk using industry-standard methodologies:
- **VaR**: Maximum expected loss at given confidence levels (Basel III)
- **CVaR**: Average loss beyond VaR threshold (Expected Shortfall)
- **Stress Testing**: Historical crisis scenarios (2008, COVID, Flash Crash)
- **Beta Analysis**: Market sensitivity and systematic risk
- **Tail Risk**: Skewness, kurtosis, maximum losses
- **Risk Decomposition**: Component VaR per position

**When to Use**:
- ✅ Before deploying strategies to production
- ✅ For investor reporting and risk disclosures
- ✅ To set position limits and risk budgets
- ✅ For regulatory compliance (if applicable)

---

## Quick Start

### Basic VaR Analysis

```python
from rustybt.analytics.risk import RiskAnalytics
import pandas as pd

# Load backtest results with 'returns' or 'portfolio_value' column
backtest_df = pd.read_parquet("backtest_results.parquet")

# Initialize risk analytics
risk = RiskAnalytics(
    backtest_result=backtest_df,
    confidence_levels=[0.95, 0.99]  # 95% and 99% confidence
)

# Calculate VaR using historical method
var_results = risk.calculate_var(method='historical')
print(f"95% VaR: {var_results['var_95']}")  # e.g., -0.0250 = -2.5% daily loss
print(f"99% VaR: {var_results['var_99']}")  # e.g., -0.0420 = -4.2% daily loss

# Interpret:
# - 95% VaR = -0.025 means:
#   "We expect to lose more than 2.5% on only 5% of trading days"
```

### Stress Testing

```python
# Run predefined historical crisis scenarios
stress_results = risk.run_stress_tests()

print(f"2008 Financial Crisis: {stress_results['2008_financial_crisis']}")  # Est. loss: -$50,000
print(f"COVID-19 Crash: {stress_results['covid_crash']}")                    # Est. loss: -$35,000
print(f"Flash Crash: {stress_results['flash_crash']}")                       # Est. loss: -$10,000

# Interpret: Portfolio would lose $50K in 2008-style crisis
```

### Comprehensive Risk Report

```python
# Run all risk analyses
risk_report = risk.analyze_risk()

# VaR and CVaR
print("=== Value at Risk ===")
print(risk_report['var'])    # {'var_95': Decimal('-0.025'), 'var_99': Decimal('-0.042')}
print(risk_report['cvar'])   # {'cvar_95': Decimal('-0.035'), 'cvar_99': Decimal('-0.055')}

# Tail risk metrics
print("\n=== Tail Risk ===")
print(f"Skewness: {risk_report['tail_risk']['skewness']}")          # -0.5 (negative skew)
print(f"Kurtosis: {risk_report['tail_risk']['kurtosis']}")          # 3.2 (fat tails)
print(f"Max 1-day loss: {risk_report['tail_risk']['max_loss_1d']}")  # -8.5%

# Beta analysis (if benchmark provided)
if 'beta' in risk_report:
    print(f"\nBeta: {risk_report['beta']['beta']}")                  # 1.2 (more volatile than market)
    print(f"Alpha: {risk_report['beta']['alpha']}")                  # 0.05% daily
```

---

## API Reference

### RiskAnalytics

```python
from rustybt.analytics.risk import RiskAnalytics

class RiskAnalytics:
    """Comprehensive risk analytics for backtest results."""

    def __init__(
        self,
        backtest_result: pd.DataFrame | pl.DataFrame,
        confidence_levels: list[float] | None = None,
        benchmark_returns: pd.Series | None = None,
        positions: pd.DataFrame | None = None,
    ):
        """Initialize risk analytics.

        Args:
            backtest_result: Backtest results with 'returns' or 'portfolio_value' column.
                           Must have DatetimeIndex.
            confidence_levels: Confidence levels for VaR/CVaR (e.g., [0.95, 0.99]).
                              Default: [0.95, 0.99]
            benchmark_returns: Optional benchmark returns (e.g., SPY) for beta calculation.
                              Must have same frequency and aligned dates.
            positions: Optional positions data for risk decomposition.
                      Format 1: DataFrame with 'symbol' and 'value' columns
                      Format 2: DataFrame with '{symbol}_returns' columns

        Raises:
            InsufficientDataError: If < 30 observations (minimum for reliable statistics)
            ValueError: If backtest_result missing required columns
        """
```

---

### calculate_var()

```python
def calculate_var(
    self,
    method: str = "historical"
) -> dict[str, Decimal]:
    """Calculate Value at Risk at multiple confidence levels.

    VaR is the maximum expected loss at a given confidence level over
    a time horizon (typically 1 day). It answers: "What's the worst loss
    we can expect on 95% of days?"

    Args:
        method: VaR calculation method
            - 'parametric': Assumes normal distribution (fast, unreliable for fat tails)
            - 'historical': Uses empirical quantiles (no assumptions, robust)
            - 'montecarlo': Simulation-based (flexible, slower)

    Returns:
        Dictionary with VaR for each confidence level.
        Keys: 'var_95', 'var_99', etc.
        Values: Negative numbers indicate losses (e.g., -0.025 = -2.5% loss)

    Example:
        >>> var = risk.calculate_var(method='historical')
        >>> print(f"95% VaR: {var['var_95']}")  # -0.025 = -2.5% max loss on 95% of days
    """
```

**Method Comparison**:

| Method | Assumptions | Pros | Cons | When to Use |
|--------|-------------|------|------|-------------|
| **Parametric** | Normal distribution | Fast, analytical | Poor for fat tails, skewed returns | Only if returns are normally distributed |
| **Historical** | None (empirical) | Robust, no assumptions | Needs sufficient data (100+ obs) | Default choice for most strategies |
| **Monte Carlo** | Estimated distribution | Flexible, captures dynamics | Slowest, depends on estimation | For complex portfolios with dependencies |

---

### calculate_cvar()

```python
def calculate_cvar(
    self,
    method: str = "historical"
) -> dict[str, Decimal]:
    """Calculate Conditional VaR (Expected Shortfall).

    CVaR is the average loss in the worst (1 - confidence_level) % of cases.
    More conservative than VaR and better captures tail risk.

    Formula: CVaR = E[R | R ≤ VaR]
           = mean of returns below VaR threshold

    Properties:
    - CVaR ≥ VaR (in absolute terms)
    - Coherent risk measure (unlike VaR)
    - Captures tail risk better than VaR

    Args:
        method: VaR calculation method ('parametric', 'historical', 'montecarlo')

    Returns:
        Dictionary with CVaR for each confidence level.
        Keys: 'cvar_95', 'cvar_99', etc.

    Example:
        >>> cvar = risk.calculate_cvar(method='historical')
        >>> print(f"95% VaR: {var['var_95']}")    # -0.025 = max loss on 95% of days
        >>> print(f"95% CVaR: {cvar['cvar_95']}")  # -0.035 = avg loss on worst 5% of days

        Interpretation: When things go bad (worst 5% of days),
        we lose 3.5% on average (worse than 2.5% VaR threshold)
    """
```

---

### run_stress_tests()

```python
def run_stress_tests(self) -> dict[str, Decimal]:
    """Run predefined stress test scenarios.

    Applies historical crisis shocks to portfolio to estimate
    potential losses in extreme scenarios.

    Predefined scenarios:
    1. **2008 Financial Crisis**:
       - SPY: -50%, TLT: +20%, GLD: +5%
       - Duration: 18 months (Sep 2007 - Mar 2009)

    2. **COVID-19 Crash** (March 2020):
       - SPY: -35%, TLT: +5%
       - Duration: 1 month (Feb - Mar 2020)

    3. **Flash Crash** (May 2010):
       - SPY: -10% intraday
       - Duration: Minutes (single day event)

    Returns:
        Dictionary mapping scenario name to estimated loss.
        Keys: '2008_financial_crisis', 'covid_crash', 'flash_crash'

    Example:
        >>> stress = risk.run_stress_tests()
        >>> print(f"2008 Crisis Loss: ${stress['2008_financial_crisis']}")  # -$50,000
        >>> print(f"Worst case: ${min(stress.values())}")  # Find worst scenario
    """
```

---

### apply_scenario()

```python
def apply_scenario(
    self,
    scenario: dict[str, float]
) -> Decimal:
    """Apply user-defined scenario to portfolio.

    Create custom "what-if" scenarios by specifying asset-specific shocks.

    Args:
        scenario: Dictionary mapping asset symbols to percentage shocks.
                 Example: {"SPY": -0.20, "TLT": 0.10, "GLD": 0.05}
                 Shocks: -0.20 = -20%, 0.10 = +10%

    Returns:
        Estimated portfolio loss as Decimal

    Requires:
        - positions data provided in __init__()
        - positions must have 'symbol'/'value' or '{symbol}_returns' columns

    Example:
        >>> # Custom scenario: Market crash + bond rally
        >>> scenario = {
        ...     "SPY": -0.30,  # Stocks down 30%
        ...     "TLT": 0.15,   # Bonds up 15%
        ...     "GLD": 0.08    # Gold up 8%
        ... }
        >>> loss = risk.apply_scenario(scenario)
        >>> print(f"Estimated loss: ${loss}")  # -$25,000
    """
```

---

### calculate_beta()

```python
def calculate_beta(self) -> dict[str, Decimal]:
    """Calculate portfolio beta vs benchmark.

    Beta measures sensitivity to market movements using linear regression:
    R_portfolio = α + β * R_benchmark + ε

    Beta Interpretation:
    - β = 1: Moves with market (S&P 500 index funds)
    - β > 1: More volatile than market (tech stocks, leveraged strategies)
    - β < 1: Less volatile than market (defensive stocks, bonds)
    - β < 0: Inverse relationship (gold, some hedge strategies)

    Returns:
        Dictionary with:
        - 'beta': Portfolio beta
        - 'alpha': Jensen's alpha (excess return, annualized)
        - 'r_squared': R² of regression (variance explained by market)

    Requires:
        - benchmark_returns provided in __init__()

    Example:
        >>> beta_results = risk.calculate_beta()
        >>> print(f"Beta: {beta_results['beta']}")  # 1.25 (25% more volatile than market)
        >>> print(f"Alpha: {beta_results['alpha']}")  # 0.05 (5% annual excess return)
        >>> print(f"R²: {beta_results['r_squared']}")  # 0.75 (75% variance explained by market)

        Interpretation: Strategy is 25% more volatile than market,
        generates 5% annual excess return, 75% driven by market movements
    """
```

---

### calculate_tail_risk()

```python
def calculate_tail_risk(self) -> dict[str, Decimal]:
    """Calculate tail risk metrics.

    Returns:
        Dictionary with:
        - 'skewness': Asymmetry of returns distribution
           * 0 = symmetric (normal distribution)
           * < 0 = negative skew (more extreme losses than gains) ⚠️
           * > 0 = positive skew (more extreme gains than losses) ✅

        - 'kurtosis': Fat tails indicator (excess kurtosis)
           * 0 = normal tails (Gaussian)
           * > 0 = fat tails (more extreme events than normal) ⚠️
           * < 0 = thin tails (fewer extreme events)

        - 'max_loss_1d': Maximum 1-day loss
        - 'max_loss_5d': Maximum 5-day cumulative loss
        - 'max_loss_10d': Maximum 10-day cumulative loss

        - 'downside_deviation': Standard deviation of negative returns only
           (semideviation, used in Sortino ratio)

    Example:
        >>> tail = risk.calculate_tail_risk()
        >>> print(f"Skewness: {tail['skewness']}")  # -0.5 (negative skew - BAD)
        >>> print(f"Kurtosis: {tail['kurtosis']}")  # 3.2 (fat tails - BAD)
        >>> print(f"Max 1-day loss: {tail['max_loss_1d']}")  # -8.5%

        Interpretation:
        - Negative skew (-0.5): More extreme losses than gains
        - Positive excess kurtosis (3.2): Fat tails, expect extreme events
        - Combined: High tail risk, parametric VaR will underestimate risk
    """
```

---

### calculate_risk_decomposition()

```python
def calculate_risk_decomposition(
    self,
    confidence: float = 0.95
) -> pd.DataFrame:
    """Calculate risk decomposition (component VaR).

    Decomposes portfolio VaR into contributions from individual positions.
    Useful for identifying risk concentration and rebalancing.

    Formula:
        Marginal VaR_i = (Cov(r_i, r_portfolio) / σ_portfolio) * z_score
        Component VaR_i = weight_i * Marginal VaR_i
        Risk Contribution % = Component VaR_i / Portfolio VaR * 100

    Args:
        confidence: Confidence level for VaR calculation (default: 0.95)

    Returns:
        DataFrame with columns:
        - 'symbol': Asset symbol
        - 'marginal_var': Marginal VaR (change in portfolio VaR per $1 increase in position)
        - 'component_var': Component VaR (contribution to total portfolio VaR)
        - 'risk_contribution_pct': Percentage contribution to portfolio risk

    Requires:
        - positions data with '{symbol}_returns' columns

    Example:
        >>> decomp = risk.calculate_risk_decomposition()
        >>> print(decomp.sort_values('risk_contribution_pct', ascending=False))

             symbol  marginal_var  component_var  risk_contribution_pct
        0      TSLA        0.0450         0.0135                   45.2
        1      AAPL        0.0280         0.0098                   32.8
        2       SPY        0.0180         0.0066                   22.0

        Interpretation: TSLA contributes 45% of portfolio risk despite
        potentially smaller allocation (high volatility + correlation)
    """
```

---

## Complete Examples

### Multi-Method VaR Comparison

```python
from rustybt.analytics.risk import RiskAnalytics
import pandas as pd

# Load backtest results
backtest_df = pd.read_parquet("strategy_results.parquet")

# Initialize
risk = RiskAnalytics(backtest_result=backtest_df, confidence_levels=[0.95, 0.99])

# Compare VaR methods
methods = ['parametric', 'historical', 'montecarlo']
results = {}

for method in methods:
    var = risk.calculate_var(method=method)
    cvar = risk.calculate_cvar(method=method)

    results[method] = {
        'var_95': var['var_95'],
        'cvar_95': cvar['cvar_95']
    }

# Compare results
import pandas as pd
comparison = pd.DataFrame(results).T
print(comparison)

# Output:
#              var_95   cvar_95
# parametric  -0.0220  -0.0295
# historical  -0.0250  -0.0335
# montecarlo  -0.0245  -0.0328

# Interpretation:
# - Historical VaR most conservative (-2.5% vs -2.2% parametric)
# - Parametric underestimates risk (assumes normal distribution)
# - Use historical or Monte Carlo for fat-tailed returns
```

---

### Complete Risk Assessment

```python
from rustybt.analytics.risk import RiskAnalytics
import pandas as pd

# Load data
backtest_df = pd.read_parquet("backtest_results.parquet")
spy_returns = pd.read_parquet("spy_returns.parquet")['returns']
positions_df = pd.read_parquet("positions.parquet")  # Has 'symbol', 'value' columns

# Initialize with all optional data
risk = RiskAnalytics(
    backtest_result=backtest_df,
    confidence_levels=[0.90, 0.95, 0.99],  # Multiple confidence levels
    benchmark_returns=spy_returns,
    positions=positions_df
)

# 1. VaR and CVaR
print("=== Value at Risk ===")
var = risk.calculate_var(method='historical')
cvar = risk.calculate_cvar(method='historical')

for conf in [0.90, 0.95, 0.99]:
    var_key = f'var_{int(conf * 100)}'
    cvar_key = f'cvar_{int(conf * 100)}'
    print(f"{int(conf*100)}% VaR: {var[var_key]:.4f}, CVaR: {cvar[cvar_key]:.4f}")

# 2. Stress tests
print("\n=== Stress Tests ===")
stress = risk.run_stress_tests()
for scenario, loss in stress.items():
    print(f"{scenario}: ${float(loss):,.2f}")

# 3. Tail risk
print("\n=== Tail Risk ===")
tail = risk.calculate_tail_risk()
print(f"Skewness: {tail['skewness']:.3f}")
print(f"Kurtosis: {tail['kurtosis']:.3f}")
print(f"Max 1-day loss: {tail['max_loss_1d']:.2%}")
print(f"Downside deviation: {tail['downside_deviation']:.4f}")

# 4. Beta analysis
print("\n=== Beta Analysis ===")
beta_results = risk.calculate_beta()
print(f"Beta: {beta_results['beta']:.3f}")
print(f"Alpha: {beta_results['alpha']:.4f}")
print(f"R²: {beta_results['r_squared']:.3f}")

# 5. Risk decomposition
print("\n=== Risk Decomposition ===")
decomp = risk.calculate_risk_decomposition()
print(decomp.sort_values('risk_contribution_pct', ascending=False))

# 6. Custom scenario
print("\n=== Custom Scenario: Tech Crash ===")
tech_crash = {
    'AAPL': -0.25,
    'MSFT': -0.28,
    'GOOGL': -0.30,
    'TSLA': -0.40
}
loss = risk.apply_scenario(tech_crash)
print(f"Estimated loss: ${float(loss):,.2f}")

# 7. Visualizations
risk.plot_var_distribution(method='historical', confidence=0.95)
risk.plot_stress_test_results()
risk.plot_correlation_heatmap()  # If positions provided
```

---

## Interpretation Guide

### VaR Interpretation

**VaR at 95% confidence = -2.5%**

Meaning:
- On 95% of trading days, we expect to lose less than 2.5%
- On 5% of trading days (1 in 20), we expect to lose more than 2.5%
- Over 100 trading days, expect ~5 days with losses > 2.5%

**VaR is NOT**:
- ❌ Maximum possible loss (there's always a worse scenario)
- ❌ Average loss (that's CVaR)
- ❌ Drawdown (VaR is 1-day horizon, drawdown is peak-to-trough)

**VaR IS**:
- ✅ Threshold loss exceeded on X% of days
- ✅ Risk budget metric (position limits based on VaR)
- ✅ Regulatory compliance metric (Basel III)

---

### CVaR Interpretation

**CVaR at 95% confidence = -3.5%**

Meaning:
- When we have a "bad day" (worst 5% of days), we lose 3.5% on average
- CVaR > VaR (in absolute terms) always
- More conservative than VaR, better for risk management

Example:
```
95% VaR = -2.5%
95% CVaR = -3.5%

Interpretation:
- VaR: Threshold is -2.5% (5% of days exceed this)
- CVaR: Average loss on those bad days is -3.5%
```

---

### Skewness and Kurtosis

**Skewness**:
- **-0.5 (negative skew)**: More extreme losses than gains ⚠️
  - Bad for investors (asymmetric risk)
  - Common in equity strategies (crash risk)
  - Parametric VaR underestimates risk

- **+0.5 (positive skew)**: More extreme gains than losses ✅
  - Good for investors
  - Rare in practice
  - Common in some option strategies

**Kurtosis** (excess kurtosis):
- **+3.0 (fat tails)**: More extreme events than normal distribution ⚠️
  - Bad: Expect more "black swan" events
  - Parametric VaR severely underestimates risk
  - Use historical or Monte Carlo VaR

- **0.0 (normal tails)**: Gaussian distribution
  - Rare in financial markets
  - Parametric VaR acceptable

---

### Beta Interpretation

**Beta = 1.25**

Meaning:
- Portfolio is 25% more volatile than benchmark
- If market moves 10%, portfolio moves 12.5% (on average)
- Higher systematic risk

**Beta Ranges**:
- **β < 0**: Inverse relationship (hedged strategies, gold)
- **0 < β < 1**: Defensive (lower volatility than market)
- **β = 1**: Tracks market (index funds)
- **β > 1**: Aggressive (higher volatility than market)
- **β > 1.5**: Very aggressive (leveraged, high-beta stocks)

**Alpha Interpretation**:
- **α > 0**: Outperforming benchmark (skill) ✅
- **α ≈ 0**: Matching benchmark
- **α < 0**: Underperforming benchmark ⚠️

Note: Check `alpha_significant` to see if alpha is statistically significant (p < 0.05)

---

## Best Practices

### ✅ DO

1. **Use multiple VaR methods** for robustness
   ```python
   var_hist = risk.calculate_var(method='historical')
   var_mc = risk.calculate_var(method='montecarlo')
   # Compare results, use most conservative
   ```

2. **Always calculate CVaR alongside VaR**
   ```python
   var = risk.calculate_var()
   cvar = risk.calculate_cvar()  # More conservative, captures tail risk
   ```

3. **Check tail risk metrics** before using parametric VaR
   ```python
   tail = risk.calculate_tail_risk()
   if abs(tail['skewness']) > 1.0 or tail['kurtosis'] > 3.0:
       # Use historical or Monte Carlo VaR (fat tails detected)
       var = risk.calculate_var(method='historical')
   ```

4. **Run stress tests** for extreme scenarios
   ```python
   stress = risk.run_stress_tests()
   # Know worst-case losses before deploying
   ```

5. **Calculate beta** to understand market dependency
   ```python
   beta_results = risk.calculate_beta()
   # High beta = high market risk, needs higher expected return
   ```

6. **Check sufficient data** (minimum 30 observations, prefer 100+)
   ```python
   if len(backtest_df) < 100:
       print("⚠️ Warning: Limited data for reliable VaR estimates")
   ```

---

### ❌ DON'T

1. **Don't use parametric VaR for fat-tailed returns**
   ```python
   # BAD: Parametric VaR with fat tails
   tail = risk.calculate_tail_risk()
   if tail['kurtosis'] > 3.0:
       var = risk.calculate_var(method='parametric')  # WRONG: Underestimates risk

   # GOOD: Use historical or Monte Carlo
   var = risk.calculate_var(method='historical')  # CORRECT
   ```

2. **Don't rely on VaR alone**
   ```python
   # BAD: Only VaR
   var = risk.calculate_var()

   # GOOD: VaR + CVaR + stress tests
   var = risk.calculate_var()
   cvar = risk.calculate_cvar()
   stress = risk.run_stress_tests()
   ```

3. **Don't ignore statistical significance**
   ```python
   # BAD: Assuming alpha is meaningful
   alpha = beta_results['alpha']

   # GOOD: Check significance
   if beta_results['alpha_significant']:
       print("Alpha is statistically significant")
   else:
       print("Alpha may be due to chance")
   ```

4. **Don't use insufficient data**
   ```python
   # BAD: VaR with 20 observations
   risk = RiskAnalytics(backtest_result)  # Only 20 rows
   var = risk.calculate_var()  # Unreliable

   # GOOD: Ensure sufficient data
   if len(backtest_df) >= 100:
       var = risk.calculate_var()  # Reliable
   ```

---

## Common Pitfalls

### Pitfall 1: Confusing VaR with Maximum Loss

```python
# WRONG interpretation
var_95 = -0.025
print("Maximum possible loss is 2.5%")  # WRONG

# CORRECT interpretation
var_95 = -0.025
print("On 95% of days, loss is less than 2.5%")  # CORRECT
print("On 5% of days, loss exceeds 2.5% (could be much worse)")  # CORRECT
```

**Why**: VaR is a threshold, not a maximum. Tail losses can be much worse.

---

### Pitfall 2: Using Wrong Confidence Level

```python
# BAD: Too low confidence level
var_80 = risk.calculate_var()  # 80% confidence (too optimistic)

# GOOD: Industry standard confidence levels
var_95 = risk.calculate_var(confidence_levels=[0.95, 0.99])
# 95% for internal risk management, 99% for regulatory
```

---

### Pitfall 3: Not Scaling VaR to Portfolio Size

```python
# VaR is percentage
var_95 = -0.025  # -2.5%

# BAD: Report percentage only
print(f"VaR: {var_95}")

# GOOD: Scale to portfolio value
portfolio_value = 1000000  # $1M
var_dollar = portfolio_value * abs(float(var_95))
print(f"95% VaR: ${var_dollar:,.0f}")  # $25,000
```

---

### Pitfall 4: Ignoring Time Horizon

```python
# VaR is 1-day by default
var_1d = -0.025  # 2.5% daily VaR

# BAD: Assume this is monthly VaR
monthly_var = var_1d  # WRONG

# GOOD: Scale to longer horizon (if needed)
import numpy as np
trading_days_per_month = 21
var_monthly = var_1d * np.sqrt(trading_days_per_month)  # ~11.5% monthly
# Note: Assumes IID returns (often violated)
```

---

## Visualization

### VaR Distribution Plot

```python
# Plot returns distribution with VaR threshold
fig = risk.plot_var_distribution(
    method='historical',
    confidence=0.95,
    bins=50,
    figsize=(10, 6)
)
plt.savefig('var_distribution.png', dpi=150, bbox_inches='tight')
```

### Stress Test Results

```python
# Plot stress test results as bar chart
fig = risk.plot_stress_test_results(figsize=(10, 6))
plt.savefig('stress_tests.png', dpi=150, bbox_inches='tight')
```

### Correlation Heatmap

```python
# Plot asset correlation matrix (requires positions data)
fig = risk.plot_correlation_heatmap(figsize=(10, 8))
plt.savefig('correlation.png', dpi=150, bbox_inches='tight')
```

---

## See Also

- [Analytics Suite Overview](../README.md)
- [Performance Attribution](../attribution/README.md)
- [Trade Analysis](../trade-analysis/README.md)
- [Optimization Framework](../../optimization/README.md)

---

## References

### Academic Sources

1. **VaR and CVaR**:
   - Jorion, P. (2007). *Value at Risk: The New Benchmark for Managing Financial Risk*. McGraw-Hill.
   - Rockafellar, R. T., & Uryasev, S. (2000). "Optimization of Conditional Value-at-Risk". *Journal of Risk*.

2. **Tail Risk**:
   - Taleb, N. N. (2007). *The Black Swan: The Impact of the Highly Improbable*. Random House.
   - Mandelbrot, B., & Hudson, R. L. (2004). *The (Mis)behavior of Markets*. Basic Books.

3. **Beta Analysis**:
   - Sharpe, W. F. (1964). "Capital Asset Prices: A Theory of Market Equilibrium". *Journal of Finance*.
   - Jensen, M. C. (1968). "The Performance of Mutual Funds". *Journal of Finance*.

4. **Basel III**:
   - Basel Committee on Banking Supervision. (2019). *Minimum Capital Requirements for Market Risk*. BIS.

---

*Last Updated: 2025-10-16 | RustyBT v1.0*
