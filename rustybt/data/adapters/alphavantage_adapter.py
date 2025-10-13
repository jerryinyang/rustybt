"""Alpha Vantage data adapter for stocks, forex, and crypto.

Alpha Vantage API documentation: https://www.alphavantage.co/documentation/
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
    QuotaExceededError,
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


class AlphaVantageAdapter(BaseAPIProviderAdapter, DataSource):
    """Alpha Vantage API adapter.

    Supports:
    - Stocks: Global equities
    - Forex: Currency pairs
    - Crypto: Digital currencies

    Rate limits (configurable by tier):
    - Free: 5 requests/minute, 500 requests/day
    - Premium: 75 requests/minute, 1200 requests/day

    Implements both BaseAPIProviderAdapter and DataSource interfaces for backwards
    compatibility and unified data source access.

    Attributes:
        tier: Subscription tier ('free' or 'premium')
        asset_type: Asset type ('stocks', 'forex', 'crypto')
    """

    # Tier-specific rate limits
    TIER_LIMITS = {
        "free": {"requests_per_minute": 5, "requests_per_day": 500},
        "premium": {"requests_per_minute": 75, "requests_per_day": 1200},
    }

    # Timeframe mapping (RustyBT -> Alpha Vantage API)
    INTRADAY_INTERVALS = {
        "1m": "1min",
        "5m": "5min",
        "15m": "15min",
        "30m": "30min",
        "1h": "60min",
    }

    def __init__(
        self,
        tier: str = "free",
        asset_type: str = "stocks",
    ) -> None:
        """Initialize Alpha Vantage adapter.

        Args:
            tier: Subscription tier ('free' or 'premium')
            asset_type: Asset type ('stocks', 'forex', 'crypto')

        Raises:
            ValueError: If tier or asset_type is invalid
            AuthenticationError: If ALPHAVANTAGE_API_KEY not found
        """
        if tier not in self.TIER_LIMITS:
            raise ValueError(
                f"Invalid tier '{tier}'. Must be one of: {list(self.TIER_LIMITS.keys())}"
            )

        if asset_type not in ("stocks", "forex", "crypto"):
            raise ValueError(
                f"Invalid asset_type '{asset_type}'. Must be one of: stocks, forex, crypto"
            )

        self.tier = tier
        self.asset_type = asset_type

        # Initialize base adapter with tier-specific limits
        limits = self.TIER_LIMITS[tier]
        super().__init__(
            name=f"alphavantage_{asset_type}_{tier}",
            api_key_env_var="ALPHAVANTAGE_API_KEY",
            requests_per_minute=limits["requests_per_minute"],
            requests_per_day=limits["requests_per_day"],
            base_url="https://www.alphavantage.co/query",
        )

    def _get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers.

        Returns:
            Empty dict (Alpha Vantage uses query param auth)
        """
        return {}

    def _get_auth_params(self) -> dict[str, str]:
        """Get authentication query parameters.

        Alpha Vantage uses apikey query parameter for authentication.

        Returns:
            Dictionary with apikey parameter
        """
        return {"apikey": self.api_key}

    def _get_function_name(self, timeframe: str) -> str:
        """Get Alpha Vantage function name based on asset type and timeframe.

        Args:
            timeframe: Timeframe (e.g., "1d", "1h", "1m")

        Returns:
            Alpha Vantage function name
        """
        is_intraday = timeframe in self.INTRADAY_INTERVALS

        if self.asset_type == "stocks":
            return "TIME_SERIES_INTRADAY" if is_intraday else "TIME_SERIES_DAILY"
        elif self.asset_type == "forex":
            return "FX_INTRADAY" if is_intraday else "FX_DAILY"
        elif self.asset_type == "crypto":
            return "CRYPTO_INTRADAY" if is_intraday else "DIGITAL_CURRENCY_DAILY"
        else:
            raise ValueError(f"Unknown asset type: {self.asset_type}")

    async def fetch_ohlcv(
        self,
        symbol: str,
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        timeframe: str,
    ) -> pl.DataFrame:
        """Fetch OHLCV data from Alpha Vantage API.

        Args:
            symbol: Symbol to fetch (e.g., "AAPL", "EUR/USD", "BTC")
            start_date: Start date
            end_date: End date
            timeframe: Timeframe (e.g., "1d", "1h", "1m")

        Returns:
            Polars DataFrame with OHLCV data

        Raises:
            ValueError: If timeframe is invalid
            SymbolNotFoundError: If symbol not found
            QuotaExceededError: If rate limit exceeded
            DataParsingError: If response parsing fails
        """
        # Get function name
        function = self._get_function_name(timeframe)

        # Build query parameters
        params = {"function": function}

        # Add symbol parameters based on asset type
        if self.asset_type == "stocks":
            params["symbol"] = symbol.upper()
        elif self.asset_type == "forex":
            # Split forex pair (e.g., "EUR/USD" -> from=EUR, to=USD)
            if "/" not in symbol:
                raise ValueError(f"Forex symbol must be in format 'XXX/YYY', got '{symbol}'")
            from_currency, to_currency = symbol.upper().split("/")
            params["from_symbol"] = from_currency
            params["to_symbol"] = to_currency
        elif self.asset_type == "crypto":
            # Crypto needs market (default: USD)
            params["symbol"] = symbol.upper()
            params["market"] = "USD"

        # Add interval for intraday data
        if timeframe in self.INTRADAY_INTERVALS:
            params["interval"] = self.INTRADAY_INTERVALS[timeframe]

        # Request full output (up to 20 years for daily, full day for intraday)
        params["outputsize"] = "full"

        # Make request
        data = await self._make_request("GET", "", params=params)

        # Check for API errors
        if "Error Message" in data:
            error_msg = data["Error Message"]
            if "Invalid API call" in error_msg or "not found" in error_msg.lower():
                raise SymbolNotFoundError(
                    f"Symbol '{symbol}' not found in Alpha Vantage {self.asset_type}"
                )
            raise DataParsingError(f"Alpha Vantage API error: {error_msg}")

        # Check for rate limit
        if "Note" in data:
            note = data["Note"]
            if "API call frequency" in note or "premium" in note.lower():
                raise QuotaExceededError(f"Alpha Vantage rate limit exceeded: {note}")

        # Parse time series data
        return self._parse_time_series_response(data, symbol, start_date, end_date, timeframe)

    def _parse_time_series_response(
        self,
        data: dict,
        symbol: str,
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        timeframe: str,
    ) -> pl.DataFrame:
        """Parse Alpha Vantage time series response.

        Args:
            data: JSON response from Alpha Vantage API
            symbol: Original symbol
            start_date: Filter start date
            end_date: Filter end date
            timeframe: Timeframe

        Returns:
            Polars DataFrame with standardized schema

        Raises:
            DataParsingError: If response format is invalid
        """
        # Find time series key in response
        time_series_key = None
        for key in data:
            if "Time Series" in key or "Digital Currency" in key or "FX" in key:
                time_series_key = key
                break

        if not time_series_key or not data[time_series_key]:
            raise DataParsingError(
                f"No time series data found in Alpha Vantage response for {symbol}"
            )

        time_series = data[time_series_key]

        # Parse time series data
        rows = []
        for timestamp_str, values in time_series.items():
            timestamp = pd.Timestamp(timestamp_str, tz="UTC")

            # Filter by date range
            if timestamp < start_date or timestamp > end_date:
                continue

            # Alpha Vantage uses different key formats
            # Stocks/Forex intraday: "1. open", "2. high", etc.
            # Stocks/Forex daily: "1. open", "2. high", etc.
            # Crypto: "1a. open (USD)", "2a. high (USD)", etc.

            # Try to detect key format
            if "1. open" in values:
                open_key, high_key, low_key, close_key, volume_key = (
                    "1. open",
                    "2. high",
                    "3. low",
                    "4. close",
                    "5. volume",
                )
            elif "1a. open (USD)" in values:
                open_key, high_key, low_key, close_key, volume_key = (
                    "1a. open (USD)",
                    "2a. high (USD)",
                    "3a. low (USD)",
                    "4a. close (USD)",
                    "5. volume",
                )
            elif "1b. open (USD)" in values:
                open_key, high_key, low_key, close_key, volume_key = (
                    "1b. open (USD)",
                    "2b. high (USD)",
                    "3b. low (USD)",
                    "4b. close (USD)",
                    "5. volume",
                )
            else:
                # Try to infer from available keys
                available_keys = list(values.keys())
                raise DataParsingError(
                    f"Unknown Alpha Vantage response format. Available keys: {available_keys}"
                )

            row = {
                "timestamp": timestamp,
                "symbol": symbol,
                "open": Decimal(str(values[open_key])),
                "high": Decimal(str(values[high_key])),
                "low": Decimal(str(values[low_key])),
                "close": Decimal(str(values[close_key])),
                "volume": Decimal(str(values.get(volume_key, 0))),
            }
            rows.append(row)

        if not rows:
            raise DataParsingError(
                f"No data found in date range {start_date} to {end_date} for {symbol}"
            )

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
        """Standardize Alpha Vantage data to RustyBT schema.

        Args:
            df: DataFrame in Alpha Vantage format

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
        """Ingest Alpha Vantage data into bundle (Parquet + metadata).

        Args:
            bundle_name: Name of bundle to create/update
            symbols: List of symbols to ingest
            start: Start timestamp for data range
            end: End timestamp for data range
            frequency: Time resolution (e.g., "1d", "1h", "1m")
            **kwargs: Additional parameters (ignored for Alpha Vantage)

        Raises:
            NetworkError: If data fetch fails
            ValidationError: If data validation fails
            IOError: If bundle write fails
        """
        logger.info(
            "alphavantage_ingest_start",
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
                "alphavantage_no_data",
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
            "alphavantage_ingest_complete",
            bundle=bundle_name,
            rows=len(df_prepared),
            frame_type=frame_type,
            bundle_path=str(bundle_dir),
        )

    def get_metadata(self) -> DataSourceMetadata:
        """Get Alpha Vantage source metadata.

        Returns:
            DataSourceMetadata with Alpha Vantage API information
        """
        return DataSourceMetadata(
            source_type="alphavantage",
            source_url="https://www.alphavantage.co/query",
            api_version="v1",
            supports_live=False,
            rate_limit=self.TIER_LIMITS[self.tier]["requests_per_minute"],
            auth_required=True,
            data_delay=0,  # Data is delayed but no specific delay documented
            supported_frequencies=list(self.INTRADAY_INTERVALS.keys()) + ["1d"],
            additional_info={
                "tier": self.tier,
                "asset_type": self.asset_type,
                "requests_per_day": self.TIER_LIMITS[self.tier]["requests_per_day"],
            },
        )

    def supports_live(self) -> bool:
        """Alpha Vantage does not support live streaming.

        Returns:
            False (delayed data, no WebSocket support)
        """
        return False

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
