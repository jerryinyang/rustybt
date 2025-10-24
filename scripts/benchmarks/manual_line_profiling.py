"""Manual line-by-line timing analysis of bottleneck function.

Since line_profiler isn't installed, we'll manually time each operation
to show exactly what's slow inside simple_ma_crossover_backtest().
"""

import logging
import time
from pathlib import Path

import numpy as np
import polars as pl

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Import dependencies
import sys

sys.path.insert(0, str(Path(__file__).parent))
from run_production_profiling import create_synthetic_price_data


def simple_ma_crossover_backtest_instrumented(params: dict, data: pl.DataFrame) -> dict:
    """Instrumented version with manual timing."""

    timings = {}

    # Operation 1: Extract parameters
    t0 = time.perf_counter()
    lookback_short = params["lookback_short"]
    lookback_long = params["lookback_long"]
    timings["extract_params"] = time.perf_counter() - t0

    # Operation 2: Get unique assets
    t0 = time.perf_counter()
    assets = data["asset"].unique().to_list()
    timings["get_unique_assets"] = time.perf_counter() - t0

    all_returns = []

    # Track per-asset operations
    filter_times = []
    sort_times = []
    to_numpy_times = []
    ma_calc_times = []
    signal_times = []
    return_calc_times = []

    # Operation 3: Process each asset
    for asset in assets:
        # 3a: Filter data for this asset
        t0 = time.perf_counter()
        asset_data = data.filter(pl.col("asset") == asset).sort("date")
        filter_times.append(time.perf_counter() - t0)

        # 3b: Extract prices to NumPy
        t0 = time.perf_counter()
        prices = asset_data["close"].to_numpy()
        to_numpy_times.append(time.perf_counter() - t0)

        if len(prices) < lookback_long + 1:
            continue

        # 3c: Calculate moving averages
        t0 = time.perf_counter()
        fast_ma = np.convolve(prices, np.ones(lookback_short) / lookback_short, mode="valid")
        slow_ma = np.convolve(prices, np.ones(lookback_long) / lookback_long, mode="valid")
        ma_calc_times.append(time.perf_counter() - t0)

        # 3d: Align arrays
        t0 = time.perf_counter()
        min_len = min(len(fast_ma), len(slow_ma))
        fast_ma = fast_ma[:min_len]
        slow_ma = slow_ma[:min_len]
        timings.setdefault("array_alignment", 0)
        timings["array_alignment"] += time.perf_counter() - t0

        # 3e: Generate signals
        t0 = time.perf_counter()
        signals = np.where(fast_ma > slow_ma, 1, -1)
        signal_times.append(time.perf_counter() - t0)

        # 3f: Calculate returns
        t0 = time.perf_counter()
        aligned_prices = prices[lookback_long : lookback_long + min_len + 1]
        returns = np.diff(aligned_prices) / aligned_prices[:-1]

        if len(signals) > len(returns):
            signals = signals[: len(returns)]
        elif len(returns) > len(signals):
            returns = returns[: len(signals)]

        strategy_returns = signals * returns
        all_returns.extend(strategy_returns.tolist())
        return_calc_times.append(time.perf_counter() - t0)

    # Aggregate timing stats
    timings["filter_per_asset_avg"] = np.mean(filter_times) if filter_times else 0
    timings["filter_per_asset_total"] = np.sum(filter_times) if filter_times else 0
    timings["to_numpy_per_asset_avg"] = np.mean(to_numpy_times) if to_numpy_times else 0
    timings["to_numpy_per_asset_total"] = np.sum(to_numpy_times) if to_numpy_times else 0
    timings["ma_calc_per_asset_avg"] = np.mean(ma_calc_times) if ma_calc_times else 0
    timings["ma_calc_per_asset_total"] = np.sum(ma_calc_times) if ma_calc_times else 0
    timings["signal_gen_per_asset_avg"] = np.mean(signal_times) if signal_times else 0
    timings["signal_gen_per_asset_total"] = np.sum(signal_times) if signal_times else 0
    timings["return_calc_per_asset_avg"] = np.mean(return_calc_times) if return_calc_times else 0
    timings["return_calc_per_asset_total"] = np.sum(return_calc_times) if return_calc_times else 0

    # Operation 4: Calculate final metrics
    t0 = time.perf_counter()
    if not all_returns:
        result = {
            "performance_metrics": {
                "sharpe_ratio": 0.0,
                "total_return": 0.0,
            }
        }
    else:
        all_returns = np.array(all_returns)
        mean_return = all_returns.mean()
        std_return = all_returns.std()
        sharpe = (mean_return / std_return * np.sqrt(252)) if std_return > 0 else 0.0
        total_return = (1 + all_returns).prod() - 1
        result = {
            "performance_metrics": {
                "sharpe_ratio": float(sharpe),
                "total_return": float(total_return),
            }
        }
    timings["final_metrics"] = time.perf_counter() - t0

    return result, timings


def analyze_line_level_bottlenecks():
    """Analyze line-level bottlenecks manually."""

    logger.info("=" * 80)
    logger.info("MANUAL LINE-BY-LINE TIMING ANALYSIS")
    logger.info("=" * 80)
    logger.info("")

    # Create test data
    logger.info("Creating test data (252 days × 10 assets)...")
    data = create_synthetic_price_data(n_days=252, n_assets=10, seed=42)
    params = {"lookback_short": 10, "lookback_long": 30}

    logger.info("Running instrumented backtest...")
    logger.info("")

    # Run instrumented version
    result, timings = simple_ma_crossover_backtest_instrumented(params, data)

    # Calculate total time
    total_time = sum(timings.values())

    # Display results
    logger.info("=" * 80)
    logger.info("LINE-LEVEL TIMING BREAKDOWN")
    logger.info("=" * 80)
    logger.info("")
    logger.info(f"Total function time: {total_time*1000:.3f}ms")
    logger.info("")

    # Sort by time contribution
    sorted_timings = sorted(timings.items(), key=lambda x: x[1], reverse=True)

    logger.info("Operation                          Time (ms)    % of Total")
    logger.info("-" * 80)

    for operation, duration in sorted_timings:
        pct = (duration / total_time * 100) if total_time > 0 else 0
        ms = duration * 1000
        logger.info(f"{operation:35} {ms:8.3f}ms   {pct:6.2f}%")

    logger.info("")
    logger.info("=" * 80)
    logger.info("KEY INSIGHTS")
    logger.info("=" * 80)
    logger.info("")

    # Analyze findings
    filter_total = timings.get("filter_per_asset_total", 0)
    filter_pct = (filter_total / total_time * 100) if total_time > 0 else 0

    to_numpy_total = timings.get("to_numpy_per_asset_total", 0)
    to_numpy_pct = (to_numpy_total / total_time * 100) if total_time > 0 else 0

    ma_total = timings.get("ma_calc_per_asset_total", 0)
    ma_pct = (ma_total / total_time * 100) if total_time > 0 else 0

    logger.info(f"1. POLARS FILTERING: {filter_pct:.1f}% of runtime")
    logger.info(f"   - Called 10 times (once per asset)")
    logger.info(f"   - Average: {timings.get('filter_per_asset_avg', 0)*1000:.3f}ms per call")
    logger.info(f"   - This is PURE OVERHEAD - could be eliminated with caching")
    logger.info("")

    logger.info(f"2. DATAFRAME→NUMPY CONVERSION: {to_numpy_pct:.1f}% of runtime")
    logger.info(f"   - Called 10 times (once per asset)")
    logger.info(f"   - Average: {timings.get('to_numpy_per_asset_avg', 0)*1000:.3f}ms per call")
    logger.info(f"   - This is MEMORY COPY overhead")
    logger.info("")

    logger.info(f"3. ACTUAL COMPUTATION (Moving Averages): {ma_pct:.1f}% of runtime")
    logger.info(f"   - This is the REAL WORK")
    logger.info(f"   - Called 10 times (once per asset)")
    logger.info(f"   - Average: {timings.get('ma_calc_per_asset_avg', 0)*1000:.3f}ms per call")
    logger.info("")

    overhead = filter_pct + to_numpy_pct
    computation = ma_pct

    logger.info("=" * 80)
    logger.info(f"OVERHEAD vs COMPUTATION")
    logger.info("=" * 80)
    logger.info(f"Data Wrangling Overhead: {overhead:.1f}%")
    logger.info(f"Actual Computation:      {computation:.1f}%")
    logger.info("")
    logger.info(
        f"Overhead/Computation Ratio: {overhead/computation if computation > 0 else 0:.2f}x"
    )
    logger.info("")
    logger.info("🚨 We're spending MORE time moving data than computing!")
    logger.info("")


if __name__ == "__main__":
    analyze_line_level_bottlenecks()
