"""Interactive Brokers adapter using ib_async library.

This module provides integration with Interactive Brokers TWS/IB Gateway for live trading.
Uses ib_async library for Pythonic async interface.

Decision Rationale (ib_insync vs custom TWS API):
- ib_insync provides Pythonic async/await interface (integrates seamlessly with LiveTradingEngine)
- Active maintenance and comprehensive documentation
- Proven in production environments
- Handles connection management, reconnection, and event handling
- Custom TWS API would require significant development effort with marginal performance gains
- ib_insync wraps IB's C++ API efficiently with minimal overhead

Setup Requirements:
- TWS (Trader Workstation) or IB Gateway must be running
- API connections enabled in TWS settings
- Socket port configured:
  - TWS Live: 7497
  - TWS Paper: 7496
  - Gateway Live: 4001
  - Gateway Paper: 4002

Note: Uses ib_insync library (not ib_async) for Pythonic async interface.
"""

import asyncio
from decimal import Decimal

import structlog
from ib_insync import IB, Contract, Future, Order, Stock, Trade

from rustybt.assets import Asset, Equity
from rustybt.assets import Future as RustyBTFuture
from rustybt.live.brokers.base import BrokerAdapter

logger = structlog.get_logger(__name__)


class IBConnectionError(Exception):
    """IB connection error."""

    pass


class IBOrderRejectError(Exception):
    """IB order rejected error."""

    pass


class IBBrokerAdapter(BrokerAdapter):
    """Interactive Brokers broker adapter.

    Connects to TWS/IB Gateway and provides order execution, position queries,
    and real-time market data for stocks, futures, options, and forex.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7496,
        client_id: int = 1,
        auto_reconnect: bool = True,
    ):
        """Initialize IB adapter.

        Args:
            host: TWS/Gateway host (default: localhost)
            port: Socket port (7496=TWS paper, 7497=TWS live, 4002=Gateway paper, 4001=Gateway live)
            client_id: Unique client ID (1-32)
            auto_reconnect: Enable auto-reconnection on disconnect
        """
        self._host = host
        self._port = port
        self._client_id = client_id
        self._auto_reconnect = auto_reconnect

        self._ib: IB | None = None
        self._connected = False

        # Order tracking
        self._order_id_counter = 1
        self._pending_orders: dict[int, Trade] = {}  # order_id -> Trade

        # Market data subscriptions
        self._subscribed_contracts: dict[Asset, Contract] = {}
        self._market_data_queue: asyncio.Queue = asyncio.Queue()

        # Reconnection settings
        self._reconnect_delay = 1.0  # Start at 1 second
        self._max_reconnect_delay = 16.0

    async def connect(self) -> None:
        """Establish connection to IB TWS/Gateway.

        Raises:
            IBConnectionError: If connection fails
        """
        try:
            self._ib = IB()

            logger.info(
                "connecting_to_ib",
                host=self._host,
                port=self._port,
                client_id=self._client_id,
            )

            await self._ib.connectAsync(
                host=self._host,
                port=self._port,
                clientId=self._client_id,
                timeout=30,
            )

            self._connected = True
            self._reconnect_delay = 1.0  # Reset delay on successful connection

            # Register event handlers
            self._ib.orderStatusEvent += self._on_order_status
            self._ib.execDetailsEvent += self._on_execution
            self._ib.errorEvent += self._on_error
            self._ib.disconnectedEvent += self._on_disconnect

            logger.info("ib_connected", client_id=self._client_id)

        except Exception as e:
            logger.error("ib_connection_failed", error=str(e), host=self._host, port=self._port)
            raise IBConnectionError(
                f"Failed to connect to IB at {self._host}:{self._port}: {e}"
            ) from e

    async def disconnect(self) -> None:
        """Disconnect from IB."""
        if self._ib and self._connected:
            logger.info("disconnecting_from_ib")
            self._ib.disconnect()
            self._connected = False
            logger.info("ib_disconnected")

    async def submit_order(
        self,
        asset: Asset,
        amount: Decimal,
        order_type: str,
        limit_price: Decimal | None = None,
        stop_price: Decimal | None = None,
    ) -> str:
        """Submit order to IB.

        Args:
            asset: Asset to trade
            amount: Order quantity (positive=buy, negative=sell)
            order_type: 'market', 'limit', 'stop', 'stop-limit', 'trailing-stop'
            limit_price: Limit price for limit/stop-limit orders
            stop_price: Stop price for stop/stop-limit orders

        Returns:
            Broker order ID as string

        Raises:
            IBConnectionError: If not connected
            IBOrderRejectError: If order submission fails
        """
        if not self._connected or not self._ib:
            raise IBConnectionError("Not connected to IB")

        try:
            # Create IB contract from asset
            contract = self._create_contract(asset)

            # Create IB order
            ib_order = self._create_order(
                amount=amount,
                order_type=order_type,
                limit_price=limit_price,
                stop_price=stop_price,
            )

            # Place order
            trade = self._ib.placeOrder(contract, ib_order)

            # Store pending order
            self._pending_orders[ib_order.orderId] = trade

            logger.info(
                "order_submitted",
                order_id=ib_order.orderId,
                asset=asset.symbol,
                amount=str(amount),
                order_type=order_type,
            )

            return str(ib_order.orderId)

        except Exception as e:
            logger.error("order_submission_failed", asset=asset.symbol, error=str(e))
            raise IBOrderRejectError(f"Failed to submit order for {asset.symbol}: {e}") from e

    async def cancel_order(self, broker_order_id: str) -> None:
        """Cancel order.

        Args:
            broker_order_id: IB order ID

        Raises:
            IBConnectionError: If not connected
            IBOrderRejectError: If cancellation fails
        """
        if not self._connected or not self._ib:
            raise IBConnectionError("Not connected to IB")

        try:
            order_id = int(broker_order_id)

            if order_id in self._pending_orders:
                trade = self._pending_orders[order_id]
                self._ib.cancelOrder(trade.order)
                logger.info("order_cancelled", order_id=order_id)
            else:
                logger.warning("order_not_found_for_cancellation", order_id=order_id)

        except Exception as e:
            logger.error("order_cancellation_failed", order_id=broker_order_id, error=str(e))
            raise IBOrderRejectError(f"Failed to cancel order {broker_order_id}: {e}") from e

    async def get_account_info(self) -> dict[str, Decimal]:
        """Get account information from IB.

        Returns:
            Dict with keys: 'cash', 'equity', 'buying_power', 'initial_margin', 'maintenance_margin'

        Raises:
            IBConnectionError: If not connected
        """
        if not self._connected or not self._ib:
            raise IBConnectionError("Not connected to IB")

        try:
            # Request account summary
            summary = self._ib.accountSummary()

            # Parse account values
            account_info = {}
            for item in summary:
                tag = item.tag
                value = item.value

                if tag == "TotalCashValue":
                    account_info["cash"] = Decimal(value)
                elif tag == "NetLiquidation":
                    account_info["equity"] = Decimal(value)
                elif tag == "BuyingPower":
                    account_info["buying_power"] = Decimal(value)
                elif tag == "InitMarginReq":
                    account_info["initial_margin"] = Decimal(value)
                elif tag == "MaintMarginReq":
                    account_info["maintenance_margin"] = Decimal(value)
                elif tag == "GrossPositionValue":
                    account_info["gross_position_value"] = Decimal(value)

            logger.info(
                "account_info_retrieved",
                cash=str(account_info.get("cash", Decimal(0))),
                equity=str(account_info.get("equity", Decimal(0))),
            )

            return account_info

        except Exception as e:
            logger.error("account_info_retrieval_failed", error=str(e))
            raise IBConnectionError(f"Failed to retrieve account info: {e}") from e

    async def get_positions(self) -> list[dict]:
        """Get current positions from IB.

        Returns:
            List of position dicts with keys: 'asset', 'amount', 'cost_basis', 'market_value'

        Raises:
            IBConnectionError: If not connected
        """
        if not self._connected or not self._ib:
            raise IBConnectionError("Not connected to IB")

        try:
            # Request positions
            positions = self._ib.positions()

            position_list = []
            for pos in positions:
                # Convert IB contract to RustyBT asset
                # (simplified - would need AssetFinder in production)
                asset_symbol = pos.contract.symbol

                position_dict = {
                    "symbol": asset_symbol,  # In production, use AssetFinder to get Asset object
                    "amount": Decimal(str(pos.position)),
                    "cost_basis": Decimal(str(pos.avgCost)),
                    "market_value": Decimal(str(pos.position * pos.avgCost)),  # Simplified
                }

                position_list.append(position_dict)

            logger.info("positions_retrieved", count=len(position_list))

            return position_list

        except Exception as e:
            logger.error("position_retrieval_failed", error=str(e))
            raise IBConnectionError(f"Failed to retrieve positions: {e}") from e

    async def get_open_orders(self) -> list[dict]:
        """Get open/pending orders from IB.

        Returns:
            List of order dicts

        Raises:
            IBConnectionError: If not connected
        """
        if not self._connected or not self._ib:
            raise IBConnectionError("Not connected to IB")

        try:
            trades = self._ib.openTrades()

            order_list = []
            for trade in trades:
                order_dict = {
                    "order_id": str(trade.order.orderId),
                    "symbol": trade.contract.symbol,
                    "amount": Decimal(str(trade.order.totalQuantity)),
                    "status": trade.orderStatus.status,
                    "order_type": trade.order.orderType,
                }
                order_list.append(order_dict)

            logger.info("open_orders_retrieved", count=len(order_list))

            return order_list

        except Exception as e:
            logger.error("open_orders_retrieval_failed", error=str(e))
            raise IBConnectionError(f"Failed to retrieve open orders: {e}") from e

    async def subscribe_market_data(self, assets: list[Asset]) -> None:
        """Subscribe to real-time market data.

        Args:
            assets: List of assets to subscribe to

        Raises:
            IBConnectionError: If not connected
        """
        if not self._connected or not self._ib:
            raise IBConnectionError("Not connected to IB")

        try:
            for asset in assets:
                if asset not in self._subscribed_contracts:
                    contract = self._create_contract(asset)

                    # Request market data
                    ticker = self._ib.reqMktData(contract, "", False, False)

                    # Register callback
                    ticker.updateEvent += lambda t, a=asset: self._on_market_data_update(t, a)

                    self._subscribed_contracts[asset] = contract

                    logger.info("market_data_subscribed", asset=asset.symbol)

        except Exception as e:
            logger.error("market_data_subscription_failed", error=str(e))
            raise IBConnectionError(f"Failed to subscribe to market data: {e}") from e

    async def unsubscribe_market_data(self, assets: list[Asset]) -> None:
        """Unsubscribe from market data.

        Args:
            assets: List of assets to unsubscribe from

        Raises:
            IBConnectionError: If not connected
        """
        if not self._connected or not self._ib:
            raise IBConnectionError("Not connected to IB")

        try:
            for asset in assets:
                if asset in self._subscribed_contracts:
                    contract = self._subscribed_contracts[asset]
                    self._ib.cancelMktData(contract)
                    del self._subscribed_contracts[asset]

                    logger.info("market_data_unsubscribed", asset=asset.symbol)

        except Exception as e:
            logger.error("market_data_unsubscription_failed", error=str(e))
            raise IBConnectionError(f"Failed to unsubscribe from market data: {e}") from e

    async def get_next_market_data(self) -> dict | None:
        """Get next market data update (blocking).

        Returns:
            Dict with market data or None if queue is empty
        """
        try:
            # Non-blocking get
            return self._market_data_queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def get_current_price(self, asset: Asset) -> Decimal:
        """Get current price for asset.

        Args:
            asset: Asset to get price for

        Returns:
            Current price

        Raises:
            IBConnectionError: If not connected
        """
        if not self._connected or not self._ib:
            raise IBConnectionError("Not connected to IB")

        try:
            contract = self._create_contract(asset)

            # Request snapshot
            ticker = self._ib.reqMktData(contract, "", True, False)

            # Wait for ticker to update
            await asyncio.sleep(1)

            # Get last price
            if ticker.last and ticker.last > 0:
                price = Decimal(str(ticker.last))
            elif ticker.close and ticker.close > 0:
                price = Decimal(str(ticker.close))
            else:
                raise IBConnectionError(f"No price available for {asset.symbol}")

            # Cancel subscription
            self._ib.cancelMktData(contract)

            logger.info("current_price_retrieved", asset=asset.symbol, price=str(price))

            return price

        except Exception as e:
            logger.error("current_price_retrieval_failed", asset=asset.symbol, error=str(e))
            raise IBConnectionError(f"Failed to get current price for {asset.symbol}: {e}") from e

    def is_connected(self) -> bool:
        """Check if connected to IB.

        Returns:
            True if connected, False otherwise
        """
        return self._connected and self._ib is not None and self._ib.isConnected()

    # ========== Helper Methods ==========

    def _create_contract(self, asset: Asset) -> Contract:
        """Create IB contract from RustyBT asset.

        Args:
            asset: RustyBT asset

        Returns:
            IB Contract object
        """
        # Stock (Equity)
        if isinstance(asset, Equity):
            return Stock(
                symbol=asset.symbol,
                exchange="SMART",
                currency="USD",
            )

        # Future
        elif isinstance(asset, RustyBTFuture):
            # Extract contract month from asset (simplified)
            return Future(
                symbol=asset.root_symbol,
                lastTradeDateOrContractMonth=asset.notice_date.strftime("%Y%m"),
                exchange=asset.exchange,
                currency="USD",
            )

        # Default to Stock for unknown types
        else:
            logger.warning(
                "unknown_asset_type_defaulting_to_stock",
                asset_type=type(asset).__name__,
                symbol=asset.symbol,
            )
            return Stock(
                symbol=asset.symbol,
                exchange="SMART",
                currency="USD",
            )

    def _create_order(
        self,
        amount: Decimal,
        order_type: str,
        limit_price: Decimal | None = None,
        stop_price: Decimal | None = None,
    ) -> Order:
        """Create IB order from parameters.

        Args:
            amount: Order quantity (positive=buy, negative=sell)
            order_type: Order type string
            limit_price: Limit price (for limit orders)
            stop_price: Stop price (for stop orders)

        Returns:
            IB Order object
        """
        # Determine action (BUY/SELL)
        action = "BUY" if amount > 0 else "SELL"
        quantity = abs(amount)

        # Get next order ID
        order_id = self._get_next_order_id()

        # Create order based on type
        order = Order()
        order.orderId = order_id
        order.action = action
        order.totalQuantity = float(quantity)

        if order_type.lower() == "market":
            order.orderType = "MKT"

        elif order_type.lower() == "limit":
            order.orderType = "LMT"
            if limit_price is None:
                raise ValueError("limit_price required for limit orders")
            order.lmtPrice = float(limit_price)

        elif order_type.lower() == "stop":
            order.orderType = "STP"
            if stop_price is None:
                raise ValueError("stop_price required for stop orders")
            order.auxPrice = float(stop_price)

        elif order_type.lower() == "stop-limit":
            order.orderType = "STP LMT"
            if limit_price is None or stop_price is None:
                raise ValueError("limit_price and stop_price required for stop-limit orders")
            order.lmtPrice = float(limit_price)
            order.auxPrice = float(stop_price)

        elif order_type.lower() == "trailing-stop":
            order.orderType = "TRAIL"
            if stop_price is None:
                raise ValueError("stop_price (trailing amount) required for trailing-stop orders")
            order.auxPrice = float(stop_price)

        else:
            raise ValueError(f"Unsupported order type: {order_type}")

        return order

    def _get_next_order_id(self) -> int:
        """Get next available order ID.

        Returns:
            Order ID
        """
        if self._ib and self._ib.client.getReqId():
            return self._ib.client.getReqId()
        else:
            order_id = self._order_id_counter
            self._order_id_counter += 1
            return order_id

    # ========== Event Handlers ==========

    def _on_order_status(self, trade: Trade) -> None:
        """Handle order status updates."""
        logger.info(
            "order_status_update",
            order_id=trade.order.orderId,
            status=trade.orderStatus.status,
            filled=trade.orderStatus.filled,
            remaining=trade.orderStatus.remaining,
        )

    def _on_execution(self, trade: Trade, fill) -> None:
        """Handle order execution (fill)."""
        logger.info(
            "order_filled",
            order_id=trade.order.orderId,
            fill_price=str(fill.execution.price),
            fill_quantity=str(fill.execution.shares),
            commission=str(fill.commissionReport.commission if fill.commissionReport else 0),
        )

    def _on_error(self, reqId: int, errorCode: int, errorString: str, contract) -> None:
        """Handle IB errors."""
        logger.error(
            "ib_error",
            req_id=reqId,
            error_code=errorCode,
            error_string=errorString,
            contract=contract.symbol if contract else None,
        )

        # Handle specific error codes
        if errorCode == 502:
            logger.error("ib_connection_lost", error="Cannot connect to TWS")
        elif errorCode == 103:
            logger.error("ib_duplicate_order_id", error="Duplicate order ID")
        elif errorCode == 201:
            logger.error("ib_order_rejected", error=errorString)

    def _on_disconnect(self) -> None:
        """Handle disconnection event."""
        logger.warning("ib_disconnected")
        self._connected = False

        # Auto-reconnect if enabled
        if self._auto_reconnect:
            asyncio.create_task(self._reconnect())

    async def _reconnect(self) -> None:
        """Attempt to reconnect to IB with exponential backoff."""
        logger.info("attempting_ib_reconnection", delay=self._reconnect_delay)

        await asyncio.sleep(self._reconnect_delay)

        try:
            await self.connect()
            logger.info("ib_reconnection_successful")

        except Exception as e:
            logger.error("ib_reconnection_failed", error=str(e))

            # Increase delay with exponential backoff
            self._reconnect_delay = min(self._reconnect_delay * 2, self._max_reconnect_delay)

            # Retry
            if self._auto_reconnect:
                asyncio.create_task(self._reconnect())

    def _on_market_data_update(self, ticker, asset: Asset) -> None:
        """Handle market data updates."""
        if ticker.last and ticker.last > 0:
            data = {
                "asset": asset,
                "price": Decimal(str(ticker.last)),
                "bid": Decimal(str(ticker.bid)) if ticker.bid and ticker.bid > 0 else None,
                "ask": Decimal(str(ticker.ask)) if ticker.ask and ticker.ask > 0 else None,
                "volume": int(ticker.volume) if ticker.volume else 0,
                "timestamp": ticker.time,
            }

            # Add to queue
            self._market_data_queue.put_nowait(data)
