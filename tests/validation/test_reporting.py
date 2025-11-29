"""Tests for validation reporting module."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from rustybt.validation.models import Finding, Session, SessionStage
from rustybt.validation.reporting import (
    CommonPattern,
    LayerReportGenerator,
    LAYER_NUMBERS,
    ReportGenerator,
    StrategyReportGenerator,
    STRATEGY_DISPLAY_NAMES,
)


@pytest.fixture
def sample_session() -> Session:
    """Create a sample session for testing."""
    return Session(
        id="20251124-143000-000000-sma_crossover",
        created_at=datetime(2025, 11, 24, 14, 30, 0),
        strategy_name="sma_crossover",
        rustybt_version="0.3.4",
        backtrader_version="1.9.78",
        python_version="3.12.0",
        status="COMPLETED",
        data_fixture=Path("fixtures/validation_data.parquet"),
        layers_completed=["data", "signals", "orders", "broker", "portfolio"],
    )


@pytest.fixture
def sample_finding_bug() -> Finding:
    """Create a sample BUG finding."""
    return Finding(
        id="FIND-001",
        layer="orders",
        description="Order execution timing differs between frameworks",
        classification="BUG",
        rationale="rustybt processes orders one bar later than Backtrader",
        severity="Major",
        affected_components=["rustybt/broker/execution.py"],
        suggested_fix="Adjust order timing in execution loop",
        resolved=False,
        rustybt_value="2025-01-02",
        backtrader_value="2025-01-01",
    )


@pytest.fixture
def sample_finding_design() -> Finding:
    """Create a sample DESIGN finding."""
    return Finding(
        id="FIND-002",
        layer="signals",
        description="RSI smoothing method differs",
        classification="DESIGN",
        rationale="Both implementations are valid",
        design_rationale="rustybt uses Wilder's smoothing, Backtrader uses EMA",
        design_choice="either_valid",
        user_impact="Minor numerical differences in RSI values",
        documentation_ref="docs/design-differences.md#rsi-smoothing",
        rustybt_value="70.5",
        backtrader_value="71.2",
    )


@pytest.fixture
def sample_finding_unclassified() -> Finding:
    """Create a sample unclassified finding."""
    return Finding(
        id="FIND-003",
        layer="portfolio",
        description="Minor portfolio value difference at end of day",
        classification=None,
        rustybt_value="10000.50",
        backtrader_value="10000.48",
    )


@pytest.fixture
def session_with_findings(
    sample_session: Session,
    sample_finding_bug: Finding,
    sample_finding_design: Finding,
    sample_finding_unclassified: Finding,
) -> Session:
    """Create a session with multiple findings."""
    sample_session.findings = [
        sample_finding_bug,
        sample_finding_design,
        sample_finding_unclassified,
    ]
    return sample_session


class TestReportGenerator:
    """Test suite for ReportGenerator class."""

    def test_init_sets_session_and_timestamp(self, sample_session: Session) -> None:
        """Test ReportGenerator initializes with session and timestamp."""
        generator = ReportGenerator(sample_session)

        assert generator.session == sample_session
        assert generator.generated_at is not None
        assert isinstance(generator.generated_at, datetime)

    def test_generate_markdown_basic_structure(self, sample_session: Session) -> None:
        """Test markdown report has required sections."""
        generator = ReportGenerator(sample_session)
        report = generator.generate_markdown()

        # Check header section
        assert "# Validation Session Report" in report
        assert sample_session.id in report
        assert sample_session.strategy_name in report
        assert sample_session.status in report

        # Check sections exist
        assert "## Summary" in report
        assert "## Layer Results" in report

    def test_generate_markdown_with_findings(
        self, session_with_findings: Session
    ) -> None:
        """Test markdown report includes all findings."""
        generator = ReportGenerator(session_with_findings)
        report = generator.generate_markdown()

        # Check findings detail section exists
        assert "## Findings Detail" in report

        # Check each finding is included
        for finding in session_with_findings.findings:
            assert finding.id in report
            assert finding.layer in report

    def test_generate_markdown_summary_table(
        self, session_with_findings: Session
    ) -> None:
        """Test summary table has correct counts."""
        generator = ReportGenerator(session_with_findings)
        report = generator.generate_markdown()

        # Check table structure
        assert "| Metric | Value |" in report
        assert "| Total Findings | 3 |" in report
        assert "| BUG |" in report
        assert "| DESIGN |" in report
        assert "| Unclassified | 1 |" in report

    def test_generate_markdown_layer_results(
        self, session_with_findings: Session
    ) -> None:
        """Test layer results section has all layers."""
        generator = ReportGenerator(session_with_findings)
        report = generator.generate_markdown()

        # Check all layer headings
        assert "### Layer 1: Data Handling" in report
        assert "### Layer 2: Signal Computation" in report
        assert "### Layer 3: Order Lifecycle" in report
        assert "### Layer 4: Broker Transactions" in report
        assert "### Layer 5: Portfolio Returns" in report

    def test_generate_json_format(self, sample_session: Session) -> None:
        """Test JSON report contains required fields."""
        generator = ReportGenerator(sample_session)
        report = generator.generate_json()

        # Check top-level fields
        assert report["session_id"] == sample_session.id
        assert report["strategy"] == sample_session.strategy_name
        assert report["status"] == sample_session.status
        assert "summary" in report
        assert "layers" in report
        assert "findings" in report
        assert "metadata" in report

    def test_generate_json_summary(self, session_with_findings: Session) -> None:
        """Test JSON summary has correct counts."""
        generator = ReportGenerator(session_with_findings)
        report = generator.generate_json()

        summary = report["summary"]
        assert summary["total_findings"] == 3
        assert summary["bug_count"] == 1
        assert summary["design_count"] == 1
        assert summary["unclassified_count"] == 1

    def test_generate_json_layers(self, session_with_findings: Session) -> None:
        """Test JSON layers structure."""
        generator = ReportGenerator(session_with_findings)
        report = generator.generate_json()

        layers = report["layers"]
        assert "data" in layers
        assert "signals" in layers
        assert "orders" in layers
        assert "broker" in layers
        assert "portfolio" in layers

        # Check signals layer has the DESIGN finding
        assert layers["signals"]["design_count"] == 1

    def test_generate_json_metadata(self, sample_session: Session) -> None:
        """Test JSON metadata includes version info."""
        generator = ReportGenerator(sample_session)
        report = generator.generate_json()

        metadata = report["metadata"]
        assert metadata["rustybt_version"] == sample_session.rustybt_version
        assert metadata["backtrader_version"] == sample_session.backtrader_version
        assert metadata["python_version"] == sample_session.python_version

    def test_save_markdown_creates_file(
        self, sample_session: Session, tmp_path: Path
    ) -> None:
        """Test save_markdown creates report file."""
        generator = ReportGenerator(sample_session)
        report_path = generator.save_markdown(tmp_path)

        assert report_path.exists()
        assert report_path.name == "report.md"
        assert report_path.parent == tmp_path

        # Verify content
        content = report_path.read_text()
        assert "# Validation Session Report" in content

    def test_save_json_creates_file(
        self, sample_session: Session, tmp_path: Path
    ) -> None:
        """Test save_json creates report file."""
        import json

        generator = ReportGenerator(sample_session)
        report_path = generator.save_json(tmp_path)

        assert report_path.exists()
        assert report_path.name == "report.json"

        # Verify valid JSON
        content = json.loads(report_path.read_text())
        assert content["session_id"] == sample_session.id

    def test_save_creates_directory_if_missing(
        self, sample_session: Session, tmp_path: Path
    ) -> None:
        """Test save methods create directory if it doesn't exist."""
        nested_dir = tmp_path / "nested" / "directory"
        generator = ReportGenerator(sample_session)

        report_path = generator.save_markdown(nested_dir)

        assert report_path.exists()
        assert nested_dir.exists()

    def test_markdown_bug_finding_details(
        self, sample_session: Session, sample_finding_bug: Finding
    ) -> None:
        """Test markdown includes BUG-specific fields."""
        sample_session.findings = [sample_finding_bug]
        generator = ReportGenerator(sample_session)
        report = generator.generate_markdown()

        assert "**Severity:** Major" in report
        assert "rustybt/broker/execution.py" in report
        assert "**Status:** Open" in report

    def test_markdown_design_finding_details(
        self, sample_session: Session, sample_finding_design: Finding
    ) -> None:
        """Test markdown includes DESIGN-specific fields."""
        sample_session.findings = [sample_finding_design]
        generator = ReportGenerator(sample_session)
        report = generator.generate_markdown()

        assert "**Design Rationale:**" in report
        assert "**Preferred Approach:** either_valid" in report
        assert "**Documentation:**" in report

    def test_json_finding_serialization(
        self, sample_session: Session, sample_finding_bug: Finding
    ) -> None:
        """Test findings are properly serialized in JSON."""
        sample_session.findings = [sample_finding_bug]
        generator = ReportGenerator(sample_session)
        report = generator.generate_json()

        findings = report["findings"]
        assert len(findings) == 1

        finding = findings[0]
        assert finding["id"] == "FIND-001"
        assert finding["layer"] == "orders"
        assert finding["classification"] == "BUG"
        assert finding["severity"] == "Major"

    def test_empty_session_no_findings_section(
        self, sample_session: Session
    ) -> None:
        """Test markdown omits findings detail section when no findings."""
        generator = ReportGenerator(sample_session)
        report = generator.generate_markdown()

        assert "## Findings Detail" not in report

    def test_layer_status_pending_when_not_completed(
        self, sample_session: Session
    ) -> None:
        """Test layer shows PENDING status when not in layers_completed."""
        sample_session.layers_completed = ["data", "signals"]  # Only 2 layers
        generator = ReportGenerator(sample_session)
        report = generator.generate_markdown()

        # Orders layer should be pending
        assert "PENDING" in report

    def test_resolved_bug_shows_fixed_status(
        self, sample_session: Session, sample_finding_bug: Finding
    ) -> None:
        """Test resolved BUG shows correct status."""
        sample_finding_bug.resolved = True
        sample_finding_bug.resolved_at = datetime(2025, 11, 25, 10, 0, 0)
        sample_finding_bug.regression_test = "tests/regression/test_order_timing.py"
        sample_session.findings = [sample_finding_bug]

        generator = ReportGenerator(sample_session)
        report = generator.generate_markdown()

        assert "**Status:** Resolved" in report
        assert "**Resolved At:** 2025-11-25 10:00" in report
        assert "tests/regression/test_order_timing.py" in report


class TestReportGeneratorEdgeCases:
    """Test edge cases and error handling."""

    def test_session_with_no_layers_completed(self, sample_session: Session) -> None:
        """Test report handles session with no completed layers."""
        sample_session.layers_completed = []
        generator = ReportGenerator(sample_session)
        report = generator.generate_markdown()

        assert "Layers Passed | 0/5" in report

    def test_session_in_progress_status(self, sample_session: Session) -> None:
        """Test report handles IN_PROGRESS session."""
        sample_session.status = "IN_PROGRESS"
        generator = ReportGenerator(sample_session)
        report = generator.generate_markdown()

        assert "**Status:** IN_PROGRESS" in report

    def test_long_description_truncated_in_table(
        self, sample_session: Session
    ) -> None:
        """Test long finding descriptions are truncated in summary tables."""
        long_desc = "A" * 100  # 100 character description
        finding = Finding(
            id="FIND-LONG",
            layer="data",
            description=long_desc,
            classification="DESIGN",
            design_rationale=long_desc,  # Full description in rationale
        )
        sample_session.findings = [finding]
        sample_session.layers_completed = ["data"]

        generator = ReportGenerator(sample_session)
        report = generator.generate_markdown()

        # Table row should have truncated description (50 chars)
        assert "..." in report
        # Full description should be in design_rationale field
        assert long_desc in report

    def test_special_characters_in_description(
        self, sample_session: Session
    ) -> None:
        """Test report handles special characters in descriptions."""
        finding = Finding(
            id="FIND-SPECIAL",
            layer="data",
            description="Values differ: $100.00 vs $99.99 | >5% difference",
            classification="BUG",
        )
        sample_session.findings = [finding]
        sample_session.layers_completed = ["data"]

        generator = ReportGenerator(sample_session)
        report = generator.generate_markdown()

        assert "$100.00" in report
        assert ">5%" in report


class TestLayerReportGenerator:
    """Test suite for LayerReportGenerator class."""

    @pytest.fixture
    def mock_session_manager(self) -> MagicMock:
        """Create a mock session manager."""
        return MagicMock()

    @pytest.fixture
    def sample_sessions(self) -> list[Session]:
        """Create sample sessions with findings for testing."""
        session1 = Session(
            id="20251124-143000-000000-sma_crossover",
            created_at=datetime(2025, 11, 24, 14, 30, 0),
            strategy_name="sma_crossover",
            rustybt_version="0.3.4",
            backtrader_version="1.9.78",
            python_version="3.12.0",
            status="COMPLETED",
            data_fixture=Path("fixtures/test.parquet"),
            stage=SessionStage.COMPLETED,
            layers_completed=["data", "signals", "orders", "broker", "portfolio"],
            findings=[
                Finding(
                    id="FIND-S1-001",
                    layer="signals",
                    description="RSI calculation uses Wilder's smoothing",
                    classification="DESIGN",
                    user_impact="RSI values may differ by ~0.5%",
                ),
                Finding(
                    id="FIND-S1-002",
                    layer="data",
                    description="Timestamp precision difference",
                    classification="DESIGN",
                ),
            ],
        )

        session2 = Session(
            id="20251124-150000-000000-momentum",
            created_at=datetime(2025, 11, 24, 15, 0, 0),
            strategy_name="momentum",
            rustybt_version="0.3.4",
            backtrader_version="1.9.78",
            python_version="3.12.0",
            status="COMPLETED",
            data_fixture=Path("fixtures/test.parquet"),
            stage=SessionStage.COMPLETED,
            layers_completed=["data", "signals", "orders", "broker", "portfolio"],
            findings=[
                Finding(
                    id="FIND-S2-001",
                    layer="signals",
                    description="RSI calculation uses Wilder's smoothing",
                    classification="DESIGN",
                    user_impact="RSI values may differ by ~0.5%",
                ),
            ],
        )

        session3 = Session(
            id="20251124-160000-000000-mean_reversion",
            created_at=datetime(2025, 11, 24, 16, 0, 0),
            strategy_name="mean_reversion",
            rustybt_version="0.3.4",
            backtrader_version="1.9.78",
            python_version="3.12.0",
            status="COMPLETED",
            data_fixture=Path("fixtures/test.parquet"),
            stage=SessionStage.COMPLETED,
            layers_completed=["data", "signals", "orders", "broker", "portfolio"],
            findings=[],
        )

        return [session1, session2, session3]

    def test_init_with_valid_layer(self, mock_session_manager: MagicMock) -> None:
        """Test LayerReportGenerator initializes with valid layer."""
        generator = LayerReportGenerator("signals", mock_session_manager)

        assert generator.layer == "signals"
        assert generator.session_manager == mock_session_manager
        assert generator.generated_at is not None

    def test_init_with_invalid_layer(self, mock_session_manager: MagicMock) -> None:
        """Test LayerReportGenerator raises error for invalid layer."""
        with pytest.raises(ValueError, match="Invalid layer"):
            LayerReportGenerator("invalid", mock_session_manager)

    def test_generate_report_structure(
        self, mock_session_manager: MagicMock, sample_sessions: list[Session]
    ) -> None:
        """Test generated report has correct structure."""
        mock_session_manager.list_sessions.return_value = sample_sessions

        generator = LayerReportGenerator("signals", mock_session_manager)
        report = generator.generate()

        # Check header
        assert "# Layer 2: Signals - Validation Report" in report

        # Check sections
        assert "## Overview" in report
        assert "## Strategy Results" in report
        assert "## Common DESIGN Differences" in report

    def test_generate_strategy_table(
        self, mock_session_manager: MagicMock, sample_sessions: list[Session]
    ) -> None:
        """Test strategy results table is generated correctly."""
        mock_session_manager.list_sessions.return_value = sample_sessions

        generator = LayerReportGenerator("signals", mock_session_manager)
        report = generator.generate()

        # Check table headers
        assert "| Strategy | Status | Findings | Notes |" in report

        # Check strategies appear
        assert "sma_crossover" in report
        assert "momentum" in report
        assert "mean_reversion" in report

    def test_identify_common_patterns(
        self, mock_session_manager: MagicMock, sample_sessions: list[Session]
    ) -> None:
        """Test common patterns are identified across sessions."""
        mock_session_manager.list_sessions.return_value = sample_sessions

        generator = LayerReportGenerator("signals", mock_session_manager)
        findings = generator.get_layer_findings()
        patterns = generator.identify_common_patterns(findings, sample_sessions)

        # RSI finding appears in 2 strategies, should be grouped
        assert len(patterns) >= 1
        rsi_pattern = next(
            (p for p in patterns if "RSI" in p.description), None
        )
        assert rsi_pattern is not None
        assert len(rsi_pattern.affected_strategies) == 2

    def test_get_layer_findings(
        self, mock_session_manager: MagicMock, sample_sessions: list[Session]
    ) -> None:
        """Test layer findings are correctly filtered."""
        mock_session_manager.list_sessions.return_value = sample_sessions

        generator = LayerReportGenerator("signals", mock_session_manager)
        findings = generator.get_layer_findings()

        # Should get 2 signals findings (1 from each of first 2 sessions)
        assert len(findings) == 2
        for f in findings:
            assert f.layer == "signals"

    def test_save_report(
        self, mock_session_manager: MagicMock, sample_sessions: list[Session], tmp_path: Path
    ) -> None:
        """Test report is saved to correct location."""
        mock_session_manager.list_sessions.return_value = sample_sessions

        generator = LayerReportGenerator("signals", mock_session_manager)
        report_path = generator.save(tmp_path)

        assert report_path.exists()
        assert report_path.name == "layer-2-signals-report.md"

        content = report_path.read_text()
        assert "# Layer 2: Signals" in content

    def test_layer_numbers_mapping(self) -> None:
        """Test layer numbers are correctly mapped."""
        assert LAYER_NUMBERS["data"] == 1
        assert LAYER_NUMBERS["signals"] == 2
        assert LAYER_NUMBERS["orders"] == 3
        assert LAYER_NUMBERS["broker"] == 4
        assert LAYER_NUMBERS["portfolio"] == 5

    def test_empty_sessions(self, mock_session_manager: MagicMock) -> None:
        """Test report handles no completed sessions."""
        mock_session_manager.list_sessions.return_value = []

        generator = LayerReportGenerator("signals", mock_session_manager)
        report = generator.generate()

        assert "No validated strategies found" in report

    def test_no_findings_for_layer(
        self, mock_session_manager: MagicMock, sample_sessions: list[Session]
    ) -> None:
        """Test report handles layer with no findings."""
        mock_session_manager.list_sessions.return_value = sample_sessions

        generator = LayerReportGenerator("broker", mock_session_manager)
        findings = generator.get_layer_findings()

        assert len(findings) == 0

    def test_common_pattern_dataclass(self) -> None:
        """Test CommonPattern dataclass works correctly."""
        pattern = CommonPattern(
            description="RSI uses different smoothing",
            affected_strategies=["sma_crossover", "momentum"],
            user_impact="Minor numerical differences",
            workaround="None needed",
        )

        assert pattern.description == "RSI uses different smoothing"
        assert len(pattern.affected_strategies) == 2
        assert pattern.user_impact == "Minor numerical differences"


class TestLayerReportCLI:
    """Test CLI integration for layer reports."""

    @pytest.fixture
    def mock_sessions(self, tmp_path: Path) -> list[Session]:
        """Create mock sessions for CLI testing."""
        return [
            Session(
                id="20251124-143000-000000-test_strategy",
                created_at=datetime(2025, 11, 24, 14, 30, 0),
                strategy_name="test_strategy",
                rustybt_version="0.3.4",
                backtrader_version="1.9.78",
                python_version="3.12.0",
                status="COMPLETED",
                data_fixture=Path("fixtures/test.parquet"),
                stage=SessionStage.COMPLETED,
                layers_completed=["data", "signals", "orders", "broker", "portfolio"],
                findings=[
                    Finding(
                        id="FIND-001",
                        layer="signals",
                        description="Test DESIGN finding",
                        classification="DESIGN",
                    )
                ],
            )
        ]

    def test_report_command_layer_option_help(self):
        """Test report --layer option appears in help."""
        from click.testing import CliRunner
        from rustybt.validation.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["report", "--help"])

        assert result.exit_code == 0
        assert "--layer" in result.output
        assert "signals" in result.output

    def test_report_command_requires_session_or_layer(self):
        """Test report command requires session_id or --layer."""
        from click.testing import CliRunner
        from rustybt.validation.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["report"])

        assert result.exit_code == 1
        assert "SESSION_ID required" in result.output


class TestStrategyReportGenerator:
    """Test suite for StrategyReportGenerator class."""

    @pytest.fixture
    def mock_session_manager(self) -> MagicMock:
        """Create a mock session manager."""
        return MagicMock()

    @pytest.fixture
    def sma_crossover_session(self) -> Session:
        """Create a sample SMA crossover session."""
        return Session(
            id="20251124-143000-000000-sma_crossover",
            created_at=datetime(2025, 11, 24, 14, 30, 0),
            strategy_name="sma_crossover",
            rustybt_version="0.3.4",
            backtrader_version="1.9.78",
            python_version="3.12.0",
            status="COMPLETED",
            data_fixture=Path("fixtures/test.parquet"),
            stage=SessionStage.COMPLETED,
            layers_completed=["data", "signals", "orders", "broker", "portfolio"],
            findings=[],
        )

    @pytest.fixture
    def momentum_session_with_findings(self) -> Session:
        """Create a momentum session with DESIGN findings."""
        return Session(
            id="20251124-150000-000000-momentum",
            created_at=datetime(2025, 11, 24, 15, 0, 0),
            strategy_name="momentum",
            rustybt_version="0.3.4",
            backtrader_version="1.9.78",
            python_version="3.12.0",
            status="COMPLETED",
            data_fixture=Path("fixtures/test.parquet"),
            stage=SessionStage.COMPLETED,
            layers_completed=["data", "signals", "orders", "broker", "portfolio"],
            findings=[
                Finding(
                    id="FIND-001",
                    layer="signals",
                    description="RSI calculation uses Wilder's smoothing",
                    classification="DESIGN",
                    user_impact="RSI values may differ by ~0.5%",
                ),
            ],
        )

    @pytest.fixture
    def partial_session(self) -> Session:
        """Create a session with partial validation."""
        return Session(
            id="20251124-160000-000000-test_strategy",
            created_at=datetime(2025, 11, 24, 16, 0, 0),
            strategy_name="test_strategy",
            rustybt_version="0.3.4",
            backtrader_version="1.9.78",
            python_version="3.12.0",
            status="IN_PROGRESS",
            data_fixture=Path("fixtures/test.parquet"),
            stage=SessionStage.COMPARED,
            layers_completed=["data", "signals"],  # Only 2 layers
            findings=[],
        )

    def test_init_stores_strategy_name(self, mock_session_manager: MagicMock) -> None:
        """Test StrategyReportGenerator initializes with strategy name."""
        generator = StrategyReportGenerator("sma_crossover", mock_session_manager)

        assert generator.strategy_name == "sma_crossover"
        assert generator.session_manager == mock_session_manager
        assert generator.generated_at is not None

    def test_generate_report_structure(
        self, mock_session_manager: MagicMock, sma_crossover_session: Session
    ) -> None:
        """Test generated report has correct structure."""
        mock_session_manager.list_sessions.return_value = [sma_crossover_session]

        generator = StrategyReportGenerator("sma_crossover", mock_session_manager)
        report = generator.generate()

        # Check header
        assert "# SMA Crossover Strategy - Validation Report" in report

        # Check sections
        assert "## Strategy Overview" in report
        assert "## Validation Results" in report
        assert "## Recommendations" in report

    def test_generate_shows_parameters(
        self, mock_session_manager: MagicMock, sma_crossover_session: Session
    ) -> None:
        """Test report shows strategy parameters."""
        mock_session_manager.list_sessions.return_value = [sma_crossover_session]

        generator = StrategyReportGenerator("sma_crossover", mock_session_manager)
        report = generator.generate()

        assert "**Parameters:**" in report
        assert "Fast Period: 10" in report
        assert "Slow Period: 30" in report

    def test_generate_validation_table(
        self, mock_session_manager: MagicMock, sma_crossover_session: Session
    ) -> None:
        """Test validation results table shows all layers."""
        mock_session_manager.list_sessions.return_value = [sma_crossover_session]

        generator = StrategyReportGenerator("sma_crossover", mock_session_manager)
        report = generator.generate()

        # Check all layers appear
        assert "Data Handling" in report
        assert "Signal Computation" in report
        assert "Order Lifecycle" in report
        assert "Broker Transactions" in report
        assert "Portfolio Returns" in report

    def test_calculate_overall_status_validated(
        self, mock_session_manager: MagicMock, sma_crossover_session: Session
    ) -> None:
        """Test overall status is VALIDATED when all layers pass."""
        generator = StrategyReportGenerator("sma_crossover", mock_session_manager)
        status = generator.calculate_overall_status(sma_crossover_session)

        assert status == "✓ VALIDATED"

    def test_calculate_overall_status_partial(
        self, mock_session_manager: MagicMock, partial_session: Session
    ) -> None:
        """Test overall status is PARTIAL when some layers incomplete."""
        generator = StrategyReportGenerator("test_strategy", mock_session_manager)
        status = generator.calculate_overall_status(partial_session)

        assert status == "⚠ PARTIAL"

    def test_calculate_overall_status_failed(
        self, mock_session_manager: MagicMock, sma_crossover_session: Session
    ) -> None:
        """Test overall status is FAILED when unresolved BUGs exist."""
        sma_crossover_session.findings = [
            Finding(
                id="BUG-001",
                layer="orders",
                description="Order execution timing bug",
                classification="BUG",
                resolved=False,
            )
        ]

        generator = StrategyReportGenerator("sma_crossover", mock_session_manager)
        status = generator.calculate_overall_status(sma_crossover_session)

        assert status == "✗ FAILED"

    def test_generate_recommendations_from_design(
        self, mock_session_manager: MagicMock, momentum_session_with_findings: Session
    ) -> None:
        """Test recommendations are generated from DESIGN findings."""
        mock_session_manager.list_sessions.return_value = [momentum_session_with_findings]

        generator = StrategyReportGenerator("momentum", mock_session_manager)
        report = generator.generate()

        assert "## Recommendations" in report
        assert "RSI" in report
        assert "FIND-001" in report

    def test_generate_recommendations_for_bugs(
        self, mock_session_manager: MagicMock, sma_crossover_session: Session
    ) -> None:
        """Test recommendations include action required for BUGs."""
        sma_crossover_session.findings = [
            Finding(
                id="BUG-001",
                layer="orders",
                description="Order execution timing differs",
                classification="BUG",
                resolved=False,
            )
        ]
        mock_session_manager.list_sessions.return_value = [sma_crossover_session]

        generator = StrategyReportGenerator("sma_crossover", mock_session_manager)
        recommendations = generator.generate_recommendations(sma_crossover_session.findings)

        assert len(recommendations) == 1
        assert "**Action Required:**" in recommendations[0]

    def test_no_session_found(self, mock_session_manager: MagicMock) -> None:
        """Test report handles no sessions found."""
        mock_session_manager.list_sessions.return_value = []

        generator = StrategyReportGenerator("unknown_strategy", mock_session_manager)
        report = generator.generate()

        assert "No validation sessions found" in report

    def test_save_report(
        self, mock_session_manager: MagicMock, sma_crossover_session: Session, tmp_path: Path
    ) -> None:
        """Test report is saved to correct location."""
        mock_session_manager.list_sessions.return_value = [sma_crossover_session]

        generator = StrategyReportGenerator("sma_crossover", mock_session_manager)
        report_path = generator.save(tmp_path)

        assert report_path.exists()
        assert report_path.name == "strategy-sma-crossover-report.md"

        content = report_path.read_text()
        assert "# SMA Crossover Strategy" in content

    def test_findings_summary_section(
        self, mock_session_manager: MagicMock, momentum_session_with_findings: Session
    ) -> None:
        """Test findings summary section is generated."""
        mock_session_manager.list_sessions.return_value = [momentum_session_with_findings]

        generator = StrategyReportGenerator("momentum", mock_session_manager)
        report = generator.generate()

        assert "## Findings Summary" in report
        assert "### Signal Computation" in report
        assert "FIND-001" in report

    def test_strategy_display_names(self) -> None:
        """Test strategy display name mapping."""
        assert STRATEGY_DISPLAY_NAMES["sma_crossover"] == "SMA Crossover"
        assert STRATEGY_DISPLAY_NAMES["mean_reversion"] == "Mean Reversion"
        assert STRATEGY_DISPLAY_NAMES["momentum"] == "Momentum"
        assert STRATEGY_DISPLAY_NAMES["multi_factor"] == "Multi-Factor"

    def test_unknown_strategy_uses_formatted_name(
        self, mock_session_manager: MagicMock
    ) -> None:
        """Test unknown strategy uses formatted name."""
        mock_session_manager.list_sessions.return_value = []

        generator = StrategyReportGenerator("custom_strategy_name", mock_session_manager)
        report = generator.generate()

        assert "# Custom Strategy Name Strategy" in report


class TestStrategyReportCLI:
    """Test CLI integration for strategy reports."""

    def test_report_command_strategy_option_help(self):
        """Test report --strategy option appears in help."""
        from click.testing import CliRunner
        from rustybt.validation.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["report", "--help"])

        assert result.exit_code == 0
        assert "--strategy" in result.output

    def test_report_command_with_strategy(self):
        """Test report --strategy generates report."""
        from click.testing import CliRunner
        from rustybt.validation.cli import main

        runner = CliRunner()

        with runner.isolated_filesystem():
            result = runner.invoke(main, ["report", "--strategy", "sma_crossover"])

            assert result.exit_code == 0
            assert "Strategy report saved to" in result.output
            assert "sma_crossover" in result.output


# Story 7.4: StatusDashboard tests

class TestStatusDashboard:
    """Test suite for StatusDashboard class."""

    @pytest.fixture
    def mock_session_manager(self) -> MagicMock:
        """Create a mock session manager."""
        return MagicMock()

    @pytest.fixture
    def sample_completed_sessions(self) -> list[Session]:
        """Create sample completed sessions for dashboard testing."""
        session1 = Session(
            id="20251124-143000-000000-sma_crossover",
            created_at=datetime(2025, 11, 24, 14, 30, 0),
            strategy_name="sma_crossover",
            rustybt_version="0.3.4",
            backtrader_version="1.9.78",
            python_version="3.12.0",
            status="COMPLETED",
            data_fixture=Path("fixtures/test.parquet"),
            stage=SessionStage.COMPLETED,
            layers_completed=["data", "signals", "orders", "broker", "portfolio"],
            findings=[
                Finding(
                    id="FIND-001",
                    layer="signals",
                    description="RSI smoothing differs",
                    classification="DESIGN",
                ),
            ],
        )

        session2 = Session(
            id="20251124-150000-000000-momentum",
            created_at=datetime(2025, 11, 24, 15, 0, 0),
            strategy_name="momentum",
            rustybt_version="0.3.4",
            backtrader_version="1.9.78",
            python_version="3.12.0",
            status="COMPLETED",
            data_fixture=Path("fixtures/test.parquet"),
            stage=SessionStage.COMPLETED,
            layers_completed=["data", "signals", "orders", "broker", "portfolio"],
            findings=[],
        )

        return [session1, session2]

    def test_init_creates_session_manager(self) -> None:
        """Test StatusDashboard creates session manager if not provided."""
        from rustybt.validation.reporting import StatusDashboard

        # This will create a real session manager, which is fine for unit test
        dashboard = StatusDashboard(None)
        assert dashboard.session_manager is not None
        assert dashboard.generated_at is not None

    def test_get_data_returns_dashboard_data(
        self, mock_session_manager: MagicMock, sample_completed_sessions: list[Session]
    ) -> None:
        """Test get_data returns DashboardData with correct structure."""
        from rustybt.validation.reporting import StatusDashboard, DashboardData

        mock_session_manager.list_sessions.return_value = sample_completed_sessions

        dashboard = StatusDashboard(mock_session_manager)
        data = dashboard.get_data()

        assert isinstance(data, DashboardData)
        assert data.strategies_validated >= 0
        assert data.total_strategies == 4
        assert data.total_layers == 5
        assert data.total_findings >= 0

    def test_render_produces_ascii_output(
        self, mock_session_manager: MagicMock, sample_completed_sessions: list[Session]
    ) -> None:
        """Test render produces ASCII dashboard."""
        from rustybt.validation.reporting import StatusDashboard

        mock_session_manager.list_sessions.return_value = sample_completed_sessions

        dashboard = StatusDashboard(mock_session_manager)
        output = dashboard.render()

        assert "rustybt Validation Status" in output
        assert "Strategies Validated:" in output
        assert "Layer Coverage:" in output
        assert "Findings Summary:" in output
        assert "Overall Confidence:" in output

    def test_to_json_returns_dict(
        self, mock_session_manager: MagicMock, sample_completed_sessions: list[Session]
    ) -> None:
        """Test to_json returns dict with required keys."""
        from rustybt.validation.reporting import StatusDashboard

        mock_session_manager.list_sessions.return_value = sample_completed_sessions

        dashboard = StatusDashboard(mock_session_manager)
        data = dashboard.to_json()

        assert isinstance(data, dict)
        assert "generated_at" in data
        assert "strategies_validated" in data
        assert "total_strategies" in data
        assert "layers_covered" in data
        assert "findings" in data
        assert "confidence" in data
        assert "healthy" in data

    def test_is_healthy_true_when_all_validated(
        self, mock_session_manager: MagicMock
    ) -> None:
        """Test is_healthy returns True when all strategies validated and no open bugs."""
        from rustybt.validation.reporting import StatusDashboard

        # Create sessions for all expected strategies
        sessions = []
        for name in ["sma_crossover", "mean_reversion", "momentum", "multi_factor"]:
            sessions.append(Session(
                id=f"20251124-{name}",
                created_at=datetime.now(),
                strategy_name=name,
                rustybt_version="0.3.4",
                backtrader_version="1.9.78",
                python_version="3.12.0",
                status="COMPLETED",
                data_fixture=Path("fixtures/test.parquet"),
                stage=SessionStage.COMPLETED,
                layers_completed=["data", "signals", "orders", "broker", "portfolio"],
                findings=[],
            ))

        mock_session_manager.list_sessions.return_value = sessions

        dashboard = StatusDashboard(mock_session_manager)
        assert dashboard.is_healthy() is True

    def test_is_healthy_false_with_open_bugs(
        self, mock_session_manager: MagicMock, sample_completed_sessions: list[Session]
    ) -> None:
        """Test is_healthy returns False when open bugs exist."""
        from rustybt.validation.reporting import StatusDashboard

        # Add an unresolved bug
        sample_completed_sessions[0].findings.append(Finding(
            id="BUG-001",
            layer="orders",
            description="Order timing bug",
            classification="BUG",
            resolved=False,
        ))

        mock_session_manager.list_sessions.return_value = sample_completed_sessions

        dashboard = StatusDashboard(mock_session_manager)
        assert dashboard.is_healthy() is False

    def test_get_exit_code_returns_0_when_healthy(
        self, mock_session_manager: MagicMock
    ) -> None:
        """Test get_exit_code returns 0 when healthy."""
        from rustybt.validation.reporting import StatusDashboard

        sessions = []
        for name in ["sma_crossover", "mean_reversion", "momentum", "multi_factor"]:
            sessions.append(Session(
                id=f"20251124-{name}",
                created_at=datetime.now(),
                strategy_name=name,
                rustybt_version="0.3.4",
                backtrader_version="1.9.78",
                python_version="3.12.0",
                status="COMPLETED",
                data_fixture=Path("fixtures/test.parquet"),
                stage=SessionStage.COMPLETED,
                layers_completed=["data", "signals", "orders", "broker", "portfolio"],
                findings=[],
            ))

        mock_session_manager.list_sessions.return_value = sessions

        dashboard = StatusDashboard(mock_session_manager)
        assert dashboard.get_exit_code() == 0

    def test_get_exit_code_returns_1_when_unhealthy(
        self, mock_session_manager: MagicMock, sample_completed_sessions: list[Session]
    ) -> None:
        """Test get_exit_code returns 1 when unhealthy."""
        from rustybt.validation.reporting import StatusDashboard

        mock_session_manager.list_sessions.return_value = sample_completed_sessions

        dashboard = StatusDashboard(mock_session_manager)
        # Not all strategies validated, so unhealthy
        assert dashboard.get_exit_code() == 1


# Story 7.5: DocumentationGenerator tests

class TestDocumentationGenerator:
    """Test suite for DocumentationGenerator class."""

    @pytest.fixture
    def mock_session_manager(self) -> MagicMock:
        """Create a mock session manager."""
        return MagicMock()

    @pytest.fixture
    def session_with_design_findings(self) -> Session:
        """Create session with DESIGN findings."""
        return Session(
            id="20251124-143000-000000-sma_crossover",
            created_at=datetime(2025, 11, 24, 14, 30, 0),
            strategy_name="sma_crossover",
            rustybt_version="0.3.4",
            backtrader_version="1.9.78",
            python_version="3.12.0",
            status="COMPLETED",
            data_fixture=Path("fixtures/test.parquet"),
            stage=SessionStage.COMPLETED,
            layers_completed=["data", "signals", "orders", "broker", "portfolio"],
            findings=[
                Finding(
                    id="DESIGN-001",
                    layer="signals",
                    description="RSI calculation uses Wilder's smoothing",
                    classification="DESIGN",
                    design_rationale="Wilder's smoothing is more accurate for RSI",
                    user_impact="RSI values may differ by 0.5%",
                ),
                Finding(
                    id="DESIGN-002",
                    layer="data",
                    description="Timestamp precision is nanoseconds",
                    classification="DESIGN",
                    design_choice="rustybt_preferred",
                ),
            ],
        )

    @pytest.fixture
    def session_with_bug_findings(self) -> Session:
        """Create session with BUG findings."""
        return Session(
            id="20251124-143000-000000-momentum",
            created_at=datetime(2025, 11, 24, 14, 30, 0),
            strategy_name="momentum",
            rustybt_version="0.3.4",
            backtrader_version="1.9.78",
            python_version="3.12.0",
            status="COMPLETED",
            data_fixture=Path("fixtures/test.parquet"),
            stage=SessionStage.COMPLETED,
            layers_completed=["data", "signals", "orders", "broker", "portfolio"],
            findings=[
                Finding(
                    id="BUG-001",
                    layer="orders",
                    description="Order execution off by one bar",
                    classification="BUG",
                    severity="Major",
                    resolved=True,
                    resolved_at=datetime(2025, 11, 25, 10, 0, 0),
                    regression_test="tests/regression/test_order_timing.py",
                ),
            ],
        )

    def test_generate_design_differences(
        self, mock_session_manager: MagicMock, session_with_design_findings: Session
    ) -> None:
        """Test generate_design_differences creates markdown."""
        from rustybt.validation.reporting import DocumentationGenerator

        mock_session_manager.list_sessions.return_value = [session_with_design_findings]

        generator = DocumentationGenerator(mock_session_manager)
        content = generator.generate_design_differences()

        assert "# rustybt vs Backtrader: Design Differences" in content
        assert "Signal Computation" in content or "Data Handling" in content
        assert "DESIGN-001" in content
        assert "<!-- MANUAL SECTION START -->" in content

    def test_generate_bug_fixes(
        self, mock_session_manager: MagicMock, session_with_bug_findings: Session
    ) -> None:
        """Test generate_bug_fixes creates markdown."""
        from rustybt.validation.reporting import DocumentationGenerator

        mock_session_manager.list_sessions.return_value = [session_with_bug_findings]

        generator = DocumentationGenerator(mock_session_manager)
        content = generator.generate_bug_fixes()

        assert "# rustybt Bug Fixes" in content
        assert "BUG-001" in content
        assert "Resolved" in content
        assert "Regression Test" in content

    def test_generate_bug_fixes_no_bugs(self, mock_session_manager: MagicMock) -> None:
        """Test generate_bug_fixes when no bugs exist."""
        from rustybt.validation.reporting import DocumentationGenerator

        mock_session_manager.list_sessions.return_value = []

        generator = DocumentationGenerator(mock_session_manager)
        content = generator.generate_bug_fixes()

        assert "No bugs identified" in content

    def test_save_preserves_manual_sections(
        self, mock_session_manager: MagicMock, session_with_design_findings: Session, tmp_path: Path
    ) -> None:
        """Test save_design_differences preserves manual sections."""
        from rustybt.validation.reporting import DocumentationGenerator

        mock_session_manager.list_sessions.return_value = [session_with_design_findings]

        generator = DocumentationGenerator(mock_session_manager, tmp_path)

        # Create file with manual content
        output_path = tmp_path / "design-differences.md"
        manual_content = """<!-- MANUAL SECTION START -->

This is my custom note that should be preserved.

<!-- MANUAL SECTION END -->"""
        output_path.write_text(f"# Placeholder\n\n{manual_content}")

        # Regenerate
        generator.save_design_differences()

        # Check preserved
        new_content = output_path.read_text()
        assert "custom note that should be preserved" in new_content

    def test_generate_all_creates_both_files(
        self, mock_session_manager: MagicMock, session_with_design_findings: Session, tmp_path: Path
    ) -> None:
        """Test generate_all creates both documentation files."""
        from rustybt.validation.reporting import DocumentationGenerator

        mock_session_manager.list_sessions.return_value = [session_with_design_findings]

        generator = DocumentationGenerator(mock_session_manager, tmp_path)
        design_path, bugs_path = generator.generate_all()

        assert design_path.exists()
        assert bugs_path.exists()
        assert design_path.name == "design-differences.md"
        assert bugs_path.name == "bug-fixes.md"


# Story 7.6: ValidationProgress and CompletionTracker tests

class TestValidationProgress:
    """Test suite for ValidationProgress dataclass."""

    def test_calculate_returns_progress(self) -> None:
        """Test calculate returns ValidationProgress with correct values."""
        from rustybt.validation.reporting import ValidationProgress

        progress = ValidationProgress.calculate(
            validated_strategies=2,
            total_strategies=4,
            completed_layers=10,
            total_layers=20,
            resolved_findings=5,
            total_findings=10,
        )

        assert progress.strategy_completion == 0.5
        assert progress.layer_completion == 0.5
        assert progress.finding_resolution == 0.5
        # Weighted: (0.5 * 0.4) + (0.5 * 0.3) + (0.5 * 0.3) = 0.2 + 0.15 + 0.15 = 0.5
        assert progress.overall == 0.5

    def test_calculate_with_zero_findings(self) -> None:
        """Test calculate handles zero findings correctly."""
        from rustybt.validation.reporting import ValidationProgress

        progress = ValidationProgress.calculate(
            validated_strategies=4,
            total_strategies=4,
            completed_layers=20,
            total_layers=20,
            resolved_findings=0,
            total_findings=0,
        )

        # No findings = 100% resolution
        assert progress.finding_resolution == 1.0
        assert progress.overall == 1.0

    def test_calculate_with_names(self) -> None:
        """Test calculate includes strategy names."""
        from rustybt.validation.reporting import ValidationProgress

        progress = ValidationProgress.calculate(
            validated_strategies=2,
            total_strategies=4,
            completed_layers=10,
            total_layers=20,
            resolved_findings=0,
            total_findings=0,
            completed_strategy_names=["sma_crossover", "momentum"],
            incomplete_strategy_names=["mean_reversion", "multi_factor"],
            missing_layer_map={"mean_reversion": ["orders", "broker"]},
        )

        assert "sma_crossover" in progress.completed_strategies
        assert "mean_reversion" in progress.incomplete_strategies
        assert "orders" in progress.missing_layers["mean_reversion"]


class TestCompletionTracker:
    """Test suite for CompletionTracker class."""

    @pytest.fixture
    def mock_session_manager(self) -> MagicMock:
        """Create a mock session manager."""
        return MagicMock()

    def test_get_progress_returns_validation_progress(
        self, mock_session_manager: MagicMock
    ) -> None:
        """Test get_progress returns ValidationProgress."""
        from rustybt.validation.reporting import CompletionTracker, ValidationProgress

        mock_session_manager.list_sessions.return_value = []

        tracker = CompletionTracker(mock_session_manager)
        progress = tracker.get_progress()

        assert isinstance(progress, ValidationProgress)

    def test_get_incomplete_strategies(self, mock_session_manager: MagicMock) -> None:
        """Test get_incomplete_strategies returns list."""
        from rustybt.validation.reporting import CompletionTracker

        mock_session_manager.list_sessions.return_value = []

        tracker = CompletionTracker(mock_session_manager)
        incomplete = tracker.get_incomplete_strategies()

        assert isinstance(incomplete, list)
        # All strategies should be incomplete when no sessions
        assert len(incomplete) == 4

    def test_get_next_steps_returns_suggestions(
        self, mock_session_manager: MagicMock
    ) -> None:
        """Test get_next_steps returns list of suggestions."""
        from rustybt.validation.reporting import CompletionTracker

        mock_session_manager.list_sessions.return_value = []

        tracker = CompletionTracker(mock_session_manager)
        steps = tracker.get_next_steps()

        assert isinstance(steps, list)
        assert len(steps) > 0

    def test_render_produces_output(self, mock_session_manager: MagicMock) -> None:
        """Test render produces formatted output."""
        from rustybt.validation.reporting import CompletionTracker

        mock_session_manager.list_sessions.return_value = []

        tracker = CompletionTracker(mock_session_manager)
        output = tracker.render()

        assert "Validation Progress" in output
        assert "Strategies:" in output
        assert "Layers:" in output
        assert "Overall:" in output
        assert "Next Steps:" in output


# Story 7.7: NextActionsRecommender tests

class TestRecommendation:
    """Test suite for Recommendation dataclass."""

    def test_get_priority_label_high(self) -> None:
        """Test priority 1 returns HIGH."""
        from rustybt.validation.reporting import Recommendation

        rec = Recommendation(priority=1, action="Fix bug", details="", command="")
        assert rec.get_priority_label() == "HIGH"

    def test_get_priority_label_medium(self) -> None:
        """Test priority 2 returns MEDIUM."""
        from rustybt.validation.reporting import Recommendation

        rec = Recommendation(priority=2, action="Classify", details="", command="")
        assert rec.get_priority_label() == "MEDIUM"

    def test_get_priority_label_low(self) -> None:
        """Test priority 3+ returns LOW."""
        from rustybt.validation.reporting import Recommendation

        rec = Recommendation(priority=3, action="Docs", details="", command="")
        assert rec.get_priority_label() == "LOW"


class TestNextActionsRecommender:
    """Test suite for NextActionsRecommender class."""

    @pytest.fixture
    def mock_session_manager(self) -> MagicMock:
        """Create a mock session manager."""
        return MagicMock()

    def test_recommend_returns_list(self, mock_session_manager: MagicMock) -> None:
        """Test recommend returns list of Recommendations."""
        from rustybt.validation.reporting import NextActionsRecommender, Recommendation

        mock_session_manager.list_sessions.return_value = []
        mock_session_manager.find_sessions.return_value = []

        recommender = NextActionsRecommender(mock_session_manager)
        recs = recommender.recommend()

        assert isinstance(recs, list)
        for rec in recs:
            assert isinstance(rec, Recommendation)

    def test_recommend_sorted_by_priority(
        self, mock_session_manager: MagicMock
    ) -> None:
        """Test recommendations are sorted by priority."""
        from rustybt.validation.reporting import NextActionsRecommender

        mock_session_manager.list_sessions.return_value = []
        mock_session_manager.find_sessions.return_value = []

        recommender = NextActionsRecommender(mock_session_manager)
        recs = recommender.recommend()

        priorities = [r.priority for r in recs]
        assert priorities == sorted(priorities)

    def test_recommend_includes_command(
        self, mock_session_manager: MagicMock
    ) -> None:
        """Test each recommendation includes a CLI command."""
        from rustybt.validation.reporting import NextActionsRecommender

        mock_session_manager.list_sessions.return_value = []
        mock_session_manager.find_sessions.return_value = []

        recommender = NextActionsRecommender(mock_session_manager)
        recs = recommender.recommend()

        for rec in recs:
            assert rec.command != ""
            assert "rustybt-validate" in rec.command

    def test_render_produces_output(self, mock_session_manager: MagicMock) -> None:
        """Test render produces formatted output."""
        from rustybt.validation.reporting import NextActionsRecommender

        mock_session_manager.list_sessions.return_value = []
        mock_session_manager.find_sessions.return_value = []

        recommender = NextActionsRecommender(mock_session_manager)
        output = recommender.render()

        assert "Recommended Next Actions" in output
        assert "Command:" in output


# CLI Integration Tests for Stories 7.4-7.7

class TestStatusCLI:
    """Test CLI integration for status command."""

    def test_status_command_help(self):
        """Test status command appears in help."""
        from click.testing import CliRunner
        from rustybt.validation.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["status", "--help"])

        assert result.exit_code == 0
        assert "--format" in result.output
        assert "--ci" in result.output

    def test_status_command_ascii(self):
        """Test status command with ASCII output."""
        from click.testing import CliRunner
        from rustybt.validation.cli import main

        runner = CliRunner()

        with runner.isolated_filesystem():
            result = runner.invoke(main, ["status"])

            assert result.exit_code == 0
            assert "rustybt Validation Status" in result.output

    def test_status_command_json(self):
        """Test status command with JSON output."""
        import json

        from click.testing import CliRunner
        from rustybt.validation.cli import main

        runner = CliRunner()

        with runner.isolated_filesystem():
            result = runner.invoke(main, ["status", "--format", "json"])

            assert result.exit_code == 0
            # Should be valid JSON
            data = json.loads(result.output)
            assert "strategies_validated" in data


class TestProgressCLI:
    """Test CLI integration for progress command."""

    def test_progress_command_help(self):
        """Test progress command appears in help."""
        from click.testing import CliRunner
        from rustybt.validation.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["progress", "--help"])

        assert result.exit_code == 0

    def test_progress_command_runs(self):
        """Test progress command runs successfully."""
        from click.testing import CliRunner
        from rustybt.validation.cli import main

        runner = CliRunner()

        with runner.isolated_filesystem():
            result = runner.invoke(main, ["progress"])

            assert result.exit_code == 0
            assert "Validation Progress" in result.output


class TestNextActionsCLI:
    """Test CLI integration for next-actions command."""

    def test_next_actions_command_help(self):
        """Test next-actions command appears in help."""
        from click.testing import CliRunner
        from rustybt.validation.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["next-actions", "--help"])

        assert result.exit_code == 0

    def test_next_actions_command_runs(self):
        """Test next-actions command runs successfully."""
        from click.testing import CliRunner
        from rustybt.validation.cli import main

        runner = CliRunner()

        with runner.isolated_filesystem():
            result = runner.invoke(main, ["next-actions"])

            assert result.exit_code == 0
            assert "Recommended Next Actions" in result.output


class TestDocsCLI:
    """Test CLI integration for docs commands."""

    def test_docs_generate_help(self):
        """Test docs generate command appears in help."""
        from click.testing import CliRunner
        from rustybt.validation.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["docs", "generate", "--help"])

        assert result.exit_code == 0
        assert "--output-dir" in result.output
        assert "--design-only" in result.output

    def test_docs_generate_runs(self):
        """Test docs generate command runs successfully."""
        from click.testing import CliRunner
        from rustybt.validation.cli import main

        runner = CliRunner()

        with runner.isolated_filesystem():
            result = runner.invoke(main, ["docs", "generate"])

            assert result.exit_code == 0
            assert "Generated:" in result.output

    def test_docs_preview_runs(self):
        """Test docs preview command runs successfully."""
        from click.testing import CliRunner
        from rustybt.validation.cli import main

        runner = CliRunner()

        with runner.isolated_filesystem():
            result = runner.invoke(main, ["docs", "preview"])

            assert result.exit_code == 0
            assert "rustybt vs Backtrader" in result.output
