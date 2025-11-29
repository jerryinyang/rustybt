"""Investigation module for discrepancy analysis.

This module provides functionality for investigating and classifying
discrepancies found during validation sessions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Literal

import click

if TYPE_CHECKING:
    from rustybt.validation.models import Finding, Session


# Valid layers for filtering
VALID_LAYERS = ("data", "signals", "orders", "broker", "portfolio")


@dataclass
class InvestigationContext:
    """Context information for a finding during investigation.

    Provides temporal and related event context for investigating
    a discrepancy.
    """

    previous_bar_timestamp: str | None = None
    next_bar_timestamp: str | None = None
    related_signal: str | None = None
    related_order_type: str | None = None
    tolerance_config: str | None = None


def filter_findings(
    findings: list[Finding],
    layer: str | None = None,
    unclassified: bool = False,
    bugs: bool = False,
    design: bool = False,
) -> list[Finding]:
    """Filter findings based on criteria.

    Args:
        findings: List of findings to filter
        layer: Optional layer filter (data, signals, orders, broker, portfolio)
        unclassified: If True, only show unclassified findings
        bugs: If True, only show BUG-classified findings
        design: If True, only show DESIGN-classified findings

    Returns:
        Filtered list of findings
    """
    result = findings.copy()

    # Apply layer filter
    if layer:
        result = [f for f in result if f.layer == layer]

    # Apply classification filters (mutually exclusive based on flags)
    # If multiple status flags are set, they act as OR (include any matching)
    if unclassified or bugs or design:
        filtered = []
        for f in result:
            if unclassified and f.classification is None:
                filtered.append(f)
            elif bugs and f.classification == "BUG":
                filtered.append(f)
            elif design and f.classification == "DESIGN":
                filtered.append(f)
        result = filtered

    return result


def find_index_by_id(findings: list[Finding], finding_id: str) -> int:
    """Find index of finding by ID.

    Args:
        findings: List of findings to search
        finding_id: Finding ID to find

    Returns:
        Index of the finding, or 0 if not found
    """
    for idx, f in enumerate(findings):
        if f.id == finding_id:
            return idx
    return 0


def format_finding_presentation(
    finding: Finding,
    index: int,
    total: int,
    context: InvestigationContext | None = None,
) -> str:
    """Format finding details for presentation.

    Args:
        finding: Finding to format
        index: Current index (0-based)
        total: Total number of findings
        context: Optional context information

    Returns:
        Formatted string representation
    """
    # Count unclassified for progress display
    classification_label = finding.classification or "unclassified"

    lines = [
        f"=== Finding {finding.id} ({index + 1}/{total} {classification_label}) ===",
        "",
        f"Layer: {finding.layer}",
        f"Description: {finding.description}",
    ]

    # Add values if present
    if finding.rustybt_value is not None:
        lines.append(f"rustybt value: {finding.rustybt_value}")
    if finding.backtrader_value is not None:
        lines.append(f"Backtrader value: {finding.backtrader_value}")

    # Calculate difference if both values are numeric
    if finding.rustybt_value is not None and finding.backtrader_value is not None:
        try:
            rb_val = float(finding.rustybt_value)
            bt_val = float(finding.backtrader_value)
            diff = abs(rb_val - bt_val)
            if bt_val != 0:
                pct = abs(diff / bt_val) * 100
                lines.append(f"Difference: {diff:.6f} ({pct:.2f}%)")
            else:
                lines.append(f"Difference: {diff:.6f}")
        except (ValueError, TypeError):
            # Non-numeric values
            pass

    # Add context if available
    if context:
        lines.append("")
        lines.append("Context:")
        if context.previous_bar_timestamp:
            lines.append(f"  Previous bar: {context.previous_bar_timestamp}")
        if context.next_bar_timestamp:
            lines.append(f"  Next bar: {context.next_bar_timestamp}")
        if context.related_signal:
            lines.append(f"  Signal: {context.related_signal}")
        if context.related_order_type:
            lines.append(f"  Order type: {context.related_order_type}")
        if context.tolerance_config:
            lines.append(f"  Tolerance: {context.tolerance_config}")

    # Add classification info if present
    if finding.classification:
        lines.append("")
        lines.append(f"Classification: {finding.classification}")
        if finding.rationale:
            lines.append(f"Rationale: {finding.rationale}")
        if finding.investigated_by:
            lines.append(f"Investigated by: {finding.investigated_by}")
        if finding.investigated_at:
            lines.append(f"Investigated at: {finding.investigated_at}")

    lines.append("")
    lines.append("Actions:")
    lines.append("  [b] Classify as BUG (requires fix)")
    lines.append("  [d] Classify as DESIGN (intentional difference)")
    lines.append("  [s] Skip (investigate later)")
    lines.append("  [v] View source code locations")
    lines.append("  [c] View comparison context")
    lines.append("  [n] Next finding")
    lines.append("  [p] Previous finding")
    lines.append("  [q] Quit investigation")

    return "\n".join(lines)


def get_unclassified_count(findings: list[Finding]) -> int:
    """Get count of unclassified findings.

    Args:
        findings: List of findings

    Returns:
        Count of findings without classification
    """
    return sum(1 for f in findings if f.classification is None)


def get_progress_indicator(
    findings: list[Finding],
    current_index: int,
) -> str:
    """Get progress indicator string.

    Args:
        findings: List of findings
        current_index: Current finding index

    Returns:
        Progress string like "1/5 (3 unclassified)"
    """
    total = len(findings)
    unclassified = get_unclassified_count(findings)
    return f"{current_index + 1}/{total} ({unclassified} unclassified)"


def extract_context_from_session(
    session: Session,
    finding: Finding,
) -> InvestigationContext:
    """Extract temporal and related context for a finding.

    Args:
        session: Session containing the finding
        finding: Finding to get context for

    Returns:
        InvestigationContext with available context information
    """
    # This is a basic implementation that returns empty context
    # Full implementation would parse session logs and extract
    # temporal context, related signals, and tolerance info
    context = InvestigationContext()

    # The context would typically be extracted from:
    # 1. Session logs (rustybt.jsonl, backtrader.jsonl)
    # 2. Tolerance configuration used during comparison
    # 3. Related findings from same timestamp

    # For now, return basic context
    # This will be enhanced as we have more session data available
    return context
