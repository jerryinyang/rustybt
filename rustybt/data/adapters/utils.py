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


def build_symbol_sid_map(symbols: Iterable[str]) -> dict[str, int]:
    """Build deterministic SID mapping for symbols."""
    mapping: dict[str, int] = {}
    next_sid = 1

    for symbol in symbols:
        normalized_symbol = symbol.upper().strip()
        if normalized_symbol not in mapping:
            mapping[normalized_symbol] = next_sid
            next_sid += 1

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
