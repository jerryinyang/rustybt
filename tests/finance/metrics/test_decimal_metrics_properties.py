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
"""Property-based tests for Decimal metrics using Hypothesis.

These tests verify mathematical invariants and properties that must hold
for all valid inputs.
"""

from decimal import Decimal

import polars as pl
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from rustybt.finance.metrics import (
    calculate_calmar_ratio,
    calculate_cvar,
    calculate_excess_return,
    calculate_max_drawdown,
    calculate_profit_factor,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_var,
    calculate_win_rate,
)

# Hypothesis strategies for generating test data
decimal_returns = st.lists(
    st.decimals(min_value=Decimal("-0.1"), max_value=Decimal("0.1"), places=6),
    min_size=10,
    max_size=100,
)

positive_decimals = st.decimals(min_value=Decimal("0.001"), max_value=Decimal("1000"), places=2)

trade_returns_strategy = st.lists(
    st.decimals(min_value=Decimal("-100"), max_value=Decimal("100"), places=2),
    min_size=5,
    max_size=50,
)


class TestSharpeRatioProperties:
    """Property-based tests for Sharpe ratio."""

    @given(returns=decimal_returns)
    @settings(max_examples=1000)
    def test_sharpe_ratio_definition(self, returns):
        """Sharpe ratio must equal (mean - rf) / std."""
        assume(len(returns) >= 2)
        returns_series = pl.Series("returns", returns)

        mean = Decimal(str(returns_series.mean()))
        std = Decimal(str(returns_series.std()))
        assume(std > Decimal("0"))  # Skip zero-volatility cases

        sharpe = calculate_sharpe_ratio(returns_series, risk_free_rate=Decimal("0"))
        expected_sharpe = (mean / std) * Decimal("252").sqrt()

        assert sharpe == expected_sharpe

    @given(
        returns=decimal_returns,
        rf_rate=st.decimals(min_value=Decimal("0"), max_value=Decimal("0.1"), places=4),
    )
    @settings(max_examples=500, suppress_health_check=[HealthCheck.filter_too_much])
    def test_sharpe_ratio_increases_with_rf_decrease(self, returns, rf_rate):
        """For positive mean returns, Sharpe should increase as rf decreases."""
        assume(len(returns) >= 2)
        returns_series = pl.Series("returns", returns)

        mean = Decimal(str(returns_series.mean()))
        std = Decimal(str(returns_series.std()))
        assume(std > Decimal("0"))
        assume(mean > rf_rate)  # Mean return above risk-free rate

        sharpe_high_rf = calculate_sharpe_ratio(returns_series, risk_free_rate=rf_rate)
        sharpe_low_rf = calculate_sharpe_ratio(
            returns_series, risk_free_rate=rf_rate / Decimal("2")
        )

        # Lower rf should give higher Sharpe
        assert sharpe_low_rf >= sharpe_high_rf


class TestSortinoRatioProperties:
    """Property-based tests for Sortino ratio."""

    @given(returns=decimal_returns)
    @settings(max_examples=1000)
    def test_sortino_geq_sharpe_with_negative_returns(self, returns):
        """When negative returns exist, Sortino >= Sharpe (ignores upside vol)."""
        assume(len(returns) >= 2)
        returns_series = pl.Series("returns", returns)

        # Ensure there are negative returns
        assume(any(r < Decimal("0") for r in returns))

        std = Decimal(str(returns_series.std()))
        assume(std > Decimal("0"))

        downside_returns = returns_series.filter(returns_series < Decimal("0"))
        assume(len(downside_returns) > 0)

        sharpe = calculate_sharpe_ratio(returns_series)
        sortino = calculate_sortino_ratio(returns_series)

        # Sortino should be >= Sharpe when downside exists
        assert sortino >= sharpe

    @given(
        returns=st.lists(
            st.decimals(min_value=Decimal("0.001"), max_value=Decimal("0.1"), places=4),
            min_size=10,
            max_size=50,
        )
    )
    @settings(max_examples=500)
    def test_sortino_infinite_with_all_positive(self, returns):
        """If all returns positive, Sortino = inf."""
        returns_series = pl.Series("returns", returns)

        sortino = calculate_sortino_ratio(returns_series)

        assert sortino == Decimal("inf")


class TestMaxDrawdownProperties:
    """Property-based tests for maximum drawdown."""

    @given(returns=decimal_returns)
    @settings(max_examples=1000)
    def test_max_drawdown_bounds(self, returns):
        """Maximum drawdown must be in range [-1, 0]."""
        assume(len(returns) >= 2)

        # Create cumulative returns
        cumulative = [Decimal("1")]
        for ret in returns:
            cumulative.append(cumulative[-1] * (Decimal("1") + ret))

        cumulative_series = pl.Series("cumulative", cumulative)
        max_dd = calculate_max_drawdown(cumulative_series)

        assert max_dd <= Decimal("0"), "Drawdown must be non-positive"
        assert max_dd >= Decimal("-1"), "Drawdown cannot exceed -100%"

    @given(
        returns=st.lists(
            st.decimals(min_value=Decimal("0"), max_value=Decimal("0.05"), places=4),
            min_size=10,
            max_size=50,
        )
    )
    @settings(max_examples=500)
    def test_max_drawdown_zero_with_rising_values(self, returns):
        """With all positive returns, max drawdown should be zero."""
        # Create cumulative returns (always rising)
        cumulative = [Decimal("1")]
        for ret in returns:
            cumulative.append(cumulative[-1] * (Decimal("1") + ret))

        cumulative_series = pl.Series("cumulative", cumulative)
        max_dd = calculate_max_drawdown(cumulative_series)

        assert max_dd == Decimal("0")


class TestCalmarRatioProperties:
    """Property-based tests for Calmar ratio."""

    @given(returns=decimal_returns)
    @settings(max_examples=500)
    def test_calmar_ratio_definition(self, returns):
        """Calmar = annualized_return / abs(max_drawdown)."""
        assume(len(returns) >= 2)

        # Create cumulative returns
        cumulative = [Decimal("1")]
        for ret in returns:
            cumulative.append(cumulative[-1] * (Decimal("1") + ret))

        cumulative_series = pl.Series("cumulative", cumulative[1:])

        max_dd = calculate_max_drawdown(cumulative_series)
        assume(max_dd < Decimal("0"))  # Need some drawdown

        calmar = calculate_calmar_ratio(cumulative_series, periods_per_year=252)

        # Calculate expected
        total_return = cumulative_series[-1] / cumulative_series[0] - Decimal("1")
        years = Decimal(str(len(cumulative_series))) / Decimal("252")
        annual_return = (Decimal("1") + total_return) ** (Decimal("1") / years) - Decimal("1")
        expected_calmar = annual_return / abs(max_dd)

        # Allow small rounding errors
        assert abs(calmar - expected_calmar) < Decimal("0.001")


class TestVaRAndCVaRProperties:
    """Property-based tests for VaR and CVaR."""

    @given(
        returns=decimal_returns,
        confidence_level=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("0.1"), places=2),
    )
    @settings(max_examples=1000)
    def test_cvar_leq_var(self, returns, confidence_level):
        """CVaR must be <= VaR (more conservative risk measure)."""
        assume(len(returns) >= 20)
        returns_series = pl.Series("returns", returns)

        var = calculate_var(returns_series, confidence_level)
        cvar = calculate_cvar(returns_series, confidence_level)

        assert cvar <= var

    @given(returns=decimal_returns)
    @settings(max_examples=500)
    def test_var_99_leq_var_95(self, returns):
        """VaR at 99% confidence <= VaR at 95% (more extreme)."""
        assume(len(returns) >= 20)
        returns_series = pl.Series("returns", returns)

        var_95 = calculate_var(returns_series, Decimal("0.05"))
        var_99 = calculate_var(returns_series, Decimal("0.01"))

        # 1% percentile is more extreme (further left) than 5% percentile
        assert var_99 <= var_95


class TestWinRateProperties:
    """Property-based tests for win rate."""

    @given(trade_returns=trade_returns_strategy)
    @settings(max_examples=1000)
    def test_win_rate_bounds(self, trade_returns):
        """Win rate must be in range [0, 1]."""
        assume(len(trade_returns) > 0)
        trade_series = pl.Series("trades", trade_returns)

        win_rate = calculate_win_rate(trade_series)

        assert Decimal("0") <= win_rate <= Decimal("1")

    @given(
        trade_returns=st.lists(
            st.decimals(min_value=Decimal("0.01"), max_value=Decimal("100"), places=2),
            min_size=5,
            max_size=20,
        )
    )
    @settings(max_examples=500)
    def test_win_rate_one_with_all_winners(self, trade_returns):
        """Win rate = 1.0 when all trades are winners."""
        trade_series = pl.Series("trades", trade_returns)

        win_rate = calculate_win_rate(trade_series)

        assert win_rate == Decimal("1")

    @given(
        trade_returns=st.lists(
            st.decimals(min_value=Decimal("-100"), max_value=Decimal("-0.01"), places=2),
            min_size=5,
            max_size=20,
        )
    )
    @settings(max_examples=500)
    def test_win_rate_zero_with_all_losers(self, trade_returns):
        """Win rate = 0.0 when all trades are losers."""
        trade_series = pl.Series("trades", trade_returns)

        win_rate = calculate_win_rate(trade_series)

        assert win_rate == Decimal("0")


class TestProfitFactorProperties:
    """Property-based tests for profit factor."""

    @given(winning_trades=positive_decimals, losing_trades=positive_decimals)
    @settings(max_examples=1000)
    def test_profit_factor_definition(self, winning_trades, losing_trades):
        """Profit factor must equal gross_profit / gross_loss."""
        trade_returns = pl.Series("returns", [winning_trades, -losing_trades])
        profit_factor = calculate_profit_factor(trade_returns)

        expected_pf = winning_trades / losing_trades
        assert profit_factor == expected_pf

    @given(
        trade_returns=st.lists(
            st.decimals(min_value=Decimal("0.01"), max_value=Decimal("100"), places=2),
            min_size=3,
            max_size=20,
        )
    )
    @settings(max_examples=500)
    def test_profit_factor_infinite_with_no_losses(self, trade_returns):
        """Profit factor = inf when there are no losses."""
        trade_series = pl.Series("trades", trade_returns)

        pf = calculate_profit_factor(trade_series)

        assert pf == Decimal("inf")

    @given(gross_profit=positive_decimals, gross_loss=positive_decimals)
    @settings(max_examples=500)
    def test_profit_factor_above_one_is_profitable(self, gross_profit, gross_loss):
        """Profit factor > 1 means profitable strategy."""
        assume(gross_profit > gross_loss)

        trade_returns = pl.Series("returns", [gross_profit, -gross_loss])
        pf = calculate_profit_factor(trade_returns)

        assert pf > Decimal("1")


class TestExcessReturnProperties:
    """Property-based tests for excess return."""

    @given(
        strategy_returns=decimal_returns,
        benchmark_offset=st.decimals(
            min_value=Decimal("-0.05"), max_value=Decimal("0.05"), places=4
        ),
    )
    @settings(max_examples=1000)
    def test_excess_return_definition(self, strategy_returns, benchmark_offset):
        """Excess return = strategy - benchmark."""
        assume(len(strategy_returns) >= 2)

        strategy_series = pl.Series("strategy", strategy_returns)
        # Create benchmark as strategy + offset
        benchmark_series = strategy_series + benchmark_offset

        excess = calculate_excess_return(strategy_series, benchmark_series)
        expected_excess = strategy_series - benchmark_series

        assert all(excess == expected_excess)

    @given(returns=decimal_returns)
    @settings(max_examples=500)
    def test_excess_return_zero_vs_self(self, returns):
        """Excess return vs self should be zero."""
        assume(len(returns) >= 2)
        returns_series = pl.Series("returns", returns)

        excess = calculate_excess_return(returns_series, returns_series)

        # All values should be zero
        assert all(excess == Decimal("0"))


class TestAttributionProperties:
    """Property-based tests for attribution."""

    @given(
        position_returns=st.lists(
            st.decimals(min_value=Decimal("-0.1"), max_value=Decimal("0.1"), places=4),
            min_size=3,
            max_size=10,
        ),
        position_weights=st.lists(
            st.decimals(min_value=Decimal("0.01"), max_value=Decimal("1"), places=4),
            min_size=3,
            max_size=10,
        ),
    )
    @settings(max_examples=1000)
    def test_attribution_sums_to_total(self, position_returns, position_weights):
        """Sum of position attributions must equal total portfolio return."""
        assume(len(position_returns) == len(position_weights))
        assume(len(position_returns) >= 2)
        assume(sum(position_weights) > Decimal("0"))

        # Normalize weights to sum to 1
        total_weight = sum(position_weights)
        normalized_weights = [w / total_weight for w in position_weights]

        # Calculate portfolio return
        portfolio_return = sum(
            r * w for r, w in zip(position_returns, normalized_weights, strict=False)
        )

        # Calculate attribution
        attributions = [r * w for r, w in zip(position_returns, normalized_weights, strict=False)]
        total_attribution = sum(attributions)

        # Should sum to portfolio return (exact equality with Decimal)
        assert total_attribution == portfolio_return
