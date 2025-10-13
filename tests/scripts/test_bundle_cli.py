from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import polars as pl
import pytest
from click.testing import CliRunner

from rustybt.__main__ import main
from rustybt.assets.asset_db_schema import ASSET_DB_VERSION
from rustybt.data.bundles.metadata import BundleMetadata
from rustybt.data.polars.parquet_schema import DAILY_BARS_SCHEMA
from rustybt.data.polars.parquet_writer import ParquetWriter


@pytest.fixture(autouse=True)
def restore_bundle_metadata():
    original_path = BundleMetadata._db_path
    original_engine = BundleMetadata._engine
    yield
    BundleMetadata._db_path = original_path
    BundleMetadata._engine = original_engine


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def prepared_bundle(tmp_path, monkeypatch) -> str:
    zipline_root = tmp_path / ".zipline"
    bundles_dir = zipline_root / "data" / "bundles"
    bundles_dir.mkdir(parents=True)

    monkeypatch.setenv("ZIPLINE_ROOT", str(zipline_root))

    db_path = zipline_root / f"assets-{ASSET_DB_VERSION}.db"
    BundleMetadata.set_db_path(str(db_path))
    BundleMetadata._get_engine()

    bundle_name = "test-bundle"
    bundle_path = bundles_dir / bundle_name

    writer = ParquetWriter(str(bundle_path))

    df = pl.DataFrame(
        {
            "date": [date(2025, 1, 1), date(2025, 1, 2)],
            "sid": [1, 1],
            "open": [Decimal("100.00"), Decimal("101.00")],
            "high": [Decimal("101.00"), Decimal("102.00")],
            "low": [Decimal("99.00"), Decimal("100.00")],
            "close": [Decimal("100.50"), Decimal("101.50")],
            "volume": [Decimal("1000000"), Decimal("1100000")],
        }
    ).cast(DAILY_BARS_SCHEMA, strict=False)

    writer.write_daily_bars(
        df,
        bundle_name=bundle_name,
        source_metadata={
            "source_type": "yfinance",
            "source_url": "https://example.com",
            "api_version": "v8",
            "symbols": ["AAPL"],
        },
    )

    return bundle_name


def test_bundle_list_shows_bundle(runner: CliRunner, prepared_bundle: str):
    result = runner.invoke(main, ["bundle", "list"])
    assert result.exit_code == 0
    assert "Available Bundles" in result.output
    assert prepared_bundle in result.output


def test_bundle_info_displays_metadata(runner: CliRunner, prepared_bundle: str):
    result = runner.invoke(main, ["bundle", "info", prepared_bundle])
    assert result.exit_code == 0
    assert "Bundle:" in result.output
    assert "Source Type" in result.output
    assert "Symbols" in result.output


def test_bundle_validate_passes(runner: CliRunner, prepared_bundle: str):
    result = runner.invoke(main, ["bundle", "validate", prepared_bundle])
    assert result.exit_code == 0
    assert "Overall: PASSED" in result.output


def test_bundle_migrate_dry_run_invokes_script(monkeypatch, runner: CliRunner):
    calls: dict[str, tuple] = {}

    class StubStats:
        errors: list[str] = []

    stub = SimpleNamespace()
    stub.run_migration = (
        lambda dry_run, backup: calls.setdefault("run", (dry_run, backup)) or StubStats()
    )
    stub.validate_migration = lambda: calls.setdefault("validate", True) or True

    monkeypatch.setattr("rustybt.__main__._load_migration_module", lambda: stub)

    result = runner.invoke(main, ["bundle", "migrate", "--dry-run"])

    assert result.exit_code == 0
    assert calls["run"] == (True, True)
    assert "validate" not in calls  # not called during dry-run


def test_bundle_migrate_rollback_reads_manifest(monkeypatch, runner: CliRunner, tmp_path):
    backup_root = tmp_path / ".zipline" / "backups" / "catalog-backup-123"
    backup_root.mkdir(parents=True)
    manifest_path = backup_root / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "timestamp": 123,
                "datacatalog_checksum": "abc",
                "parquet_catalogs": {},
                "bundle_count": 0,
            }
        )
    )

    @dataclass
    class StubManifest:
        timestamp: int
        backup_path: Path
        datacatalog_checksum: str
        parquet_catalogs: dict[str, str]
        bundle_count: int

    called: dict[str, StubManifest] = {}

    stub = SimpleNamespace(
        json=json,
        BackupManifest=StubManifest,
        restore_from_backup=lambda manifest: called.setdefault("restore", manifest),
        validate_migration=lambda: True,
        run_migration=lambda **_: None,
    )

    monkeypatch.setattr("rustybt.__main__._load_migration_module", lambda: stub)
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    result = runner.invoke(main, ["bundle", "migrate", "--rollback", "123"])

    assert result.exit_code == 0
    assert "restore" in called
    assert called["restore"].backup_path == backup_root


def test_bundle_migrate_validate(monkeypatch, runner: CliRunner):
    stub = SimpleNamespace(validate_migration=lambda: True, run_migration=lambda **_: None)
    monkeypatch.setattr("rustybt.__main__._load_migration_module", lambda: stub)

    result = runner.invoke(main, ["bundle", "migrate", "--validate"])

    assert result.exit_code == 0
