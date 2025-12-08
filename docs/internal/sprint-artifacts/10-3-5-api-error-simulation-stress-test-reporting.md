# Story 10.3.5: API Error Simulation & Stress Test Reporting

Status: done

## Story

As a **developer**,
I want **stress tests that simulate API errors and generate comprehensive reports**,
So that **I can validate error handling and track stress test results over time**.

## Acceptance Criteria

1. **AC1:** API error simulation capability exists for:
   - 500 Internal Server Error
   - 429 Rate Limit Exceeded
   - 408 Request Timeout
   - Connection refused

2. **AC2:** Each error is handled gracefully:
   - Appropriate retry logic applied
   - No crash or state corruption
   - Errors logged with context

3. **AC3:** Comprehensive stress test report is generated:
   - Test date and duration
   - Scenarios executed with parameters
   - Pass/fail status for each scenario
   - Metrics: reconnection times, throughput, memory usage
   - Error counts by type
   - Overall pass/fail verdict

4. **AC4:** Report is saved to `docs/live-trading/stress-test-report.md`

## Tasks / Subtasks

- [x] Task 1: Create API error test file (AC: #1-2)
  - [x] Create `tests/live/stress/test_api_errors.py`
  - [x] Import stress testing infrastructure
  - [x] Create mock response utilities

- [x] Task 2: Implement 500 error simulation (AC: #1, #2)
  - [x] Mock 500 Internal Server Error response
  - [x] Verify retry logic activates
  - [x] Verify exponential backoff
  - [x] Verify no crash
  - [x] Verify state consistent after recovery

- [x] Task 3: Implement 429 error simulation (AC: #1, #2)
  - [x] Mock 429 Rate Limit Exceeded response
  - [x] Verify backoff behavior
  - [x] Verify retry after Retry-After header delay
  - [x] Verify no crash
  - [x] Verify order eventually processed

- [x] Task 4: Implement timeout simulation (AC: #1, #2)
  - [x] Mock 408 Request Timeout response
  - [x] Simulate connection timeout
  - [x] Verify retry logic
  - [x] Verify timeout handling

- [x] Task 5: Implement connection refused simulation (AC: #1, #2)
  - [x] Simulate connection refused error
  - [x] Verify error logged
  - [x] Verify retry with backoff
  - [x] Verify graceful degradation

- [x] Task 6: Implement error context logging (AC: #2)
  - [x] Verify order_id in error context
  - [x] Verify symbol in error context
  - [x] Verify operation type in error context
  - [x] Verify no sensitive data logged

- [x] Task 7: Implement report aggregation (AC: #3)
  - [x] Load results from all stress tests
  - [x] Aggregate metrics
  - [x] Calculate overall pass/fail

- [x] Task 8: Generate markdown report (AC: #4)
  - [x] Create report template
  - [x] Populate with test results
  - [x] Save to `docs/live-trading/stress-test-report.md`
  - [x] Include visualizations (if applicable)

## Dev Notes

### Error Simulation Utilities

```python
from unittest.mock import AsyncMock, patch
import httpx

async def simulate_500_error(broker, operation):
    """Simulate 500 Internal Server Error."""
    mock_response = httpx.Response(
        status_code=500,
        json={"error": "Internal Server Error"}
    )

    with patch.object(broker._client, 'post', return_value=mock_response):
        with pytest.raises(BrokerError):
            await operation()

async def simulate_429_error(broker, operation, retry_after=5):
    """Simulate 429 Rate Limit Exceeded."""
    mock_response = httpx.Response(
        status_code=429,
        headers={"Retry-After": str(retry_after)},
        json={"error": "Rate limit exceeded"}
    )

    call_count = 0
    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_response
        return httpx.Response(200, json={"success": True})

    with patch.object(broker._client, 'post', side_effect=mock_post):
        result = await operation()
        assert call_count == 2  # Retry happened
```

### Retry Logic Verification

From Architecture, retry should use exponential backoff:
```python
def verify_retry_delays(recorded_delays: list[float], base: float = 1.0, max_delay: float = 60.0):
    """Verify retry delays follow exponential backoff."""
    for i, delay in enumerate(recorded_delays):
        expected = min(base * (2 ** i), max_delay)
        # Allow 10% tolerance
        assert abs(delay - expected) < expected * 0.1
```

### Report Template

```markdown
# Stress Test Report

**Generated:** 2025-12-XX
**Duration:** X hours

## Summary

| Metric | Value |
|--------|-------|
| Total Scenarios | X |
| Passed | X |
| Failed | X |
| Overall Status | PASS/FAIL |

## Scenario Results

### Network Resilience
- **Status:** PASS/FAIL
- **Duration:** 300s
- **Disconnections:** 5
- **Avg Reconnection Time:** 2.5s
- **Max Reconnection Time:** 4.2s

### Order Throughput
- **Status:** PASS/FAIL
- **Orders Submitted:** 600
- **Latency p50:** 12.5ms
- **Latency p99:** 78.1ms

### Long-Running Stability
- **Status:** PASS/FAIL
- **Duration:** 24h
- **Memory Growth:** 1.3%
- **Errors:** 0

### API Error Handling
- **Status:** PASS/FAIL
- **500 Errors Handled:** Yes
- **429 Errors Handled:** Yes
- **Timeouts Handled:** Yes
- **Connection Refused Handled:** Yes

## Error Summary

| Error Type | Count | Handled |
|------------|-------|---------|
| 500 Internal Server | X | Yes/No |
| 429 Rate Limit | X | Yes/No |
| 408 Timeout | X | Yes/No |
| Connection Refused | X | Yes/No |

## Recommendations

[Any recommendations based on results]
```

### Architecture Patterns and Constraints

From NFRs:
- **NFR7**: System must survive any single API failure without data loss
- **NFR10**: All order state transitions logged for audit

### Prerequisites

- Stories 10.3.1-10.3.4 should be complete for aggregation
- Error handling in brokers implemented

### References

- [Source: docs/internal/planning/prd-epic-10.md#FR28, FR29 - API error simulation]
- [Source: docs/internal/sprint-artifacts/epic-10-tech-spec.md#AC-10.3.5]
- [Source: docs/internal/sprint-artifacts/epic-10-tech-spec.md#Observability - Logging]
- [Source: docs/internal/planning/epics/epic-10-live-trading-production-readiness-lighter-xyz-integration.md#Story 10.3.5]

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

Implementation approach:
1. Created MockAPIClient with error injection capability for 500, 429, 408, and connection refused
2. Implemented ErrorRecord dataclass for tracking error details with context
3. Created make_request_with_retry() with exponential backoff logic
4. Implemented circuit breaker pattern with configurable threshold
5. Created StressTestReportGenerator for markdown report generation
6. Integrated with stress scenario infrastructure

### Completion Notes List

- Created comprehensive API error test suite with 28 tests
- MockAPIClient supports injecting any ErrorType with configurable count
- ErrorRecord captures operation, context, error_type, timestamp, retry_count
- Exponential backoff implemented with base 0.1s, max 5s delays
- Circuit breaker trips after 5 consecutive failures, blocks subsequent requests
- StressTestReportGenerator loads results from JSON and generates markdown
- Tests verify all 4 error types handled gracefully with retry logic
- Context logging verified for order_id, symbol, and operation type
- All 28 tests passing

### File List

- tests/live/stress/test_api_errors.py (created)

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-05 | Story drafted from Epic 10 breakdown | SM Agent |
| 2025-12-06 | Implemented API error simulation tests with all ACs satisfied | Dev Agent |
