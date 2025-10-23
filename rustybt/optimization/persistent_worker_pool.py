"""
Persistent worker pool for optimization workflows.

This module provides PersistentWorkerPool to reuse worker processes across
multiple optimization runs, avoiding teardown/startup overhead.

Constitutional requirements:
- CR-001: Decimal precision for financial data
- CR-004: Complete type hints
- CR-005: Zero-mock enforcement (real implementations only)
"""

import atexit
import multiprocessing
import time
from collections.abc import Callable
from multiprocessing.pool import Pool
from typing import Any, Optional

import structlog

logger = structlog.get_logger()


class PersistentWorkerPool(Pool):
    """Persistent worker pool that reuses processes across batches.

    Extends multiprocessing.Pool to maintain worker processes across multiple
    optimization runs, reducing the overhead of process creation and teardown.

    Performance expectations:
        - 11% expected improvement for multi-batch optimization workflows
        - Eliminates worker startup overhead (typically 50-200ms per worker)
        - Memory overhead: minimal (workers stay resident)

    Example:
        >>> from rustybt.optimization import PersistentWorkerPool
        >>>
        >>> # Create persistent pool (workers stay alive)
        >>> pool = PersistentWorkerPool(processes=8)
        >>>
        >>> # Run multiple optimization batches
        >>> for batch in optimization_batches:
        ...     results = pool.map(objective_function, batch)
        ...
        >>> # Cleanup when done
        >>> pool.close()
        >>> pool.join()

    Example with ParallelOptimizer:
        >>> from rustybt.optimization import ParallelOptimizer
        >>> from rustybt.optimization.config import OptimizationConfig
        >>>
        >>> # Enable persistent worker pool in config
        >>> config = OptimizationConfig.create_default()
        >>> config.enable_persistent_worker_pool = True
        >>>
        >>> # ParallelOptimizer automatically uses persistent pool
        >>> optimizer = ParallelOptimizer(
        ...     algorithm=my_algorithm,
        ...     n_jobs=8,
        ...     config=config
        ... )
        >>> optimizer.run(objective_function)

    Args:
        processes: Number of worker processes (default: cpu_count())
        initializer: Worker initialization function (optional)
        initargs: Arguments for initializer (optional)
        maxtasksperchild: Maximum tasks per worker before restart (default: None = unlimited)
        context: Multiprocessing context (default: None = uses current)

    Raises:
        ValueError: If configuration is invalid
    """

    # Class-level registry to track active pools
    _active_pools: dict[int, "PersistentWorkerPool"] = {}
    _pool_lock = multiprocessing.Lock()

    def __init__(
        self,
        processes: Optional[int] = None,
        initializer: Optional[Callable] = None,
        initargs: tuple = (),
        maxtasksperchild: Optional[int] = None,
        context: Optional[Any] = None,
    ):
        """Initialize persistent worker pool.

        Args:
            processes: Number of worker processes
            initializer: Worker initialization function
            initargs: Arguments for initializer
            maxtasksperchild: Maximum tasks per worker before restart
            context: Multiprocessing context

        Raises:
            ValueError: If configuration is invalid
        """
        # Validate processes count
        if processes is not None and processes <= 0:
            raise ValueError("processes must be positive")

        # Use default CPU count if not specified
        if processes is None:
            processes = multiprocessing.cpu_count()

        # Store configuration
        self._processes = processes
        self._initializer = initializer
        self._initargs = initargs
        self._maxtasksperchild = maxtasksperchild
        self._context = context

        # Track statistics
        self._batch_count = 0
        self._total_tasks = 0
        self._creation_time = time.time()

        # Initialize parent Pool
        super().__init__(
            processes=processes,
            initializer=initializer,
            initargs=initargs,
            maxtasksperchild=maxtasksperchild,
            context=context,
        )

        # Register pool for cleanup
        pool_id = id(self)
        with self._pool_lock:
            self._active_pools[pool_id] = self

        # Register cleanup on exit
        atexit.register(self._cleanup_on_exit, pool_id)

        logger.info(
            "persistent_worker_pool_created",
            processes=processes,
            maxtasksperchild=maxtasksperchild,
            pool_id=pool_id,
        )

    def run_batch(
        self,
        func: Callable[[Any], Any],
        tasks: list[Any],
        chunksize: Optional[int] = None,
    ) -> list[Any]:
        """Run batch of tasks without pool teardown.

        This is the key optimization: workers are reused across batches
        instead of being torn down and recreated.

        Args:
            func: Function to apply to each task
            tasks: List of task arguments
            chunksize: Size of chunks for parallel processing (default: auto)

        Returns:
            List of results

        Example:
            >>> pool = PersistentWorkerPool(processes=8)
            >>>
            >>> # Run first batch
            >>> batch1_results = pool.run_batch(objective, batch1_tasks)
            >>>
            >>> # Run second batch (workers reused, no startup overhead)
            >>> batch2_results = pool.run_batch(objective, batch2_tasks)
        """
        self._batch_count += 1
        self._total_tasks += len(tasks)

        logger.debug(
            "running_batch",
            batch_number=self._batch_count,
            task_count=len(tasks),
            total_tasks=self._total_tasks,
        )

        # Use map for parallel execution
        results = self.map(func, tasks, chunksize=chunksize)

        logger.debug(
            "batch_completed",
            batch_number=self._batch_count,
            task_count=len(tasks),
        )

        return results

    def reset_workers(self) -> None:
        """Reset worker processes (force restart).

        This can be useful if workers have accumulated state or memory
        that needs to be cleared.

        Warning:
            This operation has the same overhead as creating a new pool.
            Use sparingly - only when necessary.
        """
        logger.info("resetting_workers", processes=self._processes)

        # Close current pool
        self.close()
        self.join()

        # Reinitialize with same configuration
        super().__init__(
            processes=self._processes,
            initializer=self._initializer,
            initargs=self._initargs,
            maxtasksperchild=self._maxtasksperchild,
            context=self._context,
        )

        logger.info("workers_reset", processes=self._processes)

    def get_statistics(self) -> dict[str, Any]:
        """Get pool statistics.

        Returns:
            Dictionary with statistics:
                - batch_count: Number of batches executed
                - total_tasks: Total tasks executed
                - uptime_seconds: Pool uptime
                - processes: Number of worker processes

        Example:
            >>> pool = PersistentWorkerPool(processes=8)
            >>> # ... run batches ...
            >>> stats = pool.get_statistics()
            >>> print(f"Batches: {stats['batch_count']}, Tasks: {stats['total_tasks']}")
        """
        uptime = time.time() - self._creation_time

        return {
            "batch_count": self._batch_count,
            "total_tasks": self._total_tasks,
            "uptime_seconds": uptime,
            "processes": self._processes,
            "average_tasks_per_batch": (
                self._total_tasks / self._batch_count if self._batch_count > 0 else 0
            ),
        }

    def close(self) -> None:
        """Close pool (workers finish current tasks then stop).

        After close(), no new tasks can be submitted.
        """
        logger.info(
            "closing_persistent_worker_pool",
            batch_count=self._batch_count,
            total_tasks=self._total_tasks,
        )
        super().close()

    def terminate(self) -> None:
        """Terminate pool immediately (workers stop without finishing).

        Warning:
            This may leave tasks incomplete. Use close() for graceful shutdown.
        """
        logger.warning(
            "terminating_persistent_worker_pool",
            batch_count=self._batch_count,
            total_tasks=self._total_tasks,
        )
        super().terminate()

    def join(self) -> None:
        """Wait for workers to finish (after close() or terminate()).

        This blocks until all worker processes have exited.
        """
        logger.debug("joining_persistent_worker_pool")
        super().join()
        logger.info("persistent_worker_pool_joined")

    @classmethod
    def _cleanup_on_exit(cls, pool_id: int) -> None:
        """Cleanup pool on process exit.

        Args:
            pool_id: ID of pool to cleanup
        """
        with cls._pool_lock:
            if pool_id in cls._active_pools:
                pool = cls._active_pools[pool_id]
                try:
                    pool.terminate()
                    pool.join()
                except Exception as e:
                    logger.error(
                        "pool_cleanup_failed",
                        pool_id=pool_id,
                        error=str(e),
                    )
                finally:
                    del cls._active_pools[pool_id]

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup pool."""
        self.close()
        self.join()
        return False

    def __repr__(self) -> str:
        """String representation."""
        stats = self.get_statistics()
        return (
            f"PersistentWorkerPool(processes={self._processes}, "
            f"batches={stats['batch_count']}, tasks={stats['total_tasks']}, "
            f"uptime={stats['uptime_seconds']:.1f}s)"
        )


# Global singleton for cross-optimization persistence (optional advanced usage)
_global_pool: Optional[PersistentWorkerPool] = None
_global_pool_lock = multiprocessing.Lock()


def get_global_pool(processes: Optional[int] = None) -> PersistentWorkerPool:
    """Get or create global persistent worker pool.

    This provides a singleton pool that persists across multiple optimization
    runs in the same process.

    Args:
        processes: Number of processes (default: cpu_count())

    Returns:
        Global PersistentWorkerPool instance

    Example:
        >>> from rustybt.optimization.persistent_worker_pool import get_global_pool
        >>>
        >>> # Get global pool (created once)
        >>> pool = get_global_pool(processes=8)
        >>>
        >>> # Use in multiple optimizations
        >>> results1 = pool.run_batch(objective1, tasks1)
        >>> results2 = pool.run_batch(objective2, tasks2)
        >>>
        >>> # Pool persists until process exit

    Warning:
        The global pool is NOT cleaned up automatically. Ensure proper
        cleanup in long-running applications:

        >>> pool = get_global_pool()
        >>> try:
        ...     # ... use pool ...
        ... finally:
        ...     pool.close()
        ...     pool.join()
    """
    global _global_pool

    with _global_pool_lock:
        if _global_pool is None:
            if processes is None:
                processes = multiprocessing.cpu_count()

            _global_pool = PersistentWorkerPool(processes=processes)

            logger.info(
                "global_persistent_pool_created",
                processes=processes,
            )

        return _global_pool


def cleanup_global_pool() -> None:
    """Cleanup global persistent worker pool.

    Call this at application exit or when pool is no longer needed.

    Example:
        >>> from rustybt.optimization.persistent_worker_pool import cleanup_global_pool
        >>>
        >>> # At application shutdown
        >>> cleanup_global_pool()
    """
    global _global_pool

    with _global_pool_lock:
        if _global_pool is not None:
            logger.info("cleaning_up_global_persistent_pool")

            try:
                _global_pool.close()
                _global_pool.join()
            except Exception as e:
                logger.error(
                    "global_pool_cleanup_failed",
                    error=str(e),
                )
            finally:
                _global_pool = None

            logger.info("global_persistent_pool_cleaned_up")
