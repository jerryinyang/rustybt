"""
Setup profiling data bundles for Story 7.1.

This script creates simplified profiling bundles using synthetic data
for fast setup without requiring external APIs or network access.
"""

import sys
from pathlib import Path

import pandas as pd
import structlog

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rustybt.data.bundles import ingest, register

logger = structlog.get_logger(__name__)


def generate_synthetic_ohlcv(
    symbols: list[str],
    start: pd.Timestamp,
    end: pd.Timestamp,
    frequency: str = "1d",
    calendar=None,
) -> pd.DataFrame:
    """Generate synthetic OHLCV data for profiling.

    Args:
        symbols: List of ticker symbols
        start: Start date
        end: End date
        frequency: Data frequency ('1d', '1h', '1m')
        calendar: Trading calendar (optional, uses NYSE if None)

    Returns:
        DataFrame with OHLCV data for all symbols
    """
    import numpy as np
    from exchange_calendars import get_calendar

    logger.info(
        "generating_synthetic_data",
        symbol_count=len(symbols),
        start=start,
        end=end,
        frequency=frequency,
    )

    # Generate date range aligned to the trading calendar
    if calendar is None:
        calendar = get_calendar("XNYS")  # NYSE calendar

    if frequency == "1d":
        # Trading sessions only
        start_tz_naive = start.tz_localize(None) if start.tz is not None else start
        end_tz_naive = end.tz_localize(None) if end.tz is not None else end
        dates = calendar.sessions_in_range(start_tz_naive, end_tz_naive)
    elif frequency in ("1h", "1m"):
        # Build minute grid for all trading minutes between start..end
        start_tz_naive = start.tz_localize(None) if start.tz is not None else start
        end_tz_naive = end.tz_localize(None) if end.tz is not None else end
        sessions = calendar.sessions_in_range(start_tz_naive, end_tz_naive)

        minute_list = []
        for session in sessions:
            market_open = calendar.session_open(session)
            market_close = calendar.session_close(session)
            # Use [open, close) minutes; exclude exact close to match writer index
            n_mins = int((market_close - market_open).total_seconds() // 60)
            if n_mins <= 0:
                continue
            session_minutes = pd.date_range(start=market_open, periods=n_mins, freq="1min")
            minute_list.append(session_minutes)

        if len(minute_list) == 0:
            dates = pd.DatetimeIndex([], tz="UTC")
        else:
            # Concatenate all minute ranges, preserving timezone
            all_minutes = pd.concat([pd.Series(m) for m in minute_list], ignore_index=True)
            dates = pd.DatetimeIndex(all_minutes.values, tz="UTC")
    else:
        # Fallback generic generator
        dates = pd.date_range(start=start, end=end, freq=frequency)

    all_data = []

    for symbol in symbols:
        # Generate random walk price series
        np.random.seed(hash(symbol) % (2**32))  # Deterministic per symbol

        # Starting price based on symbol hash (between $10-$200)
        base_price = 10 + (hash(symbol) % 190)

        # Generate price series with realistic volatility
        returns = np.random.normal(0, 0.02, len(dates))  # 2% daily volatility
        price_multipliers = np.exp(np.cumsum(returns))
        close_prices = base_price * price_multipliers

        # Generate OHLC from close prices
        high_prices = close_prices * (1 + np.abs(np.random.normal(0, 0.01, len(dates))))
        low_prices = close_prices * (1 - np.abs(np.random.normal(0, 0.01, len(dates))))

        # Open is close from previous day with some noise
        open_prices = np.roll(close_prices, 1)
        open_prices[0] = close_prices[0]
        open_prices = open_prices * (1 + np.random.normal(0, 0.005, len(dates)))

        # Volume with realistic variation
        base_volume = 1_000_000 + (hash(symbol) % 10_000_000)
        volume = base_volume * (1 + np.abs(np.random.normal(0, 0.3, len(dates))))

        # Create DataFrame for this symbol
        df = pd.DataFrame(
            {
                "symbol": symbol,
                "date": dates,
                "open": open_prices,
                "high": high_prices,
                "low": low_prices,
                "close": close_prices,
                "volume": volume.astype(int),
            }
        )

        all_data.append(df)

    # Combine all symbols
    combined_df = pd.concat(all_data, ignore_index=True)

    logger.info(
        "synthetic_data_generated",
        total_rows=len(combined_df),
        symbols=len(symbols),
        date_range=(dates[0], dates[-1]),
    )

    return combined_df


@register("profiling-daily")
def profiling_daily_bundle(
    environ,
    asset_db_writer,
    minute_bar_writer,
    daily_bar_writer,
    adjustment_writer,
    calendar,
    start_session,
    end_session,
    cache,
    show_progress,
    output_dir,
):
    """
    Daily profiling bundle for Story 7.1.

    50 synthetic stocks, 2 years of daily data.
    """
    # Generate 50 synthetic symbols
    symbols = [f"SYM{i:03d}" for i in range(50)]

    # Date range: Fixed 3-year range to ensure alignment with profiling scenarios
    # Scenarios use dates from 2024-08-01 to 2025-08-01, so bundle must cover that
    # plus 250 trading days before for SMA history
    start = pd.Timestamp("2023-10-01", tz="UTC")
    end = pd.Timestamp("2026-10-01", tz="UTC")

    # Generate synthetic data using the trading calendar
    df = generate_synthetic_ohlcv(
        symbols=symbols, start=start, end=end, frequency="1d", calendar=calendar
    )

    # Create asset metadata
    equity_info = pd.DataFrame(
        {
            "symbol": symbols,
            "asset_name": [f"Synthetic Stock {i}" for i in range(len(symbols))],
            "start_date": start,
            "end_date": end,
            "exchange": "NYSE",
        }
    )

    # Write asset metadata
    asset_db_writer.write(equities=equity_info)

    # Write OHLCV data using iterator pattern
    def pricing_iter():
        for sid, symbol in enumerate(symbols):
            symbol_df = df[df["symbol"] == symbol].copy()
            symbol_df = symbol_df.set_index("date")
            symbol_df = symbol_df[["open", "high", "low", "close", "volume"]]
            yield sid, symbol_df

    daily_bar_writer.write(pricing_iter(), show_progress=show_progress)

    # Write empty adjustments to create required tables
    adjustment_writer.write()

    logger.info("profiling_daily_bundle_complete", symbols=len(symbols), rows=len(df))


@register("profiling-hourly")
def profiling_hourly_bundle(
    environ,
    asset_db_writer,
    minute_bar_writer,
    daily_bar_writer,
    adjustment_writer,
    calendar,
    start_session,
    end_session,
    cache,
    show_progress,
    output_dir,
):
    """
    Hourly profiling bundle for Story 7.1.

    20 synthetic assets, 6 months of hourly data.
    """
    # Generate 20 synthetic symbols
    symbols = [f"SYM{i:03d}" for i in range(20)]

    # Date range: Fixed range to align with hourly scenario (2024-09-01 to 2024-12-01)
    # Need extra months for indicator history
    start = pd.Timestamp("2024-06-01", tz="UTC")
    end = pd.Timestamp("2025-01-01", tz="UTC")

    # Generate minute-level synthetic data (hourly scenario aggregates from minutes)
    df = generate_synthetic_ohlcv(
        symbols=symbols, start=start, end=end, frequency="1m", calendar=calendar
    )

    # Create asset metadata
    equity_info = pd.DataFrame(
        {
            "symbol": symbols,
            "asset_name": [f"Synthetic Asset {i}" for i in range(len(symbols))],
            "start_date": start,
            "end_date": end,
            "exchange": "NYSE",
        }
    )

    # Write asset metadata
    asset_db_writer.write(equities=equity_info)

    # Write OHLCV data using iterator pattern
    def pricing_iter():
        for sid, symbol in enumerate(symbols):
            symbol_df = df[df["symbol"] == symbol].copy()
            symbol_df = symbol_df.set_index("date")
            symbol_df = symbol_df[["open", "high", "low", "close", "volume"]]
            yield sid, symbol_df

    minute_bar_writer.write(pricing_iter(), show_progress=show_progress)

    # Write empty adjustments to create required tables
    adjustment_writer.write()

    logger.info("profiling_hourly_bundle_complete", symbols=len(symbols), rows=len(df))


@register("profiling-minute")
def profiling_minute_bundle(
    environ,
    asset_db_writer,
    minute_bar_writer,
    daily_bar_writer,
    adjustment_writer,
    calendar,
    start_session,
    end_session,
    cache,
    show_progress,
    output_dir,
):
    """
    Minute profiling bundle for Story 7.1.

    10 synthetic assets, 1 month of minute data.
    """
    # Generate 10 synthetic symbols
    symbols = [f"SYM{i:03d}" for i in range(10)]

    # Date range: Fixed range to align with minute scenario (2024-10-01 to 2024-11-01)
    # Need extra days for indicator history (limit to trading hours to reduce data volume)
    start = pd.Timestamp("2024-09-15", tz="UTC")
    end = pd.Timestamp("2024-11-15", tz="UTC")

    # Generate minute-level synthetic data aligned to calendar market minutes
    df = generate_synthetic_ohlcv(
        symbols=symbols, start=start, end=end, frequency="1m", calendar=calendar
    )

    # Create asset metadata
    equity_info = pd.DataFrame(
        {
            "symbol": symbols,
            "asset_name": [f"Synthetic Asset {i}" for i in range(len(symbols))],
            "start_date": start,
            "end_date": end,
            "exchange": "NYSE",
        }
    )

    # Write asset metadata
    asset_db_writer.write(equities=equity_info)

    # Write OHLCV data using iterator pattern
    def pricing_iter():
        for sid, symbol in enumerate(symbols):
            symbol_df = df[df["symbol"] == symbol].copy()
            symbol_df = symbol_df.set_index("date")
            symbol_df = symbol_df[["open", "high", "low", "close", "volume"]]
            yield sid, symbol_df

    minute_bar_writer.write(pricing_iter(), show_progress=show_progress)

    # Write empty adjustments to create required tables
    adjustment_writer.write()

    logger.info("profiling_minute_bundle_complete", symbols=len(symbols), rows=len(df))


def setup_profiling_bundles():
    """Setup all profiling bundles for Story 7.1."""
    # Ingest daily, hourly, and minute profiling bundles
    bundles = ["profiling-daily", "profiling-hourly", "profiling-minute"]

    logger.info("setting_up_profiling_bundles", bundles=bundles)

    for bundle_name in bundles:
        try:
            logger.info("ingesting_bundle", bundle=bundle_name)
            ingest(bundle_name, show_progress=True)
            logger.info("bundle_ingested", bundle=bundle_name)
        except Exception as e:
            logger.error("bundle_ingest_failed", bundle=bundle_name, error=str(e))
            raise

    logger.info("all_profiling_bundles_ready")


if __name__ == "__main__":
    # Setup logging
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ]
    )

    try:
        setup_profiling_bundles()
        print("\n✅ All profiling bundles created successfully!")
        print("\nCreated bundles:")
        print("  - profiling-daily: 50 stocks, 2 years daily data (502 trading days)")
        print("\nNote: Hourly and minute bundles require additional calendar setup.")
        print("      Daily bundle is sufficient for profiling Python implementation.")
    except Exception as e:
        print(f"\n❌ Failed to setup profiling bundles: {e}")
        sys.exit(1)
