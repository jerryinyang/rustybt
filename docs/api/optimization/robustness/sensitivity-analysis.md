# Parameter Sensitivity Analysis

Parameter sensitivity analysis identifies robust vs. sensitive parameters to detect overfitting and validate optimization results. Robust parameters have flat performance surfaces; sensitive parameters have sharp performance cliffs.

## Overview

**Purpose**: Test if optimized parameters are:
- ✅ **Robust**: Performance stable across parameter range (flat surface)
- ❌ **Sensitive**: Performance cliff near optimal value (overfit indicator)

**How It Works**:
1. Take optimized (base) parameters as center point
2. Vary each parameter independently across range (±50% default)
3. Evaluate objective function at each parameter value
4. Calculate stability metrics (variance, gradient, curvature)
5. Classify parameters as robust, moderate, or sensitive
6. Test parameter interactions with 2D analysis

**Statistical Foundation**:
- **Variance**: Spread of objective values (low variance = stable)
- **Gradient**: Rate of change (low gradient = gradual changes)
- **Curvature**: Second derivative (low curvature = smooth surface)
- **Stability Score**: Combined metric (0-1, higher = more stable)

---

## API Reference

### SensitivityAnalyzer

```python
from rustybt.optimization.sensitivity import SensitivityAnalyzer

class SensitivityAnalyzer:
    """Parameter sensitivity and stability analysis for strategy robustness."""

    def __init__(
        self,
        base_params: dict[str, float],
        n_points: int = 20,
        perturbation_pct: float = 0.5,
        n_bootstrap: int = 100,
        interaction_threshold: float = 0.1,
        random_seed: int | None = None,
    ):
        """Initialize sensitivity analyzer.

        Args:
            base_params: Center point for sensitivity analysis (optimized parameters)
            n_points: Points to sample per parameter (minimum 3, recommended 20+)
            perturbation_pct: Range to vary params as % of base (0.5 = ±50%)
            n_bootstrap: Bootstrap iterations for confidence intervals (default: 100)
            interaction_threshold: Threshold for detecting interactions (default: 0.1)
            random_seed: Random seed for reproducibility (optional)

        Raises:
            ValueError: If n_points < 3 or perturbation_pct <= 0
        """
```

### analyze()

```python
def analyze(
    self,
    objective: Callable[[dict[str, float]], float],
    param_ranges: dict[str, tuple[float, float]] | None = None,
    calculate_ci: bool = True,
) -> dict[str, SensitivityResult]:
    """Perform sensitivity analysis on all parameters.

    Args:
        objective: Objective function taking params dict, returning scalar
                  Example: lambda p: run_backtest(strategy, data, **p).sharpe_ratio
        param_ranges: Optional explicit ranges (min, max) per parameter.
                     If None, uses ±perturbation_pct around base_params
        calculate_ci: Whether to calculate confidence intervals (slower)

    Returns:
        Dictionary mapping parameter name to SensitivityResult
    """
```

### analyze_interaction()

```python
def analyze_interaction(
    self,
    param1: str,
    param2: str,
    objective: Callable[[dict[str, float]], float],
    param_ranges: dict[str, tuple[float, float]] | None = None,
) -> InteractionResult:
    """Analyze interaction between two parameters.

    Args:
        param1: First parameter name
        param2: Second parameter name
        objective: Objective function
        param_ranges: Optional explicit ranges per parameter

    Returns:
        InteractionResult with 2D performance surface
    """
```

### plot_sensitivity()

```python
def plot_sensitivity(
    self,
    parameter_name: str,
    output_path: Path | str | None = None,
    show_ci: bool = True,
) -> Figure:
    """Plot 1D sensitivity curve for parameter.

    Args:
        parameter_name: Parameter to plot
        output_path: Optional path to save figure
        show_ci: Whether to show confidence intervals

    Returns:
        Matplotlib Figure object

    Raises:
        KeyError: If parameter not analyzed yet (run analyze() first)
    """
```

### plot_interaction()

```python
def plot_interaction(
    self,
    param1: str,
    param2: str,
    output_path: Path | str | None = None,
) -> Figure:
    """Plot 2D interaction heatmap.

    Args:
        param1: First parameter name
        param2: Second parameter name
        output_path: Optional path to save figure

    Returns:
        Matplotlib Figure object

    Raises:
        KeyError: If interaction not analyzed yet (run analyze_interaction() first)
    """
```

### generate_report()

```python
def generate_report(self) -> str:
    """Generate markdown report with recommendations.

    Returns:
        Markdown-formatted report string with stability analysis,
        robustness assessment, recommendations, and overfitting indicators
    """
```

---

## Complete Example

### Basic Sensitivity Analysis

```python
from rustybt.optimization.sensitivity import SensitivityAnalyzer

# Optimized parameters (from grid search, Bayesian, etc.)
base_params = {
    'lookback_period': 20,
    'entry_threshold': 0.02,
    'stop_loss_pct': 0.05,
    'take_profit_pct': 0.10
}

# Define objective function
def objective(params: dict) -> float:
    """Run backtest with given parameters, return Sharpe ratio."""
    result = run_backtest(
        strategy=MomentumStrategy(**params),
        data=data,
        initial_capital=Decimal("100000")
    )
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

# Examine results
for param_name, result in results.items():
    print(f"\n{param_name}:")
    print(f"  Base value: {result.base_value:.4g}")
    print(f"  Stability score: {result.stability_score:.3f}")
    print(f"  Classification: {result.classification}")
    print(f"  Variance: {result.variance:.4f}")
    print(f"  Max gradient: {result.max_gradient:.4f}")
    print(f"  Max curvature: {result.max_curvature:.4f}")

    if result.classification == 'robust':
        print(f"  ✅ Robust parameter - safe to use")
    elif result.classification == 'moderate':
        print(f"  ⚠️  Moderate stability - monitor if parameter changes")
    else:  # sensitive
        print(f"  ❌ Sensitive parameter - may be overfit")
        print(f"     Consider widening search or using more stable alternative")

# Visualize sensitivity curves
for param_name in base_params:
    analyzer.plot_sensitivity(
        param_name,
        output_path=f'sensitivity_{param_name}.png',
        show_ci=True
    )

# Generate comprehensive report
report = analyzer.generate_report()
with open('sensitivity_report.md', 'w') as f:
    f.write(report)

print("\n📊 Sensitivity report saved to sensitivity_report.md")
```

**Expected Output**:
```
lookback_period:
  Base value: 20
  Stability score: 0.850
  Classification: robust
  Variance: 0.0024
  Max gradient: 0.0152
  Max curvature: 0.0008
  ✅ Robust parameter - safe to use

entry_threshold:
  Base value: 0.02
  Stability score: 0.420
  Classification: sensitive
  Variance: 0.1240
  Max gradient: 0.8520
  Max curvature: 1.2450
  ❌ Sensitive parameter - may be overfit
     Consider widening search or using more stable alternative
```

---

### Parameter Interaction Analysis

Test if parameters interact (non-separable optimization surface):

```python
# Analyze interaction between two parameters
interaction = analyzer.analyze_interaction(
    param1='lookback_period',
    param2='entry_threshold',
    objective=objective
)

print(f"\nInteraction Analysis: lookback_period × entry_threshold")
print(f"  Interaction strength: {interaction.interaction_strength:.4f}")
print(f"  Has interaction: {interaction.has_interaction}")

if interaction.has_interaction:
    print("  ⚠️  Parameters interact significantly")
    print("  → Optimize jointly (e.g., grid search 2D, Bayesian)")
    print("  → Do NOT optimize independently (sequential)")
else:
    print("  ✅ Parameters are independent")
    print("  → Can optimize independently")
    print("  → Sequential optimization acceptable")

# Visualize 2D interaction surface
analyzer.plot_interaction(
    'lookback_period',
    'entry_threshold',
    output_path='interaction_lookback_threshold.png'
)

# Test all pairwise interactions
param_names = list(base_params.keys())
interaction_matrix = []

for i, param1 in enumerate(param_names):
    for j, param2 in enumerate(param_names):
        if i < j:  # Avoid duplicates
            interaction = analyzer.analyze_interaction(param1, param2, objective)
            interaction_matrix.append({
                'param1': param1,
                'param2': param2,
                'strength': interaction.interaction_strength,
                'has_interaction': interaction.has_interaction
            })

# Report interactions
print("\n=== Pairwise Interaction Analysis ===")
for item in interaction_matrix:
    status = "⚠️  INTERACTION" if item['has_interaction'] else "✅ INDEPENDENT"
    print(f"{item['param1']} × {item['param2']}: {status} (strength: {item['strength']:.4f})")
```

---

## Interpretation Guide

### Stability Score

**What it measures**: Combined stability metric (0-1, higher = more stable)

**Calculation**:
```python
instability = variance + max_gradient + max_curvature
stability_score = 1 / (1 + instability)
```

**Classification Thresholds**:
- **> 0.8**: Robust (flat performance surface, safe to use)
- **0.5-0.8**: Moderate (acceptable stability, monitor changes)
- **< 0.5**: Sensitive (performance cliff, likely overfit)

**Interpretation**:
```python
if result.stability_score > 0.8:
    # Performance stable across ±50% range
    # Small parameter errors won't hurt performance
    # Safe for production deployment
    deploy_with_confidence()
elif result.stability_score > 0.5:
    # Performance moderately stable
    # Be cautious with parameter adjustments
    # Monitor performance if parameter drifts
    deploy_with_monitoring()
else:
    # Performance cliff detected
    # Strong overfitting indicator
    # Small parameter errors could drastically hurt performance
    do_not_deploy()
```

### Variance

**What it measures**: Spread of objective values across parameter range

**Low Variance (< 0.01)**: Performance stable, robust parameter
**High Variance (> 0.1)**: Performance fluctuates, sensitive parameter

### Gradient

**What it measures**: Rate of change of objective function

**Low Gradient (< 0.05)**: Gradual changes, robust
**High Gradient (> 0.5)**: Sharp changes, sensitive

### Curvature

**What it measures**: Second derivative (convexity/concavity)

**Low Curvature (< 0.01)**: Smooth surface, robust
**High Curvature (> 0.1)**: Sharp corners, sensitive

---

### Interaction Strength

**What it measures**: Cross-derivative magnitude (non-separability)

**Calculation**:
```python
# ∂²f/∂x∂y measures if parameters interact
grad_x = np.gradient(objective_matrix, axis=0)
cross_deriv = np.gradient(grad_x, axis=1)
interaction_strength = np.mean(np.abs(cross_deriv))
```

**Thresholds**:
- **< 0.05**: No interaction (parameters independent)
- **0.05-0.1**: Weak interaction (borderline)
- **> 0.1**: Strong interaction (optimize jointly)

**Implications**:
```python
if interaction.has_interaction:
    # Parameters are coupled
    # Optimal value of param1 depends on param2
    # Must optimize jointly (grid search 2D, Bayesian)
    # Sequential optimization suboptimal
else:
    # Parameters are independent
    # Optimal value of param1 doesn't depend on param2
    # Can optimize sequentially
    # Coordinate descent acceptable
```

---

## Advanced Usage

### Custom Parameter Ranges

Specify explicit parameter ranges instead of automatic ±50%:

```python
# Custom ranges
param_ranges = {
    'lookback_period': (10, 50),      # Test 10-50
    'entry_threshold': (0.01, 0.05),  # Test 1%-5%
    'stop_loss_pct': (0.02, 0.10)     # Test 2%-10%
}

analyzer = SensitivityAnalyzer(
    base_params=base_params,
    n_points=20
)

results = analyzer.analyze(
    objective=objective,
    param_ranges=param_ranges  # Use custom ranges
)
```

### Asymmetric Ranges

Test different ranges above/below base value:

```python
# For discrete parameters (e.g., lookback_period)
# Only test integer values
base_lookback = 20
min_lookback = 10
max_lookback = 30

param_ranges = {
    'lookback_period': (min_lookback, max_lookback)
}

# Post-process to use only integer values
results = analyzer.analyze(objective, param_ranges=param_ranges)

# OR implement integer-aware objective
def objective_int(params: dict) -> float:
    # Round lookback to nearest integer
    params = params.copy()
    params['lookback_period'] = int(round(params['lookback_period']))
    return run_backtest(strategy, data, **params).sharpe_ratio
```

### Conditional Parameters

Analyze parameters that depend on each other:

```python
# Example: stop_loss only applies if use_stop_loss=True
base_params = {
    'use_stop_loss': 1.0,  # 1.0 = True, 0.0 = False
    'stop_loss_pct': 0.05
}

def objective(params: dict) -> float:
    use_stop = params['use_stop_loss'] > 0.5
    stop_pct = params['stop_loss_pct'] if use_stop else None

    result = run_backtest(
        strategy=Strategy(stop_loss=stop_pct),
        data=data
    )
    return float(result.sharpe_ratio)

# Analyze stop_loss_pct sensitivity (only meaningful if use_stop_loss=True)
# Fix use_stop_loss=1.0, vary stop_loss_pct
fixed_params = base_params.copy()
fixed_params['use_stop_loss'] = 1.0

analyzer = SensitivityAnalyzer(base_params=fixed_params)
results = analyzer.analyze(objective)
```

---

## Common Pitfalls

### ❌ Pitfall 1: Too Few Sample Points

```python
# BAD: Too few points (unreliable gradient/curvature)
analyzer = SensitivityAnalyzer(base_params=params, n_points=3)

# GOOD: Sufficient points for accurate derivatives
analyzer = SensitivityAnalyzer(base_params=params, n_points=20)
```

**Why**: Gradient and curvature require sufficient sampling for accurate numerical differentiation.

---

### ❌ Pitfall 2: Testing Only Narrow Range

```python
# BAD: Narrow range (only tests ±5%)
analyzer = SensitivityAnalyzer(base_params=params, perturbation_pct=0.05)

# GOOD: Wide range (tests ±50%)
analyzer = SensitivityAnalyzer(base_params=params, perturbation_pct=0.5)
```

**Why**: Overfitting may only appear when parameters deviate significantly from optimal.

---

### ❌ Pitfall 3: Ignoring Parameter Constraints

```python
# BAD: Unbounded ranges causing invalid parameters
param_ranges = {
    'stop_loss_pct': (-0.1, 0.2)  # WRONG: negative stop loss invalid
}

# GOOD: Respect parameter constraints
param_ranges = {
    'stop_loss_pct': (0.01, 0.15)  # CORRECT: 1%-15% valid range
}

# OR implement constraint-aware objective
def objective_constrained(params: dict) -> float:
    # Clip to valid ranges
    params = params.copy()
    params['stop_loss_pct'] = np.clip(params['stop_loss_pct'], 0.01, 0.50)

    result = run_backtest(strategy, data, **params)
    return float(result.sharpe_ratio)
```

---

### ❌ Pitfall 4: Not Testing Interactions

```python
# BAD: Only test 1D sensitivity
results = analyzer.analyze(objective)
# Miss parameter interactions

# GOOD: Test pairwise interactions
results = analyzer.analyze(objective)

# Test key interactions
interaction_lb_th = analyzer.analyze_interaction('lookback_period', 'entry_threshold', objective)
interaction_sl_tp = analyzer.analyze_interaction('stop_loss_pct', 'take_profit_pct', objective)

if interaction_lb_th.has_interaction or interaction_sl_tp.has_interaction:
    print("⚠️  Parameter interactions detected - optimize jointly")
```

---

## Best Practices

### ✅ DO

1. **Test wide parameter ranges** (±50% or wider) to reveal overfitting
2. **Use sufficient sample points** (20+ per parameter)
3. **Analyze parameter interactions** for multi-parameter strategies
4. **Generate comprehensive reports** with `generate_report()`
5. **Visualize sensitivity curves** with `plot_sensitivity()`
6. **Set random seed** for reproducibility
7. **Test on out-of-sample data** to avoid in-sample bias
8. **Respect parameter constraints** (e.g., positive values, integer ranges)

### ❌ DON'T

1. **Skip sensitivity analysis** after optimization (leads to production failures)
2. **Test only narrow ranges** (±10% may miss overfitting)
3. **Use too few sample points** (< 10 per parameter)
4. **Ignore sensitive parameters** (strong overfitting indicator)
5. **Ignore parameter interactions** (leads to suboptimal joint optimization)
6. **Deploy strategies with majority sensitive parameters** (high risk)
7. **Test only in-sample** (optimistic bias)

---

## Sensitivity Analysis Workflow

**Complete robustness validation workflow**:

```python
# 1. Run optimization
from rustybt.optimization.search.grid_search import GridSearchAlgorithm

optimizer = GridSearchAlgorithm()
best_params, opt_result = optimizer.optimize(
    objective=objective,
    param_space=param_space
)

# 2. Sensitivity analysis on optimal parameters
analyzer = SensitivityAnalyzer(
    base_params=best_params,
    n_points=20,
    perturbation_pct=0.5,
    random_seed=42
)

sensitivity_results = analyzer.analyze(objective, calculate_ci=True)

# 3. Check for overfitting indicators
sensitive_params = [
    name for name, result in sensitivity_results.items()
    if result.classification == 'sensitive'
]

if sensitive_params:
    print(f"⚠️  Overfitting detected in parameters: {sensitive_params}")
    print("   Consider:")
    print("   1. Widening parameter search space")
    print("   2. Adding regularization to optimization")
    print("   3. Using walk-forward validation")
    print("   4. Selecting parameters from robust regions")

# 4. Test parameter interactions
param_names = list(best_params.keys())
has_interactions = False

for i, param1 in enumerate(param_names):
    for j, param2 in enumerate(param_names):
        if i < j:
            interaction = analyzer.analyze_interaction(param1, param2, objective)
            if interaction.has_interaction:
                print(f"⚠️  Interaction detected: {param1} × {param2}")
                has_interactions = True

if has_interactions:
    print("   → Recommend joint optimization (Bayesian, 2D grid search)")

# 5. Generate report
report = analyzer.generate_report()
with open(f'sensitivity_report_{datetime.now():%Y%m%d}.md', 'w') as f:
    f.write(report)

# 6. Decision logic
robust_count = sum(1 for r in sensitivity_results.values() if r.classification == 'robust')
total_count = len(sensitivity_results)
robustness_pct = (robust_count / total_count) * 100

if robustness_pct >= 75 and not has_interactions:
    print("✅ Strategy passes sensitivity analysis - ready for deployment")
elif robustness_pct >= 50:
    print("⚠️  Strategy shows moderate robustness - acceptable but monitor closely")
else:
    print("❌ Strategy fails sensitivity analysis - needs refinement")
```

---

## Statistical Theory

### Numerical Differentiation

**First Derivative (Gradient)**:
```python
# Central difference approximation
gradient = (f(x + h) - f(x - h)) / (2 * h)
```

**Second Derivative (Curvature)**:
```python
# Central difference approximation
curvature = (f(x + h) - 2*f(x) + f(x - h)) / (h**2)
```

**Implementation** (numpy):
```python
gradient = np.gradient(objective_values, param_values)
curvature = np.gradient(gradient, param_values)
```

### Bootstrap Confidence Intervals

Resample objective values with replacement to estimate CI for stability score:

```python
stability_scores = []

for _ in range(n_bootstrap):
    # Resample objective values
    resampled_obj = resample(objective_values, replace=True)

    # Recalculate metrics
    variance = np.var(resampled_obj)
    gradient = np.max(np.abs(np.gradient(resampled_obj, param_values)))
    curvature = np.max(np.abs(np.gradient(gradient, param_values)))

    # Stability score
    instability = variance + gradient + curvature
    stability_score = 1 / (1 + instability)
    stability_scores.append(stability_score)

# 95% confidence interval
ci_lower = np.percentile(stability_scores, 2.5)
ci_upper = np.percentile(stability_scores, 97.5)
```

---

## See Also

- [Robustness Testing Overview](README.md) - Main robustness documentation
- [Monte Carlo Permutation](monte-carlo.md) - Trade sequencing tests
- [Noise Infusion](noise-infusion.md) - Price noise testing
- [Bayesian Optimization](../algorithms/bayesian.md) - Efficient parameter search with built-in uncertainty

---

## References

### Academic Sources

1. **Sensitivity Analysis**:
   - Saltelli, A., et al. (2008). *Global Sensitivity Analysis: The Primer*. Wiley.
   - Sobol', I. M. (2001). "Global Sensitivity Indices for Nonlinear Mathematical Models". *Mathematics and Computers in Simulation*, 55(1-3), 271-280.

2. **Parameter Stability**:
   - Morris, M. D. (1991). "Factorial Sampling Plans for Preliminary Computational Experiments". *Technometrics*, 33(2), 161-174.

3. **Overfitting Detection**:
   - Bailey, D. H., et al. (2014). "Pseudo-Mathematics and Financial Charlatanism: The Effects of Backtest Overfitting on Out-of-Sample Performance". *Notices of the AMS*, 61(5), 458-471.
   - López de Prado, M. (2018). *Advances in Financial Machine Learning*. Wiley. (Chapter 11: The Dangers of Backtesting)

---

*Last Updated: 2025-10-16 | RustyBT v1.0*
