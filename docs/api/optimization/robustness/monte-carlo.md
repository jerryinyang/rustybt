# Monte Carlo Permutation Testing

Monte Carlo permutation testing validates strategy performance by shuffling trade order and testing if performance persists. This distinguishes skill from lucky trade sequencing.

## Overview

**Purpose**: Test if strategy performance is due to:
- ✅ **Skill**: Strategy logic identifies profitable opportunities
- ❌ **Luck**: Fortuitous trade sequencing in backtest

**How It Works**:
1. Extract trades from backtest (returns, PnL, timestamps)
2. Shuffle trade order randomly (permutation) or resample (bootstrap)
3. Reconstruct equity curve from shuffled trades
4. Calculate performance metrics (Sharpe, return, drawdown, etc.)
5. Repeat 1000+ times to build distribution
6. Compare observed metrics to simulated distribution

**Statistical Foundation**:
- Null hypothesis: Performance is random (trade order doesn't matter)
- Alternative hypothesis: Performance is skill-based (specific trade sequence)
- P-value: Fraction of permutations with equal/better performance
- Robust if: Observed metric outside 95% CI and statistically significant

---

## API Reference

### MonteCarloSimulator

```python
from rustybt.optimization.monte_carlo import MonteCarloSimulator

class MonteCarloSimulator:
    """Monte Carlo simulation with trade permutation for robustness testing."""

    def __init__(
        self,
        n_simulations: int = 1000,
        method: Literal["permutation", "bootstrap"] = "permutation",
        seed: int | None = None,
        confidence_level: float = 0.95,
    ):
        """Initialize Monte Carlo simulator.

        Args:
            n_simulations: Number of Monte Carlo runs (minimum 100, recommended 1000+)
            method: 'permutation' (shuffle without replacement) or
                   'bootstrap' (sample with replacement)
            seed: Random seed for reproducibility (optional)
            confidence_level: Confidence level for intervals (0.0-1.0, default 0.95)

        Raises:
            ValueError: If n_simulations < 100 or confidence_level invalid
        """
```

### run()

```python
def run(
    self,
    trades: pl.DataFrame,
    observed_metrics: dict[str, Decimal],
    initial_capital: Decimal = Decimal("100000"),
) -> MonteCarloResult:
    """Run Monte Carlo simulation on trade sequence.

    Args:
        trades: DataFrame with columns: ['timestamp', 'return', 'pnl', 'asset']
               Returns should be absolute returns (0.02 = 2% gain, -0.01 = 1% loss)
               PnL should be dollar P&L per trade
        observed_metrics: Dictionary of observed metrics to test.
                         Must include at least one metric.
                         Example: {'sharpe_ratio': Decimal('1.5'), 'total_return': Decimal('0.25')}
        initial_capital: Starting capital for equity curve reconstruction

    Returns:
        MonteCarloResult with statistical analysis

    Raises:
        ValueError: If trades DataFrame is invalid or empty
    """
```

### MonteCarloResult

```python
from rustybt.optimization.monte_carlo import MonteCarloResult

@dataclass(frozen=True)
class MonteCarloResult:
    """Monte Carlo simulation result with statistical analysis.

    Attributes:
        observed_metrics: Original backtest metrics (before permutation)
        simulated_metrics: Distribution of metrics from all simulations
        confidence_intervals: Confidence intervals for each metric
        p_values: P-values testing if observed result is significant
        percentile_ranks: Percentile rank of observed result in distribution (0-100)
        n_simulations: Number of simulations performed
        method: Simulation method ('permutation' or 'bootstrap')
        seed: Random seed used for reproducibility
    """

    @property
    def is_significant(self) -> dict[str, bool]:
        """Check if each metric is statistically significant (p < 0.05)."""

    @property
    def is_robust(self) -> dict[str, bool]:
        """Check if observed result is outside 95% CI (robust indicator)."""

    def get_summary(self, metric: str = "sharpe_ratio") -> str:
        """Generate summary interpretation for a metric."""

    def plot_distribution(
        self,
        metric: str = "sharpe_ratio",
        output_path: str | Path | None = None,
        show: bool = True,
    ) -> None:
        """Plot distribution of simulated metric with observed value."""
```

---

## Complete Example

### Basic Permutation Test

```python
from decimal import Decimal
from rustybt.optimization.monte_carlo import MonteCarloSimulator
import polars as pl

# Run backtest and extract trades
result = run_backtest(strategy, data, start_date='2020-01-01', end_date='2023-12-31')

# Trades DataFrame must have: 'timestamp', 'return', 'pnl'
trades = result.transactions.select(['timestamp', 'return', 'pnl', 'asset'])

# Calculate observed metrics
observed_metrics = {
    'sharpe_ratio': result.sharpe_ratio,
    'total_return': result.total_return,
    'max_drawdown': result.max_drawdown,
    'win_rate': Decimal(str(len(trades.filter(pl.col('return') > 0)) / len(trades)))
}

# Monte Carlo simulation
mc = MonteCarloSimulator(
    n_simulations=1000,
    method='permutation',
    seed=42,
    confidence_level=0.95
)

mc_results = mc.run(
    trades=trades,
    observed_metrics=observed_metrics,
    initial_capital=Decimal("100000")
)

# Analyze results
print(mc_results.get_summary('sharpe_ratio'))
print(mc_results.get_summary('total_return'))

# Check robustness
for metric_name in observed_metrics:
    is_sig = mc_results.is_significant[metric_name]
    is_rob = mc_results.is_robust[metric_name]
    p_val = mc_results.p_values[metric_name]
    percentile = mc_results.percentile_ranks[metric_name]

    print(f"\n{metric_name}:")
    print(f"  Significant: {is_sig} (p={p_val:.4f})")
    print(f"  Robust: {is_rob}")
    print(f"  Percentile: {percentile:.1f}")

    if is_sig and is_rob:
        print(f"  ✅ ROBUST: Outside 95% CI and statistically significant")
    elif is_sig:
        print(f"  ⚠️  SIGNIFICANT: Stat significant but close to CI boundary")
    else:
        print(f"  ❌ NOT ROBUST: Performance may be due to luck")

# Visualize distributions
mc_results.plot_distribution('sharpe_ratio', output_path='mc_sharpe.png')
mc_results.plot_distribution('total_return', output_path='mc_return.png')
mc_results.plot_distribution('max_drawdown', output_path='mc_drawdown.png')
```

**Expected Output**:
```
Monte Carlo Analysis (1000 simulations, permutation method)
Metric: sharpe_ratio
Observed: 1.8500
95% CI: [0.4200, 1.2800]
P-value: 0.0120
Percentile: 98.8

✅ ROBUST: Strategy is statistically significant and outside 95% CI
```

---

### Bootstrap vs. Permutation

**Permutation** (shuffle without replacement):
- Preserves exact trade distribution
- Tests if trade *sequence* matters
- Best for: Validating strategy timing logic

**Bootstrap** (sample with replacement):
- Some trades appear multiple times, some never
- Tests if trade *set* is representative
- Best for: Assessing sampling variability

```python
# Permutation test - shuffle trade order
mc_perm = MonteCarloSimulator(method='permutation', n_simulations=1000, seed=42)
perm_results = mc_perm.run(trades, observed_metrics, initial_capital)

# Bootstrap test - resample trades with replacement
mc_boot = MonteCarloSimulator(method='bootstrap', n_simulations=1000, seed=42)
boot_results = mc_boot.run(trades, observed_metrics, initial_capital)

# Compare results
print("Permutation Test:")
print(f"  Sharpe p-value: {perm_results.p_values['sharpe_ratio']}")
print(f"  Robust: {perm_results.is_robust['sharpe_ratio']}")

print("\nBootstrap Test:")
print(f"  Sharpe p-value: {boot_results.p_values['sharpe_ratio']}")
print(f"  Robust: {boot_results.is_robust['sharpe_ratio']}")

# Interpretation
if perm_results.is_robust['sharpe_ratio'] and boot_results.is_robust['sharpe_ratio']:
    print("\n✅ Strategy passes both permutation and bootstrap tests")
elif perm_results.is_robust['sharpe_ratio']:
    print("\n⚠️  Strategy robust to sequencing but sensitive to trade sampling")
elif boot_results.is_robust['sharpe_ratio']:
    print("\n⚠️  Trade set is good but sequencing matters (may indicate timing skill)")
else:
    print("\n❌ Strategy fails both tests - performance may be luck")
```

---

### Multiple Metrics Analysis

```python
# Define comprehensive metrics
observed_metrics = {
    'sharpe_ratio': result.sharpe_ratio,
    'sortino_ratio': result.sortino_ratio,
    'total_return': result.total_return,
    'annual_return': result.annual_return,
    'max_drawdown': result.max_drawdown,
    'win_rate': result.win_rate,
    'profit_factor': result.profit_factor,
    'avg_win_to_avg_loss': result.avg_win / result.avg_loss if result.avg_loss != 0 else Decimal("0")
}

# Run Monte Carlo
mc = MonteCarloSimulator(n_simulations=1000, seed=42)
mc_results = mc.run(trades, observed_metrics, initial_capital)

# Analyze all metrics
robust_count = 0
total_count = len(observed_metrics)

for metric_name, observed_value in observed_metrics.items():
    is_robust = mc_results.is_robust[metric_name]
    is_significant = mc_results.is_significant[metric_name]

    if is_robust and is_significant:
        robust_count += 1
        status = "✅ ROBUST"
    elif is_significant:
        status = "⚠️  SIGNIFICANT"
    else:
        status = "❌ NOT ROBUST"

    print(f"{metric_name}: {status}")
    print(f"  Observed: {observed_value:.4f}")
    print(f"  P-value: {mc_results.p_values[metric_name]:.4f}")
    print(f"  95% CI: {mc_results.confidence_intervals[metric_name]}")
    print()

# Overall assessment
robustness_pct = (robust_count / total_count) * 100
print(f"Overall Robustness: {robust_count}/{total_count} metrics robust ({robustness_pct:.1f}%)")

if robustness_pct >= 75:
    print("✅ Strategy shows strong robustness across multiple metrics")
elif robustness_pct >= 50:
    print("⚠️  Strategy shows moderate robustness - acceptable but monitor closely")
else:
    print("❌ Strategy shows weak robustness - high risk of lucky backtest")
```

---

## Interpretation Guide

### Statistical Significance (P-Values)

**What it measures**: Probability of achieving observed performance by chance

**Thresholds**:
- **p < 0.01**: Strong evidence of skill (< 1% chance of luck)
- **0.01 ≤ p < 0.05**: Moderate evidence of skill (1-5% chance of luck)
- **p ≥ 0.05**: Insufficient evidence (may be luck)

**Calculation**: Fraction of simulations with performance ≥ observed
```python
# For metrics where higher is better (Sharpe, return)
p_value = (simulated_metrics >= observed_metric).mean()

# For metrics where lower is better (drawdown)
p_value = (simulated_metrics <= observed_metric).mean()
```

### Confidence Intervals

**What it measures**: Range of performance expected from random trade sequencing

**Robust indicator**: Observed metric outside 95% CI
- If observed < CI lower: Worse than random (strategy has negative edge)
- If observed > CI upper: Better than random (strategy has positive edge)
- If observed inside CI: Not significantly different from random

**Example**:
```
Observed Sharpe: 1.85
95% CI: [0.42, 1.28]
Interpretation: Observed (1.85) > CI upper (1.28) → Robust
```

### Percentile Ranks

**What it measures**: Where observed metric falls in simulated distribution

**Interpretation**:
- **> 95th percentile**: Top 5% (robust, better than 95% of permutations)
- **90-95th percentile**: Top 10% (good, but borderline)
- **50-90th percentile**: Above average but not exceptional
- **< 50th percentile**: Below average (concerning)

---

## Advanced Usage

### Custom Metrics

Test any metric derivable from equity curve:

```python
# Define custom metric calculator
def calculate_custom_metrics(trades_df: pl.DataFrame, initial_capital: Decimal) -> dict:
    """Calculate custom metrics from trades."""

    # Reconstruct equity curve
    pnl = trades_df['pnl'].to_numpy()
    equity = float(initial_capital) + np.cumsum(pnl)

    # Custom metric 1: Ulcer Index (drawdown pain)
    running_max = np.maximum.accumulate(equity)
    drawdowns = (equity - running_max) / running_max
    ulcer_index = np.sqrt(np.mean(drawdowns ** 2))

    # Custom metric 2: Consecutive wins
    returns = trades_df['return'].to_numpy()
    wins = returns > 0
    max_consecutive_wins = 0
    current_streak = 0
    for win in wins:
        if win:
            current_streak += 1
            max_consecutive_wins = max(max_consecutive_wins, current_streak)
        else:
            current_streak = 0

    # Custom metric 3: Recovery factor
    total_return = (equity[-1] - float(initial_capital)) / float(initial_capital)
    max_dd = abs(np.min(drawdowns))
    recovery_factor = total_return / max_dd if max_dd > 0 else 0

    return {
        'ulcer_index': Decimal(str(ulcer_index)),
        'max_consecutive_wins': Decimal(str(max_consecutive_wins)),
        'recovery_factor': Decimal(str(recovery_factor))
    }

# Use custom metrics in Monte Carlo
observed_custom = calculate_custom_metrics(trades, initial_capital)

mc = MonteCarloSimulator(n_simulations=1000, seed=42)
mc_results = mc.run(trades, observed_custom, initial_capital)

print(mc_results.get_summary('recovery_factor'))
```

### Conditional Analysis

Test robustness for different market regimes:

```python
# Split trades by market regime
bull_market_trades = trades.filter(
    (pl.col('timestamp') >= '2020-01-01') & (pl.col('timestamp') < '2021-06-01')
)
bear_market_trades = trades.filter(
    (pl.col('timestamp') >= '2022-01-01') & (pl.col('timestamp') < '2023-01-01')
)

# Test each regime separately
for regime_name, regime_trades in [('Bull', bull_market_trades), ('Bear', bear_market_trades)]:
    if len(regime_trades) < 30:
        print(f"Skipping {regime_name} - insufficient trades")
        continue

    mc = MonteCarloSimulator(n_simulations=1000, seed=42)
    mc_results = mc.run(regime_trades, observed_metrics, initial_capital)

    print(f"\n{regime_name} Market:")
    print(mc_results.get_summary('sharpe_ratio'))

    if mc_results.is_robust['sharpe_ratio']:
        print(f"  ✅ Robust in {regime_name} market")
    else:
        print(f"  ❌ Not robust in {regime_name} market")
```

---

## Common Pitfalls

### ❌ Pitfall 1: Too Few Simulations

```python
# BAD: Unreliable statistics
mc = MonteCarloSimulator(n_simulations=50)

# GOOD: Reliable statistics
mc = MonteCarloSimulator(n_simulations=1000)
```

**Why**: Central Limit Theorem requires sufficient samples for accurate confidence intervals

---

### ❌ Pitfall 2: Incorrect Trade Returns

```python
# BAD: Percentage returns as integers (50% = 50 instead of 0.50)
trades_bad = pl.DataFrame({
    'timestamp': timestamps,
    'return': [50, -20, 30],  # WRONG
    'pnl': [5000, -2000, 3000]
})

# GOOD: Decimal returns as fractions (50% = 0.50)
trades_good = pl.DataFrame({
    'timestamp': timestamps,
    'return': [0.50, -0.20, 0.30],  # CORRECT
    'pnl': [5000, -2000, 3000]
})

mc = MonteCarloSimulator(n_simulations=1000)
result = mc.run(trades_good, observed_metrics, Decimal("10000"))
```

---

### ❌ Pitfall 3: Not Checking Sample Size

```python
# BAD: Running Monte Carlo on too few trades
if len(trades) < 30:
    # Insufficient for reliable statistics
    mc_results = mc.run(trades, observed_metrics, initial_capital)  # WRONG

# GOOD: Validate minimum sample size
MIN_TRADES = 30

if len(trades) < MIN_TRADES:
    print(f"⚠️  Insufficient trades ({len(trades)}) for Monte Carlo test")
    print(f"   Minimum required: {MIN_TRADES}")
else:
    mc = MonteCarloSimulator(n_simulations=1000)
    mc_results = mc.run(trades, observed_metrics, initial_capital)
```

---

### ❌ Pitfall 4: Ignoring Multiple Testing

When testing many metrics, expect some false positives:

```python
# BAD: Testing 20 metrics, expecting all to be significant
# At p=0.05, expect ~1 false positive per 20 tests

# GOOD: Apply Bonferroni correction or interpret holistically
n_metrics = len(observed_metrics)
alpha_corrected = 0.05 / n_metrics  # Bonferroni

robust_count = sum(1 for m in observed_metrics if mc_results.is_robust[m])

# More conservative: Require majority of metrics to be robust
if robust_count / n_metrics >= 0.75:
    print("✅ Strategy robust (75%+ metrics pass)")
else:
    print("❌ Strategy not robust (< 75% metrics pass)")
```

---

## Best Practices

### ✅ DO

1. **Use 1000+ simulations** for reliable statistics
2. **Test multiple metrics** (Sharpe, return, drawdown, win rate)
3. **Set random seed** for reproducibility
4. **Validate input data** (check for nulls, correct return format)
5. **Check both significance and robustness** (p-value AND outside CI)
6. **Document results** in strategy validation reports

### ❌ DON'T

1. **Skip Monte Carlo testing** after optimization (leads to production failures)
2. **Test with < 30 trades** (unreliable statistics)
3. **Rely on single metric** (examine comprehensive performance)
4. **Ignore p-values > 0.05** (may indicate luck)
5. **Use wrong return format** (ensure fractional returns, not percentages)

---

## See Also

- [Robustness Testing Overview](README.md) - Main robustness documentation
- [Noise Infusion](noise-infusion.md) - Price noise testing
- [Sensitivity Analysis](sensitivity-analysis.md) - Parameter stability testing

---

*Last Updated: 2025-10-16 | RustyBT v1.0*
