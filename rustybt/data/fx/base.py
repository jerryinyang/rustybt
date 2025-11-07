"""Foreign exchange (FX) rate reader interface.

This module provides the abstract base class for reading foreign exchange rates
in rustybt. FX rates are used to convert asset values between currencies during
backtesting of multi-currency portfolios.

The FXRateReader interface supports multiple named rate types (e.g., "mid", "bid",
"ask") and provides efficient batch lookups for currency conversions across time.

Example:
    Implement a custom FX rate reader:

    >>> class CustomFXReader(FXRateReader):
    ...     def get_rates(self, rate, quote, bases, dts):
    ...         # Load rates from your data source
    ...         rates = load_fx_data(rate, quote, bases, dts)
    ...         return rates
    >>>
    >>> # Use the reader
    >>> reader = CustomFXReader()
    >>> # Get single rate
    >>> rate = reader.get_rate_scalar('mid', 'USD', 'EUR', pd.Timestamp('2023-01-01'))
    >>> # Get batch rates
    >>> rates = reader.get_rates('mid', 'USD', ['EUR', 'GBP'], date_range)
"""
from abc import ABC, abstractmethod

import numpy as np
import pandas as pd

from rustybt.lib._factorize import factorize_strings
from rustybt.utils.date_utils import make_utc_aware
from rustybt.utils.sentinel import sentinel

DEFAULT_FX_RATE = sentinel("DEFAULT_FX_RATE")


class FXRateReader(ABC):
    """Abstract base class for reading foreign exchange rates.

    An FX rate reader provides access to one or more named "rates", each representing
    a collection of exchange rate mappings from (quote, base, dt) -> float.

    Each rate represents a distinct data source or methodology (e.g., "mid", "bid",
    "ask", "london_close", "nyse_close"). The reader converts amounts from base
    currencies to a quote currency at specific dates.

    Implementations must provide the get_rates() method. The base class automatically
    provides convenience methods for scalar and columnar lookups.

    Methods:
        get_rates: Load 2D array of rates (abstract, must implement)
        get_rate_scalar: Load single scalar rate (provided)
        get_rates_columnar: Load 1D array of parallel rates (provided)

    Example:
        Implement a simple FX reader:

        >>> class SimpleFXReader(FXRateReader):
        ...     def get_rates(self, rate, quote, bases, dts):
        ...         # Return identity rates (1.0) for simplicity
        ...         return np.ones((len(dts), len(bases)))
        >>>
        >>> reader = SimpleFXReader()
        >>> # Convert 100 EUR to USD on a specific date
        >>> rate = reader.get_rate_scalar('mid', 'USD', 'EUR', pd.Timestamp('2023-01-01'))
        >>> amount_usd = 100 * rate

    Notes:
        - All datetime values must be timezone-aware (UTC)
        - Dates in get_rates() must be sorted in ascending order
        - Base currency arrays may contain duplicates
    """

    @abstractmethod
    def get_rates(self, rate, quote, bases, dts):
        """Load a 2D array of FX rates for multiple currencies and dates.

        Returns exchange rates for the cartesian product of base currencies
        and dates. Rows correspond to dates, columns to base currencies.

        Args:
            rate: Name of the rate to load (e.g., 'mid', 'bid', 'ask').
            quote: Currency code to convert into (e.g., 'USD').
            bases: Array of currency codes to convert from (e.g., ['EUR', 'GBP']).
                May contain duplicate currencies.
            dts: Datetimes for rate lookups. Must be sorted ascending and
                localized to UTC.

        Returns:
            np.ndarray: Array of shape (len(dts), len(bases)) containing exchange
                rates. Element [i, j] is the rate to convert bases[j] to quote
                on dts[i].

        Example:
            >>> rates = reader.get_rates(
            ...     'mid',
            ...     'USD',
            ...     np.array(['EUR', 'GBP', 'JPY'], dtype=object),
            ...     pd.date_range('2023-01-01', periods=5, tz='UTC')
            ... )
            >>> print(rates.shape)
            (5, 3)  # 5 dates × 3 currencies
            >>> # Rate to convert EUR to USD on first date
            >>> eur_to_usd = rates[0, 0]
        """

    def get_rate_scalar(self, rate, quote, base, dt):
        """Load a single scalar FX rate value.

        Convenience method for loading a single exchange rate. Delegates
        to get_rates() and extracts the scalar result.

        Args:
            rate: Name of the rate to load (e.g., 'mid', 'bid', 'ask').
            quote: Currency code to convert into (e.g., 'USD').
            base: Currency code to convert from (e.g., 'EUR').
            dt: Datetime for rate lookup (np.datetime64 or pd.Timestamp).

        Returns:
            float: Exchange rate from base to quote on dt.

        Example:
            >>> # Get EUR to USD rate on a specific date
            >>> rate = reader.get_rate_scalar('mid', 'USD', 'EUR',
            ...                               pd.Timestamp('2023-06-15'))
            >>> print(f"1 EUR = {rate:.4f} USD")
            1 EUR = 1.0950 USD
            >>> # Convert 100 EUR to USD
            >>> amount_usd = 100 * rate
        """
        rates_2d = self.get_rates(
            rate,
            quote,
            bases=np.array([base], dtype=object),
            dts=make_utc_aware(pd.DatetimeIndex([dt])),
        )
        return rates_2d[0, 0]

    def get_rates_columnar(self, rate, quote, bases, dts):
        """Load a 1D array of FX rates from parallel currency and date arrays.

        Performs FX rate lookups for parallel arrays of currencies and dates,
        returning one rate per (base, dt) pair. This is more efficient than
        repeated scalar lookups when currencies and dates are not aligned.

        Args:
            rate: Name of the rate to load (e.g., 'mid', 'bid', 'ask').
            quote: Currency code to convert into (e.g., 'USD').
            bases: Array of currency codes, parallel to dts. May contain
                duplicates and does not need to be sorted.
            dts: Datetimes parallel to bases. May contain duplicates and
                does not need to be sorted.

        Returns:
            np.ndarray: 1D array of shape (len(bases),) where element [i] is the
                exchange rate from bases[i] to quote on dts[i].

        Raises:
            ValueError: If len(bases) != len(dts).

        Example:
            >>> # Convert different currencies on different dates
            >>> currencies = np.array(['EUR', 'GBP', 'EUR', 'JPY'], dtype=object)
            >>> dates = pd.DatetimeIndex(['2023-01-01', '2023-01-02',
            ...                           '2023-01-03', '2023-01-02'], tz='UTC')
            >>> rates = reader.get_rates_columnar('mid', 'USD', currencies, dates)
            >>> print(rates.shape)
            (4,)
            >>> # Element [0] = EUR->USD on 2023-01-01
            >>> # Element [1] = GBP->USD on 2023-01-02
            >>> # Element [2] = EUR->USD on 2023-01-03
            >>> # Element [3] = JPY->USD on 2023-01-02

        Notes:
            This method is equivalent to:
                [get_rate_scalar(rate, quote, b, d) for b, d in zip(bases, dts)]
            but much more efficient as it batches the underlying data access.
        """
        if len(bases) != len(dts):
            raise ValueError(f"len(bases) ({len(bases)}) != len(dts) ({len(dts)})")

        bases_ix, unique_bases, _ = factorize_strings(
            bases,
            missing_value=None,
            # Only dts need to be sorted, not bases.
            sort=False,
        )
        # NOTE: np.unique returns unique_dts in sorted order, which is required
        # for calling get_rates.
        unique_dts, dts_ix = np.unique(dts.values, return_inverse=True)
        rates_2d = self.get_rates(rate, quote, unique_bases, pd.DatetimeIndex(unique_dts, tz="utc"))
        return rates_2d[dts_ix, bases_ix]
