"""
Tests for manual code review findings.

Validates that:
- Manual review findings file is valid YAML
- All findings have proper category classification
- Findings cover expected control flow areas
"""

from __future__ import annotations

import pytest

from tests.live.audit.conftest import FINDINGS_DIR
from tests.live.audit.models import Category, FindingsFile, FoundBy, Severity


class TestManualReviewFindingsFile:
    """Test manual_review_findings.yaml validity."""

    def test_manual_review_findings_file_exists(self) -> None:
        """Verify manual_review_findings.yaml exists."""
        assert (FINDINGS_DIR / "manual_review_findings.yaml").exists()

    def test_manual_review_findings_is_valid_yaml(self) -> None:
        """Verify manual_review_findings.yaml is valid and parseable."""
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "manual_review_findings.yaml")
        assert ff is not None

    def test_manual_review_findings_has_findings(self) -> None:
        """Verify manual_review_findings.yaml has at least one finding."""
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "manual_review_findings.yaml")
        assert len(ff.findings) > 0

    def test_all_findings_have_manual_review_source(self) -> None:
        """Verify all findings are from manual review."""
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "manual_review_findings.yaml")
        for finding in ff.findings:
            assert (
                finding.found_by == FoundBy.MANUAL_REVIEW
            ), f"Finding {finding.id} not from manual_review"


class TestManualReviewCategories:
    """Test that findings cover required control flow areas."""

    def test_has_state_management_findings(self) -> None:
        """Verify findings include state management issues."""
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "manual_review_findings.yaml")
        state_findings = ff.filter_by_category(Category.STATE_MANAGEMENT)
        assert len(state_findings) > 0, "Expected state_management findings"

    def test_has_concurrency_findings(self) -> None:
        """Verify findings include concurrency issues."""
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "manual_review_findings.yaml")
        concurrency_findings = ff.filter_by_category(Category.CONCURRENCY)
        assert len(concurrency_findings) > 0, "Expected concurrency findings"

    def test_has_reconnection_logic_findings(self) -> None:
        """Verify findings include reconnection logic issues."""
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "manual_review_findings.yaml")
        reconnection_findings = ff.filter_by_category(Category.RECONNECTION_LOGIC)
        assert len(reconnection_findings) > 0, "Expected reconnection_logic findings"

    def test_has_error_handling_findings(self) -> None:
        """Verify findings include error handling issues."""
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "manual_review_findings.yaml")
        error_findings = ff.filter_by_category(Category.ERROR_HANDLING)
        assert len(error_findings) > 0, "Expected error_handling findings"


class TestManualReviewSeverity:
    """Test severity distribution in manual review findings."""

    def test_has_high_severity_findings(self) -> None:
        """Verify HIGH severity findings exist."""
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "manual_review_findings.yaml")
        high_findings = ff.filter_by_severity(Severity.HIGH)
        assert len(high_findings) > 0, "Expected HIGH severity findings from manual review"

    def test_has_medium_severity_findings(self) -> None:
        """Verify MEDIUM severity findings exist."""
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "manual_review_findings.yaml")
        medium_findings = ff.filter_by_severity(Severity.MEDIUM)
        assert len(medium_findings) > 0, "Expected MEDIUM severity findings from manual review"


class TestManualReviewModuleCoverage:
    """Test that findings cover key control flow modules."""

    def test_covers_order_manager(self) -> None:
        """Verify findings include order_manager.py issues."""
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "manual_review_findings.yaml")
        order_findings = ff.filter_by_module("rustybt/live/order_manager.py")
        assert len(order_findings) > 0, "Expected order_manager.py findings"

    def test_covers_state_manager(self) -> None:
        """Verify findings include state_manager.py issues."""
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "manual_review_findings.yaml")
        state_findings = ff.filter_by_module("rustybt/live/state_manager.py")
        assert len(state_findings) > 0, "Expected state_manager.py findings"

    def test_covers_streaming_base(self) -> None:
        """Verify findings include streaming/base.py issues."""
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "manual_review_findings.yaml")
        streaming_findings = ff.filter_by_module("rustybt/live/streaming/base.py")
        assert len(streaming_findings) > 0, "Expected streaming/base.py findings"

    def test_covers_engine(self) -> None:
        """Verify findings include engine.py issues."""
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "manual_review_findings.yaml")
        engine_findings = ff.filter_by_module("rustybt/live/engine.py")
        assert len(engine_findings) > 0, "Expected engine.py findings"

    def test_covers_circuit_breakers(self) -> None:
        """Verify findings include circuit_breakers.py issues."""
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "manual_review_findings.yaml")
        cb_findings = ff.filter_by_module("rustybt/live/circuit_breakers.py")
        assert len(cb_findings) > 0, "Expected circuit_breakers.py findings"
