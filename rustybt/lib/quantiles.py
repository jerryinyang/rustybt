"""Algorithms for computing quantiles on numpy arrays.

This module provides utilities for computing quantile bins across rows of
2D arrays, useful for ranking and binning data in pipeline operations.

The quantiles function leverages pandas' qcut for efficient quantile
computation with proper handling of edge cases and ties.
"""

# from numpy.lib import apply_along_axis
from numpy import apply_along_axis
from pandas import qcut


def quantiles(data, nbins_or_partition_bounds):
    """Compute rowwise quantile bins for array data.

    Applies quantile binning independently to each row of a 2D array,
    assigning each value to a quantile bin. This is useful for ranking
    securities or normalizing data within each time period.

    Args:
        data: 2D numpy array where each row represents a time period and
            each column represents a different asset or feature.
        nbins_or_partition_bounds: Either:
            - int: Number of equal-sized quantile bins to create
            - array-like: Custom partition boundaries for bins

    Returns:
        2D array of same shape as input, with values replaced by their
        quantile bin indices (0-indexed integers).

    Examples:
        Rank securities into quintiles each day::

            import numpy as np
            from rustybt.lib.quantiles import quantiles

            # 3 days of data for 5 securities
            returns = np.array([
                [0.01, -0.02, 0.03, -0.01, 0.02],
                [0.02,  0.01, -0.01, 0.03, -0.02],
                [-0.01, 0.02,  0.01, -0.02, 0.03]
            ])

            # Compute quintiles for each day
            bins = quantiles(returns, 5)
            # bins[i, j] is the quintile (0-4) of security j on day i

        Use custom boundaries::

            # Bin into terciles with custom boundaries
            bins = quantiles(data, [0.0, 0.33, 0.67, 1.0])
    """
    return apply_along_axis(
        qcut,
        1,
        data,
        q=nbins_or_partition_bounds,
        labels=False,
    )
