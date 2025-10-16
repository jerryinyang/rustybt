"""Example: Parallel optimization with multiple search algorithms.

This example demonstrates how to use ParallelOptimizer to speed up
optimization campaigns by distributing evaluations across multiple CPU cores.
"""

import time
from decimal import Decimal

from rustybt.optimization import ParallelOptimizer
from rustybt.optimization.parameter_space import (
    CategoricalParameter,
    ContinuousParameter,
    DiscreteParameter,
    ParameterSpace,
)
from rustybt.optimization.search.bayesian_search import BayesianSearchAlgorithm
from rustybt.optimization.search.grid_search import GridSearchAlgorithm
from rustybt.optimization.search.random_search import RandomSearchAlgorithm


# Example 1: CPU-intensive objective function
def cpu_intensive_backtest(params):
    """Simulate CPU-intensive backtest.

    This represents a realistic backtest that takes significant time to compute.

    Args:
        params: Strategy parameters

    Returns:
        Sharpe ratio as Decimal
    """
    lookback = params["lookback"]
    threshold = float(params["threshold"])

    # Simulate computation time
    time.sleep(0.1)

    # Simple function for demonstration (replace with real backtest)
    # Optimal around lookback=50, threshold=0.02
    lookback_penalty = abs(lookback - 50) / 100
    threshold_penalty = abs(threshold - 0.02) * 10

    sharpe = Decimal("2.0") - Decimal(str(lookback_penalty)) - Decimal(str(threshold_penalty))

    return sharpe


# Example 2: Define parameter space
def create_parameter_space():
    """Create parameter space for strategy optimization.

    Returns:
        ParameterSpace instance
    """
    return ParameterSpace(
        parameters=[
            DiscreteParameter(
                name="lookback",
                min_value=10,
                max_value=100,
                step=10,
                description="Lookback period for moving average",
            ),
            ContinuousParameter(
                name="threshold",
                min_value=0.001,
                max_value=0.1,
                prior="log-uniform",
                description="Signal threshold",
            ),
            CategoricalParameter(
                name="aggregation",
                choices=["mean", "median", "ewm"],
                description="Price aggregation method",
            ),
        ]
    )


# Example 3: Parallel Random Search
def example_parallel_random_search():
    """Demonstrate parallel random search optimization."""
    print("=" * 80)
    print("Example 1: Parallel Random Search")
    print("=" * 80)

    param_space = create_parameter_space()

    # Create random search algorithm
    algorithm = RandomSearchAlgorithm(
        parameter_space=param_space,
        n_iter=50,  # 50 random samples
        seed=42,
    )

    # Wrap with parallel optimizer (use 4 workers)
    parallel_opt = ParallelOptimizer(
        algorithm=algorithm,
        n_jobs=4,  # Use 4 CPU cores
        verbose=True,  # Show progress bar
    )

    # Run optimization
    print("\nRunning parallel random search with 4 workers...")
    start_time = time.time()
    parallel_opt.run(cpu_intensive_backtest)
    duration = time.time() - start_time

    # Get results
    best_params, best_score = parallel_opt.get_best_result()
    print(f"\nOptimization completed in {duration:.1f} seconds")
    print(f"Best Sharpe Ratio: {best_score:.4f}")
    print(f"Best Parameters: {best_params}")

    # Show worker statistics
    print("\nWorker Statistics:")
    worker_stats = parallel_opt.get_worker_statistics()
    for worker_id, stats in worker_stats.items():
        print(
            f"  Worker {worker_id}: {stats.evaluations_completed} evals, "
            f"throughput={stats.throughput:.2f} eval/sec, "
            f"success_rate={stats.success_rate:.1%}"
        )


# Example 4: Parallel Grid Search
def example_parallel_grid_search():
    """Demonstrate parallel grid search optimization."""
    print("\n" + "=" * 80)
    print("Example 2: Parallel Grid Search")
    print("=" * 80)

    # Create smaller parameter space for grid search
    param_space = ParameterSpace(
        parameters=[
            DiscreteParameter(name="lookback", min_value=20, max_value=80, step=20),
            ContinuousParameter(name="threshold", min_value=0.01, max_value=0.05, prior="uniform"),
        ]
    )

    # Create grid search algorithm
    algorithm = GridSearchAlgorithm(parameter_space=param_space)

    # Parallel optimizer with 8 workers
    parallel_opt = ParallelOptimizer(
        algorithm=algorithm,
        n_jobs=8,
        verbose=True,
    )

    print("\nRunning parallel grid search with 8 workers...")
    start_time = time.time()
    parallel_opt.run(cpu_intensive_backtest)
    duration = time.time() - start_time

    best_params, best_score = parallel_opt.get_best_result()
    print(f"\nOptimization completed in {duration:.1f} seconds")
    print(f"Best Sharpe Ratio: {best_score:.4f}")
    print(f"Best Parameters: {best_params}")


# Example 5: Parallel Bayesian Optimization
def example_parallel_bayesian_optimization():
    """Demonstrate parallel Bayesian optimization."""
    print("\n" + "=" * 80)
    print("Example 3: Parallel Bayesian Optimization")
    print("=" * 80)

    param_space = ParameterSpace(
        parameters=[
            ContinuousParameter(name="lookback", min_value=10, max_value=100, prior="uniform"),
            ContinuousParameter(
                name="threshold", min_value=0.001, max_value=0.1, prior="log-uniform"
            ),
        ]
    )

    # Create Bayesian search algorithm
    algorithm = BayesianSearchAlgorithm(
        parameter_space=param_space,
        n_iter=30,
        n_initial_points=10,
        acquisition_function="ei",  # Expected Improvement
        seed=42,
    )

    # Parallel optimizer with batch evaluation
    parallel_opt = ParallelOptimizer(
        algorithm=algorithm,
        n_jobs=4,
        batch_size=8,  # Evaluate 8 points in parallel
        verbose=True,
    )

    print("\nRunning parallel Bayesian optimization with 4 workers...")
    start_time = time.time()
    parallel_opt.run(cpu_intensive_backtest)
    duration = time.time() - start_time

    best_params, best_score = parallel_opt.get_best_result()
    print(f"\nOptimization completed in {duration:.1f} seconds")
    print(f"Best Sharpe Ratio: {best_score:.4f}")
    print(f"Best Parameters: {best_params}")


# Example 6: Speedup comparison
def example_speedup_comparison():
    """Compare serial vs parallel performance."""
    print("\n" + "=" * 80)
    print("Example 4: Speedup Comparison (Serial vs Parallel)")
    print("=" * 80)

    param_space = ParameterSpace(
        parameters=[DiscreteParameter(name="lookback", min_value=10, max_value=100, step=10)]
    )

    # Serial execution (1 worker)
    print("\nRunning serial optimization (1 worker)...")
    serial_algorithm = GridSearchAlgorithm(parameter_space=param_space)
    serial_opt = ParallelOptimizer(serial_algorithm, n_jobs=1, verbose=False)

    start_serial = time.time()
    serial_opt.run(cpu_intensive_backtest)
    serial_time = time.time() - start_serial

    # Parallel execution (4 workers)
    print("Running parallel optimization (4 workers)...")
    parallel_algorithm = GridSearchAlgorithm(parameter_space=param_space)
    parallel_opt = ParallelOptimizer(parallel_algorithm, n_jobs=4, verbose=False)

    start_parallel = time.time()
    parallel_opt.run(cpu_intensive_backtest)
    parallel_time = time.time() - start_parallel

    # Calculate speedup
    speedup = serial_time / parallel_time
    efficiency = speedup / 4

    print("\nResults:")
    print(f"  Serial time:     {serial_time:.1f} seconds")
    print(f"  Parallel time:   {parallel_time:.1f} seconds")
    print(f"  Speedup:         {speedup:.2f}×")
    print(f"  Efficiency:      {efficiency:.1%} (speedup / n_workers)")

    # Verify same results
    serial_best = serial_opt.get_best_result()[1]
    parallel_best = parallel_opt.get_best_result()[1]
    print(f"\n  Serial best:     {serial_best:.4f}")
    print(f"  Parallel best:   {parallel_best:.4f}")
    print(f"  Match:           {'✓' if serial_best == parallel_best else '✗'}")


# Example 7: Resource limits
def example_resource_limits():
    """Demonstrate resource limit configuration."""
    print("\n" + "=" * 80)
    print("Example 5: Resource Limits Configuration")
    print("=" * 80)

    param_space = ParameterSpace(
        parameters=[DiscreteParameter(name="lookback", min_value=10, max_value=50, step=10)]
    )

    algorithm = GridSearchAlgorithm(parameter_space=param_space)

    # Configure resource limits
    parallel_opt = ParallelOptimizer(
        algorithm=algorithm,
        n_jobs=4,  # Limit to 4 workers
        max_eval_time=5.0,  # Timeout after 5 seconds per evaluation
        maxtasksperchild=10,  # Restart workers every 10 tasks (prevent memory leaks)
        batch_size=8,  # Submit 8 tasks at a time
        verbose=True,
    )

    print("\nConfiguration:")
    print(f"  Workers:           {parallel_opt.n_jobs}")
    print(f"  Max eval time:     {parallel_opt.max_eval_time}s")
    print(f"  Batch size:        {parallel_opt.batch_size}")
    print(f"  Tasks per worker:  {parallel_opt.maxtasksperchild}")

    print("\nRunning optimization with resource limits...")
    parallel_opt.run(cpu_intensive_backtest)

    best_params, best_score = parallel_opt.get_best_result()
    print(f"\nBest Sharpe Ratio: {best_score:.4f}")
    print(f"Best Parameters: {best_params}")


if __name__ == "__main__":
    # Run all examples
    example_parallel_random_search()
    example_parallel_grid_search()
    example_parallel_bayesian_optimization()
    example_speedup_comparison()
    example_resource_limits()

    print("\n" + "=" * 80)
    print("All examples completed!")
    print("=" * 80)
