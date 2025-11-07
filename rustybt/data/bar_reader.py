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
"""Abstract base classes and exceptions for reading bar data.

This module defines the BarReader interface for accessing OHLCV (Open, High,
Low, Close, Volume) pricing data at various frequencies (minute/daily). It also
defines exceptions for handling missing data scenarios.
"""
from abc import ABC, abstractmethod


class NoDataOnDate(Exception):
    """
    Raised when a spot price cannot be found for the sid and date.
    """

    pass


class NoDataBeforeDate(NoDataOnDate):
    """Raised when requested data is before the first available date."""

    pass


class NoDataAfterDate(NoDataOnDate):
    """Raised when requested data is after the last available date."""

    pass


class NoDataForSid(Exception):
    """
    Raised when the requested sid is missing from the pricing data.
    """

    pass


OHLCV = ("open", "high", "low", "close", "volume")


class BarReader(ABC):
    """Abstract base class for reading bar (OHLCV) pricing data.

    This interface defines the contract for accessing historical OHLCV data
    for assets. Implementations provide either minute-level or daily-level
    data access.
    """

    @property
    @abstractmethod
    def data_frequency(self):
        """The frequency of data provided by this reader.

        Returns:
            str: Either 'minute' or 'daily'.
        """
        pass

    @abstractmethod
    def load_raw_arrays(self, columns, start_date, end_date, assets):
        """Load raw OHLCV data arrays for the specified assets and date range.

        Args:
            columns: List of column names to load. Valid values are 'open',
                'high', 'low', 'close', or 'volume'.
            start_date: Beginning of the window range.
            end_date: End of the window range.
            assets: List of asset identifiers (sids) in the window.

        Returns:
            list of np.ndarray: A list with an entry per field of ndarrays with
                shape (time periods in range, num assets) with dtype float64,
                containing the values for the respective field over the start
                and end date range.
        """
        pass

    @property
    @abstractmethod
    def last_available_dt(self):
        """The last session for which the reader can provide data.

        Returns:
            pd.Timestamp: The last session for which the reader can provide data.
        """
        pass

    @property
    @abstractmethod
    def trading_calendar(self):
        """The trading calendar used to read the data.

        Returns:
            rustybt.utils.calendar.TradingCalendar or None: The trading calendar
                used to read the data. Can be None if the writer didn't specify it.
        """
        pass

    @property
    @abstractmethod
    def first_trading_day(self):
        """The first trading day for which the reader can provide data.

        Returns:
            pd.Timestamp: The first trading day (session) for which the reader
                can provide data.
        """
        pass

    @abstractmethod
    def get_value(self, sid, dt, field):
        """Retrieve the value at the given coordinates.

        Args:
            sid: The asset identifier.
            dt: The timestamp for the desired data point.
            field: The OHLVC field name for the desired data point.

        Returns:
            float or int: The value at the given coordinates. Returns float for
                OHLC fields, int for 'volume'.

        Raises:
            NoDataOnDate: If the given dt is not a valid market minute (in
                minute mode) or session (in daily mode) according to this
                reader's trading calendar.
        """
        pass

    @abstractmethod
    def get_last_traded_dt(self, asset, dt):
        """Get the latest time on or before dt in which the asset traded.

        If there are no trades on or before dt, returns pd.NaT.

        Args:
            asset: The asset for which to get the last traded time.
            dt: The timestamp at which to start searching for the last
                traded time.

        Returns:
            pd.Timestamp: The timestamp of the last trade for the given asset,
                using the input dt as a vantage point. Returns pd.NaT if no
                trades found.
        """
        pass
