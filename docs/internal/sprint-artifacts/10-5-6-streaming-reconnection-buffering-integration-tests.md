# Story 10.5.6: Streaming Reconnection, Buffering & Integration Tests

Status: review

## Story

As a **developer**,
I want **robust reconnection and buffering for the streaming adapter with comprehensive tests**,
So that **live trading survives network failures**.

## Acceptance Criteria

1. **AC1:** Reconnection with exponential backoff works:
   - On disconnect, reconnection attempted
   - Delay follows `min(base * 2^attempts, max_delay)` pattern
   - Max attempts configurable

2. **AC2:** Subscriptions restored after reconnection:
   - Previous subscriptions remembered
   - Re-subscribed automatically on reconnect

3. **AC3:** Buffering during brief disconnections works:
   - Messages buffered during disconnect (< 30 seconds)
   - Buffered messages processed on reconnect

4. **AC4:** Integration tests pass on Lighter.xyz testnet:
   - Connect, subscribe, receive messages tested
   - Tests skip gracefully if credentials unavailable

## Tasks / Subtasks

- [ ] Task 1: Implement reconnection logic (AC: #1)
  - [ ] Create `reconnect()` async method
  - [ ] Implement exponential backoff
  - [ ] Track reconnection attempts
  - [ ] Reset on successful reconnect

- [ ] Task 2: Implement subscription restoration (AC: #2)
  - [ ] Store active subscriptions
  - [ ] After reconnect, re-subscribe to all
  - [ ] Verify subscriptions restored

- [ ] Task 3: Implement message buffering (AC: #3)
  - [ ] Create message buffer (bounded queue)
  - [ ] Buffer messages during disconnect state
  - [ ] Process buffered messages on reconnect
  - [ ] Discard buffer if disconnect > 30 seconds

- [ ] Task 4: Write integration tests (AC: #4)
  - [ ] Test connect and subscribe on testnet
  - [ ] Test receive trade messages
  - [ ] Test reconnection behavior
  - [ ] Add skip if no credentials

- [ ] Task 5: Write unit tests for reconnection (AC: #1-3)
  - [ ] Test exponential backoff delays
  - [ ] Test subscription restoration
  - [ ] Test buffering behavior

## Dev Notes

### Reconnection Implementation

From Architecture Pattern 3:

```python
async def reconnect(self) -> None:
    """Reconnect with exponential backoff."""
    self._reconnect_count = 0
    max_attempts = 10

    while self._reconnect_count < max_attempts:
        self._reconnect_count += 1

        # Calculate delay with exponential backoff
        delay = min(
            self.config.reconnect_delay * (2 ** (self._reconnect_count - 1)),
            self.config.reconnect_max_delay,
        )

        logger.info(
            "lighter_reconnecting",
            attempt=self._reconnect_count,
            delay=delay
        )

        await asyncio.sleep(delay)

        try:
            await self.connect()

            # Re-subscribe to previous subscriptions
            for symbol, channels in self._subscriptions.items():
                await self.subscribe([symbol], list(channels))

            self._reconnect_count = 0  # Reset on success
            logger.info("lighter_reconnected")
            return
        except Exception as e:
            logger.warning("lighter_reconnect_failed", error=str(e))

    logger.error("lighter_max_reconnect_attempts_reached")
    raise LighterConnectionError("Max reconnection attempts reached")
```

### Message Buffering

```python
from collections import deque

class LighterWebSocketAdapter(BaseWebSocketAdapter):
    def __init__(self, ...):
        ...
        self._message_buffer: deque = deque(maxlen=1000)
        self._buffering = False

    async def _on_disconnect(self):
        """Handle disconnect, start buffering."""
        self._buffering = True
        self._disconnect_time = time.monotonic()

    async def _on_reconnect(self):
        """Handle reconnect, process buffer."""
        if time.monotonic() - self._disconnect_time > 30:
            # Too long disconnected, discard buffer
            self._message_buffer.clear()
            logger.warning("buffer_discarded_due_to_long_disconnect")
        else:
            # Process buffered messages
            while self._message_buffer:
                message = self._message_buffer.popleft()
                await self._process_message(message)

        self._buffering = False
```

### Integration Test Structure

```python
import pytest
import os

skip_without_lighter_creds = pytest.mark.skipif(
    not os.environ.get("LIGHTER_TESTNET_PRIVATE_KEY"),
    reason="Lighter.xyz testnet credentials not available"
)

@pytest.mark.integration
@skip_without_lighter_creds
class TestLighterStreamIntegration:
    """Integration tests for Lighter.xyz streaming adapter."""

    @pytest.fixture
    async def adapter(self):
        """Create connected adapter for tests."""
        adapter = LighterWebSocketAdapter(testnet=True)
        await adapter.connect()
        yield adapter
        await adapter.disconnect()

    async def test_connect_and_subscribe(self, adapter):
        """Test connection and subscription."""
        await adapter.subscribe(["BTC-PERP"], ["trades"])
        assert adapter.is_connected()

    async def test_receive_trade_message(self, adapter):
        """Test receiving trade messages."""
        messages = []
        adapter.set_tick_callback(lambda tick: messages.append(tick))

        await adapter.subscribe(["BTC-PERP"], ["trades"])

        # Wait for some messages
        await asyncio.sleep(5)

        # May not receive messages if no trades occurring
        # Just verify no errors
```

### Architecture Patterns and Constraints

From NFRs:
- **NFR2**: Reconnection < 30 seconds
- **NFR9**: Queue orders during brief disconnections (< 30 seconds)
- **Pattern 3**: Exponential backoff

### Prerequisites

- Stories 10.5.4 and 10.5.5 must be complete
- All streaming adapter functionality implemented

### References

- [Source: docs/internal/planning/architecture-epic-10.md#Pattern 3: Reconnection with Exponential Backoff]
- [Source: docs/internal/sprint-artifacts/epic-10-tech-spec.md#AC-10.5.6]
- [Source: docs/internal/sprint-artifacts/epic-10-tech-spec.md#Test Strategy Summary]
- [Source: docs/internal/planning/epics/epic-10-live-trading-production-readiness-lighter-xyz-integration.md#Story 10.5.6]

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

<!-- Will be filled by dev agent -->

### Debug Log References

### Completion Notes List

### File List

## Code Review

### Review Date: 2025-12-08
### Reviewer: Senior Developer (Code Review Workflow)
### Decision: ✅ **APPROVED**

### Sub-Epic 10.5 Summary (Stories 10.5.1 - 10.5.6)

| Area | Status | Tests |
|------|--------|-------|
| Data Adapter Skeleton & Asset Discovery | ✅ Pass | 10 tests |
| OHLCV Fetching (Multi-timeframe) | ✅ Pass | 5 tests |
| Data Standardization & Validation | ✅ Pass | 5 tests |
| WebSocket Connection | ✅ Pass | 4 tests |
| Multi-Channel Subscription & Bar Agg | ✅ Pass | 14 tests |
| Reconnection & Buffering | ✅ Pass | 20 tests |
| **Total** | **✅ Pass** | **58 tests** |

### Positive Findings

1. **Asset Discovery** (`lighter_adapter.py:160-229`):
   - Caching with 5-minute TTL
   - Category filtering (perpetual/spot)
   - Regex/wildcard pattern matching

2. **OHLCV Schema** (`lighter_adapter.py:26-35`):
   - Polars Decimal(18,8) precision for financial data
   - Proper timestamp handling

3. **Data Validation** (`lighter_adapter.py:672-707`):
   - OHLCV relationship validation
   - Null detection and schema validation

4. **WebSocket Streaming** (`lighter_stream.py`):
   - Bar buffer for tick-to-bar aggregation
   - Message buffering during reconnection
   - Context manager support

### Minor Observations (Non-blocking)

1. **[LOW]** `datetime.utcfromtimestamp()` deprecated in `lighter_stream.py:359,361,432`
   - Should use `datetime.fromtimestamp(ts, timezone.utc)`
   - Functional but generates deprecation warnings

### Action Items

1. **[LOW]** Update deprecated datetime usage in `lighter_stream.py`

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-05 | Story drafted from Epic 10 breakdown | SM Agent |
| 2025-12-08 | Code review: APPROVED with minor observation | Senior Developer |
