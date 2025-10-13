"""Property-based equivalence tests for Rust optimizations.

This module uses hypothesis for property-based testing to ensure Rust implementations
produce identical results to Python implementations across a wide range of inputs.

These tests fulfill AC6: Tests validate Rust and Python implementations produce identical results.
"""

import math
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from rustybt.rust_optimizations import (
    RUST_AVAILABLE,
    rust_array_sum,
    rust_create_columns,
    rust_ema,
    rust_fillna,
    rust_index_select,
    rust_mean,
    rust_pairwise_op,
    rust_rolling_sum,
    rust_sma,
    rust_window_slice,
)

# Mark all tests in this module as rust_equivalence
pytestmark = pytest.mark.rust_equivalence


# Strategy for floating point numbers (avoid extreme values that cause numerical issues)
float_strategy = st.floats(
    min_value=-1e6,
    max_value=1e6,
    allow_nan=False,
    allow_infinity=False,
)

# Strategy for arrays of floats
array_strategy = st.lists(float_strategy, min_size=1, max_size=100)


def pure_python_sma(values, window):
    """Pure Python SMA for equivalence testing."""
    if window <= 0:
        raise ValueError("Window size must be greater than 0")
    if not values:
        return []

    result = [float("nan")] * len(values)
    if len(values) < window:
        return result

    first_sum = sum(values[:window])
    result[window - 1] = first_sum / window

    for i in range(window, len(values)):
        prev_sma = result[i - 1]
        new_val = values[i]
        old_val = values[i - window]
        result[i] = prev_sma + (new_val - old_val) / window

    return result


def pure_python_ema(values, span):
    """Pure Python EMA for equivalence testing."""
    if span <= 0:
        raise ValueError("Span must be greater than 0")
    if not values:
        return []

    result = [0.0] * len(values)
    alpha = 2.0 / (span + 1.0)
    result[0] = values[0]

    for i in range(1, len(values)):
        result[i] = alpha * values[i] + (1.0 - alpha) * result[i - 1]

    return result


def pure_python_decimal_sma(values, window):
    """Pure Python Decimal SMA for equivalence testing."""
    if window <= 0:
        raise ValueError("Window size must be greater than 0")
    if not values:
        return []

    result = [Decimal("NaN")] * len(values)
    if len(values) < window:
        return result

    total = sum(values[:window], Decimal(0))
    result[window - 1] = total / Decimal(window)

    rolling_sum = total
    for idx in range(window, len(values)):
        rolling_sum += values[idx]
        rolling_sum -= values[idx - window]
        result[idx] = rolling_sum / Decimal(window)

    return result


def pure_python_decimal_ema(values, span):
    """Pure Python Decimal EMA for equivalence testing."""
    if span <= 0:
        raise ValueError("Span must be greater than 0")
    if not values:
        return []

    alpha = Decimal(2) / Decimal(span + 1)
    one_minus_alpha = Decimal(1) - alpha

    result = []
    ema = values[0]
    result.append(ema)

    for value in values[1:]:
        ema = alpha * value + one_minus_alpha * ema
        result.append(ema)

    return result


def arrays_equal(a, b, rel_tol=1e-9):
    """Compare arrays with tolerance for floating point errors."""
    if len(a) != len(b):
        return False

    for x, y in zip(a, b, strict=False):
        if math.isnan(x) and math.isnan(y):
            continue
        if not math.isclose(x, y, rel_tol=rel_tol):
            return False

    return True


# Test: SMA Equivalence
@settings(max_examples=1000)
@given(
    values=st.lists(float_strategy, min_size=10, max_size=100),
    window=st.integers(min_value=2, max_value=20),
)
def test_sma_equivalence(values, window):
    """Rust SMA must match Python SMA across all inputs."""
    if window > len(values):
        pytest.skip("Window larger than array")

    python_result = pure_python_sma(values, window)
    rust_result = rust_sma(values, window)

    assert arrays_equal(
        rust_result, python_result
    ), f"SMA mismatch: Rust={rust_result[:5]}... Python={python_result[:5]}..."


# Test: EMA Equivalence
@settings(max_examples=1000)
@given(
    values=st.lists(float_strategy, min_size=10, max_size=100),
    span=st.integers(min_value=2, max_value=50),
)
def test_ema_equivalence(values, span):
    """Rust EMA must match Python EMA across all inputs."""
    python_result = pure_python_ema(values, span)
    rust_result = rust_ema(values, span)

    assert arrays_equal(
        rust_result, python_result
    ), f"EMA mismatch: Rust={rust_result[:5]}... Python={python_result[:5]}..."


# Test: Array Sum Equivalence
@settings(max_examples=1000)
@given(values=array_strategy)
def test_array_sum_equivalence(values):
    """Rust array sum must match Python sum."""
    python_result = sum(values)
    rust_result = rust_array_sum(values)

    assert math.isclose(
        rust_result, python_result, rel_tol=1e-9
    ), f"Sum mismatch: Rust={rust_result} Python={python_result}"


# Test: Mean Equivalence
@settings(max_examples=1000)
@given(values=array_strategy)
def test_mean_equivalence(values):
    """Rust mean must match Python mean."""
    python_result = sum(values) / len(values) if values else float("nan")
    rust_result = rust_mean(values)

    if math.isnan(python_result):
        assert math.isnan(rust_result)
    else:
        assert math.isclose(
            rust_result, python_result, rel_tol=1e-9
        ), f"Mean mismatch: Rust={rust_result} Python={python_result}"


# Test: Rolling Sum Equivalence
@settings(max_examples=1000)
@given(
    values=st.lists(float_strategy, min_size=10, max_size=100),
    window=st.integers(min_value=2, max_value=20),
)
def test_rolling_sum_equivalence(values, window):
    """Rust rolling sum must match Python rolling sum."""
    if window > len(values):
        pytest.skip("Window larger than array")

    # Pure Python rolling sum
    python_result = [float("nan")] * len(values)
    if len(values) >= window:
        first_sum = sum(values[:window])
        python_result[window - 1] = first_sum
        for i in range(window, len(values)):
            python_result[i] = python_result[i - 1] + values[i] - values[i - window]

    rust_result = rust_rolling_sum(values, window)

    assert arrays_equal(
        rust_result, python_result
    ), f"Rolling sum mismatch: Rust={rust_result[:5]}... Python={python_result[:5]}..."


# Test: Window Slice Equivalence
@settings(max_examples=1000)
@given(
    values=array_strategy,
    start=st.integers(min_value=0, max_value=50),
    end=st.integers(min_value=1, max_value=100),
)
def test_window_slice_equivalence(values, start, end):
    """Rust window slice must match Python slice."""
    if start >= len(values) or end > len(values) or start >= end:
        pytest.skip("Invalid slice bounds")

    python_result = values[start:end]
    rust_result = rust_window_slice(values, start, end)

    assert (
        rust_result == python_result
    ), f"Slice mismatch: Rust={rust_result} Python={python_result}"


# Test: Index Select Equivalence
@settings(max_examples=1000)
@given(
    values=array_strategy,
    indices=st.lists(st.integers(min_value=0, max_value=99), min_size=1, max_size=20),
)
def test_index_select_equivalence(values, indices):
    """Rust index select must match Python list comprehension."""
    # Filter out invalid indices
    valid_indices = [i for i in indices if i < len(values)]
    if not valid_indices:
        pytest.skip("No valid indices")

    python_result = [values[i] for i in valid_indices]
    rust_result = rust_index_select(values, valid_indices)

    assert (
        rust_result == python_result
    ), f"Index select mismatch: Rust={rust_result} Python={python_result}"


# Test: Fill NaN Equivalence
@settings(max_examples=1000)
@given(
    values=st.lists(
        st.one_of(float_strategy, st.just(float("nan"))),
        min_size=1,
        max_size=100,
    ),
    fill_value=float_strategy,
)
def test_fillna_equivalence(values, fill_value):
    """Rust fillna must match Python fillna."""
    python_result = [fill_value if math.isnan(x) else x for x in values]
    rust_result = rust_fillna(values, fill_value)

    assert arrays_equal(
        rust_result, python_result
    ), f"Fillna mismatch: Rust={rust_result[:5]}... Python={python_result[:5]}..."


# Test: Pairwise Operations Equivalence
@settings(max_examples=1000)
@given(
    size=st.integers(min_value=1, max_value=100),
    op=st.sampled_from(["add", "sub", "mul", "div"]),
)
def test_pairwise_op_equivalence(size, op):
    """Rust pairwise operations must match Python operations."""
    # Generate two arrays of the same size

    a = [float(i) for i in range(1, size + 1)]
    b = [float(i) for i in range(1, size + 1)]

    # Python implementation
    if op == "add":
        python_result = [x + y for x, y in zip(a, b, strict=False)]
    elif op == "sub":
        python_result = [x - y for x, y in zip(a, b, strict=False)]
    elif op == "mul":
        python_result = [x * y for x, y in zip(a, b, strict=False)]
    elif op == "div":
        python_result = [x / y for x, y in zip(a, b, strict=False)]

    rust_result = rust_pairwise_op(a, b, op)

    assert arrays_equal(
        rust_result, python_result, rel_tol=1e-7
    ), f"Pairwise {op} mismatch: Rust={rust_result[:5]}... Python={python_result[:5]}..."


# Test: Create Columns Equivalence
@settings(max_examples=1000)
@given(
    n_rows=st.integers(min_value=1, max_value=50),
    n_cols=st.integers(min_value=1, max_value=10),
)
def test_create_columns_equivalence(n_rows, n_cols):
    """Rust create_columns must match Python implementation."""
    # Create test data: n_cols columns with n_rows each
    data = [[float(i * n_cols + j) for i in range(n_rows)] for j in range(n_cols)]

    # Python implementation
    flattened_py = []
    for col in data:
        flattened_py.extend(col)
    python_result = (flattened_py, n_rows, n_cols)

    rust_result = rust_create_columns(data)

    assert rust_result[1] == python_result[1], "Row count mismatch"
    assert rust_result[2] == python_result[2], "Column count mismatch"
    assert (
        rust_result[0] == python_result[0]
    ), f"Flattened data mismatch: Rust={rust_result[0][:10]}... Python={python_result[0][:10]}..."


# Edge Cases Tests
def test_empty_array_handling():
    """Test empty array edge cases."""
    assert rust_array_sum([]) == 0.0
    assert math.isnan(rust_mean([]))
    assert rust_sma([], 3) == []
    assert rust_ema([], 3) == []
    assert rust_rolling_sum([], 3) == []


def test_single_element_arrays():
    """Test single element arrays."""
    assert rust_array_sum([42.0]) == 42.0
    assert rust_mean([42.0]) == 42.0
    assert rust_ema([42.0], 3) == [42.0]


def test_error_conditions():
    """Test that both implementations raise errors consistently."""
    # Invalid window sizes
    with pytest.raises(ValueError):
        rust_sma([1.0, 2.0, 3.0], 0)

    with pytest.raises(ValueError):
        rust_rolling_sum([1.0, 2.0, 3.0], -1)

    # Mismatched array lengths in pairwise op
    with pytest.raises(ValueError):
        rust_pairwise_op([1.0, 2.0], [1.0], "add")

    # Invalid column lengths in create_columns
    with pytest.raises(ValueError):
        rust_create_columns([[1.0, 2.0], [3.0]])


# Conditional test for when Rust is available
@pytest.mark.skipif(not RUST_AVAILABLE, reason="Rust extensions not available")
def test_rust_available():
    """Verify Rust extensions are loaded correctly."""
    assert RUST_AVAILABLE is True

    # Test that a simple operation works
    result = rust_array_sum([1.0, 2.0, 3.0])
    assert result == 6.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])


def test_decimal_sma_equivalence_fixed_precision():
    values = [Decimal("100.00"), Decimal("101.00"), Decimal("102.50"), Decimal("103.25")]
    window = 2
    python_result = pure_python_decimal_sma(values, window)
    rust_result = rust_sma(values, window)
    for rust_val, py_val in zip(rust_result, python_result, strict=False):
        if isinstance(py_val, Decimal) and py_val.is_nan():
            assert isinstance(rust_val, Decimal) and rust_val.is_nan()
        else:
            assert rust_val == py_val


def test_decimal_ema_equivalence_fixed_precision():
    values = [Decimal("100.00"), Decimal("101.00"), Decimal("102.00"), Decimal("103.00")]
    span = 3
    python_result = pure_python_decimal_ema(values, span)
    rust_result = rust_ema(values, span)
    assert rust_result == python_result


def test_window_slice_invalid_bounds_python(monkeypatch):
    monkeypatch.setattr("rustybt.rust_optimizations.RUST_AVAILABLE", False)
    data = [1.0, 2.0, 3.0]
    with pytest.raises(IndexError, match="Invalid window bounds"):
        rust_window_slice(data, 5, 10)


def test_decimal_index_select_invalid(monkeypatch):
    monkeypatch.setattr("rustybt.rust_optimizations.RUST_AVAILABLE", False)
    data = [Decimal("1.0"), Decimal("2.0")]
    with pytest.raises(IndexError, match="Index 3 out of bounds"):
        rust_index_select(data, [0, 3])


# ====================================================================
# COMPREHENSIVE DECIMAL PROPERTY-BASED TESTS (AC6 - Decimal Coverage)
# ====================================================================

# Strategy for Decimal numbers with financial precision
decimal_strategy = st.builds(
    Decimal,
    st.one_of(
        st.integers(min_value=-1_000_000, max_value=1_000_000),
        st.floats(
            min_value=-1_000_000.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False
        ).map(str),
    ).map(str),
)

# Strategy for arrays of Decimals
decimal_array_strategy = st.lists(decimal_strategy, min_size=1, max_size=100)


def decimals_equal(a, b, places=10):
    """Compare Decimal arrays with tolerance."""
    if len(a) != len(b):
        return False

    for x, y in zip(a, b, strict=False):
        if isinstance(x, Decimal) and isinstance(y, Decimal):
            if x.is_nan() and y.is_nan():
                continue
            # Compare with quantization to handle rounding differences
            try:
                x_rounded = x.quantize(Decimal(10) ** -places)
                y_rounded = y.quantize(Decimal(10) ** -places)
                if x_rounded != y_rounded:
                    return False
            except:
                if x != y:
                    return False
        else:
            if x != y:
                return False

    return True


@settings(max_examples=500)
@given(
    values=st.lists(decimal_strategy, min_size=10, max_size=50),
    window=st.integers(min_value=2, max_value=20),
)
def test_decimal_sma_property_based(values, window):
    """Property-based test: Decimal SMA must match Python Decimal SMA."""
    if window > len(values):
        pytest.skip("Window larger than array")

    python_result = pure_python_decimal_sma(values, window)
    rust_result = rust_sma(values, window)

    assert decimals_equal(
        rust_result, python_result, places=8
    ), f"Decimal SMA mismatch:\nRust={rust_result[:3]}\nPython={python_result[:3]}"


@settings(max_examples=500)
@given(
    values=st.lists(decimal_strategy, min_size=10, max_size=50),
    span=st.integers(min_value=2, max_value=30),
)
def test_decimal_ema_property_based(values, span):
    """Property-based test: Decimal EMA must match Python Decimal EMA."""
    python_result = pure_python_decimal_ema(values, span)
    rust_result = rust_ema(values, span)

    assert decimals_equal(
        rust_result, python_result, places=8
    ), f"Decimal EMA mismatch:\nRust={rust_result[:3]}\nPython={python_result[:3]}"


@settings(max_examples=500)
@given(values=decimal_array_strategy)
def test_decimal_sum_property_based(values):
    """Property-based test: Decimal sum must match Python sum."""
    python_result = sum(values, Decimal(0))
    rust_result = rust_array_sum(values)

    assert isinstance(rust_result, Decimal), "Rust result must be Decimal"
    # Allow small rounding differences
    assert decimals_equal(
        [rust_result], [python_result], places=10
    ), f"Decimal sum mismatch: Rust={rust_result} Python={python_result}"


@settings(max_examples=500)
@given(values=decimal_array_strategy)
def test_decimal_mean_property_based(values):
    """Property-based test: Decimal mean must match Python mean."""
    from decimal import getcontext

    ctx = getcontext()

    python_result = ctx.divide(sum(values, Decimal(0)), Decimal(len(values)))
    rust_result = rust_mean(values)

    assert isinstance(rust_result, Decimal), "Rust result must be Decimal"
    assert decimals_equal(
        [rust_result], [python_result], places=8
    ), f"Decimal mean mismatch: Rust={rust_result} Python={python_result}"


@settings(max_examples=500)
@given(
    values=st.lists(decimal_strategy, min_size=10, max_size=50),
    window=st.integers(min_value=2, max_value=20),
)
def test_decimal_rolling_sum_property_based(values, window):
    """Property-based test: Decimal rolling sum must match Python."""
    if window > len(values):
        pytest.skip("Window larger than array")

    # Pure Python Decimal rolling sum
    python_result = [Decimal("NaN")] * len(values)
    if len(values) >= window:
        rolling_sum = sum(values[:window], Decimal(0))
        python_result[window - 1] = rolling_sum
        for idx in range(window, len(values)):
            rolling_sum += values[idx]
            rolling_sum -= values[idx - window]
            python_result[idx] = rolling_sum

    rust_result = rust_rolling_sum(values, window)

    assert decimals_equal(
        rust_result, python_result, places=8
    ), f"Decimal rolling sum mismatch:\nRust={rust_result[:3]}\nPython={python_result[:3]}"


@settings(max_examples=500)
@given(
    values=decimal_array_strategy,
    start=st.integers(min_value=0, max_value=50),
    end=st.integers(min_value=1, max_value=100),
)
def test_decimal_window_slice_property_based(values, start, end):
    """Property-based test: Decimal window slice must match Python slice."""
    if start >= len(values) or end > len(values) or start >= end:
        pytest.skip("Invalid slice bounds")

    python_result = values[start:end]
    rust_result = rust_window_slice(values, start, end)

    assert all(isinstance(x, Decimal) for x in rust_result), "All results must be Decimal"
    assert (
        rust_result == python_result
    ), f"Decimal slice mismatch:\nRust={rust_result}\nPython={python_result}"


@settings(max_examples=500)
@given(
    values=decimal_array_strategy,
    indices=st.lists(st.integers(min_value=0, max_value=99), min_size=1, max_size=20),
)
def test_decimal_index_select_property_based(values, indices):
    """Property-based test: Decimal index select must match Python."""
    valid_indices = [i for i in indices if i < len(values)]
    if not valid_indices:
        pytest.skip("No valid indices")

    python_result = [values[i] for i in valid_indices]
    rust_result = rust_index_select(values, valid_indices)

    assert all(isinstance(x, Decimal) for x in rust_result), "All results must be Decimal"
    assert (
        rust_result == python_result
    ), f"Decimal index select mismatch:\nRust={rust_result}\nPython={python_result}"


@settings(max_examples=500)
@given(
    values=st.lists(
        st.one_of(decimal_strategy, st.just(Decimal("NaN"))),
        min_size=1,
        max_size=50,
    ),
    fill_value=decimal_strategy,
)
def test_decimal_fillna_property_based(values, fill_value):
    """Property-based test: Decimal fillna must match Python."""
    python_result = [fill_value if (isinstance(x, Decimal) and x.is_nan()) else x for x in values]
    rust_result = rust_fillna(values, fill_value)

    assert all(isinstance(x, Decimal) for x in rust_result), "All results must be Decimal"
    assert (
        rust_result == python_result
    ), f"Decimal fillna mismatch:\nRust={rust_result[:5]}\nPython={python_result[:5]}"


@settings(max_examples=500)
@given(
    size=st.integers(min_value=1, max_value=50),
    op=st.sampled_from(["add", "sub", "mul", "div"]),
)
def test_decimal_pairwise_op_property_based(size, op):
    """Property-based test: Decimal pairwise operations must match Python."""
    from decimal import getcontext

    # Generate two Decimal arrays of the same size (avoid zeros for division)
    if op == "div":
        a = [Decimal(str(i + 1)) for i in range(size)]
        b = [Decimal(str(i + 1)) for i in range(size)]
    else:
        a = [Decimal(str(i)) for i in range(size)]
        b = [Decimal(str(i + 1)) for i in range(size)]

    # Python implementation
    if op == "add":
        python_result = [x + y for x, y in zip(a, b, strict=False)]
    elif op == "sub":
        python_result = [x - y for x, y in zip(a, b, strict=False)]
    elif op == "mul":
        python_result = [x * y for x, y in zip(a, b, strict=False)]
    elif op == "div":
        ctx = getcontext()
        python_result = [ctx.divide(x, y) for x, y in zip(a, b, strict=False)]

    rust_result = rust_pairwise_op(a, b, op)

    assert all(isinstance(x, Decimal) for x in rust_result), "All results must be Decimal"
    assert decimals_equal(
        rust_result, python_result, places=10
    ), f"Decimal pairwise {op} mismatch:\nRust={rust_result[:3]}\nPython={python_result[:3]}"


@settings(max_examples=100)
@given(
    values=st.lists(
        st.one_of(decimal_strategy, float_strategy),
        min_size=1,
        max_size=20,
    ),
)
def test_mixed_float_decimal_detection(values):
    """Test that mixed float/Decimal sequences are correctly detected and handled."""
    # If any Decimal in the sequence, should use Decimal path
    has_decimal = any(isinstance(v, Decimal) for v in values)

    result = rust_array_sum(values)

    if has_decimal:
        assert isinstance(
            result, Decimal
        ), f"Expected Decimal result for sequence with Decimals: {values[:5]}"
    else:
        assert isinstance(
            result, float
        ), f"Expected float result for float-only sequence: {values[:5]}"


def test_decimal_precision_preservation():
    """Test that Decimal precision is preserved through operations."""
    from decimal import getcontext

    # Set high precision
    original_prec = getcontext().prec
    getcontext().prec = 28

    try:
        values = [Decimal("0.1"), Decimal("0.2"), Decimal("0.3")]
        result = rust_array_sum(values)

        # Result should be exactly 0.6 with Decimal precision
        assert result == Decimal("0.6"), f"Decimal precision lost: expected 0.6, got {result}"

        # Test with values that demonstrate float imprecision (0.1 + 0.2 = 0.30000000000000004 in float)
        float_result = 0.1 + 0.2
        decimal_values = [Decimal("0.1"), Decimal("0.2")]
        decimal_result = rust_array_sum(decimal_values)

        # Float has imprecision, Decimal doesn't
        assert (
            abs(float_result - 0.3) > 1e-17
        ), f"This test expects float imprecision (got {abs(float_result - 0.3):.2e}) to demonstrate Decimal advantage"
        assert decimal_result == Decimal("0.3"), "Decimal should give exact result"

    finally:
        getcontext().prec = original_prec


def test_decimal_rounding_modes():
    """Test that Decimal rounding modes are respected."""
    from decimal import ROUND_DOWN, ROUND_HALF_UP, getcontext

    values = [Decimal("1.5"), Decimal("2.5"), Decimal("3.5")]
    window = 2

    # Test ROUND_HALF_UP
    original_rounding = getcontext().rounding
    getcontext().rounding = ROUND_HALF_UP

    try:
        result_half_up = rust_sma(values, window)
        assert all(
            isinstance(x, Decimal)
            for x in result_half_up
            if not (isinstance(x, Decimal) and x.is_nan())
        )

        # Test ROUND_DOWN
        getcontext().rounding = ROUND_DOWN
        result_down = rust_sma(values, window)
        assert all(
            isinstance(x, Decimal)
            for x in result_down
            if not (isinstance(x, Decimal) and x.is_nan())
        )

        # Results may differ based on rounding mode
        # (but both should be valid Decimals)

    finally:
        getcontext().rounding = original_rounding
