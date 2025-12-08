"""
Pytest fixtures for stress testing infrastructure.

Provides fixtures to:
- Load stress test scenarios from YAML files
- Execute stress test scenarios
- Validate results against success criteria
- Generate result files
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from tests.live.stress.models import (
    ResultsFile,
    ScenarioType,
    StressScenario,
    StressTestResult,
    SuccessCriteria,
)

if TYPE_CHECKING:
    from collections.abc import Callable


# Path to scenarios directory
SCENARIOS_DIR = Path(__file__).parent / "scenarios"
RESULTS_DIR = Path(__file__).parent / "results"


@pytest.fixture
def scenarios_dir() -> Path:
    """Return the path to the scenarios directory."""
    return SCENARIOS_DIR


@pytest.fixture
def results_dir() -> Path:
    """Return the path to the results directory."""
    return RESULTS_DIR


@pytest.fixture
def load_scenario() -> Callable[[str], StressScenario]:
    """Fixture factory to load a scenario by name.

    Usage:
        def test_example(load_scenario):
            scenario = load_scenario("network_disconnect")
            assert scenario.type == ScenarioType.NETWORK
    """

    def _load(scenario_name: str) -> StressScenario:
        # Try with and without .yaml extension
        yaml_path = SCENARIOS_DIR / f"{scenario_name}.yaml"
        if not yaml_path.exists():
            yaml_path = SCENARIOS_DIR / scenario_name
        if not yaml_path.exists():
            raise FileNotFoundError(f"Scenario file not found: {scenario_name}")
        return StressScenario.load_from_yaml(yaml_path)

    return _load


@pytest.fixture
def load_all_scenarios() -> Callable[[], list[StressScenario]]:
    """Fixture factory to load all available scenarios."""

    def _load() -> list[StressScenario]:
        scenarios = []
        for yaml_file in SCENARIOS_DIR.glob("*.yaml"):
            scenarios.append(StressScenario.load_from_yaml(yaml_file))
        return scenarios

    return _load


@pytest.fixture
def scenarios_by_type() -> Callable[[ScenarioType], list[StressScenario]]:
    """Fixture factory to filter scenarios by type."""

    def _filter(scenario_type: ScenarioType) -> list[StressScenario]:
        scenarios = []
        for yaml_file in SCENARIOS_DIR.glob("*.yaml"):
            scenario = StressScenario.load_from_yaml(yaml_file)
            if scenario.type == scenario_type:
                scenarios.append(scenario)
        return scenarios

    return _filter


@pytest.fixture
def validate_results() -> Callable[[dict[str, Any], SuccessCriteria], tuple[bool, dict[str, bool]]]:
    """Fixture factory to validate results against success criteria.

    Returns a tuple of (overall_passed, criteria_results) where:
    - overall_passed: True if all criteria pass
    - criteria_results: Dict mapping criterion name to pass/fail

    Usage:
        def test_example(validate_results):
            results = {"reconnection_times": [5, 10, 8]}
            criteria = SuccessCriteria(max_reconnection_time_seconds=30)
            passed, details = validate_results(results, criteria)
    """

    def _validate(
        results: dict[str, Any], criteria: SuccessCriteria
    ) -> tuple[bool, dict[str, bool]]:
        criteria_dict = criteria.model_dump(exclude_none=True)
        criteria_results = {}
        all_passed = True

        for criterion, expected in criteria_dict.items():
            if criterion.startswith("_"):
                continue

            # Handle different criterion types
            if criterion == "all_reconnections_successful":
                # Check if all reconnections completed
                reconnection_times = results.get("reconnection_times", [])
                failed_reconnections = results.get("failed_reconnections", 0)
                passed = failed_reconnections == 0 and len(reconnection_times) > 0
            elif criterion == "max_reconnection_time_seconds":
                # Check max reconnection time
                reconnection_times = results.get("reconnection_times", [])
                passed = (
                    all(t <= expected for t in reconnection_times) if reconnection_times else True
                )
            elif criterion == "no_data_loss":
                # Check for data loss
                data_loss = results.get("data_loss", False)
                passed = not data_loss
            elif criterion == "all_orders_tracked":
                # Check order tracking
                orders_submitted = results.get("orders_submitted", 0)
                orders_tracked = results.get("orders_tracked", 0)
                passed = orders_submitted == orders_tracked
            elif criterion == "no_duplicates":
                # Check for duplicate orders
                duplicate_count = results.get("duplicate_orders", 0)
                passed = duplicate_count == 0
            elif criterion == "max_latency_ms":
                # Check latency threshold
                latencies = results.get("latencies_ms", [])
                passed = all(l <= expected for l in latencies) if latencies else True
            elif criterion == "no_crashes":
                # Check for crashes
                crash_count = results.get("crash_count", 0)
                passed = crash_count == 0
            elif criterion == "memory_growth_percent_max":
                # Check memory growth
                memory_growth_percent = results.get("memory_growth_percent", 0)
                passed = memory_growth_percent <= expected
            elif criterion == "state_integrity":
                # Check state integrity
                state_corrupted = results.get("state_corrupted", False)
                passed = not state_corrupted
            elif criterion == "all_errors_handled":
                # Check error handling
                unhandled_errors = results.get("unhandled_errors", 0)
                passed = unhandled_errors == 0
            elif criterion == "no_unhandled_exceptions":
                # Check for unhandled exceptions
                exception_count = results.get("unhandled_exception_count", 0)
                passed = exception_count == 0
            elif criterion == "circuit_breaker_triggered":
                # Check if circuit breaker was triggered when expected
                cb_triggered = results.get("circuit_breaker_triggered", False)
                passed = cb_triggered == expected
            elif criterion == "recovery_successful":
                # Check if recovery was successful
                recovery_success = results.get("recovery_successful", False)
                passed = recovery_success == expected
            else:
                # Generic comparison for unknown criteria
                actual = results.get(criterion)
                if isinstance(expected, bool):
                    passed = actual == expected
                elif isinstance(expected, (int, float)):
                    passed = actual is not None and actual <= expected
                else:
                    passed = actual == expected

            criteria_results[criterion] = passed
            if not passed:
                all_passed = False

        return all_passed, criteria_results

    return _validate


@pytest.fixture
def execute_scenario() -> Callable[[StressScenario, Any], StressTestResult]:
    """Fixture factory to execute a stress test scenario.

    This is a placeholder that delegates to type-specific executors.
    Actual test implementations should use this fixture and provide
    the appropriate executor or broker.

    Usage:
        async def test_network(execute_scenario, paper_broker):
            scenario = load_scenario("network_disconnect")
            result = await execute_scenario(scenario, paper_broker)
            assert result.passed
    """

    async def _execute(scenario: StressScenario, executor: Any = None) -> StressTestResult:
        """Execute a scenario and return results.

        This is a base implementation that can be overridden or extended
        by specific test modules.
        """
        start_time = datetime.now()
        metrics: dict[str, Any] = {}
        errors: list[str] = []
        criteria_results: dict[str, bool] = {}

        try:
            # Type-specific execution logic
            if scenario.type == ScenarioType.NETWORK:
                metrics, errors = await _execute_network_scenario(scenario, executor)
            elif scenario.type == ScenarioType.THROUGHPUT:
                metrics, errors = await _execute_throughput_scenario(scenario, executor)
            elif scenario.type == ScenarioType.LONG_RUNNING:
                metrics, errors = await _execute_long_running_scenario(scenario, executor)
            elif scenario.type == ScenarioType.ERROR:
                metrics, errors = await _execute_error_scenario(scenario, executor)

            # Validate against criteria
            from tests.live.stress.conftest import _validate_criteria

            passed, criteria_results = _validate_criteria(metrics, scenario.success_criteria)

        except Exception as e:
            errors.append(f"Execution error: {str(e)}")
            passed = False

        end_time = datetime.now()

        return StressTestResult.create(
            scenario=scenario,
            start_time=start_time,
            end_time=end_time,
            passed=passed,
            metrics=metrics,
            errors=errors,
            criteria_results=criteria_results,
        )

    return _execute


async def _execute_network_scenario(
    scenario: StressScenario, executor: Any
) -> tuple[dict[str, Any], list[str]]:
    """Execute a network resilience scenario."""
    params = scenario.get_typed_parameters()
    metrics: dict[str, Any] = {
        "reconnection_times": [],
        "failed_reconnections": 0,
        "data_loss": False,
    }
    errors: list[str] = []

    # Placeholder implementation - actual tests implement specific logic
    # This provides the structure for scenario execution

    return metrics, errors


async def _execute_throughput_scenario(
    scenario: StressScenario, executor: Any
) -> tuple[dict[str, Any], list[str]]:
    """Execute a throughput test scenario."""
    params = scenario.get_typed_parameters()
    metrics: dict[str, Any] = {
        "orders_submitted": 0,
        "orders_tracked": 0,
        "orders_filled": 0,
        "duplicate_orders": 0,
        "latencies_ms": [],
    }
    errors: list[str] = []

    return metrics, errors


async def _execute_long_running_scenario(
    scenario: StressScenario, executor: Any
) -> tuple[dict[str, Any], list[str]]:
    """Execute a long-running stability scenario."""
    params = scenario.get_typed_parameters()
    metrics: dict[str, Any] = {
        "crash_count": 0,
        "memory_samples_mb": [],
        "memory_growth_percent": 0.0,
        "state_corrupted": False,
        "checkpoints_saved": 0,
    }
    errors: list[str] = []

    return metrics, errors


async def _execute_error_scenario(
    scenario: StressScenario, executor: Any
) -> tuple[dict[str, Any], list[str]]:
    """Execute an API error simulation scenario."""
    params = scenario.get_typed_parameters()
    metrics: dict[str, Any] = {
        "errors_injected": 0,
        "errors_handled": 0,
        "unhandled_errors": 0,
        "unhandled_exception_count": 0,
        "circuit_breaker_triggered": False,
        "recovery_successful": True,
    }
    errors: list[str] = []

    return metrics, errors


def _validate_criteria(
    results: dict[str, Any], criteria: SuccessCriteria
) -> tuple[bool, dict[str, bool]]:
    """Internal criteria validation function."""
    criteria_dict = criteria.model_dump(exclude_none=True)
    criteria_results = {}
    all_passed = True

    for criterion, expected in criteria_dict.items():
        if criterion.startswith("_"):
            continue

        # Handle different criterion types (same logic as fixture)
        if criterion == "all_reconnections_successful":
            reconnection_times = results.get("reconnection_times", [])
            failed_reconnections = results.get("failed_reconnections", 0)
            passed = failed_reconnections == 0 and len(reconnection_times) > 0
        elif criterion == "max_reconnection_time_seconds":
            reconnection_times = results.get("reconnection_times", [])
            passed = all(t <= expected for t in reconnection_times) if reconnection_times else True
        elif criterion == "no_data_loss":
            data_loss = results.get("data_loss", False)
            passed = not data_loss
        elif criterion == "all_orders_tracked":
            orders_submitted = results.get("orders_submitted", 0)
            orders_tracked = results.get("orders_tracked", 0)
            passed = orders_submitted == orders_tracked
        elif criterion == "no_duplicates":
            duplicate_count = results.get("duplicate_orders", 0)
            passed = duplicate_count == 0
        elif criterion == "max_latency_ms":
            latencies = results.get("latencies_ms", [])
            passed = all(lat <= expected for lat in latencies) if latencies else True
        elif criterion == "no_crashes":
            crash_count = results.get("crash_count", 0)
            passed = crash_count == 0
        elif criterion == "memory_growth_percent_max":
            memory_growth_percent = results.get("memory_growth_percent", 0)
            passed = memory_growth_percent <= expected
        elif criterion == "state_integrity":
            state_corrupted = results.get("state_corrupted", False)
            passed = not state_corrupted
        elif criterion == "all_errors_handled":
            unhandled_errors = results.get("unhandled_errors", 0)
            passed = unhandled_errors == 0
        elif criterion == "no_unhandled_exceptions":
            exception_count = results.get("unhandled_exception_count", 0)
            passed = exception_count == 0
        elif criterion == "circuit_breaker_triggered":
            cb_triggered = results.get("circuit_breaker_triggered", False)
            passed = cb_triggered == expected
        elif criterion == "recovery_successful":
            recovery_success = results.get("recovery_successful", False)
            passed = recovery_success == expected
        else:
            actual = results.get(criterion)
            if isinstance(expected, bool):
                passed = actual == expected
            elif isinstance(expected, (int, float)):
                passed = actual is not None and actual <= expected
            else:
                passed = actual == expected

        criteria_results[criterion] = passed
        if not passed:
            all_passed = False

    return all_passed, criteria_results


@pytest.fixture
def save_result() -> Callable[[StressTestResult, str | None], Path]:
    """Fixture factory to save a test result to JSON.

    Usage:
        def test_example(save_result, execute_scenario):
            result = await execute_scenario(scenario, broker)
            result_path = save_result(result)
    """

    def _save(result: StressTestResult, filename: str | None = None) -> Path:
        if filename is None:
            # Generate filename from scenario and timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{result.scenario_name}_{timestamp}.json"

        result_path = RESULTS_DIR / filename
        result.save_to_json(result_path)
        return result_path

    return _save


@pytest.fixture
def load_results() -> Callable[[str | None], ResultsFile]:
    """Fixture factory to load results from a file."""

    def _load(filename: str | None = None) -> ResultsFile:
        if filename is None:
            filename = "all_results.json"
        return ResultsFile.load_from_json(RESULTS_DIR / filename)

    return _load


@pytest.fixture
def aggregate_results() -> Callable[[], ResultsFile]:
    """Fixture factory to aggregate all individual result files."""

    def _aggregate() -> ResultsFile:
        aggregated = ResultsFile()
        for json_file in RESULTS_DIR.glob("*.json"):
            if json_file.name == "all_results.json":
                continue
            try:
                result = StressTestResult.load_from_json(json_file)
                aggregated.add_result(result)
            except Exception:
                # Skip malformed result files
                pass
        return aggregated

    return _aggregate


# Marker for slow/long-running stress tests
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "stress: mark test as a stress test (may take longer)")
    config.addinivalue_line("markers", "slow: mark test as slow (24h+ duration)")
    config.addinivalue_line(
        "markers", "requires_testnet: mark test as requiring testnet connection"
    )
