"""Base broker adapter interface.

This module defines the abstract interface that all broker adapters must implement.
"""

from abc import ABC, abstractmethod
from decimal import Decimal

from rustybt.assets import Asset


class BrokerAdapter(ABC):
    """Abstract base class for broker adapters."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to broker.

        Raises:
            BrokerConnectionError: If connection fails
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from broker."""
        pass

    @abstractmethod
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
            BrokerError: If order submission fails
        """
        pass

    @abstractmethod
    async def cancel_order(self, broker_order_id: str) -> None:
        """Cancel order.

        Args:
            broker_order_id: Broker's order ID

        Raises:
            BrokerError: If cancellation fails
        """
        pass

    @abstractmethod
    async def get_account_info(self) -> dict[str, Decimal]:
        """Get account information.

        Returns:
            Dict with keys: 'cash', 'equity', 'buying_power', etc.

        Raises:
            BrokerError: If request fails
        """
        pass

    @abstractmethod
    async def get_positions(self) -> list[dict]:
        """Get current positions.

        Returns:
            List of position dicts with keys: 'asset', 'amount', 'cost_basis', 'market_value'

        Raises:
            BrokerError: If request fails
        """
        pass

    @abstractmethod
    async def get_open_orders(self) -> list[dict]:
        """Get open/pending orders from broker.

        Returns:
            List of order dicts with keys: 'order_id', 'asset', 'amount', 'status', 'order_type'

        Raises:
            BrokerError: If request fails
        """
        pass

    @abstractmethod
    async def subscribe_market_data(self, assets: list[Asset]) -> None:
        """Subscribe to real-time market data.

        Args:
            assets: List of assets to subscribe to

        Raises:
            BrokerError: If subscription fails
        """
        pass

    @abstractmethod
    async def unsubscribe_market_data(self, assets: list[Asset]) -> None:
        """Unsubscribe from market data.

        Args:
            assets: List of assets to unsubscribe from

        Raises:
            BrokerError: If unsubscribe fails
        """
        pass

    @abstractmethod
    async def get_next_market_data(self) -> dict | None:
        """Get next market data update (blocking).

        Returns:
            Dict with keys: 'asset', 'open', 'high', 'low', 'close', 'volume', 'timestamp'
            Returns None if no data available

        Raises:
            BrokerError: If data fetch fails
        """
        pass

    @abstractmethod
    async def get_current_price(self, asset: Asset) -> Decimal:
        """Get current price for asset.

        Args:
            asset: Asset to get price for

        Returns:
            Current price

        Raises:
            BrokerError: If price fetch fails
        """
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if broker connection is active.

        Returns:
            True if connected, False otherwise
        """
        pass
