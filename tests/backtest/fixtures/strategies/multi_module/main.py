"""Main entry point for multi-module strategy."""

from utils.indicators import calculate_bollinger, calculate_rsi
from utils.risk_management import calculate_position_size

from rustybt import run_algorithm


def initialize(context):
    """Initialize strategy."""
    context.symbols = ["AAPL", "MSFT"]
    context.rsi_period = 14


def handle_data(context, data):
    """Handle market data."""
    for symbol in context.symbols:
        # Get price history (simplified for testing)
        price_history = [100, 101, 102, 103, 104]

        rsi = calculate_rsi(price_history, context.rsi_period)
        bollinger = calculate_bollinger(price_history)

        # Trading logic
        if rsi < 30:  # Oversold
            position_size = calculate_position_size(context, symbol)
            # order(symbol, position_size)
            pass


if __name__ == "__main__":
    # Entry point - this is what entry point detection should find
    run_algorithm(
        start="2020-01-01",
        end="2020-12-31",
        initialize=initialize,
        handle_data=handle_data,
        capital_base=100000,
    )
