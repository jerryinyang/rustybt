"""Monte Carlo simulation with noise infusion for robustness testing.

This module provides noise infusion capabilities to validate if strategy
performance is overfit to specific historical price patterns by adding
synthetic noise to OHLCV data and measuring performance degradation.
"""

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Literal

import matplotlib.pyplot as plt
import numpy as np
import polars as pl


@dataclass(frozen=True)
class NoiseInfusionResult:
    """Noise infusion simulation result with degradation analysis.

    Contains performance distributions across noise realizations, degradation
    metrics, and robustness indicators for strategy validation.

    Attributes:
        original_metrics: Metrics from noise-free backtest
        noisy_metrics: Distribution of metrics from noisy backtests
        mean_metrics: Mean metrics across all noise realizations
        std_metrics: Standard deviation of metrics across realizations
        degradation_pct: Percentage degradation for each metric
        worst_case_metrics: 5th percentile (worst-case) metrics
        confidence_intervals: 95% confidence intervals for each metric
        n_simulations: Number of noise realizations
        noise_model: Noise model used ('gaussian' or 'bootstrap')
        std_pct: Noise amplitude as percentage
        seed: Random seed used
    """

    original_metrics: dict[str, Decimal]
    noisy_metrics: dict[str, list[Decimal]]
    mean_metrics: dict[str, Decimal]
    std_metrics: dict[str, Decimal]
    degradation_pct: dict[str, Decimal]
    worst_case_metrics: dict[str, Decimal]
    confidence_intervals: dict[str, tuple[Decimal, Decimal]]
    n_simulations: int
    noise_model: Literal["gaussian", "bootstrap"]
    std_pct: Decimal
    seed: int | None

    @property
    def is_robust(self) -> dict[str, bool]:
        """Check if strategy is robust to noise (degradation < 20%).

        Returns:
            Dictionary mapping metric name to robustness boolean
        """
        return {
            metric: degradation < Decimal("20")
            for metric, degradation in self.degradation_pct.items()
        }

    @property
    def is_fragile(self) -> dict[str, bool]:
        """Check if strategy is fragile (degradation > 50%, overfit indicator).

        Returns:
            Dictionary mapping metric name to fragility boolean
        """
        return {
            metric: degradation > Decimal("50")
            for metric, degradation in self.degradation_pct.items()
        }

    def get_summary(self, metric: str = "sharpe_ratio") -> str:
        """Generate summary interpretation for a metric.

        Args:
            metric: Metric name to summarize (default: 'sharpe_ratio')

        Returns:
            Human-readable interpretation string

        Raises:
            ValueError: If metric not found in results
        """
        if metric not in self.original_metrics:
            raise ValueError(f"Metric '{metric}' not found in results")

        original = self.original_metrics[metric]
        mean = self.mean_metrics[metric]
        std = self.std_metrics[metric]
        degradation = self.degradation_pct[metric]
        worst_case = self.worst_case_metrics[metric]
        ci_lower, ci_upper = self.confidence_intervals[metric]

        lines = [
            f"Noise Infusion Test ({self.n_simulations} simulations, "
            f"{self.noise_model} noise, {float(self.std_pct) * 100:.1f}% amplitude)",
            f"Metric: {metric}",
            f"Original (noise-free): {original:.4f}",
            f"Noisy mean: {mean:.4f} ± {std:.4f}",
            f"95% CI: [{ci_lower:.4f}, {ci_upper:.4f}]",
            f"Worst case (5th %ile): {worst_case:.4f}",
            f"Degradation: {degradation:.1f}%",
            "",
        ]

        # Interpretation
        if self.is_fragile[metric]:
            lines.append("❌ FRAGILE: Strategy highly sensitive to noise (likely overfit)")
        elif degradation > Decimal("25"):
            lines.append("⚠️  MODERATE: Strategy shows moderate noise sensitivity")
        elif self.is_robust[metric]:
            lines.append("✅ ROBUST: Strategy tolerates noise well")
        else:
            lines.append("✅ GOOD: Strategy shows good noise tolerance")

        return "\n".join(lines)

    def plot_distribution(
        self,
        metric: str = "sharpe_ratio",
        output_path: str | Path | None = None,
        show: bool = True,
    ) -> None:
        """Plot distribution of noisy metric with original value.

        Creates histogram of noisy metric distribution with annotations
        showing original value, degradation, and robustness indicators.

        Args:
            metric: Metric name to plot (default: 'sharpe_ratio')
            output_path: Path to save plot (optional, saves if provided)
            show: Whether to display plot (default: True)

        Raises:
            ValueError: If metric not found in results
        """
        if metric not in self.original_metrics:
            raise ValueError(f"Metric '{metric}' not found in results")

        # Extract data
        original = float(self.original_metrics[metric])
        distribution = [float(v) for v in self.noisy_metrics[metric]]
        mean = float(self.mean_metrics[metric])
        ci_lower, ci_upper = self.confidence_intervals[metric]
        ci_lower = float(ci_lower)
        ci_upper = float(ci_upper)
        degradation = float(self.degradation_pct[metric])
        worst_case = float(self.worst_case_metrics[metric])

        # Create figure
        _fig, ax = plt.subplots(figsize=(10, 6))

        # Plot histogram
        ax.hist(
            distribution,
            bins=50,
            alpha=0.7,
            color="steelblue",
            edgecolor="black",
            label="Noisy Distribution",
        )

        # Add original value line
        ax.axvline(
            original,
            color="red",
            linewidth=2,
            linestyle="-",
            label=f"Original: {original:.4f}",
        )

        # Add mean line
        ax.axvline(
            mean,
            color="orange",
            linewidth=2,
            linestyle="--",
            label=f"Noisy Mean: {mean:.4f}",
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

        # Add worst case line
        ax.axvline(
            worst_case,
            color="purple",
            linewidth=1.5,
            linestyle=":",
            label=f"Worst Case (5%): {worst_case:.4f}",
        )

        # Labels and title
        ax.set_xlabel(metric.replace("_", " ").title(), fontsize=12)
        ax.set_ylabel("Frequency", fontsize=12)
        ax.set_title(
            f"Noise Infusion Test: {metric.replace('_', ' ').title()}\n"
            f"({self.n_simulations} simulations, {self.noise_model} noise, "
            f"{float(self.std_pct) * 100:.1f}% amplitude)",
            fontsize=14,
            fontweight="bold",
        )

        # Add statistics box
        stats_text = (
            f"Degradation: {degradation:.1f}%\n"
            f"Mean: {mean:.4f}\n"
            f"Std: {np.std(distribution):.4f}\n"
            f"Worst: {worst_case:.4f}"
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
        if self.is_fragile[metric]:
            interpretation = "❌ FRAGILE"
            color = "red"
        elif degradation > 25:
            interpretation = "⚠️  MODERATE"
            color = "orange"
        elif self.is_robust[metric]:
            interpretation = "✅ ROBUST"
            color = "green"
        else:
            interpretation = "✅ GOOD"
            color = "lightgreen"

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
        ax.legend(loc="upper right", fontsize=9)
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


class NoiseInfusionSimulator:
    """Monte Carlo simulation with noise infusion for robustness testing.

    Tests if strategy is overfit to specific historical price patterns by
    adding synthetic noise to data and measuring performance degradation.

    Best for:
        - Validating backtest robustness
        - Detecting overfitting to price patterns
        - Stress testing strategies
        - Assessing generalization beyond historical data

    Args:
        n_simulations: Number of noise realizations (default: 1000)
        std_pct: Noise amplitude as % of price (default: 0.01 = 1%)
        noise_model: 'gaussian' or 'bootstrap' (default: 'gaussian')
        seed: Random seed for reproducibility (optional)
        preserve_structure: Whether to preserve temporal structure (default: False)
        confidence_level: Confidence level for intervals (default: 0.95)

    Example:
        >>> # Run original backtest
        >>> result = run_backtest(strategy, data)
        >>> original_sharpe = result['sharpe_ratio']
        >>>
        >>> # Noise infusion test
        >>> sim = NoiseInfusionSimulator(n_simulations=1000, std_pct=0.01, seed=42)
        >>> results = sim.run(data, lambda d: run_backtest(strategy, d))
        >>>
        >>> print(f"Original Sharpe: {original_sharpe:.2f}")
        >>> print(f"Noisy Mean Sharpe: {results.mean_metrics['sharpe_ratio']:.2f}")
        >>> print(f"Degradation: {results.degradation_pct['sharpe_ratio']:.1f}%")
        >>>
        >>> if results.is_robust['sharpe_ratio']:
        ...     print("Strategy is robust to noise!")
        >>> else:
        ...     print("Strategy may be overfit to price patterns")
    """

    def __init__(
        self,
        n_simulations: int = 1000,
        std_pct: float = 0.01,
        noise_model: Literal["gaussian", "bootstrap"] = "gaussian",
        seed: int | None = None,
        preserve_structure: bool = False,
        confidence_level: float = 0.95,
    ):
        """Initialize noise infusion simulator.

        Args:
            n_simulations: Number of simulations to run
            std_pct: Noise amplitude as percentage (0.01 = 1%)
            noise_model: Noise generation method ('gaussian' or 'bootstrap')
            seed: Random seed for reproducibility
            preserve_structure: Whether to preserve temporal autocorrelation
            confidence_level: Confidence level for intervals (0.0-1.0)

        Raises:
            ValueError: If parameters are invalid
        """
        if n_simulations < 100:
            raise ValueError("n_simulations must be >= 100 for reliable statistics")
        if std_pct <= 0 or std_pct > 0.5:
            raise ValueError("std_pct must be between 0.0 and 0.5 (50%)")
        if noise_model not in ("gaussian", "bootstrap"):
            raise ValueError(f"Invalid noise_model: {noise_model}")
        if not 0.0 < confidence_level < 1.0:
            raise ValueError("confidence_level must be between 0.0 and 1.0")

        self.n_simulations = n_simulations
        self.std_pct = Decimal(str(std_pct))
        self.noise_model = noise_model
        self.seed = seed
        self.preserve_structure = preserve_structure
        self.confidence_level = confidence_level

        # Set random seed for reproducibility
        if seed is not None:
            np.random.seed(seed)

    def run(
        self,
        data: pl.DataFrame,
        backtest_fn: Callable[[pl.DataFrame], dict[str, Decimal]],
    ) -> NoiseInfusionResult:
        """Run noise infusion simulation on OHLCV data.

        Args:
            data: OHLCV DataFrame with columns: ['open', 'high', 'low', 'close', 'volume']
                 Must include timestamp/date column for temporal ordering
            backtest_fn: Function that takes OHLCV data and returns metrics dict
                        Example: lambda d: {'sharpe_ratio': Decimal('1.5'), ...}

        Returns:
            NoiseInfusionResult with degradation analysis

        Raises:
            ValueError: If data is invalid or backtest_fn doesn't return metrics
        """
        # Validate inputs
        self._validate_data(data)

        # Run original (noise-free) backtest
        original_metrics = backtest_fn(data)
        if not original_metrics:
            raise ValueError("backtest_fn must return non-empty metrics dictionary")

        # Run noisy simulations
        noisy_distributions = self._run_simulations(data, backtest_fn)

        # Calculate statistics
        mean_metrics = self._calculate_means(noisy_distributions)
        std_metrics = self._calculate_stds(noisy_distributions)
        degradation_pct = self._calculate_degradation(original_metrics, mean_metrics)
        worst_case_metrics = self._calculate_worst_case(noisy_distributions)
        confidence_intervals = self._calculate_confidence_intervals(noisy_distributions)

        return NoiseInfusionResult(
            original_metrics=original_metrics,
            noisy_metrics=noisy_distributions,
            mean_metrics=mean_metrics,
            std_metrics=std_metrics,
            degradation_pct=degradation_pct,
            worst_case_metrics=worst_case_metrics,
            confidence_intervals=confidence_intervals,
            n_simulations=self.n_simulations,
            noise_model=self.noise_model,
            std_pct=self.std_pct,
            seed=self.seed,
        )

    def add_noise(self, data: pl.DataFrame, sim_seed: int | None = None) -> pl.DataFrame:
        """Add noise to OHLCV data while preserving relationships.

        Args:
            data: OHLCV DataFrame
            sim_seed: Seed for this specific simulation (for reproducibility)

        Returns:
            Noisy OHLCV DataFrame with validated relationships
        """
        # Set seed for this simulation
        if sim_seed is not None:
            np.random.seed(sim_seed)

        # Generate noise based on model
        if self.noise_model == "gaussian":
            noisy_data = self._add_gaussian_noise(data)
        else:  # bootstrap
            noisy_data = self._add_bootstrap_noise(data)

        # Fix OHLCV relationships if violated
        noisy_data = self._fix_ohlcv_relationships(noisy_data)

        return noisy_data

    def _validate_data(self, data: pl.DataFrame) -> None:
        """Validate OHLCV DataFrame has required columns.

        Args:
            data: OHLCV DataFrame to validate

        Raises:
            ValueError: If validation fails
        """
        if len(data) == 0:
            raise ValueError("Data DataFrame cannot be empty")

        required_columns = ["open", "high", "low", "close", "volume"]
        missing = [col for col in required_columns if col not in data.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        # Check for null values
        for col in required_columns:
            if data[col].null_count() > 0:
                raise ValueError(f"Column '{col}' contains null values")

        # Validate OHLCV relationships
        violations = data.filter(
            (pl.col("high") < pl.col("low"))
            | (pl.col("high") < pl.col("open"))
            | (pl.col("high") < pl.col("close"))
            | (pl.col("low") > pl.col("open"))
            | (pl.col("low") > pl.col("close"))
            | (pl.col("volume") < 0)
        )

        if len(violations) > 0:
            raise ValueError(f"Data violates OHLCV constraints in {len(violations)} rows")

    def _run_simulations(
        self,
        data: pl.DataFrame,
        backtest_fn: Callable[[pl.DataFrame], dict[str, Decimal]],
    ) -> dict[str, list[Decimal]]:
        """Run noise infusion simulations.

        Args:
            data: Original OHLCV data
            backtest_fn: Backtest function

        Returns:
            Dictionary mapping metric names to lists of noisy values
        """
        # Initialize metric storage
        noisy_metrics: dict[str, list[Decimal]] = {}

        for i in range(self.n_simulations):
            # Generate noisy data
            sim_seed = None if self.seed is None else self.seed + i
            noisy_data = self.add_noise(data, sim_seed=sim_seed)

            # Run backtest on noisy data
            metrics = backtest_fn(noisy_data)

            # Store metrics
            for metric_name, value in metrics.items():
                if metric_name not in noisy_metrics:
                    noisy_metrics[metric_name] = []
                noisy_metrics[metric_name].append(value)

        return noisy_metrics

    def _add_gaussian_noise(self, data: pl.DataFrame) -> pl.DataFrame:
        """Add Gaussian noise to OHLCV data.

        Generates random returns from N(0, std_pct) and applies to prices
        while maintaining OHLC proportional relationships.

        Args:
            data: Original OHLCV data

        Returns:
            Noisy OHLCV data
        """
        # Generate noise for each bar
        n_bars = len(data)
        noise = np.random.normal(0, float(self.std_pct), size=n_bars)

        # Apply noise to close prices
        close = data["close"].to_numpy()
        close_noisy = close * (1 + noise)

        # Calculate scaling factor for each bar
        factor = close_noisy / close

        # Apply proportional scaling to OHLC
        open_noisy = data["open"].to_numpy() * factor
        high_noisy = data["high"].to_numpy() * factor
        low_noisy = data["low"].to_numpy() * factor

        # Volume stays the same (or add small noise if desired)
        volume_noisy = data["volume"].to_numpy()

        # Create noisy DataFrame
        noisy_data = data.clone()
        noisy_data = noisy_data.with_columns(
            [
                pl.Series("open", open_noisy),
                pl.Series("high", high_noisy),
                pl.Series("low", low_noisy),
                pl.Series("close", close_noisy),
                pl.Series("volume", volume_noisy),
            ]
        )

        return noisy_data

    def _add_bootstrap_noise(self, data: pl.DataFrame) -> pl.DataFrame:
        """Add bootstrap noise to OHLCV data.

        Resamples historical returns with replacement and applies to prices.
        Preserves empirical return distribution (fat tails, skewness).

        Args:
            data: Original OHLCV data

        Returns:
            Noisy OHLCV data
        """
        # Extract close prices
        close = data["close"].to_numpy()

        # Calculate returns
        returns = np.diff(close) / close[:-1]

        # Bootstrap sample returns (with replacement)
        n_bars = len(close)
        noise_returns = np.random.choice(returns, size=n_bars, replace=True)

        # Apply noise
        close_noisy = close * (1 + noise_returns)

        # Calculate scaling factor
        factor = close_noisy / close

        # Apply to OHLC
        open_noisy = data["open"].to_numpy() * factor
        high_noisy = data["high"].to_numpy() * factor
        low_noisy = data["low"].to_numpy() * factor
        volume_noisy = data["volume"].to_numpy()

        # Create noisy DataFrame
        noisy_data = data.clone()
        noisy_data = noisy_data.with_columns(
            [
                pl.Series("open", open_noisy),
                pl.Series("high", high_noisy),
                pl.Series("low", low_noisy),
                pl.Series("close", close_noisy),
                pl.Series("volume", volume_noisy),
            ]
        )

        return noisy_data

    def _fix_ohlcv_relationships(self, data: pl.DataFrame) -> pl.DataFrame:
        """Fix OHLCV relationships after noise application.

        Ensures: high >= low, high >= open/close, low <= open/close, volume >= 0

        Args:
            data: Potentially invalid OHLCV data

        Returns:
            Valid OHLCV data
        """
        # Extract columns as numpy arrays
        open_vals = data["open"].to_numpy()
        high_vals = data["high"].to_numpy()
        low_vals = data["low"].to_numpy()
        close_vals = data["close"].to_numpy()
        volume_vals = data["volume"].to_numpy()

        # Adjust high to be max of all
        high_vals = np.maximum.reduce([high_vals, open_vals, close_vals])

        # Adjust low to be min of all
        low_vals = np.minimum.reduce([low_vals, open_vals, close_vals])

        # Ensure high >= low (add small epsilon if needed)
        high_vals = np.maximum(high_vals, low_vals + 1e-8)

        # Ensure volume >= 0
        volume_vals = np.maximum(volume_vals, 0)

        # Create fixed DataFrame
        fixed_data = data.clone()
        fixed_data = fixed_data.with_columns(
            [
                pl.Series("open", open_vals),
                pl.Series("high", high_vals),
                pl.Series("low", low_vals),
                pl.Series("close", close_vals),
                pl.Series("volume", volume_vals),
            ]
        )

        return fixed_data

    def _calculate_means(self, distributions: dict[str, list[Decimal]]) -> dict[str, Decimal]:
        """Calculate mean for each metric distribution.

        Args:
            distributions: Metric distributions

        Returns:
            Dictionary of mean values
        """
        means = {}
        for metric_name, values in distributions.items():
            mean_val = np.mean([float(v) for v in values])
            means[metric_name] = Decimal(str(mean_val))
        return means

    def _calculate_stds(self, distributions: dict[str, list[Decimal]]) -> dict[str, Decimal]:
        """Calculate standard deviation for each metric distribution.

        Args:
            distributions: Metric distributions

        Returns:
            Dictionary of std values
        """
        stds = {}
        for metric_name, values in distributions.items():
            std_val = np.std([float(v) for v in values], ddof=1)
            stds[metric_name] = Decimal(str(std_val))
        return stds

    def _calculate_degradation(
        self, original: dict[str, Decimal], noisy_mean: dict[str, Decimal]
    ) -> dict[str, Decimal]:
        """Calculate performance degradation percentage.

        Degradation = (original - noisy_mean) / original * 100

        Args:
            original: Original metrics
            noisy_mean: Mean noisy metrics

        Returns:
            Dictionary of degradation percentages
        """
        degradation = {}
        for metric_name in original:
            if metric_name not in noisy_mean:
                continue

            orig = original[metric_name]
            noisy = noisy_mean[metric_name]

            # Calculate degradation (handle zero division)
            deg = (orig - noisy) / abs(orig) * Decimal("100") if orig != 0 else Decimal("0")
            degradation[metric_name] = deg

        return degradation

    def _calculate_worst_case(self, distributions: dict[str, list[Decimal]]) -> dict[str, Decimal]:
        """Calculate worst-case (5th percentile) metrics.

        Args:
            distributions: Metric distributions

        Returns:
            Dictionary of worst-case values
        """
        worst_case = {}
        for metric_name, values in distributions.items():
            values_array = np.array([float(v) for v in values])
            worst = np.percentile(values_array, 5)
            worst_case[metric_name] = Decimal(str(worst))
        return worst_case

    def _calculate_confidence_intervals(
        self, distributions: dict[str, list[Decimal]]
    ) -> dict[str, tuple[Decimal, Decimal]]:
        """Calculate confidence intervals for each metric.

        Args:
            distributions: Metric distributions

        Returns:
            Dictionary mapping metric name to (lower, upper) CI bounds
        """
        alpha = 1 - self.confidence_level
        lower_percentile = (alpha / 2) * 100
        upper_percentile = (1 - alpha / 2) * 100

        confidence_intervals = {}
        for metric_name, distribution in distributions.items():
            values = np.array([float(v) for v in distribution])

            ci_lower = np.percentile(values, lower_percentile)
            ci_upper = np.percentile(values, upper_percentile)

            confidence_intervals[metric_name] = (
                Decimal(str(ci_lower)),
                Decimal(str(ci_upper)),
            )

        return confidence_intervals
