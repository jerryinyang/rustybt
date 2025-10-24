"""Pytest configuration for optimization tests.

This module provides fixtures and configuration for optimization test suite,
ensuring proper test isolation by cleaning up global caches and state.
"""

import pytest


@pytest.fixture(autouse=True)
def clear_optimization_caches():
    """Clear global optimization caches and singletons before/after each test.

    This fixture ensures test isolation by resetting:
    1. @lru_cache on get_cached_assets()
    2. Global _global_data_cache singleton
    3. BundleConnectionPool singleton
    4. PersistentWorkerPool global instance
    5. Global _default_config singleton (OptimizationConfig)

    Without this cleanup, tests fail when run as part of full suite due to
    cache pollution from other tests.

    Yields:
        None: Cleanup happens after test execution
    """
    # Clear caches before test
    from rustybt.optimization.caching import clear_asset_cache, get_global_data_cache

    clear_asset_cache()
    cache = get_global_data_cache()
    cache.clear()

    # Clear bundle pool singleton (if it exists)
    from rustybt.optimization.bundle_pool import BundleConnectionPool

    if BundleConnectionPool._instance is not None:
        BundleConnectionPool._instance.force_invalidate()

    # Clear persistent worker pool singleton (if it exists)
    try:
        from rustybt.optimization.persistent_worker_pool import cleanup_global_pool

        cleanup_global_pool()
    except Exception:
        # Ignore cleanup errors - pool may not exist
        pass

    # Reset global config singleton
    import rustybt.optimization.config as config_module

    original_config = config_module._default_config
    config_module._default_config = None

    yield

    # Clear caches after test (cleanup)
    clear_asset_cache()
    cache = get_global_data_cache()
    cache.clear()

    # Clear bundle pool singleton
    if BundleConnectionPool._instance is not None:
        BundleConnectionPool._instance.force_invalidate()

    # Clear persistent worker pool singleton
    try:
        cleanup_global_pool()
    except Exception:
        # Ignore cleanup errors
        pass

    # Restore config singleton
    config_module._default_config = original_config
