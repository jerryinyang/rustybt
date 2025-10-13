"""Tests for data catalog and metadata management."""

import tempfile
import time
from pathlib import Path

import pandas as pd
import pytest
import sqlalchemy as sa

from rustybt.assets.asset_db_schema import ASSET_DB_VERSION, metadata
from rustybt.data.catalog import DataCatalog


@pytest.fixture
def temp_catalog_db():
    """Create temporary catalog database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    # Create tables
    engine = sa.create_engine(f"sqlite:///{db_path}")
    metadata.create_all(engine)
    engine.dispose()

    yield db_path

    # Cleanup
    Path(db_path).unlink()


class TestDataCatalog:
    """Test data catalog initialization and basic operations."""

    def test_catalog_initialization(self, temp_catalog_db):
        """Test catalog initialization with custom db path."""
        catalog = DataCatalog(db_path=temp_catalog_db)
        assert catalog.db_path == temp_catalog_db
        assert catalog.engine is not None

    def test_catalog_initialization_default_path(self):
        """Test catalog initialization with default path."""
        catalog = DataCatalog()
        assert catalog.db_path is not None
        assert f"assets-{ASSET_DB_VERSION}.db" in catalog.db_path


class TestMetadataStorage:
    """Test bundle metadata storage and retrieval."""

    def test_store_metadata(self, temp_catalog_db):
        """Test storing bundle metadata."""
        catalog = DataCatalog(db_path=temp_catalog_db)

        metadata_dict = {
            "bundle_name": "test_bundle",
            "source_type": "csv",
            "source_url": "/data/test.csv",
            "checksum": "a" * 64,
            "fetch_timestamp": int(time.time()),
        }

        catalog.store_metadata(metadata_dict)

        # Verify metadata was stored
        retrieved = catalog.get_bundle_metadata("test_bundle")
        assert retrieved is not None
        assert retrieved["bundle_name"] == "test_bundle"
        assert retrieved["source_type"] == "csv"
        assert retrieved["checksum"] == "a" * 64
        assert retrieved["file_checksum"] == "a" * 64
        assert retrieved["timezone"] == "UTC"

    def test_store_metadata_missing_required_fields(self, temp_catalog_db):
        """Test error handling for missing required fields."""
        catalog = DataCatalog(db_path=temp_catalog_db)

        incomplete_metadata = {
            "bundle_name": "test_bundle",
            # Missing source_type
        }

        with pytest.raises(ValueError, match="Missing required metadata fields"):
            catalog.store_metadata(incomplete_metadata)

    def test_store_metadata_without_optional_fields(self, temp_catalog_db):
        """Ensure optional provenance fields are not required."""
        catalog = DataCatalog(db_path=temp_catalog_db)

        metadata_dict = {
            "bundle_name": "minimal_bundle",
            "source_type": "csv",
        }

        catalog.store_metadata(metadata_dict)

        retrieved = catalog.get_bundle_metadata("minimal_bundle")
        assert retrieved is not None
        assert retrieved["source_type"] == "csv"
        assert retrieved["fetch_timestamp"] is not None

    def test_store_metadata_update_existing(self, temp_catalog_db):
        """Test updating existing bundle metadata."""
        catalog = DataCatalog(db_path=temp_catalog_db)

        # Store initial metadata
        initial_metadata = {
            "bundle_name": "test_bundle",
            "source_type": "csv",
            "source_url": "/data/test.csv",
            "checksum": "a" * 64,
            "fetch_timestamp": int(time.time()),
        }
        catalog.store_metadata(initial_metadata)

        # Update with new checksum
        updated_metadata = {
            "bundle_name": "test_bundle",
            "source_type": "csv",
            "source_url": "/data/test_updated.csv",
            "checksum": "b" * 64,
            "fetch_timestamp": int(time.time()),
            "file_size_bytes": 1024,
        }
        catalog.store_metadata(updated_metadata)

        # Verify update
        retrieved = catalog.get_bundle_metadata("test_bundle")
        assert retrieved["checksum"] == "b" * 64
        assert retrieved["file_checksum"] == "b" * 64
        assert retrieved["source_url"] == "/data/test_updated.csv"
        assert retrieved["file_size_bytes"] == 1024

    def test_get_bundle_metadata_not_found(self, temp_catalog_db):
        """Test retrieving metadata for non-existent bundle."""
        catalog = DataCatalog(db_path=temp_catalog_db)
        result = catalog.get_bundle_metadata("nonexistent_bundle")
        assert result is None

    def test_store_metadata_with_optional_fields(self, temp_catalog_db):
        """Test storing metadata with optional fields."""
        catalog = DataCatalog(db_path=temp_catalog_db)

        metadata_dict = {
            "bundle_name": "test_bundle",
            "source_type": "yfinance",
            "source_url": "https://api.yfinance.com",
            "api_version": "1.2.3",
            "data_version": "v2023.01",
            "checksum": "c" * 64,
            "fetch_timestamp": int(time.time()),
            "timezone": "America/New_York",
        }

        catalog.store_metadata(metadata_dict)

        retrieved = catalog.get_bundle_metadata("test_bundle")
        assert retrieved["api_version"] == "1.2.3"
        assert retrieved["data_version"] == "v2023.01"
        assert retrieved["timezone"] == "America/New_York"


class TestQualityMetricsStorage:
    """Test data quality metrics storage and retrieval."""

    def test_store_quality_metrics(self, temp_catalog_db):
        """Test storing quality metrics."""
        catalog = DataCatalog(db_path=temp_catalog_db)

        # Store bundle metadata first (foreign key requirement)
        catalog.store_metadata(
            {
                "bundle_name": "test_bundle",
                "source_type": "csv",
                "checksum": "a" * 64,
                "fetch_timestamp": int(time.time()),
            }
        )

        # Store quality metrics
        metrics = {
            "bundle_name": "test_bundle",
            "row_count": 1000,
            "start_date": int(pd.Timestamp("2023-01-01").timestamp()),
            "end_date": int(pd.Timestamp("2023-12-31").timestamp()),
            "missing_days_count": 5,
            "missing_days_list": ["2023-01-05", "2023-01-10"],
            "outlier_count": 3,
            "ohlcv_violations": 0,
            "validation_timestamp": int(time.time()),
            "validation_passed": True,
        }

        catalog.store_quality_metrics(metrics)

        # Verify metrics were stored
        retrieved = catalog.get_quality_metrics("test_bundle")
        assert retrieved is not None
        assert retrieved["row_count"] == 1000
        assert retrieved["missing_days_count"] == 5
        assert retrieved["missing_days_list"] == ["2023-01-05", "2023-01-10"]
        assert retrieved["validation_passed"] is True

    def test_store_quality_metrics_missing_required_fields(self, temp_catalog_db):
        """Test error handling for missing required fields."""
        catalog = DataCatalog(db_path=temp_catalog_db)

        incomplete_metrics = {
            "bundle_name": "test_bundle",
            "row_count": 1000,
            # Missing start_date, end_date, validation_timestamp
        }

        with pytest.raises(ValueError, match="Missing required quality metric fields"):
            catalog.store_quality_metrics(incomplete_metrics)

    def test_get_quality_metrics_most_recent(self, temp_catalog_db):
        """Test retrieving most recent quality metrics."""
        catalog = DataCatalog(db_path=temp_catalog_db)

        # Store bundle metadata
        catalog.store_metadata(
            {
                "bundle_name": "test_bundle",
                "source_type": "csv",
                "checksum": "a" * 64,
                "fetch_timestamp": int(time.time()),
            }
        )

        # Store multiple quality metric entries
        for i in range(3):
            metrics = {
                "bundle_name": "test_bundle",
                "row_count": 1000 + i,
                "start_date": int(pd.Timestamp("2023-01-01").timestamp()),
                "end_date": int(pd.Timestamp("2023-12-31").timestamp()),
                "validation_timestamp": int(time.time()) + i,
            }
            catalog.store_quality_metrics(metrics)
            time.sleep(0.01)  # Ensure different timestamps

        # Should retrieve most recent (row_count = 1002)
        retrieved = catalog.get_quality_metrics("test_bundle")
        assert retrieved["row_count"] == 1002

    def test_get_quality_metrics_not_found(self, temp_catalog_db):
        """Test retrieving metrics for non-existent bundle."""
        catalog = DataCatalog(db_path=temp_catalog_db)
        result = catalog.get_quality_metrics("nonexistent_bundle")
        assert result is None


class TestListBundles:
    """Test listing bundles with filtering."""

    def test_list_all_bundles(self, temp_catalog_db):
        """Test listing all bundles."""
        catalog = DataCatalog(db_path=temp_catalog_db)

        # Store multiple bundles
        for i in range(3):
            catalog.store_metadata(
                {
                    "bundle_name": f"bundle_{i}",
                    "source_type": "csv",
                    "checksum": "a" * 64,
                    "fetch_timestamp": int(time.time()),
                }
            )

            catalog.store_quality_metrics(
                {
                    "bundle_name": f"bundle_{i}",
                    "row_count": 1000 + i,
                    "start_date": int(pd.Timestamp("2023-01-01").timestamp()),
                    "end_date": int(pd.Timestamp("2023-12-31").timestamp()),
                    "validation_timestamp": int(time.time()),
                }
            )

        bundles = catalog.list_bundles()
        assert len(bundles) == 3
        assert all("row_count" in bundle for bundle in bundles)

    def test_list_bundles_filter_by_source_type(self, temp_catalog_db):
        """Test filtering bundles by source type."""
        catalog = DataCatalog(db_path=temp_catalog_db)

        # Store bundles with different source types
        catalog.store_metadata(
            {
                "bundle_name": "csv_bundle",
                "source_type": "csv",
                "checksum": "a" * 64,
                "fetch_timestamp": int(time.time()),
            }
        )

        catalog.store_metadata(
            {
                "bundle_name": "yfinance_bundle",
                "source_type": "yfinance",
                "checksum": "b" * 64,
                "fetch_timestamp": int(time.time()),
            }
        )

        bundles = catalog.list_bundles(source_type="csv")
        assert len(bundles) == 1
        assert bundles[0]["bundle_name"] == "csv_bundle"

    def test_list_bundles_filter_by_date_range(self, temp_catalog_db):
        """Test filtering bundles by date range."""
        catalog = DataCatalog(db_path=temp_catalog_db)

        # Store bundles with different date ranges
        catalog.store_metadata(
            {
                "bundle_name": "bundle_2023",
                "source_type": "csv",
                "checksum": "a" * 64,
                "fetch_timestamp": int(time.time()),
            }
        )

        catalog.store_quality_metrics(
            {
                "bundle_name": "bundle_2023",
                "row_count": 1000,
                "start_date": int(pd.Timestamp("2023-01-01").timestamp()),
                "end_date": int(pd.Timestamp("2023-12-31").timestamp()),
                "validation_timestamp": int(time.time()),
            }
        )

        catalog.store_metadata(
            {
                "bundle_name": "bundle_2024",
                "source_type": "csv",
                "checksum": "b" * 64,
                "fetch_timestamp": int(time.time()),
            }
        )

        catalog.store_quality_metrics(
            {
                "bundle_name": "bundle_2024",
                "row_count": 1000,
                "start_date": int(pd.Timestamp("2024-01-01").timestamp()),
                "end_date": int(pd.Timestamp("2024-12-31").timestamp()),
                "validation_timestamp": int(time.time()),
            }
        )

        # Filter for bundles with data in 2023
        bundles = catalog.list_bundles(
            start_date=int(pd.Timestamp("2023-01-01").timestamp()),
            end_date=int(pd.Timestamp("2023-12-31").timestamp()),
        )

        assert len(bundles) == 1
        assert bundles[0]["bundle_name"] == "bundle_2023"


class TestDeleteMetadata:
    """Test deleting bundle metadata."""

    def test_delete_bundle_metadata(self, temp_catalog_db):
        """Test deleting bundle and associated quality metrics."""
        catalog = DataCatalog(db_path=temp_catalog_db)

        # Store bundle and metrics
        catalog.store_metadata(
            {
                "bundle_name": "test_bundle",
                "source_type": "csv",
                "checksum": "a" * 64,
                "fetch_timestamp": int(time.time()),
            }
        )

        catalog.store_quality_metrics(
            {
                "bundle_name": "test_bundle",
                "row_count": 1000,
                "start_date": int(pd.Timestamp("2023-01-01").timestamp()),
                "end_date": int(pd.Timestamp("2023-12-31").timestamp()),
                "validation_timestamp": int(time.time()),
            }
        )

        # Delete bundle
        result = catalog.delete_bundle_metadata("test_bundle")
        assert result is True

        # Verify deletion
        assert catalog.get_bundle_metadata("test_bundle") is None
        assert catalog.get_quality_metrics("test_bundle") is None

    def test_delete_nonexistent_bundle(self, temp_catalog_db):
        """Test deleting non-existent bundle."""
        catalog = DataCatalog(db_path=temp_catalog_db)
        result = catalog.delete_bundle_metadata("nonexistent_bundle")
        assert result is False


@pytest.mark.integration
class TestBundleIngestionIntegration:
    """Integration tests for end-to-end bundle ingestion with metadata tracking."""

    def test_csv_bundle_ingestion_with_metadata(self, temp_catalog_db, tmp_path):
        """Integration test: CSV bundle ingestion records metadata and quality metrics."""
        from exchange_calendars import get_calendar

        from rustybt.data.metadata_tracker import BundleMetadataTracker

        # Create test CSV data
        csv_dir = tmp_path / "test_bundle"
        csv_dir.mkdir()

        csv_file = csv_dir / "TEST.csv"
        test_data = """date,open,high,low,close,volume
2023-01-03,100.0,105.0,98.0,102.0,1000
2023-01-04,102.0,106.0,99.0,103.0,1100
2023-01-05,103.0,107.0,100.0,104.0,1200
2023-01-06,104.0,108.0,101.0,105.0,1300
2023-01-09,105.0,109.0,102.0,106.0,1400
"""
        csv_file.write_text(test_data)

        # Load data for quality analysis
        import polars as pl

        data = pl.read_csv(str(csv_file))
        data = data.with_columns(pl.col("date").str.to_datetime())

        # Initialize tracker with test catalog
        tracker = BundleMetadataTracker(catalog=DataCatalog(db_path=temp_catalog_db))
        nyse_calendar = get_calendar("NYSE")

        # Record bundle ingestion
        result = tracker.record_csv_bundle(
            bundle_name="test_integration_bundle",
            csv_dir=csv_dir,
            data=data,
            calendar=nyse_calendar,
        )

        # Verify metadata was recorded
        assert result["metadata"] is not None
        assert result["quality_metrics"] is not None

        metadata = result["metadata"]
        assert metadata["bundle_name"] == "test_integration_bundle"
        assert metadata["source_type"] == "csv"
        assert metadata["source_url"] == str(csv_dir)
        assert len(metadata["checksum"]) == 64  # SHA256 length
        assert metadata["timezone"] == "UTC"

        # Verify quality metrics were calculated
        quality = result["quality_metrics"]
        assert quality["row_count"] == 5
        assert quality["ohlcv_violations"] == 0
        assert quality["validation_passed"] is True

        # Verify data is queryable via catalog API
        catalog = DataCatalog(db_path=temp_catalog_db)

        retrieved_metadata = catalog.get_bundle_metadata("test_integration_bundle")
        assert retrieved_metadata is not None
        assert retrieved_metadata["bundle_name"] == "test_integration_bundle"
        assert retrieved_metadata["checksum"] == metadata["checksum"]

        retrieved_quality = catalog.get_quality_metrics("test_integration_bundle")
        assert retrieved_quality is not None
        assert retrieved_quality["row_count"] == 5
        assert retrieved_quality["validation_passed"] is True

        # Verify bundle appears in list
        bundles = catalog.list_bundles()
        assert len(bundles) == 1
        assert bundles[0]["bundle_name"] == "test_integration_bundle"

    def test_csv_bundle_with_data_quality_issues(self, temp_catalog_db, tmp_path):
        """Integration test: Bundle with OHLCV violations properly detected."""
        from rustybt.data.metadata_tracker import BundleMetadataTracker

        # Create CSV with OHLCV violations
        csv_dir = tmp_path / "bad_bundle"
        csv_dir.mkdir()

        csv_file = csv_dir / "BAD.csv"
        bad_data = """date,open,high,low,close,volume
2023-01-03,100.0,95.0,98.0,102.0,1000
2023-01-04,102.0,106.0,99.0,103.0,1100
"""
        csv_file.write_text(bad_data)

        # Load data
        import polars as pl

        data = pl.read_csv(str(csv_file))
        data = data.with_columns(pl.col("date").str.to_datetime())

        # Record bundle
        tracker = BundleMetadataTracker(catalog=DataCatalog(db_path=temp_catalog_db))
        result = tracker.record_csv_bundle(
            bundle_name="bad_bundle", csv_dir=csv_dir, data=data, calendar=None
        )

        # Verify violation detected
        quality = result["quality_metrics"]
        assert quality["ohlcv_violations"] == 1  # First row has high < open
        assert quality["validation_passed"] is False

        # Verify queryable
        catalog = DataCatalog(db_path=temp_catalog_db)
        retrieved_quality = catalog.get_quality_metrics("bad_bundle")
        assert retrieved_quality["validation_passed"] is False
