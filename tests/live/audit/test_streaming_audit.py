"""
Tests for streaming adapter static analysis audit.

Validates that:
- ruff runs without crash on streaming modules
- mypy runs without crash on streaming modules
- findings file is valid YAML
- All findings have required fields
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.live.audit.conftest import FINDINGS_DIR
from tests.live.audit.models import FindingsFile, Severity


class TestStreamingStaticAnalysis:
    """Test static analysis on streaming modules."""

    def test_ruff_runs_on_streaming_modules(self) -> None:
        """Verify ruff check runs without crashing on streaming modules."""
        result = subprocess.run(
            ["ruff", "check", "--output-format=json", "rustybt/live/streaming/"],
            capture_output=True,
            text=True,
        )
        assert result.returncode in (0, 1), f"ruff crashed: {result.stderr}"

    def test_mypy_runs_on_streaming_modules(self) -> None:
        """Verify mypy runs without crashing on streaming modules."""
        result = subprocess.run(
            [
                "mypy",
                "--show-error-codes",
                "--ignore-missing-imports",
                "rustybt/live/streaming/",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode in (0, 1), f"mypy crashed: {result.stderr}"


class TestStreamingFindingsFile:
    """Test streaming_findings.yaml validity."""

    def test_streaming_findings_file_exists(self) -> None:
        """Verify streaming_findings.yaml exists."""
        assert (FINDINGS_DIR / "streaming_findings.yaml").exists()

    def test_streaming_findings_is_valid_yaml(self) -> None:
        """Verify streaming_findings.yaml is valid and parseable."""
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "streaming_findings.yaml")
        assert ff is not None

    def test_streaming_findings_has_findings(self) -> None:
        """Verify streaming_findings.yaml has at least one finding."""
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "streaming_findings.yaml")
        assert len(ff.findings) > 0

    def test_streaming_finding_modules_are_valid(self) -> None:
        """Verify all findings reference valid streaming modules."""
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "streaming_findings.yaml")
        for finding in ff.findings:
            assert finding.module.startswith(
                "rustybt/live/streaming/"
            ), f"Finding {finding.id} references non-streaming module: {finding.module}"


class TestStreamingFindingsSeverity:
    """Test severity distribution in streaming findings."""

    def test_severity_counts(self) -> None:
        """Verify severity counts are tracked correctly."""
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "streaming_findings.yaml")
        counts = ff.severity_counts()
        total = sum(counts.values())
        assert total > 0

    def test_high_severity_findings_exist(self) -> None:
        """Verify HIGH severity findings are captured from bar_buffer."""
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "streaming_findings.yaml")
        high_findings = ff.filter_by_severity(Severity.HIGH)
        assert len(high_findings) > 0
