"""Unit tests for position reconciliation."""

from datetime import datetime
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from rustybt.live.brokers.base import BrokerAdapter
from rustybt.live.models import (
    DiscrepancySeverity,
    DiscrepancyType,
    OrderSnapshot,
    PositionSnapshot,
    ReconciliationStrategy,
)
from rustybt.live.reconciler import PositionReconciler, ReconciliationError


class MockBrokerAdapter(BrokerAdapter):
    """Mock broker adapter for testing reconciliation."""

    def __init__(
        self,
        mock_positions: list[dict],
        mock_cash: Decimal = Decimal("100000.00"),
        mock_orders: list[dict] = None,
    ):
        """Initialize with mock data.

        Args:
            mock_positions: List of position dicts with 'symbol' and 'amount'
            mock_cash: Mock cash balance
            mock_orders: List of open order dicts
        """
        self._mock_positions = mock_positions
        self._mock_cash = mock_cash
        self._mock_orders = mock_orders or []
        self._connected = False

    async def connect(self) -> None:
        """Mock connect."""
        self._connected = True

    async def disconnect(self) -> None:
        """Mock disconnect."""
        self._connected = False

    async def submit_order(self, *args, **kwargs) -> str:
        """Mock submit order."""
        return "mock-order-id"

    async def cancel_order(self, broker_order_id: str) -> None:
        """Mock cancel order."""
        pass

    async def get_account_info(self) -> dict:
        """Mock account info."""
        return {"cash": self._mock_cash, "equity": Decimal("100000.00")}

    async def get_positions(self) -> list[dict]:
        """Return mock positions."""
        return self._mock_positions

    async def get_open_orders(self) -> list[dict]:
        """Return mock open orders."""
        return self._mock_orders

    async def subscribe_market_data(self, assets) -> None:
        """Mock subscribe."""
        pass

    async def unsubscribe_market_data(self, assets) -> None:
        """Mock unsubscribe."""
        pass

    async def get_next_market_data(self):
        """Mock get next market data."""
        return None

    async def get_current_price(self, asset) -> Decimal:
        """Mock get current price."""
        return Decimal("100.00")

    def is_connected(self) -> bool:
        """Mock is connected."""
        return self._connected


class TestPositionReconciliation:
    """Test position reconciliation functionality."""

    @pytest.mark.asyncio
    async def test_no_discrepancies(self):
        """Test reconciliation with matching positions."""
        local_positions = [
            PositionSnapshot(
                asset="AAPL", sid=1, amount="100", cost_basis="150.00", last_price="155.00"
            ),
            PositionSnapshot(
                asset="MSFT", sid=2, amount="50", cost_basis="320.00", last_price="325.00"
            ),
        ]

        broker_positions = [
            {"symbol": "AAPL", "amount": "100"},
            {"symbol": "MSFT", "amount": "50"},
        ]

        broker = MockBrokerAdapter(broker_positions)
        reconciler = PositionReconciler(broker, ReconciliationStrategy.WARN_ONLY)

        report = await reconciler.reconcile_all(
            local_positions=local_positions, local_cash=Decimal("100000.00")
        )

        assert report.total_discrepancy_count() == 0
        assert report.summary == "No discrepancies detected"

    @pytest.mark.asyncio
    async def test_quantity_mismatch_minor(self):
        """Test minor quantity mismatch (<1%)."""
        local_positions = [
            PositionSnapshot(
                asset="AAPL", sid=1, amount="1000", cost_basis="150.00", last_price="155.00"
            ),
        ]

        # 0.5% difference (1000 vs 1005)
        broker_positions = [{"symbol": "AAPL", "amount": "1005"}]

        broker = MockBrokerAdapter(broker_positions)
        reconciler = PositionReconciler(broker, ReconciliationStrategy.WARN_ONLY)

        report = await reconciler.reconcile_all(
            local_positions=local_positions, local_cash=Decimal("100000.00")
        )

        assert len(report.position_discrepancies) == 1
        disc = report.position_discrepancies[0]
        assert disc.discrepancy_type == DiscrepancyType.QUANTITY_MISMATCH
        assert disc.severity == DiscrepancySeverity.MINOR

    @pytest.mark.asyncio
    async def test_quantity_mismatch_moderate(self):
        """Test moderate quantity mismatch (1-5%)."""
        local_positions = [
            PositionSnapshot(
                asset="AAPL", sid=1, amount="100", cost_basis="150.00", last_price="155.00"
            ),
        ]

        # 3% difference (100 vs 103)
        broker_positions = [{"symbol": "AAPL", "amount": "103"}]

        broker = MockBrokerAdapter(broker_positions)
        reconciler = PositionReconciler(broker, ReconciliationStrategy.WARN_ONLY)

        report = await reconciler.reconcile_all(
            local_positions=local_positions, local_cash=Decimal("100000.00")
        )

        assert len(report.position_discrepancies) == 1
        disc = report.position_discrepancies[0]
        assert disc.discrepancy_type == DiscrepancyType.QUANTITY_MISMATCH
        assert disc.severity == DiscrepancySeverity.MODERATE

    @pytest.mark.asyncio
    async def test_quantity_mismatch_critical(self):
        """Test critical quantity mismatch (>5%)."""
        local_positions = [
            PositionSnapshot(
                asset="AAPL", sid=1, amount="100", cost_basis="150.00", last_price="155.00"
            ),
        ]

        # 50% difference (100 vs 150)
        broker_positions = [{"symbol": "AAPL", "amount": "150"}]

        broker = MockBrokerAdapter(broker_positions)
        reconciler = PositionReconciler(broker, ReconciliationStrategy.WARN_ONLY)

        report = await reconciler.reconcile_all(
            local_positions=local_positions, local_cash=Decimal("100000.00")
        )

        assert len(report.position_discrepancies) == 1
        disc = report.position_discrepancies[0]
        assert disc.discrepancy_type == DiscrepancyType.QUANTITY_MISMATCH
        assert disc.severity == DiscrepancySeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_side_mismatch(self):
        """Test side mismatch (long vs short)."""
        local_positions = [
            PositionSnapshot(
                asset="AAPL", sid=1, amount="100", cost_basis="150.00", last_price="155.00"
            ),
        ]

        # Opposite side
        broker_positions = [{"symbol": "AAPL", "amount": "-100"}]

        broker = MockBrokerAdapter(broker_positions)
        reconciler = PositionReconciler(broker, ReconciliationStrategy.WARN_ONLY)

        report = await reconciler.reconcile_all(
            local_positions=local_positions, local_cash=Decimal("100000.00")
        )

        assert len(report.position_discrepancies) == 1
        disc = report.position_discrepancies[0]
        assert disc.discrepancy_type == DiscrepancyType.SIDE_MISMATCH
        assert disc.severity == DiscrepancySeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_missing_broker_position(self):
        """Test position exists locally but not at broker."""
        local_positions = [
            PositionSnapshot(
                asset="AAPL", sid=1, amount="100", cost_basis="150.00", last_price="155.00"
            ),
        ]

        broker_positions = []  # No positions at broker

        broker = MockBrokerAdapter(broker_positions)
        reconciler = PositionReconciler(broker, ReconciliationStrategy.WARN_ONLY)

        report = await reconciler.reconcile_all(
            local_positions=local_positions, local_cash=Decimal("100000.00")
        )

        assert len(report.position_discrepancies) == 1
        disc = report.position_discrepancies[0]
        assert disc.discrepancy_type == DiscrepancyType.MISSING_BROKER
        assert disc.severity == DiscrepancySeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_missing_local_position(self):
        """Test position exists at broker but not locally."""
        local_positions = []  # No local positions

        broker_positions = [{"symbol": "AAPL", "amount": "100"}]

        broker = MockBrokerAdapter(broker_positions)
        reconciler = PositionReconciler(broker, ReconciliationStrategy.WARN_ONLY)

        report = await reconciler.reconcile_all(
            local_positions=local_positions, local_cash=Decimal("100000.00")
        )

        assert len(report.position_discrepancies) == 1
        disc = report.position_discrepancies[0]
        assert disc.discrepancy_type == DiscrepancyType.MISSING_LOCAL
        assert disc.severity == DiscrepancySeverity.CRITICAL


class TestCashReconciliation:
    """Test cash balance reconciliation functionality."""

    @pytest.mark.asyncio
    async def test_cash_within_tolerance(self):
        """Test cash balance within tolerance (1%)."""
        local_cash = Decimal("100000.00")
        broker_cash = Decimal("100500.00")  # 0.5% difference

        broker = MockBrokerAdapter([], mock_cash=broker_cash)
        reconciler = PositionReconciler(broker, ReconciliationStrategy.WARN_ONLY)

        report = await reconciler.reconcile_all(local_positions=[], local_cash=local_cash)

        # Should be within default 1% tolerance
        assert report.cash_discrepancy is None

    @pytest.mark.asyncio
    async def test_cash_exceeds_tolerance(self):
        """Test cash balance exceeds tolerance."""
        local_cash = Decimal("100000.00")
        broker_cash = Decimal("106000.00")  # 6% difference

        broker = MockBrokerAdapter([], mock_cash=broker_cash)
        reconciler = PositionReconciler(broker, ReconciliationStrategy.WARN_ONLY)

        report = await reconciler.reconcile_all(local_positions=[], local_cash=local_cash)

        assert report.cash_discrepancy is not None
        assert report.cash_discrepancy.severity == DiscrepancySeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_cash_custom_tolerance(self):
        """Test cash reconciliation with custom tolerance."""
        local_cash = Decimal("100000.00")
        broker_cash = Decimal("103000.00")  # 3% difference

        broker = MockBrokerAdapter([], mock_cash=broker_cash)
        # Set tolerance to 5%
        reconciler = PositionReconciler(
            broker, ReconciliationStrategy.WARN_ONLY, cash_tolerance_pct=0.05
        )

        report = await reconciler.reconcile_all(local_positions=[], local_cash=local_cash)

        # 3% difference should be within 5% tolerance
        assert report.cash_discrepancy is None


class TestOrderReconciliation:
    """Test order reconciliation functionality."""

    @pytest.mark.asyncio
    async def test_matching_orders(self):
        """Test order reconciliation with matching orders."""
        local_orders = [
            OrderSnapshot(
                order_id="order-1",
                asset="AAPL",
                sid=1,
                amount="100",
                order_type="limit",
                limit_price="150.00",
                broker_order_id="broker-order-1",
                status="pending",
                created_at=datetime.now(),
            ),
        ]

        broker_orders = [{"order_id": "broker-order-1", "asset": "AAPL", "status": "pending"}]

        broker = MockBrokerAdapter([], mock_orders=broker_orders)
        reconciler = PositionReconciler(broker, ReconciliationStrategy.WARN_ONLY)

        report = await reconciler.reconcile_all(
            local_positions=[],
            local_cash=Decimal("100000.00"),
            local_orders=local_orders,
        )

        assert len(report.order_discrepancies) == 0

    @pytest.mark.asyncio
    async def test_orphaned_local_order(self):
        """Test order exists locally but not at broker."""
        local_orders = [
            OrderSnapshot(
                order_id="order-1",
                asset="AAPL",
                sid=1,
                amount="100",
                order_type="limit",
                limit_price="150.00",
                broker_order_id="broker-order-1",
                status="pending",
                created_at=datetime.now(),
            ),
        ]

        broker_orders = []  # No broker orders

        broker = MockBrokerAdapter([], mock_orders=broker_orders)
        reconciler = PositionReconciler(broker, ReconciliationStrategy.WARN_ONLY)

        report = await reconciler.reconcile_all(
            local_positions=[],
            local_cash=Decimal("100000.00"),
            local_orders=local_orders,
        )

        assert len(report.order_discrepancies) == 1
        disc = report.order_discrepancies[0]
        assert disc.discrepancy_type == "orphaned_local"

    @pytest.mark.asyncio
    async def test_orphaned_broker_order(self):
        """Test order exists at broker but not locally."""
        local_orders = []  # No local orders

        broker_orders = [{"order_id": "broker-order-1", "asset": "AAPL", "status": "pending"}]

        broker = MockBrokerAdapter([], mock_orders=broker_orders)
        reconciler = PositionReconciler(broker, ReconciliationStrategy.WARN_ONLY)

        report = await reconciler.reconcile_all(
            local_positions=[],
            local_cash=Decimal("100000.00"),
            local_orders=local_orders,
        )

        assert len(report.order_discrepancies) == 1
        disc = report.order_discrepancies[0]
        assert disc.discrepancy_type == "orphaned_broker"

    @pytest.mark.asyncio
    async def test_order_status_mismatch(self):
        """Test order with mismatched status."""
        local_orders = [
            OrderSnapshot(
                order_id="order-1",
                asset="AAPL",
                sid=1,
                amount="100",
                order_type="limit",
                limit_price="150.00",
                broker_order_id="broker-order-1",
                status="pending",
                created_at=datetime.now(),
            ),
        ]

        broker_orders = [{"order_id": "broker-order-1", "asset": "AAPL", "status": "filled"}]

        broker = MockBrokerAdapter([], mock_orders=broker_orders)
        reconciler = PositionReconciler(broker, ReconciliationStrategy.WARN_ONLY)

        report = await reconciler.reconcile_all(
            local_positions=[],
            local_cash=Decimal("100000.00"),
            local_orders=local_orders,
        )

        assert len(report.order_discrepancies) == 1
        disc = report.order_discrepancies[0]
        assert disc.discrepancy_type == "status_mismatch"
        assert disc.local_status == "pending"
        assert disc.broker_status == "filled"


class TestReconciliationStrategies:
    """Test reconciliation strategy application."""

    @pytest.mark.asyncio
    async def test_warn_only_strategy(self):
        """Test WARN_ONLY strategy logs but continues."""
        local_positions = [
            PositionSnapshot(
                asset="AAPL", sid=1, amount="100", cost_basis="150.00", last_price="155.00"
            ),
        ]
        broker_positions = [{"symbol": "AAPL", "amount": "150"}]

        broker = MockBrokerAdapter(broker_positions)
        reconciler = PositionReconciler(broker, ReconciliationStrategy.WARN_ONLY)

        report = await reconciler.reconcile_all(
            local_positions=local_positions, local_cash=Decimal("100000.00")
        )

        assert "WARN_ONLY" in report.actions_taken[0]

    @pytest.mark.asyncio
    async def test_sync_to_broker_strategy(self):
        """Test SYNC_TO_BROKER strategy recommends update."""
        local_positions = [
            PositionSnapshot(
                asset="AAPL", sid=1, amount="100", cost_basis="150.00", last_price="155.00"
            ),
        ]
        broker_positions = [{"symbol": "AAPL", "amount": "150"}]

        broker = MockBrokerAdapter(broker_positions)
        reconciler = PositionReconciler(broker, ReconciliationStrategy.SYNC_TO_BROKER)

        report = await reconciler.reconcile_all(
            local_positions=local_positions, local_cash=Decimal("100000.00")
        )

        assert "SYNC_TO_BROKER" in report.actions_taken[0]

    @pytest.mark.asyncio
    async def test_sync_to_local_strategy(self):
        """Test SYNC_TO_LOCAL strategy recommends orders."""
        local_positions = [
            PositionSnapshot(
                asset="AAPL", sid=1, amount="100", cost_basis="150.00", last_price="155.00"
            ),
        ]
        broker_positions = [{"symbol": "AAPL", "amount": "150"}]

        broker = MockBrokerAdapter(broker_positions)
        reconciler = PositionReconciler(broker, ReconciliationStrategy.SYNC_TO_LOCAL)

        report = await reconciler.reconcile_all(
            local_positions=local_positions, local_cash=Decimal("100000.00")
        )

        assert "SYNC_TO_LOCAL" in report.actions_taken[0]

    @pytest.mark.asyncio
    async def test_halt_and_alert_strategy(self):
        """Test HALT_AND_ALERT strategy raises error."""
        local_positions = [
            PositionSnapshot(
                asset="AAPL", sid=1, amount="100", cost_basis="150.00", last_price="155.00"
            ),
        ]
        broker_positions = [{"symbol": "AAPL", "amount": "150"}]

        broker = MockBrokerAdapter(broker_positions)
        reconciler = PositionReconciler(broker, ReconciliationStrategy.HALT_AND_ALERT)

        with pytest.raises(ReconciliationError, match="halted for manual intervention"):
            await reconciler.reconcile_all(
                local_positions=local_positions, local_cash=Decimal("100000.00")
            )


class TestReconciliationReport:
    """Test ReconciliationReport functionality."""

    @pytest.mark.asyncio
    async def test_report_summary(self):
        """Test report summary generation."""
        local_positions = [
            PositionSnapshot(
                asset="AAPL", sid=1, amount="100", cost_basis="150.00", last_price="155.00"
            ),
        ]
        broker_positions = [{"symbol": "AAPL", "amount": "150"}]
        broker_cash = Decimal("110000.00")  # 10% difference

        broker = MockBrokerAdapter(broker_positions, mock_cash=broker_cash)
        reconciler = PositionReconciler(broker, ReconciliationStrategy.WARN_ONLY)

        report = await reconciler.reconcile_all(
            local_positions=local_positions, local_cash=Decimal("100000.00")
        )

        assert "Found 2 discrepancies" in report.summary
        assert "1 positions" in report.summary
        assert "1 cash" in report.summary

    @pytest.mark.asyncio
    async def test_report_has_critical_discrepancies(self):
        """Test has_critical_discrepancies method."""
        local_positions = [
            PositionSnapshot(
                asset="AAPL", sid=1, amount="100", cost_basis="150.00", last_price="155.00"
            ),
        ]
        broker_positions = []  # Missing position (critical)

        broker = MockBrokerAdapter(broker_positions)
        reconciler = PositionReconciler(broker, ReconciliationStrategy.WARN_ONLY)

        report = await reconciler.reconcile_all(
            local_positions=local_positions, local_cash=Decimal("100000.00")
        )

        assert report.has_critical_discrepancies()

    @pytest.mark.asyncio
    async def test_report_total_discrepancy_count(self):
        """Test total_discrepancy_count method."""
        local_positions = [
            PositionSnapshot(
                asset="AAPL", sid=1, amount="100", cost_basis="150.00", last_price="155.00"
            ),
        ]
        broker_positions = [{"symbol": "AAPL", "amount": "150"}]
        broker_cash = Decimal("110000.00")  # Cash discrepancy

        broker = MockBrokerAdapter(broker_positions, mock_cash=broker_cash)
        reconciler = PositionReconciler(broker, ReconciliationStrategy.WARN_ONLY)

        report = await reconciler.reconcile_all(
            local_positions=local_positions, local_cash=Decimal("100000.00")
        )

        # 1 position + 1 cash = 2 total
        assert report.total_discrepancy_count() == 2


class TestReconcilerConfiguration:
    """Test reconciler configuration and updates."""

    @pytest.mark.asyncio
    async def test_set_strategy(self):
        """Test changing reconciliation strategy."""
        broker = MockBrokerAdapter([])
        reconciler = PositionReconciler(broker, ReconciliationStrategy.WARN_ONLY)

        reconciler.set_strategy(ReconciliationStrategy.SYNC_TO_BROKER)
        assert reconciler._reconciliation_strategy == ReconciliationStrategy.SYNC_TO_BROKER

    @pytest.mark.asyncio
    async def test_set_cash_tolerance(self):
        """Test changing cash tolerance."""
        broker = MockBrokerAdapter([])
        reconciler = PositionReconciler(broker, ReconciliationStrategy.WARN_ONLY)

        reconciler.set_cash_tolerance(0.05)
        assert reconciler._cash_tolerance_pct == 0.05


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_everything(self):
        """Test reconciliation with no positions, cash, or orders."""
        broker = MockBrokerAdapter([])
        reconciler = PositionReconciler(broker, ReconciliationStrategy.WARN_ONLY)

        report = await reconciler.reconcile_all(
            local_positions=[], local_cash=Decimal("100000.00"), local_orders=[]
        )

        # Cash should match within tolerance
        assert report.total_discrepancy_count() == 0

    @pytest.mark.asyncio
    async def test_decimal_precision(self):
        """Test that Decimal precision is preserved."""
        local_positions = [
            PositionSnapshot(
                asset="AAPL",
                sid=1,
                amount="100.123456789",
                cost_basis="150.00",
                last_price="155.00",
            ),
        ]
        broker_positions = [{"symbol": "AAPL", "amount": "100.123456789"}]

        broker = MockBrokerAdapter(broker_positions)
        reconciler = PositionReconciler(broker, ReconciliationStrategy.WARN_ONLY)

        report = await reconciler.reconcile_all(
            local_positions=local_positions, local_cash=Decimal("100000.00")
        )

        # Should match exactly with full precision
        assert report.total_discrepancy_count() == 0

    @pytest.mark.asyncio
    async def test_multiple_discrepancy_types(self):
        """Test detection of multiple discrepancy types simultaneously."""
        local_positions = [
            PositionSnapshot(
                asset="AAPL", sid=1, amount="100", cost_basis="150.00", last_price="155.00"
            ),
            PositionSnapshot(
                asset="MSFT", sid=2, amount="50", cost_basis="320.00", last_price="325.00"
            ),
        ]

        broker_positions = [
            {"symbol": "AAPL", "amount": "150"},  # Quantity mismatch
            {"symbol": "GOOGL", "amount": "25"},  # Missing local
            # MSFT missing at broker
        ]

        broker = MockBrokerAdapter(broker_positions)
        reconciler = PositionReconciler(broker, ReconciliationStrategy.WARN_ONLY)

        report = await reconciler.reconcile_all(
            local_positions=local_positions, local_cash=Decimal("100000.00")
        )

        assert len(report.position_discrepancies) == 3
        types = {d.discrepancy_type for d in report.position_discrepancies}
        assert DiscrepancyType.QUANTITY_MISMATCH in types
        assert DiscrepancyType.MISSING_LOCAL in types
        assert DiscrepancyType.MISSING_BROKER in types


class TestPropertyBasedDiscrepancyCalculations:
    """Property-based tests for discrepancy percentage calculations using Hypothesis."""

    @given(
        local=st.decimals(min_value=Decimal("-10000"), max_value=Decimal("10000"), allow_nan=False),
        broker=st.decimals(
            min_value=Decimal("-10000"), max_value=Decimal("10000"), allow_nan=False
        ),
    )
    def test_discrepancy_percentage_is_bounded(self, local, broker):
        """Property: Discrepancy percentage is always between 0.0 and 1.0."""
        broker_adapter = MockBrokerAdapter([])
        reconciler = PositionReconciler(broker_adapter, ReconciliationStrategy.WARN_ONLY)

        discrepancy_pct = reconciler._calculate_discrepancy_percentage(local, broker)

        assert 0.0 <= discrepancy_pct <= 1.0, (
            f"Discrepancy percentage {discrepancy_pct} is out of bounds [0.0, 1.0] "
            f"for local={local}, broker={broker}"
        )

    @given(
        value=st.decimals(min_value=Decimal("-10000"), max_value=Decimal("10000"), allow_nan=False)
    )
    def test_identical_values_have_zero_discrepancy(self, value):
        """Property: Identical local and broker values always yield 0% discrepancy."""
        broker_adapter = MockBrokerAdapter([])
        reconciler = PositionReconciler(broker_adapter, ReconciliationStrategy.WARN_ONLY)

        discrepancy_pct = reconciler._calculate_discrepancy_percentage(value, value)

        assert (
            discrepancy_pct == 0.0
        ), f"Identical values should have 0% discrepancy, got {discrepancy_pct} for value={value}"

    def test_none_values_have_expected_discrepancy(self):
        """Property: None values result in predictable discrepancy percentages."""
        broker_adapter = MockBrokerAdapter([])
        reconciler = PositionReconciler(broker_adapter, ReconciliationStrategy.WARN_ONLY)

        # Both None -> 0% discrepancy
        assert reconciler._calculate_discrepancy_percentage(None, None) == 0.0

        # One None -> 100% discrepancy
        assert reconciler._calculate_discrepancy_percentage(None, Decimal("100")) == 1.0
        assert reconciler._calculate_discrepancy_percentage(Decimal("100"), None) == 1.0

    @given(
        local=st.decimals(min_value=Decimal("1"), max_value=Decimal("10000"), allow_nan=False),
        broker=st.decimals(min_value=Decimal("1"), max_value=Decimal("10000"), allow_nan=False),
    )
    def test_discrepancy_is_symmetric(self, local, broker):
        """Property: Discrepancy percentage is symmetric (swap local/broker gives same result)."""
        broker_adapter = MockBrokerAdapter([])
        reconciler = PositionReconciler(broker_adapter, ReconciliationStrategy.WARN_ONLY)

        discrepancy_forward = reconciler._calculate_discrepancy_percentage(local, broker)
        discrepancy_reverse = reconciler._calculate_discrepancy_percentage(broker, local)

        assert abs(discrepancy_forward - discrepancy_reverse) < 1e-10, (
            f"Discrepancy should be symmetric: forward={discrepancy_forward}, "
            f"reverse={discrepancy_reverse}, local={local}, broker={broker}"
        )

    @given(base=st.decimals(min_value=Decimal("100"), max_value=Decimal("1000"), allow_nan=False))
    def test_small_percentage_differences_classified_correctly(self, base):
        """Property: Known percentage differences result in correct severity classification."""
        broker_adapter = MockBrokerAdapter([])
        reconciler = PositionReconciler(broker_adapter, ReconciliationStrategy.WARN_ONLY)

        # 0.5% difference (should be MINOR)
        other = base * Decimal("1.005")
        discrepancy_pct = reconciler._calculate_discrepancy_percentage(base, other)
        severity = reconciler._classify_position_severity(
            discrepancy_pct, DiscrepancyType.QUANTITY_MISMATCH
        )
        assert severity == DiscrepancySeverity.MINOR, (
            f"0.5% difference should be MINOR, got {severity} "
            f"(base={base}, other={other}, pct={discrepancy_pct})"
        )

        # 3% difference (should be MODERATE)
        other = base * Decimal("1.03")
        discrepancy_pct = reconciler._calculate_discrepancy_percentage(base, other)
        severity = reconciler._classify_position_severity(
            discrepancy_pct, DiscrepancyType.QUANTITY_MISMATCH
        )
        assert severity == DiscrepancySeverity.MODERATE, (
            f"3% difference should be MODERATE, got {severity} "
            f"(base={base}, other={other}, pct={discrepancy_pct})"
        )

        # 10% difference (should be CRITICAL)
        other = base * Decimal("1.10")
        discrepancy_pct = reconciler._calculate_discrepancy_percentage(base, other)
        severity = reconciler._classify_position_severity(
            discrepancy_pct, DiscrepancyType.QUANTITY_MISMATCH
        )
        assert severity == DiscrepancySeverity.CRITICAL, (
            f"10% difference should be CRITICAL, got {severity} "
            f"(base={base}, other={other}, pct={discrepancy_pct})"
        )

    def test_zero_values_edge_cases(self):
        """Test edge cases with zero values."""
        broker_adapter = MockBrokerAdapter([])
        reconciler = PositionReconciler(broker_adapter, ReconciliationStrategy.WARN_ONLY)

        # Both zero -> 0% discrepancy
        assert reconciler._calculate_discrepancy_percentage(Decimal("0"), Decimal("0")) == 0.0

        # One zero, one non-zero -> 100% discrepancy
        discrepancy = reconciler._calculate_discrepancy_percentage(Decimal("0"), Decimal("100"))
        assert discrepancy == 1.0

        discrepancy = reconciler._calculate_discrepancy_percentage(Decimal("100"), Decimal("0"))
        assert discrepancy == 1.0

    @given(
        local=st.decimals(min_value=Decimal("-1000"), max_value=Decimal("-1"), allow_nan=False),
        broker=st.decimals(min_value=Decimal("1"), max_value=Decimal("1000"), allow_nan=False),
    )
    def test_opposite_signs_use_absolute_values(self, local, broker):
        """Property: Discrepancy calculation uses absolute values (side mismatch handled separately)."""
        broker_adapter = MockBrokerAdapter([])
        reconciler = PositionReconciler(broker_adapter, ReconciliationStrategy.WARN_ONLY)

        # The calculation should use absolute values
        discrepancy_pct = reconciler._calculate_discrepancy_percentage(local, broker)

        # Should be between 0 and 1
        assert (
            0.0 <= discrepancy_pct <= 1.0
        ), f"Discrepancy for opposite signs should be bounded, got {discrepancy_pct}"
