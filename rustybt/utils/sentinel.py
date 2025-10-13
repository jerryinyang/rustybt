"""
Construction of sentinel objects.

Sentinel objects are used when you only care to check for object identity.
"""

from __future__ import annotations

import sys
from textwrap import dedent
from types import FrameType
from typing import Any


class _Sentinel:
    """Base class for Sentinel objects."""

    __slots__ = ("__weakref__",)


def is_sentinel(obj: Any) -> bool:
    return isinstance(obj, _Sentinel)


def sentinel(name: str, doc: str | None = None) -> type[_Sentinel]:
    cache: dict[str, type[_Sentinel]] = sentinel._cache
    try:
        value = cache[name]  # memoized
    except KeyError:
        pass
    else:
        if doc == value.__doc__:
            return value

        raise ValueError(
            dedent(
                """\
            New sentinel value %r conflicts with an existing sentinel of the
            same name.
            Old sentinel docstring: %r
            New sentinel docstring: %r

            The old sentinel was created at: %s

            Resolve this conflict by changing the name of one of the sentinels.
            """,
            )
            % (name, value.__doc__, doc, getattr(value, "_created_at", "<unknown>"))
        )

    frame: FrameType | None
    try:
        frame = sys._getframe(1)
    except ValueError:
        frame = None

    created_at: str
    if frame is None:
        created_at = "<unknown>"
    else:
        created_at = "%s:%s" % (frame.f_code.co_filename, frame.f_lineno)

    @object.__new__  # bind a single instance to the name 'Sentinel'
    class Sentinel(_Sentinel):
        __doc__ = doc
        __name__ = name

        # store created_at so that we can report this in case of a duplicate
        # name violation
        _created_at = created_at

        def __new__(cls) -> None:  # type: ignore[misc]
            raise TypeError("cannot create %r instances" % name)

        def __repr__(self) -> str:
            return "sentinel(%r)" % name

        def __reduce__(self) -> tuple[Any, tuple[str, str | None]]:
            return sentinel, (name, doc)

        def __deepcopy__(self, _memo: Any) -> _Sentinel:
            return self

        def __copy__(self) -> _Sentinel:
            return self

    cls = type(Sentinel)
    module_name: str | None = None
    if frame is not None:
        try:
            module_name = frame.f_globals["__name__"]
        except KeyError:
            # f_globals doesn't hold '__name__'
            pass
    cls.__module__ = module_name  # type: ignore[assignment]

    cache[name] = Sentinel  # cache result
    return Sentinel


sentinel._cache: dict[str, type[_Sentinel]] = {}  # type: ignore[attr-defined,misc]
