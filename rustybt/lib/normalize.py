"""Row-wise normalization and grouped operations for 2D arrays.

This module provides utilities for applying functions to groups within rows
of 2D arrays. This is useful for sector-neutral normalization, grouped
ranking, and other operations where you want to apply a transformation
independently to different groups within each time period.

The implementation is simple but effective for moderate-sized datasets,
processing each row and each group within that row sequentially.
"""

import numpy as np


def naive_grouped_rowwise_apply(data, group_labels, func, func_args=(), out=None):
    """Apply a function to groups within each row of a 2D array.

    For each row, applies the given function independently to each group of
    values. Groups are defined by the group_labels array. This is useful for
    operations like sector-neutral normalization where you want to normalize
    values within each sector independently each day.

    Args:
        data: 2D input array (typically time x assets).
        group_labels: 2D array of integer group labels, same shape as data.
            Each unique label defines a group.
        func: Function to apply to each group. Should accept a 1D array
            and optional positional arguments, returning a 1D array of the
            same length.
        func_args: Additional positional arguments to pass to func. Optional.
        out: Pre-allocated output array. If not provided, a new array is
            created. Optional.

    Returns:
        2D array of same shape as data, with func applied to each group
        within each row.

    Examples:
        Demean within groups::

            >>> import numpy as np
            >>> data = np.array([[1., 2., 3.],
            ...                  [2., 3., 4.],
            ...                  [5., 6., 7.]])
            >>> labels = np.array([[0, 0, 1],
            ...                    [0, 1, 0],
            ...                    [1, 0, 2]])
            >>> naive_grouped_rowwise_apply(data, labels, lambda row: row - row.min())
            array([[ 0.,  1.,  0.],
                   [ 0.,  0.,  2.],
                   [ 0.,  0.,  0.]])

        Normalize to sum within groups::

            >>> naive_grouped_rowwise_apply(data, labels, lambda row: row / row.sum())
            array([[ 0.33333333,  0.66666667,  1.        ],
                   [ 0.33333333,  1.        ,  0.66666667],
                   [ 1.        ,  1.        ,  1.        ]])

        Sector-neutral z-score normalization::

            def zscore(values):
                return (values - values.mean()) / values.std()

            # Normalize each security relative to its sector each day
            normalized = naive_grouped_rowwise_apply(returns, sector_labels, zscore)
    """
    if out is None:
        out = np.empty_like(data)

    for row, label_row, out_row in zip(data, group_labels, out):
        for label in np.unique(label_row):
            locs = label_row == label
            out_row[locs] = func(row[locs], *func_args)
    return out
