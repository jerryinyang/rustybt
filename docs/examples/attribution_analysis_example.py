"""
Performance Attribution Analysis Example

This example demonstrates how to use the PerformanceAttribution class to analyze
what drove your strategy's performance.

Attribution analysis decomposes returns into:
- Alpha: Excess return from skill
- Beta: Market-driven returns
- Factor exposures: Returns from factor tilts (size, value, momentum, etc.)
- Timing: Skill in market timing
- Selection: Skill in security selection
"""

import numpy as np
import pandas as pd

from rustybt.analytics.attribution import PerformanceAttribution

# ============================================================================
# Example 1: Basic Alpha/Beta Attribution
# ============================================================================

print("=" * 80)
print("Example 1: Basic Alpha/Beta Attribution")
print("=" * 80)

# Create sample portfolio returns
np.random.seed(42)
dates = pd.date_range(start="2023-01-01", periods=252, freq="D")

# Generate benchmark returns (e.g., S&P 500)
benchmark_returns = pd.Series(
    np.random.normal(0.0004, 0.015, 252),  # ~10% annual return, 15% vol
    index=dates,
    name="benchmark",
)

# Generate portfolio returns with some alpha and higher beta
true_alpha = 0.0002  # 5% annual alpha
true_beta = 1.3  # Higher market sensitivity

portfolio_returns = (
    true_alpha
    + true_beta * benchmark_returns
    + np.random.normal(0, 0.005, 252)  # Idiosyncratic risk
)

# Create backtest result DataFrame
backtest_result = pd.DataFrame({"returns": portfolio_returns}, index=dates)

# Perform attribution analysis
attrib = PerformanceAttribution(
    backtest_result=backtest_result, benchmark_returns=benchmark_returns
)

results = attrib.analyze_attribution()

# Display results
print("\nAlpha/Beta Results:")
print("-" * 80)
alpha_beta = results["alpha_beta"]
print(f"Alpha (daily):        {alpha_beta['alpha']:.6f}")
print(
    f"Alpha (annualized):   {alpha_beta['alpha_annualized']:.4f} ({float(alpha_beta['alpha_annualized']) * 100:.2f}%)"
)
print(f"Beta:                 {alpha_beta['beta']:.4f}")
print(f"Alpha p-value:        {alpha_beta['alpha_pvalue']:.4f}")
print(f"Alpha significant:    {alpha_beta['alpha_significant']}")
print(f"Information Ratio:    {alpha_beta['information_ratio']:.4f}")
print(f"IR (annualized):      {alpha_beta['information_ratio_annualized']:.4f}")
print(f"R-squared:            {alpha_beta['r_squared']:.4f}")
print(f"Tracking Error:       {alpha_beta['tracking_error']:.6f}")

print("\nInterpretation:")
print(f"- Your strategy generated {float(alpha_beta['alpha_annualized']) * 100:.2f}% annual alpha")
print(
    f"- Beta of {float(alpha_beta['beta']):.2f} means your strategy is {abs(float(alpha_beta['beta']) - 1) * 100:.0f}% more volatile than the benchmark"
)
if alpha_beta["alpha_significant"]:
    print("- The alpha is statistically significant (p < 0.05), suggesting real skill")
else:
    print("- The alpha is NOT statistically significant - could be luck")

# ============================================================================
# Example 2: Multi-Factor Attribution (Fama-French)
# ============================================================================

print("\n" + "=" * 80)
print("Example 2: Multi-Factor Attribution (Fama-French 3-Factor)")
print("=" * 80)

# Create Fama-French factor returns
# Mkt-RF: Market minus risk-free rate
# SMB: Small Minus Big (size factor)
# HML: High Minus Low (value factor)
factor_returns = pd.DataFrame(
    {
        "Mkt-RF": np.random.normal(0.0004, 0.015, 252),
        "SMB": np.random.normal(0.0001, 0.01, 252),  # Small cap premium
        "HML": np.random.normal(0.0001, 0.008, 252),  # Value premium
    },
    index=dates,
)

# Create portfolio with known factor exposures
true_factor_loadings = {
    "Mkt-RF": 1.1,  # Slightly more market exposure
    "SMB": 0.4,  # Tilt toward small caps
    "HML": -0.2,  # Growth tilt (negative value exposure)
}
true_factor_alpha = 0.0003  # 7.6% annual alpha

portfolio_returns_ff = (
    true_factor_alpha
    + true_factor_loadings["Mkt-RF"] * factor_returns["Mkt-RF"]
    + true_factor_loadings["SMB"] * factor_returns["SMB"]
    + true_factor_loadings["HML"] * factor_returns["HML"]
    + np.random.normal(0, 0.005, 252)
)

backtest_result_ff = pd.DataFrame({"returns": portfolio_returns_ff}, index=dates)

# Perform factor attribution
attrib_ff = PerformanceAttribution(
    backtest_result=backtest_result_ff, factor_returns=factor_returns
)

results_ff = attrib_ff.analyze_attribution()

# Display factor attribution results
print("\nFactor Attribution Results:")
print("-" * 80)
factor_attrib = results_ff["factor_attribution"]
print(f"Alpha (daily):        {factor_attrib['alpha']:.6f}")
print(
    f"Alpha (annualized):   {factor_attrib['alpha_annualized']:.4f} ({float(factor_attrib['alpha_annualized']) * 100:.2f}%)"
)
print(f"Alpha significant:    {factor_attrib['alpha_significant']}")
print(f"R-squared:            {factor_attrib['r_squared']:.4f}")

print("\nFactor Loadings (Exposures):")
for factor, loading in factor_attrib["factor_loadings"].items():
    print(f"  {factor:10s}: {float(loading):7.4f}")

print("\nInterpretation:")
print(f"- Market exposure: {float(factor_attrib['factor_loadings']['Mkt-RF']):.2f}x")
if float(factor_attrib["factor_loadings"]["SMB"]) > 0:
    print(
        f"- Small cap tilt: {float(factor_attrib['factor_loadings']['SMB']):.2f} (favors small companies)"
    )
else:
    print(
        f"- Large cap tilt: {abs(float(factor_attrib['factor_loadings']['SMB'])):.2f} (favors large companies)"
    )

if float(factor_attrib["factor_loadings"]["HML"]) > 0:
    print(
        f"- Value tilt: {float(factor_attrib['factor_loadings']['HML']):.2f} (favors value stocks)"
    )
else:
    print(
        f"- Growth tilt: {abs(float(factor_attrib['factor_loadings']['HML'])):.2f} (favors growth stocks)"
    )

# ============================================================================
# Example 3: Timing Attribution (Market Timing Skill)
# ============================================================================

print("\n" + "=" * 80)
print("Example 3: Timing Attribution (Market Timing)")
print("=" * 80)

# Create portfolio with timing skill (higher beta in up markets)
portfolio_timing = []
for bench_ret in benchmark_returns:
    if bench_ret > 0:
        # Higher exposure in up markets
        port_ret = 1.8 * bench_ret + np.random.normal(0, 0.005)
    else:
        # Lower exposure in down markets
        port_ret = 0.7 * bench_ret + np.random.normal(0, 0.005)
    portfolio_timing.append(port_ret)

backtest_result_timing = pd.DataFrame({"returns": portfolio_timing}, index=dates)

# Perform timing attribution
attrib_timing = PerformanceAttribution(
    backtest_result=backtest_result_timing, benchmark_returns=benchmark_returns
)

results_timing = attrib_timing.analyze_attribution()

# Display timing results
print("\nTiming Attribution Results:")
print("-" * 80)
timing = results_timing["timing"]
print(f"Timing coefficient:   {timing['timing_coefficient']:.6f}")
print(f"Timing p-value:       {timing['timing_pvalue']:.4f}")
print(f"Has timing skill:     {timing['has_timing_skill']}")
print(f"Timing direction:     {timing['timing_direction']}")

print("\nInterpretation:")
if timing["has_timing_skill"]:
    print("- Strategy demonstrates statistically significant market timing skill")
    print("- Positive timing coefficient indicates higher exposure in up markets")
else:
    print("- No statistically significant market timing detected")

# ============================================================================
# Example 4: Rolling Attribution (Time-Varying Analysis)
# ============================================================================

print("\n" + "=" * 80)
print("Example 4: Rolling Attribution Analysis")
print("=" * 80)

# Use the basic portfolio from Example 1
# Perform rolling attribution with 60-day window
attrib_rolling = PerformanceAttribution(
    backtest_result=backtest_result, benchmark_returns=benchmark_returns
)

results_rolling = attrib_rolling.analyze_attribution()

if "rolling" in results_rolling:
    rolling = results_rolling["rolling"]
    print("\nRolling Attribution (60-day window):")
    print("-" * 80)
    print(f"Rolling alpha - Mean:  {rolling['rolling_alpha'].mean():.6f}")
    print(f"Rolling alpha - Std:   {rolling['rolling_alpha'].std():.6f}")
    print(f"Rolling beta - Mean:   {rolling['rolling_beta'].mean():.4f}")
    print(f"Rolling beta - Std:    {rolling['rolling_beta'].std():.4f}")
    print(f"Rolling IR - Mean:     {rolling['rolling_information_ratio'].mean():.4f}")

    print("\nInterpretation:")
    alpha_std = float(rolling["rolling_alpha"].std())
    if alpha_std > 0.001:
        print(f"- Alpha varies significantly over time (std = {alpha_std:.6f})")
        print("- Performance may be period-dependent")
    else:
        print("- Alpha is relatively stable over time")

# ============================================================================
# Example 5: Visualization
# ============================================================================

print("\n" + "=" * 80)
print("Example 5: Attribution Visualizations")
print("=" * 80)

# Generate visualizations (commented out to avoid showing plots in this example)
# Uncomment these lines to see the plots

print("\nGenerating attribution visualizations...")

# 1. Attribution waterfall chart
# fig1 = attrib.plot_attribution_waterfall(results)
# fig1.savefig('attribution_waterfall.png', dpi=300, bbox_inches='tight')
print("- Waterfall chart: Shows decomposition of total return into alpha + beta")

# 2. Rolling attribution time series
# fig2 = attrib_rolling.plot_rolling_attribution(results_rolling)
# fig2.savefig('rolling_attribution.png', dpi=300, bbox_inches='tight')
print("- Rolling attribution: Shows how alpha and beta evolve over time")

# 3. Factor exposures bar chart
# fig3 = attrib_ff.plot_factor_exposures(results_ff)
# fig3.savefig('factor_exposures.png', dpi=300, bbox_inches='tight')
print("- Factor exposures: Shows factor loadings (tilts)")

print("\nVisualization files saved successfully!")

# ============================================================================
# Example 6: Interpreting Results for Different Strategies
# ============================================================================

print("\n" + "=" * 80)
print("Example 6: How to Interpret Attribution Results")
print("=" * 80)

print(
    """
KEY METRICS AND INTERPRETATION:

1. ALPHA (alpha)
   - What it means: Excess return beyond what's explained by risk factors
   - Good values: Positive and statistically significant (p < 0.05)
   - Interpretation:
     * alpha > 0 and significant: Strategy adds value (skill)
     * alpha ~= 0 or not significant: Returns explained by factor exposures
     * alpha < 0: Strategy destroys value

2. BETA (β)
   - What it means: Sensitivity to benchmark/market movements
   - Typical values:
     * β = 1.0: Moves with market
     * β > 1.0: More volatile than market (aggressive)
     * β < 1.0: Less volatile than market (defensive)
   - Interpretation:
     * High beta: Amplifies market returns (both up and down)
     * Low beta: Dampens market returns

3. INFORMATION RATIO (IR)
   - What it means: Risk-adjusted alpha (alpha / tracking error)
   - Good values: IR > 0.5 is good, IR > 1.0 is excellent
   - Interpretation:
     * Measures consistency of outperformance
     * Higher IR = more consistent alpha generation

4. FACTOR LOADINGS
   - What it means: Exposure to systematic risk factors
   - Examples:
     * SMB > 0: Small cap tilt
     * HML > 0: Value tilt
     * Mom > 0: Momentum tilt
   - Interpretation:
     * Positive loading: Returns increase when factor performs well
     * Negative loading: Returns increase when factor performs poorly

5. TIMING COEFFICIENT (gamma)
   - What it means: Market timing ability
   - Good values: gamma > 0 and statistically significant
   - Interpretation:
     * gamma > 0: Higher exposure in up markets (good timing)
     * gamma < 0: Lower exposure in up markets (poor timing)

COMMON SCENARIOS:

Scenario 1: High Alpha, Beta ≈ 1
→ Strategy generates consistent excess returns with market-like risk
→ Ideal for long-term investing

Scenario 2: Low Alpha, Beta > 1
→ Strategy is just a leveraged bet on the market
→ No skill, just higher risk

Scenario 3: Significant Factor Loadings, Low Alpha
→ Returns explained by factor exposures
→ Could replicate with factor ETFs

Scenario 4: Positive Timing Coefficient
→ Strategy successfully adjusts exposure based on market conditions
→ Valuable skill, especially in volatile markets

ACTIONABLE INSIGHTS:

1. If alpha is not significant:
   - Re-examine strategy logic
   - Check if returns are just from factor bets
   - Consider lower transaction costs

2. If beta is too high:
   - Reduce position sizes
   - Add hedges
   - Use market-neutral strategies

3. If factor loadings are unintended:
   - Adjust portfolio construction
   - Use factor-neutral screening
   - Rebalance more frequently

4. If timing coefficient is negative:
   - Avoid trying to time the market
   - Use consistent position sizing
   - Focus on security selection instead
"""
)

print("\n" + "=" * 80)
print("Example complete! Attribution analysis helps you understand:")
print("- WHERE your returns come from (alpha vs. beta vs. factors)")
print("- WHETHER outperformance is skill or luck")
print("- HOW to improve your strategy (timing, selection, factor tilts)")
print("=" * 80)
