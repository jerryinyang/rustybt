"""Alpaca data adapter for US stocks.

Alpaca Market Data API v2 documentation: https://alpaca.markets/docs/api-references/market-data-api/
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


class AlpacaAdapter(BaseAPIProviderAdapter):
    """Alpaca Market Data API v2 adapter.

    Supports:
    - US stocks (real-time and historical)
    - Paper trading data feed (free)
    - Live trading data feed (requires subscription)

    Rate limits:
    - Data API: 200 requests/minute (both paper and live)

    Attributes:
        is_paper: Whether to use paper trading endpoint (default: True)
    """

    # Timeframe mapping (RustyBT -> Alpaca API)
    TIMEFRAME_MAP = {
        "1m": "1Min",
        "5m": "5Min",
        "15m": "15Min",
        "30m": "30Min",
        "1h": "1Hour",
        "1d": "1Day",
    }

    def __init__(self, is_paper: bool = True) -> None:
        """Initialize Alpaca adapter.

        Args:
            is_paper: Use paper trading endpoint (default: True)

        Raises:
            AuthenticationError: If ALPACA_API_KEY or ALPACA_API_SECRET not found
        """
        self.is_paper = is_paper

        # Initialize base adapter with Alpaca-specific auth
        super().__init__(
            name=f"alpaca_{'paper' if is_paper else 'live'}",
            api_key_env_var="ALPACA_API_KEY",
            api_secret_env_var="ALPACA_API_SECRET",
            requests_per_minute=200,  # 200 req/min for data API
            base_url="https://data.alpaca.markets",
        )

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get Alpaca authentication headers.

        Alpaca requires custom headers: APCA-API-KEY-ID and APCA-API-SECRET-KEY

        Returns:
            Dictionary with Alpaca auth headers
        """
        return {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.api_secret or "",
        }

    def _get_auth_params(self) -> Dict[str, str]:
        """Get authentication query parameters.

        Returns:
            Empty dict (Alpaca uses header auth)
        """
        return {}

    async def fetch_ohlcv(
        self,
        symbol: str,
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        timeframe: str,
    ) -> pl.DataFrame:
        """Fetch OHLCV data from Alpaca Market Data API.

        Args:
            symbol: Stock symbol (e.g., "AAPL")
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
        # Map timeframe to Alpaca format
        if timeframe not in self.TIMEFRAME_MAP:
            raise ValueError(
                f"Invalid timeframe '{timeframe}'. "
                f"Must be one of: {list(self.TIMEFRAME_MAP.keys())}"
            )

        alpaca_timeframe = self.TIMEFRAME_MAP[timeframe]

        # Build endpoint URL
        # Market Data API v2: /v2/stocks/{symbol}/bars
        url = f"/v2/stocks/{symbol.upper()}/bars"

        # Build query parameters
        params = {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "timeframe": alpaca_timeframe,
            "limit": "10000",  # Max bars per request
            "adjustment": "all",  # Include all corporate actions
            "feed": "iex" if self.is_paper else "sip",  # IEX for paper, SIP for live
        }

        # Make request
        data = await self._make_request("GET", url, params=params)

        # Check for errors
        if "bars" not in data:
            if "message" in data:
                error_msg = data["message"]
                if "not found" in error_msg.lower() or "invalid" in error_msg.lower():
                    raise SymbolNotFoundError(
                        f"Symbol '{symbol}' not found in Alpaca"
                    )
                raise DataParsingError(f"Alpaca API error: {error_msg}")
            raise DataParsingError(
                f"Unexpected response format from Alpaca for {symbol}"
            )

        # Parse bars
        return self._parse_bars_response(data, symbol)

    def _parse_bars_response(self, data: Dict, symbol: str) -> pl.DataFrame:
        """Parse Alpaca bars API response.

        Args:
            data: JSON response from Alpaca API
            symbol: Original symbol

        Returns:
            Polars DataFrame with standardized schema

        Raises:
            DataParsingError: If response format is invalid
        """
        bars = data.get("bars", [])

        if not bars:
            raise DataParsingError(
                f"No bars found in Alpaca response for {symbol}"
            )

        # Convert to DataFrame
        # Alpaca response format:
        # {
        #   "t": "2021-02-01T16:00:00Z",  # timestamp (RFC3339)
        #   "o": 133.75,                   # open
        #   "h": 133.82,                   # high
        #   "l": 133.51,                   # low
        #   "c": 133.52,                   # close
        #   "v": 9876543,                  # volume
        #   "n": 1234,                     # number of trades
        #   "vw": 133.6                    # volume weighted average price
        # }
        df = pl.DataFrame(
            {
                "timestamp": [
                    pd.Timestamp(bar["t"]).tz_convert("UTC") for bar in bars
                ],
                "symbol": [symbol] * len(bars),
                "open": [Decimal(str(bar["o"])) for bar in bars],
                "high": [Decimal(str(bar["h"])) for bar in bars],
                "low": [Decimal(str(bar["l"])) for bar in bars],
                "close": [Decimal(str(bar["c"])) for bar in bars],
                "volume": [Decimal(str(bar["v"])) for bar in bars],
            }
        )

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
        """Standardize Alpaca data to RustyBT schema.

        Args:
            df: DataFrame in Alpaca format

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
