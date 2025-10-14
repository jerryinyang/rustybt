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

**Impact on Returns**:
```python
# Example: 100 trades, 100 shares each, $0.001/share

Total commission = 100 trades × 100 shares × $0.001
                 = $10 per trade
                 = $1,000 total

# On $100,000 portfolio = 1.0% drag on returns
# Over time, compounds significantly!
```

## Commission Model Interface

### Base Class

```python
from rustybt.finance.commission import CommissionModel

class CommissionModel(metaclass=FinancialModelMeta):
    """Abstract base for commission models."""

    @abstractmethod
    def calculate(self, order, transaction):
        """Calculate commission for a transaction.

        Parameters
        ----------
        order : Order
            Order being filled
        transaction : Transaction
            Transaction being processed

        Returns
        -------
        commission : float
            Commission charged in dollars
        """
        raise NotImplementedError
```

## Built-in Commission Models

### NoCommission

No commission charged (testing only).

```python
from rustybt.finance.commission import NoCommission

algo.set_commission(NoCommission())
```

**⚠️ Warning**: Unrealistic for actual trading. Use only for testing.

### PerShare

Fixed cost per share (common for US equities).

**Use Case**: Interactive Brokers, TradeStation, most US brokers.

**Example**:
```python
from rustybt.finance.commission import PerShare

# $0.001 per share, $1 minimum per trade
algo.set_commission(PerShare(
    cost=0.001,           # $0.001 per share
    min_trade_cost=1.0    # $1 minimum
))
```

**Calculation**:
```python
commission = max(
    abs(transaction.amount) * cost,
    min_trade_cost
)

# Example: 100 shares @ $0.001/share
# = max(100 × $0.001, $1.00) = $1.00

# Example: 5000 shares @ $0.001/share
# = max(5000 × $0.001, $1.00) = $5.00
```

**Typical Values**:
```python
# Interactive Brokers IBKR Lite
PerShare(cost=0.0, min_trade_cost=0.0)  # $0 commission

# Interactive Brokers IBKR Pro
PerShare(cost=0.005, min_trade_cost=1.0)  # $0.005/share, $1 min

# TradeStation
PerShare(cost=0.006, min_trade_cost=0.60)  # $0.006/share, $0.60 min

# Lightspeed
PerShare(cost=0.0045, min_trade_cost=1.0)  # $0.0045/share, $1 min
```

### PerTrade

Fixed cost per trade regardless of size.

**Use Case**: Robinhood, zero-commission brokers, or flat-fee structures.

**Example**:
```python
from rustybt.finance.commission import PerTrade

# $0 per trade (zero-commission)
algo.set_commission(PerTrade(cost=0.0))

# $4.95 per trade (traditional broker)
algo.set_commission(PerTrade(cost=4.95))
```

**Calculation**:
```python
commission = cost  # Fixed cost per trade

# 100 shares = $4.95
# 1000 shares = $4.95
# 10000 shares = $4.95 (same!)
```

**Typical Values**:
```python
# Zero-commission brokers
PerTrade(cost=0.0)

# Traditional brokers (legacy pricing)
PerTrade(cost=4.95)   # E*TRADE
PerTrade(cost=6.95)   # TD Ameritrade (old)
PerTrade(cost=9.99)   # Schwab (old)
```

### PerDollar

Percentage of trade value (AUM-based or boutique brokers).

**Use Case**: Percentage-based fee structures, institutional brokers.

**Example**:
```python
from rustybt.finance.commission import PerDollar

# 0.15% of trade value
algo.set_commission(PerDollar(cost=0.0015))
```

**Calculation**:
```python
commission = abs(transaction.amount * transaction.price) * cost

# Example: 100 shares @ $100 = $10,000 trade value
# Commission = $10,000 × 0.0015 = $15.00
```

**Typical Values**:
```python
# Typical institutional rates
PerDollar(cost=0.001)   # 0.10% (10 bps)
PerDollar(cost=0.0015)  # 0.15% (15 bps)
PerDollar(cost=0.003)   # 0.30% (30 bps)
```

**Note**: Higher for small accounts, lower for large institutional accounts.

### PerContract

Fixed cost per futures contract.

**Use Case**: Futures trading (CME, ICE, Eurex).

**Example**:
```python
from rustybt.finance.commission import PerContract

# $0.85 per contract (common futures rate)
algo.set_commission(PerContract(cost=0.85))
```

**Calculation**:
```python
commission = abs(transaction.amount) * cost

# Example: 10 contracts @ $0.85/contract
# = 10 × $0.85 = $8.50
```

**Typical Values**:
```python
# Common futures commission rates
PerContract(cost=0.50)   # High-volume trader
PerContract(cost=0.85)   # Standard retail
PerContract(cost=1.50)   # Traditional broker
PerContract(cost=2.50)   # Full-service broker
```

**Include Exchange Fees**:
```python
from rustybt.finance.constants import FUTURE_EXCHANGE_FEES_BY_SYMBOL

# Automatically includes exchange fees by contract
PerContract(
    cost=0.85,
    exchange_fee=True  # Add NFA, exchange fees
)

# For ES (E-mini S&P 500):
# = $0.85 + $1.28 (CME fees) = $2.13 total per contract
```

## Tiered Commission Models

### PerShareTiered

Volume-based pricing tiers.

**Use Case**: Active traders with volume discounts.

**Example**:
```python
from rustybt.finance.commission import PerShareTiered

# Tiered pricing based on monthly volume
algo.set_commission(PerShareTiered(
    tiers=[
        (0, 10000, 0.005),           # 0-10k shares: $0.005/share
        (10000, 50000, 0.004),       # 10k-50k: $0.004/share
        (50000, 100000, 0.003),      # 50k-100k: $0.003/share
        (100000, float('inf'), 0.002) # 100k+: $0.002/share
    ],
    min_trade_cost=1.0
))
```

**Calculation**:
```python
# Cumulative volume tracked
# Commission based on current tier

# Month starts: 0 shares traded
# Trade 5000 shares: 5000 × $0.005 = $25.00
# Trade 10000 shares: 10000 × $0.004 = $40.00 (moved to tier 2)
# Trade 50000 shares: 50000 × $0.003 = $150.00 (moved to tier 3)
```

### PerDollarTiered

AUM-based or trade size-based tiers.

**Example**:
```python
from rustybt.finance.commission import PerDollarTiered

# Larger trades get better rates
algo.set_commission(PerDollarTiered(
    tiers=[
        (0, 10000, 0.003),           # < $10k: 0.30%
        (10000, 100000, 0.002),      # $10k-$100k: 0.20%
        (100000, 1000000, 0.0015),   # $100k-$1M: 0.15%
        (1000000, float('inf'), 0.001) # > $1M: 0.10%
    ]
))
```

## Maker-Taker Fee Models

### MakerTakerFee

Rebates for providing liquidity, fees for taking liquidity.

**Use Case**: Crypto exchanges, direct market access.

**Example**:
```python
from rustybt.finance.commission import MakerTakerFee

# Crypto exchange typical rates
algo.set_commission(MakerTakerFee(
    maker_rate=-0.0001,   # -0.01% rebate for limit orders
    taker_rate=0.0006     # 0.06% fee for market orders
))
```

**Calculation**:
```python
# Limit order (adds liquidity) = maker
if order.limit is not None:
    commission = trade_value * abs(maker_rate)  # Rebate!
    commission = -commission  # Negative = receive rebate

# Market order (takes liquidity) = taker
else:
    commission = trade_value * taker_rate

# Example: $10,000 trade
# Maker (limit): $10,000 × 0.0001 = -$1.00 (rebate)
# Taker (market): $10,000 × 0.0006 = $6.00 (fee)
```

**Typical Crypto Exchange Rates**:
```python
# Binance (tier 0)
MakerTakerFee(maker_rate=0.001, taker_rate=0.001)  # 0.10% / 0.10%

# Coinbase Pro (tier 0)
MakerTakerFee(maker_rate=0.004, taker_rate=0.006)  # 0.40% / 0.60%

# Kraken (tier 0)
MakerTakerFee(maker_rate=0.0016, taker_rate=0.0026)  # 0.16% / 0.26%

# FTX (was) (tier 1)
MakerTakerFee(maker_rate=0.0002, taker_rate=0.0007)  # 0.02% / 0.07%
```

## Asset-Specific Commissions

Configure different commissions by asset type.

```python
from rustybt.finance.commission import PerAssetCommission, PerShare, PerContract
from rustybt.assets import Equity, Future

# Different rates for different assets
commission = PerAssetCommission(
    default=PerShare(cost=0.005, min_trade_cost=1.0),
    asset_types={
        Equity: PerShare(cost=0.001, min_trade_cost=1.0),
        Future: PerContract(cost=0.85, exchange_fee=True)
    }
)

algo.set_commission(commission)
```

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
- [Borrow Costs](borrow-costs.md) - Short selling costs
- [Financing Costs](financing.md) - Overnight and leverage fees
- [Transaction Cost Overview](README.md) - Complete cost modeling

## Next Steps

1. Review [Slippage Models](slippage.md) for complete cost picture
2. Study [Borrow Costs](borrow-costs.md) for short selling
3. Analyze [Commission Impact](../workflows/examples.md) on your strategies
