"""Timeout decorator for enforcing execution time limits.

This module provides a decorator for enforcing maximum execution time on
functions that may hang or run indefinitely. Uses signal.alarm() which is
POSIX-only (Linux, macOS) and does NOT work on Windows.

Note:
    This implementation is POSIX-only. For Windows support, consider using
    threading.Timer or multiprocessing with timeout instead.

Example:
    >>> from rustybt.validation.timeouts import timeout
    >>>
    >>> @timeout(seconds=300)
    >>> def execute_strategy(strategy, data):
    ...     # Will raise TimeoutError if execution exceeds 5 minutes
    ...     return run_backtest(strategy, data)
"""

import functools
import signal
from collections.abc import Callable
from types import FrameType
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")


class ValidationTimeoutError(Exception):
    """Raised when a function execution exceeds the configured timeout."""

    pass


def timeout(seconds: int) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator that enforces a maximum execution time on a function.

    Uses signal.alarm() to interrupt function execution after the specified
    number of seconds. This is POSIX-only and will NOT work on Windows.

    Args:
        seconds: Maximum execution time in seconds

    Returns:
        Decorated function that raises ValidationTimeoutError if execution exceeds limit

    Raises:
        ValidationTimeoutError: If function execution exceeds the specified timeout

    Note:
        POSIX systems only (Linux, macOS). Does not work on Windows.
        Only one alarm can be scheduled at a time per process.

    Example:
        >>> @timeout(seconds=5)
        >>> def slow_operation():
        ...     time.sleep(10)  # Will timeout after 5 seconds
        >>>
        >>> try:
        ...     slow_operation()
        ... except ValidationTimeoutError:
        ...     print("Operation timed out!")
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        def _timeout_handler(_signum: int, _frame: FrameType | None) -> None:
            raise ValidationTimeoutError(
                f"Function {func.__name__} exceeded {seconds}s timeout"
            )

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Set up the timeout handler
            old_handler = signal.signal(signal.SIGALRM, _timeout_handler)

            # Schedule the alarm
            signal.alarm(seconds)

            try:
                result = func(*args, **kwargs)
            finally:
                # Always cancel the alarm and restore old handler
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)

            return result

        return wrapper

    return decorator


# Future usage patterns (to be applied in Epic 2 and Epic 4)
"""
Recommended timeout values for different operations:

1. Strategy execution (Epic 2):
   @timeout(seconds=300)  # 5 minutes max
   def execute_strategy(strategy, data):
       return run_backtest(strategy, data)

2. Layer comparison (Epic 4):
   @timeout(seconds=120)  # 2 minutes per layer
   def compare_layer(rustybt_logs, backtrader_logs, layer):
       return comparator.compare(rustybt_logs, backtrader_logs)

3. Report generation (Epic 7):
   @timeout(seconds=60)  # 1 minute for report generation
   def generate_report(session):
       return ReportGenerator(session).generate()

Note: Timeouts should be tuned based on actual performance measurements
during benchmarking (Story 7.4).
"""
