"""Canonical definitions of country code constants.

This module provides ISO 3166 alpha-2 country codes used throughout rustybt
for identifying the country/exchange of securities. The CountryCode class
serves as a convenient namespace for accessing country codes.

The codes follow ISO 3166-1 alpha-2 standard (two-letter country codes).

Examples:
    Access country codes::

        from rustybt.country import CountryCode

        us_code = CountryCode.UNITED_STATES  # 'US'
        uk_code = CountryCode.UNITED_KINGDOM  # 'GB'
        jp_code = CountryCode.JAPAN  # 'JP'

    Use in asset lookup::

        asset = asset_finder.lookup_symbol(
            'AAPL',
            country_code=CountryCode.UNITED_STATES
        )

Note:
    Country codes are primarily used for disambiguating securities with
    the same symbol in different markets.
"""

from iso3166 import countries_by_name


def code(name):
    """Get ISO 3166 alpha-2 country code for a country name.

    Args:
        name: Full country name as recognized by ISO 3166.

    Returns:
        Two-letter ISO 3166-1 alpha-2 country code.

    Examples:
        >>> code("UNITED STATES")
        'US'
        >>> code("JAPAN")
        'JP'
    """
    return countries_by_name[name].alpha2


class CountryCode:
    """Namespace for ISO 3166 alpha-2 country codes.

    Provides convenient access to two-letter country codes for all major
    markets. All codes are uppercase two-letter strings following the
    ISO 3166-1 alpha-2 standard.

    Attributes:
        Each attribute corresponds to a country name and contains its
        two-letter ISO code. Examples:
        - UNITED_STATES: 'US'
        - UNITED_KINGDOM: 'GB'
        - JAPAN: 'JP'
        - CHINA: 'CN'
        (See class definition for complete list)

    Examples:
        Using country codes::

            from rustybt.country import CountryCode

            # Check country code
            assert CountryCode.UNITED_STATES == 'US'
            assert CountryCode.JAPAN == 'JP'

            # Use in symbol lookup
            asset_finder.lookup_symbol('SONY', CountryCode.JAPAN)
    """

    ARGENTINA = code("ARGENTINA")
    AUSTRALIA = code("AUSTRALIA")
    AUSTRIA = code("AUSTRIA")
    BELGIUM = code("BELGIUM")
    BRAZIL = code("BRAZIL")
    CANADA = code("CANADA")
    CHILE = code("CHILE")
    CHINA = code("CHINA")
    COLOMBIA = code("COLOMBIA")
    CZECH_REPUBLIC = code("CZECHIA")
    DENMARK = code("DENMARK")
    FINLAND = code("FINLAND")
    FRANCE = code("FRANCE")
    GERMANY = code("GERMANY")
    GREECE = code("GREECE")
    HONG_KONG = code("HONG KONG")
    HUNGARY = code("HUNGARY")
    INDIA = code("INDIA")
    INDONESIA = code("INDONESIA")
    IRELAND = code("IRELAND")
    ISRAEL = code("ISRAEL")
    ITALY = code("ITALY")
    JAPAN = code("JAPAN")
    MALAYSIA = code("MALAYSIA")
    MEXICO = code("MEXICO")
    NETHERLANDS = code("NETHERLANDS")
    NEW_ZEALAND = code("NEW ZEALAND")
    NORWAY = code("NORWAY")
    PAKISTAN = code("PAKISTAN")
    PERU = code("PERU")
    PHILIPPINES = code("PHILIPPINES")
    POLAND = code("POLAND")
    PORTUGAL = code("PORTUGAL")
    RUSSIA = code("RUSSIAN FEDERATION")
    SINGAPORE = code("SINGAPORE")
    SOUTH_AFRICA = code("SOUTH AFRICA")
    SOUTH_KOREA = code("KOREA, REPUBLIC OF")
    SPAIN = code("SPAIN")
    SWEDEN = code("SWEDEN")
    SWITZERLAND = code("SWITZERLAND")
    TAIWAN = code("TAIWAN, PROVINCE OF CHINA")
    THAILAND = code("THAILAND")
    TURKEY = code("TÜRKIYE")
    UNITED_KINGDOM = code("UNITED KINGDOM OF GREAT BRITAIN AND NORTHERN IRELAND")
    UNITED_STATES = code("UNITED STATES OF AMERICA")
