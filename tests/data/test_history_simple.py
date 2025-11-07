"""Simplified test to reproduce the off-by-one data history bug.

Bug Report: RUSTYBT-DATA-001
"""

from datetime import date
from pathlib import Path

import pandas as pd
import polars as pl
import pytest


def test_history_alignment_with_synthetic_data():
    """Test history alignment with synthetic data (no bundle required).

    This test creates synthetic data and verifies that get_history_window()
    returns the correct bars based on end_dt.
    """
    from rustybt.assets import Asset
    from rustybt.data.polars.data_portal import PolarsDataPortal

    # Create synthetic asset
    test_asset = Asset(
        sid=1,
        symbol="TEST",
        asset_name="TEST",
        exchange="TEST",
        start_date=pd.Timestamp("2020-01-01"),
        end_date=pd.Timestamp("2020-12-31"),
    )

    # Create synthetic OHLCV data with distinctive values
    # Each day has close = 105 + day_number
    # 2020-01-01: close=105
    # 2020-01-02: close=106
    # 2020-01-03: close=107
    # etc.
    dates = pd.date_range("2020-01-01", "2020-01-10", freq="D")
    data = pl.DataFrame(
        {
            "sid": [1] * len(dates),
            "date": [d.date() for d in dates],
            "open": [float(100 + i) for i in range(len(dates))],
            "high": [float(110 + i) for i in range(len(dates))],
            "low": [float(90 + i) for i in range(len(dates))],
            "close": [float(105 + i) for i in range(len(dates))],
            "volume": [float(1000 + i * 100) for i in range(len(dates))],
        }
    )

    # Create a mock reader
    class MockReader:
        def load_daily_bars(self, sids, start_date, end_date):
            return data.filter((pl.col("date") >= start_date) & (pl.col("date") <= end_date))

    reader = MockReader()
    portal = PolarsDataPortal(daily_reader=reader)

    # TEST CASE 1: When end_dt is 2020-01-05, should return bar for 2020-01-05
    end_dt = pd.Timestamp("2020-01-05")
    portal.set_simulation_time(end_dt)

    df_history = portal.get_history_window(
        assets=[test_asset],
        end_dt=end_dt,
        bar_count=1,
        frequency="1d",
        field="close",
        data_frequency="daily",
    )

    # Expected: close value for 2020-01-05 is 109.0 (105 + 4, since Jan 1 is index 0)
    expected_close = 109.0
    actual_close = df_history.loc[df_history.index[-1], test_asset]
    returned_date = df_history.index[-1].date()

    print(f"\nTest Case 1: end_dt={end_dt.date()}")
    print(f"  Expected: date={end_dt.date()}, close={expected_close}")
    print(f"  Actual:   date={returned_date}, close={actual_close}")

    assert abs(actual_close - expected_close) < 0.01, (
        f"Expected close={expected_close} for date {end_dt.date()}, "
        f"but got {actual_close}. "
        f"Returned index date: {returned_date}"
    )

    assert (
        returned_date == end_dt.date()
    ), f"DataFrame index shows date {returned_date}, but expected {end_dt.date()}"

    # TEST CASE 2: Test multiple bars
    end_dt2 = pd.Timestamp("2020-01-07")
    portal.set_simulation_time(end_dt2)

    df_history2 = portal.get_history_window(
        assets=[test_asset],
        end_dt=end_dt2,
        bar_count=3,  # Should return 2020-01-05, 2020-01-06, 2020-01-07
        frequency="1d",
        field="close",
        data_frequency="daily",
    )

    print(f"\nTest Case 2: end_dt={end_dt2.date()}, bar_count=3")
    print(f"  Returned dates: {[d.date() for d in df_history2.index]}")
    print(f"  Returned closes: {df_history2[test_asset].tolist()}")

    # Expected: last bar should be 2020-01-07 with close=111.0 (105 + 6)
    expected_last_close = 111.0
    actual_last_close = df_history2.loc[df_history2.index[-1], test_asset]
    last_date = df_history2.index[-1].date()

    assert last_date == end_dt2.date(), f"Last bar date is {last_date}, expected {end_dt2.date()}"

    assert (
        abs(actual_last_close - expected_last_close) < 0.01
    ), f"Last bar close is {actual_last_close}, expected {expected_last_close}"

    # TEST CASE 3: Verify all 3 bars have correct dates and values
    expected_dates = [
        date(2020, 1, 5),
        date(2020, 1, 6),
        date(2020, 1, 7),
    ]
    expected_closes = [109.0, 110.0, 111.0]

    actual_dates = [d.date() for d in df_history2.index]
    actual_closes = df_history2[test_asset].tolist()

    for i, (exp_date, exp_close, act_date, act_close) in enumerate(
        zip(expected_dates, expected_closes, actual_dates, actual_closes)
    ):
        print(f"  Bar {i}: expected ({exp_date}, {exp_close}), actual ({act_date}, {act_close})")
        assert act_date == exp_date, f"Bar {i}: date mismatch"
        assert abs(act_close - exp_close) < 0.01, f"Bar {i}: close mismatch"

    print("\nAll tests passed! ✅")


if __name__ == "__main__":
    test_history_alignment_with_synthetic_data()
