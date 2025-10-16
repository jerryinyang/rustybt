#!/usr/bin/env python
#
# Copyright 2025 RustyBT Contributors
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

"""
Example Strategy: High-Frequency Trading with Custom Event Triggers

This example demonstrates the new event system capabilities:
1. Sub-second (millisecond) data resolution
2. Custom price threshold triggers
3. Custom time interval triggers
4. Event priority handling

Strategy Logic:
- Monitor AAPL stock price
- Trigger buy signal when price crosses above $150
- Trigger sell signal when price crosses below $145
- Rebalance portfolio every 5 minutes
- Execute trades with millisecond precision
"""

from decimal import Decimal

import pandas as pd

from rustybt import TradingAlgorithm
from rustybt.api import order_target_percent, symbol
from rustybt.gens.events import EventPriority, PriceThresholdTrigger, TimeIntervalTrigger


class HighFrequencyTriggerStrategy(TradingAlgorithm):
    """
    High-frequency strategy using custom event triggers.

    Demonstrates:
    - Price threshold triggers for entry/exit signals
    - Time interval triggers for periodic rebalancing
    - Sub-second event handling
    """

    def initialize(self, context):
        """
        Initialize strategy with custom triggers.

        Args:
            context: Strategy context object
        """
        # Set up assets
        context.asset = symbol("AAPL")

        # Strategy parameters
        context.buy_threshold = Decimal("150.00")
        context.sell_threshold = Decimal("145.00")
        context.position_size = Decimal("0.5")  # 50% of portfolio

        # State tracking
        context.last_signal = None
        context.trades_today = 0
        context.max_trades_per_day = 10

        # Register price threshold trigger for buy signal
        buy_trigger = PriceThresholdTrigger(
            asset=context.asset,
            threshold=context.buy_threshold,
            direction="above",
            field="close",
        )
        self.register_trigger(buy_trigger, self.on_buy_signal, priority=EventPriority.CUSTOM)

        # Register price threshold trigger for sell signal
        sell_trigger = PriceThresholdTrigger(
            asset=context.asset,
            threshold=context.sell_threshold,
            direction="below",
            field="close",
        )
        self.register_trigger(sell_trigger, self.on_sell_signal, priority=EventPriority.CUSTOM)

        # Register time interval trigger for periodic rebalancing
        rebalance_trigger = TimeIntervalTrigger(
            interval=pd.Timedelta(minutes=5), callback=self.rebalance_portfolio
        )
        self.register_trigger(rebalance_trigger, priority=EventPriority.CUSTOM)

        self.log.info(
            "Strategy initialized with buy threshold=%s, sell threshold=%s",
            context.buy_threshold,
            context.sell_threshold,
        )

    def on_buy_signal(self, context, data):
        """
        Execute when price crosses above buy threshold.

        Args:
            context: Strategy context
            data: Current market data
        """
        if context.trades_today >= context.max_trades_per_day:
            self.log.warning("Max trades per day reached, skipping buy signal")
            return

        current_price = data.current(context.asset, "price")
        self.log.info(
            "Buy signal triggered at price=%s (threshold=%s)",
            current_price,
            context.buy_threshold,
        )

        # Enter long position
        order_target_percent(context.asset, context.position_size)
        context.last_signal = "buy"
        context.trades_today += 1

    def on_sell_signal(self, context, data):
        """
        Execute when price crosses below sell threshold.

        Args:
            context: Strategy context
            data: Current market data
        """
        if context.trades_today >= context.max_trades_per_day:
            self.log.warning("Max trades per day reached, skipping sell signal")
            return

        current_price = data.current(context.asset, "price")
        self.log.info(
            "Sell signal triggered at price=%s (threshold=%s)",
            current_price,
            context.sell_threshold,
        )

        # Exit position
        order_target_percent(context.asset, 0)
        context.last_signal = "sell"
        context.trades_today += 1

    def rebalance_portfolio(self, context, data):
        """
        Periodic portfolio rebalancing (every 5 minutes).

        Args:
            context: Strategy context
            data: Current market data
        """
        current_time = self.get_datetime()
        position = self.portfolio.positions.get(context.asset)

        if position:
            self.log.info(
                "Rebalancing at %s: position=%s shares, value=%s",
                current_time,
                position.amount,
                position.market_value,
            )
        else:
            self.log.info("Rebalancing at %s: no position", current_time)

    def before_trading_start(self, context, data):
        """
        Reset daily counters before market open.

        Args:
            context: Strategy context
            data: Pre-market data
        """
        context.trades_today = 0
        self.log.info("New trading day started, reset trade counter")

    def handle_data(self, context, data):
        """
        Main event handler called on every bar.

        With millisecond resolution, this is called every millisecond.
        Custom triggers handle the actual trading logic.

        Args:
            context: Strategy context
            data: Current market data
        """
        # Custom triggers handle all trading logic
        # This method can be used for monitoring or additional logic
        pass


if __name__ == "__main__":
    """
    Run the strategy with millisecond data resolution.

    Usage:
        python examples/high_frequency_custom_triggers.py
    """
    from rustybt import run_algorithm

    # Run backtest with millisecond resolution
    result = run_algorithm(
        initialize=HighFrequencyTriggerStrategy.initialize,
        handle_data=HighFrequencyTriggerStrategy.handle_data,
        before_trading_start=HighFrequencyTriggerStrategy.before_trading_start,
        start=pd.Timestamp("2023-01-01", tz="UTC"),
        end=pd.Timestamp("2023-01-31", tz="UTC"),
        capital_base=100000,
        data_frequency="millisecond",  # Sub-second resolution
    )

    # Print results
    print("=" * 60)
    print("Strategy Performance Summary")
    print("=" * 60)
    print(f"Total Return: {result['returns'].iloc[-1]:.2%}")
    print(f"Sharpe Ratio: {result['sharpe']:.2f}")
    print(f"Max Drawdown: {result['max_drawdown']:.2%}")
    print(f"Total Trades: {len(result['transactions'])}")
    print("=" * 60)
