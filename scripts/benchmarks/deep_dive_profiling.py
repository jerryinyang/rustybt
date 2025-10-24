"""Deep-dive line-by-line profiling of bottleneck functions.

This script uses line_profiler to analyze the exact lines causing slowdowns
inside the identified bottleneck functions.
"""

import logging
from pathlib import Path

import numpy as np
import polars as pl

from rustybt.benchmarks.profiling import profile_workflow

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

PROFILING_DIR = Path(__file__).parent.parent.parent / "profiling-results"


# Import the bottleneck function
import sys

sys.path.insert(0, str(Path(__file__).parent))
from run_production_profiling import create_synthetic_price_data, simple_ma_crossover_backtest


def analyze_bottleneck_line_by_line():
    """Run line-by-line profiling on the bottleneck function."""

    logger.info("=" * 80)
    logger.info("DEEP-DIVE LINE-BY-LINE PROFILING")
    logger.info("=" * 80)
    logger.info("")
    logger.info("Profiling: simple_ma_crossover_backtest()")
    logger.info("This will show EXACTLY which lines are slow")
    logger.info("")

    # Create test data (smaller for faster analysis)
    data = create_synthetic_price_data(n_days=252, n_assets=10, seed=42)
    params = {"lookback_short": 10, "lookback_long": 30}

    # Define wrapper function to profile
    def run_single_backtest():
        return simple_ma_crossover_backtest(params, data)

    # Profile with line_profiler
    try:
        result, metrics = profile_workflow(
            workflow_fn=run_single_backtest,
            workflow_args=(),
            profiler_type="line_profiler",
            output_dir=str(PROFILING_DIR),
            run_id="bottleneck_line_analysis",
        )

        logger.info("✅ Line profiling complete!")
        logger.info(f"Report: {metrics['profile_output_path']}")
        logger.info("")

        # Read and display the line profiling results
        report_path = Path(metrics["profile_output_path"])
        report_content = report_path.read_text()

        logger.info("=" * 80)
        logger.info("LINE-BY-LINE PROFILING RESULTS")
        logger.info("=" * 80)
        logger.info(report_content)

        return report_content

    except ImportError:
        logger.error("❌ line_profiler not installed!")
        logger.error("Install with: pip install line_profiler")
        return None


if __name__ == "__main__":
    analyze_bottleneck_line_by_line()
