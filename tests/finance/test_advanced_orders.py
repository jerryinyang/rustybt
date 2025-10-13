"""
Tests for advanced order types: Trailing Stop, OCO, and Bracket orders.
"""

import pandas as pd
import pytest

from rustybt.assets import Equity
from rustybt.assets.exchange_info import ExchangeInfo
from rustybt.errors import BadOrderParameters
from rustybt.finance.blotter.simulation_blotter import SimulationBlotter
from rustybt.finance.execution import (
    BracketOrder,
    LimitOrder,
    MarketOrder,
    OCOOrder,
    StopOrder,
    TrailingStopOrder,
)
from rustybt.finance.order import ORDER_STATUS, Order


class TestTrailingStopOrder:
    """Test suite for TrailingStopOrder execution style."""

    def test_trailing_stop_requires_trail_param(self):
        """TrailingStopOrder must have either trail_amount or trail_percent."""
        with pytest.raises(
            BadOrderParameters, match="requires either trail_amount or trail_percent"
        ):
            TrailingStopOrder()

    def test_trailing_stop_cannot_have_both_params(self):
        """TrailingStopOrder cannot have both trail_amount and trail_percent."""
        with pytest.raises(BadOrderParameters, match="cannot have both"):
            TrailingStopOrder(trail_amount=5.0, trail_percent=0.05)

    def test_trailing_stop_amount_must_be_positive(self):
        """trail_amount must be positive."""
        with pytest.raises(BadOrderParameters, match="must be positive"):
            TrailingStopOrder(trail_amount=-5.0)

        with pytest.raises(BadOrderParameters, match="must be positive"):
            TrailingStopOrder(trail_amount=0)

    def test_trailing_stop_percent_must_be_valid(self):
        """trail_percent must be between 0 and 1."""
        with pytest.raises(BadOrderParameters, match="must be between 0 and 1"):
            TrailingStopOrder(trail_percent=-0.05)

        with pytest.raises(BadOrderParameters, match="must be between 0 and 1"):
            TrailingStopOrder(trail_percent=0)

        with pytest.raises(BadOrderParameters, match="must be between 0 and 1"):
            TrailingStopOrder(trail_percent=1.0)

        with pytest.raises(BadOrderParameters, match="must be between 0 and 1"):
            TrailingStopOrder(trail_percent=1.5)

    def test_trailing_stop_with_trail_amount(self):
        """TrailingStopOrder with trail_amount is valid."""
        style = TrailingStopOrder(trail_amount=5.0)
        assert style.trail_amount == 5.0
        assert style.trail_percent is None

    def test_trailing_stop_with_trail_percent(self):
        """TrailingStopOrder with trail_percent is valid."""
        style = TrailingStopOrder(trail_percent=0.05)
        assert style.trail_percent == 0.05
        assert style.trail_amount is None

    def test_trailing_stop_update_for_long_position_amount(self):
        """Trailing stop adjusts correctly for long position with trail_amount."""
        style = TrailingStopOrder(trail_amount=5.0)
        is_buy = False  # Sell order (closing long)

        # Initial price: $100, stop should be $95
        stop_price = style.update_trailing_stop(100.0, is_buy)
        assert stop_price == 95.0
        assert style._highest_price == 100.0

        # Price rises to $105, stop adjusts to $100
        stop_price = style.update_trailing_stop(105.0, is_buy)
        assert stop_price == 100.0
        assert style._highest_price == 105.0

        # Price falls to $103, stop stays at $100 (doesn't adjust downward)
        stop_price = style.update_trailing_stop(103.0, is_buy)
        assert stop_price == 100.0
        assert style._highest_price == 105.0  # Highest unchanged

        # Price rises to $110, stop adjusts to $105
        stop_price = style.update_trailing_stop(110.0, is_buy)
        assert stop_price == 105.0
        assert style._highest_price == 110.0

    def test_trailing_stop_update_for_long_position_percent(self):
        """Trailing stop adjusts correctly for long position with trail_percent."""
        style = TrailingStopOrder(trail_percent=0.05)  # 5%
        is_buy = False  # Sell order (closing long)

        # Initial price: $100, stop should be $95
        stop_price = style.update_trailing_stop(100.0, is_buy)
        assert stop_price == 95.0

        # Price rises to $105, stop adjusts to $99.75 (105 * 0.95)
        stop_price = style.update_trailing_stop(105.0, is_buy)
        assert stop_price == pytest.approx(99.75)

    def test_trailing_stop_update_for_short_position_amount(self):
        """Trailing stop adjusts correctly for short position with trail_amount."""
        style = TrailingStopOrder(trail_amount=5.0)
        is_buy = True  # Buy order (closing short)

        # Initial price: $100, stop should be $105
        stop_price = style.update_trailing_stop(100.0, is_buy)
        assert stop_price == 105.0
        assert style._lowest_price == 100.0

        # Price falls to $95, stop adjusts to $100
        stop_price = style.update_trailing_stop(95.0, is_buy)
        assert stop_price == 100.0
        assert style._lowest_price == 95.0

        # Price rises to $97, stop stays at $100 (doesn't adjust upward)
        stop_price = style.update_trailing_stop(97.0, is_buy)
        assert stop_price == 100.0
        assert style._lowest_price == 95.0  # Lowest unchanged

    def test_trailing_stop_never_widens_stop_distance(self):
        """Trailing stop should never increase the stop distance (property test)."""
        style = TrailingStopOrder(trail_amount=5.0)
        is_buy = False

        # Initial setup
        initial_price = 100.0
        style.update_trailing_stop(initial_price, is_buy)
        initial_stop = style._stop_price

        # Simulate various price movements
        prices = [105.0, 110.0, 108.0, 112.0, 107.0, 115.0]
        for price in prices:
            stop_price = style.update_trailing_stop(price, is_buy)
            # Stop should always be within trail_amount of highest price seen
            assert stop_price >= initial_stop  # Never worse than initial
            assert style._highest_price - stop_price == pytest.approx(5.0)


class TestOCOOrder:
    """Test suite for One-Cancels-Other (OCO) orders."""

    def test_oco_requires_execution_styles(self):
        """OCO order must have valid ExecutionStyle instances."""
        with pytest.raises(BadOrderParameters, match="must be an ExecutionStyle instance"):
            OCOOrder(order1_style="not_a_style", order2_style=LimitOrder(100.0))

        with pytest.raises(BadOrderParameters, match="must be an ExecutionStyle instance"):
            OCOOrder(order1_style=LimitOrder(100.0), order2_style="not_a_style")

    def test_oco_creation_with_valid_styles(self):
        """OCO order can be created with valid execution styles."""
        limit_style = LimitOrder(100.0)
        stop_style = StopOrder(95.0)
        oco = OCOOrder(order1_style=limit_style, order2_style=stop_style)

        assert oco.order1_style == limit_style
        assert oco.order2_style == stop_style

    def test_oco_has_no_own_prices(self):
        """OCO order delegates prices to child orders."""
        oco = OCOOrder(order1_style=LimitOrder(100.0), order2_style=StopOrder(95.0))
        assert oco.get_limit_price(True) is None
        assert oco.get_stop_price(True) is None


class TestBracketOrder:
    """Test suite for Bracket orders."""

    def test_bracket_requires_valid_entry_style(self):
        """BracketOrder entry_style must be an ExecutionStyle instance."""
        with pytest.raises(BadOrderParameters, match="must be an ExecutionStyle instance"):
            BracketOrder(entry_style="not_a_style", stop_loss_price=95.0, take_profit_price=105.0)

    def test_bracket_validates_stop_loss_price(self):
        """BracketOrder validates stop_loss_price."""
        with pytest.raises(BadOrderParameters, match="stop_loss"):
            BracketOrder(
                entry_style=MarketOrder(),
                stop_loss_price=-1.0,  # Invalid negative price
                take_profit_price=105.0,
            )

    def test_bracket_validates_take_profit_price(self):
        """BracketOrder validates take_profit_price."""
        with pytest.raises(BadOrderParameters, match="take_profit"):
            BracketOrder(
                entry_style=MarketOrder(),
                stop_loss_price=95.0,
                take_profit_price=-1.0,  # Invalid negative price
            )

    def test_bracket_creation_with_market_entry(self):
        """BracketOrder can be created with MarketOrder entry."""
        bracket = BracketOrder(
            entry_style=MarketOrder(), stop_loss_price=95.0, take_profit_price=105.0
        )
        assert bracket.stop_loss_price == 95.0
        assert bracket.take_profit_price == 105.0
        assert not bracket._entry_filled

    def test_bracket_creation_with_limit_entry(self):
        """BracketOrder can be created with LimitOrder entry."""
        bracket = BracketOrder(
            entry_style=LimitOrder(100.0), stop_loss_price=95.0, take_profit_price=105.0
        )
        assert bracket.get_limit_price(True) == 100.0

    def test_bracket_delegates_entry_prices(self):
        """BracketOrder delegates limit/stop prices to entry order."""
        entry_style = LimitOrder(100.0)
        bracket = BracketOrder(
            entry_style=entry_style, stop_loss_price=95.0, take_profit_price=105.0
        )
        assert bracket.get_limit_price(True) == entry_style.get_limit_price(True)
        assert bracket.get_stop_price(True) == entry_style.get_stop_price(True)


class TestOrderStateTransitions:
    """Test suite for order state machine and transitions."""

    def setup_method(self):
        """Set up test fixtures."""
        self.equity = Equity(
            1,
            exchange_info=ExchangeInfo("NYSE", "New York Stock Exchange", "US"),
        )
        self.dt = pd.Timestamp("2023-01-01")

    def test_order_starts_in_open_state(self):
        """New orders start in OPEN state."""
        order = Order(
            dt=self.dt,
            asset=self.equity,
            amount=100,
        )
        assert order.status == ORDER_STATUS.OPEN

    def test_order_filled_state(self):
        """Order transitions to FILLED when fully filled."""
        order = Order(
            dt=self.dt,
            asset=self.equity,
            amount=100,
            filled=100,
        )
        assert order.status == ORDER_STATUS.FILLED

    def test_order_partially_filled_state(self):
        """Order shows PARTIALLY_FILLED when partially filled."""
        order = Order(
            dt=self.dt,
            asset=self.equity,
            amount=100,
            filled=50,
        )
        assert order.status == ORDER_STATUS.PARTIALLY_FILLED
        assert order.open_amount == 50

    def test_order_cancelled_state(self):
        """Order can be cancelled."""
        order = Order(
            dt=self.dt,
            asset=self.equity,
            amount=100,
        )
        order.cancel()
        assert order.status == ORDER_STATUS.CANCELLED

    def test_order_rejected_state(self):
        """Order can be rejected with reason."""
        order = Order(
            dt=self.dt,
            asset=self.equity,
            amount=100,
        )
        order.reject(reason="Insufficient funds")
        assert order.status == ORDER_STATUS.REJECTED
        assert order.reason == "Insufficient funds"

    def test_stop_order_triggered_state(self):
        """Stop order shows TRIGGERED when stop price reached."""
        order = Order(
            dt=self.dt,
            asset=self.equity,
            amount=100,
            stop=95.0,
        )
        # Trigger the stop
        order.check_triggers(95.0, self.dt)
        assert order.stop_reached
        # Status should reflect triggered state when stop reached but not filled
        if order.filled == 0:
            assert order.status == ORDER_STATUS.TRIGGERED

    def test_trailing_stop_order_fields(self):
        """Trailing stop order has correct fields."""
        order = Order(
            dt=self.dt,
            asset=self.equity,
            amount=100,
            trail_amount=5.0,
        )
        assert order.is_trailing_stop
        assert order.trail_amount == 5.0
        assert order.trail_percent is None

    def test_linked_order_fields(self):
        """Orders can be linked for OCO."""
        order1 = Order(
            dt=self.dt,
            asset=self.equity,
            amount=100,
            limit=105.0,
        )
        order2 = Order(
            dt=self.dt,
            asset=self.equity,
            amount=100,
            stop=95.0,
        )
        order1.linked_order_ids = [order2.id]
        order2.linked_order_ids = [order1.id]

        assert order2.id in order1.linked_order_ids
        assert order1.id in order2.linked_order_ids


class TestBlotterIntegration:
    """Test blotter integration with advanced orders."""

    def setup_method(self):
        """Set up test fixtures."""
        self.blotter = SimulationBlotter()
        self.equity = Equity(
            1,
            exchange_info=ExchangeInfo("NYSE", "New York Stock Exchange", "US"),
        )
        self.blotter.set_date(pd.Timestamp("2023-01-01"))

    def test_blotter_creates_trailing_stop_order(self):
        """Blotter creates trailing stop order correctly."""
        order_id = self.blotter.order(
            asset=self.equity, amount=100, style=TrailingStopOrder(trail_amount=5.0)
        )

        assert order_id is not None
        order = self.blotter.orders[order_id]
        assert order.is_trailing_stop
        assert order.trail_amount == 5.0

    def test_blotter_creates_oco_order_pair(self):
        """Blotter creates OCO order pair with linked IDs."""
        limit_style = LimitOrder(105.0)
        stop_style = StopOrder(95.0)
        oco_style = OCOOrder(order1_style=limit_style, order2_style=stop_style)

        parent_id = self.blotter.order(asset=self.equity, amount=100, style=oco_style)

        assert parent_id is not None
        order1 = self.blotter.orders[parent_id]
        assert len(order1.linked_order_ids) == 1

        order2_id = order1.linked_order_ids[0]
        order2 = self.blotter.orders[order2_id]
        assert parent_id in order2.linked_order_ids

    def test_blotter_creates_bracket_order(self):
        """Blotter creates bracket order entry."""
        bracket_style = BracketOrder(
            entry_style=MarketOrder(), stop_loss_price=95.0, take_profit_price=105.0
        )

        entry_id = self.blotter.order(asset=self.equity, amount=100, style=bracket_style)

        assert entry_id is not None
        assert hasattr(self.blotter, "_bracket_orders")
        assert entry_id in self.blotter._bracket_orders

    def test_cancel_linked_orders_on_fill(self):
        """Canceling one OCO order cancels linked orders."""
        limit_style = LimitOrder(105.0)
        stop_style = StopOrder(95.0)
        oco_style = OCOOrder(order1_style=limit_style, order2_style=stop_style)

        parent_id = self.blotter.order(asset=self.equity, amount=100, style=oco_style)

        order1 = self.blotter.orders[parent_id]
        order2_id = order1.linked_order_ids[0]
        order2 = self.blotter.orders[order2_id]

        # Simulate order1 filling by calling cancel_linked_orders
        self.blotter.cancel_linked_orders(parent_id)

        # order2 should be cancelled
        assert order2.status == ORDER_STATUS.CANCELLED

    def test_bracket_order_creates_children_on_fill(self):
        """Bracket order creates stop-loss and take-profit on entry fill."""
        bracket_style = BracketOrder(
            entry_style=MarketOrder(), stop_loss_price=95.0, take_profit_price=105.0
        )

        entry_id = self.blotter.order(asset=self.equity, amount=100, style=bracket_style)

        # Simulate entry fill
        self.blotter.process_bracket_fill(entry_id)

        # Find child orders
        child_orders = [
            order for order in self.blotter.orders.values() if order.parent_order_id == entry_id
        ]

        assert len(child_orders) == 2

        # Verify one is stop-loss, one is take-profit
        stop_loss = next((o for o in child_orders if o.stop is not None), None)
        take_profit = next((o for o in child_orders if o.limit is not None), None)

        assert stop_loss is not None
        assert stop_loss.stop == 95.0
        assert take_profit is not None
        assert take_profit.limit == 105.0

        # Verify they're linked as OCO
        assert take_profit.id in stop_loss.linked_order_ids
        assert stop_loss.id in take_profit.linked_order_ids


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
