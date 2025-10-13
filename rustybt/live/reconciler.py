"""Position reconciliation for live trading.

This module implements comprehensive position reconciliation between local state
and broker positions to detect and handle discrepancies during live trading.
"""

from datetime import datetime
from decimal import Decimal

import structlog

from rustybt.live.brokers.base import BrokerAdapter
from rustybt.live.models import (
    CashDiscrepancy,
    DiscrepancySeverity,
    DiscrepancyType,
    OrderDiscrepancy,
    OrderSnapshot,
    PositionDiscrepancy,
    PositionSnapshot,
    ReconciliationReport,
    ReconciliationStrategy,
)

logger = structlog.get_logger(__name__)


class ReconciliationError(Exception):
    """Raised when reconciliation fails critically."""


class PositionReconciler:
    """Reconciles local positions with broker positions.

    Compares local state against live broker state and applies reconciliation
    strategies to handle discrepancies. Supports position, cash, and order
    reconciliation with configurable strategies and severity classification.
    """

    def __init__(
        self,
        broker_adapter: BrokerAdapter,
        reconciliation_strategy: ReconciliationStrategy = ReconciliationStrategy.WARN_ONLY,
        cash_tolerance_pct: float = 0.01,
    ):
        """Initialize position reconciler.

        Args:
            broker_adapter: Broker adapter for fetching positions
            reconciliation_strategy: Strategy for handling discrepancies
            cash_tolerance_pct: Tolerance for cash balance differences (default: 1%)
        """
        self._broker = broker_adapter
        self._reconciliation_strategy = reconciliation_strategy
        self._cash_tolerance_pct = cash_tolerance_pct

        logger.info(
            "reconciler_initialized",
            strategy=reconciliation_strategy.value,
            cash_tolerance_pct=cash_tolerance_pct,
        )

    async def reconcile_all(
        self,
        local_positions: list[PositionSnapshot],
        local_cash: Decimal,
        local_orders: list[OrderSnapshot] | None = None,
    ) -> ReconciliationReport:
        """Perform comprehensive reconciliation of positions, cash, and orders.

        Args:
            local_positions: List of local position snapshots
            local_cash: Local cash balance
            local_orders: List of local pending orders (optional)

        Returns:
            ReconciliationReport with all discrepancies and actions taken

        Raises:
            ReconciliationError: If critical reconciliation fails with HALT_AND_ALERT strategy
        """
        logger.info(
            "reconciliation_started",
            local_position_count=len(local_positions),
            local_cash=str(local_cash),
            local_order_count=len(local_orders) if local_orders else 0,
        )

        try:
            # Reconcile positions
            position_discrepancies = await self._reconcile_positions(local_positions)

            # Reconcile cash balance
            cash_discrepancy = await self._reconcile_cash(local_cash)

            # Reconcile orders (if provided)
            order_discrepancies = []
            if local_orders is not None:
                order_discrepancies = await self._reconcile_orders(local_orders)

            # Generate report
            report = self._generate_report(
                position_discrepancies, cash_discrepancy, order_discrepancies
            )

            # Apply reconciliation strategy if needed
            if report.has_critical_discrepancies():
                await self._apply_strategy(report)

            logger.info(
                "reconciliation_completed",
                total_discrepancies=report.total_discrepancy_count(),
                position_discrepancies=len(position_discrepancies),
                cash_discrepancy=cash_discrepancy is not None,
                order_discrepancies=len(order_discrepancies),
            )

            return report

        except ReconciliationError:
            raise
        except Exception as e:
            logger.error("reconciliation_failed", error=str(e), exc_info=True)
            raise ReconciliationError(f"Reconciliation failed: {e}") from e

    async def _reconcile_positions(
        self, local_positions: list[PositionSnapshot]
    ) -> list[PositionDiscrepancy]:
        """Reconcile local positions with broker positions.

        Args:
            local_positions: List of local position snapshots

        Returns:
            List of position discrepancies
        """
        # Fetch broker positions
        broker_positions_raw = await self._broker.get_positions()
        broker_positions = self._normalize_broker_positions(broker_positions_raw)

        # Build local positions dict
        local_dict = {pos.asset: pos.to_decimal_amount() for pos in local_positions}

        discrepancies = []

        # Check for mismatches and missing broker positions
        for asset, local_amount in local_dict.items():
            broker_amount = broker_positions.get(asset)

            if broker_amount is None:
                # Position exists locally but not at broker
                discrepancies.append(
                    self._create_position_discrepancy(
                        asset=asset,
                        local_amount=local_amount,
                        broker_amount=None,
                        discrepancy_type=DiscrepancyType.MISSING_BROKER,
                    )
                )
            elif local_amount != broker_amount:
                # Check for side mismatch (opposite signs)
                if (local_amount > 0 and broker_amount < 0) or (
                    local_amount < 0 and broker_amount > 0
                ):
                    discrepancies.append(
                        self._create_position_discrepancy(
                            asset=asset,
                            local_amount=local_amount,
                            broker_amount=broker_amount,
                            discrepancy_type=DiscrepancyType.SIDE_MISMATCH,
                        )
                    )
                else:
                    # Quantity mismatch
                    discrepancies.append(
                        self._create_position_discrepancy(
                            asset=asset,
                            local_amount=local_amount,
                            broker_amount=broker_amount,
                            discrepancy_type=DiscrepancyType.QUANTITY_MISMATCH,
                        )
                    )

        # Check for extra broker positions
        for asset, broker_amount in broker_positions.items():
            if asset not in local_dict:
                discrepancies.append(
                    self._create_position_discrepancy(
                        asset=asset,
                        local_amount=None,
                        broker_amount=broker_amount,
                        discrepancy_type=DiscrepancyType.MISSING_LOCAL,
                    )
                )

        return discrepancies

    async def _reconcile_cash(self, local_cash: Decimal) -> CashDiscrepancy | None:
        """Reconcile local cash balance with broker cash balance.

        Args:
            local_cash: Local cash balance

        Returns:
            CashDiscrepancy if discrepancy exceeds tolerance, None otherwise
        """
        # Fetch broker account info
        account_info = await self._broker.get_account_info()
        broker_cash = account_info.get("cash", Decimal("0"))

        # Ensure broker_cash is Decimal
        if not isinstance(broker_cash, Decimal):
            broker_cash = Decimal(str(broker_cash))

        # Calculate discrepancy percentage
        discrepancy_pct = self._calculate_discrepancy_percentage(local_cash, broker_cash)

        # Check if within tolerance
        if discrepancy_pct <= self._cash_tolerance_pct:
            return None

        # Classify severity
        severity = self._classify_cash_severity(discrepancy_pct)

        logger.warning(
            "cash_discrepancy_detected",
            local_cash=str(local_cash),
            broker_cash=str(broker_cash),
            discrepancy_pct=discrepancy_pct,
            severity=severity.value,
        )

        return CashDiscrepancy(
            local_cash=str(local_cash),
            broker_cash=str(broker_cash),
            discrepancy_pct=discrepancy_pct,
            severity=severity,
        )

    async def _reconcile_orders(self, local_orders: list[OrderSnapshot]) -> list[OrderDiscrepancy]:
        """Reconcile local pending orders with broker open orders.

        Args:
            local_orders: List of local pending orders

        Returns:
            List of order discrepancies
        """
        # Fetch broker open orders
        broker_orders_raw = await self._broker.get_open_orders()

        # Build broker orders dict by broker_order_id
        broker_orders = {}
        for order in broker_orders_raw:
            order_id = order.get("order_id") or order.get("id")
            if order_id:
                broker_orders[order_id] = order

        # Build local orders dict by broker_order_id
        local_orders_dict = {}
        for order in local_orders:
            if order.broker_order_id:
                local_orders_dict[order.broker_order_id] = order

        discrepancies = []

        # Check for orphaned local orders (in local but not in broker)
        for order in local_orders:
            if order.broker_order_id and order.broker_order_id not in broker_orders:
                discrepancies.append(
                    OrderDiscrepancy(
                        order_id=order.order_id,
                        broker_order_id=order.broker_order_id,
                        asset=order.asset,
                        discrepancy_type="orphaned_local",
                        local_status=order.status,
                        broker_status=None,
                    )
                )

        # Check for orphaned broker orders and status mismatches
        for broker_order_id, broker_order in broker_orders.items():
            local_order = local_orders_dict.get(broker_order_id)
            asset = broker_order.get("asset") or broker_order.get("symbol", "UNKNOWN")

            if local_order is None:
                # Broker order not found locally
                discrepancies.append(
                    OrderDiscrepancy(
                        order_id=None,
                        broker_order_id=broker_order_id,
                        asset=asset,
                        discrepancy_type="orphaned_broker",
                        local_status=None,
                        broker_status=broker_order.get("status", "unknown"),
                    )
                )
            else:
                # Check for status mismatch
                broker_status = broker_order.get("status", "unknown")
                if local_order.status != broker_status:
                    discrepancies.append(
                        OrderDiscrepancy(
                            order_id=local_order.order_id,
                            broker_order_id=broker_order_id,
                            asset=asset,
                            discrepancy_type="status_mismatch",
                            local_status=local_order.status,
                            broker_status=broker_status,
                        )
                    )

        return discrepancies

    def _normalize_broker_positions(self, broker_positions_raw: list[dict]) -> dict[str, Decimal]:
        """Normalize broker positions to {asset: amount} dict.

        Args:
            broker_positions_raw: Raw broker position data

        Returns:
            Dict mapping asset symbol to position size
        """
        positions = {}

        for pos in broker_positions_raw:
            asset = pos.get("symbol") or pos.get("asset")
            amount = pos.get("amount") or pos.get("quantity", 0)

            # Convert to Decimal (CRITICAL: never use float)
            if isinstance(amount, str):
                amount = Decimal(amount)
            else:
                amount = Decimal(str(amount))

            # Only track non-zero positions
            if amount != Decimal(0):
                positions[asset] = amount

        return positions

    def _create_position_discrepancy(
        self,
        asset: str,
        local_amount: Decimal | None,
        broker_amount: Decimal | None,
        discrepancy_type: DiscrepancyType,
    ) -> PositionDiscrepancy:
        """Create a position discrepancy with severity classification.

        Args:
            asset: Asset symbol
            local_amount: Local position size
            broker_amount: Broker position size
            discrepancy_type: Type of discrepancy

        Returns:
            PositionDiscrepancy with severity classification
        """
        # Calculate discrepancy percentage
        discrepancy_pct = self._calculate_discrepancy_percentage(local_amount, broker_amount)

        # Classify severity
        severity = self._classify_position_severity(discrepancy_pct, discrepancy_type)

        logger.warning(
            "position_discrepancy_detected",
            asset=asset,
            local_amount=str(local_amount) if local_amount else None,
            broker_amount=str(broker_amount) if broker_amount else None,
            discrepancy_type=discrepancy_type.value,
            discrepancy_pct=discrepancy_pct,
            severity=severity.value,
        )

        return PositionDiscrepancy(
            asset=asset,
            local_amount=str(local_amount) if local_amount is not None else None,
            broker_amount=str(broker_amount) if broker_amount is not None else None,
            discrepancy_type=discrepancy_type,
            severity=severity,
            discrepancy_pct=discrepancy_pct,
        )

    def _calculate_discrepancy_percentage(
        self, local_value: Decimal | None, broker_value: Decimal | None
    ) -> float:
        """Calculate discrepancy percentage between local and broker values.

        Args:
            local_value: Local value (position size or cash)
            broker_value: Broker value (position size or cash)

        Returns:
            Discrepancy percentage (0.0-1.0+)
        """
        if local_value is None and broker_value is None:
            return 0.0

        if local_value is None:
            return 1.0  # 100% discrepancy (missing local)

        if broker_value is None:
            return 1.0  # 100% discrepancy (missing broker)

        # Use absolute values for percentage calculation
        local_abs = abs(local_value)
        broker_abs = abs(broker_value)

        if local_abs == Decimal(0) and broker_abs == Decimal(0):
            return 0.0

        # Calculate percentage difference: |local - broker| / max(local, broker)
        max_value = max(local_abs, broker_abs)
        if max_value == Decimal(0):
            return 0.0

        discrepancy = abs(local_abs - broker_abs) / max_value
        return float(discrepancy)

    def _classify_position_severity(
        self, discrepancy_pct: float, discrepancy_type: DiscrepancyType
    ) -> DiscrepancySeverity:
        """Classify position discrepancy severity.

        Args:
            discrepancy_pct: Discrepancy percentage (0.0-1.0+)
            discrepancy_type: Type of discrepancy

        Returns:
            Severity level
        """
        # Missing positions and side mismatches are always critical
        if discrepancy_type in (
            DiscrepancyType.MISSING_LOCAL,
            DiscrepancyType.MISSING_BROKER,
            DiscrepancyType.SIDE_MISMATCH,
        ):
            return DiscrepancySeverity.CRITICAL

        # Quantity mismatch severity based on percentage
        if discrepancy_pct < 0.01:  # <1%
            return DiscrepancySeverity.MINOR
        elif discrepancy_pct < 0.05:  # 1-5%
            return DiscrepancySeverity.MODERATE
        else:  # >5%
            return DiscrepancySeverity.CRITICAL

    def _classify_cash_severity(self, discrepancy_pct: float) -> DiscrepancySeverity:
        """Classify cash discrepancy severity.

        Args:
            discrepancy_pct: Discrepancy percentage (0.0-1.0+)

        Returns:
            Severity level
        """
        if discrepancy_pct < 0.02:  # <2%
            return DiscrepancySeverity.MINOR
        elif discrepancy_pct < 0.05:  # 2-5%
            return DiscrepancySeverity.MODERATE
        else:  # >5%
            return DiscrepancySeverity.CRITICAL

    def _generate_report(
        self,
        position_discrepancies: list[PositionDiscrepancy],
        cash_discrepancy: CashDiscrepancy | None,
        order_discrepancies: list[OrderDiscrepancy],
    ) -> ReconciliationReport:
        """Generate reconciliation report.

        Args:
            position_discrepancies: List of position discrepancies
            cash_discrepancy: Cash discrepancy (if any)
            order_discrepancies: List of order discrepancies

        Returns:
            ReconciliationReport
        """
        # Generate summary
        total_count = (
            len(position_discrepancies) + (1 if cash_discrepancy else 0) + len(order_discrepancies)
        )

        if total_count == 0:
            summary = "No discrepancies detected"
        else:
            critical_positions = sum(
                1 for d in position_discrepancies if d.severity == DiscrepancySeverity.CRITICAL
            )
            critical_cash = (
                1
                if cash_discrepancy and cash_discrepancy.severity == DiscrepancySeverity.CRITICAL
                else 0
            )
            critical_total = critical_positions + critical_cash

            summary = (
                f"Found {total_count} discrepancies: "
                f"{len(position_discrepancies)} positions, "
                f"{1 if cash_discrepancy else 0} cash, "
                f"{len(order_discrepancies)} orders. "
                f"Critical: {critical_total}"
            )

        return ReconciliationReport(
            timestamp=datetime.now(),
            position_discrepancies=position_discrepancies,
            cash_discrepancy=cash_discrepancy,
            order_discrepancies=order_discrepancies,
            actions_taken=[],
            summary=summary,
        )

    async def _apply_strategy(self, report: ReconciliationReport) -> None:
        """Apply reconciliation strategy to handle critical discrepancies.

        Args:
            report: Reconciliation report

        Raises:
            ReconciliationError: If HALT_AND_ALERT strategy is active
        """
        if self._reconciliation_strategy == ReconciliationStrategy.WARN_ONLY:
            logger.warning(
                "reconciliation_strategy_warn_only",
                discrepancies=report.total_discrepancy_count(),
                message="Continuing with local state",
            )
            report.actions_taken.append("WARN_ONLY: Logged discrepancies, no action taken")

        elif self._reconciliation_strategy == ReconciliationStrategy.SYNC_TO_BROKER:
            logger.info(
                "reconciliation_strategy_sync_to_broker",
                discrepancies=report.total_discrepancy_count(),
                message="Local state should be updated to match broker",
            )
            report.actions_taken.append(
                "SYNC_TO_BROKER: Recommend updating local state to match broker positions"
            )

        elif self._reconciliation_strategy == ReconciliationStrategy.SYNC_TO_LOCAL:
            logger.warning(
                "reconciliation_strategy_sync_to_local",
                discrepancies=report.total_discrepancy_count(),
                message="Broker positions should be updated to match local (RISKY)",
            )
            report.actions_taken.append(
                "SYNC_TO_LOCAL: Recommend submitting orders to match local positions (RISKY)"
            )

        elif self._reconciliation_strategy == ReconciliationStrategy.HALT_AND_ALERT:
            logger.critical(
                "reconciliation_strategy_halt_and_alert",
                discrepancies=report.total_discrepancy_count(),
                message="Halting engine for manual intervention",
            )
            raise ReconciliationError(
                f"Critical discrepancies detected ({report.total_discrepancy_count()}), "
                "engine halted for manual intervention"
            )

    def set_strategy(self, strategy: ReconciliationStrategy) -> None:
        """Update reconciliation strategy.

        Args:
            strategy: New reconciliation strategy
        """
        old_strategy = self._reconciliation_strategy
        self._reconciliation_strategy = strategy

        logger.info(
            "reconciliation_strategy_updated",
            old_strategy=old_strategy.value,
            new_strategy=strategy.value,
        )

    def set_cash_tolerance(self, tolerance_pct: float) -> None:
        """Update cash reconciliation tolerance.

        Args:
            tolerance_pct: New tolerance percentage (0.0-1.0)
        """
        old_tolerance = self._cash_tolerance_pct
        self._cash_tolerance_pct = tolerance_pct

        logger.info(
            "cash_tolerance_updated",
            old_tolerance=old_tolerance,
            new_tolerance=tolerance_pct,
        )
