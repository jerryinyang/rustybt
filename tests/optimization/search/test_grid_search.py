"""Tests for grid search algorithm."""

import math
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from rustybt.optimization.parameter_space import (
    CategoricalParameter,
    ContinuousParameter,
    DiscreteParameter,
    ParameterSpace,
)
from rustybt.optimization.search import GridSearchAlgorithm


class TestGridSearchAlgorithm:
    """Tests for GridSearchAlgorithm."""

    def test_initialization(self):
        """Test grid search initialization."""
        param_space = ParameterSpace(
            parameters=[
                DiscreteParameter(name="window", min_value=10, max_value=30, step=10),
                CategoricalParameter(name="threshold", choices=[0.01, 0.02]),
            ]
        )

        grid = GridSearchAlgorithm(param_space)

        assert grid.iteration == 0
        assert grid.total_combinations == 6  # 3 windows * 2 thresholds
        assert grid.progress == 0.0
        assert grid.is_complete() is False

    def test_rejects_continuous_parameters(self):
        """Test that grid search rejects continuous parameters."""
        param_space = ParameterSpace(
            parameters=[
                ContinuousParameter(name="lr", min_value=0.001, max_value=0.1),
            ]
        )

        with pytest.raises(ValueError, match="does not support continuous parameters"):
            GridSearchAlgorithm(param_space)

    def test_warns_on_large_grid(self):
        """Test warning for large grid sizes."""
        param_space = ParameterSpace(
            parameters=[
                DiscreteParameter(name="p1", min_value=1, max_value=10, step=1),
                DiscreteParameter(name="p2", min_value=1, max_value=10, step=1),
                DiscreteParameter(name="p3", min_value=1, max_value=20, step=1),
                DiscreteParameter(name="p4", min_value=1, max_value=10, step=1),
            ]
        )

        # Should warn: 10 * 10 * 20 * 10 = 20,000 combinations
        with pytest.warns(UserWarning, match="Grid search will evaluate"):
            GridSearchAlgorithm(param_space)

    def test_grid_generation_discrete_only(self):
        """Test grid generation with discrete parameters only."""
        param_space = ParameterSpace(
            parameters=[
                DiscreteParameter(name="short", min_value=10, max_value=30, step=10),
                DiscreteParameter(name="long", min_value=50, max_value=100, step=25),
            ]
        )

        grid = GridSearchAlgorithm(param_space)

        expected_combinations = 3 * 3  # [10, 20, 30] × [50, 75, 100]
        assert grid.total_combinations == expected_combinations

    def test_grid_generation_categorical_only(self):
        """Test grid generation with categorical parameters only."""
        param_space = ParameterSpace(
            parameters=[
                CategoricalParameter(name="opt", choices=["adam", "sgd", "rmsprop"]),
                CategoricalParameter(name="activation", choices=["relu", "tanh"]),
            ]
        )

        grid = GridSearchAlgorithm(param_space)

        expected_combinations = 3 * 2  # 3 optimizers × 2 activations
        assert grid.total_combinations == expected_combinations

    def test_grid_generation_mixed_parameters(self):
        """Test grid generation with mixed parameter types."""
        param_space = ParameterSpace(
            parameters=[
                DiscreteParameter(name="window", min_value=10, max_value=20, step=5),
                CategoricalParameter(name="method", choices=["sma", "ema", "wma"]),
            ]
        )

        grid = GridSearchAlgorithm(param_space)

        expected_combinations = 3 * 3  # [10, 15, 20] × 3 methods
        assert grid.total_combinations == expected_combinations

    def test_suggest_returns_all_combinations(self):
        """Test that suggest returns all combinations exactly once."""
        param_space = ParameterSpace(
            parameters=[
                DiscreteParameter(name="a", min_value=1, max_value=2, step=1),
                DiscreteParameter(name="b", min_value=10, max_value=20, step=10),
            ]
        )

        grid = GridSearchAlgorithm(param_space)

        expected_combinations = {
            (1, 10),
            (1, 20),
            (2, 10),
            (2, 20),
        }

        seen_combinations = set()
        while not grid.is_complete():
            params = grid.suggest()
            combo = (params["a"], params["b"])
            seen_combinations.add(combo)

            # Update with dummy score to progress
            grid.update(params, Decimal("1.0"))

        assert seen_combinations == expected_combinations
        assert grid.is_complete()

    def test_suggest_raises_when_complete(self):
        """Test that suggest raises error when grid is exhausted."""
        param_space = ParameterSpace(
            parameters=[
                DiscreteParameter(name="a", min_value=1, max_value=2, step=1),
            ]
        )

        grid = GridSearchAlgorithm(param_space)

        # Exhaust grid
        for _ in range(2):
            params = grid.suggest()
            grid.update(params, Decimal("1.0"))

        assert grid.is_complete()

        with pytest.raises(ValueError, match="Grid search is complete"):
            grid.suggest()

    def test_update_validates_parameters(self):
        """Test that update validates parameters against space."""
        param_space = ParameterSpace(
            parameters=[
                DiscreteParameter(name="window", min_value=10, max_value=30, step=10),
            ]
        )

        grid = GridSearchAlgorithm(param_space)

        # Valid update
        params = grid.suggest()
        grid.update(params, Decimal("1.5"))  # Should succeed

        # Invalid parameter value
        with pytest.raises(ValueError, match="outside bounds"):
            grid.update({"window": 5}, Decimal("1.0"))  # 5 is outside bounds

    def test_progress_tracking(self):
        """Test progress tracking during optimization."""
        param_space = ParameterSpace(
            parameters=[
                DiscreteParameter(name="a", min_value=1, max_value=4, step=1),
            ]
        )

        grid = GridSearchAlgorithm(param_space)

        assert grid.total_combinations == 4
        assert grid.progress == 0.0

        # Complete 1 trial
        params = grid.suggest()
        grid.update(params, Decimal("1.0"))
        assert grid.progress == 0.25

        # Complete 2 more trials
        for _ in range(2):
            params = grid.suggest()
            grid.update(params, Decimal("1.0"))

        assert grid.progress == 0.75

        # Complete last trial
        params = grid.suggest()
        grid.update(params, Decimal("1.0"))
        assert grid.progress == 1.0
        assert grid.is_complete()

    def test_early_stopping_disabled(self):
        """Test grid search without early stopping."""
        param_space = ParameterSpace(
            parameters=[
                DiscreteParameter(name="a", min_value=1, max_value=3, step=1),
            ]
        )

        grid = GridSearchAlgorithm(param_space, early_stopping_rounds=None)

        # Even with no improvement, should not stop early
        for _ in range(3):
            params = grid.suggest()
            grid.update(params, Decimal("1.0"))  # Same score every time

        assert grid.is_complete()  # Only completes because grid exhausted

    def test_early_stopping_enabled(self):
        """Test early stopping when no improvement."""
        param_space = ParameterSpace(
            parameters=[
                DiscreteParameter(name="a", min_value=1, max_value=10, step=1),
            ]
        )

        grid = GridSearchAlgorithm(param_space, early_stopping_rounds=3)

        # First trial establishes best score
        params = grid.suggest()
        grid.update(params, Decimal("2.0"))

        # Next 3 trials have no improvement
        for _ in range(3):
            params = grid.suggest()
            grid.update(params, Decimal("1.0"))

        # Should trigger early stopping
        assert grid.is_complete()
        assert grid.total_combinations == 10  # Grid not exhausted
        assert grid.progress < 1.0  # Didn't complete all combinations

    def test_early_stopping_resets_on_improvement(self):
        """Test that early stopping counter resets on improvement."""
        param_space = ParameterSpace(
            parameters=[
                DiscreteParameter(name="a", min_value=1, max_value=10, step=1),
            ]
        )

        grid = GridSearchAlgorithm(param_space, early_stopping_rounds=3)

        # First trial
        params = grid.suggest()
        grid.update(params, Decimal("1.0"))

        # Two trials without improvement
        for _ in range(2):
            params = grid.suggest()
            grid.update(params, Decimal("0.5"))

        # New best (resets counter)
        params = grid.suggest()
        grid.update(params, Decimal("2.0"))

        # Should not be complete yet
        assert not grid.is_complete()

        # Now 3 more without improvement
        for _ in range(3):
            params = grid.suggest()
            grid.update(params, Decimal("1.5"))

        # Now should trigger early stopping
        assert grid.is_complete()

    def test_get_best_params(self):
        """Test retrieving best parameters."""
        param_space = ParameterSpace(
            parameters=[
                DiscreteParameter(name="window", min_value=10, max_value=30, step=10),
            ]
        )

        grid = GridSearchAlgorithm(param_space)

        # Evaluate all combinations with different scores
        scores = [Decimal("1.5"), Decimal("2.8"), Decimal("2.1")]
        for score in scores:
            params = grid.suggest()
            grid.update(params, score)

        best_params = grid.get_best_params()
        assert best_params["window"] == 20  # Second combination had score 2.8

    def test_get_best_params_raises_without_results(self):
        """Test that get_best_params raises error without results."""
        param_space = ParameterSpace(
            parameters=[
                DiscreteParameter(name="a", min_value=1, max_value=2, step=1),
            ]
        )

        grid = GridSearchAlgorithm(param_space)

        with pytest.raises(ValueError, match="No results available"):
            grid.get_best_params()

    def test_get_results_all(self):
        """Test getting all results sorted by score."""
        param_space = ParameterSpace(
            parameters=[
                DiscreteParameter(name="a", min_value=1, max_value=3, step=1),
            ]
        )

        grid = GridSearchAlgorithm(param_space)

        # Evaluate all with different scores
        scores = [Decimal("1.5"), Decimal("2.8"), Decimal("2.1")]
        for score in scores:
            params = grid.suggest()
            grid.update(params, score)

        results = grid.get_results()

        assert len(results) == 3
        # Should be sorted by score descending
        assert results[0][1] == Decimal("2.8")
        assert results[1][1] == Decimal("2.1")
        assert results[2][1] == Decimal("1.5")

    def test_get_results_top_k(self):
        """Test getting top K results."""
        param_space = ParameterSpace(
            parameters=[
                DiscreteParameter(name="a", min_value=1, max_value=5, step=1),
            ]
        )

        grid = GridSearchAlgorithm(param_space)

        # Evaluate all
        for i in range(5):
            params = grid.suggest()
            grid.update(params, Decimal(str(i)))

        results = grid.get_results(top_k=2)

        assert len(results) == 2
        assert results[0][1] == Decimal("4")  # Best
        assert results[1][1] == Decimal("3")  # Second best

    def test_get_results_raises_without_results(self):
        """Test that get_results raises error without results."""
        param_space = ParameterSpace(
            parameters=[
                DiscreteParameter(name="a", min_value=1, max_value=2, step=1),
            ]
        )

        grid = GridSearchAlgorithm(param_space)

        with pytest.raises(ValueError, match="No results available"):
            grid.get_results()

    def test_thread_safety_suggest(self):
        """Test thread-safe suggest() for parallel execution."""
        param_space = ParameterSpace(
            parameters=[
                DiscreteParameter(name="a", min_value=1, max_value=20, step=1),
            ]
        )

        grid = GridSearchAlgorithm(param_space)

        # Simulate multiple workers calling suggest concurrently
        def worker(worker_id):
            results = []
            while True:
                try:
                    params = grid.suggest()
                    results.append(params["a"])
                except ValueError:
                    # Grid exhausted
                    break
            return results

        # Use threading to test concurrent access
        import threading

        workers = []
        all_results = []
        for i in range(4):
            t = threading.Thread(target=lambda worker_id=i: all_results.extend(worker(worker_id)))
            workers.append(t)
            t.start()

        for t in workers:
            t.join()

        # All combinations should be suggested exactly once
        assert len(all_results) == 20
        assert len(set(all_results)) == 20  # No duplicates

    def test_thread_safety_update(self):
        """Test thread-safe update() for parallel execution."""
        param_space = ParameterSpace(
            parameters=[
                DiscreteParameter(name="a", min_value=1, max_value=10, step=1),
            ]
        )

        grid = GridSearchAlgorithm(param_space)

        # Get all params first
        all_params = []
        for _ in range(10):
            all_params.append(grid.suggest())

        # Update concurrently from multiple threads
        def worker(params_list):
            for params in params_list:
                grid.update(params, Decimal("1.0"))

        import threading

        # Split params across workers
        workers = []
        chunk_size = len(all_params) // 4
        for i in range(4):
            start = i * chunk_size
            end = start + chunk_size if i < 3 else len(all_params)
            t = threading.Thread(target=worker, args=(all_params[start:end],))
            workers.append(t)
            t.start()

        for t in workers:
            t.join()

        # All updates should be recorded
        assert len(grid.get_results()) == 10
        assert grid.progress == 1.0

    def test_get_state_and_set_state(self):
        """Test checkpoint/resume via state management."""
        param_space = ParameterSpace(
            parameters=[
                DiscreteParameter(name="window", min_value=10, max_value=40, step=10),
                CategoricalParameter(name="method", choices=["a", "b"]),
            ]
        )

        # Run partial optimization
        grid1 = GridSearchAlgorithm(param_space, early_stopping_rounds=5)

        for i in range(4):
            params = grid1.suggest()
            grid1.update(params, Decimal(str(i)))

        # Save state
        state = grid1.get_state()

        # Create new instance and restore state
        grid2 = GridSearchAlgorithm(param_space, early_stopping_rounds=5)
        grid2.set_state(state)

        # Verify state restored correctly
        assert grid2.iteration == grid1.iteration
        assert grid2.progress == grid1.progress
        assert grid2.get_best_params() == grid1.get_best_params()
        assert len(grid2.get_results()) == len(grid1.get_results())

        # Continue optimization from checkpoint
        while not grid2.is_complete():
            params = grid2.suggest()
            grid2.update(params, Decimal("1.0"))

        assert grid2.is_complete()

    def test_empty_parameter_space(self):
        """Test error handling for empty parameter space."""
        # ParameterSpace validation requires at least 1 parameter
        # GridSearchAlgorithm._generate_grid will raise ValueError if empty
        with pytest.raises(ValueError, match="at least 1"):
            # This will fail at ParameterSpace level
            ParameterSpace(parameters=[])


class TestGridSearchPropertyTests:
    """Property-based tests for grid search."""

    @given(param_counts=st.lists(st.integers(min_value=2, max_value=5), min_size=1, max_size=4))
    @settings(max_examples=50, deadline=None)
    def test_grid_size_invariant(self, param_counts):
        """Grid size must equal product of parameter value counts."""
        # Create parameter space with specified counts
        # Note: min_value=2 because DiscreteParameter requires max > min
        parameters = []
        for i, count in enumerate(param_counts):
            parameters.append(DiscreteParameter(name=f"p{i}", min_value=1, max_value=count, step=1))

        param_space = ParameterSpace(parameters=parameters)
        grid = GridSearchAlgorithm(param_space)

        expected_size = math.prod(param_counts)
        assert grid.total_combinations == expected_size

    @given(
        num_params=st.integers(min_value=1, max_value=3),
        values_per_param=st.integers(min_value=2, max_value=4),
    )
    @settings(max_examples=20, deadline=None)
    def test_all_combinations_unique(self, num_params, values_per_param):
        """All suggested combinations must be unique."""
        # Create parameter space
        parameters = []
        for i in range(num_params):
            parameters.append(
                DiscreteParameter(
                    name=f"p{i}",
                    min_value=1,
                    max_value=values_per_param,
                    step=1,
                )
            )

        param_space = ParameterSpace(parameters=parameters)
        grid = GridSearchAlgorithm(param_space)

        # Collect all suggestions
        seen = set()
        while not grid.is_complete():
            params = grid.suggest()
            # Create hashable tuple
            param_tuple = tuple(params[f"p{i}"] for i in range(num_params))
            assert param_tuple not in seen
            seen.add(param_tuple)

            grid.update(params, Decimal("1.0"))

        # Should have suggested exactly the expected number
        expected_count = values_per_param**num_params
        assert len(seen) == expected_count


class TestGridSearchIntegration:
    """Integration tests with realistic scenarios."""

    def test_simple_backtest_integration(self):
        """Test grid search with simple backtest function."""

        def simple_backtest(params: dict) -> Decimal:
            """Dummy backtest - returns higher score for larger window."""
            window = params["window"]
            threshold = params["threshold"]
            # Simple scoring function
            return Decimal(str(window * threshold))

        param_space = ParameterSpace(
            parameters=[
                DiscreteParameter(name="window", min_value=10, max_value=30, step=10),
                CategoricalParameter(name="threshold", choices=[0.01, 0.02, 0.03]),
            ]
        )

        grid = GridSearchAlgorithm(param_space)

        # Run optimization
        while not grid.is_complete():
            params = grid.suggest()
            score = simple_backtest(params)
            grid.update(params, score)

        # Verify results
        best_params = grid.get_best_params()
        assert best_params["window"] == 30  # Largest window
        assert best_params["threshold"] == 0.03  # Largest threshold

        results = grid.get_results()
        assert len(results) == 9  # 3 windows × 3 thresholds

    def test_optimization_with_failures(self):
        """Test grid search handles backtest failures gracefully."""

        def failing_backtest(params: dict) -> Decimal:
            """Backtest that fails for certain params."""
            window = params["window"]
            if window == 20:
                raise ValueError("Simulated backtest failure")
            return Decimal(str(window))

        param_space = ParameterSpace(
            parameters=[
                DiscreteParameter(name="window", min_value=10, max_value=30, step=10),
            ]
        )

        grid = GridSearchAlgorithm(param_space)

        # Run optimization (note: grid search doesn't handle failures internally,
        # but Optimizer wrapper should - here we just test the algorithm continues)
        results = []
        while not grid.is_complete():
            params = grid.suggest()
            try:
                score = failing_backtest(params)
            except ValueError:
                score = Decimal("-Infinity")  # Optimizer would handle this
            grid.update(params, score)
            results.append((params, score))

        # Should complete all combinations
        assert len(results) == 3
        best_params = grid.get_best_params()
        assert best_params["window"] == 30  # Best of successful runs
