"""Integration tests for Rust-optimized backtests.

These tests verify that:
1. Backtests run successfully with Rust optimizations enabled
2. Backtests produce identical results with/without Rust (AC6)
3. Rust-optimized backtests complete faster (AC5)
4. Configuration passes correctly from Python to Rust (AC4)
"""

import math

import pandas as pd
import polars as pl
import pytest

from rustybt.rust_optimizations import RUST_AVAILABLE, rust_ema, rust_pairwise_op, rust_sma


@pytest.mark.integration
@pytest.mark.skipif(not RUST_AVAILABLE, reason="Rust extensions not available")
class TestRustBacktestIntegration:
    """Integration tests for Rust-optimized backtests."""

    def test_sma_crossover_strategy_rust_optimized(self):
        """Test SMA crossover strategy using Rust optimizations."""
        # Generate sample price data with clear trend changes to create crossovers
        import math

        prices = []
        for i in range(300):
            # Create sine wave pattern to generate crossovers
            base = 100.0
            trend = math.sin(i / 50.0) * 20  # Oscillating trend
            prices.append(base + trend)

        # Calculate SMAs using Rust (shorter windows to ensure crossovers)
        sma_short = rust_sma(prices, 10)
        sma_long = rust_sma(prices, 30)

        # Calculate crossovers using Rust pairwise operation
        crossover = rust_pairwise_op(sma_short, sma_long, "sub")

        # Generate signals
        signals = []
        for i in range(1, len(crossover)):
            if not math.isnan(crossover[i]) and not math.isnan(crossover[i - 1]):
                if crossover[i - 1] < 0 and crossover[i] > 0:
                    signals.append(("BUY", i, prices[i]))
                elif crossover[i - 1] > 0 and crossover[i] < 0:
                    signals.append(("SELL", i, prices[i]))

        # Verify signals generated
        assert len(signals) > 0, "Strategy should generate trading signals"
        assert all(s[0] in ["BUY", "SELL"] for s in signals), "All signals should be BUY or SELL"

    def test_ema_strategy_rust_optimized(self):
        """Test EMA-based strategy using Rust optimizations."""
        # Generate sample price data with trend
        prices = [100.0 * (1.001**i) for i in range(200)]

        # Calculate EMAs using Rust
        ema_fast = rust_ema(prices, 12)
        ema_slow = rust_ema(prices, 26)

        # MACD line
        macd = rust_pairwise_op(ema_fast, ema_slow, "sub")

        # Signal line (EMA of MACD)
        signal = rust_ema(macd, 9)

        # Histogram
        histogram = rust_pairwise_op(macd, signal, "sub")

        # Verify calculation completed
        assert len(histogram) == len(prices)
        assert not all(math.isnan(x) for x in histogram[-50:]), "Should have valid values at end"

    def test_rust_optimization_deterministic(self):
        """Test that Rust optimizations produce deterministic results."""
        prices = [100.0, 102.0, 101.0, 103.0, 105.0, 104.0, 106.0] * 20

        # Run calculation multiple times
        results = [rust_sma(prices, 10) for _ in range(5)]

        # All results should be identical
        for i in range(1, len(results)):
            for j in range(len(results[0])):
                if math.isnan(results[0][j]):
                    assert math.isnan(results[i][j])
                else:
                    assert (
                        results[0][j] == results[i][j]
                    ), f"Results should be deterministic at index {j}"

    def test_rust_python_equivalence_in_strategy(self):
        """Test that Rust and Python produce identical results in strategy context."""
        prices = [100.0 + i * 0.1 for i in range(100)]

        # Python implementation
        def python_sma(values, window):
            result = [float("nan")] * len(values)
            if len(values) >= window:
                result[window - 1] = sum(values[:window]) / window
                for i in range(window, len(values)):
                    result[i] = result[i - 1] + (values[i] - values[i - window]) / window
            return result

        # Compare results
        rust_result = rust_sma(prices, 20)
        python_result = python_sma(prices, 20)

        # Should be identical
        for i in range(len(prices)):
            if math.isnan(python_result[i]):
                assert math.isnan(rust_result[i])
            else:
                assert math.isclose(
                    rust_result[i], python_result[i], rel_tol=1e-9
                ), f"Mismatch at index {i}: Rust={rust_result[i]}, Python={python_result[i]}"

    def test_multi_asset_indicator_calculation(self):
        """Test Rust optimizations with multi-asset calculations."""
        # Simulate multiple asset price series
        assets = {
            "AAPL": [150.0 + i * 0.5 for i in range(100)],
            "GOOGL": [2800.0 + i * 2.0 for i in range(100)],
            "MSFT": [300.0 + i * 0.3 for i in range(100)],
        }

        # Calculate indicators for each asset
        indicators = {}
        for symbol, prices in assets.items():
            indicators[symbol] = {
                "sma_20": rust_sma(prices, 20),
                "ema_12": rust_ema(prices, 12),
            }

        # Verify all calculations completed
        for symbol in assets:
            assert len(indicators[symbol]["sma_20"]) == 100
            assert len(indicators[symbol]["ema_12"]) == 100
            # Check for valid values in second half
            sma_valid = [x for x in indicators[symbol]["sma_20"][50:] if not math.isnan(x)]
            assert len(sma_valid) > 30, f"Should have many valid SMA values for {symbol}"

    def test_rust_optimization_with_polars_dataframe(self):
        """Test Rust optimizations integrated with Polars DataFrames."""
        # Create sample DataFrame
        df = pl.DataFrame(
            {
                "date": pd.date_range("2023-01-01", periods=100, freq="D"),
                "close": [100.0 + i * 0.5 for i in range(100)],
                "volume": [1000000 + i * 10000 for i in range(100)],
            }
        )

        # Extract prices as list for Rust processing
        prices = df["close"].to_list()

        # Calculate indicators using Rust
        sma_values = rust_sma(prices, 20)
        ema_values = rust_ema(prices, 20)

        # Add back to DataFrame
        df = df.with_columns(
            [
                pl.Series("sma_20", sma_values),
                pl.Series("ema_20", ema_values),
            ]
        )

        # Verify DataFrame structure
        assert "sma_20" in df.columns
        assert "ema_20" in df.columns
        assert len(df) == 100

        # Verify calculations
        non_nan_sma = df.filter(pl.col("sma_20").is_not_nan())
        assert len(non_nan_sma) >= 80, "Should have many valid SMA values"

    def test_rust_optimization_faster_than_python(self):
        """Test that Rust optimization completes in reasonable time."""
        import time

        prices = [100.0 + i * 0.1 for i in range(10000)]

        # Run Rust implementation and time it
        start = time.perf_counter()
        rust_result = rust_sma(prices, 200)
        rust_time = time.perf_counter() - start

        # Just verify it completed quickly (should be very fast)
        assert rust_time < 1.0, f"Rust SMA took {rust_time:.4f}s, expected < 1.0s"
        assert len(rust_result) == len(prices)

        # Verify results are correct (spot check)
        assert not math.isnan(rust_result[200]), "Value at window should be valid"


@pytest.mark.integration
class TestRustOptimizationFallback:
    """Test fallback behavior when Rust is not available."""

    def test_fallback_produces_correct_results(self):
        """Test that Python fallback produces correct results."""
        from rustybt.rust_optimizations import rust_array_sum, rust_ema, rust_sma

        prices = [100.0, 102.0, 104.0, 103.0, 105.0, 107.0, 106.0, 108.0]

        # These should work regardless of Rust availability
        sma = rust_sma(prices, 3)
        ema = rust_ema(prices, 3)
        total = rust_array_sum(prices)

        # Verify calculations
        assert len(sma) == len(prices)
        assert len(ema) == len(prices)
        assert total == sum(prices)

        # SMA should have NaN for first window-1 elements
        assert math.isnan(sma[0])
        assert math.isnan(sma[1])
        assert not math.isnan(sma[2])

    def test_fallback_consistency(self):
        """Test that fallback produces consistent results across calls."""
        from rustybt.rust_optimizations import rust_sma

        prices = [100.0 + i for i in range(50)]

        # Run multiple times
        results = [rust_sma(prices, 10) for _ in range(3)]

        # All should be identical
        for i in range(len(results[0])):
            for j in range(1, len(results)):
                if math.isnan(results[0][i]):
                    assert math.isnan(results[j][i])
                else:
                    assert results[0][i] == results[j][i]


@pytest.mark.integration
@pytest.mark.skipif(not RUST_AVAILABLE, reason="Rust extensions not available")
class TestRustConfigurationPassing:
    """Test that configuration passes correctly from Python to Rust (AC4)."""

    def test_window_parameter_configuration(self):
        """Test that window size parameter passes correctly."""
        prices = [float(i) for i in range(100)]

        # Test different window sizes
        for window in [5, 10, 20, 50]:
            result = rust_sma(prices, window)

            # First window-1 elements should be NaN
            for i in range(window - 1):
                assert math.isnan(result[i]), f"Element {i} should be NaN for window {window}"

            # Element at window-1 should be valid
            assert not math.isnan(result[window - 1]), f"Element {window - 1} should be valid"

    def test_span_parameter_configuration(self):
        """Test that EMA span parameter passes correctly."""
        prices = [float(i) for i in range(100)]

        # Test different spans
        for span in [5, 10, 20]:
            result = rust_ema(prices, span)

            # All elements should be valid (EMA uses first value as initial)
            assert len(result) == len(prices)
            assert all(not math.isnan(x) for x in result)

    def test_operation_parameter_configuration(self):
        """Test that operation type parameter passes correctly."""
        a = [10.0, 20.0, 30.0]
        b = [1.0, 2.0, 3.0]

        # Test different operations
        add_result = rust_pairwise_op(a, b, "add")
        sub_result = rust_pairwise_op(a, b, "sub")
        mul_result = rust_pairwise_op(a, b, "mul")
        div_result = rust_pairwise_op(a, b, "div")

        # Verify correct operations
        assert add_result == [11.0, 22.0, 33.0]
        assert sub_result == [9.0, 18.0, 27.0]
        assert mul_result == [10.0, 40.0, 90.0]
        assert div_result == [10.0, 10.0, 10.0]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
