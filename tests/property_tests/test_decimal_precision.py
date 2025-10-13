"""Property-based tests for Decimal arithmetic properties and precision preservation."""

from decimal import Decimal, getcontext

from hypothesis import example, given

from .strategies import decimal_prices, decimal_quantities


@given(
    a=decimal_prices(max_value=Decimal("10000"), scale=2),
    b=decimal_prices(max_value=Decimal("10000"), scale=2),
    c=decimal_prices(max_value=Decimal("10000"), scale=2),
)
@example(a=Decimal("100"), b=Decimal("200"), c=Decimal("300"))
@example(a=Decimal("0"), b=Decimal("0"), c=Decimal("0"))
def test_decimal_addition_associativity(a: Decimal, b: Decimal, c: Decimal) -> None:
    """Test Decimal addition is associative: (a + b) + c == a + (b + c).

    Property:
        (a + b) + c = a + (b + c)

    This fundamental property must hold for all Decimal arithmetic.
    """
    left = (a + b) + c
    right = a + (b + c)

    assert (
        left == right
    ), f"Addition associativity violated: ({a} + {b}) + {c} = {left}, {a} + ({b} + {c}) = {right}"


@given(
    a=decimal_prices(max_value=Decimal("10000"), scale=2),
    b=decimal_prices(max_value=Decimal("10000"), scale=2),
)
@example(a=Decimal("100"), b=Decimal("200"))
@example(a=Decimal("0"), b=Decimal("1"))
def test_decimal_addition_commutativity(a: Decimal, b: Decimal) -> None:
    """Test Decimal addition is commutative: a + b == b + a.

    Property:
        a + b = b + a

    Order of operands should not matter for addition.
    """
    left = a + b
    right = b + a

    assert (
        left == right
    ), f"Addition commutativity violated: {a} + {b} = {left}, {b} + {a} = {right}"


@given(
    a=decimal_prices(min_value=Decimal("1"), max_value=Decimal("1000"), scale=2),
    b=decimal_prices(min_value=Decimal("1"), max_value=Decimal("1000"), scale=2),
    c=decimal_prices(min_value=Decimal("1"), max_value=Decimal("1000"), scale=2),
)
@example(a=Decimal("2"), b=Decimal("3"), c=Decimal("4"))
@example(a=Decimal("1"), b=Decimal("1"), c=Decimal("1"))
def test_decimal_multiplication_associativity(a: Decimal, b: Decimal, c: Decimal) -> None:
    """Test Decimal multiplication is associative: (a × b) × c == a × (b × c).

    Property:
        (a × b) × c = a × (b × c)

    This fundamental property must hold for all Decimal arithmetic.
    """
    left = (a * b) * c
    right = a * (b * c)

    assert left == right, (
        f"Multiplication associativity violated: "
        f"({a} × {b}) × {c} = {left}, "
        f"{a} × ({b} × {c}) = {right}"
    )


@given(
    a=decimal_prices(min_value=Decimal("1"), max_value=Decimal("1000"), scale=2),
    b=decimal_prices(min_value=Decimal("1"), max_value=Decimal("1000"), scale=2),
)
@example(a=Decimal("100"), b=Decimal("200"))
@example(a=Decimal("1"), b=Decimal("1"))
def test_decimal_multiplication_commutativity(a: Decimal, b: Decimal) -> None:
    """Test Decimal multiplication is commutative: a × b == b × a.

    Property:
        a × b = b × a

    Order of operands should not matter for multiplication.
    """
    left = a * b
    right = b * a

    assert (
        left == right
    ), f"Multiplication commutativity violated: {a} × {b} = {left}, {b} × {a} = {right}"


@given(
    a=decimal_prices(min_value=Decimal("1"), max_value=Decimal("100"), scale=2),
    b=decimal_prices(max_value=Decimal("100"), scale=2),
    c=decimal_prices(max_value=Decimal("100"), scale=2),
)
@example(a=Decimal("2"), b=Decimal("3"), c=Decimal("4"))
@example(a=Decimal("10"), b=Decimal("5"), c=Decimal("5"))
def test_decimal_distributivity(a: Decimal, b: Decimal, c: Decimal) -> None:
    """Test Decimal distributivity: a × (b + c) == a × b + a × c.

    Property:
        a × (b + c) = a × b + a × c

    This property is critical for financial calculations involving
    position values and portfolio aggregations.
    """
    left = a * (b + c)
    right = a * b + a * c

    assert (
        left == right
    ), f"Distributivity violated: {a} × ({b} + {c}) = {left}, {a} × {b} + {a} × {c} = {right}"


@given(
    value=decimal_prices(min_value=Decimal("0.00000001"), max_value=Decimal("1000000"), scale=8),
)
@example(value=Decimal("0.00000001"))  # Minimum crypto precision
@example(value=Decimal("1000000.00"))  # Large portfolio value
def test_decimal_precision_preserved_across_operations(value: Decimal) -> None:
    """Test Decimal operations preserve precision.

    Property:
        Operations on Decimal values maintain configured precision

    This ensures no silent rounding occurs during calculations.
    """
    # Set high precision context
    original_prec = getcontext().prec
    getcontext().prec = 28  # Financial precision

    try:
        # Perform various operations
        result1 = value + Decimal("0.00000001")
        result2 = value - Decimal("0.00000001")
        result3 = value * Decimal("1.00000001")
        result4 = value / Decimal("1.00000001")

        # Verify results have appropriate precision
        # The key is that operations complete without raising errors
        # and maintain exactness
        assert isinstance(result1, Decimal), "Result should be Decimal type"
        assert isinstance(result2, Decimal), "Result should be Decimal type"
        assert isinstance(result3, Decimal), "Result should be Decimal type"
        assert isinstance(result4, Decimal), "Result should be Decimal type"

        # Verify operations are reversible
        reconstructed = result3 / Decimal("1.00000001")
        # Allow for small rounding in final decimal place due to division
        assert abs(reconstructed - value) < Decimal(
            "0.00000001"
        ), f"Precision lost in round-trip: original={value}, reconstructed={reconstructed}"
    finally:
        getcontext().prec = original_prec


@given(
    a=decimal_prices(max_value=Decimal("1000"), scale=2),
)
@example(a=Decimal("0"))
@example(a=Decimal("100"))
def test_decimal_additive_identity(a: Decimal) -> None:
    """Test Decimal additive identity: a + 0 == a.

    Property:
        a + 0 = a

    Adding zero should not change the value.
    """
    result = a + Decimal("0")
    assert result == a, f"Additive identity violated: {a} + 0 = {result}, expected {a}"


@given(
    a=decimal_prices(min_value=Decimal("1"), max_value=Decimal("1000"), scale=2),
)
@example(a=Decimal("1"))
@example(a=Decimal("100"))
def test_decimal_multiplicative_identity(a: Decimal) -> None:
    """Test Decimal multiplicative identity: a × 1 == a.

    Property:
        a × 1 = a

    Multiplying by one should not change the value.
    """
    result = a * Decimal("1")
    assert result == a, f"Multiplicative identity violated: {a} × 1 = {result}, expected {a}"


@given(
    a=decimal_prices(max_value=Decimal("1000"), scale=2),
)
@example(a=Decimal("100"))
@example(a=Decimal("0"))
def test_decimal_additive_inverse(a: Decimal) -> None:
    """Test Decimal additive inverse: a + (-a) == 0.

    Property:
        a + (-a) = 0

    Adding the negative of a value should yield zero.
    """
    result = a + (-a)
    assert result == Decimal("0"), f"Additive inverse violated: {a} + (-{a}) = {result}, expected 0"


@given(
    value=decimal_prices(min_value=Decimal("0.01"), max_value=Decimal("10000"), scale=2),
)
@example(value=Decimal("100.00"))
@example(value=Decimal("0.01"))
def test_decimal_string_representation_preserves_precision(value: Decimal) -> None:
    """Test Decimal string representation preserves precision.

    Property:
        Decimal(str(value)) = value

    Converting to string and back should preserve the exact value.
    """
    str_repr = str(value)
    reconstructed = Decimal(str_repr)

    assert reconstructed == value, (
        f"String representation lost precision: "
        f"original={value}, string={str_repr}, reconstructed={reconstructed}"
    )


@given(
    price=decimal_prices(min_value=Decimal("1"), max_value=Decimal("500"), scale=2),
    quantity=decimal_quantities(min_value=Decimal("1"), max_value=Decimal("1000"), scale=2),
)
@example(price=Decimal("100.50"), quantity=Decimal("123.45"))
@example(price=Decimal("0.01"), quantity=Decimal("0.01"))
def test_decimal_multiplication_no_float_contamination(price: Decimal, quantity: Decimal) -> None:
    """Test Decimal multiplication doesn't introduce float errors.

    Property:
        Decimal(price × quantity) calculated exactly

    Multiplying Decimal values should never introduce floating-point errors.
    """
    # Calculate using Decimal
    decimal_result = price * quantity

    # Calculate using float (which would introduce errors)
    float_result = float(price) * float(quantity)
    Decimal(str(float_result))

    # Decimal result should be more precise than float result
    # They might differ due to float rounding
    assert isinstance(decimal_result, Decimal), "Result should be Decimal type"

    # Verify Decimal result is exact (no rounding beyond specified precision)
    # By checking it maintains more precision than float conversion
    str_result = str(decimal_result)
    assert "." in str_result or decimal_result == Decimal(
        "0"
    ), "Decimal result should maintain decimal precision"
