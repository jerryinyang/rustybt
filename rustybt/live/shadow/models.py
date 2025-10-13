"""Shadow trading data models.

This module defines data structures for shadow trading validation metrics,
signal records, and alignment analysis.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum

from rustybt.assets import Asset


class SignalAlignment(Enum):
    """Signal alignment classification."""

    EXACT_MATCH = "exact_match"  # Timestamp, asset, side, quantity, price all match
    DIRECTION_MATCH = "direction_match"  # Timestamp, asset, side match; quantity/price differ
    MAGNITUDE_MISMATCH = "magnitude_mismatch"  # Same direction, >50% quantity difference
    MISSING_SIGNAL = "missing_signal"  # Backtest signal not executed live (or vice versa)
    TIME_MISMATCH = "time_mismatch"  # Signals outside time tolerance window


@dataclass
class SignalRecord:
    """Record of a trading signal from backtest or live engine.

    Attributes:
        timestamp: Signal generation time
        asset: Asset being traded
        side: "BUY" or "SELL"
        quantity: Order quantity (Decimal)
        price: Signal price (Decimal, optional for market orders)
        order_type: Order type ("market", "limit", etc.)
        source: "backtest" or "live"
        signal_id: Unique signal identifier
    """

    timestamp: datetime
    asset: Asset
    side: str
    quantity: Decimal
    price: Decimal | None
    order_type: str
    source: str  # "backtest" or "live"
    signal_id: str = field(default="")

    def __post_init__(self):
        """Generate signal ID if not provided."""
        if not self.signal_id:
            ts_str = self.timestamp.strftime("%Y%m%d%H%M%S%f")
            self.signal_id = f"{self.source}_{self.asset.symbol}_{ts_str}"

    def matches_time(self, other: "SignalRecord", tolerance_ms: int) -> bool:
        """Check if timestamps match within tolerance."""
        time_diff_ms = abs((self.timestamp - other.timestamp).total_seconds() * 1000)
        return time_diff_ms <= tolerance_ms

    def matches_direction(self, other: "SignalRecord") -> bool:
        """Check if signals have same direction."""
        return self.asset == other.asset and self.side == other.side

    def quantity_difference_pct(self, other: "SignalRecord") -> Decimal:
        """Calculate percentage difference in quantity."""
        if self.quantity == Decimal("0"):
            return Decimal("100") if other.quantity != Decimal("0") else Decimal("0")
        diff = abs(self.quantity - other.quantity)
        return (diff / abs(self.quantity)) * Decimal("100")


@dataclass
class ExecutionQualityMetrics:
    """Execution quality comparison metrics.

    Tracks expected vs. actual execution quality to detect when
    real execution deviates from backtest assumptions.

    Attributes:
        expected_slippage_bps: Expected slippage from backtest model (bps)
        actual_slippage_bps: Actual slippage from live fills (bps)
        slippage_error_bps: Difference between actual and expected
        fill_rate_expected: Expected fill rate from partial fill model
        fill_rate_actual: Actual fill rate from broker
        fill_rate_error_pct: Percentage difference in fill rates
        commission_expected: Expected commission from model
        commission_actual: Actual commission charged by broker
        commission_error_pct: Percentage difference in commission
        sample_count: Number of fills in sample
    """

    expected_slippage_bps: Decimal
    actual_slippage_bps: Decimal
    slippage_error_bps: Decimal
    fill_rate_expected: Decimal
    fill_rate_actual: Decimal
    fill_rate_error_pct: Decimal
    commission_expected: Decimal
    commission_actual: Decimal
    commission_error_pct: Decimal
    sample_count: int

    @classmethod
    def from_fills(
        cls,
        backtest_fills: list[dict],
        live_fills: list[dict],
    ) -> "ExecutionQualityMetrics":
        """Calculate execution quality metrics from fill records.

        Args:
            backtest_fills: List of backtest fill records
            live_fills: List of live fill records

        Returns:
            ExecutionQualityMetrics instance
        """
        if not backtest_fills or not live_fills:
            # Return zero metrics if no fills
            return cls(
                expected_slippage_bps=Decimal("0"),
                actual_slippage_bps=Decimal("0"),
                slippage_error_bps=Decimal("0"),
                fill_rate_expected=Decimal("1"),
                fill_rate_actual=Decimal("1"),
                fill_rate_error_pct=Decimal("0"),
                commission_expected=Decimal("0"),
                commission_actual=Decimal("0"),
                commission_error_pct=Decimal("0"),
                sample_count=0,
            )

        # Calculate average slippage
        total_expected_slippage = sum(
            fill.get("slippage_bps", Decimal("0")) for fill in backtest_fills
        )
        total_actual_slippage = sum(fill.get("slippage_bps", Decimal("0")) for fill in live_fills)

        expected_slippage_bps = total_expected_slippage / len(backtest_fills)
        actual_slippage_bps = total_actual_slippage / len(live_fills)
        slippage_error_bps = actual_slippage_bps - expected_slippage_bps

        # Calculate fill rates
        total_expected_fill = sum(fill.get("fill_pct", Decimal("1")) for fill in backtest_fills)
        total_actual_fill = sum(fill.get("fill_pct", Decimal("1")) for fill in live_fills)

        fill_rate_expected = total_expected_fill / len(backtest_fills)
        fill_rate_actual = total_actual_fill / len(live_fills)

        if fill_rate_expected > Decimal("0"):
            fill_rate_error_pct = (
                (fill_rate_actual - fill_rate_expected) / fill_rate_expected * Decimal("100")
            )
        else:
            fill_rate_error_pct = Decimal("0")

        # Calculate commissions
        total_expected_commission = sum(
            fill.get("commission", Decimal("0")) for fill in backtest_fills
        )
        total_actual_commission = sum(fill.get("commission", Decimal("0")) for fill in live_fills)

        commission_expected = total_expected_commission / len(backtest_fills)
        commission_actual = total_actual_commission / len(live_fills)

        if commission_expected > Decimal("0"):
            commission_error_pct = (
                (commission_actual - commission_expected) / commission_expected * Decimal("100")
            )
        else:
            commission_error_pct = Decimal("0")

        return cls(
            expected_slippage_bps=expected_slippage_bps,
            actual_slippage_bps=actual_slippage_bps,
            slippage_error_bps=slippage_error_bps,
            fill_rate_expected=fill_rate_expected,
            fill_rate_actual=fill_rate_actual,
            fill_rate_error_pct=fill_rate_error_pct,
            commission_expected=commission_expected,
            commission_actual=commission_actual,
            commission_error_pct=commission_error_pct,
            sample_count=len(live_fills),
        )


@dataclass
class AlignmentMetrics:
    """Overall alignment metrics for shadow trading validation.

    Combines signal alignment and execution quality metrics to provide
    a comprehensive view of backtest-live alignment.

    Attributes:
        execution_quality: Execution quality metrics
        backtest_signal_count: Number of backtest signals
        live_signal_count: Number of live signals
        signal_match_rate: Percentage of signals that match
        divergence_breakdown: Count of each divergence type
        timestamp: Metrics calculation timestamp
    """

    execution_quality: ExecutionQualityMetrics
    backtest_signal_count: int
    live_signal_count: int
    signal_match_rate: Decimal
    divergence_breakdown: dict[SignalAlignment, int]
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def is_aligned(self, config) -> bool:
        """Check if alignment metrics meet configuration thresholds.

        Args:
            config: ShadowTradingConfig with thresholds

        Returns:
            True if all metrics within thresholds, False otherwise
        """
        # Check signal match rate
        if self.signal_match_rate < config.signal_match_rate_min:
            return False

        # Check slippage error
        if abs(self.execution_quality.slippage_error_bps) > config.slippage_error_bps_max:
            return False

        # Check fill rate error
        if abs(self.execution_quality.fill_rate_error_pct) > config.fill_rate_error_pct_max:
            return False

        # Check commission error
        if abs(self.execution_quality.commission_error_pct) > config.commission_error_pct_max:
            return False

        return True

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        result = {
            "backtest_signal_count": self.backtest_signal_count,
            "live_signal_count": self.live_signal_count,
            "signal_match_rate": self.signal_match_rate,
            "divergence_breakdown": {
                alignment.value: count for alignment, count in self.divergence_breakdown.items()
            },
            "timestamp": (
                self.timestamp.isoformat()
                if hasattr(self.timestamp, "isoformat")
                else str(self.timestamp)
            ),
        }

        # Add execution quality if present
        if self.execution_quality is not None:
            result["execution_quality"] = {
                "expected_slippage_bps": str(self.execution_quality.expected_slippage_bps),
                "actual_slippage_bps": str(self.execution_quality.actual_slippage_bps),
                "slippage_error_bps": str(self.execution_quality.slippage_error_bps),
                "fill_rate_expected": str(self.execution_quality.fill_rate_expected),
                "fill_rate_actual": str(self.execution_quality.fill_rate_actual),
                "fill_rate_error_pct": str(self.execution_quality.fill_rate_error_pct),
                "commission_expected": str(self.execution_quality.commission_expected),
                "commission_actual": str(self.execution_quality.commission_actual),
                "commission_error_pct": str(self.execution_quality.commission_error_pct),
                "sample_count": self.execution_quality.sample_count,
            }

        return result
