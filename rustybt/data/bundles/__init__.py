# These imports are necessary to force module-scope register calls to happen.
from . import quandl  # noqa
from . import csvdir  # noqa
from . import adapter_bundles  # noqa

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
