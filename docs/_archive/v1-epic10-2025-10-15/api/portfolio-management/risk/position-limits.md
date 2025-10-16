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

- Exposure Tracking (Coming soon) - Monitor portfolio exposure
- Risk Metrics (Coming soon) - Calculate risk measures
- Best Practices (Coming soon) - Risk management guidelines
- [Portfolio Management](../README.md) - Portfolio tracking

## Next Steps

1. Study Exposure Tracking (Coming soon) for monitoring exposure
2. Review Risk Metrics (Coming soon) for risk measurement
3. Read Best Practices (Coming soon) for comprehensive risk management
