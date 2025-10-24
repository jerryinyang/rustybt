"""
Sequential optimization evaluation infrastructure.

This module implements the sequential evaluation workflow where optimizations
are evaluated one at a time in priority order until goals are achieved or
diminishing returns are reached.

Constitutional requirements:
- CR-002: Real evaluation, no synthetic results
- CR-004: Complete type hints
- CR-007: Systematic workflow with decision documentation
"""

import json
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from .comparisons import validate_functional_equivalence
from .exceptions import FunctionalEquivalenceError, SequentialEvaluationError
from .models import (
    OptimizationComponent,
    PerformanceReport,
    PerformanceThreshold,
)
from .profiling import run_benchmark_suite
from .threshold import evaluate_threshold


def evaluate_single_optimization(
    optimization: OptimizationComponent,
    baseline_fn: Callable[..., Any],
    optimized_fn: Callable[..., Any],
    test_cases: list[tuple[tuple, dict]],
    benchmark_workload_fn: Callable[..., Any],
    benchmark_args: tuple,
    benchmark_kwargs: dict[str, Any] | None,
    threshold: PerformanceThreshold,
    num_benchmark_runs: int = 10,
    output_dir: str = "benchmark-results",
) -> dict[str, Any]:
    """
    Evaluate a single optimization following the BLOCKING functional consistency workflow.

    Workflow:
    1. Test functional equivalence (BLOCKING - must pass before benchmarking)
    2. Run baseline benchmarks
    3. Run optimized benchmarks
    4. Evaluate against threshold
    5. Generate decision

    Args:
        optimization: OptimizationComponent to evaluate
        baseline_fn: Baseline implementation function
        optimized_fn: Optimized implementation function
        test_cases: Test cases for functional equivalence
        benchmark_workload_fn: Workflow function to benchmark
        benchmark_args: Arguments for benchmark workflow
        benchmark_kwargs: Keyword arguments for benchmark workflow
        threshold: Performance threshold for evaluation
        num_benchmark_runs: Number of benchmark iterations (default: 10)
        output_dir: Directory for benchmark results

    Returns:
        Dictionary with evaluation results:
        {
            'component_id': str,
            'functional_equivalence_passed': bool,
            'baseline_results': BenchmarkResultSet,
            'optimized_results': BenchmarkResultSet,
            'threshold_evaluation': dict,
            'decision': str (accepted/rejected),
            'decision_rationale': str
        }

    Raises:
        FunctionalEquivalenceError: If functional consistency fails (BLOCKING)
        SequentialEvaluationError: If evaluation workflow fails

    Examples:
        >>> # Define baseline and optimized functions
        >>> def baseline_sma(values, window):
        ...     return python_sma(values, window)
        >>> def optimized_sma(values, window):
        ...     return rust_sma(values, window)  # Hypothetical
        >>>
        >>> # Test cases
        >>> test_cases = [
        ...     (([1.0, 2.0, 3.0, 4.0, 5.0], 3), {}),
        ... ]
        >>>
        >>> # Benchmark workload
        >>> def workload():
        ...     return baseline_sma([1.0]*1000, 20)
        >>>
        >>> result = evaluate_single_optimization(
        ...     optimization=my_optimization,
        ...     baseline_fn=baseline_sma,
        ...     optimized_fn=optimized_sma,
        ...     test_cases=test_cases,
        ...     benchmark_workload_fn=workload,
        ...     benchmark_args=(),
        ...     benchmark_kwargs={},
        ...     threshold=my_threshold
        ... )
    """
    if benchmark_kwargs is None:
        benchmark_kwargs = {}

    result = {
        "component_id": optimization.component_id,
        "component_name": optimization.component_name,
        "functional_equivalence_passed": False,
        "baseline_results": None,
        "optimized_results": None,
        "threshold_evaluation": None,
        "decision": "rejected",
        "decision_rationale": "",
    }

    # STEP 1: Functional Equivalence Testing (BLOCKING)

    try:
        validate_functional_equivalence(
            baseline_fn=baseline_fn,
            optimized_fn=optimized_fn,
            test_cases=test_cases,
            tolerance=Decimal("1e-10"),
            comparison_mode="array",
        )
        result["functional_equivalence_passed"] = True

    except FunctionalEquivalenceError as e:
        result["decision_rationale"] = f"REJECTED: Functional equivalence failed - {e}"
        return result  # BLOCKING - cannot proceed to benchmarking

    # STEP 2: Baseline Benchmarking

    try:
        baseline_results = run_benchmark_suite(
            workflow_fn=benchmark_workload_fn,
            workflow_args=benchmark_args,
            workflow_kwargs=benchmark_kwargs,
            num_runs=num_benchmark_runs,
            configuration_name=f"{optimization.component_id}_baseline",
            workflow_type=threshold.workflow_type,
            output_dir=output_dir,
        )
        result["baseline_results"] = baseline_results

    except Exception as e:
        result["decision_rationale"] = f"REJECTED: Baseline benchmarking failed - {e}"
        raise SequentialEvaluationError(f"Baseline benchmarking failed: {e}") from e

    # STEP 3: Optimized Benchmarking

    try:
        optimized_results = run_benchmark_suite(
            workflow_fn=benchmark_workload_fn,
            workflow_args=benchmark_args,
            workflow_kwargs=benchmark_kwargs,
            num_runs=num_benchmark_runs,
            configuration_name=f"{optimization.component_id}_optimized",
            workflow_type=threshold.workflow_type,
            output_dir=output_dir,
        )
        result["optimized_results"] = optimized_results

    except Exception as e:
        result["decision_rationale"] = f"REJECTED: Optimized benchmarking failed - {e}"
        raise SequentialEvaluationError(f"Optimized benchmarking failed: {e}") from e

    # STEP 4: Threshold Evaluation

    try:
        threshold_eval = evaluate_threshold(
            baseline_results=baseline_results,
            optimized_results=optimized_results,
            threshold=threshold,
            include_details=True,
        )
        result["threshold_evaluation"] = threshold_eval

        if threshold_eval["passes_threshold"]:
            result["decision"] = "accepted"
            result["decision_rationale"] = threshold_eval["decision_rationale"]
        else:
            result["decision"] = "rejected"
            result["decision_rationale"] = threshold_eval["decision_rationale"]

    except Exception as e:
        result["decision_rationale"] = f"REJECTED: Threshold evaluation failed - {e}"
        raise SequentialEvaluationError(f"Threshold evaluation failed: {e}") from e

    return result


def evaluate_optimization_sequence(
    optimizations: list[OptimizationComponent],
    threshold: PerformanceThreshold,
    evaluation_configs: dict[str, Any],
    output_dir: str = "benchmark-results",
    goal_improvement_percent: Decimal = Decimal("40.0"),
    stop_on_goal_achieved: bool = True,
) -> PerformanceReport:
    """
    Evaluate optimizations sequentially in priority order.

    Continues evaluation until:
    - Goal improvement achieved (default: 40%)
    - All optimizations evaluated
    - Diminishing returns (last 2 rejected)

    Args:
        optimizations: List of OptimizationComponent (sorted by priority_rank)
        threshold: PerformanceThreshold for evaluation
        evaluation_configs: Dict mapping component_id to evaluation configuration:
            {
                'component_id': {
                    'baseline_fn': Callable,
                    'optimized_fn': Callable,
                    'test_cases': List[Tuple],
                    'benchmark_workload_fn': Callable,
                    'benchmark_args': tuple,
                    'benchmark_kwargs': dict
                }
            }
        output_dir: Directory for results
        goal_improvement_percent: Target cumulative improvement (default: 40%)
        stop_on_goal_achieved: Stop when goal reached (default: True)

    Returns:
        PerformanceReport with evaluation results

    Raises:
        SequentialEvaluationError: If evaluation workflow fails

    Examples:
        >>> optimizations = [opt1, opt2, opt3]  # Sorted by priority
        >>> configs = {
        ...     'batch_init_v1': {
        ...         'baseline_fn': baseline_batch_init,
        ...         'optimized_fn': optimized_batch_init,
        ...         'test_cases': [...],
        ...         'benchmark_workload_fn': grid_search_workflow,
        ...         'benchmark_args': (),
        ...         'benchmark_kwargs': {}
        ...     }
        ... }
        >>> report = evaluate_optimization_sequence(optimizations, threshold, configs)
        >>> print(f"Cumulative improvement: {report.cumulative_improvement_percent}%")
    """
    # Sort optimizations by priority rank
    sorted_optimizations = sorted(optimizations, key=lambda o: o.priority_rank)

    # Initialize report
    report = PerformanceReport(
        report_id=f"seq_eval_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
        report_date=datetime.utcnow().isoformat() + "Z",
        workflow_type=threshold.workflow_type,
        components=sorted_optimizations,
        threshold=threshold,
        current_evaluation_index=0,
        executive_summary="",
        detailed_findings="",
    )

    # Evaluate optimizations sequentially
    for idx, optimization in enumerate(sorted_optimizations):
        report.current_evaluation_index = idx

        # Get evaluation configuration
        config = evaluation_configs.get(optimization.component_id)
        if not config:
            report.skipped_optimizations.append(optimization.component_id)
            continue

        # Evaluate single optimization
        try:
            eval_result = evaluate_single_optimization(
                optimization=optimization,
                baseline_fn=config["baseline_fn"],
                optimized_fn=config["optimized_fn"],
                test_cases=config["test_cases"],
                benchmark_workload_fn=config["benchmark_workload_fn"],
                benchmark_args=config.get("benchmark_args", ()),
                benchmark_kwargs=config.get("benchmark_kwargs", {}),
                threshold=threshold,
                num_benchmark_runs=threshold.min_sample_size,
                output_dir=output_dir,
            )

            # Update optimization component with results
            optimization.baseline_results = eval_result.get("baseline_results")
            optimization.optimized_results = eval_result.get("optimized_results")
            optimization.decision_rationale = eval_result.get("decision_rationale")
            optimization.evaluation_order = idx + 1

            # Record decision
            if eval_result["decision"] == "accepted":
                optimization.status = "accepted"
                report.accepted_optimizations.append(optimization.component_id)
            else:
                optimization.status = "rejected"
                report.rejected_optimizations.append(optimization.component_id)

            # Check cumulative progress

        except Exception as e:  # noqa: BLE001 - catch all for error reporting
            optimization.status = "rejected"
            optimization.decision_rationale = f"Evaluation error: {e}"
            report.rejected_optimizations.append(optimization.component_id)

        # Check stopping criteria
        if (
            stop_on_goal_achieved
            and report.cumulative_improvement_percent >= goal_improvement_percent
        ):
            report.goal_achieved = True
            report.stop_reason = (
                f"Goal achieved: {report.cumulative_improvement_percent:.2f}% "
                f">= {goal_improvement_percent}%"
            )
            # Mark remaining as skipped
            for remaining in sorted_optimizations[idx + 1 :]:
                report.skipped_optimizations.append(remaining.component_id)
            break

        # Check for diminishing returns
        if not report.should_continue_evaluation():
            break

    # Generate executive summary
    report.executive_summary = _generate_executive_summary(report)
    report.detailed_findings = _generate_detailed_findings(report)

    # Save report
    _save_performance_report(report, output_dir)

    return report


def _generate_executive_summary(report: PerformanceReport) -> str:
    """Generate executive summary for performance report."""
    accepted = len(report.accepted_optimizations)
    rejected = len(report.rejected_optimizations)
    skipped = len(report.skipped_optimizations)
    total = accepted + rejected + skipped

    cumulative = report.cumulative_improvement_percent
    speedup = report.cumulative_speedup_ratio

    summary = f"""
SEQUENTIAL OPTIMIZATION EVALUATION SUMMARY
{'='*80}

RESULTS:
  - Optimizations Evaluated: {accepted + rejected} of {total}
  - Accepted: {accepted}
  - Rejected: {rejected}
  - Skipped: {skipped}

PERFORMANCE:
  - Cumulative Improvement: {cumulative:.2f}%
  - Cumulative Speedup: {speedup:.3f}x
  - Goal Status: {"✓ ACHIEVED" if report.goal_achieved else "✗ NOT ACHIEVED"}

STOPPING REASON: {report.stop_reason or "All optimizations evaluated"}

ACCEPTED OPTIMIZATIONS:
"""

    for comp_id in report.accepted_optimizations:
        comp = next((c for c in report.components if c.component_id == comp_id), None)
        if comp and comp.improvement_percent:
            summary += f"  - {comp.component_name}: {comp.improvement_percent:.2f}% improvement\n"

    if report.rejected_optimizations:
        summary += "\nREJECTED OPTIMIZATIONS:\n"
        for comp_id in report.rejected_optimizations:
            comp = next((c for c in report.components if c.component_id == comp_id), None)
            if comp:
                summary += f"  - {comp.component_name}: {comp.decision_rationale}\n"

    return summary


def _generate_detailed_findings(report: PerformanceReport) -> str:
    """Generate detailed findings for performance report."""
    findings = "DETAILED EVALUATION FINDINGS\n"
    findings += "=" * 80 + "\n\n"

    for comp in report.components:
        findings += f"\n## {comp.component_name} (ID: {comp.component_id})\n"
        findings += f"   Priority Rank: #{comp.priority_rank}\n"
        findings += f"   Status: {comp.status.upper()}\n"

        if comp.baseline_results and comp.optimized_results:
            findings += f"   Baseline Mean: {comp.baseline_results.execution_time_mean:.3f}s\n"
            findings += f"   Optimized Mean: {comp.optimized_results.execution_time_mean:.3f}s\n"

        if comp.improvement_percent:
            findings += f"   Improvement: {comp.improvement_percent:.2f}%\n"
            findings += f"   Speedup: {comp.speedup_ratio:.3f}x\n"

        if comp.decision_rationale:
            findings += f"   Decision: {comp.decision_rationale}\n"

        findings += "\n"

    return findings


def _save_performance_report(report: PerformanceReport, output_dir: str) -> None:
    """Save PerformanceReport to JSON file."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    report_file = output_path / f"{report.report_id}_report.json"

    data = {
        "report_id": report.report_id,
        "report_date": report.report_date,
        "workflow_type": report.workflow_type,
        "cumulative_improvement_percent": str(report.cumulative_improvement_percent),
        "cumulative_speedup_ratio": str(report.cumulative_speedup_ratio),
        "goal_achieved": report.goal_achieved,
        "stop_reason": report.stop_reason,
        "accepted_optimizations": report.accepted_optimizations,
        "rejected_optimizations": report.rejected_optimizations,
        "skipped_optimizations": report.skipped_optimizations,
        "executive_summary": report.executive_summary,
        "detailed_findings": report.detailed_findings,
    }

    report_file.write_text(json.dumps(data, indent=2))

    # Also save as markdown
    md_file = output_path / f"{report.report_id}_report.md"
    md_content = f"""# Performance Optimization Evaluation Report

{report.executive_summary}

{report.detailed_findings}

---
Report ID: {report.report_id}
Generated: {report.report_date}
"""
    md_file.write_text(md_content)
