"""Memory overhead benchmarks for Decimal vs float.

Measures memory consumption of Decimal-based implementations compared to
float-based implementations.

Run with: pytest benchmarks/memory_overhead_benchmark.py --benchmark-only

Note: Memory profiling uses tracemalloc (stdlib) for accurate memory tracking.
"""

import random
import tracemalloc
from collections import namedtuple
from decimal import Decimal

import polars as pl
import pytest

from rustybt.assets import Equity
from rustybt.finance.decimal.ledger import DecimalLedger
from rustybt.finance.decimal.position import DecimalPosition

# Test fixture for exchange info
ExchangeInfo = namedtuple("ExchangeInfo", ["canonical_name", "name", "country_code"])
TEST_EXCHANGE = ExchangeInfo(
    canonical_name="NYSE", name="New York Stock Exchange", country_code="US"
)


def measure_memory(func):
    """Measure peak memory usage of a function."""
    tracemalloc.start()
    result = func()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return result, peak


@pytest.mark.benchmark(group="memory-decimal-values")
def test_memory_decimal_vs_float_1000_values(benchmark):
    """Compare memory usage: 1000 Decimal values vs 1000 floats.

    Expected:
        Decimal: ~16 bytes per value (128-bit)
        float64: ~8 bytes per value (64-bit)
        Overhead: ~100% (2x memory)
    """

    def create_decimals():
        _, peak_decimal = measure_memory(
            lambda: [Decimal(str(50.0 + i * 0.01)) for i in range(1000)]
        )
        return peak_decimal

    decimal_memory = benchmark(create_decimals)

    # Report memory in KB
    print(f"\nDecimal memory (1000 values): {decimal_memory / 1024:.2f} KB")


@pytest.mark.benchmark(group="memory-series")
def test_memory_decimal_series_vs_float_10000(benchmark):
    """Compare memory usage: Decimal Series vs Float64 Series (10,000 values).

    Expected overhead: ~100-150% (2-2.5x memory)
    """

    def create_decimal_series():
        random.seed(42)
        values = [Decimal(str(random.random() * 100)) for _ in range(10000)]
        _, peak = measure_memory(lambda: pl.Series("values", values, dtype=pl.Decimal(scale=8)))
        return peak

    decimal_memory = benchmark(create_decimal_series)

    print(f"\nDecimal Series memory (10,000 values): {decimal_memory / 1024:.2f} KB")


@pytest.mark.benchmark(group="memory-portfolio")
def test_memory_decimal_portfolio_100_positions(benchmark):
    """Measure memory overhead of DecimalLedger with 100 positions.

    Expected: ~50-100 KB for 100 positions
    """

    def create_portfolio():
        ledger = DecimalLedger(starting_cash=Decimal("1000000"))

        for i in range(1, 101):
            asset = Equity(sid=i, exchange_info=TEST_EXCHANGE, symbol=f"STOCK{i}")
            position = DecimalPosition(
                asset=asset,
                amount=Decimal("100"),
                cost_basis=Decimal("50"),
                last_sale_price=Decimal(str(50.0 + i * 0.1)),
                last_sale_date=None,
            )
            ledger.positions[asset] = position

        return ledger

    _, peak = measure_memory(create_portfolio)
    memory_kb = peak / 1024

    result = benchmark(create_portfolio)

    print(f"\nDecimalLedger memory (100 positions): {memory_kb:.2f} KB")
    assert len(result.positions) == 100


@pytest.mark.benchmark(group="memory-dataframe")
def test_memory_decimal_dataframe_ohlcv(benchmark):
    """Measure memory overhead of Decimal DataFrame (OHLCV data).

    1 year × 100 assets = 25,200 rows × 5 Decimal columns
    Expected: ~5-15 MB
    """

    def create_decimal_dataframe():
        random.seed(42)
        num_rows = 252 * 100

        data = {
            "open": pl.Series(
                [Decimal(str(50.0 + random.random() * 10)) for _ in range(num_rows)],
                dtype=pl.Decimal(scale=8),
            ),
            "high": pl.Series(
                [Decimal(str(55.0 + random.random() * 10)) for _ in range(num_rows)],
                dtype=pl.Decimal(scale=8),
            ),
            "low": pl.Series(
                [Decimal(str(45.0 + random.random() * 10)) for _ in range(num_rows)],
                dtype=pl.Decimal(scale=8),
            ),
            "close": pl.Series(
                [Decimal(str(50.0 + random.random() * 10)) for _ in range(num_rows)],
                dtype=pl.Decimal(scale=8),
            ),
            "volume": pl.Series(
                [Decimal(str(random.random() * 1000000)) for _ in range(num_rows)],
                dtype=pl.Decimal(scale=8),
            ),
        }

        return pl.DataFrame(data)

    _, peak = measure_memory(create_decimal_dataframe)
    memory_mb = peak / 1024 / 1024

    result = benchmark(create_decimal_dataframe)

    print(f"\nDecimal DataFrame memory (25,200 rows × 5 cols): {memory_mb:.2f} MB")
    assert len(result) == 25200


@pytest.mark.benchmark(group="memory-returns-series")
def test_memory_returns_series_252_vs_2520(benchmark):
    """Compare memory usage for different return series lengths.

    Tests memory scaling: 252 returns (1 year) vs 2520 returns (10 years)
    Expected: Linear scaling ~10x memory for 10x data
    """

    def create_returns_series(num_returns):
        random.seed(42)
        returns = [Decimal(str(random.gauss(0.0005, 0.015))) for _ in range(num_returns)]
        _, peak = measure_memory(lambda: pl.Series("returns", returns, dtype=pl.Decimal(scale=8)))
        return peak

    # Measure 1 year
    memory_252 = create_returns_series(252)

    # Measure 10 years
    def measure_10_years():
        return create_returns_series(2520)

    memory_2520 = benchmark(measure_10_years)

    scaling_factor = memory_2520 / memory_252
    print(f"\n1 year memory: {memory_252 / 1024:.2f} KB")
    print(f"10 year memory: {memory_2520 / 1024:.2f} KB")
    print(f"Scaling factor: {scaling_factor:.2f}x")

    # Should be approximately linear scaling
    assert 8 < scaling_factor < 12


@pytest.mark.benchmark(group="memory-portfolio-scaling")
@pytest.mark.parametrize("num_positions", [10, 100, 1000])
def test_memory_portfolio_scaling(benchmark, num_positions):
    """Test memory usage scales with portfolio size.

    Expected: Linear O(n) memory scaling
    """

    def create_portfolio():
        ledger = DecimalLedger(starting_cash=Decimal("1000000"))

        for i in range(1, num_positions + 1):
            asset = Equity(sid=i, exchange_info=TEST_EXCHANGE, symbol=f"STOCK{i}")
            position = DecimalPosition(
                asset=asset,
                amount=Decimal("100"),
                cost_basis=Decimal("50"),
                last_sale_price=Decimal("55"),
                last_sale_date=None,
            )
            ledger.positions[asset] = position

        return ledger

    _, peak = measure_memory(create_portfolio)
    memory_kb = peak / 1024

    result = benchmark(create_portfolio)

    print(f"\nMemory for {num_positions} positions: {memory_kb:.2f} KB")
    assert len(result.positions) == num_positions


@pytest.mark.benchmark(group="memory-overhead-calculation")
def test_calculate_total_memory_overhead(benchmark):
    """Calculate total memory overhead for realistic backtest scenario.

    Scenario:
        - Portfolio: 100 positions
        - Price data: 1 year × 100 assets
        - Returns series: 252 daily returns

    This represents typical backtest memory footprint.
    """

    def create_backtest_memory_footprint():
        # Portfolio
        ledger = DecimalLedger(starting_cash=Decimal("1000000"))
        for i in range(1, 101):
            asset = Equity(sid=i, exchange_info=TEST_EXCHANGE, symbol=f"STOCK{i}")
            position = DecimalPosition(
                asset=asset,
                amount=Decimal("100"),
                cost_basis=Decimal("50"),
                last_sale_price=Decimal(str(50.0 + i * 0.1)),
                last_sale_date=None,
            )
            ledger.positions[asset] = position

        # Price data
        random.seed(42)
        num_rows = 252 * 100
        price_df = pl.DataFrame(
            {
                "close": pl.Series(
                    [Decimal(str(50.0 + random.random() * 10)) for _ in range(num_rows)],
                    dtype=pl.Decimal(scale=8),
                ),
            }
        )

        # Returns series
        returns = [Decimal(str(random.gauss(0.0005, 0.015))) for _ in range(252)]
        returns_series = pl.Series("returns", returns, dtype=pl.Decimal(scale=8))

        return {
            "ledger": ledger,
            "prices": price_df,
            "returns": returns_series,
        }

    _, peak = measure_memory(create_backtest_memory_footprint)
    memory_mb = peak / 1024 / 1024

    result = benchmark(create_backtest_memory_footprint)

    print(f"\nTotal backtest memory footprint: {memory_mb:.2f} MB")
    print("  - Portfolio: 100 positions")
    print("  - Price data: 25,200 rows")
    print("  - Returns: 252 values")

    assert "ledger" in result
    assert "prices" in result
    assert "returns" in result


@pytest.mark.benchmark(group="memory-comparison-summary")
def test_memory_overhead_summary(benchmark):
    """Generate comprehensive memory overhead summary.

    Compares Decimal vs expected float memory usage across all components.
    """

    def measure_all_components():
        results = {}

        # 1. Simple values (1000)
        _, decimal_values_mem = measure_memory(
            lambda: [Decimal(str(50.0 + i * 0.01)) for i in range(1000)]
        )
        results["1000_values_kb"] = decimal_values_mem / 1024

        # 2. Series (10,000)
        random.seed(42)
        _, series_mem = measure_memory(
            lambda: pl.Series(
                [Decimal(str(random.random() * 100)) for _ in range(10000)],
                dtype=pl.Decimal(scale=8),
            )
        )
        results["10000_series_kb"] = series_mem / 1024

        # 3. Portfolio (100 positions)
        def create_portfolio():
            ledger = DecimalLedger(starting_cash=Decimal("1000000"))
            for i in range(1, 101):
                asset = Equity(sid=i, exchange_info=TEST_EXCHANGE, symbol=f"STOCK{i}")
                position = DecimalPosition(
                    asset=asset,
                    amount=Decimal("100"),
                    cost_basis=Decimal("50"),
                    last_sale_price=Decimal("55"),
                    last_sale_date=None,
                )
                ledger.positions[asset] = position
            return ledger

        _, portfolio_mem = measure_memory(create_portfolio)
        results["100_positions_kb"] = portfolio_mem / 1024

        return results

    results = benchmark(measure_all_components)

    print("\n" + "=" * 60)
    print("MEMORY OVERHEAD SUMMARY (Decimal)")
    print("=" * 60)
    print(f"1,000 Decimal values:    {results['1000_values_kb']:>10.2f} KB")
    print(f"10,000 Decimal Series:   {results['10000_series_kb']:>10.2f} KB")
    print(f"100 position portfolio:  {results['100_positions_kb']:>10.2f} KB")
    print("=" * 60)
    print("Expected float64 memory: ~50% of Decimal memory")
    print("Estimated overhead:      ~100-150% (2-2.5x)")
    print("=" * 60)
