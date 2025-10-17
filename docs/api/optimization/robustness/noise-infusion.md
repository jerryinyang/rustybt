# Noise Infusion Testing

Noise infusion testing validates strategy robustness by adding synthetic noise to historical price data and measuring performance degradation. This detects overfitting to specific historical price patterns.

## Overview

**Purpose**: Test if strategy is overfit to historical data by:
- ✅ **Robust**: Strategy generalizes beyond specific price patterns
- ❌ **Fragile**: Strategy overfit to exact historical prices (noise-sensitive)

**How It Works**:
1. Start with clean historical OHLCV data
2. Add synthetic noise to prices (Gaussian or bootstrapped returns)
3. Preserve OHLCV relationships (high ≥ low, high ≥ open/close)
4. Run backtest on noisy data
5. Repeat 1000+ times with different noise realizations
6. Measure performance degradation vs. noise-free backtest

**Statistical Foundation**:
- Robust strategies tolerate price noise (degradation < 20%)
- Fragile strategies collapse under noise (degradation > 50%, overfit indicator)
- Confidence intervals show expected performance range under uncertainty

---

## API Reference

### NoiseInfusionSimulator

```python
from rustybt.optimization.noise_infusion import NoiseInfusionSimulator

class NoiseInfusionSimulator:
    """Monte Carlo simulation with noise infusion for robustness testing."""

    def __init__(
        self,
        n_simulations: int = 1000,
        std_pct: float = 0.01,
        noise_model: Literal["gaussian", "bootstrap"] = "gaussian",
        seed: int | None = None,
        preserve_structure: bool = False,
        confidence_level: float = 0.95,
    ):
        """Initialize noise infusion simulator.

        Args:
            n_simulations: Number of noise realizations (minimum 100, recommended 1000+)
            std_pct: Noise amplitude as percentage (0.01 = 1%, range: 0.0-0.5)
            noise_model: 'gaussian' (normal returns) or
                        'bootstrap' (resample historical returns)
            seed: Random seed for reproducibility (optional)
            preserve_structure: Whether to preserve temporal autocorrelation (default: False)
            confidence_level: Confidence level for intervals (0.0-1.0, default 0.95)

        Raises:
            ValueError: If std_pct not in (0.0, 0.5] or n_simulations < 100
        """
```

### run()

```python
def run(
    self,
    data: pl.DataFrame,
    backtest_fn: Callable[[pl.DataFrame], dict[str, Decimal]],
) -> NoiseInfusionResult:
    """Run noise infusion simulation on OHLCV data.

    Args:
        data: OHLCV DataFrame with columns: ['open', 'high', 'low', 'close', 'volume']
             Must include timestamp/date column for temporal ordering
        backtest_fn: Function that takes OHLCV data and returns metrics dict.
                    Example: lambda d: {'sharpe_ratio': Decimal('1.5'), ...}

    Returns:
        NoiseInfusionResult with degradation analysis

    Raises:
        ValueError: If data is invalid or backtest_fn doesn't return metrics
    """
```

### add_noise()

```python
def add_noise(
    self,
    data: pl.DataFrame,
    sim_seed: int | None = None
) -> pl.DataFrame:
    """Add noise to OHLCV data while preserving relationships.

    Args:
        data: OHLCV DataFrame
        sim_seed: Seed for this specific simulation (for reproducibility)

    Returns:
        Noisy OHLCV DataFrame with validated relationships (high ≥ low, etc.)
    """
```

### NoiseInfusionResult

```python
from rustybt.optimization.noise_infusion import NoiseInfusionResult

@dataclass(frozen=True)
class NoiseInfusionResult:
    """Noise infusion simulation result with degradation analysis.

    Attributes:
        original_metrics: Metrics from noise-free backtest
        noisy_metrics: Distribution of metrics from noisy backtests
        mean_metrics: Mean metrics across all noise realizations
        std_metrics: Standard deviation of metrics across realizations
        degradation_pct: Percentage degradation for each metric
        worst_case_metrics: 5th percentile (worst-case) metrics
        confidence_intervals: 95% confidence intervals for each metric
        n_simulations: Number of noise realizations
        noise_model: Noise model used ('gaussian' or 'bootstrap')
        std_pct: Noise amplitude as percentage
        seed: Random seed used
    """

    @property
    def is_robust(self) -> dict[str, bool]:
        """Check if strategy is robust to noise (degradation < 20%)."""

    @property
    def is_fragile(self) -> dict[str, bool]:
        """Check if strategy is fragile (degradation > 50%, overfit indicator)."""

    def get_summary(self, metric: str = "sharpe_ratio") -> str:
        """Generate summary interpretation for a metric."""

    def plot_distribution(
        self,
        metric: str = "sharpe_ratio",
        output_path: str | Path | None = None,
        show: bool = True,
    ) -> None:
        """Plot distribution of noisy metric with original value."""
```

---

## Complete Example

### Basic Noise Infusion Test

```python
from decimal import Decimal
from rustybt.optimization.noise_infusion import NoiseInfusionSimulator
import polars as pl

# Load historical OHLCV data
data = pl.read_parquet("aapl_daily_2020_2023.parquet")

# Define backtest function
def run_backtest_on_data(ohlcv_data: pl.DataFrame) -> dict:
    """Run backtest and return metrics."""
    result = run_backtest(
        strategy=MovingAverageCrossover(short=20, long=50),
        data=ohlcv_data,
        initial_capital=Decimal("100000")
    )

    return {
        'sharpe_ratio': result.sharpe_ratio,
        'total_return': result.total_return,
        'max_drawdown': result.max_drawdown,
        'win_rate': result.win_rate
    }

# Noise infusion simulation
sim = NoiseInfusionSimulator(
    n_simulations=1000,
    std_pct=0.01,  # 1% price noise
    noise_model='gaussian',
    seed=42,
    confidence_level=0.95
)

results = sim.run(data, run_backtest_on_data)

# Analyze results
print(results.get_summary('sharpe_ratio'))

# Check robustness for each metric
for metric_name in results.original_metrics:
    original = results.original_metrics[metric_name]
    noisy_mean = results.mean_metrics[metric_name]
    degradation = results.degradation_pct[metric_name]
    is_robust = results.is_robust[metric_name]
    is_fragile = results.is_fragile[metric_name]

    print(f"\n{metric_name}:")
    print(f"  Original: {original:.4f}")
    print(f"  Noisy Mean: {noisy_mean:.4f}")
    print(f"  Degradation: {degradation:.1f}%")

    if is_fragile:
        print(f"  ❌ FRAGILE: Highly sensitive to noise (likely overfit)")
    elif degradation > Decimal("25"):
        print(f"  ⚠️  MODERATE: Moderate noise sensitivity")
    elif is_robust:
        print(f"  ✅ ROBUST: Tolerates noise well")
    else:
        print(f"  ✅ GOOD: Good noise tolerance")

# Visualize
results.plot_distribution('sharpe_ratio', output_path='noise_sharpe.png')
```

**Expected Output**:
```
Noise Infusion Test (1000 simulations, gaussian noise, 1.0% amplitude)
Metric: sharpe_ratio
Original (noise-free): 1.8500
Noisy mean: 1.6200 ± 0.3100
95% CI: [1.0800, 2.1500]
Worst case (5th %ile): 1.1200
Degradation: 12.4%

✅ ROBUST: Strategy tolerates noise well
```

---

### Gaussian vs. Bootstrap Noise

**Gaussian Noise** (default):
- Adds random returns from N(0, σ) distribution
- Simple, symmetric noise
- Best for: General robustness testing

**Bootstrap Noise**:
- Resamples historical returns with replacement
- Preserves empirical return distribution (fat tails, skewness)
- Best for: Realistic noise matching market characteristics

```python
# Gaussian noise test
sim_gaussian = NoiseInfusionSimulator(
    n_simulations=1000,
    std_pct=0.01,
    noise_model='gaussian',
    seed=42
)
gaussian_results = sim_gaussian.run(data, run_backtest_on_data)

# Bootstrap noise test
sim_bootstrap = NoiseInfusionSimulator(
    n_simulations=1000,
    std_pct=0.01,
    noise_model='bootstrap',
    seed=42
)
bootstrap_results = sim_bootstrap.run(data, run_backtest_on_data)

# Compare degradation
print("Gaussian Noise:")
print(f"  Sharpe degradation: {gaussian_results.degradation_pct['sharpe_ratio']:.1f}%")
print(f"  Robust: {gaussian_results.is_robust['sharpe_ratio']}")

print("\nBootstrap Noise:")
print(f"  Sharpe degradation: {bootstrap_results.degradation_pct['sharpe_ratio']:.1f}%")
print(f"  Robust: {bootstrap_results.is_robust['sharpe_ratio']}")

# Interpretation
if gaussian_results.is_robust['sharpe_ratio'] and bootstrap_results.is_robust['sharpe_ratio']:
    print("\n✅ Strategy passes both Gaussian and bootstrap noise tests")
elif gaussian_results.is_robust['sharpe_ratio']:
    print("\n⚠️  Strategy robust to Gaussian noise but sensitive to empirical distribution")
elif bootstrap_results.is_robust['sharpe_ratio']:
    print("\n⚠️  Strategy robust to empirical noise but sensitive to symmetric noise")
else:
    print("\n❌ Strategy fails both noise tests - likely overfit")
```

---

### Multiple Noise Levels

Test robustness across different noise amplitudes:

```python
# Test multiple noise levels
noise_levels = [0.005, 0.01, 0.02, 0.03]  # 0.5%, 1%, 2%, 3%

degradation_results = []

for std_pct in noise_levels:
    sim = NoiseInfusionSimulator(
        n_simulations=500,  # Fewer per level
        std_pct=std_pct,
        noise_model='gaussian',
        seed=42
    )

    results = sim.run(data, run_backtest_on_data)

    degradation_results.append({
        'noise_level': std_pct * 100,  # Convert to percentage
        'sharpe_degradation': float(results.degradation_pct['sharpe_ratio']),
        'is_robust': results.is_robust['sharpe_ratio']
    })

# Analyze noise sensitivity curve
import matplotlib.pyplot as plt

noise_levels_pct = [r['noise_level'] for r in degradation_results]
degradations = [r['sharpe_degradation'] for r in degradation_results]

plt.figure(figsize=(10, 6))
plt.plot(noise_levels_pct, degradations, 'o-', linewidth=2, markersize=8)
plt.axhline(y=20, color='green', linestyle='--', label='Robust threshold (20%)')
plt.axhline(y=50, color='red', linestyle='--', label='Fragile threshold (50%)')
plt.xlabel('Noise Level (%)', fontsize=12)
plt.ylabel('Sharpe Ratio Degradation (%)', fontsize=12)
plt.title('Noise Sensitivity Curve', fontsize=14)
plt.legend()
plt.grid(True, alpha=0.3)
plt.savefig('noise_sensitivity_curve.png', dpi=150, bbox_inches='tight')

# Assess overall robustness
max_robust_noise = max([r['noise_level'] for r in degradation_results if r['is_robust']], default=0)
print(f"\nMaximum noise level with robust performance: {max_robust_noise}%")

if max_robust_noise >= 2.0:
    print("✅ Excellent noise tolerance")
elif max_robust_noise >= 1.0:
    print("✅ Good noise tolerance")
elif max_robust_noise >= 0.5:
    print("⚠️  Moderate noise tolerance")
else:
    print("❌ Poor noise tolerance (likely overfit)")
```

---

## Interpretation Guide

### Degradation Thresholds

**What it measures**: Percentage drop in performance under noise

**Calculation**:
```python
degradation_pct = (original_metric - noisy_mean) / abs(original_metric) * 100
```

**Thresholds**:
- **< 10%**: Excellent robustness (strategy generalizes very well)
- **10-20%**: Good robustness (acceptable degradation)
- **20-35%**: Moderate robustness (acceptable for some strategies, monitor closely)
- **35-50%**: Concerning (strategy may be overfit, review assumptions)
- **> 50%**: Fragile (strong overfit indicator, do not deploy)

### Worst-Case Analysis

**What it measures**: 5th percentile performance (95% of noisy backtests perform better)

**Use Case**: Stress testing, risk assessment

**Interpretation**:
```python
worst_case_sharpe = results.worst_case_metrics['sharpe_ratio']
original_sharpe = results.original_metrics['sharpe_ratio']

if worst_case_sharpe > 0:
    print("✅ Strategy profitable even in worst case")
elif worst_case_sharpe > original_sharpe * Decimal("0.5"):
    print("⚠️  Worst case is degraded but still acceptable")
else:
    print("❌ Worst case is severely degraded")
```

### Confidence Intervals

**What it measures**: Range of expected performance under noise

**Interpretation**:
```python
ci_lower, ci_upper = results.confidence_intervals['sharpe_ratio']
original = results.original_metrics['sharpe_ratio']

ci_width = ci_upper - ci_lower
print(f"95% CI width: {ci_width:.4f}")

if ci_width < original * Decimal("0.3"):
    print("✅ Narrow CI (stable performance)")
elif ci_width < original * Decimal("0.6"):
    print("⚠️  Moderate CI width")
else:
    print("❌ Wide CI (unstable under noise)")
```

---

## Advanced Usage

### Custom Noise Model

Implement custom noise generation:

```python
class CustomNoiseSimulator(NoiseInfusionSimulator):
    """Custom noise simulator with regime-dependent noise."""

    def _add_gaussian_noise(self, data: pl.DataFrame) -> pl.DataFrame:
        """Override noise generation with custom logic."""

        # Example: Higher noise during high-volatility periods
        close = data['close'].to_numpy()
        returns = np.diff(close) / close[:-1]

        # Calculate rolling volatility
        window = 20
        rolling_vol = np.array([
            np.std(returns[max(0, i-window):i]) if i >= window else np.std(returns[:i+1])
            for i in range(len(returns))
        ])

        # Scale noise by volatility
        base_noise = float(self.std_pct)
        adaptive_noise = base_noise * (1 + rolling_vol / np.mean(rolling_vol))

        # Generate noise
        noise = np.random.normal(0, adaptive_noise, size=len(data))

        # Apply to prices (rest of implementation same as parent class)
        close_noisy = close * (1 + noise)
        factor = close_noisy / close

        open_noisy = data['open'].to_numpy() * factor
        high_noisy = data['high'].to_numpy() * factor
        low_noisy = data['low'].to_numpy() * factor
        volume_noisy = data['volume'].to_numpy()

        noisy_data = data.clone()
        noisy_data = noisy_data.with_columns([
            pl.Series('open', open_noisy),
            pl.Series('high', high_noisy),
            pl.Series('low', low_noisy),
            pl.Series('close', close_noisy),
            pl.Series('volume', volume_noisy),
        ])

        return self._fix_ohlcv_relationships(noisy_data)

# Use custom simulator
custom_sim = CustomNoiseSimulator(n_simulations=1000, std_pct=0.01, seed=42)
custom_results = custom_sim.run(data, run_backtest_on_data)
```

### Single Noisy Realization

Generate one noisy dataset for manual inspection:

```python
# Create simulator
sim = NoiseInfusionSimulator(std_pct=0.01, noise_model='gaussian', seed=42)

# Generate single noisy dataset
noisy_data = sim.add_noise(data, sim_seed=42)

# Compare original vs. noisy
import matplotlib.pyplot as plt

fig, axes = plt.subplots(2, 1, figsize=(12, 8))

# Original prices
axes[0].plot(data['timestamp'], data['close'], label='Original', alpha=0.7)
axes[0].set_title('Original Close Prices')
axes[0].legend()
axes[0].grid(True, alpha=0.3)

# Noisy prices
axes[1].plot(noisy_data['timestamp'], noisy_data['close'], label='Noisy (1% noise)', alpha=0.7, color='orange')
axes[1].set_title('Noisy Close Prices')
axes[1].legend()
axes[1].grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('original_vs_noisy.png', dpi=150)

# Run backtest on both
original_result = run_backtest_on_data(data)
noisy_result = run_backtest_on_data(noisy_data)

print("Original Sharpe:", original_result['sharpe_ratio'])
print("Noisy Sharpe:", noisy_result['sharpe_ratio'])
print("Single-trial degradation:",
      (original_result['sharpe_ratio'] - noisy_result['sharpe_ratio']) /
      original_result['sharpe_ratio'] * 100, "%")
```

---

## Common Pitfalls

### ❌ Pitfall 1: Wrong Noise Amplitude

```python
# BAD: Noise too small (no effect)
sim = NoiseInfusionSimulator(std_pct=0.0001)  # 0.01% - negligible

# BAD: Noise too large (destroys all signal)
sim = NoiseInfusionSimulator(std_pct=0.5)  # 50% - unrealistic

# GOOD: Realistic noise levels
sim_conservative = NoiseInfusionSimulator(std_pct=0.01)  # 1% (typical for daily bars)
sim_aggressive = NoiseInfusionSimulator(std_pct=0.02)    # 2% (stress test)
```

**Guideline**:
- **Daily bars**: 0.5-2% noise
- **Hourly bars**: 0.1-0.5% noise
- **Minute bars**: 0.01-0.1% noise

---

### ❌ Pitfall 2: Not Validating OHLCV Constraints

The simulator automatically fixes OHLCV relationships, but verify:

```python
# After adding noise, always check relationships
noisy_data = sim.add_noise(data)

# Verify high >= low
assert (noisy_data['high'] >= noisy_data['low']).all()

# Verify high >= open/close
assert (noisy_data['high'] >= noisy_data['open']).all()
assert (noisy_data['high'] >= noisy_data['close']).all()

# Verify low <= open/close
assert (noisy_data['low'] <= noisy_data['open']).all()
assert (noisy_data['low'] <= noisy_data['close']).all()

# Verify volume >= 0
assert (noisy_data['volume'] >= 0).all()
```

The `_fix_ohlcv_relationships()` method ensures these constraints automatically.

---

### ❌ Pitfall 3: Slow Backtest Function

Noise infusion runs backtest 1000+ times:

```python
# BAD: Slow backtest (takes hours)
def slow_backtest(data):
    # Complex calculations on every bar
    # Heavy I/O operations
    # Unoptimized loops
    ...

sim = NoiseInfusionSimulator(n_simulations=1000)
results = sim.run(data, slow_backtest)  # Takes 10+ hours

# GOOD: Optimized backtest
def fast_backtest(data):
    # Vectorized operations with Polars
    # Minimal I/O
    # Cached intermediate results
    ...

sim = NoiseInfusionSimulator(n_simulations=1000)
results = sim.run(data, fast_backtest)  # Takes < 1 hour
```

**Optimization Tips**:
1. Use vectorized Polars operations
2. Cache indicator calculations
3. Reduce I/O operations
4. Profile and optimize bottlenecks

---

### ❌ Pitfall 4: Testing In-Sample Data Only

```python
# BAD: Noise test on same data used for optimization
optimized_params = optimize(train_data)  # 2020-2022
sim = NoiseInfusionSimulator(n_simulations=1000)
results = sim.run(train_data, lambda d: backtest(d, optimized_params))  # WRONG

# GOOD: Noise test on out-of-sample data
optimized_params = optimize(train_data)  # 2020-2022
sim = NoiseInfusionSimulator(n_simulations=1000)
results = sim.run(test_data, lambda d: backtest(d, optimized_params))  # CORRECT (2023 data)
```

---

## Best Practices

### ✅ DO

1. **Test multiple noise levels** (0.5%, 1%, 2%) to assess robustness range
2. **Use both Gaussian and bootstrap** noise for comprehensive testing
3. **Test on out-of-sample data** to avoid in-sample bias
4. **Optimize backtest function** (runs 1000+ times)
5. **Set random seed** for reproducibility
6. **Examine multiple metrics** (Sharpe, return, drawdown)
7. **Document noise test results** in validation reports

### ❌ DON'T

1. **Skip noise testing** after optimization (leads to production surprises)
2. **Use unrealistic noise levels** (too small or too large)
3. **Test only on in-sample data** (optimistic bias)
4. **Ignore worst-case metrics** (important for risk assessment)
5. **Deploy fragile strategies** (degradation > 50%)
6. **Use slow backtest functions** (makes testing impractical)

---

## See Also

- [Robustness Testing Overview](README.md) - Main robustness documentation
- [Monte Carlo Permutation](monte-carlo.md) - Trade sequencing tests
- [Sensitivity Analysis](sensitivity-analysis.md) - Parameter stability testing

---

*Last Updated: 2025-10-16 | RustyBT v1.0*
