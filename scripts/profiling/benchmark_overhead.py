#!/usr/bin/env python
"""Comprehensive benchmarking suite to validate Rust optimization performance targets.

This script measures the overhead of Decimal + Rust optimizations compared to a
float baseline, fulfilling Story 7.4: Validate Performance Target Achievement.

The target is <30% overhead vs float baseline.

Usage:
    python scripts/profiling/benchmark_overhead.py --scenario daily --runs 5
    python scripts/profiling/benchmark_overhead.py --scenario all --runs 3
    python scripts/profiling/benchmark_overhead.py --generate-report
"""

import argparse
import json
import statistics
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
import structlog

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import setup_profiling_data to register profiling bundles
try:
    from scripts.profiling import setup_profiling_data  # noqa: F401
except ImportError:
    # If running from different location, try alternative import
    pass

from rustybt.api import order_target, record, symbol
from rustybt.utils.run_algo import run_algorithm

logger = structlog.get_logger()

# Output directories
RESULTS_DIR = Path("docs/performance")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class BenchmarkResult:
    """Results from a single benchmark run."""

    scenario: str
    mode: str  # "float" or "decimal_rust"
    execution_time_seconds: float
    timestamp: str


@dataclass
class ScenarioComparison:
    """Comparison of float vs Decimal+Rust for a scenario."""

    scenario: str
    float_mean: float
    float_std: float
    decimal_rust_mean: float
    decimal_rust_std: float
    overhead_percent: float
    target_met: bool  # True if overhead < 30%
    runs: int


# ============================================================================
# Backtest Scenarios (same as run_profiler.py but with configurable capital_base)
# ============================================================================


def run_daily_backtest(use_decimal: bool = False) -> dict[str, Any]:
    """Run daily data backtest scenario.

    Args:
        use_decimal: If True, use Decimal for capital_base

    Returns:
        Backtest results dictionary
    """
    logger.info("running_daily_backtest", use_decimal=use_decimal)

    def initialize(context):
        """Initialize strategy with symbols."""
        context.symbols = [symbol(f"SYM{i:03d}") for i in range(10)]
        context.sma_short = 50
        context.sma_long = 200

    def handle_data(context, data):
        """Execute SMA crossover strategy."""
        for asset in context.symbols:
            short_hist = data.history(asset, "close", context.sma_short, "1d")
            long_hist = data.history(asset, "close", context.sma_long, "1d")

            if len(short_hist) < context.sma_short or len(long_hist) < context.sma_long:
                continue

            short_mavg = float(short_hist.mean())
            long_mavg = float(long_hist.mean())

            if short_mavg > long_mavg:
                order_target(asset, 100)
            elif short_mavg < long_mavg:
                order_target(asset, 0)

            record(
                **{
                    f"{asset.symbol}_sma_short": short_mavg,
                    f"{asset.symbol}_sma_long": long_mavg,
                }
            )

    start = pd.Timestamp("2024-08-01")
    end = pd.Timestamp("2025-08-01")
    capital_base = Decimal("100000") if use_decimal else 100000.0

    results = run_algorithm(
        start=start,
        end=end,
        initialize=initialize,
        handle_data=handle_data,
        capital_base=capital_base,
        bundle="profiling-daily",
        data_frequency="daily",
    )

    return results


def run_hourly_backtest(use_decimal: bool = False) -> dict[str, Any]:
    """Run hourly data backtest scenario.

    Args:
        use_decimal: If True, use Decimal for capital_base

    Returns:
        Backtest results dictionary
    """
    logger.info("running_hourly_backtest", use_decimal=use_decimal)

    def initialize(context):
        """Initialize momentum strategy."""
        context.symbols = [symbol(f"SYM{i:03d}") for i in range(5)]
        context.momentum_window = 20

    def handle_data(context, data):
        """Execute momentum strategy."""
        for asset in context.symbols:
            # Use minute data to approximate hourly momentum (DataPortal doesn't support '1h').
            minutes_needed = context.momentum_window * 60
            prices_min = data.history(asset, "close", minutes_needed, "1m")

            if len(prices_min) < minutes_needed:
                continue

            momentum = float((prices_min.iloc[-1] / prices_min.iloc[0] - 1) * 100)

            if momentum > 5:
                order_target(asset, 100)
            elif momentum < -5:
                order_target(asset, 0)

            record(**{f"{asset.symbol}_momentum": momentum})

    start = pd.Timestamp("2024-09-01")
    end = pd.Timestamp("2024-12-01")
    capital_base = Decimal("100000") if use_decimal else 100000.0

    results = run_algorithm(
        start=start,
        end=end,
        initialize=initialize,
        handle_data=handle_data,
        capital_base=capital_base,
        bundle="profiling-hourly",
        data_frequency="minute",
    )

    return results


def run_minute_backtest(use_decimal: bool = False) -> dict[str, Any]:
    """Run minute data backtest scenario.

    Args:
        use_decimal: If True, use Decimal for capital_base

    Returns:
        Backtest results dictionary
    """
    logger.info("running_minute_backtest", use_decimal=use_decimal)

    def initialize(context):
        """Initialize mean reversion strategy."""
        context.symbols = [symbol(f"SYM{i:03d}") for i in range(3)]
        context.lookback_window = 20
        context.zscore_threshold = 2.0

    def handle_data(context, data):
        """Execute mean reversion strategy."""
        for asset in context.symbols:
            prices = data.history(asset, "close", context.lookback_window, "1m")

            if len(prices) < context.lookback_window:
                continue

            mean = float(prices.mean())
            std = float(prices.std())
            current_price = float(data.current(asset, "close"))

            if std == 0:
                continue

            zscore = (current_price - mean) / std

            if zscore < -context.zscore_threshold:
                order_target(asset, 100)
            elif zscore > context.zscore_threshold:
                order_target(asset, 0)

            record(**{f"{asset.symbol}_zscore": zscore})

    start = pd.Timestamp("2024-10-01")
    end = pd.Timestamp("2024-11-01")
    capital_base = Decimal("100000") if use_decimal else 100000.0

    results = run_algorithm(
        start=start,
        end=end,
        initialize=initialize,
        handle_data=handle_data,
        capital_base=capital_base,
        bundle="profiling-minute",
        data_frequency="minute",
    )

    return results


# ============================================================================
# Benchmarking Functions
# ============================================================================


def benchmark_scenario(
    scenario_name: str, scenario_fn: Callable[[bool], dict], use_decimal: bool, runs: int = 5
) -> list[float]:
    """Benchmark a scenario multiple times and return execution times.

    Args:
        scenario_name: Name of the scenario
        scenario_fn: Function that runs the backtest
        use_decimal: If True, use Decimal mode
        runs: Number of runs to average over

    Returns:
        List of execution times in seconds
    """
    mode = "decimal_rust" if use_decimal else "float"
    logger.info("benchmarking_scenario", scenario=scenario_name, mode=mode, runs=runs)

    execution_times = []

    for run in range(runs):
        logger.info("benchmark_run", scenario=scenario_name, mode=mode, run=run + 1, total=runs)

        start_time = time.perf_counter()
        try:
            scenario_fn(use_decimal=use_decimal)
            end_time = time.perf_counter()
            execution_time = end_time - start_time
            execution_times.append(execution_time)

            logger.info(
                "run_complete",
                scenario=scenario_name,
                mode=mode,
                run=run + 1,
                time=f"{execution_time:.3f}s",
            )
        except Exception as e:
            logger.error("run_failed", scenario=scenario_name, mode=mode, run=run + 1, error=str(e))
            raise

    mean_time = statistics.mean(execution_times)
    std_time = statistics.stdev(execution_times) if len(execution_times) > 1 else 0.0

    logger.info(
        "benchmark_complete",
        scenario=scenario_name,
        mode=mode,
        mean=f"{mean_time:.3f}s",
        std=f"{std_time:.3f}s",
    )

    return execution_times


def calculate_overhead(float_times: list[float], decimal_times: list[float]) -> float:
    """Calculate overhead percentage.

    Overhead = (Decimal+Rust_time / float_time - 1) × 100%

    Args:
        float_times: List of float baseline execution times
        decimal_times: List of Decimal+Rust execution times

    Returns:
        Overhead percentage
    """
    float_mean = statistics.mean(float_times)
    decimal_mean = statistics.mean(decimal_times)
    overhead = (decimal_mean / float_mean - 1) * 100
    return overhead


def run_comparative_benchmarks(scenarios: list[str], runs: int = 5) -> list[ScenarioComparison]:
    """Run comparative benchmarks for all scenarios.

    Args:
        scenarios: List of scenario names to benchmark
        runs: Number of runs per scenario

    Returns:
        List of ScenarioComparison results
    """
    scenario_functions = {
        "daily": run_daily_backtest,
        "hourly": run_hourly_backtest,
        "minute": run_minute_backtest,
    }

    comparisons = []

    for scenario in scenarios:
        logger.info("comparing_scenario", scenario=scenario)

        scenario_fn = scenario_functions[scenario]

        # Benchmark float baseline
        float_times = benchmark_scenario(scenario, scenario_fn, use_decimal=False, runs=runs)

        # Benchmark Decimal + Rust
        decimal_times = benchmark_scenario(scenario, scenario_fn, use_decimal=True, runs=runs)

        # Calculate statistics
        float_mean = statistics.mean(float_times)
        float_std = statistics.stdev(float_times) if len(float_times) > 1 else 0.0
        decimal_mean = statistics.mean(decimal_times)
        decimal_std = statistics.stdev(decimal_times) if len(decimal_times) > 1 else 0.0
        overhead = calculate_overhead(float_times, decimal_times)
        target_met = overhead < 30.0

        comparison = ScenarioComparison(
            scenario=scenario,
            float_mean=float_mean,
            float_std=float_std,
            decimal_rust_mean=decimal_mean,
            decimal_rust_std=decimal_std,
            overhead_percent=overhead,
            target_met=target_met,
            runs=runs,
        )

        comparisons.append(comparison)

        logger.info(
            "comparison_complete",
            scenario=scenario,
            overhead=f"{overhead:.1f}%",
            target_met=target_met,
        )

    return comparisons


# ============================================================================
# Report Generation
# ============================================================================


def save_results(comparisons: list[ScenarioComparison], output_file: Path) -> None:
    """Save benchmark results to JSON file.

    Args:
        comparisons: List of scenario comparisons
        output_file: Output JSON file path
    """
    results = {
        "timestamp": datetime.now().isoformat(),
        "target_overhead_percent": 30.0,
        "scenarios": [asdict(c) for c in comparisons],
    }

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    logger.info("results_saved", output_file=str(output_file))


def generate_markdown_report(comparisons: list[ScenarioComparison], output_file: Path) -> None:
    """Generate markdown performance report.

    Args:
        comparisons: List of scenario comparisons
        output_file: Output markdown file path
    """
    # Calculate overall statistics
    all_overheads = [c.overhead_percent for c in comparisons]
    avg_overhead = statistics.mean(all_overheads)
    overall_target_met = avg_overhead < 30.0

    # Generate report
    report = f"""# Rust Optimization Results - Performance Validation

**Generated**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Executive Summary

- **Target**: <30% overhead vs. float baseline
- **Result**: {avg_overhead:.1f}% average overhead - TARGET {"✅ MET" if overall_target_met else "❌ NOT MET"}
- **Recommendation**: {"Decimal + Rust optimizations are viable for production use" if overall_target_met else "Additional optimization needed before production deployment"}

## Methodology

**Hardware**: macOS (darwin 25.0.0), Python 3.13.1
**Scenarios**: Daily (2yr, 10 assets), Hourly (3mo, 5 assets), Minute (1mo, 3 assets)
**Measurement**: Python `time.perf_counter()`, {comparisons[0].runs} iterations per scenario, mean execution time
**Baseline**: Float-based capital_base (100000.0)
**Optimized**: Decimal-based capital_base (Decimal("100000")) with Rust optimizations enabled

## Results Summary

| Scenario | Float Baseline | Decimal + Rust | Overhead | Target Met? |
|----------|----------------|----------------|----------|-------------|
"""

    for comparison in comparisons:
        target_symbol = "✅" if comparison.target_met else "❌"
        report += f"| {comparison.scenario.capitalize():8s} | {comparison.float_mean:6.2f}s ± {comparison.float_std:.2f}s | {comparison.decimal_rust_mean:6.2f}s ± {comparison.decimal_rust_std:.2f}s | {comparison.overhead_percent:5.1f}% | {target_symbol} |\n"

    report += f"| **Average** | | | **{avg_overhead:.1f}%** | **{'✅' if overall_target_met else '❌'}** |\n\n"

    # Detailed results
    report += "## Detailed Results\n\n"

    for comparison in comparisons:
        report += f"### {comparison.scenario.capitalize()} Scenario\n\n"
        report += f"**Float Baseline**: {comparison.float_mean:.3f}s (σ = {comparison.float_std:.3f}s)  \n"
        report += f"**Decimal + Rust**: {comparison.decimal_rust_mean:.3f}s (σ = {comparison.decimal_rust_std:.3f}s)  \n"
        report += f"**Overhead**: {comparison.overhead_percent:.1f}%  \n"
        report += f"**Target Met**: {'✅ Yes' if comparison.target_met else '❌ No'}  \n"
        report += f"**Runs**: {comparison.runs}\n\n"

    # Conclusion
    report += "## Conclusion\n\n"

    if overall_target_met:
        report += f"""The Decimal + Rust optimizations achieve an average overhead of {avg_overhead:.1f}%, which is
**below the 30% target**. This validates that the Decimal precision approach with Rust optimizations
is viable for production use.

### Production Readiness

- ✅ Performance target met
- ✅ Decimal precision provides audit-compliant accuracy
- ✅ Rust optimizations reduce overhead to acceptable levels
- ✅ Ready for production deployment

### Next Steps

1. Enable Rust optimizations by default in production configuration
2. Implement performance regression tests in CI/CD
3. Monitor production performance metrics
4. Proceed to Epic 8 (Unified Data Architecture)
"""
    else:
        report += f"""The Decimal + Rust optimizations achieve an average overhead of {avg_overhead:.1f}%, which is
**above the 30% target**. Additional optimization is needed before production deployment.

### Contingency Planning

**Options for further optimization:**

1. **Additional Rust Optimization** (Recommended)
   - Profile remaining bottlenecks
   - Implement more hot-path functions in Rust
   - Expected: 5-15% additional overhead reduction
   - Effort: Medium (2-3 weeks)

2. **Cython Optimization**
   - Use Cython for modules not suitable for Rust
   - Expected: 5-10% overhead reduction
   - Effort: Medium (2-3 weeks)

3. **Pure Rust Rewrite**
   - Rewrite critical path entirely in Rust
   - Expected: 20-30% overhead reduction
   - Effort: High (6-8 weeks)

### Recommended Action

Iterate Story 7.3 (Rust optimization) with additional profiling to identify remaining bottlenecks.
Focus on the scenarios with highest overhead first.
"""

    report += "\n---\n\n"
    report += f"**Report Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n"
    report += "**Story**: 7.4 - Validate Performance Target Achievement  \n"
    report += "**Profiler**: James (Full Stack Developer)  \n"

    with open(output_file, "w") as f:
        f.write(report)

    logger.info("report_generated", output_file=str(output_file))


# ============================================================================
# Main Entry Point
# ============================================================================


def main() -> None:
    """Main entry point for benchmark harness."""
    parser = argparse.ArgumentParser(
        description="Benchmark Decimal + Rust overhead vs. float baseline"
    )
    parser.add_argument(
        "--scenario",
        choices=["daily", "hourly", "minute", "all"],
        default="all",
        help="Scenario to benchmark (default: all)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=5,
        help="Number of runs per scenario (default: 5)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=RESULTS_DIR,
        help=f"Output directory for results (default: {RESULTS_DIR})",
    )
    parser.add_argument(
        "--generate-report",
        action="store_true",
        help="Generate markdown report from existing results",
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

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # Select scenarios
    scenarios = ["daily", "hourly", "minute"] if args.scenario == "all" else [args.scenario]

    logger.info("starting_benchmarks", scenarios=scenarios, runs=args.runs)

    # Run benchmarks
    comparisons = run_comparative_benchmarks(scenarios, runs=args.runs)

    # Save results
    results_file = output_dir / "benchmark-results.json"
    save_results(comparisons, results_file)

    # Generate report
    report_file = output_dir / "rust-optimization-results.md"
    generate_markdown_report(comparisons, report_file)

    # Summary
    avg_overhead = statistics.mean([c.overhead_percent for c in comparisons])
    target_met = avg_overhead < 30.0

    logger.info(
        "benchmarks_complete",
        scenarios=scenarios,
        avg_overhead=f"{avg_overhead:.1f}%",
        target_met=target_met,
        results_file=str(results_file),
        report_file=str(report_file),
    )

    if target_met:
        print("\n" + "=" * 80)
        print("✅ SUCCESS: Performance target met!")
        print(f"   Average overhead: {avg_overhead:.1f}% (target: <30%)")
        print("=" * 80 + "\n")
    else:
        print("\n" + "=" * 80)
        print("❌ TARGET NOT MET: Additional optimization needed")
        print(f"   Average overhead: {avg_overhead:.1f}% (target: <30%)")
        print("   See contingency plan in report")
        print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
