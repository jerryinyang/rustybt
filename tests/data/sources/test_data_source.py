"""Unit tests for DataSource interface and adapters."""

import pytest

from rustybt.data.sources.base import DataSource, DataSourceMetadata
from rustybt.data.sources.registry import DataSourceRegistry


class TestDataSourceInterface:
    """Test DataSource interface compliance across all adapters."""

    @pytest.fixture
    def adapter_classes(self):
        """Return all adapter classes that should implement DataSource."""
        import os

        from rustybt.data.adapters.ccxt_adapter import CCXTAdapter
        from rustybt.data.adapters.csv_adapter import CSVAdapter
        from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

        # Always include adapters that don't require API keys
        adapters = [YFinanceAdapter, CCXTAdapter, CSVAdapter]

        # Only include API-key-required adapters if keys are available
        try:
            if os.environ.get("POLYGON_API_KEY"):
                from rustybt.data.adapters.polygon_adapter import PolygonAdapter

                adapters.append(PolygonAdapter)
        except ImportError:
            pass

        try:
            if os.environ.get("ALPACA_API_KEY"):
                from rustybt.data.adapters.alpaca_adapter import AlpacaAdapter

                adapters.append(AlpacaAdapter)
        except ImportError:
            pass

        try:
            if os.environ.get("ALPHAVANTAGE_API_KEY"):
                from rustybt.data.adapters.alphavantage_adapter import AlphaVantageAdapter

                adapters.append(AlphaVantageAdapter)
        except ImportError:
            pass

        return adapters

    def test_datasource_interface_compliance(self, adapter_classes):
        """All adapters must implement DataSource interface."""
        for adapter_class in adapter_classes:
            assert issubclass(
                adapter_class, DataSource
            ), f"{adapter_class.__name__} must inherit from DataSource"

            # Check all required methods exist
            assert hasattr(
                adapter_class, "fetch"
            ), f"{adapter_class.__name__} missing fetch() method"
            assert hasattr(
                adapter_class, "ingest_to_bundle"
            ), f"{adapter_class.__name__} missing ingest_to_bundle() method"
            assert hasattr(
                adapter_class, "get_metadata"
            ), f"{adapter_class.__name__} missing get_metadata() method"
            assert hasattr(
                adapter_class, "supports_live"
            ), f"{adapter_class.__name__} missing supports_live() method"

    def test_metadata_structure(self, adapter_classes):
        """All adapters return valid DataSourceMetadata."""
        for adapter_class in adapter_classes:
            # Create minimal instance (may fail for some adapters without config)
            try:
                if adapter_class.__name__ == "CCXTAdapter":
                    adapter = adapter_class(exchange_id="binance")
                elif adapter_class.__name__ == "CSVAdapter":
                    # CSV adapter expects CSVConfig object
                    import tempfile

                    from rustybt.data.adapters.csv_adapter import CSVConfig, SchemaMapping

                    temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
                    temp_file.write("date,open,high,low,close,volume\n")
                    temp_file.close()
                    config = CSVConfig(file_path=temp_file.name, schema_mapping=SchemaMapping())
                    adapter = adapter_class(config)
                else:
                    adapter = adapter_class()

                metadata = adapter.get_metadata()

                # Verify metadata is correct type
                assert isinstance(
                    metadata, DataSourceMetadata
                ), f"{adapter_class.__name__}.get_metadata() must return DataSourceMetadata"

                # Verify required fields are populated
                assert metadata.source_type, "source_type must be non-empty"
                assert metadata.source_url, "source_url must be non-empty"
                # api_version can be None for some adapters (like CCXT when exchange doesn't expose it)
                assert isinstance(metadata.supports_live, bool), "supports_live must be bool"

                # Verify supported_frequencies is a list
                assert isinstance(
                    metadata.supported_frequencies, list
                ), "supported_frequencies must be a list"

            except (ImportError, AttributeError) as e:
                pytest.skip(f"Cannot test {adapter_class.__name__}: {e}")

    def test_supports_live_consistency(self, adapter_classes):
        """supports_live() must match metadata.supports_live."""
        for adapter_class in adapter_classes:
            try:
                if adapter_class.__name__ == "CCXTAdapter":
                    adapter = adapter_class(exchange_id="binance")
                elif adapter_class.__name__ == "CSVAdapter":
                    import tempfile

                    from rustybt.data.adapters.csv_adapter import CSVConfig, SchemaMapping

                    temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
                    temp_file.write("date,open,high,low,close,volume\n")
                    temp_file.close()
                    config = CSVConfig(file_path=temp_file.name, schema_mapping=SchemaMapping())
                    adapter = adapter_class(config)
                else:
                    adapter = adapter_class()

                metadata = adapter.get_metadata()
                supports_live = adapter.supports_live()

                assert metadata.supports_live == supports_live, (
                    f"{adapter_class.__name__}: metadata.supports_live ({metadata.supports_live}) "
                    f"must match supports_live() ({supports_live})"
                )

            except (ImportError, AttributeError):
                pytest.skip(f"Cannot test {adapter_class.__name__}")

    def test_backwards_compatibility(self):
        """Old adapter APIs still work (fetch_ohlcv)."""
        from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

        adapter = YFinanceAdapter()

        # Verify fetch_ohlcv method exists for backwards compatibility
        assert hasattr(
            adapter, "fetch_ohlcv"
        ), "YFinanceAdapter must have fetch_ohlcv() for backwards compatibility"

        # Verify it's a callable method
        assert callable(adapter.fetch_ohlcv), "fetch_ohlcv must be callable"


class TestDataSourceRegistry:
    """Test DataSourceRegistry discovery and factory methods."""

    def test_registry_discovery(self):
        """Registry auto-discovers all sources."""
        sources = DataSourceRegistry.list_sources()

        # At minimum, should have yfinance, ccxt, csv
        assert "yfinance" in sources, "Registry must discover YFinanceAdapter"
        assert "ccxt" in sources, "Registry must discover CCXTAdapter"
        assert "csv" in sources, "Registry must discover CSVAdapter"

        # Should have at least 3 sources
        assert len(sources) >= 3, f"Expected at least 3 sources, got {len(sources)}"

    def test_registry_factory(self):
        """Registry creates source instances correctly."""
        # Test YFinance source creation
        source = DataSourceRegistry.get_source("yfinance")

        assert source is not None, "get_source() must return instance"
        assert isinstance(source, DataSource), "Instance must implement DataSource"

        from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

        assert isinstance(
            source, YFinanceAdapter
        ), "get_source('yfinance') must return YFinanceAdapter instance"

    def test_registry_factory_with_config(self):
        """Registry passes configuration to adapter constructors."""
        source = DataSourceRegistry.get_source("ccxt", exchange_id="binance")

        assert source is not None
        assert hasattr(source, "exchange_id")
        assert (
            source.exchange_id == "binance"
        ), "Configuration must be passed to adapter constructor"

    def test_registry_unknown_source(self):
        """Registry raises ValueError for unknown sources."""
        with pytest.raises(ValueError, match="Unknown data source"):
            DataSourceRegistry.get_source("nonexistent_source")

    def test_get_source_info(self):
        """get_source_info() returns metadata dict."""
        info = DataSourceRegistry.get_source_info("yfinance")

        # Verify required keys exist
        assert "name" in info
        assert "class_name" in info
        assert "source_type" in info
        assert "supports_live" in info
        assert "metadata" in info

        # Verify values
        assert info["name"] == "yfinance"
        assert info["source_type"] == "yfinance"
        assert info["supports_live"] is False  # YFinance doesn't support live

    def test_get_source_info_unknown_source(self):
        """get_source_info() raises ValueError for unknown sources."""
        with pytest.raises(ValueError, match="Unknown data source"):
            DataSourceRegistry.get_source_info("nonexistent_source")


class TestDataSourceLiveSupport:
    """Test that adapters correctly report live streaming support."""

    def test_yfinance_no_live(self):
        """YFinance does not support live streaming."""
        from rustybt.data.adapters.yfinance_adapter import YFinanceAdapter

        adapter = YFinanceAdapter()
        assert adapter.supports_live() is False, "YFinance has 15-minute delay, not live"

    def test_ccxt_supports_live(self):
        """CCXT supports live streaming."""
        from rustybt.data.adapters.ccxt_adapter import CCXTAdapter

        adapter = CCXTAdapter(exchange_id="binance")
        assert adapter.supports_live() is True, "CCXT supports WebSocket streaming"

    def test_csv_no_live(self):
        """CSV adapter does not support live streaming."""
        import tempfile

        from rustybt.data.adapters.csv_adapter import CSVAdapter, CSVConfig, SchemaMapping

        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
        temp_file.write("date,open,high,low,close,volume\n")
        temp_file.close()
        config = CSVConfig(file_path=temp_file.name, schema_mapping=SchemaMapping())
        adapter = CSVAdapter(config)
        assert adapter.supports_live() is False, "CSV is static file data, not live"

    def test_polygon_supports_live(self):
        """Polygon supports live streaming."""
        import os

        # Skip if API key not available (CI/CD environments)
        if not os.environ.get("POLYGON_API_KEY"):
            pytest.skip("POLYGON_API_KEY not set - skipping Polygon adapter test")

        try:
            from rustybt.data.adapters.polygon_adapter import PolygonAdapter

            # Use DataSourceRegistry to avoid constructor issues
            source = DataSourceRegistry.get_source("polygon")
            assert source.supports_live() is True, "Polygon supports WebSocket streaming"
        except (ImportError, ValueError) as e:
            pytest.skip(f"Polygon adapter not available: {e}")

    def test_alpaca_supports_live(self):
        """Alpaca supports live streaming."""
        import os

        # Skip if API key not available (CI/CD environments)
        if not os.environ.get("ALPACA_API_KEY"):
            pytest.skip("ALPACA_API_KEY not set - skipping Alpaca adapter test")

        try:
            from rustybt.data.adapters.alpaca_adapter import AlpacaAdapter

            # Use DataSourceRegistry to avoid constructor issues
            source = DataSourceRegistry.get_source("alpaca")
            assert source.supports_live() is True, "Alpaca supports WebSocket streaming"
        except (ImportError, ValueError, TypeError) as e:
            pytest.skip(f"Alpaca adapter not available: {e}")


class TestDataSourceMetadata:
    """Test DataSourceMetadata dataclass."""

    def test_metadata_creation(self):
        """DataSourceMetadata can be created with valid data."""
        metadata = DataSourceMetadata(
            source_type="test",
            source_url="https://test.com",
            api_version="v1",
            supports_live=True,
            rate_limit=100,
            auth_required=True,
            data_delay=0,
            supported_frequencies=["1m", "1h", "1d"],
            additional_info={"test": "data"},
        )

        assert metadata.source_type == "test"
        assert metadata.supports_live is True
        assert metadata.rate_limit == 100

    def test_metadata_immutable(self):
        """DataSourceMetadata is immutable (frozen dataclass)."""
        metadata = DataSourceMetadata(
            source_type="test",
            source_url="https://test.com",
            api_version="v1",
            supports_live=False,
        )

        with pytest.raises(AttributeError):
            metadata.source_type = "modified"
