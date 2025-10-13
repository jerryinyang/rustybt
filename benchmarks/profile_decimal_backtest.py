"""Profile Decimal backtest to identify optimization hotspots for Epic 7.

This script uses cProfile to identify the top time-consuming functions in the
Decimal implementation, which will be prioritized for Rust optimization.

Usage:
    python benchmarks/profile_decimal_backtest.py

Output:
    - benchmarks/results/decimal_backtest.prof (binary profile)
    - benchmarks/results/hotspots.txt (top 20 functions)
    - docs/performance/hotspots.md (formatted for documentation)
"""

import cProfile
import pstats
import random

# Test fixture for exchange info
from collections import namedtuple
from decimal import Decimal
from pathlib import Path

import polars as pl

from rustybt.assets import Equity
from rustybt.finance.decimal.commission import PerShareCommission
from rustybt.finance.decimal.ledger import DecimalLedger
from rustybt.finance.decimal.order import DecimalOrder
from rustybt.finance.decimal.position import DecimalPosition

ExchangeInfo = namedtuple("ExchangeInfo", ["canonical_name", "name", "country_code"])
TEST_EXCHANGE = ExchangeInfo(
    canonical_name="NYSE", name="New York Stock Exchange", country_code="US"
)


class DecimalMetrics:
    """Decimal-based metrics calculator."""

    @staticmethod
    def sharpe_ratio(returns: pl.Series, risk_free_rate: Decimal = Decimal("0")) -> Decimal:
        """Calculate Sharpe ratio with Decimal precision."""
        if len(returns) < 2:
            return Decimal("0")

        # Calculate excess returns
        excess_returns = returns.map_elements(
            lambda x: x - risk_free_rate if x is not None else Decimal("0"),
            return_dtype=pl.Decimal(scale=8),
        )

        # Calculate mean and std
        mean_return = excess_returns.mean()
        std_return = excess_returns.std()

        if mean_return is None or std_return is None or std_return == 0:
            return Decimal("0")

        return Decimal(str(mean_return)) / Decimal(str(std_return))


def run_decimal_backtest():
    """Run Decimal-based backtest for profiling.

    This simulates a realistic backtest with:
    - 252 trading days (1 year)
    - 10 assets
    - Moving average crossover strategy
    - Commission and position tracking
    """
    random.seed(42)
    commission_model = PerShareCommission(rate=Decimal("0.001"))

    # Initialize portfolio
    ledger = DecimalLedger(starting_cash=Decimal("1000000"))
    daily_returns = []

    # Simulate 252 days of trading
    for day in range(252):
        # Generate price data
        prices = {}
        for i in range(1, 11):
            asset = Equity(sid=i, exchange_info=TEST_EXCHANGE, symbol=f"STOCK{i}")
            prices[asset] = Decimal(str(50.0 + random.random() * 10))

        # Simple strategy: buy if price > 50, sell if price < 50
        for asset, price in prices.items():
            current_position = ledger.positions.get(asset)

            if price > Decimal("50") and (current_position is None or current_position.amount == 0):
                # Buy signal
                order = DecimalOrder(dt=None, asset=asset, amount=Decimal("100"), limit=price)

                fill_value = abs(order.amount) * order.limit
                commission = commission_model.calculate(order, order.limit, order.amount)

                # Update portfolio
                ledger.cash -= fill_value + commission

                position = DecimalPosition(
                    asset=asset,
                    amount=order.amount,
                    cost_basis=order.limit,
                    last_sale_price=order.limit,
                    last_sale_date=None,
                )
                ledger.positions[asset] = position

            elif price < Decimal("50") and current_position is not None:
                # Sell signal
                if current_position.amount > 0:
                    order = DecimalOrder(
                        dt=None,
                        asset=asset,
                        amount=-current_position.amount,
                        limit=price,
                    )

                    fill_value = abs(order.amount) * order.limit
                    commission = commission_model.calculate(order, order.limit, order.amount)

                    # Update portfolio
                    ledger.cash += fill_value - commission
                    del ledger.positions[asset]

        # Calculate daily return
        portfolio_value = ledger.portfolio_value
        if len(daily_returns) > 0:
            # Calculate return based on portfolio value change
            prev_value = Decimal("1000000") if day == 1 else portfolio_value
            daily_return = (
                (portfolio_value - prev_value) / prev_value if prev_value != 0 else Decimal("0")
            )
            daily_returns.append(daily_return)
        else:
            daily_returns.append(Decimal("0"))

    # Calculate metrics
    returns_series = pl.Series("returns", daily_returns, dtype=pl.Decimal(scale=8))
    sharpe = DecimalMetrics.sharpe_ratio(returns_series)

    return {
        "final_portfolio_value": ledger.portfolio_value,
        "sharpe_ratio": sharpe,
        "total_positions": len(ledger.positions),
    }


def main():
    """Run profiling and export results."""
    print("Starting profiling of Decimal backtest...")

    # Create results directory
    results_dir = Path("benchmarks/results")
    results_dir.mkdir(parents=True, exist_ok=True)

    # Run profiler
    profiler = cProfile.Profile()
    profiler.enable()

    result = run_decimal_backtest()

    profiler.disable()

    print("\nBacktest completed:")
    print(f"  Final portfolio value: ${result['final_portfolio_value']}")
    print(f"  Sharpe ratio: {result['sharpe_ratio']}")
    print(f"  Final positions: {result['total_positions']}")

    # Save binary profile
    profile_path = results_dir / "decimal_backtest.prof"
    profiler.dump_stats(str(profile_path))
    print(f"\nBinary profile saved to: {profile_path}")
    print(f"  Visualize with: snakeviz {profile_path}")

    # Analyze and export top hotspots
    stats = pstats.Stats(profiler)
    stats.sort_stats("cumulative")

    # Export to text file
    text_output = results_dir / "hotspots.txt"
    with open(text_output, "w") as f:
        f.write("Top 20 Hotspots (by cumulative time)\n")
        f.write("=" * 80 + "\n\n")
        stats.stream = f
        stats.print_stats(20)

    print(f"Hotspot analysis saved to: {text_output}")

    # Export formatted markdown for documentation
    md_output = Path("docs/performance/hotspots.md")
    md_output.parent.mkdir(parents=True, exist_ok=True)

    with open(md_output, "w") as f:
        f.write("# Decimal Implementation Hotspots\n\n")
        f.write("**Generated:** Profiling run of 252-day backtest with 10 assets\n\n")
        f.write("## Purpose\n\n")
        f.write("Identify top time-consuming functions for Rust optimization in Epic 7.\n\n")
        f.write("## Top 20 Functions (by cumulative time)\n\n")
        f.write("| Rank | Function | Cumulative Time (s) | Calls | Time/Call (ms) |\n")
        f.write("|------|----------|--------------------:|------:|---------------:|\n")

        # Get top 20 functions
        stats_list = stats.get_stats_profile()
        sorted_stats = sorted(
            stats_list.func_profiles.items(),
            key=lambda x: x[1].cumtime,
            reverse=True,
        )[:20]

        for rank, (func, func_stats) in enumerate(sorted_stats, 1):
            func_name = f"{func[0]}:{func[1]}:{func[2]}"
            cumtime = func_stats.cumtime
            # ncalls can be a string like "1/1" for recursive calls
            ncalls_str = str(func_stats.ncalls)
            ncalls = int(ncalls_str.split("/")[0]) if "/" in ncalls_str else int(ncalls_str)
            time_per_call = (cumtime / ncalls * 1000) if ncalls > 0 else 0

            f.write(
                f"| {rank} | `{func_name}` | {cumtime:.3f} | {ncalls_str} | {time_per_call:.3f} |\n"
            )

        f.write("\n## Optimization Priorities for Epic 7\n\n")
        f.write("Based on profiling results, prioritize:\n\n")
        f.write(
            "1. **Decimal arithmetic operations** (if in top 10) - Implement in Rust with rust-decimal\n"
        )
        f.write("2. **Metrics calculations** (Sharpe, drawdown) - Vectorize with SIMD in Rust\n")
        f.write(
            "3. **Data aggregation** (Polars operations on Decimal) - Optimize type conversions\n"
        )
        f.write("4. **Commission calculations** - Batch processing in Rust if hot path\n")
        f.write("\n---\n\n")
        f.write(f"*Profile data: {profile_path}*\n")

    print(f"Markdown hotspots exported to: {md_output}")

    # Print top 10 to console
    print("\n" + "=" * 80)
    print("TOP 10 HOTSPOTS FOR EPIC 7 OPTIMIZATION:")
    print("=" * 80)

    for rank, (func, func_stats) in enumerate(sorted_stats[:10], 1):
        func_name = f"{func[0]}:{func[1]}:{func[2]}"
        cumtime = func_stats.cumtime
        total_time = sum(s.cumtime for s in stats_list.func_profiles.values())
        percentage = (cumtime / total_time * 100) if total_time > 0 else 0

        print(f"{rank}. {func_name}")
        print(f"   {cumtime:.3f}s ({percentage:.1f}% of total time)\n")

    print("=" * 80)
    print("\nProfiler run complete!")


if __name__ == "__main__":
    main()
