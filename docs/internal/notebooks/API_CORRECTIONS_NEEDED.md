# API Corrections for New Tutorial Notebooks

**Date:** 2025-11-07
**Status:** Corrections Identified

---

## Issues Found

### Notebook 15: Monte Carlo Basics

#### Issue 1: Incorrect Class Names
**Problem:**
```python
# ❌ WRONG (doesn't exist)
from rustybt.optimization.monte_carlo import (
    DataPermutationSimulator,  # Doesn't exist
    PermutationMethod,  # Doesn't exist
)
```

**Solution:**
```python
# ✅ CORRECT
from rustybt.optimization.monte_carlo import (
    MonteCarloSimulator,  # Correct class name
    MonteCarloResult,
)
# Use string literals: 'permutation' or 'bootstrap'
```

#### Issue 2: Incorrect NoiseInfusion API
**Problem:**
```python
# ❌ WRONG
from rustybt.optimization.noise_infusion import (
    NoiseConfig,  # Doesn't exist
    NoiseType,  # Doesn't exist
)

noise_config = NoiseConfig(
    noise_type=NoiseType.MULTIPLICATIVE,
    noise_level=0.02,
)
```

**Solution:**
```python
# ✅ CORRECT
from rustybt.optimization.noise_infusion import NoiseInfusionSimulator

noise_simulator = NoiseInfusionSimulator(
    n_simulations=100,
    std_pct=0.02,  # Not noise_level
    noise_model='gaussian',  # Not noise_type, use string
    seed=42,
)
```

#### Issue 3: Incorrect MonteCarloSimulator Usage
**Problem:**
```python
# ❌ WRONG - MonteCarloSimulator doesn't run full backtests
mc_results = mc_simulator.run(
    strategy_class=MovingAverageCrossover,
    params={'fast_window': 20, 'slow_window': 50},
    bundle='yfinance',
    start_date=datetime(2020, 1, 1),
    end_date=datetime(2023, 12, 31),
)
```

**Solution:**
```python
# ✅ CORRECT - Pass trades DataFrame and observed metrics
# First run backtest to get trades
result = run_algorithm(...)
trades = result.transactions  # Get trades DataFrame

# Then run Monte Carlo on trades
mc_results = mc_simulator.run(
    trades=trades,
    observed_metrics={'sharpe_ratio': result.sharpe_ratio},
    initial_capital=Decimal("100000"),
)
```

---

### Notebook 16: Sensitivity Analysis Basics

#### Issue 1: Non-existent Classes
**Problem:**
```python
# ❌ WRONG
from rustybt.optimization.sensitivity import (
    SensitivityAnalyzer,
    ParameterSensitivity,  # Doesn't exist
    StabilityMetrics,  # Doesn't exist
)
```

**Solution:**
```python
# ✅ CORRECT
from rustybt.optimization.sensitivity import (
    SensitivityAnalyzer,
    SensitivityResult,  # This is what you get back
    InteractionResult,  # For 2D analysis
)
```

#### Issue 2: Incorrect analyze() Usage
**Problem:**
```python
# ❌ WRONG - Can't pass strategy class
rsi_sensitivity = sensitivity_analyzer.analyze_parameter(
    strategy_class=RSIMeanReversion,  # Wrong API
    parameter_name='rsi_period',
    parameter_values=list(range(5, 31)),
    bundle='yfinance',
)
```

**Solution:**
```python
# ✅ CORRECT - Pass objective function
def objective_function(params):
    \"\"\"Run backtest with given params and return objective metric.\"\"\"
    result = run_algorithm(
        strategy_class=RSIMeanReversion,
        strategy_params=params,
        bundle='yfinance',
        ...
    )
    return float(result['sharpe_ratio'].iloc[-1])

# Create analyzer with base parameters
analyzer = SensitivityAnalyzer(
    base_params={'rsi_period': 14, 'oversold_threshold': 30, 'overbought_threshold': 70},
    n_points=20,
    perturbation_pct=0.5,
)

# Analyze all parameters
results = analyzer.analyze(
    objective=objective_function,
    param_ranges={
        'rsi_period': (5, 30),
        'oversold_threshold': (20, 40),
        'overbought_threshold': (60, 80),
    }
)

# Access individual parameter results
rsi_result = results['rsi_period']
print(f"Stability score: {rsi_result.stability_score}")
```

#### Issue 3: No analyze_parameter_grid() Method
**Problem:**
```python
# ❌ WRONG - This method doesn't exist
sensitivity_2d = sensitivity_analyzer.analyze_parameter_grid(
    strategy_class=RSIMeanReversion,
    parameter_grid=param_grid,
    ...
)
```

**Solution:**
```python
# ✅ CORRECT - Use analyze_interaction() for 2D
interaction_result = analyzer.analyze_interaction(
    param1='oversold_threshold',
    param2='overbought_threshold',
    objective=objective_function,
    param_ranges={
        'oversold_threshold': (20, 40),
        'overbought_threshold': (60, 80),
    }
)

# Access 2D grid
param1_values = interaction_result.param1_values
param2_values = interaction_result.param2_values
objective_matrix = interaction_result.objective_matrix  # 2D numpy array
```

---

### Notebook 19: Portfolio Allocation Methods

#### Status: ✅ Mostly Correct

The portfolio allocation APIs are correct. Minor improvements:

1. The examples show conceptual usage but don't have actual runnable code (by design, since they need data bundles)
2. All class names and methods are correct:
   - `FixedAllocation` ✅
   - `DynamicAllocation` ✅
   - `RiskParityAllocation` ✅
   - `KellyCriterionAllocation` ✅
   - `DrawdownBasedAllocation` ✅
   - `AllocationRebalancer` ✅
   - `RebalancingFrequency` ✅

---

## Summary of Required Changes

| Notebook | Severity | Issues | Runnable? |
|----------|----------|--------|-----------|
| 15_monte_carlo_basics.ipynb | **HIGH** | Wrong class names, wrong API usage | ❌ No |
| 16_sensitivity_analysis_basics.ipynb | **HIGH** | Wrong API usage pattern | ❌ No |
| 19_portfolio_allocation_methods.ipynb | **LOW** | Conceptual only (expected) | ⚠️ Partial |

---

## Action Items

### Priority 1: Fix Notebooks 15 & 16
1. ✅ Update imports to use correct class names
2. ✅ Fix API usage patterns to match actual methods
3. ✅ Add correct code examples with proper signatures
4. ✅ Update all function calls to use correct parameters
5. ✅ Test that examples would work with actual data

### Priority 2: Enhance Notebook 19
1. ⚠️ Notebook 19 is intentionally conceptual (needs data bundles)
2. ✅ API usage is correct
3. ⚠️ Consider adding note about needing real backtest data

---

## Root Cause Analysis

**Why this happened:**
- Created notebooks based on logical API design, not actual implementation
- Didn't validate against actual module code before writing
- Assumed API patterns that seemed reasonable

**Prevention:**
- Always read actual module code before writing tutorials
- Test imports before documenting
- Verify method signatures match

---

## Next Steps

1. **Fix notebook 15** - Correct Monte Carlo & Noise Infusion APIs
2. **Fix notebook 16** - Correct Sensitivity Analysis API
3. **Test notebooks** - Ensure imports work and examples are accurate
4. **Add warnings** - Note where data bundles are required
5. **Update TUTORIAL_INDEX** - Mark notebooks with data requirements
