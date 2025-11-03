"""Shared helpers for data adapters when writing bundles."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Iterable
from typing import TypeVar

import polars as pl

T = TypeVar("T")

INTRADAY_FREQUENCIES: set[str] = {
    "1m",
    "5m",
    "15m",
    "30m",
    "1h",
    "1min",
    "5min",
    "15min",
    "30min",
    "60min",
    "1hour",
}


def run_async(coro: Awaitable[T]) -> T:
    """Run async coroutine from sync context, handling existing event loops.

    This function safely runs async code from synchronous context,
    automatically detecting and handling existing event loops (e.g., Jupyter).

    Args:
        coro: Async coroutine to execute

    Returns:
        Result from coroutine execution

    Raises:
        Any exception raised by the coroutine

    Example:
        >>> async def fetch_data():
        ...     return await some_async_function()
        >>> result = run_async(fetch_data())  # Works in both Jupyter and scripts

    Implementation:
        - If no event loop exists: Uses asyncio.run() (creates new loop)
        - If event loop exists (Jupyter): Uses nest_asyncio to enable nested loops
        - nest_asyncio is a core dependency, always available

    Note:
        This function uses nest_asyncio which is a core dependency of rustybt.
        It automatically patches the event loop to allow nested asyncio.run() calls,
        which is required for Jupyter notebook support.
    """
    try:
        # Try to get the running loop (will raise if none exists)
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop - safe to use asyncio.run()
        return asyncio.run(coro)
    else:
        # Running loop exists (e.g., Jupyter) - use nest_asyncio
        # nest_asyncio is a core dependency, so it's always available
        import nest_asyncio

        nest_asyncio.apply(loop)
        return loop.run_until_complete(coro)


def normalize_symbols(symbols: Iterable[str]) -> list[str]:
    """Normalize and de-duplicate symbols while preserving order."""
    normalized: list[str] = []
    seen: set[str] = set()

    for symbol in symbols:
        normalized_symbol = symbol.upper().strip()
        if normalized_symbol not in seen:
            seen.add(normalized_symbol)
            normalized.append(normalized_symbol)

    return normalized


def build_symbol_sid_map(symbols: Iterable[str], bundle_name: str | None = None) -> dict[str, int]:
    """Build deterministic SID mapping for symbols, reusing existing SIDs within bundle.

    First checks if symbols already exist in the specified bundle and reuses
    their existing SIDs. Only assigns new SIDs to symbols that don't exist yet.
    This ensures SID consistency across bundle re-ingestions while keeping
    SIDs independent between different bundles.

    Args:
        symbols: Iterable of symbol strings
        bundle_name: Bundle name to scope SID lookup. If provided, only reuses
                    SIDs from this specific bundle. If None, uses global lookup
                    (legacy behavior, may cause ID conflicts across bundles).

    Returns:
        Dictionary mapping symbols to SIDs

    Example:
        >>> # First ingestion of bundle-A
        >>> map1 = build_symbol_sid_map(["AAPL", "MSFT"], bundle_name="bundle-A")
        >>> # {'AAPL': 1, 'MSFT': 2}
        >>>
        >>> # Re-ingestion of bundle-A - SIDs are reused within same bundle
        >>> map2 = build_symbol_sid_map(["AAPL", "GOOGL"], bundle_name="bundle-A")
        >>> # {'AAPL': 1, 'GOOGL': 3}  <- AAPL keeps SID 1
        >>>
        >>> # First ingestion of bundle-B - gets independent SIDs
        >>> map3 = build_symbol_sid_map(["AAPL", "TSLA"], bundle_name="bundle-B")
        >>> # {'AAPL': 4, 'TSLA': 5}  <- Different SID for AAPL in bundle-B
    """
    from rustybt.data.bundles.metadata import BundleMetadata

    mapping: dict[str, int] = {}

    # Phase 1: Check for existing SIDs in database (within specified bundle if provided)
    for symbol in symbols:
        normalized_symbol = symbol.upper().strip()
        if normalized_symbol in mapping:
            continue  # Already processed (duplicate in input)

        try:
            existing_sid = BundleMetadata.get_symbol_sid(normalized_symbol, bundle_name=bundle_name)
            if existing_sid is not None:
                mapping[normalized_symbol] = existing_sid
        except Exception:  # nosec B110 - Intentional: fail gracefully and assign new SID in phase 2
            # Database access failed, will assign new SID in phase 2
            pass

    # Phase 2: Assign new SIDs to symbols not found in database
    # For symbols that need new SIDs, let the database auto-assign them
    # This avoids race conditions when multiple processes run concurrently
    symbols_needing_sids = [
        symbol.upper().strip() for symbol in symbols if symbol.upper().strip() not in mapping
    ]

    if symbols_needing_sids:
        # Register symbols in database and let it auto-assign SIDs
        # This is done one at a time within a transaction to avoid conflicts
        for symbol in symbols_needing_sids:
            try:
                # add_symbol with sid=None lets the database auto-increment
                # We need a temporary bundle name if none provided
                temp_bundle = bundle_name if bundle_name else "_temp_sid_assignment"

                # This will either insert (new SID) or return existing SID
                sid = BundleMetadata.add_symbol(
                    bundle_name=temp_bundle,
                    symbol=symbol,
                    asset_type=None,  # Will be updated later when writing
                    exchange=None,
                    sid=None,  # Let database auto-assign
                )
                mapping[symbol] = sid
            except Exception:  # nosec B110 - Fail gracefully
                # If database write fails, try to get next ID manually
                try:
                    next_sid = BundleMetadata.get_next_symbol_id()
                    mapping[symbol] = next_sid
                except Exception:
                    # Last resort: use sequential numbering from 1000000
                    mapping[symbol] = 1000000 + len(mapping)

    return mapping


def prepare_ohlcv_frame(
    df: pl.DataFrame,
    symbol_map: dict[str, int],
    frequency: str,
) -> tuple[pl.DataFrame, str]:
    """Convert adapter DataFrame into ParquetWriter schema."""
    if frequency in INTRADAY_FREQUENCIES:
        minute_df = (
            df.with_columns(
                pl.col("symbol").str.to_uppercase().replace(symbol_map).cast(pl.Int64).alias("sid")
            )
            .drop("symbol")
            .select(["timestamp", "sid", "open", "high", "low", "close", "volume"])
        )
        return minute_df, "minute"

    daily_df = (
        df.with_columns(
            [
                pl.col("timestamp").dt.date().alias("date"),
                pl.col("symbol").str.to_uppercase().replace(symbol_map).cast(pl.Int64).alias("sid"),
            ]
        )
        .drop(["timestamp", "symbol"])
        .select(["date", "sid", "open", "high", "low", "close", "volume"])
    )
    return daily_df, "daily"
