"""Base data adapter framework for RustyBT.

This module provides the abstract base class and supporting infrastructure
for implementing data source adapters with standardized error handling,
validation, rate limiting, and retry logic.
"""

import asyncio
import random
import time
from abc import ABC, abstractmethod
from decimal import getcontext
from functools import wraps
from typing import TYPE_CHECKING, Optional

import pandas as pd
import polars as pl
import structlog

if TYPE_CHECKING:
    from rustybt.data.polars.validation import DataValidator

# Set decimal precision for financial calculations
getcontext().prec = 28

logger = structlog.get_logger()


# ============================================================================
# Exception Hierarchy
# ============================================================================


# Import centralized exceptions
from rustybt.exceptions import (
    DataAdapterError,
    DataValidationError,
)


# Legacy aliases for backward compatibility
class NetworkError(DataAdapterError):
    """Network connectivity error during data fetching."""

    def __init__(self, message: str, adapter: str | None = None):
        super().__init__(message, adapter=adapter)


class RateLimitError(DataAdapterError):
    """API rate limit exceeded during data fetching."""

    def __init__(self, message: str, adapter: str | None = None, reset_after: float | None = None):
        context = {"reset_after": reset_after} if reset_after is not None else None
        super().__init__(message, adapter=adapter, context=context)


# Use centralized exceptions
InvalidDataError = DataValidationError
ValidationError = DataValidationError


# ============================================================================
# Rate Limiter
# ============================================================================


class RateLimiter:
    """Token bucket rate limiter for API requests.

    Uses token bucket algorithm to enforce request rate limits with burst support.

    Attributes:
        rate: Maximum requests per second
        burst_size: Maximum burst size (tokens available at start)
        tokens: Current number of available tokens
        last_update: Timestamp of last token refill
        requests_made: Total requests processed
        throttle_events: Number of times requests were throttled
    """

    def __init__(self, requests_per_second: int, burst_size: int | None = None) -> None:
        """Initialize rate limiter.

        Args:
            requests_per_second: Maximum requests per second to allow
            burst_size: Maximum burst size (defaults to requests_per_second)
        """
        self.rate = requests_per_second
        self.burst_size = burst_size or requests_per_second
        self.tokens = float(self.burst_size)
        self.last_update = time.time()
        self.lock = asyncio.Lock()
        self.requests_made = 0
        self.throttle_events = 0

    async def acquire(self) -> None:
        """Acquire permission to make request.

        Blocks if rate limit would be exceeded. Uses token bucket algorithm
        to refill tokens based on elapsed time.
        """
        async with self.lock:
            now = time.time()
            elapsed = now - self.last_update

            # Refill tokens based on elapsed time
            self.tokens = min(self.burst_size, self.tokens + elapsed * self.rate)
            self.last_update = now

            # Wait if no tokens available
            if self.tokens < 1:
                wait_time = (1 - self.tokens) / self.rate
                self.throttle_events += 1
                logger.warning(
                    "rate_limit_throttle",
                    wait_time=wait_time,
                    requests_made=self.requests_made,
                    throttle_events=self.throttle_events,
                )
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= 1

            self.requests_made += 1


# ============================================================================
# Retry Decorator
# ============================================================================


def with_retry(max_retries: int = 3, initial_delay: float = 1.0, backoff_factor: float = 2.0):
    """Decorator for retry logic with exponential backoff and jitter.

    Retries transient errors (NetworkError, TimeoutError) with exponential
    backoff. Non-retryable errors are raised immediately.

    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds before first retry
        backoff_factor: Multiplier for exponential backoff (delay *= backoff_factor)

    Returns:
        Decorated async function with retry logic

    Example:
        >>> @with_retry(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
        ... async def fetch_data():
        ...     return await api.get("/data")
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except (NetworkError, TimeoutError) as e:
                    last_exception = e

                    if attempt < max_retries - 1:
                        # Calculate delay with exponential backoff and jitter
                        delay = initial_delay * (backoff_factor**attempt)
                        jitter = delay * random.uniform(-0.2, 0.2)
                        actual_delay = max(0, delay + jitter)

                        logger.warning(
                            "retry_attempt",
                            attempt=attempt + 1,
                            max_retries=max_retries,
                            delay=actual_delay,
                            error=str(e),
                        )

                        await asyncio.sleep(actual_delay)
                    else:
                        logger.error("retry_exhausted", attempts=max_retries, error=str(e))

            raise last_exception

        return wrapper

    return decorator


# ============================================================================
# Validation Functions
# ============================================================================


def validate_ohlcv_relationships(df: pl.DataFrame) -> bool:
    """Validate OHLCV relationships and data quality.

    Checks:
    - Required columns exist
    - OHLCV relationships valid (high >= low, high >= open/close, etc.)
    - No NULL values in required columns
    - Timestamps are sorted
    - No duplicate timestamps per symbol

    Args:
        df: DataFrame to validate

    Returns:
        True if validation passes

    Raises:
        ValidationError: If any validation check fails
    """
    # Check required columns exist
    required_cols = ["timestamp", "symbol", "open", "high", "low", "close", "volume"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValidationError(f"Missing required columns: {missing_cols}")

    # Validate OHLCV relationships
    invalid_rows = df.filter(
        (pl.col("high") < pl.col("low"))
        | (pl.col("high") < pl.col("open"))
        | (pl.col("high") < pl.col("close"))
        | (pl.col("low") > pl.col("open"))
        | (pl.col("low") > pl.col("close"))
    )

    if len(invalid_rows) > 0:
        raise ValidationError(
            f"Invalid OHLCV relationships in {len(invalid_rows)} rows",
            invalid_rows=invalid_rows.select(
                ["timestamp", "symbol", "open", "high", "low", "close"]
            ),
        )

    # Check for NULL values
    null_counts = df.select([pl.col(c).null_count().alias(c) for c in required_cols])
    total_nulls = sum(null_counts.row(0))
    if total_nulls > 0:
        null_dict = {k: v for k, v in zip(required_cols, null_counts.row(0), strict=False) if v > 0}
        raise ValidationError(f"NULL values found in required columns: {null_dict}")

    # Temporal consistency: timestamps must be sorted
    if not df["timestamp"].is_sorted():
        raise ValidationError("Timestamps are not sorted")

    # Check for duplicate timestamps per symbol
    duplicates = df.group_by(["symbol", "timestamp"]).agg(pl.count()).filter(pl.col("count") > 1)
    if len(duplicates) > 0:
        raise ValidationError(
            f"Duplicate timestamps found for {len(duplicates)} symbol-timestamp pairs"
        )

    return True


def detect_outliers(df: pl.DataFrame, threshold: float = 3.0) -> pl.DataFrame:
    """Detect price outliers using median absolute deviation (MAD).

    Uses MAD which is more robust to outliers than standard deviation.
    Identifies price changes that exceed threshold * MAD from median.

    Args:
        df: DataFrame with OHLCV data
        threshold: Number of MADs for outlier detection (default: 3.0)

    Returns:
        DataFrame containing only outlier rows

    Example:
        >>> outliers = detect_outliers(data, threshold=3.0)
        >>> if len(outliers) > 0:
        ...     print(f"Found {len(outliers)} outliers")
    """
    # Calculate price changes
    df_with_changes = df.with_columns(
        [(pl.col("close") / pl.col("close").shift(1) - 1).alias("pct_change")]
    )

    # Calculate median and MAD of price changes per symbol
    # MAD = median(|x_i - median(x)|)
    stats = df_with_changes.group_by("symbol").agg(
        [
            pl.col("pct_change").median().alias("median_change"),
            (pl.col("pct_change") - pl.col("pct_change").median())
            .abs()
            .median()
            .alias("mad_change"),
        ]
    )

    # Join stats back to main dataframe
    df_with_stats = df_with_changes.join(stats, on="symbol", how="left")

    # Flag outliers using MAD
    # An outlier is when |pct_change - median| > threshold * MAD
    # Filter out null values from pct_change (first row will be null due to shift)
    outliers = df_with_stats.filter(
        pl.col("pct_change").is_not_null()
        & pl.col("mad_change").is_not_null()
        & (pl.col("mad_change") > 0)  # Avoid division issues
        & (
            (pl.col("pct_change") - pl.col("median_change")).abs()
            > (threshold * pl.col("mad_change"))
        )
    )

    if len(outliers) > 0:
        logger.warning(
            "outliers_detected",
            count=len(outliers),
            symbols=outliers["symbol"].unique().to_list(),
            max_deviation=float(outliers["pct_change"].abs().max()),
        )

    return outliers.select(["timestamp", "symbol", "open", "high", "low", "close", "pct_change"])


# ============================================================================
# Base Data Adapter
# ============================================================================


class BaseDataAdapter(ABC):
    """Base class for data source adapters.

    Provides standardized interface for fetching, validating, and standardizing
    market data from various sources. Includes built-in rate limiting, retry logic,
    and error handling.

    Attributes:
        name: Adapter name for logging and identification
        rate_limiter: RateLimiter instance for API throttling
        max_retries: Maximum number of retry attempts for transient errors
        initial_retry_delay: Initial delay before first retry (seconds)
        backoff_factor: Multiplier for exponential backoff

    Example:
        >>> class MyAdapter(BaseDataAdapter):
        ...     async def fetch(self, symbols, start_date, end_date, resolution):
        ...         # Implementation here
        ...         pass
        ...
        ...     def validate(self, df):
        ...         return validate_ohlcv_relationships(df)
        ...
        ...     def standardize(self, df):
        ...         # Convert to standard schema
        ...         return df
    """

    # Standard OHLCV schema (expected output format)
    STANDARD_SCHEMA = {
        "timestamp": pl.Datetime("us"),
        "symbol": pl.Utf8,
        "open": pl.Decimal(precision=18, scale=8),
        "high": pl.Decimal(precision=18, scale=8),
        "low": pl.Decimal(precision=18, scale=8),
        "close": pl.Decimal(precision=18, scale=8),
        "volume": pl.Decimal(precision=18, scale=8),
    }

    def __init__(
        self,
        name: str,
        rate_limit_per_second: int = 10,
        max_retries: int = 3,
        initial_retry_delay: float = 1.0,
        backoff_factor: float = 2.0,
        validator: Optional["DataValidator"] = None,
    ) -> None:
        """Initialize base data adapter.

        Args:
            name: Adapter name for logging and identification
            rate_limit_per_second: Maximum requests per second
            max_retries: Maximum retry attempts for transient errors
            initial_retry_delay: Initial delay before first retry (seconds)
            backoff_factor: Multiplier for exponential backoff
            validator: Optional DataValidator for multi-layer data validation
        """
        self.name = name
        self.rate_limiter = RateLimiter(requests_per_second=rate_limit_per_second)
        self.max_retries = max_retries
        self.initial_retry_delay = initial_retry_delay
        self.backoff_factor = backoff_factor
        self.validator = validator

    @abstractmethod
    async def fetch(
        self,
        symbols: list[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        resolution: str,
    ) -> pl.DataFrame:
        """Fetch OHLCV data and return Polars DataFrame with Decimal columns.

        Must be implemented by subclasses. Should fetch raw data from source,
        apply standardization, and validate before returning.

        Args:
            symbols: List of symbols to fetch (e.g., ["AAPL", "MSFT"])
            start_date: Start date for data range
            end_date: End date for data range
            resolution: Time resolution (e.g., "1d", "1h", "1m")

        Returns:
            Polars DataFrame with standardized OHLCV schema

        Raises:
            NetworkError: If API request fails
            RateLimitError: If rate limit exceeded
            InvalidDataError: If received data is invalid
            ValidationError: If data validation fails
        """
        pass

    def validate(self, df: pl.DataFrame) -> bool:
        """Validate OHLCV data quality and relationships.

        If a DataValidator was provided at initialization, uses multi-layer
        validation. Otherwise, uses basic validation (validate_ohlcv_relationships).
        Subclasses can override this method for custom validation logic.

        Args:
            df: DataFrame to validate

        Returns:
            True if validation passes

        Raises:
            ValidationError: If data validation fails
        """
        if self.validator is not None:
            # Use multi-layer validation
            self.validator.validate_and_raise(df)
            return True
        else:
            # Use basic validation (backward compatibility)
            return validate_ohlcv_relationships(df)

    @abstractmethod
    def standardize(self, df: pl.DataFrame) -> pl.DataFrame:
        """Convert provider-specific format to RustyBT standard schema.

        Must be implemented by subclasses. Should convert provider-specific
        column names and data types to standard OHLCV schema.

        Args:
            df: DataFrame in provider-specific format

        Returns:
            DataFrame with standardized schema and Decimal columns
        """
        pass

    def _log_fetch_success(
        self,
        symbols: list[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        resolution: str,
        row_count: int,
    ) -> None:
        """Log successful data fetch.

        Args:
            symbols: Symbols fetched
            start_date: Start date of range
            end_date: End date of range
            resolution: Time resolution
            row_count: Number of rows fetched
        """
        logger.info(
            "data_fetched",
            adapter=self.name,
            symbols=symbols,
            start_date=str(start_date),
            end_date=str(end_date),
            rows=row_count,
            resolution=resolution,
        )

    def _log_validation_failure(self, error: ValidationError) -> None:
        """Log validation failure.

        Args:
            error: ValidationError that occurred
        """
        logger.error(
            "validation_failed",
            adapter=self.name,
            error_type=type(error).__name__,
            error_message=str(error),
            invalid_rows=(len(error.invalid_rows) if error.invalid_rows is not None else 0),
        )
