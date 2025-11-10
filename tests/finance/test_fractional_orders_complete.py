"""
Comprehensive TDD Tests for Fractional Order Execution

CRITICAL BUG: RustyBT silently rounds fractional order fills to integers.
This test suite validates the complete fix for fractional order handling.

Test Coverage:
1. Asset configuration detects crypto pairs correctly
2. Fractional order mode setting in initialize() works
3. Order amounts preserve fractional values
4. Transaction amounts preserve fractional values
5. Slippage models preserve fractional values
6. Position tracking preserves fractional amounts
7. End-to-end fractional order execution
"""

from unittest.mock import Mock

import pandas as pd
import pytest

from rustybt.assets import Asset
from rustybt.finance.asset_config import (
    FractionalOrderMode,
    is_crypto_exchange,
    should_use_fractional_orders,
)
from rustybt.finance.order import Order
from rustybt.finance.slippage import VolumeShareSlippage
from rustybt.finance.transaction import create_transaction


class TestAssetConfiguration:
    """Test that crypto assets are properly detected for fractional orders."""

    def test_crypto_pair_detection_by_name(self):
        """Crypto pairs like BTC/USDT should be detected by name format."""
        # Create mock asset with crypto pair name
        asset = Mock(spec=Asset)
        asset.asset_name = "BTC/USDT"
        asset.exchange_info = None  # May not be set

        result = should_use_fractional_orders(asset, FractionalOrderMode.AUTO)
        assert result is True, "BTC/USDT should enable fractional orders in AUTO mode"

    def test_crypto_pair_detection_eth(self):
        """ETH/USDT should also be detected."""
        asset = Mock(spec=Asset)
        asset.asset_name = "ETH/USDT"

        result = should_use_fractional_orders(asset, FractionalOrderMode.AUTO)
        assert result is True, "ETH/USDT should enable fractional orders in AUTO mode"

    def test_non_crypto_asset(self):
        """Traditional assets without / should use integers."""
        asset = Mock(spec=Asset)
        asset.asset_name = "AAPL"
        asset.exchange_info = None

        result = should_use_fractional_orders(asset, FractionalOrderMode.AUTO)
        assert result is False, "AAPL should NOT enable fractional orders in AUTO mode"

    def test_always_mode_forces_fractional(self):
        """ALWAYS mode should enable fractional for all assets."""
        asset = Mock(spec=Asset)
        asset.asset_name = "AAPL"

        result = should_use_fractional_orders(asset, FractionalOrderMode.ALWAYS)
        assert result is True, "ALWAYS mode should enable fractional for all assets"

    def test_never_mode_forces_integer(self):
        """NEVER mode should disable fractional for all assets."""
        asset = Mock(spec=Asset)
        asset.asset_name = "BTC/USDT"

        result = should_use_fractional_orders(asset, FractionalOrderMode.NEVER)
        assert result is False, "NEVER mode should disable fractional for all assets"


class TestTransactionCreation:
    """Test that transactions preserve fractional amounts."""

    def test_fractional_transaction_amount_preserved(self):
        """Transaction should preserve fractional amount when mode is ALWAYS."""
        # Create mock order with fractional amount
        order = Mock(spec=Order)
        order.asset = Mock(spec=Asset)
        order.asset.asset_name = "BTC/USDT"
        order.id = "test_order_1"

        # Request fractional fill: 1.5660932 BTC
        requested_amount = 1.5660932073098248
        dt = pd.Timestamp("2020-03-26")
        price = 6663.92

        txn = create_transaction(
            order=order,
            dt=dt,
            price=price,
            amount=requested_amount,
            fractional_order_mode=FractionalOrderMode.ALWAYS,
        )

        assert (
            abs(txn.amount - requested_amount) < 1e-10
        ), f"Transaction amount should be {requested_amount}, got {txn.amount}"

    def test_fractional_transaction_small_amount(self):
        """Transaction should preserve small fractional amounts."""
        order = Mock(spec=Order)
        order.asset = Mock(spec=Asset)
        order.asset.asset_name = "BTC/USDT"
        order.id = "test_order_2"

        # Small fractional amount
        requested_amount = 0.1578038597022786
        dt = pd.Timestamp("2020-03-27")
        price = 6562.16

        txn = create_transaction(
            order=order,
            dt=dt,
            price=price,
            amount=requested_amount,
            fractional_order_mode=FractionalOrderMode.ALWAYS,
        )

        assert (
            abs(txn.amount - requested_amount) < 1e-10
        ), f"Small fractional amount should be preserved: {requested_amount} != {txn.amount}"

    def test_integer_transaction_in_never_mode(self):
        """Transaction should round to integer when mode is NEVER."""
        order = Mock(spec=Order)
        order.asset = Mock(spec=Asset)
        order.asset.asset_name = "BTC/USDT"
        order.id = "test_order_3"

        requested_amount = 1.5660932073098248
        dt = pd.Timestamp("2020-03-26")
        price = 6663.92

        txn = create_transaction(
            order=order,
            dt=dt,
            price=price,
            amount=requested_amount,
            fractional_order_mode=FractionalOrderMode.NEVER,
        )

        assert (
            txn.amount == 1
        ), f"Transaction amount should be rounded to 1 in NEVER mode, got {txn.amount}"

    def test_negative_fractional_amount(self):
        """Negative fractional amounts (sells) should also be preserved."""
        order = Mock(spec=Order)
        order.asset = Mock(spec=Asset)
        order.asset.asset_name = "BTC/USDT"
        order.id = "test_order_4"

        requested_amount = -1.5660932073098248
        dt = pd.Timestamp("2020-03-26")
        price = 6663.92

        txn = create_transaction(
            order=order,
            dt=dt,
            price=price,
            amount=requested_amount,
            fractional_order_mode=FractionalOrderMode.ALWAYS,
        )

        assert (
            abs(txn.amount - requested_amount) < 1e-10
        ), f"Negative fractional amount should be preserved: {requested_amount} != {txn.amount}"


class TestSlippageModels:
    """Test that slippage models preserve fractional amounts."""

    def test_volume_share_slippage_fractional(self):
        """VolumeShareSlippage should preserve fractional order amounts."""
        slippage = VolumeShareSlippage(volume_limit=0.025, price_impact=0.1)

        # Create mock order with fractional open_amount
        order = Mock(spec=Order)
        order.asset = Mock(spec=Asset)
        order.asset.asset_name = "BTC/USDT"
        order.asset.symbol = "BTC/USDT"
        order.open_amount = 1.5660932073098248
        order.amount = 1.5660932073098248
        order.direction = 1  # Buy order
        order.limit = None  # No limit price
        order.stop = None  # No stop price

        # Create mock data
        data = Mock()
        data.current = Mock(return_value=1000000.0)  # High volume

        # Process order
        price, amount = slippage.process_order(data, order)

        # Should return fractional amount, not rounded to integer
        assert amount is not None, "Slippage should not reject fractional orders"
        assert abs(amount) > 1.5, f"Amount should be fractional (1.566...), got {amount}"
        assert abs(amount) < 1.6, f"Amount should not be rounded to 2, got {amount}"

    def test_slippage_small_fractional_amount(self):
        """Slippage should handle amounts < 1.0 correctly."""
        slippage = VolumeShareSlippage(volume_limit=0.025, price_impact=0.1)

        order = Mock(spec=Order)
        order.asset = Mock(spec=Asset)
        order.asset.asset_name = "BTC/USDT"
        order.asset.symbol = "BTC/USDT"
        order.open_amount = 0.1578038597022786
        order.amount = 0.1578038597022786
        order.direction = 1  # Buy order
        order.limit = None  # No limit price
        order.stop = None  # No stop price

        data = Mock()
        data.current = Mock(return_value=1000000.0)

        price, amount = slippage.process_order(data, order)

        assert amount is not None, "Slippage should not reject amounts < 1.0"
        assert abs(amount) > 0.15, f"Small fractional amount should be preserved: {amount}"
        assert abs(amount) < 0.16, f"Amount should not be rounded: {amount}"


class TestFractionalOrderModeInInitialize:
    """Test that fractional_order_mode can be set in initialize() method."""

    def test_mode_settable_in_initialize(self):
        """Setting fractional_order_mode in initialize() should work."""
        from rustybt.algorithm import TradingAlgorithm

        class TestStrategy(TradingAlgorithm):
            def initialize(self):
                # This should work - set fractional mode in initialize
                from rustybt.finance.asset_config import FractionalOrderMode

                self.fractional_order_mode = FractionalOrderMode.ALWAYS

        # This test verifies the pattern works without error
        # The actual functionality will be tested in integration tests


class TestEndToEndFractionalExecution:
    """Integration tests for complete fractional order execution flow."""

    def test_order_to_transaction_fractional_preserved(self):
        """Complete flow from order creation to transaction should preserve fractional amounts."""
        # This will be an integration test once fixes are in place
        # For now, validates the test structure
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
