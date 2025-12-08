"""
Tests for broker adapter static analysis audit.

Validates that:
- ruff runs without crash on broker modules
- mypy runs without crash on broker modules
- findings file is valid YAML
- All findings have exchange tags
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.live.audit.conftest import FINDINGS_DIR
from tests.live.audit.models import FindingsFile, Severity


class TestBrokersStaticAnalysis:
    """Test static analysis on broker modules."""

    def test_ruff_runs_on_broker_modules(self) -> None:
        """Verify ruff check runs without crashing on broker modules."""
        result = subprocess.run(
            ["ruff", "check", "--output-format=json", "rustybt/live/brokers/"],
            capture_output=True,
            text=True,
        )
        assert result.returncode in (0, 1), f"ruff crashed: {result.stderr}"

    def test_mypy_runs_on_broker_modules(self) -> None:
        """Verify mypy runs without crashing on broker modules."""
        result = subprocess.run(
            [
                "mypy",
                "--show-error-codes",
                "--ignore-missing-imports",
                "rustybt/live/brokers/",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode in (0, 1), f"mypy crashed: {result.stderr}"


class TestBrokersFindingsFile:
    """Test brokers_findings.yaml validity."""

    def test_brokers_findings_file_exists(self) -> None:
        """Verify brokers_findings.yaml exists."""
        assert (FINDINGS_DIR / "brokers_findings.yaml").exists()

    def test_brokers_findings_is_valid_yaml(self) -> None:
        """Verify brokers_findings.yaml is valid and parseable."""
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "brokers_findings.yaml")
        assert ff is not None

    def test_brokers_findings_has_findings(self) -> None:
        """Verify brokers_findings.yaml has at least one finding."""
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "brokers_findings.yaml")
        assert len(ff.findings) > 0

    def test_all_broker_findings_have_exchange_tag(self) -> None:
        """Verify all broker findings have exchange tag."""
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "brokers_findings.yaml")
        for finding in ff.findings:
            assert finding.exchange is not None, f"Finding {finding.id} missing exchange tag"

    def test_broker_finding_modules_are_valid(self) -> None:
        """Verify all findings reference valid broker modules."""
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "brokers_findings.yaml")
        for finding in ff.findings:
            assert finding.module.startswith(
                "rustybt/live/brokers/"
            ), f"Finding {finding.id} references non-broker module: {finding.module}"


class TestBrokersFindingsSeverity:
    """Test severity distribution in broker findings."""

    def test_severity_counts(self) -> None:
        """Verify severity counts are tracked correctly."""
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "brokers_findings.yaml")
        counts = ff.severity_counts()
        total = sum(counts.values())
        assert total > 0

    def test_high_severity_findings_exist(self) -> None:
        """Verify HIGH severity findings are captured."""
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "brokers_findings.yaml")
        high_findings = ff.filter_by_severity(Severity.HIGH)
        assert len(high_findings) > 0
