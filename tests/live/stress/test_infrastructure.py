"""
Tests for stress testing infrastructure.

Validates:
- Scenario loading from YAML
- Schema validation
- Result serialization
- Fixture availability
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.live.stress.models import (
    ErrorParameters,
    LongRunningParameters,
    NetworkParameters,
    ResultsFile,
    ScenarioType,
    StressScenario,
    StressTestResult,
    SuccessCriteria,
    ThroughputParameters,
)

if TYPE_CHECKING:
    from collections.abc import Callable


class TestScenarioLoading:
    """Tests for loading scenarios from YAML files."""

    def test_load_network_scenario(self, load_scenario: Callable[[str], StressScenario]) -> None:
        """Test loading a network disconnect scenario."""
        scenario = load_scenario("network_disconnect")

        assert scenario.name == "network_disconnect_recovery"
        assert scenario.type == ScenarioType.NETWORK
        assert scenario.duration == 300
        assert "network" in scenario.tags

    def test_load_throughput_scenario(self, load_scenario: Callable[[str], StressScenario]) -> None:
        """Test loading a throughput scenario."""
        scenario = load_scenario("high_throughput")

        assert scenario.name == "order_burst_test"
        assert scenario.type == ScenarioType.THROUGHPUT
        assert scenario.duration == 60

    def test_load_long_running_scenario(
        self, load_scenario: Callable[[str], StressScenario]
    ) -> None:
        """Test loading a long-running scenario."""
        scenario = load_scenario("long_running_24h")

        assert scenario.name == "stability_24h"
        assert scenario.type == ScenarioType.LONG_RUNNING
        assert scenario.duration == 86400  # 24 hours

    def test_load_error_scenario(self, load_scenario: Callable[[str], StressScenario]) -> None:
        """Test loading an error simulation scenario."""
        scenario = load_scenario("api_error_simulation")

        assert scenario.name == "api_error_handling"
        assert scenario.type == ScenarioType.ERROR
        assert scenario.duration == 300

    def test_load_all_scenarios(
        self, load_all_scenarios: Callable[[], list[StressScenario]]
    ) -> None:
        """Test loading all scenarios."""
        scenarios = load_all_scenarios()

        assert len(scenarios) >= 4
        types = {s.type for s in scenarios}
        assert ScenarioType.NETWORK in types
        assert ScenarioType.THROUGHPUT in types
        assert ScenarioType.LONG_RUNNING in types
        assert ScenarioType.ERROR in types

    def test_scenarios_by_type(
        self, scenarios_by_type: Callable[[ScenarioType], list[StressScenario]]
    ) -> None:
        """Test filtering scenarios by type."""
        network_scenarios = scenarios_by_type(ScenarioType.NETWORK)

        assert len(network_scenarios) >= 1
        for scenario in network_scenarios:
            assert scenario.type == ScenarioType.NETWORK

    def test_load_nonexistent_scenario_raises(
        self, load_scenario: Callable[[str], StressScenario]
    ) -> None:
        """Test that loading a nonexistent scenario raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_scenario("nonexistent_scenario")


class TestSchemaValidation:
    """Tests for scenario schema validation."""

    def test_network_parameters_typed(self, load_scenario: Callable[[str], StressScenario]) -> None:
        """Test that network scenario parameters parse to NetworkParameters."""
        scenario = load_scenario("network_disconnect")
        params = scenario.get_typed_parameters()

        assert isinstance(params, NetworkParameters)
        assert params.disconnect_count == 5
        assert params.disconnect_interval_seconds == 60
        assert params.max_reconnect_time_seconds == 30

    def test_throughput_parameters_typed(
        self, load_scenario: Callable[[str], StressScenario]
    ) -> None:
        """Test that throughput scenario parameters parse to ThroughputParameters."""
        scenario = load_scenario("high_throughput")
        params = scenario.get_typed_parameters()

        assert isinstance(params, ThroughputParameters)
        assert params.orders_per_second == 10
        assert params.order_type == "market"
        assert params.asset == "BTC-PERP"

    def test_long_running_parameters_typed(
        self, load_scenario: Callable[[str], StressScenario]
    ) -> None:
        """Test that long-running scenario parameters parse to LongRunningParameters."""
        scenario = load_scenario("long_running_24h")
        params = scenario.get_typed_parameters()

        assert isinstance(params, LongRunningParameters)
        assert params.signal_interval_seconds == 300
        assert params.memory_sample_interval_seconds == 3600

    def test_error_parameters_typed(self, load_scenario: Callable[[str], StressScenario]) -> None:
        """Test that error scenario parameters parse to ErrorParameters."""
        scenario = load_scenario("api_error_simulation")
        params = scenario.get_typed_parameters()

        assert isinstance(params, ErrorParameters)
        assert "500" in params.error_types
        assert "429" in params.error_types
        assert params.error_probability == 0.1

    def test_success_criteria_parsed(self, load_scenario: Callable[[str], StressScenario]) -> None:
        """Test that success criteria are properly parsed."""
        scenario = load_scenario("network_disconnect")
        criteria = scenario.success_criteria

        assert isinstance(criteria, SuccessCriteria)
        criteria_dict = criteria.model_dump()
        assert criteria_dict.get("all_reconnections_successful") is True
        assert criteria_dict.get("max_reconnection_time_seconds") == 30

    def test_invalid_scenario_type_fails(self, tmp_path: Path) -> None:
        """Test that invalid scenario type fails validation."""
        invalid_yaml = tmp_path / "invalid.yaml"
        invalid_yaml.write_text(
            """
name: invalid_test
type: invalid_type
duration: 60
parameters: {}
success_criteria: {}
"""
        )

        with pytest.raises(Exception):  # Pydantic validation error
            StressScenario.load_from_yaml(invalid_yaml)

    def test_negative_duration_fails(self, tmp_path: Path) -> None:
        """Test that negative duration fails validation."""
        invalid_yaml = tmp_path / "invalid_duration.yaml"
        invalid_yaml.write_text(
            """
name: invalid_duration_test
type: network
duration: -1
parameters: {}
success_criteria: {}
"""
        )

        with pytest.raises(Exception):  # Pydantic validation error
            StressScenario.load_from_yaml(invalid_yaml)


class TestResultSerialization:
    """Tests for result serialization to JSON."""

    def test_result_creation(self, load_scenario: Callable[[str], StressScenario]) -> None:
        """Test creating a StressTestResult."""
        scenario = load_scenario("network_disconnect")
        start_time = datetime.now()
        end_time = datetime.now()

        result = StressTestResult.create(
            scenario=scenario,
            start_time=start_time,
            end_time=end_time,
            passed=True,
            metrics={"reconnection_times": [5, 10, 8]},
            errors=[],
            criteria_results={"all_reconnections_successful": True},
        )

        assert result.scenario_name == "network_disconnect_recovery"
        assert result.scenario_type == ScenarioType.NETWORK
        assert result.passed is True
        assert result.metrics["reconnection_times"] == [5, 10, 8]

    def test_result_save_and_load(
        self, load_scenario: Callable[[str], StressScenario], tmp_path: Path
    ) -> None:
        """Test saving and loading a result from JSON."""
        scenario = load_scenario("network_disconnect")
        start_time = datetime.now()
        end_time = datetime.now()

        result = StressTestResult.create(
            scenario=scenario,
            start_time=start_time,
            end_time=end_time,
            passed=True,
            metrics={"reconnection_times": [5, 10, 8]},
        )

        # Save to JSON
        json_path = tmp_path / "test_result.json"
        result.save_to_json(json_path)

        # Load and verify
        loaded = StressTestResult.load_from_json(json_path)
        assert loaded.scenario_name == result.scenario_name
        assert loaded.passed == result.passed
        assert loaded.metrics == result.metrics

    def test_result_json_structure(
        self, load_scenario: Callable[[str], StressScenario], tmp_path: Path
    ) -> None:
        """Test that JSON output has expected structure."""
        scenario = load_scenario("high_throughput")
        start_time = datetime.now()
        end_time = datetime.now()

        result = StressTestResult.create(
            scenario=scenario,
            start_time=start_time,
            end_time=end_time,
            passed=False,
            metrics={"orders_submitted": 100, "latencies_ms": [50, 60, 70]},
            errors=["Test error"],
        )

        json_path = tmp_path / "structured_result.json"
        result.save_to_json(json_path)

        # Verify JSON structure
        with open(json_path) as f:
            data = json.load(f)

        assert "scenario_name" in data
        assert "scenario_type" in data
        assert "start_time" in data
        assert "end_time" in data
        assert "duration_seconds" in data
        assert "passed" in data
        assert "metrics" in data
        assert "errors" in data
        assert "environment" in data

    def test_results_file_aggregation(
        self, load_scenario: Callable[[str], StressScenario], tmp_path: Path
    ) -> None:
        """Test aggregating multiple results into ResultsFile."""
        results_file = ResultsFile()

        # Add multiple results
        for scenario_name in ["network_disconnect", "high_throughput"]:
            scenario = load_scenario(scenario_name)
            result = StressTestResult.create(
                scenario=scenario,
                start_time=datetime.now(),
                end_time=datetime.now(),
                passed=True,
                metrics={},
            )
            results_file.add_result(result)

        assert len(results_file.results) == 2
        assert len(results_file.filter_passed()) == 2
        assert len(results_file.filter_failed()) == 0

    def test_results_file_summary(self, load_scenario: Callable[[str], StressScenario]) -> None:
        """Test ResultsFile summary generation."""
        results_file = ResultsFile()

        # Add passing and failing results
        network_scenario = load_scenario("network_disconnect")
        throughput_scenario = load_scenario("high_throughput")

        results_file.add_result(
            StressTestResult.create(
                scenario=network_scenario,
                start_time=datetime.now(),
                end_time=datetime.now(),
                passed=True,
                metrics={},
            )
        )
        results_file.add_result(
            StressTestResult.create(
                scenario=throughput_scenario,
                start_time=datetime.now(),
                end_time=datetime.now(),
                passed=False,
                metrics={},
            )
        )

        summary = results_file.summary()
        assert summary["total"] == 2
        assert summary["passed"] == 1
        assert summary["failed"] == 1
        assert summary["pass_rate"] == 0.5


class TestResultValidation:
    """Tests for validating results against success criteria."""

    def test_validate_network_success(self, validate_results: Callable) -> None:
        """Test validation passes for successful network metrics."""
        metrics = {
            "reconnection_times": [5, 10, 8],
            "failed_reconnections": 0,
            "data_loss": False,
        }
        criteria = SuccessCriteria(
            all_reconnections_successful=True,
            max_reconnection_time_seconds=30,
            no_data_loss=True,
        )

        passed, results = validate_results(metrics, criteria)

        assert passed is True
        assert results["all_reconnections_successful"] is True
        assert results["max_reconnection_time_seconds"] is True
        assert results["no_data_loss"] is True

    def test_validate_network_failure(self, validate_results: Callable) -> None:
        """Test validation fails for unsuccessful network metrics."""
        metrics = {
            "reconnection_times": [5, 35, 8],  # 35 > 30 threshold
            "failed_reconnections": 0,
            "data_loss": False,
        }
        criteria = SuccessCriteria(
            all_reconnections_successful=True,
            max_reconnection_time_seconds=30,
            no_data_loss=True,
        )

        passed, results = validate_results(metrics, criteria)

        assert passed is False
        assert results["max_reconnection_time_seconds"] is False

    def test_validate_throughput_success(self, validate_results: Callable) -> None:
        """Test validation passes for successful throughput metrics."""
        metrics = {
            "orders_submitted": 100,
            "orders_tracked": 100,
            "duplicate_orders": 0,
            "latencies_ms": [50, 60, 70, 80],
        }
        criteria = SuccessCriteria(
            all_orders_tracked=True,
            no_duplicates=True,
            max_latency_ms=100,
        )

        passed, results = validate_results(metrics, criteria)

        assert passed is True

    def test_validate_throughput_failure_duplicates(self, validate_results: Callable) -> None:
        """Test validation fails when duplicates exist."""
        metrics = {
            "orders_submitted": 100,
            "orders_tracked": 100,
            "duplicate_orders": 2,
            "latencies_ms": [50, 60, 70],
        }
        criteria = SuccessCriteria(
            all_orders_tracked=True,
            no_duplicates=True,
            max_latency_ms=100,
        )

        passed, results = validate_results(metrics, criteria)

        assert passed is False
        assert results["no_duplicates"] is False

    def test_validate_long_running_success(self, validate_results: Callable) -> None:
        """Test validation passes for stable long-running metrics."""
        metrics = {
            "crash_count": 0,
            "memory_growth_percent": 5.0,
            "state_corrupted": False,
        }
        criteria = SuccessCriteria(
            no_crashes=True,
            memory_growth_percent_max=10,
            state_integrity=True,
        )

        passed, results = validate_results(metrics, criteria)

        assert passed is True

    def test_validate_long_running_memory_failure(self, validate_results: Callable) -> None:
        """Test validation fails when memory growth exceeds threshold."""
        metrics = {
            "crash_count": 0,
            "memory_growth_percent": 15.0,  # > 10% threshold
            "state_corrupted": False,
        }
        criteria = SuccessCriteria(
            no_crashes=True,
            memory_growth_percent_max=10,
            state_integrity=True,
        )

        passed, results = validate_results(metrics, criteria)

        assert passed is False
        assert results["memory_growth_percent_max"] is False

    def test_validate_error_handling_success(self, validate_results: Callable) -> None:
        """Test validation passes for proper error handling."""
        metrics = {
            "unhandled_errors": 0,
            "unhandled_exception_count": 0,
            "circuit_breaker_triggered": True,
            "recovery_successful": True,
        }
        criteria = SuccessCriteria(
            all_errors_handled=True,
            no_unhandled_exceptions=True,
            circuit_breaker_triggered=True,
            recovery_successful=True,
        )

        passed, results = validate_results(metrics, criteria)

        assert passed is True


class TestFixtureAvailability:
    """Tests that all required fixtures are available."""

    def test_scenarios_dir_fixture(self, scenarios_dir: Path) -> None:
        """Test scenarios_dir fixture returns valid path."""
        assert scenarios_dir.exists()
        assert scenarios_dir.is_dir()

    def test_results_dir_fixture(self, results_dir: Path) -> None:
        """Test results_dir fixture returns valid path."""
        # Results dir may not exist until first test run
        assert results_dir.parent.exists()

    def test_load_scenario_fixture(self, load_scenario: Callable) -> None:
        """Test load_scenario fixture is callable."""
        assert callable(load_scenario)

    def test_load_all_scenarios_fixture(self, load_all_scenarios: Callable) -> None:
        """Test load_all_scenarios fixture is callable."""
        assert callable(load_all_scenarios)

    def test_scenarios_by_type_fixture(self, scenarios_by_type: Callable) -> None:
        """Test scenarios_by_type fixture is callable."""
        assert callable(scenarios_by_type)

    def test_validate_results_fixture(self, validate_results: Callable) -> None:
        """Test validate_results fixture is callable."""
        assert callable(validate_results)

    def test_execute_scenario_fixture(self, execute_scenario: Callable) -> None:
        """Test execute_scenario fixture is callable."""
        assert callable(execute_scenario)

    def test_save_result_fixture(self, save_result: Callable) -> None:
        """Test save_result fixture is callable."""
        assert callable(save_result)


class TestScenarioSaveAndReload:
    """Tests for saving and reloading scenarios."""

    def test_scenario_round_trip(self, tmp_path: Path) -> None:
        """Test that a scenario can be saved and reloaded."""
        scenario = StressScenario(
            name="test_scenario",
            description="Test scenario for round-trip",
            type=ScenarioType.NETWORK,
            duration=120,
            parameters={"disconnect_count": 3},
            success_criteria=SuccessCriteria(all_reconnections_successful=True),
        )

        yaml_path = tmp_path / "test_scenario.yaml"
        scenario.save_to_yaml(yaml_path)

        loaded = StressScenario.load_from_yaml(yaml_path)

        assert loaded.name == scenario.name
        assert loaded.type == scenario.type
        assert loaded.duration == scenario.duration
        assert loaded.parameters == scenario.parameters
