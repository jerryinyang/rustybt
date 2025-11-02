"""CCXT data adapter for fetching crypto OHLCV data from 100+ exchanges.

This module provides integration with the CCXT library to fetch historical
OHLCV data from cryptocurrency exchanges with standardized schema, rate
limiting, error handling, and resumable ingestion with progress tracking.
"""

import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal, getcontext
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar

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
    with_retry,
)
from rustybt.data.adapters.utils import (
    build_symbol_sid_map,
    normalize_symbols,
    prepare_ohlcv_frame,
    run_async,
)
from rustybt.data.polars.parquet_writer import ParquetWriter
from rustybt.data.sources.base import DataSource, DataSourceMetadata
from rustybt.utils.paths import data_path, ensure_directory

# Set decimal precision for financial calculations
getcontext().prec = 28

logger = structlog.get_logger()


# ============================================================================
# Progress Tracking for Resumable Ingestion
# ============================================================================


class IngestionStatus(str, Enum):
    """Status of symbol ingestion."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SymbolProgress:
    """Progress tracking for individual symbol ingestion."""

    symbol: str
    status: IngestionStatus
    start_date: str  # ISO format timestamp
    end_date: str  # ISO format timestamp
    rows_ingested: int = 0
    started_at: str | None = None  # ISO format timestamp
    completed_at: str | None = None  # ISO format timestamp
    error_message: str | None = None


@dataclass
class IngestionProgress:
    """Overall ingestion progress for a bundle."""

    bundle_name: str
    frequency: str
    exchange_id: str
    total_symbols: int
    symbols: dict[str, SymbolProgress]
    started_at: str  # ISO format timestamp
    last_updated: str | None = None  # ISO format timestamp

    def get_pending_symbols(self) -> list[str]:
        """Get list of symbols that haven't been completed yet."""
        return [
            symbol
            for symbol, progress in self.symbols.items()
            if progress.status
            in (IngestionStatus.PENDING, IngestionStatus.FAILED, IngestionStatus.IN_PROGRESS)
        ]

    def get_completed_symbols(self) -> list[str]:
        """Get list of successfully completed symbols."""
        return [
            symbol
            for symbol, progress in self.symbols.items()
            if progress.status == IngestionStatus.COMPLETED
        ]

    def mark_in_progress(self, symbol: str) -> None:
        """Mark symbol as in progress."""
        if symbol in self.symbols:
            self.symbols[symbol].status = IngestionStatus.IN_PROGRESS
            self.symbols[symbol].started_at = datetime.now(UTC).isoformat()
            self.last_updated = datetime.now(UTC).isoformat()

    def mark_completed(self, symbol: str, rows_ingested: int) -> None:
        """Mark symbol as completed."""
        if symbol in self.symbols:
            self.symbols[symbol].status = IngestionStatus.COMPLETED
            self.symbols[symbol].rows_ingested = rows_ingested
            self.symbols[symbol].completed_at = datetime.now(UTC).isoformat()
            self.last_updated = datetime.now(UTC).isoformat()

    def mark_failed(self, symbol: str, error: str) -> None:
        """Mark symbol as failed with error message."""
        if symbol in self.symbols:
            self.symbols[symbol].status = IngestionStatus.FAILED
            self.symbols[symbol].error_message = error
            self.last_updated = datetime.now(UTC).isoformat()


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

        # Sort by timestamp and symbol for multi-symbol fetches
        # This ensures validation passes when multiple symbols are fetched sequentially
        df = df.sort(["timestamp", "symbol"])

        # Standardize and validate
        df = self.standardize(df)
        self.validate(df)

        self._log_fetch_success(symbols, start_date, end_date, resolution, len(df))

        return df

    @with_retry(max_retries=3, initial_delay=1.0, backoff_factor=2.0)  # type: ignore[misc]
    async def _fetch_ohlcv_batch(
        self, symbol: str, timeframe: str, since: int, limit: int = 1000
    ) -> list[list[int | float]]:
        """Fetch single OHLCV batch with retry logic.

        Wraps exchange.fetch_ohlcv with automatic retry on network errors.
        Uses exponential backoff with jitter to handle transient failures.

        Args:
            symbol: Trading pair symbol (e.g., "BTC/USDT")
            timeframe: CCXT timeframe string (e.g., "1h")
            since: Start timestamp in Unix milliseconds
            limit: Maximum bars to fetch per request

        Returns:
            List of OHLCV data: [[timestamp, o, h, l, c, v], ...]

        Raises:
            NetworkError: If API request fails after retries
            InvalidDataError: If symbol is invalid (not retried)
            RateLimitError: If rate limit exceeded (not retried)
        """
        try:
            # Fetch batch (CCXT handles async internally for some exchanges)
            if asyncio.iscoroutinefunction(self.exchange.fetch_ohlcv):
                ohlcv = await self.exchange.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=timeframe,
                    since=since,
                    limit=limit,
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
                        since=since,
                        limit=limit,
                    ),
                )

            return ohlcv if ohlcv else []

        except ccxt.NetworkError as e:
            # Retry decorator will catch and retry NetworkError
            raise NetworkError(f"CCXT network error for {self.exchange_id}: {e}") from e
        except ccxt.ExchangeNotAvailable as e:
            # Retry decorator will catch and retry NetworkError
            raise NetworkError(f"Exchange {self.exchange_id} unavailable: {e}") from e
        except ccxt.BadSymbol as e:
            # Invalid symbol - don't retry, fail immediately
            raise InvalidDataError(f"Invalid symbol {symbol}: {e}") from e
        except ccxt.RateLimitExceeded as e:
            # Rate limit - don't retry here, let rate limiter handle it
            raise RateLimitError(f"Rate limit exceeded on {self.exchange_id}: {e}") from e
        except Exception as e:
            # Catch-all for unexpected CCXT errors - treat as network error for retry
            logger.error(
                "ccxt_unexpected_error",
                exchange=self.exchange_id,
                symbol=symbol,
                error_type=type(e).__name__,
                error=str(e),
            )
            raise NetworkError(f"Unexpected CCXT error for {self.exchange_id}: {e}") from e

    async def _fetch_with_pagination(
        self, symbol: str, timeframe: str, since: int, until: int
    ) -> list[list[int | float | str]]:
        """Fetch OHLCV data with pagination for large date ranges.

        CCXT exchanges typically limit responses to 500-1000 bars per request.
        This method handles pagination automatically with retry logic for each batch.

        Args:
            symbol: Trading pair symbol (e.g., "BTC/USDT")
            timeframe: CCXT timeframe string (e.g., "1h")
            since: Start timestamp in Unix milliseconds
            until: End timestamp in Unix milliseconds

        Returns:
            List of OHLCV data with symbol appended: [[timestamp, o, h, l, c, v, symbol], ...]

        Raises:
            NetworkError: If API request fails after retries
            InvalidDataError: If symbol is invalid
            RateLimitError: If rate limit exceeded
        """
        all_ohlcv = []
        current_since = since

        while current_since < until:
            # Apply rate limiting
            await self.rate_limiter.acquire()

            # Fetch batch with automatic retry logic
            ohlcv = await self._fetch_ohlcv_batch(
                symbol=symbol,
                timeframe=timeframe,
                since=current_since,
                limit=1000,
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

    def _get_progress_file_path(self, bundle_name: str) -> Path:
        """Get path to ingestion progress file for bundle.

        Args:
            bundle_name: Name of the bundle

        Returns:
            Path to progress JSON file

        Example:
            >>> adapter._get_progress_file_path("crypto-hourly")
            Path("data/bundles/crypto-hourly/.ingestion_progress.json")
        """
        from rustybt.utils.paths import data_path

        bundle_dir = Path(data_path(["bundles", bundle_name]))
        return bundle_dir / ".ingestion_progress.json"

    def _load_progress(self, bundle_name: str) -> IngestionProgress | None:
        """Load ingestion progress from file if exists.

        Args:
            bundle_name: Name of the bundle

        Returns:
            IngestionProgress object if file exists and is valid, None otherwise
        """
        progress_file = self._get_progress_file_path(bundle_name)

        if not progress_file.exists():
            return None

        try:
            with open(progress_file) as f:
                data = json.load(f)

            # Reconstruct SymbolProgress objects
            symbols = {}
            for symbol, symbol_data in data["symbols"].items():
                symbols[symbol] = SymbolProgress(
                    symbol=symbol_data["symbol"],
                    status=IngestionStatus(symbol_data["status"]),
                    start_date=symbol_data["start_date"],
                    end_date=symbol_data["end_date"],
                    rows_ingested=symbol_data.get("rows_ingested", 0),
                    started_at=symbol_data.get("started_at"),
                    completed_at=symbol_data.get("completed_at"),
                    error_message=symbol_data.get("error_message"),
                )

            progress = IngestionProgress(
                bundle_name=data["bundle_name"],
                frequency=data["frequency"],
                exchange_id=data["exchange_id"],
                total_symbols=data["total_symbols"],
                symbols=symbols,
                started_at=data["started_at"],
                last_updated=data.get("last_updated"),
            )

            logger.info(
                "progress_loaded",
                bundle=bundle_name,
                completed=len(progress.get_completed_symbols()),
                pending=len(progress.get_pending_symbols()),
                total=progress.total_symbols,
            )

            return progress

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(
                "progress_file_corrupted",
                bundle=bundle_name,
                error=str(e),
                action="starting_fresh",
            )
            return None

    def _save_progress(self, progress: IngestionProgress) -> None:
        """Save ingestion progress to file.

        Args:
            progress: IngestionProgress object to save
        """
        progress_file = self._get_progress_file_path(progress.bundle_name)
        progress_file.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dict for JSON serialization
        data = {
            "bundle_name": progress.bundle_name,
            "frequency": progress.frequency,
            "exchange_id": progress.exchange_id,
            "total_symbols": progress.total_symbols,
            "started_at": progress.started_at,
            "last_updated": progress.last_updated,
            "symbols": {
                symbol: {
                    "symbol": symbol_progress.symbol,
                    "status": symbol_progress.status.value,
                    "start_date": symbol_progress.start_date,
                    "end_date": symbol_progress.end_date,
                    "rows_ingested": symbol_progress.rows_ingested,
                    "started_at": symbol_progress.started_at,
                    "completed_at": symbol_progress.completed_at,
                    "error_message": symbol_progress.error_message,
                }
                for symbol, symbol_progress in progress.symbols.items()
            },
        }

        # Atomic write using temp file
        temp_file = progress_file.with_suffix(".json.tmp")
        try:
            with open(temp_file, "w") as f:
                json.dump(data, f, indent=2)
            temp_file.replace(progress_file)

            logger.debug(
                "progress_saved",
                bundle=progress.bundle_name,
                completed=len(progress.get_completed_symbols()),
                pending=len(progress.get_pending_symbols()),
            )
        except Exception as e:
            logger.error("progress_save_failed", bundle=progress.bundle_name, error=str(e))
            if temp_file.exists():
                temp_file.unlink()
            raise

    def ingest_to_bundle(
        self,
        bundle_name: str,
        symbols: list[str],
        start: pd.Timestamp,
        end: pd.Timestamp,
        frequency: str,
        resume: bool = True,
        **kwargs: Any,
    ) -> None:
        """Ingest CCXT data into bundle (Parquet + metadata) with resumable progress tracking.

        Implements per-symbol ingestion with automatic progress tracking. If ingestion
        is interrupted, it can be resumed from where it left off by re-running with the
        same parameters.

        Args:
            bundle_name: Name of bundle to create/update
            symbols: List of symbols to ingest (e.g., ["BTC/USDT", "ETH/USDT"])
            start: Start timestamp for data range
            end: End timestamp for data range
            frequency: Time resolution (e.g., "1d", "1h", "1m")
            resume: Whether to resume from existing progress (default: True)
            **kwargs: Additional parameters (e.g., timezone="UTC")

        Raises:
            NetworkError: If data fetch fails after retries
            ValidationError: If data validation fails
            IOError: If bundle write fails

        Note:
            Progress is tracked in `.ingestion_progress.json` in the bundle directory.
            To force re-ingestion of all symbols, set resume=False.
        """
        normalized_symbols = normalize_symbols(symbols)

        # Load or create progress tracking
        progress = None
        if resume:
            progress = self._load_progress(bundle_name)

        if progress is None:
            # Create new progress tracker
            symbols_dict = {
                symbol: SymbolProgress(
                    symbol=symbol,
                    status=IngestionStatus.PENDING,
                    start_date=start.isoformat(),
                    end_date=end.isoformat(),
                )
                for symbol in normalized_symbols
            }
            progress = IngestionProgress(
                bundle_name=bundle_name,
                frequency=frequency,
                exchange_id=self.exchange_id,
                total_symbols=len(normalized_symbols),
                symbols=symbols_dict,
                started_at=datetime.now(UTC).isoformat(),
            )
            self._save_progress(progress)

        # Get symbols that need to be ingested
        pending_symbols = progress.get_pending_symbols()
        completed_symbols = progress.get_completed_symbols()

        logger.info(
            "ccxt_ingest_start",
            bundle=bundle_name,
            exchange=self.exchange_id,
            total_symbols=len(normalized_symbols),
            completed_symbols=len(completed_symbols),
            pending_symbols=len(pending_symbols),
            resume=resume,
            start=start,
            end=end,
            frequency=frequency,
        )

        if not pending_symbols:
            logger.info(
                "ccxt_ingest_already_complete",
                bundle=bundle_name,
                exchange=self.exchange_id,
                total_symbols=len(normalized_symbols),
            )
            return

        # Prepare bundle directory and writer
        bundle_dir = Path(data_path(["bundles", bundle_name]))
        ensure_directory(str(bundle_dir))
        writer = ParquetWriter(str(bundle_dir))

        metadata = self.get_metadata()
        timezone = kwargs.get("timezone", "UTC")

        # Ingest symbols one by one with progress tracking
        for symbol in pending_symbols:
            try:
                # Mark as in progress
                progress.mark_in_progress(symbol)
                self._save_progress(progress)

                logger.info(
                    "ccxt_symbol_ingest_start",
                    bundle=bundle_name,
                    symbol=symbol,
                    progress=f"{len(completed_symbols) + 1}/{len(normalized_symbols)}",
                )

                # Fetch data for this symbol only
                df = run_async(self.fetch([symbol], start, end, frequency))

                if df.is_empty():
                    logger.warning(
                        "ccxt_no_data_for_symbol",
                        bundle=bundle_name,
                        symbol=symbol,
                    )
                    # Mark as completed with 0 rows (no data available for this symbol)
                    progress.mark_completed(symbol, rows_ingested=0)
                    self._save_progress(progress)
                    completed_symbols.append(symbol)
                    continue

                # Prepare data for writing
                symbol_map = build_symbol_sid_map([symbol], bundle_name=bundle_name)
                df_prepared, frame_type = prepare_ohlcv_frame(df, symbol_map, frequency)

                # Prepare source metadata
                source_metadata = {
                    "source_type": metadata.source_type,
                    "source_url": metadata.source_url,
                    "api_version": metadata.api_version,
                    "symbols": [symbol],
                    "exchange": self.exchange_id,
                    "timezone": timezone,
                    "symbol_map": symbol_map,  # Pass SID mapping to ensure parquet-DB consistency
                }

                # Write to bundle
                if frame_type == "daily":
                    writer.write_daily_bars(
                        df_prepared,
                        bundle_name=bundle_name,
                        source_metadata=source_metadata,
                    )
                else:
                    writer.write_minute_bars(
                        df_prepared,
                        bundle_name=bundle_name,
                        source_metadata=source_metadata,
                    )

                # Mark as completed
                progress.mark_completed(symbol, rows_ingested=len(df_prepared))
                self._save_progress(progress)
                completed_symbols.append(symbol)

                logger.info(
                    "ccxt_symbol_ingest_complete",
                    bundle=bundle_name,
                    symbol=symbol,
                    rows=len(df_prepared),
                    progress=f"{len(completed_symbols)}/{len(normalized_symbols)}",
                )

            except (NetworkError, InvalidDataError, RateLimitError) as e:
                # Mark symbol as failed but continue with other symbols
                error_msg = f"{type(e).__name__}: {str(e)}"
                progress.mark_failed(symbol, error=error_msg)
                self._save_progress(progress)

                logger.error(
                    "ccxt_symbol_ingest_failed",
                    bundle=bundle_name,
                    symbol=symbol,
                    error=error_msg,
                    will_retry_on_next_run=True,
                )

                # Continue with next symbol instead of failing entire ingestion
                continue

        # Final summary
        final_completed = progress.get_completed_symbols()
        final_pending = progress.get_pending_symbols()

        logger.info(
            "ccxt_ingest_complete",
            bundle=bundle_name,
            exchange=self.exchange_id,
            completed=len(final_completed),
            failed=len(
                [s for s in progress.symbols.values() if s.status == IngestionStatus.FAILED]
            ),
            total=len(normalized_symbols),
            bundle_path=str(bundle_dir),
        )

        # If there are still pending/failed symbols, inform user
        if final_pending:
            logger.warning(
                "ccxt_ingest_incomplete",
                bundle=bundle_name,
                pending_symbols=final_pending[:5] if len(final_pending) > 5 else final_pending,
                total_pending=len(final_pending),
                message="Re-run ingestion to retry failed symbols",
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
