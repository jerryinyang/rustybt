"""Type stubs for rustybt.algorithm module.

This stub file provides type hints for IDE autocomplete and type checking,
particularly for class-based strategy development.
"""

from typing import Any

import pandas as pd

class TradingAlgorithm:
    """Type hints for TradingAlgorithm class.

    When creating class-based strategies, override these methods with proper type hints.
    The 'context' parameter in user methods is actually the TradingAlgorithm instance itself.
    """

    # For subclasses to override - these show the expected signatures
    def initialize(self, context: TradingAlgorithm) -> None: ...
    def handle_data(self, context: TradingAlgorithm, data: Any) -> None: ...
    def before_trading_start(self, context: TradingAlgorithm, data: Any) -> None: ...
    def analyze(self, context: TradingAlgorithm, perf: pd.DataFrame) -> None: ...

    # Core attributes that users access via context
    asset_finder: Any
    portfolio: Any
    account: Any
    blotter: Any

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
