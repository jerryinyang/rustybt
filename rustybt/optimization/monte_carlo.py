"""Monte Carlo simulation with trade permutation for robustness testing.

This module provides Monte Carlo simulation capabilities to validate if strategy
performance is due to skill or lucky trade sequencing by shuffling trade order
and generating performance distributions.
"""

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Literal

import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from scipy import stats


@dataclass(frozen=True)
class MonteCarloResult:
    """Monte Carlo simulation result with statistical analysis.

    Contains performance distributions, confidence intervals, and statistical
    significance metrics from Monte Carlo permutation or bootstrap analysis.

    Attributes:
        observed_metrics: Original backtest metrics (before permutation)
        simulated_metrics: Distribution of metrics from all simulations
        confidence_intervals: Confidence intervals for each metric
        p_values: P-values testing if observed result is significant
        percentile_ranks: Percentile rank of observed result in distribution
        n_simulations: Number of simulations performed
        method: Simulation method ('permutation' or 'bootstrap')
        seed: Random seed used for reproducibility
    """

    observed_metrics: dict[str, Decimal]
    simulated_metrics: dict[str, list[Decimal]]
    confidence_intervals: dict[str, tuple[Decimal, Decimal]]
    p_values: dict[str, Decimal]
    percentile_ranks: dict[str, Decimal]
    n_simulations: int
    method: Literal["permutation", "bootstrap"]
    seed: int | None

    @property
    def is_significant(self) -> dict[str, bool]:
        """Check if each metric is statistically significant (p < 0.05).

        Returns:
            Dictionary mapping metric name to significance boolean
        """
        return {metric: p_value < Decimal("0.05") for metric, p_value in self.p_values.items()}

    @property
    def is_robust(self) -> dict[str, bool]:
        """Check if observed result is outside 95% CI (robust indicator).

        Returns:
            Dictionary mapping metric name to robustness boolean
        """
        result = {}
        for metric, (ci_lower, ci_upper) in self.confidence_intervals.items():
            observed = self.observed_metrics[metric]
            # Robust if outside CI bounds
            result[metric] = observed < ci_lower or observed > ci_upper
        return result

    def get_summary(self, metric: str = "sharpe_ratio") -> str:
        """Generate summary interpretation for a metric.

        Args:
            metric: Metric name to summarize (default: 'sharpe_ratio')

        Returns:
            Human-readable interpretation string
        """
        if metric not in self.observed_metrics:
            raise ValueError(f"Metric '{metric}' not found in results")

        observed = self.observed_metrics[metric]
        ci_lower, ci_upper = self.confidence_intervals[metric]
        p_value = self.p_values[metric]
        percentile = self.percentile_ranks[metric]

        lines = [
            f"Monte Carlo Analysis ({self.n_simulations} simulations, {self.method} method)",
            f"Metric: {metric}",
            f"Observed: {observed:.4f}",
            f"95% CI: [{ci_lower:.4f}, {ci_upper:.4f}]",
            f"P-value: {p_value:.4f}",
            f"Percentile: {percentile:.1f}",
            "",
        ]

        # Interpretation
        if self.is_significant[metric] and self.is_robust[metric]:
            lines.append("✅ ROBUST: Strategy is statistically significant and outside 95% CI")
        elif self.is_significant[metric]:
            lines.append("⚠️  SIGNIFICANT: Statistically significant but close to CI boundary")
        elif self.is_robust[metric]:
            lines.append("⚠️  UNUSUAL: Outside CI but not statistically significant")
        else:
            lines.append("❌ NOT ROBUST: Performance may be due to luck")

        return "\n".join(lines)

    def plot_distribution(
        self,
        metric: str = "sharpe_ratio",
        output_path: str | Path | None = None,
        show: bool = True,
    ) -> None:
        """Plot distribution of simulated metric with observed value.

        Creates histogram of simulated metric distribution with annotations
        showing observed value, confidence intervals, and statistical significance.

        Args:
            metric: Metric name to plot (default: 'sharpe_ratio')
            output_path: Path to save plot (optional, saves if provided)
            show: Whether to display plot (default: True)

        Raises:
            ValueError: If metric not found in results
        """
        if metric not in self.observed_metrics:
            raise ValueError(f"Metric '{metric}' not found in results")

        # Extract data
        observed = float(self.observed_metrics[metric])
        distribution = [float(v) for v in self.simulated_metrics[metric]]
        ci_lower, ci_upper = self.confidence_intervals[metric]
        ci_lower = float(ci_lower)
        ci_upper = float(ci_upper)
        p_value = float(self.p_values[metric])
        percentile = float(self.percentile_ranks[metric])

        # Create figure
        _fig, ax = plt.subplots(figsize=(10, 6))

        # Plot histogram
        ax.hist(
            distribution,
            bins=50,
            alpha=0.7,
            color="steelblue",
            edgecolor="black",
            label="Simulated Distribution",
        )

        # Add observed value line
        ax.axvline(
            observed,
            color="red",
            linewidth=2,
            linestyle="-",
            label=f"Observed: {observed:.4f}",
        )

        # Add confidence interval lines
        ax.axvline(
            ci_lower,
            color="green",
            linewidth=1.5,
            linestyle="--",
            label=f"95% CI: [{ci_lower:.4f}, {ci_upper:.4f}]",
        )
        ax.axvline(ci_upper, color="green", linewidth=1.5, linestyle="--")

        # Labels and title
        ax.set_xlabel(metric.replace("_", " ").title(), fontsize=12)
        ax.set_ylabel("Frequency", fontsize=12)
        ax.set_title(
            f"Monte Carlo Permutation Test: {metric.replace('_', ' ').title()}\n"
            f"({self.n_simulations} simulations, {self.method} method)",
            fontsize=14,
            fontweight="bold",
        )

        # Add statistics box
        stats_text = (
            f"P-value: {p_value:.4f}\n"
            f"Percentile: {percentile:.1f}\n"
            f"Mean: {np.mean(distribution):.4f}\n"
            f"Std: {np.std(distribution):.4f}"
        )
        ax.text(
            0.02,
            0.98,
            stats_text,
            transform=ax.transAxes,
            fontsize=10,
            verticalalignment="top",
            bbox={"boxstyle": "round", "facecolor": "wheat", "alpha": 0.5},
        )

        # Add interpretation
        if self.is_significant[metric] and self.is_robust[metric]:
            interpretation = "✅ ROBUST"
            color = "green"
        elif self.is_significant[metric]:
            interpretation = "⚠️  SIGNIFICANT"
            color = "orange"
        elif self.is_robust[metric]:
            interpretation = "⚠️  UNUSUAL"
            color = "orange"
        else:
            interpretation = "❌ NOT ROBUST"
            color = "red"

        ax.text(
            0.98,
            0.98,
            interpretation,
            transform=ax.transAxes,
            fontsize=12,
            fontweight="bold",
            verticalalignment="top",
            horizontalalignment="right",
            bbox={"boxstyle": "round", "facecolor": color, "alpha": 0.3},
        )

        # Legend
        ax.legend(loc="upper right", fontsize=10)
        ax.grid(True, alpha=0.3)

        # Save if path provided
        if output_path is not None:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(output_path, dpi=300, bbox_inches="tight")

        # Show if requested
        if show:
            plt.show()
        else:
            plt.close()


class MonteCarloSimulator:
    """Monte Carlo simulation with trade permutation for robustness testing.

    Tests if strategy performance is due to skill or lucky trade sequencing
    by shuffling trade order and generating performance distribution.

    Best for:
        - Validating backtest results
        - Detecting luck vs. skill
        - Calculating confidence intervals for metrics
        - Statistical significance testing

    Args:
        n_simulations: Number of Monte Carlo runs (default: 1000)
        method: 'permutation' or 'bootstrap' (default: 'permutation')
        seed: Random seed for reproducibility (optional)
        confidence_level: Confidence level for intervals (default: 0.95)

    Example:
        >>> # Run backtest
        >>> result = run_backtest(strategy, data)
        >>> trades = result.transactions  # DataFrame with trades
        >>>
        >>> # Monte Carlo simulation
        >>> mc = MonteCarloSimulator(n_simulations=1000, method='permutation', seed=42)
        >>> mc_results = mc.run(
        ...     trades=trades,
        ...     observed_metrics={'sharpe_ratio': result.sharpe_ratio}
        ... )
        >>>
        >>> print(mc_results.get_summary('sharpe_ratio'))
        >>>
        >>> if mc_results.is_significant['sharpe_ratio']:
        ...     print("Strategy is statistically robust!")
        >>> else:
        ...     print("Performance may be due to luck")
    """

    def __init__(
        self,
        n_simulations: int = 1000,
        method: Literal["permutation", "bootstrap"] = "permutation",
        seed: int | None = None,
        confidence_level: float = 0.95,
    ):
        """Initialize Monte Carlo simulator.

        Args:
            n_simulations: Number of simulations to run
            method: Simulation method ('permutation' or 'bootstrap')
            seed: Random seed for reproducibility
            confidence_level: Confidence level for intervals (0.0-1.0)

        Raises:
            ValueError: If parameters are invalid
        """
        if n_simulations < 100:
            raise ValueError("n_simulations must be >= 100 for reliable statistics")
        if method not in ("permutation", "bootstrap"):
            raise ValueError(f"Invalid method: {method}")
        if not 0.0 < confidence_level < 1.0:
            raise ValueError("confidence_level must be between 0.0 and 1.0")

        self.n_simulations = n_simulations
        self.method = method
        self.seed = seed
        self.confidence_level = confidence_level

        # Set random seed for reproducibility
        if seed is not None:
            np.random.seed(seed)

    def run(
        self,
        trades: pl.DataFrame,
        observed_metrics: dict[str, Decimal],
        initial_capital: Decimal = Decimal("100000"),
    ) -> MonteCarloResult:
        """Run Monte Carlo simulation on trade sequence.

        Args:
            trades: DataFrame with columns: ['timestamp', 'return', 'pnl', 'asset']
                   Returns should be absolute returns (0.02 = 2% gain)
            observed_metrics: Dictionary of observed metrics to test
                            Must include at least one metric (e.g., 'sharpe_ratio')
            initial_capital: Starting capital for equity curve reconstruction

        Returns:
            MonteCarloResult with statistical analysis

        Raises:
            ValueError: If trades DataFrame is invalid or empty
        """
        # Validate inputs
        self._validate_trades(trades)
        if not observed_metrics:
            raise ValueError("observed_metrics cannot be empty")

        # Extract trade returns and PnL
        trade_data = self._extract_trade_data(trades)

        # Run simulations
        simulated_distributions = self._run_simulations(trade_data, initial_capital)

        # Calculate statistical metrics
        confidence_intervals = self._calculate_confidence_intervals(simulated_distributions)
        p_values = self._calculate_p_values(simulated_distributions, observed_metrics)
        percentile_ranks = self._calculate_percentile_ranks(
            simulated_distributions, observed_metrics
        )

        return MonteCarloResult(
            observed_metrics=observed_metrics,
            simulated_metrics=simulated_distributions,
            confidence_intervals=confidence_intervals,
            p_values=p_values,
            percentile_ranks=percentile_ranks,
            n_simulations=self.n_simulations,
            method=self.method,
            seed=self.seed,
        )

    def _validate_trades(self, trades: pl.DataFrame) -> None:
        """Validate trades DataFrame has required columns.

        Args:
            trades: Trades DataFrame to validate

        Raises:
            ValueError: If validation fails
        """
        if len(trades) == 0:
            raise ValueError("Trades DataFrame cannot be empty")

        required_columns = ["return", "pnl"]
        missing = [col for col in required_columns if col not in trades.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        # Check for invalid values
        if trades["return"].null_count() > 0:
            raise ValueError("Trades contain null returns")
        if trades["pnl"].null_count() > 0:
            raise ValueError("Trades contain null PnL")

    def _extract_trade_data(self, trades: pl.DataFrame) -> dict[str, np.ndarray]:
        """Extract trade data as numpy arrays for efficient processing.

        Args:
            trades: Trades DataFrame

        Returns:
            Dictionary with 'returns' and 'pnl' arrays
        """
        return {
            "returns": trades["return"].to_numpy(),
            "pnl": trades["pnl"].to_numpy(),
        }

    def _run_simulations(
        self, trade_data: dict[str, np.ndarray], initial_capital: Decimal
    ) -> dict[str, list[Decimal]]:
        """Run Monte Carlo simulations.

        Args:
            trade_data: Dictionary with trade returns and PnL
            initial_capital: Starting capital

        Returns:
            Dictionary mapping metric names to lists of simulated values
        """
        simulated_metrics: dict[str, list[Decimal]] = {
            "sharpe_ratio": [],
            "total_return": [],
            "max_drawdown": [],
            "win_rate": [],
        }

        for _ in range(self.n_simulations):
            # Generate permuted or bootstrapped trade sequence
            if self.method == "permutation":
                sim_returns, sim_pnl = self._permute_trades(trade_data)
            else:  # bootstrap
                sim_returns, sim_pnl = self._bootstrap_trades(trade_data)

            # Reconstruct equity curve from shuffled trades
            equity_curve = self._reconstruct_equity_curve(sim_pnl, float(initial_capital))

            # Calculate metrics from simulated equity curve
            metrics = self._calculate_metrics(sim_returns, equity_curve)

            # Store metrics
            for metric_name, value in metrics.items():
                simulated_metrics[metric_name].append(value)

        return simulated_metrics

    def _permute_trades(self, trade_data: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
        """Permute trade order (shuffle without replacement).

        Args:
            trade_data: Dictionary with trade returns and PnL

        Returns:
            Tuple of (permuted_returns, permuted_pnl)
        """
        n_trades = len(trade_data["returns"])
        indices = np.random.permutation(n_trades)

        return (
            trade_data["returns"][indices],
            trade_data["pnl"][indices],
        )

    def _bootstrap_trades(self, trade_data: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
        """Bootstrap trade sample (sample with replacement).

        Args:
            trade_data: Dictionary with trade returns and PnL

        Returns:
            Tuple of (bootstrapped_returns, bootstrapped_pnl)
        """
        n_trades = len(trade_data["returns"])
        indices = np.random.choice(n_trades, size=n_trades, replace=True)

        return (
            trade_data["returns"][indices],
            trade_data["pnl"][indices],
        )

    def _reconstruct_equity_curve(
        self, pnl_sequence: np.ndarray, initial_capital: float
    ) -> np.ndarray:
        """Reconstruct equity curve from PnL sequence.

        Args:
            pnl_sequence: Array of trade P&L values
            initial_capital: Starting capital

        Returns:
            Equity curve array (includes initial capital at start)
        """
        # Start with initial capital
        equity_curve = np.zeros(len(pnl_sequence) + 1)
        equity_curve[0] = initial_capital

        # Accumulate PnL
        equity_curve[1:] = initial_capital + np.cumsum(pnl_sequence)

        return equity_curve

    def _calculate_metrics(
        self, returns: np.ndarray, equity_curve: np.ndarray
    ) -> dict[str, Decimal]:
        """Calculate performance metrics from equity curve.

        Args:
            returns: Array of trade returns
            equity_curve: Equity curve array

        Returns:
            Dictionary of calculated metrics
        """
        metrics = {}

        # Sharpe ratio
        if len(returns) > 1:
            mean_return = np.mean(returns)
            std_return = np.std(returns, ddof=1)
            sharpe = mean_return / std_return * np.sqrt(252) if std_return > 0 else 0.0
        else:
            sharpe = 0.0
        metrics["sharpe_ratio"] = Decimal(str(sharpe))

        # Total return
        total_return = (equity_curve[-1] - equity_curve[0]) / equity_curve[0]
        metrics["total_return"] = Decimal(str(total_return))

        # Maximum drawdown
        running_max = np.maximum.accumulate(equity_curve)
        drawdowns = (equity_curve - running_max) / running_max
        max_drawdown = abs(np.min(drawdowns))
        metrics["max_drawdown"] = Decimal(str(max_drawdown))

        # Win rate
        win_rate = np.mean(returns > 0) if len(returns) > 0 else 0.0
        metrics["win_rate"] = Decimal(str(win_rate))

        return metrics

    def _calculate_confidence_intervals(
        self, simulated_distributions: dict[str, list[Decimal]]
    ) -> dict[str, tuple[Decimal, Decimal]]:
        """Calculate confidence intervals for each metric.

        Args:
            simulated_distributions: Dictionary of simulated metric distributions

        Returns:
            Dictionary mapping metric name to (lower, upper) CI bounds
        """
        alpha = 1 - self.confidence_level
        lower_percentile = (alpha / 2) * 100
        upper_percentile = (1 - alpha / 2) * 100

        confidence_intervals = {}
        for metric_name, distribution in simulated_distributions.items():
            # Convert to float for percentile calculation
            values = np.array([float(v) for v in distribution])

            ci_lower = np.percentile(values, lower_percentile)
            ci_upper = np.percentile(values, upper_percentile)

            confidence_intervals[metric_name] = (
                Decimal(str(ci_lower)),
                Decimal(str(ci_upper)),
            )

        return confidence_intervals

    def _calculate_p_values(
        self,
        simulated_distributions: dict[str, list[Decimal]],
        observed_metrics: dict[str, Decimal],
    ) -> dict[str, Decimal]:
        """Calculate p-values testing if observed result is significant.

        P-value = fraction of simulations with result >= observed (for positive metrics).

        Args:
            simulated_distributions: Dictionary of simulated metric distributions
            observed_metrics: Dictionary of observed metric values

        Returns:
            Dictionary mapping metric name to p-value
        """
        p_values = {}

        for metric_name in simulated_distributions:
            if metric_name not in observed_metrics:
                # Skip metrics not in observed
                continue

            observed = float(observed_metrics[metric_name])
            distribution = np.array([float(v) for v in simulated_distributions[metric_name]])

            # For max_drawdown (lower is better), calculate opposite tail
            if metric_name == "max_drawdown":
                p_value = np.mean(distribution <= observed)
            else:
                # For other metrics (higher is better)
                p_value = np.mean(distribution >= observed)

            p_values[metric_name] = Decimal(str(p_value))

        return p_values

    def _calculate_percentile_ranks(
        self,
        simulated_distributions: dict[str, list[Decimal]],
        observed_metrics: dict[str, Decimal],
    ) -> dict[str, Decimal]:
        """Calculate percentile rank of observed result in distribution.

        Args:
            simulated_distributions: Dictionary of simulated metric distributions
            observed_metrics: Dictionary of observed metric values

        Returns:
            Dictionary mapping metric name to percentile rank (0-100)
        """
        percentile_ranks = {}

        for metric_name in simulated_distributions:
            if metric_name not in observed_metrics:
                continue

            observed = float(observed_metrics[metric_name])
            distribution = np.array([float(v) for v in simulated_distributions[metric_name]])

            # Calculate percentile rank using scipy
            percentile = stats.percentileofscore(distribution, observed, kind="rank")

            percentile_ranks[metric_name] = Decimal(str(percentile))

        return percentile_ranks
