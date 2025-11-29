"""Validation CLI.

This module provides the command-line interface for the validation framework,
allowing users to manage sessions and run validations.
"""

from datetime import datetime
from importlib.metadata import version

import click


@click.group()
@click.version_option(version=version("rustybt"), prog_name="rustybt-validate")
def main() -> None:
    """RustyBT validation framework CLI.

    This tool provides commands for validating rustybt's correctness through
    systematic comparison against Backtrader reference implementations.
    """
    pass


@main.group()
def session() -> None:
    """Manage validation sessions."""
    pass


@session.command("create")
@click.option("--strategy", required=True, help="Strategy name")
@click.option("--data", type=click.Path(exists=True), required=True, help="Path to data fixture")
@click.option("--rustybt-version", default="0.3.4", help="rustybt version")
@click.option("--backtrader-version", default="1.9.78", help="Backtrader version")
@click.option("--force", is_flag=True, help="Override existing IN_PROGRESS session (marks as SUPERSEDED)")
def session_create(
    strategy: str, data: str, rustybt_version: str, backtrader_version: str, force: bool
) -> None:
    """Create a new validation session.

    If a session already exists for the same strategy with IN_PROGRESS status,
    use --force to mark it as SUPERSEDED and create a new session.
    """
    from pathlib import Path

    from rustybt.validation.exceptions import DuplicateSessionError
    from rustybt.validation.session import SessionManager

    try:
        sm = SessionManager()
        session = sm.create_session(
            strategy, Path(data), rustybt_version, backtrader_version, force=force
        )

        # Check if any sessions were superseded
        superseded = getattr(session, "_superseded_sessions", None)
        if superseded:
            click.secho(
                f"⚠ Warning: Existing session(s) marked as SUPERSEDED: {', '.join(superseded)}",
                fg="yellow",
            )

        click.secho(f"✓ Session created: {session.id}", fg="green")
        click.echo(f"  Strategy: {session.strategy_name}")
        click.echo(f"  Data: {session.data_fixture}")
    except DuplicateSessionError as e:
        click.secho(f"✗ Error: {e}", fg="red", err=True)
        click.echo("")
        click.echo("Suggested actions:")
        click.echo(f"  • Resume existing session: rustybt-validate session resume {e.existing_session_id}")
        click.echo(f"  • Delete existing session: rustybt-validate session delete {e.existing_session_id}")
        click.echo(f"  • Override with --force:   rustybt-validate session create --strategy {strategy} --data {data} --force")
        raise SystemExit(1) from e
    except Exception as e:
        click.secho(f"✗ Error: {e}", fg="red", err=True)
        raise SystemExit(1) from e


@session.command("list")
@click.option("--strategy", default=None, help="Filter by strategy name")
@click.option("--status", default=None, help="Filter by status (IN_PROGRESS, COMPLETED, FAILED)")
@click.option("--stage", default=None, help="Filter by stage (created, executing, executed, etc.)")
@click.option("--since", default=None, help="Filter sessions created after date (YYYY-MM-DD)")
@click.option("--has-findings", is_flag=True, help="Only show sessions with findings")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table", help="Output format")
def session_list(
    strategy: str | None,
    status: str | None,
    stage: str | None,
    since: str | None,
    has_findings: bool,
    output_format: str,
) -> None:
    """List all validation sessions with optional filters.

    Examples:
        rustybt-validate session list --strategy sma_crossover
        rustybt-validate session list --status COMPLETED --format json
        rustybt-validate session list --since 2025-01-01 --has-findings
    """
    import json
    from datetime import datetime

    from rustybt.validation.models import SessionStage
    from rustybt.validation.session import SessionManager

    sm = SessionManager()

    # Parse stage if provided
    stage_filter = None
    if stage:
        try:
            stage_filter = SessionStage(stage.lower())
        except ValueError:
            valid_stages = [s.value for s in SessionStage]
            click.secho(f"✗ Invalid stage: {stage}. Valid stages: {', '.join(valid_stages)}", fg="red", err=True)
            raise SystemExit(1) from None

    # Parse since date if provided
    since_filter = None
    if since:
        try:
            since_filter = datetime.fromisoformat(since)
        except ValueError:
            click.secho(f"✗ Invalid date format: {since}. Use YYYY-MM-DD", fg="red", err=True)
            raise SystemExit(1) from None

    sessions = sm.find_sessions(
        strategy=strategy,
        status=status,
        stage=stage_filter,
        since=since_filter,
        has_findings=has_findings,
    )

    if output_format == "json":
        # JSON output format
        output = [
            {
                "id": s.id,
                "strategy": s.strategy_name,
                "stage": s.stage.value,
                "status": s.status,
                "created_at": s.created_at.isoformat(),
                "findings_count": len(s.findings),
            }
            for s in sessions
        ]
        click.echo(json.dumps(output, indent=2))
    elif not sessions:
        click.echo("(no sessions)")
    else:
        # Table format header with Stage column
        click.echo(
            f"{'Session ID':<45} | {'Strategy':<20} | {'Stage':<15} | {'Status':<12} | Created"
        )
        click.echo("-" * 120)
        for s in sessions:
            click.echo(
                f"{s.id:<45} | {s.strategy_name:<20} | {s.stage.value:<15} | {s.status:<12} | {s.created_at}"
            )


@session.command("show")
@click.argument("session_id")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table", help="Output format")
def session_show(session_id: str, output_format: str) -> None:
    """Show details of a validation session.

    Displays full session metadata, progress timeline with timestamps,
    findings summary, and layer completion status.
    """
    import json

    from rustybt.validation.models import SessionStage
    from rustybt.validation.session import SessionManager

    sm = SessionManager()
    try:
        session = sm.load_session(session_id)

        if output_format == "json":
            # JSON output format
            findings_summary = {}
            for f in session.findings:
                key = f.classification or "unclassified"
                findings_summary[key] = findings_summary.get(key, 0) + 1

            output = {
                "id": session.id,
                "strategy": session.strategy_name,
                "stage": session.stage.value,
                "status": session.status,
                "created_at": session.created_at.isoformat(),
                "stage_started_at": session.stage_started_at.isoformat() if session.stage_started_at else None,
                "execution_completed_at": session.execution_completed_at.isoformat() if session.execution_completed_at else None,
                "comparison_completed_at": session.comparison_completed_at.isoformat() if session.comparison_completed_at else None,
                "layers_completed": session.layers_completed,
                "layers_pending": _get_pending_layers(session.layers_completed),
                "rustybt_version": session.rustybt_version,
                "backtrader_version": session.backtrader_version,
                "python_version": session.python_version,
                "data_fixture": str(session.data_fixture),
                "findings_count": len(session.findings),
                "findings_summary": findings_summary,
            }
            click.echo(json.dumps(output, indent=2))
        else:
            # Table format with progress timeline
            click.echo(f"Session: {session.id}")
            click.echo(f"Strategy: {session.strategy_name}")
            click.echo(f"Status: {session.status}")
            click.echo(f"Stage: {session.stage.value}")
            click.echo(f"Created: {session.created_at}")
            click.echo("")

            # Progress timeline
            click.echo("Progress:")
            _display_progress_timeline(session)
            click.echo("")

            # Findings summary
            if session.findings:
                click.echo(_format_findings_summary(session.findings))
            else:
                click.echo("Findings: None")
            click.echo("")

            # Layer status
            completed = session.layers_completed or []
            pending = _get_pending_layers(completed)
            if completed:
                click.echo(f"Layers Completed: {', '.join(completed)}")
            if pending:
                click.echo(f"Layers Pending: {', '.join(pending)}")
            click.echo("")

            # Version info
            click.echo(f"rustybt Version: {session.rustybt_version}")
            click.echo(f"Backtrader Version: {session.backtrader_version}")
            click.echo(f"Python Version: {session.python_version}")
            click.echo(f"Data Fixture: {session.data_fixture}")
            click.echo(f"Directory: validation-sessions/{session.id}/")
    except FileNotFoundError:
        click.secho(f"✗ Session not found: {session_id}", fg="red", err=True)
        raise SystemExit(1)


def _display_progress_timeline(session) -> None:
    """Display progress timeline with checkmarks."""
    from rustybt.validation.models import SessionStage

    # Define stages and their completion checks
    stages = [
        ("Created", SessionStage.CREATED, session.created_at),
        ("Execution", SessionStage.EXECUTED, session.execution_completed_at),
        ("Comparison", SessionStage.COMPARED, session.comparison_completed_at),
        ("Investigation", SessionStage.INVESTIGATING, None),
        ("Completed", SessionStage.COMPLETED, None),
    ]

    stage_order = [
        SessionStage.CREATED,
        SessionStage.EXECUTING,
        SessionStage.EXECUTED,
        SessionStage.COMPARING,
        SessionStage.COMPARED,
        SessionStage.INVESTIGATING,
        SessionStage.COMPLETED,
    ]

    current_idx = stage_order.index(session.stage) if session.stage in stage_order else 0

    for label, stage, timestamp in stages:
        stage_idx = stage_order.index(stage) if stage in stage_order else 0

        if stage == SessionStage.COMPLETED and session.stage == SessionStage.COMPLETED:
            click.echo(f"  [x] {label}")
        elif stage_idx < current_idx or (stage_idx == current_idx and timestamp):
            # Completed stage
            ts_str = f" ({timestamp.strftime('%H:%M:%S')})" if timestamp else ""
            click.echo(f"  [x] {label} completed{ts_str}")
        elif stage_idx == current_idx:
            # Current stage in progress
            click.echo(f"  [ ] {label} in progress")
        else:
            # Future stage
            click.echo(f"  [ ] {label}")


def _format_findings_summary(findings: list) -> str:
    """Format findings summary with counts by classification."""
    summary: dict[str, int] = {}
    for f in findings:
        key = f.classification or "unclassified"
        summary[key] = summary.get(key, 0) + 1

    parts = [f"{count} {cls}" for cls, count in sorted(summary.items())]
    return f"Findings: {len(findings)} total ({', '.join(parts)})"


def _get_pending_layers(completed: list[str]) -> list[str]:
    """Get list of pending layers based on completed ones."""
    all_layers = ["data", "signals", "orders", "broker", "portfolio"]
    return [layer for layer in all_layers if layer not in completed]


@session.command("resume")
@click.argument("session_id")
def session_resume(session_id: str) -> None:
    """Resume an interrupted validation session.

    Loads the session and determines the appropriate stage to resume from
    based on completed artifacts. FAILED sessions are reset to the last
    successful checkpoint.

    Example:
        rustybt-validate session resume 20251124-143000-sma_crossover
    """
    from rustybt.validation.session import SessionManager

    sm = SessionManager()
    try:
        session = sm.resume(session_id)
        resume_info = sm.get_resume_info(session)

        click.secho(f"✓ Resuming session {session_id} from stage: {resume_info['stage']}", fg="green")
        click.echo(f"  Next step: {resume_info['next_step']}")
        if resume_info['artifacts_found'] != "None":
            click.echo(f"  Artifacts found: {resume_info['artifacts_found']}")
        click.echo(f"  Status: {session.status}")
    except ValueError as e:
        click.secho(f"✗ Cannot resume: {e}", fg="red", err=True)
        raise SystemExit(1)
    except FileNotFoundError:
        click.secho(f"✗ Session not found: {session_id}", fg="red", err=True)
        raise SystemExit(1)


@session.command("findings")
@click.argument("session_id")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table", help="Output format")
def session_findings(session_id: str, output_format: str) -> None:
    """List all findings for a validation session.

    Displays findings with ID, layer, classification, and description.
    Unclassified findings are highlighted with a '-' marker.

    Example:
        rustybt-validate session findings 20251124-143000-sma_crossover
    """
    import json

    from rustybt.validation.session import SessionManager

    sm = SessionManager()
    try:
        session = sm.load_session(session_id)

        if not session.findings:
            click.echo(f"Session {session_id} has no findings.")
            return

        if output_format == "json":
            output = [
                {
                    "id": f.id,
                    "layer": f.layer,
                    "classification": f.classification,
                    "description": f.description,
                    "rustybt_value": f.rustybt_value,
                    "backtrader_value": f.backtrader_value,
                    "rationale": f.rationale,
                    "resolved": f.resolved,
                }
                for f in session.findings
            ]
            click.echo(json.dumps(output, indent=2))
        else:
            # Table format
            click.echo(f"Findings for session: {session_id}")
            click.echo(f"Total: {len(session.findings)}")
            click.echo("")

            # Count unclassified
            unclassified = [f for f in session.findings if f.classification is None]
            if unclassified:
                click.secho(f"⚠ {len(unclassified)} unclassified finding(s)", fg="yellow")
                click.echo("")

            # Table header
            click.echo(f"{'ID':<15} | {'Layer':<12} | {'Classification':<15} | Description")
            click.echo("-" * 80)

            for f in session.findings:
                classification = f.classification or "-"
                # Truncate description to 35 chars for display
                desc = f.description[:35] + "..." if len(f.description) > 35 else f.description
                click.echo(f"{f.id:<15} | {f.layer:<12} | {classification:<15} | {desc}")

    except FileNotFoundError:
        click.secho(f"✗ Session not found: {session_id}", fg="red", err=True)
        raise SystemExit(1)


@session.command("activities")
@click.argument("session_id")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table", help="Output format")
def session_activities(session_id: str, output_format: str) -> None:
    """Show session activity log (audit trail).

    Displays all timestamped activities for a session including
    creation, stage changes, findings, and manual notes.

    Example:
        rustybt-validate session activities 20251124-143000-sma_crossover
    """
    import json

    from rustybt.validation.session import SessionManager

    sm = SessionManager()
    try:
        session = sm.load_session(session_id)

        if not session.activities:
            click.echo(f"Session {session_id} has no activities logged.")
            return

        if output_format == "json":
            output = [a.to_dict() for a in session.activities]
            click.echo(json.dumps(output, indent=2))
        else:
            # Table format
            click.echo(f"Activity log for session: {session_id}")
            click.echo(f"Total activities: {len(session.activities)}")
            click.echo("")

            # Table header
            click.echo(f"{'Timestamp':<20} | {'Actor':<10} | Action")
            click.echo("-" * 80)

            for activity in session.activities:
                ts = activity.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                action_str = activity.action
                if activity.details and "message" in activity.details:
                    action_str += f": {activity.details['message']}"
                click.echo(f"{ts:<20} | {activity.actor:<10} | {action_str}")

    except FileNotFoundError:
        click.secho(f"✗ Session not found: {session_id}", fg="red", err=True)
        raise SystemExit(1)


@session.command("delete")
@click.argument("session_id")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.option("--dry-run", is_flag=True, help="Show what would be deleted without deleting")
def session_delete(session_id: str, yes: bool, dry_run: bool) -> None:
    """Delete a validation session and all its files.

    Permanently removes the session directory including logs, analysis files,
    and all associated data. This action cannot be undone.

    Use --dry-run to preview what would be deleted without actually deleting.
    """
    from rustybt.validation.session import SessionManager

    sm = SessionManager()

    try:
        # Load session to show details before deletion
        session = sm.load_session(session_id)
    except FileNotFoundError:
        click.secho(f"✗ Session not found: {session_id}", fg="red", err=True)
        raise SystemExit(1) from None

    if dry_run:
        click.echo(f"Would delete session: {session_id}")
        click.echo(f"  Strategy: {session.strategy_name}")
        click.echo(f"  Status: {session.status}")
        click.echo(f"  Created: {session.created_at}")
        click.echo(f"  Findings: {len(session.findings)}")
        click.secho("(dry run - no files deleted)", fg="yellow")
        return

    if not yes:
        click.echo(f"About to delete session: {session_id}")
        click.echo(f"  Strategy: {session.strategy_name}")
        click.echo(f"  Status: {session.status}")
        click.echo(f"  Findings: {len(session.findings)}")
        if not click.confirm("Are you sure you want to permanently delete this session?"):
            click.echo("Cancelled.")
            return

    try:
        sm.delete_session(session_id)
        click.secho(f"✓ Session deleted: {session_id}", fg="green")
    except Exception as e:
        click.secho(f"✗ Error deleting session: {e}", fg="red", err=True)
        raise SystemExit(1) from e


@session.command("archive")
@click.argument("session_id")
@click.option("--dry-run", is_flag=True, help="Show what would be archived without archiving")
def session_archive(session_id: str, dry_run: bool) -> None:
    """Archive a validation session to compressed storage.

    Creates a gzipped tar archive of the session and removes the original.
    Archives are stored in validation-sessions/archive/.

    Use --dry-run to preview what would be archived without actually archiving.
    """
    from rustybt.validation.session import SessionManager

    sm = SessionManager()

    try:
        session = sm.load_session(session_id)
    except FileNotFoundError:
        click.secho(f"✗ Session not found: {session_id}", fg="red", err=True)
        raise SystemExit(1) from None

    if dry_run:
        click.echo(f"Would archive session: {session_id}")
        click.echo(f"  Strategy: {session.strategy_name}")
        click.echo(f"  Status: {session.status}")
        click.echo(f"  Would create: validation-sessions/archive/{session_id}.tar.gz")
        click.secho("(dry run - no files archived)", fg="yellow")
        return

    try:
        archive_path = sm.archive_session(session_id)
        click.secho(f"✓ Session archived: {session_id}", fg="green")
        click.echo(f"  Archive: {archive_path}")
    except Exception as e:
        click.secho(f"✗ Error archiving session: {e}", fg="red", err=True)
        raise SystemExit(1) from e


@session.command("cleanup")
@click.option("--older-than", type=int, help="Only clean sessions older than N days")
@click.option("--status", help="Only clean sessions with this status (e.g., COMPLETED, FAILED)")
@click.option("--archive", is_flag=True, help="Archive sessions instead of deleting")
@click.option("--dry-run", is_flag=True, help="Show what would be cleaned without cleaning")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def session_cleanup(
    older_than: int | None, status: str | None, archive: bool, dry_run: bool, yes: bool
) -> None:
    """Clean up old sessions by deleting or archiving them.

    Without --older-than, cleans ALL sessions matching the status filter.
    Use --dry-run to preview what would be affected.

    Examples:
      # Delete sessions older than 30 days
      rustybt-validate session cleanup --older-than 30

      # Archive completed sessions older than 7 days
      rustybt-validate session cleanup --older-than 7 --status COMPLETED --archive

      # Delete all failed sessions
      rustybt-validate session cleanup --status FAILED

      # Preview what would be deleted
      rustybt-validate session cleanup --older-than 30 --dry-run
    """
    from rustybt.validation.session import SessionManager

    sm = SessionManager()

    # First do a dry-run to see what would be affected
    affected = sm.cleanup_sessions(
        older_than_days=older_than,
        status=status,
        dry_run=True,
        archive=archive,
    )

    if not affected:
        click.echo("No sessions match the cleanup criteria.")
        return

    action = "archive" if archive else "delete"
    click.echo(f"Sessions to {action}: {len(affected)}")
    for session_id in affected:
        click.echo(f"  - {session_id}")

    if dry_run:
        click.secho(f"(dry run - no sessions {action}d)", fg="yellow")
        return

    if not yes:
        if not click.confirm(f"Proceed with {action}?"):
            click.echo("Cancelled.")
            return

    # Actually perform the cleanup
    cleaned = sm.cleanup_sessions(
        older_than_days=older_than,
        status=status,
        dry_run=False,
        archive=archive,
    )

    click.secho(f"✓ {len(cleaned)} session(s) {action}d", fg="green")


@main.command()
@click.argument("session_id", required=False)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["markdown", "json"]),
    default="markdown",
    help="Output format (default: markdown)",
)
@click.option(
    "--layer",
    "layer_name",
    type=click.Choice(["data", "signals", "orders", "broker", "portfolio"]),
    default=None,
    help="Generate layer report instead of session report",
)
@click.option(
    "--strategy",
    "strategy_name",
    type=str,
    default=None,
    help="Generate strategy report (e.g., sma_crossover, momentum)",
)
def report(session_id: str | None, output_format: str, layer_name: str | None, strategy_name: str | None) -> None:
    """Generate a validation report for a session, layer, or strategy.

    Creates a comprehensive report including session summary, layer results,
    and detailed findings. Reports are saved to the appropriate directory.

    For layer reports, aggregates findings across all validated strategies
    and identifies common patterns.

    For strategy reports, shows validation results across all layers for
    a single strategy with recommendations.

    Examples:
        rustybt-validate report 20251124-143000-sma_crossover
        rustybt-validate report SESSION_ID --format json
        rustybt-validate report --layer signals
        rustybt-validate report --strategy sma_crossover
    """
    from rustybt.validation.reporting import LayerReportGenerator, ReportGenerator, StrategyReportGenerator
    from rustybt.validation.session import SessionManager

    sm = SessionManager()

    # Layer report mode
    if layer_name:
        generator = LayerReportGenerator(layer_name, sm)
        report_path = generator.save()

        click.secho(f"Layer report saved to: {report_path}", fg="green")
        click.echo(f"  Layer: {layer_name}")

        # Get summary stats
        findings = generator.get_layer_findings()
        bug_count = sum(1 for f in findings if f.classification == "BUG")
        design_count = sum(1 for f in findings if f.classification == "DESIGN")
        click.echo(f"  Findings: {len(findings)} ({bug_count} BUG, {design_count} DESIGN)")
        return

    # Strategy report mode
    if strategy_name:
        generator = StrategyReportGenerator(strategy_name, sm)
        report_path = generator.save()

        click.secho(f"Strategy report saved to: {report_path}", fg="green")
        click.echo(f"  Strategy: {strategy_name}")
        return

    # Session report mode
    if not session_id:
        click.secho("Error: SESSION_ID required (or use --layer or --strategy)", fg="red", err=True)
        raise SystemExit(1)

    try:
        session = sm.load_session(session_id)
    except FileNotFoundError:
        click.secho(f"Error: Session not found: {session_id}", fg="red", err=True)
        raise SystemExit(1) from None

    generator = ReportGenerator(session)

    if output_format == "json":
        report_path = generator.save_json()
        click.secho(f"JSON report saved to: {report_path}", fg="green")
    else:
        report_path = generator.save_markdown()
        click.secho(f"Report saved to: {report_path}", fg="green")

    click.echo(f"  Session: {session.id}")
    click.echo(f"  Strategy: {session.strategy_name}")
    click.echo(f"  Status: {session.status}")
    click.echo(f"  Findings: {len(session.findings)}")


@main.group()
def log() -> None:
    """Log file operations."""
    pass


@log.command("validate")
@click.argument("log_path", type=click.Path(exists=True))
def log_validate(log_path: str) -> None:
    """Validate log file schema.

    Checks that each line is valid JSON with required fields:
    - timestamp: Required on every entry
    - layer: Required, must be one of: broker, data, orders, portfolio, signals
    - event: Required on every entry
    """
    from pathlib import Path

    from rustybt.validation.log_parser import validate_log_schema

    result = validate_log_schema(Path(log_path))
    click.echo(str(result))

    if not result.valid:
        for error in result.errors[:10]:  # Show first 10 errors
            click.echo(f"  {error}")
        if len(result.errors) > 10:
            click.echo(f"  ... and {len(result.errors) - 10} more errors")
        raise SystemExit(1)


@main.command()
@click.argument("session_id")
@click.option(
    "--rustybt-module",
    default=None,
    help="Python module path for rustybt strategy (default: tests.validation.strategies.rustybt.{strategy})",
)
@click.option(
    "--backtrader-module",
    default=None,
    help="Python module path for Backtrader strategy (default: tests.validation.strategies.bt_strategies.{strategy})",
)
def run(session_id: str, rustybt_module: str | None, backtrader_module: str | None) -> None:
    """Execute validation for a session.

    Runs the strategy in both rustybt and Backtrader frameworks,
    collecting logs for later comparison.
    """
    from rustybt.validation.coordinator import execute_dual
    from rustybt.validation.log_parser import count_log_entries
    from rustybt.validation.session import SessionManager

    sm = SessionManager()
    try:
        session = sm.load_session(session_id)
    except FileNotFoundError:
        click.secho(f"✗ Session not found: {session_id}", fg="red", err=True)
        raise SystemExit(1) from None

    # Default module paths based on strategy name
    strategy = session.strategy_name
    rb_module = rustybt_module or f"tests.validation.strategies.rustybt.{strategy}"
    bt_module = backtrader_module or f"tests.validation.strategies.bt_strategies.{strategy}"

    click.echo(f"Executing {strategy}...")
    click.echo(f"  rustybt module: {rb_module}")
    click.echo(f"  Backtrader module: {bt_module}")

    # Execute dual
    result = execute_dual(
        session=session,
        strategy_name=strategy,
        rustybt_module=rb_module,
        backtrader_module=bt_module,
    )

    # Print results
    click.echo(str(result))
    if result.success:
        # Count log entries
        rb_count = count_log_entries(result.rustybt_log)
        bt_count = count_log_entries(result.backtrader_log)
        click.secho(f"  - rustybt: {rb_count} log entries", fg="green")
        click.secho(f"  - Backtrader: {bt_count} log entries", fg="green")

        # Update session
        sm.update_execution_result(session, result)
        click.echo(f"Session status updated: {session.status}")
    else:
        for error in result.errors[:5]:
            click.secho(f"  Error: {error}", fg="red", err=True)
        if len(result.errors) > 5:
            click.echo(f"  ... and {len(result.errors) - 5} more errors")
        raise SystemExit(1)


@main.command()
@click.argument("output", type=click.Path())
@click.option("--assets", default=50, help="Number of assets")
@click.option("--start", default="2020-01-01", help="Start date")
@click.option("--end", default="2021-12-31", help="End date")
@click.option("--seed", default=42, help="Random seed")
def generate_fixture(
    output: str, assets: int, start: str, end: str, seed: int
) -> None:
    """Generate test data fixture."""
    from pathlib import Path

    from rustybt.validation.generate_fixture import generate_fixture as gen

    gen(Path(output), assets, start, end, seed)


@main.group()
def config() -> None:
    """Tolerance configuration commands."""
    pass


@config.command("show")
@click.argument("layer")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table", help="Output format")
def config_show(layer: str, output_format: str) -> None:
    """Show tolerance configuration for a validation layer.

    LAYER can be one of: layer_1, layer_2, layer_3, layer_4, layer_5, or 'all' for all layers.

    Examples:
        rustybt-validate config show layer_1
        rustybt-validate config show all --format json
    """
    import json
    from pathlib import Path

    from rustybt.validation.tolerance import ToleranceConfig

    valid_layers = ["layer_1", "layer_2", "layer_3", "layer_4", "layer_5", "all"]

    if layer not in valid_layers:
        click.secho(f"✗ Invalid layer: {layer}", fg="red", err=True)
        click.echo(f"Valid layers: {', '.join(valid_layers)}")
        raise SystemExit(1)

    # Load configuration
    config_dir = Path("tests/validation/config")
    if config_dir.exists():
        tolerance_config = ToleranceConfig.load_from_directory(config_dir)
    else:
        tolerance_config = ToleranceConfig()

    # Get layer data
    layer_data: dict = {}
    if layer == "all":
        layer_data = tolerance_config.to_dict()
    elif layer == "layer_1":
        layer_data = {"layer_1_data": tolerance_config.to_dict()["layer_1_data"]}
    elif layer == "layer_2":
        layer_data = {"layer_2_signals": tolerance_config.to_dict()["layer_2_signals"]}
    elif layer == "layer_3":
        layer_data = {"layer_3_orders": tolerance_config.to_dict()["layer_3_orders"]}
    elif layer == "layer_4":
        layer_data = {"layer_4_broker": tolerance_config.to_dict()["layer_4_broker"]}
    elif layer == "layer_5":
        layer_data = {"layer_5_portfolio": tolerance_config.to_dict()["layer_5_portfolio"]}

    if output_format == "json":
        click.echo(json.dumps(layer_data, indent=2))
    else:
        for layer_name, tolerances in layer_data.items():
            click.echo(f"\n{layer_name} tolerances:")
            click.echo("-" * 40)
            for key, value in tolerances.items():
                click.echo(f"  {key}: {value}")


@config.command("defaults")
@click.option("--format", "output_format", type=click.Choice(["table", "json"]), default="table", help="Output format")
def config_defaults(output_format: str) -> None:
    """Show default tolerance configuration (ignoring any config files).

    Useful for understanding what the built-in defaults are before customizing.
    """
    import json

    from rustybt.validation.tolerance import ToleranceConfig

    # Get defaults (no config files)
    default_config = ToleranceConfig()
    data = default_config.to_dict()

    if output_format == "json":
        click.echo(json.dumps(data, indent=2))
    else:
        for layer_name, tolerances in data.items():
            click.echo(f"\n{layer_name} tolerances:")
            click.echo("-" * 40)
            for key, value in tolerances.items():
                click.echo(f"  {key}: {value}")


@main.command()
@click.argument("session_id")
@click.option("--finding", help="Jump to specific finding ID (e.g., FIND-001)")
@click.option(
    "--layer",
    type=click.Choice(["data", "signals", "orders", "broker", "portfolio"]),
    help="Filter findings to specific layer",
)
@click.option("--unclassified", is_flag=True, help="Show only unclassified findings")
@click.option("--bugs", is_flag=True, help="Show only BUG-classified findings")
@click.option("--design", is_flag=True, help="Show only DESIGN-classified findings")
def investigate(
    session_id: str,
    finding: str | None,
    layer: str | None,
    unclassified: bool,
    bugs: bool,
    design: bool,
) -> None:
    """Investigate discrepancies in a validation session.

    Launches an interactive interface for investigating and classifying
    findings. Use filter options to focus on specific layers or classification
    states.

    Examples:
        rustybt-validate investigate 20251124-143000-sma_crossover
        rustybt-validate investigate SESSION_ID --finding FIND-001
        rustybt-validate investigate SESSION_ID --layer orders
        rustybt-validate investigate SESSION_ID --unclassified
    """
    from rustybt.validation.investigation import (
        extract_context_from_session,
        filter_findings,
        find_index_by_id,
        format_finding_presentation,
        get_progress_indicator,
    )
    from rustybt.validation.session import SessionManager

    sm = SessionManager()
    try:
        session = sm.load_session(session_id)
    except FileNotFoundError:
        click.secho(f"✗ Session not found: {session_id}", fg="red", err=True)
        raise SystemExit(1) from None

    # Apply filters
    findings = filter_findings(
        session.findings,
        layer=layer,
        unclassified=unclassified,
        bugs=bugs,
        design=design,
    )

    if not findings:
        click.echo("No findings match the specified filters.")
        # Show helpful info about available findings
        if session.findings:
            click.echo(f"\nSession has {len(session.findings)} total finding(s).")
            layer_counts: dict[str, int] = {}
            for f in session.findings:
                layer_counts[f.layer] = layer_counts.get(f.layer, 0) + 1
            click.echo(f"By layer: {layer_counts}")
        return

    # Start at specified finding or beginning
    current_idx = 0
    if finding:
        current_idx = find_index_by_id(findings, finding)
        if current_idx == 0 and findings[0].id != finding:
            click.secho(f"⚠ Finding {finding} not found, starting at first finding", fg="yellow")

    # Log investigation started
    session.log_activity("investigation_started", f"Starting investigation with {len(findings)} findings")
    sm.update_session(session)

    # Investigation loop
    while True:
        current_finding = findings[current_idx]
        context = extract_context_from_session(session, current_finding)

        # Display finding
        click.clear()
        progress = get_progress_indicator(findings, current_idx)
        click.echo(f"Progress: {progress}")
        click.echo("")
        click.echo(format_finding_presentation(current_finding, current_idx, len(findings), context))

        # Get user action
        action = click.prompt(
            "Enter action",
            type=click.Choice(["b", "d", "s", "v", "c", "n", "p", "q"]),
            default="n",
        )

        if action == "q":
            click.echo("\nExiting investigation.")
            session.log_activity("investigation_paused", f"Investigation paused at finding {current_finding.id}")
            sm.update_session(session)
            break

        elif action == "n":
            # Next finding
            current_idx = (current_idx + 1) % len(findings)

        elif action == "p":
            # Previous finding
            current_idx = (current_idx - 1) % len(findings)

        elif action == "b":
            # Classify as BUG using full workflow
            from rustybt.validation.classification import classify_as_bug

            def save_finding_callback(f):
                sm.update_session(session)

            classify_as_bug(
                current_finding,
                session=session,
                save_callback=save_finding_callback,
            )
            click.pause()

            # Auto-advance to next finding
            current_idx = (current_idx + 1) % len(findings)

        elif action == "d":
            # Classify as DESIGN using full workflow
            from rustybt.validation.classification import classify_as_design

            def save_finding_callback(f):
                sm.update_session(session)

            classify_as_design(
                current_finding,
                session=session,
                save_callback=save_finding_callback,
            )
            click.pause()

            # Auto-advance to next finding
            current_idx = (current_idx + 1) % len(findings)

        elif action == "s":
            # Skip - just move to next
            click.echo(f"Skipping finding {current_finding.id}")
            current_idx = (current_idx + 1) % len(findings)

        elif action == "v":
            # View source code locations
            from rustybt.validation.source_linking import (
                format_source_locations,
                locate_source,
                open_in_editor,
            )

            click.echo("\n=== Source Code Locations ===")
            locations = locate_source(current_finding)

            if not locations:
                click.echo(f"No source locations found for {current_finding.layer} layer.")
                click.echo(f"Searched for: {current_finding.description}")
            else:
                click.echo(format_source_locations(locations))
                click.echo("")

                # Prompt to open in editor
                selection = click.prompt(
                    f"Open location? [1-{len(locations)} or n to skip]",
                    default="n",
                )

                if selection != "n":
                    try:
                        idx = int(selection) - 1
                        if 0 <= idx < len(locations):
                            open_in_editor(locations[idx])
                            click.echo(f"Opening {locations[idx].file}...")
                        else:
                            click.echo("Invalid selection.")
                    except ValueError:
                        click.echo("Invalid selection.")

            click.pause()

        elif action == "c":
            # View comparison context
            click.echo("\n=== Comparison Context ===")
            click.echo(f"Finding ID: {current_finding.id}")
            click.echo(f"Layer: {current_finding.layer}")
            click.echo(f"Description: {current_finding.description}")
            if context.previous_bar_timestamp:
                click.echo(f"Previous bar: {context.previous_bar_timestamp}")
            if context.next_bar_timestamp:
                click.echo(f"Next bar: {context.next_bar_timestamp}")
            if context.related_signal:
                click.echo(f"Related signal: {context.related_signal}")
            if context.related_order_type:
                click.echo(f"Order type: {context.related_order_type}")
            if context.tolerance_config:
                click.echo(f"Tolerance config: {context.tolerance_config}")
            click.echo("\n(Additional context will be available when session logs are parsed)")
            click.pause()


@main.group()
def config() -> None:
    """Configuration management commands.

    Manage validation framework configuration settings.
    """
    pass


@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key: str, value: str) -> None:
    """Set a configuration value.

    Supported keys:
        editor - Editor command with {file} and {line} placeholders

    Examples:
        rustybt-validate config set editor "code -g {file}:{line}"
        rustybt-validate config set editor "vim +{line} {file}"
        rustybt-validate config set editor "subl {file}:{line}"
    """
    from rustybt.validation.source_linking import set_editor_command

    if key == "editor":
        # Validate editor command has required placeholders
        if "{file}" not in value:
            click.secho("⚠ Editor command should include {file} placeholder", fg="yellow")
        if "{line}" not in value:
            click.secho("⚠ Editor command should include {line} placeholder", fg="yellow")

        set_editor_command(value)
        click.secho(f"✓ Editor set to: {value}", fg="green")
    else:
        click.secho(f"✗ Unknown config key: {key}", fg="red", err=True)
        click.echo("Supported keys: editor")
        raise SystemExit(1)


@config.command("get")
@click.argument("key")
def config_get(key: str) -> None:
    """Get a configuration value.

    Supported keys:
        editor - Editor command with {file} and {line} placeholders

    Example:
        rustybt-validate config get editor
    """
    from rustybt.validation.source_linking import get_editor_command

    if key == "editor":
        cmd = get_editor_command()
        click.echo(f"editor = {cmd}")
    else:
        click.secho(f"✗ Unknown config key: {key}", fg="red", err=True)
        click.echo("Supported keys: editor")
        raise SystemExit(1)


@config.command("list")
def config_list() -> None:
    """List all configuration values.

    Example:
        rustybt-validate config list
    """
    from rustybt.validation.source_linking import get_editor_command

    click.echo("Current configuration:")
    click.echo(f"  editor = {get_editor_command()}")


@main.command()
@click.argument("finding_id")
def verify(finding_id: str) -> None:
    """Verify a bug fix resolves the discrepancy.

    Re-runs strategy execution for both frameworks and re-runs layer comparison
    to check if the original discrepancy is no longer present.

    Only BUG-classified findings can be verified. If verification passes,
    the finding is marked as resolved.

    Examples:
        rustybt-validate verify FIND-001
        rustybt-validate verify layer_3_finding_001
    """
    from rustybt.validation.verification import (
        ExecutionError,
        load_finding,
        re_execute_strategies,
        compare_layer_for_finding,
        save_finding,
    )

    click.echo(f"\n=== Verifying Fix for {finding_id} ===\n")

    # Load finding and session
    finding, session = load_finding(finding_id)

    if finding is None or session is None:
        click.secho(f"✗ Error: Finding {finding_id} not found.", fg="red", err=True)
        raise SystemExit(1)

    # Validate finding is classified as BUG
    if finding.classification != "BUG":
        click.secho(
            f"✗ Error: Finding {finding_id} is not classified as BUG "
            f"(classification: {finding.classification or 'unclassified'}).",
            fg="red",
            err=True,
        )
        click.echo("\nOnly BUG-classified findings can be verified.")
        click.echo("Use 'rustybt-validate investigate' to classify findings first.")
        raise SystemExit(1)

    # Show original discrepancy
    click.echo("Original discrepancy:")
    click.echo(f"  Layer: {finding.layer}")
    click.echo(f"  Description: {finding.description}")
    if finding.rustybt_value is not None:
        click.echo(f"  rustybt: {finding.rustybt_value}, Backtrader: {finding.backtrader_value}")
    click.echo()

    # Re-execute strategies
    click.echo("Re-running strategy execution...")
    try:
        rb_logs, bt_logs = re_execute_strategies(session)
        click.secho("✓ rustybt executed successfully", fg="green")
        click.secho("✓ Backtrader executed successfully", fg="green")
    except ExecutionError as e:
        click.secho(f"✗ Execution failed: {e}", fg="red", err=True)
        raise SystemExit(1)

    # Re-run comparison
    click.echo("\nRe-running layer comparison...")
    discrepancies = compare_layer_for_finding(finding, rb_logs, bt_logs)

    # Check if original discrepancy still present
    # Match by description pattern or event type
    original_still_present = False
    matching_discrepancy = None

    for d in discrepancies:
        # Check if this discrepancy matches the original finding
        if (
            finding.description.lower() in d.description.lower()
            or d.description.lower() in finding.description.lower()
            or (d.event and finding.description.split("/")[-1].split(":")[0] == d.event)
        ):
            original_still_present = True
            matching_discrepancy = d
            break

    if not original_still_present:
        # Verification passed
        click.secho(f"✓ Original discrepancy no longer detected", fg="green")
        click.echo("\n=== Fix Verified ===")

        # Update finding
        finding.resolved = True
        finding.resolved_at = datetime.now()

        # Generate regression test
        from rustybt.validation.regression import generate_regression_test
        from pathlib import Path

        try:
            test_path = generate_regression_test(finding, Path.cwd())
            finding.regression_test = str(test_path.relative_to(Path.cwd()))
            click.secho(f"✓ Regression test created: {finding.regression_test}", fg="green")
        except Exception as e:
            # Fallback if test generation fails
            finding.regression_test = f"tests/validation/regression/test_{finding_id.lower().replace('-', '_')}.py"
            click.secho(f"⚠ Could not auto-generate test: {e}", fg="yellow")

        save_finding(finding, session)

        click.secho(f"{finding_id} marked as resolved", fg="green")
        click.echo("\nNext steps:")
        click.echo("  1. Run regression tests: pytest tests/validation/regression/ -v")
        click.echo("  2. Commit the regression test to ensure CI catches future regressions")
    else:
        # Verification failed
        click.secho("✗ Verification failed", fg="red")
        click.echo("Discrepancy still present:")
        if matching_discrepancy:
            click.echo(f"  rustybt: {matching_discrepancy.rustybt_value}, Backtrader: {matching_discrepancy.backtrader_value}")
        click.echo()
        click.echo("Fix not complete. Finding remains open.")
        click.echo("\nDebugging suggestions:")
        click.echo("  1. Check if the fix was applied to the correct file")
        click.echo("  2. Review the comparison tolerance settings")
        click.echo("  3. Use 'rustybt-validate investigate' to view more context")
        click.echo(f"  4. Check files: {', '.join(finding.affected_components) if finding.affected_components else 'N/A'}")


@main.command()
@click.argument("session_id")
@click.option("--layer", "-l", multiple=True, help="Specific layers to compare (can specify multiple)")
def compare(session_id: str, layer: tuple[str, ...]) -> None:
    """Run layer comparison and detect regressions.

    Compares execution logs from both frameworks across all layers
    (or specified layers) and checks for regressions against previously
    fixed bugs.

    Examples:
        rustybt-validate compare 20251127-120000-sma_crossover
        rustybt-validate compare SESSION_ID --layer orders --layer broker
    """
    from pathlib import Path

    from rustybt.validation.comparators import (
        ComparisonResult,
        Layer1DataComparator,
        Layer2SignalComparator,
        Layer3OrdersComparator,
        Layer4BrokerComparator,
        Layer5PortfolioComparator,
    )
    from rustybt.validation.log_parser import parse_log
    from rustybt.validation.regression_detection import (
        detect_regressions,
        report_regressions,
    )
    from rustybt.validation.session import SessionManager

    sm = SessionManager()

    try:
        session = sm.load_session(session_id)
    except FileNotFoundError:
        click.secho(f"✗ Session not found: {session_id}", fg="red", err=True)
        raise SystemExit(1) from None

    click.echo(f"\n=== Comparing Session: {session_id} ===\n")
    click.echo(f"Strategy: {session.strategy_name}")
    click.echo(f"Status: {session.status}")

    # Load logs
    session_dir = sm.sessions_dir / session_id
    logs_dir = session_dir / "logs"
    rb_log = logs_dir / "rustybt.jsonl"
    bt_log = logs_dir / "backtrader.jsonl"

    if not rb_log.exists() or not bt_log.exists():
        click.secho("✗ Log files not found. Run execution first.", fg="red", err=True)
        raise SystemExit(1)

    click.echo("\nLoading logs...")
    rb_logs = parse_log(rb_log)
    bt_logs = parse_log(bt_log)
    click.echo(f"  rustybt: {len(rb_logs)} events")
    click.echo(f"  Backtrader: {len(bt_logs)} events")

    # Determine layers to compare
    all_layers = ["data", "signals", "orders", "broker", "portfolio"]
    layers_to_compare = list(layer) if layer else all_layers

    # Validate layer names
    for l in layers_to_compare:
        if l not in all_layers:
            click.secho(f"✗ Invalid layer: {l}. Must be one of: {all_layers}", fg="red", err=True)
            raise SystemExit(1)

    # Get comparators
    comparators = {
        "data": Layer1DataComparator(),
        "signals": Layer2SignalComparator(),
        "orders": Layer3OrdersComparator(),
        "broker": Layer4BrokerComparator(),
        "portfolio": Layer5PortfolioComparator(),
    }

    # Run comparisons
    all_discrepancies = []
    click.echo("\nRunning comparisons...")

    for layer_name in layers_to_compare:
        comparator = comparators[layer_name]
        result: ComparisonResult = comparator.compare(rb_logs, bt_logs)

        if result.discrepancies:
            click.secho(f"  {layer_name}: {len(result.discrepancies)} discrepancies", fg="yellow")
            all_discrepancies.extend(result.discrepancies)
        else:
            click.secho(f"  {layer_name}: ✓ matched", fg="green")

    # Check for regressions FIRST
    click.echo("\nChecking for regressions...")
    regressions = detect_regressions(all_discrepancies)

    if regressions:
        report_regressions(regressions)

        # Filter out regression discrepancies for reporting
        regression_descriptions = {r.current_discrepancy.description for r in regressions}
        new_discrepancies = [
            d for d in all_discrepancies
            if d.description not in regression_descriptions
        ]

        click.echo(f"\nAdditionally, {len(new_discrepancies)} new discrepancies found.")
    else:
        click.secho("✓ No regressions detected", fg="green")
        new_discrepancies = all_discrepancies

    # Summary
    click.echo(f"\n=== Summary ===")
    click.echo(f"Total discrepancies: {len(all_discrepancies)}")
    click.echo(f"Regressions: {len(regressions)}")
    click.echo(f"New findings: {len(new_discrepancies)}")

    if regressions:
        click.secho("\n⚠️  Session has regressions that must be resolved.", fg="yellow")
        raise SystemExit(1)

    if all_discrepancies:
        click.echo("\nNext steps:")
        click.echo("  1. Run 'rustybt-validate investigate' to classify discrepancies")
        click.echo("  2. Fix any bugs identified")
        click.echo("  3. Run 'rustybt-validate verify' to confirm fixes")


@main.command()
@click.option("--sessions-dir", type=click.Path(exists=True), help="Sessions directory")
def check_regressions(sessions_dir: str | None) -> None:
    """Check all sessions for potential regressions.

    Scans current discrepancies across all sessions and checks if any
    match previously resolved bug findings.

    Examples:
        rustybt-validate check-regressions
        rustybt-validate check-regressions --sessions-dir ./my-sessions
    """
    from pathlib import Path

    from rustybt.validation.regression_detection import (
        detect_regressions,
        load_resolved_bugs,
        report_regressions,
    )

    dir_path = Path(sessions_dir) if sessions_dir else Path("validation-sessions")

    if not dir_path.exists():
        click.secho(f"✗ Sessions directory not found: {dir_path}", fg="red", err=True)
        raise SystemExit(1)

    click.echo(f"\n=== Checking for Regressions ===\n")

    # Load resolved bugs
    resolved_bugs = load_resolved_bugs(dir_path)
    click.echo(f"Found {len(resolved_bugs)} resolved bug findings")

    if not resolved_bugs:
        click.echo("No resolved bugs to check against.")
        return

    click.echo("\nResolved bugs:")
    for bug in resolved_bugs[:10]:  # Show first 10
        fixed_date = bug.resolved_at.strftime("%Y-%m-%d") if bug.resolved_at else "N/A"
        click.echo(f"  - {bug.id} ({bug.layer}): {bug.description[:50]}... [fixed {fixed_date}]")

    if len(resolved_bugs) > 10:
        click.echo(f"  ... and {len(resolved_bugs) - 10} more")

    click.echo("\nRun 'rustybt-validate compare SESSION_ID' to check specific sessions for regressions.")


@main.command()
@click.option("--format", "-f", "output_format", type=click.Choice(["ascii", "json"]), default="ascii", help="Output format")
@click.option("--ci", is_flag=True, help="CI mode: return exit code based on health status")
def status(output_format: str, ci: bool) -> None:
    """Show overall validation status dashboard.

    Displays an ASCII dashboard with:
    - Strategy validation status per strategy
    - Layer coverage across strategies
    - Findings summary (BUG/DESIGN counts)
    - Confidence score

    In CI mode, returns exit code 0 if healthy, 1 if unhealthy.

    Examples:
        rustybt-validate status
        rustybt-validate status --format json
        rustybt-validate status --ci
    """
    from rustybt.validation.reporting import StatusDashboard
    from rustybt.validation.session import SessionManager

    sm = SessionManager()
    dashboard = StatusDashboard(sm)

    if output_format == "json":
        import json
        data = dashboard.to_json()
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        click.echo(dashboard.render())

    if ci:
        raise SystemExit(dashboard.get_exit_code())


@main.command()
def progress() -> None:
    """Show validation completion progress.

    Displays progress bars for:
    - Strategy completion
    - Layer completion
    - Finding resolution
    - Overall weighted progress

    Also shows next steps to complete validation.

    Examples:
        rustybt-validate progress
    """
    from rustybt.validation.reporting import CompletionTracker
    from rustybt.validation.session import SessionManager

    sm = SessionManager()
    tracker = CompletionTracker(sm)
    click.echo(tracker.render())


@main.command("next-actions")
def next_actions() -> None:
    """Show recommended next actions.

    Analyzes current validation state and recommends prioritized actions:
    - Priority 1: Fix open bugs
    - Priority 2: Classify unclassified findings
    - Priority 3: Complete incomplete strategies
    - Priority 4: Update documentation

    Each recommendation includes an executable CLI command.

    Examples:
        rustybt-validate next-actions
    """
    from rustybt.validation.reporting import NextActionsRecommender
    from rustybt.validation.session import SessionManager

    sm = SessionManager()
    recommender = NextActionsRecommender(sm)
    click.echo(recommender.render())


@main.group()
def docs() -> None:
    """Documentation generation commands.

    Generate user-facing documentation from validation findings.
    """
    pass


@docs.command("generate")
@click.option("--output-dir", "-o", type=click.Path(), default="docs/validation", help="Output directory")
@click.option("--design-only", is_flag=True, help="Only generate design-differences.md")
@click.option("--bugs-only", is_flag=True, help="Only generate bug-fixes.md")
def docs_generate(output_dir: str, design_only: bool, bugs_only: bool) -> None:
    """Generate documentation from validation findings.

    Creates:
    - design-differences.md: Documented DESIGN differences between rustybt and Backtrader
    - bug-fixes.md: List of resolved bugs with regression test references

    Manual sections in existing files are preserved on regeneration.

    Examples:
        rustybt-validate docs generate
        rustybt-validate docs generate --output-dir ./docs/api
        rustybt-validate docs generate --design-only
    """
    from pathlib import Path

    from rustybt.validation.reporting import DocumentationGenerator
    from rustybt.validation.session import SessionManager

    sm = SessionManager()
    generator = DocumentationGenerator(sm, Path(output_dir))

    if design_only:
        path = generator.save_design_differences()
        click.secho(f"✓ Generated: {path}", fg="green")
    elif bugs_only:
        path = generator.save_bug_fixes()
        click.secho(f"✓ Generated: {path}", fg="green")
    else:
        design_path, bugs_path = generator.generate_all()
        click.secho(f"✓ Generated: {design_path}", fg="green")
        click.secho(f"✓ Generated: {bugs_path}", fg="green")


@docs.command("preview")
@click.option("--type", "-t", "doc_type", type=click.Choice(["design", "bugs"]), default="design", help="Document type to preview")
def docs_preview(doc_type: str) -> None:
    """Preview generated documentation without saving.

    Displays the generated content without writing to disk.

    Examples:
        rustybt-validate docs preview
        rustybt-validate docs preview --type bugs
    """
    from rustybt.validation.reporting import DocumentationGenerator
    from rustybt.validation.session import SessionManager

    sm = SessionManager()
    generator = DocumentationGenerator(sm)

    if doc_type == "design":
        content = generator.generate_design_differences()
    else:
        content = generator.generate_bug_fixes()

    click.echo(content)


if __name__ == "__main__":
    main()
