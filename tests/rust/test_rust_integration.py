"""
Tests for Rust integration with Python via PyO3.

These tests validate the Python → Rust → Python roundtrip works correctly.
"""

import pytest

pytestmark = pytest.mark.rust


def test_import_rust_sum():
    """Test that rust_sum can be imported from rustybt package."""
    from rustybt import rust_sum

    assert rust_sum is not None
    assert callable(rust_sum)


def test_rust_sum_basic():
    """Test basic rust_sum functionality with positive integers."""
    from rustybt import rust_sum

    result = rust_sum(2, 3)
    assert result == 5
    assert isinstance(result, int)


def test_rust_sum_negative():
    """Test rust_sum with negative numbers."""
    from rustybt import rust_sum

    result = rust_sum(-10, 5)
    assert result == -5


def test_rust_sum_zero():
    """Test rust_sum with zero values (edge case)."""
    from rustybt import rust_sum

    assert rust_sum(0, 0) == 0
    assert rust_sum(10, 0) == 10
    assert rust_sum(0, -5) == -5


def test_rust_sum_large_integers():
    """Test rust_sum with large integers (i64 range)."""
    from rustybt import rust_sum

    # Test with large positive numbers
    large_a = 2**60
    large_b = 1000
    result = rust_sum(large_a, large_b)
    assert result == large_a + large_b

    # Test with large negative numbers
    large_neg = -(2**60)
    result = rust_sum(large_neg, 500)
    assert result == large_neg + 500


def test_rust_sum_type_error_float():
    """Test that rust_sum raises TypeError for float inputs."""
    from rustybt import rust_sum

    with pytest.raises(TypeError):
        rust_sum(2.5, 3.5)  # type: ignore[arg-type]


def test_rust_sum_type_error_string():
    """Test that rust_sum raises TypeError for string inputs."""
    from rustybt import rust_sum

    with pytest.raises(TypeError):
        rust_sum("2", "3")  # type: ignore[arg-type]


def test_rust_sum_type_error_mixed():
    """Test that rust_sum raises TypeError for mixed type inputs."""
    from rustybt import rust_sum

    with pytest.raises(TypeError):
        rust_sum(2, "3")  # type: ignore[arg-type]

    with pytest.raises(TypeError):
        rust_sum(2.5, 3)  # type: ignore[arg-type]


def test_rust_sum_overflow():
    """Test rust_sum behavior with potential overflow.

    Note: Rust i64 addition wraps on overflow in release mode,
    or panics in debug mode. This test documents the behavior.
    """
    from rustybt import rust_sum

    # Test near i64::MAX (9223372036854775807)
    max_i64 = 2**63 - 1

    # This should work without overflow
    result = rust_sum(max_i64 - 1000, 500)
    assert result == max_i64 - 500

    # Actual overflow would wrap or panic depending on build mode
    # We don't test this to avoid platform-specific behavior


def test_rust_extension_availability():
    """Test that _RUST_AVAILABLE flag is set correctly."""
    import rustybt

    assert hasattr(rustybt, "_RUST_AVAILABLE")
    assert rustybt._RUST_AVAILABLE is True
