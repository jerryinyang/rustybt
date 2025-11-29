"""Tests for validation CLI."""

import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest
from click.testing import CliRunner

from rustybt.validation.cli import main
from rustybt.validation.models import Finding, Session, SessionStage


class TestValidationCLI:
    """Test suite for validation framework CLI."""

    def test_cli_entry_point_exists(self):
        """Test that rustybt-validate entry point is registered."""
        # This test verifies the CLI is importable and callable
        from rustybt.validation.cli import main

        assert callable(main)

    def test_cli_help_command(self):
        """Test --help flag displays help text."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        assert "RustyBT validation framework CLI" in result.output
        assert "Options:" in result.output
        assert "--help" in result.output
        assert "--version" in result.output

    def test_cli_version_command(self):
        """Test --version flag displays version number."""
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])

        assert result.exit_code == 0
        assert "rustybt-validate, version" in result.output
        # Verify version format (X.Y.Z or X.Y.Z.devN)
        assert any(char.isdigit() for char in result.output)

    def test_cli_executable_via_subprocess(self):
        """Test CLI is accessible as system command after installation."""
        # This verifies the entry point registration in pyproject.toml works
        result = subprocess.run(
            [sys.executable, "-m", "rustybt.validation.cli", "--help"],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0
        assert "RustyBT validation framework CLI" in result.stdout

    def test_cli_no_subcommands_initially(self):
        """Test CLI stub has no subcommands yet (will be added in Story 1.6)."""
        runner = CliRunner()
        result = runner.invoke(main, [])

        # Click group with no subcommands and no arguments returns exit code 2 (usage error)
        # This is expected behavior - the CLI exists but has no commands yet
        assert result.exit_code == 2
        # Should show usage information
        assert "Usage:" in result.output


class TestReportCommand:
    """Test suite for report CLI command."""

    @pytest.fixture
    def test_session(self, tmp_path: Path) -> Session:
        """Create a test session with session manager."""
        import yaml

        session_id = "20251124-143000-000000-test_strategy"
        session_dir = tmp_path / session_id
        session_dir.mkdir(parents=True)
        (session_dir / "logs").mkdir()
        (session_dir / "analysis").mkdir()

        session = Session(
            id=session_id,
            created_at=datetime(2025, 11, 24, 14, 30, 0),
            strategy_name="test_strategy",
            rustybt_version="0.3.4",
            backtrader_version="1.9.78",
            python_version="3.12.0",
            status="COMPLETED",
            data_fixture=Path("fixtures/test.parquet"),
            layers_completed=["data", "signals", "orders", "broker", "portfolio"],
            findings=[
                Finding(
                    id="FIND-001",
                    layer="signals",
                    description="Test finding",
                    classification="DESIGN",
                )
            ],
        )

        # Save session YAML
        session_file = session_dir / "session.yaml"
        data = {
            "id": session.id,
            "created_at": session.created_at.isoformat(),
            "strategy_name": session.strategy_name,
            "rustybt_version": session.rustybt_version,
            "backtrader_version": session.backtrader_version,
            "python_version": session.python_version,
            "status": session.status,
            "data_fixture": str(session.data_fixture),
            "stage": session.stage.value,
            "layers_completed": session.layers_completed,
            "findings": [f.to_dict() for f in session.findings],
            "activities": [],
        }

        with open(session_file, "w") as f:
            yaml.dump(data, f)

        return session

    def test_report_command_help(self):
        """Test report command --help shows usage."""
        runner = CliRunner()
        result = runner.invoke(main, ["report", "--help"])

        assert result.exit_code == 0
        assert "Generate a validation report" in result.output
        assert "--format" in result.output

    def test_report_command_session_not_found(self, tmp_path: Path):
        """Test report command with non-existent session."""
        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, ["report", "nonexistent-session"])

        assert result.exit_code == 1
        assert "Session not found" in result.output

    def test_report_command_markdown_format(self, tmp_path: Path, test_session: Session):
        """Test report command generates markdown report."""
        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Create validation-sessions directory structure expected by SessionManager
            import shutil
            sessions_dir = Path("validation-sessions")
            sessions_dir.mkdir(exist_ok=True)

            # Copy test session to expected location
            src_session_dir = tmp_path / test_session.id
            dst_session_dir = sessions_dir / test_session.id
            shutil.copytree(src_session_dir, dst_session_dir)

            result = runner.invoke(main, ["report", test_session.id])

            assert result.exit_code == 0
            assert "Report saved to" in result.output
            assert "report.md" in result.output

            # Verify file was created
            report_path = dst_session_dir / "report.md"
            assert report_path.exists()

    def test_report_command_json_format(self, tmp_path: Path, test_session: Session):
        """Test report command with --format json."""
        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=tmp_path):
            import shutil
            sessions_dir = Path("validation-sessions")
            sessions_dir.mkdir(exist_ok=True)

            src_session_dir = tmp_path / test_session.id
            dst_session_dir = sessions_dir / test_session.id
            shutil.copytree(src_session_dir, dst_session_dir)

            result = runner.invoke(main, ["report", test_session.id, "--format", "json"])

            assert result.exit_code == 0
            assert "JSON report saved to" in result.output
            assert "report.json" in result.output

            # Verify file was created
            report_path = dst_session_dir / "report.json"
            assert report_path.exists()

    def test_report_command_shows_session_info(self, tmp_path: Path, test_session: Session):
        """Test report command shows session summary."""
        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=tmp_path):
            import shutil
            sessions_dir = Path("validation-sessions")
            sessions_dir.mkdir(exist_ok=True)

            src_session_dir = tmp_path / test_session.id
            dst_session_dir = sessions_dir / test_session.id
            shutil.copytree(src_session_dir, dst_session_dir)

            result = runner.invoke(main, ["report", test_session.id])

            assert result.exit_code == 0
            assert test_session.strategy_name in result.output
            assert test_session.status in result.output
            assert "Findings: 1" in result.output
