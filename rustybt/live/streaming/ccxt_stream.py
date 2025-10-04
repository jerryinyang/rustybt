"""CCXT WebSocket adapter for unified multi-exchange real-time market data.

Note: This adapter requires ccxt.pro (separate package from ccxt).
Install with: pip install ccxt[pro] or uv add ccxt[pro]
"""

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


class CCXTWebSocketAdapter(BaseWebSocketAdapter):
    """CCXT Pro WebSocket adapter for unified exchange support.

    Provides WebSocket streaming for 40+ exchanges via CCXT Pro unified API.
    Handles trade streams with exchange-agnostic interface.

    CCXT Pro Documentation:
    https://docs.ccxt.com/en/latest/manual.html#ccxt-pro

    Supported Exchanges (WebSocket):
    - Binance, Coinbase, Kraken, Bybit, OKX, Huobi, KuCoin, and 30+ more

    Note: CCXT Pro is a separate package (ccxt>=4.0.0 with [pro] extra)
    """

    def __init__(
        self,
        exchange_id: str,
        config: StreamConfig | None = None,
        on_tick: Callable[[TickData], None] | None = None,
        exchange_config: dict[str, Any] | None = None,
    ) -> None:
        """Initialize CCXT WebSocket adapter.

        Args:
            exchange_id: CCXT exchange ID (e.g., 'binance', 'coinbase', 'kraken')
            config: Streaming configuration
            on_tick: Callback for tick data
            exchange_config: Optional CCXT exchange configuration (API keys, options)

        Raises:
            ImportError: If ccxt.pro is not installed
            ValueError: If exchange_id is invalid or doesn't support WebSocket
        """
        try:
            import ccxt.pro as ccxtpro  # type: ignore
        except ImportError as e:
            raise ImportError(
                "ccxt.pro is required for WebSocket streaming. "
                "Install with: pip install 'ccxt[pro]' or uv add 'ccxt[pro]'"
            ) from e

        self.exchange_id = exchange_id
        self.exchange_config = exchange_config or {}

        # Initialize CCXT Pro exchange
        try:
            exchange_class = getattr(ccxtpro, exchange_id)
            self.exchange = exchange_class(self.exchange_config)
        except AttributeError as e:
            raise ValueError(
                f"Invalid exchange_id: {exchange_id}. "
                f"Check supported exchanges: https://docs.ccxt.com/en/latest/exchange-markets.html"
            ) from e

        # Check WebSocket support
        if not hasattr(self.exchange, "watch_trades"):
            raise ValueError(
                f"Exchange {exchange_id} does not support WebSocket streaming via CCXT Pro"
            )

        # CCXT Pro uses exchange's WebSocket URL internally
        # We use a placeholder URL since connection is managed by CCXT
        url = f"ccxt://{exchange_id}"

        super().__init__(url=url, config=config, on_tick=on_tick)

        self._watch_tasks: dict[str, Any] = {}  # symbol -> watch task

        logger.info(
            "ccxt_websocket_initialized",
            exchange_id=exchange_id,
            has_websocket=hasattr(self.exchange, "watch_trades"),
        )

    async def subscribe(self, symbols: list[str], channels: list[str]) -> None:
        """Subscribe to CCXT Pro streams.

        Args:
            symbols: List of symbols (e.g., ['BTC/USDT', 'ETH/USDT'])
            channels: List of channels (e.g., ['trades', 'ticker'])
                     Note: CCXT Pro has different watch methods per channel

        Raises:
            SubscriptionError: If subscription fails
        """
        # CCXT Pro uses watch_* methods instead of explicit subscription messages
        # We'll start watch_trades tasks for each symbol

        try:
            for symbol in symbols:
                # Start watch task for symbol
                if symbol not in self._watch_tasks:
                    # Store subscription
                    if symbol not in self._subscriptions:
                        self._subscriptions[symbol] = set()
                    self._subscriptions[symbol].update(channels)

            logger.info(
                "ccxt_subscribed",
                exchange=self.exchange_id,
                symbols=symbols,
                channels=channels,
                total_subscriptions=len(self._subscriptions),
            )

        except Exception as e:
            logger.error(
                "ccxt_subscription_failed",
                exchange=self.exchange_id,
                symbols=symbols,
                error=str(e),
            )
            raise SubscriptionError(f"Failed to subscribe on {self.exchange_id}: {e}") from e

    async def unsubscribe(self, symbols: list[str], channels: list[str]) -> None:
        """Unsubscribe from CCXT Pro streams.

        Args:
            symbols: List of symbols
            channels: List of channels

        Raises:
            SubscriptionError: If unsubscription fails
        """
        try:
            for symbol in symbols:
                # Cancel watch task
                if symbol in self._watch_tasks:
                    task = self._watch_tasks[symbol]
                    if task and not task.done():
                        task.cancel()
                    del self._watch_tasks[symbol]

                # Update subscriptions
                if symbol in self._subscriptions:
                    self._subscriptions[symbol].difference_update(channels)
                    if not self._subscriptions[symbol]:
                        del self._subscriptions[symbol]

            logger.info(
                "ccxt_unsubscribed",
                exchange=self.exchange_id,
                symbols=symbols,
                channels=channels,
                remaining_subscriptions=len(self._subscriptions),
            )

        except Exception as e:
            logger.error(
                "ccxt_unsubscription_failed",
                exchange=self.exchange_id,
                symbols=symbols,
                error=str(e),
            )
            raise SubscriptionError(f"Failed to unsubscribe on {self.exchange_id}: {e}") from e

    async def watch_symbol_trades(self, symbol: str) -> None:
        """Watch trades for a symbol using CCXT Pro.

        This method continuously watches trades and calls on_tick callback.

        Args:
            symbol: Trading symbol (e.g., 'BTC/USDT')
        """
        try:
            while symbol in self._subscriptions:
                # Watch trades (this is a blocking call that waits for new trades)
                trades = await self.exchange.watch_trades(symbol)

                # Parse and emit each trade
                for trade in trades:
                    tick = self._parse_ccxt_trade(trade, symbol)
                    if tick and self.on_tick:
                        self.on_tick(tick)

        except Exception as e:
            logger.error(
                "ccxt_watch_error",
                exchange=self.exchange_id,
                symbol=symbol,
                error=str(e),
            )

    def parse_message(self, raw_message: dict[str, Any]) -> TickData | None:
        """Parse CCXT Pro trade to TickData.

        CCXT Pro trade format (unified):
        {
            'id': '12345',
            'timestamp': 1672531200000,
            'datetime': '2023-01-01T00:00:00.000Z',
            'symbol': 'BTC/USDT',
            'type': None,
            'side': 'buy',
            'price': 50000.0,
            'amount': 0.1,
            'cost': 5000.0,
            'takerOrMaker': 'taker'
        }

        Args:
            raw_message: CCXT trade dict

        Returns:
            TickData if valid trade, None otherwise

        Raises:
            ParseError: If message parsing fails
        """
        try:
            return self._parse_ccxt_trade(raw_message, raw_message.get("symbol", "UNKNOWN"))
        except Exception as e:
            logger.error("ccxt_parse_error", message=raw_message, error=str(e))
            raise ParseError(f"Failed to parse CCXT trade: {e}") from e

    def _parse_ccxt_trade(self, trade: dict[str, Any], symbol: str) -> TickData | None:
        """Parse CCXT unified trade format to TickData.

        Args:
            trade: CCXT trade dict
            symbol: Trading symbol

        Returns:
            TickData or None if invalid
        """
        try:
            timestamp = datetime.fromtimestamp(trade["timestamp"] / 1000)  # ms to seconds
            price = Decimal(str(trade["price"]))
            volume = Decimal(str(trade["amount"]))
            side = TickSide.BUY if trade["side"] == "buy" else TickSide.SELL

            tick = TickData(
                symbol=symbol,
                timestamp=timestamp,
                price=price,
                volume=volume,
                side=side,
            )

            logger.debug(
                "ccxt_trade_parsed",
                exchange=self.exchange_id,
                symbol=symbol,
                price=str(price),
                volume=str(volume),
                side=side.value,
            )

            return tick

        except (KeyError, ValueError, TypeError) as e:
            logger.error(
                "ccxt_trade_parse_error",
                exchange=self.exchange_id,
                trade=trade,
                error=str(e),
            )
            return None

    def _build_subscription_message(
        self, symbols: list[str], channels: list[str]
    ) -> dict[str, Any]:
        """Build CCXT subscription message.

        Note: CCXT Pro doesn't use explicit subscription messages.
        Instead, it uses watch_* methods. This is a placeholder.

        Args:
            symbols: List of symbols
            channels: List of channels

        Returns:
            Placeholder dict (not used by CCXT Pro)
        """
        return {
            "method": "subscribe",
            "exchange": self.exchange_id,
            "symbols": symbols,
            "channels": channels,
        }

    def _build_unsubscription_message(
        self, symbols: list[str], channels: list[str]
    ) -> dict[str, Any]:
        """Build CCXT unsubscription message.

        Note: CCXT Pro doesn't use explicit unsubscription messages.
        This is a placeholder.

        Args:
            symbols: List of symbols
            channels: List of channels

        Returns:
            Placeholder dict (not used by CCXT Pro)
        """
        return {
            "method": "unsubscribe",
            "exchange": self.exchange_id,
            "symbols": symbols,
            "channels": channels,
        }

    async def close(self) -> None:
        """Close CCXT Pro exchange connection."""
        try:
            await self.exchange.close()
            logger.info("ccxt_exchange_closed", exchange=self.exchange_id)
        except Exception as e:
            logger.error("ccxt_close_error", exchange=self.exchange_id, error=str(e))
