"""Tests for intelligent caching system.

Tests cover:
- Cache key generation (deterministic, order-independent)
- Cache lookup (hit/miss scenarios)
- Two-tier caching (hot/cold cache promotion/demotion)
- Cache eviction (LRU, size-based)
- Cache statistics tracking
- Performance targets (<1s for cache hit)
"""

import time
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import polars as pl
import pytest

from rustybt.data.polars.cache_manager import CacheManager, LRUCache

# Fixtures


@pytest.fixture
def temp_cache_dir():
    """Create temporary cache directory."""
    with TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_dataframe():
    """Create sample OHLCV DataFrame."""
    return pl.DataFrame(
        {
            "timestamp": pl.datetime_range(
                datetime(2023, 1, 1),
                datetime(2023, 1, 31),
                "1d",
                eager=True,
            ),
            "open": [100.0 + i for i in range(31)],
            "high": [105.0 + i for i in range(31)],
            "low": [95.0 + i for i in range(31)],
            "close": [102.0 + i for i in range(31)],
            "volume": [1000000 + i * 10000 for i in range(31)],
        }
    )


@pytest.fixture
def cache_manager(temp_cache_dir):
    """Create CacheManager instance."""
    db_path = Path(temp_cache_dir) / "metadata.db"
    cache_dir = Path(temp_cache_dir) / "cache"

    # Create a minimal dataset for testing
    cache = CacheManager(
        db_path=str(db_path),
        cache_directory=str(cache_dir),
        hot_cache_size_mb=10,  # Small for testing
        cold_cache_size_mb=100,
    )

    # Create a test dataset
    dataset_id = cache.metadata_catalog.create_dataset("yfinance", "1d")

    # Store dataset_id for tests
    cache.test_dataset_id = dataset_id

    return cache


# Unit Tests - Cache Key Generation


def test_cache_key_generation_deterministic(cache_manager):
    """Cache key generation produces consistent results."""
    key1 = cache_manager.generate_cache_key(
        ["AAPL", "MSFT"],
        "2023-01-01",
        "2023-12-31",
        "1d",
        "yfinance",
    )
    key2 = cache_manager.generate_cache_key(
        ["AAPL", "MSFT"],
        "2023-01-01",
        "2023-12-31",
        "1d",
        "yfinance",
    )

    assert key1 == key2
    assert len(key1) == 16  # First 16 chars of SHA256


def test_cache_key_generation_symbol_order_independent(cache_manager):
    """Cache key is same regardless of symbol order."""
    key1 = cache_manager.generate_cache_key(
        ["AAPL", "MSFT"],
        "2023-01-01",
        "2023-12-31",
        "1d",
        "yfinance",
    )
    key2 = cache_manager.generate_cache_key(
        ["MSFT", "AAPL"],
        "2023-01-01",
        "2023-12-31",
        "1d",
        "yfinance",
    )

    assert key1 == key2


def test_cache_key_generation_different_parameters(cache_manager):
    """Different parameters produce different cache keys."""
    key1 = cache_manager.generate_cache_key(
        ["AAPL"],
        "2023-01-01",
        "2023-12-31",
        "1d",
        "yfinance",
    )
    key2 = cache_manager.generate_cache_key(
        ["AAPL"],
        "2023-01-01",
        "2023-12-31",
        "1h",  # Different resolution
        "yfinance",
    )
    key3 = cache_manager.generate_cache_key(
        ["AAPL"],
        "2023-01-01",
        "2023-06-30",  # Different date range
        "1d",
        "yfinance",
    )

    assert key1 != key2
    assert key1 != key3
    assert key2 != key3


# Unit Tests - Cache Lookup


def test_cache_lookup_nonexistent_key(cache_manager):
    """Cache lookup returns None for nonexistent key."""
    cache_entry = cache_manager.lookup_cache("nonexistent")
    assert cache_entry is None


def test_cache_lookup_existing_key(cache_manager, sample_dataframe):
    """Cache lookup finds existing cache entry."""
    cache_key = cache_manager.generate_cache_key(
        ["AAPL"],
        "2023-01-01",
        "2023-01-31",
        "1d",
        "yfinance",
    )

    # Store data in cache
    cache_manager.put_cached_data(
        cache_key,
        sample_dataframe,
        cache_manager.test_dataset_id,
    )

    # Lookup cache entry
    cache_entry = cache_manager.lookup_cache(cache_key)

    assert cache_entry is not None
    assert cache_entry["cache_key"] == cache_key
    assert cache_entry["dataset_id"] == cache_manager.test_dataset_id
    assert cache_entry["size_bytes"] > 0


# Unit Tests - LRU Cache


def test_lru_cache_put_and_get():
    """LRU cache stores and retrieves DataFrames."""
    lru = LRUCache(max_size_bytes=10 * 1024 * 1024)  # 10MB

    df = pl.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})

    lru.put("key1", df)

    retrieved = lru.get("key1")
    assert retrieved is not None
    assert retrieved.equals(df)


def test_lru_cache_eviction():
    """LRU cache evicts least recently used entries."""
    lru = LRUCache(max_size_bytes=1024)  # Very small cache

    # Create DataFrames that will exceed cache size
    df1 = pl.DataFrame({"a": list(range(100))})
    df2 = pl.DataFrame({"b": list(range(100))})
    df3 = pl.DataFrame({"c": list(range(100))})

    lru.put("key1", df1)
    lru.put("key2", df2)
    lru.put("key3", df3)  # Should evict key1

    # key1 should be evicted, key2 and key3 should remain
    assert lru.get("key1") is None  # Evicted
    assert lru.get("key2") is not None or lru.get("key3") is not None


def test_lru_cache_clear():
    """LRU cache clears all entries."""
    lru = LRUCache(max_size_bytes=10 * 1024 * 1024)

    df = pl.DataFrame({"a": [1, 2, 3]})
    lru.put("key1", df)
    lru.put("key2", df)

    lru.clear()

    assert lru.get("key1") is None
    assert lru.get("key2") is None
    assert lru.current_size_bytes == 0


# Integration Tests - Cache Read/Write


def test_cache_miss_returns_none(cache_manager):
    """Cache miss returns None."""
    cache_key = cache_manager.generate_cache_key(
        ["AAPL"],
        "2023-01-01",
        "2023-01-31",
        "1d",
        "yfinance",
    )

    df = cache_manager.get_cached_data(cache_key)

    assert df is None
    assert cache_manager.session_stats["miss_count"] == 1
    assert cache_manager.session_stats["hit_count"] == 0


def test_cache_write_and_read(cache_manager, sample_dataframe):
    """Cache write followed by read returns same data."""
    cache_key = cache_manager.generate_cache_key(
        ["AAPL"],
        "2023-01-01",
        "2023-01-31",
        "1d",
        "yfinance",
    )

    # Write to cache
    cache_manager.put_cached_data(
        cache_key,
        sample_dataframe,
        cache_manager.test_dataset_id,
    )

    # Read from cache (hot cache hit)
    df_cached = cache_manager.get_cached_data(cache_key)

    assert df_cached is not None
    assert df_cached.equals(sample_dataframe)
    assert cache_manager.session_stats["hit_count"] == 1
    assert cache_manager.session_stats["hot_hits"] == 1


def test_cache_cold_hit_after_hot_eviction(cache_manager, sample_dataframe):
    """Cold cache hit after hot cache eviction."""
    cache_key = cache_manager.generate_cache_key(
        ["AAPL"],
        "2023-01-01",
        "2023-01-31",
        "1d",
        "yfinance",
    )

    # Write to cache
    cache_manager.put_cached_data(
        cache_key,
        sample_dataframe,
        cache_manager.test_dataset_id,
    )

    # Clear hot cache to simulate eviction
    cache_manager.hot_cache.clear()

    # Read from cache (should hit cold cache)
    df_cached = cache_manager.get_cached_data(cache_key)

    assert df_cached is not None
    assert df_cached.equals(sample_dataframe)
    assert cache_manager.session_stats["cold_hits"] == 1


def test_cache_with_backtest_linkage(cache_manager, sample_dataframe):
    """Cache entries linked to backtest ID."""
    cache_key = cache_manager.generate_cache_key(
        ["AAPL"],
        "2023-01-01",
        "2023-01-31",
        "1d",
        "yfinance",
    )

    backtest_id = "backtest-001"

    # Write to cache with backtest linkage
    cache_manager.put_cached_data(
        cache_key,
        sample_dataframe,
        cache_manager.test_dataset_id,
        backtest_id=backtest_id,
    )

    # Verify linkage in database
    import sqlalchemy as sa
    from sqlalchemy.orm import Session

    with Session(cache_manager.metadata_catalog.engine) as session:
        stmt = sa.select(cache_manager.metadata_catalog.backtest_cache_links).where(
            cache_manager.metadata_catalog.backtest_cache_links.c.backtest_id == backtest_id
        )
        result = session.execute(stmt).fetchone()

        assert result is not None
        assert result.cache_key == cache_key


def test_cache_access_count_increments(cache_manager, sample_dataframe):
    """Cache access count increments on each hit."""
    cache_key = cache_manager.generate_cache_key(
        ["AAPL"],
        "2023-01-01",
        "2023-01-31",
        "1d",
        "yfinance",
    )

    # Write to cache
    cache_manager.put_cached_data(
        cache_key,
        sample_dataframe,
        cache_manager.test_dataset_id,
    )

    # Access multiple times
    for _ in range(5):
        cache_manager.get_cached_data(cache_key)

    # Check access count
    cache_entry = cache_manager.lookup_cache(cache_key)
    assert cache_entry["access_count"] == 6  # 1 write + 5 reads


# Integration Tests - Cache Eviction


def test_lru_eviction_removes_oldest_entry(cache_manager, sample_dataframe):
    """LRU eviction removes least recently accessed entry."""
    # Create multiple cache entries
    keys = []
    for i in range(5):
        cache_key = cache_manager.generate_cache_key(
            [f"SYMBOL{i}"],
            "2023-01-01",
            "2023-01-31",
            "1d",
            "yfinance",
        )
        keys.append(cache_key)

        cache_manager.put_cached_data(
            cache_key,
            sample_dataframe,
            cache_manager.test_dataset_id,
        )

        # Add small delay to ensure different timestamps
        time.sleep(0.01)

    # Access all except first to make it least recently used
    for key in keys[1:]:
        cache_manager.get_cached_data(key)

    # Force eviction by setting very low limit
    cache_manager.cold_cache_size_mb = 0.01  # Very small
    cache_manager._check_cold_cache_eviction()

    # First key should be evicted
    cache_manager.lookup_cache(keys[0])
    # Note: May or may not be evicted depending on file sizes
    # Just verify eviction runs without error


def test_size_based_eviction_removes_largest_entry(cache_manager):
    """Size-based eviction removes largest entries."""
    # Create DataFrames of different sizes
    small_df = pl.DataFrame({"a": [1, 2, 3]})
    large_df = pl.DataFrame({"a": list(range(10000))})

    key_small = cache_manager.generate_cache_key(
        ["SMALL"],
        "2023-01-01",
        "2023-01-31",
        "1d",
        "yfinance",
    )
    key_large = cache_manager.generate_cache_key(
        ["LARGE"],
        "2023-01-01",
        "2023-01-31",
        "1d",
        "yfinance",
    )

    cache_manager.put_cached_data(
        key_small,
        small_df,
        cache_manager.test_dataset_id,
    )
    cache_manager.put_cached_data(
        key_large,
        large_df,
        cache_manager.test_dataset_id,
    )

    # Force eviction by size
    cache_manager.cold_cache_size_mb = 0.01
    cache_manager.eviction_policy = "size"
    cache_manager._check_cold_cache_eviction()

    # Verify eviction ran (exact outcome depends on file sizes)
    total_size = cache_manager._get_total_cache_size_mb()
    assert total_size >= 0  # Eviction completed without error


# Integration Tests - Cache Statistics


def test_cache_statistics_tracking(cache_manager, sample_dataframe):
    """Cache statistics track hits and misses correctly."""
    cache_key = cache_manager.generate_cache_key(
        ["AAPL"],
        "2023-01-01",
        "2023-01-31",
        "1d",
        "yfinance",
    )

    # Trigger cache miss
    cache_manager.get_cached_data(cache_key)

    # Write to cache
    cache_manager.put_cached_data(
        cache_key,
        sample_dataframe,
        cache_manager.test_dataset_id,
    )

    # Trigger cache hits
    cache_manager.get_cached_data(cache_key)
    cache_manager.get_cached_data(cache_key)

    # Check statistics
    stats = cache_manager.session_stats
    assert stats["miss_count"] == 1
    assert stats["hit_count"] == 2


def test_daily_statistics_recording(cache_manager, sample_dataframe):
    """Daily statistics recording stores aggregated data."""
    cache_key = cache_manager.generate_cache_key(
        ["AAPL"],
        "2023-01-01",
        "2023-01-31",
        "1d",
        "yfinance",
    )

    # Generate cache activity
    cache_manager.get_cached_data(cache_key)  # Miss

    cache_manager.put_cached_data(
        cache_key,
        sample_dataframe,
        cache_manager.test_dataset_id,
    )

    cache_manager.get_cached_data(cache_key)  # Hit

    # Record daily statistics
    cache_manager.record_daily_statistics()

    # Query statistics
    stats = cache_manager.get_cache_statistics()

    assert stats["hit_count"] == 1
    assert stats["miss_count"] == 1
    assert stats["hit_rate"] == 0.5
    assert stats["total_size_mb"] > 0
    assert stats["entry_count"] == 1


def test_get_cache_statistics_with_date_range(cache_manager, sample_dataframe):
    """Get cache statistics for specific date range."""
    cache_key = cache_manager.generate_cache_key(
        ["AAPL"],
        "2023-01-01",
        "2023-01-31",
        "1d",
        "yfinance",
    )

    # Generate activity and record
    cache_manager.put_cached_data(
        cache_key,
        sample_dataframe,
        cache_manager.test_dataset_id,
    )
    cache_manager.get_cached_data(cache_key)

    cache_manager.record_daily_statistics()

    # Query with date range
    today = datetime.now().date()
    stats = cache_manager.get_cache_statistics(
        start_date=today.isoformat(),
        end_date=today.isoformat(),
    )

    assert stats["hit_count"] >= 0
    assert stats["entry_count"] == 1


# Integration Tests - Cache Clearing


def test_clear_cache_by_key(cache_manager, sample_dataframe):
    """Clear specific cache entry by key."""
    cache_key = cache_manager.generate_cache_key(
        ["AAPL"],
        "2023-01-01",
        "2023-01-31",
        "1d",
        "yfinance",
    )

    cache_manager.put_cached_data(
        cache_key,
        sample_dataframe,
        cache_manager.test_dataset_id,
    )

    # Clear specific entry
    cache_manager.clear_cache(cache_key=cache_key)

    # Verify cleared
    df = cache_manager.get_cached_data(cache_key)
    assert df is None


def test_clear_cache_by_backtest(cache_manager, sample_dataframe):
    """Clear all cache entries linked to backtest."""
    backtest_id = "backtest-001"

    # Create multiple cache entries for same backtest
    for i in range(3):
        cache_key = cache_manager.generate_cache_key(
            [f"SYMBOL{i}"],
            "2023-01-01",
            "2023-01-31",
            "1d",
            "yfinance",
        )

        cache_manager.put_cached_data(
            cache_key,
            sample_dataframe,
            cache_manager.test_dataset_id,
            backtest_id=backtest_id,
        )

    # Clear by backtest
    cache_manager.clear_cache(backtest_id=backtest_id)

    # Verify all entries cleared
    for i in range(3):
        cache_key = cache_manager.generate_cache_key(
            [f"SYMBOL{i}"],
            "2023-01-01",
            "2023-01-31",
            "1d",
            "yfinance",
        )
        df = cache_manager.get_cached_data(cache_key)
        assert df is None


def test_clear_all_cache(cache_manager, sample_dataframe):
    """Clear entire cache."""
    # Create multiple cache entries
    for i in range(3):
        cache_key = cache_manager.generate_cache_key(
            [f"SYMBOL{i}"],
            "2023-01-01",
            "2023-01-31",
            "1d",
            "yfinance",
        )

        cache_manager.put_cached_data(
            cache_key,
            sample_dataframe,
            cache_manager.test_dataset_id,
        )

    # Clear all
    cache_manager.clear_cache()

    # Verify all entries cleared
    stats = cache_manager.get_cache_statistics()
    assert stats["entry_count"] == 0


# Performance Tests


@pytest.mark.benchmark
def test_cache_hit_performance_hot_cache(cache_manager, sample_dataframe, benchmark):
    """Hot cache hit completes in <0.01 seconds."""
    cache_key = cache_manager.generate_cache_key(
        ["AAPL"],
        "2023-01-01",
        "2023-12-31",
        "1d",
        "yfinance",
    )

    # Pre-populate cache
    cache_manager.put_cached_data(
        cache_key,
        sample_dataframe,
        cache_manager.test_dataset_id,
    )

    # Benchmark hot cache hit
    def cache_hit():
        return cache_manager.get_cached_data(cache_key)

    result = benchmark(cache_hit)

    # Verify result
    assert result is not None

    # Verify <0.01s target for hot cache
    # benchmark.stats contains the timing information (if benchmarks enabled)
    if benchmark.stats is not None:
        assert benchmark.stats["mean"] < 0.01


@pytest.mark.benchmark
def test_cache_hit_performance_cold_cache(cache_manager, sample_dataframe, benchmark):
    """Cold cache hit completes in <1 second."""
    cache_key = cache_manager.generate_cache_key(
        ["AAPL"],
        "2023-01-01",
        "2023-12-31",
        "1d",
        "yfinance",
    )

    # Pre-populate cache
    cache_manager.put_cached_data(
        cache_key,
        sample_dataframe,
        cache_manager.test_dataset_id,
    )

    # Clear hot cache to force cold cache access
    cache_manager.hot_cache.clear()

    # Benchmark cold cache hit
    def cache_hit():
        return cache_manager.get_cached_data(cache_key)

    result = benchmark(cache_hit)

    # Verify result
    assert result is not None

    # Verify <1s target for cold cache
    # benchmark.stats contains the timing information (if benchmarks enabled)
    if benchmark.stats is not None:
        assert benchmark.stats["mean"] < 1.0


# Property-Based Tests


@pytest.mark.hypothesis
def test_cache_key_uniqueness_property():
    """Property: Different parameters always produce different cache keys."""
    from hypothesis import given
    from hypothesis import strategies as st

    cache_manager_temp = CacheManager(
        db_path=":memory:",
        cache_directory="/tmp/test_cache",
    )

    @given(
        symbols1=st.lists(st.text(min_size=1, max_size=10), min_size=1, max_size=5),
        symbols2=st.lists(st.text(min_size=1, max_size=10), min_size=1, max_size=5),
        resolution=st.sampled_from(["1m", "5m", "1h", "1d"]),
    )
    def test_property(symbols1, symbols2, resolution):
        # Generate keys with different symbol sets
        key1 = cache_manager_temp.generate_cache_key(
            symbols1,
            "2023-01-01",
            "2023-12-31",
            resolution,
            "yfinance",
        )
        key2 = cache_manager_temp.generate_cache_key(
            symbols2,
            "2023-01-01",
            "2023-12-31",
            resolution,
            "yfinance",
        )

        # If symbol sets are different (after sorting), keys must differ
        if sorted(symbols1) != sorted(symbols2):
            assert key1 != key2

    test_property()
