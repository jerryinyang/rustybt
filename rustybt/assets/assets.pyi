"""Type stubs for rustybt.assets.assets - AssetFinder class.

Provides type hints for asset lookup and retrieval operations in trading strategies.
"""

from typing import Any, Sequence

import pandas as pd

from rustybt.assets import Asset, Equity, Future

class AssetFinder:
    """Interface to asset metadata database.

    Provides methods for looking up assets by ID (sid) or symbol.
    Accessible in strategies via context.asset_finder.

    Attributes
    ----------
    sids : pd.Index
        Index of all asset identifiers (sids) in the database.
    """

    sids: pd.Index

    def __init__(
        self, engine: str | Any, future_chain_predicates: dict[str, Any] | None = None
    ) -> None: ...
    def retrieve_asset(self, sid: int, default_none: bool = False) -> Asset: ...
    def retrieve_all(self, sids: Sequence[int], default_none: bool = False) -> list[Asset]: ...
    def retrieve_equities(self, sids: Sequence[int]) -> list[Equity]: ...
    def retrieve_futures_contracts(self, sids: Sequence[int]) -> list[Future]: ...
    def lookup_symbol(
        self,
        symbol: str,
        as_of_date: pd.Timestamp | None,
        fuzzy: bool = False,
        country_code: str | None = None,
    ) -> Asset: ...
    def lookup_symbols(
        self,
        symbols: Sequence[str],
        as_of_date: pd.Timestamp | None,
        fuzzy: bool = False,
        country_code: str | None = None,
    ) -> list[Asset]: ...
    def lookup_future_symbol(self, symbol: str) -> Future: ...
