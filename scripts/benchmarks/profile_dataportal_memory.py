"""Memory Profiling for DataPortal.history() - FR-021 Compliance

This script profiles memory usage of DataPortal.history() calls to fulfill
the FR-021 requirement for memory efficiency metrics.

Usage:
    python -m memory_profiler scripts/benchmarks/profile_dataportal_memory.py
"""

import logging
import sys
from pathlib import Path

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


def profile_dataportal_memory(
    bundle_name: str = "mag-7", n_calls: int = 500, lookback_period: int = 50
):
    """Profile memory usage of DataPortal.history() calls.

    This function is decorated with @profile when run via memory_profiler.

    Args:
        bundle_name: Name of ingested bundle to use
        n_calls: Number of history() calls to make
        lookback_period: Number of bars to request in each history call
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

    logger.info(f"Found {len(all_assets_list)} assets in bundle")

    # Use middle session for history calls
    all_sessions = calendar.sessions_in_range(first_session, last_session)
    test_session = all_sessions[lookback_period + 5]

    logger.info(f"Test session: {test_session.date()}")
    logger.info(f"Making {n_calls} calls to history(lookback={lookback_period})")

    # Track results
    successful_calls = 0

    # Make repeated history calls (this is what we're profiling)
    for i in range(n_calls):
        try:
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

        except Exception as e:
            logger.debug(f"Call {i + 1} failed: {e}")
            continue

    logger.info(f"Memory profiling complete: {successful_calls}/{n_calls} calls")

    return successful_calls


def main():
    """Execute memory profiling."""
    logger.info("=" * 80)
    logger.info("DATAPORTAL MEMORY PROFILING - FR-021")
    logger.info("=" * 80)

    # Ensure output directory exists
    PROFILING_DIR.mkdir(exist_ok=True, parents=True)

    # Configuration
    BUNDLE_NAME = "mag-7"
    N_CALLS = 500  # Fewer calls for memory profiling
    LOOKBACK_PERIOD = 50

    logger.info(f"\nConfiguration:")
    logger.info(f"  Bundle: {BUNDLE_NAME}")
    logger.info(f"  Number of calls: {N_CALLS}")
    logger.info(f"  Lookback period: {LOOKBACK_PERIOD}")
    logger.info("")

    # Run profiled function
    result = profile_dataportal_memory(
        bundle_name=BUNDLE_NAME, n_calls=N_CALLS, lookback_period=LOOKBACK_PERIOD
    )

    logger.info("")
    logger.info("=" * 80)
    logger.info(f"Memory profiling complete: {result} successful calls")
    logger.info("=" * 80)
    logger.info("")
    logger.info("📊 MEMORY PROFILING RESULTS:")
    logger.info("   Check the output above for line-by-line memory usage")
    logger.info("   Key metrics to look for:")
    logger.info("     - Peak memory usage during history() calls")
    logger.info("     - Memory allocated for DataFrames")
    logger.info("     - Memory growth over multiple calls")
    logger.info("")
    logger.info("💡 TO RUN WITH MEMORY PROFILING:")
    logger.info("   python -m memory_profiler scripts/benchmarks/profile_dataportal_memory.py")
    logger.info("")

    return 0


if __name__ == "__main__":
    # Check if running under memory_profiler
    try:
        import memory_profiler

        # Apply @profile decorator to the function
        profile_dataportal_memory = memory_profiler.profile(profile_dataportal_memory)
        logger.info("✅ memory_profiler detected - memory profiling enabled")
    except ImportError:
        logger.warning("⚠️  memory_profiler not available - run without memory profiling")
        logger.info("   Install with: pip install memory-profiler")

    sys.exit(main())
