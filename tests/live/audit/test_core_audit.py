"""
Tests for core live trading module audit.

Validates that:
- ruff runs without crash on core modules
- mypy runs without crash on core modules
- findings file is valid YAML
- All findings have required fields
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.live.audit.conftest import FINDINGS_DIR
from tests.live.audit.models import FindingsFile, Severity

# Core modules to audit
CORE_MODULES = [
    "rustybt/live/engine.py",
    "rustybt/live/order_manager.py",
    "rustybt/live/state_manager.py",
    "rustybt/live/strategy_executor.py",
    "rustybt/live/reconciler.py",
    "rustybt/live/circuit_breakers.py",
    "rustybt/live/data_feed.py",
]


class TestStaticAnalysis:
    """Test that static analysis tools run successfully."""

    def test_ruff_runs_on_core_modules(self) -> None:
        """Verify ruff check runs without crashing on core modules."""
        result = subprocess.run(
            ["ruff", "check", "--output-format=json", *CORE_MODULES],
            capture_output=True,
            text=True,
        )
        # ruff returns 0 if no issues, 1 if issues found - both are OK
        assert result.returncode in (0, 1), f"ruff crashed: {result.stderr}"

    def test_mypy_runs_on_core_modules(self) -> None:
        """Verify mypy runs without crashing on core modules."""
        result = subprocess.run(
            [
                "mypy",
                "--show-error-codes",
                "--ignore-missing-imports",
                *CORE_MODULES,
            ],
            capture_output=True,
            text=True,
        )
        # mypy returns 0 if no errors, 1 if errors found - both are OK
        assert result.returncode in (0, 1), f"mypy crashed: {result.stderr}"


class TestCoreFindingsFile:
    """Test core_findings.yaml validity."""

    def test_core_findings_file_exists(self) -> None:
        """Verify core_findings.yaml exists."""
        assert (FINDINGS_DIR / "core_findings.yaml").exists()

    def test_core_findings_is_valid_yaml(self) -> None:
        """Verify core_findings.yaml is valid and parseable."""
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "core_findings.yaml")
        assert ff is not None

    def test_core_findings_has_findings(self) -> None:
        """Verify core_findings.yaml has at least one finding."""
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "core_findings.yaml")
        assert len(ff.findings) > 0

    def test_all_core_findings_have_required_fields(self) -> None:
        """Verify all findings have required fields populated."""
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "core_findings.yaml")
        for finding in ff.findings:
            assert finding.id is not None
            assert finding.module is not None
            assert finding.severity is not None
            assert finding.category is not None
            assert finding.description is not None
            assert finding.recommendation is not None
            assert finding.found_by is not None
            assert finding.found_at is not None

    def test_core_finding_ids_are_unique(self) -> None:
        """Verify all finding IDs are unique."""
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "core_findings.yaml")
        ids = [f.id for f in ff.findings]
        assert len(ids) == len(set(ids)), "Duplicate finding IDs found"

    def test_core_finding_modules_are_valid(self) -> None:
        """Verify all findings reference valid core modules."""
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "core_findings.yaml")
        valid_prefixes = [
            "rustybt/live/engine.py",
            "rustybt/live/order_manager.py",
            "rustybt/live/state_manager.py",
            "rustybt/live/strategy_executor.py",
            "rustybt/live/reconciler.py",
            "rustybt/live/circuit_breakers.py",
            "rustybt/live/data_feed.py",
        ]
        for finding in ff.findings:
            assert any(
                finding.module.startswith(prefix) for prefix in valid_prefixes
            ), f"Finding {finding.id} references invalid module: {finding.module}"


class TestCoreFindingsSeverity:
    """Test severity distribution in core findings."""

    def test_severity_counts(self) -> None:
        """Verify severity counts are tracked correctly."""
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "core_findings.yaml")
        counts = ff.severity_counts()
        # Should have at least some findings
        total = sum(counts.values())
        assert total > 0

    def test_high_severity_findings_exist(self) -> None:
        """Verify HIGH severity findings are captured (expected from mypy)."""
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "core_findings.yaml")
        high_findings = ff.filter_by_severity(Severity.HIGH)
        assert len(high_findings) > 0, "Expected HIGH severity findings from static analysis"
