"""Test to reproduce the off-by-one data history bug.

Bug Report: RUSTYBT-DATA-001
When data.history() is called during a backtest, it returns bars that are
shifted by -1 day compared to the bundle storage.

Expected: When current_dt is 2020-01-03, history() should return bar for 2020-01-03
Actual: Returns bar data from 2020-01-02 (off by one)
"""

from datetime import date

import pandas as pd
import pytest

from rustybt.data.polars.data_portal import PolarsDataPortal
from rustybt.data.polars.parquet_daily_bars import PolarsParquetDailyReader
from rustybt.testing.fixtures import (
    with_asset_finder,
    with_trading_calendars,
)


@pytest.mark.skipif(
    not pytest.config.getoption("--run-bundle-tests", default=False),
    reason="Requires binance-spot-1d bundle installed",
)
class TestHistoryAlignmentBug:
    """Test suite to reproduce and verify fix for history alignment bug."""

    def test_history_matches_bundle_export(
        self,
        tmpdir,
        asset_finder,
        trading_calendar,
    ):
        """Verify that history() returns bars matching bundle export.

        This test:
        1. Exports bundle data directly (correct reference)
        2. Accesses same data via data_portal.get_history_window()
        3. Compares to ensure they match

        Expected: 100% match
        Current: 100% mismatch (off-by-one)
        """
        # Setup: Load binance-spot-1d bundle
        bundle_path = Path.home() / ".zipline" / "data" / "bundles" / "binance-spot-1d"
        if not bundle_path.exists():
            pytest.skip("binance-spot-1d bundle not found")

        reader = PolarsParquetDailyReader(str(bundle_path))
        portal = PolarsDataPortal(daily_reader=reader)

        # Find BTC/USDT asset
        btc_asset = None
        for asset in asset_finder.retrieve_all(asset_finder.sids):
            if asset.asset_name == "BTC/USDT":
                btc_asset = asset
                break

        if btc_asset is None:
            pytest.skip("BTC/USDT asset not found in bundle")

        # Step 1: Export bundle data directly (reference truth)
        df_export = reader.load_daily_bars(
            sids=[btc_asset.sid],
            start_date=date(2020, 1, 1),
            end_date=date(2020, 1, 10),
        )

        # Convert to pandas for easier comparison
        df_export_pd = df_export.to_pandas().set_index("date")

        # Step 2: Access same data via get_history_window (simulating backtest)
        test_dates = [
            pd.Timestamp("2020-01-03"),
            pd.Timestamp("2020-01-04"),
            pd.Timestamp("2020-01-05"),
        ]

        for test_dt in test_dates:
            # This simulates what happens during handle_data
            df_history = portal.get_history_window(
                assets=[btc_asset],
                end_dt=test_dt,
                bar_count=1,
                frequency="1d",
                field="close",
                data_frequency="daily",
            )

            # Get expected value from export
            expected_date = test_dt.date()
            expected_close = df_export_pd.loc[expected_date, "close"]

            # Get actual value from history
            actual_close = df_history.loc[df_history.index[-1], btc_asset]

            # This assertion currently FAILS due to the bug
            assert abs(actual_close - float(expected_close)) < 0.01, (
                f"Data mismatch on {test_dt.date()}: "
                f"expected close={expected_close}, got {actual_close}. "
                f"History index: {df_history.index[-1].date()}, expected: {expected_date}"
            )

    def test_current_dt_matches_returned_bar_date(
        self,
        asset_finder,
        trading_calendar,
    ):
        """Verify that when current_dt is X, history() returns bar for date X.

        This is the core invariant that must hold: The date reported by
        current_dt should match the date of the bar returned by history().

        Expected: current_dt date == history bar date
        Current: history bar date is current_dt - 1 day (BUG)
        """
        from pathlib import Path

        from rustybt._protocol import BarData
        from rustybt.algorithm import TradingAlgorithm
        from rustybt.pipeline import Pipeline
        from rustybt.pipeline.domain import EquityCalendarDomain
        from rustybt.pipeline.filters import StaticAssets

        bundle_path = Path.home() / ".zipline" / "data" / "bundles" / "binance-spot-1d"
        if not bundle_path.exists():
            pytest.skip("binance-spot-1d bundle not found")

        reader = PolarsParquetDailyReader(str(bundle_path))
        portal = PolarsDataPortal(daily_reader=reader)

        # Find BTC/USDT
        btc_asset = None
        for asset in asset_finder.retrieve_all(asset_finder.sids):
            if asset.asset_name == "BTC/USDT":
                btc_asset = asset
                break

        if btc_asset is None:
            pytest.skip("BTC/USDT not found")

        # Simulate what happens in handle_data
        simulation_dt = pd.Timestamp("2020-01-05 00:00:00+00:00")
        portal.set_simulation_time(simulation_dt)

        # Create BarData (what user sees in handle_data)
        bar_data = BarData(
            data_portal=portal,
            simulation_dt_func=lambda: simulation_dt,
            data_frequency="daily",
            trading_calendar=trading_calendar,
            restrictions=None,  # Simplified for test
        )

        # Call history (what user does in strategy)
        history = bar_data.history(
            assets=btc_asset,
            fields=["close"],
            bar_count=1,
            frequency="1d",
            return_type="array",
        )

        # The bar returned should be for 2020-01-05, not 2020-01-04
        # We can't check the date directly in array mode, but we can
        # verify by comparing against known bundle data
        df_export = reader.load_daily_bars(
            sids=[btc_asset.sid],
            start_date=date(2020, 1, 5),
            end_date=date(2020, 1, 5),
        )

        expected_close = float(df_export["close"][0])
        actual_close = history[-1][0]

        # This assertion currently FAILS due to the bug
        assert abs(actual_close - expected_close) < 0.01, (
            f"When current_dt is {simulation_dt.date()}, history() returned "
            f"close={actual_close}, but bundle data for {simulation_dt.date()} "
            f"shows close={expected_close}. This indicates an off-by-one error."
        )


@pytest.mark.integration
def test_history_alignment_minimal():
    """Minimal test to reproduce history alignment bug without bundle dependency.

    This test creates synthetic data and verifies that history() returns
    the correct bars based on current_dt.
    """
    import polars as pl

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
    dates = pd.date_range("2020-01-01", "2020-01-10", freq="D")
    data = pl.DataFrame(
        {
            "sid": [1] * len(dates),
            "date": [d.date() for d in dates],
            "open": [float(100 + i) for i in range(len(dates))],  # 100, 101, 102, ...
            "high": [float(110 + i) for i in range(len(dates))],
            "low": [float(90 + i) for i in range(len(dates))],
            "close": [float(105 + i) for i in range(len(dates))],  # 105, 106, 107, ...
            "volume": [float(1000 + i * 100) for i in range(len(dates))],
        }
    )

    # Create a mock reader
    class MockReader:
        def load_daily_bars(self, sids, start_date, end_date):
            return data.filter((pl.col("date") >= start_date) & (pl.col("date") <= end_date))

    reader = MockReader()
    portal = PolarsDataPortal(daily_reader=reader)

    # Test: When end_dt is 2020-01-05, should return bar for 2020-01-05
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

    # Expected: close value for 2020-01-05 is 109.0 (105 + 4)
    expected_close = 109.0
    actual_close = df_history.loc[df_history.index[-1], test_asset]

    assert abs(actual_close - expected_close) < 0.01, (
        f"Expected close={expected_close} for date {end_dt.date()}, "
        f"but got {actual_close}. "
        f"Returned index date: {df_history.index[-1].date()}"
    )

    # Additional check: Verify the index date matches end_dt
    returned_date = df_history.index[-1].date()
    expected_date = end_dt.date()
    assert (
        returned_date == expected_date
    ), f"DataFrame index shows date {returned_date}, but expected {expected_date}"
