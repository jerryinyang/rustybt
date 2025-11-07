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

"""Simulation configuration and trading parameters.

This module provides classes for configuring backtesting simulations, including
time periods, capital allocation, data frequency, and trading calendar settings.

The SimulationParameters class encapsulates all the configuration needed to run
a backtest, ensuring consistency between the algorithm's time range and the
available trading calendar.

Examples:
    Creating simulation parameters for a backtest:

    >>> import pandas as pd
    >>> from rustybt.utils.calendars import get_calendar
    >>> from rustybt.finance.trading import SimulationParameters
    >>>
    >>> calendar = get_calendar('NYSE')
    >>> sim_params = SimulationParameters(
    ...     start_session=pd.Timestamp('2020-01-01', tz='UTC'),
    ...     end_session=pd.Timestamp('2020-12-31', tz='UTC'),
    ...     trading_calendar=calendar,
    ...     capital_base=100000.0,
    ...     data_frequency='daily',
    ...     emission_rate='daily'
    ... )
    >>> print(f"Trading from {sim_params.start_session} to {sim_params.end_session}")
    >>> print(f"Starting capital: ${sim_params.capital_base:,.2f}")
"""

import logging

import pandas as pd

from rustybt.utils.memoize import remember_last

log = logging.getLogger("Trading")


DEFAULT_CAPITAL_BASE = 1e5


class SimulationParameters:
    """Configuration parameters for a backtesting simulation.

    This class encapsulates all the parameters needed to run a backtest,
    including the time period, initial capital, data frequency, and trading
    calendar. It automatically adjusts start and end dates to valid trading
    sessions and provides convenient access to derived properties.

    Args:
        start_session (pd.Timestamp): First session of the simulation
        end_session (pd.Timestamp): Last session of the simulation
        trading_calendar (TradingCalendar): Calendar defining trading sessions
        capital_base (float, optional): Starting portfolio value. Defaults to $100,000
        emission_rate (str, optional): Frequency of performance updates ('daily' or 'minute').
            Defaults to 'daily'
        data_frequency (str, optional): Frequency of data bars ('daily' or 'minute').
            Defaults to 'daily'
        arena (str, optional): Simulation environment ('backtest', 'live', etc.).
            Defaults to 'backtest'

    Attributes:
        start_session (pd.Timestamp): Normalized start date (midnight UTC)
        end_session (pd.Timestamp): Normalized end date (midnight UTC)
        capital_base (float): Initial portfolio value
        emission_rate (str): Performance update frequency
        data_frequency (str): Bar data frequency
        arena (str): Simulation environment
        trading_calendar (TradingCalendar): Trading calendar in use
        first_open (pd.Timestamp): Market open time on first session
        last_close (pd.Timestamp): Market close time on last session
        sessions (DatetimeIndex): All trading sessions in the simulation period

    Raises:
        AssertionError: If parameters are invalid (e.g., start after end,
            dates outside calendar range)

    Examples:
        Basic simulation setup:

        >>> from rustybt.utils.calendars import get_calendar
        >>> import pandas as pd
        >>>
        >>> params = SimulationParameters(
        ...     start_session=pd.Timestamp('2020-01-01', tz='UTC'),
        ...     end_session=pd.Timestamp('2020-12-31', tz='UTC'),
        ...     trading_calendar=get_calendar('NYSE'),
        ...     capital_base=50000.0
        ... )
        >>> print(len(params.sessions))  # Number of trading days
        >>> print(params.first_open)  # First market open time
        >>> print(params.last_close)  # Last market close time

        Minute-frequency simulation:

        >>> minute_params = SimulationParameters(
        ...     start_session=pd.Timestamp('2020-01-01', tz='UTC'),
        ...     end_session=pd.Timestamp('2020-01-31', tz='UTC'),
        ...     trading_calendar=get_calendar('NYSE'),
        ...     capital_base=100000.0,
        ...     data_frequency='minute',
        ...     emission_rate='daily'  # Still report daily
        ... )

    Note:
        If start_session or end_session fall on non-trading days, they will be
        automatically adjusted to the nearest valid trading session (forward for
        start, backward for end).
    """
    def __init__(
        self,
        start_session,
        end_session,
        trading_calendar,
        capital_base=DEFAULT_CAPITAL_BASE,
        emission_rate="daily",
        data_frequency="daily",
        arena="backtest",
    ):
        assert type(start_session) is pd.Timestamp
        assert type(end_session) is pd.Timestamp

        assert trading_calendar is not None, "Must pass in trading calendar!"
        assert start_session <= end_session, "Period start falls after period end."
        assert (
            start_session.tz_localize(None) <= trading_calendar.last_session
        ), "Period start falls after the last known trading day."
        assert (
            end_session.tz_localize(None) >= trading_calendar.first_session
        ), "Period end falls before the first known trading day."

        # chop off any minutes or hours on the given start and end dates,
        # as we only support session labels here (and we represent session
        # labels as midnight UTC).
        self._start_session = start_session.normalize()
        self._end_session = end_session.normalize()
        self._capital_base = capital_base

        self._emission_rate = emission_rate
        self._data_frequency = data_frequency

        # copied to algorithm's environment for runtime access
        self._arena = arena

        self._trading_calendar = trading_calendar

        if not trading_calendar.is_session(self._start_session.tz_localize(None)):
            # if the start date is not a valid session in this calendar,
            # push it forward to the first valid session
            self._start_session = trading_calendar.minute_to_session(self._start_session)

        if not trading_calendar.is_session(self._end_session.tz_localize(None)):
            # if the end date is not a valid session in this calendar,
            # pull it backward to the last valid session before the given
            # end date.
            self._end_session = trading_calendar.minute_to_session(
                self._end_session, direction="previous"
            )

        self._first_open = trading_calendar.session_first_minute(
            self._start_session.tz_localize(None)
        )
        self._last_close = trading_calendar.session_close(self._end_session.tz_localize(None))

    @property
    def capital_base(self):
        """Initial portfolio value in base currency."""
        return self._capital_base

    @property
    def emission_rate(self):
        """Frequency of performance metric emissions ('daily' or 'minute')."""
        return self._emission_rate

    @property
    def data_frequency(self):
        """Frequency of bar data ('daily' or 'minute')."""
        return self._data_frequency

    @data_frequency.setter
    def data_frequency(self, val):
        """Set the data frequency."""
        self._data_frequency = val

    @property
    def arena(self):
        """Simulation environment ('backtest', 'live', 'paper', etc.)."""
        return self._arena

    @arena.setter
    def arena(self, val):
        """Set the simulation arena."""
        self._arena = val

    @property
    def start_session(self):
        """First trading session of the simulation (midnight UTC)."""
        return self._start_session

    @property
    def end_session(self):
        """Last trading session of the simulation (midnight UTC)."""
        return self._end_session

    @property
    def first_open(self):
        """Market open timestamp for the first session."""
        return self._first_open

    @property
    def last_close(self):
        """Market close timestamp for the last session."""
        return self._last_close

    @property
    def trading_calendar(self):
        """Trading calendar defining valid sessions and market hours."""
        return self._trading_calendar

    @property
    @remember_last
    def sessions(self):
        """All trading sessions within the simulation period.

        Returns:
            pd.DatetimeIndex: Index of all trading sessions from start to end.
        """
        return self._trading_calendar.sessions_in_range(self.start_session, self.end_session)

    def create_new(self, start_session, end_session, data_frequency=None):
        """Create a new SimulationParameters with a different time range.

        This method creates a new SimulationParameters object with the same
        configuration as the current one, but with a different start and end
        session. Useful for creating sub-periods within a larger simulation.

        Args:
            start_session (pd.Timestamp): New start session
            end_session (pd.Timestamp): New end session
            data_frequency (str, optional): Override data frequency. If None,
                uses the current data_frequency

        Returns:
            SimulationParameters: New parameters object with updated time range

        Examples:
            Creating a subset of the original simulation period:

            >>> original = SimulationParameters(
            ...     start_session=pd.Timestamp('2020-01-01', tz='UTC'),
            ...     end_session=pd.Timestamp('2020-12-31', tz='UTC'),
            ...     trading_calendar=calendar,
            ...     capital_base=100000.0
            ... )
            >>> # Create parameters for just Q1
            >>> q1_params = original.create_new(
            ...     start_session=pd.Timestamp('2020-01-01', tz='UTC'),
            ...     end_session=pd.Timestamp('2020-03-31', tz='UTC')
            ... )
            >>> print(len(q1_params.sessions))  # Fewer sessions
        """
        if data_frequency is None:
            data_frequency = self.data_frequency

        return SimulationParameters(
            start_session,
            end_session,
            self._trading_calendar,
            capital_base=self.capital_base,
            emission_rate=self.emission_rate,
            data_frequency=data_frequency,
            arena=self.arena,
        )

    def __repr__(self):
        return f"""
{self.__class__.__name__}(
    start_session={self.start_session},
    end_session={self.end_session},
    capital_base={self.capital_base},
    data_frequency={self.data_frequency},
    emission_rate={self.emission_rate},
    first_open={self.first_open},
    last_close={self.last_close},
    trading_calendar={self._trading_calendar}
)\
"""
