"""Testing infrastructure for RustyBT backtesting framework.

This module provides a comprehensive suite of testing utilities including:

**Test Fixtures (fixtures.py)**
- ZiplineTestCase: Base class with fixture management
- WithAssetFinder: Asset database fixtures
- WithDataPortal: Data access fixtures
- WithTradingCalendars: Trading calendar fixtures
- WithBenchmarkReturns: Benchmark data fixtures

**Test Utilities (core.py)**
- Mock data generators (create_minute_bar_data, create_daily_df_for_asset)
- Data portal construction (create_data_portal, FakeDataPortal)
- Assertion helpers (check_allclose, assert_timestamp_equal)
- Temporary resources (tmp_asset_finder, tmp_dir)

**Predicates (predicates.py)**
- assert_equal: Recursive equality testing with type dispatch
- wildcard: Match-anything placeholder
- instance_of: Type-checking placeholder

**Pipeline Testing (pipeline_terms.py)**
- CheckWindowsFactor: Validate lookback windows
- CheckWindowsClassifier: Validate classifier windows

Examples:
    Create a basic test case::

        from rustybt.testing import ZiplineTestCase

        class MyStrategyTest(ZiplineTestCase):
            def test_my_strategy(self):
                # Test fixtures automatically set up and torn down
                assert hasattr(self, 'asset_finder')

    Generate test data::

        from rustybt.testing import create_minute_bar_data
        import pandas as pd

        minutes = pd.date_range('2023-01-01', periods=390, freq='1min')
        sids = [1, 2, 3]

        data = create_minute_bar_data(minutes, sids)
        for sid, df in data:
            assert len(df) == 390

    Use assertion predicates::

        from rustybt.testing.predicates import assert_equal, wildcard

        result = {'a': 1, 'b': 2, 'c': 'dynamic_value'}
        expected = {'a': 1, 'b': 2, 'c': wildcard}

        assert_equal(result, expected)  # Passes - wildcard matches anything
"""

from .core import (  # noqa
    AssetID,
    AssetIDPlusDay,
    EPOCH,
    ExplodingObject,
    FakeDataPortal,
    FetcherDataPortal,
    MockDailyBarReader,
    OpenPrice,
    RecordBatchBlotter,
    add_security_data,
    all_pairs_matching_predicate,
    all_subindices,
    assert_single_position,
    assert_timestamp_equal,
    check_allclose,
    check_arrays,
    create_daily_df_for_asset,
    create_data_portal,
    create_data_portal_from_trade_history,
    create_empty_splits_mergers_frame,
    create_minute_bar_data,
    create_minute_df_for_asset,
    drain_zipline,
    empty_asset_finder,
    empty_assets_db,
    make_alternating_boolean_array,
    make_cascading_boolean_array,
    make_trade_data_for_asset_info,
    parameter_space,
    patch_os_environment,
    patch_read_csv,
    permute_rows,
    powerset,
    prices_generating_returns,
    product_upper_triangle,
    read_compressed,
    seconds_to_timestamp,
    security_list_copy,
    simulate_minutes_for_day,
    str_to_seconds,
    subtest,
    temp_pipeline_engine,
    test_resource_path,
    tmp_asset_finder,
    tmp_assets_db,
    tmp_bcolz_equity_minute_bar_reader,
    tmp_dir,
    to_series,
    to_utc,
    trades_by_sid_to_dfs,
    write_bcolz_minute_data,
    write_compressed,
)
from .fixtures import ZiplineTestCase  # noqa
