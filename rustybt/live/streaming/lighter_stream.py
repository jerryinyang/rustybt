"""Lighter.xyz WebSocket adapter for real-time market data streaming.

This module provides real-time market data streaming from Lighter DEX
via WebSocket connection, supporting trade updates and order book data.
"""

import asyncio
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import structlog

from rustybt.live.streaming.bar_buffer import BarBuffer, OHLCVBar
from rustybt.live.streaming.base import (
    BaseWebSocketAdapter,
    ParseError,
    SubscriptionError,
)
from rustybt.live.streaming.models import StreamConfig, TickData, TickSide

logger = structlog.get_logger(__name__)


class LighterStreamConfig(StreamConfig):
    """Extended configuration for Lighter streaming.

    Extends StreamConfig with Lighter-specific options.

    Attributes:
        max_symbols_per_subscription: Max symbols per subscription message
        enable_trade_stream: Enable trade stream subscription
        enable_orderbook_stream: Enable orderbook stream subscription
    """

    max_symbols_per_subscription: int = 50
    enable_trade_stream: bool = True
    enable_orderbook_stream: bool = False

    def __init__(
        self,
        bar_resolution: int = 60,
        heartbeat_interval: int = 30,
        heartbeat_timeout: int = 60,
        reconnect_attempts: int | None = None,
        reconnect_delay: int = 1,
        reconnect_max_delay: int = 16,
        circuit_breaker_threshold: int = 10,
        max_symbols_per_subscription: int = 50,
        enable_trade_stream: bool = True,
        enable_orderbook_stream: bool = False,
    ) -> None:
        """Initialize Lighter stream configuration."""
        super().__init__(
            bar_resolution=bar_resolution,
            heartbeat_interval=heartbeat_interval,
            heartbeat_timeout=heartbeat_timeout,
            reconnect_attempts=reconnect_attempts,
            reconnect_delay=reconnect_delay,
            reconnect_max_delay=reconnect_max_delay,
            circuit_breaker_threshold=circuit_breaker_threshold,
        )
        self.max_symbols_per_subscription = max_symbols_per_subscription
        self.enable_trade_stream = enable_trade_stream
        self.enable_orderbook_stream = enable_orderbook_stream


class LighterWebSocketAdapter(BaseWebSocketAdapter):
    """Lighter.xyz WebSocket adapter for real-time market data.

    Supports perpetual futures markets via Lighter WebSocket API.
    Handles trade streams, order book updates, and candlestick aggregation.

    Features:
        - Multi-symbol subscription with channel filtering
        - Real-time tick data conversion
        - Bar aggregation from tick stream
        - Automatic reconnection with subscription recovery
        - Connection health monitoring

    Example:
        >>> adapter = LighterWebSocketAdapter(testnet=True)
        >>> await adapter.connect()
        >>> await adapter.subscribe(["BTC-PERP", "ETH-PERP"], ["trades"])
        >>> # Ticks received via on_tick callback
    """

    # WebSocket URLs
    MAINNET_URL = "wss://mainnet.zklighter.elliot.ai/ws"
    TESTNET_URL = "wss://testnet.zklighter.elliot.ai/ws"

    def __init__(
        self,
        testnet: bool = True,
        config: LighterStreamConfig | StreamConfig | None = None,
        on_tick: Callable[[TickData], None] | None = None,
        on_bar: Callable[[OHLCVBar], None] | None = None,
    ) -> None:
        """Initialize Lighter WebSocket adapter.

        Args:
            testnet: Use testnet WebSocket (default True, per ADR-003)
            config: Streaming configuration
            on_tick: Callback for tick data
            on_bar: Callback for completed bars
        """
        self.testnet = testnet
        url = self.TESTNET_URL if testnet else self.MAINNET_URL

        # Use LighterStreamConfig if standard StreamConfig provided
        if config and not isinstance(config, LighterStreamConfig):
            config = LighterStreamConfig(
                bar_resolution=config.bar_resolution,
                heartbeat_interval=config.heartbeat_interval,
                heartbeat_timeout=config.heartbeat_timeout,
                reconnect_attempts=config.reconnect_attempts,
                reconnect_delay=config.reconnect_delay,
                reconnect_max_delay=config.reconnect_max_delay,
                circuit_breaker_threshold=config.circuit_breaker_threshold,
            )

        super().__init__(url=url, config=config or LighterStreamConfig(), on_tick=on_tick)

        self.on_bar = on_bar

        # Bar buffer for tick-to-bar aggregation
        self._bar_buffer: BarBuffer | None = None
        if self.config and self.config.bar_resolution:
            self._bar_buffer = BarBuffer(
                bar_resolution=self.config.bar_resolution,
                on_bar_complete=self._handle_bar_complete,
            )

        # Message buffer for reconnection
        self._message_buffer: list[dict] = []
        self._buffer_max_size: int = 1000
        self._buffering_enabled: bool = False

        # Pending subscriptions during reconnection
        self._pending_subscriptions: dict[str, set[str]] = defaultdict(set)

        # Track subscription confirmations
        self._subscription_confirmed: dict[str, bool] = {}

        logger.info(
            "lighter_websocket_initialized",
            testnet=testnet,
            url=url,
            bar_resolution=self.config.bar_resolution if self.config else None,
        )

    async def subscribe(self, symbols: list[str], channels: list[str]) -> None:
        """Subscribe to Lighter.xyz streams.

        Args:
            symbols: List of symbols (e.g., ["BTC-PERP", "ETH-PERP"])
            channels: List of channels (e.g., ["trades", "orderbook"])

        Raises:
            SubscriptionError: If subscription fails
        """
        if not self.is_connected:
            raise SubscriptionError("Not connected to WebSocket")

        # Build subscription messages (may need to batch for large symbol lists)
        for symbol in symbols:
            for channel in channels:
                message = self._build_subscription_message([symbol], [channel])

                try:
                    await self._send_message(message)

                    # Update subscriptions tracking
                    if symbol not in self._subscriptions:
                        self._subscriptions[symbol] = set()
                    self._subscriptions[symbol].add(channel)

                    logger.debug(
                        "lighter_subscribed",
                        symbol=symbol,
                        channel=channel,
                    )

                except Exception as e:
                    logger.error(
                        "lighter_subscription_failed",
                        symbol=symbol,
                        channel=channel,
                        error=str(e),
                    )
                    raise SubscriptionError(
                        f"Failed to subscribe to {symbol}:{channel}: {e}"
                    ) from e

        logger.info(
            "lighter_subscriptions_complete",
            symbols=symbols,
            channels=channels,
            total_subscriptions=len(self._subscriptions),
        )

    async def unsubscribe(self, symbols: list[str], channels: list[str]) -> None:
        """Unsubscribe from Lighter.xyz streams.

        Args:
            symbols: List of symbols
            channels: List of channels

        Raises:
            SubscriptionError: If unsubscription fails
        """
        if not self.is_connected:
            raise SubscriptionError("Not connected to WebSocket")

        for symbol in symbols:
            for channel in channels:
                message = self._build_unsubscription_message([symbol], [channel])

                try:
                    await self._send_message(message)

                    # Update subscriptions tracking
                    if symbol in self._subscriptions:
                        self._subscriptions[symbol].discard(channel)
                        if not self._subscriptions[symbol]:
                            del self._subscriptions[symbol]

                    logger.debug(
                        "lighter_unsubscribed",
                        symbol=symbol,
                        channel=channel,
                    )

                except Exception as e:
                    logger.error(
                        "lighter_unsubscription_failed",
                        symbol=symbol,
                        channel=channel,
                        error=str(e),
                    )
                    raise SubscriptionError(
                        f"Failed to unsubscribe from {symbol}:{channel}: {e}"
                    ) from e

        logger.info(
            "lighter_unsubscriptions_complete",
            symbols=symbols,
            channels=channels,
            remaining_subscriptions=len(self._subscriptions),
        )

    def parse_message(self, raw_message: dict[str, Any]) -> TickData | None:
        """Parse Lighter WebSocket message to TickData.

        Lighter WebSocket message formats:

        Trade stream:
        {
            "type": "trade",
            "data": {
                "symbol": "BTC-PERP",
                "price": "42000.50",
                "size": "0.1",
                "side": "buy",
                "timestamp": 1704067200000
            }
        }

        Subscription confirmation:
        {
            "type": "subscribed",
            "channel": "trades",
            "symbol": "BTC-PERP"
        }

        Args:
            raw_message: Raw WebSocket message

        Returns:
            TickData if message is a trade, None otherwise

        Raises:
            ParseError: If message parsing fails critically
        """
        try:
            msg_type = raw_message.get("type", raw_message.get("channel", ""))

            # Handle subscription confirmation
            if msg_type == "subscribed":
                symbol = raw_message.get("symbol", "")
                channel = raw_message.get("channel", "")
                logger.debug(
                    "lighter_subscription_confirmed",
                    symbol=symbol,
                    channel=channel,
                )
                self._subscription_confirmed[f"{symbol}:{channel}"] = True
                return None

            # Handle pong/heartbeat
            if msg_type in ("pong", "heartbeat"):
                logger.debug("lighter_heartbeat_received")
                return None

            # Handle error messages
            if msg_type == "error":
                error_msg = raw_message.get("message", raw_message.get("error", "Unknown error"))
                logger.warning("lighter_error_message", error=error_msg)
                return None

            # Handle trade messages
            if msg_type == "trade" or msg_type == "trades":
                return self._parse_trade_message(raw_message)

            # Handle candle/kline messages (direct bar updates)
            if msg_type in ("candle", "kline", "candlestick"):
                return self._parse_candle_message(raw_message)

            # Unknown message type - log and ignore
            logger.debug(
                "lighter_unknown_message_type",
                type=msg_type,
                keys=list(raw_message.keys()),
            )
            return None

        except (KeyError, ValueError, TypeError) as e:
            logger.error(
                "lighter_parse_error",
                message=str(raw_message)[:200],
                error=str(e),
            )
            raise ParseError(f"Failed to parse Lighter message: {e}") from e

    def _parse_trade_message(self, raw_message: dict[str, Any]) -> TickData | None:
        """Parse trade message to TickData.

        Args:
            raw_message: Trade message from WebSocket

        Returns:
            TickData or None
        """
        data = raw_message.get("data", raw_message)

        # Extract fields (handle various field names)
        symbol = data.get("symbol") or data.get("market") or data.get("order_book", "")
        price_str = data.get("price") or data.get("px") or data.get("p")
        size_str = data.get("size") or data.get("sz") or data.get("quantity") or data.get("q")
        side_str = data.get("side") or data.get("s", "unknown")
        timestamp_raw = data.get("timestamp") or data.get("time") or data.get("ts") or data.get("t")

        if not all([symbol, price_str, size_str]):
            logger.debug("lighter_incomplete_trade", data=data)
            return None

        # Parse timestamp (convert to naive UTC for bar buffer compatibility)
        if isinstance(timestamp_raw, (int, float)):
            # Assume milliseconds if large
            if timestamp_raw > 1e12:
                timestamp = datetime.utcfromtimestamp(timestamp_raw / 1000)
            else:
                timestamp = datetime.utcfromtimestamp(timestamp_raw)
        elif isinstance(timestamp_raw, str):
            ts = datetime.fromisoformat(timestamp_raw.replace("Z", "+00:00"))
            # Convert to naive UTC
            timestamp = ts.replace(tzinfo=None) if ts.tzinfo else ts
        else:
            timestamp = datetime.utcnow()

        # Parse side
        side_lower = str(side_str).lower()
        if side_lower in ("buy", "b", "bid", "long"):
            side = TickSide.BUY
        elif side_lower in ("sell", "s", "ask", "short"):
            side = TickSide.SELL
        else:
            side = TickSide.UNKNOWN

        # Create tick
        tick = TickData(
            symbol=symbol,
            timestamp=timestamp,
            price=Decimal(str(price_str)),
            volume=Decimal(str(size_str)),
            side=side,
        )

        logger.debug(
            "lighter_trade_parsed",
            symbol=symbol,
            price=str(tick.price),
            volume=str(tick.volume),
            side=side.value,
        )

        # Process through bar buffer if enabled
        if self._bar_buffer:
            completed_bar = self._bar_buffer.add_tick(tick)
            if completed_bar:
                logger.debug(
                    "bar_completed_from_tick",
                    symbol=completed_bar.symbol,
                    timestamp=completed_bar.timestamp.isoformat(),
                )

        return tick

    def _parse_candle_message(self, raw_message: dict[str, Any]) -> TickData | None:
        """Parse candle/kline message.

        For candle updates, we emit the close price as a tick to maintain
        consistency with trade-based bar aggregation.

        Args:
            raw_message: Candle message from WebSocket

        Returns:
            TickData with candle close price or None
        """
        data = raw_message.get("data", raw_message)

        symbol = data.get("symbol") or data.get("market", "")
        close_str = data.get("close") or data.get("c")
        volume_str = data.get("volume") or data.get("v", "0")
        timestamp_raw = data.get("timestamp") or data.get("time") or data.get("t")

        if not all([symbol, close_str]):
            return None

        # Parse timestamp (naive UTC for compatibility)
        if isinstance(timestamp_raw, (int, float)):
            if timestamp_raw > 1e12:
                timestamp = datetime.utcfromtimestamp(timestamp_raw / 1000)
            else:
                timestamp = datetime.utcfromtimestamp(timestamp_raw)
        else:
            timestamp = datetime.utcnow()

        return TickData(
            symbol=symbol,
            timestamp=timestamp,
            price=Decimal(str(close_str)),
            volume=Decimal(str(volume_str)),
            side=TickSide.UNKNOWN,
        )

    def _build_subscription_message(
        self, symbols: list[str], channels: list[str]
    ) -> dict[str, Any]:
        """Build Lighter subscription message.

        Lighter WebSocket subscription format:
        {
            "method": "subscribe",
            "params": {
                "channel": "trades",
                "symbol": "BTC-PERP"
            }
        }

        Args:
            symbols: List of symbols
            channels: List of channels

        Returns:
            Subscription message dict
        """
        # Lighter subscribes one symbol/channel at a time
        symbol = symbols[0] if symbols else "BTC-PERP"
        channel = channels[0] if channels else "trades"

        return {
            "method": "subscribe",
            "params": {
                "channel": channel,
                "symbol": symbol,
            },
        }

    def _build_unsubscription_message(
        self, symbols: list[str], channels: list[str]
    ) -> dict[str, Any]:
        """Build Lighter unsubscription message.

        Args:
            symbols: List of symbols
            channels: List of channels

        Returns:
            Unsubscription message dict
        """
        symbol = symbols[0] if symbols else "BTC-PERP"
        channel = channels[0] if channels else "trades"

        return {
            "method": "unsubscribe",
            "params": {
                "channel": channel,
                "symbol": symbol,
            },
        }

    def _handle_bar_complete(self, bar: OHLCVBar) -> None:
        """Handle completed bar from buffer.

        Args:
            bar: Completed OHLCV bar
        """
        if self.on_bar:
            self.on_bar(bar)

        logger.debug(
            "lighter_bar_complete",
            symbol=bar.symbol,
            timestamp=bar.timestamp.isoformat(),
            open=str(bar.open),
            high=str(bar.high),
            low=str(bar.low),
            close=str(bar.close),
            volume=str(bar.volume),
        )

    # =========================================================================
    # Buffering for Reconnection (Story 10.5.6)
    # =========================================================================

    def enable_buffering(self) -> None:
        """Enable message buffering during reconnection."""
        self._buffering_enabled = True
        self._message_buffer.clear()
        logger.info("buffering_enabled")

    def disable_buffering(self) -> None:
        """Disable message buffering and clear buffer."""
        self._buffering_enabled = False
        self._message_buffer.clear()
        logger.info("buffering_disabled")

    def get_buffered_messages(self) -> list[dict]:
        """Get buffered messages.

        Returns:
            Copy of buffered messages
        """
        return self._message_buffer.copy()

    async def replay_buffer(self) -> None:
        """Replay buffered messages after reconnection."""
        if not self._message_buffer:
            logger.debug("no_buffered_messages_to_replay")
            return

        logger.info("replaying_buffered_messages", count=len(self._message_buffer))

        for msg in self._message_buffer:
            try:
                tick = self.parse_message(msg)
                if tick and self.on_tick:
                    self.on_tick(tick)
            except ParseError as e:
                logger.warning("buffer_replay_parse_error", error=str(e))

        self._message_buffer.clear()

    async def reconnect(self) -> None:
        """Reconnect with buffering support.

        Overrides base reconnect to enable buffering during reconnection.
        """
        # Enable buffering during reconnection
        self.enable_buffering()

        try:
            await super().reconnect()
        finally:
            # Replay buffer after reconnection
            if self.is_connected:
                await self.replay_buffer()
            self.disable_buffering()

    # =========================================================================
    # Multi-Channel Subscription (Story 10.5.5)
    # =========================================================================

    async def subscribe_all_channels(self, symbols: list[str]) -> None:
        """Subscribe to all available channels for symbols.

        Args:
            symbols: List of symbols to subscribe

        Raises:
            SubscriptionError: If subscription fails
        """
        channels = ["trades"]

        # Add orderbook if enabled in config
        if isinstance(self.config, LighterStreamConfig) and self.config.enable_orderbook_stream:
            channels.append("orderbook")

        await self.subscribe(symbols, channels)

    def flush_bars(self) -> dict[str, OHLCVBar]:
        """Flush all incomplete bars from buffer.

        Returns:
            Dict of symbol -> incomplete bar
        """
        if not self._bar_buffer:
            return {}
        return self._bar_buffer.flush_all()

    def get_bar_buffer_state(self) -> dict[str, dict]:
        """Get current state of bar buffer for monitoring.

        Returns:
            Dict with buffer state information
        """
        if not self._bar_buffer:
            return {"enabled": False}

        return {
            "enabled": True,
            "bar_resolution": self._bar_buffer.bar_resolution,
            "symbols_buffering": list(self._bar_buffer._current_bars.keys()),
        }

    # =========================================================================
    # Context Manager Support
    # =========================================================================

    async def __aenter__(self) -> "LighterWebSocketAdapter":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()
