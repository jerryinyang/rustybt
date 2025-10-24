"""
Tests for fork-based shared bundle context.

Constitutional requirements:
- CR-005: Zero-mock enforcement (real bundle data, real implementations)
"""

import multiprocessing
import os

import pytest

from rustybt.optimization.shared_bundle_context_fork import (
    SUPPORTS_FORK,
    SharedBundleContextFork,
    create_shared_bundle_context,
)

# Skip all tests on Windows
pytestmark = pytest.mark.skipif(not SUPPORTS_FORK, reason="Fork mode not supported on Windows")


@pytest.fixture(autouse=True)
def clear_bundle_cache():
    """Clear module-level bundle cache before each test."""
    import rustybt.optimization.shared_bundle_context_fork as fork_module

    fork_module._BUNDLE_CACHE.clear()
    yield
    fork_module._BUNDLE_CACHE.clear()


class TestSharedBundleContextFork:
    """Tests for SharedBundleContextFork."""

    def test_initialization(self):
        """Test basic initialization."""
        context = SharedBundleContextFork("mag-7")
        assert context.bundle_name == "mag-7"
        assert not context.is_initialized()

    def test_initialize_loads_bundle(self):
        """Test that initialize() loads bundle data."""
        context = SharedBundleContextFork("mag-7")
        context.initialize()

        assert context.is_initialized()
        bundle = context.get_bundle()
        assert bundle is not None
        assert len(bundle.asset_finder.sids) > 0

        context.cleanup()

    def test_get_bundle_before_initialize_raises(self):
        """Test that get_bundle() raises if not initialized."""
        context = SharedBundleContextFork("mag-7")

        with pytest.raises(RuntimeError, match="not initialized"):
            context.get_bundle()

    def test_initialize_twice_raises(self):
        """Test that initialize() can't be called twice."""
        context = SharedBundleContextFork("mag-7")
        context.initialize()

        with pytest.raises(RuntimeError, match="already initialized"):
            context.initialize()

        context.cleanup()

    def test_invalid_bundle_name_raises(self):
        """Test that empty bundle name raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            SharedBundleContextFork("")

    def test_nonexistent_bundle_raises(self):
        """Test that loading nonexistent bundle raises FileNotFoundError."""
        context = SharedBundleContextFork("nonexistent-bundle-xyz")

        with pytest.raises(FileNotFoundError):
            context.initialize()

    def test_cleanup(self):
        """Test cleanup releases resources."""
        context = SharedBundleContextFork("mag-7")
        context.initialize()

        assert context.is_initialized()

        context.cleanup()

        assert not context.is_initialized()
        with pytest.raises(RuntimeError):
            context.get_bundle()

    def test_context_manager(self):
        """Test context manager protocol."""
        with SharedBundleContextFork("mag-7") as context:
            context.initialize()
            assert context.is_initialized()
            bundle = context.get_bundle()
            assert bundle is not None

        # Should be cleaned up after exit
        assert not context.is_initialized()

    def test_set_fork_mode(self):
        """Test set_fork_mode() sets multiprocessing to fork."""
        result = SharedBundleContextFork.set_fork_mode()
        assert result is True

        # Verify fork mode is actually set
        # Note: This may fail if already set to different mode
        try:
            method = multiprocessing.get_start_method()
            assert method == "fork"
        except RuntimeError:
            # Already set, skip verification
            pass

    def test_functional_equivalence_single_worker(self):
        """Test that fork context returns same bundle as direct load."""
        # Direct load
        from rustybt.data.bundles.core import load

        direct_bundle = load("mag-7")

        # Fork context
        context = SharedBundleContextFork("mag-7")
        context.initialize()
        fork_bundle = context.get_bundle()

        # Compare key attributes
        assert len(fork_bundle.asset_finder.sids) == len(direct_bundle.asset_finder.sids)
        assert fork_bundle.equity_daily_bar_reader is not None
        assert direct_bundle.equity_daily_bar_reader is not None
        assert fork_bundle.asset_finder is not None
        assert direct_bundle.asset_finder is not None

        context.cleanup()


def worker_get_bundle(context_bundle_name: str, result_queue: multiprocessing.Queue):
    """Worker function to test bundle access in forked process.

    Args:
        context_bundle_name: Bundle name to verify
        result_queue: Queue to return result
    """
    try:
        # Worker should have inherited bundle via fork()
        # The module-level _BUNDLE_CACHE is inherited via copy-on-write
        # Create new context instance and access bundle
        context = SharedBundleContextFork(context_bundle_name)

        # Access bundle (should work because cache was inherited from parent)
        bundle = context.get_bundle()

        result_queue.put(
            {
                "success": True,
                "num_assets": len(bundle.asset_finder.sids),
                "has_bar_reader": bundle.equity_daily_bar_reader is not None,
            }
        )
    except Exception as e:
        result_queue.put(
            {
                "success": False,
                "error": str(e),
            }
        )


class TestSharedBundleContextForkMultiprocess:
    """Tests for fork context with actual multiprocessing."""

    def test_bundle_inherited_by_worker(self):
        """Test that workers inherit bundle via fork()."""
        # Set fork mode
        SharedBundleContextFork.set_fork_mode()

        # Initialize in manager process
        context = SharedBundleContextFork("mag-7")
        context.initialize()
        manager_bundle = context.get_bundle()

        # Spawn worker process (will fork)
        result_queue = multiprocessing.Queue()
        worker = multiprocessing.Process(target=worker_get_bundle, args=("mag-7", result_queue))
        worker.start()
        worker.join(timeout=10)

        # Check result
        assert not worker.is_alive(), "Worker process timed out"
        result = result_queue.get(timeout=1)

        assert result["success"] is True, f"Worker failed: {result.get('error')}"
        assert result["has_bar_reader"] is True
        assert result["num_assets"] == len(manager_bundle.asset_finder.sids)

        context.cleanup()

    def test_multiple_workers_share_bundle(self):
        """Test that multiple workers can access shared bundle."""
        # Set fork mode
        SharedBundleContextFork.set_fork_mode()

        # Initialize in manager
        context = SharedBundleContextFork("mag-7")
        context.initialize()

        # Spawn multiple workers
        n_workers = 4
        result_queue = multiprocessing.Queue()
        workers = []

        for _ in range(n_workers):
            worker = multiprocessing.Process(target=worker_get_bundle, args=("mag-7", result_queue))
            workers.append(worker)
            worker.start()

        # Wait for all workers
        for worker in workers:
            worker.join(timeout=10)
            assert not worker.is_alive(), "Worker process timed out"

        # Check all results
        for _ in range(n_workers):
            result = result_queue.get(timeout=1)
            assert result["success"] is True, f"Worker failed: {result.get('error')}"
            assert result["has_bar_reader"] is True
            assert result["num_assets"] > 0

        context.cleanup()


class TestCreateSharedBundleContext:
    """Tests for create_shared_bundle_context factory function."""

    def test_creates_context_on_supported_platform(self):
        """Test that factory creates context on Unix/Linux/macOS."""
        context = create_shared_bundle_context("mag-7")

        if SUPPORTS_FORK:
            assert context is not None
            assert isinstance(context, SharedBundleContextFork)
            assert context.bundle_name == "mag-7"
        else:
            assert context is None

    def test_returns_none_on_windows(self, monkeypatch):
        """Test that factory returns None on Windows."""
        # Simulate Windows platform
        monkeypatch.setattr("rustybt.optimization.shared_bundle_context_fork.SUPPORTS_FORK", False)

        context = create_shared_bundle_context("mag-7")
        assert context is None


class TestPlatformDetection:
    """Tests for platform detection."""

    def test_supports_fork_detection(self):
        """Test that SUPPORTS_FORK correctly detects platform."""
        if os.name == "nt":
            # Windows
            assert SUPPORTS_FORK is False
        else:
            # Unix/Linux/macOS
            assert SUPPORTS_FORK is True

    def test_windows_initialization_raises(self, monkeypatch):
        """Test that initializing on Windows raises RuntimeError."""
        # Simulate Windows
        monkeypatch.setattr("rustybt.optimization.shared_bundle_context_fork.SUPPORTS_FORK", False)

        with pytest.raises(RuntimeError, match="fork.*not available on Windows"):
            SharedBundleContextFork("mag-7")
