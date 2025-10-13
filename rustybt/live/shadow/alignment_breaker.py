"""Alignment circuit breaker for shadow trading.

This module extends the circuit breaker framework with alignment-specific
trip conditions to halt trading when backtest-live divergence exceeds thresholds.
"""

from datetime import UTC, datetime, timedelta

import structlog

from rustybt.live.circuit_breakers import (
    BaseCircuitBreaker,
    CircuitBreakerType,
)
from rustybt.live.shadow.config import ShadowTradingConfig
from rustybt.live.shadow.models import AlignmentMetrics

logger = structlog.get_logger()


class AlignmentCircuitBreaker(BaseCircuitBreaker):
    """Circuit breaker that trips on backtest-live alignment degradation.

    This breaker monitors signal alignment and execution quality metrics.
    If metrics breach thresholds for the grace period, trading is halted
    until manual investigation and reset.

    Attributes:
        config: Shadow trading configuration with thresholds
        grace_period_seconds: Time window before tripping
        breach_start_time: When breaches first detected
        recent_breaches: History of recent breach reasons
    """

    def __init__(
        self,
        config: ShadowTradingConfig,
    ):
        """Initialize alignment circuit breaker.

        Args:
            config: Shadow trading configuration
        """
        super().__init__(CircuitBreakerType.MANUAL)  # Use MANUAL type for now
        self.config = config
        self.grace_period_seconds = config.grace_period_seconds
        self._breach_start_time: datetime | None = None
        self._recent_breaches: list[str] = []
        self._current_time: datetime | None = None  # For testing

        logger.info(
            "alignment_circuit_breaker_initialized",
            signal_match_rate_min=str(config.signal_match_rate_min),
            slippage_error_bps_max=str(config.slippage_error_bps_max),
            grace_period_seconds=config.grace_period_seconds,
        )

    def _get_current_time(self) -> datetime:
        """Get current time (testable by setting _current_time).

        Returns:
            Current datetime (UTC)
        """
        if self._current_time is not None:
            return self._current_time
        return datetime.now(UTC)

    def reset(self) -> None:
        """Reset circuit breaker to NORMAL state.

        Overrides base class to also clear alignment-specific state.
        """
        super().reset()
        self._breach_start_time = None
        self._recent_breaches.clear()

    def check_alignment(self, metrics: AlignmentMetrics) -> bool:
        """Check alignment metrics and trip if thresholds breached.

        This method implements the core alignment validation logic with
        grace period handling.

        Args:
            metrics: Current alignment metrics

        Returns:
            True if alignment is good, False if breached
        """
        # Store metrics for get_breach_summary()
        self._last_metrics = metrics

        # Check if metrics meet thresholds
        if metrics.is_aligned(self.config):
            # Alignment restored - reset breach tracking
            if self._breach_start_time is not None:
                logger.info(
                    "alignment_restored",
                    breach_duration_seconds=(
                        self._get_current_time() - self._breach_start_time
                    ).total_seconds(),
                )
                self._breach_start_time = None
                self._recent_breaches.clear()
            return True

        # Alignment breached - collect breach reasons
        breaches = self._identify_breaches(metrics)
        self._recent_breaches = breaches

        # Start grace period if not already started
        if self._breach_start_time is None:
            self._breach_start_time = self._get_current_time()
            logger.warning(
                "alignment_breach_detected_grace_period_started",
                breaches=breaches,
                grace_period_seconds=self.grace_period_seconds,
            )
            # If grace period is 0, trip immediately
            if self.grace_period_seconds == 0:
                breach_duration = 0
            else:
                return True  # Still within grace period

        # Check if grace period has elapsed
        if self._breach_start_time is not None:
            breach_duration = (self._get_current_time() - self._breach_start_time).total_seconds()
        # breach_duration already set to 0 if grace_period_seconds == 0

        if breach_duration >= self.grace_period_seconds:
            # Grace period expired - trip circuit breaker
            trip_reason = (
                f"Alignment degraded for {breach_duration:.0f}s (grace period: "
                f"{self.grace_period_seconds}s). Breaches: {', '.join(breaches)}"
            )

            self._trip(reason=trip_reason)

            logger.error(
                "alignment_circuit_breaker_tripped",
                breach_duration_seconds=breach_duration,
                breaches=breaches,
                signal_match_rate=str(metrics.signal_match_rate),
                slippage_error_bps=str(metrics.execution_quality.slippage_error_bps),
            )

            return False
        else:
            # Still within grace period
            logger.warning(
                "alignment_breach_ongoing",
                breach_duration_seconds=breach_duration,
                grace_period_remaining_seconds=self.grace_period_seconds - breach_duration,
                breaches=breaches,
            )
            return True

    def _identify_breaches(self, metrics: AlignmentMetrics) -> list[str]:
        """Identify specific threshold breaches.

        Args:
            metrics: Alignment metrics to check

        Returns:
            List of breach descriptions
        """
        breaches = []

        # Check signal match rate
        if metrics.signal_match_rate < self.config.signal_match_rate_min:
            breaches.append(
                f"Signal match rate {metrics.signal_match_rate:.2%} < "
                f"{self.config.signal_match_rate_min:.2%}"
            )

        # Check slippage error
        slippage_error = abs(metrics.execution_quality.slippage_error_bps)
        if slippage_error > self.config.slippage_error_bps_max:
            breaches.append(
                f"Slippage error {slippage_error}bps > {self.config.slippage_error_bps_max}bps"
            )

        # Check fill rate error
        fill_rate_error = abs(metrics.execution_quality.fill_rate_error_pct)
        if fill_rate_error > self.config.fill_rate_error_pct_max:
            breaches.append(
                f"Fill rate error {fill_rate_error:.1f}% > {self.config.fill_rate_error_pct_max}%"
            )

        # Check commission error
        commission_error = abs(metrics.execution_quality.commission_error_pct)
        if commission_error > self.config.commission_error_pct_max:
            breaches.append(
                f"Commission error {commission_error:.1f}% > "
                f"{self.config.commission_error_pct_max}%"
            )

        return breaches

    def get_breach_summary(self) -> dict:
        """Get summary of current breaches for alerting.

        Returns:
            Dictionary with breach details for each metric
        """
        # Return the most recent metrics checked (stored during last check_alignment call)
        if not hasattr(self, "_last_metrics"):
            return {}

        metrics = self._last_metrics

        return {
            "signal_match_rate": {
                "breached": metrics.signal_match_rate < self.config.signal_match_rate_min,
                "threshold": self.config.signal_match_rate_min,
                "actual": metrics.signal_match_rate,
            },
            "slippage_error_bps": {
                "breached": abs(metrics.execution_quality.slippage_error_bps)
                > self.config.slippage_error_bps_max,
                "threshold": self.config.slippage_error_bps_max,
                "actual": abs(metrics.execution_quality.slippage_error_bps),
            },
            "fill_rate_error_pct": {
                "breached": abs(metrics.execution_quality.fill_rate_error_pct)
                > self.config.fill_rate_error_pct_max,
                "threshold": self.config.fill_rate_error_pct_max,
                "actual": abs(metrics.execution_quality.fill_rate_error_pct),
            },
            "commission_error_pct": {
                "breached": abs(metrics.execution_quality.commission_error_pct)
                > self.config.commission_error_pct_max,
                "threshold": self.config.commission_error_pct_max,
                "actual": abs(metrics.execution_quality.commission_error_pct),
            },
        }

    def manual_reset(self, reason: str) -> None:
        """Manually reset circuit breaker after investigation.

        Args:
            reason: Reason for manual reset (e.g., "Model updated", "Market regime changed")
        """
        logger.info(
            "alignment_circuit_breaker_manual_reset",
            reason=reason,
            previous_breaches=self._recent_breaches,
        )

        self.reset()
        self._breach_start_time = None
        self._recent_breaches.clear()

    def allow_override(self, trader_id: str, reason: str, duration_minutes: int = 60) -> None:
        """Allow trader to override circuit breaker temporarily.

        This provides a manual override for experienced traders who understand
        the divergence and choose to continue trading.

        Args:
            trader_id: ID of trader authorizing override
            reason: Reason for override
            duration_minutes: How long override is valid (default: 60 min)
        """
        logger.warning(
            "alignment_circuit_breaker_override",
            trader_id=trader_id,
            reason=reason,
            duration_minutes=duration_minutes,
            recent_breaches=self._recent_breaches,
        )

        # Reset breaker temporarily
        self.reset()
        self._breach_start_time = None

        # Set grace period to override duration
        original_grace_period = self.grace_period_seconds
        self.grace_period_seconds = duration_minutes * 60

        # Log override expiration time
        override_expires = self._get_current_time() + timedelta(minutes=duration_minutes)
        logger.info(
            "override_active",
            expires_at=override_expires.isoformat(),
            original_grace_period_seconds=original_grace_period,
        )

        # Note: In production, you'd set a timer to restore original grace period
        # after override expires. For now, requires manual intervention.
