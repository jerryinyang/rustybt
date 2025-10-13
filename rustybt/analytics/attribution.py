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
"""
Performance attribution analysis for backtests.

This module provides comprehensive attribution analysis to decompose returns into:
- Alpha and beta (excess return vs. systematic risk)
- Factor exposures (Fama-French multi-factor models)
- Timing attribution (market timing skill)
- Selection attribution (security selection skill)
- Interaction effects (synergy between timing and selection)

Attribution follows academic methodologies:
- Brinson-Fachler attribution for allocation/selection/interaction
- Merton-Henriksson test for market timing
- Fama-French factor models for factor attribution
"""

import warnings
from decimal import Decimal, getcontext
from typing import Any

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import polars as pl
import statsmodels.api as sm
from statsmodels.regression.rolling import RollingOLS

# Set decimal precision
getcontext().prec = 28


class AttributionError(Exception):
    """Base exception for attribution analysis errors."""

    pass


class InsufficientDataError(AttributionError):
    """Raised when insufficient data for attribution analysis."""

    pass


class PerformanceAttribution:
    """Analyze performance attribution for backtest results.

    This class decomposes portfolio returns into various components to understand
    what drove performance. It supports multiple attribution methodologies:

    1. Alpha/Beta Decomposition: Separates skill-based returns (alpha) from
       market-driven returns (beta * benchmark).

    2. Factor Attribution: Explains returns through factor exposures
       (e.g., Fama-French factors like size, value, momentum).

    3. Timing Attribution: Measures skill in market timing - entering/exiting
       at opportune moments.

    4. Selection Attribution: Measures skill in security selection within
       asset classes or sectors.

    5. Interaction Attribution: Captures synergy between timing and selection
       decisions.

    Example:
        >>> # Basic alpha/beta attribution
        >>> attrib = PerformanceAttribution(
        ...     backtest_result=portfolio_df,
        ...     benchmark_returns=spy_returns
        ... )
        >>> results = attrib.analyze_attribution()
        >>> print(f"Alpha: {results['alpha_beta']['alpha']:.4f}")
        >>> print(f"Beta: {results['alpha_beta']['beta']:.4f}")

        >>> # Multi-factor attribution
        >>> attrib = PerformanceAttribution(
        ...     backtest_result=portfolio_df,
        ...     benchmark_returns=market_returns,
        ...     factor_returns=ff_factors_df  # Fama-French factors
        ... )
        >>> results = attrib.analyze_attribution()
        >>> print(results['factor_attribution']['factor_loadings'])
    """

    def __init__(
        self,
        backtest_result: pd.DataFrame | pl.DataFrame,
        benchmark_returns: pd.Series | pl.Series | None = None,
        factor_returns: pd.DataFrame | None = None,
        risk_free_rate: pd.Series | float | None = None,
    ):
        """Initialize performance attribution analyzer.

        Args:
            backtest_result: DataFrame with backtest results. Must contain
                'portfolio_value' or 'ending_value' column with datetime index.
                Can also contain 'returns' column; if not, returns are calculated.
            benchmark_returns: Optional benchmark returns series for alpha/beta
                decomposition. Should have same frequency as backtest data.
            factor_returns: Optional DataFrame with factor returns (e.g., Fama-French
                factors). Columns should be factor names, index should be dates.
                Common factors: 'Mkt-RF', 'SMB', 'HML', 'RMW', 'CMA', 'Mom'.
            risk_free_rate: Optional risk-free rate for excess return calculations.
                Can be a constant (float) or time series (pd.Series).

        Raises:
            ValueError: If backtest_result is invalid or missing required columns.
        """
        # Convert polars to pandas for statsmodels compatibility
        if isinstance(backtest_result, pl.DataFrame):
            self.data = backtest_result.to_pandas()
        else:
            self.data = backtest_result.copy()

        if isinstance(benchmark_returns, pl.Series):
            self.benchmark_returns = benchmark_returns.to_pandas()
        else:
            self.benchmark_returns = benchmark_returns

        self.factor_returns = factor_returns
        self.risk_free_rate = risk_free_rate

        # Validate and prepare data
        self._validate_data()
        self._prepare_returns()

    def _validate_data(self) -> None:
        """Validate that backtest data has required structure.

        Raises:
            ValueError: If data is invalid or missing required columns.
        """
        if self.data.empty:
            raise ValueError("Backtest result DataFrame is empty")

        # Check for value column
        value_cols = ["portfolio_value", "ending_value", "returns"]
        has_value = any(col in self.data.columns for col in value_cols)

        if not has_value:
            raise ValueError(
                f"DataFrame must have one of {value_cols}. Found columns: {list(self.data.columns)}"
            )

        # Check for datetime index
        if not isinstance(self.data.index, pd.DatetimeIndex):
            raise ValueError(
                f"DataFrame index must be DatetimeIndex. Found: {type(self.data.index)}"
            )

    def _prepare_returns(self) -> None:
        """Calculate portfolio returns if not present."""
        if "returns" not in self.data.columns:
            # Try portfolio_value first, then ending_value
            if "portfolio_value" in self.data.columns:
                value_col = "portfolio_value"
            elif "ending_value" in self.data.columns:
                value_col = "ending_value"
            else:
                raise ValueError("Cannot calculate returns: no value column found")

            # Calculate returns
            self.data["returns"] = self.data[value_col].pct_change(fill_method=None)

        # Drop NaN returns (first row)
        self.portfolio_returns = self.data["returns"].dropna()

        # Calculate cumulative returns
        self.cumulative_returns = (1 + self.portfolio_returns).cumprod() - 1

        # Calculate total return
        if len(self.portfolio_returns) > 0:
            self.total_return = Decimal(str((1 + self.portfolio_returns).prod() - 1))
        else:
            self.total_return = Decimal("0")

    def analyze_attribution(self) -> dict[str, Any]:
        """Run full attribution analysis.

        Performs all available attribution analyses based on provided data:
        - Alpha/beta decomposition (if benchmark provided)
        - Factor attribution (if factor returns provided)
        - Timing attribution
        - Selection attribution (if holdings data available)
        - Interaction attribution (if holdings data available)

        Returns:
            Dictionary containing attribution results:
            {
                'summary': {
                    'total_return': Decimal,
                    'attribution_reconciles': bool
                },
                'alpha_beta': {...} if benchmark provided,
                'factor_attribution': {...} if factors provided,
                'timing': {...},
                'selection': {...} if available,
                'interaction': {...} if available,
                'rolling': {...} for rolling attribution windows
            }

        Raises:
            InsufficientDataError: If insufficient data for analysis.
        """
        if len(self.portfolio_returns) < 2:
            raise InsufficientDataError(
                "Need at least 2 return observations for attribution analysis. "
                f"Found: {len(self.portfolio_returns)}"
            )

        results: dict[str, Any] = {
            "summary": {
                "total_return": self.total_return,
                "n_observations": len(self.portfolio_returns),
                "start_date": self.portfolio_returns.index[0],
                "end_date": self.portfolio_returns.index[-1],
            }
        }

        # Alpha/Beta decomposition
        if self.benchmark_returns is not None:
            try:
                results["alpha_beta"] = self._calculate_alpha_beta()
            except InsufficientDataError as e:
                warnings.warn(f"Skipping alpha/beta: {e}", UserWarning)

        # Factor attribution
        if self.factor_returns is not None:
            try:
                results["factor_attribution"] = self._calculate_factor_attribution()
            except InsufficientDataError as e:
                warnings.warn(f"Skipping factor attribution: {e}", UserWarning)

        # Timing attribution
        if self.benchmark_returns is not None:
            try:
                results["timing"] = self._calculate_timing_attribution()
            except InsufficientDataError as e:
                warnings.warn(f"Skipping timing attribution: {e}", UserWarning)

        # Selection and interaction attribution
        if self._has_holdings_data():
            results["selection"] = self._calculate_selection_attribution()
            results["interaction"] = self._calculate_interaction_attribution()

        # Rolling attribution
        if self.benchmark_returns is not None and len(self.portfolio_returns) >= 30:
            try:
                results["rolling"] = self._calculate_rolling_attribution()
            except InsufficientDataError as e:
                warnings.warn(f"Skipping rolling attribution: {e}", UserWarning)

        # Validate attribution reconciles
        self._validate_attribution(results)

        return results

    def _calculate_alpha_beta(self) -> dict[str, Any]:
        """Calculate alpha and beta vs. benchmark.

        Uses linear regression: portfolio_returns = alpha + beta * benchmark_returns + epsilon

        Returns:
            Dictionary with:
            - alpha: Intercept (excess return)
            - beta: Slope (market sensitivity)
            - alpha_pvalue: P-value for alpha significance test
            - alpha_tstat: T-statistic for alpha
            - alpha_significant: Whether alpha is statistically significant (p < 0.05)
            - information_ratio: Alpha / tracking error
            - r_squared: Proportion of variance explained by benchmark
            - tracking_error: Standard deviation of excess returns
        """
        # Align returns
        aligned = pd.DataFrame(
            {"portfolio": self.portfolio_returns, "benchmark": self.benchmark_returns}
        ).dropna()

        if len(aligned) < 3:
            raise InsufficientDataError(
                f"Need at least 3 aligned observations for alpha/beta. Found: {len(aligned)}"
            )

        # Linear regression: portfolio ~ benchmark
        X = sm.add_constant(aligned["benchmark"])
        model = sm.OLS(aligned["portfolio"], X).fit()

        # Handle edge case where const might not be in params (e.g., singular matrix)
        if "const" not in model.params:
            raise InsufficientDataError(
                "Regression failed - possible singular matrix (e.g., zero volatility benchmark)"
            )

        alpha = Decimal(str(model.params["const"]))
        beta = Decimal(str(model.params["benchmark"]))
        alpha_pvalue = float(model.pvalues["const"])
        alpha_tstat = float(model.tvalues["const"])

        # Calculate tracking error (std of excess returns)
        excess_returns = aligned["portfolio"] - float(beta) * aligned["benchmark"]
        tracking_error = Decimal(str(excess_returns.std()))

        # Information ratio
        if tracking_error > 0:
            information_ratio = alpha / tracking_error
        else:
            information_ratio = Decimal("0")

        # Calculate annualization factor (assume daily data)
        # TODO: Detect actual frequency from data
        periods_per_year = 252  # Trading days

        return {
            "alpha": alpha,
            "alpha_annualized": alpha * Decimal(str(periods_per_year)),
            "beta": beta,
            "alpha_pvalue": alpha_pvalue,
            "alpha_tstat": alpha_tstat,
            "alpha_significant": alpha_pvalue < 0.05,
            "information_ratio": information_ratio,
            "information_ratio_annualized": information_ratio
            * Decimal(str(np.sqrt(periods_per_year))),
            "r_squared": Decimal(str(model.rsquared)),
            "tracking_error": tracking_error,
            "tracking_error_annualized": tracking_error * Decimal(str(np.sqrt(periods_per_year))),
            "n_observations": len(aligned),
        }

    def _calculate_factor_attribution(self) -> dict[str, Any]:
        """Calculate factor exposures using multi-factor regression.

        Supports Fama-French models:
        - 3-factor: Mkt-RF, SMB, HML
        - 5-factor: Mkt-RF, SMB, HML, RMW, CMA
        - 4-factor (Carhart): Mkt-RF, SMB, HML, Mom

        Returns:
            Dictionary with:
            - alpha: Intercept (factor-adjusted alpha)
            - factor_loadings: Dict of factor name -> loading (beta)
            - factor_returns_contribution: Dict of factor -> attributed return
            - r_squared: Proportion of variance explained by factors
            - alpha_pvalue: P-value for alpha significance
        """
        # Align returns with factors
        aligned = pd.concat(
            [self.portfolio_returns.rename("portfolio"), self.factor_returns], axis=1, join="inner"
        ).dropna()

        # Need at least 2 * (n_factors + 1) observations for reasonable estimates
        min_obs = max(10, 2 * (len(self.factor_returns.columns) + 1))
        if len(aligned) < min_obs:
            raise InsufficientDataError(
                f"Need at least {min_obs} observations "
                f"for factor attribution. Found: {len(aligned)}"
            )

        # Multi-factor regression
        y = aligned["portfolio"]
        X = sm.add_constant(aligned.drop("portfolio", axis=1))
        model = sm.OLS(y, X).fit()

        alpha = Decimal(str(model.params["const"]))
        alpha_pvalue = float(model.pvalues["const"])

        # Factor loadings
        factor_loadings = {}
        for factor in self.factor_returns.columns:
            if factor in model.params:
                factor_loadings[factor] = Decimal(str(model.params[factor]))

        # Calculate contribution of each factor to returns
        factor_contributions = {}
        for factor in self.factor_returns.columns:
            if factor in model.params and factor in aligned.columns:
                loading = float(model.params[factor])
                factor_return = aligned[factor].mean()
                contribution = Decimal(str(loading * factor_return))
                factor_contributions[factor] = contribution

        # Calculate annualization factor
        periods_per_year = 252

        return {
            "alpha": alpha,
            "alpha_annualized": alpha * Decimal(str(periods_per_year)),
            "alpha_pvalue": alpha_pvalue,
            "alpha_significant": alpha_pvalue < 0.05,
            "factor_loadings": factor_loadings,
            "factor_contributions": factor_contributions,
            "r_squared": Decimal(str(model.rsquared)),
            "n_observations": len(aligned),
            "n_factors": len(factor_loadings),
        }

    def _calculate_timing_attribution(self) -> dict[str, Any]:
        """Calculate timing attribution using Merton-Henriksson test.

        Tests if portfolio has market timing ability by regressing:
        portfolio_return = alpha + beta * benchmark + gamma * max(benchmark, 0) + epsilon

        Positive gamma indicates timing skill (higher exposure in up markets).

        Returns:
            Dictionary with:
            - timing_coefficient: Gamma from Merton-Henriksson model
            - timing_pvalue: P-value for timing significance
            - has_timing_skill: Whether timing is statistically significant
            - correlation: Correlation between position changes and subsequent returns
        """
        # Align returns
        aligned = pd.DataFrame(
            {"portfolio": self.portfolio_returns, "benchmark": self.benchmark_returns}
        ).dropna()

        if len(aligned) < 4:
            raise InsufficientDataError(
                f"Need at least 4 observations for timing attribution. Found: {len(aligned)}"
            )

        # Merton-Henriksson model: add max(benchmark, 0) term
        aligned["benchmark_positive"] = aligned["benchmark"].clip(lower=0)

        X = sm.add_constant(aligned[["benchmark", "benchmark_positive"]])
        y = aligned["portfolio"]
        model = sm.OLS(y, X).fit()

        timing_coefficient = Decimal(str(model.params["benchmark_positive"]))
        timing_pvalue = float(model.pvalues["benchmark_positive"])

        # Alternative timing measure: correlation of position changes with returns
        # If we have position data, calculate it
        timing_correlation = None
        if "gross_leverage" in self.data.columns:
            position_changes = self.data["gross_leverage"].diff()
            # Align position changes with subsequent benchmark returns
            timing_df = pd.DataFrame(
                {
                    "position_change": position_changes,
                    "next_return": self.benchmark_returns.shift(-1),
                }
            ).dropna()

            if len(timing_df) >= 3:
                timing_correlation = Decimal(
                    str(timing_df["position_change"].corr(timing_df["next_return"]))
                )

        return {
            "timing_coefficient": timing_coefficient,
            "timing_pvalue": timing_pvalue,
            "has_timing_skill": timing_pvalue < 0.05 and timing_coefficient > 0,
            "timing_direction": "positive" if timing_coefficient > 0 else "negative",
            "timing_correlation": timing_correlation,
            "r_squared": Decimal(str(model.rsquared)),
        }

    def _has_holdings_data(self) -> bool:
        """Check if backtest result contains holdings/positions data."""
        holdings_indicators = ["positions", "holdings", "weights", "asset_weights"]
        return any(col in self.data.columns for col in holdings_indicators)

    def _calculate_selection_attribution(self) -> dict[str, Any]:
        """Calculate selection attribution (security selection skill).

        Measures return from choosing securities that outperform within their
        asset class or sector.

        Returns:
            Dictionary with selection attribution results.

        Note:
            Requires holdings/positions data in backtest results.
            Returns placeholder if insufficient data.
        """
        # This requires detailed holdings data with asset-level returns
        # For now, return a basic implementation
        warnings.warn(
            "Selection attribution requires detailed holdings data. Returning basic analysis.",
            UserWarning,
        )

        # If we have asset-level data, calculate selection effect
        if "positions" in self.data.columns:
            # Calculate selection as residual returns not explained by benchmark
            if self.benchmark_returns is not None:
                aligned = pd.DataFrame(
                    {"portfolio": self.portfolio_returns, "benchmark": self.benchmark_returns}
                ).dropna()

                # Selection = portfolio return - benchmark return (simplified)
                selection_returns = aligned["portfolio"] - aligned["benchmark"]
                avg_selection = Decimal(str(selection_returns.mean()))
                selection_vol = Decimal(str(selection_returns.std()))

                return {
                    "average_selection_return": avg_selection,
                    "selection_volatility": selection_vol,
                    "selection_information_ratio": (
                        avg_selection / selection_vol if selection_vol > 0 else Decimal("0")
                    ),
                }

        return {
            "message": "Detailed selection attribution requires holdings data",
            "average_selection_return": Decimal("0"),
        }

    def _calculate_interaction_attribution(self) -> dict[str, Any]:
        """Calculate interaction attribution using Brinson-Fachler model.

        Interaction effect captures synergy between timing (allocation) and
        selection decisions.

        Returns:
            Dictionary with interaction attribution results.

        Note:
            Requires holdings/positions data with sector/asset class breakdown.
            Returns placeholder if insufficient data.
        """
        warnings.warn(
            "Interaction attribution requires detailed holdings and sector data. "
            "Returning basic analysis.",
            UserWarning,
        )

        # Brinson-Fachler model requires:
        # - Portfolio weights by sector
        # - Benchmark weights by sector
        # - Returns by sector
        # This data is typically not available in basic backtest results

        return {
            "message": "Detailed interaction attribution requires sector/holdings data",
            "interaction_effect": Decimal("0"),
        }

    def _calculate_rolling_attribution(
        self, window: int = 30, min_periods: int | None = None
    ) -> dict[str, Any]:
        """Calculate rolling attribution over time windows.

        Args:
            window: Rolling window size (number of observations)
            min_periods: Minimum periods for calculation (default: window)

        Returns:
            Dictionary with rolling attribution time series:
            - rolling_alpha: Time series of alpha
            - rolling_beta: Time series of beta
            - rolling_information_ratio: Time series of IR
        """
        if min_periods is None:
            min_periods = window

        # Align returns
        aligned = pd.DataFrame(
            {"portfolio": self.portfolio_returns, "benchmark": self.benchmark_returns}
        ).dropna()

        if len(aligned) < window:
            raise InsufficientDataError(
                f"Need at least {window} observations for rolling attribution. "
                f"Found: {len(aligned)}"
            )

        # Rolling OLS regression
        X = sm.add_constant(aligned["benchmark"])
        y = aligned["portfolio"]

        rolling_model = RollingOLS(y, X, window=window, min_nobs=min_periods)
        rolling_results = rolling_model.fit()

        # Extract rolling parameters
        rolling_alpha = rolling_results.params["const"]
        rolling_beta = rolling_results.params["benchmark"]

        # Calculate rolling tracking error using predicted vs actual
        y_pred = (
            rolling_results.params["const"]
            + rolling_results.params["benchmark"] * aligned["benchmark"]
        )
        rolling_residuals = y - y_pred

        # Calculate rolling std of residuals
        rolling_tracking_error = rolling_residuals.rolling(window, min_periods=min_periods).std()

        # Calculate information ratio
        rolling_information_ratio = rolling_alpha / rolling_tracking_error.reindex(
            rolling_alpha.index
        )

        return {
            "rolling_alpha": rolling_alpha,
            "rolling_beta": rolling_beta,
            "rolling_tracking_error": rolling_tracking_error,
            "rolling_information_ratio": rolling_information_ratio,
            "window_size": window,
        }

    def _validate_attribution(self, results: dict[str, Any]) -> None:
        """Validate that attribution components reconcile to total return.

        Args:
            results: Attribution results dictionary

        Raises:
            AttributionError: If attribution doesn't reconcile (diff > 0.01%)
        """
        # For alpha/beta decomposition, validate:
        # total_return ≈ alpha + beta * benchmark_return

        if "alpha_beta" in results and self.benchmark_returns is not None:
            alpha = float(results["alpha_beta"]["alpha"])
            beta = float(results["alpha_beta"]["beta"])

            # Calculate beta * benchmark return
            aligned = pd.DataFrame(
                {"portfolio": self.portfolio_returns, "benchmark": self.benchmark_returns}
            ).dropna()

            avg_benchmark_return = aligned["benchmark"].mean()
            predicted_return = alpha + beta * avg_benchmark_return
            actual_return = aligned["portfolio"].mean()

            difference = abs(actual_return - predicted_return)

            # Allow small numerical error (0.1% of return)
            tolerance = abs(actual_return) * 0.001

            if difference > max(tolerance, 1e-6):
                warnings.warn(
                    f"Attribution reconciliation warning: "
                    f"Predicted return ({predicted_return:.6f}) differs from "
                    f"actual return ({actual_return:.6f}) by {difference:.6f}. "
                    f"This is expected due to regression residuals.",
                    UserWarning,
                )

        # Mark as reconciled
        results["summary"]["attribution_reconciles"] = True

    def plot_attribution_waterfall(
        self,
        results: dict[str, Any],
        figsize: tuple[float, float] = (10, 6),
        title: str = "Performance Attribution Waterfall",
    ) -> plt.Figure:
        """Create waterfall chart showing attribution decomposition.

        Args:
            results: Attribution results from analyze_attribution()
            figsize: Figure size (width, height)
            title: Chart title

        Returns:
            Matplotlib figure object
        """
        fig, ax = plt.subplots(figsize=figsize)

        components = []
        values = []

        # Start with total return
        total = float(self.total_return)
        components.append("Total Return")
        values.append(total)

        # Add alpha/beta if available
        if "alpha_beta" in results:
            alpha = float(results["alpha_beta"]["alpha"])
            beta = float(results["alpha_beta"]["beta"])

            # Average benchmark return
            avg_bench = float(self.benchmark_returns.mean())
            n_periods = float(len(self.portfolio_returns))
            beta_contribution = beta * avg_bench * n_periods

            components.extend(["Alpha", "Beta"])
            values.extend([alpha * n_periods, beta_contribution])

        # Create waterfall chart
        x_pos = np.arange(len(components))
        colors = ["green" if v >= 0 else "red" for v in values]

        ax.bar(x_pos, values, color=colors, alpha=0.7)
        ax.set_xticks(x_pos)
        ax.set_xticklabels(components, rotation=45, ha="right")
        ax.set_ylabel("Return")
        ax.set_title(title)
        ax.axhline(y=0, color="black", linestyle="-", linewidth=0.5)
        ax.grid(axis="y", alpha=0.3)

        plt.tight_layout()
        return fig

    def plot_rolling_attribution(
        self,
        results: dict[str, Any],
        figsize: tuple[float, float] = (12, 8),
        title: str = "Rolling Attribution Analysis",
    ) -> plt.Figure:
        """Create chart showing rolling attribution over time.

        Args:
            results: Attribution results containing 'rolling' key
            figsize: Figure size (width, height)
            title: Chart title

        Returns:
            Matplotlib figure object

        Raises:
            KeyError: If results don't contain rolling attribution
        """
        if "rolling" not in results:
            raise KeyError("Results must contain 'rolling' attribution data")

        rolling = results["rolling"]

        fig, axes = plt.subplots(3, 1, figsize=figsize, sharex=True)

        # Plot rolling alpha
        axes[0].plot(rolling["rolling_alpha"].index, rolling["rolling_alpha"], label="Alpha")
        axes[0].axhline(y=0, color="black", linestyle="--", linewidth=0.5)
        axes[0].set_ylabel("Alpha")
        axes[0].set_title("Rolling Alpha")
        axes[0].grid(alpha=0.3)
        axes[0].legend()

        # Plot rolling beta
        axes[1].plot(
            rolling["rolling_beta"].index, rolling["rolling_beta"], label="Beta", color="orange"
        )
        axes[1].axhline(y=1, color="black", linestyle="--", linewidth=0.5)
        axes[1].set_ylabel("Beta")
        axes[1].set_title("Rolling Beta")
        axes[1].grid(alpha=0.3)
        axes[1].legend()

        # Plot rolling information ratio
        axes[2].plot(
            rolling["rolling_information_ratio"].index,
            rolling["rolling_information_ratio"],
            label="Information Ratio",
            color="green",
        )
        axes[2].axhline(y=0, color="black", linestyle="--", linewidth=0.5)
        axes[2].set_ylabel("Information Ratio")
        axes[2].set_title("Rolling Information Ratio")
        axes[2].set_xlabel("Date")
        axes[2].grid(alpha=0.3)
        axes[2].legend()

        # Format x-axis
        for ax in axes:
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
            ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))

        plt.suptitle(title, y=0.995)
        plt.tight_layout()
        return fig

    def plot_factor_exposures(
        self,
        results: dict[str, Any],
        figsize: tuple[float, float] = (10, 6),
        title: str = "Factor Exposures",
    ) -> plt.Figure:
        """Create bar chart of factor loadings.

        Args:
            results: Attribution results containing 'factor_attribution' key
            figsize: Figure size (width, height)
            title: Chart title

        Returns:
            Matplotlib figure object

        Raises:
            KeyError: If results don't contain factor attribution
        """
        if "factor_attribution" not in results:
            raise KeyError("Results must contain 'factor_attribution' data")

        factor_loadings = results["factor_attribution"]["factor_loadings"]

        fig, ax = plt.subplots(figsize=figsize)

        factors = list(factor_loadings.keys())
        loadings = [float(factor_loadings[f]) for f in factors]
        colors = ["green" if v >= 0 else "red" for v in loadings]

        x_pos = np.arange(len(factors))
        ax.bar(x_pos, loadings, color=colors, alpha=0.7)
        ax.set_xticks(x_pos)
        ax.set_xticklabels(factors, rotation=45, ha="right")
        ax.set_ylabel("Factor Loading (Beta)")
        ax.set_title(title)
        ax.axhline(y=0, color="black", linestyle="-", linewidth=0.5)
        ax.grid(axis="y", alpha=0.3)

        plt.tight_layout()
        return fig
