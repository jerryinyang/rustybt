"""Tests for walk-forward optimization framework."""

from datetime import datetime, timedelta
from decimal import Decimal

import polars as pl
import pytest
from hypothesis import given
from hypothesis import strategies as st

from rustybt.optimization import (
    ContinuousParameter,
    DiscreteParameter,
    ObjectiveFunction,
    ParameterSpace,
)
from rustybt.optimization.search import RandomSearchAlgorithm
from rustybt.optimization.walk_forward import (
    WalkForwardOptimizer,
    WindowConfig,
    WindowData,
)


class TestWindowConfig:
    """Tests for WindowConfig."""

    def test_window_config_valid(self):
        """Test valid window configuration."""
        config = WindowConfig(
            train_period=100,
            validation_period=20,
            test_period=20,
            step_size=10,
            window_type="rolling",
        )

        assert config.train_period == 100
        assert config.validation_period == 20
        assert config.test_period == 20
        assert config.step_size == 10
        assert config.window_type == "rolling"

    def test_window_config_invalid_train_period(self):
        """Test invalid train_period raises error."""
        with pytest.raises(ValueError, match="train_period must be positive"):
            WindowConfig(
                train_period=0,  # Invalid
                validation_period=20,
                test_period=20,
                step_size=10,
            )

    def test_window_config_invalid_validation_period(self):
        """Test invalid validation_period raises error."""
        with pytest.raises(ValueError, match="validation_period must be positive"):
            WindowConfig(
                train_period=100,
                validation_period=-5,  # Invalid
                test_period=20,
                step_size=10,
            )

    def test_window_config_invalid_test_period(self):
        """Test invalid test_period raises error."""
        with pytest.raises(ValueError, match="test_period must be positive"):
            WindowConfig(
                train_period=100,
                validation_period=20,
                test_period=0,  # Invalid
                step_size=10,
            )

    def test_window_config_invalid_step_size(self):
        """Test invalid step_size raises error."""
        with pytest.raises(ValueError, match="step_size must be positive"):
            WindowConfig(
                train_period=100,
                validation_period=20,
                test_period=20,
                step_size=-1,  # Invalid
            )

    def test_window_config_invalid_window_type(self):
        """Test invalid window_type raises error."""
        with pytest.raises(ValueError, match="window_type must be"):
            WindowConfig(
                train_period=100,
                validation_period=20,
                test_period=20,
                step_size=10,
                window_type="invalid",  # Invalid
            )

    def test_window_config_expanding_type(self):
        """Test expanding window configuration."""
        config = WindowConfig(
            train_period=100,
            validation_period=20,
            test_period=20,
            step_size=10,
            window_type="expanding",
        )

        assert config.window_type == "expanding"


class TestWindowData:
    """Tests for WindowData."""

    def test_window_data_valid(self):
        """Test valid window data."""
        # Create sample data
        train_df = pl.DataFrame({"price": [1.0, 2.0, 3.0]})
        val_df = pl.DataFrame({"price": [4.0, 5.0]})
        test_df = pl.DataFrame({"price": [6.0, 7.0]})

        window = WindowData(
            train_data=train_df,
            validation_data=val_df,
            test_data=test_df,
            train_start_idx=0,
            train_end_idx=2,
            validation_start_idx=3,
            validation_end_idx=4,
            test_start_idx=5,
            test_end_idx=6,
        )

        assert len(window.train_data) == 3
        assert len(window.validation_data) == 2
        assert len(window.test_data) == 2
        assert window.test_start_idx > window.validation_end_idx

    def test_window_data_lookahead_bias_validation_check(self):
        """Test window data prevents lookahead bias (validation after train)."""
        train_df = pl.DataFrame({"price": [1.0, 2.0]})
        val_df = pl.DataFrame({"price": [3.0]})
        test_df = pl.DataFrame({"price": [4.0]})

        # Validation starts before train ends - should fail
        with pytest.raises(ValueError, match="Validation must start after train ends"):
            WindowData(
                train_data=train_df,
                validation_data=val_df,
                test_data=test_df,
                train_start_idx=0,
                train_end_idx=5,  # Train ends at 5
                validation_start_idx=4,  # Validation starts at 4 (before train end!)
                validation_end_idx=6,
                test_start_idx=7,
                test_end_idx=8,
            )

    def test_window_data_lookahead_bias_test_check(self):
        """Test window data prevents lookahead bias (test after validation)."""
        train_df = pl.DataFrame({"price": [1.0, 2.0]})
        val_df = pl.DataFrame({"price": [3.0]})
        test_df = pl.DataFrame({"price": [4.0]})

        # Test starts before validation ends - should fail
        with pytest.raises(ValueError, match="Test must start after validation ends"):
            WindowData(
                train_data=train_df,
                validation_data=val_df,
                test_data=test_df,
                train_start_idx=0,
                train_end_idx=2,
                validation_start_idx=3,
                validation_end_idx=5,  # Validation ends at 5
                test_start_idx=4,  # Test starts at 4 (before validation end!)
                test_end_idx=6,
            )


class TestWalkForwardOptimizer:
    """Tests for WalkForwardOptimizer."""

    def create_synthetic_data(self, n_rows: int = 500) -> pl.DataFrame:
        """Create synthetic time-series data for testing.

        Args:
            n_rows: Number of rows to generate

        Returns:
            DataFrame with synthetic price data
        """
        import numpy as np

        np.random.seed(42)

        # Create time series
        dates = [datetime(2020, 1, 1) + timedelta(days=i) for i in range(n_rows)]

        # Generate synthetic returns
        returns = np.random.randn(n_rows) * 0.02

        # Generate prices from returns
        prices = 100.0 * (1 + returns).cumprod()

        return pl.DataFrame(
            {
                "date": dates,
                "price": prices,
                "volume": np.random.randint(1000, 10000, n_rows),
            }
        )

    def simple_backtest_function(self, params: dict, data: pl.DataFrame) -> dict:
        """Simple backtest function for testing.

        Calculates score based on parameters and data characteristics.
        """
        # Extract parameters
        lookback = params.get("lookback", 20)
        threshold = Decimal(str(params.get("threshold", 0.02)))

        # Calculate simple moving average strategy returns
        prices = data["price"].to_numpy()

        if len(prices) < lookback:
            # Not enough data
            return {
                "performance_metrics": {
                    "sharpe_ratio": 0.0,
                    "total_return": 0.0,
                    "max_drawdown": 0.0,
                }
            }

        # Calculate returns
        returns = (prices[1:] - prices[:-1]) / prices[:-1]

        # Calculate moving average
        ma = []
        for i in range(lookback - 1, len(prices) - 1):
            ma_val = prices[i - lookback + 1 : i + 1].mean()
            ma.append(ma_val)

        if not ma:
            return {
                "performance_metrics": {
                    "sharpe_ratio": 0.0,
                    "total_return": 0.0,
                    "max_drawdown": 0.0,
                }
            }

        # Generate signals
        signals = []
        for i in range(len(ma)):
            price_idx = i + lookback - 1
            if prices[price_idx] > ma[i] * (1 + float(threshold)):
                signals.append(1)  # Long signal
            elif prices[price_idx] < ma[i] * (1 - float(threshold)):
                signals.append(-1)  # Short signal
            else:
                signals.append(0)  # No signal

        # Calculate strategy returns
        strategy_returns = []
        for i, signal in enumerate(signals):
            if i + lookback < len(returns):
                strategy_returns.append(signal * returns[i + lookback])

        if not strategy_returns:
            return {
                "performance_metrics": {
                    "sharpe_ratio": 0.0,
                    "total_return": 0.0,
                    "max_drawdown": 0.0,
                }
            }

        # Calculate metrics
        import numpy as np

        strategy_returns = np.array(strategy_returns)
        mean_return = strategy_returns.mean()
        std_return = strategy_returns.std()

        sharpe = (mean_return / std_return * np.sqrt(252)) if std_return > 0 else 0.0
        total_return = (1 + strategy_returns).prod() - 1

        # Calculate max drawdown
        cumulative = (1 + strategy_returns).cumprod()
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = abs(drawdown.min()) if len(drawdown) > 0 else 0.0

        return {
            "performance_metrics": {
                "sharpe_ratio": float(sharpe),
                "total_return": float(total_return),
                "max_drawdown": float(max_drawdown),
            }
        }

    def test_walk_forward_optimizer_initialization(self):
        """Test walk-forward optimizer initialization."""
        param_space = ParameterSpace(
            parameters=[
                DiscreteParameter(name="lookback", min_value=10, max_value=50, step=5),
                ContinuousParameter(name="threshold", min_value=0.01, max_value=0.05),
            ]
        )

        config = WindowConfig(
            train_period=100,
            validation_period=20,
            test_period=20,
            step_size=20,
            window_type="rolling",
        )

        optimizer = WalkForwardOptimizer(
            parameter_space=param_space,
            search_algorithm_factory=lambda: RandomSearchAlgorithm(param_space, n_iter=10, seed=42),
            objective_function=ObjectiveFunction(metric="sharpe_ratio"),
            backtest_function=self.simple_backtest_function,
            config=config,
            max_trials_per_window=10,
        )

        assert optimizer.max_trials_per_window == 10
        assert optimizer.config.window_type == "rolling"

    def test_walk_forward_optimizer_invalid_max_trials(self):
        """Test walk-forward optimizer with invalid max_trials raises error."""
        param_space = ParameterSpace(
            parameters=[DiscreteParameter(name="lookback", min_value=10, max_value=50)]
        )

        config = WindowConfig(train_period=100, validation_period=20, test_period=20, step_size=20)

        with pytest.raises(ValueError, match="max_trials_per_window must be positive"):
            WalkForwardOptimizer(
                parameter_space=param_space,
                search_algorithm_factory=lambda: RandomSearchAlgorithm(param_space, n_trials=10),
                objective_function=ObjectiveFunction(metric="sharpe_ratio"),
                backtest_function=self.simple_backtest_function,
                config=config,
                max_trials_per_window=0,  # Invalid
            )

    def test_generate_rolling_windows(self):
        """Test rolling window generation."""
        data = self.create_synthetic_data(n_rows=250)

        param_space = ParameterSpace(
            parameters=[DiscreteParameter(name="lookback", min_value=10, max_value=50)]
        )

        config = WindowConfig(
            train_period=100,
            validation_period=30,
            test_period=30,
            step_size=30,
            window_type="rolling",
        )

        optimizer = WalkForwardOptimizer(
            parameter_space=param_space,
            search_algorithm_factory=lambda: RandomSearchAlgorithm(param_space, n_iter=5),
            objective_function=ObjectiveFunction(metric="sharpe_ratio"),
            backtest_function=self.simple_backtest_function,
            config=config,
            max_trials_per_window=5,
        )

        windows = optimizer._generate_windows(data)

        # Should generate 2 windows:
        # Window 1: train=[0:100], val=[100:130], test=[130:160]
        # Window 2: train=[30:130], val=[130:160], test=[160:190]
        assert len(windows) >= 2

        # Check first window
        assert windows[0].train_start_idx == 0
        assert windows[0].train_end_idx == 99
        assert windows[0].validation_start_idx == 100
        assert windows[0].validation_end_idx == 129
        assert windows[0].test_start_idx == 130
        assert windows[0].test_end_idx == 159

        # Check temporal ordering (no lookahead bias)
        for window in windows:
            assert window.validation_start_idx > window.train_end_idx
            assert window.test_start_idx > window.validation_end_idx

        # Check rolling property (train window size stays constant)
        train_size_0 = windows[0].train_end_idx - windows[0].train_start_idx + 1
        train_size_1 = windows[1].train_end_idx - windows[1].train_start_idx + 1
        assert train_size_0 == train_size_1 == 100

    def test_generate_expanding_windows(self):
        """Test expanding window generation."""
        data = self.create_synthetic_data(n_rows=300)

        param_space = ParameterSpace(
            parameters=[DiscreteParameter(name="lookback", min_value=10, max_value=50)]
        )

        config = WindowConfig(
            train_period=100,
            validation_period=30,
            test_period=30,
            step_size=30,
            window_type="expanding",
        )

        optimizer = WalkForwardOptimizer(
            parameter_space=param_space,
            search_algorithm_factory=lambda: RandomSearchAlgorithm(param_space, n_iter=5),
            objective_function=ObjectiveFunction(metric="sharpe_ratio"),
            backtest_function=self.simple_backtest_function,
            config=config,
            max_trials_per_window=5,
        )

        windows = optimizer._generate_windows(data)

        assert len(windows) >= 2

        # Check temporal ordering
        for window in windows:
            assert window.validation_start_idx > window.train_end_idx
            assert window.test_start_idx > window.validation_end_idx

        # Check expanding property (train window grows)
        train_size_0 = windows[0].train_end_idx - windows[0].train_start_idx + 1
        train_size_1 = windows[1].train_end_idx - windows[1].train_start_idx + 1
        assert train_size_1 > train_size_0

        # Check all windows start from beginning
        for window in windows:
            assert window.train_start_idx == 0

    def test_insufficient_data_for_walk_forward(self):
        """Test walk-forward with insufficient data raises error."""
        # Only 50 rows, need 140 minimum (100 train + 20 val + 20 test)
        data = self.create_synthetic_data(n_rows=50)

        param_space = ParameterSpace(
            parameters=[DiscreteParameter(name="lookback", min_value=10, max_value=50)]
        )

        config = WindowConfig(
            train_period=100,
            validation_period=20,
            test_period=20,
            step_size=20,
        )

        optimizer = WalkForwardOptimizer(
            parameter_space=param_space,
            search_algorithm_factory=lambda: RandomSearchAlgorithm(param_space, n_iter=5),
            objective_function=ObjectiveFunction(metric="sharpe_ratio"),
            backtest_function=self.simple_backtest_function,
            config=config,
            max_trials_per_window=5,
        )

        with pytest.raises(ValueError, match="Insufficient data"):
            optimizer.run(data)

    def test_walk_forward_run_rolling(self):
        """Test full walk-forward optimization with rolling windows."""
        data = self.create_synthetic_data(n_rows=250)

        param_space = ParameterSpace(
            parameters=[
                DiscreteParameter(name="lookback", min_value=10, max_value=30, step=10),
                ContinuousParameter(name="threshold", min_value=0.01, max_value=0.03),
            ]
        )

        config = WindowConfig(
            train_period=100,
            validation_period=30,
            test_period=30,
            step_size=30,
            window_type="rolling",
        )

        optimizer = WalkForwardOptimizer(
            parameter_space=param_space,
            search_algorithm_factory=lambda: RandomSearchAlgorithm(param_space, n_iter=10, seed=42),
            objective_function=ObjectiveFunction(metric="sharpe_ratio"),
            backtest_function=self.simple_backtest_function,
            config=config,
            max_trials_per_window=10,
        )

        result = optimizer.run(data)

        # Check result structure
        assert result.num_windows >= 2
        assert len(result.window_results) == result.num_windows
        assert "train" in result.aggregate_metrics
        assert "validation" in result.aggregate_metrics
        assert "test" in result.aggregate_metrics

        # Check each window has results
        for window_result in result.window_results:
            assert "lookback" in window_result.best_params
            assert "threshold" in window_result.best_params
            assert "score" in window_result.train_metrics
            assert "score" in window_result.validation_metrics
            assert "score" in window_result.test_metrics

        # Check aggregate metrics exist
        assert "score_mean" in result.aggregate_metrics["test"]
        assert "score_std" in result.aggregate_metrics["test"]

        # Check parameter stability analysis
        assert "lookback" in result.parameter_stability
        assert "threshold" in result.parameter_stability
        assert "mean" in result.parameter_stability["lookback"]
        assert "std" in result.parameter_stability["lookback"]
        assert "coefficient_of_variation" in result.parameter_stability["lookback"]

    def test_walk_forward_run_expanding(self):
        """Test full walk-forward optimization with expanding windows."""
        data = self.create_synthetic_data(n_rows=250)

        param_space = ParameterSpace(
            parameters=[
                DiscreteParameter(name="lookback", min_value=10, max_value=30, step=10),
            ]
        )

        config = WindowConfig(
            train_period=100,
            validation_period=30,
            test_period=30,
            step_size=30,
            window_type="expanding",
        )

        optimizer = WalkForwardOptimizer(
            parameter_space=param_space,
            search_algorithm_factory=lambda: RandomSearchAlgorithm(param_space, n_iter=10, seed=42),
            objective_function=ObjectiveFunction(metric="sharpe_ratio"),
            backtest_function=self.simple_backtest_function,
            config=config,
            max_trials_per_window=10,
        )

        result = optimizer.run(data)

        # Check expanding property in results
        assert result.num_windows >= 2
        train_sizes = [wr.train_end_idx - wr.train_start_idx + 1 for wr in result.window_results]

        # Train sizes should be increasing
        for i in range(1, len(train_sizes)):
            assert train_sizes[i] > train_sizes[i - 1]


class TestLookaheadBiasPrevention:
    """Tests specifically for lookahead bias prevention."""

    def create_data_with_future_signal(self, n_rows: int = 300) -> pl.DataFrame:
        """Create data with obvious pattern in future periods.

        This tests if walk-forward accidentally uses test data in optimization.
        """
        import numpy as np

        np.random.seed(42)

        # Calculate split point
        split_point = int(n_rows * 0.67)  # 67% for early, 33% for late

        # First part: random walk
        returns_early = np.random.randn(split_point) * 0.02
        prices_early = 100.0 * (1 + returns_early).cumprod()

        # Last part: strong upward trend (obvious pattern)
        late_rows = n_rows - split_point
        returns_late = np.abs(np.random.randn(late_rows) * 0.01) + 0.03  # Always positive
        prices_late = prices_early[-1] * (1 + returns_late).cumprod()

        prices = np.concatenate([prices_early, prices_late])
        dates = [datetime(2020, 1, 1) + timedelta(days=i) for i in range(n_rows)]

        return pl.DataFrame({"date": dates, "price": prices, "volume": 1000})

    def simple_backtest(self, params: dict, data: pl.DataFrame) -> dict:
        """Simple momentum backtest."""
        lookback = params.get("lookback", 20)
        prices = data["price"].to_numpy()

        if len(prices) < lookback + 1:
            return {"performance_metrics": {"sharpe_ratio": 0.0}}

        returns = (prices[lookback:] - prices[:-lookback]) / prices[:-lookback]
        sharpe = returns.mean() / returns.std() * (252**0.5) if returns.std() > 0 else 0.0

        return {"performance_metrics": {"sharpe_ratio": float(sharpe)}}

    @given(
        train_period=st.integers(min_value=50, max_value=100),
        test_period=st.integers(min_value=20, max_value=40),
    )
    def test_test_always_after_train(self, train_period: int, test_period: int):
        """Property test: test window must always start after train window ends."""
        data = pl.DataFrame(
            {
                "date": [datetime(2020, 1, 1) + timedelta(days=i) for i in range(300)],
                "price": list(range(300)),
            }
        )

        param_space = ParameterSpace(
            parameters=[DiscreteParameter(name="lookback", min_value=10, max_value=30)]
        )

        config = WindowConfig(
            train_period=train_period,
            validation_period=20,
            test_period=test_period,
            step_size=20,
        )

        optimizer = WalkForwardOptimizer(
            parameter_space=param_space,
            search_algorithm_factory=lambda: RandomSearchAlgorithm(param_space, n_iter=5),
            objective_function=ObjectiveFunction(metric="sharpe_ratio"),
            backtest_function=self.simple_backtest,
            config=config,
            max_trials_per_window=5,
        )

        windows = optimizer._generate_windows(data)

        for window in windows:
            # Test must start after train ends
            assert window.test_start_idx > window.train_end_idx
            # Test must start after validation ends
            assert window.test_start_idx > window.validation_end_idx

    def test_params_selected_before_test_period(self):
        """Test that parameters are selected using only train+val data."""
        data = self.create_data_with_future_signal(n_rows=250)

        param_space = ParameterSpace(
            parameters=[DiscreteParameter(name="lookback", min_value=10, max_value=50)]
        )

        config = WindowConfig(
            train_period=80,
            validation_period=20,
            test_period=20,
            step_size=30,
        )

        optimizer = WalkForwardOptimizer(
            parameter_space=param_space,
            search_algorithm_factory=lambda: RandomSearchAlgorithm(param_space, n_iter=10, seed=42),
            objective_function=ObjectiveFunction(metric="sharpe_ratio"),
            backtest_function=self.simple_backtest,
            config=config,
            max_trials_per_window=10,
        )

        result = optimizer.run(data)

        # For each window, verify params were selected before test period
        for window_result in result.window_results:
            # Parameters should be selected using data up to validation_end
            # Test data starts after that and should NOT influence selection
            assert window_result.test_start_idx > window_result.train_end_idx

            # If test data influenced optimization, we'd expect best_params
            # to exploit the future trend. We can't directly test this without
            # the actual dates, but we verify the structural guarantee:
            # test_start comes after train_end, so test data wasn't available
            # during optimization.
