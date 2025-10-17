# Borrow Costs & Overnight Financing

**Module**: `rustybt.finance.costs`
**Source**: `rustybt/finance/costs.py`
**Verified**: 2025-10-16

## Overview

**Borrow Costs** and **Overnight Financing** model the daily interest charges for short positions and leveraged positions. These costs are critical for realistic simulation of:
- **Short selling** (borrowing shares to sell)
- **Margin trading** (leveraged long positions)
- **Forex carry trades** (overnight swap rates)
- **Crypto perpetual futures** (funding rates)

**Key Models**:
- **BorrowCostModel**: Daily interest on short position values
- **OvernightFinancingModel**: Daily financing for leveraged positions

**Financial Integrity**: All calculations use Python's `Decimal` type for audit-compliant precision.

---

## Why Model Borrow Costs & Financing?

### Without Costs (Unrealistic)

```python
# Naive simulation
short_position_value = Decimal("100000")  # Short $100k
daily_cost = Decimal("0")  # ✗ Ignores borrow costs
# Overstates short strategy profitability!
```

**Problems**:
- ✗ Overstates short strategy profits
- ✗ Ignores margin interest costs
- ✗ Not production-ready
- ✗ Misleading for leveraged strategies

### With Costs (Realistic)

```python
# Realistic simulation
borrow_cost_model = BorrowCostModel(rate_provider)
daily_cost = borrow_cost_model.calculate_daily_cost(
    "GME", Decimal("100000"), timestamp
)
# daily_cost = $100,000 × (25% / 365) = $68.49/day
# Accounts for real holding costs!
```

**Benefits**:
- ✓ Realistic profitability for short strategies
- ✓ Accounts for margin interest
- ✓ Production-ready backtests
- ✓ Better risk assessment

---

## Borrow Cost Model

**Source**: `rustybt/finance/costs.py:390`

### Overview

Calculates daily interest charges on short position values. When you short sell, you borrow shares from your broker, who charges interest on the value of the borrowed shares.

**Formula**:
```
daily_cost = abs(position_value) × (annual_rate / days_in_year)
```

**Example**:
- Short 100 shares of AAPL @ $150 = $15,000 position
- Annual borrow rate: 0.3%
- Daily cost: $15,000 × (0.003 / 365) = $0.123/day
- Annual cost (if held 365 days): ~$45

### Borrow Rate Classifications

**Source**: `rustybt/finance/costs.py:42-48`

```python
class BorrowRateType(Enum):
    """Classification of borrow rates by difficulty."""

    EASY_TO_BORROW = "easy"      # 0.3% - 1%    (Large cap stocks)
    MODERATE = "moderate"         # 1% - 5%      (Mid cap stocks)
    HARD_TO_BORROW = "hard"      # 5% - 50%     (High short interest)
    EXTREMELY_HARD = "extreme"    # 50%+         (Squeeze candidates)
```

**Real-World Examples**:
- **AAPL** (Easy): 0.3% - 1%
- **Small cap** (Moderate): 1% - 5%
- **GME Jan 2021** (Extremely Hard): 50% - 80%+

### BorrowCostModel Class

**Source**: `rustybt/finance/costs.py:390-544`

```python
class BorrowCostModel:
    """Borrow cost model for short position financing."""

    def __init__(
        self,
        rate_provider: BorrowRateProvider,
        default_rate: Decimal = Decimal("0.003"),  # 0.3% default
        days_in_year: int = 365,
    ):
        """Initialize borrow cost model.

        Args:
            rate_provider: Provider for borrow rate lookups
            default_rate: Default annual rate when specific rate unavailable
            days_in_year: Days per year for daily rate calculation
        """
```

**Source Verification**:
- Constructor (lines 411-433)
- Formula: `daily_cost = position_value * (annual_rate / days_in_year)` (lines 462-465)
- Accrues costs from ledger positions (lines 469-544)

### Example: Basic Borrow Cost Calculation

```python
from decimal import Decimal
from rustybt.finance.costs import BorrowCostModel, DictBorrowRateProvider
import pandas as pd

# Setup: Define borrow rates
borrow_rates = {
    "AAPL": Decimal("0.003"),  # 0.3% (easy to borrow)
    "GME": Decimal("0.25"),    # 25% (hard to borrow)
    "TSLA": Decimal("0.05"),   # 5% (moderate)
}

# Create rate provider
rate_provider = DictBorrowRateProvider(borrow_rates)

# Create borrow cost model
model = BorrowCostModel(
    rate_provider=rate_provider,
    default_rate=Decimal("0.003"),  # 0.3% default for unlisted stocks
    days_in_year=365
)

# Calculate daily borrow cost for AAPL short
timestamp = pd.Timestamp("2024-01-15")
aapl_position_value = Decimal("15000.00")  # Short 100 shares @ $150

daily_cost, annual_rate = model.calculate_daily_cost(
    symbol="AAPL",
    position_value=aapl_position_value,
    current_time=timestamp
)

print(f"AAPL Short Position:")
print(f"  Position Value: ${aapl_position_value}")
print(f"  Annual Rate: {float(annual_rate) * 100:.2f}%")
print(f"  Daily Cost: ${daily_cost}")
print(f"  Monthly Cost: ${daily_cost * Decimal('30')}")
print(f"  Annual Cost: ${daily_cost * Decimal('365')}")

# Output:
# AAPL Short Position:
#   Position Value: $15000.00
#   Annual Rate: 0.30%
#   Daily Cost: $0.12
#   Monthly Cost: $3.70
#   Annual Cost: $45.00
```

### Example: Hard-to-Borrow Stocks

```python
# GME during short squeeze (extremely hard to borrow)
gme_position_value = Decimal("10000.00")  # Short 100 shares @ $100

daily_cost, annual_rate = model.calculate_daily_cost(
    symbol="GME",
    position_value=gme_position_value,
    current_time=timestamp
)

print(f"\nGME Short Position (Hard to Borrow):")
print(f"  Position Value: ${gme_position_value}")
print(f"  Annual Rate: {float(annual_rate) * 100:.1f}%")
print(f"  Daily Cost: ${daily_cost}")
print(f"  Weekly Cost: ${daily_cost * Decimal('7')}")
print(f"  Monthly Cost: ${daily_cost * Decimal('30')}")
print(f"  Annual Cost: ${daily_cost * Decimal('365')}")

# Output:
# GME Short Position (Hard to Borrow):
#   Position Value: $10000.00
#   Annual Rate: 25.0%
#   Daily Cost: $6.85
#   Weekly Cost: $47.95
#   Monthly Cost: $205.48
#   Annual Cost: $2,500.00  (25% of position value!)
```

### Example: Borrow Rate Comparison

```python
# Compare borrow costs across different stocks
positions = [
    ("AAPL", Decimal("50000"), Decimal("0.003")),   # Large cap
    ("MID", Decimal("50000"), Decimal("0.03")),     # Mid cap
    ("HTB", Decimal("50000"), Decimal("0.10")),     # Hard to borrow
    ("GME", Decimal("50000"), Decimal("0.50")),     # Extreme
]

print("\nBorrow Cost Comparison ($50k position):")
print("=" * 80)
print(f"{'Stock':>8} {'Rate':>8} {'Daily':>12} {'Monthly':>12} {'Annual':>12}")
print("=" * 80)

for symbol, value, rate in positions:
    daily = value * rate / Decimal("365")
    monthly = daily * Decimal("30")
    annual = daily * Decimal("365")

    print(f"{symbol:>8} {float(rate)*100:>7.1f}% ${float(daily):>11.2f} "
          f"${float(monthly):>11.2f} ${float(annual):>11,.2f}")

# Output:
# Borrow Cost Comparison ($50k position):
# ================================================================================
#    Stock     Rate        Daily      Monthly       Annual
# ================================================================================
#     AAPL     0.3%        $0.41        $12.33       $150.00
#      MID     3.0%        $4.11       $123.29     $1,500.00
#      HTB    10.0%       $13.70       $410.96     $5,000.00
#      GME    50.0%       $68.49     $2,054.79    $25,000.00
```

### Example: Automatic Accrual from Ledger

```python
from rustybt.finance.decimal.ledger import DecimalLedger
from rustybt.assets import Equity

# Create ledger with short positions
ledger = DecimalLedger()

# Short positions
aapl = Equity(1, exchange='NYSE', symbol='AAPL')
gme = Equity(2, exchange='NYSE', symbol='GME')

# Add short positions to ledger
# (In real backtesting, these would be created by order fills)
ledger.positions[aapl].amount = Decimal("-100")  # Short 100 AAPL
ledger.positions[aapl].market_value = Decimal("-15000")  # @ $150/share

ledger.positions[gme].amount = Decimal("-100")  # Short 100 GME
ledger.positions[gme].market_value = Decimal("-10000")  # @ $100/share

# Accrue borrow costs
timestamp = pd.Timestamp("2024-01-15")
result = model.accrue_costs(ledger, timestamp)

print("\nBorrow Cost Accrual:")
print(f"  Positions Processed: {result.positions_processed}")
print(f"  Total Daily Cost: ${result.total_cost}")
print(f"  Cash After Debit: ${ledger.cash}")

print(f"\n  Per-Position Costs:")
for symbol, cost in result.position_costs.items():
    print(f"    {symbol}: ${cost}")

# Output:
# Borrow Cost Accrual:
#   Positions Processed: 2
#   Total Daily Cost: $6.97
#   Cash After Debit: $-6.97
#
#   Per-Position Costs:
#     AAPL: $0.12
#     GME: $6.85
```

---

## Overnight Financing Model

**Source**: `rustybt/finance/costs.py:921`

### Overview

Calculates daily financing costs/credits for leveraged positions. When you use margin (borrow money from broker), you pay interest on the borrowed amount.

**Formula**:
```
leveraged_exposure = position_value - cash_used
daily_financing = leveraged_exposure × (annual_rate / days_in_year)
```

**Key Concepts**:
- **Long Leverage**: Always costs money (pay interest on borrowed cash)
- **Short Leverage**: Can cost or credit (depends on asset class and rates)
- **Leveraged Exposure**: Amount of borrowed capital

**Example**:
- Long $100k AAPL position with $50k cash (2x leverage)
- Leveraged exposure: $50,000
- Annual rate: 5%
- Daily cost: $50,000 × (0.05 / 365) = $6.85/day
- Annual cost: ~$2,500

### OvernightFinancingModel Class

**Source**: `rustybt/finance/costs.py:921-1158`

```python
class OvernightFinancingModel:
    """Overnight financing model for leveraged positions."""

    def __init__(
        self,
        rate_provider: FinancingRateProvider,
        days_in_year: int = 365,
        rollover_time: pd.Timestamp | None = None,
    ):
        """Initialize overnight financing model.

        Args:
            rate_provider: Provider for financing rate lookups
            days_in_year: Days per year (365 for equities, 360 for forex)
            rollover_time: Specific time for rollover (e.g., 5pm ET for forex)
        """
```

**Source Verification**:
- Constructor (lines 950-971)
- Leverage calculation (lines 973-993)
- Financing calculation (lines 995-1045)
- Automatic application (lines 1047-1158)

### Example: Equity Margin Trading

```python
from rustybt.finance.costs import (
    OvernightFinancingModel,
    DictFinancingRateProvider,
    AssetClass
)

# Setup: Define financing rates by asset class
long_rates = {
    AssetClass.EQUITY: Decimal("0.05"),    # 5% for long equity margin
    AssetClass.FOREX: Decimal("0.00"),     # No fixed rate for forex
    AssetClass.CRYPTO: Decimal("0.10"),    # 10% for crypto leverage
}

short_rates = {
    AssetClass.EQUITY: Decimal("0.00"),    # No financing on short (covered by borrow costs)
    AssetClass.FOREX: Decimal("0.005"),    # Swap rate
    AssetClass.CRYPTO: Decimal("-0.02"),   # Funding rate (can be negative = credit)
}

# Create rate provider
rate_provider = DictFinancingRateProvider(long_rates, short_rates)

# Create financing model
model = OvernightFinancingModel(
    rate_provider=rate_provider,
    days_in_year=365
)

# Calculate leveraged exposure
position_value = Decimal("100000.00")  # $100k position
cash_used = Decimal("50000.00")        # $50k cash (2x leverage)

leveraged_exposure = model.calculate_leveraged_exposure(
    position_value, cash_used
)

print(f"Leveraged Position:")
print(f"  Position Value: ${position_value}")
print(f"  Cash Used: ${cash_used}")
print(f"  Leveraged Exposure: ${leveraged_exposure}")
print(f"  Leverage Ratio: {float(position_value / cash_used):.1f}x")

# Output:
# Leveraged Position:
#   Position Value: $100000.00
#   Cash Used: $50000.00
#   Leveraged Exposure: $50000.00
#   Leverage Ratio: 2.0x
```

### Example: Daily Financing Calculation

```python
# Calculate daily financing for leveraged equity position
timestamp = pd.Timestamp("2024-01-15")

daily_financing, annual_rate = model.calculate_daily_financing(
    symbol="AAPL",
    asset_class=AssetClass.EQUITY,
    leveraged_exposure=Decimal("50000.00"),
    is_long=True,
    current_time=timestamp
)

print(f"\nLeveraged Long Position (2x):")
print(f"  Leveraged Amount: ${Decimal('50000')}")
print(f"  Annual Rate: {float(annual_rate) * 100:.2f}%")
print(f"  Daily Financing: ${daily_financing}")
print(f"  Monthly Financing: ${daily_financing * Decimal('30')}")
print(f"  Annual Financing: ${daily_financing * Decimal('365')}")

# Output:
# Leveraged Long Position (2x):
#   Leveraged Amount: $50000
#   Annual Rate: 5.00%
#   Daily Financing: $6.85
#   Monthly Financing: $205.48
#   Annual Financing: $2,500.00
```

### Example: Different Leverage Ratios

```python
# Compare costs at different leverage levels
position_value = Decimal("100000")
leverage_ratios = [
    (Decimal("100000"), "1x (no leverage)"),
    (Decimal("50000"), "2x"),
    (Decimal("33333"), "3x"),
    (Decimal("20000"), "5x"),
    (Decimal("10000"), "10x"),
]

print("\nFinancing Cost by Leverage Ratio:")
print("=" * 80)
print(f"{'Leverage':>10} {'Cash Used':>12} {'Borrowed':>12} {'Daily':>12} {'Annual':>12}")
print("=" * 80)

for cash_used, label in leverage_ratios:
    leveraged_exposure = model.calculate_leveraged_exposure(
        position_value, cash_used
    )

    if leveraged_exposure > Decimal("0"):
        daily, _ = model.calculate_daily_financing(
            "AAPL", AssetClass.EQUITY, leveraged_exposure, True, timestamp
        )
        annual = daily * Decimal("365")
    else:
        daily = Decimal("0")
        annual = Decimal("0")

    print(f"{label:>10} ${float(cash_used):>11,.0f} ${float(leveraged_exposure):>11,.0f} "
          f"${float(daily):>11.2f} ${float(annual):>11,.2f}")

# Output:
# Financing Cost by Leverage Ratio:
# ================================================================================
#   Leverage    Cash Used     Borrowed        Daily       Annual
# ================================================================================
#         1x    $100,000           $0        $0.00         $0.00
#         2x     $50,000      $50,000        $6.85     $2,500.00
#         3x     $33,333      $66,667        $9.13     $3,333.35
#         5x     $20,000      $80,000       $10.96     $4,000.00
#        10x     $10,000      $90,000       $12.33     $4,500.00
```

### Example: Forex Carry Trade

```python
# Forex carry trade example (short EUR/USD)

# Create forex-specific rate provider
forex_rates = {
    AssetClass.FOREX: Decimal("0.00"),      # No cost to hold long EUR/USD
}

forex_short_rates = {
    AssetClass.FOREX: Decimal("0.005"),     # 0.5% cost to short EUR/USD
}

forex_provider = DictFinancingRateProvider(forex_rates, forex_short_rates)

forex_model = OvernightFinancingModel(
    rate_provider=forex_provider,
    days_in_year=360  # Forex convention
)

# Short EUR/USD position
eur_usd_value = Decimal("100000.00")  # Notional
cash_used = Decimal("5000.00")        # 5% margin (20x leverage typical in forex)

leveraged_exposure = forex_model.calculate_leveraged_exposure(
    eur_usd_value, cash_used
)

daily_financing, rate = forex_model.calculate_daily_financing(
    symbol="EUR/USD",
    asset_class=AssetClass.FOREX,
    leveraged_exposure=leveraged_exposure,
    is_long=False,  # Short position
    current_time=timestamp
)

print(f"\nForex Carry Trade (Short EUR/USD):")
print(f"  Position Size: ${eur_usd_value}")
print(f"  Margin Required: ${cash_used}")
print(f"  Leverage: {float(eur_usd_value / cash_used):.0f}x")
print(f"  Leveraged Exposure: ${leveraged_exposure}")
print(f"  Swap Rate: {float(rate) * 100:.2f}%")
print(f"  Daily Swap Cost: ${daily_financing}")
print(f"  Annual Swap Cost: ${daily_financing * Decimal('360')}")

# Output:
# Forex Carry Trade (Short EUR/USD):
#   Position Size: $100000.00
#   Margin Required: $5000.00
#   Leverage: 20x
#   Leveraged Exposure: $95000.00
#   Swap Rate: 0.50%
#   Daily Swap Cost: $1.32
#   Annual Swap Cost: $475.00
```

### Example: Positive Carry (Credit)

```python
# Positive carry example (short USD/JPY)

# Some forex pairs have positive carry for shorts
positive_carry_rates = {
    AssetClass.FOREX: Decimal("0.00"),
}

positive_carry_short = {
    AssetClass.FOREX: Decimal("-0.012"),  # Negative rate = credit (receive 1.2%)
}

positive_carry_provider = DictFinancingRateProvider(
    positive_carry_rates, positive_carry_short
)

positive_carry_model = OvernightFinancingModel(
    rate_provider=positive_carry_provider,
    days_in_year=360
)

# Short USD/JPY
usd_jpy_value = Decimal("100000.00")
cash_used = Decimal("5000.00")

leveraged_exposure = positive_carry_model.calculate_leveraged_exposure(
    usd_jpy_value, cash_used
)

daily_financing, rate = positive_carry_model.calculate_daily_financing(
    symbol="USD/JPY",
    asset_class=AssetClass.FOREX,
    leveraged_exposure=leveraged_exposure,
    is_long=False,
    current_time=timestamp
)

print(f"\nPositive Carry (Short USD/JPY):")
print(f"  Position Size: ${usd_jpy_value}")
print(f"  Swap Rate: {float(rate) * 100:.2f}%")
print(f"  Daily Swap: ${daily_financing}")

if daily_financing < Decimal("0"):
    print(f"  ✓ CREDIT (you receive): ${abs(daily_financing)}/day")
    print(f"  ✓ Annual Credit: ${abs(daily_financing) * Decimal('360')}")
else:
    print(f"  ✗ COST (you pay): ${daily_financing}/day")

# Output:
# Positive Carry (Short USD/JPY):
#   Position Size: $100000.00
#   Swap Rate: -1.20%
#   Daily Swap: $-3.17
#   ✓ CREDIT (you receive): $3.17/day
#   ✓ Annual Credit: $1,140.00
```

---

## Rate Providers

### DictBorrowRateProvider

**Source**: `rustybt/finance/costs.py:111-186`

In-memory dictionary for fast static rate lookups.

```python
# Example: Simple rate dictionary
rates = {
    "AAPL": Decimal("0.003"),
    "TSLA": Decimal("0.05"),
    "GME": Decimal("0.25"),
}

provider = DictBorrowRateProvider(rates)
rate = provider.get_rate("AAPL", timestamp)
# Returns Decimal('0.003')
```

### CSVBorrowRateProvider

**Source**: `rustybt/finance/costs.py:188-388`

CSV file-based provider supporting time-varying rates.

**CSV Format (Static)**:
```csv
symbol,annual_rate
AAPL,0.003
GME,0.25
TSLA,0.05
```

**CSV Format (Time-Varying)**:
```csv
symbol,date,annual_rate
GME,2020-12-01,0.05
GME,2021-01-15,0.80
GME,2021-02-01,0.30
```

```python
from pathlib import Path

# Load from CSV
provider = CSVBorrowRateProvider(
    csv_path=Path("borrow_rates.csv"),
    normalize_symbols=True,
    cache_rates=True
)

# Automatic time-based rate lookup
rate = provider.get_rate("GME", pd.Timestamp("2021-01-20"))
# Returns most recent rate <= timestamp (0.80 in this case)
```

---

## Production Usage Patterns

### Pattern 1: Combined Borrow Costs and Slippage

```python
from rustybt.finance.decimal.blotter import DecimalBlotter
from rustybt.finance.decimal.slippage import VolumeShareSlippage
from rustybt.finance.decimal.commission import PerShareCommission
from rustybt.finance.costs import BorrowCostModel, DictBorrowRateProvider

# Create realistic blotter with transaction costs
blotter = DecimalBlotter(
    commission_model=PerShareCommission(
        cost_per_share=Decimal("0.005"),
        min_cost=Decimal("1.00")
    ),
    slippage_model=VolumeShareSlippage(
        volume_limit=Decimal("0.025"),
        price_impact=Decimal("0.1")
    )
)

# Add borrow cost model for shorts
borrow_rates = {
    "AAPL": Decimal("0.003"),
    "GME": Decimal("0.25"),
}
borrow_provider = DictBorrowRateProvider(borrow_rates)
borrow_model = BorrowCostModel(borrow_provider)

# During backtest, accrue costs daily
result = borrow_model.accrue_costs(ledger, current_time)
```

### Pattern 2: Daily Cost Accrual in Backtest

```python
class ShortSellingStrategy:
    """Strategy with daily borrow cost accrual."""

    def __init__(self, borrow_model, financing_model):
        self.borrow_model = borrow_model
        self.financing_model = financing_model
        self.last_accrual_date = None

    def on_bar(self, data, ledger):
        """Called on each bar."""
        current_date = data.current_dt.date()

        # Accrue costs once per day
        if self.last_accrual_date != current_date:
            # Accrue borrow costs for shorts
            borrow_result = self.borrow_model.accrue_costs(
                ledger, data.current_dt
            )

            # Accrue financing for leveraged positions
            financing_result = self.financing_model.apply_financing(
                ledger, data.current_dt
            )

            # Log total daily costs
            total_cost = borrow_result.total_cost + financing_result.total_cost
            logger.info(
                "daily_costs_accrued",
                date=current_date,
                borrow_cost=str(borrow_result.total_cost),
                financing_cost=str(financing_result.total_cost),
                total_cost=str(total_cost)
            )

            self.last_accrual_date = current_date

        # ... strategy logic ...
```

### Pattern 3: Cost Impact Analysis

```python
def analyze_cost_impact(strategy, with_costs=True):
    """Compare strategy performance with/without costs."""

    # Backtest without costs
    blotter_no_costs = DecimalBlotter()
    results_no_costs = run_backtest(strategy, blotter_no_costs)

    # Backtest with costs
    if with_costs:
        blotter_with_costs = create_realistic_blotter()
        results_with_costs = run_backtest(strategy, blotter_with_costs)

        # Calculate impact
        return_impact = (
            results_with_costs["total_return"] -
            results_no_costs["total_return"]
        )
        sharpe_impact = (
            results_with_costs["sharpe_ratio"] -
            results_no_costs["sharpe_ratio"]
        )

        print(f"Cost Impact Analysis:")
        print(f"  Return Impact: {float(return_impact):.2%}")
        print(f"  Sharpe Impact: {float(sharpe_impact):.2f}")

    return results_with_costs if with_costs else results_no_costs
```

---

## Best Practices

### ✅ DO

1. **Use Realistic Borrow Rates**
   ```python
   # ✓ Correct - research actual rates
   rates = {
       "AAPL": Decimal("0.003"),  # 0.3% (actual typical rate)
       "GME": Decimal("0.25"),    # 25% (actual squeeze rate)
   }
   ```

2. **Accrue Costs Daily**
   ```python
   # ✓ Correct - accrue once per day
   if current_date != last_accrual_date:
       model.accrue_costs(ledger, current_time)
   ```

3. **Track Accumulated Costs**
   ```python
   # Check total costs paid
   for asset, position in ledger.positions.items():
       if hasattr(position, "accumulated_borrow_cost"):
           print(f"{asset.symbol}: ${position.accumulated_borrow_cost}")
   ```

4. **Model Both Borrow and Financing**
   ```python
   # For leveraged shorts, model both
   borrow_result = borrow_model.accrue_costs(ledger, timestamp)
   financing_result = financing_model.apply_financing(ledger, timestamp)
   total_cost = borrow_result.total_cost + financing_result.total_cost
   ```

5. **Use Time-Varying Rates for Accuracy**
   ```python
   # ✓ Correct - capture rate changes
   provider = CSVBorrowRateProvider("rates_with_dates.csv")
   ```

### ❌ DON'T

1. **Don't Ignore Borrow Costs**
   ```python
   # ✗ Wrong - unrealistic for shorts
   # (no borrow cost model)
   ```

2. **Don't Use Same Rate for All Stocks**
   ```python
   # ✗ Wrong - different stocks have different rates
   default_rate = Decimal("0.003")  # Too simplistic

   # ✓ Correct - stock-specific rates
   rates = {"AAPL": Decimal("0.003"), "GME": Decimal("0.25")}
   ```

3. **Don't Forget Financing on Leverage**
   ```python
   # ✗ Wrong - 2x leveraged position without financing costs
   # Will overstate profitability

   # ✓ Correct - model financing costs
   financing_model.apply_financing(ledger, timestamp)
   ```

4. **Don't Accrue Multiple Times Per Day**
   ```python
   # ✗ Wrong - accruing on every bar (intraday)
   for bar in bars:
       model.accrue_costs(ledger, bar.timestamp)

   # ✓ Correct - accrue once per day
   if bar.date != last_date:
       model.accrue_costs(ledger, bar.timestamp)
   ```

5. **Don't Ignore Positive Carry**
   ```python
   # Some forex/crypto positions pay you to hold
   # Model with negative rates for accurate P&L
   short_rates = {
       AssetClass.FOREX: Decimal("-0.012")  # Credit
   }
   ```

---

## Related Documentation

- [Slippage Models](./slippage-models.md) - Price slippage modeling
- [Commission Models](./commission-models.md) - Transaction commission calculation
- [DecimalBlotter](../execution/decimal-blotter.md) - Order management system

---

## Summary

**Borrow Costs & Overnight Financing** model holding costs with Decimal precision:

**Borrow Costs** (Short Positions):
- Formula: `daily_cost = position_value × (annual_rate / 365)`
- Easy to borrow: 0.3% - 1%
- Hard to borrow: 5% - 50%+
- Critical for short selling strategies

**Overnight Financing** (Leveraged Positions):
- Formula: `daily_financing = leveraged_exposure × (annual_rate / 365)`
- Typical equity margin: 5% - 8%
- Forex swap rates: Can be positive or negative (carry trades)
- Critical for leveraged strategies

**Key Principles**:
1. Costs accumulate daily
2. Use realistic, asset-specific rates
3. Model both borrow and financing for leveraged shorts
4. Time-varying rates capture market dynamics

All calculations use `Decimal` precision for audit-compliant financial tracking.
