"""Parameter sensitivity and stability analysis for strategy robustness."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from matplotlib.figure import Figure
from numpy.typing import NDArray
from sklearn.utils import resample


@dataclass(frozen=True)
class SensitivityResult:
    """Results for single parameter sensitivity analysis.

    Attributes:
        parameter_name: Name of analyzed parameter
        param_values: Tested parameter values
        objective_values: Objective function values at each param value
        base_value: Base (center) parameter value
        base_objective: Objective value at base parameter
        variance: Variance of objective across parameter range
        max_gradient: Maximum gradient (rate of change)
        max_curvature: Maximum curvature (convexity)
        stability_score: Composite stability metric (0-1, higher = more stable)
        classification: 'robust', 'moderate', or 'sensitive'
        confidence_lower: Lower bound of 95% CI for stability score (optional)
        confidence_upper: Upper bound of 95% CI for stability score (optional)
    """

    parameter_name: str
    param_values: list[float]
    objective_values: list[float]
    base_value: float
    base_objective: float
    variance: float
    max_gradient: float
    max_curvature: float
    stability_score: float
    classification: str
    confidence_lower: float | None = None
    confidence_upper: float | None = None


@dataclass(frozen=True)
class InteractionResult:
    """Results for parameter interaction analysis.

    Attributes:
        param1_name: First parameter name
        param2_name: Second parameter name
        param1_values: Tested values for param1
        param2_values: Tested values for param2
        objective_matrix: 2D array of objective values [param1, param2]
        interaction_strength: Magnitude of parameter interaction
        has_interaction: True if parameters interact significantly
    """

    param1_name: str
    param2_name: str
    param1_values: list[float]
    param2_values: list[float]
    objective_matrix: NDArray[np.floating[Any]]
    interaction_strength: float
    has_interaction: bool


class SensitivityAnalyzer:
    """Parameter sensitivity and stability analysis for strategy robustness.

    Identifies robust parameters (flat performance surface) vs. sensitive
    parameters (sharp performance cliffs). Detects parameter interactions.

    Best for:
        - Validating optimization results
        - Identifying overfitting to specific parameter values
        - Understanding parameter importance
        - Selecting robust parameter regions

    Args:
        base_params: Center point for sensitivity analysis
        n_points: Points to sample per parameter (default: 20)
        perturbation_pct: Range to vary params as % of base (default: 0.5 = ±50%)
        n_bootstrap: Bootstrap iterations for confidence intervals (default: 100)
        interaction_threshold: Threshold for detecting interactions (default: 0.1)
        random_seed: Random seed for reproducibility (default: None)

    Example:
        >>> analyzer = SensitivityAnalyzer(
        ...     base_params={'lookback': 20, 'threshold': 0.02},
        ...     n_points=20,
        ...     perturbation_pct=0.5
        ... )
        >>> results = analyzer.analyze(
        ...     objective=run_backtest,
        ...     param_ranges={'lookback': (10, 30), 'threshold': (0.01, 0.05)}
        ... )
        >>> print(results['lookback'].stability_score)  # 0.85 (robust)
        >>> print(results['threshold'].stability_score) # 0.45 (sensitive)
        >>> analyzer.plot_sensitivity('lookback')
        >>> analyzer.plot_interaction('lookback', 'threshold')
        >>> report = analyzer.generate_report()
    """

    def __init__(
        self,
        base_params: dict[str, float],
        n_points: int = 20,
        perturbation_pct: float = 0.5,
        n_bootstrap: int = 100,
        interaction_threshold: float = 0.1,
        random_seed: int | None = None,
    ) -> None:
        """Initialize sensitivity analyzer.

        Args:
            base_params: Center point for sensitivity analysis
            n_points: Points to sample per parameter
            perturbation_pct: Range to vary params as % of base (±X%)
            n_bootstrap: Bootstrap iterations for confidence intervals
            interaction_threshold: Threshold for detecting interactions
            random_seed: Random seed for reproducibility

        Raises:
            ValueError: If n_points < 3 or perturbation_pct <= 0
        """
        if n_points < 3:
            raise ValueError(f"n_points must be >= 3, got {n_points}")
        if perturbation_pct <= 0:
            raise ValueError(f"perturbation_pct must be > 0, got {perturbation_pct}")

        self.base_params = base_params
        self.n_points = n_points
        self.perturbation_pct = perturbation_pct
        self.n_bootstrap = n_bootstrap
        self.interaction_threshold = interaction_threshold
        self.random_seed = random_seed

        # Storage for results
        self._sensitivity_results: dict[str, SensitivityResult] = {}
        self._interaction_results: dict[tuple[str, str], InteractionResult] = {}

        # Random state for bootstrap
        self._rng = np.random.default_rng(random_seed)

    def analyze(
        self,
        objective: Callable[[dict[str, float]], float],
        param_ranges: dict[str, tuple[float, float]] | None = None,
        calculate_ci: bool = True,
    ) -> dict[str, SensitivityResult]:
        """Perform sensitivity analysis on all parameters.

        Args:
            objective: Objective function taking params dict, returning scalar
            param_ranges: Optional explicit ranges (min, max) per parameter.
                         If None, uses ±perturbation_pct around base_params
            calculate_ci: Whether to calculate confidence intervals (slower)

        Returns:
            Dictionary mapping parameter name to SensitivityResult

        Example:
            >>> def objective(params):
            ...     return -params['x']**2  # Quadratic function
            >>> analyzer = SensitivityAnalyzer(base_params={'x': 0.0})
            >>> results = analyzer.analyze(objective)
            >>> results['x'].stability_score  # High (stable function)
        """
        # Determine parameter ranges
        ranges = self._get_param_ranges(param_ranges)

        # Analyze each parameter independently
        for param_name, (min_val, max_val) in ranges.items():
            result = self._analyze_single_parameter(
                param_name=param_name,
                objective=objective,
                min_val=min_val,
                max_val=max_val,
                calculate_ci=calculate_ci,
            )
            self._sensitivity_results[param_name] = result

        return self._sensitivity_results

    def analyze_interaction(
        self,
        param1: str,
        param2: str,
        objective: Callable[[dict[str, float]], float],
        param_ranges: dict[str, tuple[float, float]] | None = None,
    ) -> InteractionResult:
        """Analyze interaction between two parameters.

        Args:
            param1: First parameter name
            param2: Second parameter name
            objective: Objective function
            param_ranges: Optional explicit ranges per parameter

        Returns:
            InteractionResult with 2D performance surface

        Example:
            >>> result = analyzer.analyze_interaction('lookback', 'threshold', objective)
            >>> if result.has_interaction:
            ...     print("Parameters interact - optimize jointly")
        """
        # Get parameter ranges
        ranges = self._get_param_ranges(param_ranges)

        if param1 not in ranges:
            raise ValueError(f"Parameter {param1} not in param_ranges")
        if param2 not in ranges:
            raise ValueError(f"Parameter {param2} not in param_ranges")

        # Create 2D grid
        param1_values = np.linspace(*ranges[param1], self.n_points)
        param2_values = np.linspace(*ranges[param2], self.n_points)

        # Evaluate objective on grid
        objective_matrix = np.zeros((len(param1_values), len(param2_values)))
        for i, p1_val in enumerate(param1_values):
            for j, p2_val in enumerate(param2_values):
                params = self.base_params.copy()
                params[param1] = p1_val
                params[param2] = p2_val
                objective_matrix[i, j] = objective(params)

        # Calculate interaction strength (cross-derivative)
        # ∂²f/∂x∂y measures non-separability
        grad_x = np.gradient(objective_matrix, axis=0)
        cross_deriv = np.gradient(grad_x, axis=1)
        interaction_strength = float(np.mean(np.abs(cross_deriv)))

        # Detect interaction
        has_interaction = interaction_strength > self.interaction_threshold

        result = InteractionResult(
            param1_name=param1,
            param2_name=param2,
            param1_values=param1_values.tolist(),
            param2_values=param2_values.tolist(),
            objective_matrix=objective_matrix,
            interaction_strength=interaction_strength,
            has_interaction=has_interaction,
        )

        # Store result
        self._interaction_results[(param1, param2)] = result

        return result

    def plot_sensitivity(
        self,
        parameter_name: str,
        output_path: Path | str | None = None,
        show_ci: bool = True,
    ) -> Figure:
        """Plot 1D sensitivity curve for parameter.

        Args:
            parameter_name: Parameter to plot
            output_path: Optional path to save figure
            show_ci: Whether to show confidence intervals

        Returns:
            Matplotlib Figure object

        Raises:
            KeyError: If parameter not analyzed yet
        """
        if parameter_name not in self._sensitivity_results:
            raise KeyError(f"Parameter {parameter_name} not analyzed. Run analyze() first.")

        result = self._sensitivity_results[parameter_name]

        fig, ax = plt.subplots(figsize=(10, 6))

        # Plot objective vs parameter
        ax.plot(result.param_values, result.objective_values, "b-", linewidth=2, label="Objective")

        # Mark base value
        ax.axvline(
            result.base_value,
            color="r",
            linestyle="--",
            linewidth=2,
            label=f"Base ({result.base_value:.4g})",
        )
        ax.plot(result.base_value, result.base_objective, "ro", markersize=10)

        # Show confidence intervals if available
        if show_ci and result.confidence_lower is not None and result.confidence_upper is not None:
            # Create confidence band (conceptual - would need full bootstrap data)
            # For now, just show stability score CI in text
            ci_text = (
                f"Stability: {result.stability_score:.3f} "
                f"[{result.confidence_lower:.3f}, {result.confidence_upper:.3f}]"
            )
            ax.text(
                0.02,
                0.98,
                ci_text,
                transform=ax.transAxes,
                verticalalignment="top",
                bbox={"boxstyle": "round", "facecolor": "wheat"},
            )

        # Labels and title
        ax.set_xlabel(f"{parameter_name} Value", fontsize=12)
        ax.set_ylabel("Objective Function", fontsize=12)
        ax.set_title(
            f"Sensitivity Analysis: {parameter_name}\n"
            f"Stability: {result.stability_score:.3f} ({result.classification})",
            fontsize=14,
        )
        ax.legend()
        ax.grid(True, alpha=0.3)

        plt.tight_layout()

        if output_path:
            fig.savefig(output_path, dpi=150, bbox_inches="tight")

        return fig

    def plot_interaction(
        self,
        param1: str,
        param2: str,
        output_path: Path | str | None = None,
    ) -> Figure:
        """Plot 2D interaction heatmap.

        Args:
            param1: First parameter name
            param2: Second parameter name
            output_path: Optional path to save figure

        Returns:
            Matplotlib Figure object

        Raises:
            KeyError: If interaction not analyzed yet
        """
        key = (param1, param2)
        if key not in self._interaction_results:
            raise KeyError(
                f"Interaction {param1}×{param2} not analyzed. "  # noqa: RUF001
                f"Run analyze_interaction() first."
            )

        result = self._interaction_results[key]

        fig, ax = plt.subplots(figsize=(10, 8))

        # Create heatmap
        sns.heatmap(
            result.objective_matrix,
            xticklabels=np.round(result.param2_values, 3),
            yticklabels=np.round(result.param1_values, 3),
            cmap="viridis",
            cbar_kws={"label": "Objective Function"},
            ax=ax,
        )

        # Mark base values
        base_idx1 = np.argmin(np.abs(np.array(result.param1_values) - self.base_params[param1]))
        base_idx2 = np.argmin(np.abs(np.array(result.param2_values) - self.base_params[param2]))
        ax.plot(base_idx2 + 0.5, base_idx1 + 0.5, "r*", markersize=20, label="Base")

        # Labels and title
        ax.set_xlabel(f"{param2} Value", fontsize=12)
        ax.set_ylabel(f"{param1} Value", fontsize=12)

        interaction_status = "Interaction Detected" if result.has_interaction else "No Interaction"
        ax.set_title(
            f"Interaction Analysis: {param1} × {param2}\n"  # noqa: RUF001
            f"{interaction_status} (strength: {result.interaction_strength:.4f})",
            fontsize=14,
        )

        plt.tight_layout()

        if output_path:
            fig.savefig(output_path, dpi=150, bbox_inches="tight")

        return fig

    def generate_report(self) -> str:
        """Generate markdown report with recommendations.

        Returns:
            Markdown-formatted report string

        Example:
            >>> report = analyzer.generate_report()
            >>> with open('sensitivity_report.md', 'w') as f:
            ...     f.write(report)
        """
        if not self._sensitivity_results:
            return (
                "# Sensitivity Analysis Report\n\nNo analysis performed yet. Run analyze() first."
            )

        lines = [
            "# Parameter Sensitivity Analysis Report",
            "",
            "## Summary",
            "",
            "| Parameter | Base Value | Stability Score | Classification | Recommendation |",
            "|-----------|------------|-----------------|----------------|----------------|",
        ]

        # Add parameter rows
        robust_count = 0
        total_count = len(self._sensitivity_results)

        for param_name, result in sorted(self._sensitivity_results.items()):
            if result.classification == "robust":
                recommendation = "✓ Safe to use"
                robust_count += 1
            else:
                recommendation = "⚠ Use caution"

            lines.append(
                f"| {param_name} | {result.base_value:.4g} | "
                f"{result.stability_score:.3f} | {result.classification.capitalize()} | "
                f"{recommendation} |"
            )

        # Robustness assessment
        lines.extend(
            [
                "",
                "## Robustness Assessment",
                "",
            ]
        )

        robustness_pct = (robust_count / total_count * 100) if total_count > 0 else 0
        if robustness_pct >= 80:
            assessment = "**Excellent**"
        elif robustness_pct >= 60:
            assessment = "**Good**"
        elif robustness_pct >= 40:
            assessment = "**Moderate**"
        else:
            assessment = "**Poor**"

        lines.append(
            f"Overall strategy robustness: {assessment} "
            f"({robust_count}/{total_count} parameters robust)"
        )
        lines.append("")

        # Detailed recommendations
        lines.extend(
            [
                "## Recommendations",
                "",
            ]
        )

        for i, (param_name, result) in enumerate(sorted(self._sensitivity_results.items()), 1):
            if result.classification == "robust":
                pct = self.perturbation_pct * 100
                range_desc = f"performance stable across ±{pct:.0f}% range"
                lines.append(
                    f"{i}. **{param_name}={result.base_value:.4g}**: Robust parameter, {range_desc}"
                )
            elif result.classification == "moderate":
                lines.append(
                    f"{i}. **{param_name}={result.base_value:.4g}**: Moderately stable, "
                    f"monitor performance if parameter changes"
                )
            else:  # sensitive
                lines.append(
                    f"{i}. **{param_name}={result.base_value:.4g}**: Sensitive parameter, "
                    f"consider widening search or using more stable alternative"
                )

        # Interaction analysis
        if self._interaction_results:
            lines.extend(
                [
                    "",
                    "## Parameter Interactions",
                    "",
                ]
            )

            for (param1, param2), result in sorted(self._interaction_results.items()):
                if result.has_interaction:
                    lines.append(
                        f"- **{param1} × {param2}**: Interaction detected "  # noqa: RUF001
                        f"(strength: {result.interaction_strength:.3f})"
                    )
                    lines.append("  → Optimize jointly, not independently")
                else:
                    lines.append(
                        f"- **{param1} × {param2}**: No interaction "  # noqa: RUF001
                        f"(strength: {result.interaction_strength:.3f})"
                    )
                    lines.append("  → Can optimize independently")

        # Overfitting indicators
        lines.extend(
            [
                "",
                "## Overfitting Indicators",
                "",
            ]
        )

        sensitive_params = [
            name
            for name, result in self._sensitivity_results.items()
            if result.classification == "sensitive"
        ]

        if sensitive_params:
            lines.append("⚠️ **High-risk parameters detected:**")
            lines.append("")
            for param in sensitive_params:
                result = self._sensitivity_results[param]
                lines.append(
                    f"- **{param}**: High sensitivity (score: {result.stability_score:.3f})"
                )
                lines.append(f"  - Variance: {result.variance:.4f}")
                lines.append(f"  - Max gradient: {result.max_gradient:.4f}")
                lines.append(f"  - Max curvature: {result.max_curvature:.4f}")
            lines.append("")
            lines.append("**Recommendation**: These parameters may be overfit. Consider:")
            lines.append("1. Using parameters from stable regions instead")
            lines.append("2. Widening parameter search space")
            lines.append("3. Adding regularization to optimization")
            lines.append("4. Performing walk-forward validation")
        else:
            lines.append("✅ No significant overfitting indicators detected.")

        return "\n".join(lines)

    def _get_param_ranges(
        self,
        param_ranges: dict[str, tuple[float, float]] | None,
    ) -> dict[str, tuple[float, float]]:
        """Get parameter ranges (explicit or derived from base_params).

        Args:
            param_ranges: Optional explicit ranges

        Returns:
            Dictionary mapping parameter name to (min, max)
        """
        if param_ranges is not None:
            return param_ranges

        # Derive from base_params using perturbation_pct
        ranges = {}
        for param_name, base_value in self.base_params.items():
            # Handle zero base values
            delta = 1.0 if base_value == 0 else abs(base_value * self.perturbation_pct)

            ranges[param_name] = (base_value - delta, base_value + delta)

        return ranges

    def _analyze_single_parameter(
        self,
        param_name: str,
        objective: Callable[[dict[str, float]], float],
        min_val: float,
        max_val: float,
        calculate_ci: bool,
    ) -> SensitivityResult:
        """Analyze sensitivity for single parameter.

        Args:
            param_name: Parameter to analyze
            objective: Objective function
            min_val: Minimum parameter value
            max_val: Maximum parameter value
            calculate_ci: Whether to calculate confidence intervals

        Returns:
            SensitivityResult for parameter
        """
        # Sample parameter values
        param_values = np.linspace(min_val, max_val, self.n_points)

        # Evaluate objective at each value
        objective_values = []
        for param_val in param_values:
            params = self.base_params.copy()
            params[param_name] = float(param_val)
            obj_val = objective(params)
            objective_values.append(obj_val)

        objective_values_array = np.array(objective_values)

        # Find base value and objective
        base_value = self.base_params[param_name]
        base_idx = np.argmin(np.abs(param_values - base_value))
        base_objective = objective_values[base_idx]

        # Calculate stability metrics
        variance = float(np.var(objective_values_array))

        # Gradient (rate of change)
        gradient = np.gradient(objective_values_array, param_values)
        max_gradient = float(np.max(np.abs(gradient)))

        # Curvature (second derivative)
        curvature = np.gradient(gradient, param_values)
        max_curvature = float(np.max(np.abs(curvature)))

        # Stability score (0-1, higher = more stable)
        # Use raw metrics - no normalization needed
        instability = variance + max_gradient + max_curvature
        stability_score = float(1 / (1 + instability))

        # Classify parameter
        if stability_score > 0.8:
            classification = "robust"
        elif stability_score > 0.5:
            classification = "moderate"
        else:
            classification = "sensitive"

        # Calculate confidence intervals via bootstrap
        confidence_lower = None
        confidence_upper = None
        if calculate_ci:
            confidence_lower, confidence_upper = self._bootstrap_confidence_interval(
                param_values=param_values,
                objective_values=objective_values_array,
            )

        return SensitivityResult(
            parameter_name=param_name,
            param_values=param_values.tolist(),
            objective_values=objective_values,
            base_value=base_value,
            base_objective=base_objective,
            variance=variance,
            max_gradient=max_gradient,
            max_curvature=max_curvature,
            stability_score=stability_score,
            classification=classification,
            confidence_lower=confidence_lower,
            confidence_upper=confidence_upper,
        )

    def _bootstrap_confidence_interval(
        self,
        param_values: NDArray[np.floating[Any]],
        objective_values: NDArray[np.floating[Any]],
    ) -> tuple[float, float]:
        """Calculate bootstrap confidence interval for stability score.

        Args:
            param_values: Parameter values
            objective_values: Objective values

        Returns:
            Tuple of (lower_bound, upper_bound) for 95% CI
        """
        stability_scores = []

        for _ in range(self.n_bootstrap):
            # Resample objective values
            resampled_objectives = resample(
                objective_values,
                replace=True,
                n_samples=len(objective_values),
                random_state=self._rng.integers(0, 2**31),
            )

            # Recalculate stability metrics
            variance = float(np.var(resampled_objectives))
            gradient = np.gradient(resampled_objectives, param_values)
            max_gradient = float(np.max(np.abs(gradient)))
            curvature = np.gradient(gradient, param_values)
            max_curvature = float(np.max(np.abs(curvature)))

            # Stability score
            instability = variance + max_gradient + max_curvature
            stability_score = float(1 / (1 + instability))
            stability_scores.append(stability_score)

        # 95% confidence interval
        lower = float(np.percentile(stability_scores, 2.5))
        upper = float(np.percentile(stability_scores, 97.5))

        return lower, upper


def calculate_stability_score(
    variance: float,
    gradient: float,
    curvature: float = 0.0,
) -> float:
    """Calculate stability score from metrics.

    Args:
        variance: Variance of objective across parameter range
        gradient: Maximum gradient (rate of change)
        curvature: Maximum curvature (convexity)

    Returns:
        Stability score (0-1, higher = more stable)

    Example:
        >>> score = calculate_stability_score(variance=0.1, gradient=0.5, curvature=0.2)
        >>> score > 0.5  # Moderately stable
        True
    """
    instability = variance + gradient + curvature
    return float(1 / (1 + instability))
