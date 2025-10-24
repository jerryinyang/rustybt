"""Layer 3 performance benchmarks: Bundle connection pooling.

This script benchmarks worker initialization time with and without bundle pooling.
Target: 84% reduction (313ms → <50ms) after first load.

Constitutional requirements:
- CR-001: Decimal precision for all numeric results
- CR-008: Zero-mock enforcement (real bundle loading)
"""

import multiprocessing
import time
from decimal import Decimal
from pathlib import Path
from typing import List, Tuple

import structlog

from rustybt.data.bundles.core import load
from rustybt.optimization.bundle_pool import BundleConnectionPool, get_bundle_from_pool
from rustybt.optimization.config import OptimizationConfig

logger = structlog.get_logger(__name__)


def worker_init_without_pool(bundle_name: str) -> Decimal:
    """Initialize worker and load bundle WITHOUT connection pooling.

    Args:
        bundle_name: Name of bundle to load

    Returns:
        Initialization time in milliseconds (Decimal)
    """
    start_time = time.perf_counter()

    # Load bundle directly (no pooling)
    bundle_data = load(bundle_name)

    elapsed_ms = Decimal(str((time.perf_counter() - start_time) * 1000))

    return elapsed_ms


def worker_init_with_pool(bundle_name: str, max_pool_size: int = 100) -> Decimal:
    """Initialize worker and load bundle WITH connection pooling.

    Args:
        bundle_name: Name of bundle to load
        max_pool_size: Maximum pool size

    Returns:
        Initialization time in milliseconds (Decimal)
    """
    start_time = time.perf_counter()

    # Load bundle from pool
    bundle_data = get_bundle_from_pool(bundle_name, max_pool_size=max_pool_size)

    elapsed_ms = Decimal(str((time.perf_counter() - start_time) * 1000))

    return elapsed_ms


def benchmark_worker_initialization(
    bundle_name: str,
    num_workers: int,
    use_pool: bool,
) -> Tuple[Decimal, List[Decimal]]:
    """Benchmark worker initialization time.

    Args:
        bundle_name: Name of bundle to load
        num_workers: Number of workers to simulate
        use_pool: Whether to use connection pooling

    Returns:
        Tuple of (mean_time_ms, all_times_ms)
    """
    times: List[Decimal] = []

    # Reset pool before benchmark if using pool
    if use_pool:
        BundleConnectionPool._instance = None

    for i in range(num_workers):
        if use_pool:
            elapsed = worker_init_with_pool(bundle_name)
        else:
            elapsed = worker_init_without_pool(bundle_name)

        times.append(elapsed)

        logger.debug(
            "worker_init_benchmark",
            worker_id=i,
            use_pool=use_pool,
            elapsed_ms=str(elapsed),
        )

    # Calculate mean
    mean_time = sum(times, Decimal(0)) / len(times)

    return mean_time, times


def benchmark_first_vs_subsequent_load(bundle_name: str, num_runs: int) -> dict:
    """Benchmark first load vs subsequent loads with pooling.

    Args:
        bundle_name: Name of bundle to load
        num_runs: Number of subsequent loads to benchmark

    Returns:
        Dictionary with benchmark results
    """
    # Reset pool
    BundleConnectionPool._instance = None

    # First load (cold start)
    first_load_time = worker_init_with_pool(bundle_name)

    logger.info(
        "first_load_benchmark",
        bundle_name=bundle_name,
        first_load_ms=str(first_load_time),
    )

    # Subsequent loads (warm cache)
    subsequent_times: List[Decimal] = []
    for i in range(num_runs):
        elapsed = worker_init_with_pool(bundle_name)
        subsequent_times.append(elapsed)

    mean_subsequent = sum(subsequent_times, Decimal(0)) / len(subsequent_times)
    max_subsequent = max(subsequent_times)
    min_subsequent = min(subsequent_times)

    logger.info(
        "subsequent_loads_benchmark",
        bundle_name=bundle_name,
        num_runs=num_runs,
        mean_ms=str(mean_subsequent),
        max_ms=str(max_subsequent),
        min_ms=str(min_subsequent),
    )

    return {
        "first_load_ms": first_load_time,
        "mean_subsequent_ms": mean_subsequent,
        "max_subsequent_ms": max_subsequent,
        "min_subsequent_ms": min_subsequent,
        "speedup_ratio": first_load_time / mean_subsequent if mean_subsequent > 0 else Decimal(0),
    }


def benchmark_scaling_with_workers(
    bundle_name: str,
    worker_counts: List[int],
) -> dict:
    """Benchmark scaling with different worker counts.

    Args:
        bundle_name: Name of bundle to load
        worker_counts: List of worker counts to test

    Returns:
        Dictionary with scaling results
    """
    results = {}

    for num_workers in worker_counts:
        logger.info(
            "scaling_benchmark_start",
            bundle_name=bundle_name,
            num_workers=num_workers,
        )

        # Benchmark without pool
        mean_without_pool, times_without = benchmark_worker_initialization(
            bundle_name=bundle_name,
            num_workers=num_workers,
            use_pool=False,
        )

        # Benchmark with pool
        mean_with_pool, times_with = benchmark_worker_initialization(
            bundle_name=bundle_name,
            num_workers=num_workers,
            use_pool=True,
        )

        # Calculate speedup
        speedup_percent = (
            ((mean_without_pool - mean_with_pool) / mean_without_pool * 100)
            if mean_without_pool > 0
            else Decimal(0)
        )

        results[num_workers] = {
            "mean_without_pool_ms": mean_without_pool,
            "mean_with_pool_ms": mean_with_pool,
            "speedup_percent": speedup_percent,
            "times_without_pool": times_without,
            "times_with_pool": times_with,
        }

        logger.info(
            "scaling_benchmark_result",
            num_workers=num_workers,
            mean_without_pool_ms=str(mean_without_pool),
            mean_with_pool_ms=str(mean_with_pool),
            speedup_percent=str(speedup_percent),
        )

    return results


def validate_layer3_targets(
    bundle_name: str,
    num_runs: int,
    config: OptimizationConfig,
) -> dict:
    """Validate Layer 3 performance targets.

    Targets:
    - Worker initialization: 313ms → <50ms (84% reduction)
    - Statistical validation: ≥10 runs, 95% CI, p<0.05

    Args:
        bundle_name: Name of bundle to load
        num_runs: Number of runs (should be ≥10)
        config: Optimization configuration

    Returns:
        Dict with validation results
    """
    logger.info(
        "layer3_validation_start",
        bundle_name=bundle_name,
        num_runs=num_runs,
    )

    # Benchmark baseline (without pool)
    baseline_mean, baseline_times = benchmark_worker_initialization(
        bundle_name=bundle_name,
        num_workers=num_runs,
        use_pool=False,
    )

    # Benchmark optimized (with pool)
    optimized_mean, optimized_times = benchmark_worker_initialization(
        bundle_name=bundle_name,
        num_workers=num_runs,
        use_pool=True,
    )

    # Calculate improvement
    improvement_percent = (
        ((baseline_mean - optimized_mean) / baseline_mean * 100)
        if baseline_mean > 0
        else Decimal(0)
    )

    # Get threshold for validation
    threshold = config.get_threshold("grid_search", "production")

    # Simple result dict (not using BenchmarkResult class which is for detailed profiling)
    result = {
        "baseline_time_ms": baseline_mean,
        "optimized_time_ms": optimized_mean,
        "improvement_percent": improvement_percent,
        "speedup_ratio": baseline_mean / optimized_mean if optimized_mean > 0 else Decimal(0),
        "num_runs": num_runs,
        "baseline_times": baseline_times,
        "optimized_times": optimized_times,
        "passed": False,  # Will be set below
    }

    # Evaluate against threshold
    passed = improvement_percent >= threshold.min_improvement_percent
    result["passed"] = passed

    logger.info(
        "layer3_validation_result",
        passed=passed,
        baseline_mean_ms=str(baseline_mean),
        optimized_mean_ms=str(optimized_mean),
        improvement_percent=str(improvement_percent),
        target_improvement_percent=str(threshold.min_improvement_percent),
    )

    # Check specific Layer 3 target (<50ms after first load)
    if optimized_mean < Decimal("50"):
        logger.info(
            "layer3_50ms_target_met",
            optimized_mean_ms=str(optimized_mean),
        )
    else:
        logger.warning(
            "layer3_50ms_target_not_met",
            optimized_mean_ms=str(optimized_mean),
            target_ms="50",
        )

    return result


def run_layer3_benchmarks(
    bundle_name: str,
    output_dir: Path,
    num_runs: int = 10,
    worker_counts: List[int] = None,
) -> dict:
    """Run complete Layer 3 benchmark suite.

    Args:
        bundle_name: Name of bundle to load
        output_dir: Directory to save results
        num_runs: Number of runs per benchmark (default: 10)
        worker_counts: List of worker counts to test (default: [2, 4, 8, 16])

    Returns:
        Dictionary with all benchmark results
    """
    if worker_counts is None:
        worker_counts = [2, 4, 8, 16]

    logger.info(
        "layer3_benchmark_suite_start",
        bundle_name=bundle_name,
        num_runs=num_runs,
        worker_counts=worker_counts,
    )

    # Create config
    config = OptimizationConfig.create_default()

    # 1. Validate Layer 3 targets
    validation_result = validate_layer3_targets(
        bundle_name=bundle_name,
        num_runs=num_runs,
        config=config,
    )

    # 2. Benchmark first vs subsequent loads
    first_vs_subsequent = benchmark_first_vs_subsequent_load(
        bundle_name=bundle_name,
        num_runs=num_runs,
    )

    # 3. Benchmark scaling with workers
    scaling_results = benchmark_scaling_with_workers(
        bundle_name=bundle_name,
        worker_counts=worker_counts,
    )

    # Compile all results
    all_results = {
        "validation": validation_result,
        "first_vs_subsequent": first_vs_subsequent,
        "scaling": scaling_results,
    }

    # Generate simple text report
    report_path = output_dir / "layer3_benchmark_report.txt"
    with open(report_path, "w") as f:
        f.write("=" * 80 + "\n")
        f.write("Layer 3: Bundle Connection Pooling Benchmarks\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Bundle: {bundle_name}\n")
        f.write(f"Baseline mean: {validation_result['baseline_time_ms']:.2f} ms\n")
        f.write(f"Optimized mean: {validation_result['optimized_time_ms']:.2f} ms\n")
        f.write(f"Improvement: {validation_result['improvement_percent']:.2f}%\n")
        f.write(f"Speedup: {validation_result['speedup_ratio']:.2f}x\n")
        f.write(f"Status: {'PASS' if validation_result['passed'] else 'FAIL'}\n")
        f.write("\n" + "=" * 80 + "\n")

    logger.info(
        "layer3_benchmark_suite_complete",
        report_path=str(report_path),
    )

    return all_results


def main():
    """Main entry point for Layer 3 benchmarks."""
    import sys

    # Configure logging
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    )

    # Parse arguments
    if len(sys.argv) < 2:
        print("Usage: python benchmark_layer3.py <bundle_name> [output_dir]")
        print("Example: python benchmark_layer3.py quandl ./benchmark-results")
        sys.exit(1)

    bundle_name = sys.argv[1]
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("benchmark-results")

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Run benchmarks
    results = run_layer3_benchmarks(
        bundle_name=bundle_name,
        output_dir=output_dir,
        num_runs=10,
        worker_counts=[2, 4, 8, 16],
    )

    # Print summary
    validation = results["validation"]
    print("\n" + "=" * 80)
    print("LAYER 3 BENCHMARK SUMMARY")
    print("=" * 80)
    print(f"Bundle: {bundle_name}")
    print(f"Baseline mean: {validation['baseline_time_ms']:.2f} ms")
    print(f"Optimized mean: {validation['optimized_time_ms']:.2f} ms")
    print(f"Improvement: {validation['improvement_percent']:.2f}%")
    print(f"Target: ≥84% (Layer 3 target)")
    print(f"Status: {'✅ PASSED' if validation['passed'] else '❌ FAILED'}")
    print("=" * 80)

    # Print first vs subsequent
    fvs = results["first_vs_subsequent"]
    print("\nFIRST VS SUBSEQUENT LOAD:")
    print(f"First load: {fvs['first_load_ms']:.2f} ms")
    print(f"Subsequent mean: {fvs['mean_subsequent_ms']:.2f} ms")
    print(f"Speedup ratio: {fvs['speedup_ratio']:.2f}x")

    # Print scaling
    print("\nSCALING WITH WORKERS:")
    for num_workers, scaling_result in results["scaling"].items():
        print(f"{num_workers} workers: {scaling_result['speedup_percent']:.2f}% speedup")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.INFO)
    main()
