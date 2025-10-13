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
Risk analytics for backtests.

This module provides comprehensive risk analysis to understand strategy risk profile:
- Value at Risk (VaR): Maximum expected loss at given confidence levels
- Conditional VaR (CVaR / Expected Shortfall): Average loss beyond VaR
- Stress testing: Simulate extreme historical scenarios
- Scenario analysis: User-defined what-if scenarios
- Correlation analysis: Portfolio correlation matrix
- Beta analysis: Market sensitivity
- Tail risk metrics: Skewness, kurtosis, max loss
- Risk decomposition: Contribution to portfolio risk

Risk methodologies follow industry standards (Basel III, academic research).
"""

from decimal import Decimal, getcontext
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import polars as pl
import seaborn as sns
from scipy import stats

# Set decimal precision
getcontext().prec = 28


class RiskError(Exception):
    """Base exception for risk analysis errors."""

    pass


class InsufficientDataError(RiskError):
    """Raised when insufficient data for risk analysis."""

    pass


class RiskAnalytics:
    """Comprehensive risk analytics for backtest results.

    This class provides a wide range of risk metrics to understand portfolio
    risk profile and tail risk exposure:

    1. Value at Risk (VaR): Maximum expected loss at confidence level
       - Parametric VaR (normal distribution assumption)
       - Historical VaR (empirical quantiles)
       - Monte Carlo VaR (simulation-based)

    2. Conditional VaR (CVaR): Average loss beyond VaR threshold
       - More conservative than VaR
       - Captures tail risk better

    3. Stress Testing: Apply historical crisis scenarios
       - 2008 Financial Crisis
       - COVID-19 Crash
       - Flash Crash

    4. Scenario Analysis: User-defined what-if scenarios
       - Flexible scenario specification
       - Portfolio impact calculation

    5. Correlation Analysis: Portfolio correlation matrix
       - Asset correlation heatmap
       - Concentration risk identification

    6. Beta Analysis: Market sensitivity
       - Portfolio beta vs benchmark
       - Position-level betas

    7. Tail Risk Metrics: Distribution characteristics
       - Skewness (asymmetry)
       - Kurtosis (fat tails)
       - Max drawdown
       - Downside deviation

    8. Risk Decomposition: Contribution analysis
       - Marginal VaR per position
       - Component VaR

    Example:
        >>> # Basic VaR analysis
        >>> risk = RiskAnalytics(
        ...     backtest_result=portfolio_df,
        ...     confidence_levels=[0.95, 0.99]
        ... )
        >>> var_results = risk.calculate_var(method='historical')
        >>> print(f"95% VaR: {var_results['var_95']}")

        >>> # Comprehensive risk report
        >>> risk_report = risk.analyze_risk()
        >>> print(risk_report['var'])
        >>> print(risk_report['cvar'])
        >>> print(risk_report['stress_tests'])

        >>> # With benchmark for beta analysis
        >>> risk = RiskAnalytics(
        ...     backtest_result=portfolio_df,
        ...     benchmark_returns=spy_returns
        ... )
        >>> beta = risk.calculate_beta()
    """

    def __init__(
        self,
        backtest_result: pd.DataFrame | pl.DataFrame,
        confidence_levels: list[float] | None = None,
        benchmark_returns: pd.Series | None = None,
        positions: pd.DataFrame | None = None,
    ):
        """Initialize risk analytics.

        Args:
            backtest_result: Backtest results with 'returns' or 'portfolio_value'
            confidence_levels: Confidence levels for VaR/CVaR (e.g., [0.95, 0.99])
            benchmark_returns: Optional benchmark returns for beta calculation
            positions: Optional positions data for risk decomposition

        Raises:
            InsufficientDataError: If insufficient data for risk analysis
        """
        # Set default confidence levels
        if confidence_levels is None:
            confidence_levels = [0.95, 0.99]

        # Convert polars to pandas if needed
        if isinstance(backtest_result, pl.DataFrame):
            self.data = backtest_result.to_pandas()
        else:
            self.data = backtest_result.copy()

        # Extract returns - calculate if not present
        if "returns" in self.data.columns:
            self.returns = self.data["returns"]
        elif "portfolio_value" in self.data.columns:
            self.returns = self.data["portfolio_value"].pct_change().dropna()
        else:
            raise InsufficientDataError(
                "Backtest result must contain 'returns' or 'portfolio_value' column"
            )

        # Validate sufficient data
        if len(self.returns) < 30:
            raise InsufficientDataError(
                f"Insufficient data for risk analysis: {len(self.returns)} observations "
                f"(minimum 30 required)"
            )

        self.confidence_levels = confidence_levels
        self.benchmark_returns = benchmark_returns
        self.positions = positions

        # Convert returns to numpy for calculations
        self.returns_array = self.returns.to_numpy()

    def analyze_risk(self, var_method: str = "historical") -> dict[str, Any]:
        """Run comprehensive risk analysis.

        Args:
            var_method: VaR calculation method ('parametric', 'historical', 'montecarlo')

        Returns:
            Dictionary with risk metrics:
            - 'var': VaR at all confidence levels
            - 'cvar': CVaR at all confidence levels
            - 'stress_tests': Stress test results
            - 'tail_risk': Tail risk metrics
            - 'beta': Beta analysis (if benchmark provided)
            - 'correlation': Correlation matrix (if positions provided)
        """
        results = {
            "var": self.calculate_var(method=var_method),
            "cvar": self.calculate_cvar(method=var_method),
            "stress_tests": self.run_stress_tests(),
            "tail_risk": self.calculate_tail_risk(),
        }

        # Optional analyses
        if self.benchmark_returns is not None:
            results["beta"] = self.calculate_beta()

        if self.positions is not None:
            results["correlation"] = self.calculate_correlation()
            results["risk_decomposition"] = self.calculate_risk_decomposition()

        return results

    def calculate_var(self, method: str = "historical") -> dict[str, Decimal]:
        """Calculate Value at Risk at multiple confidence levels.

        VaR is the maximum expected loss at a given confidence level over
        a time horizon (typically 1 day).

        Args:
            method: Calculation method
                - 'parametric': Assumes normal distribution
                - 'historical': Uses empirical quantiles
                - 'montecarlo': Simulation-based

        Returns:
            Dictionary with VaR for each confidence level
            Keys: 'var_95', 'var_99', etc.

        Raises:
            ValueError: If unknown method specified
        """
        results = {}

        for confidence in self.confidence_levels:
            if method == "parametric":
                var = self._var_parametric(confidence)
            elif method == "historical":
                var = self._var_historical(confidence)
            elif method == "montecarlo":
                var = self._var_montecarlo(confidence)
            else:
                raise ValueError(
                    f"Unknown VaR method: {method}. Use 'parametric', 'historical', or 'montecarlo'"
                )

            key = f"var_{int(confidence * 100)}"
            results[key] = var

        return results

    def _var_parametric(self, confidence: float) -> Decimal:
        """Calculate parametric VaR assuming normal distribution.

        Formula: VaR = mean - std * z_score
        where:
            mean = mean daily return
            std = standard deviation of daily returns
            z_score = z-score for confidence level

        Args:
            confidence: Confidence level (e.g., 0.95)

        Returns:
            VaR as Decimal (negative value indicates loss)
        """
        mean = self.returns_array.mean()
        std = self.returns_array.std()
        z_score = stats.norm.ppf(1 - confidence)

        var = mean + z_score * std  # z_score is negative for losses
        return Decimal(str(var))

    def _var_historical(self, confidence: float) -> Decimal:
        """Calculate historical VaR using empirical quantiles.

        This method makes no distributional assumptions and uses actual
        historical returns to estimate VaR.

        Args:
            confidence: Confidence level (e.g., 0.95)

        Returns:
            VaR as Decimal (negative value indicates loss)
        """
        quantile = 1 - confidence
        var = np.quantile(self.returns_array, quantile)
        return Decimal(str(var))

    def _var_montecarlo(self, confidence: float, n_simulations: int = 10000) -> Decimal:
        """Calculate Monte Carlo VaR using simulations.

        Simulates portfolio returns assuming normal distribution with
        estimated parameters, then calculates empirical quantile.

        Args:
            confidence: Confidence level (e.g., 0.95)
            n_simulations: Number of simulations (default: 10,000)

        Returns:
            VaR as Decimal (negative value indicates loss)
        """
        mean = self.returns_array.mean()
        std = self.returns_array.std()

        # Simulate returns
        simulated_returns = np.random.normal(mean, std, n_simulations)

        # Calculate VaR from simulations
        quantile = 1 - confidence
        var = np.quantile(simulated_returns, quantile)
        return Decimal(str(var))

    def calculate_cvar(self, method: str = "historical") -> dict[str, Decimal]:
        """Calculate Conditional VaR (Expected Shortfall).

        CVaR is the average loss in the worst (1 - confidence_level) % of cases.
        It provides a more conservative risk measure than VaR.

        Property: CVaR >= VaR (in absolute terms)

        Args:
            method: VaR calculation method ('parametric', 'historical', 'montecarlo')

        Returns:
            Dictionary with CVaR for each confidence level
            Keys: 'cvar_95', 'cvar_99', etc.
        """
        var_results = self.calculate_var(method=method)
        cvar_results = {}

        for confidence in self.confidence_levels:
            var_key = f"var_{int(confidence * 100)}"
            var = float(var_results[var_key])

            # CVaR = average loss beyond VaR
            tail_losses = self.returns_array[self.returns_array <= var]

            # Use VaR itself if no losses beyond VaR, otherwise use mean of tail losses
            cvar = Decimal(str(var)) if len(tail_losses) == 0 else Decimal(str(tail_losses.mean()))

            cvar_key = f"cvar_{int(confidence * 100)}"
            cvar_results[cvar_key] = cvar

        return cvar_results

    def run_stress_tests(self) -> dict[str, Decimal]:
        """Run predefined stress test scenarios.

        Applies historical crisis shocks to portfolio to estimate
        potential losses in extreme scenarios.

        Predefined scenarios:
        - 2008 Financial Crisis: SPY -50%, TLT +20%, GLD +5%
        - COVID-19 Crash (March 2020): SPY -35%, TLT +5%
        - Flash Crash (May 2010): SPY -10% in 1 day

        Returns:
            Dictionary mapping scenario name to estimated loss

        Notes:
            If positions data is available with asset-specific returns,
            applies asset-specific shocks. Otherwise, applies uniform shock.
        """
        # Define historical crisis scenarios with asset-specific shocks
        scenarios = {
            "2008_financial_crisis": {
                "description": "2008 Financial Crisis",
                "shocks": {"SPY": -0.50, "TLT": 0.20, "GLD": 0.05},
                "uniform_shock": -0.50,  # Fallback if no positions
            },
            "covid_crash": {
                "description": "COVID-19 Crash (March 2020)",
                "shocks": {"SPY": -0.35, "TLT": 0.05},
                "uniform_shock": -0.35,
            },
            "flash_crash": {
                "description": "Flash Crash (May 2010)",
                "shocks": {"SPY": -0.10},
                "uniform_shock": -0.10,
            },
        }

        results = {}

        for scenario_name, scenario_data in scenarios.items():
            # Try to use asset-specific shocks if positions available
            if self.positions is not None:
                try:
                    loss = self.apply_scenario(scenario_data["shocks"])
                except (ValueError, KeyError):
                    # Fallback to uniform shock if positions don't have required columns
                    loss = self._apply_simple_scenario(scenario_data["uniform_shock"])
            else:
                # Use uniform shock when no positions data
                loss = self._apply_simple_scenario(scenario_data["uniform_shock"])

            results[scenario_name] = loss

        return results

    def _apply_simple_scenario(self, shock: float) -> Decimal:
        """Apply simple uniform shock to portfolio.

        This is a simplified implementation that applies uniform shock.
        In practice, you would apply position-specific shocks if positions
        data is available.

        Args:
            shock: Percentage shock (e.g., -0.35 for -35%)

        Returns:
            Estimated loss as Decimal
        """
        # Use most recent portfolio value if available
        if "portfolio_value" in self.data.columns:
            portfolio_value = self.data["portfolio_value"].iloc[-1]
        else:
            # Estimate from returns
            portfolio_value = 100000  # Default assumption

        loss = Decimal(str(portfolio_value)) * Decimal(str(shock))
        return loss

    def apply_scenario(self, scenario: dict[str, float]) -> Decimal:
        """Apply user-defined scenario to portfolio.

        Supports two position data formats:
        1. Explicit positions: DataFrame with 'symbol' and 'value' columns
        2. Returns-based: DataFrame with '{symbol}_returns' columns (uses equal weights)

        Args:
            scenario: Dictionary mapping asset symbols to shocks
                Example: {"SPY": -0.2, "TLT": 0.1}

        Returns:
            Estimated loss as Decimal

        Raises:
            ValueError: If positions data not provided
        """
        if self.positions is None:
            raise ValueError(
                "Positions data required for scenario analysis. "
                "Provide positions in RiskAnalytics.__init__()"
            )

        total_loss = Decimal(0)

        # Check if positions has explicit symbol/value columns
        if "symbol" in self.positions.columns and "value" in self.positions.columns:
            # Format 1: Explicit positions with symbol and value
            for symbol, shock in scenario.items():
                position_data = self.positions[self.positions["symbol"] == symbol]

                if len(position_data) > 0:
                    position_value = position_data["value"].iloc[-1]
                    position_loss = Decimal(str(position_value)) * Decimal(str(shock))
                    total_loss += position_loss
        else:
            # Format 2: Returns-based positions (e.g., SPY_returns, TLT_returns)
            # Use portfolio value and equal weights for simplicity
            portfolio_value = (
                self.data["portfolio_value"].iloc[-1]
                if "portfolio_value" in self.data.columns
                else Decimal("100000")  # Default
            )

            # Get returns columns
            returns_cols = [col for col in self.positions.columns if col.endswith("_returns")]
            n_assets = len(returns_cols)

            if n_assets == 0:
                raise ValueError(
                    "Positions must have either 'symbol'/'value' columns "
                    "or '{symbol}_returns' columns"
                )

            # Assume equal weights
            position_value = Decimal(str(portfolio_value)) / n_assets

            for symbol, shock in scenario.items():
                # Check if this symbol exists in returns columns
                returns_col = f"{symbol}_returns"
                if returns_col in self.positions.columns:
                    position_loss = position_value * Decimal(str(shock))
                    total_loss += position_loss

        return total_loss

    def calculate_correlation(self) -> pd.DataFrame:
        """Calculate correlation matrix of portfolio assets.

        Requires positions data with returns for each asset.

        Returns:
            Correlation matrix as DataFrame

        Raises:
            ValueError: If positions data not provided
        """
        if self.positions is None:
            raise ValueError(
                "Positions data required for correlation analysis. "
                "Provide positions in RiskAnalytics.__init__()"
            )

        # Calculate correlation matrix
        # Assuming positions has returns columns for each asset
        correlation_matrix = self.positions.corr()

        return correlation_matrix

    def calculate_beta(self) -> dict[str, Decimal]:
        """Calculate portfolio beta vs benchmark.

        Beta measures sensitivity to market movements:
        - Beta = 1: Moves with market
        - Beta > 1: More volatile than market
        - Beta < 1: Less volatile than market

        Formula: β = Cov(portfolio, benchmark) / Var(benchmark)

        Returns:
            Dictionary with beta metrics:
            - 'beta': Portfolio beta
            - 'alpha': Jensen's alpha (intercept)
            - 'r_squared': R-squared of regression

        Raises:
            ValueError: If benchmark returns not provided
        """
        if self.benchmark_returns is None:
            raise ValueError(
                "Benchmark returns required for beta calculation. "
                "Provide benchmark_returns in RiskAnalytics.__init__()"
            )

        # Align returns with benchmark
        aligned_data = pd.DataFrame(
            {"portfolio": self.returns, "benchmark": self.benchmark_returns}
        ).dropna()

        if len(aligned_data) < 30:
            raise InsufficientDataError(
                f"Insufficient aligned data for beta calculation: {len(aligned_data)} observations"
            )

        # Calculate alpha using regression (also calculates beta)
        # Using uppercase X and y as is standard convention in statistics/ML
        X = aligned_data["benchmark"].to_numpy().reshape(-1, 1)  # noqa: N806
        y = aligned_data["portfolio"].to_numpy()

        # Add intercept
        X_with_intercept = np.column_stack([np.ones(len(X)), X])  # noqa: N806

        # Linear regression: y = alpha + beta * X
        coefficients = np.linalg.lstsq(X_with_intercept, y, rcond=None)[0]
        alpha = coefficients[0]
        beta_from_regression = coefficients[1]

        # Calculate R-squared
        y_pred = X_with_intercept @ coefficients
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - y.mean()) ** 2)
        r_squared = 1 - (ss_res / ss_tot)

        return {
            "beta": Decimal(str(beta_from_regression)),
            "alpha": Decimal(str(alpha)),
            "r_squared": Decimal(str(r_squared)),
        }

    def calculate_tail_risk(self) -> dict[str, Decimal]:
        """Calculate tail risk metrics.

        Returns:
            Dictionary with tail risk metrics:
            - 'skewness': Asymmetry of returns distribution
                (negative = more extreme losses)
            - 'kurtosis': Fat tails indicator
                (high = more extreme events)
            - 'max_loss_1d': Maximum 1-day loss
            - 'max_loss_5d': Maximum 5-day cumulative loss
            - 'max_loss_10d': Maximum 10-day cumulative loss
            - 'downside_deviation': Standard deviation of negative returns
        """
        # Skewness and kurtosis
        skewness = stats.skew(self.returns_array)
        kurtosis = stats.kurtosis(self.returns_array)

        # Max losses
        max_loss_1d = self.returns_array.min()

        # Rolling sums for multi-day losses
        if len(self.returns_array) >= 5:
            rolling_5d = pd.Series(self.returns_array).rolling(5).sum()
            max_loss_5d = rolling_5d.min()
        else:
            max_loss_5d = max_loss_1d

        if len(self.returns_array) >= 10:
            rolling_10d = pd.Series(self.returns_array).rolling(10).sum()
            max_loss_10d = rolling_10d.min()
        else:
            max_loss_10d = max_loss_5d

        # Downside deviation (semideviation)
        negative_returns = self.returns_array[self.returns_array < 0]
        downside_deviation = negative_returns.std() if len(negative_returns) > 0 else 0.0

        return {
            "skewness": Decimal(str(skewness)),
            "kurtosis": Decimal(str(kurtosis)),
            "max_loss_1d": Decimal(str(max_loss_1d)),
            "max_loss_5d": Decimal(str(max_loss_5d)),
            "max_loss_10d": Decimal(str(max_loss_10d)),
            "downside_deviation": Decimal(str(downside_deviation)),
        }

    def calculate_risk_decomposition(self, confidence: float = 0.95) -> pd.DataFrame:
        """Calculate risk decomposition (component VaR).

        Decomposes portfolio VaR into contributions from individual positions
        using marginal VaR and component VaR calculations.

        Formula:
            Marginal VaR_i = (Cov(r_i, r_portfolio) / sigma_portfolio) * z_score
            Component VaR_i = weight_i * Marginal VaR_i
            Risk Contribution % = Component VaR_i / Portfolio VaR * 100

        Args:
            confidence: Confidence level for VaR calculation (default: 0.95)

        Returns:
            DataFrame with columns:
            - 'symbol': Asset symbol
            - 'marginal_var': Marginal VaR (change in portfolio VaR per unit change in position)
            - 'component_var': Component VaR (contribution to total portfolio VaR)
            - 'risk_contribution_pct': Percentage contribution to portfolio risk

        Raises:
            ValueError: If positions data not provided
            InsufficientDataError: If insufficient data for covariance calculation
        """
        if self.positions is None:
            raise ValueError(
                "Positions data required for risk decomposition. "
                "Provide positions in RiskAnalytics.__init__()"
            )

        # Extract asset returns columns (columns ending with '_returns')
        returns_cols = [col for col in self.positions.columns if col.endswith("_returns")]

        if len(returns_cols) == 0:
            raise ValueError(
                "Positions DataFrame must contain asset return columns (e.g., 'SPY_returns')"
            )

        # Extract asset symbols from column names
        symbols = [col.replace("_returns", "") for col in returns_cols]

        # Get asset returns
        asset_returns = self.positions[returns_cols].to_numpy()

        # Calculate equal weights (simplified - in practice would use actual position values)
        n_assets = len(symbols)
        weights = np.ones(n_assets) / n_assets

        # Calculate portfolio returns
        portfolio_returns = asset_returns @ weights

        # Calculate portfolio standard deviation
        portfolio_std = portfolio_returns.std()

        if portfolio_std == 0:
            raise InsufficientDataError(
                "Portfolio has zero volatility - cannot calculate risk decomposition"
            )

        # Calculate covariance between each asset and portfolio
        asset_portfolio_cov = np.array(
            [np.cov(asset_returns[:, i], portfolio_returns)[0, 1] for i in range(n_assets)]
        )

        # Calculate z-score for confidence level
        z_score = abs(stats.norm.ppf(1 - confidence))

        # Calculate marginal VaR for each asset
        # Marginal VaR = (Cov(r_i, r_p) / sigma_p) * z_score
        marginal_var = (asset_portfolio_cov / portfolio_std) * z_score

        # Calculate component VaR
        # Component VaR = weight_i * Marginal VaR_i
        component_var = weights * marginal_var

        # Calculate portfolio VaR for risk contribution percentage
        portfolio_var = portfolio_std * z_score

        # Calculate risk contribution percentage
        if portfolio_var != 0:
            risk_contribution_pct = (component_var / portfolio_var) * 100
        else:
            risk_contribution_pct = np.zeros(n_assets)

        # Create results DataFrame
        results = pd.DataFrame(
            {
                "symbol": symbols,
                "marginal_var": [Decimal(str(mv)) for mv in marginal_var],
                "component_var": [Decimal(str(cv)) for cv in component_var],
                "risk_contribution_pct": [Decimal(str(rc)) for rc in risk_contribution_pct],
            }
        )

        # Sort by absolute component VaR (highest risk contributors first)
        results["abs_component_var"] = results["component_var"].abs()
        results = results.sort_values("abs_component_var", ascending=False)
        results = results.drop(columns=["abs_component_var"])
        results = results.reset_index(drop=True)

        return results

    def plot_var_distribution(
        self,
        method: str = "historical",
        confidence: float = 0.95,
        bins: int = 50,
        figsize: tuple = (10, 6),
    ) -> plt.Figure:
        """Plot returns distribution with VaR threshold.

        Args:
            method: VaR calculation method
            confidence: Confidence level to plot
            bins: Number of histogram bins
            figsize: Figure size (width, height)

        Returns:
            Matplotlib figure
        """
        var_results = self.calculate_var(method=method)
        var_key = f"var_{int(confidence * 100)}"
        var = float(var_results[var_key])

        fig, ax = plt.subplots(figsize=figsize)

        # Plot histogram
        ax.hist(self.returns_array, bins=bins, alpha=0.7, color="blue", edgecolor="black")

        # Plot VaR threshold line
        ax.axvline(
            var, color="red", linestyle="--", linewidth=2, label=f"VaR ({confidence * 100:.0f}%)"
        )

        # Labels
        ax.set_xlabel("Returns")
        ax.set_ylabel("Frequency")
        ax.set_title(f"Returns Distribution with {confidence * 100:.0f}% VaR")
        ax.legend()
        ax.grid(alpha=0.3)

        return fig

    def plot_stress_test_results(self, figsize: tuple = (10, 6)) -> plt.Figure:
        """Plot stress test results as bar chart.

        Args:
            figsize: Figure size (width, height)

        Returns:
            Matplotlib figure
        """
        stress_results = self.run_stress_tests()

        # Convert to DataFrame for plotting
        scenarios = list(stress_results.keys())
        losses = [float(stress_results[s]) for s in scenarios]

        # Clean up scenario names for display
        display_names = [s.replace("_", " ").title() for s in scenarios]

        fig, ax = plt.subplots(figsize=figsize)

        colors = ["red" if loss < 0 else "green" for loss in losses]
        ax.bar(display_names, losses, color=colors, alpha=0.7, edgecolor="black")

        ax.set_xlabel("Scenario")
        ax.set_ylabel("Estimated Loss ($)")
        ax.set_title("Stress Test Results")
        ax.grid(axis="y", alpha=0.3)
        ax.axhline(0, color="black", linewidth=0.8)

        # Rotate x labels if needed
        plt.xticks(rotation=45, ha="right")

        plt.tight_layout()
        return fig

    def plot_correlation_heatmap(self, figsize: tuple = (10, 8)) -> plt.Figure:
        """Plot correlation heatmap.

        Args:
            figsize: Figure size (width, height)

        Returns:
            Matplotlib figure

        Raises:
            ValueError: If positions data not provided
        """
        correlation_matrix = self.calculate_correlation()

        fig, ax = plt.subplots(figsize=figsize)

        sns.heatmap(
            correlation_matrix,
            annot=True,
            fmt=".2f",
            cmap="coolwarm",
            center=0,
            square=True,
            linewidths=1,
            cbar_kws={"shrink": 0.8},
            ax=ax,
        )

        ax.set_title("Asset Correlation Matrix")

        plt.tight_layout()
        return fig
