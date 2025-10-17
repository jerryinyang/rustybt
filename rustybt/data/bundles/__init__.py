# These imports are necessary to force module-scope register calls to happen.
from . import quandl  # noqa
from . import csvdir  # noqa


# Deferred import of adapter_bundles to avoid circular import
# (adapter_bundles imports from adapters, which imports from bundles)
# This is safe because adapter_bundles is deprecated and only registers
# profiling bundles used in performance tests.
def _register_adapter_bundles():
    """Lazy registration of deprecated adapter bundles."""
    try:
        from . import adapter_bundles  # noqa: F401
    except ImportError:
        pass


# Register adapter bundles by default for user convenience
# This makes yfinance-profiling and other free bundles available out-of-the-box
_register_adapter_bundles()


# Attempt to register profiling bundles if available (used by performance tests)
try:  # pragma: no cover - optional dependency for profiling scenarios
    import scripts.profiling.setup_profiling_data  # noqa: F401
except Exception:  # noqa: BLE001 - best-effort import
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
