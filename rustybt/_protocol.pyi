"""Cython-optimized protocol classes for rustybt backtesting.

This module contains performance-critical implementations of the BarData interface
and related protocol classes used for accessing market data during simulations.

The module is implemented in Cython for maximum performance, with optimizations
including:
- Static typing for all internal variables
- Inline C functions for hot paths
- Minimal Python overhead in data access methods
- Efficient caching of frequently accessed values

Example:
    >>> # BarData is typically passed to algorithm functions
    >>> def handle_data(context, data):
    ...     # data is a BarData instance
    ...     price = data.current(context.asset, 'price')
    ...     history = data.history(context.asset, 'close', 30, '1d')

Note:
    This is a Cython extension module. The .pyx source provides the actual
    implementation; this .pyi file provides type hints for static analysis.
"""

from collections.abc import Iterable
from typing import Callable, Literal, Union, overload

import numpy as np
import pandas as pd

from rustybt.assets import Asset
from rustybt.assets.continuous_futures import ContinuousFuture

class BarData:
    """Provides methods for accessing minutely and daily price/volume data from
    Algorithm API functions.

    Also provides utility methods to determine if an asset is alive, and if it
    has recent trade data.

    An instance of this object is passed as ``data`` to
    :func:`~zipline.api.handle_data` and
    :func:`~zipline.api.before_trading_start`.

    Parameters
    ----------
    data_portal : DataPortal
        Provider for bar pricing data.
    simulation_dt_func : callable
        Function which returns the current simulation time.
        This is usually bound to a method of TradingSimulation.
    data_frequency : {'minute', 'daily'}
        The frequency of the bar data; i.e. whether the data is
        daily or minute bars
    trading_calendar : TradingCalendar
        The trading calendar for the simulation
    restrictions : zipline.finance.asset_restrictions.Restrictions
        Object that combines and returns restricted list information from
        multiple sources
    """

    data_portal: object
    simulation_dt_func: Callable[[], pd.Timestamp]
    data_frequency: str
    current_dt: pd.Timestamp
    fetcher_assets: list[Asset]
    current_session: pd.Timestamp
    current_session_minutes: pd.DatetimeIndex

    def __init__(
        self,
        data_portal: object,
        simulation_dt_func: Callable[[], pd.Timestamp],
        data_frequency: str,
        trading_calendar: object,
        restrictions: object,
    ) -> None: ...

    # Overloads for current() - single asset, single field
    @overload
    def current(
        self,
        assets: Union[Asset, ContinuousFuture, str],
        fields: str,
    ) -> Union[float, pd.Timestamp]: ...

    # Overloads for current() - single asset, multiple fields
    @overload
    def current(
        self,
        assets: Union[Asset, ContinuousFuture, str],
        fields: Iterable[str],
    ) -> pd.Series: ...

    # Overloads for current() - multiple assets, single field
    @overload
    def current(
        self,
        assets: Iterable[Union[Asset, ContinuousFuture, str]],
        fields: str,
    ) -> pd.Series: ...

    # Overloads for current() - multiple assets, multiple fields
    @overload
    def current(
        self,
        assets: Iterable[Union[Asset, ContinuousFuture, str]],
        fields: Iterable[str],
    ) -> pd.DataFrame: ...
    def current(
        self,
        assets: Union[Asset, ContinuousFuture, str, Iterable[Union[Asset, ContinuousFuture, str]]],
        fields: Union[str, Iterable[str]],
    ) -> Union[float, pd.Timestamp, pd.Series, pd.DataFrame]:
        """Get current values for assets and fields at simulation time.

        Returns the most recent data for the requested assets and fields,
        adjusted for corporate actions and forward-filled as appropriate.

        Args:
            assets: Single asset or iterable of assets to query.
            fields: Single field or iterable of fields. Valid fields:
                - 'price': Last known close price (forward-filled, adjusted)
                - 'open': Opening price for current bar (NaN if no trades)
                - 'high': High price for current bar (NaN if no trades)
                - 'low': Low price for current bar (NaN if no trades)
                - 'close': Close price for current bar (NaN if no trades)
                - 'volume': Volume for current bar (0 if no trades)
                - 'last_traded': Timestamp of last trade (NaT if never traded)

        Returns:
            Return type depends on inputs:
            - Single asset + single field → scalar (float or Timestamp)
            - Single asset + multiple fields → Series indexed by field
            - Multiple assets + single field → Series indexed by asset
            - Multiple assets + multiple fields → DataFrame

        Raises:
            ValueError: If field name is invalid or asset is not found.

        Example:
            >>> # Get single price
            >>> price = data.current(asset, 'price')
            >>> # Get OHLC for one asset
            >>> ohlc = data.current(asset, ['open', 'high', 'low', 'close'])
            >>> # Get prices for multiple assets
            >>> prices = data.current([asset1, asset2], 'price')

        Note:
            Cython-optimized for minimal overhead. For minute-frequency data,
            this function is called potentially millions of times per backtest.
        """
        ...

    def current_chain(
        self,
        continuous_future: ContinuousFuture,
    ) -> list[Asset]:
        """Get the current future contract chain for a continuous future.

        Returns the list of active future contracts that make up the chain
        for the specified continuous future at the current simulation time.

        Args:
            continuous_future: The continuous future specification.

        Returns:
            List of Future assets in the chain, ordered by delivery date.

        Example:
            >>> cf = continuous_future('CL', offset=0, roll='calendar')
            >>> chain = data.current_chain(cf)
            >>> front_contract = chain[0]  # Front month
            >>> back_contract = chain[1]   # Second month
        """
        ...
    # Overloads for can_trade() - single asset
    @overload
    def can_trade(
        self,
        assets: Asset,
    ) -> bool: ...

    # Overloads for can_trade() - multiple assets
    @overload
    def can_trade(
        self,
        assets: Iterable[Asset],
    ) -> pd.Series: ...
    def can_trade(
        self,
        assets: Union[Asset, Iterable[Asset]],
    ) -> Union[bool, pd.Series]:
        """Check if assets are currently tradable.

        An asset is tradable if ALL of the following conditions are met:
        1. The asset is alive for the current session
        2. The asset's exchange is open at the current simulation time
        3. There is a known last price for the asset (not NaN)
        4. The asset is not on any restriction lists

        Args:
            assets: Single asset or iterable of assets to check.

        Returns:
            bool or Series[bool]: Tradability status for each asset.

        Example:
            >>> if data.can_trade(asset):
            ...     order(asset, 100)
            >>> tradable = data.can_trade([asset1, asset2, asset3])
            >>> # Only trade assets that are tradable
            >>> for asset in tradable[tradable].index:
            ...     order(asset, 100)

        Note:
            For assets on different exchanges than the simulation calendar,
            this may return False during hours when that exchange is closed.
        """
        ...
    # Overloads for is_stale() - single asset
    @overload
    def is_stale(
        self,
        assets: Asset,
    ) -> bool: ...

    # Overloads for is_stale() - multiple assets
    @overload
    def is_stale(
        self,
        assets: Iterable[Asset],
    ) -> pd.Series: ...
    def is_stale(
        self,
        assets: Union[Asset, Iterable[Asset]],
    ) -> Union[bool, pd.Series]:
        """Check if assets have stale data (alive but no recent trades).

        Returns True if an asset is alive at the current time but has no
        trade data for the current bar. This is useful for detecting
        illiquid or halted securities.

        Args:
            assets: Single asset or iterable of assets to check.

        Returns:
            bool or Series[bool]: Staleness status for each asset.
            - True: Asset is alive but has no current trade data
            - False: Asset has current data OR has never traded

        Example:
            >>> for asset in universe:
            ...     if data.is_stale(asset):
            ...         # Skip illiquid asset
            ...         continue
            ...     else:
            ...         # Trade liquid asset
            ...         order(asset, 100)

        Note:
            An asset that has never traded returns False, not True. The
            distinction is: stale means "was trading but isn't now".
        """
        ...
    # Overloads for history() - DataFrame return (default)
    @overload
    def history(
        self,
        assets: Union[Asset, ContinuousFuture, str, Iterable[Union[Asset, ContinuousFuture, str]]],
        fields: Union[str, Iterable[str]],
        bar_count: int,
        frequency: str,
        return_type: Literal["dataframe"] = "dataframe",
    ) -> Union[pd.Series, pd.DataFrame]: ...

    # Overloads for history() - Array return
    @overload
    def history(
        self,
        assets: Union[Asset, ContinuousFuture, str, Iterable[Union[Asset, ContinuousFuture, str]]],
        fields: Union[str, Iterable[str]],
        bar_count: int,
        frequency: str,
        return_type: Literal["array"],
    ) -> np.ndarray: ...
    def history(
        self,
        assets: Union[Asset, ContinuousFuture, str, Iterable[Union[Asset, ContinuousFuture, str]]],
        fields: Union[str, Iterable[str]],
        bar_count: int,
        frequency: str,
        return_type: Literal["dataframe", "array"] = "dataframe",
    ) -> Union[pd.Series, pd.DataFrame, np.ndarray]:
        """Get trailing window of historical data, adjusted for corporate actions.

        Returns a window of past data for the specified assets and fields,
        with all adjustments (splits, dividends, mergers) applied as of the
        current simulation time.

        Args:
            assets: Asset(s) for which to load data.
            fields: Field(s) to load. Same valid fields as current().
            bar_count: Number of bars to return.
            frequency: Data frequency:
                - '1m': Minutely bars
                - '1d': Daily bars
            return_type: Output format:
                - 'dataframe': pandas DataFrame/Series (default)
                - 'array': NumPy ndarray (~19% faster for numeric operations)

        Returns:
            When return_type='dataframe':
            - Single asset + single field → Series with DatetimeIndex
            - Single asset + multiple fields → DataFrame (bars × fields)
            - Multiple assets + single field → DataFrame (bars × assets)
            - Multiple assets + multiple fields → DataFrame with MultiIndex

            When return_type='array':
            - NumPy array with same logical structure but no labels
            - Shape varies by input combination
            - Faster for strategies doing array-based calculations

        Example:
            >>> # Get 30 days of closing prices
            >>> closes = data.history(asset, 'close', 30, '1d')
            >>> # Calculate 20-day moving average
            >>> sma = closes.mean()
            >>>
            >>> # Use array mode for faster NumPy operations
            >>> close_array = data.history(asset, 'close', 30, '1d', 'array')
            >>> sma = close_array.mean()  # ~19% faster
            >>>
            >>> # Get multiple fields
            >>> ohlcv = data.history(asset, ['open','high','low','close','volume'], 10, '1d')

        Note:
            All data is adjusted for splits/dividends/mergers as of the current
            simulation time. The adjustment calculations use Cython for speed.

            Performance tip: Use return_type='array' when possible for strategies
            that work directly with NumPy arrays, as it avoids DataFrame overhead.
        """
        ...

class InnerPosition:
    """The real values of a position.

    This exists to be owned by both a Position and a protocol.Position
    at the same time without a cycle.
    """

    asset: Asset
    amount: float
    cost_basis: float
    last_sale_price: float
    last_sale_date: pd.Timestamp

    def __init__(
        self,
        asset: Asset,
        amount: float = 0,
        cost_basis: float = 0.0,
        last_sale_price: float = 0.0,
        last_sale_date: pd.Timestamp | None = None,
    ) -> None: ...

def handle_non_market_minutes(bar_data: BarData):
    """Context manager for handling data access during non-market minutes.

    When active, adjusts data lookups to use the previous market minute instead
    of the current simulation time. This is essential for contexts like
    before_trading_start() where the simulation clock is between market sessions.

    Args:
        bar_data: BarData instance to configure for non-market handling.

    Yields:
        None

    Example:
        >>> with handle_non_market_minutes(data):
        ...     # Access data as of previous market close
        ...     price = data.current(asset, 'price')

    Note:
        This is automatically used by the simulation engine; users rarely
        need to call it directly.
    """
    ...
