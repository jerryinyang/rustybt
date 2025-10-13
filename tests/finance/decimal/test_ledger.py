"""Unit tests for DecimalLedger."""

from decimal import Decimal

import pandas as pd
import pytest

from rustybt.finance.decimal import (
    DecimalLedger,
    DecimalPosition,
    InsufficientFundsError,
    InvalidTransactionError,
)


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


class TestDecimalLedger:
    """Test DecimalLedger class."""

    def test_ledger_initialization(self):
        """Test ledger initializes with Decimal cash."""
        starting_cash = Decimal("100000.00")
        ledger = DecimalLedger(starting_cash=starting_cash)

        assert ledger.starting_cash == starting_cash
        assert ledger.cash == starting_cash
        assert ledger.portfolio_value == starting_cash
        assert len(ledger.positions) == 0

    def test_ledger_rejects_non_decimal_starting_cash(self):
        """Test ledger rejects non-Decimal starting cash."""
        with pytest.raises(InvalidTransactionError, match="starting_cash must be Decimal"):
            DecimalLedger(starting_cash=100000.0)  # float instead of Decimal

    def test_portfolio_value_with_no_positions(self):
        """Test portfolio value equals cash when no positions."""
        ledger = DecimalLedger(starting_cash=Decimal("100000"))

        assert ledger.portfolio_value == Decimal("100000")
        assert ledger.positions_value == Decimal("0")
        assert ledger.portfolio_value == ledger.cash

    def test_portfolio_value_with_single_position(self):
        """Test portfolio value calculation with one position."""
        ledger = DecimalLedger(starting_cash=Decimal("100000"))

        asset = MockAsset("AAPL")
        position = DecimalPosition(
            asset=asset,
            amount=Decimal("100"),
            cost_basis=Decimal("150"),
            last_sale_price=Decimal("155"),
        )
        ledger.positions[asset] = position

        expected_positions_value = Decimal("100") * Decimal("155")
        expected_portfolio_value = Decimal("100000") + expected_positions_value

        assert ledger.positions_value == expected_positions_value
        assert ledger.portfolio_value == expected_portfolio_value
        assert ledger.portfolio_value == Decimal("115500")

    def test_portfolio_value_with_multiple_positions(self):
        """Test portfolio value calculation with multiple positions."""
        ledger = DecimalLedger(starting_cash=Decimal("100000"))

        # Add first position
        aapl = MockAsset("AAPL")
        position1 = DecimalPosition(
            asset=aapl,
            amount=Decimal("100"),
            cost_basis=Decimal("150"),
            last_sale_price=Decimal("155"),
        )
        ledger.positions[aapl] = position1

        # Add second position
        googl = MockAsset("GOOGL")
        position2 = DecimalPosition(
            asset=googl,
            amount=Decimal("50"),
            cost_basis=Decimal("2800"),
            last_sale_price=Decimal("2850"),
        )
        ledger.positions[googl] = position2

        expected_positions_value = Decimal("100") * Decimal("155") + Decimal("50") * Decimal("2850")
        expected_portfolio_value = Decimal("100000") + expected_positions_value

        assert ledger.positions_value == expected_positions_value
        assert ledger.portfolio_value == expected_portfolio_value

    def test_portfolio_value_invariant(self):
        """Test portfolio value invariant: portfolio_value == positions_value + cash."""
        ledger = DecimalLedger(starting_cash=Decimal("100000"))

        # Add position
        asset = MockAsset("AAPL")
        position = DecimalPosition(
            asset=asset,
            amount=Decimal("100"),
            cost_basis=Decimal("150"),
            last_sale_price=Decimal("155"),
        )
        ledger.positions[asset] = position

        # Manually adjust cash (simulating a transaction)
        ledger.cash = Decimal("85000")

        # Verify invariant
        assert ledger.portfolio_value == ledger.positions_value + ledger.cash

    def test_process_transaction_buy(self):
        """Test processing buy transaction."""
        ledger = DecimalLedger(starting_cash=Decimal("100000"))

        asset = MockAsset("AAPL")
        dt = pd.Timestamp("2025-01-15")

        # Buy 100 shares at $150 with $5 commission
        ledger.process_transaction(
            asset=asset,
            amount=Decimal("100"),
            price=Decimal("150.00"),
            commission=Decimal("5.00"),
            dt=dt,
        )

        # Check cash decrease
        expected_cash = Decimal("100000") - (Decimal("100") * Decimal("150.00")) - Decimal("5.00")
        assert ledger.cash == expected_cash
        assert ledger.cash == Decimal("84995.00")

        # Check position created
        assert asset in ledger.positions
        position = ledger.positions[asset]
        assert position.amount == Decimal("100")
        # Cost basis should include commission: (15000 + 5) / 100 = 150.05
        expected_cost_basis = (Decimal("100") * Decimal("150.00") + Decimal("5.00")) / Decimal(
            "100"
        )
        assert position.cost_basis == expected_cost_basis

    def test_process_transaction_sell(self):
        """Test processing sell transaction."""
        ledger = DecimalLedger(starting_cash=Decimal("100000"))

        asset = MockAsset("AAPL")
        dt1 = pd.Timestamp("2025-01-15")
        dt2 = pd.Timestamp("2025-01-16")

        # Buy 100 shares first
        ledger.process_transaction(
            asset=asset,
            amount=Decimal("100"),
            price=Decimal("150.00"),
            commission=Decimal("5.00"),
            dt=dt1,
        )

        initial_cash = ledger.cash

        # Sell 50 shares at $155 with $3 commission
        ledger.process_transaction(
            asset=asset,
            amount=Decimal("-50"),
            price=Decimal("155.00"),
            commission=Decimal("3.00"),
            dt=dt2,
        )

        # Check cash increase
        expected_cash = initial_cash + (Decimal("50") * Decimal("155.00")) - Decimal("3.00")
        assert ledger.cash == expected_cash

        # Check position updated
        position = ledger.positions[asset]
        assert position.amount == Decimal("50")

    def test_process_transaction_insufficient_funds(self):
        """Test transaction with insufficient funds raises error."""
        ledger = DecimalLedger(starting_cash=Decimal("1000"))

        asset = MockAsset("AAPL")
        dt = pd.Timestamp("2025-01-15")

        # Try to buy 100 shares at $150 (need $15000)
        with pytest.raises(InsufficientFundsError):
            ledger.process_transaction(
                asset=asset,
                amount=Decimal("100"),
                price=Decimal("150.00"),
                commission=Decimal("5.00"),
                dt=dt,
            )

    def test_process_transaction_close_position(self):
        """Test closing position completely removes it from ledger."""
        ledger = DecimalLedger(starting_cash=Decimal("100000"))

        asset = MockAsset("AAPL")
        dt1 = pd.Timestamp("2025-01-15")
        dt2 = pd.Timestamp("2025-01-16")

        # Buy 100 shares
        ledger.process_transaction(
            asset=asset,
            amount=Decimal("100"),
            price=Decimal("150.00"),
            commission=Decimal("5.00"),
            dt=dt1,
        )

        # Sell all 100 shares
        ledger.process_transaction(
            asset=asset,
            amount=Decimal("-100"),
            price=Decimal("155.00"),
            commission=Decimal("5.00"),
            dt=dt2,
        )

        # Position should be removed
        assert asset not in ledger.positions

    def test_process_transaction_rejects_non_decimal_amount(self):
        """Test transaction rejects non-Decimal amount."""
        ledger = DecimalLedger(starting_cash=Decimal("100000"))
        asset = MockAsset("AAPL")
        dt = pd.Timestamp("2025-01-15")

        with pytest.raises(InvalidTransactionError, match="amount must be Decimal"):
            ledger.process_transaction(
                asset=asset,
                amount=100,  # int instead of Decimal
                price=Decimal("150.00"),
                commission=Decimal("5.00"),
                dt=dt,
            )

    def test_process_transaction_rejects_non_decimal_price(self):
        """Test transaction rejects non-Decimal price."""
        ledger = DecimalLedger(starting_cash=Decimal("100000"))
        asset = MockAsset("AAPL")
        dt = pd.Timestamp("2025-01-15")

        with pytest.raises(InvalidTransactionError, match="price must be Decimal"):
            ledger.process_transaction(
                asset=asset,
                amount=Decimal("100"),
                price=150.00,  # float instead of Decimal
                commission=Decimal("5.00"),
                dt=dt,
            )

    def test_calculate_returns(self):
        """Test returns calculation."""
        ledger = DecimalLedger(starting_cash=Decimal("100000"))

        start_value = Decimal("100000")
        end_value = Decimal("105000")

        returns = ledger.calculate_returns(start_value, end_value)

        expected_return = (end_value / start_value) - Decimal("1")
        assert returns == expected_return
        assert returns == Decimal("0.05")  # 5% return

    def test_calculate_returns_negative(self):
        """Test returns calculation with loss."""
        ledger = DecimalLedger(starting_cash=Decimal("100000"))

        start_value = Decimal("100000")
        end_value = Decimal("95000")

        returns = ledger.calculate_returns(start_value, end_value)

        expected_return = (end_value / start_value) - Decimal("1")
        assert returns == expected_return
        assert returns == Decimal("-0.05")  # -5% return

    def test_calculate_returns_zero_start_value_raises_error(self):
        """Test returns calculation with zero start value raises error."""
        ledger = DecimalLedger(starting_cash=Decimal("100000"))

        with pytest.raises(ValueError, match="Start value must be positive"):
            ledger.calculate_returns(Decimal("0"), Decimal("100000"))

    def test_calculate_daily_return(self):
        """Test daily return calculation."""
        ledger = DecimalLedger(starting_cash=Decimal("100000"))

        start_value = Decimal("100000")
        end_value = Decimal("102000")

        daily_return = ledger.calculate_daily_return(start_value, end_value)

        expected_return = (end_value - start_value) / start_value
        assert daily_return == expected_return
        assert daily_return == Decimal("0.02")  # 2% daily return

    def test_calculate_cumulative_return(self):
        """Test cumulative return calculation."""
        ledger = DecimalLedger(starting_cash=Decimal("100000"))

        current_value = Decimal("125000")

        cumulative_return = ledger.calculate_cumulative_return(current_value)

        expected_return = (current_value / ledger.starting_cash) - Decimal("1")
        assert cumulative_return == expected_return
        assert cumulative_return == Decimal("0.25")  # 25% cumulative return

    def test_calculate_leverage_no_positions(self):
        """Test leverage calculation with no positions."""
        ledger = DecimalLedger(starting_cash=Decimal("100000"))

        leverage = ledger.calculate_leverage()

        # No positions = zero gross exposure = zero leverage
        assert leverage == Decimal("0")

    def test_calculate_leverage_fully_invested(self):
        """Test leverage calculation when fully invested."""
        ledger = DecimalLedger(starting_cash=Decimal("100000"))

        asset = MockAsset("AAPL")
        position = DecimalPosition(
            asset=asset,
            amount=Decimal("100"),
            cost_basis=Decimal("150"),
            last_sale_price=Decimal("150"),
        )
        ledger.positions[asset] = position

        # Gross exposure = 15000, Net liquidation = 100000 + 15000 = 115000
        # Leverage = 15000 / 115000 = 0.1304...
        gross_exposure = Decimal("100") * Decimal("150")
        net_liquidation = ledger.portfolio_value
        expected_leverage = gross_exposure / net_liquidation

        leverage = ledger.calculate_leverage()
        assert leverage == expected_leverage

    def test_calculate_leverage_with_short(self):
        """Test leverage calculation with short position."""
        ledger = DecimalLedger(starting_cash=Decimal("100000"))

        asset = MockAsset("AAPL")
        position = DecimalPosition(
            asset=asset,
            amount=Decimal("-100"),  # Short position
            cost_basis=Decimal("150"),
            last_sale_price=Decimal("150"),
        )
        ledger.positions[asset] = position

        # Gross exposure = abs(-15000) = 15000
        # Net liquidation = 100000 + (-15000) = 85000
        # Leverage = 15000 / 85000 = 0.1764...
        gross_exposure = abs(Decimal("-100") * Decimal("150"))
        net_liquidation = ledger.portfolio_value
        expected_leverage = gross_exposure / net_liquidation

        leverage = ledger.calculate_leverage()
        assert leverage == expected_leverage

    def test_calculate_leverage_zero_portfolio_raises_error(self):
        """Test leverage calculation with zero portfolio value raises error."""
        ledger = DecimalLedger(starting_cash=Decimal("0"))

        with pytest.raises(ValueError, match="Cannot calculate leverage with zero portfolio value"):
            ledger.calculate_leverage()

    def test_calculate_shares_from_dollars_equity(self):
        """Test calculating shares from dollars for equity (whole shares)."""
        ledger = DecimalLedger(starting_cash=Decimal("100000"))

        asset = MockAsset("AAPL", asset_type="Equity")
        shares = ledger.calculate_shares_from_dollars(asset, Decimal("1000"), Decimal("155.50"))

        # $1000 / $155.50 = 6.43 shares → round down to 6 whole shares
        expected_shares = Decimal("6")
        assert shares == expected_shares

    def test_calculate_shares_from_dollars_crypto(self):
        """Test calculating shares from dollars for crypto (fractional shares)."""
        ledger = DecimalLedger(starting_cash=Decimal("100000"))

        asset = MockAsset("BTC", asset_type="Cryptocurrency")
        shares = ledger.calculate_shares_from_dollars(asset, Decimal("100"), Decimal("50000"))

        # $100 / $50000 = 0.002 BTC
        expected_shares = Decimal("0.00200000")
        assert shares == expected_shares

    def test_get_position_exists(self):
        """Test getting position that exists."""
        ledger = DecimalLedger(starting_cash=Decimal("100000"))

        asset = MockAsset("AAPL")
        position = DecimalPosition(
            asset=asset,
            amount=Decimal("100"),
            cost_basis=Decimal("150"),
            last_sale_price=Decimal("155"),
        )
        ledger.positions[asset] = position

        retrieved_position = ledger.get_position(asset)
        assert retrieved_position == position

    def test_get_position_not_exists(self):
        """Test getting position that doesn't exist."""
        ledger = DecimalLedger(starting_cash=Decimal("100000"))

        asset = MockAsset("AAPL")
        retrieved_position = ledger.get_position(asset)
        assert retrieved_position is None

    def test_to_dict(self):
        """Test ledger to_dict conversion."""
        ledger = DecimalLedger(starting_cash=Decimal("100000"))

        asset = MockAsset("AAPL")
        position = DecimalPosition(
            asset=asset,
            amount=Decimal("100"),
            cost_basis=Decimal("150"),
            last_sale_price=Decimal("155"),
        )
        ledger.positions[asset] = position

        result = ledger.to_dict()

        assert result["starting_cash"] == "100000"
        assert result["cash"] == "100000"
        assert "AAPL" in result["positions"]

    def test_repr(self):
        """Test ledger string representation."""
        ledger = DecimalLedger(starting_cash=Decimal("100000"))

        repr_str = repr(ledger)
        assert "DecimalLedger" in repr_str
        assert "100000" in repr_str
