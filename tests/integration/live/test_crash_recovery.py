"""Integration tests for crash recovery with state restoration."""

from datetime import datetime
from decimal import Decimal

import pytest

from rustybt.live.models import (
    AlignmentMetrics,
    OrderSnapshot,
    PositionSnapshot,
    StateCheckpoint,
)
from rustybt.live.state_manager import ReconciliationStrategy, StateManager


@pytest.fixture
def checkpoint_dir(tmp_path):
    """Create temporary checkpoint directory."""
    return tmp_path / "integration_checkpoints"


@pytest.fixture
def strategy_name():
    """Strategy name for testing."""
    return "test_mean_reversion_strategy"


class TestCrashRecoveryScenario:
    """Integration tests for full crash → recovery scenarios."""

    def test_save_crash_restore_scenario(self, checkpoint_dir, strategy_name):
        """Test complete save → crash → restore scenario.

        This simulates:
        1. Engine running with positions and orders
        2. Periodic checkpoint saved
        3. Engine crashes (simulated by creating new StateManager instance)
        4. Engine restarts and loads checkpoint
        5. State is restored correctly
        """
        # === PHASE 1: Engine Running ===
        state_manager = StateManager(checkpoint_dir=checkpoint_dir)

        # Create checkpoint representing live trading state
        original_checkpoint = StateCheckpoint(
            strategy_name=strategy_name,
            timestamp=datetime.now(),
            strategy_state={"last_signal": "buy", "position_size": 100},
            positions=[
                PositionSnapshot(
                    asset="AAPL",
                    sid=1,
                    amount="100",
                    cost_basis="150.00",
                    last_price="155.00",
                ),
                PositionSnapshot(
                    asset="MSFT",
                    sid=2,
                    amount="50",
                    cost_basis="320.00",
                    last_price="325.00",
                ),
            ],
            pending_orders=[
                OrderSnapshot(
                    order_id="order-123",
                    asset="GOOGL",
                    sid=3,
                    amount="10",
                    order_type="limit",
                    limit_price="2800.00",
                    broker_order_id="broker-456",
                    status="pending",
                    created_at=datetime.now(),
                )
            ],
            cash_balance="25000.00",
        )

        # Save checkpoint (periodic save)
        state_manager.save_checkpoint(strategy_name, original_checkpoint)

        # === PHASE 2: Simulated Crash ===
        # (In reality, process would terminate abruptly)
        # Simulate by discarding state_manager instance
        del state_manager

        # === PHASE 3: Engine Restart ===
        # Create new StateManager (simulates fresh engine start)
        recovery_state_manager = StateManager(checkpoint_dir=checkpoint_dir)

        # Load checkpoint
        restored_checkpoint = recovery_state_manager.load_checkpoint(strategy_name)

        # === PHASE 4: Verify State Restoration ===
        assert restored_checkpoint is not None, "Checkpoint should be found"

        # Verify strategy name
        assert restored_checkpoint.strategy_name == strategy_name

        # Verify strategy state
        assert restored_checkpoint.strategy_state["last_signal"] == "buy"
        assert restored_checkpoint.strategy_state["position_size"] == 100

        # Verify positions restored
        assert len(restored_checkpoint.positions) == 2
        aapl_pos = next(p for p in restored_checkpoint.positions if p.asset == "AAPL")
        assert aapl_pos.to_decimal_amount() == Decimal("100")
        assert aapl_pos.to_decimal_cost_basis() == Decimal("150.00")

        msft_pos = next(p for p in restored_checkpoint.positions if p.asset == "MSFT")
        assert msft_pos.to_decimal_amount() == Decimal("50")

        # Verify pending orders restored
        assert len(restored_checkpoint.pending_orders) == 1
        order = restored_checkpoint.pending_orders[0]
        assert order.order_id == "order-123"
        assert order.broker_order_id == "broker-456"
        assert order.status == "pending"

        # Verify cash balance
        assert restored_checkpoint.to_decimal_cash_balance() == Decimal("25000.00")

    def test_crash_with_empty_state(self, checkpoint_dir, strategy_name):
        """Test crash recovery with no positions or orders."""
        # Save minimal checkpoint
        state_manager = StateManager(checkpoint_dir=checkpoint_dir)

        minimal_checkpoint = StateCheckpoint(
            strategy_name=strategy_name,
            timestamp=datetime.now(),
            cash_balance="100000.00",
        )

        state_manager.save_checkpoint(strategy_name, minimal_checkpoint)

        # Simulate crash
        del state_manager

        # Restore
        recovery_manager = StateManager(checkpoint_dir=checkpoint_dir)
        restored = recovery_manager.load_checkpoint(strategy_name)

        assert restored is not None
        assert restored.positions == []
        assert restored.pending_orders == []
        assert restored.to_decimal_cash_balance() == Decimal("100000.00")

    def test_crash_with_alignment_metrics(self, checkpoint_dir, strategy_name):
        """Test crash recovery preserves shadow trading alignment metrics."""
        state_manager = StateManager(checkpoint_dir=checkpoint_dir)

        # Create checkpoint with alignment metrics
        checkpoint_with_metrics = StateCheckpoint(
            strategy_name=strategy_name,
            timestamp=datetime.now(),
            cash_balance="50000.00",
            alignment_metrics=AlignmentMetrics(
                signal_match_rate=0.92,
                slippage_error_bps=8.5,
                fill_rate_error_pct=1.2,
                backtest_signal_count=150,
                live_signal_count=138,
                last_updated=datetime.now(),
            ),
        )

        state_manager.save_checkpoint(strategy_name, checkpoint_with_metrics)

        # Simulate crash
        del state_manager

        # Restore
        recovery_manager = StateManager(checkpoint_dir=checkpoint_dir)
        restored = recovery_manager.load_checkpoint(strategy_name)

        # Verify alignment metrics preserved
        assert restored.alignment_metrics is not None
        assert restored.alignment_metrics.signal_match_rate == 0.92
        assert restored.alignment_metrics.slippage_error_bps == 8.5
        assert restored.alignment_metrics.backtest_signal_count == 150
        assert restored.alignment_metrics.live_signal_count == 138

    def test_multiple_crash_recovery_cycles(self, checkpoint_dir, strategy_name):
        """Test multiple crash → recovery cycles maintain consistency."""
        for cycle in range(3):
            state_manager = StateManager(checkpoint_dir=checkpoint_dir)

            checkpoint = StateCheckpoint(
                strategy_name=strategy_name,
                timestamp=datetime.now(),
                strategy_state={"cycle": cycle},
                cash_balance=str(Decimal("100000") + Decimal(cycle * 1000)),
            )

            state_manager.save_checkpoint(strategy_name, checkpoint)

            # Simulate crash
            del state_manager

            # Restore
            recovery_manager = StateManager(checkpoint_dir=checkpoint_dir)
            restored = recovery_manager.load_checkpoint(strategy_name)

            # Verify cycle state
            assert restored.strategy_state["cycle"] == cycle
            expected_balance = Decimal("100000") + Decimal(cycle * 1000)
            assert restored.to_decimal_cash_balance() == expected_balance

            del recovery_manager

    def test_no_checkpoint_on_first_start(self, checkpoint_dir, strategy_name):
        """Test engine start with no existing checkpoint."""
        state_manager = StateManager(checkpoint_dir=checkpoint_dir)

        # Attempt to load checkpoint (should return None)
        checkpoint = state_manager.load_checkpoint(strategy_name)

        assert checkpoint is None

    def test_checkpoint_cleanup_after_strategy_completion(self, checkpoint_dir, strategy_name):
        """Test checkpoint can be deleted when strategy completes."""
        state_manager = StateManager(checkpoint_dir=checkpoint_dir)

        # Create and save checkpoint
        checkpoint = StateCheckpoint(
            strategy_name=strategy_name,
            timestamp=datetime.now(),
            cash_balance="100000.00",
        )

        state_manager.save_checkpoint(strategy_name, checkpoint)

        # Verify checkpoint exists
        assert state_manager.load_checkpoint(strategy_name) is not None

        # Delete checkpoint (strategy completed)
        deleted = state_manager.delete_checkpoint(strategy_name)
        assert deleted is True

        # Verify checkpoint removed
        assert state_manager.load_checkpoint(strategy_name) is None


class TestCrashRecoveryWithReconciliation:
    """Integration tests for crash recovery with position reconciliation."""

    @pytest.mark.asyncio
    async def test_restore_with_reconciliation_discrepancy(self, checkpoint_dir, strategy_name):
        """Test state restoration detects position discrepancies."""

        from rustybt.live.brokers.base import BrokerAdapter
        from rustybt.live.reconciler import PositionReconciler

        # Mock broker with discrepant positions
        class MockBroker(BrokerAdapter):
            def __init__(self):
                self._connected = False

            async def connect(self):
                self._connected = True

            async def disconnect(self):
                self._connected = False

            async def submit_order(self, *args, **kwargs):
                return "mock-order-id"

            async def cancel_order(self, broker_order_id):
                pass

            async def get_account_info(self):
                return {"cash": Decimal("100000"), "equity": Decimal("100000")}

            async def get_positions(self):
                # Return discrepant positions
                return [
                    {"symbol": "AAPL", "amount": "150"},  # Different from checkpoint
                    {"symbol": "MSFT", "amount": "50"},  # Matches
                ]

            async def fetch_positions(self):
                return await self.get_positions()

            async def subscribe_market_data(self, assets):
                pass

            async def unsubscribe_market_data(self, assets):
                pass

            async def get_next_market_data(self):
                return None

            async def get_current_price(self, asset):
                return Decimal("100.00")

            def is_connected(self):
                return self._connected

        # Create checkpoint with known positions
        state_manager = StateManager(checkpoint_dir=checkpoint_dir)

        checkpoint = StateCheckpoint(
            strategy_name=strategy_name,
            timestamp=datetime.now(),
            positions=[
                PositionSnapshot(
                    asset="AAPL",
                    sid=1,
                    amount="100",  # Will be different from broker
                    cost_basis="150.00",
                    last_price="155.00",
                ),
                PositionSnapshot(
                    asset="MSFT",
                    sid=2,
                    amount="50",
                    cost_basis="320.00",
                    last_price="325.00",
                ),
            ],
            cash_balance="25000.00",
        )

        state_manager.save_checkpoint(strategy_name, checkpoint)

        # Simulate crash
        del state_manager

        # Restore and reconcile
        recovery_manager = StateManager(checkpoint_dir=checkpoint_dir)
        restored_checkpoint = recovery_manager.load_checkpoint(strategy_name)

        # Perform reconciliation
        broker = MockBroker()
        reconciler = PositionReconciler(broker, ReconciliationStrategy.WARN_ONLY)

        result = await reconciler.reconcile_positions(restored_checkpoint.positions)

        # Verify discrepancy detected
        assert len(result["discrepancies"]) > 0
        aapl_discrepancy = next((d for d in result["discrepancies"] if d.asset == "AAPL"), None)
        assert aapl_discrepancy is not None
        assert aapl_discrepancy.local_amount == Decimal("100")
        assert aapl_discrepancy.broker_amount == Decimal("150")
