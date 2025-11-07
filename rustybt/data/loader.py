#
# Copyright 2016 Quantopian, Inc.
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

"""CSV data loading utilities for rustybt.

This module provides simple utilities to load pricing data from CSV files,
supporting both single files and directories containing multiple CSV files.
"""

import os

import pandas as pd


def load_prices_from_csv(filepath, identifier_col, tz="UTC"):
    """Load OHLCV pricing data from a single CSV file.

    Reads a CSV file containing pricing data, converts the identifier column to a
    timezone-aware DatetimeIndex, and sorts by date.

    Args:
        filepath: Path to the CSV file containing pricing data.
        identifier_col: Name of the column to use as the datetime index.
            This column should contain date or datetime values.
        tz: Timezone for the datetime index. Defaults to 'UTC'.

    Returns:
        DataFrame with DatetimeIndex and OHLCV columns, sorted by date.

    Examples:
        Load daily OHLCV data:
            >>> df = load_prices_from_csv(
            ...     'prices.csv',
            ...     identifier_col='date'
            ... )
            >>> df.head()
                            open    high     low   close  volume
            date
            2020-01-02  100.0  105.0   99.0  103.0   50000
            2020-01-03  103.0  108.0  102.0  107.0   60000

        Load with specific timezone:
            >>> df = load_prices_from_csv(
            ...     'prices.csv',
            ...     identifier_col='timestamp',
            ...     tz='America/New_York'
            ... )

    Note:
        The CSV file should have columns matching OHLCV fields (open, high, low,
        close, volume) or any other pricing data fields needed.
    """
    data = pd.read_csv(filepath, index_col=identifier_col)
    data.index = pd.DatetimeIndex(data.index, tz=tz)
    data.sort_index(inplace=True)
    return data


def load_prices_from_csv_folder(folderpath, identifier_col, tz="UTC"):
    """Load and concatenate pricing data from all CSV files in a directory.

    Reads all CSV files in the specified folder, loads each using
    load_prices_from_csv(), and concatenates them column-wise. This is useful
    when each CSV file contains data for a different asset or time period.

    Args:
        folderpath: Path to directory containing CSV files.
        identifier_col: Name of the column to use as the datetime index
            in each CSV file.
        tz: Timezone for the datetime index. Defaults to 'UTC'.

    Returns:
        DataFrame with all CSV files concatenated column-wise, indexed by date.
        Returns None if no CSV files are found in the folder.

    Examples:
        Load multiple asset files from a folder:
            >>> df = load_prices_from_csv_folder(
            ...     'data/equities/',
            ...     identifier_col='date'
            ... )
            >>> # Columns from all CSV files are concatenated
            >>> df.columns
            Index(['AAPL_open', 'AAPL_close', 'MSFT_open', 'MSFT_close', ...])

        Load with specific timezone:
            >>> df = load_prices_from_csv_folder(
            ...     'data/fx/',
            ...     identifier_col='timestamp',
            ...     tz='UTC'
            ... )

    Note:
        - Only files with '.csv' extension are processed
        - Files are processed in directory iteration order (not guaranteed to be sorted)
        - All CSV files must have compatible schemas for concatenation
        - Non-CSV files in the directory are silently ignored
    """
    data = None
    for file in os.listdir(folderpath):
        if ".csv" not in file:
            continue
        raw = load_prices_from_csv(os.path.join(folderpath, file), identifier_col, tz)
        if data is None:
            data = raw
        else:
            data = pd.concat([data, raw], axis=1)
    return data
