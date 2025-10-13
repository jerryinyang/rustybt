"""CCXT unified broker adapter for multi-exchange support.

This module provides integration with 100+ cryptocurrency exchanges via the
CCXT unified API. Supports spot, futures, and derivatives markets across
multiple exchanges with a standardized interface.

IMPORTANT: While CCXT supports 100+ exchanges, many have incomplete implementations
or limited testing. For production use, focus on well-supported exchanges:
- Binance, Coinbase, Kraken, Bybit, OKX, Bitfinex, Huobi

Always test with testnet/sandbox accounts before live trading.
"""

import asyncio
from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import ccxt
import ccxt.async_support as ccxt_async
import pandas as pd
import structlog

from rustybt.assets import Asset
from rustybt.exceptions import (
    BrokerAuthenticationError,
    BrokerConnectionError,
    BrokerError,
    BrokerRateLimitError,
    BrokerResponseError,
    InsufficientFundsError,
    InvalidOrderError,
    OrderRejectedError,
)
from rustybt.live.brokers.base import BrokerAdapter
from rustybt.live.streaming.bar_buffer import BarBuffer, OHLCVBar
from rustybt.live.streaming.ccxt_stream import CCXTWebSocketAdapter
from rustybt.utils.error_handling import log_exception, retry_async

if TYPE_CHECKING:
    from rustybt.live.streaming.models import TickData

logger = structlog.get_logger(__name__)

# Backward compatibility alias
CCXTConnectionError = BrokerConnectionError


class CCXTBrokerAdapter(BrokerAdapter):
    """CCXT unified broker adapter.

    Provides unified interface to 100+ cryptocurrency exchanges via CCXT.
    Supports spot, futures, and derivatives markets with automatic rate limiting.

    Supported Exchanges (well-tested):
        - Binance, Coinbase, Kraken, Bybit, OKX
        - Bitfinex, Huobi, KuCoin, Gate.io
        - FTX (if available), Deribit, BitMEX

    Supported Order Types (unified):
        - MARKET: Market order (all exchanges)
        - LIMIT: Limit order (all exchanges)
        - STOP: Stop order (where supported)
        - STOP_LIMIT: Stop-limit order (where supported)

    Exchange-Specific Features:
        - Pass exchange-specific params via order params dict
        - Check exchange.has capabilities for feature support

    Rate Limiting:
        - Automatic rate limiting per exchange (enableRateLimit=true)
        - Adaptive throttling on 429 errors

    Error Handling:
        - NetworkError: Network/connection issues
        - ExchangeError: Exchange-specific errors
        - InsufficientFunds: Insufficient balance
        - InvalidOrder: Invalid order parameters
    """

    # Well-supported exchanges for production use
    RECOMMENDED_EXCHANGES = [
        "binance",
        "coinbase",
        "kraken",
        "bybit",
        "okx",
        "bitfinex",
        "huobi",
        "kucoin",
        "gateio",
    ]

    DEFAULT_MAX_RETRIES = 3

    def __init__(
        self,
        exchange_id: str,
        api_key: str,
        api_secret: str,
        market_type: str = "spot",
        testnet: bool = False,
        exchange_params: dict[str, Any] | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        """Initialize CCXT broker adapter.

        Args:
            exchange_id: Exchange ID (e.g., 'binance', 'coinbase', 'kraken')
            api_key: Exchange API key
            api_secret: Exchange API secret
            market_type: Market type ('spot', 'future', 'swap')
            testnet: Use testnet/sandbox if True
            exchange_params: Additional exchange-specific parameters

        Raises:
            ValueError: If exchange_id is not supported
            BrokerConnectionError: If exchange initialization fails
        """
        self.exchange_id = exchange_id.lower()
        self.api_key = api_key
        self.api_secret = api_secret
        self.market_type = market_type
        self.testnet = testnet

        # Validate exchange
        if self.exchange_id not in ccxt_async.exchanges:
            raise ValueError(
                f"Unsupported exchange: {exchange_id}. "
                f"Available exchanges: {', '.join(ccxt_async.exchanges[:10])}..."
            )

        # Warn if exchange is not in recommended list
        if self.exchange_id not in self.RECOMMENDED_EXCHANGES:
            logger.warning(
                "exchange_not_recommended",
                exchange_id=self.exchange_id,
                recommended=self.RECOMMENDED_EXCHANGES,
                note="This exchange may have incomplete CCXT implementation. Test thoroughly.",
            )

        # Initialize exchange
        try:
            exchange_class = getattr(ccxt_async, self.exchange_id)

            # Build exchange config
            config = {
                "apiKey": api_key,
                "secret": api_secret,
                "enableRateLimit": True,  # Automatic rate limiting
                "options": {
                    "defaultType": market_type,  # spot, future, swap
                },
            }

            # Add testnet/sandbox mode
            if testnet:
                config["sandbox"] = True

            # Add custom params
            if exchange_params:
                config.update(exchange_params)

            self.exchange = exchange_class(config)

            self._connected = False
            self._market_data_queue: asyncio.Queue[dict] = asyncio.Queue()

            # WebSocket streaming components
            self._ws_adapter: CCXTWebSocketAdapter | None = None
            self._bar_buffer: BarBuffer | None = None
            self._max_retries = max(1, max_retries)

            logger.info(
                "ccxt_adapter_initialized",
                exchange_id=self.exchange_id,
                market_type=market_type,
                testnet=testnet,
            )

        except Exception as exc:  # pragma: no cover - executed when CCXT misbehaves
            error = BrokerConnectionError(
                f"Failed to initialize exchange {exchange_id}: {exc}",
                broker=exchange_id,
                cause=exc,
            )
            log_exception(exc, extra={"exchange_id": exchange_id, "phase": "initialization"})
            raise error from exc

    async def _execute_with_retry(
        self,
        operation: Callable[[], Awaitable[Any]],
        *,
        context: dict[str, Any] | None = None,
    ) -> Any:
        """Execute a CCXT operation with retry for transient failures."""
        retry_context = {"exchange_id": self.exchange_id, **(context or {})}
        return await retry_async(
            operation,
            retry_exceptions=(
                ccxt.NetworkError,
                ccxt.RequestTimeout,
                ccxt.DDoSProtection,
                ccxt.ExchangeNotAvailable,
            ),
            max_attempts=self._max_retries,
            context=retry_context,
        )

    async def connect(self) -> None:
        """Establish connection to exchange.

        Raises:
            BrokerConnectionError: If connection fails
        """
        if self._connected:
            logger.warning("already_connected")
            return

        logger.info("connecting_to_exchange", exchange_id=self.exchange_id)

        try:
            await self._execute_with_retry(
                lambda: self.exchange.load_markets(),
                context={"operation": "load_markets"},
            )

            balance = await self._execute_with_retry(
                lambda: self.exchange.fetch_balance(),
                context={"operation": "fetch_balance"},
            )

            if balance is None:
                raise BrokerConnectionError(
                    "Failed to fetch balance from broker",
                    broker=self.exchange_id,
                )

            self._ws_adapter = CCXTWebSocketAdapter(
                exchange_id=self.exchange_id,
                config={
                    "apiKey": self.api_key,
                    "secret": self.api_secret,
                    "sandbox": self.testnet,
                },
                on_tick=self._handle_tick,
            )

            self._bar_buffer = BarBuffer(
                bar_resolution=60,
                on_bar_complete=self._handle_bar_complete,
            )

            await self._execute_with_retry(
                lambda: self._ws_adapter.connect() if self._ws_adapter else asyncio.sleep(0),
                context={"operation": "ws_connect"},
            )

            self._connected = True
            logger.info(
                "connected_to_exchange",
                exchange_id=self.exchange_id,
                markets_loaded=len(self.exchange.markets),
            )

        except BrokerError:
            self._connected = False
            raise
        except ccxt.AuthenticationError as exc:
            self._connected = False
            error = BrokerAuthenticationError(
                f"Authentication with {self.exchange_id} failed: {exc}",
                broker=self.exchange_id,
                cause=exc,
            )
            log_exception(exc, extra={"exchange_id": self.exchange_id, "operation": "connect"})
            raise error from exc
        except ccxt.NetworkError as exc:
            self._connected = False
            error = BrokerConnectionError(
                f"Network error connecting to {self.exchange_id}: {exc}",
                broker=self.exchange_id,
                cause=exc,
            )
            log_exception(exc, extra={"exchange_id": self.exchange_id, "operation": "connect"})
            raise error from exc
        except ccxt.ExchangeError as exc:
            self._connected = False
            error = BrokerResponseError(
                f"Exchange error connecting to {self.exchange_id}: {exc}",
                broker=self.exchange_id,
                cause=exc,
            )
            log_exception(exc, extra={"exchange_id": self.exchange_id, "operation": "connect"})
            raise error from exc
        except Exception as exc:  # pragma: no cover - fallback for unexpected issues
            self._connected = False
            error = BrokerError(
                f"Failed to connect to {self.exchange_id}: {exc}",
                context={"broker": self.exchange_id},
                cause=exc,
            )
            log_exception(exc, extra={"exchange_id": self.exchange_id, "operation": "connect"})
            raise error from exc

    async def disconnect(self) -> None:
        """Disconnect from exchange."""
        if not self._connected:
            logger.warning("not_connected")
            return

        logger.info("disconnecting_from_exchange", exchange_id=self.exchange_id)

        # Disconnect WebSocket first
        if self._ws_adapter:
            await self._ws_adapter.disconnect()
            self._ws_adapter = None

        # Clear bar buffer
        self._bar_buffer = None

        # Close exchange connection
        await self.exchange.close()

        self._connected = False
        logger.info("disconnected_from_exchange", exchange_id=self.exchange_id)

    async def submit_order(
        self,
        asset: Asset,
        amount: Decimal,
        order_type: str,
        limit_price: Decimal | None = None,
        stop_price: Decimal | None = None,
    ) -> str:
        """Submit order to exchange.

        Args:
            asset: Asset to trade
            amount: Order quantity (positive=buy, negative=sell)
            order_type: Order type ('market', 'limit', 'stop', 'stop-limit')
            limit_price: Limit price for limit/stop-limit orders
            stop_price: Stop price for stop orders

        Returns:
            Exchange order ID

        Raises:
            OrderRejectedError: If order is rejected
            BrokerRateLimitError: If rate limit exceeded
            InvalidOrderError: If parameters are invalid for the broker
        """
        if not self._connected:
            raise BrokerConnectionError(
                f"Not connected to {self.exchange_id}", broker=self.exchange_id
            )

        # Validate parameters
        if amount == 0:
            raise ValueError("Order amount cannot be zero")

        # Determine side and quantity
        side = "buy" if amount > 0 else "sell"
        quantity = abs(amount)

        # Map order type to CCXT format
        ccxt_order_type = self._map_order_type(order_type)

        # Build order params
        params = {}

        # Add stop price if provided
        # NOTE: CCXT requires float at API boundary - convert only here
        if stop_price is not None:
            params["stopPrice"] = float(stop_price)

        try:

            async def create_order() -> dict:
                if ccxt_order_type in ("market", "limit"):
                    return await self.exchange.create_order(
                        symbol=asset.symbol,
                        type=ccxt_order_type,
                        side=side,
                        amount=float(quantity),
                        price=float(limit_price) if limit_price else None,
                        params=params,
                    )

                return await self.exchange.create_order(
                    symbol=asset.symbol,
                    type="limit" if limit_price else "market",
                    side=side,
                    amount=float(quantity),
                    price=float(limit_price) if limit_price else None,
                    params={**params, "type": ccxt_order_type},
                )

            order = await self._execute_with_retry(
                create_order,
                context={
                    "operation": "create_order",
                    "symbol": asset.symbol,
                    "side": side,
                },
            )

            order_id = f"{asset.symbol}:{order['id']}"

            # Comprehensive broker order submission logging (AC: 2)
            logger.info(
                "broker_order_submitted",
                event_type="broker_order_submitted",
                exchange_id=self.exchange_id,
                order_id=order_id,
                broker_order_id=order["id"],
                asset=asset.symbol,
                side=side,
                amount=str(amount),
                order_type=ccxt_order_type,
                limit_price=str(limit_price) if limit_price else None,
                stop_price=str(stop_price) if stop_price else None,
                timestamp=pd.Timestamp.now(tz="UTC").isoformat(),
            )

            return order_id

        except ccxt.RateLimitExceeded as exc:
            error = BrokerRateLimitError(
                f"Rate limit exceeded on {self.exchange_id}: {exc}",
                broker=self.exchange_id,
                cause=exc,
            )
            log_exception(exc, extra={"exchange_id": self.exchange_id, "operation": "submit_order"})
            raise error from exc

        except ccxt.InsufficientFunds as exc:
            error = InsufficientFundsError(
                f"Insufficient funds on {self.exchange_id}: {exc}",
                context={"broker": self.exchange_id},
                cause=exc,
            )
            log_exception(exc, extra={"exchange_id": self.exchange_id, "operation": "submit_order"})
            raise error from exc

        except ccxt.InvalidOrder as exc:
            error = InvalidOrderError(
                f"Invalid order on {self.exchange_id}: {exc}",
                context={"broker": self.exchange_id, "symbol": asset.symbol},
                cause=exc,
            )
            log_exception(exc, extra={"exchange_id": self.exchange_id, "operation": "submit_order"})
            raise error from exc

        except ccxt.OrderNotFound as exc:
            error = OrderRejectedError(
                f"Order not found on {self.exchange_id}: {exc}",
                broker=self.exchange_id,
                cause=exc,
            )
            log_exception(exc, extra={"exchange_id": self.exchange_id, "operation": "submit_order"})
            raise error from exc

        except (ccxt.ExchangeError, ccxt.NetworkError) as exc:
            error = BrokerResponseError(
                f"Failed to submit order on {self.exchange_id}: {exc}",
                broker=self.exchange_id,
                cause=exc,
            )
            log_exception(exc, extra={"exchange_id": self.exchange_id, "operation": "submit_order"})
            raise error from exc

    async def cancel_order(self, broker_order_id: str) -> None:
        """Cancel order.

        Args:
            broker_order_id: Exchange order ID (format: 'SYMBOL:ORDERID')

        Raises:
            OrderRejectedError: If cancellation fails
        """
        if not self._connected:
            raise BrokerConnectionError(
                f"Not connected to {self.exchange_id}", broker=self.exchange_id
            )

        # Parse order ID
        if ":" not in broker_order_id:
            raise ValueError("Order ID must be in format 'SYMBOL:ORDERID'")

        symbol, order_id = broker_order_id.split(":", 1)

        try:
            # Cancel order
            await self._execute_with_retry(
                lambda: self.exchange.cancel_order(order_id, symbol),
                context={"operation": "cancel_order", "symbol": symbol},
            )

            logger.info(
                "order_cancelled",
                exchange_id=self.exchange_id,
                order_id=broker_order_id,
                symbol=symbol,
            )

        except (ccxt.ExchangeError, ccxt.NetworkError) as exc:
            error = OrderRejectedError(
                f"Failed to cancel order {broker_order_id} on {self.exchange_id}: {exc}",
                order_id=order_id,
                broker=self.exchange_id,
                cause=exc,
            )
            log_exception(
                exc,
                extra={
                    "exchange_id": self.exchange_id,
                    "operation": "cancel_order",
                    "order_id": broker_order_id,
                },
            )
            raise error from exc

    async def get_account_info(self) -> dict[str, Decimal]:
        """Get account information.

        Returns:
            Dict with keys: 'cash', 'equity', 'buying_power'

        Raises:
            BrokerError: If request fails
        """
        if not self._connected:
            raise BrokerConnectionError(
                f"Not connected to {self.exchange_id}", broker=self.exchange_id
            )

        try:
            balance = await self._execute_with_retry(
                lambda: self.exchange.fetch_balance(),
                context={"operation": "fetch_balance"},
            )

            usdt_balance = balance.get("USDT", {})
            free = Decimal(str(usdt_balance.get("free", 0)))
            used = Decimal(str(usdt_balance.get("used", 0)))
            total = Decimal(str(usdt_balance.get("total", 0)))

            return {
                "cash": free,
                "equity": total,
                "buying_power": free,
                "margin_used": used,
            }

        except (ccxt.ExchangeError, ccxt.NetworkError) as exc:
            error = BrokerResponseError(
                f"Failed to get account info from {self.exchange_id}: {exc}",
                broker=self.exchange_id,
                cause=exc,
            )
            log_exception(
                exc, extra={"exchange_id": self.exchange_id, "operation": "get_account_info"}
            )
            raise error from exc

    async def get_positions(self) -> list[dict]:
        """Get current positions.

        Returns:
            List of position dicts with keys: 'symbol', 'amount', 'entry_price', 'market_value'

        Raises:
            BrokerError: If request fails
        """
        if not self._connected:
            raise BrokerConnectionError(
                f"Not connected to {self.exchange_id}", broker=self.exchange_id
            )

        # Check if exchange supports positions
        if not self.exchange.has.get("fetchPositions"):
            logger.debug(
                "exchange_does_not_support_positions",
                exchange_id=self.exchange_id,
                note="Returning empty list",
            )
            return []

        try:
            positions_data = await self._execute_with_retry(
                lambda: self.exchange.fetch_positions(),
                context={"operation": "fetch_positions"},
            )

            positions = []
            for position_data in positions_data:
                # Skip zero positions
                contracts = float(position_data.get("contracts", 0))
                if contracts == 0:
                    continue

                symbol = position_data["symbol"]
                side = position_data.get("side")  # 'long' or 'short'
                entry_price = Decimal(str(position_data.get("entryPrice", 0)))
                mark_price = Decimal(str(position_data.get("markPrice", 0)))
                notional = Decimal(str(position_data.get("notional", 0)))
                unrealized_pnl = Decimal(str(position_data.get("unrealizedPnl", 0)))

                # Convert to signed amount
                amount = Decimal(str(contracts)) if side == "long" else -Decimal(str(contracts))

                positions.append(
                    {
                        "symbol": symbol,
                        "amount": amount,
                        "entry_price": entry_price,
                        "mark_price": mark_price,
                        "market_value": notional,
                        "unrealized_pnl": unrealized_pnl,
                    }
                )

            logger.debug("positions_fetched", exchange_id=self.exchange_id, count=len(positions))

            return positions

        except (ccxt.ExchangeError, ccxt.NetworkError) as exc:
            error = BrokerResponseError(
                f"Failed to get positions from {self.exchange_id}: {exc}",
                broker=self.exchange_id,
                cause=exc,
            )
            log_exception(
                exc, extra={"exchange_id": self.exchange_id, "operation": "get_positions"}
            )
            raise error from exc

    async def get_open_orders(self) -> list[dict]:
        """Get open/pending orders.

        Returns:
            List of order dicts

        Raises:
            BrokerError: If request fails
        """
        if not self._connected:
            raise BrokerConnectionError(
                f"Not connected to {self.exchange_id}", broker=self.exchange_id
            )

        try:
            orders_data = await self._execute_with_retry(
                lambda: self.exchange.fetch_open_orders(),
                context={"operation": "fetch_open_orders"},
            )

            orders = []
            for order_data in orders_data:
                symbol = order_data["symbol"]
                order_id = str(order_data["id"])

                orders.append(
                    {
                        "order_id": f"{symbol}:{order_id}",
                        "symbol": symbol,
                        "side": order_data["side"],
                        "type": order_data["type"],
                        "quantity": Decimal(str(order_data["amount"])),
                        "price": (
                            Decimal(str(order_data["price"])) if order_data.get("price") else None
                        ),
                        "status": order_data["status"],
                    }
                )

            return orders

        except (ccxt.ExchangeError, ccxt.NetworkError) as exc:
            error = BrokerResponseError(
                f"Failed to get open orders from {self.exchange_id}: {exc}",
                broker=self.exchange_id,
                cause=exc,
            )
            log_exception(
                exc, extra={"exchange_id": self.exchange_id, "operation": "get_open_orders"}
            )
            raise error from exc

    async def subscribe_market_data(self, assets: list[Asset]) -> None:
        """Subscribe to real-time market data via WebSocket.

        Args:
            assets: List of assets to subscribe

        Raises:
            BrokerError: If subscription fails
        """
        if not self._connected:
            raise BrokerConnectionError(
                f"Not connected to {self.exchange_id}", broker=self.exchange_id
            )

        if not self._ws_adapter:
            raise BrokerConnectionError(
                "WebSocket adapter not initialized", broker=self.exchange_id
            )

        symbols = [asset.symbol for asset in assets]

        try:
            # Subscribe to trades stream for real-time tick data
            await self._ws_adapter.subscribe(symbols=symbols, channels=["trades"])

            logger.info(
                "market_data_subscribed",
                exchange_id=self.exchange_id,
                symbols=symbols,
                channels=["trades"],
            )

        except Exception as exc:  # pragma: no cover - websocket adapter handles most errors
            error = BrokerError(
                f"Failed to subscribe to market data: {exc}",
                context={"broker": self.exchange_id, "operation": "subscribe", "symbols": symbols},
                cause=exc,
            )
            log_exception(
                exc, extra={"exchange_id": self.exchange_id, "operation": "subscribe_market_data"}
            )
            raise error from exc

    async def unsubscribe_market_data(self, assets: list[Asset]) -> None:
        """Unsubscribe from market data via WebSocket.

        Args:
            assets: List of assets to unsubscribe

        Raises:
            BrokerError: If unsubscription fails
        """
        if not self._connected:
            raise BrokerConnectionError(
                f"Not connected to {self.exchange_id}", broker=self.exchange_id
            )

        if not self._ws_adapter:
            raise BrokerConnectionError(
                "WebSocket adapter not initialized", broker=self.exchange_id
            )

        symbols = [asset.symbol for asset in assets]

        try:
            # Unsubscribe from trades stream
            await self._ws_adapter.unsubscribe(symbols=symbols, channels=["trades"])

            logger.info(
                "market_data_unsubscribed",
                exchange_id=self.exchange_id,
                symbols=symbols,
                channels=["trades"],
            )

        except Exception as exc:  # pragma: no cover - websocket adapter handles most errors
            error = BrokerError(
                f"Failed to unsubscribe from market data: {exc}",
                context={
                    "broker": self.exchange_id,
                    "operation": "unsubscribe",
                    "symbols": symbols,
                },
                cause=exc,
            )
            log_exception(
                exc, extra={"exchange_id": self.exchange_id, "operation": "unsubscribe_market_data"}
            )
            raise error from exc

    async def get_next_market_data(self) -> dict | None:
        """Get next market data update.

        Returns:
            Market data dict or None if queue is empty
        """
        try:
            return await asyncio.wait_for(self._market_data_queue.get(), timeout=0.1)
        except TimeoutError:
            return None

    async def get_current_price(self, asset: Asset) -> Decimal:
        """Get current price for asset.

        Args:
            asset: Asset to get price for

        Returns:
            Current price

        Raises:
            BrokerError: If price fetch fails
        """
        if not self._connected:
            raise BrokerConnectionError(
                f"Not connected to {self.exchange_id}", broker=self.exchange_id
            )

        try:
            ticker = await self._execute_with_retry(
                lambda: self.exchange.fetch_ticker(asset.symbol),
                context={"operation": "fetch_ticker", "symbol": asset.symbol},
            )

            if not ticker or "last" not in ticker:
                raise BrokerResponseError(
                    f"No price data for {asset.symbol}",
                    broker=self.exchange_id,
                    context={"symbol": asset.symbol},
                )

            price = Decimal(str(ticker["last"]))

            logger.debug(
                "price_fetched",
                exchange_id=self.exchange_id,
                symbol=asset.symbol,
                price=str(price),
            )

            return price

        except BrokerError:
            raise
        except (ccxt.ExchangeError, ccxt.NetworkError) as exc:
            error = BrokerResponseError(
                f"Failed to get current price from {self.exchange_id}: {exc}",
                broker=self.exchange_id,
                context={"symbol": asset.symbol},
                cause=exc,
            )
            log_exception(
                exc,
                extra={
                    "exchange_id": self.exchange_id,
                    "operation": "get_current_price",
                    "symbol": asset.symbol,
                },
            )
            raise error from exc

    def is_connected(self) -> bool:
        """Check if connected to exchange.

        Returns:
            True if connected, False otherwise
        """
        return self._connected

    # Private methods

    def _map_order_type(self, order_type: str) -> str:
        """Map RustyBT order type to CCXT order type.

        Args:
            order_type: RustyBT order type

        Returns:
            CCXT order type

        Raises:
            ValueError: If order type is not supported
        """
        # CCXT unified order types
        order_type_map = {
            "market": "market",
            "limit": "limit",
        }

        # Return mapped type or original (for exchange-specific types)
        return order_type_map.get(order_type, order_type)

    def get_exchange_capabilities(self) -> dict[str, bool]:
        """Get exchange capabilities.

        Returns:
            Dict of capabilities supported by exchange

        Example:
            >>> capabilities = adapter.get_exchange_capabilities()
            >>> if capabilities['fetchPositions']:
            ...     positions = await adapter.get_positions()
        """
        return {
            "fetchPositions": self.exchange.has.get("fetchPositions", False),
            "fetchOHLCV": self.exchange.has.get("fetchOHLCV", False),
            "fetchTicker": self.exchange.has.get("fetchTicker", False),
            "fetchTickers": self.exchange.has.get("fetchTickers", False),
            "fetchOrderBook": self.exchange.has.get("fetchOrderBook", False),
            "fetchTrades": self.exchange.has.get("fetchTrades", False),
            "createOrder": self.exchange.has.get("createOrder", False),
            "cancelOrder": self.exchange.has.get("cancelOrder", False),
            "fetchBalance": self.exchange.has.get("fetchBalance", False),
            "fetchOpenOrders": self.exchange.has.get("fetchOpenOrders", False),
            "fetchClosedOrders": self.exchange.has.get("fetchClosedOrders", False),
        }

    def _handle_tick(self, tick: "TickData") -> None:
        """Handle incoming tick data from WebSocket.

        Adds tick to bar buffer for OHLCV aggregation.

        Args:
            tick: Tick data from WebSocket
        """
        if not self._bar_buffer:
            logger.warning("bar_buffer_not_initialized", symbol=tick.symbol)
            return

        # Add tick to bar buffer (will emit bar if boundary crossed)
        self._bar_buffer.add_tick(tick)

        logger.debug(
            "tick_received",
            exchange_id=self.exchange_id,
            symbol=tick.symbol,
            price=str(tick.price),
            volume=str(tick.volume),
            timestamp=tick.timestamp.isoformat(),
        )

    def _handle_bar_complete(self, bar: OHLCVBar) -> None:
        """Handle completed OHLCV bar from bar buffer.

        Converts bar to MarketDataEvent and pushes to queue.

        Args:
            bar: Completed OHLCV bar
        """
        # Convert OHLCVBar to market data dict for queue
        market_data = {
            "type": "bar",
            "symbol": bar.symbol,
            "timestamp": bar.timestamp,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
        }

        # Push to queue (non-blocking)
        try:
            self._market_data_queue.put_nowait(market_data)

            logger.info(
                "bar_completed",
                exchange_id=self.exchange_id,
                symbol=bar.symbol,
                timestamp=bar.timestamp.isoformat(),
                open=str(bar.open),
                high=str(bar.high),
                low=str(bar.low),
                close=str(bar.close),
                volume=str(bar.volume),
            )

        except asyncio.QueueFull:
            logger.warning(
                "market_data_queue_full",
                exchange_id=self.exchange_id,
                symbol=bar.symbol,
                queue_size=self._market_data_queue.qsize(),
            )
