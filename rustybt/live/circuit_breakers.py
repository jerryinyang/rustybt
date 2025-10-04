"""Circuit breakers for live trading risk management.

This module implements various circuit breakers to prevent catastrophic losses:
- DrawdownCircuitBreaker: Halt if portfolio drawdown exceeds threshold
- DailyLossCircuitBreaker: Halt if daily loss exceeds limit
- OrderRateCircuitBreaker: Prevent runaway order submission
- ErrorRateCircuitBreaker: Halt on repeated errors
- ManualCircuitBreaker: Emergency stop capability
"""

import asyncio
from collections import deque
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any

import pandas as pd
import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


class CircuitBreakerState(Enum):
    """Circuit breaker states."""

    NORMAL = "normal"
    TRIPPED = "tripped"
    MANUALLY_HALTED = "manually_halted"
    RESETTING = "resetting"


class CircuitBreakerType(Enum):
    """Types of circuit breakers."""

    DRAWDOWN = "drawdown"
    DAILY_LOSS = "daily_loss"
    ORDER_RATE = "order_rate"
    ERROR_RATE = "error_rate"
    MANUAL = "manual"


class CircuitBreakerTrippedEvent(BaseModel):
    """Event emitted when circuit breaker trips.

    Args:
        breaker_type: Type of circuit breaker that tripped
        reason: Human-readable reason for trip
        timestamp: When the breaker tripped
        details: Additional details about the trip condition
    """

    breaker_type: CircuitBreakerType
    reason: str
    timestamp: pd.Timestamp = Field(default_factory=pd.Timestamp.now)
    details: dict[str, Any] = Field(default_factory=dict)

    class Config:
        """Pydantic config."""

        frozen = True
        arbitrary_types_allowed = True


class ManualHaltEvent(BaseModel):
    """Event emitted when manual halt triggered.

    Args:
        reason: Reason for manual halt
        operator: Operator who triggered the halt (username, API client, etc.)
        timestamp: When the halt was triggered
    """

    reason: str
    operator: str
    timestamp: pd.Timestamp = Field(default_factory=pd.Timestamp.now)

    class Config:
        """Pydantic config."""

        frozen = True
        arbitrary_types_allowed = True


class CircuitBreakerError(Exception):
    """Exception raised when circuit breaker prevents operation."""

    pass


class BaseCircuitBreaker:
    """Base class for all circuit breakers.

    Provides common functionality for state tracking and event emission.
    """

    def __init__(self, breaker_type: CircuitBreakerType) -> None:
        """Initialize base circuit breaker.

        Args:
            breaker_type: Type of circuit breaker
        """
        self._breaker_type = breaker_type
        self._state = CircuitBreakerState.NORMAL
        self._trip_time: pd.Timestamp | None = None
        self._trip_reason: str | None = None

    @property
    def state(self) -> CircuitBreakerState:
        """Get current circuit breaker state."""
        return self._state

    @property
    def is_tripped(self) -> bool:
        """Check if circuit breaker is tripped."""
        return self._state in (CircuitBreakerState.TRIPPED, CircuitBreakerState.MANUALLY_HALTED)

    def reset(self) -> None:
        """Reset circuit breaker to NORMAL state.

        Requires manual confirmation in production systems.
        """
        logger.info(
            "circuit_breaker_reset",
            breaker_type=self._breaker_type.value,
            previous_state=self._state.value,
        )
        self._state = CircuitBreakerState.NORMAL
        self._trip_time = None
        self._trip_reason = None

    def _trip(
        self, reason: str, details: dict[str, Any] | None = None
    ) -> CircuitBreakerTrippedEvent:
        """Trip the circuit breaker.

        Args:
            reason: Human-readable reason for trip
            details: Additional details about the trip condition

        Returns:
            CircuitBreakerTrippedEvent to be emitted
        """
        self._state = CircuitBreakerState.TRIPPED
        self._trip_time = pd.Timestamp.now()
        self._trip_reason = reason

        logger.critical(
            "circuit_breaker_tripped",
            breaker_type=self._breaker_type.value,
            reason=reason,
            details=details or {},
        )

        return CircuitBreakerTrippedEvent(
            breaker_type=self._breaker_type,
            reason=reason,
            timestamp=self._trip_time,
            details=details or {},
        )


class DrawdownCircuitBreaker(BaseCircuitBreaker):
    """Circuit breaker that halts trading if portfolio drawdown exceeds threshold.

    Tracks the high-water mark (highest portfolio value) and calculates drawdown
    as percentage decline from that peak. Trips when drawdown exceeds threshold.

    Args:
        threshold: Maximum allowed drawdown (negative decimal, e.g., -0.10 for -10%)
        initial_portfolio_value: Starting portfolio value for high-water mark

    Example:
        >>> breaker = DrawdownCircuitBreaker(
        ...     threshold=Decimal("-0.10"), initial_portfolio_value=Decimal("100000")
        ... )
        >>> event = breaker.check(Decimal("89000"))  # -11% drawdown, will trip
    """

    def __init__(
        self,
        threshold: Decimal,
        initial_portfolio_value: Decimal,
    ) -> None:
        """Initialize drawdown circuit breaker.

        Args:
            threshold: Maximum allowed drawdown (negative decimal, e.g., -0.10 for -10%)
            initial_portfolio_value: Starting portfolio value for high-water mark
        """
        super().__init__(CircuitBreakerType.DRAWDOWN)
        self._threshold = threshold
        self._high_water_mark = initial_portfolio_value
        logger.info(
            "drawdown_circuit_breaker_initialized",
            threshold=str(threshold),
            initial_value=str(initial_portfolio_value),
        )

    def check(self, current_portfolio_value: Decimal) -> CircuitBreakerTrippedEvent | None:
        """Check if drawdown exceeds threshold.

        Updates high-water mark if current value is higher. Calculates drawdown
        and trips breaker if threshold exceeded.

        Args:
            current_portfolio_value: Current portfolio value

        Returns:
            CircuitBreakerTrippedEvent if tripped, None otherwise
        """
        # Already tripped, no need to check
        if self.is_tripped:
            return None

        # Update high-water mark
        if current_portfolio_value > self._high_water_mark:
            self._high_water_mark = current_portfolio_value
            logger.debug(
                "high_water_mark_updated",
                new_hwm=str(self._high_water_mark),
            )

        # Calculate drawdown
        drawdown = (current_portfolio_value - self._high_water_mark) / self._high_water_mark

        # Check threshold
        if drawdown <= self._threshold:
            return self._trip(
                reason="Portfolio drawdown exceeded threshold",
                details={
                    "current_value": str(current_portfolio_value),
                    "high_water_mark": str(self._high_water_mark),
                    "drawdown": str(drawdown),
                    "threshold": str(self._threshold),
                },
            )

        return None


class DailyLossCircuitBreaker(BaseCircuitBreaker):
    """Circuit breaker that halts trading if daily loss exceeds limit.

    Tracks starting portfolio value at market open (reset daily) and calculates
    daily loss. Trips when loss exceeds configured limit.

    Args:
        limit: Maximum allowed daily loss (negative decimal or absolute amount)
        initial_portfolio_value: Starting portfolio value for the day
        is_percentage: If True, limit is percentage; if False, absolute amount

    Example:
        >>> breaker = DailyLossCircuitBreaker(
        ...     limit=Decimal("-0.05"),
        ...     initial_portfolio_value=Decimal("100000"),
        ...     is_percentage=True,
        ... )
        >>> event = breaker.check(Decimal("94000"))  # -6% loss, will trip
    """

    def __init__(
        self,
        limit: Decimal,
        initial_portfolio_value: Decimal,
        is_percentage: bool = True,
    ) -> None:
        """Initialize daily loss circuit breaker.

        Args:
            limit: Maximum allowed daily loss (negative decimal or absolute amount)
            initial_portfolio_value: Starting portfolio value for the day
            is_percentage: If True, limit is percentage; if False, absolute amount
        """
        super().__init__(CircuitBreakerType.DAILY_LOSS)
        self._limit = limit
        self._starting_value = initial_portfolio_value
        self._is_percentage = is_percentage
        logger.info(
            "daily_loss_circuit_breaker_initialized",
            limit=str(limit),
            is_percentage=is_percentage,
            starting_value=str(initial_portfolio_value),
        )

    def reset_daily(self, new_starting_value: Decimal) -> None:
        """Reset daily loss counter at market open.

        Args:
            new_starting_value: New starting portfolio value for the day
        """
        self._starting_value = new_starting_value
        # Only reset if not manually halted
        if self._state == CircuitBreakerState.TRIPPED:
            self._state = CircuitBreakerState.NORMAL
            self._trip_time = None
            self._trip_reason = None
        logger.info("daily_loss_reset", starting_value=str(new_starting_value))

    def check(self, current_portfolio_value: Decimal) -> CircuitBreakerTrippedEvent | None:
        """Check if daily loss exceeds limit.

        Args:
            current_portfolio_value: Current portfolio value

        Returns:
            CircuitBreakerTrippedEvent if tripped, None otherwise
        """
        # Already tripped, no need to check
        if self.is_tripped:
            return None

        # Calculate daily loss
        loss_amount = current_portfolio_value - self._starting_value

        if self._is_percentage:
            loss_percentage = loss_amount / self._starting_value
            if loss_percentage <= self._limit:
                return self._trip(
                    reason="Daily loss exceeded percentage limit",
                    details={
                        "current_value": str(current_portfolio_value),
                        "starting_value": str(self._starting_value),
                        "loss_percentage": str(loss_percentage),
                        "limit": str(self._limit),
                        "loss_amount": str(loss_amount),
                    },
                )
        else:
            if loss_amount <= self._limit:
                return self._trip(
                    reason="Daily loss exceeded absolute limit",
                    details={
                        "current_value": str(current_portfolio_value),
                        "starting_value": str(self._starting_value),
                        "loss_amount": str(loss_amount),
                        "limit": str(self._limit),
                    },
                )

        return None


class OrderRateCircuitBreaker(BaseCircuitBreaker):
    """Circuit breaker that prevents runaway order submission.

    Tracks order submission timestamps in sliding window and trips if rate
    exceeds configured limit.

    Args:
        max_orders: Maximum number of orders allowed in window
        window_seconds: Time window in seconds for rate calculation

    Example:
        >>> breaker = OrderRateCircuitBreaker(max_orders=100, window_seconds=60)
        >>> for _ in range(101):
        ...     event = breaker.record_order()  # 101st order will trip
    """

    def __init__(self, max_orders: int, window_seconds: int = 60) -> None:
        """Initialize order rate circuit breaker.

        Args:
            max_orders: Maximum number of orders allowed in window
            window_seconds: Time window in seconds for rate calculation
        """
        super().__init__(CircuitBreakerType.ORDER_RATE)
        self._max_orders = max_orders
        self._window_seconds = window_seconds
        self._order_timestamps: deque[datetime] = deque()
        logger.info(
            "order_rate_circuit_breaker_initialized",
            max_orders=max_orders,
            window_seconds=window_seconds,
        )

    def record_order(self) -> CircuitBreakerTrippedEvent | None:
        """Record order submission and check rate limit.

        Returns:
            CircuitBreakerTrippedEvent if tripped, None otherwise
        """
        # Already tripped, block all orders
        if self.is_tripped:
            raise CircuitBreakerError(f"Order rate circuit breaker tripped: {self._trip_reason}")

        now = datetime.now()
        self._order_timestamps.append(now)

        # Remove orders outside window
        cutoff = now - timedelta(seconds=self._window_seconds)
        while self._order_timestamps and self._order_timestamps[0] < cutoff:
            self._order_timestamps.popleft()

        # Check rate
        order_count = len(self._order_timestamps)
        if order_count > self._max_orders:
            return self._trip(
                reason="Order rate exceeded limit",
                details={
                    "order_count": order_count,
                    "max_orders": self._max_orders,
                    "window_seconds": self._window_seconds,
                },
            )

        return None


class ErrorRateCircuitBreaker(BaseCircuitBreaker):
    """Circuit breaker that halts on repeated errors.

    Tracks order rejections and errors in sliding window and trips if rate
    exceeds configured limit. Distinguishes different error types.

    Args:
        max_errors: Maximum number of errors allowed in window
        window_seconds: Time window in seconds for error rate calculation

    Example:
        >>> breaker = ErrorRateCircuitBreaker(max_errors=10, window_seconds=60)
        >>> for _ in range(11):
        ...     event = breaker.record_error("order_rejected")  # 11th error will trip
    """

    def __init__(self, max_errors: int, window_seconds: int = 60) -> None:
        """Initialize error rate circuit breaker.

        Args:
            max_errors: Maximum number of errors allowed in window
            window_seconds: Time window in seconds for error rate calculation
        """
        super().__init__(CircuitBreakerType.ERROR_RATE)
        self._max_errors = max_errors
        self._window_seconds = window_seconds
        self._error_records: deque[tuple[datetime, str]] = deque()  # (timestamp, error_type)
        logger.info(
            "error_rate_circuit_breaker_initialized",
            max_errors=max_errors,
            window_seconds=window_seconds,
        )

    def record_error(self, error_type: str) -> CircuitBreakerTrippedEvent | None:
        """Record error and check error rate limit.

        Args:
            error_type: Type of error (e.g., "order_rejected", "broker_error", "data_error")

        Returns:
            CircuitBreakerTrippedEvent if tripped, None otherwise
        """
        # Already tripped, halt trading
        if self.is_tripped:
            return None

        now = datetime.now()
        self._error_records.append((now, error_type))

        # Remove errors outside window
        cutoff = now - timedelta(seconds=self._window_seconds)
        while self._error_records and self._error_records[0][0] < cutoff:
            self._error_records.popleft()

        # Check error rate
        error_count = len(self._error_records)
        if error_count > self._max_errors:
            # Count error types
            error_types_count: dict[str, int] = {}
            for _, err_type in self._error_records:
                error_types_count[err_type] = error_types_count.get(err_type, 0) + 1

            return self._trip(
                reason="Error rate exceeded limit",
                details={
                    "error_count": error_count,
                    "max_errors": self._max_errors,
                    "window_seconds": self._window_seconds,
                    "error_types": error_types_count,
                },
            )

        return None


class ManualCircuitBreaker(BaseCircuitBreaker):
    """Manual emergency stop circuit breaker.

    Provides explicit manual halt and reset capability for emergency situations.

    Example:
        >>> breaker = ManualCircuitBreaker()
        >>> event = breaker.trip("Market anomaly detected", operator="trader_alice")
        >>> breaker.reset()
    """

    def __init__(self) -> None:
        """Initialize manual circuit breaker."""
        super().__init__(CircuitBreakerType.MANUAL)
        logger.info("manual_circuit_breaker_initialized")

    def trip(self, reason: str, operator: str = "unknown") -> ManualHaltEvent:
        """Manually trip the circuit breaker.

        Args:
            reason: Reason for manual halt
            operator: Operator who triggered the halt (username, API client, etc.)

        Returns:
            ManualHaltEvent to be emitted
        """
        self._state = CircuitBreakerState.MANUALLY_HALTED
        self._trip_time = pd.Timestamp.now()
        self._trip_reason = reason

        logger.critical(
            "manual_circuit_breaker_tripped",
            reason=reason,
            operator=operator,
        )

        return ManualHaltEvent(
            reason=reason,
            operator=operator,
            timestamp=self._trip_time,
        )


class CircuitBreakerManager:
    """Manages all circuit breakers for live trading engine.

    Coordinates multiple circuit breakers and provides unified interface
    for checking and managing circuit breaker state.

    Args:
        drawdown_breaker: Optional drawdown circuit breaker
        daily_loss_breaker: Optional daily loss circuit breaker
        order_rate_breaker: Optional order rate circuit breaker
        error_rate_breaker: Optional error rate circuit breaker
        manual_breaker: Optional manual circuit breaker (created by default)

    Example:
        >>> manager = CircuitBreakerManager(
        ...     drawdown_breaker=DrawdownCircuitBreaker(Decimal("-0.10"), Decimal("100000")),
        ...     daily_loss_breaker=DailyLossCircuitBreaker(Decimal("-0.05"), Decimal("100000")),
        ... )
        >>> manager.check_drawdown(Decimal("89000"))
    """

    def __init__(
        self,
        drawdown_breaker: DrawdownCircuitBreaker | None = None,
        daily_loss_breaker: DailyLossCircuitBreaker | None = None,
        order_rate_breaker: OrderRateCircuitBreaker | None = None,
        error_rate_breaker: ErrorRateCircuitBreaker | None = None,
        manual_breaker: ManualCircuitBreaker | None = None,
    ) -> None:
        """Initialize circuit breaker manager.

        Args:
            drawdown_breaker: Optional drawdown circuit breaker
            daily_loss_breaker: Optional daily loss circuit breaker
            order_rate_breaker: Optional order rate circuit breaker
            error_rate_breaker: Optional error rate circuit breaker
            manual_breaker: Optional manual circuit breaker (created by default)
        """
        self._drawdown_breaker = drawdown_breaker
        self._daily_loss_breaker = daily_loss_breaker
        self._order_rate_breaker = order_rate_breaker
        self._error_rate_breaker = error_rate_breaker
        self._manual_breaker = manual_breaker or ManualCircuitBreaker()
        self._event_callbacks: list[Any] = []

        logger.info(
            "circuit_breaker_manager_initialized",
            drawdown_enabled=drawdown_breaker is not None,
            daily_loss_enabled=daily_loss_breaker is not None,
            order_rate_enabled=order_rate_breaker is not None,
            error_rate_enabled=error_rate_breaker is not None,
        )

    def register_event_callback(self, callback: Any) -> None:
        """Register callback for circuit breaker events.

        Args:
            callback: Async callback function to receive circuit breaker events
        """
        self._event_callbacks.append(callback)

    async def _emit_event(self, event: Any) -> None:
        """Emit circuit breaker event to all registered callbacks.

        Args:
            event: Circuit breaker event to emit
        """
        for callback in self._event_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                logger.error("event_callback_error", error=str(e), exc_info=True)

    @property
    def state(self) -> CircuitBreakerState:
        """Get overall circuit breaker state.

        Returns highest priority state from all breakers.
        """
        # Check manual halt first
        if self._manual_breaker.state == CircuitBreakerState.MANUALLY_HALTED:
            return CircuitBreakerState.MANUALLY_HALTED

        # Check if any breaker is tripped
        breakers = [
            self._drawdown_breaker,
            self._daily_loss_breaker,
            self._order_rate_breaker,
            self._error_rate_breaker,
        ]
        for breaker in breakers:
            if breaker and breaker.is_tripped:
                return CircuitBreakerState.TRIPPED

        return CircuitBreakerState.NORMAL

    @property
    def is_tripped(self) -> bool:
        """Check if any circuit breaker is tripped."""
        return self.state in (CircuitBreakerState.TRIPPED, CircuitBreakerState.MANUALLY_HALTED)

    async def check_drawdown(self, current_portfolio_value: Decimal) -> None:
        """Check drawdown circuit breaker.

        Args:
            current_portfolio_value: Current portfolio value
        """
        if self._drawdown_breaker:
            event = self._drawdown_breaker.check(current_portfolio_value)
            if event:
                await self._emit_event(event)

    async def check_daily_loss(self, current_portfolio_value: Decimal) -> None:
        """Check daily loss circuit breaker.

        Args:
            current_portfolio_value: Current portfolio value
        """
        if self._daily_loss_breaker:
            event = self._daily_loss_breaker.check(current_portfolio_value)
            if event:
                await self._emit_event(event)

    async def record_order(self) -> None:
        """Record order submission and check rate limit.

        Raises:
            CircuitBreakerError: If order rate circuit breaker is tripped
        """
        if self._order_rate_breaker:
            event = self._order_rate_breaker.record_order()
            if event:
                await self._emit_event(event)

    async def record_error(self, error_type: str) -> None:
        """Record error and check error rate limit.

        Args:
            error_type: Type of error (e.g., "order_rejected", "broker_error")
        """
        if self._error_rate_breaker:
            event = self._error_rate_breaker.record_error(error_type)
            if event:
                await self._emit_event(event)

    async def manual_halt(self, reason: str, operator: str = "unknown") -> None:
        """Manually halt trading.

        Args:
            reason: Reason for manual halt
            operator: Operator who triggered the halt
        """
        event = self._manual_breaker.trip(reason, operator)
        await self._emit_event(event)

    def reset_all(self) -> None:
        """Reset all circuit breakers to NORMAL state.

        IMPORTANT: This should require manual confirmation in production.
        """
        logger.warning("resetting_all_circuit_breakers")

        if self._drawdown_breaker:
            self._drawdown_breaker.reset()
        if self._daily_loss_breaker:
            self._daily_loss_breaker.reset()
        if self._order_rate_breaker:
            self._order_rate_breaker.reset()
        if self._error_rate_breaker:
            self._error_rate_breaker.reset()
        if self._manual_breaker:
            self._manual_breaker.reset()

        logger.info("all_circuit_breakers_reset")

    def reset_daily_loss(self, new_starting_value: Decimal) -> None:
        """Reset daily loss circuit breaker at market open.

        Args:
            new_starting_value: New starting portfolio value for the day
        """
        if self._daily_loss_breaker:
            self._daily_loss_breaker.reset_daily(new_starting_value)

    def get_status(self) -> dict[str, Any]:
        """Get status of all circuit breakers.

        Returns:
            Dictionary with status of all breakers
        """
        return {
            "overall_state": self.state.value,
            "is_tripped": self.is_tripped,
            "drawdown": {
                "enabled": self._drawdown_breaker is not None,
                "state": self._drawdown_breaker.state.value if self._drawdown_breaker else None,
            },
            "daily_loss": {
                "enabled": self._daily_loss_breaker is not None,
                "state": self._daily_loss_breaker.state.value if self._daily_loss_breaker else None,
            },
            "order_rate": {
                "enabled": self._order_rate_breaker is not None,
                "state": self._order_rate_breaker.state.value if self._order_rate_breaker else None,
            },
            "error_rate": {
                "enabled": self._error_rate_breaker is not None,
                "state": self._error_rate_breaker.state.value if self._error_rate_breaker else None,
            },
            "manual": {
                "enabled": True,
                "state": self._manual_breaker.state.value,
            },
        }
