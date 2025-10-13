"""Integration tests for API provider adapters.

These tests make real API calls to data providers and require valid API keys.
Tests are skipped if API keys are not configured.

Setup:
1. Copy .env.example to .env and add your API keys:
   - POLYGON_API_KEY
   - ALPACA_API_KEY and ALPACA_API_SECRET
   - ALPHAVANTAGE_API_KEY

2. Run integration tests:
   pytest tests/integration/data/test_api_providers.py -m api_integration -v

Note: These tests will count against your API rate limits.
"""

import os

import pandas as pd
import pytest

from rustybt.data.adapters import AlpacaAdapter, AlphaVantageAdapter, PolygonAdapter

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def skip_if_no_polygon_key():
    """Skip test if POLYGON_API_KEY not configured."""
    if "POLYGON_API_KEY" not in os.environ:
        pytest.skip("POLYGON_API_KEY not configured in environment")


@pytest.fixture
def skip_if_no_alpaca_keys():
    """Skip test if ALPACA_API_KEY not configured."""
    if "ALPACA_API_KEY" not in os.environ or "ALPACA_API_SECRET" not in os.environ:
        pytest.skip("ALPACA_API_KEY or ALPACA_API_SECRET not configured in environment")


@pytest.fixture
def skip_if_no_alphavantage_key():
    """Skip test if ALPHAVANTAGE_API_KEY not configured."""
    if "ALPHAVANTAGE_API_KEY" not in os.environ:
        pytest.skip("ALPHAVANTAGE_API_KEY not configured in environment")


# ============================================================================
# Polygon Integration Tests
# ============================================================================


@pytest.mark.api_integration
@pytest.mark.asyncio
async def test_polygon_stocks_real_data(skip_if_no_polygon_key):
    """Polygon adapter fetches real stock data."""
    adapter = PolygonAdapter(tier="free", asset_type="stocks")

    # Fetch daily data for AAPL (last 5 days)
    end_date = pd.Timestamp.now(tz="UTC")
    start_date = end_date - pd.Timedelta(days=5)

    df = await adapter.fetch_ohlcv("AAPL", start_date, end_date, "1d")

    # Verify we got data
    assert len(df) > 0
    assert "timestamp" in df.columns
    assert "symbol" in df.columns
    assert df["symbol"][0] == "AAPL"

    # Cleanup
    await adapter.close()


@pytest.mark.api_integration
@pytest.mark.asyncio
async def test_polygon_crypto_real_data(skip_if_no_polygon_key):
    """Polygon adapter fetches real crypto data."""
    adapter = PolygonAdapter(tier="free", asset_type="crypto")

    # Fetch hourly data for BTC (last 2 days)
    end_date = pd.Timestamp.now(tz="UTC")
    start_date = end_date - pd.Timedelta(days=2)

    df = await adapter.fetch_ohlcv("BTCUSD", start_date, end_date, "1h")

    # Verify we got data
    assert len(df) > 0
    assert df["symbol"][0] == "BTCUSD"

    # Cleanup
    await adapter.close()


@pytest.mark.api_integration
@pytest.mark.asyncio
async def test_polygon_rate_limiting(skip_if_no_polygon_key):
    """Polygon rate limiter enforces request limits."""
    adapter = PolygonAdapter(tier="free", asset_type="stocks")  # 5 req/min

    end_date = pd.Timestamp.now(tz="UTC")
    start_date = end_date - pd.Timedelta(days=1)

    # Make 5 requests (at rate limit for free tier)
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]

    for symbol in symbols:
        await adapter.fetch_ohlcv(symbol, start_date, end_date, "1d")

    # Verify rate limiter tracked requests
    assert adapter.api_rate_limiter.minute_requests

    # Cleanup
    await adapter.close()


# ============================================================================
# Alpaca Integration Tests
# ============================================================================


@pytest.mark.api_integration
@pytest.mark.asyncio
async def test_alpaca_stocks_real_data(skip_if_no_alpaca_keys):
    """Alpaca adapter fetches real stock data."""
    adapter = AlpacaAdapter(is_paper=True)

    # Fetch daily data for AAPL (last 5 days)
    end_date = pd.Timestamp.now(tz="UTC")
    start_date = end_date - pd.Timedelta(days=5)

    df = await adapter.fetch_ohlcv("AAPL", start_date, end_date, "1d")

    # Verify we got data
    assert len(df) > 0
    assert "timestamp" in df.columns
    assert df["symbol"][0] == "AAPL"

    # Cleanup
    await adapter.close()


@pytest.mark.api_integration
@pytest.mark.asyncio
async def test_alpaca_intraday_data(skip_if_no_alpaca_keys):
    """Alpaca adapter fetches intraday data."""
    adapter = AlpacaAdapter(is_paper=True)

    # Fetch 1-hour data for recent trading day
    end_date = pd.Timestamp.now(tz="UTC")
    start_date = end_date - pd.Timedelta(hours=24)

    df = await adapter.fetch_ohlcv("MSFT", start_date, end_date, "1h")

    # Verify we got data
    assert len(df) > 0
    assert df["symbol"][0] == "MSFT"

    # Cleanup
    await adapter.close()


# ============================================================================
# Alpha Vantage Integration Tests
# ============================================================================


@pytest.mark.api_integration
@pytest.mark.asyncio
async def test_alphavantage_stocks_real_data(skip_if_no_alphavantage_key):
    """Alpha Vantage adapter fetches real stock data."""
    adapter = AlphaVantageAdapter(tier="free", asset_type="stocks")

    # Fetch daily data for AAPL (last 30 days)
    end_date = pd.Timestamp.now(tz="UTC")
    start_date = end_date - pd.Timedelta(days=30)

    df = await adapter.fetch_ohlcv("AAPL", start_date, end_date, "1d")

    # Verify we got data
    assert len(df) > 0
    assert "timestamp" in df.columns
    assert df["symbol"][0] == "AAPL"

    # Cleanup
    await adapter.close()


@pytest.mark.api_integration
@pytest.mark.asyncio
async def test_alphavantage_forex_real_data(skip_if_no_alphavantage_key):
    """Alpha Vantage adapter fetches real forex data."""
    adapter = AlphaVantageAdapter(tier="free", asset_type="forex")

    # Fetch daily data for EUR/USD (last 30 days)
    end_date = pd.Timestamp.now(tz="UTC")
    start_date = end_date - pd.Timedelta(days=30)

    df = await adapter.fetch_ohlcv("EUR/USD", start_date, end_date, "1d")

    # Verify we got data
    assert len(df) > 0
    assert df["symbol"][0] == "EUR/USD"

    # Cleanup
    await adapter.close()


@pytest.mark.api_integration
@pytest.mark.asyncio
async def test_alphavantage_rate_limiting(skip_if_no_alphavantage_key):
    """Alpha Vantage rate limiter enforces request limits."""
    adapter = AlphaVantageAdapter(tier="free", asset_type="stocks")  # 5 req/min

    end_date = pd.Timestamp.now(tz="UTC")
    start_date = end_date - pd.Timedelta(days=30)

    # Make 3 requests (well under rate limit)
    symbols = ["AAPL", "MSFT", "GOOGL"]

    for symbol in symbols:
        await adapter.fetch_ohlcv(symbol, start_date, end_date, "1d")

    # Verify rate limiter tracked requests
    assert len(adapter.api_rate_limiter.minute_requests) == 3

    # Cleanup
    await adapter.close()
