"""Context manager utilities for rustybt.

This module provides utility context managers for various purposes:
- nop_context: A no-op context manager that does nothing
- CallbackManager: Create context managers from pre/post execution callbacks

These utilities are useful for creating optional context managers or for
wrapping operations with custom setup/teardown logic.

Examples:
    Using nop_context as a placeholder:

    >>> with nop_context:
    ...     print("No setup or teardown")
    No setup or teardown

    Using CallbackManager for custom context management:

    >>> def setup(): print("Setting up")
    >>> def teardown(): print("Tearing down")
    >>> manager = CallbackManager(setup, teardown)
    >>> with manager:
    ...     print("Working")
    Setting up
    Working
    Tearing down
"""


@object.__new__
class nop_context:
    """A no-op context manager that performs no operations.

    This context manager does nothing on entry or exit, making it useful
    as a placeholder when a context manager is required but no action
    is needed.

    Examples:
        Use as a simple context manager:

        >>> with nop_context:
        ...     print("Inside context")
        Inside context

        Use as a conditional context manager:

        >>> use_lock = False
        >>> lock = threading.Lock() if use_lock else nop_context
        >>> with lock:
        ...     print("Protected or not")
        Protected or not

    Note:
        This is a singleton created with object.__new__ for efficiency.
    """

    def __enter__(self):
        """Enter the context manager (no-op)."""
        pass

    def __exit__(self, *excinfo):
        """Exit the context manager (no-op).

        Args:
            *excinfo: Exception information (type, value, traceback) if an
                exception occurred, otherwise (None, None, None).
        """
        pass


def _nop(*args, **kwargs):
    """Internal no-op function for default callbacks."""
    pass


class CallbackManager:
    """Create a context manager from pre- and post-execution callbacks.

    This class allows you to create reusable context managers by providing
    setup (pre) and teardown (post) callbacks. The callbacks can accept
    arguments which are provided when entering the context.

    Args:
        pre: A pre-execution callback function. This will be called with
            the provided args and kwargs when entering the context.
            The return value becomes the context manager's enter value.
            Default is a no-op function.
        post: A post-execution callback function. This will be called with
            the provided args and kwargs when exiting the context.
            Default is a no-op function.

    Note:
        The enter value of this context manager will be the result of calling
        pre(*args, **kwargs).

    Examples:
        Basic usage with string formatting:

        >>> def pre(where):
        ...     print('entering %s block' % where)
        >>> def post(where):
        ...     print('exiting %s block' % where)
        >>> manager = CallbackManager(pre, post)
        >>> with manager('example'):
        ...    print('inside example block')
        entering example block
        inside example block
        exiting example block

        Reusable with different arguments:

        >>> with manager('another'):
        ...     print('inside another block')
        entering another block
        inside another block
        exiting another block

        Using without arguments:

        >>> def simple_setup():
        ...     print('Setup')
        ...     return 'resource'
        >>> def simple_teardown():
        ...     print('Teardown')
        >>> manager = CallbackManager(simple_setup, simple_teardown)
        >>> with manager as resource:
        ...     print(f'Using {resource}')
        Setup
        Using resource
        Teardown

        Passing complex data structures:

        >>> def acquire_resources(count, **config):
        ...     print(f'Acquiring {count} resources with {config}')
        ...     return list(range(count))
        >>> def release_resources(count, **config):
        ...     print(f'Releasing {count} resources')
        >>> manager = CallbackManager(acquire_resources, release_resources)
        >>> with manager(3, timeout=30) as resources:
        ...     print(f'Got resources: {resources}')
        Acquiring 3 resources with {'timeout': 30}
        Got resources: [0, 1, 2]
        Releasing 3 resources
    """

    def __init__(self, pre=None, post=None):
        self.pre = pre if pre is not None else _nop
        self.post = post if post is not None else _nop

    def __call__(self, *args, **kwargs):
        return _ManagedCallbackContext(self.pre, self.post, args, kwargs)

    # special case, if no extra args are passed make this a context manager
    # which forwards no args to pre and post
    def __enter__(self):
        return self.pre()

    def __exit__(self, *excinfo):
        self.post()


class _ManagedCallbackContext:
    def __init__(self, pre, post, args, kwargs):
        self._pre = pre
        self._post = post
        self._args = args
        self._kwargs = kwargs

    def __enter__(self):
        return self._pre(*self._args, **self._kwargs)

    def __exit__(self, *excinfo):
        self._post(*self._args, **self._kwargs)
