"""Utility library for array operations and data structures.

This package provides specialized array types and utilities for efficient
data processing in backtesting pipelines:

- adjusted_array: Arrays with adjustment support for corporate actions
- labelarray: Efficient categorical/string array implementation
- normalize: Row-wise normalization and grouping operations
- quantiles: Quantile calculation utilities

These utilities are optimized for pipeline operations on large datasets,
with support for windowing, categorical data, and efficient memory usage.

Examples:
    Import specific utilities::

        from rustybt.lib.labelarray import LabelArray
        from rustybt.lib.adjusted_array import AdjustedArray
        from rustybt.lib.quantiles import quantiles

    The modules can be imported directly as submodules without circular
    dependency issues.
"""
# Module imports handled directly by importers to avoid circular dependencies
# All submodules can be imported directly (e.g., from rustybt.lib.labelarray import LabelArray)
__all__ = ["labelarray", "adjusted_array", "normalize", "quantiles"]
