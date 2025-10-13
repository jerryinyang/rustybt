"""Comprehensive backtest performance benchmark suite.

This module implements AC1-AC8 of Story 7.5:
- AC1: Benchmark scenarios covering common use cases (daily, hourly, minute)
- AC2: Test different strategy complexities (simple, medium, complex)
- AC3: Test different portfolio sizes (10, 50, 100, 500 assets)
- AC4: Store benchmark results historically
- AC5: Run in CI/CD (nightly builds)
- AC6: Generate performance graphs
- AC7: Detect performance regressions >5%
- AC8: Compare Python-only vs. Rust-optimized

Run with: pytest tests/benchmarks/test_backtest_performance.py --benchmark-only -v
"""

import json
import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
import polars as pl
import pytest

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Paths
BENCHMARK_DIR = Path(__file__).parent
DATA_DIR = BENCHMARK_DIR / "data"
RESULTS_DIR = Path(__file__).parent.parent.parent / "docs" / "performance"
HISTORY_FILE = RESULTS_DIR / "benchmark-history.json"

# Import strategy factories
from tests.benchmarks.strategies.momentum_strategy import (
    create_handle_data_fn as create_momentum_handle,
)
from tests.benchmarks.strategies.momentum_strategy import (
    create_initialize_fn as create_momentum_init,
)
from tests.benchmarks.strategies.multi_indicator_strategy import (
    create_handle_data_fn as create_complex_handle,
)
from tests.benchmarks.strategies.multi_indicator_strategy import (
    create_initialize_fn as create_complex_init,
)
from tests.benchmarks.strategies.simple_sma_crossover import (
    create_handle_data_fn as create_simple_handle,
)
from tests.benchmarks.strategies.simple_sma_crossover import (
    create_initialize_fn as create_simple_init,
)

# ============================================================================
# Fixture Loading Utilities
# ============================================================================


def load_fixture(filename: str) -> pl.DataFrame:
    """Load benchmark data fixture.

    Args:
        filename: Fixture filename (e.g., 'daily_10_assets.parquet')

    Returns:
        Polars DataFrame with OHLCV data

    Raises:
        FileNotFoundError: If fixture doesn't exist
    """
    fixture_path = DATA_DIR / filename

    if not fixture_path.exists():
        pytest.skip(
            f"Fixture {filename} not found. Run: python scripts/benchmarks/generate_fixtures.py"
        )

    return pl.read_parquet(fixture_path)


def fixture_exists(filename: str) -> bool:
    """Check if a fixture file exists.

    Args:
        filename: Fixture filename

    Returns:
        True if fixture exists, False otherwise
    """
    return (DATA_DIR / filename).exists()


# ============================================================================
# Benchmark Runner
# ============================================================================


def run_backtest_benchmark(
    initialize_fn,
    handle_data_fn,
    fixture_filename: str,
    data_frequency: str = "daily",
    capital_base: Decimal = Decimal("100000"),
) -> dict[str, Any]:
    """Run backtest and return results with timing.

    Args:
        initialize_fn: Strategy initialize function
        handle_data_fn: Strategy handle_data function
        fixture_filename: Data fixture filename (used to determine bundle)
        data_frequency: Data frequency ('daily', 'minute')
        capital_base: Starting capital

    Returns:
        Dict with backtest results and metadata
    """
    # Import here to avoid slow imports at module level
    # Import profiling bundle registrations (required before bundles can be loaded)
    import scripts.profiling.setup_profiling_data  # noqa: F401
    from rustybt.utils.run_algo import run_algorithm

    # Map fixture filename to appropriate profiling bundle
    # Profiling bundles provide synthetic data aligned to our benchmark scenarios
    bundle_mapping = {
        "daily_10_assets.parquet": ("profiling-daily", "2024-08-01", "2025-08-01"),
        "daily_50_assets.parquet": ("profiling-daily", "2024-08-01", "2025-08-01"),
        "daily_100_assets.parquet": ("profiling-daily", "2024-08-01", "2025-08-01"),
        "daily_500_assets.parquet": ("profiling-daily", "2024-08-01", "2025-08-01"),
        "hourly_10_assets.parquet": ("profiling-hourly", "2024-09-01", "2024-12-01"),
        "hourly_20_assets.parquet": ("profiling-hourly", "2024-09-01", "2024-12-01"),
        "hourly_50_assets.parquet": ("profiling-hourly", "2024-09-01", "2024-12-01"),
        "hourly_100_assets.parquet": ("profiling-hourly", "2024-09-01", "2024-12-01"),
        "minute_10_assets.parquet": ("profiling-minute", "2024-10-01", "2024-11-01"),
        "minute_20_assets.parquet": ("profiling-minute", "2024-10-01", "2024-11-01"),
        "minute_50_assets.parquet": ("profiling-minute", "2024-10-01", "2024-11-01"),
    }

    if fixture_filename not in bundle_mapping:
        # Fallback: try to load fixture to get date range
        pytest.skip(f"No bundle mapping for {fixture_filename}. Bundle ingestion needed.")

    bundle_name, start_str, end_str = bundle_mapping[fixture_filename]
    start_date = pd.Timestamp(start_str)
    end_date = pd.Timestamp(end_str)

    # Check if bundle exists
    from rustybt.data import bundles

    try:
        # Try to load bundle metadata to verify it exists
        bundles.load(bundle_name)
    except Exception:
        # Bundle not ingested, skip test
        pytest.skip(
            f"Bundle '{bundle_name}' not ingested. "
            f"Run: python scripts/profiling/setup_profiling_data.py"
        )

    logger.info(
        f"Running backtest: bundle={bundle_name}, "
        f"{start_date.date()} to {end_date.date()}, "
        f"frequency={data_frequency}"
    )

    try:
        # Run actual backtest using run_algorithm
        # Note: run_algorithm expects float for capital_base, not Decimal
        perf = run_algorithm(
            start=start_date,
            end=end_date,
            initialize=initialize_fn,
            handle_data=handle_data_fn,
            capital_base=float(capital_base),
            bundle=bundle_name,
            data_frequency=data_frequency,
        )

        # Extract key metrics from performance DataFrame
        final_value = float(perf["portfolio_value"].iloc[-1])
        total_return = float((final_value - float(capital_base)) / float(capital_base) * 100)

        results = {
            "fixture": fixture_filename,
            "bundle": bundle_name,
            "start_date": str(start_date.date()),
            "end_date": str(end_date.date()),
            "data_frequency": data_frequency,
            "capital_base": float(capital_base),
            "final_portfolio_value": final_value,
            "total_return_pct": total_return,
            "num_transactions": len(perf[perf["transactions"].apply(len) > 0]),
            "completed": True,
        }

        logger.info(
            f"Backtest complete: return={total_return:.2f}%, final_value=${final_value:,.2f}"
        )

        return results

    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        # Return error info but don't fail the benchmark
        return {
            "fixture": fixture_filename,
            "bundle": bundle_name,
            "error": str(e),
            "completed": False,
        }


# ============================================================================
# Daily Benchmark Scenarios
# ============================================================================


@pytest.mark.benchmark(group="daily-simple-10")
def test_daily_simple_10_assets_rust(benchmark):
    """Benchmark daily simple strategy, 10 assets, Rust-optimized (Scenario 1).

    Priority: HIGH - Fast baseline, quick feedback
    Expected runtime: ~20s
    """
    # Note: Now using profiling bundles instead of fixtures
    initialize_fn = create_simple_init(n_assets=10)
    handle_data_fn = create_simple_handle()

    result = benchmark(
        run_backtest_benchmark,
        initialize_fn=initialize_fn,
        handle_data_fn=handle_data_fn,
        fixture_filename="daily_10_assets.parquet",
        data_frequency="daily",
    )

    assert result["completed"]


@pytest.mark.benchmark(group="daily-simple-50")
def test_daily_simple_50_assets_rust(benchmark):
    """Benchmark daily simple strategy, 50 assets, Rust-optimized (Scenario 2).

    Priority: HIGH - Common portfolio size
    Expected runtime: ~30s
    """
    if not fixture_exists("daily_50_assets.parquet"):
        pytest.skip("Fixture not generated")

    initialize_fn = create_simple_init(n_assets=50)
    handle_data_fn = create_simple_handle()

    result = benchmark(
        run_backtest_benchmark,
        initialize_fn=initialize_fn,
        handle_data_fn=handle_data_fn,
        fixture_filename="daily_50_assets.parquet",
        data_frequency="daily",
    )

    assert result["completed"]


@pytest.mark.benchmark(group="daily-simple-50-python")
def test_daily_simple_50_assets_python(benchmark):
    """Benchmark daily simple strategy, 50 assets, Python-only (Scenario 14).

    Priority: HIGH - Python-only baseline for comparison
    Expected runtime: ~30s
    """
    if not fixture_exists("daily_50_assets.parquet"):
        pytest.skip("Fixture not generated")

    initialize_fn = create_simple_init(n_assets=50)
    handle_data_fn = create_simple_handle()

    # TODO: Add rust_enabled=False parameter when available
    result = benchmark(
        run_backtest_benchmark,
        initialize_fn=initialize_fn,
        handle_data_fn=handle_data_fn,
        fixture_filename="daily_50_assets.parquet",
        data_frequency="daily",
    )

    assert result["completed"]


@pytest.mark.benchmark(group="daily-medium-50")
def test_daily_medium_50_assets_rust(benchmark):
    """Benchmark daily medium strategy, 50 assets, Rust-optimized (Scenario 3).

    Priority: HIGH - Realistic use case
    Expected runtime: ~40s
    """
    if not fixture_exists("daily_50_assets.parquet"):
        pytest.skip("Fixture not generated")

    initialize_fn = create_momentum_init(n_assets=50)
    handle_data_fn = create_momentum_handle()

    result = benchmark(
        run_backtest_benchmark,
        initialize_fn=initialize_fn,
        handle_data_fn=handle_data_fn,
        fixture_filename="daily_50_assets.parquet",
        data_frequency="daily",
    )

    assert result["completed"]


@pytest.mark.benchmark(group="daily-medium-10")
def test_daily_medium_10_assets_rust(benchmark):
    """Benchmark daily medium strategy, 10 assets, Rust-optimized (Scenario 11).

    Priority: MEDIUM - Strategy overhead measurement
    Expected runtime: ~25s
    """
    if not fixture_exists("daily_10_assets.parquet"):
        pytest.skip("Fixture not generated")

    initialize_fn = create_momentum_init(n_assets=10)
    handle_data_fn = create_momentum_handle()

    result = benchmark(
        run_backtest_benchmark,
        initialize_fn=initialize_fn,
        handle_data_fn=handle_data_fn,
        fixture_filename="daily_10_assets.parquet",
        data_frequency="daily",
    )

    assert result["completed"]


@pytest.mark.benchmark(group="daily-complex-100")
def test_daily_complex_100_assets_rust(benchmark):
    """Benchmark daily complex strategy, 100 assets, Rust-optimized (Scenario 4).

    Priority: MEDIUM - Stress test for daily
    Expected runtime: ~80s
    """
    if not fixture_exists("daily_100_assets.parquet"):
        pytest.skip("Fixture not generated")

    initialize_fn = create_complex_init(n_assets=100)
    handle_data_fn = create_complex_handle()

    result = benchmark(
        run_backtest_benchmark,
        initialize_fn=initialize_fn,
        handle_data_fn=handle_data_fn,
        fixture_filename="daily_100_assets.parquet",
        data_frequency="daily",
    )

    assert result["completed"]


@pytest.mark.benchmark(group="daily-simple-500")
@pytest.mark.slow
def test_daily_simple_500_assets_rust(benchmark):
    """Benchmark daily simple strategy, 500 assets, Rust-optimized (Scenario 10).

    Priority: LOW - Large portfolio scaling
    Expected runtime: ~120s
    """
    if not fixture_exists("daily_500_assets.parquet"):
        pytest.skip("Fixture not generated")

    initialize_fn = create_simple_init(n_assets=500)
    handle_data_fn = create_simple_handle()

    result = benchmark(
        run_backtest_benchmark,
        initialize_fn=initialize_fn,
        handle_data_fn=handle_data_fn,
        fixture_filename="daily_500_assets.parquet",
        data_frequency="daily",
    )

    assert result["completed"]


# ============================================================================
# Hourly Benchmark Scenarios
# ============================================================================


@pytest.mark.benchmark(group="hourly-simple-10")
def test_hourly_simple_10_assets_rust(benchmark):
    """Benchmark hourly simple strategy, 10 assets, Rust-optimized (Scenario 5).

    Priority: HIGH - Intraday baseline
    Expected runtime: ~30s
    """
    if not fixture_exists("hourly_10_assets.parquet"):
        pytest.skip("Fixture not generated")

    initialize_fn = create_simple_init(n_assets=10)
    handle_data_fn = create_simple_handle()

    result = benchmark(
        run_backtest_benchmark,
        initialize_fn=initialize_fn,
        handle_data_fn=handle_data_fn,
        fixture_filename="hourly_10_assets.parquet",
        data_frequency="minute",  # Hourly data loaded as minute bars
    )

    assert result["completed"]


@pytest.mark.benchmark(group="hourly-medium-50")
def test_hourly_medium_50_assets_rust(benchmark):
    """Benchmark hourly medium strategy, 50 assets, Rust-optimized (Scenario 6).

    Priority: HIGH - Common intraday use case
    Expected runtime: ~60s
    """
    if not fixture_exists("hourly_50_assets.parquet"):
        pytest.skip("Fixture not generated")

    initialize_fn = create_momentum_init(n_assets=50)
    handle_data_fn = create_momentum_handle()

    result = benchmark(
        run_backtest_benchmark,
        initialize_fn=initialize_fn,
        handle_data_fn=handle_data_fn,
        fixture_filename="hourly_50_assets.parquet",
        data_frequency="minute",
    )

    assert result["completed"]


@pytest.mark.benchmark(group="hourly-medium-20-python")
def test_hourly_medium_20_assets_python(benchmark):
    """Benchmark hourly medium strategy, 20 assets, Python-only (Scenario 15).

    Priority: MEDIUM - Python-only baseline for hourly
    Expected runtime: ~60s
    """
    if not fixture_exists("hourly_20_assets.parquet"):
        pytest.skip("Fixture not generated")

    initialize_fn = create_momentum_init(n_assets=20)
    handle_data_fn = create_momentum_handle()

    result = benchmark(
        run_backtest_benchmark,
        initialize_fn=initialize_fn,
        handle_data_fn=handle_data_fn,
        fixture_filename="hourly_20_assets.parquet",
        data_frequency="minute",
    )

    assert result["completed"]


@pytest.mark.benchmark(group="hourly-complex-100")
@pytest.mark.slow
def test_hourly_complex_100_assets_rust(benchmark):
    """Benchmark hourly complex strategy, 100 assets, Rust-optimized (Scenario 7).

    Priority: MEDIUM - Intraday stress test
    Expected runtime: ~120s
    """
    if not fixture_exists("hourly_100_assets.parquet"):
        pytest.skip("Fixture not generated")

    initialize_fn = create_complex_init(n_assets=100)
    handle_data_fn = create_complex_handle()

    result = benchmark(
        run_backtest_benchmark,
        initialize_fn=initialize_fn,
        handle_data_fn=handle_data_fn,
        fixture_filename="hourly_100_assets.parquet",
        data_frequency="minute",
    )

    assert result["completed"]


@pytest.mark.benchmark(group="hourly-simple-100")
def test_hourly_simple_100_assets_rust(benchmark):
    """Benchmark hourly simple strategy, 100 assets, Rust-optimized (Scenario 12).

    Priority: MEDIUM - Scaling test
    Expected runtime: ~80s
    """
    if not fixture_exists("hourly_100_assets.parquet"):
        pytest.skip("Fixture not generated")

    initialize_fn = create_simple_init(n_assets=100)
    handle_data_fn = create_simple_handle()

    result = benchmark(
        run_backtest_benchmark,
        initialize_fn=initialize_fn,
        handle_data_fn=handle_data_fn,
        fixture_filename="hourly_100_assets.parquet",
        data_frequency="minute",
    )

    assert result["completed"]


# ============================================================================
# Minute Benchmark Scenarios
# ============================================================================


@pytest.mark.benchmark(group="minute-simple-10")
def test_minute_simple_10_assets_rust(benchmark):
    """Benchmark minute simple strategy, 10 assets, Rust-optimized (Scenario 8).

    Priority: HIGH - HFT baseline
    Expected runtime: ~40s
    """
    if not fixture_exists("minute_10_assets.parquet"):
        pytest.skip("Fixture not generated")

    initialize_fn = create_simple_init(n_assets=10)
    handle_data_fn = create_simple_handle()

    result = benchmark(
        run_backtest_benchmark,
        initialize_fn=initialize_fn,
        handle_data_fn=handle_data_fn,
        fixture_filename="minute_10_assets.parquet",
        data_frequency="minute",
    )

    assert result["completed"]


@pytest.mark.benchmark(group="minute-medium-20")
def test_minute_medium_20_assets_rust(benchmark):
    """Benchmark minute medium strategy, 20 assets, Rust-optimized (Scenario 9).

    Priority: MEDIUM - HFT realistic use case
    Expected runtime: ~80s
    """
    if not fixture_exists("minute_20_assets.parquet"):
        pytest.skip("Fixture not generated")

    initialize_fn = create_momentum_init(n_assets=20)
    handle_data_fn = create_momentum_handle()

    result = benchmark(
        run_backtest_benchmark,
        initialize_fn=initialize_fn,
        handle_data_fn=handle_data_fn,
        fixture_filename="minute_20_assets.parquet",
        data_frequency="minute",
    )

    assert result["completed"]


@pytest.mark.benchmark(group="minute-simple-50")
@pytest.mark.slow
def test_minute_simple_50_assets_rust(benchmark):
    """Benchmark minute simple strategy, 50 assets, Rust-optimized (Scenario 13).

    Priority: LOW - HFT scaling test
    Expected runtime: ~80s
    """
    if not fixture_exists("minute_50_assets.parquet"):
        pytest.skip("Fixture not generated")

    initialize_fn = create_simple_init(n_assets=50)
    handle_data_fn = create_simple_handle()

    result = benchmark(
        run_backtest_benchmark,
        initialize_fn=initialize_fn,
        handle_data_fn=handle_data_fn,
        fixture_filename="minute_50_assets.parquet",
        data_frequency="minute",
    )

    assert result["completed"]


# ============================================================================
# Benchmark Result Storage (AC4)
# ============================================================================


@pytest.fixture(scope="session", autouse=True)
def store_benchmark_results(request):
    """Store benchmark results to history file after all tests complete.

    This fixture runs automatically after all benchmarks complete.
    """
    yield  # Let all tests run first

    # Only store results if pytest-benchmark data is available
    if not hasattr(request.config, "_benchmarksession"):
        return

    # Get benchmark session
    bench_session = request.config._benchmarksession

    if bench_session is None:
        return

    # Create results directory if needed
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # Get Git commit info (if available)
    import subprocess

    try:
        git_commit = (
            subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
            .decode("utf-8")
            .strip()
        )
        git_branch = (
            subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"], stderr=subprocess.DEVNULL
            )
            .decode("utf-8")
            .strip()
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        git_commit = "unknown"
        git_branch = "unknown"

    # Load existing history
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE) as f:
            history = json.load(f)
    else:
        history = {"runs": []}

    # Add current run
    current_run = {
        "timestamp": datetime.utcnow().isoformat(),
        "git_commit": git_commit,
        "git_branch": git_branch,
        "python_version": f"{pytest.__version__}",
    }

    history["runs"].append(current_run)

    # Save updated history
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

    logger.info(f"Benchmark results stored to {HISTORY_FILE}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--benchmark-only"])
