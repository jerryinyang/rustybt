"""
Asset configuration utilities for rustybt.

This module provides configuration for asset-specific behaviors like
fractional order handling.
"""

from enum import Enum


class FractionalOrderMode(Enum):
    """Configuration for how to handle fractional order amounts.

    Attributes
    ----------
    AUTO : str
        Automatically detect based on asset exchange.
        Crypto exchanges (binance, coinbase, etc.) allow fractional orders.
        Traditional exchanges require integer share counts.
        This is the recommended default.

    ALWAYS : str
        Always preserve fractional amounts for all assets.
        Useful for backtesting strategies that assume fractional shares.

    NEVER : str
        Always round to integer share counts for all assets.
        Useful for ensuring traditional equity behavior across all assets.

    Examples
    --------
    >>> from rustybt import run_algorithm
    >>> from rustybt.finance.asset_config import FractionalOrderMode
    >>>
    >>> # Auto-detect (default) - crypto gets fractional, equities get integer
    >>> results = run_algorithm(
    ...     start=start_date,
    ...     end=end_date,
    ...     initialize=initialize,
    ...     handle_data=handle_data,
    ...     fractional_order_mode=FractionalOrderMode.AUTO,  # default
    ... )
    >>>
    >>> # Always allow fractional for all assets
    >>> results = run_algorithm(
    ...     start=start_date,
    ...     end=end_date,
    ...     initialize=initialize,
    ...     handle_data=handle_data,
    ...     fractional_order_mode=FractionalOrderMode.ALWAYS,
    ... )
    """

    AUTO = "auto"
    ALWAYS = "always"
    NEVER = "never"


# Known cryptocurrency exchanges for auto-detection
CRYPTO_EXCHANGES = frozenset(
    {
        "binance",
        "coinbase",
        "kraken",
        "ftx",
        "okex",
        "huobi",
        "bybit",
        "kucoin",
        "gateio",
        "bitfinex",
        "gemini",
        "crypto.com",
        "bitstamp",
        "bittrex",
        "poloniex",
    }
)


def is_crypto_exchange(asset):
    """Check if an asset is from a cryptocurrency exchange.

    Parameters
    ----------
    asset : Asset
        The asset to check.

    Returns
    -------
    bool
        True if the asset is from a known crypto exchange, False otherwise.

    Examples
    --------
    >>> from rustybt.data.bundles.core import load
    >>> bundle_data = load("binance-spot-1d")
    >>> af = bundle_data.asset_finder
    >>> btc = af.lookup_symbol('BTC/USDT', as_of_date=None)
    >>> is_crypto_exchange(btc)
    True
    """
    if not hasattr(asset, "exchange_info"):
        return False

    exchange = str(asset.exchange_info).lower()
    return any(crypto_ex in exchange for crypto_ex in CRYPTO_EXCHANGES)


def should_use_fractional_orders(asset, mode):
    """Determine if fractional orders should be used for an asset.

    Parameters
    ----------
    asset : Asset
        The asset to check.
    mode : FractionalOrderMode
        The fractional order mode configuration.

    Returns
    -------
    bool
        True if fractional orders should be preserved, False if they should
        be rounded to integers.

    Examples
    --------
    >>> from rustybt.finance.asset_config import (
    ...     FractionalOrderMode, should_use_fractional_orders
    ... )
    >>> # Auto mode - checks exchange
    >>> should_use_fractional_orders(btc_asset, FractionalOrderMode.AUTO)
    True
    >>> should_use_fractional_orders(aapl_asset, FractionalOrderMode.AUTO)
    False
    >>>
    >>> # Always mode - all assets
    >>> should_use_fractional_orders(aapl_asset, FractionalOrderMode.ALWAYS)
    True
    >>>
    >>> # Never mode - no assets
    >>> should_use_fractional_orders(btc_asset, FractionalOrderMode.NEVER)
    False
    """
    if mode == FractionalOrderMode.ALWAYS:
        return True
    elif mode == FractionalOrderMode.NEVER:
        return False
    elif mode == FractionalOrderMode.AUTO:
        return is_crypto_exchange(asset)
    else:
        # Default to auto behavior
        return is_crypto_exchange(asset)
