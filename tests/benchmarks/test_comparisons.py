"""
Tests for functional equivalence comparison utilities.

These tests verify the comparison logic used to validate that optimized
implementations produce identical results to baseline implementations.

Constitutional requirements:
- CR-002: Zero-Mock Enforcement - Use real data in tests
- CR-004: Type Safety - Complete type hints
- CR-005: Property-based tests where applicable
"""

from decimal import Decimal

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from rustybt.benchmarks.comparisons import (
    _compare_arrays,
    _compare_decimals,
    _compare_floats,
    _results_equal,
    generate_test_cases_for_decimal_ops,
    generate_test_cases_for_sma,
    validate_functional_equivalence,
)
from rustybt.benchmarks.exceptions import FunctionalEquivalenceError


class TestFunctionalEquivalence:
    """Test functional equivalence checking."""

    def test_identical_functions_pass(self):
        """Test that identical functions pass equivalence test."""
        baseline = lambda x: x * 2
        optimized = lambda x: x * 2

        test_cases = [((5,), {}), ((10,), {}), ((100,), {})]

        assert validate_functional_equivalence(baseline, optimized, test_cases)

    def test_different_functions_fail(self):
        """Test that different functions fail equivalence test."""
        baseline = lambda x: x * 2
        optimized = lambda x: x * 3

        test_cases = [((5,), {})]

        with pytest.raises(FunctionalEquivalenceError):
            validate_functional_equivalence(baseline, optimized, test_cases)

    def test_function_with_kwargs(self):
        """Test equivalence with keyword arguments."""
        baseline = lambda x, multiplier=2: x * multiplier
        optimized = lambda x, multiplier=2: x * multiplier

        test_cases = [((5,), {"multiplier": 3}), ((10,), {"multiplier": 5})]

        assert validate_functional_equivalence(baseline, optimized, test_cases)

    def test_exception_handling(self):
        """Test that exceptions are caught and wrapped."""
        baseline = lambda x: x / 0  # Always raises
        optimized = lambda x: x * 2

        test_cases = [((5,), {})]

        with pytest.raises(FunctionalEquivalenceError):
            validate_functional_equivalence(baseline, optimized, test_cases)

    def test_array_comparison_mode(self):
        """Test array comparison mode."""
        baseline = lambda arr: np.array(arr) * 2
        optimized = lambda arr: np.array(arr) * 2

        test_cases = [(([1, 2, 3],), {}), (([10, 20, 30],), {})]

        assert validate_functional_equivalence(
            baseline, optimized, test_cases, comparison_mode="array"
        )

    def test_float_comparison_mode(self):
        """Test float comparison mode with tolerance."""
        baseline = lambda x: x / 3.0
        optimized = lambda x: x / 3.0

        test_cases = [((10.0,), {})]

        assert validate_functional_equivalence(
            baseline, optimized, test_cases, tolerance=Decimal("0.0001"), comparison_mode="float"
        )

    def test_decimal_comparison_mode(self):
        """Test decimal comparison mode."""
        baseline = lambda x: Decimal(str(x)) * Decimal("2.5")
        optimized = lambda x: Decimal(str(x)) * Decimal("2.5")

        test_cases = [((10,), {}), ((25,), {})]

        assert validate_functional_equivalence(
            baseline, optimized, test_cases, comparison_mode="decimal"
        )


class TestResultsEqual:
    """Test _results_equal dispatcher."""

    def test_exact_mode(self):
        """Test exact comparison mode."""
        assert _results_equal(5, 5, None, "exact")
        assert not _results_equal(5, 6, None, "exact")
        assert _results_equal("hello", "hello", None, "exact")
        assert not _results_equal("hello", "world", None, "exact")

    def test_decimal_mode(self):
        """Test decimal mode."""
        assert _results_equal(Decimal("5.0"), Decimal("5.0"), None, "decimal")
        assert not _results_equal(Decimal("5.0"), Decimal("5.1"), None, "decimal")

    def test_float_mode(self):
        """Test float mode."""
        assert _results_equal(5.0, 5.0, None, "float")
        assert _results_equal(5.0, 5.00000001, Decimal("0.001"), "float")

    def test_array_mode(self):
        """Test array mode."""
        assert _results_equal(np.array([1, 2, 3]), np.array([1, 2, 3]), None, "array")

    def test_invalid_mode(self):
        """Test that invalid mode raises ValueError."""
        with pytest.raises(ValueError, match="Unknown comparison mode"):
            _results_equal(5, 5, None, "invalid_mode")


class TestCompareDecimals:
    """Test _compare_decimals function."""

    def test_exact_comparison(self):
        """Test exact Decimal comparison."""
        assert _compare_decimals(Decimal("5.0"), Decimal("5.0"), None)
        assert not _compare_decimals(Decimal("5.0"), Decimal("5.1"), None)

    def test_tolerance_comparison(self):
        """Test Decimal comparison with tolerance."""
        assert _compare_decimals(Decimal("5.0"), Decimal("5.001"), Decimal("0.01"))
        assert not _compare_decimals(Decimal("5.0"), Decimal("5.1"), Decimal("0.01"))

    def test_nan_handling(self):
        """Test NaN handling in Decimal comparison."""
        nan1 = Decimal("NaN")
        nan2 = Decimal("NaN")
        normal = Decimal("5.0")

        # Two NaNs should be equal
        assert _compare_decimals(nan1, nan2, Decimal("0.01"))

        # NaN vs normal should not be equal
        assert not _compare_decimals(nan1, normal, Decimal("0.01"))
        assert not _compare_decimals(normal, nan1, Decimal("0.01"))

    def test_list_comparison(self):
        """Test list of Decimals comparison."""
        list1 = [Decimal("1.0"), Decimal("2.0"), Decimal("3.0")]
        list2 = [Decimal("1.0"), Decimal("2.0"), Decimal("3.0")]
        list3 = [Decimal("1.0"), Decimal("2.0"), Decimal("3.1")]

        assert _compare_decimals(list1, list2, None)
        assert not _compare_decimals(list1, list3, None)

    def test_list_different_lengths(self):
        """Test that different length lists are not equal."""
        list1 = [Decimal("1.0"), Decimal("2.0")]
        list2 = [Decimal("1.0"), Decimal("2.0"), Decimal("3.0")]

        assert not _compare_decimals(list1, list2, None)


class TestCompareFloats:
    """Test _compare_floats function."""

    def test_exact_comparison(self):
        """Test exact float comparison."""
        assert _compare_floats(5.0, 5.0, None)
        # With default tolerance (1e-10), these should be different
        assert not _compare_floats(5.0, 5.1, None)

    def test_tolerance_comparison(self):
        """Test float comparison with custom tolerance."""
        assert _compare_floats(5.0, 5.001, Decimal("0.01"))
        assert not _compare_floats(5.0, 5.1, Decimal("0.01"))

    def test_nan_handling(self):
        """Test NaN handling in float comparison."""
        nan = float("nan")
        normal = 5.0

        # Two NaNs should be equal
        assert _compare_floats(nan, nan, None)

        # NaN vs normal should not be equal
        assert not _compare_floats(nan, normal, None)
        assert not _compare_floats(normal, nan, None)

    def test_list_comparison(self):
        """Test list of floats comparison."""
        list1 = [1.0, 2.0, 3.0]
        list2 = [1.0, 2.0, 3.0]
        list3 = [1.0, 2.0, 3.1]

        assert _compare_floats(list1, list2, None)
        assert not _compare_floats(list1, list3, Decimal("0.01"))

    def test_list_different_lengths(self):
        """Test that different length lists are not equal."""
        list1 = [1.0, 2.0]
        list2 = [1.0, 2.0, 3.0]

        assert not _compare_floats(list1, list2, None)


class TestCompareArrays:
    """Test _compare_arrays function."""

    def test_identical_arrays(self):
        """Test identical arrays are equal."""
        arr1 = np.array([1, 2, 3])
        arr2 = np.array([1, 2, 3])

        assert _compare_arrays(arr1, arr2, None)

    def test_different_arrays(self):
        """Test different arrays are not equal."""
        arr1 = np.array([1, 2, 3])
        arr2 = np.array([1, 2, 4])

        assert not _compare_arrays(arr1, arr2, None)

    def test_tolerance_comparison(self):
        """Test array comparison with tolerance."""
        arr1 = np.array([1.0, 2.0, 3.0])
        arr2 = np.array([1.001, 2.001, 3.001])

        assert _compare_arrays(arr1, arr2, Decimal("0.01"))
        assert not _compare_arrays(arr1, arr2, Decimal("0.0001"))

    def test_different_shapes(self):
        """Test arrays with different shapes are not equal."""
        arr1 = np.array([1, 2, 3])
        arr2 = np.array([[1, 2], [3, 4]])

        assert not _compare_arrays(arr1, arr2, None)

    def test_nan_handling(self):
        """Test NaN handling in array comparison."""
        arr1 = np.array([1.0, np.nan, 3.0])
        arr2 = np.array([1.0, np.nan, 3.0])
        arr3 = np.array([1.0, 2.0, 3.0])

        # Arrays with same NaN positions should be equal
        assert _compare_arrays(arr1, arr2, None)

        # Arrays with different NaN positions should not be equal
        assert not _compare_arrays(arr1, arr3, None)

    def test_multidimensional_arrays(self):
        """Test multidimensional array comparison."""
        arr1 = np.array([[1, 2], [3, 4]])
        arr2 = np.array([[1, 2], [3, 4]])
        arr3 = np.array([[1, 2], [3, 5]])

        assert _compare_arrays(arr1, arr2, None)
        assert not _compare_arrays(arr1, arr3, None)


class TestGenerateTestCasesForSMA:
    """Test SMA test case generator."""

    def test_generates_correct_number(self):
        """Test that correct number of test cases are generated."""
        test_cases = generate_test_cases_for_sma(num_cases=5)
        assert len(test_cases) == 5

    def test_test_case_structure(self):
        """Test that test cases have correct structure."""
        test_cases = generate_test_cases_for_sma(num_cases=1)
        assert len(test_cases) == 1

        (args, kwargs) = test_cases[0]
        assert len(args) == 2  # (values, window)
        assert isinstance(args[0], list)  # values
        assert isinstance(args[1], int)  # window
        assert isinstance(kwargs, dict)

    def test_respects_constraints(self):
        """Test that generated cases respect constraints."""
        test_cases = generate_test_cases_for_sma(
            num_cases=10, min_length=10, max_length=20, min_window=2, max_window=5
        )

        for (values, window), kwargs in test_cases:
            assert 10 <= len(values) <= 20
            assert 2 <= window <= 5
            assert window <= len(values)

    def test_reproducible_with_seed(self):
        """Test that generation is reproducible."""
        cases1 = generate_test_cases_for_sma(num_cases=5)
        cases2 = generate_test_cases_for_sma(num_cases=5)

        # Should be identical due to fixed seed
        for (args1, kwargs1), (args2, kwargs2) in zip(cases1, cases2):
            assert args1[0] == args2[0]  # values
            assert args1[1] == args2[1]  # window


class TestGenerateTestCasesForDecimalOps:
    """Test Decimal operations test case generator."""

    def test_generates_correct_number(self):
        """Test that correct number of test cases are generated."""
        test_cases = generate_test_cases_for_decimal_ops(num_cases=5)
        assert len(test_cases) == 5

    def test_test_case_structure(self):
        """Test that test cases have correct structure."""
        test_cases = generate_test_cases_for_decimal_ops(num_cases=1)
        assert len(test_cases) == 1

        (args, kwargs) = test_cases[0]
        assert len(args) == 1  # (values,)
        assert isinstance(args[0], list)
        assert all(isinstance(v, Decimal) for v in args[0])

        assert "scale" in kwargs
        assert "rounding" in kwargs

    def test_respects_length_constraints(self):
        """Test that generated cases respect length constraints."""
        test_cases = generate_test_cases_for_decimal_ops(num_cases=10, min_length=5, max_length=10)

        for (values,), kwargs in test_cases:
            assert 5 <= len(values) <= 10

    def test_generates_valid_decimals(self):
        """Test that generated Decimals are valid."""
        test_cases = generate_test_cases_for_decimal_ops(num_cases=10)

        for (values,), kwargs in test_cases:
            for v in values:
                assert isinstance(v, Decimal)
                assert not v.is_nan()
                assert not v.is_infinite()
                assert Decimal("10.0") <= v <= Decimal("1000.0")

    def test_reproducible_with_seed(self):
        """Test that generation is reproducible."""
        cases1 = generate_test_cases_for_decimal_ops(num_cases=5)
        cases2 = generate_test_cases_for_decimal_ops(num_cases=5)

        # Should be identical due to fixed seed
        for (args1, kwargs1), (args2, kwargs2) in zip(cases1, cases2):
            assert args1[0] == args2[0]  # values


class TestPropertyBasedComparisons:
    """Property-based tests for comparison functions."""

    @given(st.floats(allow_nan=False, allow_infinity=False))
    def test_float_comparison_reflexive(self, value):
        """Test that float comparison is reflexive."""
        assert _compare_floats(value, value, None)

    @given(st.lists(st.floats(allow_nan=False, allow_infinity=False), min_size=1, max_size=10))
    def test_float_list_comparison_reflexive(self, values):
        """Test that float list comparison is reflexive."""
        assert _compare_floats(values, values, None)

    @given(st.integers(min_value=-1000, max_value=1000).map(lambda x: Decimal(str(x))))
    def test_decimal_comparison_reflexive(self, value):
        """Test that Decimal comparison is reflexive."""
        assert _compare_decimals(value, value, None)

    @given(st.lists(st.integers(min_value=1, max_value=100), min_size=1, max_size=20))
    def test_array_comparison_reflexive(self, values):
        """Test that array comparison is reflexive."""
        arr = np.array(values)
        assert _compare_arrays(arr, arr, None)
