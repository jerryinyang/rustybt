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

        # Initialize Polars reader
        self._reader = PolarsParquetDailyReader(
            str(self.bundle_path),
            enable_cache=True,
            enable_metadata_catalog=False,
        )

        # Cache for loaded data
        self._cache: dict[tuple, np.ndarray] = {}

        logger.info(
            "parquet_bar_reader_initialized",
            bundle_path=str(self.bundle_path),
            calendar=calendar_name,
            start_session=str(self._start_session),
            end_session=str(self._end_session),
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
                    target_date_date = target_date.date()

                    if target_date_date in pivoted.index:
                        for asset_idx, asset_id in enumerate(assets):
                            if asset_id in pivoted.columns:
                                value = pivoted.loc[target_date_date, asset_id]
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
        sid : int
            Asset ID
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
        # Normalize timestamp
        dt = pd.Timestamp(dt).normalize()

        # Check if date is in sessions
        if dt not in self.sessions:
            raise NoDataOnDate(f"Date {dt} not in calendar {self._calendar_name}")

        # Load single value
        try:
            df = self._reader.load_spot_value(
                sids=[sid],
                target_date=dt.date(),
                field=field,
            )

            if len(df) == 0:
                # Check if this is before/after asset range
                first_date = self._reader.get_first_available_date(sid)
                last_date = self._reader.get_last_available_date(sid)

                if first_date is None or last_date is None:
                    raise NoDataOnDate(f"No data for asset {sid}")

                if dt.date() < first_date:
                    raise NoDataBeforeDate(f"No data for asset {sid} before {first_date}")
                if dt.date() > last_date:
                    raise NoDataAfterDate(f"No data for asset {sid} after {last_date}")

                raise NoDataOnDate(f"No data for asset {sid} on {dt}")

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
                sid=sid,
                dt=str(dt),
                field=field,
                error=str(e),
            )
            raise NoDataOnDate(f"Failed to get value for {sid} on {dt}: {e}") from e

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
