"""Integration tests for the subprocess execution runner.

These tests execute actual strategies in subprocesses and verify:
- Log files are created
- Exit codes are correct
- Both frameworks produce compatible output

Note: These tests require the test strategies and data fixtures to exist.
Backtrader tests are skipped if backtrader is not installed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from rustybt.validation.runner import run_backtrader_strategy, run_rustybt_strategy

if TYPE_CHECKING:
    pass


# Check if backtrader is available
try:
    import backtrader  # noqa: F401

    BACKTRADER_AVAILABLE = True
except ImportError:
    BACKTRADER_AVAILABLE = False


@pytest.fixture
def validation_data_fixture() -> Path:
    """Return path to the validation data fixture."""
    fixture_path = Path(__file__).parent / "fixtures" / "validation_data.parquet"
    if not fixture_path.exists():
        pytest.skip(f"Validation data fixture not found: {fixture_path}")
    return fixture_path


class TestRunRustybtStrategyIntegration:
    """Integration tests for run_rustybt_strategy()."""

    def test_executes_simple_strategy(self, tmp_path: Path, validation_data_fixture: Path) -> None:
        """Test executing a simple rustybt strategy."""
        output_log = tmp_path / "rustybt_output.jsonl"

        result = run_rustybt_strategy(
            strategy_module="tests.validation.strategies.rustybt.simple_strategy.SimpleStrategy",
            data_path=validation_data_fixture,
            output_log=output_log,
            timeout=60,
        )

        # Verify execution succeeded
        assert result.returncode == 0, f"Strategy failed: {result.stderr}"

        # Verify log file was created
        assert output_log.exists(), "Log file was not created"

        # Verify log file has content
        assert output_log.stat().st_size > 0, "Log file is empty"

        # Verify log entries are valid JSON
        with open(output_log) as f:
            for line in f:
                entry = json.loads(line)
                assert "timestamp" in entry
                assert "layer" in entry
                assert "event" in entry

    def test_captures_stdout_stderr(self, tmp_path: Path, validation_data_fixture: Path) -> None:
        """Test that stdout and stderr are captured."""
        output_log = tmp_path / "output.jsonl"

        result = run_rustybt_strategy(
            strategy_module="tests.validation.strategies.rustybt.simple_strategy.SimpleStrategy",
            data_path=validation_data_fixture,
            output_log=output_log,
            timeout=60,
        )

        # stdout and stderr should be strings (might be empty)
        assert isinstance(result.stdout, str)
        assert isinstance(result.stderr, str)

    def test_passes_params_to_strategy(self, tmp_path: Path, validation_data_fixture: Path) -> None:
        """Test that params are passed to the strategy."""
        output_log = tmp_path / "output.jsonl"
        params = {"test_param": "test_value"}

        result = run_rustybt_strategy(
            strategy_module="tests.validation.strategies.rustybt.simple_strategy.SimpleStrategy",
            data_path=validation_data_fixture,
            output_log=output_log,
            params=params,
            timeout=60,
        )

        assert result.returncode == 0, f"Strategy failed: {result.stderr}"

    def test_timeout_enforcement(self, tmp_path: Path) -> None:
        """Test that timeout is enforced (this test uses a very short timeout)."""
        # Create a minimal data file
        from datetime import datetime, timedelta

        import polars as pl

        # Create minimal test data
        dates = [datetime(2020, 1, 1) + timedelta(days=i) for i in range(5)]
        data = pl.DataFrame(
            {
                "datetime": dates,
                "open": [100.0] * 5,
                "high": [101.0] * 5,
                "low": [99.0] * 5,
                "close": [100.5] * 5,
                "volume": [1000] * 5,
            }
        )
        data_path = tmp_path / "test_data.parquet"
        data.write_parquet(data_path)

        output_log = tmp_path / "output.jsonl"

        # Run with a reasonable timeout - should succeed
        result = run_rustybt_strategy(
            strategy_module="tests.validation.strategies.rustybt.simple_strategy.SimpleStrategy",
            data_path=data_path,
            output_log=output_log,
            timeout=30,  # 30 seconds should be plenty
        )

        # Should complete successfully
        assert result.returncode == 0, f"Strategy failed: {result.stderr}"


@pytest.mark.skipif(not BACKTRADER_AVAILABLE, reason="Backtrader not installed")
class TestRunBacktraderStrategyIntegration:
    """Integration tests for run_backtrader_strategy()."""

    def test_executes_simple_strategy(self, tmp_path: Path, validation_data_fixture: Path) -> None:
        """Test executing a simple Backtrader strategy."""
        output_log = tmp_path / "backtrader_output.jsonl"

        result = run_backtrader_strategy(
            strategy_module="tests.validation.strategies.bt_strategies.simple_strategy.SimpleStrategy",
            data_path=validation_data_fixture,
            output_log=output_log,
            timeout=60,
        )

        # Verify execution succeeded
        assert (
            result.returncode == 0
        ), f"Strategy failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"

        # Verify log file was created
        assert output_log.exists(), "Log file was not created"

        # Verify log file has content
        assert output_log.stat().st_size > 0, "Log file is empty"

        # Verify log entries are valid JSON
        with open(output_log) as f:
            for line in f:
                entry = json.loads(line)
                assert "timestamp" in entry
                assert "layer" in entry
                assert "event" in entry

    def test_captures_stdout_stderr(self, tmp_path: Path, validation_data_fixture: Path) -> None:
        """Test that stdout and stderr are captured."""
        output_log = tmp_path / "output.jsonl"

        result = run_backtrader_strategy(
            strategy_module="tests.validation.strategies.bt_strategies.simple_strategy.SimpleStrategy",
            data_path=validation_data_fixture,
            output_log=output_log,
            timeout=60,
        )

        assert isinstance(result.stdout, str)
        assert isinstance(result.stderr, str)


@pytest.mark.skipif(not BACKTRADER_AVAILABLE, reason="Backtrader not installed")
class TestDualFrameworkExecution:
    """Integration tests for executing the same logical strategy in both frameworks."""

    @pytest.mark.integration
    def test_dual_execution_produces_logs(
        self, tmp_path: Path, validation_data_fixture: Path
    ) -> None:
        """Test executing a strategy in both frameworks produces log files."""
        rb_log = tmp_path / "rustybt.jsonl"
        bt_log = tmp_path / "backtrader.jsonl"

        # Execute in rustybt
        rb_result = run_rustybt_strategy(
            strategy_module="tests.validation.strategies.rustybt.simple_strategy.SimpleStrategy",
            data_path=validation_data_fixture,
            output_log=rb_log,
            timeout=60,
        )

        # Execute in Backtrader
        bt_result = run_backtrader_strategy(
            strategy_module="tests.validation.strategies.bt_strategies.simple_strategy.SimpleStrategy",
            data_path=validation_data_fixture,
            output_log=bt_log,
            timeout=60,
        )

        # Both should succeed
        assert rb_result.returncode == 0, f"rustybt failed: {rb_result.stderr}"
        assert bt_result.returncode == 0, f"Backtrader failed: {bt_result.stderr}"

        # Both should produce log files
        assert rb_log.exists(), "rustybt log file not created"
        assert bt_log.exists(), "Backtrader log file not created"

        # Both log files should have content
        assert rb_log.stat().st_size > 0, "rustybt log is empty"
        assert bt_log.stat().st_size > 0, "Backtrader log is empty"

    @pytest.mark.integration
    def test_logs_have_compatible_schema(
        self, tmp_path: Path, validation_data_fixture: Path
    ) -> None:
        """Test that both frameworks produce logs with identical schema."""
        rb_log = tmp_path / "rustybt.jsonl"
        bt_log = tmp_path / "backtrader.jsonl"

        # Execute in both frameworks
        run_rustybt_strategy(
            strategy_module="tests.validation.strategies.rustybt.simple_strategy.SimpleStrategy",
            data_path=validation_data_fixture,
            output_log=rb_log,
            timeout=60,
        )

        run_backtrader_strategy(
            strategy_module="tests.validation.strategies.bt_strategies.simple_strategy.SimpleStrategy",
            data_path=validation_data_fixture,
            output_log=bt_log,
            timeout=60,
        )

        # Parse both log files
        def parse_log(path: Path) -> list[dict]:
            entries = []
            with open(path) as f:
                for line in f:
                    entries.append(json.loads(line))
            return entries

        rb_entries = parse_log(rb_log)
        bt_entries = parse_log(bt_log)

        # Both should have entries
        assert len(rb_entries) > 0, "rustybt produced no log entries"
        assert len(bt_entries) > 0, "Backtrader produced no log entries"

        # Check schema compatibility - all entries should have same top-level keys
        # Core fields plus logged_at for debugging
        expected_keys = {"timestamp", "logged_at", "layer", "event", "asset", "data"}

        for entry in rb_entries:
            assert set(entry.keys()) == expected_keys, f"rustybt entry missing keys: {entry.keys()}"

        for entry in bt_entries:
            assert (
                set(entry.keys()) == expected_keys
            ), f"Backtrader entry missing keys: {entry.keys()}"


class TestErrorHandling:
    """Tests for error handling in integration scenarios."""

    def test_nonexistent_strategy_returns_error(
        self, tmp_path: Path, validation_data_fixture: Path
    ) -> None:
        """Test that non-existent strategy returns non-zero exit code."""
        output_log = tmp_path / "output.jsonl"

        result = run_rustybt_strategy(
            strategy_module="nonexistent.module.Strategy",
            data_path=validation_data_fixture,
            output_log=output_log,
            timeout=30,
        )

        assert result.returncode != 0
        assert "could not import" in result.stderr.lower()

    def test_nonexistent_data_file_returns_error(self, tmp_path: Path) -> None:
        """Test that non-existent data file returns non-zero exit code."""
        result = run_rustybt_strategy(
            strategy_module="tests.validation.strategies.rustybt.simple_strategy.SimpleStrategy",
            data_path=Path("/nonexistent/path/data.parquet"),
            output_log=tmp_path / "output.jsonl",
            timeout=30,
        )

        assert result.returncode != 0
        assert "not found" in result.stderr.lower()
