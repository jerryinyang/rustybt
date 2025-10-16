# Order Status & Tracking

**Module**: `rustybt.finance.order`, `rustybt.finance.decimal.order`
**Source**: `rustybt/finance/order.py`, `rustybt/finance/decimal/order.py`
**Verified**: 2025-10-16

## Overview

RustyBT provides comprehensive order status tracking throughout the complete order lifecycle. Every order is tracked from submission through final disposition (filled, cancelled, or rejected) with detailed state information at each step.

**Key Features**:
- **Status States**: 7 distinct order states with clear transitions
- **Fill Tracking**: Partial and complete fill monitoring
- **Commission Tracking**: Cumulative commission on fills
- **Price Tracking**: Limit/stop prices and actual fill prices
- **Advanced Order Tracking**: Trailing stops, OCO, bracket orders

---

## ORDER_STATUS Enum

**Source**: `rustybt/finance/order.py:23-35`

```python
from rustybt.finance.order import ORDER_STATUS

ORDER_STATUS = IntEnum(
    "ORDER_STATUS",
    [
        "OPEN",              # 0 - Order placed, awaiting fill
        "FILLED",            # 1 - Order completely filled
        "CANCELLED",         # 2 - Order cancelled (user action)
        "REJECTED",          # 3 - Order rejected (validation failed)
        "HELD",              # 4 - Order held (pending approval)
        "TRIGGERED",         # 5 - Stop order triggered
        "PARTIALLY_FILLED",  # 6 - Partial fill, still open
    ],
    start=0,
)
```

### Status Definitions

| Status | Value | Description | Terminal? |
|--------|-------|-------------|-----------|
| **OPEN** | 0 | Order submitted and active, no fills yet | No |
| **FILLED** | 1 | Order completely filled | Yes |
| **CANCELLED** | 2 | Order cancelled by user or system | Yes |
| **REJECTED** | 3 | Order rejected due to validation failure | Yes |
| **HELD** | 4 | Order held pending approval (regulatory/broker) | No |
| **TRIGGERED** | 5 | Stop order trigger condition met | No |
| **PARTIALLY_FILLED** | 6 | Order partially filled, remaining amount still active | No |

**Terminal States**: Order lifecycle ends (FILLED, CANCELLED, REJECTED)
**Active States**: Order still processing (OPEN, HELD, TRIGGERED, PARTIALLY_FILLED)

---

## Order Class

**Source**: `rustybt/finance/order.py:45`

### Base Order Attributes

```python
from rustybt.finance.order import Order

# Order attributes (verified from __slots__ lines 49-74)
order.id                    # str - Unique order identifier (UUID hex)
order.dt                    # datetime - Last update timestamp
order.created               # datetime - Order creation timestamp
order.asset                 # Asset - Asset being traded
order.amount                # int/Decimal - Order quantity (+ = buy, - = sell)
order.filled                # int/Decimal - Quantity filled so far
order.commission            # float/Decimal - Commission paid so far
order.stop                  # float/Decimal - Stop price (if applicable)
order.limit                 # float/Decimal - Limit price (if applicable)
order.stop_reached          # bool - Stop price has been hit
order.limit_reached         # bool - Limit price has been reached
order.direction             # int - 1 (buy) or -1 (sell)
order.broker_order_id       # str - Broker's order ID (live trading)
order.reason                # str - Rejection/cancellation reason
```

### Advanced Order Type Attributes

```python
# Trailing Stop Orders (source lines 67-73)
order.trail_amount          # Decimal - Absolute dollar trailing amount
order.trail_percent         # Decimal - Percentage trailing amount
order.is_trailing_stop      # bool - True if trailing stop order
order.trailing_highest_price  # Decimal - Highest price seen (for trailing)
order.trailing_lowest_price   # Decimal - Lowest price seen (for trailing)

# Linked Orders (OCO, Bracket)
order.linked_order_ids      # list[str] - Linked order IDs
order.parent_order_id       # str - Parent order ID (for bracket children)
```

---

## DecimalOrder Class

**Source**: `rustybt/finance/decimal/order.py:37`

```python
from rustybt.finance.decimal.order import DecimalOrder

class DecimalOrder(Order):
    """Order with Decimal precision for prices and quantities."""
```

### DecimalOrder Enhancements

**Key Differences from Base Order**:
- **Decimal Precision**: All prices and quantities use `Decimal` type
- **Fractional Shares**: Supports fractional quantities (e.g., `Decimal("0.001")`)
- **Precision Validation**: Validates precision matches asset class requirements
- **Crypto Support**: Native support for cryptocurrency fractional units

### DecimalOrder Constructor

**Source**: `rustybt/finance/decimal/order.py:87-126`

```python
order = DecimalOrder(
    dt=datetime.now(),
    asset=asset,
    amount=Decimal("100.5"),
    order_type="limit",
    stop=None,
    limit=Decimal("150.00"),
    filled=None,               # Defaults to Decimal("0")
    commission=None,           # Defaults to Decimal("0")
    id=None,                   # Auto-generated if None
    trail_amount=None,         # For trailing stops
    trail_percent=None,        # For trailing stops
    linked_order_ids=None,     # For OCO orders
    parent_order_id=None,      # For bracket orders
    config=None                # Uses default DecimalConfig
)
```

### Example: Creating Orders

```python
from decimal import Decimal
from datetime import datetime
from rustybt.assets import Equity
from rustybt.finance.decimal.order import DecimalOrder

# Setup
aapl = Equity(1, exchange='NYSE', symbol='AAPL')
current_time = datetime(2024, 1, 15, 9, 30)

# Example 1: Simple market order
market_order = DecimalOrder(
    dt=current_time,
    asset=aapl,
    amount=Decimal("100"),
    order_type="market"
)

print(f"Order ID: {market_order.id}")
print(f"Status: {market_order.status}")
print(f"Amount: {market_order.amount}")
print(f"Filled: {market_order.filled}")
print(f"Remaining: {market_order.remaining}")

# Example 2: Limit order
limit_order = DecimalOrder(
    dt=current_time,
    asset=aapl,
    amount=Decimal("100"),
    order_type="limit",
    limit=Decimal("150.00")
)

# Example 3: Stop-loss order
stop_order = DecimalOrder(
    dt=current_time,
    asset=aapl,
    amount=Decimal("-100"),  # Sell
    order_type="stop",
    stop=Decimal("145.00")
)

# Example 4: Fractional crypto order
btc = Equity(2, exchange='CRYPTO', symbol='BTC')
crypto_order = DecimalOrder(
    dt=current_time,
    asset=btc,
    amount=Decimal("0.00012345"),  # Fractional BTC
    order_type="market"
)
```

---

## Order Status Properties

### status

Get current order status.

```python
@property
def status(self) -> ORDER_STATUS:
    """Current order status enum value."""
    return self._status
```

**Source**: `rustybt/finance/order.py` (property method)

### Example: Checking Order Status

```python
from rustybt.finance.order import ORDER_STATUS

# Check specific status
if order.status == ORDER_STATUS.OPEN:
    print("Order is open and active")

if order.status == ORDER_STATUS.FILLED:
    print("Order completely filled")

if order.status == ORDER_STATUS.CANCELLED:
    print("Order was cancelled")

# Check if order is in terminal state
terminal_states = {ORDER_STATUS.FILLED, ORDER_STATUS.CANCELLED, ORDER_STATUS.REJECTED}
if order.status in terminal_states:
    print("Order lifecycle complete")

# Check if order is still active
active_states = {
    ORDER_STATUS.OPEN,
    ORDER_STATUS.HELD,
    ORDER_STATUS.TRIGGERED,
    ORDER_STATUS.PARTIALLY_FILLED
}
if order.status in active_states:
    print("Order still processing")
```

### remaining

Get remaining quantity to be filled.

```python
@property
def remaining(self) -> Decimal:
    """Quantity remaining to be filled."""
    return self.amount - self.filled
```

**Source**: `rustybt/finance/decimal/order.py` (property method)

### Example: Tracking Fill Progress

```python
from decimal import Decimal

# Create order
order = DecimalOrder(
    dt=datetime.now(),
    asset=aapl,
    amount=Decimal("1000")
)

print(f"Original Amount: {order.amount}")
print(f"Filled: {order.filled}")
print(f"Remaining: {order.remaining}")  # 1000

# After partial fill
order.filled = Decimal("300")
print(f"\nAfter 300 shares filled:")
print(f"  Filled: {order.filled}")
print(f"  Remaining: {order.remaining}")  # 700

# After another partial fill
order.filled = Decimal("700")
print(f"\nAfter 700 total shares filled:")
print(f"  Filled: {order.filled}")
print(f"  Remaining: {order.remaining}")  # 300

# After complete fill
order.filled = Decimal("1000")
print(f"\nAfter complete fill:")
print(f"  Filled: {order.filled}")
print(f"  Remaining: {order.remaining}")  # 0
print(f"  Fully filled: {order.remaining == Decimal('0')}")
```

### open

Check if order is open (unfilled or partially filled).

```python
@property
def open(self) -> bool:
    """True if order has quantity remaining."""
    return self.remaining != Decimal("0")
```

**Source**: `rustybt/finance/decimal/order.py` (property method)

### Example: Order Open Status

```python
# New order - open
order = DecimalOrder(
    dt=datetime.now(),
    asset=aapl,
    amount=Decimal("100")
)
assert order.open  # True

# After partial fill - still open
order.filled = Decimal("50")
assert order.open  # True
assert order.remaining == Decimal("50")

# After complete fill - not open
order.filled = Decimal("100")
assert not order.open  # False
assert order.remaining == Decimal("0")
```

---

## Order Status State Machine

### Status Transitions

```
┌─────────────────────────────────────────────────────────────┐
│                       ORDER CREATED                          │
│                      (constructor)                           │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │      OPEN       │ ◄────────────┐
                  │   (initial)     │              │
                  └────┬─────┬──────┘              │
                       │     │                     │
       ┌───────────────┘     └───────────────┐    │
       │                                     │    │
       ▼                                     ▼    │
┌─────────────┐                      ┌─────────────┐
│  TRIGGERED  │                      │    HELD     │
│ (stop hit)  │                      │ (pending)   │
└──────┬──────┘                      └──────┬──────┘
       │                                    │
       └────────────────┬───────────────────┘
                        │
                        ▼
              ┌──────────────────┐
              │ PARTIALLY_FILLED │ ──────────┐
              │ (some filled)    │           │ More fills
              └──────┬───────────┘           │
                     │                       │
         ┌───────────┼───────────┬───────────┘
         │           │           │
         ▼           ▼           ▼
  ┌───────────┐ ┌─────────┐ ┌──────────┐
  │  FILLED   │ │CANCELLED│ │ REJECTED │
  │(complete) │ │ (user)  │ │ (system) │
  └───────────┘ └─────────┘ └──────────┘
     TERMINAL     TERMINAL     TERMINAL
```

### Example: Complete Lifecycle

```python
from decimal import Decimal
from datetime import datetime, timedelta
from rustybt.finance.order import ORDER_STATUS
from rustybt.finance.decimal.order import DecimalOrder
from rustybt.assets import Equity

# Setup
aapl = Equity(1, exchange='NYSE', symbol='AAPL')
order_time = datetime(2024, 1, 15, 9, 30)

# ============================================
# STATE 1: OPEN (initial)
# ============================================
order = DecimalOrder(
    dt=order_time,
    asset=aapl,
    amount=Decimal("1000"),
    order_type="stop",
    stop=Decimal("145.00")
)

print("STATE 1: OPEN")
print(f"  Status: {order.status.name}")  # OPEN
print(f"  Filled: {order.filled}")        # 0
print(f"  Remaining: {order.remaining}")  # 1000
print(f"  Open: {order.open}")            # True

# ============================================
# STATE 2: TRIGGERED (stop price hit)
# ============================================
order_time += timedelta(minutes=5)
order.dt = order_time

# Stop price reached
market_price = Decimal("144.50")
order.check_triggers(market_price, order_time)

# Update status to TRIGGERED
if order.stop_reached and not order.triggered:
    order._status = ORDER_STATUS.TRIGGERED
    order.triggered = True

print("\nSTATE 2: TRIGGERED")
print(f"  Status: {order.status.name}")  # TRIGGERED
print(f"  Stop Reached: {order.stop_reached}")  # True
print(f"  Filled: {order.filled}")        # 0
print(f"  Remaining: {order.remaining}")  # 1000

# ============================================
# STATE 3: PARTIALLY_FILLED
# ============================================
order_time += timedelta(seconds=50)
order.dt = order_time

# Partial fill
order.filled = Decimal("400")
order._status = ORDER_STATUS.PARTIALLY_FILLED
order.filled_price = Decimal("144.45")

print("\nSTATE 3: PARTIALLY_FILLED")
print(f"  Status: {order.status.name}")  # PARTIALLY_FILLED
print(f"  Filled: {order.filled}")        # 400
print(f"  Remaining: {order.remaining}")  # 600
print(f"  Open: {order.open}")            # True

# ============================================
# STATE 4: PARTIALLY_FILLED (more fills)
# ============================================
order_time += timedelta(seconds=30)
order.dt = order_time

# Another partial fill
order.filled = Decimal("800")
# Update weighted average fill price
old_value = Decimal("400") * Decimal("144.45")
new_value = Decimal("400") * Decimal("144.40")
order.filled_price = (old_value + new_value) / Decimal("800")

print("\nSTATE 4: PARTIALLY_FILLED (more fills)")
print(f"  Status: {order.status.name}")  # PARTIALLY_FILLED
print(f"  Filled: {order.filled}")        # 800
print(f"  Remaining: {order.remaining}")  # 200
print(f"  Avg Fill Price: ${order.filled_price}")

# ============================================
# STATE 5: FILLED (complete)
# ============================================
order_time += timedelta(seconds=20)
order.dt = order_time

# Final fill
order.filled = Decimal("1000")
order._status = ORDER_STATUS.FILLED
# Update weighted average fill price
old_value = Decimal("800") * order.filled_price
new_value = Decimal("200") * Decimal("144.50")
order.filled_price = (old_value + new_value) / Decimal("1000")

print("\nSTATE 5: FILLED")
print(f"  Status: {order.status.name}")  # FILLED
print(f"  Filled: {order.filled}")        # 1000
print(f"  Remaining: {order.remaining}")  # 0
print(f"  Open: {order.open}")            # False
print(f"  Final Avg Fill Price: ${order.filled_price}")

# Verify terminal state
terminal_states = {ORDER_STATUS.FILLED, ORDER_STATUS.CANCELLED, ORDER_STATUS.REJECTED}
is_terminal = order.status in terminal_states
print(f"  Terminal State: {is_terminal}")  # True
```

---

## Order Cancellation

### cancel()

Mark order as cancelled.

**Source**: `rustybt/finance/decimal/order.py` (method)

```python
def cancel(self, reason: str = "") -> None:
    """Cancel order.

    Args:
        reason: Cancellation reason
    """
    self._status = ORDER_STATUS.CANCELLED
    self.reason = reason
```

### Example: Cancelling Orders

```python
from decimal import Decimal
from rustybt.finance.order import ORDER_STATUS

# Create order
order = DecimalOrder(
    dt=datetime.now(),
    asset=aapl,
    amount=Decimal("100"),
    order_type="limit",
    limit=Decimal("150.00")
)

# Cancel order
order.cancel(reason="User requested cancellation")

print(f"Status: {order.status.name}")  # CANCELLED
print(f"Reason: {order.reason}")
print(f"Open: {order.open}")  # False if fully cancelled

# Check terminal state
assert order.status == ORDER_STATUS.CANCELLED
```

### Example: Cancel and Replace

```python
from decimal import Decimal
from rustybt.finance.decimal.blotter import DecimalBlotter

blotter = DecimalBlotter()
blotter.set_current_dt(datetime.now())

# Place original order
original_id = blotter.order(
    asset=aapl,
    amount=Decimal("100"),
    order_type="limit",
    limit_price=Decimal("150.00")
)

# Market moved - cancel and replace
blotter.cancel_order(original_id)

# Place new order with adjusted price
new_id = blotter.order(
    asset=aapl,
    amount=Decimal("100"),
    order_type="limit",
    limit_price=Decimal("149.50")  # More aggressive
)

print(f"Cancelled: {original_id}")
print(f"New Order: {new_id}")
```

---

## Order Rejection

### reject()

Mark order as rejected.

**Source**: `rustybt/finance/decimal/order.py` (method)

```python
def reject(self, reason: str = "") -> None:
    """Reject order.

    Args:
        reason: Rejection reason
    """
    self._status = ORDER_STATUS.REJECTED
    self.reason = reason
```

### Example: Order Rejection

```python
from rustybt.finance.decimal.order import InvalidQuantityError

# Example 1: Validation rejection
try:
    order = DecimalOrder(
        dt=datetime.now(),
        asset=aapl,
        amount=Decimal("0")  # Invalid!
    )
except InvalidQuantityError:
    print("Order rejected: Zero quantity")

# Example 2: Manual rejection
order = DecimalOrder(
    dt=datetime.now(),
    asset=aapl,
    amount=Decimal("100")
)

# Reject due to insufficient funds
order.reject(reason="Insufficient buying power")

print(f"Status: {order.status.name}")  # REJECTED
print(f"Reason: {order.reason}")
```

---

## Fill Tracking

### Example: Tracking Partial Fills

```python
from decimal import Decimal
from rustybt.finance.decimal.order import DecimalOrder

# Create large order
order = DecimalOrder(
    dt=datetime.now(),
    asset=aapl,
    amount=Decimal("10000")
)

print("ORDER FILL TRACKING")
print("=" * 50)

# Track fills
fills = []

# Fill 1: 2000 shares @ $150.00
fill_1 = {
    'amount': Decimal("2000"),
    'price': Decimal("150.00"),
    'timestamp': datetime.now()
}
order.filled += fill_1['amount']
order.filled_price = fill_1['price']
fills.append(fill_1)

print(f"\nFill 1:")
print(f"  Amount: {fill_1['amount']}")
print(f"  Price: ${fill_1['price']}")
print(f"  Filled: {order.filled}")
print(f"  Remaining: {order.remaining}")
print(f"  % Filled: {float(order.filled / order.amount) * 100:.1f}%")

# Fill 2: 3000 shares @ $150.10
fill_2 = {
    'amount': Decimal("3000"),
    'price': Decimal("150.10"),
    'timestamp': datetime.now()
}
# Update filled
previous_filled = order.filled
order.filled += fill_2['amount']
# Update weighted average fill price
old_value = previous_filled * order.filled_price
new_value = fill_2['amount'] * fill_2['price']
order.filled_price = (old_value + new_value) / order.filled
fills.append(fill_2)

print(f"\nFill 2:")
print(f"  Amount: {fill_2['amount']}")
print(f"  Price: ${fill_2['price']}")
print(f"  Filled: {order.filled}")
print(f"  Remaining: {order.remaining}")
print(f"  % Filled: {float(order.filled / order.amount) * 100:.1f}%")
print(f"  Avg Fill Price: ${order.filled_price}")

# Fill 3: 5000 shares @ $150.05
fill_3 = {
    'amount': Decimal("5000"),
    'price': Decimal("150.05"),
    'timestamp': datetime.now()
}
previous_filled = order.filled
order.filled += fill_3['amount']
old_value = previous_filled * order.filled_price
new_value = fill_3['amount'] * fill_3['price']
order.filled_price = (old_value + new_value) / order.filled
fills.append(fill_3)

print(f"\nFill 3:")
print(f"  Amount: {fill_3['amount']}")
print(f"  Price: ${fill_3['price']}")
print(f"  Filled: {order.filled}")
print(f"  Remaining: {order.remaining}")
print(f"  % Filled: {float(order.filled / order.amount) * 100:.1f}%")
print(f"  Avg Fill Price: ${order.filled_price}")

# Summary
print(f"\n{'=' * 50}")
print(f"FILL SUMMARY")
print(f"{'=' * 50}")
print(f"Total Fills: {len(fills)}")
print(f"Total Filled: {order.filled} / {order.amount}")
print(f"Final Avg Price: ${order.filled_price}")
print(f"Fully Filled: {order.remaining == Decimal('0')}")
```

---

## Production Usage Patterns

### Pattern 1: Order Status Monitoring

```python
from decimal import Decimal
from rustybt.finance.order import ORDER_STATUS
from rustybt.finance.decimal.blotter import DecimalBlotter

def monitor_orders(blotter: DecimalBlotter):
    """Monitor all order statuses."""
    all_orders = blotter.orders.values()

    # Group by status
    by_status = {}
    for order in all_orders:
        status_name = order.status.name
        if status_name not in by_status:
            by_status[status_name] = []
        by_status[status_name].append(order)

    # Report
    print("ORDER STATUS SUMMARY")
    print("=" * 60)
    for status_name, orders in sorted(by_status.items()):
        print(f"{status_name}: {len(orders)} orders")
        for order in orders:
            fill_pct = float(order.filled / order.amount) * 100
            print(f"  {order.id[:8]}: {order.asset.symbol} "
                  f"{order.filled}/{order.amount} ({fill_pct:.1f}%)")

# Usage:
blotter = DecimalBlotter()
# ... place orders ...
monitor_orders(blotter)
```

### Pattern 2: Order Lifecycle Callbacks

```python
from rustybt.finance.order import ORDER_STATUS

class OrderLifecycleTracker:
    """Track order lifecycle with callbacks."""

    def __init__(self):
        self.callbacks = {
            ORDER_STATUS.OPEN: [],
            ORDER_STATUS.TRIGGERED: [],
            ORDER_STATUS.PARTIALLY_FILLED: [],
            ORDER_STATUS.FILLED: [],
            ORDER_STATUS.CANCELLED: [],
            ORDER_STATUS.REJECTED: []
        }

    def on_status_change(self, status: ORDER_STATUS, callback):
        """Register callback for status change."""
        self.callbacks[status].append(callback)

    def notify(self, order):
        """Notify callbacks of order status."""
        for callback in self.callbacks[order.status]:
            callback(order)

# Usage:
tracker = OrderLifecycleTracker()

# Register callbacks
tracker.on_status_change(
    ORDER_STATUS.FILLED,
    lambda o: print(f"✓ Order {o.id[:8]} filled at ${o.filled_price}")
)

tracker.on_status_change(
    ORDER_STATUS.CANCELLED,
    lambda o: print(f"✗ Order {o.id[:8]} cancelled: {o.reason}")
)

tracker.on_status_change(
    ORDER_STATUS.PARTIALLY_FILLED,
    lambda o: print(f"◐ Order {o.id[:8]} {float(o.filled/o.amount)*100:.1f}% filled")
)

# Notify on order updates
# tracker.notify(order)
```

### Pattern 3: Order Quality Metrics

```python
from decimal import Decimal

def calculate_order_quality_metrics(order):
    """Calculate quality metrics for filled order."""
    if order.status != ORDER_STATUS.FILLED:
        raise ValueError("Order must be fully filled")

    # Metrics
    metrics = {
        'order_id': order.id,
        'asset': order.asset.symbol,
        'total_quantity': float(order.amount),
        'average_fill_price': float(order.filled_price),
        'total_commission': float(order.commission),
        'commission_per_share': float(order.commission / order.amount),
        'time_to_fill': (order.dt - order.created).total_seconds(),
    }

    # If we tracked individual fills, we could calculate:
    # - Price improvement/slippage vs initial quote
    # - Fill rate (quantity / time)
    # - Number of partial fills

    return metrics

# Usage:
# order = blotter.get_order(order_id)
# if order.status == ORDER_STATUS.FILLED:
#     metrics = calculate_order_quality_metrics(order)
#     print(f"Order Quality Metrics:")
#     for key, value in metrics.items():
#         print(f"  {key}: {value}")
```

---

## Best Practices

### ✅ DO

1. **Check Order Status Before Operating**
   ```python
   order = blotter.get_order(order_id)
   if order and order.open:
       # Safe to cancel
       blotter.cancel_order(order_id)
   ```

2. **Track Fill Progress for Large Orders**
   ```python
   if order.status == ORDER_STATUS.PARTIALLY_FILLED:
       fill_pct = float(order.filled / order.amount) * 100
       print(f"Order {fill_pct:.1f}% filled")
   ```

3. **Log Order Status Changes**
   ```python
   logger.info(
       "order_status_changed",
       order_id=order.id,
       old_status=old_status.name,
       new_status=order.status.name,
       filled=str(order.filled),
       remaining=str(order.remaining)
   )
   ```

4. **Handle Terminal States Appropriately**
   ```python
   terminal_states = {ORDER_STATUS.FILLED, ORDER_STATUS.CANCELLED, ORDER_STATUS.REJECTED}
   if order.status in terminal_states:
       # Remove from active tracking
       # Archive for reporting
   ```

5. **Calculate Weighted Average Fill Prices**
   ```python
   # For partial fills
   old_value = previous_filled * old_fill_price
   new_value = new_fill_amount * new_fill_price
   avg_price = (old_value + new_value) / total_filled
   ```

### ❌ DON'T

1. **Don't Modify Status Directly (Use Methods)**
   ```python
   # ✗ Wrong
   order._status = ORDER_STATUS.CANCELLED

   # ✓ Correct
   order.cancel(reason="User requested")
   ```

2. **Don't Assume Orders Fill Immediately**
   ```python
   # ✗ Wrong
   order_id = blotter.order(asset, amount)
   # Immediately assume filled

   # ✓ Correct
   order_id = blotter.order(asset, amount)
   order = blotter.get_order(order_id)
   while order.open:
       # Process market data
       # Check for fills
   ```

3. **Don't Ignore Rejection Reasons**
   ```python
   # ✓ Correct
   if order.status == ORDER_STATUS.REJECTED:
       logger.error(f"Order rejected: {order.reason}")
       # Take corrective action
   ```

4. **Don't Cancel Already-Filled Orders**
   ```python
   # ✓ Correct
   order = blotter.get_order(order_id)
   if order and order.open:
       blotter.cancel_order(order_id)
   ```

5. **Don't Lose Fill Price Information**
   ```python
   # ✓ Correct - Track weighted average
   order.filled_price  # Automatically maintained
   ```

---

## Related Documentation

- [Order Types](../order-types.md) - All supported order types
- [DecimalBlotter](./decimal-blotter.md) - Order management system
- [Execution Pipeline](./execution-pipeline.md) - Complete execution flow
- [Latency Models](./latency-models.md) - Execution timing
- [Partial Fill Models](./partial-fills.md) - Fill simulation

---

## Summary

**Order Status & Tracking** provides:
- **7 Order States**: Complete lifecycle from OPEN through FILLED/CANCELLED/REJECTED
- **Fill Tracking**: Partial and complete fill monitoring with weighted average prices
- **Status Properties**: Convenient properties (`open`, `remaining`, `status`)
- **Lifecycle Management**: Status transitions and terminal state handling
- **Production Patterns**: Monitoring, callbacks, and quality metrics

All order tracking uses `Decimal` precision to ensure accurate financial calculations throughout the order lifecycle.
