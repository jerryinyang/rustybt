# Story 10.2.6: End-to-End Order Flow Validation

Status: done

## Story

As a **developer**,
I want **to validate the complete order flow from strategy signal to position update**,
So that **I can confirm the entire trading pipeline works correctly**.

## Acceptance Criteria

1. **AC1:** Complete BUY signal flow is validated:
   - Strategy generates BUY signal
   - Signal processed by `strategy_executor.py`
   - Order created by `order_manager.py`
   - Order submitted via broker adapter
   - Fill received via streaming or polling
   - Position updated in `state_manager.py`
   - All state transitions logged

2. **AC2:** Complete SELL signal flow is validated:
   - Strategy generates SELL signal
   - Position is reduced or closed
   - PnL calculated correctly

3. **AC3:** Timing meets performance requirements:
   - Signal to API call < 100ms (excluding network) per NFR1

4. **AC4:** Flow works across session restarts:
   - State persisted before restart
   - State restored after restart
   - Trading continues correctly

5. **AC5:** All components in the chain are exercised:
   - Engine → StrategyExecutor → OrderManager → Broker → Fill → StateManager

## Tasks / Subtasks

- [ ] Task 1: Create end-to-end test infrastructure (AC: #1-5)
  - [ ] Create `tests/live/testnet/test_e2e_order_flow.py`
  - [ ] Create test strategy that generates signals on schedule
  - [ ] Create timing measurement instrumentation

- [ ] Task 2: Implement BUY flow test (AC: #1)
  - [ ] Configure test strategy with BUY signal
  - [ ] Start live trading engine on testnet
  - [ ] Trigger BUY signal
  - [ ] Verify order created
  - [ ] Verify order submitted
  - [ ] Verify fill received
  - [ ] Verify position created
  - [ ] Verify all transitions logged

- [ ] Task 3: Implement SELL flow test (AC: #2)
  - [ ] Ensure position exists from BUY test
  - [ ] Trigger SELL signal
  - [ ] Verify position reduced/closed
  - [ ] Verify PnL calculated
  - [ ] Verify state updated

- [ ] Task 4: Implement timing measurement (AC: #3)
  - [ ] Instrument signal generation timestamp
  - [ ] Instrument API call timestamp
  - [ ] Calculate latency
  - [ ] Assert < 100ms (excluding network)
  - [ ] Log timing metrics

- [ ] Task 5: Implement restart test (AC: #4)
  - [ ] Complete BUY flow
  - [ ] Stop engine (graceful shutdown)
  - [ ] Verify state persisted
  - [ ] Restart engine
  - [ ] Verify state restored
  - [ ] Continue with SELL flow
  - [ ] Verify correct behavior

- [ ] Task 6: Trace component chain (AC: #5)
  - [ ] Add trace logging to each component
  - [ ] Verify all components invoked
  - [ ] Verify correct sequence
  - [ ] Document chain for audit

- [ ] Task 7: Test multiple cycles (AC: #1-5)
  - [ ] Run BUY/SELL cycle multiple times
  - [ ] Verify consistency
  - [ ] Verify no state drift

## Dev Notes

### Complete Order Flow Chain

```
1. LiveTradingEngine.run()
   ↓
2. StrategyExecutor.on_bar(bar_data)
   ↓ (generates signal)
3. OrderManager.create_order(signal)
   ↓
4. BrokerAdapter.submit_order(order)
   ↓ (async - waits for fill)
5. BrokerAdapter receives fill (via stream or poll)
   ↓
6. OrderManager.on_fill(fill)
   ↓
7. StateManager.update_position(fill)
   ↓
8. Position updated, PnL recalculated
```

### Timing Instrumentation

```python
import time

class TimingInstrument:
    def __init__(self):
        self.timestamps = {}

    def mark(self, event: str):
        self.timestamps[event] = time.monotonic()

    def latency(self, start_event: str, end_event: str) -> float:
        return self.timestamps[end_event] - self.timestamps[start_event]

# Usage
timing.mark("signal_generated")
# ... flow ...
timing.mark("api_call_made")
assert timing.latency("signal_generated", "api_call_made") < 0.100
```

### Test Strategy for E2E

```python
class E2ETestStrategy:
    """Strategy that generates signals on command."""

    def __init__(self):
        self.pending_signal = None

    def queue_signal(self, signal: str):
        self.pending_signal = signal

    def on_bar(self, bar_data):
        if self.pending_signal:
            signal = self.pending_signal
            self.pending_signal = None
            return signal
        return None
```

### Architecture Patterns and Constraints

From NFRs:
- **NFR1**: Order submission latency < 100ms from signal to API call (excluding network)
- **NFR10**: All order state transitions logged for audit
- **NFR12**: State recovery after restart restores exact position state

### Prerequisites

- Stories 10.2.4 and 10.2.5 must be complete
- Full live trading engine functional on testnet
- All components integrated

### References

- [Source: docs/internal/planning/prd-epic-10.md#FR20 - End-to-end order flow validation]
- [Source: docs/internal/sprint-artifacts/epic-10-tech-spec.md#AC-10.2.6]
- [Source: docs/internal/sprint-artifacts/epic-10-tech-spec.md#Workflows and Sequencing - Order Submission Flow]
- [Source: docs/internal/planning/epics/epic-10-live-trading-production-readiness-lighter-xyz-integration.md#Story 10.2.6]

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
