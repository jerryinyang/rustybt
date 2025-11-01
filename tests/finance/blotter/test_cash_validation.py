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
Tests for cash validation in SimulationBlotter.

This test suite verifies that the blotter correctly validates available cash
before allowing orders to be placed, preventing negative cash balances that
could occur in backtests.
"""
import pandas as pd
import pytest

from rustybt.assets import Equity
from rustybt.exceptions import InsufficientFundsError
from rustybt.finance.blotter import SimulationBlotter
from rustybt.finance.cancel_policy import NeverCancel
from rustybt.finance.execution import LimitOrder, MarketOrder
from rustybt.finance.order import ORDER_STATUS
from rustybt.testing.fixtures import (
    WithCreateBarData,
    WithDataPortal,
    WithSimParams,
    ZiplineTestCase,
)


class CashValidationTestCase(WithCreateBarData, WithDataPortal, WithSimParams, ZiplineTestCase):
    """Test cases for cash validation in SimulationBlotter."""

    START_DATE = pd.Timestamp("2006-01-05")
    END_DATE = pd.Timestamp("2006-01-06")
    ASSET_FINDER_EQUITY_SIDS = 24, 25

    @classmethod
    def init_class_fixtures(cls):
        super(CashValidationTestCase, cls).init_class_fixtures()
        cls.asset_24 = cls.asset_finder.retrieve_asset(24)
        cls.asset_25 = cls.asset_finder.retrieve_asset(25)

    @classmethod
    def make_equity_daily_bar_data(cls, country_code, sids):
        """Create price data for testing."""
        yield (
            24,
            pd.DataFrame(
                {
                    "open": [50, 50],
                    "high": [50, 50],
                    "low": [50, 50],
                    "close": [50, 50],
                    "volume": [100, 400],
                },
                index=cls.sim_params.sessions,
            ),
        )
        yield (
            25,
            pd.DataFrame(
                {
                    "open": [100, 100],
                    "high": [100, 100],
                    "low": [100, 100],
                    "close": [100, 100],
                    "volume": [100, 400],
                },
                index=cls.sim_params.sessions,
            ),
        )

    def create_mock_portfolio(self, cash=10000.0):
        """Create a simple portfolio mock for testing.

        Note: This is NOT a mocking framework - it's a simple data class
        that holds portfolio state for testing.
        """

        class MockPortfolio:
            def __init__(self, cash_amount):
                self.cash = cash_amount
                self.positions = {}
                self.portfolio_value = cash_amount

        return MockPortfolio(cash)

    def test_order_rejected_insufficient_cash_limit_order(self):
        """Test that limit orders are rejected when cash is insufficient."""
        blotter = SimulationBlotter(cancel_policy=NeverCancel())
        blotter.current_dt = self.sim_params.sessions[0]

        # Create portfolio with $1000 cash
        portfolio = self.create_mock_portfolio(cash=1000.0)

        # Set portfolio reference
        blotter.set_portfolio_reference(portfolio, self.data_portal)

        # Try to buy 100 shares at $50 each = $5000 (exceeds $1000 cash)
        with pytest.raises(InsufficientFundsError) as exc_info:
            blotter.order(
                asset=self.asset_24,
                amount=100,
                style=LimitOrder(limit_price=50.0),
                order_id="test-order-1",
            )

        # Verify error message contains useful information
        assert "$5,000.00" in str(exc_info.value) or "5000.00" in str(exc_info.value)
        assert "$1,000.00" in str(exc_info.value) or "1000.00" in str(exc_info.value)

    def test_order_accepted_sufficient_cash(self):
        """Test that orders are accepted when cash is sufficient."""
        blotter = SimulationBlotter(cancel_policy=NeverCancel())
        blotter.current_dt = self.sim_params.sessions[0]

        # Create portfolio with $10,000 cash
        portfolio = self.create_mock_portfolio(cash=10000.0)
        blotter.set_portfolio_reference(portfolio, self.data_portal)

        # Buy 100 shares at $50 each = $5000 (within $10,000 cash)
        order_id = blotter.order(
            asset=self.asset_24,
            amount=100,
            style=LimitOrder(limit_price=50.0),
        )

        # Verify order was created
        assert order_id is not None
        assert order_id in blotter.orders
        assert blotter.orders[order_id].amount == 100

    def test_reserved_cash_tracked_for_pending_orders(self):
        """Test that pending orders reserve cash, preventing over-ordering."""
        blotter = SimulationBlotter(cancel_policy=NeverCancel())
        blotter.current_dt = self.sim_params.sessions[0]

        # Create portfolio with $10,000 cash
        portfolio = self.create_mock_portfolio(cash=10000.0)
        blotter.set_portfolio_reference(portfolio, self.data_portal)

        # Place first order: 100 shares @ $50 = $5000
        order_id_1 = blotter.order(
            asset=self.asset_24,
            amount=100,
            style=LimitOrder(limit_price=50.0),
        )
        assert order_id_1 is not None

        # Calculate reserved cash - should be $5000
        reserved = blotter._calculate_reserved_cash()
        assert reserved == pytest.approx(5000.0, rel=0.01)

        # Try to place second order: 150 shares @ $50 = $7500
        # Total needed: $5000 + $7500 = $12,500 > $10,000 available
        with pytest.raises(InsufficientFundsError):
            blotter.order(
                asset=self.asset_25,
                amount=150,
                style=LimitOrder(limit_price=50.0),
            )

    def test_multiple_orders_respect_total_cash(self):
        """Test that multiple orders cannot exceed total cash."""
        blotter = SimulationBlotter(cancel_policy=NeverCancel())
        blotter.current_dt = self.sim_params.sessions[0]

        # Create portfolio with $10,000 cash
        portfolio = self.create_mock_portfolio(cash=10000.0)
        blotter.set_portfolio_reference(portfolio, self.data_portal)

        # Place first order: 80 shares @ $50 = $4000
        order_id_1 = blotter.order(
            asset=self.asset_24,
            amount=80,
            style=LimitOrder(limit_price=50.0),
        )
        assert order_id_1 is not None

        # Place second order: 60 shares @ $50 = $3000 (total $7000 < $10,000)
        order_id_2 = blotter.order(
            asset=self.asset_25,
            amount=60,
            style=LimitOrder(limit_price=50.0),
        )
        assert order_id_2 is not None

        # Try third order: 80 shares @ $50 = $4000
        # Total: $4000 + $3000 + $4000 = $11,000 > $10,000
        with pytest.raises(InsufficientFundsError):
            blotter.order(
                asset=self.asset_24,
                amount=80,
                style=LimitOrder(limit_price=50.0),
            )

    def test_sell_orders_dont_require_cash(self):
        """Test that sell orders (negative amount) bypass cash validation."""
        blotter = SimulationBlotter(cancel_policy=NeverCancel())
        blotter.current_dt = self.sim_params.sessions[0]

        # Create portfolio with only $100 cash
        portfolio = self.create_mock_portfolio(cash=100.0)
        blotter.set_portfolio_reference(portfolio, self.data_portal)

        # Sell order should succeed even with low cash
        order_id = blotter.order(
            asset=self.asset_24,
            amount=-100,  # Sell 100 shares
            style=LimitOrder(limit_price=50.0),
        )

        # Verify order was created
        assert order_id is not None
        assert blotter.orders[order_id].amount == -100

    def test_cash_validation_disabled_when_flag_false(self):
        """Test that cash validation can be disabled via configuration flag."""
        blotter = SimulationBlotter(cancel_policy=NeverCancel(), enable_cash_validation=False)
        blotter.current_dt = self.sim_params.sessions[0]

        # Create portfolio with only $1000 cash
        portfolio = self.create_mock_portfolio(cash=1000.0)
        blotter.set_portfolio_reference(portfolio, self.data_portal)

        # Try to buy $10,000 worth - should succeed when validation disabled
        order_id = blotter.order(
            asset=self.asset_24,
            amount=200,  # 200 * $50 = $10,000
            style=LimitOrder(limit_price=50.0),
        )

        # Order should be created (validation was disabled)
        assert order_id is not None

    def test_cash_validation_disabled_without_portfolio_reference(self):
        """Test that validation is skipped if portfolio reference not set."""
        blotter = SimulationBlotter(cancel_policy=NeverCancel())
        blotter.current_dt = self.sim_params.sessions[0]

        # Don't set portfolio reference (blotter.portfolio remains None)

        # Order should be created without validation
        order_id = blotter.order(
            asset=self.asset_24,
            amount=1000,  # Large order
            style=LimitOrder(limit_price=50.0),
        )

        assert order_id is not None

    def test_market_order_uses_current_price_for_validation(self):
        """Test that market orders use current price from data portal."""
        blotter = SimulationBlotter(cancel_policy=NeverCancel())
        blotter.current_dt = self.sim_params.sessions[0]

        # Create portfolio with $6000 cash
        portfolio = self.create_mock_portfolio(cash=6000.0)
        blotter.set_portfolio_reference(portfolio, self.data_portal)

        # Market order for 100 shares (current price is $50, so $5000 total)
        order_id = blotter.order(asset=self.asset_24, amount=100, style=MarketOrder())

        # Should succeed because $5000 < $6000
        assert order_id is not None

        # Now try order that exceeds cash
        with pytest.raises(InsufficientFundsError):
            blotter.order(
                asset=self.asset_24,
                amount=200,  # 200 * $50 = $10,000 > $6000
                style=MarketOrder(),
            )

    def test_reserved_cash_excludes_sell_orders(self):
        """Test that sell orders are not counted in reserved cash."""
        blotter = SimulationBlotter(cancel_policy=NeverCancel())
        blotter.current_dt = self.sim_params.sessions[0]

        portfolio = self.create_mock_portfolio(cash=10000.0)
        blotter.set_portfolio_reference(portfolio, self.data_portal)

        # Place buy order
        blotter.order(
            asset=self.asset_24,
            amount=100,
            style=LimitOrder(limit_price=50.0),
        )

        # Place sell order
        blotter.order(
            asset=self.asset_25,
            amount=-50,
            style=LimitOrder(limit_price=100.0),
        )

        # Reserved cash should only include buy order ($5000)
        reserved = blotter._calculate_reserved_cash()
        assert reserved == pytest.approx(5000.0, rel=0.01)

    def test_error_message_includes_context(self):
        """Test that InsufficientFundsError includes helpful context."""
        blotter = SimulationBlotter(cancel_policy=NeverCancel())
        blotter.current_dt = self.sim_params.sessions[0]

        portfolio = self.create_mock_portfolio(cash=1000.0)
        blotter.set_portfolio_reference(portfolio, self.data_portal)

        # Place first order to create reserved cash
        blotter.order(
            asset=self.asset_24,
            amount=10,
            style=LimitOrder(limit_price=50.0),
        )

        # Try second order that exceeds available cash
        with pytest.raises(InsufficientFundsError) as exc_info:
            blotter.order(
                asset=self.asset_25,
                amount=20,
                style=LimitOrder(limit_price=100.0),
            )

        error = exc_info.value
        # Verify context contains expected fields
        assert hasattr(error, "context")
        assert "asset" in error.context
        assert "amount" in error.context
        assert "estimated_price" in error.context
        assert "total_cash" in error.context
        assert "reserved_cash" in error.context
