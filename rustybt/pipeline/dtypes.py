"""Data type definitions and constraints for Pipeline terms.

This module defines the allowed data types (dtypes) for each category of
Pipeline term: Factors, Filters, and Classifiers. These dtype constraints
ensure type safety and appropriate operations for each term type.

Type Categories:
    - **FACTOR_DTYPES**: Allowed dtypes for Factor terms
    - **FILTER_DTYPES**: Allowed dtypes for Filter terms
    - **CLASSIFIER_DTYPES**: Allowed dtypes for Classifier terms

Allowed Dtypes:
    Factors can have:
        - float64: Standard numerical computations
        - int64: Integer-valued computations
        - datetime64[ns]: Date/time computations

    Filters can have:
        - bool: Boolean True/False values only

    Classifiers can have:
        - object: String/categorical labels (via LabelArray)
        - int64: Integer category codes

Examples:
    >>> from rustybt.pipeline.dtypes import FACTOR_DTYPES, FILTER_DTYPES
    >>> from rustybt.utils.numpy_utils import float64_dtype, bool_dtype
    >>>
    >>> # Check if a dtype is valid for a Factor
    >>> float64_dtype in FACTOR_DTYPES
    True
    >>>
    >>> # Check if a dtype is valid for a Filter
    >>> bool_dtype in FILTER_DTYPES
    True

See Also:
    Factor: Numerical pipeline computations
    Filter: Boolean pipeline computations
    Classifier: Categorical pipeline computations
"""

from rustybt.utils.numpy_utils import (
    bool_dtype,
    datetime64ns_dtype,
    float64_dtype,
    int64_dtype,
    object_dtype,
)

CLASSIFIER_DTYPES = frozenset({object_dtype, int64_dtype})
FACTOR_DTYPES = frozenset({datetime64ns_dtype, float64_dtype, int64_dtype})
FILTER_DTYPES = frozenset({bool_dtype})
