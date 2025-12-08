"""Paper trading state persistence tests.

This module provides comprehensive tests for paper trading state persistence,
validating:
- State saves correctly across session restarts
- Positions restore with exact values
- Order history is preserved
- State restoration accuracy

Story: 10.2.2 - Paper Trading State Persistence & Long-Running Stability
"""

import asyncio
import tempfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from rustybt.assets import Equity, ExchangeInfo
from rustybt.live.brokers.paper_broker import PaperBroker
from rustybt.live.models import (
    AlignmentMetrics,
    OrderSnapshot,
    PositionSnapshot,
    StateCheckpoint,
)
from rustybt.live.state_manager import (
    CheckpointCorrupted,
    StateManager,
)

from .conftest import create_bar_data

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_asset() -> Equity:
    """Create sample equity asset for testing."""
    exchange_info = ExchangeInfo("NASDAQ", "NASDAQ", "US")
    return Equity(1, exchange_info, symbol="TEST")


@pytest.fixture
def paper_broker() -> PaperBroker:
    """Create PaperBroker with immediate fill for testing."""
    return PaperBroker(
        starting_cash=Decimal("100000"),
        order_latency_ms=1,
        latency_jitter_pct=Decimal("0"),
    )


@pytest.fixture
def temp_checkpoint_dir(tmp_path):
    """Create temporary directory for checkpoint files."""
    checkpoint_dir = tmp_path / "checkpoints"
    checkpoint_dir.mkdir()
    return checkpoint_dir


@pytest.fixture
def state_manager(temp_checkpoint_dir):
    """Create StateManager with temporary directory."""
    return StateManager(
        checkpoint_dir=temp_checkpoint_dir,
        staleness_threshold_seconds=3600,
    )


# =============================================================================
# Helper Functions
# =============================================================================


def create_position_snapshot(
    asset: str,
    sid: int,
    amount: Decimal,
    cost_basis: Decimal,
    last_price: Decimal,
) -> PositionSnapshot:
    """Create a PositionSnapshot for testing."""
    return PositionSnapshot(
        asset=asset,
        sid=sid,
        amount=str(amount),
        cost_basis=str(cost_basis),
        last_price=str(last_price),
    )


def create_order_snapshot(
    order_id: str,
    asset: str,
    sid: int,
    amount: Decimal,
    order_type: str,
    status: str,
    limit_price: Decimal | None = None,
    broker_order_id: str | None = None,
) -> OrderSnapshot:
    """Create an OrderSnapshot for testing."""
    return OrderSnapshot(
        order_id=order_id,
        asset=asset,
        sid=sid,
        amount=str(amount),
        order_type=order_type,
        limit_price=str(limit_price) if limit_price else None,
        broker_order_id=broker_order_id,
        status=status,
        created_at=datetime.now(),
    )


def create_checkpoint(
    strategy_name: str,
    positions: list[PositionSnapshot],
    orders: list[OrderSnapshot],
    cash_balance: Decimal,
    alignment_metrics: AlignmentMetrics | None = None,
) -> StateCheckpoint:
    """Create a StateCheckpoint for testing."""
    return StateCheckpoint(
        strategy_name=strategy_name,
        timestamp=datetime.now(),
        positions=positions,
        pending_orders=orders,
        cash_balance=str(cash_balance),
        alignment_metrics=alignment_metrics,
    )


# =============================================================================
# AC1: State Persistence Across Restarts
# =============================================================================


class TestStatePersistenceAcrossRestarts:
    """Tests for AC1: Paper trading state persists across session restarts."""

    def test_save_and_load_checkpoint_basic(self, state_manager):
        """Test basic checkpoint save and load."""
        strategy_name = "test_strategy"

        # Create checkpoint with positions
        positions = [
            create_position_snapshot(
                asset="BTC-PERP",
                sid=1,
                amount=Decimal("0.5"),
                cost_basis=Decimal("45000.00"),
                last_price=Decimal("46000.00"),
            ),
        ]
        orders = [
            create_order_snapshot(
                order_id="order-123",
                asset="BTC-PERP",
                sid=1,
                amount=Decimal("0.25"),
                order_type="limit",
                status="pending",
                limit_price=Decimal("44000.00"),
            ),
        ]
        checkpoint = create_checkpoint(
            strategy_name=strategy_name,
            positions=positions,
            orders=orders,
            cash_balance=Decimal("50000.00"),
        )

        # Save checkpoint
        state_manager.save_checkpoint(strategy_name, checkpoint)

        # Load checkpoint
        loaded = state_manager.load_checkpoint(strategy_name)

        assert loaded is not None
        assert loaded.strategy_name == strategy_name
        assert len(loaded.positions) == 1
        assert len(loaded.pending_orders) == 1
        assert loaded.cash_balance == "50000.00"

    def test_positions_restored_exactly(self, state_manager):
        """Test that open positions are restored exactly."""
        strategy_name = "position_test"

        # Create positions with specific values
        positions = [
            create_position_snapshot(
                asset="AAPL",
                sid=1,
                amount=Decimal("100"),
                cost_basis=Decimal("150.25"),
                last_price=Decimal("152.50"),
            ),
            create_position_snapshot(
                asset="GOOGL",
                sid=2,
                amount=Decimal("-50"),  # Short position
                cost_basis=Decimal("140.00"),
                last_price=Decimal("138.00"),
            ),
        ]
        checkpoint = create_checkpoint(
            strategy_name=strategy_name,
            positions=positions,
            orders=[],
            cash_balance=Decimal("75000.00"),
        )

        # Save and reload
        state_manager.save_checkpoint(strategy_name, checkpoint)
        loaded = state_manager.load_checkpoint(strategy_name)

        # Verify positions restored exactly
        assert len(loaded.positions) == 2

        # Find AAPL position
        aapl = next(p for p in loaded.positions if p.asset == "AAPL")
        assert aapl.to_decimal_amount() == Decimal("100")
        assert aapl.to_decimal_cost_basis() == Decimal("150.25")
        assert aapl.to_decimal_last_price() == Decimal("152.50")

        # Find GOOGL position (short)
        googl = next(p for p in loaded.positions if p.asset == "GOOGL")
        assert googl.to_decimal_amount() == Decimal("-50")
        assert googl.to_decimal_cost_basis() == Decimal("140.00")
        assert googl.to_decimal_last_price() == Decimal("138.00")

    def test_order_history_preserved(self, state_manager):
        """Test that order history is preserved across restarts."""
        strategy_name = "order_history_test"

        orders = [
            create_order_snapshot(
                order_id="order-1",
                asset="AAPL",
                sid=1,
                amount=Decimal("100"),
                order_type="market",
                status="filled",
            ),
            create_order_snapshot(
                order_id="order-2",
                asset="AAPL",
                sid=1,
                amount=Decimal("-50"),
                order_type="limit",
                status="pending",
                limit_price=Decimal("155.00"),
            ),
            create_order_snapshot(
                order_id="order-3",
                asset="GOOGL",
                sid=2,
                amount=Decimal("25"),
                order_type="stop",
                status="submitted",
            ),
        ]
        checkpoint = create_checkpoint(
            strategy_name=strategy_name,
            positions=[],
            orders=orders,
            cash_balance=Decimal("100000.00"),
        )

        # Save and reload
        state_manager.save_checkpoint(strategy_name, checkpoint)
        loaded = state_manager.load_checkpoint(strategy_name)

        # Verify orders preserved
        assert len(loaded.pending_orders) == 3

        order_ids = {o.order_id for o in loaded.pending_orders}
        assert "order-1" in order_ids
        assert "order-2" in order_ids
        assert "order-3" in order_ids

    def test_session_continues_from_restored_state(self, state_manager):
        """Test that session can continue from restored state."""
        strategy_name = "session_continue_test"

        # Initial state with positions and cash
        initial_positions = [
            create_position_snapshot(
                asset="TEST",
                sid=1,
                amount=Decimal("100"),
                cost_basis=Decimal("100.00"),
                last_price=Decimal("100.00"),
            ),
        ]
        initial_checkpoint = create_checkpoint(
            strategy_name=strategy_name,
            positions=initial_positions,
            orders=[],
            cash_balance=Decimal("90000.00"),
        )

        # Save initial state
        state_manager.save_checkpoint(strategy_name, initial_checkpoint)

        # Load state (simulating restart)
        loaded = state_manager.load_checkpoint(strategy_name)
        assert loaded is not None

        # Simulate continuing: modify state
        # Add a new position
        new_positions = list(loaded.positions) + [
            create_position_snapshot(
                asset="NEW",
                sid=2,
                amount=Decimal("50"),
                cost_basis=Decimal("200.00"),
                last_price=Decimal("205.00"),
            ),
        ]
        updated_checkpoint = create_checkpoint(
            strategy_name=strategy_name,
            positions=new_positions,
            orders=[],
            cash_balance=Decimal("80000.00"),  # Cash decreased
        )

        # Save updated state
        state_manager.save_checkpoint(strategy_name, updated_checkpoint)

        # Verify final state
        final = state_manager.load_checkpoint(strategy_name)
        assert len(final.positions) == 2
        assert final.to_decimal_cash_balance() == Decimal("80000.00")


# =============================================================================
# AC2: State Restoration Accuracy
# =============================================================================


class TestStateRestorationAccuracy:
    """Tests for AC2: State restoration is accurate."""

    def test_position_size_exact_match(self, state_manager):
        """Test that position size matches pre-restart value exactly."""
        strategy_name = "size_accuracy"

        # Test various position sizes including decimals
        test_sizes = [
            Decimal("100"),
            Decimal("0.5"),
            Decimal("1234.56789"),  # High precision
            Decimal("-500"),  # Short position
        ]

        for i, size in enumerate(test_sizes):
            positions = [
                create_position_snapshot(
                    asset=f"ASSET_{i}",
                    sid=i,
                    amount=size,
                    cost_basis=Decimal("100.00"),
                    last_price=Decimal("100.00"),
                ),
            ]
            checkpoint = create_checkpoint(
                strategy_name=strategy_name,
                positions=positions,
                orders=[],
                cash_balance=Decimal("100000"),
            )

            state_manager.save_checkpoint(strategy_name, checkpoint)
            loaded = state_manager.load_checkpoint(strategy_name)

            assert loaded.positions[0].to_decimal_amount() == size

    def test_entry_price_exact_match(self, state_manager):
        """Test that entry price matches pre-restart value exactly."""
        strategy_name = "price_accuracy"

        # Test various entry prices
        test_prices = [
            Decimal("100.00"),
            Decimal("0.00001"),  # Very small (crypto)
            Decimal("123456.78"),  # Large
            Decimal("99.995"),  # Fractional cents
        ]

        for i, price in enumerate(test_prices):
            positions = [
                create_position_snapshot(
                    asset=f"ASSET_{i}",
                    sid=i,
                    amount=Decimal("100"),
                    cost_basis=price,
                    last_price=price,
                ),
            ]
            checkpoint = create_checkpoint(
                strategy_name=strategy_name,
                positions=positions,
                orders=[],
                cash_balance=Decimal("100000"),
            )

            state_manager.save_checkpoint(strategy_name, checkpoint)
            loaded = state_manager.load_checkpoint(strategy_name)

            assert loaded.positions[0].to_decimal_cost_basis() == price

    def test_unrealized_pnl_recalculates_correctly(self, state_manager):
        """Test that unrealized PnL recalculates correctly with current prices."""
        strategy_name = "pnl_recalc"

        # Create position with specific values
        cost_basis = Decimal("100.00")
        amount = Decimal("100")
        last_price = Decimal("110.00")

        positions = [
            create_position_snapshot(
                asset="TEST",
                sid=1,
                amount=amount,
                cost_basis=cost_basis,
                last_price=last_price,
            ),
        ]
        checkpoint = create_checkpoint(
            strategy_name=strategy_name,
            positions=positions,
            orders=[],
            cash_balance=Decimal("90000"),
        )

        state_manager.save_checkpoint(strategy_name, checkpoint)
        loaded = state_manager.load_checkpoint(strategy_name)

        # Recalculate expected PnL
        pos = loaded.positions[0]
        recalc_pnl = (
            pos.to_decimal_last_price() - pos.to_decimal_cost_basis()
        ) * pos.to_decimal_amount()
        expected_pnl = (last_price - cost_basis) * amount

        assert recalc_pnl == expected_pnl
        assert recalc_pnl == Decimal("1000.00")

    def test_multiple_position_restore_accuracy(self, state_manager):
        """Test that multiple positions (long and short) restore accurately."""
        strategy_name = "multi_position"

        positions = [
            # Long positions
            create_position_snapshot(
                "AAPL", 1, Decimal("100"), Decimal("150.00"), Decimal("155.00")
            ),
            create_position_snapshot(
                "GOOGL", 2, Decimal("50"), Decimal("2800.00"), Decimal("2750.00")
            ),
            # Short positions
            create_position_snapshot(
                "MSFT", 3, Decimal("-75"), Decimal("330.00"), Decimal("335.00")
            ),
            create_position_snapshot(
                "TSLA", 4, Decimal("-25"), Decimal("250.00"), Decimal("245.00")
            ),
        ]
        checkpoint = create_checkpoint(
            strategy_name=strategy_name,
            positions=positions,
            orders=[],
            cash_balance=Decimal("50000.00"),
        )

        state_manager.save_checkpoint(strategy_name, checkpoint)
        loaded = state_manager.load_checkpoint(strategy_name)

        assert len(loaded.positions) == 4

        # Verify each position
        for orig, restored in zip(positions, loaded.positions):
            assert orig.asset == restored.asset
            assert orig.amount == restored.amount
            assert orig.cost_basis == restored.cost_basis
            assert orig.last_price == restored.last_price

    def test_different_position_counts(self, state_manager):
        """Test with different numbers of positions."""
        strategy_name = "position_counts"

        for count in [0, 1, 5, 10, 50]:
            positions = [
                create_position_snapshot(
                    asset=f"ASSET_{i}",
                    sid=i,
                    amount=Decimal(str(i * 10 + 1)),
                    cost_basis=Decimal(str(100 + i)),
                    last_price=Decimal(str(100 + i + 5)),
                )
                for i in range(count)
            ]
            checkpoint = create_checkpoint(
                strategy_name=strategy_name,
                positions=positions,
                orders=[],
                cash_balance=Decimal("100000"),
            )

            state_manager.save_checkpoint(strategy_name, checkpoint)
            loaded = state_manager.load_checkpoint(strategy_name)

            assert len(loaded.positions) == count


# =============================================================================
# AC5: State Integrity
# =============================================================================


class TestStateIntegrity:
    """Tests for AC5: No state corruption during operation."""

    def test_checkpoint_atomic_write(self, state_manager, temp_checkpoint_dir):
        """Test that checkpoint writes are atomic (no partial writes)."""
        strategy_name = "atomic_test"

        # Create and save checkpoint
        checkpoint = create_checkpoint(
            strategy_name=strategy_name,
            positions=[
                create_position_snapshot("TEST", 1, Decimal("100"), Decimal("100"), Decimal("100")),
            ],
            orders=[],
            cash_balance=Decimal("90000"),
        )
        state_manager.save_checkpoint(strategy_name, checkpoint)

        # Verify no temp files left
        temp_files = list(temp_checkpoint_dir.glob("*.tmp"))
        assert len(temp_files) == 0

        # Verify checkpoint file exists
        checkpoint_files = list(temp_checkpoint_dir.glob("*_checkpoint.json"))
        assert len(checkpoint_files) == 1

    def test_corrupted_checkpoint_detection(self, temp_checkpoint_dir):
        """Test that corrupted checkpoints are detected."""
        state_manager = StateManager(checkpoint_dir=temp_checkpoint_dir)

        # Create a corrupted checkpoint file
        strategy_name = "corrupted_test"
        checkpoint_path = temp_checkpoint_dir / f"{strategy_name}_checkpoint.json"
        checkpoint_path.write_text("{ invalid json }")

        # Attempt to load should raise CheckpointCorrupted
        with pytest.raises(CheckpointCorrupted):
            state_manager.load_checkpoint(strategy_name)

    def test_position_calculations_remain_correct(self, state_manager):
        """Test that position calculations remain correct after multiple saves."""
        strategy_name = "calc_integrity"

        # Initial position
        amount = Decimal("100")
        cost_basis = Decimal("100.00")

        for iteration in range(10):
            # Update last price each iteration
            last_price = Decimal("100.00") + Decimal(str(iteration))

            positions = [
                create_position_snapshot(
                    asset="TEST",
                    sid=1,
                    amount=amount,
                    cost_basis=cost_basis,
                    last_price=last_price,
                ),
            ]
            checkpoint = create_checkpoint(
                strategy_name=strategy_name,
                positions=positions,
                orders=[],
                cash_balance=Decimal("90000"),
            )

            state_manager.save_checkpoint(strategy_name, checkpoint)
            loaded = state_manager.load_checkpoint(strategy_name)

            # Verify calculations
            pos = loaded.positions[0]
            expected_pnl = (
                pos.to_decimal_last_price() - pos.to_decimal_cost_basis()
            ) * pos.to_decimal_amount()
            assert expected_pnl == (last_price - cost_basis) * amount

    def test_alignment_metrics_persistence(self, state_manager):
        """Test that alignment metrics persist correctly."""
        strategy_name = "alignment_test"

        metrics = AlignmentMetrics(
            signal_match_rate=0.95,
            slippage_error_bps=5.0,
            fill_rate_error_pct=2.5,
            backtest_signal_count=100,
            live_signal_count=98,
            last_updated=datetime.now(),
        )

        checkpoint = create_checkpoint(
            strategy_name=strategy_name,
            positions=[],
            orders=[],
            cash_balance=Decimal("100000"),
            alignment_metrics=metrics,
        )

        state_manager.save_checkpoint(strategy_name, checkpoint)
        loaded = state_manager.load_checkpoint(strategy_name)

        assert loaded.alignment_metrics is not None
        assert loaded.alignment_metrics.signal_match_rate == 0.95
        assert loaded.alignment_metrics.slippage_error_bps == 5.0


# =============================================================================
# AC6: Audit Logging
# =============================================================================


class TestAuditLogging:
    """Tests for AC6: All order state transitions are logged for audit trail."""

    @pytest.mark.asyncio
    async def test_transactions_provide_audit_trail(self, paper_broker, sample_asset):
        """Test that transactions provide a complete audit trail."""
        await paper_broker.connect()

        paper_broker._update_market_data(sample_asset, create_bar_data(Decimal("100.00")))

        # Execute multiple orders
        await paper_broker.submit_order(
            asset=sample_asset,
            amount=Decimal("100"),
            order_type="market",
        )
        await asyncio.sleep(0.1)

        paper_broker._update_market_data(sample_asset, create_bar_data(Decimal("110.00")))
        await paper_broker.submit_order(
            asset=sample_asset,
            amount=Decimal("-50"),
            order_type="market",
        )
        await asyncio.sleep(0.1)

        # Verify audit trail
        assert len(paper_broker.transactions) == 2

        # Verify transaction details
        tx1 = paper_broker.transactions[0]
        assert tx1.amount == Decimal("100")
        assert tx1.price == Decimal("100.00")

        tx2 = paper_broker.transactions[1]
        assert tx2.amount == Decimal("-50")
        assert tx2.price == Decimal("110.00")

    @pytest.mark.asyncio
    async def test_order_tracking_complete(self, paper_broker, sample_asset):
        """Test that all orders are tracked for audit."""
        await paper_broker.connect()

        paper_broker._update_market_data(sample_asset, create_bar_data(Decimal("100.00")))

        # Submit multiple orders
        order_ids = []
        for i in range(5):
            order_id = await paper_broker.submit_order(
                asset=sample_asset,
                amount=Decimal("10"),
                order_type="market",
            )
            order_ids.append(order_id)
            await asyncio.sleep(0.05)

        await asyncio.sleep(0.2)

        # All orders should be tracked
        for order_id in order_ids:
            assert order_id in paper_broker.orders


# =============================================================================
# State Manager Utilities
# =============================================================================


class TestStateManagerUtilities:
    """Tests for StateManager utility methods."""

    def test_list_checkpoints(self, state_manager):
        """Test listing all available checkpoints."""
        # Create multiple checkpoints
        for name in ["strategy_a", "strategy_b", "strategy_c"]:
            checkpoint = create_checkpoint(
                strategy_name=name,
                positions=[],
                orders=[],
                cash_balance=Decimal("100000"),
            )
            state_manager.save_checkpoint(name, checkpoint)

        # List checkpoints
        checkpoints = state_manager.list_checkpoints()
        assert len(checkpoints) == 3
        assert "strategy_a" in checkpoints
        assert "strategy_b" in checkpoints
        assert "strategy_c" in checkpoints

    def test_delete_checkpoint(self, state_manager):
        """Test checkpoint deletion."""
        strategy_name = "delete_test"

        # Create checkpoint
        checkpoint = create_checkpoint(
            strategy_name=strategy_name,
            positions=[],
            orders=[],
            cash_balance=Decimal("100000"),
        )
        state_manager.save_checkpoint(strategy_name, checkpoint)

        # Verify exists
        assert state_manager.load_checkpoint(strategy_name) is not None

        # Delete
        result = state_manager.delete_checkpoint(strategy_name)
        assert result is True

        # Verify deleted
        assert state_manager.load_checkpoint(strategy_name) is None

    def test_get_checkpoint_info(self, state_manager):
        """Test getting checkpoint metadata."""
        strategy_name = "info_test"

        positions = [
            create_position_snapshot("TEST", 1, Decimal("100"), Decimal("100"), Decimal("100")),
        ]
        orders = [
            create_order_snapshot("order-1", "TEST", 1, Decimal("50"), "limit", "pending"),
        ]
        checkpoint = create_checkpoint(
            strategy_name=strategy_name,
            positions=positions,
            orders=orders,
            cash_balance=Decimal("90000"),
        )
        state_manager.save_checkpoint(strategy_name, checkpoint)

        # Get info
        info = state_manager.get_checkpoint_info(strategy_name)

        assert info is not None
        assert info["strategy_name"] == strategy_name
        assert info["positions_count"] == 1
        assert info["pending_orders_count"] == 1
        assert "file_size_bytes" in info
        assert "checkpoint_timestamp" in info

    def test_checkpoint_staleness_detection(self):
        """Test that stale checkpoints are detected."""
        # Create checkpoint with old timestamp
        checkpoint = StateCheckpoint(
            strategy_name="stale_test",
            timestamp=datetime(2020, 1, 1),  # Very old
            positions=[],
            pending_orders=[],
            cash_balance="100000",
        )

        # Check staleness (default 1 hour threshold)
        assert checkpoint.is_stale(3600) is True

        # Create fresh checkpoint
        fresh_checkpoint = StateCheckpoint(
            strategy_name="fresh_test",
            timestamp=datetime.now(),
            positions=[],
            pending_orders=[],
            cash_balance="100000",
        )
        assert fresh_checkpoint.is_stale(3600) is False
