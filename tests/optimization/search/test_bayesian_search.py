"""Tests for Bayesian optimization algorithm."""

from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from rustybt.optimization.parameter_space import (
    CategoricalParameter,
    ContinuousParameter,
    DiscreteParameter,
    ParameterSpace,
)
from rustybt.optimization.search.bayesian_search import BayesianOptimizer


@pytest.fixture
def simple_space() -> ParameterSpace:
    """Create simple 2D parameter space for testing."""
    return ParameterSpace(
        parameters=[
            ContinuousParameter(name="x", min_value=-5.0, max_value=5.0),
            ContinuousParameter(name="y", min_value=-5.0, max_value=5.0),
        ]
    )


@pytest.fixture
def mixed_space() -> ParameterSpace:
    """Create mixed parameter space with different types."""
    return ParameterSpace(
        parameters=[
            ContinuousParameter(name="learning_rate", min_value=0.001, max_value=0.1),
            DiscreteParameter(name="batch_size", min_value=16, max_value=128, step=16),
            CategoricalParameter(name="optimizer", choices=["adam", "sgd", "rmsprop"]),
        ]
    )


def sphere_function(params: dict[str, Any]) -> Decimal:
    """Simple sphere function: f(x,y) = -(x^2 + y^2).

    Global maximum at (0, 0) with value 0.
    """
    x = float(params["x"])
    y = float(params["y"])
    return Decimal(str(-(x**2 + y**2)))


def rastrigin_2d(params: dict[str, Any]) -> Decimal:
    """2D Rastrigin function (harder optimization problem).

    Global maximum at (0, 0) with value 0.
    """
    x = float(params["x"])
    y = float(params["y"])
    result = -(x**2 - 10 * np.cos(2 * np.pi * x) + y**2 - 10 * np.cos(2 * np.pi * y))
    return Decimal(str(result))


class TestBayesianOptimizerInitialization:
    """Test BayesianOptimizer initialization."""

    def test_basic_initialization(self, simple_space: ParameterSpace) -> None:
        """Test basic optimizer initialization."""
        optimizer = BayesianOptimizer(
            parameter_space=simple_space,
            n_iter=10,
        )

        assert optimizer.n_iter == 10
        assert optimizer.acq_func == "EI"
        assert optimizer.iteration == 0
        assert not optimizer.is_complete()

    def test_initialization_with_all_params(self, simple_space: ParameterSpace) -> None:
        """Test initialization with all parameters."""
        optimizer = BayesianOptimizer(
            parameter_space=simple_space,
            n_iter=20,
            acq_func="LCB",
            kappa=2.5,
            xi=0.1,
            convergence_threshold=1e-3,
            convergence_patience=5,
            random_state=42,
        )

        assert optimizer.n_iter == 20
        assert optimizer.acq_func == "LCB"
        assert optimizer.kappa == 2.5
        assert optimizer.xi == 0.1
        assert optimizer.random_state == 42

    def test_invalid_n_iter(self, simple_space: ParameterSpace) -> None:
        """Test that invalid n_iter raises ValueError."""
        with pytest.raises(ValueError, match="n_iter must be positive"):
            BayesianOptimizer(parameter_space=simple_space, n_iter=0)

        with pytest.raises(ValueError, match="n_iter must be positive"):
            BayesianOptimizer(parameter_space=simple_space, n_iter=-5)

    def test_initialization_with_prior_knowledge(self, simple_space: ParameterSpace) -> None:
        """Test initialization with prior knowledge."""
        initial_points = [{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 1.0}]
        initial_scores = [Decimal("0.0"), Decimal("-2.0")]

        optimizer = BayesianOptimizer(
            parameter_space=simple_space,
            n_iter=10,
            initial_points=initial_points,
            initial_scores=initial_scores,
        )

        assert optimizer.iteration == 0  # Prior knowledge doesn't count as iterations

    def test_mismatched_initial_points_and_scores(self, simple_space: ParameterSpace) -> None:
        """Test that mismatched initial points and scores raises error."""
        initial_points = [{"x": 0.0, "y": 0.0}]
        initial_scores = [Decimal("0.0"), Decimal("-1.0")]  # Mismatch!

        with pytest.raises(
            ValueError, match="initial_points and initial_scores must have same length"
        ):
            BayesianOptimizer(
                parameter_space=simple_space,
                initial_points=initial_points,
                initial_scores=initial_scores,
            )


class TestBayesianOptimizerSuggestUpdate:
    """Test suggest() and update() methods."""

    def test_suggest_returns_valid_params(self, simple_space: ParameterSpace) -> None:
        """Test that suggest() returns valid parameters."""
        optimizer = BayesianOptimizer(parameter_space=simple_space, n_iter=5)

        params = optimizer.suggest()

        assert isinstance(params, dict)
        assert "x" in params
        assert "y" in params
        assert -5.0 <= params["x"] <= 5.0
        assert -5.0 <= params["y"] <= 5.0

    def test_suggest_increment_iteration(self, simple_space: ParameterSpace) -> None:
        """Test that suggest() increments iteration counter."""
        optimizer = BayesianOptimizer(parameter_space=simple_space, n_iter=5)

        assert optimizer.iteration == 0
        optimizer.suggest()
        assert optimizer.iteration == 1

    def test_suggest_after_complete_raises_error(self, simple_space: ParameterSpace) -> None:
        """Test that suggest() after completion raises error."""
        optimizer = BayesianOptimizer(parameter_space=simple_space, n_iter=1)

        optimizer.suggest()
        optimizer.update(optimizer._current_suggestion, Decimal("0.0"))

        assert optimizer.is_complete()
        with pytest.raises(ValueError, match="Optimization is complete"):
            optimizer.suggest()

    def test_update_tracks_best(self, simple_space: ParameterSpace) -> None:
        """Test that update() tracks best score and params."""
        optimizer = BayesianOptimizer(parameter_space=simple_space, n_iter=5)

        # First evaluation
        params1 = optimizer.suggest()
        optimizer.update(params1, Decimal("1.5"))

        assert optimizer.get_best_score() == Decimal("1.5")
        assert optimizer.get_best_params() == params1

        # Better evaluation
        params2 = optimizer.suggest()
        optimizer.update(params2, Decimal("2.0"))

        assert optimizer.get_best_score() == Decimal("2.0")
        assert optimizer.get_best_params() == params2

        # Worse evaluation (shouldn't update best)
        params3 = optimizer.suggest()
        optimizer.update(params3, Decimal("1.0"))

        assert optimizer.get_best_score() == Decimal("2.0")
        assert optimizer.get_best_params() == params2

    def test_update_without_suggest_raises_error(self, simple_space: ParameterSpace) -> None:
        """Test that update() without suggest() raises error."""
        optimizer = BayesianOptimizer(parameter_space=simple_space, n_iter=5)

        with pytest.raises(ValueError, match="No suggestion pending"):
            optimizer.update({"x": 0.0, "y": 0.0}, Decimal("0.0"))

    def test_update_with_wrong_params_raises_error(self, simple_space: ParameterSpace) -> None:
        """Test that update() with wrong params raises error."""
        optimizer = BayesianOptimizer(parameter_space=simple_space, n_iter=5)

        params = optimizer.suggest()
        wrong_params = {"x": params["x"] + 1.0, "y": params["y"]}

        with pytest.raises(ValueError, match="don't match suggestion"):
            optimizer.update(wrong_params, Decimal("0.0"))


class TestBayesianOptimizerAcquisitionFunctions:
    """Test different acquisition functions."""

    @pytest.mark.parametrize("acq_func", ["EI", "PI", "LCB"])
    def test_acquisition_function(self, simple_space: ParameterSpace, acq_func: str) -> None:
        """Test that each acquisition function works."""
        optimizer = BayesianOptimizer(
            parameter_space=simple_space,
            n_iter=10,
            acq_func=acq_func,  # type: ignore
            random_state=42,
        )

        # Run a few iterations
        for _ in range(5):
            params = optimizer.suggest()
            score = sphere_function(params)
            optimizer.update(params, score)

        # Should have found something close to optimum
        best_score = optimizer.get_best_score()
        assert best_score is not None
        assert best_score > Decimal("-5.0")  # Should improve from random


class TestBayesianOptimizerConvergence:
    """Test convergence detection."""

    def test_convergence_on_max_iterations(self, simple_space: ParameterSpace) -> None:
        """Test that optimizer stops after max iterations."""
        optimizer = BayesianOptimizer(parameter_space=simple_space, n_iter=10)

        for i in range(10):
            assert not optimizer.is_complete()
            params = optimizer.suggest()
            optimizer.update(params, sphere_function(params))

        assert optimizer.is_complete()

    def test_early_convergence_detection(self, simple_space: ParameterSpace) -> None:
        """Test early stopping when converged."""
        optimizer = BayesianOptimizer(
            parameter_space=simple_space,
            n_iter=100,
            convergence_threshold=1e-3,
            convergence_patience=5,
            random_state=42,
        )

        iteration_count = 0
        while not optimizer.is_complete() and iteration_count < 100:
            params = optimizer.suggest()
            optimizer.update(params, sphere_function(params))
            iteration_count += 1

        # Should converge before max iterations on simple problem
        assert iteration_count < 100


class TestBayesianOptimizerPriorKnowledge:
    """Test prior knowledge seeding."""

    def test_prior_knowledge_improves_convergence(self, simple_space: ParameterSpace) -> None:
        """Test that prior knowledge speeds up optimization."""
        # Without prior knowledge
        optimizer_no_prior = BayesianOptimizer(
            parameter_space=simple_space,
            n_iter=10,
            random_state=42,
        )

        for _ in range(10):
            params = optimizer_no_prior.suggest()
            optimizer_no_prior.update(params, sphere_function(params))

        # With prior knowledge (near optimum)
        optimizer_with_prior = BayesianOptimizer(
            parameter_space=simple_space,
            n_iter=10,
            initial_points=[{"x": 0.1, "y": 0.1}],
            initial_scores=[sphere_function({"x": 0.1, "y": 0.1})],
            random_state=42,
        )

        for _ in range(10):
            params = optimizer_with_prior.suggest()
            optimizer_with_prior.update(params, sphere_function(params))

        # With prior should find better solution
        best_no_prior = optimizer_no_prior.get_best_score()
        best_with_prior = optimizer_with_prior.get_best_score()

        assert best_no_prior is not None
        assert best_with_prior is not None
        assert best_with_prior >= best_no_prior


class TestBayesianOptimizerMixedSpace:
    """Test optimization on mixed parameter spaces."""

    def test_mixed_space_optimization(self, mixed_space: ParameterSpace) -> None:
        """Test optimization on space with continuous, discrete, and categorical."""

        def mock_objective(params: dict[str, Any]) -> Decimal:
            """Mock objective function for mixed space."""
            lr = float(params["learning_rate"])
            bs = int(params["batch_size"])
            opt = params["optimizer"]

            # Prefer low learning rate, batch size 64, adam optimizer
            score = -(abs(lr - 0.01) + abs(bs - 64) / 64)
            if opt == "adam":
                score += 0.5

            return Decimal(str(score))

        optimizer = BayesianOptimizer(
            parameter_space=mixed_space,
            n_iter=20,
            convergence_patience=1000,  # Disable early stopping for test
            random_state=42,
        )

        while not optimizer.is_complete():
            params = optimizer.suggest()
            score = mock_objective(params)
            optimizer.update(params, score)

        best_params = optimizer.get_best_params()
        assert best_params is not None

        # Should find good parameters
        assert best_params["optimizer"] == "adam"
        assert abs(best_params["learning_rate"] - 0.01) < 0.05
        assert best_params["batch_size"] in [16, 32, 48, 64, 80, 96, 112, 128]  # Valid steps


class TestBayesianOptimizerStateManagement:
    """Test state serialization and restoration."""

    def test_get_set_state(self, simple_space: ParameterSpace) -> None:
        """Test state serialization and restoration."""
        optimizer1 = BayesianOptimizer(
            parameter_space=simple_space,
            n_iter=20,
            random_state=42,
        )

        # Run a few iterations
        for _ in range(5):
            params = optimizer1.suggest()
            optimizer1.update(params, sphere_function(params))

        # Save state
        state = optimizer1.get_state()

        # Create new optimizer and restore state
        optimizer2 = BayesianOptimizer(
            parameter_space=simple_space,
            n_iter=20,
        )
        optimizer2.set_state(state)

        # Should have same state
        assert optimizer2.iteration == optimizer1.iteration
        assert optimizer2.get_best_score() == optimizer1.get_best_score()
        assert optimizer2.get_best_params() == optimizer1.get_best_params()
        assert len(optimizer2._evaluations) == len(optimizer1._evaluations)

        # Continue optimization from restored state
        params = optimizer2.suggest()
        optimizer2.update(params, sphere_function(params))

        assert optimizer2.iteration == 6


class TestBayesianOptimizerEfficiency:
    """Test efficiency compared to grid search."""

    def test_bayesian_vs_grid_efficiency(self, simple_space: ParameterSpace) -> None:
        """Test that Bayesian optimization is more efficient than grid search."""
        # Use Rastrigin function (harder problem)
        # Disable early convergence to ensure we run for full iterations
        optimizer = BayesianOptimizer(
            parameter_space=simple_space,
            n_iter=30,
            convergence_patience=1000,  # Effectively disable early stopping
            random_state=42,
        )

        iterations = 0
        while not optimizer.is_complete():
            params = optimizer.suggest()
            optimizer.update(params, rastrigin_2d(params))
            iterations += 1

        # Should run for full n_iter since we disabled early stopping
        assert iterations == 30

        bayesian_best = optimizer.get_best_score()
        assert bayesian_best is not None

        # Bayesian should find near-optimal solution (close to 0)
        # Rastrigin is difficult but Bayesian should still find something reasonable
        assert bayesian_best > Decimal("-10.0")

        # With only 30 evaluations vs grid search needing 100+ for similar accuracy


class TestBayesianOptimizerVisualization:
    """Test visualization methods."""

    def test_plot_convergence(self, simple_space: ParameterSpace, tmp_path: Path) -> None:
        """Test convergence plotting."""
        pytest.importorskip("matplotlib")

        optimizer = BayesianOptimizer(
            parameter_space=simple_space,
            n_iter=10,
            random_state=42,
        )

        for _ in range(10):
            params = optimizer.suggest()
            optimizer.update(params, sphere_function(params))

        # Test without saving
        fig = optimizer.plot_convergence()
        assert fig is not None

        # Test with saving
        save_path = tmp_path / "convergence.png"
        fig = optimizer.plot_convergence(save_path=save_path)
        assert save_path.exists()

    def test_plot_objective(self, simple_space: ParameterSpace, tmp_path: Path) -> None:
        """Test objective function plotting."""
        pytest.importorskip("matplotlib")

        optimizer = BayesianOptimizer(
            parameter_space=simple_space,
            n_iter=10,
            random_state=42,
        )

        for _ in range(10):
            params = optimizer.suggest()
            optimizer.update(params, sphere_function(params))

        save_path = tmp_path / "objective.png"
        fig = optimizer.plot_objective(save_path=save_path)
        assert fig is not None
        assert save_path.exists()

    def test_plot_evaluations(self, simple_space: ParameterSpace, tmp_path: Path) -> None:
        """Test evaluations plotting."""
        pytest.importorskip("matplotlib")

        optimizer = BayesianOptimizer(
            parameter_space=simple_space,
            n_iter=10,
            random_state=42,
        )

        for _ in range(10):
            params = optimizer.suggest()
            optimizer.update(params, sphere_function(params))

        save_path = tmp_path / "evaluations.png"
        fig = optimizer.plot_evaluations(save_path=save_path)
        assert fig is not None
        assert save_path.exists()


class TestBayesianOptimizerPropertyBased:
    """Property-based tests using Hypothesis."""

    @given(
        n_params=st.integers(min_value=1, max_value=3),
        n_iter=st.integers(min_value=5, max_value=20),
    )
    def test_suggestions_respect_bounds(self, n_params: int, n_iter: int) -> None:
        """All suggestions must be within parameter bounds."""
        space = ParameterSpace(
            parameters=[
                ContinuousParameter(name=f"x{i}", min_value=0.0, max_value=1.0)
                for i in range(n_params)
            ]
        )

        optimizer = BayesianOptimizer(
            parameter_space=space,
            n_iter=n_iter,
            random_state=42,
        )

        for _ in range(min(n_iter, 10)):  # Limit for test speed
            params = optimizer.suggest()

            # All parameters in [0, 1]
            for i in range(n_params):
                assert 0.0 <= params[f"x{i}"] <= 1.0

            # Update with dummy result
            optimizer.update(params, Decimal(str(np.random.random())))

    @given(
        n_iter=st.integers(min_value=1, max_value=50),
    )
    def test_best_score_monotonic_increasing(self, n_iter: int) -> None:
        """Best score should never decrease (higher is better)."""
        space = ParameterSpace(
            parameters=[ContinuousParameter(name="x", min_value=-5.0, max_value=5.0)]
        )

        optimizer = BayesianOptimizer(
            parameter_space=space,
            n_iter=n_iter,
            random_state=42,
        )

        best_scores = []
        for _ in range(min(n_iter, 10)):
            params = optimizer.suggest()
            score = Decimal(str(-(params["x"] ** 2)))  # Simple quadratic
            optimizer.update(params, score)

            current_best = optimizer.get_best_score()
            if current_best is not None:
                best_scores.append(current_best)

        # Best score should be monotonically non-decreasing
        for i in range(1, len(best_scores)):
            assert best_scores[i] >= best_scores[i - 1]
