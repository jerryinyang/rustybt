# Story 10.3.2: Network Failure & Reconnection Tests

Status: done

## Story

As a **developer**,
I want **stress tests that simulate network failures and measure reconnection behavior**,
So that **I can validate system resilience to network issues**.

## Acceptance Criteria

1. **AC1:** Network failure simulation works:
   - WebSocket disconnect can be simulated during active trading
   - Disconnect is detected within 60 seconds (NFR8)

2. **AC2:** Reconnection behavior is validated:
   - Reconnection attempted with exponential backoff
   - Reconnection succeeds within 30 seconds (NFR2)
   - Reconnection time is measured and logged

3. **AC3:** Circuit breaker behavior is validated:
   - After threshold consecutive failures, circuit breaker trips
   - System enters safe state
   - Recovery attempted after cooldown period

4. **AC4:** Stress test report is generated with:
   - Total disconnections simulated
   - Average reconnection time
   - Max reconnection time
   - Circuit breaker trips (if any)
   - Pass/fail status

5. **AC5:** Multiple scenarios are tested:
   - Single disconnect
   - Rapid disconnects
   - Disconnect during active order

## Tasks / Subtasks

- [x] Task 1: Create network resilience test file (AC: #1-5)
  - [x] Create `tests/live/stress/test_network_resilience.py`
  - [x] Import stress testing infrastructure
  - [x] Load network scenarios from YAML

- [x] Task 2: Implement disconnect simulation (AC: #1)
  - [x] Create `simulate_disconnect(adapter)` utility
  - [x] Verify disconnect detected
  - [x] Measure detection time
  - [x] Assert < 60 seconds

- [x] Task 3: Implement reconnection measurement (AC: #2)
  - [x] Create `measure_reconnection(adapter)` utility
  - [x] Time from disconnect to reconnected state
  - [x] Verify subscriptions restored
  - [x] Assert < 30 seconds

- [x] Task 4: Implement circuit breaker test (AC: #3)
  - [x] Create `test_circuit_breaker_trips()` test
  - [x] Simulate rapid consecutive failures
  - [x] Verify circuit breaker state change
  - [x] Verify safe state entered
  - [x] Verify cooldown behavior

- [x] Task 5: Implement report generation (AC: #4)
  - [x] Collect all metrics during test
  - [x] Generate structured report
  - [x] Include all required metrics
  - [x] Save to results directory

- [x] Task 6: Implement scenario tests (AC: #5)
  - [x] Test: Single disconnect recovery
  - [x] Test: Rapid disconnects (5 in 60 seconds)
  - [x] Test: Disconnect during order submission
  - [x] Test: Disconnect with open positions

- [x] Task 7: Verify queued orders during disconnect (AC: #2)
  - [x] Submit order just before disconnect
  - [x] Verify order queued
  - [x] Reconnect
  - [x] Verify order processed per NFR9

## Dev Notes

### Network Failure Simulation

```python
async def simulate_disconnect(adapter, delay_before_reconnect: float = 0):
    """Simulate network failure by closing WebSocket."""
    disconnect_time = time.monotonic()

    # Force close WebSocket
    if hasattr(adapter, '_ws') and adapter._ws:
        await adapter._ws.close()

    # Wait for detection
    while adapter.is_connected():
        await asyncio.sleep(0.1)
        elapsed = time.monotonic() - disconnect_time
        if elapsed > 60:
            pytest.fail(f"Disconnect not detected within 60 seconds")

    detection_time = time.monotonic() - disconnect_time
    return detection_time
```

### Reconnection Measurement

```python
async def measure_reconnection(adapter, max_wait: float = 30) -> float:
    """Measure time until reconnection completes."""
    start_time = time.monotonic()

    while not adapter.is_connected():
        await asyncio.sleep(0.1)
        elapsed = time.monotonic() - start_time
        if elapsed > max_wait:
            pytest.fail(f"Reconnection failed within {max_wait} seconds")

    return time.monotonic() - start_time
```

### Circuit Breaker Test Pattern

```python
async def test_circuit_breaker_trips():
    """Verify circuit breaker trips after consecutive failures."""
    adapter = create_test_adapter()

    # Simulate rapid failures
    for i in range(CIRCUIT_BREAKER_THRESHOLD + 1):
        await simulate_disconnect(adapter, delay_before_reconnect=0.1)
        # Don't wait for full reconnect - simulate immediate failure

    # Verify circuit breaker tripped
    assert adapter.circuit_breaker_tripped
    assert adapter.in_safe_state
```

### Architecture Patterns and Constraints

From NFRs and Architecture:
- **NFR2**: WebSocket reconnection < 30 seconds
- **NFR8**: Stale connection detection < 60 seconds
- **NFR9**: Orders queued during brief disconnections (< 30 seconds)
- **Pattern 3**: Exponential backoff with `delay = min(base * 2^attempts, max_delay)`

### Report Format

```json
{
  "scenario": "network_resilience",
  "timestamp": "2025-12-05T10:00:00Z",
  "duration_seconds": 300,
  "disconnections_simulated": 5,
  "avg_reconnection_time_seconds": 2.5,
  "max_reconnection_time_seconds": 4.2,
  "min_reconnection_time_seconds": 1.8,
  "circuit_breaker_trips": 0,
  "orders_queued_during_disconnect": 2,
  "orders_processed_after_reconnect": 2,
  "passed": true
}
```

### Prerequisites

- Story 10.3.1 must be complete (stress testing infrastructure)
- Streaming adapter with reconnection logic available

### References

- [Source: docs/internal/planning/prd-epic-10.md#FR22, FR23 - Network failure and reconnection]
- [Source: docs/internal/sprint-artifacts/epic-10-tech-spec.md#AC-10.3.2]
- [Source: docs/internal/planning/architecture-epic-10.md#Pattern 3: Reconnection with Exponential Backoff]
- [Source: docs/internal/planning/epics/epic-10-live-trading-production-readiness-lighter-xyz-integration.md#Story 10.3.2]

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

Implementation approach:
1. Created MockWebSocketAdapter class simulating real adapter behavior
2. Implemented simulate_disconnect() and measure_reconnection() utilities
3. Created ReconnectionMetrics dataclass for metrics collection
4. Implemented tests for all scenarios: single, rapid, during order, with positions
5. Added circuit breaker testing with threshold-based tripping
6. Integrated with stress testing infrastructure from Story 10.3.1

### Completion Notes List

- Created comprehensive network resilience test suite with 24 tests
- Implemented MockWebSocketAdapter with connection states, subscriptions, circuit breaker
- simulate_disconnect() verifies detection < 60s (NFR8)
- measure_reconnection() verifies reconnection < 30s (NFR2)
- Tests cover: disconnect detection, exponential backoff, subscription restoration, circuit breaker trips/reset
- Order queuing tests verify NFR9 (orders queued during brief disconnections)
- Integrated with stress scenario infrastructure from 10.3.1
- All 24 tests passing

### File List

- tests/live/stress/test_network_resilience.py (created)

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-05 | Story drafted from Epic 10 breakdown | SM Agent |
| 2025-12-06 | Implemented network resilience tests with all ACs satisfied | Dev Agent |
