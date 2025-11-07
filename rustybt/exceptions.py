"""Centralized exception hierarchy for RustyBT.

This module defines context-rich exceptions that are shared across the
codebase.  Each exception captures the most relevant context for the
failure so we can produce structured logs for developers while still being
able to present clear user-facing messages.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


def _normalise_context(context: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a shallow copy of context with falsy values removed."""
    if not context:
        return {}
    return {str(key): value for key, value in context.items() if value is not None}


@dataclass
class RustyBTError(Exception):
    """Base exception for all RustyBT errors."""

    message: str = field(default_factory=lambda: "RustyBT encountered an error")
    context: dict[str, Any] = field(default_factory=dict)
    cause: BaseException | None = field(default=None, repr=False)

    def __init__(
        self,
        message: str | None = None,
        *,
        context: Mapping[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message or self.message)
        self.message = message or self.message
        self.context = _normalise_context(context)
        self.cause = cause

    def __str__(self) -> str:  # pragma: no cover - exercised indirectly
        if self.context:
            context_repr = ", ".join(f"{k}={v!r}" for k, v in self.context.items())
            return f"{self.message} ({context_repr})"
        return self.message

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"{self.__class__.__name__}(message={self.message!r}, context={self.context!r})"

    def to_log_fields(self) -> dict[str, Any]:
        """Return a dict suitable for structured logging."""
        payload: dict[str, Any] = {"error": self.__class__.__name__, **self.context}
        payload["message"] = self.message
        if self.cause is not None:
            payload["cause"] = repr(self.cause)
        return payload


class DataError(RustyBTError):
    """Errors related to data acquisition or quality."""

    message = "Data operation failed"


class DataNotFoundError(DataError):
    """Raised when requested data cannot be found.

    Captures details about the asset and time range that was requested
    but not available in the data source.
    """
    message = "Requested data was not found"

    def __init__(
        self,
        message: str | None = None,
        *,
        asset: str | None = None,
        start: str | None = None,
        end: str | None = None,
        context: Mapping[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        merged_context = {"asset": asset, "start": start, "end": end, **_normalise_context(context)}
        super().__init__(message or self.message, context=merged_context, cause=cause)


class DataAdapterError(DataError):
    """Raised when a data adapter encounters an error.

    Captures details about which adapter failed and retry attempts.
    """
    message = "Data adapter error"

    def __init__(
        self,
        message: str | None = None,
        *,
        adapter: str | None = None,
        attempt: int | None = None,
        context: Mapping[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        merged_context = {"adapter": adapter, "attempt": attempt, **_normalise_context(context)}
        super().__init__(message or self.message, context=merged_context, cause=cause)


class DataValidationError(DataAdapterError):
    """Raised when data fails validation checks.

    Captures information about which rows or values failed validation.
    """
    message = "Data validation failed"

    def __init__(
        self,
        message: str | None = None,
        *,
        invalid_rows: Any | None = None,
        adapter: str | None = None,
        context: Mapping[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        merged_context = {"invalid_rows": invalid_rows, **_normalise_context(context)}
        super().__init__(
            message or self.message, adapter=adapter, context=merged_context, cause=cause
        )

    @property
    def invalid_rows(self) -> Any | None:
        """Get the invalid rows from context."""
        return self.context.get("invalid_rows")


class LookaheadError(DataError):
    """Raised when code attempts to access future data (lookahead bias).

    This prevents backtests from using data that wouldn't have been
    available at the simulation time.
    """
    message = "Attempted to access future data"

    def __init__(
        self,
        message: str | None = None,
        *,
        requested_dt: str | None = None,
        current_dt: str | None = None,
        context: Mapping[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        merged_context = {
            "requested_dt": requested_dt,
            "current_dt": current_dt,
            **_normalise_context(context),
        }
        super().__init__(message or self.message, context=merged_context, cause=cause)


class OrderError(RustyBTError):
    """Base exception for order-related errors."""
    message = "Order processing failed"


class OrderRejectedError(OrderError):
    """Raised when a broker or risk control rejects an order.

    Captures details about the rejected order including order ID, asset,
    broker, and reason for rejection.
    """
    message = "Order was rejected"

    def __init__(
        self,
        message: str | None = None,
        *,
        order_id: str | None = None,
        asset: str | None = None,
        broker: str | None = None,
        reason: str | None = None,
        context: Mapping[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        merged_context = {
            "order_id": order_id,
            "asset": asset,
            "broker": broker,
            "reason": reason,
            **_normalise_context(context),
        }
        super().__init__(message or self.message, context=merged_context, cause=cause)


class OrderNotFoundError(OrderError):
    """Raised when an order cannot be found by its ID.

    This typically indicates an invalid order ID or an order that has
    already been fully processed and removed from tracking.
    """
    message = "Order not found"

    def __init__(
        self,
        message: str | None = None,
        *,
        order_id: str | None = None,
        context: Mapping[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        merged_context = {"order_id": order_id, **_normalise_context(context)}
        super().__init__(message or self.message, context=merged_context, cause=cause)


class InsufficientFundsError(OrderError):
    """Raised when an order cannot be executed due to insufficient funds.

    Captures the required amount versus available funds.
    """
    message = "Insufficient funds for order"

    def __init__(
        self,
        message: str | None = None,
        *,
        required: Any | None = None,
        available: Any | None = None,
        context: Mapping[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        merged_context = {
            "required": required,
            "available": available,
            **_normalise_context(context),
        }
        super().__init__(message or self.message, context=merged_context, cause=cause)


class InvalidOrderError(OrderError):
    """Raised when order parameters are invalid.

    Captures which parameter was invalid and what value was provided.
    """
    message = "Invalid order parameters"

    def __init__(
        self,
        message: str | None = None,
        *,
        parameter: str | None = None,
        value: Any | None = None,
        context: Mapping[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        merged_context = {
            "parameter": parameter,
            "value": value,
            **_normalise_context(context),
        }
        super().__init__(message or self.message, context=merged_context, cause=cause)


class BrokerError(RustyBTError):
    """Base exception for broker-related errors."""
    message = "Broker operation failed"


class BrokerConnectionError(BrokerError):
    """Raised when unable to establish connection with broker.

    This typically indicates network issues or broker service unavailability.
    """
    message = "Failed to connect to broker"

    def __init__(
        self,
        message: str | None = None,
        *,
        broker: str | None = None,
        context: Mapping[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        merged_context = {"broker": broker, **_normalise_context(context)}
        super().__init__(message or self.message, context=merged_context, cause=cause)


class BrokerAuthenticationError(BrokerError):
    """Raised when broker authentication fails.

    This indicates invalid credentials or expired API tokens.
    """
    message = "Broker authentication failed"

    def __init__(
        self,
        message: str | None = None,
        *,
        broker: str | None = None,
        context: Mapping[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        merged_context = {"broker": broker, **_normalise_context(context)}
        super().__init__(message or self.message, context=merged_context, cause=cause)


class BrokerRateLimitError(BrokerError):
    """Raised when broker rate limits are exceeded.

    Captures how long to wait before retrying (reset_after).
    """
    message = "Broker rate limit exceeded"

    def __init__(
        self,
        message: str | None = None,
        *,
        broker: str | None = None,
        reset_after: float | None = None,
        context: Mapping[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        merged_context = {
            "broker": broker,
            "reset_after": reset_after,
            **_normalise_context(context),
        }
        super().__init__(message or self.message, context=merged_context, cause=cause)


class BrokerResponseError(BrokerError):
    """Raised when broker returns an invalid or unexpected response.

    Captures the HTTP status code and broker identifier.
    """
    message = "Broker returned invalid response"

    def __init__(
        self,
        message: str | None = None,
        *,
        broker: str | None = None,
        status_code: int | None = None,
        context: Mapping[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        merged_context = {
            "broker": broker,
            "status_code": status_code,
            **_normalise_context(context),
        }
        super().__init__(message or self.message, context=merged_context, cause=cause)


class StrategyError(RustyBTError):
    """Base exception for strategy-related errors."""
    message = "Strategy execution failed"


class StrategyInitializationError(StrategyError):
    """Raised when strategy initialization fails.

    This occurs during the setup phase before the strategy begins execution.
    """
    message = "Strategy initialization failed"


class StrategyExecutionError(StrategyError):
    """Raised when strategy execution encounters an error.

    This covers errors during the main strategy logic execution.
    """
    message = "Strategy execution failed"


class InvalidSignalError(StrategyError):
    """Raised when a strategy produces an invalid trading signal.

    This indicates the signal doesn't meet expected format or constraints.
    """
    message = "Strategy produced an invalid signal"


class ValidationError(RustyBTError):
    """Base exception for validation errors.

    Captures which field failed validation and what value was provided.
    """
    message = "Validation failed"

    def __init__(
        self,
        message: str | None = None,
        *,
        field: str | None = None,
        value: Any | None = None,
        context: Mapping[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        merged_context = {
            "field": field,
            "value": value,
            **_normalise_context(context),
        }
        super().__init__(message or self.message, context=merged_context, cause=cause)


class ConfigValidationError(ValidationError):
    """Raised when configuration parameters are invalid."""
    message = "Configuration validation failed"


class AssetValidationError(ValidationError):
    """Raised when asset information is invalid or incomplete."""
    message = "Asset validation failed"


class ParameterValidationError(ValidationError):
    """Raised when function or method parameters are invalid."""
    message = "Parameter validation failed"


class CircuitBreakerError(RustyBTError):
    """Base exception for circuit breaker activations."""
    message = "Circuit breaker triggered"


class CircuitBreakerTrippedError(CircuitBreakerError):
    """Raised when attempting operations while circuit breaker is open.

    The circuit breaker is in OPEN state, preventing further operations
    until it resets or moves to HALF_OPEN state.
    """
    message = "Circuit breaker is in OPEN state"


class AlignmentCircuitBreakerError(CircuitBreakerError):
    """Raised when backtest and live trading results diverge significantly.

    This safety mechanism detects when live trading behavior doesn't match
    backtested expectations, potentially indicating implementation issues.
    """
    message = "Backtest/live alignment circuit breaker triggered"


__all__ = [
    "AlignmentCircuitBreakerError",
    "AssetValidationError",
    "BrokerAuthenticationError",
    "BrokerConnectionError",
    "BrokerError",
    "BrokerRateLimitError",
    "BrokerResponseError",
    "CircuitBreakerError",
    "CircuitBreakerTrippedError",
    "ConfigValidationError",
    "DataAdapterError",
    "DataError",
    "DataNotFoundError",
    "DataValidationError",
    "InsufficientFundsError",
    "InvalidOrderError",
    "InvalidSignalError",
    "LookaheadError",
    "OrderError",
    "OrderNotFoundError",
    "OrderRejectedError",
    "ParameterValidationError",
    "RustyBTError",
    "StrategyError",
    "StrategyExecutionError",
    "StrategyInitializationError",
    "ValidationError",
]
