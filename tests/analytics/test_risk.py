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
Tests for risk analytics.

Test coverage:
- Unit tests for VaR calculations (parametric, historical, Monte Carlo)
- Unit tests for CVaR calculations
- Unit tests for stress testing
- Unit tests for tail risk metrics
- Unit tests for beta analysis
- Property tests: CVaR >= VaR, VaR relationships
- Integration tests with synthetic backtest data
- Edge case handling (insufficient data, missing benchmark, etc.)
"""

from decimal import Decimal

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from rustybt.analytics.risk import InsufficientDataError, RiskAnalytics

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_returns():
    """Create sample portfolio returns data."""
    np.random.seed(42)  # Set seed for reproducibility
    dates = pd.date_range(start="2023-01-01", periods=252, freq="D")
    returns = np.random.normal(0.001, 0.02, 252)  # 0.1% mean, 2% std

    # Create DataFrame
    returns_series = pd.Series(returns, index=dates)
    portfolio_value = (1 + returns_series).cumprod() * 100000

    df = pd.DataFrame({"portfolio_value": portfolio_value, "returns": returns_series}, index=dates)

    return df


@pytest.fixture
def sample_benchmark_returns():
    """Create sample benchmark returns."""
    np.random.seed(43)  # Set seed for reproducibility
    dates = pd.date_range(start="2023-01-01", periods=252, freq="D")
    returns = np.random.normal(0.0005, 0.015, 252)  # 0.05% mean, 1.5% std
    return pd.Series(returns, index=dates, name="benchmark")


@pytest.fixture
def synthetic_normal_returns():
    """Create synthetic returns from normal distribution."""
    np.random.seed(100)
    dates = pd.date_range(start="2023-01-01", periods=1000, freq="D")
    returns = np.random.normal(0, 0.01, 1000)  # Mean 0, std 1%

    df = pd.DataFrame({"returns": returns}, index=dates)
    return df


@pytest.fixture
def synthetic_skewed_returns():
    """Create synthetic returns with negative skew (fat left tail)."""
    np.random.seed(101)
    dates = pd.date_range(start="2023-01-01", periods=1000, freq="D")

    # Use exponential distribution and flip to get left skew
    returns = -np.random.exponential(0.01, 1000) + 0.001

    df = pd.DataFrame({"returns": returns}, index=dates)
    return df


@pytest.fixture
def sample_positions():
    """Create sample positions data for risk decomposition."""
    np.random.seed(102)
    dates = pd.date_range(start="2023-01-01", periods=100, freq="D")

    # Create sample positions for 3 assets
    spy_returns = np.random.normal(0.001, 0.02, 100)
    tlt_returns = np.random.normal(0.0005, 0.01, 100)
    gld_returns = np.random.normal(0.0003, 0.015, 100)

    df = pd.DataFrame(
        {
            "SPY_returns": spy_returns,
            "TLT_returns": tlt_returns,
            "GLD_returns": gld_returns,
        },
        index=dates,
    )

    return df


# ============================================================================
# Unit Tests: Initialization and Validation
# ============================================================================


def test_initialization_with_returns(sample_returns):
    """Test initialization with returns column."""
    risk = RiskAnalytics(sample_returns)

    assert risk.data is not None
    assert isinstance(risk.data, pd.DataFrame)
    assert len(risk.returns) > 0
    assert risk.confidence_levels == [0.95, 0.99]


def test_initialization_with_portfolio_value_only(sample_returns):
    """Test initialization calculates returns from portfolio_value."""
    df_without_returns = sample_returns[["portfolio_value"]].copy()

    risk = RiskAnalytics(df_without_returns)

    assert "returns" not in df_without_returns.columns
    assert len(risk.returns) > 0
    # Returns should be one less than portfolio values (due to pct_change)
    assert len(risk.returns) == len(df_without_returns) - 1


def test_initialization_with_custom_confidence_levels(sample_returns):
    """Test initialization with custom confidence levels."""
    risk = RiskAnalytics(sample_returns, confidence_levels=[0.90, 0.95, 0.99])

    assert risk.confidence_levels == [0.90, 0.95, 0.99]


def test_initialization_with_benchmark(sample_returns, sample_benchmark_returns):
    """Test initialization with benchmark returns."""
    risk = RiskAnalytics(sample_returns, benchmark_returns=sample_benchmark_returns)

    assert risk.benchmark_returns is not None
    assert len(risk.benchmark_returns) > 0


def test_initialization_insufficient_data():
    """Test that insufficient data raises error."""
    # Create DataFrame with only 20 observations (< 30 minimum)
    dates = pd.date_range(start="2023-01-01", periods=20, freq="D")
    returns = np.random.normal(0, 0.01, 20)
    df = pd.DataFrame({"returns": returns}, index=dates)

    with pytest.raises(InsufficientDataError, match="Insufficient data for risk analysis"):
        RiskAnalytics(df)


def test_initialization_missing_columns():
    """Test that missing required columns raises error."""
    # Create DataFrame without returns or portfolio_value
    dates = pd.date_range(start="2023-01-01", periods=100, freq="D")
    df = pd.DataFrame({"other_column": np.random.normal(0, 1, 100)}, index=dates)

    with pytest.raises(InsufficientDataError, match="must contain 'returns' or 'portfolio_value'"):
        RiskAnalytics(df)


# ============================================================================
# Unit Tests: VaR Calculations
# ============================================================================


def test_var_parametric(synthetic_normal_returns):
    """Test parametric VaR calculation."""
    risk = RiskAnalytics(synthetic_normal_returns, confidence_levels=[0.95])

    var_results = risk.calculate_var(method="parametric")

    assert "var_95" in var_results
    assert isinstance(var_results["var_95"], Decimal)
    # VaR should be negative (loss)
    assert float(var_results["var_95"]) < 0


def test_var_historical(synthetic_normal_returns):
    """Test historical VaR calculation."""
    risk = RiskAnalytics(synthetic_normal_returns, confidence_levels=[0.95])

    var_results = risk.calculate_var(method="historical")

    assert "var_95" in var_results
    assert isinstance(var_results["var_95"], Decimal)
    # VaR should be negative (loss)
    assert float(var_results["var_95"]) < 0


def test_var_montecarlo(synthetic_normal_returns):
    """Test Monte Carlo VaR calculation."""
    risk = RiskAnalytics(synthetic_normal_returns, confidence_levels=[0.95])

    var_results = risk.calculate_var(method="montecarlo")

    assert "var_95" in var_results
    assert isinstance(var_results["var_95"], Decimal)
    # VaR should be negative (loss)
    assert float(var_results["var_95"]) < 0


def test_var_multiple_confidence_levels(synthetic_normal_returns):
    """Test VaR at multiple confidence levels."""
    risk = RiskAnalytics(synthetic_normal_returns, confidence_levels=[0.90, 0.95, 0.99])

    var_results = risk.calculate_var(method="historical")

    assert "var_90" in var_results
    assert "var_95" in var_results
    assert "var_99" in var_results

    # Higher confidence should have larger VaR (more negative)
    assert float(var_results["var_99"]) <= float(var_results["var_95"])
    assert float(var_results["var_95"]) <= float(var_results["var_90"])


def test_var_invalid_method(synthetic_normal_returns):
    """Test that invalid VaR method raises error."""
    risk = RiskAnalytics(synthetic_normal_returns)

    with pytest.raises(ValueError, match="Unknown VaR method"):
        risk.calculate_var(method="invalid_method")


# ============================================================================
# Unit Tests: CVaR Calculations
# ============================================================================


def test_cvar_calculation(synthetic_normal_returns):
    """Test CVaR calculation."""
    risk = RiskAnalytics(synthetic_normal_returns, confidence_levels=[0.95])

    cvar_results = risk.calculate_cvar(method="historical")

    assert "cvar_95" in cvar_results
    assert isinstance(cvar_results["cvar_95"], Decimal)
    # CVaR should be negative (loss)
    assert float(cvar_results["cvar_95"]) < 0


def test_cvar_greater_than_var(synthetic_normal_returns):
    """Test that CVaR >= VaR (property test - CVaR is more conservative)."""
    risk = RiskAnalytics(synthetic_normal_returns, confidence_levels=[0.95, 0.99])

    var_results = risk.calculate_var(method="historical")
    cvar_results = risk.calculate_cvar(method="historical")

    # CVaR should be <= VaR (more negative = larger loss)
    assert float(cvar_results["cvar_95"]) <= float(var_results["var_95"])
    assert float(cvar_results["cvar_99"]) <= float(var_results["var_99"])


def test_cvar_with_different_methods(synthetic_normal_returns):
    """Test CVaR with different VaR methods."""
    risk = RiskAnalytics(synthetic_normal_returns, confidence_levels=[0.95])

    cvar_parametric = risk.calculate_cvar(method="parametric")
    cvar_historical = risk.calculate_cvar(method="historical")
    cvar_montecarlo = risk.calculate_cvar(method="montecarlo")

    assert "cvar_95" in cvar_parametric
    assert "cvar_95" in cvar_historical
    assert "cvar_95" in cvar_montecarlo


# ============================================================================
# Unit Tests: Stress Testing
# ============================================================================


def test_stress_tests(sample_returns):
    """Test stress testing with predefined scenarios."""
    risk = RiskAnalytics(sample_returns)

    stress_results = risk.run_stress_tests()

    # Should have all predefined scenarios
    assert "2008_financial_crisis" in stress_results
    assert "covid_crash" in stress_results
    assert "flash_crash" in stress_results

    # All should be losses (negative)
    for _scenario, loss in stress_results.items():
        assert isinstance(loss, Decimal)
        assert float(loss) < 0  # Should be negative (loss)


def test_stress_test_applies_correct_shocks(sample_returns):
    """Test that stress tests apply correct shock magnitudes."""
    risk = RiskAnalytics(sample_returns)

    stress_results = risk.run_stress_tests()

    # 2008 crisis should be worst (50% drop)
    # COVID should be moderate (35% drop)
    # Flash crash should be smallest (10% drop)
    loss_2008 = abs(float(stress_results["2008_financial_crisis"]))
    loss_covid = abs(float(stress_results["covid_crash"]))
    loss_flash = abs(float(stress_results["flash_crash"]))

    assert loss_2008 > loss_covid > loss_flash


# ============================================================================
# Unit Tests: Scenario Analysis
# ============================================================================


def test_scenario_analysis_requires_positions(sample_returns):
    """Test that scenario analysis requires positions data."""
    risk = RiskAnalytics(sample_returns)

    scenario = {"SPY": -0.20, "TLT": 0.10}

    with pytest.raises(ValueError, match="Positions data required"):
        risk.apply_scenario(scenario)


def test_scenario_analysis_with_positions(sample_returns, sample_positions):
    """Test scenario analysis with positions data."""
    # Add position values to positions DataFrame
    sample_positions["symbol"] = "SPY"
    sample_positions["value"] = 50000

    risk = RiskAnalytics(sample_returns, positions=sample_positions)

    scenario = {"SPY": -0.20}
    loss = risk.apply_scenario(scenario)

    assert isinstance(loss, Decimal)
    assert float(loss) < 0  # Should be negative (loss)


# ============================================================================
# Unit Tests: Correlation Analysis
# ============================================================================


def test_correlation_requires_positions(sample_returns):
    """Test that correlation analysis requires positions data."""
    risk = RiskAnalytics(sample_returns)

    with pytest.raises(ValueError, match="Positions data required"):
        risk.calculate_correlation()


def test_correlation_matrix(sample_returns, sample_positions):
    """Test correlation matrix calculation."""
    risk = RiskAnalytics(sample_returns, positions=sample_positions)

    correlation_matrix = risk.calculate_correlation()

    assert isinstance(correlation_matrix, pd.DataFrame)
    # Diagonal should be 1.0 (perfect correlation with self)
    for col in correlation_matrix.columns:
        if col in correlation_matrix.index:
            assert abs(correlation_matrix.loc[col, col] - 1.0) < 0.01


# ============================================================================
# Unit Tests: Beta Analysis
# ============================================================================


def test_beta_requires_benchmark(sample_returns):
    """Test that beta calculation requires benchmark."""
    risk = RiskAnalytics(sample_returns)

    with pytest.raises(ValueError, match="Benchmark returns required"):
        risk.calculate_beta()


def test_beta_calculation(sample_returns, sample_benchmark_returns):
    """Test beta calculation with benchmark."""
    risk = RiskAnalytics(sample_returns, benchmark_returns=sample_benchmark_returns)

    beta_results = risk.calculate_beta()

    assert "beta" in beta_results
    assert "alpha" in beta_results
    assert "r_squared" in beta_results

    assert isinstance(beta_results["beta"], Decimal)
    assert isinstance(beta_results["alpha"], Decimal)
    assert isinstance(beta_results["r_squared"], Decimal)

    # R-squared should be between 0 and 1
    assert 0 <= float(beta_results["r_squared"]) <= 1


def test_beta_with_known_values():
    """Test beta calculation with known relationship."""
    np.random.seed(200)
    dates = pd.date_range(start="2023-01-01", periods=252, freq="D")

    # Create portfolio with beta = 1.5
    true_beta = 1.5
    true_alpha = 0.0005

    benchmark = np.random.normal(0.001, 0.02, 252)
    portfolio = true_alpha + true_beta * benchmark + np.random.normal(0, 0.005, 252)

    portfolio_df = pd.DataFrame({"returns": portfolio}, index=dates)
    benchmark_series = pd.Series(benchmark, index=dates)

    risk = RiskAnalytics(portfolio_df, benchmark_returns=benchmark_series)
    beta_results = risk.calculate_beta()

    # Beta should be close to 1.5 (within tolerance due to noise)
    assert abs(float(beta_results["beta"]) - true_beta) < 0.2


# ============================================================================
# Unit Tests: Tail Risk Metrics
# ============================================================================


def test_tail_risk_metrics(synthetic_normal_returns):
    """Test tail risk metrics calculation."""
    risk = RiskAnalytics(synthetic_normal_returns)

    tail_risk = risk.calculate_tail_risk()

    assert "skewness" in tail_risk
    assert "kurtosis" in tail_risk
    assert "max_loss_1d" in tail_risk
    assert "max_loss_5d" in tail_risk
    assert "max_loss_10d" in tail_risk
    assert "downside_deviation" in tail_risk

    # All should be Decimal
    for metric in tail_risk.values():
        assert isinstance(metric, Decimal)

    # Max loss should be negative
    assert float(tail_risk["max_loss_1d"]) < 0


def test_tail_risk_with_negative_skew(synthetic_skewed_returns):
    """Test that negative skew is detected."""
    risk = RiskAnalytics(synthetic_skewed_returns)

    tail_risk = risk.calculate_tail_risk()

    # Skewness should be negative (more extreme losses)
    assert float(tail_risk["skewness"]) < 0


def test_tail_risk_max_loss_ordering(synthetic_normal_returns):
    """Test that max losses increase with time horizon."""
    risk = RiskAnalytics(synthetic_normal_returns)

    tail_risk = risk.calculate_tail_risk()

    # Multi-day losses should be >= 1-day loss (in absolute terms)
    assert abs(float(tail_risk["max_loss_5d"])) >= abs(float(tail_risk["max_loss_1d"]))
    assert abs(float(tail_risk["max_loss_10d"])) >= abs(float(tail_risk["max_loss_5d"]))


# ============================================================================
# Unit Tests: Risk Decomposition
# ============================================================================


def test_risk_decomposition_requires_positions(sample_returns):
    """Test that risk decomposition requires positions data."""
    risk = RiskAnalytics(sample_returns)

    with pytest.raises(ValueError, match="Positions data required"):
        risk.calculate_risk_decomposition()


def test_risk_decomposition_with_positions(sample_returns, sample_positions):
    """Test risk decomposition calculation."""
    risk = RiskAnalytics(sample_returns, positions=sample_positions)

    decomposition = risk.calculate_risk_decomposition()

    assert isinstance(decomposition, pd.DataFrame)
    assert "symbol" in decomposition.columns
    assert "marginal_var" in decomposition.columns
    assert "component_var" in decomposition.columns
    assert "risk_contribution_pct" in decomposition.columns

    # Verify we have results for all assets
    assert len(decomposition) == 3  # SPY, TLT, GLD

    # Verify all values are Decimal type
    for i in range(len(decomposition)):
        assert isinstance(decomposition["marginal_var"].iloc[i], Decimal)
        assert isinstance(decomposition["component_var"].iloc[i], Decimal)
        assert isinstance(decomposition["risk_contribution_pct"].iloc[i], Decimal)

    # Verify risk contributions sum to approximately 100%
    total_contribution = sum(float(x) for x in decomposition["risk_contribution_pct"])
    assert abs(total_contribution - 100.0) < 2.0  # Within 2% due to rounding/numerical precision


def test_risk_decomposition_validates_calculations():
    """Test that risk decomposition uses actual calculations, not hardcoded values."""
    np.random.seed(200)
    dates = pd.date_range(start="2023-01-01", periods=100, freq="D")

    # Create two scenarios with different returns
    scenario1_returns = {
        "A_returns": np.random.normal(0.001, 0.02, 100),
        "B_returns": np.random.normal(0.0005, 0.01, 100),
    }

    scenario2_returns = {
        "A_returns": np.random.normal(0.002, 0.03, 100),  # Different mean and std
        "B_returns": np.random.normal(0.001, 0.015, 100),
    }

    portfolio1 = pd.DataFrame({"returns": np.random.normal(0, 0.01, 100)}, index=dates)
    portfolio2 = pd.DataFrame({"returns": np.random.normal(0, 0.01, 100)}, index=dates)

    positions1 = pd.DataFrame(scenario1_returns, index=dates)
    positions2 = pd.DataFrame(scenario2_returns, index=dates)

    risk1 = RiskAnalytics(portfolio1, positions=positions1)
    risk2 = RiskAnalytics(portfolio2, positions=positions2)

    decomp1 = risk1.calculate_risk_decomposition()
    decomp2 = risk2.calculate_risk_decomposition()

    # Verify different inputs produce different outputs (zero-mock validation)
    assert not decomp1["marginal_var"].equals(decomp2["marginal_var"])
    assert not decomp1["component_var"].equals(decomp2["component_var"])


# ============================================================================
# Unit Tests: Comprehensive Risk Analysis
# ============================================================================


def test_analyze_risk_without_optional_data(sample_returns):
    """Test comprehensive risk analysis without optional data."""
    risk = RiskAnalytics(sample_returns)

    risk_report = risk.analyze_risk()

    assert "var" in risk_report
    assert "cvar" in risk_report
    assert "stress_tests" in risk_report
    assert "tail_risk" in risk_report

    # Should NOT have beta or correlation without optional data
    assert "beta" not in risk_report
    assert "correlation" not in risk_report


def test_analyze_risk_with_benchmark(sample_returns, sample_benchmark_returns):
    """Test comprehensive risk analysis with benchmark."""
    risk = RiskAnalytics(sample_returns, benchmark_returns=sample_benchmark_returns)

    risk_report = risk.analyze_risk()

    assert "beta" in risk_report
    assert "beta" in risk_report["beta"]


def test_analyze_risk_with_positions(sample_returns, sample_positions):
    """Test comprehensive risk analysis with positions."""
    risk = RiskAnalytics(sample_returns, positions=sample_positions)

    risk_report = risk.analyze_risk()

    assert "correlation" in risk_report
    assert "risk_decomposition" in risk_report


# ============================================================================
# Unit Tests: Visualizations
# ============================================================================


def test_plot_var_distribution(synthetic_normal_returns):
    """Test VaR distribution plot."""
    risk = RiskAnalytics(synthetic_normal_returns)

    fig = risk.plot_var_distribution()

    assert isinstance(fig, plt.Figure)
    plt.close(fig)


def test_plot_stress_test_results(sample_returns):
    """Test stress test results plot."""
    risk = RiskAnalytics(sample_returns)

    fig = risk.plot_stress_test_results()

    assert isinstance(fig, plt.Figure)
    plt.close(fig)


def test_plot_correlation_heatmap(sample_returns, sample_positions):
    """Test correlation heatmap plot."""
    risk = RiskAnalytics(sample_returns, positions=sample_positions)

    fig = risk.plot_correlation_heatmap()

    assert isinstance(fig, plt.Figure)
    plt.close(fig)


def test_plot_correlation_heatmap_requires_positions(sample_returns):
    """Test that correlation heatmap requires positions."""
    risk = RiskAnalytics(sample_returns)

    with pytest.raises(ValueError, match="Positions data required"):
        risk.plot_correlation_heatmap()


# ============================================================================
# Property Tests
# ============================================================================


@given(
    mean_return=st.floats(min_value=-0.01, max_value=0.01),
    std_return=st.floats(min_value=0.001, max_value=0.05),
    confidence=st.sampled_from([0.90, 0.95, 0.99]),
)
@settings(max_examples=50, deadline=None)
def test_property_cvar_greater_equal_var(mean_return, std_return, confidence):
    """Property test: CVaR >= VaR (in absolute terms)."""
    # Generate synthetic returns
    np.random.seed(42)
    dates = pd.date_range(start="2023-01-01", periods=252, freq="D")
    returns = np.random.normal(mean_return, std_return, 252)

    df = pd.DataFrame({"returns": returns}, index=dates)

    risk = RiskAnalytics(df, confidence_levels=[confidence])

    var_results = risk.calculate_var(method="historical")
    cvar_results = risk.calculate_cvar(method="historical")

    var_key = f"var_{int(confidence * 100)}"
    cvar_key = f"cvar_{int(confidence * 100)}"

    # CVaR should be <= VaR (more negative = larger loss)
    assert float(cvar_results[cvar_key]) <= float(var_results[var_key])


@given(
    confidence_levels=st.lists(st.floats(min_value=0.90, max_value=0.99), min_size=2, max_size=3)
)
@settings(max_examples=30, deadline=None)
def test_property_var_increases_with_confidence(confidence_levels):
    """Property test: Higher confidence -> larger VaR (more negative)."""
    # Generate synthetic returns
    np.random.seed(42)
    dates = pd.date_range(start="2023-01-01", periods=252, freq="D")
    returns = np.random.normal(0, 0.02, 252)

    df = pd.DataFrame({"returns": returns}, index=dates)

    # Sort confidence levels
    sorted_confidences = sorted(set(confidence_levels))
    if len(sorted_confidences) < 2:
        return  # Skip if not enough unique values

    risk = RiskAnalytics(df, confidence_levels=sorted_confidences)
    var_results = risk.calculate_var(method="historical")

    # Check that VaR increases (becomes more negative) with confidence
    for i in range(len(sorted_confidences) - 1):
        lower_conf = sorted_confidences[i]
        higher_conf = sorted_confidences[i + 1]

        lower_key = f"var_{int(lower_conf * 100)}"
        higher_key = f"var_{int(higher_conf * 100)}"

        # Higher confidence should have larger VaR (more negative)
        assert float(var_results[higher_key]) <= float(var_results[lower_key])


# ============================================================================
# Integration Tests
# ============================================================================


def test_integration_full_risk_analysis(sample_returns, sample_benchmark_returns, sample_positions):
    """Integration test: Full risk analysis workflow."""
    # Create RiskAnalytics with all optional data
    risk = RiskAnalytics(
        sample_returns,
        confidence_levels=[0.90, 0.95, 0.99],
        benchmark_returns=sample_benchmark_returns,
        positions=sample_positions,
    )

    # Run comprehensive analysis
    risk_report = risk.analyze_risk(var_method="historical")

    # Validate structure
    assert "var" in risk_report
    assert "cvar" in risk_report
    assert "stress_tests" in risk_report
    assert "tail_risk" in risk_report
    assert "beta" in risk_report
    assert "correlation" in risk_report
    assert "risk_decomposition" in risk_report

    # Validate VaR results
    assert "var_90" in risk_report["var"]
    assert "var_95" in risk_report["var"]
    assert "var_99" in risk_report["var"]

    # Validate CVaR results
    assert "cvar_90" in risk_report["cvar"]
    assert "cvar_95" in risk_report["cvar"]
    assert "cvar_99" in risk_report["cvar"]

    # Validate stress tests
    assert "2008_financial_crisis" in risk_report["stress_tests"]
    assert "covid_crash" in risk_report["stress_tests"]
    assert "flash_crash" in risk_report["stress_tests"]

    # Validate tail risk
    assert "skewness" in risk_report["tail_risk"]
    assert "kurtosis" in risk_report["tail_risk"]

    # Validate beta
    assert "beta" in risk_report["beta"]
    assert "alpha" in risk_report["beta"]


def test_integration_var_methods_comparison(sample_returns):
    """Integration test: Compare different VaR methods."""
    risk = RiskAnalytics(sample_returns, confidence_levels=[0.95])

    var_parametric = risk.calculate_var(method="parametric")
    var_historical = risk.calculate_var(method="historical")
    var_montecarlo = risk.calculate_var(method="montecarlo")

    # All methods should give results in similar range
    # (not testing exact values, just that they're reasonable)
    assert float(var_parametric["var_95"]) < 0
    assert float(var_historical["var_95"]) < 0
    assert float(var_montecarlo["var_95"]) < 0


# ============================================================================
# Edge Cases
# ============================================================================


def test_edge_case_all_positive_returns():
    """Test handling of all positive returns (no losses)."""
    dates = pd.date_range(start="2023-01-01", periods=100, freq="D")
    returns = np.abs(np.random.normal(0.01, 0.005, 100))  # All positive

    df = pd.DataFrame({"returns": returns}, index=dates)

    risk = RiskAnalytics(df)

    var_results = risk.calculate_var(method="historical")
    # VaR might be positive (no expected loss)
    assert "var_95" in var_results


def test_edge_case_constant_returns():
    """Test handling of constant returns (zero variance)."""
    dates = pd.date_range(start="2023-01-01", periods=100, freq="D")
    returns = np.ones(100) * 0.001  # Constant

    df = pd.DataFrame({"returns": returns}, index=dates)

    risk = RiskAnalytics(df)

    var_results = risk.calculate_var(method="parametric")
    # With zero variance, VaR should equal mean
    assert abs(float(var_results["var_95"]) - 0.001) < 0.0001
