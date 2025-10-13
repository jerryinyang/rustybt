"""Performance regression tests to validate ongoing compliance with performance targets.

These tests fulfill AC9: CI/CD integration validates ongoing compliance with target.

Run with: pytest tests/regression/test_performance_regression.py -v
"""

import json
import logging
import sys
import time
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import profiling bundle registrations (required before bundles can be loaded)
# This ensures the @register decorators are executed
import scripts.profiling.setup_profiling_data  # noqa: F401
from rustybt.api import order_target, record, symbol
from rustybt.utils.run_algo import run_algorithm

logger = logging.getLogger(__name__)

# Baseline file location
BASELINE_FILE = Path(__file__).parent / "performance_baselines.json"

# Performance thresholds (from coding standards)
WARNING_THRESHOLD = 1.05  # 5% degradation warning
FAILURE_THRESHOLD = 1.20  # 20% degradation hard failure


def load_baselines() -> dict:
    """Load performance baselines from JSON file.

    Returns:
        Dictionary of baseline times by scenario
    """
    if not BASELINE_FILE.exists():
        pytest.skip(f"Baseline file not found: {BASELINE_FILE}")

    with open(BASELINE_FILE) as f:
        baselines = json.load(f)

    return baselines


def save_baselines(baselines: dict) -> None:
    """Save performance baselines to JSON file.

    Args:
        baselines: Dictionary of baseline times by scenario
    """
    with open(BASELINE_FILE, "w") as f:
        json.dump(baselines, f, indent=2)

    logger.info(f"Baselines saved to {BASELINE_FILE}")


def measure_backtest_time(backtest_fn, *args, **kwargs) -> float:
    """Measure execution time of a backtest.

    Args:
        backtest_fn: Function that runs the backtest
        *args: Positional arguments to pass to backtest_fn
        **kwargs: Keyword arguments to pass to backtest_fn

    Returns:
        Execution time in seconds
    """
    start_time = time.perf_counter()
    backtest_fn(*args, **kwargs)
    end_time = time.perf_counter()
    return end_time - start_time


# ============================================================================
# Backtest Scenarios
# ============================================================================


def run_daily_backtest_regression():
    """Run daily backtest for regression testing."""

    def initialize(context):
        context.symbols = [symbol(f"SYM{i:03d}") for i in range(10)]
        context.sma_short = 50
        context.sma_long = 200

    def handle_data(context, data):
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

    results = run_algorithm(
        start=start,
        end=end,
        initialize=initialize,
        handle_data=handle_data,
        capital_base=Decimal("100000"),
        bundle="profiling-daily",
        data_frequency="daily",
    )

    return results


def run_hourly_backtest_regression():
    """Run hourly backtest for regression testing."""

    def initialize(context):
        context.symbols = [symbol(f"SYM{i:03d}") for i in range(5)]
        context.momentum_window = 20

    def handle_data(context, data):
        for asset in context.symbols:
            # Approximate hourly momentum from minute data (DataPortal doesn't support '1h').
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

    results = run_algorithm(
        start=start,
        end=end,
        initialize=initialize,
        handle_data=handle_data,
        capital_base=Decimal("100000"),
        bundle="profiling-hourly",
        data_frequency="minute",
    )

    return results


def run_minute_backtest_regression():
    """Run minute backtest for regression testing."""

    def initialize(context):
        context.symbols = [symbol(f"SYM{i:03d}") for i in range(3)]
        context.lookback_window = 20
        context.zscore_threshold = 2.0

    def handle_data(context, data):
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

    results = run_algorithm(
        start=start,
        end=end,
        initialize=initialize,
        handle_data=handle_data,
        capital_base=Decimal("100000"),
        bundle="profiling-minute",
        data_frequency="minute",
    )

    return results


# ============================================================================
# Regression Tests
# ============================================================================


@pytest.mark.regression
@pytest.mark.slow
def test_daily_backtest_performance_regression():
    """Ensure daily backtest performance doesn't regress.

    Fails if performance degrades >20% from baseline (hard failure per coding standards).
    Warns if performance degrades >5% from baseline.
    """
    baselines = load_baselines()

    if "daily_backtest" not in baselines:
        pytest.skip("No baseline for daily_backtest")

    baseline_time = baselines["daily_backtest"]["decimal_rust"]
    warning_threshold = baseline_time * WARNING_THRESHOLD
    failure_threshold = baseline_time * FAILURE_THRESHOLD

    # Measure current performance
    actual_time = measure_backtest_time(run_daily_backtest_regression)

    # Calculate degradation
    degradation_percent = ((actual_time / baseline_time) - 1) * 100

    logger.info(
        f"Daily backtest: {actual_time:.2f}s vs baseline {baseline_time:.2f}s "
        f"({degradation_percent:+.1f}%)"
    )

    # Alert if >5% degradation
    if actual_time > warning_threshold:
        logger.warning(
            f"Performance degradation detected: {actual_time:.2f}s vs baseline {baseline_time:.2f}s "
            f"({degradation_percent:+.1f}% slower)"
        )

    # Fail if >20% degradation
    assert actual_time < failure_threshold, (
        f"Performance regression FAILURE: {actual_time:.2f}s > {failure_threshold:.2f}s "
        f"({degradation_percent:+.1f}% slower than baseline)"
    )


@pytest.mark.regression
@pytest.mark.slow
def test_hourly_backtest_performance_regression():
    """Ensure hourly backtest performance doesn't regress.

    Fails if performance degrades >20% from baseline (hard failure per coding standards).
    Warns if performance degrades >5% from baseline.
    """
    baselines = load_baselines()

    if "hourly_backtest" not in baselines:
        pytest.skip("No baseline for hourly_backtest")

    baseline_time = baselines["hourly_backtest"]["decimal_rust"]
    warning_threshold = baseline_time * WARNING_THRESHOLD
    failure_threshold = baseline_time * FAILURE_THRESHOLD

    # Measure current performance
    actual_time = measure_backtest_time(run_hourly_backtest_regression)

    # Calculate degradation
    degradation_percent = ((actual_time / baseline_time) - 1) * 100

    logger.info(
        f"Hourly backtest: {actual_time:.2f}s vs baseline {baseline_time:.2f}s "
        f"({degradation_percent:+.1f}%)"
    )

    # Alert if >5% degradation
    if actual_time > warning_threshold:
        logger.warning(
            f"Performance degradation detected: {actual_time:.2f}s vs baseline {baseline_time:.2f}s "
            f"({degradation_percent:+.1f}% slower)"
        )

    # Fail if >20% degradation
    assert actual_time < failure_threshold, (
        f"Performance regression FAILURE: {actual_time:.2f}s > {failure_threshold:.2f}s "
        f"({degradation_percent:+.1f}% slower than baseline)"
    )


@pytest.mark.regression
@pytest.mark.slow
def test_minute_backtest_performance_regression():
    """Ensure minute backtest performance doesn't regress.

    Fails if performance degrades >20% from baseline (hard failure per coding standards).
    Warns if performance degrades >5% from baseline.
    """
    baselines = load_baselines()

    if "minute_backtest" not in baselines:
        pytest.skip("No baseline for minute_backtest")

    baseline_time = baselines["minute_backtest"]["decimal_rust"]
    warning_threshold = baseline_time * WARNING_THRESHOLD
    failure_threshold = baseline_time * FAILURE_THRESHOLD

    # Measure current performance
    actual_time = measure_backtest_time(run_minute_backtest_regression)

    # Calculate degradation
    degradation_percent = ((actual_time / baseline_time) - 1) * 100

    logger.info(
        f"Minute backtest: {actual_time:.2f}s vs baseline {baseline_time:.2f}s "
        f"({degradation_percent:+.1f}%)"
    )

    # Alert if >5% degradation
    if actual_time > warning_threshold:
        logger.warning(
            f"Performance degradation detected: {actual_time:.2f}s vs baseline {baseline_time:.2f}s "
            f"({degradation_percent:+.1f}% slower)"
        )

    # Fail if >20% degradation
    assert actual_time < failure_threshold, (
        f"Performance regression FAILURE: {actual_time:.2f}s > {failure_threshold:.2f}s "
        f"({degradation_percent:+.1f}% slower than baseline)"
    )


# ============================================================================
# Baseline Creation (run manually to establish baselines)
# ============================================================================


@pytest.mark.skip(reason="Run manually to create baselines: pytest -k test_create_baselines -v")
def test_create_baselines():
    """Create initial performance baselines.

    Run this test manually after confirming benchmarks meet targets:
        pytest tests/regression/test_performance_regression.py::test_create_baselines -v -s
    """
    logger.info("Creating performance baselines...")

    baselines = {}

    # Daily backtest
    logger.info("Measuring daily backtest baseline...")
    daily_time = measure_backtest_time(run_daily_backtest_regression)
    baselines["daily_backtest"] = {"decimal_rust": daily_time}
    logger.info(f"Daily backtest baseline: {daily_time:.2f}s")

    # Hourly backtest
    logger.info("Measuring hourly backtest baseline...")
    hourly_time = measure_backtest_time(run_hourly_backtest_regression)
    baselines["hourly_backtest"] = {"decimal_rust": hourly_time}
    logger.info(f"Hourly backtest baseline: {hourly_time:.2f}s")

    # Minute backtest
    logger.info("Measuring minute backtest baseline...")
    minute_time = measure_backtest_time(run_minute_backtest_regression)
    baselines["minute_backtest"] = {"decimal_rust": minute_time}
    logger.info(f"Minute backtest baseline: {minute_time:.2f}s")

    # Save baselines
    save_baselines(baselines)

    logger.info(f"Baselines saved to {BASELINE_FILE}")
    logger.info("Baselines:")
    logger.info(json.dumps(baselines, indent=2))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
