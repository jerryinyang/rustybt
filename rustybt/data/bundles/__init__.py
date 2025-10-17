# These imports are necessary to force module-scope register calls to happen.
import os
import sys
from contextlib import contextmanager


@contextmanager
def _suppress_git_stderr():
    """
    Suppress stderr output during imports to hide git warnings from dependencies.

    Some dependencies (bcolz, ccxt) try to detect their version from git during
    import, which fails with "fatal: bad revision 'HEAD'" when executed in a
    git repository without commits. This is a harmless warning that confuses users.

    This context manager temporarily redirects stderr to /dev/null during imports,
    preventing the git error from being displayed while still allowing the imports
    to succeed.
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
    """Lazy registration of deprecated adapter bundles."""
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
