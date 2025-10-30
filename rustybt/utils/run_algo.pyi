"""Type stubs for rustybt.utils.run_algo module.

This stub provides type hints for the run_algorithm function,
which is the primary entry point for executing function-based strategies.

IMPORTANT: run_algorithm() ONLY supports function-based strategies.
           For class-based strategies (TradingAlgorithm subclasses),
           use the CLI: rustybt run -f strategy.py
"""

from datetime import datetime
from typing import Callable, Optional, TypeAlias

import pandas as pd
from pandas import DataFrame, Series

from rustybt._protocol import BarData
from rustybt.algorithm import TradingAlgorithm
from rustybt.utils.calendar_utils import TradingCalendar

# Type alias for context (which is the TradingAlgorithm instance)
Context = TradingAlgorithm

# Function signatures for strategy lifecycle functions
InitializeFunc: TypeAlias = Callable[[Context], None]
HandleDataFunc: TypeAlias = Callable[[Context, BarData], None]
BeforeTradingStartFunc: TypeAlias = Callable[[Context, BarData], None]
AnalyzeFunc: TypeAlias = Callable[[Context, DataFrame], None]

def run_algorithm(
    start: datetime | pd.Timestamp | str,
    end: datetime | pd.Timestamp | str,
    initialize: InitializeFunc,
    capital_base: float,
    handle_data: Optional[HandleDataFunc] = None,
    before_trading_start: Optional[BeforeTradingStartFunc] = None,
    analyze: Optional[AnalyzeFunc] = None,
    data_frequency: str = "daily",
    bundle: str = "quantopian-quandl",
    bundle_timestamp: Optional[datetime | pd.Timestamp] = None,
    trading_calendar: Optional[TradingCalendar] = None,
    metrics_set: str = "default",
    benchmark_returns: Optional[Series] = None,
    default_extension: bool = True,
    extensions: tuple = (),
    strict_extensions: bool = True,
    environ: Optional[dict] = None,
    custom_loader: Optional[object] = None,
    blotter: str = "default",
) -> DataFrame:
    """Run a trading algorithm using function-based strategy definition.

    IMPORTANT: This function ONLY supports function-based strategies where you pass
               standalone initialize() and handle_data() functions. For class-based
               strategies that inherit from TradingAlgorithm, use the CLI instead:
               `rustybt run -f strategy.py`

    Args:
        start: Start date for the backtest (datetime, pd.Timestamp, or string 'YYYY-MM-DD')
        end: End date for the backtest (datetime, pd.Timestamp, or string 'YYYY-MM-DD')
        initialize: Function called once at strategy start. Signature: `def initialize(context)`
        capital_base: Starting capital in dollars
        handle_data: Function called on each bar.
            Signature: `def handle_data(context, data)`
        before_trading_start: Function called before market open.
            Signature: `def before_trading_start(context, data)`
        analyze: Function called after backtest completes.
            Signature: `def analyze(context, perf)`
        data_frequency: 'daily' or 'minute'
        bundle: Name of the data bundle to use (e.g., 'quantopian-quandl', 'yfinance-profiling')
        bundle_timestamp: Specific bundle version timestamp
        trading_calendar: Trading calendar to use (defaults to bundle calendar)
        metrics_set: Metrics set name (default: 'default')
        benchmark_returns: Custom benchmark returns series
        default_extension: Whether to load default extensions
        extensions: Additional extensions to load
        strict_extensions: Raise error if extensions fail to load
        environ: Environment variables (defaults to os.environ)
        custom_loader: Custom data loader
        blotter: Blotter type (default: 'default')

    Returns:
        DataFrame containing backtest results with columns:
            - portfolio_value: Total portfolio value over time
            - returns: Period returns
            - transactions: Executed transactions
            - positions: Position history
            - orders: Order history
            - ... (additional metrics based on metrics_set)

    Example (Function-Based Strategy):
        >>> from rustybt.api import symbol, order_target_percent
        >>> import pandas as pd
        >>>
        >>> def initialize(context):
        ...     context.asset = symbol('AAPL')
        >>>
        >>> def handle_data(context, data):
        ...     order_target_percent(context.asset, 1.0)
        >>>
        >>> result = run_algorithm(
        ...     initialize=initialize,
        ...     handle_data=handle_data,
        ...     start=pd.Timestamp('2020-01-01'),
        ...     end=pd.Timestamp('2023-12-31'),
        ...     capital_base=10000,
        ...     bundle='quantopian-quandl'
        ... )
        >>> print(f"Total return: {result['returns'].iloc[-1]:.2%}")

    Raises:
        ValueError: If required parameters are missing or invalid
        TypeError: If passing class-based strategy or incorrect function signatures

    Notes:
        - Functions are standalone, NOT methods
        - Access algorithm state via `context` parameter
        - context.portfolio - Portfolio state
        - context.account - Account state
        - context.symbol('TICKER') - Lookup assets
        - For class-based strategies, use CLI: `rustybt run -f strategy.py`

    See Also:
        - docs/guides/execution-methods.md - Complete execution guide
        - rustybt.algorithm.TradingAlgorithm - For class-based strategies
    """
    ...
