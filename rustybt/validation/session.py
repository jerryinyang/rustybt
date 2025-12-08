"""Session management for validation framework."""

import shutil
import sys
import tarfile
from datetime import datetime, timedelta
from pathlib import Path

import yaml

from rustybt.validation.exceptions import DuplicateFindingError, DuplicateSessionError
from rustybt.validation.models import Activity, Finding, Session, SessionStage
from rustybt.validation.resilience import retry


class SessionManager:
    """Manage validation sessions with YAML persistence."""

    def __init__(self, sessions_dir: Path = Path("validation-sessions")):
        """Initialize session manager."""
        self.sessions_dir = sessions_dir
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def create_session(
        self,
        strategy_name: str,
        data_fixture: Path,
        rustybt_version: str,
        backtrader_version: str,
        force: bool = False,
    ) -> Session:
        """Create new validation session with duplicate detection.

        Checks for existing IN_PROGRESS sessions with the same strategy name.
        If a duplicate is found and force=False, raises DuplicateSessionError.
        If force=True, marks existing sessions as SUPERSEDED and creates new one.

        Args:
            strategy_name: Name of the strategy to validate
            data_fixture: Path to test data fixture
            rustybt_version: Version of rustybt under test
            backtrader_version: Version of Backtrader reference
            force: If True, supersede existing IN_PROGRESS sessions

        Returns:
            Newly created Session

        Raises:
            DuplicateSessionError: If duplicate IN_PROGRESS session exists and force=False
        """
        # Check for duplicate IN_PROGRESS sessions
        existing = self.find_sessions(strategy=strategy_name, status="IN_PROGRESS")

        if existing and not force:
            raise DuplicateSessionError(existing[0].id, strategy_name)

        # If force=True, mark existing sessions as SUPERSEDED
        superseded_sessions: list[str] = []
        if existing and force:
            for session in existing:
                session.status = "SUPERSEDED"
                self._save_session(session)
                superseded_sessions.append(session.id)

        timestamp = datetime.now()
        # Include microseconds to ensure uniqueness when force-creating in same second
        session_id = (
            timestamp.strftime("%Y%m%d-%H%M%S") + f"-{timestamp.microsecond:06d}-{strategy_name}"
        )

        session = Session(
            id=session_id,
            created_at=timestamp,
            strategy_name=strategy_name,
            rustybt_version=rustybt_version,
            backtrader_version=backtrader_version,
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            status="IN_PROGRESS",
            data_fixture=data_fixture,
        )

        # Auto-log session creation
        session.log_activity("created", f"Validation session created for {strategy_name}")

        self._save_session(session)

        # Store superseded session IDs on the new session for reference
        if superseded_sessions:
            session._superseded_sessions = superseded_sessions  # type: ignore[attr-defined]

        return session

    @retry(max_attempts=3, backoff_factor=2, exceptions=(IOError, OSError, yaml.YAMLError))
    def load_session(self, session_id: str) -> Session:
        """Load session from YAML with automatic retry on transient failures."""
        session_dir = self.sessions_dir / session_id
        session_file = session_dir / "session.yaml"

        with open(session_file) as f:
            data = yaml.safe_load(f)

        findings = [Finding.from_dict(f) for f in data.get("findings", [])]

        # Parse activities from dict format (backwards compatible - default to empty list)
        activities = [Activity.from_dict(a) for a in data.get("activities", [])]

        # Parse stage from string (backwards compatible - default to CREATED)
        stage_str = data.get("stage", "created")
        stage = SessionStage(stage_str) if stage_str else SessionStage.CREATED

        # Parse optional datetime fields
        stage_started_at = (
            datetime.fromisoformat(data["stage_started_at"])
            if data.get("stage_started_at")
            else None
        )
        execution_completed_at = (
            datetime.fromisoformat(data["execution_completed_at"])
            if data.get("execution_completed_at")
            else None
        )
        comparison_completed_at = (
            datetime.fromisoformat(data["comparison_completed_at"])
            if data.get("comparison_completed_at")
            else None
        )

        return Session(
            id=data["id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            strategy_name=data["strategy_name"],
            rustybt_version=data["rustybt_version"],
            backtrader_version=data["backtrader_version"],
            python_version=data["python_version"],
            status=data["status"],
            data_fixture=Path(data["data_fixture"]),
            findings=findings,
            stage=stage,
            stage_started_at=stage_started_at,
            execution_completed_at=execution_completed_at,
            comparison_completed_at=comparison_completed_at,
            layers_completed=data.get("layers_completed", []),
            activities=activities,
        )

    def update_session(self, session: Session) -> None:
        """Update existing session."""
        self._save_session(session)

    # Valid stage transitions map: {from_stage: [allowed_to_stages]}
    VALID_TRANSITIONS: dict[SessionStage, list[SessionStage]] = {
        SessionStage.CREATED: [SessionStage.EXECUTING, SessionStage.FAILED],
        SessionStage.EXECUTING: [SessionStage.EXECUTED, SessionStage.FAILED],
        SessionStage.EXECUTED: [SessionStage.COMPARING, SessionStage.FAILED],
        SessionStage.COMPARING: [SessionStage.COMPARED, SessionStage.FAILED],
        SessionStage.COMPARED: [SessionStage.INVESTIGATING, SessionStage.FAILED],
        SessionStage.INVESTIGATING: [
            SessionStage.COMPLETED,
            SessionStage.COMPARED,
            SessionStage.FAILED,
        ],
        SessionStage.COMPLETED: [],  # Terminal state
        SessionStage.FAILED: [SessionStage.CREATED],  # Can retry from scratch
    }

    def update_stage(self, session: Session, new_stage: SessionStage) -> None:
        """Update session stage with timestamp and validation.

        Updates the session's stage, sets appropriate timestamps, and saves
        the session to disk. Validates that the stage transition is allowed
        according to the workflow lifecycle.

        Args:
            session: Session to update
            new_stage: New stage to transition to

        Raises:
            ValueError: If the stage transition is not allowed
        """
        current_stage = session.stage
        allowed_transitions = self.VALID_TRANSITIONS.get(current_stage, [])

        if new_stage not in allowed_transitions:
            raise ValueError(
                f"Invalid stage transition: {current_stage.value} -> {new_stage.value}. "
                f"Allowed transitions from {current_stage.value}: "
                f"{[s.value for s in allowed_transitions]}"
            )

        # Update stage and timestamp
        now = datetime.now()
        session.stage = new_stage
        session.stage_started_at = now

        # Set completion timestamps for specific transitions
        if new_stage == SessionStage.EXECUTED:
            session.execution_completed_at = now
        elif new_stage == SessionStage.COMPARED:
            session.comparison_completed_at = now

        # Log stage transition activity
        session.log_activity(
            "stage_changed",
            f"Stage changed from {current_stage.value} to {new_stage.value}",
        )

        # Save session after stage change
        self._save_session(session)

        # Auto-generate report on completion (AC #5)
        if new_stage == SessionStage.COMPLETED:
            self._auto_generate_report(session)

    def list_sessions(self, status: str | None = None) -> list[Session]:
        """List all sessions with optional status filter.

        Args:
            status: Optional status filter ("IN_PROGRESS", "COMPLETED", "FAILED")

        Returns:
            List of Session objects sorted by created_at descending
        """
        sessions: list[Session] = []
        for d in self.sessions_dir.iterdir():
            if d.is_dir():
                try:
                    session = self.load_session(d.name)
                    if status is None or session.status == status:
                        sessions.append(session)
                except (FileNotFoundError, yaml.YAMLError):
                    continue  # Skip corrupted/incomplete sessions
        return sorted(sessions, key=lambda s: s.created_at, reverse=True)

    def find_sessions(
        self,
        strategy: str | None = None,
        status: str | None = None,
        stage: SessionStage | None = None,
        since: datetime | None = None,
        has_findings: bool = False,
    ) -> list[Session]:
        """Find sessions matching the given criteria.

        Supports filtering by multiple parameters with AND logic - all filters
        must match for a session to be included in results.

        Args:
            strategy: Optional strategy name filter
            status: Optional status filter ("IN_PROGRESS", "COMPLETED", "FAILED", "SUPERSEDED")
            stage: Optional SessionStage filter
            since: Optional datetime - only sessions created after this time
            has_findings: If True, only include sessions with one or more findings

        Returns:
            List of Session objects matching criteria, sorted by created_at descending
        """
        sessions: list[Session] = []
        for d in self.sessions_dir.iterdir():
            if d.is_dir():
                try:
                    session = self.load_session(d.name)
                    # Apply filters (AND logic)
                    if strategy is not None and session.strategy_name != strategy:
                        continue
                    if status is not None and session.status != status:
                        continue
                    if stage is not None and session.stage != stage:
                        continue
                    if since is not None and session.created_at < since:
                        continue
                    if has_findings and len(session.findings) == 0:
                        continue
                    sessions.append(session)
                except (FileNotFoundError, yaml.YAMLError):
                    continue  # Skip corrupted/incomplete sessions
        return sorted(sessions, key=lambda s: s.created_at, reverse=True)

    def add_finding(self, session: Session, finding: Finding) -> None:
        """Add a finding to a session with duplicate detection.

        Checks for existing findings with the same layer, event-like description,
        and timestamp. Finding uniqueness is determined by comparing the finding ID.

        Args:
            session: Session to add finding to
            finding: Finding to add

        Raises:
            DuplicateFindingError: If finding with same ID already exists
        """
        # Check for duplicate finding by ID
        for existing in session.findings:
            if existing.id == finding.id:
                raise DuplicateFindingError(existing.id)

        session.findings.append(finding)

        # Log finding addition
        session.log_activity(
            "finding_added",
            f"Finding {finding.id} added in {finding.layer} layer",
        )

        self._save_session(session)

    def delete_session(self, session_id: str, dry_run: bool = False) -> bool:
        """Delete a session and all its files.

        Permanently removes the session directory and all contents including
        logs, analysis files, and the session.yaml file.

        Args:
            session_id: ID of session to delete
            dry_run: If True, only simulate deletion without removing files

        Returns:
            True if deletion was successful (or would be in dry_run mode)

        Raises:
            FileNotFoundError: If session does not exist
        """
        session_dir = self.sessions_dir / session_id
        if not session_dir.exists():
            raise FileNotFoundError(f"Session not found: {session_id}")

        if dry_run:
            return True

        # Remove entire session directory
        shutil.rmtree(session_dir)
        return True

    def archive_session(
        self,
        session_id: str,
        archive_dir: Path | None = None,
        dry_run: bool = False,
    ) -> Path | None:
        """Archive a session to a compressed tarball.

        Creates a gzipped tar archive of the session directory and removes
        the original directory. Archive is stored in archive_dir (default:
        validation-sessions/archive/).

        Args:
            session_id: ID of session to archive
            archive_dir: Directory to store archive (default: sessions_dir/archive)
            dry_run: If True, only simulate archiving without file operations

        Returns:
            Path to created archive file, or None in dry_run mode

        Raises:
            FileNotFoundError: If session does not exist
        """
        session_dir = self.sessions_dir / session_id
        if not session_dir.exists():
            raise FileNotFoundError(f"Session not found: {session_id}")

        # Default archive directory
        if archive_dir is None:
            archive_dir = self.sessions_dir / "archive"

        if dry_run:
            return None

        # Create archive directory if needed
        archive_dir.mkdir(parents=True, exist_ok=True)

        # Create archive file
        archive_path = archive_dir / f"{session_id}.tar.gz"
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(session_dir, arcname=session_id)

        # Remove original directory after successful archive
        shutil.rmtree(session_dir)

        return archive_path

    def cleanup_sessions(
        self,
        older_than_days: int | None = None,
        status: str | None = None,
        dry_run: bool = False,
        archive: bool = False,
    ) -> list[str]:
        """Clean up old sessions by deleting or archiving them.

        Finds sessions matching the criteria and either deletes or archives them.

        Args:
            older_than_days: Only clean sessions older than this many days
            status: Only clean sessions with this status (e.g., "COMPLETED", "FAILED")
            dry_run: If True, only simulate cleanup without file operations
            archive: If True, archive sessions instead of deleting

        Returns:
            List of session IDs that were (or would be) cleaned up
        """
        cleaned: list[str] = []
        cutoff_date = None

        if older_than_days is not None:
            cutoff_date = datetime.now() - timedelta(days=older_than_days)

        sessions = self.list_sessions(status=status)

        for session in sessions:
            # Apply age filter
            if cutoff_date is not None and session.created_at >= cutoff_date:
                continue

            if archive:
                self.archive_session(session.id, dry_run=dry_run)
            else:
                self.delete_session(session.id, dry_run=dry_run)

            cleaned.append(session.id)

        return cleaned

    def update_execution_result(
        self,
        session: Session,
        result: "ExecutionResult",
    ) -> None:
        """Update session with execution result.

        Args:
            session: Session to update
            result: Execution result from execute_dual()
        """
        # Store execution metadata in session
        # The session.yaml will be updated with execution info
        session_dir = self.sessions_dir / session.id
        session_file = session_dir / "session.yaml"

        # Load existing data
        with open(session_file) as f:
            data = yaml.safe_load(f)

        # Add execution results
        data["execution"] = {
            "timestamp": datetime.now().isoformat(),
            "rustybt_success": result.rustybt_success,
            "backtrader_success": result.backtrader_success,
            "rustybt_log": str(result.rustybt_log),
            "backtrader_log": str(result.backtrader_log),
            "rustybt_log_valid": result.rustybt_log_valid,
            "backtrader_log_valid": result.backtrader_log_valid,
            "success": result.success,
        }

        # Update status based on result
        if result.success:
            data["status"] = "EXECUTED"
            session.status = "EXECUTED"
        else:
            data["status"] = "FAILED"
            session.status = "FAILED"
            data["execution"]["errors"] = result.errors

        with open(session_file, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

    def _auto_generate_report(self, session: Session) -> Path | None:
        """Auto-generate report when session is completed.

        Generates a markdown report automatically when session status changes
        to COMPLETED. The report is saved to the session directory.

        Args:
            session: Completed session to generate report for.

        Returns:
            Path to generated report, or None if generation failed.
        """
        from rustybt.validation.reporting import ReportGenerator

        try:
            generator = ReportGenerator(session)
            session_dir = self.sessions_dir / session.id
            report_path = generator.save_markdown(session_dir)

            # Log report generation
            session.log_activity(
                "report_generated",
                f"Report auto-generated on completion: {report_path}",
            )
            self._save_session(session)

            return report_path
        except Exception:
            # Don't fail the completion if report generation fails
            # Just log it and continue
            session.log_activity(
                "report_generation_failed",
                "Failed to auto-generate report on completion",
            )
            self._save_session(session)
            return None

    def _save_session(self, session: Session) -> None:
        """Save session to YAML."""
        session_dir = self.sessions_dir / session.id
        session_dir.mkdir(parents=True, exist_ok=True)
        # Create subdirectories for logs and analysis artifacts
        (session_dir / "logs").mkdir(exist_ok=True)
        (session_dir / "analysis").mkdir(exist_ok=True)

        session_file = session_dir / "session.yaml"
        data = {
            "id": session.id,
            "created_at": session.created_at.isoformat(),
            "strategy_name": session.strategy_name,
            "rustybt_version": session.rustybt_version,
            "backtrader_version": session.backtrader_version,
            "python_version": session.python_version,
            "status": session.status,
            "data_fixture": str(session.data_fixture),
            "stage": session.stage.value,
            "stage_started_at": (
                session.stage_started_at.isoformat() if session.stage_started_at else None
            ),
            "execution_completed_at": (
                session.execution_completed_at.isoformat()
                if session.execution_completed_at
                else None
            ),
            "comparison_completed_at": (
                session.comparison_completed_at.isoformat()
                if session.comparison_completed_at
                else None
            ),
            "layers_completed": session.layers_completed,
            "findings": [
                {
                    "id": f.id,
                    "layer": f.layer,
                    "description": f.description,
                    "classification": f.classification,
                    "rationale": f.rationale,
                    "investigated_by": f.investigated_by,
                    "investigated_at": f.investigated_at.isoformat() if f.investigated_at else None,
                    "resolved": f.resolved,
                    "rustybt_value": f.rustybt_value,
                    "backtrader_value": f.backtrader_value,
                }
                for f in session.findings
            ],
            "activities": [a.to_dict() for a in session.activities],
        }

        with open(session_file, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

    def _last_successful_stage(self, session: Session) -> SessionStage:
        """Determine last successfully completed stage from artifacts.

        Inspects the session directory for evidence of completed work:
        - Logs exist and valid -> execution completed
        - Analysis reports exist -> comparison completed
        - All findings classified -> investigation completed

        Args:
            session: Session to analyze

        Returns:
            SessionStage representing the last successfully completed stage
        """
        from rustybt.validation.log_parser import validate_log_schema

        session_dir = self.sessions_dir / session.id
        logs_dir = session_dir / "logs"
        analysis_dir = session_dir / "analysis"

        # Check if logs exist and are valid
        rb_log = logs_dir / "rustybt.jsonl"
        bt_log = logs_dir / "backtrader.jsonl"

        if not (rb_log.exists() and bt_log.exists()):
            return SessionStage.CREATED

        # Validate logs
        try:
            rb_valid = validate_log_schema(rb_log)
            bt_valid = validate_log_schema(bt_log)

            if not (rb_valid.valid and bt_valid.valid):
                return SessionStage.CREATED
        except Exception:
            # If validation fails, assume logs are invalid
            return SessionStage.CREATED

        # Logs valid, at least EXECUTED stage completed

        # Check if comparison done (any layer reports exist)
        if not analysis_dir.exists() or not any(analysis_dir.glob("layer_*_report.md")):
            return SessionStage.EXECUTED

        # Comparison done, check investigation status

        # Check findings for unclassified items
        unclassified = [f for f in session.findings if f.classification is None]

        if unclassified:
            # Still have unclassified findings -> comparison done, investigation pending
            return SessionStage.COMPARED

        # All findings classified -> investigation done
        return SessionStage.INVESTIGATING

    def resume(self, session_id: str) -> Session:
        """Resume session from last completed stage.

        Loads the session and determines the appropriate stage to resume from
        based on completed artifacts. FAILED sessions are reset to the last
        successful stage.

        Args:
            session_id: ID of session to resume

        Returns:
            Session ready for continuation

        Raises:
            ValueError: If session is already COMPLETED
            FileNotFoundError: If session does not exist
        """
        session = self.load_session(session_id)

        if session.stage == SessionStage.COMPLETED:
            raise ValueError(f"Cannot resume session {session_id}: session is already COMPLETED")

        # Determine resume point
        previous_stage = session.stage
        if session.stage == SessionStage.FAILED:
            # Reset to last successful stage
            last_stage = self._last_successful_stage(session)
            session.stage = last_stage
            session.stage_started_at = datetime.now()

        # Set status to IN_PROGRESS if not already
        if session.status != "IN_PROGRESS":
            session.status = "IN_PROGRESS"

        # Log session resumed activity
        session.log_activity(
            "session_resumed",
            f"Session resumed from {previous_stage.value} stage at {session.stage.value}",
        )

        self._save_session(session)
        return session

    def get_resume_info(self, session: Session) -> dict[str, str]:
        """Get human-readable information about resume status.

        Args:
            session: Session to get info for

        Returns:
            Dictionary with 'stage', 'next_step', and 'artifacts_found' keys
        """
        session_dir = self.sessions_dir / session.id
        logs_dir = session_dir / "logs"
        analysis_dir = session_dir / "analysis"

        # Gather artifact info
        artifacts: list[str] = []

        rb_log = logs_dir / "rustybt.jsonl"
        bt_log = logs_dir / "backtrader.jsonl"

        if rb_log.exists():
            artifacts.append("rustybt.jsonl")
        if bt_log.exists():
            artifacts.append("backtrader.jsonl")

        if analysis_dir.exists():
            reports = list(analysis_dir.glob("layer_*_report.md"))
            if reports:
                artifacts.append(f"{len(reports)} analysis report(s)")

        if session.findings:
            classified = sum(1 for f in session.findings if f.classification)
            artifacts.append(f"{classified}/{len(session.findings)} findings classified")

        # Determine next step based on stage
        next_steps = {
            SessionStage.CREATED: "Execute strategy in both frameworks",
            SessionStage.EXECUTING: "Continue execution (in progress)",
            SessionStage.EXECUTED: "Run layer comparison",
            SessionStage.COMPARING: "Continue comparison (in progress)",
            SessionStage.COMPARED: "Investigate discrepancies",
            SessionStage.INVESTIGATING: "Continue investigation",
            SessionStage.COMPLETED: "Session complete - no action needed",
            SessionStage.FAILED: "Resume from last checkpoint",
        }

        return {
            "stage": session.stage.value,
            "next_step": next_steps.get(session.stage, "Unknown"),
            "artifacts_found": ", ".join(artifacts) if artifacts else "None",
        }
