#!/usr/bin/env python3
"""Recover main assets database from per-bundle metadata.db files."""

import os
import shutil
import sqlite3
import tempfile
import time
from pathlib import Path


def recover_metadata():
    """Rebuild assets-{version}.db from per-bundle metadata.db files."""
    # Use constants directly to avoid importing rustybt modules that may cache engine
    ASSET_DB_VERSION = 10
    root = Path(os.path.expanduser("~/.zipline"))
    bundles_dir = root / "data" / "bundles"
    main_db_path = root / f"assets-{ASSET_DB_VERSION}.db"

    # Create database in temp location first
    temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    temp_db_path = temp_db.name
    temp_db.close()

    print(f"Creating database in temp location: {temp_db_path}")

    # Create schema manually to avoid rustybt import side effects
    conn = sqlite3.connect(temp_db_path)
    cur = conn.cursor()

    # Create all required tables
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS exchanges (
            exchange TEXT NOT NULL PRIMARY KEY,
            canonical_name TEXT NOT NULL,
            country_code TEXT NOT NULL,
            UNIQUE (exchange)
        );

        CREATE TABLE IF NOT EXISTS equities (
            sid INTEGER NOT NULL PRIMARY KEY,
            asset_name TEXT,
            start_date INTEGER DEFAULT 0 NOT NULL,
            end_date INTEGER NOT NULL,
            first_traded INTEGER,
            auto_close_date INTEGER,
            exchange TEXT REFERENCES exchanges(exchange),
            UNIQUE (sid)
        );

        CREATE TABLE IF NOT EXISTS equity_symbol_mappings (
            id INTEGER NOT NULL PRIMARY KEY,
            sid INTEGER NOT NULL REFERENCES equities(sid),
            symbol TEXT NOT NULL,
            company_symbol TEXT,
            share_class_symbol TEXT,
            start_date INTEGER NOT NULL,
            end_date INTEGER NOT NULL,
            UNIQUE (id)
        );
        CREATE INDEX IF NOT EXISTS idx_esm_sid ON equity_symbol_mappings(sid);
        CREATE INDEX IF NOT EXISTS idx_esm_company ON equity_symbol_mappings(company_symbol);

        CREATE TABLE IF NOT EXISTS equity_supplementary_mappings (
            sid INTEGER NOT NULL REFERENCES equities(sid),
            field TEXT NOT NULL,
            start_date INTEGER NOT NULL,
            end_date INTEGER NOT NULL,
            value TEXT NOT NULL,
            PRIMARY KEY (sid, field, start_date)
        );

        CREATE TABLE IF NOT EXISTS futures_root_symbols (
            root_symbol TEXT NOT NULL PRIMARY KEY,
            root_symbol_id INTEGER,
            sector TEXT,
            description TEXT,
            exchange TEXT REFERENCES exchanges(exchange),
            UNIQUE (root_symbol)
        );

        CREATE TABLE IF NOT EXISTS futures_contracts (
            sid INTEGER NOT NULL PRIMARY KEY,
            symbol TEXT UNIQUE,
            root_symbol TEXT REFERENCES futures_root_symbols(root_symbol),
            asset_name TEXT,
            start_date INTEGER DEFAULT 0 NOT NULL,
            end_date INTEGER NOT NULL,
            first_traded INTEGER,
            exchange TEXT REFERENCES exchanges(exchange),
            notice_date INTEGER NOT NULL,
            expiration_date INTEGER NOT NULL,
            auto_close_date INTEGER NOT NULL,
            multiplier REAL,
            tick_size REAL,
            UNIQUE (sid)
        );
        CREATE INDEX IF NOT EXISTS idx_fc_symbol ON futures_contracts(symbol);
        CREATE INDEX IF NOT EXISTS idx_fc_root ON futures_contracts(root_symbol);

        CREATE TABLE IF NOT EXISTS asset_router (
            sid INTEGER NOT NULL PRIMARY KEY,
            asset_type TEXT,
            UNIQUE (sid)
        );

        CREATE TABLE IF NOT EXISTS version_info (
            id INTEGER NOT NULL PRIMARY KEY CHECK (id <= 1),
            version INTEGER NOT NULL UNIQUE,
            UNIQUE (id)
        );

        CREATE TABLE IF NOT EXISTS bundle_metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bundle_name TEXT NOT NULL UNIQUE,
            source_type TEXT NOT NULL,
            source_url TEXT,
            api_version TEXT,
            fetch_timestamp INTEGER NOT NULL,
            data_version TEXT,
            timezone TEXT NOT NULL DEFAULT 'UTC',
            row_count INTEGER,
            start_date INTEGER,
            end_date INTEGER,
            missing_days_count INTEGER NOT NULL DEFAULT 0,
            missing_days_list TEXT NOT NULL DEFAULT '[]',
            outlier_count INTEGER NOT NULL DEFAULT 0,
            ohlcv_violations INTEGER NOT NULL DEFAULT 0,
            validation_passed INTEGER NOT NULL DEFAULT 1,
            validation_timestamp INTEGER,
            file_checksum TEXT,
            file_size_bytes INTEGER,
            checksum TEXT,
            calendar TEXT,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_bundle_metadata_name ON bundle_metadata(bundle_name);
        CREATE INDEX IF NOT EXISTS idx_bundle_metadata_fetch ON bundle_metadata(fetch_timestamp);
        CREATE INDEX IF NOT EXISTS idx_bundle_metadata_validation ON bundle_metadata(validation_timestamp);

        CREATE TABLE IF NOT EXISTS bundle_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cache_key TEXT NOT NULL UNIQUE,
            bundle_name TEXT NOT NULL,
            bundle_path TEXT NOT NULL,
            symbols TEXT,
            start TEXT,
            end TEXT,
            frequency TEXT,
            fetch_timestamp INTEGER NOT NULL,
            size_bytes INTEGER NOT NULL,
            row_count INTEGER,
            last_accessed INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_bundle_cache_key ON bundle_cache(cache_key);
        CREATE INDEX IF NOT EXISTS idx_bundle_cache_last_accessed ON bundle_cache(last_accessed);

        CREATE TABLE IF NOT EXISTS cache_statistics (
            stat_date INTEGER PRIMARY KEY,
            hit_count INTEGER DEFAULT 0,
            miss_count INTEGER DEFAULT 0,
            total_size_mb REAL DEFAULT 0.0,
            avg_fetch_latency_ms REAL DEFAULT 0.0
        );
        CREATE INDEX IF NOT EXISTS idx_cache_statistics_date ON cache_statistics(stat_date);

        CREATE TABLE IF NOT EXISTS bundle_symbols (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bundle_name TEXT NOT NULL REFERENCES bundle_metadata(bundle_name),
            symbol TEXT NOT NULL,
            asset_type TEXT,
            exchange TEXT,
            UNIQUE (bundle_name, symbol)
        );
        CREATE INDEX IF NOT EXISTS idx_bundle_symbols_bundle ON bundle_symbols(bundle_name);
        CREATE INDEX IF NOT EXISTS idx_bundle_symbols_symbol ON bundle_symbols(symbol);

        CREATE TABLE IF NOT EXISTS backtest_data_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            backtest_id TEXT NOT NULL,
            bundle_name TEXT NOT NULL REFERENCES bundle_metadata(bundle_name),
            accessed_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_backtest_data_links_backtest_id ON backtest_data_links(backtest_id);
        CREATE INDEX IF NOT EXISTS idx_backtest_data_links_bundle_name ON backtest_data_links(bundle_name);

        INSERT OR IGNORE INTO version_info (id, version) VALUES (1, 10);
    """
    )
    conn.commit()
    print("Schema created successfully")

    # Process each bundle directory
    bundle_dirs = [d for d in bundles_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]

    recovered_bundles = 0
    recovered_symbols = 0

    for bundle_dir in sorted(bundle_dirs):
        bundle_name = bundle_dir.name
        bundle_metadata_db = bundle_dir / "metadata.db"

        if not bundle_metadata_db.exists():
            print(f"  SKIP {bundle_name}: no metadata.db")
            continue

        try:
            bundle_conn = sqlite3.connect(bundle_metadata_db)
            bundle_cur = bundle_conn.cursor()

            # Get dataset info
            bundle_cur.execute("SELECT source, resolution FROM datasets LIMIT 1")
            dataset_row = bundle_cur.fetchone()
            source_type = dataset_row[0] if dataset_row else "unknown"
            resolution = dataset_row[1] if dataset_row else "unknown"

            # Get symbol count and date range
            bundle_cur.execute("SELECT COUNT(*) FROM symbols")
            symbol_count = bundle_cur.fetchone()[0]

            bundle_cur.execute(
                """
                SELECT MIN(start_date), MAX(end_date), SUM(row_count)
                FROM date_ranges
            """
            )
            date_row = bundle_cur.fetchone()
            start_date_str, end_date_str, total_rows = date_row if date_row else (None, None, 0)

            # Convert date strings to epoch if present
            start_date = None
            end_date = None
            if start_date_str:
                try:
                    from datetime import datetime

                    start_date = int(
                        datetime.fromisoformat(start_date_str.replace("Z", "+00:00")).timestamp()
                    )
                except (ValueError, TypeError):  # noqa: PERF203
                    pass
            if end_date_str:
                try:
                    from datetime import datetime

                    end_date = int(
                        datetime.fromisoformat(end_date_str.replace("Z", "+00:00")).timestamp()
                    )
                except (ValueError, TypeError):  # noqa: PERF203
                    pass

            current_time = int(time.time())

            # Insert bundle_metadata
            cur.execute(
                """
                INSERT INTO bundle_metadata (
                    bundle_name, source_type, source_url, api_version,
                    fetch_timestamp, data_version, timezone,
                    row_count, start_date, end_date,
                    missing_days_count, missing_days_list,
                    outlier_count, ohlcv_violations,
                    validation_passed, validation_timestamp,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    bundle_name,
                    source_type,
                    None,  # source_url
                    resolution,  # api_version (using resolution as placeholder)
                    current_time,  # fetch_timestamp
                    None,  # data_version
                    "UTC",  # timezone
                    total_rows or 0,
                    start_date,
                    end_date,
                    0,  # missing_days_count
                    "[]",  # missing_days_list
                    0,  # outlier_count
                    0,  # ohlcv_violations
                    1,  # validation_passed
                    current_time,  # validation_timestamp
                    current_time,  # created_at
                    current_time,  # updated_at
                ),
            )

            # Insert symbols
            bundle_cur.execute("SELECT symbol, asset_type, exchange FROM symbols")
            symbols = bundle_cur.fetchall()

            for symbol, asset_type, exchange in symbols:
                cur.execute(
                    """
                    INSERT INTO bundle_symbols (bundle_name, symbol, asset_type, exchange)
                    VALUES (?, ?, ?, ?)
                """,
                    (bundle_name, symbol, asset_type, exchange),
                )
                recovered_symbols += 1

            bundle_conn.close()
            recovered_bundles += 1
            print(f"  OK {bundle_name}: {symbol_count} symbols, {total_rows or 0} rows")

        except Exception as e:
            print(f"  ERROR {bundle_name}: {e}")

    conn.commit()
    conn.close()

    # Move temp db to final location
    if main_db_path.exists():
        backup_path = main_db_path.with_suffix(".db.pre_recovery")
        print(f"Backing up existing db to {backup_path}")
        shutil.move(str(main_db_path), str(backup_path))

    shutil.move(temp_db_path, str(main_db_path))

    print(f"\nRecovery complete:")
    print(f"  Bundles: {recovered_bundles}")
    print(f"  Symbols: {recovered_symbols}")
    print(f"  Database: {main_db_path}")


if __name__ == "__main__":
    recover_metadata()
