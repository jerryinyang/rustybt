"""Simple live trading example with moving average crossover strategy.

This example demonstrates:
1. Same strategy code runs in both backtest and live modes (AC8)
2. Subscribing to market data and receiving updates
3. Order submission and fill handling
4. Event flow and strategy execution

Setup:
    pip install rustybt

    # For paper trading (no real capital):
    python examples/live_trading_simple.py --mode paper

    # For backtesting (same strategy):
    python examples/live_trading_simple.py --mode backtest

Strategy:
    Simple moving average crossover:
    - Buy when fast MA crosses above slow MA
    - Sell when fast MA crosses below slow MA
"""

import argparse
import asyncio
from decimal import Decimal

import pandas as pd
import structlog

from rustybt.algorithm import TradingAlgorithm

# Configure logging
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
)
logger = structlog.get_logger()


class SimpleMovingAverageCrossStrategy(TradingAlgorithm):
    """Simple moving average crossover strategy.

    This strategy implements a classic technical indicator:
    - Fast SMA (10 periods)
    - Slow SMA (30 periods)
    - Buy signal: fast crosses above slow
    - Sell signal: fast crosses below slow

    IMPORTANT: This exact same code runs in both backtest and live modes
    without any modifications. This demonstrates strategy reusability (AC8).
    """

    def initialize(self, context):
        """Called once at strategy startup.

        Args:
            context: Context object (same API in backtest and live)
        """
        # Set up strategy parameters
        context.asset = self.symbol("AAPL")
        self.sma_fast = 10
        self.sma_slow = 30

        # Track previous signal for crossover detection
        context.previous_signal = None

        logger.info(
            "strategy_initialized",
            asset=context.asset.symbol if hasattr(context.asset, "symbol") else "AAPL",
            sma_fast=self.sma_fast,
            sma_slow=self.sma_slow,
        )

    def handle_data(self, data):
        """Called every bar (minute/daily).

        This method is called identically in both backtest and live modes.

        Args:
            data: BarData object providing:
                  - data.current(asset, field) → current value
                  - data.history(asset, field, bar_count, frequency) → historical window
                  - data.can_trade(asset) → tradability check
        """
        context = self  # In TradingAlgorithm, context is self

        # Check if we can trade
        if not data.can_trade(context.asset):
            return

        # Get historical prices
        try:
            prices = data.history(context.asset, "close", self.sma_slow, "1d")
        except Exception as e:
            logger.warning("history_fetch_failed", error=str(e))
            return

        # Calculate moving averages
        fast_mavg = prices[-self.sma_fast :].mean()
        slow_mavg = prices.mean()

        # Generate signal
        signal = "buy" if fast_mavg > slow_mavg else "sell"

        # Detect crossover
        if context.previous_signal != signal:
            logger.info(
                "signal_change",
                previous=context.previous_signal,
                current=signal,
                fast_mavg=str(fast_mavg),
                slow_mavg=str(slow_mavg),
            )

            # Execute trade on crossover
            if signal == "buy":
                # Buy: target 100% of portfolio
                self.order_target_percent(context.asset, 1.0)
                logger.info("buy_order_submitted", target_pct=1.0)
            else:
                # Sell: target 0% of portfolio (liquidate)
                self.order_target_percent(context.asset, 0.0)
                logger.info("sell_order_submitted", target_pct=0.0)

            context.previous_signal = signal

    def on_order_fill(self, context, order_id, fill_price, fill_amount, commission):
        """Optional live trading callback for order fills.

        This method is ONLY called in live mode (not in backtest).
        It's optional - the strategy works without it.

        Args:
            context: Context object
            order_id: Order ID that was filled
            fill_price: Price at which order was filled
            fill_amount: Amount filled
            commission: Commission charged
        """
        logger.info(
            "order_filled",
            order_id=order_id,
            fill_price=str(fill_price),
            fill_amount=str(fill_amount),
            commission=str(commission),
        )


def run_backtest(strategy, start_date, end_date, capital_base):
    """Run strategy in backtest mode.

    Args:
        strategy: TradingAlgorithm instance
        start_date: Start date for backtest
        end_date: End date for backtest
        capital_base: Starting capital

    Returns:
        Backtest results
    """
    from rustybt import run_algorithm

    logger.info(
        "backtest_starting",
        start=start_date,
        end=end_date,
        capital=str(capital_base),
    )

    result = run_algorithm(
        strategy=strategy,
        start=pd.Timestamp(start_date),
        end=pd.Timestamp(end_date),
        capital_base=capital_base,
        data_frequency="daily",
        bundle="quandl",  # Or your configured bundle
    )

    logger.info("backtest_complete", final_value=str(result.portfolio_value[-1]))
    return result


async def run_live(strategy, broker_type="paper"):
    """Run strategy in live/paper trading mode.

    Args:
        strategy: TradingAlgorithm instance (same as backtest)
        broker_type: 'paper' for paper trading, or broker name for live

    Note:
        This uses the EXACT SAME strategy instance as backtest mode.
        No code changes needed (AC8: Strategy reusability validated).
    """
    from rustybt.live import LiveTradingEngine
    from rustybt.live.brokers import PaperBroker  # Will be implemented in Story 6.7

    logger.info("live_trading_starting", broker_type=broker_type)

    # Create broker adapter
    if broker_type == "paper":
        broker = PaperBroker()
    else:
        raise ValueError(f"Broker type not yet supported: {broker_type}")

    # Create live trading engine
    # Note: Same strategy class as backtest, no modifications
    engine = LiveTradingEngine(
        strategy=strategy,
        broker_adapter=broker,
        data_portal=None,  # Will be configured with PolarsDataPortal
        # portfolio and account will be created by engine
    )

    # Run engine
    try:
        await engine.run()
    except KeyboardInterrupt:
        logger.info("shutdown_requested")
        await engine.graceful_shutdown()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Simple Moving Average Crossover Strategy")
    parser.add_argument(
        "--mode",
        choices=["backtest", "paper", "live"],
        default="backtest",
        help="Trading mode: backtest, paper (simulation), or live (real)",
    )
    parser.add_argument(
        "--start",
        default="2023-01-01",
        help="Start date for backtest (YYYY-MM-DD)",
    )
    parser.add_argument("--end", default="2023-12-31", help="End date for backtest (YYYY-MM-DD)")
    parser.add_argument(
        "--capital",
        type=float,
        default=100000,
        help="Starting capital (default: 100000)",
    )
    parser.add_argument(
        "--broker",
        default="paper",
        help="Broker for live trading (default: paper)",
    )

    args = parser.parse_args()

    # Create strategy instance (same for all modes)
    strategy = SimpleMovingAverageCrossStrategy()

    if args.mode == "backtest":
        # Run in backtest mode
        result = run_backtest(
            strategy=strategy,
            start_date=args.start,
            end_date=args.end,
            capital_base=Decimal(str(args.capital)),
        )
        print("\nBacktest Results:")
        print(f"Final Portfolio Value: ${result.portfolio_value[-1]:,.2f}")

    elif args.mode in ("paper", "live"):
        # Run in live/paper mode
        asyncio.run(run_live(strategy=strategy, broker_type=args.broker))

    else:
        print(f"Unknown mode: {args.mode}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
