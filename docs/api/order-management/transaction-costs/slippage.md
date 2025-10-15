# Slippage Models

Complete guide to slippage modeling in RustyBT for realistic trade execution simulation.

## Overview

Slippage represents the difference between expected and actual execution prices. RustyBT provides multiple slippage models to simulate realistic execution:

- **FixedSlippage**: Constant price impact
- **VolumeShareSlippage**: Volume-constrained execution
- **FixedBasisPointsSlippage**: Percentage-based impact
- **Custom Models**: Build your own slippage models

## Why Model Slippage?

**Without slippage modeling**, backtests assume:
- ✗ Orders fill at exact quoted prices
- ✗ Unlimited liquidity available
- ✗ No market impact

**With realistic slippage**, backtests account for:
- ✓ Bid-ask spread costs
- ✓ Market impact from large orders
- ✓ Liquidity constraints
- ✓ Partial fills in illiquid markets

## Custom Slippage Models

Build custom slippage model for specific needs.

### Example: Market Impact with Square Root Model

```python
from rustybt.finance.slippage import SlippageModel
from rustybt.finance.transaction import create_transaction
import math

class MarketImpactSlippage(SlippageModel):
    """Square-root market impact model."""

    def __init__(self, impact_coefficient=0.5, volume_limit=0.10):
        self.impact_coefficient = impact_coefficient
        self.volume_limit = volume_limit

    def process_order(self, order, bar):
        # Maximum fill amount based on volume
        max_fill = int(bar['volume'] * self.volume_limit)
        fill_amount = min(order.open_amount, max_fill)

        if fill_amount == 0:
            return None, None

        # Square root market impact
        volume_share = fill_amount / bar['volume']
        impact = self.impact_coefficient * math.sqrt(volume_share)

        # Apply impact to price
        if order.amount > 0:  # Buy
            fill_price = bar['close'] * (1 + impact)
        else:  # Sell
            fill_price = bar['close'] * (1 - impact)

        return fill_price, fill_amount
```

### Example: Bid-Ask Spread Model

```python
class BidAskSlippage(SlippageModel):
    """Simulate bid-ask spread crossing."""

    def __init__(self, spread_bps=5):
        """
        Parameters
        ----------
        spread_bps : float
            Bid-ask spread in basis points (default 5 = 0.05%)
        """
        self.spread_bps = spread_bps

    def process_order(self, order, bar):
        # Calculate half-spread
        half_spread = (self.spread_bps / 10000) / 2

        # Buy at ask, sell at bid
        if order.amount > 0:  # Buy
            # Cross the spread: pay ask
            fill_price = bar['close'] * (1 + half_spread)
        else:  # Sell
            # Cross the spread: receive bid
            fill_price = bar['close'] * (1 - half_spread)

        # Assume full fill for liquid markets
        fill_amount = order.open_amount

        return fill_price, fill_amount
```

### Example: Time-of-Day Dependent Slippage

```python
class TimeOfDaySlippage(SlippageModel):
    """Higher slippage at market open/close."""

    def __init__(self, base_slippage, peak_multiplier=2.0):
        self.base_slippage = base_slippage
        self.peak_multiplier = peak_multiplier

    def get_time_multiplier(self, dt):
        """Calculate slippage multiplier based on time."""
        hour = dt.hour
        minute = dt.minute

        # Higher slippage first/last 30 minutes
        if (hour == 9 and minute < 30) or (hour == 15 and minute >= 30):
            return self.peak_multiplier
        else:
            return 1.0

    def process_order(self, order, bar):
        # Get base fill from underlying model
        fill_price, fill_amount = self.base_slippage.process_order(order, bar)

        if fill_price is None:
            return None, None

        # Adjust for time of day
        multiplier = self.get_time_multiplier(bar['dt'])
        base_price = bar['close']
        slippage = fill_price - base_price
        adjusted_slippage = slippage * multiplier

        return base_price + adjusted_slippage, fill_amount
```

## Slippage Analysis

### Measure Strategy Slippage

```python
class SlippageAnalysis(TradingAlgorithm):
    def initialize(self, context):
        context.total_slippage = 0.0
        context.trade_count = 0

    def handle_data(self, context, data):
        # ... trading logic ...
        pass

    def analyze(self, context, perf):
        """Calculate total slippage impact."""
        for txn in perf.transactions:
            # Slippage = difference from close price
            close_price = data.history(txn.asset, 'close', 1, '1d')[0]
            slippage = abs(txn.price - close_price) / close_price

            context.total_slippage += slippage
            context.trade_count += 1

        avg_slippage = context.total_slippage / context.trade_count
        print(f"Average slippage: {avg_slippage:.4%}")
```

### Compare Slippage Models

```python
# Test with different slippage models
models = [
    ('No Slippage', NoSlippage()),
    ('Fixed 5¢', FixedSlippage(spread=0.05)),
    ('10 bps', FixedBasisPointsSlippage(basis_points=10)),
    ('Volume Share', VolumeShareSlippage())
]

results = {}
for name, slippage_model in models:
    algo = MyStrategy()
    algo.set_slippage(slippage_model)
    perf = algo.run(start, end)
    results[name] = perf.portfolio_value[-1]

# Compare final portfolio values
for name, value in results.items():
    print(f"{name}: ${value:,.2f}")
```

## Best Practices

### ✅ DO

1. **Use VolumeShareSlippage as Default**: Most realistic for most strategies
2. **Model Slippage Conservatively**: Better to overestimate costs
3. **Adjust for Asset Class**: Equities vs futures vs crypto have different liquidity
4. **Test Sensitivity**: Run backtests with varying slippage assumptions
5. **Account for Order Size**: Large orders should have higher slippage

### ❌ DON'T

1. **Use NoSlippage for Production**: Unrealistic, will overestimate performance
2. **Ignore Partial Fills**: VolumeShareSlippage can cause partial fills
3. **Use Same Slippage for All Assets**: Liquid vs illiquid assets differ significantly
4. **Forget Market Impact**: Large orders move prices
5. **Underestimate Costs**: Better to be pessimistic in backtests

## Slippage Guidelines by Asset Class

| Asset Class | Typical Slippage | Recommended Model | volume_limit |
|-------------|------------------|-------------------|--------------|
| Large Cap Stocks | 2-5 bps | VolumeShareSlippage | 0.025 (2.5%) |
| Mid Cap Stocks | 5-15 bps | VolumeShareSlippage | 0.015 (1.5%) |
| Small Cap Stocks | 15-50 bps | VolumeShareSlippage | 0.005 (0.5%) |
| Futures | 1-5 bps | VolumeShareSlippage | 0.05 (5%) |
| Crypto (Liquid) | 5-20 bps | VolumeShareSlippage | 0.01 (1%) |
| Crypto (Illiquid) | 20-100 bps | VolumeShareSlippage | 0.005 (0.5%) |
| Options | Varies widely | Custom | Depends on strikes |

## Troubleshooting

### Orders Not Filling

**Symptom**: Orders remain open for many bars

**Cause**: Volume limit too restrictive

**Solution**:
```python
# Increase volume_limit for testing
algo.set_slippage(VolumeShareSlippage(volume_limit=0.05))  # 5%

# Or use smaller orders
max_order_size = current_volume * 0.01  # 1% of volume
```

### Excessive Slippage

**Symptom**: Much worse performance than expected

**Causes**:
- Too pessimistic slippage model
- Orders too large for available volume
- Trading illiquid assets

**Solutions**:
```python
# Check average slippage
avg_slippage = (trades['price'] - trades['close']).abs() / trades['close']
print(f"Average slippage: {avg_slippage.mean():.4%}")

# Reduce order sizes
if avg_slippage.mean() > 0.002:  # More than 20 bps
    # Scale down orders
    order_size *= 0.5
```

## Related Documentation

- [Commission Models](commissions.md) - Transaction fee modeling
- Volume Share Slippage (Coming soon) - Detailed fill processing
- [Order Types](../order-types.md) - How order types affect slippage
- Transaction Costs - Complete cost modeling guide

## Next Steps

1. Study [Commission Models](commissions.md) for complete cost modeling
2. Review Fill Processing (Coming soon) for execution details
3. Test [Sensitivity Analysis](../workflows/examples.md) with varying slippage assumptions
