"""Exchange information and trading calendar integration.

This module provides the ExchangeInfo class which encapsulates metadata about financial
exchanges where assets are traded. Each ExchangeInfo instance contains:

- Exchange identification (name, canonical name)
- Geographic information (country code)
- Trading calendar integration

The ExchangeInfo class serves as a bridge between asset metadata and trading calendar
functionality, allowing assets to be associated with their exchange's specific trading
hours, holidays, and other calendar-specific behavior.

Examples:
    Create an exchange info instance:
        >>> from rustybt.assets.exchange_info import ExchangeInfo
        >>> nyse = ExchangeInfo("NEW YORK STOCK EXCHANGE", "NYSE", "US")
        >>> print(nyse.canonical_name)
        NYSE
        >>> print(nyse.country_code)
        US

    Access the trading calendar:
        >>> calendar = nyse.calendar
        >>> print(calendar.name)
        NYSE

    Compare exchanges:
        >>> nasdaq = ExchangeInfo("NASDAQ GLOBAL MARKET", "NASDAQ", "US")
        >>> nyse == nasdaq
        False
        >>> nyse2 = ExchangeInfo("NEW YORK STOCK EXCHANGE", "NYSE", "US")
        >>> nyse == nyse2
        True

See Also:
    rustybt.utils.calendar_utils: Trading calendar utilities
    rustybt.assets.AssetFinder: Asset lookup with exchange filtering
"""

from rustybt.utils.calendar_utils import get_calendar


class ExchangeInfo:
    """An exchange where assets are traded.

    This class encapsulates metadata about a financial exchange, including its name,
    canonical identifier, and geographic location. It provides lazy access to the
    exchange's trading calendar for schedule and holiday information.

    Args:
        name: The full name of the exchange (e.g., 'NEW YORK STOCK EXCHANGE' or
            'NASDAQ GLOBAL MARKET'). Can be None if only using canonical_name.
        canonical_name: The canonical/short name of the exchange (e.g., 'NYSE' or
            'NASDAQ'). If None, defaults to the value of `name`.
        country_code: The ISO 3166-1 alpha-2 country code where the exchange is
            located (e.g., 'US', 'GB', 'JP'). Will be converted to uppercase.

    Attributes:
        name: The full exchange name.
        canonical_name: The canonical exchange identifier.
        country_code: The uppercase ISO country code.
        calendar: Lazily-loaded TradingCalendar for this exchange.

    Examples:
        Create a basic exchange:
            >>> nyse = ExchangeInfo("NEW YORK STOCK EXCHANGE", "NYSE", "US")
            >>> print(nyse.canonical_name)
            NYSE

        Access the trading calendar:
            >>> cal = nyse.calendar
            >>> print(cal.name)
            NYSE

        Compare exchanges for equality:
            >>> nasdaq = ExchangeInfo("NASDAQ", "NASDAQ", "US")
            >>> nyse == nasdaq
            False
    """

    def __init__(self, name, canonical_name, country_code):
        """Initialize an ExchangeInfo instance.

        Args:
            name: Full exchange name.
            canonical_name: Canonical exchange identifier (defaults to name if None).
            country_code: ISO 3166-1 alpha-2 country code.
        """
        self.name = name

        if canonical_name is None:
            canonical_name = name

        self.canonical_name = canonical_name
        self.country_code = country_code.upper()

    def __repr__(self):
        """Return a string representation of the ExchangeInfo.

        Returns:
            A string in the format: ExchangeInfo(name, canonical_name, country_code).
        """
        return "%s(%r, %r, %r)" % (
            type(self).__name__,
            self.name,
            self.canonical_name,
            self.country_code,
        )

    @property
    def calendar(self):
        """Get the trading calendar for this exchange.

        The calendar provides information about trading sessions, holidays, open/close
        times, and other schedule-related data specific to this exchange.

        Returns:
            TradingCalendar: The trading calendar associated with this exchange's
                canonical_name.

        Raises:
            ValueError: If no calendar is registered for this exchange's canonical_name.

        Examples:
            >>> nyse = ExchangeInfo("NYSE", "NYSE", "US")
            >>> calendar = nyse.calendar
            >>> sessions = calendar.all_sessions
        """
        return get_calendar(self.canonical_name)

    def __eq__(self, other):
        """Test equality with another ExchangeInfo.

        Two ExchangeInfo instances are equal if their name, canonical_name, and
        country_code attributes are all equal.

        Args:
            other: The object to compare with.

        Returns:
            bool: True if equal, False otherwise, NotImplemented if other is not
                an ExchangeInfo.
        """
        if not isinstance(other, ExchangeInfo):
            return NotImplemented

        return all(
            getattr(self, attr) == getattr(other, attr)
            for attr in ("name", "canonical_name", "country_code")
        )

    def __ne__(self, other):
        """Test inequality with another ExchangeInfo.

        Args:
            other: The object to compare with.

        Returns:
            bool: True if not equal, False otherwise, NotImplemented if other is not
                an ExchangeInfo.
        """
        eq = self == other
        if eq is NotImplemented:
            return NotImplemented
        return not eq
