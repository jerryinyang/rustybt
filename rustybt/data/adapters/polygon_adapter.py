"""Polygon.io data adapter for stocks, options, forex, and crypto.

Polygon.io API documentation: https://polygon.io/docs
"""

import asyncio
from decimal import Decimal
from pathlib import Path

import pandas as pd
import polars as pl
import structlog

from rustybt.data.adapters.api_provider_base import (
    BaseAPIProviderAdapter,
    DataParsingError,
    SymbolNotFoundError,
)
from rustybt.data.adapters.base import validate_ohlcv_relationships
from rustybt.data.adapters.utils import (
    build_symbol_sid_map,
    normalize_symbols,
    prepare_ohlcv_frame,
)
from rustybt.data.polars.parquet_writer import ParquetWriter
from rustybt.data.sources.base import DataSource, DataSourceMetadata
from rustybt.utils.paths import data_path, ensure_directory

logger = structlog.get_logger()


class PolygonAdapter(BaseAPIProviderAdapter, DataSource):
    """Polygon.io data adapter.

    Supports:
    - Stocks: US and global equities
    - Options: US options chains
    - Forex: Currency pairs (prefix: C:EURUSD)
    - Crypto: Cryptocurrencies (prefix: X:BTCUSD)

    Rate limits (configurable by tier):
    - Free: 5 requests/minute
    - Starter: 10 requests/minute
    - Developer: 100 requests/minute

    Implements both BaseAPIProviderAdapter and DataSource interfaces for backwards
    compatibility and unified data source access.

    Attributes:
        tier: Subscription tier ('free', 'starter', 'developer')
        asset_type: Asset type ('stocks', 'options', 'forex', 'crypto')
    """

    # Tier-specific rate limits
    TIER_LIMITS = {
        "free": {"requests_per_minute": 5},
        "starter": {"requests_per_minute": 10},
        "developer": {"requests_per_minute": 100},
    }

    # Timeframe mapping (RustyBT -> Polygon API)
    TIMEFRAME_MAP = {
        "1m": ("1", "minute"),
        "5m": ("5", "minute"),
        "15m": ("15", "minute"),
        "30m": ("30", "minute"),
        "1h": ("1", "hour"),
        "4h": ("4", "hour"),
        "1d": ("1", "day"),
        "1w": ("1", "week"),
        "1M": ("1", "month"),
    }

    def __init__(
        self,
        tier: str = "free",
        asset_type: str = "stocks",
    ) -> None:
        """Initialize Polygon adapter.

        Args:
            tier: Subscription tier ('free', 'starter', 'developer')
            asset_type: Asset type ('stocks', 'options', 'forex', 'crypto')

        Raises:
            ValueError: If tier or asset_type is invalid
            AuthenticationError: If POLYGON_API_KEY not found
        """
        if tier not in self.TIER_LIMITS:
            raise ValueError(
                f"Invalid tier '{tier}'. Must be one of: {list(self.TIER_LIMITS.keys())}"
            )

        if asset_type not in ("stocks", "options", "forex", "crypto"):
            raise ValueError(
                f"Invalid asset_type '{asset_type}'. Must be one of: stocks, options, forex, crypto"
            )

        self.tier = tier
        self.asset_type = asset_type

        # Initialize base adapter with tier-specific limits
        limits = self.TIER_LIMITS[tier]
        super().__init__(
            name=f"polygon_{asset_type}_{tier}",
            api_key_env_var="POLYGON_API_KEY",
            requests_per_minute=limits["requests_per_minute"],
            base_url="https://api.polygon.io",
        )

    def _get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers.

        Polygon supports both query param and Authorization header.
        Using header for better security.

        Returns:
            Authorization header with Bearer token
        """
        return {"Authorization": f"Bearer {self.api_key}"}

    def _get_auth_params(self) -> dict[str, str]:
        """Get authentication query parameters.

        Returns:
            Empty dict (using header auth instead)
        """
        return {}

    def _build_ticker_symbol(self, symbol: str) -> str:
        """Build Polygon ticker format based on asset type.

        Args:
            symbol: Raw symbol (e.g., "AAPL", "EURUSD", "BTCUSD")

        Returns:
            Polygon-formatted ticker (e.g., "AAPL", "C:EURUSD", "X:BTCUSD")
        """
        if self.asset_type == "stocks":
            return symbol.upper()
        elif self.asset_type == "forex":
            return f"C:{symbol.upper()}"
        elif self.asset_type == "crypto":
            return f"X:{symbol.upper()}"
        else:  # options
            return symbol.upper()

    async def fetch_ohlcv(
        self,
        symbol: str,
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        timeframe: str,
    ) -> pl.DataFrame:
        """Fetch OHLCV data from Polygon API.

        Args:
            symbol: Symbol to fetch
            start_date: Start date
            end_date: End date
            timeframe: Timeframe (e.g., "1d", "1h", "1m")

        Returns:
            Polars DataFrame with OHLCV data

        Raises:
            ValueError: If timeframe is invalid
            SymbolNotFoundError: If symbol not found
            DataParsingError: If response parsing fails
        """
        # Map timeframe to Polygon format
        if timeframe not in self.TIMEFRAME_MAP:
            raise ValueError(
                f"Invalid timeframe '{timeframe}'. "
                f"Must be one of: {list(self.TIMEFRAME_MAP.keys())}"
            )

        multiplier, timespan = self.TIMEFRAME_MAP[timeframe]

        # Build ticker and endpoint
        ticker = self._build_ticker_symbol(symbol)

        if self.asset_type == "options":
            # Options use snapshot endpoint
            url = f"/v3/snapshot/options/{ticker}"
            data = await self._make_request("GET", url)
            return self._parse_options_response(data, symbol, start_date, end_date)
        else:
            # Aggregates endpoint for stocks, forex, crypto
            from_date = start_date.strftime("%Y-%m-%d")
            to_date = end_date.strftime("%Y-%m-%d")

            url = f"/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from_date}/{to_date}"
            params = {
                "adjusted": "true",
                "sort": "asc",
                "limit": "50000",  # Max results per request
            }

            data = await self._make_request("GET", url, params=params)

            # Check for errors in response
            if data.get("status") == "ERROR":
                error_msg = data.get("error", "Unknown error")
                if "NOT_FOUND" in error_msg or "not found" in error_msg.lower():
                    raise SymbolNotFoundError(
                        f"Symbol '{symbol}' not found in Polygon {self.asset_type}"
                    )
                raise DataParsingError(f"Polygon API error: {error_msg}")

            # Parse aggregates response
            return self._parse_aggregates_response(data, symbol)

    def _parse_aggregates_response(self, data: dict, symbol: str) -> pl.DataFrame:
        """Parse Polygon aggregates API response.

        Args:
            data: JSON response from Polygon API
            symbol: Original symbol (for adding to DataFrame)

        Returns:
            Polars DataFrame with standardized schema

        Raises:
            DataParsingError: If response format is invalid
        """
        if "results" not in data or not data["results"]:
            raise DataParsingError(f"No results found in Polygon response for {symbol}")

        results = data["results"]

        # Convert to DataFrame
        # Polygon response format:
        # {
        #   "v": volume,
        #   "vw": volume weighted average price,
        #   "o": open,
        #   "c": close,
        #   "h": high,
        #   "l": low,
        #   "t": timestamp (milliseconds),
        #   "n": number of transactions
        # }
        df = pl.DataFrame(
            {
                "timestamp": [pd.Timestamp(r["t"], unit="ms", tz="UTC") for r in results],
                "symbol": [symbol] * len(results),
                "open": [Decimal(str(r["o"])) for r in results],
                "high": [Decimal(str(r["h"])) for r in results],
                "low": [Decimal(str(r["l"])) for r in results],
                "close": [Decimal(str(r["c"])) for r in results],
                "volume": [Decimal(str(r["v"])) for r in results],
            }
        )

        return self.standardize(df)

    def _parse_options_response(
        self,
        data: dict,
        symbol: str,
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
    ) -> pl.DataFrame:
        """Parse Polygon options snapshot response.

        Note: Options endpoint returns snapshot data, not historical bars.
        For historical options data, would need different endpoint.

        Args:
            data: JSON response from Polygon API
            symbol: Original symbol
            start_date: Requested start date
            end_date: Requested end date

        Returns:
            Polars DataFrame with current options data

        Raises:
            DataParsingError: If response format is invalid
        """
        if "results" not in data or not data["results"]:
            raise DataParsingError(f"No results found in Polygon options snapshot for {symbol}")

        results = data["results"]

        # Parse options chain data
        rows = []
        for option in results:
            details = option.get("details", {})
            last_quote = option.get("last_quote", {})

            # Create row with available data
            row = {
                "timestamp": pd.Timestamp.now(tz="UTC"),
                "symbol": details.get("ticker", symbol),
                "open": Decimal(str(last_quote.get("bid", 0))),
                "high": Decimal(str(last_quote.get("ask", 0))),
                "low": Decimal(str(last_quote.get("bid", 0))),
                "close": Decimal(str(last_quote.get("midpoint", 0))),
                "volume": Decimal(str(option.get("volume", 0))),
            }
            rows.append(row)

        if not rows:
            raise DataParsingError(f"Failed to parse options data for {symbol}")

        df = pl.DataFrame(rows)
        return self.standardize(df)

    def validate(self, df: pl.DataFrame) -> bool:
        """Validate OHLCV data quality.

        Args:
            df: DataFrame to validate

        Returns:
            True if validation passes

        Raises:
            ValidationError: If validation fails
        """
        return validate_ohlcv_relationships(df)

    def standardize(self, df: pl.DataFrame) -> pl.DataFrame:
        """Standardize Polygon data to RustyBT schema.

        Args:
            df: DataFrame in Polygon format

        Returns:
            DataFrame with standardized schema and Decimal columns
        """
        # Ensure timestamp is datetime
        if df["timestamp"].dtype != pl.Datetime("us"):
            # Handle string timestamps
            if df["timestamp"].dtype == pl.Utf8:
                df = df.with_columns(pl.col("timestamp").str.to_datetime("%Y-%m-%d"))
            # Then cast to microsecond precision
            df = df.with_columns(pl.col("timestamp").cast(pl.Datetime("us")))

        # Ensure Decimal types for price/volume columns
        decimal_cols = ["open", "high", "low", "close", "volume"]
        for col in decimal_cols:
            if not str(df[col].dtype).startswith("decimal"):
                # Convert to string first, then to Decimal to preserve precision
                df = df.with_columns(
                    pl.col(col).cast(pl.Utf8).cast(pl.Decimal(precision=18, scale=8))
                )

        # Sort by timestamp
        df = df.sort("timestamp")

        return df.select(list(self.STANDARD_SCHEMA.keys()))

    # ========================================================================
    # DataSource Interface Implementation
    # ========================================================================

    def ingest_to_bundle(
        self,
        bundle_name: str,
        symbols: list[str],
        start: pd.Timestamp,
        end: pd.Timestamp,
        frequency: str,
        **kwargs,
    ) -> None:
        """Ingest Polygon data into bundle (Parquet + metadata).

        Args:
            bundle_name: Name of bundle to create/update
            symbols: List of symbols to ingest
            start: Start timestamp for data range
            end: End timestamp for data range
            frequency: Time resolution (e.g., "1d", "1h", "1m")
            **kwargs: Additional parameters (ignored for Polygon)

        Raises:
            NetworkError: If data fetch fails
            ValidationError: If data validation fails
            IOError: If bundle write fails
        """
        logger.info(
            "polygon_ingest_start",
            bundle=bundle_name,
            symbols=symbols[:5] if len(symbols) > 5 else symbols,
            symbol_count=len(symbols),
            start=start,
            end=end,
            frequency=frequency,
            tier=self.tier,
            asset_type=self.asset_type,
        )

        normalized_symbols = normalize_symbols(symbols)

        all_data = []
        for symbol in normalized_symbols:
            df_symbol = asyncio.run(self.fetch_ohlcv(symbol, start, end, frequency))
            if not df_symbol.is_empty():
                all_data.append(df_symbol)

        if not all_data:
            logger.warning(
                "polygon_no_data",
                bundle=bundle_name,
                symbols=normalized_symbols,
                frequency=frequency,
            )
            return

        combined_df = pl.concat(all_data)

        symbol_map = build_symbol_sid_map(normalized_symbols)
        df_prepared, frame_type = prepare_ohlcv_frame(combined_df, symbol_map, frequency)

        bundle_dir = Path(data_path(["bundles", bundle_name]))
        ensure_directory(str(bundle_dir))

        writer = ParquetWriter(str(bundle_dir))

        metadata = self.get_metadata()
        source_metadata = {
            "source_type": metadata.source_type,
            "source_url": metadata.source_url,
            "api_version": metadata.api_version,
            "symbols": list(symbol_map.keys()),
            "timezone": kwargs.get("timezone", "UTC"),
        }

        if frame_type == "daily":
            writer.write_daily_bars(
                df_prepared,
                bundle_name=bundle_name,
                source_metadata=source_metadata,
            )
        else:
            writer.write_minute_bars(df_prepared)

        logger.info(
            "polygon_ingest_complete",
            bundle=bundle_name,
            rows=len(df_prepared),
            frame_type=frame_type,
            bundle_path=str(bundle_dir),
        )

    def get_metadata(self) -> DataSourceMetadata:
        """Get Polygon source metadata.

        Returns:
            DataSourceMetadata with Polygon API information
        """
        return DataSourceMetadata(
            source_type="polygon",
            source_url="https://api.polygon.io",
            api_version="v2",
            supports_live=True,
            rate_limit=self.TIER_LIMITS[self.tier]["requests_per_minute"],
            auth_required=True,
            data_delay=0,  # Real-time data
            supported_frequencies=list(self.TIMEFRAME_MAP.keys()),
            additional_info={
                "tier": self.tier,
                "asset_type": self.asset_type,
                "websocket_available": True,
            },
        )

    def supports_live(self) -> bool:
        """Polygon supports live streaming via WebSocket.

        Returns:
            True (real-time WebSocket streaming available)
        """
        return True

    # Backwards compatibility alias
    async def fetch(
        self,
        symbols: list[str],
        start: pd.Timestamp,
        end: pd.Timestamp,
        frequency: str,
    ) -> pl.DataFrame:
        """Legacy method name for backwards compatibility.

        Delegates to fetch_ohlcv() for each symbol and combines results.

        Args:
            symbols: List of symbols to fetch
            start: Start timestamp
            end: End timestamp
            frequency: Time resolution

        Returns:
            Polars DataFrame with OHLCV data
        """
        all_data = []
        for symbol in symbols:
            df = await self.fetch_ohlcv(symbol, start, end, frequency)
            all_data.append(df)

        return pl.concat(all_data) if all_data else pl.DataFrame()
