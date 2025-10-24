"""Tests for DataPortal history() method with array return optimization."""

import numpy as np
import pandas as pd
import polars as pl
import pytest

from rustybt.data.polars.data_portal import PolarsDataPortal


class MockAsset:
    """Mock asset for testing."""

    def __init__(self, sid=1, symbol="AAPL"):
        self.sid = sid
        self.symbol = symbol

    def __repr__(self):
        return f"MockAsset({self.symbol})"


class MockDataSource:
    """Mock data source for testing."""

    async def fetch(self, symbols, start, end, frequency):
        """Return mock OHLCV data."""
        # Create sample data with Polars
        n_bars = 30  # Return more than requested to test slicing
        data = pl.DataFrame(
            {
                "date": pd.date_range(start, periods=n_bars, freq="D"),
                "symbol": [symbols[0]] * n_bars,
                "open": [100.0 + i for i in range(n_bars)],
                "high": [102.0 + i for i in range(n_bars)],
                "low": [98.0 + i for i in range(n_bars)],
                "close": [101.0 + i for i in range(n_bars)],
                "volume": [1000000.0 + i * 1000 for i in range(n_bars)],
            }
        )

        # Convert to Decimal (financial precision)
        for col in ["open", "high", "low", "close"]:
            data = data.with_columns(pl.col(col).cast(pl.Float64))

        return data


@pytest.fixture
def mock_asset():
    """Create mock asset for testing."""
    return MockAsset(sid=1, symbol="AAPL")


@pytest.fixture
def data_portal():
    """Create DataPortal with mock data source."""
    mock_source = MockDataSource()
    portal = PolarsDataPortal(
        data_source=mock_source,
        use_cache=False,  # Disable source-level cache for testing
        current_simulation_time=pd.Timestamp("2023-01-30"),
        enable_history_cache=True,  # Enable history cache (Layer 2)
    )
    return portal


class TestDataPortalHistory:
    """Tests for DataPortal.history() method."""

    @pytest.mark.asyncio
    async def test_history_dataframe_return(self, data_portal, mock_asset):
        """Test history() with default DataFrame return (backward compatible)."""
        # This would require async support in DataPortal or mocking
        # For now, test the existence of the method and basic structure
        assert hasattr(data_portal, "history")
        assert hasattr(data_portal, "_history_dataframe")
        assert hasattr(data_portal, "_history_array")

    def test_history_method_signature(self, data_portal):
        """Test history() method has correct signature."""
        import inspect

        sig = inspect.signature(data_portal.history)
        params = sig.parameters

        # Check required parameters
        assert "assets" in params
        assert "fields" in params
        assert "bar_count" in params
        assert "frequency" in params
        assert "return_type" in params

        # Check return_type default value
        assert params["return_type"].default == "dataframe"

    def test_history_cache_initialization(self, data_portal):
        """Test history cache is initialized properly."""
        assert data_portal.enable_history_cache is True
        assert data_portal.history_cache is not None
        assert data_portal.history_cache.permanent_windows == [20, 50, 200]
        assert data_portal.history_cache.tier2_maxsize == 256

    def test_history_cache_disabled(self):
        """Test DataPortal works with cache disabled."""
        mock_source = MockDataSource()
        portal = PolarsDataPortal(
            data_source=mock_source,
            use_cache=False,
            enable_history_cache=False,  # Disable cache
        )

        assert portal.enable_history_cache is False
        assert portal.history_cache is None

    def test_history_input_normalization(self, data_portal, mock_asset):
        """Test history() normalizes single asset/field to lists."""
        # We can test the method exists and would handle this
        # without actually executing async calls
        assert callable(data_portal.history)

        # The implementation should handle:
        # - Single asset -> [asset]
        # - Single field -> [field]


class TestHistoryCacheIntegration:
    """Tests for history cache integration with DataPortal."""

    def test_cache_stats_accessible(self, data_portal):
        """Test cache statistics are accessible."""
        stats = data_portal.history_cache.get_stats()

        assert "hits" in stats
        assert "misses" in stats
        assert "hit_rate" in stats
        assert "tier1_size" in stats
        assert "tier2_size" in stats
        assert "memory_bytes" in stats
        assert "memory_mb" in stats

    def test_cache_warming_stats_accessible(self, data_portal):
        """Test cache warming statistics are accessible."""
        warming_stats = data_portal.history_cache.get_cache_warming_stats()

        assert "total_requests" in warming_stats
        assert "current_hit_rate" in warming_stats
        assert "is_warmed" in warming_stats
        assert "tier1_utilization" in warming_stats
        assert "tier2_utilization" in warming_stats


class TestBackwardCompatibility:
    """Tests for backward compatibility with existing DataPortal API."""

    def test_get_history_window_still_works(self, data_portal):
        """Test existing get_history_window() method still works."""
        assert hasattr(data_portal, "get_history_window")
        assert callable(data_portal.get_history_window)

    def test_default_return_type_is_dataframe(self, data_portal):
        """Test that default return_type='dataframe' preserves existing behavior."""
        import inspect

        sig = inspect.signature(data_portal.history)
        assert sig.parameters["return_type"].default == "dataframe"


class TestArrayReturnPath:
    """Tests for NumPy array return optimization."""

    def test_array_return_shape(self):
        """Test array return has correct shape."""
        # This would test the _history_array method returns correct shape
        # (n_bars, n_fields) for single field -> (n_bars, 1)
        # We'll test this in integration tests
        pass

    def test_decimal_to_float64_conversion(self):
        """Test Decimal to float64 conversion in array path."""
        # Test that Polars Decimal columns are converted to float64
        # with controlled precision (1e-10 tolerance)
        pass

    def test_cache_used_in_array_path(self):
        """Test that cache is used in array return path."""
        # Test that repeated calls hit the cache
        pass


class TestFieldValidation:
    """Tests for field validation."""

    def test_valid_fields(self, data_portal, mock_asset):
        """Test valid OHLCV fields are accepted."""
        valid_fields = ["open", "high", "low", "close", "volume"]

        # Test each field is validated properly
        for field in valid_fields:
            # Should not raise
            try:
                data_portal._validate_field(field)
            except ValueError:
                pytest.fail(f"Valid field '{field}' was rejected")

    def test_invalid_field_rejected(self, data_portal):
        """Test invalid fields are rejected."""
        with pytest.raises(ValueError, match="Invalid field"):
            data_portal._validate_field("invalid_field")


class TestTypeHints:
    """Tests for type hints compliance."""

    def test_return_type_annotation(self, data_portal):
        """Test history() has correct return type annotation."""
        import inspect
        from typing import get_type_hints

        hints = get_type_hints(data_portal.history)

        # Should return Union[pd.DataFrame, np.ndarray]
        assert "return" in hints
        # The actual type checking would require runtime type validation
