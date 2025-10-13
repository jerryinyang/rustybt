"""
Tests for Rust optimization wrapper with fallback.

Validates that the wrapper provides consistent API whether Rust is available or not.
"""

import math
from decimal import Decimal

import pytest

pytestmark = pytest.mark.rust


def test_wrapper_module_imports():
    """Test that rust_optimizations module can be imported."""
    from rustybt import rust_optimizations

    assert rust_optimizations is not None
    assert hasattr(rust_optimizations, "RUST_AVAILABLE")


def test_sma_basic():
    """Test SMA calculation."""
    from rustybt.rust_optimizations import rust_sma

    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    result = rust_sma(values, 3)

    assert len(result) == 5
    assert math.isnan(result[0])
    assert math.isnan(result[1])
    assert abs(result[2] - 2.0) < 1e-10
    assert abs(result[3] - 3.0) < 1e-10
    assert abs(result[4] - 4.0) < 1e-10


def test_ema_basic():
    """Test EMA calculation."""
    from rustybt.rust_optimizations import rust_ema

    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    result = rust_ema(values, 3)

    assert len(result) == 5
    assert result[0] == 1.0
    # EMA should be increasing
    for i in range(1, len(result)):
        assert result[i] > result[i - 1]


def test_array_sum_basic():
    """Test array sum."""
    from rustybt.rust_optimizations import rust_array_sum

    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    result = rust_array_sum(values)

    assert result == 15.0


def test_array_sum_empty():
    """Test array sum with empty list."""
    from rustybt.rust_optimizations import rust_array_sum

    values = []
    result = rust_array_sum(values)

    assert result == 0.0


def test_mean_basic():
    """Test mean calculation."""
    from rustybt.rust_optimizations import rust_mean

    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    result = rust_mean(values)

    assert result == 3.0


def test_mean_empty():
    """Test mean with empty list."""
    from rustybt.rust_optimizations import rust_mean

    values = []
    result = rust_mean(values)

    assert math.isnan(result)


def test_decimal_sma_wrapper():
    """Decimal inputs should return Decimal outputs."""
    from rustybt.rust_optimizations import rust_sma

    values = [Decimal("1.00"), Decimal("2.00"), Decimal("3.00"), Decimal("4.00")]
    result = rust_sma(values, 2)

    assert all(isinstance(val, Decimal) or math.isnan(float(val)) for val in result)


def test_rolling_sum_basic():
    """Test rolling sum calculation."""
    from rustybt.rust_optimizations import rust_rolling_sum

    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    result = rust_rolling_sum(values, 3)

    assert len(result) == 5
    assert math.isnan(result[0])
    assert math.isnan(result[1])
    assert result[2] == 6.0  # 1+2+3
    assert result[3] == 9.0  # 2+3+4
    assert result[4] == 12.0  # 3+4+5


def test_window_slice():
    """Test window slice operation."""
    from rustybt.rust_optimizations import rust_window_slice

    data = [1.0, 2.0, 3.0, 4.0, 5.0]
    result = rust_window_slice(data, 1, 4)

    assert result == [2.0, 3.0, 4.0]


def test_create_columns():
    """Test column creation (returns flattened data with shape)."""
    from rustybt.rust_optimizations import rust_create_columns

    data = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]
    result = rust_create_columns(data)

    # Rust returns (flattened_data, n_rows, n_cols)
    assert result == ([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], 3, 2)


def test_index_select():
    """Test index selection."""
    from rustybt.rust_optimizations import rust_index_select

    data = [10.0, 20.0, 30.0, 40.0, 50.0]
    indices = [0, 2, 4]
    result = rust_index_select(data, indices)

    assert result == [10.0, 30.0, 50.0]


def test_fillna():
    """Test NaN filling."""
    from rustybt.rust_optimizations import rust_fillna

    data = [1.0, float("nan"), 3.0, float("nan"), 5.0]
    result = rust_fillna(data, 0.0)

    assert result == [1.0, 0.0, 3.0, 0.0, 5.0]


def test_pairwise_add():
    """Test pairwise addition."""
    from rustybt.rust_optimizations import rust_pairwise_op

    a = [1.0, 2.0, 3.0]
    b = [4.0, 5.0, 6.0]
    result = rust_pairwise_op(a, b, "add")

    assert result == [5.0, 7.0, 9.0]


def test_pairwise_multiply():
    """Test pairwise multiplication."""
    from rustybt.rust_optimizations import rust_pairwise_op

    a = [2.0, 3.0, 4.0]
    b = [5.0, 6.0, 7.0]
    result = rust_pairwise_op(a, b, "mul")  # Rust uses 'mul' not 'multiply'

    assert result == [10.0, 18.0, 28.0]


def test_sma_edge_case_window_larger_than_data():
    """Test SMA when window is larger than data."""
    from rustybt.rust_optimizations import rust_sma

    values = [1.0, 2.0]
    result = rust_sma(values, 5)

    assert all(math.isnan(x) for x in result)


def test_sma_edge_case_window_one():
    """Test SMA with window of 1 (should return original values)."""
    from rustybt.rust_optimizations import rust_sma

    values = [1.0, 2.0, 3.0]
    result = rust_sma(values, 1)

    assert result == values


def test_error_handling_invalid_window():
    """Test that invalid window size raises ValueError."""
    from rustybt.rust_optimizations import rust_sma

    with pytest.raises(ValueError, match="Window size must be greater than 0"):
        rust_sma([1.0, 2.0, 3.0], 0)


def test_error_handling_pairwise_length_mismatch():
    """Test that mismatched array lengths raise ValueError."""
    from rustybt.rust_optimizations import rust_pairwise_op

    a = [1.0, 2.0]
    b = [3.0, 4.0, 5.0]

    # Rust error message differs slightly
    with pytest.raises(ValueError, match="Array lengths don't match"):
        rust_pairwise_op(a, b, "add")
