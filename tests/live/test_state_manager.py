"""Unit tests for StateManager checkpoint and restoration."""

import json
import os
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from rustybt.live.models import (
    AlignmentMetrics,
    OrderSnapshot,
    PositionSnapshot,
    StateCheckpoint,
)
from rustybt.live.state_manager import CheckpointCorrupted, StateManager


@pytest.fixture
def temp_checkpoint_dir(tmp_path):
    """Create temporary checkpoint directory."""
    checkpoint_dir = tmp_path / "checkpoints"
    checkpoint_dir.mkdir()
    return checkpoint_dir


@pytest.fixture
def state_manager(temp_checkpoint_dir):
    """Create StateManager with temp directory."""
    return StateManager(checkpoint_dir=temp_checkpoint_dir)


@pytest.fixture
def sample_checkpoint():
    """Create sample checkpoint for testing."""
    return StateCheckpoint(
        strategy_name="test_strategy",
        timestamp=datetime.now(),
        strategy_state={"last_signal": "buy", "signal_strength": 0.75},
        positions=[
            PositionSnapshot(
                asset="AAPL",
                sid=1,
                amount="100",
                cost_basis="150.25",
                last_price="155.50",
            ),
            PositionSnapshot(
                asset="MSFT",
                sid=2,
                amount="50",
                cost_basis="320.00",
                last_price="325.75",
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


class TestStateCheckpointModel:
    """Test StateCheckpoint Pydantic model validation."""

    def test_checkpoint_creation(self, sample_checkpoint):
        """Test creating valid checkpoint."""
        assert sample_checkpoint.strategy_name == "test_strategy"
        assert len(sample_checkpoint.positions) == 2
        assert len(sample_checkpoint.pending_orders) == 1
        assert sample_checkpoint.to_decimal_cash_balance() == Decimal("25000.00")

    def test_position_snapshot_validation(self):
        """Test PositionSnapshot decimal validation."""
        pos = PositionSnapshot(
            asset="AAPL",
            sid=1,
            amount="100.5",
            cost_basis="150.25",
            last_price="155.50",
        )

        assert pos.to_decimal_amount() == Decimal("100.5")
        assert pos.to_decimal_cost_basis() == Decimal("150.25")
        assert pos.to_decimal_last_price() == Decimal("155.50")

    def test_position_snapshot_invalid_decimal(self):
        """Test PositionSnapshot rejects invalid decimal strings."""
        with pytest.raises(ValueError, match="Invalid decimal string"):
            PositionSnapshot(
                asset="AAPL",
                sid=1,
                amount="not_a_number",
                cost_basis="150.25",
                last_price="155.50",
            )

    def test_order_snapshot_validation(self):
        """Test OrderSnapshot decimal validation."""
        order = OrderSnapshot(
            order_id="order-123",
            asset="AAPL",
            sid=1,
            amount="50",
            order_type="limit",
            limit_price="100.50",
            status="pending",
            created_at=datetime.now(),
        )

        assert order.to_decimal_amount() == Decimal("50")
        assert order.to_decimal_limit_price() == Decimal("100.50")

    def test_order_snapshot_no_limit_price(self):
        """Test OrderSnapshot with no limit price (market order)."""
        order = OrderSnapshot(
            order_id="order-123",
            asset="AAPL",
            sid=1,
            amount="50",
            order_type="market",
            status="pending",
            created_at=datetime.now(),
        )

        assert order.to_decimal_limit_price() is None

    def test_checkpoint_staleness_detection(self):
        """Test checkpoint staleness detection."""
        # Fresh checkpoint
        fresh = StateCheckpoint(
            strategy_name="test",
            timestamp=datetime.now(),
            cash_balance="10000.00",
        )
        assert not fresh.is_stale(threshold_seconds=3600)

        # Stale checkpoint (2 hours old)
        stale = StateCheckpoint(
            strategy_name="test",
            timestamp=datetime.now() - timedelta(hours=2),
            cash_balance="10000.00",
        )
        assert stale.is_stale(threshold_seconds=3600)

    def test_alignment_metrics_validation(self):
        """Test AlignmentMetrics model."""
        metrics = AlignmentMetrics(
            signal_match_rate=0.95,
            slippage_error_bps=5.2,
            fill_rate_error_pct=0.3,
            backtest_signal_count=100,
            live_signal_count=95,
            last_updated=datetime.now(),
        )

        assert metrics.signal_match_rate == 0.95
        assert metrics.backtest_signal_count == 100

    def test_alignment_metrics_invalid_rate(self):
        """Test AlignmentMetrics rejects invalid signal_match_rate."""
        with pytest.raises(ValueError):
            AlignmentMetrics(
                signal_match_rate=1.5,  # Invalid: > 1.0
                slippage_error_bps=5.0,
                fill_rate_error_pct=0.3,
                backtest_signal_count=100,
                live_signal_count=95,
                last_updated=datetime.now(),
            )


class TestStateManager:
    """Test StateManager save/load operations."""

    def test_save_checkpoint_creates_file(self, state_manager, sample_checkpoint):
        """Test save_checkpoint creates JSON file."""
        strategy_name = "test_strategy"

        state_manager.save_checkpoint(strategy_name, sample_checkpoint)

        checkpoint_path = state_manager._get_checkpoint_path(strategy_name)
        assert checkpoint_path.exists()

    def test_save_checkpoint_valid_json(self, state_manager, sample_checkpoint):
        """Test saved checkpoint is valid JSON."""
        strategy_name = "test_strategy"

        state_manager.save_checkpoint(strategy_name, sample_checkpoint)

        checkpoint_path = state_manager._get_checkpoint_path(strategy_name)
        with open(checkpoint_path) as f:
            data = json.load(f)

        assert data["strategy_name"] == strategy_name
        assert len(data["positions"]) == 2
        assert data["cash_balance"] == "25000.00"

    def test_load_checkpoint_success(self, state_manager, sample_checkpoint):
        """Test load_checkpoint reads and validates checkpoint."""
        strategy_name = "test_strategy"

        # Save first
        state_manager.save_checkpoint(strategy_name, sample_checkpoint)

        # Load
        loaded = state_manager.load_checkpoint(strategy_name)

        assert loaded is not None
        assert loaded.strategy_name == strategy_name
        assert len(loaded.positions) == 2
        assert loaded.cash_balance == "25000.00"

    def test_load_checkpoint_not_found(self, state_manager):
        """Test load_checkpoint returns None for missing checkpoint."""
        loaded = state_manager.load_checkpoint("nonexistent_strategy")

        assert loaded is None

    def test_load_checkpoint_corrupted_json(self, state_manager, temp_checkpoint_dir):
        """Test load_checkpoint raises CheckpointCorrupted for invalid JSON."""
        strategy_name = "corrupted_strategy"
        checkpoint_path = state_manager._get_checkpoint_path(strategy_name)

        # Write invalid JSON
        with open(checkpoint_path, "w") as f:
            f.write("{ invalid json }")

        with pytest.raises(CheckpointCorrupted, match="corrupted"):
            state_manager.load_checkpoint(strategy_name)

    def test_atomic_write_uses_temp_file(self, state_manager, sample_checkpoint):
        """Test save_checkpoint uses temp file for atomic writes."""
        strategy_name = "test_strategy"

        # Monkey-patch os.rename to capture calls
        original_rename = os.rename
        rename_calls = []

        def mock_rename(src, dst):
            rename_calls.append((str(src), str(dst)))
            return original_rename(src, dst)

        os.rename = mock_rename

        try:
            state_manager.save_checkpoint(strategy_name, sample_checkpoint)

            # Verify rename was called (temp → final)
            assert len(rename_calls) == 1
            src, dst = rename_calls[0]
            assert src.endswith(".tmp")
            assert dst.endswith("_checkpoint.json")
        finally:
            os.rename = original_rename

    def test_atomic_write_no_temp_file_left_on_success(self, state_manager, sample_checkpoint):
        """Test temp file is removed after successful write."""
        strategy_name = "test_strategy"

        state_manager.save_checkpoint(strategy_name, sample_checkpoint)

        checkpoint_path = state_manager._get_checkpoint_path(strategy_name)
        temp_path = state_manager._get_temp_path(checkpoint_path)

        # Temp file should not exist
        assert not temp_path.exists()

    def test_delete_checkpoint(self, state_manager, sample_checkpoint):
        """Test delete_checkpoint removes checkpoint file."""
        strategy_name = "test_strategy"

        state_manager.save_checkpoint(strategy_name, sample_checkpoint)
        assert state_manager.delete_checkpoint(strategy_name) is True

        checkpoint_path = state_manager._get_checkpoint_path(strategy_name)
        assert not checkpoint_path.exists()

    def test_delete_checkpoint_not_found(self, state_manager):
        """Test delete_checkpoint returns False for missing checkpoint."""
        assert state_manager.delete_checkpoint("nonexistent") is False

    def test_list_checkpoints(self, state_manager, sample_checkpoint):
        """Test list_checkpoints returns all strategies."""
        state_manager.save_checkpoint("strategy_a", sample_checkpoint)
        state_manager.save_checkpoint("strategy_b", sample_checkpoint)

        checkpoints = state_manager.list_checkpoints()

        assert "strategy_a" in checkpoints
        assert "strategy_b" in checkpoints
        assert len(checkpoints) == 2

    def test_get_checkpoint_info(self, state_manager, sample_checkpoint):
        """Test get_checkpoint_info returns metadata."""
        strategy_name = "test_strategy"

        state_manager.save_checkpoint(strategy_name, sample_checkpoint)

        info = state_manager.get_checkpoint_info(strategy_name)

        assert info is not None
        assert info["strategy_name"] == strategy_name
        assert info["positions_count"] == 2
        assert info["pending_orders_count"] == 1
        assert "file_size_bytes" in info

    def test_get_checkpoint_info_not_found(self, state_manager):
        """Test get_checkpoint_info returns None for missing checkpoint."""
        info = state_manager.get_checkpoint_info("nonexistent")

        assert info is None

    def test_staleness_warning_logged(self, state_manager, capsys):
        """Test staleness warning is logged for old checkpoints."""
        strategy_name = "stale_strategy"

        # Create stale checkpoint
        stale_checkpoint = StateCheckpoint(
            strategy_name=strategy_name,
            timestamp=datetime.now() - timedelta(hours=2),
            cash_balance="10000.00",
        )

        state_manager.save_checkpoint(strategy_name, stale_checkpoint)

        # Load with 1 hour threshold
        state_manager = StateManager(
            checkpoint_dir=state_manager.checkpoint_dir, staleness_threshold_seconds=3600
        )

        loaded = state_manager.load_checkpoint(strategy_name)

        # Check output contains staleness warning
        captured = capsys.readouterr()
        assert "checkpoint_stale" in captured.out or "checkpoint_stale" in captured.err
        assert loaded is not None


class TestCheckpointRoundTrip:
    """Test full save/load round-trip scenarios."""

    def test_round_trip_preserves_all_data(self, state_manager, sample_checkpoint):
        """Test saving and loading preserves all checkpoint data."""
        strategy_name = "test_strategy"

        # Save
        state_manager.save_checkpoint(strategy_name, sample_checkpoint)

        # Load
        loaded = state_manager.load_checkpoint(strategy_name)

        # Verify all data preserved
        assert loaded.strategy_name == sample_checkpoint.strategy_name
        assert loaded.strategy_state == sample_checkpoint.strategy_state
        assert len(loaded.positions) == len(sample_checkpoint.positions)
        assert len(loaded.pending_orders) == len(sample_checkpoint.pending_orders)
        assert loaded.cash_balance == sample_checkpoint.cash_balance

        # Verify position details
        for original, loaded_pos in zip(
            sample_checkpoint.positions, loaded.positions, strict=False
        ):
            assert loaded_pos.asset == original.asset
            assert loaded_pos.amount == original.amount
            assert loaded_pos.cost_basis == original.cost_basis

    def test_round_trip_with_alignment_metrics(self, state_manager):
        """Test save/load with alignment metrics."""
        checkpoint = StateCheckpoint(
            strategy_name="shadow_strategy",
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

        state_manager.save_checkpoint("shadow_strategy", checkpoint)

        loaded = state_manager.load_checkpoint("shadow_strategy")

        assert loaded.alignment_metrics is not None
        assert loaded.alignment_metrics.signal_match_rate == 0.92
        assert loaded.alignment_metrics.backtest_signal_count == 150

    def test_round_trip_empty_positions_orders(self, state_manager):
        """Test save/load with no positions or orders."""
        checkpoint = StateCheckpoint(
            strategy_name="empty_strategy",
            timestamp=datetime.now(),
            cash_balance="100000.00",
        )

        state_manager.save_checkpoint("empty_strategy", checkpoint)

        loaded = state_manager.load_checkpoint("empty_strategy")

        assert loaded.positions == []
        assert loaded.pending_orders == []
        assert loaded.cash_balance == "100000.00"
