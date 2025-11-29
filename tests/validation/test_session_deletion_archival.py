"""Tests for session deletion and archival functionality.

This module tests Story 3.5: Implement Session Deletion and Archival
- Session deletion
- Session archival to tar.gz
- Cleanup command with filters
- --dry-run support
"""

import tarfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from click.testing import CliRunner

from rustybt.validation.cli import main
from rustybt.validation.session import SessionManager


class TestSessionDeletion:
    """Test session deletion functionality."""

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

    def test_delete_session_removes_directory(
        self, session_manager: SessionManager, fixture_file: Path
    ):
        """Test deleting a session removes its directory."""
        session = session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78"
        )
        session_dir = session_manager.sessions_dir / session.id

        assert session_dir.exists()

        session_manager.delete_session(session.id)

        assert not session_dir.exists()

    def test_delete_session_nonexistent_raises_error(
        self, session_manager: SessionManager
    ):
        """Test deleting nonexistent session raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError) as exc_info:
            session_manager.delete_session("nonexistent-session")

        assert "Session not found" in str(exc_info.value)

    def test_delete_session_dry_run_preserves_files(
        self, session_manager: SessionManager, fixture_file: Path
    ):
        """Test --dry-run doesn't actually delete files."""
        session = session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78"
        )
        session_dir = session_manager.sessions_dir / session.id

        result = session_manager.delete_session(session.id, dry_run=True)

        assert result is True
        assert session_dir.exists()  # Directory still there

    def test_delete_session_removes_all_contents(
        self, session_manager: SessionManager, fixture_file: Path
    ):
        """Test deletion removes logs and analysis subdirectories."""
        session = session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78"
        )
        session_dir = session_manager.sessions_dir / session.id

        # Create some files in subdirectories
        (session_dir / "logs" / "test.log").touch()
        (session_dir / "analysis" / "report.json").touch()

        session_manager.delete_session(session.id)

        assert not session_dir.exists()
        assert not (session_dir / "logs").exists()
        assert not (session_dir / "analysis").exists()


class TestSessionArchival:
    """Test session archival functionality."""

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

    def test_archive_session_creates_tarball(
        self, session_manager: SessionManager, fixture_file: Path
    ):
        """Test archiving creates a gzipped tar archive."""
        session = session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78"
        )

        archive_path = session_manager.archive_session(session.id)

        assert archive_path is not None
        assert archive_path.exists()
        assert archive_path.suffix == ".gz"
        assert ".tar" in archive_path.name

    def test_archive_session_removes_original(
        self, session_manager: SessionManager, fixture_file: Path
    ):
        """Test archiving removes the original session directory."""
        session = session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78"
        )
        session_dir = session_manager.sessions_dir / session.id

        session_manager.archive_session(session.id)

        assert not session_dir.exists()

    def test_archive_session_in_default_location(
        self, session_manager: SessionManager, fixture_file: Path
    ):
        """Test archive is stored in default archive directory."""
        session = session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78"
        )

        archive_path = session_manager.archive_session(session.id)

        expected_dir = session_manager.sessions_dir / "archive"
        assert archive_path.parent == expected_dir

    def test_archive_session_contains_session_files(
        self, session_manager: SessionManager, fixture_file: Path
    ):
        """Test archive contains all session files."""
        session = session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78"
        )

        archive_path = session_manager.archive_session(session.id)

        # Verify archive contents
        with tarfile.open(archive_path, "r:gz") as tar:
            names = tar.getnames()
            # Should contain session directory with session.yaml
            assert any("session.yaml" in name for name in names)

    def test_archive_session_dry_run_preserves_files(
        self, session_manager: SessionManager, fixture_file: Path
    ):
        """Test --dry-run doesn't create archive or remove files."""
        session = session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78"
        )
        session_dir = session_manager.sessions_dir / session.id

        result = session_manager.archive_session(session.id, dry_run=True)

        assert result is None
        assert session_dir.exists()  # Original still there
        archive_dir = session_manager.sessions_dir / "archive"
        assert not archive_dir.exists() or not list(archive_dir.glob("*.tar.gz"))

    def test_archive_session_custom_directory(
        self, session_manager: SessionManager, fixture_file: Path, tmp_path: Path
    ):
        """Test archiving to custom directory."""
        session = session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78"
        )
        custom_archive_dir = tmp_path / "custom-archive"

        archive_path = session_manager.archive_session(
            session.id, archive_dir=custom_archive_dir
        )

        assert archive_path.parent == custom_archive_dir

    def test_archive_nonexistent_session_raises_error(
        self, session_manager: SessionManager
    ):
        """Test archiving nonexistent session raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError) as exc_info:
            session_manager.archive_session("nonexistent-session")

        assert "Session not found" in str(exc_info.value)


class TestSessionCleanup:
    """Test session cleanup functionality."""

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

    def test_cleanup_by_status(
        self, session_manager: SessionManager, fixture_file: Path
    ):
        """Test cleanup filters by status."""
        s1 = session_manager.create_session("strategy_a", fixture_file, "0.3.4", "1.9.78")
        s2 = session_manager.create_session("strategy_b", fixture_file, "0.3.4", "1.9.78")

        # Mark one as COMPLETED
        s1.status = "COMPLETED"
        session_manager.update_session(s1)

        cleaned = session_manager.cleanup_sessions(status="COMPLETED")

        assert len(cleaned) == 1
        assert s1.id in cleaned
        assert not (session_manager.sessions_dir / s1.id).exists()
        assert (session_manager.sessions_dir / s2.id).exists()

    def test_cleanup_by_age(
        self, session_manager: SessionManager, fixture_file: Path
    ):
        """Test cleanup filters by age."""
        # Create session
        session = session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78"
        )

        # Modify created_at to be 40 days ago
        session.created_at = datetime.now() - timedelta(days=40)
        session_manager.update_session(session)

        # Create recent session
        recent = session_manager.create_session(
            "recent_strategy", fixture_file, "0.3.4", "1.9.78"
        )

        # Cleanup sessions older than 30 days
        cleaned = session_manager.cleanup_sessions(older_than_days=30)

        assert len(cleaned) == 1
        assert session.id in cleaned
        assert not (session_manager.sessions_dir / session.id).exists()
        assert (session_manager.sessions_dir / recent.id).exists()

    def test_cleanup_dry_run_returns_would_be_affected(
        self, session_manager: SessionManager, fixture_file: Path
    ):
        """Test dry run returns list of sessions that would be cleaned."""
        session = session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78"
        )
        session.status = "COMPLETED"
        session_manager.update_session(session)

        cleaned = session_manager.cleanup_sessions(status="COMPLETED", dry_run=True)

        assert len(cleaned) == 1
        assert session.id in cleaned
        # Session should still exist
        assert (session_manager.sessions_dir / session.id).exists()

    def test_cleanup_with_archive(
        self, session_manager: SessionManager, fixture_file: Path
    ):
        """Test cleanup with archive flag creates archives."""
        session = session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78"
        )
        session.status = "COMPLETED"
        session_manager.update_session(session)

        cleaned = session_manager.cleanup_sessions(status="COMPLETED", archive=True)

        assert len(cleaned) == 1
        # Original should be gone
        assert not (session_manager.sessions_dir / session.id).exists()
        # Archive should exist
        archive_dir = session_manager.sessions_dir / "archive"
        assert (archive_dir / f"{session.id}.tar.gz").exists()

    def test_cleanup_returns_empty_when_no_matches(
        self, session_manager: SessionManager, fixture_file: Path
    ):
        """Test cleanup returns empty list when no sessions match."""
        session = session_manager.create_session(
            "test_strategy", fixture_file, "0.3.4", "1.9.78"
        )
        # Session is IN_PROGRESS

        cleaned = session_manager.cleanup_sessions(status="COMPLETED")

        assert len(cleaned) == 0
        # Session should still exist
        assert (session_manager.sessions_dir / session.id).exists()


class TestCLIDeleteCommand:
    """Test CLI delete command."""

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

    def test_cli_delete_with_confirmation(
        self, runner: CliRunner, tmp_path: Path, fixture_file: Path
    ):
        """Test CLI delete prompts for confirmation."""
        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Create session
            result1 = runner.invoke(main, [
                "session", "create",
                "--strategy", "test_strategy",
                "--data", str(fixture_file),
            ])
            assert result1.exit_code == 0
            # Extract session ID from output
            session_id = result1.output.split("Session created: ")[1].split("\n")[0]

            # Delete with confirmation
            result2 = runner.invoke(main, [
                "session", "delete", session_id, "--yes"
            ])

            assert result2.exit_code == 0
            assert "Session deleted" in result2.output

    def test_cli_delete_dry_run(
        self, runner: CliRunner, tmp_path: Path, fixture_file: Path
    ):
        """Test CLI delete --dry-run shows preview."""
        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Create session
            result1 = runner.invoke(main, [
                "session", "create",
                "--strategy", "test_strategy",
                "--data", str(fixture_file),
            ])
            session_id = result1.output.split("Session created: ")[1].split("\n")[0]

            # Delete with dry-run
            result2 = runner.invoke(main, [
                "session", "delete", session_id, "--dry-run"
            ])

            assert result2.exit_code == 0
            assert "Would delete session" in result2.output
            assert "dry run" in result2.output

    def test_cli_delete_nonexistent_session(self, runner: CliRunner, tmp_path: Path):
        """Test CLI delete shows error for nonexistent session."""
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(main, [
                "session", "delete", "nonexistent-session", "--yes"
            ])

            assert result.exit_code == 1
            assert "Session not found" in result.output


class TestCLIArchiveCommand:
    """Test CLI archive command."""

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

    def test_cli_archive_creates_tarball(
        self, runner: CliRunner, tmp_path: Path, fixture_file: Path
    ):
        """Test CLI archive creates archive file."""
        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Create session
            result1 = runner.invoke(main, [
                "session", "create",
                "--strategy", "test_strategy",
                "--data", str(fixture_file),
            ])
            session_id = result1.output.split("Session created: ")[1].split("\n")[0]

            # Archive
            result2 = runner.invoke(main, ["session", "archive", session_id])

            assert result2.exit_code == 0
            assert "Session archived" in result2.output
            assert ".tar.gz" in result2.output

    def test_cli_archive_dry_run(
        self, runner: CliRunner, tmp_path: Path, fixture_file: Path
    ):
        """Test CLI archive --dry-run shows preview."""
        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Create session
            result1 = runner.invoke(main, [
                "session", "create",
                "--strategy", "test_strategy",
                "--data", str(fixture_file),
            ])
            session_id = result1.output.split("Session created: ")[1].split("\n")[0]

            # Archive with dry-run
            result2 = runner.invoke(main, [
                "session", "archive", session_id, "--dry-run"
            ])

            assert result2.exit_code == 0
            assert "Would archive session" in result2.output
            assert "dry run" in result2.output


class TestCLICleanupCommand:
    """Test CLI cleanup command."""

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

    def test_cli_cleanup_dry_run(
        self, runner: CliRunner, tmp_path: Path, fixture_file: Path
    ):
        """Test CLI cleanup --dry-run shows preview."""
        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Create and complete session
            result1 = runner.invoke(main, [
                "session", "create",
                "--strategy", "test_strategy",
                "--data", str(fixture_file),
            ])
            assert result1.exit_code == 0

            # Run cleanup dry-run (all sessions, no status filter)
            result2 = runner.invoke(main, [
                "session", "cleanup", "--dry-run"
            ])

            assert result2.exit_code == 0
            assert "Sessions to delete" in result2.output
            assert "dry run" in result2.output

    def test_cli_cleanup_no_matches(
        self, runner: CliRunner, tmp_path: Path, fixture_file: Path
    ):
        """Test CLI cleanup shows message when no sessions match."""
        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Create session (IN_PROGRESS)
            runner.invoke(main, [
                "session", "create",
                "--strategy", "test_strategy",
                "--data", str(fixture_file),
            ])

            # Cleanup COMPLETED (none exist)
            result = runner.invoke(main, [
                "session", "cleanup", "--status", "COMPLETED", "--dry-run"
            ])

            assert result.exit_code == 0
            assert "No sessions match" in result.output
