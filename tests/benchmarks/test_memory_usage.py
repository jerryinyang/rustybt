"""Memory usage benchmarking for RustyBT.

This module implements AC9 of Story 7.5: Memory benchmarks included.

Measures peak memory usage and allocation rates for backtest scenarios.

Run with: pytest tests/benchmarks/test_memory_usage.py -v
Note: Requires memory_profiler package
"""

import logging
from pathlib import Path

import pytest

try:
    from memory_profiler import memory_usage

    MEMORY_PROFILER_AVAILABLE = True
except ImportError:
    MEMORY_PROFILER_AVAILABLE = False
    memory_usage = None

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Paths
BENCHMARK_DIR = Path(__file__).parent
DATA_DIR = BENCHMARK_DIR / "data"


# ============================================================================
# Memory Measurement Utilities
# ============================================================================


def measure_memory(func, *args, **kwargs) -> dict[str, float]:
    """Measure memory usage of a function.

    Args:
        func: Function to measure
        *args: Positional arguments for function
        **kwargs: Keyword arguments for function

    Returns:
        Dict with memory statistics (MB)
    """
    if not MEMORY_PROFILER_AVAILABLE:
        pytest.skip("memory_profiler not installed")

    # Measure memory usage (samples every 0.1 seconds)
    mem_usage = memory_usage(
        (func, args, kwargs),
        interval=0.1,
        timeout=None,
        max_usage=True,
        retval=True,
        include_children=False,
    )

    # memory_usage returns (max_memory, return_value) when max_usage=True
    if isinstance(mem_usage, tuple):
        max_memory, return_value = mem_usage
        mem_stats = {
            "peak_mb": max_memory,
            "result": return_value,
        }
    else:
        # Fallback if format changes
        mem_stats = {
            "peak_mb": max(mem_usage) if isinstance(mem_usage, list) else mem_usage,
            "result": None,
        }

    return mem_stats


# ============================================================================
# Memory Benchmarks for Key Scenarios
# ============================================================================


@pytest.mark.memory
@pytest.mark.skipif(not MEMORY_PROFILER_AVAILABLE, reason="memory_profiler not installed")
def test_memory_daily_simple_10_assets():
    """Measure memory usage for daily simple strategy, 10 assets."""
    # Import strategies
    from .strategies.simple_sma_crossover import create_handle_data_fn, create_initialize_fn
    from .test_backtest_performance import fixture_exists, run_backtest_benchmark

    if not fixture_exists("daily_10_assets.parquet"):
        pytest.skip("Fixture not generated")

    initialize_fn = create_initialize_fn(n_assets=10)
    handle_data_fn = create_handle_data_fn()

    logger.info("Measuring memory for daily simple 10 assets...")

    mem_stats = measure_memory(
        run_backtest_benchmark,
        initialize_fn=initialize_fn,
        handle_data_fn=handle_data_fn,
        fixture_filename="daily_10_assets.parquet",
        data_frequency="daily",
    )

    peak_mb = mem_stats["peak_mb"]
    logger.info(f"Peak memory usage: {peak_mb:.2f} MB")

    # Sanity check: should be reasonable
    assert peak_mb > 0
    assert peak_mb < 2000, f"Memory usage too high: {peak_mb:.2f} MB"


@pytest.mark.memory
@pytest.mark.skipif(not MEMORY_PROFILER_AVAILABLE, reason="memory_profiler not installed")
def test_memory_daily_simple_50_assets():
    """Measure memory usage for daily simple strategy, 50 assets."""
    from .strategies.simple_sma_crossover import create_handle_data_fn, create_initialize_fn
    from .test_backtest_performance import fixture_exists, run_backtest_benchmark

    if not fixture_exists("daily_50_assets.parquet"):
        pytest.skip("Fixture not generated")

    initialize_fn = create_initialize_fn(n_assets=50)
    handle_data_fn = create_handle_data_fn()

    logger.info("Measuring memory for daily simple 50 assets...")

    mem_stats = measure_memory(
        run_backtest_benchmark,
        initialize_fn=initialize_fn,
        handle_data_fn=handle_data_fn,
        fixture_filename="daily_50_assets.parquet",
        data_frequency="daily",
    )

    peak_mb = mem_stats["peak_mb"]
    logger.info(f"Peak memory usage: {peak_mb:.2f} MB")

    assert peak_mb > 0
    assert peak_mb < 3000, f"Memory usage too high: {peak_mb:.2f} MB"


@pytest.mark.memory
@pytest.mark.skipif(not MEMORY_PROFILER_AVAILABLE, reason="memory_profiler not installed")
def test_memory_hourly_medium_50_assets():
    """Measure memory usage for hourly medium strategy, 50 assets."""
    from .strategies.momentum_strategy import create_handle_data_fn, create_initialize_fn
    from .test_backtest_performance import fixture_exists, run_backtest_benchmark

    if not fixture_exists("hourly_50_assets.parquet"):
        pytest.skip("Fixture not generated")

    initialize_fn = create_initialize_fn(n_assets=50)
    handle_data_fn = create_handle_data_fn()

    logger.info("Measuring memory for hourly medium 50 assets...")

    mem_stats = measure_memory(
        run_backtest_benchmark,
        initialize_fn=initialize_fn,
        handle_data_fn=handle_data_fn,
        fixture_filename="hourly_50_assets.parquet",
        data_frequency="minute",
    )

    peak_mb = mem_stats["peak_mb"]
    logger.info(f"Peak memory usage: {peak_mb:.2f} MB")

    assert peak_mb > 0
    assert peak_mb < 4000, f"Memory usage too high: {peak_mb:.2f} MB"


@pytest.mark.memory
@pytest.mark.slow
@pytest.mark.skipif(not MEMORY_PROFILER_AVAILABLE, reason="memory_profiler not installed")
def test_memory_minute_simple_10_assets():
    """Measure memory usage for minute simple strategy, 10 assets."""
    from .strategies.simple_sma_crossover import create_handle_data_fn, create_initialize_fn
    from .test_backtest_performance import fixture_exists, run_backtest_benchmark

    if not fixture_exists("minute_10_assets.parquet"):
        pytest.skip("Fixture not generated")

    initialize_fn = create_initialize_fn(n_assets=10)
    handle_data_fn = create_handle_data_fn()

    logger.info("Measuring memory for minute simple 10 assets...")

    mem_stats = measure_memory(
        run_backtest_benchmark,
        initialize_fn=initialize_fn,
        handle_data_fn=handle_data_fn,
        fixture_filename="minute_10_assets.parquet",
        data_frequency="minute",
    )

    peak_mb = mem_stats["peak_mb"]
    logger.info(f"Peak memory usage: {peak_mb:.2f} MB")

    assert peak_mb > 0
    assert peak_mb < 3000, f"Memory usage too high: {peak_mb:.2f} MB"


@pytest.mark.memory
@pytest.mark.slow
@pytest.mark.skipif(not MEMORY_PROFILER_AVAILABLE, reason="memory_profiler not installed")
def test_memory_daily_complex_100_assets():
    """Measure memory usage for daily complex strategy, 100 assets."""
    from .strategies.multi_indicator_strategy import create_handle_data_fn, create_initialize_fn
    from .test_backtest_performance import fixture_exists, run_backtest_benchmark

    if not fixture_exists("daily_100_assets.parquet"):
        pytest.skip("Fixture not generated")

    initialize_fn = create_initialize_fn(n_assets=100)
    handle_data_fn = create_handle_data_fn()

    logger.info("Measuring memory for daily complex 100 assets...")

    mem_stats = measure_memory(
        run_backtest_benchmark,
        initialize_fn=initialize_fn,
        handle_data_fn=handle_data_fn,
        fixture_filename="daily_100_assets.parquet",
        data_frequency="daily",
    )

    peak_mb = mem_stats["peak_mb"]
    logger.info(f"Peak memory usage: {peak_mb:.2f} MB")

    assert peak_mb > 0
    assert peak_mb < 5000, f"Memory usage too high: {peak_mb:.2f} MB"


# ============================================================================
# Memory Scaling Analysis
# ============================================================================


@pytest.mark.memory
@pytest.mark.skipif(not MEMORY_PROFILER_AVAILABLE, reason="memory_profiler not installed")
def test_memory_scaling_by_portfolio_size():
    """Analyze memory scaling with portfolio size."""
    from .strategies.simple_sma_crossover import create_handle_data_fn, create_initialize_fn
    from .test_backtest_performance import fixture_exists, run_backtest_benchmark

    sizes = [10, 50, 100]
    results = []

    for size in sizes:
        fixture = f"daily_{size}_assets.parquet"
        if not fixture_exists(fixture):
            logger.warning(f"Skipping {fixture} - not generated")
            continue

        initialize_fn = create_initialize_fn(n_assets=size)
        handle_data_fn = create_handle_data_fn()

        logger.info(f"Measuring memory for {size} assets...")

        mem_stats = measure_memory(
            run_backtest_benchmark,
            initialize_fn=initialize_fn,
            handle_data_fn=handle_data_fn,
            fixture_filename=fixture,
            data_frequency="daily",
        )

        results.append(
            {
                "size": size,
                "peak_mb": mem_stats["peak_mb"],
            }
        )

        logger.info(f"  {size} assets: {mem_stats['peak_mb']:.2f} MB")

    # Verify we have at least some results
    assert len(results) > 0, "No fixtures available for memory scaling test"

    # Log summary
    logger.info("\nMemory Scaling Summary:")
    for result in results:
        logger.info(f"  {result['size']} assets: {result['peak_mb']:.2f} MB")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "memory"])
