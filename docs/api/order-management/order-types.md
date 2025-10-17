# Order Types API Reference

**Version**: 2.0 (Production Grade)
**Status**: ✅ Source Code Verified
**Last Updated**: 2025-10-16
**Story**: 11.3 - Order & Portfolio Management Documentation (Production Grade Redo)

---

## ⚠️ Documentation Integrity Notice

**This documentation has been verified against source code** to ensure 100% accuracy. All order types documented below exist in `rustybt/finance/execution.py` with exact import paths and signatures verified.

**Story 10.2 Corrections Applied**:
- ❌ **TWAPOrder** (Time-Weighted Average Price) - REMOVED (does not exist in source code)
- ❌ **VWAPOrder** (Volume-Weighted Average Price) - REMOVED (does not exist in source code)
- ❌ **IcebergOrder** (Hidden Liquidity) - REMOVED (does not exist in source code)

These algorithmic order types are **OUT OF SCOPE** per PRD and were incorrectly documented in Story 10.2. They do not exist in the RustyBT codebase and have been removed from this documentation.


---

## Table of Contents

1. [Overview](#overview)
2. [ExecutionStyle Base Class](#executionstyle-base-class)
3. [Basic Order Types](#basic-order-types)
   - [MarketOrder](#marketorder)
   - [LimitOrder](#limitorder)
   - [StopOrder](#stoporder)
   - [StopLimitOrder](#stoplimitorder)
4. [Advanced Order Types](#advanced-order-types)
   - [TrailingStopOrder](#trailingstoporder)
   - [OCOOrder (One-Cancels-Other)](#ocoorder-one-cancels-other)
   - [BracketOrder](#bracketorder)
5. [Order Validation](#order-validation)
6. [Error Handling](#error-handling)
7. [Best Practices](#best-practices)
8. [Complete Examples](#complete-examples)
9. [Related Documentation](#related-documentation)

---

## Overview

RustyBT supports **7 verified order execution styles** for implementing simple to sophisticated trading strategies. All order types are defined in `rustybt/finance/execution.py` and inherit from the `ExecutionStyle` base class.

### Supported Order Types

| Order Type | Source Code Line | Use Case | Price Protection | Fill Guarantee |
|------------|-----------------|----------|------------------|----------------|
| **MarketOrder** | execution.py:64 | Immediate execution | ❌ No | ✅ Yes* |
| **LimitOrder** | execution.py:81 | Price control | ✅ Yes | ❌ No |
| **StopOrder** | execution.py:111 | Stop-loss, breakouts | ❌ No | ✅ After trigger* |
| **StopLimitOrder** | execution.py:142 | Stop with price protection | ✅ Yes | ❌ No |
| **TrailingStopOrder** | execution.py:219 | Protect profits | ❌ No | ✅ After trigger* |
| **OCOOrder** | execution.py:318 | Paired exit orders | Varies | Varies |
| **BracketOrder** | execution.py:359 | Entry + risk management | Varies | Varies |

*In liquid markets only. Execution not guaranteed in illiquid markets or extreme volatility.

### Architecture

```python
ExecutionStyle (Abstract Base Class)
    ├── MarketOrder
    ├── LimitOrder
    ├── StopOrder
    ├── StopLimitOrder
    ├── TrailingStopOrder
    ├── OCOOrder
    └── BracketOrder
```

### Example Types in This Documentation

This documentation includes two types of code examples:

#### 📋 Usage Pattern Snippets
Brief code snippets showing **how to use** specific APIs within a trading strategy context. These are not complete runnable scripts but demonstrate the correct syntax and patterns. They assume you're working within a `TradingAlgorithm` subclass where methods like `initialize()` and `handle_data()` are available.

**Example**:
```python
def handle_data(context, data):
    # Usage pattern - shows API call syntax in strategy context
    order(asset, 100, style=MarketOrder())
```

#### 🚀 Complete Examples
Full runnable examples that include all necessary imports, setup, and context. These can be used as standalone scripts or integrated into your strategies.

**Example**:
```python
# Complete example - includes all imports and setup
from rustybt.algorithm import TradingAlgorithm
from rustybt.finance.execution import MarketOrder
from rustybt.api import order, symbol

class MyStrategy(TradingAlgorithm):
    def initialize(self, context):
        context.asset = symbol('AAPL')

    def handle_data(self, context, data):
        order(context.asset, 100, style=MarketOrder())
```

Look for section headers like "Complete Examples" for full runnable code, and inline examples for usage patterns.

---

## ExecutionStyle Base Class

**Source**: `rustybt/finance/execution.py:35-61`

All order types inherit from the `ExecutionStyle` abstract base class.

### Abstract Methods

```python
import abc

class ExecutionStyle(metaclass=abc.ABCMeta):
    """Base class for order execution styles."""

    @abc.abstractmethod
    def get_limit_price(self, is_buy):
        """Get limit price for this order (None or value >= 0)"""
        raise NotImplementedError

    @abc.abstractmethod
    def get_stop_price(self, is_buy):
        """Get stop price for this order (None or value >= 0)"""
        raise NotImplementedError

    @property
    def exchange(self):
        """Exchange to route order to (optional)"""
        return self._exchange
```

### Key Concepts

- **Execution Style**: Defines HOW an order should be executed (at market, at limit, etc.)
- **Order vs Style**: Orders carry quantity/direction; styles define execution logic
- **Price Methods**: `get_limit_price()` and `get_stop_price()` return execution parameters

---

## Basic Order Types

### MarketOrder

**Source**: `rustybt/finance/execution.py:64-78`
**Import**: `from rustybt.finance.execution import MarketOrder`

Execute immediately at current market price. Provides execution speed over price certainty.

#### Constructor

```python
MarketOrder(exchange=None)
```

**Parameters**:
- `exchange` (str, optional): Exchange to route order to (e.g., "NASDAQ", "NYSE"). Default: `None` (uses default routing).

#### Behavior

- ✅ **Fill Guarantee**: Orders fill immediately at next available price (in liquid markets)
- ❌ **No Price Protection**: Susceptible to slippage in illiquid markets
- ⚡ **Execution Speed**: Fastest execution, no price negotiation
- 📊 **Slippage**: Varies based on market liquidity and order size

#### When to Use

- **High Liquidity**: Large cap stocks with tight spreads
- **Speed Critical**: Breaking news, time-sensitive signals
- **Small Orders**: Order size < 1% of average daily volume

#### When to Avoid

- ❌ Illiquid assets (wide bid-ask spreads)
- ❌ Large orders relative to volume
- ❌ Volatile market conditions (flash crashes, circuit breakers)
- ❌ After-hours trading (low liquidity)

#### Example: Basic Market Order

```python
from rustybt.api import order
from rustybt.finance.execution import MarketOrder

def handle_data(context, data):
    """Place basic market orders."""
    # Buy 100 shares at market price
    order(symbol('AAPL'), 100, style=MarketOrder())

    # Sell 50 shares at market price
    order(symbol('GOOGL'), -50, style=MarketOrder())
```

#### Example: Market Order with Exchange Routing

```python
from rustybt.api import order
from rustybt.finance.execution import MarketOrder

def handle_data(context, data):
    """Route market order to specific exchange."""
    # Route to NASDAQ
    order(
        symbol('AAPL'),
        100,
        style=MarketOrder(exchange="NASDAQ")
    )
```

#### Example: Market Order with Slippage Modeling

```python
from rustybt.api import order, set_slippage
from rustybt.finance.execution import MarketOrder
from rustybt.finance.slippage import VolumeShareSlippageDecimal
from decimal import Decimal

def initialize(context):
    """Configure realistic slippage for market orders."""
    # Model slippage: 5% max volume share, 5bps per 1% volume
    set_slippage(VolumeShareSlippageDecimal(
        volume_limit=Decimal("0.05"),
        price_impact=Decimal("0.05")
    ))

def handle_data(context, data):
    """Market order with slippage applied."""
    order(symbol('AAPL'), 100, style=MarketOrder())
    # Slippage automatically applied during execution
```

#### Error Handling

```python
from rustybt.api import order
from rustybt.finance.execution import MarketOrder
from rustybt.exceptions import OrderError, InsufficientFundsError

def handle_data(context, data):
    """Handle market order errors."""
    try:
        order_id = order(symbol('AAPL'), 100, style=MarketOrder())
        if order_id:
            context.log.info(f"Market order placed: {order_id}")
    except InsufficientFundsError as e:
        context.log.error(f"Insufficient funds: {e}")
    except OrderError as e:
        context.log.error(f"Order failed: {e}")
```

---

### LimitOrder

**Source**: `rustybt/finance/execution.py:81-108`
**Import**: `from rustybt.finance.execution import LimitOrder`

Execute only at specified price or better. Provides price protection over execution guarantee.

#### Constructor

```python
LimitOrder(limit_price, asset=None, exchange=None)
```

**Parameters**:
- `limit_price` (float): **REQUIRED**. Maximum buy price or minimum sell price. Must be positive and finite.
- `asset` (Asset, optional): Asset being traded (used for tick size rounding). Default: `None` (uses 0.01 tick size).
- `exchange` (str, optional): Exchange to route order to. Default: `None`.

**Raises**:
- `BadOrderParameters`: If `limit_price` is negative, infinite, or NaN.

#### Behavior

- ✅ **Price Protection**: Order never fills at worse price than limit
- ❌ **No Fill Guarantee**: Order may never fill if price doesn't reach limit
- 📊 **Fill Logic**:
  - **Buy orders**: Fill when market price ≤ limit_price
  - **Sell orders**: Fill when market price ≥ limit_price
- 🔄 **Price Rounding**: Prices rounded to asset's tick size (default: $0.01)

#### When to Use

- **Price Sensitivity**: Willing to miss fill for better price
- **Illiquid Assets**: Protection against wide spreads
- **Non-Urgent Execution**: Can wait for favorable price

#### When to Avoid

- ❌ Fast-moving markets (risk missing opportunity)
- ❌ Time-sensitive signals (may not fill in time)
- ❌ Market-on-close execution requirements

#### Example: Basic Limit Orders

```python
from rustybt.api import order
from rustybt.finance.execution import LimitOrder

def handle_data(context, data):
    """Place limit orders with price protection."""
    current_price = data.current(symbol('AAPL'), 'price')

    # Buy at $150 or lower
    order(
        symbol('AAPL'),
        100,
        style=LimitOrder(limit_price=150.0)
    )

    # Sell at $155 or higher
    order(
        symbol('AAPL'),
        -100,
        style=LimitOrder(limit_price=155.0)
    )

    # Buy at 1% below current price
    order(
        symbol('GOOGL'),
        50,
        style=LimitOrder(limit_price=current_price * 0.99)
    )
```

#### Example: Limit Order with Asset Tick Size

```python
from rustybt.api import order, symbol
from rustybt.finance.execution import LimitOrder

def handle_data(context, data):
    """Limit order with proper tick size rounding."""
    asset = symbol('AAPL')
    current_price = data.current(asset, 'price')

    # Order with asset-specific tick size
    order(
        asset,
        100,
        style=LimitOrder(
            limit_price=current_price * 0.99,
            asset=asset  # Uses asset's tick_size for rounding
        )
    )
```

#### Example: Limit Order Validation

```python
from rustybt.api import order
from rustybt.finance.execution import LimitOrder
from rustybt.errors import BadOrderParameters
import math

def handle_data(context, data):
    """Validate limit price before order submission."""
    def place_limit_order(sym, qty, limit_price):
        """Place limit order with validation."""
        # Validate price
        if limit_price <= 0:
            context.log.error(f"Invalid limit price: {limit_price}")
            return None

        if not math.isfinite(limit_price):
            context.log.error(f"Limit price must be finite: {limit_price}")
            return None

        try:
            order_id = order(
                symbol(sym),
                qty,
                style=LimitOrder(limit_price=limit_price)
            )
            return order_id
        except BadOrderParameters as e:
            context.log.error(f"Bad limit order parameters: {e}")
            return None

    # Valid order
    place_limit_order('AAPL', 100, 150.0)

    # Invalid orders (will be rejected)
    place_limit_order('AAPL', 100, -150.0)  # Negative price
    place_limit_order('AAPL', 100, float('inf'))  # Infinite price
```

#### Example: Monitoring Limit Order Fills

```python
from rustybt.api import order, get_open_orders
from rustybt.finance.execution import LimitOrder

def handle_data(context, data):
    """Monitor limit order status."""
    if not hasattr(context, 'limit_order_id'):
        # Place limit order
        context.limit_order_id = order(
            symbol('AAPL'),
            100,
            style=LimitOrder(limit_price=150.0)
        )
        context.log.info(f"Limit order placed: {context.limit_order_id}")
    else:
        # Check if order still open
        open_orders = get_open_orders()
        if symbol('AAPL') in open_orders:
            for open_order in open_orders[symbol('AAPL')]:
                if open_order.id == context.limit_order_id:
                    context.log.info(
                        f"Limit order {open_order.id} still open: "
                        f"filled {open_order.filled}/{open_order.amount}"
                    )
        else:
            context.log.info(f"Limit order {context.limit_order_id} filled!")
            delattr(context, 'limit_order_id')
```

---

### StopOrder

**Source**: `rustybt/finance/execution.py:111-139`
**Import**: `from rustybt.finance.execution import StopOrder`

Trigger market order when price reaches stop threshold. Used for stop-loss protection and breakout strategies.

#### Constructor

```python
StopOrder(stop_price, asset=None, exchange=None)
```

**Parameters**:
- `stop_price` (float): **REQUIRED**. Price threshold that triggers the order. Must be positive and finite.
- `asset` (Asset, optional): Asset being traded (used for tick size rounding). Default: `None`.
- `exchange` (str, optional): Exchange to route order to. Default: `None`.

**Raises**:
- `BadOrderParameters`: If `stop_price` is negative, infinite, or NaN.

#### Behavior

- ⏱️ **Dormant Phase**: Order inactive until stop price reached
- ⚡ **Trigger**: Becomes market order when price crosses stop threshold
- ❌ **Post-Trigger Slippage**: Subject to slippage after conversion to market order
- 📊 **Trigger Logic**:
  - **Buy stop**: Triggers when market price ≥ stop_price
  - **Sell stop**: Triggers when market price ≤ stop_price

#### When to Use

- **Stop-Loss Protection**: Limit downside risk on long positions
- **Short Covering**: Limit upside risk on short positions
- **Breakout Strategies**: Enter when price breaks resistance/support

#### When to Avoid

- ❌ Extremely volatile markets (risk of large slippage)
- ❌ Illiquid assets (may trigger far from stop price)
- ❌ When price precision critical (use StopLimitOrder instead)

#### Example: Basic Stop-Loss

```python
from rustybt.api import order, symbol
from rustybt.finance.execution import StopOrder

def handle_data(context, data):
    """Implement stop-loss with stop orders."""
    current_price = data.current(symbol('AAPL'), 'price')

    # Stop-loss at 5% below current price
    stop_loss_price = current_price * 0.95

    # Sell 100 shares if price drops to stop
    order(
        symbol('AAPL'),
        -100,
        style=StopOrder(stop_price=stop_loss_price)
    )
```

#### Example: Buy Stop for Breakout

```python
from rustybt.api import order, symbol
from rustybt.finance.execution import StopOrder

def handle_data(context, data):
    """Buy on breakout above resistance."""
    resistance_level = 150.0  # Identified resistance

    # Buy 100 shares if price breaks above $150
    order(
        symbol('AAPL'),
        100,
        style=StopOrder(stop_price=resistance_level)
    )
```

#### Example: Dynamic Stop-Loss Management

```python
from rustybt.api import order, symbol, get_open_orders, cancel_order
from rustybt.finance.execution import StopOrder

def handle_data(context, data):
    """Manage dynamic stop-loss orders."""
    asset = symbol('AAPL')
    position = context.portfolio.positions.get(asset)

    if position and position.amount > 0:
        current_price = data.current(asset, 'price')
        entry_price = position.cost_basis
        pnl_pct = (current_price - entry_price) / entry_price

        # Calculate stop level
        if pnl_pct > 0.10:  # 10% profit
            stop_price = entry_price * 1.05  # Lock in 5% gain
        else:
            stop_price = entry_price * 0.95  # Initial 5% stop

        # Cancel existing stops
        open_orders = get_open_orders(asset)
        for open_order in open_orders:
            if isinstance(open_order.style, StopOrder):
                cancel_order(open_order)

        # Place new stop
        order(
            asset,
            -position.amount,
            style=StopOrder(stop_price=stop_price)
        )
```

#### Example: Stop Order Error Handling

```python
from rustybt.api import order, symbol
from rustybt.finance.execution import StopOrder
from rustybt.errors import BadOrderParameters

def handle_data(context, data):
    """Handle stop order errors."""
    def place_stop_order(sym, qty, stop_price):
        """Place stop order with validation."""
        try:
            if stop_price <= 0:
                raise ValueError(f"Stop price must be positive: {stop_price}")

            order_id = order(
                symbol(sym),
                qty,
                style=StopOrder(stop_price=stop_price)
            )
            context.log.info(f"Stop order placed: {order_id} @ ${stop_price}")
            return order_id

        except BadOrderParameters as e:
            context.log.error(f"Invalid stop order parameters: {e}")
            return None
        except ValueError as e:
            context.log.error(f"Validation error: {e}")
            return None

    current_price = data.current(symbol('AAPL'), 'price')

    # Valid stop order
    place_stop_order('AAPL', -100, current_price * 0.95)

    # Invalid stop order
    place_stop_order('AAPL', -100, -50.0)  # Negative price (rejected)
```

---

### StopLimitOrder

**Source**: `rustybt/finance/execution.py:142-179`
**Import**: `from rustybt.finance.execution import StopLimitOrder`

Trigger limit order when price reaches stop threshold. Combines stop trigger with limit price protection.

#### Constructor

```python
StopLimitOrder(limit_price, stop_price, asset=None, exchange=None)
```

**Parameters**:
- `limit_price` (float): **REQUIRED**. Limit price for order after trigger. Must be positive and finite.
- `stop_price` (float): **REQUIRED**. Price threshold that triggers the order. Must be positive and finite.
- `asset` (Asset, optional): Asset being traded (used for tick size rounding). Default: `None`.
- `exchange` (str, optional): Exchange to route order to. Default: `None`.

**Raises**:
- `BadOrderParameters`: If `limit_price` or `stop_price` is negative, infinite, or NaN.

#### Behavior

- ⏱️ **Dormant Phase**: Order inactive until stop price reached
- 📋 **Trigger**: Becomes limit order when price crosses stop threshold
- ✅ **Price Protection**: Limit order provides price protection after trigger
- ❌ **No Fill Guarantee**: May not fill if price moves too fast past limit

#### When to Use

- **Stop-Loss with Price Control**: Limit worst-case exit price
- **Breakout with Protection**: Enter breakouts with maximum price
- **Volatile Markets**: Prevent extreme slippage on stop triggers

#### When to Avoid

- ❌ When execution guarantee critical (regular StopOrder better)
- ❌ Fast-moving markets (order may not fill at all)

#### Example: Stop-Limit for Controlled Exit

```python
from rustybt.api import order, symbol
from rustybt.finance.execution import StopLimitOrder

def handle_data(context, data):
    """Exit with price protection using stop-limit."""
    current_price = data.current(symbol('AAPL'), 'price')

    # Sell between $95-$94 if price drops to $95
    order(
        symbol('AAPL'),
        -100,
        style=StopLimitOrder(
            stop_price=95.0,   # Trigger at $95
            limit_price=94.0   # Accept fills down to $94
        )
    )
```

#### Example: Buy Stop-Limit for Breakout

```python
from rustybt.api import order, symbol
from rustybt.finance.execution import StopLimitOrder

def handle_data(context, data):
    """Buy breakout with maximum price protection."""
    resistance = 150.0

    # Buy between $150-$151 if price breaks above $150
    order(
        symbol('AAPL'),
        100,
        style=StopLimitOrder(
            stop_price=resistance,        # Trigger at $150
            limit_price=resistance * 1.01  # Max price $151
        )
    )
```

#### Example: Stop-Limit vs Stop Comparison

```python
from rustybt.api import order, symbol
from rustybt.finance.execution import StopOrder, StopLimitOrder

def handle_data(context, data):
    """Compare stop order vs stop-limit order behavior."""
    current_price = data.current(symbol('AAPL'), 'price')
    stop_price = current_price * 0.95

    # Scenario 1: Stop Order (guaranteed fill, no price control)
    order(
        symbol('AAPL'),
        -100,
        style=StopOrder(stop_price=stop_price)
    )
    # Triggers at $95, fills at any price (could be $90 in crash)

    # Scenario 2: Stop-Limit Order (price control, no fill guarantee)
    order(
        symbol('AAPL'),
        -100,
        style=StopLimitOrder(
            stop_price=stop_price,
            limit_price=stop_price * 0.98  # Only fill down to $93.10
        )
    )
    # Triggers at $95, only fills $93.10-$95 range
    # If price drops to $90, order does NOT fill!
```

---

### TrailingStopOrder

**Source**: `rustybt/finance/execution.py:219-315`
**Import**: `from rustybt.finance.execution import TrailingStopOrder`

Stop order that automatically adjusts as market price moves favorably. Used to protect profits while allowing position to run.

#### Constructor

```python
TrailingStopOrder(trail_amount=None, trail_percent=None, asset=None, exchange=None)
```

**Parameters**:
- `trail_amount` (float, optional): Absolute dollar amount to trail. Must be positive. **Mutually exclusive with `trail_percent`**.
- `trail_percent` (float, optional): Percentage (as decimal) to trail. Must be between 0 and 1. **Mutually exclusive with `trail_amount`**.
- `asset` (Asset, optional): Asset being traded (used for tick size rounding). Default: `None`.
- `exchange` (str, optional): Exchange to route order to. Default: `None`.

**Raises**:
- `BadOrderParameters`: If neither or both trail parameters provided, or if values out of range.

**Constraints**:
- Exactly ONE of `trail_amount` or `trail_percent` must be specified
- `trail_amount` must be > 0
- `trail_percent` must be > 0 and < 1

#### Behavior

- 📈 **Dynamic Adjustment**: Stop price follows market price favorably
- 🔒 **One-Way Ratchet**: Stop price never widens, only tightens
- ⚡ **Trigger**: Becomes market order when price reverses past stop
- ✅ **Profit Protection**: Automatically locks in gains as price moves favorably

**Trailing Logic**:

For **sell** orders (closing long position):
```python
stop_price = highest_price_seen - trail_amount
# or
stop_price = highest_price_seen * (1 - trail_percent)
```

For **buy** orders (covering short position):
```python
stop_price = lowest_price_seen + trail_amount
# or
stop_price = lowest_price_seen * (1 + trail_percent)
```

#### When to Use

- **Protect Profits**: Lock in gains on winning trades
- **Trending Markets**: Let winners run while protecting downside
- **Long-Term Holds**: Dynamic risk management without manual adjustment

#### When to Avoid

- ❌ Choppy/sideways markets (premature triggers)
- ❌ Highly volatile assets (noise triggers stops)
- ❌ Short-term mean reversion strategies

#### Example: Absolute Trailing Stop

```python
from rustybt.api import order, symbol
from rustybt.finance.execution import TrailingStopOrder

def handle_data(context, data):
    """Trail stop by fixed dollar amount."""
    # Sell if price drops $5 from highest point
    order(
        symbol('AAPL'),
        -100,
        style=TrailingStopOrder(trail_amount=5.0)
    )
```

#### Example: Percentage Trailing Stop

```python
from rustybt.api import order, symbol
from rustybt.finance.execution import TrailingStopOrder

def handle_data(context, data):
    """Trail stop by percentage."""
    # Sell if price drops 3% from highest point
    order(
        symbol('AAPL'),
        -100,
        style=TrailingStopOrder(trail_percent=0.03)
    )
```

#### Example: Dynamic Trailing Stop Strategy

```python
from rustybt.api import order, symbol, get_open_orders, cancel_order
from rustybt.finance.execution import TrailingStopOrder

def initialize(context):
    """Initialize trailing stop strategy."""
    context.entry_price = {}

def handle_data(context, data):
    """Implement adaptive trailing stop."""
    asset = symbol('AAPL')
    position = context.portfolio.positions.get(asset)

    if position and position.amount > 0:
        current_price = data.current(asset, 'price')

        # Get entry price
        if asset not in context.entry_price:
            context.entry_price[asset] = position.cost_basis

        entry_price = context.entry_price[asset]
        profit_pct = (current_price - entry_price) / entry_price

        # Adaptive trailing stop based on profit
        if profit_pct > 0.20:  # 20% profit
            trail_pct = 0.10  # Wider 10% trail
        elif profit_pct > 0.10:  # 10% profit
            trail_pct = 0.05  # 5% trail
        else:
            trail_pct = 0.03  # Tight 3% trail

        # Cancel existing trailing stops
        open_orders = get_open_orders(asset)
        for open_order in open_orders:
            if isinstance(open_order.style, TrailingStopOrder):
                cancel_order(open_order)

        # Place new trailing stop
        order(
            asset,
            -position.amount,
            style=TrailingStopOrder(trail_percent=trail_pct)
        )

        context.log.info(
            f"Trailing stop updated: profit={profit_pct:.1%}, trail={trail_pct:.1%}"
        )
```

#### Example: Trailing Stop Behavior Simulation

```python
from rustybt.finance.execution import TrailingStopOrder
from decimal import Decimal

# Simulate trailing stop behavior
prices = [100, 105, 110, 115, 112, 110, 108]

trailing_stop = TrailingStopOrder(trail_percent=0.05)

for price in prices:
    # Simulate update (sell order)
    stop_price = trailing_stop.update_trailing_stop(
        current_price=Decimal(str(price)),
        is_buy=False
    )

    print(f"Price: ${price} → Stop: ${stop_price}")

    # Check trigger
    if price < float(stop_price):
        print(f"  ⚠️ TRIGGERED at ${price}!")
        break

# Output:
# Price: $100 → Stop: $95.00
# Price: $105 → Stop: $99.75
# Price: $110 → Stop: $104.50
# Price: $115 → Stop: $109.25
# Price: $112 → Stop: $109.25 (doesn't widen)
# Price: $110 → Stop: $109.25
# Price: $108 → Stop: $109.25
#   ⚠️ TRIGGERED at $108!
```

#### Example: Error Handling

```python
from rustybt.api import order, symbol
from rustybt.finance.execution import TrailingStopOrder
from rustybt.errors import BadOrderParameters

def handle_data(context, data):
    """Handle trailing stop order errors."""
    def place_trailing_stop(sym, qty, trail_amount=None, trail_percent=None):
        """Place trailing stop with validation."""
        try:
            order_id = order(
                symbol(sym),
                qty,
                style=TrailingStopOrder(
                    trail_amount=trail_amount,
                    trail_percent=trail_percent
                )
            )
            context.log.info(f"Trailing stop placed: {order_id}")
            return order_id

        except BadOrderParameters as e:
            context.log.error(f"Invalid trailing stop: {e}")
            return None

    # Valid orders
    place_trailing_stop('AAPL', -100, trail_amount=5.0)
    place_trailing_stop('AAPL', -100, trail_percent=0.03)

    # Invalid orders
    place_trailing_stop('AAPL', -100)  # Neither parameter (error)
    place_trailing_stop('AAPL', -100, trail_amount=5.0, trail_percent=0.03)  # Both (error)
    place_trailing_stop('AAPL', -100, trail_amount=-5.0)  # Negative (error)
    place_trailing_stop('AAPL', -100, trail_percent=1.5)  # > 1 (error)
```

---

## Advanced Order Types

### OCOOrder (One-Cancels-Other)

**Source**: `rustybt/finance/execution.py:318-356`
**Import**: `from rustybt.finance.execution import OCOOrder`

Links two orders together such that when one fills, the other is automatically canceled. Commonly used for take-profit/stop-loss pairs.

#### Constructor

```python
OCOOrder(order1_style, order2_style, exchange=None)
```

**Parameters**:
- `order1_style` (ExecutionStyle): **REQUIRED**. First order's execution style. Must be ExecutionStyle instance.
- `order2_style` (ExecutionStyle): **REQUIRED**. Second order's execution style. Must be ExecutionStyle instance.
- `exchange` (str, optional): Exchange to route orders to. Default: `None`.

**Raises**:
- `BadOrderParameters`: If either order style is not an ExecutionStyle instance.

#### Behavior

- 🔗 **Linked Orders**: Two orders created and linked together
- ⚡ **First Fill Wins**: Whichever order fills first cancels the other
- ❌ **Auto-Cancel**: Remaining order immediately canceled on first fill
- ✅ **Prevents Over-Execution**: Ensures only one order executes

**Internal State**:
- `_filled_order`: Tracks which order filled first (if any)

#### When to Use

- **Exit Strategy**: Profit target AND stop-loss
- **Bi-Directional Breakout**: Buy upside breakout OR sell downside breakdown
- **Range Trading**: Buy support OR sell resistance

#### When to Avoid

- ❌ When both orders should potentially fill (not mutually exclusive)
- ❌ Different assets (OCO is for same asset)
- ❌ When order correlation not 100% negative

#### Example: Take-Profit / Stop-Loss Pair

```python
from rustybt.api import order, symbol
from rustybt.finance.execution import OCOOrder, LimitOrder, StopOrder

def handle_data(context, data):
    """Exit position with OCO: profit target OR stop-loss."""
    # Take profit at $110 OR stop-loss at $90
    oco_style = OCOOrder(
        order1_style=LimitOrder(limit_price=110.0),  # Profit target
        order2_style=StopOrder(stop_price=90.0)       # Stop-loss
    )

    # Close 100 shares (whichever condition hits first)
    order(symbol('AAPL'), -100, style=oco_style)
```

#### Example: Breakout/Breakdown Strategy

```python
from rustybt.api import order, symbol
from rustybt.finance.execution import OCOOrder, StopOrder

def handle_data(context, data):
    """Trade bi-directional breakout with OCO."""
    current_price = data.current(symbol('AAPL'), 'price')
    resistance = 110.0
    support = 90.0

    # Buy breakout OR sell breakdown (only one executes)
    # Note: This requires TWO separate orders with different amounts

    # Buy breakout
    buy_oco = OCOOrder(
        order1_style=StopOrder(stop_price=resistance),  # Buy trigger
        order2_style=StopOrder(stop_price=support)      # Cancel if support breaks
    )
    order(symbol('AAPL'), 100, style=buy_oco)

    # Sell breakdown (separate order for opposite direction)
    sell_oco = OCOOrder(
        order1_style=StopOrder(stop_price=support),     # Sell trigger
        order2_style=StopOrder(stop_price=resistance)   # Cancel if resistance breaks
    )
    order(symbol('AAPL'), -100, style=sell_oco)
```

#### Example: OCO with Limit and Stop-Limit

```python
from rustybt.api import order, symbol
from rustybt.finance.execution import OCOOrder, LimitOrder, StopLimitOrder

def handle_data(context, data):
    """OCO with more sophisticated order types."""
    # Take profit with limit OR stop with price protection
    oco_style = OCOOrder(
        order1_style=LimitOrder(limit_price=110.0),
        order2_style=StopLimitOrder(
            stop_price=90.0,
            limit_price=88.0  # Don't accept worse than $88
        )
    )

    order(symbol('AAPL'), -100, style=oco_style)
```

#### Example: Monitoring OCO Order Status

```python
from rustybt.api import order, symbol, get_open_orders
from rustybt.finance.execution import OCOOrder, LimitOrder, StopOrder

def handle_data(context, data):
    """Monitor OCO order execution."""
    if not hasattr(context, 'oco_order_id'):
        # Place OCO order
        oco_style = OCOOrder(
            order1_style=LimitOrder(limit_price=110.0),
            order2_style=StopOrder(stop_price=90.0)
        )

        context.oco_order_id = order(symbol('AAPL'), -100, style=oco_style)
        context.log.info(f"OCO order placed: {context.oco_order_id}")
    else:
        # Check order status
        open_orders = get_open_orders(symbol('AAPL'))

        if not open_orders:
            context.log.info(f"OCO order {context.oco_order_id} filled!")
            # Determine which leg filled
            # (implementation depends on order tracking system)
            delattr(context, 'oco_order_id')
        else:
            context.log.info(f"OCO order still active: {len(open_orders)} legs")
```

#### Example: Error Handling

```python
from rustybt.api import order, symbol
from rustybt.finance.execution import OCOOrder, LimitOrder, StopOrder
from rustybt.errors import BadOrderParameters

def handle_data(context, data):
    """Handle OCO order errors."""
    def place_oco_order(sym, qty, order1_style, order2_style):
        """Place OCO order with validation."""
        try:
            # Validate order styles
            from rustybt.finance.execution import ExecutionStyle
            if not isinstance(order1_style, ExecutionStyle):
                raise ValueError("order1_style must be ExecutionStyle instance")
            if not isinstance(order2_style, ExecutionStyle):
                raise ValueError("order2_style must be ExecutionStyle instance")

            oco_style = OCOOrder(order1_style, order2_style)
            order_id = order(symbol(sym), qty, style=oco_style)

            context.log.info(f"OCO order placed: {order_id}")
            return order_id

        except BadOrderParameters as e:
            context.log.error(f"Invalid OCO parameters: {e}")
            return None
        except ValueError as e:
            context.log.error(f"Validation error: {e}")
            return None

    # Valid OCO order
    place_oco_order(
        'AAPL',
        -100,
        LimitOrder(110.0),
        StopOrder(90.0)
    )

    # Invalid OCO order (not ExecutionStyle instances)
    place_oco_order('AAPL', -100, 110.0, 90.0)  # Raw floats (error)
```

---

### BracketOrder

**Source**: `rustybt/finance/execution.py:359-408`
**Import**: `from rustybt.finance.execution import BracketOrder`

Combines entry, stop-loss, and take-profit into a single order. After entry fills, stop-loss and take-profit orders are automatically placed as an OCO pair.

#### Constructor

```python
BracketOrder(entry_style, stop_loss_price, take_profit_price, asset=None, exchange=None)
```

**Parameters**:
- `entry_style` (ExecutionStyle): **REQUIRED**. Execution style for entry order. Must be ExecutionStyle instance.
- `stop_loss_price` (float): **REQUIRED**. Stop price for protective stop-loss. Must be positive and finite.
- `take_profit_price` (float): **REQUIRED**. Limit price for take-profit order. Must be positive and finite.
- `asset` (Asset, optional): Asset being traded (used for tick size rounding). Default: `None`.
- `exchange` (str, optional): Exchange to route orders to. Default: `None`.

**Raises**:
- `BadOrderParameters`: If `entry_style` not ExecutionStyle, or prices negative/infinite/NaN.

#### Behavior

1. 📨 **Entry Order**: Placed immediately with specified entry_style
2. ⏱️ **Wait for Entry**: Stop-loss and take-profit dormant until entry fills
3. 🔗 **Activate OCO**: After entry, stop-loss and take-profit placed as OCO pair
4. ✅ **Risk Managed**: Position automatically has exit strategy from entry

**Order Lifecycle**:
```
Entry Order (Market/Limit/Stop/etc.)
    │ (fills)
    ▼
Parent Order ID assigned
    │
    ├──> Stop-Loss Order (StopOrder)
    │         ↓
    │    (activated)
    │
    └──> Take-Profit Order (LimitOrder)
            ↓
        (activated)
            │
            └──> OCO relationship (one cancels other)
```

**Internal State**:
- `_entry_filled`: Tracks if entry order has filled
- `_stop_loss_order_id`: ID of stop-loss child order (after entry)
- `_take_profit_order_id`: ID of take-profit child order (after entry)

#### When to Use

- **Enter with Risk Management**: Automate stop-loss and target from entry
- **Swing Trading**: Predefined risk-reward ratios
- **Disciplined Execution**: Remove emotional exit decisions

#### When to Avoid

- ❌ Need dynamic exit levels (use manual management)
- ❌ Trailing stops preferred (use TrailingStopOrder)
- ❌ Multiple exit conditions (more complex logic needed)

#### Example: Basic Bracket Order

```python
from rustybt.api import order, symbol
from rustybt.finance.execution import BracketOrder, MarketOrder

def handle_data(context, data):
    """Enter position with automated risk management."""
    current_price = data.current(symbol('AAPL'), 'price')

    # Enter at market with 5% stop and 10% target
    bracket_style = BracketOrder(
        entry_style=MarketOrder(),
        stop_loss_price=current_price * 0.95,   # $95 (5% risk)
        take_profit_price=current_price * 1.10  # $110 (10% target)
    )

    order(symbol('AAPL'), 100, style=bracket_style)
    # Risk-Reward Ratio: 10% / 5% = 2:1
```

#### Example: Bracket Order with Limit Entry

```python
from rustybt.api import order, symbol
from rustybt.finance.execution import BracketOrder, LimitOrder

def handle_data(context, data):
    """Enter at limit price with bracket."""
    current_price = data.current(symbol('AAPL'), 'price')

    # Enter at limit, exit with stops
    bracket_style = BracketOrder(
        entry_style=LimitOrder(limit_price=98.0),  # Enter at $98
        stop_loss_price=93.0,                       # Risk $5
        take_profit_price=108.0                     # Target $10
    )

    order(symbol('AAPL'), 100, style=bracket_style)
    # Risk-Reward Ratio: (108-98)/(98-93) = 10/5 = 2:1
```

#### Example: Bracket Order with Stop Entry

```python
from rustybt.api import order, symbol
from rustybt.finance.execution import BracketOrder, StopOrder

def handle_data(context, data):
    """Enter on breakout with bracket."""
    resistance = 105.0

    # Enter on breakout above resistance
    bracket_style = BracketOrder(
        entry_style=StopOrder(stop_price=resistance),  # Breakout entry
        stop_loss_price=100.0,                          # Below entry
        take_profit_price=115.0                         # Above entry
    )

    order(symbol('AAPL'), 100, style=bracket_style)
```

#### Example: Dynamic Bracket Strategy

```python
from rustybt.api import order, symbol
from rustybt.finance.execution import BracketOrder, MarketOrder

def initialize(context):
    """Initialize bracket order strategy."""
    context.atr_period = 14  # Average True Range period
    context.atr_stop_multiplier = 2.0
    context.risk_reward_ratio = 2.0

def handle_data(context, data):
    """Calculate dynamic bracket levels based on ATR."""
    asset = symbol('AAPL')

    # Get current price and ATR
    current_price = data.current(asset, 'price')

    # Calculate ATR (simplified - use proper TA library in production)
    high = data.history(asset, 'high', context.atr_period + 1, '1d')
    low = data.history(asset, 'low', context.atr_period + 1, '1d')
    close = data.history(asset, 'close', context.atr_period + 1, '1d')

    tr = (high - low).max()  # Simplified true range
    atr = tr  # Simplified ATR (use proper calculation in production)

    # Calculate bracket levels
    stop_distance = atr * context.atr_stop_multiplier
    profit_distance = stop_distance * context.risk_reward_ratio

    stop_loss_price = current_price - stop_distance
    take_profit_price = current_price + profit_distance

    # Place bracket order
    bracket_style = BracketOrder(
        entry_style=MarketOrder(),
        stop_loss_price=stop_loss_price,
        take_profit_price=take_profit_price
    )

    order(asset, 100, style=bracket_style)

    context.log.info(
        f"Bracket order: Entry=${current_price:.2f}, "
        f"Stop=${stop_loss_price:.2f}, "
        f"Target=${take_profit_price:.2f}, "
        f"R:R={context.risk_reward_ratio}:1"
    )
```

#### Example: Monitoring Bracket Order Execution

```python
from rustybt.api import order, symbol, get_open_orders
from rustybt.finance.execution import BracketOrder, MarketOrder

def initialize(context):
    """Initialize bracket tracking."""
    context.bracket_orders = {}

def handle_data(context, data):
    """Monitor bracket order lifecycle."""
    asset = symbol('AAPL')

    if asset not in context.bracket_orders:
        # Place bracket order
        current_price = data.current(asset, 'price')

        bracket_style = BracketOrder(
            entry_style=MarketOrder(),
            stop_loss_price=current_price * 0.95,
            take_profit_price=current_price * 1.10
        )

        order_id = order(asset, 100, style=bracket_style)
        context.bracket_orders[asset] = {
            'order_id': order_id,
            'entry_filled': False,
            'exit_filled': False
        }

        context.log.info(f"Bracket order placed: {order_id}")

    else:
        # Monitor bracket status
        bracket_info = context.bracket_orders[asset]
        position = context.portfolio.positions.get(asset)
        open_orders = get_open_orders(asset)

        # Check if entry filled
        if not bracket_info['entry_filled'] and position:
            bracket_info['entry_filled'] = True
            context.log.info(f"Bracket entry filled: {bracket_info['order_id']}")

        # Check if exit filled
        if bracket_info['entry_filled'] and not position:
            bracket_info['exit_filled'] = True
            context.log.info(f"Bracket exit filled: {bracket_info['order_id']}")
            del context.bracket_orders[asset]

        # Log status
        if bracket_info['entry_filled'] and not bracket_info['exit_filled']:
            context.log.info(
                f"Bracket active: {len(open_orders)} exit orders pending"
            )
```

#### Example: Error Handling

```python
from rustybt.api import order, symbol
from rustybt.finance.execution import BracketOrder, MarketOrder, LimitOrder
from rustybt.errors import BadOrderParameters

def handle_data(context, data):
    """Handle bracket order errors."""
    def place_bracket_order(sym, qty, entry_style, stop_price, profit_price):
        """Place bracket order with validation."""
        try:
            # Validate entry style
            from rustybt.finance.execution import ExecutionStyle
            if not isinstance(entry_style, ExecutionStyle):
                raise ValueError("entry_style must be ExecutionStyle instance")

            # Validate prices
            if stop_price <= 0 or profit_price <= 0:
                raise ValueError("Prices must be positive")

            # Validate risk-reward makes sense for direction
            current_price = data.current(symbol(sym), 'price')

            if qty > 0:  # Long position
                if stop_price >= current_price:
                    raise ValueError("Stop must be below entry for long")
                if profit_price <= current_price:
                    raise ValueError("Profit target must be above entry for long")
            else:  # Short position
                if stop_price <= current_price:
                    raise ValueError("Stop must be above entry for short")
                if profit_price >= current_price:
                    raise ValueError("Profit target must be below entry for short")

            bracket_style = BracketOrder(entry_style, stop_price, profit_price)
            order_id = order(symbol(sym), qty, style=bracket_style)

            context.log.info(f"Bracket order placed: {order_id}")
            return order_id

        except BadOrderParameters as e:
            context.log.error(f"Invalid bracket parameters: {e}")
            return None
        except ValueError as e:
            context.log.error(f"Validation error: {e}")
            return None

    current_price = data.current(symbol('AAPL'), 'price')

    # Valid bracket order
    place_bracket_order(
        'AAPL',
        100,
        MarketOrder(),
        current_price * 0.95,
        current_price * 1.10
    )

    # Invalid bracket orders
    place_bracket_order('AAPL', 100, MarketOrder(), -95.0, 110.0)  # Negative stop
    place_bracket_order('AAPL', 100, MarketOrder(), 105.0, 90.0)  # Inverted levels
    place_bracket_order('AAPL', 100, "market", 95.0, 110.0)  # Invalid entry_style
```

---

## Order Validation

All order types undergo validation before submission to prevent invalid orders.

### Validation Checks

**Price Validation** (`check_stoplimit_prices()`):
- Source: `rustybt/finance/execution.py:411-428`
- Checks: Price is finite, non-negative, not NaN
- Raises: `BadOrderParameters` on validation failure

```python
def check_stoplimit_prices(price, label):
    """Validate stop/limit prices are reasonable."""
    try:
        if not isfinite(price):
            raise BadOrderParameters(
                msg=f"Attempted to place order with {label} price of {price}."
            )
    except TypeError as exc:
        raise BadOrderParameters(
            msg=f"Attempted to place order with {label} price of {type(price)}."
        ) from exc

    if price < 0:
        raise BadOrderParameters(
            msg=f"Can't place {label} order with negative price."
        )
```

### Common Validation Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `BadOrderParameters: negative price` | Price < 0 | Use positive prices |
| `BadOrderParameters: infinite price` | Price = inf or NaN | Use finite prices |
| `BadOrderParameters: missing parameter` | Required param not provided | Provide all required params |
| `BadOrderParameters: invalid style` | Wrong type for execution style | Use ExecutionStyle instance |

### Example: Pre-Validation Pattern

```python
from rustybt.api import order, symbol
from rustybt.finance.execution import LimitOrder
from rustybt.errors import BadOrderParameters
import math

def handle_data(context, data):
    """Validate order parameters before submission."""
    def validate_and_order(sym, qty, limit_price):
        """Validate parameters before creating order."""
        # Pre-validation
        if limit_price <= 0:
            context.log.error(f"Invalid limit price: {limit_price}")
            return None

        if not math.isfinite(limit_price):
            context.log.error(f"Limit price not finite: {limit_price}")
            return None

        if qty == 0:
            context.log.error("Order quantity cannot be zero")
            return None

        # Place order (should succeed if pre-validation passed)
        try:
            order_id = order(
                symbol(sym),
                qty,
                style=LimitOrder(limit_price=limit_price)
            )
            context.log.info(f"Order placed: {order_id}")
            return order_id

        except BadOrderParameters as e:
            context.log.error(f"Order rejected: {e}")
            return None

    # Usage
    current_price = data.current(symbol('AAPL'), 'price')
    validate_and_order('AAPL', 100, current_price * 0.99)
```

---

## Error Handling

### Common Errors

#### BadOrderParameters

**Source**: `rustybt.errors.BadOrderParameters`

Raised when order parameters fail validation.

**Common Causes**:
- Negative prices
- Infinite or NaN prices
- Missing required parameters
- Invalid parameter types
- Invalid parameter combinations

**Example**:
```python
from rustybt.api import order, symbol
from rustybt.finance.execution import TrailingStopOrder
from rustybt.errors import BadOrderParameters

def handle_data(context, data):
    """Handle BadOrderParameters errors."""
    try:
        # Invalid: both trail_amount and trail_percent
        order(
            symbol('AAPL'),
            -100,
            style=TrailingStopOrder(
                trail_amount=5.0,
                trail_percent=0.03  # ERROR: can't specify both
            )
        )
    except BadOrderParameters as e:
        context.log.error(f"Invalid parameters: {e}")
        # Fallback: use trail_percent only
        order(
            symbol('AAPL'),
            -100,
            style=TrailingStopOrder(trail_percent=0.03)
        )
```

#### InsufficientFunds

**Source**: `rustybt.exceptions.InsufficientFundsError`

Raised when insufficient cash/margin to place order.

**Example**:
```python
from rustybt.api import order, symbol
from rustybt.finance.execution import MarketOrder
from rustybt.exceptions import InsufficientFundsError

def handle_data(context, data):
    """Handle insufficient funds errors."""
    try:
        order(symbol('AAPL'), 1000, style=MarketOrder())
    except InsufficientFundsError as e:
        context.log.warning(f"Insufficient funds: {e}")

        # Calculate affordable quantity
        price = data.current(symbol('AAPL'), 'price')
        cash = context.portfolio.cash
        affordable_qty = int(cash / price)

        if affordable_qty > 0:
            context.log.info(f"Placing reduced order: {affordable_qty} shares")
            order(symbol('AAPL'), affordable_qty, style=MarketOrder())
        else:
            context.log.error("Cannot afford even 1 share")
```

#### OrderError

**Source**: `rustybt.exceptions.OrderError`

General order submission or execution error.

**Example**:
```python
from rustybt.api import order, symbol
from rustybt.finance.execution import MarketOrder
from rustybt.exceptions import OrderError

def handle_data(context, data):
    """Handle general order errors."""
    try:
        order(symbol('AAPL'), 100, style=MarketOrder())
    except OrderError as e:
        context.log.error(f"Order failed: {e}")
        # Log details for debugging
        context.log.info(f"Portfolio cash: ${context.portfolio.cash:.2f}")
        context.log.info(f"Open orders: {len(context.blotter.open_orders)}")
```

---

## Best Practices

### ✅ DO

1. **Validate Parameters Before Submission**
   ```python
   # Check price validity
   if price > 0 and math.isfinite(price):
       order(symbol('AAPL'), 100, style=LimitOrder(price))
   ```

2. **Monitor Order Status**
   ```python
   open_orders = get_open_orders(symbol('AAPL'))
   for open_order in open_orders:
       context.log.info(f"Order {open_order.id}: {open_order.filled}/{open_order.amount}")
   ```

3. **Use Appropriate Order Type for Strategy**
   - Market orders: High liquidity, speed critical
   - Limit orders: Illiquid assets, price control
   - Stop orders: Risk management, breakouts
   - Bracket orders: Swing trades, defined risk-reward

4. **Model Transaction Costs**
   ```python
   from rustybt.api import set_slippage, set_commission
   from rustybt.finance.slippage import VolumeShareSlippageDecimal
   from rustybt.finance.commission import PerShareCommission
   from decimal import Decimal

   set_slippage(VolumeShareSlippageDecimal(
       volume_limit=Decimal("0.05"),
       price_impact=Decimal("0.05")
   ))
   set_commission(PerShareCommission(Decimal("0.005")))
   ```

5. **Set Realistic Stop-Loss Levels**
   ```python
   # Based on ATR, not arbitrary percentages
   atr = calculate_atr(data, symbol('AAPL'), period=14)
   stop_distance = atr * 2.0  # 2 ATR stop
   stop_price = current_price - stop_distance
   ```

### ❌ DON'T

1. **Don't Place Market Orders Without Volume Check**
   ```python
   # BAD: Large order in illiquid market
   order(symbol('ILLIQUID_STOCK'), 10000, style=MarketOrder())

   # GOOD: Check volume first
   volume = data.current(symbol('STOCK'), 'volume')
   if order_size < volume * 0.01:  # < 1% of volume
       order(symbol('STOCK'), order_size, style=MarketOrder())
   else:
       # Use limit order or split order
       order(symbol('STOCK'), order_size, style=LimitOrder(price))
   ```

2. **Don't Ignore Partial Fills**
   ```python
   # BAD: Assume order filled completely
   order(symbol('AAPL'), 1000, style=LimitOrder(150.0))
   # Position may not be 1000 shares!

   # GOOD: Check filled quantity
   open_orders = get_open_orders(symbol('AAPL'))
   for open_order in open_orders:
       if open_order.filled < open_order.amount:
           context.log.warning(
               f"Partial fill: {open_order.filled}/{open_order.amount}"
           )
   ```

3. **Don't Mix Up Buy/Sell Direction**
   ```python
   # BAD: Inconsistent signs
   order(symbol('AAPL'), -100, style=LimitOrder(155.0))  # Sell at $155
   order(symbol('AAPL'), 100, style=StopOrder(90.0))  # Buy stop at $90??

   # GOOD: Consistent logic
   order(symbol('AAPL'), -100, style=LimitOrder(155.0))  # Sell at $155
   order(symbol('AAPL'), -100, style=StopOrder(145.0))   # Stop-loss at $145
   ```

4. **Don't Set Stops Too Tight**
   ```python
   # BAD: Tight stop in volatile market
   order(symbol('VOLATILE_STOCK'), -100, style=StopOrder(
       current_price * 0.99  # 1% stop (too tight!)
   ))

   # GOOD: ATR-based stop
   atr = calculate_atr(data, symbol('VOLATILE_STOCK'), 14)
   stop_distance = atr * 2.5
   order(symbol('VOLATILE_STOCK'), -100, style=StopOrder(
       current_price - stop_distance
   ))
   ```

5. **Don't Forget About Execution Costs**
   ```python
   # BAD: Ignore slippage and commissions
   expected_profit = (exit_price - entry_price) * quantity

   # GOOD: Account for costs
   slippage_estimate = entry_price * 0.0005  # 5 bps
   commission = quantity * 0.005  # $0.005/share
   expected_profit = (
       (exit_price - entry_price - slippage_estimate) * quantity
       - commission * 2  # Entry + exit
   )
   ```

---

## Complete Examples

### Example 1: Mean Reversion with Bracket Orders

```python
from rustybt.api import (
    initialize, handle_data, symbol, order,
    get_open_orders, schedule_function, date_rules, time_rules
)
from rustybt.finance.execution import BracketOrder, MarketOrder

def initialize(context):
    """Initialize mean reversion strategy."""
    context.asset = symbol('AAPL')
    context.lookback = 20
    context.entry_threshold = 2.0  # Standard deviations
    context.stop_atr_mult = 2.0
    context.target_atr_mult = 3.0

    # Schedule rebalancing
    schedule_function(
        check_entry,
        date_rules.every_day(),
        time_rules.market_open(minutes=30)
    )

def check_entry(context, data):
    """Check for mean reversion entry signals."""
    asset = context.asset
    position = context.portfolio.positions.get(asset)

    # Skip if already in position
    if position and position.amount != 0:
        return

    # Calculate mean reversion signal
    prices = data.history(asset, 'price', context.lookback, '1d')
    mean = prices.mean()
    std = prices.std()
    current_price = data.current(asset, 'price')

    z_score = (current_price - mean) / std

    # Entry signal: price > 2 std deviations from mean
    if abs(z_score) > context.entry_threshold:
        # Calculate ATR for stop/target placement
        high = data.history(asset, 'high', context.lookback, '1d')
        low = data.history(asset, 'low', context.lookback, '1d')
        atr = (high - low).mean()  # Simplified ATR

        # Long entry (oversold)
        if z_score < -context.entry_threshold:
            stop_price = current_price - (atr * context.stop_atr_mult)
            target_price = mean  # Revert to mean

            order(
                asset,
                100,
                style=BracketOrder(
                    entry_style=MarketOrder(),
                    stop_loss_price=stop_price,
                    take_profit_price=target_price
                )
            )

            context.log.info(
                f"LONG entry: z={z_score:.2f}, "
                f"stop=${stop_price:.2f}, target=${target_price:.2f}"
            )

        # Short entry (overbought)
        elif z_score > context.entry_threshold:
            stop_price = current_price + (atr * context.stop_atr_mult)
            target_price = mean  # Revert to mean

            order(
                asset,
                -100,
                style=BracketOrder(
                    entry_style=MarketOrder(),
                    stop_loss_price=stop_price,
                    take_profit_price=target_price
                )
            )

            context.log.info(
                f"SHORT entry: z={z_score:.2f}, "
                f"stop=${stop_price:.2f}, target=${target_price:.2f}"
            )

def handle_data(context, data):
    """Monitor positions and orders."""
    asset = context.asset
    position = context.portfolio.positions.get(asset)

    if position:
        current_price = data.current(asset, 'price')
        pnl_pct = (
            (current_price - position.cost_basis) / position.cost_basis
            * (1 if position.amount > 0 else -1)
        )

        context.log.info(
            f"Position: {position.amount} shares, P&L: {pnl_pct:.2%}"
        )
```

### Example 2: Breakout Strategy with Trailing Stops

```python
from rustybt.api import (
    initialize, handle_data, symbol, order,
    get_open_orders, cancel_order
)
from rustybt.finance.execution import StopOrder, TrailingStopOrder

def initialize(context):
    """Initialize breakout strategy."""
    context.asset = symbol('AAPL')
    context.lookback = 20
    context.trail_activation = 0.05  # 5% profit to activate trail
    context.trail_percent = 0.03  # 3% trailing stop
    context.entry_placed = False

def handle_data(context, data):
    """Breakout strategy with trailing stop."""
    asset = context.asset
    position = context.portfolio.positions.get(asset)
    current_price = data.current(asset, 'price')

    # Entry logic
    if not position or position.amount == 0:
        # Calculate breakout level (20-day high)
        highs = data.history(asset, 'high', context.lookback, '1d')
        breakout_level = highs.max()

        # Place buy stop at breakout level
        if not context.entry_placed:
            order(
                asset,
                100,
                style=StopOrder(stop_price=breakout_level * 1.01)  # Slight buffer
            )
            context.entry_placed = True
            context.log.info(f"Breakout order placed @ ${breakout_level * 1.01:.2f}")

    # Exit logic (trailing stop)
    else:
        if not hasattr(context, 'entry_price'):
            context.entry_price = position.cost_basis

        # Calculate profit percentage
        profit_pct = (current_price - context.entry_price) / context.entry_price

        # Activate trailing stop after profit threshold
        if profit_pct > context.trail_activation:
            # Cancel existing orders
            open_orders = get_open_orders(asset)
            for open_order in open_orders:
                cancel_order(open_order)

            # Place trailing stop
            order(
                asset,
                -position.amount,
                style=TrailingStopOrder(trail_percent=context.trail_percent)
            )

            context.log.info(
                f"Trailing stop activated: profit={profit_pct:.2%}, "
                f"trail={context.trail_percent:.2%}"
            )

            # Reset for next trade
            context.entry_placed = False
            delattr(context, 'entry_price')
```

### Running the Examples

Once you've defined your strategy with order types, you can execute it using either the CLI or Python API.

#### CLI Method

Save your strategy to a file (e.g., `mean_reversion.py`) and run:

```bash
rustybt run -f mean_reversion.py -b yfinance-profiling --start 2020-01-01 --end 2023-12-31
```

#### Python API Method

Add execution code to your strategy file:

```python
# mean_reversion.py
from rustybt.utils.run_algo import run_algorithm
import pandas as pd

# ... (strategy functions from examples above) ...

if __name__ == "__main__":
    result = run_algorithm(
        initialize=initialize,
        handle_data=handle_data,
        bundle='yfinance-profiling',
        start=pd.Timestamp('2020-01-01'),
        end=pd.Timestamp('2023-12-31'),
        capital_base=10000
    )

    # Analyze results
    print("\n" + "="*50)
    print("Backtest Results")
    print("="*50)
    print(f"Total return: {result['returns'].iloc[-1]:.2%}")
    print(f"Sharpe ratio: {result['sharpe']:.2f}")
    print(f"Max drawdown: {result['max_drawdown']:.2%}")

    # Access order history
    if 'orders' in result:
        print(f"\nTotal orders: {len(result['orders'])}")
        print(f"Filled orders: {result['orders']['status'].eq('filled').sum()}")
```

Then run with:

```bash
python mean_reversion.py
```

!!! tip "Accessing Order Details"
    The `result` DataFrame includes an `orders` sub-DataFrame with complete order history, including order types, prices, fills, and statuses. Use this for detailed execution analysis.

---

## Related Documentation

### Order Management System
- [Order Lifecycle](workflows/order-lifecycle.md) - Order state transitions and status tracking
- [Blotter Architecture](execution/blotter.md) - Order routing, execution, and tracking
- [Order Examples](workflows/examples.md) - Real-world order management patterns

### Transaction Costs
- [Slippage Models](transaction-costs/slippage.md) - Price impact and market friction modeling
- [Commission Models](transaction-costs/commissions.md) - Broker fee calculation
- [Borrow Costs](transaction-costs/borrow-costs-financing.md) - Short selling costs (Story 4.5)
- [Overnight Financing](transaction-costs/borrow-costs-financing.md) - Leverage costs (Story 4.6)

### Execution Systems
- [Latency Simulation](execution/latency-models.md) - Order submission and execution delays (Story 4.1)
- [Partial Fill Models](execution/partial-fills.md) - Realistic fill simulation (Story 4.2)

### Portfolio Management
- [Risk Management](../portfolio-management/risk/position-limits.md) - Position limits and controls
- [Multi-Strategy Allocation](../portfolio-management/multi-strategy/allocators.md) - Capital allocation (Story 4.8)

---

## Next Steps

1. **Learn Order Lifecycle**: Understand how orders transition through states → [Order Lifecycle](workflows/order-lifecycle.md)
2. **Model Transaction Costs**: Add realistic slippage and commissions → [Slippage Models](transaction-costs/slippage.md)
3. **Study Examples**: See real-world order patterns → [Order Examples](workflows/examples.md)

---

**Document Status**: ✅ Production Grade - All APIs Verified Against Source Code
**Last Verification**: 2025-10-16
**Verification Method**: Direct source code inspection of `rustybt/finance/execution.py`
**Story**: 11.3 - Order & Portfolio Management Documentation (Production Grade Redo)
