# Walk-Forward Optimization Framework

Out-of-sample validation to prevent overfitting through temporal validation.

## Overview

Walk-forward optimization simulates realistic trading by:
1. Optimizing parameters on historical (training) data
2. Testing on unseen future (testing) data
3. Rolling the window forward through time
4. Aggregating out-of-sample performance

This prevents overfitting by ensuring parameters work on data they haven't "seen" during optimization.

## Key Concepts

### Training Period

Historical data used for parameter optimization.

```
[Training Period: Optimize Parameters]
```

**Typical length**: 6 months to 2 years

### Testing Period

Future data used for out-of-sample validation.

```
[Training Period][Testing Period: Apply Best Params]
```

**Typical length**: 1-3 months

### Window Types

#### Rolling Window

Fixed-size window that moves forward.

```
Window 1: [Train 1][Test 1]
Window 2:         [Train 2][Test 2]
Window 3:                 [Train 3][Test 3]
```

**Use when**: Recent data most relevant, regime changes

#### Anchored Window

Growing window anchored at start.

```
Window 1: [Train 1][Test 1]
Window 2: [Train 1 + Train 2][Test 2]
Window 3: [Train 1 + Train 2 + Train 3][Test 3]
```

**Use when**: More data = better optimization, stable regimes

## Basic Usage

```python
from rustybt.optimization import WalkForwardOptimizer
from rustybt.optimization.parameter_space import ParameterSpace, DiscreteParameter

# Define parameter space
param_space = ParameterSpace(parameters=[
    DiscreteParameter('lookback', 10, 100, step=10)
])

# Define objective function with date range
def run_backtest_period(params, start_date, end_date):
    """Run backtest for specific period."""
    result = run_backtest(
        strategy=MyStrategy(**params),
        start_date=start_date,
        end_date=end_date
    )
    return calculate_sharpe(result)

# Create walk-forward optimizer
wf = WalkForwardOptimizer(
    objective_function=run_backtest_period,
    parameter_space=param_space,
    train_period_days=252,  # 1 year training
    test_period_days=63,    # 3 months testing
    reoptimize_frequency_days=63,  # Reoptimize every 3 months
    start_date='2020-01-01',
    end_date='2023-12-31',
    algorithm='bayesian',
    n_iterations_per_window=50,
    anchored=False  # Rolling window
)

# Run walk-forward optimization
result = wf.optimize()

# View results
print(f"In-sample Sharpe: {result.in_sample_metrics['sharpe']:.3f}")
print(f"Out-of-sample Sharpe: {result.out_of_sample_metrics['sharpe']:.3f}")
print(f"Degradation: {result.degradation:.1%}")
```

## Constructor

```python
WalkForwardOptimizer(
    objective_function: Callable,
    parameter_space: ParameterSpace,
    train_period_days: int,
    test_period_days: int,
    reoptimize_frequency_days: int,
    start_date: str | pd.Timestamp,
    end_date: str | pd.Timestamp,
    algorithm: str = 'bayesian',
    n_iterations_per_window: int = 50,
    anchored: bool = False
)
```

**Parameters**:
- `objective_function`: Function with signature `(params, start, end) -> Decimal`
- `parameter_space`: Parameter space to optimize
- `train_period_days`: Training window size in trading days
- `test_period_days`: Testing window size in trading days
- `reoptimize_frequency_days`: How often to reoptimize (usually = test_period_days)
- `start_date`: Overall start date
- `end_date`: Overall end date
- `algorithm`: Optimization algorithm ('grid', 'random', 'bayesian', 'genetic')
- `n_iterations_per_window`: Optimization iterations per training window
- `anchored`: If True, use anchored window; if False, use rolling window

## Results Structure

```python
class WalkForwardResult:
    in_sample_metrics: Dict[str, Decimal]
    out_of_sample_metrics: Dict[str, Decimal]
    per_window_results: List[WindowResult]
    degradation: float
    parameter_stability: Dict[str, float]
```

### In-Sample Metrics

Performance during training periods:

```python
{
    'sharpe': Decimal('2.5'),
    'sortino': Decimal('3.1'),
    'max_drawdown': Decimal('-0.15'),
    'annual_return': Decimal('0.35')
}
```

### Out-of-Sample Metrics

Performance during testing periods (what matters!):

```python
{
    'sharpe': Decimal('1.8'),  # Lower than in-sample (expected)
    'sortino': Decimal('2.2'),
    'max_drawdown': Decimal('-0.22'),
    'annual_return': Decimal('0.25')
}
```

### Degradation

How much performance drops from in-sample to out-of-sample:

```python
degradation = 1 - (oos_sharpe / is_sharpe)
# Example: 1 - (1.8 / 2.5) = 0.28 = 28% degradation
```

**Interpretation**:
- <20%: Good generalization
- 20-40%: Acceptable degradation
- >40%: Likely overfitting

### Parameter Stability

How much parameters change between windows:

```python
{
    'lookback': 0.15,  # 15% average change
    'threshold': 0.25   # 25% average change
}
```

**Interpretation**:
- <20%: Stable parameters
- 20-50%: Moderate stability
- >50%: Unstable (regime-dependent)

## Complete Example

```python
from decimal import Decimal
import pandas as pd
from rustybt.optimization import WalkForwardOptimizer
from rustybt.optimization.parameter_space import ParameterSpace, DiscreteParameter

# Define parameter space
param_space = ParameterSpace(parameters=[
    DiscreteParameter('ma_short', 10, 50, step=5),
    DiscreteParameter('ma_long', 50, 200, step=25)
])

# Define objective function
def backtest_ma_crossover(params, start_date, end_date):
    """Moving average crossover strategy."""
    result = run_backtest(
        strategy=MACrossover(
            short_window=params['ma_short'],
            long_window=params['ma_long']
        ),
        start_date=start_date,
        end_date=end_date,
        capital_base=100000
    )
    return Decimal(str(result['sharpe_ratio']))

# Create walk-forward optimizer
wf = WalkForwardOptimizer(
    objective_function=backtest_ma_crossover,
    parameter_space=param_space,
    train_period_days=252,  # 1 year training
    test_period_days=63,    # 3 months testing
    reoptimize_frequency_days=63,  # Reoptimize every test period
    start_date='2018-01-01',
    end_date='2023-12-31',
    algorithm='bayesian',
    n_iterations_per_window=30,
    anchored=False  # Rolling window
)

print("Starting walk-forward optimization...")
print(f"Training period: {wf.train_period_days} days")
print(f"Testing period: {wf.test_period_days} days")
print(f"Number of windows: {wf.n_windows}")

# Run optimization
result = wf.optimize()

# Print summary
print("\n=== Walk-Forward Results ===")
print(f"\nIn-Sample Performance:")
print(f"  Sharpe Ratio: {result.in_sample_metrics['sharpe']:.3f}")
print(f"  Annual Return: {result.in_sample_metrics['annual_return']:.2%}")
print(f"  Max Drawdown: {result.in_sample_metrics['max_drawdown']:.2%}")

print(f"\nOut-of-Sample Performance:")
print(f"  Sharpe Ratio: {result.out_of_sample_metrics['sharpe']:.3f}")
print(f"  Annual Return: {result.out_of-sample_metrics['annual_return']:.2%}")
print(f"  Max Drawdown: {result.out_of_sample_metrics['max_drawdown']:.2%}")

print(f"\nDegradation: {result.degradation:.1%}")

print(f"\nParameter Stability:")
for param, stability in result.parameter_stability.items():
    print(f"  {param}: {stability:.1%} variation")

# Per-window analysis
print("\n=== Per-Window Results ===")
for i, window in enumerate(result.per_window_results, 1):
    print(f"\nWindow {i}:")
    print(f"  Train: {window.train_start} to {window.train_end}")
    print(f"  Test: {window.test_start} to {window.test_end}")
    print(f"  Best params: {window.best_params}")
    print(f"  IS Sharpe: {window.is_sharpe:.3f}")
    print(f"  OOS Sharpe: {window.oos_sharpe:.3f}")
```

## Visualization

### Equity Curves

Compare in-sample vs out-of-sample:

```python
def plot_walk_forward_equity(result):
    """Plot in-sample and out-of-sample equity curves."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(14, 7))

    # Plot each window
    for window in result.per_window_results:
        # In-sample (training) in blue
        ax.plot(window.train_dates, window.train_equity,
                'b-', alpha=0.3, linewidth=1)

        # Out-of-sample (testing) in red
        ax.plot(window.test_dates, window.test_equity,
                'r-', alpha=0.8, linewidth=2)

    ax.set_xlabel('Date')
    ax.set_ylabel('Portfolio Value')
    ax.set_title('Walk-Forward Analysis: In-Sample vs Out-of-Sample')
    ax.legend(['In-Sample (Training)', 'Out-of-Sample (Testing)'])
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    return fig
```

### Parameter Evolution

Track how optimal parameters change over time:

```python
def plot_parameter_evolution(result):
    """Plot optimal parameters over time."""
    import matplotlib.pyplot as plt

    params_over_time = {}
    for window in result.per_window_results:
        for param, value in window.best_params.items():
            if param not in params_over_time:
                params_over_time[param] = []
            params_over_time[param].append({
                'date': window.train_end,
                'value': value
            })

    fig, axes = plt.subplots(len(params_over_time), 1,
                             figsize=(12, 4*len(params_over_time)))

    if len(params_over_time) == 1:
        axes = [axes]

    for ax, (param, values) in zip(axes, params_over_time.items()):
        dates = [v['date'] for v in values]
        vals = [v['value'] for v in values]

        ax.plot(dates, vals, 'o-', linewidth=2, markersize=8)
        ax.set_xlabel('Date')
        ax.set_ylabel(param)
        ax.set_title(f'Optimal {param} Over Time')
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    return fig
```

## Best Practices

### 1. Appropriate Window Sizes

**Training period**:
- Too short (<6 months): Insufficient data, unstable optimization
- Too long (>3 years): Old data may be irrelevant
- **Recommended**: 1-2 years

**Testing period**:
- Too short (<1 month): High variance in results
- Too long (>6 months): Parameters become stale
- **Recommended**: 1-3 months

### 2. Reoptimization Frequency

Usually equals testing period:

```python
reoptimize_frequency_days = test_period_days
```

**More frequent**: Parameters adapt faster but risk overfitting
**Less frequent**: More stable but may miss regime changes

### 3. Anchored vs Rolling

**Use anchored when**:
- More data improves optimization
- Market regime is stable
- Long-term relationships are important

**Use rolling when**:
- Recent data is most relevant
- Market regimes change
- Adaptive strategies

### 4. Degradation Thresholds

**Accept strategy if**:
- Degradation <30%
- OOS Sharpe >1.0
- Parameter stability <40%

**Reject strategy if**:
- Degradation >50%
- OOS Sharpe <0.5
- Parameter stability >60%

## Common Pitfalls

### ❌ Using Same Test Period Multiple Times

```python
# WRONG: Same test data seen multiple times
train_period = 252
test_period = 63
reoptimize = 21  # Reoptimizing every 21 days!
# This means each data point is in 3 test periods!
```

### ❌ Too Few Windows

```python
# WRONG: Only 2 windows, not enough for validation
total_days = 500
train_period = 400
test_period = 100
# Only 1-2 windows!
```

**Recommendation**: At least 5-10 windows for reliable validation.

### ❌ Look-Ahead Bias

```python
# WRONG: Using future data in training
def objective(params, start, end):
    # Bug: Accidentally using data beyond 'end'
    result = run_backtest(params, start, '2023-12-31')  # WRONG!
    return calculate_sharpe(result)
```

Always respect the date boundaries!

## See Also

- [Window Sizing Strategies](windows.md)
- [Out-of-Sample Validation](validation.md)
- [Overfitting Prevention](../best-practices/overfitting-prevention.md)
- [Main Optimization API](../../optimization-api.md)
