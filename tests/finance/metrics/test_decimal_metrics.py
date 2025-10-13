#
# Copyright 2025 RustyBT Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Unit tests for Decimal metrics calculations."""

from decimal import Decimal

import polars as pl
import pytest

from rustybt.finance.metrics import (
    InsufficientDataError,
    InvalidMetricError,
    calculate_calmar_ratio,
    calculate_cvar,
    calculate_excess_return,
    calculate_information_ratio,
    calculate_max_drawdown,
    calculate_profit_factor,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_tracking_error,
    calculate_var,
    calculate_win_rate,
)


class TestSharpeRatio:
    """Tests for Sharpe ratio calculation."""

    def test_sharpe_ratio_calculation(self):
        """Test Sharpe ratio with known returns."""
        returns = pl.Series(
            "returns",
            [
                Decimal("0.01"),
                Decimal("-0.005"),
                Decimal("0.015"),
                Decimal("0.02"),
                Decimal("-0.01"),
            ],
        )

        sharpe = calculate_sharpe_ratio(returns, risk_free_rate=Decimal("0"))

        # Verify calculation manually
        mean = Decimal(str(returns.mean()))
        std = Decimal(str(returns.std()))
        expected_sharpe = (mean / std) * Decimal("252").sqrt()

        assert sharpe == expected_sharpe

    def test_sharpe_ratio_with_risk_free_rate(self):
        """Test Sharpe ratio with non-zero risk-free rate."""
        returns = pl.Series("returns", [Decimal("0.05"), Decimal("0.03"), Decimal("0.04")])
        risk_free = Decimal("0.02")

        sharpe = calculate_sharpe_ratio(returns, risk_free_rate=risk_free)

        assert sharpe > Decimal("0")

    def test_sharpe_ratio_zero_volatility(self):
        """Test Sharpe ratio with zero volatility."""
        returns = pl.Series("returns", [Decimal("0.01"), Decimal("0.01"), Decimal("0.01")])

        sharpe = calculate_sharpe_ratio(returns)

        # Zero volatility should return 0
        assert sharpe == Decimal("0")

    def test_sharpe_ratio_insufficient_data(self):
        """Test Sharpe ratio with insufficient data."""
        returns = pl.Series("returns", [Decimal("0.01")])

        with pytest.raises(InsufficientDataError):
            calculate_sharpe_ratio(returns)


class TestSortinoRatio:
    """Tests for Sortino ratio calculation."""

    def test_sortino_ratio_with_mixed_returns(self):
        """Test Sortino ratio calculation with positive and negative returns."""
        returns = pl.Series(
            "returns",
            [Decimal("0.02"), Decimal("0.01"), Decimal("-0.01"), Decimal("0.03"), Decimal("-0.02")],
        )

        sortino = calculate_sortino_ratio(returns, risk_free_rate=Decimal("0"))

        # Calculate manually
        mean = Decimal(str(returns.mean()))
        downside_returns = returns.filter(returns < Decimal("0"))
        downside_std = Decimal(str(downside_returns.std()))

        expected_sortino = (mean / downside_std) * Decimal("252").sqrt()
        assert sortino == expected_sortino

    def test_sortino_ratio_no_negative_returns(self):
        """Test Sortino ratio with all positive returns."""
        returns = pl.Series("returns", [Decimal("0.02"), Decimal("0.01"), Decimal("0.03")])

        sortino = calculate_sortino_ratio(returns)

        # No downside risk means infinite Sortino
        assert sortino == Decimal("inf")

    def test_sortino_greater_than_sharpe(self):
        """Test that Sortino >= Sharpe when negative returns exist."""
        returns = pl.Series(
            "returns",
            [Decimal("0.05"), Decimal("-0.01"), Decimal("0.03"), Decimal("-0.02"), Decimal("0.04")],
        )

        sharpe = calculate_sharpe_ratio(returns)
        sortino = calculate_sortino_ratio(returns)

        # Sortino should be >= Sharpe (penalizes only downside)
        assert sortino >= sharpe


class TestMaxDrawdown:
    """Tests for maximum drawdown calculation."""

    def test_max_drawdown_calculation(self):
        """Test maximum drawdown with known scenario."""
        # Returns: start at 1.0, rise to 1.5, fall to 0.9
        cumulative_returns = pl.Series(
            "returns",
            [
                Decimal("1.0"),  # Start
                Decimal("1.2"),  # +20%
                Decimal("1.5"),  # +50% (peak)
                Decimal("1.3"),  # -13% from peak
                Decimal("0.9"),  # -40% from peak (max drawdown)
            ],
        )

        max_dd = calculate_max_drawdown(cumulative_returns)

        # Drawdown = (0.9 - 1.5) / 1.5 = -0.4 = -40%
        expected_dd = Decimal("-0.4")
        assert max_dd == expected_dd

    def test_max_drawdown_no_drawdown(self):
        """Test maximum drawdown with continuously rising values."""
        cumulative_returns = pl.Series(
            "returns", [Decimal("1.0"), Decimal("1.1"), Decimal("1.2"), Decimal("1.3")]
        )

        max_dd = calculate_max_drawdown(cumulative_returns)

        # No drawdown
        assert max_dd == Decimal("0")

    def test_max_drawdown_bounds(self):
        """Test that drawdown is in valid range [-1, 0]."""
        cumulative_returns = pl.Series(
            "returns", [Decimal("1.0"), Decimal("1.5"), Decimal("0.75"), Decimal("1.2")]
        )

        max_dd = calculate_max_drawdown(cumulative_returns)

        assert max_dd <= Decimal("0")
        assert max_dd >= Decimal("-1")

    def test_max_drawdown_empty_series(self):
        """Test maximum drawdown with empty series."""
        returns = pl.Series("returns", [], dtype=pl.Decimal)

        with pytest.raises(InsufficientDataError):
            calculate_max_drawdown(returns)


class TestCalmarRatio:
    """Tests for Calmar ratio calculation."""

    def test_calmar_ratio_calculation(self):
        """Test Calmar ratio calculation."""
        cumulative_returns = pl.Series(
            "returns", [Decimal("1.0"), Decimal("1.2"), Decimal("1.5"), Decimal("1.3")]
        )

        calmar = calculate_calmar_ratio(cumulative_returns, periods_per_year=252)

        # Calmar = annual_return / abs(max_drawdown)
        assert calmar > Decimal("0")

    def test_calmar_ratio_no_drawdown(self):
        """Test Calmar ratio with no drawdown."""
        cumulative_returns = pl.Series("returns", [Decimal("1.0"), Decimal("1.1"), Decimal("1.2")])

        calmar = calculate_calmar_ratio(cumulative_returns)

        # No drawdown means infinite Calmar
        assert calmar == Decimal("inf")


class TestVaRAndCVaR:
    """Tests for VaR and CVaR calculation."""

    def test_var_calculation(self):
        """Test VaR at 95% confidence level."""
        returns = pl.Series("returns", [Decimal(str(x / 100)) for x in range(-10, 11)])

        var_95 = calculate_var(returns, confidence_level=Decimal("0.05"))

        # 5th percentile of [-0.10, ..., 0.10]
        expected_var = Decimal(str(returns.quantile(0.05)))
        assert var_95 == expected_var

    def test_cvar_less_than_or_equal_var(self):
        """Test CVaR <= VaR invariant."""
        returns = pl.Series(
            "returns",
            [
                Decimal("0.02"),
                Decimal("0.01"),
                Decimal("-0.01"),
                Decimal("-0.03"),
                Decimal("-0.05"),
            ],
        )

        var_95 = calculate_var(returns, confidence_level=Decimal("0.05"))
        cvar_95 = calculate_cvar(returns, confidence_level=Decimal("0.05"))

        assert cvar_95 <= var_95

    def test_var_99_vs_var_95(self):
        """Test that VaR 99% < VaR 95% (more extreme)."""
        returns = pl.Series("returns", [Decimal(str(x / 100)) for x in range(-20, 21)])

        var_95 = calculate_var(returns, confidence_level=Decimal("0.05"))
        var_99 = calculate_var(returns, confidence_level=Decimal("0.01"))

        # 1% tail is more extreme than 5% tail
        assert var_99 < var_95


class TestWinRateAndProfitFactor:
    """Tests for win rate and profit factor calculations."""

    def test_win_rate_calculation(self):
        """Test win rate: count wins / count total."""
        trade_returns = pl.Series(
            "returns",
            [
                Decimal("0.05"),  # Win
                Decimal("-0.02"),  # Loss
                Decimal("0.03"),  # Win
                Decimal("0.01"),  # Win
                Decimal("-0.04"),  # Loss
            ],
        )

        win_rate = calculate_win_rate(trade_returns)

        # 3 wins out of 5 trades = 60%
        expected_win_rate = Decimal("3") / Decimal("5")
        assert win_rate == expected_win_rate
        assert win_rate == Decimal("0.6")

    def test_win_rate_bounds(self):
        """Test that win rate is in [0, 1]."""
        trade_returns = pl.Series("returns", [Decimal("0.05"), Decimal("-0.02"), Decimal("0.03")])

        win_rate = calculate_win_rate(trade_returns)

        assert Decimal("0") <= win_rate <= Decimal("1")

    def test_profit_factor_calculation(self):
        """Test profit factor = gross profits / gross losses."""
        trade_returns = pl.Series("returns", [Decimal("100"), Decimal("-50"), Decimal("75")])

        pf = calculate_profit_factor(trade_returns)

        # (100 + 75) / 50 = 3.5
        expected_pf = Decimal("175") / Decimal("50")
        assert pf == expected_pf
        assert pf == Decimal("3.5")

    def test_profit_factor_all_winners(self):
        """Test profit factor with all winning trades."""
        trade_returns = pl.Series("returns", [Decimal("100"), Decimal("75"), Decimal("150")])

        pf = calculate_profit_factor(trade_returns)

        # No losses means infinite profit factor
        assert pf == Decimal("inf")

    def test_profit_factor_no_profits(self):
        """Test profit factor with no profitable trades."""
        trade_returns = pl.Series("returns", [Decimal("-50"), Decimal("-25")])

        pf = calculate_profit_factor(trade_returns)

        # No profits means profit factor of 0
        assert pf == Decimal("0")


class TestBenchmarkComparison:
    """Tests for benchmark comparison metrics."""

    def test_excess_return_calculation(self):
        """Test excess return = strategy - benchmark."""
        strategy = pl.Series("returns", [Decimal("0.02"), Decimal("0.01")])
        benchmark = pl.Series("returns", [Decimal("0.015"), Decimal("0.005")])

        excess = calculate_excess_return(strategy, benchmark)

        expected = pl.Series("excess", [Decimal("0.005"), Decimal("0.005")])
        assert all(excess == expected)

    def test_excess_return_length_mismatch(self):
        """Test excess return with mismatched lengths."""
        strategy = pl.Series("returns", [Decimal("0.02"), Decimal("0.01")])
        benchmark = pl.Series("returns", [Decimal("0.015")])

        with pytest.raises(InvalidMetricError):
            calculate_excess_return(strategy, benchmark)

    def test_information_ratio_calculation(self):
        """Test Information ratio = mean(excess) / std(excess)."""
        strategy = pl.Series("returns", [Decimal("0.02"), Decimal("0.01"), Decimal("0.03")])
        benchmark = pl.Series("returns", [Decimal("0.015"), Decimal("0.005"), Decimal("0.02")])

        ir = calculate_information_ratio(strategy, benchmark)

        # Should be positive when strategy outperforms
        assert ir > Decimal("0")

    def test_tracking_error_calculation(self):
        """Test tracking error = std(excess returns)."""
        strategy = pl.Series("returns", [Decimal("0.02"), Decimal("0.01"), Decimal("0.03")])
        benchmark = pl.Series("returns", [Decimal("0.015"), Decimal("0.005"), Decimal("0.02")])

        te = calculate_tracking_error(strategy, benchmark)

        # Tracking error should be positive
        assert te > Decimal("0")


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_all_negative_returns(self):
        """Test metrics with all negative returns."""
        returns = pl.Series("returns", [Decimal("-0.01"), Decimal("-0.02"), Decimal("-0.015")])

        sharpe = calculate_sharpe_ratio(returns)
        sortino = calculate_sortino_ratio(returns)

        # Both should be negative
        assert sharpe < Decimal("0")
        assert sortino < Decimal("0")

    def test_single_large_loss(self):
        """Test drawdown with single large loss."""
        cumulative = pl.Series(
            "returns", [Decimal("1.0"), Decimal("1.1"), Decimal("1.2"), Decimal("0.5")]
        )

        max_dd = calculate_max_drawdown(cumulative)

        # Loss from 1.2 to 0.5 = -58.33%
        expected_dd = (Decimal("0.5") - Decimal("1.2")) / Decimal("1.2")
        assert abs(max_dd - expected_dd) < Decimal("0.0001")

    def test_very_small_returns(self):
        """Test metrics with very small returns."""
        returns = pl.Series("returns", [Decimal("0.0001"), Decimal("0.0002"), Decimal("-0.0001")])

        sharpe = calculate_sharpe_ratio(returns)

        # Should handle small values without overflow
        assert abs(sharpe) < Decimal("1000")
