"""
Class-Based Moving Average Crossover Strategy

This example demonstrates the class-based API for writing trading strategies.
The class-based API is useful for:
- Organizing complex strategies with helper methods
- Reusing strategy code across multiple files
- Object-oriented programming patterns

IMPORTANT: This format works with CLI execution:
    rustybt run -f class_based_moving_average.py -b quandl --start 2020-01-01 --end 2023-12-31

For notebooks and run_algorithm(), use the functional API instead (see buy_apple.py).
"""

from rustybt import TradingAlgorithm
from rustybt.api import order_target, record, symbol


class MovingAverageStrategy(TradingAlgorithm):
    """
    Moving average crossover strategy using class-based API.

    Buys when short moving average crosses above long moving average.
    Sells when short moving average crosses below long moving average.

    Method Signatures (Class-Based):
    - initialize(self) - NO context parameter
    - handle_data(self, context, data) - self comes first
    - State stored on self (e.g., self.asset)
    """

    def initialize(self):
        """
        Initialize strategy.

        IMPORTANT: No context parameter! Just self.
        Store state as self.attribute_name (not context.attribute_name).
        """
        # Set up strategy parameters
        self.asset = symbol("AAPL")
        self.short_window = 100
        self.long_window = 300
        self.i = 0

        print(f"Initialized {self.__class__.__name__}")
        print(f"Trading {self.asset.symbol}")
        print(f"Short MA: {self.short_window} days, Long MA: {self.long_window} days")

    def handle_data(self, context, data):
        """
        Handle each bar of market data.

        Parameters
        ----------
        self : MovingAverageStrategy
            The strategy instance
        context : TradingAlgorithm
            Algorithm context (same as self in class-based API)
        data : BarData
            Current and historical market data

        IMPORTANT: self parameter comes first!
        Access state via self (e.g., self.asset, self.i).
        """
        self.i += 1

        # Skip first bars until we have enough data
        if self.i < self.long_window:
            return

        # Use helper method (advantage of class-based API!)
        short_mavg, long_mavg = self.calculate_moving_averages(data)

        # Get current price and position
        price = data.current(self.asset, "price")
        current_position = context.portfolio.positions[self.asset].amount

        # Trading logic: Moving average crossover
        if short_mavg > long_mavg and current_position == 0:
            # Golden cross: Buy signal
            order_target(self.asset, 100)
            print(
                f"BUY signal on day {self.i}: Short MA ({short_mavg:.2f}) > Long MA ({long_mavg:.2f})"
            )

        elif short_mavg < long_mavg and current_position > 0:
            # Death cross: Sell signal
            order_target(self.asset, 0)
            print(
                f"SELL signal on day {self.i}: Short MA ({short_mavg:.2f}) < Long MA ({long_mavg:.2f})"
            )

        # Record metrics for analysis
        record(
            price=price,
            short_mavg=short_mavg,
            long_mavg=long_mavg,
            position=current_position,
        )

    def calculate_moving_averages(self, data):
        """
        Calculate short and long moving averages.

        This is a helper method - one advantage of the class-based API.
        Can access self.asset, self.short_window, etc. directly.

        Parameters
        ----------
        data : BarData
            Market data

        Returns
        -------
        tuple[float, float]
            (short_mavg, long_mavg)
        """
        short_history = data.history(
            self.asset, "price", bar_count=self.short_window, frequency="1d"
        )
        long_history = data.history(self.asset, "price", bar_count=self.long_window, frequency="1d")

        return short_history.mean(), long_history.mean()

    def analyze(self, context, perf):
        """
        Analyze results after backtest completes (optional).

        Parameters
        ----------
        self : MovingAverageStrategy
        context : TradingAlgorithm
        perf : pd.DataFrame
            Performance results
        """
        print("\n=== Backtest Complete ===")
        print(f"Final portfolio value: ${context.portfolio.portfolio_value:,.2f}")
        print(f"Total return: {perf['algorithm_period_return'].iloc[-1] * 100:.2f}%")
        print(f"Max drawdown: {perf['max_drawdown'].min() * 100:.2f}%")


# CLI Execution:
#   rustybt run -f class_based_moving_average.py -b quandl \\
#       --start 2020-01-01 --end 2023-12-31 --capital-base 100000
#
# The framework automatically detects the MovingAverageStrategy class
# and binds its methods to the algorithm instance!

# For functional API equivalent, see: buy_apple.py
