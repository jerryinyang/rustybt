"""Unit tests for BundleConnectionPool.

Constitutional requirements:
- CR-008: Zero-mock enforcement (real bundle loading, no mocks)
- CR-004: Complete type hints
"""

import threading
import time
from collections import OrderedDict
from typing import List

import pytest

from rustybt.data.bundles.core import BundleData
from rustybt.optimization.bundle_pool import BundleConnectionPool, get_bundle_from_pool
from rustybt.optimization.cache_invalidation import get_bundle_version


class TestBundleConnectionPoolSingleton:
    """Test singleton pattern correctness."""

    def test_singleton_same_instance(self):
        """Test that get_instance() always returns same instance."""
        # Reset singleton for clean test
        BundleConnectionPool._instance = None

        pool1 = BundleConnectionPool.get_instance()
        pool2 = BundleConnectionPool.get_instance()

        assert pool1 is pool2, "get_instance() should return same instance"

    def test_singleton_thread_safe_creation(self):
        """Test that singleton creation is thread-safe."""
        # Reset singleton
        BundleConnectionPool._instance = None

        instances: List[BundleConnectionPool] = []

        def create_instance():
            pool = BundleConnectionPool.get_instance()
            instances.append(pool)

        # Create 10 threads trying to get instance simultaneously
        threads = [threading.Thread(target=create_instance) for _ in range(10)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # All instances should be the same object
        assert len(instances) == 10
        assert all(
            inst is instances[0] for inst in instances
        ), "All threads should get same singleton instance"

    def test_singleton_preserves_state(self):
        """Test that singleton preserves state across calls."""
        # Reset singleton
        BundleConnectionPool._instance = None

        pool1 = BundleConnectionPool.get_instance()
        # Modify state
        pool1.version_hashes["test"] = "abc123"

        pool2 = BundleConnectionPool.get_instance()
        # State should be preserved
        assert "test" in pool2.version_hashes
        assert pool2.version_hashes["test"] == "abc123"


class TestBundleConnectionPoolLazyLoading:
    """Test lazy initialization on first access."""

    def test_lazy_initialization(self, test_bundle):
        """Test that bundle is only loaded on first access."""
        # Reset singleton
        BundleConnectionPool._instance = None

        pool = BundleConnectionPool.get_instance()

        # Initially pool should be empty
        assert len(pool.bundle_connections) == 0

        # First access loads bundle
        bundle_data = pool.get_bundle(test_bundle)

        assert isinstance(bundle_data, BundleData)
        assert len(pool.bundle_connections) == 1
        assert test_bundle in pool.bundle_connections

    def test_subsequent_access_uses_cache(self, test_bundle):
        """Test that subsequent access returns cached bundle."""
        # Reset singleton
        BundleConnectionPool._instance = None

        pool = BundleConnectionPool.get_instance()

        # First access
        bundle_data_1 = pool.get_bundle(test_bundle)

        # Second access (should be cached)
        bundle_data_2 = pool.get_bundle(test_bundle)

        # Should be same object (cached)
        assert bundle_data_1 is bundle_data_2

    def test_lazy_loading_multiple_bundles(self, test_bundle, alt_test_bundle):
        """Test lazy loading with multiple bundles."""
        # Reset singleton
        BundleConnectionPool._instance = None

        pool = BundleConnectionPool.get_instance()

        # Load first bundle
        bundle1 = pool.get_bundle(test_bundle)
        assert len(pool.bundle_connections) == 1

        # Load second bundle
        bundle2 = pool.get_bundle(alt_test_bundle)
        assert len(pool.bundle_connections) == 2

        # Both should be in pool
        assert test_bundle in pool.bundle_connections
        assert alt_test_bundle in pool.bundle_connections


class TestBundleConnectionPoolLRUEviction:
    """Test LRU eviction when max pool size reached."""

    def test_lru_eviction_at_capacity(self):
        """Test that LRU bundle evicted when pool reaches capacity."""
        # Reset singleton with small max_pool_size
        BundleConnectionPool._instance = None

        pool = BundleConnectionPool.get_instance(max_pool_size=3)

        # Mock bundles (for capacity testing)
        from rustybt.data.bundles.core import _BundleData

        # Add 3 bundles (at capacity)
        for i in range(3):
            bundle_name = f"bundle_{i}"
            # Create mock BundleData
            mock_bundle = _BundleData(
                asset_finder=None,
                equity_minute_bar_reader=None,
                equity_daily_bar_reader=None,
                adjustment_reader=None,
            )
            pool.bundle_connections[bundle_name] = mock_bundle
            pool.version_hashes[bundle_name] = f"hash_{i}"

        # Pool should be at capacity
        assert len(pool.bundle_connections) == 3

        # Add 4th bundle (should evict LRU)
        bundle_name_4 = "bundle_3"
        mock_bundle_4 = _BundleData(
            asset_finder=None,
            equity_minute_bar_reader=None,
            equity_daily_bar_reader=None,
            adjustment_reader=None,
        )
        pool._add_to_pool(bundle_name_4, mock_bundle_4)

        # Pool should still be at capacity
        assert len(pool.bundle_connections) == 3

        # LRU bundle (bundle_0) should be evicted
        assert "bundle_0" not in pool.bundle_connections
        assert "bundle_1" in pool.bundle_connections
        assert "bundle_2" in pool.bundle_connections
        assert "bundle_3" in pool.bundle_connections

    def test_lru_order_updated_on_access(self):
        """Test that LRU order updated when bundle accessed."""
        # Reset singleton with small max_pool_size
        BundleConnectionPool._instance = None

        pool = BundleConnectionPool.get_instance(max_pool_size=3)

        from rustybt.data.bundles.core import _BundleData

        # Add 3 bundles
        for i in range(3):
            bundle_name = f"bundle_{i}"
            mock_bundle = _BundleData(
                asset_finder=None,
                equity_minute_bar_reader=None,
                equity_daily_bar_reader=None,
                adjustment_reader=None,
            )
            pool.bundle_connections[bundle_name] = mock_bundle

        # Access bundle_0 (should move to end)
        pool._update_lru_order("bundle_0")

        # Current order should be: bundle_1, bundle_2, bundle_0
        keys = list(pool.bundle_connections.keys())
        assert keys == ["bundle_1", "bundle_2", "bundle_0"]

        # Add 4th bundle (should evict bundle_1, not bundle_0)
        bundle_name_4 = "bundle_3"
        mock_bundle_4 = _BundleData(
            asset_finder=None,
            equity_minute_bar_reader=None,
            equity_daily_bar_reader=None,
            adjustment_reader=None,
        )
        pool._add_to_pool(bundle_name_4, mock_bundle_4)

        # bundle_1 should be evicted (LRU)
        assert "bundle_1" not in pool.bundle_connections
        assert "bundle_0" in pool.bundle_connections  # Moved to end, not evicted
        assert "bundle_2" in pool.bundle_connections
        assert "bundle_3" in pool.bundle_connections

    def test_max_pool_size_enforced(self):
        """Test that max_pool_size strictly enforced."""
        # Reset singleton
        BundleConnectionPool._instance = None

        max_size = 5
        pool = BundleConnectionPool.get_instance(max_pool_size=max_size)

        from rustybt.data.bundles.core import _BundleData

        # Add max_size + 10 bundles
        for i in range(max_size + 10):
            bundle_name = f"bundle_{i}"
            mock_bundle = _BundleData(
                asset_finder=None,
                equity_minute_bar_reader=None,
                equity_daily_bar_reader=None,
                adjustment_reader=None,
            )
            pool._add_to_pool(bundle_name, mock_bundle)

        # Pool should never exceed max_size
        assert len(pool.bundle_connections) == max_size


class TestBundleConnectionPoolThreadSafety:
    """Test thread safety for concurrent access."""

    def test_concurrent_get_bundle_same_bundle(self, test_bundle):
        """Test concurrent access to same bundle is thread-safe."""
        # Reset singleton
        BundleConnectionPool._instance = None

        pool = BundleConnectionPool.get_instance()

        bundles: List[BundleData] = []
        errors: List[Exception] = []

        def get_bundle_concurrent():
            try:
                bundle_data = pool.get_bundle(test_bundle)
                bundles.append(bundle_data)
            except Exception as e:
                errors.append(e)

        # Create 10 threads accessing same bundle
        threads = [threading.Thread(target=get_bundle_concurrent) for _ in range(10)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # No errors should occur
        assert len(errors) == 0, f"Thread safety errors: {errors}"

        # All threads should get same bundle (cached)
        assert len(bundles) == 10
        assert all(b is bundles[0] for b in bundles), "All threads should get same cached bundle"

    def test_concurrent_get_bundle_different_bundles(self, test_bundle, alt_test_bundle):
        """Test concurrent access to different bundles is thread-safe."""
        # Reset singleton
        BundleConnectionPool._instance = None

        pool = BundleConnectionPool.get_instance()

        bundle1_results: List[BundleData] = []
        bundle2_results: List[BundleData] = []
        errors: List[Exception] = []

        def get_bundle1():
            try:
                bundle_data = pool.get_bundle(test_bundle)
                bundle1_results.append(bundle_data)
            except Exception as e:
                errors.append(e)

        def get_bundle2():
            try:
                bundle_data = pool.get_bundle(alt_test_bundle)
                bundle2_results.append(bundle_data)
            except Exception as e:
                errors.append(e)

        # Create 10 threads for each bundle
        threads = []
        for _ in range(10):
            threads.append(threading.Thread(target=get_bundle1))
            threads.append(threading.Thread(target=get_bundle2))

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # No errors should occur
        assert len(errors) == 0, f"Thread safety errors: {errors}"

        # All threads for bundle1 should get same instance
        assert len(bundle1_results) == 10
        assert all(b is bundle1_results[0] for b in bundle1_results)

        # All threads for bundle2 should get same instance
        assert len(bundle2_results) == 10
        assert all(b is bundle2_results[0] for b in bundle2_results)


class TestBundleConnectionPoolVersionInvalidation:
    """Test version-based cache invalidation."""

    def test_invalidate_if_version_changed_no_change(self, test_bundle):
        """Test that bundle not invalidated if version unchanged."""
        # Reset singleton
        BundleConnectionPool._instance = None

        pool = BundleConnectionPool.get_instance()

        # Load bundle initially
        bundle_data = pool.get_bundle(test_bundle)

        # Get current version hash
        version = get_bundle_version(test_bundle)
        pool.version_hashes[test_bundle] = version.computed_hash

        # Check invalidation (should return False)
        invalidated = pool.invalidate_if_version_changed(test_bundle)

        assert invalidated is False
        assert test_bundle in pool.bundle_connections

    def test_version_hash_stored_on_first_access(self, test_bundle):
        """Test that version hash stored on first bundle access."""
        # Reset singleton
        BundleConnectionPool._instance = None

        pool = BundleConnectionPool.get_instance()

        # Initially no version hash
        assert test_bundle not in pool.version_hashes

        # Load bundle
        pool.get_bundle(test_bundle)

        # Version hash should be stored
        assert test_bundle in pool.version_hashes
        assert len(pool.version_hashes[test_bundle]) == 64  # SHA256 hex length


class TestBundleConnectionPoolForceInvalidation:
    """Test manual force invalidation API."""

    def test_force_invalidate_single_bundle(self, test_bundle):
        """Test force_invalidate() removes specific bundle."""
        # Reset singleton
        BundleConnectionPool._instance = None

        pool = BundleConnectionPool.get_instance()

        # Load bundle
        pool.get_bundle(test_bundle)

        assert test_bundle in pool.bundle_connections
        assert test_bundle in pool.version_hashes

        # Force invalidate
        pool.force_invalidate(test_bundle)

        # Bundle should be removed
        assert test_bundle not in pool.bundle_connections
        assert test_bundle not in pool.version_hashes

    def test_force_invalidate_all_bundles(self, test_bundle, alt_test_bundle):
        """Test force_invalidate() without args clears all bundles."""
        # Reset singleton
        BundleConnectionPool._instance = None

        pool = BundleConnectionPool.get_instance()

        # Load multiple bundles
        pool.get_bundle(test_bundle)
        pool.get_bundle(alt_test_bundle)

        assert len(pool.bundle_connections) == 2

        # Force invalidate all
        pool.force_invalidate()

        # All bundles should be removed
        assert len(pool.bundle_connections) == 0
        assert len(pool.version_hashes) == 0

    def test_force_invalidate_nonexistent_bundle(self):
        """Test force_invalidate() handles nonexistent bundle gracefully."""
        # Reset singleton
        BundleConnectionPool._instance = None

        pool = BundleConnectionPool.get_instance()

        # Force invalidate nonexistent bundle (should not raise)
        pool.force_invalidate("nonexistent_bundle")

        # Pool should still be empty
        assert len(pool.bundle_connections) == 0


class TestBundleConnectionPoolStats:
    """Test pool statistics tracking."""

    def test_get_pool_stats_empty(self):
        """Test get_pool_stats() with empty pool."""
        # Reset singleton
        BundleConnectionPool._instance = None

        pool = BundleConnectionPool.get_instance(max_pool_size=100)

        stats = pool.get_pool_stats()

        assert stats["pool_size"] == 0
        assert stats["max_pool_size"] == 100
        assert stats["num_versions_tracked"] == 0

    def test_get_pool_stats_with_bundles(self, test_bundle, alt_test_bundle):
        """Test get_pool_stats() with loaded bundles."""
        # Reset singleton
        BundleConnectionPool._instance = None

        pool = BundleConnectionPool.get_instance(max_pool_size=100)

        # Load bundles
        pool.get_bundle(test_bundle)
        pool.get_bundle(alt_test_bundle)

        stats = pool.get_pool_stats()

        assert stats["pool_size"] == 2
        assert stats["max_pool_size"] == 100
        assert stats["num_versions_tracked"] == 2


class TestConvenienceFunction:
    """Test get_bundle_from_pool() convenience function."""

    def test_get_bundle_from_pool(self, test_bundle):
        """Test get_bundle_from_pool() works correctly."""
        # Reset singleton
        BundleConnectionPool._instance = None

        bundle_data = get_bundle_from_pool(test_bundle)

        assert isinstance(bundle_data, BundleData)

        # Should use singleton
        pool = BundleConnectionPool.get_instance()
        assert test_bundle in pool.bundle_connections


class TestBundleConnectionPoolFunctionalEquivalence:
    """Test that pooled connections produce identical results to direct loading."""

    def test_functional_equivalence_single_bundle(self, test_bundle):
        """Test that pool returns same data as direct load."""
        from rustybt.data.bundles.core import load

        # Direct load
        direct_bundle = load(test_bundle)

        # Reset singleton
        BundleConnectionPool._instance = None

        # Pool load
        pool = BundleConnectionPool.get_instance()
        pooled_bundle = pool.get_bundle(test_bundle)

        # Both should have same structure
        assert type(direct_bundle) == type(pooled_bundle)
        assert direct_bundle.asset_finder is not None
        assert pooled_bundle.asset_finder is not None

        # Asset finders should have same assets
        direct_assets = sorted([a.symbol for a in direct_bundle.asset_finder.retrieve_all()])
        pooled_assets = sorted([a.symbol for a in pooled_bundle.asset_finder.retrieve_all()])

        assert (
            direct_assets == pooled_assets
        ), "Pooled bundle should have same assets as direct load"


# Fixtures


@pytest.fixture
def test_bundle():
    """Provide test bundle name.

    Returns the name of a bundle that exists with data in the test environment.
    Skips test if bundle not available or data not ingested.
    """
    from rustybt.data.bundles import bundles
    from rustybt.data.bundles.core import load

    available_bundles = list(bundles.keys())

    if len(available_bundles) == 0:
        pytest.skip("No bundles available for testing")

    # Try to find a bundle with actual data
    for bundle_name in available_bundles:
        try:
            # Try to load bundle to check if data exists
            bundle_data = load(bundle_name)
            return bundle_name
        except (ValueError, FileNotFoundError):
            # Bundle data not ingested, try next
            continue

    # No bundle with data found
    pytest.skip(
        f"No bundles with ingested data available. Available bundles: {available_bundles}. Run 'zipline ingest -b <bundle_name>' to ingest data."
    )


@pytest.fixture
def alt_test_bundle():
    """Provide alternative test bundle name.

    Returns the name of a second bundle for multi-bundle tests.
    Skips test if second bundle not available or data not ingested.
    """
    from rustybt.data.bundles import bundles
    from rustybt.data.bundles.core import load

    available_bundles = list(bundles.keys())

    if len(available_bundles) < 2:
        pytest.skip("Need at least 2 bundles for this test")

    # Try to find two bundles with actual data
    bundles_with_data = []
    for bundle_name in available_bundles:
        try:
            # Try to load bundle to check if data exists
            bundle_data = load(bundle_name)
            bundles_with_data.append(bundle_name)
            if len(bundles_with_data) >= 2:
                break
        except (ValueError, FileNotFoundError):
            # Bundle data not ingested, try next
            continue

    if len(bundles_with_data) < 2:
        pytest.skip(
            f"Need at least 2 bundles with ingested data. Found {len(bundles_with_data)}. Run 'zipline ingest -b <bundle_name>' to ingest data."
        )

    # Return second bundle
    return bundles_with_data[1]


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset singleton before each test."""
    # Reset singleton to ensure clean state
    BundleConnectionPool._instance = None
    yield
    # Clean up after test
    BundleConnectionPool._instance = None
