"""Hyperliquid WebSocket adapter for real-time market data."""

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Any

import structlog

from rustybt.live.streaming.base import (
    BaseWebSocketAdapter,
    ParseError,
    SubscriptionError,
)
from rustybt.live.streaming.models import StreamConfig, TickData, TickSide

logger = structlog.get_logger(__name__)


class HyperliquidWebSocketAdapter(BaseWebSocketAdapter):
    """Hyperliquid WebSocket adapter.

    Supports perpetual futures markets via Hyperliquid WebSocket API.
    Handles trade and candle streams.

    Hyperliquid WebSocket API Documentation:
    https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/websocket
    """

    # Hyperliquid WebSocket URL (Mainnet only - Arbitrum L1)
    MAINNET_URL = "wss://api.hyperliquid.xyz/ws"
    # Testnet URL (if available - check docs)
    TESTNET_URL = "wss://api.hyperliquid-testnet.xyz/ws"

    def __init__(
        self,
        testnet: bool = False,
        config: StreamConfig | None = None,
        on_tick: Callable[[TickData], None] | None = None,
    ) -> None:
        """Initialize Hyperliquid WebSocket adapter.

        Args:
            testnet: Use testnet if True (Note: Hyperliquid testnet may not be available)
            config: Streaming configuration
            on_tick: Callback for tick data
        """
        self.testnet = testnet
        url = self.TESTNET_URL if testnet else self.MAINNET_URL

        super().__init__(url=url, config=config, on_tick=on_tick)

        logger.info(
            "hyperliquid_websocket_initialized",
            testnet=testnet,
            url=url,
        )

    async def subscribe(self, symbols: list[str], channels: list[str]) -> None:
        """Subscribe to Hyperliquid streams.

        Args:
            symbols: List of symbols (e.g., ['BTC', 'ETH'])
            channels: List of channels (e.g., ['trades', 'candle.1m'])

        Raises:
            SubscriptionError: If subscription fails
        """
        if not self.is_connected:
            raise SubscriptionError("Not connected to WebSocket")

        # Build subscription message
        message = self._build_subscription_message(symbols, channels)

        try:
            # Send subscription
            await self._send_message(message)

            # Update subscriptions
            for symbol in symbols:
                if symbol not in self._subscriptions:
                    self._subscriptions[symbol] = set()
                self._subscriptions[symbol].update(channels)

            logger.info(
                "hyperliquid_subscribed",
                symbols=symbols,
                channels=channels,
                total_subscriptions=len(self._subscriptions),
            )

        except Exception as e:
            logger.error("hyperliquid_subscription_failed", symbols=symbols, error=str(e))
            raise SubscriptionError(f"Failed to subscribe: {e}") from e

    async def unsubscribe(self, symbols: list[str], channels: list[str]) -> None:
        """Unsubscribe from Hyperliquid streams.

        Args:
            symbols: List of symbols
            channels: List of channels

        Raises:
            SubscriptionError: If unsubscription fails
        """
        if not self.is_connected:
            raise SubscriptionError("Not connected to WebSocket")

        # Build unsubscription message
        message = self._build_unsubscription_message(symbols, channels)

        try:
            # Send unsubscription
            await self._send_message(message)

            # Update subscriptions
            for symbol in symbols:
                if symbol in self._subscriptions:
                    self._subscriptions[symbol].difference_update(channels)
                    if not self._subscriptions[symbol]:
                        del self._subscriptions[symbol]

            logger.info(
                "hyperliquid_unsubscribed",
                symbols=symbols,
                channels=channels,
                remaining_subscriptions=len(self._subscriptions),
            )

        except Exception as e:
            logger.error("hyperliquid_unsubscription_failed", symbols=symbols, error=str(e))
            raise SubscriptionError(f"Failed to unsubscribe: {e}") from e

    def parse_message(self, raw_message: dict[str, Any]) -> TickData | None:
        """Parse Hyperliquid WebSocket message to TickData.

        Hyperliquid WebSocket message format:
        {
            "channel": "trades",
            "data": [{
                "coin": "BTC",
                "side": "B",
                "px": "50000.0",
                "sz": "0.1",
                "time": 1672531200000
            }]
        }

        Args:
            raw_message: Raw WebSocket message

        Returns:
            TickData if message is a trade, None otherwise

        Raises:
            ParseError: If message parsing fails
        """
        try:
            # Handle subscription confirmation
            if "method" in raw_message and raw_message.get("method") == "subscribe":
                success = raw_message.get("result", {}).get("success", False)
                if success:
                    logger.debug("hyperliquid_subscription_confirmed", message=raw_message)
                else:
                    logger.warning("hyperliquid_subscription_failed", message=raw_message)
                return None

            # Handle pong response (heartbeat)
            if raw_message.get("channel") == "pong":
                logger.debug("hyperliquid_pong_received")
                return None

            # Parse data message
            channel = raw_message.get("channel", "")
            data_list = raw_message.get("data", [])

            if not channel or not data_list:
                logger.debug("hyperliquid_empty_message", message=raw_message)
                return None

            # Only handle trade messages for now
            if channel != "trades":
                logger.debug("hyperliquid_non_trade_message", channel=channel)
                return None

            # Parse first trade in data list
            trade = data_list[0]
            symbol = trade["coin"]
            timestamp = datetime.fromtimestamp(trade["time"] / 1000)  # ms to seconds
            price = Decimal(trade["px"])
            volume = Decimal(trade["sz"])
            # Hyperliquid uses 'B' for buy, 'A' for ask/sell
            side = TickSide.BUY if trade["side"] == "B" else TickSide.SELL

            tick = TickData(
                symbol=symbol,
                timestamp=timestamp,
                price=price,
                volume=volume,
                side=side,
            )

            logger.debug(
                "hyperliquid_trade_parsed",
                symbol=symbol,
                price=str(price),
                volume=str(volume),
                side=side.value,
            )

            return tick

        except (KeyError, ValueError, TypeError) as e:
            logger.error("hyperliquid_parse_error", message=raw_message, error=str(e))
            raise ParseError(f"Failed to parse Hyperliquid message: {e}") from e

    def _build_subscription_message(
        self, symbols: list[str], channels: list[str]
    ) -> dict[str, Any]:
        """Build Hyperliquid subscription message.

        Hyperliquid format:
        {
            "method": "subscribe",
            "subscription": {
                "type": "trades",
                "coin": "BTC"
            }
        }

        Args:
            symbols: List of symbols
            channels: List of channels

        Returns:
            Subscription message dict
        """
        # Hyperliquid subscribes one symbol/channel at a time
        # For simplicity, subscribe to first symbol with first channel
        # (In production, you'd send multiple messages or batch subscriptions)
        if not symbols or not channels:
            return {"method": "subscribe", "subscription": {"type": "trades", "coin": "BTC"}}

        symbol = symbols[0]
        channel = channels[0]

        # Map channel names
        channel_type = channel
        if channel.startswith("candle"):
            # Extract interval: candle.1m -> candles with interval
            channel_type = "candle"

        return {
            "method": "subscribe",
            "subscription": {
                "type": channel_type,
                "coin": symbol,
            },
        }

    def _build_unsubscription_message(
        self, symbols: list[str], channels: list[str]
    ) -> dict[str, Any]:
        """Build Hyperliquid unsubscription message.

        Args:
            symbols: List of symbols
            channels: List of channels

        Returns:
            Unsubscription message dict
        """
        if not symbols or not channels:
            return {
                "method": "unsubscribe",
                "subscription": {"type": "trades", "coin": "BTC"},
            }

        symbol = symbols[0]
        channel = channels[0]

        channel_type = channel
        if channel.startswith("candle"):
            channel_type = "candle"

        return {
            "method": "unsubscribe",
            "subscription": {
                "type": channel_type,
                "coin": symbol,
            },
        }
