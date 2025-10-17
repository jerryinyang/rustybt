# Robustness Testing & Monte Carlo Simulation

Monte Carlo simulation and robustness testing validate strategy performance by testing sensitivity to trade sequencing, price noise, and parameter variations. These tools help distinguish skill from luck and detect overfitting.

## Overview

**Purpose**: Validate that strategy performance is not due to:
- Lucky trade sequencing (Monte Carlo permutation)
- Overfitting to specific price patterns (noise infusion)
- Parameter instability (sensitivity analysis)

**When to Use**:
- ✅ After optimization to validate results
- ✅ Before deploying strategies to production
- ✅ When comparing multiple strategies
- ✅ As part of walk-forward validation workflow

**Key Concepts**:
- **Monte Carlo Permutation**: Shuffle trade order to test if performance persists
- **Noise Infusion**: Add synthetic noise to prices to test generalization
- **Sensitivity Analysis**: Vary parameters to identify stable regions
- **Statistical Significance**: P-values and confidence intervals

---

## Quick Start

### Monte Carlo Permutation Test

Tests if strategy performance is due to skill or lucky trade sequencing:

```python
from decimal import Decimal
from rustybt.optimization.monte_carlo import MonteCarloSimulator
import polars as pl

# After running backtest, extract trades
trades = result.transactions  # DataFrame with columns: ['timestamp', 'return', 'pnl']

# Monte Carlo simulation - shuffle trades 1000 times
mc = MonteCarloSimulator(
    n_simulations=1000,
    method='permutation',  # or 'bootstrap'
    seed=42,
    confidence_level=0.95
)

mc_results = mc.run(
    trades=trades,
    observed_metrics={
        'sharpe_ratio': result.sharpe_ratio,
        'total_return': result.total_return,
        'max_drawdown': result.max_drawdown
    },
    initial_capital=Decimal("100000")
)

# Check if strategy is robust
print(mc_results.get_summary('sharpe_ratio'))

if mc_results.is_significant['sharpe_ratio'] and mc_results.is_robust['sharpe_ratio']:
    print("✅ Strategy is statistically robust!")
    print(f"P-value: {mc_results.p_values['sharpe_ratio']}")
    print(f"Percentile: {mc_results.percentile_ranks['sharpe_ratio']}")
else:
    print("❌ Performance may be due to luck")

# Visualize distribution
mc_results.plot_distribution('sharpe_ratio', output_path='monte_carlo_sharpe.png')
```

**Interpretation**:
- **Robust**: Observed metric outside 95% CI and statistically significant (p < 0.05)
- **Significant**: Statistically significant but close to CI boundary
- **Not Robust**: Performance may be due to lucky trade sequencing

---

### Noise Infusion Test

Tests if strategy is overfit to specific historical price patterns:

```python
from rustybt.optimization.noise_infusion import NoiseInfusionSimulator

# Original OHLCV data
data = pl.read_parquet("historical_data.parquet")

# Define backtest function
def run_backtest_on_data(ohlcv_data: pl.DataFrame) -> dict:
    """Run backtest and return metrics."""
    result = run_backtest(strategy, ohlcv_data)
    return {
        'sharpe_ratio': result.sharpe_ratio,
        'total_return': result.total_return,
        'max_drawdown': result.max_drawdown
    }

# Noise infusion simulation
sim = NoiseInfusionSimulator(
    n_simulations=1000,
    std_pct=0.01,  # 1% noise amplitude
    noise_model='gaussian',  # or 'bootstrap'
    seed=42,
    confidence_level=0.95
)

results = sim.run(data, run_backtest_on_data)

# Check robustness
print(results.get_summary('sharpe_ratio'))

if results.is_robust['sharpe_ratio']:
    print("✅ Strategy tolerates noise well (degradation < 20%)")
elif results.is_fragile['sharpe_ratio']:
    print("❌ Strategy is fragile (degradation > 50%, likely overfit)")
else:
    print("⚠️  Strategy shows moderate noise sensitivity")

print(f"Degradation: {results.degradation_pct['sharpe_ratio']}%")
print(f"Original Sharpe: {results.original_metrics['sharpe_ratio']}")
print(f"Noisy Mean: {results.mean_metrics['sharpe_ratio']}")
print(f"Worst Case (5th %ile): {results.worst_case_metrics['sharpe_ratio']}")

# Visualize noise impact
results.plot_distribution('sharpe_ratio', output_path='noise_infusion_sharpe.png')
```

**Interpretation**:
- **Robust**: Degradation < 20% (strategy generalizes well)
- **Moderate**: Degradation 20-50% (acceptable for some strategies)
- **Fragile**: Degradation > 50% (overfit to price patterns)

---

### Parameter Sensitivity Analysis

Identifies robust vs. sensitive parameters to detect overfitting:

```python
from rustybt.optimization.sensitivity import SensitivityAnalyzer

# Base (optimized) parameters
base_params = {
    'lookback_period': 20,
    'entry_threshold': 0.02,
    'stop_loss': 0.05
}

# Define objective function
def objective(params: dict) -> float:
    """Run backtest with given parameters, return Sharpe ratio."""
    result = run_backtest(strategy, data, **params)
    return float(result.sharpe_ratio)

# Sensitivity analyzer
analyzer = SensitivityAnalyzer(
    base_params=base_params,
    n_points=20,           # Test 20 values per parameter
    perturbation_pct=0.5,  # Vary ±50% around base
    n_bootstrap=100,       # Bootstrap iterations for CI
    random_seed=42
)

# Analyze all parameters
results = analyzer.analyze(objective, calculate_ci=True)

# Check stability
for param_name, result in results.items():
    print(f"{param_name}: stability={result.stability_score:.3f} ({result.classification})")

    if result.classification == 'robust':
        print(f"  ✅ Robust parameter - safe to use")
    elif result.classification == 'sensitive':
        print(f"  ❌ Sensitive parameter - may be overfit")
        print(f"     Variance: {result.variance:.4f}")
        print(f"     Max gradient: {result.max_gradient:.4f}")

# Visualize sensitivity
analyzer.plot_sensitivity('lookback_period', output_path='sensitivity_lookback.png')

# Check parameter interactions
interaction = analyzer.analyze_interaction('lookback_period', 'entry_threshold', objective)
if interaction.has_interaction:
    print("⚠️  Parameters interact - optimize jointly, not independently")
    analyzer.plot_interaction('lookback_period', 'entry_threshold', output_path='interaction.png')
else:
    print("✅ Parameters are independent - can optimize separately")

# Generate comprehensive report
report = analyzer.generate_report()
with open('sensitivity_report.md', 'w') as f:
    f.write(report)
```

**Interpretation**:
- **Robust (score > 0.8)**: Performance stable across parameter range
- **Moderate (score 0.5-0.8)**: Acceptable stability, monitor changes
- **Sensitive (score < 0.5)**: Performance cliff, likely overfit

---

## Robustness Testing Workflow

**Recommended sequence after optimization**:

```python
# 1. Run optimization
best_params, opt_result = optimizer.optimize(objective)

# 2. Run backtest with optimal parameters
result = run_backtest(strategy, data, **best_params)

# 3. Monte Carlo permutation test
mc_results = MonteCarloSimulator(n_simulations=1000).run(
    trades=result.transactions,
    observed_metrics={'sharpe_ratio': result.sharpe_ratio}
)

# 4. Noise infusion test
noise_results = NoiseInfusionSimulator(n_simulations=500, std_pct=0.01).run(
    data=data,
    backtest_fn=lambda d: run_backtest(strategy, d, **best_params)
)

# 5. Sensitivity analysis
sensitivity_results = SensitivityAnalyzer(base_params=best_params).analyze(objective)

# 6. Decision logic
is_deployable = (
    mc_results.is_significant['sharpe_ratio'] and
    mc_results.is_robust['sharpe_ratio'] and
    noise_results.degradation_pct['sharpe_ratio'] < Decimal("25") and
    all(r.classification != 'sensitive' for r in sensitivity_results.values())
)

if is_deployable:
    print("✅ Strategy passed all robustness tests - ready for deployment")
else:
    print("❌ Strategy failed robustness tests - needs refinement")
```

---

## Core Modules

### Monte Carlo Simulation
- **Module**: `rustybt.optimization.monte_carlo`
- **Purpose**: Trade permutation and bootstrap testing
- **Best For**: Detecting lucky trade sequencing
- **Documentation**: [Monte Carlo Framework](monte-carlo.md)

### Noise Infusion
- **Module**: `rustybt.optimization.noise_infusion`
- **Purpose**: Price data noise testing
- **Best For**: Detecting overfitting to price patterns
- **Documentation**: [Noise Infusion](noise-infusion.md)

### Sensitivity Analysis
- **Module**: `rustybt.optimization.sensitivity`
- **Purpose**: Parameter stability analysis
- **Best For**: Identifying robust parameter regions
- **Documentation**: [Sensitivity Analysis](sensitivity-analysis.md)

---

## API Reference

### MonteCarloSimulator
```python
from rustybt.optimization.monte_carlo import MonteCarloSimulator

mc = MonteCarloSimulator(
    n_simulations=1000,           # Number of permutations
    method='permutation',         # 'permutation' or 'bootstrap'
    seed=42,                      # Random seed (optional)
    confidence_level=0.95         # Confidence level for CI
)

result = mc.run(
    trades=trades_df,             # Polars DataFrame with 'return', 'pnl'
    observed_metrics=metrics,     # Dict of observed metrics to test
    initial_capital=Decimal(...)  # Starting capital
)
```

### NoiseInfusionSimulator
```python
from rustybt.optimization.noise_infusion import NoiseInfusionSimulator

sim = NoiseInfusionSimulator(
    n_simulations=1000,           # Number of noise realizations
    std_pct=0.01,                 # Noise amplitude (0.01 = 1%)
    noise_model='gaussian',       # 'gaussian' or 'bootstrap'
    seed=42,                      # Random seed (optional)
    preserve_structure=False,     # Preserve temporal autocorrelation
    confidence_level=0.95         # Confidence level for CI
)

result = sim.run(
    data=ohlcv_df,                # Polars DataFrame with OHLCV
    backtest_fn=callable          # Function: DataFrame -> dict of metrics
)
```

### SensitivityAnalyzer
```python
from rustybt.optimization.sensitivity import SensitivityAnalyzer

analyzer = SensitivityAnalyzer(
    base_params=base_params,      # Center point for analysis
    n_points=20,                  # Points per parameter
    perturbation_pct=0.5,         # Range as % of base (±50%)
    n_bootstrap=100,              # Bootstrap iterations for CI
    interaction_threshold=0.1,    # Threshold for interaction detection
    random_seed=42                # Random seed (optional)
)

results = analyzer.analyze(
    objective=callable,           # Function: dict -> float
    param_ranges=None,            # Optional explicit ranges
    calculate_ci=True             # Calculate confidence intervals
)
```

---

## Best Practices

### ✅ DO

1. **Run all three tests** (Monte Carlo, noise infusion, sensitivity) before deployment
2. **Use consistent seeds** for reproducibility
3. **Test multiple noise levels** (1%, 2%, 5%) to assess robustness range
4. **Analyze parameter interactions** for multi-parameter strategies
5. **Document results** in strategy validation reports
6. **Combine with walk-forward** validation for comprehensive testing

### ❌ DON'T

1. **Skip robustness testing** after optimization (leads to production failures)
2. **Use too few simulations** (minimum 500, recommended 1000+)
3. **Ignore sensitive parameters** (indicates overfitting)
4. **Deploy fragile strategies** (degradation > 50%)
5. **Test on in-sample data only** (use walk-forward or out-of-sample)
6. **Over-interpret single metrics** (examine multiple performance measures)

---

## Common Pitfalls

### Pitfall 1: Insufficient Simulations
```python
# ❌ BAD: Too few simulations
mc = MonteCarloSimulator(n_simulations=50)  # Unreliable statistics

# ✅ GOOD: Sufficient simulations
mc = MonteCarloSimulator(n_simulations=1000)  # Reliable statistics
```

### Pitfall 2: Ignoring Multiple Testing
```python
# ❌ BAD: Testing many parameters without correction
# When testing 20 parameters, expect 1 false positive at p=0.05

# ✅ GOOD: Apply Bonferroni correction or interpret holistically
alpha_corrected = 0.05 / len(parameters)  # Bonferroni
# Or examine overall robustness pattern, not individual p-values
```

### Pitfall 3: Wrong Noise Amplitude
```python
# ❌ BAD: Noise too small or too large
sim = NoiseInfusionSimulator(std_pct=0.0001)  # Too small, no effect
sim = NoiseInfusionSimulator(std_pct=0.5)     # Too large, destroys signal

# ✅ GOOD: Realistic noise levels
sim = NoiseInfusionSimulator(std_pct=0.01)    # 1% (typical for daily bars)
sim = NoiseInfusionSimulator(std_pct=0.02)    # 2% (conservative test)
```

---

## Performance Considerations

### Monte Carlo Permutation
- **Time Complexity**: O(n_simulations × n_trades)
- **Memory**: O(n_simulations × n_metrics)
- **Typical Runtime**: 1-5 seconds for 1000 simulations with 1000 trades

### Noise Infusion
- **Time Complexity**: O(n_simulations × backtest_time)
- **Memory**: O(n_bars × n_simulations)
- **Typical Runtime**: Minutes to hours (depends on backtest complexity)
- **Optimization**: Use parallelization for multiple noise realizations

### Sensitivity Analysis
- **Time Complexity**: O(n_params × n_points × backtest_time)
- **Memory**: O(n_params × n_points)
- **Typical Runtime**: Minutes to hours (depends on backtest complexity)
- **Optimization**: Parallelize parameter evaluations

---

## Statistical Interpretation

### P-Values
- **p < 0.01**: Strong evidence of skill (not luck)
- **0.01 ≤ p < 0.05**: Moderate evidence of skill
- **p ≥ 0.05**: Insufficient evidence (may be luck)

### Confidence Intervals
- **Observed outside 95% CI**: Robust indicator
- **Observed inside 95% CI**: Performance not significantly different from random

### Degradation Thresholds
- **< 10%**: Excellent robustness
- **10-20%**: Good robustness
- **20-35%**: Moderate robustness (acceptable for some strategies)
- **35-50%**: Concerning (review strategy)
- **> 50%**: Fragile (likely overfit)

### Stability Scores
- **> 0.8**: Robust parameter (safe to use)
- **0.5-0.8**: Moderate stability (monitor performance)
- **< 0.5**: Sensitive parameter (likely overfit, use caution)

---

## See Also

- [Optimization Framework](../README.md) - Main optimization documentation
- [Bayesian Optimization](../algorithms/bayesian.md) - Efficient parameter search

---

## References

### Academic Sources

1. **Permutation Tests**:
   - Good, P. (2005). *Permutation, Parametric, and Bootstrap Tests of Hypotheses*. Springer.
   - Ernst, M. D. (2004). "Permutation Methods: A Basis for Exact Inference". *Statistical Science*.

2. **Bootstrap Methods**:
   - Efron, B., & Tibshirani, R. J. (1994). *An Introduction to the Bootstrap*. CRC Press.
   - Davison, A. C., & Hinkley, D. V. (1997). *Bootstrap Methods and Their Application*. Cambridge.

3. **Sensitivity Analysis**:
   - Saltelli, A., et al. (2008). *Global Sensitivity Analysis: The Primer*. Wiley.
   - Sobol', I. M. (2001). "Global Sensitivity Indices for Nonlinear Mathematical Models". *Mathematics and Computers in Simulation*.

4. **Overfitting in Quant Finance**:
   - Bailey, D. H., et al. (2014). "Pseudo-Mathematics and Financial Charlatanism". *The Journal of Portfolio Management*.
   - López de Prado, M. (2018). *Advances in Financial Machine Learning*. Wiley.

---

*Last Updated: 2025-10-16 | RustyBT v1.0*
