"""Binance broker adapter for live trading.

This module provides integration with Binance exchange for live trading,
supporting both spot and futures markets.
"""

import asyncio
import hashlib
import hmac
import time
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

import aiohttp
import structlog

from rustybt.assets import Asset
from rustybt.live.brokers.base import BrokerAdapter
from rustybt.live.streaming.binance_stream import BinanceWebSocketAdapter
from rustybt.live.streaming.models import StreamConfig, TickData

logger = structlog.get_logger(__name__)


class BinanceConnectionError(Exception):
    """Binance connection error."""


class BinanceOrderRejectError(Exception):
    """Binance order rejection error."""


class BinanceRateLimitError(Exception):
    """Binance rate limit exceeded error."""


class BinanceMaintenanceError(Exception):
    """Binance exchange under maintenance error."""


class BinanceBrokerAdapter(BrokerAdapter):
    """Binance broker adapter.

    Integrates with Binance exchange for live trading via REST API and WebSocket.
    Supports spot and futures markets with comprehensive order types.

    Supported Order Types:
        - MARKET: Market order
        - LIMIT: Limit order
        - STOP_LOSS: Stop-loss order
        - STOP_LOSS_LIMIT: Stop-loss limit order
        - TAKE_PROFIT: Take-profit order
        - TAKE_PROFIT_LIMIT: Take-profit limit order

    Rate Limits:
        - REST API: 1200 requests/minute (weight-based)
        - Order placement: 100 orders/10 seconds per symbol

    Error Codes:
        - -1021: Timestamp out of sync
        - -1022: Signature invalid
        - -2010: Insufficient balance
        - -2011: Order would trigger immediately
    """

    # API endpoints
    SPOT_BASE_URL = "https://api.binance.com"
    FUTURES_BASE_URL = "https://fapi.binance.com"
    TESTNET_SPOT_URL = "https://testnet.binance.vision"
    TESTNET_FUTURES_URL = "https://testnet.binancefuture.com"

    # Rate limiting
    REQUESTS_PER_MINUTE = 1200
    ORDERS_PER_10_SECONDS = 100

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        market_type: str = "spot",
        testnet: bool = False,
        stream_config: StreamConfig | None = None,
    ) -> None:
        """Initialize Binance broker adapter.

        Args:
            api_key: Binance API key
            api_secret: Binance API secret
            market_type: Market type ('spot' or 'futures')
            testnet: Use testnet if True
            stream_config: WebSocket streaming configuration

        Raises:
            ValueError: If market_type is invalid
        """
        if market_type not in ("spot", "futures"):
            raise ValueError(f"Invalid market_type: {market_type}, must be 'spot' or 'futures'")

        self.api_key = api_key
        self.api_secret = api_secret
        self.market_type = market_type
        self.testnet = testnet

        # Set base URL
        if testnet:
            self.base_url = (
                self.TESTNET_SPOT_URL if market_type == "spot" else self.TESTNET_FUTURES_URL
            )
        else:
            self.base_url = self.SPOT_BASE_URL if market_type == "spot" else self.FUTURES_BASE_URL

        # WebSocket adapter
        self.ws_adapter = BinanceWebSocketAdapter(
            market_type=market_type,
            config=stream_config,
            on_tick=self._on_tick,
        )

        # HTTP session
        self._session: aiohttp.ClientSession | None = None
        self._connected = False
        self._market_data_queue: asyncio.Queue[dict] = asyncio.Queue()

        # Rate limiting
        self._request_timestamps: list[float] = []
        self._order_timestamps: dict[str, list[float]] = {}

        logger.info(
            "binance_adapter_initialized",
            market_type=market_type,
            testnet=testnet,
            base_url=self.base_url,
        )

    async def connect(self) -> None:
        """Establish connection to Binance.

        Raises:
            BinanceConnectionError: If connection fails
        """
        if self._connected:
            logger.warning("already_connected")
            return

        logger.info("connecting_to_binance", base_url=self.base_url)

        try:
            # Create HTTP session
            self._session = aiohttp.ClientSession()

            # Test API connectivity
            await self._test_connectivity()

            # Connect WebSocket
            await self.ws_adapter.connect()

            self._connected = True
            logger.info("connected_to_binance", market_type=self.market_type)

        except Exception as e:
            self._connected = False
            if self._session:
                await self._session.close()
                self._session = None
            logger.error("connection_failed", error=str(e))
            raise BinanceConnectionError(f"Failed to connect to Binance: {e}") from e

    async def disconnect(self) -> None:
        """Disconnect from Binance."""
        if not self._connected:
            logger.warning("not_connected")
            return

        logger.info("disconnecting_from_binance")

        # Disconnect WebSocket
        await self.ws_adapter.disconnect()

        # Close HTTP session
        if self._session:
            await self._session.close()
            self._session = None

        self._connected = False
        logger.info("disconnected_from_binance")

    async def submit_order(
        self,
        asset: Asset,
        amount: Decimal,
        order_type: str,
        limit_price: Decimal | None = None,
        stop_price: Decimal | None = None,
        oco_params: dict[str, Decimal] | None = None,
        iceberg_qty: Decimal | None = None,
    ) -> str:
        """Submit order to Binance.

        Args:
            asset: Asset to trade
            amount: Order quantity (positive=buy, negative=sell)
            order_type: Order type ('market', 'limit', 'stop', 'stop-limit')
            limit_price: Limit price for limit/stop-limit orders
            stop_price: Stop price for stop/stop-limit orders
            oco_params: OCO order params {'stop_price': Decimal, 'stop_limit_price': Decimal, 'limit_price': Decimal}
            iceberg_qty: Iceberg order visible quantity (must be >= minQty and <= total quantity)

        Returns:
            Binance order ID (for OCO orders, returns list client order ID)

        Raises:
            BinanceOrderRejectError: If order is rejected
            BinanceRateLimitError: If rate limit exceeded
            ValueError: If parameters are invalid

        Examples:
            # OCO order (One-Cancels-Other)
            await adapter.submit_order(
                asset=btc,
                amount=Decimal("0.1"),
                order_type="oco",
                oco_params={
                    'limit_price': Decimal("50000"),  # Take-profit limit price
                    'stop_price': Decimal("48000"),   # Stop-loss trigger price
                    'stop_limit_price': Decimal("47900")  # Stop-limit sell price
                }
            )

            # Iceberg order (partial visibility)
            await adapter.submit_order(
                asset=btc,
                amount=Decimal("1.0"),
                order_type="limit",
                limit_price=Decimal("50000"),
                iceberg_qty=Decimal("0.1")  # Show only 0.1 BTC at a time
            )
        """
        if not self._connected:
            raise BinanceConnectionError("Not connected to Binance")

        # Validate parameters
        if amount == 0:
            raise ValueError("Order amount cannot be zero")

        # Determine side
        side = "BUY" if amount > 0 else "SELL"
        quantity = abs(amount)

        # Check rate limits
        await self._check_order_rate_limit(asset.symbol)

        # Handle OCO orders
        if oco_params is not None:
            return await self._submit_oco_order(asset, side, quantity, oco_params)

        # Map order type
        binance_order_type = self._map_order_type(order_type)

        # Build order params
        params = {
            "symbol": asset.symbol,
            "side": side,
            "type": binance_order_type,
            "quantity": str(quantity),
        }

        # Add price parameters based on order type
        if binance_order_type in ("LIMIT", "STOP_LOSS_LIMIT", "TAKE_PROFIT_LIMIT"):
            if limit_price is None:
                raise ValueError(f"limit_price required for {order_type} order")
            params["price"] = str(limit_price)
            params["timeInForce"] = "GTC"  # Good-til-cancelled

        if binance_order_type in ("STOP_LOSS", "STOP_LOSS_LIMIT"):
            if stop_price is None:
                raise ValueError(f"stop_price required for {order_type} order")
            params["stopPrice"] = str(stop_price)

        if binance_order_type in ("TAKE_PROFIT", "TAKE_PROFIT_LIMIT"):
            if stop_price is None:
                raise ValueError(f"stop_price required for {order_type} order")
            params["stopPrice"] = str(stop_price)

        # Add Iceberg order params
        if iceberg_qty is not None:
            if binance_order_type != "LIMIT":
                raise ValueError("Iceberg orders only supported for LIMIT order type")
            if iceberg_qty <= 0 or iceberg_qty > quantity:
                raise ValueError(f"iceberg_qty must be > 0 and <= total quantity ({quantity})")
            params["icebergQty"] = str(iceberg_qty)

        # Submit order
        endpoint = "/fapi/v1/order" if self.market_type == "futures" else "/api/v3/order"

        try:
            response = await self._signed_request("POST", endpoint, params)

            order_id = f"{asset.symbol}:{response['orderId']}"

            logger.info(
                "order_submitted",
                order_id=order_id,
                symbol=asset.symbol,
                side=side,
                order_type=binance_order_type,
                quantity=str(quantity),
                price=str(limit_price) if limit_price else None,
                iceberg_qty=str(iceberg_qty) if iceberg_qty else None,
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
            broker_order_id: Binance order ID

        Raises:
            BinanceOrderRejectError: If cancellation fails
        """
        if not self._connected:
            raise BinanceConnectionError("Not connected to Binance")

        # Parse order ID to get symbol (Binance requires symbol for cancellation)
        # Note: We need to store symbol mapping or extract from order
        # For now, we'll need the full order ID format: "symbol:orderid"
        if ":" not in broker_order_id:
            raise ValueError("Order ID must be in format 'SYMBOL:ORDERID'")

        symbol, order_id = broker_order_id.split(":", 1)

        params = {
            "symbol": symbol,
            "orderId": order_id,
        }

        endpoint = "/fapi/v1/order" if self.market_type == "futures" else "/api/v3/order"

        try:
            await self._signed_request("DELETE", endpoint, params)

            logger.info("order_cancelled", order_id=broker_order_id, symbol=symbol)

        except Exception as e:
            logger.error("order_cancellation_failed", order_id=broker_order_id, error=str(e))
            raise BinanceOrderRejectError(f"Failed to cancel order {broker_order_id}: {e}") from e

    async def get_account_info(self) -> dict[str, Decimal]:
        """Get account information.

        Returns:
            Dict with keys: 'cash', 'equity', 'buying_power'

        Raises:
            BinanceConnectionError: If request fails
        """
        if not self._connected:
            raise BinanceConnectionError("Not connected to Binance")

        endpoint = "/fapi/v2/account" if self.market_type == "futures" else "/api/v3/account"

        try:
            response = await self._signed_request("GET", endpoint, {})

            if self.market_type == "futures":
                # Futures account
                total_wallet_balance = Decimal(response["totalWalletBalance"])
                available_balance = Decimal(response["availableBalance"])
                unrealized_pnl = Decimal(response["totalUnrealizedProfit"])

                return {
                    "cash": available_balance,
                    "equity": total_wallet_balance + unrealized_pnl,
                    "buying_power": available_balance,  # Simplified
                }
            else:
                # Spot account
                balances = response["balances"]

                # Sum all USDT-equivalent balances (simplified)
                total_cash = Decimal("0")
                for balance in balances:
                    if balance["asset"] == "USDT":
                        total_cash = Decimal(balance["free"])

                return {
                    "cash": total_cash,
                    "equity": total_cash,
                    "buying_power": total_cash,
                }

        except Exception as e:
            logger.error("get_account_info_failed", error=str(e))
            raise BinanceConnectionError(f"Failed to get account info: {e}") from e

    async def get_positions(self) -> list[dict]:
        """Get current positions.

        Returns:
            List of position dicts with keys: 'asset', 'amount', 'entry_price', 'market_value'

        Raises:
            BinanceConnectionError: If request fails
        """
        if not self._connected:
            raise BinanceConnectionError("Not connected to Binance")

        if self.market_type == "spot":
            # Spot market has balances, not positions
            return []

        # Futures positions
        endpoint = "/fapi/v2/positionRisk"

        try:
            response = await self._signed_request("GET", endpoint, {})

            positions = []
            for position_data in response:
                position_amt = Decimal(position_data["positionAmt"])

                # Skip zero positions
                if position_amt == 0:
                    continue

                symbol = position_data["symbol"]
                entry_price = Decimal(position_data["entryPrice"])
                mark_price = Decimal(position_data["markPrice"])
                unrealized_pnl = Decimal(position_data["unRealizedProfit"])

                positions.append(
                    {
                        "symbol": symbol,
                        "amount": position_amt,
                        "entry_price": entry_price,
                        "mark_price": mark_price,
                        "unrealized_pnl": unrealized_pnl,
                        "market_value": position_amt * mark_price,
                    }
                )

            logger.debug("positions_fetched", count=len(positions))

            return positions

        except Exception as e:
            logger.error("get_positions_failed", error=str(e))
            raise BinanceConnectionError(f"Failed to get positions: {e}") from e

    async def get_open_orders(self) -> list[dict]:
        """Get open/pending orders.

        Returns:
            List of order dicts

        Raises:
            BinanceConnectionError: If request fails
        """
        if not self._connected:
            raise BinanceConnectionError("Not connected to Binance")

        endpoint = "/fapi/v1/openOrders" if self.market_type == "futures" else "/api/v3/openOrders"

        try:
            response = await self._signed_request("GET", endpoint, {})

            orders = []
            for order_data in response:
                orders.append(
                    {
                        "order_id": f"{order_data['symbol']}:{order_data['orderId']}",
                        "symbol": order_data["symbol"],
                        "side": order_data["side"],
                        "type": order_data["type"],
                        "quantity": Decimal(order_data["origQty"]),
                        "price": Decimal(order_data["price"]) if order_data["price"] else None,
                        "status": order_data["status"],
                    }
                )

            return orders

        except Exception as e:
            logger.error("get_open_orders_failed", error=str(e))
            raise BinanceConnectionError(f"Failed to get open orders: {e}") from e

    async def subscribe_market_data(self, assets: list[Asset]) -> None:
        """Subscribe to real-time market data.

        Args:
            assets: List of assets to subscribe

        Raises:
            BinanceConnectionError: If subscription fails
        """
        if not self._connected:
            raise BinanceConnectionError("Not connected to Binance")

        symbols = [asset.symbol for asset in assets]

        try:
            # Subscribe to kline stream for price updates
            await self.ws_adapter.subscribe(symbols, ["kline_1m"])

            logger.info("market_data_subscribed", symbols=symbols)

        except Exception as e:
            logger.error("market_data_subscription_failed", symbols=symbols, error=str(e))
            raise BinanceConnectionError(f"Failed to subscribe to market data: {e}") from e

    async def unsubscribe_market_data(self, assets: list[Asset]) -> None:
        """Unsubscribe from market data.

        Args:
            assets: List of assets to unsubscribe

        Raises:
            BinanceConnectionError: If unsubscribe fails
        """
        if not self._connected:
            raise BinanceConnectionError("Not connected to Binance")

        symbols = [asset.symbol for asset in assets]

        try:
            await self.ws_adapter.unsubscribe(symbols, ["kline_1m"])

            logger.info("market_data_unsubscribed", symbols=symbols)

        except Exception as e:
            logger.error("market_data_unsubscription_failed", symbols=symbols, error=str(e))
            raise BinanceConnectionError(f"Failed to unsubscribe from market data: {e}") from e

    async def get_next_market_data(self) -> dict | None:
        """Get next market data update.

        Returns:
            Market data dict or None if queue is empty

        Raises:
            BinanceConnectionError: If data fetch fails
        """
        try:
            # Non-blocking get from queue
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
            BinanceConnectionError: If price fetch fails
        """
        if not self._connected:
            raise BinanceConnectionError("Not connected to Binance")

        endpoint = (
            "/fapi/v1/ticker/price" if self.market_type == "futures" else "/api/v3/ticker/price"
        )

        params = {"symbol": asset.symbol}

        try:
            response = await self._unsigned_request("GET", endpoint, params)
            price = Decimal(response["price"])

            logger.debug("price_fetched", symbol=asset.symbol, price=str(price))

            return price

        except Exception as e:
            logger.error("get_current_price_failed", symbol=asset.symbol, error=str(e))
            raise BinanceConnectionError(f"Failed to get current price: {e}") from e

    def is_connected(self) -> bool:
        """Check if connected to Binance.

        Returns:
            True if connected, False otherwise
        """
        return self._connected

    # Private methods

    def _on_tick(self, tick: TickData) -> None:
        """Handle tick data from WebSocket.

        Args:
            tick: Tick data
        """
        # Convert TickData to market data dict
        market_data = {
            "symbol": tick.symbol,
            "price": tick.price,
            "volume": tick.volume,
            "timestamp": tick.timestamp,
            "side": tick.side.value,
        }

        # Add to queue (non-blocking)
        try:
            self._market_data_queue.put_nowait(market_data)
        except asyncio.QueueFull:
            logger.warning("market_data_queue_full", symbol=tick.symbol)

    async def _test_connectivity(self) -> None:
        """Test API connectivity.

        Raises:
            BinanceConnectionError: If connectivity test fails
        """
        endpoint = "/fapi/v1/ping" if self.market_type == "futures" else "/api/v3/ping"

        try:
            await self._unsigned_request("GET", endpoint, {})
            logger.info("connectivity_test_passed")
        except Exception as e:
            logger.error("connectivity_test_failed", error=str(e))
            raise BinanceConnectionError(f"Connectivity test failed: {e}") from e

    async def _unsigned_request(
        self, method: str, endpoint: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Make unsigned API request.

        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Request parameters

        Returns:
            Response JSON

        Raises:
            BinanceConnectionError: If request fails
        """
        if not self._session:
            raise BinanceConnectionError("HTTP session not initialized")

        url = f"{self.base_url}{endpoint}"

        # Check rate limit
        await self._check_request_rate_limit()

        try:
            async with self._session.request(method, url, params=params) as response:
                response_json = await response.json()

                if response.status != 200:
                    error_msg = response_json.get("msg", "Unknown error")
                    error_code = response_json.get("code", -1)

                    # Handle specific errors
                    if error_code == -1003:
                        raise BinanceRateLimitError(f"Rate limit exceeded: {error_msg}")
                    elif response.status == 503:
                        raise BinanceMaintenanceError(f"Exchange under maintenance: {error_msg}")
                    else:
                        raise BinanceConnectionError(f"API error {error_code}: {error_msg}")

                return response_json

        except aiohttp.ClientError as e:
            logger.error("http_request_failed", method=method, endpoint=endpoint, error=str(e))
            raise BinanceConnectionError(f"HTTP request failed: {e}") from e

    async def _signed_request(
        self, method: str, endpoint: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Make signed API request.

        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Request parameters

        Returns:
            Response JSON

        Raises:
            BinanceConnectionError: If request fails
        """
        if not self._session:
            raise BinanceConnectionError("HTTP session not initialized")

        # Add timestamp
        params["timestamp"] = int(time.time() * 1000)

        # Generate signature
        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode("utf-8"), query_string.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        params["signature"] = signature

        # Add API key header
        headers = {
            "X-MBX-APIKEY": self.api_key,
        }

        url = f"{self.base_url}{endpoint}"

        # Check rate limit
        await self._check_request_rate_limit()

        try:
            async with self._session.request(
                method,
                url,
                params=params if method == "GET" else None,
                data=params if method != "GET" else None,
                headers=headers,
            ) as response:
                response_json = await response.json()

                if response.status != 200:
                    error_msg = response_json.get("msg", "Unknown error")
                    error_code = response_json.get("code", -1)

                    # Handle specific errors
                    if error_code == -1003:
                        raise BinanceRateLimitError(f"Rate limit exceeded: {error_msg}")
                    elif error_code == -1021:
                        raise BinanceConnectionError(f"Timestamp out of sync: {error_msg}")
                    elif error_code == -1022:
                        raise BinanceConnectionError(f"Invalid signature: {error_msg}")
                    elif error_code == -2010:
                        raise BinanceOrderRejectError(f"Insufficient balance: {error_msg}")
                    elif error_code == -2011:
                        raise BinanceOrderRejectError(
                            f"Order would trigger immediately: {error_msg}"
                        )
                    elif response.status == 503:
                        raise BinanceMaintenanceError(f"Exchange under maintenance: {error_msg}")
                    else:
                        raise BinanceConnectionError(f"API error {error_code}: {error_msg}")

                return response_json

        except aiohttp.ClientError as e:
            logger.error("http_request_failed", method=method, endpoint=endpoint, error=str(e))
            raise BinanceConnectionError(f"HTTP request failed: {e}") from e

    async def _check_request_rate_limit(self) -> None:
        """Check and enforce request rate limit.

        Raises:
            BinanceRateLimitError: If rate limit would be exceeded
        """
        current_time = time.time()

        # Remove timestamps older than 1 minute
        self._request_timestamps = [ts for ts in self._request_timestamps if current_time - ts < 60]

        # Check if we're at limit
        if len(self._request_timestamps) >= self.REQUESTS_PER_MINUTE:
            wait_time = 60 - (current_time - self._request_timestamps[0])
            logger.warning(
                "rate_limit_approaching",
                requests_in_window=len(self._request_timestamps),
                wait_time=wait_time,
            )
            await asyncio.sleep(wait_time)

        # Record request
        self._request_timestamps.append(current_time)

    async def _check_order_rate_limit(self, symbol: str) -> None:
        """Check and enforce order rate limit per symbol.

        Args:
            symbol: Trading symbol

        Raises:
            BinanceRateLimitError: If rate limit would be exceeded
        """
        current_time = time.time()

        # Initialize symbol tracking
        if symbol not in self._order_timestamps:
            self._order_timestamps[symbol] = []

        # Remove timestamps older than 10 seconds
        self._order_timestamps[symbol] = [
            ts for ts in self._order_timestamps[symbol] if current_time - ts < 10
        ]

        # Check if we're at limit
        if len(self._order_timestamps[symbol]) >= self.ORDERS_PER_10_SECONDS:
            wait_time = 10 - (current_time - self._order_timestamps[symbol][0])
            logger.warning(
                "order_rate_limit_approaching",
                symbol=symbol,
                orders_in_window=len(self._order_timestamps[symbol]),
                wait_time=wait_time,
            )
            await asyncio.sleep(wait_time)

        # Record order
        self._order_timestamps[symbol].append(current_time)

    def _map_order_type(self, order_type: str) -> str:
        """Map RustyBT order type to Binance order type.

        Args:
            order_type: RustyBT order type

        Returns:
            Binance order type

        Raises:
            ValueError: If order type is not supported
        """
        order_type_map = {
            "market": "MARKET",
            "limit": "LIMIT",
            "stop": "STOP_LOSS",
            "stop-limit": "STOP_LOSS_LIMIT",
        }

        if order_type not in order_type_map:
            raise ValueError(
                f"Unsupported order type: {order_type}. "
                f"Supported types: {list(order_type_map.keys())}"
            )

        return order_type_map[order_type]

    async def _submit_oco_order(
        self,
        asset: Asset,
        side: str,
        quantity: Decimal,
        oco_params: dict[str, Decimal],
    ) -> str:
        """Submit OCO (One-Cancels-Other) order to Binance.

        OCO orders consist of two orders:
        1. Limit order (take-profit)
        2. Stop-loss order (stop-limit)

        Args:
            asset: Asset to trade
            side: Order side ('BUY' or 'SELL')
            quantity: Order quantity
            oco_params: OCO params with 'limit_price', 'stop_price', 'stop_limit_price'

        Returns:
            Binance list client order ID

        Raises:
            ValueError: If OCO params are invalid
            BinanceOrderRejectError: If order is rejected
        """
        # Validate OCO params
        required_keys = {"limit_price", "stop_price", "stop_limit_price"}
        if not all(key in oco_params for key in required_keys):
            raise ValueError(f"OCO params must include: {required_keys}")

        limit_price = oco_params["limit_price"]
        stop_price = oco_params["stop_price"]
        stop_limit_price = oco_params["stop_limit_price"]

        # Build OCO order params
        params = {
            "symbol": asset.symbol,
            "side": side,
            "quantity": str(quantity),
            "price": str(limit_price),  # Limit order price (take-profit)
            "stopPrice": str(stop_price),  # Stop trigger price
            "stopLimitPrice": str(stop_limit_price),  # Stop-limit order price
            "stopLimitTimeInForce": "GTC",  # Good-til-cancelled
        }

        # Submit OCO order
        endpoint = "/api/v3/order/oco"  # OCO only supported on spot

        try:
            response = await self._signed_request("POST", endpoint, params)

            # OCO returns a list client order ID
            list_client_order_id = response.get("listClientOrderId", "unknown")
            order_id = f"{asset.symbol}:{list_client_order_id}"

            logger.info(
                "oco_order_submitted",
                order_id=order_id,
                symbol=asset.symbol,
                side=side,
                quantity=str(quantity),
                limit_price=str(limit_price),
                stop_price=str(stop_price),
                stop_limit_price=str(stop_limit_price),
            )

            return order_id

        except Exception as e:
            logger.error(
                "oco_order_submission_failed",
                symbol=asset.symbol,
                side=side,
                error=str(e),
            )
            raise BinanceOrderRejectError(f"OCO order rejected: {e}") from e
