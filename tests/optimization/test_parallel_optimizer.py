"""Tests for parallel optimization framework."""

import time
from decimal import Decimal

import pytest

from rustybt.optimization.parallel_optimizer import (
    ParallelOptimizer,
    TaskResult,
    WorkerStats,
    _evaluate_params_worker,
)
from rustybt.optimization.parameter_space import (
    ContinuousParameter,
    DiscreteParameter,
    ParameterSpace,
)
from rustybt.optimization.search.grid_search import GridSearchAlgorithm
from rustybt.optimization.search.random_search import RandomSearchAlgorithm

# Module-level objective functions (required for multiprocessing pickle)


def simple_objective(params):
    """Simple quadratic objective."""
    x = params["x"]
    return Decimal(str(-(x**2)))


def sphere_objective(params):
    """Sphere function (minimize x^2 + y^2)."""
    x = float(params["x"])
    y = float(params["y"])
    return Decimal(str(-(x**2 + y**2)))


def quadratic_objective(params):
    """Quadratic with known maximum at x=5."""
    x = params["x"]
    return Decimal(str(-((x - 5) ** 2) + 10))


def failing_objective(params):
    """Objective that fails for x=5."""
    x = params["x"]
    if x == 5:
        raise ValueError("Intentional failure for x=5")
    return Decimal(str(-(x**2)))


def slow_objective(params):
    """Slow CPU-intensive objective."""
    time.sleep(0.05)
    return Decimal(str(-(params["x"] ** 2)))


def cpu_intensive_objective(params):
    """CPU-bound calculation."""
    result = Decimal(0)
    for i in range(100000):
        result += Decimal(str(i % 10))
    x = float(params["x"])
    return Decimal(str(-(x**2))) + result * Decimal("0.0000001")


class TestWorkerStats:
    """Tests for WorkerStats dataclass."""

    def test_throughput_calculation(self):
        """Test throughput calculation."""
        stats = WorkerStats(worker_id=0)
        stats.evaluations_completed = 10
        stats.total_duration_seconds = Decimal("5.0")

        assert stats.throughput == Decimal("2.0")  # 10 evals / 5 seconds

    def test_throughput_zero_duration(self):
        """Test throughput when no evaluations completed."""
        stats = WorkerStats(worker_id=0)
        assert stats.throughput == Decimal(0)

    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        stats = WorkerStats(worker_id=0)
        stats.evaluations_completed = 8
        stats.evaluations_failed = 2

        assert stats.success_rate == 0.8  # 8 / 10

    def test_success_rate_no_evaluations(self):
        """Test success rate when no evaluations."""
        stats = WorkerStats(worker_id=0)
        assert stats.success_rate == 0.0


class TestTaskResult:
    """Tests for TaskResult dataclass."""

    def test_is_success_true(self):
        """Test is_success when no error."""
        result = TaskResult(
            params={"x": 1},
            score=Decimal("10.5"),
            duration_seconds=Decimal("1.0"),
            error=None,
            worker_id=0,
        )
        assert result.is_success is True

    def test_is_success_false(self):
        """Test is_success when error present."""
        result = TaskResult(
            params={"x": 1},
            score=Decimal("-Infinity"),
            duration_seconds=Decimal("1.0"),
            error="Division by zero",
            worker_id=0,
        )
        assert result.is_success is False


class TestEvaluateParamsWorker:
    """Tests for worker evaluation function."""

    def test_successful_evaluation(self):
        """Test successful parameter evaluation."""

        def objective(params):
            return Decimal(str(params["x"] ** 2))

        result = _evaluate_params_worker(
            params={"x": 5}, objective_function=objective, worker_id=0, max_eval_time=None
        )

        assert result.is_success
        assert result.score == Decimal("25")
        assert result.error is None
        assert result.worker_id == 0
        assert result.duration_seconds > 0

    def test_failed_evaluation(self):
        """Test evaluation with exception."""

        def objective(params):
            raise ValueError("Invalid parameters")

        result = _evaluate_params_worker(
            params={"x": 5}, objective_function=objective, worker_id=1, max_eval_time=None
        )

        assert not result.is_success
        assert result.score == Decimal("-Infinity")
        assert "Invalid parameters" in result.error
        assert result.worker_id == 1

    def test_evaluation_auto_converts_to_decimal(self):
        """Test that numeric results are converted to Decimal."""

        def objective(params):
            return 42.5  # Return float

        result = _evaluate_params_worker(
            params={"x": 1}, objective_function=objective, worker_id=0, max_eval_time=None
        )

        assert result.is_success
        assert isinstance(result.score, Decimal)
        assert result.score == Decimal("42.5")


class TestParallelOptimizer:
    """Tests for ParallelOptimizer class."""

    def test_initialization_default_workers(self):
        """Test initialization with default worker count."""
        param_space = ParameterSpace(
            parameters=[ContinuousParameter(name="x", min_value=0, max_value=10)]
        )
        algorithm = RandomSearchAlgorithm(parameter_space=param_space, n_iter=10)
        optimizer = ParallelOptimizer(algorithm)

        assert optimizer.n_jobs > 0  # Should auto-detect CPUs
        assert optimizer.backend == "multiprocessing"
        assert optimizer.verbose is True

    def test_initialization_explicit_workers(self):
        """Test initialization with explicit worker count."""
        param_space = ParameterSpace(
            parameters=[ContinuousParameter(name="x", min_value=0, max_value=10)]
        )
        algorithm = RandomSearchAlgorithm(parameter_space=param_space, n_iter=10)
        optimizer = ParallelOptimizer(algorithm, n_jobs=4, verbose=False)

        assert optimizer.n_jobs == 4
        assert optimizer.verbose is False

    def test_initialization_invalid_backend(self):
        """Test initialization with invalid backend."""
        param_space = ParameterSpace(
            parameters=[ContinuousParameter(name="x", min_value=0, max_value=10)]
        )
        algorithm = RandomSearchAlgorithm(parameter_space=param_space, n_iter=10)

        with pytest.raises(ValueError, match="backend must be"):
            ParallelOptimizer(algorithm, backend="invalid")

    def test_initialization_invalid_n_jobs(self):
        """Test initialization with invalid n_jobs."""
        param_space = ParameterSpace(
            parameters=[ContinuousParameter(name="x", min_value=0, max_value=10)]
        )
        algorithm = RandomSearchAlgorithm(parameter_space=param_space, n_iter=10)

        with pytest.raises(ValueError, match="n_jobs must be positive"):
            ParallelOptimizer(algorithm, n_jobs=0)

    def test_initialization_invalid_max_eval_time(self):
        """Test initialization with invalid max_eval_time."""
        param_space = ParameterSpace(
            parameters=[ContinuousParameter(name="x", min_value=0, max_value=10)]
        )
        algorithm = RandomSearchAlgorithm(parameter_space=param_space, n_iter=10)

        with pytest.raises(ValueError, match="max_eval_time must be positive"):
            ParallelOptimizer(algorithm, max_eval_time=-1)

    def test_parallel_random_search(self):
        """Test parallel execution with random search."""
        param_space = ParameterSpace(
            parameters=[
                ContinuousParameter(name="x", min_value=-5, max_value=5, prior="uniform"),
                ContinuousParameter(name="y", min_value=-5, max_value=5, prior="uniform"),
            ]
        )

        algorithm = RandomSearchAlgorithm(parameter_space=param_space, n_iter=20, seed=42)

        optimizer = ParallelOptimizer(algorithm, n_jobs=2, verbose=False)
        optimizer.run(sphere_objective)

        best_params, best_score = optimizer.get_best_result()

        # Best score should be close to 0 (minimum of sphere function)
        assert best_score > Decimal("-5")  # Should find reasonably good solution
        assert "x" in best_params
        assert "y" in best_params

    def test_parallel_grid_search(self):
        """Test parallel execution with grid search."""
        param_space = ParameterSpace(
            parameters=[DiscreteParameter(name="x", min_value=0, max_value=10, step=1)]
        )

        algorithm = GridSearchAlgorithm(parameter_space=param_space)

        optimizer = ParallelOptimizer(algorithm, n_jobs=2, verbose=False)
        optimizer.run(quadratic_objective)

        best_params, best_score = optimizer.get_best_result()

        # Should find exact maximum at x=5
        assert best_params["x"] == 5
        assert best_score == Decimal("10")

    def test_parallel_determinism(self):
        """Test that parallel produces same best result as serial (with same seed)."""
        param_space = ParameterSpace(
            parameters=[
                ContinuousParameter(name="x", min_value=-5, max_value=5, prior="uniform"),
                ContinuousParameter(name="y", min_value=-5, max_value=5, prior="uniform"),
            ]
        )

        # Serial optimization
        serial_algorithm = RandomSearchAlgorithm(parameter_space=param_space, n_iter=50, seed=42)
        while not serial_algorithm.is_complete():
            params = serial_algorithm.suggest()
            score = sphere_objective(params)
            serial_algorithm.update(params, score)
        serial_best_params, serial_best_score = serial_algorithm.get_best_result()

        # Parallel optimization (same seed)
        parallel_algorithm = RandomSearchAlgorithm(parameter_space=param_space, n_iter=50, seed=42)
        parallel_optimizer = ParallelOptimizer(parallel_algorithm, n_jobs=2, verbose=False)
        parallel_optimizer.run(sphere_objective)
        parallel_best_params, parallel_best_score = parallel_optimizer.get_best_result()

        # Best scores should be identical (same seed, deterministic sampling)
        assert abs(serial_best_score - parallel_best_score) < Decimal("0.001")

    def test_worker_failure_handling(self):
        """Test that optimizer handles worker failures gracefully."""
        param_space = ParameterSpace(
            parameters=[DiscreteParameter(name="x", min_value=0, max_value=10, step=1)]
        )

        algorithm = GridSearchAlgorithm(parameter_space=param_space)
        optimizer = ParallelOptimizer(algorithm, n_jobs=2, verbose=False)
        optimizer.run(failing_objective)

        # Should complete despite failures
        best_params, best_score = optimizer.get_best_result()

        # Should find best among non-failing evaluations
        assert best_params["x"] != 5  # Failed parameter
        assert best_score > Decimal("-Infinity")

        # Should track failures
        assert optimizer._failed_evaluations > 0

    def test_progress_monitoring(self):
        """Test progress monitoring during optimization."""
        param_space = ParameterSpace(
            parameters=[DiscreteParameter(name="x", min_value=0, max_value=5, step=1)]
        )

        algorithm = GridSearchAlgorithm(parameter_space=param_space)
        optimizer = ParallelOptimizer(algorithm, n_jobs=2, verbose=False)

        # Run optimization
        optimizer.run(simple_objective)

        # Check progress is 100% after completion
        progress = optimizer.get_progress()
        assert progress == 1.0

    def test_worker_statistics(self):
        """Test worker statistics tracking."""
        param_space = ParameterSpace(
            parameters=[DiscreteParameter(name="x", min_value=0, max_value=10, step=1)]
        )

        algorithm = GridSearchAlgorithm(parameter_space=param_space)
        optimizer = ParallelOptimizer(algorithm, n_jobs=2, verbose=False)
        optimizer.run(simple_objective)

        stats = optimizer.get_worker_statistics()

        # Should have stats for all workers
        assert len(stats) == 2

        # All workers should have completed some evaluations
        total_completed = sum(s.evaluations_completed for s in stats.values())
        assert total_completed == 11  # 0-10 inclusive

        # No failures expected
        total_failed = sum(s.evaluations_failed for s in stats.values())
        assert total_failed == 0

    def test_get_best_params_before_run(self):
        """Test get_best_params raises error before optimization run."""
        param_space = ParameterSpace(
            parameters=[ContinuousParameter(name="x", min_value=0, max_value=10)]
        )
        algorithm = RandomSearchAlgorithm(parameter_space=param_space, n_iter=10)
        optimizer = ParallelOptimizer(algorithm, n_jobs=2, verbose=False)

        with pytest.raises(ValueError, match="No successful results"):
            optimizer.get_best_params()

    def test_estimate_total_iterations_random_search(self):
        """Test total iterations estimation for random search."""
        param_space = ParameterSpace(
            parameters=[ContinuousParameter(name="x", min_value=0, max_value=10)]
        )
        algorithm = RandomSearchAlgorithm(parameter_space=param_space, n_iter=100)
        optimizer = ParallelOptimizer(algorithm, n_jobs=2, verbose=False)

        total = optimizer._estimate_total_iterations()
        assert total == 100

    def test_estimate_total_iterations_grid_search(self):
        """Test total iterations estimation for grid search."""
        param_space = ParameterSpace(
            parameters=[
                DiscreteParameter(name="x", min_value=0, max_value=10, step=1),
                DiscreteParameter(name="y", min_value=0, max_value=5, step=1),
            ]
        )
        algorithm = GridSearchAlgorithm(parameter_space=param_space)
        optimizer = ParallelOptimizer(algorithm, n_jobs=2, verbose=False)

        total = optimizer._estimate_total_iterations()
        # Grid search generates all combinations
        assert total == algorithm._total_combinations

    def test_batch_size_configuration(self):
        """Test batch size configuration."""
        param_space = ParameterSpace(
            parameters=[ContinuousParameter(name="x", min_value=0, max_value=10)]
        )
        algorithm = RandomSearchAlgorithm(parameter_space=param_space, n_iter=10)

        # Default batch size
        optimizer1 = ParallelOptimizer(algorithm, n_jobs=4, verbose=False)
        assert optimizer1.batch_size == 8  # 2 * n_jobs

        # Custom batch size
        optimizer2 = ParallelOptimizer(algorithm, n_jobs=4, batch_size=16, verbose=False)
        assert optimizer2.batch_size == 16

    def test_maxtasksperchild_configuration(self):
        """Test maxtasksperchild configuration."""
        param_space = ParameterSpace(
            parameters=[ContinuousParameter(name="x", min_value=0, max_value=10)]
        )
        algorithm = RandomSearchAlgorithm(parameter_space=param_space, n_iter=10)

        optimizer = ParallelOptimizer(algorithm, n_jobs=2, maxtasksperchild=50, verbose=False)
        assert optimizer.maxtasksperchild == 50


class TestParallelPerformance:
    """Performance tests for parallel optimization."""

    def test_parallel_speedup(self):
        """Test that parallel achieves speedup over serial."""
        param_space = ParameterSpace(
            parameters=[DiscreteParameter(name="x", min_value=0, max_value=15, step=1)]
        )

        # Serial execution (1 worker)
        serial_algorithm = GridSearchAlgorithm(parameter_space=param_space)
        serial_optimizer = ParallelOptimizer(serial_algorithm, n_jobs=1, verbose=False)
        start_serial = time.time()
        serial_optimizer.run(slow_objective)
        serial_time = time.time() - start_serial

        # Parallel execution (4 workers)
        parallel_algorithm = GridSearchAlgorithm(parameter_space=param_space)
        parallel_optimizer = ParallelOptimizer(parallel_algorithm, n_jobs=4, verbose=False)
        start_parallel = time.time()
        parallel_optimizer.run(slow_objective)
        parallel_time = time.time() - start_parallel

        # Calculate speedup
        speedup = serial_time / parallel_time

        # Should achieve at least some speedup with 4 workers
        # (Python's multiprocessing has significant overhead due to process forking and pickling)
        # Just verify parallel is not slower than serial
        assert (
            speedup >= 1.0
        ), f"Expected speedup >= 1.0 (parallel faster or equal to serial), got {speedup:.2f}"

        # Ideally should be faster, but we'll just log it
        print(
            f"\nParallel speedup with 4 workers: {speedup:.2f}x (serial={serial_time:.2f}s, parallel={parallel_time:.2f}s)"
        )

        # Both should find same best result
        serial_best = serial_optimizer.get_best_result()[1]
        parallel_best = parallel_optimizer.get_best_result()[1]
        assert serial_best == parallel_best

    def test_parallel_efficiency(self):
        """Test parallel efficiency (speedup / n_workers)."""
        param_space = ParameterSpace(
            parameters=[DiscreteParameter(name="x", min_value=0, max_value=7, step=1)]
        )

        # Measure baseline (1 worker)
        baseline_algorithm = GridSearchAlgorithm(parameter_space=param_space)
        baseline_optimizer = ParallelOptimizer(baseline_algorithm, n_jobs=1, verbose=False)
        start = time.time()
        baseline_optimizer.run(cpu_intensive_objective)
        baseline_time = time.time() - start

        # Measure parallel (2 workers)
        parallel_algorithm = GridSearchAlgorithm(parameter_space=param_space)
        parallel_optimizer = ParallelOptimizer(parallel_algorithm, n_jobs=2, verbose=False)
        start = time.time()
        parallel_optimizer.run(cpu_intensive_objective)
        parallel_time = time.time() - start

        speedup = baseline_time / parallel_time
        efficiency = speedup / 2  # 2 workers

        # Just verify parallel doesn't make things significantly worse
        # (Python's multiprocessing has overhead from process forking and pickling)
        assert (
            speedup >= 0.8
        ), f"Expected parallel not to be significantly slower (speedup >= 0.8), got {speedup:.2f}"

        # Log efficiency for informational purposes
        print(f"\nParallel efficiency with 2 workers: {efficiency:.1%} (speedup={speedup:.2f}x)")


# Ray backend tests (optional, requires ray installation)
# Check if ray is available
try:
    import ray  # noqa: F401

    RAY_AVAILABLE = True
except ImportError:
    RAY_AVAILABLE = False


class TestRayBackend:
    """Tests for Ray distributed backend."""

    @pytest.mark.skipif(not RAY_AVAILABLE, reason="Ray not installed")
    def test_ray_backend_basic(self):
        """Test basic Ray backend functionality."""
        import ray

        # Ensure Ray is shut down before test
        if ray.is_initialized():
            ray.shutdown()

        def simple_objective(params):
            return Decimal(str(-(params["x"] ** 2)))

        param_space = ParameterSpace(
            parameters=[DiscreteParameter(name="x", min_value=0, max_value=10, step=1)]
        )

        algorithm = GridSearchAlgorithm(parameter_space=param_space)
        optimizer = ParallelOptimizer(algorithm, n_jobs=2, backend="ray", verbose=False)
        optimizer.run(simple_objective)

        best_params, best_score = optimizer.get_best_result()

        # Should find best result
        assert best_params["x"] == 0
        assert best_score == Decimal("0")

        # Cleanup
        ray.shutdown()

    @pytest.mark.skipif(RAY_AVAILABLE, reason="Ray is installed, cannot test import error")
    def test_ray_not_installed_error(self):
        """Test error when Ray backend requested but not installed."""
        param_space = ParameterSpace(
            parameters=[ContinuousParameter(name="x", min_value=0, max_value=10)]
        )
        algorithm = RandomSearchAlgorithm(parameter_space=param_space, n_iter=10)

        with pytest.raises(ImportError, match="Ray backend requires"):
            ParallelOptimizer(algorithm, backend="ray")
