"""Simple single-file strategy for testing entry point detection."""

from rustybt import run_algorithm


def initialize(context):
    """Initialize strategy - runs once at start."""
    context.symbols = ["AAPL", "MSFT", "GOOGL"]
    context.invested = False


def handle_data(context, data):
    """Handle market data - runs every bar."""
    if not context.invested:
        for symbol in context.symbols:
            # order_target_percent(symbol, 0.33)
            pass
        context.invested = True


if __name__ == "__main__":
    # Entry point - this is what entry point detection should find
    run_algorithm(
        start="2020-01-01",
        end="2020-12-31",
        initialize=initialize,
        handle_data=handle_data,
        capital_base=100000,
        bundle="quantopian-quandl",
    )
