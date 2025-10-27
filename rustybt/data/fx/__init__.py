from typing import TYPE_CHECKING

from .base import DEFAULT_FX_RATE, FXRateReader
from .exploding import ExplodingFXRateReader
from .in_memory import InMemoryFXRateReader

# TYPE_CHECKING imports for static type checkers and IDEs
# These imports are only evaluated by type checkers (mypy, pyright, etc.)
# and IDEs for autocomplete/hints. They are NOT imported at runtime,
# preserving the lazy-loading behavior for optional h5py dependency.
if TYPE_CHECKING:
    from .hdf5 import HDF5FXRateReader, HDF5FXRateWriter


# Legacy HDF5 support - optional dependency (h5py)
# Import only when needed to avoid crashes if h5py is broken/missing
def __getattr__(name):
    if name in ("HDF5FXRateReader", "HDF5FXRateWriter"):
        try:
            from .hdf5 import HDF5FXRateReader, HDF5FXRateWriter

            return HDF5FXRateReader if name == "HDF5FXRateReader" else HDF5FXRateWriter
        except ImportError as e:
            raise ImportError(
                f"{name} requires h5py (legacy HDF5 support). "
                "RustyBT has migrated to Parquet format. "
                "Install h5py if you need legacy HDF5 support: pip install h5py"
            ) from e
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "DEFAULT_FX_RATE",
    "ExplodingFXRateReader",
    "FXRateReader",
    "HDF5FXRateReader",  # Lazy-loaded - requires h5py
    "HDF5FXRateWriter",  # Lazy-loaded - requires h5py
    "InMemoryFXRateReader",
]
