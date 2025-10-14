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

**Impact Example**:
```python
# Without slippage:
# Buy 1000 shares at $100 = $100,000 cost

# With 0.1% slippage:
# Buy 1000 shares at $100.10 = $100,100 cost
# Extra $100 cost (0.1% slippage)

# Over 100 trades: $10,000 extra cost!
```

## Slippage Model Interface

### Base Class

```python
from rustybt.finance.slippage import SlippageModel

class SlippageModel(metaclass=FinancialModelMeta):
    """Abstract base class for slippage models."""

    @abstractmethod
    def process_order(self, order, bar):
        """Calculate slippage and fill for an order.

        Parameters
        ----------
        order : Order
            Order to process
        bar : dict
            Current bar data (OHLCV)

        Returns
        -------
        fill_price : float
            Execution price after slippage
        fill_amount : int
            Number of shares that can fill
        """
        raise NotImplementedError
```

## Built-in Slippage Models

### NoSlippage

Fill at exact quoted price with no slippage.

**Use Case**: Testing, or when transaction costs are negligible.

**Example**:
```python
from rustybt.finance.slippage import NoSlippage

algo.set_slippage(NoSlippage())
```

**Behavior**:
```python
# Fill at exact close price
fill_price = bar['close']
fill_amount = order.amount  # Full fill
```

**⚠️ Warning**: Unrealistic for most strategies. Use only for testing or when costs truly negligible.

### FixedSlippage

Apply constant price impact per share.

**Use Case**: Simple modeling when impact is roughly constant.

**Example**:
```python
from rustybt.finance.slippage import FixedSlippage

# 5 cents slippage per share
algo.set_slippage(FixedSlippage(spread=0.05))
```

**Behavior**:
```python
# Buy order: pay spread above market
if order.amount > 0:
    fill_price = bar['close'] + spread
# Sell order: receive spread below market
else:
    fill_price = bar['close'] - spread

fill_amount = order.amount  # Full fill
```

**Example Calculation**:
```python
# Market price: $100
# Spread: $0.05

# Buy 100 shares:
# Cost = 100 × $100.05 = $10,005

# Sell 100 shares:
# Proceeds = 100 × $99.95 = $9,995

# Round-trip cost: $10,005 - $9,995 = $10 slippage
```

### FixedBasisPointsSlippage

Apply percentage-based slippage.

**Use Case**: When market impact scales with price (most assets).

**Example**:
```python
from rustybt.finance.slippage import FixedBasisPointsSlippage

# 10 basis points = 0.10% slippage
algo.set_slippage(FixedBasisPointsSlippage(basis_points=10))
```

**Behavior**:
```python
slippage_pct = basis_points / 10000

# Buy order
if order.amount > 0:
    fill_price = bar['close'] * (1 + slippage_pct)
# Sell order
else:
    fill_price = bar['close'] * (1 - slippage_pct)

fill_amount = order.amount  # Full fill
```

**Example Calculation**:
```python
# Market price: $100
# Basis points: 10 (0.10%)

# Buy 100 shares:
# Cost = 100 × ($100 × 1.001) = $10,010

# Sell 100 shares:
# Proceeds = 100 × ($100 × 0.999) = $9,990

# Round-trip cost: $10,010 - $9,990 = $20 slippage (0.20%)
```

**Advantage**: Scales appropriately with price (10 bps on $10 stock ≠ 10 bps on $1000 stock).

### VolumeShareSlippage (Recommended)

Most realistic model: combines volume limits and price impact.

**Use Case**: Default for most strategies, especially with large orders.

**Example**:
```python
from rustybt.finance.slippage import VolumeShareSlippage

algo.set_slippage(VolumeShareSlippage(
    volume_limit=0.025,      # Max 2.5% of bar volume
    price_impact=0.10        # 10% price impact
))
```

**Parameters**:
- `volume_limit`: Max fraction of bar volume (default: 0.025 for equities, 0.05 for futures)
- `price_impact`: Price impact coefficient (default: 0.10)

**Behavior**:

1. **Volume Constraint**:
   ```python
   max_fill_amount = min(
       order.open_amount,
       bar['volume'] * volume_limit
   )
   ```

2. **Price Impact**:
   ```python
   volume_share = fill_amount / bar['volume']
   impact = price_impact * volume_share ** 2

   # Buy order
   if order.amount > 0:
       fill_price = bar['close'] * (1 + impact)
   # Sell order
   else:
       fill_price = bar['close'] * (1 - impact)
   ```

**Example Calculation**:
```python
# Market price: $100
# Bar volume: 1,000,000 shares
# Order: Buy 30,000 shares
# volume_limit: 0.025 (2.5%)
# price_impact: 0.10

# Max fill this bar:
max_fill = 1,000,000 × 0.025 = 25,000 shares

# Volume share:
volume_share = 25,000 / 1,000,000 = 0.025

# Price impact:
impact = 0.10 × (0.025) ** 2 = 0.0000625 (0.00625%)

# Fill price:
fill_price = $100 × 1.0000625 = $100.00625

# This bar fills 25,000 shares
# Remaining 5,000 shares carried to next bar
```

**Partial Fill Handling**:
```python
# Order for 100,000 shares, volume allows 25,000 per bar

# Bar 1: Fill 25,000 @ $100.00625
# Bar 2: Fill 25,000 @ $100.50  # Price moved
# Bar 3: Fill 25,000 @ $101.00
# Bar 4: Fill 25,000 @ $100.75
# Total filled: 100,000
# Average price: $100.5653 (vs $100 without slippage)
```

### VolatilityVolumeShare

Volume share slippage adjusted for volatility.

**Use Case**: Assets with varying volatility (options, crypto).

**Example**:
```python
from rustybt.finance.slippage import VolatilityVolumeShare

algo.set_slippage(VolatilityVolumeShare(
    volume_limit=0.025,
    volatility_window=20  # Days for volatility calculation
))
```

**Behavior**:
```python
# Calculate historical volatility
returns = price_history.pct_change()
volatility = returns.std() * sqrt(252)  # Annualized

# Adjust price impact based on volatility
adjusted_impact = base_impact * (volatility / 0.20)  # Normalize to 20% vol

# Higher volatility → higher slippage
```

## Asset-Specific Slippage

Configure different slippage for different asset types.

```python
from rustybt.finance.slippage import PerAssetSlippage, VolumeShareSlippage, FixedSlippage
from rustybt.assets import Equity, Future

# Create asset-specific models
slippage = PerAssetSlippage(
    default=VolumeShareSlippage(volume_limit=0.025),
    asset_types={
        Equity: VolumeShareSlippage(volume_limit=0.025, price_impact=0.10),
        Future: VolumeShareSlippage(volume_limit=0.05, price_impact=0.05)
    }
)

algo.set_slippage(slippage)
```

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
- [Volume Share Slippage](../execution/fills.md) - Detailed fill processing
- [Order Types](../order-types.md) - How order types affect slippage
- [Transaction Costs Overview](README.md) - Complete cost modeling guide

## Next Steps

1. Study [Commission Models](commissions.md) for complete cost modeling
2. Review [Fill Processing](../execution/fills.md) for execution details
3. Test [Sensitivity Analysis](../workflows/examples.md) with varying slippage assumptions
