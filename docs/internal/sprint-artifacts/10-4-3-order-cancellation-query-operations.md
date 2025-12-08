# Story 10.4.3: Order Cancellation & Query Operations

Status: review

## Story

As a **developer**,
I want **to cancel orders and query order status from Lighter.xyz**,
So that **users can manage their orders**.

## Acceptance Criteria

1. **AC1:** Order cancellation works:
   - Cancel transaction signed and submitted
   - Order cancelled on exchange
   - Success confirmed

2. **AC2:** Open orders queryable:
   - GET `/accountActiveOrders` called
   - List of open orders returned with: order_id, symbol, side, type, quantity, price, status

3. **AC3:** Order history queryable:
   - GET `/accountInactiveOrders` called
   - Filled/cancelled orders returned with fill details

4. **AC4:** Order status mapping implemented:
   - Lighter status → rustybt OrderStatus enum
   - All status values handled

## Tasks / Subtasks

- [x] Task 1: Implement cancel_order method (AC: #1)
  - [x] Create `cancel_order()` async method
  - [x] Accept broker_order_id parameter
  - [x] Create cancel transaction
  - [x] Sign and submit via SignerClient
  - [x] Verify cancellation success

- [x] Task 2: Implement get_open_orders method (AC: #2)
  - [x] Create `get_open_orders()` async method
  - [x] Call `account_active_orders` via AccountApi
  - [x] Parse response to list of orders
  - [x] Map fields to standard format

- [x] Task 3: Implement get_order_history method (AC: #3)
  - [x] Create `get_order_history()` async method
  - [x] Call `account_inactive_orders` via AccountApi
  - [x] Parse response including fill details
  - [x] Handle pagination via limit/offset

- [x] Task 4: Implement status mapping (AC: #4)
  - [x] Create LIGHTER_STATUS_MAP dictionary
  - [x] Map: pending, open/submitted, filled, cancelled, partial_fill
  - [x] Handle unknown statuses (returns 'unknown')

- [x] Task 5: Write unit tests (AC: #1-4)
  - [x] Test cancel_order with mock
  - [x] Test get_open_orders with mock
  - [x] Test get_order_history with mock
  - [x] Test status mapping (6 tests)

## Dev Notes

### Cancel Order Implementation

```python
async def cancel_order(self, broker_order_id: str) -> None:
    """Cancel an open order on Lighter.xyz.

    Args:
        broker_order_id: The order ID from Lighter.xyz
    """
    await self._check_request_rate_limit()

    # Create cancel transaction
    cancel_tx = self._create_cancel_order_tx(broker_order_id)
    signed_tx = self._sign_transaction(cancel_tx)

    try:
        response = await self._client.post("/sendTx", json=signed_tx)
        response.raise_for_status()

        logger.info("order_cancelled", order_id=broker_order_id)
    except httpx.HTTPStatusError as e:
        raise LighterOrderRejectError(
            f"Cancel failed: {e.response.text}",
            order_context={"order_id": broker_order_id}
        )
```

### Open Orders Query

```python
async def get_open_orders(self) -> list[dict]:
    """Get all open orders from Lighter.xyz.

    Returns:
        List of open orders with standardized fields
    """
    await self._check_request_rate_limit()

    response = await self._client.get(
        "/accountActiveOrders",
        params={"account": self._wallet_address}
    )
    response.raise_for_status()
    data = response.json()

    return [
        {
            "order_id": order["id"],
            "symbol": order["symbol"],
            "side": order["side"],
            "type": order["order_type"],
            "quantity": Decimal(str(order["quantity"])),
            "price": Decimal(str(order["price"])) if order.get("price") else None,
            "status": self._map_status(order["status"]),
            "filled_quantity": Decimal(str(order.get("filled_quantity", "0"))),
            "timestamp": order["timestamp"],
        }
        for order in data.get("orders", [])
    ]
```

### Status Mapping

```python
LIGHTER_STATUS_MAP = {
    "pending": OrderStatus.PENDING,
    "open": OrderStatus.SUBMITTED,
    "filled": OrderStatus.FILLED,
    "cancelled": OrderStatus.CANCELLED,
    "partially_filled": OrderStatus.PARTIAL_FILL,
}

def _map_status(self, lighter_status: str) -> OrderStatus:
    """Map Lighter.xyz status to rustybt OrderStatus."""
    status = LIGHTER_STATUS_MAP.get(lighter_status.lower())
    if status is None:
        logger.warning("unknown_lighter_status", status=lighter_status)
        return OrderStatus.UNKNOWN
    return status
```

### Architecture Patterns and Constraints

- Follow existing broker adapter patterns for return types
- All financial values as Decimal
- Rate limiting applied to all API calls

### Prerequisites

- Story 10.4.2 must be complete (order submission works)

### References

- [Source: docs/internal/sprint-artifacts/epic-10-tech-spec.md#AC-10.4.3]
- [Source: docs/internal/sprint-artifacts/epic-10-tech-spec.md#APIs and Interfaces - LighterBrokerAdapter]
- [Source: docs/internal/planning/epics/epic-10-live-trading-production-readiness-lighter-xyz-integration.md#Story 10.4.3]

## Dev Agent Record

### Context Reference

- `docs/internal/sprint-artifacts/10-4-3-order-cancellation-query-operations.context.xml`

### Agent Model Used

Claude claude-opus-4-5-20251101

### Debug Log References

- Implemented cancel_order using SignerClient.cancel_order()
- get_open_orders uses AccountApi.account_active_orders()
- get_order_history uses AccountApi.account_inactive_orders()
- Status mapping covers: pending, open, submitted, filled, cancelled, partially_filled

### Completion Notes List

- ✅ `cancel_order()` cancels orders via SignerClient
- ✅ `get_open_orders()` returns active orders with standardized fields
- ✅ `get_order_history()` returns inactive orders with fill details
- ✅ `_map_status()` converts Lighter status to OrderStatus enum
- ✅ LIGHTER_STATUS_MAP handles 6 status values + unknown fallback
- ✅ All financial values use Decimal precision
- ✅ 9 unit tests covering cancellation, queries, and status mapping

### File List

| File | Action |
|------|--------|
| `rustybt/live/brokers/lighter_adapter.py` | Modified |
| `tests/live/lighter/test_lighter_broker.py` | Modified |

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-05 | Story drafted from Epic 10 breakdown | SM Agent |
| 2025-12-06 | Implementation complete, 9 tests passing | Dev Agent |
