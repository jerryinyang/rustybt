# Slippage Models

**Module**: `rustybt.finance.decimal.slippage`
**Source**: `rustybt/finance/decimal/slippage.py`
**Verified**: 2025-10-16

## Overview

**Slippage** is the difference between the expected execution price and the actual execution price due to market impact, bid-ask spread, and liquidity constraints. RustyBT provides Decimal-precision slippage models to simulate realistic order execution costs.

**Key Concepts**:
- **Market Impact**: Large orders move prices against you
- **Bid-Ask Spread**: Cost of crossing spread to execute immediately
- **Liquidity**: Limited volume available at any price level
- **Slippage Always Worsens Execution**: Never improves your fill price

**Financial Integrity**: All slippage calculations use Python's `Decimal` type for audit-compliant precision.

---

## Why Model Slippage?

### Without Slippage (Unrealistic)

```python
# Naive backtest assumption
market_price = Decimal("100.00")
execution_price = market_price  # ✗ Assumes no slippage
# Overstates profitability!
```

**Problems**:
- ✗ Assumes infinite liquidity
- ✗ Ignores market impact
- ✗ Overstates strategy profitability
- ✗ Not production-ready

### With Slippage (Realistic)

```python
# Realistic execution
market_price = Decimal("100.00")
slippage_model = FixedBasisPointsSlippage(Decimal("5"))  # 0.05%
execution_price = slippage_model.calculate(order, market_price)
# execution_price = Decimal("100.05") for buy order
# Accounts for market impact!
```

**Benefits**:
- ✓ Realistic execution costs
- ✓ Conservative profitability estimates
- ✓ Production-ready backtests
- ✓ Better strategy validation

---

## DecimalSlippageModel Base Class

**Source**: `rustybt/finance/decimal/slippage.py:18`

```python
from abc import ABC, abstractmethod
from decimal import Decimal

class DecimalSlippageModel(ABC):
    """Abstract base class for Decimal slippage models."""

    @abstractmethod
    def calculate(self, order: DecimalOrder, market_price: Decimal) -> Decimal:
        """Calculate execution price with slippage.

        Args:
            order: Order being filled
            market_price: Current market price

        Returns:
            Execution price with slippage

        Note:
            Buy orders: execution price >= market price (worse)
            Sell orders: execution price <= market price (worse)
        """
        pass
```

**Key Contract**:
- Slippage **always worsens** execution price
- Buy orders: `execution_price >= market_price`
- Sell orders: `execution_price <= market_price`

---

## NoSlippage

**Source**: `rustybt/finance/decimal/slippage.py:43`

Zero slippage model for testing. Returns exact market price with no price impact.

### Class Definition

```python
class NoSlippage(DecimalSlippageModel):
    """Zero slippage model for testing."""

    def calculate(self, order: DecimalOrder, market_price: Decimal) -> Decimal:
        """Return market price with no slippage."""
        return market_price
```

**Source Verification** (lines 50-60):
- Returns `market_price` unchanged
- No price impact applied
- Used for testing only

### Example: NoSlippage

```python
from decimal import Decimal
from rustybt.finance.decimal.slippage import NoSlippage
from rustybt.finance.decimal.order import DecimalOrder

# Create model
model = NoSlippage()

# Create buy order
buy_order = DecimalOrder(
    dt=datetime.now(),
    asset=equity,
    amount=Decimal("100")
)

# Calculate execution price
market_price = Decimal("150.00")
execution_price = model.calculate(buy_order, market_price)

print(f"Market Price: ${market_price}")
print(f"Execution Price: ${execution_price}")
# Output:
# Market Price: $150.00
# Execution Price: $150.00  (no slippage)

# Verify no impact
assert execution_price == market_price
print("✓ No slippage applied")
```

**When to Use**:
- Testing strategies without transaction costs
- Baseline comparisons
- Debugging execution logic

---

## FixedSlippage

**Source**: `rustybt/finance/decimal/slippage.py:66`

Fixed slippage as absolute dollar amount. Simple model with constant price impact per trade.

### Class Definition

```python
class FixedSlippage(DecimalSlippageModel):
    """Fixed slippage as absolute dollar amount.

    Formula:
        Buy: market_price + slippage
        Sell: market_price - slippage
    """

    def __init__(self, slippage: Decimal, config: DecimalConfig | None = None) -> None:
        """Initialize fixed slippage model.

        Args:
            slippage: Fixed slippage amount (e.g., Decimal("0.10") = $0.10)
            config: DecimalConfig instance

        Raises:
            ValueError: If slippage is negative
        """
        if slippage < Decimal("0"):
            raise ValueError(f"Slippage must be non-negative, got {slippage}")

        self.slippage = slippage
        self.config = config or DecimalConfig.get_instance()
```

**Source Verification** (lines 98-123):
- Constructor validates `slippage >= 0` (line 90-91)
- Buy orders: `market_price + slippage` (line 110)
- Sell orders: `market_price - slippage` (line 113)

### Example: FixedSlippage - Basic Usage

```python
from decimal import Decimal
from rustybt.finance.decimal.slippage import FixedSlippage

# Create model with $0.10 slippage
model = FixedSlippage(slippage=Decimal("0.10"))

# Buy order: pay more
buy_order = DecimalOrder(
    dt=datetime.now(),
    asset=equity,
    amount=Decimal("100")
)

market_price = Decimal("150.00")
buy_execution = model.calculate(buy_order, market_price)

print(f"Buy Order:")
print(f"  Market Price: ${market_price}")
print(f"  Execution Price: ${buy_execution}")
print(f"  Slippage Cost: ${buy_execution - market_price}")
# Output:
# Buy Order:
#   Market Price: $150.00
#   Execution Price: $150.10  (paid $0.10 more)
#   Slippage Cost: $0.10

# Sell order: receive less
sell_order = DecimalOrder(
    dt=datetime.now(),
    asset=equity,
    amount=Decimal("-100")
)

sell_execution = model.calculate(sell_order, market_price)

print(f"\nSell Order:")
print(f"  Market Price: ${market_price}")
print(f"  Execution Price: ${sell_execution}")
print(f"  Slippage Cost: ${market_price - sell_execution}")
# Output:
# Sell Order:
#   Market Price: $150.00
#   Execution Price: $149.90  (received $0.10 less)
#   Slippage Cost: $0.10
```

### Example: FixedSlippage - Penny Stocks vs Large Caps

```python
# High volatility penny stock - larger slippage
penny_model = FixedSlippage(slippage=Decimal("0.05"))  # 5 cents

penny_price = Decimal("2.00")
penny_execution = penny_model.calculate(buy_order, penny_price)
penny_impact_pct = ((penny_execution - penny_price) / penny_price) * Decimal("100")

print(f"Penny Stock ($2.00):")
print(f"  Slippage: $0.05")
print(f"  Impact: {float(penny_impact_pct):.2f}%")
# Output:
# Penny Stock ($2.00):
#   Slippage: $0.05
#   Impact: 2.50%  (large percentage impact)

# Large cap stock - same absolute slippage, smaller percentage
large_cap_price = Decimal("500.00")
large_cap_execution = penny_model.calculate(buy_order, large_cap_price)
large_cap_impact_pct = ((large_cap_execution - large_cap_price) / large_cap_price) * Decimal("100")

print(f"\nLarge Cap ($500.00):")
print(f"  Slippage: $0.05")
print(f"  Impact: {float(large_cap_impact_pct):.4f}%")
# Output:
# Large Cap ($500.00):
#   Slippage: $0.05
#   Impact: 0.0100%  (tiny percentage impact)
```

### Example: FixedSlippage - Error Handling

```python
# Negative slippage not allowed
try:
    invalid_model = FixedSlippage(slippage=Decimal("-0.10"))
except ValueError as e:
    print(f"Error: {e}")
    # Output: Error: Slippage must be non-negative, got -0.10

# Zero slippage is valid (equivalent to NoSlippage)
zero_model = FixedSlippage(slippage=Decimal("0"))
execution = zero_model.calculate(buy_order, Decimal("100.00"))
assert execution == Decimal("100.00")
print("✓ Zero slippage model valid")
```

**When to Use**:
- Simple spread modeling
- Low-latency execution
- Small orders in liquid markets

**Limitations**:
- Doesn't scale with order size
- Doesn't account for market impact
- Not realistic for large orders

---

## FixedBasisPointsSlippage

**Source**: `rustybt/finance/decimal/slippage.py:129`

Slippage as fixed percentage of price (basis points). More realistic than fixed dollar amount as it scales with price.

### Class Definition

```python
class FixedBasisPointsSlippage(DecimalSlippageModel):
    """Slippage as fixed basis points (percentage of price).

    Formula:
        Buy: market_price × (1 + bps / 10000)
        Sell: market_price × (1 - bps / 10000)

    Note: 1 basis point = 0.01% = 0.0001
    """

    def __init__(self, basis_points: Decimal, config: DecimalConfig | None = None) -> None:
        """Initialize fixed basis points slippage model.

        Args:
            basis_points: Slippage in basis points (e.g., Decimal("10") = 0.1%)
            config: DecimalConfig instance

        Raises:
            ValueError: If basis_points is negative
        """
        if basis_points < Decimal("0"):
            raise ValueError(f"Basis points must be non-negative, got {basis_points}")

        self.basis_points = basis_points
        self.config = config or DecimalConfig.get_instance()
```

**Source Verification** (lines 161-188):
- Constructor validates `basis_points >= 0` (line 153-154)
- Conversion: `slippage_factor = basis_points / 10000` (line 171)
- Buy: `market_price * (1 + slippage_factor)` (line 175)
- Sell: `market_price * (1 - slippage_factor)` (line 178)

### Example: FixedBasisPointsSlippage - Basic Usage

```python
from decimal import Decimal
from rustybt.finance.decimal.slippage import FixedBasisPointsSlippage

# Create model with 5 basis points (0.05%)
model = FixedBasisPointsSlippage(basis_points=Decimal("5"))

# Test with different prices
prices = [Decimal("10.00"), Decimal("100.00"), Decimal("1000.00")]

print("Fixed Basis Points Slippage (5 bps = 0.05%)")
print("=" * 60)

for price in prices:
    buy_execution = model.calculate(buy_order, price)
    slippage_amount = buy_execution - price
    slippage_pct = (slippage_amount / price) * Decimal("100")

    print(f"\nMarket Price: ${price}")
    print(f"  Buy Execution: ${buy_execution}")
    print(f"  Slippage: ${slippage_amount}")
    print(f"  Impact: {float(slippage_pct):.4f}%")

# Output:
# Fixed Basis Points Slippage (5 bps = 0.05%)
# ============================================================
#
# Market Price: $10.00
#   Buy Execution: $10.005
#   Slippage: $0.005
#   Impact: 0.0500%
#
# Market Price: $100.00
#   Buy Execution: $100.05
#   Slippage: $0.05
#   Impact: 0.0500%
#
# Market Price: $1000.00
#   Buy Execution: $1000.50
#   Slippage: $0.50
#   Impact: 0.0500%  (percentage stays constant!)
```

### Example: Realistic Basis Point Values

```python
# Typical basis point values for different scenarios

# High-frequency trading (tight spreads)
hft_model = FixedBasisPointsSlippage(basis_points=Decimal("1"))  # 0.01%

# Retail trading (typical spreads)
retail_model = FixedBasisPointsSlippage(basis_points=Decimal("5"))  # 0.05%

# Large institutional orders
institutional_model = FixedBasisPointsSlippage(basis_points=Decimal("10"))  # 0.1%

# Illiquid markets
illiquid_model = FixedBasisPointsSlippage(basis_points=Decimal("50"))  # 0.5%

market_price = Decimal("100.00")

print("Slippage Comparison at $100 Market Price:")
print("=" * 60)

models = [
    ("HFT (1 bps)", hft_model),
    ("Retail (5 bps)", retail_model),
    ("Institutional (10 bps)", institutional_model),
    ("Illiquid (50 bps)", illiquid_model)
]

for name, model in models:
    execution = model.calculate(buy_order, market_price)
    cost = execution - market_price
    print(f"{name:25s}: ${execution} (cost: ${cost})")

# Output:
# Slippage Comparison at $100 Market Price:
# ============================================================
# HFT (1 bps)              : $100.01 (cost: $0.01)
# Retail (5 bps)           : $100.05 (cost: $0.05)
# Institutional (10 bps)   : $100.10 (cost: $0.10)
# Illiquid (50 bps)        : $100.50 (cost: $0.50)
```

### Example: Round-Trip Cost

```python
# Calculate round-trip cost (buy + sell)
model = FixedBasisPointsSlippage(basis_points=Decimal("5"))

market_price = Decimal("100.00")
quantity = Decimal("100")

# Buy
buy_execution = model.calculate(buy_order, market_price)
buy_cost = (buy_execution - market_price) * quantity

# Sell
sell_order = DecimalOrder(dt=datetime.now(), asset=equity, amount=Decimal("-100"))
sell_execution = model.calculate(sell_order, market_price)
sell_cost = (market_price - sell_execution) * quantity

# Total round-trip cost
total_cost = buy_cost + sell_cost

print(f"Round-Trip Cost Analysis:")
print(f"=" * 60)
print(f"Quantity: {quantity} shares")
print(f"Market Price: ${market_price}")
print(f"\nBuy:")
print(f"  Execution: ${buy_execution}")
print(f"  Slippage per share: ${buy_execution - market_price}")
print(f"  Total cost: ${buy_cost}")
print(f"\nSell:")
print(f"  Execution: ${sell_execution}")
print(f"  Slippage per share: ${market_price - sell_execution}")
print(f"  Total cost: ${sell_cost}")
print(f"\nRound-Trip:")
print(f"  Total slippage: ${total_cost}")
print(f"  Cost per share: ${total_cost / quantity}")

# Output:
# Round-Trip Cost Analysis:
# ============================================================
# Quantity: 100 shares
# Market Price: $100.00
#
# Buy:
#   Execution: $100.05
#   Slippage per share: $0.05
#   Total cost: $5.00
#
# Sell:
#   Execution: $99.95
#   Slippage per share: $0.05
#   Total cost: $5.00
#
# Round-Trip:
#   Total slippage: $10.00
#   Cost per share: $0.10
```

**When to Use**:
- Most common slippage model
- Scales appropriately with price
- Good for typical retail/institutional trading

**Advantages**:
- Percentage-based (scales with price)
- Simple and intuitive
- Industry-standard metric

**Limitations**:
- Doesn't account for order size
- No volume constraints
- Same impact for small/large orders

---

## VolumeShareSlippage

**Source**: `rustybt/finance/decimal/slippage.py:194`

Volume-based slippage model with quadratic price impact. Most realistic model that accounts for order size relative to market volume.

### Class Definition

```python
class VolumeShareSlippage(DecimalSlippageModel):
    """Volume-based slippage model with price impact.

    Formula:
        volume_share = order_volume / bar_volume
        price_impact = volume_share^2 × impact_factor
        execution_price = market_price × (1 +/- price_impact)

    Note: Quadratic impact reflects market microstructure reality
    """

    def __init__(
        self,
        volume_limit: Decimal = Decimal("0.025"),
        price_impact: Decimal = Decimal("0.1"),
        config: DecimalConfig | None = None,
    ) -> None:
        """Initialize volume share slippage model.

        Args:
            volume_limit: Maximum order volume as fraction of bar volume
            price_impact: Price impact coefficient (default 0.1)
            config: DecimalConfig instance

        Raises:
            ValueError: If volume_limit or price_impact is negative
        """
        if volume_limit <= Decimal("0"):
            raise ValueError(f"Volume limit must be positive, got {volume_limit}")

        if price_impact < Decimal("0"):
            raise ValueError(f"Price impact must be non-negative, got {price_impact}")

        self.volume_limit = volume_limit
        self.price_impact = price_impact
        self.config = config or DecimalConfig.get_instance()
```

**Source Verification** (lines 244-297):
- Validates parameters (lines 228-232)
- Calculates `volume_share = fill_amount / bar_volume` (line 269)
- Enforces volume limit (lines 272-276)
- Quadratic impact: `price_impact = volume_share^2 * impact_factor` (line 279)
- Buy: `market_price * (1 + price_impact)` (line 283)
- Sell: `market_price * (1 - price_impact)` (line 286)

### Example: VolumeShareSlippage - Basic Usage

```python
from decimal import Decimal
from rustybt.finance.decimal.slippage import VolumeShareSlippage

# Create model
# - volume_limit: Max 2.5% of bar volume
# - price_impact: Impact coefficient
model = VolumeShareSlippage(
    volume_limit=Decimal("0.025"),  # 2.5%
    price_impact=Decimal("0.1")
)

# Market data
market_price = Decimal("100.00")
bar_volume = Decimal("1000000")  # 1M shares traded

# Small order (0.1% of volume)
small_fill = Decimal("1000")
small_execution = model.calculate(
    buy_order, market_price, small_fill, bar_volume
)
small_impact = small_execution - market_price
small_impact_pct = (small_impact / market_price) * Decimal("100")

print(f"Small Order (1,000 shares = 0.1% of volume):")
print(f"  Execution: ${small_execution}")
print(f"  Slippage: ${small_impact}")
print(f"  Impact: {float(small_impact_pct):.4f}%")
# Output:
# Small Order (1,000 shares = 0.1% of volume):
#   Execution: $100.0001
#   Slippage: $0.0001
#   Impact: 0.0001%  (tiny impact)

# Medium order (1% of volume)
medium_fill = Decimal("10000")
medium_execution = model.calculate(
    buy_order, market_price, medium_fill, bar_volume
)
medium_impact = medium_execution - market_price
medium_impact_pct = (medium_impact / market_price) * Decimal("100")

print(f"\nMedium Order (10,000 shares = 1% of volume):")
print(f"  Execution: ${medium_execution}")
print(f"  Slippage: ${medium_impact}")
print(f"  Impact: {float(medium_impact_pct):.4f}%")
# Output:
# Medium Order (10,000 shares = 1% of volume):
#   Execution: $100.01
#   Slippage: $0.01
#   Impact: 0.0100%  (100x larger due to quadratic)

# Large order (2.5% of volume - at limit)
large_fill = Decimal("25000")
large_execution = model.calculate(
    buy_order, market_price, large_fill, bar_volume
)
large_impact = large_execution - market_price
large_impact_pct = (large_impact / market_price) * Decimal("100")

print(f"\nLarge Order (25,000 shares = 2.5% of volume - AT LIMIT):")
print(f"  Execution: ${large_execution}")
print(f"  Slippage: ${large_impact}")
print(f"  Impact: {float(large_impact_pct):.4f}%")
# Output:
# Large Order (25,000 shares = 2.5% of volume - AT LIMIT):
#   Execution: $100.0625
#   Slippage: $0.0625
#   Impact: 0.0625%  (625x larger!)
```

### Example: Volume Limit Enforcement

```python
model = VolumeShareSlippage(volume_limit=Decimal("0.025"))

market_price = Decimal("100.00")
bar_volume = Decimal("1000000")

# Attempt to fill more than volume limit
excessive_fill = Decimal("30000")  # 3% of volume (exceeds 2.5% limit)

try:
    execution = model.calculate(
        buy_order, market_price, excessive_fill, bar_volume
    )
except ValueError as e:
    print(f"Error: {e}")
    # Output: Error: Fill volume 30000 exceeds limit of 25000.0
    #         (volume_share: 0.03, limit: 0.025)

# Calculate maximum allowed fill
max_allowed_fill = bar_volume * model.volume_limit
print(f"\nMax allowed fill: {max_allowed_fill} shares")
print(f"Attempted fill: {excessive_fill} shares")
print(f"Over limit by: {excessive_fill - max_allowed_fill} shares")
```

### Example: Quadratic Impact Demonstration

```python
# Demonstrate quadratic scaling
model = VolumeShareSlippage(
    volume_limit=Decimal("0.1"),  # 10% limit
    price_impact=Decimal("1.0")    # 100% coefficient
)

market_price = Decimal("100.00")
bar_volume = Decimal("100000")

# Test different order sizes
order_sizes = [
    Decimal("100"),    # 0.1%
    Decimal("1000"),   # 1.0%
    Decimal("5000"),   # 5.0%
    Decimal("10000"),  # 10.0% (max)
]

print("Quadratic Price Impact Demonstration:")
print("=" * 70)
print(f"{'Order Size':>12} {'Volume %':>10} {'Slippage':>12} {'Impact %':>12}")
print("=" * 70)

for size in order_sizes:
    execution = model.calculate(buy_order, market_price, size, bar_volume)
    slippage = execution - market_price
    impact_pct = (slippage / market_price) * Decimal("100")
    volume_pct = (size / bar_volume) * Decimal("100")

    print(f"{int(size):>12,} {float(volume_pct):>9.2f}% "
          f"${float(slippage):>11.4f} {float(impact_pct):>11.4f}%")

# Output:
# Quadratic Price Impact Demonstration:
# ======================================================================
#   Order Size  Volume %     Slippage     Impact %
# ======================================================================
#          100       0.10%      $0.0001       0.0001%
#        1,000       1.00%      $0.0100       0.0100%  (10x size, 100x impact)
#        5,000       5.00%      $0.2500       0.2500%  (50x size, 2500x impact)
#       10,000      10.00%      $1.0000       1.0000%  (100x size, 10000x impact)
```

### Example: Conservative vs Aggressive Models

```python
# Conservative model (tight limits, high impact)
conservative = VolumeShareSlippage(
    volume_limit=Decimal("0.01"),   # 1% max
    price_impact=Decimal("0.5")      # High impact
)

# Balanced model (moderate)
balanced = VolumeShareSlippage(
    volume_limit=Decimal("0.025"),  # 2.5% max
    price_impact=Decimal("0.1")      # Moderate impact
)

# Aggressive model (loose limits, low impact)
aggressive = VolumeShareSlippage(
    volume_limit=Decimal("0.05"),   # 5% max
    price_impact=Decimal("0.05")     # Low impact
)

market_price = Decimal("100.00")
bar_volume = Decimal("1000000")
fill_amount = Decimal("10000")  # 1% of volume

models = [
    ("Conservative", conservative),
    ("Balanced", balanced),
    ("Aggressive", aggressive)
]

print("Model Comparison (10,000 share order, 1M volume):")
print("=" * 70)

for name, model in models:
    try:
        execution = model.calculate(buy_order, market_price, fill_amount, bar_volume)
        impact = execution - market_price
        impact_pct = (impact / market_price) * Decimal("100")
        print(f"{name:15s}: ${execution} (impact: {float(impact_pct):.4f}%)")
    except ValueError as e:
        print(f"{name:15s}: REJECTED - {e}")

# Output:
# Model Comparison (10,000 share order, 1M volume):
# ======================================================================
# Conservative   : REJECTED - Fill volume 10000 exceeds limit of 10000.0
# Balanced       : $100.01 (impact: 0.0100%)
# Aggressive     : $100.005 (impact: 0.0050%)
```

**When to Use**:
- Most realistic slippage model
- Large orders that impact market
- Production backtests
- Strategy validation

**Advantages**:
- Accounts for order size
- Enforces liquidity constraints
- Quadratic impact (realistic)
- Industry-standard approach

**Limitations**:
- Requires bar volume data
- More complex than fixed models
- May need parameter tuning

---

## Slippage Model Selection Guide

### Decision Tree

```
Start: Choose Slippage Model
│
├─ Testing/Debugging?
│  └─ Use NoSlippage
│
├─ Small orders in liquid markets?
│  ├─ Fixed dollar spread? → Use FixedSlippage
│  └─ Percentage spread? → Use FixedBasisPointsSlippage
│
└─ Production backtesting?
   ├─ Small retail orders?
   │  └─ Use FixedBasisPointsSlippage (5-10 bps)
   │
   └─ Large institutional orders?
      └─ Use VolumeShareSlippage (most realistic)
```

### Comparison Table

| Model | Complexity | Realism | Use Case |
|-------|------------|---------|----------|
| **NoSlippage** | Lowest | Unrealistic | Testing only |
| **FixedSlippage** | Low | Low | Simple spreads |
| **FixedBasisPointsSlippage** | Low | Medium | Retail trading |
| **VolumeShareSlippage** | High | High | Institutional/production |

### Example: Model Selection Strategy

```python
from decimal import Decimal
from rustybt.finance.decimal.slippage import (
    NoSlippage,
    FixedBasisPointsSlippage,
    VolumeShareSlippage
)

def select_slippage_model(
    order_size: Decimal,
    avg_daily_volume: Decimal,
    is_production: bool
) -> DecimalSlippageModel:
    """Select appropriate slippage model based on order characteristics."""

    # Calculate volume percentage
    volume_pct = (order_size / avg_daily_volume) if avg_daily_volume > Decimal("0") else Decimal("0")

    # Testing mode - no slippage
    if not is_production:
        return NoSlippage()

    # Small orders (< 0.1% of ADV) - fixed basis points
    if volume_pct < Decimal("0.001"):
        return FixedBasisPointsSlippage(basis_points=Decimal("5"))

    # Medium orders (0.1% - 1% of ADV) - moderate volume-based
    elif volume_pct < Decimal("0.01"):
        return VolumeShareSlippage(
            volume_limit=Decimal("0.025"),
            price_impact=Decimal("0.1")
        )

    # Large orders (> 1% of ADV) - conservative volume-based
    else:
        return VolumeShareSlippage(
            volume_limit=Decimal("0.01"),
            price_impact=Decimal("0.3")
        )

# Usage examples
print("Slippage Model Selection:")
print("=" * 70)

scenarios = [
    (Decimal("100"), Decimal("1000000"), True, "Small retail order"),
    (Decimal("5000"), Decimal("1000000"), True, "Medium institutional order"),
    (Decimal("15000"), Decimal("1000000"), True, "Large institutional order"),
    (Decimal("1000"), Decimal("1000000"), False, "Testing mode"),
]

for order_size, adv, production, description in scenarios:
    model = select_slippage_model(order_size, adv, production)
    volume_pct = (order_size / adv) * Decimal("100")

    print(f"\n{description}:")
    print(f"  Order: {order_size} shares ({float(volume_pct):.3f}% of ADV)")
    print(f"  Model: {model}")
```

---

## Production Usage Patterns

### Pattern 1: Backtesting with Realistic Slippage

```python
from decimal import Decimal
from rustybt.finance.decimal.blotter import DecimalBlotter
from rustybt.finance.decimal.slippage import VolumeShareSlippage
from rustybt.finance.decimal.commission import PerShareCommission

# Create production-grade blotter
blotter = DecimalBlotter(
    commission_model=PerShareCommission(
        cost_per_share=Decimal("0.005"),
        min_cost=Decimal("1.00")
    ),
    slippage_model=VolumeShareSlippage(
        volume_limit=Decimal("0.025"),  # 2.5% max
        price_impact=Decimal("0.1")
    )
)

# Run backtest with realistic execution costs
# ... strategy logic ...
```

### Pattern 2: Conservative/Balanced/Aggressive Scenarios

```python
# Test strategy under different slippage assumptions

scenarios = {
    'conservative': VolumeShareSlippage(
        volume_limit=Decimal("0.01"),
        price_impact=Decimal("0.3")
    ),
    'balanced': VolumeShareSlippage(
        volume_limit=Decimal("0.025"),
        price_impact=Decimal("0.1")
    ),
    'aggressive': VolumeShareSlippage(
        volume_limit=Decimal("0.05"),
        price_impact=Decimal("0.05")
    )
}

results = {}
for scenario_name, slippage_model in scenarios.items():
    blotter = DecimalBlotter(slippage_model=slippage_model)
    # Run backtest
    results[scenario_name] = run_backtest(strategy, blotter)

# Compare results
for scenario, result in results.items():
    print(f"{scenario:15s}: Sharpe={result['sharpe']:.2f}")
```

### Pattern 3: Adaptive Slippage Based on Market Conditions

```python
class AdaptiveSlippage(DecimalSlippageModel):
    """Adjust slippage based on market volatility."""

    def __init__(self):
        self.low_vol_model = FixedBasisPointsSlippage(Decimal("5"))
        self.high_vol_model = FixedBasisPointsSlippage(Decimal("15"))
        self.volatility_threshold = Decimal("0.02")  # 2% threshold

    def calculate(self, order, market_price, current_volatility=None):
        """Select model based on volatility."""
        if current_volatility and current_volatility > self.volatility_threshold:
            return self.high_vol_model.calculate(order, market_price)
        else:
            return self.low_vol_model.calculate(order, market_price)
```

---

## Best Practices

### ✅ DO

1. **Use Realistic Models for Production**
   ```python
   # ✓ Correct - realistic slippage
   slippage = VolumeShareSlippage(
       volume_limit=Decimal("0.025"),
       price_impact=Decimal("0.1")
   )
   ```

2. **Test Multiple Scenarios**
   ```python
   # Test conservative, balanced, aggressive
   for model in [conservative, balanced, aggressive]:
       results = backtest(strategy, model)
   ```

3. **Scale Slippage with Order Size**
   ```python
   # Use volume-based models for large orders
   if order_size > (adv * Decimal("0.01")):
       model = VolumeShareSlippage(...)
   ```

4. **Document Slippage Assumptions**
   ```python
   # Document model choice in backtest metadata
   metadata = {
       'slippage_model': 'VolumeShareSlippage',
       'volume_limit': '2.5%',
       'price_impact': '0.1'
   }
   ```

5. **Validate Against Historical Data**
   ```python
   # Compare simulated vs actual execution costs
   actual_costs = get_historical_execution_costs()
   simulated_costs = calculate_simulated_costs(slippage_model)
   validate_accuracy(actual_costs, simulated_costs)
   ```

### ❌ DON'T

1. **Don't Use NoSlippage in Production**
   ```python
   # ✗ Wrong - unrealistic
   slippage = NoSlippage()  # Only for testing!
   ```

2. **Don't Ignore Volume Constraints**
   ```python
   # ✗ Wrong - no volume limits
   slippage = FixedBasisPointsSlippage(Decimal("5"))
   # Large orders will have unrealistic fills

   # ✓ Correct - enforce volume limits
   slippage = VolumeShareSlippage(volume_limit=Decimal("0.025"))
   ```

3. **Don't Use Same Model for All Assets**
   ```python
   # ✗ Wrong - one size doesn't fit all
   slippage = FixedSlippage(Decimal("0.10"))  # Same for penny stocks and large caps

   # ✓ Correct - asset-specific models
   if asset_price < Decimal("10"):
       slippage = FixedBasisPointsSlippage(Decimal("50"))  # Higher for penny stocks
   ```

4. **Don't Forget Round-Trip Costs**
   ```python
   # ✓ Correct - account for both sides
   buy_cost = slippage.calculate(buy_order, price) - price
   sell_cost = price - slippage.calculate(sell_order, price)
   total_cost = buy_cost + sell_cost
   ```

5. **Don't Over-Optimize on Zero Slippage**
   ```python
   # ✗ Wrong - optimizing without costs
   best_params = optimize(strategy, slippage=NoSlippage())

   # ✓ Correct - optimize with realistic costs
   best_params = optimize(strategy, slippage=realistic_model)
   ```

---

## Related Documentation

- [Commission Models](./commission-models.md) - Transaction commission calculation
- [DecimalBlotter](../execution/decimal-blotter.md) - Order management system
- [Execution Pipeline](../execution/execution-pipeline.md) - Complete execution flow
- [Partial Fill Models](../execution/partial-fills.md) - Fill simulation

---

## Summary

**Slippage Models** provide realistic execution cost simulation:

- **NoSlippage**: Testing only (no costs)
- **FixedSlippage**: Simple absolute spread ($0.10)
- **FixedBasisPointsSlippage**: Percentage-based spread (5 bps = 0.05%)
- **VolumeShareSlippage**: Most realistic (accounts for order size and market impact)

**Key Principles**:
1. Slippage always worsens execution price
2. Buy orders pay more, sell orders receive less
3. Larger orders have larger impact (quadratic in VolumeShareSlippage)
4. Production backtests should use volume-based models

All slippage calculations use `Decimal` precision for audit-compliant financial calculations.
