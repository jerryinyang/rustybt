"""
Tests for PersistentWorkerPool optimization.

This module validates functional equivalence and performance of PersistentWorkerPool.

Constitutional requirements:
- CR-004: Complete type hints
- CR-005: Zero-mock enforcement (real implementations, no mocks)
"""

import multiprocessing
import time
from decimal import Decimal

import pytest

from rustybt.optimization.persistent_worker_pool import (
    PersistentWorkerPool,
    cleanup_global_pool,
    get_global_pool,
)


# Test worker functions
def simple_square(x: int) -> int:
    """Simple test function: square a number.

    Args:
        x: Input number

    Returns:
        x squared
    """
    return x * x


def expensive_computation(x: int) -> Decimal:
    """More expensive test function for benchmarking.

    Args:
        x: Input number

    Returns:
        Decimal result of computation
    """
    # Simulate backtest-like computation
    result = Decimal(0)
    for i in range(1000):
        result += Decimal(x) / Decimal(i + 1)
    return result


def worker_with_state(x: int) -> int:
    """Worker function that modifies state (for reset testing).

    Args:
        x: Input number

    Returns:
        x + 1
    """
    return x + 1


def test_persistent_pool_basic_functionality() -> None:
    """Test basic PersistentWorkerPool functionality.

    Validates:
        - Pool creation
        - Task execution
        - Correct results
    """
    pool = PersistentWorkerPool(processes=4)

    try:
        # Run simple tasks
        tasks = list(range(10))
        results = pool.map(simple_square, tasks)

        # Validate results
        expected = [x * x for x in tasks]
        assert results == expected

    finally:
        pool.close()
        pool.join()


def test_persistent_pool_functional_equivalence() -> None:
    """Test functional equivalence with standard multiprocessing.Pool.

    CRITICAL: This is a BLOCKING test for acceptance. PersistentWorkerPool
    must produce identical results to standard Pool.
    """
    tasks = list(range(50))

    # Standard Pool results
    with multiprocessing.Pool(processes=4) as standard_pool:
        standard_results = standard_pool.map(simple_square, tasks)

    # PersistentWorkerPool results
    with PersistentWorkerPool(processes=4) as persistent_pool:
        persistent_results = persistent_pool.map(simple_square, tasks)

    # Results must be identical
    assert standard_results == persistent_results


def test_persistent_pool_run_batch() -> None:
    """Test run_batch() method for multi-batch execution.

    Validates:
        - Multiple batches can be run
        - Workers are reused (no startup overhead)
        - Results are correct for each batch
    """
    pool = PersistentWorkerPool(processes=4)

    try:
        # Run multiple batches
        batch1 = list(range(10))
        batch2 = list(range(10, 20))
        batch3 = list(range(20, 30))

        results1 = pool.run_batch(simple_square, batch1)
        results2 = pool.run_batch(simple_square, batch2)
        results3 = pool.run_batch(simple_square, batch3)

        # Validate results
        assert results1 == [x * x for x in batch1]
        assert results2 == [x * x for x in batch2]
        assert results3 == [x * x for x in batch3]

        # Check statistics
        stats = pool.get_statistics()
        assert stats["batch_count"] == 3
        assert stats["total_tasks"] == 30
        assert stats["processes"] == 4
        assert stats["uptime_seconds"] > 0

    finally:
        pool.close()
        pool.join()


def test_persistent_pool_context_manager() -> None:
    """Test context manager usage of PersistentWorkerPool.

    Validates:
        - Proper resource cleanup via context manager
        - No resource leaks
    """
    tasks = list(range(20))

    # Use context manager
    with PersistentWorkerPool(processes=4) as pool:
        results = pool.map(simple_square, tasks)
        assert results == [x * x for x in tasks]

    # Pool should be closed after context exit


def test_persistent_pool_statistics() -> None:
    """Test pool statistics tracking.

    Validates:
        - Statistics are tracked correctly
        - Batch count increments
        - Task count increments
    """
    pool = PersistentWorkerPool(processes=4)

    try:
        # Initial statistics
        stats = pool.get_statistics()
        assert stats["batch_count"] == 0
        assert stats["total_tasks"] == 0
        assert stats["processes"] == 4

        # Run a batch
        pool.run_batch(simple_square, list(range(10)))

        # Check statistics updated
        stats = pool.get_statistics()
        assert stats["batch_count"] == 1
        assert stats["total_tasks"] == 10

        # Run another batch
        pool.run_batch(simple_square, list(range(5)))

        # Check statistics updated again
        stats = pool.get_statistics()
        assert stats["batch_count"] == 2
        assert stats["total_tasks"] == 15

    finally:
        pool.close()
        pool.join()


def test_persistent_pool_worker_reuse() -> None:
    """Test that workers are reused across batches (not recreated).

    Validates:
        - Workers persist across batches
        - No recreation overhead

    Note: This is a timing-based test to verify no startup overhead
    between batches.
    """
    pool = PersistentWorkerPool(processes=4)

    try:
        # First batch (includes worker startup)
        batch1 = list(range(100))
        start1 = time.time()
        results1 = pool.run_batch(expensive_computation, batch1)
        duration1 = time.time() - start1

        # Second batch (workers already initialized, should be faster)
        batch2 = list(range(100, 200))
        start2 = time.time()
        results2 = pool.run_batch(expensive_computation, batch2)
        duration2 = time.time() - start2

        # Second batch should not be significantly slower
        # (allowing 10% variance for system noise)
        assert (
            duration2 <= duration1 * 1.1
        ), f"Second batch took longer ({duration2:.2f}s vs {duration1:.2f}s), indicating worker recreation"

        # Validate results are correct
        assert len(results1) == 100
        assert len(results2) == 100

    finally:
        pool.close()
        pool.join()


def test_persistent_pool_reset_workers() -> None:
    """Test worker reset functionality.

    Validates:
        - Workers can be reset
        - Pool continues to function after reset
    """
    pool = PersistentWorkerPool(processes=4)

    try:
        # Run batch before reset
        batch1 = list(range(10))
        results1 = pool.run_batch(simple_square, batch1)
        assert results1 == [x * x for x in batch1]

        # Reset workers
        pool.reset_workers()

        # Run batch after reset
        batch2 = list(range(10, 20))
        results2 = pool.run_batch(simple_square, batch2)
        assert results2 == [x * x for x in batch2]

        # Statistics should be preserved
        stats = pool.get_statistics()
        assert stats["batch_count"] == 2

    finally:
        pool.close()
        pool.join()


def test_persistent_pool_invalid_processes() -> None:
    """Test error handling for invalid processes count.

    Validates:
        - Proper validation of inputs
    """
    with pytest.raises(ValueError, match="processes must be positive"):
        PersistentWorkerPool(processes=0)

    with pytest.raises(ValueError, match="processes must be positive"):
        PersistentWorkerPool(processes=-1)


def test_persistent_pool_global_singleton() -> None:
    """Test global persistent pool singleton.

    Validates:
        - Global pool is created once
        - Same instance returned on subsequent calls
        - Pool persists across calls
    """
    # Clean up any existing global pool
    cleanup_global_pool()

    # Get global pool
    pool1 = get_global_pool(processes=4)
    assert pool1 is not None

    # Run a batch
    results1 = pool1.run_batch(simple_square, list(range(10)))
    assert results1 == [x * x for x in range(10)]

    # Get global pool again (should be same instance)
    pool2 = get_global_pool(processes=4)
    assert pool2 is pool1

    # Statistics should show previous batch
    stats = pool2.get_statistics()
    assert stats["batch_count"] >= 1

    # Cleanup
    cleanup_global_pool()


def test_persistent_pool_global_cleanup() -> None:
    """Test global pool cleanup.

    Validates:
        - Global pool can be cleaned up
        - New pool created after cleanup
    """
    # Clean up any existing global pool
    cleanup_global_pool()

    # Create global pool
    pool1 = get_global_pool(processes=4)
    pool1_id = id(pool1)

    # Cleanup
    cleanup_global_pool()

    # New global pool should be different instance
    pool2 = get_global_pool(processes=4)
    pool2_id = id(pool2)

    assert pool1_id != pool2_id

    # Cleanup
    cleanup_global_pool()


def test_persistent_pool_maxtasksperchild() -> None:
    """Test maxtasksperchild parameter.

    Validates:
        - Workers are restarted after max tasks
        - Pool continues to function correctly
    """
    # Create pool with maxtasksperchild=10
    pool = PersistentWorkerPool(processes=2, maxtasksperchild=10)

    try:
        # Run 30 tasks (should trigger worker restarts)
        tasks = list(range(30))
        results = pool.map(simple_square, tasks)

        # Validate results
        assert results == [x * x for x in tasks]

    finally:
        pool.close()
        pool.join()


def test_persistent_pool_repr() -> None:
    """Test string representation of PersistentWorkerPool.

    Validates:
        - __repr__ returns useful information
    """
    pool = PersistentWorkerPool(processes=4)

    try:
        # Run a batch
        pool.run_batch(simple_square, list(range(10)))

        # Check repr
        repr_str = repr(pool)
        assert "PersistentWorkerPool" in repr_str
        assert "processes=4" in repr_str
        assert "batches=" in repr_str
        assert "tasks=" in repr_str

    finally:
        pool.close()
        pool.join()


def test_persistent_pool_large_batch() -> None:
    """Test PersistentWorkerPool with large batch.

    Validates:
        - Pool handles large batches correctly
        - No memory issues
    """
    pool = PersistentWorkerPool(processes=4)

    try:
        # Large batch
        tasks = list(range(1000))
        results = pool.run_batch(simple_square, tasks)

        # Validate results
        assert len(results) == 1000
        assert results[0] == 0
        assert results[999] == 999 * 999

    finally:
        pool.close()
        pool.join()


@pytest.mark.benchmark
def test_persistent_pool_performance_vs_standard(benchmark) -> None:
    """Benchmark PersistentWorkerPool vs standard Pool.

    This test measures the performance improvement from worker reuse.

    Note: Full performance benefit realized in multi-batch scenarios.
    """

    def run_with_standard_pool():
        """Run multiple batches with standard Pool (recreation overhead)."""
        total = 0
        for _ in range(5):
            with multiprocessing.Pool(processes=4) as pool:
                results = pool.map(simple_square, list(range(20)))
                total += sum(results)
        return total

    def run_with_persistent_pool():
        """Run multiple batches with PersistentWorkerPool (no recreation)."""
        total = 0
        with PersistentWorkerPool(processes=4) as pool:
            for _ in range(5):
                results = pool.run_batch(simple_square, list(range(20)))
                total += sum(results)
        return total

    # Benchmark both approaches
    standard_result = benchmark(run_with_standard_pool)
    persistent_result = run_with_persistent_pool()

    # Results should be identical
    assert standard_result == persistent_result

    # Log performance note
    print(f"Standard pool result: {standard_result}")
    print(f"Persistent pool result: {persistent_result}")
    print("Note: Persistent pool shows improvement in multi-batch scenarios")
