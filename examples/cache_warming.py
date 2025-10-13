#!/usr/bin/env python3
"""
Cache Warming Example

Demonstrates pre-fetching data to warm the cache before backtesting.
Useful for large backtests with many symbols.

Benefits:
- Faster backtest execution (cache hits)
- Predictable performance
- Avoid API rate limits during backtest
"""

import asyncio

import pandas as pd

from rustybt.data.sources import CachedDataSource, DataSourceRegistry
from rustybt.utils.calendar_utils import get_calendar


async def warm_cache_for_symbols(
    symbols: list[str], start: pd.Timestamp, end: pd.Timestamp, frequency: str = "daily"
):
    """Pre-fetch and cache data for symbols.

    Args:
        symbols: List of ticker symbols
        start: Start date
        end: End date
        frequency: Data frequency ('daily', 'hourly', 'minute')
    """
    print(f"🔥 Warming cache for {len(symbols)} symbols...")
    print(f"   Period: {start.date()} to {end.date()}")
    print(f"   Frequency: {frequency}")

    # Create data source with caching
    source = DataSourceRegistry.get_source("yfinance")
    cached_source = CachedDataSource(adapter=source)

    # Fetch data for all symbols (will cache automatically)
    for i, symbol in enumerate(symbols, 1):
        try:
            print(f"   [{i}/{len(symbols)}] Fetching {symbol}...", end=" ", flush=True)

            df = await cached_source.fetch(
                symbols=[symbol], start=start, end=end, frequency=frequency
            )

            print(f"✓ ({len(df)} bars)")

        except Exception as e:
            print(f"✗ Error: {e}")

    # Print cache statistics
    stats = cached_source.get_stats()
    print("\n✅ Cache warming complete!")
    print(f"   Cache size: {stats['size_mb']:.2f} MB")
    print(f"   Entries: {stats['entries']}")


def warm_cache_for_next_trading_day(symbols: list[str], calendar_name: str = "NYSE"):
    """Pre-fetch data up to next trading day.

    Args:
        symbols: List of ticker symbols
        calendar_name: Trading calendar name ('NYSE', 'NASDAQ', etc.)
    """
    calendar = get_calendar(calendar_name)

    # Get next trading day
    today = pd.Timestamp.now()
    next_trading_day = calendar.next_open(today).date()

    print(f"🔥 Warming cache for next trading day: {next_trading_day}")

    # Fetch data from last year to next trading day
    start = pd.Timestamp(next_trading_day) - pd.Timedelta(days=365)
    end = pd.Timestamp(next_trading_day)

    asyncio.run(warm_cache_for_symbols(symbols, start, end, frequency="daily"))


def main():
    """Cache warming examples."""
    print("=" * 60)
    print("Cache Warming Examples")
    print("=" * 60)

    # Example 1: Warm cache for backtest period
    print("\n📍 Example 1: Backtest Period (2023)")
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
    start = pd.Timestamp("2023-01-01")
    end = pd.Timestamp("2023-12-31")

    asyncio.run(warm_cache_for_symbols(symbols, start, end, frequency="daily"))

    # Example 2: Warm cache for next trading day
    print("\n📍 Example 2: Next Trading Day")
    symbols = ["SPY", "QQQ", "IWM"]
    warm_cache_for_next_trading_day(symbols)

    # Example 3: Warm cache for intraday data
    print("\n📍 Example 3: Intraday Data (Last 30 Days)")
    symbols = ["AAPL", "TSLA"]
    start = pd.Timestamp.now() - pd.Timedelta(days=30)
    end = pd.Timestamp.now()

    asyncio.run(warm_cache_for_symbols(symbols, start, end, frequency="hourly"))

    print("\n" + "=" * 60)
    print("✅ All cache warming examples complete!")
    print("=" * 60)
    print("\nNow run your backtest - it should be much faster!")


if __name__ == "__main__":
    main()
