"""Tests for validation framework data models."""

from datetime import datetime
from pathlib import Path

import pytest

from rustybt.validation import Discrepancy, Finding, Session


class TestSession:
    """Test suite for Session model."""

    def test_session_creation_with_all_fields(self):
        """Test Session instantiation with all required fields."""
        session = Session(
            id="20251124-143000-sma_crossover",
            created_at=datetime(2025, 11, 24, 14, 30, 0),
            strategy_name="sma_crossover",
            rustybt_version="0.3.4",
            backtrader_version="1.9.78",
            python_version="3.12.0",
            status="IN_PROGRESS",
            data_fixture=Path("fixtures/validation_data.parquet"),
        )

        assert session.id == "20251124-143000-sma_crossover"
        assert session.strategy_name == "sma_crossover"
        assert session.status == "IN_PROGRESS"
        assert len(session.findings) == 0  # Default empty list

    def test_session_default_findings_list(self):
        """Test that findings defaults to empty list."""
        session = Session(
            id="test-session",
            created_at=datetime.now(),
            strategy_name="test",
            rustybt_version="0.1.0",
            backtrader_version="1.9.78",
            python_version="3.12.0",
            status="COMPLETED",
            data_fixture=Path("test.parquet"),
        )

        assert isinstance(session.findings, list)
        assert len(session.findings) == 0

    def test_session_status_literals(self):
        """Test Session with all valid status values."""
        statuses = ["IN_PROGRESS", "COMPLETED", "FAILED"]

        for status in statuses:
            session = Session(
                id=f"test-{status}",
                created_at=datetime.now(),
                strategy_name="test",
                rustybt_version="0.1.0",
                backtrader_version="1.9.78",
                python_version="3.12.0",
                status=status,  # type: ignore
                data_fixture=Path("test.parquet"),
            )
            assert session.status == status

    def test_session_with_findings(self):
        """Test Session with findings added."""
        finding = Finding(
            id="finding-001",
            layer="data",
            description="Price mismatch",
        )

        session = Session(
            id="test-session",
            created_at=datetime.now(),
            strategy_name="test",
            rustybt_version="0.1.0",
            backtrader_version="1.9.78",
            python_version="3.12.0",
            status="IN_PROGRESS",
            data_fixture=Path("test.parquet"),
            findings=[finding],
        )

        assert len(session.findings) == 1
        assert session.findings[0].id == "finding-001"


class TestFinding:
    """Test suite for Finding model."""

    def test_finding_creation_minimal(self):
        """Test Finding with only required fields."""
        finding = Finding(
            id="finding-001",
            layer="data",
            description="Price mismatch in OHLC data",
        )

        assert finding.id == "finding-001"
        assert finding.layer == "data"
        assert finding.description == "Price mismatch in OHLC data"
        assert finding.classification is None
        assert finding.rationale is None
        assert finding.investigated_by is None
        assert finding.investigated_at is None
        assert finding.resolved is False
        assert finding.rustybt_value is None
        assert finding.backtrader_value is None

    def test_finding_bug_classification(self):
        """Test Finding with BUG classification."""
        finding = Finding(
            id="finding-002",
            layer="signals",
            description="Signal timing mismatch",
            classification="BUG",
            rationale="rustybt incorrectly calculates SMA on first bar",
            investigated_by="developer",
            investigated_at=datetime(2025, 11, 24, 15, 0, 0),
            resolved=False,
            rustybt_value=100.5,
            backtrader_value=101.2,
        )

        assert finding.classification == "BUG"
        assert finding.rationale == "rustybt incorrectly calculates SMA on first bar"
        assert finding.resolved is False

    def test_finding_design_classification(self):
        """Test Finding with DESIGN classification."""
        finding = Finding(
            id="finding-003",
            layer="orders",
            description="Order fill timing differs",
            classification="DESIGN",
            rationale="rustybt uses bar-close fills, Backtrader uses next-bar-open",
            investigated_by="architect",
            investigated_at=datetime(2025, 11, 24, 15, 30, 0),
            resolved=True,
        )

        assert finding.classification == "DESIGN"
        assert finding.resolved is True

    def test_finding_all_layers(self):
        """Test Finding with all valid layer values."""
        layers = ["data", "signals", "orders", "broker", "portfolio"]

        for layer in layers:
            finding = Finding(
                id=f"finding-{layer}",
                layer=layer,  # type: ignore
                description=f"Test {layer} finding",
            )
            assert finding.layer == layer


class TestDiscrepancy:
    """Test suite for Discrepancy model."""

    def test_discrepancy_creation(self):
        """Test Discrepancy instantiation with all fields."""
        discrepancy = Discrepancy(
            layer="data",
            event="on_data",
            timestamp=datetime(2025, 1, 15, 9, 30, 0),
            asset="AAPL",
            field="close_price",
            rustybt_value=150.25,
            backtrader_value=150.26,
            tolerance=0.01,
            exceeded_by=0.01,
        )

        assert discrepancy.layer == "data"
        assert discrepancy.event == "on_data"
        assert discrepancy.asset == "AAPL"
        assert discrepancy.field == "close_price"
        assert discrepancy.rustybt_value == 150.25
        assert discrepancy.backtrader_value == 150.26
        assert discrepancy.tolerance == 0.01
        assert discrepancy.exceeded_by == 0.01

    def test_discrepancy_without_asset(self):
        """Test Discrepancy for portfolio-wide events (no specific asset)."""
        discrepancy = Discrepancy(
            layer="portfolio",
            event="portfolio_value",
            timestamp=datetime(2025, 1, 15, 16, 0, 0),
            asset=None,  # Portfolio-wide
            field="total_value",
            rustybt_value=100000.50,
            backtrader_value=100001.00,
            tolerance=1.0,
            exceeded_by=0.50,
        )

        assert discrepancy.asset is None
        assert discrepancy.layer == "portfolio"

    def test_discrepancy_tolerance_exceeded(self):
        """Test Discrepancy with tolerance exceeded by various amounts."""
        discrepancy = Discrepancy(
            layer="broker",
            event="fill_order",
            timestamp=datetime.now(),
            asset="MSFT",
            field="fill_price",
            rustybt_value=300.15,
            backtrader_value=300.20,
            tolerance=0.01,
            exceeded_by=0.05,
        )

        assert discrepancy.exceeded_by > discrepancy.tolerance


class TestModelIntegration:
    """Integration tests for models working together."""

    def test_session_with_finding_with_values(self):
        """Test complete workflow: Session → Finding → Values."""
        # Create a finding with discrepancy values
        finding = Finding(
            id="integration-finding-001",
            layer="broker",
            description="Commission calculation differs",
            classification="BUG",
            rationale="rustybt applies commission to wrong order",
            investigated_by="qa-agent",
            investigated_at=datetime.now(),
            resolved=False,
            rustybt_value={"commission": 1.50},
            backtrader_value={"commission": 1.00},
        )

        # Create session with the finding
        session = Session(
            id="20251124-150000-integration_test",
            created_at=datetime.now(),
            strategy_name="integration_test",
            rustybt_version="0.3.4",
            backtrader_version="1.9.78",
            python_version="3.12.0",
            status="IN_PROGRESS",
            data_fixture=Path("fixtures/test_data.parquet"),
            findings=[finding],
        )

        # Verify relationships
        assert len(session.findings) == 1
        assert session.findings[0].classification == "BUG"
        assert session.findings[0].rustybt_value["commission"] == 1.50
        assert session.findings[0].backtrader_value["commission"] == 1.00

    def test_multiple_findings_in_session(self):
        """Test Session with multiple findings across different layers."""
        findings = [
            Finding(id="f1", layer="data", description="Data issue"),
            Finding(id="f2", layer="signals", description="Signal issue"),
            Finding(id="f3", layer="orders", description="Order issue"),
            Finding(id="f4", layer="broker", description="Broker issue"),
            Finding(id="f5", layer="portfolio", description="Portfolio issue"),
        ]

        session = Session(
            id="test-multi-findings",
            created_at=datetime.now(),
            strategy_name="test",
            rustybt_version="0.3.4",
            backtrader_version="1.9.78",
            python_version="3.12.0",
            status="COMPLETED",
            data_fixture=Path("test.parquet"),
            findings=findings,
        )

        assert len(session.findings) == 5
        layers = [f.layer for f in session.findings]
        assert layers == ["data", "signals", "orders", "broker", "portfolio"]
