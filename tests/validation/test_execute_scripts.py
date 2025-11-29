"""Unit tests for the CLI execution wrapper scripts.

Tests cover:
- CLI argument parsing for both scripts
- Input validation (missing args, invalid paths, invalid JSON)
- Strategy import error handling
- Help text generation

Note: These tests invoke the scripts via subprocess to test the actual CLI interface.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass


class TestExecuteRustybtCLI:
    """Tests for the execute_rustybt.py CLI wrapper."""

    def test_missing_strategy_returns_error(self) -> None:
        """Test that missing --strategy argument returns non-zero exit code."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "rustybt.validation.execute_rustybt",
                "--data",
                "/tmp/test.parquet",
                "--output",
                "/tmp/test.jsonl",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0
        # argparse should complain about missing required argument
        assert "required" in result.stderr.lower() or "strategy" in result.stderr.lower()

    def test_missing_data_returns_error(self) -> None:
        """Test that missing --data argument returns non-zero exit code."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "rustybt.validation.execute_rustybt",
                "--strategy",
                "test.Strategy",
                "--output",
                "/tmp/test.jsonl",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0
        assert "required" in result.stderr.lower() or "data" in result.stderr.lower()

    def test_missing_output_returns_error(self) -> None:
        """Test that missing --output argument returns non-zero exit code."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "rustybt.validation.execute_rustybt",
                "--strategy",
                "test.Strategy",
                "--data",
                "/tmp/test.parquet",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0
        assert "required" in result.stderr.lower() or "output" in result.stderr.lower()

    def test_invalid_json_params_returns_error(self) -> None:
        """Test that invalid JSON in --params returns error."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "rustybt.validation.execute_rustybt",
                "--strategy",
                "test.Strategy",
                "--data",
                "/tmp/test.parquet",
                "--output",
                "/tmp/test.jsonl",
                "--params",
                "not-valid-json",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0
        # argparse json.loads type will fail with decode error
        assert "invalid" in result.stderr.lower() or "json" in result.stderr.lower()

    def test_nonexistent_strategy_returns_error(self, tmp_path: Path) -> None:
        """Test that non-existent strategy module returns error with clear message."""
        # Create a dummy data file
        data_file = tmp_path / "test.parquet"
        data_file.touch()

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "rustybt.validation.execute_rustybt",
                "--strategy",
                "nonexistent.module.Strategy",
                "--data",
                str(data_file),
                "--output",
                str(tmp_path / "output.jsonl"),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0
        assert "could not import" in result.stderr.lower()
        assert "nonexistent.module" in result.stderr.lower()

    def test_nonexistent_data_file_returns_error(self, tmp_path: Path) -> None:
        """Test that non-existent data file returns error with clear message."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "rustybt.validation.execute_rustybt",
                "--strategy",
                "rustybt.validation.RustyBTValidatedStrategy",
                "--data",
                "/nonexistent/path/to/data.parquet",
                "--output",
                str(tmp_path / "output.jsonl"),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0
        assert "not found" in result.stderr.lower() or "nonexistent" in result.stderr.lower()

    def test_help_shows_arguments(self) -> None:
        """Test that --help shows all expected arguments."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "rustybt.validation.execute_rustybt",
                "--help",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "--strategy" in result.stdout
        assert "--data" in result.stdout
        assert "--output" in result.stdout
        assert "--params" in result.stdout

    def test_valid_json_params_accepted(self) -> None:
        """Test that valid JSON params are accepted by argument parser."""
        # This will fail on import (no such strategy), but params should parse correctly
        params = {"period": 20, "threshold": 0.5}

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "rustybt.validation.execute_rustybt",
                "--strategy",
                "nonexistent.Strategy",
                "--data",
                "/tmp/test.parquet",
                "--output",
                "/tmp/test.jsonl",
                "--params",
                json.dumps(params),
            ],
            capture_output=True,
            text=True,
        )

        # Should fail on import, not on param parsing
        assert "invalid" not in result.stderr.lower() or "json" not in result.stderr.lower()


class TestExecuteBacktraderCLI:
    """Tests for the execute_backtrader.py CLI wrapper."""

    def test_missing_strategy_returns_error(self) -> None:
        """Test that missing --strategy argument returns non-zero exit code."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "rustybt.validation.execute_backtrader",
                "--data",
                "/tmp/test.parquet",
                "--output",
                "/tmp/test.jsonl",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0
        assert "required" in result.stderr.lower() or "strategy" in result.stderr.lower()

    def test_missing_data_returns_error(self) -> None:
        """Test that missing --data argument returns non-zero exit code."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "rustybt.validation.execute_backtrader",
                "--strategy",
                "test.Strategy",
                "--output",
                "/tmp/test.jsonl",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0
        assert "required" in result.stderr.lower() or "data" in result.stderr.lower()

    def test_missing_output_returns_error(self) -> None:
        """Test that missing --output argument returns non-zero exit code."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "rustybt.validation.execute_backtrader",
                "--strategy",
                "test.Strategy",
                "--data",
                "/tmp/test.parquet",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0
        assert "required" in result.stderr.lower() or "output" in result.stderr.lower()

    def test_invalid_json_params_returns_error(self) -> None:
        """Test that invalid JSON in --params returns error."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "rustybt.validation.execute_backtrader",
                "--strategy",
                "test.Strategy",
                "--data",
                "/tmp/test.parquet",
                "--output",
                "/tmp/test.jsonl",
                "--params",
                "{invalid json}",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0
        assert "invalid" in result.stderr.lower() or "json" in result.stderr.lower()

    def test_nonexistent_strategy_returns_error(self, tmp_path: Path) -> None:
        """Test that non-existent strategy module returns error with clear message."""
        data_file = tmp_path / "test.parquet"
        data_file.touch()

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "rustybt.validation.execute_backtrader",
                "--strategy",
                "nonexistent.bt.Strategy",
                "--data",
                str(data_file),
                "--output",
                str(tmp_path / "output.jsonl"),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0
        assert "could not import" in result.stderr.lower()
        assert "nonexistent.bt" in result.stderr.lower()

    def test_help_shows_arguments(self) -> None:
        """Test that --help shows all expected arguments."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "rustybt.validation.execute_backtrader",
                "--help",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "--strategy" in result.stdout
        assert "--data" in result.stdout
        assert "--output" in result.stdout
        assert "--params" in result.stdout


class TestBothScriptsConsistency:
    """Tests to verify both scripts have consistent interfaces."""

    def test_both_have_same_required_arguments(self) -> None:
        """Test that both scripts require the same arguments."""
        rustybt_help = subprocess.run(
            [sys.executable, "-m", "rustybt.validation.execute_rustybt", "--help"],
            capture_output=True,
            text=True,
        )

        backtrader_help = subprocess.run(
            [sys.executable, "-m", "rustybt.validation.execute_backtrader", "--help"],
            capture_output=True,
            text=True,
        )

        # Both should have same required args
        for arg in ["--strategy", "--data", "--output"]:
            assert arg in rustybt_help.stdout, f"rustybt missing {arg}"
            assert arg in backtrader_help.stdout, f"backtrader missing {arg}"

    def test_both_have_optional_params(self) -> None:
        """Test that both scripts have optional --params argument."""
        rustybt_help = subprocess.run(
            [sys.executable, "-m", "rustybt.validation.execute_rustybt", "--help"],
            capture_output=True,
            text=True,
        )

        backtrader_help = subprocess.run(
            [sys.executable, "-m", "rustybt.validation.execute_backtrader", "--help"],
            capture_output=True,
            text=True,
        )

        assert "--params" in rustybt_help.stdout
        assert "--params" in backtrader_help.stdout


class TestCLIErrorMessages:
    """Tests for clear error messaging."""

    def test_import_error_includes_module_path(self, tmp_path: Path) -> None:
        """Test that import errors include the full module path."""
        data_file = tmp_path / "test.parquet"
        data_file.touch()

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "rustybt.validation.execute_rustybt",
                "--strategy",
                "some.deep.module.path.MyStrategy",
                "--data",
                str(data_file),
                "--output",
                str(tmp_path / "output.jsonl"),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0
        # Error message should include the module path for debugging
        assert "some.deep.module.path" in result.stderr
