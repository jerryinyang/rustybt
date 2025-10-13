"""Execution quality tracker for shadow trading.

This module tracks expected vs. actual execution quality metrics including
slippage, fill rates, and commission to detect when real execution deviates
from backtest assumptions.
"""

from collections import deque
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import structlog

from rustybt.live.shadow.config import ShadowTradingConfig
from rustybt.live.shadow.models import ExecutionQualityMetrics

logger = structlog.get_logger()


class ExecutionQualityTracker:
    """Tracks execution quality comparing backtest assumptions vs. reality.

    This tracker maintains a rolling window of fills and calculates metrics
    to detect when real execution quality diverges from backtest models.

    Attributes:
        config: Shadow trading configuration
        backtest_fills: Buffer of backtest (expected) fills
        live_fills: Buffer of live (actual) fills
        window_size: Number of fills to keep in rolling window
    """

    def __init__(self, config: ShadowTradingConfig, window_size: int = 100):
        """Initialize execution quality tracker.

        Args:
            config: Shadow trading configuration
            window_size: Number of fills to track (default: 100)
        """
        self.config = config
        self.window_size = window_size
        self._backtest_fills: deque = deque(maxlen=window_size)
        self._live_fills: deque = deque(maxlen=window_size)

        logger.info(
            "execution_quality_tracker_initialized",
            window_size=window_size,
            slippage_error_bps_max=str(config.slippage_error_bps_max),
            fill_rate_error_pct_max=str(config.fill_rate_error_pct_max),
        )

    def add_backtest_fill(
        self,
        order_id: str,
        signal_price: Decimal,
        fill_price: Decimal,
        fill_quantity: Decimal,
        order_quantity: Decimal,
        commission: Decimal,
        timestamp: datetime,
    ) -> None:
        """Add backtest fill record.

        Args:
            order_id: Order identifier
            signal_price: Price when signal generated
            fill_price: Actual fill price
            fill_quantity: Quantity filled
            order_quantity: Quantity ordered
            commission: Commission charged
            timestamp: Fill timestamp
        """
        # Calculate slippage in bps
        if signal_price > Decimal("0"):
            slippage_bps = abs(fill_price - signal_price) / signal_price * Decimal("10000")
        else:
            slippage_bps = Decimal("0")

        # Calculate fill percentage
        if order_quantity > Decimal("0"):
            fill_pct = fill_quantity / abs(order_quantity)
        else:
            fill_pct = Decimal("1")

        fill_record = {
            "order_id": order_id,
            "signal_price": signal_price,
            "fill_price": fill_price,
            "fill_quantity": fill_quantity,
            "order_quantity": order_quantity,
            "commission": commission,
            "slippage_bps": slippage_bps,
            "fill_pct": fill_pct,
            "timestamp": timestamp,
            "source": "backtest",
        }

        self._backtest_fills.append(fill_record)

        logger.debug(
            "backtest_fill_added",
            order_id=order_id,
            slippage_bps=str(slippage_bps),
            fill_pct=str(fill_pct),
            commission=str(commission),
        )

    def add_live_fill(
        self,
        order_id: str,
        signal_price: Decimal,
        fill_price: Decimal,
        fill_quantity: Decimal,
        order_quantity: Decimal,
        commission: Decimal,
        timestamp: datetime,
    ) -> None:
        """Add live fill record.

        Args:
            order_id: Order identifier
            signal_price: Price when signal generated
            fill_price: Actual fill price from broker
            fill_quantity: Quantity filled
            order_quantity: Quantity ordered
            commission: Commission charged by broker
            timestamp: Fill timestamp
        """
        # Calculate slippage in bps
        if signal_price > Decimal("0"):
            slippage_bps = abs(fill_price - signal_price) / signal_price * Decimal("10000")
        else:
            slippage_bps = Decimal("0")

        # Calculate fill percentage
        if order_quantity > Decimal("0"):
            fill_pct = fill_quantity / abs(order_quantity)
        else:
            fill_pct = Decimal("1")

        fill_record = {
            "order_id": order_id,
            "signal_price": signal_price,
            "fill_price": fill_price,
            "fill_quantity": fill_quantity,
            "order_quantity": order_quantity,
            "commission": commission,
            "slippage_bps": slippage_bps,
            "fill_pct": fill_pct,
            "timestamp": timestamp,
            "source": "live",
        }

        self._live_fills.append(fill_record)

        logger.debug(
            "live_fill_added",
            order_id=order_id,
            slippage_bps=str(slippage_bps),
            fill_pct=str(fill_pct),
            commission=str(commission),
        )

    def calculate_metrics(self, window_minutes: int | None = None) -> ExecutionQualityMetrics:
        """Calculate execution quality metrics over recent window.

        Args:
            window_minutes: Time window in minutes (None = use all fills)

        Returns:
            ExecutionQualityMetrics instance
        """
        # Filter fills by time window if specified
        if window_minutes:
            cutoff_time = datetime.now(UTC) - timedelta(minutes=window_minutes)
            backtest_fills = [f for f in self._backtest_fills if f["timestamp"] >= cutoff_time]
            live_fills = [f for f in self._live_fills if f["timestamp"] >= cutoff_time]
        else:
            backtest_fills = list(self._backtest_fills)
            live_fills = list(self._live_fills)

        # Calculate metrics
        metrics = ExecutionQualityMetrics.from_fills(backtest_fills, live_fills)

        logger.info(
            "execution_quality_metrics_calculated",
            window_minutes=window_minutes or "all",
            slippage_error_bps=str(metrics.slippage_error_bps),
            fill_rate_error_pct=str(metrics.fill_rate_error_pct),
            commission_error_pct=str(metrics.commission_error_pct),
            sample_count=metrics.sample_count,
        )

        return metrics

    def check_thresholds(self, metrics: ExecutionQualityMetrics) -> list[str]:
        """Check if execution quality metrics breach thresholds.

        Args:
            metrics: ExecutionQualityMetrics to check

        Returns:
            List of breach reasons (empty if all within thresholds)
        """
        breaches = []

        # Check slippage error
        if abs(metrics.slippage_error_bps) > self.config.slippage_error_bps_max:
            breaches.append(
                f"Slippage error {metrics.slippage_error_bps}bps exceeds "
                f"threshold {self.config.slippage_error_bps_max}bps"
            )

        # Check fill rate error
        if abs(metrics.fill_rate_error_pct) > self.config.fill_rate_error_pct_max:
            breaches.append(
                f"Fill rate error {metrics.fill_rate_error_pct}% exceeds "
                f"threshold {self.config.fill_rate_error_pct_max}%"
            )

        # Check commission error
        if abs(metrics.commission_error_pct) > self.config.commission_error_pct_max:
            breaches.append(
                f"Commission error {metrics.commission_error_pct}% exceeds "
                f"threshold {self.config.commission_error_pct_max}%"
            )

        if breaches:
            logger.warning(
                "execution_quality_thresholds_breached",
                breaches=breaches,
                slippage_error_bps=str(metrics.slippage_error_bps),
                fill_rate_error_pct=str(metrics.fill_rate_error_pct),
                commission_error_pct=str(metrics.commission_error_pct),
            )

        return breaches

    def get_fill_history(self, source: str = "both", limit: int = 100) -> list[dict]:
        """Get fill history for analysis.

        Args:
            source: "backtest", "live", or "both"
            limit: Maximum number of fills to return

        Returns:
            List of fill records
        """
        if source == "backtest":
            return list(self._backtest_fills)[-limit:]
        elif source == "live":
            return list(self._live_fills)[-limit:]
        else:  # both
            # Merge and sort by timestamp
            all_fills = list(self._backtest_fills) + list(self._live_fills)
            all_fills.sort(key=lambda f: f["timestamp"], reverse=True)
            return all_fills[:limit]

    def reset(self) -> None:
        """Reset tracker state."""
        self._backtest_fills.clear()
        self._live_fills.clear()
        logger.info("execution_quality_tracker_reset")
