"""Tests for order manager."""

import asyncio
from decimal import Decimal

import pandas as pd
import pytest

from rustybt.assets import Equity
from rustybt.assets.exchange_info import ExchangeInfo
from rustybt.live.order_manager import OrderManager, OrderStatus


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

        await manager.create_order(asset=sample_asset, amount=Decimal("100"), order_type="market")
        await manager.create_order(asset=sample_asset, amount=Decimal("200"), order_type="market")

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

        await manager.create_order(asset=sample_asset, amount=Decimal("100"), order_type="market")
        await manager.create_order(asset=asset2, amount=Decimal("200"), order_type="market")
        await manager.create_order(asset=sample_asset, amount=Decimal("300"), order_type="market")

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


class TestOrderManagerLogging:
    """Integration tests for order manager logging."""

    @pytest.mark.asyncio
    async def test_order_submitted_logging(self, sample_asset, tmp_path, caplog):
        """Test that order submission generates audit logs."""
        import json

        from rustybt.utils.logging import configure_logging

        # Configure logging to temp directory
        log_dir = tmp_path / "logs"
        configure_logging(log_dir=log_dir, log_level="INFO", log_to_console=False)

        manager = OrderManager()

        # Create order
        order = await manager.create_order(
            asset=sample_asset,
            amount=Decimal("100"),
            order_type="market",
        )

        # Read log file
        log_file = log_dir / "rustybt.log"
        assert log_file.exists(), "Log file should be created"

        with open(log_file) as f:
            logs = [json.loads(line) for line in f if line.strip()]

        # Find order_submitted log
        submitted_logs = [log for log in logs if log.get("event_type") == "order_submitted"]
        assert len(submitted_logs) == 1, "Should have exactly one order_submitted log"

        log_entry = submitted_logs[0]
        assert log_entry["order_id"] == order.id
        assert log_entry["asset"] == "AAPL"
        assert log_entry["amount"] == "100"
        assert log_entry["order_type"] == "market"
        assert "timestamp" in log_entry

    @pytest.mark.asyncio
    async def test_order_filled_logging(self, sample_asset, tmp_path):
        """Test that order fill generates audit logs without hardcoded slippage."""
        import json

        from rustybt.utils.logging import configure_logging

        # Configure logging to temp directory
        log_dir = tmp_path / "logs"
        configure_logging(log_dir=log_dir, log_level="INFO", log_to_console=False)

        manager = OrderManager()

        # Create and fill order
        order = await manager.create_order(
            asset=sample_asset,
            amount=Decimal("100"),
            order_type="market",
        )

        await manager.update_order_status(
            order_id=order.id,
            status=OrderStatus.FILLED,
            filled_price=Decimal("150.50"),
            filled_amount=Decimal("100"),
            commission=Decimal("1.00"),
        )

        # Read log file
        log_file = log_dir / "rustybt.log"
        with open(log_file) as f:
            logs = [json.loads(line) for line in f if line.strip()]

        # Find order_filled log
        filled_logs = [log for log in logs if log.get("event_type") == "order_filled"]
        assert len(filled_logs) == 1, "Should have exactly one order_filled log"

        log_entry = filled_logs[0]
        assert log_entry["order_id"] == order.id
        assert log_entry["asset"] == "AAPL"
        assert log_entry["fill_price"] == "150.50"
        assert log_entry["filled_amount"] == "100"
        assert log_entry["commission"] == "1.00"
        # Verify slippage is NOT in logs (was hardcoded before fix)
        assert (
            "slippage" not in log_entry
        ), "Slippage should be omitted until calculation implemented"
        assert "timestamp" in log_entry

    @pytest.mark.asyncio
    async def test_order_rejected_logging(self, sample_asset, tmp_path):
        """Test that order rejection generates audit logs."""
        import json

        from rustybt.utils.logging import configure_logging

        # Configure logging to temp directory
        log_dir = tmp_path / "logs"
        configure_logging(log_dir=log_dir, log_level="INFO", log_to_console=False)

        manager = OrderManager()

        # Create and reject order
        order = await manager.create_order(
            asset=sample_asset,
            amount=Decimal("100"),
            order_type="market",
        )

        await manager.update_order_status(
            order_id=order.id,
            status=OrderStatus.REJECTED,
            reject_reason="Insufficient funds",
        )

        # Read log file
        log_file = log_dir / "rustybt.log"
        with open(log_file) as f:
            logs = [json.loads(line) for line in f if line.strip()]

        # Find order_rejected log
        rejected_logs = [log for log in logs if log.get("event_type") == "order_rejected"]
        assert len(rejected_logs) == 1, "Should have exactly one order_rejected log"

        log_entry = rejected_logs[0]
        assert log_entry["order_id"] == order.id
        assert log_entry["asset"] == "AAPL"
        assert log_entry["rejection_reason"] == "Insufficient funds"
        assert log_entry["level"] == "error"
        assert "timestamp" in log_entry

    @pytest.mark.asyncio
    async def test_order_canceled_logging(self, sample_asset, tmp_path):
        """Test that order cancellation generates audit logs."""
        import json

        from rustybt.utils.logging import configure_logging

        # Configure logging to temp directory
        log_dir = tmp_path / "logs"
        configure_logging(log_dir=log_dir, log_level="INFO", log_to_console=False)

        manager = OrderManager()

        # Create and cancel order
        order = await manager.create_order(
            asset=sample_asset,
            amount=Decimal("100"),
            order_type="market",
        )

        await manager.cancel_order(order.id, reason="User requested")

        # Read log file
        log_file = log_dir / "rustybt.log"
        with open(log_file) as f:
            logs = [json.loads(line) for line in f if line.strip()]

        # Find order_canceled log
        canceled_logs = [log for log in logs if log.get("event_type") == "order_canceled"]
        assert len(canceled_logs) == 1, "Should have exactly one order_canceled log"

        log_entry = canceled_logs[0]
        assert log_entry["order_id"] == order.id
        assert log_entry["asset"] == "AAPL"
        assert log_entry["reason"] == "User requested"
        assert "timestamp" in log_entry
