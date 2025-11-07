"""Core bundle management infrastructure for data ingestion and loading.

This module provides the central data bundle system for rustybt, handling:
- Bundle registration and discovery
- Data ingestion from various sources
- Bundle loading and reader creation
- Bundle lifecycle management (cleaning old ingestions)
- Support for both legacy Bcolz and modern Parquet bundles

The bundle system enables modular data ingestion where each bundle represents
a dataset from a specific source (e.g., Quandl, CSV files, market data APIs).

Example:
    Register and ingest a custom bundle:

    >>> from rustybt.data.bundles import register, ingest
    >>>
    >>> @register('my-bundle')
    ... def my_ingest(environ, asset_db_writer, minute_bar_writer,
    ...              daily_bar_writer, adjustment_writer, calendar,
    ...              start_session, end_session, cache, show_progress,
    ...              output_dir):
    ...     # Write your ingestion logic here
    ...     pass
    >>>
    >>> # Ingest the bundle
    >>> ingest('my-bundle', show_progress=True)

    Load a bundle for backtesting:

    >>> from rustybt.data.bundles import load
    >>> bundle_data = load('quandl')
    >>> print(bundle_data.asset_finder.retrieve_all(bundle_data.asset_finder.sids))

Notes:
    - Bundles are stored in the data directory configured via environment variables
    - Each ingestion creates a timestamped directory to enable version management
    - The load function automatically detects Parquet vs Bcolz bundle format
"""
import errno
import logging
import os
import shutil
import warnings
from collections import namedtuple
from typing import Mapping, Optional

import click
import pandas as pd
from toolz import complement, curry, take

import rustybt.utils.paths as pth
from rustybt.assets import ASSET_DB_VERSION, AssetDBWriter, AssetFinder
from rustybt.assets.asset_db_migrations import downgrade
from rustybt.utils.cache import (
    dataframe_cache,
    working_dir,
    working_file,
)
from rustybt.utils.calendar_utils import get_calendar
from rustybt.utils.compat import ExitStack, mappingproxy
from rustybt.utils.input_validation import ensure_timestamp, optionally
from rustybt.utils.preprocess import preprocess

from ..adjustments import SQLiteAdjustmentReader, SQLiteAdjustmentWriter
from ..bcolz_daily_bars import BcolzDailyBarReader, BcolzDailyBarWriter
from ..bcolz_minute_bars import (
    BcolzMinuteBarReader,
    BcolzMinuteBarWriter,
)

log = logging.getLogger(__name__)


def asset_db_path(bundle_name, timestr, environ=None, db_version=None):
    """Get the absolute path to a bundle's asset database.

    Args:
        bundle_name: Name of the bundle.
        timestr: Timestamp string for the ingestion (ISO format with semicolons).
        environ: Optional environment variable mapping. Defaults to os.environ.
        db_version: Optional database version. Defaults to current ASSET_DB_VERSION.

    Returns:
        str: Absolute path to the asset database file.

    Example:
        >>> path = asset_db_path('quandl', '2023-01-01T00;00;00')
        >>> print(path)
        /path/to/data/quandl/2023-01-01T00;00;00/assets-7.sqlite
    """
    return pth.data_path(
        asset_db_relative(bundle_name, timestr, db_version),
        environ=environ,
    )


def minute_equity_path(bundle_name, timestr, environ=None):
    """Get the absolute path to a bundle's minute bar data.

    Args:
        bundle_name: Name of the bundle.
        timestr: Timestamp string for the ingestion (ISO format with semicolons).
        environ: Optional environment variable mapping. Defaults to os.environ.

    Returns:
        str: Absolute path to the minute equity data directory.

    Example:
        >>> path = minute_equity_path('quandl', '2023-01-01T00;00;00')
        >>> print(path)
        /path/to/data/quandl/2023-01-01T00;00;00/minute_equities.bcolz
    """
    return pth.data_path(
        minute_equity_relative(bundle_name, timestr),
        environ=environ,
    )


def daily_equity_path(bundle_name, timestr, environ=None):
    """Get the absolute path to a bundle's daily bar data.

    Args:
        bundle_name: Name of the bundle.
        timestr: Timestamp string for the ingestion (ISO format with semicolons).
        environ: Optional environment variable mapping. Defaults to os.environ.

    Returns:
        str: Absolute path to the daily equity data directory.

    Example:
        >>> path = daily_equity_path('quandl', '2023-01-01T00;00;00')
        >>> print(path)
        /path/to/data/quandl/2023-01-01T00;00;00/daily_equities.bcolz
    """
    return pth.data_path(
        daily_equity_relative(bundle_name, timestr),
        environ=environ,
    )


def adjustment_db_path(bundle_name, timestr, environ=None):
    """Get the absolute path to a bundle's adjustment database.

    Args:
        bundle_name: Name of the bundle.
        timestr: Timestamp string for the ingestion (ISO format with semicolons).
        environ: Optional environment variable mapping. Defaults to os.environ.

    Returns:
        str: Absolute path to the adjustment database file.

    Example:
        >>> path = adjustment_db_path('quandl', '2023-01-01T00;00;00')
        >>> print(path)
        /path/to/data/quandl/2023-01-01T00;00;00/adjustments.sqlite
    """
    return pth.data_path(
        adjustment_db_relative(bundle_name, timestr),
        environ=environ,
    )


def cache_path(bundle_name, environ=None):
    """Get the absolute path to a bundle's cache directory.

    Args:
        bundle_name: Name of the bundle.
        environ: Optional environment variable mapping. Defaults to os.environ.

    Returns:
        str: Absolute path to the bundle cache directory.

    Example:
        >>> path = cache_path('quandl')
        >>> print(path)
        /path/to/data/quandl/.cache
    """
    return pth.data_path(
        cache_relative(bundle_name),
        environ=environ,
    )


def adjustment_db_relative(bundle_name, timestr):
    """Get the relative path components for a bundle's adjustment database.

    Args:
        bundle_name: Name of the bundle.
        timestr: Timestamp string for the ingestion.

    Returns:
        tuple: Path components (bundle_name, timestr, filename).

    Example:
        >>> components = adjustment_db_relative('quandl', '2023-01-01T00;00;00')
        >>> print(components)
        ('quandl', '2023-01-01T00;00;00', 'adjustments.sqlite')
    """
    return bundle_name, timestr, "adjustments.sqlite"


def cache_relative(bundle_name):
    """Get the relative path components for a bundle's cache directory.

    Args:
        bundle_name: Name of the bundle.

    Returns:
        tuple: Path components (bundle_name, cache_dirname).

    Example:
        >>> components = cache_relative('quandl')
        >>> print(components)
        ('quandl', '.cache')
    """
    return bundle_name, ".cache"


def daily_equity_relative(bundle_name, timestr):
    """Get the relative path components for a bundle's daily equity data.

    Args:
        bundle_name: Name of the bundle.
        timestr: Timestamp string for the ingestion.

    Returns:
        tuple: Path components (bundle_name, timestr, dirname).

    Example:
        >>> components = daily_equity_relative('quandl', '2023-01-01T00;00;00')
        >>> print(components)
        ('quandl', '2023-01-01T00;00;00', 'daily_equities.bcolz')
    """
    return bundle_name, timestr, "daily_equities.bcolz"


def minute_equity_relative(bundle_name, timestr):
    """Get the relative path components for a bundle's minute equity data.

    Args:
        bundle_name: Name of the bundle.
        timestr: Timestamp string for the ingestion.

    Returns:
        tuple: Path components (bundle_name, timestr, dirname).

    Example:
        >>> components = minute_equity_relative('quandl', '2023-01-01T00;00;00')
        >>> print(components)
        ('quandl', '2023-01-01T00;00;00', 'minute_equities.bcolz')
    """
    return bundle_name, timestr, "minute_equities.bcolz"


def asset_db_relative(bundle_name, timestr, db_version=None):
    """Get the relative path components for a bundle's asset database.

    Args:
        bundle_name: Name of the bundle.
        timestr: Timestamp string for the ingestion.
        db_version: Optional database version. Defaults to current ASSET_DB_VERSION.

    Returns:
        tuple: Path components (bundle_name, timestr, filename).

    Example:
        >>> components = asset_db_relative('quandl', '2023-01-01T00;00;00')
        >>> print(components)
        ('quandl', '2023-01-01T00;00;00', 'assets-7.sqlite')
    """
    db_version = ASSET_DB_VERSION if db_version is None else db_version

    return bundle_name, timestr, "assets-%d.sqlite" % db_version


def to_bundle_ingest_dirname(ts):
    """Convert a pandas Timestamp into the name of the directory for the ingestion.

    Colons are replaced with semicolons to ensure filesystem compatibility across
    all platforms (Windows doesn't allow colons in filenames).

    Args:
        ts: The timestamp of the ingestion.

    Returns:
        str: The name of the directory for this ingestion.

    Example:
        >>> import pandas as pd
        >>> ts = pd.Timestamp('2023-01-15 10:30:45')
        >>> dirname = to_bundle_ingest_dirname(ts)
        >>> print(dirname)
        2023-01-15T10;30;45
    """
    return ts.isoformat().replace(":", ";")


def from_bundle_ingest_dirname(cs):
    """Read a bundle ingestion directory name into a pandas Timestamp.

    Reverses the transformation from to_bundle_ingest_dirname by converting
    semicolons back to colons before parsing.

    Args:
        cs: The name of the ingestion directory.

    Returns:
        pd.Timestamp: The time when this ingestion happened.

    Example:
        >>> dirname = '2023-01-15T10;30;45'
        >>> ts = from_bundle_ingest_dirname(dirname)
        >>> print(ts)
        2023-01-15 10:30:45
    """
    return pd.Timestamp(cs.replace(";", ":"))


def ingestions_for_bundle(bundle, environ=None):
    """Get all ingestion timestamps for a bundle, sorted newest first.

    Args:
        bundle: Name of the bundle.
        environ: Optional environment variable mapping. Defaults to os.environ.

    Returns:
        list[pd.Timestamp]: List of ingestion timestamps in descending order.

    Raises:
        OSError: If the bundle directory doesn't exist.

    Example:
        >>> timestamps = ingestions_for_bundle('quandl')
        >>> for ts in timestamps[:3]:  # Show 3 most recent
        ...     print(ts)
        2023-12-01 10:30:00
        2023-11-15 09:45:00
        2023-11-01 08:00:00
    """
    return sorted(
        (
            from_bundle_ingest_dirname(ing)
            for ing in os.listdir(pth.data_path([bundle], environ))
            if not pth.hidden(ing)
        ),
        reverse=True,
    )


RegisteredBundle = namedtuple(
    "RegisteredBundle",
    [
        "calendar_name",
        "start_session",
        "end_session",
        "minutes_per_day",
        "ingest",
        "create_writers",
    ],
)
RegisteredBundle.__doc__ = """Bundle registration information.

Attributes:
    calendar_name: Name of the trading calendar (e.g., 'NYSE', 'XNYS').
    start_session: First session for data ingestion (pd.Timestamp or None).
    end_session: Last session for data ingestion (pd.Timestamp or None).
    minutes_per_day: Number of minutes in a trading day (typically 390).
    ingest: The ingestion function to call for this bundle.
    create_writers: Whether to create database writers during ingestion.

Example:
    >>> bundle = RegisteredBundle(
    ...     calendar_name='NYSE',
    ...     start_session=pd.Timestamp('2020-01-01'),
    ...     end_session=pd.Timestamp('2023-12-31'),
    ...     minutes_per_day=390,
    ...     ingest=my_ingest_function,
    ...     create_writers=True
    ... )
"""

_BundleData = namedtuple(
    "_BundleData",
    "asset_finder equity_minute_bar_reader equity_daily_bar_reader adjustment_reader",
)


class BundleData(_BundleData):
    """Bundle data readers with automatic resource management.

    Wraps the core data readers for a bundle and provides context manager
    support for proper cleanup of database connections and file handles.

    Attributes:
        asset_finder: AssetFinder for looking up asset metadata.
        equity_minute_bar_reader: Reader for minute-frequency OHLCV data.
        equity_daily_bar_reader: Reader for daily-frequency OHLCV data.
        adjustment_reader: Reader for splits, dividends, and other adjustments.

    Example:
        >>> with load('quandl') as bundle:
        ...     # Access asset data
        ...     assets = bundle.asset_finder.retrieve_all(bundle.asset_finder.sids)
        ...     # Access pricing data
        ...     daily_data = bundle.equity_daily_bar_reader.load_raw_arrays(
        ...         ['close'], start_date, end_date, [sid]
        ...     )
    """

    def close(self):
        """Close all resources that need cleanup.

        Closes database connections and file handles for the asset finder
        and adjustment reader if they support the close() method.
        """
        # Close AssetFinder if it has a close method
        if hasattr(self.asset_finder, "close"):
            self.asset_finder.close()

        # Close SQLiteAdjustmentReader if it has a close method
        if hasattr(self.adjustment_reader, "close"):
            self.adjustment_reader.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


BundleCore = namedtuple(
    "BundleCore",
    "bundles register unregister ingest load clean",
)
BundleCore.__doc__ = """Core bundle management functions.

Attributes:
    bundles: Mapping of bundle names to RegisteredBundle objects.
    register: Function to register a new bundle.
    unregister: Function to unregister a bundle.
    ingest: Function to download and ingest bundle data.
    load: Function to load an ingested bundle.
    clean: Function to remove old bundle ingestions.
"""


class UnknownBundle(click.ClickException, LookupError):
    """Exception raised when a bundle name is not found in the registry.

    Attributes:
        name: The name of the bundle that was not found.
        exit_code: CLI exit code (1).

    Example:
        >>> try:
        ...     load('nonexistent-bundle')
        ... except UnknownBundle as e:
        ...     print(f"Bundle not found: {e.name}")
        Bundle not found: nonexistent-bundle
    """

    exit_code = 1

    def __init__(self, name):
        super(UnknownBundle, self).__init__(
            "No bundle registered with the name %r" % name,
        )
        self.name = name

    def __str__(self):
        return self.message


class BadClean(click.ClickException, ValueError):
    """Exception raised when invalid arguments are passed to the clean function.

    The clean function accepts either date-based filtering (before/after) or
    count-based filtering (keep_last), but not both simultaneously.

    Args:
        before: The 'before' argument that was passed.
        after: The 'after' argument that was passed.
        keep_last: The 'keep_last' argument that was passed.

    Example:
        >>> try:
        ...     clean('quandl', before=pd.Timestamp('2023-01-01'), keep_last=5)
        ... except BadClean:
        ...     print("Cannot mix date and count-based cleaning")
        Cannot mix date and count-based cleaning
    """

    def __init__(self, before, after, keep_last):
        super(BadClean, self).__init__(
            "Cannot pass a combination of `before` and `after` with "
            "`keep_last`. Must pass one. "
            "Got: before=%r, after=%r, keep_last=%r\n"
            % (
                before,
                after,
                keep_last,
            ),
        )

    def __str__(self):
        return self.message


# TODO: simplify
def _make_bundle_core():
    """Create a family of data bundle functions that share a common registry.

    Creates and returns a closure containing the bundle registry and all
    bundle management functions. This enables a clean API where all functions
    operate on the same underlying bundle mapping.

    Returns:
        BundleCore: Named tuple containing:
            - bundles (mappingproxy): Read-only mapping of bundle names to RegisteredBundle.
            - register (callable): Register a new data bundle.
            - unregister (callable): Remove a bundle from the registry.
            - ingest (callable): Download and write bundle data.
            - load (callable): Load an ingested bundle into memory.
            - clean (callable): Remove old bundle ingestions.

    Example:
        >>> bundles, register, unregister, ingest, load, clean = _make_bundle_core()
        >>> # Register a custom bundle
        >>> @register('my-data')
        ... def my_ingest_func(*args):
        ...     pass
        >>> # Use the bundle
        >>> ingest('my-data', show_progress=True)
        >>> bundle_data = load('my-data')
    """
    _bundles = {}  # the registered bundles
    # Expose _bundles through a proxy so that users cannot mutate this
    # accidentally. Users may go through `register` to update this which will
    # warn when trampling another bundle.
    bundles = mappingproxy(_bundles)

    @curry
    def register(
        name,
        f,
        calendar_name="NYSE",
        start_session=None,
        end_session=None,
        minutes_per_day=390,
        create_writers=True,
    ):
        """Register a data bundle ingest function.

        Registers a custom ingestion function that downloads and processes data
        for backtesting. The function can be used as a decorator or called directly.

        Args:
            name: Unique identifier for the bundle.
            f: Ingest function with signature:
                f(environ, asset_db_writer, minute_bar_writer, daily_bar_writer,
                  adjustment_writer, calendar, start_session, end_session, cache,
                  show_progress, output_dir)
                where:
                - environ (Mapping): Environment variables.
                - asset_db_writer (AssetDBWriter): Writer for asset metadata.
                - minute_bar_writer (BcolzMinuteBarWriter): Writer for minute bars.
                - daily_bar_writer (BcolzDailyBarWriter): Writer for daily bars.
                - adjustment_writer (SQLiteAdjustmentWriter): Writer for adjustments.
                - calendar (TradingCalendar): Trading calendar for date alignment.
                - start_session (pd.Timestamp): First date to ingest.
                - end_session (pd.Timestamp): Last date to ingest.
                - cache (DataFrameCache): Temporary storage for intermediate data.
                - show_progress (bool): Whether to display progress information.
                - output_dir (str): Directory path for bundle output.
            calendar_name: Trading calendar name (e.g., 'NYSE', 'XNYS'). Default: 'NYSE'.
            start_session: First session for data. Defaults to calendar's first session.
            end_session: Last session for data. Defaults to calendar's last session.
            minutes_per_day: Minutes in a normal trading day. Default: 390.
            create_writers: Whether to create database writers automatically. Default: True.
                Set to False for bundles that manage their own writers.

        Returns:
            callable: The registered ingest function (for decorator usage).

        Warns:
            UserWarning: If a bundle with the same name already exists.

        Example:
            As a decorator:

            >>> @register('my-csv-data', calendar_name='XNYS')
            ... def ingest_csv(environ, asset_db_writer, minute_bar_writer,
            ...                daily_bar_writer, adjustment_writer, calendar,
            ...                start_session, end_session, cache, show_progress,
            ...                output_dir):
            ...     # Load CSV data
            ...     df = pd.read_csv('data.csv')
            ...     # Write to bundle
            ...     daily_bar_writer.write(process_data(df))

            Direct call:

            >>> def my_ingest_func(*args):
            ...     pass
            >>> register('my-bundle', my_ingest_func, calendar_name='LSE')
        """
        if name in bundles:
            warnings.warn(
                "Overwriting bundle with name %r" % name,
                stacklevel=3,
            )

        # NOTE: We don't eagerly compute calendar values here because
        # `register` is called at module scope in zipline, and creating a
        # calendar currently takes between 0.5 and 1 seconds, which causes a
        # noticeable delay on the zipline CLI.
        _bundles[name] = RegisteredBundle(
            calendar_name=calendar_name,
            start_session=start_session,
            end_session=end_session,
            minutes_per_day=minutes_per_day,
            ingest=f,
            create_writers=create_writers,
        )
        return f

    def unregister(name):
        """Unregister a bundle from the registry.

        Removes a bundle registration, preventing further ingestion or loading
        until it's registered again.

        Args:
            name: Name of the bundle to unregister.

        Raises:
            UnknownBundle: If no bundle with this name is registered.

        Example:
            >>> unregister('my-old-bundle')
            >>> # The bundle is now removed from the registry
            >>> try:
            ...     ingest('my-old-bundle')
            ... except UnknownBundle:
            ...     print("Bundle no longer registered")
        """
        try:
            del _bundles[name]
        except KeyError:
            raise UnknownBundle(name)

    def ingest(
        name,
        environ=os.environ,
        timestamp=None,
        assets_versions=(),
        show_progress=False,
    ):
        """Ingest data for a registered bundle.

        Downloads and processes data according to the bundle's registered ingest
        function, creating a timestamped directory with all required database files.

        Args:
            name: Name of the bundle to ingest.
            environ: Environment variables mapping. Defaults to os.environ.
            timestamp: Timestamp for this ingestion. Defaults to current UTC time.
                Multiple ingestions create separate timestamped directories.
            assets_versions: Asset database versions to create via downgrade.
                Useful for compatibility with older code. Example: (5, 6) creates
                assets-5.sqlite and assets-6.sqlite in addition to current version.
            show_progress: Whether to display progress information during ingestion.

        Raises:
            UnknownBundle: If the bundle name is not registered.
            ValueError: If assets_versions is specified but create_writers=False.

        Example:
            Basic ingestion:

            >>> ingest('quandl', show_progress=True)
            Ingesting quandl...
            [Progress output...]

            Ingestion with specific timestamp:

            >>> import pandas as pd
            >>> ts = pd.Timestamp('2023-01-01', tz='UTC')
            >>> ingest('my-bundle', timestamp=ts)

            Create backward-compatible asset databases:

            >>> ingest('quandl', assets_versions=(5, 6), show_progress=True)
        """
        try:
            bundle = bundles[name]
        except KeyError:
            raise UnknownBundle(name)

        calendar = get_calendar(bundle.calendar_name)

        start_session = bundle.start_session
        end_session = bundle.end_session

        if start_session is None or start_session < calendar.first_session:
            start_session = calendar.first_session

        if end_session is None or end_session > calendar.last_session:
            end_session = calendar.last_session

        if timestamp is None:
            timestamp = pd.Timestamp.utcnow()
        timestamp = timestamp.tz_convert("utc").tz_localize(None)

        timestr = to_bundle_ingest_dirname(timestamp)
        cachepath = cache_path(name, environ=environ)
        pth.ensure_directory(pth.data_path([name, timestr], environ=environ))
        pth.ensure_directory(cachepath)
        with (
            dataframe_cache(cachepath, clean_on_failure=False) as cache,
            ExitStack() as stack,
        ):
            # we use `cleanup_on_failure=False` so that we don't purge the
            # cache directory if the load fails in the middle
            if bundle.create_writers:
                wd = stack.enter_context(working_dir(pth.data_path([], environ=environ)))
                daily_bars_path = wd.ensure_dir(*daily_equity_relative(name, timestr))
                daily_bar_writer = BcolzDailyBarWriter(
                    daily_bars_path,
                    calendar,
                    start_session,
                    end_session,
                )
                # Do an empty write to ensure that the daily ctables exist
                # when we create the SQLiteAdjustmentWriter below. The
                # SQLiteAdjustmentWriter needs to open the daily ctables so
                # that it can compute the adjustment ratios for the dividends.

                daily_bar_writer.write(())
                minute_bar_writer = BcolzMinuteBarWriter(
                    wd.ensure_dir(*minute_equity_relative(name, timestr)),
                    calendar,
                    start_session,
                    end_session,
                    minutes_per_day=bundle.minutes_per_day,
                )
                assets_db_path = wd.getpath(*asset_db_relative(name, timestr))
                asset_db_writer = AssetDBWriter(assets_db_path)

                adjustment_db_writer = stack.enter_context(
                    SQLiteAdjustmentWriter(
                        wd.getpath(*adjustment_db_relative(name, timestr)),
                        BcolzDailyBarReader(daily_bars_path),
                        overwrite=True,
                    )
                )
            else:
                daily_bar_writer = None
                minute_bar_writer = None
                asset_db_writer = None
                adjustment_db_writer = None
                if assets_versions:
                    raise ValueError(
                        "Need to ingest a bundle that creates "
                        "writers in order to downgrade the assets"
                        " db."
                    )
            log.info("Ingesting %s", name)
            bundle.ingest(
                environ,
                asset_db_writer,
                minute_bar_writer,
                daily_bar_writer,
                adjustment_db_writer,
                calendar,
                start_session,
                end_session,
                cache,
                show_progress,
                pth.data_path([name, timestr], environ=environ),
            )

            for version in sorted(set(assets_versions), reverse=True):
                version_path = wd.getpath(
                    *asset_db_relative(
                        name,
                        timestr,
                        db_version=version,
                    )
                )
                with working_file(version_path) as wf:
                    shutil.copy2(assets_db_path, wf.path)
                    downgrade(wf.path, version)

    def most_recent_data(bundle_name, timestamp, environ=None):
        """Get the path to the most recent ingestion for a bundle.

        Finds the most recent ingestion directory that exists for the bundle,
        regardless of the timestamp parameter (which is kept for API compatibility).

        Args:
            bundle_name: Name of the bundle to lookup.
            timestamp: Timestamp parameter (currently unused, kept for compatibility).
            environ: Environment variables mapping. Defaults to os.environ.

        Returns:
            str: Absolute path to the most recent ingestion directory.

        Raises:
            UnknownBundle: If the bundle name is not registered.
            ValueError: If no data exists for the bundle (needs ingestion).

        Example:
            >>> path = most_recent_data('quandl', pd.Timestamp.now())
            >>> print(path)
            /path/to/data/quandl/2023-12-01T10;30;00
        """
        if bundle_name not in bundles:
            raise UnknownBundle(bundle_name)

        try:
            candidates = os.listdir(
                pth.data_path([bundle_name], environ=environ),
            )
            return pth.data_path(
                [
                    bundle_name,
                    max(
                        filter(complement(pth.hidden), candidates),
                        key=from_bundle_ingest_dirname,
                    ),
                ],
                environ=environ,
            )
        except (ValueError, OSError) as e:
            if getattr(e, "errno", errno.ENOENT) != errno.ENOENT:
                raise
            raise ValueError(
                f"no data for bundle {bundle_name!r} on or before {timestamp}\n"
                f"maybe you need to run: $ zipline ingest -b {bundle_name}",
            )

    def load(
        name: str,
        environ: Optional[Mapping[str, str]] = None,
        timestamp: Optional[pd.Timestamp] = None,
    ) -> BundleData:
        """Load a previously ingested bundle for backtesting.

        Automatically detects the bundle format (Parquet or legacy Bcolz) and
        creates appropriate readers for accessing asset metadata, pricing data,
        and corporate actions.

        Args:
            name: Name of the bundle to load.
            environ: Environment variables mapping. Defaults to os.environ.
            timestamp: Timestamp of ingestion to load. Defaults to most recent.
                Allows loading historical ingestions for reproducibility.

        Returns:
            BundleData: Bundle data container with these readers:
                - asset_finder: Look up asset metadata by symbol or SID
                - equity_daily_bar_reader: Access daily OHLCV data
                - equity_minute_bar_reader: Access minute OHLCV data (if available)
                - adjustment_reader: Access splits, dividends, and adjustments

        Raises:
            UnknownBundle: If the bundle name is not registered.
            ValueError: If no data exists for the bundle (needs ingestion).

        Example:
            Load and use a bundle:

            >>> # Load the most recent ingestion
            >>> bundle = load('quandl')
            >>>
            >>> # Find assets
            >>> asset = bundle.asset_finder.lookup_symbol('AAPL', pd.Timestamp('2023-01-01'))
            >>>
            >>> # Get daily pricing data
            >>> closes = bundle.equity_daily_bar_reader.load_raw_arrays(
            ...     ['close'],
            ...     pd.Timestamp('2023-01-01'),
            ...     pd.Timestamp('2023-12-31'),
            ...     [asset.sid]
            ... )

            Use with context manager for automatic cleanup:

            >>> with load('quandl') as bundle:
            ...     # Work with bundle data
            ...     assets = bundle.asset_finder.retrieve_all(bundle.asset_finder.sids)
            ... # Resources automatically closed here

            Load a specific historical ingestion:

            >>> ts = pd.Timestamp('2023-01-01', tz='UTC')
            >>> bundle = load('quandl', timestamp=ts)
        """
        if environ is None:
            environ = os.environ
        if timestamp is None:
            timestamp = pd.Timestamp.utcnow()

        # Check if this is a Parquet bundle (created by ingest-unified)
        from rustybt.data.bundles.metadata import BundleMetadata

        metadata = BundleMetadata.get(name)
        if metadata is not None:
            # This is a Parquet bundle created by ingest-unified
            # Load using Parquet reader adapter
            from pathlib import Path

            from rustybt.data.polars.parquet_adjustments import ParquetAdjustmentReader
            from rustybt.data.polars.parquet_asset_finder import ParquetAssetFinder
            from rustybt.data.polars.parquet_bar_reader import ParquetDailyBarReader
            from rustybt.data.polars.parquet_minute_bar_reader import ParquetMinuteBarReader

            bundle_path_str = pth.data_path(["bundles", name], environ=environ)
            bundle_path = Path(bundle_path_str)

            # Get calendar from metadata (default to XNYS for backward compatibility)
            calendar_name = metadata.get("calendar") or "XNYS"

            # Get date range from metadata
            start_date = metadata.get("start_date")
            end_date = metadata.get("end_date")

            if start_date is None or end_date is None:
                raise ValueError(
                    f"Bundle '{name}' metadata is missing start_date or end_date. "
                    f"Bundle may be corrupted. Try re-ingesting with 'rustybt ingest-unified'."
                )

            # Convert Unix timestamps to pandas Timestamps
            start_session = pd.Timestamp(start_date, unit="s")
            end_session = pd.Timestamp(end_date, unit="s")

            # Create Parquet asset finder (reads from metadata.db)
            asset_finder = ParquetAssetFinder(bundle_name=name)

            # Create Parquet daily bar reader
            daily_bar_reader = ParquetDailyBarReader(
                bundle_path=str(bundle_path),
                calendar_name=calendar_name,
                start_session=start_session,
                end_session=end_session,
            )

            # Create Parquet minute bar reader if minute data exists
            minute_bars_path = bundle_path / "minute_bars"
            if minute_bars_path.exists() and any(minute_bars_path.iterdir()):
                minute_bar_reader = ParquetMinuteBarReader(
                    bundle_path=str(bundle_path),
                    calendar_name=calendar_name,
                    start_session=start_session,
                    end_session=end_session,
                )
                log.info("Loaded minute bar reader for bundle '%s'", name)
            else:
                minute_bar_reader = None
                log.info("No minute data found for bundle '%s'", name)

            # Create Parquet adjustment reader
            try:
                adjustment_reader = ParquetAdjustmentReader(bundle_path=str(bundle_path))
                log.info("Loaded adjustment reader for bundle '%s'", name)
            except Exception as e:
                log.warning("Could not load adjustment reader for bundle '%s': %s", name, str(e))
                adjustment_reader = None

            log.info(
                "Loading Parquet bundle '%s' with calendar '%s' (%s to %s)",
                name,
                calendar_name,
                start_session.date(),
                end_session.date(),
            )

            return BundleData(
                asset_finder=asset_finder,
                equity_minute_bar_reader=minute_bar_reader,
                equity_daily_bar_reader=daily_bar_reader,
                adjustment_reader=adjustment_reader,
            )

        # Traditional Bcolz bundle - use existing logic
        timestr = most_recent_data(name, timestamp, environ=environ)
        return BundleData(
            asset_finder=AssetFinder(
                asset_db_path(name, timestr, environ=environ),
            ),
            equity_minute_bar_reader=BcolzMinuteBarReader(
                minute_equity_path(name, timestr, environ=environ),
            ),
            equity_daily_bar_reader=BcolzDailyBarReader(
                daily_equity_path(name, timestr, environ=environ),
            ),
            adjustment_reader=SQLiteAdjustmentReader(
                adjustment_db_path(name, timestr, environ=environ),
            ),
        )

    @preprocess(
        before=optionally(ensure_timestamp),
        after=optionally(ensure_timestamp),
    )
    def clean(name, before=None, after=None, keep_last=None, environ=os.environ):
        """Clean up old bundle ingestions to free disk space.

        Removes bundle ingestion directories based on date or count criteria.
        Use this to manage disk space by removing outdated or redundant ingestions.

        Args:
            name: Name of the bundle to clean.
            before: Remove ingestions created before this timestamp.
                Mutually exclusive with keep_last.
            after: Remove ingestions created after this timestamp.
                Mutually exclusive with keep_last.
            keep_last: Keep only the N most recent ingestions, remove the rest.
                Mutually exclusive with before/after. Use 0 to remove all.
            environ: Environment variables mapping. Defaults to os.environ.

        Returns:
            set[str]: Set of absolute paths to directories that were removed.

        Raises:
            BadClean: If invalid argument combination is passed (before/after with keep_last).
            UnknownBundle: If the bundle name is not registered.

        Example:
            Remove old ingestions (keep only last 3):

            >>> cleaned = clean('quandl', keep_last=3)
            >>> print(f"Removed {len(cleaned)} ingestions")
            Removed 5 ingestions

            Remove ingestions before a date:

            >>> cutoff = pd.Timestamp('2023-01-01', tz='UTC')
            >>> cleaned = clean('quandl', before=cutoff)

            Remove ingestions in a date range:

            >>> start = pd.Timestamp('2023-01-01', tz='UTC')
            >>> end = pd.Timestamp('2023-06-30', tz='UTC')
            >>> cleaned = clean('quandl', after=start, before=end)

            Remove all ingestions:

            >>> clean('old-bundle', keep_last=0)
        """
        try:
            all_runs = sorted(
                filter(
                    complement(pth.hidden),
                    os.listdir(pth.data_path([name], environ=environ)),
                ),
                key=from_bundle_ingest_dirname,
            )
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise
            raise UnknownBundle(name)

        if before is after is keep_last is None:
            raise BadClean(before, after, keep_last)
        if (before is not None or after is not None) and keep_last is not None:
            raise BadClean(before, after, keep_last)

        if keep_last is None:

            def should_clean(name):
                dt = from_bundle_ingest_dirname(name)
                return (before is not None and dt < before) or (after is not None and dt > after)

        elif keep_last >= 0:
            last_n_dts = set(take(keep_last, reversed(all_runs)))

            def should_clean(name):
                return name not in last_n_dts

        else:
            raise BadClean(before, after, keep_last)

        cleaned = set()
        for run in all_runs:
            if should_clean(run):
                log.info("Cleaning %s.", run)
                path = pth.data_path([name, run], environ=environ)
                shutil.rmtree(path)
                cleaned.add(path)

        return cleaned

    return BundleCore(bundles, register, unregister, ingest, load, clean)


bundles, register, unregister, ingest, load, clean = _make_bundle_core()
