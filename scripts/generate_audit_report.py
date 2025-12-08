#!/usr/bin/env python3
"""Generate audit report from YAML findings.

This script aggregates all audit findings from YAML files and generates
a comprehensive markdown report for the live trading code audit.

Usage:
    python scripts/generate_audit_report.py [--output PATH]

Options:
    --output PATH   Output path for the report [default: docs/live-trading/audit-report.md]
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import yaml


def load_findings(findings_dir: Path) -> list[dict]:
    """Load all findings from YAML files.

    Args:
        findings_dir: Directory containing finding YAML files.

    Returns:
        List of finding dictionaries.
    """
    findings = []
    yaml_files = sorted(findings_dir.glob("*.yaml"))

    for yaml_file in yaml_files:
        # Skip sample findings file
        if "sample" in yaml_file.stem:
            continue

        with open(yaml_file) as f:
            data = yaml.safe_load(f)
            if data and "findings" in data:
                findings.extend(data["findings"])

    return findings


def group_findings_by_module(findings: list[dict]) -> dict[str, list[dict]]:
    """Group findings by module path.

    Args:
        findings: List of finding dictionaries.

    Returns:
        Dictionary mapping module paths to findings.
    """
    grouped: dict[str, list[dict]] = {}
    for finding in findings:
        module = finding.get("module", "unknown")
        if module not in grouped:
            grouped[module] = []
        grouped[module].append(finding)
    return grouped


def generate_audit_report(findings: list[dict]) -> str:
    """Generate markdown audit report from findings.

    Args:
        findings: List of finding dictionaries.

    Returns:
        Markdown report string.
    """
    # Count by severity
    severity_counts = Counter(f.get("severity", "UNKNOWN") for f in findings)

    # Count by status
    status_counts = Counter(f.get("status", "UNKNOWN") for f in findings)

    # Count with regression tests
    with_tests = sum(1 for f in findings if f.get("regression_test"))

    # Count by category
    category_counts = Counter(f.get("category", "unknown") for f in findings)

    # Calculate coverage percentage
    coverage = (with_tests / len(findings) * 100) if findings else 0

    # Build report
    report = f"""# Live Trading Code Audit Report

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Epic:** 10.1 - Code Audit & Issue Management
**Status:** Complete

## Executive Summary

A comprehensive code audit was performed on the rustybt live trading infrastructure. The audit included:
- Static analysis using ruff and mypy
- Manual code review focusing on control flow and concurrency
- Security review for credential handling

## Findings Summary

| Severity | Count | Status |
|----------|-------|--------|
| CRITICAL | {severity_counts.get('CRITICAL', 0)} | {'Documented' if severity_counts.get('CRITICAL', 0) > 0 else 'N/A'} |
| HIGH | {severity_counts.get('HIGH', 0)} | {'Documented' if severity_counts.get('HIGH', 0) > 0 else 'N/A'} |
| MEDIUM | {severity_counts.get('MEDIUM', 0)} | Deferred |
| LOW | {severity_counts.get('LOW', 0)} | Deferred |
| **Total** | **{len(findings)}** | - |

## Resolution Status

| Status | Count |
|--------|-------|
| Open | {status_counts.get('OPEN', 0)} |
| In Progress | {status_counts.get('IN_PROGRESS', 0)} |
| Resolved | {status_counts.get('RESOLVED', 0)} |
| Verified | {status_counts.get('VERIFIED', 0)} |

## Categories

| Category | Count |
|----------|-------|
"""

    for category, count in sorted(category_counts.items()):
        report += f"| {category} | {count} |\n"

    report += f"""
## Regression Test Coverage

- Findings with regression tests: {with_tests}/{len(findings)}
- Coverage: {coverage:.1f}%

"""

    # Group findings by severity for detailed view
    grouped_by_module = group_findings_by_module(findings)

    # Add HIGH severity findings by module
    high_findings = [f for f in findings if f.get("severity") == "HIGH"]
    if high_findings:
        report += "## HIGH Severity Findings by Module\n\n"

        for module, module_findings in sorted(grouped_by_module.items()):
            high_in_module = [f for f in module_findings if f.get("severity") == "HIGH"]
            if high_in_module:
                # Extract module name from path
                module_name = Path(module).name
                report += f"### {module_name} - {len(high_in_module)} findings\n\n"
                report += "| ID | Line | Description | Category |\n"
                report += "|----|------|-------------|----------|\n"

                for f in sorted(high_in_module, key=lambda x: x.get("line", 0)):
                    report += f"| {f.get('id', 'N/A')} | {f.get('line', 'N/A')} | "
                    report += f"{f.get('description', 'No description')[:60]}... | "
                    report += f"{f.get('category', 'unknown')} |\n"

                report += "\n"

    # Add MEDIUM/LOW deferred findings summary
    medium_low = [f for f in findings if f.get("severity") in ("MEDIUM", "LOW")]
    if medium_low:
        report += "## Deferred Findings (MEDIUM/LOW)\n\n"

        medium_findings = [f for f in findings if f.get("severity") == "MEDIUM"]
        if medium_findings:
            report += f"### MEDIUM Severity - {len(medium_findings)} findings\n\n"
            report += (
                "These are tracked for future resolution but do not block production readiness:\n\n"
            )
            report += "| ID | Module | Description | Justification |\n"
            report += "|----|--------|-------------|---------------|\n"

            for f in medium_findings[:10]:  # Limit to first 10
                module_name = Path(f.get("module", "")).name
                report += f"| {f.get('id', 'N/A')} | {module_name} | "
                report += f"{f.get('description', '')[:40]}... | Non-blocking |\n"

            if len(medium_findings) > 10:
                report += f"\n*...and {len(medium_findings) - 10} more MEDIUM findings*\n"
            report += "\n"

        low_findings = [f for f in findings if f.get("severity") == "LOW"]
        if low_findings:
            report += f"### LOW Severity - {len(low_findings)} findings\n\n"
            report += "Style and documentation improvements for future sprints:\n\n"

            # Group by category for low severity
            low_by_category = Counter(f.get("category", "unknown") for f in low_findings)
            for category, count in sorted(low_by_category.items()):
                report += f"- {category}: {count} findings\n"

            report += "\n"

    # Add recommendations section
    report += """## Recommendations

### Immediate (Before Production)

1. **Fix HIGH type errors in engine.py** - These are most likely to cause runtime issues
2. **Fix CCXT adapter exception handling** - Exception type mismatches could mask errors
3. **Fix bar_buffer.py type annotations** - Simple fix, high impact

### Short-term (Next Sprint)

1. Add state transition validation to OrderManager
2. Add jitter to reconnection backoff
3. Add locking to circuit breaker reset()

### Long-term

1. Complete TODO placeholders in engine.py reconciliation
2. Standardize timezone handling across modules
3. Add comprehensive type annotations to remaining modules

## Audit Infrastructure

The audit created reusable infrastructure for ongoing code quality:

- `tests/live/audit/models.py` - Pydantic schema for findings
- `tests/live/audit/conftest.py` - Pytest fixtures for finding management
- `tests/live/audit/findings/*.yaml` - Machine-readable finding storage
- `tests/live/audit/test_*.py` - Regression tests

## Appendix: Finding Files

| File | Purpose |
|------|---------|
| core_findings.yaml | Engine, OrderManager, StateManager, Reconciler findings |
| brokers_findings.yaml | All broker adapter findings |
| streaming_findings.yaml | Streaming adapter findings |
| manual_review_findings.yaml | Manual code review findings |
| sample_findings.yaml | Schema documentation/testing |
"""

    return report


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate audit report from YAML findings.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/live-trading/audit-report.md"),
        help="Output path for the report",
    )
    parser.add_argument(
        "--findings-dir",
        type=Path,
        default=Path("tests/live/audit/findings"),
        help="Directory containing finding YAML files",
    )

    args = parser.parse_args()

    # Ensure paths are relative to project root
    project_root = Path(__file__).parent.parent
    findings_dir = project_root / args.findings_dir
    output_path = project_root / args.output

    if not findings_dir.exists():
        print(f"Error: Findings directory not found: {findings_dir}")
        return 1

    # Load findings
    findings = load_findings(findings_dir)
    print(f"Loaded {len(findings)} findings from {findings_dir}")

    # Generate report
    report = generate_audit_report(findings)

    # Save report
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report)
    print(f"Audit report generated: {output_path}")

    # Print summary
    severity_counts = Counter(f.get("severity", "UNKNOWN") for f in findings)
    print("\nSummary:")
    for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        count = severity_counts.get(severity, 0)
        if count > 0:
            print(f"  {severity}: {count}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
