#!/usr/bin/env python
#
# Copyright 2025 RustyBT Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Example: Creating a Custom Broker Adapter

This example demonstrates how to create a custom broker adapter for RustyBT
that interfaces with a proprietary or custom trading system.

Key Concepts Demonstrated:
- Inheriting from BrokerAdapter base class
- Implementing required abstract methods
- Order management and tracking
- Position reconciliation
- Market data integration
- Error handling and retry logic

Usage:
    python examples/custom_broker_adapter.py
"""

import asyncio
import random
import uuid
from decimal import Decimal, getcontext

import pandas as pd
import structlog

from rustybt.assets import Asset, Equity
from rustybt.exceptions import (
    BrokerError,
    DataNotFoundError,
    InsufficientFundsError,
    OrderNotFoundError,
)
from rustybt.live.brokers.base import BrokerAdapter

# Set decimal precision
getcontext().prec = 28

logger = structlog.get_logger()


class CustomBrokerAdapter(BrokerAdapter):
    """Custom broker adapter template.

    This adapter demonstrates a complete implementation of the BrokerAdapter
    interface for connecting to a custom trading system or broker API.

    Adapt this template for your broker by:
    1. Replacing mock API calls with real API client
    2. Implementing proper authentication
    3. Adding broker-specific order types
    4. Handling broker-specific error codes
    5. Implementing WebSocket streaming (optional)

    Example:
        >>> broker = CustomBrokerAdapter(
        ...     api_url="https://api.mybroker.com",
        ...     api_key="your_api_key",
        ...     api_secret="your_api_secret"
        ... )
        >>> await broker.connect()
        >>> order_id = await broker.submit_order(
        ...     asset=asset,
        ...     amount=Decimal("100"),
        ...     order_type="market"
        ... )
    """

    def __init__(
        self, api_url: str, api_key: str, api_secret: str, testnet: bool = True, timeout: int = 30
    ):
        """Initialize custom broker adapter.

        Args:
            api_url: Broker API base URL
            api_key: API authentication key
            api_secret: API secret key
            testnet: Use testnet/sandbox mode
            timeout: Request timeout in seconds
        """
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.timeout = timeout

        # Connection state
        self._connected = False

        # Order tracking
        self._orders: dict[str, dict] = {}
        self._order_id_map: dict[str, str] = {}  # internal_id -> broker_id

        # Position tracking
        self._positions: dict[str, dict] = {}

        # Account state
        self._account = {
            "cash": Decimal("100000"),
            "equity": Decimal("100000"),
            "buying_power": Decimal("100000"),
            "margin_used": Decimal("0"),
        }

        # Market data queue (for mock data)
        self._market_data_queue = asyncio.Queue()

        logger.info("custom_broker_initialized", api_url=self.api_url, testnet=self.testnet)

    async def connect(self) -> None:
        """Establish connection to broker.

        This method should:
        1. Authenticate with broker API
        2. Verify API credentials
        3. Initialize WebSocket connections (if applicable)
        4. Load initial account state

        Raises:
            BrokerConnectionError: If connection fails
        """
        logger.info("connecting_to_broker")

        try:
            # TODO: Replace with real API authentication
            # Example:
            # response = await self._api_client.authenticate(
            #     api_key=self.api_key,
            #     api_secret=self.api_secret
            # )
            # self._session_token = response['token']

            # Simulate connection delay
            await asyncio.sleep(0.5)

            # Load initial account state
            await self._load_account_state()

            # Load existing positions
            await self._load_positions()

            self._connected = True
            logger.info("broker_connected", account_cash=float(self._account["cash"]))

        except Exception as e:
            logger.error("connection_failed", error=str(e))
            raise BrokerError(f"Failed to connect: {e}", adapter="custom_broker")

    async def disconnect(self) -> None:
        """Disconnect from broker.

        This method should:
        1. Close WebSocket connections
        2. Cancel any pending subscriptions
        3. Clean up resources
        """
        logger.info("disconnecting_from_broker")

        # TODO: Close API connections
        # await self._api_client.close()
        # await self._websocket.close()

        self._connected = False
        logger.info("broker_disconnected")

    async def submit_order(
        self,
        asset: Asset,
        amount: Decimal,
        order_type: str,
        limit_price: Decimal | None = None,
        stop_price: Decimal | None = None,
    ) -> str:
        """Submit order to broker.

        Args:
            asset: Asset to trade
            amount: Order quantity (positive=buy, negative=sell)
            order_type: 'market', 'limit', 'stop', 'stop-limit'
            limit_price: Limit price for limit/stop-limit orders
            stop_price: Stop price for stop/stop-limit orders

        Returns:
            Broker order ID

        Raises:
            InsufficientFundsError: If insufficient funds
            BrokerError: If order submission fails
        """
        if not self._connected:
            raise BrokerError("Not connected to broker", adapter="custom_broker")

        logger.info(
            "submitting_order", asset=asset.symbol, amount=float(amount), order_type=order_type
        )

        # Validate order
        await self._validate_order(asset, amount, order_type)

        # Generate internal order ID
        internal_id = str(uuid.uuid4())

        try:
            # TODO: Replace with real API call
            # Example:
            # response = await self._api_client.submit_order(
            #     symbol=asset.symbol,
            #     side='buy' if amount > 0 else 'sell',
            #     quantity=abs(float(amount)),
            #     order_type=order_type,
            #     limit_price=float(limit_price) if limit_price else None,
            #     stop_price=float(stop_price) if stop_price else None
            # )
            # broker_order_id = response['order_id']

            # Simulate API call
            await asyncio.sleep(0.1)
            broker_order_id = f"ORD_{random.randint(100000, 999999)}"

            # Store order
            self._orders[internal_id] = {
                "broker_order_id": broker_order_id,
                "asset": asset,
                "amount": amount,
                "order_type": order_type,
                "status": "open",
                "filled": Decimal("0"),
                "limit_price": limit_price,
                "stop_price": stop_price,
                "created_at": pd.Timestamp.now(),
            }

            self._order_id_map[internal_id] = broker_order_id

            logger.info("order_submitted", internal_id=internal_id, broker_order_id=broker_order_id)

            return broker_order_id

        except Exception as e:
            logger.error("order_submission_failed", error=str(e))
            raise BrokerError(f"Order submission failed: {e}", adapter="custom_broker")

    async def cancel_order(self, broker_order_id: str) -> None:
        """Cancel order.

        Args:
            broker_order_id: Broker's order ID

        Raises:
            OrderNotFoundError: If order doesn't exist
            BrokerError: If cancellation fails
        """
        logger.info("cancelling_order", broker_order_id=broker_order_id)

        # Find internal order ID
        internal_id = None
        for iid, bid in self._order_id_map.items():
            if bid == broker_order_id:
                internal_id = iid
                break

        if not internal_id or internal_id not in self._orders:
            raise OrderNotFoundError(f"Order {broker_order_id} not found")

        try:
            # TODO: Replace with real API call
            # await self._api_client.cancel_order(broker_order_id)

            # Simulate cancellation
            await asyncio.sleep(0.05)

            # Update order status
            self._orders[internal_id]["status"] = "cancelled"

            logger.info("order_cancelled", broker_order_id=broker_order_id)

        except Exception as e:
            logger.error("cancellation_failed", error=str(e))
            raise BrokerError(f"Order cancellation failed: {e}", adapter="custom_broker")

    async def get_account_info(self) -> dict[str, Decimal]:
        """Get account information.

        Returns:
            Dict with keys: 'cash', 'equity', 'buying_power', 'margin_used'

        Raises:
            BrokerError: If request fails
        """
        if not self._connected:
            raise BrokerError("Not connected to broker", adapter="custom_broker")

        try:
            # TODO: Replace with real API call
            # response = await self._api_client.get_account()
            # return {
            #     'cash': Decimal(str(response['cash'])),
            #     'equity': Decimal(str(response['equity'])),
            #     'buying_power': Decimal(str(response['buying_power'])),
            #     'margin_used': Decimal(str(response['margin_used'])),
            # }

            # Return cached account state
            return self._account.copy()

        except Exception as e:
            logger.error("get_account_failed", error=str(e))
            raise BrokerError(f"Failed to get account info: {e}", adapter="custom_broker")

    async def get_positions(self) -> list[dict]:
        """Get current positions.

        Returns:
            List of position dicts with keys: 'asset', 'amount', 'cost_basis',
            'market_value', 'unrealized_pnl'

        Raises:
            BrokerError: If request fails
        """
        if not self._connected:
            raise BrokerError("Not connected to broker", adapter="custom_broker")

        try:
            # TODO: Replace with real API call
            # response = await self._api_client.get_positions()

            # Convert positions to standard format
            positions = []
            for symbol, pos in self._positions.items():
                positions.append(
                    {
                        "asset": symbol,
                        "amount": pos["amount"],
                        "cost_basis": pos["cost_basis"],
                        "market_value": pos["market_value"],
                        "unrealized_pnl": pos["unrealized_pnl"],
                    }
                )

            return positions

        except Exception as e:
            logger.error("get_positions_failed", error=str(e))
            raise BrokerError(f"Failed to get positions: {e}", adapter="custom_broker")

    async def get_open_orders(self) -> list[dict]:
        """Get open/pending orders from broker.

        Returns:
            List of order dicts with keys: 'order_id', 'asset', 'amount',
            'status', 'order_type', 'limit_price', 'stop_price'

        Raises:
            BrokerError: If request fails
        """
        if not self._connected:
            raise BrokerError("Not connected to broker", adapter="custom_broker")

        try:
            # TODO: Replace with real API call
            # response = await self._api_client.get_open_orders()

            # Filter open orders
            open_orders = []
            for _internal_id, order in self._orders.items():
                if order["status"] in ["open", "partially_filled"]:
                    open_orders.append(
                        {
                            "order_id": order["broker_order_id"],
                            "asset": order["asset"].symbol,
                            "amount": order["amount"],
                            "status": order["status"],
                            "order_type": order["order_type"],
                            "limit_price": order.get("limit_price"),
                            "stop_price": order.get("stop_price"),
                        }
                    )

            return open_orders

        except Exception as e:
            logger.error("get_open_orders_failed", error=str(e))
            raise BrokerError(f"Failed to get open orders: {e}", adapter="custom_broker")

    async def subscribe_market_data(self, assets: list[Asset]) -> None:
        """Subscribe to real-time market data.

        Args:
            assets: List of assets to subscribe to

        Raises:
            BrokerError: If subscription fails
        """
        logger.info("subscribing_to_market_data", symbols=[a.symbol for a in assets])

        # TODO: Implement WebSocket subscription
        # await self._websocket.subscribe(symbols=[a.symbol for a in assets])

        logger.info("market_data_subscribed")

    async def unsubscribe_market_data(self, assets: list[Asset]) -> None:
        """Unsubscribe from market data.

        Args:
            assets: List of assets to unsubscribe from

        Raises:
            BrokerError: If unsubscribe fails
        """
        logger.info("unsubscribing_from_market_data", symbols=[a.symbol for a in assets])

        # TODO: Implement WebSocket unsubscribe
        # await self._websocket.unsubscribe(symbols=[a.symbol for a in assets])

        logger.info("market_data_unsubscribed")

    async def get_next_market_data(self) -> dict | None:
        """Get next market data update (blocking).

        Returns:
            Dict with keys: 'asset', 'open', 'high', 'low', 'close', 'volume',
            'timestamp'. Returns None if no data available.

        Raises:
            BrokerError: If data fetch fails
        """
        try:
            # TODO: Get data from WebSocket queue
            # data = await self._websocket_queue.get()

            # For demo, generate mock data
            await asyncio.sleep(1)  # Simulate 1-second bar
            return None  # No data in this example

        except Exception as e:
            logger.error("get_market_data_failed", error=str(e))
            return None

    async def get_current_price(self, asset: Asset) -> Decimal:
        """Get current price for asset.

        Args:
            asset: Asset to get price for

        Returns:
            Current price

        Raises:
            DataNotFoundError: If price not available
            BrokerError: If request fails
        """
        try:
            # TODO: Replace with real API call
            # response = await self._api_client.get_quote(asset.symbol)
            # return Decimal(str(response['last_price']))

            # Generate mock price
            base_price = Decimal("150.00")
            noise = Decimal(str(random.uniform(-2, 2)))
            return base_price + noise

        except Exception as e:
            logger.error("get_price_failed", asset=asset.symbol, error=str(e))
            raise DataNotFoundError(f"Price not available for {asset.symbol}")

    def is_connected(self) -> bool:
        """Check if broker connection is active.

        Returns:
            True if connected, False otherwise
        """
        return self._connected

    # ========================================================================
    # Helper Methods
    # ========================================================================

    async def _load_account_state(self) -> None:
        """Load initial account state from broker."""
        # TODO: Fetch real account state
        # response = await self._api_client.get_account()
        # self._account = {
        #     'cash': Decimal(str(response['cash'])),
        #     ...
        # }
        pass

    async def _load_positions(self) -> None:
        """Load existing positions from broker."""
        # TODO: Fetch real positions
        # response = await self._api_client.get_positions()
        # for pos in response:
        #     self._positions[pos['symbol']] = {...}
        pass

    async def _validate_order(self, asset: Asset, amount: Decimal, order_type: str) -> None:
        """Validate order before submission.

        Raises:
            InsufficientFundsError: If insufficient funds
            BrokerError: If order is invalid
        """
        # Check buying power
        if amount > 0:  # Buy order
            estimated_cost = abs(amount) * Decimal("150")  # Rough estimate
            if estimated_cost > self._account["buying_power"]:
                raise InsufficientFundsError(
                    f"Insufficient funds: need ${estimated_cost}, have ${self._account['buying_power']}"
                )

        # Validate order type
        valid_order_types = ["market", "limit", "stop", "stop-limit"]
        if order_type not in valid_order_types:
            raise BrokerError(
                f"Invalid order type: {order_type}. Valid types: {valid_order_types}",
                adapter="custom_broker",
            )


# ============================================================================
# Example Usage
# ============================================================================


async def main():
    """Demonstrate custom broker adapter usage."""
    print("=" * 70)
    print("Custom Broker Adapter Example")
    print("=" * 70)

    # Create custom broker adapter
    print("\n[1/5] Initializing custom broker...")
    broker = CustomBrokerAdapter(
        api_url="https://api.example.com",
        api_key="demo_api_key",
        api_secret="demo_api_secret",
        testnet=True,
    )
    print("✓ Broker initialized")

    # Connect to broker
    print("\n[2/5] Connecting to broker...")
    await broker.connect()
    print("✓ Connected to broker")

    # Get account info
    print("\n[3/5] Getting account information...")
    account = await broker.get_account_info()
    print(f"✓ Account cash: ${account['cash']}")
    print(f"  Equity: ${account['equity']}")
    print(f"  Buying power: ${account['buying_power']}")

    # Create mock asset
    asset = Equity(
        1,  # Asset ID
        exchange="NYSE",
        symbol="AAPL",
    )

    # Submit order
    print("\n[4/5] Submitting market order...")
    order_id = await broker.submit_order(
        asset=asset,
        amount=Decimal("100"),  # Buy 100 shares
        order_type="market",
    )
    print(f"✓ Order submitted: {order_id}")

    # Get open orders
    print("\n[5/5] Checking open orders...")
    open_orders = await broker.get_open_orders()
    print(f"✓ Open orders: {len(open_orders)}")
    for order in open_orders:
        print(f"  - {order['asset']}: {order['amount']} shares @ {order['order_type']}")

    # Disconnect
    await broker.disconnect()

    print("\n" + "=" * 70)
    print("✓ Example complete!")
    print("=" * 70)
    print("\nNext steps:")
    print("  1. Replace mock API calls with real broker API")
    print("  2. Implement proper authentication")
    print("  3. Add WebSocket market data streaming")
    print("  4. Implement position reconciliation")
    print("  5. Add comprehensive error handling")


if __name__ == "__main__":
    asyncio.run(main())
