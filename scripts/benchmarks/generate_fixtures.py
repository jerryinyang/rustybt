#!/usr/bin/env python
"""Generate benchmark data fixtures.

This script generates deterministic synthetic OHLCV data for benchmarking.
All fixtures use seed=42 for reproducibility.

Usage:
    python scripts/benchmarks/generate_fixtures.py
    python scripts/benchmarks/generate_fixtures.py --frequency daily --assets 50
"""

import argparse
import logging
from datetime import datetime
from pathlib import Path

import numpy as np
import polars as pl

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Constants
SEED = 42
DATA_DIR = Path(__file__).parent.parent.parent / "tests" / "benchmarks" / "data"
MAX_TOTAL_SIZE_MB = 500


def generate_ohlcv_data(
    start_date: datetime,
    end_date: datetime,
    frequency: str,
    num_assets: int,
    seed: int = SEED,
) -> pl.DataFrame:
    """Generate deterministic synthetic OHLCV data.

    Args:
        start_date: Start date for data generation
        end_date: End date for data generation
        frequency: Data frequency ('1d', '1h', '1m')
        num_assets: Number of assets to generate
        seed: Random seed for reproducibility

    Returns:
        Polars DataFrame with OHLCV data
    """
    np.random.seed(seed)

    # Generate timestamps based on frequency
    if frequency == "1d":
        # Daily: business days only
        timestamps = pl.datetime_range(start_date, end_date, interval="1d", eager=True)
        # Filter to weekdays (simple approximation, ignores holidays)
        timestamps_df = pl.DataFrame({"timestamp": timestamps})
        timestamps_df = timestamps_df.filter(
            pl.col("timestamp").dt.weekday() < 5  # Monday=0, Friday=4
        )
        timestamps = timestamps_df["timestamp"].to_list()
    elif frequency == "1h":
        # Hourly: 24/7 (crypto-style)
        timestamps = pl.datetime_range(start_date, end_date, interval="1h", eager=True).to_list()
    elif frequency == "1m":
        # Minute: 24/7 (crypto-style)
        timestamps = pl.datetime_range(start_date, end_date, interval="1m", eager=True).to_list()
    else:
        raise ValueError(f"Invalid frequency: {frequency}")

    logger.info(
        f"Generating {len(timestamps)} bars for {num_assets} assets at {frequency} frequency"
    )

    # Generate OHLCV for each asset
    data_rows = []

    for asset_id in range(num_assets):
        # Initialize price at 100 with asset-specific offset
        base_price = 100.0 + (asset_id * 0.5)
        current_price = base_price

        for ts in timestamps:
            # Random walk with drift
            # Daily volatility ~2%, hourly ~0.3%, minute ~0.05%
            if frequency == "1d":
                volatility = 0.02
            elif frequency == "1h":
                volatility = 0.003
            else:  # 1m
                volatility = 0.0005

            # Generate returns with slight upward drift
            drift = 0.0001
            returns = drift + (volatility * np.random.randn())
            current_price = current_price * (1 + returns)

            # Ensure price stays positive
            current_price = max(current_price, 1.0)

            # Generate OHLC from close price
            close = current_price

            # High/Low spread based on volatility
            spread = current_price * volatility * abs(np.random.randn())
            high = close + spread * np.random.uniform(0.5, 1.5)
            low = close - spread * np.random.uniform(0.5, 1.5)

            # Open between low and high
            open_price = low + (high - low) * np.random.uniform(0.2, 0.8)

            # Ensure OHLC relationships
            high = max(high, open_price, close)
            low = min(low, open_price, close)

            # Generate volume (log-normal distribution)
            mean_volume = 100000
            volume_std = 50000
            volume = max(int(np.random.lognormal(np.log(mean_volume), 0.5)), 1000)

            data_rows.append(
                {
                    "timestamp": ts,
                    "asset": f"ASSET{asset_id:03d}",
                    "open": open_price,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": volume,
                }
            )

    # Create DataFrame
    df = pl.DataFrame(data_rows)

    # Validate OHLC relationships
    invalid_rows = df.filter(
        (pl.col("high") < pl.col("low"))
        | (pl.col("high") < pl.col("open"))
        | (pl.col("high") < pl.col("close"))
        | (pl.col("low") > pl.col("open"))
        | (pl.col("low") > pl.col("close"))
    )

    if len(invalid_rows) > 0:
        logger.warning(f"Found {len(invalid_rows)} rows with invalid OHLC relationships")
        # Fix them
        df = df.with_columns(
            [
                pl.when(pl.col("high") < pl.col("low"))
                .then(pl.col("low"))
                .otherwise(pl.col("high"))
                .alias("high"),
            ]
        )

    return df


def save_fixture(
    df: pl.DataFrame,
    filename: str,
    compression: str = "snappy",
) -> int:
    """Save fixture to Parquet file.

    Args:
        df: DataFrame to save
        filename: Output filename
        compression: Compression algorithm ('snappy', 'gzip', 'zstd')

    Returns:
        File size in bytes
    """
    output_path = DATA_DIR / filename

    # Write to Parquet with compression
    df.write_parquet(
        output_path,
        compression=compression,
        statistics=True,
        use_pyarrow=True,
    )

    file_size = output_path.stat().st_size
    file_size_mb = file_size / (1024 * 1024)

    logger.info(f"Saved {filename}: {file_size_mb:.2f} MB ({len(df)} rows)")

    return file_size


def generate_all_fixtures():
    """Generate all benchmark fixtures."""
    # Create data directory if it doesn't exist
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    logger.info(f"Generating fixtures in {DATA_DIR}")

    total_size = 0
    fixtures_generated = 0

    # Define fixtures to generate
    fixtures = [
        # Daily fixtures (2 years)
        {
            "name": "daily_10_assets.parquet",
            "frequency": "1d",
            "assets": 10,
            "start": datetime(2023, 1, 1),
            "end": datetime(2025, 1, 1),
            "max_size_mb": 10,
        },
        {
            "name": "daily_50_assets.parquet",
            "frequency": "1d",
            "assets": 50,
            "start": datetime(2023, 1, 1),
            "end": datetime(2025, 1, 1),
            "max_size_mb": 10,
        },
        {
            "name": "daily_100_assets.parquet",
            "frequency": "1d",
            "assets": 100,
            "start": datetime(2023, 1, 1),
            "end": datetime(2025, 1, 1),
            "max_size_mb": 30,
        },
        {
            "name": "daily_500_assets.parquet",
            "frequency": "1d",
            "assets": 500,
            "start": datetime(2023, 1, 1),
            "end": datetime(2025, 1, 1),
            "max_size_mb": 100,
        },
        # Hourly fixtures (6 months)
        {
            "name": "hourly_10_assets.parquet",
            "frequency": "1h",
            "assets": 10,
            "start": datetime(2024, 7, 1),
            "end": datetime(2025, 1, 1),
            "max_size_mb": 10,
        },
        {
            "name": "hourly_20_assets.parquet",
            "frequency": "1h",
            "assets": 20,
            "start": datetime(2024, 7, 1),
            "end": datetime(2025, 1, 1),
            "max_size_mb": 10,
        },
        {
            "name": "hourly_50_assets.parquet",
            "frequency": "1h",
            "assets": 50,
            "start": datetime(2024, 7, 1),
            "end": datetime(2025, 1, 1),
            "max_size_mb": 30,
        },
        {
            "name": "hourly_100_assets.parquet",
            "frequency": "1h",
            "assets": 100,
            "start": datetime(2024, 7, 1),
            "end": datetime(2025, 1, 1),
            "max_size_mb": 30,
        },
        # Minute fixtures (1 month)
        {
            "name": "minute_10_assets.parquet",
            "frequency": "1m",
            "assets": 10,
            "start": datetime(2024, 12, 1),
            "end": datetime(2025, 1, 1),
            "max_size_mb": 10,
        },
        {
            "name": "minute_20_assets.parquet",
            "frequency": "1m",
            "assets": 20,
            "start": datetime(2024, 12, 1),
            "end": datetime(2025, 1, 1),
            "max_size_mb": 10,
        },
        {
            "name": "minute_50_assets.parquet",
            "frequency": "1m",
            "assets": 50,
            "start": datetime(2024, 12, 1),
            "end": datetime(2025, 1, 1),
            "max_size_mb": 30,
        },
    ]

    for fixture_spec in fixtures:
        logger.info(f"\nGenerating {fixture_spec['name']}...")

        # Generate data
        df = generate_ohlcv_data(
            start_date=fixture_spec["start"],
            end_date=fixture_spec["end"],
            frequency=fixture_spec["frequency"],
            num_assets=fixture_spec["assets"],
            seed=SEED,
        )

        # Save fixture
        file_size = save_fixture(df, fixture_spec["name"], compression="snappy")
        file_size_mb = file_size / (1024 * 1024)

        # Check size constraint
        if file_size_mb > fixture_spec["max_size_mb"]:
            logger.warning(
                f"Fixture {fixture_spec['name']} exceeds size limit: "
                f"{file_size_mb:.2f} MB > {fixture_spec['max_size_mb']} MB"
            )
            # Try with better compression
            logger.info("Retrying with gzip compression...")
            file_size = save_fixture(df, fixture_spec["name"], compression="gzip")
            file_size_mb = file_size / (1024 * 1024)
            logger.info(f"Compressed size: {file_size_mb:.2f} MB")

        total_size += file_size
        fixtures_generated += 1

    total_size_mb = total_size / (1024 * 1024)
    logger.info(f"\nGenerated {fixtures_generated} fixtures")
    logger.info(f"Total size: {total_size_mb:.2f} MB (target: {MAX_TOTAL_SIZE_MB} MB)")

    if total_size_mb > MAX_TOTAL_SIZE_MB:
        logger.warning(f"Total size exceeds target by {total_size_mb - MAX_TOTAL_SIZE_MB:.2f} MB")
    else:
        logger.info(f"Within target size (margin: {MAX_TOTAL_SIZE_MB - total_size_mb:.2f} MB)")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate benchmark data fixtures")
    parser.add_argument(
        "--frequency",
        choices=["1d", "1h", "1m", "all"],
        default="all",
        help="Data frequency to generate (default: all)",
    )
    parser.add_argument(
        "--assets", type=int, help='Number of assets (only used with --frequency, not "all")'
    )

    args = parser.parse_args()

    if args.frequency == "all":
        generate_all_fixtures()
    else:
        if args.assets is None:
            parser.error(f"--assets is required when --frequency is {args.frequency}")

        # Generate single fixture
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        if args.frequency == "1d":
            start_date = datetime(2023, 1, 1)
            end_date = datetime(2025, 1, 1)
        elif args.frequency == "1h":
            start_date = datetime(2024, 7, 1)
            end_date = datetime(2025, 1, 1)
        else:  # 1m
            start_date = datetime(2024, 12, 1)
            end_date = datetime(2025, 1, 1)

        filename = (
            f"{args.frequency.replace('1', '')}{args.frequency[-1]}_{args.assets}_assets.parquet"
        )

        logger.info(f"Generating {filename}...")
        df = generate_ohlcv_data(
            start_date=start_date,
            end_date=end_date,
            frequency=args.frequency,
            num_assets=args.assets,
            seed=SEED,
        )

        save_fixture(df, filename, compression="snappy")


if __name__ == "__main__":
    main()
