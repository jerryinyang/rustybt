"""
Regression tests for audit findings.

These tests validate that CRITICAL/HIGH findings are correctly tracked
and will fail if findings are removed without proper resolution.

Each test documents:
- The finding ID
- The issue description
- The expected fix
"""

from __future__ import annotations

import pytest

from tests.live.audit.conftest import FINDINGS_DIR
from tests.live.audit.models import FindingsFile, Severity, Status


class TestCriticalHighFindingsTracked:
    """Test that all CRITICAL/HIGH findings are tracked in YAML files."""

    def test_engine_high_findings_count(self) -> None:
        """Verify engine HIGH findings are captured.

        Finding IDs: AUDIT-E002 through AUDIT-E012
        These are type errors that could cause runtime failures.
        """
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "core_findings.yaml")
        engine_findings = ff.filter_by_module("rustybt/live/engine.py")
        high_findings = [f for f in engine_findings if f.severity == Severity.HIGH]
        # Should have multiple HIGH severity issues
        assert (
            len(high_findings) >= 8
        ), f"Expected at least 8 HIGH engine findings, got {len(high_findings)}"

    def test_strategy_executor_high_findings(self) -> None:
        """Verify strategy_executor HIGH findings are captured.

        Finding IDs: AUDIT-X001, AUDIT-X002
        API mismatches in TradingAlgorithm calls.
        """
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "core_findings.yaml")
        executor_findings = ff.filter_by_module("rustybt/live/strategy_executor.py")
        high_findings = [f for f in executor_findings if f.severity == Severity.HIGH]
        assert (
            len(high_findings) >= 2
        ), f"Expected at least 2 HIGH executor findings, got {len(high_findings)}"

    def test_reconciler_high_findings(self) -> None:
        """Verify reconciler HIGH findings are captured.

        Finding ID: AUDIT-R002
        Type mismatch in assignment.
        """
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "core_findings.yaml")
        reconciler_findings = ff.filter_by_module("rustybt/live/reconciler.py")
        high_findings = [f for f in reconciler_findings if f.severity == Severity.HIGH]
        assert len(high_findings) >= 1

    def test_ccxt_adapter_high_findings(self) -> None:
        """Verify CCXT adapter HIGH findings are captured.

        Finding IDs: AUDIT-B004 through AUDIT-B011
        Exception type mismatches in error handling.
        """
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "brokers_findings.yaml")
        ccxt_findings = ff.filter_by_module("rustybt/live/brokers/ccxt_adapter.py")
        high_findings = [f for f in ccxt_findings if f.severity == Severity.HIGH]
        assert (
            len(high_findings) >= 8
        ), f"Expected at least 8 HIGH ccxt findings, got {len(high_findings)}"

    def test_binance_adapter_high_findings(self) -> None:
        """Verify Binance adapter HIGH findings are captured.

        Finding IDs: AUDIT-B013, AUDIT-B014, AUDIT-B015
        Type indexing errors.
        """
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "brokers_findings.yaml")
        binance_findings = ff.filter_by_module("rustybt/live/brokers/binance_adapter.py")
        high_findings = [f for f in binance_findings if f.severity == Severity.HIGH]
        assert len(high_findings) >= 3

    def test_paper_broker_high_findings(self) -> None:
        """Verify Paper broker HIGH findings are captured.

        Finding IDs: AUDIT-B018, AUDIT-B019
        Timestamp type mismatches.
        """
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "brokers_findings.yaml")
        paper_findings = ff.filter_by_module("rustybt/live/brokers/paper_broker.py")
        high_findings = [f for f in paper_findings if f.severity == Severity.HIGH]
        assert len(high_findings) >= 2

    def test_bar_buffer_high_findings(self) -> None:
        """Verify bar_buffer HIGH findings are captured.

        Finding IDs: AUDIT-S006, AUDIT-S007, AUDIT-S008
        Using 'any' instead of 'Any' type.
        """
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "streaming_findings.yaml")
        buffer_findings = ff.filter_by_module("rustybt/live/streaming/bar_buffer.py")
        high_findings = [f for f in buffer_findings if f.severity == Severity.HIGH]
        assert len(high_findings) >= 3

    def test_streaming_base_high_findings(self) -> None:
        """Verify streaming base HIGH findings are captured.

        Finding ID: AUDIT-S012
        Reconnection always triggers even on intentional disconnect.
        """
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "manual_review_findings.yaml")
        streaming_findings = ff.filter_by_module("rustybt/live/streaming/base.py")
        high_findings = [f for f in streaming_findings if f.severity == Severity.HIGH]
        assert len(high_findings) >= 1


class TestTotalFindingCounts:
    """Test total finding counts match expectations."""

    def test_total_critical_high_findings(self) -> None:
        """Verify total CRITICAL/HIGH count across all files."""
        total_critical_high = 0
        for yaml_file in FINDINGS_DIR.glob("*.yaml"):
            if yaml_file.name == "sample_findings.yaml":
                continue
            ff = FindingsFile.load_from_yaml(yaml_file)
            for f in ff.findings:
                if f.severity in (Severity.CRITICAL, Severity.HIGH):
                    total_critical_high += 1
        # Based on our audit: 31 CRITICAL/HIGH findings
        assert (
            total_critical_high >= 30
        ), f"Expected at least 30 CRITICAL/HIGH findings, got {total_critical_high}"

    def test_findings_have_descriptions(self) -> None:
        """Verify all CRITICAL/HIGH findings have descriptions."""
        for yaml_file in FINDINGS_DIR.glob("*.yaml"):
            if yaml_file.name == "sample_findings.yaml":
                continue
            ff = FindingsFile.load_from_yaml(yaml_file)
            for f in ff.findings:
                if f.severity in (Severity.CRITICAL, Severity.HIGH):
                    assert f.description, f"Finding {f.id} missing description"
                    assert f.recommendation, f"Finding {f.id} missing recommendation"

    def test_findings_have_line_numbers_where_applicable(self) -> None:
        """Verify static analysis findings have line numbers."""
        for yaml_file in FINDINGS_DIR.glob("*.yaml"):
            if yaml_file.name in ("sample_findings.yaml", "manual_review_findings.yaml"):
                continue
            ff = FindingsFile.load_from_yaml(yaml_file)
            for f in ff.findings:
                if f.severity in (Severity.CRITICAL, Severity.HIGH):
                    # Static analysis findings should have line numbers
                    assert f.line is not None, f"Finding {f.id} missing line number"


class TestFindingCategories:
    """Test that findings cover key risk categories."""

    def test_has_type_error_findings(self) -> None:
        """Verify type error findings exist."""
        all_findings = []
        for yaml_file in FINDINGS_DIR.glob("*.yaml"):
            if yaml_file.name == "sample_findings.yaml":
                continue
            ff = FindingsFile.load_from_yaml(yaml_file)
            all_findings.extend(ff.findings)
        type_findings = [f for f in all_findings if f.category.value == "type_error"]
        assert len(type_findings) >= 20

    def test_has_error_handling_findings(self) -> None:
        """Verify error handling findings exist."""
        all_findings = []
        for yaml_file in FINDINGS_DIR.glob("*.yaml"):
            if yaml_file.name == "sample_findings.yaml":
                continue
            ff = FindingsFile.load_from_yaml(yaml_file)
            all_findings.extend(ff.findings)
        error_findings = [f for f in all_findings if f.category.value == "error_handling"]
        assert len(error_findings) >= 5

    def test_has_concurrency_findings(self) -> None:
        """Verify concurrency findings exist from manual review."""
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "manual_review_findings.yaml")
        concurrency_findings = [f for f in ff.findings if f.category.value == "concurrency"]
        assert len(concurrency_findings) >= 1

    def test_has_state_management_findings(self) -> None:
        """Verify state management findings exist from manual review."""
        ff = FindingsFile.load_from_yaml(FINDINGS_DIR / "manual_review_findings.yaml")
        state_findings = [f for f in ff.findings if f.category.value == "state_management"]
        assert len(state_findings) >= 2
