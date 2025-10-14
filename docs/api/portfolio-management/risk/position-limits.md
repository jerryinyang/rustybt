# Position Limits and Risk Controls

Complete guide to position limits, risk controls, and portfolio constraints in RustyBT.

## Overview

Position limits and risk controls prevent excessive risk-taking and ensure strategies operate within defined boundaries:

- **Position Limits**: Maximum position size per asset
- **Concentration Limits**: Maximum portfolio allocation per asset
- **Leverage Constraints**: Maximum leverage allowed
- **Drawdown Limits**: Stop trading if drawdown exceeds threshold
- **Custom Controls**: Build your own risk controls

## Why Use Risk Controls?

**Without risk controls**:
- ✗ Strategy can accumulate excessive positions
- ✗ Single position can dominate portfolio
- ✗ No protection against runaway losses
- ✗ Difficult to manage risk in production

**With risk controls**:
- ✓ Automatic enforcement of risk limits
- ✓ Protection against coding errors
- ✓ Consistent risk management
- ✓ Safe production deployment

## Position Size Limits

### Maximum Shares Per Asset

Limit absolute number of shares held.

```python
from rustybt.finance.controls import MaxPositionSize

class MyStrategy(TradingAlgorithm):
    def initialize(self, context):
        # Limit to 1000 shares of any asset
        self.set_max_position_size(
            asset=None,  # Apply to all assets
            max_shares=1000
        )

    def handle_data(self, context, data):
        # This order will be rejected if it would exceed limit
        order(asset, 2000)  # REJECTED: exceeds 1000 share limit
```

### Maximum Position Value

Limit dollar value of position.

```python
class MyStrategy(TradingAlgorithm):
    def initialize(self, context):
        # Limit to $50,000 per position
        self.set_max_position_value(
            asset=None,
            max_value=50000
        )

    def handle_data(self, context, data):
        price = data.current(asset, 'close')

        # Calculate shares that respect limit
        max_shares = int(50000 / price)
        order(asset, max_shares)
```

### Asset-Specific Limits

Different limits for different assets.

```python
from rustybt.finance.controls import MaxPositionSize

class MyStrategy(TradingAlgorithm):
    def initialize(self, context):
        # Different limits for different assets
        self.set_max_position_size(
            asset=symbol('SPY'),
            max_shares=5000  # Allow more for liquid ETF
        )

        self.set_max_position_size(
            asset=symbol('TSLA'),
            max_shares=500   # Limit volatile stock
        )

        # Default for all other assets
        self.set_max_position_size(
            asset=None,
            max_shares=1000
        )
```

## Concentration Limits

### Maximum Portfolio Percentage

Limit position as percentage of portfolio.

```python
class ConcentrationLimit(TradingAlgorithm):
    def initialize(self, context):
        context.max_position_pct = 0.10  # 10% max per position

    def handle_data(self, context, data):
        portfolio_value = context.portfolio.portfolio_value
        max_position_value = portfolio_value * context.max_position_pct

        price = data.current(asset, 'close')
        max_shares = int(max_position_value / price)

        # Enforce limit
        position = context.portfolio.positions.get(asset)
        current_shares = position.amount if position else 0

        if current_shares >= max_shares:
            return  # Already at limit

        order(asset, max_shares - current_shares)
```

### Sector Concentration Limits

Limit exposure to specific sectors.

```python
class SectorLimits(TradingAlgorithm):
    def initialize(self, context):
        context.sector_limits = {
            'Technology': 0.30,  # Max 30% in tech
            'Finance': 0.25,      # Max 25% in finance
            'Energy': 0.15,       # Max 15% in energy
        }

    def check_sector_limit(self, context, asset, new_value):
        """Check if order would violate sector limit."""
        sector = asset.sector

        if sector not in context.sector_limits:
            return True  # No limit for this sector

        # Calculate current sector exposure
        portfolio_value = context.portfolio.portfolio_value
        sector_value = sum(
            pos.amount * pos.last_sale_price
            for a, pos in context.portfolio.positions.items()
            if a.sector == sector
        )

        # Check if new order would exceed limit
        new_sector_value = sector_value + new_value
        sector_pct = new_sector_value / portfolio_value

        return sector_pct <= context.sector_limits[sector]

    def handle_data(self, context, data):
        price = data.current(asset, 'close')
        order_value = 100 * price

        if self.check_sector_limit(context, asset, order_value):
            order(asset, 100)
        else:
            self.log.warning(f"Order rejected: would exceed {asset.sector} sector limit")
```

## Leverage Constraints

### Maximum Leverage

Limit total leverage (gross exposure / portfolio value).

```python
class LeverageLimit(TradingAlgorithm):
    def initialize(self, context):
        context.max_leverage = 2.0  # 2x leverage max

    def calculate_leverage(self, context):
        """Calculate current leverage."""
        portfolio_value = context.portfolio.portfolio_value

        # Gross exposure = sum of absolute position values
        gross_exposure = sum(
            abs(pos.amount * pos.last_sale_price)
            for pos in context.portfolio.positions.values()
        )

        leverage = gross_exposure / portfolio_value
        return leverage

    def handle_data(self, context, data):
        current_leverage = self.calculate_leverage(context)

        if current_leverage >= context.max_leverage:
            self.log.warning(f"At leverage limit: {current_leverage:.2f}x")
            return  # Don't place new orders

        # Calculate available leverage capacity
        portfolio_value = context.portfolio.portfolio_value
        max_gross_exposure = portfolio_value * context.max_leverage
        current_gross_exposure = current_leverage * portfolio_value
        available_exposure = max_gross_exposure - current_gross_exposure

        # Size order based on available leverage
        price = data.current(asset, 'close')
        max_shares = int(available_exposure / price)

        if max_shares > 0:
            order(asset, max_shares)
```

### Net Exposure Limits

Control net long/short exposure.

```python
class NetExposureLimit(TradingAlgorithm):
    def initialize(self, context):
        context.max_net_exposure = 1.0   # 100% net long/short max
        context.min_net_exposure = -0.5  # 50% net short max

    def calculate_net_exposure(self, context):
        """Calculate net exposure (long - short) / portfolio value."""
        portfolio_value = context.portfolio.portfolio_value

        long_exposure = sum(
            pos.amount * pos.last_sale_price
            for pos in context.portfolio.positions.values()
            if pos.amount > 0  # Long positions
        )

        short_exposure = sum(
            abs(pos.amount * pos.last_sale_price)
            for pos in context.portfolio.positions.values()
            if pos.amount < 0  # Short positions
        )

        net_exposure = (long_exposure - short_exposure) / portfolio_value
        return net_exposure

    def handle_data(self, context, data):
        net_exposure = self.calculate_net_exposure(context)

        # Check if order would violate limits
        if net_exposure >= context.max_net_exposure:
            # At max long exposure, can only add shorts
            order(asset, -100)  # Short order OK
        elif net_exposure <= context.min_net_exposure:
            # At max short exposure, can only add longs
            order(asset, 100)   # Long order OK
```

## Drawdown Limits

### Stop Trading on Max Drawdown

Halt trading if drawdown exceeds threshold.

```python
class DrawdownLimit(TradingAlgorithm):
    def initialize(self, context):
        context.max_drawdown_threshold = -0.20  # Stop at 20% drawdown
        context.peak_portfolio_value = context.portfolio.portfolio_value
        context.trading_halted = False

    def check_drawdown_limit(self, context):
        """Check if drawdown limit exceeded."""
        current_value = context.portfolio.portfolio_value

        # Update peak
        if current_value > context.peak_portfolio_value:
            context.peak_portfolio_value = current_value

        # Calculate drawdown
        drawdown = (current_value - context.peak_portfolio_value) / context.peak_portfolio_value

        if drawdown <= context.max_drawdown_threshold:
            context.trading_halted = True
            self.log.error(f"TRADING HALTED: Drawdown {drawdown:.2%} exceeds limit")

            # Close all positions
            for asset, position in context.portfolio.positions.items():
                order(asset, -position.amount)

        return context.trading_halted

    def handle_data(self, context, data):
        # Check drawdown before trading
        if self.check_drawdown_limit(context):
            return  # Trading halted

        # Normal trading logic
        order(asset, 100)
```

### Daily Loss Limit

Stop trading if daily loss exceeds threshold.

```python
class DailyLossLimit(TradingAlgorithm):
    def initialize(self, context):
        context.max_daily_loss = -0.05  # Stop at 5% daily loss
        context.start_of_day_value = context.portfolio.portfolio_value

    def before_trading_start(self, context, data):
        """Reset daily tracking."""
        context.start_of_day_value = context.portfolio.portfolio_value
        context.daily_loss_limit_hit = False

    def handle_data(self, context, data):
        # Check daily loss
        current_value = context.portfolio.portfolio_value
        daily_return = (current_value - context.start_of_day_value) / context.start_of_day_value

        if daily_return <= context.max_daily_loss:
            context.daily_loss_limit_hit = True
            self.log.error(f"Daily loss limit hit: {daily_return:.2%}")

            # Close all positions
            for asset, position in context.portfolio.positions.items():
                order(asset, -position.amount)
            return

        # Normal trading if within limits
        if not context.daily_loss_limit_hit:
            order(asset, 100)
```

## Custom Risk Controls

### Build Custom Control

```python
from rustybt.finance.controls import RiskControl

class CustomRiskControl(RiskControl):
    """Custom risk control implementation."""

    def __init__(self, **kwargs):
        self.params = kwargs

    def check(self, context, order):
        """Check if order passes risk control.

        Parameters
        ----------
        context : Context
            Strategy context
        order : Order
            Proposed order

        Returns
        -------
        allowed : bool
            Whether order is allowed
        reason : str
            Rejection reason if not allowed
        """
        # Your custom logic
        if self.custom_check(context, order):
            return True, None
        else:
            return False, "Custom control rejection reason"

    def custom_check(self, context, order):
        """Implement custom check logic."""
        pass

# Use custom control
algo.add_risk_control(CustomRiskControl(param1=value1))
```

### Example: Volatility-Based Position Sizing

```python
class VolatilityControl(RiskControl):
    """Size positions based on recent volatility."""

    def __init__(self, target_volatility=0.20):
        self.target_volatility = target_volatility
        self.lookback = 30

    def check(self, context, order):
        """Adjust order size based on volatility."""
        asset = order.asset

        # Calculate recent volatility
        prices = context.data.history(asset, 'close', self.lookback, '1d')
        returns = prices.pct_change().dropna()
        volatility = returns.std() * np.sqrt(252)

        # Adjust position size
        volatility_scalar = self.target_volatility / volatility
        adjusted_amount = int(order.amount * volatility_scalar)

        if abs(adjusted_amount) < abs(order.amount):
            # Reduce position size due to high volatility
            order.amount = adjusted_amount
            self.log.info(
                f"Volatility control: reduced order from {order.amount} "
                f"to {adjusted_amount} (vol: {volatility:.2%})"
            )

        return True, None
```

## Risk Control Best Practices

### Multiple Layers of Protection

```python
class DefensiveStrategy(TradingAlgorithm):
    def initialize(self, context):
        # Layer 1: Position size limits
        context.max_position_pct = 0.10  # 10% max per position

        # Layer 2: Sector concentration limits
        context.max_sector_pct = 0.30    # 30% max per sector

        # Layer 3: Total leverage limit
        context.max_leverage = 1.5       # 1.5x max leverage

        # Layer 4: Drawdown stop
        context.max_drawdown = -0.25     # Stop at 25% drawdown

        # Layer 5: Daily loss limit
        context.max_daily_loss = -0.05   # Stop at 5% daily loss

    def handle_data(self, context, data):
        # Check all risk controls before trading
        if not self.pass_all_controls(context, data, asset, amount):
            return

        # Place order
        order(asset, amount)

    def pass_all_controls(self, context, data, asset, amount):
        """Check all risk controls."""
        checks = [
            self.check_position_limit(context, asset, amount),
            self.check_sector_limit(context, asset, amount),
            self.check_leverage_limit(context, asset, amount),
            self.check_drawdown_limit(context),
            self.check_daily_loss_limit(context),
        ]

        return all(checks)
```

## Testing Risk Controls

### Validate Risk Control Logic

```python
import pytest

def test_position_limit():
    """Test position size limit enforcement."""
    algo = MyStrategy()
    algo.run(start_date, end_date)

    # Check no position exceeded limit
    for date, positions in algo.position_history.items():
        for asset, position in positions.items():
            assert abs(position.amount) <= 1000, \
                f"Position limit violated: {position.amount} shares"

def test_leverage_limit():
    """Test leverage limit enforcement."""
    algo = LeverageLimit()
    perf = algo.run(start_date, end_date)

    # Calculate leverage at each step
    for date, row in perf.iterrows():
        leverage = calculate_leverage(row)
        assert leverage <= 2.0, \
            f"Leverage limit violated: {leverage:.2f}x at {date}"

def test_drawdown_halt():
    """Test trading halts on max drawdown."""
    algo = DrawdownLimit()
    perf = algo.run(start_date, end_date)

    # Check that trading stopped after max drawdown
    drawdown = calculate_drawdown(perf.portfolio_value)
    if drawdown.min() < -0.20:
        # Find when limit was hit
        limit_date = drawdown[drawdown < -0.20].index[0]

        # Verify no new orders after limit hit
        orders_after = perf.orders[perf.orders.index > limit_date]
        assert len(orders_after) == 0 or all(orders_after['amount'] < 0), \
            "Orders placed after drawdown limit hit"
```

## Best Practices

### ✅ DO

1. **Use Multiple Controls**: Layer different risk controls for robust protection
2. **Test Thoroughly**: Validate controls work as expected in backtests
3. **Log Rejections**: Record why orders were rejected for analysis
4. **Start Conservative**: Begin with strict limits, relax if appropriate
5. **Monitor in Production**: Track risk control triggers in live trading

### ❌ DON'T

1. **Rely on Single Control**: One control may miss edge cases
2. **Set Limits Too Loose**: Controls should actually constrain risky behavior
3. **Ignore Rejections**: Understand why controls are triggering
4. **Override Controls**: Don't bypass controls in production
5. **Forget Correlation**: Assets can be correlated, diversification isn't automatic

## Related Documentation

- [Exposure Tracking](exposure-tracking.md) - Monitor portfolio exposure
- [Risk Metrics](risk-metrics.md) - Calculate risk measures
- [Best Practices](best-practices.md) - Risk management guidelines
- [Portfolio Management](../README.md) - Portfolio tracking

## Next Steps

1. Study [Exposure Tracking](exposure-tracking.md) for monitoring exposure
2. Review [Risk Metrics](risk-metrics.md) for risk measurement
3. Read [Best Practices](best-practices.md) for comprehensive risk management
