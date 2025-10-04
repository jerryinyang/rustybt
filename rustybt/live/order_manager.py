"""Order lifecycle management for live trading.

This module tracks orders from submission through completion, managing state
transitions and providing thread-safe access to order state.
"""

import asyncio
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional

import pandas as pd
import structlog

from rustybt.assets import Asset

logger = structlog.get_logger()


class OrderStatus(str, Enum):
    """Order status states."""

    SUBMITTED = "submitted"  # Order created, not yet sent to broker
    PENDING = "pending"  # Order sent to broker, awaiting fill
    FILLED = "filled"  # Order fully filled
    CANCELED = "canceled"  # Order canceled
    REJECTED = "rejected"  # Order rejected by broker


@dataclass
class Order:
    """Order representation with lifecycle tracking."""

    id: str
    asset: Asset
    amount: Decimal  # Positive = buy, negative = sell
    order_type: str  # 'market', 'limit', 'stop', 'stop-limit'
    status: OrderStatus
    broker_order_id: Optional[str] = None
    limit_price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    created_at: pd.Timestamp = field(default_factory=pd.Timestamp.now)
    submitted_at: Optional[pd.Timestamp] = None
    filled_at: Optional[pd.Timestamp] = None
    filled_price: Optional[Decimal] = None
    filled_amount: Optional[Decimal] = None
    commission: Decimal = Decimal("0")
    reject_reason: Optional[str] = None


class OrderManager:
    """Manages order lifecycle tracking with thread-safe state access."""

    def __init__(self) -> None:
        """Initialize order manager."""
        self._orders: Dict[str, Order] = {}
        self._lock = asyncio.Lock()
        self._order_counter = 0

    async def create_order(
        self,
        asset: Asset,
        amount: Decimal,
        order_type: str = "market",
        limit_price: Optional[Decimal] = None,
        stop_price: Optional[Decimal] = None,
    ) -> Order:
        """Create new order with unique ID.

        Args:
            asset: Asset to trade
            amount: Order quantity (positive=buy, negative=sell)
            order_type: 'market', 'limit', 'stop', 'stop-limit'
            limit_price: Limit price for limit/stop-limit orders
            stop_price: Stop price for stop/stop-limit orders

        Returns:
            Created order

        Example:
            >>> order = await manager.create_order(
            ...     asset=AAPL,
            ...     amount=Decimal("100"),
            ...     order_type="limit",
            ...     limit_price=Decimal("150.50")
            ... )
        """
        async with self._lock:
            self._order_counter += 1
            order_id = f"order-{self._order_counter:08d}"

            order = Order(
                id=order_id,
                asset=asset,
                amount=amount,
                order_type=order_type,
                status=OrderStatus.SUBMITTED,
                limit_price=limit_price,
                stop_price=stop_price,
            )

            self._orders[order_id] = order

            logger.info(
                "order_created",
                order_id=order_id,
                asset=asset.symbol,
                amount=str(amount),
                order_type=order_type,
            )

            return order

    async def update_order_status(
        self,
        order_id: str,
        status: OrderStatus,
        broker_order_id: Optional[str] = None,
        filled_price: Optional[Decimal] = None,
        filled_amount: Optional[Decimal] = None,
        commission: Optional[Decimal] = None,
        reject_reason: Optional[str] = None,
    ) -> None:
        """Update order status and related fields.

        Args:
            order_id: Order ID to update
            status: New order status
            broker_order_id: Broker's order ID (if available)
            filled_price: Fill price (if filled)
            filled_amount: Filled amount (if filled)
            commission: Commission charged (if filled)
            reject_reason: Reason for rejection (if rejected)

        Raises:
            KeyError: If order_id not found
        """
        async with self._lock:
            order = self._orders[order_id]

            old_status = order.status
            order.status = status

            if broker_order_id is not None:
                order.broker_order_id = broker_order_id

            if status == OrderStatus.PENDING and order.submitted_at is None:
                order.submitted_at = pd.Timestamp.now()

            if status == OrderStatus.FILLED:
                order.filled_at = pd.Timestamp.now()
                order.filled_price = filled_price
                order.filled_amount = filled_amount or order.amount
                if commission is not None:
                    order.commission = commission

            if status == OrderStatus.REJECTED and reject_reason is not None:
                order.reject_reason = reject_reason

            logger.info(
                "order_status_updated",
                order_id=order_id,
                old_status=old_status.value,
                new_status=status.value,
                asset=order.asset.symbol,
            )

    async def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID.

        Args:
            order_id: Order ID

        Returns:
            Order if found, None otherwise
        """
        async with self._lock:
            return self._orders.get(order_id)

    async def get_active_orders(self) -> List[Order]:
        """Get all active orders (submitted or pending).

        Returns:
            List of active orders
        """
        async with self._lock:
            return [
                order
                for order in self._orders.values()
                if order.status in (OrderStatus.SUBMITTED, OrderStatus.PENDING)
            ]

    async def get_all_orders(self) -> List[Order]:
        """Get all orders.

        Returns:
            List of all orders
        """
        async with self._lock:
            return list(self._orders.values())

    async def get_orders_by_asset(self, asset: Asset) -> List[Order]:
        """Get all orders for specific asset.

        Args:
            asset: Asset to filter by

        Returns:
            List of orders for asset
        """
        async with self._lock:
            return [order for order in self._orders.values() if order.asset == asset]

    async def cancel_order(self, order_id: str, reason: str = "User requested") -> None:
        """Cancel order.

        Args:
            order_id: Order ID to cancel
            reason: Cancellation reason

        Raises:
            KeyError: If order_id not found
            ValueError: If order not in cancelable state
        """
        async with self._lock:
            order = self._orders[order_id]

            if order.status not in (OrderStatus.SUBMITTED, OrderStatus.PENDING):
                raise ValueError(
                    f"Cannot cancel order in status {order.status.value}"
                )

            order.status = OrderStatus.CANCELED
            order.reject_reason = reason

            logger.info(
                "order_canceled",
                order_id=order_id,
                asset=order.asset.symbol,
                reason=reason,
            )

    def get_order_count(self) -> int:
        """Get total number of orders tracked.

        Returns:
            Order count
        """
        return len(self._orders)
