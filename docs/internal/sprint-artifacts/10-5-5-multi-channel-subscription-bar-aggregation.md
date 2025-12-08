# Story 10.5.5: Multi-Channel Subscription & Bar Aggregation

Status: review

## Story

As a **developer**,
I want **to subscribe to multiple data channels and aggregate trades into OHLCV bars**,
So that **live trading receives complete market data**.

## Acceptance Criteria

1. **AC1:** Multiple channel subscriptions work:
   - Trades channel subscription works
   - Orderbook channel subscription works
   - Candlestick channel subscription works

2. **AC2:** BarBuffer aggregation works:
   - Trade ticks aggregated into OHLCV bars
   - Bar completed at timeframe boundary
   - Bar pushed to downstream handlers

3. **AC3:** Orderbook data parsed correctly:
   - Bids and asks extracted
   - Price levels updated correctly

4. **AC4:** Unsubscribe works:
   - `unsubscribe(symbols, channels)` removes subscriptions
   - No more messages received for unsubscribed channels

## Tasks / Subtasks

- [ ] Task 1: Implement multi-channel support (AC: #1)
  - [ ] Extend subscribe to support multiple channel types
  - [ ] Parse each message type appropriately
  - [ ] Route messages to correct handlers

- [ ] Task 2: Implement BarBuffer integration (AC: #2)
  - [ ] Create BarBuffer instance per symbol/timeframe
  - [ ] Feed TickData to BarBuffer
  - [ ] Handle bar completion callbacks
  - [ ] Push completed bars to engine

- [ ] Task 3: Implement orderbook parsing (AC: #3)
  - [ ] Parse orderbook update messages
  - [ ] Extract bids and asks
  - [ ] Create OrderbookData object

- [ ] Task 4: Implement unsubscribe (AC: #4)
  - [ ] Create `unsubscribe()` async method
  - [ ] Build unsubscription message
  - [ ] Send to WebSocket
  - [ ] Update subscription tracking

- [ ] Task 5: Write unit tests (AC: #1-4)
  - [ ] Test multi-channel subscription
  - [ ] Test bar aggregation
  - [ ] Test orderbook parsing
  - [ ] Test unsubscribe

## Dev Notes

### Multi-Channel Message Routing

```python
async def _message_handler(self):
    """Handle incoming WebSocket messages."""
    while self.is_connected():
        try:
            raw = await self._ws.recv()
            message = json.loads(raw)

            msg_type = message.get("type")

            if msg_type == "trade":
                tick = self.parse_message(message)
                if tick:
                    await self._on_tick(tick)
            elif msg_type == "orderbook":
                orderbook = self._parse_orderbook(message)
                if orderbook:
                    await self._on_orderbook(orderbook)
            elif msg_type == "candle":
                bar = self._parse_candle(message)
                if bar:
                    await self._on_bar(bar)
        except websockets.ConnectionClosed:
            break
        except Exception as e:
            logger.error("message_parse_error", error=str(e))
```

### BarBuffer Integration

```python
class LighterWebSocketAdapter(BaseWebSocketAdapter):
    def __init__(self, ...):
        ...
        self._bar_buffers: dict[str, BarBuffer] = {}  # symbol -> buffer

    def create_bar_buffer(self, symbol: str, timeframe: str) -> None:
        """Create BarBuffer for aggregating ticks to bars."""
        key = f"{symbol}_{timeframe}"
        self._bar_buffers[key] = BarBuffer(
            timeframe=timeframe,
            on_bar_complete=self._on_bar_complete
        )

    async def _on_tick(self, tick: TickData) -> None:
        """Process incoming tick, aggregate to bars."""
        # Find matching bar buffers
        for key, buffer in self._bar_buffers.items():
            if key.startswith(tick.symbol):
                buffer.add_tick(tick)

    def _on_bar_complete(self, bar: dict) -> None:
        """Called when a bar is complete."""
        if self._bar_callback:
            self._bar_callback(bar)
```

### Orderbook Parsing

```python
@dataclass
class OrderbookData:
    symbol: str
    bids: list[tuple[Decimal, Decimal]]  # (price, size)
    asks: list[tuple[Decimal, Decimal]]  # (price, size)
    timestamp: pd.Timestamp

def _parse_orderbook(self, message: dict) -> OrderbookData | None:
    """Parse orderbook update message."""
    if message.get("type") != "orderbook":
        return None

    return OrderbookData(
        symbol=message["symbol"],
        bids=[
            (Decimal(str(b["price"])), Decimal(str(b["size"])))
            for b in message.get("bids", [])
        ],
        asks=[
            (Decimal(str(a["price"])), Decimal(str(a["size"])))
            for a in message.get("asks", [])
        ],
        timestamp=pd.Timestamp(message["timestamp"], unit='ms'),
    )
```

### Unsubscribe Implementation

```python
async def unsubscribe(self, symbols: list[str], channels: list[str]) -> None:
    """Unsubscribe from Lighter.xyz WebSocket channels.

    Args:
        symbols: List of symbols to unsubscribe from
        channels: List of channel types to unsubscribe
    """
    if not self.is_connected():
        return

    message = self._build_unsubscription_message(symbols, channels)
    await self._ws.send(json.dumps(message))

    # Update subscription tracking
    for symbol in symbols:
        if symbol in self._subscriptions:
            self._subscriptions[symbol] -= set(channels)

    logger.info("lighter_unsubscribed", symbols=symbols, channels=channels)

def _build_unsubscription_message(self, symbols: list[str], channels: list[str]) -> dict:
    """Build WebSocket unsubscription message."""
    return {
        "type": "unsubscribe",
        "channels": [
            {"name": ch, "symbols": symbols}
            for ch in channels
        ]
    }
```

### Prerequisites

- Story 10.5.4 must be complete (connection works)
- BarBuffer exists in streaming infrastructure

### References

- [Source: docs/internal/sprint-artifacts/epic-10-tech-spec.md#AC-10.5.5]
- [Source: docs/internal/planning/epics/epic-10-live-trading-production-readiness-lighter-xyz-integration.md#Story 10.5.5]

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
