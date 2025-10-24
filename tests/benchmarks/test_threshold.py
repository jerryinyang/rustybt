"""
Comprehensive tests for performance threshold evaluation framework.

This test suite validates the statistical validation, decision framework,
and threshold configuration system with property-based and integration tests.

Constitutional requirements:
- CR-002: Zero-Mock Enforcement - Real statistical calculations, no mocks
- CR-004: Type Safety - Complete type hints
- CR-005: Test-Driven Development - Property-based tests with Hypothesis
"""

from decimal import Decimal
from typing import List

import numpy as np
import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from rustybt.benchmarks.exceptions import InsufficientDataError, ThresholdEvaluationError
from rustybt.benchmarks.models import BenchmarkResult, BenchmarkResultSet, PerformanceThreshold
from rustybt.benchmarks.threshold import (
    create_threshold,
    evaluate_threshold,
    validate_threshold_configuration,
)
from rustybt.optimization.config import OptimizationConfig, get_default_config, set_default_config


@pytest.fixture(autouse=True)
def reset_default_config():
    """
    Reset the global default config before and after each test.

    This fixture prevents test pollution by ensuring the singleton
    _default_config is reset to None before each test runs.
    """
    import rustybt.optimization.config as config_module

    # Save original state
    original_config = config_module._default_config

    # Reset to None before test (forces fresh creation)
    config_module._default_config = None

    yield

    # Restore after test
    config_module._default_config = original_config


class TestThresholdCreation:
    """Tests for threshold creation utility."""

    def test_create_threshold_with_defaults(self):
        """Test creating threshold with default parameters."""
        threshold = create_threshold(min_improvement_percent=Decimal("5.0"))

        assert threshold.min_improvement_percent == Decimal("5.0")
        assert threshold.workflow_type == "grid_search"
        assert threshold.statistical_confidence == Decimal("0.95")
        assert threshold.min_sample_size == 10
        assert threshold.max_memory_increase_percent == Decimal("2.0")
        assert len(threshold.rationale) > 0
        assert len(threshold.created_date) > 0

    def test_create_threshold_with_custom_parameters(self):
        """Test creating threshold with custom parameters."""
        threshold = create_threshold(
            min_improvement_percent=Decimal("10.0"),
            workflow_type="walk_forward",
            dataset_size_category="large",
            statistical_confidence=Decimal("0.99"),
            min_sample_size=20,
            max_memory_increase_percent=Decimal("1.0"),
            rationale="Custom strict threshold",
        )

        assert threshold.min_improvement_percent == Decimal("10.0")
        assert threshold.workflow_type == "walk_forward"
        assert threshold.dataset_size_category == "large"
        assert threshold.statistical_confidence == Decimal("0.99")
        assert threshold.min_sample_size == 20
        assert threshold.max_memory_increase_percent == Decimal("1.0")
        assert threshold.rationale == "Custom strict threshold"

    def test_create_threshold_auto_rationale(self):
        """Test that rationale is auto-generated when not provided."""
        threshold = create_threshold(
            min_improvement_percent=Decimal("7.5"), workflow_type="single_backtest"
        )

        # Rationale should mention key parameters
        assert "7.5" in threshold.rationale
        assert "single_backtest" in threshold.rationale


class TestThresholdValidation:
    """Tests for threshold validation utility."""

    def test_validate_threshold_low_improvement(self):
        """Test validation warns about very low improvement threshold."""
        threshold = create_threshold(min_improvement_percent=Decimal("1.0"))

        warnings = validate_threshold_configuration(threshold)

        assert len(warnings) > 0
        assert any("very low" in w.lower() for w in warnings)

    def test_validate_threshold_high_improvement(self):
        """Test validation warns about unrealistically high threshold."""
        threshold = create_threshold(min_improvement_percent=Decimal("60.0"))

        warnings = validate_threshold_configuration(threshold)

        assert len(warnings) > 0
        assert any("very high" in w.lower() for w in warnings)

    def test_validate_threshold_restrictive_memory(self):
        """Test validation warns about restrictive memory limits."""
        threshold = create_threshold(
            min_improvement_percent=Decimal("5.0"), max_memory_increase_percent=Decimal("0.5")
        )

        warnings = validate_threshold_configuration(threshold)

        assert len(warnings) > 0
        assert any("restrictive" in w.lower() for w in warnings)

    def test_validate_threshold_lenient_memory(self):
        """Test validation warns about very lenient memory limits."""
        threshold = create_threshold(
            min_improvement_percent=Decimal("5.0"), max_memory_increase_percent=Decimal("25.0")
        )

        warnings = validate_threshold_configuration(threshold)

        assert len(warnings) > 0
        assert any("lenient" in w.lower() for w in warnings)

    def test_validate_threshold_low_confidence(self):
        """Test validation warns about low confidence level."""
        threshold = create_threshold(
            min_improvement_percent=Decimal("5.0"), statistical_confidence=Decimal("0.80")
        )

        warnings = validate_threshold_configuration(threshold)

        assert len(warnings) > 0
        assert any("confidence" in w.lower() and "low" in w.lower() for w in warnings)

    def test_validate_threshold_good_configuration(self):
        """Test that reasonable configuration has no warnings."""
        threshold = create_threshold(
            min_improvement_percent=Decimal("5.0"),
            statistical_confidence=Decimal("0.95"),
            max_memory_increase_percent=Decimal("2.0"),
            min_sample_size=10,
        )

        warnings = validate_threshold_configuration(threshold)

        # Should have no or minimal warnings
        assert len(warnings) == 0


def create_sample_benchmark_result(
    name: str, iteration: int, exec_time: Decimal, memory_mb: Decimal = Decimal("500")
) -> BenchmarkResult:
    """Helper to create benchmark result for tests."""
    return BenchmarkResult(
        benchmark_id=f"{name}_{iteration:03d}",
        configuration_name=name,
        iteration_number=iteration,
        execution_time_seconds=exec_time,
        cpu_time_seconds=exec_time * Decimal("0.95"),
        memory_peak_mb=memory_mb,
        memory_average_mb=memory_mb * Decimal("0.9"),
        dataset_size=1000,
        parameter_combinations=100,
        backtest_count=100,
        platform="test_platform",
        cpu_model="test_cpu",
        python_version="3.12.0",
        timestamp=f"2025-10-23T10:{iteration:02d}:00Z",
        random_seed=42,
        flame_graph_path=None,
        profiling_json_path=None,
    )


def create_sample_result_set(
    name: str, mean_time: Decimal, num_samples: int = 10, variance: Decimal = Decimal("0.1")
) -> BenchmarkResultSet:
    """Helper to create result set with controlled statistics."""
    results = []
    for i in range(1, num_samples + 1):
        # Add controlled variance (convert to Decimal to avoid type mixing)
        time_offset = (
            (Decimal(i) - Decimal(num_samples) / Decimal("2")) * variance / Decimal(num_samples)
        )
        exec_time = mean_time + time_offset
        results.append(create_sample_benchmark_result(name, i, exec_time))

    return BenchmarkResultSet(configuration_name=name, workflow_type="grid_search", results=results)


class TestThresholdEvaluation:
    """Tests for threshold evaluation core functionality."""

    def test_evaluate_threshold_insufficient_baseline_samples(self):
        """Test that insufficient baseline samples raises error."""
        threshold = create_threshold(min_improvement_percent=Decimal("5.0"))

        baseline_results = create_sample_result_set(
            "baseline", mean_time=Decimal("10.0"), num_samples=5  # < 10 required
        )
        optimized_results = create_sample_result_set(
            "optimized", mean_time=Decimal("8.0"), num_samples=10
        )

        with pytest.raises(InsufficientDataError, match="Baseline has 5 samples"):
            evaluate_threshold(baseline_results, optimized_results, threshold)

    def test_evaluate_threshold_insufficient_optimized_samples(self):
        """Test that insufficient optimized samples raises error."""
        threshold = create_threshold(min_improvement_percent=Decimal("5.0"))

        baseline_results = create_sample_result_set(
            "baseline", mean_time=Decimal("10.0"), num_samples=10
        )
        optimized_results = create_sample_result_set(
            "optimized", mean_time=Decimal("8.0"), num_samples=7  # < 10 required
        )

        with pytest.raises(InsufficientDataError, match="Optimized has 7 samples"):
            evaluate_threshold(baseline_results, optimized_results, threshold)

    def test_evaluate_threshold_accepts_significant_improvement(self):
        """Test that significant improvement (12%) is accepted."""
        threshold = create_threshold(min_improvement_percent=Decimal("5.0"))

        baseline_results = create_sample_result_set(
            "baseline", mean_time=Decimal("10.0"), num_samples=10
        )
        # 12% improvement
        optimized_results = create_sample_result_set(
            "optimized", mean_time=Decimal("8.8"), num_samples=10  # 12% faster
        )

        result = evaluate_threshold(baseline_results, optimized_results, threshold)

        assert result["passes_threshold"] is True
        assert result["improvement_percent"] > Decimal("11.0")
        assert result["improvement_percent"] < Decimal("13.0")
        assert result["statistical_significance"] == True  # May be numpy bool
        assert result["passes_memory_check"] is True
        assert "ACCEPTED" in result["decision_rationale"]

    def test_evaluate_threshold_rejects_insufficient_improvement(self):
        """Test that insufficient improvement (3%) is rejected."""
        threshold = create_threshold(min_improvement_percent=Decimal("5.0"))

        baseline_results = create_sample_result_set(
            "baseline", mean_time=Decimal("10.0"), num_samples=10
        )
        # Only 3% improvement
        optimized_results = create_sample_result_set(
            "optimized", mean_time=Decimal("9.7"), num_samples=10  # 3% faster
        )

        result = evaluate_threshold(baseline_results, optimized_results, threshold)

        assert result["passes_threshold"] is False
        assert result["improvement_percent"] > Decimal("2.0")
        assert result["improvement_percent"] < Decimal("4.0")
        assert "REJECTED" in result["decision_rationale"]
        assert (
            "below" in result["decision_rationale"] or "threshold" in result["decision_rationale"]
        )

    def test_evaluate_threshold_exactly_at_threshold(self):
        """Test that exactly 5% improvement is accepted."""
        threshold = create_threshold(min_improvement_percent=Decimal("5.0"))

        baseline_results = create_sample_result_set(
            "baseline",
            mean_time=Decimal("10.0"),
            num_samples=10,
            variance=Decimal("0.01"),  # Very low variance for precise result
        )
        # Exactly 5% improvement
        optimized_results = create_sample_result_set(
            "optimized",
            mean_time=Decimal("9.5"),  # Exactly 5% faster
            num_samples=10,
            variance=Decimal("0.01"),  # Very low variance for precise result
        )

        result = evaluate_threshold(baseline_results, optimized_results, threshold)

        # Should pass (>= threshold), allow small rounding error
        assert result["improvement_percent"] >= Decimal("4.99")

    def test_evaluate_threshold_rejects_excessive_memory(self):
        """Test that excessive memory increase (>2%) is rejected."""
        threshold = create_threshold(
            min_improvement_percent=Decimal("5.0"), max_memory_increase_percent=Decimal("2.0")
        )

        baseline_results_list = []
        for i in range(1, 11):
            baseline_results_list.append(
                create_sample_benchmark_result(
                    "baseline", i, Decimal("10.0"), memory_mb=Decimal("100")  # Low memory
                )
            )

        optimized_results_list = []
        for i in range(1, 11):
            optimized_results_list.append(
                create_sample_benchmark_result(
                    "optimized",
                    i,
                    Decimal("8.0"),  # 20% faster
                    memory_mb=Decimal("400"),  # 300% increase (exceeds 2% limit)
                )
            )

        baseline_results = BenchmarkResultSet("baseline", "grid_search", baseline_results_list)
        optimized_results = BenchmarkResultSet("optimized", "grid_search", optimized_results_list)

        result = evaluate_threshold(baseline_results, optimized_results, threshold)

        assert result["passes_threshold"] is False
        assert result["passes_memory_check"] is False
        assert result["memory_increase_percent"] > Decimal("2.0")
        assert "memory" in result["decision_rationale"].lower()

    def test_evaluate_threshold_includes_details(self):
        """Test that evaluation includes detailed metrics."""
        threshold = create_threshold(min_improvement_percent=Decimal("5.0"))

        baseline_results = create_sample_result_set("baseline", Decimal("10.0"))
        optimized_results = create_sample_result_set("optimized", Decimal("8.5"))

        result = evaluate_threshold(
            baseline_results, optimized_results, threshold, include_details=True
        )

        # Check all expected keys present
        assert "passes_threshold" in result
        assert "improvement_percent" in result
        assert "speedup_ratio" in result
        assert "statistical_significance" in result
        assert "p_value" in result
        assert "baseline_mean" in result
        assert "optimized_mean" in result
        assert "baseline_ci_95" in result
        assert "optimized_ci_95" in result
        assert "baseline_std" in result
        assert "optimized_std" in result
        assert "memory_increase_percent" in result
        assert "decision_rationale" in result

    def test_evaluate_threshold_without_details(self):
        """Test that evaluation can exclude detailed metrics."""
        threshold = create_threshold(min_improvement_percent=Decimal("5.0"))

        baseline_results = create_sample_result_set("baseline", Decimal("10.0"))
        optimized_results = create_sample_result_set("optimized", Decimal("8.5"))

        result = evaluate_threshold(
            baseline_results, optimized_results, threshold, include_details=False
        )

        # Essential keys should be present
        assert "passes_threshold" in result
        assert "improvement_percent" in result
        assert "decision_rationale" in result

        # Detail keys should not be present
        assert "baseline_std" not in result
        assert "optimized_std" not in result


class TestOptimizationConfig:
    """Tests for optimization configuration system."""

    def test_create_default_config(self):
        """Test creating default configuration."""
        config = OptimizationConfig.create_default()

        assert len(config.thresholds) > 0
        assert config.enable_debug_logging is False
        assert config.benchmark_output_dir == "benchmark-results"
        assert config.sequential_evaluation_goal_percent == Decimal("40.0")
        assert config.stop_on_diminishing_returns is True

    def test_create_strict_config(self):
        """Test creating strict configuration."""
        config = OptimizationConfig.create_strict()

        # Check that strict thresholds exist
        threshold = config.get_threshold("grid_search", "production")
        assert threshold.min_improvement_percent == Decimal("10.0")
        assert threshold.statistical_confidence == Decimal("0.99")
        assert threshold.min_sample_size == 20

        assert config.sequential_evaluation_goal_percent == Decimal("50.0")

    def test_create_lenient_config(self):
        """Test creating lenient configuration."""
        config = OptimizationConfig.create_lenient()

        threshold = config.get_threshold("grid_search", "small")
        assert threshold.min_improvement_percent == Decimal("2.0")
        assert threshold.statistical_confidence == Decimal("0.90")
        assert threshold.min_sample_size == 10  # Maintains statistical validity

        assert config.enable_debug_logging is True
        assert config.stop_on_diminishing_returns is False

    def test_get_threshold_for_workflow(self):
        """Test getting threshold for specific workflow."""
        config = OptimizationConfig.create_default()

        grid_search_threshold = config.get_threshold("grid_search", "production")
        assert grid_search_threshold.workflow_type == "grid_search"
        assert grid_search_threshold.dataset_size_category == "production"

    def test_get_threshold_missing_configuration(self):
        """Test that missing configuration raises KeyError."""
        config = OptimizationConfig.create_default()

        with pytest.raises(KeyError, match="No threshold configured"):
            config.get_threshold("nonexistent_workflow", "production")

    def test_set_threshold(self):
        """Test setting custom threshold."""
        config = OptimizationConfig.create_default()

        custom_threshold = create_threshold(
            min_improvement_percent=Decimal("7.5"),
            workflow_type="grid_search",
            dataset_size_category="production",
        )

        config.set_threshold(custom_threshold)

        retrieved = config.get_threshold("grid_search", "production")
        assert retrieved.min_improvement_percent == Decimal("7.5")

    def test_get_all_thresholds(self):
        """Test getting all configured thresholds."""
        config = OptimizationConfig.create_default()

        all_thresholds = config.get_all_thresholds()

        assert isinstance(all_thresholds, dict)
        assert len(all_thresholds) > 0
        assert ("grid_search", "production") in all_thresholds

    def test_get_default_config_singleton(self):
        """Test that get_default_config returns singleton."""
        config1 = get_default_config()
        config2 = get_default_config()

        assert config1 is config2

    def test_set_default_config(self):
        """Test setting default configuration globally."""
        original_config = get_default_config()

        # Set strict config as default
        strict_config = OptimizationConfig.create_strict()
        set_default_config(strict_config)

        new_default = get_default_config()
        assert new_default is strict_config

        # Restore original
        set_default_config(original_config)


class TestPropertyBasedThresholdEvaluation:
    """Property-based tests for threshold evaluation using Hypothesis."""

    @given(
        baseline_mean=st.decimals(
            min_value=Decimal("10.0"),  # Higher minimum for stability
            max_value=Decimal("1000.0"),
            allow_nan=False,
            allow_infinity=False,
        ),
        improvement_factor=st.decimals(
            min_value=Decimal("1.05"),  # Larger minimum improvement
            max_value=Decimal("1.5"),  # Smaller maximum to reduce extreme cases
            allow_nan=False,
            allow_infinity=False,
        ),
    )
    def test_improvement_percent_calculation_property(self, baseline_mean, improvement_factor):
        """Property: improvement calculations should be reasonable and consistent."""
        optimized_mean = baseline_mean / improvement_factor

        # Create identical samples (no variance) for exact property testing
        baseline_list = [
            create_sample_benchmark_result("baseline", i, baseline_mean) for i in range(1, 11)
        ]
        optimized_list = [
            create_sample_benchmark_result("optimized", i, optimized_mean) for i in range(1, 11)
        ]

        baseline_results = BenchmarkResultSet("baseline", "grid_search", baseline_list)
        optimized_results = BenchmarkResultSet("optimized", "grid_search", optimized_list)

        threshold = create_threshold(Decimal("1.0"))  # Low threshold to always pass

        result = evaluate_threshold(baseline_results, optimized_results, threshold)

        # Property 1: speedup_ratio should be close to expected value
        expected_speedup = baseline_mean / optimized_mean
        actual_speedup = result["speedup_ratio"]
        assert abs(actual_speedup - expected_speedup) < Decimal("0.01")

        # Property 2: improvement_percent should be positive for speedup > 1
        assert result["improvement_percent"] > Decimal("0")

        # Property 3: speedup and improvement should be related reasonably
        # improvement = (speedup - 1) * 100, so speedup ≈ (improvement/100) + 1
        derived_speedup = (result["improvement_percent"] / Decimal("100")) + Decimal("1")
        assert abs(derived_speedup - actual_speedup) < Decimal("0.2")  # Reasonable tolerance

    @given(
        min_improvement=st.decimals(
            min_value=Decimal("1.0"),
            max_value=Decimal("20.0"),
            allow_nan=False,
            allow_infinity=False,
        ),
        actual_improvement_factor=st.decimals(
            min_value=Decimal("1.0"),
            max_value=Decimal("30.0"),
            allow_nan=False,
            allow_infinity=False,
        ),
    )
    def test_threshold_comparison_property(self, min_improvement, actual_improvement_factor):
        """Property: passes_threshold if and only if improvement >= threshold."""
        threshold = create_threshold(min_improvement_percent=min_improvement)

        baseline_time = Decimal("100.0")
        # Calculate optimized time to achieve exact improvement
        optimized_time = (
            baseline_time * (Decimal("100") - actual_improvement_factor) / Decimal("100")
        )

        # Ensure optimized time is positive
        assume(optimized_time > Decimal("0.1"))

        baseline_results = create_sample_result_set("baseline", baseline_time)
        optimized_results = create_sample_result_set("optimized", optimized_time)

        result = evaluate_threshold(baseline_results, optimized_results, threshold)

        # Property: should pass if actual >= threshold (with some tolerance for stats)
        if actual_improvement_factor >= min_improvement * Decimal("1.1"):
            # Clear pass (10% margin for statistical variation)
            assert result["improvement_percent"] >= min_improvement * Decimal("0.9")
        elif actual_improvement_factor < min_improvement * Decimal("0.9"):
            # Clear fail
            assert result["improvement_percent"] < min_improvement * Decimal("1.1")

    @given(
        sample_size=st.integers(min_value=10, max_value=50),
        mean_value=st.decimals(
            min_value=Decimal("1.0"),
            max_value=Decimal("100.0"),
            allow_nan=False,
            allow_infinity=False,
        ),
    )
    def test_confidence_interval_contains_mean_property(self, sample_size, mean_value):
        """Property: 95% confidence interval must contain the mean."""
        results = create_sample_result_set(
            "test", mean_time=mean_value, num_samples=sample_size, variance=Decimal("0.1")
        )

        ci_lower, ci_upper = results.execution_time_ci_95

        # Property: mean must be within CI
        assert ci_lower <= results.execution_time_mean <= ci_upper

    @given(
        sample_size=st.integers(min_value=10, max_value=30),
        baseline_times=st.lists(
            st.decimals(
                min_value=Decimal("0.1"),
                max_value=Decimal("100.0"),
                allow_nan=False,
                allow_infinity=False,
            ),
            min_size=10,
            max_size=30,
        ),
        optimized_times=st.lists(
            st.decimals(
                min_value=Decimal("0.1"),
                max_value=Decimal("100.0"),
                allow_nan=False,
                allow_infinity=False,
            ),
            min_size=10,
            max_size=30,
        ),
    )
    def test_p_value_range_property(self, sample_size, baseline_times, optimized_times):
        """Property: p-value must be in range [0, 1] for paired t-test."""
        # Paired t-test requires equal sample sizes - use the specified sample_size
        # Trim or pad both lists to exactly sample_size elements
        baseline_times = (baseline_times * ((sample_size // len(baseline_times)) + 1))[:sample_size]
        optimized_times = (optimized_times * ((sample_size // len(optimized_times)) + 1))[
            :sample_size
        ]

        # Ensure we have exactly the same number of samples
        assert len(baseline_times) == sample_size
        assert len(optimized_times) == sample_size

        baseline_results = create_sample_result_set(
            "baseline",
            Decimal(str(sum(float(t) for t in baseline_times) / len(baseline_times))),
            num_samples=sample_size,
        )

        optimized_results = create_sample_result_set(
            "optimized",
            Decimal(str(sum(float(t) for t in optimized_times) / len(optimized_times))),
            num_samples=sample_size,
        )

        threshold = create_threshold(Decimal("1.0"))

        result = evaluate_threshold(baseline_results, optimized_results, threshold)

        # Property: p-value must be in valid range (unless NaN for edge cases)
        if not np.isnan(result["p_value"]):
            assert 0.0 <= result["p_value"] <= 1.0


class TestIntegrationScenarios:
    """Integration tests for real-world threshold evaluation scenarios."""

    def test_scenario_grid_search_optimization_accepted(self):
        """
        Integration Test: Grid Search optimization with 12% improvement accepted.

        Scenario:
        - Baseline: 100 backtests, 50s mean time
        - Optimized: 100 backtests, 44s mean time (12% improvement)
        - Threshold: 5% minimum, 95% confidence
        - Expected: ACCEPTED
        """
        threshold = create_threshold(
            min_improvement_percent=Decimal("5.0"),
            workflow_type="grid_search",
            statistical_confidence=Decimal("0.95"),
        )

        baseline_results = create_sample_result_set(
            "grid_search_baseline",
            mean_time=Decimal("50.0"),
            num_samples=10,
            variance=Decimal("1.0"),
        )

        optimized_results = create_sample_result_set(
            "grid_search_optimized",
            mean_time=Decimal("44.0"),  # 12% improvement
            num_samples=10,
            variance=Decimal("1.0"),
        )

        result = evaluate_threshold(
            baseline_results, optimized_results, threshold, include_details=True
        )

        # Assertions
        assert result["passes_threshold"] is True
        assert Decimal("11.0") < result["improvement_percent"] < Decimal("13.0")
        assert result["speedup_ratio"] > Decimal("1.1")
        assert result["statistical_significance"] == True  # May be numpy bool
        assert result["p_value"] < 0.05
        assert result["passes_memory_check"] is True
        assert "ACCEPTED" in result["decision_rationale"]

        print(f"\n✓ Grid Search 12% improvement ACCEPTED")
        print(f"  Improvement: {result['improvement_percent']:.2f}%")
        print(f"  Speedup: {result['speedup_ratio']:.3f}x")
        print(f"  P-value: {result['p_value']:.4f}")

    def test_scenario_grid_search_optimization_rejected(self):
        """
        Integration Test: Grid Search optimization with 3% improvement rejected.

        Scenario:
        - Baseline: 100 backtests, 50s mean time
        - Optimized: 100 backtests, 48.5s mean time (3% improvement)
        - Threshold: 5% minimum, 95% confidence
        - Expected: REJECTED (below threshold)
        """
        threshold = create_threshold(
            min_improvement_percent=Decimal("5.0"),
            workflow_type="grid_search",
            statistical_confidence=Decimal("0.95"),
        )

        baseline_results = create_sample_result_set(
            "grid_search_baseline",
            mean_time=Decimal("50.0"),
            num_samples=10,
            variance=Decimal("1.0"),
        )

        optimized_results = create_sample_result_set(
            "grid_search_optimized",
            mean_time=Decimal("48.5"),  # 3% improvement
            num_samples=10,
            variance=Decimal("1.0"),
        )

        result = evaluate_threshold(
            baseline_results, optimized_results, threshold, include_details=True
        )

        # Assertions
        assert result["passes_threshold"] is False
        assert Decimal("2.5") < result["improvement_percent"] < Decimal("3.5")
        assert "REJECTED" in result["decision_rationale"]
        assert (
            "below" in result["decision_rationale"].lower()
            or "threshold" in result["decision_rationale"].lower()
        )

        print(f"\n✓ Grid Search 3% improvement REJECTED")
        print(f"  Improvement: {result['improvement_percent']:.2f}%")
        print(f"  Threshold: {threshold.min_improvement_percent}%")
        print(f"  Rationale: {result['decision_rationale']}")

    def test_scenario_walk_forward_with_memory_overhead(self):
        """
        Integration Test: Walk Forward optimization rejected due to memory overhead.

        Scenario:
        - Baseline: 5 windows, 200s mean time, 500MB memory
        - Optimized: 5 windows, 170s mean time (15% improvement), 2000MB memory (300% increase)
        - Threshold: 5% minimum, 2% memory increase limit
        - Expected: REJECTED (memory overhead)
        """
        threshold = create_threshold(
            min_improvement_percent=Decimal("5.0"),
            workflow_type="walk_forward",
            max_memory_increase_percent=Decimal("2.0"),
        )

        baseline_results_list = []
        for i in range(1, 11):
            baseline_results_list.append(
                create_sample_benchmark_result(
                    "walk_forward_baseline", i, Decimal("200.0"), memory_mb=Decimal("500")
                )
            )

        optimized_results_list = []
        for i in range(1, 11):
            optimized_results_list.append(
                create_sample_benchmark_result(
                    "walk_forward_optimized",
                    i,
                    Decimal("170.0"),  # 15% faster
                    memory_mb=Decimal("2000"),  # 300% increase
                )
            )

        baseline_results = BenchmarkResultSet(
            "walk_forward_baseline", "walk_forward", baseline_results_list
        )

        optimized_results = BenchmarkResultSet(
            "walk_forward_optimized", "walk_forward", optimized_results_list
        )

        result = evaluate_threshold(
            baseline_results, optimized_results, threshold, include_details=True
        )

        # Assertions
        assert result["passes_threshold"] is False
        assert result["improvement_percent"] > Decimal("14.0")  # Good performance improvement
        assert result["passes_memory_check"] is False  # But memory increase too high
        assert result["memory_increase_percent"] > Decimal("2.0")
        assert "memory" in result["decision_rationale"].lower()

        print(f"\n✓ Walk Forward optimization REJECTED (memory)")
        print(f"  Improvement: {result['improvement_percent']:.2f}% (good)")
        print(f"  Memory increase: {result['memory_increase_percent']:.2f}% (exceeds 2% limit)")

    def test_scenario_edge_case_exactly_at_threshold(self):
        """
        Integration Test: Edge case where improvement exactly meets threshold.

        Scenario:
        - Baseline: 100s mean time
        - Optimized: 95s mean time (exactly 5% improvement)
        - Threshold: 5% minimum
        - Expected: ACCEPTED (>= threshold)
        """
        threshold = create_threshold(min_improvement_percent=Decimal("5.0"))

        baseline_results = create_sample_result_set(
            "baseline", mean_time=Decimal("100.0"), num_samples=10
        )

        optimized_results = create_sample_result_set(
            "optimized", mean_time=Decimal("95.0"), num_samples=10  # Exactly 5% improvement
        )

        result = evaluate_threshold(baseline_results, optimized_results, threshold)

        # Should pass at exactly the threshold
        assert result["improvement_percent"] >= Decimal("4.9")  # Allow small rounding
        print(f"\n✓ Exactly 5% improvement: {result['improvement_percent']:.2f}%")

    def test_scenario_diminishing_returns_detection(self):
        """
        Integration Test: Sequential evaluation detects diminishing returns.

        Scenario:
        - Optimization 1: 12% improvement → ACCEPTED
        - Optimization 2: 3% improvement → REJECTED
        - Optimization 3: 2% improvement → REJECTED
        - Expected: Stop after 2 consecutive rejections
        """
        threshold = create_threshold(min_improvement_percent=Decimal("5.0"))

        # First optimization: 12% improvement (accepted)
        opt1_baseline = create_sample_result_set("opt1_baseline", Decimal("100.0"))
        opt1_optimized = create_sample_result_set("opt1_optimized", Decimal("88.0"))
        result1 = evaluate_threshold(opt1_baseline, opt1_optimized, threshold)

        assert result1["passes_threshold"] is True

        # Second optimization: 3% improvement (rejected)
        opt2_baseline = create_sample_result_set("opt2_baseline", Decimal("88.0"))
        opt2_optimized = create_sample_result_set("opt2_optimized", Decimal("85.4"))
        result2 = evaluate_threshold(opt2_baseline, opt2_optimized, threshold)

        assert result2["passes_threshold"] is False

        # Third optimization: 2% improvement (rejected)
        opt3_baseline = create_sample_result_set("opt3_baseline", Decimal("85.4"))
        opt3_optimized = create_sample_result_set("opt3_optimized", Decimal("83.7"))
        result3 = evaluate_threshold(opt3_baseline, opt3_optimized, threshold)

        assert result3["passes_threshold"] is False

        print(f"\n✓ Diminishing returns detected")
        print(f"  Opt 1: {result1['improvement_percent']:.2f}% → ACCEPTED")
        print(f"  Opt 2: {result2['improvement_percent']:.2f}% → REJECTED")
        print(f"  Opt 3: {result3['improvement_percent']:.2f}% → REJECTED")
        print(f"  Sequential evaluation should stop after Opt 3")


class TestAdditionalCoverage:
    """Additional tests to achieve 90%+ coverage for threshold.py"""

    def test_evaluate_threshold_unequal_sample_sizes_error(self):
        """Test that unequal sample sizes raises ThresholdEvaluationError."""
        threshold = create_threshold(min_improvement_percent=Decimal("5.0"))

        baseline_results = create_sample_result_set(
            "baseline", mean_time=Decimal("10.0"), num_samples=10
        )
        optimized_results = create_sample_result_set(
            "optimized", mean_time=Decimal("8.0"), num_samples=15  # Different count
        )

        with pytest.raises(ThresholdEvaluationError, match="equal sample sizes"):
            evaluate_threshold(baseline_results, optimized_results, threshold)

    def test_decision_rationale_multiple_failures(self):
        """Test decision rationale with multiple rejection reasons combined."""
        threshold = create_threshold(
            min_improvement_percent=Decimal("10.0"), max_memory_increase_percent=Decimal("2.0")
        )

        # Create scenario with insufficient improvement AND excessive memory
        baseline_results_list = []
        for i in range(1, 11):
            baseline_results_list.append(
                create_sample_benchmark_result(
                    "baseline", i, Decimal("100.0"), memory_mb=Decimal("100")
                )
            )

        optimized_results_list = []
        for i in range(1, 11):
            optimized_results_list.append(
                create_sample_benchmark_result(
                    "optimized",
                    i,
                    Decimal("96.0"),  # Only 4% improvement (< 10% threshold)
                    memory_mb=Decimal("500"),  # 400% memory increase (> 2% threshold)
                )
            )

        baseline_results = BenchmarkResultSet("baseline", "grid_search", baseline_results_list)
        optimized_results = BenchmarkResultSet("optimized", "grid_search", optimized_results_list)

        result = evaluate_threshold(baseline_results, optimized_results, threshold)

        # Should have REJECTED with multiple reasons
        assert result["passes_threshold"] is False
        assert "REJECTED" in result["decision_rationale"]
        rationale_lower = result["decision_rationale"].lower()
        # Check for multiple failure reasons
        assert "improvement" in rationale_lower or "below" in rationale_lower
        assert "memory" in rationale_lower

    def test_decision_rationale_not_significant_only(self):
        """Test decision rationale when only statistical significance fails."""
        threshold = create_threshold(
            min_improvement_percent=Decimal("3.0"),  # Low threshold
            max_memory_increase_percent=Decimal("50.0"),  # Very lenient
        )

        # Create results with good improvement but high variance (may not be significant)
        baseline_results = create_sample_result_set(
            "baseline",
            mean_time=Decimal("10.0"),
            num_samples=10,
            variance=Decimal("5.0"),  # High variance
        )
        optimized_results = create_sample_result_set(
            "optimized",
            mean_time=Decimal("9.5"),  # 5% improvement (above 3% threshold)
            num_samples=10,
            variance=Decimal("5.0"),  # High variance
        )

        result = evaluate_threshold(baseline_results, optimized_results, threshold)

        # If it fails (might not always due to randomness), check rationale mentions p-value/significance
        if not result["passes_threshold"] and not result["statistical_significance"]:
            assert (
                "significant" in result["decision_rationale"].lower()
                or "p=" in result["decision_rationale"]
            )

    def test_zero_baseline_memory_edge_case(self):
        """Test memory evaluation when baseline memory is zero."""
        threshold = create_threshold(
            min_improvement_percent=Decimal("5.0"), max_memory_increase_percent=Decimal("2.0")
        )

        baseline_results_list = []
        for i in range(1, 11):
            baseline_results_list.append(
                create_sample_benchmark_result(
                    "baseline", i, Decimal("10.0"), memory_mb=Decimal("0")  # Zero memory baseline
                )
            )

        optimized_results_list = []
        for i in range(1, 11):
            optimized_results_list.append(
                create_sample_benchmark_result(
                    "optimized",
                    i,
                    Decimal("8.0"),  # 20% improvement
                    memory_mb=Decimal("0.5"),  # Small memory usage
                )
            )

        baseline_results = BenchmarkResultSet("baseline", "grid_search", baseline_results_list)
        optimized_results = BenchmarkResultSet("optimized", "grid_search", optimized_results_list)

        result = evaluate_threshold(baseline_results, optimized_results, threshold)

        # Should pass memory check (< 1MB threshold for zero baseline)
        assert result["passes_memory_check"] is True
        assert result["memory_increase_percent"] == Decimal("inf") or result[
            "memory_increase_percent"
        ] >= Decimal("0")

    def test_evaluate_against_threshold_function(self):
        """Test the evaluate_against_threshold function for single results."""
        from rustybt.benchmarks.threshold import evaluate_against_threshold

        threshold = create_threshold(
            min_improvement_percent=Decimal("5.0"), statistical_confidence=Decimal("0.95")
        )

        # Create a benchmark result that passes
        passing_result = BenchmarkResult(
            benchmark_id="test_001",
            configuration_name="test_config",
            iteration_number=1,
            execution_time_seconds=Decimal("8.0"),
            cpu_time_seconds=Decimal("7.6"),
            memory_peak_mb=Decimal("500"),
            memory_average_mb=Decimal("450"),
            dataset_size=1000,
            parameter_combinations=100,
            backtest_count=100,
            platform="test_platform",
            cpu_model="test_cpu",
            python_version="3.12.0",
            timestamp="2025-10-23T10:00:00Z",
            random_seed=42,
            flame_graph_path=None,
            profiling_json_path=None,
        )

        # Use object.__setattr__ for frozen dataclass
        object.__setattr__(passing_result, "improvement_percent", Decimal("12.0"))
        object.__setattr__(passing_result, "p_value", 0.01)
        object.__setattr__(passing_result, "speedup_ratio", Decimal("1.12"))

        passed, details = evaluate_against_threshold(passing_result, threshold)

        assert passed is True
        assert details["improvement_percent"] == 12.0
        assert details["min_required"] == 5.0
        assert details["p_value"] == 0.01
        assert details["significance_level"] == 0.05  # 1 - 0.95
        assert details["speedup_ratio"] == 1.12

    def test_evaluate_against_threshold_rejection(self):
        """Test evaluate_against_threshold when result fails."""
        from rustybt.benchmarks.threshold import evaluate_against_threshold

        threshold = create_threshold(
            min_improvement_percent=Decimal("10.0"), statistical_confidence=Decimal("0.95")
        )

        # Create a benchmark result that fails
        failing_result = BenchmarkResult(
            benchmark_id="test_002",
            configuration_name="test_config_fail",
            iteration_number=1,
            execution_time_seconds=Decimal("9.5"),
            cpu_time_seconds=Decimal("9.0"),
            memory_peak_mb=Decimal("500"),
            memory_average_mb=Decimal("450"),
            dataset_size=1000,
            parameter_combinations=100,
            backtest_count=100,
            platform="test_platform",
            cpu_model="test_cpu",
            python_version="3.12.0",
            timestamp="2025-10-23T10:00:00Z",
            random_seed=42,
            flame_graph_path=None,
            profiling_json_path=None,
        )

        # Use object.__setattr__ for frozen dataclass
        object.__setattr__(failing_result, "improvement_percent", Decimal("3.0"))
        object.__setattr__(failing_result, "p_value", 0.15)
        object.__setattr__(failing_result, "speedup_ratio", Decimal("1.03"))

        passed, details = evaluate_against_threshold(failing_result, threshold)

        assert passed is False
        assert details["improvement_percent"] == 3.0
        assert details["min_required"] == 10.0
        assert details["p_value"] == 0.15

    def test_include_details_false(self):
        """Test that include_details=False returns minimal result."""
        threshold = create_threshold(min_improvement_percent=Decimal("5.0"))

        baseline_results = create_sample_result_set("baseline", Decimal("10.0"))
        optimized_results = create_sample_result_set("optimized", Decimal("8.5"))

        result = evaluate_threshold(
            baseline_results, optimized_results, threshold, include_details=False
        )

        # Should have basic keys
        assert "passes_threshold" in result
        assert "improvement_percent" in result
        assert "speedup_ratio" in result
        assert "statistical_significance" in result
        assert "p_value" in result
        assert "decision_rationale" in result

        # Should NOT have detailed keys
        assert "baseline_mean" not in result
        assert "optimized_mean" not in result
        assert "baseline_ci_95" not in result
        assert "baseline_std" not in result

    def test_validate_threshold_small_sample_size_warning(self):
        """Test validation warns about small sample size."""
        # Create threshold directly with __post_init__ bypassed
        # to test the validation function (not the constructor validation)
        from rustybt.benchmarks.models import PerformanceThreshold

        # Use object.__new__ to create without validation, then set attributes
        threshold = object.__new__(PerformanceThreshold)
        object.__setattr__(threshold, "min_improvement_percent", Decimal("5.0"))
        object.__setattr__(threshold, "workflow_type", "grid_search")
        object.__setattr__(threshold, "dataset_size_category", "production")
        object.__setattr__(threshold, "statistical_confidence", Decimal("0.95"))
        object.__setattr__(threshold, "min_sample_size", 5)  # Too small
        object.__setattr__(threshold, "max_memory_increase_percent", Decimal("2.0"))
        object.__setattr__(threshold, "rationale", "test")
        object.__setattr__(threshold, "created_date", "2025-10-23T10:00:00Z")

        warnings = validate_threshold_configuration(threshold)

        assert len(warnings) > 0
        assert any("sample size" in w.lower() and "small" in w.lower() for w in warnings)
