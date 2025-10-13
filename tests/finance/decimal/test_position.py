"""Unit tests for DecimalPosition."""

from decimal import Decimal

import pandas as pd
import pytest

from rustybt.finance.decimal import (
    DecimalPosition,
    InvalidPositionError,
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

    def __class__(self):
        # Return a mock class with the specified name
        class MockClass:
            __name__ = self.asset_type

        return MockClass


class TestDecimalPosition:
    """Test DecimalPosition class."""

    def test_position_initialization(self):
        """Test position initializes with Decimal values."""
        asset = MockAsset("AAPL")
        position = DecimalPosition(
            asset=asset,
            amount=Decimal("100"),
            cost_basis=Decimal("150.00"),
            last_sale_price=Decimal("155.00"),
        )

        assert position.asset == asset
        assert position.amount == Decimal("100")
        assert position.cost_basis == Decimal("150.00")
        assert position.last_sale_price == Decimal("155.00")
        assert position.last_sale_date is None

    def test_position_initialization_with_date(self):
        """Test position initialization with last_sale_date."""
        asset = MockAsset("AAPL")
        dt = pd.Timestamp("2025-01-15")
        position = DecimalPosition(
            asset=asset,
            amount=Decimal("100"),
            cost_basis=Decimal("150.00"),
            last_sale_price=Decimal("155.00"),
            last_sale_date=dt,
        )

        assert position.last_sale_date == dt

    def test_position_rejects_non_decimal_amount(self):
        """Test position rejects non-Decimal amount."""
        asset = MockAsset("AAPL")

        with pytest.raises(InvalidPositionError, match="amount must be Decimal"):
            DecimalPosition(
                asset=asset,
                amount=100,  # int instead of Decimal
                cost_basis=Decimal("150.00"),
                last_sale_price=Decimal("155.00"),
            )

    def test_position_rejects_non_decimal_cost_basis(self):
        """Test position rejects non-Decimal cost_basis."""
        asset = MockAsset("AAPL")

        with pytest.raises(InvalidPositionError, match="cost_basis must be Decimal"):
            DecimalPosition(
                asset=asset,
                amount=Decimal("100"),
                cost_basis=150.00,  # float instead of Decimal
                last_sale_price=Decimal("155.00"),
            )

    def test_position_rejects_non_decimal_price(self):
        """Test position rejects non-Decimal last_sale_price."""
        asset = MockAsset("AAPL")

        with pytest.raises(InvalidPositionError, match="last_sale_price must be Decimal"):
            DecimalPosition(
                asset=asset,
                amount=Decimal("100"),
                cost_basis=Decimal("150.00"),
                last_sale_price=155.00,  # float instead of Decimal
            )

    def test_market_value_calculation(self):
        """Test market value calculation."""
        asset = MockAsset("AAPL")
        position = DecimalPosition(
            asset=asset,
            amount=Decimal("100"),
            cost_basis=Decimal("150.00"),
            last_sale_price=Decimal("155.50"),
        )

        expected_value = Decimal("100") * Decimal("155.50")
        assert position.market_value == expected_value
        assert position.market_value == Decimal("15550.00")

    def test_market_value_with_fractional_shares(self):
        """Test market value calculation with fractional shares (crypto)."""
        asset = MockAsset("BTC", asset_type="Cryptocurrency")
        position = DecimalPosition(
            asset=asset,
            amount=Decimal("0.00000001"),  # 1 Satoshi
            cost_basis=Decimal("50000.00"),
            last_sale_price=Decimal("55000.00"),
        )

        expected_value = Decimal("0.00000001") * Decimal("55000.00")
        assert position.market_value == expected_value
        assert position.market_value == Decimal("0.00055000")

    def test_unrealized_pnl_positive(self):
        """Test unrealized P&L calculation (profit)."""
        asset = MockAsset("AAPL")
        position = DecimalPosition(
            asset=asset,
            amount=Decimal("100"),
            cost_basis=Decimal("150.00"),
            last_sale_price=Decimal("155.00"),
        )

        market_value = Decimal("100") * Decimal("155.00")
        cost_value = Decimal("100") * Decimal("150.00")
        expected_pnl = market_value - cost_value

        assert position.unrealized_pnl == expected_pnl
        assert position.unrealized_pnl == Decimal("500.00")

    def test_unrealized_pnl_negative(self):
        """Test unrealized P&L calculation (loss)."""
        asset = MockAsset("AAPL")
        position = DecimalPosition(
            asset=asset,
            amount=Decimal("100"),
            cost_basis=Decimal("155.00"),
            last_sale_price=Decimal("150.00"),
        )

        market_value = Decimal("100") * Decimal("150.00")
        cost_value = Decimal("100") * Decimal("155.00")
        expected_pnl = market_value - cost_value

        assert position.unrealized_pnl == expected_pnl
        assert position.unrealized_pnl == Decimal("-500.00")

    def test_unrealized_pnl_short_position(self):
        """Test unrealized P&L for short position."""
        asset = MockAsset("AAPL")
        position = DecimalPosition(
            asset=asset,
            amount=Decimal("-100"),  # Short position
            cost_basis=Decimal("150.00"),
            last_sale_price=Decimal("145.00"),  # Price decreased
        )

        market_value = Decimal("-100") * Decimal("145.00")  # -14500
        cost_value = Decimal("-100") * Decimal("150.00")  # -15000
        expected_pnl = market_value - cost_value  # -14500 - (-15000) = 500

        assert position.unrealized_pnl == expected_pnl
        assert position.unrealized_pnl == Decimal("500.00")

    def test_update_same_direction_buy(self):
        """Test updating position with same-direction transaction (buy more)."""
        asset = MockAsset("AAPL")
        position = DecimalPosition(
            asset=asset,
            amount=Decimal("100"),
            cost_basis=Decimal("150.00"),
            last_sale_price=Decimal("150.00"),
        )

        # Buy 50 more shares at $155
        position.update(
            transaction_amount=Decimal("50"),
            transaction_price=Decimal("155.00"),
            transaction_dt=pd.Timestamp("2025-01-15"),
        )

        # New cost basis should be volume-weighted average
        # (100 * 150 + 50 * 155) / 150 = (15000 + 7750) / 150 = 151.67
        expected_cost_basis = (
            Decimal("100") * Decimal("150.00") + Decimal("50") * Decimal("155.00")
        ) / Decimal("150")

        assert position.amount == Decimal("150")
        assert position.cost_basis == expected_cost_basis
        assert position.last_sale_price == Decimal("155.00")

    def test_update_reverse_direction_partial_close(self):
        """Test updating position by reversing direction (partial close)."""
        asset = MockAsset("AAPL")
        position = DecimalPosition(
            asset=asset,
            amount=Decimal("100"),
            cost_basis=Decimal("150.00"),
            last_sale_price=Decimal("150.00"),
        )

        # Sell 60 shares (partial close)
        position.update(
            transaction_amount=Decimal("-60"),
            transaction_price=Decimal("155.00"),
            transaction_dt=pd.Timestamp("2025-01-15"),
        )

        # Cost basis should remain the same (not crossing zero)
        assert position.amount == Decimal("40")
        assert position.cost_basis == Decimal("150.00")
        assert position.last_sale_price == Decimal("155.00")

    def test_update_reverse_direction_cross_zero(self):
        """Test updating position by crossing zero (flip from long to short)."""
        asset = MockAsset("AAPL")
        position = DecimalPosition(
            asset=asset,
            amount=Decimal("100"),
            cost_basis=Decimal("150.00"),
            last_sale_price=Decimal("150.00"),
        )

        # Sell 150 shares (close and go short 50)
        position.update(
            transaction_amount=Decimal("-150"),
            transaction_price=Decimal("155.00"),
            transaction_dt=pd.Timestamp("2025-01-15"),
        )

        # Cost basis should be reset to transaction price
        assert position.amount == Decimal("-50")
        assert position.cost_basis == Decimal("155.00")
        assert position.last_sale_price == Decimal("155.00")

    def test_update_close_position(self):
        """Test closing position completely."""
        asset = MockAsset("AAPL")
        position = DecimalPosition(
            asset=asset,
            amount=Decimal("100"),
            cost_basis=Decimal("150.00"),
            last_sale_price=Decimal("150.00"),
        )

        # Sell all 100 shares
        position.update(
            transaction_amount=Decimal("-100"),
            transaction_price=Decimal("155.00"),
            transaction_dt=pd.Timestamp("2025-01-15"),
        )

        # Cost basis should be zero when position is closed
        assert position.amount == Decimal("0")
        assert position.cost_basis == Decimal("0")
        assert position.last_sale_price == Decimal("155.00")

    def test_handle_split_equity(self):
        """Test stock split handling for equity."""
        asset = MockAsset("AAPL", asset_type="Equity")
        position = DecimalPosition(
            asset=asset,
            amount=Decimal("100"),
            cost_basis=Decimal("150.00"),
            last_sale_price=Decimal("150.00"),
        )

        # 3-for-1 split: 100 / 3 = 33.33 → 33 shares
        cash_returned = position.handle_split(Decimal("3"))

        assert position.amount == Decimal("33")
        assert position.cost_basis == Decimal("450.00")  # 150 * 3

        # Cash from fractional share: 0.33 * 450 = 148.50
        # But rounded to nearest cent
        expected_cash = (Decimal("100") / Decimal("3") - Decimal("33")) * Decimal("450.00")
        assert cash_returned == expected_cash.quantize(Decimal("0.01"))

    def test_handle_split_crypto_no_cash(self):
        """Test split handling for crypto (no fractional share cash)."""
        asset = MockAsset("BTC", asset_type="Cryptocurrency")
        position = DecimalPosition(
            asset=asset,
            amount=Decimal("1.00000000"),
            cost_basis=Decimal("50000.00"),
            last_sale_price=Decimal("50000.00"),
        )

        # 2-for-1 split
        cash_returned = position.handle_split(Decimal("2"))

        assert position.amount == Decimal("0.50000000")
        assert position.cost_basis == Decimal("100000.00")
        assert cash_returned == Decimal("0.00")  # No fractional share cash for crypto

    def test_adjust_commission_cost_basis_long(self):
        """Test commission adjustment for long position."""
        asset = MockAsset("AAPL")
        position = DecimalPosition(
            asset=asset,
            amount=Decimal("100"),
            cost_basis=Decimal("150.00"),
            last_sale_price=Decimal("150.00"),
        )

        # Add $10 commission
        position.adjust_commission_cost_basis(commission=Decimal("10.00"))

        # New cost basis: (150 * 100 + 10) / 100 = 150.10
        expected_cost_basis = (Decimal("150.00") * Decimal("100") + Decimal("10.00")) / Decimal(
            "100"
        )
        assert position.cost_basis == expected_cost_basis
        assert position.cost_basis == Decimal("150.10")

    def test_adjust_commission_cost_basis_short(self):
        """Test commission adjustment for short position."""
        asset = MockAsset("AAPL")
        position = DecimalPosition(
            asset=asset,
            amount=Decimal("-100"),
            cost_basis=Decimal("150.00"),
            last_sale_price=Decimal("150.00"),
        )

        # Add $10 commission
        position.adjust_commission_cost_basis(commission=Decimal("10.00"))

        # For shorts, commission decreases the cost basis (break even at lower price)
        # New cost basis: (150 * -100 + 10) / -100 = 149.90
        expected_cost_basis = (Decimal("150.00") * Decimal("-100") + Decimal("10.00")) / Decimal(
            "-100"
        )
        assert position.cost_basis == expected_cost_basis
        assert position.cost_basis == Decimal("149.90")

    def test_adjust_commission_zero_amount_no_change(self):
        """Test commission adjustment does nothing for zero amount."""
        asset = MockAsset("AAPL")
        position = DecimalPosition(
            asset=asset,
            amount=Decimal("0"),
            cost_basis=Decimal("150.00"),
            last_sale_price=Decimal("150.00"),
        )

        original_cost_basis = position.cost_basis
        position.adjust_commission_cost_basis(commission=Decimal("10.00"))

        assert position.cost_basis == original_cost_basis

    def test_adjust_commission_zero_commission_no_change(self):
        """Test zero commission adjustment does nothing."""
        asset = MockAsset("AAPL")
        position = DecimalPosition(
            asset=asset,
            amount=Decimal("100"),
            cost_basis=Decimal("150.00"),
            last_sale_price=Decimal("150.00"),
        )

        original_cost_basis = position.cost_basis
        position.adjust_commission_cost_basis(commission=Decimal("0"))

        assert position.cost_basis == original_cost_basis

    def test_to_dict(self):
        """Test position to_dict conversion."""
        asset = MockAsset("AAPL")
        dt = pd.Timestamp("2025-01-15")
        position = DecimalPosition(
            asset=asset,
            amount=Decimal("100"),
            cost_basis=Decimal("150.00"),
            last_sale_price=Decimal("155.00"),
            last_sale_date=dt,
        )

        result = position.to_dict()

        assert result["asset"] == asset
        assert result["amount"] == "100"
        assert result["cost_basis"] == "150.00"
        assert result["last_sale_price"] == "155.00"
        assert result["last_sale_date"] == dt
        assert result["market_value"] == "15500.00"
        assert result["unrealized_pnl"] == "500.00"

    def test_repr(self):
        """Test position string representation."""
        asset = MockAsset("AAPL")
        position = DecimalPosition(
            asset=asset,
            amount=Decimal("100"),
            cost_basis=Decimal("150.00"),
            last_sale_price=Decimal("155.00"),
        )

        repr_str = repr(position)
        assert "DecimalPosition" in repr_str
        assert "100" in repr_str
        assert "150.00" in repr_str
        assert "155.00" in repr_str
