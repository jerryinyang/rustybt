# Performance Tracking

**Module**: `rustybt.finance.metrics`

**Source Files**:
- `rustybt/finance/metrics/decimal_tracker.py` (373 lines)
- `rustybt/finance/metrics/formatting.py` (10,823 bytes)

**Last Updated**: 2025-10-16
**Confidence**: 100% (all APIs verified against source code)

---

## Overview

The RustyBT performance tracking system provides comprehensive tracking and calculation of performance metrics with Decimal precision for audit-compliant financial analysis. The core component is the **DecimalMetricsTracker**, which maintains a history of returns and automatically calculates a full suite of performance metrics.

### Key Features

- **Decimal Precision**: All calculations use Python's `Decimal` type for audit compliance
- **Comprehensive Metrics**: 15+ performance metrics calculated automatically
- **Benchmark Comparison**: Track strategy vs benchmark with information ratio and tracking error
- **Trade Analysis**: Win rate, profit factor, and trade-level statistics
- **Custom Metrics**: Register custom metric calculations
- **Caching**: Automatic caching for performance optimization
- **Multiple Output Formats**: Formatted tables, JSON, or raw dictionaries

---

## DecimalMetricsTracker

**Source**: `rustybt/finance/metrics/decimal_tracker.py:45-373`

The main class for tracking and calculating performance metrics with Decimal precision.

### Class Definition

```python
from rustybt.finance.metrics.decimal_tracker import DecimalMetricsTracker
from rustybt.finance.decimal.config import DecimalConfig
from decimal import Decimal

tracker = DecimalMetricsTracker(
    strategy_name="MyStrategy",
    risk_free_rate=Decimal("0.02"),        # 2% annual risk-free rate
    annualization_factor=252,               # 252 trading days per year
    config=None                             # Uses default DecimalConfig
)
```

### Constructor Parameters

**Source**: `decimal_tracker.py:58-76`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `strategy_name` | `str` | `"Strategy"` | Name of the strategy being tracked |
| `risk_free_rate` | `Decimal` | `Decimal("0.02")` | Annual risk-free rate (e.g., `Decimal("0.02")` = 2%) |
| `annualization_factor` | `int` | `252` | Periods per year (252 for daily, 12 for monthly, 1 for annual) |
| `config` | `DecimalConfig \| None` | `None` | DecimalConfig for precision (uses default if None) |

---

## Core Methods

### update()

**Source**: `decimal_tracker.py:95-140`

Update the tracker with new returns data.

```python
def update(
    self,
    returns: pl.Series,                    # Required: new returns
    trade_returns: pl.Series | None = None,  # Optional: trade-level returns
    benchmark_returns: pl.Series | None = None,  # Optional: benchmark returns
) -> None
```

**Parameters**:
- `returns`: New returns data as Polars Series with Decimal values
- `trade_returns`: Optional trade-level returns for win rate / profit factor
- `benchmark_returns`: Optional benchmark returns for information ratio / tracking error

**Behavior**:
- Appends returns to history
- Updates cumulative returns (compounds returns)
- Optionally appends trade and benchmark returns
- Invalidates metrics cache

**Example**:
```python
import polars as pl
from decimal import Decimal

# Daily returns
returns = pl.Series("returns", [
    Decimal("0.01"),   # +1% day 1
    Decimal("-0.005"), # -0.5% day 2
    Decimal("0.015"),  # +1.5% day 3
])

tracker.update(returns=returns)

# With benchmark comparison
spy_returns = pl.Series("spy", [
    Decimal("0.008"),
    Decimal("-0.003"),
    Decimal("0.012"),
])

tracker.update(
    returns=returns,
    benchmark_returns=spy_returns,
)
```

---

### calculate_all_metrics()

**Source**: `decimal_tracker.py:158-308`

Calculate the full suite of performance metrics.

```python
def calculate_all_metrics(
    self,
    force_recalculate: bool = False
) -> dict[str, Decimal]
```

**Parameters**:
- `force_recalculate`: Force recalculation even if cache is valid (default: `False`)

**Returns**: Dictionary mapping metric name to Decimal value

**Metrics Calculated** (when sufficient data exists):

| Metric Name | Description | Source Function |
|-------------|-------------|-----------------|
| `sharpe_ratio` | Risk-adjusted return (Sharpe ratio) | `calculate_sharpe_ratio()` |
| `sortino_ratio` | Downside risk-adjusted return | `calculate_sortino_ratio()` |
| `max_drawdown` | Maximum peak-to-trough decline | `calculate_max_drawdown()` |
| `calmar_ratio` | Return / max drawdown | `calculate_calmar_ratio()` |
| `var_95` | 95% Value at Risk | `calculate_var(confidence_level=0.05)` |
| `var_99` | 99% Value at Risk | `calculate_var(confidence_level=0.01)` |
| `cvar_95` | 95% Conditional VaR (Expected Shortfall) | `calculate_cvar(confidence_level=0.05)` |
| `cvar_99` | 99% Conditional VaR | `calculate_cvar(confidence_level=0.01)` |
| `win_rate` | Percentage of profitable trades (if trade data provided) | `calculate_win_rate()` |
| `profit_factor` | Gross profits / gross losses (if trade data provided) | `calculate_profit_factor()` |
| `information_ratio` | Excess return / tracking error (if benchmark provided) | `calculate_information_ratio()` |
| `tracking_error` | Volatility of excess returns (if benchmark provided) | `calculate_tracking_error()` |
| `mean_return` | Mean of returns | Polars `.mean()` |
| `volatility` | Standard deviation of returns | Polars `.std()` |
| `cumulative_return` | Total return over period | Final cumulative - 1.0 |
| `annual_return` | Annualized return | `(1 + total_return) ^ (1/years) - 1` |

**Example**:
```python
# Calculate all metrics
metrics = tracker.calculate_all_metrics()

# Access specific metrics
print(f"Sharpe Ratio: {metrics['sharpe_ratio']}")
print(f"Max Drawdown: {metrics['max_drawdown']}")
print(f"Annual Return: {metrics['annual_return']}")

# Force recalculation (bypass cache)
fresh_metrics = tracker.calculate_all_metrics(force_recalculate=True)
```

---

### get_metrics_summary()

**Source**: `decimal_tracker.py:309-323`

Get a formatted summary of all metrics as a table.

```python
def get_metrics_summary(
    self,
    precision_map: dict[str, int] | None = None
) -> str
```

**Parameters**:
- `precision_map`: Optional mapping of metric name to display precision (decimal places)

**Returns**: Formatted string with metrics table

**Example**:
```python
# Default formatting
summary = tracker.get_metrics_summary()
print(summary)

# Output:
# ╔═══════════════════╦═══════════╗
# ║ Metric            ║ Value     ║
# ╠═══════════════════╬═══════════╣
# ║ sharpe_ratio      ║ 1.85      ║
# ║ sortino_ratio     ║ 2.34      ║
# ║ max_drawdown      ║ -0.15     ║
# ║ annual_return     ║ 0.24      ║
# ╚═══════════════════╩═══════════╝

# Custom precision
precision = {
    "sharpe_ratio": 4,
    "max_drawdown": 6,
}
summary = tracker.get_metrics_summary(precision_map=precision)
```

---

### get_metrics_json()

**Source**: `decimal_tracker.py:325-335`

Get all metrics as a JSON string.

```python
def get_metrics_json(self) -> str
```

**Returns**: JSON string with all metrics

**Example**:
```python
import json

# Get metrics as JSON
json_str = tracker.get_metrics_json()

# Parse JSON
metrics_dict = json.loads(json_str)
print(metrics_dict["sharpe_ratio"])

# Save to file
with open("metrics.json", "w") as f:
    f.write(json_str)
```

---

### register_custom_metric()

**Source**: `decimal_tracker.py:141-156`

Register a custom metric calculation function.

```python
def register_custom_metric(
    self,
    name: str,
    metric_func: Callable[[pl.Series], Decimal]
) -> None
```

**Parameters**:
- `name`: Name of the custom metric
- `metric_func`: Function that takes returns series and returns a Decimal

**Example**:
```python
from decimal import Decimal
import polars as pl

# Define custom metric: Mean return scaled by 100
def mean_times_100(returns: pl.Series) -> Decimal:
    return Decimal(str(returns.mean())) * Decimal("100")

# Register custom metric
tracker.register_custom_metric("mean_x100", mean_times_100)

# Custom metric will be included in calculate_all_metrics()
metrics = tracker.calculate_all_metrics()
print(metrics["mean_x100"])  # Custom metric available


# Example: Custom metric for maximum single-day gain
def max_daily_gain(returns: pl.Series) -> Decimal:
    return Decimal(str(returns.max()))

tracker.register_custom_metric("max_gain", max_daily_gain)


# Example: Custom metric for average winning day
def avg_winning_day(returns: pl.Series) -> Decimal:
    winning_days = returns.filter(returns > Decimal("0"))
    if len(winning_days) == 0:
        return Decimal("0")
    return Decimal(str(winning_days.mean()))

tracker.register_custom_metric("avg_win", avg_winning_day)

metrics = tracker.calculate_all_metrics()
print(f"Max Daily Gain: {metrics['max_gain']}")
print(f"Avg Winning Day: {metrics['avg_win']}")
```

---

### reset()

**Source**: `decimal_tracker.py:337-350`

Reset all tracked data and clear the cache.

```python
def reset(self) -> None
```

**Example**:
```python
# Reset tracker for new strategy run
tracker.reset()

# All data cleared
assert len(tracker._returns) == 0
assert len(tracker._cumulative_returns) == 1  # [Decimal("1")]
```

---

### get_returns_series()

**Source**: `decimal_tracker.py:352-361`

Get the returns history as a Polars Series.

```python
def get_returns_series(self) -> pl.Series
```

**Returns**: Polars Series with all returns

**Example**:
```python
# Get returns for analysis
returns_series = tracker.get_returns_series()

# Calculate custom statistics
print(f"Mean: {returns_series.mean()}")
print(f"Median: {returns_series.median()}")
print(f"Skewness: {returns_series.skew()}")
```

---

### get_cumulative_returns_series()

**Source**: `decimal_tracker.py:363-373`

Get the cumulative returns history as a Polars Series.

```python
def get_cumulative_returns_series(self) -> pl.Series
```

**Returns**: Polars Series with cumulative returns (starting at 1.0)

**Example**:
```python
# Get cumulative returns for plotting
cumulative = tracker.get_cumulative_returns_series()

# Calculate equity curve statistics
peak = cumulative.max()
trough = cumulative.min()
final = cumulative[-1]

print(f"Peak Portfolio Value: {peak}")
print(f"Final Portfolio Value: {final}")
```

---

## Production Examples

### Example 1: Basic Strategy Performance Tracking

```python
from rustybt.finance.metrics.decimal_tracker import DecimalMetricsTracker
from decimal import Decimal
import polars as pl

# Initialize tracker for daily strategy
tracker = DecimalMetricsTracker(
    strategy_name="MeanReversion",
    risk_free_rate=Decimal("0.02"),  # 2% risk-free rate
    annualization_factor=252,
)

# Simulate strategy returns over 100 days
import random
random.seed(42)

for day in range(100):
    # Generate random daily return
    daily_return = Decimal(str(random.gauss(0.001, 0.015)))

    # Update tracker
    tracker.update(returns=pl.Series([daily_return]))

# Calculate performance metrics
metrics = tracker.calculate_all_metrics()

# Display key metrics
print(f"Strategy: {tracker.strategy_name}")
print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
print(f"Max Drawdown: {metrics['max_drawdown']:.2%}")
print(f"Annual Return: {metrics['annual_return']:.2%}")
print(f"Volatility: {metrics['volatility']:.2%}")
```

---

### Example 2: Benchmark Comparison

```python
from rustybt.finance.metrics.decimal_tracker import DecimalMetricsTracker
from decimal import Decimal
import polars as pl

# Strategy vs SPY benchmark
tracker = DecimalMetricsTracker(
    strategy_name="EnhancedIndex",
    risk_free_rate=Decimal("0.02"),
    annualization_factor=252,
)

# Load historical data (example)
strategy_returns = pl.Series("strategy", [
    Decimal("0.012"), Decimal("-0.008"), Decimal("0.015"),
    Decimal("0.002"), Decimal("-0.005"), Decimal("0.018"),
])

spy_returns = pl.Series("spy", [
    Decimal("0.010"), Decimal("-0.006"), Decimal("0.013"),
    Decimal("0.001"), Decimal("-0.004"), Decimal("0.014"),
])

# Update with benchmark
tracker.update(
    returns=strategy_returns,
    benchmark_returns=spy_returns,
)

# Calculate metrics including benchmark comparison
metrics = tracker.calculate_all_metrics()

# Benchmark-specific metrics
print(f"Information Ratio: {metrics['information_ratio']:.2f}")
print(f"Tracking Error: {metrics['tracking_error']:.2%}")
print(f"Strategy Sharpe: {metrics['sharpe_ratio']:.2f}")

# Compare excess return
strategy_cumulative = tracker.get_cumulative_returns_series()[-1]
benchmark_cumulative = Decimal("1")
for r in spy_returns:
    benchmark_cumulative *= (Decimal("1") + r)

excess_cumulative = strategy_cumulative - benchmark_cumulative
print(f"Excess Return vs Benchmark: {excess_cumulative:.2%}")
```

---

### Example 3: Trade-Level Analysis

```python
from rustybt.finance.metrics.decimal_tracker import DecimalMetricsTracker
from decimal import Decimal
import polars as pl

# Track individual trades
tracker = DecimalMetricsTracker(
    strategy_name="BreakoutTrader",
    annualization_factor=252,
)

# Daily returns
daily_returns = pl.Series("returns", [
    Decimal("0.005"), Decimal("0.002"), Decimal("-0.003"),
    Decimal("0.008"), Decimal("-0.001"),
])

# Trade-level returns (closed trades)
trade_returns = pl.Series("trades", [
    Decimal("0.05"),   # Trade 1: +5%
    Decimal("-0.02"),  # Trade 2: -2%
    Decimal("0.03"),   # Trade 3: +3%
    Decimal("-0.01"),  # Trade 4: -1%
    Decimal("0.07"),   # Trade 5: +7%
])

# Update tracker with both daily and trade data
tracker.update(
    returns=daily_returns,
    trade_returns=trade_returns,
)

# Calculate metrics
metrics = tracker.calculate_all_metrics()

# Trade statistics
print(f"Win Rate: {metrics['win_rate']:.2%}")
print(f"Profit Factor: {metrics['profit_factor']:.2f}")
print(f"Average Return: {metrics['mean_return']:.2%}")

# Interpretation:
# - Win Rate: 60% (3 wins out of 5 trades)
# - Profit Factor: (0.05 + 0.03 + 0.07) / (0.02 + 0.01) = 5.0
#   (For every $1 lost, strategy makes $5)
```

---

### Example 4: Custom Metrics Registration

```python
from rustybt.finance.metrics.decimal_tracker import DecimalMetricsTracker
from decimal import Decimal
import polars as pl

tracker = DecimalMetricsTracker(strategy_name="CustomStrategy")

# Register custom metrics
def calculate_upside_capture(returns: pl.Series) -> Decimal:
    """Calculate percentage of positive returns."""
    positive_count = len(returns.filter(returns > Decimal("0")))
    total_count = len(returns)
    if total_count == 0:
        return Decimal("0")
    return Decimal(str(positive_count)) / Decimal(str(total_count))

def calculate_avg_winner_loser_ratio(returns: pl.Series) -> Decimal:
    """Calculate ratio of average winner to average loser."""
    winners = returns.filter(returns > Decimal("0"))
    losers = returns.filter(returns < Decimal("0"))

    if len(winners) == 0 or len(losers) == 0:
        return Decimal("0")

    avg_winner = Decimal(str(winners.mean()))
    avg_loser = abs(Decimal(str(losers.mean())))

    return avg_winner / avg_loser

# Register both custom metrics
tracker.register_custom_metric("upside_capture", calculate_upside_capture)
tracker.register_custom_metric("win_loss_ratio", calculate_avg_winner_loser_ratio)

# Add returns
returns = pl.Series("returns", [
    Decimal("0.02"), Decimal("-0.01"), Decimal("0.03"),
    Decimal("-0.015"), Decimal("0.025"), Decimal("-0.005"),
])

tracker.update(returns=returns)

# Get all metrics (including custom)
metrics = tracker.calculate_all_metrics()

print(f"Upside Capture: {metrics['upside_capture']:.2%}")
print(f"Win/Loss Ratio: {metrics['win_loss_ratio']:.2f}")
print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
```

---

### Example 5: Real-Time Monitoring During Backtest

```python
from rustybt.finance.metrics.decimal_tracker import DecimalMetricsTracker
from decimal import Decimal
import polars as pl

# Initialize tracker
tracker = DecimalMetricsTracker(
    strategy_name="LiveMonitoring",
    annualization_factor=252,
)

# Simulate backtest with monitoring
class BacktestMonitor:
    def __init__(self, tracker: DecimalMetricsTracker):
        self.tracker = tracker
        self.check_interval = 20  # Check metrics every 20 days
        self.day_count = 0

    def on_bar(self, daily_return: Decimal):
        """Called every bar during backtest."""
        self.day_count += 1

        # Update tracker
        self.tracker.update(returns=pl.Series([daily_return]))

        # Periodic monitoring
        if self.day_count % self.check_interval == 0:
            metrics = self.tracker.calculate_all_metrics()

            print(f"\n=== Day {self.day_count} Metrics ===")
            print(f"Sharpe Ratio: {metrics.get('sharpe_ratio', Decimal('0')):.2f}")
            print(f"Max Drawdown: {metrics.get('max_drawdown', Decimal('0')):.2%}")

            # Risk check: halt if drawdown exceeds -20%
            if metrics.get('max_drawdown', Decimal('0')) < Decimal("-0.20"):
                print("⚠️  WARNING: Max drawdown exceeds -20%!")
                print("Consider halting strategy or reducing position size")

# Run backtest with monitoring
monitor = BacktestMonitor(tracker)

# Simulate 100 days
import random
random.seed(42)

for day in range(100):
    daily_return = Decimal(str(random.gauss(0.0005, 0.02)))
    monitor.on_bar(daily_return)

# Final metrics
print("\n=== Final Metrics ===")
summary = tracker.get_metrics_summary()
print(summary)
```

---

### Example 6: Multi-Period Performance Analysis

```python
from rustybt.finance.metrics.decimal_tracker import DecimalMetricsTracker
from decimal import Decimal
import polars as pl

# Track performance across multiple time periods
class MultiPeriodTracker:
    def __init__(self):
        self.quarterly_trackers = []
        self.current_quarter = None
        self.day_in_quarter = 0

    def start_quarter(self, quarter_name: str):
        """Start a new quarter."""
        self.current_quarter = DecimalMetricsTracker(
            strategy_name=f"Q{quarter_name}",
            annualization_factor=252,
        )
        self.quarterly_trackers.append((quarter_name, self.current_quarter))
        self.day_in_quarter = 0

    def add_daily_return(self, daily_return: Decimal):
        """Add daily return to current quarter."""
        if self.current_quarter is None:
            raise ValueError("Must call start_quarter() first")

        self.current_quarter.update(returns=pl.Series([daily_return]))
        self.day_in_quarter += 1

    def get_quarterly_summary(self) -> dict[str, dict[str, Decimal]]:
        """Get metrics for all quarters."""
        summary = {}
        for quarter_name, tracker in self.quarterly_trackers:
            metrics = tracker.calculate_all_metrics()
            summary[quarter_name] = {
                "sharpe_ratio": metrics.get("sharpe_ratio", Decimal("0")),
                "max_drawdown": metrics.get("max_drawdown", Decimal("0")),
                "annual_return": metrics.get("annual_return", Decimal("0")),
            }
        return summary

# Usage
multi_tracker = MultiPeriodTracker()

# Q1
multi_tracker.start_quarter("Q1-2024")
for _ in range(63):  # ~63 trading days in Q1
    multi_tracker.add_daily_return(Decimal(str(random.gauss(0.001, 0.015))))

# Q2
multi_tracker.start_quarter("Q2-2024")
for _ in range(63):
    multi_tracker.add_daily_return(Decimal(str(random.gauss(0.0005, 0.018))))

# Q3
multi_tracker.start_quarter("Q3-2024")
for _ in range(63):
    multi_tracker.add_daily_return(Decimal(str(random.gauss(0.0015, 0.012))))

# Compare quarters
quarterly_summary = multi_tracker.get_quarterly_summary()
for quarter, metrics in quarterly_summary.items():
    print(f"\n{quarter}:")
    print(f"  Sharpe: {metrics['sharpe_ratio']:.2f}")
    print(f"  Max DD: {metrics['max_drawdown']:.2%}")
    print(f"  Annual Return: {metrics['annual_return']:.2%}")
```

---

### Example 7: Caching and Performance Optimization

```python
from rustybt.finance.metrics.decimal_tracker import DecimalMetricsTracker
from decimal import Decimal
import polars as pl
import time

tracker = DecimalMetricsTracker(strategy_name="CacheDemo")

# Add 1000 days of returns
returns = pl.Series(
    "returns",
    [Decimal(str(random.gauss(0.0005, 0.015))) for _ in range(1000)]
)
tracker.update(returns=returns)

# First calculation (no cache)
start = time.time()
metrics1 = tracker.calculate_all_metrics()
elapsed1 = time.time() - start
print(f"First calculation: {elapsed1:.4f} seconds")

# Second calculation (cache hit)
start = time.time()
metrics2 = tracker.calculate_all_metrics()
elapsed2 = time.time() - start
print(f"Cached calculation: {elapsed2:.4f} seconds")
print(f"Speedup: {elapsed1 / elapsed2:.1f}x")

# Force recalculation (bypass cache)
start = time.time()
metrics3 = tracker.calculate_all_metrics(force_recalculate=True)
elapsed3 = time.time() - start
print(f"Forced recalculation: {elapsed3:.4f} seconds")

# Cache invalidation on update
tracker.update(returns=pl.Series([Decimal("0.01")]))

start = time.time()
metrics4 = tracker.calculate_all_metrics()  # Cache miss (invalidated by update)
elapsed4 = time.time() - start
print(f"After update (cache invalidated): {elapsed4:.4f} seconds")
```

---

### Example 8: Export Metrics to JSON for Reporting

```python
from rustybt.finance.metrics.decimal_tracker import DecimalMetricsTracker
from decimal import Decimal
import polars as pl
import json
from datetime import datetime

tracker = DecimalMetricsTracker(
    strategy_name="ProductionStrategy",
    risk_free_rate=Decimal("0.02"),
    annualization_factor=252,
)

# Add returns
returns = pl.Series("returns", [
    Decimal("0.01"), Decimal("-0.005"), Decimal("0.015"),
    Decimal("0.002"), Decimal("-0.008"), Decimal("0.012"),
])
tracker.update(returns=returns)

# Calculate metrics
metrics = tracker.calculate_all_metrics()

# Create comprehensive report
report = {
    "strategy_name": tracker.strategy_name,
    "generated_at": datetime.now().isoformat(),
    "metrics": {
        key: str(value) for key, value in metrics.items()
    },
    "summary": {
        "total_returns": len(tracker._returns),
        "cumulative_value": str(tracker._cumulative_returns[-1]),
    }
}

# Save to file
with open("strategy_metrics.json", "w") as f:
    json.dump(report, f, indent=2)

print("Report saved to strategy_metrics.json")

# Load and parse
with open("strategy_metrics.json", "r") as f:
    loaded = json.load(f)
    print(f"Sharpe Ratio: {loaded['metrics']['sharpe_ratio']}")
```

---

## Best Practices

### 1. Choose Appropriate Annualization Factor

```python
# Daily data
tracker_daily = DecimalMetricsTracker(
    strategy_name="DailyStrategy",
    annualization_factor=252,  # 252 trading days
)

# Monthly data
tracker_monthly = DecimalMetricsTracker(
    strategy_name="MonthlyStrategy",
    annualization_factor=12,  # 12 months
)

# Hourly data (crypto)
tracker_hourly = DecimalMetricsTracker(
    strategy_name="CryptoStrategy",
    annualization_factor=365 * 24,  # 8760 hours
)
```

### 2. Handle Insufficient Data Gracefully

```python
tracker = DecimalMetricsTracker(strategy_name="NewStrategy")

# Add only 1 return (insufficient for most metrics)
tracker.update(returns=pl.Series([Decimal("0.01")]))

# calculate_all_metrics() handles insufficient data
metrics = tracker.calculate_all_metrics()

# Many metrics will be missing or zero
print(f"Metrics count: {len(metrics)}")  # Will be 0 or minimal

# Wait for more data
tracker.update(returns=pl.Series([Decimal("0.005"), Decimal("0.002")]))

# Now metrics are valid
metrics = tracker.calculate_all_metrics()
print(f"Sharpe Ratio: {metrics.get('sharpe_ratio', 'N/A')}")
```

### 3. Use Benchmark Comparison for Active Strategies

```python
# Only provide benchmark if strategy aims to beat it
tracker = DecimalMetricsTracker(strategy_name="ActiveEquity")

# For index-beating strategies
strategy_returns = pl.Series("strategy", [...])
spy_returns = pl.Series("spy", [...])

tracker.update(
    returns=strategy_returns,
    benchmark_returns=spy_returns,  # Enable IR and tracking error
)

# Check if strategy beats benchmark
metrics = tracker.calculate_all_metrics()
if metrics.get("information_ratio", Decimal("0")) > Decimal("0.5"):
    print("Strategy shows strong alpha generation!")
```

### 4. Register Custom Metrics Before Updating

```python
tracker = DecimalMetricsTracker(strategy_name="Custom")

# Register custom metrics BEFORE adding data
def custom_metric(returns: pl.Series) -> Decimal:
    return Decimal(str(returns.mean()))

tracker.register_custom_metric("my_metric", custom_metric)

# Now update with data
tracker.update(returns=pl.Series([...]))

# Custom metric automatically calculated
metrics = tracker.calculate_all_metrics()
```

### 5. Reset Tracker Between Strategy Runs

```python
tracker = DecimalMetricsTracker(strategy_name="BacktestRunner")

# Run 1
for return_val in run_1_returns:
    tracker.update(returns=pl.Series([return_val]))

metrics_run1 = tracker.calculate_all_metrics()

# Reset for Run 2
tracker.reset()

# Run 2
for return_val in run_2_returns:
    tracker.update(returns=pl.Series([return_val]))

metrics_run2 = tracker.calculate_all_metrics()

# Compare runs
print(f"Run 1 Sharpe: {metrics_run1['sharpe_ratio']}")
print(f"Run 2 Sharpe: {metrics_run2['sharpe_ratio']}")
```

---

## Common Patterns

### Pattern 1: Real-Time Strategy Monitoring

```python
class StrategyWithMonitoring:
    def __init__(self):
        self.tracker = DecimalMetricsTracker(
            strategy_name="LiveStrategy",
            annualization_factor=252,
        )
        self.returns_buffer = []

    def on_trade_close(self, pnl: Decimal, position_value: Decimal):
        """Called when trade closes."""
        trade_return = pnl / position_value
        self.returns_buffer.append(trade_return)

    def end_of_day(self):
        """Called at end of day."""
        if len(self.returns_buffer) > 0:
            daily_return = sum(self.returns_buffer, Decimal("0"))
            self.tracker.update(returns=pl.Series([daily_return]))
            self.returns_buffer.clear()

    def get_current_metrics(self) -> dict[str, Decimal]:
        """Get current performance metrics."""
        return self.tracker.calculate_all_metrics()
```

### Pattern 2: Walk-Forward Validation Metrics

```python
def walk_forward_metrics(returns_by_period: list[pl.Series]) -> list[dict[str, Decimal]]:
    """Calculate metrics for each walk-forward period."""
    metrics_by_period = []

    for i, period_returns in enumerate(returns_by_period):
        tracker = DecimalMetricsTracker(
            strategy_name=f"Period_{i+1}",
            annualization_factor=252,
        )

        tracker.update(returns=period_returns)
        metrics = tracker.calculate_all_metrics()
        metrics_by_period.append(metrics)

    return metrics_by_period

# Usage
periods = [
    pl.Series("p1", [Decimal("0.01"), ...]),
    pl.Series("p2", [Decimal("0.005"), ...]),
    pl.Series("p3", [Decimal("0.012"), ...]),
]

all_metrics = walk_forward_metrics(periods)

# Check consistency across periods
sharpe_ratios = [m.get("sharpe_ratio", Decimal("0")) for m in all_metrics]
print(f"Sharpe Ratio Std Dev: {statistics.stdev([float(sr) for sr in sharpe_ratios])}")
```

---

## Error Handling

The `DecimalMetricsTracker` handles errors gracefully:

```python
tracker = DecimalMetricsTracker(strategy_name="ErrorHandling")

# Insufficient data: returns empty dict or zeros
tracker.update(returns=pl.Series([Decimal("0.01")]))  # Only 1 return
metrics = tracker.calculate_all_metrics()
# Most metrics will be 0 or missing

# Zero volatility: Sharpe ratio returns 0
tracker.update(returns=pl.Series([
    Decimal("0.01"), Decimal("0.01"), Decimal("0.01")
]))  # No variance
metrics = tracker.calculate_all_metrics()
assert metrics["sharpe_ratio"] == Decimal("0")

# Division by zero in metrics: handled internally
# See rustybt/finance/metrics/decimal_metrics.py for individual error handling
```

---

## Related Documentation

- **Risk Metrics**: Individual metric calculation functions (`calculate_sharpe_ratio`, `calculate_var`, etc.)
- **Analytics Suite**: Attribution analysis and formatting utilities
- **DecimalConfig**: Precision configuration for Decimal calculations
- **Portfolio Allocator**: Multi-strategy coordination with performance tracking

---

## Source Code References

All APIs documented above are verified against source code:

- **DecimalMetricsTracker**: `rustybt/finance/metrics/decimal_tracker.py:45-373`
  - `__init__`: Line 58-76
  - `update`: Line 95-140
  - `register_custom_metric`: Line 141-156
  - `calculate_all_metrics`: Line 158-308
  - `get_metrics_summary`: Line 309-323
  - `get_metrics_json`: Line 325-335
  - `reset`: Line 337-350
  - `get_returns_series`: Line 352-361
  - `get_cumulative_returns_series`: Line 363-373

---

**Last Verified**: 2025-10-16
**Source Version**: RustyBT v1.0 (Epic 10 Documentation)
**Verification**: 100% of APIs verified against source code
