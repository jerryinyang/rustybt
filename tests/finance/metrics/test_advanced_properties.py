"""Property-based tests for advanced performance metrics.

Uses Hypothesis to test metric properties with randomly generated data.
"""

import numpy as np
import pandas as pd
from hypothesis import given, settings
from hypothesis import strategies as st

from rustybt.finance.metrics.advanced import (
    calmar_ratio,
    conditional_value_at_risk,
    profit_factor,
    value_at_risk,
    win_rate,
)


# Custom strategies for generating valid financial data
@st.composite
def returns_strategy(draw, min_size=10, max_size=1000):
    """Generate valid return series."""
    size = draw(st.integers(min_value=min_size, max_value=max_size))
    returns = draw(
        st.lists(
            st.floats(min_value=-0.20, max_value=0.20, allow_nan=False, allow_infinity=False),
            min_size=size,
            max_size=size,
        )
    )
    return np.array(returns)


@st.composite
def transactions_strategy(draw, min_size=5, max_size=100):
    """Generate valid transaction DataFrames."""
    size = draw(st.integers(min_value=min_size, max_value=max_size))
    pnl_values = draw(
        st.lists(
            st.floats(min_value=-1000.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
            min_size=size,
            max_size=size,
        )
    )
    return pd.DataFrame({"pnl": pnl_values})


class TestVaRProperties:
    """Property-based tests for VaR."""

    @given(returns=returns_strategy())
    @settings(max_examples=200, deadline=None)
    def test_var_is_non_negative(self, returns):
        """VaR should always be non-negative (loss magnitude)."""
        var_95 = value_at_risk(returns, confidence_level=0.95)

        if np.isfinite(var_95):
            assert var_95 >= 0

    @given(returns=returns_strategy())
    @settings(max_examples=200, deadline=None)
    def test_var_99_worse_than_var_95(self, returns):
        """VaR at 99% should always be >= VaR at 95% (worse loss)."""
        var_95 = value_at_risk(returns, confidence_level=0.95)
        var_99 = value_at_risk(returns, confidence_level=0.99)

        if np.isfinite(var_95) and np.isfinite(var_99):
            assert var_99 >= var_95

    @given(returns=returns_strategy())
    @settings(max_examples=200, deadline=None)
    def test_var_bounded_by_max_loss(self, returns):
        """VaR should not exceed maximum observed loss."""
        var_95 = value_at_risk(returns, confidence_level=0.95)
        max_loss = abs(np.min(returns))

        if np.isfinite(var_95):
            # Allow small numerical tolerance
            assert var_95 <= max_loss + 1e-6


class TestCVaRProperties:
    """Property-based tests for CVaR."""

    @given(returns=returns_strategy())
    @settings(max_examples=200, deadline=None)
    def test_cvar_is_non_negative(self, returns):
        """CVaR should always be non-negative (loss magnitude)."""
        cvar_95 = conditional_value_at_risk(returns, confidence_level=0.95)

        if np.isfinite(cvar_95):
            assert cvar_95 >= 0

    @given(returns=returns_strategy())
    @settings(max_examples=200, deadline=None)
    def test_cvar_worse_than_var(self, returns):
        """CVaR should always be >= VaR at same confidence level."""
        var_95 = value_at_risk(returns, confidence_level=0.95)
        cvar_95 = conditional_value_at_risk(returns, confidence_level=0.95)

        if np.isfinite(var_95) and np.isfinite(cvar_95):
            # CVaR should be at least as bad as VaR
            assert cvar_95 >= var_95 - 1e-6  # Allow small numerical tolerance

    @given(returns=returns_strategy())
    @settings(max_examples=200, deadline=None)
    def test_cvar_99_worse_than_cvar_95(self, returns):
        """CVaR at 99% should be >= CVaR at 95%."""
        cvar_95 = conditional_value_at_risk(returns, confidence_level=0.95)
        cvar_99 = conditional_value_at_risk(returns, confidence_level=0.99)

        if np.isfinite(cvar_95) and np.isfinite(cvar_99):
            assert cvar_99 >= cvar_95 - 1e-6  # Allow small numerical tolerance

    @given(returns=returns_strategy())
    @settings(max_examples=200, deadline=None)
    def test_cvar_bounded_by_max_loss(self, returns):
        """CVaR should not exceed maximum observed loss."""
        cvar_95 = conditional_value_at_risk(returns, confidence_level=0.95)
        max_loss = abs(np.min(returns))

        if np.isfinite(cvar_95):
            assert cvar_95 <= max_loss + 1e-6


class TestCalmarRatioProperties:
    """Property-based tests for Calmar ratio."""

    @given(returns=returns_strategy(min_size=30))
    @settings(max_examples=200, deadline=None)
    def test_calmar_ratio_sign(self, returns):
        """Calmar ratio sign should match total return sign."""
        from empyrical import cum_returns_final, max_drawdown

        total_return = cum_returns_final(returns)
        max_dd = max_drawdown(returns)
        calmar = calmar_ratio(returns, periods=252)

        if np.isfinite(calmar) and not np.isinf(calmar):
            # If total return is positive, Calmar should be positive
            if total_return > 0 and max_dd < 0:
                assert calmar > 0
            # If total return is negative, Calmar should be negative
            elif total_return < 0 and max_dd < 0:
                assert calmar < 0

    @given(returns=returns_strategy(min_size=30))
    @settings(max_examples=200, deadline=None)
    def test_calmar_ratio_no_drawdown(self, returns):
        """If all returns are positive (no drawdown), Calmar should be infinite."""
        # Filter to all positive returns
        if np.all(returns > 0):
            calmar = calmar_ratio(returns, periods=252)
            assert np.isinf(calmar)


class TestWinRateProperties:
    """Property-based tests for win rate."""

    @given(transactions=transactions_strategy())
    @settings(max_examples=200, deadline=None)
    def test_win_rate_bounded(self, transactions):
        """Win rate should be between 0 and 100."""
        wr = win_rate(transactions)

        if np.isfinite(wr):
            assert 0 <= wr <= 100

    @given(transactions=transactions_strategy())
    @settings(max_examples=200, deadline=None)
    def test_win_rate_all_positive(self, transactions):
        """If all trades are positive, win rate should be 100."""
        # Filter to all positive
        transactions_pos = transactions[transactions["pnl"] > 0]

        if len(transactions_pos) > 0:
            wr = win_rate(transactions_pos)
            assert wr == 100.0

    @given(transactions=transactions_strategy())
    @settings(max_examples=200, deadline=None)
    def test_win_rate_all_negative(self, transactions):
        """If all trades are negative, win rate should be 0."""
        # Filter to all negative
        transactions_neg = transactions[transactions["pnl"] < 0]

        if len(transactions_neg) > 0:
            wr = win_rate(transactions_neg)
            assert wr == 0.0

    @given(transactions=transactions_strategy())
    @settings(max_examples=200, deadline=None)
    def test_win_rate_consistency(self, transactions):
        """Win rate should match manual calculation."""
        wr = win_rate(transactions)

        if len(transactions) > 0:
            manual_wr = (transactions["pnl"] > 0).sum() / len(transactions) * 100
            if np.isfinite(wr):
                assert abs(wr - manual_wr) < 0.01


class TestProfitFactorProperties:
    """Property-based tests for profit factor."""

    @given(transactions=transactions_strategy())
    @settings(max_examples=200, deadline=None)
    def test_profit_factor_non_negative(self, transactions):
        """Profit factor should always be non-negative."""
        pf = profit_factor(transactions)

        if np.isfinite(pf) and not np.isinf(pf):
            assert pf >= 0

    @given(transactions=transactions_strategy())
    @settings(max_examples=200, deadline=None)
    def test_profit_factor_all_positive(self, transactions):
        """If all trades are positive, profit factor should be infinite."""
        # Filter to all positive
        transactions_pos = transactions[transactions["pnl"] > 0]

        if len(transactions_pos) > 0:
            pf = profit_factor(transactions_pos)
            assert np.isinf(pf)

    @given(transactions=transactions_strategy())
    @settings(max_examples=200, deadline=None)
    def test_profit_factor_all_negative(self, transactions):
        """If all trades are negative, profit factor should be 0.0 (no profits)."""
        # Filter to all negative
        transactions_neg = transactions[transactions["pnl"] < 0]

        if len(transactions_neg) > 0:
            pf = profit_factor(transactions_neg)
            assert pf == 0.0

    @given(transactions=transactions_strategy())
    @settings(max_examples=200, deadline=None)
    def test_profit_factor_greater_than_one_for_profitable(self, transactions):
        """If total P&L is positive, profit factor should be > 1."""
        total_pnl = transactions["pnl"].sum()

        if total_pnl > 0:
            pf = profit_factor(transactions)

            if np.isfinite(pf) and not np.isinf(pf):
                assert pf > 1.0

    @given(transactions=transactions_strategy())
    @settings(max_examples=200, deadline=None)
    def test_profit_factor_less_than_one_for_losing(self, transactions):
        """If total P&L is negative, profit factor should be < 1."""
        total_pnl = transactions["pnl"].sum()

        if total_pnl < 0:
            pf = profit_factor(transactions)

            if np.isfinite(pf) and not np.isinf(pf):
                assert pf < 1.0

    @given(transactions=transactions_strategy())
    @settings(max_examples=200, deadline=None)
    def test_profit_factor_consistency(self, transactions):
        """Profit factor should match manual calculation."""
        pf = profit_factor(transactions)

        gross_profits = transactions[transactions["pnl"] > 0]["pnl"].sum()
        gross_losses = abs(transactions[transactions["pnl"] < 0]["pnl"].sum())

        if gross_losses > 0:
            manual_pf = gross_profits / gross_losses

            if np.isfinite(pf) and not np.isinf(pf):
                assert abs(pf - manual_pf) < 0.01
        elif gross_profits > 0:
            # All winners
            assert np.isinf(pf)
        else:
            # No profits or losses
            assert np.isnan(pf)


class TestCrossMetricProperties:
    """Property-based tests for relationships between metrics."""

    @given(returns=returns_strategy(min_size=30))
    @settings(max_examples=100, deadline=None)
    def test_var_cvar_ordering(self, returns):
        """Test that VaR95 <= CVaR95 <= CVaR99."""
        var_95 = value_at_risk(returns, confidence_level=0.95)
        cvar_95 = conditional_value_at_risk(returns, confidence_level=0.95)
        cvar_99 = conditional_value_at_risk(returns, confidence_level=0.99)

        if all(np.isfinite([var_95, cvar_95, cvar_99])):
            # Allow small numerical tolerance
            assert var_95 <= cvar_95 + 1e-6
            assert cvar_95 <= cvar_99 + 1e-6
