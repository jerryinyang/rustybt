"""Retry logic with exponential backoff for transient failures.

This module provides a decorator for automatic retry with exponential backoff,
useful for handling transient failures in file I/O, network operations, or
other unreliable operations.

Example:
    >>> from rustybt.validation.resilience import retry
    >>> from pathlib import Path
    >>> import polars as pl
    >>>
    >>> @retry(max_attempts=3, backoff_factor=2, exceptions=(IOError,))
    >>> def parse_log_file(path: Path) -> pl.DataFrame:
    ...     return pl.read_parquet(path)  # May fail transiently due to file lock
"""

import functools
import logging
import time
from collections.abc import Callable
from typing import ParamSpec, TypeVar

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


def retry(
    max_attempts: int = 3,
    backoff_factor: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator that retries a function with exponential backoff on failure.

    Args:
        max_attempts: Maximum number of attempts (including initial call)
        backoff_factor: Exponential backoff multiplier (wait_time = backoff_factor ** attempt)
        exceptions: Tuple of exception types to catch and retry

    Returns:
        Decorated function that retries on specified exceptions

    Raises:
        The original exception after max_attempts is exhausted

    Example:
        >>> @retry(max_attempts=3, backoff_factor=2, exceptions=(IOError,))
        >>> def flaky_read(path):
        ...     return open(path).read()
        >>>
        >>> # Attempt 0: immediate execution
        >>> # Attempt 1: wait 2^0 = 1 second, retry
        >>> # Attempt 2: wait 2^1 = 2 seconds, retry
        >>> # Attempt 3: wait 2^2 = 4 seconds, retry
        >>> # If still failing, re-raise exception
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception: Exception | None = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    # Don't sleep after the last attempt
                    if attempt < max_attempts - 1:
                        wait_time = backoff_factor**attempt
                        logger.debug(
                            f"Retry {attempt + 1}/{max_attempts} for {func.__name__} "
                            f"after {wait_time}s (error: {e})"
                        )
                        time.sleep(wait_time)

            # Re-raise the last exception after exhausting all attempts
            logger.warning(
                f"Function {func.__name__} failed after {max_attempts} attempts"
            )
            if last_exception:
                raise last_exception
            else:
                # This should never happen, but satisfies type checker
                raise RuntimeError("Retry failed but no exception was raised")

        return wrapper

    return decorator
