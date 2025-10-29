"""Type stubs for rustybt.assets._assets - Compiled Cython module.

This stub file provides type hints and signatures for core Asset classes.
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
    def is_alive_for_session(self, session_label: pd.Timestamp) -> bool: ...
    def is_exchange_open(self, dt_minute: pd.Timestamp) -> bool: ...
    def from_dict(self, dict_: dict[str, Any]) -> Asset: ...
    def to_dict(self) -> dict[str, Any]: ...

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

    Futures have additional attributes like expiration, multiplier, etc.
    """

    notice_date: pd.Timestamp
    expiration_date: pd.Timestamp
    contract_multiplier: float
    underlying: Optional[str]

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
