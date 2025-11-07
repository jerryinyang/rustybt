#
# Copyright 2018 Quantopian, Inc.
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

"""Benchmark data source for backtesting performance comparison.

This module provides the BenchmarkSource class which manages benchmark asset
returns for comparing algorithm performance. It handles both asset-based
benchmarks (like SPY) and custom return series, supporting both daily and
minute data frequencies.

The benchmark source pre-calculates returns for the entire simulation period
and provides efficient lookups for performance comparison during backtesting.
"""

import pandas as pd

from rustybt.errors import (
    BenchmarkAssetNotAvailableTooEarly,
    BenchmarkAssetNotAvailableTooLate,
    InvalidBenchmarkAsset,
)


class BenchmarkSource:
    """Manages benchmark returns for backtesting performance comparison.

    Provides pre-calculated benchmark returns for efficient lookup during
    simulation. Supports both asset-based benchmarks (e.g., SPY) and custom
    return series. Handles both daily and minute-frequency data.

    The benchmark source validates the benchmark asset's availability during
    the simulation period and pre-calculates returns adjusted for splits,
    dividends, and mergers.

    Attributes:
        benchmark_asset: The asset to use as a benchmark, or None if using
            custom returns.
        sessions: Trading sessions for the simulation period.
        emission_rate: Data frequency, either 'daily' or 'minute'.
        data_portal: Portal for accessing historical price data.

    Examples:
        Create benchmark from SPY asset::

            benchmark = BenchmarkSource(
                benchmark_asset=spy_asset,
                trading_calendar=calendar,
                sessions=sessions,
                data_portal=portal,
                emission_rate='daily'
            )

            # Get return for a specific date
            daily_return = benchmark.get_value(pd.Timestamp('2020-01-15'))

        Create benchmark from custom returns::

            custom_returns = pd.Series([0.01, -0.02, 0.015], index=sessions)
            benchmark = BenchmarkSource(
                benchmark_asset=None,
                trading_calendar=calendar,
                sessions=sessions,
                data_portal=portal,
                benchmark_returns=custom_returns
            )
    """

    def __init__(
        self,
        benchmark_asset,
        trading_calendar,
        sessions,
        data_portal,
        emission_rate="daily",
        benchmark_returns=None,
    ):
        """Initialize a benchmark source.

        Args:
            benchmark_asset: Asset to use as benchmark, or None if providing
                custom returns.
            trading_calendar: Trading calendar for the simulation.
            sessions: DatetimeIndex of trading sessions.
            data_portal: DataPortal for accessing price history.
            emission_rate: Data frequency, 'daily' or 'minute'. Default 'daily'.
            benchmark_returns: Custom return series to use instead of an asset.
                Should be indexed by session dates. Optional.

        Raises:
            Exception: If neither benchmark_asset nor benchmark_returns is provided.
            BenchmarkAssetNotAvailableTooEarly: If benchmark asset started trading
                after the first simulation session.
            BenchmarkAssetNotAvailableTooLate: If benchmark asset stopped trading
                before the last simulation session.
            InvalidBenchmarkAsset: If benchmark asset has stock dividends.
        """
        self.benchmark_asset = benchmark_asset
        self.sessions = sessions
        self.emission_rate = emission_rate
        self.data_portal = data_portal

        if len(sessions) == 0:
            self._precalculated_series = pd.Series()
        elif benchmark_asset is not None:
            self._validate_benchmark(benchmark_asset)
            (
                self._precalculated_series,
                self._daily_returns,
            ) = self._initialize_precalculated_series(
                benchmark_asset, trading_calendar, sessions, data_portal
            )
        elif benchmark_returns is not None:
            self._daily_returns = daily_series = benchmark_returns.reindex(
                sessions,
            ).fillna(0)

            if self.emission_rate == "minute":
                # we need to take the env's benchmark returns, which are daily,
                # and resample them to minute
                minutes = trading_calendar.sessions_minutes(sessions[0], sessions[-1])
                minute_series = daily_series.tz_localize(minutes.tzinfo).reindex(
                    index=minutes, method="ffill"
                )

                self._precalculated_series = minute_series
            else:
                self._precalculated_series = daily_series
        else:
            raise Exception("Must provide either benchmark_asset or benchmark_returns.")

    def get_value(self, dt):
        """Look up the returns for a given datetime.

        Args:
            dt: The datetime label to look up. Should be a minute timestamp if
                emission_rate is 'minute', or a session date if emission_rate
                is 'daily'.

        Returns:
            The benchmark return at the given datetime.

        Warning:
            This method expects minute inputs if emission_rate is 'minute'
            and session labels when emission_rate is 'daily'.

        See Also:
            daily_returns: Get returns for a range of sessions.
        """
        return self._precalculated_series.loc[dt]

    def get_range(self, start_dt, end_dt):
        """Look up the returns for a given period.

        Args:
            start_dt: The inclusive start datetime label.
            end_dt: The inclusive end datetime label.

        Returns:
            Series of benchmark returns for the specified period.

        Warning:
            This method expects minute inputs if emission_rate is 'minute'
            and session labels when emission_rate is 'daily'.

        See Also:
            daily_returns: Get daily returns for a range of sessions.
            get_value: Get return for a single datetime.
        """
        return self._precalculated_series.loc[start_dt:end_dt]

    def daily_returns(self, start, end=None):
        """Get daily returns for the given period.

        Args:
            start: The inclusive starting session date.
            end: The inclusive ending session date. If not provided, returns
                the scalar value for the start date only. Optional.

        Returns:
            If end is provided, returns a Series of daily returns indexed by
            trading sessions in the range [start, end]. If end is None, returns
            a single float value for the start date.

        Examples:
            Get returns for a single day::

                return_value = benchmark.daily_returns(
                    pd.Timestamp('2020-01-15')
                )

            Get returns for a date range::

                returns_series = benchmark.daily_returns(
                    pd.Timestamp('2020-01-01'),
                    pd.Timestamp('2020-01-31')
                )
        """
        if end is None:
            return self._daily_returns[start]

        return self._daily_returns[start:end]

    def _validate_benchmark(self, benchmark_asset):
        """Validate that a benchmark asset is suitable for the simulation period.

        Checks that the benchmark asset:
        - Does not have stock dividends (which complicate return calculations)
        - Started trading before or on the first simulation session
        - Continued trading through the last simulation session

        Args:
            benchmark_asset: The asset to validate.

        Raises:
            InvalidBenchmarkAsset: If the asset has stock dividends.
            BenchmarkAssetNotAvailableTooEarly: If asset started trading after
                the first simulation session.
            BenchmarkAssetNotAvailableTooLate: If asset stopped trading before
                the last simulation session.
        """
        # check if this security has a stock dividend.  if so, raise an
        # error suggesting that the user pick a different asset to use
        # as benchmark.
        stock_dividends = self.data_portal.get_stock_dividends(self.benchmark_asset, self.sessions)

        if len(stock_dividends) > 0:
            raise InvalidBenchmarkAsset(
                sid=str(self.benchmark_asset), dt=stock_dividends[0]["ex_date"]
            )

        if benchmark_asset.start_date > self.sessions[0]:
            # the asset started trading after the first simulation day
            raise BenchmarkAssetNotAvailableTooEarly(
                sid=str(self.benchmark_asset),
                dt=self.sessions[0],
                start_dt=benchmark_asset.start_date,
            )

        if benchmark_asset.end_date < self.sessions[-1]:
            # the asset stopped trading before the last simulation day
            raise BenchmarkAssetNotAvailableTooLate(
                sid=str(self.benchmark_asset),
                dt=self.sessions[-1],
                end_dt=benchmark_asset.end_date,
            )

    @staticmethod
    def _compute_daily_returns(g):
        """Compute daily return from a group of prices.

        Args:
            g: Array-like of prices, with first element being the opening
                price and last element being the closing price.

        Returns:
            The percent change from first to last price.
        """
        return (g[-1] - g[0]) / g[0]

    @classmethod
    def downsample_minute_return_series(cls, trading_calendar, minutely_returns):
        """Convert minute-frequency returns to daily session returns.

        Takes a series of minute returns and downsamples it to daily returns
        by computing the percent change at each session close.

        Args:
            trading_calendar: Trading calendar for session calculations.
            minutely_returns: Series of minute-frequency returns.

        Returns:
            Series of daily returns indexed by session dates, excluding the
            first session (which has no prior close for comparison).
        """
        sessions = trading_calendar.minutes_to_sessions(
            minutely_returns.index,
        )
        closes = trading_calendar.closes[sessions[0] : sessions[-1]]
        daily_returns = minutely_returns[closes].pct_change()
        daily_returns.index = closes.index
        return daily_returns.iloc[1:]

    def _initialize_precalculated_series(self, asset, trading_calendar, trading_days, data_portal):
        """Pre-calculate benchmark return series for the entire simulation period.

        Retrieves adjusted price history for the benchmark asset and computes
        returns. Prices are fully adjusted for dividends, splits, and mergers.
        For minute-frequency simulations, also computes minute-level returns.

        Special handling for edge cases:
        - If asset started trading on simulation start date, uses open-to-close
          return for the first day instead of prior close comparison.
        - For minute frequency, retrieves minute-level prices and computes both
          minute and daily returns.

        Args:
            asset: The benchmark asset.
            trading_calendar: Trading calendar for the simulation.
            trading_days: DatetimeIndex of trading sessions.
            data_portal: DataPortal for accessing price history.

        Returns:
            Tuple of (returns_series, daily_returns) where:
            - returns_series: Series of returns at the emission frequency
              (minute or daily) indexed by timestamps
            - daily_returns: Series of daily session returns indexed by dates

        Raises:
            ValueError: If asset does not exist during the simulation period.

        Note:
            Validation that the asset covers the simulation period should be
            done before calling this method (via _validate_benchmark).
        """
        if self.emission_rate == "minute":
            minutes = trading_calendar.sessions_minutes(self.sessions[0], self.sessions[-1])
            benchmark_series = data_portal.get_history_window(
                [asset],
                minutes[-1],
                bar_count=len(minutes) + 1,
                frequency="1m",
                field="price",
                data_frequency=self.emission_rate,
                ffill=True,
            )[asset]

            return (
                benchmark_series.pct_change()[1:],
                self.downsample_minute_return_series(
                    trading_calendar,
                    benchmark_series,
                ),
            )

        start_date = asset.start_date
        if start_date < trading_days[0]:
            # get the window of close prices for benchmark_asset from the
            # last trading day of the simulation, going up to one day
            # before the simulation start day (so that we can get the %
            # change on day 1)
            benchmark_series = data_portal.get_history_window(
                [asset],
                trading_days[-1],
                bar_count=len(trading_days) + 1,
                frequency="1d",
                field="price",
                data_frequency=self.emission_rate,
                ffill=True,
            )[asset]

            returns = benchmark_series.pct_change()[1:]
            return returns, returns
        elif start_date == trading_days[0]:
            # Attempt to handle case where stock data starts on first
            # day, in this case use the open to close return.
            benchmark_series = data_portal.get_history_window(
                [asset],
                trading_days[-1],
                bar_count=len(trading_days),
                frequency="1d",
                field="price",
                data_frequency=self.emission_rate,
                ffill=True,
            )[asset]

            # get a minute history window of the first day
            first_open = data_portal.get_spot_value(
                asset,
                "open",
                trading_days[0],
                "daily",
            )
            first_close = data_portal.get_spot_value(
                asset,
                "close",
                trading_days[0],
                "daily",
            )

            first_day_return = (first_close - first_open) / first_open

            returns = benchmark_series.pct_change()[:]
            returns[0] = first_day_return
            return returns, returns
        else:
            raise ValueError(
                "cannot set benchmark to asset that does not exist during"
                " the simulation period (asset start date=%r)" % start_date
            )
