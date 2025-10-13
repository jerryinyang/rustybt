"""Base API provider adapter with authentication and rate limiting.

This module provides the base class for data API providers (Polygon, Alpaca, Alpha Vantage)
with authentication support, API key management, rate limiting, and error handling.
"""

import configparser
import os
import time
from abc import abstractmethod
from pathlib import Path

import aiohttp
import pandas as pd
import polars as pl
import structlog

from rustybt.data.adapters.base import (
    BaseDataAdapter,
    DataAdapterError,
    NetworkError,
    RateLimitError,
    with_retry,
)

logger = structlog.get_logger()


# ============================================================================
# API Provider Exception Hierarchy
# ============================================================================


class AuthenticationError(DataAdapterError):
    """API authentication failed."""

    pass


class SymbolNotFoundError(DataAdapterError):
    """Symbol not found in data provider."""

    pass


class QuotaExceededError(RateLimitError):
    """API quota exceeded (daily/monthly limit)."""

    pass


class DataParsingError(DataAdapterError):
    """Failed to parse API response."""

    pass


# ============================================================================
# API Rate Limiter with Daily Quota Support
# ============================================================================


class APIRateLimiter:
    """Rate limiter with per-minute and per-day quota support.

    Tracks requests per minute and per day to enforce API tier limits.
    Supports free tier and paid tier configurations.

    Attributes:
        requests_per_minute: Maximum requests allowed per minute
        requests_per_day: Maximum requests allowed per day (None = unlimited)
        minute_requests: List of timestamps for requests in current minute
        day_requests: List of timestamps for requests in current day
        quota_warnings_sent: Track if quota warning already logged
    """

    def __init__(
        self,
        requests_per_minute: int,
        requests_per_day: int | None = None,
    ) -> None:
        """Initialize API rate limiter.

        Args:
            requests_per_minute: Maximum requests per minute
            requests_per_day: Maximum requests per day (None for unlimited)
        """
        self.requests_per_minute = requests_per_minute
        self.requests_per_day = requests_per_day
        self.minute_requests: list[float] = []
        self.day_requests: list[float] = []
        self.quota_warnings_sent = False

    async def acquire(self) -> None:
        """Acquire permission to make API request.

        Blocks if rate limit would be exceeded. Cleans up expired timestamps
        and waits if necessary to respect rate limits.

        Raises:
            QuotaExceededError: If daily quota is exhausted
        """
        now = time.time()

        # Clean up old requests (older than 1 minute for minute limit)
        minute_ago = now - 60
        self.minute_requests = [t for t in self.minute_requests if t > minute_ago]

        # Clean up old requests (older than 1 day for day limit)
        day_ago = now - 86400
        self.day_requests = [t for t in self.day_requests if t > day_ago]

        # Check daily quota
        if self.requests_per_day is not None:
            if len(self.day_requests) >= self.requests_per_day:
                raise QuotaExceededError(
                    f"Daily quota of {self.requests_per_day} requests exceeded. "
                    f"Resets in {int(86400 - (now - min(self.day_requests)))} seconds."
                )

            # Log warning at 80% of daily quota
            quota_used_pct = (len(self.day_requests) / self.requests_per_day) * 100
            if quota_used_pct >= 80 and not self.quota_warnings_sent:
                logger.warning(
                    "api_quota_warning",
                    quota_used_pct=quota_used_pct,
                    requests_remaining=self.requests_per_day - len(self.day_requests),
                )
                self.quota_warnings_sent = True

        # Check per-minute rate limit
        if len(self.minute_requests) >= self.requests_per_minute:
            # Wait until oldest request expires
            wait_time = 60 - (now - self.minute_requests[0])
            if wait_time > 0:
                logger.warning(
                    "rate_limit_throttle",
                    wait_time=wait_time,
                    requests_per_minute=self.requests_per_minute,
                )
                import asyncio

                await asyncio.sleep(wait_time)
                now = time.time()

        # Record this request
        self.minute_requests.append(now)
        self.day_requests.append(now)

        # Reset warning flag if we're back below 80%
        if self.requests_per_day is not None:
            quota_used_pct = (len(self.day_requests) / self.requests_per_day) * 100
            if quota_used_pct < 80:
                self.quota_warnings_sent = False


# ============================================================================
# Base API Provider Adapter
# ============================================================================


class BaseAPIProviderAdapter(BaseDataAdapter):
    """Base class for data API provider adapters.

    Extends BaseDataAdapter with authentication support, API key management,
    provider-specific rate limiting, and enhanced error handling.

    Attributes:
        api_key: Primary API key for authentication
        api_secret: Optional API secret for providers requiring key+secret
        api_rate_limiter: APIRateLimiter instance for quota enforcement
        session: aiohttp ClientSession for HTTP requests
        base_url: Base URL for API endpoints
    """

    def __init__(
        self,
        name: str,
        api_key_env_var: str,
        api_secret_env_var: str | None = None,
        requests_per_minute: int = 10,
        requests_per_day: int | None = None,
        base_url: str = "",
    ) -> None:
        """Initialize base API provider adapter.

        Args:
            name: Adapter name for logging
            api_key_env_var: Environment variable name for API key
            api_secret_env_var: Optional environment variable for API secret
            requests_per_minute: Maximum requests per minute
            requests_per_day: Maximum requests per day (None for unlimited)
            base_url: Base URL for API endpoints

        Raises:
            AuthenticationError: If API key not found in environment or config
        """
        # Initialize base adapter (skips standard rate limiter)
        super().__init__(
            name=name,
            rate_limit_per_second=requests_per_minute,
            max_retries=3,
            initial_retry_delay=1.0,
            backoff_factor=2.0,
        )

        # Load API credentials
        self.api_key, self.api_secret = self._load_credentials(api_key_env_var, api_secret_env_var)

        # Validate API key exists
        if not self.api_key:
            raise AuthenticationError(
                f"API key not found. Set environment variable {api_key_env_var} "
                f"or add to ~/.rustybt/api_keys.ini"
            )

        # Check for API keys in version control (security warning)
        self._check_api_key_security()

        # Initialize API-specific rate limiter
        self.api_rate_limiter = APIRateLimiter(
            requests_per_minute=requests_per_minute,
            requests_per_day=requests_per_day,
        )

        # HTTP session (created on first request)
        self.session: aiohttp.ClientSession | None = None
        self.base_url = base_url

        logger.info(
            "api_provider_initialized",
            adapter=self.name,
            rate_limit_per_minute=requests_per_minute,
            rate_limit_per_day=requests_per_day,
        )

    def _load_credentials(
        self, api_key_env_var: str, api_secret_env_var: str | None
    ) -> tuple[str | None, str | None]:
        """Load API credentials from environment variables or config file.

        Checks in order:
        1. Environment variables
        2. ~/.rustybt/api_keys.ini config file

        Args:
            api_key_env_var: Environment variable name for API key
            api_secret_env_var: Optional environment variable for API secret

        Returns:
            Tuple of (api_key, api_secret) - either can be None if not found
        """
        # Try environment variables first
        api_key = os.environ.get(api_key_env_var)
        api_secret = os.environ.get(api_secret_env_var) if api_secret_env_var else None

        if api_key:
            logger.debug(
                "api_key_loaded_from_env",
                adapter=self.name,
                env_var=api_key_env_var,
            )
            return api_key, api_secret

        # Try config file
        config_path = Path.home() / ".rustybt" / "api_keys.ini"
        if config_path.exists():
            config = configparser.ConfigParser()
            config.read(config_path)

            if self.name in config:
                api_key = config[self.name].get("api_key")
                api_secret = config[self.name].get("api_secret")
                logger.debug(
                    "api_key_loaded_from_config",
                    adapter=self.name,
                    config_path=str(config_path),
                )
                return api_key, api_secret

        return None, None

    def _check_api_key_security(self) -> None:
        """Check for API keys in version control and log warning.

        Scans .env and api_keys.ini files to ensure they're in .gitignore.
        """
        security_issues = []

        # Check if .env exists and is in .gitignore
        if Path(".env").exists():
            gitignore_path = Path(".gitignore")
            if gitignore_path.exists():
                gitignore_content = gitignore_path.read_text()
                if ".env" not in gitignore_content:
                    security_issues.append(".env file exists but not in .gitignore")
            else:
                security_issues.append(".env file exists but no .gitignore found")

        # Check if api_keys.ini exists in project root
        if Path("api_keys.ini").exists():
            security_issues.append("api_keys.ini found in project root - should be in ~/.rustybt/")

        if security_issues:
            logger.warning(
                "api_key_security_warning",
                adapter=self.name,
                issues=security_issues,
                recommendation=(
                    "Ensure API key files are in .gitignore and not committed to version control"
                ),
            )

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session.

        Returns:
            Active aiohttp ClientSession
        """
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers=self._get_auth_headers(),
                timeout=aiohttp.ClientTimeout(total=30),
            )
        return self.session

    async def close(self) -> None:
        """Close HTTP session and cleanup resources."""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.debug("api_session_closed", adapter=self.name)

    @abstractmethod
    def _get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers for API requests.

        Must be implemented by subclasses to provide provider-specific
        authentication headers.

        Returns:
            Dictionary of HTTP headers for authentication
        """
        pass

    @abstractmethod
    def _get_auth_params(self) -> dict[str, str]:
        """Get authentication query parameters for API requests.

        Must be implemented by subclasses to provide provider-specific
        authentication query parameters.

        Returns:
            Dictionary of query parameters for authentication
        """
        pass

    @with_retry(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
    async def _make_request(
        self,
        method: str,
        url: str,
        params: dict[str, str] | None = None,
        **kwargs,
    ) -> dict:
        """Make authenticated HTTP request with rate limiting and retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full URL or path (if path, prepended with base_url)
            params: Query parameters
            **kwargs: Additional arguments for aiohttp request

        Returns:
            Parsed JSON response as dictionary

        Raises:
            AuthenticationError: If authentication fails (401, 403)
            QuotaExceededError: If rate limit exceeded (429)
            SymbolNotFoundError: If symbol not found (404)
            NetworkError: If network request fails
            DataParsingError: If response parsing fails
        """
        # Enforce rate limiting
        await self.api_rate_limiter.acquire()

        # Build full URL
        if not url.startswith("http"):
            url = self.base_url + url

        # Merge auth params with request params
        all_params = {**(params or {}), **self._get_auth_params()}

        # Get session
        session = await self._get_session()

        try:
            async with session.request(method, url, params=all_params, **kwargs) as response:
                # Handle authentication errors
                if response.status in (401, 403):
                    error_text = await response.text()
                    raise AuthenticationError(
                        f"Authentication failed for {self.name}: {error_text}"
                    )

                # Handle rate limit errors
                if response.status == 429:
                    retry_after = response.headers.get("Retry-After", "60")
                    raise QuotaExceededError(
                        f"Rate limit exceeded for {self.name}. Retry after {retry_after}s"
                    )

                # Handle symbol not found
                if response.status == 404:
                    raise SymbolNotFoundError(f"Symbol not found in {self.name} API")

                # Raise for other HTTP errors
                response.raise_for_status()

                # Parse JSON response
                try:
                    data = await response.json()
                    return data
                except Exception as e:
                    raise DataParsingError(f"Failed to parse JSON response from {self.name}: {e}")

        except aiohttp.ClientError as e:
            raise NetworkError(f"Network error for {self.name}: {e}")

    async def authenticate(self) -> bool:
        """Authenticate with API provider (for OAuth flows).

        Default implementation validates API key exists. Override for
        providers requiring OAuth or other authentication flows.

        Returns:
            True if authentication successful

        Raises:
            AuthenticationError: If authentication fails
        """
        if not self.api_key:
            raise AuthenticationError(f"No API key configured for {self.name}")

        logger.info("api_authenticated", adapter=self.name)
        return True

    @abstractmethod
    async def fetch_ohlcv(
        self,
        symbol: str,
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        timeframe: str,
    ) -> pl.DataFrame:
        """Fetch OHLCV data for single symbol.

        Must be implemented by subclasses with provider-specific logic.

        Args:
            symbol: Symbol to fetch
            start_date: Start date
            end_date: End date
            timeframe: Timeframe (provider-specific format)

        Returns:
            Polars DataFrame with OHLCV data in standard schema
        """
        pass

    async def fetch(
        self,
        symbols: list[str],
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
        resolution: str,
    ) -> pl.DataFrame:
        """Fetch OHLCV data for multiple symbols.

        Implements BaseDataAdapter.fetch() by calling fetch_ohlcv() for each symbol.

        Args:
            symbols: List of symbols to fetch
            start_date: Start date
            end_date: End date
            resolution: Time resolution

        Returns:
            Polars DataFrame with standardized OHLCV schema
        """
        frames = []

        for symbol in symbols:
            try:
                df = await self.fetch_ohlcv(symbol, start_date, end_date, resolution)
                frames.append(df)
            except SymbolNotFoundError:
                logger.warning(
                    "symbol_not_found",
                    adapter=self.name,
                    symbol=symbol,
                )
                continue

        if not frames:
            raise SymbolNotFoundError(f"No data found for symbols {symbols} in {self.name}")

        # Concatenate all symbol data
        result = pl.concat(frames)

        # Validate and log
        self.validate(result)
        self._log_fetch_success(symbols, start_date, end_date, resolution, len(result))

        return result
