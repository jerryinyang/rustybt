"""Unit tests for the subprocess execution runner.

Tests cover:
- Command construction for both runner functions
- Timeout parameter handling
- Params serialization
- Mocked subprocess execution

Note: Integration tests with actual strategy execution are in test_runner_integration.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from rustybt.validation.runner import (
    DEFAULT_TIMEOUT,
    run_backtrader_strategy,
    run_rustybt_strategy,
)

if TYPE_CHECKING:
    pass


class TestRunRustybtStrategy:
    """Tests for run_rustybt_strategy() function."""

    @patch("subprocess.run")
    def test_builds_correct_command_basic(self, mock_run: MagicMock) -> None:
        """Test that the command is constructed correctly without params."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        run_rustybt_strategy(
            strategy_module="test.module.Strategy",
            data_path=Path("/data/test.parquet"),
            output_log=Path("/logs/test.jsonl"),
        )

        # Verify subprocess.run was called
        mock_run.assert_called_once()

        # Get the command list
        call_args = mock_run.call_args
        cmd = call_args[0][0]  # First positional arg is the command list

        # Verify command structure
        assert cmd[0] == sys.executable
        assert "-m" in cmd
        assert "rustybt.validation.execute_rustybt" in cmd
        assert "--strategy" in cmd
        assert "test.module.Strategy" in cmd
        assert "--data" in cmd
        assert "/data/test.parquet" in cmd
        assert "--output" in cmd
        assert "/logs/test.jsonl" in cmd

    @patch("subprocess.run")
    def test_builds_command_with_params(self, mock_run: MagicMock) -> None:
        """Test that params are JSON serialized and added to command."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        params = {"sma_period": 20, "threshold": 0.05}

        run_rustybt_strategy(
            strategy_module="test.module.Strategy",
            data_path=Path("/data/test.parquet"),
            output_log=Path("/logs/test.jsonl"),
            params=params,
        )

        cmd = mock_run.call_args[0][0]

        # Verify params are included
        assert "--params" in cmd
        params_idx = cmd.index("--params")
        params_json = cmd[params_idx + 1]

        # Verify JSON serialization
        parsed = json.loads(params_json)
        assert parsed == params

    @patch("subprocess.run")
    def test_uses_default_timeout(self, mock_run: MagicMock) -> None:
        """Test that default timeout is used when not specified."""
        mock_run.return_value = MagicMock(returncode=0)

        run_rustybt_strategy(
            strategy_module="test.module.Strategy",
            data_path=Path("/data/test.parquet"),
            output_log=Path("/logs/test.jsonl"),
        )

        # Verify timeout kwarg
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["timeout"] == DEFAULT_TIMEOUT

    @patch("subprocess.run")
    def test_uses_custom_timeout(self, mock_run: MagicMock) -> None:
        """Test that custom timeout is passed through."""
        mock_run.return_value = MagicMock(returncode=0)
        custom_timeout = 60

        run_rustybt_strategy(
            strategy_module="test.module.Strategy",
            data_path=Path("/data/test.parquet"),
            output_log=Path("/logs/test.jsonl"),
            timeout=custom_timeout,
        )

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["timeout"] == custom_timeout

    @patch("subprocess.run")
    def test_captures_output(self, mock_run: MagicMock) -> None:
        """Test that capture_output and text flags are set."""
        mock_run.return_value = MagicMock(returncode=0)

        run_rustybt_strategy(
            strategy_module="test.module.Strategy",
            data_path=Path("/data/test.parquet"),
            output_log=Path("/logs/test.jsonl"),
        )

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["capture_output"] is True
        assert call_kwargs["text"] is True

    @patch("subprocess.run")
    def test_returns_completed_process(self, mock_run: MagicMock) -> None:
        """Test that CompletedProcess object is returned."""
        expected_result = subprocess.CompletedProcess(
            args=["test"],
            returncode=0,
            stdout="success output",
            stderr="",
        )
        mock_run.return_value = expected_result

        result = run_rustybt_strategy(
            strategy_module="test.module.Strategy",
            data_path=Path("/data/test.parquet"),
            output_log=Path("/logs/test.jsonl"),
        )

        assert result == expected_result
        assert result.returncode == 0
        assert result.stdout == "success output"

    @patch("subprocess.run")
    def test_uses_sys_executable(self, mock_run: MagicMock) -> None:
        """Test that sys.executable is used for Python interpreter."""
        mock_run.return_value = MagicMock(returncode=0)

        run_rustybt_strategy(
            strategy_module="test.module.Strategy",
            data_path=Path("/data/test.parquet"),
            output_log=Path("/logs/test.jsonl"),
        )

        cmd = mock_run.call_args[0][0]
        assert cmd[0] == sys.executable


class TestRunBacktraderStrategy:
    """Tests for run_backtrader_strategy() function."""

    @patch("subprocess.run")
    def test_builds_correct_command_basic(self, mock_run: MagicMock) -> None:
        """Test that the command is constructed correctly without params."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        run_backtrader_strategy(
            strategy_module="test.module.BTStrategy",
            data_path=Path("/data/test.parquet"),
            output_log=Path("/logs/bt_test.jsonl"),
        )

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]

        # Verify command structure
        assert cmd[0] == sys.executable
        assert "-m" in cmd
        assert "rustybt.validation.execute_backtrader" in cmd
        assert "--strategy" in cmd
        assert "test.module.BTStrategy" in cmd
        assert "--data" in cmd
        assert "/data/test.parquet" in cmd
        assert "--output" in cmd
        assert "/logs/bt_test.jsonl" in cmd

    @patch("subprocess.run")
    def test_builds_command_with_params(self, mock_run: MagicMock) -> None:
        """Test that params are JSON serialized and added to command."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        params = {"sma_period": 20, "threshold": 0.05}

        run_backtrader_strategy(
            strategy_module="test.module.BTStrategy",
            data_path=Path("/data/test.parquet"),
            output_log=Path("/logs/bt_test.jsonl"),
            params=params,
        )

        cmd = mock_run.call_args[0][0]

        assert "--params" in cmd
        params_idx = cmd.index("--params")
        params_json = cmd[params_idx + 1]

        parsed = json.loads(params_json)
        assert parsed == params

    @patch("subprocess.run")
    def test_uses_default_timeout(self, mock_run: MagicMock) -> None:
        """Test that default timeout is used when not specified."""
        mock_run.return_value = MagicMock(returncode=0)

        run_backtrader_strategy(
            strategy_module="test.module.BTStrategy",
            data_path=Path("/data/test.parquet"),
            output_log=Path("/logs/bt_test.jsonl"),
        )

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["timeout"] == DEFAULT_TIMEOUT

    @patch("subprocess.run")
    def test_uses_custom_timeout(self, mock_run: MagicMock) -> None:
        """Test that custom timeout is passed through."""
        mock_run.return_value = MagicMock(returncode=0)
        custom_timeout = 120

        run_backtrader_strategy(
            strategy_module="test.module.BTStrategy",
            data_path=Path("/data/test.parquet"),
            output_log=Path("/logs/bt_test.jsonl"),
            timeout=custom_timeout,
        )

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["timeout"] == custom_timeout

    @patch("subprocess.run")
    def test_captures_output(self, mock_run: MagicMock) -> None:
        """Test that capture_output and text flags are set."""
        mock_run.return_value = MagicMock(returncode=0)

        run_backtrader_strategy(
            strategy_module="test.module.BTStrategy",
            data_path=Path("/data/test.parquet"),
            output_log=Path("/logs/bt_test.jsonl"),
        )

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["capture_output"] is True
        assert call_kwargs["text"] is True


class TestRunnerDefaults:
    """Tests for runner module defaults and constants."""

    def test_default_timeout_value(self) -> None:
        """Test that DEFAULT_TIMEOUT is 300 seconds (5 minutes)."""
        assert DEFAULT_TIMEOUT == 300

    @patch("subprocess.run")
    def test_empty_params_not_added(self, mock_run: MagicMock) -> None:
        """Test that --params is not added when params is None."""
        mock_run.return_value = MagicMock(returncode=0)

        run_rustybt_strategy(
            strategy_module="test.module.Strategy",
            data_path=Path("/data/test.parquet"),
            output_log=Path("/logs/test.jsonl"),
            params=None,
        )

        cmd = mock_run.call_args[0][0]
        assert "--params" not in cmd


class TestRunnerPathHandling:
    """Tests for path handling in runner functions."""

    @patch("subprocess.run")
    def test_path_converted_to_string(self, mock_run: MagicMock) -> None:
        """Test that Path objects are converted to strings in command."""
        mock_run.return_value = MagicMock(returncode=0)

        data_path = Path("/some/data/file.parquet")
        output_path = Path("/some/output/file.jsonl")

        run_rustybt_strategy(
            strategy_module="test.Strategy",
            data_path=data_path,
            output_log=output_path,
        )

        cmd = mock_run.call_args[0][0]

        # Verify paths are strings in command
        data_idx = cmd.index("--data")
        output_idx = cmd.index("--output")

        assert cmd[data_idx + 1] == str(data_path)
        assert cmd[output_idx + 1] == str(output_path)

    @patch("subprocess.run")
    def test_handles_spaces_in_path(self, mock_run: MagicMock) -> None:
        """Test that paths with spaces are handled correctly."""
        mock_run.return_value = MagicMock(returncode=0)

        data_path = Path("/path with spaces/data.parquet")
        output_path = Path("/output path/file.jsonl")

        run_rustybt_strategy(
            strategy_module="test.Strategy",
            data_path=data_path,
            output_log=output_path,
        )

        cmd = mock_run.call_args[0][0]

        # Paths with spaces should be preserved as single arguments
        assert str(data_path) in cmd
        assert str(output_path) in cmd
