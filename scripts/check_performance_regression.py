#!/usr/bin/env python3
"""Check for performance regressions by comparing benchmark results.

This script compares current benchmark results against a baseline
and reports any performance degradations exceeding the threshold.

Exit codes:
    0: No regressions detected or all within threshold
    1: Performance regressions detected exceeding threshold
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple


def load_benchmark_results(filepath: Path) -> Dict:
    """Load benchmark results from JSON file.

    Args:
        filepath: Path to benchmark results JSON file

    Returns:
        Dictionary of benchmark results
    """
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {filepath}: {e}", file=sys.stderr)
        sys.exit(1)


def extract_benchmark_metrics(results: Dict) -> Dict[str, float]:
    """Extract benchmark metrics from results.

    Args:
        results: Benchmark results dictionary

    Returns:
        Dictionary mapping benchmark_name -> execution_time
    """
    metrics = {}

    # Handle pytest-benchmark format
    if "benchmarks" in results:
        for benchmark in results["benchmarks"]:
            name = benchmark.get("name", "unknown")
            # Use mean time or median time
            time = benchmark.get("stats", {}).get("mean") or benchmark.get("stats", {}).get(
                "median", 0
            )
            metrics[name] = time

    # Handle custom format (dict of benchmark_name: time)
    elif isinstance(results, dict):
        for name, data in results.items():
            if isinstance(data, (int, float)):
                metrics[name] = data
            elif isinstance(data, dict) and "time" in data:
                metrics[name] = data["time"]
            elif isinstance(data, dict) and "mean" in data:
                metrics[name] = data["mean"]

    return metrics


def compare_benchmarks(
    baseline: Dict[str, float], current: Dict[str, float], threshold: float = 0.20
) -> Tuple[List[Tuple[str, float, float, float]], List[Tuple[str, float, float, float]]]:
    """Compare baseline and current benchmarks.

    Args:
        baseline: Baseline benchmark metrics
        current: Current benchmark metrics
        threshold: Regression threshold (e.g., 0.20 = 20% slower)

    Returns:
        Tuple of (regressions, improvements)
        Each list contains tuples of (name, baseline_time, current_time, pct_change)
    """
    regressions = []
    improvements = []

    for name in baseline:
        if name not in current:
            print(f"Warning: Benchmark '{name}' not found in current results", file=sys.stderr)
            continue

        baseline_time = baseline[name]
        current_time = current[name]

        if baseline_time == 0:
            print(f"Warning: Baseline time for '{name}' is 0, skipping", file=sys.stderr)
            continue

        pct_change = (current_time - baseline_time) / baseline_time

        if pct_change > threshold:
            regressions.append((name, baseline_time, current_time, pct_change))
        elif pct_change < -0.05:  # Report improvements > 5%
            improvements.append((name, baseline_time, current_time, pct_change))

    return regressions, improvements


def format_time(seconds: float) -> str:
    """Format time in human-readable format.

    Args:
        seconds: Time in seconds

    Returns:
        Formatted string (e.g., "123.45 ms")
    """
    if seconds < 1e-6:
        return f"{seconds * 1e9:.2f} ns"
    elif seconds < 1e-3:
        return f"{seconds * 1e6:.2f} µs"
    elif seconds < 1:
        return f"{seconds * 1e3:.2f} ms"
    else:
        return f"{seconds:.2f} s"


def main():
    parser = argparse.ArgumentParser(description="Check for performance regressions in benchmarks")
    parser.add_argument(
        "--baseline",
        required=True,
        help="Path to baseline benchmark results (JSON)",
    )
    parser.add_argument(
        "--current",
        required=True,
        help="Path to current benchmark results (JSON)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.20,
        help="Regression threshold (default: 0.20 = 20%%)",
    )
    parser.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="Exit with error code if regressions detected",
    )

    args = parser.parse_args()

    baseline_path = Path(args.baseline)
    current_path = Path(args.current)

    print(f"Loading baseline benchmarks from {baseline_path}...")
    baseline_results = load_benchmark_results(baseline_path)
    baseline_metrics = extract_benchmark_metrics(baseline_results)

    print(f"Loading current benchmarks from {current_path}...")
    current_results = load_benchmark_results(current_path)
    current_metrics = extract_benchmark_metrics(current_results)

    print(f"\nComparing {len(baseline_metrics)} benchmarks...")
    print(f"Regression threshold: {args.threshold * 100:.0f}%\n")

    regressions, improvements = compare_benchmarks(
        baseline_metrics, current_metrics, args.threshold
    )

    # Report improvements
    if improvements:
        print(f"✅ Performance improvements ({len(improvements)}):\n")
        for name, baseline_time, current_time, pct_change in sorted(
            improvements, key=lambda x: x[3]
        ):
            print(f"  {name}")
            print(
                f"    Baseline: {format_time(baseline_time)} → Current: {format_time(current_time)}"
            )
            print(f"    Improvement: {-pct_change * 100:.1f}% faster")
            print()

    # Report regressions
    if regressions:
        print(f"❌ Performance regressions detected ({len(regressions)}):\n")
        for name, baseline_time, current_time, pct_change in sorted(
            regressions, key=lambda x: x[3], reverse=True
        ):
            print(f"  {name}")
            print(
                f"    Baseline: {format_time(baseline_time)} → Current: {format_time(current_time)}"
            )
            print(
                f"    Regression: {pct_change * 100:.1f}% slower (threshold: {args.threshold * 100:.0f}%)"
            )
            print()

        print("Action required:")
        print("1. Investigate the cause of performance degradation")
        print("2. Optimize the affected code")
        print("3. Update baseline if the regression is intentional")

        if args.fail_on_regression:
            sys.exit(1)
        else:
            print(
                "\nNote: Regressions detected but not failing due to --fail-on-regression not set"
            )
            sys.exit(0)
    else:
        print(f"✅ No performance regressions detected (threshold: {args.threshold * 100:.0f}%)")
        sys.exit(0)


if __name__ == "__main__":
    main()
