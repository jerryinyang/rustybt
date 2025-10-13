"""Data models for live trading state management and checkpointing.

This module defines Pydantic models for serializing and deserializing live trading
state including positions, orders, and alignment metrics for crash recovery.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class PositionSnapshot(BaseModel):
    """Snapshot of a position for state checkpoint serialization.

    Attributes:
        asset: Asset symbol
        sid: Security identifier
        amount: Position size (Decimal as string for precision)
        cost_basis: Cost basis per share/unit (Decimal as string)
        last_price: Last known price (Decimal as string)
    """

    asset: str = Field(..., description="Asset symbol (e.g., 'AAPL', 'BTCUSDT')")
    sid: int = Field(..., description="Security identifier")
    amount: str = Field(..., description="Position size as Decimal string")
    cost_basis: str = Field(..., description="Cost basis per unit as Decimal string")
    last_price: str = Field(..., description="Last known price as Decimal string")

    @field_validator("amount", "cost_basis", "last_price")
    @classmethod
    def validate_decimal_string(cls, v: str) -> str:
        """Validate that string can be converted to Decimal."""
        try:
            Decimal(v)
        except Exception as e:
            raise ValueError(f"Invalid decimal string: {v}") from e
        return v

    def to_decimal_amount(self) -> Decimal:
        """Convert amount to Decimal."""
        return Decimal(self.amount)

    def to_decimal_cost_basis(self) -> Decimal:
        """Convert cost_basis to Decimal."""
        return Decimal(self.cost_basis)

    def to_decimal_last_price(self) -> Decimal:
        """Convert last_price to Decimal."""
        return Decimal(self.last_price)


class OrderSnapshot(BaseModel):
    """Snapshot of a pending order for state checkpoint serialization.

    Attributes:
        order_id: Internal order identifier
        asset: Asset symbol
        sid: Security identifier
        amount: Order quantity (Decimal as string, positive=buy, negative=sell)
        order_type: Order type (market, limit, stop, stop-limit)
        limit_price: Limit price for limit orders (optional, Decimal as string)
        broker_order_id: Broker's order identifier (optional)
        status: Order status (pending, submitted, filled, cancelled, rejected)
        created_at: Order creation timestamp
    """

    order_id: str = Field(..., description="Internal order identifier")
    asset: str = Field(..., description="Asset symbol")
    sid: int = Field(..., description="Security identifier")
    amount: str = Field(..., description="Order quantity as Decimal string")
    order_type: str = Field(..., description="Order type: market, limit, stop, stop-limit")
    limit_price: str | None = Field(
        None, description="Limit price as Decimal string (for limit orders)"
    )
    broker_order_id: str | None = Field(None, description="Broker order identifier")
    status: str = Field(
        ...,
        description="Order status: pending, submitted, filled, cancelled, rejected",
    )
    created_at: datetime = Field(..., description="Order creation timestamp")

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: str) -> str:
        """Validate amount is a valid Decimal string."""
        try:
            Decimal(v)
        except Exception as e:
            raise ValueError(f"Invalid decimal string for amount: {v}") from e
        return v

    @field_validator("limit_price")
    @classmethod
    def validate_limit_price(cls, v: str | None) -> str | None:
        """Validate limit_price is a valid Decimal string if provided."""
        if v is not None:
            try:
                Decimal(v)
            except Exception as e:
                raise ValueError(f"Invalid decimal string for limit_price: {v}") from e
        return v

    def to_decimal_amount(self) -> Decimal:
        """Convert amount to Decimal."""
        return Decimal(self.amount)

    def to_decimal_limit_price(self) -> Decimal | None:
        """Convert limit_price to Decimal if set."""
        return Decimal(self.limit_price) if self.limit_price else None


class AlignmentMetrics(BaseModel):
    """Shadow trading alignment metrics for validation persistence.

    These metrics track how well live trading matches backtest behavior,
    critical for validating strategy implementation correctness.

    Attributes:
        signal_match_rate: Percentage of matching signals (0.0-1.0)
        slippage_error_bps: Slippage error in basis points
        fill_rate_error_pct: Fill rate error percentage
        backtest_signal_count: Number of signals in backtest reference
        live_signal_count: Number of signals generated live
        last_updated: Timestamp of last metrics update
    """

    signal_match_rate: float = Field(..., ge=0.0, le=1.0, description="Signal match rate (0.0-1.0)")
    slippage_error_bps: float = Field(..., description="Slippage error in basis points")
    fill_rate_error_pct: float = Field(..., description="Fill rate error percentage")
    backtest_signal_count: int = Field(..., ge=0, description="Backtest signal count for reference")
    live_signal_count: int = Field(..., ge=0, description="Live signal count")
    last_updated: datetime = Field(..., description="Last metrics update timestamp")


class StateCheckpoint(BaseModel):
    """Complete state checkpoint for crash recovery.

    This model represents a complete snapshot of live trading state that can be
    serialized to disk and restored after a crash or restart.

    Attributes:
        strategy_name: Name of the strategy
        timestamp: Checkpoint creation timestamp
        strategy_state: Custom strategy state (user-defined dict)
        positions: List of position snapshots
        pending_orders: List of pending order snapshots
        cash_balance: Cash balance as Decimal string
        alignment_metrics: Shadow trading alignment metrics (optional)
    """

    strategy_name: str = Field(..., description="Strategy identifier")
    timestamp: datetime = Field(..., description="Checkpoint creation timestamp")
    strategy_state: dict[str, Any] = Field(
        default_factory=dict, description="Custom strategy state data"
    )
    positions: list[PositionSnapshot] = Field(
        default_factory=list, description="Position snapshots"
    )
    pending_orders: list[OrderSnapshot] = Field(
        default_factory=list, description="Pending order snapshots"
    )
    cash_balance: str = Field(..., description="Cash balance as Decimal string")
    alignment_metrics: AlignmentMetrics | None = Field(
        None, description="Shadow trading alignment metrics"
    )

    @field_validator("cash_balance")
    @classmethod
    def validate_cash_balance(cls, v: str) -> str:
        """Validate cash_balance is a valid Decimal string."""
        try:
            Decimal(v)
        except Exception as e:
            raise ValueError(f"Invalid decimal string for cash_balance: {v}") from e
        return v

    def to_decimal_cash_balance(self) -> Decimal:
        """Convert cash_balance to Decimal."""
        return Decimal(self.cash_balance)

    def is_stale(self, threshold_seconds: int = 3600) -> bool:
        """Check if checkpoint is stale (older than threshold).

        Args:
            threshold_seconds: Staleness threshold in seconds (default: 1 hour)

        Returns:
            True if checkpoint is older than threshold
        """
        age = (datetime.now() - self.timestamp.replace(tzinfo=None)).total_seconds()
        return age > threshold_seconds


class DiscrepancySeverity(str, Enum):
    """Severity levels for position discrepancies."""

    MINOR = "minor"
    MODERATE = "moderate"
    CRITICAL = "critical"


class DiscrepancyType(str, Enum):
    """Types of position discrepancies."""

    QUANTITY_MISMATCH = "quantity_mismatch"
    MISSING_LOCAL = "missing_local"
    MISSING_BROKER = "missing_broker"
    SIDE_MISMATCH = "side_mismatch"


class ReconciliationStrategy(str, Enum):
    """Strategies for handling reconciliation discrepancies."""

    SYNC_TO_BROKER = "sync_to_broker"
    SYNC_TO_LOCAL = "sync_to_local"
    HALT_AND_ALERT = "halt_and_alert"
    WARN_ONLY = "warn_only"


class PositionDiscrepancy(BaseModel):
    """Represents a discrepancy between local and broker positions.

    Attributes:
        asset: Asset symbol
        local_amount: Local position size (None if missing locally)
        broker_amount: Broker position size (None if missing at broker)
        discrepancy_type: Type of discrepancy
        severity: Severity level
        discrepancy_pct: Discrepancy percentage (0.0-1.0)
    """

    asset: str = Field(..., description="Asset symbol")
    local_amount: str | None = Field(None, description="Local position size as Decimal string")
    broker_amount: str | None = Field(None, description="Broker position size as Decimal string")
    discrepancy_type: DiscrepancyType = Field(..., description="Discrepancy type")
    severity: DiscrepancySeverity = Field(..., description="Severity level")
    discrepancy_pct: float = Field(..., ge=0.0, description="Discrepancy percentage (0.0-1.0)")

    def to_decimal_local_amount(self) -> Decimal | None:
        """Convert local_amount to Decimal."""
        return Decimal(self.local_amount) if self.local_amount else None

    def to_decimal_broker_amount(self) -> Decimal | None:
        """Convert broker_amount to Decimal."""
        return Decimal(self.broker_amount) if self.broker_amount else None


class CashDiscrepancy(BaseModel):
    """Represents a discrepancy between local and broker cash balance.

    Attributes:
        local_cash: Local cash balance as Decimal string
        broker_cash: Broker cash balance as Decimal string
        discrepancy_pct: Discrepancy percentage (0.0-1.0)
        severity: Severity level
    """

    local_cash: str = Field(..., description="Local cash balance as Decimal string")
    broker_cash: str = Field(..., description="Broker cash balance as Decimal string")
    discrepancy_pct: float = Field(..., ge=0.0, description="Discrepancy percentage (0.0-1.0)")
    severity: DiscrepancySeverity = Field(..., description="Severity level")

    def to_decimal_local_cash(self) -> Decimal:
        """Convert local_cash to Decimal."""
        return Decimal(self.local_cash)

    def to_decimal_broker_cash(self) -> Decimal:
        """Convert broker_cash to Decimal."""
        return Decimal(self.broker_cash)


class OrderDiscrepancy(BaseModel):
    """Represents a discrepancy between local and broker orders.

    Attributes:
        order_id: Internal order ID
        broker_order_id: Broker order ID (if available)
        asset: Asset symbol
        discrepancy_type: Type of discrepancy (orphaned_local, orphaned_broker, status_mismatch)
        local_status: Local order status (if available)
        broker_status: Broker order status (if available)
    """

    order_id: str | None = Field(None, description="Internal order ID")
    broker_order_id: str | None = Field(None, description="Broker order ID")
    asset: str = Field(..., description="Asset symbol")
    discrepancy_type: str = Field(
        ..., description="Discrepancy type: orphaned_local, orphaned_broker, status_mismatch"
    )
    local_status: str | None = Field(None, description="Local order status")
    broker_status: str | None = Field(None, description="Broker order status")


class ReconciliationReport(BaseModel):
    """Report of reconciliation results.

    Attributes:
        timestamp: Report creation timestamp
        position_discrepancies: List of position discrepancies
        cash_discrepancy: Cash discrepancy (if any)
        order_discrepancies: List of order discrepancies
        actions_taken: List of actions taken to resolve discrepancies
        summary: Human-readable summary
    """

    timestamp: datetime = Field(..., description="Report creation timestamp")
    position_discrepancies: list[PositionDiscrepancy] = Field(
        default_factory=list, description="Position discrepancies"
    )
    cash_discrepancy: CashDiscrepancy | None = Field(None, description="Cash discrepancy")
    order_discrepancies: list[OrderDiscrepancy] = Field(
        default_factory=list, description="Order discrepancies"
    )
    actions_taken: list[str] = Field(default_factory=list, description="Actions taken")
    summary: str = Field(..., description="Human-readable summary")

    def has_critical_discrepancies(self) -> bool:
        """Check if report contains critical discrepancies."""
        position_critical = any(
            d.severity == DiscrepancySeverity.CRITICAL for d in self.position_discrepancies
        )
        cash_critical = (
            self.cash_discrepancy is not None
            and self.cash_discrepancy.severity == DiscrepancySeverity.CRITICAL
        )
        return position_critical or cash_critical

    def total_discrepancy_count(self) -> int:
        """Get total count of all discrepancies."""
        return (
            len(self.position_discrepancies)
            + (1 if self.cash_discrepancy else 0)
            + len(self.order_discrepancies)
        )
