"""Shared helpers for data adapters when writing bundles."""

from __future__ import annotations

from collections.abc import Iterable

import polars as pl

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
