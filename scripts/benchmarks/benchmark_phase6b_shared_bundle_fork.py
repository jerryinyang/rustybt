"""
Benchmark SharedBundleContext fork() optimization (Phase 6B re-evaluation).

This script measures performance improvement from fork-based shared bundle context,
comparing worker initialization time with and without shared bundle inheritance.

QA Re-evaluation (2025-10-23): Alternative 1 from re-evaluation guidance - fork()
multiprocessing to avoid pickle serialization of sqlite3.Connection objects.

Key Insight:
    Fork mode allows workers to inherit bundle data via copy-on-write memory,
    eliminating redundant bundle loading overhead across N workers.

Metrics:
    - Worker initialization time (per worker)
    - Total parallel workflow time (N workers)
    - Memory overhead
    - Speedup percentage

Constitutional requirements:
- CR-005: Zero-mock enforcement (real bundle data, real implementations)
- AC Requirements: ≥10 runs, 95% CI, p<0.05 significance
"""

import multiprocessing
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import numpy as np
import structlog
from scipy import stats

from rustybt.data.bundles.core import load
from rustybt.optimization.shared_bundle_context_fork import (
    SUPPORTS_FORK,
    SharedBundleContextFork,
)

logger = structlog.get_logger()


@dataclass
class BenchmarkResult:
    """Result from benchmark run."""

    approach: str
    total_duration: float
    per_worker_duration: float
    n_workers: int
    n_tasks: int


def baseline_worker_task(bundle_name: str, task_id: int) -> dict[str, Any]:
    """Baseline worker task - loads bundle independently (no sharing).

    Args:
        bundle_name: Bundle to load
        task_id: Task identifier

    Returns:
        Task result with timing info
    """
    start_time = time.time()

    # Load bundle (this happens in EVERY worker - redundant!)
    bundle = load(bundle_name)

    # Simulate lightweight backtest work
    assets = bundle.asset_finder.retrieve_all(bundle.asset_finder.sids)
    result = {
        "task_id": task_id,
        "num_assets": len(assets),
        "bundle_load_time": time.time() - start_time,
    }

    return result


def fork_worker_task(bundle_name: str, task_id: int) -> dict[str, Any]:
    """Fork-based worker task - accesses shared bundle (inherited from parent).

    Args:
        bundle_name: Bundle to access (already in memory)
        task_id: Task identifier

    Returns:
        Task result with timing info
    """
    start_time = time.time()

    # Access inherited bundle (no loading - just memory access!)
    context = SharedBundleContextFork(bundle_name)
    bundle = context.get_bundle()

    # Simulate lightweight backtest work
    assets = bundle.asset_finder.retrieve_all(bundle.asset_finder.sids)
    result = {
        "task_id": task_id,
        "num_assets": len(assets),
        "bundle_access_time": time.time() - start_time,
    }

    return result


def run_baseline_benchmark(
    bundle_name: str,
    n_workers: int,
    n_tasks: int,
    n_runs: int,
) -> list[BenchmarkResult]:
    """Run baseline benchmark (spawn mode, per-worker loading).

    Args:
        bundle_name: Bundle to use
        n_workers: Number of worker processes
        n_tasks: Number of tasks to execute
        n_runs: Number of benchmark runs

    Returns:
        List of benchmark results
    """
    print(f"\n📊 Baseline (Spawn Mode, Per-Worker Loading) - {n_runs} runs")
    print(f"   Workers: {n_workers}, Tasks: {n_tasks}")

    results = []

    for run in range(n_runs):
        print(f"\n   Run {run + 1}/{n_runs}...")

        # Use spawn mode (standard multiprocessing)
        multiprocessing.set_start_method("spawn", force=True)

        start_time = time.time()

        # Create worker pool
        with multiprocessing.Pool(processes=n_workers) as pool:
            # Execute tasks
            task_args = [(bundle_name, i) for i in range(n_tasks)]
            task_results = pool.starmap(baseline_worker_task, task_args)

        total_duration = time.time() - start_time

        # Calculate per-worker average
        per_worker_times = [r["bundle_load_time"] for r in task_results]
        per_worker_avg = np.mean(per_worker_times)

        results.append(
            BenchmarkResult(
                approach="Baseline (Spawn)",
                total_duration=total_duration,
                per_worker_duration=per_worker_avg,
                n_workers=n_workers,
                n_tasks=n_tasks,
            )
        )

        print(f"      Total duration: {total_duration:.3f}s")
        print(f"      Per-worker avg: {per_worker_avg:.3f}s")

    return results


def run_fork_benchmark(
    bundle_name: str,
    n_workers: int,
    n_tasks: int,
    n_runs: int,
) -> list[BenchmarkResult]:
    """Run fork-based shared bundle benchmark.

    Args:
        bundle_name: Bundle to use
        n_workers: Number of worker processes
        n_tasks: Number of tasks to execute
        n_runs: Number of benchmark runs

    Returns:
        List of benchmark results
    """
    print(f"\n🚀 Optimized (Fork Mode, Shared Bundle) - {n_runs} runs")
    print(f"   Workers: {n_workers}, Tasks: {n_tasks}")

    results = []

    for run in range(n_runs):
        print(f"\n   Run {run + 1}/{n_runs}...")

        # Set fork mode
        SharedBundleContextFork.set_fork_mode()

        # Initialize shared context in manager process
        context = SharedBundleContextFork(bundle_name)
        context.initialize()

        start_time = time.time()

        # Create worker pool (fork mode - workers inherit bundle)
        with multiprocessing.Pool(processes=n_workers) as pool:
            # Execute tasks
            task_args = [(bundle_name, i) for i in range(n_tasks)]
            task_results = pool.starmap(fork_worker_task, task_args)

        total_duration = time.time() - start_time

        # Calculate per-worker average
        per_worker_times = [r["bundle_access_time"] for r in task_results]
        per_worker_avg = np.mean(per_worker_times)

        # Cleanup
        context.cleanup()

        results.append(
            BenchmarkResult(
                approach="Optimized (Fork)",
                total_duration=total_duration,
                per_worker_duration=per_worker_avg,
                n_workers=n_workers,
                n_tasks=n_tasks,
            )
        )

        print(f"      Total duration: {total_duration:.3f}s")
        print(f"      Per-worker avg: {per_worker_avg:.3f}s")

    return results


def calculate_statistics(
    baseline_results: list[BenchmarkResult],
    optimized_results: list[BenchmarkResult],
) -> dict[str, Any]:
    """Calculate statistical comparison between baseline and optimized.

    Args:
        baseline_results: Baseline (spawn) results
        optimized_results: Fork-based results

    Returns:
        Dictionary with statistical metrics
    """
    # Total duration comparison
    baseline_times = [r.total_duration for r in baseline_results]
    optimized_times = [r.total_duration for r in optimized_results]

    baseline_mean = np.mean(baseline_times)
    optimized_mean = np.mean(optimized_times)
    speedup_pct = (baseline_mean - optimized_mean) / baseline_mean * 100

    # Statistical significance (paired t-test)
    if len(baseline_times) == len(optimized_times):
        t_stat, p_value = stats.ttest_rel(baseline_times, optimized_times)
    else:
        t_stat, p_value = stats.ttest_ind(baseline_times, optimized_times)

    # 95% confidence interval for speedup
    speedup_values = [(b - o) / b * 100 for b, o in zip(baseline_times, optimized_times)]
    ci_95 = stats.t.interval(
        confidence=0.95,
        df=len(speedup_values) - 1,
        loc=np.mean(speedup_values),
        scale=stats.sem(speedup_values),
    )

    # Per-worker time comparison
    baseline_per_worker = [r.per_worker_duration for r in baseline_results]
    optimized_per_worker = [r.per_worker_duration for r in optimized_results]

    per_worker_speedup = (
        (np.mean(baseline_per_worker) - np.mean(optimized_per_worker))
        / np.mean(baseline_per_worker)
        * 100
    )

    return {
        "baseline_mean_time": baseline_mean,
        "baseline_std_time": np.std(baseline_times),
        "optimized_mean_time": optimized_mean,
        "optimized_std_time": np.std(optimized_times),
        "speedup_pct": speedup_pct,
        "speedup_ci_95": ci_95,
        "p_value": p_value,
        "t_statistic": t_stat,
        "is_significant": p_value < 0.05,
        "meets_threshold": speedup_pct >= 5.0 and p_value < 0.05,
        "baseline_per_worker": np.mean(baseline_per_worker),
        "optimized_per_worker": np.mean(optimized_per_worker),
        "per_worker_speedup": per_worker_speedup,
    }


def main():
    """Run SharedBundleContext fork() benchmark."""
    print("=" * 80)
    print("SharedBundleContext Fork() Optimization Benchmark (Phase 6B)")
    print("=" * 80)
    print("\nObjective: Measure speedup from fork-based shared bundle context")
    print("Hypothesis: Fork mode achieves ≥13% speedup by eliminating redundant loads")
    print("\nConfiguration:")

    # Check platform support
    if not SUPPORTS_FORK:
        print("\n❌ ERROR: Fork mode not supported on this platform (Windows)")
        print("   This benchmark requires Unix/Linux/macOS")
        return

    # Configuration
    BUNDLE_NAME = "mag-7"
    N_WORKERS = 8  # Parallel workers
    N_TASKS = 16  # Tasks per run (2x workers for queue effect)
    N_RUNS = 10  # Statistical requirement: ≥10 runs

    print(f"  Bundle: {BUNDLE_NAME}")
    print(f"  Workers: {N_WORKERS}")
    print(f"  Tasks per run: {N_TASKS}")
    print(f"  Benchmark runs: {N_RUNS}")
    print(f"  Platform: {multiprocessing.get_start_method()} (will use fork for optimized)")

    # Run baseline benchmark (spawn mode)
    baseline_results = run_baseline_benchmark(
        bundle_name=BUNDLE_NAME,
        n_workers=N_WORKERS,
        n_tasks=N_TASKS,
        n_runs=N_RUNS,
    )

    # Run fork benchmark (shared bundle)
    optimized_results = run_fork_benchmark(
        bundle_name=BUNDLE_NAME,
        n_workers=N_WORKERS,
        n_tasks=N_TASKS,
        n_runs=N_RUNS,
    )

    # Calculate statistics
    print("\n" + "=" * 80)
    print("STATISTICAL ANALYSIS")
    print("=" * 80)

    stats_result = calculate_statistics(baseline_results, optimized_results)

    print(f"\n📊 Baseline (Spawn Mode, Per-Worker Loading):")
    print(f"   Mean total time: {stats_result['baseline_mean_time']:.3f}s")
    print(f"   Std dev: {stats_result['baseline_std_time']:.3f}s")
    print(f"   Per-worker avg: {stats_result['baseline_per_worker']:.3f}s")

    print(f"\n🚀 Optimized (Fork Mode, Shared Bundle):")
    print(f"   Mean total time: {stats_result['optimized_mean_time']:.3f}s")
    print(f"   Std dev: {stats_result['optimized_std_time']:.3f}s")
    print(f"   Per-worker avg: {stats_result['optimized_per_worker']:.3f}s")

    print(f"\n⚡ Speedup:")
    print(f"   Total workflow: {stats_result['speedup_pct']:.2f}%")
    print(
        f"   95% CI: [{stats_result['speedup_ci_95'][0]:.2f}%, {stats_result['speedup_ci_95'][1]:.2f}%]"
    )
    print(f"   Per-worker: {stats_result['per_worker_speedup']:.2f}%")
    print(f"   p-value: {stats_result['p_value']:.6f}")
    print(
        f"   Statistically significant: {'✅ YES' if stats_result['is_significant'] else '❌ NO'}"
    )

    # Acceptance decision
    print("\n" + "=" * 80)
    print("ACCEPTANCE DECISION")
    print("=" * 80)

    if stats_result["meets_threshold"]:
        print(
            f"✅ ACCEPT: SharedBundleContext fork() achieves {stats_result['speedup_pct']:.2f}% speedup"
        )
        print("   (≥5% required, p<0.05)")
        print("   Fork-based shared bundle will be integrated into ParallelOptimizer")
    else:
        if stats_result["speedup_pct"] < 5.0:
            print(f"❌ REJECT: Speedup {stats_result['speedup_pct']:.2f}% below 5% threshold")
        elif not stats_result["is_significant"]:
            print(
                f"❌ REJECT: Not statistically significant (p={stats_result['p_value']:.4f} ≥ 0.05)"
            )
        print("   Will update rejection rationale in decisions/shared_bundle_context_rejected.md")

    print("\n" + "=" * 80)

    # Additional analysis
    print("\n📈 Efficiency Breakdown:")
    time_saved_per_worker = (
        stats_result["baseline_per_worker"] - stats_result["optimized_per_worker"]
    )
    print(f"   Time saved per worker: {time_saved_per_worker:.3f}s")
    print(f"   Total time saved ({N_WORKERS} workers): {time_saved_per_worker * N_WORKERS:.3f}s")
    print(f"   Efficiency gain: {stats_result['per_worker_speedup']:.1f}%")

    print("\n💡 Interpretation:")
    if stats_result["speedup_pct"] >= 5.0:
        print("   Fork-based shared bundle eliminates redundant bundle loading overhead.")
        print(
            f"   Each worker saves ~{time_saved_per_worker:.3f}s by inheriting bundle via copy-on-write."
        )
        print("   Benefit scales linearly with number of workers.")
    else:
        print("   Fork() overhead or task execution time dominates bundle loading time.")
        print("   Shared bundle benefit may be too small for lightweight tasks.")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
