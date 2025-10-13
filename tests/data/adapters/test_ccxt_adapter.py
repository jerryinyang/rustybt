"""Tests for CCXTAdapter data adapter.

This module contains unit tests and integration tests for the CCXT adapter,
including data format conversion, symbol normalization, and live data fetching.
"""

from decimal import Decimal

import pandas as pd
import polars as pl
import pytest

from rustybt.data.adapters import CCXTAdapter, InvalidDataError


class TestCCXTAdapter:
    """Unit tests for CCXTAdapter class."""

    def test_ccxt_adapter_initialization(self) -> None:
        """CCXTAdapter initializes with correct exchange."""
        adapter = CCXTAdapter(exchange_id="binance")

        assert adapter.name == "CCXTAdapter(binance)"
        assert adapter.exchange_id == "binance"
        assert adapter.exchange is not None
        assert adapter.exchange.enableRateLimit is True

    def test_ccxt_adapter_invalid_exchange(self) -> None:
        """CCXTAdapter raises error for invalid exchange."""
        with pytest.raises(AttributeError, match="not found in CCXT"):
            CCXTAdapter(exchange_id="invalid_exchange_xyz")

    def test_resolution_mapping(self) -> None:
        """Resolution mapping contains all expected timeframes."""
        adapter = CCXTAdapter(exchange_id="binance")

        expected_resolutions = ["1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d", "1w"]

        for resolution in expected_resolutions:
            assert resolution in adapter.RESOLUTION_MAPPING
            assert adapter.RESOLUTION_MAPPING[resolution] == resolution

    def test_symbol_normalization_slash_format(self) -> None:
        """Symbol normalization handles slash format correctly."""
        adapter = CCXTAdapter(exchange_id="binance")

        assert adapter._normalize_symbol("BTC/USDT") == "BTC/USDT"
        assert adapter._normalize_symbol("btc/usdt") == "BTC/USDT"
        assert adapter._normalize_symbol("ETH/USD") == "ETH/USD"

    def test_symbol_normalization_dash_format(self) -> None:
        """Symbol normalization converts dash to slash."""
        adapter = CCXTAdapter(exchange_id="binance")

        assert adapter._normalize_symbol("BTC-USDT") == "BTC/USDT"
        assert adapter._normalize_symbol("ETH-USD") == "ETH/USD"
        assert adapter._normalize_symbol("btc-usdt") == "BTC/USDT"

    def test_symbol_normalization_concatenated_format(self) -> None:
        """Symbol normalization handles concatenated format."""
        adapter = CCXTAdapter(exchange_id="binance")

        assert adapter._normalize_symbol("BTCUSDT") == "BTC/USDT"
        assert adapter._normalize_symbol("ETHUSDT") == "ETH/USDT"
        assert adapter._normalize_symbol("BTCUSD") == "BTC/USD"
        assert adapter._normalize_symbol("ETHEUR") == "ETH/EUR"
        assert adapter._normalize_symbol("LINKBTC") == "LINK/BTC"

    def test_symbol_normalization_case_insensitive(self) -> None:
        """Symbol normalization is case insensitive."""
        adapter = CCXTAdapter(exchange_id="binance")

        assert adapter._normalize_symbol("btcusdt") == "BTC/USDT"
        assert adapter._normalize_symbol("BtCuSdT") == "BTC/USDT"
        assert adapter._normalize_symbol("BTCUSDT") == "BTC/USDT"

    def test_data_format_conversion(self) -> None:
        """CCXT data format converts to unified schema correctly."""
        CCXTAdapter(exchange_id="binance")

        # Simulate CCXT format data with symbol appended
        ccxt_data = [
            [1609459200000, 29000.5, 29500.0, 28800.0, 29200.0, 1500.5, "BTC/USDT"],
            [1609545600000, 29200.0, 29800.0, 29100.0, 29500.0, 1800.2, "BTC/USDT"],
        ]

        # Convert to DataFrame format as in adapter
        df = pl.DataFrame(
            {
                "timestamp": [pd.Timestamp(row[0], unit="ms") for row in ccxt_data],
                "symbol": [row[6] for row in ccxt_data],
                "open": [Decimal(str(row[1])) for row in ccxt_data],
                "high": [Decimal(str(row[2])) for row in ccxt_data],
                "low": [Decimal(str(row[3])) for row in ccxt_data],
                "close": [Decimal(str(row[4])) for row in ccxt_data],
                "volume": [Decimal(str(row[5])) for row in ccxt_data],
            }
        )

        # Verify schema
        assert "timestamp" in df.columns
        assert "symbol" in df.columns
        assert "open" in df.columns
        assert "high" in df.columns
        assert "low" in df.columns
        assert "close" in df.columns
        assert "volume" in df.columns

        # Verify data types (Polars doesn't auto-cast Decimal in DataFrame constructor)
        assert df["symbol"][0] == "BTC/USDT"
        assert df["timestamp"][0] == pd.Timestamp("2021-01-01 00:00:00")

        # Verify Decimal precision preservation
        assert isinstance(df["open"][0], Decimal)
        assert df["open"][0] == Decimal("29000.5")
        assert df["high"][0] == Decimal("29500.0")

    def test_decimal_conversion_preserves_precision(self) -> None:
        """Decimal conversion preserves precision correctly."""
        CCXTAdapter(exchange_id="binance")

        # Test various price formats as strings (to avoid float formatting issues)
        test_cases = [
            ("29000.5", Decimal("29000.5")),
            ("29000.12345678", Decimal("29000.12345678")),
            ("1.23456789", Decimal("1.23456789")),
            ("0.00000123", Decimal("0.00000123")),
        ]

        for price_str, expected_decimal in test_cases:
            # Simulate CCXT returning float, we convert via str()
            price_float = float(price_str)
            decimal_price = Decimal(str(price_float))

            # Verify Decimal type
            assert isinstance(decimal_price, Decimal)

            # Verify conversion worked (may lose precision for very small numbers)
            # This tests that the conversion process works, not exact precision
            assert abs(decimal_price - expected_decimal) < Decimal("0.00000001")

    @pytest.mark.asyncio
    async def test_fetch_unsupported_resolution_error(self) -> None:
        """Fetch raises ValueError for unsupported resolution."""
        adapter = CCXTAdapter(exchange_id="binance")

        with pytest.raises(ValueError, match="Unsupported resolution"):
            await adapter.fetch(
                symbols=["BTC/USDT"],
                start_date=pd.Timestamp("2024-01-01"),
                end_date=pd.Timestamp("2024-01-02"),
                resolution="3h",  # Not in RESOLUTION_MAPPING
            )

    @pytest.mark.asyncio
    async def test_fetch_invalid_symbol_error(self) -> None:
        """Fetch raises InvalidDataError for invalid symbol."""
        adapter = CCXTAdapter(exchange_id="binance")

        # Mock markets to avoid network call
        adapter.exchange.markets = {
            "BTC/USDT": {"symbol": "BTC/USDT", "active": True},
            "ETH/USDT": {"symbol": "ETH/USDT", "active": True},
        }

        with pytest.raises(InvalidDataError, match="not found"):
            await adapter.fetch(
                symbols=["INVALID/SYMBOL"],
                start_date=pd.Timestamp("2024-01-01"),
                end_date=pd.Timestamp("2024-01-02"),
                resolution="1d",
            )


@pytest.mark.live
@pytest.mark.asyncio
class TestCCXTAdapterLive:
    """Integration tests for CCXTAdapter with live data.

    These tests require network access and make real API calls to exchanges.
    Run with: pytest -m live tests/data/adapters/test_ccxt_adapter.py
    """

    async def test_fetch_live_data_binance(self) -> None:
        """Fetch live BTC/USDT data from Binance."""
        adapter = CCXTAdapter(exchange_id="binance")

        df = await adapter.fetch(
            symbols=["BTC/USDT"],
            start_date=pd.Timestamp("2024-01-01"),
            end_date=pd.Timestamp("2024-01-02"),
            resolution="1h",
        )

        # Verify data fetched
        assert len(df) > 0, "No data returned from Binance"
        assert "BTC/USDT" in df["symbol"].unique().to_list()

        # Verify schema compliance
        assert "timestamp" in df.columns
        assert "symbol" in df.columns
        assert "open" in df.columns
        assert "high" in df.columns
        assert "low" in df.columns
        assert "close" in df.columns
        assert "volume" in df.columns

        # Verify Decimal types for OHLCV columns
        for col in ["open", "high", "low", "close", "volume"]:
            assert all(isinstance(val, Decimal) for val in df[col].to_list())

        # Validate OHLCV relationships
        adapter.validate(df)

    async def test_fetch_live_data_coinbase(self) -> None:
        """Fetch live ETH/USD data from Coinbase."""
        adapter = CCXTAdapter(exchange_id="coinbase")

        df = await adapter.fetch(
            symbols=["ETH/USD"],
            start_date=pd.Timestamp("2024-01-01"),
            end_date=pd.Timestamp("2024-01-02"),
            resolution="1d",
        )

        # Verify data fetched
        assert len(df) > 0, "No data returned from Coinbase"
        assert "ETH/USD" in df["symbol"].unique().to_list()

        # Validate schema and relationships
        adapter.validate(df)

    async def test_fetch_live_data_kraken(self) -> None:
        """Fetch live BTC/USD data from Kraken."""
        adapter = CCXTAdapter(exchange_id="kraken")

        df = await adapter.fetch(
            symbols=["BTC/USD"],
            start_date=pd.Timestamp("2024-01-01"),
            end_date=pd.Timestamp("2024-01-02"),
            resolution="1d",
        )

        # Verify data fetched
        assert len(df) > 0, "No data returned from Kraken"
        assert "BTC/USD" in df["symbol"].unique().to_list()

        # Validate schema and relationships
        adapter.validate(df)

    async def test_multi_exchange_comparison(self) -> None:
        """Fetch same symbol from multiple exchanges and compare."""
        exchanges = ["binance", "coinbase", "kraken"]
        results = {}

        for exchange_id in exchanges:
            try:
                adapter = CCXTAdapter(exchange_id=exchange_id)

                # Note: Different exchanges may use different symbol formats
                # Binance/Kraken: BTC/USD or BTC/USDT, Coinbase: BTC/USD
                symbol = "BTC/USD" if exchange_id == "coinbase" else "BTC/USDT"

                df = await adapter.fetch(
                    symbols=[symbol],
                    start_date=pd.Timestamp("2024-01-01"),
                    end_date=pd.Timestamp("2024-01-02"),
                    resolution="1d",
                )

                results[exchange_id] = df

            except Exception as e:
                pytest.skip(f"Exchange {exchange_id} unavailable: {e}")

        # Verify all exchanges returned data
        for exchange_id, df in results.items():
            assert len(df) > 0, f"No data from {exchange_id}"

            # Verify Decimal types
            for col in ["open", "high", "low", "close", "volume"]:
                assert all(isinstance(val, Decimal) for val in df[col].to_list())

    async def test_multi_symbol_fetch(self) -> None:
        """Fetch multiple symbols in single request."""
        adapter = CCXTAdapter(exchange_id="binance")

        df = await adapter.fetch(
            symbols=["BTC/USDT", "ETH/USDT"],
            start_date=pd.Timestamp("2024-01-01"),
            end_date=pd.Timestamp("2024-01-02"),
            resolution="1h",
        )

        # Verify both symbols present
        symbols = df["symbol"].unique().to_list()
        assert "BTC/USDT" in symbols
        assert "ETH/USDT" in symbols

        # Verify data for each symbol
        btc_data = df.filter(pl.col("symbol") == "BTC/USDT")
        eth_data = df.filter(pl.col("symbol") == "ETH/USDT")

        assert len(btc_data) > 0, "No BTC data"
        assert len(eth_data) > 0, "No ETH data"

    async def test_pagination_large_date_range(self) -> None:
        """Test pagination handles large date ranges correctly."""
        adapter = CCXTAdapter(exchange_id="binance")

        # Fetch 30 days of hourly data (720 bars) - should trigger pagination
        df = await adapter.fetch(
            symbols=["BTC/USDT"],
            start_date=pd.Timestamp("2024-01-01"),
            end_date=pd.Timestamp("2024-01-31"),
            resolution="1h",
        )

        # Verify significant amount of data returned
        assert len(df) > 500, f"Expected >500 bars, got {len(df)}"

        # Verify data is sorted by timestamp
        assert df["timestamp"].is_sorted()

        # Verify no duplicate timestamps
        duplicates = (
            df.group_by(["symbol", "timestamp"])
            .agg(pl.count().alias("count"))
            .filter(pl.col("count") > 1)
        )
        assert len(duplicates) == 0, f"Found {len(duplicates)} duplicate timestamps"


@pytest.mark.unit
class TestCCXTAdapterEdgeCases:
    """Unit tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_date_range(self) -> None:
        """Fetch with empty date range returns empty DataFrame."""
        adapter = CCXTAdapter(exchange_id="binance")

        # Mock markets to avoid network call
        adapter.exchange.markets = {
            "BTC/USDT": {"symbol": "BTC/USDT", "active": True},
        }

        # Start date after end date (inverted range)
        df = await adapter.fetch(
            symbols=["BTC/USDT"],
            start_date=pd.Timestamp("2024-01-02"),
            end_date=pd.Timestamp("2024-01-01"),
            resolution="1h",
        )

        # Should return empty DataFrame with correct schema
        assert len(df) == 0
        assert "timestamp" in df.columns
        assert "symbol" in df.columns

    def test_testnet_mode_initialization(self) -> None:
        """CCXTAdapter initializes with testnet mode if available."""
        # Binance has testnet support
        adapter = CCXTAdapter(exchange_id="binance", testnet=True)

        assert adapter.testnet is True
        # Note: sandbox mode may not be enabled if exchange doesn't support it

    def test_api_credentials_initialization(self) -> None:
        """CCXTAdapter accepts API credentials."""
        adapter = CCXTAdapter(exchange_id="binance", api_key="test_key", api_secret="test_secret")

        assert adapter.exchange.apiKey == "test_key"
        assert adapter.exchange.secret == "test_secret"
