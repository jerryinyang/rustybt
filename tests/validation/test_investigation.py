"""Tests for investigation module and CLI command."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from rustybt.validation.cli import main
from rustybt.validation.investigation import (
    InvestigationContext,
    filter_findings,
    find_index_by_id,
    format_finding_presentation,
    get_progress_indicator,
    get_unclassified_count,
)
from rustybt.validation.models import Finding


@pytest.fixture
def sample_findings() -> list[Finding]:
    """Create sample findings for testing."""
    return [
        Finding(
            id="FIND-001",
            layer="data",
            description="Data mismatch at bar 100",
            classification=None,
            rustybt_value=100.5,
            backtrader_value=100.0,
        ),
        Finding(
            id="FIND-002",
            layer="signals",
            description="Signal timing difference",
            classification="BUG",
            rationale="Off by one error",
            investigated_by="developer",
            investigated_at=datetime(2025, 1, 15, 10, 30),
            rustybt_value="2020-03-15T09:30:00",
            backtrader_value="2020-03-15T09:29:00",
        ),
        Finding(
            id="FIND-003",
            layer="orders",
            description="Order quantity mismatch",
            classification=None,
            rustybt_value=100,
            backtrader_value=99,
        ),
        Finding(
            id="FIND-004",
            layer="orders",
            description="Order type difference",
            classification="DESIGN",
            rationale="Intentional change for better fills",
            investigated_by="architect",
            investigated_at=datetime(2025, 1, 14, 14, 0),
            rustybt_value="LIMIT",
            backtrader_value="MARKET",
        ),
        Finding(
            id="FIND-005",
            layer="portfolio",
            description="Portfolio value drift",
            classification=None,
            rustybt_value=100000.50,
            backtrader_value=100000.00,
        ),
    ]


class TestFilterFindings:
    """Tests for filter_findings function."""

    def test_filter_by_layer_data(self, sample_findings):
        """Test filtering by data layer."""
        result = filter_findings(sample_findings, layer="data")
        assert len(result) == 1
        assert result[0].id == "FIND-001"

    def test_filter_by_layer_orders(self, sample_findings):
        """Test filtering by orders layer."""
        result = filter_findings(sample_findings, layer="orders")
        assert len(result) == 2
        assert {f.id for f in result} == {"FIND-003", "FIND-004"}

    def test_filter_by_unclassified(self, sample_findings):
        """Test filtering for unclassified findings."""
        result = filter_findings(sample_findings, unclassified=True)
        assert len(result) == 3
        assert all(f.classification is None for f in result)

    def test_filter_by_bugs(self, sample_findings):
        """Test filtering for BUG-classified findings."""
        result = filter_findings(sample_findings, bugs=True)
        assert len(result) == 1
        assert result[0].classification == "BUG"

    def test_filter_by_design(self, sample_findings):
        """Test filtering for DESIGN-classified findings."""
        result = filter_findings(sample_findings, design=True)
        assert len(result) == 1
        assert result[0].classification == "DESIGN"

    def test_combined_filter_layer_and_unclassified(self, sample_findings):
        """Test combining layer and unclassified filters."""
        result = filter_findings(sample_findings, layer="orders", unclassified=True)
        assert len(result) == 1
        assert result[0].id == "FIND-003"

    def test_combined_filter_layer_and_bugs(self, sample_findings):
        """Test combining layer and bugs filters."""
        result = filter_findings(sample_findings, layer="signals", bugs=True)
        assert len(result) == 1
        assert result[0].id == "FIND-002"

    def test_no_filters_returns_all(self, sample_findings):
        """Test that no filters returns all findings."""
        result = filter_findings(sample_findings)
        assert len(result) == 5

    def test_filter_empty_list(self):
        """Test filtering empty list."""
        result = filter_findings([], layer="data")
        assert result == []

    def test_filter_no_matches(self, sample_findings):
        """Test filter with no matches."""
        result = filter_findings(sample_findings, layer="broker")
        assert result == []

    def test_multiple_status_filters_as_or(self, sample_findings):
        """Test that multiple status filters act as OR."""
        result = filter_findings(sample_findings, bugs=True, design=True)
        assert len(result) == 2
        classifications = {f.classification for f in result}
        assert classifications == {"BUG", "DESIGN"}


class TestFindIndexById:
    """Tests for find_index_by_id function."""

    def test_find_existing_finding(self, sample_findings):
        """Test finding existing finding by ID."""
        idx = find_index_by_id(sample_findings, "FIND-003")
        assert idx == 2

    def test_find_first_finding(self, sample_findings):
        """Test finding first finding by ID."""
        idx = find_index_by_id(sample_findings, "FIND-001")
        assert idx == 0

    def test_find_last_finding(self, sample_findings):
        """Test finding last finding by ID."""
        idx = find_index_by_id(sample_findings, "FIND-005")
        assert idx == 4

    def test_find_nonexistent_returns_zero(self, sample_findings):
        """Test that nonexistent ID returns 0."""
        idx = find_index_by_id(sample_findings, "FIND-999")
        assert idx == 0

    def test_find_in_empty_list(self):
        """Test finding in empty list."""
        idx = find_index_by_id([], "FIND-001")
        assert idx == 0


class TestFormatFindingPresentation:
    """Tests for format_finding_presentation function."""

    def test_basic_presentation(self, sample_findings):
        """Test basic finding presentation."""
        output = format_finding_presentation(sample_findings[0], 0, 5)

        assert "FIND-001" in output
        assert "data" in output
        assert "Data mismatch at bar 100" in output
        assert "100.5" in output
        assert "100.0" in output
        assert "unclassified" in output

    def test_presentation_includes_actions(self, sample_findings):
        """Test that presentation includes action menu."""
        output = format_finding_presentation(sample_findings[0], 0, 5)

        assert "[b] Classify as BUG" in output
        assert "[d] Classify as DESIGN" in output
        assert "[s] Skip" in output
        assert "[v] View source code" in output
        assert "[c] View comparison context" in output
        assert "[n] Next finding" in output
        assert "[p] Previous finding" in output
        assert "[q] Quit" in output

    def test_presentation_with_classification(self, sample_findings):
        """Test presentation of classified finding."""
        output = format_finding_presentation(sample_findings[1], 1, 5)

        assert "BUG" in output
        assert "Off by one error" in output
        assert "developer" in output

    def test_presentation_with_context(self, sample_findings):
        """Test presentation with context information."""
        context = InvestigationContext(
            previous_bar_timestamp="2020-03-15T09:29:00",
            next_bar_timestamp="2020-03-15T09:31:00",
            related_signal="buy_signal = True",
            related_order_type="MARKET",
            tolerance_config="0 (exact match)",
        )
        output = format_finding_presentation(sample_findings[0], 0, 5, context)

        assert "Context:" in output
        assert "Previous bar: 2020-03-15T09:29:00" in output
        assert "Next bar: 2020-03-15T09:31:00" in output
        assert "Signal: buy_signal = True" in output
        assert "Order type: MARKET" in output
        assert "Tolerance: 0 (exact match)" in output

    def test_presentation_difference_calculation(self, sample_findings):
        """Test that difference is calculated for numeric values."""
        output = format_finding_presentation(sample_findings[0], 0, 5)

        # Difference should be 0.5 (|100.5 - 100.0|)
        assert "Difference:" in output
        assert "0.5" in output


class TestGetUnclassifiedCount:
    """Tests for get_unclassified_count function."""

    def test_count_unclassified(self, sample_findings):
        """Test counting unclassified findings."""
        count = get_unclassified_count(sample_findings)
        assert count == 3  # FIND-001, FIND-003, FIND-005

    def test_count_all_classified(self):
        """Test count when all are classified."""
        findings = [
            Finding(id="F1", layer="data", description="Test", classification="BUG"),
            Finding(id="F2", layer="data", description="Test", classification="DESIGN"),
        ]
        count = get_unclassified_count(findings)
        assert count == 0

    def test_count_empty_list(self):
        """Test count of empty list."""
        count = get_unclassified_count([])
        assert count == 0


class TestGetProgressIndicator:
    """Tests for get_progress_indicator function."""

    def test_progress_indicator_format(self, sample_findings):
        """Test progress indicator format."""
        progress = get_progress_indicator(sample_findings, 0)
        assert "1/5" in progress
        assert "3 unclassified" in progress

    def test_progress_indicator_middle(self, sample_findings):
        """Test progress indicator in middle of list."""
        progress = get_progress_indicator(sample_findings, 2)
        assert "3/5" in progress

    def test_progress_indicator_last(self, sample_findings):
        """Test progress indicator at end of list."""
        progress = get_progress_indicator(sample_findings, 4)
        assert "5/5" in progress


@pytest.mark.investigation
class TestInvestigateCLICommand:
    """Tests for the investigate CLI command."""

    def test_investigate_command_exists(self):
        """Test that investigate command is registered."""
        runner = CliRunner()
        result = runner.invoke(main, ["investigate", "--help"])

        assert result.exit_code == 0
        assert "session_id" in result.output.lower()
        assert "--finding" in result.output
        assert "--layer" in result.output
        assert "--unclassified" in result.output
        assert "--bugs" in result.output
        assert "--design" in result.output

    def test_investigate_session_not_found(self):
        """Test investigate with nonexistent session."""
        runner = CliRunner()
        result = runner.invoke(main, ["investigate", "nonexistent-session"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_investigate_layer_choices(self):
        """Test that layer option has correct choices."""
        runner = CliRunner()
        result = runner.invoke(main, ["investigate", "--help"])

        # Check that all valid layers are shown
        assert "data" in result.output
        assert "signals" in result.output
        assert "orders" in result.output
        assert "broker" in result.output
        assert "portfolio" in result.output

    def test_investigate_invalid_layer(self):
        """Test that invalid layer is rejected."""
        runner = CliRunner()
        # Invalid layer should be rejected by Click's Choice validator before session load
        result = runner.invoke(main, ["investigate", "test-session", "--layer", "invalid"])

        assert result.exit_code != 0
        assert "Invalid value" in result.output or "invalid" in result.output.lower()

    def test_investigate_no_findings_after_filter(self, tmp_path):
        """Test investigate when no findings match filters."""
        from rustybt.validation.models import Session
        from rustybt.validation.session import SessionManager

        # Create a real session with findings
        sm = SessionManager(sessions_dir=tmp_path)
        session = Session(
            id="test-session",
            created_at=datetime.now(),
            strategy_name="test_strategy",
            rustybt_version="0.3.4",
            backtrader_version="1.9.78",
            python_version="3.12.0",
            status="IN_PROGRESS",
            data_fixture=Path("test.parquet"),
            findings=[
                Finding(id="F1", layer="data", description="Test", classification="BUG")
            ],
        )
        sm._save_session(session)

        runner = CliRunner()
        with runner.isolated_filesystem():
            # Copy session to isolated filesystem
            import shutil
            shutil.copytree(tmp_path, "validation-sessions")

            result = runner.invoke(main, ["investigate", "test-session", "--layer", "signals"])

        assert result.exit_code == 0
        assert "No findings match" in result.output

    def test_investigate_shows_layer_counts_on_no_match(self, tmp_path):
        """Test that layer counts are shown when no findings match."""
        from rustybt.validation.models import Session
        from rustybt.validation.session import SessionManager

        # Create a real session with findings
        sm = SessionManager(sessions_dir=tmp_path)
        session = Session(
            id="test-session",
            created_at=datetime.now(),
            strategy_name="test_strategy",
            rustybt_version="0.3.4",
            backtrader_version="1.9.78",
            python_version="3.12.0",
            status="IN_PROGRESS",
            data_fixture=Path("test.parquet"),
            findings=[
                Finding(id="F1", layer="data", description="Test1"),
                Finding(id="F2", layer="data", description="Test2"),
                Finding(id="F3", layer="orders", description="Test3"),
            ],
        )
        sm._save_session(session)

        runner = CliRunner()
        with runner.isolated_filesystem():
            import shutil
            shutil.copytree(tmp_path, "validation-sessions")

            result = runner.invoke(main, ["investigate", "test-session", "--layer", "signals"])

        assert "No findings match" in result.output
        assert "3 total finding" in result.output

    def test_investigate_quit_action(self, tmp_path):
        """Test quitting investigation."""
        from rustybt.validation.models import Session
        from rustybt.validation.session import SessionManager

        # Create a real session with findings
        sm = SessionManager(sessions_dir=tmp_path)
        session = Session(
            id="test-session",
            created_at=datetime.now(),
            strategy_name="test_strategy",
            rustybt_version="0.3.4",
            backtrader_version="1.9.78",
            python_version="3.12.0",
            status="IN_PROGRESS",
            data_fixture=Path("test.parquet"),
            findings=[
                Finding(id="F1", layer="data", description="Test finding")
            ],
        )
        sm._save_session(session)

        runner = CliRunner()
        with runner.isolated_filesystem():
            import shutil
            shutil.copytree(tmp_path, "validation-sessions")

            # Simulate user pressing 'q' to quit
            result = runner.invoke(main, ["investigate", "test-session"], input="q\n")

        assert result.exit_code == 0
        assert "Exiting investigation" in result.output


class TestInvestigationContext:
    """Tests for InvestigationContext dataclass."""

    def test_context_defaults(self):
        """Test that context has None defaults."""
        context = InvestigationContext()

        assert context.previous_bar_timestamp is None
        assert context.next_bar_timestamp is None
        assert context.related_signal is None
        assert context.related_order_type is None
        assert context.tolerance_config is None

    def test_context_with_values(self):
        """Test context with all values set."""
        context = InvestigationContext(
            previous_bar_timestamp="2020-03-15T09:29:00",
            next_bar_timestamp="2020-03-15T09:31:00",
            related_signal="buy_signal",
            related_order_type="MARKET",
            tolerance_config="0.01",
        )

        assert context.previous_bar_timestamp == "2020-03-15T09:29:00"
        assert context.next_bar_timestamp == "2020-03-15T09:31:00"
        assert context.related_signal == "buy_signal"
        assert context.related_order_type == "MARKET"
        assert context.tolerance_config == "0.01"
