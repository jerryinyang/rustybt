# Commission Models

Complete guide to commission and fee modeling in RustyBT.

## Overview

Commission models calculate the cost of executing trades. RustyBT supports multiple commission structures to match real broker pricing:

- **Per-Share**: Fixed cost per share (US equities)
- **Per-Trade**: Fixed cost per trade
- **Per-Dollar**: Percentage of trade value
- **Per-Contract**: Fixed cost per futures contract
- **Tiered**: Volume-based pricing tiers
- **Maker-Taker**: Exchange fee rebate system

## Why Model Commissions?

Commissions directly impact strategy profitability, especially for high-frequency strategies. Accurately modeling commission costs in backtesting ensures realistic performance expectations.

## Custom Commission Models

### Example: Time-of-Day Based Commissions

```python
from rustybt.finance.commission import CommissionModel

class TimeBasedCommission(CommissionModel):
    """Higher commission during market open/close."""

    def __init__(self, base_cost=0.001, peak_multiplier=1.5):
        self.base_cost = base_cost
        self.peak_multiplier = peak_multiplier

    def calculate(self, order, transaction):
        # Base commission
        commission = abs(transaction.amount) * self.base_cost

        # Check if during peak hours
        hour = transaction.dt.hour
        minute = transaction.dt.minute

        if (hour == 9 and minute < 30) or (hour == 15 and minute >= 30):
            # First/last 30 minutes: higher cost
            commission *= self.peak_multiplier

        # Apply minimum
        return max(commission, 1.0)
```

### Example: Volume Discount Commission

```python
class VolumeDiscountCommission(CommissionModel):
    """Commission decreases with higher monthly volume."""

    def __init__(self, base_cost=0.005):
        self.base_cost = base_cost
        self.monthly_volume = 0
        self.current_month = None

    def calculate(self, order, transaction):
        # Reset monthly volume at month start
        current_month = transaction.dt.month
        if current_month != self.current_month:
            self.monthly_volume = 0
            self.current_month = current_month

        # Update volume
        self.monthly_volume += abs(transaction.amount)

        # Calculate discount based on volume
        if self.monthly_volume > 1000000:
            discount = 0.6  # 40% off
        elif self.monthly_volume > 500000:
            discount = 0.75  # 25% off
        elif self.monthly_volume > 100000:
            discount = 0.9  # 10% off
        else:
            discount = 1.0  # No discount

        commission = abs(transaction.amount) * self.base_cost * discount
        return max(commission, 1.0)
```

### Example: Commission with Payment for Order Flow

```python
class PFOFCommission(CommissionModel):
    """Zero commission with price improvement/degradation from PFOF."""

    def __init__(self, avg_price_degradation=0.0001):
        """
        Parameters
        ----------
        avg_price_degradation : float
            Average price degradation as fraction (e.g., 0.0001 = 0.01%)
        """
        self.degradation = avg_price_degradation

    def calculate(self, order, transaction):
        # Zero explicit commission
        explicit_commission = 0.0

        # But account for implicit cost via degraded execution
        # (this would typically be modeled in slippage, but shown here for illustration)
        trade_value = abs(transaction.amount * transaction.price)
        implicit_cost = trade_value * self.degradation

        # Return explicit commission only
        # (implicit cost handled elsewhere)
        return explicit_commission
```

## Commission Analysis

### Calculate Total Commission Impact

```python
class CommissionAnalysis(TradingAlgorithm):
    def analyze(self, context, perf):
        """Analyze commission impact on returns."""
        total_commission = perf.orders['commission'].sum()
        final_value = perf.portfolio_value[-1]
        initial_value = perf.portfolio_value[0]

        # Calculate returns with and without commissions
        actual_return = (final_value - initial_value) / initial_value
        commission_impact = total_commission / initial_value

        print(f"Total commissions paid: ${total_commission:,.2f}")
        print(f"Commission impact: {commission_impact:.2%}")
        print(f"Actual return: {actual_return:.2%}")
        print(f"Return without commissions: {actual_return + commission_impact:.2%}")
```

### Compare Commission Models

```python
models = [
    ('Zero Commission', NoCommission()),
    ('$0.001/share', PerShare(cost=0.001, min_trade_cost=1.0)),
    ('$0.005/share', PerShare(cost=0.005, min_trade_cost=1.0)),
    ('$4.95/trade', PerTrade(cost=4.95)),
]

results = {}
for name, commission_model in models:
    algo = MyStrategy()
    algo.set_commission(commission_model)
    perf = algo.run(start, end)

    results[name] = {
        'final_value': perf.portfolio_value[-1],
        'total_commission': perf.orders['commission'].sum()
    }

# Display results
for name, metrics in results.items():
    print(f"{name}:")
    print(f"  Final Value: ${metrics['final_value']:,.2f}")
    print(f"  Total Commission: ${metrics['total_commission']:,.2f}")
```

## Best Practices

### ✅ DO

1. **Use Realistic Commission Rates**: Match your actual broker
2. **Include All Fees**: Exchange fees, regulatory fees, etc.
3. **Account for Minimum Trade Costs**: Don't ignore minimum fees
4. **Test Commission Sensitivity**: See how costs affect strategy viability
5. **Track Commission Totals**: Monitor commission drag over time

### ❌ DON'T

1. **Use NoCommission for Backtests**: Unrealistic, overestimates performance
2. **Forget Exchange Fees**: Futures especially have significant exchange fees
3. **Ignore Maker-Taker**: Crypto strategies need accurate fee modeling
4. **Assume Zero Commission is Free**: PFOF has implicit costs
5. **Underestimate Impact**: Commissions compound over many trades

## Commission Guidelines by Broker Type

| Broker Type | Commission Model | Typical Rates |
|-------------|------------------|---------------|
| Discount (US) | PerShare | $0.001-$0.005/share, $1 min |
| Zero-Commission | NoCommission or PerTrade(0) | $0 explicit |
| Traditional | PerTrade | $4.95-$9.99/trade |
| Futures | PerContract | $0.50-$2.50/contract + exchange |
| Crypto Exchange | MakerTakerFee | 0.1%-0.6% taker, -0.01%-0.4% maker |
| Institutional | PerDollar or Tiered | 0.10%-0.30% (negotiated) |

## Related Documentation

- [Slippage Models](slippage.md) - Price impact and execution costs
- Borrow Costs (Coming soon) - Short selling costs
- Financing Costs (Coming soon) - Overnight and leverage fees
- Transaction Costs - Complete cost modeling

## Next Steps

1. Review [Slippage Models](slippage.md) for complete cost picture
2. Study Borrow Costs (Coming soon) for short selling
3. Analyze [Commission Impact](../workflows/examples.md) on your strategies
