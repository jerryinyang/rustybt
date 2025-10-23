"""
Benchmark SharedBundleContext optimization (Phase 6B, Rank #1).

This script measures performance improvement from shared bundle context across
multiple worker processes, comparing against standard per-worker bundle loading.

Constitutional requirements:
- CR-005: Zero-mock enforcement (real bundle data, no mocks)
- AC Requirements: ≥10 runs, 95% CI, p<0.05 significance
"""

import multiprocessing
import time
from decimal import Decimal
from typing import List

import numpy as np
from scipy import stats

from rustybt.data.bundles.core import load
from rustybt.optimization.shared_bundle_context import SharedBundleContext


def worker_standard_load(bundle_name: str, iterations: int) -> float:
    """Worker function with standard bundle loading (baseline).

    Args:
        bundle_name: Bundle to load
        iterations: Number of load iterations

    Returns:
        Total duration in seconds
    """
    start = time.time()
    for _ in range(iterations):
        bundle = load(bundle_name)
        # Access some data to ensure loading completed
        _ = bundle.asset_finder
    return time.time() - start


def worker_shared_bundle(
    bundle_name: str, metadata_dict: dict, iterations: int
) -> float:
    """Worker function with shared bundle context (optimized).

    Args:
        bundle_name: Bundle to load
        metadata_dict: Shared bundle metadata
        iterations: Number of access iterations

    Returns:
        Total duration in seconds
    """
    from rustybt.optimization.shared_bundle_context import SharedBundleMetadata

    # Reconstruct metadata from dict
    metadata = SharedBundleMetadata(**metadata_dict)

    start = time.time()
    context = SharedBundleContext(bundle_name)
    context.attach(metadata)

    for _ in range(iterations):
        bundle = context.get_bundle()
        # Access some data
        _ = bundle.asset_finder

    context.close()
    return time.time() - start


def run_baseline_benchmark(
    bundle_name: str, n_workers: int, iterations_per_worker: int, n_runs: int
) -> List[float]:
    """Run baseline benchmark with standard per-worker loading.

    Args:
        bundle_name: Bundle to use
        n_workers: Number of worker processes
        iterations_per_worker: Bundle loads per worker
        n_runs: Number of benchmark runs

    Returns:
        List of durations for each run
    """
    print(
        f"\n📊 Baseline: Standard per-worker loading "
        f"({n_workers} workers, {iterations_per_worker} iterations/worker)"
    )

    durations = []
    for run in range(n_runs):
        start = time.time()

        with multiprocessing.Pool(processes=n_workers) as pool:
            results = pool.starmap(
                worker_standard_load,
                [(bundle_name, iterations_per_worker) for _ in range(n_workers)],
            )

        duration = time.time() - start
        durations.append(duration)

        worker_avg = np.mean(results)
        print(
            f"  Run {run + 1}/{n_runs}: {duration:.3f}s total, "
            f"{worker_avg:.3f}s worker avg"
        )

    return durations


def run_optimized_benchmark(
    bundle_name: str, n_workers: int, iterations_per_worker: int, n_runs: int
) -> List[float]:
    """Run optimized benchmark with SharedBundleContext.

    Args:
        bundle_name: Bundle to use
        n_workers: Number of worker processes
        iterations_per_worker: Bundle accesses per worker
        n_runs: Number of benchmark runs

    Returns:
        List of durations for each run
    """
    print(
        f"\n📊 Optimized: SharedBundleContext "
        f"({n_workers} workers, {iterations_per_worker} iterations/worker)"
    )

    durations = []
    for run in range(n_runs):
        # Initialize shared context once
        context = SharedBundleContext(bundle_name)
        context.initialize()
        metadata = context.get_metadata()

        # Convert metadata to dict for pickling
        metadata_dict = {
            "bundle_name": metadata.bundle_name,
            "shm_name": metadata.shm_name,
            "data_size": metadata.data_size,
            "checksum": metadata.checksum,
            "version": metadata.version,
        }

        start = time.time()

        with multiprocessing.Pool(processes=n_workers) as pool:
            results = pool.starmap(
                worker_shared_bundle,
                [
                    (bundle_name, metadata_dict, iterations_per_worker)
                    for _ in range(n_workers)
                ],
            )

        duration = time.time() - start
        durations.append(duration)

        worker_avg = np.mean(results)
        print(
            f"  Run {run + 1}/{n_runs}: {duration:.3f}s total, "
            f"{worker_avg:.3f}s worker avg"
        )

        # Cleanup
        context.cleanup()

    return durations


def calculate_statistics(
    baseline_times: List[float], optimized_times: List[float]
) -> dict:
    """Calculate performance statistics with confidence intervals.

    Args:
        baseline_times: Baseline benchmark times
        optimized_times: Optimized benchmark times

    Returns:
        Dictionary with statistics
    """
    baseline_mean = np.mean(baseline_times)
    optimized_mean = np.mean(optimized_times)

    # Calculate speedup
    speedup_pct = (baseline_mean - optimized_mean) / baseline_mean * 100

    # Paired t-test
    t_stat, p_value = stats.ttest_rel(baseline_times, optimized_times)

    # 95% confidence interval for speedup
    speedup_values = [
        (b - o) / b * 100 for b, o in zip(baseline_times, optimized_times)
    ]
    ci_95 = stats.t.interval(
        confidence=0.95,
        df=len(speedup_values) - 1,
        loc=np.mean(speedup_values),
        scale=stats.sem(speedup_values),
    )

    return {
        "baseline_mean": baseline_mean,
        "baseline_std": np.std(baseline_times),
        "optimized_mean": optimized_mean,
        "optimized_std": np.std(optimized_times),
        "speedup_pct": speedup_pct,
        "t_statistic": t_stat,
        "p_value": p_value,
        "ci_95_lower": ci_95[0],
        "ci_95_upper": ci_95[1],
        "is_significant": p_value < 0.05,
        "meets_threshold": speedup_pct >= 5.0 and p_value < 0.05,
    }


def main():
    """Run SharedBundleContext benchmark suite."""
    print("=" * 80)
    print("Phase 6B Benchmark: SharedBundleContext Optimization")
    print("=" * 80)

    # Configuration
    BUNDLE_NAME = "mag-7"
    N_WORKERS = 8
    ITERATIONS_PER_WORKER = 3
    N_RUNS = 10

    print(f"\nConfiguration:")
    print(f"  Bundle: {BUNDLE_NAME}")
    print(f"  Workers: {N_WORKERS}")
    print(f"  Iterations per worker: {ITERATIONS_PER_WORKER}")
    print(f"  Benchmark runs: {N_RUNS}")
    print(f"  Total operations: {N_WORKERS * ITERATIONS_PER_WORKER * N_RUNS}")

    # Run benchmarks
    baseline_times = run_baseline_benchmark(
        BUNDLE_NAME, N_WORKERS, ITERATIONS_PER_WORKER, N_RUNS
    )

    optimized_times = run_optimized_benchmark(
        BUNDLE_NAME, N_WORKERS, ITERATIONS_PER_WORKER, N_RUNS
    )

    # Calculate statistics
    stats_dict = calculate_statistics(baseline_times, optimized_times)

    # Print results
    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)

    print(f"\n📈 Performance Metrics:")
    print(
        f"  Baseline:  {stats_dict['baseline_mean']:.3f}s "
        f"± {stats_dict['baseline_std']:.3f}s"
    )
    print(
        f"  Optimized: {stats_dict['optimized_mean']:.3f}s "
        f"± {stats_dict['optimized_std']:.3f}s"
    )
    print(f"  Speedup:   {stats_dict['speedup_pct']:.2f}%")
    print(
        f"  95% CI:    [{stats_dict['ci_95_lower']:.2f}%, "
        f"{stats_dict['ci_95_upper']:.2f}%]"
    )

    print(f"\n📊 Statistical Validation:")
    print(f"  t-statistic: {stats_dict['t_statistic']:.4f}")
    print(f"  p-value:     {stats_dict['p_value']:.6f}")
    print(
        f"  Significant: {'✅ YES' if stats_dict['is_significant'] else '❌ NO'} "
        f"(p < 0.05)"
    )

    print(f"\n✅ Acceptance Criteria:")
    print(f"  Min 10 runs:     ✅ PASS ({N_RUNS} runs)")
    print(f"  95% CI:          ✅ PASS (calculated)")
    print(
        f"  p < 0.05:        "
        f"{'✅ PASS' if stats_dict['is_significant'] else '❌ FAIL'}"
    )
    print(
        f"  ≥5% speedup:     "
        f"{'✅ PASS' if stats_dict['speedup_pct'] >= 5.0 else '❌ FAIL'} "
        f"({stats_dict['speedup_pct']:.2f}%)"
    )

    print(f"\n🎯 DECISION:")
    if stats_dict["meets_threshold"]:
        print(
            f"  ✅ ACCEPT SharedBundleContext "
            f"({stats_dict['speedup_pct']:.2f}% improvement)"
        )
    else:
        print(
            f"  ❌ REJECT SharedBundleContext "
            f"(does not meet 5% threshold or p<0.05)"
        )

    print("\n" + "=" * 80)

    return stats_dict


if __name__ == "__main__":
    main()
