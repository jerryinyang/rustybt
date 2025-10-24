"""Bundle version tracking and cache invalidation.

This module provides SHA256-based bundle versioning for cache invalidation.
When bundle metadata changes (assets, date range, schema), the hash changes
and cached data is automatically invalidated.

Constitutional requirements:
- CR-004: Complete type hints
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import List, Tuple

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class BundleVersionMetadata:
    """Bundle version metadata for cache invalidation.

    This dataclass stores bundle metadata and computed SHA256 hash.
    When metadata changes, hash changes, invalidating cached data.

    Attributes:
        bundle_name: Name of the bundle
        asset_list: List of asset symbols in bundle
        date_range: Tuple of (start_date, end_date)
        schema_version: Bundle schema version string
        computed_hash: SHA256 hash of metadata

    Example:
        >>> from datetime import datetime
        >>> metadata = BundleVersionMetadata(
        ...     bundle_name='quandl',
        ...     asset_list=['AAPL', 'MSFT'],
        ...     date_range=(datetime(2020, 1, 1), datetime(2023, 12, 31)),
        ...     schema_version='v1',
        ...     computed_hash='abc123...'
        ... )
    """

    bundle_name: str
    asset_list: List[str]
    date_range: Tuple[datetime, datetime]
    schema_version: str
    computed_hash: str


def compute_bundle_hash(bundle_metadata: dict) -> str:
    """Compute SHA256 hash of bundle metadata.

    This function creates a deterministic hash from bundle metadata.
    Hash changes when assets, date range, or schema version changes.

    Hash input format:
        "{sorted_assets}|{start_date}|{end_date}|{schema_version}"

    Args:
        bundle_metadata: Dictionary with keys:
            - assets: List[str] or str (comma-separated)
            - date_range: Tuple[datetime, datetime] or str
            - schema_version: str

    Returns:
        SHA256 hash as hex string (64 characters)

    Raises:
        ValueError: If required metadata keys missing
        TypeError: If metadata values have wrong types

    Example:
        >>> metadata = {
        ...     'assets': ['AAPL', 'MSFT', 'GOOGL'],
        ...     'date_range': (datetime(2020, 1, 1), datetime(2023, 12, 31)),
        ...     'schema_version': 'v1'
        ... }
        >>> hash1 = compute_bundle_hash(metadata)
        >>> print(len(hash1))
        64
        >>> # Changing assets changes hash
        >>> metadata['assets'].append('TSLA')
        >>> hash2 = compute_bundle_hash(metadata)
        >>> assert hash1 != hash2
    """
    # Validate required keys
    required_keys = ["assets", "date_range", "schema_version"]
    missing_keys = [key for key in required_keys if key not in bundle_metadata]
    if missing_keys:
        raise ValueError(f"Bundle metadata missing required keys: {missing_keys}")

    # Extract and normalize assets
    assets = bundle_metadata["assets"]
    if isinstance(assets, str):
        # Parse comma-separated string
        asset_list = [a.strip() for a in assets.split(",")]
    elif isinstance(assets, list):
        asset_list = list(assets)
    else:
        raise TypeError(f"Expected assets to be str or list, got {type(assets)}")

    # Sort assets for deterministic hash
    sorted_assets = sorted(asset_list)
    assets_str = ",".join(sorted_assets)

    # Extract and normalize date range
    date_range = bundle_metadata["date_range"]
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        if isinstance(start_date, datetime) and isinstance(end_date, datetime):
            date_range_str = f"{start_date.isoformat()}|{end_date.isoformat()}"
        else:
            # Try to convert to string
            date_range_str = f"{str(start_date)}|{str(end_date)}"
    elif isinstance(date_range, str):
        date_range_str = date_range
    else:
        raise TypeError(
            f"Expected date_range to be tuple[datetime, datetime] or str, "
            f"got {type(date_range)}"
        )

    # Extract schema version
    schema_version = str(bundle_metadata["schema_version"])

    # Create deterministic hash input
    hash_input = f"{assets_str}|{date_range_str}|{schema_version}"

    # Compute SHA256 hash
    hash_bytes = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

    logger.debug(
        "bundle_hash_computed",
        bundle_name=bundle_metadata.get("bundle_name", "unknown"),
        num_assets=len(sorted_assets),
        hash_input_length=len(hash_input),
        hash_result=hash_bytes[:16],
    )

    return hash_bytes


def get_bundle_version(bundle_name: str) -> BundleVersionMetadata:
    """Extract bundle version metadata and compute hash.

    This function loads bundle metadata (asset list, date range, schema version)
    and computes SHA256 hash for cache invalidation.

    Args:
        bundle_name: Name of the bundle to load

    Returns:
        BundleVersionMetadata with computed hash

    Raises:
        ValueError: If bundle not found or metadata incomplete

    Example:
        >>> version = get_bundle_version('quandl')
        >>> print(f"Bundle hash: {version.computed_hash[:16]}...")
        >>> print(f"Assets: {len(version.asset_list)}")
    """
    # Import here to avoid circular dependency
    from rustybt.data.bundles.core import load

    try:
        bundle = load(bundle_name)
    except Exception as e:
        raise ValueError(f"Failed to load bundle '{bundle_name}': {e}") from e

    # Extract asset list
    asset_finder = bundle.asset_finder
    all_sids = list(asset_finder.sids)
    all_assets = asset_finder.retrieve_all(all_sids)
    asset_list = sorted([asset.symbol for asset in all_assets])

    # Extract date range
    try:
        # Try to get date range from bundle
        calendar = getattr(bundle, "calendar", None)
        if calendar is not None:
            first_session = calendar.first_session
            last_session = calendar.last_session
            date_range = (first_session, last_session)
        else:
            # Fallback: use min/max dates from asset dates
            if all_assets:
                start_dates = [a.start_date for a in all_assets if hasattr(a, "start_date")]
                end_dates = [a.end_date for a in all_assets if hasattr(a, "end_date")]
                if start_dates and end_dates:
                    date_range = (min(start_dates), max(end_dates))
                else:
                    # Use placeholder if no date info available
                    date_range = (datetime(2000, 1, 1), datetime(2099, 12, 31))
            else:
                date_range = (datetime(2000, 1, 1), datetime(2099, 12, 31))
    except Exception as e:
        logger.warning("failed_to_extract_date_range", bundle_name=bundle_name, error=str(e))
        # Use placeholder date range
        date_range = (datetime(2000, 1, 1), datetime(2099, 12, 31))

    # Extract schema version (use placeholder if not available)
    schema_version = getattr(bundle, "schema_version", "v1")

    # Compute hash
    metadata_dict = {
        "assets": asset_list,
        "date_range": date_range,
        "schema_version": schema_version,
        "bundle_name": bundle_name,
    }
    bundle_hash = compute_bundle_hash(metadata_dict)

    return BundleVersionMetadata(
        bundle_name=bundle_name,
        asset_list=asset_list,
        date_range=date_range,
        schema_version=schema_version,
        computed_hash=bundle_hash,
    )


def cache_invalidation_check(bundle_name: str, cached_hash: str) -> bool:
    """Check if cached data is still valid for bundle.

    Compares cached hash with current bundle hash. If hashes differ,
    bundle has been updated and cache should be invalidated.

    Args:
        bundle_name: Name of the bundle
        cached_hash: Previously cached bundle hash

    Returns:
        True if cache valid (hashes match), False if invalidated (hashes differ)

    Example:
        >>> cached_hash = 'abc123...'
        >>> is_valid = cache_invalidation_check('quandl', cached_hash)
        >>> if not is_valid:
        ...     print("Cache invalidated, reload data")
    """
    try:
        current_version = get_bundle_version(bundle_name)
        is_valid = current_version.computed_hash == cached_hash

        if is_valid:
            logger.debug(
                "cache_valid",
                bundle_name=bundle_name,
                cached_hash=cached_hash[:16],
            )
        else:
            logger.info(
                "cache_invalidated",
                bundle_name=bundle_name,
                cached_hash=cached_hash[:16],
                current_hash=current_version.computed_hash[:16],
            )

        return is_valid

    except Exception as e:
        logger.error(
            "cache_invalidation_check_failed",
            bundle_name=bundle_name,
            error=str(e),
        )
        # On error, assume cache invalid to force refresh
        return False


def compare_bundle_versions(bundle_name: str, hash1: str, hash2: str) -> bool:
    """Compare two bundle version hashes for equality.

    This is a simple equality check with logging for debugging.

    Args:
        bundle_name: Name of the bundle (for logging)
        hash1: First hash to compare
        hash2: Second hash to compare

    Returns:
        True if hashes match, False otherwise

    Example:
        >>> same = compare_bundle_versions('quandl', 'abc123', 'abc123')
        >>> print(same)
        True
    """
    is_same = hash1 == hash2

    logger.debug(
        "bundle_version_comparison",
        bundle_name=bundle_name,
        hash1=hash1[:16],
        hash2=hash2[:16],
        is_same=is_same,
    )

    return is_same
