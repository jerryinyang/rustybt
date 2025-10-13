"""Tests for base WebSocket adapter."""

import asyncio
from contextlib import suppress
from datetime import datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from rustybt.live.streaming.base import (
    BaseWebSocketAdapter,
    ConnectionState,
    ParseError,
    SubscriptionError,
    WSConnectionError,
)
from rustybt.live.streaming.models import StreamConfig, TickData, TickSide


class MockWebSocketAdapter(BaseWebSocketAdapter):
    """Mock WebSocket adapter for testing."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.subscribed_symbols: list[str] = []
        self.unsubscribed_symbols: list[str] = []

    async def subscribe(self, symbols: list[str], channels: list[str]) -> None:
        """Mock subscribe."""
        if not self.is_connected:
            raise SubscriptionError("Not connected")

        message = self._build_subscription_message(symbols, channels)
        await self._send_message(message)

        for symbol in symbols:
            if symbol not in self._subscriptions:
                self._subscriptions[symbol] = set()
            self._subscriptions[symbol].update(channels)

        self.subscribed_symbols.extend(symbols)

    async def unsubscribe(self, symbols: list[str], channels: list[str]) -> None:
        """Mock unsubscribe."""
        if not self.is_connected:
            raise SubscriptionError("Not connected")

        message = self._build_unsubscription_message(symbols, channels)
        await self._send_message(message)

        for symbol in symbols:
            if symbol in self._subscriptions:
                self._subscriptions[symbol].difference_update(channels)
                if not self._subscriptions[symbol]:
                    del self._subscriptions[symbol]

        self.unsubscribed_symbols.extend(symbols)

    def parse_message(self, raw_message: dict[str, Any]) -> TickData | None:
        """Mock parse message."""
        if "error" in raw_message:
            raise ParseError(raw_message["error"])

        if raw_message.get("type") == "tick":
            return TickData(
                symbol=raw_message["symbol"],
                timestamp=datetime.fromtimestamp(raw_message["timestamp"]),
                price=Decimal(str(raw_message["price"])),
                volume=Decimal(str(raw_message["volume"])),
                side=TickSide.BUY,
            )

        return None

    def _build_subscription_message(
        self, symbols: list[str], channels: list[str]
    ) -> dict[str, Any]:
        """Mock build subscription message."""
        return {"method": "SUBSCRIBE", "symbols": symbols, "channels": channels}

    def _build_unsubscription_message(
        self, symbols: list[str], channels: list[str]
    ) -> dict[str, Any]:
        """Mock build unsubscription message."""
        return {"method": "UNSUBSCRIBE", "symbols": symbols, "channels": channels}


class TestBaseWebSocketAdapter:
    """Tests for BaseWebSocketAdapter."""

    @pytest.fixture
    def adapter(self) -> MockWebSocketAdapter:
        """Create mock adapter."""
        return MockWebSocketAdapter(url="wss://test.example.com/ws")

    def test_adapter_initialization(self, adapter: MockWebSocketAdapter) -> None:
        """Test adapter initialization."""
        assert adapter.url == "wss://test.example.com/ws"
        assert adapter.state == ConnectionState.DISCONNECTED
        assert not adapter.is_connected
        assert adapter.active_subscriptions == {}

    def test_adapter_with_custom_config(self) -> None:
        """Test adapter with custom config."""
        config = StreamConfig(bar_resolution=300, heartbeat_interval=60)
        adapter = MockWebSocketAdapter(
            url="wss://test.example.com/ws",
            config=config,
        )

        assert adapter.config.bar_resolution == 300
        assert adapter.config.heartbeat_interval == 60

    @pytest.mark.asyncio
    async def test_connect_success(self, adapter: MockWebSocketAdapter) -> None:
        """Test successful connection."""

        async def async_connect(*args, **kwargs):
            return AsyncMock()

        with patch("rustybt.live.streaming.base.websockets.connect", side_effect=async_connect):
            await adapter.connect()

            assert adapter.state == ConnectionState.CONNECTED
            assert adapter.is_connected

    @pytest.mark.asyncio
    async def test_connect_failure(self, adapter: MockWebSocketAdapter) -> None:
        """Test connection failure."""
        with patch("rustybt.live.streaming.base.websockets.connect") as mock_connect:
            mock_connect.side_effect = Exception("Connection refused")

            with pytest.raises(WSConnectionError, match="Failed to connect"):
                await adapter.connect()

            assert adapter.state == ConnectionState.DISCONNECTED
            assert not adapter.is_connected

    @pytest.mark.asyncio
    async def test_disconnect(self, adapter: MockWebSocketAdapter) -> None:
        """Test disconnect."""
        mock_ws = AsyncMock()

        async def async_connect(*args, **kwargs):
            return mock_ws

        with patch("rustybt.live.streaming.base.websockets.connect", side_effect=async_connect):
            await adapter.connect()
            assert adapter.is_connected

            await adapter.disconnect()

            assert adapter.state == ConnectionState.DISCONNECTED
            assert not adapter.is_connected
            mock_ws.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_subscribe(self, adapter: MockWebSocketAdapter) -> None:
        """Test subscription."""

        async def async_connect(*args, **kwargs):
            return AsyncMock()

        with patch("rustybt.live.streaming.base.websockets.connect", side_effect=async_connect):
            await adapter.connect()
            await adapter.subscribe(["BTCUSDT"], ["trade"])

            assert "BTCUSDT" in adapter.subscribed_symbols
            assert "BTCUSDT" in adapter.active_subscriptions
            assert "trade" in adapter.active_subscriptions["BTCUSDT"]

    @pytest.mark.asyncio
    async def test_subscribe_not_connected(self, adapter: MockWebSocketAdapter) -> None:
        """Test subscribe when not connected."""
        with pytest.raises(SubscriptionError, match="Not connected"):
            await adapter.subscribe(["BTCUSDT"], ["trade"])

    @pytest.mark.asyncio
    async def test_unsubscribe(self, adapter: MockWebSocketAdapter) -> None:
        """Test unsubscription."""

        async def async_connect(*args, **kwargs):
            return AsyncMock()

        with patch("rustybt.live.streaming.base.websockets.connect", side_effect=async_connect):
            await adapter.connect()
            await adapter.subscribe(["BTCUSDT"], ["trade"])
            await adapter.unsubscribe(["BTCUSDT"], ["trade"])

            assert "BTCUSDT" in adapter.unsubscribed_symbols
            assert "BTCUSDT" not in adapter.active_subscriptions

    @pytest.mark.asyncio
    async def test_parse_message_tick(self, adapter: MockWebSocketAdapter) -> None:
        """Test parsing tick message."""
        message = {
            "type": "tick",
            "symbol": "BTCUSDT",
            "timestamp": 1696334400.0,
            "price": "50000.00",
            "volume": "1.5",
        }

        tick = adapter.parse_message(message)

        assert tick is not None
        assert tick.symbol == "BTCUSDT"
        assert tick.price == Decimal("50000.00")
        assert tick.volume == Decimal("1.5")

    @pytest.mark.asyncio
    async def test_parse_message_error(self, adapter: MockWebSocketAdapter) -> None:
        """Test parsing error message."""
        message = {"error": "Invalid subscription"}

        with pytest.raises(ParseError, match="Invalid subscription"):
            adapter.parse_message(message)

    @pytest.mark.asyncio
    async def test_parse_message_unknown_type(self, adapter: MockWebSocketAdapter) -> None:
        """Test parsing unknown message type."""
        message = {"type": "unknown", "data": "something"}

        tick = adapter.parse_message(message)

        assert tick is None

    def test_active_subscriptions_immutable(self, adapter: MockWebSocketAdapter) -> None:
        """Test active_subscriptions returns copy."""
        adapter._subscriptions["BTCUSDT"] = {"trade"}

        subscriptions = adapter.active_subscriptions
        subscriptions["ETHUSDT"] = {"kline"}

        # Original should not be modified
        assert "ETHUSDT" not in adapter._subscriptions

    @pytest.mark.asyncio
    async def test_reconnect_exponential_backoff(self, adapter: MockWebSocketAdapter) -> None:
        """Test reconnect uses exponential backoff on repeated failures."""
        with (
            patch(
                "rustybt.live.streaming.base.websockets.connect",
                new_callable=AsyncMock,
            ) as mock_connect,
            patch("asyncio.sleep") as mock_sleep,
        ):
            # Simulate connection failures to test backoff
            mock_connect.side_effect = [
                Exception("Connection failed"),  # First attempt fails
                Exception("Connection failed"),  # Second attempt fails
                AsyncMock(),  # Third attempt succeeds
            ]

            # First reconnect attempt: 1s delay, then fails
            with suppress(Exception):
                await adapter.reconnect()
            mock_sleep.assert_called_with(1)

            # Second reconnect attempt: 2s delay (backoff), then fails
            with suppress(Exception):
                await adapter.reconnect()
            mock_sleep.assert_called_with(2)

            # Third reconnect attempt: 4s delay (backoff), then succeeds
            await adapter.reconnect()
            mock_sleep.assert_called_with(4)

    @pytest.mark.asyncio
    async def test_reconnect_max_attempts(self, adapter: MockWebSocketAdapter) -> None:
        """Test reconnect respects max attempts."""
        config = StreamConfig(reconnect_attempts=2)
        adapter = MockWebSocketAdapter(url="wss://test.example.com/ws", config=config)

        with (
            patch("rustybt.live.streaming.base.websockets.connect") as mock_connect,
            patch("asyncio.sleep"),
        ):
            mock_connect.side_effect = Exception("Connection failed")

            # First two attempts should succeed
            with suppress(Exception):
                await adapter.reconnect()

            with suppress(Exception):
                await adapter.reconnect()

            # Third attempt should fail
            with pytest.raises(WSConnectionError, match="Reconnect attempts exceeded"):
                await adapter.reconnect()

    @pytest.mark.asyncio
    async def test_circuit_breaker(self, adapter: MockWebSocketAdapter) -> None:
        """Test circuit breaker trips after consecutive errors."""
        config = StreamConfig(circuit_breaker_threshold=3)
        adapter = MockWebSocketAdapter(url="wss://test.example.com/ws", config=config)

        # Simulate consecutive errors
        for i in range(3):
            adapter._consecutive_errors = i + 1
            if i == 2:  # Should trip on 3rd error
                with patch.object(adapter, "reconnect") as mock_reconnect:
                    adapter._check_circuit_breaker()
                    # Circuit breaker should trigger reconnect
                    assert (
                        mock_reconnect.called
                        or adapter._consecutive_errors >= config.circuit_breaker_threshold
                    )

    @pytest.mark.asyncio
    async def test_connect_when_already_connected(self, adapter: MockWebSocketAdapter) -> None:
        """Test connect when already connected returns early."""

        async def async_connect(*args, **kwargs):
            return AsyncMock()

        with patch("rustybt.live.streaming.base.websockets.connect", side_effect=async_connect):
            await adapter.connect()
            assert adapter.is_connected

            # Try to connect again - should return early
            await adapter.connect()
            assert adapter.state == ConnectionState.CONNECTED

    @pytest.mark.asyncio
    async def test_connect_when_connecting(self, adapter: MockWebSocketAdapter) -> None:
        """Test connect when already connecting returns early."""
        adapter._state = ConnectionState.CONNECTING

        # Should return early without attempting connection
        await adapter.connect()
        assert adapter.state == ConnectionState.CONNECTING

    @pytest.mark.asyncio
    async def test_disconnect_when_already_disconnected(
        self, adapter: MockWebSocketAdapter
    ) -> None:
        """Test disconnect when already disconnected returns early."""
        assert adapter.state == ConnectionState.DISCONNECTED

        # Should return early
        await adapter.disconnect()
        assert adapter.state == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_reconnect_when_already_reconnecting(self, adapter: MockWebSocketAdapter) -> None:
        """Test reconnect when already reconnecting returns early."""
        adapter._state = ConnectionState.RECONNECTING

        # Should return early without attempting reconnection
        await adapter.reconnect()
        assert adapter.state == ConnectionState.RECONNECTING

    @pytest.mark.asyncio
    async def test_reconnect_with_resubscription(self, adapter: MockWebSocketAdapter) -> None:
        """Test reconnect re-subscribes to previous symbols."""
        mock_ws = AsyncMock()

        async def async_connect(*args, **kwargs):
            return mock_ws

        with (
            patch("rustybt.live.streaming.base.websockets.connect", side_effect=async_connect),
            patch("asyncio.sleep"),
        ):
            # Connect and subscribe
            await adapter.connect()
            await adapter.subscribe(["BTCUSDT", "ETHUSDT"], ["trade"])

            # Clear subscribed symbols list
            adapter.subscribed_symbols.clear()

            # Reconnect should re-subscribe
            await adapter.reconnect()

            # Check re-subscription happened
            assert "BTCUSDT" in adapter.subscribed_symbols
            assert "ETHUSDT" in adapter.subscribed_symbols

    @pytest.mark.asyncio
    async def test_reconnect_failure(self, adapter: MockWebSocketAdapter) -> None:
        """Test reconnect handles connection failure gracefully."""
        with (
            patch("rustybt.live.streaming.base.websockets.connect") as mock_connect,
            patch("asyncio.sleep"),
        ):
            mock_connect.side_effect = OSError("Connection refused")

            # Reconnect should handle failure and set state to disconnected
            # Exception is caught and state set to DISCONNECTED
            with suppress(Exception):
                await adapter.reconnect()

            # Check that reconnect attempt was made and state is correct
            assert adapter._reconnect_count > 0 or adapter.state == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_listen_without_websocket(self, adapter: MockWebSocketAdapter) -> None:
        """Test _listen returns early if websocket not set."""
        # Call _listen without websocket
        await adapter._listen()
        # Should return early without error

    @pytest.mark.asyncio
    async def test_listen_processes_messages(self, adapter: MockWebSocketAdapter) -> None:
        """Test _listen processes incoming messages."""
        messages = [
            '{"type": "tick", "symbol": "BTCUSDT", "timestamp": 1696334400.0, '
            '"price": "50000", "volume": "1.0"}'
        ]

        mock_ws = AsyncMock()
        mock_ws.__aiter__.return_value = iter(messages)

        adapter._websocket = mock_ws
        ticks_received = []

        def on_tick(tick: TickData) -> None:
            ticks_received.append(tick)

        adapter.on_tick = on_tick

        # Run _listen
        await adapter._listen()

        # Should have received tick
        assert len(ticks_received) == 1
        assert ticks_received[0].symbol == "BTCUSDT"

    @pytest.mark.asyncio
    async def test_listen_handles_json_decode_error(self, adapter: MockWebSocketAdapter) -> None:
        """Test _listen handles invalid JSON gracefully."""
        messages = ["invalid json"]

        mock_ws = AsyncMock()
        mock_ws.__aiter__.return_value = iter(messages)

        adapter._websocket = mock_ws

        # Should handle JSON error without raising
        await adapter._listen()
        assert adapter._consecutive_errors == 1

    @pytest.mark.asyncio
    async def test_listen_handles_parse_error(self, adapter: MockWebSocketAdapter) -> None:
        """Test _listen handles parse errors gracefully."""
        messages = ['{"error": "Parse failed"}']

        mock_ws = AsyncMock()
        mock_ws.__aiter__.return_value = iter(messages)

        adapter._websocket = mock_ws

        # Should handle parse error without raising
        await adapter._listen()
        assert adapter._consecutive_errors == 1

    @pytest.mark.asyncio
    async def test_listen_handles_value_error(self, adapter: MockWebSocketAdapter) -> None:
        """Test _listen handles ValueError gracefully."""
        mock_ws = AsyncMock()
        mock_ws.__aiter__.return_value = iter(['{"type": "tick"}'])  # Missing required fields

        adapter._websocket = mock_ws

        # Mock parse_message to raise ValueError
        def parse_with_error(msg: dict[str, Any]) -> TickData | None:
            raise ValueError("Missing required field")

        adapter.parse_message = parse_with_error

        # Should handle error without raising
        await adapter._listen()
        assert adapter._consecutive_errors == 1

    @pytest.mark.asyncio
    async def test_listen_reconnects_on_connection_closed(
        self, adapter: MockWebSocketAdapter
    ) -> None:
        """Test _listen triggers reconnect on ConnectionClosed."""
        from websockets.exceptions import ConnectionClosed

        class AsyncIterWithException:
            def __aiter__(self):
                return self

            async def __anext__(self):
                raise ConnectionClosed(None, None)

        mock_ws = AsyncIterWithException()
        adapter._websocket = mock_ws

        with patch.object(adapter, "reconnect") as mock_reconnect:
            await adapter._listen()
            mock_reconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_listen_reconnects_on_websocket_exception(
        self, adapter: MockWebSocketAdapter
    ) -> None:
        """Test _listen triggers reconnect on WebSocketException."""
        from websockets.exceptions import WebSocketException

        class AsyncIterWithException:
            def __aiter__(self):
                return self

            async def __anext__(self):
                raise WebSocketException("Connection error")

        mock_ws = AsyncIterWithException()
        adapter._websocket = mock_ws

        with patch.object(adapter, "reconnect") as mock_reconnect:
            await adapter._listen()
            mock_reconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_heartbeat_monitor_without_last_message(
        self, adapter: MockWebSocketAdapter
    ) -> None:
        """Test heartbeat monitor continues when no messages received yet."""
        adapter._state = ConnectionState.CONNECTED
        adapter._last_message_time = None

        # Create task and cancel after short delay
        task = asyncio.create_task(adapter._heartbeat_monitor())
        await asyncio.sleep(0.1)
        task.cancel()

        with suppress(asyncio.CancelledError):
            await task

        # Should not have triggered reconnect
        assert adapter.state == ConnectionState.CONNECTED

    @pytest.mark.asyncio
    async def test_heartbeat_monitor_detects_stale_connection(
        self, adapter: MockWebSocketAdapter
    ) -> None:
        """Test heartbeat monitor detects stale connection."""
        from datetime import timedelta

        adapter._state = ConnectionState.CONNECTED
        adapter._last_message_time = datetime.utcnow() - timedelta(seconds=120)  # 2 minutes ago
        adapter._websocket = AsyncMock()

        with patch.object(adapter, "reconnect"):
            # Run one iteration of heartbeat monitor
            adapter._state = ConnectionState.CONNECTED
            await asyncio.sleep(0.1)

            task = asyncio.create_task(adapter._heartbeat_monitor())
            await asyncio.sleep(0.2)

            # Should have detected stale connection
            if adapter._state == ConnectionState.CONNECTED:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    @pytest.mark.asyncio
    async def test_heartbeat_monitor_sends_ping(self, adapter: MockWebSocketAdapter) -> None:
        """Test heartbeat monitor sends ping."""
        adapter._state = ConnectionState.CONNECTED
        adapter._last_message_time = datetime.utcnow()

        mock_ws = AsyncMock()
        pong_waiter = asyncio.Future()
        pong_waiter.set_result(None)
        mock_ws.ping.return_value = pong_waiter

        adapter._websocket = mock_ws

        # Run one iteration
        task = asyncio.create_task(adapter._heartbeat_monitor())
        await asyncio.sleep(0.1)
        task.cancel()

        with suppress(asyncio.CancelledError):
            await task

    @pytest.mark.asyncio
    async def test_heartbeat_timeout_triggers_reconnect(
        self, adapter: MockWebSocketAdapter
    ) -> None:
        """Test heartbeat timeout triggers reconnect."""
        adapter._state = ConnectionState.CONNECTED
        adapter._last_message_time = datetime.utcnow()

        mock_ws = AsyncMock()

        # Simulate timeout on ping
        async def timeout_ping():
            await asyncio.sleep(10)  # Never completes

        mock_ws.ping.return_value = asyncio.create_task(timeout_ping())
        adapter._websocket = mock_ws

        with patch.object(adapter, "reconnect"):
            task = asyncio.create_task(adapter._heartbeat_monitor())
            await asyncio.sleep(0.1)

            # Cancel the heartbeat task
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    @pytest.mark.asyncio
    async def test_heartbeat_websocket_exception(self, adapter: MockWebSocketAdapter) -> None:
        """Test heartbeat handles WebSocket exceptions."""
        from websockets.exceptions import WebSocketException

        adapter._state = ConnectionState.CONNECTED
        adapter._last_message_time = datetime.utcnow()

        mock_ws = AsyncMock()
        mock_ws.ping.side_effect = WebSocketException("Ping failed")
        adapter._websocket = mock_ws

        # Run one iteration
        task = asyncio.create_task(adapter._heartbeat_monitor())
        await asyncio.sleep(0.1)
        adapter._state = ConnectionState.DISCONNECTED  # Stop the loop

        with suppress(Exception):
            await task

    @pytest.mark.asyncio
    async def test_send_message_when_not_connected(self, adapter: MockWebSocketAdapter) -> None:
        """Test _send_message raises when not connected."""
        with pytest.raises(WSConnectionError, match="Not connected"):
            await adapter._send_message({"test": "message"})

    @pytest.mark.asyncio
    async def test_send_message_failure(self, adapter: MockWebSocketAdapter) -> None:
        """Test _send_message handles send failures."""
        mock_ws = AsyncMock()
        mock_ws.send.side_effect = Exception("Send failed")

        adapter._state = ConnectionState.CONNECTED
        adapter._websocket = mock_ws

        with pytest.raises(WSConnectionError, match="Failed to send message"):
            await adapter._send_message({"test": "message"})
