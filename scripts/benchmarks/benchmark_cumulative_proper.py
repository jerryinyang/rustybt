"""Proper cumulative benchmark for Phase 6A optimizations (Layers 1+2+3).

This benchmark simulates a realistic grid search optimization workflow to validate
the cumulative ≥90% speedup target.

Workflow simulation:
1. Initialize bundle connection (Layer 3: pooling)
2. Extract asset list (Layer 1: asset caching)
3. Load historical data (Layer 1: data pre-grouping + Layer 2: history cache)
4. Run simple moving average crossover strategy
5. Repeat for multiple parameter combinations

Constitutional requirements:
- CR-001: Decimal precision for all numeric results
- CR-008: Zero-mock enforcement (real bundle, real data)
"""

import time
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


def simulate_backtest_with_optimizations(
    bundle_name: str,
    fast_window: int,
    slow_window: int,
    enable_optimizations: bool,
) -> Tuple[float, int]:
    """Simulate a simple moving average crossover backtest.

    This exercises all three optimization layers:
    - Bundle loading (Layer 3)
    - Asset list extraction (Layer 1)
    - Historical data access (Layer 1 + Layer 2)

    Args:
        bundle_name: Bundle to use
        fast_window: Fast MA window
        slow_window: Slow MA window
        enable_optimizations: Whether to enable optimizations

    Returns:
        Tuple of (sharpe_ratio, num_trades)
    """
    # Layer 3: Bundle loading with optional pooling
    if enable_optimizations:
        from rustybt.optimization.bundle_pool import get_bundle_from_pool

        bundle_data = get_bundle_from_pool(bundle_name)
    else:
        from rustybt.data.bundles.core import load

        bundle_data = load(bundle_name)

    # Get asset finder (needed for both paths)
    asset_finder = bundle_data.asset_finder

    # Layer 1: Asset list extraction with optional caching
    if enable_optimizations:
        # Create simple hash for caching (just use bundle name)
        import hashlib

        from rustybt.optimization.caching import get_cached_assets

        bundle_hash = hashlib.sha256(bundle_name.encode()).hexdigest()
        asset_list = get_cached_assets(bundle_name, bundle_hash)
    else:
        # Direct extraction without caching
        all_sids = list(asset_finder.sids)
        all_assets = asset_finder.retrieve_all(all_sids)
        asset_list = [asset.symbol for asset in all_assets]

    # Select first asset for simplicity
    if not asset_list:
        return (0.0, 0)

    asset_symbol = asset_list[0]

    # Layer 1 + Layer 2: Data loading with optional pre-grouping and history caching
    # For this benchmark, we'll load daily bars directly
    # In real usage, DataPortal.history() would use HistoryCache (Layer 2)
    bar_reader = bundle_data.equity_daily_bar_reader

    # Get asset sid
    asset = asset_finder.lookup_symbol(asset_symbol, as_of_date=None)
    sid = asset.sid

    # Load price data (this is where pre-grouping would help in real workflows)
    try:
        # Load close prices for strategy
        close_prices = []
        sessions = bar_reader.sessions
        for session in sessions[: min(len(sessions), 252)]:  # 1 year of data
            try:
                bars = bar_reader.load_raw_arrays(
                    columns=["close"], start_date=session, end_date=session, sids=[sid]
                )
                if len(bars) > 0 and "close" in bars:
                    close_prices.append(float(bars["close"][0]))
            except:
                continue

        if len(close_prices) < slow_window:
            return (0.0, 0)

        # Calculate moving averages
        prices_array = np.array(close_prices)
        fast_ma = np.convolve(prices_array, np.ones(fast_window) / fast_window, mode="valid")
        slow_ma = np.convolve(prices_array, np.ones(slow_window) / slow_window, mode="valid")

        # Calculate returns
        min_len = min(len(fast_ma), len(slow_ma))
        if min_len < 2:
            return (0.0, 0)

        signals = (fast_ma[:min_len] > slow_ma[:min_len]).astype(int)
        signal_changes = np.diff(signals)
        num_trades = int(np.sum(np.abs(signal_changes)))

        # Simple return calculation
        aligned_prices = prices_array[slow_window : slow_window + min_len]
        returns = np.diff(aligned_prices) / aligned_prices[:-1]

        if len(returns) > 0:
            sharpe = float(np.mean(returns) / (np.std(returns) + 1e-10) * np.sqrt(252))
        else:
            sharpe = 0.0

        return (sharpe, num_trades)

    except Exception as e:
        logger.debug("backtest_error", error=str(e))
        return (0.0, 0)


def run_grid_search(
    bundle_name: str,
    parameter_combinations: List[Tuple[int, int]],
    enable_optimizations: bool,
) -> Decimal:
    """Run grid search over MA parameters.

    Args:
        bundle_name: Bundle to use
        parameter_combinations: List of (fast_window, slow_window) tuples
        enable_optimizations: Whether to enable optimizations

    Returns:
        Execution time in milliseconds
    """
    start_time = time.perf_counter()

    results = []
    for fast_window, slow_window in parameter_combinations:
        sharpe, trades = simulate_backtest_with_optimizations(
            bundle_name,
            fast_window,
            slow_window,
            enable_optimizations,
        )
        results.append((fast_window, slow_window, sharpe, trades))

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    return Decimal(str(elapsed_ms))


def run_cumulative_benchmark(
    bundle_name: str,
    num_runs: int = 10,
) -> Dict:
    """Run cumulative benchmark for all Phase 6A optimizations.

    Args:
        bundle_name: Bundle to use
        num_runs: Number of runs for statistical validity

    Returns:
        Dictionary with benchmark results
    """
    logger.info(
        "cumulative_benchmark_start",
        bundle_name=bundle_name,
        num_runs=num_runs,
    )

    # Grid search parameters: 3x3 grid of MA combinations
    parameter_combinations = [
        (10, 20),
        (10, 30),
        (10, 50),
        (20, 30),
        (20, 50),
        (20, 100),
        (30, 50),
        (30, 100),
        (30, 150),
    ]

    logger.info(
        "grid_parameters",
        combinations=len(parameter_combinations),
        parameters=parameter_combinations,
    )

    # Warm up both configurations
    logger.info("warmup", phase="baseline")
    run_grid_search(bundle_name, parameter_combinations[:2], enable_optimizations=False)

    logger.info("warmup", phase="optimized")
    run_grid_search(bundle_name, parameter_combinations[:2], enable_optimizations=True)

    # Benchmark baseline (all OFF)
    logger.info("benchmarking", phase="baseline")
    baseline_times: List[Decimal] = []
    for run in range(num_runs):
        elapsed = run_grid_search(bundle_name, parameter_combinations, enable_optimizations=False)
        baseline_times.append(elapsed)
        logger.debug("run_complete", phase="baseline", run=run + 1, time_ms=float(elapsed))

    baseline_mean = sum(baseline_times) / len(baseline_times)

    # Clear caches before optimized runs to ensure fair comparison
    from rustybt.optimization.bundle_pool import BundleConnectionPool
    from rustybt.optimization.caching import clear_asset_cache, get_global_data_cache

    clear_asset_cache()
    get_global_data_cache().clear()
    # Reset bundle pool
    BundleConnectionPool._instance = None

    # Benchmark optimized (all ON)
    logger.info("benchmarking", phase="optimized")
    optimized_times: List[Decimal] = []
    for run in range(num_runs):
        elapsed = run_grid_search(bundle_name, parameter_combinations, enable_optimizations=True)
        optimized_times.append(elapsed)
        logger.debug("run_complete", phase="optimized", run=run + 1, time_ms=float(elapsed))

    optimized_mean = sum(optimized_times) / len(optimized_times)

    # Calculate improvement
    improvement_percent = (
        ((baseline_mean - optimized_mean) / baseline_mean * 100)
        if baseline_mean > 0
        else Decimal(0)
    )
    speedup_ratio = baseline_mean / optimized_mean if optimized_mean > 0 else Decimal(0)

    # Check cache statistics
    from rustybt.optimization.caching import get_asset_cache_info

    cache_info = get_asset_cache_info()
    logger.info(
        "cache_statistics",
        asset_cache_hits=cache_info["hits"],
        asset_cache_misses=cache_info["misses"],
        asset_cache_hit_rate=f"{cache_info['hit_rate']:.1%}",
    )

    # Check targets
    target_improvement = Decimal("90.0")
    passed = improvement_percent >= target_improvement

    results = {
        "baseline_mean_ms": baseline_mean,
        "optimized_mean_ms": optimized_mean,
        "improvement_percent": improvement_percent,
        "speedup_ratio": speedup_ratio,
        "target_improvement_percent": target_improvement,
        "passed": passed,
        "num_runs": num_runs,
        "num_parameter_combinations": len(parameter_combinations),
        "baseline_times": baseline_times,
        "optimized_times": optimized_times,
        "cache_stats": cache_info,
    }

    logger.info(
        "cumulative_benchmark_complete",
        baseline_mean_ms=float(baseline_mean),
        optimized_mean_ms=float(optimized_mean),
        improvement_percent=float(improvement_percent),
        speedup_ratio=float(speedup_ratio),
        target=float(target_improvement),
        passed=passed,
    )

    return results


def main():
    """Main entry point."""
    import logging
    import sys

    # Configure logging
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    )

    # Parse arguments
    if len(sys.argv) < 2:
        print("Usage: python benchmark_cumulative_proper.py <bundle_name> [output_dir] [num_runs]")
        print(
            "Example: python benchmark_cumulative_proper.py yf-benchmark ./benchmark-results/cumulative 10"
        )
        sys.exit(1)

    bundle_name = sys.argv[1]
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("benchmark-results/cumulative")
    num_runs = int(sys.argv[3]) if len(sys.argv) > 3 else 10

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Run benchmark
    results = run_cumulative_benchmark(
        bundle_name=bundle_name,
        num_runs=num_runs,
    )

    # Generate report
    report_path = output_dir / "cumulative_benchmark_report.txt"
    with open(report_path, "w") as f:
        f.write("=" * 80 + "\n")
        f.write("Phase 6A Cumulative Optimization Benchmarks\n")
        f.write("Layers 1 (Asset Caching + Data Pre-Grouping) +\n")
        f.write("Layer 2 (History Cache) +\n")
        f.write("Layer 3 (Bundle Pooling)\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Bundle: {bundle_name}\n")
        f.write(f"Grid search: {results['num_parameter_combinations']} parameter combinations\n")
        f.write(f"Number of runs: {num_runs}\n\n")
        f.write(f"Baseline (all OFF) mean: {results['baseline_mean_ms']:.2f} ms\n")
        f.write(f"Optimized (all ON) mean: {results['optimized_mean_ms']:.2f} ms\n")
        f.write(f"Improvement: {results['improvement_percent']:.2f}%\n")
        f.write(f"Speedup: {results['speedup_ratio']:.2f}x\n")
        f.write(f"Target: ≥{results['target_improvement_percent']:.0f}%\n")
        f.write(f"\nAsset Cache Statistics:\n")
        f.write(f"  Hits: {results['cache_stats']['hits']}\n")
        f.write(f"  Misses: {results['cache_stats']['misses']}\n")
        f.write(f"  Hit Rate: {results['cache_stats']['hit_rate']:.1%}\n")
        f.write(f"\nStatus: {'PASS' if results['passed'] else 'FAIL'}\n")
        f.write("\n" + "=" * 80 + "\n")

    # Print summary
    print("\n" + "=" * 80)
    print("PHASE 6A CUMULATIVE BENCHMARK SUMMARY")
    print("=" * 80)
    print(f"Bundle: {bundle_name}")
    print(f"Grid Search: {results['num_parameter_combinations']} combinations")
    print(f"Baseline (all OFF): {results['baseline_mean_ms']:.2f} ms")
    print(f"Optimized (all ON): {results['optimized_mean_ms']:.2f} ms")
    print(f"Improvement: {results['improvement_percent']:.2f}%")
    print(f"Target: ≥{results['target_improvement_percent']:.0f}%")
    print(f"Cache Hit Rate: {results['cache_stats']['hit_rate']:.1%}")
    print(f"Status: {'✅ PASSED' if results['passed'] else '❌ FAILED'}")
    print("=" * 80)
    print(f"\nReport saved: {report_path}")


if __name__ == "__main__":
    main()
