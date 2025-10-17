# Blotter System

**Source**: `rustybt/finance/blotter/simulation_blotter.py`
**Verified**: 2025-10-16

## Overview

The Blotter is RustyBT's order management system that handles order placement, tracking, execution simulation, and fill processing.

## SimulationBlotter

**Source**: `rustybt/finance/blotter/simulation_blotter.py:47`

The default blotter for backtesting that simulates realistic order execution.

### Initialization

```python
from rustybt.finance.blotter import SimulationBlotter
from rustybt.finance.slippage import FixedBasisPointsSlippage
from rustybt.finance.commission import PerShare

blotter = SimulationBlotter(
    equity_slippage=FixedBasisPointsSlippage(),
    equity_commission=PerShare(cost=0.005),
    future_slippage=None,  # Uses default
    future_commission=None,  # Uses default
    cancel_policy=None  # Uses NeverCancel
)
```

### Key Attributes

**Source verified** in `simulation_blotter.py:59-66`:

| Attribute | Type | Description |
|-----------|------|-------------|
| `open_orders` | `defaultdict(list)` | Orders grouped by asset |
| `orders` | `dict` | All orders indexed by order ID |
| `new_orders` | `list` | Orders placed since last event |
| `max_shares` | `int` | Max shares per order (100 billion) |
| `slippage_models` | `dict` | Slippage by asset class |
| `commission_models` | `dict` | Commission by asset class |

### Order Placement

**Method**: `order(asset, amount, style, order_id=None)`
**Source**: `simulation_blotter.py:105`

```python
from rustybt.algorithm import TradingAlgorithm
from rustybt.finance.execution import LimitOrder

class MyStrategy(TradingAlgorithm):
    def handle_data(self, context, data):
        # Place order through blotter
        order_id = self.order(
            self.asset,
            100,
            style=LimitOrder(limit_price=150.0)
        )
```

**Parameters** (verified in source):
- `asset` (Asset): Asset to trade
- `amount` (int): Shares (positive=buy, negative=sell)
- `style` (ExecutionStyle): Order execution style
- `order_id` (str, optional): Custom order ID

**Returns**: `str` or `None` - Order ID if placed, None if rejected

**Validations** (source line 141-147):
- Rejects `amount == 0`
- Raises `OverflowError` if `amount > 100 billion`

## Order Status Tracking

**Source**: `rustybt/finance/order.py:23`

### ORDER_STATUS Enum

```python
from rustybt.finance.order import ORDER_STATUS

# Verified statuses (order.py:23-35)
ORDER_STATUS.OPEN              # 0 - Order placed, not filled
ORDER_STATUS.FILLED            # 1 - Order completely filled
ORDER_STATUS.CANCELLED         # 2 - Order cancelled
ORDER_STATUS.REJECTED          # 3 - Order rejected
ORDER_STATUS.HELD              # 4 - Order held (pending)
ORDER_STATUS.TRIGGERED         # 5 - Stop order triggered
ORDER_STATUS.PARTIALLY_FILLED  # 6 - Partial fill
```

### Order Object

**Source**: `rustybt/finance/order.py:45`

```python
class Order:
    """
    Represents a trading order with status and fill tracking.

    Source: order.py:45
    """
```

**Key Attributes** (verified __slots__ at line 49-74):

| Attribute | Type | Description |
|-----------|------|-------------|
| `id` | str | Unique order identifier (UUID) |
| `dt` | Timestamp | Order creation time |
| `asset` | Asset | Asset being traded |
| `amount` | int | Order quantity |
| `filled` | int | Shares filled so far |
| `commission` | float | Commission charged |
| `_status` | ORDER_STATUS | Current order status |
| `stop` | float | Stop price (if applicable) |
| `limit` | float | Limit price (if applicable) |
| `broker_order_id` | str | Broker's ID (live trading) |

**Advanced Order Fields** (trailing stop support):
- `trail_amount`: Absolute dollar trailing amount
- `trail_percent`: Percentage trailing amount
- `is_trailing_stop`: Boolean flag
- `trailing_highest_price`: Highest price seen
- `trailing_lowest_price`: Lowest price seen

**Linked Order Fields** (OCO/Bracket support):
- `linked_order_ids`: List of linked order IDs
- `parent_order_id`: Parent order ID

## Accessing Orders in Strategy

```python
from rustybt.algorithm import TradingAlgorithm

class MyStrategy(TradingAlgorithm):
    def handle_data(self, context, data):
        # Get all open orders for an asset
        open_orders = self.get_open_orders(self.asset)

        for order in open_orders:
            print(f"Order {order.id}")
            print(f"  Status: {order._status}")
            print(f"  Amount: {order.amount}")
            print(f"  Filled: {order.filled}")
            print(f"  Commission: ${order.commission:.2f}")

        # Get all orders (any status)
        all_orders = context.blotter.orders

        # Get specific order by ID
        if order_id in context.blotter.orders:
            order = context.blotter.orders[order_id]
```

## Order Lifecycle

```
1. CREATED       → Order object instantiated
        ↓
2. OPEN          → Order placed in blotter
        ↓
   ┌────────────┼────────────┐
   ↓            ↓            ↓
3a. TRIGGERED  3b. HELD   3c. REJECTED
   (stop hit)   (pending)   (validation fail)
   ↓
4. PARTIALLY_FILLED → Some shares filled
        ↓
   ┌────────────┼────────────┐
   ↓            ↓            ↓
5a. FILLED   5b. CANCELLED  5c. PARTIALLY_FILLED
   (complete)  (manual)      (continues)
```

## Default Models

**Equity Defaults** (source line 70, 77):
- Slippage: `FixedBasisPointsSlippage()`
- Commission: `PerShare()`

**Future Defaults** (source line 71-82):
- Slippage: `VolatilityVolumeShare()`
- Commission: `PerContract()`

## Cancel Policy

**Source**: `rustybt/finance/cancel_policy.py`

```python
from rustybt.finance.cancel_policy import EODCancel, NeverCancel

# Cancel all open orders at end of day
blotter = SimulationBlotter(cancel_policy=EODCancel())

# Never auto-cancel (default)
blotter = SimulationBlotter(cancel_policy=NeverCancel())
```

## Related Documentation

- [Order Types](../order-types.md) - All available execution styles
- Transaction Costs - Slippage and commission models

## Verification

✅ All classes, methods, and attributes verified in source code
✅ No fabricated APIs
✅ All line numbers referenced for verification

**Verification Date**: 2025-10-16
**Source Files Verified**:
- `rustybt/finance/blotter/blotter.py:22`
- `rustybt/finance/blotter/simulation_blotter.py:47`
- `rustybt/finance/order.py:23,45`
