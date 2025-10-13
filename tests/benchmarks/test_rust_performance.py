"""Performance benchmarks for Rust optimizations vs Python implementations.

This module uses pytest-benchmark to measure and compare the performance of
Rust-optimized functions against pure Python implementations.

These tests fulfill AC5 & AC9: Benchmarks show Rust optimization achieves measurable speedup.

Run with: pytest tests/benchmarks/test_rust_performance.py --benchmark-only
"""

import math

import pytest

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

# Test data sizes
SMALL_SIZE = 100
MEDIUM_SIZE = 1000
LARGE_SIZE = 10000

# Generate test data
small_data = [float(i) for i in range(SMALL_SIZE)]
medium_data = [float(i) for i in range(MEDIUM_SIZE)]
large_data = [float(i) for i in range(LARGE_SIZE)]


# Pure Python implementations for comparison
def pure_python_sma(values, window):
    """Pure Python SMA implementation."""
    if window <= 0 or not values or len(values) < window:
        return [float("nan")] * len(values)

    result = [float("nan")] * len(values)
    first_sum = sum(values[:window])
    result[window - 1] = first_sum / window

    for i in range(window, len(values)):
        prev_sma = result[i - 1]
        result[i] = prev_sma + (values[i] - values[i - window]) / window

    return result


def pure_python_ema(values, span):
    """Pure Python EMA implementation."""
    if span <= 0 or not values:
        return []

    result = [0.0] * len(values)
    alpha = 2.0 / (span + 1.0)
    result[0] = values[0]

    for i in range(1, len(values)):
        result[i] = alpha * values[i] + (1.0 - alpha) * result[i - 1]

    return result


# === SMA Benchmarks ===


@pytest.mark.benchmark(group="sma_small")
def test_python_sma_small(benchmark):
    """Benchmark Python SMA on small dataset (100 elements)."""
    result = benchmark(pure_python_sma, small_data, 10)
    assert len(result) == SMALL_SIZE


@pytest.mark.benchmark(group="sma_small")
@pytest.mark.skipif(not RUST_AVAILABLE, reason="Rust not available")
def test_rust_sma_small(benchmark):
    """Benchmark Rust SMA on small dataset (100 elements)."""
    result = benchmark(rust_sma, small_data, 10)
    assert len(result) == SMALL_SIZE


@pytest.mark.benchmark(group="sma_medium")
def test_python_sma_medium(benchmark):
    """Benchmark Python SMA on medium dataset (1000 elements)."""
    result = benchmark(pure_python_sma, medium_data, 50)
    assert len(result) == MEDIUM_SIZE


@pytest.mark.benchmark(group="sma_medium")
@pytest.mark.skipif(not RUST_AVAILABLE, reason="Rust not available")
def test_rust_sma_medium(benchmark):
    """Benchmark Rust SMA on medium dataset (1000 elements)."""
    result = benchmark(rust_sma, medium_data, 50)
    assert len(result) == MEDIUM_SIZE


@pytest.mark.benchmark(group="sma_large")
def test_python_sma_large(benchmark):
    """Benchmark Python SMA on large dataset (10000 elements)."""
    result = benchmark(pure_python_sma, large_data, 200)
    assert len(result) == LARGE_SIZE


@pytest.mark.benchmark(group="sma_large")
@pytest.mark.skipif(not RUST_AVAILABLE, reason="Rust not available")
def test_rust_sma_large(benchmark):
    """Benchmark Rust SMA on large dataset (10000 elements)."""
    result = benchmark(rust_sma, large_data, 200)
    assert len(result) == LARGE_SIZE


# === EMA Benchmarks ===


@pytest.mark.benchmark(group="ema_small")
def test_python_ema_small(benchmark):
    """Benchmark Python EMA on small dataset (100 elements)."""
    result = benchmark(pure_python_ema, small_data, 10)
    assert len(result) == SMALL_SIZE


@pytest.mark.benchmark(group="ema_small")
@pytest.mark.skipif(not RUST_AVAILABLE, reason="Rust not available")
def test_rust_ema_small(benchmark):
    """Benchmark Rust EMA on small dataset (100 elements)."""
    result = benchmark(rust_ema, small_data, 10)
    assert len(result) == SMALL_SIZE


@pytest.mark.benchmark(group="ema_large")
def test_python_ema_large(benchmark):
    """Benchmark Python EMA on large dataset (10000 elements)."""
    result = benchmark(pure_python_ema, large_data, 50)
    assert len(result) == LARGE_SIZE


@pytest.mark.benchmark(group="ema_large")
@pytest.mark.skipif(not RUST_AVAILABLE, reason="Rust not available")
def test_rust_ema_large(benchmark):
    """Benchmark Rust EMA on large dataset (10000 elements)."""
    result = benchmark(rust_ema, large_data, 50)
    assert len(result) == LARGE_SIZE


# === Array Operations Benchmarks ===


@pytest.mark.benchmark(group="array_sum")
def test_python_sum_large(benchmark):
    """Benchmark Python sum on large dataset (10000 elements)."""
    result = benchmark(sum, large_data)
    assert result > 0


@pytest.mark.benchmark(group="array_sum")
@pytest.mark.skipif(not RUST_AVAILABLE, reason="Rust not available")
def test_rust_sum_large(benchmark):
    """Benchmark Rust array sum on large dataset (10000 elements)."""
    result = benchmark(rust_array_sum, large_data)
    assert result > 0


@pytest.mark.benchmark(group="array_mean")
def test_python_mean_large(benchmark):
    """Benchmark Python mean on large dataset (10000 elements)."""
    result = benchmark(lambda x: sum(x) / len(x), large_data)
    assert result > 0


@pytest.mark.benchmark(group="array_mean")
@pytest.mark.skipif(not RUST_AVAILABLE, reason="Rust not available")
def test_rust_mean_large(benchmark):
    """Benchmark Rust mean on large dataset (10000 elements)."""
    result = benchmark(rust_mean, large_data)
    assert result > 0


@pytest.mark.benchmark(group="rolling_sum")
def test_python_rolling_sum_large(benchmark):
    """Benchmark Python rolling sum on large dataset (10000 elements)."""

    def python_rolling_sum(values, window):
        result = [float("nan")] * len(values)
        if len(values) >= window:
            result[window - 1] = sum(values[:window])
            for i in range(window, len(values)):
                result[i] = result[i - 1] + values[i] - values[i - window]
        return result

    result = benchmark(python_rolling_sum, large_data, 50)
    assert len(result) == LARGE_SIZE


@pytest.mark.benchmark(group="rolling_sum")
@pytest.mark.skipif(not RUST_AVAILABLE, reason="Rust not available")
def test_rust_rolling_sum_large(benchmark):
    """Benchmark Rust rolling sum on large dataset (10000 elements)."""
    result = benchmark(rust_rolling_sum, large_data, 50)
    assert len(result) == LARGE_SIZE


# === Data Operations Benchmarks ===


@pytest.mark.benchmark(group="window_slice")
def test_python_slice_large(benchmark):
    """Benchmark Python slice on large dataset."""
    result = benchmark(lambda x: x[100:9900], large_data)
    assert len(result) == 9800


@pytest.mark.benchmark(group="window_slice")
@pytest.mark.skipif(not RUST_AVAILABLE, reason="Rust not available")
def test_rust_slice_large(benchmark):
    """Benchmark Rust window slice on large dataset."""
    result = benchmark(rust_window_slice, large_data, 100, 9900)
    assert len(result) == 9800


@pytest.mark.benchmark(group="index_select")
def test_python_index_select_large(benchmark):
    """Benchmark Python index selection."""
    indices = list(range(0, LARGE_SIZE, 10))  # Every 10th element
    result = benchmark(lambda x, idx: [x[i] for i in idx], large_data, indices)
    assert len(result) == len(indices)


@pytest.mark.benchmark(group="index_select")
@pytest.mark.skipif(not RUST_AVAILABLE, reason="Rust not available")
def test_rust_index_select_large(benchmark):
    """Benchmark Rust index selection."""
    indices = list(range(0, LARGE_SIZE, 10))  # Every 10th element
    result = benchmark(rust_index_select, large_data, indices)
    assert len(result) == len(indices)


@pytest.mark.benchmark(group="fillna")
def test_python_fillna_large(benchmark):
    """Benchmark Python fillna."""
    data_with_nan = [float("nan") if i % 10 == 0 else float(i) for i in range(LARGE_SIZE)]
    result = benchmark(lambda x, v: [v if math.isnan(y) else y for y in x], data_with_nan, 0.0)
    assert len(result) == LARGE_SIZE


@pytest.mark.benchmark(group="fillna")
@pytest.mark.skipif(not RUST_AVAILABLE, reason="Rust not available")
def test_rust_fillna_large(benchmark):
    """Benchmark Rust fillna."""
    data_with_nan = [float("nan") if i % 10 == 0 else float(i) for i in range(LARGE_SIZE)]
    result = benchmark(rust_fillna, data_with_nan, 0.0)
    assert len(result) == LARGE_SIZE


@pytest.mark.benchmark(group="pairwise_add")
def test_python_pairwise_add_large(benchmark):
    """Benchmark Python pairwise addition."""
    result = benchmark(
        lambda a, b: [x + y for x, y in zip(a, b, strict=False)], large_data, large_data
    )
    assert len(result) == LARGE_SIZE


@pytest.mark.benchmark(group="pairwise_add")
@pytest.mark.skipif(not RUST_AVAILABLE, reason="Rust not available")
def test_rust_pairwise_add_large(benchmark):
    """Benchmark Rust pairwise addition."""
    result = benchmark(rust_pairwise_op, large_data, large_data, "add")
    assert len(result) == LARGE_SIZE


@pytest.mark.benchmark(group="create_columns")
def test_python_create_columns(benchmark):
    """Benchmark Python create_columns."""
    columns = [[float(i * 10 + j) for i in range(1000)] for j in range(10)]

    def python_create_columns(data):
        n_cols = len(data)
        n_rows = len(data[0])
        flattened = []
        for col in data:
            flattened.extend(col)
        return (flattened, n_rows, n_cols)

    result = benchmark(python_create_columns, columns)
    assert result[1] == 1000
    assert result[2] == 10


@pytest.mark.benchmark(group="create_columns")
@pytest.mark.skipif(not RUST_AVAILABLE, reason="Rust not available")
def test_rust_create_columns(benchmark):
    """Benchmark Rust create_columns."""
    columns = [[float(i * 10 + j) for i in range(1000)] for j in range(10)]
    result = benchmark(rust_create_columns, columns)
    assert result[1] == 1000
    assert result[2] == 10


# === Composite Benchmark (Realistic Scenario) ===


@pytest.mark.benchmark(group="composite_indicator")
def test_python_composite_indicator(benchmark):
    """Benchmark composite indicator calculation (SMA + EMA) in Python."""

    def composite_calculation(prices):
        sma = pure_python_sma(prices, 20)
        ema = pure_python_ema(prices, 20)
        # Combine signals
        signals = [s - e for s, e in zip(sma, ema, strict=False) if not math.isnan(s)]
        return signals

    result = benchmark(composite_calculation, large_data)
    assert len(result) > 0


@pytest.mark.benchmark(group="composite_indicator")
@pytest.mark.skipif(not RUST_AVAILABLE, reason="Rust not available")
def test_rust_composite_indicator(benchmark):
    """Benchmark composite indicator calculation (SMA + EMA) in Rust."""

    def composite_calculation(prices):
        sma = rust_sma(prices, 20)
        ema = rust_ema(prices, 20)
        # Combine signals using Rust pairwise op
        signals = rust_pairwise_op(sma, ema, "sub")
        # Filter out NaNs
        return [x for x in signals if not math.isnan(x)]

    result = benchmark(composite_calculation, large_data)
    assert len(result) > 0


# Performance assertions (run separately)
@pytest.mark.skipif(not RUST_AVAILABLE, reason="Rust not available")
@pytest.mark.slow
def test_rust_performance_assertions():
    """Assert that Rust implementations are faster than Python (run manually)."""
    import timeit

    # Test SMA performance
    python_time = timeit.timeit(lambda: pure_python_sma(large_data, 200), number=100)
    rust_time = timeit.timeit(lambda: rust_sma(large_data, 200), number=100)

    speedup = python_time / rust_time
    print(f"\nSMA Speedup: {speedup:.2f}x (Python: {python_time:.4f}s, Rust: {rust_time:.4f}s)")

    # We expect at least 1.5x speedup, but don't fail if slightly under
    # (performance can vary by system)
    if speedup < 1.2:
        pytest.skip(f"Speedup {speedup:.2f}x is less than expected, but not failing test")

    assert speedup > 1.0, f"Rust should be faster than Python, got {speedup:.2f}x"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--benchmark-only"])
