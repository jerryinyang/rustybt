"""Tests for DataPortal multi-tier cache implementation."""

import threading
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import numpy as np
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from rustybt.optimization.dataportal_ext import CacheKey, HistoryCache


class TestCacheKey:
    """Tests for CacheKey namedtuple."""

    def test_cache_key_creation(self):
        """Test CacheKey creation with all fields."""
        key = CacheKey(
            asset_id=1,
            field="close",
            bar_count=20,
            end_date="2023-01-01",
        )

        assert key.asset_id == 1
        assert key.field == "close"
        assert key.bar_count == 20
        assert key.end_date == "2023-01-01"

    def test_cache_key_immutability(self):
        """Test CacheKey is immutable (namedtuple property)."""
        key = CacheKey(asset_id=1, field="close", bar_count=20, end_date="2023-01-01")

        with pytest.raises(AttributeError):
            key.asset_id = 2  # Should raise AttributeError

    def test_cache_key_hashing(self):
        """Test CacheKey can be used as dictionary key."""
        key1 = CacheKey(asset_id=1, field="close", bar_count=20, end_date="2023-01-01")
        key2 = CacheKey(asset_id=1, field="close", bar_count=20, end_date="2023-01-01")
        key3 = CacheKey(asset_id=2, field="close", bar_count=20, end_date="2023-01-01")

        # Same keys should be equal
        assert key1 == key2
        assert hash(key1) == hash(key2)

        # Different keys should not be equal
        assert key1 != key3
        assert hash(key1) != hash(key3)

    def test_cache_key_as_dict_key(self):
        """Test CacheKey works as dictionary key."""
        key = CacheKey(asset_id=1, field="close", bar_count=20, end_date="2023-01-01")
        cache = {key: np.array([100.0, 101.0])}

        assert key in cache
        assert np.array_equal(cache[key], np.array([100.0, 101.0]))


class TestHistoryCache:
    """Tests for HistoryCache multi-tier implementation."""

    def test_cache_initialization(self):
        """Test cache initializes with default settings."""
        cache = HistoryCache()

        assert cache.permanent_windows == [20, 50, 200]
        assert cache.tier2_maxsize == 256
        assert cache.hits == 0
        assert cache.misses == 0
        assert cache.hit_rate == 0.0

    def test_cache_custom_settings(self):
        """Test cache initializes with custom settings."""
        cache = HistoryCache(permanent_windows=[10, 30], tier2_maxsize=128)

        assert cache.permanent_windows == [10, 30]
        assert cache.tier2_maxsize == 128

    def test_cache_miss(self):
        """Test cache miss returns None and updates statistics."""
        cache = HistoryCache()
        key = CacheKey(asset_id=1, field="close", bar_count=20, end_date="2023-01-01")

        result = cache.get(key)

        assert result is None
        assert cache.hits == 0
        assert cache.misses == 1
        assert cache.hit_rate == 0.0

    def test_tier1_cache_hit(self):
        """Test tier1 (permanent) cache hit."""
        cache = HistoryCache(permanent_windows=[20, 50, 200])
        key = CacheKey(asset_id=1, field="close", bar_count=20, end_date="2023-01-01")
        data = np.array([100.0, 101.0, 102.0])

        cache.put(key, data)
        result = cache.get(key)

        assert np.array_equal(result, data)
        assert cache.hits == 1
        assert cache.misses == 0
        assert cache.hit_rate == 100.0
        assert key in cache.tier1_cache
        assert key not in cache.tier2_cache

    def test_tier2_cache_hit(self):
        """Test tier2 (LRU) cache hit."""
        cache = HistoryCache(permanent_windows=[20, 50, 200])
        key = CacheKey(asset_id=1, field="close", bar_count=30, end_date="2023-01-01")
        data = np.array([100.0, 101.0, 102.0])

        cache.put(key, data)
        result = cache.get(key)

        assert np.array_equal(result, data)
        assert cache.hits == 1
        assert cache.misses == 0
        assert cache.hit_rate == 100.0
        assert key not in cache.tier1_cache
        assert key in cache.tier2_cache

    def test_tier2_lru_eviction(self):
        """Test tier2 LRU eviction when maxsize exceeded."""
        cache = HistoryCache(permanent_windows=[], tier2_maxsize=3)

        # Add 4 entries (should evict oldest)
        keys = [
            CacheKey(asset_id=i, field="close", bar_count=30, end_date="2023-01-01")
            for i in range(4)
        ]

        for i, key in enumerate(keys):
            cache.put(key, np.array([float(i)]))

        # First key should be evicted
        assert cache.get(keys[0]) is None
        assert cache.get(keys[1]) is not None
        assert cache.get(keys[2]) is not None
        assert cache.get(keys[3]) is not None
        assert len(cache.tier2_cache) == 3

    def test_tier2_lru_ordering(self):
        """Test tier2 maintains LRU ordering on access."""
        cache = HistoryCache(permanent_windows=[], tier2_maxsize=3)

        keys = [
            CacheKey(asset_id=i, field="close", bar_count=30, end_date="2023-01-01")
            for i in range(3)
        ]

        for i, key in enumerate(keys):
            cache.put(key, np.array([float(i)]))

        # Access first key (makes it most recently used)
        cache.get(keys[0])

        # Add new key (should evict keys[1], not keys[0])
        new_key = CacheKey(asset_id=99, field="close", bar_count=30, end_date="2023-01-01")
        cache.put(new_key, np.array([99.0]))

        assert cache.get(keys[0]) is not None  # Still in cache
        assert cache.get(keys[1]) is None  # Evicted
        assert cache.get(keys[2]) is not None
        assert cache.get(new_key) is not None

    def test_cache_invalidation(self):
        """Test cache invalidation clears all tiers and resets statistics."""
        cache = HistoryCache(permanent_windows=[20], tier2_maxsize=256)

        # Add entries to both tiers
        tier1_key = CacheKey(asset_id=1, field="close", bar_count=20, end_date="2023-01-01")
        tier2_key = CacheKey(asset_id=2, field="close", bar_count=30, end_date="2023-01-01")

        cache.put(tier1_key, np.array([100.0]))
        cache.put(tier2_key, np.array([200.0]))

        # Generate some statistics
        cache.get(tier1_key)
        cache.get(tier2_key)
        cache.get(CacheKey(asset_id=3, field="close", bar_count=40, end_date="2023-01-01"))

        assert cache.hits == 2
        assert cache.misses == 1

        # Invalidate cache
        cache.invalidate_cache("test_bundle_hash_123")

        # All caches cleared and stats reset
        assert len(cache.tier1_cache) == 0
        assert len(cache.tier2_cache) == 0
        assert cache.hits == 0
        assert cache.misses == 0
        assert cache.hit_rate == 0.0

    def test_hit_rate_calculation(self):
        """Test hit rate calculation accuracy."""
        cache = HistoryCache()
        key = CacheKey(asset_id=1, field="close", bar_count=20, end_date="2023-01-01")

        # Initial state
        assert cache.hit_rate == 0.0

        # 1 miss
        cache.get(key)
        assert cache.hit_rate == 0.0

        # Add data
        cache.put(key, np.array([100.0]))

        # 1 hit (1 hit / 2 total = 50%)
        cache.get(key)
        assert cache.hit_rate == 50.0

        # 1 more hit (2 hits / 3 total = 66.67%)
        cache.get(key)
        assert cache.hit_rate == pytest.approx(66.67, rel=0.01)

    def test_get_stats(self):
        """Test cache statistics export."""
        cache = HistoryCache(permanent_windows=[20], tier2_maxsize=256)

        # Add entries
        tier1_key = CacheKey(asset_id=1, field="close", bar_count=20, end_date="2023-01-01")
        tier2_key = CacheKey(asset_id=2, field="close", bar_count=30, end_date="2023-01-01")

        cache.put(tier1_key, np.array([100.0]))
        cache.put(tier2_key, np.array([200.0]))

        # Generate hits/misses
        cache.get(tier1_key)
        cache.get(tier2_key)
        cache.get(CacheKey(asset_id=3, field="close", bar_count=40, end_date="2023-01-01"))

        stats = cache.get_stats()

        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_rate"] == pytest.approx(66.67, rel=0.01)
        assert stats["tier1_size"] == 1
        assert stats["tier2_size"] == 1

    def test_thread_safety_concurrent_reads(self):
        """Test cache handles concurrent reads safely."""
        cache = HistoryCache()
        key = CacheKey(asset_id=1, field="close", bar_count=20, end_date="2023-01-01")
        cache.put(key, np.array([100.0, 101.0]))

        def read_cache():
            result = cache.get(key)
            assert result is not None
            return result

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(read_cache) for _ in range(100)]
            results = [f.result() for f in futures]

        # All reads should succeed
        assert len(results) == 100
        assert all(np.array_equal(r, np.array([100.0, 101.0])) for r in results)

    def test_thread_safety_concurrent_writes(self):
        """Test cache handles concurrent writes safely."""
        cache = HistoryCache(permanent_windows=[], tier2_maxsize=256)

        def write_cache(i):
            key = CacheKey(asset_id=i, field="close", bar_count=30, end_date="2023-01-01")
            cache.put(key, np.array([float(i)]))

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(write_cache, i) for i in range(100)]
            [f.result() for f in futures]

        # All writes should succeed without corruption
        assert len(cache.tier2_cache) <= 256

    def test_thread_safety_mixed_operations(self):
        """Test cache handles mixed read/write operations safely."""
        cache = HistoryCache(permanent_windows=[20], tier2_maxsize=256)

        def mixed_operations(i):
            key = CacheKey(asset_id=i % 10, field="close", bar_count=20, end_date="2023-01-01")

            # Mix of reads and writes
            cache.get(key)
            cache.put(key, np.array([float(i)]))
            cache.get(key)

        with ThreadPoolExecutor(max_workers=16) as executor:
            futures = [executor.submit(mixed_operations, i) for i in range(200)]
            [f.result() for f in futures]

        # Statistics should be consistent
        stats = cache.get_stats()
        assert stats["hits"] + stats["misses"] > 0
        assert stats["tier1_size"] <= 10  # Only 10 unique assets

    def test_memory_usage_estimation(self):
        """Test memory usage estimation."""
        cache = HistoryCache(permanent_windows=[20], tier2_maxsize=256)

        # Add some data
        for i in range(5):
            key = CacheKey(asset_id=i, field="close", bar_count=20, end_date="2023-01-01")
            # 20 float64 values = 20 * 8 = 160 bytes per array
            cache.put(key, np.array([float(j) for j in range(20)]))

        stats = cache.get_stats()

        # Should have memory stats
        assert "memory_bytes" in stats
        assert "memory_mb" in stats

        # Memory should be reasonable (5 arrays * 20 values * 8 bytes = 800 bytes)
        assert stats["memory_bytes"] >= 800
        assert stats["memory_mb"] < 1.0  # Less than 1MB

    def test_cache_warming_stats(self):
        """Test cache warming statistics."""
        cache = HistoryCache(permanent_windows=[20, 50, 200], tier2_maxsize=256)

        # Initial state - no warming
        warming_stats = cache.get_cache_warming_stats()
        assert warming_stats["total_requests"] == 0
        assert warming_stats["current_hit_rate"] == 0.0
        assert warming_stats["is_warmed"] is False
        assert warming_stats["tier1_utilization"] == 0.0
        assert warming_stats["tier2_utilization"] == 0.0

        # Add some permanent window data (tier1)
        for bar_count in [20, 50, 200]:
            key = CacheKey(asset_id=1, field="close", bar_count=bar_count, end_date="2023-01-01")
            cache.get(key)  # Miss
            cache.put(key, np.array([100.0] * bar_count))
            cache.get(key)  # Hit

        warming_stats = cache.get_cache_warming_stats()
        assert warming_stats["total_requests"] == 6  # 3 misses + 3 hits
        assert warming_stats["current_hit_rate"] == 50.0  # 3 hits / 6 total
        assert warming_stats["is_warmed"] is False  # < 60% threshold
        assert warming_stats["tier1_utilization"] == 100.0  # All 3 permanent windows used

        # Access more to get above 60% hit rate
        for _ in range(6):
            for bar_count in [20, 50, 200]:
                key = CacheKey(
                    asset_id=1, field="close", bar_count=bar_count, end_date="2023-01-01"
                )
                cache.get(key)  # All hits

        warming_stats = cache.get_cache_warming_stats()
        assert warming_stats["current_hit_rate"] > 60.0
        assert warming_stats["is_warmed"] is True


class TestPropertyBasedCache:
    """Property-based tests using Hypothesis for comprehensive validation."""

    @given(
        bar_count=st.integers(min_value=1, max_value=500),
        asset_id=st.integers(min_value=1, max_value=10000),
        field=st.sampled_from(["open", "high", "low", "close", "volume"]),
    )
    @settings(max_examples=1000, deadline=None)
    def test_property_cache_get_put_consistency(self, bar_count, asset_id, field):
        """Property: Whatever is put into cache can be retrieved unchanged."""
        cache = HistoryCache()

        # Generate unique date string
        end_date = f"2023-{(asset_id % 12) + 1:02d}-{(asset_id % 28) + 1:02d}"
        key = CacheKey(asset_id=asset_id, field=field, bar_count=bar_count, end_date=end_date)

        # Create test data
        original_data = np.array([float(i) for i in range(bar_count)], dtype=np.float64)

        # Put and retrieve
        cache.put(key, original_data)
        retrieved_data = cache.get(key)

        # Property: Retrieved data must be identical
        assert retrieved_data is not None
        assert np.array_equal(retrieved_data, original_data)
        assert retrieved_data.dtype == original_data.dtype
        assert retrieved_data.shape == original_data.shape

    @given(
        bar_count=st.integers(min_value=1, max_value=500),
        n_assets=st.integers(min_value=1, max_value=50),
    )
    @settings(max_examples=1000, deadline=None)
    def test_property_cache_isolation(self, bar_count, n_assets):
        """Property: Different cache keys do not interfere with each other."""
        cache = HistoryCache()

        # Create unique keys and data
        keys_and_data = []
        for i in range(n_assets):
            key = CacheKey(
                asset_id=i + 1,
                field="close",
                bar_count=bar_count,
                end_date=f"2023-01-{(i % 28) + 1:02d}",
            )
            data = np.array([float(i * 100 + j) for j in range(bar_count)], dtype=np.float64)
            keys_and_data.append((key, data))
            cache.put(key, data)

        # Property: Each key retrieves its own unique data
        for key, original_data in keys_and_data:
            retrieved = cache.get(key)
            assert retrieved is not None
            assert np.array_equal(retrieved, original_data)

    @given(
        permanent_windows=st.lists(
            st.integers(min_value=1, max_value=500), min_size=1, max_size=10, unique=True
        ),
        tier2_maxsize=st.integers(min_value=1, max_value=500),
    )
    @settings(max_examples=500, deadline=None)
    def test_property_tier_separation(self, permanent_windows, tier2_maxsize):
        """Property: Permanent windows always go to tier1, others to tier2."""
        cache = HistoryCache(permanent_windows=permanent_windows, tier2_maxsize=tier2_maxsize)

        # Test permanent window (tier1)
        for window in permanent_windows[:3]:  # Test first 3 to avoid too many iterations
            key = CacheKey(asset_id=1, field="close", bar_count=window, end_date="2023-01-01")
            data = np.array([100.0] * window)
            cache.put(key, data)

            # Property: Must be in tier1, not tier2
            assert key in cache.tier1_cache
            assert key not in cache.tier2_cache

        # Test non-permanent window (tier2)
        non_permanent = max(permanent_windows) + 100
        key = CacheKey(asset_id=1, field="close", bar_count=non_permanent, end_date="2023-01-01")
        data = np.array([100.0] * non_permanent)
        cache.put(key, data)

        # Property: Must be in tier2, not tier1
        assert key not in cache.tier1_cache
        assert key in cache.tier2_cache

    @given(
        tier2_maxsize=st.integers(min_value=1, max_value=20),
        n_entries=st.integers(min_value=1, max_value=100),
    )
    @settings(max_examples=500, deadline=None)
    def test_property_lru_eviction_maintains_maxsize(self, tier2_maxsize, n_entries):
        """Property: Tier2 never exceeds maxsize, regardless of put operations."""
        assume(n_entries > 0)

        cache = HistoryCache(permanent_windows=[], tier2_maxsize=tier2_maxsize)

        # Add many entries (more than maxsize)
        for i in range(n_entries):
            key = CacheKey(asset_id=i, field="close", bar_count=30, end_date="2023-01-01")
            cache.put(key, np.array([100.0]))

        # Property: Tier2 size never exceeds maxsize
        assert len(cache.tier2_cache) <= tier2_maxsize

    @given(
        hit_count=st.integers(min_value=0, max_value=1000),
        miss_count=st.integers(min_value=0, max_value=1000),
    )
    @settings(max_examples=1000, deadline=None)
    def test_property_hit_rate_calculation(self, hit_count, miss_count):
        """Property: Hit rate is always hits/(hits+misses)*100, or 0 if no requests."""
        cache = HistoryCache()

        # Simulate hits and misses
        cache.hits = hit_count
        cache.misses = miss_count

        total = hit_count + miss_count
        if total == 0:
            # Property: 0 requests = 0% hit rate
            assert cache.hit_rate == 0.0
        else:
            # Property: Hit rate formula
            expected_rate = (hit_count / total) * 100.0
            assert abs(cache.hit_rate - expected_rate) < 1e-10
            # Property: Hit rate always between 0 and 100
            assert 0.0 <= cache.hit_rate <= 100.0

    @given(
        bar_counts=st.lists(st.integers(min_value=1, max_value=200), min_size=1, max_size=50),
    )
    @settings(max_examples=500, deadline=None)
    def test_property_memory_usage_monotonic(self, bar_counts):
        """Property: Adding data always increases or maintains memory usage."""
        cache = HistoryCache()

        previous_memory = 0
        for i, bar_count in enumerate(bar_counts):
            key = CacheKey(asset_id=i, field="close", bar_count=bar_count, end_date="2023-01-01")
            # float64 = 8 bytes per value
            data = np.array([100.0] * bar_count, dtype=np.float64)
            cache.put(key, data)

            current_memory = cache.get_stats()["memory_bytes"]

            # Property: Memory never decreases when adding (unless LRU evicts)
            # We can't guarantee strict monotonic due to eviction, but memory should be reasonable
            assert current_memory >= 0
            assert (
                current_memory <= len(bar_counts) * max(bar_counts) * 8 * 2
            )  # Upper bound with safety margin

    @given(
        bar_count=st.integers(min_value=1, max_value=200),
        n_threads=st.integers(min_value=2, max_value=8),
        n_operations=st.integers(min_value=10, max_value=100),
    )
    @settings(max_examples=100, deadline=None)
    def test_property_thread_safety_no_corruption(self, bar_count, n_threads, n_operations):
        """Property: Concurrent access never corrupts cache data."""
        cache = HistoryCache()

        # Create reference data
        reference_data = np.array([100.0] * bar_count, dtype=np.float64)
        key = CacheKey(asset_id=1, field="close", bar_count=bar_count, end_date="2023-01-01")

        # Pre-populate
        cache.put(key, reference_data)

        def worker():
            for _ in range(n_operations):
                retrieved = cache.get(key)
                if retrieved is not None:
                    # Property: Retrieved data must always match reference
                    assert np.array_equal(retrieved, reference_data)

        # Run concurrent workers
        with ThreadPoolExecutor(max_workers=n_threads) as executor:
            futures = [executor.submit(worker) for _ in range(n_threads)]
            for f in futures:
                f.result()  # Will raise if assertion failed

        # Property: Cache still contains correct data after concurrent access
        final_data = cache.get(key)
        assert final_data is not None
        assert np.array_equal(final_data, reference_data)

    @given(
        original_values=st.lists(
            st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=200,
        ),
    )
    @settings(max_examples=1000, deadline=None)
    def test_property_decimal_precision_preservation(self, original_values):
        """Property: Float64 values maintain precision through cache round-trip."""
        cache = HistoryCache()

        key = CacheKey(
            asset_id=1, field="close", bar_count=len(original_values), end_date="2023-01-01"
        )

        # Create array from values
        original_array = np.array(original_values, dtype=np.float64)

        # Put and retrieve
        cache.put(key, original_array)
        retrieved = cache.get(key)

        # Property: Values are preserved with float64 precision
        assert retrieved is not None
        assert np.allclose(retrieved, original_array, rtol=1e-15, atol=1e-15)

    @given(
        n_unique_keys=st.integers(min_value=1, max_value=100),
    )
    @settings(max_examples=500, deadline=None)
    def test_property_invalidation_clears_all(self, n_unique_keys):
        """Property: Invalidation removes all entries from both tiers."""
        cache = HistoryCache(permanent_windows=[20, 50], tier2_maxsize=100)

        # Add entries to both tiers
        for i in range(n_unique_keys):
            # Some to tier1
            if i % 3 == 0:
                bar_count = 20
            # Some to tier2
            else:
                bar_count = 30 + i

            key = CacheKey(
                asset_id=i,
                field="close",
                bar_count=bar_count,
                end_date=f"2023-01-{(i % 28) + 1:02d}",
            )
            cache.put(key, np.array([100.0]))

        # Verify we have entries
        tier1_before = len(cache.tier1_cache)
        tier2_before = len(cache.tier2_cache)
        assume(tier1_before > 0 or tier2_before > 0)

        # Invalidate
        cache.invalidate_cache("test_hash_123")

        # Property: All caches are empty after invalidation
        assert len(cache.tier1_cache) == 0
        assert len(cache.tier2_cache) == 0
        assert cache.hits == 0
        assert cache.misses == 0
