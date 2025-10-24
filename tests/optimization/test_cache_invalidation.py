"""Unit tests for cache invalidation module.

Tests bundle version tracking, SHA256 hashing, and cache invalidation logic.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from rustybt.optimization.cache_invalidation import (
    BundleVersionMetadata,
    cache_invalidation_check,
    compare_bundle_versions,
    compute_bundle_hash,
    get_bundle_version,
)


class TestBundleVersionMetadata:
    """Test suite for BundleVersionMetadata dataclass."""

    def test_bundle_version_metadata_creation(self):
        """Test BundleVersionMetadata can be created."""
        metadata = BundleVersionMetadata(
            bundle_name="test_bundle",
            asset_list=["AAPL", "MSFT"],
            date_range=(datetime(2020, 1, 1), datetime(2023, 12, 31)),
            schema_version="v1",
            computed_hash="abc123" * 10 + "abcd",
        )

        assert metadata.bundle_name == "test_bundle"
        assert len(metadata.asset_list) == 2
        assert metadata.computed_hash == "abc123" * 10 + "abcd"


class TestComputeBundleHash:
    """Test suite for compute_bundle_hash() function."""

    def test_compute_bundle_hash_basic(self):
        """Test compute_bundle_hash produces 64-char SHA256 hash."""
        metadata = {
            "assets": ["AAPL", "MSFT", "GOOGL"],
            "date_range": (datetime(2020, 1, 1), datetime(2023, 12, 31)),
            "schema_version": "v1",
        }

        hash_result = compute_bundle_hash(metadata)

        # SHA256 produces 64-character hex string
        assert isinstance(hash_result, str)
        assert len(hash_result) == 64
        assert all(c in "0123456789abcdef" for c in hash_result)

    def test_compute_bundle_hash_deterministic(self):
        """Test compute_bundle_hash is deterministic (same input = same output)."""
        metadata = {
            "assets": ["AAPL", "MSFT"],
            "date_range": (datetime(2020, 1, 1), datetime(2023, 12, 31)),
            "schema_version": "v1",
        }

        hash1 = compute_bundle_hash(metadata)
        hash2 = compute_bundle_hash(metadata)

        assert hash1 == hash2

    def test_compute_bundle_hash_asset_order_independent(self):
        """Test compute_bundle_hash produces same hash regardless of asset order."""
        metadata1 = {
            "assets": ["AAPL", "MSFT", "GOOGL"],
            "date_range": (datetime(2020, 1, 1), datetime(2023, 12, 31)),
            "schema_version": "v1",
        }

        metadata2 = {
            "assets": ["GOOGL", "AAPL", "MSFT"],  # Different order
            "date_range": (datetime(2020, 1, 1), datetime(2023, 12, 31)),
            "schema_version": "v1",
        }

        hash1 = compute_bundle_hash(metadata1)
        hash2 = compute_bundle_hash(metadata2)

        # Hashes should be identical (assets are sorted internally)
        assert hash1 == hash2

    def test_compute_bundle_hash_changes_with_assets(self):
        """Test compute_bundle_hash changes when asset list changes."""
        metadata1 = {
            "assets": ["AAPL", "MSFT"],
            "date_range": (datetime(2020, 1, 1), datetime(2023, 12, 31)),
            "schema_version": "v1",
        }

        metadata2 = {
            "assets": ["AAPL", "MSFT", "GOOGL"],  # Added asset
            "date_range": (datetime(2020, 1, 1), datetime(2023, 12, 31)),
            "schema_version": "v1",
        }

        hash1 = compute_bundle_hash(metadata1)
        hash2 = compute_bundle_hash(metadata2)

        assert hash1 != hash2

    def test_compute_bundle_hash_changes_with_date_range(self):
        """Test compute_bundle_hash changes when date range changes."""
        metadata1 = {
            "assets": ["AAPL", "MSFT"],
            "date_range": (datetime(2020, 1, 1), datetime(2023, 12, 31)),
            "schema_version": "v1",
        }

        metadata2 = {
            "assets": ["AAPL", "MSFT"],
            "date_range": (datetime(2020, 1, 1), datetime(2024, 12, 31)),  # Different end
            "schema_version": "v1",
        }

        hash1 = compute_bundle_hash(metadata1)
        hash2 = compute_bundle_hash(metadata2)

        assert hash1 != hash2

    def test_compute_bundle_hash_changes_with_schema_version(self):
        """Test compute_bundle_hash changes when schema version changes."""
        metadata1 = {
            "assets": ["AAPL", "MSFT"],
            "date_range": (datetime(2020, 1, 1), datetime(2023, 12, 31)),
            "schema_version": "v1",
        }

        metadata2 = {
            "assets": ["AAPL", "MSFT"],
            "date_range": (datetime(2020, 1, 1), datetime(2023, 12, 31)),
            "schema_version": "v2",  # Different schema
        }

        hash1 = compute_bundle_hash(metadata1)
        hash2 = compute_bundle_hash(metadata2)

        assert hash1 != hash2

    def test_compute_bundle_hash_missing_keys_raises(self):
        """Test compute_bundle_hash raises ValueError if required keys missing."""
        metadata = {
            "assets": ["AAPL", "MSFT"],
            # Missing 'date_range' and 'schema_version'
        }

        with pytest.raises(ValueError, match="Bundle metadata missing required keys"):
            compute_bundle_hash(metadata)

    def test_compute_bundle_hash_assets_as_string(self):
        """Test compute_bundle_hash handles assets as comma-separated string."""
        metadata1 = {
            "assets": "AAPL,MSFT,GOOGL",  # String format
            "date_range": (datetime(2020, 1, 1), datetime(2023, 12, 31)),
            "schema_version": "v1",
        }

        metadata2 = {
            "assets": ["AAPL", "MSFT", "GOOGL"],  # List format
            "date_range": (datetime(2020, 1, 1), datetime(2023, 12, 31)),
            "schema_version": "v1",
        }

        hash1 = compute_bundle_hash(metadata1)
        hash2 = compute_bundle_hash(metadata2)

        # Should produce same hash regardless of format
        assert hash1 == hash2

    def test_compute_bundle_hash_date_range_as_string(self):
        """Test compute_bundle_hash handles date_range as string."""
        metadata = {
            "assets": ["AAPL", "MSFT"],
            "date_range": "2020-01-01|2023-12-31",  # String format
            "schema_version": "v1",
        }

        hash_result = compute_bundle_hash(metadata)

        # Should not raise, produces valid hash
        assert isinstance(hash_result, str)
        assert len(hash_result) == 64


class TestGetBundleVersion:
    """Test suite for get_bundle_version() function."""

    @patch("rustybt.data.bundles.core.load")
    def test_get_bundle_version_basic(self, mock_load):
        """Test get_bundle_version extracts bundle metadata and computes hash."""
        # Setup mock bundle
        mock_asset1 = MagicMock()
        mock_asset1.symbol = "AAPL"
        mock_asset1.start_date = datetime(2020, 1, 1)
        mock_asset1.end_date = datetime(2023, 12, 31)

        mock_asset2 = MagicMock()
        mock_asset2.symbol = "MSFT"
        mock_asset2.start_date = datetime(2020, 1, 1)
        mock_asset2.end_date = datetime(2023, 12, 31)

        mock_asset_finder = MagicMock()
        mock_asset_finder.retrieve_all.return_value = [mock_asset1, mock_asset2]

        mock_bundle = MagicMock()
        mock_bundle.asset_finder = mock_asset_finder
        mock_bundle.schema_version = "v1"
        mock_bundle.calendar = None

        mock_load.return_value = mock_bundle

        # Call get_bundle_version
        version = get_bundle_version("test_bundle")

        # Verify metadata extracted
        assert version.bundle_name == "test_bundle"
        assert len(version.asset_list) == 2
        assert "AAPL" in version.asset_list
        assert "MSFT" in version.asset_list
        assert version.schema_version == "v1"
        assert len(version.computed_hash) == 64

    @patch("rustybt.data.bundles.core.load")
    def test_get_bundle_version_bundle_not_found_raises(self, mock_load):
        """Test get_bundle_version raises ValueError if bundle not found."""
        mock_load.side_effect = Exception("Bundle not found")

        with pytest.raises(ValueError, match="Failed to load bundle"):
            get_bundle_version("nonexistent_bundle")

    @patch("rustybt.data.bundles.core.load")
    def test_get_bundle_version_fallback_date_range(self, mock_load):
        """Test get_bundle_version uses fallback date range if calendar unavailable."""

        # Setup mock asset without start_date/end_date attributes
        # Use spec to prevent MagicMock from creating these attributes
        class MockAsset:
            symbol = "AAPL"

        mock_asset1 = MockAsset()

        mock_asset_finder = MagicMock()
        mock_asset_finder.retrieve_all.return_value = [mock_asset1]

        mock_bundle = MagicMock()
        mock_bundle.asset_finder = mock_asset_finder
        mock_bundle.schema_version = "v1"
        mock_bundle.calendar = None

        mock_load.return_value = mock_bundle

        # Call get_bundle_version
        version = get_bundle_version("test_bundle")

        # Should use placeholder date range
        assert version.date_range == (datetime(2000, 1, 1), datetime(2099, 12, 31))


class TestCacheInvalidationCheck:
    """Test suite for cache_invalidation_check() function."""

    @patch("rustybt.optimization.cache_invalidation.get_bundle_version")
    def test_cache_invalidation_check_valid(self, mock_get_version):
        """Test cache_invalidation_check returns True when hash matches."""
        mock_version = BundleVersionMetadata(
            bundle_name="test_bundle",
            asset_list=["AAPL", "MSFT"],
            date_range=(datetime(2020, 1, 1), datetime(2023, 12, 31)),
            schema_version="v1",
            computed_hash="abc123" * 10 + "abcd",
        )
        mock_get_version.return_value = mock_version

        is_valid = cache_invalidation_check("test_bundle", "abc123" * 10 + "abcd")

        assert is_valid is True

    @patch("rustybt.optimization.cache_invalidation.get_bundle_version")
    def test_cache_invalidation_check_invalid(self, mock_get_version):
        """Test cache_invalidation_check returns False when hash differs."""
        mock_version = BundleVersionMetadata(
            bundle_name="test_bundle",
            asset_list=["AAPL", "MSFT"],
            date_range=(datetime(2020, 1, 1), datetime(2023, 12, 31)),
            schema_version="v1",
            computed_hash="abc123" * 10 + "abcd",
        )
        mock_get_version.return_value = mock_version

        is_valid = cache_invalidation_check("test_bundle", "def456" * 10 + "efgh")

        assert is_valid is False

    @patch("rustybt.optimization.cache_invalidation.get_bundle_version")
    def test_cache_invalidation_check_error_returns_false(self, mock_get_version):
        """Test cache_invalidation_check returns False on error (force refresh)."""
        mock_get_version.side_effect = Exception("Bundle error")

        is_valid = cache_invalidation_check("test_bundle", "abc123" * 10 + "abcd")

        # Should return False to force cache refresh on error
        assert is_valid is False


class TestCompareBundleVersions:
    """Test suite for compare_bundle_versions() function."""

    def test_compare_bundle_versions_equal(self):
        """Test compare_bundle_versions returns True for equal hashes."""
        result = compare_bundle_versions("test_bundle", "abc123", "abc123")

        assert result is True

    def test_compare_bundle_versions_not_equal(self):
        """Test compare_bundle_versions returns False for different hashes."""
        result = compare_bundle_versions("test_bundle", "abc123", "def456")

        assert result is False
