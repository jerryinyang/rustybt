"""
Benchmark PersistentWorkerPool optimization (Phase 6B, Rank #5).

This script measures performance improvement from worker process reuse across
multiple batches, comparing against standard Pool recreation overhead.

Constitutional requirements:
- CR-005: Zero-mock enforcement (real bundle data, no mocks)
- AC Requirements: ≥10 runs, 95% CI, p<0.05 significance
"""

import multiprocessing
import time
from typing import List

import numpy as np
from scipy import stats

from rustybt.data.bundles.core import load
from rustybt.optimization.persistent_worker_pool import PersistentWorkerPool


def simple_backtest_task(bundle_name: str, asset_idx: int) -> float:
    """Simulate a simple backtest task.

    Args:
        bundle_name: Bundle to use
        asset_idx: Asset index to process

    Returns:
        Simulated metric value
    """
    # Load bundle (or reuse from worker cache)
    bundle = load(bundle_name)

    # Simulate computation
    result = 0.0
    for i in range(1000):
        result += (asset_idx + i) / 1000.0

    return result


def run_baseline_benchmark(
    bundle_name: str,
    n_workers: int,
    n_batches: int,
    tasks_per_batch: int,
    n_runs: int,
) -> List[float]:
    """Run baseline benchmark with standard Pool (recreation per batch).

    Args:
        bundle_name: Bundle to use
        n_workers: Number of worker processes
        n_batches: Number of batches
        tasks_per_batch: Tasks per batch
        n_runs: Number of benchmark runs

    Returns:
        List of durations for each run
    """
    print(
        f"\n📊 Baseline: Standard Pool (recreation per batch) "
        f"({n_workers} workers, {n_batches} batches × {tasks_per_batch} tasks)"
    )

    durations = []
    for run in range(n_runs):
        start = time.time()

        for batch_idx in range(n_batches):
            # Create new pool for each batch (baseline overhead)
            with multiprocessing.Pool(processes=n_workers) as pool:
                tasks = [
                    (bundle_name, batch_idx * tasks_per_batch + i)
                    for i in range(tasks_per_batch)
                ]
                _ = pool.starmap(simple_backtest_task, tasks)

        duration = time.time() - start
        durations.append(duration)

        print(f"  Run {run + 1}/{n_runs}: {duration:.3f}s")

    return durations


def run_optimized_benchmark(
    bundle_name: str,
    n_workers: int,
    n_batches: int,
    tasks_per_batch: int,
    n_runs: int,
) -> List[float]:
    """Run optimized benchmark with PersistentWorkerPool.

    Args:
        bundle_name: Bundle to use
        n_workers: Number of worker processes
        n_batches: Number of batches
        tasks_per_batch: Tasks per batch
        n_runs: Number of benchmark runs

    Returns:
        List of durations for each run
    """
    print(
        f"\n📊 Optimized: PersistentWorkerPool (worker reuse) "
        f"({n_workers} workers, {n_batches} batches × {tasks_per_batch} tasks)"
    )

    durations = []
    for run in range(n_runs):
        start = time.time()

        # Create persistent pool once
        with PersistentWorkerPool(processes=n_workers) as pool:
            for batch_idx in range(n_batches):
                tasks = [
                    (bundle_name, batch_idx * tasks_per_batch + i)
                    for i in range(tasks_per_batch)
                ]
                # Use starmap for tuple arguments
                _ = pool.starmap(simple_backtest_task, tasks)

        duration = time.time() - start
        durations.append(duration)

        print(f"  Run {run + 1}/{n_runs}: {duration:.3f}s")

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
    """Run PersistentWorkerPool benchmark suite."""
    print("=" * 80)
    print("Phase 6B Benchmark: PersistentWorkerPool Optimization")
    print("=" * 80)

    # Configuration
    BUNDLE_NAME = "mag-7"
    N_WORKERS = 8
    N_BATCHES = 5  # Number of batches to process
    TASKS_PER_BATCH = 20  # Tasks per batch
    N_RUNS = 10  # Benchmark runs for statistical significance

    print(f"\nConfiguration:")
    print(f"  Bundle: {BUNDLE_NAME}")
    print(f"  Workers: {N_WORKERS}")
    print(f"  Batches: {N_BATCHES}")
    print(f"  Tasks per batch: {TASKS_PER_BATCH}")
    print(f"  Benchmark runs: {N_RUNS}")
    print(f"  Total tasks: {N_BATCHES * TASKS_PER_BATCH * N_RUNS}")

    # Run benchmarks
    baseline_times = run_baseline_benchmark(
        BUNDLE_NAME, N_WORKERS, N_BATCHES, TASKS_PER_BATCH, N_RUNS
    )

    optimized_times = run_optimized_benchmark(
        BUNDLE_NAME, N_WORKERS, N_BATCHES, TASKS_PER_BATCH, N_RUNS
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
            f"  ✅ ACCEPT PersistentWorkerPool "
            f"({stats_dict['speedup_pct']:.2f}% improvement)"
        )
    else:
        print(
            f"  ❌ REJECT PersistentWorkerPool "
            f"(does not meet 5% threshold or p<0.05)"
        )

    print("\n" + "=" * 80)

    return stats_dict


if __name__ == "__main__":
    main()
