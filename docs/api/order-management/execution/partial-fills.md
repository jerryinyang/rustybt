# Partial Fill Models

**Version**: 2.0 (Production Grade)
**Status**: ✅ Source Code Verified
**Last Updated**: 2025-10-16
**Story**: 11.3 - Order & Portfolio Management Documentation (Production Grade Redo)

---

## Overview

RustyBT's partial fill models provide realistic simulation of order execution when full order quantity cannot be immediately filled. In real markets, large orders, illiquid assets, or limit orders often fill gradually over multiple time periods.

**Source**: `rustybt/finance/execution.py:1200-1677`

### Why Partial Fills Matter

In live trading, orders rarely fill completely in a single transaction:

1. **Liquidity Constraints**: Order size exceeds available liquidity
2. **Limit Orders**: Price must reach limit, may not stay there
3. **Market Impact**: Large orders move price against you
4. **Exchange Rules**: FOK/IOC not always used, partial fills standard

**Real-World Impact**:
- **Position Sizing**: Actual position ≠ intended position
- **Slippage**: Multiple fills at different prices
- **Timing**: Position built over minutes/hours, not instantaneously
- **Risk Management**: Under-filled orders leave gaps in hedges

### Architecture

```python
PartialFillModel (Abstract Base Class)
    ├── VolumeBasedFillModel        # Fill based on % of volume
    ├── AggressiveFillModel          # Fill quickly (90-100%)
    ├── ConservativeFillModel        # Fill slowly (30-50%)
    └── BalancedFillModel            # Fill moderately (60-80%)

OrderTracker                         # Tracks partial fill state
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

1. [PartialFillModel Base Class](#partialfillmodel-base-class)
2. [VolumeBasedFillModel](#volumebasedfillmodel)
3. [AggressiveFillModel](#aggressivefillmodel)
4. [ConservativeFillModel](#conservativefillmodel)
5. [BalancedFillModel](#balancedfillmodel)
6. [OrderTracker](#ordertracker)
7. [Complete Examples](#complete-examples)
8. [Best Practices](#best-practices)
9. [Related Documentation](#related-documentation)

---

## PartialFillModel Base Class

**Source**: `rustybt/finance/execution.py:1375-1402`
**Import**: `from rustybt.finance.execution import PartialFillModel`

Abstract base class for all partial fill simulation models.

### Abstract Methods

```python
import abc
from decimal import Decimal

class PartialFillModel(metaclass=abc.ABCMeta):
    """Base class for partial fill simulation models."""

    @abc.abstractmethod
    def calculate_fill_amount(self, order, bar_data):
        """Calculate how much of an order fills in this period.

        Parameters
        ----------
        order : Order
            The order being filled
        bar_data : BarData
            Current market data

        Returns
        -------
        fill_amount : int
            Number of shares filled (0 to order.remaining)
        fill_price : Decimal
            Price at which shares filled
        """
        raise NotImplementedError
```

### Key Concepts

- **Partial Fill**: Order fills gradually over multiple periods
- **Fill Ratio**: `filled / total_amount` (0.0 to 1.0)
- **Remaining**: `total_amount - filled`
- **Fill Price**: May vary across partial fills

### Fill States

```python
# Order lifecycle with partial fills:
# 1. New order: filled=0, remaining=amount
# 2. Partial fill: 0 < filled < amount
# 3. Fully filled: filled=amount, remaining=0

order.amount = 1000        # Total order size
order.filled = 350         # Filled so far
order.remaining = 650      # Still to fill
order.fill_ratio = 0.35    # 35% filled
```

---

## VolumeBasedFillModel

**Source**: `rustybt/finance/execution.py:1404-1498`
**Import**: `from rustybt.finance.execution import VolumeBasedFillModel`

Fill orders based on percentage of available market volume. Most realistic model.

### Constructor

```python
VolumeBasedFillModel(
    volume_share_limit=0.025,
    min_fill_ratio=0.01,
    max_fill_ratio=1.0
)
```

**Parameters**:
- `volume_share_limit` (float): **REQUIRED**. Maximum order size as fraction of bar volume. Default: `0.025` (2.5% of volume).
- `min_fill_ratio` (float, optional): Minimum fill ratio per period. Default: `0.01` (1%).
- `max_fill_ratio` (float, optional): Maximum fill ratio per period. Default: `1.0` (100%, full fill possible).

**Raises**:
- `ValueError`: If parameters out of valid range [0, 1].

### Behavior

```python
# Calculate fill based on available volume
bar_volume = bar_data.current(order.asset, 'volume')
available_volume = bar_volume * volume_share_limit

# Fill ratio for this period
fill_amount = min(order.remaining, available_volume)
fill_ratio = fill_amount / order.amount

# Clamp to min/max
fill_ratio = max(min_fill_ratio, min(fill_ratio, max_fill_ratio))
actual_fill = int(order.remaining * fill_ratio)
```

**Key Factors**:
- ✅ **Volume-Dependent**: Liquid assets fill faster
- 📊 **Market Impact**: Large orders fill slower
- ⚡ **Realistic**: Matches real-world execution
- 🔄 **Multi-Period**: Large orders span multiple bars

### When to Use

- **Production Backtests**: Most realistic model
- **Large Orders**: Order size significant vs volume
- **Illiquid Assets**: Low volume = slow fills
- **Realistic Testing**: Match live execution

### When to Avoid

- ❌ Small orders in liquid markets (instant fill realistic)
- ❌ Market orders in high liquidity (fills fast)
- ❌ Prototyping (simpler models faster)

### Example: Basic Volume-Based Fills

```python
# NOTE: set_execution_engine is available via context in TradingAlgorithm
from rustybt.finance.execution import VolumeBasedFillModel, ExecutionEngine

def initialize(context):
    """Set up volume-based partial fills."""
    # Fill up to 2.5% of bar volume per period
    fill_model = VolumeBasedFillModel(
        volume_share_limit=0.025,  # Max 2.5% of volume
        min_fill_ratio=0.01,        # At least 1% per bar
        max_fill_ratio=1.0          # Can fill 100% if enough volume
    )

    engine = ExecutionEngine(
        partial_fill_model=fill_model,
        # ... other parameters
    )
    set_execution_engine(engine)
```

### Example: Order Size vs Volume Analysis

```python
# NOTE: initialize() and handle_data() are available in TradingAlgorithm context
from rustybt.api import order
from rustybt.finance.execution import VolumeBasedFillModel, MarketOrder

def initialize(context):
    """Track partial fill behavior."""
    context.fill_model = VolumeBasedFillModel(volume_share_limit=0.025)
    context.partial_fills = []

def handle_data(context, data):
    """Place order and track fill progress."""
    asset = symbol('AAPL')
    bar_volume = data.current(asset, 'volume')

    # Place order = 10% of bar volume (will partially fill)
    order_size = int(bar_volume * 0.10)

    if order_size > 0:
        order_id = order(asset, order_size, style=MarketOrder())

        # Expected fills:
        # - 2.5% of volume per bar
        # - Need ~4 bars to fill 10% volume order
        expected_bars = 0.10 / 0.025  # = 4 bars

        context.log.info(
            f"Placed order: {order_size:,} shares "
            f"({order_size/bar_volume:.1%} of volume), "
            f"expect {expected_bars:.0f} bars to fill"
        )
```

### Example: Adaptive Volume Share

```python
from rustybt.finance.execution import VolumeBasedFillModel

class AdaptiveVolumeModel(VolumeBasedFillModel):
    """Adjust volume share based on order urgency."""

    def __init__(self, urgency='normal'):
        # Urgency levels
        urgency_params = {
            'low': 0.01,      # 1% of volume (passive)
            'normal': 0.025,  # 2.5% of volume (standard)
            'high': 0.05,     # 5% of volume (aggressive)
            'urgent': 0.10    # 10% of volume (very aggressive)
        }

        volume_share = urgency_params.get(urgency, 0.025)

        super().__init__(
            volume_share_limit=volume_share,
            min_fill_ratio=volume_share / 2,  # Min = half of target
            max_fill_ratio=1.0
        )

# Usage:
passive_model = AdaptiveVolumeModel(urgency='low')    # Slow fills
normal_model = AdaptiveVolumeModel(urgency='normal')  # Standard
urgent_model = AdaptiveVolumeModel(urgency='urgent')  # Fast fills
```

---

## AggressiveFillModel

**Source**: `rustybt/finance/execution.py:1500-1514`
**Import**: `from rustybt.finance.execution import AggressiveFillModel`

Aggressive fill strategy: 90-100% of order fills per period. Fast execution.

### Constructor

```python
AggressiveFillModel()
```

**Parameters**: None

### Behavior

```python
# Fill 90-100% of remaining order each period
fill_ratio = random.uniform(0.90, 1.00)
fill_amount = int(order.remaining * fill_ratio)
```

- ⚡ **Fast Fills**: Most orders complete in 1-2 periods
- 🎯 **Market Orders**: Simulates aggressive market order execution
- ⚠️ **Less Realistic**: Ignores volume constraints
- 📊 **Use Case**: High liquidity, small orders, market orders

### When to Use

- **High Liquidity**: Large cap stocks, major ETFs
- **Small Orders**: Order size < 0.1% of ADV
- **Market Orders**: Price not important, speed critical
- **Simple Testing**: Quick fills, focus on strategy logic

### When to Avoid

- ❌ Large orders (unrealistic instant fill)
- ❌ Illiquid assets (would have major impact)
- ❌ Production backtests (too optimistic)

### Example: Aggressive Fill for Liquid Assets

```python
# NOTE: set_execution_engine is available via context in TradingAlgorithm
from rustybt.finance.execution import AggressiveFillModel, ExecutionEngine

def initialize(context):
    """Use aggressive fills for liquid large-cap stocks."""
    # Most orders fill in 1-2 bars
    fill_model = AggressiveFillModel()

    engine = ExecutionEngine(
        partial_fill_model=fill_model,
        # ... other parameters
    )
    set_execution_engine(engine)

    context.log.info("Using aggressive fill model: 90-100% per bar")
```

---

## ConservativeFillModel

**Source**: `rustybt/finance/execution.py:1516-1530`
**Import**: `from rustybt.finance.execution import ConservativeFillModel`

Conservative fill strategy: 30-50% of order fills per period. Slow, passive execution.

### Constructor

```python
ConservativeFillModel()
```

**Parameters**: None

### Behavior

```python
# Fill 30-50% of remaining order each period
fill_ratio = random.uniform(0.30, 0.50)
fill_amount = int(order.remaining * fill_ratio)
```

- 🐌 **Slow Fills**: Orders take 2-4 periods to complete
- 💰 **Limit Orders**: Simulates passive limit order execution
- ✅ **Lower Impact**: Mimics working order over time
- 📊 **Use Case**: Illiquid assets, large orders, passive strategies

### When to Use

- **Illiquid Assets**: Low volume, wide spreads
- **Large Orders**: Order size > 1% of ADV
- **Limit Orders**: Working orders at specific prices
- **Passive Execution**: Price improvement more important than speed

### When to Avoid

- ❌ High liquidity + small orders (unrealistically slow)
- ❌ Market orders (should fill faster)
- ❌ Time-sensitive strategies (too slow)

### Example: Conservative Fill for Illiquid Assets

```python
# NOTE: set_execution_engine is available via context in TradingAlgorithm
from rustybt.finance.execution import ConservativeFillModel, ExecutionEngine

def initialize(context):
    """Use conservative fills for illiquid small-cap stocks."""
    # Orders fill over 2-4 bars (passive execution)
    fill_model = ConservativeFillModel()

    engine = ExecutionEngine(
        partial_fill_model=fill_model,
        # ... other parameters
    )
    set_execution_engine(engine)

    context.log.info("Using conservative fill model: 30-50% per bar")
```

---

## BalancedFillModel

**Source**: `rustybt/finance/execution.py:1532-1546`
**Import**: `from rustybt.finance.execution import BalancedFillModel`

Balanced fill strategy: 60-80% of order fills per period. Middle ground.

### Constructor

```python
BalancedFillModel()
```

**Parameters**: None

### Behavior

```python
# Fill 60-80% of remaining order each period
fill_ratio = random.uniform(0.60, 0.80)
fill_amount = int(order.remaining * fill_ratio)
```

- ⚖️ **Balanced**: Middle ground between aggressive and conservative
- 📊 **Moderate Speed**: Orders fill in 1-3 periods
- ✅ **Default Choice**: Good for general strategies
- 🎯 **Use Case**: Standard equities, moderate liquidity

### When to Use

- **Default Model**: Good starting point for most strategies
- **Moderate Liquidity**: Mid-cap stocks, standard ETFs
- **General Testing**: Balanced realism and simplicity
- **Mixed Orders**: Combination of market and limit orders

### When to Avoid

- ❌ When specific liquidity known (use VolumeBasedFillModel)
- ❌ When precision critical (use production-grade model)

### Example: Balanced Fill as Default

```python
# NOTE: set_execution_engine is available via context in TradingAlgorithm
from rustybt.finance.execution import BalancedFillModel, ExecutionEngine

def initialize(context):
    """Use balanced fills as default."""
    # Orders fill over 1-3 bars (moderate execution)
    fill_model = BalancedFillModel()

    engine = ExecutionEngine(
        partial_fill_model=fill_model,
        # ... other parameters
    )
    set_execution_engine(engine)

    context.log.info("Using balanced fill model: 60-80% per bar")
```

---

## OrderTracker

**Source**: `rustybt/finance/execution.py:1548-1677`
**Import**: `from rustybt.finance.execution import OrderTracker`

Tracks partial fill state for orders across multiple time periods.

### Constructor

```python
OrderTracker()
```

**Parameters**: None

### Attributes

```python
class OrderTracker:
    def __init__(self):
        self.active_orders = {}      # order_id -> OrderState
        self.fill_history = {}       # order_id -> List[PartialFill]
        self.completed_orders = {}   # order_id -> Order
```

### Methods

#### track_order(order)

```python
def track_order(self, order):
    """Start tracking an order.

    Parameters
    ----------
    order : Order
        Order to track
    """
```

#### record_fill(order_id, fill_amount, fill_price, timestamp)

```python
def record_fill(self, order_id, fill_amount, fill_price, timestamp):
    """Record a partial fill.

    Parameters
    ----------
    order_id : str
        Order identifier
    fill_amount : int
        Shares filled in this fill
    fill_price : Decimal
        Price of this fill
    timestamp : pd.Timestamp
        Time of fill
    """
```

#### get_fill_history(order_id)

```python
def get_fill_history(self, order_id):
    """Get all fills for an order.

    Parameters
    ----------
    order_id : str
        Order identifier

    Returns
    -------
    fills : List[PartialFill]
        All partial fills for this order
    """
```

#### is_fully_filled(order_id)

```python
def is_fully_filled(self, order_id):
    """Check if order is fully filled.

    Parameters
    ----------
    order_id : str
        Order identifier

    Returns
    -------
    fully_filled : bool
        True if order.filled == order.amount
    """
```

### Example: Tracking Partial Fills

```python
# NOTE: initialize() and handle_data() are available in TradingAlgorithm context
from rustybt.api import order
from rustybt.finance.execution import OrderTracker, MarketOrder

def initialize(context):
    """Initialize order tracker."""
    context.tracker = OrderTracker()
    context.monitored_orders = {}

def handle_data(context, data):
    """Place order and track fills."""
    asset = symbol('AAPL')

    # Place large order (will partially fill)
    order_id = order(asset, 10000, style=MarketOrder())

    if order_id:
        context.tracker.track_order(order_id)
        context.monitored_orders[order_id] = {
            'asset': asset,
            'submitted_time': context.get_datetime(),
            'target_amount': 10000
        }

    # Check fill progress for monitored orders
    for oid in list(context.monitored_orders.keys()):
        fill_history = context.tracker.get_fill_history(oid)

        if fill_history:
            total_filled = sum(f.amount for f in fill_history)
            target = context.monitored_orders[oid]['target_amount']
            fill_pct = total_filled / target

            context.log.info(
                f"Order {oid}: {total_filled:,}/{target:,} filled "
                f"({fill_pct:.1%}) in {len(fill_history)} fills"
            )

            # Calculate volume-weighted average fill price
            total_value = sum(f.amount * f.price for f in fill_history)
            vwap = total_value / total_filled

            context.log.info(f"  VWAP: ${vwap:.2f}")

        # Remove if fully filled
        if context.tracker.is_fully_filled(oid):
            context.log.info(f"Order {oid} fully filled!")
            del context.monitored_orders[oid]
```

---

## Complete Examples

### Example 1: Production Partial Fill Strategy

```python
# NOTE: initialize() and handle_data() are available in TradingAlgorithm context
from rustybt.api import order, symbol
from rustybt.finance.execution import VolumeBasedFillModel, OrderTracker, MarketOrder

def initialize(context):
    """Set up production-grade partial fill tracking."""
    # Volume-based model (most realistic)
    context.fill_model = VolumeBasedFillModel(
        volume_share_limit=0.025,  # 2.5% of volume
        min_fill_ratio=0.01,
        max_fill_ratio=1.0
    )

    # Order tracker
    context.tracker = OrderTracker()

    # Strategy parameters
    context.target_position = 50000  # shares
    context.max_order_size = 10000   # per order

def handle_data(context, data):
    """Incrementally build position with partial fill awareness."""
    asset = symbol('AAPL')
    current_position = context.portfolio.positions.get(asset, 0)
    remaining_to_buy = context.target_position - current_position

    # Check if we have unfilled orders
    open_orders = context.blotter.open_orders.get(asset, [])

    if not open_orders and remaining_to_buy > 0:
        # Place new order (capped at max_order_size)
        order_size = min(remaining_to_buy, context.max_order_size)

        order_id = order(asset, order_size, style=MarketOrder())

        if order_id:
            context.tracker.track_order(order_id)

            # Get volume to estimate fill time
            bar_volume = data.current(asset, 'volume')
            volume_share = 0.025  # Our model parameter

            expected_bars = order_size / (bar_volume * volume_share)

            context.log.info(
                f"Placed order: {order_size:,} shares, "
                f"expect ~{expected_bars:.1f} bars to fill"
            )

    # Monitor partial fills
    for open_order in open_orders:
        if open_order.filled > 0:
            fill_pct = open_order.filled / open_order.amount
            context.log.info(
                f"Order {open_order.id}: {fill_pct:.1%} filled "
                f"({open_order.filled:,}/{open_order.amount:,})"
            )
```

### Example 2: Adaptive Fill Model Based on Liquidity

```python
# NOTE: initialize() and handle_data() are available in TradingAlgorithm context
from rustybt.api import order
from rustybt.finance.execution import (
    VolumeBasedFillModel, AggressiveFillModel,
    ConservativeFillModel, MarketOrder
)

def initialize(context):
    """Use different fill models based on asset liquidity."""
    context.liquidity_thresholds = {
        'high': 5_000_000,    # > 5M ADV
        'medium': 1_000_000,  # 1-5M ADV
        'low': 1_000_000      # < 1M ADV
    }

def get_fill_model(asset, data):
    """Select appropriate fill model based on liquidity."""
    # Calculate average daily volume
    volumes = data.history(asset, 'volume', 20, '1d')
    avg_volume = volumes.mean()

    if avg_volume > 5_000_000:
        # High liquidity: aggressive fills
        return AggressiveFillModel()

    elif avg_volume > 1_000_000:
        # Medium liquidity: volume-based fills
        return VolumeBasedFillModel(volume_share_limit=0.025)

    else:
        # Low liquidity: conservative fills
        return ConservativeFillModel()

def handle_data(context, data):
    """Place orders with liquidity-appropriate fill model."""
    asset = symbol('TICKER')

    # Get appropriate fill model
    fill_model = get_fill_model(asset, data)

    context.log.info(f"Using {fill_model.__class__.__name__} for {asset.symbol}")

    # Place order with selected model
    # (Note: In practice, set model once in initialize or per-asset basis)
    order(asset, 1000, style=MarketOrder())
```

### Example 3: Fill Price Impact Analysis

```python
# NOTE: initialize() and handle_data() are available in TradingAlgorithm context
from rustybt.api import order
from rustybt.finance.execution import OrderTracker, MarketOrder
import pandas as pd

def initialize(context):
    """Track fill price slippage due to partial fills."""
    context.tracker = OrderTracker()
    context.fill_analysis = []

def handle_data(context, data):
    """Analyze fill quality."""
    asset = symbol('AAPL')
    current_price = data.current(asset, 'price')

    # Place order
    order_id = order(asset, 10000, style=MarketOrder())

    if order_id:
        context.tracker.track_order(order_id)

        # Store initial price for comparison
        context.fill_analysis.append({
            'order_id': order_id,
            'submission_price': current_price,
            'submission_time': context.get_datetime()
        })

def analyze(context, results):
    """Analyze fill price degradation."""
    for analysis in context.fill_analysis:
        order_id = analysis['order_id']
        fill_history = context.tracker.get_fill_history(order_id)

        if not fill_history:
            continue

        # Calculate VWAP of fills
        total_filled = sum(f.amount for f in fill_history)
        total_value = sum(f.amount * f.price for f in fill_history)
        vwap = total_value / total_filled

        # Calculate slippage
        submission_price = analysis['submission_price']
        slippage_bps = ((vwap - submission_price) / submission_price) * 10000

        # Time to complete
        first_fill = fill_history[0].timestamp
        last_fill = fill_history[-1].timestamp
        fill_duration = (last_fill - first_fill).total_seconds()

        context.log.info(
            f"\nOrder {order_id} Fill Analysis:"
            f"\n  Fills: {len(fill_history)}"
            f"\n  Duration: {fill_duration:.0f}s"
            f"\n  Submission price: ${submission_price:.2f}"
            f"\n  VWAP: ${vwap:.2f}"
            f"\n  Slippage: {slippage_bps:.1f} bps"
        )
```

---

## Best Practices

### ✅ DO

1. **Match Model to Liquidity**
   ```python
   # High liquidity = aggressive
   if avg_volume > 5_000_000:
       model = AggressiveFillModel()
   # Low liquidity = volume-based or conservative
   else:
       model = VolumeBasedFillModel(volume_share_limit=0.01)
   ```

2. **Track Fill Progress**
   ```python
   # Monitor partial fills
   tracker = OrderTracker()
   for order in open_orders:
       if order.filled < order.amount:
           print(f"Partial fill: {order.filled}/{order.amount}")
   ```

3. **Account for Fill Delays**
   ```python
   # Don't assume instant fills
   if open_orders_exist(asset):
       return  # Wait for current order to fill
   ```

4. **Use VolumeBasedFillModel for Production**
   ```python
   # Most realistic
   model = VolumeBasedFillModel(volume_share_limit=0.025)
   ```

5. **Measure Fill Quality**
   ```python
   # Track VWAP vs submission price
   vwap = sum(f.price * f.amount for f in fills) / total_filled
   slippage = vwap - submission_price
   ```

### ❌ DON'T

1. **Don't Ignore Partial Fills**
   ```python
   # BAD: Assume full fill
   order(asset, 10000)  # May only fill 2500!

   # GOOD: Check actual fill
   order_id = order(asset, 10000)
   actual_filled = get_order(order_id).filled
   ```

2. **Don't Use AggressiveFillModel for Large Orders**
   ```python
   # BAD: 10% of ADV fills instantly (unrealistic!)
   model = AggressiveFillModel()
   order(asset, 100000)  # Way too optimistic

   # GOOD: Volume-based for large orders
   model = VolumeBasedFillModel(volume_share_limit=0.025)
   ```

3. **Don't Place Multiple Orders Without Checking Fills**
   ```python
   # BAD: Stack up unfilled orders
   order(asset, 10000)
   order(asset, 10000)  # Previous may not be filled!

   # GOOD: Check open orders first
   if not get_open_orders(asset):
       order(asset, 10000)
   ```

4. **Don't Forget Fill Price Variance**
   ```python
   # BAD: Use submission price for calculations
   cost = order_amount * submission_price  # Wrong!

   # GOOD: Use actual fill prices
   cost = sum(f.amount * f.price for f in fills)
   ```

5. **Don't Use Same Model for All Assets**
   ```python
   # BAD: One size fits all
   model = BalancedFillModel()  # For everything

   # GOOD: Asset-specific models
   if asset_is_liquid:
       model = AggressiveFillModel()
   else:
       model = ConservativeFillModel()
   ```

---

## Related Documentation

### Order Management
- [Order Types](../order-types.md) - All supported order execution styles
- [Order Lifecycle](../workflows/order-lifecycle.md) - Order state transitions

### Execution Systems
- [Latency Models](latency-models.md) - Execution delay simulation

### Transaction Costs
- [Slippage Models](../transaction-costs/slippage.md) - Price impact from fills
- [Commission Models](../transaction-costs/commissions.md) - Per-share fees

---

## Next Steps

1. **Learn Latency Models**: Understand execution delays → [Latency Models](latency-models.md)
3. **Model Slippage**: Account for price impact → [Slippage Models](../transaction-costs/slippage.md)
4. **Study Order Lifecycle**: See how fills affect order states → [Order Lifecycle](../workflows/order-lifecycle.md)

---

**Document Status**: ✅ Production Grade - All APIs Verified Against Source Code
**Last Verification**: 2025-10-16
**Verification Method**: Direct source code inspection of `rustybt/finance/execution.py`
**Story**: 11.3 - Order & Portfolio Management Documentation (Production Grade Redo)
