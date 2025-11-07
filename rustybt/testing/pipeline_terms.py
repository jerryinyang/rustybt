"""Custom pipeline terms for testing lookback windows.

Provides specialized factor and classifier implementations that validate
the correctness of lookback window data during pipeline computation.
These are essential for testing that pipeline infrastructure correctly
maintains historical data windows.

Classes:
    CheckWindowsMixin: Base mixin for window validation logic
    CheckWindowsFactor: Factor that validates lookback windows
    CheckWindowsClassifier: Classifier that validates lookback windows

Examples:
    Validate factor lookback windows::

        import numpy as np
        import pandas as pd
        from rustybt.testing.pipeline_terms import CheckWindowsFactor

        # Define expected window values for asset 1
        expected = {
            1: {
                pd.Timestamp('2023-01-05'): np.array([100, 101, 102, 103, 104]),
                pd.Timestamp('2023-01-06'): np.array([101, 102, 103, 104, 105]),
            }
        }

        # Create factor that validates windows
        factor = CheckWindowsFactor(
            input_=pricing.close,
            window_length=5,
            expected_windows=expected
        )

        # Run pipeline - will raise if windows don't match expected
        result = engine.run_pipeline(
            Pipeline({'check': factor}),
            start_date=pd.Timestamp('2023-01-05'),
            end_date=pd.Timestamp('2023-01-06')
        )

    Validate classifier windows::

        from rustybt.testing.pipeline_terms import CheckWindowsClassifier

        expected_classifier = {
            1: {
                pd.Timestamp('2023-01-05'): np.array(['A', 'A', 'B', 'B', 'B']),
            }
        }

        classifier = CheckWindowsClassifier(
            input_=sector_classifier,
            window_length=5,
            expected_windows=expected_classifier
        )
"""

import numpy as np

from rustybt.pipeline.classifiers.classifier import CustomClassifier
from rustybt.pipeline.factors.factor import CustomFactor
from rustybt.utils.idbox import IDBox

from .predicates import assert_equal


class CheckWindowsMixin:
    """Mixin providing window validation logic for factors and classifiers.

    Implements the compute method that checks lookback windows against
    expected values for specified assets and dates. Used as a base for
    both CheckWindowsFactor and CheckWindowsClassifier.
    """
    params = ("expected_windows",)

    def compute(self, today, assets, out, input_, expected_windows):
        for asset, expected_by_day in expected_windows:
            expected_by_day = expected_by_day.ob

            col_ix = np.searchsorted(assets, asset)
            if assets[col_ix] != asset:
                raise AssertionError("asset %s is not in the window" % asset)

            try:
                expected = expected_by_day[today]
            except KeyError:
                pass
            else:
                expected = np.asanyarray(expected)
                actual = input_[:, col_ix]
                assert_equal(
                    actual,
                    expected,
                    array_decimal=(6 if expected.dtype.kind == "f" else None),
                )

        # output is just latest
        out[:] = input_[-1]


class CheckWindowsClassifier(CheckWindowsMixin, CustomClassifier):
    """A custom classifier that makes assertions about the lookback windows that
    it gets passed.

    Parameters
    ----------
    input_ : Term
        The input term to the classifier.
    window_length : int
        The length of the lookback window.
    expected_windows : dict[int, dict[pd.Timestamp, np.ndarray]]
        For each asset, for each day, what the expected lookback window is.

    Notes:
    -----
    The output of this classifier is the same as ``Latest``. Any assets or days
    not in ``expected_windows`` are not checked.
    """

    def __new__(cls, input_, window_length, expected_windows):
        if input_.dtype.kind == "V":
            dtype = np.dtype("O")
        else:
            dtype = input_.dtype

        return super(CheckWindowsClassifier, cls).__new__(
            cls,
            inputs=[input_],
            dtype=dtype,
            window_length=window_length,
            expected_windows=frozenset((k, IDBox(v)) for k, v in expected_windows.items()),
        )


class CheckWindowsFactor(CheckWindowsMixin, CustomFactor):
    """A custom factor that makes assertions about the lookback windows that
    it gets passed.

    Parameters
    ----------
    input_ : Term
        The input term to the factor.
    window_length : int
        The length of the lookback window.
    expected_windows : dict[int, dict[pd.Timestamp, np.ndarray]]
        For each asset, for each day, what the expected lookback window is.

    Notes:
    -----
    The output of this factor is the same as ``Latest``. Any assets or days
    not in ``expected_windows`` are not checked.
    """

    def __new__(cls, input_, window_length, expected_windows):
        return super(CheckWindowsFactor, cls).__new__(
            cls,
            inputs=[input_],
            dtype=input_.dtype,
            window_length=window_length,
            expected_windows=frozenset((k, IDBox(v)) for k, v in expected_windows.items()),
        )
