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
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import ccxt
import ccxt.async_support as ccxt_async
import structlog

from rustybt.assets import Asset
from rustybt.live.brokers.base import BrokerAdapter
from rustybt.live.streaming.bar_buffer import BarBuffer, OHLCVBar
from rustybt.live.streaming.ccxt_stream import CCXTWebSocketAdapter

if TYPE_CHECKING:
    from rustybt.live.streaming.models import TickData

logger = structlog.get_logger(__name__)


class CCXTConnectionError(Exception):
    """CCXT connection error."""


class CCXTOrderRejectError(Exception):
    """CCXT order rejection error."""


class CCXTRateLimitError(Exception):
    """CCXT rate limit exceeded error."""


class CCXTExchangeError(Exception):
    """CCXT exchange-specific error."""


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

    def __init__(
        self,
        exchange_id: str,
        api_key: str,
        api_secret: str,
        market_type: str = "spot",
        testnet: bool = False,
        exchange_params: Optional[Dict[str, Any]] = None,
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
            CCXTConnectionError: If exchange initialization fails
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
            self._market_data_queue: asyncio.Queue[Dict] = asyncio.Queue()

            # WebSocket streaming components
            self._ws_adapter: Optional[CCXTWebSocketAdapter] = None
            self._bar_buffer: Optional[BarBuffer] = None

            logger.info(
                "ccxt_adapter_initialized",
                exchange_id=self.exchange_id,
                market_type=market_type,
                testnet=testnet,
            )

        except Exception as e:
            logger.error("exchange_initialization_failed", exchange_id=exchange_id, error=str(e))
            raise CCXTConnectionError(f"Failed to initialize exchange {exchange_id}: {e}") from e

    async def connect(self) -> None:
        """Establish connection to exchange.

        Raises:
            CCXTConnectionError: If connection fails
        """
        if self._connected:
            logger.warning("already_connected")
            return

        logger.info("connecting_to_exchange", exchange_id=self.exchange_id)

        try:
            # Load markets (test connectivity)
            await self.exchange.load_markets()

            # Test authentication by fetching balance
            balance = await self.exchange.fetch_balance()

            if balance is None:
                raise CCXTConnectionError("Failed to fetch balance")

            # Initialize WebSocket adapter
            self._ws_adapter = CCXTWebSocketAdapter(
                exchange_id=self.exchange_id,
                config={"apiKey": self.api_key, "secret": self.api_secret, "sandbox": self.testnet},
                on_tick=self._handle_tick,
            )

            # Initialize bar buffer (1-minute bars default)
            self._bar_buffer = BarBuffer(
                bar_resolution=60,  # 60 seconds = 1 minute
                on_bar_complete=self._handle_bar_complete,
            )

            # Connect WebSocket
            await self._ws_adapter.connect()

            self._connected = True
            logger.info(
                "connected_to_exchange",
                exchange_id=self.exchange_id,
                markets_loaded=len(self.exchange.markets),
            )

        except ccxt.NetworkError as e:
            self._connected = False
            logger.error("network_error", exchange_id=self.exchange_id, error=str(e))
            raise CCXTConnectionError(f"Network error connecting to {self.exchange_id}: {e}") from e

        except ccxt.ExchangeError as e:
            self._connected = False
            logger.error("exchange_error", exchange_id=self.exchange_id, error=str(e))
            raise CCXTConnectionError(f"Exchange error connecting to {self.exchange_id}: {e}") from e

        except Exception as e:
            self._connected = False
            logger.error("connection_failed", exchange_id=self.exchange_id, error=str(e))
            raise CCXTConnectionError(f"Failed to connect to {self.exchange_id}: {e}") from e

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
        limit_price: Optional[Decimal] = None,
        stop_price: Optional[Decimal] = None,
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
            CCXTOrderRejectError: If order is rejected
            CCXTRateLimitError: If rate limit exceeded
            ValueError: If parameters are invalid
        """
        if not self._connected:
            raise CCXTConnectionError(f"Not connected to {self.exchange_id}")

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
            # Create order
            if ccxt_order_type in ("market", "limit"):
                # Standard market/limit order
                order = await self.exchange.create_order(
                    symbol=asset.symbol,
                    type=ccxt_order_type,
                    side=side,
                    amount=float(quantity),
                    price=float(limit_price) if limit_price else None,
                    params=params,
                )
            else:
                # Exchange-specific order type (stop, stop-limit, etc.)
                # Pass via params
                order = await self.exchange.create_order(
                    symbol=asset.symbol,
                    type="limit" if limit_price else "market",
                    side=side,
                    amount=float(quantity),
                    price=float(limit_price) if limit_price else None,
                    params={**params, "type": ccxt_order_type},
                )

            order_id = f"{asset.symbol}:{order['id']}"

            logger.info(
                "order_submitted",
                exchange_id=self.exchange_id,
                order_id=order_id,
                symbol=asset.symbol,
                side=side,
                order_type=ccxt_order_type,
                quantity=quantity,
                price=str(limit_price) if limit_price else "market",
            )

            return order_id

        except ccxt.RateLimitExceeded as e:
            logger.error("rate_limit_exceeded", exchange_id=self.exchange_id, error=str(e))
            raise CCXTRateLimitError(f"Rate limit exceeded on {self.exchange_id}: {e}") from e

        except ccxt.InsufficientFunds as e:
            logger.error("insufficient_funds", exchange_id=self.exchange_id, error=str(e))
            raise CCXTOrderRejectError(f"Insufficient funds on {self.exchange_id}: {e}") from e

        except ccxt.InvalidOrder as e:
            logger.error("invalid_order", exchange_id=self.exchange_id, error=str(e))
            raise CCXTOrderRejectError(f"Invalid order on {self.exchange_id}: {e}") from e

        except (ccxt.ExchangeError, ccxt.NetworkError) as e:
            logger.error("order_submission_failed", exchange_id=self.exchange_id, error=str(e))
            raise CCXTExchangeError(f"Failed to submit order on {self.exchange_id}: {e}") from e

    async def cancel_order(self, broker_order_id: str) -> None:
        """Cancel order.

        Args:
            broker_order_id: Exchange order ID (format: 'SYMBOL:ORDERID')

        Raises:
            CCXTOrderRejectError: If cancellation fails
        """
        if not self._connected:
            raise CCXTConnectionError(f"Not connected to {self.exchange_id}")

        # Parse order ID
        if ":" not in broker_order_id:
            raise ValueError("Order ID must be in format 'SYMBOL:ORDERID'")

        symbol, order_id = broker_order_id.split(":", 1)

        try:
            # Cancel order
            await self.exchange.cancel_order(order_id, symbol)

            logger.info(
                "order_cancelled",
                exchange_id=self.exchange_id,
                order_id=broker_order_id,
                symbol=symbol,
            )

        except (ccxt.ExchangeError, ccxt.NetworkError) as e:
            logger.error(
                "order_cancellation_failed",
                exchange_id=self.exchange_id,
                order_id=broker_order_id,
                error=str(e),
            )
            raise CCXTOrderRejectError(
                f"Failed to cancel order {broker_order_id} on {self.exchange_id}: {e}"
            ) from e

    async def get_account_info(self) -> Dict[str, Decimal]:
        """Get account information.

        Returns:
            Dict with keys: 'cash', 'equity', 'buying_power'

        Raises:
            CCXTConnectionError: If request fails
        """
        if not self._connected:
            raise CCXTConnectionError(f"Not connected to {self.exchange_id}")

        try:
            # Fetch balance
            balance = await self.exchange.fetch_balance()

            # Extract USDT balance (simplified)
            usdt_balance = balance.get("USDT", {})
            free = Decimal(str(usdt_balance.get("free", 0)))
            used = Decimal(str(usdt_balance.get("used", 0)))
            total = Decimal(str(usdt_balance.get("total", 0)))

            return {
                "cash": free,
                "equity": total,
                "buying_power": free,
            }

        except (ccxt.ExchangeError, ccxt.NetworkError) as e:
            logger.error("get_account_info_failed", exchange_id=self.exchange_id, error=str(e))
            raise CCXTConnectionError(
                f"Failed to get account info from {self.exchange_id}: {e}"
            ) from e

    async def get_positions(self) -> List[Dict]:
        """Get current positions.

        Returns:
            List of position dicts with keys: 'symbol', 'amount', 'entry_price', 'market_value'

        Raises:
            CCXTConnectionError: If request fails
        """
        if not self._connected:
            raise CCXTConnectionError(f"Not connected to {self.exchange_id}")

        # Check if exchange supports positions
        if not self.exchange.has.get("fetchPositions"):
            logger.debug(
                "exchange_does_not_support_positions",
                exchange_id=self.exchange_id,
                note="Returning empty list",
            )
            return []

        try:
            # Fetch positions
            positions_data = await self.exchange.fetch_positions()

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

                positions.append({
                    "symbol": symbol,
                    "amount": amount,
                    "entry_price": entry_price,
                    "mark_price": mark_price,
                    "market_value": notional,
                    "unrealized_pnl": unrealized_pnl,
                })

            logger.debug("positions_fetched", exchange_id=self.exchange_id, count=len(positions))

            return positions

        except (ccxt.ExchangeError, ccxt.NetworkError) as e:
            logger.error("get_positions_failed", exchange_id=self.exchange_id, error=str(e))
            raise CCXTConnectionError(f"Failed to get positions from {self.exchange_id}: {e}") from e

    async def get_open_orders(self) -> List[Dict]:
        """Get open/pending orders.

        Returns:
            List of order dicts

        Raises:
            CCXTConnectionError: If request fails
        """
        if not self._connected:
            raise CCXTConnectionError(f"Not connected to {self.exchange_id}")

        try:
            # Fetch open orders
            orders_data = await self.exchange.fetch_open_orders()

            orders = []
            for order_data in orders_data:
                symbol = order_data["symbol"]
                order_id = str(order_data["id"])

                orders.append({
                    "order_id": f"{symbol}:{order_id}",
                    "symbol": symbol,
                    "side": order_data["side"],
                    "type": order_data["type"],
                    "quantity": Decimal(str(order_data["amount"])),
                    "price": Decimal(str(order_data["price"])) if order_data.get("price") else None,
                    "status": order_data["status"],
                })

            return orders

        except (ccxt.ExchangeError, ccxt.NetworkError) as e:
            logger.error("get_open_orders_failed", exchange_id=self.exchange_id, error=str(e))
            raise CCXTConnectionError(
                f"Failed to get open orders from {self.exchange_id}: {e}"
            ) from e

    async def subscribe_market_data(self, assets: List[Asset]) -> None:
        """Subscribe to real-time market data via WebSocket.

        Args:
            assets: List of assets to subscribe

        Raises:
            CCXTConnectionError: If subscription fails
        """
        if not self._connected:
            raise CCXTConnectionError(f"Not connected to {self.exchange_id}")

        if not self._ws_adapter:
            raise CCXTConnectionError("WebSocket adapter not initialized")

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

        except Exception as e:
            logger.error("market_data_subscription_failed", exchange_id=self.exchange_id, symbols=symbols, error=str(e))
            raise CCXTConnectionError(f"Failed to subscribe to market data: {e}") from e

    async def unsubscribe_market_data(self, assets: List[Asset]) -> None:
        """Unsubscribe from market data via WebSocket.

        Args:
            assets: List of assets to unsubscribe

        Raises:
            CCXTConnectionError: If unsubscription fails
        """
        if not self._connected:
            raise CCXTConnectionError(f"Not connected to {self.exchange_id}")

        if not self._ws_adapter:
            raise CCXTConnectionError("WebSocket adapter not initialized")

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

        except Exception as e:
            logger.error("market_data_unsubscription_failed", exchange_id=self.exchange_id, symbols=symbols, error=str(e))
            raise CCXTConnectionError(f"Failed to unsubscribe from market data: {e}") from e

    async def get_next_market_data(self) -> Optional[Dict]:
        """Get next market data update.

        Returns:
            Market data dict or None if queue is empty
        """
        try:
            return await asyncio.wait_for(self._market_data_queue.get(), timeout=0.1)
        except asyncio.TimeoutError:
            return None

    async def get_current_price(self, asset: Asset) -> Decimal:
        """Get current price for asset.

        Args:
            asset: Asset to get price for

        Returns:
            Current price

        Raises:
            CCXTConnectionError: If price fetch fails
        """
        if not self._connected:
            raise CCXTConnectionError(f"Not connected to {self.exchange_id}")

        try:
            # Fetch ticker
            ticker = await self.exchange.fetch_ticker(asset.symbol)

            if not ticker or "last" not in ticker:
                raise CCXTConnectionError(f"No price data for {asset.symbol}")

            price = Decimal(str(ticker["last"]))

            logger.debug(
                "price_fetched",
                exchange_id=self.exchange_id,
                symbol=asset.symbol,
                price=str(price),
            )

            return price

        except (ccxt.ExchangeError, ccxt.NetworkError) as e:
            logger.error(
                "get_current_price_failed",
                exchange_id=self.exchange_id,
                symbol=asset.symbol,
                error=str(e),
            )
            raise CCXTConnectionError(
                f"Failed to get current price from {self.exchange_id}: {e}"
            ) from e

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

    def get_exchange_capabilities(self) -> Dict[str, bool]:
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
