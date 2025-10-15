# Portfolio Management System

Complete guide to RustyBT's portfolio tracking, position management, and performance monitoring.

## Overview

RustyBT provides comprehensive portfolio management for tracking:

- **Positions**: Long and short holdings with cost basis
- **Cash Management**: Available cash, buying power, margin
- **P&L Tracking**: Realized and unrealized profits/losses
- **Performance Metrics**: Returns, Sharpe ratio, drawdown
- **Multi-Strategy**: Portfolio-level aggregation and attribution

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Trading Algorithm                     │
└───────────────────┬─────────────────────────────────────┘
                    │ order(asset, amount)
                    ▼
┌─────────────────────────────────────────────────────────┐
│                    Execution System                      │
│  (Blotter → Transaction)                                 │
└───────────────────┬─────────────────────────────────────┘
                    │ transaction
                    ▼
┌─────────────────────────────────────────────────────────┐
│                  Portfolio Tracker                       │
│  ┌───────────────────────────────────────────────────┐  │
│  │ Position Management                               │  │
│  │  • Update positions                               │  │
│  │  • Track cost basis (FIFO/LIFO/AvgCost)        │  │
│  │  • Calculate P&L                                  │  │
│  └───────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────┐  │
│  │ Cash Management                                   │  │
│  │  • Track cash balance                             │  │
│  │  • Calculate buying power                         │  │
│  │  • Handle dividends                               │  │
│  └───────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────┐  │
│  │ Performance Tracking                              │  │
│  │  • Portfolio value                                │  │
│  │  • Returns (daily, cumulative)                    │  │
│  │  • Risk metrics                                   │  │
│  └───────────────────────────────────────────────────┘  │
└───────────────────┬─────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────┐
│                   Strategy Context                       │
│  context.portfolio.positions                             │
│  context.portfolio.portfolio_value                       │
│  context.portfolio.cash                                  │
└─────────────────────────────────────────────────────────┘
```

## Quick Start

### Access Portfolio in Strategy

```python
from rustybt.algorithm import TradingAlgorithm

class MyStrategy(TradingAlgorithm):
    def handle_data(self, context, data):
        # Access portfolio state
        portfolio = context.portfolio

        # Current portfolio value
        total_value = portfolio.portfolio_value

        # Available cash
        cash = portfolio.cash

        # All positions
        positions = portfolio.positions

        # Specific position
        position = positions.get(asset)
        if position:
            print(f"Holdings: {position.amount} shares")
            print(f"Cost basis: ${position.cost_basis:.2f}")
            print(f"Current value: ${position.amount * position.last_sale_price:.2f}")
```

## Portfolio Object

### Key Attributes

```python
portfolio = context.portfolio

# Portfolio-level metrics
portfolio.portfolio_value    # Total value (cash + positions)
portfolio.positions_value    # Total position value
portfolio.cash               # Available cash
portfolio.starting_cash      # Initial cash
portfolio.returns            # Total return since start
portfolio.pnl                # Total P&L (dollar amount)

# Position tracking
portfolio.positions          # Dict[Asset, Position]
portfolio.positions_exposure # Long/short exposure

# Historical tracking
portfolio.start_date         # Strategy start date
portfolio.positions_value_history  # Historical values
```

### Access Positions

```python
def handle_data(self, context, data):
    # Get all positions
    for asset, position in context.portfolio.positions.items():
        print(f"{asset.symbol}:")
        print(f"  Amount: {position.amount}")
        print(f"  Cost basis: ${position.cost_basis:.2f}")
        print(f"  Last price: ${position.last_sale_price:.2f}")

    # Check specific position
    if asset in context.portfolio.positions:
        position = context.portfolio.positions[asset]
        # Have position
    else:
        # No position
```

## Position Object

### Position Attributes

```python
position = context.portfolio.positions[asset]

# Core attributes
position.asset              # Asset object
position.amount             # Shares held (+ long, - short)
position.cost_basis         # Average cost per share
position.last_sale_price    # Current market price
position.last_sale_date     # Last price update date
```

### Position Calculations

```python
# Current market value
market_value = position.amount * position.last_sale_price

# Unrealized P&L
unrealized_pnl = (position.last_sale_price - position.cost_basis) * position.amount

# P&L percentage
pnl_pct = (position.last_sale_price / position.cost_basis - 1)

# Example:
# 100 shares @ $50 cost basis, now trading @ $55
# market_value = 100 × $55 = $5,500
# unrealized_pnl = ($55 - $50) × 100 = $500
# pnl_pct = ($55 / $50 - 1) = 10%
```

## Cost Basis Accounting

### FIFO (First-In, First-Out)

Default method: oldest shares sold first.

```python
# Trade sequence:
# 1. Buy 100 @ $50
# 2. Buy 100 @ $55
# 3. Sell 150

# FIFO:
# Sell 100 @ $50 (first lot)
# Sell 50 @ $55 (partial second lot)
# Remaining: 50 @ $55 cost basis
```

### LIFO (Last-In, First-Out)

Newest shares sold first.

```python
# Same sequence with LIFO:
# Sell 100 @ $55 (second lot)
# Sell 50 @ $50 (partial first lot)
# Remaining: 50 @ $50 cost basis
```

### Average Cost

Weighted average of all purchases.

```python
# Buy 100 @ $50 = $5,000
# Buy 100 @ $55 = $5,500
# Average cost = ($5,000 + $5,500) / 200 = $52.50/share

# Sell 150:
# Remaining: 50 @ $52.50 cost basis
```

**Note**: RustyBT currently uses FIFO by default. See Accounting Methods (Coming soon) for details.

## Cash Management

### Available Cash

```python
def handle_data(self, context, data):
    cash = context.portfolio.cash

    # Calculate maximum shares can buy
    price = data.current(asset, 'close')
    max_shares = int(cash / price)

    # Order with cash constraint
    if max_shares > 100:
        order(asset, 100)
```

### Buying Power (Margin)

```python
# With 2:1 margin
buying_power = context.portfolio.cash * 2

# Can control 2x cash value in positions
max_position_value = buying_power
```

### Cash Flow Events

```python
# Cash updated by:
# - Trade execution (cash -= fill_value + commission)
# - Dividends (cash += dividend_amount)
# - Interest (cash += interest)
# - Deposits/withdrawals (live trading)
```

## P&L Calculations

### Realized P&L

Profit/loss from closed positions.

```python
# Buy 100 @ $50 = -$5,000
# Sell 100 @ $55 = +$5,500
# Realized P&L = $5,500 - $5,000 = $500

# Tracked in transaction history
for txn in context.transactions:
    realized_pnl = txn.amount * (txn.price - position.cost_basis)
```

### Unrealized P&L

Profit/loss from open positions.

```python
def calculate_unrealized_pnl(context):
    total_unrealized = 0

    for asset, position in context.portfolio.positions.items():
        current_price = position.last_sale_price
        unrealized = (current_price - position.cost_basis) * position.amount
        total_unrealized += unrealized

    return total_unrealized
```

### Total P&L

```python
total_pnl = context.portfolio.pnl
# = realized_pnl + unrealized_pnl
# = current_portfolio_value - starting_cash
```

## Performance Metrics

### Portfolio Returns

```python
# Total return
total_return = context.portfolio.returns
# = (current_value - starting_cash) / starting_cash

# Daily return
daily_return = (today_value - yesterday_value) / yesterday_value
```

### Portfolio Value Over Time

```python
def analyze(self, context, perf):
    import matplotlib.pyplot as plt

    # Plot portfolio value
    perf.portfolio_value.plot(title='Portfolio Value')
    plt.xlabel('Date')
    plt.ylabel('Portfolio Value ($)')
    plt.show()

    # Plot returns
    perf.returns.plot(title='Cumulative Returns')
    plt.xlabel('Date')
    plt.ylabel('Return (%)')
    plt.show()
```

## Position Sizing Strategies

### Fixed Dollar Amount

```python
def handle_data(self, context, data):
    target_position_value = 10000  # $10k per position
    price = data.current(asset, 'close')
    target_shares = int(target_position_value / price)

    position = context.portfolio.positions.get(asset)
    current_shares = position.amount if position else 0

    order(asset, target_shares - current_shares)
```

### Percentage of Portfolio

```python
def handle_data(self, context, data):
    target_pct = 0.10  # 10% of portfolio
    portfolio_value = context.portfolio.portfolio_value
    target_value = portfolio_value * target_pct

    price = data.current(asset, 'close')
    target_shares = int(target_value / price)

    position = context.portfolio.positions.get(asset)
    current_shares = position.amount if position else 0

    order(asset, target_shares - current_shares)
```

### Risk-Based Position Sizing

```python
def calculate_position_size(self, context, data, asset):
    """Size position based on volatility."""
    # Calculate volatility
    prices = data.history(asset, 'close', 30, '1d')
    returns = prices.pct_change()
    volatility = returns.std() * np.sqrt(252)  # Annualized

    # Target 1% portfolio risk per position
    portfolio_value = context.portfolio.portfolio_value
    risk_amount = portfolio_value * 0.01

    # Position size based on volatility
    price = prices[-1]
    position_size = int(risk_amount / (price * volatility))

    return position_size
```

## Documentation Structure

### Position Management
- **Positions (Coming soon)** - Position tracking and updates
- **Accounting Methods (Coming soon)** - FIFO, LIFO, average cost
- **Cash Management (Coming soon)** - Cash flow and buying power
- **Corporate Actions (Coming soon)** - Splits, dividends

### Multi-Strategy
- **[Portfolio Allocators](multi-strategy/allocators.md)** - Capital allocation
- **Order Aggregation (Coming soon)** - Cross-strategy netting
- **Performance Attribution (Coming soon)** - Strategy-level P&L

### Risk Management
- **[Position Limits](risk/position-limits.md)** - Maximum position constraints
- **Exposure Tracking (Coming soon)** - Gross/net exposure
- **Risk Metrics (Coming soon)** - VaR, correlation, stress tests
- **Best Practices (Coming soon)** - Risk management guidelines

### Performance
- **Metrics (Coming soon)** - Returns, Sharpe, alpha/beta
- **Calculations (Coming soon)** - Performance calculations
- **Interpretation (Coming soon)** - Understanding metrics

## Best Practices

### ✅ DO

1. **Check Positions Before Trading**: Avoid duplicate orders
2. **Monitor Cash Balance**: Ensure sufficient funds
3. **Track Cost Basis**: For accurate P&L calculation
4. **Use Position Sizing**: Don't over-concentrate
5. **Review Portfolio Regularly**: Monitor exposure and risk

### ❌ DON'T

1. **Ignore Position Limits**: Can lead to excessive risk
2. **Forget About Cash**: Ensure liquidity for new trades
3. **Overlook Transaction Costs**: Impact portfolio returns
4. **Neglect Rebalancing**: Positions drift over time
5. **Trade Without Stops**: Always manage downside risk

## Related Documentation

- [Order Management](../order-management/README.md) - Order placement and execution
- Transaction Costs - Commissions and slippage
- Live Trading - Live portfolio reconciliation
- [Analytics API](../analytics-api.md) - Advanced performance analysis

## Next Steps

1. Study Positions (Coming soon) for position tracking details
2. Review Accounting Methods (Coming soon) for cost basis calculations
3. Explore Risk Management for portfolio protection
4. Learn Performance Metrics (Coming soon) for strategy evaluation
