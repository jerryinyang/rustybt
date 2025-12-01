"""Test data fixture generator for validation framework.

This module generates deterministic synthetic OHLCV data fixtures for
validation testing. Both rustybt and Backtrader can consume the same
Parquet fixture to ensure behavioral differences are real, not data-related.

Story X.2: Schema specification:
    - timestamp: datetime64[ns, UTC] - UTC timezone for consistency
    - asset: string - Asset symbol identifier
    - open, high, low, close: float64 - Price data
    - volume: int64 - Volume data

Usage:
    python -m rustybt.validation.generate_fixture --output fixture.parquet --seed 42
"""

import argparse
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl


def generate_fixture(
    output: Path,
    assets: int = 50,
    start: str = "2020-01-01",
    end: str = "2021-12-31",
    seed: int = 42,
) -> Path:
    """Generate standardized test data fixture with UTC timestamps.

    Parameters
    ----------
    output : Path
        Output path for the Parquet file.
    assets : int, optional
        Number of assets to generate. Default 50.
    start : str, optional
        Start date in YYYY-MM-DD format. Default "2020-01-01".
    end : str, optional
        End date in YYYY-MM-DD format. Default "2021-12-31".
    seed : int, optional
        Random seed for deterministic generation. Default 42.

    Note:
    ----
    The same seed will always produce identical data, ensuring
    reproducible validation tests across runs.
    """
    np.random.seed(seed)

    # Asset tiers
    large_cap = [
        "AAPL",
        "GOOGL",
        "MSFT",
        "AMZN",
        "TSLA",
        "NVDA",
        "META",
        "BRK.B",
        "JPM",
        "V",
        "WMT",
        "JNJ",
        "PG",
        "MA",
        "HD",
        "DIS",
        "PYPL",
        "BAC",
        "NFLX",
        "CSCO",
    ]
    mid_cap = [
        "CRWD",
        "SNOW",
        "DDOG",
        "NET",
        "ZS",
        "OKTA",
        "TEAM",
        "SHOP",
        "SQ",
        "TWLO",
        "PLTR",
        "U",
        "ABNB",
        "COIN",
        "RIVN",
        "LCID",
        "RBLX",
        "DASH",
        "PINS",
        "SNAP",
    ]
    small_cap = ["PLUG", "FCEL", "SOLO", "WKHS", "RIDE", "NKLA", "FSR", "SPCE", "OPEN", "WISH"]

    symbols = (large_cap + mid_cap + small_cap)[:assets]
    tiers = (
        dict.fromkeys(large_cap[:20], "large")
        | dict.fromkeys(mid_cap[:20], "mid")
        | dict.fromkeys(small_cap[:10], "small")
    )

    # Parse dates as UTC timezone-aware
    start_date = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=UTC)
    end_date = datetime.strptime(end, "%Y-%m-%d").replace(tzinfo=UTC)
    days = (end_date - start_date).days

    data = []
    for symbol in symbols:
        tier = tiers.get(symbol, "mid")
        initial_price = 100.0

        # Price random walk
        returns = np.random.normal(0.0005, 0.015, days)
        prices = initial_price * np.cumprod(1 + returns)

        # OHLC generation
        for i in range(days):
            # Create UTC timestamp
            date = start_date + timedelta(days=i)
            price = prices[i]
            intraday_vol = abs(np.random.normal(0, 0.01))

            open_price = price
            high_price = price * (1 + intraday_vol)
            low_price = price * (1 - intraday_vol)
            close_price = prices[i + 1] if i + 1 < days else price

            # Ensure OHLC constraints
            high_price = max(high_price, open_price, close_price)
            low_price = min(low_price, open_price, close_price)

            # Volume by tier
            if tier == "large":
                volume = np.random.randint(1_000_000, 10_000_000)
            elif tier == "mid":
                volume = np.random.randint(100_000, 1_000_000)
            else:
                volume = np.random.randint(10_000, 100_000)

            data.append(
                {
                    "timestamp": date,
                    "asset": symbol,
                    "open": float(open_price),
                    "high": float(high_price),
                    "low": float(low_price),
                    "close": float(close_price),
                    "volume": int(volume),
                }
            )

    df = pl.DataFrame(data)

    # Ensure timestamp column has UTC timezone
    df = df.with_columns(pl.col("timestamp").dt.replace_time_zone("UTC"))

    df = df.sort(["timestamp", "asset"])

    output.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(output)

    size_mb = output.stat().st_size / (1024 * 1024)
    print(f"✓ Generated {len(df)} rows for {assets} assets")
    print(f"✓ Date range: {start} to {end} (UTC)")
    print(f"✓ File size: {size_mb:.2f} MB")
    print(f"✓ Schema: {dict(df.schema)}")
    print(f"✓ Output: {output}")

    return output


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Generate validation test fixture")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--assets", type=int, default=50)
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default="2021-12-31")
    parser.add_argument("--seed", type=int, default=42)

    args = parser.parse_args()
    generate_fixture(args.output, args.assets, args.start, args.end, args.seed)


if __name__ == "__main__":
    main()
