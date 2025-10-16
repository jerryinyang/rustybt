# Optimization Framework

Comprehensive guide to RustyBT's optimization framework for systematic parameter tuning and strategy validation.

## Overview

The optimization framework provides tools for finding optimal strategy parameters while preventing overfitting. It includes multiple search algorithms, validation techniques, and robustness testing methods.

### Key Features

- **Multiple Search Algorithms**: Grid, random, Bayesian, and genetic optimization
- **Walk-Forward Analysis**: Out-of-sample validation to prevent overfitting
- **Monte Carlo Testing**: Robustness validation with noise infusion
- **Parallel Processing**: Distributed optimization for large parameter spaces
- **Best Practices Built-In**: Overfitting prevention and validation techniques

### Architecture

```
┌─────────────────────────────────────────────────────┐
│           Parameter Space Definition                 │
├─────────────────────────────────────────────────────┤
│           Search Algorithm Selection                 │
│   (Grid / Random / Bayesian / Genetic)              │
├─────────────────────────────────────────────────────┤
│         Objective Function Evaluation                │
│       (Backtest with Parameters)                     │
├─────────────────────────────────────────────────────┤
│              Result Analysis                         │
│    (Best Parameters + Validation)                    │
├─────────────────────────────────────────────────────┤
│         Walk-Forward Validation                      │
│      (Out-of-Sample Performance)                     │
├─────────────────────────────────────────────────────┤
│          Monte Carlo Robustness                      │
│       (Parameter Stability Testing)                  │
└─────────────────────────────────────────────────────┘
```

## Quick Navigation

### Core Framework
- **Architecture** - Optimization system architecture and design patterns
- **[Parameter Spaces](framework/parameter-spaces.md)** - Defining search spaces for optimization
- **[Objective Functions](framework/objective-functions.md)** - Designing objective functions and metrics

### Search Algorithms
- **[Grid Search](algorithms/grid-search.md)** - Exhaustive search over parameter grid
- **[Random Search](algorithms/random-search.md)** - Random sampling strategies
- **[Bayesian Optimization](algorithms/bayesian.md)** - Gaussian process-based optimization
- **[Genetic Algorithms](algorithms/genetic.md)** - Evolutionary optimization strategies

### Validation Techniques
- **[Walk-Forward Framework](walk-forward/framework.md)** - Walk-forward optimization architecture
- **[Window Sizing](walk-forward/windows.md)** - Training and testing window strategies
- **[Out-of-Sample Validation](walk-forward/validation.md)** - Validation methodologies

### Robustness Testing
- **Monte Carlo Framework (Coming soon)** - Data permutation techniques
- **Noise Infusion (Coming soon)** - Adding noise for robustness
- **[Stability Testing](monte-carlo/stability-testing.md)** - Parameter stability analysis

### Performance & Scaling
- **[Multiprocessing](parallel/multiprocessing.md)** - Parallel optimization with multiprocessing
- **Distributed Computing (Coming soon)** - Scaling to clusters

### Best Practices
- **[Overfitting Prevention](best-practices/overfitting-prevention.md)** - Avoiding overfitting pitfalls
- **Validation Techniques (Coming soon)** - Comprehensive validation strategies

## Quick Start

### Basic Optimization

```python
from rustybt.optimization import Optimizer
from rustybt.optimization.parameter_space import ParameterSpace, DiscreteParameter

# Define parameter space
param_space = ParameterSpace(parameters=[
    DiscreteParameter(name='lookback', min_value=10, max_value=100, step=10)
])

# Define objective function
def run_backtest(params):
    # Your backtest logic
    return sharpe_ratio

# Run optimization
optimizer = Optimizer(
    objective_function=run_backtest,
    parameter_space=param_space,
    algorithm='bayesian',
    n_iterations=50
)

result = optimizer.optimize()
print(f"Best params: {result.best_params}")
```

### Walk-Forward Validation

```python
from rustybt.optimization import WalkForwardOptimizer

wf = WalkForwardOptimizer(
    objective_function=run_backtest,
    parameter_space=param_space,
    train_period_days=252,
    test_period_days=63,
    start_date='2020-01-01',
    end_date='2023-12-31'
)

result = wf.optimize()
print(f"In-sample Sharpe: {result.in_sample_metrics['sharpe']}")
print(f"Out-of-sample Sharpe: {result.out_of_sample_metrics['sharpe']}")
```

## Algorithm Selection Guide

| Use Case | Recommended Algorithm | Why |
|----------|----------------------|-----|
| Small parameter space (<1000 combinations) | Grid Search | Complete coverage, deterministic |
| Large continuous space | Bayesian Optimization | Sample-efficient, exploits structure |
| Non-smooth objective | Genetic Algorithm | Handles discontinuities |
| Initial exploration | Random Search | Fast, good baseline |
| Production validation | Walk-Forward | Realistic out-of-sample testing |

## Common Workflows

### Workflow 1: Basic Parameter Tuning

1. Define parameter space
2. Choose search algorithm based on space size
3. Run optimization
4. Validate with out-of-sample data

### Workflow 2: Production-Ready Optimization

1. Initial exploration with random search
2. Refinement with Bayesian optimization
3. Walk-forward validation
4. Monte Carlo robustness testing
5. Final verification with grid search in narrow region

### Workflow 3: Large-Scale Optimization

1. Define parameter space
2. Use parallel random or grid search
3. Identify promising regions
4. Refine with Bayesian optimization
5. Validate with walk-forward

## Key Concepts

### Parameter Types

- **Continuous**: Float/Decimal parameters (e.g., threshold from 0.01 to 0.10)
- **Discrete**: Integer parameters with step size (e.g., lookback from 10 to 100, step 5)
- **Categorical**: Fixed choices (e.g., signal type: 'momentum', 'mean_reversion')

### Objective Functions

- **Sharpe Ratio**: Risk-adjusted returns (most common)
- **Sortino Ratio**: Downside risk-adjusted returns
- **Calmar Ratio**: Return / max drawdown
- **Custom Metrics**: Any quantifiable strategy metric

### Overfitting Prevention

⚠️ **Critical Warning**: Optimization without validation leads to overfitting!

**Always use**:
1. **Walk-forward analysis** - Out-of-sample testing
2. **Parameter stability** - Small changes shouldn't drastically affect results
3. **Monte Carlo testing** - Robustness to noise
4. **Simplicity bias** - Prefer simpler strategies when performance is similar

## Performance Considerations

### Optimization Speed

| Algorithm | Speed | Sample Efficiency | Best For |
|-----------|-------|-------------------|----------|
| Grid Search | Slow (O(n^p)) | Low | Small spaces |
| Random Search | Fast | Medium | Exploration |
| Bayesian | Medium | High | Expensive objectives |
| Genetic | Medium | Medium | Non-smooth functions |

### Parallelization

- **Grid/Random Search**: Embarrassingly parallel, scales linearly
- **Genetic Algorithm**: Population-based, natural parallelism
- **Bayesian**: Sequential by nature, limited parallelization

## Common Pitfalls

### 1. Data Snooping Bias

❌ **Wrong**: Optimizing on full historical data
✅ **Right**: Walk-forward with strict temporal separation

### 2. Overfitting to Noise

❌ **Wrong**: Accepting best in-sample parameters
✅ **Right**: Validating out-of-sample and testing robustness

### 3. Optimization Bias

❌ **Wrong**: Trying hundreds of objective functions until one looks good
✅ **Right**: Pre-define objective function and stick to it

### 4. Insufficient Data

❌ **Wrong**: Optimizing with <100 trades
✅ **Right**: Ensure statistical significance (>30 trades minimum)

### 5. Look-Ahead Bias

❌ **Wrong**: Using future data in objective function
✅ **Right**: Strict point-in-time data access

## Examples

See the `examples/optimization/` directory for complete examples:

- `grid_search_ma_crossover.py` - Basic grid search
- `bayesian_optimization_5param.py` - Multi-parameter Bayesian optimization
- `walk_forward_analysis.py` - Walk-forward validation
- `parallel_optimization_example.py` - Distributed optimization
- `monte_carlo_robustness.py` - Robustness testing

## See Also

- [Main Optimization API Reference](../optimization-api.md)
- [Analytics Documentation](../analytics/README.md)
- [Live Trading Documentation](../live-trading/README.md)
- [Examples & Tutorials](../../examples/README.md)

## Support

- **Issues**: [GitHub Issues](https://github.com/bmad-dev/rustybt/issues)
- **Discussions**: [GitHub Discussions](https://github.com/bmad-dev/rustybt/discussions)
- **Documentation**: [Full API Reference](https://rustybt.readthedocs.io)
