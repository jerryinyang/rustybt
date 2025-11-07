"""Utilities for creating public APIs and argument validation decorators.

This module provides helper functions for creating robust public APIs for Pipeline
terms, including decorators that restrict method applicability based on dtype.

The main utility is `restrict_to_dtype`, which creates decorators that ensure
methods are only called on Terms with compatible dtypes, providing clear error
messages when dtype constraints are violated.
"""

from rustybt.utils.input_validation import preprocess


def restrict_to_dtype(dtype, message_template):
    """Create a decorator restricting Term methods to a specific dtype.

    This factory function produces decorators that prevent Term methods from
    being called on Terms with incompatible dtypes. It's conceptually similar
    to `rustybt.utils.input_validation.expect_dtypes`, but provides more
    flexibility for crafting error messages specific to Term method calls.

    Args:
        dtype: The numpy dtype on which the decorated method may be called.
            Only Terms with this exact dtype can call the decorated method.
        message_template: A format string for the error message raised when
            dtype validation fails. The template will be formatted with
            keyword arguments: `method_name`, `expected_dtype`, and
            `received_dtype`.

    Returns:
        A decorator function that validates dtype before executing the
        decorated method.

    Raises:
        TypeError: When the decorated method is called on a Term with a
            dtype that doesn't match the expected dtype.

    Examples:
        Creating a method restricted to float64 factors:

        >>> from rustybt.utils.numpy_utils import float64_dtype
        >>>
        >>> @restrict_to_dtype(
        ...     dtype=float64_dtype,
        ...     message_template=(
        ...         "{method_name}() was called on a factor of dtype {received_dtype}. "
        ...         "{method_name}() requires factors of dtype {expected_dtype}."
        ...     ),
        ... )
        ... def some_factor_method(self, ...):
        ...     # This method can only be called on float64 factors
        ...     return self.stuff_that_requires_being_float64(...)

        Using the decorator on Factor methods:

        >>> from rustybt.pipeline.factors import Factor
        >>> from rustybt.utils.numpy_utils import float64_dtype, int64_dtype
        >>>
        >>> class MyFactor(Factor):
        ...     dtype = int64_dtype
        ...
        ...     @restrict_to_dtype(
        ...         dtype=float64_dtype,
        ...         message_template="Cannot call {method_name}() on {received_dtype}"
        ...     )
        ...     def my_method(self):
        ...         pass
        >>>
        >>> factor = MyFactor()
        >>> factor.my_method()  # Raises TypeError
    """

    def processor(term_method, _, term_instance):
        term_dtype = term_instance.dtype
        if term_dtype != dtype:
            raise TypeError(
                message_template.format(
                    method_name=term_method.__name__,
                    expected_dtype=dtype.name,
                    received_dtype=term_dtype,
                )
            )
        return term_instance

    return preprocess(self=processor)
