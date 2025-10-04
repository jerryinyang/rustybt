"""Base WebSocket adapter for real-time market data streaming."""

import asyncio
import json
from abc import ABC, abstractmethod
from collections.abc import Callable
from contextlib import suppress
from datetime import datetime
from enum import Enum
from typing import Any

import structlog
import websockets
from websockets.client import WebSocketClientProtocol
from websockets.exceptions import ConnectionClosed, WebSocketException

from rustybt.live.streaming.models import StreamConfig, TickData

logger = structlog.get_logger(__name__)


class ConnectionState(str, Enum):
    """WebSocket connection state."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"


class WebSocketError(Exception):
    """Base exception for WebSocket errors."""


class WSConnectionError(WebSocketError):
    """WebSocket connection error."""


class ParseError(WebSocketError):
    """Message parsing error."""


class SubscriptionError(WebSocketError):
    """Subscription error."""


class BaseWebSocketAdapter(ABC):
    """Base class for WebSocket streaming adapters.

    Provides connection management, subscription handling, message parsing,
    and error handling for real-time market data streams.

    Subclasses must implement:
    - subscribe()
    - unsubscribe()
    - parse_message()
    - _build_subscription_message()
    - _build_unsubscription_message()
    """

    def __init__(
        self,
        url: str,
        config: StreamConfig | None = None,
        on_tick: Callable[[TickData], None] | None = None,
    ) -> None:
        """Initialize WebSocket adapter.

        Args:
            url: WebSocket URL
            config: Streaming configuration
            on_tick: Callback for tick data (called when tick parsed)
        """
        self.url = url
        self.config = config or StreamConfig()
        self.on_tick = on_tick

        self._state = ConnectionState.DISCONNECTED
        self._websocket: WebSocketClientProtocol | None = None
        self._subscriptions: dict[str, set[str]] = {}  # symbol -> channels
        self._last_message_time: datetime | None = None
        self._reconnect_count = 0
        self._consecutive_errors = 0
        self._listen_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._reconnect_task: asyncio.Task | None = None

    @property
    def state(self) -> ConnectionState:
        """Get current connection state."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self._state == ConnectionState.CONNECTED

    @property
    def active_subscriptions(self) -> dict[str, set[str]]:
        """Get active subscriptions (symbol -> channels)."""
        return self._subscriptions.copy()

    async def connect(self) -> None:
        """Connect to WebSocket server.

        Raises:
            WSConnectionError: If connection fails
        """
        if self._state in (ConnectionState.CONNECTED, ConnectionState.CONNECTING):
            logger.warning("already_connected", state=self._state)
            return

        self._state = ConnectionState.CONNECTING
        logger.info("connecting_websocket", url=self.url)

        try:
            self._websocket = await websockets.connect(self.url)
            self._state = ConnectionState.CONNECTED
            self._last_message_time = datetime.utcnow()
            self._consecutive_errors = 0
            logger.info("websocket_connected", url=self.url)

            # Start listening for messages
            self._listen_task = asyncio.create_task(self._listen())

            # Start heartbeat monitoring
            self._heartbeat_task = asyncio.create_task(self._heartbeat_monitor())

        except Exception as e:
            self._state = ConnectionState.DISCONNECTED
            logger.error("connection_failed", url=self.url, error=str(e))
            raise WSConnectionError(f"Failed to connect to {self.url}: {e}") from e

    async def disconnect(self) -> None:
        """Disconnect from WebSocket server."""
        if self._state == ConnectionState.DISCONNECTED:
            logger.warning("already_disconnected")
            return

        logger.info("disconnecting_websocket", url=self.url)

        # Cancel tasks
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._listen_task

        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._heartbeat_task

        # Close WebSocket
        if self._websocket:
            await self._websocket.close()
            self._websocket = None

        self._state = ConnectionState.DISCONNECTED
        self._last_message_time = None
        logger.info("websocket_disconnected", url=self.url)

    async def reconnect(self) -> None:
        """Reconnect to WebSocket server with exponential backoff."""
        if self._state == ConnectionState.RECONNECTING:
            logger.warning("already_reconnecting")
            return

        # Check reconnect attempts limit
        if (
            self.config.reconnect_attempts is not None
            and self._reconnect_count >= self.config.reconnect_attempts
        ):
            logger.error(
                "reconnect_attempts_exceeded",
                attempts=self._reconnect_count,
                max_attempts=self.config.reconnect_attempts,
            )
            raise WSConnectionError("Reconnect attempts exceeded")

        self._state = ConnectionState.RECONNECTING
        self._reconnect_count += 1

        # Calculate backoff delay
        delay = min(
            self.config.reconnect_delay * (2 ** (self._reconnect_count - 1)),
            self.config.reconnect_max_delay,
        )

        logger.info(
            "reconnecting_websocket",
            url=self.url,
            attempt=self._reconnect_count,
            delay=delay,
        )

        await asyncio.sleep(delay)

        try:
            # Save subscriptions for re-subscription
            subscriptions_to_restore = self._subscriptions.copy()

            # Disconnect and reconnect
            await self.disconnect()
            await self.connect()

            # Re-subscribe to all symbols
            for symbol, channels in subscriptions_to_restore.items():
                await self.subscribe([symbol], list(channels))

            logger.info("reconnect_successful", url=self.url)
            self._reconnect_count = 0

        except (WebSocketException, OSError) as e:
            logger.error(
                "reconnect_failed", url=self.url, error=str(e), attempt=self._reconnect_count
            )
            # Will retry on next heartbeat timeout or disconnect
            self._state = ConnectionState.DISCONNECTED

    @abstractmethod
    async def subscribe(self, symbols: list[str], channels: list[str]) -> None:
        """Subscribe to symbols and channels.

        Args:
            symbols: List of symbols to subscribe
            channels: List of channels (e.g., 'trade', 'kline', 'ticker')

        Raises:
            SubscriptionError: If subscription fails
        """

    @abstractmethod
    async def unsubscribe(self, symbols: list[str], channels: list[str]) -> None:
        """Unsubscribe from symbols and channels.

        Args:
            symbols: List of symbols to unsubscribe
            channels: List of channels

        Raises:
            SubscriptionError: If unsubscription fails
        """

    @abstractmethod
    def parse_message(self, raw_message: dict[str, Any]) -> TickData | None:
        """Parse raw WebSocket message to TickData.

        Args:
            raw_message: Raw message from WebSocket

        Returns:
            TickData if message parsed successfully, None otherwise

        Raises:
            ParseError: If message parsing fails critically
        """

    @abstractmethod
    def _build_subscription_message(
        self, symbols: list[str], channels: list[str]
    ) -> dict[str, Any]:
        """Build subscription message for exchange.

        Args:
            symbols: List of symbols
            channels: List of channels

        Returns:
            Subscription message as dict
        """

    @abstractmethod
    def _build_unsubscription_message(
        self, symbols: list[str], channels: list[str]
    ) -> dict[str, Any]:
        """Build unsubscription message for exchange.

        Args:
            symbols: List of symbols
            channels: List of channels

        Returns:
            Unsubscription message as dict
        """

    async def _listen(self) -> None:
        """Listen for WebSocket messages."""
        if not self._websocket:
            logger.error("websocket_not_connected")
            return

        try:
            async for message in self._websocket:
                self._last_message_time = datetime.utcnow()
                self._consecutive_errors = 0

                try:
                    # Parse JSON message
                    raw_message = json.loads(message)

                    # Parse to TickData
                    tick = self.parse_message(raw_message)

                    # Call tick callback if provided
                    if tick and self.on_tick:
                        self.on_tick(tick)

                except json.JSONDecodeError as e:
                    logger.warning("invalid_json_message", message=message[:100], error=str(e))
                    self._consecutive_errors += 1
                    self._check_circuit_breaker()

                except ParseError as e:
                    logger.warning("parse_error", error=str(e))
                    self._consecutive_errors += 1
                    self._check_circuit_breaker()

                except (ValueError, KeyError, TypeError) as e:
                    logger.error("message_handling_error", error=str(e))
                    self._consecutive_errors += 1
                    self._check_circuit_breaker()

        except ConnectionClosed as e:
            logger.warning("websocket_connection_closed", code=e.code, reason=e.reason)
            await self.reconnect()

        except (WebSocketException, OSError) as e:
            logger.error("websocket_exception", error=str(e))
            await self.reconnect()

    async def _heartbeat_monitor(self) -> None:
        """Monitor connection health and send heartbeats."""
        while self._state == ConnectionState.CONNECTED:
            await asyncio.sleep(self.config.heartbeat_interval)

            if not self._last_message_time:
                continue

            # Check if connection is stale
            time_since_last_message = (datetime.utcnow() - self._last_message_time).total_seconds()

            if time_since_last_message > self.config.heartbeat_timeout:
                logger.warning(
                    "stale_connection_detected",
                    seconds_since_last_message=time_since_last_message,
                )
                await self.reconnect()
                return

            # Send ping if WebSocket supports it
            if self._websocket:
                try:
                    pong_waiter = await self._websocket.ping()
                    await asyncio.wait_for(pong_waiter, timeout=5.0)
                    logger.debug("heartbeat_pong_received")
                except TimeoutError:
                    logger.warning("heartbeat_timeout")
                    await self.reconnect()
                    return
                except (WebSocketException, OSError) as e:
                    logger.warning("heartbeat_error", error=str(e))

    def _check_circuit_breaker(self) -> None:
        """Check if circuit breaker should trip."""
        if self._consecutive_errors >= self.config.circuit_breaker_threshold:
            logger.error(
                "circuit_breaker_tripped",
                consecutive_errors=self._consecutive_errors,
                threshold=self.config.circuit_breaker_threshold,
            )
            # Trigger reconnection
            self._reconnect_task = asyncio.create_task(self.reconnect())

    async def _send_message(self, message: dict[str, Any]) -> None:
        """Send message to WebSocket.

        Args:
            message: Message to send

        Raises:
            WSConnectionError: If not connected or send fails
        """
        if not self.is_connected or not self._websocket:
            raise WSConnectionError("Not connected to WebSocket")

        try:
            await self._websocket.send(json.dumps(message))
            logger.debug("message_sent", message=message)
        except Exception as e:
            logger.error("message_send_failed", error=str(e))
            raise WSConnectionError(f"Failed to send message: {e}") from e
