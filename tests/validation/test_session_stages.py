"""Tests for session stage tracking functionality.

Tests cover:
- SessionStage enum values and string representations
- Session model stage fields and defaults
- SessionManager.update_stage() method and transitions
- Valid and invalid stage transitions
- Timestamp recording on stage changes
- Layers completed tracking
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from rustybt.validation.models import Session, SessionStage
from rustybt.validation.session import SessionManager


class TestSessionStageEnum:
    """Test suite for SessionStage enum."""

    def test_session_stage_enum_values(self):
        """Verify all 8 stage values exist with correct string representations."""
        assert SessionStage.CREATED.value == "created"
        assert SessionStage.EXECUTING.value == "executing"
        assert SessionStage.EXECUTED.value == "executed"
        assert SessionStage.COMPARING.value == "comparing"
        assert SessionStage.COMPARED.value == "compared"
        assert SessionStage.INVESTIGATING.value == "investigating"
        assert SessionStage.COMPLETED.value == "completed"
        assert SessionStage.FAILED.value == "failed"

    def test_session_stage_enum_count(self):
        """Verify exactly 8 stages are defined."""
        assert len(SessionStage) == 8

    def test_session_stage_from_value(self):
        """Verify stages can be created from string values."""
        assert SessionStage("created") == SessionStage.CREATED
        assert SessionStage("executing") == SessionStage.EXECUTING
        assert SessionStage("executed") == SessionStage.EXECUTED
        assert SessionStage("comparing") == SessionStage.COMPARING
        assert SessionStage("compared") == SessionStage.COMPARED
        assert SessionStage("investigating") == SessionStage.INVESTIGATING
        assert SessionStage("completed") == SessionStage.COMPLETED
        assert SessionStage("failed") == SessionStage.FAILED

    def test_invalid_stage_value_raises(self):
        """Verify invalid stage values raise ValueError."""
        with pytest.raises(ValueError):
            SessionStage("invalid")


class TestSessionModelStageFields:
    """Test suite for Session model stage fields."""

    def test_session_default_stage(self):
        """Verify Session defaults to CREATED stage."""
        session = Session(
            id="test-session",
            created_at=datetime.now(),
            strategy_name="test",
            rustybt_version="0.1.0",
            backtrader_version="1.9.78",
            python_version="3.12.0",
            status="IN_PROGRESS",
            data_fixture=Path("test.parquet"),
        )

        assert session.stage == SessionStage.CREATED

    def test_session_default_stage_timestamps(self):
        """Verify Session stage timestamps default to None."""
        session = Session(
            id="test-session",
            created_at=datetime.now(),
            strategy_name="test",
            rustybt_version="0.1.0",
            backtrader_version="1.9.78",
            python_version="3.12.0",
            status="IN_PROGRESS",
            data_fixture=Path("test.parquet"),
        )

        assert session.stage_started_at is None
        assert session.execution_completed_at is None
        assert session.comparison_completed_at is None

    def test_session_default_layers_completed(self):
        """Verify Session layers_completed defaults to empty list."""
        session = Session(
            id="test-session",
            created_at=datetime.now(),
            strategy_name="test",
            rustybt_version="0.1.0",
            backtrader_version="1.9.78",
            python_version="3.12.0",
            status="IN_PROGRESS",
            data_fixture=Path("test.parquet"),
        )

        assert session.layers_completed == []
        assert isinstance(session.layers_completed, list)

    def test_session_with_explicit_stage(self):
        """Verify Session accepts explicit stage value."""
        session = Session(
            id="test-session",
            created_at=datetime.now(),
            strategy_name="test",
            rustybt_version="0.1.0",
            backtrader_version="1.9.78",
            python_version="3.12.0",
            status="IN_PROGRESS",
            data_fixture=Path("test.parquet"),
            stage=SessionStage.EXECUTING,
        )

        assert session.stage == SessionStage.EXECUTING

    def test_session_with_all_stage_fields(self):
        """Verify Session accepts all stage-related fields."""
        now = datetime.now()
        layers = ["data", "signals"]

        session = Session(
            id="test-session",
            created_at=now,
            strategy_name="test",
            rustybt_version="0.1.0",
            backtrader_version="1.9.78",
            python_version="3.12.0",
            status="IN_PROGRESS",
            data_fixture=Path("test.parquet"),
            stage=SessionStage.COMPARING,
            stage_started_at=now,
            execution_completed_at=now,
            comparison_completed_at=None,
            layers_completed=layers,
        )

        assert session.stage == SessionStage.COMPARING
        assert session.stage_started_at == now
        assert session.execution_completed_at == now
        assert session.comparison_completed_at is None
        assert session.layers_completed == layers


class TestUpdateStageValidTransitions:
    """Test valid stage transitions in SessionManager.update_stage()."""

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

    def test_valid_transition_created_to_executing(self, session_manager, test_session):
        """Verify CREATED -> EXECUTING succeeds."""
        assert test_session.stage == SessionStage.CREATED

        session_manager.update_stage(test_session, SessionStage.EXECUTING)

        assert test_session.stage == SessionStage.EXECUTING
        assert test_session.stage_started_at is not None

    def test_valid_transition_executing_to_executed(self, session_manager, test_session):
        """Verify EXECUTING -> EXECUTED succeeds."""
        session_manager.update_stage(test_session, SessionStage.EXECUTING)
        session_manager.update_stage(test_session, SessionStage.EXECUTED)

        assert test_session.stage == SessionStage.EXECUTED
        assert test_session.execution_completed_at is not None

    def test_valid_transition_executed_to_comparing(self, session_manager, test_session):
        """Verify EXECUTED -> COMPARING succeeds."""
        session_manager.update_stage(test_session, SessionStage.EXECUTING)
        session_manager.update_stage(test_session, SessionStage.EXECUTED)
        session_manager.update_stage(test_session, SessionStage.COMPARING)

        assert test_session.stage == SessionStage.COMPARING

    def test_valid_transition_comparing_to_compared(self, session_manager, test_session):
        """Verify COMPARING -> COMPARED succeeds."""
        session_manager.update_stage(test_session, SessionStage.EXECUTING)
        session_manager.update_stage(test_session, SessionStage.EXECUTED)
        session_manager.update_stage(test_session, SessionStage.COMPARING)
        session_manager.update_stage(test_session, SessionStage.COMPARED)

        assert test_session.stage == SessionStage.COMPARED
        assert test_session.comparison_completed_at is not None

    def test_valid_transition_compared_to_investigating(
        self, session_manager, test_session
    ):
        """Verify COMPARED -> INVESTIGATING succeeds."""
        session_manager.update_stage(test_session, SessionStage.EXECUTING)
        session_manager.update_stage(test_session, SessionStage.EXECUTED)
        session_manager.update_stage(test_session, SessionStage.COMPARING)
        session_manager.update_stage(test_session, SessionStage.COMPARED)
        session_manager.update_stage(test_session, SessionStage.INVESTIGATING)

        assert test_session.stage == SessionStage.INVESTIGATING

    def test_valid_transition_investigating_to_completed(
        self, session_manager, test_session
    ):
        """Verify INVESTIGATING -> COMPLETED succeeds."""
        session_manager.update_stage(test_session, SessionStage.EXECUTING)
        session_manager.update_stage(test_session, SessionStage.EXECUTED)
        session_manager.update_stage(test_session, SessionStage.COMPARING)
        session_manager.update_stage(test_session, SessionStage.COMPARED)
        session_manager.update_stage(test_session, SessionStage.INVESTIGATING)
        session_manager.update_stage(test_session, SessionStage.COMPLETED)

        assert test_session.stage == SessionStage.COMPLETED

    def test_valid_transition_investigating_back_to_compared(
        self, session_manager, test_session
    ):
        """Verify INVESTIGATING -> COMPARED succeeds (back to review)."""
        session_manager.update_stage(test_session, SessionStage.EXECUTING)
        session_manager.update_stage(test_session, SessionStage.EXECUTED)
        session_manager.update_stage(test_session, SessionStage.COMPARING)
        session_manager.update_stage(test_session, SessionStage.COMPARED)
        session_manager.update_stage(test_session, SessionStage.INVESTIGATING)
        session_manager.update_stage(test_session, SessionStage.COMPARED)

        assert test_session.stage == SessionStage.COMPARED

    def test_valid_transition_any_to_failed(self, session_manager, test_session):
        """Verify any stage can transition to FAILED."""
        # Test from CREATED
        session_manager.update_stage(test_session, SessionStage.FAILED)
        assert test_session.stage == SessionStage.FAILED

    def test_valid_transition_failed_to_created(self, session_manager, test_session):
        """Verify FAILED -> CREATED succeeds (retry from scratch)."""
        session_manager.update_stage(test_session, SessionStage.FAILED)
        session_manager.update_stage(test_session, SessionStage.CREATED)

        assert test_session.stage == SessionStage.CREATED


class TestUpdateStageInvalidTransitions:
    """Test invalid stage transitions raise ValueError."""

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

    def test_invalid_transition_created_to_completed(
        self, session_manager, test_session
    ):
        """Verify CREATED -> COMPLETED raises ValueError (can't skip stages)."""
        with pytest.raises(ValueError, match="Invalid stage transition"):
            session_manager.update_stage(test_session, SessionStage.COMPLETED)

    def test_invalid_transition_created_to_executed(
        self, session_manager, test_session
    ):
        """Verify CREATED -> EXECUTED raises ValueError (must execute first)."""
        with pytest.raises(ValueError, match="Invalid stage transition"):
            session_manager.update_stage(test_session, SessionStage.EXECUTED)

    def test_invalid_transition_created_to_comparing(
        self, session_manager, test_session
    ):
        """Verify CREATED -> COMPARING raises ValueError."""
        with pytest.raises(ValueError, match="Invalid stage transition"):
            session_manager.update_stage(test_session, SessionStage.COMPARING)

    def test_invalid_transition_executing_to_completed(
        self, session_manager, test_session
    ):
        """Verify EXECUTING -> COMPLETED raises ValueError (can't skip stages)."""
        session_manager.update_stage(test_session, SessionStage.EXECUTING)

        with pytest.raises(ValueError, match="Invalid stage transition"):
            session_manager.update_stage(test_session, SessionStage.COMPLETED)

    def test_invalid_transition_from_completed(self, session_manager, test_session):
        """Verify COMPLETED is terminal - no transitions allowed."""
        # Get to COMPLETED state
        session_manager.update_stage(test_session, SessionStage.EXECUTING)
        session_manager.update_stage(test_session, SessionStage.EXECUTED)
        session_manager.update_stage(test_session, SessionStage.COMPARING)
        session_manager.update_stage(test_session, SessionStage.COMPARED)
        session_manager.update_stage(test_session, SessionStage.INVESTIGATING)
        session_manager.update_stage(test_session, SessionStage.COMPLETED)

        with pytest.raises(ValueError, match="Invalid stage transition"):
            session_manager.update_stage(test_session, SessionStage.CREATED)

    def test_invalid_transition_error_message(self, session_manager, test_session):
        """Verify error message includes current stage and allowed transitions."""
        try:
            session_manager.update_stage(test_session, SessionStage.COMPLETED)
            pytest.fail("Expected ValueError")
        except ValueError as e:
            error_msg = str(e)
            assert "created" in error_msg
            assert "completed" in error_msg
            assert "executing" in error_msg  # allowed transition


class TestUpdateStageTimestamps:
    """Test timestamp recording on stage changes."""

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

    def test_stage_started_at_set_on_transition(self, session_manager, test_session):
        """Verify stage_started_at is set on every stage change."""
        before = datetime.now()
        session_manager.update_stage(test_session, SessionStage.EXECUTING)
        after = datetime.now()

        assert test_session.stage_started_at is not None
        assert before <= test_session.stage_started_at <= after

    def test_execution_completed_at_set_on_executed(self, session_manager, test_session):
        """Verify execution_completed_at is set when transitioning to EXECUTED."""
        session_manager.update_stage(test_session, SessionStage.EXECUTING)

        before = datetime.now()
        session_manager.update_stage(test_session, SessionStage.EXECUTED)
        after = datetime.now()

        assert test_session.execution_completed_at is not None
        assert before <= test_session.execution_completed_at <= after

    def test_comparison_completed_at_set_on_compared(
        self, session_manager, test_session
    ):
        """Verify comparison_completed_at is set when transitioning to COMPARED."""
        session_manager.update_stage(test_session, SessionStage.EXECUTING)
        session_manager.update_stage(test_session, SessionStage.EXECUTED)
        session_manager.update_stage(test_session, SessionStage.COMPARING)

        before = datetime.now()
        session_manager.update_stage(test_session, SessionStage.COMPARED)
        after = datetime.now()

        assert test_session.comparison_completed_at is not None
        assert before <= test_session.comparison_completed_at <= after

    def test_timestamps_preserved_through_full_workflow(
        self, session_manager, test_session
    ):
        """Verify all timestamps are correctly recorded through full workflow."""
        session_manager.update_stage(test_session, SessionStage.EXECUTING)
        session_manager.update_stage(test_session, SessionStage.EXECUTED)
        exec_time = test_session.execution_completed_at

        session_manager.update_stage(test_session, SessionStage.COMPARING)
        session_manager.update_stage(test_session, SessionStage.COMPARED)
        comp_time = test_session.comparison_completed_at

        session_manager.update_stage(test_session, SessionStage.INVESTIGATING)
        session_manager.update_stage(test_session, SessionStage.COMPLETED)

        # Verify timestamps are preserved and ordered
        assert test_session.execution_completed_at == exec_time
        assert test_session.comparison_completed_at == comp_time
        assert exec_time <= comp_time


class TestUpdateStageSavesSession:
    """Test that update_stage saves session to disk."""

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

    def test_stage_persisted_after_update(self, session_manager, test_session):
        """Verify stage is persisted to disk after update_stage()."""
        session_manager.update_stage(test_session, SessionStage.EXECUTING)

        # Reload session from disk
        reloaded = session_manager.load_session(test_session.id)

        assert reloaded.stage == SessionStage.EXECUTING

    def test_timestamps_persisted_after_update(self, session_manager, test_session):
        """Verify timestamps are persisted to disk after update_stage()."""
        session_manager.update_stage(test_session, SessionStage.EXECUTING)
        session_manager.update_stage(test_session, SessionStage.EXECUTED)

        # Reload session from disk
        reloaded = session_manager.load_session(test_session.id)

        assert reloaded.stage_started_at is not None
        assert reloaded.execution_completed_at is not None


class TestLayersCompleted:
    """Test layers_completed tracking."""

    def test_layers_completed_starts_empty(self):
        """Verify layers_completed defaults to empty list."""
        session = Session(
            id="test",
            created_at=datetime.now(),
            strategy_name="test",
            rustybt_version="0.1.0",
            backtrader_version="1.9.78",
            python_version="3.12.0",
            status="IN_PROGRESS",
            data_fixture=Path("test.parquet"),
        )

        assert session.layers_completed == []

    def test_layers_completed_can_be_added(self):
        """Verify layers can be added to layers_completed."""
        session = Session(
            id="test",
            created_at=datetime.now(),
            strategy_name="test",
            rustybt_version="0.1.0",
            backtrader_version="1.9.78",
            python_version="3.12.0",
            status="IN_PROGRESS",
            data_fixture=Path("test.parquet"),
        )

        session.layers_completed.append("data")
        session.layers_completed.append("signals")

        assert session.layers_completed == ["data", "signals"]

    def test_layers_completed_persisted(self, tmp_path):
        """Verify layers_completed is persisted to disk."""
        sm = SessionManager(sessions_dir=tmp_path)
        session = sm.create_session(
            strategy_name="test",
            data_fixture=Path("test.parquet"),
            rustybt_version="0.1.0",
            backtrader_version="1.9.78",
        )

        session.layers_completed = ["data", "signals", "orders"]
        sm.update_session(session)

        # Reload
        reloaded = sm.load_session(session.id)
        assert reloaded.layers_completed == ["data", "signals", "orders"]
