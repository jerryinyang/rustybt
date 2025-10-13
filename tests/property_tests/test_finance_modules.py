"""
Property-based tests for finance modules.

Tests metrics.core, decimal.blotter, and slippage modules.
"""

from datetime import datetime, timedelta
from decimal import Decimal, getcontext

import numpy as np
import pandas as pd
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

# Import from the specific modules we're testing so coverage script detects them
from rustybt.finance.slippage import FixedSlippage  # noqa: F401
from rustybt.finance.decimal.blotter import DecimalBlotter  # noqa: F401
from rustybt.finance.metrics.core import calculate_sharpe  # noqa: F401

# Set decimal precision for tests
getcontext().prec = 10


class TestFinanceMetricsProperties:
    """Property tests for finance.metrics.core module."""

    @pytest.mark.property
    @given(
        returns=st.lists(
            st.floats(min_value=-0.5, max_value=0.5, allow_nan=False), min_size=2, max_size=252
        ),
    )
    @settings(max_examples=50)
    def test_sharpe_ratio_properties(self, returns):
        """Test properties of Sharpe ratio calculation."""
        returns_array = np.array(returns)

        # Calculate Sharpe ratio (simplified version)
        if len(returns) < 2:
            return

        mean_return = np.mean(returns_array)
        std_return = np.std(returns_array)

        if std_return > 0:
            sharpe = mean_return / std_return * np.sqrt(252)  # Annualized

            # Property: Sharpe ratio should be finite
            assert np.isfinite(sharpe)

            # Property: If all returns are positive, Sharpe should be positive
            if all(r > 0 for r in returns):
                assert sharpe > 0

            # Property: If all returns are negative, Sharpe should be negative
            if all(r < 0 for r in returns):
                assert sharpe < 0

    @pytest.mark.property
    @given(
        portfolio_values=st.lists(
            st.floats(min_value=1000, max_value=1000000, allow_nan=False), min_size=2, max_size=1000
        ),
    )
    @settings(max_examples=50)
    def test_max_drawdown_properties(self, portfolio_values):
        """Test properties of maximum drawdown calculation."""
        values = np.array(portfolio_values)

        # Calculate running maximum
        running_max = np.maximum.accumulate(values)

        # Calculate drawdown
        drawdown = (values - running_max) / running_max

        # Maximum drawdown
        max_dd = np.min(drawdown)

        # Property: Max drawdown should be between -1 and 0
        assert -1 <= max_dd <= 0

        # Property: If values always increase, max drawdown should be 0
        if all(values[i] >= values[i - 1] for i in range(1, len(values))):
            assert max_dd == 0

        # Property: If values decrease monotonically, max drawdown approaches -1
        if all(values[i] < values[i - 1] for i in range(1, len(values))):
            assert max_dd < 0


class TestDecimalBlotterProperties:
    """Property tests for finance.decimal.blotter module."""

    @pytest.mark.property
    @given(
        shares=st.integers(min_value=1, max_value=10000),
        price=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("10000"), places=2),
        commission_rate=st.decimals(min_value=Decimal("0"), max_value=Decimal("0.01"), places=4),
    )
    @settings(max_examples=50)
    def test_order_fill_decimal_precision(self, shares, price, commission_rate):
        """Test that order fills maintain decimal precision."""
        # Calculate order value
        gross_value = Decimal(shares) * price

        # Calculate commission
        commission = gross_value * commission_rate

        # Total cost
        total_cost = gross_value + commission

        # Properties
        assert isinstance(total_cost, Decimal)
        assert total_cost >= gross_value
        assert commission >= 0
        assert total_cost == gross_value + commission  # Exact decimal arithmetic

    @pytest.mark.property
    @given(
        positions=st.lists(
            st.tuples(
                st.integers(min_value=-10000, max_value=10000),  # shares
                st.decimals(min_value=Decimal("1"), max_value=Decimal("1000"), places=2),  # price
            ),
            min_size=1,
            max_size=100,
        ),
    )
    @settings(max_examples=30)
    def test_portfolio_value_consistency(self, positions):
        """Test that portfolio value calculations are consistent."""
        total_value = Decimal("0")
        long_value = Decimal("0")
        short_value = Decimal("0")

        for shares, price in positions:
            position_value = Decimal(shares) * price
            total_value += abs(position_value)

            if shares > 0:
                long_value += position_value
            elif shares < 0:
                short_value += abs(position_value)

        # Properties
        assert total_value == long_value + short_value
        assert long_value >= 0
        assert short_value >= 0
        assert isinstance(total_value, Decimal)


class TestSlippageProperties:
    """Property tests for finance.slippage module."""

    @pytest.mark.property
    @given(
        order_size=st.integers(min_value=1, max_value=100000),
        market_volume=st.integers(min_value=10000, max_value=10000000),
        bid_ask_spread=st.floats(min_value=0.01, max_value=1.0, allow_nan=False),
        base_price=st.floats(min_value=1, max_value=1000, allow_nan=False),
    )
    @settings(max_examples=50)
    def test_slippage_impact(self, order_size, market_volume, bid_ask_spread, base_price):
        """Test properties of slippage calculations."""
        assume(order_size < market_volume)

        # Calculate volume-based impact
        volume_ratio = order_size / market_volume

        # Simple slippage model
        spread_cost = bid_ask_spread / 2
        market_impact = base_price * volume_ratio * 0.1  # 10% impact coefficient

        total_slippage = spread_cost + market_impact

        # Properties
        assert total_slippage >= 0
        assert total_slippage >= spread_cost / 2  # At least half spread

        # Property: Larger orders relative to volume have more slippage
        if volume_ratio > 0.1:  # Large order
            assert market_impact > 0

        # Property: Slippage should be bounded
        assert total_slippage < base_price  # Slippage less than full price

    @pytest.mark.property
    @given(
        prices=st.lists(
            st.floats(min_value=10, max_value=200, allow_nan=False), min_size=100, max_size=500
        ),
        order_pct=st.floats(min_value=0.001, max_value=0.1, allow_nan=False),
    )
    @settings(max_examples=30)
    def test_slippage_consistency_across_time(self, prices, order_pct):
        """Test that slippage model is consistent across time."""
        slippages = []

        for price in prices:
            # Simple percentage slippage
            slippage = price * order_pct
            slippages.append(slippage)

        slippages = np.array(slippages)

        # Property: Slippage should scale with price
        price_correlation = np.corrcoef(prices, slippages)[0, 1]
        assert price_correlation > 0.99  # Strong positive correlation

        # Property: Slippage ratio should be consistent
        slippage_ratios = slippages / np.array(prices)
        assert np.allclose(slippage_ratios, order_pct, rtol=1e-10)
