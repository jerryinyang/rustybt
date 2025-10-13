#!/usr/bin/env python
"""Query historical benchmark results.

Usage:
    python scripts/benchmarks/query_history.py --scenario daily_simple_50_rust --last 10
    python scripts/benchmarks/query_history.py --since 2025-01-01
    python scripts/benchmarks/query_history.py --commit abc123def
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Paths
RESULTS_DIR = Path(__file__).parent.parent.parent / "docs" / "performance"
HISTORY_FILE = RESULTS_DIR / "benchmark-history.json"


def load_history() -> dict[str, Any]:
    """Load benchmark history from JSON file.

    Returns:
        Dict with 'runs' key containing list of benchmark runs
    """
    if not HISTORY_FILE.exists():
        print(f"❌ History file not found: {HISTORY_FILE}", file=sys.stderr)
        print("Run benchmarks first to create history file", file=sys.stderr)
        sys.exit(1)

    with open(HISTORY_FILE) as f:
        return json.load(f)


def filter_runs(
    runs: list[dict],
    scenario: str | None = None,
    since: str | None = None,
    commit: str | None = None,
    last_n: int | None = None,
) -> list[dict]:
    """Filter benchmark runs based on criteria.

    Args:
        runs: List of benchmark runs
        scenario: Filter by scenario name
        since: Filter by date (ISO format: YYYY-MM-DD)
        commit: Filter by Git commit SHA
        last_n: Return only last N runs

    Returns:
        Filtered list of runs
    """
    filtered = runs

    # Filter by scenario
    if scenario:
        filtered = [r for r in filtered if r.get("scenario") == scenario]

    # Filter by date
    if since:
        since_dt = datetime.fromisoformat(since)
        filtered = [
            r for r in filtered if datetime.fromisoformat(r["timestamp"].rstrip("Z")) >= since_dt
        ]

    # Filter by commit
    if commit:
        filtered = [r for r in filtered if r.get("git_commit", "").startswith(commit)]

    # Take last N runs
    if last_n:
        filtered = filtered[-last_n:]

    return filtered


def print_runs(runs: list[dict]) -> None:
    """Print benchmark runs in tabular format.

    Args:
        runs: List of benchmark runs to print
    """
    if not runs:
        print("No matching benchmark runs found")
        return

    # Print header
    print(f"{'Timestamp':<20} {'Commit':<10} {'Scenario':<30} {'Time (s)':<10} {'Memory (MB)':<12}")
    print("-" * 90)

    # Print runs
    for run in runs:
        timestamp = run.get("timestamp", "N/A")[:19]  # Truncate to YYYY-MM-DD HH:MM:SS
        commit = run.get("git_commit", "N/A")[:8]
        scenario = run.get("scenario", "N/A")
        exec_time = run.get("execution_time", 0.0)
        memory_mb = run.get("memory_peak_mb", 0.0)

        print(f"{timestamp:<20} {commit:<10} {scenario:<30} {exec_time:<10.2f} {memory_mb:<12.1f}")

    print(f"\nTotal runs: {len(runs)}")


def print_summary(runs: list[dict]) -> None:
    """Print summary statistics for runs.

    Args:
        runs: List of benchmark runs
    """
    if not runs:
        return

    # Group by scenario
    by_scenario = {}
    for run in runs:
        scenario = run.get("scenario", "unknown")
        if scenario not in by_scenario:
            by_scenario[scenario] = []
        by_scenario[scenario].append(run)

    print("\n" + "=" * 90)
    print("Summary by Scenario")
    print("=" * 90)

    for scenario, scenario_runs in sorted(by_scenario.items()):
        times = [r.get("execution_time", 0.0) for r in scenario_runs if "execution_time" in r]

        if not times:
            continue

        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)

        print(f"\n{scenario}:")
        print(f"  Runs: {len(times)}")
        print(f"  Avg: {avg_time:.2f}s  Min: {min_time:.2f}s  Max: {max_time:.2f}s")

        # Calculate trend (if more than 2 runs)
        if len(times) >= 2:
            first_time = times[0]
            last_time = times[-1]
            delta = ((last_time / first_time) - 1) * 100
            trend = "📈" if delta > 5 else "📉" if delta < -5 else "➡️"
            print(f"  Trend: {trend} {delta:+.1f}% (first to last)")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Query historical benchmark results")
    parser.add_argument("--scenario", help="Filter by scenario name")
    parser.add_argument("--since", help="Filter by date (ISO format: YYYY-MM-DD)")
    parser.add_argument("--commit", help="Filter by Git commit SHA (prefix match)")
    parser.add_argument("--last", type=int, metavar="N", help="Show only last N runs")
    parser.add_argument("--summary", action="store_true", help="Show summary statistics")

    args = parser.parse_args()

    # Load history
    history = load_history()
    runs = history.get("runs", [])

    if not runs:
        print("No benchmark runs in history file")
        return

    # Filter runs
    filtered_runs = filter_runs(
        runs,
        scenario=args.scenario,
        since=args.since,
        commit=args.commit,
        last_n=args.last,
    )

    # Print results
    print_runs(filtered_runs)

    # Print summary if requested
    if args.summary and filtered_runs:
        print_summary(filtered_runs)


if __name__ == "__main__":
    main()
