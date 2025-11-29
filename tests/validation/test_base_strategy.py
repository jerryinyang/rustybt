"""Unit tests for RustyBTValidatedStrategy base class.

Tests cover:
- Strategy instantiation and log file creation
- _log_event() method writes valid JSONL
- Lifecycle methods (initialize, handle_data) produce expected events
- File cleanup on strategy deletion and context manager usage
- Log schema validation
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from rustybt.validation.base_strategy import (
    VALID_LAYERS,
    RustyBTValidatedStrategy,
    ValidationLayer,
)


class MockContext:
    """Mock context object for testing."""

    def __init__(self) -> None:
        self.current_dt = "2020-01-15T09:30:00"


class MockData:
    """Mock data object for testing."""

    pass


class TestRustyBTValidatedStrategyInstantiation:
    """Tests for strategy instantiation and log file creation."""

    def test_creates_log_file(self, tmp_path: Path) -> None:
        """Test that strategy instantiation creates log file at specified path."""
        log_path = tmp_path / "test.jsonl"
        strategy = RustyBTValidatedStrategy(log_path=log_path)

        assert log_path.exists()
        assert strategy._log_path == log_path
        assert strategy._log_file is not None
        assert not strategy._log_file.closed

        strategy.close()

    def test_log_path_must_be_path_object(self, tmp_path: Path) -> None:
        """Test that log_path parameter must be a Path object."""
        with pytest.raises(TypeError, match="log_path must be a Path"):
            RustyBTValidatedStrategy(log_path=str(tmp_path / "test.jsonl"))  # type: ignore

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        """Test that existing log file is overwritten."""
        log_path = tmp_path / "test.jsonl"
        log_path.write_text("existing content\n")

        strategy = RustyBTValidatedStrategy(log_path=log_path)
        strategy._log_event("data", "test", {"key": "value"})
        strategy.close()

        content = log_path.read_text()
        assert "existing content" not in content
        assert "test" in content


class TestLogEventMethod:
    """Tests for _log_event() method."""

    def test_writes_valid_json(self, tmp_path: Path) -> None:
        """Test that _log_event writes valid JSON lines."""
        log_path = tmp_path / "test.jsonl"
        strategy = RustyBTValidatedStrategy(log_path=log_path)

        strategy._log_event("data", "test_event", {"key": "value"})
        strategy.close()

        content = log_path.read_text().strip()
        entry = json.loads(content)

        assert isinstance(entry, dict)
        assert "timestamp" in entry
        assert "layer" in entry
        assert "event" in entry
        assert "asset" in entry
        assert "data" in entry

    def test_writes_all_required_fields(self, tmp_path: Path) -> None:
        """Test that log entry contains all required schema fields."""
        log_path = tmp_path / "test.jsonl"
        strategy = RustyBTValidatedStrategy(log_path=log_path)

        strategy._log_event(
            layer="signals",
            event="signal_computed",
            data={"signal_name": "sma"},
            asset="AAPL",
        )
        strategy.close()

        entry = json.loads(log_path.read_text().strip())

        assert entry["layer"] == "signals"
        assert entry["event"] == "signal_computed"
        assert entry["asset"] == "AAPL"
        assert entry["data"]["signal_name"] == "sma"

    def test_timestamp_is_iso8601_format(self, tmp_path: Path) -> None:
        """Test that timestamp uses ISO8601 format."""
        log_path = tmp_path / "test.jsonl"
        strategy = RustyBTValidatedStrategy(log_path=log_path)

        strategy._log_event("data", "test", {})
        strategy.close()

        entry = json.loads(log_path.read_text().strip())
        timestamp = entry["timestamp"]

        # ISO8601 format: YYYY-MM-DDTHH:MM:SS.fff (milliseconds precision)
        assert "T" in timestamp
        assert len(timestamp.split("T")[0]) == 10  # YYYY-MM-DD
        assert ":" in timestamp.split("T")[1]  # HH:MM:SS

    def test_timestamp_has_milliseconds_precision(self, tmp_path: Path) -> None:
        """Test that timestamp uses milliseconds precision (3 decimal places)."""
        log_path = tmp_path / "test.jsonl"
        strategy = RustyBTValidatedStrategy(log_path=log_path)

        strategy._log_event("data", "test", {})
        strategy.close()

        entry = json.loads(log_path.read_text().strip())
        timestamp = entry["timestamp"]

        # Check that timestamp has exactly 3 decimal places (milliseconds)
        # Format: YYYY-MM-DDTHH:MM:SS.fff
        assert "." in timestamp
        decimal_part = timestamp.split(".")[-1]
        assert len(decimal_part) == 3, f"Expected 3 decimal places, got {len(decimal_part)}: {timestamp}"

    def test_flushes_after_each_write(self, tmp_path: Path) -> None:
        """Test that log is flushed after each write."""
        log_path = tmp_path / "test.jsonl"
        strategy = RustyBTValidatedStrategy(log_path=log_path)

        strategy._log_event("data", "event1", {})

        # File should be readable without closing
        content = log_path.read_text()
        assert "event1" in content

        strategy._log_event("data", "event2", {})
        content = log_path.read_text()
        assert "event2" in content

        strategy.close()

    def test_asset_extracted_from_data_if_not_provided(self, tmp_path: Path) -> None:
        """Test that asset is extracted from data dict if not explicitly provided."""
        log_path = tmp_path / "test.jsonl"
        strategy = RustyBTValidatedStrategy(log_path=log_path)

        strategy._log_event("signals", "signal_computed", {"asset": "GOOG"})
        strategy.close()

        entry = json.loads(log_path.read_text().strip())
        assert entry["asset"] == "GOOG"

    def test_explicit_asset_overrides_data_asset(self, tmp_path: Path) -> None:
        """Test that explicit asset parameter takes precedence."""
        log_path = tmp_path / "test.jsonl"
        strategy = RustyBTValidatedStrategy(log_path=log_path)

        strategy._log_event(
            "signals", "signal_computed", {"asset": "GOOG"}, asset="AAPL"
        )
        strategy.close()

        entry = json.loads(log_path.read_text().strip())
        assert entry["asset"] == "AAPL"

    def test_handles_closed_file_gracefully(self, tmp_path: Path) -> None:
        """Test that _log_event handles closed file without error."""
        log_path = tmp_path / "test.jsonl"
        strategy = RustyBTValidatedStrategy(log_path=log_path)

        strategy.close()

        # Should not raise an exception
        strategy._log_event("data", "test", {})


class TestLifecycleMethods:
    """Tests for lifecycle method logging (initialize, handle_data)."""

    def test_initialize_logs_to_data_layer(self, tmp_path: Path) -> None:
        """Test that initialize() logs to layer 'data', event 'initialize'."""
        log_path = tmp_path / "test.jsonl"
        strategy = RustyBTValidatedStrategy(log_path=log_path)

        context = MockContext()
        strategy.initialize(context)
        strategy.close()

        entry = json.loads(log_path.read_text().strip())

        assert entry["layer"] == "data"
        assert entry["event"] == "initialize"
        assert entry["data"]["context"] == "strategy_init"

    def test_handle_data_logs_bar_received(self, tmp_path: Path) -> None:
        """Test that handle_data() logs to layer 'data', event 'bar_received'."""
        log_path = tmp_path / "test.jsonl"
        strategy = RustyBTValidatedStrategy(log_path=log_path)

        context = MockContext()
        data = MockData()
        strategy.handle_data(context, data)
        strategy.close()

        entry = json.loads(log_path.read_text().strip())

        assert entry["layer"] == "data"
        assert entry["event"] == "bar_received"
        assert "timestamp" in entry["data"]

    def test_handle_data_includes_context_timestamp(self, tmp_path: Path) -> None:
        """Test that handle_data includes timestamp from context."""
        log_path = tmp_path / "test.jsonl"
        strategy = RustyBTValidatedStrategy(log_path=log_path)

        context = MockContext()
        context.current_dt = "2020-01-15T09:30:00"
        strategy.handle_data(context, MockData())
        strategy.close()

        entry = json.loads(log_path.read_text().strip())
        assert entry["data"]["timestamp"] == "2020-01-15T09:30:00"


class TestConvenienceMethods:
    """Tests for convenience logging methods."""

    def test_log_signal_method(self, tmp_path: Path) -> None:
        """Test log_signal convenience method."""
        log_path = tmp_path / "test.jsonl"
        strategy = RustyBTValidatedStrategy(log_path=log_path)

        strategy.log_signal(
            signal_name="sma_crossover",
            signal_value=1.0,
            asset="AAPL",
            period=20,
        )
        strategy.close()

        entry = json.loads(log_path.read_text().strip())

        assert entry["layer"] == "signals"
        assert entry["event"] == "signal_computed"
        assert entry["asset"] == "AAPL"
        assert entry["data"]["signal_name"] == "sma_crossover"
        assert entry["data"]["signal_value"] == 1.0
        assert entry["data"]["period"] == 20

    def test_log_order_created_method(self, tmp_path: Path) -> None:
        """Test log_order_created convenience method."""
        log_path = tmp_path / "test.jsonl"
        strategy = RustyBTValidatedStrategy(log_path=log_path)

        strategy.log_order_created(
            order_type="market",
            asset="AAPL",
            quantity=100,
            limit_price=None,
        )
        strategy.close()

        entry = json.loads(log_path.read_text().strip())

        assert entry["layer"] == "orders"
        assert entry["event"] == "order_created"
        assert entry["asset"] == "AAPL"
        assert entry["data"]["order_type"] == "market"
        assert entry["data"]["quantity"] == 100
        assert entry["data"]["limit_price"] is None

    def test_log_broker_event_method(self, tmp_path: Path) -> None:
        """Test log_broker_event convenience method."""
        log_path = tmp_path / "test.jsonl"
        strategy = RustyBTValidatedStrategy(log_path=log_path)

        strategy.log_broker_event(
            event="fill_executed",
            asset="AAPL",
            order_id="12345",
            fill_price=150.25,
            fill_quantity=100,
            commission=1.00,
        )
        strategy.close()

        entry = json.loads(log_path.read_text().strip())

        assert entry["layer"] == "broker"
        assert entry["event"] == "fill_executed"
        assert entry["asset"] == "AAPL"
        assert entry["data"]["order_id"] == "12345"
        assert entry["data"]["fill_price"] == 150.25
        assert entry["data"]["fill_quantity"] == 100
        assert entry["data"]["commission"] == 1.00

    def test_log_broker_event_rejection(self, tmp_path: Path) -> None:
        """Test log_broker_event with rejection event."""
        log_path = tmp_path / "test.jsonl"
        strategy = RustyBTValidatedStrategy(log_path=log_path)

        strategy.log_broker_event(
            event="order_rejected",
            asset="GOOG",
            order_id="12346",
            reason="Insufficient funds",
        )
        strategy.close()

        entry = json.loads(log_path.read_text().strip())

        assert entry["layer"] == "broker"
        assert entry["event"] == "order_rejected"
        assert entry["asset"] == "GOOG"
        assert entry["data"]["order_id"] == "12346"
        assert entry["data"]["reason"] == "Insufficient funds"


class TestFileCleanup:
    """Tests for file cleanup and resource management."""

    def test_close_method_closes_file(self, tmp_path: Path) -> None:
        """Test that close() method closes the log file."""
        log_path = tmp_path / "test.jsonl"
        strategy = RustyBTValidatedStrategy(log_path=log_path)

        assert not strategy._log_file.closed
        strategy.close()
        assert strategy._log_file.closed

    def test_close_is_idempotent(self, tmp_path: Path) -> None:
        """Test that close() can be called multiple times safely."""
        log_path = tmp_path / "test.jsonl"
        strategy = RustyBTValidatedStrategy(log_path=log_path)

        strategy.close()
        strategy.close()  # Should not raise

    def test_del_closes_file(self, tmp_path: Path) -> None:
        """Test that __del__ closes the log file."""
        log_path = tmp_path / "test.jsonl"
        strategy = RustyBTValidatedStrategy(log_path=log_path)
        log_file = strategy._log_file

        del strategy

        assert log_file.closed

    def test_context_manager_closes_file(self, tmp_path: Path) -> None:
        """Test that context manager properly closes the file."""
        log_path = tmp_path / "test.jsonl"

        with RustyBTValidatedStrategy(log_path=log_path) as strategy:
            strategy._log_event("data", "test", {})
            log_file = strategy._log_file

        assert log_file.closed

    def test_context_manager_closes_on_exception(self, tmp_path: Path) -> None:
        """Test that context manager closes file even on exception."""
        log_path = tmp_path / "test.jsonl"
        log_file: Any = None

        with pytest.raises(ValueError):
            with RustyBTValidatedStrategy(log_path=log_path) as strategy:
                log_file = strategy._log_file
                raise ValueError("Test exception")

        assert log_file is not None
        assert log_file.closed


class TestMultipleEvents:
    """Tests for handling multiple events."""

    def test_multiple_events_append_correctly(self, tmp_path: Path) -> None:
        """Test that multiple events are appended as separate lines."""
        log_path = tmp_path / "test.jsonl"
        strategy = RustyBTValidatedStrategy(log_path=log_path)

        strategy._log_event("data", "event1", {"index": 1})
        strategy._log_event("signals", "event2", {"index": 2})
        strategy._log_event("orders", "event3", {"index": 3})
        strategy.close()

        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 3

        entries = [json.loads(line) for line in lines]
        assert entries[0]["event"] == "event1"
        assert entries[1]["event"] == "event2"
        assert entries[2]["event"] == "event3"

    def test_events_preserve_order(self, tmp_path: Path) -> None:
        """Test that events are logged in order."""
        log_path = tmp_path / "test.jsonl"
        strategy = RustyBTValidatedStrategy(log_path=log_path)

        for i in range(10):
            strategy._log_event("data", f"event_{i}", {"index": i})
        strategy.close()

        lines = log_path.read_text().strip().split("\n")
        entries = [json.loads(line) for line in lines]

        for i, entry in enumerate(entries):
            assert entry["data"]["index"] == i


class TestValidLayers:
    """Tests for validation layer constants."""

    def test_valid_layers_constant(self) -> None:
        """Test that VALID_LAYERS contains expected values."""
        expected = {"data", "signals", "orders", "broker", "portfolio"}
        assert VALID_LAYERS == expected

    def test_validation_layer_type_alias(self) -> None:
        """Test that ValidationLayer is a string type alias."""
        # ValidationLayer is just a type alias for str
        layer: ValidationLayer = "data"
        assert isinstance(layer, str)
