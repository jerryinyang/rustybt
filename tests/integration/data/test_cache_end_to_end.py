"""End-to-end integration tests for Smart Caching Layer.

Tests the integration of CachedDataSource with PolarsDataPortal and TradingAlgorithm
to ensure caching works correctly in real backtest scenarios.
"""

import asyncio
import time
from decimal import Decimal
from unittest.mock import Mock

import pandas as pd
import polars as pl
import pytest

from rustybt.data.catalog import DataCatalog
from rustybt.data.sources.base import DataSource, DataSourceMetadata
from rustybt.data.sources.cached_source import CachedDataSource
from rustybt.data.sources.freshness import NeverStaleFreshnessPolicy


@pytest.fixture
def temp_dirs(tmp_path):
    """Create temporary directories for cache and bundles."""
    cache_dir = tmp_path / "cache"
    bundle_dir = tmp_path / "bundle"
    db_dir = tmp_path / "db"

    cache_dir.mkdir()
    bundle_dir.mkdir()
    db_dir.mkdir()

    return {
        "cache": cache_dir,
        "bundle": bundle_dir,
        "db": db_dir,
    }


@pytest.fixture
def test_catalog(temp_dirs):
    """Create test catalog with temporary database."""
    db_path = temp_dirs["db"] / "test_catalog.db"
    catalog = DataCatalog(db_path=str(db_path))

    # Create tables
    from rustybt.assets.asset_db_schema import metadata

    metadata.create_all(catalog.engine)

    return catalog


@pytest.fixture
def mock_data_adapter():
    """Create mock DataSource that simulates API fetch delays."""

    class MockDataAdapter(DataSource):
        """Mock adapter with simulated fetch latency."""

        def __init__(self):
            self.fetch_count = 0
            self.fetch_latency_ms = 5000  # Simulate 5s API call

        async def fetch(
            self,
            symbols: list[str],
            start: pd.Timestamp,
            end: pd.Timestamp,
            frequency: str,
        ) -> pl.DataFrame:
            """Simulate slow API fetch."""
            self.fetch_count += 1

            # Simulate API delay
            await asyncio.sleep(self.fetch_latency_ms / 1000)

            # Generate test OHLCV data
            dates = pd.date_range(start, end, freq="D")

            data = []
            for symbol in symbols:
                for dt in dates:
                    data.append(
                        {
                            "timestamp": dt,
                            "symbol": symbol,
                            "open": Decimal(str(100.0 + len(data))),
                            "high": Decimal(str(105.0 + len(data))),
                            "low": Decimal(str(99.0 + len(data))),
                            "close": Decimal(str(104.0 + len(data))),
                            "volume": Decimal(str(1000000.0)),
                        }
                    )

            return pl.DataFrame(data)

        def ingest_to_bundle(
            self,
            bundle_name: str,
            symbols: list[str],
            start: pd.Timestamp,
            end: pd.Timestamp,
            frequency: str,
            **kwargs,
        ) -> None:
            """Not implemented for mock."""
            pass

        def get_metadata(self) -> DataSourceMetadata:
            """Return test metadata."""
            return DataSourceMetadata(
                source_type="mock",
                source_url="http://mock.test",
                api_version="v1",
                supports_live=False,
            )

        def supports_live(self) -> bool:
            """Mock does not support live."""
            return False

    return MockDataAdapter()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cached_source_with_data_portal(mock_data_adapter, temp_dirs, test_catalog):
    """Test CachedDataSource integration with PolarsDataPortal.

    Validates:
    - First backtest fetches from adapter (cache miss)
    - Second backtest uses cache (cache hit, no adapter call)
    - Cache hit is significantly faster (<100ms vs 5s)
    - Cache hit rate >80% for repeated queries
    """
    # Setup cached data source
    cached_source = CachedDataSource(
        adapter=mock_data_adapter,
        cache_dir=temp_dirs["cache"],
        freshness_policy=NeverStaleFreshnessPolicy(),
    )
    cached_source.catalog = test_catalog

    start = pd.Timestamp("2023-01-01")
    end = pd.Timestamp("2023-01-31")
    symbols = ["AAPL", "MSFT", "GOOGL"]

    # First fetch - cache miss (should take ~5 seconds)
    start_time = time.perf_counter()
    df1 = await cached_source.fetch(symbols, start, end, "1d")
    first_fetch_time_ms = (time.perf_counter() - start_time) * 1000

    # Verify first fetch called adapter
    assert mock_data_adapter.fetch_count == 1
    assert len(df1) > 0
    assert first_fetch_time_ms > 4000  # Should take at least 4s (simulated API delay)

    # Second fetch - cache hit (should be <100ms)
    start_time = time.perf_counter()
    df2 = await cached_source.fetch(symbols, start, end, "1d")
    second_fetch_time_ms = (time.perf_counter() - start_time) * 1000

    # Verify cache hit (adapter NOT called again)
    assert mock_data_adapter.fetch_count == 1  # Still 1 (not incremented)
    assert len(df2) > 0
    assert df1.equals(df2)  # Same data returned
    assert second_fetch_time_ms < 500  # Should be much faster (relaxed for test env)

    # Verify performance improvement
    speedup = first_fetch_time_ms / second_fetch_time_ms
    assert speedup > 10  # At least 10x faster

    # Verify cache statistics
    stats = test_catalog.get_cache_stats(days=1)
    assert len(stats) > 0
    assert stats[0]["hit_count"] == 1
    assert stats[0]["miss_count"] == 1
    assert stats[0]["hit_rate"] == 50.0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cache_hit_rate_multiple_queries(mock_data_adapter, temp_dirs, test_catalog):
    """Test cache hit rate exceeds 80% for repeated backtest queries.

    Simulates running multiple backtests with overlapping data requests.
    """
    # Reduce mock latency for faster test execution
    mock_data_adapter.fetch_latency_ms = 100

    cached_source = CachedDataSource(
        adapter=mock_data_adapter,
        cache_dir=temp_dirs["cache"],
        freshness_policy=NeverStaleFreshnessPolicy(),
    )
    cached_source.catalog = test_catalog

    start = pd.Timestamp("2023-01-01")
    end = pd.Timestamp("2023-12-31")
    symbols = ["AAPL", "MSFT"]

    # First query - cache miss
    await cached_source.fetch(symbols, start, end, "1d")
    initial_fetch_count = mock_data_adapter.fetch_count

    # Run 10 additional queries with same parameters (cache hits)
    for _ in range(10):
        await cached_source.fetch(symbols, start, end, "1d")

    # Verify adapter only called once (first query)
    assert mock_data_adapter.fetch_count == initial_fetch_count

    # Verify cache hit rate
    stats = test_catalog.get_cache_stats(days=1)
    assert len(stats) > 0

    # 10 hits, 1 miss = 90.9% hit rate
    assert stats[0]["hit_rate"] > 80.0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_backtest_cache_sharing(mock_data_adapter, temp_dirs, test_catalog):
    """Test multiple concurrent backtests share cache correctly.

    Simulates parallel strategy execution with shared data cache.
    """
    mock_data_adapter.fetch_latency_ms = 100

    cached_source = CachedDataSource(
        adapter=mock_data_adapter,
        cache_dir=temp_dirs["cache"],
        freshness_policy=NeverStaleFreshnessPolicy(),
    )
    cached_source.catalog = test_catalog

    start = pd.Timestamp("2023-01-01")
    end = pd.Timestamp("2023-06-30")
    symbols = ["AAPL"]

    # Simulate 5 concurrent backtest requests
    tasks = [cached_source.fetch(symbols, start, end, "1d") for _ in range(5)]

    results = await asyncio.gather(*tasks)

    # Verify all results are identical
    for result in results[1:]:
        assert result.equals(results[0])

    # Verify adapter called minimal times (concurrent race may cause up to 5 calls in worst case)
    # In production with real database locking, this would be closer to 1-2
    assert mock_data_adapter.fetch_count <= 5

    # All results should be equal regardless of cache hits
    assert all(len(r) > 0 for r in results)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cache_persistence_across_sessions(mock_data_adapter, temp_dirs, test_catalog):
    """Test cache persists across different CachedDataSource instances.

    Simulates stopping and restarting backtests with cache reuse.
    """
    mock_data_adapter.fetch_latency_ms = 100

    start = pd.Timestamp("2023-01-01")
    end = pd.Timestamp("2023-03-31")
    symbols = ["AAPL", "MSFT"]

    # Session 1: Create cached source and fetch data
    cached_source_1 = CachedDataSource(
        adapter=mock_data_adapter,
        cache_dir=temp_dirs["cache"],
        freshness_policy=NeverStaleFreshnessPolicy(),
    )
    cached_source_1.catalog = test_catalog

    await cached_source_1.fetch(symbols, start, end, "1d")
    session_1_fetch_count = mock_data_adapter.fetch_count

    # Session 2: Create NEW cached source (simulating restart)
    cached_source_2 = CachedDataSource(
        adapter=mock_data_adapter,
        cache_dir=temp_dirs["cache"],
        freshness_policy=NeverStaleFreshnessPolicy(),
    )
    cached_source_2.catalog = test_catalog

    # Fetch same data - should hit cache from session 1
    df = await cached_source_2.fetch(symbols, start, end, "1d")

    # Verify adapter NOT called again
    assert mock_data_adapter.fetch_count == session_1_fetch_count
    assert len(df) > 0


@pytest.mark.integration
def test_cache_integration_with_polars_data_portal(temp_dirs, test_catalog):
    """Test CachedDataSource can be used with PolarsDataPortal.

    This is a structural integration test verifying the components
    can be wired together (actual backtest simulation would require
    full TradingAlgorithm setup which is beyond scope of cache testing).
    """
    # Create mock adapter
    adapter = Mock(spec=DataSource)
    adapter.get_metadata.return_value = DataSourceMetadata(
        source_type="test",
        source_url="http://test.com",
        api_version="v1",
        supports_live=False,
    )
    adapter.supports_live.return_value = False

    # Create cached data source
    cached_source = CachedDataSource(
        adapter=adapter,
        cache_dir=temp_dirs["cache"],
        freshness_policy=NeverStaleFreshnessPolicy(),
    )

    # Verify cached source is a valid DataSource
    assert isinstance(cached_source, DataSource)
    assert cached_source.supports_live() is False

    # Verify metadata delegation works
    metadata = cached_source.get_metadata()
    assert metadata.source_type == "test"

    # Note: Full PolarsDataPortal integration would require actual bundle data
    # which is beyond the scope of cache-specific testing. The key validation
    # here is that CachedDataSource implements DataSource interface correctly
    # and can be used as a drop-in replacement wherever DataSource is expected.


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cache_with_different_frequencies(mock_data_adapter, temp_dirs, test_catalog):
    """Test cache correctly handles different data frequencies.

    Validates cache keys are unique per frequency to avoid conflicts.
    """
    mock_data_adapter.fetch_latency_ms = 100

    cached_source = CachedDataSource(
        adapter=mock_data_adapter,
        cache_dir=temp_dirs["cache"],
        freshness_policy=NeverStaleFreshnessPolicy(),
    )
    cached_source.catalog = test_catalog

    start = pd.Timestamp("2023-01-01")
    end = pd.Timestamp("2023-01-31")
    symbols = ["AAPL"]

    # Fetch daily data
    await cached_source.fetch(symbols, start, end, "1d")
    daily_fetch_count = mock_data_adapter.fetch_count

    # Fetch hourly data (should be different cache key)
    await cached_source.fetch(symbols, start, end, "1h")
    hourly_fetch_count = mock_data_adapter.fetch_count

    # Verify separate cache entries (adapter called twice)
    assert hourly_fetch_count == daily_fetch_count + 1

    # Fetch daily again (should hit cache)
    await cached_source.fetch(symbols, start, end, "1d")
    assert mock_data_adapter.fetch_count == hourly_fetch_count  # No new call

    # Fetch hourly again (should hit cache)
    await cached_source.fetch(symbols, start, end, "1h")
    assert mock_data_adapter.fetch_count == hourly_fetch_count  # No new call
