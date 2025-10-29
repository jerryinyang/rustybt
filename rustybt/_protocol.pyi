"""Type stubs for rustybt._protocol - Compiled Cython module.

This stub file provides type hints and signatures for IDE autocomplete,
type checkers, and documentation tools.
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
    ) -> Union[float, pd.Timestamp, pd.Series, pd.DataFrame]: ...

    def current_chain(
        self,
        continuous_future: ContinuousFuture,
    ) -> list[Asset]: ...
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
    ) -> Union[bool, pd.Series]: ...
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
    ) -> Union[bool, pd.Series]: ...
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
    ) -> Union[pd.Series, pd.DataFrame, np.ndarray]: ...

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

def handle_non_market_minutes(bar_data: BarData): ...
