"""Type stubs for rustybt.algorithm module.

This stub file provides type hints for IDE autocomplete and type checking,
particularly for class-based strategy development.
"""

from typing import Any

import pandas as pd

from rustybt._protocol import BarData
from rustybt.protocol import Account, Portfolio

class TradingAlgorithm:
    """Type hints for TradingAlgorithm class.

    When creating class-based strategies, override these methods with proper type hints.
    The 'context' parameter in user methods is actually the TradingAlgorithm instance itself.
    """

    # For subclasses to override - these show the expected signatures
    def initialize(self, context: TradingAlgorithm) -> None: ...
    def handle_data(self, context: TradingAlgorithm, data: BarData) -> None: ...
    def before_trading_start(self, context: TradingAlgorithm, data: BarData) -> None: ...
    def analyze(self, context: TradingAlgorithm, perf: pd.DataFrame) -> None: ...

    # Core attributes that users access via context
    asset_finder: Any  # AssetFinder type stub doesn't exist yet
    portfolio: Portfolio
    account: Account
    blotter: Any  # SimulationBlotter type stub doesn't exist yet

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
