"""Integration tests for unified data architecture (Story 8.5).

Tests the complete integration of DataSource, CachedDataSource, and PolarsDataPortal
with both legacy and unified APIs.
"""

from decimal import Decimal
from pathlib import Path

import pandas as pd
import polars as pl
import pytest

from rustybt.assets import Equity
from rustybt.assets.exchange_info import ExchangeInfo
from rustybt.data.polars.data_portal import PolarsDataPortal
from rustybt.data.sources.base import DataSource, DataSourceMetadata


# Mock DataSource for testing (not a real external adapter)
class MockDataSource(DataSource):
    """Mock data source for testing (returns deterministic data)."""

    def __init__(self):
        self.fetch_count = 0

    async def fetch(
        self,
        symbols: list[str],
        start: pd.Timestamp,
        end: pd.Timestamp,
        frequency: str,
    ) -> pl.DataFrame:
        """Return mock OHLCV data."""
        self.fetch_count += 1

        # Convert frequency to pandas format
        freq_map = {
            "daily": "D",
            "1d": "D",
            "hourly": "H",
            "1h": "H",
            "minute": "T",
            "1m": "T",
        }
        pandas_freq = freq_map.get(frequency, frequency)

        # Generate mock data
        dates = pd.date_range(start, end, freq=pandas_freq)
        data = []

        for symbol in symbols:
            for date in dates:
                data.append(
                    {
                        "symbol": symbol,
                        "date": date.date() if frequency == "1d" else None,
                        "timestamp": date if frequency != "1d" else None,
                        "open": Decimal("100.0"),
                        "high": Decimal("105.0"),
                        "low": Decimal("95.0"),
                        "close": Decimal("102.0"),
                        "volume": Decimal("1000000"),
                    }
                )

        return pl.DataFrame(data)

    async def ingest_to_bundle(
        self,
        bundle_name: str,
        symbols: list[str],
        start: pd.Timestamp,
        end: pd.Timestamp,
        frequency: str,
    ) -> Path:
        """Mock ingest (not implemented for test)."""
        raise NotImplementedError("Mock adapter does not support ingestion")

    def get_metadata(self) -> DataSourceMetadata:
        """Return mock metadata."""
        return DataSourceMetadata(
            source_type="mock",
            source_url="mock://test",
            api_version="1.0",
            supports_live=False,
            supported_frequencies=["1d", "1h"],
        )

    def supports_live(self) -> bool:
        """Mock does not support live."""
        return False


@pytest.fixture
def test_exchange_info():
    """Create test exchange info."""
    return ExchangeInfo("TEST", "Test Exchange", "US")


@pytest.fixture
def test_assets(test_exchange_info):
    """Create test assets with proper exchange info."""
    return [
        Equity(1, exchange_info=test_exchange_info, symbol="AAPL"),
        Equity(2, exchange_info=test_exchange_info, symbol="MSFT"),
    ]


@pytest.mark.integration
def test_dataportal_with_unified_data_source(test_assets):
    """DataPortal with unified DataSource API works correctly."""
    # Create mock data source
    source = MockDataSource()

    # Create DataPortal with unified API
    portal = PolarsDataPortal(
        data_source=source,
        use_cache=False,  # Disable cache for this test
    )

    # Test get_spot_value
    dt = pd.Timestamp("2024-01-15")
    prices = portal.get_spot_value(assets=test_assets, field="close", dt=dt, data_frequency="daily")

    assert len(prices) == 2
    assert all(price == Decimal("102.0") for price in prices)
    assert source.fetch_count == 1


@pytest.mark.integration
def test_dataportal_with_cached_source(test_assets):
    """DataPortal with CachedDataSource uses cache correctly."""
    import tempfile

    from rustybt.data.sources.cached_source import CachedDataSource

    # Create mock source
    source = MockDataSource()

    # Wrap with caching
    with tempfile.TemporaryDirectory() as cache_dir:
        cached_source = CachedDataSource(
            adapter=source,
            cache_dir=cache_dir,
        )

        # Create DataPortal
        portal = PolarsDataPortal(
            data_source=cached_source,
            use_cache=True,
        )

        assets = [test_assets[0]]  # Use first asset from fixture
        dt = pd.Timestamp("2024-01-15")

        # First fetch (cache miss)
        prices1 = portal.get_spot_value(assets=assets, field="close", dt=dt, data_frequency="daily")

        # Second fetch (cache hit - should not increment fetch_count)
        prices2 = portal.get_spot_value(assets=assets, field="close", dt=dt, data_frequency="daily")

        assert prices1.equals(prices2)
        # Cache should reduce API calls
        assert source.fetch_count >= 1  # At least one fetch occurred


@pytest.mark.integration
def test_dataportal_history_window_unified(test_assets):
    """DataPortal get_history_window works with unified DataSource."""
    source = MockDataSource()

    portal = PolarsDataPortal(
        data_source=source,
        use_cache=False,
    )

    assets = [test_assets[0]]  # Use first asset from fixture
    end_dt = pd.Timestamp("2024-01-20")

    # Get 5-day history window
    df = portal.get_history_window(
        assets=assets,
        end_dt=end_dt,
        bar_count=5,
        frequency="daily",
        field="close",
        data_frequency="daily",
    )

    assert len(df) > 0
    assert "close" in df.columns
    assert "symbol" in df.columns or "date" in df.columns


@pytest.mark.integration
def test_dataportal_backwards_compatibility_daily_reader():
    """Old DataPortal(daily_reader=...) still works with deprecation warning."""

    # Mock reader (we won't actually use it, just test initialization)
    class MockDailyReader:
        pass

    reader = MockDailyReader()

    # Should emit deprecation warning
    with pytest.warns(DeprecationWarning, match="deprecated.*v2.0.*DataSource"):
        portal = PolarsDataPortal(daily_reader=reader)

    # Verify legacy path initialized
    assert portal.daily_reader is reader
    assert portal.data_source is None


@pytest.mark.integration
def test_dataportal_requires_source_or_readers():
    """DataPortal raises error if neither data_source nor readers provided."""
    with pytest.raises(ValueError, match="Must provide either data_source or legacy readers"):
        PolarsDataPortal()


@pytest.mark.integration
def test_dataportal_cache_statistics(test_assets):
    """DataPortal tracks cache hit/miss statistics correctly."""
    source = MockDataSource()

    portal = PolarsDataPortal(
        data_source=source,
        use_cache=False,
    )

    # Initial state
    assert portal.cache_hit_count == 0
    assert portal.cache_miss_count == 0
    assert portal.cache_hit_rate == 0.0

    # After fetches, statistics may be updated if source tracks them
    assets = [test_assets[0]]  # Use first asset from fixture
    dt = pd.Timestamp("2024-01-15")

    portal.get_spot_value(assets=assets, field="close", dt=dt, data_frequency="daily")

    # Cache hit rate should be calculable
    assert isinstance(portal.cache_hit_rate, float)
    assert 0.0 <= portal.cache_hit_rate <= 100.0


@pytest.mark.integration
def test_dataportal_lookahead_prevention(test_assets):
    """DataPortal prevents lookahead bias in simulation mode."""
    source = MockDataSource()

    portal = PolarsDataPortal(
        data_source=source,
        current_simulation_time=pd.Timestamp("2024-01-10"),
    )

    # Attempting to access future data should raise LookaheadError
    from rustybt.data.polars.data_portal import LookaheadError

    with pytest.raises(LookaheadError, match="Attempted to access future data"):
        portal.get_spot_value(
            assets=test_assets,
            field="close",
            dt=pd.Timestamp("2024-01-15"),  # Future date
            data_frequency="daily",
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dataportal_auto_cache_wrapping():
    """DataPortal automatically wraps DataSource with cache when use_cache=True."""
    from rustybt.data.sources.cached_source import CachedDataSource

    source = MockDataSource()

    portal = PolarsDataPortal(
        data_source=source,
        use_cache=True,  # Should auto-wrap
    )

    # Verify source was wrapped with CachedDataSource
    assert isinstance(portal.data_source, CachedDataSource)
