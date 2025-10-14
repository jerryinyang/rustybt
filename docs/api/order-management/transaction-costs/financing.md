# Financing Costs

Complete guide to overnight financing and margin costs in RustyBT.

## Overview

Financing costs apply when:
- Holding positions overnight with borrowed funds (margin)
- Using leverage (long or short)
- Holding cryptocurrency positions with perpetual swaps

RustyBT models these costs to provide realistic multi-day strategy performance.

## Types of Financing Costs

1. **Margin Interest**: Cost to borrow cash for leveraged long positions
2. **Short Rebate**: Interest earned/paid on short sale proceeds
3. **Overnight Financing**: Daily holding costs (crypto, forex)
4. **Funding Rates**: Perpetual swap funding payments (crypto)

## Margin Interest

### Simple Margin Interest

Cost of borrowing to buy on margin.

```python
from rustybt.finance.costs import MarginInterest

class SimpleMarginInterest:
    """Model margin interest on leveraged positions."""

    def __init__(self, annual_rate=0.08):
        """
        Parameters
        ----------
        annual_rate : float
            Annual margin interest rate (e.g., 0.08 = 8%)
        """
        self.annual_rate = annual_rate
        self.daily_rate = annual_rate / 365

    def calculate(self, borrowed_amount, dt):
        """Calculate daily margin interest.

        Parameters
        ----------
        borrowed_amount : float
            Amount borrowed on margin
        dt : pd.Timestamp
            Current date

        Returns
        -------
        interest : float
            Daily interest cost
        """
        if borrowed_amount <= 0:
            return 0.0

        daily_interest = borrowed_amount * self.daily_rate
        return daily_interest

# Usage example:
margin_interest = SimpleMarginInterest(annual_rate=0.08)  # 8% annual

# Calculate borrowed amount
portfolio_value = 100000
positions_value = 150000  # Using leverage
cash = -50000  # Negative cash = borrowed

borrowed_amount = abs(min(cash, 0))
daily_cost = margin_interest.calculate(borrowed_amount, current_date)

# Example: $50,000 borrowed at 8% annual
# Daily cost = $50,000 × (0.08 / 365) = $10.96 per day
```

### Tiered Margin Rates

Different rates based on loan size.

```python
class TieredMarginInterest:
    """Tiered margin rates based on loan amount."""

    def __init__(self):
        # Typical broker tiered rates
        self.rate_tiers = [
            (0, 10000, 0.095),       # 0-$10k: 9.5%
            (10000, 50000, 0.085),   # $10k-$50k: 8.5%
            (50000, 100000, 0.075),  # $50k-$100k: 7.5%
            (100000, 250000, 0.065), # $100k-$250k: 6.5%
            (250000, float('inf'), 0.055) # $250k+: 5.5%
        ]

    def get_rate_for_amount(self, borrowed_amount):
        """Get applicable rate for loan amount."""
        for min_amt, max_amt, rate in self.rate_tiers:
            if min_amt <= borrowed_amount < max_amt:
                return rate
        return self.rate_tiers[-1][2]  # Default to highest tier

    def calculate(self, borrowed_amount, dt):
        """Calculate daily interest with tiered rates."""
        if borrowed_amount <= 0:
            return 0.0

        annual_rate = self.get_rate_for_amount(borrowed_amount)
        daily_rate = annual_rate / 365
        daily_interest = borrowed_amount * daily_rate

        return daily_interest
```

### Broker-Specific Rates

Match your actual broker's margin rates.

```python
class BrokerMarginRates:
    """Margin rates for specific brokers."""

    BROKER_RATES = {
        'Interactive Brokers': {
            'base_rate': 0.0683,  # 6.83% (benchmark + 1.5%)
            'minimum': 10000,     # Min $10k for margin
        },
        'TD Ameritrade': {
            'base_rate': 0.1075,  # 10.75%
            'minimum': 2000,      # Min $2k for margin
        },
        'Fidelity': {
            'base_rate': 0.0825,  # 8.25%
            'minimum': 2000,
        },
        'Schwab': {
            'base_rate': 0.0875,  # 8.75%
            'minimum': 2000,
        },
    }

    def __init__(self, broker_name='Interactive Brokers'):
        """
        Parameters
        ----------
        broker_name : str
            Name of broker for rate lookup
        """
        if broker_name not in self.BROKER_RATES:
            raise ValueError(f"Unknown broker: {broker_name}")

        self.broker = broker_name
        self.config = self.BROKER_RATES[broker_name]
        self.annual_rate = self.config['base_rate']
        self.daily_rate = self.annual_rate / 365

    def calculate(self, borrowed_amount, dt):
        """Calculate interest using broker's rates."""
        if borrowed_amount < self.config['minimum']:
            return 0.0  # Below minimum for margin

        return borrowed_amount * self.daily_rate
```

## Overnight Financing

### Forex Overnight Swap

Rollover interest for forex positions.

```python
class ForexOvernightSwap:
    """Model forex overnight financing (swap/rollover)."""

    def __init__(self):
        # Interest rate differentials (as of example date)
        self.interest_rates = {
            'USD': 0.055,  # 5.5%
            'EUR': 0.04,   # 4.0%
            'GBP': 0.05,   # 5.0%
            'JPY': -0.001, # -0.1%
            'CHF': 0.015,  # 1.5%
        }

    def calculate_swap(self, base_currency, quote_currency,
                      position_value, is_long):
        """Calculate overnight swap rate.

        Parameters
        ----------
        base_currency : str
            Base currency (e.g., 'EUR' in EUR/USD)
        quote_currency : str
            Quote currency (e.g., 'USD' in EUR/USD)
        position_value : float
            Position size in quote currency
        is_long : bool
            True if long position, False if short

        Returns
        -------
        swap : float
            Daily swap cost/credit
        """
        base_rate = self.interest_rates.get(base_currency, 0)
        quote_rate = self.interest_rates.get(quote_currency, 0)

        # Interest rate differential
        rate_diff = base_rate - quote_rate

        # Long position: pay if base rate < quote rate
        # Short position: opposite
        if is_long:
            net_rate = rate_diff
        else:
            net_rate = -rate_diff

        # Daily swap
        daily_swap = (position_value * net_rate) / 365

        return daily_swap

# Example: Long EUR/USD
# EUR rate: 4%, USD rate: 5.5%
# Rate differential: 4% - 5.5% = -1.5%
# Position: $100,000
# Daily cost = $100,000 × (-0.015) / 365 = -$4.11 per day
```

### Crypto Overnight Fees

Some exchanges charge overnight holding fees.

```python
class CryptoOvernightFee:
    """Model overnight holding fees for crypto."""

    def __init__(self, daily_rate=0.0001):
        """
        Parameters
        ----------
        daily_rate : float
            Daily holding fee (e.g., 0.0001 = 0.01% per day)
        """
        self.daily_rate = daily_rate

    def calculate(self, position_value, is_leveraged=False):
        """Calculate overnight fee.

        Parameters
        ----------
        position_value : float
            Value of position
        is_leveraged : bool
            Whether position is leveraged (higher fees)

        Returns
        -------
        fee : float
            Overnight holding fee
        """
        rate = self.daily_rate

        # Higher fees for leveraged positions
        if is_leveraged:
            rate *= 3  # Typical 3x multiplier

        return position_value * rate
```

## Perpetual Swap Funding

### Funding Rate Mechanism

Crypto perpetual swaps use funding rates to keep price near spot.

```python
class FundingRateModel:
    """Model crypto perpetual swap funding rates."""

    def __init__(self, funding_interval_hours=8):
        """
        Parameters
        ----------
        funding_interval_hours : int
            Hours between funding payments (typically 8)
        """
        self.funding_interval_hours = funding_interval_hours
        self.payments_per_day = 24 / funding_interval_hours

    def calculate_funding(self, position_value, funding_rate, is_long):
        """Calculate funding payment.

        Parameters
        ----------
        position_value : float
            Notional value of position
        funding_rate : float
            Current funding rate (e.g., 0.0001 = 0.01%)
        is_long : bool
            True if long, False if short

        Returns
        -------
        payment : float
            Funding payment (positive = pay, negative = receive)
        """
        # Funding payment
        payment = position_value * funding_rate

        # Long pays short when funding rate is positive
        # Short pays long when funding rate is negative
        if is_long:
            return payment  # Pay if positive
        else:
            return -payment  # Receive if positive

    def calculate_daily_funding(self, position_value, avg_funding_rate, is_long):
        """Calculate expected daily funding."""
        payment_per_interval = self.calculate_funding(
            position_value, avg_funding_rate, is_long
        )

        daily_payment = payment_per_interval * self.payments_per_day
        return daily_payment

# Example: Long BTC perpetual
# Position: $100,000
# Funding rate: 0.01% (0.0001)
# Funding interval: 8 hours (3x per day)
# Payment per interval = $100,000 × 0.0001 = $10
# Daily funding = $10 × 3 = $30 per day (paid to shorts)
```

### Historical Funding Rates

Use actual historical funding rate data.

```python
import pandas as pd

class HistoricalFundingRates:
    """Use historical funding rate data."""

    def __init__(self, funding_data):
        """
        Parameters
        ----------
        funding_data : pd.DataFrame
            Historical funding rates indexed by timestamp
            Columns: trading pairs (e.g., 'BTC/USD')
        """
        self.funding_data = funding_data
        self.funding_interval_hours = 8
        self.payments_per_day = 3

    def get_funding_rate(self, asset, dt):
        """Get funding rate at specific time."""
        try:
            rate = self.funding_data.loc[dt, asset.symbol]
            return rate
        except KeyError:
            return 0.0  # Default to 0 if no data

    def calculate(self, asset, position_value, dt, is_long):
        """Calculate funding payment using historical data."""
        funding_rate = self.get_funding_rate(asset, dt)

        payment = position_value * funding_rate

        if is_long:
            return payment
        else:
            return -payment
```

## Combined Financing Model

### All-in-One Financing

```python
class ComprehensiveFinancing:
    """Combined financing costs for all position types."""

    def __init__(self,
                 margin_rate=0.08,
                 borrow_rate=0.01,
                 funding_model=None):
        """
        Parameters
        ----------
        margin_rate : float
            Annual margin interest rate
        borrow_rate : float
            Annual short borrow rate
        funding_model : FundingRateModel
            Perpetual swap funding model
        """
        self.margin_rate = margin_rate / 365  # Daily
        self.borrow_rate = borrow_rate / 365  # Daily
        self.funding_model = funding_model

    def calculate_daily_financing(self, context, dt):
        """Calculate all financing costs for current positions.

        Returns
        -------
        total_cost : float
            Net daily financing cost
        """
        total_cost = 0.0

        # 1. Margin interest on borrowed cash
        cash = context.portfolio.cash
        if cash < 0:
            borrowed_amount = abs(cash)
            margin_interest = borrowed_amount * self.margin_rate
            total_cost += margin_interest

        # 2. Borrow costs and rebates for short positions
        for asset, position in context.portfolio.positions.items():
            position_value = abs(position.amount * position.last_sale_price)

            if position.amount < 0:  # Short position
                # Borrow cost
                borrow_cost = position_value * self.borrow_rate
                total_cost += borrow_cost

                # Rebate interest (earned on proceeds)
                # Typically lower than borrow cost, net is still a cost

            # 3. Perpetual swap funding (if applicable)
            if self.funding_model and hasattr(asset, 'is_perpetual'):
                if asset.is_perpetual:
                    funding = self.funding_model.calculate(
                        asset, position_value, dt, position.amount > 0
                    )
                    total_cost += funding

        return total_cost
```

## Strategy Integration

### Track Financing Costs

```python
class FinancingAwareStrategy(TradingAlgorithm):
    def initialize(self, context):
        # Setup financing model
        context.financing = ComprehensiveFinancing(
            margin_rate=0.08,
            borrow_rate=0.015
        )

        context.cumulative_financing = 0.0
        context.daily_financing_history = []

    def handle_data(self, context, data):
        # Calculate financing costs for current positions
        daily_financing = context.financing.calculate_daily_financing(
            context, context.datetime
        )

        # Track cumulative costs
        context.cumulative_financing += daily_financing
        context.daily_financing_history.append({
            'date': context.datetime,
            'daily_cost': daily_financing,
            'cumulative': context.cumulative_financing
        })

        self.log.info(
            f"Daily financing: ${daily_financing:.2f}, "
            f"Cumulative: ${context.cumulative_financing:.2f}"
        )

        # Adjust strategy for high financing costs
        if daily_financing > 100:  # $100/day threshold
            self.log.warning("High financing costs, reducing leverage")
            # Reduce positions...

    def analyze(self, context, perf):
        """Report financing impact on performance."""
        total_return = perf.returns[-1]
        total_financing = context.cumulative_financing
        starting_value = perf.portfolio_value[0]

        financing_drag = total_financing / starting_value

        print(f"\nFinancing Cost Analysis:")
        print(f"Total Financing Costs: ${total_financing:,.2f}")
        print(f"Financing Drag: {financing_drag:.2%}")
        print(f"Total Return: {total_return:.2%}")
        print(f"Return After Financing: {total_return - financing_drag:.2%}")
```

## Typical Rates Reference

### Margin Interest Rates (as of 2024)

| Broker | Base Rate | Tiered | Notes |
|--------|-----------|--------|-------|
| Interactive Brokers | 6.83% | Yes | Benchmark + 1.5% |
| TD Ameritrade | 10.75% | Limited | Higher for small accounts |
| Fidelity | 8.25% | Yes | Based on debit balance |
| Schwab | 8.75% | Yes | Negotiable for large accounts |
| Robinhood | 5.00% | No | Robinhood Gold members only |

### Crypto Funding Rates

| Pair | Typical Range | Notes |
|------|---------------|-------|
| BTC/USD | -0.05% to +0.05% | Usually positive (longs pay) |
| ETH/USD | -0.05% to +0.10% | Can spike during volatility |
| Altcoins | -0.20% to +0.50% | Higher variability |
| During Bull Markets | +0.10% to +0.50% | Elevated positive rates |
| During Bear Markets | -0.10% to +0.10% | Can go negative (shorts pay) |

## Best Practices

### ✅ DO

1. **Model All Financing Costs**: Margin, borrow, and funding rates
2. **Use Realistic Rates**: Match your actual broker/exchange
3. **Track Daily**: Monitor cumulative impact over time
4. **Adjust for Leverage**: Higher leverage = higher costs
5. **Factor Into Returns**: Report net-of-financing performance

### ❌ DON'T

1. **Ignore Financing**: Can be 5-10% annual drag
2. **Use Static Rates**: Rates change with market conditions
3. **Overlook Compounding**: Daily costs compound significantly
4. **Forget Time Decay**: Longer holds = more financing
5. **Assume It's Free**: No leverage is truly "free"

## Complete Example

```python
class RealisticLeveragedStrategy(TradingAlgorithm):
    def initialize(self, context):
        # Configure all transaction costs
        self.set_commission(PerShare(cost=0.005, min_trade_cost=1.0))
        self.set_slippage(VolumeShareSlippage(volume_limit=0.025))

        # Configure financing costs
        context.financing = ComprehensiveFinancing(
            margin_rate=0.08,      # 8% margin interest
            borrow_rate=0.015      # 1.5% short borrow rate
        )

        context.max_leverage = 2.0
        context.daily_financing_limit = 200  # Max $200/day
        context.total_financing = 0.0

    def handle_data(self, context, data):
        # Calculate current financing cost
        daily_financing = context.financing.calculate_daily_financing(
            context, context.datetime
        )
        context.total_financing += daily_financing

        # Check financing limits before trading
        if daily_financing > context.daily_financing_limit:
            self.log.error(
                f"Daily financing ${daily_financing:.2f} exceeds "
                f"limit ${context.daily_financing_limit:.2f}"
            )
            # Reduce leverage
            self.reduce_leverage(context)
            return

        # Normal trading logic
        # ... strategy code ...

    def analyze(self, context, perf):
        """Complete cost analysis."""
        # Calculate all costs
        total_commission = perf.orders['commission'].sum()
        total_financing = context.total_financing

        # Estimate slippage (difference between order price and execution)
        estimated_slippage = self.estimate_slippage(perf)

        total_costs = total_commission + total_financing + estimated_slippage

        print(f"\n{'='*60}")
        print(f"COMPLETE COST ANALYSIS")
        print(f"{'='*60}")
        print(f"Commissions:    ${total_commission:>10,.2f}")
        print(f"Slippage:       ${estimated_slippage:>10,.2f}")
        print(f"Financing:      ${total_financing:>10,.2f}")
        print(f"{'='*60}")
        print(f"Total Costs:    ${total_costs:>10,.2f}")
        print(f"{'='*60}")
```

## Related Documentation

- [Borrow Costs](borrow-costs.md) - Short selling costs
- [Slippage Models](slippage.md) - Execution costs
- [Commission Models](commissions.md) - Transaction fees
- [Transaction Costs Overview](README.md) - Complete cost modeling

## Next Steps

1. Review [Borrow Costs](borrow-costs.md) for short selling
2. Study [Complete Cost Model](README.md) for integrated approach
3. Test strategies with realistic financing costs
