"""Synthetic asset data generators for testing.

This module provides utilities for generating synthetic asset metadata, primarily used
for testing backtesting systems, asset lookups, and data pipeline functionality. The
generators create realistic but artificial asset information that mimics real-world
equity and futures data structures.

Use Cases:
    - Unit testing asset finder and data reader functionality
    - Integration testing backtesting systems
    - Performance benchmarking with controlled datasets
    - Prototyping strategies without requiring real data

Key Functions:
    Equity Generators:
        - make_simple_equity_info: Create basic equities with uniform lifetimes
        - make_rotating_equity_info: Create equities that rotate in/out of existence
        - make_jagged_equity_info: Create equities with staggered end dates
        - make_simple_multi_country_equity_info: Create multi-country equity sets

    Futures Generators:
        - make_future_info: Generic futures contract generator
        - make_commodity_future_info: Commodity-style futures with standard conventions

Examples:
    Create simple equity test data:
        >>> from rustybt.assets.synthetic import make_simple_equity_info
        >>> import pandas as pd
        >>> equities = make_simple_equity_info(
        ...     sids=[1, 2, 3],
        ...     start_date=pd.Timestamp('2020-01-01'),
        ...     end_date=pd.Timestamp('2021-12-31'),
        ...     symbols=['AAPL', 'GOOG', 'MSFT']
        ... )
        >>> print(equities.columns.tolist())
        ['start_date', 'end_date', 'symbol', 'exchange', 'asset_name']

    Create rotating equities for lifecycle testing:
        >>> from rustybt.assets.synthetic import make_rotating_equity_info
        >>> rotating = make_rotating_equity_info(
        ...     num_assets=5,
        ...     first_start=pd.Timestamp('2020-01-01'),
        ...     frequency=pd.DateOffset(days=1),
        ...     periods_between_starts=30,
        ...     asset_lifetime=180
        ... )

    Create commodity futures contracts:
        >>> from rustybt.assets.synthetic import make_commodity_future_info
        >>> futures = make_commodity_future_info(
        ...     first_sid=1000,
        ...     root_symbols=['CL', 'NG'],  # Oil and Natural Gas
        ...     years=[2020, 2021],
        ...     multiplier=1000
        ... )

See Also:
    rustybt.assets.AssetFinder: For looking up generated assets
    rustybt.assets.AssetDBWriter: For persisting synthetic data to database
    rustybt.data.testing: Additional test data utilities

Notes:
    - All generated dates are timezone-naive by default
    - Symbols default to sequential letters (A, B, C, ...)
    - Exchange defaults to 'TEST' for all synthetic assets
    - Future contracts follow CME month code conventions
"""

from itertools import product
from string import ascii_uppercase

import pandas as pd
from pandas.tseries.offsets import MonthBegin

from .futures import CMES_CODE_TO_MONTH


def make_rotating_equity_info(
    num_assets,
    first_start,
    frequency,
    periods_between_starts,
    asset_lifetime,
    exchange="TEST",
):
    """Create synthetic equities that rotate in and out of existence.

    Generates a set of equities where new assets start at regular intervals and each
    asset has a fixed lifetime. This is useful for testing asset lifecycle management,
    including delisting and new listing handling.

    Args:
        num_assets: Number of synthetic equity assets to create.
        first_start: Start date for the first asset in the rotation.
        frequency: Time frequency for interpreting periods (e.g., pd.DateOffset(days=1)
            or a trading day calendar). Can be a string or pandas offset object.
        periods_between_starts: Number of `frequency` periods between each new asset's
            start date. For example, if frequency is 1 day and this is 30, a new asset
            starts every 30 days.
        asset_lifetime: Number of `frequency` periods each asset remains active.
            For example, if frequency is 1 day and this is 180, each asset exists for
            180 days.
        exchange: The exchange identifier for all generated assets. Defaults to "TEST".

    Returns:
        pd.DataFrame: Asset metadata with columns:
            - symbol: Single-letter symbols (A, B, C, ...)
            - start_date: Asset start date
            - end_date: Asset end date
            - exchange: Exchange identifier
            Index is integer range from 0 to num_assets-1.

    Examples:
        Create 5 equities, each lasting 180 days, with new assets starting every 30 days:
            >>> import pandas as pd
            >>> info = make_rotating_equity_info(
            ...     num_assets=5,
            ...     first_start=pd.Timestamp('2020-01-01'),
            ...     frequency=pd.DateOffset(days=1),
            ...     periods_between_starts=30,
            ...     asset_lifetime=180
            ... )
            >>> print(info[['symbol', 'start_date', 'end_date']].head())
    """
    return pd.DataFrame(
        {
            "symbol": [chr(ord("A") + i) for i in range(num_assets)],
            # Start a new asset every `periods_between_starts` days.
            "start_date": pd.date_range(
                first_start,
                freq=(periods_between_starts * frequency),
                periods=num_assets,
            ),
            # Each asset lasts for `asset_lifetime` days.
            "end_date": pd.date_range(
                first_start + (asset_lifetime * frequency),
                freq=(periods_between_starts * frequency),
                periods=num_assets,
            ),
            "exchange": exchange,
        },
        index=range(num_assets),
    )


def make_simple_equity_info(sids, start_date, end_date, symbols=None, names=None, exchange="TEST"):
    """Create synthetic equities with uniform lifetimes.

    Generates a set of equity assets that all exist for the entire duration between
    the specified start and end dates. This is the simplest synthetic asset generator,
    useful for basic testing where asset lifecycle complexity is not needed.

    Args:
        sids: Sequence of integer security identifiers to assign to the assets.
        start_date: Start date for all assets. Will be converted to pd.Timestamp.
        end_date: End date for all assets. Will be converted to pd.Timestamp.
        symbols: Ticker symbols for the assets. If None, generates sequential letters
            'A', 'B', 'C', etc. Must match length of sids if provided.
        names: Full asset names. If None, generates names by appending " INC." to
            each symbol. Must match length of sids if provided.
        exchange: Exchange identifier for all assets. Defaults to "TEST".

    Returns:
        pd.DataFrame: Asset metadata indexed by sids with columns:
            - start_date: Asset start date (all equal)
            - end_date: Asset end date (all equal)
            - symbol: Ticker symbol
            - exchange: Exchange identifier
            - asset_name: Full asset name

    Examples:
        Basic usage with auto-generated symbols:
            >>> import pandas as pd
            >>> info = make_simple_equity_info(
            ...     sids=[1, 2, 3],
            ...     start_date=pd.Timestamp('2020-01-01'),
            ...     end_date=pd.Timestamp('2021-12-31')
            ... )
            >>> print(info['symbol'].tolist())
            ['A', 'B', 'C']

        With custom symbols and names:
            >>> info = make_simple_equity_info(
            ...     sids=[100, 101, 102],
            ...     start_date=pd.Timestamp('2020-01-01'),
            ...     end_date=pd.Timestamp('2021-12-31'),
            ...     symbols=['AAPL', 'GOOG', 'MSFT'],
            ...     names=['Apple Inc.', 'Alphabet Inc.', 'Microsoft Corp.']
            ... )
    """
    num_assets = len(sids)
    if symbols is None:
        symbols = list(ascii_uppercase[:num_assets])
    else:
        symbols = list(symbols)

    if names is None:
        names = [str(s) + " INC." for s in symbols]

    return pd.DataFrame(
        {
            "symbol": symbols,
            "start_date": pd.to_datetime([start_date] * num_assets),
            "end_date": pd.to_datetime([end_date] * num_assets),
            "asset_name": list(names),
            "exchange": exchange,
        },
        index=list(sids),
        columns=(
            "start_date",
            "end_date",
            "symbol",
            "exchange",
            "asset_name",
        ),
    )


def make_simple_multi_country_equity_info(
    countries_to_sids, countries_to_exchanges, start_date, end_date
):
    """Create synthetic equities from multiple countries.

    Generates equity assets distributed across multiple countries/exchanges, useful
    for testing multi-market functionality and country-based filtering.

    Args:
        countries_to_sids: Dictionary mapping country codes to lists of sids for
            that country. Example: {'US': [1, 2, 3], 'GB': [4, 5]}.
        countries_to_exchanges: Dictionary mapping country codes to exchange names.
            Example: {'US': 'NYSE', 'GB': 'LSE'}.
        start_date: Start date for all assets.
        end_date: End date for all assets.

    Returns:
        pd.DataFrame: Asset metadata indexed by sids with columns:
            - start_date: Asset start date
            - end_date: Asset end date
            - symbol: Generated as "COUNTRY-INDEX" (e.g., "US-0", "US-1")
            - exchange: Exchange from countries_to_exchanges mapping
            - asset_name: Same as symbol

    Examples:
        Create US and UK equities:
            >>> import pandas as pd
            >>> info = make_simple_multi_country_equity_info(
            ...     countries_to_sids={'US': [1, 2], 'GB': [3, 4]},
            ...     countries_to_exchanges={'US': 'NYSE', 'GB': 'LSE'},
            ...     start_date=pd.Timestamp('2020-01-01'),
            ...     end_date=pd.Timestamp('2021-12-31')
            ... )
            >>> print(info.loc[1, 'symbol'])  # US-0
            >>> print(info.loc[3, 'exchange'])  # LSE
    """
    sids = []
    symbols = []
    exchanges = []

    for country, country_sids in countries_to_sids.items():
        exchange = countries_to_exchanges[country]
        for i, sid in enumerate(country_sids):
            sids.append(sid)
            symbols.append("-".join([country, str(i)]))
            exchanges.append(exchange)

    return pd.DataFrame(
        {
            "symbol": symbols,
            "start_date": start_date,
            "end_date": end_date,
            "asset_name": symbols,
            "exchange": exchanges,
        },
        index=sids,
        columns=(
            "start_date",
            "end_date",
            "symbol",
            "exchange",
            "asset_name",
        ),
    )


def make_jagged_equity_info(
    num_assets, start_date, first_end, frequency, periods_between_ends, auto_close_delta
):
    """Create synthetic equities with staggered end dates.

    Generates assets that all start on the same date but end at cascading intervals,
    creating a "jagged" pattern of asset lifetimes. Useful for testing handling of
    asset delistings and portfolio rebalancing when assets drop out over time.

    Args:
        num_assets: Number of equity assets to create.
        start_date: Common start date for all assets.
        first_end: End date for the first asset to delist.
        frequency: Time frequency for interpreting periods_between_ends (e.g.,
            pd.DateOffset(days=1) or a trading calendar). Can be string or offset.
        periods_between_ends: Number of `frequency` periods between each successive
            asset's end date. For example, if frequency is 1 day and this is 30,
            assets end 30 days apart.
        auto_close_delta: Offset to add to end_date to set auto_close_date. If None,
            no auto_close_date column is added. Typically a pd.DateOffset or Timedelta.

    Returns:
        pd.DataFrame: Asset metadata with columns:
            - symbol: Single-letter symbols (A, B, C, ...)
            - start_date: All equal to start_date parameter
            - end_date: Cascading dates starting from first_end
            - exchange: All set to "TEST"
            - auto_close_date: (optional) end_date + auto_close_delta
            Index is integer range from 0 to num_assets-1.

    Examples:
        Create equities ending 30 days apart:
            >>> import pandas as pd
            >>> info = make_jagged_equity_info(
            ...     num_assets=5,
            ...     start_date=pd.Timestamp('2020-01-01'),
            ...     first_end=pd.Timestamp('2020-06-01'),
            ...     frequency=pd.DateOffset(days=1),
            ...     periods_between_ends=30,
            ...     auto_close_delta=pd.DateOffset(days=1)
            ... )
            >>> print(info[['symbol', 'end_date']].head())
    """
    frame = pd.DataFrame(
        {
            "symbol": [chr(ord("A") + i) for i in range(num_assets)],
            "start_date": start_date,
            "end_date": pd.date_range(
                first_end,
                freq=(periods_between_ends * frequency),
                periods=num_assets,
            ),
            "exchange": "TEST",
        },
        index=range(num_assets),
    )

    # Explicitly pass None to disable setting the auto_close_date column.
    if auto_close_delta is not None:
        # TODO CHECK PerformanceWarning: Non-vectorized DateOffset
        # being applied to Series or DatetimeIndex
        frame["auto_close_date"] = frame["end_date"] + auto_close_delta

    return frame


def make_future_info(
    first_sid,
    root_symbols,
    years,
    notice_date_func,
    expiration_date_func,
    start_date_func,
    month_codes=None,
    multiplier=500,
):
    """Create synthetic futures contracts with customizable date generation.

    Generates futures contracts for specified root symbols across multiple years and
    months, with flexible date calculation via callback functions. This is the base
    futures generator used by more specialized functions like make_commodity_future_info.

    Args:
        first_sid: Starting security identifier for sid assignment. Sids increment
            sequentially from this value.
        root_symbols: List of futures root symbols (e.g., ['CL', 'NG', 'ES']).
        years: List of years for which to generate contracts (e.g., [2020, 2021] or
            ['2020', '2021']).
        notice_date_func: Callable taking a pd.Timestamp (first of contract month) and
            returning the notice date. Return pd.NaT for contracts without notice dates.
        expiration_date_func: Callable taking a pd.Timestamp (first of contract month)
            and returning the expiration date.
        start_date_func: Callable taking a pd.Timestamp (first of contract month) and
            returning the contract start/listing date.
        month_codes: Dictionary mapping CME month codes to month numbers (1-12).
            If None, uses CMES_CODE_TO_MONTH which includes all 12 months.
        multiplier: Contract multiplier (e.g., 500 for mini contracts, 1000 for full).

    Returns:
        pd.DataFrame: Futures contract metadata indexed by sid with columns:
            - sid: Security identifier
            - root_symbol: Root symbol (e.g., 'CL')
            - symbol: Full contract symbol with month code (e.g., 'CLZ24')
            - start_date: Contract listing date
            - notice_date: First notice date
            - expiration_date: Contract expiration date
            - multiplier: Contract multiplier
            - exchange: Always set to "TEST"

    Examples:
        Create simple futures with standard dates:
            >>> import pandas as pd
            >>> from pandas.tseries.offsets import MonthBegin
            >>> contracts = make_future_info(
            ...     first_sid=1000,
            ...     root_symbols=['ES'],
            ...     years=[2020],
            ...     notice_date_func=lambda dt: dt - MonthBegin(1) + pd.Timedelta(days=14),
            ...     expiration_date_func=lambda dt: dt - MonthBegin(1) + pd.Timedelta(days=19),
            ...     start_date_func=lambda dt: dt - pd.Timedelta(days=365),
            ...     multiplier=50
            ... )
            >>> print(contracts[['symbol', 'expiration_date']].head())

    See Also:
        make_commodity_future_info: Specialized generator for commodity-style futures
    """
    if month_codes is None:
        month_codes = CMES_CODE_TO_MONTH

    year_strs = list(map(str, years))
    years = [pd.Timestamp(s, tz="UTC") for s in year_strs]

    # Pairs of string/date like ('K06', 2006-05-01) sorted by year/month
    # `MonthBegin(month_num - 1)` since the year already starts at month 1.
    contract_suffix_to_beginning_of_month = tuple(
        (month_code + year_str[-2:], year + MonthBegin(month_num - 1))
        for ((year, year_str), (month_code, month_num)) in product(
            zip(years, year_strs, strict=False),
            sorted(list(month_codes.items()), key=lambda item: item[1]),
        )
    )

    contracts = []
    parts = product(root_symbols, contract_suffix_to_beginning_of_month)
    for sid, (root_sym, (suffix, month_begin)) in enumerate(parts, first_sid):
        contracts.append(
            {
                "sid": sid,
                "root_symbol": root_sym,
                "symbol": root_sym + suffix,
                "start_date": start_date_func(month_begin),
                "notice_date": notice_date_func(month_begin),
                "expiration_date": expiration_date_func(month_begin),
                "multiplier": multiplier,
                "exchange": "TEST",
            }
        )
    return pd.DataFrame.from_records(contracts, index="sid")


def make_commodity_future_info(first_sid, root_symbols, years, month_codes=None, multiplier=500):
    """Create synthetic commodity futures with standard date conventions.

    Generates futures contracts following typical physical commodity conventions for
    notice and expiration dates. This is a convenience wrapper around make_future_info
    that applies standard date rules used by commodities like crude oil, natural gas, etc.

    Date Conventions:
        - Notice Date: 20th of the month, two months before contract month
        - Expiration Date: 20th of the month, one month before contract month
        - Start Date: One year before contract month
        - Exchange: "TEST"

    These conventions simulate real commodity contract behavior where physical delivery
    can be required after the notice date, and the contract expires before the actual
    contract month.

    Args:
        first_sid: Starting security identifier for sid assignment.
        root_symbols: List of commodity root symbols (e.g., ['CL', 'NG'] for crude
            oil and natural gas).
        years: List of years for contract generation (e.g., [2020, 2021]).
        month_codes: Dictionary mapping CME month codes to month numbers (1-12).
            If None, uses CMES_CODE_TO_MONTH for all 12 months.
        multiplier: Contract multiplier. Defaults to 500 for mini contracts.

    Returns:
        pd.DataFrame: Futures contract metadata indexed by sid. See make_future_info
            for column details.

    Examples:
        Create oil and gas contracts:
            >>> contracts = make_commodity_future_info(
            ...     first_sid=1000,
            ...     root_symbols=['CL', 'NG'],
            ...     years=[2020, 2021],
            ...     multiplier=1000
            ... )
            >>> # Each root has 12 contracts per year (24 total per root, 48 total)
            >>> print(len(contracts))  # 48
            >>> print(contracts[contracts['root_symbol'] == 'CL'].head())

        Create with specific months only:
            >>> from rustybt.assets.futures import CMES_CODE_TO_MONTH
            >>> # Only March (H), June (M), September (U), December (Z)
            >>> quarterly = {k: v for k, v in CMES_CODE_TO_MONTH.items() if v in [3, 6, 9, 12]}
            >>> contracts = make_commodity_future_info(
            ...     first_sid=2000,
            ...     root_symbols=['ES'],
            ...     years=[2020],
            ...     month_codes=quarterly
            ... )
            >>> print(len(contracts))  # 4 contracts

    See Also:
        make_future_info: Base futures generator with customizable date functions
    """
    nineteen_days = pd.Timedelta(days=19)
    one_year = pd.Timedelta(days=365)
    return make_future_info(
        first_sid=first_sid,
        root_symbols=root_symbols,
        years=years,
        notice_date_func=lambda dt: dt - MonthBegin(2) + nineteen_days,
        expiration_date_func=lambda dt: dt - MonthBegin(1) + nineteen_days,
        start_date_func=lambda dt: dt - one_year,
        month_codes=month_codes,
        multiplier=multiplier,
    )
