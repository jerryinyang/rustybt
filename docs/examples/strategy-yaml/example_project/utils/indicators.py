"""Technical indicators for strategy."""


def calculate_momentum(prices):
    """Calculate price momentum."""
    if len(prices) < 2:
        return 0
    return prices[-1] - prices[0]
