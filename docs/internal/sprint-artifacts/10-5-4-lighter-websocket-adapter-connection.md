# Story 10.5.4: Lighter.xyz WebSocket Adapter & Connection

Status: review

## Story

As a **developer**,
I want **a LighterWebSocketAdapter that can connect and subscribe to real-time data**,
So that **live trading can receive real-time price updates**.

## Acceptance Criteria

1. **AC1:** `LighterWebSocketAdapter` class exists in `rustybt/live/streaming/lighter_stream.py`:
   - Extends `BaseWebSocketAdapter` ABC
   - Implements required interface methods

2. **AC2:** WebSocket connection works:
   - Connection established to Lighter.xyz WebSocket endpoint
   - Connection state tracked (`is_connected()`)
   - Disconnect handled gracefully

3. **AC3:** Subscription to trades channel works:
   - `subscribe(symbols, ["trades"])` subscribes to trade updates
   - Subscription confirmed by Lighter.xyz

4. **AC4:** Message parsing works:
   - Raw WebSocket messages parsed
   - `parse_message()` returns `TickData` or None

## Tasks / Subtasks

- [ ] Task 1: Create adapter file and class skeleton (AC: #1)
  - [ ] Create `rustybt/live/streaming/lighter_stream.py`
  - [ ] Define `LighterWebSocketAdapter` class
  - [ ] Implement `BaseWebSocketAdapter` ABC interface
  - [ ] Add WebSocket URL constants

- [ ] Task 2: Implement connect/disconnect (AC: #2)
  - [ ] Create `connect()` async method
  - [ ] Create `disconnect()` async method
  - [ ] Track connection state
  - [ ] Handle connection errors

- [ ] Task 3: Implement subscribe method (AC: #3)
  - [ ] Create `subscribe()` async method
  - [ ] Build subscription message
  - [ ] Send to WebSocket
  - [ ] Track subscriptions

- [ ] Task 4: Implement message parsing (AC: #4)
  - [ ] Create `parse_message()` method
  - [ ] Parse trade messages to TickData
  - [ ] Handle unknown message types
  - [ ] Return None for non-data messages

- [ ] Task 5: Write unit tests (AC: #1-4)
  - [ ] Create `tests/live/lighter/test_lighter_stream.py`
  - [ ] Test connection with mock
  - [ ] Test subscription
  - [ ] Test message parsing

## Dev Notes

### Class Structure

```python
class LighterWebSocketAdapter(BaseWebSocketAdapter):
    """Lighter.xyz WebSocket adapter for real-time streaming.

    Implements BaseWebSocketAdapter for Lighter.xyz data streams.
    Supports trades, orderbook, and candlestick subscriptions.
    """

    # WebSocket endpoints
    MAINNET_WS_URL = "wss://mainnet.zklighter.elliot.ai/ws"
    TESTNET_WS_URL = "wss://testnet.zklighter.elliot.ai/ws"

    def __init__(self, testnet: bool = True):
        """Initialize Lighter WebSocket adapter."""
        self._ws_url = self.TESTNET_WS_URL if testnet else self.MAINNET_WS_URL
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._subscriptions: dict[str, set[str]] = {}  # symbol -> channels
        self._connected = False
```

### Connect Implementation

```python
async def connect(self) -> None:
    """Establish WebSocket connection to Lighter.xyz."""
    try:
        self._ws = await websockets.connect(self._ws_url)
        self._connected = True
        logger.info("lighter_ws_connected", url=self._ws_url)
    except Exception as e:
        logger.error("lighter_ws_connection_failed", error=str(e))
        raise LighterConnectionError(f"WebSocket connection failed: {e}")

async def disconnect(self) -> None:
    """Close WebSocket connection."""
    if self._ws:
        await self._ws.close()
        self._connected = False
        logger.info("lighter_ws_disconnected")

def is_connected(self) -> bool:
    """Check if WebSocket is connected."""
    return self._connected and self._ws is not None and self._ws.open
```

### Subscribe Implementation

```python
async def subscribe(self, symbols: list[str], channels: list[str]) -> None:
    """Subscribe to Lighter.xyz WebSocket channels.

    Args:
        symbols: List of symbols to subscribe to
        channels: List of channel types ("trades", "orderbook", "candlesticks")
    """
    if not self.is_connected():
        raise LighterConnectionError("Not connected")

    message = self._build_subscription_message(symbols, channels)
    await self._ws.send(json.dumps(message))

    # Track subscriptions
    for symbol in symbols:
        if symbol not in self._subscriptions:
            self._subscriptions[symbol] = set()
        self._subscriptions[symbol].update(channels)

    logger.info("lighter_subscribed", symbols=symbols, channels=channels)

def _build_subscription_message(self, symbols: list[str], channels: list[str]) -> dict:
    """Build WebSocket subscription message."""
    return {
        "type": "subscribe",
        "channels": [
            {"name": ch, "symbols": symbols}
            for ch in channels
        ]
    }
```

### Message Parsing

```python
def parse_message(self, raw_message: dict) -> TickData | None:
    """Parse Lighter.xyz WebSocket message to TickData.

    Args:
        raw_message: Raw message from WebSocket

    Returns:
        TickData if trade message, None otherwise
    """
    msg_type = raw_message.get("type")

    if msg_type == "trade":
        return TickData(
            symbol=raw_message["symbol"],
            price=Decimal(str(raw_message["price"])),
            size=Decimal(str(raw_message["size"])),
            side=raw_message.get("side", "unknown"),
            timestamp=pd.Timestamp(raw_message["timestamp"], unit='ms'),
        )

    # Non-trade messages (orderbook updates, etc.)
    return None
```

### Prerequisites

- Epic 10.4 in progress (broker adapter provides connection patterns)
- WebSocket infrastructure understood

### References

- [Source: docs/internal/sprint-artifacts/epic-10-tech-spec.md#AC-10.5.4]
- [Source: docs/internal/sprint-artifacts/epic-10-tech-spec.md#APIs and Interfaces - LighterWebSocketAdapter]
- [Source: docs/internal/planning/epics/epic-10-live-trading-production-readiness-lighter-xyz-integration.md#Story 10.5.4]

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
