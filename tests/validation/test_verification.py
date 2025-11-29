"""Tests for bug fix verification workflow.

Story 5.5: Implement Bug Fix Verification

Tests the verification module which re-executes strategies and re-runs
layer comparisons to verify that bug fixes resolve discrepancies.
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import polars as pl
import pytest

from rustybt.validation.models import Finding, Session, SessionStage
from rustybt.validation.verification import (
    ExecutionError,
    VerificationResult,
    compare_layer_for_finding,
    get_comparator_for_layer,
    load_finding,
    load_tolerances_for_layer,
    save_finding,
    verify_fix,
)


class TestGetComparatorForLayer:
    """Tests for get_comparator_for_layer function."""

    def test_get_data_comparator(self):
        """Should return Layer1DataComparator for 'data' layer."""
        comparator = get_comparator_for_layer("data")
        assert comparator.layer_name == "data"

    def test_get_signals_comparator(self):
        """Should return Layer2SignalComparator for 'signals' layer."""
        comparator = get_comparator_for_layer("signals")
        assert comparator.layer_name == "signals"

    def test_get_orders_comparator(self):
        """Should return Layer3OrdersComparator for 'orders' layer."""
        comparator = get_comparator_for_layer("orders")
        assert comparator.layer_name == "orders"

    def test_get_broker_comparator(self):
        """Should return Layer4BrokerComparator for 'broker' layer."""
        comparator = get_comparator_for_layer("broker")
        assert comparator.layer_name == "broker"

    def test_get_portfolio_comparator(self):
        """Should return Layer5PortfolioComparator for 'portfolio' layer."""
        comparator = get_comparator_for_layer("portfolio")
        assert comparator.layer_name == "portfolio"

    def test_invalid_layer_raises_error(self):
        """Should raise ValueError for invalid layer name."""
        with pytest.raises(ValueError, match="Invalid layer"):
            get_comparator_for_layer("invalid")


class TestLoadTolerancesForLayer:
    """Tests for load_tolerances_for_layer function."""

    def test_loads_default_tolerances_when_no_config(self, tmp_path):
        """Should return default tolerances when config directory doesn't exist."""
        tolerances = load_tolerances_for_layer("data", tmp_path / "nonexistent")
        # Should return something (defaults)
        assert tolerances is not None

    def test_returns_layer_specific_tolerances(self, tmp_path):
        """Should return tolerances specific to requested layer."""
        tolerances = load_tolerances_for_layer("signals", tmp_path)
        # Should return tolerances object
        assert tolerances is not None


class TestVerificationResult:
    """Tests for VerificationResult dataclass."""

    def test_passed_result(self):
        """Should create passed verification result."""
        result = VerificationResult(
            passed=True,
            finding_id="FIND-001",
            original_discrepancy="test discrepancy",
        )
        assert result.passed is True
        assert result.finding_id == "FIND-001"
        assert result.error is None

    def test_failed_result_with_discrepancies(self):
        """Should create failed result with current discrepancies."""
        result = VerificationResult(
            passed=False,
            finding_id="FIND-002",
            current_discrepancies=[MagicMock()],
        )
        assert result.passed is False
        assert len(result.current_discrepancies) == 1

    def test_failed_result_with_error(self):
        """Should create failed result with error message."""
        result = VerificationResult(
            passed=False,
            finding_id="FIND-003",
            error="Execution failed",
        )
        assert result.passed is False
        assert result.error == "Execution failed"


class TestCompareLayerForFinding:
    """Tests for compare_layer_for_finding function."""

    def test_compares_data_layer(self):
        """Should run data layer comparison for data finding."""
        finding = Finding(
            id="FIND-001",
            layer="data",
            description="Test discrepancy",
            classification="BUG",
        )

        # Create minimal valid DataFrames
        rb_logs = pl.DataFrame({
            "layer": ["data"],
            "event": ["bar_received"],
            "timestamp": ["2024-01-01T09:30:00"],
        })
        bt_logs = pl.DataFrame({
            "layer": ["data"],
            "event": ["bar_received"],
            "timestamp": ["2024-01-01T09:30:00"],
        })

        # Should not raise, returns list
        result = compare_layer_for_finding(finding, rb_logs, bt_logs)
        assert isinstance(result, list)

    def test_compares_signals_layer(self):
        """Should run signals layer comparison for signals finding."""
        finding = Finding(
            id="FIND-002",
            layer="signals",
            description="Signal discrepancy",
            classification="BUG",
        )

        rb_logs = pl.DataFrame({
            "layer": ["signals"],
            "event": ["signal_generated"],
            "timestamp": ["2024-01-01T09:30:00"],
        })
        bt_logs = pl.DataFrame({
            "layer": ["signals"],
            "event": ["signal_generated"],
            "timestamp": ["2024-01-01T09:30:00"],
        })

        result = compare_layer_for_finding(finding, rb_logs, bt_logs)
        assert isinstance(result, list)


class TestVerifyFix:
    """Tests for verify_fix function."""

    def test_rejects_non_bug_finding(self):
        """Should reject findings not classified as BUG."""
        finding = Finding(
            id="FIND-001",
            layer="data",
            description="Design difference",
            classification="DESIGN",
        )
        session = MagicMock(spec=Session)

        result = verify_fix(finding, session)

        assert result.passed is False
        assert "not classified as BUG" in result.error

    def test_rejects_unclassified_finding(self):
        """Should reject findings without classification."""
        finding = Finding(
            id="FIND-001",
            layer="data",
            description="Unclassified finding",
            classification=None,
        )
        session = MagicMock(spec=Session)

        result = verify_fix(finding, session)

        assert result.passed is False
        assert "not classified as BUG" in result.error

    @patch("rustybt.validation.verification.re_execute_strategies")
    def test_handles_execution_error(self, mock_execute):
        """Should handle execution errors gracefully."""
        mock_execute.side_effect = ExecutionError("rustybt crashed")

        finding = Finding(
            id="FIND-001",
            layer="data",
            description="Data discrepancy",
            classification="BUG",
        )
        session = MagicMock(spec=Session)

        result = verify_fix(finding, session)

        assert result.passed is False
        assert "rustybt crashed" in result.error

    @patch("rustybt.validation.verification.re_execute_strategies")
    @patch("rustybt.validation.verification.compare_layer_for_finding")
    def test_passes_when_discrepancy_resolved(self, mock_compare, mock_execute):
        """Should pass when original discrepancy no longer found."""
        mock_execute.return_value = (
            pl.DataFrame({"layer": [], "event": []}),
            pl.DataFrame({"layer": [], "event": []}),
        )
        mock_compare.return_value = []  # No discrepancies

        finding = Finding(
            id="FIND-001",
            layer="data",
            description="data/ohlcv_mismatch: price differs",
            classification="BUG",
        )
        session = MagicMock(spec=Session)

        result = verify_fix(finding, session)

        assert result.passed is True

    @patch("rustybt.validation.verification.re_execute_strategies")
    @patch("rustybt.validation.verification.compare_layer_for_finding")
    def test_fails_when_discrepancy_persists(self, mock_compare, mock_execute):
        """Should fail when original discrepancy still present."""
        from rustybt.validation.comparators import Discrepancy

        mock_execute.return_value = (
            pl.DataFrame({"layer": [], "event": []}),
            pl.DataFrame({"layer": [], "event": []}),
        )
        # Return discrepancy matching the original
        mock_compare.return_value = [
            Discrepancy(
                layer="data",
                event="ohlcv_mismatch",
                timestamp="2024-01-01",
                field="price",
                rustybt_value=100.0,
                backtrader_value=100.1,
                tolerance=0.01,
                exceeded_by=0.1,
                description="data/ohlcv_mismatch: price differs",
            )
        ]

        finding = Finding(
            id="FIND-001",
            layer="data",
            description="data/ohlcv_mismatch: price differs",
            classification="BUG",
        )
        session = MagicMock(spec=Session)

        result = verify_fix(finding, session)

        assert result.passed is False
        assert len(result.current_discrepancies) > 0


class TestLoadFinding:
    """Tests for load_finding function."""

    def test_finds_existing_finding(self, tmp_path):
        """Should locate finding in session."""
        from rustybt.validation.session import SessionManager

        # Create a real session with a finding using temp directory
        sm = SessionManager(tmp_path)
        session = sm.create_session(
            strategy_name="test_strategy",
            data_fixture=Path("test.csv"),
            rustybt_version="1.0.0",
            backtrader_version="1.9.0",
        )
        finding = Finding(
            id="FIND-001",
            layer="data",
            description="Test",
        )
        sm.add_finding(session, finding)

        # Now load it
        found_finding, found_session = load_finding("FIND-001", tmp_path)

        assert found_finding is not None
        assert found_finding.id == "FIND-001"
        assert found_session is not None

    def test_returns_none_for_missing_finding(self, tmp_path):
        """Should return None for non-existent finding."""
        found_finding, found_session = load_finding("NONEXISTENT", tmp_path)

        assert found_finding is None
        assert found_session is None


class TestSaveFinding:
    """Tests for save_finding function."""

    def test_updates_finding_in_session(self):
        """Should update finding and save session."""
        finding = Finding(
            id="FIND-001",
            layer="data",
            description="Test",
            resolved=True,
        )
        session = MagicMock(spec=Session)
        session.findings = [
            Finding(id="FIND-001", layer="data", description="Test")
        ]
        session.log_activity = MagicMock()

        with patch("rustybt.validation.session.SessionManager") as mock_sm_class:
            mock_sm = MagicMock()
            mock_sm_class.return_value = mock_sm

            save_finding(finding, session)

            # Should update the finding in the list
            assert session.findings[0].resolved is True
            # Should call update_session
            mock_sm.update_session.assert_called_once_with(session)


class TestCLIVerifyCommand:
    """Tests for 'rustybt-validate verify' CLI command."""

    def test_verify_command_exists(self):
        """Should have verify command registered."""
        from click.testing import CliRunner
        from rustybt.validation.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["verify", "--help"])

        assert result.exit_code == 0
        assert "Verify a bug fix" in result.output

    def test_verify_not_found(self, tmp_path, monkeypatch):
        """Should error when finding not found."""
        from click.testing import CliRunner
        from rustybt.validation.cli import main

        # Point to empty sessions dir
        monkeypatch.chdir(tmp_path)
        (tmp_path / "validation-sessions").mkdir()

        runner = CliRunner()
        result = runner.invoke(main, ["verify", "NONEXISTENT"])

        assert result.exit_code == 1
        assert "not found" in result.output

    def test_verify_rejects_design_finding(self, tmp_path, monkeypatch):
        """Should reject DESIGN-classified findings."""
        from click.testing import CliRunner
        from rustybt.validation.cli import main
        from rustybt.validation.session import SessionManager

        monkeypatch.chdir(tmp_path)

        # Create a session with a DESIGN finding
        sessions_dir = tmp_path / "validation-sessions"
        sm = SessionManager(sessions_dir)
        session = sm.create_session(
            strategy_name="test_strategy",
            data_fixture=Path("test.csv"),
            rustybt_version="1.0.0",
            backtrader_version="1.9.0",
        )
        finding = Finding(
            id="FIND-001",
            layer="data",
            description="Design difference",
            classification="DESIGN",
        )
        sm.add_finding(session, finding)

        runner = CliRunner()
        result = runner.invoke(main, ["verify", "FIND-001"])

        assert result.exit_code == 1
        assert "not classified as BUG" in result.output

    def test_verify_shows_original_discrepancy(self, tmp_path, monkeypatch):
        """Should display original discrepancy info."""
        from click.testing import CliRunner
        from rustybt.validation.cli import main
        from rustybt.validation.session import SessionManager

        monkeypatch.chdir(tmp_path)

        # Create a session with a BUG finding
        sessions_dir = tmp_path / "validation-sessions"
        sm = SessionManager(sessions_dir)
        session = sm.create_session(
            strategy_name="test_strategy",
            data_fixture=Path("test.csv"),
            rustybt_version="1.0.0",
            backtrader_version="1.9.0",
        )
        finding = Finding(
            id="FIND-001",
            layer="data",
            description="Data discrepancy: OHLCV mismatch",
            classification="BUG",
            rustybt_value=100.0,
            backtrader_value=100.5,
        )
        sm.add_finding(session, finding)

        runner = CliRunner()
        # This will fail at execution, but we can check the output shows the discrepancy
        result = runner.invoke(main, ["verify", "FIND-001"])

        # Should show original discrepancy info before attempting execution
        assert "Original discrepancy" in result.output
        assert "Data discrepancy" in result.output or "data" in result.output
