# Performance Attribution

Performance attribution decomposes portfolio returns to identify sources of performance: alpha (skill), beta (market exposure), factor exposures, timing ability, and selection skill.

## Overview

**Purpose**: Answer the question "Where did returns come from?"
- **Alpha/Beta**: Skill-based excess returns vs. market-driven returns
- **Factor Attribution**: Exposure to risk factors (size, value, momentum)
- **Timing Attribution**: Market timing skill (entering/exiting at right times)
- **Selection Attribution**: Security selection skill within asset classes
- **Rolling Attribution**: How attribution changes over time

**When to Use**:
- ✅ To understand return drivers (skill vs. luck vs. market)
- ✅ For investor reporting and transparency
- ✅ To compare strategies on risk-adjusted basis
- ✅ To validate that alpha is statistically significant

---

## Quick Start

### Basic Alpha/Beta Decomposition

```python
from rustybt.analytics.attribution import PerformanceAttribution
import pandas as pd

# Load backtest results and benchmark
backtest_df = pd.read_parquet("backtest_results.parquet")  # Must have DatetimeIndex
spy_returns = pd.read_parquet("spy_returns.parquet")['returns']

# Initialize attribution analyzer
attrib = PerformanceAttribution(
    backtest_result=backtest_df,
    benchmark_returns=spy_returns
)

# Run attribution analysis
results = attrib.analyze_attribution()

# Alpha and beta
print(f"Alpha (daily): {results['alpha_beta']['alpha']:.6f}")
print(f"Alpha (annual): {results['alpha_beta']['alpha_annualized']:.4f}")
print(f"Beta: {results['alpha_beta']['beta']:.3f}")
print(f"R²: {results['alpha_beta']['r_squared']:.3f}")
print(f"Alpha p-value: {results['alpha_beta']['alpha_pvalue']:.4f}")
print(f"Alpha significant: {results['alpha_beta']['alpha_significant']}")

# Information ratio
print(f"\nInformation Ratio: {results['alpha_beta']['information_ratio']:.2f}")
print(f"Tracking Error: {results['alpha_beta']['tracking_error']:.4f}")

# Interpretation:
# - Alpha = 0.0005 (daily) = 0.1260 (annual) = 12.6% annual excess return
# - Beta = 1.25 = 25% more volatile than market
# - R² = 0.75 = 75% of variance explained by market
# - p-value = 0.03 < 0.05 = alpha is statistically significant
```

**Interpretation**:
- **Positive alpha**: Strategy outperforms benchmark after adjusting for risk
- **Statistical significance**: p-value < 0.05 means alpha is not due to luck
- **Information Ratio**: Risk-adjusted alpha (higher = better)
- **R²**: How much performance is driven by market vs. strategy

---

### Multi-Factor Attribution

```python
# Load Fama-French factors
ff_factors = pd.read_parquet("fama_french_factors.parquet")
# Columns: 'Mkt-RF', 'SMB', 'HML', 'RMW', 'CMA', 'Mom'

# Attribution with factor model
attrib = PerformanceAttribution(
    backtest_result=backtest_df,
    benchmark_returns=spy_returns,
    factor_returns=ff_factors,  # Fama-French factors
    risk_free_rate=0.02         # 2% risk-free rate (annual)
)

results = attrib.analyze_attribution()

# Factor loadings (betas)
print("=== Factor Exposures ===")
for factor, loading in results['factor_attribution']['factor_loadings'].items():
    print(f"{factor}: {loading:.3f}")

# Output:
# Mkt-RF: 1.15   (15% more market exposure than index)
# SMB: 0.25      (Positive small-cap tilt)
# HML: -0.10     (Negative value tilt, growth bias)
# Mom: 0.35      (Strong momentum exposure)

# Factor contributions to return
print("\n=== Factor Contributions ===")
for factor, contrib in results['factor_attribution']['factor_contributions'].items():
    print(f"{factor}: {contrib:.4f}")

# Alpha after controlling for factors
print(f"\nFactor-adjusted alpha: {results['factor_attribution']['alpha']:.6f}")
print(f"R²: {results['factor_attribution']['r_squared']:.3f}")
```

**Interpretation**:
- **Factor loadings**: Exposure to each risk factor
- **Factor contributions**: Return attributable to each factor
- **Factor-adjusted alpha**: Excess return after controlling for all factors
- **Higher R²**: Strategy explained more by factors (less unique skill)

---

### Timing Attribution

```python
# Timing attribution (Merton-Henriksson test)
attrib = PerformanceAttribution(
    backtest_result=backtest_df,
    benchmark_returns=spy_returns
)

results = attrib.analyze_attribution()

# Timing analysis
print("=== Market Timing Analysis ===")
print(f"Timing coefficient: {results['timing']['timing_coefficient']:.4f}")
print(f"Timing p-value: {results['timing']['timing_pvalue']:.4f}")
print(f"Has timing skill: {results['timing']['has_timing_skill']}")
print(f"Timing direction: {results['timing']['timing_direction']}")

# Interpretation:
# timing_coefficient > 0 and p < 0.05 = Positive timing skill
# timing_coefficient < 0 = Negative timing (worse in up markets)
```

**Interpretation**:
- **Positive timing coefficient**: Higher market exposure in up markets (good timing)
- **Negative timing coefficient**: Higher exposure in down markets (bad timing)
- **Statistical significance**: p-value < 0.05 confirms timing is not luck

---

## API Reference

### PerformanceAttribution

```python
from rustybt.analytics.attribution import PerformanceAttribution

class PerformanceAttribution:
    """Analyze performance attribution for backtest results."""

    def __init__(
        self,
        backtest_result: pd.DataFrame | pl.DataFrame,
        benchmark_returns: pd.Series | pl.Series | None = None,
        factor_returns: pd.DataFrame | None = None,
        risk_free_rate: pd.Series | float | None = None,
    ):
        """Initialize performance attribution analyzer.

        Args:
            backtest_result: DataFrame with backtest results. Must contain either:
                - 'returns' column (preferred), OR
                - 'portfolio_value' or 'ending_value' column (returns calculated)
                Must have DatetimeIndex.

            benchmark_returns: Optional benchmark returns (e.g., SPY) for alpha/beta.
                Must have same frequency as backtest_result.
                Should be aligned on dates (inner join used).

            factor_returns: Optional factor returns DataFrame (e.g., Fama-French).
                Columns: factor names ('Mkt-RF', 'SMB', 'HML', 'RMW', 'CMA', 'Mom')
                Index: dates matching backtest frequency
                Common sources:
                - Kenneth French Data Library
                - AQR Capital Management
                - Custom factor models

            risk_free_rate: Optional risk-free rate for excess return calculations.
                - float: Constant rate (e.g., 0.02 for 2% annual)
                - pd.Series: Time-varying rate (matched to dates)
                Default: 0.0 (no risk-free rate adjustment)

        Raises:
            ValueError: If backtest_result is invalid or missing required columns
            ValueError: If backtest_result index is not DatetimeIndex

        Example:
            >>> attrib = PerformanceAttribution(
            ...     backtest_result=portfolio_df,
            ...     benchmark_returns=spy_returns,
            ...     factor_returns=ff_3factor,
            ...     risk_free_rate=0.02
            ... )
        """
```

---

### analyze_attribution()

```python
def analyze_attribution(self) -> dict[str, Any]:
    """Run comprehensive attribution analysis.

    Performs all available attribution analyses based on provided data:
    - Alpha/beta decomposition (if benchmark provided)
    - Factor attribution (if factor returns provided)
    - Timing attribution (if benchmark provided)
    - Selection attribution (if holdings data available)
    - Interaction attribution (if holdings data available)
    - Rolling attribution (if benchmark provided and sufficient data)

    Returns:
        Dictionary containing:
        {
            'summary': {
                'total_return': Decimal,        # Total portfolio return
                'n_observations': int,           # Number of return observations
                'start_date': datetime,          # First date
                'end_date': datetime,            # Last date
                'attribution_reconciles': bool   # Whether attribution sums to total
            },

            'alpha_beta': {  # If benchmark provided
                'alpha': Decimal,                      # Daily alpha (intercept)
                'alpha_annualized': Decimal,           # Annualized alpha
                'beta': Decimal,                       # Market beta
                'alpha_pvalue': float,                 # P-value for alpha (< 0.05 = significant)
                'alpha_tstat': float,                  # T-statistic for alpha
                'alpha_significant': bool,             # Whether alpha significant (p < 0.05)
                'information_ratio': Decimal,          # Alpha / tracking_error
                'information_ratio_annualized': Decimal,
                'r_squared': Decimal,                  # Variance explained by benchmark
                'tracking_error': Decimal,             # Std of excess returns
                'tracking_error_annualized': Decimal,
                'n_observations': int
            },

            'factor_attribution': {  # If factors provided
                'alpha': Decimal,                      # Factor-adjusted alpha
                'alpha_annualized': Decimal,
                'alpha_pvalue': float,
                'alpha_significant': bool,
                'factor_loadings': dict,               # Factor name -> loading (beta)
                'factor_contributions': dict,          # Factor name -> return contribution
                'r_squared': Decimal,
                'n_observations': int,
                'n_factors': int
            },

            'timing': {  # If benchmark provided
                'timing_coefficient': Decimal,          # Merton-Henriksson gamma
                'timing_pvalue': float,
                'has_timing_skill': bool,              # gamma > 0 and p < 0.05
                'timing_direction': str,               # 'positive' or 'negative'
                'timing_correlation': Decimal | None,  # If leverage data available
                'r_squared': Decimal
            },

            'rolling': {  # If benchmark provided and len >= 30
                'rolling_alpha': pd.Series,            # Time series of alpha
                'rolling_beta': pd.Series,             # Time series of beta
                'rolling_tracking_error': pd.Series,
                'rolling_information_ratio': pd.Series,
                'window_size': int
            }
        }

    Raises:
        InsufficientDataError: If < 2 return observations

    Example:
        >>> results = attrib.analyze_attribution()
        >>> print(f"Alpha: {results['alpha_beta']['alpha']}")
        >>> print(f"Significant: {results['alpha_beta']['alpha_significant']}")
    """
```

---

## Complete Examples

### Comprehensive Attribution Analysis

```python
from rustybt.analytics.attribution import PerformanceAttribution
import pandas as pd

# Load data
backtest_df = pd.read_parquet("strategy_results.parquet")
spy_returns = pd.read_parquet("spy_returns.parquet")['returns']
ff_factors = pd.read_parquet("fama_french_5factor.parquet")

# Initialize with all data
attrib = PerformanceAttribution(
    backtest_result=backtest_df,
    benchmark_returns=spy_returns,
    factor_returns=ff_factors,
    risk_free_rate=0.02  # 2% annual risk-free rate
)

# Run comprehensive analysis
results = attrib.analyze_attribution()

# 1. Summary
print("=== Portfolio Summary ===")
print(f"Total return: {results['summary']['total_return']:.2%}")
print(f"Period: {results['summary']['start_date']} to {results['summary']['end_date']}")
print(f"Observations: {results['summary']['n_observations']}")

# 2. Alpha/Beta
print("\n=== Alpha/Beta Analysis ===")
ab = results['alpha_beta']
print(f"Alpha (daily): {ab['alpha']:.6f}")
print(f"Alpha (annual): {ab['alpha_annualized']:.2%}")
print(f"Beta: {ab['beta']:.3f}")
print(f"R²: {ab['r_squared']:.3f}")
print(f"Alpha p-value: {ab['alpha_pvalue']:.4f}")

if ab['alpha_significant']:
    print("✅ Alpha is statistically significant (p < 0.05)")
else:
    print("⚠️ Alpha is NOT statistically significant (may be luck)")

print(f"\nInformation Ratio: {ab['information_ratio_annualized']:.2f}")
print(f"Tracking Error (annual): {ab['tracking_error_annualized']:.2%}")

# 3. Factor Attribution
print("\n=== Factor Attribution ===")
fa = results['factor_attribution']
print(f"Factor-adjusted alpha: {fa['alpha_annualized']:.2%}")
print(f"R²: {fa['r_squared']:.3f}")

print("\nFactor Loadings:")
for factor, loading in fa['factor_loadings'].items():
    print(f"  {factor}: {loading:.3f}")

print("\nFactor Contributions to Return:")
for factor, contrib in fa['factor_contributions'].items():
    print(f"  {factor}: {contrib:.4f}")

# 4. Timing Attribution
print("\n=== Timing Attribution ===")
timing = results['timing']
print(f"Timing coefficient: {timing['timing_coefficient']:.4f}")
print(f"P-value: {timing['timing_pvalue']:.4f}")
print(f"Direction: {timing['timing_direction']}")

if timing['has_timing_skill']:
    print("✅ Statistically significant timing skill detected")
else:
    print("❌ No significant timing skill")

# 5. Rolling Attribution (if available)
if 'rolling' in results:
    print("\n=== Rolling Attribution (30-day window) ===")
    rolling = results['rolling']

    print(f"Latest alpha: {rolling['rolling_alpha'].iloc[-1]:.6f}")
    print(f"Latest beta: {rolling['rolling_beta'].iloc[-1]:.3f}")
    print(f"Latest IR: {rolling['rolling_information_ratio'].iloc[-1]:.2f}")

    # Plot rolling attribution
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)

    # Alpha over time
    axes[0].plot(rolling['rolling_alpha'].index, rolling['rolling_alpha'], label='Rolling Alpha')
    axes[0].axhline(0, color='black', linestyle='--', alpha=0.3)
    axes[0].set_ylabel('Alpha')
    axes[0].set_title('Rolling Attribution Analysis (30-day window)')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    # Beta over time
    axes[1].plot(rolling['rolling_beta'].index, rolling['rolling_beta'], label='Rolling Beta', color='orange')
    axes[1].axhline(1.0, color='black', linestyle='--', alpha=0.3, label='Market Beta')
    axes[1].set_ylabel('Beta')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    # Information Ratio over time
    axes[2].plot(rolling['rolling_information_ratio'].index, rolling['rolling_information_ratio'],
                label='Rolling IR', color='green')
    axes[2].axhline(0, color='black', linestyle='--', alpha=0.3)
    axes[2].set_ylabel('Information Ratio')
    axes[2].set_xlabel('Date')
    axes[2].legend()
    axes[2].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('rolling_attribution.png', dpi=150)
    print("Rolling attribution chart saved to 'rolling_attribution.png'")
```

---

### Fama-French Factor Analysis

```python
# 3-Factor model (classic)
ff_3factor = pd.read_parquet("ff_3factor.parquet")
# Columns: 'Mkt-RF', 'SMB', 'HML'

attrib_3f = PerformanceAttribution(
    backtest_result=backtest_df,
    factor_returns=ff_3factor
)

results_3f = attrib_3f.analyze_attribution()

# 5-Factor model (extended)
ff_5factor = pd.read_parquet("ff_5factor.parquet")
# Columns: 'Mkt-RF', 'SMB', 'HML', 'RMW', 'CMA'

attrib_5f = PerformanceAttribution(
    backtest_result=backtest_df,
    factor_returns=ff_5factor
)

results_5f = attrib_5f.analyze_attribution()

# Compare models
print("=== Model Comparison ===")
print(f"3-Factor R²: {results_3f['factor_attribution']['r_squared']:.3f}")
print(f"5-Factor R²: {results_5f['factor_attribution']['r_squared']:.3f}")

print(f"\n3-Factor Alpha: {results_3f['factor_attribution']['alpha_annualized']:.2%}")
print(f"5-Factor Alpha: {results_5f['factor_attribution']['alpha_annualized']:.2%}")

# Interpretation:
# - Higher R² in 5-factor = better explained by factors
# - Lower alpha in 5-factor = less unexplained performance (less alpha)
# - 5-factor often gives more conservative alpha estimate
```

---

## Interpretation Guide

### Alpha Interpretation

**Alpha = 0.0005 (daily) = 0.126 (annualized) = 12.6% annual**

Meaning:
- Strategy generates 12.6% excess return per year vs. benchmark
- After adjusting for market risk (beta)
- **BUT**: Check statistical significance!

**Statistical Significance**:
```python
if alpha_pvalue < 0.05:
    # Alpha is statistically significant (< 5% chance it's luck)
    # Can claim skill-based outperformance
else:
    # Alpha is NOT statistically significant
    # May be due to luck, not skill
    # Need more data or longer track record
```

**Alpha Ranges**:
- **α < 0**: Underperforming (losing to benchmark after risk adjustment) ⚠️
- **0 ≤ α < 0.05**: Matching benchmark (no excess return)
- **0.05 ≤ α < 0.15**: Good performance (5-15% annual) ✅
- **α ≥ 0.15**: Excellent performance (15%+ annual) ✅✅ (rare, verify significance)

**Information Ratio** (Risk-adjusted alpha):
```python
IR = Alpha / Tracking_Error
```

- **IR < 0.5**: Weak risk-adjusted performance
- **0.5 ≤ IR < 1.0**: Good risk-adjusted performance ✅
- **IR ≥ 1.0**: Excellent risk-adjusted performance ✅✅ (very rare)

---

### Beta Interpretation

**Beta = 1.25**

Meaning:
- Portfolio is 25% more volatile than market
- If market moves 10%, portfolio moves 12.5% (on average)
- Higher systematic risk

**Beta Ranges**:
- **β < 0**: Inverse relationship (hedge strategies, inverse ETFs)
- **0 < β < 1**: Defensive (lower volatility than market)
  - Example: β = 0.6 = Utilities, consumer staples
- **β = 1**: Market-matching (index funds)
- **1 < β < 1.5**: Aggressive (higher volatility than market)
  - Example: β = 1.25 = Tech stocks, growth strategies
- **β > 1.5**: Very aggressive (leveraged strategies, high-beta stocks)

**Risk/Return Tradeoff**:
```python
Expected_Return = Risk_Free_Rate + Beta * Market_Risk_Premium

# Example:
# Risk_Free = 2%, Beta = 1.25, Market_Premium = 8%
# Expected_Return = 2% + 1.25 * 8% = 12%
```

If strategy beta = 1.25, expect ~12% return to justify extra risk.
If alpha = +5%, total expected = 17% ✅

---

### R-Squared Interpretation

**R² = 0.75 (75%)**

Meaning:
- 75% of portfolio variance explained by benchmark
- 25% is idiosyncratic (strategy-specific)
- Higher R² = more market-driven, lower R² = more unique strategy

**R² Ranges**:
- **R² > 0.9**: Highly correlated with benchmark (closet indexing) ⚠️
  - Example: Index funds, most active equity funds
- **0.7 < R² ≤ 0.9**: Moderate correlation
  - Example: Sector funds, factor-tilted strategies
- **0.4 < R² ≤ 0.7**: Low correlation (good diversification) ✅
  - Example: Alternative strategies, multi-asset portfolios
- **R² ≤ 0.4**: Very low correlation (unique strategy) ✅✅
  - Example: Market-neutral, absolute return strategies

**Interpretation**:
- **High R², high alpha**: Outperforming in same direction as market ✅
- **High R², low alpha**: Closet indexing (expensive index fund) ⚠️
- **Low R², high alpha**: Unique alpha source ✅✅ (most desirable)
- **Low R², negative alpha**: Uncorrelated underperformance ❌

---

### Factor Loadings Interpretation

**Example factor loadings**:
```python
'Mkt-RF': 1.15   # Market exposure
'SMB': 0.25      # Small-cap tilt
'HML': -0.10     # Growth bias (negative value tilt)
'Mom': 0.35      # Momentum exposure
```

**Interpretation**:
- **Mkt-RF = 1.15**: 15% more market exposure than index
- **SMB = 0.25**: Positive small-cap tilt (small > large)
- **HML = -0.10**: Growth bias (growth > value)
- **Mom = 0.35**: Strong momentum exposure

**Factor-Adjusted Alpha**:
```python
# Simple alpha/beta
alpha_simple = 0.10  # 10% annual

# After controlling for factors
alpha_adjusted = 0.05  # 5% annual

# Interpretation:
# 5% is from factors (size, value, momentum)
# Only 5% is true skill (factor-adjusted alpha)
```

---

### Timing Coefficient Interpretation

**Merton-Henriksson Model**:
```python
R_portfolio = α + β * R_market + γ * max(R_market, 0) + ε
```

**Timing coefficient (γ)**:
- **γ > 0 and p < 0.05**: Positive timing skill (higher exposure in up markets) ✅
- **γ ≈ 0 or p ≥ 0.05**: No timing skill
- **γ < 0 and p < 0.05**: Negative timing (higher exposure in down markets) ⚠️

**Example**:
```python
timing_coefficient = 0.15
timing_pvalue = 0.03  # < 0.05

# Interpretation: Statistically significant timing skill
# Portfolio increases exposure before market rallies
# and reduces exposure before declines
```

---

## Best Practices

### ✅ DO

1. **Check statistical significance** before claiming alpha
   ```python
   if results['alpha_beta']['alpha_significant']:
       print("Alpha is statistically significant")
   else:
       print("Alpha may be due to luck - need more data")
   ```

2. **Use appropriate benchmark** (match asset class and strategy style)
   ```python
   # CORRECT: Growth strategy vs. growth index
   attrib = PerformanceAttribution(backtest_df, russell_1000_growth)

   # WRONG: Growth strategy vs. value index
   attrib = PerformanceAttribution(backtest_df, russell_1000_value)
   ```

3. **Analyze rolling attribution** to detect regime changes
   ```python
   results = attrib.analyze_attribution()
   rolling = results['rolling']
   # Check if alpha/beta stable over time
   ```

4. **Use multi-factor models** for comprehensive attribution
   ```python
   # Better than simple alpha/beta
   attrib = PerformanceAttribution(
       backtest_df,
       benchmark_returns=spy,
       factor_returns=ff_5factor  # More complete attribution
   )
   ```

5. **Align data frequencies** (daily to daily, monthly to monthly)
   ```python
   # Ensure backtest and benchmark have same frequency
   assert backtest_df.index.freq == spy_returns.index.freq
   ```

---

### ❌ DON'T

1. **Don't ignore p-values**
   ```python
   # BAD: Only report alpha
   print(f"Alpha: {alpha}")

   # GOOD: Report alpha AND significance
   print(f"Alpha: {alpha} (p={pvalue}, sig={significant})")
   ```

2. **Don't use wrong benchmark**
   ```python
   # BAD: Small-cap strategy vs. S&P 500
   attrib = PerformanceAttribution(small_cap_backtest, sp500_returns)

   # GOOD: Small-cap strategy vs. Russell 2000
   attrib = PerformanceAttribution(small_cap_backtest, russell2000_returns)
   ```

3. **Don't confuse daily and annualized alpha**
   ```python
   # BAD: Report daily alpha as annual
   print(f"Annual alpha: {daily_alpha}")  # WRONG

   # GOOD: Explicitly annualize
   print(f"Alpha (daily): {daily_alpha}")
   print(f"Alpha (annual): {daily_alpha * 252}")  # CORRECT
   ```

4. **Don't skip factor analysis**
   ```python
   # BAD: Only simple alpha/beta
   attrib = PerformanceAttribution(backtest_df, spy_returns)

   # GOOD: Include factor analysis
   attrib = PerformanceAttribution(
       backtest_df, spy_returns, factor_returns=ff_factors
   )
   # Reveals if alpha is from factors or true skill
   ```

---

## Common Pitfalls

### Pitfall 1: Data Mismatch

```python
# BAD: Misaligned dates
backtest_df.index: 2020-01-01 to 2023-12-31 (daily)
spy_returns.index: 2020-01-01 to 2022-12-31 (daily)
# Result: Incomplete attribution (only overlapping period used)

# GOOD: Ensure complete overlap
# Or explicitly handle missing data
```

---

### Pitfall 2: Insufficient Data

```python
# BAD: Too few observations
len(backtest_df) = 20  # Only 20 days
attrib = PerformanceAttribution(backtest_df, spy_returns)
# Result: Unreliable statistics, high p-values

# GOOD: Minimum 100+ observations for reliable attribution
if len(backtest_df) >= 100:
    attrib = PerformanceAttribution(backtest_df, spy_returns)
```

---

### Pitfall 3: Look-Ahead Bias in Factors

```python
# BAD: Using future factor data
ff_factors_full = load_factors()  # Includes future data
attrib = PerformanceAttribution(
    backtest_df,
    factor_returns=ff_factors_full  # WRONG: Look-ahead bias
)

# GOOD: Only use factors available at backtest dates
ff_factors = ff_factors_full.loc[:backtest_df.index[-1]]
attrib = PerformanceAttribution(backtest_df, factor_returns=ff_factors)
```

---

## Visualization

### Attribution Waterfall Chart

```python
# Create waterfall chart showing return decomposition
results = attrib.analyze_attribution()

fig = attrib.plot_attribution_waterfall(
    results,
    figsize=(12, 6),
    title='Performance Attribution Breakdown'
)

plt.savefig('attribution_waterfall.png', dpi=150)
```

---

## See Also

- [Analytics Suite Overview](../README.md)
- [Risk Analytics](../risk/README.md)
- [Trade Analysis](../trade-analysis/README.md)
- [Optimization Framework](../../optimization/README.md)

---

## References

### Academic Sources

1. **Alpha and Beta**:
   - Jensen, M. C. (1968). "The Performance of Mutual Funds in the Period 1945-1964". *Journal of Finance*.
   - Sharpe, W. F. (1966). "Mutual Fund Performance". *Journal of Business*.

2. **Factor Models**:
   - Fama, E. F., & French, K. R. (1993). "Common Risk Factors in the Returns on Stocks and Bonds". *Journal of Financial Economics*.
   - Fama, E. F., & French, K. R. (2015). "A Five-Factor Asset Pricing Model". *Journal of Financial Economics*.
   - Carhart, M. M. (1997). "On Persistence in Mutual Fund Performance". *Journal of Finance*.

3. **Market Timing**:
   - Merton, R. C., & Henriksson, R. D. (1981). "On Market Timing and Investment Performance". *Journal of Business*.
   - Treynor, J., & Mazuy, K. (1966). "Can Mutual Funds Outguess the Market?". *Harvard Business Review*.

4. **Attribution Methodology**:
   - Brinson, G. P., Hood, L. R., & Beebower, G. L. (1986). "Determinants of Portfolio Performance". *Financial Analysts Journal*.
   - Brinson, G. P., & Fachler, N. (1985). "Measuring Non-US Equity Portfolio Performance". *Journal of Portfolio Management*.

---

*Last Updated: 2025-10-16 | RustyBT v1.0*
