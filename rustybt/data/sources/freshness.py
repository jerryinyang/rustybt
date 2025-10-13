"""Cache freshness policies for market-aware staleness detection.

Provides different freshness strategies based on market hours, data frequency,
and adapter type to avoid serving stale data while maximizing cache hit rates.
"""

import time
from abc import ABC, abstractmethod
from typing import Any

import pandas as pd
from exchange_calendars import ExchangeCalendar


class CacheFreshnessPolicy(ABC):
    """Abstract base class for cache freshness policies.

    Freshness policies determine when cached data becomes stale and should be
    re-fetched from the underlying adapter.

    Implementations:
    - MarketCloseFreshnessPolicy: Daily data stale after market close
    - TTLFreshnessPolicy: Simple time-to-live (seconds)
    - HybridFreshnessPolicy: TTL + market hours awareness
    - NeverStaleFreshnessPolicy: Static data (CSV files)
    - AlwaysStaleFreshnessPolicy: Live trading (no caching)
    """

    @abstractmethod
    def is_fresh(
        self,
        bundle_metadata: dict[str, Any],
        frequency: str,
        calendar: ExchangeCalendar | None = None,
    ) -> bool:
        """Check if cached data is still fresh.

        Args:
            bundle_metadata: Cache metadata with fetch_timestamp field
            frequency: Data frequency (e.g., "1d", "1h", "1m")
            calendar: Exchange calendar for market hours (optional)

        Returns:
            True if cache entry is fresh, False if stale
        """
        pass

    @abstractmethod
    def get_next_refresh_time(
        self,
        bundle_metadata: dict[str, Any],
        frequency: str,
        calendar: ExchangeCalendar | None = None,
    ) -> pd.Timestamp:
        """Get timestamp when cache entry should be invalidated.

        Args:
            bundle_metadata: Cache metadata
            frequency: Data frequency
            calendar: Exchange calendar (optional)

        Returns:
            Timestamp when cache becomes stale
        """
        pass


class MarketCloseFreshnessPolicy(CacheFreshnessPolicy):
    """Daily data is fresh until the last market close.

    Used for daily equity data where new data arrives after market close.
    Handles weekends (Friday close) and holidays via exchange calendar.

    Example:
        >>> policy = MarketCloseFreshnessPolicy()
        >>> calendar = get_calendar('NYSE')
        >>> # Fetched Friday 5 PM, checking Saturday 10 AM
        >>> bundle = {'fetch_timestamp': friday_5pm}
        >>> is_fresh = policy.is_fresh(bundle, '1d', calendar)
        >>> # Returns True (fresh until Monday close)
    """

    def is_fresh(
        self,
        bundle_metadata: dict[str, Any],
        frequency: str,
        calendar: ExchangeCalendar | None = None,
    ) -> bool:
        """Cache is fresh if fetched after last market close.

        Args:
            bundle_metadata: Cache metadata
            frequency: Data frequency (should be "1d" for this policy)
            calendar: Exchange calendar for market close times

        Returns:
            True if fetched after last market close, False otherwise
        """
        if calendar is None:
            # Fallback to 1-hour TTL without calendar
            return self._fallback_ttl_check(bundle_metadata, 3600)

        fetch_timestamp = bundle_metadata.get("fetch_timestamp", 0)
        fetch_time = pd.Timestamp(fetch_timestamp, unit="s", tz="UTC")

        # Get last market close time
        current_time = pd.Timestamp.now(tz="UTC")
        try:
            last_close = calendar.previous_close(current_time)
        except Exception:
            # Fallback if calendar lookup fails
            return self._fallback_ttl_check(bundle_metadata, 3600)

        # Cache is fresh if fetched after last close
        return fetch_time >= last_close

    def get_next_refresh_time(
        self,
        bundle_metadata: dict[str, Any],
        frequency: str,
        calendar: ExchangeCalendar | None = None,
    ) -> pd.Timestamp:
        """Next refresh is at next market close.

        Args:
            bundle_metadata: Cache metadata
            frequency: Data frequency
            calendar: Exchange calendar

        Returns:
            Timestamp of next market close
        """
        if calendar is None:
            # Fallback: 1 hour from now
            return pd.Timestamp.now(tz="UTC") + pd.Timedelta(hours=1)

        current_time = pd.Timestamp.now(tz="UTC")
        try:
            next_close = calendar.next_close(current_time)
            return next_close
        except Exception:
            # Fallback
            return current_time + pd.Timedelta(hours=1)

    def _fallback_ttl_check(self, bundle_metadata: dict[str, Any], ttl_seconds: int) -> bool:
        """Fallback TTL check when calendar is unavailable."""
        fetch_timestamp = bundle_metadata.get("fetch_timestamp", 0)
        current_time = time.time()
        age_seconds = current_time - fetch_timestamp
        return age_seconds < ttl_seconds


class TTLFreshnessPolicy(CacheFreshnessPolicy):
    """Simple time-to-live (TTL) freshness policy.

    Cache is fresh for a fixed duration after fetch. Used for 24/7 markets
    (crypto) where market hours don't apply.

    Default TTLs:
    - Daily: 24 hours
    - Hourly: 1 hour
    - Minute: 5 minutes

    Example:
        >>> policy = TTLFreshnessPolicy(ttl_seconds=3600)  # 1 hour
        >>> bundle = {'fetch_timestamp': one_hour_ago}
        >>> is_fresh = policy.is_fresh(bundle, '1h')
        >>> # Returns False (stale)
    """

    def __init__(self, ttl_seconds: int | None = None):
        """Initialize TTL policy.

        Args:
            ttl_seconds: Time-to-live in seconds. If None, auto-selects based on frequency.
        """
        self.ttl_seconds = ttl_seconds

    def is_fresh(
        self,
        bundle_metadata: dict[str, Any],
        frequency: str,
        calendar: ExchangeCalendar | None = None,
    ) -> bool:
        """Cache is fresh if age < TTL.

        Args:
            bundle_metadata: Cache metadata
            frequency: Data frequency (used for auto TTL if not specified)
            calendar: Ignored (not used for TTL policy)

        Returns:
            True if age < TTL, False otherwise
        """
        ttl = (
            self.ttl_seconds
            if self.ttl_seconds is not None
            else self._get_ttl_for_frequency(frequency)
        )

        fetch_timestamp = bundle_metadata.get("fetch_timestamp", 0)
        current_time = time.time()
        age_seconds = current_time - fetch_timestamp

        return age_seconds < ttl

    def get_next_refresh_time(
        self,
        bundle_metadata: dict[str, Any],
        frequency: str,
        calendar: ExchangeCalendar | None = None,
    ) -> pd.Timestamp:
        """Next refresh is fetch_time + TTL.

        Args:
            bundle_metadata: Cache metadata
            frequency: Data frequency
            calendar: Ignored

        Returns:
            Timestamp when TTL expires
        """
        ttl = (
            self.ttl_seconds
            if self.ttl_seconds is not None
            else self._get_ttl_for_frequency(frequency)
        )

        fetch_timestamp = bundle_metadata.get("fetch_timestamp", 0)
        refresh_time = fetch_timestamp + ttl

        return pd.Timestamp(refresh_time, unit="s", tz="UTC")

    def _get_ttl_for_frequency(self, frequency: str) -> int:
        """Get default TTL for frequency.

        Args:
            frequency: Data frequency

        Returns:
            TTL in seconds
        """
        ttl_map = {
            "1d": 86400,  # 24 hours
            "1h": 3600,  # 1 hour
            "5m": 300,  # 5 minutes
            "1m": 300,  # 5 minutes
        }
        return ttl_map.get(frequency, 3600)  # Default 1 hour


class HybridFreshnessPolicy(CacheFreshnessPolicy):
    """Hybrid freshness policy combining TTL with market hours.

    - If market closed: cache is always fresh (no new data arrives)
    - If market open: apply TTL staleness check

    Used for intraday data (hourly/minute) on exchanges with market hours.
    Avoids unnecessary refreshes on weekends/nights.

    Example:
        >>> policy = HybridFreshnessPolicy(ttl_seconds=3600)
        >>> calendar = get_calendar('NYSE')
        >>> # Saturday 10 AM, market closed
        >>> bundle = {'fetch_timestamp': friday_5pm}
        >>> is_fresh = policy.is_fresh(bundle, '1h', calendar)
        >>> # Returns True (market closed, cache fresh)
    """

    def __init__(self, ttl_seconds: int = 3600):
        """Initialize hybrid policy.

        Args:
            ttl_seconds: TTL to use when market is open (default 1 hour)
        """
        self.ttl_seconds = ttl_seconds

    def is_fresh(
        self,
        bundle_metadata: dict[str, Any],
        frequency: str,
        calendar: ExchangeCalendar | None = None,
    ) -> bool:
        """Cache is fresh if market closed OR (market open AND age < TTL).

        Args:
            bundle_metadata: Cache metadata
            frequency: Data frequency
            calendar: Exchange calendar for market hours

        Returns:
            True if fresh, False if stale
        """
        if calendar is None:
            # Fallback to simple TTL
            return TTLFreshnessPolicy(self.ttl_seconds).is_fresh(
                bundle_metadata, frequency, calendar
            )

        current_time = pd.Timestamp.now(tz="UTC")

        # Check if market is open
        try:
            is_open = calendar.is_open_on_minute(current_time)
        except Exception:
            # Fallback to TTL if calendar check fails
            return TTLFreshnessPolicy(self.ttl_seconds).is_fresh(
                bundle_metadata, frequency, calendar
            )

        # If market closed, cache is always fresh
        if not is_open:
            return True

        # Market open: apply TTL check
        fetch_timestamp = bundle_metadata.get("fetch_timestamp", 0)
        current_timestamp = time.time()
        age_seconds = current_timestamp - fetch_timestamp

        return age_seconds < self.ttl_seconds

    def get_next_refresh_time(
        self,
        bundle_metadata: dict[str, Any],
        frequency: str,
        calendar: ExchangeCalendar | None = None,
    ) -> pd.Timestamp:
        """Next refresh is next market open + TTL.

        Args:
            bundle_metadata: Cache metadata
            frequency: Data frequency
            calendar: Exchange calendar

        Returns:
            Timestamp of next refresh
        """
        if calendar is None:
            # Fallback to TTL policy
            return TTLFreshnessPolicy(self.ttl_seconds).get_next_refresh_time(
                bundle_metadata, frequency, calendar
            )

        current_time = pd.Timestamp.now(tz="UTC")

        try:
            # If market closed, refresh at next open
            if not calendar.is_open_on_minute(current_time):
                return calendar.next_open(current_time)

            # Market open: refresh after TTL
            fetch_timestamp = bundle_metadata.get("fetch_timestamp", 0)
            refresh_time = fetch_timestamp + self.ttl_seconds
            return pd.Timestamp(refresh_time, unit="s", tz="UTC")
        except Exception:
            # Fallback
            return current_time + pd.Timedelta(seconds=self.ttl_seconds)


class NeverStaleFreshnessPolicy(CacheFreshnessPolicy):
    """Cache is never stale (always fresh).

    Used for static data sources (CSV files, historical bundles) that don't
    change after initial ingestion.

    Example:
        >>> policy = NeverStaleFreshnessPolicy()
        >>> bundle = {'fetch_timestamp': very_old_timestamp}
        >>> is_fresh = policy.is_fresh(bundle, '1d')
        >>> # Returns True (always fresh)
    """

    def is_fresh(
        self,
        bundle_metadata: dict[str, Any],
        frequency: str,
        calendar: ExchangeCalendar | None = None,
    ) -> bool:
        """Always returns True (never stale).

        Args:
            bundle_metadata: Cache metadata (ignored)
            frequency: Data frequency (ignored)
            calendar: Exchange calendar (ignored)

        Returns:
            Always True
        """
        return True

    def get_next_refresh_time(
        self,
        bundle_metadata: dict[str, Any],
        frequency: str,
        calendar: ExchangeCalendar | None = None,
    ) -> pd.Timestamp:
        """Returns far future timestamp (never refresh).

        Args:
            bundle_metadata: Cache metadata (ignored)
            frequency: Data frequency (ignored)
            calendar: Exchange calendar (ignored)

        Returns:
            Timestamp far in the future
        """
        return pd.Timestamp("2099-12-31", tz="UTC")


class AlwaysStaleFreshnessPolicy(CacheFreshnessPolicy):
    """Cache is always stale (never fresh).

    Used for live trading mode where caching should be disabled and every
    request should fetch fresh data from the adapter.

    Example:
        >>> policy = AlwaysStaleFreshnessPolicy()
        >>> bundle = {'fetch_timestamp': just_now}
        >>> is_fresh = policy.is_fresh(bundle, '1m')
        >>> # Returns False (always stale → forces re-fetch)
    """

    def is_fresh(
        self,
        bundle_metadata: dict[str, Any],
        frequency: str,
        calendar: ExchangeCalendar | None = None,
    ) -> bool:
        """Always returns False (always stale).

        Args:
            bundle_metadata: Cache metadata (ignored)
            frequency: Data frequency (ignored)
            calendar: Exchange calendar (ignored)

        Returns:
            Always False
        """
        return False

    def get_next_refresh_time(
        self,
        bundle_metadata: dict[str, Any],
        frequency: str,
        calendar: ExchangeCalendar | None = None,
    ) -> pd.Timestamp:
        """Returns current time (immediate refresh).

        Args:
            bundle_metadata: Cache metadata (ignored)
            frequency: Data frequency (ignored)
            calendar: Exchange calendar (ignored)

        Returns:
            Current timestamp
        """
        return pd.Timestamp.now(tz="UTC")
