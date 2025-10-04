"""Binance WebSocket adapter for real-time market data."""

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


class BinanceWebSocketAdapter(BaseWebSocketAdapter):
    """Binance WebSocket adapter.

    Supports both spot and futures markets via Binance WebSocket API.
    Handles kline (candlestick) and trade streams.
    """

    # Binance WebSocket URLs
    SPOT_URL = "wss://stream.binance.com:9443/ws"
    FUTURES_URL = "wss://fstream.binance.com/ws"

    def __init__(
        self,
        market_type: str = "spot",
        config: StreamConfig | None = None,
        on_tick: Callable[[TickData], None] | None = None,
    ) -> None:
        """Initialize Binance WebSocket adapter.

        Args:
            market_type: Market type ('spot' or 'futures')
            config: Streaming configuration
            on_tick: Callback for tick data

        Raises:
            ValueError: If market_type is invalid
        """
        if market_type not in ("spot", "futures"):
            raise ValueError(f"Invalid market_type: {market_type}, must be 'spot' or 'futures'")

        self.market_type = market_type
        url = self.SPOT_URL if market_type == "spot" else self.FUTURES_URL

        super().__init__(url=url, config=config, on_tick=on_tick)

    async def subscribe(self, symbols: list[str], channels: list[str]) -> None:
        """Subscribe to Binance streams.

        Args:
            symbols: List of symbols (e.g., ['BTCUSDT', 'ETHUSDT'])
            channels: List of channels (e.g., ['kline_1m', 'trade', 'ticker'])

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
                "subscribed",
                symbols=symbols,
                channels=channels,
                market_type=self.market_type,
            )

        except Exception as e:
            logger.error("subscription_failed", symbols=symbols, channels=channels, error=str(e))
            raise SubscriptionError(f"Failed to subscribe: {e}") from e

    async def unsubscribe(self, symbols: list[str], channels: list[str]) -> None:
        """Unsubscribe from Binance streams.

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
                "unsubscribed",
                symbols=symbols,
                channels=channels,
                market_type=self.market_type,
            )

        except Exception as e:
            logger.error("unsubscription_failed", symbols=symbols, channels=channels, error=str(e))
            raise SubscriptionError(f"Failed to unsubscribe: {e}") from e

    def parse_message(self, raw_message: dict[str, Any]) -> TickData | None:
        """Parse Binance WebSocket message to TickData.

        Supports kline and trade messages.

        Args:
            raw_message: Raw message from Binance WebSocket

        Returns:
            TickData if message parsed successfully, None for non-data messages

        Raises:
            ParseError: If message parsing fails critically
        """
        # Check for subscription confirmation
        if "result" in raw_message:
            logger.debug("subscription_confirmation", result=raw_message["result"])
            return None

        # Check for error
        if "error" in raw_message:
            error_msg = raw_message.get("error", {}).get("msg", "Unknown error")
            logger.error("binance_error", error=error_msg)
            raise ParseError(f"Binance error: {error_msg}")

        # Get event type
        event_type = raw_message.get("e")

        if event_type == "kline":
            return self._parse_kline_message(raw_message)
        elif event_type == "trade":
            return self._parse_trade_message(raw_message)
        else:
            # Unknown event type, log and skip
            logger.debug("unknown_event_type", event_type=event_type)
            return None

    def _parse_kline_message(self, message: dict[str, Any]) -> TickData | None:
        """Parse Binance kline message.

        Args:
            message: Kline message

        Returns:
            TickData from kline close price

        Raises:
            ParseError: If parsing fails
        """
        try:
            kline = message["k"]
            symbol = kline["s"]
            timestamp = datetime.fromtimestamp(kline["T"] / 1000.0)  # Close time
            close_price = Decimal(kline["c"])
            volume = Decimal(kline["v"])

            # Use close price as tick price
            tick = TickData(
                symbol=symbol,
                timestamp=timestamp,
                price=close_price,
                volume=volume,
                side=TickSide.UNKNOWN,  # Kline doesn't have side
            )

            logger.debug(
                "kline_parsed",
                symbol=symbol,
                timestamp=timestamp.isoformat(),
                price=str(close_price),
            )

            return tick

        except (KeyError, ValueError) as e:
            logger.warning("kline_parse_error", error=str(e), message=str(message)[:200])
            raise ParseError(f"Failed to parse kline message: {e}") from e

    def _parse_trade_message(self, message: dict[str, Any]) -> TickData:
        """Parse Binance trade message.

        Args:
            message: Trade message

        Returns:
            TickData from trade

        Raises:
            ParseError: If parsing fails
        """
        try:
            symbol = message["s"]
            timestamp = datetime.fromtimestamp(message["T"] / 1000.0)
            price = Decimal(message["p"])
            quantity = Decimal(message["q"])
            is_buyer_maker = message["m"]

            # Determine side (if buyer is maker, trade is sell)
            side = TickSide.SELL if is_buyer_maker else TickSide.BUY

            tick = TickData(
                symbol=symbol,
                timestamp=timestamp,
                price=price,
                volume=quantity,
                side=side,
            )

            logger.debug(
                "trade_parsed",
                symbol=symbol,
                timestamp=timestamp.isoformat(),
                price=str(price),
                side=side.value,
            )

            return tick

        except (KeyError, ValueError) as e:
            logger.warning("trade_parse_error", error=str(e), message=str(message)[:200])
            raise ParseError(f"Failed to parse trade message: {e}") from e

    def _build_subscription_message(
        self, symbols: list[str], channels: list[str]
    ) -> dict[str, Any]:
        """Build Binance subscription message.

        Args:
            symbols: List of symbols
            channels: List of channels

        Returns:
            Subscription message
        """
        # Build stream names (e.g., 'btcusdt@kline_1m', 'ethusdt@trade')
        streams = []
        for symbol in symbols:
            symbol_lower = symbol.lower()
            for channel in channels:
                streams.append(f"{symbol_lower}@{channel}")

        # Binance subscription format
        message = {
            "method": "SUBSCRIBE",
            "params": streams,
            "id": 1,
        }

        return message

    def _build_unsubscription_message(
        self, symbols: list[str], channels: list[str]
    ) -> dict[str, Any]:
        """Build Binance unsubscription message.

        Args:
            symbols: List of symbols
            channels: List of channels

        Returns:
            Unsubscription message
        """
        # Build stream names
        streams = []
        for symbol in symbols:
            symbol_lower = symbol.lower()
            for channel in channels:
                streams.append(f"{symbol_lower}@{channel}")

        # Binance unsubscription format
        message = {
            "method": "UNSUBSCRIBE",
            "params": streams,
            "id": 1,
        }

        return message
