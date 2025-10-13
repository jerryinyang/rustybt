"""Decimal backtest benchmark for comparison with float baseline.

This benchmark measures Decimal implementation performance to calculate
overhead compared to float baseline.

Run with: pytest benchmarks/decimal_backtest.py --benchmark-only
"""

from collections import namedtuple
from decimal import Decimal

import polars as pl
import pytest

from rustybt.assets import Equity
from rustybt.finance.decimal.commission import PerShareCommission
from rustybt.finance.decimal.ledger import DecimalLedger
from rustybt.finance.decimal.order import DecimalOrder
from rustybt.finance.decimal.position import DecimalPosition

# Test fixture for exchange info (acceptable for test/benchmark fixtures)
ExchangeInfo = namedtuple("ExchangeInfo", ["canonical_name", "name", "country_code"])
TEST_EXCHANGE = ExchangeInfo(
    canonical_name="NYSE", name="New York Stock Exchange", country_code="US"
)


class DecimalMetrics:
    """Decimal-based metrics calculator."""

    @staticmethod
    def sharpe_ratio(returns: pl.Series, risk_free_rate: Decimal = Decimal("0")) -> Decimal:
        """Calculate Sharpe ratio with Decimal precision.

        Args:
            returns: Polars Series of Decimal returns
            risk_free_rate: Risk-free rate as Decimal

        Returns:
            Sharpe ratio as Decimal
        """
        if len(returns) < 2:
            return Decimal("0")

        # Calculate excess returns
        excess_returns = returns.map_elements(
            lambda x: x - risk_free_rate if x is not None else Decimal("0"),
            return_dtype=pl.Decimal(scale=8),
        )

        # Calculate mean and std
        mean_return = excess_returns.mean()
        std_return = excess_returns.std()

        if mean_return is None or std_return is None or std_return == 0:
            return Decimal("0")

        return Decimal(str(mean_return)) / Decimal(str(std_return))

    @staticmethod
    def max_drawdown(cumulative_returns: pl.Series) -> Decimal:
        """Calculate maximum drawdown with Decimal precision.

        Args:
            cumulative_returns: Polars Series of cumulative returns

        Returns:
            Maximum drawdown as Decimal
        """
        # Calculate running maximum
        running_max = cumulative_returns.cum_max()

        # Calculate drawdown
        drawdown = cumulative_returns - running_max

        # Normalize by running max (avoid division by zero)
        normalized_drawdown = drawdown / running_max.map_elements(
            lambda x: x if x != 0 else Decimal("1"), return_dtype=pl.Decimal(scale=8)
        )

        min_dd = normalized_drawdown.min()
        return Decimal(str(min_dd)) if min_dd is not None else Decimal("0")


@pytest.fixture
def large_decimal_portfolio() -> DecimalLedger:
    """Create large portfolio with 100 positions for benchmarking.

    Returns:
        DecimalLedger with 100 positions
    """
    ledger = DecimalLedger(starting_cash=Decimal("1000000"))

    for asset_id in range(1, 101):
        asset = Equity(
            sid=asset_id,
            exchange_info=TEST_EXCHANGE,
            symbol=f"TEST{asset_id}",
        )
        position = DecimalPosition(
            asset=asset,
            amount=Decimal("100"),
            cost_basis=Decimal("50"),
            last_sale_price=Decimal(str(55.0 + (asset_id * 0.1))),
            last_sale_date=None,
        )
        ledger.positions[asset] = position

    return ledger


@pytest.fixture
def decimal_returns_series() -> pl.Series:
    """Create Decimal returns series with 252 data points (1 year daily).

    Returns:
        Polars Series of Decimal returns
    """
    import random

    random.seed(42)
    # Generate realistic returns: mean 0.05%, std 1.5%
    returns = [Decimal(str(random.gauss(0.0005, 0.015))) for _ in range(252)]
    return pl.Series("returns", returns, dtype=pl.Decimal(scale=8))


@pytest.mark.benchmark(group="portfolio")
def test_decimal_portfolio_value_100_positions(benchmark, large_decimal_portfolio):
    """Benchmark Decimal portfolio value calculation with 100 positions.

    This compares against test_float_portfolio_value_100_positions baseline.
    """
    result = benchmark(lambda: large_decimal_portfolio.portfolio_value)

    # Verify calculation is correct
    assert result > Decimal("1000000")  # Starting cash + position values
    assert isinstance(result, Decimal)


@pytest.mark.benchmark(group="portfolio")
def test_decimal_portfolio_value_scalability(benchmark):
    """Benchmark Decimal portfolio value with varying position counts."""
    ledger = DecimalLedger(starting_cash=Decimal("1000000"))

    # Add 1000 positions for scalability test
    for asset_id in range(1, 1001):
        asset = Equity(sid=asset_id, exchange_info=TEST_EXCHANGE, symbol=f"TEST{asset_id}")
        position = DecimalPosition(
            asset=asset,
            amount=Decimal("100"),
            cost_basis=Decimal("50"),
            last_sale_price=Decimal("55"),
            last_sale_date=None,
        )
        ledger.positions[asset] = position

    result = benchmark(lambda: ledger.portfolio_value)

    assert result > Decimal("1000000")
    assert isinstance(result, Decimal)


@pytest.mark.benchmark(group="returns")
def test_decimal_calculate_returns(benchmark, decimal_returns_series):
    """Benchmark Decimal returns calculation.

    This compares against test_float_calculate_returns baseline.
    """
    # Generate price series from returns (cumulative product)
    # Note: Polars doesn't support cum_prod for Decimal, so we implement manually
    price_factors = decimal_returns_series.map_elements(
        lambda x: Decimal("1") + x, return_dtype=pl.Decimal(scale=8)
    )

    # Manual cumulative product
    cumulative = Decimal("1")
    prices_list = []
    for factor in price_factors:
        cumulative = cumulative * factor
        prices_list.append(cumulative)

    prices = pl.Series("prices", prices_list, dtype=pl.Decimal(scale=8))

    def calculate_returns(prices: pl.Series) -> pl.Series:
        """Calculate returns from prices."""
        shifted = prices.shift(1)
        return (prices - shifted) / shifted

    result = benchmark(calculate_returns, prices)

    # Verify calculation
    assert len(result) == len(prices)


@pytest.mark.benchmark(group="orders")
def test_decimal_order_processing_1000_orders(benchmark):
    """Benchmark Decimal order processing for 1000 orders.

    This compares against test_float_order_processing_1000_orders baseline.
    """
    commission_model = PerShareCommission(rate=Decimal("0.001"))

    def process_orders() -> list[tuple[Decimal, Decimal]]:
        """Process 1000 orders and calculate values."""
        results = []
        for i in range(1, 1001):
            asset = Equity(sid=i, exchange_info=TEST_EXCHANGE, symbol=f"TEST{i}")
            order = DecimalOrder(
                asset=asset,
                amount=Decimal("100"),
                limit=Decimal(str(50.0 + (i * 0.01))),
                stop=None,
                dt=None,
            )

            # Calculate order value and commission
            fill_price = order.limit
            fill_amount = order.amount
            fill_value = abs(fill_amount) * fill_price
            commission = commission_model.calculate(order, fill_price, fill_amount)

            results.append((fill_value, commission))
        return results

    results = benchmark(process_orders)

    # Verify processing
    assert len(results) == 1000
    assert all(isinstance(v, Decimal) for v, c in results)


@pytest.mark.benchmark(group="metrics")
def test_decimal_sharpe_ratio(benchmark, decimal_returns_series):
    """Benchmark Decimal Sharpe ratio calculation.

    This compares against test_float_sharpe_ratio baseline.
    """
    result = benchmark(DecimalMetrics.sharpe_ratio, decimal_returns_series)

    # Verify calculation
    assert isinstance(result, Decimal)
    # Sharpe should be in reasonable range
    assert Decimal("-5") < result < Decimal("5")


@pytest.mark.benchmark(group="metrics")
def test_decimal_max_drawdown(benchmark, decimal_returns_series):
    """Benchmark Decimal maximum drawdown calculation.

    This compares against test_float_max_drawdown baseline.
    """
    # Generate cumulative returns (manual cumulative product)
    price_factors = decimal_returns_series.map_elements(
        lambda x: Decimal("1") + x, return_dtype=pl.Decimal(scale=8)
    )

    # Manual cumulative product
    cumulative = Decimal("1")
    cumulative_list = []
    for factor in price_factors:
        cumulative = cumulative * factor
        cumulative_list.append(cumulative)

    cumulative_returns = pl.Series("cumulative_returns", cumulative_list, dtype=pl.Decimal(scale=8))

    result = benchmark(DecimalMetrics.max_drawdown, cumulative_returns)

    # Verify calculation
    assert isinstance(result, Decimal)
    # Drawdown should be negative or zero
    assert result <= Decimal("0")


@pytest.mark.benchmark(group="data")
def test_decimal_data_aggregation(benchmark):
    """Benchmark Decimal data aggregation operations.

    This compares against test_float_data_aggregation baseline.
    """

    def aggregate_ohlcv_data() -> dict[str, Decimal]:
        """Aggregate OHLCV data for 100 assets x 252 days."""
        import random

        random.seed(42)

        # Generate random Decimal OHLCV data (simplified)
        closes = [Decimal(str(random.random() * 100)) for _ in range(100 * 252)]
        highs = [c * Decimal("1.01") for c in closes]
        lows = [c * Decimal("0.99") for c in closes]
        volumes = [Decimal(str(random.random() * 1000000)) for _ in range(100 * 252)]

        # Create Polars DataFrame
        df = pl.DataFrame(
            {
                "close": pl.Series(closes, dtype=pl.Decimal(scale=8)),
                "high": pl.Series(highs, dtype=pl.Decimal(scale=8)),
                "low": pl.Series(lows, dtype=pl.Decimal(scale=8)),
                "volume": pl.Series(volumes, dtype=pl.Decimal(scale=8)),
            }
        )

        # Calculate aggregates
        return {
            "mean_close": Decimal(str(df["close"].mean())),
            "std_close": Decimal(str(df["close"].std())),
            "total_volume": Decimal(str(df["volume"].sum())),
            "max_high": Decimal(str(df["high"].max())),
            "min_low": Decimal(str(df["low"].min())),
        }

    result = benchmark(aggregate_ohlcv_data)

    # Verify aggregation
    assert all(isinstance(v, Decimal) for v in result.values())


@pytest.mark.benchmark(group="end-to-end")
def test_decimal_simplified_backtest(benchmark):
    """Benchmark simplified Decimal-based backtest simulation.

    This is a SIMPLIFIED baseline to measure arithmetic overhead,
    comparing against test_float_simplified_backtest baseline.
    """
    commission_model = PerShareCommission(rate=Decimal("0.001"))

    def run_simple_backtest() -> dict[str, Decimal]:
        """Run simplified backtest with portfolio, orders, and metrics."""
        import random

        random.seed(42)

        # Initialize portfolio
        ledger = DecimalLedger(starting_cash=Decimal("1000000"))
        daily_returns = []

        # Simulate 252 days of trading
        for day in range(252):
            # Process 10 orders per day
            for i in range(10):
                asset = Equity(sid=i + 1, exchange_info=TEST_EXCHANGE, symbol=f"TEST{i + 1}")
                price = Decimal(str(50.0 + random.random()))

                order = DecimalOrder(
                    asset=asset,
                    amount=Decimal("100"),
                    limit=price,
                    stop=None,
                    dt=None,
                )

                fill_price = order.limit
                fill_amount = order.amount
                fill_value = abs(fill_amount) * fill_price
                commission = commission_model.calculate(order, fill_price, fill_amount)

                # Update portfolio (simplified)
                ledger.cash -= fill_value + commission

                if asset not in ledger.positions:
                    position = DecimalPosition(
                        asset=asset,
                        amount=order.amount,
                        cost_basis=order.limit,
                        last_sale_price=order.limit,
                        last_sale_date=None,
                    )
                    ledger.positions[asset] = position

            # Calculate daily return (simplified)
            portfolio_value = ledger.portfolio_value
            if len(daily_returns) > 0:
                # Simplified return calculation
                prev_value = Decimal("1000000") + sum(
                    Decimal("10000") * (Decimal("1") + r) for r in daily_returns
                )
                daily_return = (portfolio_value - prev_value) / prev_value
                daily_returns.append(daily_return)
            else:
                daily_returns.append(Decimal("0"))

        # Calculate metrics
        returns_series = pl.Series("returns", daily_returns, dtype=pl.Decimal(scale=8))
        sharpe = DecimalMetrics.sharpe_ratio(returns_series)

        return {
            "final_portfolio_value": ledger.portfolio_value,
            "sharpe_ratio": sharpe,
            "total_orders": Decimal("2520"),  # 252 * 10
        }

    result = benchmark(run_simple_backtest)

    # Verify backtest execution
    assert result["total_orders"] == Decimal("2520")
    assert isinstance(result["final_portfolio_value"], Decimal)
    assert isinstance(result["sharpe_ratio"], Decimal)
