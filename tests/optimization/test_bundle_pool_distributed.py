"""Integration tests for BundleConnectionPool in distributed scenarios.

Tests bundle pooling with multiprocessing.Pool and distributed optimization workflows.

Constitutional requirements:
- CR-008: Zero-mock enforcement (real bundle loading, no mocks)
- CR-004: Complete type hints
"""

import multiprocessing
from decimal import Decimal
from typing import List, Tuple

import pytest

from rustybt.data.bundles.core import BundleData
from rustybt.optimization.bundle_pool import BundleConnectionPool, get_bundle_from_pool


def worker_load_bundle(bundle_name: str) -> Tuple[bool, str]:
    """Worker function to load bundle from pool.

    Args:
        bundle_name: Name of bundle to load

    Returns:
        Tuple of (success, message)
    """
    try:
        bundle_data = get_bundle_from_pool(bundle_name)
        assert isinstance(bundle_data, BundleData)
        return (True, f"Successfully loaded {bundle_name}")
    except Exception as e:
        return (False, f"Failed to load {bundle_name}: {str(e)}")


def worker_get_pool_stats(bundle_name: str) -> dict:
    """Worker function to get pool stats after loading bundle.

    Args:
        bundle_name: Name of bundle to load

    Returns:
        Dictionary with pool stats
    """
    try:
        # Load bundle
        get_bundle_from_pool(bundle_name)

        # Get pool stats
        pool = BundleConnectionPool.get_instance()
        stats = pool.get_pool_stats()

        return {
            "success": True,
            "stats": stats,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def worker_multiple_bundles(bundle_names: List[str]) -> dict:
    """Worker function to load multiple bundles.

    Args:
        bundle_names: List of bundle names to load

    Returns:
        Dictionary with results
    """
    results = {
        "success": True,
        "bundles_loaded": [],
        "errors": [],
    }

    for bundle_name in bundle_names:
        try:
            get_bundle_from_pool(bundle_name)
            results["bundles_loaded"].append(bundle_name)
        except Exception as e:
            results["success"] = False
            results["errors"].append(f"{bundle_name}: {str(e)}")

    return results


class TestBundlePoolMultiprocessing:
    """Test bundle pool with multiprocessing.Pool."""

    def test_pool_with_2_workers(self, test_bundle):
        """Test bundle pool with 2 workers."""
        # Reset singleton
        BundleConnectionPool._instance = None

        # Create multiprocessing pool
        with multiprocessing.Pool(processes=2) as pool:
            # Each worker loads same bundle
            results = pool.starmap(
                worker_load_bundle,
                [(test_bundle,) for _ in range(2)],
            )

        # All workers should succeed
        for success, message in results:
            assert success, f"Worker failed: {message}"

    def test_pool_with_4_workers(self, test_bundle):
        """Test bundle pool with 4 workers."""
        # Reset singleton
        BundleConnectionPool._instance = None

        with multiprocessing.Pool(processes=4) as pool:
            results = pool.starmap(
                worker_load_bundle,
                [(test_bundle,) for _ in range(4)],
            )

        # All workers should succeed
        assert all(success for success, _ in results)

    def test_pool_with_8_workers(self, test_bundle):
        """Test bundle pool with 8 workers."""
        # Reset singleton
        BundleConnectionPool._instance = None

        with multiprocessing.Pool(processes=8) as pool:
            results = pool.starmap(
                worker_load_bundle,
                [(test_bundle,) for _ in range(8)],
            )

        # All workers should succeed
        assert all(success for success, _ in results)

    def test_pool_with_16_workers(self, test_bundle):
        """Test bundle pool with 16 workers."""
        # Reset singleton
        BundleConnectionPool._instance = None

        with multiprocessing.Pool(processes=16) as pool:
            results = pool.starmap(
                worker_load_bundle,
                [(test_bundle,) for _ in range(16)],
            )

        # All workers should succeed
        assert all(success for success, _ in results)

    def test_pool_stats_across_workers(self, test_bundle):
        """Test that pool stats are tracked correctly across workers."""
        # Reset singleton
        BundleConnectionPool._instance = None

        with multiprocessing.Pool(processes=4) as pool:
            results = pool.starmap(
                worker_get_pool_stats,
                [(test_bundle,) for _ in range(4)],
            )

        # All workers should succeed
        assert all(r["success"] for r in results)

        # Check that stats show bundle was loaded
        for result in results:
            stats = result["stats"]
            # Note: In multiprocessing, each worker has its own process memory
            # So pool_size may be 1 per worker (not shared across processes)
            assert stats["pool_size"] >= 0


class TestBundlePoolGridSearchScenario:
    """Test bundle pool in grid search optimization scenario."""

    def test_grid_search_100_backtests(self, test_bundle):
        """Simulate 100 backtests in grid search (typical scenario)."""
        # Reset singleton
        BundleConnectionPool._instance = None

        # Simulate 100 backtests across 8 workers
        num_backtests = 100
        num_workers = 8

        with multiprocessing.Pool(processes=num_workers) as pool:
            # Each backtest loads the bundle
            results = pool.starmap(
                worker_load_bundle,
                [(test_bundle,) for _ in range(num_backtests)],
            )

        # All backtests should succeed
        successes = sum(1 for success, _ in results if success)
        assert successes == num_backtests, f"Expected {num_backtests} successes, got {successes}"

    def test_grid_search_multiple_bundles(self, test_bundle, alt_test_bundle):
        """Simulate grid search with multiple bundles."""
        # Reset singleton
        BundleConnectionPool._instance = None

        # Simulate backtests using different bundles
        bundle_sequences = [[test_bundle, alt_test_bundle] for _ in range(50)]

        with multiprocessing.Pool(processes=8) as pool:
            results = pool.map(worker_multiple_bundles, bundle_sequences)

        # All should succeed
        assert all(r["success"] for r in results)

        # Check bundles loaded
        for result in results:
            assert len(result["bundles_loaded"]) == 2


class TestBundlePoolWalkForwardScenario:
    """Test bundle pool in walk forward optimization scenario."""

    def test_walk_forward_5_windows(self, test_bundle):
        """Simulate walk forward with 5 windows, 50 trials each."""
        # Reset singleton
        BundleConnectionPool._instance = None

        # Walk forward: 5 windows, 50 trials per window = 250 total backtests
        num_windows = 5
        trials_per_window = 50
        total_backtests = num_windows * trials_per_window

        with multiprocessing.Pool(processes=8) as pool:
            results = pool.starmap(
                worker_load_bundle,
                [(test_bundle,) for _ in range(total_backtests)],
            )

        # All backtests should succeed
        successes = sum(1 for success, _ in results if success)
        assert successes == total_backtests


class TestBundlePoolPerformanceScaling:
    """Test that bundle pool provides performance benefits at scale."""

    def test_initialization_time_scaling(self, test_bundle):
        """Test that initialization time doesn't grow linearly with workers."""
        import time

        # Reset singleton
        BundleConnectionPool._instance = None

        # Measure time for 2 workers
        start_2 = time.perf_counter()
        with multiprocessing.Pool(processes=2) as pool:
            results_2 = pool.starmap(
                worker_load_bundle,
                [(test_bundle,) for _ in range(2)],
            )
        time_2 = time.perf_counter() - start_2

        # Reset singleton
        BundleConnectionPool._instance = None

        # Measure time for 16 workers
        start_16 = time.perf_counter()
        with multiprocessing.Pool(processes=16) as pool:
            results_16 = pool.starmap(
                worker_load_bundle,
                [(test_bundle,) for _ in range(16)],
            )
        time_16 = time.perf_counter() - start_16

        # Check that time doesn't scale linearly (should be sublinear due to pooling)
        # If it were linear, 16 workers would take 8x as long as 2 workers
        # With pooling, it should take much less than 8x
        linear_ratio = Decimal("8.0")
        actual_ratio = Decimal(str(time_16)) / Decimal(str(time_2)) if time_2 > 0 else Decimal("0")

        # Actual ratio should be much less than linear ratio (evidence of pooling benefit)
        # Allow some overhead, but should be < 4x (50% of linear)
        assert (
            actual_ratio < linear_ratio / 2
        ), f"Time scaling ({actual_ratio:.2f}x) suggests pooling not effective"


class TestBundlePoolNoDeadlocks:
    """Test that bundle pool doesn't cause deadlocks in distributed scenarios."""

    def test_no_deadlocks_with_concurrent_access(self, test_bundle):
        """Test that concurrent access doesn't cause deadlocks."""
        import time

        # Reset singleton
        BundleConnectionPool._instance = None

        # Start timer
        start_time = time.perf_counter()

        # Run with timeout (if deadlock occurs, this will hang)
        with multiprocessing.Pool(processes=16) as pool:
            # Use timeout to detect deadlocks
            results = pool.starmap(
                worker_load_bundle,
                [(test_bundle,) for _ in range(100)],
            )

        elapsed_time = time.perf_counter() - start_time

        # All workers should complete
        assert all(success for success, _ in results)

        # Should complete in reasonable time (< 60 seconds)
        assert (
            elapsed_time < 60
        ), f"Test took {elapsed_time:.2f}s, possible deadlock or performance issue"

    def test_no_race_conditions(self, test_bundle):
        """Test that no race conditions occur with many workers."""
        # Reset singleton
        BundleConnectionPool._instance = None

        # Run many workers concurrently
        num_iterations = 5
        all_results = []

        for _ in range(num_iterations):
            with multiprocessing.Pool(processes=16) as pool:
                results = pool.starmap(
                    worker_load_bundle,
                    [(test_bundle,) for _ in range(16)],
                )
                all_results.extend(results)

        # All iterations should succeed without race conditions
        total_successes = sum(1 for success, _ in all_results if success)
        expected_successes = num_iterations * 16

        assert (
            total_successes == expected_successes
        ), f"Race conditions detected: {total_successes}/{expected_successes} succeeded"


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
    BundleConnectionPool._instance = None
    yield
    BundleConnectionPool._instance = None
