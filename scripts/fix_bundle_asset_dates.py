#!/usr/bin/env python3
"""Fix asset dates in Parquet bundles by scanning actual data availability.

This script scans all Parquet data files to determine the actual start and end dates
for each asset, then populates the bundle metadata database with this information.

Usage:
    python scripts/fix_bundle_asset_dates.py <bundle-name>

Example:
    python scripts/fix_bundle_asset_dates.py binance-spot-1d
"""

import glob
import sqlite3
import sys
from pathlib import Path

import polars as pl
import structlog

logger = structlog.get_logger(__name__)


def scan_parquet_data(bundle_path: Path) -> dict:
    """Scan all Parquet files to get actual data availability per asset.

    Args:
        bundle_path: Path to bundle directory

    Returns:
        Dictionary mapping sid to {symbol, min_date, max_date, row_count}
    """
    daily_bars = bundle_path / "daily_bars"
    parquet_files = glob.glob(str(daily_bars / "**/*.parquet"), recursive=True)

    logger.info("scanning_parquet_files", file_count=len(parquet_files), bundle=bundle_path.name)

    asset_data = {}

    for file_path in parquet_files:
        rel_path = Path(file_path).relative_to(daily_bars)
        logger.debug("reading_parquet_file", file=str(rel_path))

        df = pl.read_parquet(file_path)

        # Group by sid to get min/max dates
        grouped = df.group_by("sid").agg(
            [
                pl.col("date").min().alias("min_date"),
                pl.col("date").max().alias("max_date"),
                pl.col("date").count().alias("row_count"),
            ]
        )

        for row in grouped.iter_rows(named=True):
            sid = row["sid"]
            min_date = row["min_date"]
            max_date = row["max_date"]
            row_count = row["row_count"]

            if sid not in asset_data:
                asset_data[sid] = {
                    "min_date": min_date,
                    "max_date": max_date,
                    "row_count": row_count,
                }
            else:
                # Update if this file has earlier/later dates
                asset_data[sid]["min_date"] = min(asset_data[sid]["min_date"], min_date)
                asset_data[sid]["max_date"] = max(asset_data[sid]["max_date"], max_date)
                asset_data[sid]["row_count"] += row_count

    logger.info("parquet_scan_complete", bundle=bundle_path.name, unique_assets=len(asset_data))

    return asset_data


def get_symbol_mappings(bundle_name: str) -> dict:
    """Get sid-to-symbol mappings from global assets database.

    Args:
        bundle_name: Name of the bundle

    Returns:
        Dictionary mapping sid to symbol name
    """
    # Try to load from global assets database first
    zipline_root = Path.home() / ".zipline"
    assets_db = zipline_root / "assets-10.db"

    if not assets_db.exists():
        logger.warning(
            "assets_db_not_found",
            path=str(assets_db),
            message="Cannot find global assets database",
        )
        return {}

    conn = sqlite3.connect(str(assets_db))
    cursor = conn.cursor()

    # Query bundle_symbols table
    cursor.execute(
        "SELECT id, symbol FROM bundle_symbols WHERE bundle_name = ?",
        (bundle_name,),
    )
    rows = cursor.fetchall()
    conn.close()

    mappings = {row[0]: row[1] for row in rows}

    if mappings:
        logger.info("loaded_symbol_mappings", count=len(mappings), source="global assets DB")
    else:
        logger.warning(
            "no_symbol_mappings",
            bundle_name=bundle_name,
            message="No symbols found in global assets DB - will use generic names",
        )

    return mappings


def populate_metadata(
    bundle_path: Path, asset_data: dict, symbol_mappings: dict, force: bool = False
):
    """Populate metadata.db with asset information and date ranges.

    Args:
        bundle_path: Path to bundle directory
        asset_data: Dictionary of asset data from scan_parquet_data()
        symbol_mappings: Dictionary of sid-to-symbol mappings
    """
    metadata_db = bundle_path / "metadata.db"
    conn = sqlite3.connect(str(metadata_db))
    cursor = conn.cursor()

    # Check if symbols table is empty
    cursor.execute("SELECT COUNT(*) FROM symbols")
    existing_count = cursor.fetchone()[0]

    if existing_count > 0:
        logger.info("symbols_table_not_empty", count=existing_count)
        if not force:
            response = input(
                f"\nWarning: symbols table already has {existing_count} entries.\n"
                "Do you want to clear and repopulate? (yes/no): "
            )
            if response.lower() != "yes":
                logger.info("metadata_population_cancelled")
                conn.close()
                return
        else:
            logger.info("force_mode_enabled", message="Skipping confirmation")
        cursor.execute("DELETE FROM symbols")
        logger.info("symbols_table_cleared")

    # Get or create dataset_id
    cursor.execute("SELECT dataset_id FROM datasets LIMIT 1")
    row = cursor.fetchone()
    if row:
        dataset_id = row[0]
        logger.info("using_existing_dataset", dataset_id=dataset_id)
    else:
        # Create default dataset with required fields
        import time

        timestamp = int(time.time())
        cursor.execute(
            """
            INSERT INTO datasets (source, resolution, schema_version, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """,
            (bundle_path.name, "1d", 1, timestamp, timestamp),
        )
        dataset_id = cursor.lastrowid
        logger.info("dataset_created", dataset_id=dataset_id)

    # Insert symbols with date ranges
    logger.info("populating_symbols", count=len(asset_data))

    for sid, data in sorted(asset_data.items()):
        symbol = symbol_mappings.get(sid, f"ASSET_{sid}")

        cursor.execute(
            """
            INSERT INTO symbols (symbol_id, dataset_id, symbol, asset_type, exchange)
            VALUES (?, ?, ?, ?, ?)
        """,
            (sid, dataset_id, symbol, "equity", "BINANCE"),
        )

        logger.debug(
            "symbol_inserted",
            sid=sid,
            symbol=symbol,
            start=str(data["min_date"]),
            end=str(data["max_date"]),
            rows=data["row_count"],
        )

    conn.commit()
    conn.close()

    logger.info("metadata_populated", bundle=bundle_path.name, symbols_inserted=len(asset_data))


def update_asset_finder_dates(bundle_path: Path, asset_data: dict, symbol_mappings: dict):
    """Update ParquetAssetFinder to use actual dates instead of placeholders.

    Args:
        bundle_path: Path to bundle directory
        asset_data: Dictionary of asset data from scan_parquet_data()
        symbol_mappings: Dictionary of sid-to-symbol mappings
    """
    logger.info("asset_finder_update_info", message="ParquetAssetFinder now needs code update")
    logger.info(
        "next_steps",
        message="Update ParquetAssetFinder._load_symbols() to query date_ranges table",
    )


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Fix asset dates in Parquet bundles")
    parser.add_argument("bundle_name", help="Name of bundle to fix")
    parser.add_argument(
        "--force", "-f", action="store_true", help="Force update without confirmation"
    )
    args = parser.parse_args()

    bundle_name = args.bundle_name
    force = args.force
    zipline_root = Path.home() / ".zipline"
    bundle_path = zipline_root / "data" / "bundles" / bundle_name

    if not bundle_path.exists():
        logger.error("bundle_not_found", bundle_path=str(bundle_path))
        sys.exit(1)

    logger.info("starting_bundle_fix", bundle=bundle_name, path=str(bundle_path))

    # Step 1: Scan Parquet data
    print("\n" + "=" * 60)
    print("Step 1: Scanning Parquet data for actual asset date ranges...")
    print("=" * 60)
    asset_data = scan_parquet_data(bundle_path)

    # Print summary
    print(f"\nFound {len(asset_data)} unique assets")
    print("\nSample assets with date ranges:")
    for sid in list(asset_data.keys())[:10]:
        data = asset_data[sid]
        print(f"  SID {sid}: {data['min_date']} to {data['max_date']} ({data['row_count']} rows)")

    # Step 2: Get symbol mappings
    print("\n" + "=" * 60)
    print("Step 2: Loading symbol mappings...")
    print("=" * 60)
    symbol_mappings = get_symbol_mappings(bundle_name)

    if not symbol_mappings:
        print(
            "\nWarning: No symbol mappings found in metadata.db."
            "\nSymbols will be set to 'ASSET_<sid>'"
        )

    # Step 3: Populate metadata
    print("\n" + "=" * 60)
    print("Step 3: Populating metadata database...")
    print("=" * 60)
    populate_metadata(bundle_path, asset_data, symbol_mappings, force=force)

    # Step 4: Create date_ranges table
    print("\n" + "=" * 60)
    print("Step 4: Creating date_ranges table...")
    print("=" * 60)

    metadata_db = bundle_path / "metadata.db"
    conn = sqlite3.connect(str(metadata_db))
    cursor = conn.cursor()

    # Create date_ranges table if it doesn't exist
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS date_ranges (
            symbol_id INTEGER PRIMARY KEY,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            row_count INTEGER NOT NULL,
            FOREIGN KEY(symbol_id) REFERENCES symbols(symbol_id)
        )
    """
    )

    # Populate date_ranges
    for sid, data in asset_data.items():
        cursor.execute(
            """
            INSERT OR REPLACE INTO date_ranges (symbol_id, start_date, end_date, row_count)
            VALUES (?, ?, ?, ?)
        """,
            (sid, str(data["min_date"]), str(data["max_date"]), data["row_count"]),
        )

    conn.commit()
    conn.close()

    logger.info("date_ranges_table_created", row_count=len(asset_data))

    # Success
    print("\n" + "=" * 60)
    print("✅ Bundle asset dates fixed successfully!")
    print("=" * 60)
    print(f"\nUpdated {len(asset_data)} assets with real date ranges")
    print("\nNext: Update ParquetAssetFinder to use the date_ranges table")


if __name__ == "__main__":
    main()
