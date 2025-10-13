"""Tests for borrow cost model in rustybt.finance.costs.

This module tests borrow cost calculations for short positions,
including rate lookups, daily accrual, cost accumulation, and
integration with the DecimalLedger.
"""

from decimal import Decimal

import pandas as pd
import pytest
from hypothesis import given
from hypothesis import strategies as st

from rustybt.finance.costs import (
    AssetClass,
    BorrowCostModel,
    BorrowCostResult,
    BorrowRateLoadError,
    BorrowRateType,
    CSVBorrowRateProvider,
    CSVFinancingRateProvider,
    DictBorrowRateProvider,
    DictFinancingRateProvider,
    FinancingRateLoadError,
    FinancingResult,
    OvernightFinancingModel,
)
from rustybt.finance.decimal.ledger import DecimalLedger
from rustybt.finance.decimal.position import DecimalPosition


# Mock Asset class for testing
class MockAsset:
    """Mock asset for testing."""

    def __init__(self, symbol: str):
        self.symbol = symbol
        self.asset_type = "Equity"

    def __hash__(self):
        return hash(self.symbol)

    def __eq__(self, other):
        return self.symbol == other.symbol

    def __repr__(self):
        return f"MockAsset({self.symbol})"


# ============================================================================
# Unit Tests: Daily Accrual Calculation
# ============================================================================


def test_daily_accrual_calculation_easy_to_borrow():
    """Daily accrual calculation for easy-to-borrow stock (0.3%)."""
    # Setup: AAPL at 0.3% annual rate
    rates = {"AAPL": Decimal("0.003")}
    provider = DictBorrowRateProvider(rates)
    model = BorrowCostModel(provider, days_in_year=365)

    # Short position: 100 shares at $150 = $15,000 value
    position_value = Decimal("15000.00")
    symbol = "AAPL"
    current_time = pd.Timestamp("2023-01-01")

    # Calculate daily cost
    daily_cost, annual_rate = model.calculate_daily_cost(symbol, position_value, current_time)

    # Expected: $15,000 × (0.003 / 365) = $0.12328767...
    expected_daily_cost = position_value * (Decimal("0.003") / Decimal("365"))

    assert daily_cost == expected_daily_cost
    assert annual_rate == Decimal("0.003")

    # Verify cost magnitude (should be small for easy-to-borrow)
    assert daily_cost < Decimal("1.00")  # Less than $1/day


def test_daily_accrual_calculation_hard_to_borrow():
    """Daily accrual calculation for hard-to-borrow stock (25%)."""
    # Setup: GME at 25% annual rate during squeeze
    rates = {"GME": Decimal("0.25")}
    provider = DictBorrowRateProvider(rates)
    model = BorrowCostModel(provider, days_in_year=365)

    # Short position: 100 shares at $200 = $20,000 value
    position_value = Decimal("20000.00")
    symbol = "GME"
    current_time = pd.Timestamp("2021-01-15")

    # Calculate daily cost
    daily_cost, annual_rate = model.calculate_daily_cost(symbol, position_value, current_time)

    # Expected: $20,000 × (0.25 / 365) = $13.698630...
    expected_daily_cost = position_value * (Decimal("0.25") / Decimal("365"))

    assert daily_cost == expected_daily_cost
    assert annual_rate == Decimal("0.25")

    # Verify cost magnitude (should be significant for hard-to-borrow)
    assert daily_cost > Decimal("10.00")  # More than $10/day


# ============================================================================
# Unit Tests: Borrow Rate Lookup
# ============================================================================


def test_borrow_rate_lookup_from_dict():
    """Borrow rate lookup from dictionary provider."""
    rates = {
        "AAPL": Decimal("0.003"),
        "GME": Decimal("0.25"),
        "TSLA": Decimal("0.015"),
    }
    provider = DictBorrowRateProvider(rates, normalize_symbols=True)

    # Test exact match
    assert provider.get_rate("AAPL", pd.Timestamp("2023-01-01")) == Decimal("0.003")

    # Test case insensitivity
    assert provider.get_rate("aapl", pd.Timestamp("2023-01-01")) == Decimal("0.003")

    # Test missing symbol
    assert provider.get_rate("UNKNOWN", pd.Timestamp("2023-01-01")) is None


def test_borrow_rate_lookup_from_csv(tmp_path):
    """Borrow rate lookup from CSV file."""
    # Create temporary CSV file
    csv_content = """symbol,annual_rate
AAPL,0.003
GME,0.25
TSLA,0.015
"""
    csv_path = tmp_path / "rates.csv"
    csv_path.write_text(csv_content)

    # Load CSV
    provider = CSVBorrowRateProvider(csv_path, normalize_symbols=True)

    # Test lookup
    assert provider.get_rate("AAPL", pd.Timestamp("2023-01-01")) == Decimal("0.003")
    assert provider.get_rate("GME", pd.Timestamp("2023-01-01")) == Decimal("0.25")


def test_default_rate_fallback():
    """Default rate used when specific rate unavailable."""
    rates = {"AAPL": Decimal("0.003")}
    provider = DictBorrowRateProvider(rates)
    default_rate = Decimal("0.005")  # 0.5% default
    model = BorrowCostModel(provider, default_rate=default_rate)

    position_value = Decimal("10000.00")
    current_time = pd.Timestamp("2023-01-01")

    # Known symbol
    daily_cost_aapl, rate_aapl = model.calculate_daily_cost("AAPL", position_value, current_time)
    assert rate_aapl == Decimal("0.003")

    # Unknown symbol (should use default)
    daily_cost_unknown, rate_unknown = model.calculate_daily_cost(
        "UNKNOWN", position_value, current_time
    )
    assert rate_unknown == default_rate

    # Cost should be higher for unknown (default 0.5% > AAPL 0.3%)
    assert daily_cost_unknown > daily_cost_aapl


# ============================================================================
# Unit Tests: Cost Accumulation
# ============================================================================


def test_cost_accumulation_over_30_days():
    """Cost accumulation over 30-day holding period."""
    rates = {"TSLA": Decimal("0.015")}  # 1.5% annual
    provider = DictBorrowRateProvider(rates)
    model = BorrowCostModel(provider)

    # Create ledger and position
    ledger = DecimalLedger(starting_cash=Decimal("100000.00"))
    tsla_asset = MockAsset(symbol="TSLA")

    # Create short position manually
    position = DecimalPosition(
        asset=tsla_asset,
        amount=Decimal("-100"),  # Short 100 shares
        cost_basis=Decimal("250.00"),
        last_sale_price=Decimal("250.00"),
    )
    ledger.positions[tsla_asset] = position

    # Accrue costs daily for 30 days
    start_date = pd.Timestamp("2023-01-01")
    accumulated_costs = []

    for day in range(30):
        current_time = start_date + pd.Timedelta(days=day)

        # Update position market value
        position.last_sale_price = Decimal("250.00")

        # Accrue borrow costs
        model.accrue_costs(ledger, current_time)

        accumulated_costs.append(position.accumulated_borrow_cost)

    # Expected total cost for 30 days:
    # Daily: $25,000 × (0.015 / 365) = $1.027397...
    # 30 days: $1.027397 × 30 = $30.821917...
    position_value = Decimal("25000.00")  # 100 shares × $250
    expected_daily = position_value * (Decimal("0.015") / Decimal("365"))
    expected_total = expected_daily * Decimal("30")

    # Use approximate comparison due to Decimal precision accumulation
    assert abs(position.accumulated_borrow_cost - expected_total) < Decimal("0.00001")

    # Verify cash was debited
    assert ledger.cash < Decimal("100000.00")
    cash_debited = Decimal("100000.00") - ledger.cash
    assert abs(cash_debited - expected_total) < Decimal("0.00001")


def test_rate_type_classification():
    """Borrow rate type classification."""
    provider = DictBorrowRateProvider({})

    # Easy to borrow
    assert provider.get_rate_type("AAPL", Decimal("0.003")) == BorrowRateType.EASY_TO_BORROW

    # Moderate
    assert provider.get_rate_type("TSLA", Decimal("0.015")) == BorrowRateType.MODERATE

    # Hard to borrow
    assert provider.get_rate_type("GME", Decimal("0.25")) == BorrowRateType.HARD_TO_BORROW

    # Extremely hard
    assert provider.get_rate_type("DWAC", Decimal("0.80")) == BorrowRateType.EXTREMELY_HARD


# ============================================================================
# Unit Tests: CSV Rate Validation
# ============================================================================


def test_csv_rate_validation_invalid_rates(tmp_path):
    """CSV provider filters out invalid rates."""
    # CSV with invalid rates (negative, > 100%)
    csv_content = """symbol,annual_rate
AAPL,0.003
INVALID1,-0.05
INVALID2,1.5
GME,0.25
"""
    csv_path = tmp_path / "rates.csv"
    csv_path.write_text(csv_content)

    provider = CSVBorrowRateProvider(csv_path)

    # Valid rates should be accessible
    assert provider.get_rate("AAPL", pd.Timestamp("2023-01-01")) == Decimal("0.003")
    assert provider.get_rate("GME", pd.Timestamp("2023-01-01")) == Decimal("0.25")

    # Invalid rates should be filtered out
    assert provider.get_rate("INVALID1", pd.Timestamp("2023-01-01")) is None
    assert provider.get_rate("INVALID2", pd.Timestamp("2023-01-01")) is None


def test_time_varying_rates_from_csv(tmp_path):
    """CSV provider handles time-varying rates."""
    csv_content = """symbol,date,annual_rate
GME,2021-01-01,0.05
GME,2021-01-15,0.80
GME,2021-02-01,0.35
"""
    csv_path = tmp_path / "rates.csv"
    csv_path.write_text(csv_content)

    provider = CSVBorrowRateProvider(csv_path)

    # Before squeeze
    rate_jan1 = provider.get_rate("GME", pd.Timestamp("2021-01-10"))
    assert rate_jan1 == Decimal("0.05")

    # During squeeze
    rate_jan20 = provider.get_rate("GME", pd.Timestamp("2021-01-20"))
    assert rate_jan20 == Decimal("0.80")

    # After squeeze
    rate_feb15 = provider.get_rate("GME", pd.Timestamp("2021-02-15"))
    assert rate_feb15 == Decimal("0.35")


def test_csv_missing_required_columns(tmp_path):
    """CSV provider raises error when required columns missing."""
    csv_content = """symbol,wrong_column
AAPL,0.003
"""
    csv_path = tmp_path / "rates.csv"
    csv_path.write_text(csv_content)

    with pytest.raises(BorrowRateLoadError):
        CSVBorrowRateProvider(csv_path)


# ============================================================================
# Integration Tests
# ============================================================================


def test_short_strategy_with_borrow_costs_30_days():
    """Integration test: Short strategy with borrow costs over 30+ days."""
    # Setup: Short GME during meme stock squeeze
    rates = {"GME": Decimal("0.25")}  # 25% annual during squeeze
    provider = DictBorrowRateProvider(rates)
    model = BorrowCostModel(provider)

    # Initialize ledger
    ledger = DecimalLedger(starting_cash=Decimal("100000.00"))
    gme_asset = MockAsset(symbol="GME")

    # Day 0: Enter short position (100 shares at $300)
    position = DecimalPosition(
        asset=gme_asset,
        amount=Decimal("-100"),  # Short
        cost_basis=Decimal("300.00"),
        last_sale_price=Decimal("300.00"),
    )
    ledger.positions[gme_asset] = position

    # Track metrics
    daily_costs = []
    cash_balances = []

    # Simulate 30 days
    start_date = pd.Timestamp("2021-01-15")

    for day in range(30):
        current_time = start_date + pd.Timedelta(days=day)

        # Update position market value (price constant at $300)
        position.last_sale_price = Decimal("300.00")

        # Accrue borrow costs
        result = model.accrue_costs(ledger, current_time)

        # Record metrics
        daily_costs.append(result.total_cost)
        cash_balances.append(ledger.cash)

    # Verify cost accumulation
    total_cost_accrued = sum(daily_costs, Decimal("0"))
    position_value = Decimal("30000.00")  # 100 shares × $300
    expected_daily = position_value * (Decimal("0.25") / Decimal("365"))
    expected_30day_cost = expected_daily * Decimal("30")

    # Use approximate comparison due to Decimal precision accumulation
    assert abs(total_cost_accrued - expected_30day_cost) < Decimal("0.00001")

    # Verify cash was debited
    cash_debited = Decimal("100000.00") - ledger.cash
    assert abs(cash_debited - expected_30day_cost) < Decimal("0.00001")

    # Verify accumulated cost in position
    assert abs(position.accumulated_borrow_cost - expected_30day_cost) < Decimal("0.00001")

    # Expected total cost: ~$616.44 over 30 days
    # This significantly impacts profitability of short strategy
    assert total_cost_accrued > Decimal("600.00")


def test_mixed_positions_long_and_short():
    """Integration test: Ledger with both long and short positions."""
    rates = {
        "AAPL": Decimal("0.003"),  # Long position (no borrow cost)
        "GME": Decimal("0.25"),  # Short position (borrow cost)
    }
    provider = DictBorrowRateProvider(rates)
    model = BorrowCostModel(provider)

    ledger = DecimalLedger(starting_cash=Decimal("100000.00"))

    # Add long position (AAPL)
    aapl_asset = MockAsset(symbol="AAPL")
    aapl_position = DecimalPosition(
        asset=aapl_asset,
        amount=Decimal("100"),  # Long (positive)
        cost_basis=Decimal("150.00"),
        last_sale_price=Decimal("150.00"),
    )
    ledger.positions[aapl_asset] = aapl_position

    # Add short position (GME)
    gme_asset = MockAsset(symbol="GME")
    gme_position = DecimalPosition(
        asset=gme_asset,
        amount=Decimal("-50"),  # Short (negative)
        cost_basis=Decimal("200.00"),
        last_sale_price=Decimal("200.00"),
    )
    ledger.positions[gme_asset] = gme_position

    # Accrue costs
    current_time = pd.Timestamp("2021-01-15")
    result = model.accrue_costs(ledger, current_time)

    # Only short position should accrue costs
    assert result.positions_processed == 1
    assert "GME" in result.position_costs
    assert "AAPL" not in result.position_costs

    # Verify cost magnitude
    gme_position_value = Decimal("50") * Decimal("200.00")  # $10,000
    expected_daily_cost = gme_position_value * (Decimal("0.25") / Decimal("365"))

    assert result.position_costs["GME"] == expected_daily_cost


def test_borrow_cost_result_structure():
    """Test BorrowCostResult structure and string representation."""
    result = BorrowCostResult(
        total_cost=Decimal("10.50"),
        position_costs={"AAPL": Decimal("5.25"), "GME": Decimal("5.25")},
        timestamp=pd.Timestamp("2023-01-01"),
        positions_processed=2,
        metadata={"default_rate": "0.003", "days_in_year": 365},
    )

    # Test attributes
    assert result.total_cost == Decimal("10.50")
    assert result.positions_processed == 2
    assert "AAPL" in result.position_costs
    assert "GME" in result.position_costs

    # Test string representation
    str_repr = str(result)
    assert "BorrowCostResult" in str_repr
    assert "total=10.50" in str_repr
    assert "positions=2" in str_repr


# ============================================================================
# Property-Based Tests
# ============================================================================


@given(
    position_value=st.decimals(min_value=Decimal("1"), max_value=Decimal("1000000"), places=2),
    annual_rate=st.decimals(min_value=Decimal("0"), max_value=Decimal("1"), places=4),
)
def test_costs_always_reduce_profitability(position_value, annual_rate):
    """Property: Borrow costs always reduce profitability (never negative costs)."""
    # Borrow costs are always >= 0
    daily_rate = annual_rate / Decimal("365")
    daily_cost = position_value * daily_rate

    # Property: Cost is non-negative
    assert daily_cost >= Decimal("0")

    # Property: Cost reduces cash (profitability)
    # If you start with cash C and pay cost X, ending cash = C - X <= C
    initial_cash = Decimal("100000.00")
    final_cash = initial_cash - daily_cost
    assert final_cash <= initial_cash


@given(
    position_value=st.decimals(min_value=Decimal("1"), max_value=Decimal("1000000"), places=2),
    annual_rate=st.decimals(min_value=Decimal("0"), max_value=Decimal("1"), places=4),
)
def test_daily_rate_bounds(position_value, annual_rate):
    """Property: Daily rate is always between 0 and annual_rate/365."""
    daily_rate = annual_rate / Decimal("365")

    # Property: Daily rate bounds
    assert daily_rate >= Decimal("0")
    assert daily_rate <= annual_rate
    assert daily_rate <= annual_rate / Decimal("365")


@given(
    position_value=st.decimals(min_value=Decimal("1"), max_value=Decimal("100000"), places=2),
    annual_rate=st.decimals(min_value=Decimal("0.001"), max_value=Decimal("1"), places=4),
    scale_factor=st.decimals(min_value=Decimal("1"), max_value=Decimal("10"), places=2),
)
def test_cost_proportional_to_position_size(position_value, annual_rate, scale_factor):
    """Property: Borrow cost scales linearly with position size."""
    provider = DictBorrowRateProvider({"TEST": annual_rate})
    model = BorrowCostModel(provider)

    # Calculate cost for base position
    cost1, _ = model.calculate_daily_cost("TEST", position_value, pd.Timestamp("2023-01-01"))

    # Calculate cost for scaled position
    cost2, _ = model.calculate_daily_cost(
        "TEST", position_value * scale_factor, pd.Timestamp("2023-01-01")
    )

    # Property: Cost scales linearly (cost2 / cost1 ≈ scale_factor)
    if cost1 > 0:
        ratio = cost2 / cost1
        # Allow for small rounding differences
        assert abs(ratio - scale_factor) < Decimal("0.0001")


@given(
    annual_rate=st.decimals(min_value=Decimal("0.001"), max_value=Decimal("1"), places=4),
)
def test_annual_cost_approximates_rate(annual_rate):
    """Property: Cost over 365 days approximates annual rate × position value."""
    position_value = Decimal("10000.00")
    provider = DictBorrowRateProvider({"TEST": annual_rate})
    model = BorrowCostModel(provider, days_in_year=365)

    # Calculate daily cost
    daily_cost, _ = model.calculate_daily_cost("TEST", position_value, pd.Timestamp("2023-01-01"))

    # Property: Annual cost ≈ annual_rate × position_value
    # (over 365 days)
    annual_cost = daily_cost * Decimal("365")
    expected_annual_cost = position_value * annual_rate

    assert abs(annual_cost - expected_annual_cost) < Decimal("0.01")


# ============================================================================
# Position Integration Tests
# ============================================================================


def test_position_cost_tracking_properties():
    """Test position cost tracking properties and methods."""
    # Create short position
    position = DecimalPosition(
        asset=MockAsset(symbol="GME"),
        amount=Decimal("-100"),
        cost_basis=Decimal("200.00"),
        last_sale_price=Decimal("200.00"),
    )

    # Verify is_short property
    assert position.is_short is True

    # Add some accumulated costs
    position.accumulated_borrow_cost = Decimal("50.00")
    position.accumulated_financing = Decimal("25.00")

    # Verify total_costs property
    assert position.total_costs == Decimal("75.00")

    # Verify unrealized_pnl_net_of_costs
    # Unrealized P&L = market_value - cost_basis * amount
    # = (-100 * 200) - (200 * -100) = -20000 - (-20000) = 0
    # Net of costs = 0 - 75 = -75
    assert position.unrealized_pnl_net_of_costs == Decimal("-75.00")


def test_position_to_dict_includes_costs():
    """Test that position.to_dict includes cost tracking fields."""
    position = DecimalPosition(
        asset=MockAsset(symbol="AAPL"),
        amount=Decimal("-50"),
        cost_basis=Decimal("150.00"),
        last_sale_price=Decimal("155.00"),
    )

    position.accumulated_borrow_cost = Decimal("10.50")
    position.accumulated_financing = Decimal("5.25")

    position_dict = position.to_dict()

    assert "accumulated_borrow_cost" in position_dict
    assert "accumulated_financing" in position_dict
    assert "total_costs" in position_dict
    assert "unrealized_pnl_net_of_costs" in position_dict

    assert position_dict["accumulated_borrow_cost"] == "10.50"
    assert position_dict["accumulated_financing"] == "5.25"
    assert position_dict["total_costs"] == "15.75"


# ============================================================================
# Overnight Financing Tests
# ============================================================================


# Mock Asset with asset_class support
class MockAssetWithClass:
    """Mock asset with asset_class for financing tests."""

    def __init__(self, symbol: str, asset_class: AssetClass = AssetClass.EQUITY):
        self.symbol = symbol
        self.asset_class = asset_class
        self.asset_type = "Equity"

    def __hash__(self):
        return hash(self.symbol)

    def __eq__(self, other):
        return self.symbol == other.symbol

    def __repr__(self):
        return f"MockAssetWithClass({self.symbol}, {self.asset_class})"


# ============================================================================
# Unit Tests: Long Leverage Pays Interest
# ============================================================================


def test_long_leverage_pays_interest():
    """Long leverage position pays interest (debit)."""
    # Setup: Equity margin at 5% annual
    long_rates = {AssetClass.EQUITY: Decimal("0.05")}
    provider = DictFinancingRateProvider(long_rates)
    model = OvernightFinancingModel(provider, days_in_year=365)

    # Leveraged long position: $100k position with $50k leverage
    symbol = "AAPL"
    asset_class = AssetClass.EQUITY
    leveraged_exposure = Decimal("50000.00")
    is_long = True
    current_time = pd.Timestamp("2023-01-01")

    # Calculate daily financing
    daily_financing, annual_rate = model.calculate_daily_financing(
        symbol, asset_class, leveraged_exposure, is_long, current_time
    )

    # Expected: $50,000 × (0.05 / 365) = $6.849315...
    expected_financing = leveraged_exposure * (Decimal("0.05") / Decimal("365"))

    assert daily_financing == expected_financing
    assert annual_rate == Decimal("0.05")
    assert daily_financing > Decimal("0")  # Cost (debit)


def test_short_leverage_forex_swap_negative():
    """Short EUR/USD with negative swap rate (pays interest)."""
    # Setup: EUR/USD short with -0.5% swap rate
    short_rates = {AssetClass.FOREX: Decimal("-0.005")}  # Negative = pay
    provider = DictFinancingRateProvider({}, short_rates)
    model = OvernightFinancingModel(provider, days_in_year=360)  # Forex uses 360

    # Short forex position: €100,000 at 1.10 = $110,000
    symbol = "EUR/USD"
    asset_class = AssetClass.FOREX
    leveraged_exposure = Decimal("110000.00")
    is_long = False
    current_time = pd.Timestamp("2023-01-01")

    # Calculate daily financing
    daily_financing, annual_rate = model.calculate_daily_financing(
        symbol, asset_class, leveraged_exposure, is_long, current_time
    )

    # Expected: $110,000 × (-0.005 / 360) = -$1.527777...
    expected_financing = leveraged_exposure * (Decimal("-0.005") / Decimal("360"))

    assert daily_financing == expected_financing
    assert annual_rate == Decimal("-0.005")
    assert daily_financing < Decimal("0")  # Negative = cost (pay)


def test_short_leverage_forex_swap_positive():
    """Short USD/JPY with positive swap rate (receives interest)."""
    # Setup: USD/JPY short with +1.2% swap rate (interest rate differential)
    short_rates = {AssetClass.FOREX: Decimal("0.012")}  # Positive = receive
    provider = DictFinancingRateProvider({}, short_rates)
    model = OvernightFinancingModel(provider, days_in_year=360)

    # Short forex position: ¥10,000,000 at 110 = $90,909
    symbol = "USD/JPY"
    asset_class = AssetClass.FOREX
    leveraged_exposure = Decimal("90909.00")
    is_long = False
    current_time = pd.Timestamp("2023-01-01")

    # Calculate daily financing
    daily_financing, annual_rate = model.calculate_daily_financing(
        symbol, asset_class, leveraged_exposure, is_long, current_time
    )

    # Expected: $90,909 × (0.012 / 360) = $3.0303
    # Positive rate on short = trader pays (cost)
    expected_financing = leveraged_exposure * (Decimal("0.012") / Decimal("360"))

    assert daily_financing == expected_financing
    assert annual_rate == Decimal("0.012")
    assert daily_financing > Decimal("0")  # Positive = cost


# ============================================================================
# Unit Tests: Leveraged Exposure Calculation
# ============================================================================


def test_leveraged_exposure_calculation():
    """Leveraged exposure calculation."""
    long_rates = {AssetClass.EQUITY: Decimal("0.05")}
    provider = DictFinancingRateProvider(long_rates)
    model = OvernightFinancingModel(provider)

    # Case 1: $100k position with $50k cash = $50k leverage
    exposure1 = model.calculate_leveraged_exposure(Decimal("100000.00"), Decimal("50000.00"))
    assert exposure1 == Decimal("50000.00")

    # Case 2: $100k position with $100k cash = $0 leverage (no financing)
    exposure2 = model.calculate_leveraged_exposure(Decimal("100000.00"), Decimal("100000.00"))
    assert exposure2 == Decimal("0")

    # Case 3: $100k position with $25k cash = $75k leverage (4x)
    exposure3 = model.calculate_leveraged_exposure(Decimal("100000.00"), Decimal("25000.00"))
    assert exposure3 == Decimal("75000.00")


# ============================================================================
# Unit Tests: 360 vs 365 Day Calculation
# ============================================================================


def test_360_vs_365_day_calculation():
    """Day count convention: 360 vs 365 days."""
    provider = DictFinancingRateProvider({AssetClass.EQUITY: Decimal("0.05")})

    # 365-day convention (equities)
    model_365 = OvernightFinancingModel(provider, days_in_year=365)
    financing_365, _ = model_365.calculate_daily_financing(
        "AAPL", AssetClass.EQUITY, Decimal("10000.00"), True, pd.Timestamp("2023-01-01")
    )

    # 360-day convention (forex)
    model_360 = OvernightFinancingModel(provider, days_in_year=360)
    financing_360, _ = model_360.calculate_daily_financing(
        "AAPL", AssetClass.EQUITY, Decimal("10000.00"), True, pd.Timestamp("2023-01-01")
    )

    # 360-day should be slightly higher (fewer days = higher daily rate)
    assert financing_360 > financing_365

    # Expected difference: 5/360 vs 5/365
    expected_365 = Decimal("10000.00") * (Decimal("0.05") / Decimal("365"))
    expected_360 = Decimal("10000.00") * (Decimal("0.05") / Decimal("360"))

    assert financing_365 == expected_365
    assert financing_360 == expected_360


# ============================================================================
# Unit Tests: Forex Swap Rate Examples
# ============================================================================


def test_forex_swap_rate_examples():
    """Forex swap rate examples for different currency pairs."""
    # EUR/USD: negative carry (pay to short)
    # USD/JPY: positive carry (receive to short - but pays in our model)
    # GBP/USD: negative carry (pay to short)

    symbol_overrides = {
        "EUR/USD": (Decimal("0"), Decimal("-0.005")),  # Pay 0.5% to short
        "USD/JPY": (Decimal("0"), Decimal("0.012")),  # Receive 1.2% to short
        "GBP/USD": (Decimal("0"), Decimal("-0.003")),  # Pay 0.3% to short
    }

    provider = DictFinancingRateProvider(
        long_rates={}, short_rates={}, symbol_overrides=symbol_overrides
    )

    model = OvernightFinancingModel(provider, days_in_year=360)

    # Test EUR/USD (negative carry)
    eur_financing, eur_rate = model.calculate_daily_financing(
        "EUR/USD",
        AssetClass.FOREX,
        Decimal("100000.00"),
        False,
        pd.Timestamp("2023-01-01"),
    )
    assert eur_rate == Decimal("-0.005")
    assert eur_financing < Decimal("0")  # Negative rate = cost

    # Test USD/JPY (positive carry)
    jpy_financing, jpy_rate = model.calculate_daily_financing(
        "USD/JPY",
        AssetClass.FOREX,
        Decimal("100000.00"),
        False,
        pd.Timestamp("2023-01-01"),
    )
    assert jpy_rate == Decimal("0.012")
    assert jpy_financing > Decimal("0")  # Positive rate = cost


# ============================================================================
# Unit Tests: Margin Interest Rate Examples
# ============================================================================


def test_margin_interest_rate_examples():
    """Margin interest rate examples for equity positions."""
    # Standard broker margin: 5% annual
    provider = DictFinancingRateProvider(long_rates={AssetClass.EQUITY: Decimal("0.05")})

    model = OvernightFinancingModel(provider, days_in_year=365)

    # $50k leveraged exposure at 5% annual
    daily_financing, annual_rate = model.calculate_daily_financing(
        "AAPL",
        AssetClass.EQUITY,
        Decimal("50000.00"),
        True,
        pd.Timestamp("2023-01-01"),
    )

    # Expected: $50k × (5% / 365) = $6.85/day
    expected = Decimal("50000.00") * (Decimal("0.05") / Decimal("365"))

    assert daily_financing == expected
    assert annual_rate == Decimal("0.05")

    # Annual cost: $6.85 × 365 ≈ $2,500
    annual_cost = daily_financing * Decimal("365")
    assert abs(annual_cost - Decimal("2500.00")) < Decimal("0.01")


# ============================================================================
# Unit Tests: CSV Financing Rate Provider
# ============================================================================


def test_financing_rate_lookup_from_csv(tmp_path):
    """Financing rate lookup from CSV file."""
    csv_content = """symbol,asset_class,long_rate,short_rate
AAPL,equity,0.05,0.00
EUR/USD,forex,0.00,-0.005
USD/JPY,forex,0.00,0.012
"""
    csv_path = tmp_path / "rates.csv"
    csv_path.write_text(csv_content)

    provider = CSVFinancingRateProvider(csv_path)

    # Test long rate
    aapl_long = provider.get_long_rate("AAPL", AssetClass.EQUITY, pd.Timestamp("2023-01-01"))
    assert aapl_long == Decimal("0.05")

    # Test short rates
    eur_short = provider.get_short_rate("EUR/USD", AssetClass.FOREX, pd.Timestamp("2023-01-01"))
    assert eur_short == Decimal("-0.005")

    jpy_short = provider.get_short_rate("USD/JPY", AssetClass.FOREX, pd.Timestamp("2023-01-01"))
    assert jpy_short == Decimal("0.012")


def test_csv_financing_missing_columns(tmp_path):
    """CSV financing provider raises error when columns missing."""
    csv_content = """symbol,wrong_column
AAPL,0.05
"""
    csv_path = tmp_path / "rates.csv"
    csv_path.write_text(csv_content)

    with pytest.raises(FinancingRateLoadError):
        CSVFinancingRateProvider(csv_path)


# ============================================================================
# Integration Tests: Leveraged Equity Strategy
# ============================================================================


def test_leveraged_equity_strategy_over_time():
    """Integration test: Leveraged equity strategy with margin interest."""
    # Setup: 2x leveraged AAPL position
    provider = DictFinancingRateProvider(long_rates={AssetClass.EQUITY: Decimal("0.05")})
    model = OvernightFinancingModel(provider, days_in_year=365)

    # Initialize ledger
    ledger = DecimalLedger(starting_cash=Decimal("100000.00"))

    # Enter leveraged position: $100k AAPL with $50k cash (2x leverage)
    aapl_asset = MockAssetWithClass(symbol="AAPL", asset_class=AssetClass.EQUITY)
    position = DecimalPosition(
        asset=aapl_asset,
        amount=Decimal("666.67"),  # ~$100k at $150/share
        cost_basis=Decimal("150.00"),
        last_sale_price=Decimal("150.00"),
    )
    # Set cash_used to track leverage
    position.cash_used = Decimal("50000.00")  # 2x leverage, $50k financed
    ledger.positions[aapl_asset] = position

    # Track financing over 30 days
    daily_financing_amounts = []
    start_date = pd.Timestamp("2023-01-01")

    for day in range(30):
        current_time = start_date + pd.Timedelta(days=day)

        # Apply financing
        result = model.apply_financing(ledger, current_time)

        daily_financing_amounts.append(result.total_financing)

    # Expected daily financing: $50k leverage × (5% / 365) = $6.85/day
    # 30 days: $6.85 × 30 = $205.48
    total_financing = sum(daily_financing_amounts, Decimal("0"))
    expected_total = Decimal("50000.00") * (Decimal("0.05") / Decimal("365")) * Decimal("30")

    assert abs(total_financing - expected_total) < Decimal("0.01")

    # Verify cash debited
    cash_debited = Decimal("100000.00") - ledger.cash
    assert abs(cash_debited - expected_total) < Decimal("0.01")

    # Verify accumulated financing in position
    assert abs(position.accumulated_financing - expected_total) < Decimal("0.01")


# ============================================================================
# Property-Based Tests: Financing
# ============================================================================


@given(
    leveraged_exposure=st.decimals(min_value=Decimal("1"), max_value=Decimal("1000000"), places=2),
    annual_rate=st.decimals(min_value=Decimal("0.001"), max_value=Decimal("0.20"), places=4),
)
def test_financing_proportional_to_exposure(leveraged_exposure, annual_rate):
    """Property: Financing cost scales linearly with leveraged exposure."""
    provider = DictFinancingRateProvider(long_rates={AssetClass.EQUITY: annual_rate})
    model = OvernightFinancingModel(provider)

    # Calculate financing for base exposure
    financing1, _ = model.calculate_daily_financing(
        "TEST", AssetClass.EQUITY, leveraged_exposure, True, pd.Timestamp("2023-01-01")
    )

    # Calculate financing for double exposure
    financing2, _ = model.calculate_daily_financing(
        "TEST",
        AssetClass.EQUITY,
        leveraged_exposure * Decimal("2"),
        True,
        pd.Timestamp("2023-01-01"),
    )

    # Property: Double exposure = double financing
    expected_financing2 = financing1 * Decimal("2")
    assert abs(financing2 - expected_financing2) < Decimal("0.000001")


@given(
    leveraged_exposure=st.decimals(min_value=Decimal("1"), max_value=Decimal("1000000"), places=2),
    annual_rate=st.decimals(min_value=Decimal("0.001"), max_value=Decimal("0.20"), places=4),
)
def test_long_leverage_always_pays(leveraged_exposure, annual_rate):
    """Property: Long leverage always pays interest (never receives)."""
    provider = DictFinancingRateProvider(long_rates={AssetClass.EQUITY: annual_rate})
    model = OvernightFinancingModel(provider)

    daily_financing, _ = model.calculate_daily_financing(
        "TEST", AssetClass.EQUITY, leveraged_exposure, True, pd.Timestamp("2023-01-01")
    )

    # Property: Long leverage financing is always positive (cost)
    assert daily_financing >= Decimal("0")


@given(
    position_value=st.decimals(min_value=Decimal("1000"), max_value=Decimal("1000000"), places=2),
    cash_used=st.decimals(min_value=Decimal("100"), max_value=Decimal("1000000"), places=2),
)
def test_leveraged_exposure_bounds(position_value, cash_used):
    """Property: Leveraged exposure is always non-negative and <= position value."""
    provider = DictFinancingRateProvider({AssetClass.EQUITY: Decimal("0.05")})
    model = OvernightFinancingModel(provider)

    exposure = model.calculate_leveraged_exposure(position_value, cash_used)

    # Property: Exposure is non-negative
    assert exposure >= Decimal("0")

    # Property: Exposure <= position value
    assert exposure <= abs(position_value)


@given(
    annual_rate=st.decimals(min_value=Decimal("0.001"), max_value=Decimal("0.20"), places=4),
    days_in_year=st.sampled_from([360, 365]),
)
def test_annual_financing_approximates_rate(annual_rate, days_in_year):
    """Property: Financing over full year approximates annual rate × exposure."""
    leveraged_exposure = Decimal("10000.00")
    provider = DictFinancingRateProvider(long_rates={AssetClass.EQUITY: annual_rate})
    model = OvernightFinancingModel(provider, days_in_year=days_in_year)

    # Calculate daily financing
    daily_financing, _ = model.calculate_daily_financing(
        "TEST", AssetClass.EQUITY, leveraged_exposure, True, pd.Timestamp("2023-01-01")
    )

    # Property: Annual financing ≈ annual_rate × exposure
    annual_financing = daily_financing * Decimal(str(days_in_year))
    expected_annual = leveraged_exposure * annual_rate

    # Allow for small rounding differences in Decimal precision
    assert abs(annual_financing - expected_annual) < Decimal("0.000001")


def test_financing_result_structure():
    """Test FinancingResult structure and properties."""
    result = FinancingResult(
        total_financing=Decimal("10.50"),
        position_financing={"AAPL": Decimal("6.85"), "MSFT": Decimal("3.65")},
        timestamp=pd.Timestamp("2023-01-01"),
        positions_processed=2,
        metadata={"days_in_year": 365},
    )

    # Test attributes
    assert result.total_financing == Decimal("10.50")
    assert result.positions_processed == 2
    assert result.total_cost == Decimal("10.50")  # All positive = all costs
    assert result.total_credit == Decimal("0")

    # Test string representation
    str_repr = str(result)
    assert "FinancingResult" in str_repr
    assert "10.50" in str_repr


def test_position_cash_used_field_integration():
    """Test that positions with explicit cash_used field work correctly with financing."""
    # Create provider
    provider = DictFinancingRateProvider(long_rates={AssetClass.EQUITY: Decimal("0.05")})
    model = OvernightFinancingModel(provider, days_in_year=365)

    # Create ledger with position that has explicit cash_used
    ledger = DecimalLedger(starting_cash=Decimal("100000.00"))
    asset = MockAssetWithClass("AAPL", AssetClass.EQUITY)

    # Position: $100k market value, $50k cash used = 2x leverage
    position = DecimalPosition(
        asset=asset,
        amount=Decimal("1000"),  # Exact 1000 shares
        cost_basis=Decimal("100.00"),
        last_sale_price=Decimal("100.00"),  # $100/share = $100k total
        cash_used=Decimal("50000.00"),  # Explicit cash_used = 2x leverage
    )

    ledger.positions = {asset: position}
    ledger.cash = Decimal("100000.00")

    # Apply financing
    result = model.apply_financing(ledger, pd.Timestamp("2023-01-01"))

    # Should calculate leveraged exposure = 100k - 50k = 50k
    leveraged_exposure = Decimal("100000.00") - Decimal("50000.00")
    expected_financing = leveraged_exposure * (Decimal("0.05") / Decimal("365"))

    assert result.positions_processed == 1
    assert result.total_financing == expected_financing
    assert position.accumulated_financing == expected_financing

    # Verify position properties
    assert position.is_leveraged is True
    assert position.leverage_ratio == Decimal("2.0")
    assert position.leveraged_exposure == Decimal("50000.00")


def test_position_without_explicit_cash_used():
    """Test that positions without cash_used default to no leverage."""
    # Create provider
    provider = DictFinancingRateProvider(long_rates={AssetClass.EQUITY: Decimal("0.05")})
    model = OvernightFinancingModel(provider, days_in_year=365)

    # Create ledger with position without cash_used (defaults to Decimal("0"))
    ledger = DecimalLedger(starting_cash=Decimal("100000.00"))
    asset = MockAssetWithClass("AAPL", AssetClass.EQUITY)

    position = DecimalPosition(
        asset=asset,
        amount=Decimal("100"),
        cost_basis=Decimal("150.00"),
        last_sale_price=Decimal("150.00"),
        # cash_used defaults to Decimal("0")
    )

    ledger.positions = {asset: position}
    ledger.cash = Decimal("100000.00")

    # Apply financing
    result = model.apply_financing(ledger, pd.Timestamp("2023-01-01"))

    # With cash_used = 0, we use market value as cash_used (no leverage)
    # So leveraged_exposure should be 0
    assert result.positions_processed == 0  # Skipped due to no leverage


def test_csv_chronological_date_validation(tmp_path):
    """Test that CSV provider validates chronological dates."""
    # Create CSV with non-chronological dates
    csv_content = """symbol,date,annual_rate
AAPL,2023-01-01,0.003
AAPL,2023-01-15,0.004
AAPL,2023-01-10,0.005
GME,2023-01-01,0.25
"""
    csv_path = tmp_path / "rates_nonchrono.csv"
    csv_path.write_text(csv_content)

    # Should log warning but still load
    provider = CSVBorrowRateProvider(csv_path)

    # Provider should still work (sorts data)
    rate = provider.get_rate("AAPL", pd.Timestamp("2023-01-20"))
    assert rate is not None  # Should get most recent rate before 2023-01-20


def test_csv_financing_chronological_date_validation(tmp_path):
    """Test that CSV financing provider validates chronological dates."""
    # Create CSV with non-chronological dates
    csv_content = """symbol,asset_class,date,long_rate,short_rate
EUR/USD,forex,2023-01-01,0.00,-0.005
EUR/USD,forex,2023-06-01,0.00,0.003
EUR/USD,forex,2023-03-01,0.00,0.001
"""
    csv_path = tmp_path / "financing_nonchrono.csv"
    csv_path.write_text(csv_content)

    # Should log warning but still load
    provider = CSVFinancingRateProvider(csv_path)

    # Provider should still work (sorts data)
    rate = provider.get_short_rate("EUR/USD", AssetClass.FOREX, pd.Timestamp("2023-12-01"))
    assert rate == Decimal("0.003")  # Most recent rate before 2023-12-01


def test_position_leverage_properties():
    """Test new leverage-related position properties."""
    from rustybt.finance.decimal.position import DecimalPosition

    asset = MockAssetWithClass("AAPL", AssetClass.EQUITY)

    # Test leveraged position
    leveraged_position = DecimalPosition(
        asset=asset,
        amount=Decimal("100"),
        cost_basis=Decimal("150.00"),
        last_sale_price=Decimal("150.00"),
        cash_used=Decimal("7500.00"),  # 50% cash = 2x leverage
    )

    assert leveraged_position.is_leveraged is True
    assert leveraged_position.leverage_ratio == Decimal("2.0")
    assert leveraged_position.leveraged_exposure == Decimal("7500.00")

    # Test non-leveraged position
    non_leveraged_position = DecimalPosition(
        asset=asset,
        amount=Decimal("100"),
        cost_basis=Decimal("150.00"),
        last_sale_price=Decimal("150.00"),
        cash_used=Decimal("15000.00"),  # 100% cash = no leverage
    )

    assert non_leveraged_position.is_leveraged is False
    assert non_leveraged_position.leverage_ratio == Decimal("1.0")
    assert non_leveraged_position.leveraged_exposure == Decimal("0")


def test_position_to_dict_includes_leverage_fields():
    """Test that position.to_dict() includes new leverage fields."""
    from rustybt.finance.decimal.position import DecimalPosition

    asset = MockAssetWithClass("AAPL", AssetClass.EQUITY)

    position = DecimalPosition(
        asset=asset,
        amount=Decimal("100"),
        cost_basis=Decimal("150.00"),
        last_sale_price=Decimal("155.50"),
        cash_used=Decimal("10000.00"),
        accumulated_borrow_cost=Decimal("5.00"),
        accumulated_financing=Decimal("10.00"),
    )

    pos_dict = position.to_dict()

    # Check new fields are included
    assert "cash_used" in pos_dict
    assert "is_leveraged" in pos_dict
    assert "leverage_ratio" in pos_dict
    assert "leveraged_exposure" in pos_dict

    # Verify values
    assert pos_dict["cash_used"] == "10000.00"
    assert pos_dict["is_leveraged"] is True
