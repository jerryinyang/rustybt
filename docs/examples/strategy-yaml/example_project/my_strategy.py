"""Example momentum strategy with explicit code capture via strategy.yaml."""

from utils.indicators import calculate_momentum
from utils.risk import position_sizer


def initialize(context):
    """Initialize strategy."""
    context.asset = symbol("AAPL")
    context.position_size = 0.1


def handle_data(context, data):
    """Execute trading logic."""
    # Calculate momentum
    momentum = calculate_momentum(data.history(context.asset, "close", 20, "1d"))

    # Get position size
    size = position_sizer(context.portfolio.portfolio_value, context.position_size)

    # Trading logic
    if momentum > 0 and not context.portfolio.positions[context.asset]:
        order(context.asset, size)
    elif momentum < 0 and context.portfolio.positions[context.asset]:
        order(context.asset, -size)
