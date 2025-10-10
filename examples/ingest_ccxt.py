"""Example: Ingest cryptocurrency data from CCXT (Binance).

This example demonstrates how to ingest hourly cryptocurrency data from Binance
using the CCXT adapter.

Usage:
    python examples/ingest_ccxt.py
"""

import asyncio

import pandas as pd

from rustybt.data.bundles.metadata import BundleMetadata
from rustybt.data.sources import DataSourceRegistry


async def main():
    """Ingest crypto data from Binance via CCXT."""
    print("=" * 60)
    print("CCXT (Binance) Cryptocurrency Ingestion Example")
    print("=" * 60)

    # Get CCXT data source for Binance
    print("\n[1/4] Initializing CCXT data source (Binance)...")
    source = DataSourceRegistry.get_source("ccxt", exchange="binance")
    print("✓ CCXT source initialized for Binance")

    # Define ingestion parameters
    bundle_name = "crypto-hourly-example"
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    start = pd.Timestamp("2024-01-01")
    end = pd.Timestamp("2024-01-31")
    frequency = "1h"

    print("\n[2/4] Ingesting data...")
    print(f"  Bundle: {bundle_name}")
    print("  Exchange: Binance")
    print(f"  Symbols: {', '.join(symbols)}")
    print(f"  Period: {start.date()} to {end.date()}")
    print(f"  Frequency: {frequency}")
    print("  Note: This may take a few minutes for hourly data...")

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
    print(f"  Date range: {metadata.start_date} to {metadata.end_date}")
    print(f"  Rows: {metadata.row_count:,}")
    print(f"  Size: {metadata.size_bytes / 1024 / 1024:.2f} MB")
    print(f"  Quality score: {metadata.quality_score:.2%}")
    print(f"  Missing data: {metadata.missing_data_pct:.2%}")

    # Calculate data points per symbol
    days = (end - start).days
    hours = days * 24
    expected_rows_per_symbol = hours
    print(f"  Expected rows per symbol: ~{expected_rows_per_symbol}")
    print(f"  Actual rows per symbol: ~{metadata.row_count // len(symbols)}")

    print("\n" + "=" * 60)
    print("✓ Crypto bundle created successfully!")
    print("=" * 60)
    print("\nNext steps:")
    print(f"  1. Use in crypto backtest: bundle='{bundle_name}'")
    print("  2. Try different exchanges: exchange='coinbase', 'kraken', etc.")
    print("  3. Ingest minute data: frequency='1m' (for HFT strategies)")


if __name__ == "__main__":
    asyncio.run(main())
