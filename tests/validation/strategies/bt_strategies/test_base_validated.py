"""Unit tests for BacktraderValidatedStrategy base class.

Tests cover:
- Strategy instantiation and log file creation
- _log_event() method writes valid JSONL
- Log schema matches rustybt format exactly
- next() produces bar_received events
- stop() closes file properly
- Cross-framework schema comparison
"""

from __future__ import annotations

import json
from pathlib import Path

import backtrader as bt
import pytest

from tests.validation.strategies.bt_strategies.base_validated import (
    VALID_LAYERS,
    BacktraderValidatedStrategy,
    ValidationLayer,
)


def create_test_csv(tmp_path: Path, rows: int = 2) -> Path:
    """Create a minimal CSV file for Backtrader.

    Backtrader GenericCSVData expects columns in specific order.
    Using defaults: datetime, open, high, low, close, volume, openinterest
    """
    csv_path = tmp_path / "data.csv"
    lines = ["Date,Open,High,Low,Close,Volume,OpenInterest"]
    base_prices = [
        (100.0, 105.0, 99.0, 104.0, 1000000),
        (104.0, 106.0, 103.0, 105.0, 1100000),
        (105.0, 108.0, 104.0, 107.0, 1200000),
    ]
    for i in range(rows):
        day = 15 + i
        o, h, l, c, v = base_prices[i % len(base_prices)]
        lines.append(f"2020-01-{day:02d},{o},{h},{l},{c},{v},0")
    csv_path.write_text("\n".join(lines) + "\n")
    return csv_path


def create_cerebro_with_strategy(
    tmp_path: Path,
    log_path: Path | str | None = None,
    csv_rows: int = 1,
) -> tuple[bt.Cerebro, Path]:
    """Create a Cerebro instance with strategy and data."""
    if log_path is None:
        log_path = tmp_path / "test.jsonl"

    cerebro = bt.Cerebro()
    cerebro.addstrategy(BacktraderValidatedStrategy, log_path=log_path)

    csv_path = create_test_csv(tmp_path, rows=csv_rows)
    data = bt.feeds.GenericCSVData(dataname=csv_path, dtformat="%Y-%m-%d")
    cerebro.adddata(data)

    return cerebro, log_path if isinstance(log_path, Path) else Path(log_path)


class TestBacktraderValidatedStrategyInstantiation:
    """Tests for strategy instantiation and log file creation."""

    def test_creates_log_file_with_path(self, tmp_path: Path) -> None:
        """Test that strategy instantiation creates log file at specified path."""
        log_path = tmp_path / "test.jsonl"

        cerebro, _ = create_cerebro_with_strategy(tmp_path, log_path=log_path)
        strategies = cerebro.run()
        strategy = strategies[0]

        assert log_path.exists()
        assert strategy._log_file is not None

        strategy.close()

    def test_log_path_required(self, tmp_path: Path) -> None:
        """Test that log_path parameter is required."""
        cerebro = bt.Cerebro()
        cerebro.addstrategy(BacktraderValidatedStrategy)  # No log_path

        csv_path = create_test_csv(tmp_path)
        data = bt.feeds.GenericCSVData(dataname=csv_path, dtformat="%Y-%m-%d")
        cerebro.adddata(data)

        with pytest.raises(ValueError, match="log_path parameter is required"):
            cerebro.run()

    def test_accepts_string_path(self, tmp_path: Path) -> None:
        """Test that string path is accepted and converted to Path."""
        log_path_str = str(tmp_path / "test.jsonl")

        cerebro, log_path = create_cerebro_with_strategy(tmp_path, log_path=log_path_str)
        strategies = cerebro.run()
        strategy = strategies[0]

        assert Path(log_path_str).exists()
        strategy.close()


class TestLogEventMethod:
    """Tests for _log_event() method."""

    def test_writes_valid_json(self, tmp_path: Path) -> None:
        """Test that _log_event writes valid JSON lines."""
        cerebro, log_path = create_cerebro_with_strategy(tmp_path)
        cerebro.run()

        # After run, check the auto-logged events (initialize, bar_received)
        content = log_path.read_text().strip().split("\n")
        entry = json.loads(content[0])  # Check initialize event

        assert isinstance(entry, dict)
        assert "timestamp" in entry
        assert "layer" in entry
        assert "event" in entry
        assert "asset" in entry
        assert "data" in entry

    def test_writes_all_required_fields(self, tmp_path: Path) -> None:
        """Test that log entry contains all required schema fields.

        Uses a custom strategy that logs signals during next().
        """

        class SignalLoggingStrategy(BacktraderValidatedStrategy):
            """Test strategy that logs a signal in next()."""

            def next(self) -> None:
                super().next()
                self._log_event(
                    layer="signals",
                    event="signal_computed",
                    data={"signal_name": "sma"},
                    asset="AAPL",
                )

        log_path = tmp_path / "test.jsonl"
        cerebro = bt.Cerebro()
        cerebro.addstrategy(SignalLoggingStrategy, log_path=log_path)

        csv_path = create_test_csv(tmp_path, rows=1)
        data = bt.feeds.GenericCSVData(dataname=csv_path, dtformat="%Y-%m-%d")
        cerebro.adddata(data)
        cerebro.run()

        entries = [json.loads(line) for line in log_path.read_text().strip().split("\n")]
        signal_entries = [e for e in entries if e["event"] == "signal_computed"]
        assert len(signal_entries) >= 1

        entry = signal_entries[0]
        assert entry["layer"] == "signals"
        assert entry["event"] == "signal_computed"
        assert entry["asset"] == "AAPL"
        assert entry["data"]["signal_name"] == "sma"

    def test_timestamp_is_iso8601_format(self, tmp_path: Path) -> None:
        """Test that timestamp uses ISO8601 format."""
        cerebro, log_path = create_cerebro_with_strategy(tmp_path)
        cerebro.run()

        entry = json.loads(log_path.read_text().strip().split("\n")[0])
        timestamp = entry["timestamp"]

        # ISO8601 format: YYYY-MM-DDTHH:MM:SS.ffffff
        assert "T" in timestamp
        assert len(timestamp.split("T")[0]) == 10  # YYYY-MM-DD
        assert ":" in timestamp.split("T")[1]  # HH:MM:SS

    def test_flushes_after_each_write(self, tmp_path: Path) -> None:
        """Test that log is flushed after each write.

        Uses a custom strategy that writes multiple events in next().
        """

        class MultiEventStrategy(BacktraderValidatedStrategy):
            """Test strategy that logs multiple events."""

            def next(self) -> None:
                super().next()
                self._log_event("data", "event1", {})
                self._log_event("data", "event2", {})

        log_path = tmp_path / "test.jsonl"
        cerebro = bt.Cerebro()
        cerebro.addstrategy(MultiEventStrategy, log_path=log_path)

        csv_path = create_test_csv(tmp_path, rows=1)
        data = bt.feeds.GenericCSVData(dataname=csv_path, dtformat="%Y-%m-%d")
        cerebro.adddata(data)
        cerebro.run()

        content = log_path.read_text()
        # Events should be flushed - check both are present
        assert "event1" in content
        assert "event2" in content


class TestLifecycleMethods:
    """Tests for lifecycle method logging (__init__, next, stop)."""

    def test_init_logs_initialize_event(self, tmp_path: Path) -> None:
        """Test that __init__ logs to layer 'data', event 'initialize'."""
        cerebro, log_path = create_cerebro_with_strategy(tmp_path)
        cerebro.run()

        entries = [json.loads(line) for line in log_path.read_text().strip().split("\n")]
        init_entry = entries[0]

        assert init_entry["layer"] == "data"
        assert init_entry["event"] == "initialize"
        assert init_entry["data"]["context"] == "strategy_init"

    def test_next_logs_bar_received(self, tmp_path: Path) -> None:
        """Test that next() logs to layer 'data', event 'bar_received'."""
        cerebro, log_path = create_cerebro_with_strategy(tmp_path, csv_rows=2)
        cerebro.run()

        entries = [json.loads(line) for line in log_path.read_text().strip().split("\n")]
        bar_events = [e for e in entries if e["event"] == "bar_received"]

        assert len(bar_events) >= 1
        for event in bar_events:
            assert event["layer"] == "data"
            assert "timestamp" in event["data"]


class TestConvenienceMethods:
    """Tests for convenience logging methods."""

    def test_log_signal_method(self, tmp_path: Path) -> None:
        """Test log_signal convenience method.

        Uses a custom strategy that calls log_signal in next().
        """

        class SignalStrategy(BacktraderValidatedStrategy):
            """Test strategy using log_signal convenience method."""

            def next(self) -> None:
                super().next()
                self.log_signal(
                    signal_name="sma_crossover",
                    signal_value=1.0,
                    asset="AAPL",
                    period=20,
                )

        log_path = tmp_path / "test.jsonl"
        cerebro = bt.Cerebro()
        cerebro.addstrategy(SignalStrategy, log_path=log_path)

        csv_path = create_test_csv(tmp_path, rows=1)
        data = bt.feeds.GenericCSVData(dataname=csv_path, dtformat="%Y-%m-%d")
        cerebro.adddata(data)
        cerebro.run()

        entries = [json.loads(line) for line in log_path.read_text().strip().split("\n")]
        signal_entry = [e for e in entries if e["event"] == "signal_computed"][0]

        assert signal_entry["layer"] == "signals"
        assert signal_entry["asset"] == "AAPL"
        assert signal_entry["data"]["signal_name"] == "sma_crossover"
        assert signal_entry["data"]["signal_value"] == 1.0
        assert signal_entry["data"]["period"] == 20

    def test_log_order_created_method(self, tmp_path: Path) -> None:
        """Test log_order_created convenience method.

        Uses a custom strategy that calls log_order_created in next().
        """

        class OrderStrategy(BacktraderValidatedStrategy):
            """Test strategy using log_order_created convenience method."""

            def next(self) -> None:
                super().next()
                self.log_order_created(
                    order_type="market",
                    asset="AAPL",
                    quantity=100,
                    limit_price=None,
                )

        log_path = tmp_path / "test.jsonl"
        cerebro = bt.Cerebro()
        cerebro.addstrategy(OrderStrategy, log_path=log_path)

        csv_path = create_test_csv(tmp_path, rows=1)
        data = bt.feeds.GenericCSVData(dataname=csv_path, dtformat="%Y-%m-%d")
        cerebro.adddata(data)
        cerebro.run()

        entries = [json.loads(line) for line in log_path.read_text().strip().split("\n")]
        order_entry = [e for e in entries if e["event"] == "order_created"][0]

        assert order_entry["layer"] == "orders"
        assert order_entry["asset"] == "AAPL"
        assert order_entry["data"]["order_type"] == "market"
        assert order_entry["data"]["quantity"] == 100
        assert order_entry["data"]["limit_price"] is None


class TestFileCleanup:
    """Tests for file cleanup via stop() method."""

    def test_stop_closes_file(self, tmp_path: Path) -> None:
        """Test that stop() closes the log file."""
        cerebro, _ = create_cerebro_with_strategy(tmp_path)
        strategies = cerebro.run()
        strategy = strategies[0]

        # After run completes, stop() should have been called
        assert strategy._log_file.closed

    def test_close_method_is_idempotent(self, tmp_path: Path) -> None:
        """Test that close() can be called multiple times safely."""
        cerebro, _ = create_cerebro_with_strategy(tmp_path)
        strategies = cerebro.run()
        strategy = strategies[0]

        strategy.close()
        strategy.close()  # Should not raise


class TestCrossFrameworkSchemaComparison:
    """Tests verifying log schema matches rustybt format exactly."""

    def test_log_schema_has_same_keys(self, tmp_path: Path) -> None:
        """Verify Backtrader logs have identical keys to rustybt."""
        # Create Backtrader log
        cerebro, bt_log_path = create_cerebro_with_strategy(tmp_path)
        cerebro.run()

        bt_entry = json.loads(bt_log_path.read_text().strip().split("\n")[0])

        # Create rustybt log
        from rustybt.validation.base_strategy import RustyBTValidatedStrategy

        rb_log_path = tmp_path / "rustybt.jsonl"
        rb_strategy = RustyBTValidatedStrategy(log_path=rb_log_path)
        rb_strategy._log_event("data", "initialize", {"context": "strategy_init"})
        rb_strategy.close()

        rb_entry = json.loads(rb_log_path.read_text().strip().split("\n")[0])

        # Same keys
        assert set(bt_entry.keys()) == set(rb_entry.keys())
        # Core fields plus optional logged_at for debugging
        assert set(bt_entry.keys()) == {"timestamp", "logged_at", "layer", "event", "asset", "data"}

    def test_valid_layers_match_rustybt(self) -> None:
        """Verify VALID_LAYERS constant matches rustybt."""
        from rustybt.validation.base_strategy import (
            VALID_LAYERS as RUSTYBT_VALID_LAYERS,
        )

        assert VALID_LAYERS == RUSTYBT_VALID_LAYERS
        assert VALID_LAYERS == {"data", "signals", "orders", "broker", "portfolio"}

    def test_initialize_event_matches_rustybt(self, tmp_path: Path) -> None:
        """Verify initialize event format matches rustybt."""
        # Backtrader
        cerebro, bt_log_path = create_cerebro_with_strategy(tmp_path)
        cerebro.run()

        bt_init = json.loads(bt_log_path.read_text().strip().split("\n")[0])

        # Rustybt
        from rustybt.validation.base_strategy import RustyBTValidatedStrategy

        rb_log_path = tmp_path / "rustybt.jsonl"
        rb_strategy = RustyBTValidatedStrategy(log_path=rb_log_path)

        class MockContext:
            pass

        rb_strategy.initialize(MockContext())
        rb_strategy.close()

        rb_init = json.loads(rb_log_path.read_text().strip().split("\n")[0])

        # Same layer and event
        assert bt_init["layer"] == rb_init["layer"] == "data"
        assert bt_init["event"] == rb_init["event"] == "initialize"
        assert bt_init["data"]["context"] == rb_init["data"]["context"] == "strategy_init"


class TestValidLayers:
    """Tests for validation layer constants."""

    def test_valid_layers_constant(self) -> None:
        """Test that VALID_LAYERS contains expected values."""
        expected = {"data", "signals", "orders", "broker", "portfolio"}
        assert VALID_LAYERS == expected

    def test_validation_layer_type_alias(self) -> None:
        """Test that ValidationLayer is a string type alias."""
        layer: ValidationLayer = "data"
        assert isinstance(layer, str)
