# Story 10.2.4: Testnet Connection & Basic Order Flow

Status: done

## Story

As a **developer**,
I want **to validate testnet connectivity and basic order submission for at least one exchange**,
So that **I can prove the system works with real exchange APIs**.

## Acceptance Criteria

1. **AC1:** Connection to testnet is successfully established:
   - Valid testnet credentials for Hyperliquid (primary) or Binance/Bybit (fallback)
   - Connection established without errors
   - Account information retrieved (balance, existing positions)

2. **AC2:** Limit order submission works on testnet:
   - Small limit order submitted (e.g., 0.001 BTC at unlikely-to-fill price)
   - Order accepted by exchange
   - Order appears in open orders
   - Order can be cancelled successfully

3. **AC3:** Market order submission and fill works on testnet:
   - Small market order submitted
   - Order is filled
   - Fill received and processed
   - Position updated accordingly

4. **AC4:** Rate limit handling is verified during order submission

5. **AC5:** Tests skip gracefully if credentials are not available

## Tasks / Subtasks

- [ ] Task 1: Create testnet test infrastructure (AC: #1-5)
  - [ ] Create `tests/live/testnet/` directory
  - [ ] Create `tests/live/testnet/__init__.py`
  - [ ] Create `tests/live/testnet/conftest.py`
  - [ ] Add credential loading from environment variables
  - [ ] Add skip decorator for missing credentials

- [ ] Task 2: Implement Hyperliquid testnet tests (AC: #1-5)
  - [ ] Create `tests/live/testnet/test_hyperliquid_testnet.py`
  - [ ] Load credentials from `HYPERLIQUID_TESTNET_API_KEY`, etc.
  - [ ] Test connection establishment
  - [ ] Test account info retrieval

- [ ] Task 3: Implement limit order test (AC: #2)
  - [ ] Submit limit order at unlikely price
  - [ ] Verify order accepted
  - [ ] Query open orders, verify present
  - [ ] Cancel order
  - [ ] Verify order removed from open orders

- [ ] Task 4: Implement market order test (AC: #3)
  - [ ] Submit minimal size market order
  - [ ] Wait for fill
  - [ ] Verify fill received
  - [ ] Verify position updated
  - [ ] Close position to restore state

- [ ] Task 5: Implement rate limit verification (AC: #4)
  - [ ] Submit multiple orders in sequence
  - [ ] Verify rate limit handling
  - [ ] Check no errors from rate limiting

- [ ] Task 6: Implement credential skip logic (AC: #5)
  - [ ] Add `@pytest.mark.skipif` for missing credentials
  - [ ] Add descriptive skip message
  - [ ] Test skip behavior works correctly

- [ ] Task 7: Create fallback tests for other exchanges (AC: #1-3)
  - [ ] Create `test_binance_testnet.py` (fallback)
  - [ ] Create `test_bybit_testnet.py` (fallback)
  - [ ] Mark as optional/fallback

## Dev Notes

### Environment Variables for Credentials

```bash
# Hyperliquid testnet (primary)
HYPERLIQUID_TESTNET_API_KEY=your_api_key
HYPERLIQUID_TESTNET_PRIVATE_KEY=your_private_key

# Binance testnet (fallback)
BINANCE_TESTNET_API_KEY=your_api_key
BINANCE_TESTNET_SECRET=your_secret

# Bybit testnet (fallback)
BYBIT_TESTNET_API_KEY=your_api_key
BYBIT_TESTNET_SECRET=your_secret
```

### Skip Decorator Pattern

```python
import pytest
import os

skip_without_hyperliquid_creds = pytest.mark.skipif(
    not os.environ.get("HYPERLIQUID_TESTNET_API_KEY"),
    reason="Hyperliquid testnet credentials not available"
)

@skip_without_hyperliquid_creds
def test_hyperliquid_connection():
    """Test connection to Hyperliquid testnet."""
    ...
```

### Minimal Order Sizes

To avoid depleting testnet funds:
- Use minimum order sizes (e.g., 0.001 for BTC pairs)
- Use unlikely limit prices that won't fill
- Close any positions opened during tests

### Architecture Patterns and Constraints

From Architecture document:
- **ADR-003**: Default to testnet (`testnet=True`)
- Rate limiting must be active during tests
- All credentials from environment variables per NFR14

### Testnet Registration Links

For documentation/setup:
- Hyperliquid testnet: https://testnet.hyperliquid.xyz/
- Binance testnet: https://testnet.binance.vision/
- Bybit testnet: https://testnet.bybit.com/

### Prerequisites

- Story 10.2.1 must be complete (paper trading works)
- Testnet credentials configured
- Exchange adapters functional

### References

- [Source: docs/internal/planning/prd-epic-10.md#FR14-FR18 - Testnet requirements]
- [Source: docs/internal/sprint-artifacts/epic-10-tech-spec.md#AC-10.2.4]
- [Source: docs/internal/planning/architecture-epic-10.md#ADR-003: Default to Testnet]
- [Source: docs/internal/planning/epics/epic-10-live-trading-production-readiness-lighter-xyz-integration.md#Story 10.2.4]

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
