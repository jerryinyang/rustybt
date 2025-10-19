"""
Canonical path locations for zipline data.

Paths are rooted at $ZIPLINE_ROOT if that environment variable is set.
Otherwise default to expanduser(~/.zipline)
"""

import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import structlog

logger = structlog.get_logger()


def hidden(path: str) -> bool:
    """Check if a path is hidden.

    Parameters
    ----------
    path : str
        A filepath.
    """
    # return os.path.split(path)[1].startswith(".")
    return Path(path).stem.startswith(".")


def ensure_directory(path: str) -> None:
    """Ensure that a directory named "path" exists."""
    Path(path).mkdir(parents=True, exist_ok=True)


def ensure_directory_containing(path: str) -> None:
    """Ensure that the directory containing `path` exists.

    This is just a convenience wrapper for doing::

        ensure_directory(os.path.dirname(path))
    """
    ensure_directory(str(Path(path).parent))


def ensure_file(path: str) -> None:
    """Ensure that a file exists. This will create any parent directories needed
    and create an empty file if it does not exist.

    Parameters
    ----------
    path : str
        The file path to ensure exists.
    """
    ensure_directory_containing(path)
    Path(path).touch(exist_ok=True)


def last_modified_time(path: str) -> pd.Timestamp:
    """Get the last modified time of path as a Timestamp."""
    return pd.Timestamp(Path(path).stat().st_mtime, unit="s", tz="UTC")


def modified_since(path: str, dt: pd.Timestamp) -> bool:
    """Check whether `path` was modified since `dt`.

    Returns False if path doesn't exist.

    Parameters
    ----------
    path : str
        Path to the file to be checked.
    dt : pd.Timestamp
        The date against which to compare last_modified_time(path).

    Returns:
    -------
    was_modified : bool
        Will be ``False`` if path doesn't exist, or if its last modified date
        is earlier than or equal to `dt`
    """
    return Path(path).exists() and last_modified_time(path) > dt


def zipline_root(environ: Mapping[Any, Any] | None = None) -> str:
    """Get the root directory for all zipline-managed files.

    For testing purposes, this accepts a dictionary to interpret as the os
    environment.

    Parameters
    ----------
    environ : dict, optional
        A dict to interpret as the os environment.

    Returns:
    -------
    root : string
        Path to the zipline root dir.
    """
    if environ is None:
        environ = os.environ

    root = environ.get("ZIPLINE_ROOT", None)
    if root is None:
        root = str(Path.expanduser(Path("~/.zipline")))

    return root


def zipline_path(paths: list[str], environ: Mapping[Any, Any] | None = None) -> str:
    """Get a path relative to the zipline root.

    Parameters
    ----------
    paths : list[str]
        List of requested path pieces.
    environ : dict, optional
        An environment dict to forward to zipline_root.

    Returns:
    -------
    newpath : str
        The requested path joined with the zipline root.
    """
    return str(Path(zipline_root(environ=environ) / Path(*paths)))


def default_extension(environ: Mapping[Any, Any] | None = None) -> str:
    """Get the path to the default zipline extension file.

    Parameters
    ----------
    environ : dict, optional
        An environment dict to forwart to zipline_root.

    Returns:
    -------
    default_extension_path : str
        The file path to the default zipline extension file.
    """
    return zipline_path(["extension.py"], environ=environ)


def data_root(environ: Mapping[Any, Any] | None = None) -> str:
    """The root directory for zipline data files.

    Parameters
    ----------
    environ : dict, optional
        An environment dict to forward to zipline_root.

    Returns:
    -------
    data_root : str
       The zipline data root.
    """
    return zipline_path(["data"], environ=environ)


def data_path(paths: Iterable[str], environ: Mapping[Any, Any] | None = None) -> str:
    """Get a path relative to the zipline data directory.

    Parameters
    ----------
    paths : iterable[str]
        List of requested path pieces.
    environ : dict, optional
        An environment dict to forward to zipline_root.

    Returns:
    -------
    newpath : str
        The requested path joined with the zipline data root.
    """
    return zipline_path(["data"] + list(paths), environ=environ)


def cache_root(environ: Mapping[Any, Any] | None = None) -> str:
    """The root directory for zipline cache files.

    Parameters
    ----------
    environ : dict, optional
        An environment dict to forward to zipline_root.

    Returns:
    -------
    cache_root : str
       The zipline cache root.
    """
    return zipline_path(["cache"], environ=environ)


def ensure_cache_root(environ: Mapping[Any, Any] | None = None) -> None:
    """Ensure that the data root exists."""
    ensure_directory(cache_root(environ=environ))


def cache_path(paths: Iterable[str], environ: dict[str, Any] | None = None) -> str:
    """Get a path relative to the zipline cache directory.

    Parameters
    ----------
    paths : iterable[str]
        List of requested path pieces.
    environ : dict, optional
        An environment dict to forward to zipline_root.

    Returns:
    -------
    newpath : str
        The requested path joined with the zipline cache root.
    """
    return zipline_path(["cache"] + list(paths), environ=environ)


# ============================================================================
# RustyBT Bundle Path Resolution
# ============================================================================


def find_project_root(start_path: Optional[Path] = None) -> Path:
    """Find project root by looking for markers (.git, pyproject.toml, setup.py).

    Searches upward from start_path until finding a project marker or reaching
    filesystem root.

    Parameters
    ----------
    start_path : Path, optional
        Starting directory (default: current working directory)

    Returns
    -------
    project_root : Path
        Project root directory if found, otherwise current working directory

    Example
    -------
    >>> root = find_project_root()
    >>> print(root)
    /Users/user/projects/rustybt
    """
    if start_path is None:
        start_path = Path.cwd()

    current = start_path.resolve()

    # Walk up directory tree
    while current != current.parent:  # Stop at filesystem root
        # Check for project markers
        if (current / ".git").exists():
            logger.debug("project_root_found", path=str(current), marker=".git")
            return current

        if (current / "pyproject.toml").exists():
            logger.debug("project_root_found", path=str(current), marker="pyproject.toml")
            return current

        if (current / "setup.py").exists():
            logger.debug("project_root_found", path=str(current), marker="setup.py")
            return current

        current = current.parent

    # Fallback: use current working directory
    logger.debug(
        "project_root_fallback",
        path=str(Path.cwd()),
        reason="no_markers_found",
    )
    return Path.cwd()


def is_jupyter_environment() -> bool:
    """Check if code is running in Jupyter notebook.

    Returns
    -------
    is_jupyter : bool
        True if running in Jupyter notebook, False otherwise

    Example
    -------
    >>> if is_jupyter_environment():
    ...     print("Running in Jupyter")
    """
    try:
        from IPython import get_ipython  # type: ignore[attr-defined]

        ipython = get_ipython()  # type: ignore[no-untyped-call]
        if ipython is None:
            return False

        # Check if IPython kernel is running (Jupyter notebook)
        return "IPKernelApp" in ipython.config
    except (ImportError, AttributeError):
        return False


def get_bundle_path(
    bundle_name: Optional[str] = None,
    environ: Mapping[Any, Any] | None = None,
) -> Path:
    """Resolve bundle directory path from configuration.

    This function resolves the bundle directory in the following order:
    1. CSVDIR environment variable (for csvdir bundles)
    2. ZIPLINE_ROOT/data/bundles/<bundle_name>
    3. ~/.zipline/data/bundles/<bundle_name> (default)

    The path is always resolved to an absolute path, creating the directory
    if it doesn't exist.

    Parameters
    ----------
    bundle_name : str, optional
        Bundle name (e.g., 'csvdir', 'quandl'). If None, returns base bundle directory.
    environ : dict, optional
        Environment dict to forward to zipline_root

    Returns
    -------
    bundle_path : Path
        Absolute path to bundle directory

    Raises
    ------
    OSError
        If bundle directory cannot be created

    Example
    -------
    >>> # Get base bundle directory
    >>> bundle_dir = get_bundle_path()
    >>> print(bundle_dir)
    /Users/user/.zipline/data/bundles

    >>> # Get specific bundle directory
    >>> csvdir_path = get_bundle_path('csvdir')
    >>> print(csvdir_path)
    /Users/user/.zipline/data/bundles/csvdir

    Notes
    -----
    This function is designed to work correctly in both CLI and Jupyter environments.
    In Jupyter, it resolves paths relative to the project root rather than the
    notebook's current working directory.
    """
    if environ is None:
        environ = os.environ

    # Special handling for csvdir bundles - check CSVDIR env var first
    if bundle_name == "csvdir" and "CSVDIR" in environ:
        csvdir_path = Path(environ["CSVDIR"]).expanduser().resolve()
        logger.debug(
            "bundle_path_from_env",
            bundle=bundle_name,
            path=str(csvdir_path),
            source="CSVDIR",
        )
        # Create directory if it doesn't exist
        csvdir_path.mkdir(parents=True, exist_ok=True)
        return csvdir_path

    # Use standard bundle path resolution: ZIPLINE_ROOT/data/bundles/<bundle_name>
    if bundle_name:
        bundle_path = Path(data_path(["bundles", bundle_name], environ=environ))
    else:
        bundle_path = Path(data_path(["bundles"], environ=environ))

    # Ensure bundle path is absolute
    bundle_path = bundle_path.resolve()

    # Create directory if it doesn't exist
    try:
        bundle_path.mkdir(parents=True, exist_ok=True)
        logger.debug(
            "bundle_path_resolved",
            bundle=bundle_name or "base",
            path=str(bundle_path),
            exists=bundle_path.exists(),
        )
    except OSError as e:
        logger.error(
            "bundle_path_creation_failed",
            bundle=bundle_name,
            path=str(bundle_path),
            error=str(e),
        )
        raise

    return bundle_path


def validate_bundle_configuration(
    bundle_name: Optional[str] = None,
    environ: Mapping[Any, Any] | None = None,
) -> bool:
    """Validate bundle directory configuration on startup.

    Checks that bundle directory exists or can be created, and verifies
    write permissions.

    Parameters
    ----------
    bundle_name : str, optional
        Bundle name to validate (validates base bundle directory if None)
    environ : dict, optional
        Environment dict to forward to get_bundle_path

    Returns
    -------
    is_valid : bool
        True if bundle configuration is valid and accessible

    Raises
    ------
    PermissionError
        If bundle directory is not writable
    OSError
        If bundle directory cannot be created

    Example
    -------
    >>> # Validate base bundle directory
    >>> validate_bundle_configuration()
    True

    >>> # Validate specific bundle
    >>> validate_bundle_configuration('csvdir')
    True
    """
    try:
        bundle_path = get_bundle_path(bundle_name, environ=environ)

        # Check if directory exists or was created
        if not bundle_path.exists():
            bundle_path.mkdir(parents=True)
            logger.info("bundle_directory_created", path=str(bundle_path))

        # Check write permissions by creating a test file
        test_file = bundle_path / ".write_test"
        try:
            test_file.touch()
            test_file.unlink()
            logger.info(
                "bundle_configuration_valid",
                bundle=bundle_name or "base",
                path=str(bundle_path),
            )
            return True
        except (PermissionError, OSError) as e:
            error_msg = (
                f"Bundle directory not writable: {bundle_path}. "
                f"Please check permissions. Error: {e}"
            )
            logger.error(
                "bundle_configuration_invalid",
                bundle=bundle_name,
                path=str(bundle_path),
                error=str(e),
            )
            raise PermissionError(error_msg) from e

    except OSError as e:
        error_msg = f"Bundle directory inaccessible: {bundle_path}. Error: {e}"
        logger.error(
            "bundle_configuration_error",
            bundle=bundle_name,
            error=str(e),
        )
        raise OSError(error_msg) from e
