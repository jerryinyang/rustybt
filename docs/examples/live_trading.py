# ruff: noqa
#!/usr/bin/env python3
"""
Live Trading Example

Demonstrates running a strategy in live trading mode with real-time data.

Requirements:
- Alpaca API credentials (free paper trading account)
- Set environment variables: ALPACA_API_KEY, ALPACA_API_SECRET
"""

import os
import sys
from decimal import Decimal

import pandas as pd

from rustybt import TradingAlgorithm
from rustybt.data.sources import DataSourceRegistry


class MeanReversionStrategy(TradingAlgorithm):
    """Simple mean reversion strategy for live trading."""

    def initialize(self):
        """Initialize strategy parameters."""
        self.symbols = ["AAPL", "MSFT"]
        self.lookback = 20  # days
        self.entry_threshold = Decimal("2.0")  # standard deviations
        self.positions = {}

        print(f"✓ Strategy initialized: {self.symbols}")

    def handle_data(self, context, data):
        """Execute on every bar (minute frequency)."""
        # Get current prices
        prices = data.current(self.symbols, "close")

        # Get historical data for z-score calculation
        history = data.history(
            self.symbols, fields="close", bar_count=self.lookback, frequency="1d"
        )

        for symbol in self.symbols:
            current_price = prices[symbol]
            hist_prices = history[symbol]

            # Calculate z-score
            mean = hist_prices.mean()
            std = hist_prices.std()

            if std > 0:
                z_score = (current_price - mean) / std

                # Entry signal: price 2 std deviations from mean
                if abs(z_score) > self.entry_threshold:
                    if z_score < -self.entry_threshold:
                        # Oversold: buy
                        if symbol not in self.positions:
                            self.order(symbol, 100)
                            self.positions[symbol] = "long"
                            print(f"🟢 BUY {symbol} @ {current_price} (z-score: {z_score:.2f})")

                    elif z_score > self.entry_threshold:
                        # Overbought: sell
                        if symbol in self.positions:
                            self.order(symbol, -100)
                            del self.positions[symbol]
                            print(f"🔴 SELL {symbol} @ {current_price} (z-score: {z_score:.2f})")

                # Exit signal: price returns to mean
                elif abs(z_score) < Decimal("0.5") and symbol in self.positions:
                    self.order(symbol, -100)
                    del self.positions[symbol]
                    print(f"↩️  EXIT {symbol} @ {current_price} (z-score: {z_score:.2f})")


def main():
    """Run live trading strategy."""
    # Check for API credentials
    api_key = os.getenv("ALPACA_API_KEY")
    api_secret = os.getenv("ALPACA_API_SECRET")

    if not api_key or not api_secret:
        print("❌ Error: Alpaca API credentials not found")
        print("\nSet environment variables:")
        print("  export ALPACA_API_KEY='your_api_key'")
        print("  export ALPACA_API_SECRET='your_api_secret'")
        print("\nGet free paper trading account at: https://alpaca.markets")
        sys.exit(1)

    # Create live data source
    print("📡 Connecting to Alpaca (paper trading)...")
    source = DataSourceRegistry.get_source(
        "alpaca", api_key=api_key, api_secret=api_secret, paper_trading=True
    )

    # Create and run live trading algorithm
    print("🚀 Starting live trading strategy...")
    algo = MeanReversionStrategy(
        data_source=source,
        live_trading=True,  # No caching, real-time data
        start=pd.Timestamp.now(),
    )

    try:
        algo.run()  # Runs indefinitely
    except KeyboardInterrupt:
        print("\n⏸️  Strategy stopped by user")

    # Print final results
    print("\n📊 Live Trading Summary:")
    print(f"Total orders: {len(algo.blotter.orders)}")
    print(f"Portfolio value: ${algo.portfolio.portfolio_value}")


if __name__ == "__main__":
    main()
