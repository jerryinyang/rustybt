"""Tests for optimizer orchestrator."""

import json
import tempfile
from decimal import Decimal
from pathlib import Path

import pytest

from rustybt.optimization import (
    CategoricalParameter,
    ContinuousParameter,
    DiscreteParameter,
    ObjectiveFunction,
    Optimizer,
    ParameterSpace,
)
from rustybt.optimization.search import RandomSearchAlgorithm


class TestOptimizer:
    """Tests for Optimizer."""

    def simple_backtest_function(self, params):
        """Simple backtest function for testing.

        Returns score based on parameter values (not hardcoded).
        """
        # Calculate score based on actual parameters
        score = Decimal("0")

        # Add contribution from each parameter
        if "lr" in params:
            lr = Decimal(str(params["lr"]))
            # Optimal lr is 0.05, penalize deviation
            score -= abs(lr - Decimal("0.05")) * Decimal("10")

        if "window" in params:
            window = params["window"]
            # Optimal window is 30, penalize deviation
            score -= abs(window - 30) * Decimal("0.1")

        if "opt" in params:
            # Prefer "adam"
            if params["opt"] == "adam":
                score += Decimal("1.0")
            else:
                score += Decimal("0.5")

        return {
            "performance_metrics": {
                "sharpe_ratio": float(score),
                "total_return": 0.25,
            }
        }

    def test_optimizer_initialization(self):
        """Test optimizer initialization."""
        param_space = ParameterSpace(
            parameters=[
                ContinuousParameter(name="lr", min_value=0.001, max_value=0.1),
            ]
        )

        search_alg = RandomSearchAlgorithm(param_space, n_trials=10, seed=42)
        obj_func = ObjectiveFunction(metric="sharpe_ratio")

        optimizer = Optimizer(
            parameter_space=param_space,
            search_algorithm=search_alg,
            objective_function=obj_func,
            backtest_function=self.simple_backtest_function,
            max_trials=10,
        )

        assert optimizer.max_trials == 10
        assert optimizer.current_trial == 0
        assert len(optimizer.results) == 0
        assert optimizer.best_result is None

    def test_optimizer_invalid_max_trials(self):
        """Test optimizer with invalid max_trials raises error."""
        param_space = ParameterSpace(
            parameters=[
                ContinuousParameter(name="lr", min_value=0.001, max_value=0.1),
            ]
        )

        search_alg = RandomSearchAlgorithm(param_space, n_trials=10)
        obj_func = ObjectiveFunction(metric="sharpe_ratio")

        with pytest.raises(ValueError):
            Optimizer(
                parameter_space=param_space,
                search_algorithm=search_alg,
                objective_function=obj_func,
                backtest_function=self.simple_backtest_function,
                max_trials=0,  # Invalid
            )

    def test_optimize_single_parameter(self):
        """Test optimization with single continuous parameter."""
        param_space = ParameterSpace(
            parameters=[
                ContinuousParameter(name="lr", min_value=0.001, max_value=0.1),
            ]
        )

        search_alg = RandomSearchAlgorithm(param_space, n_trials=5, seed=42)
        obj_func = ObjectiveFunction(metric="sharpe_ratio")

        optimizer = Optimizer(
            parameter_space=param_space,
            search_algorithm=search_alg,
            objective_function=obj_func,
            backtest_function=self.simple_backtest_function,
            max_trials=5,
        )

        best_result = optimizer.optimize()

        # Verify optimization completed
        assert optimizer.current_trial == 5
        assert len(optimizer.results) == 5
        assert best_result is not None
        assert best_result.is_success

        # Verify best result is tracked
        assert optimizer.best_result == best_result

        # Verify different trials produced different scores (not hardcoded)
        scores = [r.score for r in optimizer.results]
        assert len(set(scores)) > 1, "All scores are identical - likely hardcoded"

    def test_optimize_multiple_parameters(self):
        """Test optimization with multiple parameter types."""
        param_space = ParameterSpace(
            parameters=[
                ContinuousParameter(name="lr", min_value=0.001, max_value=0.1),
                DiscreteParameter(name="window", min_value=10, max_value=50, step=10),
                CategoricalParameter(name="opt", choices=["adam", "sgd"]),
            ]
        )

        search_alg = RandomSearchAlgorithm(param_space, n_trials=10, seed=42)
        obj_func = ObjectiveFunction(metric="sharpe_ratio")

        optimizer = Optimizer(
            parameter_space=param_space,
            search_algorithm=search_alg,
            objective_function=obj_func,
            backtest_function=self.simple_backtest_function,
            max_trials=10,
        )

        best_result = optimizer.optimize()

        assert len(optimizer.results) == 10
        assert best_result is not None

        # Verify all parameter types are present
        assert "lr" in best_result.params
        assert "window" in best_result.params
        assert "opt" in best_result.params

        # Verify parameter constraints
        param_space.validate_params(best_result.params)

    def test_optimize_tracks_best_result(self):
        """Test optimizer correctly tracks best result."""
        param_space = ParameterSpace(
            parameters=[
                ContinuousParameter(name="lr", min_value=0.001, max_value=0.1),
            ]
        )

        search_alg = RandomSearchAlgorithm(param_space, n_trials=20, seed=42)
        obj_func = ObjectiveFunction(metric="sharpe_ratio")

        optimizer = Optimizer(
            parameter_space=param_space,
            search_algorithm=search_alg,
            objective_function=obj_func,
            backtest_function=self.simple_backtest_function,
            max_trials=20,
        )

        best_result = optimizer.optimize()

        # Verify best result has highest score
        all_scores = [r.score for r in optimizer.results if r.is_success]
        max_score = max(all_scores)

        assert best_result.score == max_score

    def test_optimize_handles_backtest_failure(self):
        """Test optimizer handles backtest failures gracefully."""

        def failing_backtest(params):
            """Backtest that fails for certain parameters."""
            lr = float(params["lr"])
            if lr < 0.01:
                raise ValueError("Learning rate too small")

            return {
                "performance_metrics": {
                    "sharpe_ratio": 1.5,
                }
            }

        param_space = ParameterSpace(
            parameters=[
                ContinuousParameter(name="lr", min_value=0.001, max_value=0.1),
            ]
        )

        search_alg = RandomSearchAlgorithm(param_space, n_trials=20, seed=42)
        obj_func = ObjectiveFunction(metric="sharpe_ratio")

        optimizer = Optimizer(
            parameter_space=param_space,
            search_algorithm=search_alg,
            objective_function=obj_func,
            backtest_function=failing_backtest,
            max_trials=20,
        )

        best_result = optimizer.optimize()

        # Should complete despite some failures
        assert len(optimizer.results) == 20

        # Check for failed trials
        failed_trials = [r for r in optimizer.results if not r.is_success]
        assert len(failed_trials) > 0

        # Failed trials should have -Infinity score
        for failed in failed_trials:
            assert failed.score == Decimal("-Infinity")
            assert failed.error is not None

        # Best result should be from successful trial
        assert best_result.is_success

    def test_get_history(self):
        """Test getting optimization history."""
        param_space = ParameterSpace(
            parameters=[
                ContinuousParameter(name="lr", min_value=0.001, max_value=0.1),
            ]
        )

        search_alg = RandomSearchAlgorithm(param_space, n_trials=5, seed=42)
        obj_func = ObjectiveFunction(metric="sharpe_ratio")

        optimizer = Optimizer(
            parameter_space=param_space,
            search_algorithm=search_alg,
            objective_function=obj_func,
            backtest_function=self.simple_backtest_function,
            max_trials=5,
        )

        optimizer.optimize()

        history = optimizer.get_history()

        assert len(history) == 5
        assert isinstance(history, list)

        # Verify history is a copy (not reference)
        history.append(None)
        assert len(optimizer.results) == 5

    def test_get_best_params(self):
        """Test getting best parameters."""
        param_space = ParameterSpace(
            parameters=[
                ContinuousParameter(name="lr", min_value=0.001, max_value=0.1),
                DiscreteParameter(name="window", min_value=10, max_value=50, step=10),
            ]
        )

        search_alg = RandomSearchAlgorithm(param_space, n_trials=10, seed=42)
        obj_func = ObjectiveFunction(metric="sharpe_ratio")

        optimizer = Optimizer(
            parameter_space=param_space,
            search_algorithm=search_alg,
            objective_function=obj_func,
            backtest_function=self.simple_backtest_function,
            max_trials=10,
        )

        optimizer.optimize()

        best_params = optimizer.get_best_params()

        assert "lr" in best_params
        assert "window" in best_params

        # Verify it's a copy
        best_params["new_key"] = "value"
        assert "new_key" not in optimizer.best_result.params

    def test_get_best_params_before_optimization_raises(self):
        """Test getting best params before optimization raises error."""
        param_space = ParameterSpace(
            parameters=[
                ContinuousParameter(name="lr", min_value=0.001, max_value=0.1),
            ]
        )

        search_alg = RandomSearchAlgorithm(param_space, n_trials=5)
        obj_func = ObjectiveFunction(metric="sharpe_ratio")

        optimizer = Optimizer(
            parameter_space=param_space,
            search_algorithm=search_alg,
            objective_function=obj_func,
            backtest_function=self.simple_backtest_function,
            max_trials=5,
        )

        with pytest.raises(ValueError) as exc_info:
            optimizer.get_best_params()

        assert "No successful results" in str(exc_info.value)

    def test_checkpoint_save_and_load(self):
        """Test checkpoint save and load functionality."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint_dir = Path(tmpdir)

            param_space = ParameterSpace(
                parameters=[
                    ContinuousParameter(name="lr", min_value=0.001, max_value=0.1),
                ]
            )

            search_alg = RandomSearchAlgorithm(param_space, n_trials=10, seed=42)
            obj_func = ObjectiveFunction(metric="sharpe_ratio")

            optimizer = Optimizer(
                parameter_space=param_space,
                search_algorithm=search_alg,
                objective_function=obj_func,
                backtest_function=self.simple_backtest_function,
                max_trials=10,
                checkpoint_dir=checkpoint_dir,
                checkpoint_frequency=5,
            )

            optimizer.optimize()

            # Verify checkpoint file was created
            checkpoint_files = list(checkpoint_dir.glob("checkpoint_*.json"))
            assert len(checkpoint_files) > 0

            # Load checkpoint into new optimizer
            search_alg2 = RandomSearchAlgorithm(param_space, n_trials=10, seed=42)
            optimizer2 = Optimizer(
                parameter_space=param_space,
                search_algorithm=search_alg2,
                objective_function=obj_func,
                backtest_function=self.simple_backtest_function,
                max_trials=10,
            )

            optimizer2.load_checkpoint(checkpoint_files[-1])

            # Verify state was restored
            assert optimizer2.current_trial > 0
            assert len(optimizer2.results) > 0

    def test_checkpoint_contains_algorithm_state(self):
        """Test checkpoint includes search algorithm state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint_dir = Path(tmpdir)

            param_space = ParameterSpace(
                parameters=[
                    ContinuousParameter(name="lr", min_value=0.001, max_value=0.1),
                ]
            )

            search_alg = RandomSearchAlgorithm(param_space, n_trials=5, seed=42)
            obj_func = ObjectiveFunction(metric="sharpe_ratio")

            optimizer = Optimizer(
                parameter_space=param_space,
                search_algorithm=search_alg,
                objective_function=obj_func,
                backtest_function=self.simple_backtest_function,
                max_trials=5,
                checkpoint_dir=checkpoint_dir,
                checkpoint_frequency=5,
            )

            optimizer.optimize()

            checkpoint_file = list(checkpoint_dir.glob("checkpoint_*.json"))[0]

            # Read checkpoint
            with open(checkpoint_file) as f:
                state = json.load(f)

            # Verify algorithm state is present
            assert "algorithm_state" in state
            assert "iteration" in state["algorithm_state"]
            assert "rng_state" in state["algorithm_state"]
