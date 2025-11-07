"""Data bundle registration and management.

This module serves as the main entry point for the rustybt bundle system. It:
- Auto-registers built-in bundles (csvdir, quandl)
- Provides the core bundle API (register, ingest, load, clean)
- Handles lazy loading of optional adapter bundles
- Suppresses harmless git warnings from dependencies during import

The bundle system enables modular data ingestion from various sources
(CSV files, APIs, market data providers) into a unified format for backtesting.

Example:
    Basic bundle usage:

    >>> from rustybt.data.bundles import register, ingest, load
    >>>
    >>> # Ingest a built-in bundle
    >>> ingest('csvdir', show_progress=True)
    >>>
    >>> # Load bundle data for backtesting
    >>> bundle = load('csvdir')
    >>> assets = bundle.asset_finder.retrieve_all(bundle.asset_finder.sids)
    >>> bundle.close()

    Register a custom bundle:

    >>> @register('my-data')
    ... def my_ingest(environ, asset_db_writer, *args):
    ...     # Your ingestion logic
    ...     pass
    >>>
    >>> ingest('my-data')
"""
# These imports are necessary to force module-scope register calls to happen.
import os
import sys
from contextlib import contextmanager


@contextmanager
def _suppress_git_stderr():
    """Suppress stderr during imports to hide git warnings from dependencies.

    Some dependencies (bcolz, ccxt) attempt version detection via git during
    import, which generates harmless but confusing "fatal: bad revision 'HEAD'"
    warnings in repositories without commits.

    This context manager temporarily redirects stderr to /dev/null during imports,
    hiding git errors while allowing imports to succeed normally.

    Yields:
        None: Context where stderr is redirected to /dev/null.

    Example:
        >>> with _suppress_git_stderr():
        ...     import some_noisy_package  # Git warnings suppressed
    """
    stderr_fd = sys.stderr.fileno()
    # Save the original stderr file descriptor
    saved_stderr_fd = os.dup(stderr_fd)

    try:
        # Redirect stderr to /dev/null (Unix) or NUL (Windows)
        devnull = open(os.devnull, "w")
        os.dup2(devnull.fileno(), stderr_fd)
        devnull.close()
        yield
    finally:
        # Restore original stderr
        os.dup2(saved_stderr_fd, stderr_fd)
        os.close(saved_stderr_fd)


# Import bundles with suppressed git warnings from dependencies
with _suppress_git_stderr():
    from . import quandl  # noqa - May trigger git warning from bcolz
    from . import csvdir  # noqa


# Deferred import of adapter_bundles to avoid circular import
# (adapter_bundles imports from adapters, which imports from bundles)
# This is safe because adapter_bundles is deprecated and only registers
# profiling bundles used in performance tests.
def _register_adapter_bundles():
    """Lazy registration of deprecated adapter bundles.

    Imports and registers adapter-based bundles (yfinance, ccxt, etc.) on demand
    to avoid circular import issues. These bundles are deprecated in favor of
    the ingest-unified command but remain available for backward compatibility.

    Silently fails if adapter_bundles module is unavailable, making these bundles
    optional. Git warnings from dependencies (ccxt) are suppressed during import.

    Example:
        >>> _register_adapter_bundles()
        >>> # Now 'yfinance-profiling' and similar bundles are available
        >>> from rustybt.data.bundles import bundles
        >>> print('yfinance-profiling' in bundles)
        True
    """
    try:
        with _suppress_git_stderr():
            from . import adapter_bundles  # noqa: F401 - May trigger git warning from ccxt
    except ImportError:
        pass


# Register adapter bundles by default for user convenience
# This makes yfinance-profiling and other free bundles available out-of-the-box
_register_adapter_bundles()


# Attempt to register profiling bundles if available (used by performance tests)
try:  # pragma: no cover - optional dependency for profiling scenarios
    import scripts.profiling.setup_profiling_data  # noqa: F401
except (
    Exception
):  # noqa: BLE001 - best-effort import  # nosec B110 - intentional pass for optional import
    pass

from .core import (
    UnknownBundle,
    bundles,
    clean,
    from_bundle_ingest_dirname,
    ingest,
    ingestions_for_bundle,
    load,
    register,
    to_bundle_ingest_dirname,
    unregister,
)

__all__ = [
    "UnknownBundle",
    "bundles",
    "clean",
    "from_bundle_ingest_dirname",
    "ingest",
    "ingestions_for_bundle",
    "load",
    "register",
    "to_bundle_ingest_dirname",
    "unregister",
]
