"""
Fork-based shared bundle context for cross-worker bundle sharing.

This is a fork()-based implementation that avoids pickle serialization entirely.
Workers inherit bundle connections via copy-on-write memory, eliminating the
sqlite3.Connection pickle error that blocked the original implementation.

QA Re-evaluation (2025-10-23): Alternative 1 from re-evaluation guidance.

Key Advantages:
    - No pickle serialization needed (fork() inherits memory)
    - Faster worker startup (copy-on-write)
    - Simpler implementation
    - Works with non-picklable objects (sqlite3.Connection)

Platform Support:
    - Unix/Linux/macOS: ✅ Full support
    - Windows: ❌ Not supported (falls back to per-worker loading)

Constitutional requirements:
- CR-001: Decimal precision for financial data
- CR-004: Complete type hints
- CR-005: Zero-mock enforcement (real implementations only)
"""

import multiprocessing
import os
from typing import Optional

import structlog

from rustybt.data.bundles.core import BundleData, load

logger = structlog.get_logger()

# Platform detection
SUPPORTS_FORK = os.name != "nt"  # fork() not available on Windows

# Module-level bundle cache - inherited by workers via fork()
_BUNDLE_CACHE: dict[str, BundleData] = {}


class SharedBundleContextFork:
    """Fork-based shared bundle context (Unix/macOS/Linux only).

    Uses fork() multiprocessing to share bundle data across workers via
    copy-on-write memory. Workers inherit bundle connections directly,
    avoiding pickle serialization entirely.

    Performance expectations:
        - 13% expected improvement for optimization workflows
        - Zero serialization overhead
        - Faster worker startup vs spawn mode

    Platform Requirements:
        - Unix/Linux/macOS ONLY
        - Automatically detected via os.name check
        - Raises RuntimeError on Windows

    Example:
        >>> import multiprocessing
        >>> import os
        >>>
        >>> # Check platform support
        >>> if os.name != 'nt':
        ...     multiprocessing.set_start_method('fork', force=True)
        >>>
        >>> # Manager process: Initialize once
        >>> context = SharedBundleContextFork('mag-7')
        >>> context.initialize()
        >>>
        >>> # Workers automatically inherit bundle via fork()
        >>> bundle = context.get_bundle()
        >>> # Use bundle for backtesting
        >>>
        >>> # Manager: Cleanup when done
        >>> context.cleanup()

    Args:
        bundle_name: Name of bundle to share (e.g., 'mag-7', 'quandl')

    Raises:
        RuntimeError: If called on Windows (fork not supported)
        ValueError: If bundle_name is invalid
        FileNotFoundError: If bundle does not exist
    """

    def __init__(self, bundle_name: str):
        """Initialize fork-based shared bundle context.

        Args:
            bundle_name: Name of bundle to share

        Raises:
            RuntimeError: If platform doesn't support fork()
            ValueError: If bundle_name is empty
        """
        if not SUPPORTS_FORK:
            raise RuntimeError(
                "SharedBundleContextFork requires fork() multiprocessing, "
                "which is not available on Windows. "
                "Use spawn mode with per-worker bundle loading instead."
            )

        if not bundle_name:
            raise ValueError("bundle_name cannot be empty")

        self.bundle_name = bundle_name

        logger.info(
            "shared_bundle_context_fork_created",
            bundle_name=bundle_name,
            platform=os.name,
        )

    def initialize(self) -> None:
        """Initialize by loading bundle data in manager process.

        This MUST be called in the manager process BEFORE spawning workers.
        Workers will inherit the loaded bundle via fork().

        Raises:
            RuntimeError: If already initialized
            FileNotFoundError: If bundle does not exist
        """
        global _BUNDLE_CACHE

        if self.bundle_name in _BUNDLE_CACHE:
            raise RuntimeError("SharedBundleContextFork already initialized")

        logger.info("initializing_shared_bundle_fork", bundle_name=self.bundle_name)

        try:
            # Load bundle in manager process
            # Workers will inherit this module-level cache via copy-on-write
            bundle_data = load(self.bundle_name)
            _BUNDLE_CACHE[self.bundle_name] = bundle_data

            logger.info(
                "shared_bundle_fork_initialized",
                bundle_name=self.bundle_name,
                num_assets=len(bundle_data.asset_finder.sids),
            )

        except Exception as e:
            logger.error(
                "bundle_load_failed",
                bundle_name=self.bundle_name,
                error=str(e),
            )
            raise FileNotFoundError(f"Failed to load bundle '{self.bundle_name}': {e}") from e

    def get_bundle(self) -> BundleData:
        """Get bundle data (inherited from manager via fork()).

        Returns:
            BundleData instance

        Raises:
            RuntimeError: If not initialized
        """
        global _BUNDLE_CACHE

        if self.bundle_name not in _BUNDLE_CACHE:
            raise RuntimeError(
                "SharedBundleContextFork not initialized. "
                "Call initialize() in manager process before spawning workers."
            )

        return _BUNDLE_CACHE[self.bundle_name]

    def cleanup(self) -> None:
        """Cleanup bundle resources.

        Should be called by manager process when optimization is complete.
        """
        global _BUNDLE_CACHE

        if self.bundle_name in _BUNDLE_CACHE:
            logger.info(
                "cleaning_up_shared_bundle_fork",
                bundle_name=self.bundle_name,
            )

            # Remove from cache
            # Workers have their own copies after fork() so this is safe
            del _BUNDLE_CACHE[self.bundle_name]

            logger.info(
                "shared_bundle_fork_cleaned_up",
                bundle_name=self.bundle_name,
            )

    def is_initialized(self) -> bool:
        """Check if bundle is initialized.

        Returns:
            True if initialized, False otherwise
        """
        global _BUNDLE_CACHE
        return self.bundle_name in _BUNDLE_CACHE

    @staticmethod
    def set_fork_mode() -> bool:
        """Set multiprocessing to fork mode (must be called before any workers).

        Returns:
            True if fork mode set successfully, False if not supported

        Example:
            >>> if SharedBundleContextFork.set_fork_mode():
            ...     context = SharedBundleContextFork('mag-7')
            ...     context.initialize()
            ... else:
            ...     # Fall back to per-worker loading
            ...     pass
        """
        if not SUPPORTS_FORK:
            logger.warning(
                "fork_mode_not_supported",
                platform=os.name,
                message="fork() not available on this platform",
            )
            return False

        try:
            # Set start method to fork
            # force=True allows re-setting if already set
            multiprocessing.set_start_method("fork", force=True)

            logger.info(
                "multiprocessing_fork_mode_enabled",
                platform=os.name,
            )
            return True

        except Exception as e:
            logger.error(
                "fork_mode_failed",
                error=str(e),
            )
            return False

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup."""
        self.cleanup()
        return False


def create_shared_bundle_context(bundle_name: str) -> Optional[SharedBundleContextFork]:
    """Factory function to create fork-based shared bundle context if supported.

    Automatically detects platform and sets fork mode if available.

    Args:
        bundle_name: Name of bundle to share

    Returns:
        SharedBundleContextFork if fork supported, None otherwise

    Example:
        >>> context = create_shared_bundle_context('mag-7')
        >>> if context is not None:
        ...     context.initialize()
        ...     # Use context with workers
        ...     context.cleanup()
        ... else:
        ...     # Platform doesn't support fork, use per-worker loading
        ...     pass
    """
    if not SUPPORTS_FORK:
        logger.warning(
            "shared_bundle_context_fork_unavailable",
            platform=os.name,
            message="Fork mode not supported, will use per-worker bundle loading",
        )
        return None

    # Set fork mode
    if not SharedBundleContextFork.set_fork_mode():
        return None

    # Create and return context
    try:
        context = SharedBundleContextFork(bundle_name)
        return context
    except Exception as e:
        logger.error(
            "shared_bundle_context_fork_creation_failed",
            bundle_name=bundle_name,
            error=str(e),
        )
        return None
