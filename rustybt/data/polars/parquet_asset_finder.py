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

    def _load_from_local_metadata(self) -> tuple[list, dict]:
        """Load symbols and date ranges from bundle's local metadata.db.

        Returns:
            Tuple of (symbols list, date_ranges dict)
        """
        from pathlib import Path

        bundle_path = Path(self.bundle_name)
        if not bundle_path.exists():
            # Bundle name might be relative or just a name
            zipline_root = Path.home() / ".zipline"
            bundle_path = zipline_root / "data" / "bundles" / self.bundle_name

        metadata_db = bundle_path / "metadata.db"
        if not metadata_db.exists():
            logger.debug(
                "local_metadata_not_found",
                path=str(metadata_db),
                message="Falling back to global metadata",
            )
            return [], {}

        engine = create_engine(f"sqlite:///{metadata_db}")
        with Session(engine) as session:
            # Check if required tables exist
            inspector = sa.inspect(engine)
            tables = inspector.get_table_names()

            if "symbols" not in tables:
                logger.debug("symbols_table_not_found", message="Using global metadata")
                return [], {}

            # Load symbols from local metadata.db
            symbols_query = sa.text("SELECT symbol_id, symbol, asset_type, exchange FROM symbols")
            symbol_rows = session.execute(symbols_query).fetchall()

            symbols = [
                {
                    "symbol_id": row[0],
                    "symbol": row[1],
                    "asset_type": row[2] or "equity",
                    "exchange": row[3] or "UNKNOWN",
                }
                for row in symbol_rows
            ]

            # Load date ranges if available
            date_ranges = {}
            if "date_ranges" in tables:
                dr_query = sa.text(
                    "SELECT symbol_id, start_date, end_date, row_count FROM date_ranges"
                )
                dr_rows = session.execute(dr_query).fetchall()

                for row in dr_rows:
                    date_ranges[row[0]] = {
                        "start_date": row[1],
                        "end_date": row[2],
                        "row_count": row[3],
                    }

            logger.info(
                "local_metadata_loaded",
                symbols_count=len(symbols),
                date_ranges_count=len(date_ranges),
            )
            return symbols, date_ranges

    def _load_date_ranges(self) -> dict:
        """Load date ranges from bundle metadata.

        Returns:
            Dictionary mapping sid to {start_date, end_date, row_count}
        """
        from pathlib import Path

        bundle_path = Path(self.bundle_name)
        if not bundle_path.exists():
            # Bundle name might be relative or just a name
            zipline_root = Path.home() / ".zipline"
            bundle_path = zipline_root / "data" / "bundles" / self.bundle_name

        metadata_db = bundle_path / "metadata.db"
        if not metadata_db.exists():
            logger.warning(
                "metadata_db_not_found",
                path=str(metadata_db),
                message="Date ranges not available",
            )
            return {}

        engine = create_engine(f"sqlite:///{metadata_db}")
        with Session(engine) as session:
            # Check if date_ranges table exists
            inspector = sa.inspect(engine)
            if "date_ranges" not in inspector.get_table_names():
                logger.warning(
                    "date_ranges_table_not_found",
                    message="Run scripts/fix_bundle_asset_dates.py to populate date ranges",
                )
                return {}

            # Query date ranges
            query = sa.text("SELECT symbol_id, start_date, end_date, row_count FROM date_ranges")
            result = session.execute(query)

            date_ranges = {}
            for row in result:
                date_ranges[row[0]] = {
                    "start_date": row[1],
                    "end_date": row[2],
                    "row_count": row[3],
                }

            logger.info("date_ranges_loaded", count=len(date_ranges))
            return date_ranges

    def _load_symbols(self):
        """Load symbols from bundle metadata."""
        # Try to load from local bundle metadata.db first (for Parquet bundles)
        symbols, date_ranges = self._load_from_local_metadata()

        # Fallback to global Bundle metadata if local not available
        if not symbols:
            symbols = BundleMetadata.get_symbols(self.bundle_name)
            date_ranges = self._load_date_ranges()

        for sym in symbols:
            sid = sym["symbol_id"]
            symbol = sym["symbol"]
            asset_type = sym.get("asset_type", "equity")
            exchange = sym.get("exchange", "UNKNOWN")

            # Get actual date range for this asset
            date_range = date_ranges.get(sid)
            if date_range:
                start_date = pd.Timestamp(date_range["start_date"])
                end_date = pd.Timestamp(date_range["end_date"])
            else:
                # Fallback to placeholders if no date range found
                logger.warning(
                    "no_date_range_for_asset",
                    sid=sid,
                    symbol=symbol,
                    message="Using placeholder dates",
                )
                start_date = pd.Timestamp("2000-01-01")
                end_date = pd.Timestamp("2099-12-31")

            # Create Asset object based on type
            # Note: exchange_info is the second positional parameter after sid
            if asset_type == "equity":
                asset = Equity(
                    sid,  # First positional arg
                    exchange,  # Second positional arg (exchange_info)
                    symbol=symbol,
                    asset_name=symbol,  # Use symbol as name for now
                    start_date=start_date,
                    end_date=end_date,
                    first_traded=start_date,
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
                    start_date=start_date,
                    end_date=end_date,
                    notice_date=end_date - pd.Timedelta(days=30),  # 30 days before expiry
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

    def lifetimes(self, dates, include_start_date=False, country_codes=None):
        """Compute a DataFrame representing asset lifetimes for the specified dates.

        Parameters
        ----------
        dates : pd.DatetimeIndex
            The dates for which to compute lifetimes.
        include_start_date : bool, optional
            Whether to count the asset as alive on its start_date.
        country_codes : iterable[str], optional
            Filter assets by country code (not implemented for Parquet bundles).

        Returns
        -------
        lifetimes : pd.DataFrame
            A DataFrame with dates as index and sids as columns.
            Contains boolean values indicating whether each asset was alive on each date.
        """
        import numpy as np

        # Get all assets (country_codes filtering not implemented yet)
        all_sids = sorted(self._assets.keys())

        # Create output DataFrame
        lifetimes_data = np.zeros((len(dates), len(all_sids)), dtype=bool)

        # For each asset, determine which dates it was alive
        for col_idx, sid in enumerate(all_sids):
            asset = self._assets[sid]
            start = asset.start_date
            end = asset.end_date

            # Convert to comparable format
            if not isinstance(start, pd.Timestamp):
                start = pd.Timestamp(start)
            if not isinstance(end, pd.Timestamp):
                end = pd.Timestamp(end)

            # Determine lifetime for this asset
            for row_idx, date in enumerate(dates):
                if include_start_date:
                    is_alive = (start <= date) and (date <= end)
                else:
                    is_alive = (start < date) and (date <= end)
                lifetimes_data[row_idx, col_idx] = is_alive

        return pd.DataFrame(
            lifetimes_data,
            index=dates,
            columns=pd.Index(all_sids, dtype="int64"),
        )
