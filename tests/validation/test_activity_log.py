"""Tests for timestamped activity log functionality.

This module tests Story 3.6: Implement Timestamped Activity Log
- Activity dataclass serialization
- Auto-logging on session operations
- Manual activity logging
- CLI activities command
"""

from datetime import datetime
from pathlib import Path

import pytest
from click.testing import CliRunner

from rustybt.validation.cli import main
from rustybt.validation.models import Activity, Finding, SessionStage
from rustybt.validation.session import SessionManager


class TestActivityDataclass:
    """Test Activity dataclass serialization."""

    def test_activity_to_dict_basic(self):
        """Test Activity serializes to dict with required fields."""
        timestamp = datetime(2025, 11, 26, 10, 30, 0)
        activity = Activity(
            timestamp=timestamp,
            action="created",
            actor="system",
        )

        result = activity.to_dict()

        assert result["timestamp"] == "2025-11-26T10:30:00"
        assert result["action"] == "created"
        assert result["actor"] == "system"
        assert result["details"] is None

    def test_activity_to_dict_with_details(self):
        """Test Activity serializes details dict."""
        timestamp = datetime(2025, 11, 26, 10, 30, 0)
        activity = Activity(
            timestamp=timestamp,
            action="note",
            actor="developer",
            details={"message": "Investigated RSI calculation"},
        )

        result = activity.to_dict()

        assert result["details"] == {"message": "Investigated RSI calculation"}

    def test_activity_from_dict_basic(self):
        """Test Activity deserializes from dict."""
        data = {
            "timestamp": "2025-11-26T10:30:00",
            "action": "created",
            "actor": "system",
        }

        activity = Activity.from_dict(data)

        assert activity.timestamp == datetime(2025, 11, 26, 10, 30, 0)
        assert activity.action == "created"
        assert activity.actor == "system"
        assert activity.details is None

    def test_activity_from_dict_with_details(self):
        """Test Activity deserializes details dict."""
        data = {
            "timestamp": "2025-11-26T10:30:00",
            "action": "note",
            "actor": "developer",
            "details": {"message": "Test note"},
        }

        activity = Activity.from_dict(data)

        assert activity.details == {"message": "Test note"}

    def test_activity_roundtrip_serialization(self):
        """Test Activity serializes and deserializes correctly."""
        original = Activity(
            timestamp=datetime(2025, 11, 26, 10, 30, 45),
            action="finding_added",
            actor="system",
            details={"message": "Finding F001 added in data layer"},
        )

        serialized = original.to_dict()
        restored = Activity.from_dict(serialized)

        assert restored.timestamp == original.timestamp
        assert restored.action == original.action
        assert restored.actor == original.actor
        assert restored.details == original.details

    def test_activity_default_actor_is_system(self):
        """Test Activity defaults actor to 'system'."""
        data = {
            "timestamp": "2025-11-26T10:30:00",
            "action": "created",
        }

        activity = Activity.from_dict(data)

        assert activity.actor == "system"


class TestSessionLogActivity:
    """Test Session.log_activity() method."""

    @pytest.fixture
    def session_manager(self, tmp_path: Path) -> SessionManager:
        """Create a SessionManager with temporary directory."""
        return SessionManager(sessions_dir=tmp_path / "validation-sessions")

    @pytest.fixture
    def fixture_file(self, tmp_path: Path) -> Path:
        """Create a temporary fixture file."""
        fixture = tmp_path / "test_fixture.parquet"
        fixture.touch()
        return fixture

    def test_log_activity_appends_to_list(
        self, session_manager: SessionManager, fixture_file: Path
    ):
        """Test log_activity appends activity to session.activities."""
        session = session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78"
        )

        initial_count = len(session.activities)
        session.log_activity("test_action")

        assert len(session.activities) == initial_count + 1
        assert session.activities[-1].action == "test_action"

    def test_log_activity_includes_timestamp(
        self, session_manager: SessionManager, fixture_file: Path
    ):
        """Test log_activity records current timestamp."""
        session = session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78"
        )
        before = datetime.now()

        session.log_activity("test_action")

        after = datetime.now()
        activity = session.activities[-1]
        assert before <= activity.timestamp <= after

    def test_log_activity_with_message(
        self, session_manager: SessionManager, fixture_file: Path
    ):
        """Test log_activity stores message in details."""
        session = session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78"
        )

        session.log_activity("note", "Investigation complete")

        activity = session.activities[-1]
        assert activity.details == {"message": "Investigation complete"}

    def test_log_activity_with_custom_actor(
        self, session_manager: SessionManager, fixture_file: Path
    ):
        """Test log_activity supports custom actor."""
        session = session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78"
        )

        session.log_activity("note", "Custom note", actor="developer")

        activity = session.activities[-1]
        assert activity.actor == "developer"

    def test_log_activity_default_actor_is_system(
        self, session_manager: SessionManager, fixture_file: Path
    ):
        """Test log_activity defaults actor to 'system'."""
        session = session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78"
        )

        session.log_activity("test_action")

        activity = session.activities[-1]
        assert activity.actor == "system"


class TestAutoLogging:
    """Test auto-logging on SessionManager operations."""

    @pytest.fixture
    def session_manager(self, tmp_path: Path) -> SessionManager:
        """Create a SessionManager with temporary directory."""
        return SessionManager(sessions_dir=tmp_path / "validation-sessions")

    @pytest.fixture
    def fixture_file(self, tmp_path: Path) -> Path:
        """Create a temporary fixture file."""
        fixture = tmp_path / "test_fixture.parquet"
        fixture.touch()
        return fixture

    def test_create_session_auto_logs_created(
        self, session_manager: SessionManager, fixture_file: Path
    ):
        """Test session creation auto-logs 'created' activity."""
        session = session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78"
        )

        assert len(session.activities) == 1
        assert session.activities[0].action == "created"
        assert session.activities[0].actor == "system"
        assert "test_strategy" in session.activities[0].details["message"]

    def test_update_stage_auto_logs_stage_changed(
        self, session_manager: SessionManager, fixture_file: Path
    ):
        """Test stage update auto-logs 'stage_changed' activity."""
        session = session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78"
        )
        initial_count = len(session.activities)

        session_manager.update_stage(session, SessionStage.EXECUTING)

        assert len(session.activities) == initial_count + 1
        activity = session.activities[-1]
        assert activity.action == "stage_changed"
        assert "created" in activity.details["message"]
        assert "executing" in activity.details["message"]

    def test_add_finding_auto_logs_finding_added(
        self, session_manager: SessionManager, fixture_file: Path
    ):
        """Test adding finding auto-logs 'finding_added' activity."""
        session = session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78"
        )
        initial_count = len(session.activities)

        finding = Finding(
            id="finding_001",
            layer="data",
            description="Test discrepancy",
        )
        session_manager.add_finding(session, finding)

        assert len(session.activities) == initial_count + 1
        activity = session.activities[-1]
        assert activity.action == "finding_added"
        assert "finding_001" in activity.details["message"]
        assert "data" in activity.details["message"]

    def test_resume_auto_logs_session_resumed(
        self, session_manager: SessionManager, fixture_file: Path
    ):
        """Test resume auto-logs 'session_resumed' activity."""
        session = session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78"
        )
        initial_count = len(session.activities)

        resumed = session_manager.resume(session.id)

        assert len(resumed.activities) == initial_count + 1
        activity = resumed.activities[-1]
        assert activity.action == "session_resumed"


class TestActivityPersistence:
    """Test activities persisted in YAML."""

    @pytest.fixture
    def session_manager(self, tmp_path: Path) -> SessionManager:
        """Create a SessionManager with temporary directory."""
        return SessionManager(sessions_dir=tmp_path / "validation-sessions")

    @pytest.fixture
    def fixture_file(self, tmp_path: Path) -> Path:
        """Create a temporary fixture file."""
        fixture = tmp_path / "test_fixture.parquet"
        fixture.touch()
        return fixture

    def test_activities_persisted_after_create(
        self, session_manager: SessionManager, fixture_file: Path
    ):
        """Test activities saved in YAML after session creation."""
        session = session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78"
        )

        reloaded = session_manager.load_session(session.id)

        assert len(reloaded.activities) == 1
        assert reloaded.activities[0].action == "created"

    def test_activities_persisted_after_log_activity(
        self, session_manager: SessionManager, fixture_file: Path
    ):
        """Test manually logged activities saved in YAML."""
        session = session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78"
        )
        session.log_activity("note", "Test note", actor="developer")
        session_manager.update_session(session)

        reloaded = session_manager.load_session(session.id)

        assert len(reloaded.activities) >= 2
        note_activities = [a for a in reloaded.activities if a.action == "note"]
        assert len(note_activities) == 1
        assert note_activities[0].actor == "developer"
        assert note_activities[0].details["message"] == "Test note"

    def test_activities_persisted_after_stage_change(
        self, session_manager: SessionManager, fixture_file: Path
    ):
        """Test stage change activities saved in YAML."""
        session = session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78"
        )
        session_manager.update_stage(session, SessionStage.EXECUTING)

        reloaded = session_manager.load_session(session.id)

        stage_activities = [a for a in reloaded.activities if a.action == "stage_changed"]
        assert len(stage_activities) == 1

    def test_activities_persisted_after_add_finding(
        self, session_manager: SessionManager, fixture_file: Path
    ):
        """Test finding addition activities saved in YAML."""
        session = session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78"
        )
        finding = Finding(id="finding_001", layer="data", description="Test")
        session_manager.add_finding(session, finding)

        reloaded = session_manager.load_session(session.id)

        finding_activities = [a for a in reloaded.activities if a.action == "finding_added"]
        assert len(finding_activities) == 1

    def test_multiple_activities_accumulated(
        self, session_manager: SessionManager, fixture_file: Path
    ):
        """Test multiple activities accumulate correctly."""
        session = session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78"
        )
        session_manager.update_stage(session, SessionStage.EXECUTING)
        session.log_activity("note", "First note")
        session_manager.update_session(session)

        reloaded = session_manager.load_session(session.id)

        # Should have: created, stage_changed, note
        assert len(reloaded.activities) >= 3
        actions = [a.action for a in reloaded.activities]
        assert "created" in actions
        assert "stage_changed" in actions
        assert "note" in actions


class TestCLIActivitiesCommand:
    """Test CLI session activities command."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def fixture_file(self, tmp_path: Path) -> Path:
        """Create a temporary fixture file."""
        fixture = tmp_path / "test_fixture.parquet"
        fixture.touch()
        return fixture

    def test_cli_activities_shows_activity_log(
        self, runner: CliRunner, tmp_path: Path, fixture_file: Path
    ):
        """Test CLI activities command displays activities."""
        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Create session
            result1 = runner.invoke(main, [
                "session", "create",
                "--strategy", "test_strategy",
                "--data", str(fixture_file),
            ])
            assert result1.exit_code == 0
            session_id = result1.output.split("Session created: ")[1].split("\n")[0]

            # Show activities
            result2 = runner.invoke(main, ["session", "activities", session_id])

            assert result2.exit_code == 0
            assert "Activity log for session" in result2.output
            assert "created" in result2.output

    def test_cli_activities_json_format(
        self, runner: CliRunner, tmp_path: Path, fixture_file: Path
    ):
        """Test CLI activities command JSON output."""
        import json

        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Create session
            result1 = runner.invoke(main, [
                "session", "create",
                "--strategy", "test_strategy",
                "--data", str(fixture_file),
            ])
            session_id = result1.output.split("Session created: ")[1].split("\n")[0]

            # Show activities as JSON
            result2 = runner.invoke(main, [
                "session", "activities", session_id, "--format", "json"
            ])

            assert result2.exit_code == 0
            activities = json.loads(result2.output)
            assert isinstance(activities, list)
            assert len(activities) >= 1
            assert activities[0]["action"] == "created"

    def test_cli_activities_nonexistent_session(
        self, runner: CliRunner, tmp_path: Path
    ):
        """Test CLI activities shows error for nonexistent session."""
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, ["session", "activities", "nonexistent-id"])

            assert result.exit_code == 1
            assert "Session not found" in result.output

    def test_cli_activities_shows_message_details(
        self, runner: CliRunner, tmp_path: Path, fixture_file: Path
    ):
        """Test CLI activities shows message from details."""
        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Create session
            result1 = runner.invoke(main, [
                "session", "create",
                "--strategy", "test_strategy",
                "--data", str(fixture_file),
            ])
            session_id = result1.output.split("Session created: ")[1].split("\n")[0]

            # Show activities - should show strategy name in message
            result2 = runner.invoke(main, ["session", "activities", session_id])

            assert result2.exit_code == 0
            # The "created" activity includes strategy name in message
            assert "test_strategy" in result2.output
