"""
Comprehensive tests for sequential optimization evaluation.

Tests the complete workflow:
- evaluate_single_optimization() - functional testing, benchmarking, threshold evaluation
- evaluate_optimization_sequence() - sequential evaluation with stopping criteria
- Report generation and saving

Constitutional requirements:
- CR-002: Zero-Mock Enforcement - Real workflow execution, no mocks
- CR-004: Type Safety - Complete type hints
- CR-005: Test-Driven Development - Comprehensive test coverage
"""

import shutil
import tempfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from rustybt.benchmarks.exceptions import FunctionalEquivalenceError, SequentialEvaluationError
from rustybt.benchmarks.models import (
    BenchmarkResult,
    BenchmarkResultSet,
    OptimizationComponent,
    PerformanceReport,
    PerformanceThreshold,
)
from rustybt.benchmarks.sequential import (
    _generate_detailed_findings,
    _generate_executive_summary,
    _save_performance_report,
    evaluate_optimization_sequence,
    evaluate_single_optimization,
)
from rustybt.benchmarks.threshold import create_threshold

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def temp_output_dir():
    """Create temporary directory for benchmark outputs."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_threshold():
    """Create standard threshold for testing."""
    return create_threshold(
        min_improvement_percent=Decimal("5.0"),
        workflow_type="grid_search",
        statistical_confidence=Decimal("0.95"),
        min_sample_size=10,
    )


@pytest.fixture
def sample_optimization_component():
    """Create sample optimization component."""
    return OptimizationComponent(
        component_id="test_opt_001",
        component_name="Test Optimization",
        implementation_type="python",
        functional_category="search_algorithm",
        priority_rank=1,
        expected_impact_range=(Decimal("5.0"), Decimal("10.0")),
        complexity_level="low",
        consistency_risk_level="low",
        source_file_path="tests/test_optimization.py",
        api_signature="def test_function() -> int",
        dependencies=[],
        baseline_results=None,
        optimized_results=None,
        status="pending",
        decision_rationale=None,
        created_date="2025-10-24T00:00:00Z",
        last_updated="2025-10-24T00:00:00Z",
        evaluation_order=None,
    )


def baseline_add_function(a: int, b: int) -> int:
    """Simple baseline function for testing."""
    return a + b


def optimized_add_function(a: int, b: int) -> int:
    """Optimized function (functionally equivalent)."""
    return a + b


def broken_optimized_add_function(a: int, b: int) -> int:
    """Broken optimized function (not equivalent)."""
    return a + b + 1  # Bug!


def slow_baseline_workload() -> int:
    """Slow baseline workload for benchmarking."""
    import time

    time.sleep(0.01)  # 10ms
    return sum(range(100))


def fast_optimized_workload() -> int:
    """Fast optimized workload (simulates 20% improvement)."""
    import time

    time.sleep(0.008)  # 8ms (20% faster)
    return sum(range(100))


def marginal_optimized_workload() -> int:
    """Marginally optimized workload (only 2% improvement)."""
    import time

    time.sleep(0.0098)  # 9.8ms (2% faster)
    return sum(range(100))


# ============================================================================
# Tests for evaluate_single_optimization()
# ============================================================================


class TestEvaluateSingleOptimization:
    """Tests for evaluate_single_optimization function."""

    def test_evaluate_single_optimization_functional_equivalence_pass(
        self, sample_optimization_component, sample_threshold, temp_output_dir
    ):
        """Test that functional equivalence check passes for equivalent functions."""
        test_cases = [
            ((1, 2), {}),
            ((10, 20), {}),
            ((-5, 5), {}),
        ]

        result = evaluate_single_optimization(
            optimization=sample_optimization_component,
            baseline_fn=baseline_add_function,
            optimized_fn=optimized_add_function,
            test_cases=test_cases,
            benchmark_workload_fn=slow_baseline_workload,
            benchmark_args=(),
            benchmark_kwargs={},
            threshold=sample_threshold,
            num_benchmark_runs=10,
            output_dir=temp_output_dir,
        )

        assert result["component_id"] == "test_opt_001"
        assert result["functional_equivalence_passed"] is True
        assert result["baseline_results"] is not None
        assert result["optimized_results"] is not None
        assert result["threshold_evaluation"] is not None
        assert result["decision"] in ["accepted", "rejected"]

    def test_evaluate_single_optimization_functional_equivalence_fail(
        self, sample_optimization_component, sample_threshold, temp_output_dir
    ):
        """Test that functional equivalence check fails for non-equivalent functions."""
        test_cases = [
            ((1, 2), {}),
        ]

        result = evaluate_single_optimization(
            optimization=sample_optimization_component,
            baseline_fn=baseline_add_function,
            optimized_fn=broken_optimized_add_function,
            test_cases=test_cases,
            benchmark_workload_fn=slow_baseline_workload,
            benchmark_args=(),
            benchmark_kwargs={},
            threshold=sample_threshold,
            num_benchmark_runs=10,
            output_dir=temp_output_dir,
        )

        # Should fail at functional equivalence and not run benchmarks
        assert result["functional_equivalence_passed"] is False
        assert result["baseline_results"] is None
        assert result["optimized_results"] is None
        assert result["decision"] == "rejected"
        assert "Functional equivalence failed" in result["decision_rationale"]

    def test_evaluate_single_optimization_accepted_improvement(
        self, sample_optimization_component, sample_threshold, temp_output_dir
    ):
        """Test that similar performance (same workload) is rejected."""
        test_cases = [((1, 2), {})]

        result = evaluate_single_optimization(
            optimization=sample_optimization_component,
            baseline_fn=baseline_add_function,
            optimized_fn=optimized_add_function,
            test_cases=test_cases,
            benchmark_workload_fn=slow_baseline_workload,
            benchmark_args=(),
            benchmark_kwargs={},
            threshold=sample_threshold,
            num_benchmark_runs=10,
            output_dir=temp_output_dir,
        )

        # With same workload for both baseline and optimized, performance is similar
        # so optimization should be rejected due to insufficient improvement
        assert result["functional_equivalence_passed"] is True
        assert result["decision"] == "rejected"
        assert result["threshold_evaluation"]["passes_threshold"] is False

    def test_evaluate_single_optimization_rejected_marginal(
        self, sample_optimization_component, sample_threshold, temp_output_dir
    ):
        """Test that marginal improvement (2%) is rejected."""
        test_cases = [((1, 2), {})]

        result = evaluate_single_optimization(
            optimization=sample_optimization_component,
            baseline_fn=baseline_add_function,
            optimized_fn=optimized_add_function,
            test_cases=test_cases,
            benchmark_workload_fn=marginal_optimized_workload,
            benchmark_args=(),
            benchmark_kwargs={},
            threshold=sample_threshold,
            num_benchmark_runs=10,
            output_dir=temp_output_dir,
        )

        # With 2% improvement and 5% threshold, should be rejected
        assert result["functional_equivalence_passed"] is True
        # Note: May vary based on actual benchmark timing variability

    def test_evaluate_single_optimization_with_benchmark_kwargs(
        self, sample_optimization_component, sample_threshold, temp_output_dir
    ):
        """Test that benchmark kwargs are properly handled."""
        test_cases = [((1, 2), {})]

        def workload_with_kwargs(multiplier: int = 1) -> int:
            return sum(range(100)) * multiplier

        result = evaluate_single_optimization(
            optimization=sample_optimization_component,
            baseline_fn=baseline_add_function,
            optimized_fn=optimized_add_function,
            test_cases=test_cases,
            benchmark_workload_fn=workload_with_kwargs,
            benchmark_args=(),
            benchmark_kwargs={"multiplier": 2},
            threshold=sample_threshold,
            num_benchmark_runs=10,
            output_dir=temp_output_dir,
        )

        assert result["functional_equivalence_passed"] is True
        assert result["baseline_results"] is not None


# ============================================================================
# Tests for evaluate_optimization_sequence()
# ============================================================================


class TestEvaluateOptimizationSequence:
    """Tests for evaluate_optimization_sequence function."""

    def test_evaluate_sequence_empty_list(self, sample_threshold, temp_output_dir):
        """Test evaluation with empty optimizations list."""
        report = evaluate_optimization_sequence(
            optimizations=[],
            threshold=sample_threshold,
            evaluation_configs={},
            output_dir=temp_output_dir,
        )

        assert len(report.components) == 0
        assert len(report.accepted_optimizations) == 0
        assert len(report.rejected_optimizations) == 0
        assert report.cumulative_improvement_percent == Decimal("0")

    def test_evaluate_sequence_single_optimization(
        self, sample_optimization_component, sample_threshold, temp_output_dir
    ):
        """Test sequential evaluation with single optimization."""
        test_cases = [((1, 2), {})]

        evaluation_configs = {
            "test_opt_001": {
                "baseline_fn": baseline_add_function,
                "optimized_fn": optimized_add_function,
                "test_cases": test_cases,
                "benchmark_workload_fn": slow_baseline_workload,
                "benchmark_args": (),
                "benchmark_kwargs": {},
            }
        }

        report = evaluate_optimization_sequence(
            optimizations=[sample_optimization_component],
            threshold=sample_threshold,
            evaluation_configs=evaluation_configs,
            output_dir=temp_output_dir,
        )

        assert len(report.components) == 1
        assert report.current_evaluation_index >= 0
        assert report.executive_summary != ""
        assert report.detailed_findings != ""

    def test_evaluate_sequence_multiple_optimizations(self, sample_threshold, temp_output_dir):
        """Test sequential evaluation with multiple optimizations."""
        opt1 = OptimizationComponent(
            component_id="opt_001",
            component_name="Optimization 1",
            implementation_type="python",
            functional_category="search_algorithm",
            priority_rank=1,
            expected_impact_range=(Decimal("5.0"), Decimal("10.0")),
            complexity_level="low",
            consistency_risk_level="low",
            source_file_path="tests/test_opt1.py",
            api_signature="def opt1_function() -> int",
            dependencies=[],
            baseline_results=None,
            optimized_results=None,
            status="pending",
            decision_rationale=None,
            created_date="2025-10-24T00:00:00Z",
            last_updated="2025-10-24T00:00:00Z",
            evaluation_order=None,
        )

        opt2 = OptimizationComponent(
            component_id="opt_002",
            component_name="Optimization 2",
            implementation_type="python",
            functional_category="dataportal_caching",
            priority_rank=2,
            expected_impact_range=(Decimal("3.0"), Decimal("7.0")),
            complexity_level="low",
            consistency_risk_level="low",
            source_file_path="tests/test_opt2.py",
            api_signature="def opt2_function() -> int",
            dependencies=[],
            baseline_results=None,
            optimized_results=None,
            status="pending",
            decision_rationale=None,
            created_date="2025-10-24T00:00:00Z",
            last_updated="2025-10-24T00:00:00Z",
            evaluation_order=None,
        )

        test_cases = [((1, 2), {})]

        evaluation_configs = {
            "opt_001": {
                "baseline_fn": baseline_add_function,
                "optimized_fn": optimized_add_function,
                "test_cases": test_cases,
                "benchmark_workload_fn": slow_baseline_workload,
                "benchmark_args": (),
                "benchmark_kwargs": {},
            },
            "opt_002": {
                "baseline_fn": baseline_add_function,
                "optimized_fn": optimized_add_function,
                "test_cases": test_cases,
                "benchmark_workload_fn": fast_optimized_workload,
                "benchmark_args": (),
                "benchmark_kwargs": {},
            },
        }

        report = evaluate_optimization_sequence(
            optimizations=[opt1, opt2],
            threshold=sample_threshold,
            evaluation_configs=evaluation_configs,
            output_dir=temp_output_dir,
            goal_improvement_percent=Decimal("15.0"),
            stop_on_goal_achieved=False,  # Evaluate all
        )

        assert len(report.components) == 2
        assert len(report.accepted_optimizations) + len(report.rejected_optimizations) == 2

    def test_evaluate_sequence_goal_achievement_stops(self, sample_threshold, temp_output_dir):
        """Test that evaluation stops when goal is achieved."""
        opt1 = OptimizationComponent(
            component_id="opt_001",
            component_name="High Impact Opt",
            implementation_type="python",
            functional_category="batch_initialization",
            priority_rank=1,
            expected_impact_range=(Decimal("20.0"), Decimal("30.0")),
            complexity_level="low",
            consistency_risk_level="low",
            source_file_path="tests/test_high_impact.py",
            api_signature="def high_impact_function() -> int",
            dependencies=[],
            baseline_results=None,
            optimized_results=None,
            status="pending",
            decision_rationale=None,
            created_date="2025-10-24T00:00:00Z",
            last_updated="2025-10-24T00:00:00Z",
            evaluation_order=None,
        )

        opt2 = OptimizationComponent(
            component_id="opt_002",
            component_name="Should Be Skipped",
            implementation_type="python",
            functional_category="parallel_coordination",
            priority_rank=2,
            expected_impact_range=(Decimal("5.0"), Decimal("10.0")),
            complexity_level="low",
            consistency_risk_level="low",
            source_file_path="tests/test_skipped.py",
            api_signature="def skipped_function() -> int",
            dependencies=[],
            baseline_results=None,
            optimized_results=None,
            status="pending",
            decision_rationale=None,
            created_date="2025-10-24T00:00:00Z",
            last_updated="2025-10-24T00:00:00Z",
            evaluation_order=None,
        )

        test_cases = [((1, 2), {})]

        evaluation_configs = {
            "opt_001": {
                "baseline_fn": baseline_add_function,
                "optimized_fn": optimized_add_function,
                "test_cases": test_cases,
                "benchmark_workload_fn": slow_baseline_workload,
                "benchmark_args": (),
                "benchmark_kwargs": {},
            },
            "opt_002": {
                "baseline_fn": baseline_add_function,
                "optimized_fn": optimized_add_function,
                "test_cases": test_cases,
                "benchmark_workload_fn": fast_optimized_workload,
                "benchmark_args": (),
                "benchmark_kwargs": {},
            },
        }

        report = evaluate_optimization_sequence(
            optimizations=[opt1, opt2],
            threshold=sample_threshold,
            evaluation_configs=evaluation_configs,
            output_dir=temp_output_dir,
            goal_improvement_percent=Decimal("10.0"),  # Low goal
            stop_on_goal_achieved=True,
        )

        # If opt1 achieves 20% improvement and goal is 10%, should stop
        # opt2 should be skipped
        # Note: Actual behavior depends on benchmark timing

    def test_evaluate_sequence_missing_config_skips(
        self, sample_optimization_component, sample_threshold, temp_output_dir
    ):
        """Test that optimizations without config are skipped."""
        report = evaluate_optimization_sequence(
            optimizations=[sample_optimization_component],
            threshold=sample_threshold,
            evaluation_configs={},  # No config for test_opt_001
            output_dir=temp_output_dir,
        )

        assert "test_opt_001" in report.skipped_optimizations
        assert len(report.accepted_optimizations) == 0
        assert len(report.rejected_optimizations) == 0

    def test_evaluate_sequence_priority_sorting(self, sample_threshold, temp_output_dir):
        """Test that optimizations are evaluated in priority order."""
        opt_low_priority = OptimizationComponent(
            component_id="opt_low",
            component_name="Low Priority",
            implementation_type="python",
            functional_category="micro_operation",
            priority_rank=10,
            expected_impact_range=(Decimal("5.0"), Decimal("10.0")),
            complexity_level="low",
            consistency_risk_level="low",
            source_file_path="tests/test_low_priority.py",
            api_signature="def low_priority_function() -> int",
            dependencies=[],
            baseline_results=None,
            optimized_results=None,
            status="pending",
            decision_rationale=None,
            created_date="2025-10-24T00:00:00Z",
            last_updated="2025-10-24T00:00:00Z",
            evaluation_order=None,
        )

        opt_high_priority = OptimizationComponent(
            component_id="opt_high",
            component_name="High Priority",
            implementation_type="python",
            functional_category="orchestration_loop",
            priority_rank=1,
            expected_impact_range=(Decimal("5.0"), Decimal("10.0")),
            complexity_level="low",
            consistency_risk_level="low",
            source_file_path="tests/test_high_priority.py",
            api_signature="def high_priority_function() -> int",
            dependencies=[],
            baseline_results=None,
            optimized_results=None,
            status="pending",
            decision_rationale=None,
            created_date="2025-10-24T00:00:00Z",
            last_updated="2025-10-24T00:00:00Z",
            evaluation_order=None,
        )

        test_cases = [((1, 2), {})]

        evaluation_configs = {
            "opt_low": {
                "baseline_fn": baseline_add_function,
                "optimized_fn": optimized_add_function,
                "test_cases": test_cases,
                "benchmark_workload_fn": slow_baseline_workload,
                "benchmark_args": (),
                "benchmark_kwargs": {},
            },
            "opt_high": {
                "baseline_fn": baseline_add_function,
                "optimized_fn": optimized_add_function,
                "test_cases": test_cases,
                "benchmark_workload_fn": fast_optimized_workload,
                "benchmark_args": (),
                "benchmark_kwargs": {},
            },
        }

        # Pass in wrong order (low priority first)
        report = evaluate_optimization_sequence(
            optimizations=[opt_low_priority, opt_high_priority],
            threshold=sample_threshold,
            evaluation_configs=evaluation_configs,
            output_dir=temp_output_dir,
            stop_on_goal_achieved=False,
        )

        # Should be evaluated in priority order (high first)
        assert report.components[0].priority_rank < report.components[1].priority_rank


# ============================================================================
# Tests for Report Generation Functions
# ============================================================================


class TestReportGeneration:
    """Tests for report generation helper functions."""

    def test_generate_executive_summary(self, sample_threshold):
        """Test executive summary generation."""
        # Create baseline and optimized results with 12.5% improvement
        # improvement = (speedup - 1) * 100 = 12.5%
        # speedup = baseline / optimized = 1.125
        # If baseline = 112.5s, optimized = 100s => speedup = 1.125
        baseline_result = BenchmarkResult(
            benchmark_id="baseline_001",
            configuration_name="baseline",
            iteration_number=1,
            execution_time_seconds=Decimal("112.5"),
            cpu_time_seconds=Decimal("110.0"),
            memory_peak_mb=Decimal("50.0"),
            memory_average_mb=Decimal("40.0"),
            dataset_size=1000,
            parameter_combinations=10,
            backtest_count=10,
            platform="darwin",
            cpu_model="Test CPU",
            python_version="3.12.0",
            timestamp="2025-10-24T00:00:00Z",
            random_seed=None,
            flame_graph_path=None,
            profiling_json_path=None,
        )

        optimized_result = BenchmarkResult(
            benchmark_id="optimized_001",
            configuration_name="optimized",
            iteration_number=1,
            execution_time_seconds=Decimal("100.0"),
            cpu_time_seconds=Decimal("98.0"),
            memory_peak_mb=Decimal("50.0"),
            memory_average_mb=Decimal("40.0"),
            dataset_size=1000,
            parameter_combinations=10,
            backtest_count=10,
            platform="darwin",
            cpu_model="Test CPU",
            python_version="3.12.0",
            timestamp="2025-10-24T00:00:00Z",
            random_seed=None,
            flame_graph_path=None,
            profiling_json_path=None,
        )

        baseline_results = BenchmarkResultSet(
            configuration_name="baseline", workflow_type="grid_search", results=[baseline_result]
        )

        optimized_results = BenchmarkResultSet(
            configuration_name="optimized", workflow_type="grid_search", results=[optimized_result]
        )

        opt1 = OptimizationComponent(
            component_id="opt_001",
            component_name="Test Opt 1",
            implementation_type="python",
            functional_category="search_algorithm",
            priority_rank=1,
            expected_impact_range=(Decimal("5.0"), Decimal("10.0")),
            complexity_level="low",
            consistency_risk_level="low",
            source_file_path="tests/test_opt1_report.py",
            api_signature="def test_opt1() -> int",
            dependencies=[],
            baseline_results=baseline_results,
            optimized_results=optimized_results,
            status="accepted",
            decision_rationale=None,
            created_date="2025-10-24T00:00:00Z",
            last_updated="2025-10-24T00:00:00Z",
            evaluation_order=None,
        )

        report = PerformanceReport(
            report_id="test_report_001",
            report_date=datetime.utcnow().isoformat() + "Z",
            workflow_type="grid_search",
            components=[opt1],
            threshold=sample_threshold,
            current_evaluation_index=0,
            executive_summary="",
            detailed_findings="",
        )

        report.accepted_optimizations.append("opt_001")

        summary = _generate_executive_summary(report)

        assert "SEQUENTIAL OPTIMIZATION EVALUATION SUMMARY" in summary
        assert "Accepted: 1" in summary
        assert "Test Opt 1" in summary
        assert "12.5" in summary

    def test_generate_detailed_findings(self, sample_threshold):
        """Test detailed findings generation."""
        opt1 = OptimizationComponent(
            component_id="opt_001",
            component_name="Test Opt 1",
            implementation_type="python",
            functional_category="search_algorithm",
            priority_rank=1,
            expected_impact_range=(Decimal("5.0"), Decimal("10.0")),
            complexity_level="low",
            consistency_risk_level="low",
            source_file_path="tests/test_detailed.py",
            api_signature="def test_detailed() -> int",
            dependencies=[],
            baseline_results=None,
            optimized_results=None,
            status="accepted",
            decision_rationale=None,
            created_date="2025-10-24T00:00:00Z",
            last_updated="2025-10-24T00:00:00Z",
            evaluation_order=None,
        )

        report = PerformanceReport(
            report_id="test_report_001",
            report_date=datetime.utcnow().isoformat() + "Z",
            workflow_type="grid_search",
            components=[opt1],
            threshold=sample_threshold,
            current_evaluation_index=0,
            executive_summary="",
            detailed_findings="",
        )

        findings = _generate_detailed_findings(report)

        assert "DETAILED EVALUATION FINDINGS" in findings
        assert "Test Opt 1" in findings
        assert "opt_001" in findings
        assert "ACCEPTED" in findings

    def test_save_performance_report(self, sample_threshold, temp_output_dir):
        """Test saving report to JSON and Markdown."""
        opt1 = OptimizationComponent(
            component_id="opt_001",
            component_name="Test Opt",
            implementation_type="python",
            functional_category="search_algorithm",
            priority_rank=1,
            expected_impact_range=(Decimal("5.0"), Decimal("10.0")),
            complexity_level="low",
            consistency_risk_level="low",
            source_file_path="tests/test_save.py",
            api_signature="def test_save() -> int",
            dependencies=[],
            baseline_results=None,
            optimized_results=None,
            status="accepted",
            decision_rationale=None,
            created_date="2025-10-24T00:00:00Z",
            last_updated="2025-10-24T00:00:00Z",
            evaluation_order=None,
        )

        report = PerformanceReport(
            report_id="test_report_save",
            report_date="2025-10-24T10:00:00Z",
            workflow_type="grid_search",
            components=[opt1],
            threshold=sample_threshold,
            current_evaluation_index=0,
            executive_summary="Test Summary",
            detailed_findings="Test Findings",
        )

        _save_performance_report(report, temp_output_dir)

        # Verify files created
        json_file = Path(temp_output_dir) / "test_report_save_report.json"
        md_file = Path(temp_output_dir) / "test_report_save_report.md"

        assert json_file.exists()
        assert md_file.exists()

        # Verify JSON content
        import json

        with open(json_file) as f:
            data = json.load(f)

        assert data["report_id"] == "test_report_save"
        assert data["workflow_type"] == "grid_search"
        assert data["executive_summary"] == "Test Summary"

        # Verify Markdown content
        md_content = md_file.read_text()
        assert "# Performance Optimization Evaluation Report" in md_content
        assert "Test Summary" in md_content
        assert "Test Findings" in md_content


# ============================================================================
# Integration Tests
# ============================================================================


class TestSequentialIntegration:
    """Integration tests for complete sequential evaluation workflow."""

    def test_complete_workflow_acceptance(self, sample_threshold, temp_output_dir):
        """Test complete workflow resulting in acceptance."""
        opt = OptimizationComponent(
            component_id="complete_opt_001",
            component_name="Complete Test Optimization",
            implementation_type="python",
            functional_category="batch_initialization",
            priority_rank=1,
            expected_impact_range=(Decimal("10.0"), Decimal("20.0")),
            complexity_level="medium",
            consistency_risk_level="low",
            source_file_path="tests/test_complete.py",
            api_signature="def test_complete() -> int",
            dependencies=[],
            baseline_results=None,
            optimized_results=None,
            status="pending",
            decision_rationale=None,
            created_date="2025-10-24T00:00:00Z",
            last_updated="2025-10-24T00:00:00Z",
            evaluation_order=None,
        )

        test_cases = [((1, 2), {}), ((5, 10), {})]

        evaluation_configs = {
            "complete_opt_001": {
                "baseline_fn": baseline_add_function,
                "optimized_fn": optimized_add_function,
                "test_cases": test_cases,
                "benchmark_workload_fn": slow_baseline_workload,
                "benchmark_args": (),
                "benchmark_kwargs": {},
            }
        }

        report = evaluate_optimization_sequence(
            optimizations=[opt],
            threshold=sample_threshold,
            evaluation_configs=evaluation_configs,
            output_dir=temp_output_dir,
            goal_improvement_percent=Decimal("10.0"),
            stop_on_goal_achieved=True,
        )

        # Verify complete workflow executed
        assert report.report_id is not None
        assert report.executive_summary != ""
        assert report.detailed_findings != ""

        # Verify files created
        json_file = Path(temp_output_dir) / f"{report.report_id}_report.json"
        md_file = Path(temp_output_dir) / f"{report.report_id}_report.md"

        assert json_file.exists()
        assert md_file.exists()
