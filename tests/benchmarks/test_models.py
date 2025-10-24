"""
Unit tests for benchmarking data models.

Constitutional requirements:
- CR-002: Real test data, no mocks
- CR-004: Complete type safety
- CR-005: Property-based tests for calculations (Hypothesis)
"""

from datetime import datetime
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from rustybt.benchmarks.models import (
    AlternativeSolution,
    BaselineImplementation,
    BenchmarkResult,
    BenchmarkResultSet,
    OptimizationComponent,
    PerformanceReport,
    PerformanceThreshold,
)


class TestPerformanceThreshold:
    """Tests for PerformanceThreshold model."""

    def test_create_valid_threshold(self):
        """Test creating a valid threshold."""
        threshold = PerformanceThreshold(
            min_improvement_percent=Decimal("5.0"),
            workflow_type="grid_search",
            dataset_size_category="production",
            statistical_confidence=Decimal("0.95"),
            min_sample_size=10,
            max_memory_increase_percent=Decimal("3.0"),
            rationale="5% threshold for measurability",
            created_date="2025-10-21T10:00:00Z",
        )

        assert threshold.min_improvement_percent == Decimal("5.0")
        assert threshold.workflow_type == "grid_search"
        assert threshold.statistical_confidence == Decimal("0.95")
        assert threshold.min_sample_size == 10

    def test_threshold_validation_negative_improvement(self):
        """Test that negative improvement raises ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            PerformanceThreshold(
                min_improvement_percent=Decimal("-5.0"),
                workflow_type="grid_search",
                dataset_size_category="production",
                statistical_confidence=Decimal("0.95"),
                min_sample_size=10,
                max_memory_increase_percent=Decimal("3.0"),
                rationale="Invalid",
                created_date="2025-10-21T10:00:00Z",
            )

    def test_threshold_validation_invalid_confidence(self):
        """Test that invalid confidence raises ValueError."""
        with pytest.raises(ValueError, match="statistical_confidence must be in range"):
            PerformanceThreshold(
                min_improvement_percent=Decimal("5.0"),
                workflow_type="grid_search",
                dataset_size_category="production",
                statistical_confidence=Decimal("1.5"),  # > 0.99
                min_sample_size=10,
                max_memory_increase_percent=Decimal("3.0"),
                rationale="Invalid",
                created_date="2025-10-21T10:00:00Z",
            )

    def test_threshold_validation_small_sample_size(self):
        """Test that sample size < 10 raises ValueError."""
        with pytest.raises(ValueError, match="min_sample_size must be >= 10"):
            PerformanceThreshold(
                min_improvement_percent=Decimal("5.0"),
                workflow_type="grid_search",
                dataset_size_category="production",
                statistical_confidence=Decimal("0.95"),
                min_sample_size=5,  # < 10
                max_memory_increase_percent=Decimal("3.0"),
                rationale="Invalid",
                created_date="2025-10-21T10:00:00Z",
            )

    def test_threshold_validation_excessive_memory(self):
        """Test that memory multiplier > 50% raises ValueError."""
        with pytest.raises(ValueError, match="should not exceed 50%"):
            PerformanceThreshold(
                min_improvement_percent=Decimal("5.0"),
                workflow_type="grid_search",
                dataset_size_category="production",
                statistical_confidence=Decimal("0.95"),
                min_sample_size=10,
                max_memory_increase_percent=Decimal("60.0"),  # > 50%
                rationale="Invalid",
                created_date="2025-10-21T10:00:00Z",
            )


class TestBenchmarkResult:
    """Tests for BenchmarkResult model."""

    def test_create_valid_result(self):
        """Test creating a valid benchmark result."""
        result = BenchmarkResult(
            benchmark_id="test_run_001",
            configuration_name="baseline",
            iteration_number=1,
            execution_time_seconds=Decimal("10.5"),
            cpu_time_seconds=Decimal("10.2"),
            memory_peak_mb=Decimal("512.3"),
            memory_average_mb=Decimal("450.1"),
            dataset_size=1000,
            parameter_combinations=100,
            backtest_count=100,
            platform="darwin",
            cpu_model="Apple M1",
            python_version="3.12.0",
            timestamp="2025-10-21T10:00:00Z",
            random_seed=42,
            flame_graph_path=None,
            profiling_json_path=None,
        )

        assert result.benchmark_id == "test_run_001"
        assert result.execution_time_seconds == Decimal("10.5")
        assert result.iteration_number == 1

    def test_result_validation_negative_time(self):
        """Test that negative time raises ValueError."""
        with pytest.raises(ValueError, match="Time metrics must be non-negative"):
            BenchmarkResult(
                benchmark_id="test_run_001",
                configuration_name="baseline",
                iteration_number=1,
                execution_time_seconds=Decimal("-10.5"),  # Negative
                cpu_time_seconds=Decimal("10.2"),
                memory_peak_mb=Decimal("512.3"),
                memory_average_mb=Decimal("450.1"),
                dataset_size=1000,
                parameter_combinations=100,
                backtest_count=100,
                platform="darwin",
                cpu_model="Apple M1",
                python_version="3.12.0",
                timestamp="2025-10-21T10:00:00Z",
                random_seed=42,
                flame_graph_path=None,
                profiling_json_path=None,
            )

    def test_result_validation_invalid_iteration(self):
        """Test that iteration_number < 1 raises ValueError."""
        with pytest.raises(ValueError, match="iteration_number must be >= 1"):
            BenchmarkResult(
                benchmark_id="test_run_001",
                configuration_name="baseline",
                iteration_number=0,  # < 1
                execution_time_seconds=Decimal("10.5"),
                cpu_time_seconds=Decimal("10.2"),
                memory_peak_mb=Decimal("512.3"),
                memory_average_mb=Decimal("450.1"),
                dataset_size=1000,
                parameter_combinations=100,
                backtest_count=100,
                platform="darwin",
                cpu_model="Apple M1",
                python_version="3.12.0",
                timestamp="2025-10-21T10:00:00Z",
                random_seed=42,
                flame_graph_path=None,
                profiling_json_path=None,
            )


class TestBenchmarkResultSet:
    """Tests for BenchmarkResultSet model."""

    def create_sample_results(self, num_results=10):
        """Helper to create sample results."""
        results = []
        for i in range(1, num_results + 1):
            result = BenchmarkResult(
                benchmark_id=f"test_run_{i:03d}",
                configuration_name="baseline",
                iteration_number=i,
                execution_time_seconds=Decimal(str(10.0 + i * 0.1)),
                cpu_time_seconds=Decimal(str(9.5 + i * 0.1)),
                memory_peak_mb=Decimal(str(500 + i * 10)),
                memory_average_mb=Decimal(str(450 + i * 10)),
                dataset_size=1000,
                parameter_combinations=100,
                backtest_count=100,
                platform="darwin",
                cpu_model="Apple M1",
                python_version="3.12.0",
                timestamp=f"2025-10-21T10:{i:02d}:00Z",
                random_seed=42,
                flame_graph_path=None,
                profiling_json_path=None,
            )
            results.append(result)
        return results

    def test_create_result_set(self):
        """Test creating a result set."""
        results = self.create_sample_results(10)
        result_set = BenchmarkResultSet(
            configuration_name="baseline", workflow_type="grid_search", results=results
        )

        assert result_set.configuration_name == "baseline"
        assert result_set.sample_size == 10
        assert len(result_set.results) == 10

    def test_execution_time_mean(self):
        """Test mean calculation."""
        results = self.create_sample_results(10)
        result_set = BenchmarkResultSet(
            configuration_name="baseline", workflow_type="grid_search", results=results
        )

        # Expected mean: (10.1 + 10.2 + ... + 11.0) / 10 = 10.55
        expected_mean = Decimal("10.55")
        assert abs(result_set.execution_time_mean - expected_mean) < Decimal("0.01")

    def test_execution_time_std(self):
        """Test standard deviation calculation."""
        results = self.create_sample_results(10)
        result_set = BenchmarkResultSet(
            configuration_name="baseline", workflow_type="grid_search", results=results
        )

        # Standard deviation should be positive
        assert result_set.execution_time_std > 0

    def test_execution_time_ci_95(self):
        """Test 95% confidence interval calculation."""
        results = self.create_sample_results(10)
        result_set = BenchmarkResultSet(
            configuration_name="baseline", workflow_type="grid_search", results=results
        )

        ci_lower, ci_upper = result_set.execution_time_ci_95

        # CI should contain the mean
        assert ci_lower < result_set.execution_time_mean < ci_upper

        # CI should be symmetric around mean (approximately)
        margin_lower = result_set.execution_time_mean - ci_lower
        margin_upper = ci_upper - result_set.execution_time_mean
        assert abs(margin_lower - margin_upper) < Decimal("0.01")

    def test_memory_peak_max(self):
        """Test peak memory calculation."""
        results = self.create_sample_results(10)
        result_set = BenchmarkResultSet(
            configuration_name="baseline", workflow_type="grid_search", results=results
        )

        # Max should be from last result (510 + 10*10 = 610)
        expected_max = Decimal("600")
        assert result_set.memory_peak_max == expected_max

    def test_meets_threshold_pass(self):
        """Test threshold evaluation - passing case."""
        # Create baseline (slower)
        baseline_results = self.create_sample_results(10)
        baseline_set = BenchmarkResultSet(
            configuration_name="baseline", workflow_type="grid_search", results=baseline_results
        )

        # Create optimized (20% faster)
        optimized_results = []
        for i in range(1, 11):
            result = BenchmarkResult(
                benchmark_id=f"opt_run_{i:03d}",
                configuration_name="optimized",
                iteration_number=i,
                execution_time_seconds=Decimal(str((10.0 + i * 0.1) * 0.8)),  # 20% faster
                cpu_time_seconds=Decimal(str((9.5 + i * 0.1) * 0.8)),
                memory_peak_mb=Decimal(str(500 + i * 10)),  # Same memory
                memory_average_mb=Decimal(str(450 + i * 10)),
                dataset_size=1000,
                parameter_combinations=100,
                backtest_count=100,
                platform="darwin",
                cpu_model="Apple M1",
                python_version="3.12.0",
                timestamp=f"2025-10-21T11:{i:02d}:00Z",
                random_seed=42,
                flame_graph_path=None,
                profiling_json_path=None,
            )
            optimized_results.append(result)

        optimized_set = BenchmarkResultSet(
            configuration_name="optimized", workflow_type="grid_search", results=optimized_results
        )

        # Create threshold (5% minimum)
        threshold = PerformanceThreshold(
            min_improvement_percent=Decimal("5.0"),
            workflow_type="grid_search",
            dataset_size_category="production",
            statistical_confidence=Decimal("0.95"),
            min_sample_size=10,
            max_memory_increase_percent=Decimal("3.0"),
            rationale="Test threshold",
            created_date="2025-10-21T10:00:00Z",
        )

        # Should pass (20% improvement > 5% threshold)
        assert optimized_set.meets_threshold(baseline_set, threshold)

    def test_meets_threshold_fail_insufficient_improvement(self):
        """Test threshold evaluation - failing case (low improvement)."""
        baseline_results = self.create_sample_results(10)
        baseline_set = BenchmarkResultSet(
            configuration_name="baseline", workflow_type="grid_search", results=baseline_results
        )

        # Create optimized (only 2% faster)
        optimized_results = []
        for i in range(1, 11):
            result = BenchmarkResult(
                benchmark_id=f"opt_run_{i:03d}",
                configuration_name="optimized",
                iteration_number=i,
                execution_time_seconds=Decimal(str((10.0 + i * 0.1) * 0.98)),  # 2% faster
                cpu_time_seconds=Decimal(str((9.5 + i * 0.1) * 0.98)),
                memory_peak_mb=Decimal(str(500 + i * 10)),
                memory_average_mb=Decimal(str(450 + i * 10)),
                dataset_size=1000,
                parameter_combinations=100,
                backtest_count=100,
                platform="darwin",
                cpu_model="Apple M1",
                python_version="3.12.0",
                timestamp=f"2025-10-21T11:{i:02d}:00Z",
                random_seed=42,
                flame_graph_path=None,
                profiling_json_path=None,
            )
            optimized_results.append(result)

        optimized_set = BenchmarkResultSet(
            configuration_name="optimized", workflow_type="grid_search", results=optimized_results
        )

        threshold = PerformanceThreshold(
            min_improvement_percent=Decimal("5.0"),  # Requires 5%
            workflow_type="grid_search",
            dataset_size_category="production",
            statistical_confidence=Decimal("0.95"),
            min_sample_size=10,
            max_memory_increase_percent=Decimal("3.0"),
            rationale="Test threshold",
            created_date="2025-10-21T10:00:00Z",
        )

        # Should fail (2% improvement < 5% threshold)
        assert not optimized_set.meets_threshold(baseline_set, threshold)


class TestOptimizationComponent:
    """Tests for OptimizationComponent model."""

    def test_speedup_ratio_calculation(self):
        """Test speedup ratio property."""
        # Create baseline results
        baseline_result = BenchmarkResult(
            benchmark_id="baseline_001",
            configuration_name="baseline",
            iteration_number=1,
            execution_time_seconds=Decimal("10.0"),
            cpu_time_seconds=Decimal("9.5"),
            memory_peak_mb=Decimal("500"),
            memory_average_mb=Decimal("450"),
            dataset_size=1000,
            parameter_combinations=100,
            backtest_count=100,
            platform="darwin",
            cpu_model="Apple M1",
            python_version="3.12.0",
            timestamp="2025-10-21T10:00:00Z",
            random_seed=42,
            flame_graph_path=None,
            profiling_json_path=None,
        )

        baseline_set = BenchmarkResultSet(
            configuration_name="baseline", workflow_type="grid_search", results=[baseline_result]
        )

        # Create optimized results (2x faster)
        optimized_result = BenchmarkResult(
            benchmark_id="optimized_001",
            configuration_name="optimized",
            iteration_number=1,
            execution_time_seconds=Decimal("5.0"),  # 2x faster
            cpu_time_seconds=Decimal("4.75"),
            memory_peak_mb=Decimal("500"),
            memory_average_mb=Decimal("450"),
            dataset_size=1000,
            parameter_combinations=100,
            backtest_count=100,
            platform="darwin",
            cpu_model="Apple M1",
            python_version="3.12.0",
            timestamp="2025-10-21T11:00:00Z",
            random_seed=42,
            flame_graph_path=None,
            profiling_json_path=None,
        )

        optimized_set = BenchmarkResultSet(
            configuration_name="optimized", workflow_type="grid_search", results=[optimized_result]
        )

        # Create component
        component = OptimizationComponent(
            component_id="test_opt",
            component_name="Test Optimization",
            implementation_type="python",
            functional_category="batch_initialization",
            priority_rank=1,
            expected_impact_range=(Decimal("10"), Decimal("20")),
            complexity_level="medium",
            consistency_risk_level="low",
            source_file_path="test.py",
            api_signature="def test()",
            dependencies=[],
            baseline_results=baseline_set,
            optimized_results=optimized_set,
            status="implemented",
            decision_rationale=None,
            created_date="2025-10-21T10:00:00Z",
            last_updated="2025-10-21T10:00:00Z",
            evaluation_order=None,
        )

        # Speedup should be 2.0x
        assert component.speedup_ratio == Decimal("2.0")

        # Improvement should be 100%
        assert component.improvement_percent == Decimal("100")

    def test_speedup_ratio_none_when_missing_results(self):
        """Test that speedup_ratio returns None when results missing."""
        component = OptimizationComponent(
            component_id="test_opt",
            component_name="Test Optimization",
            implementation_type="python",
            functional_category="batch_initialization",
            priority_rank=1,
            expected_impact_range=(Decimal("10"), Decimal("20")),
            complexity_level="medium",
            consistency_risk_level="low",
            source_file_path="test.py",
            api_signature="def test()",
            dependencies=[],
            baseline_results=None,  # Missing
            optimized_results=None,  # Missing
            status="proposed",
            decision_rationale=None,
            created_date="2025-10-21T10:00:00Z",
            last_updated="2025-10-21T10:00:00Z",
            evaluation_order=None,
        )

        assert component.speedup_ratio is None
        assert component.improvement_percent is None


class TestAlternativeSolution:
    """Tests for AlternativeSolution model."""

    def test_create_alternative_solution(self):
        """Test creating an alternative solution."""
        solution = AlternativeSolution(
            solution_id="cache_lru",
            solution_name="LRU Cache",
            category="dataportal_caching",
            approach_description="Use functools.lru_cache",
            technology_stack=["functools"],
            proof_of_concept_path=None,
            expected_impact_percent=Decimal("15.0"),
            implementation_complexity="medium",
            functional_consistency_risk="high",
            pros=["Simple", "Standard library"],
            cons=["Cache invalidation risk"],
            status="proposed",
            selection_rationale="To be evaluated",
            proposed_date="2025-10-21T10:00:00Z",
        )

        assert solution.solution_id == "cache_lru"
        assert len(solution.pros) == 2
        assert len(solution.cons) == 1

    def test_alternative_solution_requires_pros_and_cons(self):
        """Test that pros and cons are required."""
        with pytest.raises(ValueError, match="pros and cons must have at least 1 item"):
            AlternativeSolution(
                solution_id="cache_lru",
                solution_name="LRU Cache",
                category="dataportal_caching",
                approach_description="Use functools.lru_cache",
                technology_stack=["functools"],
                proof_of_concept_path=None,
                expected_impact_percent=Decimal("15.0"),
                implementation_complexity="medium",
                functional_consistency_risk="high",
                pros=[],  # Empty
                cons=["Cache invalidation risk"],
                status="proposed",
                selection_rationale="To be evaluated",
                proposed_date="2025-10-21T10:00:00Z",
            )


class TestPropertyBasedStatistics:
    """Property-based tests for statistical calculations using Hypothesis (TEST-003).

    These tests validate statistical invariants that should always hold true,
    regardless of the input data. This addresses CR-005 requirement for
    property-based testing.
    """

    def create_benchmark_result(
        self, name: str, exec_time: Decimal, iteration: int = 1
    ) -> BenchmarkResult:
        """Helper to create BenchmarkResult for property tests."""
        return BenchmarkResult(
            benchmark_id=name,
            configuration_name=name,
            iteration_number=iteration,
            execution_time_seconds=exec_time,
            cpu_time_seconds=exec_time * Decimal("0.95"),
            memory_peak_mb=Decimal("100"),
            memory_average_mb=Decimal("90"),
            dataset_size=1000,
            parameter_combinations=10,
            backtest_count=10,
            platform="test",
            cpu_model="test",
            python_version="3.12.0",
            timestamp="2025-01-01T00:00:00Z",
            random_seed=None,
            flame_graph_path=None,
            profiling_json_path=None,
        )

    @given(
        execution_times=st.lists(
            st.decimals(
                min_value=Decimal("0.001"),
                max_value=Decimal("100.0"),
                allow_nan=False,
                allow_infinity=False,
            ),
            min_size=10,
            max_size=50,
        )
    )
    def test_execution_time_ci_always_contains_mean(self, execution_times):
        """Property: 95% confidence interval must always contain the mean.

        Addresses: TEST-003 (Property-based testing requirement)
        Validates: Statistical correctness of confidence interval calculation
        """
        # Create BenchmarkResults with varying execution times
        results = [
            self.create_benchmark_result(f"run_{i}", time, i + 1)
            for i, time in enumerate(execution_times)
        ]

        result_set = BenchmarkResultSet(
            configuration_name="test", workflow_type="test", results=results
        )

        # Property: Mean must be within 95% CI
        mean = result_set.execution_time_mean
        ci_lower, ci_upper = result_set.execution_time_ci_95

        assert ci_lower <= mean <= ci_upper, f"Mean {mean} not in 95% CI [{ci_lower}, {ci_upper}]"

    @given(
        baseline_time=st.decimals(
            min_value=Decimal("1.0"),
            max_value=Decimal("100.0"),
            allow_nan=False,
            allow_infinity=False,
        ),
        speedup_factor=st.decimals(
            min_value=Decimal("1.1"),
            max_value=Decimal("5.0"),
            allow_nan=False,
            allow_infinity=False,
        ),
    )
    def test_improvement_percent_matches_speedup(self, baseline_time, speedup_factor):
        """Property: improvement_percent should match speedup calculation.

        Addresses: TEST-003 (Property-based testing requirement)
        Validates: Speedup ratio and improvement percentage calculations
        """
        optimized_time = baseline_time / speedup_factor

        # Create baseline and optimized results
        baseline_result = self.create_benchmark_result("baseline", baseline_time)
        optimized_result = self.create_benchmark_result("optimized", optimized_time)

        baseline_set = BenchmarkResultSet("baseline", "test", [baseline_result])
        optimized_set = BenchmarkResultSet("optimized", "test", [optimized_result])

        component = OptimizationComponent(
            component_id="test",
            component_name="Test",
            implementation_type="python",
            functional_category="batch_initialization",
            priority_rank=1,
            expected_impact_range=(Decimal("10"), Decimal("20")),
            complexity_level="low",
            consistency_risk_level="low",
            source_file_path="test.py",
            api_signature="def test()",
            dependencies=[],
            baseline_results=baseline_set,
            optimized_results=optimized_set,
            status="implemented",
            decision_rationale=None,
            created_date="2025-01-01T00:00:00Z",
            last_updated="2025-01-01T00:00:00Z",
            evaluation_order=None,
        )

        # Property: speedup_ratio should match expected calculation
        expected_speedup = baseline_time / optimized_time
        assert abs(component.speedup_ratio - expected_speedup) < Decimal("0.01")

        # Property: improvement_percent should match (speedup - 1) * 100
        expected_improvement = (expected_speedup - Decimal("1")) * Decimal("100")
        assert abs(component.improvement_percent - expected_improvement) < Decimal("0.5")

    @given(
        values=st.lists(
            st.decimals(
                min_value=Decimal("0.001"),
                max_value=Decimal("1000.0"),
                allow_nan=False,
                allow_infinity=False,
            ),
            min_size=2,
            max_size=50,
        )
    )
    def test_std_is_non_negative(self, values):
        """Property: Standard deviation must always be >= 0.

        Addresses: TEST-003 (Property-based testing requirement)
        Validates: Standard deviation calculation correctness
        """
        results = [
            self.create_benchmark_result(f"run_{i}", val, i + 1) for i, val in enumerate(values)
        ]
        result_set = BenchmarkResultSet("test", "test", results)

        # Property: Standard deviation is always non-negative
        assert result_set.execution_time_std >= 0

        # Additional property: If all values are the same, std should be 0
        if len(set(values)) == 1:
            assert result_set.execution_time_std == 0 or result_set.execution_time_std < Decimal(
                "0.0001"
            )


class TestBenchmarkResultSetErrorHandling:
    """Tests for BenchmarkResultSet error handling with empty results."""

    def test_execution_time_mean_empty_results_raises_error(self):
        """Test that mean calculation raises ValueError for empty results."""
        result_set = BenchmarkResultSet(
            configuration_name="empty", workflow_type="test", results=[]
        )

        with pytest.raises(ValueError, match="No results available for mean calculation"):
            _ = result_set.execution_time_mean

    def test_execution_time_std_empty_results_raises_error(self):
        """Test that std calculation raises ValueError for empty results."""
        result_set = BenchmarkResultSet(
            configuration_name="empty", workflow_type="test", results=[]
        )

        with pytest.raises(ValueError, match="No results available for std calculation"):
            _ = result_set.execution_time_std

    def test_execution_time_ci_95_empty_results_raises_error(self):
        """Test that CI calculation raises ValueError for empty results."""
        result_set = BenchmarkResultSet(
            configuration_name="empty", workflow_type="test", results=[]
        )

        with pytest.raises(ValueError, match="No results available for CI calculation"):
            _ = result_set.execution_time_ci_95

    def test_memory_peak_max_empty_results_raises_error(self):
        """Test that memory peak calculation raises ValueError for empty results."""
        result_set = BenchmarkResultSet(
            configuration_name="empty", workflow_type="test", results=[]
        )

        with pytest.raises(ValueError, match="No results available for memory calculation"):
            _ = result_set.memory_peak_max

    def test_sample_size_empty_results_returns_zero(self):
        """Test that sample_size returns 0 for empty results."""
        result_set = BenchmarkResultSet(
            configuration_name="empty", workflow_type="test", results=[]
        )

        assert result_set.sample_size == 0


class TestPerformanceThresholdEdgeCases:
    """Additional edge case tests for PerformanceThreshold validation."""

    def test_negative_memory_increase_raises_error(self):
        """Test that negative max_memory_increase_percent raises ValueError."""
        with pytest.raises(ValueError, match="max_memory_increase_percent must be non-negative"):
            PerformanceThreshold(
                min_improvement_percent=Decimal("5.0"),
                workflow_type="grid_search",
                dataset_size_category="production",
                statistical_confidence=Decimal("0.95"),
                min_sample_size=10,
                max_memory_increase_percent=Decimal("-1.0"),  # Negative
                rationale="Invalid",
                created_date="2025-10-21T10:00:00Z",
            )

    def test_confidence_at_lower_boundary(self):
        """Test threshold with confidence at lower boundary (0.5)."""
        threshold = PerformanceThreshold(
            min_improvement_percent=Decimal("5.0"),
            workflow_type="grid_search",
            dataset_size_category="production",
            statistical_confidence=Decimal("0.5"),  # Exactly at lower boundary
            min_sample_size=10,
            max_memory_increase_percent=Decimal("3.0"),
            rationale="Low confidence test",
            created_date="2025-10-21T10:00:00Z",
        )

        assert threshold.statistical_confidence == Decimal("0.5")
        assert threshold.significance_level == 0.5

    def test_confidence_at_upper_boundary(self):
        """Test threshold with confidence at upper boundary (0.99)."""
        threshold = PerformanceThreshold(
            min_improvement_percent=Decimal("5.0"),
            workflow_type="grid_search",
            dataset_size_category="production",
            statistical_confidence=Decimal("0.99"),  # Exactly at upper boundary
            min_sample_size=10,
            max_memory_increase_percent=Decimal("3.0"),
            rationale="High confidence test",
            created_date="2025-10-21T10:00:00Z",
        )

        assert threshold.statistical_confidence == Decimal("0.99")
        assert abs(threshold.significance_level - 0.01) < 0.001

    def test_confidence_below_lower_boundary_raises_error(self):
        """Test that confidence < 0.5 raises ValueError."""
        with pytest.raises(ValueError, match="statistical_confidence must be in range"):
            PerformanceThreshold(
                min_improvement_percent=Decimal("5.0"),
                workflow_type="grid_search",
                dataset_size_category="production",
                statistical_confidence=Decimal("0.49"),  # Below 0.5
                min_sample_size=10,
                max_memory_increase_percent=Decimal("3.0"),
                rationale="Invalid",
                created_date="2025-10-21T10:00:00Z",
            )

    def test_memory_increase_at_boundary_50_percent(self):
        """Test max_memory_increase_percent exactly at 50%."""
        threshold = PerformanceThreshold(
            min_improvement_percent=Decimal("5.0"),
            workflow_type="grid_search",
            dataset_size_category="production",
            statistical_confidence=Decimal("0.95"),
            min_sample_size=10,
            max_memory_increase_percent=Decimal("50.0"),  # Exactly at boundary
            rationale="Max memory test",
            created_date="2025-10-21T10:00:00Z",
        )

        assert threshold.max_memory_increase_percent == Decimal("50.0")


class TestPerformanceReport:
    """Tests for PerformanceReport model and methods."""

    def create_sample_component(self, component_id: str, improvement: Decimal, status: str):
        """Helper to create OptimizationComponent."""
        # Create baseline result
        baseline_result = BenchmarkResult(
            benchmark_id=f"{component_id}_baseline",
            configuration_name="baseline",
            iteration_number=1,
            execution_time_seconds=Decimal("10.0"),
            cpu_time_seconds=Decimal("9.5"),
            memory_peak_mb=Decimal("500"),
            memory_average_mb=Decimal("450"),
            dataset_size=1000,
            parameter_combinations=100,
            backtest_count=100,
            platform="darwin",
            cpu_model="Apple M1",
            python_version="3.12.0",
            timestamp="2025-10-21T10:00:00Z",
            random_seed=42,
            flame_graph_path=None,
            profiling_json_path=None,
        )

        # Create optimized result
        speedup = Decimal("1.0") + (improvement / Decimal("100"))
        optimized_time = Decimal("10.0") / speedup

        optimized_result = BenchmarkResult(
            benchmark_id=f"{component_id}_optimized",
            configuration_name="optimized",
            iteration_number=1,
            execution_time_seconds=optimized_time,
            cpu_time_seconds=optimized_time * Decimal("0.95"),
            memory_peak_mb=Decimal("500"),
            memory_average_mb=Decimal("450"),
            dataset_size=1000,
            parameter_combinations=100,
            backtest_count=100,
            platform="darwin",
            cpu_model="Apple M1",
            python_version="3.12.0",
            timestamp="2025-10-21T11:00:00Z",
            random_seed=42,
            flame_graph_path=None,
            profiling_json_path=None,
        )

        baseline_set = BenchmarkResultSet("baseline", "test", [baseline_result])
        optimized_set = BenchmarkResultSet("optimized", "test", [optimized_result])

        return OptimizationComponent(
            component_id=component_id,
            component_name=f"Test Component {component_id}",
            implementation_type="python",
            functional_category="batch_initialization",
            priority_rank=int(component_id.split("_")[-1]),
            expected_impact_range=(Decimal("10"), Decimal("20")),
            complexity_level="medium",
            consistency_risk_level="low",
            source_file_path="test.py",
            api_signature="def test()",
            dependencies=[],
            baseline_results=baseline_set,
            optimized_results=optimized_set,
            status=status,
            decision_rationale=None,
            created_date="2025-10-21T10:00:00Z",
            last_updated="2025-10-21T10:00:00Z",
            evaluation_order=None,
        )

    def test_cumulative_improvement_percent(self):
        """Test cumulative improvement calculation."""
        component1 = self.create_sample_component("opt_1", Decimal("15"), "accepted")
        component2 = self.create_sample_component("opt_2", Decimal("10"), "accepted")
        component3 = self.create_sample_component("opt_3", Decimal("5"), "rejected")

        report = PerformanceReport(
            report_id="test_report",
            report_date="2025-10-21T10:00:00Z",
            workflow_type="grid_search",
            components=[component1, component2, component3],
            accepted_optimizations=["opt_1", "opt_2"],
            rejected_optimizations=["opt_3"],
        )

        # Cumulative improvement should be 15% + 10% = 25%
        assert abs(report.cumulative_improvement_percent - Decimal("25.0")) < Decimal("1.0")

    def test_cumulative_speedup_ratio(self):
        """Test cumulative speedup ratio calculation."""
        component1 = self.create_sample_component("opt_1", Decimal("20"), "accepted")

        report = PerformanceReport(
            report_id="test_report",
            report_date="2025-10-21T10:00:00Z",
            workflow_type="grid_search",
            components=[component1],
            accepted_optimizations=["opt_1"],
        )

        # Speedup should be 1.0 + 20/100 = 1.2
        assert abs(report.cumulative_speedup_ratio - Decimal("1.2")) < Decimal("0.05")

    def test_acceptance_rate_no_evaluations(self):
        """Test acceptance rate when no optimizations evaluated."""
        report = PerformanceReport(
            report_id="test_report", report_date="2025-10-21T10:00:00Z", workflow_type="grid_search"
        )

        assert report.acceptance_rate == Decimal("0")

    def test_acceptance_rate_all_accepted(self):
        """Test acceptance rate when all accepted."""
        component1 = self.create_sample_component("opt_1", Decimal("15"), "accepted")
        component2 = self.create_sample_component("opt_2", Decimal("10"), "accepted")

        report = PerformanceReport(
            report_id="test_report",
            report_date="2025-10-21T10:00:00Z",
            workflow_type="grid_search",
            components=[component1, component2],
            accepted_optimizations=["opt_1", "opt_2"],
        )

        # 2 accepted / 2 total = 100%
        assert report.acceptance_rate == Decimal("100.0")

    def test_acceptance_rate_mixed(self):
        """Test acceptance rate with mixed results."""
        component1 = self.create_sample_component("opt_1", Decimal("15"), "accepted")
        component2 = self.create_sample_component("opt_2", Decimal("10"), "accepted")
        component3 = self.create_sample_component("opt_3", Decimal("5"), "rejected")
        component4 = self.create_sample_component("opt_4", Decimal("3"), "rejected")

        report = PerformanceReport(
            report_id="test_report",
            report_date="2025-10-21T10:00:00Z",
            workflow_type="grid_search",
            components=[component1, component2, component3, component4],
            accepted_optimizations=["opt_1", "opt_2"],
            rejected_optimizations=["opt_3", "opt_4"],
        )

        # 2 accepted / 4 total = 50%
        assert report.acceptance_rate == Decimal("50.0")

    def test_remaining_optimizations(self):
        """Test remaining optimizations calculation."""
        component1 = self.create_sample_component("opt_1", Decimal("15"), "accepted")
        component2 = self.create_sample_component("opt_2", Decimal("10"), "proposed")
        component3 = self.create_sample_component("opt_3", Decimal("5"), "proposed")

        report = PerformanceReport(
            report_id="test_report",
            report_date="2025-10-21T10:00:00Z",
            workflow_type="grid_search",
            components=[component1, component2, component3],
            accepted_optimizations=["opt_1"],
        )

        remaining = report.remaining_optimizations

        # Should have 2 remaining (opt_2, opt_3)
        assert len(remaining) == 2
        assert all(c.component_id in ["opt_2", "opt_3"] for c in remaining)

        # Should be sorted by priority_rank
        assert remaining[0].priority_rank <= remaining[1].priority_rank

    def test_should_continue_evaluation_goal_achieved(self):
        """Test should_continue_evaluation stops when goal achieved (≥40%)."""
        component1 = self.create_sample_component("opt_1", Decimal("45"), "accepted")

        report = PerformanceReport(
            report_id="test_report",
            report_date="2025-10-21T10:00:00Z",
            workflow_type="grid_search",
            components=[component1],
            accepted_optimizations=["opt_1"],
        )

        # Should stop (45% >= 40%)
        assert not report.should_continue_evaluation()
        assert report.goal_achieved
        assert "Goal achieved" in report.stop_reason

    def test_should_continue_evaluation_all_evaluated(self):
        """Test should_continue_evaluation stops when all evaluated."""
        component1 = self.create_sample_component("opt_1", Decimal("15"), "accepted")
        component2 = self.create_sample_component("opt_2", Decimal("10"), "rejected")

        report = PerformanceReport(
            report_id="test_report",
            report_date="2025-10-21T10:00:00Z",
            workflow_type="grid_search",
            components=[component1, component2],
            accepted_optimizations=["opt_1"],
            rejected_optimizations=["opt_2"],
        )

        # Should stop (no remaining)
        assert not report.should_continue_evaluation()
        assert "All optimizations evaluated" in report.stop_reason

    def test_should_continue_evaluation_diminishing_returns(self):
        """Test should_continue_evaluation stops on diminishing returns (last 2 rejected)."""
        component1 = self.create_sample_component("opt_1", Decimal("15"), "accepted")
        component2 = self.create_sample_component("opt_2", Decimal("5"), "rejected")
        component3 = self.create_sample_component("opt_3", Decimal("3"), "rejected")
        component4 = self.create_sample_component("opt_4", Decimal("10"), "proposed")

        report = PerformanceReport(
            report_id="test_report",
            report_date="2025-10-21T10:00:00Z",
            workflow_type="grid_search",
            components=[component1, component2, component3, component4],
            accepted_optimizations=["opt_1"],
            rejected_optimizations=["opt_2", "opt_3"],
        )

        # Should stop (last 2 rejected)
        assert not report.should_continue_evaluation()
        assert "Diminishing returns" in report.stop_reason

    def test_should_continue_evaluation_continues(self):
        """Test should_continue_evaluation continues when conditions not met."""
        component1 = self.create_sample_component("opt_1", Decimal("15"), "accepted")
        component2 = self.create_sample_component("opt_2", Decimal("10"), "rejected")
        component3 = self.create_sample_component("opt_3", Decimal("12"), "proposed")

        report = PerformanceReport(
            report_id="test_report",
            report_date="2025-10-21T10:00:00Z",
            workflow_type="grid_search",
            components=[component1, component2, component3],
            accepted_optimizations=["opt_1"],
            rejected_optimizations=["opt_2"],
        )

        # Should continue (still have remaining, not all rejected, < 40%)
        assert report.should_continue_evaluation()


class TestBenchmarkResultValidation:
    """Additional validation tests for BenchmarkResult."""

    def test_negative_memory_peak_raises_error(self):
        """Test that negative memory_peak_mb raises ValueError."""
        with pytest.raises(ValueError, match="Memory metrics must be non-negative"):
            BenchmarkResult(
                benchmark_id="test",
                configuration_name="test",
                iteration_number=1,
                execution_time_seconds=Decimal("10.0"),
                cpu_time_seconds=Decimal("9.5"),
                memory_peak_mb=Decimal("-100"),  # Negative
                memory_average_mb=Decimal("450"),
                dataset_size=1000,
                parameter_combinations=100,
                backtest_count=100,
                platform="darwin",
                cpu_model="Apple M1",
                python_version="3.12.0",
                timestamp="2025-10-21T10:00:00Z",
                random_seed=42,
                flame_graph_path=None,
                profiling_json_path=None,
            )

    def test_negative_memory_average_raises_error(self):
        """Test that negative memory_average_mb raises ValueError."""
        with pytest.raises(ValueError, match="Memory metrics must be non-negative"):
            BenchmarkResult(
                benchmark_id="test",
                configuration_name="test",
                iteration_number=1,
                execution_time_seconds=Decimal("10.0"),
                cpu_time_seconds=Decimal("9.5"),
                memory_peak_mb=Decimal("500"),
                memory_average_mb=Decimal("-450"),  # Negative
                dataset_size=1000,
                parameter_combinations=100,
                backtest_count=100,
                platform="darwin",
                cpu_model="Apple M1",
                python_version="3.12.0",
                timestamp="2025-10-21T10:00:00Z",
                random_seed=42,
                flame_graph_path=None,
                profiling_json_path=None,
            )

    def test_zero_dataset_size_raises_error(self):
        """Test that dataset_size <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="Workload characteristics must be positive"):
            BenchmarkResult(
                benchmark_id="test",
                configuration_name="test",
                iteration_number=1,
                execution_time_seconds=Decimal("10.0"),
                cpu_time_seconds=Decimal("9.5"),
                memory_peak_mb=Decimal("500"),
                memory_average_mb=Decimal("450"),
                dataset_size=0,  # Zero
                parameter_combinations=100,
                backtest_count=100,
                platform="darwin",
                cpu_model="Apple M1",
                python_version="3.12.0",
                timestamp="2025-10-21T10:00:00Z",
                random_seed=42,
                flame_graph_path=None,
                profiling_json_path=None,
            )

    def test_zero_parameter_combinations_raises_error(self):
        """Test that parameter_combinations <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="Workload characteristics must be positive"):
            BenchmarkResult(
                benchmark_id="test",
                configuration_name="test",
                iteration_number=1,
                execution_time_seconds=Decimal("10.0"),
                cpu_time_seconds=Decimal("9.5"),
                memory_peak_mb=Decimal("500"),
                memory_average_mb=Decimal("450"),
                dataset_size=1000,
                parameter_combinations=0,  # Zero
                backtest_count=100,
                platform="darwin",
                cpu_model="Apple M1",
                python_version="3.12.0",
                timestamp="2025-10-21T10:00:00Z",
                random_seed=42,
                flame_graph_path=None,
                profiling_json_path=None,
            )

    def test_zero_backtest_count_raises_error(self):
        """Test that backtest_count <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="Workload characteristics must be positive"):
            BenchmarkResult(
                benchmark_id="test",
                configuration_name="test",
                iteration_number=1,
                execution_time_seconds=Decimal("10.0"),
                cpu_time_seconds=Decimal("9.5"),
                memory_peak_mb=Decimal("500"),
                memory_average_mb=Decimal("450"),
                dataset_size=1000,
                parameter_combinations=100,
                backtest_count=0,  # Zero
                platform="darwin",
                cpu_model="Apple M1",
                python_version="3.12.0",
                timestamp="2025-10-21T10:00:00Z",
                random_seed=42,
                flame_graph_path=None,
                profiling_json_path=None,
            )
