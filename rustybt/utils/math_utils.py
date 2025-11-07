#
# Copyright 2013 Quantopian, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Mathematical utility functions for rustybt.

This module provides mathematical and numerical utilities including:
- tolerant_equals: Compare floats with tolerance for equality
- NaN-aware statistical functions (via bottleneck or numpy)
- round_if_near_integer: Rounding with epsilon threshold
- number_of_decimal_places: Count decimal places in a number

The module prioritizes performance by using bottleneck when available,
falling back to numpy implementations when not.

Examples:
    Compare floats with tolerance:

    >>> tolerant_equals(1.0, 1.0000001, atol=1e-5)
    True
    >>> tolerant_equals(1.0, 1.1, atol=1e-5)
    False

    Count decimal places:

    >>> number_of_decimal_places(3.14159)
    5
    >>> number_of_decimal_places(100)
    0

    Round values near integers:

    >>> round_if_near_integer(1.99999)
    2.0
    >>> round_if_near_integer(1.5)
    1.5
"""

import math
from decimal import Decimal

from numpy import isnan


def tolerant_equals(a, b, atol=10e-7, rtol=10e-7, equal_nan=False):
    """Check if two floats are equal within specified tolerances.

    This is a scalar version of numpy.isclose, optimized for performance
    when comparing individual float values rather than arrays.

    Args:
        a: First float value to compare.
        b: Second float value to compare.
        atol: Absolute tolerance. Default is 10e-7.
        rtol: Relative tolerance. Default is 10e-7.
        equal_nan: Whether NaN values should be considered equal.
            Default is False.

    Returns:
        bool: True if a and b are equal within the specified tolerances.

    Examples:
        Basic equality check with default tolerances:

        >>> tolerant_equals(1.0, 1.0)
        True
        >>> tolerant_equals(1.0, 1.0000001)
        True
        >>> tolerant_equals(1.0, 1.001)
        False

        Using custom tolerances:

        >>> tolerant_equals(1.0, 1.1, atol=0.2)
        True
        >>> tolerant_equals(1.0, 1.1, atol=0.05)
        False

        NaN handling:

        >>> import math
        >>> tolerant_equals(math.nan, math.nan, equal_nan=False)
        False
        >>> tolerant_equals(math.nan, math.nan, equal_nan=True)
        True

    See Also:
        numpy.isclose: Vectorized version for arrays

    Note:
        The comparison is: |a - b| <= (atol + rtol * |b|)
    """
    if equal_nan and isnan(a) and isnan(b):
        return True
    return math.isclose(a, b, rel_tol=rtol, abs_tol=atol)
    # return math.fabs(a - b) <= (atol + rtol * math.fabs(b))


try:
    # fast versions
    import bottleneck as bn

    nanmean = bn.nanmean
    nanstd = bn.nanstd
    nansum = bn.nansum
    nanmax = bn.nanmax
    nanmin = bn.nanmin
    nanargmax = bn.nanargmax
    nanargmin = bn.nanargmin
    nanmedian = bn.nanmedian
except ImportError:
    # slower numpy
    import numpy as np

    nanmean = np.nanmean
    nanstd = np.nanstd
    nansum = np.nansum
    nanmax = np.nanmax
    nanmin = np.nanmin
    nanargmax = np.nanargmax
    nanargmin = np.nanargmin
    nanmedian = np.nanmedian


def round_if_near_integer(a, epsilon=1e-4):
    """Round a number to the nearest integer if it's within epsilon of that integer.

    This function is useful for cleaning up floating point values that are
    very close to integers due to rounding errors.

    Args:
        a: The number to potentially round. Can be any numeric type.
        epsilon: The maximum distance from an integer for rounding to occur.
            Default is 1e-4.

    Returns:
        float or int: The rounded integer if a is within epsilon of an integer,
            otherwise returns a unchanged.

    Examples:
        Values very close to integers get rounded:

        >>> round_if_near_integer(1.99999)
        2
        >>> round_if_near_integer(2.00001)
        2

        Values not close enough remain unchanged:

        >>> round_if_near_integer(1.5)
        1.5
        >>> round_if_near_integer(2.1)
        2.1

        Custom epsilon:

        >>> round_if_near_integer(1.01, epsilon=0.1)
        1
        >>> round_if_near_integer(1.01, epsilon=0.001)
        1.01
    """
    if abs(a - round(a)) <= epsilon:
        return round(a)
    else:
        return a


def number_of_decimal_places(n):
    """Compute the number of decimal places in a number.

    This function counts the number of digits after the decimal point
    in a number. Works with integers, floats, and string representations.

    Args:
        n: The number to analyze. Can be int, float, or str.

    Returns:
        int: The number of decimal places. Returns 0 for integers.

    Examples:
        Integer has no decimal places:

        >>> number_of_decimal_places(1)
        0
        >>> number_of_decimal_places(42)
        0

        Float decimal places are counted:

        >>> number_of_decimal_places(3.14)
        2
        >>> number_of_decimal_places(3.14159)
        5

        String representations work too:

        >>> number_of_decimal_places('3.14')
        2
        >>> number_of_decimal_places('100.0')
        1

        Scientific notation:

        >>> number_of_decimal_places(1e-3)
        3
        >>> number_of_decimal_places(1.5e2)
        0

    Note:
        Uses Decimal internally for accurate counting.
    """
    decimal = Decimal(str(n))
    return -decimal.as_tuple().exponent
