"""
Bottleneck analysis and reporting infrastructure.

This module provides tools for analyzing profiling data to identify bottlenecks,
calculate percentage contributions, and generate actionable recommendations.

Constitutional requirements:
- CR-002: Real profiling data analysis, no synthetic metrics
- CR-004: Complete type hints
- CR-007: Systematic analysis with decision documentation
"""

import json
import pstats
from datetime import datetime
from decimal import Decimal
from pathlib import Path


class BottleneckAnalysisReport:
    """
    Comprehensive bottleneck analysis report generator.

    Analyzes profiling data to identify:
    - Top bottlenecks by percentage contribution
    - Fixed vs variable costs
    - Memory efficiency issues
    - Actionable optimization opportunities
    """

    def __init__(self, profile_stats_path: str, workflow_name: str = "Workflow"):
        """
        Initialize bottleneck analysis report.

        Args:
            profile_stats_path: Path to .stats file from cProfile
            workflow_name: Name of the workflow being profiled
        """
        self.profile_stats_path = profile_stats_path
        self.workflow_name = workflow_name
        self.stats = pstats.Stats(profile_stats_path)
        self.total_time = Decimal(str(self.stats.total_tt))

        # Analysis results
        self.bottlenecks: list[dict] = []
        self.fixed_costs: list[dict] = []
        self.variable_costs: list[dict] = []
        self.memory_issues: list[dict] = []
        self.recommendations: list[str] = []

    def analyze(self) -> dict:
        """
        Perform comprehensive bottleneck analysis.

        Returns:
            Dictionary with analysis results
        """
        # Calculate percentage contributions
        self._calculate_percentage_contributions()

        # Categorize fixed vs variable costs
        self._categorize_cost_types()

        # Analyze memory efficiency (if available)
        self._analyze_memory_efficiency()

        # Generate recommendations
        self._generate_recommendations()

        return self._generate_summary()

    def _calculate_percentage_contributions(self) -> None:
        """
        Calculate percentage contribution of each function to total runtime.

        Identifies all functions contributing >0.5% of total time.
        """
        self.bottlenecks = []

        for func_key, (_cc, nc, tt, ct, _callers) in self.stats.stats.items():
            filename, line, func_name = func_key

            # Calculate percentage of total time
            percent_tottime = (
                (Decimal(str(tt)) / self.total_time * 100) if self.total_time > 0 else Decimal("0")
            )
            percent_cumtime = (
                (Decimal(str(ct)) / self.total_time * 100) if self.total_time > 0 else Decimal("0")
            )

            # Only include functions >0.5% of runtime (as per FR-006)
            if percent_cumtime >= Decimal("0.5"):
                self.bottlenecks.append(
                    {
                        "function": func_name,
                        "filename": filename,
                        "line": line,
                        "ncalls": nc,
                        "tottime": Decimal(str(tt)),
                        "cumtime": Decimal(str(ct)),
                        "percent_tottime": percent_tottime,
                        "percent_cumtime": percent_cumtime,
                        "percall_tottime": Decimal(str(tt / nc)) if nc > 0 else Decimal("0"),
                        "percall_cumtime": Decimal(str(ct / nc)) if nc > 0 else Decimal("0"),
                    }
                )

        # Sort by cumulative time percentage (highest first)
        self.bottlenecks.sort(key=lambda x: x["percent_cumtime"], reverse=True)

    def _categorize_cost_types(self) -> None:
        """
        Categorize costs as fixed vs variable.

        Fixed costs: Occur once or constant times (initialization, setup)
        Variable costs: Scale with data size (loops, iterations)
        """
        self.fixed_costs = []
        self.variable_costs = []

        for bottleneck in self.bottlenecks:
            # Heuristic: Functions called <10 times are likely fixed costs
            # Functions called many times are likely variable costs
            if bottleneck["ncalls"] < 10:
                bottleneck["cost_type"] = "fixed"
                self.fixed_costs.append(bottleneck)
            else:
                bottleneck["cost_type"] = "variable"
                self.variable_costs.append(bottleneck)

    def _analyze_memory_efficiency(self) -> None:
        """
        Analyze memory efficiency issues.

        Note: This is a placeholder. Full implementation would require
        memory_profiler integration or custom memory tracking.
        """
        # Placeholder: Check if any functions have suspiciously high per-call times
        # which might indicate memory allocation issues

        for bottleneck in self.bottlenecks:
            percall_time = bottleneck["percall_cumtime"]

            # If a single call takes >1 second, flag as potential memory issue
            if percall_time > Decimal("1.0"):
                self.memory_issues.append(
                    {
                        "function": bottleneck["function"],
                        "percall_time": percall_time,
                        "ncalls": bottleneck["ncalls"],
                        "issue": (
                            "High per-call time may indicate memory allocation or I/O bottleneck"
                        ),
                    }
                )

    def _generate_recommendations(self) -> None:
        """Generate actionable optimization recommendations based on analysis."""
        self.recommendations = []

        # Recommendation 1: Top bottleneck
        if self.bottlenecks:
            top = self.bottlenecks[0]
            self.recommendations.append(
                f"PRIMARY BOTTLENECK: {top['function']} ({top['percent_cumtime']:.1f}% of runtime) "
                f"- Consider optimizing this function first for maximum impact."
            )

        # Recommendation 2: Fixed costs
        if self.fixed_costs:
            fixed_total = sum(b["percent_cumtime"] for b in self.fixed_costs)
            if fixed_total > Decimal("10"):
                self.recommendations.append(
                    f"FIXED COSTS: {fixed_total:.1f}% of runtime is fixed overhead "
                    f"(initialization, setup). Consider batch processing or caching "
                    f"to amortize these costs over multiple operations."
                )

        # Recommendation 3: Variable costs
        if self.variable_costs:
            high_call_funcs = [b for b in self.variable_costs if b["ncalls"] > 1000]

            if high_call_funcs:
                self.recommendations.append(
                    f"VARIABLE COSTS: {len(high_call_funcs)} functions called >1000 times. "
                    f"Consider vectorization, caching, or algorithmic improvements."
                )

        # Recommendation 4: Memory issues
        if self.memory_issues:
            self.recommendations.append(
                f"MEMORY EFFICIENCY: {len(self.memory_issues)} functions with high per-call times "
                f"may have memory allocation issues. Profile with memory_profiler for details."
            )

        # Recommendation 5: Cumulative coverage
        if len(self.bottlenecks) >= 5:
            top5_coverage = sum(b["percent_cumtime"] for b in self.bottlenecks[:5])
            self.recommendations.append(
                f"COVERAGE: Top 5 bottlenecks account for {top5_coverage:.1f}% of runtime. "
                f"Optimizing these functions could yield significant improvements."
            )

    def _generate_summary(self) -> dict:
        """Generate summary dictionary with all analysis results."""
        return {
            "workflow_name": self.workflow_name,
            "total_time_seconds": float(self.total_time),
            "total_bottlenecks_identified": len(self.bottlenecks),
            "bottlenecks_gt_05_percent": len(self.bottlenecks),
            "bottlenecks_gt_5_percent": len(
                [b for b in self.bottlenecks if b["percent_cumtime"] >= Decimal("5")]
            ),
            "bottlenecks_gt_10_percent": len(
                [b for b in self.bottlenecks if b["percent_cumtime"] >= Decimal("10")]
            ),
            "fixed_costs_count": len(self.fixed_costs),
            "variable_costs_count": len(self.variable_costs),
            "fixed_costs_percent": float(sum(b["percent_cumtime"] for b in self.fixed_costs)),
            "variable_costs_percent": float(sum(b["percent_cumtime"] for b in self.variable_costs)),
            "memory_issues_count": len(self.memory_issues),
            "top_5_bottlenecks": [
                {
                    "function": b["function"],
                    "percent_cumtime": float(b["percent_cumtime"]),
                    "cumtime_seconds": float(b["cumtime"]),
                    "ncalls": b["ncalls"],
                    "cost_type": b["cost_type"],
                }
                for b in self.bottlenecks[:5]
            ],
            "recommendations": self.recommendations,
        }

    def generate_markdown_report(self, output_path: str | None = None) -> str:
        """
        Generate markdown report with bottleneck analysis.

        Args:
            output_path: Optional path to save report (if None, returns string only)

        Returns:
            Markdown report as string
        """
        summary = self._generate_summary()

        md = f"""# Bottleneck Analysis Report: {self.workflow_name}

**Generated**: {datetime.utcnow().isoformat()}Z
**Total Runtime**: {summary['total_time_seconds']:.3f}s
**Profile Source**: {self.profile_stats_path}

---

## Executive Summary

- **Total Bottlenecks Identified**: {summary['total_bottlenecks_identified']} (>0.5% of runtime)
- **Major Bottlenecks** (>5%): {summary['bottlenecks_gt_5_percent']}
- **Critical Bottlenecks** (>10%): {summary['bottlenecks_gt_10_percent']}
- **Fixed Costs**: {summary['fixed_costs_percent']:.1f}% of runtime \
({summary['fixed_costs_count']} functions)
- **Variable Costs**: {summary['variable_costs_percent']:.1f}% of runtime \
({summary['variable_costs_count']} functions)

---

## Top 5 Bottlenecks

| Rank | Function | % Runtime | Time (s) | Calls | Type |
|------|----------|-----------|----------|-------|------|
"""

        for idx, bottleneck in enumerate(summary["top_5_bottlenecks"], 1):
            md += (
                f"| {idx} | `{bottleneck['function']}` | "
                f"{bottleneck['percent_cumtime']:.2f}% | "
                f"{bottleneck['cumtime_seconds']:.3f} | "
                f"{bottleneck['ncalls']} | "
                f"{bottleneck['cost_type']} |\n"
            )

        md += "\n---\n\n## Detailed Bottleneck Breakdown\n\n"

        for idx, bottleneck in enumerate(self.bottlenecks[:20], 1):  # Top 20
            md += f"### {idx}. {bottleneck['function']}\n\n"
            md += f"- **Location**: `{bottleneck['filename']}:{bottleneck['line']}`\n"
            md += f"- **Runtime Contribution**: {bottleneck['percent_cumtime']:.2f}%\n"
            md += f"- **Cumulative Time**: {bottleneck['cumtime']:.3f}s\n"
            md += f"- **Total Calls**: {bottleneck['ncalls']:,}\n"
            md += f"- **Per-Call Time**: {bottleneck['percall_cumtime']:.6f}s\n"
            md += f"- **Cost Type**: {bottleneck['cost_type'].upper()}\n\n"

        md += "---\n\n## Fixed vs Variable Costs\n\n"
        md += f"### Fixed Costs ({summary['fixed_costs_percent']:.1f}% of runtime)\n\n"
        md += "Functions called <10 times (initialization, setup):\n\n"

        for cost in self.fixed_costs[:10]:  # Top 10 fixed costs
            md += (
                f"- `{cost['function']}`: {cost['percent_cumtime']:.2f}% ({cost['ncalls']} calls)\n"
            )

        md += f"\n### Variable Costs ({summary['variable_costs_percent']:.1f}% of runtime)\n\n"
        md += "Functions called many times (data processing, loops):\n\n"

        for cost in self.variable_costs[:10]:  # Top 10 variable costs
            md += (
                f"- `{cost['function']}`: "
                f"{cost['percent_cumtime']:.2f}% ({cost['ncalls']:,} calls)\n"
            )

        if self.memory_issues:
            md += "\n---\n\n## Memory Efficiency Issues\n\n"

            for issue in self.memory_issues:
                md += f"- **{issue['function']}**: {issue['issue']}\n"
                md += f"  - Per-call time: {issue['percall_time']:.3f}s\n"
                md += f"  - Total calls: {issue['ncalls']}\n\n"

        md += "\n---\n\n## Recommendations\n\n"

        for idx, rec in enumerate(self.recommendations, 1):
            md += f"{idx}. {rec}\n\n"

        md += "\n---\n\n"
        md += "*Report generated by RustyBT Benchmarking Infrastructure*\n"
        md += f"*Profile: {self.profile_stats_path}*\n"

        # Save to file if path provided
        if output_path:
            Path(output_path).write_text(md)

        return md

    def generate_json_report(self, output_path: str | None = None) -> dict:
        """
        Generate JSON report with bottleneck analysis.

        Args:
            output_path: Optional path to save report

        Returns:
            Report dictionary
        """
        report = {
            "metadata": {
                "workflow_name": self.workflow_name,
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "profile_source": self.profile_stats_path,
            },
            "summary": self._generate_summary(),
            "bottlenecks": [
                {
                    "function": b["function"],
                    "filename": b["filename"],
                    "line": b["line"],
                    "ncalls": b["ncalls"],
                    "tottime": float(b["tottime"]),
                    "cumtime": float(b["cumtime"]),
                    "percent_tottime": float(b["percent_tottime"]),
                    "percent_cumtime": float(b["percent_cumtime"]),
                    "percall_tottime": float(b["percall_tottime"]),
                    "percall_cumtime": float(b["percall_cumtime"]),
                    "cost_type": b["cost_type"],
                }
                for b in self.bottlenecks
            ],
            "fixed_costs": [
                {
                    "function": fc["function"],
                    "percent_cumtime": float(fc["percent_cumtime"]),
                    "ncalls": fc["ncalls"],
                }
                for fc in self.fixed_costs
            ],
            "variable_costs": [
                {
                    "function": vc["function"],
                    "percent_cumtime": float(vc["percent_cumtime"]),
                    "ncalls": vc["ncalls"],
                }
                for vc in self.variable_costs
            ],
            "memory_issues": self.memory_issues,
            "recommendations": self.recommendations,
        }

        # Save to file if path provided
        if output_path:
            Path(output_path).write_text(json.dumps(report, indent=2))

        return report


def generate_bottleneck_report(
    profile_stats_path: str, workflow_name: str = "Workflow", output_dir: str = "benchmark-results"
) -> tuple[dict, str, str]:
    """
    Generate comprehensive bottleneck analysis report.

    Convenience function that creates both JSON and Markdown reports.

    Args:
        profile_stats_path: Path to .stats file from cProfile
        workflow_name: Name of the workflow being profiled
        output_dir: Directory to save reports

    Returns:
        Tuple of (json_report, json_path, markdown_path)

    Examples:
        >>> json_report, json_path, md_path = generate_bottleneck_report(
        ...     "profiling-results/grid_search_cprofile.stats",
        ...     "Grid Search Optimization"
        ... )
        >>> print(f"Top bottleneck: {json_report['summary']['top_5_bottlenecks'][0]['function']}")
    """
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Generate report ID
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    report_id = f"{workflow_name.lower().replace(' ', '_')}_{timestamp}"

    # Create analyzer
    analyzer = BottleneckAnalysisReport(profile_stats_path, workflow_name)
    analyzer.analyze()

    # Generate reports
    json_path = str(output_path / f"{report_id}_bottlenecks.json")
    md_path = str(output_path / f"{report_id}_bottlenecks.md")

    json_report = analyzer.generate_json_report(json_path)
    analyzer.generate_markdown_report(md_path)

    return json_report, json_path, md_path


def generate_benchmark_report(
    results: list,
    output_path: str,
    title: str,
) -> None:
    """Generate a simple text report for benchmark results.

    Args:
        results: List of BenchmarkResult objects
        output_path: Path to write report to
        title: Report title
    """
    from datetime import datetime
    from pathlib import Path

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with open(output, "w") as f:
        f.write("=" * 80 + "\n")
        f.write(f"{title}\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")

        for result in results:
            f.write(f"Benchmark: {result.operation_name}\n")
            f.write(f"  Baseline: {result.baseline_time_ms:.2f} ms\n")
            f.write(f"  Optimized: {result.optimized_time_ms:.2f} ms\n")
            f.write(f"  Improvement: {result.improvement_percent:.2f}%\n")
            f.write(f"  Speedup: {result.speedup_ratio:.2f}x\n")
            f.write(f"  Statistical Significance: p={result.p_value:.4f}\n")
            f.write(f"  Status: {'PASS' if result.passed else 'FAIL'}\n")
            f.write("\n")

        f.write("=" * 80 + "\n")
