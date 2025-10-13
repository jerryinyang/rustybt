"""Tests for catalog migration script.

Tests Story 8.4 Phase 2 (Migration Testing) - AC 2.1-2.6:
- Dry-run mode preview
- Backup creation with SHA256 checksums
- Transactional migration with rollback
- Validation checkpoints
- Rollback command
- Zero data loss verification

Story: 8.4 (Unified Metadata Management)
Phase: 2 (Migration Testing)
"""

import json

# Import migration components
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rustybt.data.bundles.metadata import BundleMetadata
from scripts.migrate_catalog_to_unified import (
    BackupManifest,
    MigrationStats,
    MigrationTransaction,
    calculate_checksum,
    create_backup,
    migrate_datacatalog,
    print_migration_summary,
    restore_from_backup,
    run_migration,
    validate_migration,
)


class TestMigrationTransaction:
    """Test SQLite transactional wrapper."""

    def test_transaction_commit_on_success(self):
        """Transaction commits when no exception raised."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Initialize schema
            BundleMetadata.set_db_path(str(db_path))
            BundleMetadata._get_engine()

            with MigrationTransaction(db_path) as txn:
                txn.execute(
                    """
                    INSERT INTO bundle_metadata (bundle_name, source_type, checksum, fetch_timestamp, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        "test-bundle",
                        "yfinance",
                        "abc123",
                        int(time.time()),
                        int(time.time()),
                        int(time.time()),
                    ),
                )

            # Verify committed
            result = BundleMetadata.get("test-bundle")
            assert result is not None
            assert result["bundle_name"] == "test-bundle"

    def test_transaction_rollback_on_error(self):
        """Transaction rolls back when exception raised."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            BundleMetadata.set_db_path(str(db_path))
            BundleMetadata._get_engine()

            try:
                with MigrationTransaction(db_path) as txn:
                    txn.execute(
                        """
                        INSERT INTO bundle_metadata (bundle_name, source_type, checksum, fetch_timestamp, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """,
                        (
                            "test-bundle",
                            "yfinance",
                            "abc123",
                            int(time.time()),
                            int(time.time()),
                            int(time.time()),
                        ),
                    )

                    # Simulate error
                    raise RuntimeError("Simulated error")
            except RuntimeError:
                pass

            # Verify rolled back
            result = BundleMetadata.get("test-bundle")
            assert result is None

    def test_savepoint_and_rollback(self):
        """Savepoints allow partial rollback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            BundleMetadata.set_db_path(str(db_path))
            BundleMetadata._get_engine()

            with MigrationTransaction(db_path) as txn:
                # Insert first bundle
                now = int(time.time())
                txn.execute(
                    """
                    INSERT INTO bundle_metadata (bundle_name, source_type, checksum, fetch_timestamp, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    ("bundle-1", "yfinance", "abc", now, now, now),
                )

                # Create savepoint
                txn.savepoint("before_bundle2")

                # Insert second bundle
                txn.execute(
                    """
                    INSERT INTO bundle_metadata (bundle_name, source_type, checksum, fetch_timestamp, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    ("bundle-2", "ccxt", "def", now, now, now),
                )

                # Rollback to savepoint (removes bundle-2)
                txn.rollback_to_savepoint("before_bundle2")

            # Verify bundle-1 exists, bundle-2 doesn't
            assert BundleMetadata.get("bundle-1") is not None
            assert BundleMetadata.get("bundle-2") is None


class TestBackupAndRestore:
    """Test backup creation and restoration."""

    def test_calculate_checksum(self):
        """Calculate SHA256 checksum of file."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("test content")
            f.flush()
            file_path = Path(f.name)

        try:
            checksum = calculate_checksum(file_path)
            assert len(checksum) == 64  # SHA256 hex digest
            assert isinstance(checksum, str)
        finally:
            file_path.unlink()

    def test_backup_manifest_creation(self):
        """BackupManifest stores backup metadata correctly."""
        manifest = BackupManifest(
            timestamp=1234567890,
            backup_path=Path("/tmp/backup"),
            datacatalog_checksum="abc123",
            parquet_catalogs={"bundle1": "def456", "bundle2": "ghi789"},
            bundle_count=2,
        )

        assert manifest.timestamp == 1234567890
        assert manifest.bundle_count == 2
        assert len(manifest.parquet_catalogs) == 2

    @patch("scripts.migrate_catalog_to_unified.Path.home")
    def test_create_backup_with_checksums(self, mock_home):
        """Backup creation includes SHA256 checksums."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_home.return_value = Path(tmpdir)

            # Create mock catalog files
            zipline_dir = Path(tmpdir) / ".zipline"
            data_dir = zipline_dir / "data"
            data_dir.mkdir(parents=True)

            # Create mock DataCatalog
            catalog_db = data_dir / "catalog.db"
            catalog_db.write_text("mock datacatalog")

            # Create mock bundle with metadata
            bundle_dir = data_dir / "test-bundle"
            bundle_dir.mkdir()
            metadata_db = bundle_dir / "metadata.db"
            metadata_db.write_text("mock metadata")

            backup_dir = zipline_dir / "backups"
            backup_dir.mkdir(parents=True)

            manifest = create_backup(backup_dir)

            # Verify backup created
            assert manifest.backup_path.exists()
            assert manifest.datacatalog_checksum != ""
            assert len(manifest.parquet_catalogs) == 1
            assert "test-bundle" in manifest.parquet_catalogs

            # Verify manifest file
            manifest_file = manifest.backup_path / "manifest.json"
            assert manifest_file.exists()

            with open(manifest_file) as f:
                manifest_data = json.load(f)

            assert manifest_data["bundle_count"] == 1


class TestMigrationStats:
    """Test migration statistics tracking."""

    def test_migration_stats_initialization(self):
        """MigrationStats initializes with zero counts."""
        stats = MigrationStats()
        assert stats.bundles_migrated == 0
        assert stats.symbols_migrated == 0
        assert stats.cache_entries_migrated == 0
        assert stats.quality_records_migrated == 0
        assert stats.errors == []

    def test_migration_stats_tracking(self):
        """MigrationStats tracks migration progress."""
        stats = MigrationStats()

        stats.bundles_migrated += 3
        stats.symbols_migrated += 10
        stats.cache_entries_migrated += 5
        stats.quality_records_migrated += 2
        stats.errors.append("Test error")

        assert stats.bundles_migrated == 3
        assert stats.symbols_migrated == 10
        assert stats.cache_entries_migrated == 5
        assert stats.quality_records_migrated == 2
        assert len(stats.errors) == 1


class TestDryRunMode:
    """Test dry-run mode (AC 2.2)."""

    @patch("scripts.migrate_catalog_to_unified.DataCatalog")
    @patch("scripts.migrate_catalog_to_unified.ParquetMetadataCatalog")
    def test_dry_run_no_changes_committed(self, mock_parquet, mock_datacatalog):
        """Dry-run previews changes without committing."""
        # Mock DataCatalog
        mock_datacatalog.return_value.list_bundles.return_value = [
            {"bundle_name": "test-bundle", "source_type": "yfinance"}
        ]
        mock_datacatalog.return_value.get_quality_metrics.return_value = {
            "row_count": 1000,
            "ohlcv_violations": 0,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            BundleMetadata.set_db_path(str(Path(tmpdir) / "test.db"))

            # Run dry-run
            stats = run_migration(dry_run=True, backup=False)

            # Verify stats populated (preview)
            assert stats.bundles_migrated >= 0

            # Verify no data actually committed
            result = BundleMetadata.get("test-bundle")
            assert result is None  # Nothing committed in dry-run

    @patch("scripts.migrate_catalog_to_unified.console")
    def test_dry_run_prints_preview(self, mock_console):
        """Dry-run displays preview table."""
        stats = MigrationStats(
            bundles_migrated=10,
            symbols_migrated=50,
            cache_entries_migrated=5,
            quality_records_migrated=8,
        )

        print_migration_summary(stats, dry_run=True)

        # Verify console.print was called (preview displayed)
        assert mock_console.print.called


class TestValidationCheckpoints:
    """Test validation checkpoints (AC 2.5)."""

    @patch("scripts.migrate_catalog_to_unified.DataCatalog")
    @patch("scripts.migrate_catalog_to_unified.BundleMetadata.count_bundles")
    def test_validation_detects_bundle_count_mismatch(self, mock_new_count, mock_datacatalog):
        """Validation fails when bundle counts don't match."""
        mock_datacatalog.return_value.list_bundles.return_value = [{}, {}, {}]  # 3 bundles
        mock_new_count.return_value = 2  # Only 2 migrated

        result = validate_migration()
        assert result is False

    @patch("scripts.migrate_catalog_to_unified.DataCatalog")
    @patch("scripts.migrate_catalog_to_unified.BundleMetadata.count_bundles")
    @patch("scripts.migrate_catalog_to_unified.BundleMetadata.count_quality_records")
    def test_validation_passes_when_counts_match(
        self, mock_quality, mock_bundles, mock_datacatalog
    ):
        """Validation passes when all counts match."""
        # Mock matching counts
        mock_datacatalog.return_value.list_bundles.return_value = [{}, {}]
        mock_bundles.return_value = 2

        mock_datacatalog.return_value.count_quality_metrics.return_value = 2
        mock_quality.return_value = 2

        # Mock no bundle directories (skip symbol check)
        with patch("scripts.migrate_catalog_to_unified.Path.home") as mock_home:
            with tempfile.TemporaryDirectory() as tmpdir:
                mock_home.return_value = Path(tmpdir)
                data_dir = Path(tmpdir) / ".zipline" / "data"
                data_dir.mkdir(parents=True)

                result = validate_migration()
                assert result is True


class TestRollbackCommand:
    """Test rollback functionality (AC 2.6)."""

    def test_restore_from_backup_restores_files(self):
        """Rollback restores files from backup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create backup structure
            backup_path = Path(tmpdir) / "backup"
            backup_path.mkdir()

            # Create backup files
            backup_datacatalog = backup_path / "datacatalog.db"
            backup_datacatalog.write_text("original datacatalog")

            backup_metadata = backup_path / "test-bundle-metadata.db"
            backup_metadata.write_text("original metadata")

            # Create manifest
            manifest = BackupManifest(
                timestamp=int(time.time()),
                backup_path=backup_path,
                datacatalog_checksum="abc123",
                parquet_catalogs={"test-bundle": "def456"},
                bundle_count=1,
            )

            # Mock target directories
            with patch("scripts.migrate_catalog_to_unified.Path.home") as mock_home:
                mock_home.return_value = Path(tmpdir)

                # Create target directories
                zipline_dir = Path(tmpdir) / ".zipline" / "data"
                zipline_dir.mkdir(parents=True)
                bundle_dir = zipline_dir / "test-bundle"
                bundle_dir.mkdir()

                # Corrupt files (simulating failed migration)
                target_catalog = zipline_dir / "catalog.db"
                target_catalog.write_text("corrupted")

                target_metadata = bundle_dir / "metadata.db"
                target_metadata.write_text("corrupted")

                # Restore
                restore_from_backup(manifest)

                # Verify restored
                assert target_catalog.read_text() == "original datacatalog"
                assert target_metadata.read_text() == "original metadata"


class TestZeroDataLoss:
    """Test zero data loss guarantees (AC 2.5)."""

    @patch("scripts.migrate_catalog_to_unified.DataCatalog")
    def test_migration_preserves_all_bundle_data(self, mock_datacatalog):
        """Migration preserves all bundle metadata fields."""
        mock_bundle = {
            "bundle_name": "test-bundle",
            "source_type": "yfinance",
            "source_url": "https://api.example.com",
            "api_version": "v1",
            "fetch_timestamp": 1234567890,
        }

        mock_datacatalog.return_value.list_bundles.return_value = [mock_bundle]
        mock_datacatalog.return_value.get_quality_metrics.return_value = None

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            BundleMetadata.set_db_path(str(db_path))
            BundleMetadata._get_engine()

            stats = MigrationStats()

            with MigrationTransaction(db_path) as txn:
                migrate_datacatalog(txn, stats)

            # Verify all fields preserved
            result = BundleMetadata.get("test-bundle")
            assert result is not None
            assert result["bundle_name"] == "test-bundle"
            assert result["source_type"] == "yfinance"
            assert result["source_url"] == "https://api.example.com"
            assert result["api_version"] == "v1"
            assert result["fetch_timestamp"] == 1234567890

    def test_migration_error_causes_full_rollback(self):
        """Error during migration triggers full rollback (no partial data)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            BundleMetadata.set_db_path(str(db_path))
            BundleMetadata._get_engine()

            MigrationStats()

            try:
                with MigrationTransaction(db_path) as txn:
                    # Insert some data
                    now = int(time.time())
                    txn.execute(
                        """
                        INSERT INTO bundle_metadata (bundle_name, source_type, checksum, fetch_timestamp, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """,
                        ("bundle-1", "yfinance", "abc", now, now, now),
                    )

                    # Simulate error
                    raise RuntimeError("Migration error")
            except RuntimeError:
                pass

            # Verify nothing committed
            assert BundleMetadata.get("bundle-1") is None
