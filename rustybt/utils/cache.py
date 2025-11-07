"""Caching utilities for rustybt.

This module provides utilities for caching data in memory and on disk, including:
- CachedObject: Simple struct for maintaining cached objects with expiration dates
- ExpiringCache: Cache that automatically deletes expired entries
- dataframe_cache: Disk-backed cache for pandas DataFrames
- working_file: Context manager for atomic file operations
- working_dir: Context manager for atomic directory operations

The caching utilities are designed to be thread-safe and support various
serialization formats including pickle and msgpack.

Examples:
    Basic usage of CachedObject with expiration:

    >>> from pandas import Timestamp, Timedelta
    >>> expires = Timestamp('2014', tz='UTC')
    >>> obj = CachedObject(42, expires)
    >>> obj.unwrap(expires)
    42

    Using ExpiringCache for multiple objects:

    >>> cache = ExpiringCache()
    >>> cache.set('key1', 'value1', Timestamp('2014', tz='UTC'))
    >>> cache.get('key1', Timestamp('2013', tz='UTC'))
    'value1'
"""

import errno
import os
import pickle
from collections.abc import MutableMapping
from functools import partial

# from distutils import dir_util
from shutil import copytree, move, rmtree
from tempfile import NamedTemporaryFile, mkdtemp

import pandas as pd

from .context_tricks import nop_context
from .paths import ensure_directory
from .sentinel import sentinel


class Expired(Exception):
    """Exception raised when accessing an expired CachedObject.

    This exception is raised when attempting to unwrap a CachedObject
    after its expiration datetime has passed.
    """


ExpiredCachedObject = sentinel("ExpiredCachedObject")
AlwaysExpired = sentinel("AlwaysExpired")


class CachedObject:
    """A simple struct for maintaining a cached object with an expiration date.

    This class wraps a value along with an expiration datetime. The cached
    value can be retrieved as long as the current datetime is not strictly
    greater than the expiration datetime.

    Args:
        value: The object to cache. Can be any Python object.
        expires: Expiration date of the cached value. The cache is considered
            invalid for dates strictly greater than this value.

    Examples:
        Create a cached object with an expiration date:

        >>> from pandas import Timestamp, Timedelta
        >>> expires = Timestamp('2014', tz='UTC')
        >>> obj = CachedObject(1, expires)
        >>> obj.unwrap(expires - Timedelta('1 minute'))
        1
        >>> obj.unwrap(expires)
        1

        Accessing after expiration raises an exception:

        >>> obj.unwrap(expires + Timedelta('1 minute'))
        ... # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
            ...
        Expired: 2014-01-01 00:00:00+00:00

        Create an always-expired object:

        >>> expired_obj = CachedObject.expired()
        >>> expired_obj.unwrap(Timestamp('2020', tz='UTC'))
        ... # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
            ...
        Expired
    """

    def __init__(self, value, expires):
        self._value = value
        self._expires = expires

    @classmethod
    def expired(cls):
        """Construct a CachedObject that's expired at any time."""
        return cls(ExpiredCachedObject, expires=AlwaysExpired)

    def unwrap(self, dt):
        """Get the cached value if it hasn't expired.

        Args:
            dt: The current datetime to check against the expiration time.

        Returns:
            The cached value if it hasn't expired.

        Raises:
            Expired: Raised when dt is strictly greater than the expiration time.

        Examples:
            >>> from pandas import Timestamp
            >>> obj = CachedObject("data", Timestamp('2014', tz='UTC'))
            >>> obj.unwrap(Timestamp('2013', tz='UTC'))
            'data'
        """
        expires = self._expires
        if expires is AlwaysExpired or expires < dt:
            raise Expired(self._expires)
        return self._value

    def _unsafe_get_value(self):
        """You almost certainly shouldn't use this."""
        return self._value


class ExpiringCache:
    """A cache that stores multiple CachedObjects and auto-deletes expired entries.

    This cache automatically removes entries when they are accessed after their
    expiration time. It supports an optional cleanup callback that is invoked
    before an expired entry is deleted.

    Args:
        cache: A dict-like object supporting __delitem__, __getitem__, and
            __setitem__. If None, a standard dict is used. Default is None.
        cleanup: A callable that takes a single argument (the cached value) and
            is called upon expiry, prior to deletion. Default is a no-op function.

    Examples:
        Basic usage with automatic expiration:

        >>> from pandas import Timestamp, Timedelta
        >>> expires = Timestamp('2014', tz='UTC')
        >>> cache = ExpiringCache()
        >>> cache.set('foo', 1, expires)
        >>> cache.get('foo', expires - Timedelta('1 minute'))
        1

        Accessing an expired value raises KeyError:

        >>> cache.get('foo', expires + Timedelta('1 minute'))
        Traceback (most recent call last):
            ...
        KeyError: 'foo'

        Using a cleanup callback:

        >>> cleaned_up = []
        >>> cache = ExpiringCache(cleanup=lambda v: cleaned_up.append(v))
        >>> cache.set('bar', 'value', Timestamp('2014', tz='UTC'))
        >>> cache.get('bar', Timestamp('2015', tz='UTC'))
        Traceback (most recent call last):
            ...
        KeyError: 'bar'
        >>> 'value' in cleaned_up
        True
    """

    def __init__(self, cache=None, cleanup=lambda value_to_clean: None):
        if cache is not None:
            self._cache = cache
        else:
            self._cache = {}

        self.cleanup = cleanup

    def get(self, key, dt):
        """Get the value of a cached object.

        Args:
            key: The key to lookup in the cache.
            dt: The datetime to check against the cached value's expiration.

        Returns:
            The cached value associated with the key.

        Raises:
            KeyError: Raised if the key is not in the cache or if the value
                for the key has expired.

        Examples:
            >>> from pandas import Timestamp
            >>> cache = ExpiringCache()
            >>> cache.set('mykey', 42, Timestamp('2014', tz='UTC'))
            >>> cache.get('mykey', Timestamp('2013', tz='UTC'))
            42
        """
        try:
            return self._cache[key].unwrap(dt)
        except Expired as exc:
            self.cleanup(self._cache[key]._unsafe_get_value())
            del self._cache[key]
            raise KeyError(key) from exc

    def set(self, key, value, expiration_dt):
        """Add a new key-value pair to the cache with an expiration time.

        Args:
            key: The key to use for the cached pair. Can be any hashable object.
            value: The value to store under the given key. Can be any object.
            expiration_dt: The expiration datetime for this cached entry.
                The cache is considered invalid for dates strictly greater
                than this value.

        Examples:
            >>> from pandas import Timestamp
            >>> cache = ExpiringCache()
            >>> cache.set('temperature', 72.5, Timestamp('2014-01-01', tz='UTC'))
            >>> cache.get('temperature', Timestamp('2013-12-31', tz='UTC'))
            72.5
        """
        self._cache[key] = CachedObject(value, expiration_dt)


class dataframe_cache(MutableMapping):
    """A disk-backed cache for pandas DataFrames.

    This class implements a mutable mapping from string names to pandas
    DataFrame objects, persisting data to disk for durability. It can be
    used as a context manager to automatically clean up the cache directory
    on exit.

    Args:
        path: The directory path to the cache. Files will be written as
            path/<keyname>. If None, a temporary directory is created.
            Default is None.
        lock: A thread lock for multithreaded/multiprocessed access to the
            cache. If not provided, no locking will be used. Default is None.
        clean_on_failure: Whether to clean up the directory if an exception
            is raised in the context manager. Default is True.
        serialization: How data should be serialized. Options are 'msgpack'
            or 'pickle[:n]' where n is an optional pickle protocol number
            (e.g., 'pickle:3' uses pickle protocol 3). Default is 'pickle'.

    Note:
        - The syntax cache[:] loads all key:value pairs into memory as a dict.
        - The cache uses a temporary file format subject to change between versions.
        - When using as a context manager, the cache directory is deleted on exit.

    Examples:
        Basic usage with automatic cleanup:

        >>> import pandas as pd
        >>> df = pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]})
        >>> with dataframe_cache() as cache:
        ...     cache['mydata'] = df
        ...     retrieved = cache['mydata']
        ...     assert df.equals(retrieved)

        Persistent cache with custom path:

        >>> cache = dataframe_cache(path='/tmp/my_cache')
        >>> cache['data1'] = pd.DataFrame({'x': [1, 2]})
        >>> list(cache.keys())
        ['data1']

        Using pickle protocol 4 for serialization:

        >>> cache = dataframe_cache(serialization='pickle:4')
        >>> cache['highperf'] = pd.DataFrame({'fast': [1, 2, 3]})
    """

    def __init__(self, path=None, lock=None, clean_on_failure=True, serialization="pickle"):
        self.path = path if path is not None else mkdtemp()
        self.lock = lock if lock is not None else nop_context
        self.clean_on_failure = clean_on_failure

        if serialization == "msgpack":
            self.serialize = pd.DataFrame.to_msgpack
            self.deserialize = pd.read_msgpack
            self._protocol = None
        else:
            s = serialization.split(":", 1)
            if s[0] != "pickle":
                raise ValueError(
                    "'serialization' must be either 'msgpack' or 'pickle[:n]'",
                )
            self._protocol = int(s[1]) if len(s) == 2 else None

            self.serialize = self._serialize_pickle
            self.deserialize = partial(pickle.load, encoding="latin-1")

        ensure_directory(self.path)

    def _serialize_pickle(self, df, path):
        with open(path, "wb") as f:
            pickle.dump(df, f, protocol=self._protocol)

    def _keypath(self, key):
        return os.path.join(self.path, key)

    def __enter__(self):
        return self

    def __exit__(self, type_, value, tb):
        if not (self.clean_on_failure or value is None):
            # we are not cleaning up after a failure and there was an exception
            return

        with self.lock:
            rmtree(self.path)

    def __getitem__(self, key):
        if key == slice(None):
            return dict(self.items())

        with self.lock:
            try:
                with open(self._keypath(key), "rb") as f:
                    return self.deserialize(f)
            except OSError as exc:
                if exc.errno != errno.ENOENT:
                    raise
                raise KeyError(key) from exc

    def __setitem__(self, key, value):
        with self.lock:
            self.serialize(value, self._keypath(key))

    def __delitem__(self, key):
        with self.lock:
            try:
                os.remove(self._keypath(key))
            except OSError as exc:
                if exc.errno == errno.ENOENT:
                    # raise a keyerror if this directory did not exist
                    raise KeyError(key) from exc
                # reraise the actual oserror otherwise
                raise

    def __iter__(self):
        return iter(os.listdir(self.path))

    def __len__(self):
        return len(os.listdir(self.path))

    def __repr__(self):
        return "<%s: keys={%s}>" % (
            type(self).__name__,
            ", ".join(map(repr, sorted(self))),
        )


class working_file:
    """Context manager for atomic file operations using a temporary file.

    This context manager creates a temporary file that will be atomically moved
    to the final destination if no exceptions are raised. This ensures that
    the destination file is never left in a partially written state.

    Args:
        final_path: The location to move the file when committing successfully.
        *args: Additional positional arguments forwarded to NamedTemporaryFile.
        **kwargs: Additional keyword arguments forwarded to NamedTemporaryFile.

    Attributes:
        path: The path to the temporary file (alias for name).

    Note:
        - The file is moved on __exit__ only if there are no exceptions.
        - Uses shutil.move for the atomic operation.
        - The temporary file is automatically deleted if an exception occurs.

    Examples:
        Write data atomically to a file:

        >>> with working_file('/tmp/output.txt', mode='w') as wf:
        ...     with open(wf.path, 'w') as f:
        ...         f.write('Hello World')

        The file is not created if an exception occurs:

        >>> try:
        ...     with working_file('/tmp/output2.txt', mode='w') as wf:
        ...         with open(wf.path, 'w') as f:
        ...             f.write('Partial')
        ...         raise ValueError('Something went wrong')
        ... except ValueError:
        ...     pass  # /tmp/output2.txt was not created
    """

    def __init__(self, final_path, *args, **kwargs):
        self._tmpfile = NamedTemporaryFile(delete=False, *args, **kwargs)
        self._final_path = final_path

    @property
    def path(self):
        """Alias for ``name`` to be consistent with
        :class:`~rustybt.utils.cache.working_dir`.
        """
        return self._tmpfile.name

    def _commit(self):
        """Sync the temporary file to the final path."""
        move(self.path, self._final_path)

    def __enter__(self):
        self._tmpfile.__enter__()
        return self

    def __exit__(self, *exc_info):
        self._tmpfile.__exit__(*exc_info)
        if exc_info[0] is None:
            self._commit()


class working_dir:
    """Context manager for atomic directory operations using a temporary directory.

    This context manager creates a temporary directory that will be copied to
    the final destination if no exceptions are raised. This ensures that the
    destination directory is never left in a partially written state.

    Args:
        final_path: The location to copy the directory contents to when
            committing successfully.
        *args: Additional positional arguments (currently unused).
        **kwargs: Additional keyword arguments (currently unused).

    Attributes:
        path: The path to the temporary directory.

    Note:
        - The directory is copied on __exit__ only if there are no exceptions.
        - Uses shutil.copytree for the atomic operation.
        - The temporary directory is automatically deleted after copying or on error.

    Examples:
        Create multiple files atomically:

        >>> import os
        >>> with working_dir('/tmp/output_dir') as wd:
        ...     file1 = wd.getpath('file1.txt')
        ...     file2 = wd.getpath('file2.txt')
        ...     with open(file1, 'w') as f:
        ...         f.write('Content 1')
        ...     with open(file2, 'w') as f:
        ...         f.write('Content 2')

        Create subdirectories within the working directory:

        >>> with working_dir('/tmp/structured') as wd:
        ...     subdir = wd.ensure_dir('data', 'processed')
        ...     filepath = wd.getpath('data', 'processed', 'result.txt')
        ...     with open(filepath, 'w') as f:
        ...         f.write('Results')
    """

    def __init__(self, final_path, *args, **kwargs):
        self.path = mkdtemp()
        self._final_path = final_path

    def ensure_dir(self, *path_parts):
        """Ensure a subdirectory exists within the working directory.

        Args:
            *path_parts: Path components relative to the working directory.
                These will be joined to create the full path.

        Returns:
            str: The absolute path to the created directory.

        Examples:
            >>> with working_dir('/tmp/test') as wd:
            ...     data_dir = wd.ensure_dir('data')
            ...     nested = wd.ensure_dir('data', 'processed', 'results')
        """
        path = self.getpath(*path_parts)
        ensure_directory(path)
        return path

    def getpath(self, *path_parts):
        """Get a path relative to the working directory.

        Args:
            *path_parts: Path components relative to the working directory.
                These will be joined to create the full path.

        Returns:
            str: The absolute path constructed from the working directory
                and the provided path parts.

        Examples:
            >>> with working_dir('/tmp/test') as wd:
            ...     file_path = wd.getpath('data', 'file.txt')
            ...     # Returns something like '/tmp/tmpXXXXXX/data/file.txt'
        """
        return os.path.join(self.path, *path_parts)

    def _commit(self):
        """Sync the temporary directory to the final path."""
        copytree(src=self.path, dst=self._final_path, dirs_exist_ok=True)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        if exc_info[0] is None:
            self._commit()
        rmtree(self.path)
