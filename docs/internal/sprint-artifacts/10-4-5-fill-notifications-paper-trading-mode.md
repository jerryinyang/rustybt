# Story 10.4.5: Fill Notifications & Paper Trading Mode

Status: review

## Story

As a **developer**,
I want **to receive fill notifications and support paper trading mode**,
So that **live and simulated trading are both supported**.

## Acceptance Criteria

1. **AC1:** Fill notifications received in live mode:
   - Fill notification received via polling or WebSocket
   - Fill processed with: order_id, fill_price, fill_quantity, timestamp
   - Fill passed to order manager

2. **AC2:** Paper trading mode works:
   - With `paper_mode=True`, orders NOT sent to Lighter.xyz
   - Simulated fill generated locally
   - Positions updated based on simulated fills
   - All paper trades logged for review

3. **AC3:** Paper mode uses real market prices:
   - Real market prices fetched from Lighter.xyz (or streaming)
   - Fills use realistic prices

## Tasks / Subtasks

- [x] Task 1: Implement fill callback mechanism (AC: #1)
  - [x] Create `set_fill_callback()` method
  - [x] Store callback for fill notifications
  - [x] Call callback on order fills
  - [x] Pass fill data dict to callback

- [x] Task 2: Implement fill processing (AC: #1)
  - [x] Fill callback receives: order_id, symbol, side, fill_price, fill_quantity, timestamp
  - [x] Position updated after fill
  - [x] Async callback supported

- [x] Task 3: Implement paper trading mode (AC: #2)
  - [x] Add `paper_mode` parameter to constructor
  - [x] In submit_order, check paper_mode flag
  - [x] If paper_mode, call `_submit_paper_order()` instead
  - [x] Generate local simulated fill
  - [x] Log paper trade with "paper_trade_executed" event

- [x] Task 4: Implement simulated fills (AC: #2, #3)
  - [x] Use limit_price as base price (or placeholder)
  - [x] Apply configurable `paper_slippage` for market orders
  - [x] Assign simulated order_id (PAPER-XXXXXX format)
  - [x] Track paper positions with `_paper_positions` dict

- [x] Task 5: Implement paper position tracking (AC: #2)
  - [x] `_update_paper_position()` updates position after fill
  - [x] Weighted average entry price calculation
  - [x] Position closed when size reaches zero

- [x] Task 6: Write unit tests (AC: #1-3)
  - [x] Test paper mode initialization
  - [x] Test paper order submission
  - [x] Test paper position tracking
  - [x] Test slippage application
  - [x] Test fill callback triggered

## Dev Notes

### Fill Notification Polling

```python
async def _poll_for_fills(self):
    """Poll for new fill notifications."""
    last_check = {}  # Track last seen order IDs

    while self._polling_active:
        try:
            orders = await self.get_order_history()

            for order in orders:
                order_id = order["order_id"]
                if order_id not in last_check:
                    if order["status"] == OrderStatus.FILLED:
                        await self._on_fill(order)
                    last_check[order_id] = order

            await asyncio.sleep(1)  # Poll interval
        except Exception as e:
            logger.error("fill_poll_error", error=str(e))
            await asyncio.sleep(5)

async def _on_fill(self, order: dict):
    """Process a fill notification."""
    fill_data = {
        "order_id": order["order_id"],
        "fill_price": order.get("fill_price", order.get("price")),
        "fill_quantity": order.get("filled_quantity"),
        "timestamp": order.get("timestamp"),
    }

    if self._fill_callback:
        await self._fill_callback(fill_data)
```

### Paper Trading Mode

```python
class LighterBrokerAdapter(BrokerAdapter):
    def __init__(
        self,
        ...,
        paper_mode: bool = False,
    ):
        self._paper_mode = paper_mode
        self._paper_order_counter = 0

    async def submit_order(self, ...):
        if self._paper_mode:
            return await self._submit_paper_order(asset, amount, order_type, limit_price)
        # ... real order submission

    async def _submit_paper_order(
        self,
        asset: Asset,
        amount: Decimal,
        order_type: str,
        limit_price: Decimal | None,
    ) -> str:
        """Submit simulated paper order."""
        # Get current market price
        market_price = await self.get_current_price(asset)

        # Generate simulated order ID
        self._paper_order_counter += 1
        order_id = f"PAPER-{self._paper_order_counter:06d}"

        # Calculate fill price (with slippage for market orders)
        if order_type == "market":
            slippage = Decimal("0.001")  # 0.1% slippage
            side = "buy" if amount > 0 else "sell"
            if side == "buy":
                fill_price = market_price * (1 + slippage)
            else:
                fill_price = market_price * (1 - slippage)
        else:
            fill_price = limit_price

        # Generate simulated fill
        fill_data = {
            "order_id": order_id,
            "fill_price": fill_price,
            "fill_quantity": abs(amount),
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Log paper trade
        logger.info(
            "paper_trade_executed",
            order_id=order_id,
            symbol=asset.symbol,
            side="BUY" if amount > 0 else "SELL",
            quantity=str(abs(amount)),
            fill_price=str(fill_price),
        )

        # Process fill locally
        await self._on_fill(fill_data)

        return order_id
```

### Architecture Patterns and Constraints

- Paper mode reuses `PaperBroker` patterns but with Lighter.xyz prices
- Fill notifications can be via WebSocket (if available) or polling
- Consider using streaming adapter (Epic 10.5) for real-time prices in paper mode

### Prerequisites

- Stories 10.4.2-10.4.4 must be complete
- Market price fetching available

### References

- [Source: docs/internal/sprint-artifacts/epic-10-tech-spec.md#AC-10.4.5]
- [Source: docs/internal/planning/prd-epic-10.md#FR37, FR40 - Fill notifications and paper mode]
- [Source: docs/internal/planning/epics/epic-10-live-trading-production-readiness-lighter-xyz-integration.md#Story 10.4.5]

## Dev Agent Record

### Context Reference

- `docs/internal/sprint-artifacts/10-4-5-fill-notifications-paper-trading-mode.context.xml`

### Agent Model Used

Claude claude-opus-4-5-20251101

### Debug Log References

- Implemented fill callback mechanism with `set_fill_callback()` and `_fill_callback` storage
- Paper trading mode with `paper_mode` parameter in constructor
- `_submit_paper_order()` generates simulated fills with PAPER-XXXXXX order IDs
- Paper slippage configurable via `paper_slippage` parameter (default 0.1%)
- Paper position tracking with weighted average entry price calculation

### Completion Notes List

- ✅ `set_fill_callback()` stores async callback for fill notifications
- ✅ `_on_fill()` processes fills and calls registered callback with fill data dict
- ✅ Paper mode skips API calls and generates local simulated fills
- ✅ Paper order IDs use `PAPER-{counter:06d}` format
- ✅ Slippage applied to market orders (buy: price * (1 + slippage), sell: price * (1 - slippage))
- ✅ `_update_paper_position()` tracks paper positions with weighted avg entry
- ✅ `get_paper_positions()` returns current paper position state
- ✅ 8 unit tests covering paper mode initialization, order submission, position tracking, slippage, callbacks

### File List

| File | Action |
|------|--------|
| `rustybt/live/brokers/lighter_adapter.py` | Modified |
| `tests/live/lighter/test_lighter_broker.py` | Modified |

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-05 | Story drafted from Epic 10 breakdown | SM Agent |
| 2025-12-06 | Implementation complete, 8 tests passing | Dev Agent |
