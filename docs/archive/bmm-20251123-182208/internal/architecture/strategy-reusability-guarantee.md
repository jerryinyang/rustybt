# Strategy Reusability Guarantee

**Date:** 2025-10-03
**Author:** Winston (Architect)
**Status:** ✅ Mandatory Requirement - Epic 6

---

## Executive Summary

**GUARANTEE:** Any strategy written for RustyBT's backtest engine **MUST** run in live/paper trading mode **without any code changes**. This is a **mandatory architectural requirement** for Epic 6.

---

## The Contract

### Single Strategy, Multiple Execution Modes

A strategy is defined **once** by subclassing `TradingAlgorithm`:

```python
class MomentumStrategy(TradingAlgorithm):
    def initialize(self, context):
        """Called once at strategy startup."""
        context.asset = self.symbol('SPY')
        self.sma_fast = 10
        self.sma_slow = 30

    def handle_data(self, context, data):
        """Called every bar (minute/daily)."""
        prices = data.history(context.asset, 'close', self.sma_slow, '1d')
        fast_mavg = prices[-self.sma_fast:].mean()
        slow_mavg = prices.mean()

        if fast_mavg > slow_mavg:
            self.order_target_percent(context.asset, 1.0)
        else:
            self.order_target_percent(context.asset, 0.0)

    def before_trading_start(self, context, data):
        """Optional: Called daily before market open."""
        pass  # Can be used for daily rebalancing
```

This **exact same code** runs in:

### 1. Backtest Mode
```python
from rustybt import run_algorithm

result = run_algorithm(
    strategy=MomentumStrategy(),  # ← Your strategy
    start='2023-01-01',
    end='2023-12-31',
    capital_base=100000,
    data_frequency='daily',
    bundle='quandl'
)
```

### 2. Paper Trading Mode
```python
from rustybt.live import LiveTradingEngine, PaperBroker

engine = LiveTradingEngine(
    strategy=MomentumStrategy(),  # ← Same strategy, no changes
    broker=PaperBroker(),
    shadow_mode=True  # Enable validation
)

asyncio.run(engine.run())
```

### 3. Live Trading Mode
```python
from rustybt.live import LiveTradingEngine
from rustybt.live.brokers import IBAdapter

engine = LiveTradingEngine(
    strategy=MomentumStrategy(),  # ← Same strategy, no changes
    broker=IBAdapter(host='127.0.0.1', port=7497),
    shadow_mode=True
)

asyncio.run(engine.run())
```

**Zero code changes. Zero rewrites. Same `MomentumStrategy` class.**

---

## Mandatory Strategy API

### Required Methods (Must Implement)

| Method | Signature | Called When | Purpose |
|--------|-----------|-------------|---------|
| `initialize` | `initialize(self, context)` | Once at startup | Set up strategy state, register assets |
| `handle_data` | `handle_data(self, context, data)` | Every bar | Core strategy logic, order placement |

### Optional Methods (Backtest & Live)

| Method | Signature | Called When | Purpose |
|--------|-----------|-------------|---------|
| `before_trading_start` | `before_trading_start(self, context, data)` | Daily before market open | Pre-market calculations, daily rebalancing |
| `analyze` | `analyze(self, context, results)` | Once after backtest | Post-backtest analysis (backtest only) |

### Optional Methods (Live Trading Only)

These are **optional extensions** for live trading. If not implemented, strategy still works:

| Method | Signature | Called When | Purpose |
|--------|-----------|-------------|---------|
| `on_order_fill` | `on_order_fill(self, context, order, transaction)` | When order fills | Real-time fill notifications |
| `on_order_cancel` | `on_order_cancel(self, context, order, reason)` | When order canceled | Cancellation handling |
| `on_order_reject` | `on_order_reject(self, context, order, reason)` | When order rejected | Rejection handling |
| `on_broker_message` | `on_broker_message(self, context, message)` | Custom broker events | Broker-specific messages |

**Key Point:** A strategy with only `initialize` and `handle_data` will run in both backtest and live modes.

---

## Context API Compatibility

The `context` object provides the same interface in both modes:

```python
def handle_data(self, context, data):
    # These all work identically in backtest and live:
    context.portfolio.cash                    # Current cash
    context.portfolio.portfolio_value         # Total portfolio value
    context.portfolio.positions[asset]        # Position for asset

    # Order placement (same API):
    self.order(asset, amount)                          # Market order
    self.order_target_percent(asset, target_pct)       # Target % of portfolio
    self.order_target_value(asset, target_value)       # Target $ value

    # Data access (same API):
    data.current(asset, 'close')                       # Current price
    data.history(asset, 'close', bar_count, '1d')      # Historical window
    data.can_trade(asset)                              # Is asset tradable?
```

**All Decimal precision, all the time.** No float vs. Decimal conversion.

---

## Data API Compatibility

The `data` object provides the same interface:

```python
def handle_data(self, context, data):
    # Get current values
    price = data.current(context.asset, 'close')      # Decimal
    volume = data.current(context.asset, 'volume')    # Decimal

    # Get historical window
    prices = data.history(
        context.asset,
        'close',
        bar_count=30,
        frequency='1d'
    )  # Returns Polars DataFrame with Decimal columns

    # Check if tradable
    if data.can_trade(context.asset):
        self.order(context.asset, 100)
```

Works identically in backtest and live. Live mode uses real-time data, backtest uses historical data.

---

## Validation Requirements

### Story 6.7: Paper Trading Validation

**Acceptance Criteria:**
> AC9: Tests validate paper trading produces expected results **(matches backtest for same data)**
>
> AC10: Example demonstrates backtest → paper trading comparison showing **>99% correlation**

**Implementation Tasks:**
```
- [ ] Run same strategy in backtest mode with historical data
- [ ] Run same strategy in paper trading mode with same historical data (simulated real-time)
- [ ] Compare final portfolio values (should match within 0.1%)
- [ ] Compare position histories (should match exactly)
```

This **requires** the same strategy code to run in both modes without changes.

---

## Architecture Enforcement

### Component Integration

**LiveTradingEngine** (Epic 6):
```python
class LiveTradingEngine:
    def __init__(
        self,
        strategy: TradingAlgorithm,  # ← Same base class as backtest
        broker_adapter: BrokerAdapter,
        data_portal: PolarsDataPortal,
        scheduler: APScheduler
    ):
        self.strategy = strategy
```

**Key Points:**
1. `strategy` parameter type is `TradingAlgorithm` (same as backtest)
2. Engine calls `strategy.initialize()`, `strategy.handle_data()`, etc.
3. Optional live hooks (`on_order_fill`) are called if implemented
4. If not implemented, engine continues without error

### Shared Components

Both backtest and live use:
- ✅ Same `DecimalLedger` (portfolio accounting)
- ✅ Same `DecimalPosition` (position tracking)
- ✅ Same `DecimalTransaction` (trade records)
- ✅ Same `PolarsDataPortal` (data access)
- ✅ Same commission models
- ✅ Same slippage models

**Execution differs, but financial calculations are identical.**

---

## Breaking Changes vs. Zipline

**Important:** While RustyBT strategies are reusable **within RustyBT** (backtest → live), they are **NOT compatible with Zipline-Reloaded**:

**Breaking Changes from Zipline:**
1. `order(asset, amount)` - `amount` is now `Decimal`, not `float`
2. Portfolio values returned as `Decimal`, not `float`
3. Data API returns Polars DataFrames, not pandas DataFrames

**Migration Required:**
- Zipline strategies must update to Decimal types
- Update pandas code to Polars
- No changes needed after migrating to RustyBT backtest API

**Once migrated to RustyBT backtest, live trading is automatic (no further changes).**

---

## Examples

### Example 1: Simple Strategy (No Live Hooks)

```python
class BuyAndHoldStrategy(TradingAlgorithm):
    def initialize(self, context):
        context.asset = self.symbol('SPY')
        context.invested = False

    def handle_data(self, context, data):
        if not context.invested:
            self.order_target_percent(context.asset, 1.0)
            context.invested = True

# Works in backtest
run_algorithm(strategy=BuyAndHoldStrategy(), ...)

# Works in live (same code)
LiveTradingEngine(strategy=BuyAndHoldStrategy(), ...)
```

### Example 2: Strategy with Live Hooks (Optional)

```python
class AdvancedStrategy(TradingAlgorithm):
    def initialize(self, context):
        context.asset = self.symbol('SPY')

    def handle_data(self, context, data):
        # Core logic (works in backtest and live)
        price = data.current(context.asset, 'close')
        if price > 100:
            self.order(context.asset, 10)

    def on_order_fill(self, context, order, transaction):
        # Optional: Live-only notification
        # This method is ignored in backtest mode
        logger.info(f"Order filled: {transaction.amount} @ {transaction.price}")

# Backtest: runs initialize + handle_data
run_algorithm(strategy=AdvancedStrategy(), ...)

# Live: runs initialize + handle_data + on_order_fill
LiveTradingEngine(strategy=AdvancedStrategy(), ...)
```

**Same class. Live hooks are bonus features, not requirements.**

---

## Benefits of This Design

### 1. Confidence
- Test strategy in backtest
- Validate in paper trading
- Deploy to live **with zero code risk**

### 2. Efficiency
- Write strategy logic once
- No "backtest version" vs. "live version" maintenance
- Changes to strategy logic propagate automatically

### 3. Safety
- Shadow trading validation compares backtest vs. live (Story 6.12)
- If same code produces different results → circuit breaker trips
- Forces investigation of execution differences, not code differences

### 4. Simplicity
- Single codebase
- Single test suite
- Single truth for strategy logic

---

## Implementation Checklist

### Story 6.1: Design Live Trading Architecture
- [x] AC10: Strategy reusability guaranteed (added)
- [x] Tasks: Document strategy API contract
- [x] Tasks: Provide example showing same strategy in backtest, paper, live

### Story 6.2: Implement Async Trading Engine Core
- [x] AC8: Strategy reusability validated (added)
- [ ] Tests: Run same TradingAlgorithm in backtest and live
- [ ] Tests: Verify context API works identically
- [ ] Tests: Verify data API works identically

### Story 6.7: Implement Paper Trading Mode
- [ ] AC9: Tests validate paper trading matches backtest for same data
- [ ] AC10: Example demonstrates >99% correlation (same strategy code)

### Story 6.12: Implement Shadow Trading Validation
- [ ] Shadow engine validates same strategy produces aligned signals
- [ ] Alignment metrics confirm execution parity

---

## Documentation References

**Source Files:**
- [enhancement-scope-and-integration-strategy.md](enhancement-scope-and-integration-strategy.md#api-integration) - API Integration section
- [component-architecture.md](component-architecture.md#livetradingengine) - LiveTradingEngine definition
- [6.1.design-live-trading-architecture.story.md](../stories/completed/6.1.design-live-trading-architecture.story.md) - AC10
- [6.2.async-trading-engine-core.story.md](../stories/completed/6.2.async-trading-engine-core.story.md) - AC8
- [6.7.paper-trading-mode.story.md](../stories/completed/6.7.paper-trading-mode.story.md) - Validation tests

---

## Conclusion

**Strategy reusability is a first-class architectural requirement**, not an afterthought. The same `TradingAlgorithm` class runs in:

✅ Backtest mode (historical data, simulated execution)
✅ Paper trading mode (real-time data, simulated execution)
✅ Live trading mode (real-time data, real broker)

**Zero code changes. Zero rewrites. Zero risk.**

This guarantee is enforced through:
1. Shared `TradingAlgorithm` base class
2. Identical `context` and `data` APIs
3. Validation tests (Story 6.7 AC9, AC10)
4. Shadow trading framework (Story 6.12)

**Status:** ✅ **CONFIRMED** - Epic 6 design fully supports this requirement.
