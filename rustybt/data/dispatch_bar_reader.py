#
# Copyright 2016 Quantopian, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Bar readers that dispatch to asset-type-specific readers.

This module provides bar readers that route data requests to the appropriate
underlying reader based on the asset type (e.g., Equity vs Future). This allows
a single interface to serve data for multiple asset types from different data sources.
"""
from abc import ABC, abstractmethod

from numpy import full, int64, nan, zeros

from rustybt.utils.memoize import lazyval


class AssetDispatchBarReader(ABC):
    """Abstract bar reader that dispatches to asset-type-specific readers.

    This reader routes data requests to the appropriate underlying reader based
    on asset type. For example, equity data might come from one reader while
    futures data comes from another.

    Args:
        trading_calendar: The trading calendar to use for all readers.
        asset_finder: The AssetFinder to resolve asset identifiers.
        readers: A dict mapping Asset type to the corresponding bar reader
            (either MinuteBarReader or SessionBarReader).
        last_available_dt: The last available timestamp. If not provided,
            infers it by using the max of the last_available_dt values of
            the underlying readers.
    """

    def __init__(
        self,
        trading_calendar,
        asset_finder,
        readers,
        last_available_dt=None,
    ):
        self._trading_calendar = trading_calendar
        self._asset_finder = asset_finder
        self._readers = readers
        self._last_available_dt = last_available_dt

        for t, r in self._readers.items():
            assert trading_calendar == r.trading_calendar, (
                "All readers must share target trading_calendar. "
                f"Reader={r} for type={t} uses calendar={r.trading_calendar} which does not "
                f"match the desired shared calendar={trading_calendar} "
            )

    @abstractmethod
    def _dt_window_size(self, start_dt, end_dt):
        """Calculate the number of time periods between start and end.

        Args:
            start_dt: The start timestamp.
            end_dt: The end timestamp.

        Returns:
            int: The number of periods (minutes or sessions) in the range.
        """
        pass

    @property
    def _asset_types(self):
        """Get the asset types supported by this reader.

        Returns:
            dict_keys: The asset types for which readers are configured.
        """
        return self._readers.keys()

    def _make_raw_array_shape(self, start_dt, end_dt, num_sids):
        """Calculate the shape for raw data arrays.

        Args:
            start_dt: The start timestamp.
            end_dt: The end timestamp.
            num_sids: The number of assets.

        Returns:
            tuple: A (time_periods, num_assets) shape tuple.
        """
        return self._dt_window_size(start_dt, end_dt), num_sids

    def _make_raw_array_out(self, field, shape):
        """Create an output array for the given field and shape.

        Args:
            field: The field name (e.g., 'open', 'close', 'volume', 'sid').
            shape: The shape of the array to create.

        Returns:
            np.ndarray: An array filled with NaN (for price fields) or zeros
                (for volume/sid fields).
        """
        if field != "volume" and field != "sid":
            out = full(shape, nan)
        else:
            out = zeros(shape, dtype=int64)
        return out

    @property
    def trading_calendar(self):
        """The trading calendar used by this reader.

        Returns:
            rustybt.utils.calendar.TradingCalendar: The trading calendar.
        """
        return self._trading_calendar

    @lazyval
    def last_available_dt(self):
        """The last available timestamp across all underlying readers.

        Returns:
            pd.Timestamp: The maximum last_available_dt from all readers.
        """
        if self._last_available_dt is not None:
            return self._last_available_dt
        else:
            return max(r.last_available_dt for r in self._readers.values())

    @lazyval
    def first_trading_day(self):
        """The first trading day across all underlying readers.

        Returns:
            pd.Timestamp: The minimum first_trading_day from all readers.
        """
        return min(r.first_trading_day for r in self._readers.values())

    def get_value(self, sid, dt, field):
        """Get the value for a single asset at a specific time.

        Args:
            sid: The asset identifier.
            dt: The timestamp for the desired value.
            field: The field name (e.g., 'open', 'close', 'volume').

        Returns:
            float or int: The value at the given coordinates.
        """
        asset = self._asset_finder.retrieve_asset(sid)
        r = self._readers[type(asset)]
        return r.get_value(asset, dt, field)

    def get_last_traded_dt(self, asset, dt):
        """Get the last traded time for an asset.

        Args:
            asset: The asset to query.
            dt: The timestamp from which to search backwards.

        Returns:
            pd.Timestamp: The last traded timestamp, or pd.NaT if none found.
        """
        r = self._readers[type(asset)]
        return r.get_last_traded_dt(asset, dt)

    def load_raw_arrays(self, fields, start_dt, end_dt, sids):
        """Load raw data arrays by dispatching to asset-type-specific readers.

        This method groups assets by type, loads data from the appropriate
        reader for each type, and combines the results into unified arrays.

        Args:
            fields: List of field names to load.
            start_dt: Start of the time range.
            end_dt: End of the time range.
            sids: List of asset identifiers.

        Returns:
            list of np.ndarray: One array per field, each with shape
                (time_periods, num_assets).
        """
        asset_types = self._asset_types
        sid_groups = {t: [] for t in asset_types}
        out_pos = {t: [] for t in asset_types}

        assets = self._asset_finder.retrieve_all(sids)

        for i, asset in enumerate(assets):
            t = type(asset)
            if t not in sid_groups:
                sid_groups[t] = []
            if t not in out_pos:
                out_pos[t] = []
            sid_groups[t].append(asset)
            out_pos[t].append(i)

        batched_arrays = {
            t: self._readers[t].load_raw_arrays(fields, start_dt, end_dt, sid_groups[t])
            for t in asset_types
            if sid_groups[t]
        }

        results = []
        shape = self._make_raw_array_shape(start_dt, end_dt, len(sids))

        for i, field in enumerate(fields):
            out = self._make_raw_array_out(field, shape)
            for t, arrays in batched_arrays.items():
                out[:, out_pos[t]] = arrays[i]
            results.append(out)

        return results


class AssetDispatchMinuteBarReader(AssetDispatchBarReader):
    """Dispatch bar reader for minute-frequency data.

    This reader routes minute-level data requests to asset-type-specific
    minute bar readers.
    """

    def _dt_window_size(self, start_dt, end_dt):
        """Calculate the number of minutes in the time range.

        Args:
            start_dt: Start timestamp.
            end_dt: End timestamp.

        Returns:
            int: The number of minutes in the range.
        """
        return len(self.trading_calendar.minutes_in_range(start_dt, end_dt))


class AssetDispatchSessionBarReader(AssetDispatchBarReader):
    """Dispatch bar reader for session (daily) frequency data.

    This reader routes daily-level data requests to asset-type-specific
    session bar readers.
    """

    def _dt_window_size(self, start_dt, end_dt):
        """Calculate the number of sessions in the time range.

        Args:
            start_dt: Start timestamp.
            end_dt: End timestamp.

        Returns:
            int: The number of sessions in the range.
        """
        return len(self.trading_calendar.sessions_in_range(start_dt, end_dt))

    @lazyval
    def sessions(self):
        """Get all sessions covered by this reader.

        Returns:
            pd.DatetimeIndex: All sessions from first_trading_day to
                last_available_dt.
        """
        return self.trading_calendar.sessions_in_range(
            self.first_trading_day, self.last_available_dt
        )
