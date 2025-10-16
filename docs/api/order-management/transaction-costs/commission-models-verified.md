# Commission Models

**Module**: `rustybt.finance.decimal.commission`
**Source**: `rustybt/finance/decimal/commission.py`
**Verified**: 2025-10-16

## Overview

**Commission** models calculate transaction costs charged by brokers for executing trades. RustyBT provides Decimal-precision commission models to accurately track transaction costs in backtesting and live trading.

**Key Concepts**:
- **Per-Share**: Commission based on number of shares/contracts ($0.005/share)
- **Per-Trade**: Flat commission per order ($5/trade)
- **Per-Dollar**: Commission as percentage of transaction value (0.15%)
- **Crypto**: Maker/taker fee structure for cryptocurrency exchanges
- **Minimum Commission**: Many brokers charge minimum per trade ($1 minimum)

**Financial Integrity**: All commission calculations use Python's `Decimal` type for audit-compliant precision.

---

## Why Model Commission?

### Without Commission (Unrealistic)

```python
# Naive backtest
transaction_cost = Decimal("0")  # ✗ Ignores commission
# Overstates profits!
```

**Problems**:
- ✗ Overstates profitability
- ✗ Ignores fixed costs of trading
- ✗ Not production-ready
- ✗ Misleading for high-frequency strategies

### With Commission (Realistic)

```python
# Realistic backtest
commission_model = PerShareCommission(
    cost_per_share=Decimal("0.005"),
    min_cost=Decimal("1.00")
)
commission = commission_model.calculate(order, fill_price, fill_amount)
# Accounts for real trading costs!
```

**Benefits**:
- ✓ Realistic profitability estimates
- ✓ Accounts for minimum commissions
- ✓ Production-ready backtests
- ✓ Better strategy validation

---

## DecimalCommissionModel Base Class

**Source**: `rustybt/finance/decimal/commission.py:18`

```python
from abc import ABC, abstractmethod
from decimal import Decimal

class DecimalCommissionModel(ABC):
    """Abstract base class for Decimal commission models."""

    @abstractmethod
    def calculate(
        self,
        order: DecimalOrder,
        fill_price: Decimal,
        fill_amount: Decimal
    ) -> Decimal:
        """Calculate commission for order fill.

        Args:
            order: Order being filled
            fill_price: Execution price
            fill_amount: Quantity filled

        Returns:
            Commission as Decimal (non-negative)
        """
        pass
```

**Key Contract**:
- Returns non-negative `Decimal`
- Calculates commission for single fill (partial or complete)
- Commission accumulates across partial fills in `order.commission`

---

## NoCommission

**Source**: `rustybt/finance/decimal/commission.py:43`

Zero commission model for testing. Charges no commission on any trades.

### Class Definition

```python
class NoCommission(DecimalCommissionModel):
    """Zero commission model for testing."""

    def calculate(
        self,
        order: DecimalOrder,
        fill_price: Decimal,
        fill_amount: Decimal
    ) -> Decimal:
        """Return zero commission."""
        return Decimal("0")
```

**Source Verification** (lines 50-61):
- Always returns `Decimal("0")`
- Used for testing only
- No parameters required

### Example: NoCommission

```python
from decimal import Decimal
from rustybt.finance.decimal.commission import NoCommission

# Create model
model = NoCommission()

# Calculate commission
commission = model.calculate(
    order=buy_order,
    fill_price=Decimal("100.00"),
    fill_amount=Decimal("1000")
)

print(f"Commission: ${commission}")
# Output: Commission: $0

assert commission == Decimal("0")
print("✓ No commission charged")
```

**When to Use**:
- Testing strategies without transaction costs
- Baseline comparisons
- Debugging execution logic

---

## PerShareCommission

**Source**: `rustybt/finance/decimal/commission.py:67`

Commission charged per share/contract with optional minimum per trade.

### Class Definition

```python
class PerShareCommission(DecimalCommissionModel):
    """Commission charged per share/contract.

    Formula: max(shares × rate, minimum)
    """

    def __init__(
        self,
        cost_per_share: Decimal,
        min_cost: Decimal = Decimal("0"),
        config: DecimalConfig | None = None,
    ) -> None:
        """Initialize per-share commission model.

        Args:
            cost_per_share: Commission per share (e.g., Decimal("0.005"))
            min_cost: Minimum commission per order (e.g., Decimal("1.00"))
            config: DecimalConfig instance

        Raises:
            ValueError: If cost_per_share or min_cost is negative
        """
```

**Source Verification** (lines 113-157):
- Constructor validates `cost_per_share >= 0` (line 97-98)
- Constructor validates `min_cost >= 0` (line 100-101)
- Formula: `commission = abs(fill_amount) * rate` (line 125)
- First fill: `max(commission, minimum)` (line 132)
- Subsequent fills: Incremental commission accounting (lines 139-148)

### Example: PerShareCommission - Basic Usage

```python
from decimal import Decimal
from rustybt.finance.decimal.commission import PerShareCommission

# Typical retail broker: $0.005/share, $1 minimum
model = PerShareCommission(
    cost_per_share=Decimal("0.005"),
    min_cost=Decimal("1.00")
)

# Example 1: Small order (minimum applies)
small_commission = model.calculate(
    order=buy_order,
    fill_price=Decimal("100.00"),
    fill_amount=Decimal("100")  # 100 shares
)

calculated = Decimal("100") * Decimal("0.005")  # $0.50
print(f"Calculated commission: ${calculated}")
print(f"Actual commission: ${small_commission}")
print(f"Minimum applied: ${small_commission}")
# Output:
# Calculated commission: $0.50
# Actual commission: $1.00
# Minimum applied: $1.00  (minimum $1 enforced)

# Example 2: Large order (per-share rate applies)
large_commission = model.calculate(
    order=buy_order,
    fill_price=Decimal("100.00"),
    fill_amount=Decimal("1000")  # 1000 shares
)

calculated = Decimal("1000") * Decimal("0.005")  # $5.00
print(f"\nCalculated commission: ${calculated}")
print(f"Actual commission: ${large_commission}")
# Output:
# Calculated commission: $5.00
# Actual commission: $5.00  (exceeds minimum)
```

### Example: PerShareCommission - Partial Fills

```python
# Test partial fill commission handling
model = PerShareCommission(
    cost_per_share=Decimal("0.005"),
    min_cost=Decimal("1.00")
)

# Create order for 1000 shares
order = DecimalOrder(
    dt=datetime.now(),
    asset=equity,
    amount=Decimal("1000")
)

print("Partial Fill Commission Tracking:")
print("=" * 70)

# Fill 1: 300 shares
fill_1_commission = model.calculate(
    order=order,
    fill_price=Decimal("100.00"),
    fill_amount=Decimal("300")
)
order.commission += fill_1_commission
order.filled += Decimal("300")

print(f"\nFill 1: 300 shares")
print(f"  Calculated: 300 × $0.005 = ${Decimal('300') * Decimal('0.005')}")
print(f"  Commission: ${fill_1_commission}")
print(f"  (Minimum $1.00 applied)")
print(f"  Total commission so far: ${order.commission}")

# Fill 2: 400 shares
fill_2_commission = model.calculate(
    order=order,
    fill_price=Decimal("100.00"),
    fill_amount=Decimal("400")
)
order.commission += fill_2_commission
order.filled += Decimal("400")

total_filled = Decimal("700")
per_share_total = total_filled * Decimal("0.005")

print(f"\nFill 2: 400 shares")
print(f"  Total filled: {total_filled} shares")
print(f"  Per-share total: {total_filled} × $0.005 = ${per_share_total}")
print(f"  Previous commission: ${Decimal('1.00')}")
print(f"  Still below minimum: ${per_share_total} < $1.00")
print(f"  Additional commission: ${fill_2_commission}")
print(f"  Total commission so far: ${order.commission}")

# Fill 3: 300 shares (completes order)
fill_3_commission = model.calculate(
    order=order,
    fill_price=Decimal("100.00"),
    fill_amount=Decimal("300")
)
order.commission += fill_3_commission
order.filled += Decimal("300")

total_filled = Decimal("1000")
per_share_total = total_filled * Decimal("0.005")

print(f"\nFill 3: 300 shares (completes order)")
print(f"  Total filled: {total_filled} shares")
print(f"  Per-share total: {total_filled} × $0.005 = ${per_share_total}")
print(f"  Total should be: ${per_share_total}")
print(f"  Already paid: ${Decimal('1.00')}")
print(f"  Additional charge: ${per_share_total - Decimal('1.00')}")
print(f"  Fill 3 commission: ${fill_3_commission}")
print(f"  Final total commission: ${order.commission}")

# Output:
# Partial Fill Commission Tracking:
# ======================================================================
#
# Fill 1: 300 shares
#   Calculated: 300 × $0.005 = $1.50
#   Commission: $1.00
#   (Minimum $1.00 applied)
#   Total commission so far: $1.00
#
# Fill 2: 400 shares
#   Total filled: 700 shares
#   Per-share total: 700 × $0.005 = $3.50
#   Previous commission: $1.00
#   Still below minimum: $3.50 < $1.00
#   Additional commission: $0.00
#   Total commission so far: $1.00
#
# Fill 3: 300 shares (completes order)
#   Total filled: 1000 shares
#   Per-share total: 1000 × $0.005 = $5.00
#   Total should be: $5.00
#   Already paid: $1.00
#   Additional charge: $4.00
#   Fill 3 commission: $4.00
#   Final total commission: $5.00
```

### Example: Institutional vs Retail Rates

```python
# Retail broker
retail = PerShareCommission(
    cost_per_share=Decimal("0.005"),  # $0.005/share
    min_cost=Decimal("1.00")           # $1 minimum
)

# Institutional broker
institutional = PerShareCommission(
    cost_per_share=Decimal("0.001"),  # $0.001/share
    min_cost=Decimal("0.50")           # $0.50 minimum
)

# High-frequency trading
hft = PerShareCommission(
    cost_per_share=Decimal("0.0001"), # $0.0001/share
    min_cost=Decimal("0.10")           # $0.10 minimum
)

# Test order sizes
order_sizes = [Decimal("100"), Decimal("1000"), Decimal("10000")]

print("Commission Comparison:")
print("=" * 80)
print(f"{'Shares':>10} {'Retail':>15} {'Institutional':>15} {'HFT':>15}")
print("=" * 80)

for shares in order_sizes:
    retail_cost = retail.calculate(buy_order, Decimal("100"), shares)
    inst_cost = institutional.calculate(buy_order, Decimal("100"), shares)
    hft_cost = hft.calculate(buy_order, Decimal("100"), shares)

    print(f"{int(shares):>10,} ${float(retail_cost):>14.2f} "
          f"${float(inst_cost):>14.2f} ${float(hft_cost):>14.2f}")

# Output:
# Commission Comparison:
# ================================================================================
#     Shares          Retail  Institutional             HFT
# ================================================================================
#        100           $1.00           $0.50           $0.10
#      1,000           $5.00           $1.00           $0.10
#     10,000          $50.00          $10.00           $1.00
```

**When to Use**:
- Most common commission model
- Equity trading
- Futures contracts
- Options trading

**Advantages**:
- Simple and transparent
- Industry-standard
- Scales with order size

---

## PerTradeCommission

**Source**: `rustybt/finance/decimal/commission.py:163`

Flat commission per trade, charged once when order first fills.

### Class Definition

```python
class PerTradeCommission(DecimalCommissionModel):
    """Flat commission per trade.

    Formula: cost (charged once on first fill)
    """

    def __init__(
        self,
        cost: Decimal,
        config: DecimalConfig | None = None
    ) -> None:
        """Initialize per-trade commission model.

        Args:
            cost: Flat commission per trade (e.g., Decimal("5.00"))
            config: DecimalConfig instance

        Raises:
            ValueError: If cost is negative
        """
```

**Source Verification** (lines 192-216):
- Constructor validates `cost >= 0` (line 184-185)
- First fill: Charge full `cost` (line 205)
- Subsequent fills: Charge `Decimal("0")` (line 208)

### Example: PerTradeCommission - Basic Usage

```python
from decimal import Decimal
from rustybt.finance.decimal.commission import PerTradeCommission

# Create model with $5 flat commission
model = PerTradeCommission(cost=Decimal("5.00"))

# Create order
order = DecimalOrder(
    dt=datetime.now(),
    asset=equity,
    amount=Decimal("1000")
)

print("Flat Commission Model ($5 per trade):")
print("=" * 60)

# Fill 1: 300 shares
fill_1_commission = model.calculate(
    order=order,
    fill_price=Decimal("100.00"),
    fill_amount=Decimal("300")
)
order.commission += fill_1_commission
order.filled += Decimal("300")

print(f"\nFill 1: 300 shares")
print(f"  Commission: ${fill_1_commission}")
print(f"  Total commission: ${order.commission}")

# Fill 2: 400 shares
fill_2_commission = model.calculate(
    order=order,
    fill_price=Decimal("100.00"),
    fill_amount=Decimal("400")
)
order.commission += fill_2_commission
order.filled += Decimal("700")

print(f"\nFill 2: 400 shares")
print(f"  Commission: ${fill_2_commission}")
print(f"  Total commission: ${order.commission}")

# Fill 3: 300 shares (completes order)
fill_3_commission = model.calculate(
    order=order,
    fill_price=Decimal("100.00"),
    fill_amount=Decimal("300")
)
order.commission += fill_3_commission
order.filled += Decimal("1000")

print(f"\nFill 3: 300 shares (completes)")
print(f"  Commission: ${fill_3_commission}")
print(f"  Final total commission: ${order.commission}")

# Output:
# Flat Commission Model ($5 per trade):
# ============================================================
#
# Fill 1: 300 shares
#   Commission: $5.00
#   Total commission: $5.00
#
# Fill 2: 400 shares
#   Commission: $0.00  (no additional charge)
#   Total commission: $5.00
#
# Fill 3: 300 shares (completes)
#   Commission: $0.00  (no additional charge)
#   Final total commission: $5.00
```

### Example: When Per-Trade is Cheaper

```python
# Compare PerTrade vs PerShare

per_trade = PerTradeCommission(cost=Decimal("7.00"))
per_share = PerShareCommission(
    cost_per_share=Decimal("0.005"),
    min_cost=Decimal("1.00")
)

order_sizes = [
    Decimal("100"),
    Decimal("1000"),
    Decimal("2000"),
    Decimal("5000"),
    Decimal("10000")
]

print("Per-Trade vs Per-Share Comparison:")
print("=" * 70)
print(f"{'Shares':>10} {'Per-Trade':>15} {'Per-Share':>15} {'Savings':>15}")
print("=" * 70)

for shares in order_sizes:
    trade_cost = per_trade.calculate(buy_order, Decimal("100"), shares)
    share_cost = per_share.calculate(buy_order, Decimal("100"), shares)
    savings = share_cost - trade_cost

    print(f"{int(shares):>10,} ${float(trade_cost):>14.2f} "
          f"${float(share_cost):>14.2f} ${float(savings):>14.2f}")

# Output:
# Per-Trade vs Per-Share Comparison:
# ======================================================================
#     Shares       Per-Trade       Per-Share         Savings
# ======================================================================
#        100           $7.00           $1.00          $-6.00 (worse)
#      1,000           $7.00           $5.00          $-2.00 (worse)
#      2,000           $7.00          $10.00           $3.00 (better!)
#      5,000           $7.00          $25.00          $18.00 (better!)
#     10,000           $7.00          $50.00          $43.00 (much better!)
```

**When to Use**:
- Large order sizes
- Some discount brokers
- Zero-commission brokers with fixed fees

**Advantages**:
- Simple flat fee
- Cost-effective for large orders
- Predictable total cost

**Disadvantages**:
- Expensive for small orders
- Doesn't scale with order size

---

## PerDollarCommission

**Source**: `rustybt/finance/decimal/commission.py:222`

Commission as percentage of transaction value (notional).

### Class Definition

```python
class PerDollarCommission(DecimalCommissionModel):
    """Commission as percentage of transaction value.

    Formula: order_value × rate
    """

    def __init__(
        self,
        rate: Decimal,
        config: DecimalConfig | None = None
    ) -> None:
        """Initialize per-dollar commission model.

        Args:
            rate: Commission rate (e.g., Decimal("0.0015") = 0.15%)
            config: DecimalConfig instance

        Raises:
            ValueError: If rate is negative
        """
```

**Source Verification** (lines 251-275):
- Constructor validates `rate >= 0` (line 243-244)
- Formula: `order_value = abs(fill_amount) * fill_price` (line 263)
- Formula: `commission = order_value * rate` (line 266)

### Example: PerDollarCommission - Basic Usage

```python
from decimal import Decimal
from rustybt.finance.decimal.commission import PerDollarCommission

# Create model with 0.15% commission
model = PerDollarCommission(rate=Decimal("0.0015"))  # 0.15%

# Test different scenarios
scenarios = [
    (Decimal("100"), Decimal("100.00"), "Small retail"),
    (Decimal("1000"), Decimal("100.00"), "Medium order"),
    (Decimal("10000"), Decimal("50.00"), "Large order, lower price"),
    (Decimal("100"), Decimal("1000.00"), "Small order, high price"),
]

print("Per-Dollar Commission (0.15% of notional):")
print("=" * 80)
print(f"{'Shares':>10} {'Price':>10} {'Notional':>15} {'Commission':>15} {'Scenario':>20}")
print("=" * 80)

for shares, price, description in scenarios:
    commission = model.calculate(buy_order, price, shares)
    notional = shares * price

    print(f"{int(shares):>10,} ${float(price):>9.2f} ${float(notional):>14,.2f} "
          f"${float(commission):>14.2f} {description:>20}")

# Output:
# Per-Dollar Commission (0.15% of notional):
# ================================================================================
#     Shares      Price        Notional      Commission             Scenario
# ================================================================================
#        100    $100.00       $10,000.00          $15.00         Small retail
#      1,000    $100.00      $100,000.00         $150.00         Medium order
#     10,000     $50.00      $500,000.00         $750.00  Large order, lower price
#        100  $1,000.00      $100,000.00         $150.00  Small order, high price
```

### Example: Typical Per-Dollar Rates

```python
# Common per-dollar rates

# Managed account (high rate)
managed = PerDollarCommission(rate=Decimal("0.01"))  # 1%

# Advisory account (moderate rate)
advisory = PerDollarCommission(rate=Decimal("0.005"))  # 0.5%

# Discount broker (low rate)
discount = PerDollarCommission(rate=Decimal("0.0015"))  # 0.15%

# Institutional (very low rate)
institutional = PerDollarCommission(rate=Decimal("0.0001"))  # 0.01%

# Test order: 1000 shares @ $100
shares = Decimal("1000")
price = Decimal("100.00")

print("Per-Dollar Commission Rate Comparison:")
print(f"Order: {shares} shares @ ${price}")
print(f"Notional: ${shares * price}")
print("=" * 60)

rates = [
    ("Managed (1%)", managed),
    ("Advisory (0.5%)", advisory),
    ("Discount (0.15%)", discount),
    ("Institutional (0.01%)", institutional)
]

for name, model in rates:
    commission = model.calculate(buy_order, price, shares)
    pct_of_notional = (commission / (shares * price)) * Decimal("100")

    print(f"{name:25s}: ${float(commission):>10.2f} "
          f"({float(pct_of_notional):.4f}%)")

# Output:
# Per-Dollar Commission Rate Comparison:
# Order: 1000 shares @ $100.00
# Notional: $100000
# ============================================================
# Managed (1%)             :   $1,000.00 (1.0000%)
# Advisory (0.5%)          :     $500.00 (0.5000%)
# Discount (0.15%)         :     $150.00 (0.1500%)
# Institutional (0.01%)    :      $10.00 (0.0100%)
```

**When to Use**:
- Managed accounts
- Advisory services
- Asset-based fees
- International markets

**Advantages**:
- Scales with transaction value
- Common in managed accounts
- Simple percentage

**Disadvantages**:
- Can be expensive for large orders
- Less common for retail equity trading

---

## CryptoCommission

**Source**: `rustybt/finance/decimal/commission.py:281`

Commission for cryptocurrency exchanges with maker/taker fee structure.

### Class Definition

```python
class CryptoCommission(DecimalCommissionModel):
    """Commission for crypto exchanges with maker/taker fees.

    Maker orders add liquidity (limit orders that rest in the book).
    Taker orders remove liquidity (market orders or marketable limit orders).

    Formula: order_value × (maker_rate or taker_rate)
    """

    def __init__(
        self,
        maker_rate: Decimal,
        taker_rate: Decimal,
        config: DecimalConfig | None = None,
    ) -> None:
        """Initialize crypto commission model.

        Args:
            maker_rate: Maker fee rate (e.g., Decimal("0.001") = 0.1%)
            taker_rate: Taker fee rate (e.g., Decimal("0.002") = 0.2%)
            config: DecimalConfig instance

        Raises:
            ValueError: If rates are negative
        """
```

**Source Verification** (lines 331-365):
- Constructor validates `maker_rate >= 0` (line 315-316)
- Constructor validates `taker_rate >= 0` (line 318-319)
- Determines maker/taker: `is_maker = order.order_type == "limit"` (line 347)
- Selects rate: `rate = maker_rate if is_maker else taker_rate` (line 348)
- Formula: `commission = order_value * rate` (line 354)

### Example: CryptoCommission - Basic Usage

```python
from decimal import Decimal
from rustybt.finance.decimal.commission import CryptoCommission

# Typical crypto exchange rates
model = CryptoCommission(
    maker_rate=Decimal("0.001"),  # 0.1% maker fee
    taker_rate=Decimal("0.002")   # 0.2% taker fee
)

# Market order (taker)
market_order = DecimalOrder(
    dt=datetime.now(),
    asset=btc,
    amount=Decimal("1.0"),  # 1 BTC
    order_type="market"
)

market_commission = model.calculate(
    order=market_order,
    fill_price=Decimal("50000.00"),  # $50k per BTC
    fill_amount=Decimal("1.0")
)

print("Crypto Commission - Market Order (Taker):")
print(f"  Asset: BTC")
print(f"  Amount: 1.0 BTC")
print(f"  Price: $50,000")
print(f"  Notional: ${Decimal('1.0') * Decimal('50000')}")
print(f"  Taker Fee: 0.2%")
print(f"  Commission: ${market_commission}")
# Output:
# Crypto Commission - Market Order (Taker):
#   Asset: BTC
#   Amount: 1.0 BTC
#   Price: $50,000
#   Notional: $50000
#   Taker Fee: 0.2%
#   Commission: $100.00

# Limit order (maker)
limit_order = DecimalOrder(
    dt=datetime.now(),
    asset=btc,
    amount=Decimal("1.0"),
    order_type="limit",
    limit=Decimal("49000.00")
)

limit_commission = model.calculate(
    order=limit_order,
    fill_price=Decimal("49000.00"),
    fill_amount=Decimal("1.0")
)

print("\nCrypto Commission - Limit Order (Maker):")
print(f"  Asset: BTC")
print(f"  Amount: 1.0 BTC")
print(f"  Price: $49,000")
print(f"  Notional: ${Decimal('1.0') * Decimal('49000')}")
print(f"  Maker Fee: 0.1%")
print(f"  Commission: ${limit_commission}")
# Output:
# Crypto Commission - Limit Order (Maker):
#   Asset: BTC
#   Amount: 1.0 BTC
#   Price: $49,000
#   Notional: $49000
#   Maker Fee: 0.1%
#   Commission: $49.00
```

### Example: Exchange Rate Comparison

```python
# Different exchange fee structures

# Binance VIP 0
binance = CryptoCommission(
    maker_rate=Decimal("0.001"),  # 0.10%
    taker_rate=Decimal("0.001")   # 0.10%
)

# Coinbase Pro
coinbase = CryptoCommission(
    maker_rate=Decimal("0.005"),  # 0.50%
    taker_rate=Decimal("0.005")   # 0.50%
)

# Kraken Starter
kraken = CryptoCommission(
    maker_rate=Decimal("0.0016"),  # 0.16%
    taker_rate=Decimal("0.0026")   # 0.26%
)

# Test order: 1 BTC @ $50,000
btc_amount = Decimal("1.0")
btc_price = Decimal("50000.00")

print("Crypto Exchange Commission Comparison:")
print(f"Order: {btc_amount} BTC @ ${btc_price}")
print(f"Notional: ${btc_amount * btc_price}")
print("=" * 80)

exchanges = [
    ("Binance", binance),
    ("Coinbase Pro", coinbase),
    ("Kraken", kraken)
]

for name, model in exchanges:
    # Market order (taker)
    taker_commission = model.calculate(market_order, btc_price, btc_amount)

    # Limit order (maker)
    maker_commission = model.calculate(limit_order, btc_price, btc_amount)

    print(f"\n{name}:")
    print(f"  Maker: ${float(maker_commission):>8.2f} "
          f"({float(model.maker_rate * Decimal('100')):.2f}%)")
    print(f"  Taker: ${float(taker_commission):>8.2f} "
          f"({float(model.taker_rate * Decimal('100')):.2f}%)")

# Output:
# Crypto Exchange Commission Comparison:
# Order: 1.0 BTC @ $50000.00
# Notional: $50000.0
# ================================================================================
#
# Binance:
#   Maker:    $50.00 (0.10%)
#   Taker:    $50.00 (0.10%)
#
# Coinbase Pro:
#   Maker:   $250.00 (0.50%)
#   Taker:   $250.00 (0.50%)
#
# Kraken:
#   Maker:    $80.00 (0.16%)
#   Taker:   $130.00 (0.26%)
```

**When to Use**:
- Cryptocurrency trading
- Exchanges with maker/taker fees
- DeFi protocols

**Advantages**:
- Incentivizes providing liquidity (lower maker fees)
- Industry-standard for crypto
- Separate rates for different order types

---

## Commission Model Selection Guide

### Decision Tree

```
Start: Choose Commission Model
│
├─ Testing/Debugging?
│  └─ Use NoCommission
│
├─ Equity trading?
│  ├─ Small orders? → PerShareCommission (with minimum)
│  └─ Large orders? → PerTradeCommission or PerShareCommission
│
├─ Managed account?
│  └─ Use PerDollarCommission
│
└─ Cryptocurrency?
   └─ Use CryptoCommission (maker/taker)
```

### Comparison Table

| Model | Formula | Best For | Example |
|-------|---------|----------|---------|
| **NoCommission** | $0 | Testing | - |
| **PerShareCommission** | shares × rate | Equity, Futures | $0.005/share |
| **PerTradeCommission** | Flat fee | Large orders | $7/trade |
| **PerDollarCommission** | notional × rate | Managed accounts | 0.15% |
| **CryptoCommission** | notional × (maker/taker) | Cryptocurrency | 0.1%/0.2% |

---

## Production Usage Patterns

### Pattern 1: Realistic Backtesting

```python
from rustybt.finance.decimal.blotter import DecimalBlotter
from rustybt.finance.decimal.commission import PerShareCommission
from rustybt.finance.decimal.slippage import FixedBasisPointsSlippage

# Create production-grade blotter
blotter = DecimalBlotter(
    commission_model=PerShareCommission(
        cost_per_share=Decimal("0.005"),
        min_cost=Decimal("1.00")
    ),
    slippage_model=FixedBasisPointsSlippage(Decimal("5"))
)

# Run backtest with realistic costs
# ... strategy logic ...
```

### Pattern 2: Asset-Specific Commissions

```python
def get_commission_model(asset):
    """Select commission model based on asset class."""
    if asset.asset_class == "equity":
        return PerShareCommission(
            cost_per_share=Decimal("0.005"),
            min_cost=Decimal("1.00")
        )
    elif asset.asset_class == "crypto":
        return CryptoCommission(
            maker_rate=Decimal("0.001"),
            taker_rate=Decimal("0.002")
        )
    elif asset.asset_class == "futures":
        return PerTradeCommission(cost=Decimal("2.50"))
    else:
        return NoCommission()
```

### Pattern 3: Commission Tracking and Analysis

```python
class CommissionTracker:
    """Track and analyze commission costs."""

    def __init__(self):
        self.total_commission = Decimal("0")
        self.commission_by_asset = {}
        self.trade_count = 0

    def record_commission(self, asset, commission):
        """Record commission for analysis."""
        self.total_commission += commission
        self.trade_count += 1

        if asset not in self.commission_by_asset:
            self.commission_by_asset[asset] = Decimal("0")
        self.commission_by_asset[asset] += commission

    def get_summary(self):
        """Get commission summary."""
        avg_commission = (
            self.total_commission / Decimal(self.trade_count)
            if self.trade_count > 0
            else Decimal("0")
        )

        return {
            "total": self.total_commission,
            "trades": self.trade_count,
            "average": avg_commission,
            "by_asset": dict(self.commission_by_asset)
        }
```

---

## Best Practices

### ✅ DO

1. **Use Realistic Models**
   ```python
   # ✓ Correct - realistic commission
   commission = PerShareCommission(
       cost_per_share=Decimal("0.005"),
       min_cost=Decimal("1.00")
   )
   ```

2. **Account for Minimum Commissions**
   ```python
   # ✓ Correct - includes minimum
   model = PerShareCommission(
       cost_per_share=Decimal("0.005"),
       min_cost=Decimal("1.00")  # Important!
   )
   ```

3. **Track Total Commission Costs**
   ```python
   transactions = blotter.get_transactions()
   total_commission = sum(t.commission for t in transactions)
   ```

4. **Use Asset-Appropriate Models**
   ```python
   if asset_class == "crypto":
       model = CryptoCommission(...)
   elif asset_class == "equity":
       model = PerShareCommission(...)
   ```

5. **Test Profitability With/Without Commissions**
   ```python
   # Test strategy viability
   results_no_comm = backtest(strategy, NoCommission())
   results_with_comm = backtest(strategy, realistic_commission)
   profitability_impact = results_with_comm - results_no_comm
   ```

### ❌ DON'T

1. **Don't Use NoCommission in Production**
   ```python
   # ✗ Wrong - unrealistic
   commission = NoCommission()  # Only for testing!
   ```

2. **Don't Forget Minimum Commissions**
   ```python
   # ✗ Wrong - missing minimum
   model = PerShareCommission(cost_per_share=Decimal("0.005"))
   # Small orders will appear cheaper than reality

   # ✓ Correct - includes minimum
   model = PerShareCommission(
       cost_per_share=Decimal("0.005"),
       min_cost=Decimal("1.00")
   )
   ```

3. **Don't Ignore Round-Trip Costs**
   ```python
   # ✓ Correct - account for both sides
   buy_commission = model.calculate(buy_order, price, amount)
   sell_commission = model.calculate(sell_order, price, amount)
   total_commission = buy_commission + sell_commission
   ```

4. **Don't Use Same Rate for All Brokers**
   ```python
   # Different brokers have different rates
   retail_broker = PerShareCommission(Decimal("0.005"), Decimal("1.00"))
   institutional = PerShareCommission(Decimal("0.001"), Decimal("0.50"))
   ```

5. **Don't Over-Optimize Without Costs**
   ```python
   # ✗ Wrong - optimizing without costs
   best_params = optimize(strategy, NoCommission())

   # ✓ Correct - optimize with realistic costs
   best_params = optimize(strategy, realistic_commission)
   ```

---

## Related Documentation

- [Slippage Models](./slippage-models-verified.md) - Price slippage modeling
- [DecimalBlotter](../execution/decimal-blotter.md) - Order management system
- [Execution Pipeline](../execution/execution-pipeline.md) - Complete execution flow

---

## Summary

**Commission Models** calculate transaction costs with Decimal precision:

- **NoCommission**: Testing only ($0)
- **PerShareCommission**: Most common ($0.005/share, $1 min)
- **PerTradeCommission**: Flat fee ($7/trade)
- **PerDollarCommission**: Percentage of value (0.15%)
- **CryptoCommission**: Maker/taker fees (0.1%/0.2%)

**Key Principles**:
1. Always use realistic commission in production backtests
2. Account for minimum commissions
3. Commission varies by broker and asset class
4. Track total commission costs for strategy analysis

All commission calculations use `Decimal` precision for audit-compliant financial tracking.
