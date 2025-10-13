"""
Tests for rustybt.lib._factorize Cython module.

This module tests the low-level Cython factorization operations including:
- String factorization with unknown categories
- String factorization with known categories
- Optimal dtype selection for codes
- Sorting behavior
"""
import numpy as np
import pytest
from hypothesis import given, strategies as st, assume
from numpy.testing import assert_array_equal

from rustybt.lib._factorize import (
    factorize_strings,
    factorize_strings_known_categories,
    smallest_uint_that_can_hold,
)


class TestSmallestUintThatCanHold:
    """Tests for smallest_uint_that_can_hold function."""

    def test_zero_value(self):
        """Test that values <= 0 return uint8."""
        assert smallest_uint_that_can_hold(0) == np.uint8
        assert smallest_uint_that_can_hold(-10) == np.uint8

    def test_uint8_range(self):
        """Test values that fit in uint8 (1-256)."""
        assert smallest_uint_that_can_hold(1) == np.uint8
        assert smallest_uint_that_can_hold(255) == np.uint8
        assert smallest_uint_that_can_hold(256) == np.uint8  # Boundary

    def test_uint16_range(self):
        """Test values that require uint16 (257-65536)."""
        assert smallest_uint_that_can_hold(257) == np.uint16
        assert smallest_uint_that_can_hold(65535) == np.uint16
        assert smallest_uint_that_can_hold(65536) == np.uint16  # Boundary

    def test_uint32_range(self):
        """Test values that require uint32 (65537-4294967296)."""
        assert smallest_uint_that_can_hold(65537) == np.uint32
        assert smallest_uint_that_can_hold(2**20) == np.uint32
        assert smallest_uint_that_can_hold(2**32) == np.uint32  # Boundary

    def test_uint64_range(self):
        """Test values that require uint64 (> 4294967296)."""
        assert smallest_uint_that_can_hold(2**32 + 1) == np.uint64
        assert smallest_uint_that_can_hold(2**48) == np.uint64


class TestFactorizeStrings:
    """Tests for factorize_strings function."""

    def test_factorize_empty_array(self):
        """Test factorizing an empty array."""
        values = np.array([], dtype=object)
        codes, categories, reverse_map = factorize_strings(
            values,
            missing_value=None,
            sort=False,
        )

        assert len(codes) == 0
        assert len(categories) == 1  # Only missing value
        assert categories[0] is None

    def test_factorize_single_value(self):
        """Test factorizing a single unique value."""
        values = np.array(['a', 'a', 'a'], dtype=object)
        codes, categories, reverse_map = factorize_strings(
            values,
            missing_value=None,
            sort=False,
        )

        assert_array_equal(codes, [1, 1, 1])
        assert categories[0] is None
        assert categories[1] == 'a'
        assert reverse_map[None] == 0
        assert reverse_map['a'] == 1

    def test_factorize_multiple_values(self):
        """Test factorizing multiple unique values."""
        values = np.array(['apple', 'banana', 'apple', 'cherry', 'banana'], dtype=object)
        codes, categories, reverse_map = factorize_strings(
            values,
            missing_value=None,
            sort=False,
        )

        # Check that codes are consistent
        assert codes[0] == codes[2]  # Both 'apple'
        assert codes[1] == codes[4]  # Both 'banana'
        # Only 3 unique codes in the output (apple, banana, cherry)
        # Code 0 (None) exists but isn't used
        assert len(set(codes)) == 3

        # Check categories (4 total: None + 3 actual values)
        assert len(categories) == 4
        assert None in categories
        assert 'apple' in categories
        assert 'banana' in categories
        assert 'cherry' in categories

    def test_factorize_with_missing_value(self):
        """Test that missing value is always code 0."""
        values = np.array(['a', 'b', 'c'], dtype=object)
        codes, categories, reverse_map = factorize_strings(
            values,
            missing_value='missing',
            sort=False,
        )

        assert categories[0] == 'missing'
        assert reverse_map['missing'] == 0

    def test_factorize_sorted(self):
        """Test factorizing with sorting enabled."""
        values = np.array(['zebra', 'apple', 'banana'], dtype=object)
        codes, categories, reverse_map = factorize_strings(
            values,
            missing_value=None,
            sort=True,
        )

        # Missing value should always be first
        assert categories[0] is None

        # Remaining categories should be sorted
        sorted_cats = sorted(categories[1:])
        assert list(categories[1:]) == sorted_cats

        # Check that codes point to correct categories
        for i, val in enumerate(values):
            assert categories[codes[i]] == val

    def test_factorize_unsorted(self):
        """Test factorizing without sorting (insertion order)."""
        values = np.array(['zebra', 'apple', 'banana', 'zebra'], dtype=object)
        codes, categories, reverse_map = factorize_strings(
            values,
            missing_value=None,
            sort=False,
        )

        # Missing value first, then insertion order
        assert categories[0] is None
        assert categories[1] == 'zebra'  # First unique value
        assert categories[2] == 'apple'  # Second unique value
        assert categories[3] == 'banana'  # Third unique value

    def test_factorize_dtype_optimization_uint8(self):
        """Test that small arrays use uint8."""
        values = np.array(['a', 'b', 'c'], dtype=object)
        codes, categories, reverse_map = factorize_strings(
            values,
            missing_value=None,
            sort=False,
        )

        assert codes.dtype == np.uint8

    def test_factorize_dtype_optimization_uint16(self):
        """Test that larger arrays use appropriate dtype."""
        # Create array with 300 unique values
        values = np.array([f'cat_{i}' for i in range(300)], dtype=object)
        codes, categories, reverse_map = factorize_strings(
            values,
            missing_value=None,
            sort=False,
        )

        # Should use uint16 since we have > 255 categories
        assert codes.dtype == np.uint16

    def test_factorize_preserves_byte_strings(self):
        """Test that byte strings are handled correctly."""
        values = np.array([b'apple', b'banana', b'apple'], dtype=object)
        codes, categories, reverse_map = factorize_strings(
            values,
            missing_value=None,
            sort=False,
        )

        assert codes[0] == codes[2]
        assert b'apple' in categories
        assert b'banana' in categories

    def test_factorize_with_none_values(self):
        """Test factorizing when None appears in the values."""
        values = np.array(['a', None, 'b', None, 'a'], dtype=object)
        codes, categories, reverse_map = factorize_strings(
            values,
            missing_value=None,
            sort=False,
        )

        # All None values should have the same code (0)
        assert codes[1] == codes[3] == 0
        # 'a' values should have the same code
        assert codes[0] == codes[4]

    @given(
        st.lists(
            st.text(min_size=1, max_size=10),
            min_size=1,
            max_size=100,
        )
    )
    def test_factorize_property_roundtrip(self, string_list):
        """Property test: factorizing should be reversible."""
        values = np.array(string_list, dtype=object)
        codes, categories, reverse_map = factorize_strings(
            values,
            missing_value='__missing__',
            sort=False,
        )

        # Reconstruct original values from codes and categories
        reconstructed = categories[codes]

        assert_array_equal(values, reconstructed)

    @given(
        st.lists(
            st.text(min_size=1, max_size=10),
            min_size=1,
            max_size=100,
        )
    )
    def test_factorize_property_unique_codes(self, string_list):
        """Property test: unique values should have unique codes."""
        values = np.array(string_list, dtype=object)
        codes, categories, reverse_map = factorize_strings(
            values,
            missing_value='__missing__',
            sort=False,
        )

        unique_values = set(string_list)
        # +1 for missing value
        assert len(categories) == len(unique_values) + 1

    @given(
        st.lists(
            st.text(min_size=1, max_size=10),
            min_size=1,
            max_size=100,
        )
    )
    def test_factorize_property_sorted_order(self, string_list):
        """Property test: sorted factorization maintains sort order."""
        values = np.array(string_list, dtype=object)
        codes, categories, reverse_map = factorize_strings(
            values,
            missing_value=None,
            sort=True,
        )

        # Categories (excluding None) should be sorted
        non_none_cats = [c for c in categories if c is not None]
        assert non_none_cats == sorted(non_none_cats)


class TestFactorizeStringsKnownCategories:
    """Tests for factorize_strings_known_categories function."""

    def test_factorize_known_all_present(self):
        """Test when all values match known categories."""
        values = np.array(['a', 'b', 'c', 'a'], dtype=object)
        categories = ['a', 'b', 'c']

        codes, result_cats, reverse_map = factorize_strings_known_categories(
            values,
            categories,
            missing_value='missing',
            sort=False,
        )

        # Missing value should be code 0
        assert result_cats[0] == 'missing'

        # All values should be found
        for i, val in enumerate(values):
            assert result_cats[codes[i]] == val

    def test_factorize_known_with_missing(self):
        """Test when some values are not in known categories."""
        values = np.array(['a', 'b', 'unknown', 'd'], dtype=object)
        categories = ['a', 'b', 'c', 'd']

        codes, result_cats, reverse_map = factorize_strings_known_categories(
            values,
            categories,
            missing_value='missing',
            sort=False,
        )

        # 'unknown' should map to missing value code
        missing_code = reverse_map['missing']
        assert codes[2] == missing_code

        # Known values should map correctly
        assert result_cats[codes[0]] == 'a'
        assert result_cats[codes[1]] == 'b'
        assert result_cats[codes[3]] == 'd'

    def test_factorize_known_sorted(self):
        """Test known categories with sorting."""
        values = np.array(['c', 'a', 'b'], dtype=object)
        categories = ['c', 'a', 'b']

        codes, result_cats, reverse_map = factorize_strings_known_categories(
            values,
            categories,
            missing_value=None,
            sort=True,
        )

        # Categories should be sorted (None first, then alphabetical)
        assert result_cats[0] is None
        non_none_cats = [c for c in result_cats if c is not None]
        assert non_none_cats == sorted(non_none_cats)

        # Values should still map correctly
        for i, val in enumerate(values):
            assert result_cats[codes[i]] == val

    def test_factorize_known_missing_in_categories(self):
        """Test when missing_value is already in categories."""
        values = np.array(['a', 'b', 'a'], dtype=object)
        categories = ['missing', 'a', 'b']  # missing already present

        codes, result_cats, reverse_map = factorize_strings_known_categories(
            values,
            categories,
            missing_value='missing',
            sort=False,
        )

        # Missing should still be code 0
        assert result_cats[0] == 'missing'

    def test_factorize_known_dtype_selection(self):
        """Test that appropriate dtype is selected based on category count."""
        values = np.array(['a', 'b', 'c'], dtype=object)

        # Small number of categories -> uint8
        categories_small = ['a', 'b', 'c']
        codes_small, _, _ = factorize_strings_known_categories(
            values,
            categories_small,
            missing_value=None,
            sort=False,
        )
        assert codes_small.dtype == np.uint8

        # Large number of categories -> uint16
        categories_large = [f'cat_{i}' for i in range(300)]
        values_large = np.array(['cat_0', 'cat_1', 'cat_2'], dtype=object)
        codes_large, _, _ = factorize_strings_known_categories(
            values_large,
            categories_large,
            missing_value=None,
            sort=False,
        )
        assert codes_large.dtype == np.uint16

    def test_factorize_known_empty_array(self):
        """Test with empty input array."""
        values = np.array([], dtype=object)
        categories = ['a', 'b', 'c']

        codes, result_cats, reverse_map = factorize_strings_known_categories(
            values,
            categories,
            missing_value=None,
            sort=False,
        )

        assert len(codes) == 0
        assert None in result_cats

    def test_factorize_known_all_missing(self):
        """Test when all values are missing (not in categories)."""
        values = np.array(['x', 'y', 'z'], dtype=object)
        categories = ['a', 'b', 'c']

        codes, result_cats, reverse_map = factorize_strings_known_categories(
            values,
            categories,
            missing_value='missing',
            sort=False,
        )

        # All should map to missing code
        missing_code = reverse_map['missing']
        assert all(code == missing_code for code in codes)

    @given(
        known_cats=st.lists(
            st.text(min_size=1, max_size=10),
            min_size=1,
            max_size=50,
            unique=True,
        ),
        n_values=st.integers(min_value=1, max_value=100),
    )
    def test_factorize_known_property_valid_codes(self, known_cats, n_values):
        """Property test: all codes should be valid indices."""
        # Create values that are all from known categories
        values = np.array(
            [known_cats[i % len(known_cats)] for i in range(n_values)],
            dtype=object
        )

        codes, result_cats, reverse_map = factorize_strings_known_categories(
            values,
            known_cats.copy(),
            missing_value='__missing__',
            sort=False,
        )

        # All codes should be valid indices
        assert all(0 <= code < len(result_cats) for code in codes)

        # Codes should reconstruct original values
        reconstructed = result_cats[codes]
        assert_array_equal(values, reconstructed)


class TestFactorizeComparison:
    """Tests comparing factorize_strings with pandas.factorize behavior."""

    def test_consistency_with_pandas(self):
        """Test that our factorize is consistent with pandas for basic cases."""
        import pandas as pd

        values = np.array(['a', 'b', 'a', 'c', 'b'], dtype=object)

        # Our implementation
        our_codes, our_cats, _ = factorize_strings(
            values,
            missing_value=None,
            sort=False,
        )

        # Pandas implementation
        pd_codes, pd_cats = pd.factorize(values, sort=False)

        # Reconstruct values - should be identical
        our_reconstructed = our_cats[our_codes]
        pd_reconstructed = pd_cats[pd_codes]

        assert_array_equal(our_reconstructed, pd_reconstructed)
        assert_array_equal(our_reconstructed, values)


class TestFactorizeEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_unicode_strings(self):
        """Test with unicode strings."""
        values = np.array(['café', '北京', 'مرحبا', 'café'], dtype=object)
        codes, categories, reverse_map = factorize_strings(
            values,
            missing_value=None,
            sort=False,
        )

        assert codes[0] == codes[3]  # Both 'café'
        assert 'café' in categories
        assert '北京' in categories
        assert 'مرحبا' in categories

    def test_very_long_strings(self):
        """Test with very long strings."""
        long_string = 'a' * 10000
        values = np.array([long_string, 'b', long_string], dtype=object)

        codes, categories, reverse_map = factorize_strings(
            values,
            missing_value=None,
            sort=False,
        )

        assert codes[0] == codes[2]
        assert long_string in categories

    def test_empty_strings(self):
        """Test with empty strings."""
        values = np.array(['', 'a', '', 'b'], dtype=object)

        codes, categories, reverse_map = factorize_strings(
            values,
            missing_value=None,
            sort=False,
        )

        assert codes[0] == codes[2]  # Both empty strings
        assert '' in categories

    def test_whitespace_strings(self):
        """Test that whitespace is preserved."""
        values = np.array(['a', ' a', 'a ', ' a '], dtype=object)

        codes, categories, reverse_map = factorize_strings(
            values,
            missing_value=None,
            sort=False,
        )

        # All should be different
        # 4 unique codes in output (None code 0 exists but isn't used)
        assert len(set(codes)) == 4
        # 5 categories total: None + 4 whitespace variations
        assert len(categories) == 5

    def test_single_category_repeated(self):
        """Test with a single category repeated many times."""
        values = np.array(['x'] * 1000, dtype=object)

        codes, categories, reverse_map = factorize_strings(
            values,
            missing_value=None,
            sort=False,
        )

        # All codes should be the same
        assert len(set(codes)) == 1
        assert len(categories) == 2  # None + 'x'

    def test_uint_boundary_255(self):
        """Test behavior at uint8 boundary (255 unique values)."""
        # Create exactly 255 unique values (including missing)
        values = np.array([f'cat_{i}' for i in range(254)], dtype=object)

        codes, categories, reverse_map = factorize_strings(
            values,
            missing_value=None,
            sort=False,
        )

        # Should still use uint8
        assert codes.dtype == np.uint8
        assert len(categories) == 255  # None + 254 values

    def test_uint_boundary_256(self):
        """Test behavior just above uint8 boundary."""
        # Create 256 unique values (need 257 categories to exceed uint8)
        values = np.array([f'cat_{i}' for i in range(256)], dtype=object)

        codes, categories, reverse_map = factorize_strings(
            values,
            missing_value=None,
            sort=False,
        )

        # Should upgrade to uint16 (257 categories total: None + 256 values)
        assert codes.dtype == np.uint16
        assert len(categories) == 257  # None + 256 values


class TestFactorizePerformance:
    """Tests to verify performance characteristics (not strict benchmarks)."""

    def test_large_array_factorization(self):
        """Test that large arrays can be factorized."""
        # Create large array with moderate number of unique values
        n_values = 100000
        n_unique = 100
        values = np.array(
            [f'cat_{i % n_unique}' for i in range(n_values)],
            dtype=object
        )

        # Should complete without error
        codes, categories, reverse_map = factorize_strings(
            values,
            missing_value=None,
            sort=False,
        )

        assert len(codes) == n_values
        assert len(categories) == n_unique + 1  # +1 for missing

    def test_many_unique_values(self):
        """Test with many unique values."""
        n_unique = 10000
        values = np.array([f'cat_{i}' for i in range(n_unique)], dtype=object)

        # Should complete without error
        codes, categories, reverse_map = factorize_strings(
            values,
            missing_value=None,
            sort=False,
        )

        assert len(categories) == n_unique + 1  # +1 for missing
