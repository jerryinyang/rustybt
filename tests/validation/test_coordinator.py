"""Tests for coordinator module - dual framework execution."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch
import subprocess

import pytest

from rustybt.validation.coordinator import ExecutionResult, execute_dual
from rustybt.validation.models import Session
from datetime import datetime


class TestExecutionResult:
    """Tests for ExecutionResult dataclass."""

    def test_success_property_all_true(self) -> None:
        """Test success property when all conditions are met."""
        result = ExecutionResult(
            rustybt_success=True,
            backtrader_success=True,
            rustybt_log=Path("/tmp/rb.jsonl"),
            backtrader_log=Path("/tmp/bt.jsonl"),
            rustybt_log_valid=True,
            backtrader_log_valid=True,
        )
        assert result.success

    def test_success_property_rustybt_failed(self) -> None:
        """Test success is False when rustybt execution failed."""
        result = ExecutionResult(
            rustybt_success=False,
            backtrader_success=True,
            rustybt_log=Path("/tmp/rb.jsonl"),
            backtrader_log=Path("/tmp/bt.jsonl"),
            rustybt_log_valid=True,
            backtrader_log_valid=True,
        )
        assert not result.success

    def test_success_property_backtrader_failed(self) -> None:
        """Test success is False when Backtrader execution failed."""
        result = ExecutionResult(
            rustybt_success=True,
            backtrader_success=False,
            rustybt_log=Path("/tmp/rb.jsonl"),
            backtrader_log=Path("/tmp/bt.jsonl"),
            rustybt_log_valid=True,
            backtrader_log_valid=True,
        )
        assert not result.success

    def test_success_property_rustybt_log_invalid(self) -> None:
        """Test success is False when rustybt log is invalid."""
        result = ExecutionResult(
            rustybt_success=True,
            backtrader_success=True,
            rustybt_log=Path("/tmp/rb.jsonl"),
            backtrader_log=Path("/tmp/bt.jsonl"),
            rustybt_log_valid=False,
            backtrader_log_valid=True,
        )
        assert not result.success

    def test_success_property_backtrader_log_invalid(self) -> None:
        """Test success is False when Backtrader log is invalid."""
        result = ExecutionResult(
            rustybt_success=True,
            backtrader_success=True,
            rustybt_log=Path("/tmp/rb.jsonl"),
            backtrader_log=Path("/tmp/bt.jsonl"),
            rustybt_log_valid=True,
            backtrader_log_valid=False,
        )
        assert not result.success

    def test_str_success(self) -> None:
        """Test string representation of successful result."""
        result = ExecutionResult(
            rustybt_success=True,
            backtrader_success=True,
            rustybt_log=Path("/tmp/rb.jsonl"),
            backtrader_log=Path("/tmp/bt.jsonl"),
            rustybt_log_valid=True,
            backtrader_log_valid=True,
        )
        assert str(result) == "✓ Both frameworks executed successfully"

    def test_str_rustybt_failed(self) -> None:
        """Test string representation when rustybt failed."""
        result = ExecutionResult(
            rustybt_success=False,
            backtrader_success=True,
            rustybt_log=Path("/tmp/rb.jsonl"),
            backtrader_log=Path("/tmp/bt.jsonl"),
            rustybt_log_valid=True,
            backtrader_log_valid=True,
        )
        assert "rustybt execution failed" in str(result)

    def test_str_multiple_failures(self) -> None:
        """Test string representation with multiple failures."""
        result = ExecutionResult(
            rustybt_success=False,
            backtrader_success=False,
            rustybt_log=Path("/tmp/rb.jsonl"),
            backtrader_log=Path("/tmp/bt.jsonl"),
            rustybt_log_valid=False,
            backtrader_log_valid=False,
        )
        output = str(result)
        assert "rustybt execution failed" in output
        assert "Backtrader execution failed" in output
        assert "rustybt log invalid" in output
        assert "Backtrader log invalid" in output

    def test_errors_default_empty(self) -> None:
        """Test errors list defaults to empty."""
        result = ExecutionResult(
            rustybt_success=True,
            backtrader_success=True,
            rustybt_log=Path("/tmp/rb.jsonl"),
            backtrader_log=Path("/tmp/bt.jsonl"),
            rustybt_log_valid=True,
            backtrader_log_valid=True,
        )
        assert result.errors == []


class TestExecuteDual:
    """Tests for execute_dual function."""

    @pytest.fixture
    def mock_session(self, tmp_path: Path) -> Session:
        """Create a mock session for testing."""
        data_fixture = tmp_path / "fixture.parquet"
        data_fixture.touch()
        return Session(
            id="test-session-123",
            created_at=datetime.now(),
            strategy_name="test_strategy",
            rustybt_version="0.3.4",
            backtrader_version="1.9.78",
            python_version="3.12.0",
            status="IN_PROGRESS",
            data_fixture=data_fixture,
        )

    def test_execute_dual_creates_logs_dir(
        self, mock_session: Session, tmp_path: Path
    ) -> None:
        """Test that execute_dual creates logs directory under session."""
        import json

        # Create mock log files that will be "created" by runners
        logs_dir = tmp_path / mock_session.id / "logs"

        # Mock runners to create valid log files
        def mock_run_rustybt(*args, **kwargs):
            logs_dir.mkdir(parents=True, exist_ok=True)
            log_file = logs_dir / "rustybt.jsonl"
            with open(log_file, "w") as f:
                f.write(
                    json.dumps(
                        {"timestamp": "2020-01-01", "layer": "data", "event": "test"}
                    )
                    + "\n"
                )
            return MagicMock(returncode=0, stderr="")

        def mock_run_backtrader(*args, **kwargs):
            log_file = logs_dir / "backtrader.jsonl"
            with open(log_file, "w") as f:
                f.write(
                    json.dumps(
                        {"timestamp": "2020-01-01", "layer": "data", "event": "test"}
                    )
                    + "\n"
                )
            return MagicMock(returncode=0, stderr="")

        with patch(
            "rustybt.validation.coordinator.run_rustybt_strategy", mock_run_rustybt
        ):
            with patch(
                "rustybt.validation.coordinator.run_backtrader_strategy",
                mock_run_backtrader,
            ):
                result = execute_dual(
                    session=mock_session,
                    strategy_name="test_strategy",
                    rustybt_module="test.rb",
                    backtrader_module="test.bt",
                    sessions_dir=tmp_path,
                )

        assert logs_dir.exists()
        assert result.rustybt_log.exists()
        assert result.backtrader_log.exists()

    def test_execute_dual_success(
        self, mock_session: Session, tmp_path: Path
    ) -> None:
        """Test successful dual execution."""
        import json

        logs_dir = tmp_path / mock_session.id / "logs"

        def mock_run_rustybt(*args, **kwargs):
            logs_dir.mkdir(parents=True, exist_ok=True)
            log_file = logs_dir / "rustybt.jsonl"
            with open(log_file, "w") as f:
                f.write(
                    json.dumps(
                        {"timestamp": "2020-01-01", "layer": "data", "event": "test"}
                    )
                    + "\n"
                )
            return MagicMock(returncode=0, stderr="")

        def mock_run_backtrader(*args, **kwargs):
            log_file = logs_dir / "backtrader.jsonl"
            with open(log_file, "w") as f:
                f.write(
                    json.dumps(
                        {"timestamp": "2020-01-01", "layer": "data", "event": "test"}
                    )
                    + "\n"
                )
            return MagicMock(returncode=0, stderr="")

        with patch(
            "rustybt.validation.coordinator.run_rustybt_strategy", mock_run_rustybt
        ):
            with patch(
                "rustybt.validation.coordinator.run_backtrader_strategy",
                mock_run_backtrader,
            ):
                result = execute_dual(
                    session=mock_session,
                    strategy_name="test_strategy",
                    rustybt_module="test.rb",
                    backtrader_module="test.bt",
                    sessions_dir=tmp_path,
                )

        assert result.success
        assert result.rustybt_success
        assert result.backtrader_success
        assert result.rustybt_log_valid
        assert result.backtrader_log_valid
        assert len(result.errors) == 0

    def test_execute_dual_rustybt_failure(
        self, mock_session: Session, tmp_path: Path
    ) -> None:
        """Test handling of rustybt execution failure."""
        logs_dir = tmp_path / mock_session.id / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        def mock_run_rustybt(*args, **kwargs):
            return MagicMock(returncode=1, stderr="ImportError: no module")

        def mock_run_backtrader(*args, **kwargs):
            import json

            log_file = logs_dir / "backtrader.jsonl"
            with open(log_file, "w") as f:
                f.write(
                    json.dumps(
                        {"timestamp": "2020-01-01", "layer": "data", "event": "test"}
                    )
                    + "\n"
                )
            return MagicMock(returncode=0, stderr="")

        with patch(
            "rustybt.validation.coordinator.run_rustybt_strategy", mock_run_rustybt
        ):
            with patch(
                "rustybt.validation.coordinator.run_backtrader_strategy",
                mock_run_backtrader,
            ):
                result = execute_dual(
                    session=mock_session,
                    strategy_name="test_strategy",
                    rustybt_module="test.rb",
                    backtrader_module="test.bt",
                    sessions_dir=tmp_path,
                )

        assert not result.success
        assert not result.rustybt_success
        assert result.backtrader_success
        assert any("rustybt execution failed" in e for e in result.errors)

    def test_execute_dual_invalid_log(
        self, mock_session: Session, tmp_path: Path
    ) -> None:
        """Test handling of invalid log schema."""
        logs_dir = tmp_path / mock_session.id / "logs"

        def mock_run_rustybt(*args, **kwargs):
            logs_dir.mkdir(parents=True, exist_ok=True)
            log_file = logs_dir / "rustybt.jsonl"
            # Create invalid log (missing required fields)
            with open(log_file, "w") as f:
                f.write('{"bad": "data"}\n')
            return MagicMock(returncode=0, stderr="")

        def mock_run_backtrader(*args, **kwargs):
            import json

            log_file = logs_dir / "backtrader.jsonl"
            with open(log_file, "w") as f:
                f.write(
                    json.dumps(
                        {"timestamp": "2020-01-01", "layer": "data", "event": "test"}
                    )
                    + "\n"
                )
            return MagicMock(returncode=0, stderr="")

        with patch(
            "rustybt.validation.coordinator.run_rustybt_strategy", mock_run_rustybt
        ):
            with patch(
                "rustybt.validation.coordinator.run_backtrader_strategy",
                mock_run_backtrader,
            ):
                result = execute_dual(
                    session=mock_session,
                    strategy_name="test_strategy",
                    rustybt_module="test.rb",
                    backtrader_module="test.bt",
                    sessions_dir=tmp_path,
                )

        assert not result.success
        assert result.rustybt_success  # Execution succeeded
        assert not result.rustybt_log_valid  # But log is invalid
        assert any("rustybt log:" in e for e in result.errors)

    def test_execute_dual_log_not_created(
        self, mock_session: Session, tmp_path: Path
    ) -> None:
        """Test handling when log file is not created."""
        logs_dir = tmp_path / mock_session.id / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        def mock_run_rustybt(*args, **kwargs):
            # Don't create log file
            return MagicMock(returncode=0, stderr="")

        def mock_run_backtrader(*args, **kwargs):
            # Don't create log file
            return MagicMock(returncode=0, stderr="")

        with patch(
            "rustybt.validation.coordinator.run_rustybt_strategy", mock_run_rustybt
        ):
            with patch(
                "rustybt.validation.coordinator.run_backtrader_strategy",
                mock_run_backtrader,
            ):
                result = execute_dual(
                    session=mock_session,
                    strategy_name="test_strategy",
                    rustybt_module="test.rb",
                    backtrader_module="test.bt",
                    sessions_dir=tmp_path,
                )

        assert not result.success
        assert any("rustybt log file not created" in e for e in result.errors)
        assert any("Backtrader log file not created" in e for e in result.errors)
