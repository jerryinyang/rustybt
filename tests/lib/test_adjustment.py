"""
Tests for rustybt.lib.adjustment Cython module.

This module tests the low-level Cython adjustment operations including:
- Float64 adjustments (multiply, add, overwrite)
- Int64/Datetime64 adjustments (overwrite)
- Boolean adjustments (overwrite)
- Object adjustments (overwrite)
- Array adjustments (1D array overwrites)
"""
import numpy as np
import pandas as pd
import pytest
from hypothesis import given, strategies as st
from numpy.testing import assert_array_equal, assert_allclose

from rustybt.lib.adjustment import (
    Float64Multiply,
    Float64Add,
    Float64Overwrite,
    Float641DArrayOverwrite,
    Datetime64Overwrite,
    Datetime641DArrayOverwrite,
    Int64Overwrite,
    ObjectOverwrite,
    Object1DArrayOverwrite,
    BooleanOverwrite,
    Boolean1DArrayOverwrite,
    make_adjustment_from_indices,
    make_adjustment_from_labels,
    get_adjustment_locs,
    choose_adjustment_type,
    MULTIPLY,
    ADD,
    OVERWRITE,
)


class TestFloat64Multiply:
    """Tests for Float64Multiply adjustment."""

    def test_multiply_single_cell(self):
        """Test multiplying a single cell."""
        arr = np.arange(9, dtype=float).reshape(3, 3)
        adj = Float64Multiply(
            first_row=1,
            last_row=1,
            first_col=1,
            last_col=1,
            value=2.0,
        )
        adj.mutate(arr)

        expected = np.array([
            [0., 1., 2.],
            [3., 8., 5.],  # Only (1,1) multiplied by 2
            [6., 7., 8.]
        ])
        assert_array_equal(arr, expected)

    def test_multiply_subarray(self):
        """Test multiplying a rectangular subarray."""
        arr = np.arange(9, dtype=float).reshape(3, 3)
        adj = Float64Multiply(
            first_row=1,
            last_row=2,
            first_col=1,
            last_col=2,
            value=4.0,
        )
        adj.mutate(arr)

        expected = np.array([
            [0., 1., 2.],
            [3., 16., 20.],
            [6., 28., 32.]
        ])
        assert_array_equal(arr, expected)

    def test_multiply_entire_column(self):
        """Test multiplying an entire column."""
        arr = np.arange(9, dtype=float).reshape(3, 3)
        adj = Float64Multiply(
            first_row=0,
            last_row=2,
            first_col=0,
            last_col=0,
            value=10.0,
        )
        adj.mutate(arr)

        expected = np.array([
            [0., 1., 2.],
            [30., 4., 5.],
            [60., 7., 8.]
        ])
        assert_array_equal(arr, expected)

    def test_multiply_by_fraction(self):
        """Test multiplying by a fraction."""
        arr = np.array([[10., 20., 30.]], dtype=float)
        adj = Float64Multiply(
            first_row=0,
            last_row=0,
            first_col=0,
            last_col=2,
            value=0.5,
        )
        adj.mutate(arr)

        expected = np.array([[5., 10., 15.]])
        assert_array_equal(arr, expected)

    @given(
        value=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)
    )
    def test_multiply_property_based(self, value):
        """Property test: multiplying then dividing should restore original."""
        from hypothesis import assume
        # Avoid values too close to zero that cause overflow when dividing
        assume(abs(value) > 1e-100)

        arr = np.arange(9, dtype=float).reshape(3, 3) + 1  # Avoid zeros
        original = arr.copy()

        adj_multiply = Float64Multiply(0, 2, 0, 2, value)
        adj_multiply.mutate(arr)

        adj_divide = Float64Multiply(0, 2, 0, 2, 1.0 / value)
        adj_divide.mutate(arr)
        assert_allclose(arr, original, rtol=1e-9)


class TestFloat64Add:
    """Tests for Float64Add adjustment."""

    def test_add_single_cell(self):
        """Test adding to a single cell."""
        arr = np.arange(9, dtype=float).reshape(3, 3)
        adj = Float64Add(
            first_row=1,
            last_row=1,
            first_col=1,
            last_col=1,
            value=10.0,
        )
        adj.mutate(arr)

        expected = np.array([
            [0., 1., 2.],
            [3., 14., 5.],
            [6., 7., 8.]
        ])
        assert_array_equal(arr, expected)

    def test_add_subarray(self):
        """Test adding to a rectangular subarray."""
        arr = np.arange(9, dtype=float).reshape(3, 3)
        adj = Float64Add(
            first_row=1,
            last_row=2,
            first_col=1,
            last_col=2,
            value=1.0,
        )
        adj.mutate(arr)

        expected = np.array([
            [0., 1., 2.],
            [3., 5., 6.],
            [6., 8., 9.]
        ])
        assert_array_equal(arr, expected)

    def test_add_negative_value(self):
        """Test adding a negative value (subtraction)."""
        arr = np.ones((3, 3), dtype=float) * 10
        adj = Float64Add(
            first_row=0,
            last_row=2,
            first_col=0,
            last_col=2,
            value=-5.0,
        )
        adj.mutate(arr)

        expected = np.ones((3, 3)) * 5
        assert_array_equal(arr, expected)

    @given(
        value=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)
    )
    def test_add_property_based(self, value):
        """Property test: adding then subtracting should restore original."""
        arr = np.arange(9, dtype=float).reshape(3, 3)
        original = arr.copy()

        adj_add = Float64Add(0, 2, 0, 2, value)
        adj_add.mutate(arr)

        adj_subtract = Float64Add(0, 2, 0, 2, -value)
        adj_subtract.mutate(arr)

        assert_allclose(arr, original, rtol=1e-10)


class TestFloat64Overwrite:
    """Tests for Float64Overwrite adjustment."""

    def test_overwrite_single_cell(self):
        """Test overwriting a single cell."""
        arr = np.arange(9, dtype=float).reshape(3, 3)
        adj = Float64Overwrite(
            first_row=1,
            last_row=1,
            first_col=1,
            last_col=1,
            value=99.0,
        )
        adj.mutate(arr)

        expected = np.array([
            [0., 1., 2.],
            [3., 99., 5.],
            [6., 7., 8.]
        ])
        assert_array_equal(arr, expected)

    def test_overwrite_subarray(self):
        """Test overwriting a rectangular subarray."""
        arr = np.arange(9, dtype=float).reshape(3, 3)
        adj = Float64Overwrite(
            first_row=1,
            last_row=2,
            first_col=1,
            last_col=2,
            value=0.0,
        )
        adj.mutate(arr)

        expected = np.array([
            [0., 1., 2.],
            [3., 0., 0.],
            [6., 0., 0.]
        ])
        assert_array_equal(arr, expected)

    def test_overwrite_with_nan(self):
        """Test overwriting with NaN."""
        arr = np.arange(9, dtype=float).reshape(3, 3)
        adj = Float64Overwrite(
            first_row=0,
            last_row=2,
            first_col=0,
            last_col=0,
            value=np.nan,
        )
        adj.mutate(arr)

        assert np.isnan(arr[:, 0]).all()
        assert not np.isnan(arr[:, 1:]).any()


class TestFloat641DArrayOverwrite:
    """Tests for Float641DArrayOverwrite adjustment."""

    def test_1d_array_overwrite_single_column(self):
        """Test overwriting a single column with different values per row."""
        arr = np.arange(25, dtype=float).reshape(5, 5)
        values = np.array([100., 200., 300., 400.], dtype=float)
        adj = Float641DArrayOverwrite(
            first_row=0,
            last_row=3,
            first_col=0,
            last_col=0,
            values=values,
        )
        adj.mutate(arr)

        expected = np.arange(25, dtype=float).reshape(5, 5)
        expected[0:4, 0] = values
        assert_array_equal(arr, expected)

    def test_1d_array_overwrite_multiple_columns(self):
        """Test overwriting multiple columns with same values per row."""
        arr = np.arange(25, dtype=float).reshape(5, 5)
        values = np.array([1., 2., 3., 4.], dtype=float)
        adj = Float641DArrayOverwrite(
            first_row=0,
            last_row=3,
            first_col=1,
            last_col=3,
            values=values,
        )
        adj.mutate(arr)

        expected = np.arange(25, dtype=float).reshape(5, 5)
        for col in [1, 2, 3]:
            expected[0:4, col] = values
        assert_array_equal(arr, expected)

    def test_1d_array_overwrite_wrong_length(self):
        """Test that mismatched array length raises ValueError."""
        arr = np.arange(25, dtype=float).reshape(5, 5)
        values = np.array([1., 2., 3.], dtype=float)  # Wrong length

        with pytest.raises(ValueError, match="Mismatch"):
            Float641DArrayOverwrite(
                first_row=0,
                last_row=3,  # 4 rows
                first_col=0,
                last_col=0,
                values=values,  # Only 3 values
            )


class TestDatetime64Overwrite:
    """Tests for Datetime64Overwrite adjustment."""

    def test_datetime_overwrite_single_cell(self):
        """Test overwriting a single datetime cell."""
        dts = pd.date_range('2014', freq='D', periods=9, tz='UTC')
        arr = dts.values.reshape(3, 3)
        original_first = arr[0, 0].copy()

        adj = Datetime64Overwrite(
            first_row=1,
            last_row=1,
            first_col=1,
            last_col=1,
            value=np.datetime64(0, 'ns'),
        )
        adj.mutate(arr.view(np.int64))

        assert arr[1, 1] == np.datetime64(0, 'ns')
        assert arr[0, 0] == original_first  # Compare numpy datetime64 values

    def test_datetime_overwrite_subarray(self):
        """Test overwriting a rectangular subarray of datetimes."""
        dts = pd.date_range('2014', freq='D', periods=9, tz='UTC')
        arr = dts.values.reshape(3, 3)

        adj = Datetime64Overwrite(
            first_row=1,
            last_row=2,
            first_col=1,
            last_col=2,
            value=np.datetime64(0, 'ns'),
        )
        adj.mutate(arr.view(np.int64))

        expected_zero = arr == np.datetime64(0, 'ns')
        assert expected_zero[1:3, 1:3].all()
        assert not expected_zero[0, :].any()
        assert not expected_zero[:, 0].any()


class TestDatetime641DArrayOverwrite:
    """Tests for Datetime641DArrayOverwrite adjustment."""

    def test_datetime_1d_array_overwrite(self):
        """Test overwriting datetimes with an array of values."""
        dts = pd.date_range('2014', freq='D', periods=9, tz='UTC')
        arr = dts.values.reshape(3, 3)

        values = np.array([
            np.datetime64(0, 'ns'),
            np.datetime64(1, 'ns')
        ])

        adj = Datetime641DArrayOverwrite(
            first_row=1,
            last_row=2,
            first_col=1,
            last_col=2,
            values=values,  # Pass datetime64 directly, not int64 view
        )
        adj.mutate(arr.view(np.int64))

        # Check row 1, cols 1-2
        assert arr[1, 1] == np.datetime64(0, 'ns')
        assert arr[1, 2] == np.datetime64(0, 'ns')

        # Check row 2, cols 1-2
        assert arr[2, 1] == np.datetime64(1, 'ns')
        assert arr[2, 2] == np.datetime64(1, 'ns')


class TestInt64Overwrite:
    """Tests for Int64Overwrite adjustment."""

    def test_int64_overwrite_single_cell(self):
        """Test overwriting a single int64 cell."""
        arr = np.arange(9, dtype=np.int64).reshape(3, 3)
        adj = Int64Overwrite(
            first_row=1,
            last_row=1,
            first_col=1,
            last_col=1,
            value=999,
        )
        adj.mutate(arr)

        expected = np.array([
            [0, 1, 2],
            [3, 999, 5],
            [6, 7, 8]
        ], dtype=np.int64)
        assert_array_equal(arr, expected)

    def test_int64_overwrite_subarray(self):
        """Test overwriting a rectangular subarray of int64."""
        arr = np.arange(9, dtype=np.int64).reshape(3, 3)
        adj = Int64Overwrite(
            first_row=1,
            last_row=2,
            first_col=1,
            last_col=2,
            value=0,
        )
        adj.mutate(arr)

        expected = np.array([
            [0, 1, 2],
            [3, 0, 0],
            [6, 0, 0]
        ], dtype=np.int64)
        assert_array_equal(arr, expected)


class TestBooleanOverwrite:
    """Tests for BooleanOverwrite adjustment."""

    def test_boolean_overwrite_single_cell(self):
        """Test overwriting a single boolean cell."""
        arr = np.zeros((3, 3), dtype=np.uint8)
        adj = BooleanOverwrite(
            first_row=1,
            last_row=1,
            first_col=1,
            last_col=1,
            value=np.uint8(1),
        )
        adj.mutate(arr)

        expected = np.zeros((3, 3), dtype=np.uint8)
        expected[1, 1] = 1
        assert_array_equal(arr, expected)

    def test_boolean_overwrite_subarray(self):
        """Test overwriting a rectangular subarray of booleans."""
        arr = np.ones((3, 3), dtype=np.uint8)
        adj = BooleanOverwrite(
            first_row=1,
            last_row=2,
            first_col=1,
            last_col=2,
            value=np.uint8(0),
        )
        adj.mutate(arr)

        expected = np.ones((3, 3), dtype=np.uint8)
        expected[1:3, 1:3] = 0
        assert_array_equal(arr, expected)


class TestBoolean1DArrayOverwrite:
    """Tests for Boolean1DArrayOverwrite adjustment."""

    def test_boolean_1d_array_overwrite(self):
        """Test overwriting booleans with an array of values."""
        arr = np.zeros((5, 5), dtype=np.uint8)
        values = np.array([True, False, True, False], dtype=bool)  # Use bool dtype

        adj = Boolean1DArrayOverwrite(
            first_row=0,
            last_row=3,
            first_col=2,
            last_col=3,
            values=values,
        )
        adj.mutate(arr)

        expected = np.zeros((5, 5), dtype=np.uint8)
        expected[0:4, 2] = values.view(np.uint8)
        expected[0:4, 3] = values.view(np.uint8)
        assert_array_equal(arr, expected)


class TestObjectOverwrite:
    """Tests for ObjectOverwrite adjustment.

    Note: ObjectOverwrite is designed for LabelArray objects which have a
    set_scalar method, not regular numpy arrays. These tests are skipped
    as they require specialized array types.
    """

    @pytest.mark.skip(reason="ObjectOverwrite requires LabelArray, not numpy array")
    def test_object_overwrite_strings(self):
        """Test overwriting string objects."""
        # This would require a LabelArray object
        pass

    @pytest.mark.skip(reason="ObjectOverwrite requires LabelArray, not numpy array")
    def test_object_overwrite_none(self):
        """Test overwriting with None."""
        # This would require a LabelArray object
        pass


class TestObject1DArrayOverwrite:
    """Tests for Object1DArrayOverwrite adjustment.

    Note: Object1DArrayOverwrite is designed for LabelArray objects.
    """

    @pytest.mark.skip(reason="Object1DArrayOverwrite requires LabelArray")
    def test_object_1d_array_overwrite(self):
        """Test overwriting objects with an array of values."""
        # This would require a LabelArray object
        pass


class TestAdjustmentValidation:
    """Tests for adjustment validation and error handling."""

    def test_invalid_row_indices(self):
        """Test that invalid row indices raise ValueError."""
        with pytest.raises(ValueError, match="first_row"):
            Float64Multiply(
                first_row=5,
                last_row=3,  # last_row < first_row
                first_col=0,
                last_col=0,
                value=2.0,
            )

    def test_invalid_col_indices(self):
        """Test that invalid column indices raise ValueError."""
        with pytest.raises(ValueError, match="first_col"):
            Float64Multiply(
                first_row=0,
                last_row=2,
                first_col=5,
                last_col=3,  # last_col < first_col
                value=2.0,
            )

    def test_negative_indices(self):
        """Test that negative indices raise ValueError."""
        with pytest.raises(ValueError):
            Float64Multiply(
                first_row=-1,
                last_row=2,
                first_col=0,
                last_col=2,
                value=2.0,
            )


class TestAdjustmentEquality:
    """Tests for adjustment equality comparison."""

    def test_equal_adjustments(self):
        """Test that identical adjustments are equal."""
        adj1 = Float64Multiply(0, 2, 0, 2, 1.5)
        adj2 = Float64Multiply(0, 2, 0, 2, 1.5)
        assert adj1 == adj2

    def test_unequal_adjustments_value(self):
        """Test that adjustments with different values are not equal."""
        adj1 = Float64Multiply(0, 2, 0, 2, 1.5)
        adj2 = Float64Multiply(0, 2, 0, 2, 2.0)
        assert adj1 != adj2

    def test_unequal_adjustments_indices(self):
        """Test that adjustments with different indices are not equal."""
        adj1 = Float64Multiply(0, 2, 0, 2, 1.5)
        adj2 = Float64Multiply(0, 1, 0, 2, 1.5)
        assert adj1 != adj2

    def test_unequal_adjustments_type(self):
        """Test that different adjustment types are not equal."""
        adj1 = Float64Multiply(0, 2, 0, 2, 1.5)
        adj2 = Float64Add(0, 2, 0, 2, 1.5)
        assert adj1 != adj2


class TestAdjustmentSerialization:
    """Tests for adjustment pickling/unpickling."""

    def test_adjustment_pickle_roundtrip(self):
        """Test that adjustments can be pickled and unpickled."""
        import pickle

        adj = Float64Multiply(0, 2, 1, 3, 2.5)
        pickled = pickle.dumps(adj)
        unpickled = pickle.loads(pickled)

        assert adj == unpickled
        assert unpickled.first_row == 0
        assert unpickled.last_row == 2
        assert unpickled.first_col == 1
        assert unpickled.last_col == 3
        assert unpickled.value == 2.5


class TestChooseAdjustmentType:
    """Tests for choose_adjustment_type function."""

    def test_choose_float_multiply(self):
        """Test choosing Float64Multiply."""
        adj_type = choose_adjustment_type(MULTIPLY, 2.0)
        assert adj_type == Float64Multiply

    def test_choose_float_add(self):
        """Test choosing Float64Add."""
        adj_type = choose_adjustment_type(ADD, 1.5)
        assert adj_type == Float64Add

    def test_choose_float_overwrite(self):
        """Test choosing Float64Overwrite."""
        adj_type = choose_adjustment_type(OVERWRITE, 3.14)
        assert adj_type == Float64Overwrite

    def test_choose_datetime_overwrite(self):
        """Test choosing Datetime64Overwrite."""
        adj_type = choose_adjustment_type(OVERWRITE, np.datetime64('2020-01-01', 'ns'))
        assert adj_type == Datetime64Overwrite

    def test_choose_int_overwrite(self):
        """Test choosing Int64Overwrite."""
        adj_type = choose_adjustment_type(OVERWRITE, 42)
        assert adj_type == Int64Overwrite

    def test_choose_bool_overwrite(self):
        """Test choosing BooleanOverwrite."""
        adj_type = choose_adjustment_type(OVERWRITE, True)
        assert adj_type == BooleanOverwrite

    def test_choose_object_overwrite(self):
        """Test choosing ObjectOverwrite."""
        adj_type = choose_adjustment_type(OVERWRITE, 'test')
        assert adj_type == ObjectOverwrite

    def test_invalid_multiply_with_string(self):
        """Test that MULTIPLY with string raises TypeError."""
        with pytest.raises(TypeError, match="Can't construct"):
            choose_adjustment_type(MULTIPLY, 'invalid')

    def test_invalid_add_with_datetime(self):
        """Test that ADD with datetime raises TypeError."""
        with pytest.raises(TypeError, match="Can't construct"):
            choose_adjustment_type(ADD, np.datetime64('2020-01-01', 'ns'))


class TestMakeAdjustmentFromIndices:
    """Tests for make_adjustment_from_indices function."""

    def test_make_multiply_adjustment(self):
        """Test making a multiply adjustment from indices."""
        adj = make_adjustment_from_indices(
            first_row=0,
            last_row=2,
            first_column=0,
            last_column=2,
            adjustment_kind=MULTIPLY,
            value=2.0,
        )

        assert isinstance(adj, Float64Multiply)
        assert adj.first_row == 0
        assert adj.last_row == 2
        assert adj.first_col == 0
        assert adj.last_col == 2
        assert adj.value == 2.0

    def test_make_overwrite_adjustment(self):
        """Test making an overwrite adjustment from indices."""
        adj = make_adjustment_from_indices(
            first_row=1,
            last_row=1,
            first_column=1,
            last_column=1,
            adjustment_kind=OVERWRITE,
            value=np.datetime64('2020-01-01', 'ns'),  # Must be nanosecond precision
        )

        assert isinstance(adj, Datetime64Overwrite)


class TestGetAdjustmentLocs:
    """Tests for get_adjustment_locs function."""

    def test_get_adjustment_locs_exact_dates(self):
        """Test getting adjustment locations with exact dates."""
        dates = pd.date_range('2014-01-01', '2014-01-07')
        assets = pd.Index(range(10), dtype='int64')

        locs = get_adjustment_locs(
            dates,
            assets,
            pd.Timestamp('2014-01-03'),
            pd.Timestamp('2014-01-05'),
            3,
        )

        assert locs == (2, 4, 3)

    def test_get_adjustment_locs_null_start_date(self):
        """Test that null start date means beginning of data."""
        dates = pd.date_range('2014-01-01', '2014-01-07')
        assets = pd.Index(range(10), dtype='int64')

        locs = get_adjustment_locs(
            dates,
            assets,
            None,  # Null start date
            pd.Timestamp('2014-01-05'),
            5,
        )

        assert locs[0] == 0  # Start from beginning


class TestMakeAdjustmentFromLabels:
    """Tests for make_adjustment_from_labels function."""

    def test_make_adjustment_from_labels(self):
        """Test making an adjustment from date/asset labels."""
        dates = pd.date_range('2014-01-01', '2014-01-10')
        assets = pd.Index(range(10), dtype='int64')

        adj = make_adjustment_from_labels(
            dates,
            assets,
            pd.Timestamp('2014-01-03'),
            pd.Timestamp('2014-01-05'),
            5,
            MULTIPLY,
            2.0,
        )

        assert isinstance(adj, Float64Multiply)
        assert adj.first_row == 2
        assert adj.last_row == 4
        assert adj.first_col == 5
        assert adj.last_col == 5
        assert adj.value == 2.0


class TestAdjustmentRepr:
    """Tests for adjustment __repr__ methods."""

    def test_float64_adjustment_repr(self):
        """Test Float64 adjustment repr."""
        adj = Float64Multiply(0, 2, 1, 3, 2.5)
        repr_str = repr(adj)

        assert 'Float64Multiply' in repr_str
        assert 'first_row=0' in repr_str
        assert 'last_row=2' in repr_str
        assert 'first_col=1' in repr_str
        assert 'last_col=3' in repr_str
        assert 'value=2.5' in repr_str
