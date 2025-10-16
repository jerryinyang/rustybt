# Order Lifecycle and State Transitions

Complete guide to order states, transitions, and lifecycle management in RustyBT.

## Overview

Every order progresses through a series of states from creation to completion. Understanding this lifecycle is crucial for:

- Monitoring order execution
- Handling partial fills
- Managing risk appropriately
- Debugging execution issues

## Order States

```python
from rustybt.finance.order import ORDER_STATUS

# Available states:
ORDER_STATUS.OPEN              # Active, awaiting trigger/fill
ORDER_STATUS.TRIGGERED         # Stop/limit reached, ready to execute
ORDER_STATUS.PARTIALLY_FILLED  # Some shares filled, remainder open
ORDER_STATUS.FILLED            # Completely filled
ORDER_STATUS.CANCELLED         # Cancelled by user or system
ORDER_STATUS.REJECTED          # Rejected due to validation failure
ORDER_STATUS.HELD              # Temporarily held (risk limits)
```

## State Transition Diagram

```
                    ┌─────────┐
                    │  OPEN   │ ◄──── Order created
                    └────┬────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
   ┌─────────┐      ┌──────────┐    ┌──────────┐
   │ REJECTED│      │TRIGGERED │    │   HELD   │
   └─────────┘      └────┬─────┘    └────┬─────┘
   (terminal)            │               │
                         │               │
                         └───────┬───────┘
                                 │
                         ┌───────▼────────┐
                         │ PARTIALLY_FILLED│
                         └───────┬────────┘
                                 │
                    ┌────────────┼────────────┐
                    │            │            │
                    ▼            ▼            ▼
              ┌─────────┐  ┌─────────┐  ┌──────────┐
              │ FILLED  │  │CANCELLED│  │   HELD   │
              └─────────┘  └─────────┘  └────┬─────┘
              (terminal)   (terminal)         │
                                             │
                                     (can return to OPEN)
```

## State Descriptions

### OPEN

Initial state when order is placed.

**Characteristics**:
- Order is active and being monitored
- For market orders: Immediately moves to execution
- For limit/stop orders: Awaits price trigger
- Can transition to: TRIGGERED, PARTIALLY_FILLED, CANCELLED, REJECTED, HELD

**Example**:
```python
order_id = order(asset, 100, style=LimitOrder(150.0))
# Order is now in OPEN state, waiting for price ≤ $150
```

### TRIGGERED

Stop or limit price has been reached; order ready for execution.

**Characteristics**:
- Only applies to stop/limit orders
- Price condition met, execution begins
- Market orders skip this state
- Can transition to: PARTIALLY_FILLED, FILLED, CANCELLED

**Example**:
```python
# Price reaches stop level
# OPEN → TRIGGERED → execution begins
```

**Monitoring**:
```python
def handle_data(self, context, data):
    open_orders = get_open_orders(asset)
    for order in open_orders:
        if order.status == ORDER_STATUS.TRIGGERED:
            print(f"Order {order.id} triggered, executing...")
```

### PARTIALLY_FILLED

Part of the order has filled; remainder still open.

**Characteristics**:
- `order.filled < order.amount`
- Partial fills common in large orders or illiquid markets
- Remaining amount continues execution
- Can transition to: FILLED, CANCELLED, HELD

**Example**:
```python
# Order for 1000 shares, but only 300 available
# State: PARTIALLY_FILLED
# order.amount = 1000
# order.filled = 300
# order.open_amount = 700
```

**Handling Partial Fills**:
```python
def handle_data(self, context, data):
    open_orders = get_open_orders(asset)
    for order in open_orders:
        if order.status == ORDER_STATUS.PARTIALLY_FILLED:
            fill_pct = order.filled / order.amount
            print(f"Order {order.id}: {fill_pct:.1%} filled")

            if fill_pct < 0.5 and self.bars_since_order > 10:
                # Cancel if less than 50% filled after 10 bars
                cancel_order(order)
```

### FILLED

Order completely filled.

**Characteristics**:
- `order.filled == order.amount`
- Terminal state (no further transitions)
- Full commission calculated
- Position updated in portfolio

**Example**:
```python
# All 1000 shares filled
# order.status = FILLED
# order.filled = 1000
# order.amount = 1000
```

**Confirmation**:
```python
def handle_data(self, context, data):
    # Check for completed orders
    for order in context.blotter.orders.values():
        if order.status == ORDER_STATUS.FILLED:
            print(f"Order {order.id} filled at avg price ${order.filled_price:.2f}")
            print(f"Total commission: ${order.commission:.2f}")
```

### CANCELLED

Order cancelled before complete fill.

**Characteristics**:
- Terminal state (no further transitions)
- Can be user-initiated or system-initiated
- Partial fills retain filled shares
- No further execution

**Cancellation Reasons**:
- User explicit cancellation
- OCO partner filled
- Time-in-force expired (GTD)
- Risk limit breached
- Market closed

**Example**:
```python
from rustybt.api import cancel_order, get_open_orders

def handle_data(self, context, data):
    open_orders = get_open_orders(asset)

    for order in open_orders:
        # Cancel stale limit orders after 5 bars
        bars_since_order = (context.datetime - order.dt).days
        if bars_since_order > 5:
            cancel_order(order)
```

### REJECTED

Order rejected due to validation failure.

**Characteristics**:
- Terminal state (no further transitions)
- No fills occurred
- `order.reason` contains rejection reason
- Immediate feedback to strategy

**Common Rejection Reasons**:
```python
# Insufficient funds
order.reason = "INSUFFICIENT_FUNDS: Required $15000, available $10000"

# Invalid price
order.reason = "INVALID_PRICE: Limit price must be positive"

# Position limit
order.reason = "POSITION_LIMIT: Exceeds max position size of 1000 shares"

# Untradeable asset
order.reason = "UNTRADEABLE_ASSET: Asset is halted"
```

**Handling Rejections**:
```python
def handle_data(self, context, data):
    for order in context.blotter.orders.values():
        if order.status == ORDER_STATUS.REJECTED:
            self.log.error(f"Order rejected: {order.reason}")

            # Adjust strategy based on reason
            if "INSUFFICIENT_FUNDS" in order.reason:
                # Reduce position size
                self.max_position_size *= 0.5
```

### HELD

Order temporarily held by risk management system.

**Characteristics**:
- Non-terminal state (can return to OPEN)
- Triggered by risk limits or controls
- No execution while held
- Can transition to: OPEN, CANCELLED

**Hold Reasons**:
- Position limit reached
- Leverage constraint breached
- Pending risk review
- Circuit breaker triggered

**Example**:
```python
# Order held due to position limit
order.status = ORDER_STATUS.HELD
order.reason = "POSITION_LIMIT: Waiting for position to close"

# After position closed, order returns to OPEN
```

## Order Attributes by State

| Attribute | OPEN | TRIGGERED | PARTIALLY_FILLED | FILLED | CANCELLED/REJECTED |
|-----------|------|-----------|------------------|--------|--------------------|
| `id` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `status` | OPEN | TRIGGERED | PARTIALLY_FILLED | FILLED | CANCELLED/REJECTED |
| `filled` | 0 | 0 or partial | > 0 and < amount | = amount | 0 or partial |
| `open_amount` | = amount | = amount | < amount | 0 | 0 or partial |
| `commission` | 0 | 0 or partial | > 0 | final | 0 or partial |
| `stop_reached` | depends | True (if stop) | True (if stop) | True (if stop) | depends |
| `limit_reached` | depends | True (if limit) | True (if limit) | True (if limit) | depends |

## Order Properties

### open_amount

Remaining shares to be filled.

```python
order.open_amount = order.amount - order.filled

# Example:
# amount = 1000
# filled = 300
# open_amount = 700
```

### triggered

Whether order is ready for execution.

```python
# Market order: always True
# Stop order: True if stop_reached
# Limit order: True if limit_reached
# Stop-Limit: True if both conditions met

if order.triggered:
    print("Order ready for execution")
```

### open

Whether order is still active.

```python
if order.open:
    print("Order is still active")
else:
    print("Order is complete (filled, cancelled, or rejected)")
```

## Complete Lifecycle Examples

### Market Order Lifecycle

```python
# t=0: Order placed
order_id = order(asset, 100, style=MarketOrder())
# Status: OPEN → immediately begins execution

# t=1: Sufficient volume available
# Status: OPEN → FILLED
# order.filled = 100
# Commission charged
# Position updated
```

### Limit Order Lifecycle

```python
# t=0: Order placed at $150 limit, current price $155
order_id = order(asset, 100, style=LimitOrder(150.0))
# Status: OPEN (waiting for price ≤ $150)

# t=5: Price drops to $149
# Status: OPEN → TRIGGERED (limit reached)

# t=6: Sufficient volume, order fills
# Status: TRIGGERED → FILLED
```

### Stop-Loss Lifecycle with Partial Fill

```python
# t=0: Order placed, current price $100
order_id = order(asset, -1000, style=StopOrder(95.0))
# Status: OPEN (waiting for price ≤ $95)

# t=10: Price drops to $94
# Status: OPEN → TRIGGERED (stop reached)

# t=11: Only 400 shares available this bar
# Status: TRIGGERED → PARTIALLY_FILLED
# order.filled = 400, order.open_amount = 600

# t=12: 300 more shares filled
# Status: PARTIALLY_FILLED (still)
# order.filled = 700, order.open_amount = 300

# t=13: Final 300 shares filled
# Status: PARTIALLY_FILLED → FILLED
```

### OCO Order Lifecycle

```python
# t=0: Place OCO order
oco_style = OCOOrder(
    LimitOrder(110.0),  # Profit
    StopOrder(90.0)      # Stop
)
order_id = order(asset, -100, style=oco_style)
# Two orders created, both in OPEN state

# t=5: Price rises to $110
# Profit order: OPEN → TRIGGERED → FILLED
# Stop order: OPEN → CANCELLED (partner filled)
```

### Bracket Order Lifecycle

```python
# t=0: Place bracket order
bracket = BracketOrder(
    MarketOrder(),
    stop_loss_price=95.0,
    take_profit_price=110.0
)
order_id = order(asset, 100, style=bracket)
# Entry order: OPEN → FILLED

# t=1: Entry filled, children created
# Stop order: OPEN (linked, parent_order_id set)
# Profit order: OPEN (linked, parent_order_id set)

# t=10: Price hits stop at $95
# Stop order: OPEN → TRIGGERED → FILLED
# Profit order: OPEN → CANCELLED (OCO partner filled)
```

## Monitoring Orders in Strategy

### Get All Open Orders

```python
def handle_data(self, context, data):
    # Get all open orders across all assets
    all_open_orders = context.blotter.open_orders

    for asset, orders in all_open_orders.items():
        print(f"{asset.symbol}: {len(orders)} open orders")
```

### Get Orders for Specific Asset

```python
from rustybt.api import get_open_orders

def handle_data(self, context, data):
    asset_orders = get_open_orders(asset)

    for order in asset_orders:
        print(f"Order {order.id}:")
        print(f"  Status: {order.status.name}")
        print(f"  Filled: {order.filled}/{order.amount}")
        print(f"  Open: {order.open_amount}")
```

### Get Specific Order

```python
def handle_data(self, context, data):
    order_obj = context.blotter.orders.get(order_id)

    if order_obj:
        if order_obj.status == ORDER_STATUS.FILLED:
            print("Order filled successfully")
        elif order_obj.status == ORDER_STATUS.REJECTED:
            print(f"Order rejected: {order_obj.reason}")
```

## Best Practices

### ✅ DO

1. **Monitor Partial Fills**: Don't assume orders fill completely
2. **Check Order Status**: Before placing new orders for same asset
3. **Handle Rejections**: Adjust strategy based on rejection reasons
4. **Cancel Stale Orders**: Remove limit orders that aren't filling
5. **Track Commission**: Account for commission in P&L calculations

### ❌ DON'T

1. **Assume Immediate Fills**: Even market orders may take time
2. **Ignore Partial Fills**: Track order.filled vs order.amount
3. **Re-submit Rejected Orders**: Without addressing rejection reason
4. **Forget About Open Orders**: Monitor and manage actively
5. **Place Duplicate Orders**: Check for existing orders first

## Troubleshooting

### Order Stuck in OPEN

**Symptom**: Limit order remains OPEN for many bars

**Causes**:
- Limit price not reached
- Insufficient volume
- Market moved away from limit

**Solutions**:
```python
# Cancel and replace with market order
cancel_order(order_id)
order(asset, amount, style=MarketOrder())

# Or adjust limit price
cancel_order(order_id)
order(asset, amount, style=LimitOrder(new_price))
```

### Unexpected Partial Fills

**Symptom**: Order partially filled, remainder stuck

**Causes**:
- Low volume
- Large order size
- IOC time-in-force

**Solutions**:
```python
# Break large orders into smaller chunks
chunk_size = 100
for i in range(0, total_amount, chunk_size):
    order(asset, min(chunk_size, total_amount - i))
```

### Order Rejected

**Symptom**: Order immediately rejected

**Solutions**:
```python
# Check rejection reason and fix
if "INSUFFICIENT_FUNDS" in order.reason:
    # Reduce position size or wait for cash

if "INVALID_PRICE" in order.reason:
    # Check stop/limit prices are positive

if "POSITION_LIMIT" in order.reason:
    # Close existing position or reduce order size
```

## Related Documentation

- [Order Types](../order-types.md) - Complete order types reference
- [Blotter Architecture](../execution/blotter.md) - Order management system
- [Transaction Costs](../transaction-costs/slippage.md) - Execution costs
- [Order Examples](examples.md) - Practical order patterns

## Next Steps

1. Review [Order Types](../order-types.md) to understand available orders
2. Study [Blotter Architecture](../execution/blotter.md) for order routing
3. See [Order Examples](examples.md) for practical patterns
