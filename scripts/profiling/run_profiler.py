#!/usr/bin/env python
"""Profiling harness for RustyBT backtest scenarios.

This script profiles representative backtest scenarios using cProfile, py-spy,
and memory_profiler to identify performance bottlenecks for Rust optimization.

Usage:
    python scripts/profiling/run_profiler.py --scenario daily --profiler cprofile
    python scripts/profiling/run_profiler.py --scenario all --profiler all
    python scripts/profiling/run_profiler.py --list-scenarios
"""

import argparse
import cProfile
import pstats
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

# Add parent directory to path to import rustybt
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import setup_profiling_data to register profiling bundles
try:
    from scripts.profiling import setup_profiling_data  # noqa: F401
except ImportError:
    # If running from different location, try alternative import
    pass

logger = structlog.get_logger()

# Profiling output directory
PROFILE_DIR = Path("docs/performance/profiles/baseline")
PROFILE_DIR.mkdir(parents=True, exist_ok=True)


# Placeholder strategy classes
# These will be replaced with actual backtest implementations in later subtasks


def profile_with_cprofile(
    scenario_name: str, run_backtest_fn: Any, output_dir: Path = PROFILE_DIR
) -> None:
    """Profile backtest scenario using cProfile.

    Args:
        scenario_name: Name of the scenario being profiled
        run_backtest_fn: Function that runs the backtest
        output_dir: Directory for profiling output
    """
    logger.info("profiling_with_cprofile", scenario=scenario_name)

    # Output file
    profile_file = output_dir / f"{scenario_name}_cprofile.pstats"

    # Run profiling
    profiler = cProfile.Profile()
    profiler.enable()

    try:
        run_backtest_fn()
    finally:
        profiler.disable()

    # Save stats
    profiler.dump_stats(str(profile_file))

    # Print summary
    stats = pstats.Stats(str(profile_file))
    stats.sort_stats("cumulative")

    logger.info(
        "cprofile_complete",
        scenario=scenario_name,
        output_file=str(profile_file),
        total_calls=stats.total_calls,
    )

    # Save top 20 functions to text file
    summary_file = output_dir / f"{scenario_name}_cprofile_summary.txt"
    with open(summary_file, "w") as f:
        f.write(f"cProfile Summary: {scenario_name}\n")
        f.write(f"Timestamp: {datetime.now().isoformat()}\n")
        f.write("=" * 80 + "\n\n")
        f.write("Top 20 functions by cumulative time:\n")
        f.write("=" * 80 + "\n")
        stats.stream = f
        stats.print_stats(20)


def profile_with_memory_profiler(
    scenario_name: str, run_backtest_fn: Any, output_dir: Path = PROFILE_DIR
) -> None:
    """Profile backtest scenario using memory_profiler.

    Args:
        scenario_name: Name of the scenario being profiled
        run_backtest_fn: Function that runs the backtest
        output_dir: Directory for profiling output
    """
    logger.info("profiling_with_memory_profiler", scenario=scenario_name)

    try:
        from memory_profiler import memory_usage
    except ImportError:
        logger.warning(
            "memory_profiler_not_installed",
            scenario=scenario_name,
            message="Install with: pip install memory_profiler",
        )
        return

    # Output file
    profile_file = output_dir / f"{scenario_name}_memory.txt"

    # Run memory profiling
    mem_usage = memory_usage((run_backtest_fn, (), {}), interval=0.1, timeout=None)

    # Save results
    with open(profile_file, "w") as f:
        f.write(f"Memory Profiling: {scenario_name}\n")
        f.write(f"Timestamp: {datetime.now().isoformat()}\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Peak memory usage: {max(mem_usage):.2f} MiB\n")
        f.write(f"Mean memory usage: {sum(mem_usage) / len(mem_usage):.2f} MiB\n")
        f.write(f"Memory samples: {len(mem_usage)}\n")
        f.write("\nMemory usage over time (MiB):\n")
        for i, mem in enumerate(mem_usage):
            f.write(f"{i * 0.1:.1f}s: {mem:.2f} MiB\n")

    logger.info(
        "memory_profiling_complete",
        scenario=scenario_name,
        output_file=str(profile_file),
        peak_memory_mb=max(mem_usage),
    )


def run_daily_scenario() -> None:
    """Run daily data backtest scenario (2 years, 50 assets, SMA strategy)."""
    logger.info("running_daily_scenario")

    import pandas as pd

    from rustybt.api import order_target, record, symbol
    from rustybt.utils.run_algo import run_algorithm

    def initialize(context):
        """Initialize strategy with symbols."""
        # Use first 10 symbols from profiling-daily bundle for faster profiling
        context.symbols = [symbol(f"SYM{i:03d}") for i in range(10)]
        context.sma_short = 50
        context.sma_long = 200

    def handle_data(context, data):
        """Execute SMA crossover strategy."""
        for asset in context.symbols:
            # Get price history
            short_hist = data.history(asset, "close", context.sma_short, "1d")
            long_hist = data.history(asset, "close", context.sma_long, "1d")

            if len(short_hist) < context.sma_short or len(long_hist) < context.sma_long:
                continue

            # Calculate SMAs
            short_mavg = float(short_hist.mean())
            long_mavg = float(long_hist.mean())

            # Trading logic
            if short_mavg > long_mavg:
                order_target(asset, 100)
            elif short_mavg < long_mavg:
                order_target(asset, 0)

            # Record for analysis
            record(
                **{f"{asset.symbol}_sma_short": short_mavg, f"{asset.symbol}_sma_long": long_mavg}
            )

    # Run backtest
    # Use fixed dates to ensure alignment with bundle data
    # Bundle generates ~2 years of data, so we start 250 trading days in
    # to allow for 200-day SMA history, and run for 1 year
    start = pd.Timestamp("2024-08-01")
    end = pd.Timestamp("2025-08-01")

    try:
        results = run_algorithm(
            start=start,
            end=end,
            initialize=initialize,
            handle_data=handle_data,
            capital_base=100000.0,  # Use float to avoid Decimal/float mixing issues during profiling
            bundle="profiling-daily",
            data_frequency="daily",
        )
        logger.info("daily_scenario_complete", total_return=float(results["returns"].sum()))
    except Exception as e:
        logger.error("daily_scenario_failed", error=str(e))
        raise


def run_hourly_scenario() -> None:
    """Run hourly data backtest scenario (6 months, 20 assets, momentum strategy)."""
    logger.info("running_hourly_scenario")

    import pandas as pd

    from rustybt.api import order_target, record, symbol
    from rustybt.utils.run_algo import run_algorithm

    def initialize(context):
        """Initialize momentum strategy."""
        # Use first 5 symbols for faster profiling
        context.symbols = [symbol(f"SYM{i:03d}") for i in range(5)]
        context.momentum_window = 20

    def handle_data(context, data):
        """Execute momentum strategy."""
        for asset in context.symbols:
            # Get price history
            prices = data.history(asset, "close", context.momentum_window, "1h")

            if len(prices) < context.momentum_window:
                continue

            # Calculate momentum (percentage change)
            momentum = float((prices.iloc[-1] / prices.iloc[0] - 1) * 100)

            # Trading logic: buy if momentum > 5%, sell if < -5%
            if momentum > 5:
                order_target(asset, 100)
            elif momentum < -5:
                order_target(asset, 0)

            record(**{f"{asset.symbol}_momentum": momentum})

    # Run backtest
    # Use fixed dates to ensure alignment with bundle data
    # Hourly scenario: 3 months of data
    start = pd.Timestamp("2024-09-01")
    end = pd.Timestamp("2024-12-01")

    try:
        results = run_algorithm(
            start=start,
            end=end,
            initialize=initialize,
            handle_data=handle_data,
            capital_base=100000.0,  # Use float to avoid Decimal/float mixing issues during profiling
            bundle="profiling-hourly",
            data_frequency="minute",  # Hourly data stored as minute data
        )
        logger.info("hourly_scenario_complete", total_return=float(results["returns"].sum()))
    except Exception as e:
        logger.error("hourly_scenario_failed", error=str(e))
        raise


def run_minute_scenario() -> None:
    """Run minute data backtest scenario (1 month, 10 assets, mean reversion strategy)."""
    logger.info("running_minute_scenario")

    import pandas as pd

    from rustybt.api import order_target, record, symbol
    from rustybt.utils.run_algo import run_algorithm

    def initialize(context):
        """Initialize mean reversion strategy."""
        # Use first 3 symbols for faster profiling (minute data is large)
        context.symbols = [symbol(f"SYM{i:03d}") for i in range(3)]
        context.lookback_window = 20
        context.zscore_threshold = 2.0

    def handle_data(context, data):
        """Execute mean reversion strategy."""
        for asset in context.symbols:
            # Get price history
            prices = data.history(asset, "close", context.lookback_window, "1m")

            if len(prices) < context.lookback_window:
                continue

            # Calculate z-score
            mean = float(prices.mean())
            std = float(prices.std())
            current_price = float(data.current(asset, "close"))

            if std == 0:
                continue

            zscore = (current_price - mean) / std

            # Trading logic: buy when oversold, sell when overbought
            if zscore < -context.zscore_threshold:
                order_target(asset, 100)
            elif zscore > context.zscore_threshold:
                order_target(asset, 0)

            record(**{f"{asset.symbol}_zscore": zscore})

    # Run backtest
    # Use fixed dates to ensure alignment with bundle data
    # Minute scenario: 1 month of data
    start = pd.Timestamp("2024-10-01")
    end = pd.Timestamp("2024-11-01")

    try:
        results = run_algorithm(
            start=start,
            end=end,
            initialize=initialize,
            handle_data=handle_data,
            capital_base=100000.0,  # Use float to avoid Decimal/float mixing issues during profiling
            bundle="profiling-minute",
            data_frequency="minute",
        )
        logger.info("minute_scenario_complete", total_return=float(results["returns"].sum()))
    except Exception as e:
        logger.error("minute_scenario_failed", error=str(e))
        raise


def list_scenarios() -> None:
    """List available profiling scenarios."""
    scenarios = {
        "daily": "Daily data backtest: 2 years, 50 assets, SMA crossover strategy",
        "hourly": "Hourly data backtest: 6 months, 20 assets, momentum strategy",
        "minute": "Minute data backtest: 1 month, 10 assets, mean reversion strategy",
        "all": "Run all scenarios",
    }

    print("Available profiling scenarios:")
    print("=" * 80)
    for name, description in scenarios.items():
        print(f"  {name:10s} - {description}")
    print()


def main() -> None:
    """Main entry point for profiling harness."""
    parser = argparse.ArgumentParser(
        description="Profile RustyBT backtest scenarios to identify bottlenecks"
    )
    parser.add_argument(
        "--scenario",
        choices=["daily", "hourly", "minute", "all"],
        default="daily",
        help="Backtest scenario to profile",
    )
    parser.add_argument(
        "--profiler",
        choices=["cprofile", "memory", "all"],
        default="cprofile",
        help="Profiler to use",
    )
    parser.add_argument(
        "--list-scenarios",
        action="store_true",
        help="List available scenarios and exit",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROFILE_DIR,
        help=f"Output directory for profiling results (default: {PROFILE_DIR})",
    )

    args = parser.parse_args()

    # Configure logging
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ]
    )

    if args.list_scenarios:
        list_scenarios()
        return

    # Update output directory
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # Select scenarios
    scenarios = ["daily", "hourly", "minute"] if args.scenario == "all" else [args.scenario]

    scenario_functions = {
        "daily": run_daily_scenario,
        "hourly": run_hourly_scenario,
        "minute": run_minute_scenario,
    }

    # Run profiling
    for scenario in scenarios:
        logger.info("starting_scenario_profiling", scenario=scenario, profiler=args.profiler)

        run_fn = scenario_functions[scenario]

        if args.profiler in ("cprofile", "all"):
            profile_with_cprofile(scenario, run_fn, output_dir)

        if args.profiler in ("memory", "all"):
            profile_with_memory_profiler(scenario, run_fn, output_dir)

        logger.info("scenario_profiling_complete", scenario=scenario)

    logger.info(
        "profiling_complete",
        scenarios=scenarios,
        profiler=args.profiler,
        output_dir=str(output_dir),
    )


if __name__ == "__main__":
    main()
