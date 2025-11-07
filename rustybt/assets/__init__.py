#
# Copyright 2015 Quantopian, Inc.
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

"""Asset management and metadata handling for RustyBT.

This module provides the core asset management infrastructure for RustyBT, including:

- **Asset Types**: Base classes and concrete implementations for different asset types
  (equities, futures, continuous futures)
- **Asset Discovery**: The AssetFinder class for looking up and retrieving assets by
  various identifiers (sids, symbols, supplementary fields)
- **Asset Database**: Tools for writing and managing asset metadata in a SQLite/PostgreSQL
  database
- **Exchange Information**: Exchange metadata and trading calendar integration

The asset system is the foundation for identifying and tracking financial instruments
in backtests and live trading. Assets are uniquely identified by 'sid' (security identifier),
and can be looked up by various attributes like ticker symbols, exchange codes, or custom
supplementary mappings.

Key Classes:
    Asset: Abstract base class for all tradable assets
    Equity: Represents equity securities (stocks)
    Future: Represents futures contracts
    ContinuousFuture: Represents rolling futures contract chains
    AssetFinder: Database-backed asset lookup and discovery
    AssetDBWriter: Tool for writing asset metadata to the database
    ExchangeInfo: Exchange metadata and trading calendar information

Examples:
    Basic asset lookup by sid:
        >>> finder = AssetFinder("sqlite:///assets.db")
        >>> asset = finder.retrieve_asset(1)
        >>> print(asset.symbol)

    Lookup by symbol:
        >>> equity = finder.lookup_symbol("AAPL", as_of_date=pd.Timestamp("2020-01-01"))
        >>> print(equity.asset_name)

    Create and write asset metadata:
        >>> writer = AssetDBWriter("sqlite:///assets.db")
        >>> equities_df = pd.DataFrame({
        ...     'symbol': ['AAPL', 'GOOG'],
        ...     'exchange': ['NYSE', 'NASDAQ'],
        ...     'start_date': pd.Timestamp('2010-01-01'),
        ...     'end_date': pd.Timestamp('2030-01-01')
        ... })
        >>> writer.write(equities=equities_df)

See Also:
    rustybt.data: Data loading and management
    rustybt.finance.trading: Trading calendar utilities
"""

from ._assets import (
    Asset,
    Equity,
    Future,
    make_asset_array,
)
from .asset_db_schema import ASSET_DB_VERSION
from .asset_writer import AssetDBWriter
from .assets import (
    AssetConvertible,
    AssetFinder,
    ContinuousFuture,
    PricingDataAssociable,
)
from .exchange_info import ExchangeInfo

__all__ = [
    "ASSET_DB_VERSION",
    "Asset",
    "AssetConvertible",
    "AssetDBWriter",
    "AssetFinder",
    "ContinuousFuture",
    "Equity",
    "ExchangeInfo",
    "Future",
    "PricingDataAssociable",
    "make_asset_array",
]
