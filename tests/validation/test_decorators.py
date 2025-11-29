"""Unit tests for validation framework decorators.

Tests cover:
- @log_signal decorator functionality
- @log_order decorator functionality
- @log_portfolio decorator functionality
- Decorator chaining
- Exception handling
- Metadata preservation
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from rustybt.validation.decorators import log_broker, log_order, log_portfolio, log_signal


# =============================================================================
# Mock Objects for Testing
# =============================================================================


@dataclass
class MockOrder:
    """Mock order object for testing @log_order."""

    size: float = 100.0
    price: float | None = None

    @property
    def data(self) -> MockData:
        """Return mock data with asset name."""
        return MockData()


@dataclass
class MockData:
    """Mock data object for order's asset name."""

    _name: str = "AAPL"


@dataclass
class MockPosition:
    """Mock position object for testing @log_portfolio."""

    amount: float = 100.0


@dataclass
class MockPortfolio:
    """Mock portfolio object for testing @log_portfolio."""

    portfolio_value: float = 10000.0
    cash: float = 5000.0
    positions: dict[str, MockPosition] | None = None

    def __post_init__(self) -> None:
        if self.positions is None:
            self.positions = {"AAPL": MockPosition(amount=100.0)}


class MockStrategy:
    """Mock strategy class with _log_event for testing decorators.

    This class mimics the interface of ValidatedStrategy base classes
    without requiring actual file I/O.
    """

    def __init__(self) -> None:
        """Initialize with empty event log."""
        self.logged_events: list[dict[str, Any]] = []
        self._portfolio = MockPortfolio()

    def _log_event(self, layer: str, event: str, data: dict[str, Any]) -> None:
        """Record logged event for test assertions."""
        self.logged_events.append({"layer": layer, "event": event, "data": data})

    @property
    def portfolio(self) -> MockPortfolio:
        """Return mock portfolio."""
        return self._portfolio

    @log_signal()
    def compute_signal(self) -> float:
        """Simple signal computation method."""
        return 42.0

    @log_signal()
    def compute_signal_with_args(self, period: int, factor: float = 1.0) -> float:
        """Signal computation with arguments."""
        return period * factor

    @log_signal()
    def failing_signal(self) -> float:
        """Signal that raises an exception."""
        raise ValueError("Signal computation failed")

    @log_order()
    def place_order(self) -> MockOrder:
        """Order placement method."""
        return MockOrder(size=100.0, price=150.0)

    @log_order()
    def place_market_order(self) -> MockOrder:
        """Market order (no limit price)."""
        return MockOrder(size=50.0, price=None)

    @log_order()
    def no_order(self) -> None:
        """Method that returns None (no order created)."""
        return None

    @log_order()
    def failing_order(self) -> MockOrder:
        """Order that raises an exception."""
        raise ValueError("Order creation failed")

    @log_portfolio()
    def update_portfolio(self) -> None:
        """Portfolio update method."""
        pass

    @log_portfolio()
    def failing_portfolio(self) -> None:
        """Portfolio update that raises an exception."""
        raise ValueError("Portfolio update failed")

    @log_signal()
    @log_portfolio()
    def chained_decorators(self) -> float:
        """Method with chained decorators."""
        return 99.0

    @log_broker()
    def on_fill(self, order_id: str, fill_price: float) -> dict[str, Any]:
        """Broker fill event handler."""
        return {"order_id": order_id, "fill_price": fill_price, "status": "filled"}

    @log_broker()
    def on_rejection(self, order_id: str, reason: str) -> None:
        """Broker rejection event handler."""
        pass  # Just acknowledge the rejection

    @log_broker()
    def failing_broker_event(self) -> None:
        """Broker event that raises an exception."""
        raise ValueError("Broker communication failed")


# =============================================================================
# Test Classes
# =============================================================================


class TestLogSignalDecorator:
    """Tests for @log_signal decorator."""

    def test_logs_signal_computed_event(self) -> None:
        """Test that @log_signal logs signal_computed event."""
        strategy = MockStrategy()
        result = strategy.compute_signal()

        assert result == 42.0
        assert len(strategy.logged_events) == 1

        event = strategy.logged_events[0]
        assert event["layer"] == "signals"
        assert event["event"] == "signal_computed"
        assert event["data"]["signal_name"] == "compute_signal"
        assert event["data"]["signal_value"] == 42.0

    def test_captures_method_arguments(self) -> None:
        """Test that arguments are captured in the log."""
        strategy = MockStrategy()
        result = strategy.compute_signal_with_args(20, factor=2.0)

        assert result == 40.0
        event = strategy.logged_events[0]
        assert event["data"]["args"] == ["20"]
        assert event["data"]["kwargs"] == {"factor": "2.0"}

    def test_logs_signal_failed_on_exception(self) -> None:
        """Test that exceptions are logged before re-raising."""
        strategy = MockStrategy()

        with pytest.raises(ValueError, match="Signal computation failed"):
            strategy.failing_signal()

        assert len(strategy.logged_events) == 1
        event = strategy.logged_events[0]
        assert event["layer"] == "signals"
        assert event["event"] == "signal_failed"
        assert event["data"]["signal_name"] == "failing_signal"
        assert event["data"]["error_type"] == "ValueError"
        assert event["data"]["error_message"] == "Signal computation failed"

    def test_preserves_method_metadata(self) -> None:
        """Test that functools.wraps preserves metadata."""
        strategy = MockStrategy()
        assert strategy.compute_signal.__name__ == "compute_signal"
        assert "Simple signal computation" in (strategy.compute_signal.__doc__ or "")

    def test_custom_layer(self) -> None:
        """Test that custom layer can be specified."""

        class CustomLayerStrategy(MockStrategy):
            @log_signal(layer="custom_signals")
            def custom_signal(self) -> float:
                return 1.0

        strategy = CustomLayerStrategy()
        strategy.custom_signal()

        assert strategy.logged_events[0]["layer"] == "custom_signals"


class TestLogOrderDecorator:
    """Tests for @log_order decorator."""

    def test_logs_order_created_event(self) -> None:
        """Test that @log_order logs order_created event."""
        strategy = MockStrategy()
        order = strategy.place_order()

        assert order is not None
        assert len(strategy.logged_events) == 1

        event = strategy.logged_events[0]
        assert event["layer"] == "orders"
        assert event["event"] == "order_created"
        assert event["data"]["order_type"] == "MockOrder"
        assert event["data"]["quantity"] == 100.0
        assert event["data"]["limit_price"] == 150.0

    def test_extracts_asset_name(self) -> None:
        """Test that asset name is extracted from order.data._name."""
        strategy = MockStrategy()
        strategy.place_order()

        event = strategy.logged_events[0]
        assert event["data"]["asset"] == "AAPL"

    def test_handles_none_limit_price(self) -> None:
        """Test that None limit price is handled (market orders)."""
        strategy = MockStrategy()
        strategy.place_market_order()

        event = strategy.logged_events[0]
        assert event["data"]["limit_price"] is None

    def test_does_not_log_when_none_returned(self) -> None:
        """Test that no event is logged when method returns None."""
        strategy = MockStrategy()
        result = strategy.no_order()

        assert result is None
        assert len(strategy.logged_events) == 0

    def test_logs_order_failed_on_exception(self) -> None:
        """Test that exceptions are logged before re-raising."""
        strategy = MockStrategy()

        with pytest.raises(ValueError, match="Order creation failed"):
            strategy.failing_order()

        assert len(strategy.logged_events) == 1
        event = strategy.logged_events[0]
        assert event["layer"] == "orders"
        assert event["event"] == "order_failed"
        assert event["data"]["error_type"] == "ValueError"

    def test_preserves_method_metadata(self) -> None:
        """Test that functools.wraps preserves metadata."""
        strategy = MockStrategy()
        assert strategy.place_order.__name__ == "place_order"
        assert "Order placement" in (strategy.place_order.__doc__ or "")


class TestLogPortfolioDecorator:
    """Tests for @log_portfolio decorator."""

    def test_logs_portfolio_updated_event(self) -> None:
        """Test that @log_portfolio logs portfolio_updated event."""
        strategy = MockStrategy()
        strategy.update_portfolio()

        assert len(strategy.logged_events) == 1

        event = strategy.logged_events[0]
        assert event["layer"] == "portfolio"
        assert event["event"] == "portfolio_updated"
        assert event["data"]["portfolio_value"] == 10000.0
        assert event["data"]["cash"] == 5000.0

    def test_captures_positions(self) -> None:
        """Test that positions are captured in the log."""
        strategy = MockStrategy()
        strategy.update_portfolio()

        event = strategy.logged_events[0]
        assert "positions" in event["data"]
        assert event["data"]["positions"]["AAPL"] == 100.0

    def test_logs_portfolio_update_failed_on_exception(self) -> None:
        """Test that exceptions are logged before re-raising."""
        strategy = MockStrategy()

        with pytest.raises(ValueError, match="Portfolio update failed"):
            strategy.failing_portfolio()

        assert len(strategy.logged_events) == 1
        event = strategy.logged_events[0]
        assert event["layer"] == "portfolio"
        assert event["event"] == "portfolio_update_failed"
        assert event["data"]["error_type"] == "ValueError"

    def test_preserves_method_metadata(self) -> None:
        """Test that functools.wraps preserves metadata."""
        strategy = MockStrategy()
        assert strategy.update_portfolio.__name__ == "update_portfolio"
        assert "Portfolio update" in (strategy.update_portfolio.__doc__ or "")


class TestLogBrokerDecorator:
    """Tests for @log_broker decorator."""

    def test_logs_broker_event(self) -> None:
        """Test that @log_broker logs broker_event event."""
        strategy = MockStrategy()
        result = strategy.on_fill(order_id="12345", fill_price=150.25)

        assert result == {"order_id": "12345", "fill_price": 150.25, "status": "filled"}
        assert len(strategy.logged_events) == 1

        event = strategy.logged_events[0]
        assert event["layer"] == "broker"
        assert event["event"] == "broker_event"
        assert event["data"]["method_name"] == "on_fill"
        # Dict return values should be merged into data
        assert event["data"]["order_id"] == "12345"
        assert event["data"]["fill_price"] == 150.25
        assert event["data"]["status"] == "filled"

    def test_captures_method_arguments(self) -> None:
        """Test that keyword arguments are captured in the log."""
        strategy = MockStrategy()
        strategy.on_rejection(order_id="12346", reason="Insufficient funds")

        event = strategy.logged_events[0]
        # Method called with keyword args, so args is empty and kwargs has the values
        assert event["data"]["args"] == []
        assert event["data"]["kwargs"]["order_id"] == repr("12346")
        assert event["data"]["kwargs"]["reason"] == repr("Insufficient funds")

    def test_logs_broker_event_failed_on_exception(self) -> None:
        """Test that exceptions are logged before re-raising."""
        strategy = MockStrategy()

        with pytest.raises(ValueError, match="Broker communication failed"):
            strategy.failing_broker_event()

        assert len(strategy.logged_events) == 1
        event = strategy.logged_events[0]
        assert event["layer"] == "broker"
        assert event["event"] == "broker_event_failed"
        assert event["data"]["method_name"] == "failing_broker_event"
        assert event["data"]["error_type"] == "ValueError"
        assert event["data"]["error_message"] == "Broker communication failed"

    def test_preserves_method_metadata(self) -> None:
        """Test that functools.wraps preserves metadata."""
        strategy = MockStrategy()
        assert strategy.on_fill.__name__ == "on_fill"
        assert "Broker fill event" in (strategy.on_fill.__doc__ or "")

    def test_custom_layer(self) -> None:
        """Test that custom layer can be specified."""

        class CustomLayerStrategy(MockStrategy):
            @log_broker(layer="custom_broker")
            def custom_broker_event(self) -> str:
                return "done"

        strategy = CustomLayerStrategy()
        strategy.custom_broker_event()

        assert strategy.logged_events[0]["layer"] == "custom_broker"

    def test_none_return_no_result_in_data(self) -> None:
        """Test that None return value doesn't add result to data."""
        strategy = MockStrategy()
        result = strategy.on_rejection(order_id="12346", reason="Margin call")

        assert result is None
        event = strategy.logged_events[0]
        assert "result" not in event["data"]


class TestDecoratorChaining:
    """Tests for chaining multiple decorators."""

    def test_chained_decorators_log_multiple_events(self) -> None:
        """Test that chained decorators produce multiple log events."""
        strategy = MockStrategy()
        result = strategy.chained_decorators()

        assert result == 99.0
        # Both decorators should log events
        assert len(strategy.logged_events) == 2

        # First event should be from @log_portfolio (innermost decorator runs first)
        # then @log_signal wraps it
        events_by_layer = {e["layer"]: e for e in strategy.logged_events}
        assert "signals" in events_by_layer
        assert "portfolio" in events_by_layer

    def test_chained_decorators_preserve_return_value(self) -> None:
        """Test that return value is preserved through chain."""
        strategy = MockStrategy()
        result = strategy.chained_decorators()

        assert result == 99.0


class TestDecoratorWithRealStrategy:
    """Integration tests with real ValidatedStrategy classes."""

    def test_with_rustybt_strategy(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test decorators work with RustyBTValidatedStrategy."""
        from rustybt.validation.base_strategy import RustyBTValidatedStrategy

        class TestStrategy(RustyBTValidatedStrategy):
            @log_signal()
            def compute_indicator(self) -> float:
                return 3.14

        log_path = tmp_path / "test.jsonl"  # type: ignore[operator]
        strategy = TestStrategy(log_path=log_path)
        result = strategy.compute_indicator()
        strategy.close()

        assert result == 3.14

        # Read and verify log
        import json

        lines = log_path.read_text().strip().split("\n")  # type: ignore[union-attr]
        # Should have initialize event + signal_computed event
        signal_events = [json.loads(line) for line in lines if "signal_computed" in line]
        assert len(signal_events) == 1
        assert signal_events[0]["data"]["signal_name"] == "compute_indicator"
        assert signal_events[0]["data"]["signal_value"] == 3.14


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_signal_with_none_return(self) -> None:
        """Test that None signal values are logged correctly."""

        class NoneSignalStrategy(MockStrategy):
            @log_signal()
            def null_signal(self) -> None:
                return None

        strategy = NoneSignalStrategy()
        result = strategy.null_signal()

        assert result is None
        assert strategy.logged_events[0]["data"]["signal_value"] is None

    def test_order_with_minimal_attributes(self) -> None:
        """Test @log_order with order object missing some attributes."""

        class MinimalOrder:
            pass

        class MinimalOrderStrategy(MockStrategy):
            @log_order()
            def minimal_order(self) -> MinimalOrder:
                return MinimalOrder()

        strategy = MinimalOrderStrategy()
        strategy.minimal_order()

        event = strategy.logged_events[0]
        assert event["data"]["order_type"] == "MinimalOrder"
        # Should not raise, missing attributes just won't be included

    def test_portfolio_without_portfolio_attr(self) -> None:
        """Test @log_portfolio with strategy missing portfolio attribute."""

        class NoPortfolioStrategy:
            def __init__(self) -> None:
                self.logged_events: list[dict[str, Any]] = []

            def _log_event(self, layer: str, event: str, data: dict[str, Any]) -> None:
                self.logged_events.append({"layer": layer, "event": event, "data": data})

            @log_portfolio()
            def update(self) -> None:
                pass

        strategy = NoPortfolioStrategy()
        strategy.update()

        # Should still log, just without portfolio details
        assert len(strategy.logged_events) == 1
        assert strategy.logged_events[0]["event"] == "portfolio_updated"

    def test_arguments_with_complex_types(self) -> None:
        """Test that complex argument types are serialized safely."""

        class ComplexArgsStrategy(MockStrategy):
            @log_signal()
            def complex_args(self, data: dict[str, int], items: list[str]) -> float:
                return float(len(data) + len(items))

        strategy = ComplexArgsStrategy()
        strategy.complex_args({"a": 1, "b": 2}, ["x", "y", "z"])

        event = strategy.logged_events[0]
        # Args should be serialized as strings
        assert isinstance(event["data"]["args"][0], str)
        assert isinstance(event["data"]["args"][1], str)
