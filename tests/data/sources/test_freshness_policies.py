"""Unit tests for cache freshness policies."""

import time

import pandas as pd
import pytest
from exchange_calendars import get_calendar
from freezegun import freeze_time

from rustybt.data.sources.freshness import (
    AlwaysStaleFreshnessPolicy,
    HybridFreshnessPolicy,
    MarketCloseFreshnessPolicy,
    NeverStaleFreshnessPolicy,
    TTLFreshnessPolicy,
)


class TestTTLFreshnessPolicy:
    """Tests for TTL freshness policy."""

    def test_fresh_within_ttl(self):
        """Cache is fresh within TTL."""
        policy = TTLFreshnessPolicy(ttl_seconds=3600)  # 1 hour

        # Fetched 30 minutes ago
        fetch_timestamp = int(time.time()) - 1800
        bundle = {"fetch_timestamp": fetch_timestamp}

        assert policy.is_fresh(bundle, "1h") is True

    def test_stale_after_ttl(self):
        """Cache is stale after TTL expires."""
        policy = TTLFreshnessPolicy(ttl_seconds=3600)  # 1 hour

        # Fetched 2 hours ago
        fetch_timestamp = int(time.time()) - 7200
        bundle = {"fetch_timestamp": fetch_timestamp}

        assert policy.is_fresh(bundle, "1h") is False

    def test_auto_ttl_selection(self):
        """TTL auto-selected based on frequency."""
        policy = TTLFreshnessPolicy()  # No TTL specified

        # Daily: 24 hours
        fetch_timestamp = int(time.time()) - 3600  # 1 hour ago
        bundle = {"fetch_timestamp": fetch_timestamp}
        assert policy.is_fresh(bundle, "1d") is True

        # Hourly: 1 hour
        fetch_timestamp = int(time.time()) - 1800  # 30 min ago
        bundle = {"fetch_timestamp": fetch_timestamp}
        assert policy.is_fresh(bundle, "1h") is True

        # Hourly stale after 1+ hours
        fetch_timestamp = int(time.time()) - 3700  # 1h 2min ago
        bundle = {"fetch_timestamp": fetch_timestamp}
        assert policy.is_fresh(bundle, "1h") is False

    def test_next_refresh_time(self):
        """Next refresh time is fetch + TTL."""
        policy = TTLFreshnessPolicy(ttl_seconds=3600)

        fetch_timestamp = int(time.time())
        bundle = {"fetch_timestamp": fetch_timestamp}

        refresh_time = policy.get_next_refresh_time(bundle, "1h")
        expected_time = pd.Timestamp(fetch_timestamp + 3600, unit="s", tz="UTC")

        assert refresh_time == expected_time


class TestMarketCloseFreshnessPolicy:
    """Tests for market close freshness policy."""

    @pytest.mark.parametrize(
        "fetch_time,check_time,expected",
        [
            # Friday before close, check Friday before close
            ("2023-10-06 15:00:00", "2023-10-06 15:30:00", True),
            # Friday after close, check Friday after close
            ("2023-10-06 16:01:00", "2023-10-06 17:00:00", True),
            # Friday after close, check Saturday
            ("2023-10-06 16:01:00", "2023-10-07 10:00:00", True),
            # Friday after close, check Monday before close
            ("2023-10-06 16:01:00", "2023-10-09 09:00:00", True),
            # Friday before close, check Monday after close
            ("2023-10-06 15:00:00", "2023-10-09 16:01:00", False),
        ],
    )
    def test_market_close_freshness(self, fetch_time, check_time, expected):
        """Test market close freshness for various scenarios."""
        policy = MarketCloseFreshnessPolicy()
        calendar = get_calendar("NYSE")

        fetch_timestamp = pd.Timestamp(fetch_time, tz="America/New_York").timestamp()
        bundle = {"fetch_timestamp": int(fetch_timestamp)}

        with freeze_time(check_time):
            is_fresh = policy.is_fresh(bundle, "1d", calendar)
            assert is_fresh == expected

    def test_weekend_freshness(self):
        """Test cache stays fresh over weekend."""
        policy = MarketCloseFreshnessPolicy()
        calendar = get_calendar("NYSE")

        # Fetched Friday after close
        fetch_time = pd.Timestamp("2023-10-06 17:00:00", tz="America/New_York")
        bundle = {"fetch_timestamp": int(fetch_time.timestamp())}

        # Check Saturday - should be fresh
        with freeze_time("2023-10-07 10:00:00"):
            assert policy.is_fresh(bundle, "1d", calendar) is True

        # Check Sunday - should be fresh
        with freeze_time("2023-10-08 10:00:00"):
            assert policy.is_fresh(bundle, "1d", calendar) is True

    def test_fallback_without_calendar(self):
        """Test fallback to TTL when calendar unavailable."""
        policy = MarketCloseFreshnessPolicy()

        # Fetched 30 minutes ago (within 1 hour fallback TTL)
        fetch_timestamp = int(time.time()) - 1800
        bundle = {"fetch_timestamp": fetch_timestamp}

        assert policy.is_fresh(bundle, "1d", calendar=None) is True

        # Fetched 2 hours ago (beyond fallback TTL)
        fetch_timestamp = int(time.time()) - 7200
        bundle = {"fetch_timestamp": fetch_timestamp}

        assert policy.is_fresh(bundle, "1d", calendar=None) is False


class TestHybridFreshnessPolicy:
    """Tests for hybrid freshness policy (TTL + market hours)."""

    def test_fresh_when_market_closed(self):
        """Cache always fresh when market is closed."""
        policy = HybridFreshnessPolicy(ttl_seconds=3600)
        calendar = get_calendar("NYSE")

        # Fetched hours ago, but market is closed (Saturday)
        fetch_timestamp = pd.Timestamp("2023-10-06 17:00:00", tz="America/New_York").timestamp()
        bundle = {"fetch_timestamp": int(fetch_timestamp)}

        with freeze_time("2023-10-07 10:00:00"):  # Saturday
            assert policy.is_fresh(bundle, "1h", calendar) is True

    def test_ttl_when_market_open(self):
        """Apply TTL when market is open."""
        policy = HybridFreshnessPolicy(ttl_seconds=3600)
        calendar = get_calendar("NYSE")

        # Fetched 30 minutes ago, market open
        fetch_time = pd.Timestamp("2023-10-06 14:00:00", tz="America/New_York")
        bundle = {"fetch_timestamp": int(fetch_time.timestamp())}

        with freeze_time("2023-10-06 14:30:00"):  # 30 min later, market open
            assert policy.is_fresh(bundle, "1h", calendar) is True

        # Fetched 2 hours ago, market open
        fetch_time = pd.Timestamp("2023-10-06 12:00:00", tz="America/New_York")
        bundle = {"fetch_timestamp": int(fetch_time.timestamp())}

        with freeze_time("2023-10-06 14:00:00"):  # 2 hours later, market open
            assert policy.is_fresh(bundle, "1h", calendar) is False

    def test_fallback_without_calendar(self):
        """Test fallback to TTL without calendar."""
        policy = HybridFreshnessPolicy(ttl_seconds=3600)

        # Within TTL
        fetch_timestamp = int(time.time()) - 1800  # 30 min ago
        bundle = {"fetch_timestamp": fetch_timestamp}
        assert policy.is_fresh(bundle, "1h", calendar=None) is True

        # Beyond TTL
        fetch_timestamp = int(time.time()) - 7200  # 2 hours ago
        bundle = {"fetch_timestamp": fetch_timestamp}
        assert policy.is_fresh(bundle, "1h", calendar=None) is False


class TestNeverStaleFreshnessPolicy:
    """Tests for never stale policy (static data)."""

    def test_always_fresh(self):
        """Cache is always fresh."""
        policy = NeverStaleFreshnessPolicy()

        # Very old fetch
        fetch_timestamp = int(time.time()) - 86400 * 365  # 1 year ago
        bundle = {"fetch_timestamp": fetch_timestamp}

        assert policy.is_fresh(bundle, "1d") is True

    def test_next_refresh_far_future(self):
        """Next refresh is far in the future."""
        policy = NeverStaleFreshnessPolicy()

        bundle = {"fetch_timestamp": int(time.time())}
        refresh_time = policy.get_next_refresh_time(bundle, "1d")

        assert refresh_time.year == 2099


class TestAlwaysStaleFreshnessPolicy:
    """Tests for always stale policy (live trading)."""

    def test_always_stale(self):
        """Cache is always stale."""
        policy = AlwaysStaleFreshnessPolicy()

        # Just fetched
        fetch_timestamp = int(time.time())
        bundle = {"fetch_timestamp": fetch_timestamp}

        assert policy.is_fresh(bundle, "1m") is False

    def test_next_refresh_immediate(self):
        """Next refresh is immediate (now)."""
        policy = AlwaysStaleFreshnessPolicy()

        bundle = {"fetch_timestamp": int(time.time())}
        refresh_time = policy.get_next_refresh_time(bundle, "1m")

        # Should be within a few seconds of now
        now = pd.Timestamp.now(tz="UTC")
        time_diff = abs((refresh_time - now).total_seconds())
        assert time_diff < 5  # Within 5 seconds


class TestFreshnessPolicyEdgeCases:
    """Edge case tests for all freshness policies."""

    def test_missing_fetch_timestamp(self):
        """Handle missing fetch_timestamp gracefully."""
        policy = TTLFreshnessPolicy(ttl_seconds=3600)

        bundle = {}  # No fetch_timestamp

        # Should default to 0 (epoch) → stale
        assert policy.is_fresh(bundle, "1h") is False

    def test_future_fetch_timestamp(self):
        """Handle future fetch_timestamp."""
        policy = TTLFreshnessPolicy(ttl_seconds=3600)

        # Fetch timestamp in the future
        fetch_timestamp = int(time.time()) + 3600
        bundle = {"fetch_timestamp": fetch_timestamp}

        # Should be fresh (negative age)
        assert policy.is_fresh(bundle, "1h") is True
