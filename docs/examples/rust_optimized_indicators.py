"""Example: Using Rust-Optimized Indicators

This example demonstrates how to use Rust-optimized technical indicators
in your trading strategies for improved performance.

The Rust optimizations are transparent - they automatically fall back to
Python if Rust extensions are not available.
"""

import time

from rustybt.rust_optimizations import (
    RUST_AVAILABLE,
    rust_ema,
    rust_pairwise_op,
    rust_sma,
)


def generate_sample_prices(n=1000):
    """Generate sample price data for demonstration."""
    # Simulate price data: starting at 100, random walk
    import random

    random.seed(42)

    prices = [100.0]
    for _ in range(n - 1):
        change = random.uniform(-2.0, 2.0)
        prices.append(max(prices[-1] + change, 1.0))

    return prices


def calculate_indicators_rust(prices, short_window=20, long_window=50):
    """Calculate indicators using Rust optimizations.

    Args:
        prices: List of price values
        short_window: Short moving average window
        long_window: Long moving average window

    Returns:
        Dictionary with indicator values
    """
    # Calculate SMAs using Rust
    sma_short = rust_sma(prices, short_window)
    sma_long = rust_sma(prices, long_window)

    # Calculate EMAs using Rust
    ema_short = rust_ema(prices, short_window)
    ema_long = rust_ema(prices, long_window)

    # Calculate crossover signals using Rust pairwise operations
    sma_diff = rust_pairwise_op(sma_short, sma_long, "sub")
    ema_diff = rust_pairwise_op(ema_short, ema_long, "sub")

    return {
        "sma_short": sma_short,
        "sma_long": sma_long,
        "ema_short": ema_short,
        "ema_long": ema_long,
        "sma_crossover": sma_diff,
        "ema_crossover": ema_diff,
    }


def calculate_indicators_python(prices, short_window=20, long_window=50):
    """Calculate indicators using pure Python (for comparison).

    Args:
        prices: List of price values
        short_window: Short moving average window
        long_window: Long moving average window

    Returns:
        Dictionary with indicator values
    """

    # Pure Python SMA
    def python_sma(values, window):
        result = [float("nan")] * len(values)
        if len(values) >= window:
            result[window - 1] = sum(values[:window]) / window
            for i in range(window, len(values)):
                result[i] = result[i - 1] + (values[i] - values[i - window]) / window
        return result

    # Pure Python EMA
    def python_ema(values, span):
        result = [0.0] * len(values)
        alpha = 2.0 / (span + 1.0)
        result[0] = values[0]
        for i in range(1, len(values)):
            result[i] = alpha * values[i] + (1.0 - alpha) * result[i - 1]
        return result

    sma_short = python_sma(prices, short_window)
    sma_long = python_sma(prices, long_window)
    ema_short = python_ema(prices, short_window)
    ema_long = python_ema(prices, long_window)

    sma_diff = [s - l for s, l in zip(sma_short, sma_long, strict=False)]
    ema_diff = [s - l for s, l in zip(ema_short, ema_long, strict=False)]

    return {
        "sma_short": sma_short,
        "sma_long": sma_long,
        "ema_short": ema_short,
        "ema_long": ema_long,
        "sma_crossover": sma_diff,
        "ema_crossover": ema_diff,
    }


def benchmark_performance(n_prices=10000, iterations=100):
    """Benchmark Rust vs Python performance."""
    prices = generate_sample_prices(n_prices)

    print(f"Benchmarking with {n_prices} prices, {iterations} iterations...\n")

    # Benchmark Python
    start = time.perf_counter()
    for _ in range(iterations):
        calculate_indicators_python(prices)
    python_time = time.perf_counter() - start

    print(
        f"Python implementation: {python_time:.4f}s ({python_time / iterations * 1000:.2f}ms per iteration)"
    )

    if RUST_AVAILABLE:
        # Benchmark Rust
        start = time.perf_counter()
        for _ in range(iterations):
            calculate_indicators_rust(prices)
        rust_time = time.perf_counter() - start

        speedup = python_time / rust_time
        print(
            f"Rust implementation:   {rust_time:.4f}s ({rust_time / iterations * 1000:.2f}ms per iteration)"
        )
        print(f"\nSpeedup: {speedup:.2f}x faster with Rust optimizations! 🚀")
    else:
        print("Rust optimizations not available (using Python fallback)")


def example_strategy_usage():
    """Example of using Rust-optimized indicators in a strategy."""
    print("\n" + "=" * 60)
    print("EXAMPLE: SMA Crossover Strategy with Rust Optimizations")
    print("=" * 60 + "\n")

    # Generate sample data
    prices = generate_sample_prices(500)

    # Calculate indicators using Rust optimizations
    indicators = calculate_indicators_rust(prices, short_window=50, long_window=200)

    # Generate trading signals
    signals = []
    for i in range(len(indicators["sma_crossover"])):
        crossover = indicators["sma_crossover"][i]
        if i > 0:
            prev_crossover = indicators["sma_crossover"][i - 1]

            # Golden cross: short SMA crosses above long SMA
            if prev_crossover < 0 and crossover > 0:
                signals.append((i, "BUY", prices[i]))

            # Death cross: short SMA crosses below long SMA
            elif prev_crossover > 0 and crossover < 0:
                signals.append((i, "SELL", prices[i]))

    print(f"Generated {len(signals)} trading signals")
    print("\nFirst 5 signals:")
    for idx, action, price in signals[:5]:
        print(f"  Day {idx}: {action} at ${price:.2f}")

    print(
        f"\nRust optimizations: {'ENABLED ✓' if RUST_AVAILABLE else 'DISABLED (using Python fallback)'}"
    )


def main():
    """Run example demonstrations."""
    print("=" * 60)
    print("Rust-Optimized Indicators Example")
    print("=" * 60 + "\n")

    # Show optimization status
    if RUST_AVAILABLE:
        print("✓ Rust optimizations are AVAILABLE and LOADED")
        print("  All indicator calculations will use Rust-accelerated functions\n")
    else:
        print("✗ Rust optimizations NOT available")
        print("  Falling back to pure Python implementations\n")

    # Run strategy example
    example_strategy_usage()

    # Run performance benchmark
    print("\n" + "=" * 60)
    print("PERFORMANCE BENCHMARK")
    print("=" * 60 + "\n")
    benchmark_performance(n_prices=10000, iterations=100)

    print("\n" + "=" * 60)
    print("Example complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
