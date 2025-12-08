# Story 10.3.1: Stress Testing Infrastructure & Scenario Configuration

Status: done

## Story

As a **developer**,
I want **a stress testing infrastructure with configurable YAML scenarios**,
So that **I can run repeatable stress tests with different parameters**.

## Acceptance Criteria

1. **AC1:** Stress testing directory structure is created:
   - `tests/live/stress/` directory with `__init__.py`, `conftest.py`
   - `tests/live/stress/scenarios/` for YAML scenario definitions

2. **AC2:** Scenario YAML schema supports all test types:
   - `name`: Scenario identifier
   - `type`: network | throughput | long_running | error
   - `duration`: Test duration in seconds
   - `parameters`: Type-specific parameters
   - `success_criteria`: Pass/fail thresholds

3. **AC3:** Pytest fixtures for loading and executing scenarios are available:
   - Fixture to load scenario from YAML
   - Fixture to execute scenario
   - Fixture to validate results against success criteria

4. **AC4:** A sample scenario file demonstrates the schema for each type

5. **AC5:** Stress test results are logged in structured JSON format:
   - `start_time`, `end_time`
   - `pass`/`fail` status
   - Metrics (reconnection_time, memory_usage, order_count, etc.)

## Tasks / Subtasks

- [x] Task 1: Create stress testing directory structure (AC: #1)
  - [x] Create `tests/live/stress/` directory
  - [x] Create `tests/live/stress/__init__.py`
  - [x] Create `tests/live/stress/scenarios/` directory
  - [x] Create `tests/live/stress/results/` directory for output

- [x] Task 2: Define scenario schema (AC: #2)
  - [x] Create `tests/live/stress/models.py` with Pydantic models
  - [x] Define `StressScenario` model with all fields
  - [x] Define type-specific parameter models
  - [x] Define success criteria model

- [x] Task 3: Create pytest fixtures (AC: #3)
  - [x] Create `conftest.py` with scenario loading
  - [x] Create `load_scenario(name)` fixture
  - [x] Create `execute_scenario(scenario)` fixture
  - [x] Create `validate_results(results, criteria)` fixture

- [x] Task 4: Create sample scenarios (AC: #4)
  - [x] Create `network_disconnect.yaml` sample
  - [x] Create `high_throughput.yaml` sample
  - [x] Create `long_running_24h.yaml` sample
  - [x] Create `api_error_simulation.yaml` sample

- [x] Task 5: Implement JSON result logging (AC: #5)
  - [x] Create `StressTestResult` model
  - [x] Implement result serialization to JSON
  - [x] Create result file naming convention
  - [x] Create result aggregation utilities

- [x] Task 6: Write infrastructure tests (AC: #1-5)
  - [x] Test scenario loading from YAML
  - [x] Test schema validation
  - [x] Test result serialization
  - [x] Test fixture availability

## Dev Notes

### Scenario YAML Schema

```yaml
# tests/live/stress/scenarios/network_disconnect.yaml
name: network_disconnect_recovery
type: network
duration: 300  # 5 minutes
parameters:
  disconnect_count: 5
  disconnect_interval_seconds: 60
  max_reconnect_time_seconds: 30
success_criteria:
  all_reconnections_successful: true
  max_reconnection_time_seconds: 30
  no_data_loss: true
```

```yaml
# tests/live/stress/scenarios/high_throughput.yaml
name: order_burst_test
type: throughput
duration: 60  # 1 minute
parameters:
  orders_per_second: 10
  order_type: market
  asset: BTC-PERP
success_criteria:
  all_orders_tracked: true
  no_duplicates: true
  max_latency_ms: 100
```

```yaml
# tests/live/stress/scenarios/long_running_24h.yaml
name: stability_24h
type: long_running
duration: 86400  # 24 hours
parameters:
  signal_interval_seconds: 300  # Signal every 5 minutes
  memory_sample_interval_seconds: 3600  # Hourly samples
success_criteria:
  no_crashes: true
  memory_growth_percent_max: 10
  state_integrity: true
```

### Pydantic Models

```python
from pydantic import BaseModel
from typing import Literal, Any

class SuccessCriteria(BaseModel):
    """Success criteria for stress test validation."""
    # Type-specific criteria added dynamically
    model_config = {"extra": "allow"}

class StressScenario(BaseModel):
    """Stress test scenario configuration."""
    name: str
    type: Literal["network", "throughput", "long_running", "error"]
    duration: int  # seconds
    parameters: dict[str, Any]
    success_criteria: SuccessCriteria

class StressTestResult(BaseModel):
    """Result of a stress test execution."""
    scenario_name: str
    start_time: str  # ISO format
    end_time: str
    duration_seconds: float
    passed: bool
    metrics: dict[str, Any]
    errors: list[str]
```

### Architecture Patterns and Constraints

From Tech Spec:
- Use pytest-asyncio for async stress test execution
- Results include machine-readable metrics
- Scenarios should be parameterizable without code changes (NFR25)

### Prerequisites

- Epic 10.1 must be complete (audit findings resolved)
- Paper broker and testnet infrastructure available

### References

- [Source: docs/internal/planning/prd-epic-10.md#Stress Test Scenarios]
- [Source: docs/internal/sprint-artifacts/epic-10-tech-spec.md#AC-10.3.1]
- [Source: docs/internal/planning/architecture-epic-10.md#ADR-004: pytest-based Stress Testing Framework]
- [Source: docs/internal/planning/epics/epic-10-live-trading-production-readiness-lighter-xyz-integration.md#Story 10.3.1]

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

Implementation plan:
1. Create directory structure following Epic 10.2 patterns (tests/live/paper/)
2. Implement Pydantic models for scenarios and results in models.py
3. Create pytest fixtures in conftest.py for scenario loading/execution
4. Create sample YAML scenarios demonstrating all 4 test types
5. Implement JSON result serialization with timestamps and metrics
6. Write comprehensive infrastructure tests

### Completion Notes List

- Created full stress testing infrastructure in tests/live/stress/
- Implemented models.py with ScenarioType enum, type-specific parameter models (NetworkParameters, ThroughputParameters, LongRunningParameters, ErrorParameters), SuccessCriteria, StressScenario, StressTestResult, and ResultsFile models
- Created conftest.py with fixtures: load_scenario, load_all_scenarios, scenarios_by_type, validate_results, execute_scenario, save_result, load_results, aggregate_results
- Created 4 sample scenario YAML files demonstrating all test types
- Implemented structured JSON result logging with environment info, timing, metrics, and criteria results
- All 35 infrastructure tests passing

### File List

- tests/live/stress/__init__.py (created)
- tests/live/stress/models.py (created)
- tests/live/stress/conftest.py (created)
- tests/live/stress/test_infrastructure.py (created)
- tests/live/stress/scenarios/network_disconnect.yaml (created)
- tests/live/stress/scenarios/high_throughput.yaml (created)
- tests/live/stress/scenarios/long_running_24h.yaml (created)
- tests/live/stress/scenarios/api_error_simulation.yaml (created)
- tests/live/stress/results/ (created directory)

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-05 | Story drafted from Epic 10 breakdown | SM Agent |
| 2025-12-06 | Implemented stress testing infrastructure with all ACs satisfied | Dev Agent |
