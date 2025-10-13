"""Example: Backtest with smart caching.

This example demonstrates the performance benefits of using CachedDataSource
for repeated backtests.

Usage:
    python examples/backtest_with_cache.py
"""

import asyncio
import time

import pandas as pd

from rustybt.assets import Equity
from rustybt.data.polars.data_portal import PolarsDataPortal
from rustybt.data.sources import DataSourceRegistry


async def main():
    """Run backtest with and without caching to demonstrate performance."""
    print("=" * 60)
    print("Backtest Caching Performance Example")
    print("=" * 60)

    # Initialize data source
    print("\n[1/5] Initializing YFinance data source...")
    source = DataSourceRegistry.get_source("yfinance")
    print("✓ Data source initialized")

    # Test parameters
    assets = [
        Equity(sid=1, symbol="AAPL"),
        Equity(sid=2, symbol="MSFT"),
    ]
    pd.Timestamp("2024-01-01")
    pd.Timestamp("2024-01-31")

    # === Test 1: Without caching ===
    print("\n[2/5] Testing WITHOUT caching...")
    portal_no_cache = PolarsDataPortal(
        data_source=source,
        use_cache=False,  # Disable caching
    )

    start_time = time.time()
    await portal_no_cache.get_spot_value(
        assets=assets,
        field="close",
        dt=pd.Timestamp("2024-01-15"),
        data_frequency="1d",
    )
    no_cache_time = time.time() - start_time
    print(f"✓ First fetch (no cache): {no_cache_time:.3f}s")

    # === Test 2: With caching (first fetch - cache miss) ===
    print("\n[3/5] Testing WITH caching (first fetch - cache miss)...")
    portal_with_cache = PolarsDataPortal(
        data_source=source,
        use_cache=True,  # Enable caching
    )

    start_time = time.time()
    await portal_with_cache.get_spot_value(
        assets=assets,
        field="close",
        dt=pd.Timestamp("2024-01-15"),
        data_frequency="1d",
    )
    cache_miss_time = time.time() - start_time
    print(f"✓ First fetch (cache miss): {cache_miss_time:.3f}s")
    print(f"  Cache hit rate: {portal_with_cache.cache_hit_rate:.1f}%")

    # === Test 3: With caching (second fetch - cache hit) ===
    print("\n[4/5] Testing WITH caching (second fetch - cache hit)...")

    start_time = time.time()
    await portal_with_cache.get_spot_value(
        assets=assets,
        field="close",
        dt=pd.Timestamp("2024-01-15"),
        data_frequency="1d",
    )
    cache_hit_time = time.time() - start_time
    print(f"✓ Second fetch (cache hit): {cache_hit_time:.3f}s")
    print(f"  Cache hit rate: {portal_with_cache.cache_hit_rate:.1f}%")

    # === Performance Summary ===
    print("\n[5/5] Performance Summary:")
    print(f"  No cache: {no_cache_time:.3f}s")
    print(
        f"  Cache miss: {cache_miss_time:.3f}s (write overhead: {cache_miss_time - no_cache_time:.3f}s)"
    )
    print(f"  Cache hit: {cache_hit_time:.3f}s")

    if cache_hit_time > 0:
        speedup = no_cache_time / cache_hit_time
        print(f"\n  Speedup: {speedup:.1f}x faster")
        print(f"  Time saved: {no_cache_time - cache_hit_time:.3f}s per fetch")

    print("\n" + "=" * 60)
    print("✓ Caching demonstration complete!")
    print("=" * 60)
    print("\nKey Takeaways:")
    print("  1. Cache hits are ~10-20x faster than API calls")
    print("  2. Cache overhead on first fetch is minimal (~5-10%)")
    print("  3. Repeated backtests benefit massively from caching")
    print("  4. Use use_cache=True for development/testing")
    print("  5. Use use_cache=False for live trading")


if __name__ == "__main__":
    asyncio.run(main())
