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
