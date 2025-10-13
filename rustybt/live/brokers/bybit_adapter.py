"""Bybit broker adapter for live trading.

This module provides integration with Bybit exchange for live trading,
supporting both spot and derivatives markets via the pybit SDK.
"""

import asyncio
import time
from decimal import Decimal
from typing import TYPE_CHECKING

import structlog
from pybit.unified_trading import HTTP

from rustybt.assets import Asset
from rustybt.live.brokers.base import BrokerAdapter
from rustybt.live.streaming.bar_buffer import BarBuffer, OHLCVBar
from rustybt.live.streaming.bybit_stream import BybitWebSocketAdapter

if TYPE_CHECKING:
    from rustybt.live.streaming.models import TickData

logger = structlog.get_logger(__name__)


class BybitConnectionError(Exception):
    """Bybit connection error."""


class BybitOrderRejectError(Exception):
    """Bybit order rejection error."""


class BybitRateLimitError(Exception):
    """Bybit rate limit exceeded error."""


class BybitMaintenanceError(Exception):
    """Bybit exchange under maintenance error."""


class BybitBrokerAdapter(BrokerAdapter):
    """Bybit broker adapter.

    Integrates with Bybit exchange for live trading via pybit SDK.
    Supports spot and derivatives markets (linear and inverse perpetuals).

    Supported Order Types:
        - MARKET: Market order
        - LIMIT: Limit order
        - CONDITIONAL: Conditional order (stop/take-profit)

    Order Execution Modes:
        - Post-Only: Maker-only orders
        - Reduce-Only: Position reduction only

    Rate Limits:
        - REST API: 120 requests/minute
        - WebSocket: 10 messages/second
        - Order placement: 100 orders/second per symbol

    Error Handling:
        - Authentication errors
        - Rate limit errors
        - Invalid parameter errors
        - Insufficient balance errors
    """

    # API endpoints
    MAINNET_URL = "https://api.bybit.com"
    TESTNET_URL = "https://api-testnet.bybit.com"

    # Rate limiting
    REQUESTS_PER_MINUTE = 120
    ORDERS_PER_SECOND = 100

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        market_type: str = "linear",
        testnet: bool = False,
    ) -> None:
        """Initialize Bybit broker adapter.

        Args:
            api_key: Bybit API key
            api_secret: Bybit API secret
            market_type: Market type ('spot', 'linear', 'inverse')
            testnet: Use testnet if True

        Raises:
            ValueError: If market_type is invalid
        """
        if market_type not in ("spot", "linear", "inverse"):
            raise ValueError(
                f"Invalid market_type: {market_type}, must be 'spot', 'linear', or 'inverse'"
            )

        self.api_key = api_key
        self.api_secret = api_secret
        self.market_type = market_type
        self.testnet = testnet

        # Initialize pybit client
        self.client = HTTP(
            testnet=testnet,
            api_key=api_key,
            api_secret=api_secret,
        )

        self._connected = False
        self._market_data_queue: asyncio.Queue[dict] = asyncio.Queue()

        # Rate limiting tracking
        self._request_timestamps: list[float] = []
        self._order_timestamps: dict[str, list[float]] = {}

        # WebSocket streaming components
        self._ws_adapter: BybitWebSocketAdapter | None = None
        self._bar_buffer: BarBuffer | None = None

        logger.info(
            "bybit_adapter_initialized",
            market_type=market_type,
            testnet=testnet,
        )

    async def connect(self) -> None:
        """Establish connection to Bybit.

        Raises:
            BybitConnectionError: If connection fails
        """
        if self._connected:
            logger.warning("already_connected")
            return

        logger.info("connecting_to_bybit", market_type=self.market_type)

        try:
            # Test API connectivity by fetching server time
            response = self.client.get_server_time()

            if response["retCode"] != 0:
                error_msg = response.get("retMsg", "Unknown error")
                raise BybitConnectionError(f"Failed to connect to Bybit: {error_msg}")

            # Initialize WebSocket adapter
            self._ws_adapter = BybitWebSocketAdapter(
                market_type=self.market_type,
                testnet=self.testnet,
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
            logger.info("connected_to_bybit", market_type=self.market_type)

        except Exception as e:
            self._connected = False
            logger.error("connection_failed", error=str(e))
            raise BybitConnectionError(f"Failed to connect to Bybit: {e}") from e

    async def disconnect(self) -> None:
        """Disconnect from Bybit."""
        if not self._connected:
            logger.warning("not_connected")
            return

        logger.info("disconnecting_from_bybit")

        # Disconnect WebSocket first
        if self._ws_adapter:
            await self._ws_adapter.disconnect()
            self._ws_adapter = None

        # Clear bar buffer
        self._bar_buffer = None

        # pybit HTTP client doesn't need explicit disconnect
        self._connected = False

        logger.info("disconnected_from_bybit")

    async def submit_order(
        self,
        asset: Asset,
        amount: Decimal,
        order_type: str,
        limit_price: Decimal | None = None,
        stop_price: Decimal | None = None,
        post_only: bool = False,
        reduce_only: bool = False,
    ) -> str:
        """Submit order to Bybit.

        Args:
            asset: Asset to trade
            amount: Order quantity (positive=buy, negative=sell)
            order_type: Order type ('market', 'limit', 'stop', 'stop-limit')
            limit_price: Limit price for limit/stop-limit orders
            stop_price: Stop price for conditional orders
            post_only: Post-Only mode (maker-only, Limit orders only)
            reduce_only: Reduce-Only mode (position reduction only, derivatives only)

        Returns:
            Bybit order ID

        Raises:
            BybitOrderRejectError: If order is rejected
            BybitRateLimitError: If rate limit exceeded
            ValueError: If parameters are invalid

        Examples:
            # Post-Only order (maker-only execution)
            await adapter.submit_order(
                asset=btc,
                amount=Decimal("0.1"),
                order_type="limit",
                limit_price=Decimal("50000"),
                post_only=True
            )

            # Reduce-Only order (only reduces position)
            await adapter.submit_order(
                asset=btc,
                amount=Decimal("-0.1"),
                order_type="market",
                reduce_only=True
            )
        """
        if not self._connected:
            raise BybitConnectionError("Not connected to Bybit")

        # Check rate limits
        await self._check_request_rate_limit()
        await self._check_order_rate_limit(asset.symbol)

        # Validate parameters
        if amount == 0:
            raise ValueError("Order amount cannot be zero")

        # Validate Post-Only with Market orders
        if post_only and order_type == "market":
            raise ValueError("Post-Only mode is incompatible with Market orders (Limit only)")

        # Map order type
        bybit_order_type = self._map_order_type(order_type)

        # Determine side
        side = "Buy" if amount > 0 else "Sell"
        quantity = str(abs(amount))

        # Build order params
        params = {
            "category": self._get_category(),
            "symbol": asset.symbol,
            "side": side,
            "orderType": bybit_order_type,
            "qty": quantity,
        }

        # Add price for limit orders
        if bybit_order_type == "Limit":
            if limit_price is None:
                raise ValueError(f"limit_price required for {order_type} order")
            params["price"] = str(limit_price)

        # Add trigger price for conditional orders
        if stop_price is not None:
            params["triggerPrice"] = str(stop_price)
            params["triggerBy"] = "LastPrice"  # Use last price as trigger

        # Add Post-Only mode (Limit orders only)
        if post_only:
            params["timeInForce"] = "PostOnly"

        # Add Reduce-Only mode (derivatives only)
        if reduce_only:
            params["reduceOnly"] = True

        try:
            # Submit order
            response = self.client.place_order(**params)

            if response["retCode"] != 0:
                error_msg = response.get("retMsg", "Unknown error")
                error_code = response.get("retCode", -1)

                # Handle specific errors
                if error_code == 10006:
                    raise BybitRateLimitError(f"Rate limit exceeded: {error_msg}")
                elif error_code == 110001:
                    raise BybitOrderRejectError(f"Insufficient balance: {error_msg}")
                else:
                    raise BybitOrderRejectError(f"Order rejected: {error_msg}")

            result = response["result"]
            order_id = f"{asset.symbol}:{result['orderId']}"

            logger.info(
                "order_submitted",
                order_id=order_id,
                symbol=asset.symbol,
                side=side,
                order_type=bybit_order_type,
                quantity=quantity,
                price=str(limit_price) if limit_price else None,
                post_only=post_only,
                reduce_only=reduce_only,
            )

            return order_id

        except Exception as e:
            logger.error(
                "order_submission_failed",
                symbol=asset.symbol,
                side=side,
                error=str(e),
            )
            raise

    async def cancel_order(self, broker_order_id: str) -> None:
        """Cancel order.

        Args:
            broker_order_id: Bybit order ID (format: 'SYMBOL:ORDERID')

        Raises:
            BybitOrderRejectError: If cancellation fails
        """
        if not self._connected:
            raise BybitConnectionError("Not connected to Bybit")

        # Parse order ID
        if ":" not in broker_order_id:
            raise ValueError("Order ID must be in format 'SYMBOL:ORDERID'")

        symbol, order_id = broker_order_id.split(":", 1)

        try:
            response = self.client.cancel_order(
                category=self._get_category(),
                symbol=symbol,
                orderId=order_id,
            )

            if response["retCode"] != 0:
                error_msg = response.get("retMsg", "Unknown error")
                raise BybitOrderRejectError(f"Failed to cancel order: {error_msg}")

            logger.info("order_cancelled", order_id=broker_order_id, symbol=symbol)

        except Exception as e:
            logger.error("order_cancellation_failed", order_id=broker_order_id, error=str(e))
            raise BybitOrderRejectError(f"Failed to cancel order {broker_order_id}: {e}") from e

    async def get_account_info(self) -> dict[str, Decimal]:
        """Get account information.

        Returns:
            Dict with keys: 'cash', 'equity', 'buying_power'

        Raises:
            BybitConnectionError: If request fails
        """
        if not self._connected:
            raise BybitConnectionError("Not connected to Bybit")

        try:
            # Get wallet balance
            response = self.client.get_wallet_balance(
                accountType="UNIFIED" if self.market_type != "spot" else "SPOT",
            )

            if response["retCode"] != 0:
                error_msg = response.get("retMsg", "Unknown error")
                raise BybitConnectionError(f"Failed to get account info: {error_msg}")

            result = response["result"]

            if self.market_type == "spot":
                # Spot account
                balances = result.get("list", [])
                if not balances:
                    return {
                        "cash": Decimal("0"),
                        "equity": Decimal("0"),
                        "buying_power": Decimal("0"),
                    }

                # Find USDT balance
                total_cash = Decimal("0")
                for balance in balances[0].get("coin", []):
                    if balance["coin"] == "USDT":
                        total_cash = Decimal(balance["walletBalance"])
                        break

                return {
                    "cash": total_cash,
                    "equity": total_cash,
                    "buying_power": total_cash,
                }
            else:
                # Unified account (derivatives)
                accounts = result.get("list", [])
                if not accounts:
                    return {
                        "cash": Decimal("0"),
                        "equity": Decimal("0"),
                        "buying_power": Decimal("0"),
                    }

                account = accounts[0]
                total_equity = Decimal(account["totalEquity"])
                available_balance = Decimal(account["totalAvailableBalance"])

                return {
                    "cash": available_balance,
                    "equity": total_equity,
                    "buying_power": available_balance,
                }

        except Exception as e:
            logger.error("get_account_info_failed", error=str(e))
            raise BybitConnectionError(f"Failed to get account info: {e}") from e

    async def get_positions(self) -> list[dict]:
        """Get current positions.

        Returns:
            List of position dicts with keys: 'symbol', 'amount', 'entry_price', 'market_value'

        Raises:
            BybitConnectionError: If request fails
        """
        if not self._connected:
            raise BybitConnectionError("Not connected to Bybit")

        if self.market_type == "spot":
            # Spot market has balances, not positions
            return []

        try:
            response = self.client.get_positions(
                category=self._get_category(),
                settleCoin="USDT",  # Filter by settlement currency
            )

            if response["retCode"] != 0:
                error_msg = response.get("retMsg", "Unknown error")
                raise BybitConnectionError(f"Failed to get positions: {error_msg}")

            result = response["result"]
            positions_data = result.get("list", [])

            positions = []
            for position_data in positions_data:
                size = Decimal(position_data["size"])

                # Skip zero positions
                if size == 0:
                    continue

                symbol = position_data["symbol"]
                side = position_data["side"]  # Buy or Sell
                entry_price = Decimal(position_data["avgPrice"])
                mark_price = Decimal(position_data["markPrice"])
                unrealized_pnl = Decimal(position_data["unrealisedPnl"])

                # Convert side to signed amount
                amount = size if side == "Buy" else -size

                positions.append(
                    {
                        "symbol": symbol,
                        "amount": amount,
                        "entry_price": entry_price,
                        "mark_price": mark_price,
                        "unrealized_pnl": unrealized_pnl,
                        "market_value": size * mark_price,
                    }
                )

            logger.debug("positions_fetched", count=len(positions))

            return positions

        except Exception as e:
            logger.error("get_positions_failed", error=str(e))
            raise BybitConnectionError(f"Failed to get positions: {e}") from e

    async def get_open_orders(self) -> list[dict]:
        """Get open/pending orders.

        Returns:
            List of order dicts

        Raises:
            BybitConnectionError: If request fails
        """
        if not self._connected:
            raise BybitConnectionError("Not connected to Bybit")

        try:
            response = self.client.get_open_orders(
                category=self._get_category(),
            )

            if response["retCode"] != 0:
                error_msg = response.get("retMsg", "Unknown error")
                raise BybitConnectionError(f"Failed to get open orders: {error_msg}")

            result = response["result"]
            orders_data = result.get("list", [])

            orders = []
            for order_data in orders_data:
                orders.append(
                    {
                        "order_id": f"{order_data['symbol']}:{order_data['orderId']}",
                        "symbol": order_data["symbol"],
                        "side": order_data["side"],
                        "type": order_data["orderType"],
                        "quantity": Decimal(order_data["qty"]),
                        "price": Decimal(order_data["price"]) if order_data.get("price") else None,
                        "status": order_data["orderStatus"],
                    }
                )

            return orders

        except Exception as e:
            logger.error("get_open_orders_failed", error=str(e))
            raise BybitConnectionError(f"Failed to get open orders: {e}") from e

    async def subscribe_market_data(self, assets: list[Asset]) -> None:
        """Subscribe to real-time market data via WebSocket.

        Args:
            assets: List of assets to subscribe

        Raises:
            BybitConnectionError: If subscription fails
        """
        if not self._connected:
            raise BybitConnectionError("Not connected to Bybit")

        if not self._ws_adapter:
            raise BybitConnectionError("WebSocket adapter not initialized")

        symbols = [asset.symbol for asset in assets]

        try:
            # Subscribe to public trade stream for real-time tick data
            await self._ws_adapter.subscribe(symbols=symbols, channels=["publicTrade"])

            logger.info(
                "market_data_subscribed",
                symbols=symbols,
                channels=["publicTrade"],
            )

        except Exception as e:
            logger.error("market_data_subscription_failed", symbols=symbols, error=str(e))
            raise BybitConnectionError(f"Failed to subscribe to market data: {e}") from e

    async def unsubscribe_market_data(self, assets: list[Asset]) -> None:
        """Unsubscribe from market data via WebSocket.

        Args:
            assets: List of assets to unsubscribe

        Raises:
            BybitConnectionError: If unsubscribe fails
        """
        if not self._connected:
            raise BybitConnectionError("Not connected to Bybit")

        if not self._ws_adapter:
            raise BybitConnectionError("WebSocket adapter not initialized")

        symbols = [asset.symbol for asset in assets]

        try:
            # Unsubscribe from public trade stream
            await self._ws_adapter.unsubscribe(symbols=symbols, channels=["publicTrade"])

            logger.info(
                "market_data_unsubscribed",
                symbols=symbols,
                channels=["publicTrade"],
            )

        except Exception as e:
            logger.error("market_data_unsubscription_failed", symbols=symbols, error=str(e))
            raise BybitConnectionError(f"Failed to unsubscribe from market data: {e}") from e

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
            BybitConnectionError: If price fetch fails
        """
        if not self._connected:
            raise BybitConnectionError("Not connected to Bybit")

        try:
            response = self.client.get_tickers(
                category=self._get_category(),
                symbol=asset.symbol,
            )

            if response["retCode"] != 0:
                error_msg = response.get("retMsg", "Unknown error")
                raise BybitConnectionError(f"Failed to get price: {error_msg}")

            result = response["result"]
            tickers = result.get("list", [])

            if not tickers:
                raise BybitConnectionError(f"No price data for {asset.symbol}")

            price = Decimal(tickers[0]["lastPrice"])

            logger.debug("price_fetched", symbol=asset.symbol, price=str(price))

            return price

        except Exception as e:
            logger.error("get_current_price_failed", symbol=asset.symbol, error=str(e))
            raise BybitConnectionError(f"Failed to get current price: {e}") from e

    def is_connected(self) -> bool:
        """Check if connected to Bybit.

        Returns:
            True if connected, False otherwise
        """
        return self._connected

    # Private methods

    async def _check_request_rate_limit(self) -> None:
        """Check if request rate limit is exceeded.

        Bybit allows 120 requests per minute.
        This method logs warnings when approaching limit and raises error when exceeded.

        Raises:
            BybitRateLimitError: If rate limit would be exceeded
        """
        now = time.time()
        cutoff = now - 60  # 60 seconds ago

        # Remove old timestamps
        self._request_timestamps = [ts for ts in self._request_timestamps if ts > cutoff]

        # Check if we're at limit
        if len(self._request_timestamps) >= self.REQUESTS_PER_MINUTE:
            logger.error(
                "bybit_rate_limit_exceeded", requests_in_window=len(self._request_timestamps)
            )
            raise BybitRateLimitError(
                f"Rate limit exceeded: {len(self._request_timestamps)} requests in last minute"
            )

        # Warn at 80% of limit
        if len(self._request_timestamps) >= int(self.REQUESTS_PER_MINUTE * 0.8):
            logger.warning(
                "bybit_rate_limit_approaching",
                requests_in_window=len(self._request_timestamps),
                limit=self.REQUESTS_PER_MINUTE,
            )

        # Record this request
        self._request_timestamps.append(now)

    async def _check_order_rate_limit(self, symbol: str) -> None:
        """Check if order rate limit is exceeded for a symbol.

        Bybit allows 100 orders per second per symbol.

        Args:
            symbol: Trading symbol

        Raises:
            BybitRateLimitError: If rate limit would be exceeded
        """
        now = time.time()
        cutoff = now - 1  # 1 second ago

        # Initialize symbol tracking if needed
        if symbol not in self._order_timestamps:
            self._order_timestamps[symbol] = []

        # Remove old timestamps
        self._order_timestamps[symbol] = [
            ts for ts in self._order_timestamps[symbol] if ts > cutoff
        ]

        # Check if we're at limit
        if len(self._order_timestamps[symbol]) >= self.ORDERS_PER_SECOND:
            logger.error(
                "bybit_order_rate_limit_exceeded",
                symbol=symbol,
                orders_in_window=len(self._order_timestamps[symbol]),
            )
            raise BybitRateLimitError(
                f"Order rate limit exceeded for {symbol}: "
                f"{len(self._order_timestamps[symbol])} orders in last second"
            )

        # Warn at 80% of limit
        if len(self._order_timestamps[symbol]) >= int(self.ORDERS_PER_SECOND * 0.8):
            logger.warning(
                "bybit_order_rate_limit_approaching",
                symbol=symbol,
                orders_in_window=len(self._order_timestamps[symbol]),
                limit=self.ORDERS_PER_SECOND,
            )

        # Record this order
        self._order_timestamps[symbol].append(now)

    def _get_category(self) -> str:
        """Get Bybit category for current market type.

        Returns:
            Category string
        """
        if self.market_type == "spot":
            return "spot"
        elif self.market_type == "linear":
            return "linear"
        elif self.market_type == "inverse":
            return "inverse"
        else:
            return "linear"  # Default

    def _map_order_type(self, order_type: str) -> str:
        """Map RustyBT order type to Bybit order type.

        Args:
            order_type: RustyBT order type

        Returns:
            Bybit order type

        Raises:
            ValueError: If order type is not supported
        """
        order_type_map = {
            "market": "Market",
            "limit": "Limit",
        }

        if order_type not in order_type_map:
            raise ValueError(
                f"Unsupported order type: {order_type}. "
                f"Supported types: {list(order_type_map.keys())}"
            )

        return order_type_map[order_type]

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
                symbol=bar.symbol,
                queue_size=self._market_data_queue.qsize(),
            )
