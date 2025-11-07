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

"""Benchmark data loading for backtesting performance comparison.

This module provides utilities to load benchmark return data for comparing
strategy performance against market indices or other benchmarks.
"""

import logging

import pandas as pd

log = logging.getLogger(__name__)


def get_benchmark_returns_from_file(filelike):
    """Load benchmark returns from a CSV file.

    Reads a CSV file containing daily benchmark returns, typically from a market
    index like S&P 500, and returns them as a time-indexed Series for performance
    comparison in backtests.

    Args:
        filelike: Path to CSV file or file-like object containing benchmark data.
            The CSV must have columns 'date' and 'return'.

    Returns:
        Series indexed by date containing daily benchmark returns, sorted by date
        in ascending order.

    Raises:
        ValueError: If the 'return' column is not found in the CSV file.

    Examples:
        Load S&P 500 benchmark returns:
            >>> returns = get_benchmark_returns_from_file('sp500_returns.csv')
            >>> returns.head()
            date
            2020-01-02    0.0125
            2020-01-03   -0.0089
            2020-01-06    0.0156
            Name: return, dtype: float64

        Use with backtest:
            >>> from rustybt import run_algorithm
            >>> benchmark_returns = get_benchmark_returns_from_file('benchmark.csv')
            >>> results = run_algorithm(
            ...     start=start_date,
            ...     end=end_date,
            ...     initialize=initialize,
            ...     capital_base=100000,
            ...     benchmark_returns=benchmark_returns
            ... )

    Note:
        Expected CSV format:
            date,return
            2020-01-02 00:00:00+00:00,0.01
            2020-01-03 00:00:00+00:00,-0.02
            2020-01-06 00:00:00+00:00,0.015

        - Date column should be parseable as datetime
        - Return column should contain decimal returns (0.01 = 1%)
        - Timezone information in dates will be removed (localized to None)
        - Returns are sorted by date before being returned

    See Also:
        rustybt.finance.performance: Performance metrics calculation
        rustybt.finance.trading: Portfolio construction
    """
    log.info("Reading benchmark returns from %s", filelike)

    df = pd.read_csv(
        filelike,
        index_col=["date"],
        parse_dates=["date"],
    )
    if df.index.tz is not None:
        df = df.tz_localize(None)

    if "return" not in df.columns:
        raise ValueError(
            "The column 'return' not found in the "
            "benchmark file \n"
            "Expected benchmark file format :\n"
            "date, return\n"
            "2020-01-02 00:00:00+00:00,0.01\n"
            "2020-01-03 00:00:00+00:00,-0.02\n"
        )

    return df["return"].sort_index()
