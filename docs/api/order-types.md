# Advanced Order Types

RustyBT supports advanced order types for sophisticated trading strategies and risk management.

## Order Types Overview

### 1. Trailing Stop Orders

A trailing stop order adjusts the stop price as the market price moves favorably, protecting profits while allowing for further gains.

**Use Case**: Protect profits on a winning position while giving it room to grow.

**Example**:
```python
from rustybt.finance.execution import TrailingStopOrder

# Trailing stop with $5 trail amount
algo.order(
    asset,
    -100,  # Sell 100 shares (closing long position)
    style=TrailingStopOrder(trail_amount=5.0)
)

# Trailing stop with 5% trail percent
algo.order(
    asset,
    -100,
    style=TrailingStopOrder(trail_percent=0.05)
)
```

**Behavior**:
- For long positions: stop price = highest_price - trail_amount (or * (1 - trail_percent))
- For short positions: stop price = lowest_price + trail_amount (or * (1 + trail_percent))
- Stop price only moves favorably, never widens

### 2. OCO (One-Cancels-Other) Orders

An OCO order links two orders together. When one fills, the other is automatically canceled.

**Use Case**: Set both a take-profit target and a stop-loss without worrying about both filling.

**Example**:
```python
from rustybt.finance.execution import OCOOrder, LimitOrder, StopOrder

# Create OCO with take-profit at $105 and stop-loss at $95
oco_style = OCOOrder(
    order1_style=LimitOrder(105.0),  # Take profit
    order2_style=StopOrder(95.0)      # Stop loss
)

algo.order(
    asset,
    -100,  # Closing order
    style=oco_style
)
```

**Behavior**:
- Two orders are created and linked
- When either order fills, the other is automatically canceled
- Commonly used for exit strategies: one profit target, one stop-loss

### 3. Bracket Orders

A bracket order combines an entry order with both a stop-loss and take-profit order.

**Use Case**: Enter a position with automatic risk management built in.

**Example**:
```python
from rustybt.finance.execution import BracketOrder, MarketOrder

# Buy 100 shares with stop at $95 and target at $105
bracket_style = BracketOrder(
    entry_style=MarketOrder(),
    stop_loss_price=95.0,
    take_profit_price=105.0
)

algo.order(
    asset,
    100,  # Buy 100 shares
    style=bracket_style
)
```

**Behavior**:
- Entry order is placed immediately
- After entry fills, stop-loss and take-profit orders are automatically created
- Stop-loss and take-profit are linked as an OCO pair
- When one child order fills, the other is canceled

## Order States

Advanced orders support the following states:

- `OPEN`: Order is active but not yet triggered
- `TRIGGERED`: Stop/limit price reached, order is now executable
- `PARTIALLY_FILLED`: Part of the order has filled
- `FILLED`: Order completely filled
- `CANCELLED`: Order was canceled
- `REJECTED`: Order was rejected by the broker/system

## Complete Example Strategy

Here's a complete strategy using advanced orders for risk management:

```python
from rustybt.algorithm import TradingAlgorithm
from rustybt.api import order, symbol
from rustybt.finance.execution import BracketOrder, MarketOrder, TrailingStopOrder

class AdvancedOrderStrategy(TradingAlgorithm):
    def initialize(self, context):
        self.stock = self.symbol('AAPL')
        self.entry_price = None
        self.in_position = False

    def handle_data(self, context, data):
        current_price = data.current(self.stock, 'close')

        if not self.in_position:
            # Enter with bracket order
            self.entry_price = current_price
            stop_loss = current_price * 0.95  # 5% stop
            take_profit = current_price * 1.10  # 10% target

            order(
                self.stock,
                100,
                style=BracketOrder(
                    entry_style=MarketOrder(),
                    stop_loss_price=stop_loss,
                    take_profit_price=take_profit
                )
            )
            self.in_position = True

        elif current_price > self.entry_price * 1.05:
            # Price up 5%, switch to trailing stop
            positions = context.portfolio.positions
            if self.stock in positions and positions[self.stock].amount > 0:
                # Cancel existing orders and place trailing stop
                cancel_all_orders_for_asset(self.stock)

                order(
                    self.stock,
                    -positions[self.stock].amount,
                    style=TrailingStopOrder(trail_percent=0.03)  # 3% trail
                )
```

## Best Practices

1. **Trailing Stops**: Use percentage-based trailing stops for volatile assets, fixed-amount for stable assets
2. **OCO Orders**: Always verify both orders are for the same quantity but opposite direction
3. **Bracket Orders**: Set realistic stop-loss and take-profit levels based on asset volatility
4. **Testing**: Always backtest advanced order strategies with realistic data

## Commission and Slippage

Advanced orders respect commission and slippage models:
- Stop orders execute as market orders after trigger (subject to slippage)
- Limit orders execute at limit price or better (less slippage)
- Each fill incurs commission based on your commission model

## Limitations

- Bracket orders create child orders after entry fills (check order status)
- OCO orders require both legs to be for the same asset
- Trailing stops recalculate on each bar (minute/daily depending on data frequency)
