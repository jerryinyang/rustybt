"""
Performance threshold evaluation utilities.

This module provides tools for creating and evaluating performance thresholds
to determine whether optimizations meet acceptance criteria.

Constitutional requirements:
- CR-001: Decimal precision for all metrics
- CR-002: Real statistical tests, no mocks
- CR-004: Complete type hints
- CR-005: Property-based tests for statistical calculations
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

import scipy.stats as stats

from .exceptions import InsufficientDataError, ThresholdEvaluationError
from .models import BenchmarkResult, BenchmarkResultSet, PerformanceThreshold


def create_threshold(
    min_improvement_percent: Decimal,
    workflow_type: str = "grid_search",
    dataset_size_category: str = "production",
    statistical_confidence: Decimal = Decimal("0.95"),
    min_sample_size: int = 10,
    max_memory_increase_percent: Decimal = Decimal("2.0"),
    rationale: str = "",
) -> PerformanceThreshold:
    """
    Create a PerformanceThreshold configuration.

    Args:
        min_improvement_percent: Minimum % improvement required (e.g., Decimal('5.0'))
        workflow_type: Type of workflow ('grid_search', 'walk_forward', 'single_backtest')
        dataset_size_category: Dataset size ('small', 'medium', 'large', 'production')
        statistical_confidence: Required confidence level (e.g., Decimal('0.95') for 95%)
        min_sample_size: Minimum number of benchmark runs (default: 10)
        max_memory_increase_percent: Max acceptable memory increase % (default: 2.0 = 2%)
        rationale: Explanation for why this threshold was chosen

    Returns:
        PerformanceThreshold instance

    Raises:
        ValueError: If parameters are invalid (via PerformanceThreshold validation)

    Examples:
        >>> threshold = create_threshold(
        ...     min_improvement_percent=Decimal('5.0'),
        ...     workflow_type='grid_search',
        ...     rationale="5% threshold balances measurability with achievability"
        ... )
    """
    # Auto-generate rationale if not provided
    if not rationale:
        rationale = (
            f"{min_improvement_percent}% minimum improvement for {workflow_type} "
            f"on {dataset_size_category} dataset with {statistical_confidence} confidence"
        )

    return PerformanceThreshold(
        min_improvement_percent=min_improvement_percent,
        workflow_type=workflow_type,
        dataset_size_category=dataset_size_category,
        statistical_confidence=statistical_confidence,
        min_sample_size=min_sample_size,
        max_memory_increase_percent=max_memory_increase_percent,
        rationale=rationale,
        created_date=datetime.utcnow().isoformat() + "Z",
    )


def evaluate_threshold(
    baseline_results: BenchmarkResultSet,
    optimized_results: BenchmarkResultSet,
    threshold: PerformanceThreshold,
    include_details: bool = True,
) -> dict[str, Any]:
    """
    Evaluate whether optimized results meet performance threshold.

    This performs comprehensive statistical analysis including:
    - Sample size validation
    - Mean improvement calculation
    - Statistical significance testing (t-test)
    - Confidence interval analysis
    - Memory overhead validation

    Args:
        baseline_results: Baseline benchmark results
        optimized_results: Optimized benchmark results
        threshold: Performance threshold to evaluate against
        include_details: Include detailed metrics in result (default: True)

    Returns:
        Dictionary with evaluation results:
        {
            'passes_threshold': bool,
            'improvement_percent': Decimal,
            'speedup_ratio': Decimal,
            'statistical_significance': bool,
            'p_value': float,
            'baseline_mean': Decimal,
            'optimized_mean': Decimal,
            'baseline_ci_95': tuple[Decimal, Decimal],
            'optimized_ci_95': tuple[Decimal, Decimal],
            'memory_overhead_ratio': Decimal,
            'passes_memory_check': bool,
            'sample_size_sufficient': bool,
            'decision_rationale': str
        }

    Raises:
        ThresholdEvaluationError: If evaluation cannot be performed
        InsufficientDataError: If insufficient samples for statistical validity

    Examples:
        >>> # Assuming baseline_results and optimized_results exist
        >>> threshold = create_threshold(Decimal('5.0'))
        >>> result = evaluate_threshold(baseline_results, optimized_results, threshold)
        >>> if result['passes_threshold']:
        ...     print(f"Optimization accepted: {result['improvement_percent']}% improvement")
    """
    # Validate sample sizes
    if baseline_results.sample_size < threshold.min_sample_size:
        raise InsufficientDataError(
            f"Baseline has {baseline_results.sample_size} samples, "
            f"need {threshold.min_sample_size}"
        )

    if optimized_results.sample_size < threshold.min_sample_size:
        raise InsufficientDataError(
            f"Optimized has {optimized_results.sample_size} samples, "
            f"need {threshold.min_sample_size}"
        )

    # Calculate means
    baseline_mean = baseline_results.execution_time_mean
    optimized_mean = optimized_results.execution_time_mean

    # Calculate improvement
    improvement_percent = ((baseline_mean - optimized_mean) / baseline_mean) * 100
    speedup_ratio = baseline_mean / optimized_mean

    # Statistical significance test (paired t-test for before/after matched runs)
    baseline_times = [r.execution_time_seconds for r in baseline_results.results]
    optimized_times = [r.execution_time_seconds for r in optimized_results.results]

    # Verify equal sample sizes for paired test
    if len(baseline_times) != len(optimized_times):
        raise ThresholdEvaluationError(
            f"Paired t-test requires equal sample sizes: baseline={len(baseline_times)}, "
            f"optimized={len(optimized_times)}"
        )

    # Convert Decimal to float for scipy
    baseline_times_float = [float(t) for t in baseline_times]
    optimized_times_float = [float(t) for t in optimized_times]

    # One-tailed paired t-test (optimized should be faster than matched baseline)
    _t_statistic, p_value = stats.ttest_rel(
        baseline_times_float, optimized_times_float, alternative="greater"  # baseline > optimized
    )

    # Confidence level for significance
    alpha = 1 - float(threshold.statistical_confidence)
    statistical_significance = p_value < alpha

    # Confidence intervals
    baseline_ci_95 = baseline_results.execution_time_ci_95
    optimized_ci_95 = optimized_results.execution_time_ci_95

    # Memory increase percentage check
    # Handle edge case where baseline memory is 0
    # (e.g., trivial workloads or disabled memory profiling)
    if baseline_results.memory_peak_max == 0:
        # If baseline is 0, check if optimized is also near-zero (within 1MB threshold)
        passes_memory_check = optimized_results.memory_peak_max <= Decimal("1.0")
        memory_increase_percent = (
            Decimal("0") if optimized_results.memory_peak_max == 0 else Decimal("inf")
        )
    else:
        memory_increase_percent = (
            (optimized_results.memory_peak_max - baseline_results.memory_peak_max)
            / baseline_results.memory_peak_max
        ) * 100
        passes_memory_check = memory_increase_percent <= threshold.max_memory_increase_percent

    # Overall decision
    passes_improvement = improvement_percent >= threshold.min_improvement_percent
    sample_size_sufficient = True  # Already validated above

    passes_threshold = (
        passes_improvement
        and statistical_significance
        and passes_memory_check
        and sample_size_sufficient
    )

    # Generate decision rationale
    decision_rationale = _generate_decision_rationale(
        passes_threshold=passes_threshold,
        improvement_percent=improvement_percent,
        threshold_min=threshold.min_improvement_percent,
        statistical_significance=statistical_significance,
        p_value=p_value,
        passes_memory_check=passes_memory_check,
        memory_increase_percent=memory_increase_percent,
        max_memory_increase_percent=threshold.max_memory_increase_percent,
    )

    result = {
        "passes_threshold": passes_threshold,
        "improvement_percent": improvement_percent,
        "speedup_ratio": speedup_ratio,
        "statistical_significance": statistical_significance,
        "p_value": p_value,
        "decision_rationale": decision_rationale,
    }

    if include_details:
        result.update(
            {
                "baseline_mean": baseline_mean,
                "optimized_mean": optimized_mean,
                "baseline_ci_95": baseline_ci_95,
                "optimized_ci_95": optimized_ci_95,
                "baseline_std": baseline_results.execution_time_std,
                "optimized_std": optimized_results.execution_time_std,
                "memory_increase_percent": memory_increase_percent,
                "baseline_memory_peak": baseline_results.memory_peak_max,
                "optimized_memory_peak": optimized_results.memory_peak_max,
                "passes_memory_check": passes_memory_check,
                "sample_size_sufficient": sample_size_sufficient,
                "baseline_sample_size": baseline_results.sample_size,
                "optimized_sample_size": optimized_results.sample_size,
            }
        )

    return result


def _generate_decision_rationale(
    passes_threshold: bool,
    improvement_percent: Decimal,
    threshold_min: Decimal,
    statistical_significance: bool,
    p_value: float,
    passes_memory_check: bool,
    memory_increase_percent: Decimal,
    max_memory_increase_percent: Decimal,
) -> str:
    """
    Generate human-readable decision rationale.

    Args:
        passes_threshold: Overall pass/fail decision
        improvement_percent: Calculated improvement percentage
        threshold_min: Minimum required improvement
        statistical_significance: Whether statistically significant
        p_value: p-value from t-test
        passes_memory_check: Whether memory increase is acceptable
        memory_increase_percent: Actual memory increase percentage
        max_memory_increase_percent: Maximum allowed memory increase percentage

    Returns:
        Human-readable rationale string
    """
    if passes_threshold:
        return (
            f"ACCEPTED: {improvement_percent:.2f}% improvement exceeds "
            f"{threshold_min}% threshold with statistical significance "
            f"(p={p_value:.4f}). Memory increase {memory_increase_percent:.2f}% "
            f"is within {max_memory_increase_percent}% limit."
        )
    else:
        reasons = []

        if improvement_percent < threshold_min:
            reasons.append(
                f"improvement {improvement_percent:.2f}% below {threshold_min}% threshold"
            )

        if not statistical_significance:
            reasons.append(f"not statistically significant (p={p_value:.4f})")

        if not passes_memory_check:
            reasons.append(
                f"memory increase {memory_increase_percent:.2f}% exceeds "
                f"{max_memory_increase_percent}% limit"
            )

        return f"REJECTED: {'; '.join(reasons)}"


def validate_threshold_configuration(threshold: PerformanceThreshold) -> list[str]:
    """
    Validate that threshold configuration is reasonable.

    Checks for common issues like overly strict or lenient thresholds.

    Args:
        threshold: Threshold configuration to validate

    Returns:
        List of warning messages (empty if no issues)

    Examples:
        >>> threshold = create_threshold(Decimal('1.0'))  # Very low threshold
        >>> warnings = validate_threshold_configuration(threshold)
        >>> if warnings:
        ...     print("Warnings:", warnings)
    """
    warnings = []

    # Check if improvement threshold is too low (noise level)
    if threshold.min_improvement_percent < Decimal("2.0"):
        warnings.append(
            f"Improvement threshold {threshold.min_improvement_percent}% is very low. "
            "Consider 2-5% minimum to exceed measurement noise."
        )

    # Check if improvement threshold is too high (unrealistic)
    if threshold.min_improvement_percent > Decimal("50.0"):
        warnings.append(
            f"Improvement threshold {threshold.min_improvement_percent}% is very high. "
            "This may be difficult to achieve for single optimizations."
        )

    # Check if memory increase percentage is too restrictive
    if threshold.max_memory_increase_percent < Decimal("1.0"):
        warnings.append(
            f"Memory increase threshold {threshold.max_memory_increase_percent}% "
            "is very restrictive. Most optimizations require some memory overhead."
        )

    # Check if memory increase percentage is too lenient
    if threshold.max_memory_increase_percent > Decimal("20.0"):
        warnings.append(
            f"Memory increase threshold {threshold.max_memory_increase_percent}% is very lenient. "
            "This could allow excessive memory usage."
        )

    # Check if sample size is too small for statistical power
    if threshold.min_sample_size < 10:
        warnings.append(
            f"Sample size {threshold.min_sample_size} is too small for reliable statistics. "
            "Recommend minimum 10 runs."
        )

    # Check if confidence level is reasonable
    if threshold.statistical_confidence < Decimal("0.90"):
        warnings.append(
            f"Confidence level {threshold.statistical_confidence} is low. "
            "Consider 0.95 (95%) for production decisions."
        )

    return warnings


def evaluate_against_threshold(
    result: "BenchmarkResult",
    threshold: PerformanceThreshold,
) -> tuple[bool, dict]:
    """Evaluate a single BenchmarkResult against a performance threshold.

    Args:
        result: BenchmarkResult to evaluate
        threshold: Performance threshold to check against

    Returns:
        Tuple of (passed, details) where:
        - passed: bool indicating if result meets threshold
        - details: dict with evaluation details
    """
    passed = (
        result.improvement_percent >= threshold.min_improvement_percent
        and result.p_value < threshold.significance_level
    )

    details = {
        "improvement_percent": float(result.improvement_percent),
        "min_required": float(threshold.min_improvement_percent),
        "p_value": result.p_value,
        "significance_level": threshold.significance_level,
        "speedup_ratio": float(result.speedup_ratio),
    }

    return passed, details
