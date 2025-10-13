"""
Rust-optimized functions with pure Python fallbacks.

This module provides a unified API for performance-critical operations,
automatically using Rust implementations when available and falling back
to pure Python when Rust extensions are not installed.

Usage:
    from rustybt.rust_optimizations import rust_sma, rust_ema

    prices = [100.0, 102.0, 101.0, 103.0, 105.0]
    sma = rust_sma(prices, window=3)
"""

import logging
import math
from collections.abc import Sequence
from decimal import Decimal, getcontext
from typing import Union

logger = logging.getLogger(__name__)

# Try to import Rust extensions
try:
    from rustybt._rustybt import (
        rust_array_sum as _rust_array_sum,
    )
    from rustybt._rustybt import (
        rust_create_columns as _rust_create_columns,
    )
    from rustybt._rustybt import (
        rust_decimal_ema as _rust_decimal_ema,
    )
    from rustybt._rustybt import (
        rust_decimal_fillna as _rust_decimal_fillna,
    )
    from rustybt._rustybt import (
        rust_decimal_index_select as _rust_decimal_index_select,
    )
    from rustybt._rustybt import (
        rust_decimal_mean as _rust_decimal_mean,
    )
    from rustybt._rustybt import (
        rust_decimal_pairwise_op as _rust_decimal_pairwise_op,
    )
    from rustybt._rustybt import (
        rust_decimal_rolling_sum as _rust_decimal_rolling_sum,
    )
    from rustybt._rustybt import (
        rust_decimal_sma as _rust_decimal_sma,
    )
    from rustybt._rustybt import (
        rust_decimal_sum as _rust_decimal_sum,
    )
    from rustybt._rustybt import (
        rust_decimal_window_slice as _rust_decimal_window_slice,
    )
    from rustybt._rustybt import (
        rust_ema as _rust_ema,
    )
    from rustybt._rustybt import (
        rust_fillna as _rust_fillna,
    )
    from rustybt._rustybt import (
        rust_index_select as _rust_index_select,
    )
    from rustybt._rustybt import (
        rust_mean as _rust_mean,
    )
    from rustybt._rustybt import (
        rust_pairwise_op as _rust_pairwise_op,
    )
    from rustybt._rustybt import (
        rust_rolling_sum as _rust_rolling_sum,
    )
    from rustybt._rustybt import (
        rust_sma as _rust_sma,
    )
    from rustybt._rustybt import (
        rust_window_slice as _rust_window_slice,
    )

    RUST_AVAILABLE = True
    logger.info("Rust optimizations available and loaded")
except ImportError as e:
    RUST_AVAILABLE = False
    logger.warning(f"Rust optimizations not available ({e}), using Python fallbacks")
    _rust_sma = None
    _rust_ema = None
    _rust_array_sum = None
    _rust_mean = None
    _rust_rolling_sum = None
    _rust_window_slice = None
    _rust_create_columns = None
    _rust_index_select = None
    _rust_fillna = None
    _rust_pairwise_op = None
    _rust_decimal_window_slice = None
    _rust_decimal_index_select = None
    _rust_decimal_sum = None
    _rust_decimal_mean = None
    _rust_decimal_sma = None
    _rust_decimal_ema = None
    _rust_decimal_rolling_sum = None
    _rust_decimal_pairwise_op = None
    _rust_decimal_fillna = None


Number = Union[float, Decimal]


def _has_decimal(values: Sequence[Number]) -> bool:
    """Return True if the sequence contains at least one Decimal value."""
    for value in values:
        if isinstance(value, Decimal):
            return True
    return False


def _decimal_context_params() -> tuple[int, str]:
    ctx = getcontext()
    return ctx.prec, ctx.rounding


def _decimal_nan() -> Decimal:
    return Decimal("NaN")


def _python_float_sma(values: Sequence[float], window: int) -> list[float]:
    if window <= 0:
        raise ValueError("Window size must be greater than 0")
    if not values:
        return []

    result = [math.nan] * len(values)
    if len(values) < window:
        return result

    first_sum = sum(values[:window])
    result[window - 1] = first_sum / window

    rolling_sum = first_sum
    for idx in range(window, len(values)):
        rolling_sum += values[idx]
        rolling_sum -= values[idx - window]
        result[idx] = rolling_sum / window

    return result


def _python_decimal_sma(values: Sequence[Decimal], window: int) -> list[Decimal]:
    if window <= 0:
        raise ValueError("Window size must be greater than 0")
    if not values:
        return []

    nan_value = _decimal_nan()
    result: list[Decimal] = [nan_value] * len(values)
    if len(values) < window:
        return result

    ctx = getcontext()
    total = sum(values[:window], Decimal(0))
    result[window - 1] = ctx.divide(total, Decimal(window))

    rolling_sum = total
    for idx in range(window, len(values)):
        rolling_sum += values[idx]
        rolling_sum -= values[idx - window]
        result[idx] = ctx.divide(rolling_sum, Decimal(window))

    return result


def _python_float_ema(values: Sequence[float], span: int) -> list[float]:
    if span <= 0:
        raise ValueError("Span must be greater than 0")
    if not values:
        return []

    alpha = 2.0 / (span + 1.0)
    result = [0.0] * len(values)
    result[0] = values[0]
    for idx in range(1, len(values)):
        result[idx] = alpha * values[idx] + (1.0 - alpha) * result[idx - 1]
    return result


def _python_decimal_ema(values: Sequence[Decimal], span: int) -> list[Decimal]:
    if span <= 0:
        raise ValueError("Span must be greater than 0")
    if not values:
        return []

    ctx = getcontext()
    two = Decimal(2)
    alpha = ctx.divide(two, Decimal(span + 1))
    one_minus_alpha = Decimal(1) - alpha

    result: list[Decimal] = []
    ema = values[0]
    result.append(ema)

    for value in values[1:]:
        ema = ctx.add(ctx.multiply(alpha, value), ctx.multiply(one_minus_alpha, ema))
        result.append(ema)

    return result


def _python_float_rolling_sum(values: Sequence[float], window: int) -> list[float]:
    if window <= 0:
        raise ValueError("Window size must be greater than 0")
    if not values:
        return []

    result = [math.nan] * len(values)
    if len(values) < window:
        return result

    rolling_sum = sum(values[:window])
    result[window - 1] = rolling_sum

    for idx in range(window, len(values)):
        rolling_sum += values[idx]
        rolling_sum -= values[idx - window]
        result[idx] = rolling_sum

    return result


def _python_decimal_rolling_sum(values: Sequence[Decimal], window: int) -> list[Decimal]:
    if window <= 0:
        raise ValueError("Window size must be greater than 0")
    if not values:
        return []

    nan_value = _decimal_nan()
    result: list[Decimal] = [nan_value] * len(values)
    if len(values) < window:
        return result

    rolling_sum = sum(values[:window], Decimal(0))
    result[window - 1] = rolling_sum

    for idx in range(window, len(values)):
        rolling_sum += values[idx]
        rolling_sum -= values[idx - window]
        result[idx] = rolling_sum

    return result


def _validate_window_bounds(sequence: Sequence[Number], start: int, end: int) -> None:
    length = len(sequence)
    if start >= length or end > length or start >= end:
        raise IndexError(f"Invalid window bounds: start={start}, end={end}, len={length}")


# Technical Indicators


def rust_sma(values: Sequence[Number], window: int) -> list[Number]:
    """
    Calculate Simple Moving Average (SMA).

    Args:
        values: List of price values
        window: Window size for the moving average

    Returns:
        List of SMA values (first window-1 elements are NaN)

    Example:
        >>> rust_sma([1.0, 2.0, 3.0, 4.0, 5.0], 3)
        [nan, nan, 2.0, 3.0, 4.0]
    """
    values_list = list(values)
    if window <= 0:
        raise ValueError("Window size must be greater than 0")
    if not values_list:
        return []
    if _has_decimal(values_list):
        precision, rounding = _decimal_context_params()
        if RUST_AVAILABLE and _rust_decimal_sma is not None:
            try:
                return _rust_decimal_sma(values_list, window, precision, rounding)
            except ValueError as e:
                # Fall back to Python for extreme values outside rust-decimal range
                logger.debug(f"Rust SMA failed ({e}), falling back to Python Decimal")
                return _python_decimal_sma(values_list, window)
        return _python_decimal_sma(values_list, window)

    if RUST_AVAILABLE and _rust_sma is not None:
        return _rust_sma(values_list, window)

    return _python_float_sma(values_list, window)


def rust_ema(values: Sequence[Number], span: int) -> list[Number]:
    """
    Calculate Exponential Moving Average (EMA).

    Args:
        values: List of price values
        span: Span for the EMA (higher span = more smoothing)

    Returns:
        List of EMA values (uses first value as initial EMA)

    Example:
        >>> rust_ema([1.0, 2.0, 3.0, 4.0, 5.0], 3)
        [1.0, 1.5, 2.25, 3.125, 4.0625]
    """
    values_list = list(values)
    if span <= 0:
        raise ValueError("Span must be greater than 0")
    if not values_list:
        return []
    if _has_decimal(values_list):
        precision, rounding = _decimal_context_params()
        if RUST_AVAILABLE and _rust_decimal_ema is not None:
            try:
                return _rust_decimal_ema(values_list, span, precision, rounding)
            except ValueError as e:
                # Fall back to Python for extreme values outside rust-decimal range
                logger.debug(f"Rust EMA failed ({e}), falling back to Python Decimal")
                return _python_decimal_ema(values_list, span)
        return _python_decimal_ema(values_list, span)

    if RUST_AVAILABLE and _rust_ema is not None:
        return _rust_ema(values_list, span)

    return _python_float_ema(values_list, span)


# Array Operations


def rust_array_sum(values: Sequence[Number]) -> Number:
    """
    Calculate sum of array values (optimized).

    Args:
        values: List of numeric values

    Returns:
        Sum of all values

    Example:
        >>> rust_array_sum([1.0, 2.0, 3.0, 4.0, 5.0])
        15.0
    """
    values_list = list(values)
    if _has_decimal(values_list):
        precision, rounding = _decimal_context_params()
        if RUST_AVAILABLE and _rust_decimal_sum is not None:
            try:
                # Normalize Decimals: convert floats to Decimal strings
                normalized = []
                for v in values_list:
                    if isinstance(v, Decimal):
                        normalized.append(v)
                    else:
                        normalized.append(Decimal(str(v)))
                return _rust_decimal_sum(normalized, precision, rounding)
            except ValueError as e:
                # Fall back to Python for extreme values outside rust-decimal range
                logger.debug(f"Rust sum failed ({e}), falling back to Python Decimal")
                # Normalize all values to Decimal for fallback
                decimal_values = [
                    v if isinstance(v, Decimal) else Decimal(str(v)) for v in values_list
                ]
                return sum(decimal_values, Decimal(0))
        # Normalize all values to Decimal for fallback
        decimal_values = [v if isinstance(v, Decimal) else Decimal(str(v)) for v in values_list]
        return sum(decimal_values, Decimal(0))

    if RUST_AVAILABLE and _rust_array_sum is not None:
        return _rust_array_sum(values_list)

    return float(sum(values_list))


def rust_mean(values: Sequence[Number]) -> Number:
    """
    Calculate array mean (optimized).

    Args:
        values: List of numeric values

    Returns:
        Mean of all values, or NaN if array is empty

    Example:
        >>> rust_mean([1.0, 2.0, 3.0, 4.0, 5.0])
        3.0
    """
    values_list = list(values)
    if not values_list:
        return math.nan

    if _has_decimal(values_list):
        precision, rounding = _decimal_context_params()
        if RUST_AVAILABLE and _rust_decimal_mean is not None:
            try:
                return _rust_decimal_mean(values_list, precision, rounding)
            except ValueError as e:
                # Fall back to Python for extreme values outside rust-decimal range
                logger.debug(f"Rust mean failed ({e}), falling back to Python Decimal")
                ctx = getcontext()
                # Normalize all values to Decimal for fallback
                decimal_values = [
                    v if isinstance(v, Decimal) else Decimal(str(v)) for v in values_list
                ]
                total = sum(decimal_values, Decimal(0))
                return ctx.divide(total, Decimal(len(values_list)))
        ctx = getcontext()
        # Normalize all values to Decimal for fallback
        decimal_values = [v if isinstance(v, Decimal) else Decimal(str(v)) for v in values_list]
        total = sum(decimal_values, Decimal(0))
        return ctx.divide(total, Decimal(len(values_list)))

    if RUST_AVAILABLE and _rust_mean is not None:
        return _rust_mean(values_list)

    return float(sum(values_list) / len(values_list))


def rust_rolling_sum(values: Sequence[Number], window: int) -> list[Number]:
    """
    Calculate rolling window sum.

    Args:
        values: List of numeric values
        window: Window size

    Returns:
        List of rolling sums (first window-1 elements are NaN)

    Example:
        >>> rust_rolling_sum([1.0, 2.0, 3.0, 4.0, 5.0], 3)
        [nan, nan, 6.0, 9.0, 12.0]
    """
    values_list = list(values)
    if window <= 0:
        raise ValueError("Window size must be greater than 0")
    if not values_list:
        return []
    if _has_decimal(values_list):
        precision, rounding = _decimal_context_params()
        if RUST_AVAILABLE and _rust_decimal_rolling_sum is not None:
            try:
                return _rust_decimal_rolling_sum(values_list, window, precision, rounding)
            except ValueError as e:
                # Fall back to Python for extreme values outside rust-decimal range
                logger.debug(f"Rust rolling_sum failed ({e}), falling back to Python Decimal")
                return _python_decimal_rolling_sum(values_list, window)
        return _python_decimal_rolling_sum(values_list, window)

    if RUST_AVAILABLE and _rust_rolling_sum is not None:
        return _rust_rolling_sum(values_list, window)

    return _python_float_rolling_sum(values_list, window)


# Data Operations (Rust-only, no fallback needed for now)


def rust_window_slice(data: Sequence[Number], start: int, end: int) -> list[Number]:
    """
    Extract a window slice from data.

    Args:
        data: Input data array
        start: Start index
        end: End index (exclusive)

    Returns:
        Sliced data
    """
    data_list = list(data)
    if _has_decimal(data_list):
        if RUST_AVAILABLE and _rust_decimal_window_slice is not None:
            try:
                return _rust_decimal_window_slice(data_list, start, end)
            except (ValueError, IndexError) as e:
                # Re-raise IndexError, fall back on ValueError (extreme values)
                if isinstance(e, IndexError):
                    raise
                logger.debug(f"Rust window_slice failed ({e}), falling back to Python Decimal")
                _validate_window_bounds(data_list, start, end)
                return data_list[start:end]
        _validate_window_bounds(data_list, start, end)
        return data_list[start:end]

    if RUST_AVAILABLE and _rust_window_slice is not None:
        return _rust_window_slice(data_list, start, end)

    _validate_window_bounds(data_list, start, end)
    return data_list[start:end]


def rust_create_columns(data: list[list[float]]):
    """
    Create column-major data structure from column vectors.

    Args:
        data: List of column vectors

    Returns:
        Tuple of (flattened_data, n_rows, n_cols) - flattened in column-major order

    Example:
        >>> rust_create_columns([[1.0, 2.0], [3.0, 4.0]])
        ([1.0, 2.0, 3.0, 4.0], 2, 2)
    """
    if RUST_AVAILABLE and _rust_create_columns is not None:
        return _rust_create_columns(data)

    # Pure Python fallback - match Rust signature
    if not data:
        return ([], 0, 0)

    n_cols = len(data)
    n_rows = len(data[0])

    # Validate all columns have same length
    for i, col in enumerate(data):
        if len(col) != n_rows:
            raise ValueError(f"Column {i} has length {len(col)}, expected {n_rows}")

    # Flatten in column-major order (same as Rust)
    flattened = []
    for col in data:
        flattened.extend(col)

    return (flattened, n_rows, n_cols)


def rust_index_select(data: Sequence[Number], indices: Sequence[int]) -> list[Number]:
    """
    Select elements by indices.

    Args:
        data: Input data array
        indices: List of indices to select

    Returns:
        Selected elements
    """
    data_list = list(data)
    index_list = list(indices)

    if _has_decimal(data_list):
        if RUST_AVAILABLE and _rust_decimal_index_select is not None:
            try:
                return _rust_decimal_index_select(data_list, index_list)
            except (ValueError, IndexError) as e:
                # Re-raise IndexError, fall back on ValueError (extreme values)
                if isinstance(e, IndexError):
                    raise
                logger.debug(f"Rust index_select failed ({e}), falling back to Python Decimal")
    elif RUST_AVAILABLE and _rust_index_select is not None:
        return _rust_index_select(data_list, index_list)

    length = len(data_list)
    result: list[Number] = []
    for idx in index_list:
        if idx >= length:
            raise IndexError(f"Index {idx} out of bounds for array of length {length}")
        result.append(data_list[idx])
    return result


def rust_fillna(data: Sequence[Number], fill_value: Number) -> list[Number]:
    """
    Fill NaN values with a specified value.

    Args:
        data: Input data array
        fill_value: Value to replace NaN with

    Returns:
        Data with NaN values filled
    """
    data_list = list(data)

    if _has_decimal(data_list) or isinstance(fill_value, Decimal):
        if RUST_AVAILABLE and _rust_decimal_fillna is not None:
            try:
                return _rust_decimal_fillna(data_list, fill_value)
            except ValueError as e:
                # Fall back to Python for extreme values outside rust-decimal range
                logger.debug(f"Rust fillna failed ({e}), falling back to Python Decimal")
                result: list[Number] = []
                for value in data_list:
                    if isinstance(value, Decimal) and value.is_nan():
                        result.append(fill_value)
                    else:
                        result.append(value)
                return result
        result: list[Number] = []
        for value in data_list:
            if isinstance(value, Decimal) and value.is_nan():
                result.append(fill_value)
            else:
                result.append(value)
        return result

    if RUST_AVAILABLE and _rust_fillna is not None:
        return _rust_fillna(data_list, float(fill_value))

    return [fill_value if math.isnan(x) else x for x in data_list]


def rust_pairwise_op(a: Sequence[Number], b: Sequence[Number], op: str) -> list[Number]:
    """
    Perform pairwise operation on two arrays.

    Args:
        a: First array
        b: Second array
        op: Operation: 'add', 'sub', 'mul', 'div' (Rust names)
            or 'subtract', 'multiply', 'divide' (Python aliases)

    Returns:
        Result of pairwise operation
    """
    a_list = list(a)
    b_list = list(b)
    if len(a_list) != len(b_list):
        raise ValueError(f"Array lengths don't match: {len(a_list)} vs {len(b_list)}")

    if _has_decimal(a_list) or _has_decimal(b_list):
        precision, rounding = _decimal_context_params()
        if RUST_AVAILABLE and _rust_decimal_pairwise_op is not None:
            try:
                return _rust_decimal_pairwise_op(a_list, b_list, op, precision, rounding)
            except ValueError as e:
                # Fall back to Python for extreme values outside rust-decimal range
                logger.debug(f"Rust pairwise_op failed ({e}), falling back to Python Decimal")

        result: list[Number] = []
        for lhs, rhs in zip(a_list, b_list, strict=False):
            lhs_dec = lhs if isinstance(lhs, Decimal) else Decimal(str(lhs))
            rhs_dec = rhs if isinstance(rhs, Decimal) else Decimal(str(rhs))
            if op in ("add", "+"):
                result.append(lhs_dec + rhs_dec)
            elif op in ("sub", "-", "subtract"):
                result.append(lhs_dec - rhs_dec)
            elif op in ("mul", "*", "multiply"):
                result.append(lhs_dec * rhs_dec)
            elif op in ("div", "/", "divide"):
                if rhs_dec == 0:
                    raise ZeroDivisionError("Division by zero")
                result.append(lhs_dec / rhs_dec)
            else:
                raise ValueError(f"Unknown operation: {op}")
        return result

    if RUST_AVAILABLE and _rust_pairwise_op is not None:
        op_map = {"subtract": "sub", "multiply": "mul", "divide": "div"}
        rust_op = op_map.get(op, op)
        return _rust_pairwise_op(a_list, b_list, rust_op)

    if op in ("add", "+"):
        return [x + y for x, y in zip(a_list, b_list, strict=False)]
    if op in ("sub", "-", "subtract"):
        return [x - y for x, y in zip(a_list, b_list, strict=False)]
    if op in ("mul", "*", "multiply"):
        return [x * y for x, y in zip(a_list, b_list, strict=False)]
    if op in ("div", "/", "divide"):
        result: list[Number] = []
        for lhs, rhs in zip(a_list, b_list, strict=False):
            if rhs == 0:
                raise ZeroDivisionError("Division by zero")
            result.append(lhs / rhs)
        return result

    raise ValueError(f"Unknown operation: {op}")


__all__ = [
    "RUST_AVAILABLE",
    "rust_array_sum",
    "rust_create_columns",
    "rust_ema",
    "rust_fillna",
    "rust_index_select",
    "rust_mean",
    "rust_pairwise_op",
    "rust_rolling_sum",
    "rust_sma",
    "rust_window_slice",
]
