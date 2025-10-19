"""Risk management utilities."""


def position_sizer(portfolio_value, target_allocation):
    """Calculate position size based on portfolio value and allocation."""
    return int(portfolio_value * target_allocation)
