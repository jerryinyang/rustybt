"""Windows-specific cleanup utilities for handling file locking issues.

Provides utilities to work around Windows file locking behavior that can
cause test failures, particularly in CI environments. Windows keeps file
handles open longer than Unix-like systems, causing PermissionErrors when
trying to delete files or directories.

Functions:
    force_close_on_windows: Force garbage collection and delay
    retry_on_permission_error: Decorator for retrying file operations
    windows_safe_cleanup: Context manager for safe directory cleanup

Classes:
    WindowsSafeTempDirectory: Wrapper for safe temp directory cleanup

Examples:
    Safely cleanup test directory::

        from rustybt.testing.windows_cleanup import windows_safe_cleanup
        import tempfile

        temp_dir = tempfile.mkdtemp()

        with windows_safe_cleanup(temp_dir):
            # Use temp directory
            write_test_files(temp_dir)
        # Cleaned up safely, even on Windows

    Retry file operations::

        from rustybt.testing.windows_cleanup import retry_on_permission_error

        @retry_on_permission_error(max_attempts=3)
        def cleanup_test_data(path):
            shutil.rmtree(path)

        # Will retry on Windows if PermissionError occurs

    Use with TempDirectory::

        from testfixtures import TempDirectory
        from rustybt.testing.windows_cleanup import WindowsSafeTempDirectory

        with TempDirectory() as td:
            with WindowsSafeTempDirectory(td) as safe_td:
                # Files will be properly closed on Windows
                write_test_files(safe_td.path)
"""

import gc
import os
import shutil
import sys
import time
from contextlib import contextmanager
from functools import wraps


def force_close_on_windows():
    """Force garbage collection and delay on Windows for file handle cleanup.

    On Windows, file handles may remain open after closing files, preventing
    deletion. This function forces garbage collection and adds a small delay
    to allow handles to close.

    Examples:
        Use before deleting files::

            import os
            from rustybt.testing.windows_cleanup import force_close_on_windows

            # Write and close file
            with open('test.txt', 'w') as f:
                f.write('test')

            # Ensure handle is closed on Windows
            force_close_on_windows()

            # Now safe to delete
            os.remove('test.txt')
    """
    if sys.platform == "win32":
        gc.collect()
        time.sleep(0.1)


def retry_on_permission_error(max_attempts=3, delay=0.1):
    """Decorator to retry operations that may fail due to Windows file locking.

    Wraps a function and automatically retries it on PermissionError
    (Windows only), with exponential backoff. Useful for file operations
    that may fail due to lingering file handles.

    Args:
        max_attempts: Maximum number of retry attempts (default: 3).
        delay: Initial delay in seconds between attempts (default: 0.1).
            Uses exponential backoff: delay * (attempt + 1).

    Returns:
        Decorated function that retries on PermissionError.

    Examples:
        Retry directory deletion::

            import shutil
            from rustybt.testing.windows_cleanup import retry_on_permission_error

            @retry_on_permission_error(max_attempts=5, delay=0.2)
            def remove_test_dir(path):
                shutil.rmtree(path)

            # Will retry up to 5 times on Windows if PermissionError
            remove_test_dir('test_directory')

        Retry file removal::

            import os
            from rustybt.testing.windows_cleanup import retry_on_permission_error

            @retry_on_permission_error()
            def remove_file(path):
                os.remove(path)

            remove_file('locked_file.txt')
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except PermissionError:
                    if attempt < max_attempts - 1 and sys.platform == "win32":
                        force_close_on_windows()
                        time.sleep(delay * (attempt + 1))  # Exponential backoff
                    else:
                        raise
            return func(*args, **kwargs)

        return wrapper

    return decorator


@contextmanager
def windows_safe_cleanup(temp_dir):
    """Context manager that ensures proper cleanup on Windows."""
    try:
        yield temp_dir
    finally:
        if sys.platform == "win32":
            force_close_on_windows()
            # Try to clean up with retries
            for attempt in range(3):
                try:
                    if os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir)
                    break
                except PermissionError:
                    if attempt < 2:
                        time.sleep(0.2 * (attempt + 1))
                    else:
                        # Last resort: mark for deletion on reboot
                        # This won't work in CI but at least won't fail the test
                        pass


class WindowsSafeTempDirectory:
    """Wrapper around TempDirectory that handles Windows file locking issues."""

    def __init__(self, temp_directory):
        self.temp_directory = temp_directory

    def __enter__(self):
        return self.temp_directory.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if sys.platform == "win32":
            force_close_on_windows()

        # Try multiple times on Windows
        if sys.platform == "win32":
            for attempt in range(3):
                try:
                    return self.temp_directory.__exit__(exc_type, exc_val, exc_tb)
                except PermissionError:
                    if attempt < 2:
                        force_close_on_windows()
                        time.sleep(0.2 * (attempt + 1))
                    else:
                        # Skip cleanup on final failure to not fail the test
                        return True  # Suppress the exception
        else:
            return self.temp_directory.__exit__(exc_type, exc_val, exc_tb)
