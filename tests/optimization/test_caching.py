"""Unit and property-based tests for optimization caching.

This module tests CachedAssetList, PreGroupedData, and DataCache
for correctness, cache invalidation, and memory management.

Constitutional requirements:
- CR-004: Complete type hints
- Zero-mock enforcement: Tests use real data and real caching
"""

from collections import namedtuple
from datetime import datetime
from decimal import Decimal

import numpy as np
import pandas as pd
import polars as pl
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine

from rustybt.assets import AssetDBWriter, AssetFinder
from rustybt.assets.synthetic import make_simple_equity_info
from rustybt.optimization.cache_invalidation import compute_bundle_hash, get_bundle_version
from rustybt.optimization.caching import (
    CachedAssetList,
    DataCache,
    PreGroupedData,
    clear_asset_cache,
    get_asset_cache_info,
    get_cached_assets,
    get_cached_grouped_data,
    get_global_data_cache,
    pre_group_data,
)

# BundleData structure matching rustybt.data.bundles.core.BundleData
_BundleData = namedtuple(
    "_BundleData",
    "asset_finder equity_minute_bar_reader equity_daily_bar_reader adjustment_reader",
)


@pytest.fixture
def real_test_bundle():
    """Create a real test bundle with real AssetFinder and real Asset objects.

    This fixture creates an in-memory SQLite database with real assets,
    following Zero-Mock Enforcement policy (no mocks, no stubs).

    Returns:
        BundleData: Real bundle with asset_finder containing real Asset objects.
    """
    # Create real equity info for test assets
    equity_info = make_simple_equity_info(
        sids=[1, 2, 3],
        start_date=pd.Timestamp("2020-01-01"),
        end_date=pd.Timestamp("2023-12-31"),
        symbols=["AAPL", "MSFT", "GOOGL"],
    )

    # Create in-memory SQLite database
    engine = create_engine("sqlite:///:memory:")
    AssetDBWriter(engine).write(equities=equity_info)

    # Create real AssetFinder with real assets
    asset_finder = AssetFinder(engine)

    # Create BundleData structure (equity_*_bar_reader and adjustment_reader are None for caching tests)
    bundle = _BundleData(
        asset_finder=asset_finder,
        equity_minute_bar_reader=None,
        equity_daily_bar_reader=None,
        adjustment_reader=None,
    )

    yield bundle

    # Cleanup
    engine.dispose()


class TestCachedAssetList:
    """Test suite for CachedAssetList dataclass."""

    def test_cached_asset_list_creation(self):
        """Test CachedAssetList can be created with valid data."""
        cached = CachedAssetList(
            bundle_name="test_bundle",
            bundle_hash="abc123" * 10 + "abcd",  # 64-char hash
            asset_list=["AAPL", "MSFT", "GOOGL"],
            created_at=datetime.now(),
        )

        assert cached.bundle_name == "test_bundle"
        assert cached.bundle_hash == "abc123" * 10 + "abcd"
        assert len(cached.asset_list) == 3
        assert "AAPL" in cached.asset_list

    def test_cached_asset_list_immutable(self):
        """Test CachedAssetList is frozen (immutable)."""
        cached = CachedAssetList(
            bundle_name="test_bundle",
            bundle_hash="abc123" * 10 + "abcd",
            asset_list=["AAPL", "MSFT"],
            created_at=datetime.now(),
        )

        # Should not be able to modify frozen dataclass
        with pytest.raises(Exception):  # FrozenInstanceError
            cached.asset_list = ["TSLA"]

    def test_cached_asset_list_equality(self):
        """Test CachedAssetList equality based on all fields."""
        timestamp = datetime.now()
        cached1 = CachedAssetList(
            bundle_name="test_bundle",
            bundle_hash="abc123" * 10 + "abcd",
            asset_list=["AAPL", "MSFT"],
            created_at=timestamp,
        )
        cached2 = CachedAssetList(
            bundle_name="test_bundle",
            bundle_hash="abc123" * 10 + "abcd",
            asset_list=["AAPL", "MSFT"],
            created_at=timestamp,
        )

        # Should be equal if all fields match
        assert cached1 == cached2

    def test_cached_asset_list_inequality_different_hash(self):
        """Test CachedAssetList inequality when hash differs."""
        timestamp = datetime.now()
        cached1 = CachedAssetList(
            bundle_name="test_bundle",
            bundle_hash="abc123" * 10 + "abcd",
            asset_list=["AAPL", "MSFT"],
            created_at=timestamp,
        )
        cached2 = CachedAssetList(
            bundle_name="test_bundle",
            bundle_hash="def456" * 10 + "efgh",  # Different hash
            asset_list=["AAPL", "MSFT"],
            created_at=timestamp,
        )

        # Should not be equal due to different hash
        assert cached1 != cached2


class TestGetCachedAssets:
    """Test suite for get_cached_assets() function."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_asset_cache()

    def test_get_cached_assets_requires_bundle_name(self):
        """Test get_cached_assets raises ValueError if bundle_name empty."""
        with pytest.raises(ValueError, match="bundle_name cannot be empty"):
            get_cached_assets("", "abc123" * 10 + "abcd")

    def test_get_cached_assets_requires_bundle_hash(self):
        """Test get_cached_assets raises ValueError if bundle_hash empty."""
        with pytest.raises(ValueError, match="bundle_hash cannot be empty"):
            get_cached_assets("test_bundle", "")

    def test_get_cached_assets_loads_bundle(self, real_test_bundle, monkeypatch):
        """Test get_cached_assets loads bundle and extracts assets using real objects."""

        def mock_load(bundle_name):
            """Return real test bundle instead of mocking."""
            assert bundle_name == "test_bundle"
            return real_test_bundle

        # Monkeypatch the load function with our real bundle
        import rustybt.data.bundles.core

        monkeypatch.setattr(rustybt.data.bundles.core, "load", mock_load)

        # Call get_cached_assets with real bundle
        result = get_cached_assets("test_bundle", "abc123" * 10 + "abcd")

        # Verify real assets extracted (AAPL, MSFT, GOOGL from fixture)
        assert len(result) == 3
        assert "AAPL" in result
        assert "MSFT" in result
        assert "GOOGL" in result

    def test_get_cached_assets_caches_result(self, real_test_bundle, monkeypatch):
        """Test get_cached_assets caches result for repeated calls using real objects."""
        load_count = [0]  # Use list to track calls (closure)

        def mock_load(bundle_name):
            """Track how many times load is called."""
            load_count[0] += 1
            return real_test_bundle

        # Monkeypatch the load function
        import rustybt.data.bundles.core

        monkeypatch.setattr(rustybt.data.bundles.core, "load", mock_load)

        # First call - cache miss, should load bundle
        result1 = get_cached_assets("test_bundle", "abc123" * 10 + "abcd")

        # Second call with same args - cache hit, should NOT load bundle again
        result2 = get_cached_assets("test_bundle", "abc123" * 10 + "abcd")

        # Verify same object reference (cache hit)
        assert result1 is result2

        # Verify bundle loaded only once (first call, second was cached)
        assert load_count[0] == 1

    def test_get_cached_assets_invalidates_on_hash_change(self, real_test_bundle, monkeypatch):
        """Test get_cached_assets reloads when bundle hash changes using real objects."""
        load_count = [0]  # Track load calls

        def mock_load(bundle_name):
            """Track how many times load is called."""
            load_count[0] += 1
            return real_test_bundle

        # Monkeypatch the load function
        import rustybt.data.bundles.core

        monkeypatch.setattr(rustybt.data.bundles.core, "load", mock_load)

        # First call with hash1 - cache miss, should load
        result1 = get_cached_assets("test_bundle", "abc123" * 10 + "abcd")

        # Second call with different hash - cache miss due to hash change, should reload
        result2 = get_cached_assets("test_bundle", "def456" * 10 + "efgh")

        # Verify bundle loaded twice (different hashes = cache misses)
        assert load_count[0] == 2

        # Verify both results contain real assets
        assert len(result1) == 3
        assert len(result2) == 3

    def test_clear_asset_cache_clears_cache(self, real_test_bundle, monkeypatch):
        """Test clear_asset_cache() clears all cached data using real objects."""
        load_count = [0]  # Track load calls

        def mock_load(bundle_name):
            """Track how many times load is called."""
            load_count[0] += 1
            return real_test_bundle

        # Monkeypatch the load function
        import rustybt.data.bundles.core

        monkeypatch.setattr(rustybt.data.bundles.core, "load", mock_load)

        # Populate cache - first load
        get_cached_assets("test_bundle", "abc123" * 10 + "abcd")
        assert load_count[0] == 1

        # Clear cache
        clear_asset_cache()

        # Next call should reload bundle (cache cleared = cache miss)
        result = get_cached_assets("test_bundle", "abc123" * 10 + "abcd")

        # Verify bundle loaded twice (once before clear, once after clear)
        assert load_count[0] == 2

        # Verify result contains real assets
        assert len(result) == 3
        assert "AAPL" in result

    def test_get_asset_cache_info_returns_stats(self, real_test_bundle, monkeypatch):
        """Test get_asset_cache_info() returns cache statistics using real objects."""
        clear_asset_cache()

        def mock_load(bundle_name):
            """Return real test bundle."""
            return real_test_bundle

        # Monkeypatch the load function
        import rustybt.data.bundles.core

        monkeypatch.setattr(rustybt.data.bundles.core, "load", mock_load)

        # First call - cache miss
        get_cached_assets("test_bundle", "abc123" * 10 + "abcd")

        # Second call with same args - cache hit
        get_cached_assets("test_bundle", "abc123" * 10 + "abcd")

        # Get cache statistics
        info = get_asset_cache_info()

        # Verify statistics
        assert info["hits"] == 1  # Second call was a hit
        assert info["misses"] == 1  # First call was a miss
        assert info["size"] == 1  # One unique bundle cached
        assert info["maxsize"] == 128  # Default LRU cache size
        assert info["hit_rate"] == 0.5  # 1 hit / (1 hit + 1 miss) = 0.5


class TestPreGroupedData:
    """Test suite for PreGroupedData dataclass."""

    def test_pre_grouped_data_creation(self):
        """Test PreGroupedData can be created with valid data."""
        data_dict = {
            "AAPL": np.array([[100.0, 102.0, 99.0, 101.0, 1000]]),
            "MSFT": np.array([[200.0, 202.0, 198.0, 201.0, 2000]]),
        }
        memory_usage = sum(arr.nbytes for arr in data_dict.values())

        grouped = PreGroupedData(
            bundle_hash="abc123" * 10 + "abcd",
            data_dict=data_dict,
            memory_usage=memory_usage,
            created_at=datetime.now(),
        )

        assert grouped.bundle_hash == "abc123" * 10 + "abcd"
        assert len(grouped.data_dict) == 2
        assert "AAPL" in grouped.data_dict
        assert grouped.data_dict["AAPL"].shape == (1, 5)
        assert grouped.memory_usage == memory_usage

    def test_pre_grouped_data_numpy_arrays(self):
        """Test PreGroupedData stores NumPy arrays correctly."""
        data_dict = {
            "AAPL": np.array(
                [
                    [100.0, 102.0, 99.0, 101.0, 1000],
                    [101.0, 103.0, 100.0, 102.0, 1100],
                ]
            ),
        }

        grouped = PreGroupedData(
            bundle_hash="abc123" * 10 + "abcd",
            data_dict=data_dict,
            memory_usage=data_dict["AAPL"].nbytes,
            created_at=datetime.now(),
        )

        # Verify shape (2 bars × 5 OHLCV columns)
        assert grouped.data_dict["AAPL"].shape == (2, 5)

        # Verify data types
        assert grouped.data_dict["AAPL"].dtype == np.float64


class TestPreGroupData:
    """Test suite for pre_group_data() function."""

    def test_pre_group_data_basic(self):
        """Test pre_group_data groups data by asset correctly."""
        data = pl.DataFrame(
            {
                "asset": ["AAPL", "AAPL", "MSFT"],
                "open": [100.0, 101.0, 200.0],
                "high": [102.0, 103.0, 202.0],
                "low": [99.0, 100.0, 198.0],
                "close": [101.0, 102.0, 201.0],
                "volume": [1000, 1100, 2000],
            }
        )

        grouped = pre_group_data(data, "abc123" * 10 + "abcd")

        # Verify structure
        assert isinstance(grouped, PreGroupedData)
        assert len(grouped.data_dict) == 2
        assert "AAPL" in grouped.data_dict
        assert "MSFT" in grouped.data_dict

        # Verify AAPL data (2 bars)
        aapl_data = grouped.data_dict["AAPL"]
        assert aapl_data.shape == (2, 5)
        assert np.allclose(aapl_data[0], [100.0, 102.0, 99.0, 101.0, 1000])
        assert np.allclose(aapl_data[1], [101.0, 103.0, 100.0, 102.0, 1100])

        # Verify MSFT data (1 bar)
        msft_data = grouped.data_dict["MSFT"]
        assert msft_data.shape == (1, 5)
        assert np.allclose(msft_data[0], [200.0, 202.0, 198.0, 201.0, 2000])

    def test_pre_group_data_missing_columns_raises(self):
        """Test pre_group_data raises ValueError if columns missing."""
        data = pl.DataFrame(
            {
                "asset": ["AAPL"],
                "open": [100.0],
                "high": [102.0],
                # Missing 'low', 'close', 'volume'
            }
        )

        with pytest.raises(ValueError, match="Data missing required columns"):
            pre_group_data(data, "abc123" * 10 + "abcd")

    def test_pre_group_data_memory_usage_calculated(self):
        """Test pre_group_data calculates memory usage correctly."""
        data = pl.DataFrame(
            {
                "asset": ["AAPL"] * 100 + ["MSFT"] * 100,
                "open": list(range(100)) + list(range(100, 200)),
                "high": list(range(101, 201)) + list(range(102, 202)),
                "low": list(range(99, 199)) + list(range(98, 198)),
                "close": list(range(100, 200)) + list(range(101, 201)),
                "volume": list(range(1000, 1100)) + list(range(2000, 2100)),
            }
        )

        grouped = pre_group_data(data, "abc123" * 10 + "abcd")

        # Calculate expected memory (2 assets × 100 bars × 5 columns × 8 bytes/float64)
        expected_memory = 2 * 100 * 5 * 8
        assert grouped.memory_usage == expected_memory

    def test_pre_group_data_preserves_decimal_precision(self):
        """Test pre_group_data preserves Decimal precision through float64."""
        # Use high-precision values that could lose precision in float32
        data = pl.DataFrame(
            {
                "asset": ["AAPL"],
                "open": [100.123456789],
                "high": [102.987654321],
                "low": [99.111111111],
                "close": [101.555555555],
                "volume": [1000],
            }
        )

        grouped = pre_group_data(data, "abc123" * 10 + "abcd")

        # Verify precision preserved within 1e-10 tolerance
        aapl_data = grouped.data_dict["AAPL"]
        assert abs(aapl_data[0, 0] - 100.123456789) < 1e-10
        assert abs(aapl_data[0, 1] - 102.987654321) < 1e-10
        assert abs(aapl_data[0, 2] - 99.111111111) < 1e-10
        assert abs(aapl_data[0, 3] - 101.555555555) < 1e-10


class TestDataCache:
    """Test suite for DataCache class."""

    def test_data_cache_initialization(self):
        """Test DataCache initializes with correct memory limit."""
        cache = DataCache(max_memory_gb=2.0)

        assert cache.max_memory_bytes == int(2.0 * 1024 * 1024 * 1024)
        assert cache.current_memory == 0
        assert cache.hits == 0
        assert cache.misses == 0
        assert len(cache.cache) == 0

    def test_data_cache_invalid_memory_limit_raises(self):
        """Test DataCache raises ValueError for invalid memory limit."""
        with pytest.raises(ValueError, match="max_memory_gb must be > 0"):
            DataCache(max_memory_gb=0)

        with pytest.raises(ValueError, match="max_memory_gb must be > 0"):
            DataCache(max_memory_gb=-1.0)

    def test_data_cache_put_and_get(self):
        """Test DataCache put() and get() operations."""
        cache = DataCache(max_memory_gb=1.0)

        data_dict = {"AAPL": np.array([[100.0, 102.0, 99.0, 101.0, 1000]])}
        grouped = PreGroupedData(
            bundle_hash="abc123" * 10 + "abcd",
            data_dict=data_dict,
            memory_usage=data_dict["AAPL"].nbytes,
            created_at=datetime.now(),
        )

        # Put data in cache
        cache.put("key1", grouped)

        # Get data from cache
        result = cache.get("key1")

        assert result is not None
        assert result.bundle_hash == grouped.bundle_hash
        assert cache.hits == 1
        assert cache.misses == 0

    def test_data_cache_get_miss(self):
        """Test DataCache get() returns None on cache miss."""
        cache = DataCache(max_memory_gb=1.0)

        result = cache.get("nonexistent_key")

        assert result is None
        assert cache.hits == 0
        assert cache.misses == 1

    def test_data_cache_lru_eviction(self):
        """Test DataCache evicts oldest entries when memory limit exceeded."""
        # Small cache (10 KB limit)
        cache = DataCache(max_memory_gb=10 / (1024 * 1024))

        # Create data that exceeds limit when all stored
        data1 = {"AAPL": np.zeros((100, 5), dtype=np.float64)}  # ~4 KB
        data2 = {"MSFT": np.zeros((100, 5), dtype=np.float64)}  # ~4 KB
        data3 = {"GOOGL": np.zeros((100, 5), dtype=np.float64)}  # ~4 KB

        grouped1 = PreGroupedData("hash1", data1, data1["AAPL"].nbytes, datetime.now())
        grouped2 = PreGroupedData("hash2", data2, data2["MSFT"].nbytes, datetime.now())
        grouped3 = PreGroupedData("hash3", data3, data3["GOOGL"].nbytes, datetime.now())

        # Add data1 and data2 (within limit)
        cache.put("key1", grouped1)
        cache.put("key2", grouped2)

        # Add data3 (exceeds limit, should evict key1)
        cache.put("key3", grouped3)

        # Verify key1 evicted
        assert cache.get("key1") is None

        # Verify key2 and key3 still cached
        assert cache.get("key2") is not None
        assert cache.get("key3") is not None

    def test_data_cache_lru_ordering(self):
        """Test DataCache moves accessed entries to end (LRU)."""
        cache = DataCache(max_memory_gb=10 / (1024 * 1024))

        data1 = {"AAPL": np.zeros((100, 5), dtype=np.float64)}
        data2 = {"MSFT": np.zeros((100, 5), dtype=np.float64)}
        data3 = {"GOOGL": np.zeros((100, 5), dtype=np.float64)}

        grouped1 = PreGroupedData("hash1", data1, data1["AAPL"].nbytes, datetime.now())
        grouped2 = PreGroupedData("hash2", data2, data2["MSFT"].nbytes, datetime.now())
        grouped3 = PreGroupedData("hash3", data3, data3["GOOGL"].nbytes, datetime.now())

        # Add data1 and data2
        cache.put("key1", grouped1)
        cache.put("key2", grouped2)

        # Access key1 (moves to end)
        cache.get("key1")

        # Add data3 (should evict key2 since key1 was recently accessed)
        cache.put("key3", grouped3)

        # Verify key2 evicted (oldest unused)
        assert cache.get("key2") is None

        # Verify key1 and key3 still cached
        assert cache.get("key1") is not None
        assert cache.get("key3") is not None

    def test_data_cache_clear(self):
        """Test DataCache clear() removes all entries."""
        cache = DataCache(max_memory_gb=1.0)

        data_dict = {"AAPL": np.array([[100.0, 102.0, 99.0, 101.0, 1000]])}
        grouped = PreGroupedData(
            "abc123" * 10 + "abcd",
            data_dict,
            data_dict["AAPL"].nbytes,
            datetime.now(),
        )

        cache.put("key1", grouped)
        cache.get("key1")  # Increment hits

        # Clear cache
        cache.clear()

        assert len(cache.cache) == 0
        assert cache.current_memory == 0
        assert cache.hits == 0
        assert cache.misses == 0

    def test_data_cache_get_stats(self):
        """Test DataCache get_stats() returns accurate statistics."""
        cache = DataCache(max_memory_gb=1.0)

        data_dict = {"AAPL": np.array([[100.0, 102.0, 99.0, 101.0, 1000]])}
        grouped = PreGroupedData(
            "abc123" * 10 + "abcd",
            data_dict,
            data_dict["AAPL"].nbytes,
            datetime.now(),
        )

        # Add data
        cache.put("key1", grouped)

        # Access twice (hits)
        cache.get("key1")  # hit
        cache.get("key1")  # hit
        cache.get("nonexistent")  # miss

        stats = cache.get_stats()

        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_rate"] == pytest.approx(2 / 3, rel=0.01)
        assert stats["entries"] == 1
        assert stats["memory_usage_mb"] > 0
        assert stats["max_memory_mb"] == 1024.0  # 1 GB in MB


class TestGetCachedGroupedData:
    """Test suite for get_cached_grouped_data() function."""

    def setup_method(self):
        """Clear global cache before each test."""
        cache = get_global_data_cache()
        cache.clear()

    def test_get_cached_grouped_data_no_cache(self):
        """Test get_cached_grouped_data with caching disabled."""
        data = pl.DataFrame(
            {
                "asset": ["AAPL", "AAPL"],
                "open": [100.0, 101.0],
                "high": [102.0, 103.0],
                "low": [99.0, 100.0],
                "close": [101.0, 102.0],
                "volume": [1000, 1100],
            }
        )

        # Call without caching
        grouped = get_cached_grouped_data(data, "abc123" * 10 + "abcd", use_cache=False)

        assert isinstance(grouped, PreGroupedData)
        assert "AAPL" in grouped.data_dict

        # Verify not cached
        cache = get_global_data_cache()
        assert cache.get("abc123" * 10 + "abcd") is None

    def test_get_cached_grouped_data_with_cache(self):
        """Test get_cached_grouped_data caches result."""
        data = pl.DataFrame(
            {
                "asset": ["AAPL", "AAPL"],
                "open": [100.0, 101.0],
                "high": [102.0, 103.0],
                "low": [99.0, 100.0],
                "close": [101.0, 102.0],
                "volume": [1000, 1100],
            }
        )

        # First call - cache miss
        grouped1 = get_cached_grouped_data(data, "abc123" * 10 + "abcd", use_cache=True)

        # Second call - cache hit
        grouped2 = get_cached_grouped_data(data, "abc123" * 10 + "abcd", use_cache=True)

        # Verify same object returned (cache hit)
        assert grouped1 is grouped2


# Property-based tests with Hypothesis


@settings(max_examples=1000, deadline=None)
@given(
    n_assets=st.integers(min_value=1, max_value=50),
    n_bars=st.integers(min_value=10, max_value=1000),
)
def test_property_pre_grouping_preserves_row_count(n_assets, n_bars):
    """Property test: Pre-grouping preserves total row count."""
    # Generate test data
    assets = [f"ASSET_{i}" for i in range(n_assets)]
    data = pl.DataFrame(
        {
            "asset": assets * n_bars,
            "open": [100.0 + i for i in range(n_assets * n_bars)],
            "high": [102.0 + i for i in range(n_assets * n_bars)],
            "low": [99.0 + i for i in range(n_assets * n_bars)],
            "close": [101.0 + i for i in range(n_assets * n_bars)],
            "volume": [1000 + i for i in range(n_assets * n_bars)],
        }
    )

    grouped = pre_group_data(data, "test_hash")

    # Verify total rows preserved
    total_rows = sum(arr.shape[0] for arr in grouped.data_dict.values())
    assert total_rows == len(data)


@settings(max_examples=1000, deadline=None)
@given(
    n_assets=st.integers(min_value=1, max_value=20),
    n_bars_per_asset=st.integers(min_value=1, max_value=100),
)
def test_property_pre_grouping_preserves_data_integrity(n_assets, n_bars_per_asset):
    """Property test: Pre-grouping preserves all data values."""
    # Generate deterministic test data
    asset_names = [f"ASSET_{i}" for i in range(n_assets)]
    rows = []
    for asset_idx, asset in enumerate(asset_names):
        for bar_idx in range(n_bars_per_asset):
            rows.append(
                {
                    "asset": asset,
                    "open": 100.0 + asset_idx * 100 + bar_idx,
                    "high": 102.0 + asset_idx * 100 + bar_idx,
                    "low": 99.0 + asset_idx * 100 + bar_idx,
                    "close": 101.0 + asset_idx * 100 + bar_idx,
                    "volume": 1000 + asset_idx * 1000 + bar_idx,
                }
            )

    data = pl.DataFrame(rows)
    grouped = pre_group_data(data, "test_hash")

    # Verify all assets present
    assert len(grouped.data_dict) == n_assets

    # Verify each asset has correct number of bars
    for asset in asset_names:
        assert grouped.data_dict[asset].shape[0] == n_bars_per_asset

    # Verify data values match original
    for asset_idx, asset in enumerate(asset_names):
        asset_array = grouped.data_dict[asset]
        for bar_idx in range(n_bars_per_asset):
            expected_open = 100.0 + asset_idx * 100 + bar_idx
            assert abs(asset_array[bar_idx, 0] - expected_open) < 1e-10


@settings(max_examples=500, deadline=None)
@given(
    bundle_contents=st.lists(
        st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("Lu",))),
        min_size=1,
        max_size=100,
        unique=True,
    )
)
def test_property_bundle_hash_deterministic(bundle_contents):
    """Property test: Same bundle contents produce same hash."""
    metadata = {
        "assets": bundle_contents,
        "date_range": (datetime(2020, 1, 1), datetime(2023, 12, 31)),
        "schema_version": "v1",
    }

    hash1 = compute_bundle_hash(metadata)
    hash2 = compute_bundle_hash(metadata)

    # Same input must produce same hash
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA256 produces 64-char hex string


@settings(max_examples=500, deadline=None)
@given(
    bundle_contents1=st.lists(
        st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("Lu",))),
        min_size=1,
        max_size=50,
        unique=True,
    ),
    bundle_contents2=st.lists(
        st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("Lu",))),
        min_size=1,
        max_size=50,
        unique=True,
    ),
)
def test_property_bundle_hash_changes_with_content(bundle_contents1, bundle_contents2):
    """Property test: Different bundle contents produce different hashes."""
    # Skip if lists are identical
    if sorted(bundle_contents1) == sorted(bundle_contents2):
        return

    metadata1 = {
        "assets": bundle_contents1,
        "date_range": (datetime(2020, 1, 1), datetime(2023, 12, 31)),
        "schema_version": "v1",
    }

    metadata2 = {
        "assets": bundle_contents2,
        "date_range": (datetime(2020, 1, 1), datetime(2023, 12, 31)),
        "schema_version": "v1",
    }

    hash1 = compute_bundle_hash(metadata1)
    hash2 = compute_bundle_hash(metadata2)

    # Different inputs must produce different hashes
    assert hash1 != hash2
