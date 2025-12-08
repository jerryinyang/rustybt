"""
Unit tests for audit infrastructure.

Tests:
- Directory structure exists
- Schema validation accepts valid findings
- Schema validation rejects invalid findings
- Fixtures load and filter correctly
- Severity counts are accurate
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from tests.live.audit.models import (
    AuditFinding,
    Category,
    FindingsFile,
    FoundBy,
    Severity,
    Status,
    get_module_code,
)


class TestDirectoryStructure:
    """Test that required directories and files exist."""

    def test_audit_directory_exists(self, findings_dir: Path) -> None:
        """Verify tests/live/audit/ directory exists."""
        audit_dir = findings_dir.parent
        assert audit_dir.exists()
        assert audit_dir.is_dir()

    def test_findings_directory_exists(self, findings_dir: Path) -> None:
        """Verify tests/live/audit/findings/ directory exists."""
        assert findings_dir.exists()
        assert findings_dir.is_dir()

    def test_init_files_exist(self, findings_dir: Path) -> None:
        """Verify __init__.py files exist."""
        audit_dir = findings_dir.parent
        assert (audit_dir / "__init__.py").exists()
        assert (findings_dir / "__init__.py").exists()

    def test_models_file_exists(self, findings_dir: Path) -> None:
        """Verify models.py exists."""
        audit_dir = findings_dir.parent
        assert (audit_dir / "models.py").exists()

    def test_conftest_exists(self, findings_dir: Path) -> None:
        """Verify conftest.py exists."""
        audit_dir = findings_dir.parent
        assert (audit_dir / "conftest.py").exists()


class TestSchemaValidation:
    """Test Pydantic schema validation."""

    def test_valid_finding_accepted(self) -> None:
        """Test that a valid finding passes validation."""
        finding = AuditFinding(
            id="AUDIT-E001",
            module="rustybt/live/engine.py",
            line=150,
            severity=Severity.CRITICAL,
            category=Category.ERROR_HANDLING,
            description="Test finding description",
            recommendation="Test recommendation",
            status=Status.OPEN,
            found_by=FoundBy.CODE_AUDIT,
            found_at=date(2025, 12, 6),
        )
        assert finding.id == "AUDIT-E001"
        assert finding.severity == Severity.CRITICAL
        assert finding.status == Status.OPEN

    def test_invalid_id_format_rejected(self) -> None:
        """Test that invalid finding ID is rejected."""
        with pytest.raises(ValueError, match="Finding ID must match pattern"):
            AuditFinding(
                id="INVALID-ID",
                module="rustybt/live/engine.py",
                severity=Severity.HIGH,
                category=Category.ERROR_HANDLING,
                description="Test",
                recommendation="Test",
                found_by=FoundBy.CODE_AUDIT,
                found_at=date(2025, 12, 6),
            )

    def test_invalid_id_missing_number_rejected(self) -> None:
        """Test that finding ID without number is rejected."""
        with pytest.raises(ValueError, match="Finding ID must match pattern"):
            AuditFinding(
                id="AUDIT-E",
                module="rustybt/live/engine.py",
                severity=Severity.HIGH,
                category=Category.ERROR_HANDLING,
                description="Test",
                recommendation="Test",
                found_by=FoundBy.CODE_AUDIT,
                found_at=date(2025, 12, 6),
            )

    def test_negative_line_number_rejected(self) -> None:
        """Test that negative line number is rejected."""
        with pytest.raises(ValueError, match="Line number must be positive"):
            AuditFinding(
                id="AUDIT-E001",
                module="rustybt/live/engine.py",
                line=-1,
                severity=Severity.HIGH,
                category=Category.ERROR_HANDLING,
                description="Test",
                recommendation="Test",
                found_by=FoundBy.CODE_AUDIT,
                found_at=date(2025, 12, 6),
            )

    def test_zero_line_number_rejected(self) -> None:
        """Test that zero line number is rejected."""
        with pytest.raises(ValueError, match="Line number must be positive"):
            AuditFinding(
                id="AUDIT-E001",
                module="rustybt/live/engine.py",
                line=0,
                severity=Severity.HIGH,
                category=Category.ERROR_HANDLING,
                description="Test",
                recommendation="Test",
                found_by=FoundBy.CODE_AUDIT,
                found_at=date(2025, 12, 6),
            )

    def test_null_line_number_accepted(self) -> None:
        """Test that null line number is accepted."""
        finding = AuditFinding(
            id="AUDIT-E001",
            module="rustybt/live/engine.py",
            line=None,
            severity=Severity.HIGH,
            category=Category.ERROR_HANDLING,
            description="Test",
            recommendation="Test",
            found_by=FoundBy.CODE_AUDIT,
            found_at=date(2025, 12, 6),
        )
        assert finding.line is None

    def test_all_severities_valid(self) -> None:
        """Test that all severity levels are valid."""
        for severity in Severity:
            finding = AuditFinding(
                id="AUDIT-E001",
                module="rustybt/live/engine.py",
                severity=severity,
                category=Category.ERROR_HANDLING,
                description="Test",
                recommendation="Test",
                found_by=FoundBy.CODE_AUDIT,
                found_at=date(2025, 12, 6),
            )
            assert finding.severity == severity

    def test_all_statuses_valid(self) -> None:
        """Test that all status values are valid."""
        for status in Status:
            finding = AuditFinding(
                id="AUDIT-E001",
                module="rustybt/live/engine.py",
                severity=Severity.HIGH,
                category=Category.ERROR_HANDLING,
                description="Test",
                recommendation="Test",
                status=status,
                found_by=FoundBy.CODE_AUDIT,
                found_at=date(2025, 12, 6),
            )
            assert finding.status == status


class TestModuleCodes:
    """Test module code mapping."""

    def test_engine_module_code(self) -> None:
        """Test engine module gets code E."""
        assert get_module_code("rustybt/live/engine.py") == "E"

    def test_order_manager_module_code(self) -> None:
        """Test order manager module gets code O."""
        assert get_module_code("rustybt/live/order_manager.py") == "O"

    def test_brokers_prefix_module_code(self) -> None:
        """Test broker adapter modules get code B."""
        assert get_module_code("rustybt/live/brokers/base.py") == "B"
        assert get_module_code("rustybt/live/brokers/paper_broker.py") == "B"

    def test_streaming_prefix_module_code(self) -> None:
        """Test streaming modules get code S."""
        assert get_module_code("rustybt/live/streaming/base.py") == "S"
        assert get_module_code("rustybt/live/streaming/bar_buffer.py") == "S"

    def test_unknown_module_code(self) -> None:
        """Test unknown module gets code U."""
        assert get_module_code("rustybt/unknown/module.py") == "U"


class TestFindingsFile:
    """Test FindingsFile loading and operations."""

    def test_load_sample_findings(self, findings_dir: Path) -> None:
        """Test loading sample findings YAML file."""
        ff = FindingsFile.load_from_yaml(findings_dir / "sample_findings.yaml")
        assert len(ff.findings) == 4

    def test_load_nonexistent_file_returns_empty(self, findings_dir: Path) -> None:
        """Test loading nonexistent file returns empty FindingsFile."""
        ff = FindingsFile.load_from_yaml(findings_dir / "nonexistent.yaml")
        assert len(ff.findings) == 0

    def test_filter_by_severity(self, findings_dir: Path) -> None:
        """Test filtering findings by severity."""
        ff = FindingsFile.load_from_yaml(findings_dir / "sample_findings.yaml")
        critical = ff.filter_by_severity(Severity.CRITICAL)
        assert len(critical) == 1
        assert critical[0].id == "AUDIT-E001"

    def test_filter_by_status(self, findings_dir: Path) -> None:
        """Test filtering findings by status."""
        ff = FindingsFile.load_from_yaml(findings_dir / "sample_findings.yaml")
        open_findings = ff.filter_by_status(Status.OPEN)
        assert len(open_findings) == 4

    def test_filter_by_module(self, findings_dir: Path) -> None:
        """Test filtering findings by module path prefix."""
        ff = FindingsFile.load_from_yaml(findings_dir / "sample_findings.yaml")
        broker_findings = ff.filter_by_module("rustybt/live/brokers/")
        assert len(broker_findings) == 1

    def test_severity_counts(self, findings_dir: Path) -> None:
        """Test severity counts are accurate."""
        ff = FindingsFile.load_from_yaml(findings_dir / "sample_findings.yaml")
        counts = ff.severity_counts()
        assert counts[Severity.CRITICAL] == 1
        assert counts[Severity.HIGH] == 1
        assert counts[Severity.MEDIUM] == 1
        assert counts[Severity.LOW] == 1


class TestFixtures:
    """Test pytest fixtures work correctly."""

    def test_all_findings_fixture(self, all_findings: FindingsFile) -> None:
        """Test all_findings fixture loads sample findings."""
        assert len(all_findings.findings) >= 4

    def test_findings_by_severity_fixture(self, findings_by_severity: callable) -> None:
        """Test findings_by_severity fixture filters correctly."""
        critical = findings_by_severity(Severity.CRITICAL)
        assert len(critical) >= 1

    def test_findings_by_status_fixture(self, findings_by_status: callable) -> None:
        """Test findings_by_status fixture filters correctly."""
        open_findings = findings_by_status(Status.OPEN)
        assert len(open_findings) >= 4

    def test_severity_counts_fixture(self, severity_counts: callable) -> None:
        """Test severity_counts fixture returns correct counts."""
        counts = severity_counts()
        assert counts[Severity.CRITICAL] >= 1
        assert counts[Severity.HIGH] >= 1

    def test_validate_findings_schema_fixture(
        self, validate_findings_schema: callable, findings_dir: Path, tmp_path: Path
    ) -> None:
        """Test validate_findings_schema fixture validates correctly."""
        assert validate_findings_schema(findings_dir / "sample_findings.yaml")
        # Nonexistent files return empty but valid FindingsFile
        assert validate_findings_schema(findings_dir / "nonexistent.yaml")
        # Create an invalid YAML file to test rejection
        invalid_file = tmp_path / "invalid.yaml"
        invalid_file.write_text("findings:\n  - id: INVALID\n    severity: WRONG")
        assert not validate_findings_schema(invalid_file)
