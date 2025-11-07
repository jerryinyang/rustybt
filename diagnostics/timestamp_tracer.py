#!/usr/bin/env python3
"""Diagnostic script to trace timestamp flow through RustyBT simulation pipeline.

This script instruments key points in the backtest execution to understand:
1. What timestamps the clock yields
2. What simulation_dt is set to
3. What current_dt reports
4. What data is actually fetched
5. What bar dates/values are returned

Bug: RUSTYBT-DATA-001 - Off-by-one data shift in daily mode
"""

import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import polars as pl

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rustybt.data.polars.parquet_daily_bars import PolarsParquetDailyReader

# Global log for collecting diagnostic info
DIAGNOSTIC_LOG = []


def log_event(event_type, **kwargs):
    """Log a diagnostic event with timestamp."""
    entry = {"event": event_type, **kwargs}
    DIAGNOSTIC_LOG.append(entry)

    # Also print for real-time monitoring
    print(f"[{event_type}] {kwargs}")


# Global state for tracking calls (since we're using plain functions)
CALL_COUNT = 0
BTC_ASSET = None


def initialize(context):
    """Initialize strategy with single asset."""
    global BTC_ASSET

    log_event("STRATEGY_INIT", message="Strategy initialized")

    # Find BTC/USDT asset
    all_sids = context.asset_finder.sids
    all_assets = context.asset_finder.retrieve_all(all_sids)

    for asset in all_assets:
        if asset.asset_name == "BTC/USDT":
            BTC_ASSET = asset
            log_event("ASSET_FOUND", sid=asset.sid, symbol=asset.asset_name)
            break

    if BTC_ASSET is None:
        raise ValueError("BTC/USDT not found in bundle")


def handle_data(context, data):
    """Called on every bar - log everything."""
    global CALL_COUNT, BTC_ASSET
    CALL_COUNT += 1

    # Stop after 10 bars to keep output manageable
    if CALL_COUNT > 10:
        return

    # Log what the user sees
    current_dt = data.current_dt
    current_session = data.current_session

    log_event(
        "HANDLE_DATA_CALLED",
        call_count=CALL_COUNT,
        current_dt=str(current_dt),  # What user sees
        current_dt_date=str(current_dt.date()),
        current_session=str(current_session),
        current_session_date=str(current_session.date()),
    )

    # Check if asset is tradeable
    can_trade = data.can_trade(BTC_ASSET)
    log_event("CAN_TRADE_CHECK", can_trade=can_trade)

    if not can_trade:
        log_event("SKIP_BAR", reason="Asset not tradeable")
        return

    # Get current price using data.current()
    try:
        current_price = data.current(BTC_ASSET, "close")
        log_event(
            "CURRENT_PRICE",
            close=float(current_price) if not pd.isna(current_price) else None,
        )
    except Exception as e:
        log_event("CURRENT_PRICE_ERROR", error=str(e))

    # Get history using data.history()
    try:
        history = data.history(
            assets=BTC_ASSET,
            fields=["open", "high", "low", "close"],
            bar_count=1,
            frequency="1d",
            return_type="array",
        )

        log_event(
            "HISTORY_RETURNED",
            call_count=CALL_COUNT,  # Add call_count for matching
            shape=history.shape,
            open=float(history[-1][0]),
            high=float(history[-1][1]),
            low=float(history[-1][2]),
            close=float(history[-1][3]),
        )
    except Exception as e:
        log_event("HISTORY_ERROR", error=str(e))


def analyze(context, perf):
    """Save diagnostic log after backtest completes."""
    global CALL_COUNT

    log_event("BACKTEST_COMPLETE", total_bars=CALL_COUNT)

    output_file = Path(__file__).parent / "timestamp_trace.json"
    with open(output_file, "w") as f:
        json.dump(DIAGNOSTIC_LOG, f, indent=2)

    print(f"\n✅ Diagnostic log saved to: {output_file}")


def create_reference_data():
    """Export bundle data for the test period to use as reference."""
    log_event("EXPORT_START", message="Exporting bundle data for reference")

    bundle_path = Path.home() / ".zipline" / "data" / "bundles" / "binance-spot-1d"
    if not bundle_path.exists():
        raise FileNotFoundError(f"Bundle not found: {bundle_path}")

    reader = PolarsParquetDailyReader(str(bundle_path))

    # Find BTC/USDT sid by reading metadata
    import sqlite3

    conn = sqlite3.connect(str(bundle_path / "metadata.db"))
    result = pl.read_database(
        'SELECT symbol_id, symbol FROM symbols WHERE symbol = "BTC/USDT"', conn
    )
    conn.close()

    if len(result) == 0:
        raise ValueError("BTC/USDT not found in bundle metadata")

    btc_sid = int(result["symbol_id"][0])
    log_event("BTC_SID_FOUND", sid=btc_sid)

    # Export 10 days of data starting from 2020-01-01
    df = reader.load_daily_bars(
        sids=[btc_sid],
        start_date=date(2020, 1, 1),
        end_date=date(2020, 1, 15),
    )

    # Convert to pandas for easier viewing
    df_pd = df.to_pandas()

    # Save to CSV for reference
    output_csv = Path(__file__).parent / "reference_data.csv"
    df_pd.to_csv(output_csv, index=False)

    log_event(
        "EXPORT_COMPLETE",
        rows=len(df_pd),
        date_range=f"{df_pd['date'].min()} to {df_pd['date'].max()}",
        output_file=str(output_csv),
    )

    # Print first few rows for quick reference
    print("\n📊 Reference Data (Bundle Export):")
    print("=" * 80)
    for idx, row in df_pd.head(10).iterrows():
        print(f"  {row['date']}: open={row['open']:.2f}, close={row['close']:.2f}")
    print("=" * 80 + "\n")

    return df_pd


def run_diagnostic():
    """Run the diagnostic backtest."""
    print("=" * 80)
    print(" RustyBT Timestamp Diagnostic Script")
    print(" Bug: RUSTYBT-DATA-001 - Off-by-one data shift")
    print("=" * 80 + "\n")

    # Step 1: Export reference data
    print("STEP 1: Exporting reference data from bundle...")
    reference_df = create_reference_data()

    # Step 2: Run diagnostic backtest
    print("\nSTEP 2: Running diagnostic backtest...")
    log_event("BACKTEST_START", message="Starting diagnostic backtest")

    from rustybt.utils.run_algo import run_algorithm

    # Run backtest for 10 days using plain functions
    # Use pandas datetime without explicit timezone - let framework handle it
    results = run_algorithm(
        start=pd.Timestamp("2020-01-01"),
        end=pd.Timestamp("2020-01-10"),
        initialize=initialize,
        handle_data=handle_data,
        analyze=analyze,
        bundle="binance-spot-1d",
        capital_base=100000.0,
        data_frequency="daily",
        benchmark_returns=None,
    )

    log_event("BACKTEST_END", message="Diagnostic backtest completed")

    # Step 3: Analyze the logs
    print("\nSTEP 3: Analyzing timestamp flow...")
    analyze_diagnostic_log(reference_df)


def analyze_diagnostic_log(reference_df):
    """Analyze the diagnostic log to identify mismatches."""
    print("\n" + "=" * 80)
    print(" TIMESTAMP FLOW ANALYSIS")
    print("=" * 80 + "\n")

    # Group events by handle_data call
    handle_data_events = [e for e in DIAGNOSTIC_LOG if e["event"] == "HANDLE_DATA_CALLED"]

    print(f"Total handle_data calls: {len(handle_data_events)}\n")

    for i, hd_event in enumerate(handle_data_events):
        call_count = hd_event["call_count"]
        current_dt_str = hd_event["current_dt_date"]

        # Find the corresponding history event
        history_events = [
            e
            for e in DIAGNOSTIC_LOG
            if e["event"] == "HISTORY_RETURNED"
            and e.get("call_count") is None  # Need to track this better
        ]

        # For now, match by position
        if i < len(history_events):
            history_event = history_events[i]
        else:
            # Find events that occurred after this handle_data
            idx_hd = DIAGNOSTIC_LOG.index(hd_event)
            history_event = None
            for e in DIAGNOSTIC_LOG[idx_hd:]:
                if e["event"] == "HISTORY_RETURNED":
                    history_event = e
                    break

        print(f"Call #{call_count}:")
        print(f"  current_dt (reported): {current_dt_str}")

        if history_event:
            returned_close = history_event["close"]

            # Find what date in reference data has this close price
            # Convert Decimal to float for comparison
            matching_rows = reference_df[
                (reference_df["close"].astype(float) - returned_close).abs() < 0.01
            ]

            if len(matching_rows) > 0:
                actual_date = matching_rows.iloc[0]["date"]
                print(f"  history() returned:    close={returned_close:.2f}")
                print(f"  This matches bundle:   {actual_date}")

                # Check if dates match
                if str(actual_date) == current_dt_str:
                    print("  ✅ MATCH - Dates align correctly")
                else:
                    print(
                        f"  ❌ MISMATCH - Off by {(pd.to_datetime(current_dt_str) - pd.to_datetime(actual_date)).days} days"
                    )
            else:
                print(f"  history() returned:    close={returned_close:.2f}")
                print("  ⚠️  No matching row in bundle export!")
        else:
            print("  ⚠️  No history data recorded")

        print()

    print("=" * 80 + "\n")

    # Summary
    print("📊 SUMMARY:")
    print(f"  Diagnostic log entries: {len(DIAGNOSTIC_LOG)}")
    print(f"  handle_data calls: {len(handle_data_events)}")
    print("  See timestamp_trace.json for full details")
    print()


if __name__ == "__main__":
    try:
        run_diagnostic()
    except Exception as e:
        log_event("DIAGNOSTIC_ERROR", error=str(e), error_type=type(e).__name__)
        print(f"\n❌ Diagnostic failed: {e}")
        import traceback

        traceback.print_exc()

        # Still save the log
        output_file = Path(__file__).parent / "timestamp_trace.json"
        with open(output_file, "w") as f:
            json.dump(DIAGNOSTIC_LOG, f, indent=2)
        print(f"\nPartial log saved to: {output_file}")
        sys.exit(1)
