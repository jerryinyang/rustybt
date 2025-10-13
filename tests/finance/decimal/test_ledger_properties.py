"""Property-based tests for DecimalLedger using Hypothesis."""

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from rustybt.finance.decimal import DecimalLedger, DecimalPosition


# Mock Asset class for testing
class MockAsset:
    """Mock asset for testing."""

    def __init__(self, symbol: str, asset_type: str = "Equity"):
        self.symbol = symbol
        self.asset_type = asset_type

    def __repr__(self):
        return f"{self.asset_type}({self.symbol})"

    def __hash__(self):
        return hash(self.symbol)

    def __eq__(self, other):
        return self.symbol == other.symbol


# Hypothesis strategies for Decimal generation
decimal_strategy = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("1000000"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

positive_decimal_strategy = st.decimals(
    min_value=Decimal("1"),
    max_value=Decimal("1000000"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)


class TestLedgerProperties:
    """Property-based tests for DecimalLedger invariants."""

    @given(starting_cash=positive_decimal_strategy)
    def test_portfolio_value_equals_cash_when_no_positions(self, starting_cash):
        """Portfolio value must equal cash when no positions exist."""
        ledger = DecimalLedger(starting_cash=starting_cash)

        assert ledger.portfolio_value == starting_cash
        assert ledger.portfolio_value == ledger.cash
        assert ledger.positions_value == Decimal("0")

    @given(
        starting_cash=positive_decimal_strategy,
        position_count=st.integers(min_value=1, max_value=5),
    )
    def test_portfolio_value_invariant(self, starting_cash, position_count):
        """Portfolio value must equal sum of positions + cash."""
        ledger = DecimalLedger(starting_cash=starting_cash)

        # Add multiple positions
        for i in range(position_count):
            asset = MockAsset(f"STOCK{i}")
            position = DecimalPosition(
                asset=asset,
                amount=Decimal("100"),
                cost_basis=Decimal("50"),
                last_sale_price=Decimal("55"),
            )
            ledger.positions[asset] = position

        # Verify invariant: portfolio_value == positions_value + cash
        assert ledger.portfolio_value == ledger.positions_value + ledger.cash

    @given(
        start_value=positive_decimal_strategy,
        end_value=positive_decimal_strategy,
    )
    def test_returns_calculation_consistency(self, start_value, end_value):
        """Returns calculation must satisfy: (1 + return) × start_value ≈ end_value."""
        ledger = DecimalLedger(starting_cash=Decimal("100000"))

        returns = ledger.calculate_returns(start_value, end_value)
        calculated_end_value = (Decimal("1") + returns) * start_value

        # Allow for small rounding differences (quantize to 2 decimal places)
        assert calculated_end_value.quantize(Decimal("0.01")) == end_value.quantize(Decimal("0.01"))

    @given(
        amount=st.decimals(min_value=Decimal("1"), max_value=Decimal("1000"), places=2),
        cost_basis=st.decimals(min_value=Decimal("10"), max_value=Decimal("1000"), places=2),
        last_sale_price=st.decimals(min_value=Decimal("10"), max_value=Decimal("1000"), places=2),
    )
    def test_position_market_value_definition(self, amount, cost_basis, last_sale_price):
        """Market value must equal amount × last_sale_price."""
        asset = MockAsset("TEST")
        position = DecimalPosition(
            asset=asset,
            amount=amount,
            cost_basis=cost_basis,
            last_sale_price=last_sale_price,
        )

        expected_market_value = amount * last_sale_price
        assert position.market_value == expected_market_value

    @given(
        amount=st.decimals(min_value=Decimal("1"), max_value=Decimal("1000"), places=2),
        cost_basis=st.decimals(min_value=Decimal("10"), max_value=Decimal("1000"), places=2),
        last_sale_price=st.decimals(min_value=Decimal("10"), max_value=Decimal("1000"), places=2),
    )
    def test_position_unrealized_pnl_definition(self, amount, cost_basis, last_sale_price):
        """Unrealized P&L must equal market_value - (cost_basis × amount)."""
        asset = MockAsset("TEST")
        position = DecimalPosition(
            asset=asset,
            amount=amount,
            cost_basis=cost_basis,
            last_sale_price=last_sale_price,
        )

        expected_pnl = (amount * last_sale_price) - (cost_basis * amount)
        assert position.unrealized_pnl == expected_pnl

    @given(
        a=decimal_strategy,
        b=decimal_strategy,
        c=decimal_strategy,
    )
    def test_decimal_associativity(self, a, b, c):
        """Decimal addition must be associative: (a + b) + c == a + (b + c)."""
        left = (a + b) + c
        right = a + (b + c)
        assert left == right

    @given(
        a=decimal_strategy,
        b=decimal_strategy,
    )
    def test_decimal_commutativity(self, a, b):
        """Decimal addition must be commutative: a + b == b + a."""
        assert a + b == b + a

    @given(
        starting_cash=positive_decimal_strategy,
        amount=st.decimals(min_value=Decimal("1"), max_value=Decimal("100"), places=2),
        price=st.decimals(min_value=Decimal("10"), max_value=Decimal("100"), places=2),
    )
    def test_leverage_bounds(self, starting_cash, amount, price):
        """Leverage must be non-negative."""
        ledger = DecimalLedger(starting_cash=starting_cash)

        asset = MockAsset("TEST")
        position = DecimalPosition(
            asset=asset,
            amount=amount,
            cost_basis=price,
            last_sale_price=price,
        )
        ledger.positions[asset] = position

        leverage = ledger.calculate_leverage()
        assert leverage >= Decimal("0")

    @given(
        dollar_amount=positive_decimal_strategy,
        price=positive_decimal_strategy,
    )
    def test_shares_from_dollars_equity_whole_shares(self, dollar_amount, price):
        """Equity shares calculation must return whole shares (no fractions)."""
        ledger = DecimalLedger(starting_cash=Decimal("1000000"))
        asset = MockAsset("STOCK", asset_type="Equity")

        shares = ledger.calculate_shares_from_dollars(asset, dollar_amount, price)

        # Verify result is whole number (no fractional part)
        assert shares == shares.quantize(Decimal("1"))

    @given(
        starting_cash=positive_decimal_strategy,
        price=st.decimals(min_value=Decimal("10"), max_value=Decimal("1000"), places=2),
    )
    def test_daily_return_consistency(self, starting_cash, price):
        """Daily return calculation must be consistent with total return."""
        ledger = DecimalLedger(starting_cash=starting_cash)

        # Calculate daily return
        daily_return = ledger.calculate_daily_return(starting_cash, starting_cash + price)

        # Verify consistency: (1 + daily_return) × start ≈ end
        calculated_end = (Decimal("1") + daily_return) * starting_cash
        expected_end = starting_cash + price

        # Allow for small rounding differences
        assert calculated_end.quantize(Decimal("0.01")) == expected_end.quantize(Decimal("0.01"))

    @given(
        amount1=st.decimals(min_value=Decimal("1"), max_value=Decimal("100"), places=2),
        price1=st.decimals(min_value=Decimal("10"), max_value=Decimal("100"), places=2),
        amount2=st.decimals(min_value=Decimal("1"), max_value=Decimal("100"), places=2),
        price2=st.decimals(min_value=Decimal("10"), max_value=Decimal("100"), places=2),
    )
    def test_volume_weighted_average_cost(self, amount1, price1, amount2, price2):
        """Cost basis update must calculate correct volume-weighted average."""
        asset = MockAsset("TEST")
        position = DecimalPosition(
            asset=asset,
            amount=amount1,
            cost_basis=price1,
            last_sale_price=price1,
        )

        # Add second transaction (same direction)
        import pandas as pd

        position.update(
            transaction_amount=amount2,
            transaction_price=price2,
            transaction_dt=pd.Timestamp("2025-01-15"),
        )

        # Calculate expected volume-weighted cost
        total_cost = (amount1 * price1) + (amount2 * price2)
        total_amount = amount1 + amount2
        expected_cost_basis = total_cost / total_amount

        assert position.cost_basis == expected_cost_basis

    @given(
        starting_cash=positive_decimal_strategy,
        position_value=st.decimals(min_value=Decimal("0"), max_value=Decimal("10000"), places=2),
    )
    def test_cumulative_return_from_inception(self, starting_cash, position_value):
        """Cumulative return must reflect total gain/loss from inception."""
        ledger = DecimalLedger(starting_cash=starting_cash)

        current_value = starting_cash + position_value
        cumulative_return = ledger.calculate_cumulative_return(current_value)

        # Verify: (1 + cumulative_return) × starting_cash ≈ current_value
        calculated_value = (Decimal("1") + cumulative_return) * starting_cash
        # Allow for small rounding differences
        assert calculated_value.quantize(Decimal("0.01")) == current_value.quantize(Decimal("0.01"))
