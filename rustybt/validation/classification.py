"""Classification workflows for validation findings.

This module provides workflows for classifying findings as BUG or DESIGN,
with proper validation and persistence.
"""

from __future__ import annotations

import getpass
import os
from datetime import datetime
from typing import TYPE_CHECKING

import click

from pathlib import Path

from rustybt.validation.models import BugSeverity, DesignChoice, Finding

if TYPE_CHECKING:
    from rustybt.validation.models import Session


def get_current_user() -> str:
    """Get current user identifier.

    Returns:
        Username from environment or system
    """
    # Try environment variable first
    user = os.environ.get("RUSTYBT_USER")
    if user:
        return user

    # Fall back to system username
    try:
        return getpass.getuser()
    except Exception:
        return "unknown"


def validate_rationale(rationale: str) -> tuple[bool, str]:
    """Validate rationale is non-empty.

    Args:
        rationale: User-provided rationale string

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not rationale or not rationale.strip():
        return False, "Rationale cannot be empty or whitespace-only."
    return True, ""


def validate_components(components: list[str]) -> tuple[bool, str]:
    """Validate at least one component is provided.

    Args:
        components: List of component paths

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not components:
        return False, "At least one affected component is required."
    return True, ""


def parse_components(components_str: str) -> list[str]:
    """Parse comma-separated components string.

    Args:
        components_str: Comma-separated file paths

    Returns:
        List of trimmed component paths
    """
    return [c.strip() for c in components_str.split(",") if c.strip()]


def classify_as_bug(
    finding: Finding,
    session: Session | None = None,
    save_callback: callable | None = None,
) -> bool:
    """Classify a finding as BUG with required metadata.

    Interactive workflow that prompts for:
    - Rationale (required)
    - Affected components (required)
    - Severity (required, with selection)
    - Suggested fix (optional)

    Args:
        finding: Finding to classify
        session: Optional session for logging
        save_callback: Optional callback to save finding

    Returns:
        True if classification completed, False if cancelled
    """
    click.echo("\n=== Classify as BUG ===\n")

    # Get rationale (required)
    rationale = ""
    while True:
        rationale = click.prompt("Rationale (required - explain why this is a bug)")
        is_valid, error = validate_rationale(rationale)
        if is_valid:
            break
        click.secho(f"Error: {error}", fg="red")

    # Get affected components (required)
    components: list[str] = []
    while True:
        components_str = click.prompt("Affected component(s) (comma-separated file paths)")
        components = parse_components(components_str)
        is_valid, error = validate_components(components)
        if is_valid:
            break
        click.secho(f"Error: {error}", fg="red")

    # Get severity
    click.echo("\nSeverity:")
    click.echo("  [1] Critical - incorrect results")
    click.echo("  [2] Major - significant deviation")
    click.echo("  [3] Minor - small deviation")
    severity_num = click.prompt("Select severity", type=int, default=2)
    severity = BugSeverity.from_number(severity_num)

    # Get suggested fix (optional)
    suggested_fix = click.prompt(
        "Suggested fix (optional, press Enter to skip)",
        default="",
    )

    # Get investigator name
    default_user = get_current_user()
    investigator = click.prompt("Investigator name", default=default_user)

    # Update finding
    finding.classification = "BUG"
    finding.rationale = rationale.strip()
    finding.severity = severity.value
    finding.affected_components = components
    finding.suggested_fix = suggested_fix.strip() if suggested_fix.strip() else None
    finding.investigated_by = investigator
    finding.investigated_at = datetime.now()

    # Save if callback provided
    if save_callback:
        save_callback(finding)

    # Log activity if session provided
    if session:
        session.log_activity(
            "finding_classified",
            f"Finding {finding.id} classified as BUG ({severity.value}): {rationale[:50]}...",
            actor=investigator,
        )

    # Show confirmation
    click.echo("\n" + "=" * 40)
    click.secho("BUG Classification Saved", fg="green", bold=True)
    click.echo("=" * 40)
    click.echo(f"Finding: {finding.id}")
    click.echo(f"Severity: {severity.value}")
    click.echo(f"Rationale: {rationale}")
    click.echo(f"Components: {', '.join(components)}")
    if finding.suggested_fix:
        click.echo(f"Suggested fix: {finding.suggested_fix}")
    click.echo("")
    click.secho(
        f"Next: Create fix in rustybt, then use 'rustybt-validate verify {finding.id}'",
        fg="cyan",
    )

    return True


def classify_as_design(
    finding: Finding,
    session: Session | None = None,
    save_callback: callable | None = None,
    project_root: Path | None = None,
) -> bool:
    """Classify a finding as DESIGN (intentional difference).

    Interactive workflow that prompts for:
    - Design rationale (required)
    - Design choice (which framework is preferred)
    - User impact (required)
    - Documentation reference (auto-creates stub if needed)

    Args:
        finding: Finding to classify
        session: Optional session for logging
        save_callback: Optional callback to save finding
        project_root: Project root for documentation stub creation

    Returns:
        True if classification completed, False if cancelled
    """
    click.echo("\n=== Classify as DESIGN ===\n")

    # Get design rationale (required)
    rationale = ""
    while True:
        rationale = click.prompt(
            "Design rationale (required - explain why this is intentional)"
        )
        is_valid, error = validate_rationale(rationale)
        if is_valid:
            break
        click.secho(f"Error: {error}", fg="red")

    # Get design choice
    click.echo("\nWhich framework is correct? (both may be valid):")
    click.echo("  [r] rustybt approach is preferred")
    click.echo("  [b] Backtrader approach is preferred")
    click.echo("  [e] Either approach is valid")
    choice_key = click.prompt(
        "Select",
        type=click.Choice(["r", "b", "e"]),
        default="e",
    )
    design_choice = DesignChoice.from_key(choice_key)

    # Get user impact (required)
    user_impact = ""
    while True:
        user_impact = click.prompt("User impact (describe practical implications)")
        if user_impact.strip():
            break
        click.secho("Error: User impact description is required.", fg="red")

    # Get documentation reference
    default_anchor = finding.description.replace(" ", "-").replace("_", "-").lower()[:30]
    default_ref = f"docs/validation/design-differences.md#{default_anchor}"
    doc_ref = click.prompt("Documentation reference", default=default_ref)

    # Create documentation stub if project_root provided
    if project_root:
        create_documentation_stub(
            finding=finding,
            rationale=rationale,
            design_choice=design_choice,
            user_impact=user_impact,
            doc_ref=doc_ref,
            project_root=project_root,
        )

    # Get investigator name
    default_user = get_current_user()
    investigator = click.prompt("Investigator name", default=default_user)

    # Update finding
    finding.classification = "DESIGN"
    finding.rationale = rationale.strip()
    finding.design_rationale = rationale.strip()
    finding.design_choice = design_choice.value
    finding.user_impact = user_impact.strip()
    finding.documentation_ref = doc_ref
    finding.investigated_by = investigator
    finding.investigated_at = datetime.now()

    # Save if callback provided
    if save_callback:
        save_callback(finding)

    # Log activity if session provided
    if session:
        session.log_activity(
            "finding_classified",
            f"Finding {finding.id} classified as DESIGN ({design_choice.value}): {rationale[:50]}...",
            actor=investigator,
        )

    # Show confirmation
    click.echo("\n" + "=" * 40)
    click.secho("DESIGN Classification Saved", fg="green", bold=True)
    click.echo("=" * 40)
    click.echo(f"Finding: {finding.id}")
    click.echo(f"Design choice: {design_choice.value}")
    click.echo(f"Rationale: {rationale}")
    click.echo(f"User impact: {user_impact}")
    click.echo(f"Documentation: {doc_ref}")
    click.echo("")
    click.secho(
        "This difference is now documented as intentional behavior.",
        fg="cyan",
    )

    return True


def create_documentation_stub(
    finding: Finding,
    rationale: str,
    design_choice: DesignChoice,
    user_impact: str,
    doc_ref: str,
    project_root: Path,
) -> bool:
    """Create documentation stub for DESIGN difference.

    Creates or updates design-differences.md with a new section for this finding.

    Args:
        finding: Finding being classified
        rationale: Design rationale text
        design_choice: Which framework is preferred
        user_impact: User impact description
        doc_ref: Documentation reference (path#anchor format)
        project_root: Project root directory

    Returns:
        True if stub was created/updated, False if anchor already exists
    """
    # Parse doc_ref into path and anchor
    if "#" in doc_ref:
        doc_path, anchor = doc_ref.rsplit("#", 1)
    else:
        doc_path = doc_ref
        anchor = finding.id.lower().replace("-", "_")

    full_path = project_root / doc_path

    # Create directory if needed
    full_path.parent.mkdir(parents=True, exist_ok=True)

    # Create file with header if doesn't exist
    if not full_path.exists():
        header = """# Design Differences

This document describes intentional differences between rustybt and Backtrader behavior.
These differences are by design and documented for user awareness.

---

"""
        full_path.write_text(header)
        click.echo(f"Created documentation file: {doc_path}")

    # Read existing content
    content = full_path.read_text()

    # Check if anchor already exists
    if f"## {anchor}" in content or f'<a name="{anchor}">' in content:
        click.secho(f"Documentation section for #{anchor} already exists.", fg="yellow")
        return False

    # Determine framework preference text
    if design_choice == DesignChoice.RUSTYBT_PREFERRED:
        preference_text = "rustybt's approach is preferred for this use case."
    elif design_choice == DesignChoice.BACKTRADER_PREFERRED:
        preference_text = "Backtrader's approach is preferred for this use case."
    else:
        preference_text = "Either approach is acceptable depending on user requirements."

    # Add new section
    new_section = f"""
## {anchor}

<a name="{anchor}"></a>

**Finding ID:** {finding.id}
**Layer:** {finding.layer}
**Description:** {finding.description}

### Rationale

{rationale}

### Framework Comparison

| Aspect | rustybt | Backtrader |
|--------|---------|------------|
| Value | {finding.rustybt_value} | {finding.backtrader_value} |

### User Impact

{user_impact}

### Resolution

This is a known design difference, not a bug. {preference_text}

---
"""
    full_path.write_text(content + new_section)
    click.secho(f"Documentation stub added to {doc_ref}", fg="green")
    return True


def format_classification_summary(finding: Finding) -> str:
    """Format a summary of a classified finding.

    Args:
        finding: Finding with classification

    Returns:
        Formatted summary string
    """
    lines = [
        f"Finding: {finding.id}",
        f"Layer: {finding.layer}",
        f"Classification: {finding.classification or 'Unclassified'}",
    ]

    if finding.classification == "BUG":
        lines.append(f"Severity: {finding.severity}")
        lines.append(f"Rationale: {finding.rationale}")
        if finding.affected_components:
            lines.append(f"Components: {', '.join(finding.affected_components)}")
        if finding.suggested_fix:
            lines.append(f"Suggested fix: {finding.suggested_fix}")
    elif finding.classification == "DESIGN":
        lines.append(f"Rationale: {finding.rationale}")
        if finding.acceptance_criteria:
            lines.append(f"Acceptance: {finding.acceptance_criteria}")

    if finding.investigated_by:
        lines.append(f"Investigated by: {finding.investigated_by}")
    if finding.investigated_at:
        lines.append(f"Investigated at: {finding.investigated_at.isoformat()}")

    return "\n".join(lines)
