#
# Copyright 2025 RustyBT Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Unit tests for cash validation in SimulationBlotter.

These tests don't depend on h5py-based fixtures to avoid segfault issues.
"""
import pandas as pd
import pytest

from rustybt.assets import Equity
from rustybt.exceptions import InsufficientFundsError
from rustybt.finance.blotter import SimulationBlotter
from rustybt.finance.cancel_policy import NeverCancel
from rustybt.finance.execution import LimitOrder, MarketOrder


class MockPortfolio:
    """Simple portfolio mock for testing (not a mocking framework)."""

    def __init__(self, cash_amount):
        self.cash = cash_amount
        self.positions = {}
        self.portfolio_value = cash_amount


class MockDataPortal:
    """Simple data portal mock for testing (not a mocking framework)."""

    def __init__(self, prices):
        self.prices = prices  # Dict of {asset: price}

    def get_spot_value(self, asset, field, dt, frequency):
        return self.prices.get(asset, 50.0)


class TestCashValidationBasic:
    """Basic cash validation tests without h5py dependencies."""

    def test_blotter_creation_with_cash_validation(self):
        """Test that blotter can be created with cash validation enabled."""
        blotter = SimulationBlotter(cancel_policy=NeverCancel(), enable_cash_validation=True)
        assert blotter.enable_cash_validation is True

    def test_blotter_creation_with_cash_validation_disabled(self):
        """Test that blotter can be created with cash validation disabled."""
        blotter = SimulationBlotter(cancel_policy=NeverCancel(), enable_cash_validation=False)
        assert blotter.enable_cash_validation is False

    def test_set_portfolio_reference(self):
        """Test that portfolio reference can be set."""
        blotter = SimulationBlotter(cancel_policy=NeverCancel())
        portfolio = MockPortfolio(10000.0)
        data_portal = MockDataPortal({})

        blotter.set_portfolio_reference(portfolio, data_portal)

        assert blotter.portfolio is portfolio
        assert blotter.data_portal is data_portal

    def test_order_rejected_insufficient_cash_limit_order(self):
        """Test that limit orders are rejected when cash is insufficient (default reject mode)."""
        blotter = SimulationBlotter(cancel_policy=NeverCancel())
        blotter.current_dt = pd.Timestamp("2024-01-01")

        # Create mock asset
        asset = Equity(
            24,
            exchange_info={"id": "test_exchange"},
            symbol="TEST",
            asset_name="TEST",
        )

        # Create portfolio with $1000 cash
        portfolio = MockPortfolio(1000.0)
        data_portal = MockDataPortal({asset: 50.0})

        # Set portfolio reference
        blotter.set_portfolio_reference(portfolio, data_portal)

        # Try to buy 100 shares at $50 each = $5000 (exceeds $1000 cash)
        # Default mode is "reject" - should return None, not raise
        order_id = blotter.order(
            asset=asset,
            amount=100,
            style=LimitOrder(limit_price=50.0),
            order_id="test-order-1",
        )

        # Verify order was rejected
        assert order_id is None

    def test_order_accepted_sufficient_cash(self):
        """Test that orders are accepted when cash is sufficient."""
        blotter = SimulationBlotter(cancel_policy=NeverCancel())
        blotter.current_dt = pd.Timestamp("2024-01-01")

        asset = Equity(
            24,
            exchange_info={"id": "test_exchange"},
            symbol="TEST",
            asset_name="TEST",
        )

        # Create portfolio with $10,000 cash
        portfolio = MockPortfolio(10000.0)
        data_portal = MockDataPortal({asset: 50.0})
        blotter.set_portfolio_reference(portfolio, data_portal)

        # Buy 100 shares at $50 each = $5000 (within $10,000 cash)
        order_id = blotter.order(
            asset=asset,
            amount=100,
            style=LimitOrder(limit_price=50.0),
        )

        # Verify order was created
        assert order_id is not None
        assert order_id in blotter.orders
        assert blotter.orders[order_id].amount == 100

    def test_sell_orders_dont_require_cash(self):
        """Test that sell orders (negative amount) bypass cash validation."""
        blotter = SimulationBlotter(cancel_policy=NeverCancel())
        blotter.current_dt = pd.Timestamp("2024-01-01")

        asset = Equity(
            24,
            exchange_info={"id": "test_exchange"},
            symbol="TEST",
            asset_name="TEST",
        )

        # Create portfolio with only $100 cash
        portfolio = MockPortfolio(100.0)
        data_portal = MockDataPortal({asset: 50.0})
        blotter.set_portfolio_reference(portfolio, data_portal)

        # Sell order should succeed even with low cash
        order_id = blotter.order(
            asset=asset,
            amount=-100,  # Sell 100 shares
            style=LimitOrder(limit_price=50.0),
        )

        # Verify order was created
        assert order_id is not None
        assert blotter.orders[order_id].amount == -100

    def test_cash_validation_disabled_when_flag_false(self):
        """Test that cash validation can be disabled via configuration flag."""
        blotter = SimulationBlotter(cancel_policy=NeverCancel(), enable_cash_validation=False)
        blotter.current_dt = pd.Timestamp("2024-01-01")

        asset = Equity(
            24,
            exchange_info={"id": "test_exchange"},
            symbol="TEST",
            asset_name="TEST",
        )

        # Create portfolio with only $1000 cash
        portfolio = MockPortfolio(1000.0)
        data_portal = MockDataPortal({asset: 50.0})
        blotter.set_portfolio_reference(portfolio, data_portal)

        # Try to buy $5000 worth - should succeed when validation disabled
        order_id = blotter.order(
            asset=asset,
            amount=100,  # 100 * $50 = $5000
            style=LimitOrder(limit_price=50.0),
        )

        # Order should be created (validation was disabled)
        assert order_id is not None

    def test_reserved_cash_calculation(self):
        """Test that reserved cash is correctly calculated."""
        blotter = SimulationBlotter(cancel_policy=NeverCancel())
        blotter.current_dt = pd.Timestamp("2024-01-01")

        asset = Equity(
            24,
            exchange_info={"id": "test_exchange"},
            symbol="TEST",
            asset_name="TEST",
        )

        portfolio = MockPortfolio(10000.0)
        data_portal = MockDataPortal({asset: 50.0})
        blotter.set_portfolio_reference(portfolio, data_portal)

        # Place order: 100 shares @ $50 = $5000
        blotter.order(
            asset=asset,
            amount=100,
            style=LimitOrder(limit_price=50.0),
        )

        # Calculate reserved cash
        reserved = blotter._calculate_reserved_cash()
        assert reserved == pytest.approx(5000.0, rel=0.01)

    def test_validation_mode_reject_returns_none(self):
        """Test that 'reject' mode returns None instead of raising exception."""
        blotter = SimulationBlotter(cancel_policy=NeverCancel(), cash_validation_mode="reject")
        blotter.current_dt = pd.Timestamp("2024-01-01")

        asset = Equity(
            24,
            exchange_info={"id": "test_exchange"},
            symbol="TEST",
            asset_name="TEST",
        )

        # Create portfolio with $1000 cash
        portfolio = MockPortfolio(1000.0)
        data_portal = MockDataPortal({asset: 50.0})
        blotter.set_portfolio_reference(portfolio, data_portal)

        # Try to buy $5000 worth - should return None, not raise
        order_id = blotter.order(
            asset=asset,
            amount=100,  # 100 * $50 = $5000 > $1000
            style=LimitOrder(limit_price=50.0),
        )

        # Verify order was rejected (None returned)
        assert order_id is None

    def test_validation_mode_warn_allows_order(self):
        """Test that 'warn' mode allows order despite insufficient cash."""
        blotter = SimulationBlotter(cancel_policy=NeverCancel(), cash_validation_mode="warn")
        blotter.current_dt = pd.Timestamp("2024-01-01")

        asset = Equity(
            24,
            exchange_info={"id": "test_exchange"},
            symbol="TEST",
            asset_name="TEST",
        )

        # Create portfolio with $1000 cash
        portfolio = MockPortfolio(1000.0)
        data_portal = MockDataPortal({asset: 50.0})
        blotter.set_portfolio_reference(portfolio, data_portal)

        # Try to buy $5000 worth - should create order with warning
        order_id = blotter.order(
            asset=asset,
            amount=100,  # 100 * $50 = $5000 > $1000
            style=LimitOrder(limit_price=50.0),
        )

        # Verify order was created despite insufficient cash
        assert order_id is not None
        assert order_id in blotter.orders

    def test_validation_mode_strict_raises_exception(self):
        """Test that 'strict' mode raises InsufficientFundsError."""
        blotter = SimulationBlotter(cancel_policy=NeverCancel(), cash_validation_mode="strict")
        blotter.current_dt = pd.Timestamp("2024-01-01")

        asset = Equity(
            24,
            exchange_info={"id": "test_exchange"},
            symbol="TEST",
            asset_name="TEST",
        )

        # Create portfolio with $1000 cash
        portfolio = MockPortfolio(1000.0)
        data_portal = MockDataPortal({asset: 50.0})
        blotter.set_portfolio_reference(portfolio, data_portal)

        # Try to buy $5000 worth - should raise exception
        with pytest.raises(InsufficientFundsError):
            blotter.order(
                asset=asset,
                amount=100,  # 100 * $50 = $5000 > $1000
                style=LimitOrder(limit_price=50.0),
            )

    def test_invalid_validation_mode_raises_error(self):
        """Test that invalid validation mode raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            SimulationBlotter(cancel_policy=NeverCancel(), cash_validation_mode="invalid")

        assert "must be 'reject', 'warn', or 'strict'" in str(exc_info.value)

    def test_default_validation_mode_is_reject(self):
        """Test that default validation mode is 'reject'."""
        blotter = SimulationBlotter(cancel_policy=NeverCancel())
        assert blotter.cash_validation_mode == "reject"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
