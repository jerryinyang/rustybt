"""Bar readers for continuous futures contracts.

This module provides bar readers that handle continuous futures, which are
synthetic instruments that roll from one contract to the next based on a
specified rolling strategy. These readers manage the complexity of stitching
together data from multiple underlying futures contracts.
"""
import numpy as np
import pandas as pd

from rustybt.data.session_bars import SessionBarReader


class ContinuousFutureSessionBarReader(SessionBarReader):
    """Bar reader for continuous futures at session (daily) frequency.

    This reader provides session-level OHLCV data for continuous futures by
    stitching together data from the appropriate underlying contracts based on
    the continuous future's rolling strategy.

    Args:
        bar_reader: The underlying session bar reader for futures contracts.
        roll_finders: Dict mapping roll style names to RollFinder instances
            that determine when to roll from one contract to the next.
    """

    def __init__(self, bar_reader, roll_finders):
        self._bar_reader = bar_reader
        self._roll_finders = roll_finders

    def load_raw_arrays(self, columns, start_date, end_date, assets):
        """Load raw OHLCV arrays for continuous futures.

        This method determines which underlying contracts are active for each
        continuous future during the requested time range, loads data for those
        contracts, and assembles the results into continuous time series.

        Args:
            columns: List of column names to load (e.g., 'open', 'close', 'sid').
            start_date: Beginning of the window range.
            end_date: End of the window range.
            assets: List of ContinuousFuture objects.

        Returns:
            list of np.ndarray: A list with an entry per column of ndarrays with
                shape (sessions in range, num assets), containing the values for
                the respective column over the date range.
        """
        rolls_by_asset = {}
        for asset in assets:
            rf = self._roll_finders[asset.roll_style]
            rolls_by_asset[asset] = rf.get_rolls(
                asset.root_symbol, start_date, end_date, asset.offset
            )

        num_sessions = len(self.trading_calendar.sessions_in_range(start_date, end_date))
        shape = num_sessions, len(assets)

        results = []

        tc = self._bar_reader.trading_calendar
        sessions = tc.sessions_in_range(start_date, end_date)

        # Get partitions
        partitions_by_asset = {}
        for asset in assets:
            partitions = []
            partitions_by_asset[asset] = partitions

            rolls = rolls_by_asset[asset]
            start = start_date

            for roll in rolls:
                sid, roll_date = roll
                start_loc = sessions.get_loc(start)

                if roll_date is not None:
                    end = roll_date - sessions.freq
                    end_loc = sessions.get_loc(end)
                else:
                    end = end_date
                    end_loc = len(sessions) - 1

                partitions.append((sid, start, end, start_loc, end_loc))

                if roll_date is not None:
                    start = sessions[end_loc + 1]

        for column in columns:
            if column != "volume" and column != "sid":
                out = np.full(shape, np.nan)
            else:
                out = np.zeros(shape, dtype=np.int64)

            for i, asset in enumerate(assets):
                partitions = partitions_by_asset[asset]

                for sid, start, end, start_loc, end_loc in partitions:
                    if column != "sid":
                        result = self._bar_reader.load_raw_arrays([column], start, end, [sid])[0][
                            :, 0
                        ]
                    else:
                        result = int(sid)
                    out[start_loc : end_loc + 1, i] = result

            results.append(out)

        return results

    @property
    def last_available_dt(self):
        """The last session for which the reader can provide data.

        Returns:
            pd.Timestamp: The last session for which the reader can provide data.
        """
        return self._bar_reader.last_available_dt

    @property
    def trading_calendar(self):
        """The trading calendar used to read the data.

        Returns:
            rustybt.utils.calendar.TradingCalendar or None: The trading calendar
                used to read the data. Can be None if the writer didn't specify it.
        """
        return self._bar_reader.trading_calendar

    @property
    def first_trading_day(self):
        """The first trading day for which the reader can provide data.

        Returns:
            pd.Timestamp: The first trading day (session) for which the reader
                can provide data.
        """
        return self._bar_reader.first_trading_day

    def get_value(self, continuous_future, dt, field):
        """Retrieve the value at the given coordinates.

        Args:
            continuous_future: The ContinuousFuture asset.
            dt: The timestamp for the desired data point.
            field: The OHLVC field name for the desired data point.

        Returns:
            float or int: The value at the given coordinates. Returns float for
                OHLC fields, int for 'volume'.

        Raises:
            NoDataOnDate: If the given dt is not a valid session according to
                this reader's trading calendar.
        """
        rf = self._roll_finders[continuous_future.roll_style]
        sid = rf.get_contract_center(continuous_future.root_symbol, dt, continuous_future.offset)
        return self._bar_reader.get_value(sid, dt, field)

    def get_last_traded_dt(self, asset, dt):
        """Get the latest session on or before dt in which the asset traded.

        If there are no trades on or before dt, returns pd.NaT.

        Args:
            asset: The ContinuousFuture asset for which to get the last
                traded session.
            dt: The timestamp at which to start searching for the last
                traded session.

        Returns:
            pd.Timestamp: The timestamp of the last trade for the given asset,
                using the input dt as a vantage point. Returns pd.NaT if no
                trades found.
        """
        rf = self._roll_finders[asset.roll_style]
        sid = rf.get_contract_center(asset.root_symbol, dt, asset.offset)
        if sid is None:
            return pd.NaT
        contract = rf.asset_finder.retrieve_asset(sid)
        return self._bar_reader.get_last_traded_dt(contract, dt)

    @property
    def sessions(self):
        """All session labels which the reader can provide.

        Returns:
            pd.DatetimeIndex: All session labels (unioning the range for all
                assets) which the reader can provide.
        """
        return self._bar_reader.sessions


class ContinuousFutureMinuteBarReader(SessionBarReader):
    """Bar reader for continuous futures at minute frequency.

    This reader provides minute-level OHLCV data for continuous futures by
    stitching together data from the appropriate underlying contracts based on
    the continuous future's rolling strategy.

    Args:
        bar_reader: The underlying minute bar reader for futures contracts.
        roll_finders: Dict mapping roll style names to RollFinder instances
            that determine when to roll from one contract to the next.
    """

    def __init__(self, bar_reader, roll_finders):
        self._bar_reader = bar_reader
        self._roll_finders = roll_finders

    def load_raw_arrays(self, columns, start_date, end_date, assets):
        """Load raw OHLCV arrays for continuous futures at minute frequency.

        This method determines which underlying contracts are active for each
        continuous future during the requested time range, loads minute-level
        data for those contracts, and assembles the results into continuous
        time series.

        Args:
            columns: List of column names to load (e.g., 'open', 'close', 'volume').
            start_date: Beginning of the window range (minute timestamp).
            end_date: End of the window range (minute timestamp).
            assets: List of ContinuousFuture objects.

        Returns:
            list of np.ndarray: A list with an entry per column of ndarrays with
                shape (minutes in range, num assets), containing the values for
                the respective column over the date range.
        """
        rolls_by_asset = {}

        tc = self.trading_calendar
        start_session = tc.minute_to_session(start_date)
        end_session = tc.minute_to_session(end_date)

        for asset in assets:
            rf = self._roll_finders[asset.roll_style]
            rolls_by_asset[asset] = rf.get_rolls(
                asset.root_symbol, start_session, end_session, asset.offset
            )

        sessions = tc.sessions_in_range(
            start_date.normalize().tz_localize(None),
            end_date.normalize().tz_localize(None),
        )

        minutes = tc.minutes_in_range(start_date, end_date)
        num_minutes = len(minutes)
        shape = num_minutes, len(assets)

        results = []

        # Get partitions
        partitions_by_asset = {}
        for asset in assets:
            partitions = []
            partitions_by_asset[asset] = partitions
            rolls = rolls_by_asset[asset]
            start = start_date
            for roll in rolls:
                sid, roll_date = roll
                start_loc = minutes.searchsorted(start)
                if roll_date is not None:
                    end = tc.session_close(roll_date - sessions.freq)
                    end_loc = minutes.searchsorted(end)
                else:
                    end = end_date
                    end_loc = len(minutes) - 1
                partitions.append((sid, start, end, start_loc, end_loc))
                if roll[-1] is not None:
                    start = tc.session_first_minute(tc.minute_to_session(minutes[end_loc + 1]))

        for column in columns:
            if column != "volume":
                out = np.full(shape, np.nan)
            else:
                out = np.zeros(shape, dtype=np.uint32)
            for i, asset in enumerate(assets):
                partitions = partitions_by_asset[asset]
                for sid, start, end, start_loc, end_loc in partitions:
                    if column != "sid":
                        result = self._bar_reader.load_raw_arrays([column], start, end, [sid])[0][
                            :, 0
                        ]
                    else:
                        result = int(sid)
                    out[start_loc : end_loc + 1, i] = result
            results.append(out)
        return results

    @property
    def last_available_dt(self):
        """The last minute for which the reader can provide data.

        Returns:
            pd.Timestamp: The last minute for which the reader can provide data.
        """
        return self._bar_reader.last_available_dt

    @property
    def trading_calendar(self):
        """The trading calendar used to read the data.

        Returns:
            rustybt.utils.calendar.TradingCalendar or None: The trading calendar
                used to read the data. Can be None if the writer didn't specify it.
        """
        return self._bar_reader.trading_calendar

    @property
    def first_trading_day(self):
        """The first trading day for which the reader can provide data.

        Returns:
            pd.Timestamp: The first trading day (session) for which the reader
                can provide data.
        """
        return self._bar_reader.first_trading_day

    def get_value(self, continuous_future, dt, field):
        """Retrieve the value at the given coordinates.

        Args:
            continuous_future: The ContinuousFuture asset.
            dt: The minute timestamp for the desired data point.
            field: The OHLVC field name for the desired data point.

        Returns:
            float or int: The value at the given coordinates. Returns float for
                OHLC fields, int for 'volume'.

        Raises:
            NoDataOnDate: If the given dt is not a valid market minute according
                to this reader's trading calendar.
        """
        rf = self._roll_finders[continuous_future.roll_style]
        sid = rf.get_contract_center(continuous_future.root_symbol, dt, continuous_future.offset)
        return self._bar_reader.get_value(sid, dt, field)

    def get_last_traded_dt(self, asset, dt):
        """Get the latest minute on or before dt in which the asset traded.

        If there are no trades on or before dt, returns pd.NaT.

        Args:
            asset: The ContinuousFuture asset for which to get the last
                traded minute.
            dt: The minute timestamp at which to start searching for the last
                traded minute.

        Returns:
            pd.Timestamp: The timestamp of the last trade for the given asset,
                using the input dt as a vantage point. Returns pd.NaT if no
                trades found.
        """
        rf = self._roll_finders[asset.roll_style]
        sid = rf.get_contract_center(asset.root_symbol, dt, asset.offset)
        if sid is None:
            return pd.NaT
        contract = rf.asset_finder.retrieve_asset(sid)
        return self._bar_reader.get_last_traded_dt(contract, dt)

    @property
    def sessions(self):
        """All session labels which the reader can provide.

        Returns:
            pd.DatetimeIndex: All session labels which the reader can provide.
        """
        return self._bar_reader.sessions
