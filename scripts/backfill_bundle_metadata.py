#!/usr/bin/env python3
"""Backfill local bundle metadata from existing parquet files and global DB.

This script populates the local metadata.db (symbols and date_ranges tables)
for bundles that were created before the local metadata feature was added.

Usage:
    python scripts/backfill_bundle_metadata.py binance-spot-1d
    python scripts/backfill_bundle_metadata.py binance-spot-1d binance-spot-1h
"""

import glob
import sys
from datetime import datetime
from pathlib import Path

import polars as pl
import structlog
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from rustybt.data.polars.local_bundle_metadata import LocalBundleMetadata

logger = structlog.get_logger()


def get_bundle_path(bundle_name: str) -> Path:
    """Get path to bundle directory."""
    zipline_root = Path.home() / ".zipline"
    bundle_path = zipline_root / "data" / "bundles" / bundle_name

    if not bundle_path.exists():
        raise FileNotFoundError(f"Bundle not found: {bundle_path}")

    return bundle_path


def get_global_symbols(bundle_name: str) -> dict[int, dict]:
    """Get symbol information from global assets DB."""
    zipline_root = Path.home() / ".zipline"

    # Find the assets DB (try multiple versions)
    assets_db = None
    for version in range(15, 0, -1):
        db_path = zipline_root / f"assets-{version}.db"
        if db_path.exists() and db_path.stat().st_size > 0:
            assets_db = db_path
            break

    if assets_db is None:
        raise FileNotFoundError("No global assets DB found in ~/.zipline")

    logger.info("using_global_db", path=str(assets_db))

    engine = create_engine(f"sqlite:///{assets_db}")
    symbols_by_sid = {}

    with Session(engine) as session:
        result = session.execute(
            text(
                "SELECT id, symbol, asset_type, exchange "
                "FROM bundle_symbols "
                "WHERE bundle_name = :bundle_name"
            ),
            {"bundle_name": bundle_name},
        )

        for row in result:
            symbols_by_sid[row[0]] = {
                "sid": row[0],
                "symbol": row[1],
                "asset_type": row[2] or "equity",
                "exchange": row[3] or "UNKNOWN",
            }

    logger.info(
        "global_symbols_loaded",
        bundle=bundle_name,
        symbol_count=len(symbols_by_sid),
    )

    return symbols_by_sid


def calculate_per_symbol_date_ranges(parquet_files: list[str]) -> dict[int, dict]:
    """Calculate date ranges for each SID from parquet files."""
    logger.info("calculating_date_ranges", file_count=len(parquet_files))

    # Track per-SID date ranges
    sid_data = {}

    for i, parquet_file in enumerate(parquet_files):
        if (i + 1) % 10 == 0:
            logger.info("processing_files", current=i + 1, total=len(parquet_files))

        try:
            df = pl.read_parquet(parquet_file)

            # Handle schema inconsistency (some files have year/month columns)
            if "year" in df.columns:
                df = df.drop(["year", "month"])

            if "date" not in df.columns or "sid" not in df.columns:
                logger.warning("invalid_schema", file=parquet_file, columns=df.columns)
                continue

            # Group by SID and calculate date ranges
            for sid_group in df.group_by("sid"):
                sid = sid_group[0][0]  # Extract SID from group key
                sid_df = sid_group[1]  # Get group DataFrame

                dates = sid_df["date"].unique().sort()
                if len(dates) == 0:
                    continue

                start_date = dates.min()
                end_date = dates.max()
                row_count = len(sid_df)

                # Convert to date objects
                if isinstance(start_date, datetime):
                    start_date = start_date.date()
                if isinstance(end_date, datetime):
                    end_date = end_date.date()

                # Update running min/max for this SID
                if sid in sid_data:
                    sid_data[sid]["start_date"] = min(sid_data[sid]["start_date"], start_date)
                    sid_data[sid]["end_date"] = max(sid_data[sid]["end_date"], end_date)
                    sid_data[sid]["row_count"] += row_count
                else:
                    sid_data[sid] = {
                        "start_date": start_date,
                        "end_date": end_date,
                        "row_count": row_count,
                    }

        except Exception as e:
            logger.error("file_processing_error", file=parquet_file, error=str(e))

    logger.info("date_ranges_calculated", sid_count=len(sid_data))

    return sid_data


def backfill_bundle_metadata(bundle_name: str, dry_run: bool = False) -> None:
    """Backfill local metadata for a bundle.

    Args:
        bundle_name: Name of the bundle to backfill
        dry_run: If True, only show what would be done without making changes
    """
    logger.info("backfill_start", bundle=bundle_name, dry_run=dry_run)

    # Get bundle path
    bundle_path = get_bundle_path(bundle_name)
    logger.info("bundle_found", path=str(bundle_path))

    # Get symbols from global DB
    symbols_by_sid = get_global_symbols(bundle_name)

    if not symbols_by_sid:
        logger.error("no_symbols_found", bundle=bundle_name)
        return

    # Find all parquet files
    daily_bars_path = bundle_path / "daily_bars"
    minute_bars_path = bundle_path / "minute_bars"

    parquet_files = []
    if daily_bars_path.exists():
        parquet_files.extend(glob.glob(str(daily_bars_path / "year=*/month=*/data.parquet")))
    if minute_bars_path.exists():
        parquet_files.extend(glob.glob(str(minute_bars_path / "year=*/month=*/day=*/data.parquet")))

    logger.info("parquet_files_found", count=len(parquet_files))

    if not parquet_files:
        logger.error("no_parquet_files_found", bundle=bundle_name)
        return

    # Calculate per-symbol date ranges from parquet data
    sid_date_ranges = calculate_per_symbol_date_ranges(parquet_files)

    if dry_run:
        logger.info(
            "dry_run_summary", symbols=len(symbols_by_sid), sids_with_data=len(sid_date_ranges)
        )
        for sid, data in list(sid_date_ranges.items())[:10]:
            symbol_info = symbols_by_sid.get(sid, {})
            logger.info(
                "dry_run_sample",
                sid=sid,
                symbol=symbol_info.get("symbol", "UNKNOWN"),
                start_date=data["start_date"],
                end_date=data["end_date"],
                rows=data["row_count"],
            )
        return

    # Initialize local metadata
    local_metadata = LocalBundleMetadata(bundle_path)

    # Clear existing data to start fresh
    logger.info("clearing_existing_metadata")
    local_metadata.clear_all()

    # Populate symbols
    logger.info("populating_symbols", count=len(symbols_by_sid))
    for sid, symbol_info in symbols_by_sid.items():
        local_metadata.add_symbol(
            sid=sid,
            symbol=symbol_info["symbol"],
            asset_type=symbol_info["asset_type"],
            exchange=symbol_info["exchange"],
        )

    # Populate date ranges
    logger.info("populating_date_ranges", count=len(sid_date_ranges))
    symbols_with_data = 0
    symbols_without_data = 0

    for sid, symbol_info in symbols_by_sid.items():
        if sid in sid_date_ranges:
            date_range = sid_date_ranges[sid]
            local_metadata.update_date_range(
                sid=sid,
                start_date=date_range["start_date"],
                end_date=date_range["end_date"],
                row_count=date_range["row_count"],
            )
            symbols_with_data += 1
        else:
            # Symbol exists in DB but has no data in parquet files
            logger.debug(
                "symbol_without_data",
                sid=sid,
                symbol=symbol_info["symbol"],
            )
            symbols_without_data += 1

    logger.info(
        "backfill_complete",
        bundle=bundle_name,
        total_symbols=len(symbols_by_sid),
        symbols_with_data=symbols_with_data,
        symbols_without_data=symbols_without_data,
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/backfill_bundle_metadata.py <bundle_name> [bundle_name2 ...]")
        print("\nExample:")
        print("  python scripts/backfill_bundle_metadata.py binance-spot-1d")
        print("  python scripts/backfill_bundle_metadata.py binance-spot-1d binance-spot-1h")
        print("\nAdd --dry-run to see what would be done without making changes:")
        print("  python scripts/backfill_bundle_metadata.py binance-spot-1d --dry-run")
        sys.exit(1)

    dry_run = "--dry-run" in sys.argv
    bundle_names = [arg for arg in sys.argv[1:] if arg != "--dry-run"]

    for bundle_name in bundle_names:
        try:
            backfill_bundle_metadata(bundle_name, dry_run=dry_run)
        except Exception as e:
            logger.error("backfill_failed", bundle=bundle_name, error=str(e))
            import traceback

            traceback.print_exc()
