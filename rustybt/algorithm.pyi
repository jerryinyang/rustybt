"""Type stubs for rustybt.algorithm module.

This stub file provides type hints for IDE autocomplete and type checking,
particularly for class-based strategy development.

IMPORTANT: Class-based strategies use `self` to access the algorithm context.
           In class-based strategies, `self` IS the context.
           Do NOT add a separate `context` parameter to initialize().
"""

from typing import Any

import pandas as pd

from rustybt._protocol import BarData
from rustybt.assets.assets import AssetFinder
from rustybt.finance.blotter.simulation_blotter import SimulationBlotter
from rustybt.protocol import Account, Portfolio

class TradingAlgorithm:
    """Type hints for TradingAlgorithm class.

    When creating class-based strategies, override these methods.
    Access algorithm state via `self` (self IS the context).

    Example:
        class MyStrategy(TradingAlgorithm):
            def initialize(self) -> None:
                # Access via self, NOT context
                self.asset = self.symbol('AAPL')

            def handle_data(self, context, data) -> None:
                # context parameter passed but self == context
                self.order(self.asset, 100)
    """

    # For subclasses to override - these show the expected signatures
    def initialize(self) -> None:
        """Initialize strategy. Override this method in your subclass.

        Access algorithm state via self:
            self.portfolio - Portfolio state
            self.account - Account state
            self.asset_finder - Asset lookup
            self.symbol('AAPL') - Lookup assets
        """
        ...

    def handle_data(self, context: TradingAlgorithm, data: BarData) -> None:
        """Handle each bar of data. Override this method in your subclass.

        Args:
            context: The algorithm instance (same as self)
            data: Market data for current bar
        """
        ...

    def before_trading_start(self, context: TradingAlgorithm, data: BarData) -> None:
        """Called before market open each day. Override this method in your subclass.

        Args:
            context: The algorithm instance (same as self)
            data: Market data for current bar
        """
        ...

    def analyze(self, context: TradingAlgorithm, perf: pd.DataFrame) -> None:
        """Analyze performance after backtest completes. Override this method in your subclass.

        Args:
            context: The algorithm instance (same as self)
            perf: Performance DataFrame with backtest results
        """
        ...
    # Core attributes that users access via self
    asset_finder: AssetFinder
    portfolio: Portfolio
    account: Account
    blotter: SimulationBlotter

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
