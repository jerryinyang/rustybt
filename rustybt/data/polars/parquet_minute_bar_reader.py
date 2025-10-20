"""BarReader adapter for Parquet minute bars.

This module provides a compatibility layer between PolarsParquetMinuteReader
and the existing BarReader interface used by run_algorithm().
"""

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl
import structlog

from rustybt.data.bar_reader import BarReader, NoDataAfterDate, NoDataBeforeDate, NoDataOnDate
from rustybt.data.polars.parquet_minute_bars import PolarsParquetMinuteReader
from rustybt.utils.calendar_utils import get_calendar

logger = structlog.get_logger(__name__)


class ParquetMinuteBarReader(BarReader):
    """BarReader adapter for Parquet minute bundles.

    This class wraps PolarsParquetMinuteReader to provide the MinuteBarReader interface
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
    first_trading_day : pd.Timestamp
        First trading day in the bundle
    last_available_dt : pd.Timestamp
        Last minute in the bundle

    Example
    -------
    >>> reader = ParquetMinuteBarReader(
    ...     bundle_path="~/.zipline/data/bundles/mag-7",
    ...     calendar_name="NYSE",
    ...     start_session=pd.Timestamp("2000-01-01"),
    ...     end_session=pd.Timestamp("2025-01-01")
    ... )
    """

    def __init__(
        self,
        bundle_path: str,
        calendar_name: str,
        start_session: pd.Timestamp,
        end_session: pd.Timestamp,
    ):
        """Initialize Parquet minute bar reader."""
        self.bundle_path = Path(bundle_path).expanduser()
        self._calendar_name = calendar_name
        self._trading_calendar = get_calendar(calendar_name)

        # Normalize timestamps
        self._start_session = pd.Timestamp(start_session).normalize()
        self._end_session = pd.Timestamp(end_session).normalize()

        # Initialize Polars reader
        self._reader = PolarsParquetMinuteReader(
            str(self.bundle_path),
            enable_cache=True,
            enable_metadata_catalog=False,
        )

        # Cache for loaded data
        self._cache: dict[tuple, np.ndarray] = {}

        # Get actual first and last trading minutes
        self._first_trading_day = self._start_session
        self._last_available_dt = pd.Timestamp(
            self._trading_calendar.session_close(self._end_session)
        )

        logger.info(
            "parquet_minute_bar_reader_initialized",
            bundle_path=str(self.bundle_path),
            calendar=calendar_name,
            start_session=str(self._start_session),
            end_session=str(self._end_session),
        )

    @property
    def data_frequency(self):
        """Return 'minute' frequency identifier."""
        return "minute"

    @property
    def trading_calendar(self):
        """Return trading calendar for this bundle."""
        return self._trading_calendar

    @property
    def first_trading_day(self):
        """Return first trading day in bundle."""
        return self._first_trading_day

    @property
    def last_available_dt(self):
        """Return last minute in bundle."""
        return self._last_available_dt

    def load_raw_arrays(self, columns, start_dt, end_dt, assets):
        """Load raw OHLCV arrays for the given datetime range and assets.

        This is the core method used by run_algorithm() to fetch pricing data.

        Parameters
        ----------
        columns : list of str
            Price fields to load ('open', 'high', 'low', 'close', 'volume')
        start_dt : pd.Timestamp
            Start datetime for data
        end_dt : pd.Timestamp
            End datetime for data
        assets : list of int
            Asset IDs (sids) to load

        Returns
        -------
        list of np.ndarray
            List of 2D arrays (minutes × assets) for each requested column.
            Arrays have dtype float64 with shape (num_minutes, num_assets).

        Raises
        ------
        NoDataOnDate
            If start_dt or end_dt is outside calendar range
        """
        # Get all trading minutes in range
        market_opens = self._trading_calendar.session_opens_in_range(
            start_dt.normalize(), end_dt.normalize()
        )
        market_closes = self._trading_calendar.session_closes_in_range(
            start_dt.normalize(), end_dt.normalize()
        )

        # Build list of all minutes
        all_minutes = []
        for open_time, close_time in zip(market_opens, market_closes):
            session_minutes = pd.date_range(open_time, close_time, freq="1min")
            all_minutes.extend(session_minutes)

        all_minutes = pd.DatetimeIndex(all_minutes)

        # Filter to requested range
        all_minutes = all_minutes[(all_minutes >= start_dt) & (all_minutes <= end_dt)]

        num_minutes = len(all_minutes)
        num_assets = len(assets)

        # Check cache
        cache_key = (tuple(columns), start_dt, end_dt, tuple(assets))
        if cache_key in self._cache:
            logger.debug("cache_hit", cache_key=cache_key)
            return self._cache[cache_key]

        # Load data from Parquet
        try:
            # Convert pd.Timestamp to datetime for Polars
            start_datetime = start_dt.to_pydatetime()
            end_datetime = end_dt.to_pydatetime()

            df = self._reader.load_minute_bars(
                sids=list(assets),
                start_dt=start_datetime,
                end_dt=end_datetime,
                fields=list(columns),
            )
        except Exception as e:
            logger.error(
                "parquet_load_failed",
                error=str(e),
                start_dt=str(start_dt),
                end_dt=str(end_dt),
                num_assets=num_assets,
            )
            # Return empty arrays filled with NaN
            return [np.full((num_minutes, num_assets), np.nan, dtype=np.float64) for _ in columns]

        # Convert Polars DataFrame to NumPy arrays
        # Create empty arrays filled with NaN
        arrays = [np.full((num_minutes, num_assets), np.nan, dtype=np.float64) for _ in columns]

        if len(df) == 0:
            logger.warning(
                "no_data_found",
                start_dt=str(start_dt),
                end_dt=str(end_dt),
                assets=assets,
            )
            return arrays

        # Convert to pandas for easier indexing
        df_pandas = df.to_pandas()

        # Convert datetime column if needed
        if "dt" in df_pandas.columns:
            df_pandas["dt"] = pd.to_datetime(df_pandas["dt"])

        # Fill arrays with data
        for col_idx, column in enumerate(columns):
            try:
                # Pivot to get datetimes × assets matrix
                pivoted = df_pandas.pivot(index="dt", columns="sid", values=column)

                # Align with requested minute range and assets
                for minute_idx, target_minute in enumerate(all_minutes):
                    if target_minute in pivoted.index:
                        for asset_idx, asset_id in enumerate(assets):
                            if asset_id in pivoted.columns:
                                value = pivoted.loc[target_minute, asset_id]
                                if pd.notna(value):
                                    # Convert Decimal to float64
                                    arrays[col_idx][minute_idx, asset_idx] = float(value)

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
            num_minutes=num_minutes,
            num_assets=num_assets,
            start_dt=str(start_dt),
            end_dt=str(end_dt),
        )

        return arrays

    def get_value(self, sid, dt, field):
        """Get single value for asset at specific datetime.

        Parameters
        ----------
        sid : int
            Asset ID
        dt : pd.Timestamp
            Datetime for which to retrieve value
        field : str
            Field name ('open', 'high', 'low', 'close', 'volume')

        Returns
        -------
        float or int
            Value for the field (float for OHLC, int for volume)

        Raises
        ------
        NoDataOnDate
            If datetime is outside bundle range
        NoDataBeforeDate
            If datetime is before asset's first available datetime
        NoDataAfterDate
            If datetime is after asset's last available datetime
        """
        # Normalize timestamp
        dt = pd.Timestamp(dt)

        # Check if datetime is in valid range
        if dt < self._first_trading_day or dt > self._last_available_dt:
            raise NoDataOnDate(f"Datetime {dt} not in bundle range")

        # Load single value
        try:
            dt_python = dt.to_pydatetime()

            df = self._reader.load_spot_value(
                sids=[sid],
                target_dt=dt_python,
                field=field,
            )

            if len(df) == 0:
                # Check if this is before/after asset range
                first_dt = self._reader.get_first_available_dt(sid)
                last_dt = self._reader.get_last_available_dt(sid)

                if first_dt is None or last_dt is None:
                    raise NoDataOnDate(f"No data for asset {sid}")

                first_dt_pd = pd.Timestamp(first_dt)
                last_dt_pd = pd.Timestamp(last_dt)

                if dt < first_dt_pd:
                    raise NoDataBeforeDate(f"No data for asset {sid} before {first_dt}")
                if dt > last_dt_pd:
                    raise NoDataAfterDate(f"No data for asset {sid} after {last_dt}")

                raise NoDataOnDate(f"No data for asset {sid} at {dt}")

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
            raise NoDataOnDate(f"Failed to get value for {sid} at {dt}: {e}") from e

    def get_last_traded_dt(self, asset, dt):
        """Get last datetime on or before dt when asset traded.

        Parameters
        ----------
        asset : Asset or int
            Asset or asset ID
        dt : pd.Timestamp
            Reference datetime

        Returns
        -------
        pd.Timestamp
            Last traded datetime, or pd.NaT if no trades found
        """
        # Extract sid if Asset object passed
        sid = asset.sid if hasattr(asset, "sid") else asset

        # Search backwards from dt for non-zero volume
        search_dt = pd.Timestamp(dt)

        # Get trading minutes for session
        session = search_dt.normalize()
        market_open = self._trading_calendar.session_open(session)
        market_close = self._trading_calendar.session_close(session)

        # Generate minutes from dt backwards to market open
        minutes = pd.date_range(market_close, market_open, freq="-1min")
        minutes = minutes[minutes <= search_dt]

        for minute in minutes:
            try:
                volume = self.get_value(sid, minute, "volume")
                if volume > 0:
                    return minute
            except (NoDataOnDate, NoDataBeforeDate, NoDataAfterDate):
                continue

        return pd.NaT

    def sid_day_index(self, sid, day):
        """Not implemented for minute data - use get_value instead."""
        raise NotImplementedError("sid_day_index not applicable for minute data")
