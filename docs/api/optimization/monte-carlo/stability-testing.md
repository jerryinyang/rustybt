# Monte Carlo Robustness Testing

Testing parameter stability and strategy robustness through Monte Carlo simulation.

## Overview

Monte Carlo testing validates that optimized parameters are robust and not overfitted by:
1. Adding noise to data
2. Permuting trade sequences
3. Perturbing parameters
4. Analyzing performance distribution

## Why Monte Carlo Testing?

**Problem**: Optimized parameters might work on historical data but fail with slight variations.

**Solution**: Test if strategy maintains performance when data/parameters are slightly perturbed.

## Basic Usage

```python
from rustybt.optimization import MonteCarloSimulator
from decimal import Decimal

# Create tester with best parameters
mc_simulator = MonteCarloSimulator(
    objective_function=run_backtest,
    base_params={'lookback': 50, 'threshold': 0.05},
    n_simulations=1000
)

# Run simulations
result = mc_simulator.run(noise_std=0.10)  # 10% noise

# Analyze results
print(f"Mean Sharpe: {result.mean_score:.3f}")
print(f"Std Sharpe: {result.std_score:.3f}")
print(f"95% CI: [{result.ci_lower:.3f}, {result.ci_upper:.3f}]")
print(f"Worst case: {result.worst_score:.3f}")

# Check robustness
if result.std_score / result.mean_score < 0.30:
    print("✓ Parameters are robust")
else:
    print("✗ Parameters are unstable")
```

## Constructor

```python
MonteCarloSimulator(
    objective_function: Callable,
    base_params: Dict[str, Any],
    n_simulations: int = 1000,
    random_seed: Optional[int] = None
)
```

**Parameters**:
- `objective_function`: Backtest function
- `base_params`: Optimized parameters to test
- `n_simulations`: Number of Monte Carlo runs
- `random_seed`: Random seed for reproducibility

## Testing Methods

### 1. Data Noise Infusion

Add random noise to price data:

```python
def test_with_price_noise():
    """Test robustness to price data noise."""
    mc = MonteCarloSimulator(
        objective_function=run_backtest,
        base_params=best_params,
        n_simulations=1000
    )

    # Add 10% random noise to prices
    result = mc.run(
        noise_type='price',
        noise_std=0.10  # 10% standard deviation
    )

    return result
```

**Interpretation**:
- Mean close to original → Robust to data noise
- Large std deviation → Sensitive to noise
- Negative worst case → Risk of failure

### 2. Return Permutation

Randomly shuffle returns while preserving distribution:

```python
def test_with_return_permutation():
    """Test if edge comes from entry/exit timing."""
    mc = MonteCarloSimulator(
        objective_function=run_backtest,
        base_params=best_params,
        n_simulations=1000
    )

    # Permute returns
    result = mc.run(noise_type='permutation')

    # Strategy should NOT maintain performance
    # If it does, edge might not be real
    if result.mean_score > original_score * 0.8:
        print("WARNING: Performance persists with random returns!")

    return result
```

**Use case**: Detect if strategy has real predictive power or just curve-fitted noise.

### 3. Parameter Perturbation

Test nearby parameter values:

```python
def test_parameter_sensitivity():
    """Test if small parameter changes affect performance."""
    mc = MonteCarloSimulator(
        objective_function=run_backtest,
        base_params={'lookback': 50, 'threshold': 0.05},
        n_simulations=100
    )

    # Perturb parameters by ±20%
    result = mc.run(
        noise_type='parameter',
        noise_std=0.20
    )

    # Robust parameters should maintain performance
    degradation = 1 - (result.mean_score / original_score)
    if degradation < 0.20:
        print("✓ Parameters are stable")
    else:
        print("✗ Parameters are sensitive")

    return result
```

### 4. Block Bootstrap

Preserve temporal structure while resampling:

```python
def test_with_block_bootstrap():
    """Test using block bootstrap resampling."""
    mc = MonteCarloSimulator(
        objective_function=run_backtest,
        base_params=best_params,
        n_simulations=1000
    )

    # Resample in blocks to preserve autocorrelation
    result = mc.run(
        noise_type='block_bootstrap',
        block_size=20  # 20-day blocks
    )

    return result
```

**Use case**: Maintain return autocorrelation structure while testing robustness.

## Complete Example

```python
from decimal import Decimal
from rustybt.optimization import MonteCarloSimulator
import matplotlib.pyplot as plt

# Optimized parameters
best_params = {
    'ma_short': 30,
    'ma_long': 150,
    'threshold': 0.05
}

# Original backtest
original_result = run_backtest(best_params)
original_sharpe = calculate_sharpe(original_result)

print(f"Original Sharpe: {original_sharpe:.3f}")
print("\nRunning Monte Carlo robustness tests...")

# Test 1: Price noise
print("\n1. Price Noise Test")
mc_noise = MonteCarloSimulator(
    objective_function=lambda p: calculate_sharpe(run_backtest(p)),
    base_params=best_params,
    n_simulations=1000,
    random_seed=42
)

noise_result = mc_noise.run(noise_type='price', noise_std=0.10)

print(f"   Mean Sharpe: {noise_result.mean_score:.3f}")
print(f"   Std Dev: {noise_result.std_score:.3f}")
print(f"   95% CI: [{noise_result.ci_lower:.3f}, {noise_result.ci_upper:.3f}]")
print(f"   Worst: {noise_result.worst_score:.3f}")

# Test 2: Parameter perturbation
print("\n2. Parameter Sensitivity Test")
mc_params = MonteCarloSimulator(
    objective_function=lambda p: calculate_sharpe(run_backtest(p)),
    base_params=best_params,
    n_simulations=100
)

param_result = mc_params.run(noise_type='parameter', noise_std=0.15)

print(f"   Mean Sharpe: {param_result.mean_score:.3f}")
print(f"   Degradation: {(1 - param_result.mean_score/original_sharpe)*100:.1f}%")

# Test 3: Return permutation
print("\n3. Return Permutation Test")
mc_perm = MonteCarloSimulator(
    objective_function=lambda p: calculate_sharpe(run_backtest(p)),
    base_params=best_params,
    n_simulations=500
)

perm_result = mc_perm.run(noise_type='permutation')

print(f"   Mean Sharpe: {perm_result.mean_score:.3f}")
if perm_result.mean_score > original_sharpe * 0.5:
    print("   ⚠ WARNING: Performance persists with random returns")
else:
    print("   ✓ Strategy has real predictive power")

# Visualization
fig, axes = plt.subplots(1, 3, figsize=(15, 5))

# Plot 1: Price noise distribution
axes[0].hist(noise_result.scores, bins=30, alpha=0.7, edgecolor='black')
axes[0].axvline(original_sharpe, color='r', linestyle='--', label='Original')
axes[0].axvline(noise_result.mean_score, color='g', linestyle='--', label='Mean')
axes[0].set_xlabel('Sharpe Ratio')
axes[0].set_ylabel('Frequency')
axes[0].set_title('Price Noise Test')
axes[0].legend()

# Plot 2: Parameter sensitivity
axes[1].hist(param_result.scores, bins=20, alpha=0.7, edgecolor='black')
axes[1].axvline(original_sharpe, color='r', linestyle='--', label='Original')
axes[1].set_xlabel('Sharpe Ratio')
axes[1].set_ylabel('Frequency')
axes[1].set_title('Parameter Sensitivity')
axes[1].legend()

# Plot 3: Return permutation
axes[2].hist(perm_result.scores, bins=30, alpha=0.7, edgecolor='black')
axes[2].axvline(original_sharpe, color='r', linestyle='--', label='Original')
axes[2].set_xlabel('Sharpe Ratio')
axes[2].set_ylabel('Frequency')
axes[2].set_title('Return Permutation')
axes[2].legend()

plt.tight_layout()
plt.show()

# Final assessment
print("\n=== Robustness Assessment ===")
cv_noise = noise_result.std_score / noise_result.mean_score
cv_params = param_result.std_score / param_result.mean_score

if cv_noise < 0.30 and cv_params < 0.30:
    print("✓ PASS: Parameters are robust")
elif cv_noise < 0.50 and cv_params < 0.50:
    print("⚠ CAUTION: Moderate robustness")
else:
    print("✗ FAIL: Parameters are not robust")
```

## Robustness Metrics

### Coefficient of Variation

```python
cv = std_score / mean_score

# Interpretation:
# < 0.20: Very robust
# 0.20-0.30: Robust
# 0.30-0.50: Moderate
# > 0.50: Poor robustness
```

### Confidence Interval Width

```python
ci_width = ci_upper - ci_lower

# Narrow CI = more consistent performance
# Wide CI = high variability
```

### Worst-Case Performance

```python
worst_case = min(all_scores)

# Should be positive for viable strategy
# Negative worst case = risk of failure
```

### Success Rate

```python
success_rate = (scores > threshold).sum() / len(scores)

# Percentage of simulations above minimum threshold
# Should be >80% for robust strategy
```

## Best Practices

### 1. Multiple Test Types

Don't rely on single test:

```python
def comprehensive_robustness_test(params):
    """Run all robustness tests."""
    tests = {
        'price_noise': mc_test(noise_type='price', noise_std=0.10),
        'parameter': mc_test(noise_type='parameter', noise_std=0.15),
        'permutation': mc_test(noise_type='permutation'),
        'bootstrap': mc_test(noise_type='block_bootstrap')
    }

    # Aggregate results
    all_pass = all(test.cv < 0.30 for test in tests.values())
    return all_pass
```

### 2. Appropriate Noise Levels

```python
# Test multiple noise levels
noise_levels = [0.05, 0.10, 0.15, 0.20]

for noise_std in noise_levels:
    result = mc_simulator.run(noise_std=noise_std)
    print(f"Noise {noise_std*100:.0f}%: "
          f"Mean={result.mean_score:.3f}, "
          f"CV={result.cv:.3f}")
```

### 3. Sufficient Simulations

```python
# More simulations = more reliable results
# But diminishing returns after ~1000

n_simulations_range = [100, 500, 1000, 2000]

for n_sims in n_simulations_range:
    mc = MonteCarloSimulator(..., n_simulations=n_sims)
    result = mc.run()
    print(f"N={n_sims}: CI width = {result.ci_upper - result.ci_lower:.3f}")
```

### 4. Compare to Benchmark

```python
# Test strategy AND benchmark
strategy_result = mc_simulator.run_strategy(best_params)
benchmark_result = mc_simulator.run_benchmark()

# Strategy should be more robust than benchmark
if strategy_result.cv < benchmark_result.cv:
    print("✓ Strategy is more robust than benchmark")
```

## Common Pitfalls

### ❌ Too Few Simulations

```python
# Bad: Only 50 simulations
mc = MonteCarloSimulator(..., n_simulations=50)

# Good: At least 500-1000
mc = MonteCarloSimulator(..., n_simulations=1000)
```

### ❌ Ignoring Temporal Structure

```python
# Bad: Simple random shuffle destroys autocorrelation
result = mc.run(noise_type='simple_shuffle')

# Good: Use block bootstrap to preserve structure
result = mc.run(noise_type='block_bootstrap', block_size=20)
```

### ❌ Only Testing One Dimension

```python
# Bad: Only test price noise
result = mc.run(noise_type='price')

# Good: Test multiple dimensions
price_test = mc.run(noise_type='price')
param_test = mc.run(noise_type='parameter')
perm_test = mc.run(noise_type='permutation')
```

### ❌ Not Setting Thresholds

```python
# Bad: No clear pass/fail criteria
result = mc.run()
print(f"Mean: {result.mean_score}")

# Good: Define acceptable thresholds
MIN_SHARPE = 1.0
MIN_SUCCESS_RATE = 0.80

if result.mean_score > MIN_SHARPE and result.success_rate > MIN_SUCCESS_RATE:
    print("✓ PASS")
else:
    print("✗ FAIL")
```

## Integration with Optimization

### Post-Optimization Validation

```python
# Step 1: Optimize parameters
optimizer = BayesianOptimizer(...)
result = optimizer.optimize()
best_params = result.best_params

# Step 2: Validate with Monte Carlo
mc = MonteCarloSimulator(
    objective_function=run_backtest,
    base_params=best_params,
    n_simulations=1000
)

validation_result = mc.run(noise_std=0.10)

# Step 3: Accept only if robust
if validation_result.cv < 0.30:
    print("✓ Parameters validated - proceeding to live trading")
else:
    print("✗ Parameters not robust - re-optimize or reject")
```

## See Also

- [Walk-Forward Optimization](../walk-forward/framework.md)
- [Overfitting Prevention](../best-practices/overfitting-prevention.md)
- [Parameter Spaces](../framework/parameter-spaces.md)
- Testing Framework
