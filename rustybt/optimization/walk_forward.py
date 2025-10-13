"""Walk-forward optimization for time-series robustness validation.

This module implements walk-forward analysis to validate strategy robustness
across multiple time windows, preventing overfitting to specific periods.
"""

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

import polars as pl
import structlog

from rustybt.optimization.base import SearchAlgorithm
from rustybt.optimization.objective import ObjectiveFunction
from rustybt.optimization.optimizer import Optimizer
from rustybt.optimization.parameter_space import ParameterSpace

logger = structlog.get_logger()


@dataclass
class WindowConfig:
    """Configuration for walk-forward window generation.

    Args:
        train_period: Number of days for in-sample optimization
        validation_period: Number of days for parameter selection
        test_period: Number of days for out-of-sample testing
        step_size: Number of days to advance each window
        window_type: 'rolling' (fixed size) or 'expanding' (growing train)

    Example:
        >>> config = WindowConfig(
        ...     train_period=250,
        ...     validation_period=50,
        ...     test_period=50,
        ...     step_size=50,
        ...     window_type='rolling'
        ... )
    """

    train_period: int
    validation_period: int
    test_period: int
    step_size: int
    window_type: Literal["rolling", "expanding"] = "rolling"

    def __post_init__(self):
        """Validate configuration."""
        if self.train_period <= 0:
            raise ValueError("train_period must be positive")
        if self.validation_period <= 0:
            raise ValueError("validation_period must be positive")
        if self.test_period <= 0:
            raise ValueError("test_period must be positive")
        if self.step_size <= 0:
            raise ValueError("step_size must be positive")
        if self.window_type not in ("rolling", "expanding"):
            raise ValueError("window_type must be 'rolling' or 'expanding'")


@dataclass
class WindowData:
    """Data for a single walk-forward window.

    Attributes:
        train_data: Training data for optimization
        validation_data: Validation data for parameter selection
        test_data: Test data for out-of-sample evaluation
        train_start_idx: Starting index of train window
        train_end_idx: Ending index of train window
        validation_start_idx: Starting index of validation window
        validation_end_idx: Ending index of validation window
        test_start_idx: Starting index of test window
        test_end_idx: Ending index of test window
    """

    train_data: pl.DataFrame
    validation_data: pl.DataFrame
    test_data: pl.DataFrame
    train_start_idx: int
    train_end_idx: int
    validation_start_idx: int
    validation_end_idx: int
    test_start_idx: int
    test_end_idx: int

    def __post_init__(self):
        """Validate window data prevents lookahead bias."""
        # Verify temporal ordering
        if self.validation_start_idx <= self.train_end_idx:
            raise ValueError(
                f"Validation must start after train ends: "
                f"val_start={self.validation_start_idx}, train_end={self.train_end_idx}"
            )
        if self.test_start_idx <= self.validation_end_idx:
            raise ValueError(
                f"Test must start after validation ends: "
                f"test_start={self.test_start_idx}, val_end={self.validation_end_idx}"
            )


@dataclass
class WindowResult:
    """Results from a single walk-forward window.

    Attributes:
        window_id: Index of this window
        best_params: Best parameters selected from validation
        train_metrics: Performance metrics on train data
        validation_metrics: Performance metrics on validation data
        test_metrics: Performance metrics on test data (out-of-sample)
        train_start_idx: Starting index of train window
        train_end_idx: Ending index of train window
        test_start_idx: Starting index of test window
        test_end_idx: Ending index of test window
        optimization_trials: Number of trials run during optimization
    """

    window_id: int
    best_params: dict[str, Any]
    train_metrics: dict[str, Any]
    validation_metrics: dict[str, Any]
    test_metrics: dict[str, Any]
    train_start_idx: int
    train_end_idx: int
    test_start_idx: int
    test_end_idx: int
    optimization_trials: int


@dataclass
class WalkForwardResult:
    """Aggregated results from walk-forward optimization.

    Attributes:
        window_results: Results from each window
        aggregate_metrics: Aggregated performance metrics across all windows
        parameter_stability: Statistics on parameter drift across windows
        num_windows: Total number of windows evaluated
        config: Walk-forward configuration used
    """

    window_results: list[WindowResult]
    aggregate_metrics: dict[str, dict[str, Decimal]]
    parameter_stability: dict[str, dict[str, Decimal]]
    num_windows: int
    config: WindowConfig


class WalkForwardOptimizer:
    """Walk-forward optimization for time-series robustness validation.

    Prevents overfitting by optimizing on in-sample data and validating on
    out-of-sample data across multiple time windows. Tracks parameter stability
    as a robustness indicator.

    Best for:
        - Time-series strategies (backtest validation)
        - Detecting overfitting to specific time periods
        - Assessing parameter stability over time
        - Production strategy validation

    Args:
        parameter_space: Parameter search space
        search_algorithm_factory: Factory function to create SearchAlgorithm instances
        objective_function: Metric extraction from backtest results
        backtest_function: Function that runs backtest given parameters and data
        config: Walk-forward window configuration
        max_trials_per_window: Maximum optimization trials per window

    Example:
        >>> wf = WalkForwardOptimizer(
        ...     parameter_space=ParameterSpace(...),
        ...     search_algorithm_factory=lambda: BayesianOptimizer(...),
        ...     objective_function=ObjectiveFunction(ObjectiveMetric.SHARPE_RATIO),
        ...     backtest_function=run_backtest,
        ...     config=WindowConfig(
        ...         train_period=250,
        ...         validation_period=50,
        ...         test_period=50,
        ...         step_size=50,
        ...         window_type='rolling'
        ...     ),
        ...     max_trials_per_window=100
        ... )
        >>> results = wf.run(data)
        >>> print(f"Test Sharpe: {results.aggregate_metrics['test']['sharpe_ratio']}")
    """

    def __init__(
        self,
        parameter_space: ParameterSpace,
        search_algorithm_factory: Callable[[], SearchAlgorithm],
        objective_function: ObjectiveFunction,
        backtest_function: Callable[[dict[str, Any], pl.DataFrame], dict[str, Any]],
        config: WindowConfig,
        max_trials_per_window: int = 100,
    ):
        """Initialize walk-forward optimizer."""
        self.parameter_space = parameter_space
        self.search_algorithm_factory = search_algorithm_factory
        self.objective_function = objective_function
        self.backtest_function = backtest_function
        self.config = config
        self.max_trials_per_window = max_trials_per_window

        # Validation
        if max_trials_per_window <= 0:
            raise ValueError("max_trials_per_window must be positive")

    def run(self, data: pl.DataFrame) -> WalkForwardResult:
        """Run walk-forward optimization.

        Args:
            data: Time-series data for optimization (must have time index)

        Returns:
            WalkForwardResult with aggregated metrics and parameter stability

        Raises:
            ValueError: If data is insufficient for walk-forward analysis
        """
        logger.info(
            "walk_forward_started",
            config=self.config,
            data_length=len(data),
            max_trials_per_window=self.max_trials_per_window,
        )

        # Generate windows
        windows = self._generate_windows(data)

        if not windows:
            raise ValueError(
                f"Insufficient data for walk-forward analysis. "
                f"Need at least {self._min_required_rows()} rows, got {len(data)}"
            )

        logger.info("walk_forward_windows_generated", num_windows=len(windows))

        # Process each window
        window_results: list[WindowResult] = []
        for window_id, window_data in enumerate(windows):
            logger.info(
                "walk_forward_window_started",
                window_id=window_id,
                train_range=(window_data.train_start_idx, window_data.train_end_idx),
                validation_range=(
                    window_data.validation_start_idx,
                    window_data.validation_end_idx,
                ),
                test_range=(window_data.test_start_idx, window_data.test_end_idx),
            )

            window_result = self._process_window(window_id, window_data)
            window_results.append(window_result)

            # Log overfitting warning if test << validation
            val_score = window_result.validation_metrics.get("score", Decimal(0))
            test_score = window_result.test_metrics.get("score", Decimal(0))
            if test_score < val_score * Decimal("0.7"):  # >30% degradation
                logger.warning(
                    "potential_overfitting_detected",
                    window_id=window_id,
                    validation_score=str(val_score),
                    test_score=str(test_score),
                    degradation_pct=(
                        str((1 - test_score / val_score) * 100) if val_score != 0 else "inf"
                    ),
                )

        # Aggregate results
        aggregate_metrics = self._aggregate_metrics(window_results)
        parameter_stability = self._analyze_parameter_stability(window_results)

        result = WalkForwardResult(
            window_results=window_results,
            aggregate_metrics=aggregate_metrics,
            parameter_stability=parameter_stability,
            num_windows=len(window_results),
            config=self.config,
        )

        logger.info(
            "walk_forward_completed",
            num_windows=len(window_results),
            test_sharpe_mean=str(aggregate_metrics.get("test", {}).get("sharpe_ratio_mean", "N/A")),
            test_sharpe_std=str(aggregate_metrics.get("test", {}).get("sharpe_ratio_std", "N/A")),
        )

        return result

    def _generate_windows(self, data: pl.DataFrame) -> list[WindowData]:
        """Generate walk-forward windows from data.

        Args:
            data: Time-series data

        Returns:
            List of WindowData objects
        """
        windows: list[WindowData] = []
        data_length = len(data)

        # Calculate minimum required length
        min_length = self._min_required_rows()
        if data_length < min_length:
            return []

        if self.config.window_type == "rolling":
            # Rolling window: fixed size, slides forward
            train_start = 0

            while True:
                train_end = train_start + self.config.train_period
                val_start = train_end
                val_end = val_start + self.config.validation_period
                test_start = val_end
                test_end = test_start + self.config.test_period

                # Check if we have enough data
                if test_end > data_length:
                    break

                # Extract window data
                train_data = data.slice(train_start, self.config.train_period)
                validation_data = data.slice(val_start, self.config.validation_period)
                test_data = data.slice(test_start, self.config.test_period)

                # Create window
                window = WindowData(
                    train_data=train_data,
                    validation_data=validation_data,
                    test_data=test_data,
                    train_start_idx=train_start,
                    train_end_idx=train_end - 1,
                    validation_start_idx=val_start,
                    validation_end_idx=val_end - 1,
                    test_start_idx=test_start,
                    test_end_idx=test_end - 1,
                )
                windows.append(window)

                # Advance by step_size
                train_start += self.config.step_size

        else:  # expanding
            # Expanding window: train grows, validation/test fixed size
            # First window uses train_period as initial train size
            current_train_end = self.config.train_period

            while True:
                train_start = 0  # Always start from beginning
                train_end = current_train_end
                val_start = train_end
                val_end = val_start + self.config.validation_period
                test_start = val_end
                test_end = test_start + self.config.test_period

                # Check if we have enough data
                if test_end > data_length:
                    break

                # Extract window data
                train_length = train_end - train_start
                train_data = data.slice(train_start, train_length)
                validation_data = data.slice(val_start, self.config.validation_period)
                test_data = data.slice(test_start, self.config.test_period)

                # Create window
                window = WindowData(
                    train_data=train_data,
                    validation_data=validation_data,
                    test_data=test_data,
                    train_start_idx=train_start,
                    train_end_idx=train_end - 1,
                    validation_start_idx=val_start,
                    validation_end_idx=val_end - 1,
                    test_start_idx=test_start,
                    test_end_idx=test_end - 1,
                )
                windows.append(window)

                # Expand train window by step_size
                current_train_end += self.config.step_size

        return windows

    def _min_required_rows(self) -> int:
        """Calculate minimum rows required for walk-forward.

        Returns:
            Minimum number of rows needed
        """
        return self.config.train_period + self.config.validation_period + self.config.test_period

    def _process_window(self, window_id: int, window: WindowData) -> WindowResult:
        """Process a single walk-forward window.

        Args:
            window_id: Index of this window
            window: Window data

        Returns:
            WindowResult with performance metrics
        """
        # Create optimizer for this window
        search_algorithm = self.search_algorithm_factory()

        # Create wrapper for backtest function that uses window data
        def train_backtest_fn(params: dict[str, Any]) -> dict[str, Any]:
            return self.backtest_function(params, window.train_data)

        optimizer = Optimizer(
            parameter_space=self.parameter_space,
            search_algorithm=search_algorithm,
            objective_function=self.objective_function,
            backtest_function=train_backtest_fn,
            max_trials=self.max_trials_per_window,
        )

        # Run optimization on training data
        train_best_result = optimizer.optimize()
        best_params = train_best_result.params

        logger.info(
            "window_optimization_completed",
            window_id=window_id,
            best_params=best_params,
            train_score=str(train_best_result.score),
            trials_run=len(optimizer.results),
        )

        # Evaluate on validation data to get validation metrics
        validation_result = self.backtest_function(best_params, window.validation_data)
        validation_score = self.objective_function.evaluate(validation_result)
        validation_metrics = {
            **validation_result.get("performance_metrics", {}),
            "score": validation_score,
        }

        # Evaluate on test data (out-of-sample)
        test_result = self.backtest_function(best_params, window.test_data)
        test_score = self.objective_function.evaluate(test_result)
        test_metrics = {
            **test_result.get("performance_metrics", {}),
            "score": test_score,
        }

        logger.info(
            "window_evaluation_completed",
            window_id=window_id,
            validation_score=str(validation_score),
            test_score=str(test_score),
        )

        return WindowResult(
            window_id=window_id,
            best_params=best_params,
            train_metrics={
                **train_best_result.backtest_metrics,
                "score": train_best_result.score,
            },
            validation_metrics=validation_metrics,
            test_metrics=test_metrics,
            train_start_idx=window.train_start_idx,
            train_end_idx=window.train_end_idx,
            test_start_idx=window.test_start_idx,
            test_end_idx=window.test_end_idx,
            optimization_trials=len(optimizer.results),
        )

    def _aggregate_metrics(
        self, window_results: list[WindowResult]
    ) -> dict[str, dict[str, Decimal]]:
        """Aggregate performance metrics across all windows.

        Args:
            window_results: Results from all windows

        Returns:
            Dictionary with aggregated metrics for train/validation/test
        """
        import statistics

        # Collect metrics by phase (train, validation, test)
        train_scores = [Decimal(str(wr.train_metrics.get("score", 0))) for wr in window_results]
        val_scores = [Decimal(str(wr.validation_metrics.get("score", 0))) for wr in window_results]
        test_scores = [Decimal(str(wr.test_metrics.get("score", 0))) for wr in window_results]

        # Helper to calculate stats
        def calc_stats(values: list[Decimal], metric_name: str) -> dict[str, Decimal]:
            if not values:
                return {}

            # Convert to float for statistics module
            float_values = [float(v) for v in values]

            return {
                f"{metric_name}_mean": Decimal(str(statistics.mean(float_values))),
                f"{metric_name}_median": Decimal(str(statistics.median(float_values))),
                f"{metric_name}_std": (
                    Decimal(str(statistics.stdev(float_values)))
                    if len(float_values) > 1
                    else Decimal(0)
                ),
                f"{metric_name}_min": Decimal(str(min(float_values))),
                f"{metric_name}_max": Decimal(str(max(float_values))),
            }

        # Aggregate common metrics across all windows
        common_metrics = ["sharpe_ratio", "total_return", "max_drawdown"]
        aggregate = {}

        for phase, phase_name in [
            ("train", "train_metrics"),
            ("validation", "validation_metrics"),
            ("test", "test_metrics"),
        ]:
            phase_agg = {}

            # Aggregate score (already collected)
            if phase == "train":
                phase_agg.update(calc_stats(train_scores, "score"))
            elif phase == "validation":
                phase_agg.update(calc_stats(val_scores, "score"))
            else:  # test
                phase_agg.update(calc_stats(test_scores, "score"))

            # Aggregate other metrics
            for metric_name in common_metrics:
                metric_values = []
                for wr in window_results:
                    phase_metrics = getattr(wr, phase_name)
                    if metric_name in phase_metrics:
                        metric_values.append(Decimal(str(phase_metrics[metric_name])))

                if metric_values:
                    phase_agg.update(calc_stats(metric_values, metric_name))

            aggregate[phase] = phase_agg

        return aggregate

    def _analyze_parameter_stability(
        self, window_results: list[WindowResult]
    ) -> dict[str, dict[str, Decimal]]:
        """Analyze parameter stability across windows.

        Args:
            window_results: Results from all windows

        Returns:
            Dictionary mapping parameter names to stability statistics
        """
        import statistics

        # Collect all parameter values across windows
        param_names = set()
        for wr in window_results:
            param_names.update(wr.best_params.keys())

        stability = {}

        for param_name in param_names:
            # Collect values for this parameter
            param_values = []
            for wr in window_results:
                if param_name in wr.best_params:
                    value = wr.best_params[param_name]
                    # Convert to Decimal if numeric
                    if isinstance(value, (int, float, Decimal)):
                        param_values.append(Decimal(str(value)))

            # Calculate stability metrics for numeric parameters only
            if param_values and len(param_values) > 1:
                float_values = [float(v) for v in param_values]
                mean_val = Decimal(str(statistics.mean(float_values)))
                std_val = Decimal(str(statistics.stdev(float_values)))

                # Calculate coefficient of variation (CV) as stability metric
                # Lower CV = more stable
                cv = std_val / mean_val if mean_val != 0 else Decimal("Infinity")

                stability[param_name] = {
                    "mean": mean_val,
                    "std": std_val,
                    "min": Decimal(str(min(float_values))),
                    "max": Decimal(str(max(float_values))),
                    "coefficient_of_variation": cv,
                    "is_stable": cv < Decimal("0.2"),  # CV < 20% considered stable
                }

                # Log unstable parameters
                if cv >= Decimal("0.2"):
                    logger.warning(
                        "unstable_parameter_detected",
                        parameter=param_name,
                        mean=str(mean_val),
                        std=str(std_val),
                        cv=str(cv),
                    )

        return stability
