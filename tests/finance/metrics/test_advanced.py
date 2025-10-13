"""Tests for advanced performance metrics.

Tests Calmar ratio, VaR, CVaR, win rate, and profit factor calculations.
"""

import numpy as np
import pandas as pd
import pytest

from rustybt.finance.metrics.advanced import (
    calmar_ratio,
    conditional_value_at_risk,
    profit_factor,
    value_at_risk,
    win_rate,
)


class TestCalmarRatio:
    """Tests for Calmar ratio calculation."""

    def test_calmar_ratio_positive_returns(self):
        """Test Calmar ratio with positive returns and drawdown."""
        # Generate returns with known characteristics
        # Total return of ~20%, max drawdown of ~10%
        returns = np.array([0.05, -0.10, 0.08, 0.03, 0.02, 0.04, -0.05, 0.06, 0.04, 0.03])

        calmar = calmar_ratio(returns, periods=252)

        # Calmar should be positive with positive total returns
        assert calmar > 0
        assert np.isfinite(calmar)

    def test_calmar_ratio_no_drawdown(self):
        """Test Calmar ratio with no drawdown (all positive returns)."""
        returns = np.array([0.01, 0.02, 0.03, 0.01, 0.02])

        calmar = calmar_ratio(returns, periods=252)

        # With no drawdown, Calmar should be infinite
        assert np.isinf(calmar)

    def test_calmar_ratio_insufficient_data(self):
        """Test Calmar ratio with insufficient data."""
        returns = np.array([0.01])

        calmar = calmar_ratio(returns, periods=252)

        assert np.isnan(calmar)

    def test_calmar_ratio_negative_returns(self):
        """Test Calmar ratio with negative total returns."""
        returns = np.array([-0.05, -0.03, -0.02, -0.01, 0.01])

        calmar = calmar_ratio(returns, periods=252)

        # Calmar can be negative with negative returns
        assert np.isfinite(calmar) or np.isnan(calmar)


class TestValueAtRisk:
    """Tests for Value at Risk calculation."""

    def test_var_95_historical(self):
        """Test VaR at 95% confidence level using historical method."""
        # Generate normal returns
        np.random.seed(42)
        returns = np.random.normal(0.001, 0.02, 1000)

        var_95 = value_at_risk(returns, confidence_level=0.95, method="historical")

        # VaR should be positive
        assert var_95 > 0
        assert np.isfinite(var_95)

        # VaR should be approximately 2 standard deviations for 95% confidence
        std = np.std(returns)
        assert var_95 < 3 * std  # Sanity check

    def test_var_99_historical(self):
        """Test VaR at 99% confidence level using historical method."""
        np.random.seed(42)
        returns = np.random.normal(0.001, 0.02, 1000)

        var_99 = value_at_risk(returns, confidence_level=0.99, method="historical")

        # VaR should be positive
        assert var_99 > 0
        assert np.isfinite(var_99)

    def test_var_99_worse_than_var_95(self):
        """Test that VaR99 is worse (higher) than VaR95."""
        np.random.seed(42)
        returns = np.random.normal(0.001, 0.02, 1000)

        var_95 = value_at_risk(returns, confidence_level=0.95)
        var_99 = value_at_risk(returns, confidence_level=0.99)

        # VaR99 should be >= VaR95 (worse loss)
        assert var_99 >= var_95

    def test_var_parametric(self):
        """Test VaR using parametric method."""
        np.random.seed(42)
        returns = np.random.normal(0.001, 0.02, 1000)

        var_parametric = value_at_risk(returns, confidence_level=0.95, method="parametric")

        assert var_parametric > 0
        assert np.isfinite(var_parametric)

    def test_var_insufficient_data(self):
        """Test VaR with insufficient data."""
        returns = np.array([0.01])

        var = value_at_risk(returns, confidence_level=0.95)

        assert np.isnan(var)

    def test_var_invalid_method(self):
        """Test VaR with invalid method."""
        returns = np.array([0.01, -0.02, 0.03])

        with pytest.raises(ValueError, match="Unknown method"):
            value_at_risk(returns, confidence_level=0.95, method="invalid")


class TestConditionalValueAtRisk:
    """Tests for Conditional Value at Risk calculation."""

    def test_cvar_95(self):
        """Test CVaR at 95% confidence level."""
        np.random.seed(42)
        returns = np.random.normal(0.001, 0.02, 1000)

        cvar_95 = conditional_value_at_risk(returns, confidence_level=0.95)

        # CVaR should be positive
        assert cvar_95 > 0
        assert np.isfinite(cvar_95)

    def test_cvar_99(self):
        """Test CVaR at 99% confidence level."""
        np.random.seed(42)
        returns = np.random.normal(0.001, 0.02, 1000)

        cvar_99 = conditional_value_at_risk(returns, confidence_level=0.99)

        # CVaR should be positive
        assert cvar_99 > 0
        assert np.isfinite(cvar_99)

    def test_cvar_worse_than_var(self):
        """Test that CVaR is worse (higher) than VaR at same confidence level."""
        np.random.seed(42)
        returns = np.random.normal(0.001, 0.02, 1000)

        var_95 = value_at_risk(returns, confidence_level=0.95)
        cvar_95 = conditional_value_at_risk(returns, confidence_level=0.95)

        # CVaR should be >= VaR (more conservative)
        assert cvar_95 >= var_95

    def test_cvar_99_worse_than_cvar_95(self):
        """Test that CVaR99 is worse than CVaR95."""
        np.random.seed(42)
        returns = np.random.normal(0.001, 0.02, 1000)

        cvar_95 = conditional_value_at_risk(returns, confidence_level=0.95)
        cvar_99 = conditional_value_at_risk(returns, confidence_level=0.99)

        # CVaR99 should be >= CVaR95
        assert cvar_99 >= cvar_95

    def test_cvar_insufficient_data(self):
        """Test CVaR with insufficient data."""
        returns = np.array([0.01])

        cvar = conditional_value_at_risk(returns, confidence_level=0.95)

        assert np.isnan(cvar)

    def test_cvar_with_known_distribution(self):
        """Test CVaR with a known distribution."""
        # Create a distribution with known tail
        returns = np.concatenate(
            [
                np.repeat(-0.05, 10),  # 1% worst losses
                np.repeat(-0.03, 40),  # Next 4% losses
                np.repeat(-0.01, 50),  # Next 5% losses
                np.repeat(0.01, 900),  # Rest are gains
            ]
        )
        np.random.shuffle(returns)

        cvar_95 = conditional_value_at_risk(returns, confidence_level=0.95)

        # CVaR95 should be the mean of worst 5% (50 values)
        # Mean of [-0.05]*10 + [-0.03]*40 = (-0.5 - 1.2) / 50 = -0.034
        expected_cvar = abs(-0.034)

        assert abs(cvar_95 - expected_cvar) < 0.01  # Allow for some variation


class TestWinRate:
    """Tests for win rate calculation."""

    def test_win_rate_mixed_trades(self):
        """Test win rate with mixed winning and losing trades."""
        transactions = pd.DataFrame(
            {"pnl": [100, -50, 75, -25, 150, 200, -100]}
        )  # 4 wins, 3 losses

        wr = win_rate(transactions)

        expected = (4 / 7) * 100  # 57.14%
        assert abs(wr - expected) < 0.1

    def test_win_rate_all_winners(self):
        """Test win rate with all winning trades."""
        transactions = pd.DataFrame({"pnl": [100, 75, 150, 200]})

        wr = win_rate(transactions)

        assert wr == 100.0

    def test_win_rate_all_losers(self):
        """Test win rate with all losing trades."""
        transactions = pd.DataFrame({"pnl": [-50, -75, -100, -25]})

        wr = win_rate(transactions)

        assert wr == 0.0

    def test_win_rate_no_trades(self):
        """Test win rate with no trades."""
        transactions = pd.DataFrame({"pnl": []})

        wr = win_rate(transactions)

        assert np.isnan(wr)

    def test_win_rate_none_input(self):
        """Test win rate with None input."""
        wr = win_rate(None)

        assert np.isnan(wr)

    def test_win_rate_custom_column(self):
        """Test win rate with custom P&L column name."""
        transactions = pd.DataFrame({"profit": [100, -50, 75]})

        wr = win_rate(transactions, pnl_column="profit")

        expected = (2 / 3) * 100  # 66.67%
        assert abs(wr - expected) < 0.1

    def test_win_rate_missing_column(self):
        """Test win rate with missing P&L column."""
        transactions = pd.DataFrame({"amount": [100, -50, 75]})

        with pytest.raises(ValueError, match="Column 'pnl' not found"):
            win_rate(transactions)


class TestProfitFactor:
    """Tests for profit factor calculation."""

    def test_profit_factor_mixed_trades(self):
        """Test profit factor with mixed trades."""
        # Gross profits: 100 + 75 + 150 = 325
        # Gross losses: 50 + 25 = 75
        # Profit factor: 325 / 75 = 4.33
        transactions = pd.DataFrame({"pnl": [100, -50, 75, -25, 150]})

        pf = profit_factor(transactions)

        expected = 325.0 / 75.0
        assert abs(pf - expected) < 0.01

    def test_profit_factor_all_winners(self):
        """Test profit factor with all winning trades (infinite)."""
        transactions = pd.DataFrame({"pnl": [100, 75, 150]})

        pf = profit_factor(transactions)

        assert np.isinf(pf)

    def test_profit_factor_all_losers(self):
        """Test profit factor with all losing trades (should be 0.0)."""
        transactions = pd.DataFrame({"pnl": [-50, -75, -100]})

        pf = profit_factor(transactions)

        # No profits means profit factor = 0 / losses = 0.0
        assert pf == 0.0

    def test_profit_factor_break_even(self):
        """Test profit factor close to break-even."""
        # Gross profits: 100 + 50 = 150
        # Gross losses: 75 + 75 = 150
        # Profit factor: 150 / 150 = 1.0
        transactions = pd.DataFrame({"pnl": [100, -75, 50, -75]})

        pf = profit_factor(transactions)

        assert abs(pf - 1.0) < 0.01

    def test_profit_factor_no_trades(self):
        """Test profit factor with no trades."""
        transactions = pd.DataFrame({"pnl": []})

        pf = profit_factor(transactions)

        assert np.isnan(pf)

    def test_profit_factor_none_input(self):
        """Test profit factor with None input."""
        pf = profit_factor(None)

        assert np.isnan(pf)

    def test_profit_factor_custom_column(self):
        """Test profit factor with custom P&L column name."""
        transactions = pd.DataFrame({"profit": [100, -50, 75]})

        pf = profit_factor(transactions, pnl_column="profit")

        expected = 175.0 / 50.0
        assert abs(pf - expected) < 0.01

    def test_profit_factor_missing_column(self):
        """Test profit factor with missing P&L column."""
        transactions = pd.DataFrame({"amount": [100, -50, 75]})

        with pytest.raises(ValueError, match="Column 'pnl' not found"):
            profit_factor(transactions)

    def test_profit_factor_interpretation(self):
        """Test profit factor values fall into expected interpretation ranges."""
        # Excellent strategy (>2.0)
        transactions_excellent = pd.DataFrame({"pnl": [100, 100, 100, -25, -25]})
        pf_excellent = profit_factor(transactions_excellent)
        assert pf_excellent > 2.0

        # Marginally profitable (1.0-1.5)
        transactions_marginal = pd.DataFrame({"pnl": [100, 50, -75, -50]})
        pf_marginal = profit_factor(transactions_marginal)
        assert 1.0 <= pf_marginal <= 1.5

        # Losing strategy (<1.0)
        transactions_losing = pd.DataFrame({"pnl": [50, 25, -100, -75]})
        pf_losing = profit_factor(transactions_losing)
        assert pf_losing < 1.0
