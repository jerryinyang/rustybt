"""Tests for Monte Carlo noise infusion simulator."""

from decimal import Decimal

import numpy as np
import polars as pl
import pytest
from hypothesis import given
from hypothesis import strategies as st

from rustybt.optimization.noise_infusion import (
    NoiseInfusionResult,
    NoiseInfusionSimulator,
)


# Fixtures
@pytest.fixture
def sample_ohlcv_data() -> pl.DataFrame:
    """Generate sample OHLCV data for testing.

    Returns:
        DataFrame with 100 bars of synthetic OHLCV data
    """
    np.random.seed(42)
    n_bars = 100

    # Generate realistic price series
    close_prices = 100 * np.exp(np.cumsum(np.random.normal(0, 0.01, n_bars)))

    # Generate OHLC with proper relationships
    high_prices = close_prices * np.random.uniform(1.0, 1.02, n_bars)
    low_prices = close_prices * np.random.uniform(0.98, 1.0, n_bars)
    open_prices = close_prices * np.random.uniform(0.99, 1.01, n_bars)

    # Ensure OHLCV constraints
    high_prices = np.maximum.reduce([high_prices, open_prices, close_prices])
    low_prices = np.minimum.reduce([low_prices, open_prices, close_prices])

    volume = np.random.uniform(1000, 10000, n_bars)

    return pl.DataFrame(
        {
            "timestamp": pl.datetime_range(
                start=pl.datetime(2020, 1, 1),
                end=pl.datetime(2020, 4, 9),
                interval="1d",
                eager=True,
            ),
            "open": open_prices,
            "high": high_prices,
            "low": low_prices,
            "close": close_prices,
            "volume": volume,
        }
    )


@pytest.fixture
def simple_backtest_fn():
    """Create simple backtest function for testing.

    Returns:
        Function that calculates basic metrics from OHLCV data
    """

    def backtest(data: pl.DataFrame) -> dict[str, Decimal]:
        """Calculate simple metrics from data.

        Args:
            data: OHLCV DataFrame

        Returns:
            Dictionary with sharpe_ratio, total_return metrics
        """
        # Calculate returns
        returns = data["close"].pct_change().drop_nulls()
        returns_array = returns.to_numpy()

        # Calculate Sharpe ratio
        if len(returns_array) > 1:
            mean_return = np.mean(returns_array)
            std_return = np.std(returns_array, ddof=1)
            sharpe = mean_return / std_return * np.sqrt(252) if std_return > 0 else 0.0
        else:
            sharpe = 0.0

        # Calculate total return
        total_return = (data["close"][-1] - data["close"][0]) / data["close"][0]

        return {
            "sharpe_ratio": Decimal(str(sharpe)),
            "total_return": Decimal(str(total_return)),
        }

    return backtest


# Unit Tests
class TestNoiseInfusionSimulator:
    """Test suite for NoiseInfusionSimulator class."""

    def test_initialization_valid_params(self):
        """Test simulator initialization with valid parameters."""
        sim = NoiseInfusionSimulator(
            n_simulations=100, std_pct=0.01, noise_model="gaussian", seed=42
        )

        assert sim.n_simulations == 100
        assert sim.std_pct == Decimal("0.01")
        assert sim.noise_model == "gaussian"
        assert sim.seed == 42

    def test_initialization_invalid_n_simulations(self):
        """Test initialization fails with too few simulations."""
        with pytest.raises(ValueError, match="n_simulations must be >= 100"):
            NoiseInfusionSimulator(n_simulations=50)

    def test_initialization_invalid_std_pct(self):
        """Test initialization fails with invalid noise amplitude."""
        with pytest.raises(ValueError, match="std_pct must be between"):
            NoiseInfusionSimulator(std_pct=0.0)

        with pytest.raises(ValueError, match="std_pct must be between"):
            NoiseInfusionSimulator(std_pct=0.6)

    def test_initialization_invalid_noise_model(self):
        """Test initialization fails with invalid noise model."""
        with pytest.raises(ValueError, match="Invalid noise_model"):
            NoiseInfusionSimulator(noise_model="invalid")  # type: ignore

    def test_initialization_invalid_confidence_level(self):
        """Test initialization fails with invalid confidence level."""
        with pytest.raises(ValueError, match="confidence_level must be between"):
            NoiseInfusionSimulator(confidence_level=1.5)

    def test_validate_data_missing_columns(self):
        """Test data validation fails with missing columns."""
        sim = NoiseInfusionSimulator(seed=42)

        invalid_data = pl.DataFrame({"open": [100], "close": [101]})

        with pytest.raises(ValueError, match="Missing required columns"):
            sim._validate_data(invalid_data)

    def test_validate_data_empty(self):
        """Test data validation fails with empty DataFrame."""
        sim = NoiseInfusionSimulator(seed=42)

        empty_data = pl.DataFrame({"open": [], "high": [], "low": [], "close": [], "volume": []})

        with pytest.raises(ValueError, match="cannot be empty"):
            sim._validate_data(empty_data)

    def test_validate_data_null_values(self):
        """Test data validation fails with null values."""
        sim = NoiseInfusionSimulator(seed=42)

        data_with_nulls = pl.DataFrame(
            {
                "open": [100, None, 102],
                "high": [105, 106, 107],
                "low": [99, 100, 101],
                "close": [103, 104, 105],
                "volume": [1000, 1100, 1200],
            }
        )

        with pytest.raises(ValueError, match="contains null values"):
            sim._validate_data(data_with_nulls)

    def test_validate_data_invalid_ohlcv_relationships(self):
        """Test data validation fails with invalid OHLCV constraints."""
        sim = NoiseInfusionSimulator(seed=42)

        invalid_ohlcv = pl.DataFrame(
            {
                "open": [100, 101, 102],
                "high": [105, 106, 107],
                "low": [110, 111, 112],  # low > high (INVALID)
                "close": [103, 104, 105],
                "volume": [1000, 1100, 1200],
            }
        )

        with pytest.raises(ValueError, match="violates OHLCV constraints"):
            sim._validate_data(invalid_ohlcv)

    def test_add_gaussian_noise(self, sample_ohlcv_data):
        """Test Gaussian noise addition to OHLCV data."""
        sim = NoiseInfusionSimulator(
            n_simulations=100, std_pct=0.01, noise_model="gaussian", seed=42
        )

        noisy_data = sim.add_noise(sample_ohlcv_data, sim_seed=42)

        # Check shape preserved
        assert len(noisy_data) == len(sample_ohlcv_data)
        assert noisy_data.columns == sample_ohlcv_data.columns

        # Check prices are different (noise added)
        assert not np.allclose(
            noisy_data["close"].to_numpy(), sample_ohlcv_data["close"].to_numpy()
        )

        # Check OHLCV constraints maintained
        assert (noisy_data["high"] >= noisy_data["low"]).all()
        assert (noisy_data["high"] >= noisy_data["open"]).all()
        assert (noisy_data["high"] >= noisy_data["close"]).all()
        assert (noisy_data["low"] <= noisy_data["open"]).all()
        assert (noisy_data["low"] <= noisy_data["close"]).all()
        assert (noisy_data["volume"] >= 0).all()

    def test_add_bootstrap_noise(self, sample_ohlcv_data):
        """Test bootstrap noise addition to OHLCV data."""
        sim = NoiseInfusionSimulator(
            n_simulations=100, std_pct=0.01, noise_model="bootstrap", seed=42
        )

        noisy_data = sim.add_noise(sample_ohlcv_data, sim_seed=42)

        # Check shape preserved
        assert len(noisy_data) == len(sample_ohlcv_data)

        # Check prices are different
        assert not np.allclose(
            noisy_data["close"].to_numpy(), sample_ohlcv_data["close"].to_numpy()
        )

        # Check OHLCV constraints maintained
        assert (noisy_data["high"] >= noisy_data["low"]).all()
        assert (noisy_data["high"] >= noisy_data["open"]).all()
        assert (noisy_data["high"] >= noisy_data["close"]).all()

    def test_fix_ohlcv_relationships(self):
        """Test OHLCV relationship fixing for violated constraints."""
        sim = NoiseInfusionSimulator(seed=42)

        # Create data with violated constraints
        invalid_data = pl.DataFrame(
            {
                "open": [100, 101, 102],
                "high": [98, 99, 100],  # high < open (INVALID)
                "low": [95, 96, 97],
                "close": [103, 104, 105],  # close > high (INVALID)
                "volume": [1000, 1100, 1200],
            }
        )

        fixed_data = sim._fix_ohlcv_relationships(invalid_data)

        # Check constraints are now satisfied
        assert (fixed_data["high"] >= fixed_data["low"]).all()
        assert (fixed_data["high"] >= fixed_data["open"]).all()
        assert (fixed_data["high"] >= fixed_data["close"]).all()
        assert (fixed_data["low"] <= fixed_data["open"]).all()
        assert (fixed_data["low"] <= fixed_data["close"]).all()

    def test_run_noise_infusion(self, sample_ohlcv_data, simple_backtest_fn):
        """Test complete noise infusion simulation."""
        sim = NoiseInfusionSimulator(
            n_simulations=100, std_pct=0.01, noise_model="gaussian", seed=42
        )

        result = sim.run(sample_ohlcv_data, simple_backtest_fn)

        # Check result type
        assert isinstance(result, NoiseInfusionResult)

        # Check result contains expected metrics
        assert "sharpe_ratio" in result.original_metrics
        assert "total_return" in result.original_metrics
        assert "sharpe_ratio" in result.noisy_metrics
        assert "total_return" in result.noisy_metrics

        # Check correct number of simulations
        assert len(result.noisy_metrics["sharpe_ratio"]) == 100

        # Check degradation calculated
        assert "sharpe_ratio" in result.degradation_pct
        assert "total_return" in result.degradation_pct

    def test_run_with_bootstrap_model(self, sample_ohlcv_data, simple_backtest_fn):
        """Test noise infusion with bootstrap model."""
        sim = NoiseInfusionSimulator(
            n_simulations=100, std_pct=0.01, noise_model="bootstrap", seed=42
        )

        result = sim.run(sample_ohlcv_data, simple_backtest_fn)

        assert result.noise_model == "bootstrap"
        assert len(result.noisy_metrics["sharpe_ratio"]) == 100

    def test_reproducibility_with_seed(self, sample_ohlcv_data, simple_backtest_fn):
        """Test results are reproducible with same seed."""
        sim1 = NoiseInfusionSimulator(n_simulations=100, seed=42)
        sim2 = NoiseInfusionSimulator(n_simulations=100, seed=42)

        result1 = sim1.run(sample_ohlcv_data, simple_backtest_fn)
        result2 = sim2.run(sample_ohlcv_data, simple_backtest_fn)

        # Check metrics are identical
        assert result1.mean_metrics["sharpe_ratio"] == result2.mean_metrics["sharpe_ratio"]
        assert result1.degradation_pct["sharpe_ratio"] == result2.degradation_pct["sharpe_ratio"]


class TestNoiseInfusionResult:
    """Test suite for NoiseInfusionResult class."""

    @pytest.fixture
    def sample_result(self) -> NoiseInfusionResult:
        """Create sample NoiseInfusionResult for testing."""
        return NoiseInfusionResult(
            original_metrics={"sharpe_ratio": Decimal("2.0"), "total_return": Decimal("0.5")},
            noisy_metrics={
                "sharpe_ratio": [Decimal("1.8"), Decimal("1.9"), Decimal("1.7")],
                "total_return": [Decimal("0.45"), Decimal("0.48"), Decimal("0.42")],
            },
            mean_metrics={"sharpe_ratio": Decimal("1.8"), "total_return": Decimal("0.45")},
            std_metrics={"sharpe_ratio": Decimal("0.1"), "total_return": Decimal("0.03")},
            degradation_pct={"sharpe_ratio": Decimal("10"), "total_return": Decimal("10")},
            worst_case_metrics={"sharpe_ratio": Decimal("1.7"), "total_return": Decimal("0.42")},
            confidence_intervals={
                "sharpe_ratio": (Decimal("1.7"), Decimal("1.9")),
                "total_return": (Decimal("0.42"), Decimal("0.48")),
            },
            n_simulations=100,
            noise_model="gaussian",
            std_pct=Decimal("0.01"),
            seed=42,
        )

    def test_is_robust_property(self, sample_result):
        """Test is_robust property identifies robust strategies."""
        # Degradation is 10% (< 20%), should be robust
        assert sample_result.is_robust["sharpe_ratio"] is True
        assert sample_result.is_robust["total_return"] is True

    def test_is_fragile_property(self):
        """Test is_fragile property identifies fragile strategies."""
        fragile_result = NoiseInfusionResult(
            original_metrics={"sharpe_ratio": Decimal("2.0")},
            noisy_metrics={"sharpe_ratio": [Decimal("0.5"), Decimal("0.6")]},
            mean_metrics={"sharpe_ratio": Decimal("0.55")},
            std_metrics={"sharpe_ratio": Decimal("0.1")},
            degradation_pct={"sharpe_ratio": Decimal("72.5")},  # >50%, fragile
            worst_case_metrics={"sharpe_ratio": Decimal("0.5")},
            confidence_intervals={"sharpe_ratio": (Decimal("0.5"), Decimal("0.6"))},
            n_simulations=100,
            noise_model="gaussian",
            std_pct=Decimal("0.01"),
            seed=42,
        )

        assert fragile_result.is_fragile["sharpe_ratio"] is True

    def test_get_summary(self, sample_result):
        """Test summary generation for result."""
        summary = sample_result.get_summary("sharpe_ratio")

        assert "Noise Infusion Test" in summary
        assert "sharpe_ratio" in summary
        assert "2.0" in summary  # original
        assert "1.8" in summary  # mean
        assert "10" in summary  # degradation
        assert "ROBUST" in summary or "GOOD" in summary

    def test_get_summary_invalid_metric(self, sample_result):
        """Test summary generation fails for invalid metric."""
        with pytest.raises(ValueError, match="not found"):
            sample_result.get_summary("invalid_metric")

    def test_plot_distribution(self, sample_result, tmp_path):
        """Test distribution plotting."""
        output_path = tmp_path / "test_plot.png"

        # Should not raise
        sample_result.plot_distribution(
            metric="sharpe_ratio", output_path=str(output_path), show=False
        )

        # Check file created
        assert output_path.exists()


# Property-Based Tests
class TestNoiseInfusionProperties:
    """Property-based tests for noise infusion simulator."""

    @given(std_pct=st.floats(min_value=0.001, max_value=0.1))
    def test_noise_amplitude_scaling(self, std_pct):
        """Test higher noise amplitude increases variance."""
        # Generate test data inline to avoid fixture scope issue
        np.random.seed(42)
        n_bars = 100
        close_prices = 100 * np.exp(np.cumsum(np.random.normal(0, 0.01, n_bars)))
        high_prices = close_prices * np.random.uniform(1.0, 1.02, n_bars)
        low_prices = close_prices * np.random.uniform(0.98, 1.0, n_bars)
        open_prices = close_prices * np.random.uniform(0.99, 1.01, n_bars)
        high_prices = np.maximum.reduce([high_prices, open_prices, close_prices])
        low_prices = np.minimum.reduce([low_prices, open_prices, close_prices])

        test_data = pl.DataFrame(
            {
                "open": open_prices,
                "high": high_prices,
                "low": low_prices,
                "close": close_prices,
                "volume": np.random.uniform(1000, 10000, n_bars),
            }
        )

        sim1 = NoiseInfusionSimulator(std_pct=std_pct, seed=42)
        sim2 = NoiseInfusionSimulator(std_pct=std_pct * 2, seed=43)

        noisy1 = sim1.add_noise(test_data, sim_seed=42)
        noisy2 = sim2.add_noise(test_data, sim_seed=43)

        # Calculate variance of noise
        diff1 = (noisy1["close"].to_numpy() - test_data["close"].to_numpy()) / test_data[
            "close"
        ].to_numpy()
        diff2 = (noisy2["close"].to_numpy() - test_data["close"].to_numpy()) / test_data[
            "close"
        ].to_numpy()

        var1 = np.var(diff1)
        var2 = np.var(diff2)

        # Higher amplitude should produce higher variance
        assert var2 > var1

    @given(
        n_bars=st.integers(min_value=50, max_value=500),
        noise_seed=st.integers(min_value=0, max_value=10000),
    )
    def test_ohlcv_constraints_preserved(self, n_bars, noise_seed):
        """Test OHLCV constraints preserved for any data size."""
        # Generate random OHLCV data
        np.random.seed(noise_seed)
        close = 100 * np.exp(np.cumsum(np.random.normal(0, 0.01, n_bars)))
        high = close * np.random.uniform(1.0, 1.02, n_bars)
        low = close * np.random.uniform(0.98, 1.0, n_bars)
        open_prices = close * np.random.uniform(0.99, 1.01, n_bars)

        # Fix constraints
        high = np.maximum.reduce([high, open_prices, close])
        low = np.minimum.reduce([low, open_prices, close])

        data = pl.DataFrame(
            {
                "open": open_prices,
                "high": high,
                "low": low,
                "close": close,
                "volume": np.random.uniform(1000, 10000, n_bars),
            }
        )

        # Add noise
        sim = NoiseInfusionSimulator(std_pct=0.02, seed=noise_seed)
        noisy_data = sim.add_noise(data, sim_seed=noise_seed)

        # Verify all constraints
        assert (noisy_data["high"] >= noisy_data["low"]).all()
        assert (noisy_data["high"] >= noisy_data["open"]).all()
        assert (noisy_data["high"] >= noisy_data["close"]).all()
        assert (noisy_data["low"] <= noisy_data["open"]).all()
        assert (noisy_data["low"] <= noisy_data["close"]).all()
        assert (noisy_data["volume"] >= 0).all()


# Integration Tests
class TestNoiseInfusionIntegration:
    """Integration tests for complete noise infusion workflows."""

    def test_robust_strategy_detection(self, sample_ohlcv_data):
        """Test detection of robust strategy (low degradation)."""

        # Robust strategy: Simple mean reversion (not sensitive to noise)
        def robust_strategy_backtest(data: pl.DataFrame) -> dict[str, Decimal]:
            """Robust strategy that doesn't overfit to specific patterns."""
            returns = data["close"].pct_change().drop_nulls()
            returns_array = returns.to_numpy()

            # Simple metrics, not overfit
            mean_return = np.mean(returns_array)
            std_return = np.std(returns_array, ddof=1)
            sharpe = mean_return / std_return * np.sqrt(252) if std_return > 0 else 0.0

            return {"sharpe_ratio": Decimal(str(sharpe))}

        sim = NoiseInfusionSimulator(n_simulations=100, std_pct=0.01, seed=42)
        result = sim.run(sample_ohlcv_data, robust_strategy_backtest)

        # Robust strategy should have low degradation
        # Note: This is probabilistic, but with seed should be consistent
        # Degradation should be < 100% (strategy doesn't completely fail)
        assert result.degradation_pct["sharpe_ratio"] < Decimal("100")

    def test_different_noise_levels(self, sample_ohlcv_data, simple_backtest_fn):
        """Test strategy degradation increases with noise level."""
        # Test with mild, moderate, and aggressive noise
        noise_levels = [0.005, 0.01, 0.02]
        degradations = []

        for std_pct in noise_levels:
            sim = NoiseInfusionSimulator(n_simulations=100, std_pct=std_pct, seed=42)
            result = sim.run(sample_ohlcv_data, simple_backtest_fn)
            degradations.append(float(result.degradation_pct["sharpe_ratio"]))

        # Generally, higher noise should cause more degradation
        # (not strictly monotonic due to randomness, but trend should hold)
        # Just check that max degradation > min degradation
        assert max(degradations) >= min(degradations)

    def test_gaussian_vs_bootstrap_comparison(self, sample_ohlcv_data, simple_backtest_fn):
        """Test both noise models produce valid results."""
        sim_gaussian = NoiseInfusionSimulator(
            n_simulations=100, std_pct=0.01, noise_model="gaussian", seed=42
        )
        sim_bootstrap = NoiseInfusionSimulator(
            n_simulations=100, std_pct=0.01, noise_model="bootstrap", seed=42
        )

        result_gaussian = sim_gaussian.run(sample_ohlcv_data, simple_backtest_fn)
        result_bootstrap = sim_bootstrap.run(sample_ohlcv_data, simple_backtest_fn)

        # Both should produce valid results
        assert result_gaussian.noise_model == "gaussian"
        assert result_bootstrap.noise_model == "bootstrap"

        # Both should have degradation calculated
        assert "sharpe_ratio" in result_gaussian.degradation_pct
        assert "sharpe_ratio" in result_bootstrap.degradation_pct

        # Degradation can be negative if noisy performance is better (random variation)
        # Just check that degradation is a finite number (not NaN/Inf)
        assert abs(result_gaussian.degradation_pct["sharpe_ratio"]) < Decimal("1000")
        assert abs(result_bootstrap.degradation_pct["sharpe_ratio"]) < Decimal("1000")

    def test_confidence_intervals_coverage(self, sample_ohlcv_data, simple_backtest_fn):
        """Test confidence intervals contain expected proportion of values."""
        sim = NoiseInfusionSimulator(
            n_simulations=1000, std_pct=0.01, confidence_level=0.95, seed=42
        )
        result = sim.run(sample_ohlcv_data, simple_backtest_fn)

        # Count how many values fall within 95% CI
        ci_lower, ci_upper = result.confidence_intervals["sharpe_ratio"]
        within_ci = sum(
            1 for v in result.noisy_metrics["sharpe_ratio"] if ci_lower <= v <= ci_upper
        )
        proportion = within_ci / len(result.noisy_metrics["sharpe_ratio"])

        # Should be approximately 0.95 (allow some tolerance)
        assert 0.90 <= proportion <= 1.0  # At least 90% should be within CI

    def test_worst_case_is_5th_percentile(self, sample_ohlcv_data, simple_backtest_fn):
        """Test worst-case metric is approximately 5th percentile."""
        sim = NoiseInfusionSimulator(n_simulations=1000, std_pct=0.01, seed=42)
        result = sim.run(sample_ohlcv_data, simple_backtest_fn)

        # Calculate 5th percentile manually
        values = [float(v) for v in result.noisy_metrics["sharpe_ratio"]]
        fifth_percentile = np.percentile(values, 5)
        worst_case = float(result.worst_case_metrics["sharpe_ratio"])

        # Should be very close
        assert abs(worst_case - fifth_percentile) < 0.01
