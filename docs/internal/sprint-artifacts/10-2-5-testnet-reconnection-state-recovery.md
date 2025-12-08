# Story 10.2.5: Testnet Reconnection & State Recovery

Status: done

## Story

As a **developer**,
I want **to validate WebSocket reconnection and state recovery after disconnection**,
So that **the system is resilient to network failures**.

## Acceptance Criteria

1. **AC1:** WebSocket reconnection works after forced disconnection:
   - Reconnection attempted with exponential backoff
   - Reconnection succeeds within 30 seconds (NFR2)
   - Subscriptions restored automatically

2. **AC2:** Position state is reconciled with exchange after reconnection:
   - Local positions compared to exchange positions
   - Any discrepancies resolved
   - State consistency verified

3. **AC3:** Order status is synced after reconnection during active order:
   - Order status queried from exchange
   - Missed fills processed
   - Local state matches exchange state

4. **AC4:** Exponential backoff follows correct formula:
   - `delay = min(base * 2^attempts, max_delay)`
   - Backoff resets on successful connection
   - Max attempts respected

## Tasks / Subtasks

- [ ] Task 1: Create reconnection test infrastructure (AC: #1-4)
  - [ ] Create `tests/live/testnet/test_testnet_reconnection.py`
  - [ ] Create method to simulate disconnect (close WebSocket)
  - [ ] Create timing capture for reconnection measurement

- [ ] Task 2: Implement basic reconnection test (AC: #1)
  - [ ] Establish testnet connection
  - [ ] Subscribe to market data
  - [ ] Force disconnect (close WebSocket connection)
  - [ ] Verify reconnection attempt starts
  - [ ] Verify reconnection completes < 30 seconds
  - [ ] Verify subscriptions restored

- [ ] Task 3: Implement position reconciliation test (AC: #2)
  - [ ] Create position on testnet
  - [ ] Force disconnect
  - [ ] Reconnect
  - [ ] Verify reconciler runs
  - [ ] Verify local position matches exchange

- [ ] Task 4: Implement order sync test (AC: #3)
  - [ ] Submit order on testnet
  - [ ] Force disconnect before fill
  - [ ] Wait for potential fill during disconnect
  - [ ] Reconnect
  - [ ] Verify order status synced
  - [ ] Verify any fills processed

- [ ] Task 5: Verify exponential backoff (AC: #4)
  - [ ] Mock repeated failures
  - [ ] Measure delay between attempts
  - [ ] Verify delay follows formula
  - [ ] Verify max delay cap
  - [ ] Verify reset on success

- [ ] Task 6: Test edge cases (AC: #1-4)
  - [ ] Multiple rapid disconnects
  - [ ] Disconnect during order submission
  - [ ] Disconnect during position reconciliation
  - [ ] Network timeout vs clean disconnect

## Dev Notes

### Simulating Disconnect

```python
async def force_disconnect(adapter):
    """Force disconnect by closing underlying WebSocket."""
    if hasattr(adapter, '_ws') and adapter._ws:
        await adapter._ws.close()
    # Wait for disconnect detection
    await asyncio.sleep(1)
```

### Exponential Backoff Verification

From Architecture Pattern 3:
```python
def expected_delay(attempt: int, base: float = 1.0, max_delay: float = 60.0) -> float:
    """Calculate expected delay for given attempt."""
    return min(base * (2 ** (attempt - 1)), max_delay)

# Example delays:
# Attempt 1: 1.0s
# Attempt 2: 2.0s
# Attempt 3: 4.0s
# Attempt 4: 8.0s
# ...
# Attempt 7+: 60.0s (capped)
```

### Reconnection Timing Measurement

```python
async def measure_reconnection_time(adapter):
    """Measure time from disconnect to reconnected state."""
    disconnect_time = time.monotonic()
    await force_disconnect(adapter)

    while not adapter.is_connected():
        await asyncio.sleep(0.1)
        if time.monotonic() - disconnect_time > 30:
            pytest.fail("Reconnection exceeded 30 seconds")

    return time.monotonic() - disconnect_time
```

### Architecture Patterns and Constraints

From Architecture and NFRs:
- **NFR2**: WebSocket reconnection must complete within 30 seconds
- **NFR8**: Stale connections detected within 60 seconds
- **Pattern 3**: Exponential backoff with `delay = min(base * 2^attempts, max_delay)`

### Prerequisites

- Story 10.2.4 must be complete (testnet connection works)
- WebSocket streaming adapter functional
- Reconciler available

### References

- [Source: docs/internal/planning/prd-epic-10.md#FR17, FR19 - Reconnection requirements]
- [Source: docs/internal/sprint-artifacts/epic-10-tech-spec.md#AC-10.2.5]
- [Source: docs/internal/planning/architecture-epic-10.md#Pattern 3: Reconnection with Exponential Backoff]
- [Source: docs/internal/planning/epics/epic-10-live-trading-production-readiness-lighter-xyz-integration.md#Story 10.2.5]

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

<!-- Will be filled by dev agent -->

### Debug Log References

### Completion Notes List

### File List

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-05 | Story drafted from Epic 10 breakdown | SM Agent |
