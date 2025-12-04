#!/usr/bin/env python3
"""Ingest CME Databento packages into rustybt bundles."""

import asyncio
import sys
from pathlib import Path

import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from rustybt.data.adapters.databento_adapter import DatabentoAdapter, DatabentoConfig


def ingest_cme_daily():
    """Ingest CME daily OHLCV data with Definition enrichment."""

    data_dir = project_root / "databento" / "CME packages"

    ohlcv_path = data_dir / "GLBX-CME-1D.zip"
    definition_path = data_dir / "GLBX-CME-DEFINITION.zip"

    print(f"OHLCV path: {ohlcv_path}")
    print(f"Definition path: {definition_path}")
    print(f"OHLCV exists: {ohlcv_path.exists()}")
    print(f"Definition exists: {definition_path.exists()}")

    if not ohlcv_path.exists():
        print(f"ERROR: OHLCV file not found: {ohlcv_path}")
        return

    # Configure adapter
    config = DatabentoConfig(
        data_path=str(ohlcv_path),
        definition_package_path=str(definition_path) if definition_path.exists() else None,
        timezone="UTC",
        use_instrument_id=True,
        symbol_format="symbol_id",
        include_user_defined_spreads=False,  # Filter out UDS
        extra_columns=["instrument_id"],  # Keep instrument_id for reference
    )

    print(f"\nConfiguration:")
    print(f"  - use_instrument_id: {config.use_instrument_id}")
    print(f"  - include_user_defined_spreads: {config.include_user_defined_spreads}")
    print(f"  - definition_package_path: {config.definition_package_path}")

    # Create adapter with context manager for cleanup
    with DatabentoAdapter(config=config) as adapter:
        print("\nStarting ingestion...")

        # Ingest all symbols for full date range
        # The adapter will detect date range from metadata
        adapter.ingest_to_bundle(
            bundle_name="cme-daily",
            symbols=[],  # Empty = all symbols
            start=pd.Timestamp("2000-01-01"),  # Will be clipped to actual data range
            end=pd.Timestamp("2030-12-31"),
            frequency="1d",
        )

        print("\nIngestion complete!")
        print("Bundle created: cme-daily")
        print("\nTo verify: rustybt bundle info cme-daily")


def ingest_cme_hourly():
    """Ingest CME hourly OHLCV data with Definition enrichment."""

    data_dir = project_root / "databento" / "CME packages"

    ohlcv_path = data_dir / "GLBX-CME-1H.zip"
    definition_path = data_dir / "GLBX-CME-DEFINITION.zip"

    print(f"OHLCV path: {ohlcv_path}")
    print(f"Definition path: {definition_path}")

    if not ohlcv_path.exists():
        print(f"ERROR: OHLCV file not found: {ohlcv_path}")
        return

    # Configure adapter
    config = DatabentoConfig(
        data_path=str(ohlcv_path),
        definition_package_path=str(definition_path) if definition_path.exists() else None,
        timezone="UTC",
        use_instrument_id=True,
        symbol_format="symbol_id",
        include_user_defined_spreads=False,
        extra_columns=["instrument_id"],
    )

    with DatabentoAdapter(config=config) as adapter:
        print("\nStarting hourly ingestion...")

        adapter.ingest_to_bundle(
            bundle_name="cme-hourly",
            symbols=[],
            start=pd.Timestamp("2000-01-01"),
            end=pd.Timestamp("2030-12-31"),
            frequency="1h",
        )

        print("\nIngestion complete!")
        print("Bundle created: cme-hourly")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ingest CME Databento packages")
    parser.add_argument(
        "--frequency",
        "-f",
        choices=["1d", "1h", "all"],
        default="1d",
        help="Frequency to ingest (default: 1d)",
    )

    args = parser.parse_args()

    if args.frequency == "1d":
        ingest_cme_daily()
    elif args.frequency == "1h":
        ingest_cme_hourly()
    elif args.frequency == "all":
        print("=" * 60)
        print("Ingesting CME Daily")
        print("=" * 60)
        ingest_cme_daily()

        print("\n" + "=" * 60)
        print("Ingesting CME Hourly")
        print("=" * 60)
        ingest_cme_hourly()
