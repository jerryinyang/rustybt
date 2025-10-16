# Order Types Reference

Complete reference for all order types supported by RustyBT.

## Overview

RustyBT supports a comprehensive range of order types for both simple and sophisticated trading strategies:

- **Basic Orders**: Market, Limit, Stop, Stop-Limit
- **Advanced Orders**: Trailing Stop, OCO (One-Cancels-Other), Bracket
- **Time-in-Force**: GTC, GTD, IOC, FOK

## Order Anatomy

Every order has the following core attributes:

```python
from rustybt.finance.order import Order

order = Order(
    dt=current_time,           # Order creation timestamp
    asset=asset,               # Asset to trade
    amount=100,                # Quantity (positive=buy, negative=sell)
    stop=None,                 # Stop price (optional)
    limit=None,                # Limit price (optional)
    filled=0,                  # Shares filled so far
    commission=0               # Commission charged so far
)
```

### Order Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `id` | str | Unique order identifier (UUID) |
| `dt` | pd.Timestamp | Order creation/update timestamp |
| `asset` | Asset | Asset to trade |
| `amount` | int | Order quantity (+ buy, - sell) |
| `filled` | int | Shares filled so far |
| `commission` | float | Total commission charged |
| `stop` | float | Stop trigger price |
| `limit` | float | Limit price |
| `status` | ORDER_STATUS | Current order state |
| `broker_order_id` | str | Broker's order ID (live trading) |

## Basic Order Types

### Market Order

Execute immediately at current market price.

**Use Case**: When speed is more important than price, or in highly liquid markets.

**Example**:
```python
from rustybt.api import order
from rustybt.finance.execution import MarketOrder

# Buy 100 shares at market price
order(asset, 100, style=MarketOrder())

# Sell 50 shares at market price
order(asset, -50, style=MarketOrder())
```

**Behavior**:
- ✅ Guaranteed execution (in liquid markets)
- ❌ No price protection
- ❌ Subject to slippage in illiquid markets
- ⚡ Immediate fill (simulation) or next available price (live)

**Risk Warning**: ⚠️ Market orders in illiquid assets can fill at significantly worse prices than expected.

### Limit Order

Execute only at specified price or better.

**Use Case**: Control execution price, willing to risk non-execution.

**Example**:
```python
from rustybt.finance.execution import LimitOrder

# Buy at $150 or lower
order(asset, 100, style=LimitOrder(limit_price=150.0))

# Sell at $155 or higher
order(asset, -100, style=LimitOrder(limit_price=155.0))
```

**Behavior**:
- ✅ Price protection guaranteed
- ✅ Reduced slippage
- ❌ May not fill if price doesn't reach limit
- ⏱️ Remains open until filled or cancelled

**Price Logic**:
- **Buy orders**: Fill when market price ≤ limit price
- **Sell orders**: Fill when market price ≥ limit price

### Stop Order

Trigger market order when price reaches stop level.

**Use Case**: Stop-loss protection, breakout strategies.

**Example**:
```python
from rustybt.finance.execution import StopOrder

# Stop-loss: sell if price drops to $95
order(asset, -100, style=StopOrder(stop_price=95.0))

# Buy breakout: buy if price rises to $105
order(asset, 100, style=StopOrder(stop_price=105.0))
```

**Behavior**:
- ⏱️ Dormant until stop price reached
- ⚡ Becomes market order after trigger
- ❌ Subject to slippage after trigger
- ✅ Useful for risk management

**Trigger Logic**:
- **Buy stop**: Triggers when price ≥ stop price
- **Sell stop**: Triggers when price ≤ stop price

**Risk Warning**: ⚠️ Stop orders become market orders and can fill at significantly worse prices in fast-moving markets (slippage).

### Stop-Limit Order

Trigger limit order when price reaches stop level.

**Use Case**: Price protection with stop-loss (but risk of non-execution).

**Example**:
```python
from rustybt.finance.execution import StopLimitOrder

# Sell between $95-$94 if price drops to $95
order(asset, -100, style=StopLimitOrder(
    limit_price=94.0,
    stop_price=95.0
))

# Buy between $105-$106 if price rises to $105
order(asset, 100, style=StopLimitOrder(
    limit_price=106.0,
    stop_price=105.0
))
```

**Behavior**:
- ⏱️ Dormant until stop price reached
- 📋 Becomes limit order after trigger
- ✅ Price protection even after trigger
- ❌ May not fill if price moves too fast

**Trigger Logic**:
- Stop reached → Order becomes limit order
- Limit order rules apply from that point

**Trade-off**: Better price protection than stop order, but lower fill probability.

## Advanced Order Types

### Trailing Stop Order

Stop price automatically adjusts as market moves favorably.

**Use Case**: Protect profits while allowing position to run.

**Example**:
```python
from rustybt.finance.execution import TrailingStopOrder

# Trail by $5 (absolute)
order(asset, -100, style=TrailingStopOrder(trail_amount=5.0))

# Trail by 5% (percentage)
order(asset, -100, style=TrailingStopOrder(trail_percent=0.05))
```

**Behavior**:
- 📈 Stop price follows market favorably
- 🔒 Stop price never widens (one-way ratchet)
- ⚡ Triggers like regular stop order
- ✅ Locks in profits automatically

**Trailing Logic**:

For **sell** orders (closing long position):
```python
# Price moves up → Stop price moves up
stop_price = highest_price_seen - trail_amount
# or
stop_price = highest_price_seen * (1 - trail_percent)
```

For **buy** orders (covering short position):
```python
# Price moves down → Stop price moves down
stop_price = lowest_price_seen + trail_amount
# or
stop_price = lowest_price_seen * (1 + trail_percent)
```

**Example Scenario**:
```python
# Initial price: $100, trailing stop 5%
# Stop starts at: $95 (100 * 0.95)

# Price rises to $110
# Stop adjusts to: $104.50 (110 * 0.95)

# Price rises to $120
# Stop adjusts to: $114 (120 * 0.95)

# Price drops to $115
# Stop stays at: $114 (doesn't widen)

# Price drops to $113.99
# Order triggers! (below $114)
```

**Best Practice**: Use percentage-based trailing stops for volatile assets, fixed-amount for stable assets.

### OCO (One-Cancels-Other) Order

Link two orders; when one fills, the other cancels automatically.

**Use Case**: Set both profit target and stop-loss without risking both filling.

**Example**:
```python
from rustybt.finance.execution import OCOOrder, LimitOrder, StopOrder

# Take profit at $110 OR stop-loss at $90
oco_style = OCOOrder(
    order1_style=LimitOrder(limit_price=110.0),  # Profit target
    order2_style=StopOrder(stop_price=90.0)       # Stop-loss
)

order(asset, -100, style=oco_style)  # Close position
```

**Behavior**:
- 🔗 Two orders created and linked
- ⚡ First to fill wins
- ❌ Other order immediately cancelled
- ✅ Prevents over-execution

**Common Patterns**:

1. **Exit Strategy**:
   ```python
   # Profit at $105 OR stop at $95
   OCOOrder(LimitOrder(105.0), StopOrder(95.0))
   ```

2. **Breakout/Breakdown**:
   ```python
   # Buy breakout at $110 OR sell breakdown at $90
   OCOOrder(
       StopOrder(110.0),  # amount=100 (buy)
       StopOrder(90.0)    # amount=-100 (sell short)
   )
   ```

**Risk Warning**: ⚠️ Ensure both orders are for same quantity and correct direction!

### Bracket Order

Entry order with automatic stop-loss and profit target.

**Use Case**: Enter position with built-in risk management.

**Example**:
```python
from rustybt.finance.execution import BracketOrder, MarketOrder

# Enter at market with 5% stop and 10% target
current_price = 100.0
bracket_style = BracketOrder(
    entry_style=MarketOrder(),
    stop_loss_price=current_price * 0.95,   # $95
    take_profit_price=current_price * 1.10  # $110
)

order(asset, 100, style=bracket_style)
```

**Behavior**:
1. 📨 Entry order placed immediately
2. ⏱️ After entry fills, two child orders created
3. 🔗 Child orders linked as OCO pair
4. ✅ Risk managed from entry

**Order Lifecycle**:
```
Entry Order (Market/Limit)
    │ (fills)
    ▼
Parent Order ID assigned
    │
    ├──> Stop-Loss Order (linked)
    │
    └──> Take-Profit Order (linked)
         │
         └──> OCO relationship
```

**Advanced Example**:
```python
# Enter with limit, exit with stops
bracket_style = BracketOrder(
    entry_style=LimitOrder(limit_price=98.0),  # Enter at $98
    stop_loss_price=93.0,                       # Risk $5
    take_profit_price=108.0                     # Target $10
)
```

**Risk-Reward Ratio**: `(take_profit - entry) / (entry - stop_loss)`

```python
# Example: (108 - 98) / (98 - 93) = 10 / 5 = 2:1 ratio
```

## Time-in-Force Instructions

Control how long order remains active.

### GTC (Good-Till-Cancelled)

Order remains active until filled or explicitly cancelled.

```python
# Order stays open indefinitely
order(asset, 100, style=LimitOrder(150.0))  # GTC is default
```

### GTD (Good-Till-Date)

Order expires at specified date/time.

```python
from rustybt.finance.execution import LimitOrder
import pandas as pd

# Expires end of trading day
order(asset, 100, style=LimitOrder(
    limit_price=150.0,
    time_in_force='GTD',
    expire_date=pd.Timestamp('2024-12-31 16:00:00')
))
```

### IOC (Immediate-Or-Cancel)

Fill immediately what's possible, cancel remainder.

```python
# Fill up to available liquidity, cancel rest
order(asset, 1000, style=LimitOrder(
    limit_price=150.0,
    time_in_force='IOC'
))
```

### FOK (Fill-Or-Kill)

Fill entire order immediately or cancel completely.

```python
# All-or-nothing execution
order(asset, 1000, style=LimitOrder(
    limit_price=150.0,
    time_in_force='FOK'
))
```

## Order Validation

All orders undergo validation before submission:

```python
from rustybt.finance.order import Order

# Validation checks:
# ✓ Asset exists and tradeable
# ✓ Amount is non-zero integer
# ✓ Stop/Limit prices are positive
# ✓ Sufficient buying power (live trading)
# ✓ No conflicting orders (some strategies)
```

### Common Rejection Reasons

| Reason | Description | Solution |
|--------|-------------|----------|
| `INSUFFICIENT_FUNDS` | Not enough cash/margin | Reduce order size |
| `INVALID_PRICE` | Stop/limit price out of bounds | Check price parameters |
| `POSITION_LIMIT` | Exceeds position limit | Reduce order size |
| `UNTRADEABLE_ASSET` | Asset not tradeable | Check asset status |
| `ZERO_AMOUNT` | Order amount is zero | Specify non-zero amount |

## Order Status Tracking

Monitor order status in strategy:

```python
def handle_data(self, context, data):
    # Get all open orders
    open_orders = context.blotter.open_orders

    # Check specific asset
    if asset in open_orders:
        for order in open_orders[asset]:
            print(f"Order {order.id}: {order.status}")
            print(f"  Filled: {order.filled}/{order.amount}")
            print(f"  Commission: ${order.commission:.2f}")
```

## Complete Strategy Example

```python
from rustybt.algorithm import TradingAlgorithm
from rustybt.api import order, symbol, get_open_orders, cancel_order
from rustybt.finance.execution import (
    MarketOrder, LimitOrder, StopOrder, BracketOrder, TrailingStopOrder
)

class AdvancedOrderStrategy(TradingAlgorithm):
    def initialize(self, context):
        self.asset = self.symbol('AAPL')
        self.entry_price = None
        self.position_entered = False

    def handle_data(self, context, data):
        price = data.current(self.asset, 'close')
        position = context.portfolio.positions.get(self.asset)

        # Entry logic
        if not self.position_entered and position is None:
            # Enter with bracket order
            self.entry_price = price
            order(
                self.asset,
                100,
                style=BracketOrder(
                    entry_style=LimitOrder(price * 0.99),  # Limit entry
                    stop_loss_price=price * 0.95,           # 5% stop
                    take_profit_price=price * 1.10          # 10% target
                )
            )
            self.position_entered = True

        # Adjust to trailing stop if position profitable
        elif position is not None and position.amount > 0:
            pnl_pct = (price - self.entry_price) / self.entry_price

            if pnl_pct > 0.05:  # 5% profit
                # Cancel existing orders
                open_orders = get_open_orders(self.asset)
                for open_order in open_orders:
                    cancel_order(open_order)

                # Place trailing stop
                order(
                    self.asset,
                    -position.amount,
                    style=TrailingStopOrder(trail_percent=0.03)
                )
```

## Best Practices

### ✅ DO

1. **Use Limit Orders in Illiquid Markets**: Protect against slippage
2. **Set Realistic Stop-Losses**: Based on asset volatility, not arbitrary percentages
3. **Monitor Order Status**: Don't assume orders filled immediately
4. **Model Transaction Costs**: Include slippage and commissions in backtests
5. **Test Order Logic**: Verify order parameters before live trading

### ❌ DON'T

1. **Place Market Orders for Large Positions**: Without volume checks
2. **Set Stops Too Tight**: Noise will trigger premature exits
3. **Ignore Partial Fills**: Track order.filled vs order.amount
4. **Forget About Weekends**: Orders may remain open across weekends
5. **Mix Up Buy/Sell**: Positive amount = buy, negative = sell

## Related Documentation

- [Order Lifecycle](workflows/order-lifecycle.md) - Order state transitions
- [Blotter Architecture](execution/blotter.md) - Order routing and management
- Transaction Costs - Slippage and commission modeling
- [Order Examples](workflows/examples.md) - Real-world trading scenarios

## Next Steps

1. Study [Order Lifecycle](workflows/order-lifecycle.md) to understand state transitions
2. Read [Slippage Models](transaction-costs/slippage.md) for realistic cost modeling
3. Review [Order Examples](workflows/examples.md) for practical patterns
