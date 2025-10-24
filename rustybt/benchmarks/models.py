"""
Data models for performance benchmarking and optimization.

All entities use Decimal for financial-grade precision and are immutable
(frozen dataclasses) to ensure type safety and prevent accidental mutations.

Constitutional Requirements:
- CR-001: Decimal Financial Computing - All metrics use Decimal type
- CR-002: Zero-Mock Enforcement - All data from real execution
- CR-004: Type Safety Excellence - 100% type hints, frozen dataclasses
- CR-005: Test-Driven Development - Property-based tests for calculations
"""

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal


@dataclass(frozen=True)
class PerformanceThreshold:
    """Performance threshold configuration for optimization evaluation."""

    # Threshold Configuration
    min_improvement_percent: Decimal  # Minimum % improvement (e.g., Decimal('5.0'))
    workflow_type: Literal["grid_search", "walk_forward", "single_backtest"]
    dataset_size_category: Literal["small", "medium", "large", "production"]

    # Decision Parameters
    statistical_confidence: Decimal  # Required confidence level (e.g., Decimal('0.95'))
    min_sample_size: int  # Minimum benchmark runs (e.g., 10)
    max_memory_increase_percent: (
        Decimal  # Max acceptable memory increase % (e.g., Decimal('2.0') = 2%)
    )

    # Metadata
    rationale: str  # Why this threshold chosen
    created_date: str  # ISO 8601 timestamp

    def __post_init__(self) -> None:
        """Validate threshold parameters."""
        if self.min_improvement_percent <= 0:
            raise ValueError("min_improvement_percent must be positive")
        if not (Decimal("0.5") <= self.statistical_confidence <= Decimal("0.99")):
            raise ValueError("statistical_confidence must be in range [0.5, 0.99]")
        if self.min_sample_size < 10:
            raise ValueError("min_sample_size must be >= 10 for statistical validity")
        if self.max_memory_increase_percent < 0:
            raise ValueError("max_memory_increase_percent must be non-negative")
        if self.max_memory_increase_percent > 50:
            raise ValueError(
                "max_memory_increase_percent should not exceed 50% (unreasonable threshold)"
            )

    @property
    def significance_level(self) -> float:
        """Compute significance level (alpha) from statistical confidence.

        For example: 95% confidence (0.95) → 5% significance level (0.05)

        Returns:
            Significance level as float (1 - statistical_confidence)
        """
        return float(1 - self.statistical_confidence)


@dataclass(frozen=True)
class BenchmarkResult:
    """Performance metrics for a single benchmark run."""

    # Identification
    benchmark_id: str  # Unique identifier (e.g., "grid_search_baseline_run001")
    configuration_name: str  # e.g., "baseline_python", "batch_init_optimized"
    iteration_number: int  # Run number (for statistical aggregation)

    # Performance Metrics
    execution_time_seconds: Decimal  # Total wall-clock time
    cpu_time_seconds: Decimal  # Actual CPU time used
    memory_peak_mb: Decimal  # Peak memory usage
    memory_average_mb: Decimal  # Average memory during execution

    # Workload Characteristics
    dataset_size: int  # Number of bars/rows processed
    parameter_combinations: int  # For optimization workflows (Grid/WF)
    backtest_count: int  # Number of backtests executed

    # Platform Information
    platform: str  # e.g., "darwin", "linux", "win32"
    cpu_model: str  # e.g., "Apple M1 Pro"
    python_version: str  # e.g., "3.12.0"

    # Statistical Metadata
    timestamp: str  # ISO 8601 run timestamp
    random_seed: int | None  # For reproducibility

    # Profiling Data (optional)
    flame_graph_path: str | None  # Path to flame graph visualization
    profiling_json_path: str | None  # Path to raw profiling data

    def __post_init__(self) -> None:
        """Validate benchmark result parameters."""
        if self.execution_time_seconds < 0 or self.cpu_time_seconds < 0:
            raise ValueError("Time metrics must be non-negative")
        if self.memory_peak_mb < 0 or self.memory_average_mb < 0:
            raise ValueError("Memory metrics must be non-negative")
        if self.iteration_number < 1:
            raise ValueError("iteration_number must be >= 1")
        if self.dataset_size <= 0 or self.parameter_combinations <= 0 or self.backtest_count <= 0:
            raise ValueError("Workload characteristics must be positive")


@dataclass
class BenchmarkResultSet:
    """Statistical aggregation of multiple benchmark runs."""

    # Identification
    configuration_name: str  # e.g., "batch_init_optimized"
    workflow_type: str  # e.g., "grid_search"

    # Raw Results
    results: list[BenchmarkResult] = field(default_factory=list)

    # Statistical Summary (computed properties)
    @property
    def execution_time_mean(self) -> Decimal:
        """Mean execution time across all runs."""
        if not self.results:
            raise ValueError("No results available for mean calculation")
        return Decimal(sum(r.execution_time_seconds for r in self.results)) / len(self.results)

    @property
    def execution_time_std(self) -> Decimal:
        """Standard deviation of execution time."""
        if not self.results:
            raise ValueError("No results available for std calculation")
        mean = self.execution_time_mean
        variance = sum((r.execution_time_seconds - mean) ** 2 for r in self.results) / len(
            self.results
        )
        # Decimal sqrt requires conversion
        return Decimal(str(float(variance) ** 0.5))

    @property
    def execution_time_ci_95(self) -> tuple[Decimal, Decimal]:
        """95% confidence interval for execution time."""
        if not self.results:
            raise ValueError("No results available for CI calculation")
        mean = self.execution_time_mean
        std = self.execution_time_std
        n = len(self.results)
        margin = Decimal(str(1.96)) * std / Decimal(str(math.sqrt(n)))  # z-score for 95% CI
        return (mean - margin, mean + margin)

    @property
    def memory_peak_max(self) -> Decimal:
        """Maximum peak memory across all runs."""
        if not self.results:
            raise ValueError("No results available for memory calculation")
        return max(r.memory_peak_mb for r in self.results)

    @property
    def sample_size(self) -> int:
        """Number of benchmark runs."""
        return len(self.results)

    def meets_threshold(
        self, baseline: "BenchmarkResultSet", threshold: PerformanceThreshold
    ) -> bool:
        """
        Evaluate if this result set meets performance threshold compared to baseline.

        Returns:
            True if improvement >= threshold.min_improvement_percent with required confidence
        """
        if self.sample_size < threshold.min_sample_size:
            return False  # Insufficient samples

        baseline_mean = baseline.execution_time_mean
        optimized_mean = self.execution_time_mean
        improvement_percent = ((baseline_mean - optimized_mean) / baseline_mean) * 100

        # Check if improvement meets minimum
        if improvement_percent < threshold.min_improvement_percent:
            return False

        # Check memory increase percentage
        memory_increase_percent = (
            (self.memory_peak_max - baseline.memory_peak_max) / baseline.memory_peak_max
        ) * 100
        if memory_increase_percent > threshold.max_memory_increase_percent:
            return False

        # Statistical significance (simplified: CI doesn't overlap baseline mean)
        _ci_lower, ci_upper = self.execution_time_ci_95
        return ci_upper < baseline_mean  # Optimized CI entirely below baseline mean


@dataclass
class OptimizationComponent:
    """Represents an optimization implementation with benchmarks."""

    # Identification
    component_id: str  # Unique identifier (e.g., "batch_init_v1")
    component_name: str  # Display name (e.g., "Batch Initialization Optimization")
    implementation_type: Literal["rust", "python", "cython", "numba", "hybrid"]
    functional_category: Literal[
        "batch_initialization",
        "parallel_coordination",
        "dataportal_caching",
        "search_algorithm",
        "orchestration_loop",
        "micro_operation",
    ]

    # Priority Ranking (for sequential evaluation)
    priority_rank: int  # 1 = highest priority, 5 = lowest (from research.md)
    expected_impact_range: tuple[Decimal, Decimal]  # e.g., (Decimal('10'), Decimal('15'))
    complexity_level: Literal["low", "medium", "high", "very_high"]
    consistency_risk_level: Literal["low", "medium", "high", "very_high"]

    # Implementation Details
    source_file_path: str  # e.g., "rustybt/performance/batch_init.py"
    api_signature: str  # Function/class signature for documentation
    dependencies: list[str]  # e.g., ["multiprocessing.shared_memory", "polars"]

    # Benchmark Association
    baseline_results: BenchmarkResultSet | None  # Pure Python baseline
    optimized_results: BenchmarkResultSet | None  # Optimized implementation

    # Decision
    status: Literal[
        "proposed",
        "in_progress",
        "implemented",
        "validating",
        "accepted",
        "rejected",
        "skipped",
        "baseline",
    ]
    decision_rationale: str | None  # Why accepted/rejected/skipped

    # Metadata
    created_date: str  # ISO 8601
    last_updated: str  # ISO 8601
    evaluation_order: int | None  # Actual order evaluated (may differ from priority_rank)

    @property
    def speedup_ratio(self) -> Decimal | None:
        """
        Calculate speedup ratio (baseline / optimized).

        Returns None if either baseline or optimized results missing.
        """
        if not self.baseline_results or not self.optimized_results:
            return None
        baseline_mean = self.baseline_results.execution_time_mean
        optimized_mean = self.optimized_results.execution_time_mean
        return baseline_mean / optimized_mean

    @property
    def improvement_percent(self) -> Decimal | None:
        """
        Calculate percentage improvement.

        Returns None if speedup unavailable.
        """
        speedup = self.speedup_ratio
        if speedup is None:
            return None
        return (speedup - 1) * 100


@dataclass
class BaselineImplementation:
    """Pure Python baseline for functional equivalence testing."""

    # Identification
    baseline_id: str  # Unique identifier (e.g., "python_sma_baseline")
    function_name: str  # e.g., "python_sma"
    replaces_component: str | None  # ID of replaced component (e.g., "rust_sma")

    # Implementation
    source_file_path: str  # e.g., "rustybt/benchmarks/baseline/python_indicators.py"
    callable_reference: Callable[..., Any] | None  # Actual function object (runtime only)
    api_signature: str  # Full signature for documentation

    # Validation
    equivalence_test_path: str  # Path to test file validating equivalence
    equivalence_test_passed: bool  # Has equivalence been validated?
    numerical_tolerance: Decimal | None  # For float comparisons (None for exact match)

    # Documentation
    implementation_notes: str  # How baseline is implemented
    performance_expectation: str  # Expected performance

    # Metadata
    created_date: str  # ISO 8601


@dataclass
class PerformanceReport:
    """
    Comprehensive performance analysis and recommendations.

    For sequential optimization evaluation workflows.
    """

    # Identification
    report_id: str  # Unique identifier (e.g., "002_perf_report_20251021")
    report_date: str  # ISO 8601
    workflow_type: str  # e.g., "grid_search"

    # Components Analyzed (in priority order)
    components: list[OptimizationComponent] = field(default_factory=list)
    baseline_components: list[BaselineImplementation] = field(default_factory=list)

    # Threshold Used
    threshold: PerformanceThreshold | None = None

    # Sequential Evaluation Results
    accepted_optimizations: list[str] = field(
        default_factory=list
    )  # component_ids in evaluation order
    rejected_optimizations: list[str] = field(default_factory=list)  # component_ids
    skipped_optimizations: list[str] = field(default_factory=list)  # component_ids
    baseline_kept: list[str] = field(default_factory=list)  # baseline_ids

    # Evaluation Progress Tracking
    current_evaluation_index: int = 0  # Which optimization is being evaluated (0-indexed)
    goal_achieved: bool = False  # Whether 3-5x speedup target reached
    stop_reason: str | None = None  # Why evaluation stopped

    # Bottleneck Analysis
    bottleneck_rankings: dict[str, Decimal] = field(
        default_factory=dict
    )  # {category: % of total time}
    optimization_opportunities: list[str] = field(default_factory=list)  # Remaining opportunities

    # Supporting Data
    profiling_summary_path: str | None = None  # Path to profiling report document
    flame_graphs_directory: str | None = None  # Directory containing visualizations

    # Decision Rationale
    executive_summary: str = ""  # High-level findings and recommendations
    detailed_findings: str = ""  # Comprehensive analysis

    # Cumulative Impact Metrics
    @property
    def cumulative_improvement_percent(self) -> Decimal:
        """
        Calculate cumulative improvement from all accepted optimizations.

        NOTE: Assumes improvements are roughly additive.
        """
        total = Decimal("0")
        for comp_id in self.accepted_optimizations:
            comp = next((c for c in self.components if c.component_id == comp_id), None)
            if comp and comp.improvement_percent:
                total += comp.improvement_percent
        return total

    @property
    def cumulative_speedup_ratio(self) -> Decimal:
        """
        Calculate cumulative speedup ratio (e.g., 1.40 = 40% faster).

        Converts cumulative improvement percentage to speedup ratio.
        """
        return Decimal("1.0") + (self.cumulative_improvement_percent / Decimal("100"))

    @property
    def acceptance_rate(self) -> Decimal:
        """Percentage of evaluated optimizations that met threshold."""
        total_evaluated = len(self.accepted_optimizations) + len(self.rejected_optimizations)
        if total_evaluated == 0:
            return Decimal("0")
        return (Decimal(len(self.accepted_optimizations)) / total_evaluated) * 100

    @property
    def remaining_optimizations(self) -> list[OptimizationComponent]:
        """Optimizations not yet evaluated (sorted by priority_rank)."""
        evaluated_ids = set(
            self.accepted_optimizations + self.rejected_optimizations + self.skipped_optimizations
        )
        remaining = [c for c in self.components if c.component_id not in evaluated_ids]
        return sorted(remaining, key=lambda c: c.priority_rank)

    def should_continue_evaluation(self) -> bool:
        """
        Determine if optimization evaluation should continue.

        Stop if:
        - Goal achieved (cumulative improvement >=40%)
        - All optimizations evaluated
        - Diminishing returns (last 2 optimizations rejected)

        Returns:
            True if should continue to next optimization, False if should stop
        """
        # Check if goal achieved
        if self.cumulative_improvement_percent >= Decimal("40.0"):
            object.__setattr__(self, "goal_achieved", True)
            object.__setattr__(self, "stop_reason", "Goal achieved: cumulative improvement ≥40%")
            return False

        # Check if all evaluated
        if len(self.remaining_optimizations) == 0:
            object.__setattr__(self, "stop_reason", "All optimizations evaluated")
            return False

        # Check for diminishing returns (last 2 rejected)
        if len(self.rejected_optimizations) >= 2:
            recent_evaluations = (self.accepted_optimizations + self.rejected_optimizations)[-2:]
            if all(opt_id in self.rejected_optimizations for opt_id in recent_evaluations):
                object.__setattr__(
                    self, "stop_reason", "Diminishing returns: last 2 optimizations rejected"
                )
                return False

        return True


@dataclass
class AlternativeSolution:
    """Alternative optimization approach evaluation."""

    # Identification
    solution_id: str  # e.g., "dataportal_cache_lru"
    solution_name: str  # e.g., "LRU Cache for DataPortal Queries"
    category: Literal[
        "batch_initialization",
        "parallel_coordination",
        "dataportal_caching",
        "search_algorithm",
        "orchestration_loop",
    ]

    # Implementation
    approach_description: str  # High-level description
    technology_stack: list[str]  # e.g., ["functools.lru_cache", "polars"]
    proof_of_concept_path: str | None  # Path to POC code

    # Analysis
    expected_impact_percent: Decimal  # Estimated improvement
    implementation_complexity: Literal["low", "medium", "high", "very_high"]
    functional_consistency_risk: Literal["low", "medium", "high", "very_high"]

    # Trade-offs
    pros: list[str]
    cons: list[str]

    # Decision
    status: Literal["proposed", "selected", "rejected", "backup"]
    selection_rationale: str

    # Metadata
    proposed_date: str  # ISO 8601

    def __post_init__(self) -> None:
        """Validate alternative solution."""
        if not self.pros or not self.cons:
            raise ValueError("Both pros and cons must have at least 1 item")
