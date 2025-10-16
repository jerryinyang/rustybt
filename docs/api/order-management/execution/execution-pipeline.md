# Execution Pipeline: Integrated Order Execution System

**Overview**: Complete order execution flow in RustyBT
**Verified**: 2025-10-16

## Overview

The **Execution Pipeline** is RustyBT's integrated system for realistic order execution simulation. It combines multiple components to provide production-grade backtesting accuracy:

- **Order Types** - Define how orders should execute
- **Blotter** - Manages order lifecycle
- **Latency Models** - Simulate execution delays
- **Partial Fill Models** - Simulate incomplete fills
- **Slippage Models** - Model price impact
- **Commission Models** - Calculate transaction costs

This document explains how these components work together to process orders from submission through final execution.

---

## Execution Pipeline Architecture

```
┌────────────────────────────────────────────────────────────┐
│                    STRATEGY ALGORITHM                       │
│                                                             │
│  order(asset, amount, style=LimitOrder(150.00))           │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    DECIMAL BLOTTER                          │
│                                                             │
│  1. Order Validation                                        │
│     • Validate parameters                                   │
│     • Check amount != 0                                     │
│     • Create DecimalOrder object                            │
│                                                             │
│  2. Order Tracking                                          │
│     • Add to open_orders[asset]                            │
│     • Track in orders[order_id]                            │
│     • Add to new_orders list                               │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              ORDER TRIGGER CHECKING                         │
│              (per market data bar)                          │
│                                                             │
│  For each open order:                                       │
│    • Check if stop price hit                                │
│    • Check if limit price reached                           │
│    • Update order.triggered status                          │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
            ┌─────────────────┐
            │ Triggered?      │
            └────┬──────┬─────┘
                 │ No   │ Yes
                 ▼      ▼
           ┌──────┐  ┌─────────────────────────────────────┐
           │ Wait │  │    LATENCY MODEL                    │
           └──────┘  │                                     │
                     │  • Calculate execution delay        │
                     │  • FixedLatency: constant delay     │
                     │  • RandomLatency: stochastic        │
                     │  • HistoricalLatency: realistic     │
                     │  • CompositeLatency: multi-layer    │
                     └─────────────┬───────────────────────┘
                                   │
                                   ▼
                     ┌─────────────────────────────────────┐
                     │    PARTIAL FILL MODEL               │
                     │                                     │
                     │  • Determine fill amount            │
                     │  • VolumeBasedFill: % of volume     │
                     │  • AggressiveFill: 90-100%          │
                     │  • ConservativeFill: 30-50%         │
                     │  • BalancedFill: 60-80%             │
                     └─────────────┬───────────────────────┘
                                   │
                                   ▼
                     ┌─────────────────────────────────────┐
                     │    SLIPPAGE MODEL                   │
                     │                                     │
                     │  • Calculate execution price        │
                     │  • FixedSlippage: constant          │
                     │  • VolumeShareSlippage: impact      │
                     │  • price_impact = f(order_size)     │
                     └─────────────┬───────────────────────┘
                                   │
                                   ▼
                     ┌─────────────────────────────────────┐
                     │    COMMISSION MODEL                 │
                     │                                     │
                     │  • Calculate transaction cost       │
                     │  • PerShare: cost × shares          │
                     │  • PerTrade: flat fee               │
                     │  • PerDollar: cost × notional       │
                     └─────────────┬───────────────────────┘
                                   │
                                   ▼
                     ┌─────────────────────────────────────┐
                     │    TRANSACTION CREATION             │
                     │                                     │
                     │  • Create DecimalTransaction        │
                     │  • Record: price, amount, costs     │
                     │  • Update order.filled              │
                     │  • Calculate order.filled_price     │
                     │  • Add to transactions list         │
                     └─────────────┬───────────────────────┘
                                   │
                                   ▼
                     ┌─────────────────────────────────────┐
                     │    ORDER STATUS UPDATE              │
                     │                                     │
                     │  if order.remaining == 0:           │
                     │    • Remove from open_orders        │
                     │    • Status: FILLED                 │
                     │  else:                              │
                     │    • Keep in open_orders            │
                     │    • Status: PARTIALLY_FILLED       │
                     └─────────────┬───────────────────────┘
                                   │
                                   ▼
                     ┌─────────────────────────────────────┐
                     │    LEDGER UPDATE                    │
                     │                                     │
                     │  • Update positions                 │
                     │  • Deduct cash (buy)                │
                     │  • Add cash (sell)                  │
                     │  • Track cost basis                 │
                     └─────────────────────────────────────┘
```

---

## Complete Execution Pipeline Example

This example demonstrates the full execution pipeline from order submission through transaction creation.

```python
from decimal import Decimal
from datetime import datetime, timedelta
from rustybt.assets import Equity
from rustybt.finance.decimal.blotter import DecimalBlotter
from rustybt.finance.decimal.commission import PerShareCommission
from rustybt.finance.decimal.slippage import FixedBasisPointsSlippage
from rustybt.finance.execution import (
    FixedLatencyModel,
    VolumeBasedFillModel,
    OrderTracker
)

# ============================================================
# STEP 1: Setup Execution Pipeline Components
# ============================================================

print("=" * 60)
print("STEP 1: SETUP EXECUTION PIPELINE")
print("=" * 60)

# Create blotter with commission and slippage
blotter = DecimalBlotter(
    commission_model=PerShareCommission(
        cost_per_share=Decimal("0.005"),
        min_cost=Decimal("1.00")
    ),
    slippage_model=FixedBasisPointsSlippage(
        basis_points=Decimal("5")  # 0.05% slippage
    )
)

# Create latency model (50ms fixed delay)
latency_model = FixedLatencyModel(latency_ms=50.0)

# Create partial fill model (volume-based)
fill_model = VolumeBasedFillModel(
    volume_share_limit=Decimal("0.025"),  # Max 2.5% of volume
    min_fill_ratio=Decimal("0.3"),
    max_fill_ratio=Decimal("1.0")
)

# Create order tracker for fill history
order_tracker = OrderTracker()

# Setup asset and initial time
aapl = Equity(1, exchange='NYSE', symbol='AAPL')
current_time = datetime(2024, 1, 15, 9, 30, 0)

print(f"Blotter: {blotter}")
print(f"Latency Model: {latency_model}")
print(f"Fill Model: {fill_model}")
print(f"Current Time: {current_time}")

# ============================================================
# STEP 2: Submit Order
# ============================================================

print("\n" + "=" * 60)
print("STEP 2: ORDER SUBMISSION")
print("=" * 60)

# Set blotter time
blotter.set_current_dt(current_time)

# Submit limit order
order_id = blotter.order(
    asset=aapl,
    amount=Decimal("1000"),  # Large order
    order_type="limit",
    limit_price=Decimal("150.00")
)

# Get order object
order = blotter.get_order(order_id)

print(f"Order ID: {order.id}")
print(f"Asset: {order.asset.symbol}")
print(f"Amount: {order.amount}")
print(f"Order Type: {order.order_type}")
print(f"Limit Price: ${order.limit}")
print(f"Status: {order.status}")
print(f"Filled: {order.filled}")
print(f"Remaining: {order.remaining}")

# Track order
order_tracker.track_order(order.id, order.amount)

# ============================================================
# STEP 3: Market Data Bar 1 - Price Above Limit (No Fill)
# ============================================================

print("\n" + "=" * 60)
print("STEP 3: BAR 1 - PRICE ABOVE LIMIT")
print("=" * 60)

current_time += timedelta(minutes=1)
blotter.set_current_dt(current_time)

# Market data
bar_data = {
    'close': Decimal("151.00"),
    'volume': Decimal("50000")
}

print(f"Time: {current_time}")
print(f"Market Price: ${bar_data['close']}")
print(f"Bar Volume: {bar_data['volume']}")

# Check if order triggers
order.check_triggers(bar_data['close'], current_time)
print(f"Order Triggered: {order.triggered}")

if order.triggered:
    # Apply latency (would add delay in real execution)
    latency_ms = latency_model.calculate_latency(order)
    print(f"Execution Latency: {latency_ms}ms")

    # Process order
    transaction = blotter.process_order(order, bar_data['close'])
    if transaction:
        print("✓ Order filled")
    else:
        print("✗ Order not filled")
else:
    print("✗ Order not triggered - price above limit")

# ============================================================
# STEP 4: Market Data Bar 2 - Price at Limit (Partial Fill)
# ============================================================

print("\n" + "=" * 60)
print("STEP 4: BAR 2 - PRICE AT LIMIT (PARTIAL FILL)")
print("=" * 60)

current_time += timedelta(minutes=1)
blotter.set_current_dt(current_time)

# Market data
bar_data = {
    'close': Decimal("149.50"),
    'volume': Decimal("100000")
}

print(f"Time: {current_time}")
print(f"Market Price: ${bar_data['close']}")
print(f"Bar Volume: {bar_data['volume']}")

# Check if order triggers
order.check_triggers(bar_data['close'], current_time)
print(f"Order Triggered: {order.triggered}")

if order.triggered:
    # Apply latency
    latency_ms = latency_model.calculate_latency(order)
    print(f"Execution Latency: {latency_ms}ms")

    # Calculate fill amount based on volume
    max_volume_share = bar_data['volume'] * fill_model.volume_share_limit
    potential_fill = min(order.remaining, max_volume_share)
    fill_ratio = fill_model.calculate_fill_ratio(order, bar_data)
    actual_fill = potential_fill * fill_ratio

    print(f"Max Volume Share: {max_volume_share}")
    print(f"Potential Fill: {potential_fill}")
    print(f"Fill Ratio: {float(fill_ratio):.2%}")
    print(f"Actual Fill: {actual_fill}")

    # Calculate execution price with slippage
    execution_price = blotter.slippage_model.calculate(order, bar_data['close'])
    slippage_amount = abs(execution_price - bar_data['close'])
    print(f"Base Price: ${bar_data['close']}")
    print(f"Slippage: ${slippage_amount}")
    print(f"Execution Price: ${execution_price}")

    # Process partial fill
    transaction = blotter.process_partial_fill(
        order=order,
        fill_amount=actual_fill,
        fill_price=execution_price
    )

    print(f"\n✓ Partial Fill Executed")
    print(f"  Transaction ID: {transaction.id}")
    print(f"  Fill Amount: {transaction.amount}")
    print(f"  Fill Price: ${transaction.price}")
    print(f"  Commission: ${transaction.commission}")
    print(f"  Total Cost: ${transaction.total_cost}")

    # Track fill
    order_tracker.record_fill(
        order_id=order.id,
        fill_amount=transaction.amount,
        fill_price=transaction.price
    )

    # Update order status
    print(f"\nOrder Status After Partial Fill:")
    print(f"  Filled: {order.filled}")
    print(f"  Remaining: {order.remaining}")
    print(f"  Average Fill Price: ${order.filled_price}")

# ============================================================
# STEP 5: Market Data Bar 3 - Complete Remaining Fill
# ============================================================

print("\n" + "=" * 60)
print("STEP 5: BAR 3 - COMPLETE REMAINING FILL")
print("=" * 60)

current_time += timedelta(minutes=1)
blotter.set_current_dt(current_time)

# Market data - higher volume allows complete fill
bar_data = {
    'close': Decimal("149.75"),
    'volume': Decimal("200000")
}

print(f"Time: {current_time}")
print(f"Market Price: ${bar_data['close']}")
print(f"Bar Volume: {bar_data['volume']}")
print(f"Remaining to Fill: {order.remaining}")

if order.remaining > Decimal("0"):
    # Calculate fill for remaining
    max_volume_share = bar_data['volume'] * fill_model.volume_share_limit
    potential_fill = min(order.remaining, max_volume_share)
    fill_ratio = fill_model.calculate_fill_ratio(order, bar_data)
    actual_fill = min(order.remaining, potential_fill * fill_ratio)

    print(f"Max Volume Share: {max_volume_share}")
    print(f"Potential Fill: {potential_fill}")
    print(f"Fill Ratio: {float(fill_ratio):.2%}")
    print(f"Actual Fill: {actual_fill}")

    # Calculate execution price with slippage
    execution_price = blotter.slippage_model.calculate(order, bar_data['close'])

    # Process final fill
    transaction = blotter.process_partial_fill(
        order=order,
        fill_amount=actual_fill,
        fill_price=execution_price
    )

    print(f"\n✓ Final Fill Executed")
    print(f"  Fill Amount: {transaction.amount}")
    print(f"  Fill Price: ${transaction.price}")
    print(f"  Commission: ${transaction.commission}")

    # Track fill
    order_tracker.record_fill(
        order_id=order.id,
        fill_amount=transaction.amount,
        fill_price=transaction.price
    )

    # Check if fully filled
    is_fully_filled = order_tracker.is_fully_filled(order.id)
    print(f"\nOrder Fully Filled: {is_fully_filled}")
    print(f"Order Remaining: {order.remaining}")

# ============================================================
# STEP 6: Review Complete Execution
# ============================================================

print("\n" + "=" * 60)
print("STEP 6: EXECUTION SUMMARY")
print("=" * 60)

# Get fill history
fill_history = order_tracker.get_fill_history(order.id)
print(f"Number of Fills: {len(fill_history)}")

print("\nFill History:")
for i, fill in enumerate(fill_history, 1):
    print(f"  Fill {i}:")
    print(f"    Amount: {fill['amount']}")
    print(f"    Price: ${fill['price']}")
    print(f"    Timestamp: {fill['timestamp']}")

# Calculate VWAP
vwap = order_tracker.calculate_vwap(order.id)
print(f"\nVolume-Weighted Average Price: ${vwap}")

# Get all transactions
all_transactions = blotter.get_transactions()
print(f"\nTotal Transactions in Blotter: {len(all_transactions)}")

# Calculate total costs
total_commission = sum(t.commission for t in all_transactions)
total_slippage = sum(t.slippage for t in all_transactions)
total_cost = sum(t.total_cost for t in all_transactions)

print(f"\nTotal Commission: ${total_commission}")
print(f"Total Slippage: ${total_slippage}")
print(f"Total Cost: ${total_cost}")

# Verify order is no longer open
open_orders = blotter.get_open_orders(aapl)
print(f"\nOpen Orders for AAPL: {len(open_orders)}")

print("\n" + "=" * 60)
print("EXECUTION PIPELINE COMPLETE")
print("=" * 60)
```

---

## Component Integration Details

### 1. Order Submission → Blotter

**Flow**:
```python
strategy → order() → blotter.order() → DecimalOrder created → tracked in open_orders
```

**Key Points**:
- Blotter validates parameters
- Creates `DecimalOrder` object
- Adds to tracking dictionaries
- Returns order ID

### 2. Order Trigger Checking

**Flow**:
```python
order.check_triggers(market_price, current_dt) → updates order.triggered
```

**Logic** (from `rustybt/finance/decimal/order.py`):
- **Market orders**: Always triggered
- **Limit orders**: Triggered when price ≤ limit (buy) or price ≥ limit (sell)
- **Stop orders**: Triggered when price ≤ stop (sell) or price ≥ stop (buy)
- **Stop-limit orders**: Two-step trigger (stop → limit)

### 3. Latency Application

**Flow**:
```python
latency_model.calculate_latency(order) → returns delay in milliseconds
```

**Models**:
- `FixedLatencyModel`: Constant delay
- `RandomLatencyModel`: Uniform random delay
- `HistoricalLatencyModel`: Realistic delay from historical data
- `CompositeLatencyModel`: Combines multiple sources

### 4. Partial Fill Calculation

**Flow**:
```python
fill_model.calculate_fill_ratio(order, bar_data) → returns ratio (0.0 to 1.0)
actual_fill = order.remaining * fill_ratio
```

**Constraints**:
- Limited by volume (`volume * volume_share_limit`)
- Limited by order remaining
- Adjusted by fill model behavior

### 5. Slippage Calculation

**Flow**:
```python
slippage_model.calculate(order, market_price) → returns execution_price
```

**Impact**:
- **Buy orders**: `execution_price > market_price` (pay more)
- **Sell orders**: `execution_price < market_price` (receive less)
- Magnitude depends on slippage model

### 6. Commission Calculation

**Flow**:
```python
commission_model.calculate(order, fill_price, fill_amount) → returns commission
```

**Models**:
- `PerShareCommission`: `cost_per_share * fill_amount`
- `PerTradeCommission`: Flat fee per trade
- `PerDollarCommission`: `cost_per_dollar * (fill_price * fill_amount)`

### 7. Transaction Creation

**Flow**:
```python
create_decimal_transaction(order_id, asset, dt, price, amount, commission) → DecimalTransaction
```

**Records**:
- Execution price (with slippage)
- Fill amount
- Commission charged
- Timestamp
- Asset

### 8. Order Status Update

**Flow**:
```python
order.filled += fill_amount
if order.remaining == 0:
    remove from open_orders
    status = FILLED
else:
    status = PARTIALLY_FILLED
```

---

## Execution Realism: Configuration Guide

### Conservative (Pessimistic) Configuration

For worst-case scenario testing:

```python
from decimal import Decimal
from rustybt.finance.decimal.blotter import DecimalBlotter
from rustybt.finance.decimal.commission import PerShareCommission
from rustybt.finance.decimal.slippage import VolumeShareSlippage
from rustybt.finance.execution import (
    RandomLatencyModel,
    ConservativeFillModel
)

# Conservative execution pipeline
conservative_blotter = DecimalBlotter(
    commission_model=PerShareCommission(
        cost_per_share=Decimal("0.01"),  # High commission
        min_cost=Decimal("5.00")
    ),
    slippage_model=VolumeShareSlippage(
        volume_limit=Decimal("0.01"),  # Strict 1% limit
        price_impact=Decimal("0.2")     # High price impact
    )
)

latency_model = RandomLatencyModel(
    min_latency_ms=100.0,  # Slow
    max_latency_ms=500.0,
    seed=42
)

fill_model = ConservativeFillModel()  # 30-50% fills

print("Conservative Configuration:")
print("  High commission, high slippage")
print("  Slow latency (100-500ms)")
print("  Conservative fills (30-50%)")
```

### Realistic (Balanced) Configuration

For production backtesting:

```python
balanced_blotter = DecimalBlotter(
    commission_model=PerShareCommission(
        cost_per_share=Decimal("0.005"),  # Typical retail
        min_cost=Decimal("1.00")
    ),
    slippage_model=VolumeShareSlippage(
        volume_limit=Decimal("0.025"),  # Reasonable 2.5%
        price_impact=Decimal("0.1")
    )
)

latency_model = HistoricalLatencyModel(
    latency_data=historical_latency_df  # From real data
)

fill_model = BalancedFillModel()  # 60-80% fills

print("Balanced Configuration:")
print("  Realistic commission and slippage")
print("  Historical latency patterns")
print("  Balanced fills (60-80%)")
```

### Aggressive (Optimistic) Configuration

For best-case scenario testing:

```python
aggressive_blotter = DecimalBlotter(
    commission_model=PerShareCommission(
        cost_per_share=Decimal("0.001"),  # Institutional rates
        min_cost=Decimal("0.50")
    ),
    slippage_model=FixedBasisPointsSlippage(
        basis_points=Decimal("1")  # Minimal slippage
    )
)

latency_model = FixedLatencyModel(
    latency_ms=10.0  # Very fast
)

fill_model = AggressiveFillModel()  # 90-100% fills

print("Aggressive Configuration:")
print("  Low commission, low slippage")
print("  Fast latency (10ms)")
print("  Aggressive fills (90-100%)")
```

---

## Best Practices

### ✅ DO

1. **Use Realistic Models**: Configure execution models based on your trading style
   ```python
   # Retail trader
   blotter = DecimalBlotter(
       commission_model=PerShareCommission(Decimal("0.005")),
       slippage_model=VolumeShareSlippage(
           volume_limit=Decimal("0.025"),
           price_impact=Decimal("0.1")
       )
   )
   ```

2. **Test Multiple Scenarios**: Run backtests with conservative, balanced, and aggressive configs
   ```python
   results = {
       'conservative': backtest(strategy, conservative_config),
       'balanced': backtest(strategy, balanced_config),
       'aggressive': backtest(strategy, aggressive_config)
   }
   ```

3. **Track Execution Quality**: Monitor fill rates, slippage, and latency
   ```python
   transactions = blotter.get_transactions()
   avg_slippage = sum(t.slippage for t in transactions) / len(transactions)
   fill_rate = sum(1 for t in transactions) / len(orders_submitted)
   ```

4. **Validate Large Orders**: Use volume-based fill models for large orders
   ```python
   if order_size > (daily_volume * Decimal("0.01")):
       # Use conservative fill model for large orders
       fill_model = VolumeBasedFillModel(volume_share_limit=Decimal("0.01"))
   ```

5. **Document Execution Assumptions**: Record model choices in backtest metadata
   ```python
   backtest_config = {
       'commission': 'PerShare($0.005)',
       'slippage': 'VolumeShare(2.5%, impact=0.1)',
       'latency': 'Historical(NYSE)',
       'fill_model': 'Balanced(60-80%)'
   }
   ```

### ❌ DON'T

1. **Don't Use Zero Costs**: Always model transaction costs
   ```python
   # ✗ Wrong
   blotter = DecimalBlotter()  # No costs

   # ✓ Correct
   blotter = DecimalBlotter(
       commission_model=PerShareCommission(Decimal("0.005")),
       slippage_model=FixedBasisPointsSlippage(Decimal("5"))
   )
   ```

2. **Don't Assume Instant Fills**: Model latency for realism
   ```python
   # ✗ Wrong
   # Assumes instant execution

   # ✓ Correct
   latency_model = FixedLatencyModel(latency_ms=50.0)
   ```

3. **Don't Ignore Partial Fills**: Large orders rarely fill completely
   ```python
   # ✓ Correct
   fill_model = VolumeBasedFillModel(
       volume_share_limit=Decimal("0.025")
   )
   ```

4. **Don't Over-Optimize on Aggressive Config**: Test with conservative config too
   ```python
   # Test strategy profitability across execution scenarios
   if conservative_sharpe < 1.0:
       # Strategy may not be robust to execution costs
   ```

5. **Don't Forget Order Book Impact**: Large orders move prices
   ```python
   # Use price impact slippage for large orders
   slippage_model = VolumeShareSlippage(
       volume_limit=Decimal("0.025"),
       price_impact=Decimal("0.1")  # 10% of volume share
   )
   ```

---

## Related Documentation

- [Order Types](../order-types.md) - All supported order types (Market, Limit, Stop, etc.)
- [DecimalBlotter](./decimal-blotter.md) - Order management system
- [Latency Models](./latency-models.md) - Execution latency simulation
- [Partial Fill Models](./partial-fills.md) - Partial fill behavior
- [Slippage Models](../transaction-costs/slippage.md) - Price slippage modeling
- [Commission Models](../transaction-costs/commissions.md) - Transaction costs

---

## Summary

The **Execution Pipeline** integrates multiple components to provide production-grade order execution simulation:

1. **Order submission** through `DecimalBlotter`
2. **Trigger checking** for conditional orders (stop/limit)
3. **Latency application** to model execution delays
4. **Partial fill calculation** based on volume and liquidity
5. **Slippage calculation** to model price impact
6. **Commission calculation** for transaction costs
7. **Transaction creation** with complete cost tracking
8. **Order status updates** to reflect fill progress

By combining these components, RustyBT achieves realistic execution simulation that accounts for real-world market microstructure effects.
