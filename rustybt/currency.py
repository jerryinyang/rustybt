"""ISO 4217 currency identifiers and utilities.

This module provides the Currency class for working with ISO 4217 currency codes.
Currencies are singleton objects - creating a Currency with the same code multiple
times returns the same instance.

The Currency class implements total ordering, allowing currencies to be compared
and sorted.

Examples:
    Create and use currency objects::

        from rustybt.currency import Currency

        usd = Currency('USD')
        print(usd.code)  # 'USD'
        print(usd.name)  # 'US Dollar'

        # Currencies with same code are identical objects
        usd2 = Currency('USD')
        assert usd is usd2

    Compare currencies::

        usd = Currency('USD')
        eur = Currency('EUR')

        # Currencies support comparison
        if usd < eur:
            print('USD comes before EUR alphabetically')

Note:
    Currency objects are immutable and cached. The None currency code
    represents no currency.
"""

from functools import total_ordering

from iso4217 import Currency as ISO4217Currency

_ALL_CURRENCIES: dict[str, "Currency"] = {}


@total_ordering
class Currency:
    """ISO 4217 currency identifier with singleton behavior.

    Represents a currency according to the ISO 4217 standard. Each unique
    currency code maps to a single Currency instance (singleton pattern).
    Supports total ordering for sorting and comparison.

    Args:
        code: ISO 4217 currency code (e.g., 'USD', 'EUR', 'JPY'), or None
            for no currency.

    Attributes:
        code: Three-letter ISO 4217 currency code (e.g., 'USD').
        name: Human-readable currency name (e.g., 'US Dollar').

    Raises:
        ValueError: If code is not a valid ISO 4217 currency code.

    Examples:
        Basic usage::

            from rustybt.currency import Currency

            usd = Currency('USD')
            print(f"{usd.code}: {usd.name}")  # 'USD: US Dollar'

        Singleton behavior::

            usd1 = Currency('USD')
            usd2 = Currency('USD')
            assert usd1 is usd2  # Same object

        Comparison and ordering::

            usd = Currency('USD')
            eur = Currency('EUR')
            jpy = Currency('JPY')

            # Currencies are ordered alphabetically by code
            assert eur < usd < jpy
            currencies = [usd, jpy, eur]
            currencies.sort()  # [EUR, JPY, USD]

        No currency::

            no_currency = Currency(None)
            print(no_currency.name)  # 'NO CURRENCY'
    """

    # Private attributes set in __new__
    _code: str
    _name: str

    def __new__(cls, code):
        try:
            return _ALL_CURRENCIES[code]
        except KeyError:
            if code is None:
                name = "NO CURRENCY"
            else:
                try:
                    name = ISO4217Currency(code).currency_name
                except ValueError as exc:
                    raise ValueError(f"{code!r} is not a valid currency code.") from exc

            obj = _ALL_CURRENCIES[code] = super().__new__(cls)
            obj._code = code
            obj._name = name
            return obj

    @property
    def code(self):
        """ISO-4217 currency code for the currency.

        Returns:
            The three-letter ISO 4217 currency code (e.g., 'USD').
        """
        return self._code

    @property
    def name(self):
        """Plain english name for the currency.

        Returns:
            The human-readable currency name (e.g., 'US Dollar').
        """
        return self._name

    def __eq__(self, other):
        """Check equality based on currency code.

        Args:
            other: Another Currency object to compare with.

        Returns:
            True if both currencies have the same code, False otherwise,
            or NotImplemented if other is not a Currency.
        """
        if type(self) is not type(other):
            return NotImplemented
        return self.code == other.code

    def __hash__(self):
        """Return hash of the currency code."""
        return hash(self.code)

    def __lt__(self, other):
        """Compare currencies alphabetically by code.

        Args:
            other: Another Currency object to compare with.

        Returns:
            True if self.code < other.code alphabetically.
        """
        return self.code < other.code

    def __repr__(self):
        """Return repr string for the currency.

        Returns:
            String representation like "Currency('USD')".
        """
        return f"{type(self).__name__}({self.code!r})"
