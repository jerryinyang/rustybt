"""
Pytest fixtures for audit infrastructure.

Provides fixtures to:
- Load all findings from YAML files
- Filter findings by severity, module, or status
- Validate findings schema
- Get counts by severity
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.live.audit.models import (
    Category,
    FindingsFile,
    Severity,
    Status,
)

if TYPE_CHECKING:
    from collections.abc import Callable


# Path to findings directory
FINDINGS_DIR = Path(__file__).parent / "findings"


@pytest.fixture
def findings_dir() -> Path:
    """Return the path to the findings directory."""
    return FINDINGS_DIR


@pytest.fixture
def load_all_findings() -> Callable[[], list[FindingsFile]]:
    """Fixture factory to load all findings from all YAML files."""

    def _load() -> list[FindingsFile]:
        findings_files = []
        for yaml_file in FINDINGS_DIR.glob("*.yaml"):
            findings_files.append(FindingsFile.load_from_yaml(yaml_file))
        return findings_files

    return _load


@pytest.fixture
def all_findings(load_all_findings: Callable[[], list[FindingsFile]]) -> FindingsFile:
    """Load all findings from all YAML files into a single FindingsFile."""
    all_files = load_all_findings()
    combined = FindingsFile()
    for ff in all_files:
        combined.findings.extend(ff.findings)
    return combined


@pytest.fixture
def core_findings() -> FindingsFile:
    """Load findings from core_findings.yaml."""
    return FindingsFile.load_from_yaml(FINDINGS_DIR / "core_findings.yaml")


@pytest.fixture
def brokers_findings() -> FindingsFile:
    """Load findings from brokers_findings.yaml."""
    return FindingsFile.load_from_yaml(FINDINGS_DIR / "brokers_findings.yaml")


@pytest.fixture
def streaming_findings() -> FindingsFile:
    """Load findings from streaming_findings.yaml."""
    return FindingsFile.load_from_yaml(FINDINGS_DIR / "streaming_findings.yaml")


@pytest.fixture
def findings_by_severity() -> Callable[[Severity], list]:
    """Fixture factory to filter findings by severity."""

    def _filter(severity: Severity) -> list:
        all_files = []
        for yaml_file in FINDINGS_DIR.glob("*.yaml"):
            ff = FindingsFile.load_from_yaml(yaml_file)
            all_files.extend(ff.filter_by_severity(severity))
        return all_files

    return _filter


@pytest.fixture
def findings_by_status() -> Callable[[Status], list]:
    """Fixture factory to filter findings by status."""

    def _filter(status: Status) -> list:
        all_files = []
        for yaml_file in FINDINGS_DIR.glob("*.yaml"):
            ff = FindingsFile.load_from_yaml(yaml_file)
            all_files.extend(ff.filter_by_status(status))
        return all_files

    return _filter


@pytest.fixture
def findings_by_module() -> Callable[[str], list]:
    """Fixture factory to filter findings by module path prefix."""

    def _filter(module_path: str) -> list:
        all_files = []
        for yaml_file in FINDINGS_DIR.glob("*.yaml"):
            ff = FindingsFile.load_from_yaml(yaml_file)
            all_files.extend(ff.filter_by_module(module_path))
        return all_files

    return _filter


@pytest.fixture
def findings_by_category() -> Callable[[Category], list]:
    """Fixture factory to filter findings by category."""

    def _filter(category: Category) -> list:
        all_files = []
        for yaml_file in FINDINGS_DIR.glob("*.yaml"):
            ff = FindingsFile.load_from_yaml(yaml_file)
            all_files.extend(ff.filter_by_category(category))
        return all_files

    return _filter


@pytest.fixture
def severity_counts() -> Callable[[], dict[Severity, int]]:
    """Fixture factory to get counts by severity level."""

    def _counts() -> dict[Severity, int]:
        totals = {s: 0 for s in Severity}
        for yaml_file in FINDINGS_DIR.glob("*.yaml"):
            ff = FindingsFile.load_from_yaml(yaml_file)
            for severity, count in ff.severity_counts().items():
                totals[severity] += count
        return totals

    return _counts


@pytest.fixture
def validate_findings_schema() -> Callable[[Path], bool]:
    """Fixture factory to validate a findings YAML file against schema."""

    def _validate(findings_path: Path) -> bool:
        try:
            FindingsFile.load_from_yaml(findings_path)
            return True
        except Exception:
            return False

    return _validate


@pytest.fixture
def open_critical_high_count() -> Callable[[], int]:
    """Count all open CRITICAL and HIGH findings."""

    def _count() -> int:
        count = 0
        for yaml_file in FINDINGS_DIR.glob("*.yaml"):
            ff = FindingsFile.load_from_yaml(yaml_file)
            for finding in ff.findings:
                if finding.status == Status.OPEN and finding.severity in (
                    Severity.CRITICAL,
                    Severity.HIGH,
                ):
                    count += 1
        return count

    return _count
