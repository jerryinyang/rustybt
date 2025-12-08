# Story 10.4.2: Order Submission (Market & Limit)

Status: review

## Story

As a **developer**,
I want **to submit market and limit orders to Lighter.xyz**,
So that **users can execute trades on the platform**.

## Acceptance Criteria

1. **AC1:** Market order submission works:
   - Transaction signed with private key
   - Transaction submitted via POST `/sendTx`
   - Response parsed for order ID
   - Order ID returned

2. **AC2:** Limit order submission works:
   - Limit order transaction created with specified price
   - Order submitted and order ID returned

3. **AC3:** Rate limiting is enforced:
   - Rate limits checked before submission
   - Order waits if rate limit would be exceeded (Pattern 2)
   - Submission proceeds when under limit

4. **AC4:** Order rejection errors are handled:
   - `LighterOrderRejectError` raised with error details
   - Error logged with order context (no sensitive data)

5. **AC5:** Amount convention is correct:
   - Positive amount = buy
   - Negative amount = sell

## Tasks / Subtasks

- [x] Task 1: Implement submit_order method (AC: #1, #2, #5)
  - [x] Create `submit_order()` async method
  - [x] Accept asset, amount, order_type, limit_price parameters
  - [x] Determine side from amount sign
  - [x] Create transaction for market or limit order
  - [x] Sign transaction with private key

- [x] Task 2: Implement transaction signing (AC: #1, #2)
  - [x] Use lighter-sdk for transaction creation
  - [x] Sign with loaded private key
  - [x] Handle signing errors

- [x] Task 3: Implement API submission (AC: #1, #2)
  - [x] POST to `/sendTx` endpoint via SignerClient
  - [x] Parse response for order_id
  - [x] Handle response errors
  - [x] Return order_id

- [x] Task 4: Implement rate limiting (AC: #3)
  - [x] Create rate limiter (TokenBucket class)
  - [x] Implement request rate limit (600/min)
  - [x] Implement order rate limit (20/sec per symbol)
  - [x] Log warnings at 80% capacity
  - [x] Wait if limit exceeded

- [x] Task 5: Implement error handling (AC: #4)
  - [x] `LighterOrderRejectError` exception (from Story 10.4.1)
  - [x] Parse Lighter.xyz error responses
  - [x] Extract error code and message
  - [x] Log with context (order_id, symbol, operation)

- [x] Task 6: Write unit tests (AC: #1-5)
  - [x] Test market order submission (mocked)
  - [x] Test limit order submission (mocked)
  - [x] Test rate limiting behavior
  - [x] Test error handling
  - [x] Test amount sign convention

## Dev Notes

### Submit Order Implementation

```python
async def submit_order(
    self,
    asset: Asset,
    amount: Decimal,
    order_type: str,
    limit_price: Decimal | None = None,
    stop_price: Decimal | None = None,
) -> str:
    """Submit order via /sendTx endpoint.

    Args:
        asset: The trading asset
        amount: Order quantity (positive=buy, negative=sell)
        order_type: "market" or "limit"
        limit_price: Price for limit orders
        stop_price: Not supported yet

    Returns:
        Order ID from Lighter.xyz
    """
    # Check rate limits
    await self._check_request_rate_limit()
    await self._check_order_rate_limit(asset.symbol)

    # Determine side from amount sign
    side = "buy" if amount > 0 else "sell"
    quantity = abs(amount)

    # Create and sign transaction
    if order_type == "market":
        tx = self._create_market_order_tx(asset.symbol, side, quantity)
    elif order_type == "limit":
        if limit_price is None:
            raise ValueError("limit_price required for limit orders")
        tx = self._create_limit_order_tx(asset.symbol, side, quantity, limit_price)
    else:
        raise ValueError(f"Unsupported order type: {order_type}")

    signed_tx = self._sign_transaction(tx)

    # Submit to API
    try:
        response = await self._client.post("/sendTx", json=signed_tx)
        response.raise_for_status()
        data = response.json()
        order_id = data.get("order_id") or data.get("id")

        logger.info(
            "order_submitted",
            order_id=order_id,
            symbol=asset.symbol,
            side=side,
            order_type=order_type,
            quantity=str(quantity),
            price=str(limit_price) if limit_price else "market",
        )

        return order_id
    except httpx.HTTPStatusError as e:
        raise LighterOrderRejectError(
            f"Order rejected: {e.response.text}",
            order_context={"symbol": asset.symbol, "side": side}
        )
```

### Rate Limiting (Token Bucket)

```python
class TokenBucket:
    """Token bucket rate limiter."""

    def __init__(self, rate: float, capacity: float):
        self.rate = rate  # tokens per second
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.monotonic()

    async def acquire(self, tokens: int = 1):
        """Acquire tokens, waiting if necessary."""
        while True:
            self._refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                return
            # Wait for tokens to refill
            wait_time = (tokens - self.tokens) / self.rate
            await asyncio.sleep(wait_time)

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self.last_update
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_update = now
```

### Architecture Patterns and Constraints

From Architecture:
- **Pattern 2**: Rate limiting at adapter level
  - 600 requests/minute REST
  - 20 orders/second per symbol
- Logging follows structured format (structlog)

### Prerequisites

- Story 10.4.1 must be complete (adapter skeleton, authentication)

### References

- [Source: docs/internal/planning/architecture-epic-10.md#Pattern 2: Rate Limiting]
- [Source: docs/internal/sprint-artifacts/epic-10-tech-spec.md#AC-10.4.2]
- [Source: docs/internal/sprint-artifacts/epic-10-tech-spec.md#APIs and Interfaces - LighterBrokerAdapter]
- [Source: docs/internal/planning/epics/epic-10-live-trading-production-readiness-lighter-xyz-integration.md#Story 10.4.2]

## Dev Agent Record

### Context Reference

- `docs/internal/sprint-artifacts/10-4-2-order-submission-market-limit.context.xml`

### Agent Model Used

Claude claude-opus-4-5-20251101

### Debug Log References

- Implemented TokenBucket class for rate limiting
- submit_order() uses SignerClient.create_market_order() and create_order()
- Rate limiters: global request limiter (600/min) + per-symbol order limiters (20/sec)
- 14 new tests added for order submission and rate limiting

### Completion Notes List

- ✅ `submit_order()` async method implemented with market and limit order support
- ✅ Amount sign convention: positive = buy, negative = sell
- ✅ TokenBucket rate limiter with async acquire, try_acquire, utilization metrics
- ✅ Warnings logged at 80% rate limit utilization
- ✅ LighterOrderRejectError raised on API errors with context
- ✅ 48 total tests passing (14 new for order submission + rate limiting)

### File List

| File | Action |
|------|--------|
| `rustybt/live/brokers/lighter_adapter.py` | Modified (added TokenBucket, submit_order, rate limiting) |
| `tests/live/lighter/test_lighter_broker.py` | Modified (added 14 order/rate limit tests) |

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-05 | Story drafted from Epic 10 breakdown | SM Agent |
| 2025-12-06 | Implementation complete, 48 tests passing | Dev Agent |
