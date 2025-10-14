# Borrow Costs and Short Selling

Complete guide to modeling borrow costs for short selling in RustyBT.

## Overview

When short selling, traders must borrow shares and pay fees to the lender. RustyBT models these costs to provide realistic short selling simulations:

- **Borrow Fee**: Daily or annual percentage fee on borrowed shares
- **Hard-to-Borrow (HTB) Premium**: Additional fees for illiquid stocks
- **Rebate Rates**: Interest earned on short sale proceeds (collateral)
- **Forced Buy-Ins**: Costs when shares become unavailable

## Why Model Borrow Costs?

**Without borrow cost modeling**:
- ✗ Short selling appears "free"
- ✗ Overestimates profitability of short strategies
- ✗ Ignores major cost component (can exceed 50% annualized for HTB stocks)

**With borrow costs**:
- ✓ Realistic short strategy performance
- ✓ Accurate cost of carry for short positions
- ✓ Better risk-adjusted returns
- ✓ Proper comparison of long vs short strategies

## Borrow Fee Basics

### Annual Borrow Rate

Expressed as annual percentage of stock value.

```python
# Annual borrow rate examples:
easy_to_borrow = 0.005   # 0.5% per year (typical large cap)
moderate = 0.05          # 5% per year
hard_to_borrow = 0.25    # 25% per year
extreme_htb = 1.00       # 100%+ per year (short squeeze risk)

# Daily borrow cost calculation:
daily_borrow_rate = annual_rate / 365
daily_cost = position_value * daily_borrow_rate

# Example: $100,000 short at 25% annual rate
# Daily cost = $100,000 × (0.25 / 365) = $68.49 per day
```

### Borrow Cost Model

```python
from rustybt.finance.costs import BorrowCost

class SimpleBorrowCost(BorrowCost):
    """Simple borrow cost model with fixed annual rate."""

    def __init__(self, annual_rate=0.005):
        """
        Parameters
        ----------
        annual_rate : float
            Annual borrow rate as decimal (e.g., 0.005 = 0.5%)
        """
        self.annual_rate = annual_rate
        self.daily_rate = annual_rate / 365

    def calculate(self, asset, position_value, dt):
        """Calculate daily borrow cost.

        Parameters
        ----------
        asset : Asset
            Borrowed asset
        position_value : float
            Absolute value of short position
        dt : pd.Timestamp
            Current date

        Returns
        -------
        cost : float
            Daily borrow cost
        """
        if position_value <= 0:
            return 0.0  # No cost for long positions

        daily_cost = position_value * self.daily_rate
        return daily_cost

# Usage:
algo.set_borrow_cost(SimpleBorrowCost(annual_rate=0.01))  # 1% annual
```

## Asset-Specific Borrow Rates

Different stocks have different borrow rates based on availability.

### Dynamic Borrow Rates

```python
class AssetSpecificBorrowCost(BorrowCost):
    """Asset-specific borrow rates."""

    def __init__(self, default_rate=0.01):
        """
        Parameters
        ----------
        default_rate : float
            Default annual borrow rate
        """
        self.default_rate = default_rate
        self.asset_rates = {}  # Custom rates by asset

    def set_borrow_rate(self, asset, annual_rate):
        """Set custom borrow rate for specific asset."""
        self.asset_rates[asset] = annual_rate

    def calculate(self, asset, position_value, dt):
        """Calculate borrow cost with asset-specific rate."""
        if position_value <= 0:
            return 0.0

        # Get rate for this asset
        annual_rate = self.asset_rates.get(asset, self.default_rate)
        daily_rate = annual_rate / 365

        return position_value * daily_rate

# Usage:
borrow_cost = AssetSpecificBorrowCost(default_rate=0.005)

# Set higher rate for hard-to-borrow stocks
borrow_cost.set_borrow_rate(symbol('GME'), 0.80)   # 80% annual (HTB)
borrow_cost.set_borrow_rate(symbol('TSLA'), 0.15)  # 15% annual
borrow_cost.set_borrow_rate(symbol('AAPL'), 0.003) # 0.3% annual (easy)

algo.set_borrow_cost(borrow_cost)
```

### Market Cap Based Rates

Typical borrow rates by market capitalization.

```python
class MarketCapBorrowCost(BorrowCost):
    """Borrow rates based on market capitalization."""

    def __init__(self):
        # Typical rates by market cap
        self.rate_by_market_cap = {
            'mega': 0.003,    # $200B+ (0.3%)
            'large': 0.005,   # $10B-$200B (0.5%)
            'mid': 0.02,      # $2B-$10B (2%)
            'small': 0.05,    # $300M-$2B (5%)
            'micro': 0.15,    # < $300M (15%)
        }

    def get_market_cap_tier(self, asset):
        """Determine market cap tier for asset."""
        market_cap = asset.market_cap

        if market_cap >= 200e9:
            return 'mega'
        elif market_cap >= 10e9:
            return 'large'
        elif market_cap >= 2e9:
            return 'mid'
        elif market_cap >= 300e6:
            return 'small'
        else:
            return 'micro'

    def calculate(self, asset, position_value, dt):
        """Calculate borrow cost based on market cap."""
        if position_value <= 0:
            return 0.0

        tier = self.get_market_cap_tier(asset)
        annual_rate = self.rate_by_market_cap[tier]
        daily_rate = annual_rate / 365

        return position_value * daily_rate
```

## Time-Varying Borrow Rates

Borrow rates change over time based on supply/demand.

### Historical Borrow Rate Data

```python
import pandas as pd

class HistoricalBorrowCost(BorrowCost):
    """Use historical borrow rate data."""

    def __init__(self, borrow_rate_data):
        """
        Parameters
        ----------
        borrow_rate_data : pd.DataFrame
            Historical borrow rates indexed by date
            Columns: asset symbols
            Values: annual borrow rates
        """
        self.borrow_rate_data = borrow_rate_data
        self.default_rate = 0.01

    def calculate(self, asset, position_value, dt):
        """Calculate borrow cost using historical rates."""
        if position_value <= 0:
            return 0.0

        # Look up historical borrow rate
        if asset.symbol in self.borrow_rate_data.columns:
            try:
                annual_rate = self.borrow_rate_data.loc[dt, asset.symbol]
            except KeyError:
                annual_rate = self.default_rate
        else:
            annual_rate = self.default_rate

        daily_rate = annual_rate / 365
        return position_value * daily_rate

# Load historical borrow rate data
borrow_rates = pd.read_csv('borrow_rates.csv', index_col='date', parse_dates=True)
algo.set_borrow_cost(HistoricalBorrowCost(borrow_rates))
```

## Short Rebate Rates

Interest earned on collateral from short sales.

### Rebate Model

```python
class ShortRebate(BorrowCost):
    """Model both borrow costs and rebate interest."""

    def __init__(self, borrow_rate=0.01, rebate_rate=0.02):
        """
        Parameters
        ----------
        borrow_rate : float
            Annual rate paid to borrow shares
        rebate_rate : float
            Annual rate earned on short sale proceeds
        """
        self.borrow_rate = borrow_rate
        self.rebate_rate = rebate_rate

    def calculate(self, asset, position_value, dt):
        """Calculate net borrowing cost (borrow - rebate)."""
        if position_value <= 0:
            return 0.0

        # Daily rates
        daily_borrow = (self.borrow_rate / 365) * position_value
        daily_rebate = (self.rebate_rate / 365) * position_value

        # Net cost = borrow cost - rebate interest
        net_cost = daily_borrow - daily_rebate

        return max(net_cost, 0)  # Can't be negative

# Example with typical rates:
# Borrow cost: 0.5% annual
# Rebate rate: 2.0% annual (on collateral)
# Net cost: -1.5% (actually earning money on short!)

algo.set_borrow_cost(ShortRebate(
    borrow_rate=0.005,   # 0.5% to borrow
    rebate_rate=0.02     # 2% rebate on proceeds
))
```

## Hard-to-Borrow (HTB) Scenarios

### Availability-Based Costs

```python
class HTBBorrowCost(BorrowCost):
    """Model hard-to-borrow scenarios."""

    def __init__(self):
        self.base_rate = 0.005  # 0.5% base
        self.htb_threshold = 0.02  # 2% of shares outstanding
        self.htb_premium = 0.20  # Additional 20% for HTB

    def calculate(self, asset, position_value, dt):
        """Calculate with HTB premium if applicable."""
        if position_value <= 0:
            return 0.0

        # Check if stock is hard to borrow
        shares_outstanding = asset.shares_outstanding
        short_interest = self.get_short_interest(asset, dt)
        short_interest_ratio = short_interest / shares_outstanding

        if short_interest_ratio > self.htb_threshold:
            # Apply HTB premium
            annual_rate = self.base_rate + self.htb_premium
        else:
            annual_rate = self.base_rate

        daily_rate = annual_rate / 365
        return position_value * daily_rate

    def get_short_interest(self, asset, dt):
        """Get current short interest for asset."""
        # Would query from data source
        pass
```

### Forced Buy-In Costs

```python
class ForcedBuyIn(BorrowCost):
    """Model risk of forced buy-ins for HTB stocks."""

    def __init__(self, buyin_probability=0.01, buyin_premium=0.02):
        """
        Parameters
        ----------
        buyin_probability : float
            Daily probability of forced buy-in
        buyin_premium : float
            Premium paid when forced to buy back
        """
        self.buyin_probability = buyin_probability
        self.buyin_premium = buyin_premium
        self.base_rate = 0.01

    def calculate(self, asset, position_value, dt):
        """Calculate expected cost including buy-in risk."""
        if position_value <= 0:
            return 0.0

        # Base borrow cost
        daily_borrow = (self.base_rate / 365) * position_value

        # Expected buy-in cost
        # = probability × premium × position_value
        expected_buyin_cost = (
            self.buyin_probability * self.buyin_premium * position_value
        )

        total_cost = daily_borrow + expected_buyin_cost
        return total_cost
```

## Strategy Integration

### Track Borrow Costs in Strategy

```python
class ShortStrategy(TradingAlgorithm):
    def initialize(self, context):
        # Set borrow cost model
        self.set_borrow_cost(AssetSpecificBorrowCost(default_rate=0.01))

        context.total_borrow_costs = 0.0
        context.asset = symbol('XYZ')

    def handle_data(self, context, data):
        # Short selling strategy logic
        position = context.portfolio.positions.get(context.asset)

        if position and position.amount < 0:
            # Track borrow costs for short position
            position_value = abs(position.amount * position.last_sale_price)
            daily_borrow_cost = self.calculate_borrow_cost(
                context.asset, position_value, context.datetime
            )

            context.total_borrow_costs += daily_borrow_cost

            self.log.info(
                f"Borrow cost: ${daily_borrow_cost:.2f} "
                f"(Total: ${context.total_borrow_costs:.2f})"
            )

    def analyze(self, context, perf):
        """Report total borrow costs."""
        print(f"Total borrow costs: ${context.total_borrow_costs:,.2f}")

        total_pnl = perf.portfolio_value[-1] - perf.portfolio_value[0]
        print(f"Total P&L: ${total_pnl:,.2f}")
        print(f"P&L after borrow costs: ${total_pnl - context.total_borrow_costs:,.2f}")
```

## Typical Borrow Rates

### By Asset Class

| Asset Type | Typical Annual Rate | Notes |
|------------|---------------------|-------|
| Large Cap Stocks | 0.3% - 1% | Easy to borrow, liquid |
| Mid Cap Stocks | 1% - 5% | Moderate availability |
| Small Cap Stocks | 5% - 15% | Limited availability |
| Penny Stocks | 15% - 50%+ | Very hard to borrow |
| ETFs | 0.1% - 0.5% | Very easy to borrow |
| Crypto | Varies | 1% - 100%+ depending on exchange |

### By Short Interest

| Short Interest % | Typical Rate | Classification |
|------------------|--------------|----------------|
| 0% - 2% | 0.3% - 1% | Easy to borrow |
| 2% - 5% | 1% - 5% | Moderate |
| 5% - 10% | 5% - 15% | Hard to borrow (HTB) |
| 10% - 20% | 15% - 50% | Very HTB |
| 20%+ | 50% - 1000%+ | Extreme HTB, squeeze risk |

## Best Practices

### ✅ DO

1. **Use Realistic Rates**: Match actual broker rates for your asset class
2. **Consider Market Conditions**: Borrow rates spike during short squeezes
3. **Track Total Costs**: Monitor cumulative borrow costs over time
4. **Factor Into Sizing**: Reduce position size for high borrow cost stocks
5. **Monitor Availability**: Check short interest and availability regularly

### ❌ DON'T

1. **Ignore Borrow Costs**: Can eliminate strategy profitability
2. **Use Same Rate for All**: Rates vary significantly by asset
3. **Forget Rebates**: Can offset some or all borrow costs
4. **Overlook HTB Risk**: Forced buy-ins can be very expensive
5. **Assume Static Rates**: Borrow costs change based on supply/demand

## Example: Complete Short Strategy with Costs

```python
class RealisticShortStrategy(TradingAlgorithm):
    def initialize(self, context):
        # Configure realistic borrow costs
        borrow_cost = AssetSpecificBorrowCost(default_rate=0.01)

        # Set rates for specific stocks
        borrow_cost.set_borrow_rate(symbol('AAPL'), 0.003)  # Easy
        borrow_cost.set_borrow_rate(symbol('TSLA'), 0.15)   # HTB

        self.set_borrow_cost(borrow_cost)

        # Configure realistic commissions
        self.set_commission(PerShare(cost=0.005, min_trade_cost=1.0))

        # Configure realistic slippage
        self.set_slippage(VolumeShareSlippage(volume_limit=0.025))

        context.target_short = symbol('TSLA')
        context.max_borrow_rate = 0.20  # Don't short if > 20% annual

    def handle_data(self, context, data):
        asset = context.target_short

        # Check borrow rate before shorting
        annual_rate = self.get_borrow_rate(asset)

        if annual_rate > context.max_borrow_rate:
            self.log.warning(
                f"Skipping {asset.symbol}: borrow rate {annual_rate:.1%} "
                f"exceeds max {context.max_borrow_rate:.1%}"
            )
            return

        # Short signal
        if self.should_short(context, data, asset):
            # Calculate position size accounting for borrow costs
            # Higher borrow costs → smaller position
            base_size = 100
            cost_adjustment = 1.0 - (annual_rate / 0.20)  # Scale by rate
            adjusted_size = int(base_size * cost_adjustment)

            order(asset, -adjusted_size)

            self.log.info(
                f"Shorting {adjusted_size} shares at "
                f"{annual_rate:.1%} annual borrow rate"
            )
```

## Related Documentation

- [Financing Costs](financing.md) - Overnight and leverage financing
- [Slippage Models](slippage.md) - Execution costs
- [Commission Models](commissions.md) - Transaction fees
- [Transaction Costs Overview](README.md) - Complete cost modeling

## Next Steps

1. Study [Financing Costs](financing.md) for overnight position costs
2. Review [Complete Cost Modeling](README.md) for integrated approach
3. Test short strategies with realistic borrow costs
