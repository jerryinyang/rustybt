"""Cython-optimized Asset classes for rustybt.

This module provides high-performance implementations of Asset base classes
including Asset, Equity, and Future. These classes are fundamental to the
backtesting framework and are heavily optimized using Cython.

Optimizations include:
- Cython-compiled comparisons using PyNumber_Index for fast sid comparisons
- Inline property accessors for exchange info
- Efficient serialization via __reduce__ for pickling
- Static typing throughout for C-level performance

Example:
    >>> asset = Equity(
    ...     sid=1234,
    ...     exchange_info=exchange_info,
    ...     symbol='AAPL',
    ...     asset_name='Apple Inc.',
    ...     start_date=pd.Timestamp('2000-01-01', tz='UTC'),
    ...     end_date=pd.Timestamp('2030-12-31', tz='UTC')
    ... )
    >>> asset.is_alive_for_session(pd.Timestamp('2024-01-01', tz='UTC'))
    True

Note:
    This is a Cython extension module for maximum performance. Asset comparisons
    and attribute access are critical hot paths in backtesting.
"""

from typing import Any, Optional

import pandas as pd

from rustybt.assets.exchange_info import ExchangeInfo

class Asset:
    """Base class for entities that can be owned by a trading algorithm.

    Attributes
    ----------
    sid : int
        Persistent unique identifier assigned to the asset.
    symbol : str
        Most recent ticker under which the asset traded.
    asset_name : str
        Full name of the asset.
    exchange : str
        Canonical short name of the exchange (e.g., 'NYSE').
    exchange_full : str
        Full name of the exchange (e.g., 'NEW YORK STOCK EXCHANGE').
    exchange_info : ExchangeInfo
        Information about the exchange this asset is listed on.
    country_code : str
        Two character code indicating the country in which the asset trades.
    start_date : pd.Timestamp
        Date on which the asset first traded.
    end_date : pd.Timestamp
        Last date on which the asset traded.
    tick_size : float
        Minimum amount that the price can change for this asset.
    auto_close_date : pd.Timestamp
        Date on which positions will be automatically liquidated.
    price_multiplier : float
        Price multiplier for this asset.
    """

    sid: int
    symbol: str
    asset_name: str
    exchange_info: ExchangeInfo
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    first_traded: Optional[pd.Timestamp]
    auto_close_date: pd.Timestamp
    tick_size: float
    price_multiplier: float

    @property
    def exchange(self) -> str: ...
    @property
    def exchange_full(self) -> str: ...
    @property
    def country_code(self) -> str: ...
    def __init__(
        self,
        sid: int,
        exchange_info: ExchangeInfo,
        symbol: str = "",
        asset_name: str = "",
        start_date: Optional[pd.Timestamp] = None,
        end_date: Optional[pd.Timestamp] = None,
        first_traded: Optional[pd.Timestamp] = None,
        auto_close_date: Optional[pd.Timestamp] = None,
        tick_size: float = 0.01,
        multiplier: float = 1.0,
    ) -> None: ...
    def __int__(self) -> int: ...
    def __index__(self) -> int: ...
    def __hash__(self) -> int: ...
    def __eq__(self, other: object) -> bool: ...
    def __ne__(self, other: object) -> bool: ...
    def __lt__(self, other: Any) -> bool: ...
    def __le__(self, other: Any) -> bool: ...
    def __gt__(self, other: Any) -> bool: ...
    def __ge__(self, other: Any) -> bool: ...
    def is_alive_for_session(self, session_label: pd.Timestamp) -> bool:
        """Check if asset is alive (tradable) on a given session.

        An asset is alive on a session if that session falls within the
        asset's [start_date, end_date] range.

        Args:
            session_label: Session to check (midnight UTC timestamp).

        Returns:
            True if the asset was trading on that session, False otherwise.

        Example:
            >>> asset.start_date
            Timestamp('2010-01-01 00:00:00+0000', tz='UTC')
            >>> asset.end_date
            Timestamp('2020-12-31 00:00:00+0000', tz='UTC')
            >>> asset.is_alive_for_session(pd.Timestamp('2015-06-01', tz='UTC'))
            True
            >>> asset.is_alive_for_session(pd.Timestamp('2025-01-01', tz='UTC'))
            False

        Note:
            Cython-optimized with int64 comparisons on timestamp values.
        """
        ...
    def is_exchange_open(self, dt_minute: pd.Timestamp) -> bool:
        """Check if the asset's exchange is open at a given minute.

        Args:
            dt_minute: Minute to check (UTC, tz-aware).

        Returns:
            True if the exchange is open at that minute, False otherwise.

        Example:
            >>> # Check if NYSE is open at 10:30 AM ET on a weekday
            >>> dt = pd.Timestamp('2024-01-15 15:30', tz='UTC')  # 10:30 ET
            >>> asset.is_exchange_open(dt)
            True
            >>> # Weekend
            >>> dt = pd.Timestamp('2024-01-13 15:30', tz='UTC')  # Saturday
            >>> asset.is_exchange_open(dt)
            False
        """
        ...
    def from_dict(self, dict_: dict[str, Any]) -> Asset:
        """Construct an Asset from a dictionary.

        Args:
            dict_: Dictionary containing asset attributes.

        Returns:
            New Asset instance.

        Example:
            >>> asset_dict = {
            ...     'sid': 1234,
            ...     'symbol': 'AAPL',
            ...     'exchange_info': exchange_info,
            ...     'start_date': pd.Timestamp('2000-01-01', tz='UTC')
            ... }
            >>> asset = Asset.from_dict(asset_dict)
        """
        ...
    def to_dict(self) -> dict[str, Any]:
        """Convert asset to a dictionary.

        Returns:
            Dictionary containing all asset attributes.

        Example:
            >>> asset_dict = asset.to_dict()
            >>> asset_dict['symbol']
            'AAPL'
            >>> asset_dict['sid']
            1234

        Note:
            Useful for serialization and debugging.
        """
        ...

class Equity(Asset):
    """Asset subclass representing equity securities.

    Equities have additional attributes specific to stocks.
    """

    def __init__(
        self,
        sid: int,
        exchange_info: ExchangeInfo,
        symbol: str = "",
        asset_name: str = "",
        start_date: Optional[pd.Timestamp] = None,
        end_date: Optional[pd.Timestamp] = None,
        first_traded: Optional[pd.Timestamp] = None,
        auto_close_date: Optional[pd.Timestamp] = None,
        tick_size: float = 0.01,
    ) -> None: ...

class Future(Asset):
    """Asset subclass representing futures contracts.

    Futures are derivative contracts with specific expiration dates and
    contract specifications. They have additional attributes beyond base
    Assets to handle futures-specific behavior.

    Attributes:
        notice_date: First date when delivery notice can be issued.
        expiration_date: Last trading date for the contract.
        contract_multiplier: Size of one contract (e.g., 100 for E-mini S&P).
        root_symbol: Root symbol (e.g., 'ES' for E-mini S&P futures).

    Note:
        auto_close_date for futures is set to the earlier of notice_date
        and expiration_date to ensure positions are closed before delivery.
    """

    notice_date: pd.Timestamp
    expiration_date: pd.Timestamp
    contract_multiplier: float
    root_symbol: str

    def __init__(
        self,
        sid: int,
        exchange_info: ExchangeInfo,
        symbol: str = "",
        asset_name: str = "",
        start_date: Optional[pd.Timestamp] = None,
        end_date: Optional[pd.Timestamp] = None,
        first_traded: Optional[pd.Timestamp] = None,
        auto_close_date: Optional[pd.Timestamp] = None,
        notice_date: Optional[pd.Timestamp] = None,
        expiration_date: Optional[pd.Timestamp] = None,
        tick_size: float = 0.01,
        multiplier: float = 1.0,
    ) -> None: ...
