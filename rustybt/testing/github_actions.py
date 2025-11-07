"""GitHub Actions specific test utilities.

Provides decorators and helpers for handling environment-specific test
failures in Continuous Integration, particularly for permission errors
and file locking issues that occur on GitHub Actions runners.

Functions:
    skip_on: Decorator to skip tests when specific exceptions occur

Examples:
    Skip on permission errors::

        from rustybt.testing.github_actions import skip_on

        @skip_on(PermissionError, reason="Windows file locking")
        def test_file_cleanup():
            # Test that may fail on Windows CI
            cleanup_temp_files()

    Skip on multiple exception types::

        @skip_on(OSError, reason="Platform-specific OS issues")
        def test_platform_specific():
            # Test that behaves differently across platforms
            check_filesystem_behavior()
"""

from functools import wraps

import pytest


def skip_on(exception, reason="Ignoring PermissionErrors on GHA"):
    """Decorator to skip tests when specific exceptions occur.

    Wraps a test function and catches specified exceptions, converting
    them to pytest.skip() instead of test failures. Useful for handling
    environment-specific issues in CI that don't represent real bugs.

    Args:
        exception: Exception type or tuple of exception types to catch.
        reason: Message to display when skipping (default: "Ignoring PermissionErrors on GHA").

    Returns:
        Decorated function that skips on the specified exception.

    Examples:
        Skip on permission errors::

            @skip_on(PermissionError)
            def test_file_operations():
                with open('locked.txt', 'w') as f:
                    f.write('test')
                os.remove('locked.txt')

        Skip on multiple exceptions::

            @skip_on((OSError, PermissionError), reason="File system issues")
            def test_filesystem():
                perform_filesystem_operations()
    """
    # Func below is the real decorator and will receive the test function as param
    def decorator_func(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                # Try to run the test
                return f(*args, **kwargs)
            except exception:
                # If certain exception happens, just ignore
                # and raise pytest.skip with given reason
                # if os.environ.get("GITHUB_ACTIONS") == "true":
                pytest.skip(reason)
                # else:
                #     raise

        return wrapper

    return decorator_func
