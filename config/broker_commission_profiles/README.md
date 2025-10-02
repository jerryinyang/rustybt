# Broker Commission Profiles

This directory contains commission profile configurations for various brokers and asset classes. These profiles define how transaction costs are calculated in RustyBT backtests and live trading.

## Available Profiles

### Equities

- **[interactive_brokers_equity.yaml](./interactive_brokers_equity.yaml)**: Interactive Brokers US equity commission structure
  - Per-share model: $0.005/share
  - Minimum: $1.00 per order
  - Suitable for: US stock trading

### Cryptocurrency

- **[binance_spot.yaml](./binance_spot.yaml)**: Binance spot trading commissions
  - Maker/taker model: 0.10% / 0.10% (VIP 0)
  - Includes VIP tier rates
  - Suitable for: Crypto spot trading

- **[coinbase_pro.yaml](./coinbase_pro.yaml)**: Coinbase Advanced (Pro) trading commissions
  - Maker/taker model with volume tiers
  - Default: 0.60% / 0.60%
  - Suitable for: Crypto trading on Coinbase

### Examples

- **[tiered_example.yaml](./tiered_example.yaml)**: Example tiered commission structure
  - Demonstrates volume-based discounts
  - Monthly volume tiers
  - Suitable for: Learning and testing

## Commission Models

### 1. PerShareCommission

Charges a fixed fee per share traded.

```yaml
commission_model: "PerShareCommission"
parameters:
  cost_per_share: 0.005  # $0.005 per share
  min_commission: 1.00   # $1.00 minimum
```

**Example**: 100 shares @ $50 = max($0.50, $1.00) = $1.00

### 2. PercentageCommission

Charges a percentage of trade value.

```yaml
commission_model: "PercentageCommission"
parameters:
  percentage: 0.001  # 0.1% of trade value
  min_commission: 0.0
```

**Example**: $10,000 trade = $10,000 × 0.001 = $10.00

### 3. TieredCommission

Volume-based commission rates with monthly tiers.

```yaml
commission_model: "TieredCommission"
parameters:
  tiers:
    0: 0.001       # 0-100k: 0.10%
    100000: 0.0005  # 100k-1M: 0.05%
    1000000: 0.0002 # 1M+: 0.02%
  min_commission: 0.0
```

**Example**:
- Month start: $50k trade = $50k × 0.001 = $50.00
- After $150k volume: $50k trade = $50k × 0.0005 = $25.00

### 4. MakerTakerCommission

Separate rates for maker (add liquidity) vs taker (remove liquidity) orders.

```yaml
commission_model: "MakerTakerCommission"
parameters:
  maker_rate: 0.0002  # 0.02% for limit orders that rest
  taker_rate: 0.0004  # 0.04% for market orders
  min_commission: 0.0
```

**Example**:
- Market order (taker): $10,000 × 0.0004 = $4.00
- Limit order (maker): $10,000 × 0.0002 = $2.00

## Using Commission Profiles

### In Python Code

```python
from decimal import Decimal
from rustybt.finance.commission import (
    PerShareCommission,
    PercentageCommission,
    TieredCommission,
    MakerTakerCommission,
)

# Interactive Brokers equity
ib_commission = PerShareCommission(
    cost_per_share=Decimal("0.005"),
    min_commission=Decimal("1.00")
)

# Binance spot trading
binance_commission = MakerTakerCommission(
    maker_rate=Decimal("0.001"),
    taker_rate=Decimal("0.001")
)

# Tiered commission
tiered_commission = TieredCommission(
    tiers={
        Decimal("0"): Decimal("0.001"),
        Decimal("100000"): Decimal("0.0005"),
        Decimal("1000000"): Decimal("0.0002"),
    }
)
```

### With Execution Engine

```python
from rustybt.finance.execution import ExecutionEngine

engine = ExecutionEngine(
    commission_model=ib_commission,
    # ... other models
)

result = engine.execute_order(order, current_time)
print(f"Commission: ${result.commission.commission}")
```

## Creating Custom Profiles

Create a new YAML file following this template:

```yaml
broker_name: "Your Broker Name"
asset_class: "equities"  # or "crypto", "futures", etc.
commission_model: "PerShareCommission"  # or other model type
parameters:
  # Model-specific parameters
  cost_per_share: 0.005
  min_commission: 1.00

notes: |
  Description and examples
```

Save to `config/broker_commission_profiles/your_broker.yaml`.

## Real-World Commission Structures

### US Equities
- **Interactive Brokers**: Per-share ($0.005/share, $1 min)
- **TD Ameritrade**: Free for most retail accounts
- **Charles Schwab**: Free for most retail accounts
- **Fidelity**: Free for most retail accounts

### Crypto Exchanges
- **Binance**: Maker/taker (0.10%/0.10% base, volume discounts)
- **Coinbase Pro**: Maker/taker (0.60%/0.60% base, volume tiers)
- **Kraken**: Maker/taker (0.16%/0.26% base, volume tiers)
- **FTX**: Maker/taker (0.02%/0.07% base, rebates available)

### Futures
- **Interactive Brokers**: Per-contract ($0.85/contract typical)
- **NinjaTrader**: Per-contract (varies by broker)
- **TradeStation**: Per-contract or percentage

## Best Practices

1. **Match Broker Profile**: Use the commission profile that matches your target broker
2. **Include in Backtests**: Always model commissions to get realistic performance metrics
3. **Update Regularly**: Broker fee structures change; keep profiles updated
4. **Test Impact**: Compare strategy performance with/without commissions
5. **Volume Tracking**: Use TieredCommission for strategies with variable volume
6. **Maker/Taker**: Use MakerTakerCommission for crypto and limit order strategies

## Notes

- Commission profiles are broker and asset-class specific
- Profiles use Decimal precision for accurate financial calculations
- Volume tracking resets monthly for tiered commissions
- Maker/taker classification depends on order type and fill behavior
- Some brokers offer rebates (negative commissions) for high-volume makers

## References

- [Interactive Brokers Pricing](https://www.interactivebrokers.com/en/pricing/commissions-stocks.php)
- [Binance Fee Schedule](https://www.binance.com/en/fee/schedule)
- [Coinbase Fee Structure](https://help.coinbase.com/en/exchange/trading-and-funding/exchange-fees)

## See Also

- [Story 4.4: Tiered Commission Models](../../../docs/stories/4.4.implement-tiered-commission-models.md)
- [Architecture: Tech Stack](../../../docs/architecture/tech-stack.md)
- [Testing Standards](../../../docs/architecture/testing-strategy.md)
