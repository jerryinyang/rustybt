"""CCXT data adapter for fetching crypto OHLCV data from 100+ exchanges.

This module provides integration with the CCXT library to fetch historical
OHLCV data from cryptocurrency exchanges with standardized schema, rate
limiting, and error handling.
"""

import asyncio
from decimal import Decimal, getcontext
from pathlib import Path
from typing import ClassVar

import ccxt
import pandas as pd
import polars as pl
import structlog

from rustybt.data.adapters.base import (
    BaseDataAdapter,
    InvalidDataError,
    NetworkError,
    RateLimitError,
    validate_ohlcv_relationships,
)
from rustybt.data.adapters.utils import (
    build_symbol_sid_map,
    normalize_symbols,
    prepare_ohlcv_frame,
)
from rustybt.data.polars.parquet_writer import ParquetWriter
from rustybt.data.sources.base import DataSource, DataSourceMetadata
from rustybt.utils.paths import data_path, ensure_directory

# Set decimal precision for financial calculations
getcontext().prec = 28

logger = structlog.get_logger()


class CCXTAdapter(BaseDataAdapter, DataSource):
    """CCXT adapter for fetching crypto OHLCV data from 100+ exchanges.

    Provides unified interface to fetch historical cryptocurrency data from
    exchanges supported by CCXT library including Binance, Coinbase, Kraken,
    and 100+ others.

    Implements both BaseDataAdapter and DataSource interfaces for backwards
    compatibility and unified data source access.

    Attributes:
        exchange_id: Exchange identifier (e.g., 'binance', 'coinbase')
        exchange: CCXT exchange instance
        testnet: Whether using testnet/sandbox mode

    Example:
        >>> adapter = CCXTAdapter(exchange_id='binance')
        >>> df = await adapter.fetch(
        ...     symbols=['BTC/USDT'],
        ...     start_date=pd.Timestamp('2024-01-01'),
        ...     end_date=pd.Timestamp('2024-01-02'),
        ...     resolution='1h'
        ... )
        >>> print(df.head())
    """

    # Resolution mapping from RustyBT format to CCXT timeframe
    RESOLUTION_MAPPING: ClassVar[dict[str, str]] = {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "1h",
        "2h": "2h",
        "4h": "4h",
        "1d": "1d",
        "1w": "1w",
    }

    def __init__(
        self,
        exchange_id: str = "binance",
        testnet: bool = False,
        api_key: str | None = None,
        api_secret: str | None = None,
    ) -> None:
        """Initialize CCXT adapter.

        Args:
            exchange_id: Exchange identifier (e.g., 'binance', 'coinbase', 'kraken')
            testnet: Use testnet/sandbox mode if available
            api_key: API key (optional, only needed for private endpoints)
            api_secret: API secret (optional)

        Raises:
            AttributeError: If exchange_id not supported by CCXT
        """
        # Get exchange class from CCXT
        if not hasattr(ccxt, exchange_id):
            raise AttributeError(
                f"Exchange '{exchange_id}' not found in CCXT. "
                f"Available exchanges: {', '.join(ccxt.exchanges[:10])}..."
            )

        exchange_class = getattr(ccxt, exchange_id)

        # Initialize exchange with rate limiting enabled
        self.exchange = exchange_class(
            {
                "enableRateLimit": True,  # Enable built-in rate limiting
                "options": {"defaultType": "spot"},  # Use spot market by default
            }
        )

        # Set API credentials if provided
        if api_key and api_secret:
            self.exchange.apiKey = api_key
            self.exchange.secret = api_secret

        # Enable testnet/sandbox mode if available
        if testnet and hasattr(self.exchange, "has") and self.exchange.has.get("sandbox"):
            self.exchange.set_sandbox_mode(True)

        # Extract rate limit from exchange metadata
        rate_limit_ms = self.exchange.rateLimit  # Milliseconds between requests
        requests_per_second = 1000 / rate_limit_ms if rate_limit_ms > 0 else 10

        # Initialize base adapter with exchange-specific rate limit (80% of max for safety)
        super().__init__(
            name=f"CCXTAdapter({exchange_id})",
            rate_limit_per_second=int(requests_per_second * 0.8),
        )

        self.exchange_id = exchange_id
        self.testnet = testnet

        # Load markets to enable symbol validation
        try:
            self.exchange.load_markets()
            logger.info(
                "ccxt_adapter_initialized",
                exchange=exchange_id,
                markets_loaded=len(self.exchange.markets),
                testnet=testnet,
                rate_limit_per_second=int(requests_per_second * 0.8),
            )
        except (ccxt.NetworkError, ccxt.ExchangeError) as e:
            logger.warning(
                "ccxt_markets_load_failed",
                exchange=exchange_id,
                error=str(e),
                fallback="will attempt to load markets on first fetch",
            )

    async def fetch(
        self,
        symbols: list[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        resolution: str,
    ) -> pl.DataFrame:
        """Fetch OHLCV data from CCXT exchange.

        Args:
            symbols: List of trading pairs (e.g., ["BTC/USDT", "ETH/USDT"])
            start_date: Start date for data range
            end_date: End date for data range
            resolution: Time resolution (e.g., "1d", "1h", "1m")

        Returns:
            Polars DataFrame with standardized OHLCV schema

        Raises:
            NetworkError: If API request fails
            InvalidDataError: If symbol is invalid or delisted
            ValueError: If resolution is not supported
        """
        # Map resolution to CCXT timeframe
        if resolution not in self.RESOLUTION_MAPPING:
            raise ValueError(
                f"Unsupported resolution: {resolution}. "
                f"Supported: {list(self.RESOLUTION_MAPPING.keys())}"
            )

        ccxt_timeframe = self.RESOLUTION_MAPPING[resolution]

        # Convert timestamps to Unix milliseconds
        since = int(start_date.timestamp() * 1000)
        until = int(end_date.timestamp() * 1000)

        all_data = []

        for symbol in symbols:
            # Normalize symbol format
            normalized_symbol = self._normalize_symbol(symbol)

            # Validate symbol exists on exchange
            if not self.exchange.markets:
                try:
                    self.exchange.load_markets()
                except Exception as e:
                    raise NetworkError(
                        f"Failed to load markets from {self.exchange_id}: {e}"
                    ) from e

            if normalized_symbol not in self.exchange.markets:
                raise InvalidDataError(
                    f"Symbol {normalized_symbol} not found on {self.exchange_id}. "
                    f"Available markets: {len(self.exchange.markets)}"
                )

            # Fetch data with pagination
            symbol_data = await self._fetch_with_pagination(
                symbol=normalized_symbol,
                timeframe=ccxt_timeframe,
                since=since,
                until=until,
            )

            all_data.extend(symbol_data)

        # Convert to Polars DataFrame
        if not all_data:
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

        df = pl.DataFrame(
            {
                "timestamp": [pd.Timestamp(row[0], unit="ms") for row in all_data],
                "symbol": [row[6] for row in all_data],  # Symbol added in pagination
                "open": [Decimal(str(row[1])) for row in all_data],
                "high": [Decimal(str(row[2])) for row in all_data],
                "low": [Decimal(str(row[3])) for row in all_data],
                "close": [Decimal(str(row[4])) for row in all_data],
                "volume": [Decimal(str(row[5])) for row in all_data],
            }
        )

        # Standardize and validate
        df = self.standardize(df)
        self.validate(df)

        self._log_fetch_success(symbols, start_date, end_date, resolution, len(df))

        return df

    async def _fetch_with_pagination(
        self, symbol: str, timeframe: str, since: int, until: int
    ) -> list:
        """Fetch OHLCV data with pagination for large date ranges.

        CCXT exchanges typically limit responses to 500-1000 bars per request.
        This method handles pagination automatically.

        Args:
            symbol: Trading pair symbol (e.g., "BTC/USDT")
            timeframe: CCXT timeframe string (e.g., "1h")
            since: Start timestamp in Unix milliseconds
            until: End timestamp in Unix milliseconds

        Returns:
            List of OHLCV data with symbol appended: [[timestamp, o, h, l, c, v, symbol], ...]

        Raises:
            NetworkError: If API request fails
            InvalidDataError: If symbol is invalid
            RateLimitError: If rate limit exceeded
        """
        all_ohlcv = []
        current_since = since

        while current_since < until:
            # Apply rate limiting
            await self.rate_limiter.acquire()

            try:
                # Fetch batch (CCXT handles async internally for some exchanges)
                if asyncio.iscoroutinefunction(self.exchange.fetch_ohlcv):
                    ohlcv = await self.exchange.fetch_ohlcv(
                        symbol=symbol,
                        timeframe=timeframe,
                        since=current_since,
                        limit=1000,  # Max bars per request
                    )
                else:
                    # Some CCXT exchanges don't support async, run in executor
                    from functools import partial

                    loop = asyncio.get_event_loop()
                    ohlcv = await loop.run_in_executor(
                        None,
                        partial(
                            self.exchange.fetch_ohlcv,
                            symbol=symbol,
                            timeframe=timeframe,
                            since=current_since,
                            limit=1000,
                        ),
                    )

                if not ohlcv:
                    break

                # Filter out data beyond until timestamp
                ohlcv_filtered = [row for row in ohlcv if row[0] <= until]

                # Add symbol to each row
                ohlcv_with_symbol = [[*row, symbol] for row in ohlcv_filtered]
                all_ohlcv.extend(ohlcv_with_symbol)

                # Update since for next iteration
                if ohlcv[-1][0] >= until:
                    break

                current_since = ohlcv[-1][0] + 1  # Last timestamp + 1ms

            except ccxt.NetworkError as e:
                raise NetworkError(f"CCXT network error for {self.exchange_id}: {e}") from e
            except ccxt.ExchangeNotAvailable as e:
                raise NetworkError(f"Exchange {self.exchange_id} unavailable: {e}") from e
            except ccxt.BadSymbol as e:
                raise InvalidDataError(f"Invalid symbol {symbol}: {e}") from e
            except ccxt.RateLimitExceeded as e:
                raise RateLimitError(f"Rate limit exceeded on {self.exchange_id}: {e}") from e
            except Exception as e:
                # Catch-all for unexpected CCXT errors
                logger.error(
                    "ccxt_unexpected_error",
                    exchange=self.exchange_id,
                    symbol=symbol,
                    error_type=type(e).__name__,
                    error=str(e),
                )
                raise NetworkError(f"Unexpected CCXT error for {self.exchange_id}: {e}") from e

        logger.info(
            "ccxt_pagination_complete",
            exchange=self.exchange_id,
            symbol=symbol,
            timeframe=timeframe,
            bars_fetched=len(all_ohlcv),
        )

        return all_ohlcv

    def _normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol format to CCXT standard (e.g., BTC/USDT).

        Handles various input formats and converts to CCXT unified format.

        Args:
            symbol: Symbol in various formats (BTC/USDT, BTC-USDT, BTCUSDT)

        Returns:
            Normalized symbol in CCXT format (e.g., BTC/USDT)

        Example:
            >>> adapter._normalize_symbol("BTC-USDT")
            "BTC/USDT"
            >>> adapter._normalize_symbol("BTCUSDT")
            "BTC/USDT"
        """
        # Handle common formats
        symbol = symbol.upper().strip()

        # Already in correct format
        if "/" in symbol:
            return symbol

        # Handle dash format: BTC-USDT → BTC/USDT
        if "-" in symbol:
            return symbol.replace("-", "/")

        # Handle concatenated format: BTCUSDT → BTC/USDT (heuristic)
        # Try common quote currencies in order of specificity
        for quote in ["USDT", "USDC", "BUSD", "USD", "EUR", "BTC", "ETH", "BNB"]:
            if symbol.endswith(quote) and len(symbol) > len(quote):
                base = symbol[: -len(quote)]
                return f"{base}/{quote}"

        # If no pattern matched, return as-is and let validation catch it
        return symbol

    def validate(self, df: pl.DataFrame) -> bool:
        """Validate CCXT data quality and OHLCV relationships.

        Args:
            df: DataFrame to validate

        Returns:
            True if validation passes

        Raises:
            ValidationError: If data validation fails
        """
        return validate_ohlcv_relationships(df)

    def standardize(self, df: pl.DataFrame) -> pl.DataFrame:
        """Convert CCXT format to RustyBT standard schema.

        CCXT data is already standardized in fetch() method during conversion
        from list format to DataFrame, so this is a pass-through.

        Args:
            df: DataFrame in CCXT format (already converted to standard schema)

        Returns:
            DataFrame with standardized schema (unchanged)
        """
        # Data already standardized in fetch() method
        return df

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
        """Ingest CCXT data into bundle (Parquet + metadata).

        Args:
            bundle_name: Name of bundle to create/update
            symbols: List of symbols to ingest (e.g., ["BTC/USDT", "ETH/USDT"])
            start: Start timestamp for data range
            end: End timestamp for data range
            frequency: Time resolution (e.g., "1d", "1h", "1m")
            **kwargs: Additional parameters (ignored for CCXT)

        Raises:
            NetworkError: If data fetch fails
            ValidationError: If data validation fails
            IOError: If bundle write fails
        """
        logger.info(
            "ccxt_ingest_start",
            bundle=bundle_name,
            exchange=self.exchange_id,
            symbols=symbols[:5] if len(symbols) > 5 else symbols,
            symbol_count=len(symbols),
            start=start,
            end=end,
            frequency=frequency,
        )

        normalized_symbols = normalize_symbols(symbols)

        df = asyncio.run(self.fetch(normalized_symbols, start, end, frequency))
        if df.is_empty():
            logger.warning(
                "ccxt_no_data",
                bundle=bundle_name,
                exchange=self.exchange_id,
                symbols=normalized_symbols,
                frequency=frequency,
            )
            return

        symbol_map = build_symbol_sid_map(normalized_symbols)
        df_prepared, frame_type = prepare_ohlcv_frame(df, symbol_map, frequency)

        bundle_dir = Path(data_path(["bundles", bundle_name]))
        ensure_directory(str(bundle_dir))

        writer = ParquetWriter(str(bundle_dir))

        metadata = self.get_metadata()
        source_metadata = {
            "source_type": metadata.source_type,
            "source_url": metadata.source_url,
            "api_version": metadata.api_version,
            "symbols": list(symbol_map.keys()),
            "exchange": self.exchange_id,
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
            "ccxt_ingest_complete",
            bundle=bundle_name,
            exchange=self.exchange_id,
            rows=len(df_prepared),
            frame_type=frame_type,
            bundle_path=str(bundle_dir),
        )

    def get_metadata(self) -> DataSourceMetadata:
        """Get CCXT source metadata.

        Returns:
            DataSourceMetadata with CCXT API information
        """
        # Determine source URL from exchange
        if hasattr(self.exchange, "urls") and "www" in self.exchange.urls:
            source_url = self.exchange.urls["www"]
        else:
            source_url = f"https://{self.exchange_id}.com/api"

        # Get API version if available
        api_version = getattr(self.exchange, "version", "unknown")

        # Check if API credentials are configured
        auth_required = bool(self.exchange.apiKey and self.exchange.secret)

        return DataSourceMetadata(
            source_type="ccxt",
            source_url=source_url,
            api_version=api_version,
            supports_live=True,  # CCXT supports WebSocket streaming
            rate_limit=int(1000 / self.exchange.rateLimit) if self.exchange.rateLimit > 0 else 10,
            auth_required=auth_required,
            data_delay=0,  # Real-time data (no delay for crypto exchanges)
            supported_frequencies=list(self.RESOLUTION_MAPPING.keys()),
            additional_info={
                "exchange_id": self.exchange_id,
                "testnet": self.testnet,
                "markets_count": len(self.exchange.markets) if self.exchange.markets else 0,
                "has_websocket": (
                    self.exchange.has.get("ws", False) if hasattr(self.exchange, "has") else False
                ),
            },
        )

    def supports_live(self) -> bool:
        """CCXT supports live streaming via WebSocket.

        Returns:
            True (CCXT exchanges support WebSocket streaming)
        """
        return True

    # Backwards compatibility alias
    async def fetch_ohlcv(
        self,
        symbols: list[str],
        start: pd.Timestamp,
        end: pd.Timestamp,
        frequency: str,
    ) -> pl.DataFrame:
        """Legacy method name for backwards compatibility.

        Delegates to fetch() method.

        Args:
            symbols: List of symbols to fetch (e.g., ["BTC/USDT", "ETH/USDT"])
            start: Start timestamp
            end: End timestamp
            frequency: Time resolution

        Returns:
            Polars DataFrame with OHLCV data
        """
        return await self.fetch(symbols, start, end, frequency)
