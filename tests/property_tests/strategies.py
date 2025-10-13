"""Custom Hypothesis strategies for property-based testing.

This module provides reusable Hypothesis strategies for generating
valid test data for financial calculations with Decimal precision.
"""

from decimal import Decimal

import polars as pl
from hypothesis import strategies as st


def decimal_prices(
    min_value: Decimal = Decimal("0.01"),
    max_value: Decimal = Decimal("10000"),
    scale: int = 2,
) -> st.SearchStrategy[Decimal]:
    """Generate Decimal prices with specified scale.

    Args:
        min_value: Minimum price (default: $0.01)
        max_value: Maximum price (default: $10,000)
        scale: Decimal places (default: 2 for equities, 8 for crypto)

    Returns:
        Hypothesis strategy generating Decimal prices
    """
    return st.decimals(
        min_value=min_value,
        max_value=max_value,
        places=scale,
        allow_nan=False,
        allow_infinity=False,
    )


def decimal_quantities(
    min_value: Decimal = Decimal("0.01"),
    max_value: Decimal = Decimal("10000"),
    scale: int = 2,
) -> st.SearchStrategy[Decimal]:
    """Generate Decimal quantities with specified scale.

    Args:
        min_value: Minimum quantity (default: 0.01)
        max_value: Maximum quantity (default: 10,000)
        scale: Decimal places (default: 2 for equities, 8 for crypto)

    Returns:
        Hypothesis strategy generating Decimal quantities
    """
    return st.decimals(
        min_value=min_value,
        max_value=max_value,
        places=scale,
        allow_nan=False,
        allow_infinity=False,
    )


def decimal_returns(
    min_return: Decimal = Decimal("-0.1"),
    max_return: Decimal = Decimal("0.1"),
) -> st.SearchStrategy[Decimal]:
    """Generate Decimal returns in realistic range.

    Args:
        min_return: Minimum return (default: -10%)
        max_return: Maximum return (default: +10%)

    Returns:
        Hypothesis strategy generating Decimal returns
    """
    return st.decimals(
        min_value=min_return,
        max_value=max_return,
        places=4,
        allow_nan=False,
        allow_infinity=False,
    )


@st.composite
def ohlcv_bars(draw: st.DrawFn, num_bars: int = 10, scale: int = 8) -> pl.DataFrame:
    """Generate valid OHLCV bars satisfying H >= max(O,C), L <= min(O,C).

    Args:
        draw: Hypothesis draw function
        num_bars: Number of bars to generate
        scale: Decimal places for prices (default: 8 for crypto)

    Returns:
        Polars DataFrame with valid OHLCV data
    """
    bars = []
    for _ in range(num_bars):
        # Generate open and close
        open_price = draw(decimal_prices(scale=scale))
        close_price = draw(decimal_prices(scale=scale))

        # Generate high >= max(open, close)
        max_oc = max(open_price, close_price)
        high_price = draw(
            st.decimals(
                min_value=max_oc,
                max_value=max_oc + Decimal("10"),
                places=scale,
                allow_nan=False,
                allow_infinity=False,
            )
        )

        # Generate low <= min(open, close)
        min_oc = min(open_price, close_price)
        low_price = draw(
            st.decimals(
                min_value=max(Decimal("0.01"), min_oc - Decimal("10")),
                max_value=min_oc,
                places=scale,
                allow_nan=False,
                allow_infinity=False,
            )
        )

        volume = draw(
            st.decimals(
                min_value=Decimal("100"),
                max_value=Decimal("1000000"),
                places=2,
                allow_nan=False,
                allow_infinity=False,
            )
        )

        bars.append(
            {
                "open": float(open_price),
                "high": float(high_price),
                "low": float(low_price),
                "close": float(close_price),
                "volume": float(volume),
            }
        )

    return pl.DataFrame(bars)


@st.composite
def decimal_portfolio_positions(
    draw: st.DrawFn, min_positions: int = 0, max_positions: int = 20
) -> list[tuple[Decimal, Decimal]]:
    """Generate list of (amount, price) tuples for portfolio positions.

    Args:
        draw: Hypothesis draw function
        min_positions: Minimum number of positions
        max_positions: Maximum number of positions

    Returns:
        List of (amount, price) tuples
    """
    num_positions = draw(st.integers(min_value=min_positions, max_value=max_positions))
    positions = []

    for _ in range(num_positions):
        amount = draw(decimal_quantities(max_value=Decimal("1000")))
        price = draw(decimal_prices(max_value=Decimal("500")))
        positions.append((amount, price))

    return positions


@st.composite
def decimal_transaction_sequence(
    draw: st.DrawFn, min_transactions: int = 1, max_transactions: int = 50
) -> list[tuple[str, Decimal, Decimal]]:
    """Generate sequence of (action, amount, price) tuples for transactions.

    Args:
        draw: Hypothesis draw function
        min_transactions: Minimum number of transactions
        max_transactions: Maximum number of transactions

    Returns:
        List of (action, amount, price) tuples where action is 'buy' or 'sell'
    """
    num_transactions = draw(st.integers(min_value=min_transactions, max_value=max_transactions))
    transactions = []

    for _ in range(num_transactions):
        action = draw(st.sampled_from(["buy", "sell"]))
        amount = draw(decimal_quantities(max_value=Decimal("100")))
        price = draw(decimal_prices(max_value=Decimal("500")))
        transactions.append((action, amount, price))

    return transactions


@st.composite
def commission_rates(
    draw: st.DrawFn,
    min_rate: Decimal = Decimal("0"),
    max_rate: Decimal = Decimal("0.01"),
) -> Decimal:
    """Generate valid commission rates.

    Args:
        draw: Hypothesis draw function
        min_rate: Minimum commission rate (default: 0%)
        max_rate: Maximum commission rate (default: 1%)

    Returns:
        Commission rate as Decimal
    """
    return draw(
        st.decimals(
            min_value=min_rate,
            max_value=max_rate,
            places=4,
            allow_nan=False,
            allow_infinity=False,
        )
    )


@st.composite
def return_series(
    draw: st.DrawFn,
    min_size: int = 10,
    max_size: int = 252,
    min_return: Decimal = Decimal("-0.1"),
    max_return: Decimal = Decimal("0.1"),
) -> list[Decimal]:
    """Generate series of returns for metrics testing.

    Args:
        draw: Hypothesis draw function
        min_size: Minimum series length
        max_size: Maximum series length (default: 252 trading days)
        min_return: Minimum return per period
        max_return: Maximum return per period

    Returns:
        List of Decimal returns
    """
    size = draw(st.integers(min_value=min_size, max_value=max_size))
    return [draw(decimal_returns(min_return, max_return)) for _ in range(size)]
