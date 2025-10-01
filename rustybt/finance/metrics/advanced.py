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
"""Advanced performance metrics for RustyBT.

This module implements additional performance metrics beyond the standard
Sharpe and Sortino ratios, including risk metrics (VaR, CVaR) and trade
statistics (win rate, profit factor).
"""

from decimal import getcontext

import empyrical as ep
import numpy as np
import pandas as pd

# Set precision for financial calculations
getcontext().prec = 28


def calmar_ratio(returns: np.ndarray, periods: int = 252) -> float:
    """Calculate Calmar ratio (annualized return / maximum drawdown).

    The Calmar ratio measures risk-adjusted return using maximum drawdown
    as the risk measure. It's particularly useful for strategies where
    drawdown is the primary concern.

    Parameters
    ----------
    returns : np.ndarray
        Array of period returns (daily, minute, etc.)
    periods : int, optional
        Number of periods per year for annualization (default: 252 for daily)

    Returns:
    -------
    float
        Calmar ratio. Higher is better. Returns np.nan if max_drawdown is zero.

    Notes:
    -----
    Formula: Annualized Return / abs(Maximum Drawdown)

    Interpretation:
        - >3.0: Excellent
        - 1.0-3.0: Good
        - <1.0: Poor

    Examples:
    --------
    >>> returns = np.array([0.01, -0.02, 0.03, -0.01, 0.02])
    >>> calmar = calmar_ratio(returns)
    >>> print(f"Calmar Ratio: {calmar:.2f}")
    """
    if len(returns) < 2:
        return np.nan

    # Calculate annualized return
    total_return = ep.cum_returns_final(returns)
    years = len(returns) / periods
    if years == 0:
        return np.nan

    annualized_return = (1 + total_return) ** (1 / years) - 1

    # Calculate maximum drawdown
    max_dd = ep.max_drawdown(returns)

    # Calmar ratio = annualized return / abs(max drawdown)
    if max_dd == 0:
        # No drawdown means infinite Calmar ratio
        return np.inf if annualized_return > 0 else np.nan

    return annualized_return / abs(max_dd)


def value_at_risk(
    returns: np.ndarray, confidence_level: float = 0.95, method: str = "historical"
) -> float:
    """Calculate Value at Risk (VaR) at specified confidence level.

    VaR estimates the maximum loss at a given confidence level. For example,
    95% VaR of 2% means there's a 95% probability that losses won't exceed 2%.

    Parameters
    ----------
    returns : np.ndarray
        Array of period returns
    confidence_level : float, optional
        Confidence level (0.95 or 0.99 typically). Default is 0.95.
    method : str, optional
        Calculation method: 'historical' or 'parametric'. Default is 'historical'.

    Returns:
    -------
    float
        VaR as a positive value representing loss magnitude.
        Returns np.nan if insufficient data.

    Notes:
    -----
    - Historical VaR: Uses empirical percentile of return distribution
    - Parametric VaR: Assumes normal distribution (not yet implemented)
    - Returned as positive value: VaR of 0.05 means 5% potential loss

    Interpretation:
        - Lower is better (less tail risk)
        - VaR95: 95% confident losses won't exceed this value
        - VaR99: 99% confident losses won't exceed this value

    Examples:
    --------
    >>> returns = np.random.normal(0.001, 0.02, 1000)
    >>> var_95 = value_at_risk(returns, confidence_level=0.95)
    >>> var_99 = value_at_risk(returns, confidence_level=0.99)
    >>> print(f"VaR 95%: {var_95:.4f}, VaR 99%: {var_99:.4f}")
    """
    if len(returns) < 2:
        return np.nan

    if method == "historical":
        # Historical VaR: percentile of empirical distribution
        # Use (1 - confidence_level) percentile for left tail
        var = np.percentile(returns, (1 - confidence_level) * 100)
        # Return as positive value (loss magnitude)
        return abs(var)
    elif method == "parametric":
        # Parametric VaR: assumes normal distribution
        from scipy.stats import norm

        mean = np.mean(returns)
        std = np.std(returns, ddof=1)
        # Z-score for confidence level
        z_score = norm.ppf(1 - confidence_level)
        var = mean + z_score * std
        return abs(var)
    else:
        raise ValueError(f"Unknown method: {method}. Use 'historical' or 'parametric'.")


def conditional_value_at_risk(returns: np.ndarray, confidence_level: float = 0.95) -> float:
    """Calculate Conditional Value at Risk (CVaR / Expected Shortfall).

    CVaR is the expected loss in the worst (1 - confidence_level)% of cases.
    It's a more conservative risk measure than VaR because it captures the
    tail risk beyond the VaR threshold.

    Parameters
    ----------
    returns : np.ndarray
        Array of period returns
    confidence_level : float, optional
        Confidence level (0.95 or 0.99 typically). Default is 0.95.

    Returns:
    -------
    float
        CVaR as a positive value representing expected loss magnitude in tail.
        Returns np.nan if insufficient data.

    Notes:
    -----
    CVaR is also known as Expected Shortfall (ES) or Average Value at Risk (AVaR).

    Formula: CVaR = E[Loss | Loss > VaR]
    (Expected value of losses exceeding VaR threshold)

    Interpretation:
        - Lower is better (less tail risk)
        - CVaR95: Expected loss in worst 5% of scenarios
        - CVaR99: Expected loss in worst 1% of scenarios
        - CVaR >= VaR always (CVaR is more conservative)

    Examples:
    --------
    >>> returns = np.random.normal(0.001, 0.02, 1000)
    >>> cvar_95 = conditional_value_at_risk(returns, confidence_level=0.95)
    >>> cvar_99 = conditional_value_at_risk(returns, confidence_level=0.99)
    >>> print(f"CVaR 95%: {cvar_95:.4f}, CVaR 99%: {cvar_99:.4f}")
    """
    if len(returns) < 2:
        return np.nan

    # Calculate VaR threshold
    var_threshold = np.percentile(returns, (1 - confidence_level) * 100)

    # CVaR = mean of returns worse than VaR threshold
    tail_returns = returns[returns <= var_threshold]

    if len(tail_returns) == 0:
        return np.nan

    cvar = np.mean(tail_returns)

    # Return as positive value (loss magnitude)
    return abs(cvar)


def win_rate(transactions: pd.DataFrame, pnl_column: str = "pnl") -> float:
    """Calculate win rate (percentage of profitable trades).

    Parameters
    ----------
    transactions : pd.DataFrame
        DataFrame containing transaction records
    pnl_column : str, optional
        Name of the P&L column. Default is 'pnl'.

    Returns:
    -------
    float
        Win rate as percentage (0-100). Returns np.nan if no trades.

    Notes:
    -----
    Formula: (Number of Winning Trades / Total Trades) * 100

    A winning trade is one with pnl > 0.

    Interpretation:
        - >70%: Excellent
        - >60%: Good
        - 50-60%: Average
        - <50%: Below average

    Note: High win rate doesn't guarantee profitability. A strategy can have
    low win rate but high profit factor if winners are much larger than losers.

    Examples:
    --------
    >>> transactions = pd.DataFrame({'pnl': [100, -50, 75, -25, 150]})
    >>> wr = win_rate(transactions)
    >>> print(f"Win Rate: {wr:.2f}%")
    Win Rate: 60.00%
    """
    if transactions is None or len(transactions) == 0:
        return np.nan

    if pnl_column not in transactions.columns:
        raise ValueError(f"Column '{pnl_column}' not found in transactions DataFrame")

    pnl_series = transactions[pnl_column]

    # Count winning trades (pnl > 0)
    winning_trades = (pnl_series > 0).sum()
    total_trades = len(pnl_series)

    if total_trades == 0:
        return np.nan

    return (winning_trades / total_trades) * 100.0


def profit_factor(transactions: pd.DataFrame, pnl_column: str = "pnl") -> float:
    """Calculate profit factor (gross profits / gross losses).

    Parameters
    ----------
    transactions : pd.DataFrame
        DataFrame containing transaction records
    pnl_column : str, optional
        Name of the P&L column. Default is 'pnl'.

    Returns:
    -------
    float
        Profit factor. Returns np.nan if no trades or no losses.
        Returns np.inf if there are no losses (all winning trades).

    Notes:
    -----
    Formula: Gross Profits / abs(Gross Losses)

    Gross Profits = Sum of all positive P&L
    Gross Losses = Sum of all negative P&L (taken as absolute value)

    Interpretation:
        - >2.0: Excellent
        - 1.5-2.0: Good
        - 1.0-1.5: Marginally profitable
        - <1.0: Losing strategy
        - 1.0: Break-even

    Examples:
    --------
    >>> transactions = pd.DataFrame({'pnl': [100, -50, 75, -25, 150]})
    >>> pf = profit_factor(transactions)
    >>> print(f"Profit Factor: {pf:.2f}")
    Profit Factor: 4.33

    >>> # All winners (infinite profit factor)
    >>> transactions = pd.DataFrame({'pnl': [100, 75, 150]})
    >>> pf = profit_factor(transactions)
    >>> print(f"Profit Factor: {pf}")
    Profit Factor: inf
    """
    if transactions is None or len(transactions) == 0:
        return np.nan

    if pnl_column not in transactions.columns:
        raise ValueError(f"Column '{pnl_column}' not found in transactions DataFrame")

    pnl_series = transactions[pnl_column]

    # Calculate gross profits (sum of positive P&L)
    gross_profits = pnl_series[pnl_series > 0].sum()

    # Calculate gross losses (absolute value of sum of negative P&L)
    gross_losses = abs(pnl_series[pnl_series < 0].sum())

    if gross_losses == 0:
        # No losses means infinite profit factor (or nan if no profits either)
        return np.inf if gross_profits > 0 else np.nan

    return gross_profits / gross_losses


# Metric classes for integration with MetricsTracker


class VaRMetric:
    """Metric that reports Value at Risk at multiple confidence levels.

    Calculates VaR at 95% and 99% confidence levels from daily returns.
    """

    def __init__(self):
        self._confidence_levels = [0.95, 0.99]

    def end_of_bar(self, packet, ledger, dt, session_ix, data_portal):
        returns = ledger.daily_returns_array[: session_ix + 1]

        for confidence_level in self._confidence_levels:
            field_name = f"var_{int(confidence_level * 100)}"
            var_value = value_at_risk(returns, confidence_level=confidence_level)
            if not np.isfinite(var_value):
                var_value = None
            packet["cumulative_risk_metrics"][field_name] = var_value

    end_of_session = end_of_bar


class CVaRMetric:
    """Metric that reports Conditional Value at Risk at multiple confidence levels.

    Calculates CVaR at 95% and 99% confidence levels from daily returns.
    """

    def __init__(self):
        self._confidence_levels = [0.95, 0.99]

    def end_of_bar(self, packet, ledger, dt, session_ix, data_portal):
        returns = ledger.daily_returns_array[: session_ix + 1]

        for confidence_level in self._confidence_levels:
            field_name = f"cvar_{int(confidence_level * 100)}"
            cvar_value = conditional_value_at_risk(returns, confidence_level=confidence_level)
            if not np.isfinite(cvar_value):
                cvar_value = None
            packet["cumulative_risk_metrics"][field_name] = cvar_value

    end_of_session = end_of_bar


class CalmarRatioMetric:
    """Metric that reports Calmar ratio from daily returns."""

    def end_of_bar(self, packet, ledger, dt, session_ix, data_portal):
        returns = ledger.daily_returns_array[: session_ix + 1]
        calmar = calmar_ratio(returns, periods=252)
        if not np.isfinite(calmar):
            calmar = None
        packet["cumulative_risk_metrics"]["calmar_ratio"] = calmar

    end_of_session = end_of_bar


class TradeStatisticsMetric:
    """Metric that reports win rate and profit factor from transactions.

    Tracks trade-level statistics by analyzing closed transactions.
    """

    def start_of_simulation(
        self, ledger, emission_rate, trading_calendar, sessions, benchmark_source
    ):
        """Initialize tracking."""
        pass

    def end_of_bar(self, packet, ledger, dt, session_ix, data_portal):
        # Get all transactions up to this point
        all_transactions = ledger.transactions()

        if len(all_transactions) > 0:
            # Convert to DataFrame if it's a list of transaction objects
            if isinstance(all_transactions, list):
                transactions_df = pd.DataFrame(
                    [
                        {
                            "pnl": (
                                t.amount * (t.price - t.cost_basis)
                                if hasattr(t, "cost_basis")
                                else 0
                            )
                        }
                        for t in all_transactions
                    ]
                )
            else:
                transactions_df = all_transactions

            # Calculate win rate
            wr = win_rate(transactions_df)
            if not np.isfinite(wr):
                wr = None
            packet["cumulative_risk_metrics"]["win_rate"] = wr

            # Calculate profit factor
            pf = profit_factor(transactions_df)
            if not np.isfinite(pf):
                pf = None
            packet["cumulative_risk_metrics"]["profit_factor"] = pf
        else:
            packet["cumulative_risk_metrics"]["win_rate"] = None
            packet["cumulative_risk_metrics"]["profit_factor"] = None

    end_of_session = end_of_bar
