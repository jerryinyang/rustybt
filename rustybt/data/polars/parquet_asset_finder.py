"""AssetFinder adapter for Parquet bundles.

This module provides an AssetFinder that reads asset metadata from
the metadata.db file in Parquet bundles instead of requiring a separate assets.db.
"""

import pandas as pd
import sqlalchemy as sa
import structlog
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from rustybt.assets import Asset, Equity, Future
from rustybt.data.bundles.metadata import BundleMetadata

logger = structlog.get_logger(__name__)


class ParquetAssetFinder:
    """AssetFinder for Parquet bundles that reads from metadata.db.

    This is a lightweight AssetFinder that creates Asset objects on-the-fly
    from symbol metadata stored in the bundle's metadata.db.

    Parameters
    ----------
    bundle_name : str
        Name of the bundle

    Attributes
    ----------
    bundle_name : str
        Name of the bundle
    _assets : dict
        Cache of Asset objects keyed by sid

    Example
    -------
    >>> finder = ParquetAssetFinder("mag-7")
    >>> asset = finder.lookup_symbol("AAPL", as_of_date=None)
    >>> print(asset.symbol)
    'AAPL'
    """

    def __init__(self, bundle_name: str):
        """Initialize asset finder for Parquet bundle.

        Args:
            bundle_name: Name of bundle
        """
        self.bundle_name = bundle_name
        self._assets: dict[int, Asset] = {}
        self._symbol_to_sid: dict[str, int] = {}

        # Load symbols from metadata
        self._load_symbols()

        logger.info(
            "parquet_asset_finder_initialized",
            bundle_name=bundle_name,
            num_assets=len(self._assets),
        )

    def _load_symbols(self):
        """Load symbols from bundle metadata."""
        symbols = BundleMetadata.get_symbols(self.bundle_name)

        for sym in symbols:
            sid = sym["symbol_id"]
            symbol = sym["symbol"]
            asset_type = sym.get("asset_type", "equity")
            exchange = sym.get("exchange", "UNKNOWN")

            # Create Asset object based on type
            # Note: exchange_info is the second positional parameter after sid
            if asset_type == "equity":
                asset = Equity(
                    sid,  # First positional arg
                    exchange,  # Second positional arg (exchange_info)
                    symbol=symbol,
                    asset_name=symbol,  # Use symbol as name for now
                    start_date=pd.Timestamp("2000-01-01"),  # Placeholder
                    end_date=pd.Timestamp("2099-12-31"),  # Placeholder
                    first_traded=pd.Timestamp("2000-01-01"),
                    auto_close_date=None,
                )
            elif asset_type == "future":
                # Extract root symbol (e.g., "ES" from "ESH21")
                # Simple heuristic: first 2-3 chars before digits
                root_symbol = "".join([c for c in symbol if not c.isdigit()])[:3]

                asset = Future(
                    sid,  # First positional arg
                    exchange,  # Second positional arg (exchange_info)
                    symbol=symbol,
                    root_symbol=root_symbol,
                    asset_name=symbol,
                    start_date=pd.Timestamp("2000-01-01"),  # Placeholder
                    end_date=pd.Timestamp("2099-12-31"),  # Placeholder
                    notice_date=pd.Timestamp("2099-12-01"),  # Placeholder
                    expiration_date=pd.Timestamp("2099-12-31"),  # Placeholder
                    auto_close_date=pd.Timestamp("2099-12-31"),
                    first_traded=pd.Timestamp("2000-01-01"),
                    tick_size=0.01,
                    multiplier=1.0,
                )
            else:
                # Generic Asset for other types
                asset = Asset(
                    sid,  # First positional arg
                    exchange,  # Second positional arg (exchange_info)
                    symbol=symbol,
                    asset_name=symbol,
                    start_date=pd.Timestamp("2000-01-01"),
                    end_date=pd.Timestamp("2099-12-31"),
                    first_traded=pd.Timestamp("2000-01-01"),
                    auto_close_date=None,
                )

            self._assets[sid] = asset
            self._symbol_to_sid[symbol] = sid

    def lookup_symbol(self, symbol: str, as_of_date=None, fuzzy=False, country_code=None):
        """Look up an asset by symbol.

        Parameters
        ----------
        symbol : str
            The ticker symbol to resolve.
        as_of_date : pd.Timestamp, optional
            Not used in Parquet bundles (all symbols are available)
        fuzzy : bool, optional
            Not implemented for Parquet bundles
        country_code : str, optional
            Not used in Parquet bundles

        Returns
        -------
        asset : Asset
            The asset with the given symbol

        Raises
        ------
        SymbolNotFound
            If no asset with the given symbol was found
        """
        if symbol not in self._symbol_to_sid:
            from rustybt.errors import SymbolNotFound

            raise SymbolNotFound(symbol=symbol)

        sid = self._symbol_to_sid[symbol]
        return self._assets[sid]

    def retrieve_asset(self, sid: int, default_none: bool = False):
        """Retrieve an asset by sid.

        Parameters
        ----------
        sid : int
            The asset identifier
        default_none : bool, optional
            If True, return None instead of raising SidsNotFound

        Returns
        -------
        asset : Asset or None
            The asset with the given sid

        Raises
        ------
        SidsNotFound
            If no asset with the given sid exists and default_none is False
        """
        if sid in self._assets:
            return self._assets[sid]

        if default_none:
            return None

        from rustybt.errors import SidsNotFound

        raise SidsNotFound(sids=[sid])

    def retrieve_all(self, sids):
        """Retrieve multiple assets by sid.

        Parameters
        ----------
        sids : iterable[int]
            Asset identifiers

        Returns
        -------
        assets : list[Asset]
            List of assets

        Raises
        ------
        SidsNotFound
            If any sid is not found
        """
        return [self.retrieve_asset(sid) for sid in sids]

    def lookup_symbols(self, symbols, as_of_date=None, fuzzy=False):
        """Look up multiple symbols.

        Parameters
        ----------
        symbols : iterable[str]
            Symbols to look up
        as_of_date : pd.Timestamp, optional
            Not used
        fuzzy : bool, optional
            Not implemented

        Returns
        -------
        assets : list[Asset]
            List of assets
        """
        return [self.lookup_symbol(sym, as_of_date, fuzzy) for sym in symbols]

    @property
    def sids(self):
        """Get all sids in the finder.

        Returns
        -------
        sids : pd.Index
            All asset identifiers
        """
        return pd.Index(sorted(self._assets.keys()), dtype="int64")

    def lookup_future_symbol(self, symbol):
        """Futures not supported in Parquet bundles."""
        raise NotImplementedError("Futures not supported in Parquet bundles")
