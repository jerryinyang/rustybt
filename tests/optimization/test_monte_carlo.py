"""Tests for Monte Carlo simulation with trade permutation."""

from decimal import Decimal

import numpy as np
import polars as pl
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from rustybt.optimization.monte_carlo import MonteCarloResult, MonteCarloSimulator


@pytest.fixture
def sample_trades():
    """Create sample trades DataFrame for testing."""
    return pl.DataFrame(
        {
            "timestamp": [
                "2024-01-01",
                "2024-01-02",
                "2024-01-03",
                "2024-01-04",
                "2024-01-05",
            ],
            "return": [0.02, -0.01, 0.03, -0.015, 0.025],
            "pnl": [200.0, -100.0, 300.0, -150.0, 250.0],
            "asset": ["AAPL", "AAPL", "AAPL", "AAPL", "AAPL"],
        }
    )


@pytest.fixture
def sample_observed_metrics():
    """Sample observed metrics for testing."""
    return {
        "sharpe_ratio": Decimal("1.5"),
        "total_return": Decimal("0.065"),
        "max_drawdown": Decimal("0.02"),
        "win_rate": Decimal("0.6"),
    }


class TestMonteCarloSimulator:
    """Test MonteCarloSimulator class."""

    def test_initialization_default_params(self):
        """Test simulator initialization with default parameters."""
        mc = MonteCarloSimulator()

        assert mc.n_simulations == 1000
        assert mc.method == "permutation"
        assert mc.seed is None
        assert mc.confidence_level == 0.95

    def test_initialization_custom_params(self):
        """Test simulator initialization with custom parameters."""
        mc = MonteCarloSimulator(
            n_simulations=500, method="bootstrap", seed=42, confidence_level=0.90
        )

        assert mc.n_simulations == 500
        assert mc.method == "bootstrap"
        assert mc.seed == 42
        assert mc.confidence_level == 0.90

    def test_initialization_invalid_n_simulations(self):
        """Test initialization fails with too few simulations."""
        with pytest.raises(ValueError, match="n_simulations must be >= 100"):
            MonteCarloSimulator(n_simulations=50)

    def test_initialization_invalid_method(self):
        """Test initialization fails with invalid method."""
        with pytest.raises(ValueError, match="Invalid method"):
            MonteCarloSimulator(method="invalid")

    def test_initialization_invalid_confidence_level(self):
        """Test initialization fails with invalid confidence level."""
        with pytest.raises(ValueError, match="confidence_level must be between"):
            MonteCarloSimulator(confidence_level=1.5)

    def test_run_with_valid_trades(self, sample_trades, sample_observed_metrics):
        """Test running simulation with valid trades."""
        mc = MonteCarloSimulator(n_simulations=100, seed=42)
        result = mc.run(sample_trades, sample_observed_metrics)

        assert isinstance(result, MonteCarloResult)
        assert result.n_simulations == 100
        assert result.method == "permutation"
        assert result.seed == 42

        # Check all metrics present
        assert "sharpe_ratio" in result.simulated_metrics
        assert "total_return" in result.simulated_metrics
        assert "max_drawdown" in result.simulated_metrics
        assert "win_rate" in result.simulated_metrics

        # Check distribution size
        assert len(result.simulated_metrics["sharpe_ratio"]) == 100

    def test_run_with_empty_trades(self, sample_observed_metrics):
        """Test run fails with empty trades DataFrame."""
        mc = MonteCarloSimulator(n_simulations=100)
        empty_trades = pl.DataFrame({"return": [], "pnl": []})

        with pytest.raises(ValueError, match="Trades DataFrame cannot be empty"):
            mc.run(empty_trades, sample_observed_metrics)

    def test_run_with_missing_columns(self, sample_observed_metrics):
        """Test run fails with missing required columns."""
        mc = MonteCarloSimulator(n_simulations=100)
        invalid_trades = pl.DataFrame({"timestamp": ["2024-01-01"], "return": [0.02]})

        with pytest.raises(ValueError, match="Missing required columns"):
            mc.run(invalid_trades, sample_observed_metrics)

    def test_run_with_null_values(self, sample_observed_metrics):
        """Test run fails with null values in trades."""
        mc = MonteCarloSimulator(n_simulations=100)
        trades_with_nulls = pl.DataFrame(
            {"return": [0.02, None, 0.03], "pnl": [200.0, -100.0, 300.0]}
        )

        with pytest.raises(ValueError, match="Trades contain null"):
            mc.run(trades_with_nulls, sample_observed_metrics)

    def test_run_with_empty_observed_metrics(self, sample_trades):
        """Test run fails with empty observed metrics."""
        mc = MonteCarloSimulator(n_simulations=100)

        with pytest.raises(ValueError, match="observed_metrics cannot be empty"):
            mc.run(sample_trades, {})

    def test_permutation_preserves_total_return(self, sample_trades):
        """Test permutation preserves total return (sum of returns)."""
        mc = MonteCarloSimulator(n_simulations=100, method="permutation", seed=42)

        # Calculate original total return
        original_total_return = sample_trades["return"].sum()

        # Extract trade data
        trade_data = mc._extract_trade_data(sample_trades)

        # Run multiple permutations
        for _ in range(10):
            permuted_returns, _ = mc._permute_trades(trade_data)
            permuted_total = np.sum(permuted_returns)

            # Total return must be preserved
            assert abs(permuted_total - original_total_return) < 1e-10

    def test_permutation_preserves_trade_count(self, sample_trades):
        """Test permutation preserves number of trades."""
        mc = MonteCarloSimulator(n_simulations=100, method="permutation", seed=42)
        trade_data = mc._extract_trade_data(sample_trades)

        original_count = len(sample_trades)

        for _ in range(10):
            permuted_returns, permuted_pnl = mc._permute_trades(trade_data)

            assert len(permuted_returns) == original_count
            assert len(permuted_pnl) == original_count

    def test_permutation_changes_order(self, sample_trades):
        """Test permutation actually changes trade order."""
        mc = MonteCarloSimulator(n_simulations=100, method="permutation", seed=42)
        trade_data = mc._extract_trade_data(sample_trades)

        original_returns = trade_data["returns"]

        # At least one permutation should differ from original
        found_different = False
        for _ in range(10):
            permuted_returns, _ = mc._permute_trades(trade_data)
            if not np.array_equal(permuted_returns, original_returns):
                found_different = True
                break

        assert found_different, "Permutation should change trade order"

    def test_bootstrap_preserves_trade_count(self, sample_trades):
        """Test bootstrap preserves number of trades."""
        mc = MonteCarloSimulator(n_simulations=100, method="bootstrap", seed=42)
        trade_data = mc._extract_trade_data(sample_trades)

        original_count = len(sample_trades)

        for _ in range(10):
            bootstrap_returns, bootstrap_pnl = mc._bootstrap_trades(trade_data)

            assert len(bootstrap_returns) == original_count
            assert len(bootstrap_pnl) == original_count

    def test_bootstrap_samples_with_replacement(self, sample_trades):
        """Test bootstrap samples with replacement (some trades may repeat)."""
        mc = MonteCarloSimulator(n_simulations=100, method="bootstrap", seed=42)
        trade_data = mc._extract_trade_data(sample_trades)

        # Bootstrap should sometimes have duplicate values
        found_duplicates = False
        for _ in range(20):
            bootstrap_returns, _ = mc._bootstrap_trades(trade_data)
            unique_count = len(np.unique(bootstrap_returns))
            if unique_count < len(bootstrap_returns):
                found_duplicates = True
                break

        assert found_duplicates, "Bootstrap should sample with replacement"

    def test_reconstruct_equity_curve(self):
        """Test equity curve reconstruction from PnL sequence."""
        mc = MonteCarloSimulator(n_simulations=100)

        pnl_sequence = np.array([100.0, -50.0, 200.0, -75.0, 150.0])
        initial_capital = 10000.0

        equity_curve = mc._reconstruct_equity_curve(pnl_sequence, initial_capital)

        # Check length (initial + trades)
        assert len(equity_curve) == len(pnl_sequence) + 1

        # Check starting value
        assert equity_curve[0] == initial_capital

        # Check final value
        expected_final = initial_capital + np.sum(pnl_sequence)
        assert abs(equity_curve[-1] - expected_final) < 1e-10

        # Check intermediate values
        assert abs(equity_curve[1] - (initial_capital + 100.0)) < 1e-10
        assert abs(equity_curve[2] - (initial_capital + 100.0 - 50.0)) < 1e-10

    def test_calculate_metrics_sharpe_ratio(self):
        """Test Sharpe ratio calculation."""
        mc = MonteCarloSimulator(n_simulations=100)

        # Consistent positive returns → high Sharpe
        # NOTE: With identical returns, std = 0, so Sharpe = 0
        # Use varied returns for non-zero std
        returns = np.array([0.01, 0.012, 0.008, 0.011, 0.009])
        equity_curve = np.cumsum(np.concatenate([[10000.0], returns * 10000]))

        metrics = mc._calculate_metrics(returns, equity_curve)

        # Sharpe should be positive with varied positive returns
        assert metrics["sharpe_ratio"] > Decimal("0")

    def test_calculate_metrics_max_drawdown(self):
        """Test maximum drawdown calculation."""
        mc = MonteCarloSimulator(n_simulations=100)

        # Create equity curve with known drawdown
        equity_curve = np.array([10000.0, 11000.0, 9000.0, 8000.0, 10000.0])
        returns = np.diff(equity_curve) / equity_curve[:-1]

        metrics = mc._calculate_metrics(returns, equity_curve)

        # Max drawdown from 11000 to 8000 = 27.27%
        expected_drawdown = (11000.0 - 8000.0) / 11000.0
        assert abs(float(metrics["max_drawdown"]) - expected_drawdown) < 0.01

    def test_calculate_metrics_win_rate(self):
        """Test win rate calculation."""
        mc = MonteCarloSimulator(n_simulations=100)

        # 3 wins, 2 losses → 60% win rate
        returns = np.array([0.01, -0.01, 0.02, 0.01, -0.005])
        equity_curve = np.cumsum(np.concatenate([[10000.0], returns * 10000]))

        metrics = mc._calculate_metrics(returns, equity_curve)

        assert metrics["win_rate"] == Decimal("0.6")

    def test_calculate_confidence_intervals(self, sample_trades, sample_observed_metrics):
        """Test confidence interval calculation."""
        mc = MonteCarloSimulator(
            n_simulations=100, method="permutation", seed=42, confidence_level=0.95
        )
        result = mc.run(sample_trades, sample_observed_metrics)

        # Check CI for each metric
        for metric in ["sharpe_ratio", "total_return", "max_drawdown", "win_rate"]:
            ci_lower, ci_upper = result.confidence_intervals[metric]

            # Lower bound should be less than or equal to upper bound
            # (can be equal if all permutations yield same result)
            assert ci_lower <= ci_upper

            # CI should contain some simulated values
            distribution = result.simulated_metrics[metric]
            values_in_ci = sum(1 for v in distribution if ci_lower <= v <= ci_upper)
            # At least 90% should be in 95% CI
            assert values_in_ci >= 0.90 * len(distribution)

    def test_calculate_p_values(self, sample_trades, sample_observed_metrics):
        """Test p-value calculation."""
        mc = MonteCarloSimulator(n_simulations=100, method="permutation", seed=42)
        result = mc.run(sample_trades, sample_observed_metrics)

        # P-values should be between 0 and 1
        for _metric, p_value in result.p_values.items():
            assert Decimal("0") <= p_value <= Decimal("1")

    def test_calculate_percentile_ranks(self, sample_trades, sample_observed_metrics):
        """Test percentile rank calculation."""
        mc = MonteCarloSimulator(n_simulations=100, method="permutation", seed=42)
        result = mc.run(sample_trades, sample_observed_metrics)

        # Percentile ranks should be between 0 and 100
        for _metric, percentile in result.percentile_ranks.items():
            assert Decimal("0") <= percentile <= Decimal("100")

    def test_reproducibility_with_seed(self, sample_trades, sample_observed_metrics):
        """Test simulations are reproducible with same seed."""
        mc1 = MonteCarloSimulator(n_simulations=100, method="permutation", seed=42)
        result1 = mc1.run(sample_trades, sample_observed_metrics)

        mc2 = MonteCarloSimulator(n_simulations=100, method="permutation", seed=42)
        result2 = mc2.run(sample_trades, sample_observed_metrics)

        # Results should be identical
        for metric in result1.simulated_metrics:
            dist1 = result1.simulated_metrics[metric]
            dist2 = result2.simulated_metrics[metric]
            assert dist1 == dist2

    def test_different_results_without_seed(self, sample_trades, sample_observed_metrics):
        """Test simulations differ without seed."""
        mc1 = MonteCarloSimulator(n_simulations=100, method="permutation")
        result1 = mc1.run(sample_trades, sample_observed_metrics)

        mc2 = MonteCarloSimulator(n_simulations=100, method="permutation")
        result2 = mc2.run(sample_trades, sample_observed_metrics)

        # Results should differ
        found_difference = False
        for metric in result1.simulated_metrics:
            dist1 = result1.simulated_metrics[metric]
            dist2 = result2.simulated_metrics[metric]
            if dist1 != dist2:
                found_difference = True
                break

        assert found_difference, "Results without seed should differ"


class TestMonteCarloResult:
    """Test MonteCarloResult class."""

    @pytest.fixture
    def sample_result(self):
        """Create sample Monte Carlo result for testing."""
        return MonteCarloResult(
            observed_metrics={
                "sharpe_ratio": Decimal("2.0"),
                "total_return": Decimal("0.15"),
            },
            simulated_metrics={
                "sharpe_ratio": [Decimal("1.0"), Decimal("1.2"), Decimal("1.5")],
                "total_return": [Decimal("0.08"), Decimal("0.10"), Decimal("0.12")],
            },
            confidence_intervals={
                "sharpe_ratio": (Decimal("1.0"), Decimal("1.5")),
                "total_return": (Decimal("0.08"), Decimal("0.12")),
            },
            p_values={
                "sharpe_ratio": Decimal("0.01"),
                "total_return": Decimal("0.02"),
            },
            percentile_ranks={
                "sharpe_ratio": Decimal("99.0"),
                "total_return": Decimal("98.0"),
            },
            n_simulations=100,
            method="permutation",
            seed=42,
        )

    def test_is_significant(self, sample_result):
        """Test significance detection (p < 0.05)."""
        significance = sample_result.is_significant

        # Both metrics have p < 0.05
        assert significance["sharpe_ratio"] is True
        assert significance["total_return"] is True

    def test_is_robust(self, sample_result):
        """Test robustness detection (outside 95% CI)."""
        robustness = sample_result.is_robust

        # Observed Sharpe (2.0) > CI upper (1.5) → robust
        assert robustness["sharpe_ratio"] is True

        # Observed return (0.15) > CI upper (0.12) → robust
        assert robustness["total_return"] is True

    def test_get_summary(self, sample_result):
        """Test summary generation."""
        summary = sample_result.get_summary("sharpe_ratio")

        # Check summary contains key information
        assert "Monte Carlo Analysis" in summary
        assert "sharpe_ratio" in summary
        assert "2.0" in summary  # Observed
        assert "0.01" in summary  # P-value
        assert "ROBUST" in summary  # Interpretation

    def test_get_summary_invalid_metric(self, sample_result):
        """Test summary fails with invalid metric."""
        with pytest.raises(ValueError, match=r"Metric .* not found"):
            sample_result.get_summary("invalid_metric")

    def test_plot_distribution(self, sample_result, tmp_path):
        """Test plot distribution generates plot without errors."""
        output_file = tmp_path / "test_plot.png"

        # Plot should not raise errors
        sample_result.plot_distribution(metric="sharpe_ratio", output_path=output_file, show=False)

        # File should be created
        assert output_file.exists()

    def test_plot_distribution_invalid_metric(self, sample_result):
        """Test plot fails with invalid metric."""
        with pytest.raises(ValueError, match=r"Metric .* not found"):
            sample_result.plot_distribution(metric="invalid_metric", show=False)


class TestIntegration:
    """Integration tests with complete backtest workflow."""

    def test_monte_carlo_on_winning_strategy(self):
        """Test Monte Carlo on strategy with consistent winning trades."""
        # Create trades from winning strategy
        trades = pl.DataFrame(
            {
                "timestamp": [f"2024-01-{i:02d}" for i in range(1, 21)],
                "return": [0.02] * 20,  # Consistent 2% wins
                "pnl": [200.0] * 20,
                "asset": ["AAPL"] * 20,
            }
        )

        observed_metrics = {
            "sharpe_ratio": Decimal("10.0"),  # Very high Sharpe
            "total_return": Decimal("0.40"),
            "win_rate": Decimal("1.0"),
        }

        mc = MonteCarloSimulator(n_simulations=200, method="permutation", seed=42)
        result = mc.run(trades, observed_metrics)

        # Consistent wins → all permutations should have same metrics
        # P-values should be moderate (all permutations similar)
        # CI should be narrow
        ci_lower, ci_upper = result.confidence_intervals["total_return"]
        ci_width = float(ci_upper - ci_lower)

        # Width should be very small (all permutations identical)
        assert ci_width < 0.01

    def test_monte_carlo_on_mixed_strategy(self):
        """Test Monte Carlo on strategy with mixed win/loss trades."""
        # Create realistic mixed trades with sufficient variation
        trades = pl.DataFrame(
            {
                "timestamp": [f"2024-01-{i:02d}" for i in range(1, 21)],
                "return": [
                    0.03,
                    -0.02,
                    0.025,
                    -0.015,
                    0.02,
                    0.04,
                    -0.01,
                    0.015,
                    -0.005,
                    0.035,
                ]
                * 2,
                "pnl": [
                    300.0,
                    -200.0,
                    250.0,
                    -150.0,
                    200.0,
                    400.0,
                    -100.0,
                    150.0,
                    -50.0,
                    350.0,
                ]
                * 2,
                "asset": ["AAPL"] * 20,
            }
        )

        observed_metrics = {
            "sharpe_ratio": Decimal("1.5"),
            "total_return": Decimal("0.20"),
            "win_rate": Decimal("0.6"),
        }

        mc = MonteCarloSimulator(n_simulations=200, method="permutation", seed=42)
        result = mc.run(trades, observed_metrics)

        # Mixed trades → permutations should vary
        # Check distribution has reasonable variance
        sharpe_distribution = result.simulated_metrics["sharpe_ratio"]
        sharpe_values = [float(v) for v in sharpe_distribution]
        sharpe_std = np.std(sharpe_values)

        # Should have some variance (not all identical)
        # Lower threshold for permutation test since we're just reordering
        assert sharpe_std > 0.0

    def test_permutation_vs_bootstrap_methods(self):
        """Test permutation and bootstrap methods produce similar distributions."""
        trades = pl.DataFrame(
            {
                "timestamp": [f"2024-01-{i:02d}" for i in range(1, 21)],
                "return": [0.02, -0.01, 0.03, -0.015, 0.025] * 4,
                "pnl": [200.0, -100.0, 300.0, -150.0, 250.0] * 4,
                "asset": ["AAPL"] * 20,
            }
        )

        observed_metrics = {"sharpe_ratio": Decimal("1.5")}

        # Run both methods
        mc_perm = MonteCarloSimulator(n_simulations=200, method="permutation", seed=42)
        result_perm = mc_perm.run(trades, observed_metrics)

        mc_boot = MonteCarloSimulator(n_simulations=200, method="bootstrap", seed=42)
        result_boot = mc_boot.run(trades, observed_metrics)

        # Both should produce distributions
        assert len(result_perm.simulated_metrics["sharpe_ratio"]) == 200
        assert len(result_boot.simulated_metrics["sharpe_ratio"]) == 200

        # Distributions should have similar statistics (but not identical)
        perm_mean = np.mean([float(v) for v in result_perm.simulated_metrics["sharpe_ratio"]])
        boot_mean = np.mean([float(v) for v in result_boot.simulated_metrics["sharpe_ratio"]])

        # Means should be reasonably close (within 20%)
        assert abs(perm_mean - boot_mean) / perm_mean < 0.20


class TestPropertyBased:
    """Property-based tests using Hypothesis."""

    @given(
        returns=st.lists(
            st.floats(min_value=-0.05, max_value=0.05, allow_nan=False, allow_infinity=False),
            min_size=10,
            max_size=50,
        )
    )
    @settings(max_examples=50, deadline=None)
    def test_permutation_preserves_sum(self, returns):
        """Property: Permutation must preserve sum of returns."""
        # Filter out edge cases
        if len(returns) < 10:
            return

        # Skip if all returns are zero (no variance)
        if all(abs(r) < 1e-10 for r in returns):
            return

        # Create trades DataFrame
        trades = pl.DataFrame(
            {
                "return": returns,
                "pnl": [r * 1000 for r in returns],
            }
        )

        # Use n_simulations=100 (minimum) for this test
        mc = MonteCarloSimulator(n_simulations=100, method="permutation", seed=42)
        trade_data = mc._extract_trade_data(trades)

        original_sum = np.sum(trade_data["returns"])

        # Test multiple permutations directly (not through run())
        for _ in range(5):
            permuted_returns, _ = mc._permute_trades(trade_data)
            permuted_sum = np.sum(permuted_returns)

            # Sum must be preserved (within floating point precision)
            assert abs(permuted_sum - original_sum) < 1e-8

    @given(
        n_trades=st.integers(min_value=10, max_value=100),
        win_rate=st.floats(min_value=0.3, max_value=0.7),
    )
    @settings(max_examples=20, deadline=None)
    def test_win_rate_preserved_by_permutation(self, n_trades, win_rate):
        """Property: Win rate must be preserved by permutation."""
        # Generate trades with specified win rate
        n_wins = int(n_trades * win_rate)
        n_losses = n_trades - n_wins

        returns = [0.02] * n_wins + [-0.01] * n_losses
        trades = pl.DataFrame(
            {
                "return": returns,
                "pnl": [r * 1000 for r in returns],
            }
        )

        # Use n_simulations=100 (minimum)
        mc = MonteCarloSimulator(n_simulations=100, method="permutation", seed=42)
        trade_data = mc._extract_trade_data(trades)

        original_win_count = np.sum(trade_data["returns"] > 0)

        # Test multiple permutations directly (not through run())
        for _ in range(5):
            permuted_returns, _ = mc._permute_trades(trade_data)
            permuted_win_count = np.sum(permuted_returns > 0)

            # Win count must be preserved
            assert permuted_win_count == original_win_count
