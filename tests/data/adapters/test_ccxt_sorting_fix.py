"""Test for CCXT timestamp sorting fix (Issue: multi-symbol fetch).

This is a standalone test to verify the fix for timestamp sorting issue
when fetching multiple symbols. Does not depend on conftest.
"""

from decimal import Decimal

import pandas as pd
import polars as pl


def test_multi_symbol_dataframe_sorting() -> None:
    """Verify multi-symbol data is sorted by timestamp and symbol.

    This simulates the CCXT adapter's behavior when fetching multiple symbols:
    - Fetches BTC/USDT data (2024-01-01 to 2024-01-03)
    - Fetches ETH/USDT data (2024-01-01 to 2024-01-03)
    - Appends sequentially (creating unsorted timestamps)
    - Sorts by timestamp and symbol
    - Validates timestamps are sorted
    """
    # Simulate CCXT data for BTC/USDT (3 days)
    btc_data = [
        [1704067200000, 42000.0, 42500.0, 41800.0, 42200.0, 1000.0, "BTC/USDT"],  # 2024-01-01
        [1704153600000, 42200.0, 42800.0, 42000.0, 42500.0, 1100.0, "BTC/USDT"],  # 2024-01-02
        [1704240000000, 42500.0, 43000.0, 42300.0, 42700.0, 1200.0, "BTC/USDT"],  # 2024-01-03
    ]

    # Simulate CCXT data for ETH/USDT (3 days) - same dates!
    eth_data = [
        [1704067200000, 2200.0, 2250.0, 2180.0, 2220.0, 5000.0, "ETH/USDT"],  # 2024-01-01
        [1704153600000, 2220.0, 2280.0, 2200.0, 2250.0, 5500.0, "ETH/USDT"],  # 2024-01-02
        [1704240000000, 2250.0, 2300.0, 2230.0, 2270.0, 6000.0, "ETH/USDT"],  # 2024-01-03
    ]

    # Simulate sequential appending (THIS WAS THE BUG)
    all_data = []
    all_data.extend(btc_data)  # All BTC data first
    all_data.extend(eth_data)  # All ETH data second (timestamps reset!)

    # Create DataFrame (as CCXT adapter does)
    df = pl.DataFrame(
        {
            "timestamp": [pd.Timestamp(row[0], unit="ms") for row in all_data],
            "symbol": [row[6] for row in all_data],
            "open": [Decimal(str(row[1])) for row in all_data],
            "high": [Decimal(str(row[2])) for row in all_data],
            "low": [Decimal(str(row[3])) for row in all_data],
            "close": [Decimal(str(row[4])) for row in all_data],
            "volume": [Decimal(str(row[5])) for row in all_data],
        }
    )

    # BEFORE FIX: Timestamps are NOT sorted (BTC dates, then ETH dates which reset)
    # Verify the bug exists in unsorted data
    assert not df["timestamp"].is_sorted(), "Unsorted data should fail validation"

    # THE FIX: Sort by timestamp and symbol
    df_sorted = df.sort(["timestamp", "symbol"])

    # AFTER FIX: Timestamps ARE sorted
    assert df_sorted["timestamp"].is_sorted(), "Sorted data should pass validation"

    # Verify correct ordering: timestamps interleaved by symbol
    expected_order = [
        ("BTC/USDT", pd.Timestamp("2024-01-01")),
        ("ETH/USDT", pd.Timestamp("2024-01-01")),
        ("BTC/USDT", pd.Timestamp("2024-01-02")),
        ("ETH/USDT", pd.Timestamp("2024-01-02")),
        ("BTC/USDT", pd.Timestamp("2024-01-03")),
        ("ETH/USDT", pd.Timestamp("2024-01-03")),
    ]

    actual_order = list(zip(df_sorted["symbol"], df_sorted["timestamp"], strict=False))

    assert len(actual_order) == len(expected_order)
    for i, ((expected_symbol, expected_ts), (actual_symbol, actual_ts)) in enumerate(
        zip(expected_order, actual_order, strict=False)
    ):
        assert (
            actual_symbol == expected_symbol
        ), f"Row {i}: expected {expected_symbol}, got {actual_symbol}"
        assert actual_ts == expected_ts, f"Row {i}: expected {expected_ts}, got {actual_ts}"

    print("✅ Multi-symbol sorting test passed!")
    print(f"   - Unsorted data fails validation: {not df['timestamp'].is_sorted()}")
    print(f"   - Sorted data passes validation: {df_sorted['timestamp'].is_sorted()}")
    print(f"   - Correct interleaved ordering verified")


if __name__ == "__main__":
    test_multi_symbol_dataframe_sorting()
