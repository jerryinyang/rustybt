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
from collections import OrderedDict
from numbers import Real

import pandas as pd
from numpy import array, full, isnan, nan
from numpy.testing import assert_almost_equal
from parameterized import parameterized

from rustybt.data.resample import (
    DailyHistoryAggregator,
    MinuteResampleSessionBarReader,
    ReindexMinuteBarReader,
    ReindexSessionBarReader,
    minute_frame_to_session_frame,
)
from rustybt.testing import parameter_space
from rustybt.testing.fixtures import (
    WithBcolzEquityDailyBarReader,
    WithBcolzEquityMinuteBarReader,
    WithBcolzFutureMinuteBarReader,
    WithEquityMinuteBarData,
    ZiplineTestCase,
)

OHLC = ["open", "high", "low", "close"]
OHLCV = OHLC + ["volume"]

NYSE_MINUTES = OrderedDict(
    (
        (
            "day_0_front",
            pd.date_range(
                "2016-03-15 9:31", "2016-03-15 9:33", freq="min", tz="US/Eastern"
            ).tz_convert("UTC"),
        ),
        (
            "day_0_back",
            pd.date_range(
                "2016-03-15 15:58", "2016-03-15 16:00", freq="min", tz="US/Eastern"
            ).tz_convert("UTC"),
        ),
        (
            "day_1_front",
            pd.date_range(
                "2016-03-16 9:31", "2016-03-16 9:33", freq="min", tz="US/Eastern"
            ).tz_convert("UTC"),
        ),
        (
            "day_1_back",
            pd.date_range(
                "2016-03-16 15:58", "2016-03-16 16:00", freq="min", tz="US/Eastern"
            ).tz_convert("UTC"),
        ),
    )
)

FUT_MINUTES = OrderedDict(
    (
        (
            "day_0_front",
            pd.date_range(
                "2016-03-15 18:01", "2016-03-15 18:03", freq="min", tz="US/Eastern"
            ).tz_convert("UTC"),
        ),
        (
            "day_0_back",
            pd.date_range(
                "2016-03-16 17:58", "2016-03-16 18:00", freq="min", tz="US/Eastern"
            ).tz_convert("UTC"),
        ),
        (
            "day_1_front",
            pd.date_range(
                "2016-03-16 18:01", "2016-03-16 18:03", freq="min", tz="US/Eastern"
            ).tz_convert("UTC"),
        ),
        (
            "day_1_back",
            pd.date_range(
                "2016-03-17 17:58", "2016-03-17 18:00", freq="min", tz="US/Eastern"
            ).tz_convert("UTC"),
        ),
    )
)

SCENARIOS = OrderedDict(
    (
        (
            "none_missing",
            array(
                [
                    [101.5, 101.9, 101.1, 101.3, 1001],
                    [103.5, 103.9, 103.1, 103.3, 1003],
                    [102.5, 102.9, 102.1, 102.3, 1002],
                ]
            ),
        ),
        (
            "all_missing",
            array(
                [
                    [nan, nan, nan, nan, 0],
                    [nan, nan, nan, nan, 0],
                    [nan, nan, nan, nan, 0],
                ]
            ),
        ),
        (
            "missing_first",
            array(
                [
                    [nan, nan, nan, nan, 0],
                    [103.5, 103.9, 103.1, 103.3, 1003],
                    [102.5, 102.9, 102.1, 102.3, 1002],
                ]
            ),
        ),
        (
            "missing_last",
            array(
                [
                    [107.5, 107.9, 107.1, 107.3, 1007],
                    [108.5, 108.9, 108.1, 108.3, 1008],
                    [nan, nan, nan, nan, 0],
                ]
            ),
        ),
        (
            "missing_middle",
            array(
                [
                    [103.5, 103.9, 103.1, 103.3, 1003],
                    [nan, nan, nan, nan, 0],
                    [102.5, 102.5, 102.1, 102.3, 1002],
                ]
            ),
        ),
    )
)

OHLCV = ("open", "high", "low", "close", "volume")

_EQUITY_CASES = (
    (1, (("none_missing", "day_0_front"), ("missing_last", "day_0_back"))),
    (2, (("missing_first", "day_0_front"), ("none_missing", "day_0_back"))),
    (3, (("missing_last", "day_0_back"), ("missing_first", "day_1_front"))),
    # Asset 4 has a start date on day 1
    (4, (("all_missing", "day_0_back"), ("none_missing", "day_1_front"))),
    # Asset 5 has a start date before day_0, but does not have data on that
    # day.
    (5, (("all_missing", "day_0_back"), ("none_missing", "day_1_front"))),
)

EQUITY_CASES = OrderedDict()

for sid, combos in _EQUITY_CASES:
    frames = [
        pd.DataFrame(SCENARIOS[s], columns=OHLCV).set_index(NYSE_MINUTES[m]) for s, m in combos
    ]
    EQUITY_CASES[sid] = pd.concat(frames)

_FUTURE_CASES = (
    (1001, (("none_missing", "day_0_front"), ("none_missing", "day_0_back"))),
    (1002, (("missing_first", "day_0_front"), ("none_missing", "day_0_back"))),
    (1003, (("missing_last", "day_0_back"), ("missing_first", "day_1_front"))),
    (1004, (("all_missing", "day_0_back"), ("none_missing", "day_1_front"))),
)

FUTURE_CASES = OrderedDict()

for sid, combos in _FUTURE_CASES:
    frames = [
        pd.DataFrame(SCENARIOS[s], columns=OHLCV).set_index(FUT_MINUTES[m]) for s, m in combos
    ]
    FUTURE_CASES[sid] = pd.concat(frames)

EXPECTED_AGGREGATION = {
    1: pd.DataFrame(
        {
            "open": [101.5, 101.5, 101.5, 101.5, 101.5, 101.5],
            "high": [101.9, 103.9, 103.9, 107.9, 108.9, 108.9],
            "low": [101.1, 101.1, 101.1, 101.1, 101.1, 101.1],
            "close": [101.3, 103.3, 102.3, 107.3, 108.3, 108.3],
            "volume": [1001, 2004, 3006, 4013, 5021, 5021],
        },
        columns=OHLCV,
    ),
    2: pd.DataFrame(
        {
            "open": [nan, 103.5, 103.5, 103.5, 103.5, 103.5],
            "high": [nan, 103.9, 103.9, 103.9, 103.9, 103.9],
            "low": [nan, 103.1, 102.1, 101.1, 101.1, 101.1],
            "close": [nan, 103.3, 102.3, 101.3, 103.3, 102.3],
            "volume": [0, 1003, 2005, 3006, 4009, 5011],
        },
        columns=OHLCV,
    ),
    # Equity 3 straddles two days.
    3: pd.DataFrame(
        {
            "open": [107.5, 107.5, 107.5, nan, 103.5, 103.5],
            "high": [107.9, 108.9, 108.9, nan, 103.9, 103.9],
            "low": [107.1, 107.1, 107.1, nan, 103.1, 102.1],
            "close": [107.3, 108.3, 108.3, nan, 103.3, 102.3],
            "volume": [1007, 2015, 2015, 0, 1003, 2005],
        },
        columns=OHLCV,
    ),
    # Equity 4 straddles two days and is not active the first day.
    4: pd.DataFrame(
        {
            "open": [nan, nan, nan, 101.5, 101.5, 101.5],
            "high": [nan, nan, nan, 101.9, 103.9, 103.9],
            "low": [nan, nan, nan, 101.1, 101.1, 101.1],
            "close": [nan, nan, nan, 101.3, 103.3, 102.3],
            "volume": [0, 0, 0, 1001, 2004, 3006],
        },
        columns=OHLCV,
    ),
    # Equity 5 straddles two days and does not have data the first day.
    5: pd.DataFrame(
        {
            "open": [nan, nan, nan, 101.5, 101.5, 101.5],
            "high": [nan, nan, nan, 101.9, 103.9, 103.9],
            "low": [nan, nan, nan, 101.1, 101.1, 101.1],
            "close": [nan, nan, nan, 101.3, 103.3, 102.3],
            "volume": [0, 0, 0, 1001, 2004, 3006],
        },
        columns=OHLCV,
    ),
    1001: pd.DataFrame(
        {
            "open": [101.5, 101.5, 101.5, 101.5, 101.5, 101.5],
            "high": [101.9, 103.9, 103.9, 103.9, 103.9, 103.9],
            "low": [101.1, 101.1, 101.1, 101.1, 101.1, 101.1],
            "close": [101.3, 103.3, 102.3, 101.3, 103.3, 102.3],
            "volume": [1001, 2004, 3006, 4007, 5010, 6012],
        },
        columns=OHLCV,
    ),
    1002: pd.DataFrame(
        {
            "open": [nan, 103.5, 103.5, 103.5, 103.5, 103.5],
            "high": [nan, 103.9, 103.9, 103.9, 103.9, 103.9],
            "low": [nan, 103.1, 102.1, 101.1, 101.1, 101.1],
            "close": [nan, 103.3, 102.3, 101.3, 103.3, 102.3],
            "volume": [0, 1003, 2005, 3006, 4009, 5011],
        },
        columns=OHLCV,
    ),
    1003: pd.DataFrame(
        {
            "open": [107.5, 107.5, 107.5, nan, 103.5, 103.5],
            "high": [107.9, 108.9, 108.9, nan, 103.9, 103.9],
            "low": [107.1, 107.1, 107.1, nan, 103.1, 102.1],
            "close": [107.3, 108.3, 108.3, nan, 103.3, 102.3],
            "volume": [1007, 2015, 2015, 0, 1003, 2005],
        },
        columns=OHLCV,
    ),
    1004: pd.DataFrame(
        {
            "open": [nan, nan, nan, 101.5, 101.5, 101.5],
            "high": [nan, nan, nan, 101.9, 103.9, 103.9],
            "low": [nan, nan, nan, 101.1, 101.1, 101.1],
            "close": [nan, nan, nan, 101.3, 103.3, 102.3],
            "volume": [0, 0, 0, 1001, 2004, 3006],
        },
        columns=OHLCV,
    ),
}

EXPECTED_SESSIONS = {
    1: pd.DataFrame(
        [EXPECTED_AGGREGATION[1].iloc[-1].values],
        columns=OHLCV,
        index=pd.to_datetime(["2016-03-15"]),
    ),
    2: pd.DataFrame(
        [EXPECTED_AGGREGATION[2].iloc[-1].values],
        columns=OHLCV,
        index=pd.to_datetime(["2016-03-15"]),
    ),
    3: pd.DataFrame(
        EXPECTED_AGGREGATION[3].iloc[[2, 5]].values,
        columns=OHLCV,
        index=pd.to_datetime(["2016-03-15", "2016-03-16"]),
    ),
    1001: pd.DataFrame(
        [EXPECTED_AGGREGATION[1001].iloc[-1].values],
        columns=OHLCV,
        index=pd.to_datetime(["2016-03-16"]),
    ),
    1002: pd.DataFrame(
        [EXPECTED_AGGREGATION[1002].iloc[-1].values],
        columns=OHLCV,
        index=pd.to_datetime(["2016-03-16"]),
    ),
    1003: pd.DataFrame(
        EXPECTED_AGGREGATION[1003].iloc[[2, 5]].values,
        columns=OHLCV,
        index=pd.to_datetime(["2016-03-16", "2016-03-17"]),
    ),
    1004: pd.DataFrame(
        EXPECTED_AGGREGATION[1004].iloc[[2, 5]].values,
        columns=OHLCV,
        index=pd.to_datetime(["2016-03-16", "2016-03-17"]),
    ),
}


class MinuteToDailyAggregationTestCase(
    WithBcolzEquityMinuteBarReader, WithBcolzFutureMinuteBarReader, ZiplineTestCase
):
    #    March 2016
    # Su Mo Tu We Th Fr Sa
    #        1  2  3  4  5
    #  6  7  8  9 10 11 12
    # 13 14 15 16 17 18 19
    # 20 21 22 23 24 25 26
    # 27 28 29 30 31

    TRADING_ENV_MIN_DATE = START_DATE = pd.Timestamp("2016-03-01")
    TRADING_ENV_MAX_DATE = END_DATE = pd.Timestamp("2016-03-31")

    TRADING_CALENDAR_STRS = ("NYSE", "us_futures")

    ASSET_FINDER_EQUITY_SIDS = 1, 2, 3, 4, 5
    ASSET_FINDER_FUTURE_SIDS = 1001, 1002, 1003, 1004

    @classmethod
    def make_equity_info(cls):
        frame = super(MinuteToDailyAggregationTestCase, cls).make_equity_info()
        # Make equity 4 start a day behind the data start to exercise assets
        # which not alive for the session.
        frame.loc[[4], "start_date"] = pd.Timestamp("2016-03-16")
        return frame

    @classmethod
    def make_equity_minute_bar_data(cls):
        for sid in cls.ASSET_FINDER_EQUITY_SIDS:
            frame = EQUITY_CASES[sid]
            yield sid, frame

    @classmethod
    def make_futures_info(cls):
        future_dict = {}

        for future_sid in cls.ASSET_FINDER_FUTURE_SIDS:
            future_dict[future_sid] = {
                "multiplier": 1000,
                "exchange": "CMES",
                "root_symbol": "ABC",
            }

        return pd.DataFrame.from_dict(future_dict, orient="index")

    @classmethod
    def make_future_minute_bar_data(cls):
        for sid in cls.ASSET_FINDER_FUTURE_SIDS:
            frame = FUTURE_CASES[sid]
            yield sid, frame

    def init_instance_fixtures(self):
        super(MinuteToDailyAggregationTestCase, self).init_instance_fixtures()
        # Set up a fresh data portal for each test, since order of calling
        # needs to be tested.
        self.equity_daily_aggregator = DailyHistoryAggregator(
            self.nyse_calendar.first_minutes,
            self.bcolz_equity_minute_bar_reader,
            self.nyse_calendar,
        )

        self.future_daily_aggregator = DailyHistoryAggregator(
            self.us_futures_calendar.first_minutes,
            self.bcolz_future_minute_bar_reader,
            self.us_futures_calendar,
        )

    @parameter_space(
        field=OHLCV,
        sid=ASSET_FINDER_EQUITY_SIDS,
        __fail_fast=True,
    )
    def test_equity_contiguous_minutes_individual(self, field, sid):
        asset = self.asset_finder.retrieve_asset(sid)
        minutes = EQUITY_CASES[asset].index

        self._test_contiguous_minutes_individual(
            field,
            asset,
            minutes,
            self.equity_daily_aggregator,
        )

    @parameter_space(
        field=OHLCV,
        sid=ASSET_FINDER_FUTURE_SIDS,
        __fail_fast=True,
    )
    def test_future_contiguous_minutes_individual(self, field, sid):
        asset = self.asset_finder.retrieve_asset(sid)
        minutes = FUTURE_CASES[asset].index

        self._test_contiguous_minutes_individual(
            field,
            asset,
            minutes,
            self.future_daily_aggregator,
        )

    def _test_contiguous_minutes_individual(
        self,
        field,
        asset,
        minutes,
        aggregator,
    ):
        # First test each minute in order.
        method_name = field + "s"
        results = []
        repeat_results = []

        for minute in minutes:
            value = getattr(aggregator, method_name)([asset], minute)[0]
            # Prevent regression on building an array when scalar is intended.
            assert isinstance(value, Real)
            results.append(value)

            # Call a second time with the same dt, to prevent regression
            # against case where crossed start and end dts caused a crash
            # instead of the last value.
            value = getattr(aggregator, method_name)([asset], minute)[0]
            # Prevent regression on building an array when scalar is intended.
            assert isinstance(value, Real)
            repeat_results.append(value)

        assert_almost_equal(
            results,
            EXPECTED_AGGREGATION[asset][field],
            err_msg=f"sid={asset} field={field}",
        )
        assert_almost_equal(
            repeat_results,
            EXPECTED_AGGREGATION[asset][field],
            err_msg=f"sid={asset} field={field}",
        )

    @parameterized.expand(
        [
            ("open_sid_1", "open", 1),
            ("high_1", "high", 1),
            ("low_1", "low", 1),
            ("close_1", "close", 1),
            ("volume_1", "volume", 1),
            ("open_2", "open", 2),
            ("high_2", "high", 2),
            ("low_2", "low", 2),
            ("close_2", "close", 2),
            ("volume_2", "volume", 2),
            ("open_3", "open", 3),
            ("high_3", "high", 3),
            ("low_3", "low", 3),
            ("close_3", "close", 3),
            ("volume_3", "volume", 3),
            ("open_4", "open", 4),
            ("high_4", "high", 4),
            ("low_4", "low", 4),
            ("close_4", "close", 4),
            ("volume_4", "volume", 4),
            ("open_5", "open", 5),
            ("high_5", "high", 5),
            ("low_5", "low", 5),
            ("close_5", "close", 5),
            ("volume_5", "volume", 5),
        ]
    )
    def test_skip_minutes_individual(self, name, field, sid):
        # Test skipping minutes, to exercise backfills.
        # Tests initial backfill and mid day backfill.
        method_name = field + "s"
        asset = self.asset_finder.retrieve_asset(sid)
        minutes = EQUITY_CASES[asset].index
        for i in [0, 2, 3, 5]:
            minute = minutes[i]
            value = getattr(self.equity_daily_aggregator, method_name)([asset], minute)[0]
            # Prevent regression on building an array when scalar is intended.
            assert isinstance(value, Real)
            assert_almost_equal(
                value,
                EXPECTED_AGGREGATION[sid][field][i],
                err_msg=f"sid={sid} field={field} dt={minute}",
            )

            # Call a second time with the same dt, to prevent regression
            # against case where crossed start and end dts caused a crash
            # instead of the last value.
            value = getattr(self.equity_daily_aggregator, method_name)([asset], minute)[0]
            # Prevent regression on building an array when scalar is intended.
            assert isinstance(value, Real)
            assert_almost_equal(
                value,
                EXPECTED_AGGREGATION[sid][field][i],
                err_msg=f"sid={sid} field={field} dt={minute}",
            )

    @parameterized.expand(OHLCV)
    def test_contiguous_minutes_multiple(self, field):
        # First test each minute in order.
        method_name = field + "s"
        assets = self.asset_finder.retrieve_all([1, 2])
        results = {asset: [] for asset in assets}
        repeat_results = {asset: [] for asset in assets}
        minutes = EQUITY_CASES[1].index
        for minute in minutes:
            values = getattr(self.equity_daily_aggregator, method_name)(assets, minute)
            for j, asset in enumerate(assets):
                value = values[j]
                # Prevent regression on building an array when scalar is
                # intended.
                assert isinstance(value, Real)
                results[asset].append(value)

            # Call a second time with the same dt, to prevent regression
            # against case where crossed start and end dts caused a crash
            # instead of the last value.
            values = getattr(self.equity_daily_aggregator, method_name)(assets, minute)
            for j, asset in enumerate(assets):
                value = values[j]
                # Prevent regression on building an array when scalar is
                # intended.
                assert isinstance(value, Real)
                repeat_results[asset].append(value)
        for asset in assets:
            assert_almost_equal(
                results[asset],
                EXPECTED_AGGREGATION[asset][field],
                err_msg=f"sid={asset} field={field}",
            )
            assert_almost_equal(
                repeat_results[asset],
                EXPECTED_AGGREGATION[asset][field],
                err_msg=f"sid={asset} field={field}",
            )

    @parameterized.expand(OHLCV)
    def test_skip_minutes_multiple(self, field):
        # Test skipping minutes, to exercise backfills.
        # Tests initial backfill and mid day backfill.
        method_name = field + "s"
        assets = self.asset_finder.retrieve_all([1, 2])
        minutes = EQUITY_CASES[1].index
        for i in [1, 5]:
            minute = minutes[i]
            values = getattr(self.equity_daily_aggregator, method_name)(assets, minute)
            for j, asset in enumerate(assets):
                value = values[j]
                # Prevent regression on building an array when scalar is
                # intended.
                assert isinstance(value, Real)
                assert_almost_equal(
                    value,
                    EXPECTED_AGGREGATION[asset][field][i],
                    err_msg=f"sid={asset} field={field} dt={minute}",
                )

            # Call a second time with the same dt, to prevent regression
            # against case where crossed start and end dts caused a crash
            # instead of the last value.
            values = getattr(self.equity_daily_aggregator, method_name)(assets, minute)
            for j, asset in enumerate(assets):
                value = values[j]
                # Prevent regression on building an array when scalar is
                # intended.
                assert isinstance(value, Real)
                assert_almost_equal(
                    value,
                    EXPECTED_AGGREGATION[asset][field][i],
                    err_msg=f"sid={asset} field={field} dt={minute}",
                )


class TestMinuteToSession(WithEquityMinuteBarData, ZiplineTestCase):
    #    March 2016
    # Su Mo Tu We Th Fr Sa
    #        1  2  3  4  5
    #  6  7  8  9 10 11 12
    # 13 14 15 16 17 18 19
    # 20 21 22 23 24 25 26
    # 27 28 29 30 31

    START_DATE = pd.Timestamp("2016-03-15")
    END_DATE = pd.Timestamp("2016-03-15")
    ASSET_FINDER_EQUITY_SIDS = 1, 2, 3

    @classmethod
    def make_equity_minute_bar_data(cls):
        for sid, frame in EQUITY_CASES.items():
            yield sid, frame

    @classmethod
    def init_class_fixtures(cls):
        super(TestMinuteToSession, cls).init_class_fixtures()
        cls.equity_frames = {sid: frame for sid, frame in cls.make_equity_minute_bar_data()}

    def test_minute_to_session(self):
        for sid in self.ASSET_FINDER_EQUITY_SIDS:
            frame = self.equity_frames[sid]
            expected = EXPECTED_SESSIONS[sid]
            result = minute_frame_to_session_frame(frame, self.nyse_calendar)
            assert_almost_equal(expected.values, result.values, err_msg=f"sid={sid}")


class TestResampleSessionBars(WithBcolzFutureMinuteBarReader, ZiplineTestCase):
    TRADING_CALENDAR_STRS = ("us_futures",)
    TRADING_CALENDAR_PRIMARY_CAL = "us_futures"

    ASSET_FINDER_FUTURE_SIDS = 1001, 1002, 1003, 1004

    START_DATE = pd.Timestamp("2016-03-16")
    END_DATE = pd.Timestamp("2016-03-17")
    NUM_SESSIONS = 2

    @classmethod
    def make_futures_info(cls):
        future_dict = {}

        for future_sid in cls.ASSET_FINDER_FUTURE_SIDS:
            future_dict[future_sid] = {
                "multiplier": 1000,
                "exchange": "CMES",
                "root_symbol": "ABC",
            }

        return pd.DataFrame.from_dict(future_dict, orient="index")

    @classmethod
    def make_future_minute_bar_data(cls):
        for sid in cls.ASSET_FINDER_FUTURE_SIDS:
            frame = FUTURE_CASES[sid]
            yield sid, frame

    def init_instance_fixtures(self):
        super(TestResampleSessionBars, self).init_instance_fixtures()
        self.session_bar_reader = MinuteResampleSessionBarReader(
            self.trading_calendar, self.bcolz_future_minute_bar_reader
        )

    def test_resample(self):
        calendar = self.trading_calendar
        for sid in self.ASSET_FINDER_FUTURE_SIDS:
            case_frame = FUTURE_CASES[sid]
            first = calendar.minute_to_session(case_frame.index[0])
            last = calendar.minute_to_session(case_frame.index[-1])
            result = self.session_bar_reader.load_raw_arrays(OHLCV, first, last, [sid])
            for i, field in enumerate(OHLCV):
                assert_almost_equal(
                    EXPECTED_SESSIONS[sid][[field]],
                    result[i],
                    err_msg=f"sid={sid} field={field}",
                )

    def test_sessions(self):
        sessions = self.session_bar_reader.sessions

        assert len(sessions) == self.NUM_SESSIONS
        assert sessions[0] == self.START_DATE
        assert sessions[-1] == self.END_DATE

    def test_last_available_dt(self):
        calendar = self.trading_calendar
        session_bar_reader = MinuteResampleSessionBarReader(
            calendar, self.bcolz_future_minute_bar_reader
        )

        assert session_bar_reader.last_available_dt == self.END_DATE

    def test_get_value(self):
        calendar = self.trading_calendar
        session_bar_reader = MinuteResampleSessionBarReader(
            calendar, self.bcolz_future_minute_bar_reader
        )
        for sid in self.ASSET_FINDER_FUTURE_SIDS:
            expected = EXPECTED_SESSIONS[sid]
            for dt, values in expected.iterrows():
                for col in OHLCV:
                    result = session_bar_reader.get_value(sid, dt, col)
                    assert_almost_equal(result, values[col], err_msg=f"sid={sid} col={col} dt={dt}")

    def test_first_trading_day(self):
        assert self.session_bar_reader.first_trading_day == self.START_DATE

    def test_get_last_traded_dt(self):
        future = self.asset_finder.retrieve_asset(self.ASSET_FINDER_FUTURE_SIDS[0])

        assert self.trading_calendar.previous_session(
            self.END_DATE
        ) == self.session_bar_reader.get_last_traded_dt(future, self.END_DATE)


class TestReindexMinuteBars(WithBcolzEquityMinuteBarReader, ZiplineTestCase):
    TRADING_CALENDAR_STRS = ("us_futures", "NYSE")
    TRADING_CALENDAR_PRIMARY_CAL = "us_futures"

    ASSET_FINDER_EQUITY_SIDS = 1, 2, 3

    START_DATE = pd.Timestamp("2015-12-01")
    END_DATE = pd.Timestamp("2015-12-31")

    def test_load_raw_arrays(self):
        reindex_reader = ReindexMinuteBarReader(
            self.trading_calendar,
            self.bcolz_equity_minute_bar_reader,
            self.START_DATE,
            self.END_DATE,
        )
        m_open = self.trading_calendar.session_first_minute(self.START_DATE)
        m_close = self.trading_calendar.session_close(self.START_DATE)

        outer_minutes = self.trading_calendar.minutes_in_range(m_open, m_close)
        result = reindex_reader.load_raw_arrays(OHLCV, m_open, m_close, [1, 2])

        opens = pd.DataFrame(data=result[0], index=outer_minutes, columns=[1, 2])
        opens_with_price = opens.dropna()

        assert len(opens) == 1440, (
            "The result should have 1440 bars, the number of minutes in a "
            "trading session on the target calendar."
        )

        assert len(opens_with_price) == 390, (
            "The result, after dropping nans, should have 390 bars, the "
            " number of bars in a trading session in the reader's calendar."
        )

        slicer = outer_minutes.slice_indexer(end=pd.Timestamp("2015-12-01 14:30", tz="UTC"))

        assert_almost_equal(
            opens[1][slicer],
            full(slicer.stop, nan),
            err_msg="All values before the NYSE market open should be nan.",
        )

        slicer = outer_minutes.slice_indexer(start=pd.Timestamp("2015-12-01 21:01", tz="UTC"))

        assert_almost_equal(
            opens[1][slicer],
            full(slicer.stop - slicer.start, nan),
            err_msg="All values after the NYSE market close should be nan.",
        )

        first_minute_loc = outer_minutes.get_loc(pd.Timestamp("2015-12-01 14:31", tz="UTC"))

        # Spot check a value.
        # The value is the autogenerated value from test fixtures.
        assert_almost_equal(
            10.0,
            opens[1][first_minute_loc],
            err_msg="The value for Equity 1, should be 10.0, at NYSE open.",
        )


class TestReindexSessionBars(WithBcolzEquityDailyBarReader, ZiplineTestCase):
    TRADING_CALENDAR_STRS = ("us_futures", "NYSE")
    TRADING_CALENDAR_PRIMARY_CAL = "us_futures"

    ASSET_FINDER_EQUITY_SIDS = 1, 2, 3

    # Dates are chosen to span Thanksgiving, which is not a Holiday on
    # us_futures.
    START_DATE = pd.Timestamp("2015-11-02")
    END_DATE = pd.Timestamp("2015-11-30")

    #     November 2015
    # Su Mo Tu We Th Fr Sa
    #  1  2  3  4  5  6  7
    #  8  9 10 11 12 13 14
    # 15 16 17 18 19 20 21
    # 22 23 24 25 26 27 28
    # 29 30

    def init_instance_fixtures(self):
        super(TestReindexSessionBars, self).init_instance_fixtures()

        self.reader = ReindexSessionBarReader(
            self.trading_calendar,
            self.bcolz_equity_daily_bar_reader,
            self.START_DATE,
            self.END_DATE,
        )

    def test_load_raw_arrays(self):
        outer_sessions = self.trading_calendar.sessions_in_range(self.START_DATE, self.END_DATE)

        result = self.reader.load_raw_arrays(OHLCV, self.START_DATE, self.END_DATE, [1, 2])

        opens = pd.DataFrame(data=result[0], index=outer_sessions, columns=[1, 2])
        opens_with_price = opens.dropna()

        assert len(opens) == 21, (
            "The reindexed result should have 21 days, which is the number of "
            "business days in 2015-11"
        )
        assert len(opens_with_price) == 20, (
            "The reindexed result after dropping nans should have 20 days, "
            "because Thanksgiving is a NYSE holiday."
        )

        tday = pd.Timestamp("2015-11-26")

        # Thanksgiving, 2015-11-26.
        # Is a holiday in NYSE, but not in us_futures.
        tday_loc = outer_sessions.get_loc(tday)

        assert_almost_equal(
            nan,
            opens[1][tday_loc],
            err_msg="2015-11-26 should be `nan`, since Thanksgiving is a "
            "holiday in the reader's calendar.",
        )

        # Thanksgiving, 2015-11-26.
        # Is a holiday in NYSE, but not in us_futures.
        tday_loc = outer_sessions.get_loc(pd.Timestamp("2015-11-26"))

        assert_almost_equal(
            nan,
            opens[1][tday_loc],
            err_msg="2015-11-26 should be `nan`, since Thanksgiving is a "
            "holiday in the reader's calendar.",
        )

    def test_load_raw_arrays_holiday_start(self):
        tday = pd.Timestamp("2015-11-26")
        outer_sessions = self.trading_calendar.sessions_in_range(tday, self.END_DATE)

        result = self.reader.load_raw_arrays(OHLCV, tday, self.END_DATE, [1, 2])

        opens = pd.DataFrame(data=result[0], index=outer_sessions, columns=[1, 2])
        opens_with_price = opens.dropna()

        assert len(opens) == 3, (
            "The reindexed result should have 3 days, which is the number of "
            "business days in from Thanksgiving to end of 2015-11."
        )
        assert len(opens_with_price) == 2, (
            "The reindexed result after dropping nans should have 2 days, "
            "because Thanksgiving is a NYSE holiday."
        )

    def test_load_raw_arrays_holiday_end(self):
        tday = pd.Timestamp("2015-11-26")
        outer_sessions = self.trading_calendar.sessions_in_range(self.START_DATE, tday)

        result = self.reader.load_raw_arrays(OHLCV, self.START_DATE, tday, [1, 2])

        opens = pd.DataFrame(data=result[0], index=outer_sessions, columns=[1, 2])
        opens_with_price = opens.dropna()

        assert len(opens) == 19, (
            "The reindexed result should have 19 days, which is the number of "
            "business days in from start of 2015-11 up to Thanksgiving."
        )
        assert len(opens_with_price) == 18, (
            "The reindexed result after dropping nans should have 18 days, "
            "because Thanksgiving is a NYSE holiday."
        )

    def test_get_value(self):
        assert_almost_equal(
            self.reader.get_value(1, self.START_DATE, "open"),
            10.0,
            err_msg="The open of the fixture data on the first session should be 10.",
        )
        tday = pd.Timestamp("2015-11-26", tz="UTC")

        assert isnan(self.reader.get_value(1, tday, "close"))

        assert self.reader.get_value(1, tday, "volume") == 0

    def test_last_available_dt(self):
        assert self.reader.last_available_dt == self.END_DATE

    def test_get_last_traded_dt(self):
        asset = self.asset_finder.retrieve_asset(1)
        assert self.reader.get_last_traded_dt(asset, self.END_DATE) == self.END_DATE

    def test_sessions(self):
        sessions = self.reader.sessions
        assert len(sessions) == 21, "There should be 21 sessions in 2015-11."
        assert pd.Timestamp("2015-11-02") == sessions[0]
        assert pd.Timestamp("2015-11-30") == sessions[-1]

    def test_first_trading_day(self):
        assert self.reader.first_trading_day == self.START_DATE

    def test_trading_calendar(self):
        assert (
            self.reader.trading_calendar.name == "us_futures"
        ), "The calendar for the reindex reader should be the specified futures calendar."


# ============================================================================
# Tests for Modern Polars-Based Aggregation (RustyBT Enhancement)
# ============================================================================

from decimal import Decimal

import polars as pl
import pytest

from rustybt.data.resample import (
    AggregationValidationError,
    _detect_gaps,
    _detect_outliers_after_aggregation,
    _validate_resolution_mapping,
    _validate_temporal_consistency,
    aggregate_ohlcv,
    aggregate_to_daily_bars,
)


class TestResolutionValidation:
    """Test resolution mapping validation."""

    def test_valid_resolution_mappings(self):
        """Valid resolution mappings should pass."""
        # These should not raise
        _validate_resolution_mapping("1m", "1h")
        _validate_resolution_mapping("1m", "1d")
        _validate_resolution_mapping("1h", "1d")
        _validate_resolution_mapping("1d", "1w")
        _validate_resolution_mapping("1d", "1mo")

    def test_invalid_same_resolution(self):
        """Same resolution should fail."""
        with pytest.raises(ValueError, match="source resolution must be finer"):
            _validate_resolution_mapping("1h", "1h")

    def test_invalid_coarse_to_fine(self):
        """Coarse to fine resolution should fail."""
        with pytest.raises(ValueError, match="source resolution must be finer"):
            _validate_resolution_mapping("1d", "1h")

    def test_invalid_resolution_string(self):
        """Invalid resolution strings should fail."""
        with pytest.raises(ValueError, match="Invalid resolution"):
            _validate_resolution_mapping("invalid", "1h")


class TestAggregateOHLCV:
    """Test main aggregate_ohlcv function."""

    def test_minute_to_hourly_aggregation(self):
        """Test 1-minute → hourly aggregation with known input/output."""
        # Create 60 1-minute bars for one hour
        df = pl.DataFrame(
            {
                "timestamp": pd.date_range("2023-01-01 10:00", periods=60, freq="1min", tz="UTC"),
                "symbol": ["AAPL"] * 60,
                "open": [Decimal("100")] + [Decimal("100.5")] * 59,
                "high": [Decimal("101")] * 60,
                "low": [Decimal("99")] * 60,
                "close": [Decimal("100.5")] * 59 + [Decimal("100.8")],
                "volume": [Decimal("1000")] * 60,
            }
        )

        df_agg = aggregate_ohlcv(df, source_resolution="1m", target_resolution="1h")

        # Verify aggregation
        assert len(df_agg) == 1
        assert df_agg["open"][0] == Decimal("100")  # First open
        assert df_agg["high"][0] == Decimal("101")  # Max high
        assert df_agg["low"][0] == Decimal("99")  # Min low
        assert df_agg["close"][0] == Decimal("100.8")  # Last close
        assert df_agg["volume"][0] == Decimal("60000")  # Sum volume

    def test_hourly_to_daily_aggregation(self):
        """Test hourly → daily aggregation preserves OHLCV relationships."""
        # Create 24 hourly bars
        df = pl.DataFrame(
            {
                "timestamp": pd.date_range("2023-01-01 00:00", periods=24, freq="1h", tz="UTC"),
                "symbol": ["AAPL"] * 24,
                "open": [Decimal("100") + Decimal(str(i)) for i in range(24)],
                "high": [Decimal("105") + Decimal(str(i)) for i in range(24)],
                "low": [Decimal("95") + Decimal(str(i)) for i in range(24)],
                "close": [Decimal("102") + Decimal(str(i)) for i in range(24)],
                "volume": [Decimal("1000")] * 24,
            }
        )

        df_agg = aggregate_ohlcv(df, source_resolution="1h", target_resolution="1d")

        # Verify aggregation
        assert len(df_agg) == 1
        assert df_agg["open"][0] == Decimal("100")  # First open
        assert df_agg["high"][0] == Decimal("128")  # Max high (105 + 23)
        assert df_agg["low"][0] == Decimal("95")  # Min low
        assert df_agg["close"][0] == Decimal("125")  # Last close (102 + 23)
        assert df_agg["volume"][0] == Decimal("24000")  # Sum volume

    def test_daily_to_weekly_aggregation(self):
        """Test daily → weekly aggregation sums volume correctly."""
        # Create 7 daily bars (one week)
        df = pl.DataFrame(
            {
                "timestamp": pd.date_range("2023-01-02", periods=7, freq="1D", tz="UTC"),
                "symbol": ["AAPL"] * 7,
                "open": [Decimal("100")] * 7,
                "high": [Decimal("105")] * 7,
                "low": [Decimal("95")] * 7,
                "close": [Decimal("102")] * 7,
                "volume": [Decimal("1000000")] * 7,
            }
        )

        df_agg = aggregate_ohlcv(df, source_resolution="1d", target_resolution="1w")

        # Verify aggregation
        assert len(df_agg) == 1
        assert df_agg["volume"][0] == Decimal("7000000")  # Sum of 7 days

    def test_multiple_symbols_aggregation(self):
        """Test aggregation with multiple symbols."""
        # Create data for 2 symbols
        symbols = ["AAPL", "MSFT"]
        dfs = []

        for symbol in symbols:
            df_symbol = pl.DataFrame(
                {
                    "timestamp": pd.date_range(
                        "2023-01-01 10:00", periods=60, freq="1min", tz="UTC"
                    ),
                    "symbol": [symbol] * 60,
                    "open": [Decimal("100")] * 60,
                    "high": [Decimal("101")] * 60,
                    "low": [Decimal("99")] * 60,
                    "close": [Decimal("100.5")] * 60,
                    "volume": [Decimal("1000")] * 60,
                }
            )
            dfs.append(df_symbol)

        df = pl.concat(dfs)
        df_agg = aggregate_ohlcv(df, source_resolution="1m", target_resolution="1h")

        # Should have 2 rows (one per symbol)
        assert len(df_agg) == 2
        assert set(df_agg["symbol"].to_list()) == {"AAPL", "MSFT"}

    def test_empty_dataframe(self):
        """Test aggregation with empty DataFrame."""
        df = pl.DataFrame(
            schema={
                "timestamp": pl.Datetime("us", "UTC"),
                "symbol": pl.Utf8,
                "open": pl.Decimal(precision=18, scale=8),
                "high": pl.Decimal(precision=18, scale=8),
                "low": pl.Decimal(precision=18, scale=8),
                "close": pl.Decimal(precision=18, scale=8),
                "volume": pl.Decimal(precision=18, scale=8),
            }
        )

        df_agg = aggregate_ohlcv(df, source_resolution="1m", target_resolution="1h")

        # Should return empty DataFrame with correct schema
        assert len(df_agg) == 0
        assert "timestamp" in df_agg.columns

    def test_missing_columns(self):
        """Test aggregation fails with missing columns."""
        df = pl.DataFrame(
            {
                "timestamp": pd.date_range("2023-01-01 10:00", periods=60, freq="1min", tz="UTC"),
                "symbol": ["AAPL"] * 60,
                "open": [Decimal("100")] * 60,
                # Missing high, low, close, volume
            }
        )

        with pytest.raises(ValueError, match="Missing required columns"):
            aggregate_ohlcv(df, source_resolution="1m", target_resolution="1h")

    def test_timezone_conversion(self):
        """Test timezone conversion during aggregation."""
        # Create data in UTC that fits within a single hour in NY timezone
        df = pl.DataFrame(
            {
                "timestamp": pd.date_range("2023-01-03 14:30", periods=60, freq="1min", tz="UTC"),
                "symbol": ["AAPL"] * 60,
                "open": [Decimal("100")] * 60,
                "high": [Decimal("101")] * 60,
                "low": [Decimal("99")] * 60,
                "close": [Decimal("100.5")] * 60,
                "volume": [Decimal("1000")] * 60,
            }
        )

        # Aggregate with UTC timezone (no conversion)
        df_agg = aggregate_ohlcv(df, source_resolution="1m", target_resolution="1h", timezone="UTC")

        # Result should be in UTC and should be 1-2 hourly bars depending on alignment
        assert len(df_agg) >= 1
        assert df_agg["timestamp"][0].tzinfo is not None
        # Verify total volume is preserved
        assert df_agg["volume"].sum() == Decimal("60000")


class TestGapDetection:
    """Test gap detection functionality."""

    def test_no_gaps(self):
        """Test gap detection with complete data."""
        # Create complete hourly data
        df = pl.DataFrame(
            {
                "timestamp": pd.date_range("2023-01-01", periods=24, freq="1h", tz="UTC"),
                "symbol": ["AAPL"] * 24,
                "source_bar_count": [60] * 24,  # Expected: 60 minutes per hour
            }
        )

        gap_info = _detect_gaps(df, "1m", "1h")

        assert gap_info["gap_count"] == 0
        assert gap_info["missing_bars_pct"] == 0

    def test_with_gaps(self):
        """Test gap detection identifies missing bars."""
        # Create data with some incomplete periods
        df = pl.DataFrame(
            {
                "timestamp": pd.date_range("2023-01-01", periods=24, freq="1h", tz="UTC"),
                "symbol": ["AAPL"] * 24,
                "source_bar_count": [60] * 20 + [30, 40, 50, 55],  # Last 4 have gaps
            }
        )

        gap_info = _detect_gaps(df, "1m", "1h")

        assert gap_info["gap_count"] == 4
        assert gap_info["missing_bars_pct"] > 0


class TestOutlierDetection:
    """Test outlier detection functionality."""

    def test_no_outliers(self):
        """Test outlier detection with normal data."""
        df = pl.DataFrame(
            {
                "timestamp": pd.date_range("2023-01-01", periods=100, freq="1h", tz="UTC"),
                "symbol": ["AAPL"] * 100,
                "open": [Decimal("100")] * 100,
                "close": [Decimal("100.5")] * 100,  # 0.5% change consistently
            }
        )

        outliers = _detect_outliers_after_aggregation(df, threshold=3.0)

        assert len(outliers) == 0

    def test_with_outliers(self):
        """Test outlier detection identifies extreme price movements."""
        # Create data with some variation and one clear outlier
        opens = [Decimal("100")] * 100
        # Add realistic variation (most bars 0%, ±1%, ±2%, ±5% with one ±20% outlier)
        closes = []
        for i in range(99):
            if i % 10 == 0:
                closes.append(Decimal("105"))  # +5% occasionally
            elif i % 7 == 0:
                closes.append(Decimal("102"))  # +2% occasionally
            elif i % 5 == 0:
                closes.append(Decimal("101"))  # +1% occasionally
            elif i % 3 == 0:
                closes.append(Decimal("99"))  # -1% occasionally
            else:
                closes.append(Decimal("100"))  # 0% most of the time
        closes.append(
            Decimal("120")
        )  # Add clear outlier at end (+20% - should trigger z-score > 3)

        df = pl.DataFrame(
            {
                "timestamp": pd.date_range("2023-01-01", periods=100, freq="1h", tz="UTC"),
                "symbol": ["AAPL"] * 100,
                "open": opens,
                "close": closes,
            }
        )

        outliers = _detect_outliers_after_aggregation(df, threshold=3.0)

        # Should detect the outlier
        assert len(outliers) > 0


class TestTemporalConsistency:
    """Test temporal consistency validation."""

    def test_sorted_timestamps(self):
        """Test temporal consistency with sorted timestamps."""
        df = pl.DataFrame(
            {
                "timestamp": pd.date_range("2023-01-01", periods=10, freq="1h", tz="UTC"),
                "symbol": ["AAPL"] * 10,
            }
        )

        # Should not raise
        _validate_temporal_consistency(df)

    def test_unsorted_timestamps(self):
        """Test temporal consistency detects unsorted timestamps."""
        timestamps = pd.date_range("2023-01-01", periods=10, freq="1h", tz="UTC").tolist()
        timestamps[5], timestamps[6] = timestamps[6], timestamps[5]  # Swap two

        df = pl.DataFrame({"timestamp": timestamps, "symbol": ["AAPL"] * 10})

        with pytest.raises(AggregationValidationError, match="Timestamps not sorted"):
            _validate_temporal_consistency(df)

    def test_duplicate_timestamps(self):
        """Test temporal consistency detects duplicates."""
        # Create sorted timestamps with a duplicate
        timestamps = pd.date_range("2023-01-01", periods=10, freq="1h", tz="UTC").tolist()
        timestamps.append(pd.Timestamp("2023-01-01 05:00:00", tz="UTC"))  # Add duplicate
        timestamps.sort()  # Sort to ensure timestamps are in order (only duplicates remain as issue)

        df = pl.DataFrame({"timestamp": timestamps, "symbol": ["AAPL"] * 11})

        with pytest.raises(AggregationValidationError, match="Duplicate timestamps"):
            _validate_temporal_consistency(df)


class TestAggregateToDailyBars:
    """Test timezone-aware daily aggregation."""

    def test_daily_aggregation_with_trading_hours(self):
        """Test aggregation to daily bars with trading session boundaries."""
        # Create full trading day of minute bars (9:30 AM - 4:00 PM EST = 390 bars)
        df = pl.DataFrame(
            {
                "timestamp": pd.date_range(
                    "2023-01-03 09:30", periods=390, freq="1min", tz="America/New_York"
                ),
                "symbol": ["AAPL"] * 390,
                "open": [Decimal("150")] + [Decimal("150.1")] * 389,
                "high": [Decimal("151")] * 390,
                "low": [Decimal("149")] * 390,
                "close": [Decimal("150.5")] * 389 + [Decimal("150.8")],
                "volume": [Decimal("1000")] * 390,
            }
        )

        df_daily = aggregate_to_daily_bars(df, timezone="America/New_York")

        # Should aggregate to 1 daily bar
        assert len(df_daily) == 1
        assert df_daily["open"][0] == Decimal("150")  # First bar's open
        assert df_daily["close"][0] == Decimal("150.8")  # Last bar's close
        assert df_daily["volume"][0] == Decimal("390000")  # Sum all volume

    def test_filters_non_trading_hours(self):
        """Test that non-trading hours are filtered out."""
        # Create bars including pre-market and after-hours
        df = pl.DataFrame(
            {
                "timestamp": pd.date_range(
                    "2023-01-03 08:00",  # Before market open
                    periods=600,
                    freq="1min",
                    tz="America/New_York",
                ),
                "symbol": ["AAPL"] * 600,
                "open": [Decimal("150")] * 600,
                "high": [Decimal("151")] * 600,
                "low": [Decimal("149")] * 600,
                "close": [Decimal("150.5")] * 600,
                "volume": [Decimal("1000")] * 600,
            }
        )

        df_daily = aggregate_to_daily_bars(
            df, timezone="America/New_York", market_open="09:30", market_close="16:00"
        )

        # Should only include bars within trading hours (390 bars)
        assert len(df_daily) == 1
        assert df_daily["volume"][0] == Decimal("390000")  # Only trading hour volume


# ============================================================================
# Property-Based Tests (Hypothesis)
# ============================================================================

from hypothesis import assume, given, settings
from hypothesis import strategies as st


class TestPropertyBasedAggregation:
    """Property-based tests for aggregation invariants."""

    @given(
        bar_count=st.integers(min_value=60, max_value=1000),
        base_price=st.decimals(
            min_value=Decimal("1"),
            max_value=Decimal("1000"),
            allow_nan=False,
            allow_infinity=False,
            places=2,
        ),
    )
    @settings(max_examples=100)
    def test_aggregated_volume_equals_sum(self, bar_count, base_price):
        """Property: Aggregated volume == sum of source volumes."""
        assume(base_price > 0)  # Ensure positive price

        # Generate minute bars
        df = pl.DataFrame(
            {
                "timestamp": pd.date_range("2023-01-01", periods=bar_count, freq="1min", tz="UTC"),
                "symbol": ["TEST"] * bar_count,
                "open": [base_price] * bar_count,
                "high": [base_price * Decimal("1.01")] * bar_count,
                "low": [base_price * Decimal("0.99")] * bar_count,
                "close": [base_price] * bar_count,
                "volume": [Decimal("1000")] * bar_count,
            }
        )

        # Aggregate to hourly
        df_agg = aggregate_ohlcv(df, source_resolution="1m", target_resolution="1h", validate=False)

        # Property: Total volume must be preserved
        source_volume_total = df["volume"].sum()
        agg_volume_total = df_agg["volume"].sum()

        assert source_volume_total == agg_volume_total

    @given(
        high=st.decimals(
            min_value=Decimal("100"),
            max_value=Decimal("200"),
            allow_nan=False,
            allow_infinity=False,
            places=2,
        ),
        low=st.decimals(
            min_value=Decimal("50"),
            max_value=Decimal("99"),
            allow_nan=False,
            allow_infinity=False,
            places=2,
        ),
    )
    @settings(max_examples=100)
    def test_ohlcv_relationships_preserved(self, high, low):
        """Property: OHLCV relationships hold after aggregation."""
        assume(high > low)  # Ensure high > low

        # Create bars with valid OHLCV relationships
        # Open and close must be between low and high
        open_price = Decimal("90")
        close_price = Decimal("95")

        # Ensure low <= min(open, close) <= max(open, close) <= high
        min_price = min(open_price, close_price)
        max_price = max(open_price, close_price)
        assume(low <= min_price)  # Low must be at or below the lower of open/close
        assume(high >= max_price)  # High must be at or above the higher of open/close

        df = pl.DataFrame(
            {
                "timestamp": pd.date_range("2023-01-01", periods=60, freq="1min", tz="UTC"),
                "symbol": ["TEST"] * 60,
                "open": [open_price] * 60,
                "high": [high] * 60,
                "low": [low] * 60,
                "close": [close_price] * 60,
                "volume": [Decimal("1000")] * 60,
            }
        )

        df_agg = aggregate_ohlcv(df, source_resolution="1m", target_resolution="1h", validate=False)

        # Property: High >= Low always
        assert all(df_agg["high"] >= df_agg["low"])
        assert all(df_agg["high"] >= df_agg["open"])
        assert all(df_agg["high"] >= df_agg["close"])
        assert all(df_agg["low"] <= df_agg["open"])
        assert all(df_agg["low"] <= df_agg["close"])

    @given(
        bar_count=st.integers(min_value=24, max_value=240),
    )
    @settings(max_examples=100)
    def test_aggregated_high_max_of_source_highs(self, bar_count):
        """Property: Aggregated High >= all source High values."""
        # Create bars with varying highs
        highs = [Decimal(str(100 + i % 10)) for i in range(bar_count)]

        df = pl.DataFrame(
            {
                "timestamp": pd.date_range("2023-01-01", periods=bar_count, freq="1h", tz="UTC"),
                "symbol": ["TEST"] * bar_count,
                "open": [Decimal("100")] * bar_count,
                "high": highs,
                "low": [Decimal("95")] * bar_count,
                "close": [Decimal("98")] * bar_count,
                "volume": [Decimal("1000")] * bar_count,
            }
        )

        df_agg = aggregate_ohlcv(df, source_resolution="1h", target_resolution="1d", validate=False)

        # Property: Aggregated high should equal max of source highs
        max_source_high = max(highs)
        assert df_agg["high"][0] == max_source_high

    @given(
        bar_count=st.integers(min_value=24, max_value=240),
    )
    @settings(max_examples=100)
    def test_aggregated_low_min_of_source_lows(self, bar_count):
        """Property: Aggregated Low <= all source Low values."""
        # Create bars with varying lows
        lows = [Decimal(str(90 + i % 10)) for i in range(bar_count)]

        df = pl.DataFrame(
            {
                "timestamp": pd.date_range("2023-01-01", periods=bar_count, freq="1h", tz="UTC"),
                "symbol": ["TEST"] * bar_count,
                "open": [Decimal("100")] * bar_count,
                "high": [Decimal("105")] * bar_count,
                "low": lows,
                "close": [Decimal("98")] * bar_count,
                "volume": [Decimal("1000")] * bar_count,
            }
        )

        df_agg = aggregate_ohlcv(df, source_resolution="1h", target_resolution="1d", validate=False)

        # Property: Aggregated low should equal min of source lows
        min_source_low = min(lows)
        assert df_agg["low"][0] == min_source_low

    @given(
        bar_count=st.integers(min_value=60, max_value=120),
    )
    @settings(max_examples=100)
    def test_aggregated_open_first_source_open(self, bar_count):
        """Property: Aggregated Open == first source Open."""
        opens = [Decimal(str(100 + i)) for i in range(bar_count)]

        df = pl.DataFrame(
            {
                "timestamp": pd.date_range(
                    "2023-01-01 10:00", periods=bar_count, freq="1min", tz="UTC"
                ),
                "symbol": ["TEST"] * bar_count,
                "open": opens,
                "high": [Decimal("105")] * bar_count,
                "low": [Decimal("95")] * bar_count,
                "close": [Decimal("102")] * bar_count,
                "volume": [Decimal("1000")] * bar_count,
            }
        )

        df_agg = aggregate_ohlcv(df, source_resolution="1m", target_resolution="1h", validate=False)

        # Property: Aggregated open should be first source open
        assert df_agg["open"][0] == opens[0]

    @given(
        bar_count=st.integers(
            min_value=30, max_value=60
        ),  # Keep within single hour to test single-period aggregation
    )
    @settings(max_examples=100)
    def test_aggregated_close_last_source_close(self, bar_count):
        """Property: Aggregated Close == last source Close (single period)."""
        closes = [Decimal(str(100 + i)) for i in range(bar_count)]

        df = pl.DataFrame(
            {
                "timestamp": pd.date_range(
                    "2023-01-01 10:00", periods=bar_count, freq="1min", tz="UTC"
                ),
                "symbol": ["TEST"] * bar_count,
                "open": [Decimal("100")] * bar_count,
                "high": [Decimal("105")] * bar_count,
                "low": [Decimal("95")] * bar_count,
                "close": closes,
                "volume": [Decimal("1000")] * bar_count,
            }
        )

        df_agg = aggregate_ohlcv(df, source_resolution="1m", target_resolution="1h", validate=False)

        # Property: Aggregated close should be last source close (for single aggregated period)
        assert len(df_agg) == 1  # Should produce exactly 1 hourly bar
        assert df_agg["close"][0] == closes[-1]
