"""Example: Ingest stock data from Yahoo Finance.

This example demonstrates how to use the unified DataSource API to ingest
historical stock data into a Parquet bundle.

Usage:
    python examples/ingest_yfinance.py
"""

import asyncio

import pandas as pd

from rustybt.data.bundles.metadata import BundleMetadata
from rustybt.data.sources import DataSourceRegistry


async def main():
    """Ingest stock data from Yahoo Finance."""
    print("=" * 60)
    print("Yahoo Finance Data Ingestion Example")
    print("=" * 60)

    # Get YFinance data source
    print("\n[1/4] Initializing YFinance data source...")
    source = DataSourceRegistry.get_source("yfinance")
    print("✓ Data source initialized")

    # Define ingestion parameters
    bundle_name = "yfinance-example"
    symbols = ["AAPL", "MSFT", "GOOGL"]
    start = pd.Timestamp("2023-01-01")
    end = pd.Timestamp("2023-12-31")
    frequency = "1d"

    print("\n[2/4] Ingesting data...")
    print(f"  Bundle: {bundle_name}")
    print(f"  Symbols: {', '.join(symbols)}")
    print(f"  Period: {start.date()} to {end.date()}")
    print(f"  Frequency: {frequency}")

    # Ingest data to bundle
    bundle_path = await source.ingest_to_bundle(
        bundle_name=bundle_name,
        symbols=symbols,
        start=start,
        end=end,
        frequency=frequency,
    )
    print(f"✓ Data ingested to: {bundle_path}")

    # Load and display bundle metadata
    print("\n[3/4] Loading bundle metadata...")
    metadata = BundleMetadata.load(bundle_name)
    print("✓ Metadata loaded")

    print("\n[4/4] Bundle Summary:")
    print(f"  Symbols: {len(metadata.symbols)}")
    print(f"  Date range: {metadata.start_date.date()} to {metadata.end_date.date()}")
    print(f"  Rows: {metadata.row_count:,}")
    print(f"  Size: {metadata.size_bytes / 1024 / 1024:.2f} MB")
    print(f"  Quality score: {metadata.quality_score:.2%}")
    print(f"  Missing data: {metadata.missing_data_pct:.2%}")

    print("\n" + "=" * 60)
    print("✓ Bundle created successfully!")
    print("=" * 60)
    print("\nNext steps:")
    print(f"  1. Use bundle in backtest: bundle='{bundle_name}'")
    print(f"  2. View bundle info: rustybt bundle info {bundle_name}")
    print(f"  3. Validate bundle: rustybt bundle validate {bundle_name}")


if __name__ == "__main__":
    asyncio.run(main())
