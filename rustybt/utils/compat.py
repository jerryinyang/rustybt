"""Compatibility utilities for Python version differences.

This module provides compatibility shims and utilities for handling
differences between Python versions and maintaining backward compatibility
with older APIs.
"""
import functools
import inspect
from collections import namedtuple  # noqa: F401 - compatibility with python 3.11
from contextlib import ExitStack, contextmanager
from html import escape as escape_html
from math import ceil
from types import MappingProxyType as mappingproxy


def consistent_round(val):
    """Round a value consistently using banker's rounding for .5 values.

    Args:
        val: The numeric value to round.

    Returns:
        The rounded integer value.
    """
    if (val % 1) >= 0.5:
        return ceil(val)
    else:
        return round(val)


update_wrapper = functools.update_wrapper
wraps = functools.wraps


def getargspec(f):
    """Get the argument specification of a function (legacy interface).

    This provides compatibility with the old inspect.getargspec API
    that was removed in Python 3.11.

    Args:
        f: The function to inspect.

    Returns:
        An ArgSpec namedtuple with args, varargs, keywords, and defaults.
    """
    ArgSpec = namedtuple(
        "ArgSpec", "args varargs keywords defaults"
    )  # noqa: PYI024 - compatibility with python 3.11
    full_argspec = inspect.getfullargspec(f)
    return ArgSpec(
        args=full_argspec.args,
        varargs=full_argspec.varargs,
        keywords=full_argspec.varkw,
        defaults=full_argspec.defaults,
    )


unicode = str

__all__ = [
    "ExitStack",
    "consistent_round",
    "contextmanager",
    "escape_html",
    "mappingproxy",
    "unicode",
    "update_wrapper",
    "wraps",
]
