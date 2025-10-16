# Order Management Examples

Practical examples of order management patterns for common trading scenarios.

## Overview

This guide demonstrates real-world order management patterns including:

- Entry and exit strategies
- Risk management with stops
- Position sizing
- Order monitoring and adjustment
- Multi-asset order management

## Basic Patterns

### Simple Buy and Hold

```python
from rustybt.algorithm import TradingAlgorithm
from rustybt.api import order, symbol

class BuyAndHold(TradingAlgorithm):
    def initialize(self, context):
        context.asset = self.symbol('SPY')
        context.ordered = False

    def handle_data(self, context, data):
        if not context.ordered:
            # Buy once at market price
            order(context.asset, 100)
            context.ordered = True
```

### Mean Reversion with Limits

```python
from rustybt.api import order, get_open_orders, cancel_order
from rustybt.finance.execution import LimitOrder

class MeanReversion(TradingAlgorithm):
    def initialize(self, context):
        context.asset = self.symbol('AAPL')
        context.lookback = 20

    def handle_data(self, context, data):
        # Get price data
        prices = data.history(context.asset, 'close', context.lookback, '1d')
        current_price = data.current(context.asset, 'close')

        # Calculate mean and std
        mean_price = prices.mean()
        std_price = prices.std()

        position = context.portfolio.positions.get(context.asset)

        # Entry: Price 2 std below mean
        if current_price < mean_price - 2 * std_price:
            if position is None or position.amount == 0:
                # Buy at current price (limit order for better fill)
                order(context.asset, 100, style=LimitOrder(current_price))

        # Exit: Price returns to mean
        elif current_price > mean_price:
            if position and position.amount > 0:
                # Sell at market to exit quickly
                order(context.asset, -position.amount)
```

## Risk Management Patterns

### Entry with Stop-Loss

```python
from rustybt.finance.execution import MarketOrder, StopOrder

class StopLossStrategy(TradingAlgorithm):
    def initialize(self, context):
        context.asset = self.symbol('AAPL')
        context.entry_price = None
        context.stop_loss_pct = 0.05  # 5% stop

    def handle_data(self, context, data):
        current_price = data.current(context.asset, 'close')
        position = context.portfolio.positions.get(context.asset)

        # Entry logic
        if position is None or position.amount == 0:
            if self.should_enter(context, data):
                # Enter at market
                order(context.asset, 100, style=MarketOrder())
                context.entry_price = current_price

                # Place stop-loss immediately
                stop_price = current_price * (1 - context.stop_loss_pct)
                order(context.asset, -100, style=StopOrder(stop_price))

    def should_enter(self, context, data):
        # Example: Simple price momentum signal
        prices = data.history(context.asset, 'close', 20, '1d')
        return prices[-1] > prices.mean()  # Price above 20-day MA
```

### Bracket Order (Complete Risk Management)

```python
from rustybt.finance.execution import BracketOrder, MarketOrder

class BracketStrategy(TradingAlgorithm):
    def initialize(self, context):
        context.asset = self.symbol('TSLA')
        context.risk_reward_ratio = 2.0  # 2:1 reward:risk

    def handle_data(self, context, data):
        current_price = data.current(context.asset, 'close')
        position = context.portfolio.positions.get(context.asset)

        if position is None or position.amount == 0:
            if self.entry_signal(context, data):
                # Calculate stop and target prices
                risk_amount = current_price * 0.05  # 5% risk
                stop_price = current_price - risk_amount
                target_price = current_price + (risk_amount * context.risk_reward_ratio)

                # Enter with automatic risk management
                order(
                    context.asset,
                    100,
                    style=BracketOrder(
                        entry_style=MarketOrder(),
                        stop_loss_price=stop_price,
                        take_profit_price=target_price
                    )
                )

                self.log.info(
                    f"Bracket order: Entry ${current_price:.2f}, "
                    f"Stop ${stop_price:.2f}, Target ${target_price:.2f}"
                )

    def entry_signal(self, context, data):
        # Example: RSI oversold signal
        prices = data.history(context.asset, 'close', 14, '1d')
        rsi = compute_rsi(prices, window=14)  # Your RSI calculation
        return rsi < 30  # Oversold condition
```

### Trailing Stop for Profit Protection

```python
from rustybt.finance.execution import TrailingStopOrder
from rustybt.api import get_open_orders, cancel_order

class TrailingStopStrategy(TradingAlgorithm):
    def initialize(self, context):
        context.asset = self.symbol('AAPL')
        context.entry_price = None
        context.profit_threshold = 0.05  # 5% profit to activate trailing
        context.trail_percent = 0.03     # 3% trail

    def handle_data(self, context, data):
        current_price = data.current(context.asset, 'close')
        position = context.portfolio.positions.get(context.asset)

        if position and position.amount > 0:
            # Calculate profit percentage
            profit_pct = (current_price - context.entry_price) / context.entry_price

            if profit_pct >= context.profit_threshold:
                # Cancel existing stop orders
                open_orders = get_open_orders(context.asset)
                for order in open_orders:
                    if order.stop is not None:
                        cancel_order(order)

                # Place trailing stop
                order(
                    context.asset,
                    -position.amount,
                    style=TrailingStopOrder(trail_percent=context.trail_percent)
                )

                self.log.info(f"Activated trailing stop at {profit_pct:.1%} profit")

        elif position is None or position.amount == 0:
            # Entry logic
            if self.entry_signal(context, data):
                order(context.asset, 100)
                context.entry_price = current_price
```

## Position Sizing Patterns

### Fixed Dollar Amount

```python
class FixedDollarPosition(TradingAlgorithm):
    def initialize(self, context):
        context.asset = self.symbol('SPY')
        context.target_position_value = 10000  # $10,000 per position

    def handle_data(self, context, data):
        current_price = data.current(context.asset, 'close')

        # Calculate shares for target dollar amount
        shares = int(context.target_position_value / current_price)

        position = context.portfolio.positions.get(context.asset)
        current_shares = position.amount if position else 0

        if self.should_rebalance(context, data):
            # Order difference to reach target
            order(context.asset, shares - current_shares)
```

### Percentage of Portfolio

```python
class PercentagePosition(TradingAlgorithm):
    def initialize(self, context):
        context.asset = self.symbol('QQQ')
        context.target_pct = 0.10  # 10% of portfolio

    def handle_data(self, context, data):
        current_price = data.current(context.asset, 'close')
        portfolio_value = context.portfolio.portfolio_value

        # Calculate target position value
        target_value = portfolio_value * context.target_pct
        target_shares = int(target_value / current_price)

        position = context.portfolio.positions.get(context.asset)
        current_shares = position.amount if position else 0

        # Rebalance to target
        order(context.asset, target_shares - current_shares)
```

### Kelly Criterion Position Sizing

```python
import numpy as np

class KellyPosition(TradingAlgorithm):
    def initialize(self, context):
        context.asset = self.symbol('AAPL')
        context.win_rate = 0.55      # 55% win rate
        context.avg_win = 0.10       # 10% average win
        context.avg_loss = 0.05      # 5% average loss

    def calculate_kelly_fraction(self, context):
        # Kelly formula: f = (p*b - q) / b
        # p = win probability
        # q = loss probability
        # b = win/loss ratio
        p = context.win_rate
        q = 1 - p
        b = context.avg_win / context.avg_loss

        kelly = (p * b - q) / b
        # Use fractional Kelly for safety
        return kelly * 0.5  # Half Kelly

    def handle_data(self, context, data):
        current_price = data.current(context.asset, 'close')
        portfolio_value = context.portfolio.portfolio_value

        # Calculate position size using Kelly
        kelly_fraction = self.calculate_kelly_fraction(context)
        target_value = portfolio_value * kelly_fraction
        target_shares = int(target_value / current_price)

        position = context.portfolio.positions.get(context.asset)
        current_shares = position.amount if position else 0

        order(context.asset, target_shares - current_shares)
```

## Order Monitoring Patterns

### Monitor and Adjust Orders

```python
from rustybt.api import get_open_orders, cancel_order
from rustybt.finance.execution import LimitOrder

class MonitoringStrategy(TradingAlgorithm):
    def initialize(self, context):
        context.asset = self.symbol('AAPL')
        context.order_timeout_bars = 5
        context.order_timestamps = {}

    def handle_data(self, context, data):
        current_price = data.current(context.asset, 'close')
        open_orders = get_open_orders(context.asset)

        for order in open_orders:
            # Track order age
            if order.id not in context.order_timestamps:
                context.order_timestamps[order.id] = context.datetime

            bars_since_order = (context.datetime - context.order_timestamps[order.id]).days

            # Cancel stale limit orders and replace with market
            if bars_since_order >= context.order_timeout_bars:
                if order.limit is not None:
                    self.log.info(f"Cancelling stale limit order {order.id}")
                    cancel_order(order)

                    # Re-submit as market order
                    order(context.asset, order.open_amount)
```

### Partial Fill Handling

```python
from rustybt.finance.order import ORDER_STATUS

class PartialFillHandler(TradingAlgorithm):
    def initialize(self, context):
        context.asset = self.symbol('AAPL')
        context.min_fill_pct = 0.75  # Require 75% fill

    def handle_data(self, context, data):
        open_orders = get_open_orders(context.asset)

        for order in open_orders:
            if order.status == ORDER_STATUS.PARTIALLY_FILLED:
                fill_pct = order.filled / order.amount

                if fill_pct < context.min_fill_pct:
                    # Not enough filled, cancel remainder
                    self.log.warning(
                        f"Order {order.id}: Only {fill_pct:.1%} filled, "
                        f"cancelling remainder"
                    )
                    cancel_order(order)
                else:
                    # Acceptable fill, let it continue
                    self.log.info(
                        f"Order {order.id}: {fill_pct:.1%} filled, "
                        f"waiting for remainder"
                    )
```

## Multi-Asset Patterns

### Pairs Trading

```python
class PairsTrading(TradingAlgorithm):
    def initialize(self, context):
        context.asset1 = self.symbol('PEP')
        context.asset2 = self.symbol('KO')
        context.lookback = 30
        context.entry_zscore = 2.0
        context.exit_zscore = 0.5

    def handle_data(self, context, data):
        # Get price history
        prices1 = data.history(context.asset1, 'close', context.lookback, '1d')
        prices2 = data.history(context.asset2, 'close', context.lookback, '1d')

        # Calculate spread and z-score
        spread = prices1 - prices2
        zscore = (spread[-1] - spread.mean()) / spread.std()

        pos1 = context.portfolio.positions.get(context.asset1)
        pos2 = context.portfolio.positions.get(context.asset2)

        # Entry logic
        if abs(zscore) > context.entry_zscore:
            if zscore > 0:
                # Asset1 overpriced, asset2 underpriced
                # Short asset1, long asset2
                order(context.asset1, -100)
                order(context.asset2, 100)
            else:
                # Asset1 underpriced, asset2 overpriced
                # Long asset1, short asset2
                order(context.asset1, 100)
                order(context.asset2, -100)

        # Exit logic
        elif abs(zscore) < context.exit_zscore:
            # Close positions
            if pos1 and pos1.amount != 0:
                order(context.asset1, -pos1.amount)
            if pos2 and pos2.amount != 0:
                order(context.asset2, -pos2.amount)
```

### Portfolio Rebalancing

```python
class Rebalancing(TradingAlgorithm):
    def initialize(self, context):
        # Define target portfolio weights
        context.target_weights = {
            self.symbol('SPY'): 0.40,   # 40% S&P 500
            self.symbol('QQQ'): 0.30,   # 30% Nasdaq
            self.symbol('IWM'): 0.20,   # 20% Small cap
            self.symbol('TLT'): 0.10,   # 10% Bonds
        }
        context.rebalance_frequency = 21  # Monthly (trading days)
        context.days_since_rebalance = 0

    def handle_data(self, context, data):
        context.days_since_rebalance += 1

        if context.days_since_rebalance >= context.rebalance_frequency:
            self.rebalance_portfolio(context, data)
            context.days_since_rebalance = 0

    def rebalance_portfolio(self, context, data):
        portfolio_value = context.portfolio.portfolio_value

        for asset, target_weight in context.target_weights.items():
            current_price = data.current(asset, 'close')

            # Calculate target position
            target_value = portfolio_value * target_weight
            target_shares = int(target_value / current_price)

            # Get current position
            position = context.portfolio.positions.get(asset)
            current_shares = position.amount if position else 0

            # Order difference
            shares_to_order = target_shares - current_shares
            if shares_to_order != 0:
                order(asset, shares_to_order)
                self.log.info(
                    f"Rebalancing {asset.symbol}: "
                    f"{current_shares} → {target_shares} shares"
                )
```

## Advanced Patterns

### Scale-In Strategy

```python
class ScaleIn(TradingAlgorithm):
    def initialize(self, context):
        context.asset = self.symbol('AAPL')
        context.total_target = 300      # Total position target
        context.scale_increments = 3    # Number of entries
        context.scale_interval = 5      # Days between entries
        context.entries_made = 0
        context.last_entry_date = None

    def handle_data(self, context, data):
        position = context.portfolio.positions.get(context.asset)
        current_shares = position.amount if position else 0

        # Check if we should scale in
        if context.entries_made < context.scale_increments:
            # Check timing
            if context.last_entry_date is None or \
               (context.datetime - context.last_entry_date).days >= context.scale_interval:

                # Calculate increment size
                increment = context.total_target // context.scale_increments

                order(context.asset, increment)
                context.entries_made += 1
                context.last_entry_date = context.datetime

                self.log.info(
                    f"Scale-in entry {context.entries_made}/{context.scale_increments}: "
                    f"{increment} shares"
                )
```

### Scale-Out Strategy

```python
class ScaleOut(TradingAlgorithm):
    def initialize(self, context):
        context.asset = self.symbol('AAPL')
        context.profit_levels = [0.05, 0.10, 0.15]  # 5%, 10%, 15% profit
        context.scale_percentages = [0.33, 0.33, 0.34]  # Scale out portions
        context.entry_price = None
        context.exits_made = 0

    def handle_data(self, context, data):
        current_price = data.current(context.asset, 'close')
        position = context.portfolio.positions.get(context.asset)

        # Entry logic
        if position is None or position.amount == 0:
            if self.entry_signal(context, data):
                order(context.asset, 300)
                context.entry_price = current_price
                context.exits_made = 0

        # Scale-out logic
        elif context.entry_price is not None:
            profit_pct = (current_price - context.entry_price) / context.entry_price

            if context.exits_made < len(context.profit_levels):
                target_profit = context.profit_levels[context.exits_made]

                if profit_pct >= target_profit:
                    # Calculate shares to sell
                    total_shares = position.amount
                    exit_pct = context.scale_percentages[context.exits_made]
                    shares_to_sell = int(total_shares * exit_pct)

                    order(context.asset, -shares_to_sell)
                    context.exits_made += 1

                    self.log.info(
                        f"Scale-out exit {context.exits_made}: "
                        f"{shares_to_sell} shares at {profit_pct:.1%} profit"
                    )
```

## Error Handling Patterns

### Robust Order Placement

```python
from rustybt.finance.order import ORDER_STATUS

class RobustOrdering(TradingAlgorithm):
    def initialize(self, context):
        context.asset = self.symbol('AAPL')
        context.max_retries = 3
        context.retry_count = {}

    def place_order_with_retry(self, context, asset, amount, style=None):
        """Place order with automatic retry on rejection."""
        try:
            order_id = order(asset, amount, style=style)

            # Check if order was rejected
            order_obj = context.blotter.orders.get(order_id)
            if order_obj and order_obj.status == ORDER_STATUS.REJECTED:
                retry_count = self.retry_count.get(asset, 0)

                if retry_count < context.max_retries:
                    self.log.warning(
                        f"Order rejected: {order_obj.reason}, "
                        f"retrying ({retry_count + 1}/{context.max_retries})"
                    )

                    # Adjust order based on rejection reason
                    adjusted_amount = self.adjust_order(
                        order_obj.reason, amount, context
                    )

                    self.retry_count[asset] = retry_count + 1
                    return self.place_order_with_retry(
                        context, asset, adjusted_amount, style
                    )
                else:
                    self.log.error("Max retries reached, giving up")
                    return None
            else:
                # Order accepted, reset retry count
                self.retry_count[asset] = 0
                return order_id

        except Exception as e:
            self.log.error(f"Order placement error: {e}")
            return None

    def adjust_order(self, rejection_reason, amount, context):
        """Adjust order based on rejection reason."""
        if "INSUFFICIENT_FUNDS" in rejection_reason:
            # Reduce order size by 50%
            return amount // 2
        elif "POSITION_LIMIT" in rejection_reason:
            # Reduce to fit within limit
            return amount // 2
        else:
            # No adjustment possible
            return amount
```

## Best Practices Summary

### ✅ DO

1. **Check Existing Positions**: Before placing new orders
2. **Monitor Order Status**: Track fills, partial fills, and rejections
3. **Use Appropriate Order Types**: Match order type to strategy needs
4. **Implement Risk Management**: Always use stops or position limits
5. **Handle Partial Fills**: Account for incomplete order fills
6. **Log Order Activity**: Track order placement and fills for debugging

### ❌ DON'T

1. **Place Duplicate Orders**: Check for open orders first
2. **Ignore Rejections**: Handle and log rejection reasons
3. **Assume Instant Fills**: Even market orders may take time
4. **Over-Leverage**: Use position sizing appropriate to account size
5. **Forget Transaction Costs**: Include commissions and slippage in backtests

## Related Documentation

- [Order Types](../order-types.md) - Complete order types reference
- [Order Lifecycle](order-lifecycle.md) - Order states and transitions
- [Blotter Architecture](../execution/blotter.md) - Order management system
- [Transaction Costs](../transaction-costs/slippage.md) - Cost modeling

## Next Steps

1. Study [Order Lifecycle](order-lifecycle.md) for state management
2. Review [Transaction Costs](../transaction-costs/slippage.md) for realistic modeling
3. Explore [Portfolio Management](../../portfolio-management/README.md) for position tracking
