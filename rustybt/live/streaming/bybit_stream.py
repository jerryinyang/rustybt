"""Bybit WebSocket adapter for real-time market data."""

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


class BybitWebSocketAdapter(BaseWebSocketAdapter):
    """Bybit WebSocket adapter.

    Supports spot, linear perpetual, and inverse perpetual markets
    via Bybit WebSocket API v5. Handles kline and trade streams.

    Bybit WebSocket API Documentation:
    https://bybit-exchange.github.io/docs/v5/websocket/connect
    """

    # Bybit WebSocket URLs (V5 API)
    MAINNET_URL = "wss://stream.bybit.com/v5/public/{category}"
    TESTNET_URL = "wss://stream-testnet.bybit.com/v5/public/{category}"

    def __init__(
        self,
        market_type: str = "linear",
        testnet: bool = False,
        config: StreamConfig | None = None,
        on_tick: Callable[[TickData], None] | None = None,
    ) -> None:
        """Initialize Bybit WebSocket adapter.

        Args:
            market_type: Market type ('spot', 'linear', 'inverse')
            testnet: Use testnet if True
            config: Streaming configuration
            on_tick: Callback for tick data

        Raises:
            ValueError: If market_type is invalid
        """
        if market_type not in ("spot", "linear", "inverse"):
            raise ValueError(
                f"Invalid market_type: {market_type}, must be 'spot', 'linear', or 'inverse'"
            )

        self.market_type = market_type
        self.testnet = testnet

        # Map market type to category
        category = market_type  # Bybit uses same naming
        base_url = self.TESTNET_URL if testnet else self.MAINNET_URL
        url = base_url.format(category=category)

        super().__init__(url=url, config=config, on_tick=on_tick)

        logger.info(
            "bybit_websocket_initialized",
            market_type=market_type,
            testnet=testnet,
            url=url,
        )

    async def subscribe(self, symbols: list[str], channels: list[str]) -> None:
        """Subscribe to Bybit streams.

        Args:
            symbols: List of symbols (e.g., ['BTCUSDT', 'ETHUSDT'])
            channels: List of channels (e.g., ['kline.1', 'publicTrade'])

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
                "bybit_subscribed",
                symbols=symbols,
                channels=channels,
                total_subscriptions=len(self._subscriptions),
            )

        except Exception as e:
            logger.error("bybit_subscription_failed", symbols=symbols, error=str(e))
            raise SubscriptionError(f"Failed to subscribe: {e}") from e

    async def unsubscribe(self, symbols: list[str], channels: list[str]) -> None:
        """Unsubscribe from Bybit streams.

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
                "bybit_unsubscribed",
                symbols=symbols,
                channels=channels,
                remaining_subscriptions=len(self._subscriptions),
            )

        except Exception as e:
            logger.error("bybit_unsubscription_failed", symbols=symbols, error=str(e))
            raise SubscriptionError(f"Failed to unsubscribe: {e}") from e

    def parse_message(self, raw_message: dict[str, Any]) -> TickData | None:
        """Parse Bybit WebSocket message to TickData.

        Bybit V5 WebSocket message format:
        {
            "topic": "publicTrade.BTCUSDT",
            "type": "snapshot",
            "ts": 1672304486868,
            "data": [{
                "i": "2290000000007764263",
                "T": 1672304486868,
                "p": "16578.50",
                "v": "0.006",
                "S": "Buy",
                "s": "BTCUSDT",
                "BT": false
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
            if "success" in raw_message:
                success = raw_message.get("success")
                if success:
                    logger.debug("bybit_subscription_confirmed", message=raw_message)
                else:
                    logger.warning("bybit_subscription_failed", message=raw_message)
                return None

            # Handle pong response (heartbeat)
            if raw_message.get("op") == "pong":
                logger.debug("bybit_pong_received")
                return None

            # Parse data message
            topic = raw_message.get("topic", "")
            data_list = raw_message.get("data", [])

            if not topic or not data_list:
                logger.debug("bybit_empty_message", message=raw_message)
                return None

            # Only handle trade messages for now
            if not topic.startswith("publicTrade."):
                logger.debug("bybit_non_trade_message", topic=topic)
                return None

            # Parse first trade in data list
            trade = data_list[0]
            symbol = trade["s"]
            timestamp = datetime.fromtimestamp(trade["T"] / 1000)  # ms to seconds
            price = Decimal(trade["p"])
            volume = Decimal(trade["v"])
            side = TickSide.BUY if trade["S"] == "Buy" else TickSide.SELL

            tick = TickData(
                symbol=symbol,
                timestamp=timestamp,
                price=price,
                volume=volume,
                side=side,
            )

            logger.debug(
                "bybit_trade_parsed",
                symbol=symbol,
                price=str(price),
                volume=str(volume),
                side=side.value,
            )

            return tick

        except (KeyError, ValueError, TypeError) as e:
            logger.error("bybit_parse_error", message=raw_message, error=str(e))
            raise ParseError(f"Failed to parse Bybit message: {e}") from e

    def _build_subscription_message(
        self, symbols: list[str], channels: list[str]
    ) -> dict[str, Any]:
        """Build Bybit subscription message.

        Bybit V5 format:
        {
            "op": "subscribe",
            "args": ["publicTrade.BTCUSDT", "kline.1.ETHUSDT"]
        }

        Args:
            symbols: List of symbols
            channels: List of channels

        Returns:
            Subscription message dict
        """
        # Build topic strings (channel.symbol format for most streams)
        args = []
        for symbol in symbols:
            for channel in channels:
                # kline channels need interval: kline.{interval}.{symbol}
                if channel.startswith("kline"):
                    # Extract interval from channel (e.g., 'kline.1' -> '1')
                    interval = channel.split(".")[-1] if "." in channel else "1"
                    args.append(f"kline.{interval}.{symbol}")
                else:
                    # Other channels: {channel}.{symbol}
                    args.append(f"{channel}.{symbol}")

        return {"op": "subscribe", "args": args}

    def _build_unsubscription_message(
        self, symbols: list[str], channels: list[str]
    ) -> dict[str, Any]:
        """Build Bybit unsubscription message.

        Args:
            symbols: List of symbols
            channels: List of channels

        Returns:
            Unsubscription message dict
        """
        # Build topic strings (same format as subscription)
        args = []
        for symbol in symbols:
            for channel in channels:
                if channel.startswith("kline"):
                    interval = channel.split(".")[-1] if "." in channel else "1"
                    args.append(f"kline.{interval}.{symbol}")
                else:
                    args.append(f"{channel}.{symbol}")

        return {"op": "unsubscribe", "args": args}
