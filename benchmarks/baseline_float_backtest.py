"""Float baseline benchmark for comparison with Decimal implementation.

This benchmark establishes a performance baseline using float64 operations
to compare against Decimal implementation overhead.

NOTE: This is a SIMPLIFIED baseline focusing on arithmetic operations,
not a full Zipline backtest, to isolate Decimal overhead.

Run with: pytest benchmarks/baseline_float_backtest.py --benchmark-only
"""

import numpy as np
import pytest


class FloatPortfolio:
    """Simplified float-based portfolio for baseline measurement."""

    def __init__(self, starting_cash: float):
        """Initialize float portfolio.

        Args:
            starting_cash: Initial cash in float64
        """
        self.cash = starting_cash
        self.positions: dict[int, dict[str, float]] = {}

    def add_position(
        self, asset_id: int, amount: float, cost_basis: float, last_price: float
    ) -> None:
        """Add position to portfolio.

        Args:
            asset_id: Asset identifier
            amount: Position size
            cost_basis: Cost basis per share
            last_price: Current market price
        """
        self.positions[asset_id] = {
            "amount": amount,
            "cost_basis": cost_basis,
            "last_price": last_price,
        }

    def portfolio_value(self) -> float:
        """Calculate total portfolio value.

        Returns:
            Total portfolio value (cash + positions)
        """
        positions_value = sum(pos["amount"] * pos["last_price"] for pos in self.positions.values())
        return self.cash + positions_value

    def calculate_returns(self, prices: np.ndarray) -> np.ndarray:
        """Calculate returns series.

        Args:
            prices: Array of prices

        Returns:
            Array of returns
        """
        return np.diff(prices) / prices[:-1]


class FloatOrder:
    """Simplified float-based order for baseline measurement."""

    def __init__(self, asset_id: int, amount: float, price: float, commission_rate: float = 0.001):
        """Initialize float order.

        Args:
            asset_id: Asset identifier
            amount: Order size
            price: Order price
            commission_rate: Commission rate as decimal
        """
        self.asset_id = asset_id
        self.amount = amount
        self.price = price
        self.commission_rate = commission_rate

    def calculate_fill_value(self) -> float:
        """Calculate order fill value.

        Returns:
            Total order value
        """
        return abs(self.amount) * self.price

    def calculate_commission(self) -> float:
        """Calculate order commission.

        Returns:
            Commission amount
        """
        return self.calculate_fill_value() * self.commission_rate


class FloatMetrics:
    """Simplified float-based metrics for baseline measurement."""

    @staticmethod
    def sharpe_ratio(returns: np.ndarray, risk_free_rate: float = 0.0) -> float:
        """Calculate Sharpe ratio.

        Args:
            returns: Returns array
            risk_free_rate: Risk-free rate

        Returns:
            Sharpe ratio
        """
        excess_returns = returns - risk_free_rate
        if len(excess_returns) < 2:
            return 0.0
        mean_return = np.mean(excess_returns)
        std_return = np.std(excess_returns, ddof=1)
        if std_return == 0:
            return 0.0
        return mean_return / std_return

    @staticmethod
    def max_drawdown(cumulative_returns: np.ndarray) -> float:
        """Calculate maximum drawdown.

        Args:
            cumulative_returns: Cumulative returns array

        Returns:
            Maximum drawdown
        """
        running_max = np.maximum.accumulate(cumulative_returns)
        drawdown = (cumulative_returns - running_max) / running_max
        return np.min(drawdown)


@pytest.fixture
def large_float_portfolio() -> FloatPortfolio:
    """Create large portfolio with 100 positions for benchmarking.

    Returns:
        Float portfolio with 100 positions
    """
    portfolio = FloatPortfolio(starting_cash=1000000.0)

    for asset_id in range(1, 101):
        portfolio.add_position(
            asset_id=asset_id,
            amount=100.0,
            cost_basis=50.0,
            last_price=55.0 + (asset_id * 0.1),
        )

    return portfolio


@pytest.fixture
def float_returns_series() -> np.ndarray:
    """Create returns series with 252 data points (1 year daily).

    Returns:
        Array of returns
    """
    np.random.seed(42)
    # Generate realistic returns: mean 0.05%, std 1.5%
    return np.random.normal(loc=0.0005, scale=0.015, size=252)


@pytest.mark.benchmark(group="portfolio")
def test_float_portfolio_value_100_positions(benchmark, large_float_portfolio):
    """Benchmark float portfolio value calculation with 100 positions.

    This establishes the baseline for DecimalLedger.portfolio_value benchmark.
    """
    result = benchmark(large_float_portfolio.portfolio_value)

    # Verify calculation is correct
    assert result > 1000000.0  # Starting cash + position values
    assert isinstance(result, float)


@pytest.mark.benchmark(group="portfolio")
def test_float_portfolio_value_scalability(benchmark):
    """Benchmark float portfolio value with varying position counts."""
    portfolio = FloatPortfolio(starting_cash=1000000.0)

    # Add 1000 positions for scalability test
    for asset_id in range(1, 1001):
        portfolio.add_position(asset_id=asset_id, amount=100.0, cost_basis=50.0, last_price=55.0)

    result = benchmark(portfolio.portfolio_value)

    assert result > 1000000.0
    assert isinstance(result, float)


@pytest.mark.benchmark(group="returns")
def test_float_calculate_returns(benchmark, float_returns_series):
    """Benchmark float returns calculation.

    This establishes the baseline for DecimalLedger.calculate_returns benchmark.
    """
    # Generate price series from returns
    prices = np.cumprod(1 + float_returns_series)

    result = benchmark(lambda: np.diff(prices) / prices[:-1])

    # Verify calculation
    assert len(result) == len(prices) - 1
    assert isinstance(result[0], np.floating)


@pytest.mark.benchmark(group="orders")
def test_float_order_processing_1000_orders(benchmark):
    """Benchmark float order processing for 1000 orders.

    This establishes the baseline for DecimalOrder benchmark.
    """

    def process_orders() -> list[tuple[float, float]]:
        """Process 1000 orders and calculate values."""
        results = []
        for i in range(1, 1001):
            order = FloatOrder(
                asset_id=i, amount=100.0, price=50.0 + (i * 0.01), commission_rate=0.001
            )
            fill_value = order.calculate_fill_value()
            commission = order.calculate_commission()
            results.append((fill_value, commission))
        return results

    results = benchmark(process_orders)

    # Verify processing
    assert len(results) == 1000
    assert all(isinstance(v, float) for v, c in results)


@pytest.mark.benchmark(group="metrics")
def test_float_sharpe_ratio(benchmark, float_returns_series):
    """Benchmark float Sharpe ratio calculation.

    This establishes the baseline for Decimal metrics benchmark.
    """
    result = benchmark(FloatMetrics.sharpe_ratio, float_returns_series)

    # Verify calculation
    assert isinstance(result, (float, np.floating))
    # Sharpe should be in reasonable range
    assert -5.0 < result < 5.0


@pytest.mark.benchmark(group="metrics")
def test_float_max_drawdown(benchmark, float_returns_series):
    """Benchmark float maximum drawdown calculation.

    This establishes the baseline for Decimal metrics benchmark.
    """
    cumulative_returns = np.cumprod(1 + float_returns_series)

    result = benchmark(FloatMetrics.max_drawdown, cumulative_returns)

    # Verify calculation
    assert isinstance(result, (float, np.floating))
    # Drawdown should be negative or zero
    assert result <= 0.0


@pytest.mark.benchmark(group="data")
def test_float_data_aggregation(benchmark):
    """Benchmark float data aggregation operations.

    This establishes the baseline for data pipeline benchmarks.
    """

    def aggregate_ohlcv_data() -> dict[str, float]:
        """Aggregate OHLCV data for 100 assets x 252 days."""
        # Simulate 1 year of daily bars for 100 assets
        num_assets = 100
        num_days = 252

        # Generate random OHLCV data
        np.random.seed(42)
        data = np.random.rand(num_assets * num_days, 5)

        # Calculate aggregates
        return {
            "mean_close": np.mean(data[:, 3]),
            "std_close": np.std(data[:, 3]),
            "total_volume": np.sum(data[:, 4]),
            "max_high": np.max(data[:, 1]),
            "min_low": np.min(data[:, 2]),
        }

    result = benchmark(aggregate_ohlcv_data)

    # Verify aggregation
    assert all(isinstance(v, (float, np.floating)) for v in result.values())


@pytest.mark.benchmark(group="end-to-end")
def test_float_simplified_backtest(benchmark):
    """Benchmark simplified float-based backtest simulation.

    This is a SIMPLIFIED baseline to measure arithmetic overhead,
    not a full Zipline backtest.
    """

    def run_simple_backtest() -> dict[str, float]:
        """Run simplified backtest with portfolio, orders, and metrics."""
        # Initialize portfolio
        portfolio = FloatPortfolio(starting_cash=1000000.0)

        # Simulate 252 days of trading
        np.random.seed(42)
        daily_returns = []

        for day in range(252):
            # Process 10 orders per day
            for i in range(10):
                order = FloatOrder(
                    asset_id=i + 1,
                    amount=100.0,
                    price=50.0 + np.random.random(),
                    commission_rate=0.001,
                )
                fill_value = order.calculate_fill_value()
                commission = order.calculate_commission()

                # Update portfolio (simplified)
                portfolio.cash -= fill_value + commission
                if (i + 1) not in portfolio.positions:
                    portfolio.add_position(
                        asset_id=i + 1,
                        amount=100.0,
                        cost_basis=order.price,
                        last_price=order.price,
                    )

            # Calculate daily return
            portfolio_value = portfolio.portfolio_value()
            if len(daily_returns) > 0:
                prev_value = 1000000.0 + sum((1 + r) for r in daily_returns) * 10000
                daily_return = (portfolio_value - prev_value) / prev_value
                daily_returns.append(daily_return)
            else:
                daily_returns.append(0.0)

        # Calculate metrics
        returns_array = np.array(daily_returns)
        sharpe = FloatMetrics.sharpe_ratio(returns_array)
        cumulative_returns = np.cumprod(1 + returns_array)
        max_dd = FloatMetrics.max_drawdown(cumulative_returns)

        return {
            "final_portfolio_value": portfolio.portfolio_value(),
            "sharpe_ratio": sharpe,
            "max_drawdown": max_dd,
            "total_orders": 252 * 10,
        }

    result = benchmark(run_simple_backtest)

    # Verify backtest execution
    assert result["total_orders"] == 2520
    assert isinstance(result["final_portfolio_value"], float)
    assert isinstance(result["sharpe_ratio"], (float, np.floating))
