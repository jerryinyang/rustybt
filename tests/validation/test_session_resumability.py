"""Tests for session resumability functionality.

Tests cover:
- _last_successful_stage() artifact detection
- resume() method for different session states
- CLI resume command
- Integration scenarios for interrupts at each stage
"""

import json
from datetime import datetime
from pathlib import Path

import pytest

from rustybt.validation.models import Finding, Session, SessionStage
from rustybt.validation.session import SessionManager


class TestLastSuccessfulStageNoArtifacts:
    """Test _last_successful_stage() when no artifacts exist."""

    @pytest.fixture
    def session_manager(self, tmp_path):
        """Create SessionManager with temp directory."""
        return SessionManager(sessions_dir=tmp_path)

    @pytest.fixture
    def test_session(self, session_manager):
        """Create a test session."""
        return session_manager.create_session(
            strategy_name="test_strategy",
            data_fixture=Path("test.parquet"),
            rustybt_version="0.1.0",
            backtrader_version="1.9.78",
        )

    def test_no_logs_returns_created(self, session_manager, test_session):
        """Verify no logs -> CREATED stage."""
        result = session_manager._last_successful_stage(test_session)
        assert result == SessionStage.CREATED

    def test_partial_logs_returns_created(self, session_manager, test_session):
        """Verify only one log file -> CREATED stage."""
        session_dir = session_manager.sessions_dir / test_session.id
        logs_dir = session_dir / "logs"

        # Create only rustybt log
        (logs_dir / "rustybt.jsonl").write_text('{"layer": "signals"}\n')

        result = session_manager._last_successful_stage(test_session)
        assert result == SessionStage.CREATED


class TestLastSuccessfulStageWithLogs:
    """Test _last_successful_stage() when logs exist."""

    @pytest.fixture
    def session_manager(self, tmp_path):
        """Create SessionManager with temp directory."""
        return SessionManager(sessions_dir=tmp_path)

    @pytest.fixture
    def test_session(self, session_manager):
        """Create a test session."""
        return session_manager.create_session(
            strategy_name="test_strategy",
            data_fixture=Path("test.parquet"),
            rustybt_version="0.1.0",
            backtrader_version="1.9.78",
        )

    def _create_valid_logs(self, session_manager, session):
        """Helper to create valid log files."""
        session_dir = session_manager.sessions_dir / session.id
        logs_dir = session_dir / "logs"

        # Create valid JSONL log entries with required schema fields
        log_entry = json.dumps({
            "layer": "signals",
            "event": "indicator_value",
            "timestamp": datetime.now().isoformat(),
            "data": {"value": 100},
        })

        (logs_dir / "rustybt.jsonl").write_text(f"{log_entry}\n")
        (logs_dir / "backtrader.jsonl").write_text(f"{log_entry}\n")

    def test_valid_logs_no_analysis_returns_executed(self, session_manager, test_session):
        """Verify valid logs without analysis -> EXECUTED stage."""
        self._create_valid_logs(session_manager, test_session)

        result = session_manager._last_successful_stage(test_session)
        assert result == SessionStage.EXECUTED

    def test_invalid_logs_returns_created(self, session_manager, test_session):
        """Verify invalid log content -> CREATED stage."""
        session_dir = session_manager.sessions_dir / test_session.id
        logs_dir = session_dir / "logs"

        # Create invalid JSONL (missing required fields)
        (logs_dir / "rustybt.jsonl").write_text("invalid json content\n")
        (logs_dir / "backtrader.jsonl").write_text("invalid json content\n")

        result = session_manager._last_successful_stage(test_session)
        assert result == SessionStage.CREATED


class TestLastSuccessfulStageWithAnalysis:
    """Test _last_successful_stage() when analysis reports exist."""

    @pytest.fixture
    def session_manager(self, tmp_path):
        """Create SessionManager with temp directory."""
        return SessionManager(sessions_dir=tmp_path)

    @pytest.fixture
    def test_session(self, session_manager):
        """Create a test session."""
        return session_manager.create_session(
            strategy_name="test_strategy",
            data_fixture=Path("test.parquet"),
            rustybt_version="0.1.0",
            backtrader_version="1.9.78",
        )

    def _create_valid_logs(self, session_manager, session):
        """Helper to create valid log files."""
        session_dir = session_manager.sessions_dir / session.id
        logs_dir = session_dir / "logs"

        log_entry = json.dumps({
            "layer": "signals",
            "event": "indicator_value",
            "timestamp": datetime.now().isoformat(),
            "data": {"value": 100},
        })

        (logs_dir / "rustybt.jsonl").write_text(f"{log_entry}\n")
        (logs_dir / "backtrader.jsonl").write_text(f"{log_entry}\n")

    def _create_analysis_reports(self, session_manager, session):
        """Helper to create analysis reports."""
        session_dir = session_manager.sessions_dir / session.id
        analysis_dir = session_dir / "analysis"
        analysis_dir.mkdir(exist_ok=True)

        (analysis_dir / "layer_signals_report.md").write_text("# Signal Analysis\n")

    def test_with_analysis_no_findings_returns_investigating(
        self, session_manager, test_session
    ):
        """Verify analysis reports exist with no findings -> INVESTIGATING stage.

        When analysis is complete and there are no findings (or all findings
        are classified), investigation is considered complete.
        """
        self._create_valid_logs(session_manager, test_session)
        self._create_analysis_reports(session_manager, test_session)

        result = session_manager._last_successful_stage(test_session)
        # No findings = all findings classified = investigation complete
        assert result == SessionStage.INVESTIGATING

    def test_with_unclassified_findings_returns_compared(
        self, session_manager, test_session
    ):
        """Verify unclassified findings -> COMPARED stage."""
        self._create_valid_logs(session_manager, test_session)
        self._create_analysis_reports(session_manager, test_session)

        # Add unclassified finding
        test_session.findings.append(
            Finding(
                id="finding_001",
                layer="signals",
                description="Signal value mismatch",
                classification=None,  # Unclassified
            )
        )
        session_manager.update_session(test_session)

        result = session_manager._last_successful_stage(test_session)
        assert result == SessionStage.COMPARED

    def test_all_findings_classified_returns_investigating(
        self, session_manager, test_session
    ):
        """Verify all findings classified -> INVESTIGATING stage."""
        self._create_valid_logs(session_manager, test_session)
        self._create_analysis_reports(session_manager, test_session)

        # Add classified finding
        test_session.findings.append(
            Finding(
                id="finding_001",
                layer="signals",
                description="Signal value mismatch",
                classification="BUG",
            )
        )
        session_manager.update_session(test_session)

        result = session_manager._last_successful_stage(test_session)
        assert result == SessionStage.INVESTIGATING


class TestResumeMethod:
    """Test SessionManager.resume() method."""

    @pytest.fixture
    def session_manager(self, tmp_path):
        """Create SessionManager with temp directory."""
        return SessionManager(sessions_dir=tmp_path)

    @pytest.fixture
    def test_session(self, session_manager):
        """Create a test session."""
        return session_manager.create_session(
            strategy_name="test_strategy",
            data_fixture=Path("test.parquet"),
            rustybt_version="0.1.0",
            backtrader_version="1.9.78",
        )

    def test_resume_loads_session(self, session_manager, test_session):
        """Verify resume() loads session by ID."""
        resumed = session_manager.resume(test_session.id)
        assert resumed.id == test_session.id

    def test_resume_completed_raises_error(self, session_manager, test_session):
        """Verify resume() raises ValueError for COMPLETED session."""
        # Set session to COMPLETED
        test_session.stage = SessionStage.COMPLETED
        session_manager.update_session(test_session)

        with pytest.raises(ValueError, match="already COMPLETED"):
            session_manager.resume(test_session.id)

    def test_resume_failed_resets_to_last_stage(self, session_manager, test_session):
        """Verify FAILED session is reset to last successful stage."""
        # Set session to FAILED
        test_session.stage = SessionStage.FAILED
        session_manager.update_session(test_session)

        resumed = session_manager.resume(test_session.id)

        # With no artifacts, should reset to CREATED
        assert resumed.stage == SessionStage.CREATED
        assert resumed.status == "IN_PROGRESS"

    def test_resume_sets_status_in_progress(self, session_manager, test_session):
        """Verify resume() sets status to IN_PROGRESS."""
        # Set to different status
        test_session.status = "EXECUTED"
        session_manager.update_session(test_session)

        resumed = session_manager.resume(test_session.id)

        assert resumed.status == "IN_PROGRESS"

    def test_resume_saves_session(self, session_manager, test_session):
        """Verify resume() persists changes to disk."""
        session_manager.resume(test_session.id)

        # Reload and verify
        reloaded = session_manager.load_session(test_session.id)
        assert reloaded.status == "IN_PROGRESS"

    def test_resume_nonexistent_raises_error(self, session_manager):
        """Verify resume() raises FileNotFoundError for nonexistent session."""
        with pytest.raises(FileNotFoundError):
            session_manager.resume("nonexistent-session-id")


class TestResumeInfo:
    """Test SessionManager.get_resume_info() method."""

    @pytest.fixture
    def session_manager(self, tmp_path):
        """Create SessionManager with temp directory."""
        return SessionManager(sessions_dir=tmp_path)

    @pytest.fixture
    def test_session(self, session_manager):
        """Create a test session."""
        return session_manager.create_session(
            strategy_name="test_strategy",
            data_fixture=Path("test.parquet"),
            rustybt_version="0.1.0",
            backtrader_version="1.9.78",
        )

    def test_resume_info_returns_stage(self, session_manager, test_session):
        """Verify get_resume_info() returns current stage."""
        info = session_manager.get_resume_info(test_session)
        assert info["stage"] == "created"

    def test_resume_info_returns_next_step(self, session_manager, test_session):
        """Verify get_resume_info() returns next step description."""
        info = session_manager.get_resume_info(test_session)
        assert "Execute strategy" in info["next_step"]

    def test_resume_info_shows_no_artifacts(self, session_manager, test_session):
        """Verify get_resume_info() shows 'None' when no artifacts exist."""
        info = session_manager.get_resume_info(test_session)
        assert info["artifacts_found"] == "None"

    def test_resume_info_lists_log_artifacts(self, session_manager, test_session):
        """Verify get_resume_info() lists log files when present."""
        session_dir = session_manager.sessions_dir / test_session.id
        logs_dir = session_dir / "logs"
        (logs_dir / "rustybt.jsonl").write_text('{"test": true}\n')

        info = session_manager.get_resume_info(test_session)
        assert "rustybt.jsonl" in info["artifacts_found"]


class TestIntegrationResumeScenarios:
    """Integration tests for various resume scenarios."""

    @pytest.fixture
    def session_manager(self, tmp_path):
        """Create SessionManager with temp directory."""
        return SessionManager(sessions_dir=tmp_path)

    @pytest.fixture
    def test_session(self, session_manager):
        """Create a test session."""
        return session_manager.create_session(
            strategy_name="test_strategy",
            data_fixture=Path("test.parquet"),
            rustybt_version="0.1.0",
            backtrader_version="1.9.78",
        )

    def _create_valid_logs(self, session_manager, session):
        """Helper to create valid log files."""
        session_dir = session_manager.sessions_dir / session.id
        logs_dir = session_dir / "logs"

        log_entry = json.dumps({
            "layer": "signals",
            "event": "indicator_value",
            "timestamp": datetime.now().isoformat(),
            "data": {"value": 100},
        })

        (logs_dir / "rustybt.jsonl").write_text(f"{log_entry}\n")
        (logs_dir / "backtrader.jsonl").write_text(f"{log_entry}\n")

    @pytest.mark.integration
    def test_resume_after_execution_interrupt(self, session_manager, test_session):
        """Test resuming session interrupted during execution."""
        # Simulate interrupt during execution (no logs created)
        test_session.stage = SessionStage.FAILED
        session_manager.update_session(test_session)

        # Resume
        resumed = session_manager.resume(test_session.id)

        assert resumed.stage == SessionStage.CREATED
        assert resumed.status == "IN_PROGRESS"

    @pytest.mark.integration
    def test_resume_after_comparison_interrupt(self, session_manager, test_session):
        """Test resuming session interrupted during comparison."""
        # Create valid logs (execution succeeded)
        self._create_valid_logs(session_manager, test_session)

        # Simulate interrupt during comparison
        test_session.stage = SessionStage.FAILED
        session_manager.update_session(test_session)

        # Resume
        resumed = session_manager.resume(test_session.id)

        assert resumed.stage == SessionStage.EXECUTED
        assert resumed.status == "IN_PROGRESS"

    @pytest.mark.integration
    def test_resume_after_investigation_interrupt(self, session_manager, test_session):
        """Test resuming session interrupted during investigation."""
        # Create valid logs
        self._create_valid_logs(session_manager, test_session)

        # Create analysis reports
        session_dir = session_manager.sessions_dir / test_session.id
        analysis_dir = session_dir / "analysis"
        analysis_dir.mkdir(exist_ok=True)
        (analysis_dir / "layer_signals_report.md").write_text("# Report\n")

        # Add unclassified finding
        test_session.findings.append(
            Finding(
                id="finding_001",
                layer="signals",
                description="Test finding",
                classification=None,
            )
        )

        # Simulate interrupt during investigation
        test_session.stage = SessionStage.FAILED
        session_manager.update_session(test_session)

        # Resume
        resumed = session_manager.resume(test_session.id)

        assert resumed.stage == SessionStage.COMPARED
        assert resumed.status == "IN_PROGRESS"
        # Verify findings preserved
        assert len(resumed.findings) == 1

    @pytest.mark.integration
    def test_resume_preserves_partial_results(self, session_manager, test_session):
        """Test that resume preserves existing artifacts."""
        # Create logs
        self._create_valid_logs(session_manager, test_session)

        # Set to FAILED
        test_session.stage = SessionStage.FAILED
        session_manager.update_session(test_session)

        # Resume
        session_manager.resume(test_session.id)

        # Verify logs still exist
        session_dir = session_manager.sessions_dir / test_session.id
        logs_dir = session_dir / "logs"
        assert (logs_dir / "rustybt.jsonl").exists()
        assert (logs_dir / "backtrader.jsonl").exists()

    @pytest.mark.integration
    def test_resume_updates_stage_timestamp(self, session_manager, test_session):
        """Test that resume updates stage_started_at timestamp."""
        # Set to FAILED
        test_session.stage = SessionStage.FAILED
        old_timestamp = datetime(2025, 1, 1, 0, 0, 0)
        test_session.stage_started_at = old_timestamp
        session_manager.update_session(test_session)

        # Resume
        resumed = session_manager.resume(test_session.id)

        # Timestamp should be updated
        assert resumed.stage_started_at is not None
        assert resumed.stage_started_at > old_timestamp
