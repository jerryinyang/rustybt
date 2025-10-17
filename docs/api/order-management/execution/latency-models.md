# Latency Simulation Models

**Version**: 2.0 (Production Grade)
**Status**: ✅ Source Code Verified
**Last Updated**: 2025-10-16
**Story**: 11.3 - Order & Portfolio Management Documentation (Production Grade Redo)

---

## Overview

RustyBT's latency simulation models provide realistic modeling of order execution delays across network transmission, broker processing, and exchange matching. These models are critical for accurate backtesting of latency-sensitive strategies and understanding real-world execution timing.

**Source**: `rustybt/finance/execution.py:453-878`

### Why Latency Matters

In live trading, orders experience multiple sources of delay:

1. **Network Latency**: Time to transmit order from client to broker (1-100ms)
2. **Broker Processing**: Time for broker to validate and route order (5-50ms)
3. **Exchange Matching**: Time for exchange to match order (1-10ms)
4. **Total Roundtrip**: Sum of all components + return path (10-200ms+)

**Real-World Impact**:
- High-frequency strategies: 1ms difference = win/loss
- Momentum strategies: 100ms delay can miss optimal entry
- Stop-loss orders: Slippage increases with execution delay

### Architecture

```python
LatencyModel (Abstract Base Class)
    ├── FixedLatencyModel           # Constant delay
    ├── RandomLatencyModel           # Uniform distribution
    ├── HistoricalLatencyModel       # Replay historical data
    └── CompositeLatencyModel        # Combine multiple models

LatencyComponents (Composite Models)
    ├── NetworkLatency               # Network transmission
    ├── BrokerProcessingLatency      # Broker validation/routing
    └── ExchangeMatchingLatency      # Exchange order matching
```

---

## Strategy Lifecycle Methods

**Important Note**: The examples in this documentation use strategy lifecycle methods that are provided by `TradingAlgorithm` and injected at runtime:

- `initialize(context)` - Strategy setup, called once at start
- `handle_data(context, data)` - Per-bar execution, called every bar
- `before_trading_start(context, data)` - Pre-market setup, called before market open

**These methods should NOT be imported**. They are automatically available in your strategy class when you inherit from `TradingAlgorithm`. The import statements in examples are shown for documentation purposes only.


---

## Table of Contents

1. [LatencyModel Base Class](#latencymodel-base-class)
2. [FixedLatencyModel](#fixedlatencymodel)
3. [RandomLatencyModel](#randomlatencymodel)
4. [HistoricalLatencyModel](#historicallatencymodel)
5. [CompositeLatencyModel](#compositelatencymodel)
6. [LatencyComponents](#latencycomponents)
   - [NetworkLatency](#networklatency)
   - [BrokerProcessingLatency](#brokerprocessinglatency)
   - [ExchangeMatchingLatency](#exchangematchinglatency)
7. [Complete Examples](#complete-examples)
8. [Best Practices](#best-practices)
9. [Related Documentation](#related-documentation)

---

## LatencyModel Base Class

**Source**: `rustybt/finance/execution.py:453-478`
**Import**: `from rustybt.finance.execution import LatencyModel`

Abstract base class for all latency simulation models.

### Abstract Methods

```python
import abc
from decimal import Decimal

class LatencyModel(metaclass=abc.ABCMeta):
    """Base class for latency simulation models."""

    @abc.abstractmethod
    def get_latency(self, order, current_time):
        """Calculate latency for an order.

        Parameters
        ----------
        order : Order
            The order being placed
        current_time : pd.Timestamp
            Current simulation time

        Returns
        -------
        latency : pd.Timedelta
            Execution delay for this order
        """
        raise NotImplementedError
```

### Key Concepts

- **Latency**: Delay between order submission and execution attempt
- **Deterministic vs Stochastic**: Fixed vs random delays
- **Order-Dependent**: Latency can vary by order properties (size, type, asset)
- **Time-Dependent**: Latency can vary by time of day, market conditions

---

## FixedLatencyModel

**Source**: `rustybt/finance/execution.py:480-520`
**Import**: `from rustybt.finance.execution import FixedLatencyModel`

Constant latency for all orders. Simplest model, useful for baseline testing.

### Constructor

```python
FixedLatencyModel(latency_ms)
```

**Parameters**:
- `latency_ms` (float): **REQUIRED**. Fixed latency in milliseconds. Must be >= 0.

**Raises**:
- `ValueError`: If `latency_ms` < 0.

### Behavior

- ✅ **Deterministic**: Same latency for every order
- ✅ **Fast**: No randomness or lookups
- ⚠️ **Unrealistic**: Real latency varies by many factors
- 📊 **Use Case**: Baseline testing, simple strategies

### When to Use

- **Simple Strategies**: Not latency-sensitive
- **Baseline Testing**: Understand average-case behavior
- **Debugging**: Eliminate randomness from testing

### When to Avoid

- ❌ High-frequency strategies (too simplified)
- ❌ Production-grade backtests (unrealistic)
- ❌ Latency-sensitive research (need realistic variance)

### Example: Basic Fixed Latency

```python
# NOTE: set_execution_engine is available via context in TradingAlgorithm
from rustybt.finance.execution import FixedLatencyModel, ExecutionEngine

def initialize(context):
    """Set constant 50ms latency for all orders."""
    latency_model = FixedLatencyModel(latency_ms=50.0)

    # Configure execution engine with latency
    engine = ExecutionEngine(
        latency_model=latency_model,
        # ... other parameters
    )
    set_execution_engine(engine)
```

### Example: Latency Impact Testing

```python
# NOTE: set_execution_engine is available via context in TradingAlgorithm
from rustybt.finance.execution import FixedLatencyModel, ExecutionEngine

def initialize(context):
    """Test strategy performance at different latency levels."""
    # Store latency setting
    context.latency_ms = 100.0  # User parameter

    latency_model = FixedLatencyModel(latency_ms=context.latency_ms)
    engine = ExecutionEngine(latency_model=latency_model)
    set_execution_engine(engine)

    context.log.info(f"Running with {context.latency_ms}ms fixed latency")

# Run multiple backtests with different latencies:
# 10ms, 50ms, 100ms, 500ms to see impact
```

---

## RandomLatencyModel

**Source**: `rustybt/finance/execution.py:522-596`
**Import**: `from rustybt.finance.execution import RandomLatencyModel`

Random latency drawn from uniform distribution. More realistic than fixed latency.

### Constructor

```python
RandomLatencyModel(min_latency_ms, max_latency_ms, seed=None)
```

**Parameters**:
- `min_latency_ms` (float): **REQUIRED**. Minimum latency in milliseconds. Must be >= 0.
- `max_latency_ms` (float): **REQUIRED**. Maximum latency in milliseconds. Must be >= min_latency_ms.
- `seed` (int, optional): Random seed for reproducibility. Default: `None` (random seed).

**Raises**:
- `ValueError`: If `min_latency_ms` < 0 or `max_latency_ms` < `min_latency_ms`.

### Behavior

- 📊 **Stochastic**: Latency varies per order
- 🎲 **Uniform Distribution**: All values equally likely in range
- 🔁 **Reproducible**: Set seed for deterministic randomness
- ⚠️ **Simple Model**: Real latency distributions are not uniform

**Statistical Properties**:
```python
mean = (min_latency_ms + max_latency_ms) / 2
std_dev = (max_latency_ms - min_latency_ms) / sqrt(12)
```

### When to Use

- **Moderate Realism**: Better than fixed, easier than historical
- **Stress Testing**: Test strategy robustness to latency variance
- **Reproducible Tests**: Use seed for consistent results

### When to Avoid

- ❌ Need realistic latency distribution (use HistoricalLatencyModel)
- ❌ Time-of-day effects matter (use HistoricalLatencyModel)
- ❌ Asset-specific latency (need custom model)

### Example: Basic Random Latency

```python
# NOTE: set_execution_engine is available via context in TradingAlgorithm
from rustybt.finance.execution import RandomLatencyModel, ExecutionEngine

def initialize(context):
    """Set random latency between 10-100ms."""
    latency_model = RandomLatencyModel(
        min_latency_ms=10.0,
        max_latency_ms=100.0,
        seed=42  # Reproducible
    )

    engine = ExecutionEngine(latency_model=latency_model)
    set_execution_engine(engine)
```

### Example: Market Hours Latency Variation

```python
# NOTE: set_execution_engine is available via context in TradingAlgorithm
from rustybt.finance.execution import RandomLatencyModel, ExecutionEngine

def initialize(context):
    """Model higher latency during market open/close."""
    # Simple approximation: wider range during volatile periods
    latency_model = RandomLatencyModel(
        min_latency_ms=20.0,   # Best case
        max_latency_ms=200.0,  # Worst case (market open/close)
        seed=context.get_parameter('random_seed', 42)
    )

    engine = ExecutionEngine(latency_model=latency_model)
    set_execution_engine(engine)

def handle_data(context, data):
    """Log latency statistics."""
    current_time = context.get_datetime()

    # Market open/close periods (simplified)
    is_open = current_time.time() < pd.Timestamp('09:45').time()
    is_close = current_time.time() > pd.Timestamp('15:45').time()

    if is_open or is_close:
        context.log.info("Volatile period: expect higher latency")
```

### Example: Monte Carlo Latency Testing

```python
# NOTE: set_execution_engine is available via context in TradingAlgorithm
from rustybt.finance.execution import RandomLatencyModel, ExecutionEngine
import numpy as np

def initialize(context):
    """Test strategy across latency distribution."""
    context.latency_samples = []

    latency_model = RandomLatencyModel(
        min_latency_ms=10.0,
        max_latency_ms=150.0,
        seed=None  # Different each run
    )

    engine = ExecutionEngine(latency_model=latency_model)
    set_execution_engine(engine)

def analyze(context, results):
    """Analyze latency impact on performance."""
    if context.latency_samples:
        latencies = np.array(context.latency_samples)

        context.log.info(f"Latency Statistics:")
        context.log.info(f"  Mean: {latencies.mean():.1f}ms")
        context.log.info(f"  Median: {np.median(latencies):.1f}ms")
        context.log.info(f"  Std Dev: {latencies.std():.1f}ms")
        context.log.info(f"  P95: {np.percentile(latencies, 95):.1f}ms")
        context.log.info(f"  P99: {np.percentile(latencies, 99):.1f}ms")
```

---

## HistoricalLatencyModel

**Source**: `rustybt/finance/execution.py:598-652`
**Import**: `from rustybt.finance.execution import HistoricalLatencyModel`

Replay historical latency measurements. Most realistic model, requires latency data.

### Constructor

```python
HistoricalLatencyModel(latency_data, interpolate=True)
```

**Parameters**:
- `latency_data` (pd.DataFrame): **REQUIRED**. Historical latency measurements with DatetimeIndex and 'latency_ms' column.
- `interpolate` (bool, optional): Interpolate between measurements. Default: `True`.

**Raises**:
- `ValueError`: If `latency_data` missing required columns or invalid format.

**DataFrame Schema**:
```python
# Required columns:
# - index: pd.DatetimeIndex (measurement timestamps)
# - 'latency_ms': float (latency in milliseconds)

# Optional columns:
# - 'asset': Asset (asset-specific latency)
# - 'order_type': str (order-type-specific latency)
```

### Behavior

- ✅ **Most Realistic**: Uses actual latency measurements
- 📊 **Time-Dependent**: Captures time-of-day patterns
- 🔄 **Interpolation**: Smooth latency between measurements (optional)
- ⚠️ **Data Required**: Needs historical latency data

### When to Use

- **Production-Grade Backtests**: Highest realism
- **Latency-Sensitive Strategies**: HFT, market making
- **Live Trading Preparation**: Match production environment

### When to Avoid

- ❌ No historical data available (use RandomLatencyModel)
- ❌ Quick prototyping (simpler models faster)
- ❌ Generic strategies (fixed/random sufficient)

### Example: Basic Historical Latency

```python
# NOTE: set_execution_engine is available via context in TradingAlgorithm
from rustybt.finance.execution import HistoricalLatencyModel, ExecutionEngine
import pandas as pd

def initialize(context):
    """Load and use historical latency data."""
    # Load historical latency measurements
    latency_data = pd.read_csv(
        'data/historical_latency.csv',
        index_col='timestamp',
        parse_dates=True
    )
    # Expected columns: timestamp (index), latency_ms

    latency_model = HistoricalLatencyModel(
        latency_data=latency_data,
        interpolate=True  # Smooth between measurements
    )

    engine = ExecutionEngine(latency_model=latency_model)
    set_execution_engine(engine)
```

### Example: Asset-Specific Latency

```python
# NOTE: set_execution_engine is available via context in TradingAlgorithm
from rustybt.finance.execution import HistoricalLatencyModel, ExecutionEngine
import pandas as pd

def initialize(context):
    """Use asset-specific historical latency."""
    # Load latency data with asset column
    latency_data = pd.read_csv(
        'data/latency_by_asset.csv',
        index_col='timestamp',
        parse_dates=True
    )
    # Columns: timestamp (index), latency_ms, asset

    latency_model = HistoricalLatencyModel(
        latency_data=latency_data,
        interpolate=True
    )

    engine = ExecutionEngine(latency_model=latency_model)
    set_execution_engine(engine)

    context.log.info(
        f"Loaded {len(latency_data)} latency measurements "
        f"for {latency_data['asset'].nunique()} assets"
    )
```

### Example: Creating Latency Data from Live Trading

```python
import pandas as pd
from datetime import datetime

class LatencyRecorder:
    """Record latency measurements during live trading."""

    def __init__(self):
        self.measurements = []

    def record_order(self, order_time, execution_time, asset, order_type):
        """Record order latency measurement."""
        latency_ms = (execution_time - order_time).total_seconds() * 1000

        self.measurements.append({
            'timestamp': order_time,
            'latency_ms': latency_ms,
            'asset': asset,
            'order_type': order_type
        })

    def save(self, filename):
        """Save measurements to CSV."""
        df = pd.DataFrame(self.measurements)
        df.set_index('timestamp', inplace=True)
        df.to_csv(filename)

        print(f"Saved {len(df)} latency measurements to {filename}")
        print(f"  Mean latency: {df['latency_ms'].mean():.1f}ms")
        print(f"  P95 latency: {df['latency_ms'].quantile(0.95):.1f}ms")

# Usage in live trading:
recorder = LatencyRecorder()

def on_order_submitted(order, submit_time):
    context.order_submit_times[order.id] = submit_time

def on_order_executed(order, exec_time):
    submit_time = context.order_submit_times.get(order.id)
    if submit_time:
        recorder.record_order(submit_time, exec_time, order.asset, order.order_type)

# At end of trading day:
recorder.save('data/latency_2025-10-16.csv')
```

---

## CompositeLatencyModel

**Source**: `rustybt/finance/execution.py:654-703`
**Import**: `from rustybt.finance.execution import CompositeLatencyModel`

Combine multiple latency models into a single model. Sum of component latencies.

### Constructor

```python
CompositeLatencyModel(*models)
```

**Parameters**:
- `*models` (LatencyModel): **REQUIRED**. Variable number of LatencyModel instances to combine.

**Raises**:
- `ValueError`: If no models provided or any model not LatencyModel instance.

### Behavior

- 🔗 **Additive**: Total latency = sum of all component latencies
- 🧩 **Modular**: Mix different model types
- 📊 **Realistic**: Model independent latency sources
- ✅ **Flexible**: Easy to add/remove components

**Total Latency**:
```python
total_latency = sum(model.get_latency(order, time) for model in models)
```

### When to Use

- **Decompose Latency**: Model network, broker, exchange separately
- **Mix Models**: Combine fixed + random + historical
- **Realistic Testing**: Sum of independent delay sources

### When to Avoid

- ❌ Components not independent (use custom model)
- ❌ Simple strategies (single model sufficient)

### Example: Network + Broker + Exchange

```python
# NOTE: set_execution_engine is available via context in TradingAlgorithm
from rustybt.finance.execution import (
    CompositeLatencyModel, FixedLatencyModel, RandomLatencyModel,
    ExecutionEngine
)

def initialize(context):
    """Model latency as sum of components."""
    # Network: fixed 20ms baseline
    network = FixedLatencyModel(latency_ms=20.0)

    # Broker: random 5-30ms processing
    broker = RandomLatencyModel(min_latency_ms=5.0, max_latency_ms=30.0)

    # Exchange: random 1-10ms matching
    exchange = RandomLatencyModel(min_latency_ms=1.0, max_latency_ms=10.0)

    # Total latency: 26-60ms (20 + [5-30] + [1-10])
    latency_model = CompositeLatencyModel(network, broker, exchange)

    engine = ExecutionEngine(latency_model=latency_model)
    set_execution_engine(engine)

    context.log.info("Using composite latency model:")
    context.log.info("  Network: 20ms (fixed)")
    context.log.info("  Broker: 5-30ms (random)")
    context.log.info("  Exchange: 1-10ms (random)")
    context.log.info("  Total: 26-60ms")
```

---

## LatencyComponents

**Source**: `rustybt/finance/execution.py:437-451`

Helper class for accessing pre-built latency component models.

### Available Components

| Component | Description | Typical Range | Source Line |
|-----------|-------------|---------------|-------------|
| `NetworkLatency` | Network transmission delay | 1-100ms | 705-752 |
| `BrokerProcessingLatency` | Broker validation/routing | 5-50ms | 754-814 |
| `ExchangeMatchingLatency` | Exchange order matching | 1-10ms | 816-878 |

---

### NetworkLatency

**Source**: `rustybt/finance/execution.py:705-752`
**Import**: `from rustybt.finance.execution import NetworkLatency`

Models network transmission latency from client to broker.

#### Constructor

```python
NetworkLatency(baseline_ms, jitter_ms=0, distance_factor=1.0)
```

**Parameters**:
- `baseline_ms` (float): **REQUIRED**. Baseline network latency in milliseconds. Must be >= 0.
- `jitter_ms` (float, optional): Random jitter range (+/-). Default: `0` (no jitter).
- `distance_factor` (float, optional): Multiplier for geographic distance. Default: `1.0`.

**Raises**:
- `ValueError`: If `baseline_ms` < 0 or `jitter_ms` < 0.

#### Behavior

```python
latency = baseline_ms * distance_factor + random.uniform(-jitter_ms, jitter_ms)
```

- 📡 **Round-Trip**: Includes send + receive time
- 🌍 **Geographic**: distance_factor models physical distance
- 📊 **Jitter**: Random variance around baseline
- ⚡ **Speed of Light**: Limited by physics (~5ms per 1000km)

#### Example: Colocated vs Remote

```python
from rustybt.finance.execution import NetworkLatency, CompositeLatencyModel

# Colocated server (same datacenter)
colocated = NetworkLatency(
    baseline_ms=1.0,      # Sub-millisecond ping
    jitter_ms=0.5,        # Minimal jitter
    distance_factor=1.0   # No distance penalty
)

# Remote server (cross-country)
remote = NetworkLatency(
    baseline_ms=30.0,     # 30ms baseline (US East to West)
    jitter_ms=10.0,       # Higher jitter over long distance
    distance_factor=1.5   # Distance penalty
)
# Effective latency: 30 * 1.5 +/- 10 = 35-55ms
```

---

### BrokerProcessingLatency

**Source**: `rustybt/finance/execution.py:754-814`
**Import**: `from rustybt.finance.execution import BrokerProcessingLatency`

Models broker order validation, risk checks, and routing.

#### Constructor

```python
BrokerProcessingLatency(
    min_processing_ms,
    max_processing_ms,
    complex_order_multiplier=2.0
)
```

**Parameters**:
- `min_processing_ms` (float): **REQUIRED**. Minimum processing time in milliseconds. Must be >= 0.
- `max_processing_ms` (float): **REQUIRED**. Maximum processing time in milliseconds. Must be >= min_processing_ms.
- `complex_order_multiplier` (float, optional): Multiplier for complex orders. Default: `2.0`.

**Raises**:
- `ValueError`: If ranges invalid or multiplier < 1.0.

#### Behavior

```python
base_latency = random.uniform(min_processing_ms, max_processing_ms)

# Complex orders take longer
if is_complex_order(order):
    latency = base_latency * complex_order_multiplier
else:
    latency = base_latency
```

**Complex Orders**:
- Stop-limit orders
- OCO (One-Cancels-Other)
- Bracket orders
- Orders with special instructions

#### Example: Retail vs Professional Broker

```python
from rustybt.finance.execution import BrokerProcessingLatency

# Retail broker (slower processing, more checks)
retail_broker = BrokerProcessingLatency(
    min_processing_ms=10.0,
    max_processing_ms=50.0,
    complex_order_multiplier=3.0  # Complex orders much slower
)

# Professional/DMA broker (faster, direct market access)
pro_broker = BrokerProcessingLatency(
    min_processing_ms=2.0,
    max_processing_ms=10.0,
    complex_order_multiplier=1.5  # Less overhead
)
```

---

### ExchangeMatchingLatency

**Source**: `rustybt/finance/execution.py:816-878`
**Import**: `from rustybt.finance.execution import ExchangeMatchingLatency`

Models exchange order book matching engine latency.

#### Constructor

```python
ExchangeMatchingLatency(
    base_latency_ms,
    volume_factor=0.0,
    volatility_factor=0.0
)
```

**Parameters**:
- `base_latency_ms` (float): **REQUIRED**. Base matching latency in milliseconds. Must be >= 0.
- `volume_factor` (float, optional): Latency increase per volume unit. Default: `0.0` (no volume effect).
- `volatility_factor` (float, optional): Latency increase during volatility. Default: `0.0` (no volatility effect).

**Raises**:
- `ValueError`: If `base_latency_ms` < 0 or factors < 0.

#### Behavior

```python
latency = base_latency_ms
latency += volume_factor * (current_volume / avg_volume)
latency += volatility_factor * (current_volatility / avg_volatility)
```

- 📊 **Volume-Dependent**: Higher volume = more messages = longer latency
- 📈 **Volatility-Dependent**: Volatile markets = more order flow = longer latency
- ⚡ **Modern Exchanges**: ~1-10ms matching latency

#### Example: NYSE vs NASDAQ

```python
from rustybt.finance.execution import ExchangeMatchingLatency

# NYSE (hybrid market, slightly slower)
nyse = ExchangeMatchingLatency(
    base_latency_ms=5.0,
    volume_factor=0.002,       # Small volume effect
    volatility_factor=0.005    # Volatility slows matching
)

# NASDAQ (pure electronic, faster)
nasdaq = ExchangeMatchingLatency(
    base_latency_ms=2.0,
    volume_factor=0.001,       # Minimal volume effect
    volatility_factor=0.003    # Better handling of volatility
)
```

---

## Complete Examples

### Example 1: Production-Grade Latency Model

```python
# NOTE: initialize() and set_execution_engine() are available in TradingAlgorithm context
from rustybt.finance.execution import (
    CompositeLatencyModel, NetworkLatency,
    BrokerProcessingLatency, ExchangeMatchingLatency,
    ExecutionEngine
)

def initialize(context):
    """Set up realistic multi-component latency model."""
    # Network latency: colocated server
    network = NetworkLatency(
        baseline_ms=2.0,      # 2ms ping
        jitter_ms=1.0,        # +/- 1ms jitter
        distance_factor=1.0   # Same datacenter
    )

    # Broker latency: professional DMA broker
    broker = BrokerProcessingLatency(
        min_processing_ms=3.0,
        max_processing_ms=15.0,
        complex_order_multiplier=2.0
    )

    # Exchange latency: NASDAQ
    exchange = ExchangeMatchingLatency(
        base_latency_ms=2.0,
        volume_factor=0.001,
        volatility_factor=0.003
    )

    # Composite model
    latency_model = CompositeLatencyModel(network, broker, exchange)

    # Configure execution engine
    engine = ExecutionEngine(
        latency_model=latency_model,
        # ... other parameters
    )
    set_execution_engine(engine)

    context.log.info("Production latency model configured:")
    context.log.info("  Network: 1-4ms (colocated)")
    context.log.info("  Broker: 3-15ms (DMA)")
    context.log.info("  Exchange: 2-10ms (NASDAQ)")
    context.log.info("  Expected total: 6-29ms")
```

### Example 2: Latency Sensitivity Analysis

```python
# NOTE: initialize() and set_execution_engine() are available in TradingAlgorithm context
from rustybt.finance.execution import FixedLatencyModel, ExecutionEngine
import pandas as pd

def run_latency_sweep(strategy_class, latency_levels):
    """Test strategy at multiple latency levels."""
    results = []

    for latency_ms in latency_levels:
        # Create strategy instance
        strategy = strategy_class()

        # Configure latency
        latency_model = FixedLatencyModel(latency_ms=latency_ms)
        engine = ExecutionEngine(latency_model=latency_model)
        set_execution_engine(engine)

        # Run backtest
        result = run_algorithm(
            strategy=strategy,
            start='2024-01-01',
            end='2024-12-31',
            capital_base=100000
        )

        results.append({
            'latency_ms': latency_ms,
            'total_return': result.total_return,
            'sharpe_ratio': result.sharpe_ratio,
            'max_drawdown': result.max_drawdown
        })

    # Analyze results
    df = pd.DataFrame(results)
    print("\nLatency Sensitivity Analysis:")
    print(df.to_string(index=False))

    # Plot results
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    df.plot(x='latency_ms', y='total_return', ax=axes[0], title='Total Return vs Latency')
    df.plot(x='latency_ms', y='sharpe_ratio', ax=axes[1], title='Sharpe Ratio vs Latency')
    df.plot(x='latency_ms', y='max_drawdown', ax=axes[2], title='Max Drawdown vs Latency')

    plt.tight_layout()
    plt.savefig('latency_sensitivity.png')
    print("\nPlot saved to latency_sensitivity.png")

    return df

# Usage:
latency_levels = [0, 10, 25, 50, 100, 200, 500]  # milliseconds
results = run_latency_sweep(MyStrategy, latency_levels)
```

### Example 3: Adaptive Latency Based on Market Conditions

```python
# NOTE: initialize(), handle_data(), and set_execution_engine() are available in TradingAlgorithm context
from rustybt.finance.execution import RandomLatencyModel, ExecutionEngine

class AdaptiveLatencyModel:
    """Adjust latency based on market conditions."""

    def __init__(self, base_min, base_max):
        self.base_min = base_min
        self.base_max = base_max
        self.current_model = RandomLatencyModel(base_min, base_max)

    def update(self, volatility, volume):
        """Update latency model based on market conditions."""
        # Higher volatility = higher latency
        vol_multiplier = 1.0 + (volatility / 0.02)  # 2% vol = 2x latency

        # Higher volume = slightly higher latency
        vol_factor = 1.0 + (volume / 1000000) * 0.1  # Per million shares

        # Combined multiplier
        multiplier = vol_multiplier * vol_factor

        new_min = self.base_min * multiplier
        new_max = self.base_max * multiplier

        self.current_model = RandomLatencyModel(new_min, new_max)

        return new_min, new_max

    def get_latency(self, order, current_time):
        """Get latency from current model."""
        return self.current_model.get_latency(order, current_time)

def initialize(context):
    """Initialize adaptive latency model."""
    context.latency_model = AdaptiveLatencyModel(
        base_min=10.0,
        base_max=50.0
    )

    context.volatility_window = 20

def handle_data(context, data):
    """Update latency model based on market conditions."""
    asset = symbol('SPY')

    # Calculate recent volatility
    prices = data.history(asset, 'close', context.volatility_window, '1d')
    returns = prices.pct_change().dropna()
    volatility = returns.std()

    # Get current volume
    volume = data.current(asset, 'volume')

    # Update latency model
    new_min, new_max = context.latency_model.update(volatility, volume)

    context.log.info(
        f"Updated latency model: {new_min:.1f}-{new_max:.1f}ms "
        f"(vol={volatility:.2%}, volume={volume:,.0f})"
    )
```

---

## Best Practices

### ✅ DO

1. **Match Production Environment**
   ```python
   # Measure live latency, then model it
   latency_model = HistoricalLatencyModel(live_measurements)
   ```

2. **Test Latency Sensitivity**
   ```python
   # Run strategy at multiple latency levels
   for latency in [10, 50, 100, 200]:
       test_strategy(FixedLatencyModel(latency))
   ```

3. **Use Composite Models for Realism**
   ```python
   # Model independent latency sources
   latency = CompositeLatencyModel(network, broker, exchange)
   ```

4. **Consider Asset Differences**
   ```python
   # Liquid stocks faster than illiquid
   if asset.volume > 1000000:
       latency = FixedLatencyModel(10)  # Fast
   else:
       latency = RandomLatencyModel(50, 200)  # Slow
   ```

5. **Document Latency Assumptions**
   ```python
   # Clear documentation in strategy
   """
   Latency Assumptions:
   - Network: 2ms (colocated)
   - Broker: 5-15ms (DMA)
   - Exchange: 2-5ms (NASDAQ)
   - Total: ~9-22ms
   """
   ```

### ❌ DON'T

1. **Don't Ignore Latency in HFT Strategies**
   ```python
   # BAD: No latency model
   strategy = HighFrequencyStrategy()  # Unrealistic!

   # GOOD: Model realistic latency
   strategy = HighFrequencyStrategy(latency_model=NetworkLatency(1.0))
   ```

2. **Don't Use Unrealistic Latency**
   ```python
   # BAD: 0ms latency (impossible)
   latency = FixedLatencyModel(0)

   # GOOD: Minimum realistic latency
   latency = FixedLatencyModel(5.0)  # At least 5ms
   ```

3. **Don't Assume Constant Latency**
   ```python
   # BAD: Fixed latency for all market conditions
   latency = FixedLatencyModel(50)

   # GOOD: Latency varies with conditions
   latency = RandomLatencyModel(30, 100)  # Or HistoricalLatencyModel
   ```

4. **Don't Forget Round-Trip Time**
   ```python
   # BAD: Only model one-way latency
   latency = FixedLatencyModel(10)  # Order submission only

   # GOOD: Model full round-trip
   latency = FixedLatencyModel(20)  # Submit + confirmation
   ```

5. **Don't Mix Incompatible Time Scales**
   ```python
   # BAD: 1ms latency with daily bars
   latency = FixedLatencyModel(1)  # Irrelevant at daily scale!

   # GOOD: Match latency to bar resolution
   # Minute bars -> 10-100ms latency relevant
   # Daily bars -> latency largely irrelevant
   ```

---

## Related Documentation

### Order Management
- [Order Types](../order-types.md) - All supported order execution styles
- [Blotter Architecture](blotter.md) - Order routing and management system

### Execution Systems
- [Partial Fill Models](partial-fills.md) - Realistic order fill simulation

### Transaction Costs
- [Slippage Models](../transaction-costs/slippage.md) - Price impact modeling
- [Commission Models](../transaction-costs/commissions.md) - Broker fee calculation

---

## Next Steps

1. **Learn Partial Fills**: Understand realistic order fill behavior → [Partial Fill Models](partial-fills.md)
3. **Model Transaction Costs**: Add realistic slippage and commissions → [Slippage Models](../transaction-costs/slippage.md)
4. **Study Order Lifecycle**: See how latency affects order states → [Order Lifecycle](../workflows/order-lifecycle.md)

---

**Document Status**: ✅ Production Grade - All APIs Verified Against Source Code
**Last Verification**: 2025-10-16
**Verification Method**: Direct source code inspection of `rustybt/finance/execution.py`
**Story**: 11.3 - Order & Portfolio Management Documentation (Production Grade Redo)
