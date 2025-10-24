"""Production-scale profiling for Grid Search and Walk Forward workflows.

This script executes the production profiling runs required by:
- T032: Execute production-scale Grid Search profiling
- T033: Execute production-scale Walk Forward profiling
- T034: Validate >0.5% bottleneck identification

Constitutional requirements:
- CR-002: Real workflows, no mocks
- CR-006: >0.5% bottleneck identification per FR-006
- CR-007: Systematic profiling with decision documentation
"""

import logging
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict

import numpy as np
import polars as pl

from rustybt.benchmarks.profiling import generate_flame_graph, profile_workflow
from rustybt.benchmarks.reporter import generate_bottleneck_report
from rustybt.optimization.parameter_space import DiscreteParameter, ParameterSpace
from rustybt.optimization.search import GridSearchAlgorithm

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Directories
PROFILING_DIR = Path(__file__).parent.parent.parent / "profiling-results"
BENCHMARK_DIR = Path(__file__).parent.parent.parent / "benchmark-results"


# ============================================================================
# Grid Search Workflow
# ============================================================================


def create_synthetic_price_data(
    n_days: int = 252, n_assets: int = 10, seed: int = 42
) -> pl.DataFrame:
    """Create synthetic price data for benchmarking.

    Args:
        n_days: Number of trading days
        n_assets: Number of assets
        seed: Random seed for reproducibility

    Returns:
        DataFrame with date, asset, and OHLCV columns
    """
    np.random.seed(seed)

    # Create dates (trading days)
    from datetime import datetime, timedelta

    start_date = datetime(2024, 1, 1)
    dates = []
    current_date = start_date

    for _ in range(n_days):
        dates.append(current_date)
        current_date += timedelta(days=1)

    # Generate data for each asset
    data_rows = []

    for asset_id in range(n_assets):
        # Generate returns with specific characteristics
        returns = np.random.randn(n_days) * 0.015 + 0.0003

        # Generate prices from returns
        prices = 100.0 * (1 + returns).cumprod()

        # Generate OHLCV data
        for i, (date, price) in enumerate(zip(dates, prices)):
            daily_volatility = 0.02
            high = price * (1 + abs(np.random.randn() * daily_volatility))
            low = price * (1 - abs(np.random.randn() * daily_volatility))
            open_price = price * (1 + np.random.randn() * daily_volatility * 0.5)
            close = price
            volume = int(1_000_000 * (1 + np.random.rand()))

            data_rows.append(
                {
                    "date": date,
                    "asset": f"ASSET_{asset_id:03d}",
                    "open": open_price,
                    "high": max(high, open_price, close),
                    "low": min(low, open_price, close),
                    "close": close,
                    "volume": volume,
                }
            )

    return pl.DataFrame(data_rows)


def simple_ma_crossover_backtest(params: dict, data: pl.DataFrame) -> dict:
    """Simple moving average crossover strategy backtest.

    Args:
        params: Strategy parameters containing:
            - lookback_short: Short MA period
            - lookback_long: Long MA period
        data: Price data DataFrame

    Returns:
        Dictionary with performance_metrics including sharpe_ratio
    """
    lookback_short = params["lookback_short"]
    lookback_long = params["lookback_long"]

    # Get unique assets
    assets = data["asset"].unique().to_list()

    # Calculate strategy returns for each asset
    all_returns = []

    for asset in assets:
        asset_data = data.filter(pl.col("asset") == asset).sort("date")
        prices = asset_data["close"].to_numpy()

        if len(prices) < lookback_long + 1:
            continue

        # Calculate moving averages
        fast_ma = np.convolve(prices, np.ones(lookback_short) / lookback_short, mode="valid")
        slow_ma = np.convolve(prices, np.ones(lookback_long) / lookback_long, mode="valid")

        # Align arrays - both MAs start at lookback_long position
        min_len = min(len(fast_ma), len(slow_ma))
        fast_ma = fast_ma[:min_len]
        slow_ma = slow_ma[:min_len]

        # Generate signals
        signals = np.where(fast_ma > slow_ma, 1, -1)

        # Calculate returns from prices (aligned with MA positions)
        # MAs start at position lookback_long, so we need returns from that point
        aligned_prices = prices[lookback_long : lookback_long + min_len + 1]
        returns = np.diff(aligned_prices) / aligned_prices[:-1]

        # Align signals with returns (use signal[t-1] for return[t])
        if len(signals) > len(returns):
            signals = signals[: len(returns)]
        elif len(returns) > len(signals):
            returns = returns[: len(signals)]

        strategy_returns = signals * returns

        all_returns.extend(strategy_returns.tolist())

    if not all_returns:
        return {
            "performance_metrics": {
                "sharpe_ratio": 0.0,
                "total_return": 0.0,
            }
        }

    # Calculate metrics
    all_returns = np.array(all_returns)
    mean_return = all_returns.mean()
    std_return = all_returns.std()

    sharpe = (mean_return / std_return * np.sqrt(252)) if std_return > 0 else 0.0
    total_return = (1 + all_returns).prod() - 1

    return {
        "performance_metrics": {
            "sharpe_ratio": float(sharpe),
            "total_return": float(total_return),
        }
    }


def run_grid_search_workflow(
    n_combinations: int = 100, n_days: int = 252, n_assets: int = 10
) -> Dict[str, Any]:
    """Run Grid Search optimization workflow.

    This is a production-scale workflow that tests multiple parameter combinations
    across multiple backtests.

    Args:
        n_combinations: Number of parameter combinations to test
        n_days: Number of trading days per backtest
        n_assets: Number of assets in the portfolio

    Returns:
        Dictionary with optimization results
    """
    logger.info(
        f"Starting Grid Search workflow: {n_combinations} combinations, {n_days} days, {n_assets} assets"
    )

    # Create synthetic data
    data = create_synthetic_price_data(n_days=n_days, n_assets=n_assets)
    logger.info(f"Generated {len(data)} rows of synthetic price data")

    # Define parameter space to generate ~n_combinations
    # For 100 combinations: 10 short × 10 long = 100
    n_short_values = int(np.sqrt(n_combinations))
    n_long_values = n_combinations // n_short_values

    param_space = ParameterSpace(
        parameters=[
            DiscreteParameter(
                name="lookback_short",
                min_value=5,
                max_value=5 + (n_short_values - 1) * 2,
                step=2,
            ),
            DiscreteParameter(
                name="lookback_long",
                min_value=30,
                max_value=30 + (n_long_values - 1) * 5,
                step=5,
            ),
        ]
    )

    # Create grid search
    grid = GridSearchAlgorithm(
        parameter_space=param_space,
        early_stopping_rounds=None,
    )

    logger.info(f"Parameter space has {grid.total_combinations} combinations")

    # Run optimization
    trial_num = 0
    while not grid.is_complete():
        trial_num += 1

        # Get next parameter combination
        params = grid.suggest()

        # Run backtest
        result = simple_ma_crossover_backtest(params, data)

        # Extract objective metric
        sharpe_ratio = Decimal(str(result["performance_metrics"]["sharpe_ratio"]))

        # Update grid search
        grid.update(params, sharpe_ratio)

        if trial_num % 20 == 0:
            logger.info(
                f"Trial {trial_num}/{grid.total_combinations} ({grid.progress * 100:.0f}% complete)"
            )

    # Get results
    best_params = grid.get_best_params()
    top_results = grid.get_results(top_k=5)

    logger.info(f"Grid Search complete: {trial_num} trials evaluated")
    logger.info(f"Best params: {best_params}")

    return {
        "total_trials": trial_num,
        "best_params": best_params,
        "top_5_results": top_results,
        "dataset_size": len(data),
        "parameter_combinations": trial_num,
    }


# ============================================================================
# Walk Forward Workflow (Simplified for profiling)
# ============================================================================


def run_walk_forward_workflow(
    n_windows: int = 5, days_per_window: int = 50, n_assets: int = 10
) -> Dict[str, Any]:
    """Run Walk Forward optimization workflow.

    This is a production-scale workflow that validates strategy robustness
    across multiple time windows.

    Args:
        n_windows: Number of walk-forward windows
        days_per_window: Number of trading days per window
        n_assets: Number of assets

    Returns:
        Dictionary with optimization results
    """
    logger.info(
        f"Starting Walk Forward workflow: {n_windows} windows, {days_per_window} days/window, {n_assets} assets"
    )

    # Create synthetic data for entire period
    total_days = days_per_window * n_windows + 100  # Extra for lookback
    data = create_synthetic_price_data(n_days=total_days, n_assets=n_assets)
    logger.info(f"Generated {len(data)} rows of synthetic price data")

    # Simple parameter space for walk-forward
    param_space = ParameterSpace(
        parameters=[
            DiscreteParameter(name="lookback_short", min_value=5, max_value=20, step=5),
            DiscreteParameter(name="lookback_long", min_value=30, max_value=60, step=10),
        ]
    )

    window_results = []

    # Simulate walk-forward windows
    for window_id in range(n_windows):
        start_idx = window_id * days_per_window
        end_idx = start_idx + days_per_window + 100  # Include lookback

        # Get window data
        window_dates = sorted(data["date"].unique().to_list())[start_idx:end_idx]
        window_data = data.filter(pl.col("date").is_in(window_dates))

        # Run grid search on this window
        grid = GridSearchAlgorithm(
            parameter_space=param_space,
            early_stopping_rounds=None,
        )

        trial_num = 0
        best_score = Decimal("-Infinity")
        best_params = None

        while not grid.is_complete():
            trial_num += 1
            params = grid.suggest()
            result = simple_ma_crossover_backtest(params, window_data)
            sharpe_ratio = Decimal(str(result["performance_metrics"]["sharpe_ratio"]))
            grid.update(params, sharpe_ratio)

            if sharpe_ratio > best_score:
                best_score = sharpe_ratio
                best_params = params

        window_results.append(
            {
                "window_id": window_id,
                "best_params": best_params,
                "best_score": float(best_score),
                "trials": trial_num,
            }
        )

        logger.info(f"Window {window_id + 1}/{n_windows} complete: best_sharpe={best_score:.3f}")

    logger.info(f"Walk Forward complete: {n_windows} windows processed")

    return {
        "total_windows": n_windows,
        "window_results": window_results,
        "total_backtests": sum(w["trials"] for w in window_results),
        "dataset_size": len(data),
    }


# ============================================================================
# Production Profiling Execution
# ============================================================================


def run_production_profiling():
    """Execute all production profiling runs (T032-T034)."""

    # Create output directories
    PROFILING_DIR.mkdir(parents=True, exist_ok=True)
    BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 80)
    logger.info("PRODUCTION PROFILING RUNS - T032, T033, T034")
    logger.info("=" * 80)

    # ========================================================================
    # T032: Execute production-scale Grid Search profiling
    # ========================================================================

    logger.info("\n" + "=" * 80)
    logger.info("T032: Grid Search Production Profiling")
    logger.info("=" * 80)
    logger.info("Configuration: 100 combinations × 252 days × 10 assets")

    grid_result, grid_metrics = profile_workflow(
        workflow_fn=run_grid_search_workflow,
        workflow_args=(100, 252, 10),  # 100 combinations, 252 days, 10 assets
        profiler_type="cprofile",
        output_dir=str(PROFILING_DIR),
        run_id="grid_search_production",
    )

    logger.info(f"Grid Search completed in {grid_metrics['total_time_seconds']:.2f}s")
    logger.info(f"Total trials: {grid_result['total_trials']}")
    logger.info(f"Dataset size: {grid_result['dataset_size']:,} rows")

    # Generate bottleneck report for Grid Search
    logger.info("\nGenerating bottleneck analysis report...")
    grid_json_report, grid_json_path, grid_md_path = generate_bottleneck_report(
        profile_stats_path=str(PROFILING_DIR / "grid_search_production_cprofile.stats"),
        workflow_name="Grid Search Production",
        output_dir=str(BENCHMARK_DIR),
    )

    logger.info(f"Reports generated:")
    logger.info(f"  JSON: {grid_json_path}")
    logger.info(f"  Markdown: {grid_md_path}")

    # Generate flame graph visualization
    logger.info("\nGenerating flame graph visualization...")
    grid_svg_path = generate_flame_graph(
        profile_stats_path=str(PROFILING_DIR / "grid_search_production_cprofile.stats"),
        title="Grid Search Production Flame Graph",
    )
    logger.info(f"  SVG: {grid_svg_path}")

    # ========================================================================
    # T033: Execute production-scale Walk Forward profiling
    # ========================================================================

    logger.info("\n" + "=" * 80)
    logger.info("T033: Walk Forward Production Profiling")
    logger.info("=" * 80)
    logger.info("Configuration: 5 windows × 50 days/window × 10 assets")

    wf_result, wf_metrics = profile_workflow(
        workflow_fn=run_walk_forward_workflow,
        workflow_args=(5, 50, 10),  # 5 windows, 50 days/window, 10 assets
        profiler_type="cprofile",
        output_dir=str(PROFILING_DIR),
        run_id="walk_forward_production",
    )

    logger.info(f"Walk Forward completed in {wf_metrics['total_time_seconds']:.2f}s")
    logger.info(f"Total windows: {wf_result['total_windows']}")
    logger.info(f"Total backtests: {wf_result['total_backtests']}")
    logger.info(f"Dataset size: {wf_result['dataset_size']:,} rows")

    # Generate bottleneck report for Walk Forward
    logger.info("\nGenerating bottleneck analysis report...")
    wf_json_report, wf_json_path, wf_md_path = generate_bottleneck_report(
        profile_stats_path=str(PROFILING_DIR / "walk_forward_production_cprofile.stats"),
        workflow_name="Walk Forward Production",
        output_dir=str(BENCHMARK_DIR),
    )

    logger.info(f"Reports generated:")
    logger.info(f"  JSON: {wf_json_path}")
    logger.info(f"  Markdown: {wf_md_path}")

    # Generate flame graph visualization
    logger.info("\nGenerating flame graph visualization...")
    wf_svg_path = generate_flame_graph(
        profile_stats_path=str(PROFILING_DIR / "walk_forward_production_cprofile.stats"),
        title="Walk Forward Production Flame Graph",
    )
    logger.info(f"  SVG: {wf_svg_path}")

    # ========================================================================
    # T034: Validate >0.5% bottleneck identification
    # ========================================================================

    logger.info("\n" + "=" * 80)
    logger.info("T034: Validate >0.5% Bottleneck Identification")
    logger.info("=" * 80)

    # Validate Grid Search bottlenecks
    grid_bottlenecks_gt_05 = [
        b for b in grid_json_report["bottlenecks"] if b["percent_cumtime"] >= 0.5
    ]

    logger.info(f"\nGrid Search Bottleneck Analysis:")
    logger.info(f"  Total bottlenecks >0.5%: {len(grid_bottlenecks_gt_05)}")
    logger.info(f"  Expected: {grid_json_report['summary']['bottlenecks_gt_05_percent']}")

    assert (
        len(grid_bottlenecks_gt_05) == grid_json_report["summary"]["bottlenecks_gt_05_percent"]
    ), "Grid Search: Mismatch in bottleneck count"

    logger.info("  ✓ Validation passed")

    # Display top 5 bottlenecks
    logger.info("\n  Top 5 Bottlenecks:")
    for idx, bottleneck in enumerate(grid_json_report["summary"]["top_5_bottlenecks"], 1):
        logger.info(
            f"    {idx}. {bottleneck['function']}: {bottleneck['percent_cumtime']:.2f}% "
            f"({bottleneck['ncalls']:,} calls, {bottleneck['cost_type']})"
        )

    # Validate Walk Forward bottlenecks
    wf_bottlenecks_gt_05 = [b for b in wf_json_report["bottlenecks"] if b["percent_cumtime"] >= 0.5]

    logger.info(f"\nWalk Forward Bottleneck Analysis:")
    logger.info(f"  Total bottlenecks >0.5%: {len(wf_bottlenecks_gt_05)}")
    logger.info(f"  Expected: {wf_json_report['summary']['bottlenecks_gt_05_percent']}")

    assert (
        len(wf_bottlenecks_gt_05) == wf_json_report["summary"]["bottlenecks_gt_05_percent"]
    ), "Walk Forward: Mismatch in bottleneck count"

    logger.info("  ✓ Validation passed")

    # Display top 5 bottlenecks
    logger.info("\n  Top 5 Bottlenecks:")
    for idx, bottleneck in enumerate(wf_json_report["summary"]["top_5_bottlenecks"], 1):
        logger.info(
            f"    {idx}. {bottleneck['function']}: {bottleneck['percent_cumtime']:.2f}% "
            f"({bottleneck['ncalls']:,} calls, {bottleneck['cost_type']})"
        )

    # ========================================================================
    # Summary
    # ========================================================================

    logger.info("\n" + "=" * 80)
    logger.info("PRODUCTION PROFILING COMPLETE")
    logger.info("=" * 80)

    logger.info("\nTask Completion:")
    logger.info("  ✓ T032: Grid Search profiling completed")
    logger.info("  ✓ T033: Walk Forward profiling completed")
    logger.info("  ✓ T034: >0.5% bottleneck identification validated")

    logger.info("\nDeliverables:")
    logger.info(f"  Grid Search Profile: {PROFILING_DIR / 'grid_search_production_cprofile.stats'}")
    logger.info(f"  Grid Search Report (JSON): {grid_json_path}")
    logger.info(f"  Grid Search Report (MD): {grid_md_path}")
    logger.info(f"  Grid Search Flame Graph (SVG): {grid_svg_path}")
    logger.info(
        f"  Walk Forward Profile: {PROFILING_DIR / 'walk_forward_production_cprofile.stats'}"
    )
    logger.info(f"  Walk Forward Report (JSON): {wf_json_path}")
    logger.info(f"  Walk Forward Report (MD): {wf_md_path}")
    logger.info(f"  Walk Forward Flame Graph (SVG): {wf_svg_path}")

    logger.info("\n" + "=" * 80)

    return {
        "grid_search": {
            "result": grid_result,
            "metrics": grid_metrics,
            "bottlenecks": grid_json_report,
        },
        "walk_forward": {"result": wf_result, "metrics": wf_metrics, "bottlenecks": wf_json_report},
    }


if __name__ == "__main__":
    run_production_profiling()
