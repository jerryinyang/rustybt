#!/usr/bin/env python
"""Compare two benchmark runs.

Usage:
    python scripts/benchmarks/compare_benchmarks.py abc123def xyz789abc
    python scripts/benchmarks/compare_benchmarks.py --commit1 abc123 --commit2 xyz789
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Paths
RESULTS_DIR = Path(__file__).parent.parent.parent / "docs" / "performance"
HISTORY_FILE = RESULTS_DIR / "benchmark-history.json"


def load_history() -> dict[str, Any]:
    """Load benchmark history."""
    if not HISTORY_FILE.exists():
        print(f"❌ History file not found: {HISTORY_FILE}", file=sys.stderr)
        sys.exit(1)

    with open(HISTORY_FILE) as f:
        return json.load(f)


def find_run_by_commit(runs: list[dict], commit_prefix: str) -> dict | None:
    """Find a run by commit prefix."""
    for run in reversed(runs):  # Search from most recent
        if run.get("git_commit", "").startswith(commit_prefix):
            return run
    return None


def compare_runs(run1: dict, run2: dict) -> None:
    """Compare two benchmark runs."""
    print("\n" + "=" * 90)
    print("Benchmark Comparison")
    print("=" * 90)
    print(f"\nRun 1: {run1.get('git_commit', 'unknown')[:8]} @ {run1.get('timestamp', 'unknown')}")
    print(f"Run 2: {run2.get('git_commit', 'unknown')[:8]} @ {run2.get('timestamp', 'unknown')}")
    print()

    # Compare by scenario
    scenarios1 = {run1.get("scenario"): run1.get("execution_time", 0.0)}
    scenarios2 = {run2.get("scenario"): run2.get("execution_time", 0.0)}

    common_scenarios = set(scenarios1.keys()) & set(scenarios2.keys())

    if not common_scenarios:
        print("⚠️  No common scenarios found between runs")
        return

    print(f"{'Scenario':<30} {'Run 1 (s)':<12} {'Run 2 (s)':<12} {'Delta':<10} {'Change':<10}")
    print("-" * 90)

    for scenario in sorted(common_scenarios):
        time1 = scenarios1[scenario]
        time2 = scenarios2[scenario]
        delta = time2 - time1
        change_pct = ((time2 / time1) - 1) * 100 if time1 > 0 else 0.0

        indicator = "🔴" if change_pct > 5 else "🟢" if change_pct < -5 else "⚪"

        print(
            f"{scenario:<30} {time1:<12.2f} {time2:<12.2f} {delta:+10.2f} {change_pct:+9.1f}% {indicator}"
        )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Compare two benchmark runs")
    parser.add_argument("commit1", nargs="?", help="First commit SHA (prefix)")
    parser.add_argument("commit2", nargs="?", help="Second commit SHA (prefix)")
    parser.add_argument("--commit1", dest="commit1_flag", help="First commit SHA")
    parser.add_argument("--commit2", dest="commit2_flag", help="Second commit SHA")

    args = parser.parse_args()

    commit1 = args.commit1 or args.commit1_flag
    commit2 = args.commit2 or args.commit2_flag

    if not commit1 or not commit2:
        parser.error("Two commit SHAs required")

    # Load history
    history = load_history()
    runs = history.get("runs", [])

    if not runs:
        print("No benchmark runs in history")
        sys.exit(1)

    # Find runs
    run1 = find_run_by_commit(runs, commit1)
    run2 = find_run_by_commit(runs, commit2)

    if not run1:
        print(f"❌ Run not found for commit: {commit1}", file=sys.stderr)
        sys.exit(1)

    if not run2:
        print(f"❌ Run not found for commit: {commit2}", file=sys.stderr)
        sys.exit(1)

    # Compare
    compare_runs(run1, run2)


if __name__ == "__main__":
    main()
