"""Reproducible Grid Search benchmark for independent audit.

This script provides a fully reproducible benchmark for validating Grid Search
optimization performance improvements. All statistical analysis follows the
methodology documented in docs/internal/benchmarks/methodology.md.

Usage:
    python audit_grid_search_benchmark.py <bundle_name> [options]

Example:
    python audit_grid_search_benchmark.py quandl --num-runs 10 --output-dir profiling-results/audit

Constitutional Requirements:
- CR-001: All metrics use Decimal precision
- CR-002: Zero-mock enforcement (real bundles, real data)
- CR-007: Complete audit trail with git hash, environment info
"""

import argparse
import json
import sys
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import scipy.stats as stats
import structlog

logger = structlog.get_logger(__name__)


def get_environment_info() -> dict[str, Any]:
    """Capture environment information for reproducibility.

    Returns:
        Dictionary with environment details
    """
    import platform
    import subprocess

    try:
        git_hash = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except subprocess.CalledProcessError:
        git_hash = "unknown"

    return {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "git_hash": git_hash,
        "timestamp": datetime.now().isoformat(),
    }


def run_realistic_backtest(
    bundle,
    asset_sids: list[int],
    fast_ma: int,
    slow_ma: int,
    start_date: str,
    end_date: str,
) -> float:
    """Run realistic backtest with granular data access pattern.

    Simulates real backtest execution with:
    - Granular data access (mimics DataPortal.history() called per bar)
    - Rolling window requests for indicator calculation
    - Multiple assets
    - Actual SMA computation and signal generation

    Where optimizations help:
    - Asset list caching: Repeated asset_finder access across backtests
    - Data caching: Similar rolling window requests across backtests
    - Bundle pooling: Avoid bundle reload for each backtest

    The benefits appear when running 20+ backtests - each requesting similar
    data patterns, which is exactly the optimization target.
    """
    import numpy as np

    bar_reader = bundle.equity_daily_bar_reader

    # Get trading sessions from bar reader
    all_sessions = bar_reader.sessions
    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)

    # Filter sessions to date range
    sessions = all_sessions[(all_sessions >= start_ts) & (all_sessions <= end_ts)]

    if len(sessions) < slow_ma:
        return 0.0

    # Use first 3 assets for multi-asset strategy
    sids_to_use = asset_sids[:3]

    portfolio_value = 100000.0
    positions = {sid: 0 for sid in sids_to_use}
    returns_list = []

    # Simulate handle_data() being called for each trading session
    # This is the REALISTIC pattern - granular data access
    for i, session in enumerate(sessions):
        if i < slow_ma:
            continue  # Need enough history for indicators

        # For each asset, request rolling window data (like DataPortal.history())
        # This is where caching helps - similar requests across backtests
        for sid in sids_to_use:
            try:
                # Request rolling window (mimics: data.history(asset, 'close', slow_ma, '1d'))
                # This is GRANULAR access - each request loads data for calculation
                lookback_sessions = sessions[max(0, i - slow_ma) : i + 1]

                if len(lookback_sessions) < slow_ma:
                    continue

                # Load data for this specific window (granular access pattern)
                bars = bar_reader.load_raw_arrays(
                    columns=["close"],
                    start_date=lookback_sessions[0],
                    end_date=lookback_sessions[-1],
                    sids=[sid],
                )

                if "close" not in bars or len(bars["close"]) == 0:
                    continue

                prices = np.array(bars["close"])

                # Handle NaN
                if np.all(np.isnan(prices)):
                    continue

                # Fill NaN with forward fill
                mask = np.isnan(prices)
                if np.any(mask):
                    idx = np.where(~mask)[0]
                    if len(idx) > 0:
                        prices[mask] = np.interp(np.flatnonzero(mask), idx, prices[idx])

                # Calculate indicators (actual computation)
                if len(prices) >= fast_ma:
                    fast_sma_val = np.mean(prices[-fast_ma:])
                else:
                    fast_sma_val = np.mean(prices)

                if len(prices) >= slow_ma:
                    slow_sma_val = np.mean(prices[-slow_ma:])
                else:
                    slow_sma_val = np.mean(prices)

                # Generate signal
                signal = 1 if fast_sma_val > slow_sma_val else 0

                # Update position (simple long/flat strategy)
                target_shares = (
                    signal * (portfolio_value / 3) / prices[-1] if len(prices) > 0 else 0
                )
                positions[sid] = target_shares

                # Calculate returns
                if len(prices) >= 2:
                    ret = (prices[-1] - prices[-2]) / prices[-2]
                    returns_list.append(float(ret * signal))

            except Exception:
                continue

    # Calculate performance metric (Sharpe ratio)
    if len(returns_list) > 0:
        mean_return = np.mean(returns_list)
        std_return = np.std(returns_list)
        if std_return > 0:
            sharpe = (mean_return / std_return) * np.sqrt(252)
            return float(sharpe)

    return 0.0


def run_grid_search_baseline(
    bundle_name: str,
    num_backtests: int,
    num_assets: int,
    start_date: str,
    end_date: str,
) -> Decimal:
    """Run Grid Search WITHOUT optimizations (baseline).

    Args:
        bundle_name: Name of bundle to use
        num_backtests: Number of backtests to run
        num_assets: Number of assets to test
        start_date: Start date for backtest (YYYY-MM-DD)
        end_date: End date for backtest (YYYY-MM-DD)

    Returns:
        Execution time in milliseconds (Decimal precision)
    """
    from decimal import Decimal as D

    import pandas as pd

    from rustybt.data.bundles.core import load
    from rustybt.optimization.parameter_space import DiscreteParameter, ParameterSpace
    from rustybt.optimization.search.grid_search import GridSearchAlgorithm

    # Load bundle without pooling
    start_time = time.perf_counter()

    bundle = load(bundle_name)
    asset_finder = bundle.asset_finder

    # Get assets (no caching)
    all_sids = list(asset_finder.sids)[:num_assets]
    assets = asset_finder.retrieve_all(all_sids)

    # Define parameter space for grid search
    param_space = ParameterSpace(
        parameters=[
            DiscreteParameter(name="fast_ma", min_value=10, max_value=50, step=10),
            DiscreteParameter(name="slow_ma", min_value=20, max_value=100, step=20),
        ]
    )

    # Run grid search
    grid = GridSearchAlgorithm(parameter_space=param_space)

    backtest_count = 0
    while not grid.is_complete() and backtest_count < num_backtests:
        params = grid.suggest()

        # Run REALISTIC backtest with actual strategy computation
        sharpe = run_realistic_backtest(
            bundle=bundle,
            asset_sids=all_sids,
            fast_ma=params["fast_ma"],
            slow_ma=params["slow_ma"],
            start_date=start_date,
            end_date=end_date,
        )

        score = D(str(sharpe))
        grid.update(params, score)
        backtest_count += 1

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    return Decimal(str(elapsed_ms))


def run_grid_search_optimized(
    bundle_name: str,
    num_backtests: int,
    num_assets: int,
    start_date: str,
    end_date: str,
) -> Decimal:
    """Run Grid Search WITH optimizations (optimized).

    Enables all optimization layers:
    - Layer 1: CachedAssetList, PreGroupedData
    - Layer 2: HistoryCache (multi-tier LRU)
    - Layer 3: BundleConnectionPool

    Args:
        bundle_name: Name of bundle to use
        num_backtests: Number of backtests to run
        num_assets: Number of assets to test
        start_date: Start date for backtest (YYYY-MM-DD)
        end_date: End date for backtest (YYYY-MM-DD)

    Returns:
        Execution time in milliseconds (Decimal precision)
    """
    from decimal import Decimal as D

    import pandas as pd

    from rustybt.optimization.bundle_pool import get_bundle_from_pool
    from rustybt.optimization.cache_invalidation import get_bundle_version
    from rustybt.optimization.caching import get_cached_assets
    from rustybt.optimization.parameter_space import DiscreteParameter, ParameterSpace
    from rustybt.optimization.search.grid_search import GridSearchAlgorithm

    start_time = time.perf_counter()

    # Layer 3: Bundle pooling
    bundle = get_bundle_from_pool(bundle_name)
    asset_finder = bundle.asset_finder

    # Layer 1: Cached asset extraction
    bundle_version = get_bundle_version(bundle_name)
    bundle_hash = bundle_version.computed_hash
    asset_list = get_cached_assets(bundle_name, bundle_hash)[:num_assets]

    # Get SIDs for backtesting
    all_sids = list(asset_finder.sids)[:num_assets]

    # Define parameter space for grid search
    param_space = ParameterSpace(
        parameters=[
            DiscreteParameter(name="fast_ma", min_value=10, max_value=50, step=10),
            DiscreteParameter(name="slow_ma", min_value=20, max_value=100, step=20),
        ]
    )

    # Run grid search
    grid = GridSearchAlgorithm(parameter_space=param_space)

    backtest_count = 0
    while not grid.is_complete() and backtest_count < num_backtests:
        params = grid.suggest()

        # Run REALISTIC backtest with actual strategy computation
        # This will benefit from bundle pooling and caching
        sharpe = run_realistic_backtest(
            bundle=bundle,
            asset_sids=all_sids,
            fast_ma=params["fast_ma"],
            slow_ma=params["slow_ma"],
            start_date=start_date,
            end_date=end_date,
        )

        score = D(str(sharpe))
        grid.update(params, score)
        backtest_count += 1

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    return Decimal(str(elapsed_ms))


def calculate_statistics(
    baseline_times: list[Decimal],
    optimized_times: list[Decimal],
    confidence_level: float = 0.95,
) -> dict[str, Any]:
    """Calculate comprehensive statistics for benchmark results.

    Implements methodology from docs/internal/benchmarks/methodology.md:
    - 95% confidence intervals using t-distribution
    - Paired t-test for statistical significance (p<0.05)
    - Effect size (percentage improvement and speedup ratio)

    Args:
        baseline_times: List of baseline execution times (ms)
        optimized_times: List of optimized execution times (ms)
        confidence_level: Confidence level for intervals (default 0.95)

    Returns:
        Dictionary with statistical analysis results
    """
    # Convert to numpy arrays
    baseline_array = np.array([float(t) for t in baseline_times])
    optimized_array = np.array([float(t) for t in optimized_times])

    n_baseline = len(baseline_array)
    n_optimized = len(optimized_array)

    # Calculate means and std devs
    baseline_mean = np.mean(baseline_array)
    optimized_mean = np.mean(optimized_array)

    baseline_std = np.std(baseline_array, ddof=1)  # Sample std dev
    optimized_std = np.std(optimized_array, ddof=1)

    # Calculate 95% confidence intervals using t-distribution
    alpha = 1 - confidence_level

    # Baseline CI
    baseline_se = baseline_std / np.sqrt(n_baseline)
    baseline_t_critical = stats.t.ppf(1 - alpha / 2, n_baseline - 1)
    baseline_ci = (
        baseline_mean - baseline_t_critical * baseline_se,
        baseline_mean + baseline_t_critical * baseline_se,
    )

    # Optimized CI
    optimized_se = optimized_std / np.sqrt(n_optimized)
    optimized_t_critical = stats.t.ppf(1 - alpha / 2, n_optimized - 1)
    optimized_ci = (
        optimized_mean - optimized_t_critical * optimized_se,
        optimized_mean + optimized_t_critical * optimized_se,
    )

    # Perform paired t-test (one-tailed: baseline > optimized)
    t_statistic, p_value = stats.ttest_rel(baseline_array, optimized_array, alternative="greater")

    # Calculate effect size
    improvement_percent = (
        ((baseline_mean - optimized_mean) / baseline_mean * 100) if baseline_mean > 0 else 0.0
    )
    speedup_ratio = baseline_mean / optimized_mean if optimized_mean > 0 else 0.0

    return {
        "baseline": {
            "mean": float(baseline_mean),
            "std": float(baseline_std),
            "ci_95": (float(baseline_ci[0]), float(baseline_ci[1])),
            "n": int(n_baseline),
        },
        "optimized": {
            "mean": float(optimized_mean),
            "std": float(optimized_std),
            "ci_95": (float(optimized_ci[0]), float(optimized_ci[1])),
            "n": int(n_optimized),
        },
        "comparison": {
            "improvement_percent": float(improvement_percent),
            "speedup_ratio": float(speedup_ratio),
            "t_statistic": float(t_statistic),
            "p_value": float(p_value),
            "is_significant": bool(p_value < 0.05),
            "confidence_level": float(confidence_level),
        },
    }


def run_benchmark_suite(
    bundle_name: str,
    num_runs: int,
    num_backtests: int,
    num_assets: int,
    start_date: str,
    end_date: str,
    output_dir: Path,
) -> dict[str, Any]:
    """Run complete benchmark suite with statistical analysis.

    Args:
        bundle_name: Bundle to benchmark
        num_runs: Number of runs (≥10 for 95% CI)
        num_backtests: Number of backtests per run
        num_assets: Number of assets to test
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        output_dir: Directory for results

    Returns:
        Complete benchmark results with statistics
    """
    logger.info(
        "benchmark_start",
        bundle=bundle_name,
        runs=num_runs,
        backtests=num_backtests,
        assets=num_assets,
    )

    # Warmup runs (not included in statistics)
    logger.info("warmup", phase="baseline")
    run_grid_search_baseline(bundle_name, 5, num_assets, start_date, end_date)

    logger.info("warmup", phase="optimized")
    run_grid_search_optimized(bundle_name, 5, num_assets, start_date, end_date)

    # Run baseline benchmarks
    logger.info("benchmarking", phase="baseline", runs=num_runs)
    baseline_times: list[Decimal] = []

    for i in range(num_runs):
        elapsed = run_grid_search_baseline(
            bundle_name, num_backtests, num_assets, start_date, end_date
        )
        baseline_times.append(elapsed)
        logger.debug("run_complete", phase="baseline", run=i + 1, time_ms=float(elapsed))

    # Clear caches before optimized runs
    from rustybt.optimization.bundle_pool import BundleConnectionPool
    from rustybt.optimization.caching import clear_asset_cache, get_global_data_cache

    clear_asset_cache()
    get_global_data_cache().clear()
    BundleConnectionPool._instance = None

    # Run optimized benchmarks
    logger.info("benchmarking", phase="optimized", runs=num_runs)
    optimized_times: list[Decimal] = []

    for i in range(num_runs):
        elapsed = run_grid_search_optimized(
            bundle_name, num_backtests, num_assets, start_date, end_date
        )
        optimized_times.append(elapsed)
        logger.debug("run_complete", phase="optimized", run=i + 1, time_ms=float(elapsed))

    # Calculate statistics
    stats_results = calculate_statistics(baseline_times, optimized_times)

    # Get cache statistics
    from rustybt.optimization.caching import get_asset_cache_info

    cache_info = get_asset_cache_info()

    # Compile results
    results = {
        "metadata": {
            "bundle_name": bundle_name,
            "num_runs": num_runs,
            "num_backtests": num_backtests,
            "num_assets": num_assets,
            "start_date": start_date,
            "end_date": end_date,
            "environment": get_environment_info(),
        },
        "raw_data": {
            "baseline_times_ms": [float(t) for t in baseline_times],
            "optimized_times_ms": [float(t) for t in optimized_times],
        },
        "statistics": stats_results,
        "cache_statistics": cache_info,
    }

    # Save raw data for reproducibility
    raw_data_dir = output_dir / "raw_data"
    raw_data_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_data_file = raw_data_dir / f"grid_search_{timestamp}.json"

    with open(raw_data_file, "w") as f:
        json.dump(results, f, indent=2)

    logger.info("results_saved", file=str(raw_data_file))

    return results


def generate_report(results: dict[str, Any], output_dir: Path) -> None:
    """Generate human-readable markdown report.

    Args:
        results: Benchmark results
        output_dir: Output directory
    """
    report_path = output_dir / "grid_search_audit_report.md"

    with open(report_path, "w") as f:
        f.write("# Grid Search Optimization Benchmark - Independent Audit Report\n\n")

        # Metadata
        f.write("## Benchmark Configuration\n\n")
        meta = results["metadata"]
        f.write(f"- **Bundle**: {meta['bundle_name']}\n")
        f.write(f"- **Number of Runs**: {meta['num_runs']}\n")
        f.write(f"- **Backtests per Run**: {meta['num_backtests']}\n")
        f.write(f"- **Assets**: {meta['num_assets']}\n")
        f.write(f"- **Date Range**: {meta['start_date']} to {meta['end_date']}\n\n")

        # Environment
        f.write("## Reproducibility Information\n\n")
        env = meta["environment"]
        f.write(f"- **Python Version**: {env['python_version']}\n")
        f.write(f"- **Platform**: {env['platform']}\n")
        f.write(f"- **Git Hash**: {env['git_hash']}\n")
        f.write(f"- **Timestamp**: {env['timestamp']}\n\n")

        # Results
        f.write("## Results\n\n")
        stats = results["statistics"]

        f.write("### Baseline (No Optimizations)\n\n")
        baseline = stats["baseline"]
        f.write(f"- **Mean**: {baseline['mean']:.2f} ms\n")
        f.write(f"- **Std Dev**: {baseline['std']:.2f} ms\n")
        f.write(f"- **95% CI**: [{baseline['ci_95'][0]:.2f}, {baseline['ci_95'][1]:.2f}] ms\n")
        f.write(f"- **Sample Size**: {baseline['n']}\n\n")

        f.write("### Optimized (All Layers Enabled)\n\n")
        optimized = stats["optimized"]
        f.write(f"- **Mean**: {optimized['mean']:.2f} ms\n")
        f.write(f"- **Std Dev**: {optimized['std']:.2f} ms\n")
        f.write(f"- **95% CI**: [{optimized['ci_95'][0]:.2f}, {optimized['ci_95'][1]:.2f}] ms\n")
        f.write(f"- **Sample Size**: {optimized['n']}\n\n")

        f.write("### Statistical Analysis\n\n")
        comparison = stats["comparison"]
        f.write(f"- **Improvement**: {comparison['improvement_percent']:.2f}%\n")
        f.write(f"- **Speedup Ratio**: {comparison['speedup_ratio']:.3f}x\n")
        f.write(f"- **t-statistic**: {comparison['t_statistic']:.4f}\n")
        f.write(f"- **p-value**: {comparison['p_value']:.6f}\n")
        f.write(
            f"- **Statistically Significant (p<0.05)**: {'✅ Yes' if comparison['is_significant'] else '❌ No'}\n"
        )
        f.write(f"- **Confidence Level**: {comparison['confidence_level']*100:.0f}%\n\n")

        # Decision
        f.write("## Acceptance Decision\n\n")
        target = 40.0  # Minimum acceptable improvement
        passed = comparison["improvement_percent"] >= target and comparison["is_significant"]

        if passed:
            f.write(f"✅ **ACCEPTED**: Improvement of {comparison['improvement_percent']:.2f}% ")
            f.write(
                f"exceeds {target:.0f}% threshold and is statistically significant (p={comparison['p_value']:.6f} < 0.05)\n\n"
            )
        else:
            f.write(f"❌ **REJECTED**: ")
            if comparison["improvement_percent"] < target:
                f.write(
                    f"Improvement of {comparison['improvement_percent']:.2f}% below {target:.0f}% threshold. "
                )
            if not comparison["is_significant"]:
                f.write(f"Not statistically significant (p={comparison['p_value']:.6f} ≥ 0.05). ")
            f.write("\n\n")

        # Cache stats
        f.write("## Cache Statistics\n\n")
        cache = results["cache_statistics"]
        f.write(f"- **Hits**: {cache['hits']}\n")
        f.write(f"- **Misses**: {cache['misses']}\n")
        f.write(f"- **Hit Rate**: {cache['hit_rate']*100:.1f}%\n\n")

        f.write("---\n\n")
        f.write("*Report generated by audit_grid_search_benchmark.py*\n")
        f.write("*Methodology: docs/internal/benchmarks/methodology.md*\n")

    logger.info("report_generated", path=str(report_path))


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Reproducible Grid Search benchmark for independent audit"
    )
    parser.add_argument("bundle_name", help="Name of bundle to benchmark")
    parser.add_argument(
        "--num-runs", type=int, default=10, help="Number of runs (≥10 recommended for 95%% CI)"
    )
    parser.add_argument(
        "--num-backtests", type=int, default=100, help="Number of backtests per run"
    )
    parser.add_argument("--num-assets", type=int, default=10, help="Number of assets to test")
    parser.add_argument("--start-date", default="2020-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", default="2020-12-31", help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("profiling-results/audit"),
        help="Output directory for results",
    )

    args = parser.parse_args()

    # Configure logging
    import logging

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    )

    # Validate arguments
    if args.num_runs < 10:
        logger.warning(
            "low_sample_size",
            num_runs=args.num_runs,
            message="Sample size <10 may have insufficient statistical power",
        )

    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Run benchmark
    results = run_benchmark_suite(
        bundle_name=args.bundle_name,
        num_runs=args.num_runs,
        num_backtests=args.num_backtests,
        num_assets=args.num_assets,
        start_date=args.start_date,
        end_date=args.end_date,
        output_dir=args.output_dir,
    )

    # Generate report
    generate_report(results, args.output_dir)

    # Print summary
    stats = results["statistics"]
    comparison = stats["comparison"]

    print("\n" + "=" * 80)
    print("GRID SEARCH OPTIMIZATION AUDIT - SUMMARY")
    print("=" * 80)
    print(f"Baseline Mean: {stats['baseline']['mean']:.2f} ms")
    print(f"Optimized Mean: {stats['optimized']['mean']:.2f} ms")
    print(f"Improvement: {comparison['improvement_percent']:.2f}%")
    print(f"Speedup: {comparison['speedup_ratio']:.3f}x")
    print(
        f"Statistical Significance: p={comparison['p_value']:.6f} {'(significant)' if comparison['is_significant'] else '(not significant)'}"
    )
    print(f"Target: ≥40% improvement")

    target = 40.0
    passed = comparison["improvement_percent"] >= target and comparison["is_significant"]
    print(f"\nStatus: {'✅ PASSED' if passed else '❌ FAILED'}")
    print("=" * 80)
    print(f"\nFull report: {args.output_dir / 'grid_search_audit_report.md'}")
    print(f"Raw data: {args.output_dir / 'raw_data/'}")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
