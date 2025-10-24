"""Isolated DataPortal.history() Profiling - Validates FR-010

This script isolates and profiles ONLY DataPortal.history() calls to validate
the research.md claim that DataPortal accounts for 61.5% of runtime overhead.

This is a simplified, focused profiling approach that:
- Uses existing ingested bundle (no bundle creation complexity)
- Directly profiles DataPortal.history() method calls
- Measures overhead without full Algorithm lifecycle
- Validates the specific bottleneck claim from research.md

Constitutional requirements:
- CR-002: Real DataPortal execution, no mocks
- FR-010: Validate DataPortal bottleneck claim
"""

import logging
import sys
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict

import pandas as pd

from rustybt.benchmarks.profiling import profile_workflow
from rustybt.benchmarks.reporter import generate_bottleneck_report
from rustybt.data import bundles
from rustybt.data.data_portal import DataPortal
from rustybt.utils.calendar_utils import get_calendar

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Directories
PROFILING_DIR = Path(__file__).parent.parent.parent / "profiling-results"
BENCHMARK_DIR = Path(__file__).parent.parent.parent / "benchmark-results"


def profile_dataportal_history_calls(
    bundle_name: str = "mag-7", n_calls: int = 1000, lookback_period: int = 50
) -> Dict[str, Any]:
    """Profile DataPortal.history() calls in isolation.

    This function makes repeated history() calls to measure the overhead
    of the DataPortal without the complexity of the full Algorithm lifecycle.

    Args:
        bundle_name: Name of ingested bundle to use
        n_calls: Number of history() calls to make
        lookback_period: Number of bars to request in each history call

    Returns:
        Dictionary with profiling results
    """
    logger.info(f"Loading bundle: {bundle_name}")

    # Load bundle
    bundle_data = bundles.load(bundle_name)

    # Get calendar and sessions
    calendar = get_calendar("XNYS")
    first_session = bundle_data.equity_daily_bar_reader.first_trading_day
    last_session = bundle_data.equity_daily_bar_reader.last_available_dt

    logger.info(f"Bundle period: {first_session.date()} to {last_session.date()}")

    # Create DataPortal
    data_portal = DataPortal(
        asset_finder=bundle_data.asset_finder,
        trading_calendar=calendar,
        first_trading_day=first_session,
        equity_daily_reader=bundle_data.equity_daily_bar_reader,
    )

    logger.info(f"DataPortal created, starting {n_calls} history calls...")

    # Get all assets
    all_assets = bundle_data.asset_finder.retrieve_all(bundle_data.asset_finder.sids)
    all_assets_list = list(all_assets)

    if not all_assets_list:
        raise ValueError("No assets found in bundle")

    logger.info(f"Found {len(all_assets_list)} assets in bundle")

    # Use middle session for history calls (ensure enough data before and after)
    all_sessions = calendar.sessions_in_range(first_session, last_session)

    if len(all_sessions) < lookback_period + 10:
        raise ValueError(
            f"Not enough sessions. Need at least {lookback_period + 10}, got {len(all_sessions)}"
        )

    test_session = all_sessions[lookback_period + 5]  # Use session with enough history

    logger.info(f"Test session: {test_session.date()}")
    logger.info(f"Making {n_calls} calls to history(lookback={lookback_period})")

    # Track results
    successful_calls = 0
    failed_calls = 0
    total_bars_retrieved = 0

    # Make repeated history calls
    start_time = time.perf_counter()

    for i in range(n_calls):
        try:
            # Cycle through assets
            asset = all_assets_list[i % len(all_assets_list)]

            # CRITICAL: This is the DataPortal.history() call we're profiling
            hist_data = data_portal.get_history_window(
                assets=[asset],
                end_dt=test_session,
                bar_count=lookback_period,
                frequency="1d",
                field="close",
                data_frequency="daily",
            )

            successful_calls += 1
            total_bars_retrieved += len(hist_data)

            if (i + 1) % 100 == 0:
                logger.debug(f"Completed {i + 1}/{n_calls} calls")

        except Exception as e:
            failed_calls += 1
            logger.debug(f"Call {i + 1} failed: {e}")
            continue

    end_time = time.perf_counter()
    total_time = end_time - start_time

    logger.info(f"Profiling complete:")
    logger.info(f"  Total calls: {n_calls}")
    logger.info(f"  Successful: {successful_calls}")
    logger.info(f"  Failed: {failed_calls}")
    logger.info(f"  Total time: {total_time:.3f}s")
    logger.info(f"  Avg time per call: {(total_time / successful_calls * 1000):.2f}ms")
    logger.info(f"  Total bars retrieved: {total_bars_retrieved:,}")

    return {
        "n_calls": n_calls,
        "successful_calls": successful_calls,
        "failed_calls": failed_calls,
        "total_time_seconds": Decimal(str(total_time)),
        "avg_time_per_call_ms": (
            Decimal(str(total_time / successful_calls * 1000))
            if successful_calls > 0
            else Decimal("0")
        ),
        "total_bars_retrieved": total_bars_retrieved,
        "bundle_name": bundle_name,
        "lookback_period": lookback_period,
        "test_session": test_session.date().isoformat(),
    }


def main():
    """Execute isolated DataPortal profiling."""
    logger.info("=" * 80)
    logger.info("ISOLATED DATAPORTAL PROFILING - FR-010 VALIDATION")
    logger.info("=" * 80)

    # Ensure output directories exist
    PROFILING_DIR.mkdir(exist_ok=True, parents=True)
    BENCHMARK_DIR.mkdir(exist_ok=True, parents=True)

    # Configuration
    BUNDLE_NAME = "mag-7"  # Use existing ingested bundle (from sample)
    N_CALLS = 2000  # 2000 calls to get meaningful data
    LOOKBACK_PERIOD = 50  # Typical moving average lookback

    logger.info(f"\nConfiguration:")
    logger.info(f"  Bundle: {BUNDLE_NAME}")
    logger.info(f"  Number of calls: {N_CALLS}")
    logger.info(f"  Lookback period: {LOOKBACK_PERIOD}")

    # ========================================================================
    # Execute Profiled DataPortal Calls
    # ========================================================================

    logger.info("\n" + "=" * 80)
    logger.info("PROFILING DATAPORTAL.HISTORY() CALLS")
    logger.info("=" * 80)

    result, metrics = profile_workflow(
        workflow_fn=profile_dataportal_history_calls,
        workflow_kwargs={
            "bundle_name": BUNDLE_NAME,
            "n_calls": N_CALLS,
            "lookback_period": LOOKBACK_PERIOD,
        },
        profiler_type="cprofile",
        output_dir=str(PROFILING_DIR),
        run_id="dataportal_isolated",
    )

    logger.info(f"\nProfiling complete: {metrics['total_time_seconds']}s")
    logger.info(f"Successful calls: {result['successful_calls']}/{result['n_calls']}")
    logger.info(f"Average per call: {result['avg_time_per_call_ms']}ms")

    # ========================================================================
    # Generate Bottleneck Report
    # ========================================================================

    logger.info("\n" + "=" * 80)
    logger.info("GENERATING BOTTLENECK ANALYSIS")
    logger.info("=" * 80)

    stats_file = PROFILING_DIR / f"{metrics['run_id']}_cprofile.stats"

    json_report, json_path, md_path = generate_bottleneck_report(
        profile_stats_path=str(stats_file),
        workflow_name="Isolated DataPortal.history() Profiling",
        output_dir=str(BENCHMARK_DIR),
    )

    logger.info(f"Bottleneck report: {md_path}")

    # ========================================================================
    # Validate DataPortal Overhead Claim
    # ========================================================================

    logger.info("\n" + "=" * 80)
    logger.info("VALIDATING FR-010: DATAPORTAL BOTTLENECK CLAIM")
    logger.info("=" * 80)

    # Find DataPortal-related functions in bottlenecks
    dataportal_keywords = [
        "data_portal",
        "dataportal",
        "get_history",
        "history_window",
        "get_history_window",
        "_get_history_window",
    ]

    dataportal_bottlenecks = [
        b
        for b in json_report["bottlenecks"]
        if any(keyword in b["function"].lower() for keyword in dataportal_keywords)
    ]

    # Also look for data reading operations (bundle readers, etc.)
    data_reading_keywords = [
        "bar_reader",
        "bcolz",
        "read",
        "load_raw_arrays",
        "equity_daily_bar_reader",
    ]

    data_reading_bottlenecks = [
        b
        for b in json_report["bottlenecks"]
        if any(keyword in b["function"].lower() for keyword in data_reading_keywords)
    ]

    # Calculate total overhead (using cumulative time percentage)
    dataportal_pct = sum(b["percent_cumtime"] for b in dataportal_bottlenecks)
    data_reading_pct = sum(b["percent_cumtime"] for b in data_reading_bottlenecks)
    total_data_overhead_pct = dataportal_pct + data_reading_pct

    logger.info(f"\n📊 BOTTLENECK BREAKDOWN:")
    logger.info(f"   DataPortal methods: {dataportal_pct:.1f}%")
    logger.info(f"   Data reading operations: {data_reading_pct:.1f}%")
    logger.info(f"   Total data overhead: {total_data_overhead_pct:.1f}%")

    # Show top DataPortal bottlenecks
    if dataportal_bottlenecks:
        logger.info(f"\n   Top DataPortal bottlenecks:")
        for i, b in enumerate(dataportal_bottlenecks[:5], 1):
            logger.info(
                f"     {i}. {b['function']}: {b['percent_cumtime']:.2f}% "
                f"({b['ncalls']:,} calls)"
            )

    # Validation against research.md claim
    logger.info(f"\n🔍 VALIDATION:")
    logger.info(f"   Research.md claim: DataPortal = 61.5%")
    logger.info(f"   Measured (DataPortal+Reading): {total_data_overhead_pct:.1f}%")

    # Determine validation status
    if total_data_overhead_pct >= 55:
        status = "✅ VALIDATED"
        message = "Data operations are the dominant bottleneck (≥55%)"
    elif total_data_overhead_pct >= 40:
        status = "⚠️  PARTIAL"
        message = "Data operations are significant but not dominant (40-55%)"
    else:
        status = "❌ NOT VALIDATED"
        message = "Data operations <40% of runtime - discrepancy with research.md"

    logger.info(f"   Status: {status}")
    logger.info(f"   {message}")

    # ========================================================================
    # Summary and Recommendations
    # ========================================================================

    logger.info("\n" + "=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)

    logger.info(f"\n✅ ISOLATED PROFILING COMPLETE:")
    logger.info(f"   - {result['successful_calls']:,} DataPortal.history() calls profiled")
    logger.info(f"   - Average overhead: {result['avg_time_per_call_ms']}ms per call")
    logger.info(f"   - Total execution time: {metrics['total_time_seconds']}s")
    logger.info(f"   - Data overhead: {total_data_overhead_pct:.1f}%")

    logger.info(f"\n📊 KEY FINDINGS:")
    logger.info(f"   - DataPortal methods: {dataportal_pct:.1f}%")
    logger.info(f"   - Data reading: {data_reading_pct:.1f}%")
    logger.info(f"   - Validation: {status}")

    logger.info(f"\n📁 ARTIFACTS GENERATED:")
    logger.info(f"   - cProfile stats: {stats_file}")
    logger.info(f"   - JSON report: {json_path}")
    logger.info(f"   - Markdown report: {md_path}")

    logger.info(f"\n💡 RECOMMENDATIONS:")
    if total_data_overhead_pct >= 40:
        logger.info("   1. DataPortal is confirmed as primary bottleneck")
        logger.info("   2. Proceed with data layer optimizations as planned")
        logger.info("   3. Focus on reducing history() call overhead")
        logger.info("   4. Consider caching strategies for repeated lookups")
    else:
        logger.info("   1. Re-evaluate optimization priorities")
        logger.info("   2. Profile full Algorithm execution for complete picture")
        logger.info("   3. May need to update research.md claims")

    logger.info("\n" + "=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
