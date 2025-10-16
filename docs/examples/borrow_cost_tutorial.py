"""Tutorial: Borrow Cost Modeling for Short Positions

This tutorial demonstrates how to use RustyBT's borrow cost modeling
to simulate realistic costs for short selling strategies.

Borrow costs are daily interest charges on short positions based on
the difficulty of borrowing shares. Easy-to-borrow stocks (like AAPL)
have low rates (~0.3%), while hard-to-borrow stocks (like GME during
the 2021 squeeze) can have rates of 25% or more annually.

Formula:
    daily_cost = abs(position_value) * (annual_rate / 365)

Topics covered:
1. Setting up borrow rate providers (dict and CSV)
2. Calculating daily borrow costs
3. Accumulating costs over time
4. Impact on short strategy profitability
"""

from decimal import Decimal
from pathlib import Path

import pandas as pd

from rustybt.finance.costs import (
    BorrowCostModel,
    CSVBorrowRateProvider,
    DictBorrowRateProvider,
)
from rustybt.finance.decimal.ledger import DecimalLedger
from rustybt.finance.decimal.position import DecimalPosition


# Mock Asset class for demonstration
class MockAsset:
    """Simple asset class for tutorial purposes."""

    def __init__(self, symbol: str):
        self.symbol = symbol
        self.asset_type = "Equity"

    def __hash__(self):
        return hash(self.symbol)

    def __eq__(self, other):
        return self.symbol == other.symbol

    def __repr__(self):
        return f"Asset({self.symbol})"


def example_1_basic_borrow_cost_calculation():
    """Example 1: Basic borrow cost calculation for a single position."""
    print("\n" + "=" * 70)
    print("Example 1: Basic Borrow Cost Calculation")
    print("=" * 70)

    # Setup rates: AAPL is easy to borrow (0.3%), GME is hard (25%)
    rates = {"AAPL": Decimal("0.003"), "GME": Decimal("0.25")}

    provider = DictBorrowRateProvider(rates)
    model = BorrowCostModel(provider)

    # Calculate daily cost for AAPL short position
    aapl_position_value = Decimal("15000.00")  # 100 shares @ $150
    aapl_cost, aapl_rate = model.calculate_daily_cost(
        "AAPL", aapl_position_value, pd.Timestamp("2023-01-01")
    )

    print("\nAAPL (Easy-to-borrow):")
    print(f"  Position Value: ${aapl_position_value:,.2f}")
    print(f"  Annual Rate: {aapl_rate * 100:.2f}%")
    print(f"  Daily Cost: ${aapl_cost:.2f}")
    print(f"  Annual Cost (365 days): ${aapl_cost * 365:.2f}")

    # Calculate daily cost for GME short position
    gme_position_value = Decimal("20000.00")  # 100 shares @ $200
    gme_cost, gme_rate = model.calculate_daily_cost(
        "GME", gme_position_value, pd.Timestamp("2021-01-15")
    )

    print("\nGME (Hard-to-borrow during squeeze):")
    print(f"  Position Value: ${gme_position_value:,.2f}")
    print(f"  Annual Rate: {gme_rate * 100:.2f}%")
    print(f"  Daily Cost: ${gme_cost:.2f}")
    print(f"  Annual Cost (365 days): ${gme_cost * 365:.2f}")

    print("\nCost Comparison:")
    print(f"  GME costs {gme_cost / aapl_cost:.1f}x more than AAPL per day")


def example_2_cost_accumulation_over_time():
    """Example 2: Cost accumulation over 30-day holding period."""
    print("\n" + "=" * 70)
    print("Example 2: Cost Accumulation Over 30 Days")
    print("=" * 70)

    # Setup
    rates = {"TSLA": Decimal("0.015")}  # 1.5% annual
    provider = DictBorrowRateProvider(rates)
    model = BorrowCostModel(provider)

    # Create ledger with short position
    ledger = DecimalLedger(starting_cash=Decimal("100000.00"))
    tsla_asset = MockAsset(symbol="TSLA")

    position = DecimalPosition(
        asset=tsla_asset,
        amount=Decimal("-100"),  # Short 100 shares
        cost_basis=Decimal("250.00"),
        last_sale_price=Decimal("250.00"),
    )
    ledger.positions[tsla_asset] = position

    print("\nInitial Position:")
    print("  Symbol: TSLA")
    print(f"  Amount: {position.amount} (short)")
    print(f"  Price: ${position.last_sale_price}")
    print(f"  Position Value: ${abs(position.market_value):,.2f}")
    print(f"  Starting Cash: ${ledger.cash:,.2f}")
    print("  Annual Borrow Rate: 1.5%")

    # Simulate 30 days
    start_date = pd.Timestamp("2023-01-01")
    daily_costs = []

    for day in range(30):
        current_time = start_date + pd.Timedelta(days=day)
        result = model.accrue_costs(ledger, current_time)
        daily_costs.append(result.total_cost)

    # Results
    total_cost = sum(daily_costs, Decimal("0"))

    print("\n30-Day Results:")
    print(f"  Total Borrow Cost: ${total_cost:.2f}")
    print(f"  Average Daily Cost: ${total_cost / 30:.2f}")
    print(f"  Final Cash: ${ledger.cash:,.2f}")
    print(f"  Cash Reduction: ${Decimal('100000.00') - ledger.cash:.2f}")
    print(f"  Accumulated in Position: ${position.accumulated_borrow_cost:.2f}")

    # Impact on profitability
    print("\nImpact on Profitability:")
    print("  If TSLA drops 5% to $237.50:")
    profit = (Decimal("250.00") - Decimal("237.50")) * 100
    net_profit = profit - total_cost
    print(f"    Gross Profit: ${profit:.2f}")
    print(f"    Borrow Costs: $({total_cost:.2f})")
    print(f"    Net Profit: ${net_profit:.2f}")
    print(f"    Cost Impact: {(total_cost / profit * 100):.1f}% of gross profit")


def example_3_using_csv_rate_provider():
    """Example 3: Loading borrow rates from CSV file."""
    print("\n" + "=" * 70)
    print("Example 3: Using CSV Rate Provider")
    print("=" * 70)

    # Check if CSV file exists
    csv_path = Path("config/borrow_rates/default_rates.csv")

    if not csv_path.exists():
        print(f"\nCSV file not found at: {csv_path}")
        print("Create it with this format:")
        print("\nsymbol,annual_rate,description")
        print("AAPL,0.003,Easy to borrow")
        print("GME,0.25,Hard to borrow")
        return

    # Load CSV rates
    provider = CSVBorrowRateProvider(csv_path)
    model = BorrowCostModel(provider)

    print(f"\nLoaded rates from: {csv_path}")

    # Test different symbols
    test_symbols = ["AAPL", "TSLA", "GME", "AMC"]
    position_value = Decimal("10000.00")

    print(f"\nDaily costs for ${position_value:,.2f} position:")
    print(f"{'Symbol':<8} {'Annual Rate':<15} {'Daily Cost':<15} {'Annual Cost':<15}")
    print("-" * 60)

    for symbol in test_symbols:
        cost, rate = model.calculate_daily_cost(symbol, position_value, pd.Timestamp("2023-01-01"))

        if rate is not None:
            annual_cost = cost * Decimal("365")
            print(
                f"{symbol:<8} {float(rate) * 100:>6.2f}%        "
                f"${float(cost):>8.2f}        ${float(annual_cost):>8.2f}"
            )


def example_4_time_varying_rates():
    """Example 4: Time-varying borrow rates (historical)."""
    print("\n" + "=" * 70)
    print("Example 4: Time-Varying Borrow Rates")
    print("=" * 70)

    # Check if historical CSV file exists
    csv_path = Path("config/borrow_rates/historical_rates.csv")

    if not csv_path.exists():
        print(f"\nHistorical CSV file not found at: {csv_path}")
        print("Create it with this format:")
        print("\nsymbol,date,annual_rate,notes")
        print("GME,2021-01-01,0.05,Before squeeze")
        print("GME,2021-01-15,0.80,During squeeze")
        print("GME,2021-02-01,0.35,Post-squeeze")
        return

    # Load time-varying rates
    provider = CSVBorrowRateProvider(csv_path)
    model = BorrowCostModel(provider)

    print(f"\nLoaded historical rates from: {csv_path}")

    # Test GME rates at different times
    dates = [
        pd.Timestamp("2021-01-10"),  # Before squeeze
        pd.Timestamp("2021-01-20"),  # During squeeze
        pd.Timestamp("2021-02-15"),  # Post-squeeze
    ]

    position_value = Decimal("20000.00")

    print(f"\nGME borrow costs over time (${position_value:,.2f} position):")
    print(f"{'Date':<15} {'Annual Rate':<15} {'Daily Cost':<15} {'Monthly Cost':<15}")
    print("-" * 65)

    for date in dates:
        cost, rate = model.calculate_daily_cost("GME", position_value, date)

        monthly_cost = cost * Decimal("30")
        print(
            f"{date.date()!s:<15} {float(rate) * 100:>6.2f}%        "
            f"${float(cost):>8.2f}        ${float(monthly_cost):>8.2f}"
        )


def example_5_short_strategy_profitability():
    """Example 5: Complete short strategy with borrow costs."""
    print("\n" + "=" * 70)
    print("Example 5: Short Strategy Profitability Analysis")
    print("=" * 70)

    # Scenario: Short GME during squeeze
    rates = {"GME": Decimal("0.25")}
    provider = DictBorrowRateProvider(rates)
    model = BorrowCostModel(provider)

    # Initial setup
    ledger = DecimalLedger(starting_cash=Decimal("100000.00"))
    gme_asset = MockAsset(symbol="GME")

    entry_price = Decimal("300.00")
    shares = Decimal("-100")  # Short 100 shares

    position = DecimalPosition(
        asset=gme_asset,
        amount=shares,
        cost_basis=entry_price,
        last_sale_price=entry_price,
    )
    ledger.positions[gme_asset] = position

    print("\nStrategy Setup:")
    print(f"  Entry: Short 100 shares of GME at ${entry_price}")
    print(f"  Position Value: ${abs(position.market_value):,.2f}")
    print("  Borrow Rate: 25% annually")
    print("  Holding Period: 30 days")

    # Simulate 30 days
    start_date = pd.Timestamp("2021-01-15")

    for day in range(30):
        current_time = start_date + pd.Timedelta(days=day)
        model.accrue_costs(ledger, current_time)

    total_borrow_cost = position.accumulated_borrow_cost

    # Scenarios
    scenarios = [
        ("Favorable", Decimal("200.00"), "33% drop"),
        ("Moderate", Decimal("250.00"), "17% drop"),
        ("Breakeven", Decimal("293.84"), "2% drop"),
        ("Loss", Decimal("350.00"), "17% rise"),
    ]

    print("\nProfitability Scenarios (after 30 days):")
    print(
        f"{'Scenario':<12} {'Exit Price':<12} {'Gross P&L':<12} "
        f"{'Borrow Cost':<12} {'Net P&L':<12} {'Return %':<12}"
    )
    print("-" * 80)

    for scenario_name, exit_price, _move in scenarios:
        gross_pnl = (entry_price - exit_price) * abs(shares)
        net_pnl = gross_pnl - total_borrow_cost
        return_pct = (net_pnl / abs(position.market_value)) * 100

        print(
            f"{scenario_name:<12} ${float(exit_price):<11.2f} "
            f"${float(gross_pnl):>10.2f}  ${float(total_borrow_cost):>10.2f}  "
            f"${float(net_pnl):>10.2f}  {float(return_pct):>10.2f}%"
        )

    print("\nKey Insights:")
    print(f"  • Borrow costs: ${total_borrow_cost:.2f} over 30 days")
    print("  • Break-even price: ~$293.84 (factoring in costs)")
    print(
        f"  • Cost impact: {(total_borrow_cost / abs(position.market_value) * 100):.2f}% of position value"
    )
    print("  • High borrow rates significantly reduce profitability")


def main():
    """Run all tutorial examples."""
    print("\n" + "=" * 70)
    print(" BORROW COST MODELING TUTORIAL")
    print("=" * 70)

    example_1_basic_borrow_cost_calculation()
    example_2_cost_accumulation_over_time()
    example_3_using_csv_rate_provider()
    example_4_time_varying_rates()
    example_5_short_strategy_profitability()

    print("\n" + "=" * 70)
    print("Tutorial Complete!")
    print("=" * 70)
    print("\nFor more information, see:")
    print("  • rustybt/finance/costs.py - Implementation")
    print("  • tests/finance/test_costs.py - Unit tests")
    print("  • config/borrow_rates/ - Rate configuration files")
    print()


if __name__ == "__main__":
    main()
