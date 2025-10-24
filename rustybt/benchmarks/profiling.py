"""
Profiling infrastructure for performance analysis.

This module provides comprehensive profiling tools using cProfile, line_profiler,
and memory_profiler to identify bottlenecks in workflows.

Constitutional requirements:
- CR-002: Real profiling data, no synthetic metrics
- CR-004: Complete type hints
- CR-007: Sprint Debug Discipline - systematic profiling workflow
"""

import cProfile
import io
import json
import platform
import pstats
import sys
import time
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from .exceptions import ProfilingError
from .models import BenchmarkResult, BenchmarkResultSet


def profile_workflow(
    workflow_fn: Callable[..., Any],
    workflow_args: tuple = (),
    workflow_kwargs: dict[str, Any] | None = None,
    profiler_type: str = "cprofile",
    output_dir: str = "profiling-results",
    run_id: str | None = None,
) -> tuple[Any, dict[str, Any]]:
    """
    Profile a workflow function and generate profiling reports.

    Supports multiple profiling backends:
    - 'cprofile': Function-level profiling (default)
    - 'line_profiler': Line-by-line profiling (requires line_profiler package)
    - 'memory_profiler': Memory usage profiling (requires memory_profiler package)

    Args:
        workflow_fn: Function to profile
        workflow_args: Positional arguments for workflow_fn
        workflow_kwargs: Keyword arguments for workflow_fn
        profiler_type: Type of profiler ('cprofile', 'line_profiler', 'memory_profiler')
        output_dir: Directory to save profiling output
        run_id: Unique identifier for this run (auto-generated if None)

    Returns:
        Tuple of (workflow_result, profiling_metrics)
        where profiling_metrics contains:
        {
            'total_time_seconds': Decimal,
            'cpu_time_seconds': Decimal,
            'memory_peak_mb': Decimal,
            'profile_output_path': str,
            'stats_json_path': str,
            'run_id': str
        }

    Raises:
        ProfilingError: If profiling fails

    Examples:
        >>> def my_workflow(param1, param2):
        ...     return param1 + param2
        >>> result, metrics = profile_workflow(my_workflow, (10, 20))
        >>> print(f"Execution time: {metrics['total_time_seconds']}s")
    """
    if workflow_kwargs is None:
        workflow_kwargs = {}

    if run_id is None:
        run_id = f"{workflow_fn.__name__}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if profiler_type == "cprofile":
        return _profile_with_cprofile(
            workflow_fn, workflow_args, workflow_kwargs, output_path, run_id
        )
    elif profiler_type == "line_profiler":
        return _profile_with_line_profiler(
            workflow_fn, workflow_args, workflow_kwargs, output_path, run_id
        )
    elif profiler_type == "memory_profiler":
        return _profile_with_memory_profiler(
            workflow_fn, workflow_args, workflow_kwargs, output_path, run_id
        )
    else:
        raise ValueError(f"Unknown profiler type: {profiler_type}")


def _profile_with_cprofile(
    workflow_fn: Callable[..., Any],
    workflow_args: tuple,
    workflow_kwargs: dict[str, Any],
    output_path: Path,
    run_id: str,
) -> tuple[Any, dict[str, Any]]:
    """Profile using cProfile (function-level profiling)."""
    profiler = cProfile.Profile()

    # Time the execution
    start_time = time.perf_counter()
    start_cpu = time.process_time()

    try:
        profiler.enable()
        result = workflow_fn(*workflow_args, **workflow_kwargs)
        profiler.disable()
    except Exception as e:
        raise ProfilingError(f"Workflow execution failed during profiling: {e}") from e

    end_time = time.perf_counter()
    end_cpu = time.process_time()

    total_time = Decimal(str(end_time - start_time))
    cpu_time = Decimal(str(end_cpu - start_cpu))

    # Save profiling stats
    stats_file = output_path / f"{run_id}_cprofile.stats"
    profiler.dump_stats(str(stats_file))

    # Generate human-readable report
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats("cumulative")
    ps.print_stats(50)  # Top 50 functions

    report_file = output_path / f"{run_id}_cprofile_report.txt"
    report_file.write_text(s.getvalue())

    # Generate JSON stats for programmatic analysis
    json_stats = _extract_cprofile_json_stats(profiler)
    json_file = output_path / f"{run_id}_cprofile_stats.json"
    json_file.write_text(json.dumps(json_stats, indent=2))

    metrics = {
        "total_time_seconds": total_time,
        "cpu_time_seconds": cpu_time,
        "memory_peak_mb": Decimal("0"),  # cProfile doesn't track memory
        "profile_output_path": str(report_file),
        "stats_json_path": str(json_file),
        "run_id": run_id,
        "profiler_type": "cprofile",
    }

    return result, metrics


def _profile_with_line_profiler(
    workflow_fn: Callable[..., Any],
    workflow_args: tuple,
    workflow_kwargs: dict[str, Any],
    output_path: Path,
    run_id: str,
) -> tuple[Any, dict[str, Any]]:
    """Profile using line_profiler (line-by-line profiling)."""
    try:
        from line_profiler import LineProfiler
    except ImportError as e:
        raise ProfilingError(
            "line_profiler not installed. Install with: pip install line_profiler"
        ) from e

    profiler = LineProfiler()
    profiler.add_function(workflow_fn)

    # Time the execution
    start_time = time.perf_counter()
    start_cpu = time.process_time()

    try:
        wrapper = profiler(workflow_fn)
        result = wrapper(*workflow_args, **workflow_kwargs)
    except Exception as e:
        raise ProfilingError(f"Workflow execution failed during profiling: {e}") from e

    end_time = time.perf_counter()
    end_cpu = time.process_time()

    total_time = Decimal(str(end_time - start_time))
    cpu_time = Decimal(str(end_cpu - start_cpu))

    # Save profiling stats
    report_file = output_path / f"{run_id}_line_profiler.txt"
    with open(report_file, "w") as f:
        profiler.print_stats(stream=f)

    metrics = {
        "total_time_seconds": total_time,
        "cpu_time_seconds": cpu_time,
        "memory_peak_mb": Decimal("0"),  # line_profiler doesn't track memory
        "profile_output_path": str(report_file),
        "stats_json_path": None,
        "run_id": run_id,
        "profiler_type": "line_profiler",
    }

    return result, metrics


def _profile_with_memory_profiler(
    workflow_fn: Callable[..., Any],
    workflow_args: tuple,
    workflow_kwargs: dict[str, Any],
    output_path: Path,
    run_id: str,
) -> tuple[Any, dict[str, Any]]:
    """Profile using memory_profiler (memory usage tracking)."""
    try:
        from memory_profiler import memory_usage
    except ImportError as e:
        raise ProfilingError(
            "memory_profiler not installed. Install with: pip install memory_profiler"
        ) from e

    # Time the execution
    start_time = time.perf_counter()
    start_cpu = time.process_time()

    # Track memory usage during execution
    mem_usage = []
    result_container = []

    def wrapper() -> None:
        try:
            res = workflow_fn(*workflow_args, **workflow_kwargs)
            result_container.append(res)
        except Exception as e:
            raise ProfilingError(f"Workflow execution failed during profiling: {e}") from e

    try:
        mem_usage = memory_usage(
            wrapper,
            interval=0.1,  # Sample every 0.1 seconds
            include_children=True,
            multiprocess=True,
        )
    except Exception as e:
        raise ProfilingError(f"Memory profiling failed: {e}") from e

    end_time = time.perf_counter()
    end_cpu = time.process_time()

    total_time = Decimal(str(end_time - start_time))
    cpu_time = Decimal(str(end_cpu - start_cpu))
    memory_peak_mb = Decimal(str(max(mem_usage))) if mem_usage else Decimal("0")

    # Save memory usage plot data
    json_file = output_path / f"{run_id}_memory_usage.json"
    json_file.write_text(
        json.dumps(
            {
                "memory_usage_mb": mem_usage,
                "peak_mb": float(memory_peak_mb),
                "sampling_interval": 0.1,
            },
            indent=2,
        )
    )

    result = result_container[0] if result_container else None

    metrics = {
        "total_time_seconds": total_time,
        "cpu_time_seconds": cpu_time,
        "memory_peak_mb": memory_peak_mb,
        "profile_output_path": str(json_file),
        "stats_json_path": str(json_file),
        "run_id": run_id,
        "profiler_type": "memory_profiler",
    }

    return result, metrics


def _extract_cprofile_json_stats(profiler: cProfile.Profile) -> dict[str, Any]:
    """Extract cProfile stats as JSON-serializable dict."""
    stats = pstats.Stats(profiler)

    functions = []
    for func_key, (_cc, nc, tt, ct, _callers) in stats.stats.items():
        filename, line, func_name = func_key
        functions.append(
            {
                "filename": filename,
                "line": line,
                "function": func_name,
                "ncalls": nc,
                "tottime": tt,
                "cumtime": ct,
                "percall_tottime": tt / nc if nc > 0 else 0,
                "percall_cumtime": ct / nc if nc > 0 else 0,
            }
        )

    # Sort by cumulative time
    functions.sort(key=lambda x: x["cumtime"], reverse=True)

    return {
        "total_calls": stats.total_calls,
        "primitive_calls": stats.prim_calls,
        "total_time": stats.total_tt,
        "functions": functions[:100],  # Top 100 functions
    }


def run_benchmark_suite(
    workflow_fn: Callable[..., Any],
    workflow_args: tuple = (),
    workflow_kwargs: dict[str, Any] | None = None,
    num_runs: int = 10,
    configuration_name: str = "benchmark",
    workflow_type: str = "grid_search",
    output_dir: str = "benchmark-results",
    dataset_size: int = 1,
    parameter_combinations: int = 1,
    backtest_count: int = 1,
) -> BenchmarkResultSet:
    """
    Run a benchmark suite with multiple iterations for statistical analysis.

    Args:
        workflow_fn: Function to benchmark
        workflow_args: Positional arguments for workflow_fn
        workflow_kwargs: Keyword arguments for workflow_fn
        num_runs: Number of benchmark runs (default: 10 for 95% CI)
        configuration_name: Name for this configuration (e.g., "baseline", "optimized")
        workflow_type: Type of workflow being benchmarked
        output_dir: Directory to save benchmark results
        dataset_size: Size of dataset processed (for reporting)
        parameter_combinations: Number of parameter combinations (for optimization workflows)
        backtest_count: Number of backtests executed (for optimization workflows)

    Returns:
        BenchmarkResultSet with all runs

    Raises:
        ProfilingError: If benchmarking fails

    Examples:
        >>> def my_workflow(n):
        ...     return sum(range(n))
        >>> results = run_benchmark_suite(my_workflow, (1000000,), num_runs=10)
        >>> print(f"Mean time: {results.execution_time_mean}s")
        >>> print(f"95% CI: {results.execution_time_ci_95}")
    """
    if workflow_kwargs is None:
        workflow_kwargs = {}

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Platform information
    platform_info = platform.system().lower()
    cpu_model = platform.processor() or "Unknown"
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    results = []

    for run_num in range(1, num_runs + 1):
        run_id = f"{configuration_name}_run{run_num:03d}"

        # Run with cProfile to get timing
        _, metrics = profile_workflow(
            workflow_fn,
            workflow_args,
            workflow_kwargs,
            profiler_type="cprofile",
            output_dir=str(output_path),
            run_id=run_id,
        )

        # Create BenchmarkResult
        result = BenchmarkResult(
            benchmark_id=run_id,
            configuration_name=configuration_name,
            iteration_number=run_num,
            execution_time_seconds=metrics["total_time_seconds"],
            cpu_time_seconds=metrics["cpu_time_seconds"],
            memory_peak_mb=metrics.get("memory_peak_mb", Decimal("0")),
            memory_average_mb=Decimal("0"),  # Would need continuous monitoring
            dataset_size=dataset_size,
            parameter_combinations=parameter_combinations,
            backtest_count=backtest_count,
            platform=platform_info,
            cpu_model=cpu_model,
            python_version=python_version,
            timestamp=datetime.utcnow().isoformat() + "Z",
            random_seed=None,
            flame_graph_path=None,
            profiling_json_path=metrics.get("stats_json_path"),
        )

        results.append(result)

    # Create result set
    result_set = BenchmarkResultSet(
        configuration_name=configuration_name, workflow_type=workflow_type, results=results
    )

    # Save result set to JSON
    result_file = output_path / f"{configuration_name}_results.json"
    _save_result_set_json(result_set, result_file)

    return result_set


def _save_result_set_json(result_set: BenchmarkResultSet, output_file: Path) -> None:
    """Save BenchmarkResultSet to JSON file."""
    data = {
        "configuration_name": result_set.configuration_name,
        "workflow_type": result_set.workflow_type,
        "sample_size": result_set.sample_size,
        "execution_time_mean": str(result_set.execution_time_mean),
        "execution_time_std": str(result_set.execution_time_std),
        "execution_time_ci_95": [str(ci) for ci in result_set.execution_time_ci_95],
        "memory_peak_max": str(result_set.memory_peak_max),
        "results": [
            {
                "benchmark_id": r.benchmark_id,
                "iteration_number": r.iteration_number,
                "execution_time_seconds": str(r.execution_time_seconds),
                "cpu_time_seconds": str(r.cpu_time_seconds),
                "memory_peak_mb": str(r.memory_peak_mb),
                "platform": r.platform,
                "cpu_model": r.cpu_model,
                "python_version": r.python_version,
                "timestamp": r.timestamp,
            }
            for r in result_set.results
        ],
    }

    output_file.write_text(json.dumps(data, indent=2))


def generate_flame_graph(
    profile_stats_path: str,
    output_svg_path: str | None = None,
    title: str = "Flame Graph",
    min_percent: float = 0.5,
) -> str:
    """
    Generate flame graph visualization from profiling data.

    This implementation converts profiling data to an SVG call graph visualization
    using pstats data. For more advanced flame graphs, consider using py-spy or
    flamegraph.pl externally.

    Args:
        profile_stats_path: Path to .stats file from cProfile
        output_svg_path: Output path for SVG file (auto-generated if None)
        title: Title for the flame graph
        min_percent: Minimum percentage of time to include in visualization (default: 0.5%)

    Returns:
        Path to generated SVG file

    Raises:
        ProfilingError: If flame graph generation fails

    Examples:
        >>> # After profiling
        >>> svg_path = generate_flame_graph("profiling-results/run001_cprofile.stats")
        >>> print(f"Flame graph saved to: {svg_path}")
    """
    if output_svg_path is None:
        stats_path = Path(profile_stats_path)
        output_svg_path = str(stats_path.with_suffix(".svg"))

    try:
        # Try using gprof2dot + graphviz for professional visualization
        svg_content = _try_gprof2dot_visualization(profile_stats_path, title, min_percent)

        if svg_content:
            # gprof2dot succeeded
            Path(output_svg_path).write_text(svg_content)
            return output_svg_path

        # Fallback: Generate simple SVG call tree visualization
        svg_content = _generate_simple_svg_flamegraph(profile_stats_path, title, min_percent)

        Path(output_svg_path).write_text(svg_content)
        return output_svg_path

    except Exception as e:
        raise ProfilingError(f"Failed to generate flame graph: {e}") from e


def _try_gprof2dot_visualization(
    profile_stats_path: str, title: str, min_percent: float
) -> str | None:
    """
    Attempt to generate flame graph using gprof2dot + graphviz.

    Returns SVG content if successful, None if tools not available.
    """
    import shutil
    import subprocess

    # Check if gprof2dot and dot are available
    if not shutil.which("gprof2dot"):
        return None
    if not shutil.which("dot"):
        return None

    try:
        # Generate DOT graph from pstats
        gprof2dot_cmd = [
            "gprof2dot",
            "-f",
            "pstats",
            "-n",
            str(min_percent),  # Filter nodes <min_percent%
            "-e",
            str(min_percent * 0.1),  # Filter edges
            profile_stats_path,
        ]

        # Safe: uses list arguments (no shell injection risk)
        dot_graph = subprocess.check_output(  # noqa: S603
            gprof2dot_cmd, stderr=subprocess.PIPE, text=True
        )

        # Convert DOT to SVG
        # Safe: uses list arguments (no shell injection risk)
        dot_cmd = ["dot", "-Tsvg"]
        svg_output = subprocess.check_output(  # noqa: S603
            dot_cmd, input=dot_graph, stderr=subprocess.PIPE, text=True
        )

        # Add title to SVG
        svg_output = svg_output.replace("<svg", f'<svg data-title="{title}"', 1)

        return svg_output

    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _generate_simple_svg_flamegraph(profile_stats_path: str, title: str, min_percent: float) -> str:
    """
    Generate a simple SVG flame graph visualization from profiling data.

    This creates a horizontal bar chart showing the top functions by cumulative time.
    Not a true flame graph (which would show call stacks), but provides useful
    visualization without external dependencies.
    """
    # Load profiling stats
    stats = pstats.Stats(profile_stats_path)
    total_time = stats.total_tt

    # Extract top functions by cumulative time
    functions = []
    for func_key, (_cc, nc, tt, ct, _callers) in stats.stats.items():
        filename, line, func_name = func_key

        # Calculate percentage
        percent_cumtime = (ct / total_time * 100) if total_time > 0 else 0

        # Only include functions above threshold
        if percent_cumtime >= min_percent:
            functions.append(
                {
                    "name": func_name,
                    "location": f"{Path(filename).name}:{line}",
                    "percent": percent_cumtime,
                    "cumtime": ct,
                    "calls": nc,
                    "tottime": tt,
                }
            )

    # Sort by cumulative time (descending)
    functions.sort(key=lambda x: x["percent"], reverse=True)

    # Take top 30 for visualization
    top_functions = functions[:30]

    # Generate SVG
    width = 1400
    height = 50 + len(top_functions) * 35 + 100  # Header + bars + footer
    bar_height = 30
    bar_spacing = 5
    max_bar_width = 1000
    left_margin = 350

    svg_parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        "  <style>",
        "    .bar { fill: #e74c3c; stroke: #c0392b; stroke-width: 1; }",
        "    .bar:hover { fill: #c0392b; }",
        "    .func-name { font-family: monospace; font-size: 12px; fill: #2c3e50; }",
        "    .location { font-family: monospace; font-size: 10px; fill: #7f8c8d; }",
        "    .percent { "
        "font-family: monospace; font-size: 11px; fill: #2c3e50; font-weight: bold; "
        "}",
        "    .title { "
        "font-family: Arial, sans-serif; font-size: 20px; fill: #2c3e50; font-weight: bold; "
        "}",
        "    .subtitle { font-family: Arial, sans-serif; font-size: 12px; fill: #7f8c8d; }",
        "  </style>",
        "",
        "  <!-- Title -->",
        f'  <text x="20" y="30" class="title">{title}</text>',
        f'  <text x="20" y="50" class="subtitle">'
        f"Top {len(top_functions)} functions by cumulative time "
        f"(≥{min_percent}% of total runtime: {total_time:.3f}s)"
        "</text>",
        "",
        "  <!-- Bars -->",
    ]

    y_offset = 80

    for idx, func in enumerate(top_functions):
        bar_width = (func["percent"] / 100) * max_bar_width
        y = y_offset + idx * (bar_height + bar_spacing)

        # Color gradient based on percentage
        if func["percent"] >= 10:
            color = "#e74c3c"  # Red for critical bottlenecks
        elif func["percent"] >= 5:
            color = "#e67e22"  # Orange for major bottlenecks
        elif func["percent"] >= 1:
            color = "#f39c12"  # Yellow for notable bottlenecks
        else:
            color = "#3498db"  # Blue for minor bottlenecks

        # Truncate long function names
        func_name = func["name"]
        if len(func_name) > 40:
            func_name = func_name[:37] + "..."

        svg_parts.extend(
            [
                "  <g>",
                f'    <!-- Function {idx + 1}: {func["name"]} -->',
                f'    <rect x="{left_margin}" y="{y}" width="{bar_width}" height="{bar_height}" ',
                f'          style="fill: {color}; stroke: #2c3e50; stroke-width: 1;" />',
                f'    <text x="{left_margin - 10}" y="{y + 15}" '
                'text-anchor="end" class="func-name">',
                f"      {func_name}",
                "    </text>",
                f'    <text x="{left_margin - 10}" y="{y + 28}" '
                'text-anchor="end" class="location">',
                f'      {func["location"]}',
                "    </text>",
                f'    <text x="{left_margin + bar_width + 10}" y="{y + 20}" class="percent">',
                f'      {func["percent"]:.2f}% ({func["cumtime"]:.3f}s, {func["calls"]:,} calls)',
                "    </text>",
                "  </g>",
            ]
        )

    # Add legend
    legend_y = y_offset + len(top_functions) * (bar_height + bar_spacing) + 30

    svg_parts.extend(
        [
            "",
            "  <!-- Legend -->",
            f'  <text x="20" y="{legend_y}" class="subtitle">Color coding:</text>',
            f'  <rect x="20" y="{legend_y + 5}" width="15" height="15" '
            'fill="#e74c3c" stroke="#2c3e50"/>',
            f'  <text x="40" y="{legend_y + 16}" class="location">≥10% (Critical)</text>',
            f'  <rect x="150" y="{legend_y + 5}" width="15" height="15" '
            'fill="#e67e22" stroke="#2c3e50"/>',
            f'  <text x="170" y="{legend_y + 16}" class="location">≥5% (Major)</text>',
            f'  <rect x="280" y="{legend_y + 5}" width="15" height="15" '
            'fill="#f39c12" stroke="#2c3e50"/>',
            f'  <text x="300" y="{legend_y + 16}" class="location">≥1% (Notable)</text>',
            f'  <rect x="410" y="{legend_y + 5}" width="15" height="15" '
            'fill="#3498db" stroke="#2c3e50"/>',
            f'  <text x="430" y="{legend_y + 16}" class="location">&lt;1% (Minor)</text>',
            "",
            "  <!-- Footer -->",
            f'  <text x="{width - 10}" y="{height - 10}" text-anchor="end" class="location">',
            "    Generated by RustyBT Profiling Infrastructure",
            "  </text>",
            "</svg>",
        ]
    )

    return "\n".join(svg_parts)
