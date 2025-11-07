"""Sentinel values for Pipeline term default parameters.

This module defines sentinel values used throughout the Pipeline API to
distinguish between "not specified" and explicit None values. This is
particularly important for optional parameters where None might be a valid
value distinct from "parameter not provided."

Sentinels:
    NotSpecified: Singleton sentinel indicating a parameter was not provided
    NotSpecifiedType: Type of the NotSpecified sentinel

Usage Pattern:
    Sentinel values allow APIs to distinguish three states:
    1. Parameter explicitly set to a value (including None)
    2. Parameter not provided (NotSpecified)
    3. Parameter set to default class-level value

Example:
    >>> from rustybt.pipeline.sentinels import NotSpecified, NotSpecifiedType
    >>> from rustybt.utils.input_validation import expect_types
    >>>
    >>> class MyTerm:
    ...     default_mask = None
    ...
    ...     @expect_types(mask=(Filter, NotSpecifiedType))
    ...     def __init__(self, mask=NotSpecified):
    ...         if mask is NotSpecified:
    ...             # Use class default
    ...             mask = self.default_mask
    ...         elif mask is None:
    ...             # Explicitly set to None (different meaning)
    ...             mask = self._process_none_mask()
    ...         self.mask = mask

    Checking for NotSpecified:

    >>> def my_function(value=NotSpecified):
    ...     if value is NotSpecified:
    ...         print("Value was not provided")
    ...         value = get_default()
    ...     return value

See Also:
    rustybt.utils.sentinel: Sentinel creation utility
    Term: Base class using NotSpecified for defaults
"""

from rustybt.utils.sentinel import sentinel

NotSpecified = sentinel(
    "NotSpecified",
    "Singleton sentinel value used for Term defaults.",
)

NotSpecifiedType = type(NotSpecified)
