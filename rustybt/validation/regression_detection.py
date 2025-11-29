"""Regression detection for validation framework.

This module provides functionality to detect when previously fixed bugs
reappear (regressions) by comparing current discrepancies against
resolved bug findings.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from rustybt.validation.comparators import Discrepancy
    from rustybt.validation.models import Finding


@dataclass
class Regression:
    """Represents a regression where a fixed bug has reappeared.

    Attributes:
        original_finding_id: ID of the original finding that was fixed
        current_discrepancy: The new discrepancy that matches the original
        fixed_at: When the original bug was fixed
        regression_detected_at: When this regression was detected
        original_fix_description: Description of how the bug was originally fixed
        original_layer: Layer where the original bug was found
    """

    original_finding_id: str
    current_discrepancy: Any  # Discrepancy type
    fixed_at: datetime | None
    regression_detected_at: datetime
    original_fix_description: str | None = None
    original_layer: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "original_finding_id": self.original_finding_id,
            "current_discrepancy": {
                "layer": self.current_discrepancy.layer,
                "event": self.current_discrepancy.event,
                "description": self.current_discrepancy.description,
                "rustybt_value": self.current_discrepancy.rustybt_value,
                "backtrader_value": self.current_discrepancy.backtrader_value,
            },
            "fixed_at": self.fixed_at.isoformat() if self.fixed_at else None,
            "regression_detected_at": self.regression_detected_at.isoformat(),
            "original_fix_description": self.original_fix_description,
            "original_layer": self.original_layer,
        }


def load_resolved_bugs(sessions_dir: Path) -> list[Finding]:
    """Load all resolved BUG findings from all sessions.

    Scans all session directories for findings that have been:
    1. Classified as BUG
    2. Marked as resolved

    Args:
        sessions_dir: Base directory containing session subdirectories

    Returns:
        List of Finding objects representing resolved bugs
    """
    from rustybt.validation.models import Finding

    resolved_bugs: list[Finding] = []

    if not sessions_dir.exists():
        return resolved_bugs

    for session_dir in sessions_dir.iterdir():
        if not session_dir.is_dir():
            continue

        # Try session.yaml first (main session file)
        session_file = session_dir / "session.yaml"
        if session_file.exists():
            try:
                with open(session_file) as f:
                    data = yaml.safe_load(f) or {}

                for f_data in data.get("findings", []):
                    finding = Finding.from_dict(f_data)
                    if finding.classification == "BUG" and finding.resolved:
                        resolved_bugs.append(finding)
            except (yaml.YAMLError, KeyError, TypeError):
                continue  # Skip malformed files

    return resolved_bugs


def matches_finding(discrepancy: Discrepancy, finding: Finding) -> bool:
    """Check if a discrepancy matches a resolved finding.

    Matching criteria:
    1. Same validation layer
    2. Similar event type (fuzzy match on description)

    Args:
        discrepancy: Current discrepancy to check
        finding: Previously resolved finding to compare against

    Returns:
        True if the discrepancy appears to be a regression of the finding
    """
    # Must match layer
    if discrepancy.layer != finding.layer:
        return False

    # Match on event type if available
    if hasattr(discrepancy, "event") and discrepancy.event:
        # Direct event match
        finding_event = _extract_event_from_finding(finding)
        if finding_event and discrepancy.event.lower() == finding_event.lower():
            return True

    # Fuzzy match on description
    discrepancy_desc = discrepancy.description.lower()
    finding_desc = finding.description.lower()

    # Check for significant keyword overlap
    disc_keywords = set(discrepancy_desc.split())
    find_keywords = set(finding_desc.split())

    # Remove common words
    common_words = {"the", "a", "an", "in", "on", "at", "for", "to", "of", "is", "was"}
    disc_keywords -= common_words
    find_keywords -= common_words

    # If more than 50% of keywords match, consider it a match
    if disc_keywords and find_keywords:
        overlap = disc_keywords & find_keywords
        similarity = len(overlap) / min(len(disc_keywords), len(find_keywords))
        if similarity >= 0.5:
            return True

    # Check for key phrases
    key_phrases = ["mismatch", "differs", "incorrect", "wrong", "error"]
    for phrase in key_phrases:
        if phrase in discrepancy_desc and phrase in finding_desc:
            # Same type of issue in same layer
            return True

    return False


def _extract_event_from_finding(finding: Finding) -> str | None:
    """Extract event type from finding description.

    Args:
        finding: Finding to extract event from

    Returns:
        Event type string or None
    """
    # Check if finding has direct event field
    if hasattr(finding, "event") and finding.event:
        return finding.event

    # Try to extract from description patterns
    desc = finding.description

    # Pattern: "layer/event_type: description"
    if "/" in desc and ":" in desc:
        parts = desc.split(":")
        event_part = parts[0].strip()
        if "/" in event_part:
            return event_part.split("/")[-1]

    # Pattern: "event_type detected" or "event_type found"
    for suffix in [" detected", " found", " occurred", " mismatch"]:
        if suffix in desc.lower():
            idx = desc.lower().find(suffix)
            prefix = desc[:idx].strip().split()
            if prefix:
                return prefix[-1].lower()

    return None


def detect_regressions(
    discrepancies: list[Discrepancy],
    sessions_dir: Path | None = None,
) -> list[Regression]:
    """Check if any discrepancies match previously fixed bugs.

    This is the main entry point for regression detection. It compares
    current discrepancies against all resolved bug findings to identify
    potential regressions.

    Args:
        discrepancies: List of current discrepancies from layer comparison
        sessions_dir: Base directory for sessions (default: validation-sessions)

    Returns:
        List of Regression objects for any matches found
    """
    if sessions_dir is None:
        sessions_dir = Path("validation-sessions")

    regressions: list[Regression] = []
    resolved_bugs = load_resolved_bugs(sessions_dir)

    for discrepancy in discrepancies:
        for bug in resolved_bugs:
            if matches_finding(discrepancy, bug):
                regressions.append(
                    Regression(
                        original_finding_id=bug.id,
                        current_discrepancy=discrepancy,
                        fixed_at=bug.resolved_at,
                        regression_detected_at=datetime.now(),
                        original_fix_description=bug.rationale,
                        original_layer=bug.layer,
                    )
                )
                # Only match each discrepancy to one finding
                break

    return regressions


def format_regression_warning(regression: Regression) -> str:
    """Format a prominent regression warning for CLI display.

    Creates an ASCII-boxed warning that highlights the regression
    with all relevant details about the original fix and current state.

    Args:
        regression: Regression to format

    Returns:
        Formatted warning string
    """
    d = regression.current_discrepancy
    fixed_date = regression.fixed_at.strftime("%Y-%m-%d") if regression.fixed_at else "N/A"
    fix_desc = regression.original_fix_description or "N/A"

    # Truncate long descriptions
    if len(fix_desc) > 50:
        fix_desc = fix_desc[:47] + "..."

    return f"""
╔══════════════════════════════════════════════════════════════════════╗
║                    ⚠️  REGRESSION DETECTED ⚠️                          ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  Finding {regression.original_finding_id} (fixed {fixed_date}) has reappeared!
║                                                                      ║
║    Layer: {d.layer}
║    Description: {d.description[:50] + '...' if len(d.description) > 50 else d.description}
║    rustybt: {d.rustybt_value}, backtrader: {d.backtrader_value}
║                                                                      ║
║  Original fix: {fix_desc}
║                                                                      ║
║  This may indicate:                                                  ║
║    • The fix was reverted                                            ║
║    • A new code path reintroduced the bug                            ║
║    • Related code was modified                                       ║
║                                                                      ║
║  ACTION REQUIRED: Investigate and fix before proceeding.             ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
"""


def report_regressions(regressions: list[Regression]) -> None:
    """Report all regressions to CLI with prominent warnings.

    Args:
        regressions: List of regressions to report
    """
    import click

    if not regressions:
        return

    click.echo(
        click.style(
            f"\n🚨 {len(regressions)} REGRESSION(S) DETECTED 🚨\n",
            fg="red",
            bold=True,
        )
    )

    for regression in regressions:
        click.echo(format_regression_warning(regression))

    click.echo(
        click.style(
            "\nSession cannot be completed until regressions are resolved.\n",
            fg="red",
        )
    )
    click.echo("Options:")
    click.echo("  1. Fix the regression and re-run verification")
    click.echo("  2. Re-classify as a new distinct issue if different from original")
    click.echo("  3. Update tolerance configuration if within acceptable range")


class RegressionError(Exception):
    """Raised when regressions block session completion."""

    def __init__(self, message: str, regressions: list[Regression] | None = None):
        super().__init__(message)
        self.regressions = regressions or []
