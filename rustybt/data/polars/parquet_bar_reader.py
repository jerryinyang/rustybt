"""BarReader adapter for Parquet bundles.

This module provides a compatibility layer between PolarsParquetDailyReader
and the existing BarReader interface used by run_algorithm().
"""

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl
import structlog

from rustybt.data.bar_reader import NoDataAfterDate, NoDataBeforeDate, NoDataOnDate
from rustybt.data.polars.parquet_daily_bars import PolarsParquetDailyReader
from rustybt.data.session_bars import CurrencyAwareSessionBarReader
from rustybt.utils.calendar_utils import get_calendar

logger = structlog.get_logger(__name__)


class ParquetDailyBarReader(CurrencyAwareSessionBarReader):
    """BarReader adapter for Parquet bundles created by ingest-unified.

    This class wraps PolarsParquetDailyReader to provide the BarReader interface
    expected by run_algorithm() and other Zipline components.

    Parameters
    ----------
    bundle_path : str
        Path to bundle directory (e.g., "~/.zipline/data/bundles/mag-7")
    calendar_name : str
        Trading calendar name (e.g., "NYSE", "24/7")
    start_session : pd.Timestamp
        First session in the bundle
    end_session : pd.Timestamp
        Last session in the bundle

    Attributes
    ----------
    trading_calendar : TradingCalendar
        Trading calendar for this bundle
    sessions : pd.DatetimeIndex
        All trading sessions in the bundle date range
    first_trading_day : pd.Timestamp
        First trading day in the bundle
    last_available_dt : pd.Timestamp
        Last trading day in the bundle

    Example
    -------
    >>> reader = ParquetDailyBarReader(
    ...     bundle_path="~/.zipline/data/bundles/mag-7",
    ...     calendar_name="NYSE",
    ...     start_session=pd.Timestamp("2000-01-01"),
    ...     end_session=pd.Timestamp("2025-01-01")
    ... )
    >>> # Use with run_algorithm() via bundles.load()
    """

    def __init__(
        self,
        bundle_path: str,
        calendar_name: str,
        start_session: pd.Timestamp,
        end_session: pd.Timestamp,
    ):
        """Initialize Parquet daily bar reader."""
        self.bundle_path = Path(bundle_path).expanduser()
        self._calendar_name = calendar_name
        self._trading_calendar = get_calendar(calendar_name)

        # Normalize timestamps to midnight UTC
        self._start_session = pd.Timestamp(start_session).normalize()
        self._end_session = pd.Timestamp(end_session).normalize()

        # Ensure sessions are within calendar's valid range
        calendar_first = self._trading_calendar.first_session
        calendar_last = self._trading_calendar.last_session

        if self._start_session < calendar_first:
            logger.warning(
                "parquet_bar_reader_start_adjusted",
                requested_start=str(self._start_session),
                calendar_first=str(calendar_first),
                message=f"Bundle start session {self._start_session.date()} is before "
                f"calendar's first session {calendar_first.date()}. Adjusting to calendar's first session.",
            )
            self._start_session = calendar_first

        if self._end_session > calendar_last:
            logger.warning(
                "parquet_bar_reader_end_adjusted",
                requested_end=str(self._end_session),
                calendar_last=str(calendar_last),
                message=f"Bundle end session {self._end_session.date()} is after "
                f"calendar's last session {calendar_last.date()}. Adjusting to calendar's last session.",
            )
            self._end_session = calendar_last

        # Initialize Polars reader
        self._reader = PolarsParquetDailyReader(
            str(self.bundle_path),
            enable_cache=True,
            enable_metadata_catalog=False,
        )

        # Cache for loaded data
        self._cache: dict[tuple, np.ndarray] = {}

        # Verify actual data range matches requested range
        # This catches metadata mismatches where bundle claims wider date range
        # than actual Parquet files contain
        self._verify_and_adjust_data_range()

        logger.info(
            "parquet_bar_reader_initialized",
            bundle_path=str(self.bundle_path),
            calendar=calendar_name,
            start_session=str(self._start_session),
            end_session=str(self._end_session),
        )

    def _verify_and_adjust_data_range(self) -> None:
        """Verify actual data range and adjust sessions if needed.

        Scans actual Parquet data to find the true date range with data.
        Adjusts start_session and end_session if actual data is more limited
        than what the bundle metadata claims.

        This handles cases where bundle metadata is outdated or incorrect.
        """
        try:
            # Scan Parquet files to get list of available SIDs
            daily_bars_path = self.bundle_path / "daily_bars"
            if not daily_bars_path.exists():
                logger.warning(
                    "daily_bars_not_found",
                    message="Cannot verify data range - daily_bars directory not found",
                )
                return

            # Get a sample of parquet files to check (may be in year=XXXX subdirectories)
            parquet_files = list(daily_bars_path.glob("**/*.parquet"))
            if not parquet_files:
                logger.warning(
                    "no_parquet_files",
                    message="Cannot verify data range - no Parquet files found",
                )
                return

            # Read one file to get sample SIDs
            import polars as pl

            df = pl.read_parquet(str(parquet_files[0]))
            sample_sids = df["sid"].unique().to_list()[:10]  # Check first 10 assets only

            if not sample_sids:
                logger.warning(
                    "no_assets_found",
                    message="Cannot verify data range - no assets found in Parquet files",
                )
                return

            # Sample a few assets to find actual data range
            actual_first = None
            actual_last = None

            for sid in sample_sids:
                first = self._reader.get_first_available_date(sid)
                last = self._reader.get_last_available_date(sid)

                if first is not None:
                    first_ts = pd.Timestamp(first)
                    if actual_first is None or first_ts < actual_first:
                        actual_first = first_ts

                if last is not None:
                    last_ts = pd.Timestamp(last)
                    if actual_last is None or last_ts > actual_last:
                        actual_last = last_ts

            if actual_first is None or actual_last is None:
                logger.warning(
                    "no_actual_data_found",
                    message="Cannot verify data range - no actual data found in Parquet files",
                )
                return

            # Adjust start_session if actual data starts later
            if actual_first > self._start_session:
                logger.warning(
                    "data_range_adjusted_to_actual",
                    metadata_start=str(self._start_session),
                    actual_start=str(actual_first),
                    message=f"Bundle metadata claims data starts at {self._start_session.date()}, "
                    f"but actual data starts at {actual_first.date()}. Adjusting to actual data range.",
                )
                self._start_session = actual_first

            # Adjust end_session if actual data ends earlier
            if actual_last < self._end_session:
                logger.warning(
                    "data_range_adjusted_to_actual",
                    metadata_end=str(self._end_session),
                    actual_end=str(actual_last),
                    message=f"Bundle metadata claims data ends at {self._end_session.date()}, "
                    f"but actual data ends at {actual_last.date()}. Adjusting to actual data range.",
                )
                self._end_session = actual_last

        except Exception as e:
            logger.warning(
                "data_range_verification_failed",
                error=str(e),
                message=f"Could not verify actual data range: {e}",
            )

    @property
    def data_frequency(self):
        """Return 'daily' frequency identifier."""
        return "daily"

    @property
    def trading_calendar(self):
        """Return trading calendar for this bundle."""
        return self._trading_calendar

    @property
    def sessions(self):
        """Return all trading sessions in bundle date range."""
        return self._trading_calendar.sessions_in_range(
            self._start_session,
            self._end_session,
        )

    @property
    def first_trading_day(self):
        """Return first trading day in bundle."""
        return self._start_session

    @property
    def last_available_dt(self):
        """Return last trading day in bundle."""
        return self._end_session

    def load_raw_arrays(self, columns, start_date, end_date, assets):
        """Load raw OHLCV arrays for the given date range and assets.

        This is the core method used by run_algorithm() to fetch pricing data.

        Parameters
        ----------
        columns : list of str
            Price fields to load ('open', 'high', 'low', 'close', 'volume')
        start_date : pd.Timestamp
            Start date for data
        end_date : pd.Timestamp
            End date for data
        assets : list of int
            Asset IDs (sids) to load

        Returns
        -------
        list of np.ndarray
            List of 2D arrays (dates × assets) for each requested column.
            Arrays have dtype float64 with shape (num_dates, num_assets).

        Raises
        ------
        NoDataOnDate
            If start_date or end_date is outside calendar range
        """
        # Validate dates are in calendar
        try:
            start_idx = self.sessions.get_loc(start_date)
            end_idx = self.sessions.get_loc(end_date)
        except KeyError as exc:
            raise NoDataOnDate(
                f"Date not in calendar: {start_date if start_date not in self.sessions else end_date}"
            ) from exc

        num_dates = end_idx - start_idx + 1
        num_assets = len(assets)

        # Check cache
        cache_key = (tuple(columns), start_date, end_date, tuple(assets))
        if cache_key in self._cache:
            logger.debug("cache_hit", cache_key=cache_key)
            return self._cache[cache_key]

        # Load data from Parquet
        try:
            df = self._reader.load_daily_bars(
                sids=list(assets),
                start_date=start_date.date(),
                end_date=end_date.date(),
                fields=list(columns),
            )
        except Exception as e:
            logger.error(
                "parquet_load_failed",
                error=str(e),
                start_date=str(start_date),
                end_date=str(end_date),
                num_assets=num_assets,
            )
            # Return empty arrays filled with NaN
            return [np.full((num_dates, num_assets), np.nan, dtype=np.float64) for _ in columns]

        # Convert Polars DataFrame to NumPy arrays
        # Create empty arrays filled with NaN
        arrays = [np.full((num_dates, num_assets), np.nan, dtype=np.float64) for _ in columns]

        if len(df) == 0:
            logger.warning(
                "no_data_found",
                start_date=str(start_date),
                end_date=str(end_date),
                assets=assets,
            )
            return arrays

        # Convert to pandas for easier pivoting
        # (Polars pivot is less mature than pandas for this use case)
        df_pandas = df.to_pandas()

        # Fill arrays with data
        for col_idx, column in enumerate(columns):
            # Pivot to get dates × assets matrix
            try:
                pivoted = df_pandas.pivot(index="date", columns="sid", values=column)

                # Align with requested date range and assets
                for date_idx in range(num_dates):
                    target_date = self.sessions[start_idx + date_idx]
                    # Convert to pandas Timestamp for comparison with pivoted.index
                    target_ts = pd.Timestamp(target_date)

                    if target_ts in pivoted.index:
                        for asset_idx, asset in enumerate(assets):
                            # Extract SID - assets can be Asset objects or integers
                            asset_sid = asset.sid if hasattr(asset, "sid") else asset

                            if asset_sid in pivoted.columns:
                                value = pivoted.loc[target_ts, asset_sid]
                                if pd.notna(value):
                                    # Convert Decimal to float64
                                    arrays[col_idx][date_idx, asset_idx] = float(value)

            except Exception as e:
                logger.error(
                    "pivot_failed",
                    column=column,
                    error=str(e),
                )
                continue

        # Cache the result
        self._cache[cache_key] = arrays

        logger.info(
            "arrays_loaded",
            num_columns=len(columns),
            num_dates=num_dates,
            num_assets=num_assets,
            start_date=str(start_date),
            end_date=str(end_date),
        )

        return arrays

    def get_value(self, sid, dt, field):
        """Get single value for asset at specific date.

        Parameters
        ----------
        sid : int or Asset
            Asset ID or Asset object
        dt : pd.Timestamp
            Date for which to retrieve value
        field : str
            Field name ('open', 'high', 'low', 'close', 'volume')

        Returns
        -------
        float or int
            Value for the field (float for OHLC, int for volume)

        Raises
        ------
        NoDataOnDate
            If date is outside bundle range or not in calendar
        NoDataBeforeDate
            If date is before asset's first available date
        NoDataAfterDate
            If date is after asset's last available date
        """
        # Extract SID if Asset object is passed
        asset_sid = sid.sid if hasattr(sid, "sid") else sid

        # Normalize timestamp
        dt = pd.Timestamp(dt).normalize()

        # Check if date is in sessions
        if dt not in self.sessions:
            raise NoDataOnDate(f"Date {dt} not in calendar {self._calendar_name}")

        # Load single value
        try:
            df = self._reader.load_spot_value(
                sids=[asset_sid],
                target_date=dt.date(),
                field=field,
            )

            if len(df) == 0:
                # Check if this is before/after asset range
                first_date = self._reader.get_first_available_date(asset_sid)
                last_date = self._reader.get_last_available_date(asset_sid)

                if first_date is None or last_date is None:
                    raise NoDataOnDate(f"No data for asset {asset_sid}")

                if dt.date() < first_date:
                    raise NoDataBeforeDate(f"No data for asset {asset_sid} before {first_date}")
                if dt.date() > last_date:
                    raise NoDataAfterDate(f"No data for asset {asset_sid} after {last_date}")

                raise NoDataOnDate(f"No data for asset {asset_sid} on {dt}")

            # Extract value
            value = df[field][0]

            # Convert Decimal to native Python type
            if field == "volume":
                return int(value)
            else:
                return float(value)

        except (NoDataOnDate, NoDataBeforeDate, NoDataAfterDate):
            raise
        except Exception as e:
            logger.error(
                "get_value_failed",
                sid=asset_sid,
                dt=str(dt),
                field=field,
                error=str(e),
            )
            raise NoDataOnDate(f"Failed to get value for {asset_sid} on {dt}: {e}") from e

    def get_last_traded_dt(self, asset, dt):
        """Get last date on or before dt when asset traded.

        Parameters
        ----------
        asset : Asset or int
            Asset or asset ID
        dt : pd.Timestamp
            Reference date

        Returns
        -------
        pd.Timestamp
            Last traded date, or pd.NaT if no trades found
        """
        # Extract sid if Asset object passed
        sid = asset.sid if hasattr(asset, "sid") else asset

        # Normalize timestamp
        dt = pd.Timestamp(dt).normalize()

        # Search backwards from dt for non-zero volume
        search_date = dt
        sessions_list = list(self.sessions)

        while search_date >= self.first_trading_day:
            try:
                volume = self.get_value(sid, search_date, "volume")
                if volume > 0:
                    return search_date
            except (NoDataOnDate, NoDataBeforeDate, NoDataAfterDate):
                pass

            # Move to previous session
            try:
                idx = sessions_list.index(search_date)
                if idx == 0:
                    break
                search_date = sessions_list[idx - 1]
            except (ValueError, IndexError):
                break

        return pd.NaT

    def currency_codes(self, sids):
        """Get currency codes for assets.

        Parameters
        ----------
        sids : np.array[int64]
            Asset IDs

        Returns
        -------
        np.array[object]
            Array of currency codes (all 'USD' for now, can be extended)
        """
        # For now, assume all assets are quoted in USD
        # This can be extended to read from bundle metadata
        return np.array(["USD"] * len(sids), dtype=object)
