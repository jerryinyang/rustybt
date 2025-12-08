"""
Pydantic models for stress testing scenarios and results.

Scenario types:
- network: Connection resilience and reconnection tests
- throughput: High-frequency order submission tests
- long_running: Extended stability tests (24-48 hours)
- error: API error handling and simulation tests
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Annotated, Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ScenarioType(str, Enum):
    """Stress test scenario types."""

    NETWORK = "network"
    THROUGHPUT = "throughput"
    LONG_RUNNING = "long_running"
    ERROR = "error"


class SuccessCriteria(BaseModel):
    """Success criteria for stress test validation.

    Allows flexible criteria fields based on scenario type.
    Common criteria fields:
    - all_reconnections_successful: bool (network tests)
    - max_reconnection_time_seconds: int (network tests)
    - no_data_loss: bool (network tests)
    - all_orders_tracked: bool (throughput tests)
    - no_duplicates: bool (throughput tests)
    - max_latency_ms: int (throughput tests)
    - no_crashes: bool (long_running tests)
    - memory_growth_percent_max: float (long_running tests)
    - state_integrity: bool (long_running tests)
    - all_errors_handled: bool (error tests)
    - no_unhandled_exceptions: bool (error tests)
    """

    model_config = ConfigDict(extra="allow")


class NetworkParameters(BaseModel):
    """Parameters specific to network resilience tests."""

    disconnect_count: int = Field(
        default=5, ge=1, description="Number of disconnections to simulate"
    )
    disconnect_interval_seconds: int = Field(
        default=60, ge=1, description="Time between disconnections"
    )
    max_reconnect_time_seconds: int = Field(
        default=30, ge=1, description="Maximum allowed reconnection time"
    )
    stale_connection_timeout_seconds: int = Field(
        default=60, ge=1, description="Time before connection is considered stale"
    )


class ThroughputParameters(BaseModel):
    """Parameters specific to throughput tests."""

    orders_per_second: int = Field(default=10, ge=1, description="Order submission rate")
    order_type: str = Field(default="market", description="Order type: market or limit")
    asset: str = Field(default="BTC-PERP", description="Asset symbol to trade")
    burst_count: int = Field(default=0, ge=0, description="Number of burst periods")
    burst_orders: int = Field(default=50, ge=0, description="Orders per burst")
    burst_interval_seconds: int = Field(default=30, ge=0, description="Time between bursts")


class LongRunningParameters(BaseModel):
    """Parameters specific to long-running stability tests."""

    signal_interval_seconds: int = Field(default=300, ge=1, description="Time between signals")
    memory_sample_interval_seconds: int = Field(
        default=3600, ge=1, description="Memory sampling interval"
    )
    checkpoint_interval_seconds: int = Field(
        default=3600, ge=1, description="State checkpoint interval"
    )
    state_persistence_interval_seconds: int = Field(
        default=300, ge=1, description="State persistence interval"
    )


class ErrorParameters(BaseModel):
    """Parameters specific to API error simulation tests."""

    error_types: list[str] = Field(
        default_factory=lambda: ["500", "429", "timeout", "connection_refused"],
        description="Error types to simulate",
    )
    error_probability: float = Field(
        default=0.1, ge=0.0, le=1.0, description="Probability of error injection"
    )
    recovery_timeout_seconds: int = Field(default=30, ge=1, description="Maximum recovery time")
    consecutive_error_threshold: int = Field(
        default=3, ge=1, description="Errors before circuit breaker"
    )


class StressScenario(BaseModel):
    """Stress test scenario configuration.

    Defines a complete stress test scenario including:
    - Scenario identification
    - Test type and duration
    - Type-specific parameters
    - Success/failure criteria
    """

    name: Annotated[str, Field(description="Unique scenario identifier")]
    description: Annotated[str, Field(default="", description="Human-readable description")]
    type: Annotated[ScenarioType, Field(description="Scenario type")]
    duration: Annotated[int, Field(ge=1, description="Test duration in seconds")]
    parameters: Annotated[dict[str, Any], Field(description="Type-specific parameters")]
    success_criteria: Annotated[SuccessCriteria, Field(description="Pass/fail criteria")]
    tags: Annotated[
        list[str], Field(default_factory=list, description="Optional tags for filtering")
    ]
    requires_testnet: Annotated[
        bool, Field(default=False, description="Whether test requires testnet connection")
    ]

    @field_validator("parameters", mode="before")
    @classmethod
    def validate_parameters(cls, v: dict[str, Any], info) -> dict[str, Any]:
        """Validate parameters based on scenario type."""
        # Parameters are validated at runtime during execution
        # This allows flexibility while maintaining structure
        return v

    def get_typed_parameters(
        self,
    ) -> NetworkParameters | ThroughputParameters | LongRunningParameters | ErrorParameters:
        """Get parameters as the appropriate typed model."""
        if self.type == ScenarioType.NETWORK:
            return NetworkParameters(**self.parameters)
        elif self.type == ScenarioType.THROUGHPUT:
            return ThroughputParameters(**self.parameters)
        elif self.type == ScenarioType.LONG_RUNNING:
            return LongRunningParameters(**self.parameters)
        elif self.type == ScenarioType.ERROR:
            return ErrorParameters(**self.parameters)
        else:
            raise ValueError(f"Unknown scenario type: {self.type}")

    @classmethod
    def load_from_yaml(cls, path: Path) -> StressScenario:
        """Load scenario from a YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data)

    def save_to_yaml(self, path: Path) -> None:
        """Save scenario to a YAML file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            yaml.dump(
                self.model_dump(mode="json"),
                f,
                default_flow_style=False,
                sort_keys=False,
            )


class StressTestMetrics(BaseModel):
    """Metrics collected during stress test execution.

    Flexible metrics model that allows type-specific fields.
    Common metrics:
    - reconnection_times: list[float] (network tests)
    - orders_submitted: int (throughput tests)
    - orders_filled: int (throughput tests)
    - latencies_ms: list[float] (throughput tests)
    - memory_samples_mb: list[float] (long_running tests)
    - errors_encountered: dict[str, int] (error tests)
    """

    model_config = ConfigDict(extra="allow")

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to a dictionary."""
        return self.model_dump()


class StressTestResult(BaseModel):
    """Result of a stress test execution.

    Captures the complete outcome of a stress test run including:
    - Timing information
    - Pass/fail status
    - Collected metrics
    - Any errors encountered
    """

    scenario_name: Annotated[str, Field(description="Name of the executed scenario")]
    scenario_type: Annotated[ScenarioType, Field(description="Type of the scenario")]
    start_time: Annotated[str, Field(description="ISO format start timestamp")]
    end_time: Annotated[str, Field(description="ISO format end timestamp")]
    duration_seconds: Annotated[float, Field(ge=0, description="Actual test duration")]
    passed: Annotated[bool, Field(description="Whether test passed all criteria")]
    metrics: Annotated[dict[str, Any], Field(default_factory=dict, description="Collected metrics")]
    errors: Annotated[
        list[str], Field(default_factory=list, description="Error messages encountered")
    ]
    criteria_results: Annotated[
        dict[str, bool], Field(default_factory=dict, description="Individual criteria pass/fail")
    ]
    environment: Annotated[
        dict[str, str], Field(default_factory=dict, description="Test environment info")
    ]

    @classmethod
    def create(
        cls,
        scenario: StressScenario,
        start_time: datetime,
        end_time: datetime,
        passed: bool,
        metrics: dict[str, Any],
        errors: list[str] | None = None,
        criteria_results: dict[str, bool] | None = None,
    ) -> StressTestResult:
        """Factory method to create a result from scenario and execution data."""
        import platform

        return cls(
            scenario_name=scenario.name,
            scenario_type=scenario.type,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            duration_seconds=(end_time - start_time).total_seconds(),
            passed=passed,
            metrics=metrics,
            errors=errors or [],
            criteria_results=criteria_results or {},
            environment={
                "python_version": platform.python_version(),
                "platform": platform.platform(),
                "hostname": platform.node(),
            },
        )

    def save_to_json(self, path: Path) -> None:
        """Save result to a JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.model_dump(mode="json"), f, indent=2)

    @classmethod
    def load_from_json(cls, path: Path) -> StressTestResult:
        """Load result from a JSON file."""
        with open(path) as f:
            data = json.load(f)
        return cls.model_validate(data)


class ResultsFile(BaseModel):
    """Collection of stress test results."""

    results: list[StressTestResult] = Field(default_factory=list)
    generated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    def add_result(self, result: StressTestResult) -> None:
        """Add a result to the collection."""
        self.results.append(result)

    def filter_by_scenario(self, scenario_name: str) -> list[StressTestResult]:
        """Filter results by scenario name."""
        return [r for r in self.results if r.scenario_name == scenario_name]

    def filter_by_type(self, scenario_type: ScenarioType) -> list[StressTestResult]:
        """Filter results by scenario type."""
        return [r for r in self.results if r.scenario_type == scenario_type]

    def filter_passed(self) -> list[StressTestResult]:
        """Get only passing results."""
        return [r for r in self.results if r.passed]

    def filter_failed(self) -> list[StressTestResult]:
        """Get only failing results."""
        return [r for r in self.results if not r.passed]

    def summary(self) -> dict[str, Any]:
        """Generate a summary of all results."""
        return {
            "total": len(self.results),
            "passed": len(self.filter_passed()),
            "failed": len(self.filter_failed()),
            "by_type": {t.value: len(self.filter_by_type(t)) for t in ScenarioType},
            "pass_rate": len(self.filter_passed()) / len(self.results) if self.results else 0,
        }

    def save_to_json(self, path: Path) -> None:
        """Save all results to a JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.model_dump(mode="json"), f, indent=2)

    @classmethod
    def load_from_json(cls, path: Path) -> ResultsFile:
        """Load results from a JSON file."""
        if not path.exists():
            return cls()
        with open(path) as f:
            data = json.load(f)
        return cls.model_validate(data)
