# Story 10.2.3: Paper vs Live Parity Verification

Status: done

## Story

As a **developer**,
I want **to verify paper trading behavior matches live trading behavior**,
So that **paper trading results are a reliable proxy for live performance**.

## Acceptance Criteria

1. **AC1:** Given identical strategy configurations, order submission calls have identical parameters:
   - Asset/symbol matches
   - Order amount matches
   - Order type matches (market/limit)
   - Price parameters match (for limit orders)

2. **AC2:** Position calculations use the same logic between paper and live:
   - Position size calculation identical
   - Entry price calculation identical
   - Position direction logic identical

3. **AC3:** PnL calculations produce identical results for the same fill prices:
   - Unrealized PnL formula identical
   - Realized PnL formula identical
   - Decimal precision identical

4. **AC4:** State transitions follow the same state machine:
   - Same valid transitions
   - Same state names
   - Same transition triggers

5. **AC5:** A parity report documents any intentional differences:
   - Paper simulates fills (live receives them)
   - Paper has no network latency
   - Other documented differences

## Tasks / Subtasks

- [ ] Task 1: Create parity test infrastructure (AC: #1-5)
  - [ ] Create `tests/live/paper/test_paper_parity.py`
  - [ ] Create mock live broker for comparison
  - [ ] Create call capture mechanism for both broker types

- [ ] Task 2: Implement order call comparison (AC: #1)
  - [ ] Configure identical strategy for paper and mock live
  - [ ] Run same signals through both
  - [ ] Capture all order submission calls
  - [ ] Compare call parameters (asset, amount, type, price)
  - [ ] Assert exact match

- [ ] Task 3: Implement position calculation comparison (AC: #2)
  - [ ] Create position from order on both brokers
  - [ ] Compare position size
  - [ ] Compare entry price
  - [ ] Compare direction
  - [ ] Test with multiple order scenarios

- [ ] Task 4: Implement PnL calculation comparison (AC: #3)
  - [ ] Set identical fill prices for both brokers
  - [ ] Calculate unrealized PnL on both
  - [ ] Calculate realized PnL on both
  - [ ] Assert exact Decimal match
  - [ ] Test various price scenarios

- [ ] Task 5: Implement state machine comparison (AC: #4)
  - [ ] Document paper broker state machine
  - [ ] Document live broker state machine
  - [ ] Compare valid transitions
  - [ ] Compare state names
  - [ ] Assert equivalence

- [ ] Task 6: Create parity report (AC: #5)
  - [ ] Document expected differences
  - [ ] Create parity report template
  - [ ] Generate report from test results
  - [ ] Include pass/fail status

- [ ] Task 7: Test edge cases (AC: #1-4)
  - [ ] Partial fills (if supported)
  - [ ] Order cancellation
  - [ ] Rapid order submission
  - [ ] Position reversals

## Dev Notes

### Parity Testing Strategy

The goal is to ensure that paper trading is a faithful simulation of live trading:

```python
def test_order_parity():
    """Verify paper and live broker receive identical order calls."""
    paper_calls = []
    live_calls = []

    # Capture calls to paper broker
    paper_broker = PaperBroker()
    paper_broker.submit_order = capture_call(paper_broker.submit_order, paper_calls)

    # Capture calls to mock live broker
    live_broker = MockLiveBroker()
    live_broker.submit_order = capture_call(live_broker.submit_order, live_calls)

    # Run same strategy signals
    strategy.on_signal("BUY", ..., broker=paper_broker)
    strategy.on_signal("BUY", ..., broker=live_broker)

    # Compare
    assert paper_calls == live_calls
```

### Expected Differences

From Epic breakdown, these differences are intentional:
1. **Fill source**: Paper simulates fills locally, live receives from exchange
2. **Network latency**: Paper has no network latency
3. **Slippage**: Paper uses configured slippage model, live has real slippage
4. **Partial fills**: Live may have partial fills, paper model depends on configuration

### Parity Report Format

```markdown
# Paper vs Live Trading Parity Report

## Test Date: 2025-12-XX

## Summary
- Order call parity: PASS/FAIL
- Position calculation parity: PASS/FAIL
- PnL calculation parity: PASS/FAIL
- State machine parity: PASS/FAIL

## Intentional Differences
1. Fill simulation (paper) vs real fills (live)
2. [Other documented differences]

## Findings
[Any unexpected differences found]
```

### Architecture Patterns and Constraints

Both brokers should implement the same `BrokerAdapter` ABC interface, ensuring:
- Same method signatures
- Same return types
- Same exception types

### Prerequisites

- Story 10.2.1 must be complete (paper trading test harness)
- Mock live broker available for testing

### References

- [Source: docs/internal/planning/prd-epic-10.md#FR13 - Compare paper vs live behavior]
- [Source: docs/internal/sprint-artifacts/epic-10-tech-spec.md#AC-10.2.3]
- [Source: docs/internal/planning/epics/epic-10-live-trading-production-readiness-lighter-xyz-integration.md#Story 10.2.3]

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
