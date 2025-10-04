"""Tests for order manager."""

import asyncio
from decimal import Decimal
from unittest.mock import Mock

import pandas as pd
import pytest

from rustybt.assets import Equity
from rustybt.assets.exchange_info import ExchangeInfo
from rustybt.live.order_manager import Order, OrderManager, OrderStatus


@pytest.fixture
def sample_asset():
    """Create sample asset for testing."""
    exchange_info = ExchangeInfo(
        "NASDAQ",
        "NASDAQ",
        "US",
    )
    return Equity(
        1,  # sid
        exchange_info,
        symbol="AAPL",
        asset_name="Apple Inc.",
        start_date=pd.Timestamp("2020-01-01"),
        end_date=pd.Timestamp("2030-01-01"),
        first_traded=pd.Timestamp("2020-01-01"),
        auto_close_date=pd.Timestamp("2030-01-01"),
    )


class TestOrderManager:
    """Test OrderManager."""

    @pytest.mark.asyncio
    async def test_create_order(self, sample_asset):
        """Test creating orders."""
        manager = OrderManager()

        order = await manager.create_order(
            asset=sample_asset,
            amount=Decimal("100"),
            order_type="market",
        )

        assert order.id == "order-00000001"
        assert order.asset == sample_asset
        assert order.amount == Decimal("100")
        assert order.order_type == "market"
        assert order.status == OrderStatus.SUBMITTED

    @pytest.mark.asyncio
    async def test_create_multiple_orders(self, sample_asset):
        """Test creating multiple orders with unique IDs."""
        manager = OrderManager()

        order1 = await manager.create_order(
            asset=sample_asset, amount=Decimal("100"), order_type="market"
        )
        order2 = await manager.create_order(
            asset=sample_asset, amount=Decimal("200"), order_type="limit"
        )

        assert order1.id == "order-00000001"
        assert order2.id == "order-00000002"
        assert manager.get_order_count() == 2

    @pytest.mark.asyncio
    async def test_update_order_status_to_pending(self, sample_asset):
        """Test updating order status to pending."""
        manager = OrderManager()

        order = await manager.create_order(
            asset=sample_asset, amount=Decimal("100"), order_type="market"
        )

        await manager.update_order_status(
            order_id=order.id,
            status=OrderStatus.PENDING,
            broker_order_id="broker-123",
        )

        updated_order = await manager.get_order(order.id)
        assert updated_order.status == OrderStatus.PENDING
        assert updated_order.broker_order_id == "broker-123"
        assert updated_order.submitted_at is not None

    @pytest.mark.asyncio
    async def test_update_order_status_to_filled(self, sample_asset):
        """Test updating order status to filled."""
        manager = OrderManager()

        order = await manager.create_order(
            asset=sample_asset, amount=Decimal("100"), order_type="market"
        )

        await manager.update_order_status(
            order_id=order.id,
            status=OrderStatus.FILLED,
            filled_price=Decimal("150.50"),
            filled_amount=Decimal("100"),
            commission=Decimal("1.00"),
        )

        updated_order = await manager.get_order(order.id)
        assert updated_order.status == OrderStatus.FILLED
        assert updated_order.filled_price == Decimal("150.50")
        assert updated_order.filled_amount == Decimal("100")
        assert updated_order.commission == Decimal("1.00")
        assert updated_order.filled_at is not None

    @pytest.mark.asyncio
    async def test_update_order_status_to_rejected(self, sample_asset):
        """Test updating order status to rejected."""
        manager = OrderManager()

        order = await manager.create_order(
            asset=sample_asset, amount=Decimal("100"), order_type="market"
        )

        await manager.update_order_status(
            order_id=order.id,
            status=OrderStatus.REJECTED,
            reject_reason="Insufficient funds",
        )

        updated_order = await manager.get_order(order.id)
        assert updated_order.status == OrderStatus.REJECTED
        assert updated_order.reject_reason == "Insufficient funds"

    @pytest.mark.asyncio
    async def test_get_order(self, sample_asset):
        """Test retrieving order by ID."""
        manager = OrderManager()

        order = await manager.create_order(
            asset=sample_asset, amount=Decimal("100"), order_type="market"
        )

        retrieved = await manager.get_order(order.id)
        assert retrieved.id == order.id
        assert retrieved.amount == Decimal("100")

    @pytest.mark.asyncio
    async def test_get_order_not_found(self):
        """Test retrieving non-existent order."""
        manager = OrderManager()

        result = await manager.get_order("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_active_orders(self, sample_asset):
        """Test retrieving active orders."""
        manager = OrderManager()

        order1 = await manager.create_order(
            asset=sample_asset, amount=Decimal("100"), order_type="market"
        )
        order2 = await manager.create_order(
            asset=sample_asset, amount=Decimal("200"), order_type="market"
        )
        order3 = await manager.create_order(
            asset=sample_asset, amount=Decimal("300"), order_type="market"
        )

        # Update statuses
        await manager.update_order_status(order1.id, OrderStatus.PENDING)
        await manager.update_order_status(order2.id, OrderStatus.FILLED)
        # order3 remains SUBMITTED

        active_orders = await manager.get_active_orders()

        assert len(active_orders) == 2
        assert order1.id in [o.id for o in active_orders]
        assert order3.id in [o.id for o in active_orders]
        assert order2.id not in [o.id for o in active_orders]

    @pytest.mark.asyncio
    async def test_get_all_orders(self, sample_asset):
        """Test retrieving all orders."""
        manager = OrderManager()

        await manager.create_order(
            asset=sample_asset, amount=Decimal("100"), order_type="market"
        )
        await manager.create_order(
            asset=sample_asset, amount=Decimal("200"), order_type="market"
        )

        all_orders = await manager.get_all_orders()
        assert len(all_orders) == 2

    @pytest.mark.asyncio
    async def test_get_orders_by_asset(self, sample_asset):
        """Test retrieving orders by asset."""
        manager = OrderManager()

        # Create second asset
        exchange_info2 = ExchangeInfo("NASDAQ", "NASDAQ", "US")
        asset2 = Equity(
            2,
            exchange_info2,
            symbol="GOOGL",
            asset_name="Alphabet Inc.",
            start_date=pd.Timestamp("2020-01-01"),
            end_date=pd.Timestamp("2030-01-01"),
            first_traded=pd.Timestamp("2020-01-01"),
            auto_close_date=pd.Timestamp("2030-01-01"),
        )

        await manager.create_order(
            asset=sample_asset, amount=Decimal("100"), order_type="market"
        )
        await manager.create_order(
            asset=asset2, amount=Decimal("200"), order_type="market"
        )
        await manager.create_order(
            asset=sample_asset, amount=Decimal("300"), order_type="market"
        )

        aapl_orders = await manager.get_orders_by_asset(sample_asset)
        assert len(aapl_orders) == 2

        googl_orders = await manager.get_orders_by_asset(asset2)
        assert len(googl_orders) == 1

    @pytest.mark.asyncio
    async def test_cancel_order(self, sample_asset):
        """Test canceling order."""
        manager = OrderManager()

        order = await manager.create_order(
            asset=sample_asset, amount=Decimal("100"), order_type="market"
        )

        await manager.cancel_order(order.id, reason="User requested")

        updated_order = await manager.get_order(order.id)
        assert updated_order.status == OrderStatus.CANCELED
        assert updated_order.reject_reason == "User requested"

    @pytest.mark.asyncio
    async def test_cancel_order_invalid_state(self, sample_asset):
        """Test canceling order in non-cancelable state."""
        manager = OrderManager()

        order = await manager.create_order(
            asset=sample_asset, amount=Decimal("100"), order_type="market"
        )

        # Fill the order
        await manager.update_order_status(
            order_id=order.id,
            status=OrderStatus.FILLED,
            filled_price=Decimal("150.50"),
            filled_amount=Decimal("100"),
        )

        # Try to cancel filled order
        with pytest.raises(ValueError, match="Cannot cancel order"):
            await manager.cancel_order(order.id)

    @pytest.mark.asyncio
    async def test_thread_safety(self, sample_asset):
        """Test concurrent order operations."""
        manager = OrderManager()

        # Create multiple orders concurrently
        tasks = [
            manager.create_order(
                asset=sample_asset,
                amount=Decimal(str(i * 100)),
                order_type="market",
            )
            for i in range(1, 11)
        ]

        orders = await asyncio.gather(*tasks)

        # All orders should have unique IDs
        order_ids = [o.id for o in orders]
        assert len(order_ids) == len(set(order_ids))

        # All orders should be tracked
        assert manager.get_order_count() == 10
