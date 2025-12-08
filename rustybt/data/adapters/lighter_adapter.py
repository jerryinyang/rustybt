"""Lighter.xyz data adapter for OHLCV data ingestion.

This module provides integration with Lighter DEX for historical OHLCV data
retrieval, asset discovery, and funding rate fetching.

Fetches candlestick data from Lighter.xyz /candlesticks endpoint.
Supports multiple timeframes and historical data retrieval.
"""

import asyncio
import re
import time
from decimal import Decimal
from typing import Any

import aiohttp
import pandas as pd
import polars as pl
import structlog

from rustybt.data.adapters.base import BaseDataAdapter, ValidationError

logger = structlog.get_logger(__name__)


# OHLCV schema for Lighter.xyz data
LIGHTER_OHLCV_SCHEMA = {
    "timestamp": pl.Datetime("us"),
    "symbol": pl.Utf8,
    "open": pl.Decimal(precision=18, scale=8),
    "high": pl.Decimal(precision=18, scale=8),
    "low": pl.Decimal(precision=18, scale=8),
    "close": pl.Decimal(precision=18, scale=8),
    "volume": pl.Decimal(precision=18, scale=8),
}

# Timeframe mapping: rustybt format -> Lighter.xyz API format (minutes)
TIMEFRAME_MAP = {
    "1m": "1",
    "5m": "5",
    "15m": "15",
    "1h": "60",
    "4h": "240",
    "1d": "1440",
}


class LighterDataError(Exception):
    """Base exception for Lighter data adapter errors."""


class LighterConnectionError(LighterDataError):
    """Connection error to Lighter.xyz API."""


class LighterRateLimitError(LighterDataError):
    """Rate limit exceeded on Lighter.xyz API."""


class LighterDataAdapter(BaseDataAdapter):
    """Lighter.xyz data adapter for OHLCV data ingestion.

    Fetches candlestick data from Lighter.xyz /candlesticks endpoint.
    Supports multiple timeframes and historical data retrieval.

    Features:
        - Asset discovery with filtering by category and pattern
        - Multi-timeframe OHLCV data fetching with pagination
        - Data standardization to rustybt schema
        - Validation of OHLCV relationships
        - Funding rate fetching for perpetual contracts

    Example:
        >>> adapter = LighterDataAdapter(testnet=True)
        >>> assets = await adapter.get_available_assets()
        >>> df = await adapter.fetch(
        ...     symbols=["BTC-PERP"],
        ...     start_date=pd.Timestamp("2024-01-01"),
        ...     end_date=pd.Timestamp("2024-12-01"),
        ...     resolution="1h"
        ... )
    """

    # API endpoints
    BASE_URL = "https://mainnet.zklighter.elliot.ai"
    TESTNET_URL = "https://testnet.zklighter.elliot.ai"

    # Rate limits
    REQUESTS_PER_SECOND = 10  # Conservative rate limit
    MAX_CANDLES_PER_REQUEST = 1000

    def __init__(
        self,
        testnet: bool = True,
        rate_limit_per_second: int = 10,
        max_retries: int = 3,
        timeout: float = 30.0,
    ) -> None:
        """Initialize Lighter data adapter.

        Args:
            testnet: Use testnet API (default True, per ADR-003)
            rate_limit_per_second: Maximum requests per second
            max_retries: Maximum retry attempts for transient errors
            timeout: HTTP request timeout in seconds
        """
        super().__init__(
            name="lighter",
            rate_limit_per_second=rate_limit_per_second,
            max_retries=max_retries,
        )

        self._testnet = testnet
        self._base_url = self.TESTNET_URL if testnet else self.BASE_URL
        self._timeout = aiohttp.ClientTimeout(total=timeout)

        # HTTP session (initialized lazily)
        self._session: aiohttp.ClientSession | None = None

        # Cache for assets (TTL-based)
        self._assets_cache: list[dict] | None = None
        self._assets_cache_time: float = 0
        self._assets_cache_ttl: float = 300.0  # 5 minutes

        logger.info(
            "lighter_data_adapter_initialized",
            testnet=testnet,
            base_url=self._base_url,
            rate_limit=rate_limit_per_second,
        )

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session.

        Returns:
            Async HTTP session
        """
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                base_url=self._base_url,
                timeout=self._timeout,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "rustybt-data-adapter/1.0",
                },
            )
        return self._session

    async def close(self) -> None:
        """Close HTTP session and clean up resources."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
            logger.info("lighter_data_adapter_closed")

    # =========================================================================
    # Asset Discovery (AC1, AC2, AC3, AC4)
    # =========================================================================

    async def get_available_assets(self) -> list[dict]:
        """List all tradeable pairs from Lighter.xyz.

        Returns:
            List of asset dictionaries with keys:
            - symbol: Trading pair symbol (e.g., "BTC-PERP")
            - base: Base asset (e.g., "BTC")
            - quote: Quote asset (e.g., "USD")
            - category: "perpetual" or "spot"
            - min_size: Minimum order size
            - tick_size: Price tick size

        Raises:
            LighterConnectionError: If API request fails
        """
        # Check cache
        now = time.monotonic()
        if (
            self._assets_cache is not None
            and (now - self._assets_cache_time) < self._assets_cache_ttl
        ):
            logger.debug("assets_cache_hit", count=len(self._assets_cache))
            return self._assets_cache

        # Acquire rate limit token
        await self.rate_limiter.acquire()

        session = await self._get_session()

        try:
            async with session.get("/api/v1/markets") as response:
                if response.status == 429:
                    raise LighterRateLimitError("Rate limit exceeded")
                response.raise_for_status()
                data = await response.json()

            assets = []
            markets = data.get("markets", data.get("data", []))

            if isinstance(markets, dict):
                # Handle nested market structure
                markets = list(markets.values())

            for market in markets:
                asset = self._parse_market_to_asset(market)
                if asset:
                    assets.append(asset)

            # Update cache
            self._assets_cache = assets
            self._assets_cache_time = now

            logger.info(
                "assets_discovered",
                count=len(assets),
                perpetuals=len([a for a in assets if a["category"] == "perpetual"]),
                spot=len([a for a in assets if a["category"] == "spot"]),
            )

            return assets

        except aiohttp.ClientResponseError as e:
            if e.status == 429:
                raise LighterRateLimitError("Rate limit exceeded") from e
            logger.error("get_assets_failed", status=e.status)
            raise LighterConnectionError(f"Failed to get assets: {e}") from e
        except aiohttp.ClientError as e:
            logger.error("get_assets_request_error", error=str(e))
            raise LighterConnectionError(f"Request failed: {e}") from e

    def _parse_market_to_asset(self, market: dict | Any) -> dict | None:
        """Parse Lighter market data to standardized asset dict.

        Args:
            market: Raw market data from API

        Returns:
            Standardized asset dict or None if invalid
        """
        try:
            # Handle both dict and object access
            if isinstance(market, dict):
                symbol = market.get("symbol") or market.get("name") or market.get("order_book", "")
                base_asset = market.get("base_asset") or market.get("base", "")
                quote_asset = market.get("quote_asset") or market.get("quote", "USD")
                min_size = market.get("min_size") or market.get("min_order_size", "0.001")
                tick_size = market.get("tick_size") or market.get("price_tick", "0.01")
            else:
                symbol = getattr(market, "symbol", "") or getattr(market, "name", "")
                base_asset = getattr(market, "base_asset", "") or getattr(market, "base", "")
                quote_asset = getattr(market, "quote_asset", "USD")
                min_size = getattr(market, "min_size", "0.001")
                tick_size = getattr(market, "tick_size", "0.01")

            if not symbol:
                return None

            # Determine category from symbol
            symbol_upper = symbol.upper()
            if "PERP" in symbol_upper or "-P" in symbol_upper:
                category = "perpetual"
            elif "SPOT" in symbol_upper:
                category = "spot"
            else:
                # Default: assume perpetual for DeFi perp DEX
                category = "perpetual"

            # Extract base from symbol if not provided
            if not base_asset:
                # Handle formats like "BTC-PERP", "BTCUSD", "BTC/USD"
                base_asset = (
                    symbol.split("-")[0].split("/")[0].replace("USD", "").replace("USDT", "")
                )

            return {
                "symbol": symbol,
                "base": base_asset,
                "quote": quote_asset if quote_asset else "USD",
                "category": category,
                "min_size": Decimal(str(min_size)),
                "tick_size": Decimal(str(tick_size)),
            }

        except (ValueError, TypeError) as e:
            logger.warning("market_parse_failed", market=str(market)[:100], error=str(e))
            return None

    async def get_assets_by_category(self, category: str) -> list[dict]:
        """Filter trading pairs by category.

        Args:
            category: "perpetual" or "spot"

        Returns:
            Filtered list of assets
        """
        all_assets = await self.get_available_assets()
        category_lower = category.lower()

        filtered = [a for a in all_assets if a["category"].lower() == category_lower]

        logger.debug(
            "assets_filtered_by_category",
            category=category,
            count=len(filtered),
            total=len(all_assets),
        )

        return filtered

    def filter_assets_by_pattern(
        self,
        assets: list[dict],
        pattern: str,
        field: str = "symbol",
    ) -> list[dict]:
        """Filter assets by pattern matching.

        Supports:
        - Exact match: "BTC-PERP"
        - Wildcard: "BTC*" or "*PERP"
        - Regex: "BTC.*PERP"

        Args:
            assets: List of asset dicts to filter
            pattern: Pattern to match (string or regex)
            field: Field to match against (default: "symbol")

        Returns:
            List of matching assets
        """
        if not pattern:
            return assets

        # Convert wildcard to regex
        if "*" in pattern and not any(c in pattern for c in [".", "^", "$", "+"]):
            # Simple wildcard pattern
            regex_pattern = pattern.replace("*", ".*")
        else:
            regex_pattern = pattern

        try:
            compiled = re.compile(regex_pattern, re.IGNORECASE)
        except re.error:
            # Invalid regex, use literal match
            compiled = re.compile(re.escape(pattern), re.IGNORECASE)

        filtered = [a for a in assets if compiled.search(str(a.get(field, "")))]

        logger.debug(
            "assets_filtered_by_pattern",
            pattern=pattern,
            field=field,
            count=len(filtered),
            total=len(assets),
        )

        return filtered

    # =========================================================================
    # OHLCV Data Fetching (Story 10.5.2)
    # =========================================================================

    async def fetch(
        self,
        symbols: list[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        resolution: str,
    ) -> pl.DataFrame:
        """Fetch OHLCV data from Lighter.xyz.

        Args:
            symbols: List of symbols to fetch (e.g., ["BTC-PERP"])
            start_date: Start of date range
            end_date: End of date range
            resolution: Timeframe ("1m", "5m", "15m", "1h", "4h", "1d")

        Returns:
            Polars DataFrame with OHLCV data

        Raises:
            ValueError: If resolution is unsupported
            LighterConnectionError: If API request fails
        """
        # Validate resolution
        lighter_resolution = self._map_resolution(resolution)

        all_data: list[pl.DataFrame] = []

        for symbol in symbols:
            symbol_data = await self._fetch_symbol(symbol, start_date, end_date, lighter_resolution)
            if not symbol_data.is_empty():
                all_data.append(symbol_data)

        if not all_data:
            return self._empty_dataframe()

        # Concatenate all symbol data
        result = pl.concat(all_data)

        # Log success
        self._log_fetch_success(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            resolution=resolution,
            row_count=len(result),
        )

        return result

    def _map_resolution(self, resolution: str) -> str:
        """Map rustybt timeframe to Lighter.xyz format.

        Args:
            resolution: rustybt timeframe (e.g., "1h")

        Returns:
            Lighter.xyz resolution string (minutes)

        Raises:
            ValueError: If resolution is unsupported
        """
        mapped = TIMEFRAME_MAP.get(resolution.lower())
        if not mapped:
            supported = ", ".join(TIMEFRAME_MAP.keys())
            raise ValueError(f"Unsupported timeframe: {resolution}. Supported: {supported}")
        return mapped

    async def _fetch_symbol(
        self,
        symbol: str,
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        resolution: str,
    ) -> pl.DataFrame:
        """Fetch data for a single symbol with pagination.

        Args:
            symbol: Trading symbol
            start_date: Start timestamp
            end_date: End timestamp
            resolution: Lighter.xyz resolution (minutes as string)

        Returns:
            Polars DataFrame with OHLCV data for this symbol
        """
        all_candles: list[dict] = []
        current_start = start_date

        session = await self._get_session()

        while current_start < end_date:
            # Acquire rate limit token
            await self.rate_limiter.acquire()

            params = {
                "symbol": symbol,
                "resolution": resolution,
                "from": int(current_start.timestamp()),
                "to": int(end_date.timestamp()),
                "limit": self.MAX_CANDLES_PER_REQUEST,
            }

            try:
                async with session.get("/api/v1/candlesticks", params=params) as response:
                    if response.status == 429:
                        # Rate limited - wait and retry
                        await asyncio.sleep(1.0)
                        continue
                    response.raise_for_status()
                    data = await response.json()

                candles = data.get("candles", data.get("data", []))
                if not candles:
                    break

                all_candles.extend(candles)

                # Find last timestamp and move to next page
                last_candle = candles[-1]
                last_timestamp = (
                    last_candle.get("timestamp") or last_candle.get("time") or last_candle.get("t")
                )

                if last_timestamp is None:
                    break

                # Convert to timestamp if needed
                if isinstance(last_timestamp, str):
                    last_ts = pd.Timestamp(last_timestamp)
                elif isinstance(last_timestamp, (int, float)):
                    # Assume seconds or milliseconds
                    if last_timestamp > 1e12:
                        last_ts = pd.Timestamp(last_timestamp, unit="ms")
                    else:
                        last_ts = pd.Timestamp(last_timestamp, unit="s")
                else:
                    last_ts = pd.Timestamp(last_timestamp)

                # Move start to after last candle
                current_start = last_ts + pd.Timedelta(seconds=1)

                # Safety: break if we didn't advance
                if len(candles) < self.MAX_CANDLES_PER_REQUEST:
                    break

                logger.debug(
                    "fetch_page_complete",
                    symbol=symbol,
                    candles_in_page=len(candles),
                    total_candles=len(all_candles),
                    next_start=str(current_start),
                )

            except aiohttp.ClientResponseError as e:
                if e.status == 429:
                    # Rate limited - wait and retry
                    await asyncio.sleep(1.0)
                    continue
                logger.error(
                    "fetch_symbol_failed",
                    symbol=symbol,
                    status=e.status,
                )
                raise LighterConnectionError(f"Fetch failed: {e}") from e
            except aiohttp.ClientError as e:
                logger.error("fetch_symbol_request_error", symbol=symbol, error=str(e))
                raise LighterConnectionError(f"Request failed: {e}") from e

        return self._parse_candles(all_candles, symbol)

    def _parse_candles(self, candles: list[dict], symbol: str) -> pl.DataFrame:
        """Parse raw candle data to Polars DataFrame.

        Args:
            candles: List of candle dicts from API
            symbol: Trading symbol

        Returns:
            Polars DataFrame with standardized OHLCV schema
        """
        if not candles:
            return self._empty_dataframe()

        rows = []
        for candle in candles:
            try:
                # Extract timestamp (handle various formats)
                ts = candle.get("timestamp") or candle.get("time") or candle.get("t")
                if isinstance(ts, str):
                    timestamp = pd.Timestamp(ts)
                elif isinstance(ts, (int, float)):
                    if ts > 1e12:
                        timestamp = pd.Timestamp(ts, unit="ms")
                    else:
                        timestamp = pd.Timestamp(ts, unit="s")
                else:
                    timestamp = pd.Timestamp(ts)

                # Extract OHLCV values (handle various field names)
                open_price = candle.get("open") or candle.get("o")
                high_price = candle.get("high") or candle.get("h")
                low_price = candle.get("low") or candle.get("l")
                close_price = candle.get("close") or candle.get("c")
                volume = candle.get("volume") or candle.get("v") or 0

                rows.append(
                    {
                        "timestamp": timestamp,
                        "symbol": symbol,
                        "open": Decimal(str(open_price)),
                        "high": Decimal(str(high_price)),
                        "low": Decimal(str(low_price)),
                        "close": Decimal(str(close_price)),
                        "volume": Decimal(str(volume)),
                    }
                )

            except (ValueError, TypeError, KeyError) as e:
                logger.warning(
                    "candle_parse_failed",
                    candle=str(candle)[:100],
                    error=str(e),
                )
                continue

        if not rows:
            return self._empty_dataframe()

        # Create DataFrame
        df = pl.DataFrame(rows)

        # Sort by timestamp
        df = df.sort("timestamp")

        return df

    def _empty_dataframe(self) -> pl.DataFrame:
        """Create empty DataFrame with standard schema.

        Returns:
            Empty Polars DataFrame with OHLCV columns
        """
        return pl.DataFrame(
            schema={
                "timestamp": pl.Datetime("us"),
                "symbol": pl.Utf8,
                "open": pl.Decimal(precision=18, scale=8),
                "high": pl.Decimal(precision=18, scale=8),
                "low": pl.Decimal(precision=18, scale=8),
                "close": pl.Decimal(precision=18, scale=8),
                "volume": pl.Decimal(precision=18, scale=8),
            }
        )

    # =========================================================================
    # Data Standardization & Validation (Story 10.5.3)
    # =========================================================================

    def standardize(self, df: pl.DataFrame) -> pl.DataFrame:
        """Convert Lighter.xyz data to rustybt standard schema.

        Args:
            df: Raw data from Lighter.xyz

        Returns:
            Standardized DataFrame with rustybt schema
        """
        # Column mapping for various API response formats
        column_map = {
            "time": "timestamp",
            "t": "timestamp",
            "o": "open",
            "h": "high",
            "l": "low",
            "c": "close",
            "v": "volume",
        }

        # Rename columns that exist
        for old_name, new_name in column_map.items():
            if old_name in df.columns and new_name not in df.columns:
                df = df.rename({old_name: new_name})

        # Ensure timestamp is datetime with UTC timezone
        if "timestamp" in df.columns:
            # Handle various timestamp formats
            ts_col = df["timestamp"]
            if ts_col.dtype == pl.Int64 or ts_col.dtype == pl.Float64:
                # Numeric timestamp - determine if seconds or milliseconds
                first_val = ts_col[0] if len(ts_col) > 0 else 0
                if first_val and first_val > 1e12:
                    df = df.with_columns(
                        [(pl.col("timestamp") * 1000).cast(pl.Datetime("us")).alias("timestamp")]
                    )
                else:
                    df = df.with_columns(
                        [
                            (pl.col("timestamp") * 1_000_000)
                            .cast(pl.Datetime("us"))
                            .alias("timestamp")
                        ]
                    )

        # Convert price columns to Decimal
        decimal_cols = ["open", "high", "low", "close", "volume"]
        for col in decimal_cols:
            if col in df.columns:
                df = df.with_columns([pl.col(col).cast(pl.Decimal(precision=18, scale=8))])

        # Select only schema columns in correct order
        schema_cols = list(LIGHTER_OHLCV_SCHEMA.keys())
        available_cols = [c for c in schema_cols if c in df.columns]

        return df.select(available_cols)

    def validate(self, df: pl.DataFrame) -> bool:
        """Validate OHLCV data relationships and schema.

        Args:
            df: DataFrame to validate

        Returns:
            True if valid

        Raises:
            ValidationError: If validation fails
        """
        # Check required columns
        required = {"timestamp", "symbol", "open", "high", "low", "close", "volume"}
        missing = required - set(df.columns)
        if missing:
            raise ValidationError(f"Missing columns: {missing}")

        # Check OHLCV relationships: low <= open, close <= high
        invalid = df.filter(
            (pl.col("low") > pl.col("open"))
            | (pl.col("low") > pl.col("close"))
            | (pl.col("high") < pl.col("open"))
            | (pl.col("high") < pl.col("close"))
        )

        if len(invalid) > 0:
            raise ValidationError(f"OHLCV relationship violated in {len(invalid)} rows")

        # Check for nulls in required fields
        for col in required:
            null_count = df[col].null_count()
            if null_count > 0:
                raise ValidationError(f"Null values found in column '{col}': {null_count}")

        return True

    # =========================================================================
    # Funding Rates (Story 10.5.3)
    # =========================================================================

    async def get_funding_rates(
        self,
        symbol: str,
        start_date: pd.Timestamp | None = None,
        end_date: pd.Timestamp | None = None,
    ) -> pl.DataFrame:
        """Fetch funding rate history from Lighter.xyz.

        Args:
            symbol: Trading pair symbol
            start_date: Start of date range (optional)
            end_date: End of date range (optional)

        Returns:
            DataFrame with columns: timestamp, symbol, funding_rate

        Raises:
            LighterConnectionError: If API request fails
        """
        await self.rate_limiter.acquire()

        session = await self._get_session()

        params: dict[str, Any] = {"symbol": symbol}
        if start_date:
            params["from"] = int(start_date.timestamp())
        if end_date:
            params["to"] = int(end_date.timestamp())

        try:
            async with session.get("/api/v1/funding-rates", params=params) as response:
                if response.status == 429:
                    raise LighterRateLimitError("Rate limit exceeded")
                response.raise_for_status()
                data = await response.json()

            rates = data.get("rates", data.get("data", []))

            rows = []
            for rate in rates:
                try:
                    ts = rate.get("timestamp") or rate.get("time")
                    if isinstance(ts, (int, float)):
                        if ts > 1e12:
                            timestamp = pd.Timestamp(ts, unit="ms")
                        else:
                            timestamp = pd.Timestamp(ts, unit="s")
                    else:
                        timestamp = pd.Timestamp(ts)

                    funding_rate = rate.get("rate") or rate.get("funding_rate")

                    rows.append(
                        {
                            "timestamp": timestamp,
                            "symbol": symbol,
                            "funding_rate": Decimal(str(funding_rate)),
                        }
                    )
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning("funding_rate_parse_failed", error=str(e))
                    continue

            df = (
                pl.DataFrame(rows)
                if rows
                else pl.DataFrame(
                    schema={
                        "timestamp": pl.Datetime("us"),
                        "symbol": pl.Utf8,
                        "funding_rate": pl.Decimal(precision=18, scale=8),
                    }
                )
            )

            logger.info(
                "funding_rates_fetched",
                symbol=symbol,
                count=len(rows),
            )

            return df

        except aiohttp.ClientResponseError as e:
            logger.error("get_funding_rates_failed", symbol=symbol, status=e.status)
            raise LighterConnectionError(f"Failed to get funding rates: {e}") from e
        except aiohttp.ClientError as e:
            logger.error("get_funding_rates_request_error", symbol=symbol, error=str(e))
            raise LighterConnectionError(f"Request failed: {e}") from e

    # =========================================================================
    # Context Manager Support
    # =========================================================================

    async def __aenter__(self) -> "LighterDataAdapter":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - close session."""
        await self.close()
