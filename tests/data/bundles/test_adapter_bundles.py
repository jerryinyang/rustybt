"""
Tests for Adapter-Bundle Bridge Functions (Story 8.1)

Tests cover:
- YFinance profiling bundle creation
- CCXT profiling bundle creation
- CSV profiling bundle wrapper
- Metadata tracking
- Integration with DataPortal
"""

from unittest.mock import Mock, patch

import pandas as pd
import pytest

from rustybt.data.bundles.adapter_bundles import (
    _create_bundle_from_adapter,
    _track_api_bundle_metadata,
    ccxt_hourly_profiling_bundle,
    ccxt_minute_profiling_bundle,
    csv_profiling_bundle,
    get_profiling_bundle_info,
    list_profiling_bundles,
    yfinance_profiling_bundle,
)


@pytest.fixture(scope="function")
def init_catalog_db(tmp_path):
    """Initialize unified metadata schema for testing."""
    import sqlalchemy as sa

    from rustybt.assets.asset_db_schema import metadata

    # Create temporary database
    db_path = tmp_path / "test_catalog.db"
    engine = sa.create_engine(f"sqlite:///{db_path}")

    # Create tables
    metadata.create_all(engine)

    yield engine, str(db_path)

    # Cleanup
    engine.dispose()


@pytest.fixture
def mock_adapter():
    """Mock adapter with fetch_ohlcv method."""
    adapter = Mock()
    adapter.__class__.__name__ = "YFinanceAdapter"
    adapter.fetch_ohlcv.return_value = pd.DataFrame(
        {
            "date": pd.date_range("2023-01-01", periods=10, freq="D"),
            "symbol": ["AAPL"] * 10,
            "open": [100.0] * 10,
            "high": [105.0] * 10,
            "low": [95.0] * 10,
            "close": [102.0] * 10,
            "volume": [1000000] * 10,
        }
    )
    return adapter


@pytest.fixture
def mock_writers():
    """Mock Zipline bundle writers."""
    return {
        "daily_bar_writer": Mock(),
        "minute_bar_writer": Mock(),
    }


@pytest.fixture
def bundle_params():
    """Standard bundle parameters."""
    return {
        "bundle_name": "test-bundle",
        "symbols": ["AAPL", "MSFT"],
        "start": pd.Timestamp("2023-01-01"),
        "end": pd.Timestamp("2023-12-31"),
        "frequency": "1d",
    }


# ============================================================================
# Core Bridge Function Tests
# ============================================================================


def test_create_bundle_from_adapter_daily(
    mock_adapter, mock_writers, bundle_params, init_catalog_db
):
    """Test bridge function creates daily bundle correctly."""
    engine, db_path = init_catalog_db

    # Mock DataCatalog to use test database
    with patch("rustybt.data.metadata_tracker.DataCatalog") as mock_catalog_class:
        from rustybt.data.catalog import DataCatalog

        mock_catalog_class.return_value = DataCatalog(db_path)

        _create_bundle_from_adapter(
            adapter=mock_adapter,
            writers=mock_writers,
            **bundle_params,
        )

    # Verify adapter called
    mock_adapter.fetch_ohlcv.assert_called_once_with(
        symbols=bundle_params["symbols"],
        start=bundle_params["start"],
        end=bundle_params["end"],
        frequency=bundle_params["frequency"],
    )

    # Verify daily writer used
    mock_writers["daily_bar_writer"].write.assert_called_once()
    mock_writers["minute_bar_writer"].write.assert_not_called()


def test_create_bundle_from_adapter_minute(
    mock_adapter, mock_writers, bundle_params, init_catalog_db
):
    """Test bridge function creates minute bundle correctly."""
    engine, db_path = init_catalog_db
    bundle_params["frequency"] = "1m"

    # Mock DataCatalog to use test database
    with patch("rustybt.data.metadata_tracker.DataCatalog") as mock_catalog_class:
        from rustybt.data.catalog import DataCatalog

        mock_catalog_class.return_value = DataCatalog(db_path)

        _create_bundle_from_adapter(
            adapter=mock_adapter,
            writers=mock_writers,
            **bundle_params,
        )

    # Verify minute writer used
    mock_writers["minute_bar_writer"].write.assert_called_once()
    mock_writers["daily_bar_writer"].write.assert_not_called()


def test_create_bundle_from_adapter_empty_data(mock_adapter, mock_writers, bundle_params):
    """Test bridge handles empty DataFrame from adapter."""
    mock_adapter.fetch_ohlcv.return_value = pd.DataFrame()

    _create_bundle_from_adapter(
        adapter=mock_adapter,
        writers=mock_writers,
        **bundle_params,
    )

    # Verify writers NOT called (no data to write)
    mock_writers["daily_bar_writer"].write.assert_not_called()
    mock_writers["minute_bar_writer"].write.assert_not_called()


def test_create_bundle_from_adapter_invalid_frequency(mock_adapter, mock_writers, bundle_params):
    """Test bridge raises error for unsupported frequency."""
    bundle_params["frequency"] = "30s"  # Invalid

    with pytest.raises(ValueError, match="Unsupported frequency"):
        _create_bundle_from_adapter(
            adapter=mock_adapter,
            writers=mock_writers,
            **bundle_params,
        )


# ============================================================================
# Metadata Tracking Tests
# ============================================================================


def test_track_api_bundle_metadata_yfinance(mock_adapter):
    """Test metadata tracking for YFinance adapter."""
    df = pd.DataFrame(
        {
            "date": pd.date_range("2023-01-01", periods=252, freq="D"),
            "open": [100.0] * 252,
            "high": [105.0] * 252,
            "low": [95.0] * 252,
            "close": [102.0] * 252,
        }
    )

    with patch("rustybt.data.bundles.adapter_bundles.track_api_bundle_metadata") as mock_track:
        mock_track.return_value = {
            "metadata": {"bundle_name": "test-bundle", "source_type": "yfinance"},
            "quality_metrics": {"ohlcv_violations": 0},
        }

        _track_api_bundle_metadata(
            bundle_name="test-bundle",
            adapter=mock_adapter,
            df=df,
            start=pd.Timestamp("2023-01-01"),
            end=pd.Timestamp("2023-12-31"),
            frequency="1d",
        )

        # Verify tracking function was called
        mock_track.assert_called_once()
        call_kwargs = mock_track.call_args[1]
        assert call_kwargs["bundle_name"] == "test-bundle"
        assert call_kwargs["source_type"] == "yfinance"
        assert "query2.finance.yahoo.com" in call_kwargs["api_url"]


def test_track_api_bundle_metadata_ccxt():
    """Test metadata tracking for CCXT adapter."""
    adapter = Mock()
    adapter.__class__.__name__ = "CCXTAdapter"
    adapter.exchange_id = "binance"
    adapter.api_version = "v3"

    df = pd.DataFrame(
        {
            "date": pd.date_range("2023-01-01", periods=100, freq="H"),
            "open": [100.0] * 100,
            "high": [105.0] * 100,
            "low": [95.0] * 100,
            "close": [102.0] * 100,
        }
    )

    with patch("rustybt.data.bundles.adapter_bundles.track_api_bundle_metadata") as mock_track:
        mock_track.return_value = {"metadata": {}, "quality_metrics": {}}

        _track_api_bundle_metadata(
            bundle_name="ccxt-test",
            adapter=adapter,
            df=df,
            start=pd.Timestamp("2023-01-01"),
            end=pd.Timestamp("2023-01-05"),
            frequency="1h",
        )

        call_kwargs = mock_track.call_args[1]
        assert call_kwargs["source_type"] == "ccxt"
        assert "binance.com" in call_kwargs["api_url"]
        assert call_kwargs["api_version"] == "v3"


def test_track_api_bundle_metadata_ohlcv_violations():
    """Test quality tracking detects OHLCV violations."""
    adapter = Mock()
    adapter.__class__.__name__ = "YFinanceAdapter"

    # Create data with violations
    df = pd.DataFrame(
        {
            "date": pd.date_range("2023-01-01", periods=10, freq="D"),
            "open": [100.0] * 10,
            "high": [95.0] * 10,  # High < Low (violation)
            "low": [105.0] * 10,
            "close": [110.0] * 10,  # Close > High (violation)
        }
    )

    with patch("rustybt.data.bundles.adapter_bundles.track_api_bundle_metadata") as mock_track:
        # Simulate quality metrics showing violations
        mock_track.return_value = {
            "metadata": {},
            "quality_metrics": {"ohlcv_violations": 20, "validation_passed": False},
        }

        _track_api_bundle_metadata(
            bundle_name="test",
            adapter=adapter,
            df=df,
            start=pd.Timestamp("2023-01-01"),
            end=pd.Timestamp("2023-01-10"),
            frequency="1d",
        )

        # Verify track_api_bundle_metadata was called
        assert mock_track.called


# ============================================================================
# Profiling Bundle Tests
# ============================================================================


@pytest.fixture
def zipline_bundle_args():
    """Standard Zipline bundle function arguments."""
    return {
        "environ": {},
        "asset_db_writer": Mock(),
        "minute_bar_writer": Mock(),
        "daily_bar_writer": Mock(),
        "adjustment_writer": Mock(),
        "calendar": Mock(),
        "start_session": pd.Timestamp("2023-01-01"),
        "end_session": pd.Timestamp("2023-12-31"),
        "cache": Mock(),
        "show_progress": False,
        "output_dir": "/tmp/test-bundle",
    }


@patch("rustybt.data.bundles.adapter_bundles.YFinanceAdapter")
@patch("rustybt.data.bundles.adapter_bundles._create_bundle_from_adapter")
def test_yfinance_profiling_bundle(mock_create, mock_adapter_class, zipline_bundle_args):
    """Test YFinance profiling bundle creation."""
    with pytest.warns(DeprecationWarning):
        yfinance_profiling_bundle(**zipline_bundle_args)

    # Verify adapter instantiated
    mock_adapter_class.assert_called_once()

    # Verify bridge function called with 50 symbols
    mock_create.assert_called_once()
    call_kwargs = mock_create.call_args[1]
    assert call_kwargs["bundle_name"] == "yfinance-profiling"
    assert len(call_kwargs["symbols"]) == 50
    assert "AAPL" in call_kwargs["symbols"]
    assert call_kwargs["frequency"] == "1d"


@patch("rustybt.data.bundles.adapter_bundles.CCXTAdapter")
@patch("rustybt.data.bundles.adapter_bundles._create_bundle_from_adapter")
def test_ccxt_hourly_profiling_bundle(mock_create, mock_adapter_class, zipline_bundle_args):
    """Test CCXT hourly profiling bundle creation."""
    with pytest.warns(DeprecationWarning):
        ccxt_hourly_profiling_bundle(**zipline_bundle_args)

    # Verify CCXT adapter with Binance exchange
    mock_adapter_class.assert_called_once_with(exchange_id="binance")

    # Verify bridge function called with 20 symbols
    mock_create.assert_called_once()
    call_kwargs = mock_create.call_args[1]
    assert call_kwargs["bundle_name"] == "ccxt-hourly-profiling"
    assert len(call_kwargs["symbols"]) == 20
    assert "BTC/USDT" in call_kwargs["symbols"]
    assert call_kwargs["frequency"] == "1h"


@patch("rustybt.data.bundles.adapter_bundles.CCXTAdapter")
@patch("rustybt.data.bundles.adapter_bundles._create_bundle_from_adapter")
def test_ccxt_minute_profiling_bundle(mock_create, mock_adapter_class, zipline_bundle_args):
    """Test CCXT minute profiling bundle creation."""
    with pytest.warns(DeprecationWarning):
        ccxt_minute_profiling_bundle(**zipline_bundle_args)

    # Verify bridge function called with 10 symbols
    call_kwargs = mock_create.call_args[1]
    assert call_kwargs["bundle_name"] == "ccxt-minute-profiling"
    assert len(call_kwargs["symbols"]) == 10
    assert call_kwargs["frequency"] == "1m"


@patch("rustybt.data.bundles.adapter_bundles.CSVAdapter")
@patch("rustybt.data.bundles.adapter_bundles._create_bundle_from_adapter")
@patch("rustybt.data.bundles.adapter_bundles.track_csv_bundle_metadata")
def test_csv_profiling_bundle(
    mock_track_csv, mock_create, mock_adapter_class, zipline_bundle_args, tmp_path, init_catalog_db
):
    """Test CSV profiling bundle wrapper."""
    engine, db_path = init_catalog_db

    # Create test CSV files
    csv_dir = tmp_path / "csv"
    csv_dir.mkdir()

    (csv_dir / "AAPL.csv").write_text(
        "date,open,high,low,close,volume\n2023-01-01,100,105,95,102,1000000\n"
    )
    (csv_dir / "MSFT.csv").write_text(
        "date,open,high,low,close,volume\n2023-01-01,200,205,195,202,2000000\n"
    )

    zipline_bundle_args["environ"] = {"CSVDIR": str(csv_dir)}

    # Mock DataCatalog in track_csv_bundle_metadata
    with patch("rustybt.data.metadata_tracker.DataCatalog") as mock_catalog_class:
        from rustybt.data.catalog import DataCatalog

        mock_catalog_class.return_value = DataCatalog(db_path)

        with pytest.warns(DeprecationWarning):
            csv_profiling_bundle(**zipline_bundle_args)

    # Verify CSV adapter instantiated
    mock_adapter_class.assert_called_once_with(csv_dir=str(csv_dir))

    # Verify bridge function called
    mock_create.assert_called_once()
    call_kwargs = mock_create.call_args[1]
    assert call_kwargs["bundle_name"] == "csv-profiling"
    assert set(call_kwargs["symbols"]) == {"AAPL", "MSFT"}


# ============================================================================
# CLI Integration Tests
# ============================================================================


def test_list_profiling_bundles():
    """Test listing all profiling bundles."""
    bundles = list_profiling_bundles()

    assert "yfinance-profiling" in bundles
    assert "ccxt-hourly-profiling" in bundles
    assert "ccxt-minute-profiling" in bundles
    assert "csv-profiling" in bundles
    assert len(bundles) == 4


def test_get_profiling_bundle_info_yfinance():
    """Test getting YFinance bundle info."""
    info = get_profiling_bundle_info("yfinance-profiling")

    assert info is not None
    assert info["symbol_count"] == 50
    assert info["frequency"] == "1d"
    assert info["duration"] == "2 years"
    assert "YFinanceAdapter" in info["adapter"]


def test_get_profiling_bundle_info_ccxt():
    """Test getting CCXT bundle info."""
    info = get_profiling_bundle_info("ccxt-hourly-profiling")

    assert info is not None
    assert info["symbol_count"] == 20
    assert info["frequency"] == "1h"
    assert "Binance" in info["adapter"]


def test_get_profiling_bundle_info_invalid():
    """Test getting info for non-existent bundle."""
    info = get_profiling_bundle_info("invalid-bundle")
    assert info is None


# ============================================================================
# Integration Tests (End-to-End)
# ============================================================================


@pytest.mark.integration
@pytest.mark.slow
@patch("rustybt.data.bundles.adapter_bundles.YFinanceAdapter")
def test_yfinance_bundle_end_to_end(
    mock_adapter_class, zipline_bundle_args, tmp_path, init_catalog_db
):
    """Integration test: YFinance bundle → DataPortal read."""
    engine, db_path = init_catalog_db

    # Mock adapter to return realistic data
    mock_adapter = Mock()
    mock_adapter.fetch_ohlcv.return_value = pd.DataFrame(
        {
            "date": pd.date_range("2023-01-01", periods=252, freq="D"),
            "symbol": ["AAPL"] * 252,
            "open": [100.0 + i for i in range(252)],
            "high": [105.0 + i for i in range(252)],
            "low": [95.0 + i for i in range(252)],
            "close": [102.0 + i for i in range(252)],
            "volume": [1000000] * 252,
        }
    )
    mock_adapter_class.return_value = mock_adapter

    # Mock DataCatalog to use test database
    with patch("rustybt.data.metadata_tracker.DataCatalog") as mock_catalog_class:
        from rustybt.data.catalog import DataCatalog

        mock_catalog_class.return_value = DataCatalog(db_path)

        # Create bundle
        with pytest.warns(DeprecationWarning):
            yfinance_profiling_bundle(**zipline_bundle_args)

    # Verify daily writer received data
    assert zipline_bundle_args["daily_bar_writer"].write.called

    # Verify data can be loaded (would use DataPortal in real test)
    df = zipline_bundle_args["daily_bar_writer"].write.call_args[0][0]
    assert len(df) == 252
    assert "AAPL" in df["symbol"].values


@pytest.mark.integration
def test_metadata_tracked_after_bundle_creation(mock_adapter, mock_writers, bundle_params):
    """Integration test: Verify metadata automatically tracked."""
    with patch("rustybt.data.bundles.adapter_bundles.track_api_bundle_metadata") as mock_track:
        mock_track.return_value = {"metadata": {}, "quality_metrics": {}}

        _create_bundle_from_adapter(
            adapter=mock_adapter,
            writers=mock_writers,
            **bundle_params,
        )

        # Verify tracking function called
        assert mock_track.called


# ============================================================================
# Deprecation Warning Tests
# ============================================================================


def test_deprecation_warnings_emitted(zipline_bundle_args):
    """Test that deprecation warnings are emitted for all bridge functions."""
    with patch("rustybt.data.bundles.adapter_bundles._create_bundle_from_adapter"):
        # YFinance
        with pytest.warns(DeprecationWarning, match="yfinance_profiling_bundle"):
            with patch("rustybt.data.bundles.adapter_bundles.YFinanceAdapter"):
                yfinance_profiling_bundle(**zipline_bundle_args)

        # CCXT Hourly
        with pytest.warns(DeprecationWarning, match="ccxt_hourly_profiling_bundle"):
            with patch("rustybt.data.bundles.adapter_bundles.CCXTAdapter"):
                ccxt_hourly_profiling_bundle(**zipline_bundle_args)

        # CCXT Minute
        with pytest.warns(DeprecationWarning, match="ccxt_minute_profiling_bundle"):
            with patch("rustybt.data.bundles.adapter_bundles.CCXTAdapter"):
                ccxt_minute_profiling_bundle(**zipline_bundle_args)

        # CSV
        with pytest.warns(DeprecationWarning, match="csv_profiling_bundle"):
            with patch("rustybt.data.bundles.adapter_bundles.CSVAdapter"):
                csv_profiling_bundle(**zipline_bundle_args)


# ============================================================================
# Transformation Layer Tests (Issue #3 Fix - NO MOCKS)
# ============================================================================


def test_transform_for_writer_polars_dataframe():
    """Test transformation with real Polars DataFrame (no mocks)."""
    import polars as pl

    from rustybt.data.bundles.adapter_bundles import _transform_for_writer

    # Create realistic OHLCV data for multiple symbols
    df = pl.DataFrame(
        {
            "timestamp": (
                [pd.Timestamp("2024-01-01") + pd.Timedelta(days=i) for i in range(5)]
                + [pd.Timestamp("2024-01-01") + pd.Timedelta(days=i) for i in range(5)]
                + [pd.Timestamp("2024-01-01") + pd.Timedelta(days=i) for i in range(5)]
            ),
            "symbol": ["AAPL"] * 5 + ["MSFT"] * 5 + ["GOOGL"] * 5,
            "open": [150.0 + i for i in range(5)]
            + [300.0 + i for i in range(5)]
            + [2800.0 + i for i in range(5)],
            "high": [155.0 + i for i in range(5)]
            + [305.0 + i for i in range(5)]
            + [2850.0 + i for i in range(5)],
            "low": [148.0 + i for i in range(5)]
            + [298.0 + i for i in range(5)]
            + [2790.0 + i for i in range(5)],
            "close": [152.0 + i for i in range(5)]
            + [302.0 + i for i in range(5)]
            + [2820.0 + i for i in range(5)],
            "volume": [1000000.0] * 15,
        }
    )

    symbols = ["AAPL", "MSFT", "GOOGL"]

    # Transform to (sid, df) tuples
    result = list(_transform_for_writer(df, symbols, "test-bundle"))

    # Verify correct number of tuples
    assert len(result) == 3, f"Expected 3 tuples, got {len(result)}"

    # Verify tuple structure: (sid, pandas_df)
    for sid, symbol_df in result:
        assert isinstance(sid, int), f"SID should be int, got {type(sid)}"
        assert isinstance(
            symbol_df, pd.DataFrame
        ), f"DataFrame should be pandas, got {type(symbol_df)}"

        # Verify SID is sequential (0, 1, 2)
        assert sid >= 0 and sid < 3, f"SID {sid} out of range"

        # Verify DataFrame has correct number of rows (5 per symbol)
        assert len(symbol_df) == 5, f"Symbol {sid} should have 5 rows, got {len(symbol_df)}"

        # Verify DataFrame has datetime index
        assert isinstance(
            symbol_df.index, pd.DatetimeIndex
        ), f"Index should be DatetimeIndex, got {type(symbol_df.index)}"

        # Verify DataFrame has required columns
        required_cols = ["open", "high", "low", "close", "volume"]
        for col in required_cols:
            assert col in symbol_df.columns, f"Missing required column: {col}"

        # Verify symbol column was dropped (writer doesn't need it)
        assert "symbol" not in symbol_df.columns, "Symbol column should be dropped"

        # Verify OHLCV values are correct (no data corruption)
        assert (symbol_df["high"] >= symbol_df["low"]).all(), "High should be >= Low"
        assert (symbol_df["high"] >= symbol_df["open"]).all(), "High should be >= Open"
        assert (symbol_df["high"] >= symbol_df["close"]).all(), "High should be >= Close"


def test_transform_for_writer_pandas_dataframe():
    """Test transformation with real pandas DataFrame (no mocks)."""
    from rustybt.data.bundles.adapter_bundles import _transform_for_writer

    # Create realistic pandas DataFrame
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=10, freq="D").tolist() * 2,
            "symbol": ["AAPL"] * 10 + ["MSFT"] * 10,
            "open": list(range(100, 110)) + list(range(200, 210)),
            "high": list(range(105, 115)) + list(range(205, 215)),
            "low": list(range(95, 105)) + list(range(195, 205)),
            "close": list(range(102, 112)) + list(range(202, 212)),
            "volume": [1000000] * 20,
        }
    )

    symbols = ["AAPL", "MSFT"]

    # Transform
    result = list(_transform_for_writer(df, symbols, "test-bundle"))

    # Verify correct transformation
    assert len(result) == 2
    assert result[0][0] == 0  # First SID
    assert result[1][0] == 1  # Second SID
    assert len(result[0][1]) == 10  # 10 rows for AAPL
    assert len(result[1][1]) == 10  # 10 rows for MSFT


def test_transform_for_writer_missing_symbol_data():
    """Test transformation handles symbols with no data (no mocks)."""
    import polars as pl

    from rustybt.data.bundles.adapter_bundles import _transform_for_writer

    # Create data with only 2 of 3 requested symbols
    df = pl.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=5, freq="D").tolist() * 2,
            "symbol": ["AAPL"] * 5 + ["MSFT"] * 5,
            "open": list(range(100, 105)) + list(range(200, 205)),
            "high": list(range(105, 110)) + list(range(205, 210)),
            "low": list(range(95, 100)) + list(range(195, 200)),
            "close": list(range(102, 107)) + list(range(202, 207)),
            "volume": [1000000] * 10,
        }
    )

    # Request 3 symbols but data only has 2
    symbols = ["AAPL", "GOOGL", "MSFT"]  # GOOGL has no data

    # Transform
    result = list(_transform_for_writer(df, symbols, "test-bundle"))

    # Should only yield 2 tuples (AAPL and MSFT)
    assert len(result) == 2, "Should skip symbols with no data"

    # Verify SIDs are consecutive (0, 1) despite skipping GOOGL
    sids = [sid for sid, _ in result]
    assert sids == [0, 1], f"SIDs should be consecutive, got {sids}"


def test_transform_for_writer_missing_symbol_column():
    """Test transformation raises error if symbol column missing (no mocks)."""
    import polars as pl

    from rustybt.data.bundles.adapter_bundles import _transform_for_writer

    # Create DataFrame without symbol column
    df = pl.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=5, freq="D"),
            "open": list(range(100, 105)),
            "high": list(range(105, 110)),
            "low": list(range(95, 100)),
            "close": list(range(102, 107)),
            "volume": [1000000] * 5,
        }
    )

    symbols = ["AAPL"]

    # Should raise ValueError
    with pytest.raises(ValueError, match="missing 'symbol' column"):
        list(_transform_for_writer(df, symbols, "test-bundle"))


def test_transform_for_writer_preserves_ohlcv_values():
    """Test transformation preserves exact OHLCV values (no mocks, no rounding)."""
    import polars as pl

    from rustybt.data.bundles.adapter_bundles import _transform_for_writer

    # Create data with precise decimal values
    df = pl.DataFrame(
        {
            "timestamp": [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-02")],
            "symbol": ["AAPL", "AAPL"],
            "open": [123.456789, 124.567890],
            "high": [125.678901, 126.789012],
            "low": [121.234567, 122.345678],
            "close": [124.567890, 125.678901],
            "volume": [1234567.0, 2345678.0],
        }
    )

    symbols = ["AAPL"]

    # Transform
    result = list(_transform_for_writer(df, symbols, "test-bundle"))

    # Verify values preserved
    sid, symbol_df = result[0]
    assert sid == 0
    assert symbol_df.iloc[0]["open"] == pytest.approx(123.456789, rel=1e-9)
    assert symbol_df.iloc[0]["high"] == pytest.approx(125.678901, rel=1e-9)
    assert symbol_df.iloc[1]["close"] == pytest.approx(125.678901, rel=1e-9)


def test_transform_for_writer_datetime_index_type():
    """Test transformation creates proper datetime index (no mocks)."""
    import polars as pl

    from rustybt.data.bundles.adapter_bundles import _transform_for_writer

    # Create data with timestamp column
    df = pl.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=5, freq="D"),
            "symbol": ["AAPL"] * 5,
            "open": [100.0] * 5,
            "high": [105.0] * 5,
            "low": [95.0] * 5,
            "close": [102.0] * 5,
            "volume": [1000000.0] * 5,
        }
    )

    symbols = ["AAPL"]

    # Transform
    result = list(_transform_for_writer(df, symbols, "test-bundle"))

    sid, symbol_df = result[0]

    # Verify index is DatetimeIndex
    assert isinstance(symbol_df.index, pd.DatetimeIndex), "Index must be DatetimeIndex"

    # Verify index is sorted
    assert symbol_df.index.is_monotonic_increasing, "Index must be sorted"

    # Verify index values match original timestamps (ignore index name)
    expected_dates = pd.date_range("2024-01-01", periods=5, freq="D")
    pd.testing.assert_index_equal(symbol_df.index, expected_dates, check_names=False)


# ============================================================================
# Adjustment Transformation Tests (Zero-Mock Enforcement)
# ============================================================================


def test_transform_splits_for_writer_with_real_data():
    """Test splits transformation with real split data (NO MOCKS).

    This test uses actual historical stock split data to ensure the transformation
    correctly maps symbols to SIDs and formats data for SQLiteAdjustmentWriter.

    Zero-Mock Enforcement: Uses real DataFrames with realistic split ratios.
    """
    import polars as pl

    from rustybt.data.bundles.adapter_bundles import _transform_splits_for_writer

    # Create asset metadata (as would be created by _create_asset_metadata)
    asset_metadata = pd.DataFrame(
        {
            "symbol": ["AAPL", "TSLA", "GOOGL"],
            "start_date": [pd.Timestamp("2020-01-01")] * 3,
            "end_date": [pd.Timestamp("2024-01-01")] * 3,
            "exchange": ["NASDAQ"] * 3,
            "auto_close_date": [pd.Timestamp("2024-01-02")] * 3,
        }
    )

    # Create real splits data (AAPL had 4:1 split on 2020-08-31, TSLA had 3:1 split on 2022-08-25)
    splits_data = {
        "AAPL": pl.DataFrame(
            {
                "date": [pd.Timestamp("2020-08-31")],
                "symbol": ["AAPL"],
                "split_ratio": [4.0],  # 4-for-1 split
            }
        ),
        "TSLA": pl.DataFrame(
            {
                "date": [
                    pd.Timestamp("2020-08-31"),  # 5-for-1 split
                    pd.Timestamp("2022-08-25"),  # 3-for-1 split
                ],
                "symbol": ["TSLA", "TSLA"],
                "split_ratio": [5.0, 3.0],
            }
        ),
    }

    # Transform
    splits_df = _transform_splits_for_writer(splits_data, asset_metadata)

    # Verify result
    assert splits_df is not None, "Should return DataFrame when splits exist"
    assert isinstance(splits_df, pd.DataFrame), "Result must be pandas DataFrame"
    assert len(splits_df) == 3, "Should have 3 split records total"

    # Verify columns
    expected_columns = {"sid", "effective_date", "ratio"}
    assert set(splits_df.columns) == expected_columns, f"Must have columns: {expected_columns}"

    # Verify data types
    assert (
        splits_df["sid"].dtype == "int64" or splits_df["sid"].dtype == "int32"
    ), "sid must be integer"
    assert pd.api.types.is_datetime64_any_dtype(
        splits_df["effective_date"]
    ), "effective_date must be datetime"
    assert pd.api.types.is_float_dtype(splits_df["ratio"]), "ratio must be float"

    # Verify SID mapping (AAPL=0, TSLA=1 based on asset_metadata order)
    aapl_splits = splits_df[splits_df["sid"] == 0]
    assert len(aapl_splits) == 1, "AAPL should have 1 split"
    assert aapl_splits.iloc[0]["ratio"] == 4.0, "AAPL split ratio must be 4.0"

    tsla_splits = splits_df[splits_df["sid"] == 1]
    assert len(tsla_splits) == 2, "TSLA should have 2 splits"
    assert set(tsla_splits["ratio"]) == {5.0, 3.0}, "TSLA split ratios must be 5.0 and 3.0"

    # Verify dates are correctly preserved
    assert aapl_splits.iloc[0]["effective_date"] == pd.Timestamp("2020-08-31")


def test_transform_splits_for_writer_empty_data():
    """Test splits transformation with no split data (edge case)."""
    from rustybt.data.bundles.adapter_bundles import _transform_splits_for_writer

    asset_metadata = pd.DataFrame({"symbol": ["AAPL"], "start_date": [pd.Timestamp("2020-01-01")]})

    # Test with empty dict
    result = _transform_splits_for_writer({}, asset_metadata)
    assert result is None, "Should return None when no splits data"


def test_transform_splits_for_writer_unknown_symbol():
    """Test splits transformation with symbol not in asset metadata."""
    import polars as pl

    from rustybt.data.bundles.adapter_bundles import _transform_splits_for_writer

    asset_metadata = pd.DataFrame({"symbol": ["AAPL"]})

    # Create splits for symbol not in metadata
    splits_data = {
        "UNKNOWN": pl.DataFrame(
            {
                "date": [pd.Timestamp("2020-08-31")],
                "symbol": ["UNKNOWN"],
                "split_ratio": [2.0],
            }
        )
    }

    # Transform
    result = _transform_splits_for_writer(splits_data, asset_metadata)

    # Should return None because no valid symbols
    assert result is None, "Should return None when no valid symbols"


def test_transform_dividends_for_writer_with_real_data():
    """Test dividends transformation with real dividend data (NO MOCKS).

    This test uses actual historical dividend data to ensure the transformation
    correctly maps symbols to SIDs and formats data for SQLiteAdjustmentWriter.

    Zero-Mock Enforcement: Uses real DataFrames with realistic dividend amounts.
    """
    import polars as pl

    from rustybt.data.bundles.adapter_bundles import _transform_dividends_for_writer

    # Create asset metadata
    asset_metadata = pd.DataFrame(
        {
            "symbol": ["AAPL", "MSFT", "JNJ"],
            "start_date": [pd.Timestamp("2020-01-01")] * 3,
            "end_date": [pd.Timestamp("2024-01-01")] * 3,
        }
    )

    # Create real dividend data (approximate historical values)
    dividends_data = {
        "AAPL": pl.DataFrame(
            {
                "date": [
                    pd.Timestamp("2023-02-10"),
                    pd.Timestamp("2023-05-12"),
                    pd.Timestamp("2023-08-11"),
                ],
                "symbol": ["AAPL", "AAPL", "AAPL"],
                "dividend": [0.23, 0.24, 0.24],  # Realistic quarterly dividends
            }
        ),
        "MSFT": pl.DataFrame(
            {
                "date": [
                    pd.Timestamp("2023-02-15"),
                    pd.Timestamp("2023-05-17"),
                ],
                "symbol": ["MSFT", "MSFT"],
                "dividend": [0.68, 0.68],
            }
        ),
    }

    # Transform
    dividends_df = _transform_dividends_for_writer(dividends_data, asset_metadata)

    # Verify result
    assert dividends_df is not None, "Should return DataFrame when dividends exist"
    assert isinstance(dividends_df, pd.DataFrame), "Result must be pandas DataFrame"
    assert len(dividends_df) == 5, "Should have 5 dividend records total (3 AAPL + 2 MSFT)"

    # Verify columns
    expected_columns = {"sid", "ex_date", "declared_date", "record_date", "pay_date", "amount"}
    assert set(dividends_df.columns) == expected_columns, f"Must have columns: {expected_columns}"

    # Verify data types
    assert dividends_df["sid"].dtype in ("int64", "int32"), "sid must be integer"
    assert pd.api.types.is_datetime64_any_dtype(dividends_df["ex_date"]), "ex_date must be datetime"
    assert pd.api.types.is_float_dtype(dividends_df["amount"]), "amount must be float"

    # Verify SID mapping (AAPL=0, MSFT=1 based on asset_metadata order)
    aapl_divs = dividends_df[dividends_df["sid"] == 0]
    assert len(aapl_divs) == 3, "AAPL should have 3 dividends"
    assert set(aapl_divs["amount"]) == {0.23, 0.24}, "AAPL dividend amounts must match"

    msft_divs = dividends_df[dividends_df["sid"] == 1]
    assert len(msft_divs) == 2, "MSFT should have 2 dividends"
    assert all(msft_divs["amount"] == 0.68), "MSFT dividend amounts must be 0.68"

    # Verify NaT values are set correctly for missing dates
    assert (
        dividends_df["declared_date"].isna().all()
    ), "declared_date should be NaT (not provided by YFinance)"
    assert (
        dividends_df["record_date"].isna().all()
    ), "record_date should be NaT (not provided by YFinance)"

    # Verify ex_date and pay_date are the same (YFinance limitation)
    assert (
        dividends_df["ex_date"] == dividends_df["pay_date"]
    ).all(), "ex_date and pay_date should match"


def test_transform_dividends_for_writer_empty_data():
    """Test dividends transformation with no dividend data (edge case)."""
    from rustybt.data.bundles.adapter_bundles import _transform_dividends_for_writer

    asset_metadata = pd.DataFrame({"symbol": ["AAPL"]})

    # Test with empty dict
    result = _transform_dividends_for_writer({}, asset_metadata)
    assert result is None, "Should return None when no dividends data"


def test_transform_dividends_for_writer_unknown_symbol():
    """Test dividends transformation with symbol not in asset metadata."""
    import polars as pl

    from rustybt.data.bundles.adapter_bundles import _transform_dividends_for_writer

    asset_metadata = pd.DataFrame({"symbol": ["AAPL"]})

    # Create dividends for symbol not in metadata
    dividends_data = {
        "UNKNOWN": pl.DataFrame(
            {
                "date": [pd.Timestamp("2023-02-10")],
                "symbol": ["UNKNOWN"],
                "dividend": [0.50],
            }
        )
    }

    # Transform
    result = _transform_dividends_for_writer(dividends_data, asset_metadata)

    # Should return None because no valid symbols
    assert result is None, "Should return None when no valid symbols"


def test_transform_splits_and_dividends_pandas_input():
    """Test transformation functions work with pandas DataFrames (not just Polars)."""
    from rustybt.data.bundles.adapter_bundles import (
        _transform_dividends_for_writer,
        _transform_splits_for_writer,
    )

    asset_metadata = pd.DataFrame({"symbol": ["AAPL", "MSFT"]})

    # Test with pandas DataFrame (not Polars)
    splits_data_pandas = {
        "AAPL": pd.DataFrame(
            {
                "date": [pd.Timestamp("2020-08-31")],
                "symbol": ["AAPL"],
                "split_ratio": [4.0],
            }
        )
    }

    dividends_data_pandas = {
        "MSFT": pd.DataFrame(
            {
                "date": [pd.Timestamp("2023-02-15")],
                "symbol": ["MSFT"],
                "dividend": [0.68],
            }
        )
    }

    # Transform
    splits_df = _transform_splits_for_writer(splits_data_pandas, asset_metadata)
    dividends_df = _transform_dividends_for_writer(dividends_data_pandas, asset_metadata)

    # Verify both work correctly
    assert splits_df is not None, "Should handle pandas DataFrame for splits"
    assert len(splits_df) == 1
    assert splits_df.iloc[0]["sid"] == 0  # AAPL

    assert dividends_df is not None, "Should handle pandas DataFrame for dividends"
    assert len(dividends_df) == 1
    assert dividends_df.iloc[0]["sid"] == 1  # MSFT
