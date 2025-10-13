#!/usr/bin/env python
"""Compare profiling results before and after optimization.

This script compares two sets of profiling results to measure optimization impact.

Usage:
    python scripts/profiling/compare_profiles.py <before_dir> <after_dir>
    python scripts/profiling/compare_profiles.py \
        docs/performance/profiles/baseline/ docs/performance/profiles/post-rust/
"""

import argparse
import pstats
import sys
from pathlib import Path

import structlog

logger = structlog.get_logger()


def load_profile_stats(profile_file: Path) -> pstats.Stats:
    """Load cProfile stats from file.

    Args:
        profile_file: Path to .pstats file

    Returns:
        Loaded stats object

    Raises:
        FileNotFoundError: If profile file doesn't exist
    """
    if not profile_file.exists():
        raise FileNotFoundError(f"Profile file not found: {profile_file}")

    return pstats.Stats(str(profile_file))


def extract_top_functions(stats: pstats.Stats, n: int = 50) -> list[tuple[str, float, int, float]]:
    """Extract top N functions by cumulative time.

    Args:
        stats: Profile statistics
        n: Number of top functions to extract

    Returns:
        List of (function_name, cumtime, ncalls, percall) tuples
    """
    stats.sort_stats("cumulative")

    # Extract function stats
    func_stats = []
    for func, (_cc, nc, _tt, ct, _callers) in stats.stats.items():
        # Format function name
        filename, line, func_name = func
        full_name = f"{Path(filename).name}:{line}:{func_name}"

        # Calculate per-call time
        percall = ct / nc if nc > 0 else 0

        func_stats.append((full_name, ct, nc, percall))

    # Sort by cumulative time and return top N
    func_stats.sort(key=lambda x: x[1], reverse=True)
    return func_stats[:n]


def compare_function_stats(
    before_stats: list[tuple[str, float, int, float]],
    after_stats: list[tuple[str, float, int, float]],
) -> dict[str, dict[str, float]]:
    """Compare function statistics between before and after.

    Args:
        before_stats: Function stats before optimization
        after_stats: Function stats after optimization

    Returns:
        Dictionary mapping function names to change metrics
    """
    # Create lookups
    before_lookup = {
        name: (cumtime, ncalls, percall) for name, cumtime, ncalls, percall in before_stats
    }
    after_lookup = {
        name: (cumtime, ncalls, percall) for name, cumtime, ncalls, percall in after_stats
    }

    # Find all functions
    all_functions = set(before_lookup.keys()) | set(after_lookup.keys())

    comparisons = {}
    for func in all_functions:
        before_cumtime, before_ncalls, _before_percall = before_lookup.get(func, (0, 0, 0))
        after_cumtime, after_ncalls, _after_percall = after_lookup.get(func, (0, 0, 0))

        # Calculate deltas
        cumtime_delta = after_cumtime - before_cumtime
        cumtime_pct = (
            ((after_cumtime - before_cumtime) / before_cumtime * 100) if before_cumtime > 0 else 0
        )

        comparisons[func] = {
            "before_cumtime": before_cumtime,
            "after_cumtime": after_cumtime,
            "cumtime_delta": cumtime_delta,
            "cumtime_pct": cumtime_pct,
            "before_ncalls": before_ncalls,
            "after_ncalls": after_ncalls,
        }

    return comparisons


def calculate_overall_runtime_delta(before_total: float, after_total: float) -> tuple[float, float]:
    """Calculate overall runtime change.

    Args:
        before_total: Total runtime before optimization (seconds)
        after_total: Total runtime after optimization (seconds)

    Returns:
        Tuple of (delta_seconds, delta_percentage)
    """
    delta_seconds = after_total - before_total
    delta_pct = (delta_seconds / before_total * 100) if before_total > 0 else 0
    return delta_seconds, delta_pct


def generate_comparison_report(
    before_dir: Path,
    after_dir: Path,
    scenario: str,
    output_file: Path,
) -> None:
    """Generate comparison report for a scenario.

    Args:
        before_dir: Directory with baseline profiling results
        after_dir: Directory with post-optimization profiling results
        scenario: Scenario name (e.g., 'daily')
        output_file: Output file for comparison report
    """
    logger.info("generating_comparison_report", scenario=scenario)

    # Load profile stats
    before_profile = before_dir / f"{scenario}_cprofile.pstats"
    after_profile = after_dir / f"{scenario}_cprofile.pstats"

    if not before_profile.exists():
        logger.warning("before_profile_missing", scenario=scenario, file=str(before_profile))
        return

    if not after_profile.exists():
        logger.warning("after_profile_missing", scenario=scenario, file=str(after_profile))
        return

    before_stats = load_profile_stats(before_profile)
    after_stats = load_profile_stats(after_profile)

    # Extract top functions
    before_funcs = extract_top_functions(before_stats, n=50)
    after_funcs = extract_top_functions(after_stats, n=50)

    # Compare
    comparisons = compare_function_stats(before_funcs, after_funcs)

    # Calculate overall runtime
    before_total = sum(ct for _, ct, _, _ in before_funcs)
    after_total = sum(ct for _, ct, _, _ in after_funcs)
    delta_seconds, delta_pct = calculate_overall_runtime_delta(before_total, after_total)

    # Generate report
    with open(output_file, "w") as f:
        f.write(f"# Profile Comparison Report: {scenario}\n\n")
        f.write(f"**Before**: {before_dir}\n")
        f.write(f"**After**: {after_dir}\n\n")
        f.write("## Overall Runtime Change\n\n")
        f.write(f"- Before: {before_total:.3f}s\n")
        f.write(f"- After: {after_total:.3f}s\n")
        f.write(f"- Delta: {delta_seconds:+.3f}s ({delta_pct:+.1f}%)\n\n")

        if delta_pct < 0:
            f.write(f"✅ **Speedup: {abs(delta_pct):.1f}%**\n\n")
        elif delta_pct > 0:
            f.write(f"⚠️ **Slowdown: {delta_pct:.1f}%**\n\n")
        else:
            f.write("➡️ **No significant change**\n\n")

        # Top improvements (functions with reduced time)
        improvements = {k: v for k, v in comparisons.items() if v["cumtime_delta"] < -0.001}
        improvements_sorted = sorted(improvements.items(), key=lambda x: x[1]["cumtime_delta"])

        f.write("## Top Improvements (Reduced Time)\n\n")
        f.write("| Function | Before (s) | After (s) | Delta (s) | Change (%) |\n")
        f.write("|----------|------------|-----------|-----------|------------|\n")
        for func, stats in improvements_sorted[:20]:
            f.write(
                f"| `{func}` | {stats['before_cumtime']:.4f} | {stats['after_cumtime']:.4f} | "
                f"{stats['cumtime_delta']:+.4f} | {stats['cumtime_pct']:+.1f}% |\n"
            )

        if not improvements_sorted:
            f.write("*No significant improvements detected*\n")

        f.write("\n")

        # Top regressions (functions with increased time)
        regressions = {k: v for k, v in comparisons.items() if v["cumtime_delta"] > 0.001}
        regressions_sorted = sorted(
            regressions.items(), key=lambda x: x[1]["cumtime_delta"], reverse=True
        )

        f.write("## Top Regressions (Increased Time)\n\n")
        f.write("| Function | Before (s) | After (s) | Delta (s) | Change (%) |\n")
        f.write("|----------|------------|-----------|-----------|------------|\n")
        for func, stats in regressions_sorted[:20]:
            f.write(
                f"| `{func}` | {stats['before_cumtime']:.4f} | {stats['after_cumtime']:.4f} | "
                f"{stats['cumtime_delta']:+.4f} | {stats['cumtime_pct']:+.1f}% |\n"
            )

        if not regressions_sorted:
            f.write("*No regressions detected*\n")

        f.write("\n")

    logger.info(
        "comparison_report_generated",
        scenario=scenario,
        output_file=str(output_file),
        overall_change_pct=delta_pct,
    )


def main() -> None:
    """Main entry point for profile comparison."""
    parser = argparse.ArgumentParser(
        description="Compare profiling results before and after optimization"
    )
    parser.add_argument(
        "before_dir",
        type=Path,
        help="Directory with baseline profiling results",
    )
    parser.add_argument(
        "after_dir",
        type=Path,
        help="Directory with post-optimization profiling results",
    )
    parser.add_argument(
        "--scenario",
        choices=["daily", "hourly", "minute", "all"],
        default="all",
        help="Scenario to compare (default: all)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file for comparison report (default: stdout)",
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

    # Validate directories
    if not args.before_dir.exists():
        logger.error("before_dir_not_found", dir=str(args.before_dir))
        sys.exit(1)

    if not args.after_dir.exists():
        logger.error("after_dir_not_found", dir=str(args.after_dir))
        sys.exit(1)

    # Select scenarios
    scenarios = ["daily", "hourly", "minute"] if args.scenario == "all" else [args.scenario]

    # Generate comparison reports
    for scenario in scenarios:
        output_file = args.output or Path(f"profile_comparison_{scenario}.md")
        generate_comparison_report(args.before_dir, args.after_dir, scenario, output_file)

    logger.info("comparison_complete", scenarios=scenarios)


if __name__ == "__main__":
    main()
