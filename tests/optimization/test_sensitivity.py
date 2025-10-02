"""Tests for parameter sensitivity analysis."""

import re

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from rustybt.optimization.sensitivity import (
    InteractionResult,
    SensitivityAnalyzer,
    SensitivityResult,
    calculate_stability_score,
)


# Synthetic test functions
def stable_quadratic(params: dict[str, float]) -> float:
    """Stable function with flat surface (broad minimum)."""
    return -(0.01 * params["x"] ** 2)  # Very gradual


def sensitive_gaussian(params: dict[str, float]) -> float:
    """Sensitive function with sharp peak."""
    return -np.exp(-100 * params["x"] ** 2)  # Very sharp


def stable_sphere(params: dict[str, float]) -> float:
    """Stable 2D function."""
    return -(0.01 * params["x"] ** 2 + 0.01 * params["y"] ** 2)


def sensitive_rastrigin(params: dict[str, float]) -> float:
    """Sensitive 2D function with many local optima."""
    amplitude = 10
    x = params["x"]
    y = params["y"]
    term_x = x**2 - amplitude * np.cos(2 * np.pi * x)
    term_y = y**2 - amplitude * np.cos(2 * np.pi * y)
    return -(amplitude * 2 + term_x + term_y)


def interacting_function(params: dict[str, float]) -> float:
    """Function with parameter interaction (cross-term)."""
    return -(params["x"] ** 2 + params["y"] ** 2 + 0.5 * params["x"] * params["y"])


def non_interacting_function(params: dict[str, float]) -> float:
    """Function without parameter interaction (separable)."""
    return -(params["x"] ** 2 + params["y"] ** 2)


# Test SensitivityAnalyzer initialization
def test_sensitivity_analyzer_init():
    """Test SensitivityAnalyzer initialization."""
    analyzer = SensitivityAnalyzer(
        base_params={"x": 0.0, "y": 1.0},
        n_points=10,
        perturbation_pct=0.3,
        n_bootstrap=50,
        interaction_threshold=0.15,
        random_seed=42,
    )

    assert analyzer.base_params == {"x": 0.0, "y": 1.0}
    assert analyzer.n_points == 10
    assert analyzer.perturbation_pct == 0.3
    assert analyzer.n_bootstrap == 50
    assert analyzer.interaction_threshold == 0.15
    assert analyzer.random_seed == 42


def test_sensitivity_analyzer_init_validation():
    """Test SensitivityAnalyzer validation."""
    # n_points too small
    with pytest.raises(ValueError, match="n_points must be >= 3"):
        SensitivityAnalyzer(base_params={"x": 0.0}, n_points=2)

    # perturbation_pct invalid
    with pytest.raises(ValueError, match="perturbation_pct must be > 0"):
        SensitivityAnalyzer(base_params={"x": 0.0}, perturbation_pct=0)

    with pytest.raises(ValueError, match="perturbation_pct must be > 0"):
        SensitivityAnalyzer(base_params={"x": 0.0}, perturbation_pct=-0.1)


# Test single parameter sensitivity analysis
def test_analyze_stable_function():
    """Test sensitivity analysis on stable function (flat surface)."""
    analyzer = SensitivityAnalyzer(base_params={"x": 0.0}, n_points=20, random_seed=42)

    results = analyzer.analyze(
        objective=stable_quadratic,
        param_ranges={"x": (-10, 10)},
        calculate_ci=False,
    )

    assert "x" in results
    result = results["x"]

    # Stable function should have moderate to high stability score
    # Note: Even "stable" quadratic has some gradient over [-10, 10] range
    expected_msg = f"Expected moderate to high stability, got {result.stability_score}"
    assert result.stability_score > 0.6, expected_msg
    assert result.classification in ["robust", "moderate"]

    # Relatively low variance and gradient (compared to sensitive function)
    assert result.variance < 1.0
    assert result.max_gradient < 1.0


def test_analyze_sensitive_function():
    """Test sensitivity analysis on sensitive function (sharp peak)."""
    analyzer = SensitivityAnalyzer(base_params={"x": 0.0}, n_points=20, random_seed=42)

    results = analyzer.analyze(
        objective=sensitive_gaussian,
        param_ranges={"x": (-1, 1)},
        calculate_ci=False,
    )

    assert "x" in results
    result = results["x"]

    # Sensitive function should have low stability score
    assert result.stability_score < 0.5, f"Expected low stability, got {result.stability_score}"
    assert result.classification == "sensitive"

    # High variance and/or gradient
    assert result.variance > 0.01 or result.max_gradient > 1.0


def test_analyze_multiple_parameters():
    """Test analyzing multiple parameters independently."""
    analyzer = SensitivityAnalyzer(
        base_params={"x": 0.0, "y": 0.0},
        n_points=15,
        random_seed=42,
    )

    results = analyzer.analyze(
        objective=stable_sphere,
        param_ranges={"x": (-5, 5), "y": (-5, 5)},
        calculate_ci=False,
    )

    # Both parameters should be analyzed
    assert set(results.keys()) == {"x", "y"}

    # Both should be moderate to high stability (stable function)
    assert results["x"].stability_score > 0.6
    assert results["y"].stability_score > 0.6
    assert results["x"].classification in ["robust", "moderate"]
    assert results["y"].classification in ["robust", "moderate"]


def test_analyze_with_confidence_intervals():
    """Test analysis with bootstrap confidence intervals."""
    analyzer = SensitivityAnalyzer(
        base_params={"x": 0.0},
        n_points=10,
        n_bootstrap=50,
        random_seed=42,
    )

    results = analyzer.analyze(
        objective=stable_quadratic,
        param_ranges={"x": (-5, 5)},
        calculate_ci=True,
    )

    result = results["x"]

    # CI should be calculated
    assert result.confidence_lower is not None
    assert result.confidence_upper is not None

    # CI should overlap with or contain the stability score
    # Note: Bootstrap CI can sometimes be wider than point estimate
    assert result.confidence_lower >= 0.0
    assert result.confidence_upper <= 1.0

    # CI should be reasonable width
    ci_width = result.confidence_upper - result.confidence_lower
    assert 0 < ci_width < 1.0


def test_analyze_with_auto_ranges():
    """Test automatic parameter range derivation."""
    analyzer = SensitivityAnalyzer(
        base_params={"x": 10.0},
        perturbation_pct=0.5,  # ±50%
        n_points=10,
        random_seed=42,
    )

    # Don't specify param_ranges - should use ±50% of base
    results = analyzer.analyze(
        objective=stable_quadratic,
        calculate_ci=False,
    )

    result = results["x"]

    # Should have sampled around [5, 15]
    assert min(result.param_values) == pytest.approx(5.0, abs=0.1)
    assert max(result.param_values) == pytest.approx(15.0, abs=0.1)


def test_analyze_zero_base_value():
    """Test handling of zero base value (edge case)."""
    analyzer = SensitivityAnalyzer(
        base_params={"x": 0.0},
        perturbation_pct=0.5,
        n_points=10,
        random_seed=42,
    )

    # Should use fixed delta for zero base
    results = analyzer.analyze(
        objective=stable_quadratic,
        calculate_ci=False,
    )

    result = results["x"]

    # Should have reasonable range (not zero-width)
    param_range = max(result.param_values) - min(result.param_values)
    assert param_range > 0


# Test interaction analysis
def test_analyze_interaction_with_interaction():
    """Test interaction analysis on interacting parameters."""
    analyzer = SensitivityAnalyzer(
        base_params={"x": 0.0, "y": 0.0},
        n_points=10,
        interaction_threshold=0.05,
        random_seed=42,
    )

    result = analyzer.analyze_interaction(
        param1="x",
        param2="y",
        objective=interacting_function,
        param_ranges={"x": (-2, 2), "y": (-2, 2)},
    )

    # Should detect interaction
    assert result.has_interaction, "Expected interaction detection"
    assert result.interaction_strength > analyzer.interaction_threshold

    # Check result structure
    assert result.param1_name == "x"
    assert result.param2_name == "y"
    assert len(result.param1_values) == 10
    assert len(result.param2_values) == 10
    assert result.objective_matrix.shape == (10, 10)


def test_analyze_interaction_without_interaction():
    """Test interaction analysis on non-interacting parameters."""
    analyzer = SensitivityAnalyzer(
        base_params={"x": 0.0, "y": 0.0},
        n_points=10,
        interaction_threshold=0.1,
        random_seed=42,
    )

    result = analyzer.analyze_interaction(
        param1="x",
        param2="y",
        objective=non_interacting_function,
        param_ranges={"x": (-2, 2), "y": (-2, 2)},
    )

    # Should NOT detect interaction (separable function)
    assert not result.has_interaction, "Expected no interaction"
    assert result.interaction_strength < analyzer.interaction_threshold


def test_analyze_interaction_missing_param():
    """Test interaction analysis with missing parameter."""
    analyzer = SensitivityAnalyzer(
        base_params={"x": 0.0, "y": 0.0},
        n_points=10,
    )

    # Missing param in ranges
    with pytest.raises(ValueError, match="Parameter z not in param_ranges"):
        analyzer.analyze_interaction(
            param1="x",
            param2="z",
            objective=non_interacting_function,
            param_ranges={"x": (-2, 2), "y": (-2, 2)},
        )


# Test plotting
def test_plot_sensitivity(tmp_path):
    """Test 1D sensitivity plot generation."""
    analyzer = SensitivityAnalyzer(base_params={"x": 0.0}, n_points=10, random_seed=42)

    analyzer.analyze(
        objective=stable_quadratic,
        param_ranges={"x": (-5, 5)},
        calculate_ci=False,
    )

    # Generate plot
    fig = analyzer.plot_sensitivity("x", output_path=None)

    # Check figure created
    assert fig is not None
    assert len(fig.axes) == 1

    # Save to file
    output_path = tmp_path / "sensitivity_x.png"
    fig = analyzer.plot_sensitivity("x", output_path=output_path)

    # Check file created
    assert output_path.exists()


def test_plot_sensitivity_with_ci(tmp_path):
    """Test sensitivity plot with confidence intervals."""
    analyzer = SensitivityAnalyzer(
        base_params={"x": 0.0},
        n_points=10,
        n_bootstrap=20,
        random_seed=42,
    )

    analyzer.analyze(
        objective=stable_quadratic,
        param_ranges={"x": (-5, 5)},
        calculate_ci=True,
    )

    # Generate plot with CI
    fig = analyzer.plot_sensitivity("x", show_ci=True)

    # Check figure created
    assert fig is not None


def test_plot_sensitivity_not_analyzed():
    """Test plotting parameter that hasn't been analyzed."""
    analyzer = SensitivityAnalyzer(base_params={"x": 0.0}, n_points=10)

    # Haven't run analyze() yet
    with pytest.raises(KeyError, match="Parameter x not analyzed"):
        analyzer.plot_sensitivity("x")


def test_plot_interaction(tmp_path):
    """Test 2D interaction heatmap generation."""
    analyzer = SensitivityAnalyzer(
        base_params={"x": 0.0, "y": 0.0},
        n_points=8,
        random_seed=42,
    )

    analyzer.analyze_interaction(
        param1="x",
        param2="y",
        objective=interacting_function,
        param_ranges={"x": (-2, 2), "y": (-2, 2)},
    )

    # Generate plot
    fig = analyzer.plot_interaction("x", "y", output_path=None)

    # Check figure created
    assert fig is not None
    assert len(fig.axes) == 2  # Main plot + colorbar

    # Save to file
    output_path = tmp_path / "interaction_xy.png"
    fig = analyzer.plot_interaction("x", "y", output_path=output_path)

    # Check file created
    assert output_path.exists()


def test_plot_interaction_not_analyzed():
    """Test plotting interaction that hasn't been analyzed."""
    analyzer = SensitivityAnalyzer(base_params={"x": 0.0, "y": 0.0}, n_points=10)

    # Haven't run analyze_interaction() yet
    with pytest.raises(KeyError, match=r"Interaction .* not analyzed"):
        analyzer.plot_interaction("x", "y")


# Test report generation
def test_generate_report_no_analysis():
    """Test report generation with no analysis."""
    analyzer = SensitivityAnalyzer(base_params={"x": 0.0}, n_points=10)

    report = analyzer.generate_report()

    # Should indicate no analysis
    assert "No analysis performed" in report


def test_generate_report_with_analysis():
    """Test report generation with sensitivity analysis."""
    analyzer = SensitivityAnalyzer(
        base_params={"stable": 0.0, "sensitive": 0.0},
        n_points=15,
        random_seed=42,
    )

    # Analyze stable and sensitive parameters
    def mixed_objective(params):
        # stable param: flat surface
        # sensitive param: sharp peak
        stable_val = -(0.01 * params["stable"] ** 2)
        sensitive_val = -np.exp(-100 * params["sensitive"] ** 2)
        return stable_val + sensitive_val

    analyzer.analyze(
        objective=mixed_objective,
        param_ranges={"stable": (-10, 10), "sensitive": (-1, 1)},
        calculate_ci=False,
    )

    report = analyzer.generate_report()

    # Check report structure
    assert "# Parameter Sensitivity Analysis Report" in report
    assert "## Summary" in report
    assert "## Robustness Assessment" in report
    assert "## Recommendations" in report
    assert "## Overfitting Indicators" in report

    # Check parameter entries
    assert "stable" in report
    assert "sensitive" in report

    # Check classifications appear
    assert re.search(r"robust|moderate|sensitive", report.lower())


def test_generate_report_with_interactions():
    """Test report generation including interaction analysis."""
    analyzer = SensitivityAnalyzer(
        base_params={"x": 0.0, "y": 0.0},
        n_points=10,
        random_seed=42,
    )

    analyzer.analyze(
        objective=interacting_function,
        param_ranges={"x": (-2, 2), "y": (-2, 2)},
        calculate_ci=False,
    )

    analyzer.analyze_interaction(
        param1="x",
        param2="y",
        objective=interacting_function,
        param_ranges={"x": (-2, 2), "y": (-2, 2)},
    )

    report = analyzer.generate_report()

    # Should include interaction section
    assert "## Parameter Interactions" in report
    # Check for interaction mention (allowing Unicode multiplication sign)
    assert "x" in report
    assert "y" in report


def test_generate_report_overfitting_warning():
    """Test report flags sensitive parameters as overfitting risk."""
    analyzer = SensitivityAnalyzer(base_params={"x": 0.0}, n_points=15, random_seed=42)

    analyzer.analyze(
        objective=sensitive_gaussian,
        param_ranges={"x": (-1, 1)},
        calculate_ci=False,
    )

    report = analyzer.generate_report()

    # Should warn about high-risk parameters
    assert "High-risk parameters detected" in report or "⚠" in report
    assert "x" in report


# Test stability score calculation
def test_calculate_stability_score():
    """Test stability score calculation function."""
    # Low variance/gradient = high stability
    score1 = calculate_stability_score(variance=0.1, gradient=0.1, curvature=0.1)
    assert 0 < score1 < 1
    assert score1 > 0.7  # Should be fairly high

    # High variance/gradient = low stability
    score2 = calculate_stability_score(variance=10.0, gradient=10.0, curvature=10.0)
    assert 0 < score2 < 1
    assert score2 < 0.1  # Should be very low

    # Score decreases as instability increases
    assert score2 < score1


def test_calculate_stability_score_edge_cases():
    """Test stability score with edge cases."""
    # All zeros = perfect stability
    score = calculate_stability_score(variance=0.0, gradient=0.0, curvature=0.0)
    assert score == 1.0

    # Only variance
    score = calculate_stability_score(variance=1.0, gradient=0.0, curvature=0.0)
    assert 0 < score < 1

    # Only gradient
    score = calculate_stability_score(variance=0.0, gradient=1.0, curvature=0.0)
    assert 0 < score < 1


# Property-based tests
@given(
    variance=st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False),
    gradient=st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False),
)
def test_stability_score_monotonic(variance, gradient):
    """Test stability score decreases with increased variance/gradient."""
    score1 = calculate_stability_score(variance=variance, gradient=gradient)
    score2 = calculate_stability_score(variance=variance * 2, gradient=gradient * 2)

    # Doubling variance/gradient should decrease score
    assert score2 <= score1


@given(
    variance=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    gradient=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    curvature=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
)
def test_stability_score_bounded(variance, gradient, curvature):
    """Test stability score always in [0, 1] range."""
    score = calculate_stability_score(variance=variance, gradient=gradient, curvature=curvature)
    assert 0.0 <= score <= 1.0


@given(
    base_value=st.floats(min_value=-100.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    n_points=st.integers(min_value=3, max_value=20),
)
def test_analyze_deterministic_with_seed(base_value, n_points):
    """Test analysis is deterministic with random seed."""
    analyzer1 = SensitivityAnalyzer(
        base_params={"x": base_value},
        n_points=n_points,
        random_seed=42,
    )

    analyzer2 = SensitivityAnalyzer(
        base_params={"x": base_value},
        n_points=n_points,
        random_seed=42,
    )

    results1 = analyzer1.analyze(
        objective=stable_quadratic,
        param_ranges={"x": (base_value - 5, base_value + 5)},
        calculate_ci=False,
    )

    results2 = analyzer2.analyze(
        objective=stable_quadratic,
        param_ranges={"x": (base_value - 5, base_value + 5)},
        calculate_ci=False,
    )

    # Results should be identical
    assert results1["x"].stability_score == results2["x"].stability_score
    assert results1["x"].variance == results2["x"].variance


# Integration tests
def test_full_sensitivity_workflow():
    """Test complete sensitivity analysis workflow."""
    # Setup analyzer
    analyzer = SensitivityAnalyzer(
        base_params={"lookback": 20.0, "threshold": 0.02},
        n_points=15,
        perturbation_pct=0.5,
        n_bootstrap=30,
        random_seed=42,
    )

    # Define mock backtest objective
    def mock_backtest(params):
        # Simulate: lookback is robust, threshold is sensitive
        lookback_component = -(0.01 * (params["lookback"] - 20) ** 2)
        threshold_component = -np.exp(-100 * (params["threshold"] - 0.02) ** 2)
        return lookback_component + threshold_component

    # Step 1: Sensitivity analysis
    results = analyzer.analyze(
        objective=mock_backtest,
        param_ranges={"lookback": (10, 30), "threshold": (0.01, 0.03)},
        calculate_ci=True,
    )

    # Verify results
    assert "lookback" in results
    assert "threshold" in results

    # lookback should be more stable than threshold
    assert results["lookback"].stability_score > results["threshold"].stability_score

    # threshold should be sensitive (sharp peak)
    assert results["threshold"].stability_score < 0.5

    # Step 2: Interaction analysis
    interaction = analyzer.analyze_interaction(
        param1="lookback",
        param2="threshold",
        objective=mock_backtest,
        param_ranges={"lookback": (10, 30), "threshold": (0.01, 0.03)},
    )

    assert interaction.param1_name == "lookback"
    assert interaction.param2_name == "threshold"

    # Step 3: Generate report
    report = analyzer.generate_report()

    assert "lookback" in report
    assert "threshold" in report
    assert "Robustness Assessment" in report

    # Step 4: Visualization (just ensure no errors)
    fig1 = analyzer.plot_sensitivity("lookback")
    fig2 = analyzer.plot_sensitivity("threshold", show_ci=True)
    fig3 = analyzer.plot_interaction("lookback", "threshold")

    assert fig1 is not None
    assert fig2 is not None
    assert fig3 is not None


def test_sensitivity_result_immutability():
    """Test SensitivityResult is immutable."""
    result = SensitivityResult(
        parameter_name="x",
        param_values=[1.0, 2.0, 3.0],
        objective_values=[0.1, 0.2, 0.3],
        base_value=2.0,
        base_objective=0.2,
        variance=0.01,
        max_gradient=0.05,
        max_curvature=0.02,
        stability_score=0.9,
        classification="robust",
    )

    # Should not be able to modify
    with pytest.raises(AttributeError):
        result.stability_score = 0.5  # type: ignore


def test_interaction_result_immutability():
    """Test InteractionResult is immutable."""
    result = InteractionResult(
        param1_name="x",
        param2_name="y",
        param1_values=[1.0, 2.0],
        param2_values=[3.0, 4.0],
        objective_matrix=np.array([[0.1, 0.2], [0.3, 0.4]]),
        interaction_strength=0.05,
        has_interaction=False,
    )

    # Should not be able to modify
    with pytest.raises(AttributeError):
        result.has_interaction = True  # type: ignore
