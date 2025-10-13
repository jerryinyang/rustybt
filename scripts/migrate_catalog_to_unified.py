#!/usr/bin/env python3
"""
Migration Script: DataCatalog + ParquetMetadataCatalog → BundleMetadata

Safely merges two separate catalog systems into unified BundleMetadata schema.

Features:
- Dry-run mode (preview changes without committing)
- Automatic backup before migration
- Transactional integrity (all-or-nothing)
- Rollback capability
- Validation checkpoints
- Progress tracking

Usage:
    # Preview migration
    python scripts/migrate_catalog_to_unified.py --dry-run

    # Execute migration with backup
    python scripts/migrate_catalog_to_unified.py --backup

    # Rollback to backup
    python scripts/migrate_catalog_to_unified.py --rollback <timestamp>

    # Validate existing migration
    python scripts/migrate_catalog_to_unified.py --validate
"""

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Adjust import paths as needed
from rustybt.data.bundles.metadata import BundleMetadata
from rustybt.data.catalog import DataCatalog
from rustybt.data.polars.metadata_catalog import ParquetMetadataCatalog

console = Console()


@dataclass
class MigrationStats:
    """Track migration progress and results."""

    bundles_migrated: int = 0
    symbols_migrated: int = 0
    cache_entries_migrated: int = 0
    quality_records_migrated: int = 0
    errors: list[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


@dataclass
class BackupManifest:
    """Metadata for backup archives."""

    timestamp: int
    backup_path: Path
    datacatalog_checksum: str
    parquet_catalogs: dict[str, str]  # bundle_name → checksum
    bundle_count: int


class MigrationTransaction:
    """Transactional wrapper for SQLite migrations."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn: sqlite3.Connection | None = None
        self.savepoint_stack: list[str] = []

    def __enter__(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("BEGIN IMMEDIATE")  # Acquire exclusive lock
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.conn.commit()
            console.print("[green]✓ Transaction committed[/green]")
        else:
            self.conn.rollback()
            console.print(f"[red]✗ Transaction rolled back: {exc_val}[/red]")

        self.conn.close()

    def savepoint(self, name: str):
        """Create a named savepoint for partial rollback."""
        self.conn.execute(f"SAVEPOINT {name}")
        self.savepoint_stack.append(name)

    def rollback_to_savepoint(self, name: str):
        """Rollback to a specific savepoint."""
        self.conn.execute(f"ROLLBACK TO SAVEPOINT {name}")
        # Remove savepoints after this one
        while self.savepoint_stack and self.savepoint_stack[-1] != name:
            self.savepoint_stack.pop()

    def execute(self, sql: str, params=None):
        """Execute SQL with optional parameters."""
        if params:
            return self.conn.execute(sql, params)
        return self.conn.execute(sql)


def calculate_checksum(file_path: Path) -> str:
    """Calculate SHA256 checksum of file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def create_backup(backup_dir: Path) -> BackupManifest:
    """Create backup of existing catalogs before migration."""
    timestamp = int(time.time())
    backup_path = backup_dir / f"catalog-backup-{timestamp}"
    backup_path.mkdir(parents=True, exist_ok=True)

    console.print(f"\n[cyan]Creating backup at {backup_path}...[/cyan]")

    # Backup DataCatalog (global)
    datacatalog_db = Path.home() / ".zipline" / "data" / "catalog.db"
    if datacatalog_db.exists():
        backup_datacatalog = backup_path / "datacatalog.db"
        shutil.copy2(datacatalog_db, backup_datacatalog)
        datacatalog_checksum = calculate_checksum(backup_datacatalog)
        console.print(f"  [green]✓[/green] DataCatalog backed up ({datacatalog_checksum[:8]}...)")
    else:
        datacatalog_checksum = ""
        console.print("  [yellow]⚠[/yellow] DataCatalog not found (skipped)")

    # Backup ParquetMetadataCatalog (per-bundle)
    parquet_catalogs = {}
    bundles_dir = Path.home() / ".zipline" / "data"

    if bundles_dir.exists():
        for bundle_dir in bundles_dir.iterdir():
            if not bundle_dir.is_dir():
                continue

            metadata_db = bundle_dir / "metadata.db"
            if metadata_db.exists():
                backup_metadata = backup_path / f"{bundle_dir.name}-metadata.db"
                shutil.copy2(metadata_db, backup_metadata)
                checksum = calculate_checksum(backup_metadata)
                parquet_catalogs[bundle_dir.name] = checksum
                console.print(f"  [green]✓[/green] {bundle_dir.name}/metadata.db backed up")

    # Create manifest
    manifest = BackupManifest(
        timestamp=timestamp,
        backup_path=backup_path,
        datacatalog_checksum=datacatalog_checksum,
        parquet_catalogs=parquet_catalogs,
        bundle_count=len(parquet_catalogs),
    )

    # Write manifest JSON
    manifest_file = backup_path / "manifest.json"
    with open(manifest_file, "w") as f:
        json.dump(
            {
                "timestamp": manifest.timestamp,
                "datacatalog_checksum": manifest.datacatalog_checksum,
                "parquet_catalogs": manifest.parquet_catalogs,
                "bundle_count": manifest.bundle_count,
            },
            f,
            indent=2,
        )

    console.print(f"[green]✓ Backup complete: {len(parquet_catalogs)} bundles backed up[/green]\n")
    return manifest


def restore_from_backup(manifest: BackupManifest):
    """Restore catalogs from backup."""
    console.print(f"\n[cyan]Restoring from backup {manifest.timestamp}...[/cyan]")

    # Restore DataCatalog
    if manifest.datacatalog_checksum:
        backup_datacatalog = manifest.backup_path / "datacatalog.db"
        datacatalog_db = Path.home() / ".zipline" / "data" / "catalog.db"

        if backup_datacatalog.exists():
            shutil.copy2(backup_datacatalog, datacatalog_db)
            console.print("  [green]✓[/green] DataCatalog restored")
        else:
            console.print("  [red]✗[/red] Backup DataCatalog not found!")

    # Restore ParquetMetadataCatalog
    bundles_dir = Path.home() / ".zipline" / "data"

    for bundle_name, checksum in manifest.parquet_catalogs.items():
        backup_metadata = manifest.backup_path / f"{bundle_name}-metadata.db"
        metadata_db = bundles_dir / bundle_name / "metadata.db"

        if backup_metadata.exists():
            metadata_db.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup_metadata, metadata_db)
            console.print(f"  [green]✓[/green] {bundle_name}/metadata.db restored")
        else:
            console.print(f"  [red]✗[/red] Backup for {bundle_name} not found!")

    console.print("[green]✓ Rollback complete[/green]\n")


def validate_migration() -> bool:
    """Validate migration integrity by comparing row counts."""
    console.print("\n[cyan]Validating migration...[/cyan]")

    # Compare bundle counts
    datacatalog = DataCatalog()
    old_bundle_count = len(datacatalog.list_bundles())
    new_bundle_count = BundleMetadata.count_bundles()

    if old_bundle_count != new_bundle_count:
        console.print(
            f"[red]✗ Bundle count mismatch: "
            f"DataCatalog={old_bundle_count}, BundleMetadata={new_bundle_count}[/red]"
        )
        return False

    console.print(f"  [green]✓[/green] Bundle count matches: {new_bundle_count}")

    # Compare quality metrics counts
    old_quality_count = datacatalog.count_quality_metrics()
    new_quality_count = BundleMetadata.count_quality_records()

    if old_quality_count != new_quality_count:
        console.print(
            f"[red]✗ Quality record mismatch: "
            f"DataCatalog={old_quality_count}, BundleMetadata={new_quality_count}[/red]"
        )
        return False

    console.print(f"  [green]✓[/green] Quality records match: {new_quality_count}")

    # Compare symbols
    bundles_dir = Path.home() / ".zipline" / "data"
    total_old_symbols = 0
    total_new_symbols = 0

    for bundle_dir in bundles_dir.iterdir():
        if not bundle_dir.is_dir():
            continue

        metadata_db = bundle_dir / "metadata.db"
        if metadata_db.exists():
            parquet_catalog = ParquetMetadataCatalog(str(metadata_db))
            old_symbols = len(parquet_catalog.get_all_symbols())
            total_old_symbols += old_symbols

            new_symbols = BundleMetadata.count_symbols(bundle_dir.name)
            total_new_symbols += new_symbols

    if total_old_symbols != total_new_symbols:
        console.print(
            f"[red]✗ Symbol count mismatch: "
            f"ParquetCatalog={total_old_symbols}, BundleMetadata={total_new_symbols}[/red]"
        )
        return False

    console.print(f"  [green]✓[/green] Symbol counts match: {total_new_symbols}")

    console.print("[green]✓ Validation passed[/green]\n")
    return True


def migrate_datacatalog(txn: MigrationTransaction, stats: MigrationStats):
    """Migrate DataCatalog → BundleMetadata (provenance + quality)."""
    datacatalog = DataCatalog()
    bundles = datacatalog.list_bundles()

    txn.savepoint("datacatalog_start")

    for bundle in bundles:
        try:
            # Migrate provenance
            now = int(time.time())
            checksum_value = bundle.get("checksum", "migrated")
            txn.execute(
                """
                INSERT OR REPLACE INTO bundle_metadata
                (
                    bundle_name,
                    source_type,
                    source_url,
                    api_version,
                    fetch_timestamp,
                    data_version,
                    checksum,
                    file_checksum,
                    file_size_bytes,
                    timezone,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    bundle["bundle_name"],
                    bundle.get("source_type"),
                    bundle.get("source_url"),
                    bundle.get("api_version"),
                    bundle.get("fetch_timestamp"),
                    bundle.get("data_version"),
                    checksum_value,
                    checksum_value,
                    None,
                    bundle.get("timezone", "UTC"),
                    now,
                    now,
                ),
            )

            # Migrate quality metrics
            quality = datacatalog.get_quality_metrics(bundle["bundle_name"])
            if quality:
                missing_days_list = quality.get("missing_days_list")
                if isinstance(missing_days_list, list):
                    missing_days_list = json.dumps(missing_days_list)
                if missing_days_list is None:
                    missing_days_list = "[]"

                missing_days_count = quality.get("missing_days_count")
                if missing_days_count is None:
                    missing_days_count = 0

                outlier_count = quality.get("outlier_count")
                if outlier_count is None:
                    outlier_count = 0

                ohlcv_violations = quality.get("ohlcv_violations")
                if ohlcv_violations is None:
                    ohlcv_violations = 0

                validation_passed = quality.get("validation_passed")
                if validation_passed is None:
                    validation_passed = True

                txn.execute(
                    """
                    UPDATE bundle_metadata
                    SET row_count = ?,
                        start_date = ?,
                        end_date = ?,
                        missing_days_count = ?,
                        missing_days_list = ?,
                        outlier_count = ?,
                        ohlcv_violations = ?,
                        validation_passed = ?,
                        validation_timestamp = ?
                    WHERE bundle_name = ?
                """,
                    (
                        quality.get("row_count"),
                        quality.get("start_date"),
                        quality.get("end_date"),
                        missing_days_count,
                        missing_days_list,
                        outlier_count,
                        ohlcv_violations,
                        validation_passed,
                        quality.get("validation_timestamp"),
                        bundle["bundle_name"],
                    ),
                )
                stats.quality_records_migrated += 1

            stats.bundles_migrated += 1

        except Exception as e:
            stats.errors.append(f"DataCatalog migration failed for {bundle['bundle_name']}: {e}")
            txn.rollback_to_savepoint("datacatalog_start")
            raise


def migrate_parquet_catalogs(txn: MigrationTransaction, stats: MigrationStats):
    """Migrate ParquetMetadataCatalog → BundleMetadata (symbols + cache)."""
    bundles_dir = Path.home() / ".zipline" / "data"

    for bundle_dir in bundles_dir.iterdir():
        if not bundle_dir.is_dir():
            continue

        metadata_db = bundle_dir / "metadata.db"
        if not metadata_db.exists():
            continue

        bundle_name = bundle_dir.name
        txn.savepoint(f"parquet_{bundle_name}")

        try:
            parquet_catalog = ParquetMetadataCatalog(str(metadata_db))

            # Migrate symbols
            symbols = parquet_catalog.get_all_symbols()
            for symbol in symbols:
                txn.execute(
                    """
                    INSERT OR IGNORE INTO bundle_symbols
                    (bundle_name, symbol, asset_type, exchange)
                    VALUES (?, ?, ?, ?)
                """,
                    (
                        bundle_name,
                        symbol["symbol"],
                        symbol.get("asset_type"),
                        symbol.get("exchange"),
                    ),
                )
                stats.symbols_migrated += 1

            # Migrate cache entries
            cache_entries = parquet_catalog.get_cache_entries()
            for entry in cache_entries:
                # bundle_cache uses bundle_path not parquet_path in unified schema
                txn.execute(
                    """
                    INSERT OR IGNORE INTO bundle_cache
                    (cache_key, bundle_name, bundle_path, fetch_timestamp, size_bytes, last_accessed)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        entry["cache_key"],
                        bundle_name,
                        entry["parquet_path"],
                        entry.get("created_at", int(time.time())),
                        entry.get("size_bytes", 0),
                        entry.get("last_accessed", int(time.time())),
                    ),
                )
                stats.cache_entries_migrated += 1

        except Exception as e:
            stats.errors.append(f"ParquetCatalog migration failed for {bundle_name}: {e}")
            txn.rollback_to_savepoint(f"parquet_{bundle_name}")
            # Don't raise - continue with other bundles
            continue


def run_migration(dry_run: bool = False, backup: bool = True) -> MigrationStats:
    """Execute migration with transactional safety."""
    stats = MigrationStats()

    # Create backup
    backup_manifest = None
    if backup and not dry_run:
        backup_dir = Path.home() / ".zipline" / "backups"
        backup_manifest = create_backup(backup_dir)

    # Migration transaction
    unified_metadata_db = Path.home() / ".zipline" / "data" / "bundle_metadata.db"

    try:
        with MigrationTransaction(unified_metadata_db) as txn:
            console.print("[cyan]Starting migration...[/cyan]\n")

            # Phase 1: DataCatalog
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Migrating DataCatalog...", total=None)
                migrate_datacatalog(txn, stats)
                progress.update(task, completed=True)

            # Phase 2: ParquetMetadataCatalog
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Migrating ParquetMetadataCatalogs...", total=None)
                migrate_parquet_catalogs(txn, stats)
                progress.update(task, completed=True)

            if dry_run:
                console.print(
                    "\n[yellow]DRY RUN: Rolling back transaction (no changes saved)[/yellow]"
                )
                raise RuntimeError("Dry run - rollback intentional")

    except Exception as e:
        if not dry_run:
            console.print(f"\n[red]✗ Migration failed: {e}[/red]")

            # Restore from backup if available
            if backup_manifest:
                restore_from_backup(backup_manifest)

        if dry_run:
            console.print("\n[green]Dry run completed (preview only)[/green]")

    # Summary
    print_migration_summary(stats, dry_run)

    return stats


def print_migration_summary(stats: MigrationStats, dry_run: bool = False):
    """Print migration results table."""
    table = Table(title="Migration Summary" if not dry_run else "Migration Preview (Dry Run)")

    table.add_column("Metric", style="cyan")
    table.add_column("Count", justify="right", style="green")

    table.add_row("Bundles Migrated", str(stats.bundles_migrated))
    table.add_row("Symbols Migrated", str(stats.symbols_migrated))
    table.add_row("Cache Entries Migrated", str(stats.cache_entries_migrated))
    table.add_row("Quality Records Migrated", str(stats.quality_records_migrated))

    if stats.errors:
        table.add_row("Errors", str(len(stats.errors)), style="red")

    console.print("\n")
    console.print(table)

    if stats.errors:
        console.print("\n[red]Errors:[/red]")
        for error in stats.errors:
            console.print(f"  - {error}")


def main():
    parser = argparse.ArgumentParser(description="Migrate catalogs to unified BundleMetadata")
    parser.add_argument("--dry-run", action="store_true", help="Preview migration without saving")
    parser.add_argument(
        "--backup", action="store_true", default=True, help="Create backup before migration"
    )
    parser.add_argument("--no-backup", action="store_true", help="Skip backup (dangerous!)")
    parser.add_argument(
        "--rollback", type=int, metavar="TIMESTAMP", help="Rollback to backup timestamp"
    )
    parser.add_argument("--validate", action="store_true", help="Validate existing migration")

    args = parser.parse_args()

    # Rollback mode
    if args.rollback:
        backup_dir = Path.home() / ".zipline" / "backups"
        backup_path = backup_dir / f"catalog-backup-{args.rollback}"

        if not backup_path.exists():
            console.print(f"[red]✗ Backup not found: {backup_path}[/red]")
            sys.exit(1)

        manifest_file = backup_path / "manifest.json"
        with open(manifest_file) as f:
            manifest_data = json.load(f)

        manifest = BackupManifest(
            timestamp=manifest_data["timestamp"],
            backup_path=backup_path,
            datacatalog_checksum=manifest_data["datacatalog_checksum"],
            parquet_catalogs=manifest_data["parquet_catalogs"],
            bundle_count=manifest_data["bundle_count"],
        )

        restore_from_backup(manifest)
        sys.exit(0)

    # Validate mode
    if args.validate:
        if validate_migration():
            sys.exit(0)
        else:
            sys.exit(1)

    # Migration mode
    backup = args.backup and not args.no_backup
    stats = run_migration(dry_run=args.dry_run, backup=backup)

    # Validate after migration
    if not args.dry_run and not stats.errors:
        validate_migration()


if __name__ == "__main__":
    main()
