"""Polygon.io data adapter for stocks, options, forex, and crypto.

Polygon.io API documentation: https://polygon.io/docs
"""

from decimal import Decimal
from typing import Dict

import pandas as pd
import polars as pl
import structlog

from rustybt.data.adapters.api_provider_base import (
    BaseAPIProviderAdapter,
    DataParsingError,
    SymbolNotFoundError,
)
from rustybt.data.adapters.base import validate_ohlcv_relationships

logger = structlog.get_logger()


class PolygonAdapter(BaseAPIProviderAdapter):
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
                f"Invalid asset_type '{asset_type}'. "
                "Must be one of: stocks, options, forex, crypto"
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

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers.

        Polygon supports both query param and Authorization header.
        Using header for better security.

        Returns:
            Authorization header with Bearer token
        """
        return {"Authorization": f"Bearer {self.api_key}"}

    def _get_auth_params(self) -> Dict[str, str]:
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

    def _parse_aggregates_response(
        self, data: Dict, symbol: str
    ) -> pl.DataFrame:
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
            raise DataParsingError(
                f"No results found in Polygon response for {symbol}"
            )

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
                "timestamp": [
                    pd.Timestamp(r["t"], unit="ms", tz="UTC") for r in results
                ],
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
        data: Dict,
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
            raise DataParsingError(
                f"No results found in Polygon options snapshot for {symbol}"
            )

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
            raise DataParsingError(
                f"Failed to parse options data for {symbol}"
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
                df = df.with_columns(
                    pl.col("timestamp").str.to_datetime("%Y-%m-%d")
                )
            # Then cast to microsecond precision
            df = df.with_columns(
                pl.col("timestamp").cast(pl.Datetime("us"))
            )

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
