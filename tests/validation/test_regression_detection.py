"""Tests for regression detection.

Story 5.7: Implement Regression Detection

Tests the regression detection module which identifies when previously
fixed bugs reappear in new comparisons.
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from rustybt.validation.comparators import Discrepancy
from rustybt.validation.models import Finding
from rustybt.validation.regression_detection import (
    Regression,
    RegressionError,
    _extract_event_from_finding,
    detect_regressions,
    format_regression_warning,
    load_resolved_bugs,
    matches_finding,
    report_regressions,
)


class TestRegression:
    """Tests for Regression dataclass."""

    def test_creates_regression(self):
        """Should create Regression with all fields."""
        discrepancy = Discrepancy(
            layer="orders",
            event="order_quantity_mismatch",
            timestamp="2024-01-01T10:00:00",
            field="quantity",
            rustybt_value=100.0,
            backtrader_value=99.0,
            tolerance=0.01,
            exceeded_by=1.0,
            description="Order quantity mismatch",
        )

        regression = Regression(
            original_finding_id="FIND-001",
            current_discrepancy=discrepancy,
            fixed_at=datetime(2025, 11, 24),
            regression_detected_at=datetime.now(),
            original_fix_description="Fixed quantity calculation",
            original_layer="orders",
        )

        assert regression.original_finding_id == "FIND-001"
        assert regression.current_discrepancy == discrepancy
        assert regression.fixed_at == datetime(2025, 11, 24)
        assert regression.original_fix_description == "Fixed quantity calculation"

    def test_to_dict(self):
        """Should serialize to dictionary."""
        discrepancy = Discrepancy(
            layer="orders",
            event="test",
            timestamp="2024-01-01",
            field="test",
            rustybt_value=1.0,
            backtrader_value=2.0,
            tolerance=0.1,
            exceeded_by=0.5,
            description="Test discrepancy",
        )

        regression = Regression(
            original_finding_id="FIND-002",
            current_discrepancy=discrepancy,
            fixed_at=datetime(2025, 11, 24),
            regression_detected_at=datetime(2025, 11, 27),
            original_fix_description="Fix",
        )

        data = regression.to_dict()

        assert data["original_finding_id"] == "FIND-002"
        assert data["fixed_at"] == "2025-11-24T00:00:00"
        assert data["regression_detected_at"] == "2025-11-27T00:00:00"
        assert data["current_discrepancy"]["layer"] == "orders"


class TestMatchesFinding:
    """Tests for matches_finding function."""

    def test_matches_same_layer_and_event(self):
        """Should match when layer and event are the same."""
        discrepancy = Discrepancy(
            layer="orders",
            event="order_quantity_mismatch",
            timestamp="2024-01-01",
            field="quantity",
            rustybt_value=100.0,
            backtrader_value=99.0,
            tolerance=0.01,
            exceeded_by=1.0,
            description="Order quantity mismatch",
        )
        finding = Finding(
            id="FIND-001",
            layer="orders",
            description="orders/order_quantity_mismatch: quantity differs",
            classification="BUG",
            resolved=True,
        )

        assert matches_finding(discrepancy, finding) is True

    def test_no_match_different_layer(self):
        """Should not match when layers differ."""
        discrepancy = Discrepancy(
            layer="signals",
            event="order_quantity_mismatch",
            timestamp="2024-01-01",
            field="quantity",
            rustybt_value=100.0,
            backtrader_value=99.0,
            tolerance=0.01,
            exceeded_by=1.0,
            description="Quantity mismatch",
        )
        finding = Finding(
            id="FIND-001",
            layer="orders",
            description="Order quantity mismatch",
            classification="BUG",
            resolved=True,
        )

        assert matches_finding(discrepancy, finding) is False

    def test_matches_on_keyword_overlap(self):
        """Should match when descriptions have significant keyword overlap."""
        discrepancy = Discrepancy(
            layer="data",
            event="price_mismatch",
            timestamp="2024-01-01",
            field="close",
            rustybt_value=100.0,
            backtrader_value=99.99,
            tolerance=0.01,
            exceeded_by=0.01,
            description="Price mismatch in close price",
        )
        finding = Finding(
            id="FIND-002",
            layer="data",
            description="Close price mismatch detected",
            classification="BUG",
            resolved=True,
        )

        assert matches_finding(discrepancy, finding) is True

    def test_no_match_different_issues(self):
        """Should not match when issues are clearly different."""
        discrepancy = Discrepancy(
            layer="portfolio",
            event="cash_mismatch",
            timestamp="2024-01-01",
            field="cash",
            rustybt_value=10000.0,
            backtrader_value=9999.0,
            tolerance=1.0,
            exceeded_by=1.0,
            description="Cash balance differs",
        )
        finding = Finding(
            id="FIND-003",
            layer="portfolio",
            description="Return calculation is wrong",
            classification="BUG",
            resolved=True,
        )

        # Different event types in same layer
        assert matches_finding(discrepancy, finding) is False


class TestLoadResolvedBugs:
    """Tests for load_resolved_bugs function."""

    def test_loads_resolved_bugs_from_sessions(self, tmp_path):
        """Should load resolved BUG findings from session files."""
        # Create session with resolved finding
        session_dir = tmp_path / "session-001"
        session_dir.mkdir()

        session_data = {
            "id": "session-001",
            "created_at": "2025-11-24T12:00:00",
            "strategy_name": "test",
            "rustybt_version": "1.0.0",
            "backtrader_version": "1.9.0",
            "python_version": "3.12.0",
            "status": "COMPLETED",
            "data_fixture": "test.csv",
            "findings": [
                {
                    "id": "FIND-001",
                    "layer": "orders",
                    "description": "Order mismatch",
                    "classification": "BUG",
                    "resolved": True,
                    "resolved_at": "2025-11-24T12:00:00",
                },
                {
                    "id": "FIND-002",
                    "layer": "data",
                    "description": "Design difference",
                    "classification": "DESIGN",
                    "resolved": False,
                },
            ],
        }
        (session_dir / "session.yaml").write_text(yaml.dump(session_data))

        bugs = load_resolved_bugs(tmp_path)

        assert len(bugs) == 1
        assert bugs[0].id == "FIND-001"
        assert bugs[0].resolved is True

    def test_returns_empty_for_nonexistent_dir(self, tmp_path):
        """Should return empty list for nonexistent directory."""
        bugs = load_resolved_bugs(tmp_path / "nonexistent")
        assert bugs == []

    def test_skips_unresolved_bugs(self, tmp_path):
        """Should skip BUG findings that are not resolved."""
        session_dir = tmp_path / "session-001"
        session_dir.mkdir()

        session_data = {
            "id": "session-001",
            "created_at": "2025-11-24T12:00:00",
            "strategy_name": "test",
            "rustybt_version": "1.0.0",
            "backtrader_version": "1.9.0",
            "python_version": "3.12.0",
            "status": "IN_PROGRESS",
            "data_fixture": "test.csv",
            "findings": [
                {
                    "id": "FIND-001",
                    "layer": "orders",
                    "description": "Open bug",
                    "classification": "BUG",
                    "resolved": False,
                }
            ],
        }
        (session_dir / "session.yaml").write_text(yaml.dump(session_data))

        bugs = load_resolved_bugs(tmp_path)
        assert len(bugs) == 0


class TestDetectRegressions:
    """Tests for detect_regressions function."""

    def test_detects_regression(self, tmp_path):
        """Should detect regression when discrepancy matches resolved bug."""
        # Create resolved bug
        session_dir = tmp_path / "session-001"
        session_dir.mkdir()

        session_data = {
            "id": "session-001",
            "created_at": "2025-11-24T12:00:00",
            "strategy_name": "test",
            "rustybt_version": "1.0.0",
            "backtrader_version": "1.9.0",
            "python_version": "3.12.0",
            "status": "COMPLETED",
            "data_fixture": "test.csv",
            "findings": [
                {
                    "id": "FIND-001",
                    "layer": "orders",
                    "description": "Order quantity mismatch",
                    "classification": "BUG",
                    "resolved": True,
                    "resolved_at": "2025-11-24T12:00:00",
                    "rationale": "Fixed calculation",
                }
            ],
        }
        (session_dir / "session.yaml").write_text(yaml.dump(session_data))

        # Discrepancy matching the resolved bug
        discrepancies = [
            Discrepancy(
                layer="orders",
                event="order_quantity_mismatch",
                timestamp="2024-01-01",
                field="quantity",
                rustybt_value=100.0,
                backtrader_value=99.0,
                tolerance=0.01,
                exceeded_by=1.0,
                description="Order quantity mismatch detected",
            )
        ]

        regressions = detect_regressions(discrepancies, tmp_path)

        assert len(regressions) == 1
        assert regressions[0].original_finding_id == "FIND-001"
        assert regressions[0].original_fix_description == "Fixed calculation"

    def test_no_regression_for_new_issue(self, tmp_path):
        """Should not detect regression for new, unrelated issue."""
        # Create resolved bug for different issue
        session_dir = tmp_path / "session-001"
        session_dir.mkdir()

        session_data = {
            "id": "session-001",
            "created_at": "2025-11-24T12:00:00",
            "strategy_name": "test",
            "rustybt_version": "1.0.0",
            "backtrader_version": "1.9.0",
            "python_version": "3.12.0",
            "status": "COMPLETED",
            "data_fixture": "test.csv",
            "findings": [
                {
                    "id": "FIND-001",
                    "layer": "data",
                    "description": "Price data issue",
                    "classification": "BUG",
                    "resolved": True,
                }
            ],
        }
        (session_dir / "session.yaml").write_text(yaml.dump(session_data))

        # Different issue
        discrepancies = [
            Discrepancy(
                layer="signals",
                event="rsi_mismatch",
                timestamp="2024-01-01",
                field="rsi",
                rustybt_value=70.0,
                backtrader_value=71.0,
                tolerance=0.1,
                exceeded_by=1.0,
                description="RSI calculation differs",
            )
        ]

        regressions = detect_regressions(discrepancies, tmp_path)
        assert len(regressions) == 0

    def test_empty_discrepancies_no_regressions(self, tmp_path):
        """Should return empty list for empty discrepancies."""
        regressions = detect_regressions([], tmp_path)
        assert regressions == []


class TestFormatRegressionWarning:
    """Tests for format_regression_warning function."""

    def test_includes_finding_id(self):
        """Should include original finding ID."""
        discrepancy = Discrepancy(
            layer="orders",
            event="test",
            timestamp="2024-01-01",
            field="test",
            rustybt_value=1.0,
            backtrader_value=2.0,
            tolerance=0.1,
            exceeded_by=1.0,
            description="Test discrepancy",
        )
        regression = Regression(
            original_finding_id="FIND-001",
            current_discrepancy=discrepancy,
            fixed_at=datetime(2025, 11, 24),
            regression_detected_at=datetime.now(),
        )

        warning = format_regression_warning(regression)

        assert "FIND-001" in warning

    def test_includes_fix_date(self):
        """Should include fix date."""
        discrepancy = Discrepancy(
            layer="orders",
            event="test",
            timestamp="2024-01-01",
            field="test",
            rustybt_value=1.0,
            backtrader_value=2.0,
            tolerance=0.1,
            exceeded_by=1.0,
            description="Test discrepancy",
        )
        regression = Regression(
            original_finding_id="FIND-001",
            current_discrepancy=discrepancy,
            fixed_at=datetime(2025, 11, 24),
            regression_detected_at=datetime.now(),
        )

        warning = format_regression_warning(regression)

        assert "2025-11-24" in warning

    def test_includes_layer_and_description(self):
        """Should include layer and description."""
        discrepancy = Discrepancy(
            layer="orders",
            event="test",
            timestamp="2024-01-01",
            field="test",
            rustybt_value=1.0,
            backtrader_value=2.0,
            tolerance=0.1,
            exceeded_by=1.0,
            description="Order quantity differs",
        )
        regression = Regression(
            original_finding_id="FIND-001",
            current_discrepancy=discrepancy,
            fixed_at=datetime(2025, 11, 24),
            regression_detected_at=datetime.now(),
        )

        warning = format_regression_warning(regression)

        assert "orders" in warning
        assert "Order quantity differs" in warning

    def test_includes_regression_keyword(self):
        """Should include REGRESSION keyword for emphasis."""
        discrepancy = Discrepancy(
            layer="data",
            event="test",
            timestamp="2024-01-01",
            field="test",
            rustybt_value=1.0,
            backtrader_value=2.0,
            tolerance=0.1,
            exceeded_by=1.0,
            description="Test",
        )
        regression = Regression(
            original_finding_id="FIND-001",
            current_discrepancy=discrepancy,
            fixed_at=datetime.now(),
            regression_detected_at=datetime.now(),
        )

        warning = format_regression_warning(regression)

        assert "REGRESSION" in warning


class TestExtractEventFromFinding:
    """Tests for _extract_event_from_finding helper."""

    def test_extracts_from_slash_pattern(self):
        """Should extract event from layer/event: description pattern."""
        finding = Finding(
            id="FIND-001",
            layer="orders",
            description="orders/order_quantity_mismatch: quantity differs",
        )

        event = _extract_event_from_finding(finding)

        assert event == "order_quantity_mismatch"

    def test_extracts_from_mismatch_suffix(self):
        """Should extract event ending with 'mismatch'."""
        finding = Finding(
            id="FIND-002",
            layer="data",
            description="Price mismatch detected in close",
        )

        event = _extract_event_from_finding(finding)

        assert "mismatch" in event.lower() or "price" in event.lower()


class TestRegressionError:
    """Tests for RegressionError exception."""

    def test_creates_error_with_message(self):
        """Should create error with message."""
        error = RegressionError("Test error")
        assert str(error) == "Test error"

    def test_creates_error_with_regressions(self):
        """Should store regressions list."""
        discrepancy = MagicMock()
        regression = Regression(
            original_finding_id="FIND-001",
            current_discrepancy=discrepancy,
            fixed_at=datetime.now(),
            regression_detected_at=datetime.now(),
        )
        error = RegressionError("Regressions found", [regression])

        assert len(error.regressions) == 1
        assert error.regressions[0].original_finding_id == "FIND-001"


class TestCLICompareCommand:
    """Tests for compare CLI command."""

    def test_compare_command_exists(self):
        """Should have compare command registered."""
        from click.testing import CliRunner
        from rustybt.validation.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["compare", "--help"])

        assert result.exit_code == 0
        assert "layer comparison" in result.output.lower() or "compare" in result.output.lower()

    def test_check_regressions_command_exists(self):
        """Should have check-regressions command registered."""
        from click.testing import CliRunner
        from rustybt.validation.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["check-regressions", "--help"])

        assert result.exit_code == 0
        assert "regression" in result.output.lower()


class TestReportRegressions:
    """Tests for report_regressions function."""

    def test_no_output_for_empty_list(self, capsys):
        """Should produce no output for empty regression list."""
        report_regressions([])
        captured = capsys.readouterr()
        # Should not print anything for empty list
        assert "REGRESSION" not in captured.out

    def test_reports_multiple_regressions(self, capsys):
        """Should report all regressions."""
        discrepancy1 = Discrepancy(
            layer="orders",
            event="test1",
            timestamp="2024-01-01",
            field="test",
            rustybt_value=1.0,
            backtrader_value=2.0,
            tolerance=0.1,
            exceeded_by=1.0,
            description="Test 1",
        )
        discrepancy2 = Discrepancy(
            layer="signals",
            event="test2",
            timestamp="2024-01-01",
            field="test",
            rustybt_value=3.0,
            backtrader_value=4.0,
            tolerance=0.1,
            exceeded_by=1.0,
            description="Test 2",
        )

        regressions = [
            Regression(
                original_finding_id="FIND-001",
                current_discrepancy=discrepancy1,
                fixed_at=datetime.now(),
                regression_detected_at=datetime.now(),
            ),
            Regression(
                original_finding_id="FIND-002",
                current_discrepancy=discrepancy2,
                fixed_at=datetime.now(),
                regression_detected_at=datetime.now(),
            ),
        ]

        report_regressions(regressions)
        captured = capsys.readouterr()

        assert "2 REGRESSION" in captured.out
        assert "FIND-001" in captured.out
        assert "FIND-002" in captured.out
