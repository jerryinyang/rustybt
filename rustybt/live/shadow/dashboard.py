"""Alignment dashboard for shadow trading validation.

This module provides programmatic access to alignment metrics and dashboard data
that can be consumed by UI frameworks (CLI, web, notebooks).
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import structlog

from rustybt.live.shadow.models import SignalAlignment
from rustybt.live.state_manager import StateManager

logger = structlog.get_logger()


class AlignmentDashboard:
    """Dashboard interface for shadow trading alignment metrics.

    Provides query methods for retrieving alignment data suitable for
    visualization in various dashboard UIs (terminal, web, notebooks).

    Attributes:
        state_manager: StateManager for accessing alignment history
        strategy_name: Name of the strategy being monitored
    """

    def __init__(self, state_manager: StateManager, strategy_name: str):
        """Initialize alignment dashboard.

        Args:
            state_manager: StateManager instance with alignment data
            strategy_name: Strategy name for querying metrics
        """
        self.state_manager = state_manager
        self.strategy_name = strategy_name

        logger.info(
            "alignment_dashboard_initialized",
            strategy_name=strategy_name,
        )

    def get_signal_match_rate(
        self,
        time_window: timedelta = timedelta(hours=1),
    ) -> tuple[Decimal, dict[str, int]]:
        """Get rolling signal match rate for specified time window.

        Args:
            time_window: Time window for rolling calculation (default: 1 hour)

        Returns:
            Tuple of (match_rate, divergence_breakdown) where match_rate is
            percentage of matching signals and divergence_breakdown is dict
            of alignment type counts
        """
        end_time = datetime.now(UTC)
        start_time = end_time - time_window

        history = self.state_manager.get_alignment_history(
            strategy_name=self.strategy_name,
            start_time=start_time,
            end_time=end_time,
        )

        if not history:
            return Decimal("0.0"), {}

        # Aggregate signal alignment counts
        total_backtest = 0
        total_live = 0
        divergence_counts: dict[str, int] = {}

        for metrics_dict in history:
            if "signal_alignment" not in metrics_dict:
                continue

            signal_data = metrics_dict["signal_alignment"]
            total_backtest += signal_data.get("backtest_signal_count", 0)
            total_live += signal_data.get("live_signal_count", 0)

            breakdown = signal_data.get("divergence_breakdown", {})
            for alignment_type, count in breakdown.items():
                divergence_counts[alignment_type] = divergence_counts.get(alignment_type, 0) + count

        # Calculate match rate (exact matches / total backtest signals)
        exact_matches = divergence_counts.get(SignalAlignment.EXACT_MATCH.value, 0)
        if total_backtest == 0:
            return Decimal("0.0"), divergence_counts

        match_rate = Decimal(str(exact_matches)) / Decimal(str(total_backtest))
        return match_rate, divergence_counts

    def get_execution_quality_metrics(
        self,
        time_window: timedelta = timedelta(hours=1),
    ) -> dict[str, Decimal]:
        """Get execution quality metrics for specified time window.

        Args:
            time_window: Time window for aggregation (default: 1 hour)

        Returns:
            Dict with keys: expected_slippage_bps, actual_slippage_bps,
            slippage_error_bps, fill_rate_expected, fill_rate_actual,
            fill_rate_error_pct, commission_expected, commission_actual,
            commission_error_pct
        """
        end_time = datetime.now(UTC)
        start_time = end_time - time_window

        history = self.state_manager.get_alignment_history(
            strategy_name=self.strategy_name,
            start_time=start_time,
            end_time=end_time,
        )

        if not history:
            return self._empty_execution_metrics()

        # Aggregate execution quality metrics
        total_samples = 0
        sum_expected_slippage = Decimal("0")
        sum_actual_slippage = Decimal("0")
        sum_slippage_error = Decimal("0")
        sum_fill_rate_expected = Decimal("0")
        sum_fill_rate_actual = Decimal("0")
        sum_commission_expected = Decimal("0")
        sum_commission_actual = Decimal("0")

        for metrics_dict in history:
            if "execution_quality" not in metrics_dict:
                continue

            exec_data = metrics_dict["execution_quality"]
            if not exec_data:  # Handle None case
                continue

            total_samples += 1
            sum_expected_slippage += Decimal(str(exec_data.get("expected_slippage_bps", 0)))
            sum_actual_slippage += Decimal(str(exec_data.get("actual_slippage_bps", 0)))
            sum_slippage_error += Decimal(str(exec_data.get("slippage_error_bps", 0)))
            sum_fill_rate_expected += Decimal(str(exec_data.get("fill_rate_expected", 0)))
            sum_fill_rate_actual += Decimal(str(exec_data.get("fill_rate_actual", 0)))
            sum_commission_expected += Decimal(str(exec_data.get("commission_expected", 0)))
            sum_commission_actual += Decimal(str(exec_data.get("commission_actual", 0)))

        if total_samples == 0:
            return self._empty_execution_metrics()

        # Calculate averages
        avg_expected_slippage = sum_expected_slippage / Decimal(str(total_samples))
        avg_actual_slippage = sum_actual_slippage / Decimal(str(total_samples))
        avg_slippage_error = sum_slippage_error / Decimal(str(total_samples))
        avg_fill_expected = sum_fill_rate_expected / Decimal(str(total_samples))
        avg_fill_actual = sum_fill_rate_actual / Decimal(str(total_samples))
        avg_comm_expected = sum_commission_expected / Decimal(str(total_samples))
        avg_comm_actual = sum_commission_actual / Decimal(str(total_samples))

        # Calculate error percentages
        fill_rate_error_pct = Decimal("0")
        if avg_fill_expected != 0:
            fill_rate_error_pct = (
                (avg_fill_actual - avg_fill_expected) / avg_fill_expected * Decimal("100")
            )

        commission_error_pct = Decimal("0")
        if avg_comm_expected != 0:
            commission_error_pct = (
                (avg_comm_actual - avg_comm_expected) / avg_comm_expected * Decimal("100")
            )

        return {
            "expected_slippage_bps": avg_expected_slippage,
            "actual_slippage_bps": avg_actual_slippage,
            "slippage_error_bps": avg_slippage_error,
            "fill_rate_expected": avg_fill_expected,
            "fill_rate_actual": avg_fill_actual,
            "fill_rate_error_pct": fill_rate_error_pct,
            "commission_expected": avg_comm_expected,
            "commission_actual": avg_comm_actual,
            "commission_error_pct": commission_error_pct,
        }

    def get_pnl_comparison(
        self,
        time_window: timedelta = timedelta(days=1),
    ) -> dict[str, list[dict[str, any]]]:
        """Get P&L comparison between backtest and live trading.

        Args:
            time_window: Time window for comparison (default: 1 day)

        Returns:
            Dict with 'cumulative' and 'daily' keys, each containing list of
            {timestamp, backtest_pnl, live_pnl, difference} dicts
        """
        end_time = datetime.now(UTC)
        start_time = end_time - time_window

        self.state_manager.get_alignment_history(
            strategy_name=self.strategy_name,
            start_time=start_time,
            end_time=end_time,
        )

        # Note: P&L tracking would require extending AlignmentMetrics to include
        # portfolio value snapshots. For now, return empty structure.
        # This would be implemented when portfolio tracking is added to shadow engine.

        logger.warning(
            "pnl_comparison_not_implemented",
            message="P&L comparison requires portfolio value tracking in AlignmentMetrics",
        )

        return {
            "cumulative": [],
            "daily": [],
        }

    def get_circuit_breaker_status(self) -> dict[str, any]:
        """Get current circuit breaker status.

        Returns:
            Dict with keys: status ('NORMAL', 'TRIPPED'), reason (if tripped),
            trip_time (if tripped), breach_details
        """
        # Note: This would query the CircuitBreaker instance directly.
        # For now, return placeholder that can be integrated with live engine.

        logger.warning(
            "circuit_breaker_status_not_integrated",
            message="Circuit breaker status requires integration with LiveTradingEngine",
        )

        return {
            "status": "UNKNOWN",
            "reason": None,
            "trip_time": None,
            "breach_details": None,
        }

    def get_alignment_trend(
        self,
        periods: list[timedelta] = None,
    ) -> dict[str, dict[str, Decimal]]:
        """Get alignment trend over multiple time periods.

        Args:
            periods: List of time periods (default: [1h, 24h, 7d, 30d])

        Returns:
            Dict mapping period label to metrics dict with signal_match_rate,
            avg_slippage_error_bps, avg_fill_rate_error_pct
        """
        if periods is None:
            periods = [
                timedelta(hours=1),
                timedelta(days=1),
                timedelta(days=7),
                timedelta(days=30),
            ]

        period_labels = {
            timedelta(hours=1): "1h",
            timedelta(days=1): "24h",
            timedelta(days=7): "7d",
            timedelta(days=30): "30d",
        }

        trends = {}
        for period in periods:
            label = period_labels.get(period, str(period))

            # Get metrics for this period
            match_rate, _ = self.get_signal_match_rate(time_window=period)
            exec_metrics = self.get_execution_quality_metrics(time_window=period)

            trends[label] = {
                "signal_match_rate": match_rate,
                "avg_slippage_error_bps": exec_metrics["slippage_error_bps"],
                "avg_fill_rate_error_pct": exec_metrics["fill_rate_error_pct"],
            }

        return trends

    def export_dashboard_json(
        self,
        time_window: timedelta = timedelta(hours=1),
    ) -> dict[str, any]:
        """Export all dashboard data as JSON-serializable dict.

        Args:
            time_window: Time window for metrics (default: 1 hour)

        Returns:
            Dict with all dashboard data suitable for JSON export or API response
        """
        match_rate, divergence = self.get_signal_match_rate(time_window)
        exec_metrics = self.get_execution_quality_metrics(time_window)
        pnl_data = self.get_pnl_comparison(time_window)
        breaker_status = self.get_circuit_breaker_status()
        trends = self.get_alignment_trend()

        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "time_window_seconds": int(time_window.total_seconds()),
            "signal_alignment": {
                "match_rate": str(match_rate),
                "divergence_breakdown": divergence,
            },
            "execution_quality": {
                k: str(v) if isinstance(v, Decimal) else v for k, v in exec_metrics.items()
            },
            "pnl_comparison": pnl_data,
            "circuit_breaker": breaker_status,
            "trends": {
                period: {k: str(v) if isinstance(v, Decimal) else v for k, v in metrics.items()}
                for period, metrics in trends.items()
            },
        }

    def _empty_execution_metrics(self) -> dict[str, Decimal]:
        """Return empty execution metrics dict."""
        return {
            "expected_slippage_bps": Decimal("0"),
            "actual_slippage_bps": Decimal("0"),
            "slippage_error_bps": Decimal("0"),
            "fill_rate_expected": Decimal("0"),
            "fill_rate_actual": Decimal("0"),
            "fill_rate_error_pct": Decimal("0"),
            "commission_expected": Decimal("0"),
            "commission_actual": Decimal("0"),
            "commission_error_pct": Decimal("0"),
        }
