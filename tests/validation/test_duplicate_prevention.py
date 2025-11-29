"""Tests for duplicate prevention in session and finding management.

This module tests Story 3.4: Implement Duplicate Prevention
- Session duplicate detection
- Finding duplicate detection
- --force flag for overriding duplicates
- SUPERSEDED status handling
"""

from datetime import datetime
from pathlib import Path

import pytest
from click.testing import CliRunner

from rustybt.validation.cli import main
from rustybt.validation.exceptions import DuplicateFindingError, DuplicateSessionError
from rustybt.validation.models import Finding, Session
from rustybt.validation.session import SessionManager


class TestDuplicateSessionError:
    """Test DuplicateSessionError exception class."""

    def test_exception_message_contains_session_id(self):
        """Verify error message contains existing session ID."""
        error = DuplicateSessionError("20251124-143000-sma_crossover", "sma_crossover")
        assert "20251124-143000-sma_crossover" in str(error)

    def test_exception_message_contains_strategy(self):
        """Verify error message contains strategy name."""
        error = DuplicateSessionError("20251124-143000-sma_crossover", "sma_crossover")
        assert "sma_crossover" in str(error)

    def test_exception_message_suggests_resume(self):
        """Verify error message suggests using resume command."""
        error = DuplicateSessionError("20251124-143000-sma_crossover", "sma_crossover")
        assert "session resume" in str(error)

    def test_exception_message_suggests_delete(self):
        """Verify error message suggests using delete command."""
        error = DuplicateSessionError("20251124-143000-sma_crossover", "sma_crossover")
        assert "session delete" in str(error)

    def test_exception_attributes(self):
        """Verify exception stores session ID and strategy as attributes."""
        error = DuplicateSessionError("session_123", "test_strategy")
        assert error.existing_session_id == "session_123"
        assert error.strategy == "test_strategy"


class TestDuplicateFindingError:
    """Test DuplicateFindingError exception class."""

    def test_exception_message_contains_finding_id(self):
        """Verify error message contains existing finding ID."""
        error = DuplicateFindingError("layer_1_finding_001")
        assert "layer_1_finding_001" in str(error)

    def test_exception_attributes(self):
        """Verify exception stores finding ID as attribute."""
        error = DuplicateFindingError("finding_123")
        assert error.existing_finding_id == "finding_123"


class TestSessionDuplicateDetection:
    """Test session duplicate detection in SessionManager."""

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

    def test_duplicate_session_raises_error(
        self, session_manager: SessionManager, fixture_file: Path
    ):
        """Test creating duplicate session raises DuplicateSessionError."""
        # Create first session
        session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78"
        )

        # Try to create duplicate
        with pytest.raises(DuplicateSessionError) as exc_info:
            session_manager.create_session(
                "test_strategy", fixture_file, "0.3.4", "1.9.78"
            )

        assert "already in progress" in str(exc_info.value)
        assert "test_strategy" in str(exc_info.value)

    def test_duplicate_session_error_includes_session_id(
        self, session_manager: SessionManager, fixture_file: Path
    ):
        """Verify error message contains existing session ID."""
        first_session = session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78"
        )

        with pytest.raises(DuplicateSessionError) as exc_info:
            session_manager.create_session(
                "test_strategy", fixture_file, "0.3.4", "1.9.78"
            )

        assert first_session.id in str(exc_info.value)

    def test_different_strategy_no_error(
        self, session_manager: SessionManager, fixture_file: Path
    ):
        """Test different strategy names don't conflict."""
        session_manager.create_session(
            "strategy_a", fixture_file, "0.3.4", "1.9.78"
        )

        # Should not raise - different strategy
        session2 = session_manager.create_session(
            "strategy_b", fixture_file, "0.3.4", "1.9.78"
        )

        assert session2.strategy_name == "strategy_b"

    def test_completed_session_no_conflict(
        self, session_manager: SessionManager, fixture_file: Path
    ):
        """Test COMPLETED sessions don't conflict with new sessions."""
        first = session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78"
        )

        # Mark as completed
        first.status = "COMPLETED"
        session_manager.update_session(first)

        # Should not raise - first session is COMPLETED
        second = session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78"
        )

        assert second.status == "IN_PROGRESS"


class TestForceFlag:
    """Test --force flag functionality."""

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

    def test_force_flag_supersedes_existing(
        self, session_manager: SessionManager, fixture_file: Path
    ):
        """Test --force marks existing session as SUPERSEDED."""
        first = session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78"
        )
        first_id = first.id

        # Create with force
        second = session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78", force=True
        )

        # Check first is superseded
        first_reloaded = session_manager.load_session(first_id)
        assert first_reloaded.status == "SUPERSEDED"
        assert second.status == "IN_PROGRESS"

    def test_force_flag_creates_new_session(
        self, session_manager: SessionManager, fixture_file: Path
    ):
        """Test --force creates a new session after superseding existing."""
        first = session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78"
        )

        second = session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78", force=True
        )

        # New session should be different
        assert first.id != second.id
        assert second.status == "IN_PROGRESS"

    def test_force_flag_supersedes_multiple_sessions(
        self, session_manager: SessionManager, fixture_file: Path
    ):
        """Test --force supersedes multiple IN_PROGRESS sessions."""
        # This scenario shouldn't normally happen, but test it anyway
        first = session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78"
        )

        # Forcibly create second (superseding first)
        second = session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78", force=True
        )

        # Third session with force
        third = session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78", force=True
        )

        # First was superseded by second, second was superseded by third
        first_reloaded = session_manager.load_session(first.id)
        second_reloaded = session_manager.load_session(second.id)

        assert first_reloaded.status == "SUPERSEDED"
        assert second_reloaded.status == "SUPERSEDED"
        assert third.status == "IN_PROGRESS"

    def test_superseded_status_preserved_in_yaml(
        self, session_manager: SessionManager, fixture_file: Path
    ):
        """Test SUPERSEDED status is persisted correctly to YAML."""
        first = session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78"
        )
        first_id = first.id

        # Create with force (supersedes first)
        session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78", force=True
        )

        # Load from disk and verify
        reloaded = session_manager.load_session(first_id)
        assert reloaded.status == "SUPERSEDED"


class TestFindingDuplicateDetection:
    """Test finding duplicate detection in SessionManager."""

    @pytest.fixture
    def session_manager(self, tmp_path: Path) -> SessionManager:
        """Create a SessionManager with temporary directory."""
        return SessionManager(sessions_dir=tmp_path / "validation-sessions")

    @pytest.fixture
    def session(self, session_manager: SessionManager, tmp_path: Path) -> Session:
        """Create a test session."""
        fixture = tmp_path / "test_fixture.parquet"
        fixture.touch()
        return session_manager.create_session(
            "test_strategy", fixture, "0.3.4", "1.9.78"
        )

    def test_duplicate_finding_raises_error(
        self, session_manager: SessionManager, session: Session
    ):
        """Test adding duplicate finding raises DuplicateFindingError."""
        finding = Finding(
            id="finding_001",
            layer="data",
            description="Test discrepancy",
        )

        # Add first finding
        session_manager.add_finding(session, finding)

        # Try to add duplicate
        duplicate = Finding(
            id="finding_001",  # Same ID
            layer="data",
            description="Different description",
        )

        with pytest.raises(DuplicateFindingError) as exc_info:
            session_manager.add_finding(session, duplicate)

        assert "finding_001" in str(exc_info.value)

    def test_duplicate_finding_error_includes_id(
        self, session_manager: SessionManager, session: Session
    ):
        """Verify error message contains existing finding ID."""
        finding = Finding(
            id="layer_1_finding_001",
            layer="data",
            description="Test",
        )
        session_manager.add_finding(session, finding)

        with pytest.raises(DuplicateFindingError) as exc_info:
            session_manager.add_finding(session, finding)

        assert exc_info.value.existing_finding_id == "layer_1_finding_001"

    def test_different_finding_ids_no_error(
        self, session_manager: SessionManager, session: Session
    ):
        """Test different finding IDs don't conflict."""
        finding1 = Finding(
            id="finding_001",
            layer="data",
            description="First finding",
        )
        finding2 = Finding(
            id="finding_002",
            layer="data",
            description="Second finding",
        )

        session_manager.add_finding(session, finding1)
        session_manager.add_finding(session, finding2)  # Should not raise

        assert len(session.findings) == 2


class TestCLIDuplicateHandling:
    """Test CLI error handling for duplicates."""

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

    def test_cli_duplicate_session_shows_error(
        self, runner: CliRunner, tmp_path: Path, fixture_file: Path
    ):
        """Test CLI displays user-friendly error on duplicate session."""
        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Create first session
            result1 = runner.invoke(main, [
                "session", "create",
                "--strategy", "test_strategy",
                "--data", str(fixture_file),
            ])
            assert result1.exit_code == 0

            # Try to create duplicate
            result2 = runner.invoke(main, [
                "session", "create",
                "--strategy", "test_strategy",
                "--data", str(fixture_file),
            ])

            assert result2.exit_code == 1
            assert "already in progress" in result2.output
            assert "Suggested actions" in result2.output

    def test_cli_force_flag_shows_warning(
        self, runner: CliRunner, tmp_path: Path, fixture_file: Path
    ):
        """Test CLI warns about superseded session when using --force."""
        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Create first session
            result1 = runner.invoke(main, [
                "session", "create",
                "--strategy", "test_strategy",
                "--data", str(fixture_file),
            ])
            assert result1.exit_code == 0

            # Create with --force
            result2 = runner.invoke(main, [
                "session", "create",
                "--strategy", "test_strategy",
                "--data", str(fixture_file),
                "--force",
            ])

            assert result2.exit_code == 0
            assert "SUPERSEDED" in result2.output
            assert "Session created" in result2.output


class TestFindSessions:
    """Test find_sessions method for duplicate detection."""

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

    def test_find_sessions_by_strategy(
        self, session_manager: SessionManager, fixture_file: Path
    ):
        """Test finding sessions by strategy name."""
        session_manager.create_session("strategy_a", fixture_file, "0.3.4", "1.9.78")
        session_manager.create_session("strategy_b", fixture_file, "0.3.4", "1.9.78")

        results = session_manager.find_sessions(strategy="strategy_a")

        assert len(results) == 1
        assert results[0].strategy_name == "strategy_a"

    def test_find_sessions_by_status(
        self, session_manager: SessionManager, fixture_file: Path
    ):
        """Test finding sessions by status."""
        session1 = session_manager.create_session(
            "strategy_a", fixture_file, "0.3.4", "1.9.78"
        )
        session2 = session_manager.create_session(
            "strategy_b", fixture_file, "0.3.4", "1.9.78"
        )

        # Mark one as COMPLETED
        session1.status = "COMPLETED"
        session_manager.update_session(session1)

        in_progress = session_manager.find_sessions(status="IN_PROGRESS")
        completed = session_manager.find_sessions(status="COMPLETED")

        assert len(in_progress) == 1
        assert len(completed) == 1

    def test_find_sessions_combined_filters(
        self, session_manager: SessionManager, fixture_file: Path
    ):
        """Test finding sessions with both strategy and status filters."""
        s1 = session_manager.create_session("strategy_a", fixture_file, "0.3.4", "1.9.78")
        session_manager.create_session("strategy_a", fixture_file, "0.3.4", "1.9.78", force=True)
        session_manager.create_session("strategy_b", fixture_file, "0.3.4", "1.9.78")

        # Find IN_PROGRESS strategy_a sessions
        results = session_manager.find_sessions(strategy="strategy_a", status="IN_PROGRESS")

        assert len(results) == 1
        assert results[0].strategy_name == "strategy_a"
        assert results[0].status == "IN_PROGRESS"
