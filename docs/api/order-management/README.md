# Order Management System

Complete guide to RustyBT's order management, execution, and transaction cost modeling systems.

## Overview

RustyBT provides a sophisticated order management system for backtesting and live trading. The system handles:

- **Order Types**: Market, Limit, Stop, Stop-Limit, Trailing Stop, and complex orders
- **Execution**: Blotter-based order routing, matching, and fill simulation
- **Transaction Costs**: Slippage and commission modeling with multiple strategies
- **Order Lifecycle**: State management, validation, and execution tracking

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Strategy Algorithm                     │
└───────────────────┬─────────────────────────────────────┘
                    │ order(asset, amount, style)
                    ▼
┌─────────────────────────────────────────────────────────┐
│                        Blotter                           │
│  • Order validation                                      │
│  • Order routing                                         │
│  • State management                                      │
└───────────────────┬─────────────────────────────────────┘
                    │ process_order(order, data)
                    ▼
┌─────────────────────────────────────────────────────────┐
│                   Execution Engine                       │
│  • Price matching                                        │
│  • Partial fills                                         │
│  • Stop/Limit triggers                                   │
└───────────────────┬─────────────────────────────────────┘
                    │ apply costs
                    ▼
┌─────────────────────────────────────────────────────────┐
│               Transaction Cost Models                    │
│  • Slippage calculation                                  │
│  • Commission calculation                                │
└───────────────────┬─────────────────────────────────────┘
                    │ create_transaction
                    ▼
┌─────────────────────────────────────────────────────────┐
│                   Portfolio Tracker                      │
│  • Position updates                                      │
│  • P&L calculation                                       │
│  • Cash management                                       │
└─────────────────────────────────────────────────────────┘
```

## Example Types in This Documentation

This documentation includes two types of code examples:

**📋 Usage Pattern Snippets**: Brief code snippets showing API usage within a trading strategy context. These assume you're working within a `TradingAlgorithm` subclass.

**🚀 Complete Examples**: Full runnable examples with all imports and setup included.

Look for section headers like "Complete Examples" for full code, and inline examples for usage patterns.

---

## Quick Start

### Basic Market Order

```python
from rustybt.algorithm import TradingAlgorithm
from rustybt.api import order, symbol

class SimpleStrategy(TradingAlgorithm):
    def initialize(self, context):
        context.asset = self.symbol('AAPL')

    def handle_data(self, context, data):
        # Place market order for 100 shares
        order(context.asset, 100)
```

### Order with Limit Price

```python
from rustybt.api import order
from rustybt.finance.execution import LimitOrder

# Buy up to $150 per share
order(asset, 100, style=LimitOrder(limit_price=150.0))
```

### Stop-Loss Order

```python
from rustybt.finance.execution import StopOrder

# Sell if price drops to $95
order(asset, -100, style=StopOrder(stop_price=95.0))
```

## Documentation Structure

### Order System
- **[Order Types](order-types.md)** - Complete reference for all order types
- **[Order Lifecycle](workflows/order-lifecycle.md)** - Order states and transitions
- **[Order Examples](workflows/examples.md)** - Real-world trading scenarios

### Execution System
- **[Blotter Architecture](execution/blotter.md)** - Order management and routing
- **Simulation Blotter (Coming soon)** - Backtesting execution
- **Fill Processing (Coming soon)** - Order matching and partial fills
- **Execution Events (Coming soon)** - Event-driven execution flow

### Transaction Costs
- **[Slippage Models](transaction-costs/slippage.md)** - Market impact and slippage
- **[Commission Models](transaction-costs/commissions.md)** - Broker fees and commissions
- **Borrow Costs (Coming soon)** - Short selling costs
- **Financing Costs (Coming soon)** - Overnight and leverage fees

## Key Concepts

### Order States

| State | Description | Transitions To |
|-------|-------------|----------------|
| `OPEN` | Order placed, awaiting trigger | `TRIGGERED`, `CANCELLED`, `REJECTED` |
| `TRIGGERED` | Stop/limit reached, ready to execute | `FILLED`, `PARTIALLY_FILLED`, `CANCELLED` |
| `PARTIALLY_FILLED` | Some shares filled | `FILLED`, `CANCELLED` |
| `FILLED` | Order completely filled | *(terminal state)* |
| `CANCELLED` | Order cancelled by user/system | *(terminal state)* |
| `REJECTED` | Order rejected (validation failure) | *(terminal state)* |
| `HELD` | Order held by system (risk limits) | `OPEN`, `CANCELLED` |

### Order Direction

- **Positive amount**: Buy (long) or Cover (close short)
- **Negative amount**: Sell (close long) or Short (short sell)

```python
order(asset, 100)   # Buy 100 shares
order(asset, -100)  # Sell 100 shares
```

### Execution Priority

Order matching follows price-time priority:

1. **Market orders**: Immediate execution at current price
2. **Limit orders**: Execute when price reaches limit (or better)
3. **Stop orders**: Convert to market order when stop price reached
4. **Stop-Limit orders**: Convert to limit order when stop price reached

## Risk Warnings

⚠️ **IMPORTANT**: Order management directly impacts trading results and risk exposure.

### Common Pitfalls

1. **Market Orders in Illiquid Assets**: Can experience severe slippage
2. **Stop Orders Without Slippage**: May fill at worse prices than expected
3. **Large Orders**: May exceed available volume, causing partial fills
4. **Stale Limit Orders**: Orders may remain open indefinitely if price doesn't reach limit

### Best Practices

✅ **DO**:
- Use limit orders in illiquid markets
- Set realistic stop-loss levels based on volatility
- Monitor order status and adjust as needed
- Model slippage and commissions realistically
- Validate order parameters before submission

❌ **DON'T**:
- Place market orders for large positions without volume checks
- Ignore transaction costs in strategy design
- Set stop-losses too tight (noise-triggered exits)
- Assume instant fills at exact prices

## Integration with Portfolio Management

Orders directly affect portfolio state:

```python
def handle_data(self, context, data):
    position = context.portfolio.positions.get(asset)

    if position is None or position.amount == 0:
        # No position, enter new
        order(asset, 100)
    elif position.amount > 0:
        # Have long position, exit
        order(asset, -position.amount)
```

See [Portfolio Management](../portfolio-management/README.md) for complete portfolio integration.

## Performance Considerations

### Order Volume Limits

Configure maximum order size as fraction of daily volume:

```python
from rustybt.finance.slippage import VolumeShareSlippage

# Limit orders to 2.5% of bar volume
set_slippage(VolumeShareSlippage(volume_limit=0.025))
```

### Commission Impact

Even small per-share commissions compound:

```python
# 0.1¢ per share on 1000 trades of 100 shares
# = $0.001 × 100 × 1000 = $100 in commissions
```

See Performance Optimization for strategies.

## Related Documentation

- [Portfolio Management](../portfolio-management/README.md) - Position tracking and P&L
- [Data Management](../data-management/README.md) - Market data for order execution
- Live Trading API - Live order execution with brokers
- Finance API - Core finance module reference

## Next Steps

1. **Understand Order Types**: Start with [Order Types](order-types.md)
2. **Learn Execution Flow**: Read [Blotter Architecture](execution/blotter.md)
3. **Model Costs Realistically**: Study Transaction Costs
4. **Build Strategies**: Review [Order Examples](workflows/examples.md)

## Support

For questions about order management:
- Check [Order Lifecycle](workflows/order-lifecycle.md) for state transitions
- See [Troubleshooting](transaction-costs/slippage.md#troubleshooting) for common issues
- Review Finance API Reference for complete API documentation
