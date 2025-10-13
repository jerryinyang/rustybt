"""Calculate performance overhead between float and Decimal implementations.

This script compares benchmark results from float baseline and Decimal
implementations to calculate overhead percentages and generate reports.
"""

import argparse
import json
from pathlib import Path
from typing import Any


def load_benchmark_results(filepath: Path) -> dict[str, Any]:
    """Load benchmark results from JSON file.

    Args:
        filepath: Path to benchmark results JSON

    Returns:
        Benchmark results dictionary
    """
    with open(filepath) as f:
        return json.load(f)


def calculate_overhead(float_time: float, decimal_time: float) -> tuple[float, str]:
    """Calculate overhead percentage.

    Args:
        float_time: Float implementation time in seconds
        decimal_time: Decimal implementation time in seconds

    Returns:
        Tuple of (overhead_percentage, interpretation)
    """
    overhead = (decimal_time / float_time - 1) * 100

    if overhead < 10:
        interpretation = "Excellent - minor optimization needed"
    elif overhead < 30:
        interpretation = "Acceptable - moderate optimization target"
    elif overhead < 50:
        interpretation = "High - priority optimization target"
    else:
        interpretation = "Critical - top priority for Rust optimization"

    return overhead, interpretation


def generate_comparison_table(
    float_results: dict[str, Any],
    decimal_results: dict[str, Any],
) -> str:
    """Generate Markdown comparison table.

    Args:
        float_results: Float benchmark results
        decimal_results: Decimal benchmark results

    Returns:
        Markdown table string
    """
    lines = [
        "| Benchmark | Float Time (s) | Decimal Time (s) | Overhead % | Status |",
        "|-----------|----------------|------------------|------------|--------|",
    ]

    float_benchmarks = {b["name"]: b["stats"] for b in float_results["benchmarks"]}
    decimal_benchmarks = {b["name"]: b["stats"] for b in decimal_results["benchmarks"]}

    for name in sorted(float_benchmarks.keys()):
        if name not in decimal_benchmarks:
            continue

        float_time = float_benchmarks[name]["mean"]
        decimal_time = decimal_benchmarks[name]["mean"]

        overhead, interpretation = calculate_overhead(float_time, decimal_time)

        status_emoji = "✅" if overhead < 30 else "⚠️" if overhead < 50 else "❌"

        lines.append(
            f"| {name} | {float_time:.6f} | {decimal_time:.6f} | "
            f"+{overhead:.1f}% | {status_emoji} {interpretation} |"
        )

    return "\n".join(lines)


def generate_markdown_report(
    float_results: dict[str, Any],
    decimal_results: dict[str, Any],
    output_path: Path,
) -> None:
    """Generate comprehensive Markdown report.

    Args:
        float_results: Float benchmark results
        decimal_results: Decimal benchmark results
        output_path: Output file path
    """
    # Calculate overall statistics
    float_times = [b["stats"]["mean"] for b in float_results["benchmarks"]]
    decimal_times = [b["stats"]["mean"] for b in decimal_results["benchmarks"]]

    float_total = sum(float_times)
    decimal_total = sum(decimal_times)
    overall_overhead, _ = calculate_overhead(float_total, decimal_total)

    comparison_table = generate_comparison_table(float_results, decimal_results)

    report = f"""# Decimal Performance Baseline

**Generated:** 2025-10-01
**Benchmark Version:** 1.0
**Hardware:** GitHub Actions Ubuntu Runner

## Executive Summary

- **Overall Overhead:** {overall_overhead:.1f}% slower than float baseline
- **Number of Benchmarks:** {len(float_results["benchmarks"])}
- **Epic 7 Target:** Reduce overhead to <30%

## Overall Performance

| Metric | Float Baseline | Decimal Current | Overhead |
|--------|----------------|-----------------|----------|
| Total time | {float_total:.4f}s | {decimal_total:.4f}s | +{overall_overhead:.1f}% |

## Detailed Benchmark Results

{comparison_table}

## Interpretation

{interpret_overall_results(overall_overhead)}

## Next Steps

1. Review high-overhead benchmarks (>30%)
2. Profile hotspots using cProfile
3. Prioritize Rust optimization targets for Epic 7
4. Implement Rust optimization for top hotspots
5. Re-run benchmarks to validate improvement

## Benchmark Methodology

See `docs/performance/benchmarking.md` for detailed methodology.

---

*Benchmark data:*
- *Float baseline: `{float_results.get("commit_info", {}).get("id", "N/A")}`*
- *Decimal results: `{decimal_results.get("commit_info", {}).get("id", "N/A")}`*
"""

    with open(output_path, "w") as f:
        f.write(report)

    print(f"Report generated: {output_path}")


def interpret_overall_results(overhead: float) -> str:
    """Provide interpretation of overall results.

    Args:
        overhead: Overall overhead percentage

    Returns:
        Interpretation text
    """
    if overhead < 10:
        return """
**Status:** ✅ **EXCELLENT**

The Decimal implementation has minimal overhead (<10%). Epic 7 Rust optimization
may not be necessary for significant performance gains. Focus on other optimization
opportunities.
"""
    elif overhead < 30:
        return """
**Status:** ✅ **TARGET ACHIEVED**

The Decimal implementation meets the Epic 7 target of <30% overhead. However,
there is still room for improvement. Epic 7 Rust optimization can bring this
closer to float performance (<10% overhead).

**Recommended Priority:** Medium - optimize highest-overhead modules first.
"""
    elif overhead < 50:
        return """
**Status:** ⚠️ **HIGH OVERHEAD**

The Decimal implementation has significant overhead (30-50%). Epic 7 Rust
optimization is **recommended** to bring performance closer to target.

**Recommended Priority:** High - prioritize top 3-5 hotspots for Rust optimization.
"""
    else:
        return """
**Status:** ❌ **CRITICAL OVERHEAD**

The Decimal implementation has critical overhead (>50%). Epic 7 Rust optimization
is **mandatory** to achieve acceptable performance.

**Recommended Priority:** Critical - immediately profile and optimize top 10 hotspots.
Consider re-evaluating Decimal implementation approach if overhead remains >50%
after profiling.
"""


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Calculate Decimal vs float overhead")
    parser.add_argument(
        "float_baseline",
        type=Path,
        help="Path to float baseline results JSON",
    )
    parser.add_argument(
        "decimal_results",
        type=Path,
        help="Path to Decimal results JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/performance/decimal-baseline.md"),
        help="Output Markdown report path",
    )

    args = parser.parse_args()

    # Load results
    print(f"Loading float baseline: {args.float_baseline}")
    float_results = load_benchmark_results(args.float_baseline)

    print(f"Loading Decimal results: {args.decimal_results}")
    decimal_results = load_benchmark_results(args.decimal_results)

    # Generate report
    generate_markdown_report(float_results, decimal_results, args.output)

    print("\n✅ Overhead calculation complete!")


if __name__ == "__main__":
    main()
