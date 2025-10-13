"""Shadow trading configuration.

This module defines configuration for shadow trading validation thresholds
and operational parameters.
"""

from dataclasses import dataclass
from decimal import Decimal

import structlog

logger = structlog.get_logger()


@dataclass(frozen=True)
class ShadowTradingConfig:
    """Configuration for shadow trading validation.

    This dataclass defines thresholds and parameters for shadow trading
    validation. Breaching these thresholds triggers the AlignmentCircuitBreaker.

    Attributes:
        signal_match_rate_min: Minimum signal match rate (0.95 = 95%)
        slippage_error_bps_max: Maximum slippage error in basis points (50 = 0.5%)
        fill_rate_error_pct_max: Maximum fill rate error percentage (20 = 20%)
        commission_error_pct_max: Maximum commission error percentage (10 = 10%)
        time_tolerance_ms: Time tolerance for signal matching in milliseconds
        enabled: Whether shadow trading is enabled
        sampling_rate: Signal sampling rate (1.0 = all signals, 0.1 = 10%)
        memory_limit_hours: Hours of alignment history to keep in memory
        grace_period_seconds: Grace period before tripping circuit breaker

    Example:
        >>> config = ShadowTradingConfig(
        ...     signal_match_rate_min=Decimal("0.99"),  # 99% match required
        ...     slippage_error_bps_max=Decimal("10"),   # 10 bps max error
        ... )
    """

    # Signal alignment thresholds
    signal_match_rate_min: Decimal = Decimal("0.95")  # 95% minimum match rate
    time_tolerance_ms: int = 100  # ±100ms tolerance for signal matching

    # Execution quality thresholds
    slippage_error_bps_max: Decimal = Decimal("50")  # 50 bps = 0.5% max error
    fill_rate_error_pct_max: Decimal = Decimal("20")  # 20% max fill rate error
    commission_error_pct_max: Decimal = Decimal("10")  # 10% max commission error

    # Operational parameters
    enabled: bool = True
    sampling_rate: Decimal = Decimal("1.0")  # 100% of signals (no sampling)
    memory_limit_hours: int = 24  # Keep 24 hours of history
    grace_period_seconds: int = 300  # 5 minute grace period before tripping

    # Alert configuration
    alert_on_divergence: bool = True
    alert_email: str | None = None
    alert_webhook: str | None = None

    def __post_init__(self):
        """Validate configuration parameters."""
        # Validate signal match rate
        if not (Decimal("0") <= self.signal_match_rate_min <= Decimal("1")):
            raise ValueError(
                f"signal_match_rate_min must be between 0 and 1, got {self.signal_match_rate_min}"
            )

        # Validate sampling rate
        if not (Decimal("0") < self.sampling_rate <= Decimal("1")):
            raise ValueError(f"sampling_rate must be between 0 and 1, got {self.sampling_rate}")

        # Validate time tolerance
        if self.time_tolerance_ms < 0:
            raise ValueError(
                f"time_tolerance_ms must be non-negative, got {self.time_tolerance_ms}"
            )

        # Validate slippage error
        if self.slippage_error_bps_max < Decimal("0"):
            raise ValueError(
                f"slippage_error_bps_max must be non-negative, got {self.slippage_error_bps_max}"
            )

        logger.info(
            "shadow_config_initialized",
            signal_match_rate_min=str(self.signal_match_rate_min),
            slippage_error_bps_max=str(self.slippage_error_bps_max),
            fill_rate_error_pct_max=str(self.fill_rate_error_pct_max),
            time_tolerance_ms=self.time_tolerance_ms,
            enabled=self.enabled,
        )

    @classmethod
    def for_paper_trading(cls) -> "ShadowTradingConfig":
        """Create strict config for paper trading validation.

        Paper trading should have near-perfect alignment (99%+) since
        it uses simulated execution with same models as backtest.

        Returns:
            Config with strict thresholds for paper trading
        """
        return cls(
            signal_match_rate_min=Decimal("0.99"),  # 99% match required
            slippage_error_bps_max=Decimal("10"),  # 10 bps max (should be near zero)
            fill_rate_error_pct_max=Decimal("5"),  # 5% max (should be near zero)
            commission_error_pct_max=Decimal("2"),  # 2% max (should be near zero)
            time_tolerance_ms=50,  # Tighter tolerance
            grace_period_seconds=60,  # Shorter grace period
        )

    @classmethod
    def for_live_trading(cls) -> "ShadowTradingConfig":
        """Create relaxed config for live trading monitoring.

        Live trading has real fills subject to market conditions,
        so thresholds are more relaxed than paper trading.

        Returns:
            Config with relaxed thresholds for live trading
        """
        return cls(
            signal_match_rate_min=Decimal("0.95"),  # 95% match acceptable
            slippage_error_bps_max=Decimal("50"),  # 50 bps (real market conditions)
            fill_rate_error_pct_max=Decimal("20"),  # 20% (partial fills expected)
            commission_error_pct_max=Decimal("10"),  # 10% (broker fee variations)
            time_tolerance_ms=100,  # Standard tolerance
            grace_period_seconds=300,  # 5 minute grace period
        )

    @classmethod
    def for_high_frequency(cls) -> "ShadowTradingConfig":
        """Create config for high-frequency strategies.

        High-frequency strategies generate many signals. Use sampling
        to reduce overhead while still validating alignment.

        Returns:
            Config optimized for high-frequency trading
        """
        return cls(
            signal_match_rate_min=Decimal("0.90"),  # More relaxed (HFT complexity)
            slippage_error_bps_max=Decimal("100"),  # Higher slippage in HFT
            fill_rate_error_pct_max=Decimal("30"),  # More partial fills
            time_tolerance_ms=200,  # Wider timing tolerance
            sampling_rate=Decimal("0.1"),  # Sample 10% of signals
            memory_limit_hours=4,  # Shorter history (memory optimization)
            grace_period_seconds=600,  # 10 minute grace period
        )
