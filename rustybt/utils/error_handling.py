"""Shared error handling utilities for RustyBT."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable, Iterable
from typing import Any, TypeVar

import structlog

from rustybt.exceptions import RustyBTError

logger = structlog.get_logger(__name__)

T = TypeVar("T")


async def retry_async(
    operation: Callable[[], Awaitable[T]],
    *,
    retry_exceptions: tuple[type[BaseException], ...],
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
    jitter: float = 0.25,
    context: dict[str, Any] | None = None,
) -> T:
    """Retry ``operation`` for transient failures with exponential backoff.

    Args:
        operation: Async callable to execute.
        retry_exceptions: Exceptions that should trigger a retry.
        max_attempts: Maximum number of attempts (including first try).
        base_delay: Initial backoff delay in seconds.
        max_delay: Maximum delay between attempts.
        backoff_factor: Exponential backoff multiplier.
        jitter: Fractional jitter (0.0-1.0) to randomise delay.
        context: Additional context fields for logging.

    Returns:
        Result of ``operation``.

    Raises:
        Exception: Re-raises the last encountered exception if retries exhausted.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")

    attempt = 0
    context = context or {}

    while True:
        try:
            return await operation()
        except retry_exceptions as exc:
            attempt += 1
            if attempt >= max_attempts:
                logger.error(
                    "retry_exhausted",
                    attempt=attempt,
                    max_attempts=max_attempts,
                    **context,
                    error=str(exc),
                )
                raise

            delay = min(base_delay * (backoff_factor ** (attempt - 1)), max_delay)
            if jitter:
                jitter_amount = delay * random.uniform(-jitter, jitter)
                delay = max(0.0, delay + jitter_amount)

            logger.warning(
                "retrying_operation",
                attempt=attempt,
                max_attempts=max_attempts,
                delay=delay,
                **context,
                error=str(exc),
            )

            await asyncio.sleep(delay)


def render_user_message(error: BaseException) -> str:
    """Return a concise user-facing message for ``error``."""
    if isinstance(error, RustyBTError):
        return error.message
    return "An unexpected error occurred. Please try again or contact support."


def render_developer_context(error: BaseException) -> dict[str, Any]:
    """Return structured context suitable for developer logs."""
    if isinstance(error, RustyBTError):
        return error.to_log_fields()
    return {"error": error.__class__.__name__, "message": str(error)}


def log_exception(
    error: BaseException,
    *,
    level: str = "error",
    extra: dict[str, Any] | None = None,
) -> None:
    """Log ``error`` with structured context."""
    log_fields = render_developer_context(error)
    if extra:
        log_fields.update(extra)

    log_method = getattr(logger, level, logger.error)
    log_method("exception", **log_fields)


def flatten_exceptions(errors: Iterable[BaseException]) -> dict[str, Any]:
    """Return merged context for a sequence of exceptions."""
    summary: dict[str, Any] = {}
    for index, error in enumerate(errors, start=1):
        prefix = f"error_{index}"
        if isinstance(error, RustyBTError):
            summary[prefix] = error.__class__.__name__
            summary.update({f"{prefix}_{k}": v for k, v in error.context.items()})
        else:
            summary[prefix] = error.__class__.__name__
            summary[f"{prefix}_message"] = str(error)
    return summary


__all__ = [
    "flatten_exceptions",
    "log_exception",
    "render_developer_context",
    "render_user_message",
    "retry_async",
]
