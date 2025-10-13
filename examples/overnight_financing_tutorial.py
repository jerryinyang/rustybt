"""
Tutorial: Overnight Financing for Leveraged Positions

This tutorial demonstrates how to use the OvernightFinancingModel to simulate
daily financing costs and credits for leveraged trading positions.

Topics covered:
1. Basic overnight financing with equity margin
2. Forex swap rates (positive and negative carry)
3. Day count conventions (360 vs 365)
4. CSV-based rate configuration
5. Integration with DecimalLedger
"""

from decimal import Decimal
from pathlib import Path

import pandas as pd

from rustybt.finance.costs import (
    AssetClass,
    CSVFinancingRateProvider,
    DictFinancingRateProvider,
    OvernightFinancingModel,
)
from rustybt.finance.decimal.ledger import DecimalLedger
from rustybt.finance.decimal.position import DecimalPosition

# ===========================================================================
# Example 1: Equity Margin Interest (Long Leverage)
# ===========================================================================

print("=" * 70)
print("Example 1: Equity Margin Interest for Leveraged Long Position")
print("=" * 70)

# Configure financing rates: 5% annual for equity margin
long_rates = {AssetClass.EQUITY: Decimal("0.05")}
provider = DictFinancingRateProvider(long_rates)
model = OvernightFinancingModel(provider, days_in_year=365)

# Scenario: $100,000 AAPL position with $50,000 cash (2x leverage)
# - Position value: $100,000
# - Cash used: $50,000
# - Leveraged amount: $50,000 (financed by broker)
# - Annual rate: 5%
# - Daily cost: $50,000 × (0.05 / 365) = $6.85/day

leveraged_exposure = Decimal("50000.00")
daily_financing, annual_rate = model.calculate_daily_financing(
    symbol="AAPL",
    asset_class=AssetClass.EQUITY,
    leveraged_exposure=leveraged_exposure,
    is_long=True,
    current_time=pd.Timestamp("2023-01-01"),
)

print("\nPosition Details:")
print("  Symbol: AAPL")
print("  Position Value: $100,000")
print("  Cash Used: $50,000")
print(f"  Leveraged Amount: ${leveraged_exposure:,.2f}")
print("  Leverage Ratio: 2.0x")
print("\nFinancing Costs:")
print(f"  Annual Rate: {float(annual_rate) * 100:.2f}%")
print(f"  Daily Cost: ${daily_financing:.2f}")
print(f"  Monthly Cost (30 days): ${daily_financing * 30:.2f}")
print(f"  Annual Cost: ${daily_financing * 365:.2f}")


# ===========================================================================
# Example 2: Forex Swap Rates (Negative Carry)
# ===========================================================================

print("\n" + "=" * 70)
print("Example 2: Forex Swap Rate - Negative Carry (EUR/USD)")
print("=" * 70)

# Configure forex swap rates
# Negative swap rate = trader pays to hold short position
symbol_overrides = {
    "EUR/USD": (Decimal("0"), Decimal("-0.005")),  # -0.5% = pay to short
}

forex_provider = DictFinancingRateProvider(
    long_rates={},
    short_rates={},
    symbol_overrides=symbol_overrides,
)
forex_model = OvernightFinancingModel(forex_provider, days_in_year=360)  # Forex uses 360

# Scenario: Short €100,000 at 1.10 = -$110,000
# - Swap rate: -0.5% (negative = trader pays)
# - Daily cost: $110,000 × (0.005 / 360) = $1.53/day

eur_financing, eur_rate = forex_model.calculate_daily_financing(
    symbol="EUR/USD",
    asset_class=AssetClass.FOREX,
    leveraged_exposure=Decimal("110000.00"),
    is_long=False,
    current_time=pd.Timestamp("2023-01-01"),
)

print("\nPosition Details:")
print("  Symbol: EUR/USD")
print("  Position: Short €100,000 at 1.10")
print("  USD Equivalent: $110,000")
print("\nSwap Costs:")
print(f"  Swap Rate: {float(eur_rate) * 100:.3f}%")
print(f"  Daily Cost: ${abs(eur_financing):.2f}")
print(f"  Annual Cost: ${abs(eur_financing) * 360:.2f}")
print("  Note: Negative swap rate = trader pays to hold short")


# ===========================================================================
# Example 3: Forex Positive Carry (USD/JPY)
# ===========================================================================

print("\n" + "=" * 70)
print("Example 3: Forex Swap Rate - Positive Carry (USD/JPY)")
print("=" * 70)

# Positive swap rate = trader receives for holding short (interest rate differential)
symbol_overrides_jpy = {
    "USD/JPY": (Decimal("0"), Decimal("0.012")),  # +1.2% = receive to short
}

jpy_provider = DictFinancingRateProvider(
    long_rates={},
    short_rates={},
    symbol_overrides=symbol_overrides_jpy,
)
jpy_model = OvernightFinancingModel(jpy_provider, days_in_year=360)

# Scenario: Short ¥10,000,000 at 110 = -$90,909
# - Swap rate: +1.2% (positive = trader receives)
# - Daily credit: $90,909 × (0.012 / 360) = $3.03/day (but shows as cost in calculation)

jpy_financing, jpy_rate = jpy_model.calculate_daily_financing(
    symbol="USD/JPY",
    asset_class=AssetClass.FOREX,
    leveraged_exposure=Decimal("90909.00"),
    is_long=False,
    current_time=pd.Timestamp("2023-01-01"),
)

print("\nPosition Details:")
print("  Symbol: USD/JPY")
print("  Position: Short ¥10,000,000 at 110")
print("  USD Equivalent: $90,909")
print("\nSwap Income:")
print(f"  Swap Rate: +{float(jpy_rate) * 100:.2f}%")
print(f"  Daily Calculation: ${jpy_financing:.2f}")
print(f"  Annual Benefit: ${jpy_financing * 360:.2f}")
print("  Note: Positive swap rate on short = trader profits from interest differential")


# ===========================================================================
# Example 4: Integration with DecimalLedger
# ===========================================================================

print("\n" + "=" * 70)
print("Example 4: Overnight Financing with DecimalLedger")
print("=" * 70)


# Create a simple mock asset class for this example
class MockAsset:
    def __init__(self, symbol, asset_class):
        self.symbol = symbol
        self.asset_class = asset_class

    def __hash__(self):
        return hash(self.symbol)

    def __eq__(self, other):
        return self.symbol == other.symbol


# Setup ledger with leveraged position
ledger = DecimalLedger(starting_cash=Decimal("100000.00"))

# Create AAPL asset and position
aapl = MockAsset("AAPL", AssetClass.EQUITY)
aapl_position = DecimalPosition(
    asset=aapl,
    amount=Decimal("666.67"),  # ~$100k at $150/share
    cost_basis=Decimal("150.00"),
    last_sale_price=Decimal("150.00"),
)
# Set cash_used to track leverage
aapl_position.cash_used = Decimal("50000.00")  # 50% cash, 50% margin
ledger.positions[aapl] = aapl_position

print("\nInitial Ledger State:")
print(f"  Cash: ${ledger.cash:,.2f}")
print(f"  Position: {aapl_position.amount} shares of AAPL @ ${aapl_position.last_sale_price}")
print(f"  Position Value: ${abs(aapl_position.market_value):,.2f}")
print(f"  Cash Used: ${aapl_position.cash_used:,.2f}")
print(f"  Leveraged Amount: ${abs(aapl_position.market_value) - aapl_position.cash_used:,.2f}")

# Apply overnight financing for 30 days
print("\nApplying overnight financing for 30 days...")

equity_provider = DictFinancingRateProvider(long_rates={AssetClass.EQUITY: Decimal("0.05")})
equity_model = OvernightFinancingModel(equity_provider, days_in_year=365)

start_date = pd.Timestamp("2023-01-01")
for day in range(30):
    current_time = start_date + pd.Timedelta(days=day)
    result = equity_model.apply_financing(ledger, current_time)

print("\nAfter 30 Days:")
print(f"  Cash: ${ledger.cash:,.2f}")
print(f"  Cash Debited: ${Decimal('100000.00') - ledger.cash:,.2f}")
print(f"  Accumulated Financing: ${aapl_position.accumulated_financing:,.2f}")
print(f"  Daily Average Cost: ${aapl_position.accumulated_financing / 30:,.2f}")


# ===========================================================================
# Example 5: Using CSV Rate Provider
# ===========================================================================

print("\n" + "=" * 70)
print("Example 5: CSV-Based Financing Rates")
print("=" * 70)

print("\nExample CSV format (config/financing_rates/default_rates.csv):")
print(
    """
symbol,asset_class,long_rate,short_rate,description
AAPL,equity,0.05,0.00,Standard margin interest for equities
MSFT,equity,0.05,0.00,Standard margin interest for equities
EUR/USD,forex,0.00,-0.005,Negative carry on EUR/USD short
USD/JPY,forex,0.00,0.012,Positive carry on USD/JPY short
BTC-USD,crypto,0.10,-0.02,Funding rate for BTC perpetuals
"""
)

csv_path = Path("config/financing_rates/default_rates.csv")
if csv_path.exists():
    print(f"\nLoading rates from {csv_path}...")
    csv_provider = CSVFinancingRateProvider(csv_path)

    # Test rate lookup
    aapl_rate = csv_provider.get_long_rate("AAPL", AssetClass.EQUITY, pd.Timestamp("2023-01-01"))
    print(f"  AAPL long financing rate: {float(aapl_rate) * 100:.2f}%")

    eur_rate = csv_provider.get_short_rate("EUR/USD", AssetClass.FOREX, pd.Timestamp("2023-01-01"))
    print(f"  EUR/USD short swap rate: {float(eur_rate) * 100:.3f}%")

    btc_rate = csv_provider.get_long_rate("BTC-USD", AssetClass.CRYPTO, pd.Timestamp("2023-01-01"))
    print(f"  BTC-USD long funding rate: {float(btc_rate) * 100:.2f}%")
else:
    print(f"\nNote: Create {csv_path} to use CSV-based rates")


print("\n" + "=" * 70)
print("Tutorial Complete!")
print("=" * 70)
print("\nKey Takeaways:")
print("  1. Long leverage always pays financing (debit from cash)")
print("  2. Short forex/crypto can pay OR receive (swap rates)")
print("  3. Use 365 days for equities, 360 days for forex")
print("  4. CSV providers support time-varying rates")
print("  5. DecimalLedger tracks accumulated financing per position")
