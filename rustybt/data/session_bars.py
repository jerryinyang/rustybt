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

"""Session-frequency bar readers for daily OHLCV data.

This module defines abstract base classes for reading pricing data at a session
(daily) frequency, with support for currency-aware implementations.
"""

from abc import abstractmethod

from rustybt.data.bar_reader import BarReader


class SessionBarReader(BarReader):
    """Abstract base class for readers providing session-frequency OHLCV data.

    Session frequency means daily bars, where each bar represents a full trading
    session. This is in contrast to minute-frequency data.

    Implementations must provide methods to load raw arrays of pricing data and
    retrieve spot values for specific dates and assets.

    Examples:
        Implementing a custom session bar reader:
            >>> class MySessionBarReader(SessionBarReader):
            ...     @property
            ...     def sessions(self):
            ...         return self._calendar.sessions
            ...
            ...     def load_raw_arrays(self, columns, start_date, end_date, assets):
            ...         # Load OHLCV arrays from your data source
            ...         return [open_array, high_array, low_array, close_array, volume_array]

    See Also:
        MinuteBarReader: Reader for minute-frequency pricing data
        CurrencyAwareSessionBarReader: Session reader with currency support
    """

    @property
    def data_frequency(self):
        """Return the data frequency ('session' for daily data).

        Returns:
            str: Always returns 'session' to indicate daily frequency.
        """
        return "session"

    @property
    @abstractmethod
    def sessions(self):
        """Get all session labels (trading days) available from this reader.

        Returns:
            DatetimeIndex: All trading session labels for which the reader can
                provide data, unioning the date ranges across all assets.

        Note:
            Sessions are trading days only - weekends and holidays are excluded
            based on the trading calendar used by this reader.
        """


class CurrencyAwareSessionBarReader(SessionBarReader):
    """Session bar reader that tracks listing currencies for multi-currency assets.

    Extends SessionBarReader to provide currency information for each asset,
    enabling proper handling of price data when assets are quoted in different
    currencies (e.g., USD, EUR, JPY).

    This is essential for:
        - International portfolios with assets from multiple countries
        - Currency conversion in performance calculations
        - Accurate P&L attribution across currencies

    Examples:
        Get currency codes for assets:
            >>> reader = MySessionBarReader(...)
            >>> sids = np.array([1, 2, 3])
            >>> currencies = reader.currency_codes(sids)
            >>> currencies
            array(['USD', 'EUR', 'JPY'], dtype=object)

        Check currency before price retrieval:
            >>> sid = 123
            >>> currency = reader.currency_codes(np.array([sid]))[0]
            >>> if currency == 'USD':
            ...     price = reader.get_value(sid, date, 'close')

    See Also:
        SessionBarReader: Base class for session-frequency readers
        HDF5DailyBarReader: HDF5-based implementation with currency support
        BcolzDailyBarReader: Bcolz-based implementation
    """

    @abstractmethod
    def currency_codes(self, sids):
        """Get listing currencies for requested asset identifiers.

        Assumes that each asset's prices are always quoted in a single currency
        throughout its lifetime.

        Args:
            sids: Array of asset identifiers (sids) as int64 values.

        Returns:
            Array of ISO 4217 currency code strings (e.g., 'USD', 'EUR', 'GBP')
            for each sid. Returns None for sids whose currency is unknown or
            not tracked.

        Examples:
            Get currencies for multiple assets:
                >>> sids = np.array([100, 200, 300])
                >>> currencies = reader.currency_codes(sids)
                >>> currencies
                array(['USD', 'EUR', 'JPY'], dtype=object)

            Handle unknown currencies:
                >>> sids = np.array([999])  # Unknown sid
                >>> currencies = reader.currency_codes(sids)
                >>> currencies
                array([None], dtype=object)

        Note:
            - Currency codes should follow ISO 4217 standard (3-letter codes)
            - Returns None for sids not found in the reader
            - Assumes currency doesn't change over an asset's lifetime
        """
