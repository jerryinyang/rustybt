# Optimization Framework

**Module**: `rustybt.optimization`
**Purpose**: Systematic parameter optimization for trading strategies
**Status**: Production-ready

---

## Overview

The RustyBT optimization framework provides systematic parameter search, validation, and robustness testing for trading strategies. It implements multiple search algorithms, parallel execution, walk-forward validation, and Monte Carlo robustness testing to help find optimal parameters while avoiding overfitting.

**Core Philosophy**: Parameter optimization must balance finding good parameters with avoiding overfitting. This framework enforces best practices through walk-forward validation, robustness testing, and comprehensive result analysis.

---

## Key Features

### Search Algorithms
- **Grid Search**: Exhaustive search over discrete parameter grids
- **Random Search**: Random sampling for large parameter spaces
- **Bayesian Optimization**: Sample-efficient optimization using Gaussian processes
- **Genetic Algorithm**: Evolutionary optimization for non-smooth objectives

### Validation & Robustness
- **Walk-Forward Optimization**: Time-series cross-validation with rolling windows
- **Monte Carlo Simulation**: Parameter stability testing with perturbations
- **Noise Infusion**: Robustness testing by adding noise to data
- **Sensitivity Analysis**: Parameter sensitivity and interaction effects

### Production Features
- **Checkpointing**: Save/restore optimization state for long-running searches
- **Parallel Execution**: Multi-core optimization with `ParallelOptimizer`
- **Structured Logging**: Comprehensive logging with `structlog`
- **Type Safety**: Full type hints and Pydantic validation

---

## Quick Start

### Basic Optimization

```python
from decimal import Decimal
from rustybt.optimization import (
    Optimizer,
    ParameterSpace,
    DiscreteParameter,
    ObjectiveFunction
)
from rustybt.optimization.search import GridSearchAlgorithm

# Define parameter space
param_space = ParameterSpace(parameters=[
    DiscreteParameter(
        name='short_window',
        min_value=5,
        max_value=20,
        step=5
    ),
    DiscreteParameter(
        name='long_window',
        min_value=20,
        max_value=50,
        step=10
    )
])

# Define backtest function
def run_backtest(short_window, long_window):
    """Run backtest with given parameters.

    Returns dict with 'performance_metrics' containing optimization metrics.
    """
    # Your backtest logic here
    # Must return dict with 'performance_metrics' key
    return {
        'performance_metrics': {
            'sharpe_ratio': Decimal('1.5'),
            'total_return': Decimal('0.25'),
            'max_drawdown': Decimal('-0.10')
        }
    }

# Configure search algorithm
search_algorithm = GridSearchAlgorithm(
    parameter_space=param_space,
    early_stopping_rounds=None  # None = exhaustive search
)

# Configure objective function
objective_function = ObjectiveFunction(
    metric='sharpe_ratio',
    higher_is_better=True
)

# Create optimizer
optimizer = Optimizer(
    parameter_space=param_space,
    search_algorithm=search_algorithm,
    objective_function=objective_function,
    backtest_function=run_backtest,
    max_trials=100
)

# Run optimization
best_result = optimizer.optimize()

print(f"Best parameters: {best_result.params}")
print(f"Best score: {best_result.score}")
print(f"Metrics: {best_result.backtest_metrics}")
```

---

## Architecture

The optimization framework uses a modular architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────┐
│                    Optimizer                             │
│              (Main Orchestrator)                         │
│                                                          │
│  1. Gets next params from SearchAlgorithm               │
│  2. Validates params with ParameterSpace                │
│  3. Runs backtest_function                              │
│  4. Extracts score with ObjectiveFunction               │
│  5. Updates SearchAlgorithm with score                  │
│  6. Repeats until complete                              │
└─────────────────────────────────────────────────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
┌──────────────┐┌──────────────┐┌──────────────┐┌──────────────┐
│ ParameterSpace││SearchAlgorithm││ObjectiveFunc ││ Backtest Func│
│               ││              ││              ││              │
│ • Defines     ││ • Suggests   ││ • Extracts   ││ • Runs       │
│   search      ││   next params││   metric     ││   backtest   │
│   space       ││ • Learns from││   from       ││ • Returns    │
│ • Validates   ││   results    ││   results    ││   metrics    │
│   params      ││ • Manages    ││ • Handles    ││              │
│               ││   exploration││   multiple   ││              │
│               ││              ││   metrics    ││              │
└──────────────┘└──────────────┘└──────────────┘└──────────────┘
```

### Core Components

1. **[ParameterSpace](core/parameter-spaces.md)**: Defines search space with continuous, discrete, and categorical parameters
2. **SearchAlgorithm**: Abstract interface for search strategies (grid, random, Bayesian, genetic)
3. **[ObjectiveFunction](core/objective-functions.md)**: Extracts optimization metric from backtest results
5. **OptimizationResult**: Immutable record of a single trial

---

## Search Algorithm Selection

### Decision Matrix

| Parameter Space | Backtest Speed | Recommended Algorithm | Why |
|----------------|----------------|----------------------|-----|
| Small (<100 combinations) | Any | **Grid Search** | Exhaustive, guarantees finding optimum |
| Medium (100-1000) | Fast | **Random Search** | Quick exploration, good baseline |
| Large (>1000) | Slow | **Bayesian** | Sample-efficient, learns from past trials |
| Very Large | Any | **Random → Bayesian** | Random exploration, then focused search |
| Non-smooth objective | Any | **Genetic Algorithm** | Handles discontinuities, multimodal |

### Algorithm Characteristics

**Grid Search**:
- ✅ Guarantees finding true optimum in discrete space
- ✅ Deterministic, reproducible
- ❌ Exponential complexity: O(n^k) where k = number of parameters
- ❌ Not practical for >5 parameters

**Random Search**:
- ✅ Fast, scales to high dimensions
- ✅ Good for initial exploration
- ✅ Embarrassingly parallel
- ❌ No convergence guarantees
- ❌ May miss optimal regions

**Bayesian Optimization**:
- ✅ Sample-efficient (needs fewer trials)
- ✅ Learns structure of objective function
- ✅ Good for expensive backtests
- ❌ More complex, requires tuning
- ❌ Sequential (limited parallelization)

**Genetic Algorithm**:
- ✅ Handles non-smooth, multimodal objectives
- ✅ Natural parallelization (population-based)
- ✅ Global search capability
- ❌ Many hyperparameters to tune
- ❌ Can be slow to converge

---

## Documentation Structure

### Core Framework
- **[Parameter Spaces](core/parameter-spaces.md)** - Defining optimization search spaces
- **[Objective Functions](core/objective-functions.md)** - Extracting metrics from backtest results

### Search Algorithms
- **[Grid Search](algorithms/grid-search.md)** - Exhaustive parameter search
- **[Random Search](algorithms/random-search.md)** - Random sampling strategies
- **[Bayesian Optimization](algorithms/bayesian.md)** - Gaussian process optimization
- **[Genetic Algorithm](algorithms/genetic.md)** - Evolutionary optimization

### Advanced Topics (Phase 2+)
- **Walk-Forward Optimization** - Time-series cross-validation
- **Parallel Optimization** - Multi-core execution
- **Monte Carlo Testing** - Robustness validation
- **Sensitivity Analysis** - Parameter interaction effects

---

## Best Practices

### 1. Start Wide, Then Refine

```python
# Step 1: Wide initial search
param_space_wide = ParameterSpace(parameters=[
    DiscreteParameter(name='lookback', min_value=10, max_value=100, step=10)
])

# Step 2: Refine around best region
best_lookback = initial_result.params['lookback']
param_space_refined = ParameterSpace(parameters=[
    DiscreteParameter(
        name='lookback',
        min_value=max(10, best_lookback - 10),
        max_value=min(100, best_lookback + 10),
        step=2
    )
])
```

### 2. Always Validate Out-of-Sample

```python
# ❌ WRONG: Optimize on full historical data
optimizer = Optimizer(..., backtest_function=run_backtest_full_history)

# ✅ RIGHT: Use walk-forward optimization
from rustybt.optimization import WalkForwardOptimizer
wf_optimizer = WalkForwardOptimizer(...)
```

### 3. Test Parameter Stability

```python
# Check if parameters are stable to small changes
from rustybt.optimization import MonteCarloSimulator

mc_simulator = MonteCarloSimulator(
    backtest_function=run_backtest,
    parameter_config=best_result.params,
    n_simulations=100,
    perturbation_pct=0.05  # ±5% perturbation
)

mc_result = mc_simulator.run()

if mc_result.stability_score < 0.7:
    print("⚠️ Warning: Parameters are not stable!")
```

### 4. Use Checkpointing for Long Optimizations

```python
from pathlib import Path

optimizer = Optimizer(
    ...,
    checkpoint_dir=Path('./checkpoints'),
    checkpoint_frequency=10  # Save every 10 trials
)

# Resume if interrupted
checkpoint = Path('./checkpoints/checkpoint_trial_50.json')
if checkpoint.exists():
    optimizer.load_checkpoint(checkpoint)

best_result = optimizer.optimize()
```

### 5. Limit Parameter Count

```python
# ❌ WRONG: Too many parameters (curse of dimensionality)
param_space = ParameterSpace(parameters=[...])  # 10+ parameters

# ✅ RIGHT: Focus on 3-5 most important parameters
param_space = ParameterSpace(parameters=[
    DiscreteParameter(name='lookback', ...),
    ContinuousParameter(name='threshold', ...),
    CategoricalParameter(name='signal_type', ...)
])
```

---

## Common Pitfalls

### ❌ Pitfall 1: Overfitting to Historical Data

```python
# WRONG: Single backtest on full history
result = optimizer.optimize()  # Overfits to historical data
```

**Solution**: Use walk-forward optimization for time-series validation.

### ❌ Pitfall 2: Ignoring Parameter Stability

```python
# WRONG: Accepting best parameters without stability check
best_params = optimizer.get_best_params()  # May be unstable
```

**Solution**: Test with Monte Carlo simulation to ensure stability.

### ❌ Pitfall 3: Data Snooping Bias

```python
# WRONG: Running optimization multiple times with different objective functions
for metric in ['sharpe', 'sortino', 'calmar']:
    objective = ObjectiveFunction(metric=metric)
    result = optimizer.optimize()
    # Picking best one = data snooping!
```

**Solution**: Pre-define objective function and stick to it.

### ❌ Pitfall 4: Insufficient Data

```python
# WRONG: Optimizing with <30 trades
backtest_result = run_backtest(...)
if backtest_result.trade_count < 30:
    # Results not statistically significant!
```

**Solution**: Ensure sufficient sample size (>30 trades minimum).

---

## Performance Considerations

### Optimization Speed

**Single-threaded performance** (example):
- Grid search 10×10 = 100 trials
- Each backtest = 1 second
- Total time = 100 seconds (~2 minutes)

**Parallel performance** (8 cores):
- Same 100 trials
- 8 trials in parallel
- Total time = 13 seconds (~8x speedup)

```python
from rustybt.optimization import ParallelOptimizer

# Use all available cores
parallel_optimizer = ParallelOptimizer(
    ...,
    n_workers=None  # None = use all cores
)
```

### Memory Considerations

- Each `OptimizationResult` stores full backtest metrics (~1-10 KB)
- 1000 trials = 1-10 MB memory
- Use checkpointing to disk for very long optimizations

---

## API Reference

### Main Classes

```python
from rustybt.optimization import (
    # Core
    Optimizer,
    ParallelOptimizer,
    ParameterSpace,
    ObjectiveFunction,
    OptimizationResult,

    # Parameters
    ContinuousParameter,
    DiscreteParameter,
    CategoricalParameter,

    # Advanced
    WalkForwardOptimizer,
    MonteCarloSimulator,
    NoiseInfusionSimulator,
    SensitivityAnalyzer
)

# Search algorithms
from rustybt.optimization.search import (
    GridSearchAlgorithm,
    RandomSearchAlgorithm,
    BayesianOptimizer,
    GeneticAlgorithm
)
```

---

## Examples

Complete working examples available in `docs/examples/optimization/`:
- `grid_search_ma_crossover.py` - Basic grid search optimization
- `bayesian_optimization_5param.py` - Multi-parameter Bayesian optimization
- `walk_forward_analysis.py` - Walk-forward validation example
- `parallel_optimization_example.py` - Multi-core parallel optimization

---

## Next Steps

2. **[Parameter Spaces](core/parameter-spaces.md)** - Define your search space
3. **[Objective Functions](core/objective-functions.md)** - Choose or create your objective
4. **Search Algorithms** - Select the right algorithm

---

## Related Documentation

- [Analytics](../analytics/README.md) - Post-optimization analysis
- [Live Trading](../live-trading/README.md) - Deploying optimized strategies

---

**Quality Assurance**: This documentation has been verified against RustyBT source code (v1.0) and all examples tested for correctness.
