"""
Baseline equivalence test utilities for functional consistency validation.

This module provides tools to validate that optimized implementations produce
identical results to baseline implementations. This is a BLOCKING requirement
per the feature specification - functional consistency must be verified before
performance evaluation.

Constitutional requirements:
- CR-002: Zero-Mock Enforcement - All comparisons use real data
- CR-004: Type Safety - Complete type hints
- CR-005: Test-Driven Development - Property-based tests with Hypothesis
"""

from collections.abc import Callable
from decimal import Decimal
from typing import Any

import numpy as np

from .exceptions import FunctionalEquivalenceError


def validate_functional_equivalence(
    baseline_fn: Callable[..., Any],
    optimized_fn: Callable[..., Any],
    test_cases: list[tuple[tuple, dict]],
    tolerance: Decimal | None = None,
    comparison_mode: str = "exact",
) -> bool:
    """
    Validate functional equivalence between baseline and optimized implementations.

    This is a BLOCKING test - optimizations must pass this before performance
    evaluation per FR-004 functional consistency requirement.

    Args:
        baseline_fn: Baseline (pure Python) implementation
        optimized_fn: Optimized implementation to test
        test_cases: List of (args, kwargs) tuples for testing
        tolerance: Numerical tolerance for floating point comparisons (None for exact)
        comparison_mode: "exact" (default), "decimal", "float", or "array"

    Returns:
        True if all test cases pass

    Raises:
        FunctionalEquivalenceError: If any test case produces different results

    Examples:
        >>> import numpy as np
        >>> # Define baseline moving average function
        >>> baseline_fn = lambda data, window: np.convolve(
        ...     data, np.ones(window)/window, mode='valid'
        ... )
        >>> # Define optimized moving average function
        >>> optimized_fn = lambda data, window: np.convolve(
        ...     data, np.ones(window)/window, mode='valid'
        ... )
        >>> test_cases = [
        ...     (([1.0, 2.0, 3.0, 4.0, 5.0], 3), {}),
        ...     (([10.0, 20.0, 30.0], 2), {}),
        ... ]
        >>> # Test: validate_functional_equivalence(
        >>> #     baseline_fn, optimized_fn, test_cases, comparison_mode="array"
        >>> # )
    """
    for i, (args, kwargs) in enumerate(test_cases):
        try:
            baseline_result = baseline_fn(*args, **kwargs)
            optimized_result = optimized_fn(*args, **kwargs)

            if not _results_equal(baseline_result, optimized_result, tolerance, comparison_mode):
                raise FunctionalEquivalenceError(
                    f"Test case {i} failed: Results differ\n"
                    f"Args: {args}\n"
                    f"Kwargs: {kwargs}\n"
                    f"Baseline: {baseline_result}\n"
                    f"Optimized: {optimized_result}"
                )

        except FunctionalEquivalenceError:
            raise
        except Exception as e:
            raise FunctionalEquivalenceError(
                f"Test case {i} raised exception: {e}\nArgs: {args}\nKwargs: {kwargs}"
            ) from e

    return True


def _results_equal(  # type: ignore[misc]
    baseline: Any,  # noqa: ANN401
    optimized: Any,  # noqa: ANN401
    tolerance: Decimal | None,
    mode: str,
) -> bool:
    """
    Compare results based on comparison mode.

    Args:
        baseline: Baseline result
        optimized: Optimized result
        tolerance: Numerical tolerance
        mode: Comparison mode

    Returns:
        True if results are equivalent
    """
    if mode == "exact":
        return baseline == optimized

    elif mode == "decimal":
        return _compare_decimals(baseline, optimized, tolerance)

    elif mode == "float":
        return _compare_floats(baseline, optimized, tolerance)

    elif mode == "array":
        return _compare_arrays(baseline, optimized, tolerance)

    else:
        raise ValueError(f"Unknown comparison mode: {mode}")


def _compare_decimals(
    baseline: Decimal | list[Decimal],
    optimized: Decimal | list[Decimal],
    tolerance: Decimal | None,
) -> bool:
    """
    Compare Decimal values or lists.

    Args:
        baseline: Baseline Decimal value(s)
        optimized: Optimized Decimal value(s)
        tolerance: Absolute tolerance (None for exact)

    Returns:
        True if values are within tolerance
    """
    if isinstance(baseline, list) and isinstance(optimized, list):
        if len(baseline) != len(optimized):
            return False

        for b, o in zip(baseline, optimized, strict=False):
            if not _compare_decimals(b, o, tolerance):
                return False
        return True

    # Single Decimal comparison
    if tolerance is None:
        # Exact comparison
        return baseline == optimized
    else:
        # Tolerance comparison
        if baseline.is_nan() and optimized.is_nan():
            return True
        if baseline.is_nan() or optimized.is_nan():
            return False

        diff = abs(baseline - optimized)
        return diff <= tolerance


def _compare_floats(
    baseline: float | list[float],
    optimized: float | list[float],
    tolerance: Decimal | None,
) -> bool:
    """
    Compare float values or lists.

    Args:
        baseline: Baseline float value(s)
        optimized: Optimized float value(s)
        tolerance: Absolute tolerance (None for default 1e-10)

    Returns:
        True if values are within tolerance
    """
    tol = float(tolerance) if tolerance is not None else 1e-10

    if isinstance(baseline, list) and isinstance(optimized, list):
        if len(baseline) != len(optimized):
            return False

        for b, o in zip(baseline, optimized, strict=False):
            if not _compare_floats(b, o, Decimal(str(tol)) if tolerance else None):
                return False
        return True

    # Single float comparison
    if np.isnan(baseline) and np.isnan(optimized):
        return True
    if np.isnan(baseline) or np.isnan(optimized):
        return False

    return abs(baseline - optimized) <= tol


def _compare_arrays(baseline: np.ndarray, optimized: np.ndarray, tolerance: Decimal | None) -> bool:
    """
    Compare NumPy arrays.

    Args:
        baseline: Baseline array
        optimized: Optimized array
        tolerance: Absolute tolerance (None for default 1e-10)

    Returns:
        True if arrays are equivalent within tolerance
    """
    baseline_arr = np.asarray(baseline)
    optimized_arr = np.asarray(optimized)

    if baseline_arr.shape != optimized_arr.shape:
        return False

    tol = float(tolerance) if tolerance is not None else 1e-10

    # Handle NaN values
    baseline_nan = np.isnan(baseline_arr)
    optimized_nan = np.isnan(optimized_arr)

    if not np.array_equal(baseline_nan, optimized_nan):
        return False

    # Compare non-NaN values
    non_nan_mask = ~baseline_nan
    return np.allclose(baseline_arr[non_nan_mask], optimized_arr[non_nan_mask], atol=tol, rtol=0)


def generate_test_cases_for_sma(
    num_cases: int = 10,
    min_length: int = 5,
    max_length: int = 100,
    min_window: int = 2,
    max_window: int = 20,
) -> list[tuple[tuple, dict]]:
    """
    Generate test cases for SMA functions.

    Args:
        num_cases: Number of test cases to generate
        min_length: Minimum array length
        max_length: Maximum array length
        min_window: Minimum window size
        max_window: Maximum window size

    Returns:
        List of (args, kwargs) tuples
    """
    import random

    np.random.seed(42)  # Reproducibility
    random.seed(42)

    test_cases = []

    for _ in range(num_cases):
        length = random.randint(min_length, max_length)  # noqa: S311
        window = random.randint(min_window, min(max_window, length))  # noqa: S311

        # Generate random price data
        values = np.random.uniform(10.0, 100.0, length).tolist()

        test_cases.append(((values, window), {}))

    return test_cases


def generate_test_cases_for_decimal_ops(
    num_cases: int = 10, min_length: int = 5, max_length: int = 50
) -> list[tuple[tuple, dict]]:
    """
    Generate test cases for Decimal operations.

    Args:
        num_cases: Number of test cases to generate
        min_length: Minimum array length
        max_length: Maximum array length

    Returns:
        List of (args, kwargs) tuples for Decimal operations
    """
    import random

    np.random.seed(42)
    random.seed(42)

    test_cases = []

    for _ in range(num_cases):
        length = random.randint(min_length, max_length)  # noqa: S311

        # Generate random Decimal values (financial data)
        values = [Decimal(str(round(np.random.uniform(10.0, 1000.0), 2))) for _ in range(length)]

        test_cases.append(((values,), {"scale": 8, "rounding": "ROUND_HALF_EVEN"}))

    return test_cases
