"""Unit tests for ExecutionQualityTracker."""

from datetime import datetime
from decimal import Decimal

import pytest

from rustybt.live.shadow.config import ShadowTradingConfig
from rustybt.live.shadow.execution_tracker import ExecutionQualityTracker


class TestExecutionQualityTracker:
    """Test execution quality tracking functionality."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return ShadowTradingConfig(
            enabled=True,
            signal_match_rate_min=Decimal("0.95"),
            slippage_error_bps_max=Decimal("50"),
            fill_rate_error_pct_max=Decimal("20"),
            commission_error_pct_max=Decimal("30"),
        )

    @pytest.fixture
    def tracker(self, config):
        """Create test tracker instance."""
        return ExecutionQualityTracker(config)

    def test_initialization(self, tracker, config):
        """Test tracker initializes correctly."""
        assert tracker.config == config
        assert len(tracker._live_fills) == 0
        metrics = tracker.calculate_metrics()
        assert metrics.sample_count == 0

    def test_add_live_fill(self, tracker):
        """Test adding live fill to tracker."""
        tracker.add_live_fill(
            order_id="order-001",
            signal_price=Decimal("100.00"),
            fill_price=Decimal("100.05"),
            fill_quantity=Decimal("100"),
            order_quantity=Decimal("100"),
            commission=Decimal("1.00"),
            timestamp=datetime.utcnow(),
        )

        assert len(tracker._live_fills) == 1
        fill = tracker._live_fills[0]
        assert fill["order_id"] == "order-001"
        assert fill["signal_price"] == Decimal("100.00")
        assert fill["fill_price"] == Decimal("100.05")
        assert fill["slippage_bps"] == Decimal("5.00")  # 5 bps slippage

    def test_slippage_calculation_buy(self, tracker):
        """Test slippage calculation for buy orders."""
        # Add expected (backtest) fill
        tracker.add_backtest_fill(
            order_id="buy-001",
            signal_price=Decimal("100.00"),
            fill_price=Decimal("100.05"),  # Expected 5 bps slip from model
            fill_quantity=Decimal("100"),
            order_quantity=Decimal("100"),
            commission=Decimal("1.00"),
            timestamp=datetime.utcnow(),
        )

        # Add actual (live) fill
        tracker.add_live_fill(
            order_id="buy-001",
            signal_price=Decimal("100.00"),
            fill_price=Decimal("100.10"),  # 10 cents worse
            fill_quantity=Decimal("100"),
            order_quantity=Decimal("100"),
            commission=Decimal("1.00"),
            timestamp=datetime.utcnow(),
        )

        metrics = tracker.calculate_metrics()
        # 10 cents on $100 = 10 bps actual
        assert metrics.actual_slippage_bps == Decimal("10.00")

    def test_slippage_calculation_sell(self, tracker):
        """Test slippage calculation for sell orders (negative price better)."""
        # Add expected (backtest) fill
        tracker.add_backtest_fill(
            order_id="sell-001",
            signal_price=Decimal("100.00"),
            fill_price=Decimal("99.98"),  # Expected 2 bps slip
            fill_quantity=Decimal("100"),
            order_quantity=Decimal("100"),
            commission=Decimal("1.00"),
            timestamp=datetime.utcnow(),
        )

        # Add actual (live) fill
        tracker.add_live_fill(
            order_id="sell-001",
            signal_price=Decimal("100.00"),
            fill_price=Decimal("99.95"),  # 5 cents worse for sell
            fill_quantity=Decimal("100"),
            order_quantity=Decimal("100"),
            commission=Decimal("1.00"),
            timestamp=datetime.utcnow(),
        )

        metrics = tracker.calculate_metrics()
        # 5 cents on $100 = 5 bps
        assert metrics.actual_slippage_bps == Decimal("5.00")

    def test_fill_rate_calculation(self, tracker):
        """Test fill rate calculation for partial fills."""
        # Backtest fill 1 (full fill expected)
        tracker.add_backtest_fill(
            order_id="full-001",
            signal_price=Decimal("100.00"),
            fill_price=Decimal("100.00"),
            fill_quantity=Decimal("100"),
            order_quantity=Decimal("100"),
            commission=Decimal("1.00"),
            timestamp=datetime.utcnow(),
        )

        # Live fill 1 (full fill)
        tracker.add_live_fill(
            order_id="full-001",
            signal_price=Decimal("100.00"),
            fill_price=Decimal("100.00"),
            fill_quantity=Decimal("100"),
            order_quantity=Decimal("100"),
            commission=Decimal("1.00"),
            timestamp=datetime.utcnow(),
        )

        # Backtest fill 2 (full fill expected)
        tracker.add_backtest_fill(
            order_id="partial-001",
            signal_price=Decimal("100.00"),
            fill_price=Decimal("100.00"),
            fill_quantity=Decimal("100"),
            order_quantity=Decimal("100"),
            commission=Decimal("1.00"),
            timestamp=datetime.utcnow(),
        )

        # Live fill 2 (partial fill - 50%)
        tracker.add_live_fill(
            order_id="partial-001",
            signal_price=Decimal("100.00"),
            fill_price=Decimal("100.00"),
            fill_quantity=Decimal("50"),
            order_quantity=Decimal("100"),
            commission=Decimal("0.50"),
            timestamp=datetime.utcnow(),
        )

        metrics = tracker.calculate_metrics()
        # Average fill rate: (100% + 50%) / 2 = 75%
        assert metrics.fill_rate_actual == Decimal("0.75")
        assert metrics.sample_count == 2

    def test_commission_tracking(self, tracker):
        """Test commission tracking across fills."""
        # Backtest fills
        tracker.add_backtest_fill(
            order_id="comm-001",
            signal_price=Decimal("100.00"),
            fill_price=Decimal("100.00"),
            fill_quantity=Decimal("100"),
            order_quantity=Decimal("100"),
            commission=Decimal("2.00"),  # Expected commission
            timestamp=datetime.utcnow(),
        )

        tracker.add_backtest_fill(
            order_id="comm-002",
            signal_price=Decimal("200.00"),
            fill_price=Decimal("200.00"),
            fill_quantity=Decimal("50"),
            order_quantity=Decimal("50"),
            commission=Decimal("2.00"),  # Expected commission
            timestamp=datetime.utcnow(),
        )

        # Live fills
        tracker.add_live_fill(
            order_id="comm-001",
            signal_price=Decimal("100.00"),
            fill_price=Decimal("100.00"),
            fill_quantity=Decimal("100"),
            order_quantity=Decimal("100"),
            commission=Decimal("2.50"),
            timestamp=datetime.utcnow(),
        )

        tracker.add_live_fill(
            order_id="comm-002",
            signal_price=Decimal("200.00"),
            fill_price=Decimal("200.00"),
            fill_quantity=Decimal("50"),
            order_quantity=Decimal("50"),
            commission=Decimal("2.50"),
            timestamp=datetime.utcnow(),
        )

        metrics = tracker.calculate_metrics()
        # Average commission: (2.50 + 2.50) / 2 = 2.50
        assert metrics.commission_actual == Decimal("2.50")

    def test_zero_slippage(self, tracker):
        """Test metrics when fills match signal price exactly."""
        tracker.add_live_fill(
            order_id="perfect-001",
            signal_price=Decimal("100.00"),
            fill_price=Decimal("100.00"),  # Exact match
            fill_quantity=Decimal("100"),
            order_quantity=Decimal("100"),
            commission=Decimal("1.00"),
            timestamp=datetime.utcnow(),
        )

        metrics = tracker.calculate_metrics()
        assert metrics.actual_slippage_bps == Decimal("0.00")

    def test_metrics_with_no_fills(self, tracker):
        """Test metrics calculation with no fills (edge case)."""
        metrics = tracker.calculate_metrics()

        assert metrics.actual_slippage_bps == Decimal("0")
        assert metrics.fill_rate_actual == Decimal("1")
        assert metrics.commission_actual == Decimal("0")
        assert metrics.sample_count == 0

    def test_reset_clears_fills(self, tracker):
        """Test reset clears fill history."""
        tracker.add_live_fill(
            order_id="reset-001",
            signal_price=Decimal("100.00"),
            fill_price=Decimal("100.05"),
            fill_quantity=Decimal("100"),
            order_quantity=Decimal("100"),
            commission=Decimal("1.00"),
            timestamp=datetime.utcnow(),
        )

        assert len(tracker._live_fills) == 1

        tracker.reset()

        assert len(tracker._live_fills) == 0
        metrics = tracker.calculate_metrics()
        assert metrics.sample_count == 0

    def test_large_slippage(self, tracker):
        """Test tracking of large slippage scenario."""
        # Backtest fill
        tracker.add_backtest_fill(
            order_id="large-slip-001",
            signal_price=Decimal("100.00"),
            fill_price=Decimal("100.10"),  # Expected 10 bps
            fill_quantity=Decimal("100"),
            order_quantity=Decimal("100"),
            commission=Decimal("1.00"),
            timestamp=datetime.utcnow(),
        )

        # Live fill with large slippage
        tracker.add_live_fill(
            order_id="large-slip-001",
            signal_price=Decimal("100.00"),
            fill_price=Decimal("100.50"),  # 50 cents = 50 bps
            fill_quantity=Decimal("100"),
            order_quantity=Decimal("100"),
            commission=Decimal("1.00"),
            timestamp=datetime.utcnow(),
        )

        metrics = tracker.calculate_metrics()
        assert metrics.actual_slippage_bps == Decimal("50.00")

    def test_multiple_fills_average(self, tracker):
        """Test averaging across multiple fills."""
        # Backtest fills
        tracker.add_backtest_fill(
            order_id="avg-001",
            signal_price=Decimal("100.00"),
            fill_price=Decimal("100.02"),
            fill_quantity=Decimal("100"),
            order_quantity=Decimal("100"),
            commission=Decimal("1.00"),
            timestamp=datetime.utcnow(),
        )

        tracker.add_backtest_fill(
            order_id="avg-002",
            signal_price=Decimal("100.00"),
            fill_price=Decimal("100.03"),
            fill_quantity=Decimal("100"),
            order_quantity=Decimal("100"),
            commission=Decimal("1.00"),
            timestamp=datetime.utcnow(),
        )

        # Live fills - 5 bps slippage
        tracker.add_live_fill(
            order_id="avg-001",
            signal_price=Decimal("100.00"),
            fill_price=Decimal("100.05"),
            fill_quantity=Decimal("100"),
            order_quantity=Decimal("100"),
            commission=Decimal("1.00"),
            timestamp=datetime.utcnow(),
        )

        # Live fills - 15 bps slippage
        tracker.add_live_fill(
            order_id="avg-002",
            signal_price=Decimal("100.00"),
            fill_price=Decimal("100.15"),
            fill_quantity=Decimal("100"),
            order_quantity=Decimal("100"),
            commission=Decimal("1.00"),
            timestamp=datetime.utcnow(),
        )

        metrics = tracker.calculate_metrics()
        # Average: (5 + 15) / 2 = 10 bps
        assert metrics.actual_slippage_bps == Decimal("10.00")
