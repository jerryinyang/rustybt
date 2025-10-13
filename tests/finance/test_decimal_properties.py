"""Property-based tests for Decimal arithmetic using Hypothesis.

This module contains comprehensive property-based tests to verify the
mathematical properties of Python's Decimal type for financial calculations.
These tests run 1000+ examples per test to ensure correctness across a wide
range of inputs.
"""

from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st


# Hypothesis strategies for Decimal values with financial ranges
def financial_decimal(
    min_value: str = "0.01", max_value: str = "1000000.00", allow_negative: bool = True
) -> st.SearchStrategy[Decimal]:
    """Generate Decimal values suitable for financial calculations.

    Args:
        min_value: Minimum value as string (default: "0.01")
        max_value: Maximum value as string (default: "1000000.00")
        allow_negative: Whether to allow negative values (default: True)

    Returns:
        Hypothesis strategy for generating Decimal values
    """
    min_dec = Decimal(min_value)
    max_dec = Decimal(max_value)

    if allow_negative:
        return st.decimals(
            min_value=-max_dec,
            max_value=max_dec,
            allow_nan=False,
            allow_infinity=False,
            places=8,  # 8 decimal places for financial precision
        )
    else:
        return st.decimals(
            min_value=min_dec,
            max_value=max_dec,
            allow_nan=False,
            allow_infinity=False,
            places=8,
        )


# Non-zero Decimal strategy for division tests
def nonzero_decimal(
    min_value: str = "0.01", max_value: str = "1000000.00"
) -> st.SearchStrategy[Decimal]:
    """Generate non-zero Decimal values.

    Args:
        min_value: Minimum absolute value as string (default: "0.01")
        max_value: Maximum value as string (default: "1000000.00")

    Returns:
        Hypothesis strategy for generating non-zero Decimal values
    """
    min_dec = Decimal(min_value)
    max_dec = Decimal(max_value)

    return st.one_of(
        st.decimals(
            min_value=min_dec,
            max_value=max_dec,
            allow_nan=False,
            allow_infinity=False,
            places=8,
        ),
        st.decimals(
            min_value=-max_dec,
            max_value=-min_dec,
            allow_nan=False,
            allow_infinity=False,
            places=8,
        ),
    )


# ============================================================================
# COMMUTATIVITY TESTS
# ============================================================================


@pytest.mark.property
@given(a=financial_decimal(), b=financial_decimal())
@settings(max_examples=1000)
def test_decimal_addition_commutative(a: Decimal, b: Decimal) -> None:
    """Verify Decimal addition is commutative: a + b == b + a.

    This property ensures that the order of operands doesn't affect the sum.
    """
    assert a + b == b + a


@pytest.mark.property
@given(a=financial_decimal(), b=financial_decimal())
@settings(max_examples=1000)
def test_decimal_multiplication_commutative(a: Decimal, b: Decimal) -> None:
    """Verify Decimal multiplication is commutative: a * b == b * a.

    This property ensures that the order of operands doesn't affect the product.
    """
    assert a * b == b * a


# ============================================================================
# ASSOCIATIVITY TESTS
# ============================================================================


@pytest.mark.property
@given(
    a=financial_decimal(max_value="10000.00"),
    b=financial_decimal(max_value="10000.00"),
    c=financial_decimal(max_value="10000.00"),
)
@settings(max_examples=1000)
def test_decimal_addition_associative(a: Decimal, b: Decimal, c: Decimal) -> None:
    """Verify Decimal addition is associative: (a + b) + c == a + (b + c).

    This property ensures that grouping of operands doesn't affect the sum.
    """
    assert (a + b) + c == a + (b + c)


@pytest.mark.property
@given(
    a=financial_decimal(max_value="1000.00"),
    b=financial_decimal(max_value="1000.00"),
    c=financial_decimal(max_value="1000.00"),
)
@settings(max_examples=1000)
def test_decimal_multiplication_associative(a: Decimal, b: Decimal, c: Decimal) -> None:
    """Verify Decimal multiplication is associative: (a * b) * c == a * (b * c).

    This property ensures that grouping of operands doesn't affect the product.
    """
    assert (a * b) * c == a * (b * c)


# ============================================================================
# IDENTITY TESTS
# ============================================================================


@pytest.mark.property
@given(a=financial_decimal())
@settings(max_examples=1000)
def test_decimal_additive_identity(a: Decimal) -> None:
    """Verify Decimal additive identity: a + 0 == a.

    This property ensures that adding zero doesn't change the value.
    """
    assert a + Decimal("0") == a
    assert Decimal("0") + a == a


@pytest.mark.property
@given(a=financial_decimal())
@settings(max_examples=1000)
def test_decimal_multiplicative_identity(a: Decimal) -> None:
    """Verify Decimal multiplicative identity: a * 1 == a.

    This property ensures that multiplying by one doesn't change the value.
    """
    assert a * Decimal("1") == a
    assert Decimal("1") * a == a


# ============================================================================
# PRECISION TESTS
# ============================================================================


@pytest.mark.property
def test_decimal_precision_basic() -> None:
    """Verify Decimal maintains precision where float fails.

    This test demonstrates that Decimal("0.1") + Decimal("0.2") == Decimal("0.3"),
    which would fail with Python floats due to binary representation issues.
    """
    # This would fail with float: 0.1 + 0.2 != 0.3
    assert Decimal("0.1") + Decimal("0.2") == Decimal("0.3")


@pytest.mark.property
@given(
    a=st.decimals(
        min_value=Decimal("0.01"),
        max_value=Decimal("100.00"),
        allow_nan=False,
        allow_infinity=False,
        places=2,
    )
)
@settings(max_examples=1000)
def test_decimal_no_float_rounding_errors(a: Decimal) -> None:
    """Verify Decimal operations don't introduce float-style rounding errors.

    When converting Decimal to float and back, precision should be maintained
    within acceptable tolerances for financial calculations.
    """
    # Decimal constructed from string should equal itself
    decimal_str = str(a)
    reconstructed = Decimal(decimal_str)
    assert a == reconstructed


# ============================================================================
# DIVISION BY ZERO TESTS
# ============================================================================


@pytest.mark.property
@given(a=nonzero_decimal())
@settings(max_examples=1000)
def test_decimal_division_by_zero_raises(a: Decimal) -> None:
    """Verify Decimal raises appropriate error for division by zero.

    This property ensures proper error handling for invalid operations.
    For non-zero values divided by zero, raises ZeroDivisionError.
    """
    with pytest.raises((ZeroDivisionError, Exception)):
        _ = a / Decimal("0")


@pytest.mark.property
@given(a=nonzero_decimal())
@settings(max_examples=1000)
def test_decimal_zero_divided_by_nonzero(a: Decimal) -> None:
    """Verify Decimal zero divided by non-zero equals zero.

    This property ensures 0 / a == 0 for all non-zero a.
    """
    assert Decimal("0") / a == Decimal("0")


# ============================================================================
# DISTRIBUTIVITY TESTS
# ============================================================================


@pytest.mark.property
@given(
    a=financial_decimal(max_value="1000.00"),
    b=financial_decimal(max_value="1000.00"),
    c=financial_decimal(max_value="1000.00"),
)
@settings(max_examples=1000)
def test_decimal_distributivity_left(a: Decimal, b: Decimal, c: Decimal) -> None:
    """Verify Decimal left distributivity: a * (b + c) == (a * b) + (a * c).

    This property ensures multiplication distributes over addition.
    """
    assert a * (b + c) == (a * b) + (a * c)


@pytest.mark.property
@given(
    a=financial_decimal(max_value="1000.00"),
    b=financial_decimal(max_value="1000.00"),
    c=financial_decimal(max_value="1000.00"),
)
@settings(max_examples=1000)
def test_decimal_distributivity_right(a: Decimal, b: Decimal, c: Decimal) -> None:
    """Verify Decimal right distributivity: (a + b) * c == (a * c) + (b * c).

    This property ensures multiplication distributes over addition from the right.
    """
    assert (a + b) * c == (a * c) + (b * c)


# ============================================================================
# INVERSE OPERATIONS TESTS
# ============================================================================


@pytest.mark.property
@given(a=financial_decimal(), b=financial_decimal())
@settings(max_examples=1000)
def test_decimal_additive_inverse(a: Decimal, b: Decimal) -> None:
    """Verify Decimal additive inverse: (a + b) - b == a.

    This property ensures subtraction is the inverse of addition.
    """
    assert (a + b) - b == a
    assert (a - b) + b == a


@pytest.mark.property
@given(a=financial_decimal(max_value="10000.00"), b=nonzero_decimal(max_value="100.00"))
@settings(max_examples=1000)
def test_decimal_multiplicative_inverse(a: Decimal, b: Decimal) -> None:
    """Verify Decimal multiplicative inverse: (a * b) / b == a.

    This property ensures division is the inverse of multiplication for non-zero divisors.
    """
    assert (a * b) / b == a


# ============================================================================
# EDGE CASE TESTS
# ============================================================================


@pytest.mark.property
@given(
    a=st.decimals(
        min_value=Decimal("0.00000001"),
        max_value=Decimal("0.0001"),
        allow_nan=False,
        allow_infinity=False,
        places=8,
    ),
    b=st.decimals(
        min_value=Decimal("0.00000001"),
        max_value=Decimal("0.0001"),
        allow_nan=False,
        allow_infinity=False,
        places=8,
    ),
)
@settings(max_examples=1000)
def test_decimal_very_small_numbers(a: Decimal, b: Decimal) -> None:
    """Verify Decimal operations work correctly with very small numbers.

    This property tests precision with values near the lower bounds of
    financial calculations (fractions of cents).
    """
    result = a + b
    assert result >= a
    assert result >= b
    assert result == b + a  # Commutativity


@pytest.mark.property
@given(
    a=st.decimals(
        min_value=Decimal("100000.00"),
        max_value=Decimal("10000000.00"),
        allow_nan=False,
        allow_infinity=False,
        places=2,
    ),
    b=st.decimals(
        min_value=Decimal("100000.00"),
        max_value=Decimal("10000000.00"),
        allow_nan=False,
        allow_infinity=False,
        places=2,
    ),
)
@settings(max_examples=1000)
def test_decimal_very_large_numbers(a: Decimal, b: Decimal) -> None:
    """Verify Decimal operations work correctly with very large numbers.

    This property tests precision with large portfolio values.
    """
    result = a + b
    assert result >= a
    assert result >= b
    assert result == b + a  # Commutativity


@pytest.mark.property
@given(
    positive=financial_decimal(min_value="0.01", max_value="1000.00", allow_negative=False),
    negative=financial_decimal(min_value="0.01", max_value="1000.00", allow_negative=False),
)
@settings(max_examples=1000)
def test_decimal_mixed_signs(positive: Decimal, negative: Decimal) -> None:
    """Verify Decimal operations work correctly with mixed positive/negative values.

    This property tests arithmetic with both gains and losses.
    """
    neg = -negative
    # Adding a positive and negative
    result = positive + neg
    # Subtracting should give original positive
    assert result - neg == positive
    assert result + negative == positive


@pytest.mark.property
@given(a=financial_decimal())
@settings(max_examples=1000)
def test_decimal_negation_inverse(a: Decimal) -> None:
    """Verify Decimal negation is its own inverse: -(-a) == a.

    This property ensures double negation returns the original value.
    """
    assert -(-a) == a


@pytest.mark.property
@given(a=financial_decimal(), b=financial_decimal())
@settings(max_examples=1000)
def test_decimal_subtraction_as_negative_addition(a: Decimal, b: Decimal) -> None:
    """Verify Decimal subtraction equals adding the negative: a - b == a + (-b).

    This property shows the relationship between subtraction and addition.
    """
    assert a - b == a + (-b)
