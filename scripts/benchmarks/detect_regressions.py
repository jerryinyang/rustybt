#!/usr/bin/env python
"""Detect performance regressions in benchmark results.

Compares current benchmark results to previous release baseline and flags
regressions >5% degradation.

Usage:
    python scripts/benchmarks/detect_regressions.py
    python scripts/benchmarks/detect_regressions.py --threshold 0.10

Exit codes:
    0: No regressions detected
    1: Regressions detected (fails CI/CD)
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
BASELINES_FILE = (
    Path(__file__).parent.parent.parent / "tests" / "regression" / "performance_baselines.json"
)

# Default thresholds
WARNING_THRESHOLD = 0.05  # 5% degradation warning
FAILURE_THRESHOLD = 0.20  # 20% degradation hard failure (from coding standards)


def load_history() -> dict[str, Any]:
    """Load benchmark history.

    Returns:
        Dict with 'runs' key containing list of runs
    """
    if not HISTORY_FILE.exists():
        print(f"❌ History file not found: {HISTORY_FILE}", file=sys.stderr)
        sys.exit(1)

    with open(HISTORY_FILE) as f:
        return json.load(f)


def load_baselines() -> dict[str, Any]:
    """Load performance baselines.

    Returns:
        Dict with baseline times by scenario
    """
    if not BASELINES_FILE.exists():
        print(f"⚠️  Baselines file not found: {BASELINES_FILE}", file=sys.stderr)
        print(
            "Run: pytest tests/regression/test_performance_regression.py::test_create_baselines",
            file=sys.stderr,
        )
        return {}

    with open(BASELINES_FILE) as f:
        return json.load(f)


def get_latest_results(history: dict[str, Any]) -> dict[str, float]:
    """Get latest benchmark results by scenario.

    Args:
        history: Benchmark history dict

    Returns:
        Dict mapping scenario name to execution time
    """
    runs = history.get("runs", [])

    if not runs:
        return {}

    # Group by scenario and take latest
    latest_by_scenario = {}

    for run in runs:
        scenario = run.get("scenario")
        exec_time = run.get("execution_time")
        timestamp = run.get("timestamp")

        if not all([scenario, exec_time, timestamp]):
            continue

        if scenario not in latest_by_scenario:
            latest_by_scenario[scenario] = run
        else:
            # Keep latest by timestamp
            if timestamp > latest_by_scenario[scenario]["timestamp"]:
                latest_by_scenario[scenario] = run

    return {s: r["execution_time"] for s, r in latest_by_scenario.items()}


def detect_regressions(
    current_results: dict[str, float],
    baselines: dict[str, Any],
    warning_threshold: float = WARNING_THRESHOLD,
    failure_threshold: float = FAILURE_THRESHOLD,
) -> tuple[list[dict], list[dict]]:
    """Detect performance regressions.

    Args:
        current_results: Current benchmark results (scenario -> time)
        baselines: Baseline benchmark results
        warning_threshold: Warning threshold (e.g., 0.05 for 5%)
        failure_threshold: Failure threshold (e.g., 0.20 for 20%)

    Returns:
        Tuple of (warnings, failures) lists
    """
    warnings = []
    failures = []

    for scenario, current_time in current_results.items():
        # Look up baseline
        baseline_time = None

        # Try exact match first
        if scenario in baselines:
            if isinstance(baselines[scenario], dict):
                baseline_time = baselines[scenario].get("decimal_rust")
            else:
                baseline_time = baselines[scenario]

        # Try fuzzy match (scenario name might differ slightly)
        if baseline_time is None:
            # Try matching by key parts (e.g., "daily", "simple", "50")
            for base_scenario, base_data in baselines.items():
                if base_scenario in scenario or scenario in base_scenario:
                    if isinstance(base_data, dict):
                        baseline_time = base_data.get("decimal_rust")
                    else:
                        baseline_time = base_data
                    break

        if baseline_time is None:
            continue  # No baseline to compare against

        # Calculate degradation
        degradation = (current_time / baseline_time) - 1
        degradation_pct = degradation * 100

        regression_data = {
            "scenario": scenario,
            "current_time": current_time,
            "baseline_time": baseline_time,
            "degradation": degradation,
            "degradation_pct": degradation_pct,
        }

        # Check thresholds
        if degradation > failure_threshold:
            failures.append(regression_data)
        elif degradation > warning_threshold:
            warnings.append(regression_data)

    return warnings, failures


def print_regression_report(warnings: list[dict], failures: list[dict]) -> None:
    """Print regression report.

    Args:
        warnings: List of warning regressions
        failures: List of failure regressions
    """
    print("\n" + "=" * 90)
    print("Performance Regression Report")
    print("=" * 90)
    print(f"Generated: {datetime.utcnow().isoformat()}")
    print()

    if failures:
        print("❌ FAILURES (>20% degradation):")
        print("-" * 90)
        for reg in sorted(failures, key=lambda x: x["degradation"], reverse=True):
            print(f"\n  Scenario: {reg['scenario']}")
            print(f"  Current:  {reg['current_time']:.2f}s")
            print(f"  Baseline: {reg['baseline_time']:.2f}s")
            print(f"  Degradation: {reg['degradation_pct']:+.1f}%")
        print()

    if warnings:
        print("⚠️  WARNINGS (>5% degradation):")
        print("-" * 90)
        for reg in sorted(warnings, key=lambda x: x["degradation"], reverse=True):
            print(f"\n  Scenario: {reg['scenario']}")
            print(f"  Current:  {reg['current_time']:.2f}s")
            print(f"  Baseline: {reg['baseline_time']:.2f}s")
            print(f"  Degradation: {reg['degradation_pct']:+.1f}%")
        print()

    if not warnings and not failures:
        print("✅ No regressions detected")
        print()


def create_github_issue_body(warnings: list[dict], failures: list[dict]) -> str:
    """Create GitHub issue body for regression alert.

    Args:
        warnings: List of warning regressions
        failures: List of failure regressions

    Returns:
        Markdown-formatted issue body
    """
    body = "# Performance Regression Detected\n\n"
    body += f"**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n\n"

    if failures:
        body += "## ❌ Critical Failures (>20% degradation)\n\n"
        body += "| Scenario | Current | Baseline | Degradation |\n"
        body += "|----------|---------|----------|-------------|\n"
        for reg in sorted(failures, key=lambda x: x["degradation"], reverse=True):
            body += f"| {reg['scenario']} | {reg['current_time']:.2f}s | {reg['baseline_time']:.2f}s | {reg['degradation_pct']:+.1f}% |\n"
        body += "\n"

    if warnings:
        body += "## ⚠️ Warnings (>5% degradation)\n\n"
        body += "| Scenario | Current | Baseline | Degradation |\n"
        body += "|----------|---------|----------|-------------|\n"
        for reg in sorted(warnings, key=lambda x: x["degradation"], reverse=True):
            body += f"| {reg['scenario']} | {reg['current_time']:.2f}s | {reg['baseline_time']:.2f}s | {reg['degradation_pct']:+.1f}% |\n"
        body += "\n"

    body += "## Action Items\n\n"
    body += "1. Review recent changes that might have impacted performance\n"
    body += "2. Run profiler to identify bottlenecks\n"
    body += "3. Consider additional Rust optimizations\n"
    body += "4. Update baselines if degradation is acceptable\n\n"
    body += "## Resources\n\n"
    body += "- [Benchmark Guide](docs/performance/benchmark-guide.md)\n"
    body += "- [Profiling Results](docs/performance/profiling-results.md)\n"
    body += "- [Story 7.5](docs/stories/7.5.implement-comprehensive-benchmarking-suite.story.md)\n"

    return body


def main():
    """Main entry point."""
    import os  # Move import to top of function

    parser = argparse.ArgumentParser(description="Detect performance regressions")
    parser.add_argument(
        "--threshold",
        type=float,
        default=WARNING_THRESHOLD,
        help=f"Warning threshold (default: {WARNING_THRESHOLD})",
    )
    parser.add_argument(
        "--failure-threshold",
        type=float,
        default=FAILURE_THRESHOLD,
        help=f"Failure threshold (default: {FAILURE_THRESHOLD})",
    )
    parser.add_argument(
        "--output",
        choices=["console", "json", "github"],
        default="console",
        help="Output format (default: console)",
    )

    args = parser.parse_args()

    # Load data
    history = load_history()
    baselines = load_baselines()

    if not baselines:
        print("⚠️  No baselines available, skipping regression detection", file=sys.stderr)
        sys.exit(0)

    # Get latest results
    current_results = get_latest_results(history)

    if not current_results:
        print("⚠️  No current results found in history", file=sys.stderr)
        sys.exit(0)

    # Detect regressions
    warnings, failures = detect_regressions(
        current_results,
        baselines,
        warning_threshold=args.threshold,
        failure_threshold=args.failure_threshold,
    )

    # Output results
    if args.output == "console":
        print_regression_report(warnings, failures)
    elif args.output == "json":
        result = {
            "warnings": warnings,
            "failures": failures,
            "regressions_detected": bool(warnings or failures),
        }
        print(json.dumps(result, indent=2))
    elif args.output == "github":
        issue_body = create_github_issue_body(warnings, failures)
        print(issue_body)

    # Set output for GitHub Actions
    if failures or warnings:
        # Write to GitHub Actions output if running in CI
        github_output = Path(os.environ.get("GITHUB_OUTPUT", ""))
        if github_output.exists():
            with open(github_output, "a") as f:
                f.write("regressions_detected=true\n")
                f.write(
                    f"regression_report<<EOF\n{create_github_issue_body(warnings, failures)}\nEOF\n"
                )

    # Exit with error if failures detected
    if failures:
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
