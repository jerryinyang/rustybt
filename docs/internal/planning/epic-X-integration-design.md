# Epic X Integration Design Document

**Date:** 2025-11-29
**Author:** Dev Agent (Story X.1)
**Status:** Final
**Story Reference:** X-1-analyze-rustybt-engine-integration-points

---

## Executive Summary

This document details the integration design for connecting the validation framework to rustybt's real backtesting engine. The analysis examined TradingAlgorithm lifecycle, DataPortal/DataBundle infrastructure, broker simulation (Blotter), and pipeline-based indicators. The recommended approach uses a **function-based integration pattern** that maximizes compatibility while preserving the validation logging infrastructure.

---

## 1. TradingAlgorithm Architecture Analysis

### 1.1 Lifecycle Methods

rustybt's `TradingAlgorithm` (defined in `rustybt/algorithm.py`) supports two strategy formats:

**Functional Format:**
```python
def initialize(context):
    context.asset = symbol('AAPL')

def handle_data(context, data):
    order(context.asset, 10)
```

**Class-Based Format:**
```python
class MyStrategy(TradingAlgorithm):
    def initialize(self, context):
        context.asset = self.symbol('AAPL')

    def handle_data(self, context, data):
        self.order(context.asset, 10)
```

### 1.2 Key Lifecycle Hooks

| Method | Signature | Description |
|--------|-----------|-------------|
| `initialize(context)` | Called once at start | Setup strategy state, attach pipelines |
| `before_trading_start(context, data)` | Called before each trading day | Pre-market preparation, pipeline outputs |
| `handle_data(context, data)` | Called per bar (minute/daily) | Main trading logic |
| `analyze(context, perf)` | Called once at end | Post-backtest analysis |

### 1.3 Context Object

The `context` parameter IS the TradingAlgorithm instance itself. Key attributes:
- `context.portfolio` - Portfolio object with positions, cash, portfolio_value
- `context.account` - Account object with leverage, buying power
- `context.blotter` - Access to order management
- `context.datetime` - Current simulation datetime (via `get_datetime()`)

### 1.4 Extensibility Points

1. **Lifecycle Method Override** - Can override initialize/handle_data in subclass
2. **schedule_function()** - Register callbacks for specific dates/times
3. **@api_method decorator** - Methods exposed to API namespace
4. **No Event Hooks** - rustybt does NOT have a generic event subscription system

---

## 2. Data Infrastructure Analysis

### 2.1 Data Loading Architecture

rustybt uses a layered data access architecture:

```
DataBundle (registered ingest function)
    → BundleData (readers created by load())
        → DataPortal (coordinates readers for simulation)
            → BarData (algorithm's data interface)
```

### 2.2 DataBundle Registration

Bundles are registered via `rustybt.data.bundles.register()`:

```python
from rustybt.data.bundles import register

@register('validation-fixture', calendar_name='XNYS')
def ingest_validation_data(environ, asset_db_writer, minute_bar_writer,
                           daily_bar_writer, adjustment_writer, calendar,
                           start_session, end_session, cache, show_progress,
                           output_dir):
    # Write OHLCV data using writers
    daily_bar_writer.write(ohlcv_generator())
    asset_db_writer.write(equities=asset_metadata)
```

### 2.3 Parquet Bundle Support

rustybt supports modern Parquet bundles (detected via `BundleMetadata`):
- Uses `ParquetDailyBarReader` / `ParquetMinuteBarReader`
- Uses `ParquetAssetFinder` for asset metadata
- Stored in `~/.zipline/bundles/{bundle_name}/`

### 2.4 Data Access During Backtest (Q2 Answer)

The `data` parameter in `handle_data(context, data)` provides:

```python
# Current bar price
current_price = data.current(asset, 'close')

# Historical data (returns pandas DataFrame/Series)
prices = data.history(asset, 'close', bar_count=20, frequency='1d')

# Multiple assets
closes = data.history([asset1, asset2], 'close', 20, '1d')

# Multiple fields
ohlc = data.history(asset, ['open', 'high', 'low', 'close'], 20, '1d')

# Check if asset is tradeable
can_trade = data.can_trade(asset)
```

### 2.5 Recommended Data Integration Approach

**Option A: Custom Bundle Registration (Recommended)**
- Register validation fixture as a named bundle
- Use `ingest-unified` or custom ingest function
- Pros: Full rustybt compatibility, proper trading calendar handling
- Cons: Requires one-time bundle registration per fixture

**Option B: Direct DataPortal Initialization**
- Bypass bundle system, create DataPortal with custom readers
- Pros: More flexible, no registration needed
- Cons: More complex, must handle calendar/timestamps manually

**Recommendation:** Use **Option A** with custom bundle registration. Create a helper function `register_validation_bundle(parquet_path, bundle_name)` that:
1. Reads Parquet fixture
2. Registers as a rustybt bundle
3. Handles asset metadata generation

---

## 3. Broker Infrastructure Analysis

### 3.1 Order Execution Architecture

```
TradingAlgorithm.order()
    → SimulationBlotter.order()
        → SlippageModel.process_order()
        → CommissionModel.calculate()
            → Transaction created
                → MetricsTracker.process_transaction()
```

### 3.2 Order API Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `order(asset, amount, ...)` | Place fixed-share order | Returns order_id |
| `order_value(asset, value, ...)` | Order by dollar value | |
| `order_target(asset, target, ...)` | Order to target shares | |
| `order_target_percent(asset, percent, ...)` | Order to % of portfolio | |
| `order_percent(asset, percent, ...)` | Order % of current value | |

All order methods accept optional `limit_price`, `stop_price`, and `style` parameters.

### 3.3 Order Execution Styles

```python
from rustybt.finance.execution import MarketOrder, LimitOrder, StopOrder, StopLimitOrder

order(asset, 100, style=MarketOrder())
order(asset, 100, style=LimitOrder(150.00))
order(asset, 100, style=StopOrder(145.00))
order(asset, 100, style=StopLimitOrder(145.00, 150.00))
```

### 3.4 Transaction Event Capture (Q4 Answer)

rustybt does NOT have event hooks for broker transactions. However, transactions are captured via:

1. **SimulationBlotter.get_transactions()** - Returns (transactions, commissions, closed_orders)
2. **TradingAlgorithm.perf_tracker** - Tracks all transactions
3. **Post-execution result** - `run_algorithm()` returns DataFrame with transactions

**Recommended Approach:** Use **method wrapping** to inject logging:

```python
# Wrap order methods to log order_created
original_order = context.order
def logged_order(asset, amount, *args, **kwargs):
    order_id = original_order(asset, amount, *args, **kwargs)
    self._log_event("orders", "order_created", {...})
    return order_id

# Capture transactions from blotter after each bar
transactions, commissions, _ = context.blotter.get_transactions(data)
for txn in transactions:
    self._log_event("broker", "transaction_executed", {...})
```

### 3.5 Trailing Stop Support (Q5 Answer)

rustybt's built-in order types:
- `MarketOrder` - Immediate market execution
- `LimitOrder(limit_price)` - Execute at limit price or better
- `StopOrder(stop_price)` - Trigger market order when stop hit
- `StopLimitOrder(stop_price, limit_price)` - Trigger limit order when stop hit

**Trailing Stop:** NOT natively supported. Must be implemented manually:
```python
def handle_data(context, data):
    # Track highest price since entry
    if context.trailing_stop_active:
        current_price = data.current(asset, 'close')
        context.highest_price = max(context.highest_price, current_price)
        stop_price = context.highest_price * (1 - context.trail_percent)
        if current_price <= stop_price:
            order_target(asset, 0)  # Exit position
```

---

## 4. Indicator Infrastructure Analysis

### 4.1 Pipeline Factors (Q3 Answer)

rustybt provides technical indicators via the Pipeline system in `rustybt/pipeline/factors/`:

| Indicator | Class | Location |
|-----------|-------|----------|
| Simple Moving Average | `SimpleMovingAverage` | `factors/basic.py` |
| Exponential Moving Average | `ExponentialWeightedMovingAverage` (EWMA) | `factors/basic.py` |
| RSI | `RSI` | `factors/technical.py` |
| MACD | `MovingAverageConvergenceDivergenceSignal` | `factors/technical.py` |
| Bollinger Bands | `BollingerBands` | `factors/technical.py` |
| Standard Deviation | `nanstd` (numpy util) | `utils/math_utils.py` |

### 4.2 Pipeline Usage

Pipeline factors are designed for cross-sectional analysis, not per-bar computation:

```python
from rustybt.pipeline import Pipeline
from rustybt.pipeline.factors import SimpleMovingAverage, RSI

def make_pipeline():
    sma_20 = SimpleMovingAverage(inputs=[EquityPricing.close], window_length=20)
    rsi_14 = RSI()
    return Pipeline(columns={'sma': sma_20, 'rsi': rsi_14})

def initialize(context):
    attach_pipeline(make_pipeline(), 'my_pipe')

def before_trading_start(context, data):
    context.output = pipeline_output('my_pipe')
    # context.output is a DataFrame with sma, rsi columns per asset
```

### 4.3 Per-Bar Indicator Computation

For validation strategies, we need per-bar indicator values. Options:

**Option A: Use data.history() + manual calculation**
```python
def handle_data(context, data):
    prices = data.history(asset, 'close', 20, '1d')
    sma_20 = prices.mean()
    std_20 = prices.std()
```

**Option B: Use talib (if available)**
```python
import talib
prices = data.history(asset, 'close', 50, '1d')
sma = talib.SMA(prices.values, timeperiod=20)[-1]
rsi = talib.RSI(prices.values, timeperiod=14)[-1]
```

**Recommendation:** Use **Option A** (data.history() + manual calculation) for:
- Maximum compatibility (no extra dependencies)
- Exact match with Backtrader's indicator implementations
- Clear, auditable calculations for validation

---

## 5. Integration Pattern Decision (Q1 Answer)

### 5.1 Options Evaluated

| Pattern | Description | Pros | Cons |
|---------|-------------|------|------|
| **Inheritance** | `ValidatedStrategy(TradingAlgorithm)` | Clean OOP | Complex initialization |
| **Composition** | Wrap TradingAlgorithm instance | Flexible | Extra indirection |
| **Function-based** | Standalone functions + mixin | Simple, matches rustybt examples | Less encapsulation |

### 5.2 Recommended Pattern: Function-Based with Mixin

```python
from pathlib import Path
from rustybt.validation.base_strategy import ValidatedStrategyMixin
from rustybt.utils.run_algo import run_algorithm
from rustybt.api import order, order_target, symbol

class ValidationContext(ValidatedStrategyMixin):
    """Context object that holds strategy state and provides logging."""

    def __init__(self, log_path: Path):
        self._init_logging(log_path)
        self.asset = None

def initialize(context):
    """Standard rustybt initialize function."""
    context.asset = symbol('TEST')
    context._log_event("data", "initialize", {...})

def handle_data(context, data):
    """Standard rustybt handle_data function."""
    timestamp = context.get_datetime().isoformat()
    context._log_event("data", "bar_received", {...}, simulation_timestamp=timestamp)

    # Get indicator values
    prices = data.history(context.asset, 'close', 20, '1d')
    sma_20 = prices.mean()
    context.log_signal("sma_20", sma_20, asset=str(context.asset))

    # Trading logic
    if should_buy:
        order_target(context.asset, 100)
        context.log_order_created("market", str(context.asset), 100)

# Execute backtest
def run_validation_backtest(
    strategy_module,
    bundle_name: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    log_path: Path,
    capital_base: float = 100000,
):
    """Run a validated rustybt backtest."""
    result = run_algorithm(
        start=start,
        end=end,
        initialize=strategy_module.initialize,
        handle_data=strategy_module.handle_data,
        capital_base=capital_base,
        bundle=bundle_name,
        benchmark_returns=None,  # No benchmark needed
    )
    return result
```

### 5.3 Key Integration Points for Logging

| Layer | Event | Integration Point |
|-------|-------|-------------------|
| Layer 1 (Data) | `initialize` | Beginning of `initialize()` |
| Layer 1 (Data) | `bar_received` | Beginning of `handle_data()` |
| Layer 2 (Signals) | `signal_computed` | After each indicator calculation |
| Layer 3 (Orders) | `order_created` | After each order() call |
| Layer 4 (Broker) | `transaction_executed` | After blotter.get_transactions() |
| Layer 4 (Broker) | `commission_charged` | From commission in transaction |
| Layer 4 (Broker) | `cash_updated` | From context.portfolio.cash |
| Layer 5 (Portfolio) | `portfolio_value_updated` | From context.portfolio.portfolio_value |
| Layer 5 (Portfolio) | `final_metrics` | In analyze() or after run_algorithm() |

---

## 6. Implementation Roadmap

### 6.1 Story X.2: Shared Data Fixture Infrastructure

1. Create `register_validation_bundle(fixture_path, bundle_name)` helper
2. Generate asset metadata from Parquet fixture
3. Ensure both frameworks see identical bars
4. Add fixture verification tests

### 6.2 Story X.3: Reimplement ValidatedStrategy Base Class

1. Remove homebrew simulation code:
   - `SimulatedPosition`
   - `_cash`, `_positions`, `_portfolio_values`
   - `_execute_order()`, `_update_portfolio_value()`
   - `_calculate_sharpe_ratio()`

2. Keep `ValidatedStrategyMixin` logging infrastructure:
   - `_init_logging()`, `_log_event()`
   - `log_signal()`, `log_order_created()`, `log_broker_event()`
   - Context manager support

3. Create new `ValidationContext` class that:
   - Inherits from `ValidatedStrategyMixin`
   - Acts as context object for function-based strategies
   - Provides logging methods

### 6.3 Story X.4: Reimplement execute_rustybt.py

Replace manual row iteration:
```python
# CURRENT (Homebrew)
for row in data.iter_rows():
    strategy.handle_data(None, row)
```

With real rustybt runner:
```python
# TARGET (Real rustybt)
from rustybt.utils.run_algo import run_algorithm
result = run_algorithm(
    initialize=strategy.initialize,
    handle_data=strategy.handle_data,
    bundle='validation-fixture',
    ...
)
```

### 6.4 Stories X.5-X.6: Strategy Reimplementation

Replace deque-based indicators:
```python
# CURRENT (Homebrew)
self._price_history.append(price)
sma = sum(self._price_history) / len(self._price_history)
```

With data.history():
```python
# TARGET (Real rustybt)
prices = data.history(asset, 'close', 20, '1d')
sma = prices.mean()
```

Replace `_execute_order()`:
```python
# CURRENT (Homebrew)
self._execute_order(asset, quantity, price)
```

With rustybt order API:
```python
# TARGET (Real rustybt)
order_target(asset, target_shares)
```

---

## 7. Risk Mitigations

### R1: TradingAlgorithm API Compatibility
- **Risk:** API may not support required logging hooks
- **Mitigation:** Function-based pattern avoids inheritance issues; method wrapping provides logging hooks

### R2: DataBundle Registration Complexity
- **Risk:** Bundle registration may require complex setup
- **Mitigation:** Create helper function that abstracts complexity; document clear registration process

### R3: Indicator Implementation Differences
- **Risk:** Indicator warmup/precision may differ from Backtrader
- **Mitigation:** Use same calculation approach (mean/std on history); document as DESIGN difference if values differ

### R4: Broker Event Capture
- **Risk:** No event hooks for fills
- **Mitigation:** Method wrapping for orders; post-bar transaction extraction from blotter

### R5: Trading Calendar Mismatches
- **Risk:** Bar count differences due to calendar handling
- **Mitigation:** Ensure both frameworks use same calendar; verify bar counts in X.2

---

## 8. Appendix: Key Code Locations

### rustybt Core
| File | Key Classes/Functions |
|------|----------------------|
| `rustybt/algorithm.py` | `TradingAlgorithm`, lifecycle methods |
| `rustybt/api.py` | `order`, `order_target`, `symbol`, etc. |
| `rustybt/utils/run_algo.py` | `run_algorithm()` entry point |
| `rustybt/data/bundles/core.py` | `register()`, `load()`, `BundleData` |
| `rustybt/data/data_portal.py` | `DataPortal` data access |
| `rustybt/finance/blotter/blotter.py` | `Blotter` abstract class |
| `rustybt/pipeline/factors/basic.py` | `SimpleMovingAverage`, `EWMA` |
| `rustybt/pipeline/factors/technical.py` | `RSI`, `MACDSignal`, `BollingerBands` |

### Validation Framework
| File | Key Classes/Functions |
|------|----------------------|
| `rustybt/validation/base_strategy.py` | `ValidatedStrategyMixin`, `RustyBTValidatedStrategy` |
| `rustybt/validation/execute_rustybt.py` | Current homebrew runner (to be replaced) |
| `rustybt/validation/execute_backtrader.py` | Reference implementation (unchanged) |

---

## 9. Open Questions Resolved

| ID | Question | Answer |
|----|----------|--------|
| Q1 | Best integration pattern? | **Function-based** with `ValidatedStrategyMixin` |
| Q2 | How to register custom Parquet data? | Use `@register()` decorator with custom ingest function |
| Q3 | Does rustybt have required indicators? | **Yes** - SMA, EWMA (EMA), RSI, MACD in pipeline factors |
| Q4 | How to capture broker events? | Method wrapping for orders; blotter.get_transactions() for fills |
| Q5 | Trailing stop support? | **Not native** - must implement manually in handle_data |

---

*Document generated as part of Story X.1 analysis. This design guides implementation for Stories X.2-X.8.*
