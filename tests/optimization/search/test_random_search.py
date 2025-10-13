"""Tests for random search algorithm."""

import concurrent.futures
import warnings
from decimal import Decimal

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
from rustybt.optimization.search import RandomSearchAlgorithm


class TestRandomSearchAlgorithm:
    """Tests for RandomSearchAlgorithm."""

    def test_initialization(self):
        """Test random search initialization."""
        param_space = ParameterSpace(
            parameters=[
                ContinuousParameter(
                    name="lr", min_value=Decimal("0.001"), max_value=Decimal("0.1")
                ),
            ]
        )

        search_alg = RandomSearchAlgorithm(param_space, n_iter=10, seed=42)

        assert search_alg.n_iter == 10
        assert search_alg.seed == 42
        assert search_alg.iteration == 0
        assert search_alg.is_complete() is False

    def test_initialization_invalid_n_iter(self):
        """Test initialization fails with invalid n_iter."""
        param_space = ParameterSpace(
            parameters=[
                ContinuousParameter(
                    name="lr", min_value=Decimal("0.001"), max_value=Decimal("0.1")
                ),
            ]
        )

        with pytest.raises(ValueError, match="n_iter must be positive"):
            RandomSearchAlgorithm(param_space, n_iter=0, seed=42)

        with pytest.raises(ValueError, match="n_iter must be positive"):
            RandomSearchAlgorithm(param_space, n_iter=-5, seed=42)

    def test_initialization_invalid_max_retries(self):
        """Test initialization fails with invalid max_retries."""
        param_space = ParameterSpace(
            parameters=[
                ContinuousParameter(
                    name="lr", min_value=Decimal("0.001"), max_value=Decimal("0.1")
                ),
            ]
        )

        with pytest.raises(ValueError, match="max_retries must be positive"):
            RandomSearchAlgorithm(param_space, n_iter=10, seed=42, max_retries=0)

    def test_suggest_uniform_distribution(self):
        """Test uniform distribution sampling."""
        param_space = ParameterSpace(
            parameters=[
                ContinuousParameter(
                    name="lr",
                    min_value=Decimal("0.001"),
                    max_value=Decimal("0.1"),
                    prior="uniform",
                ),
            ]
        )

        search_alg = RandomSearchAlgorithm(param_space, n_iter=1000, seed=42)

        # Sample many values
        values = []
        for _ in range(1000):
            params = search_alg.suggest()
            values.append(float(params["lr"]))
            search_alg.update(params, Decimal("1.0"))

        # Check all values in bounds
        assert all(0.001 <= v <= 0.1 for v in values)

        # Check mean is approximately in the middle (uniform distribution)
        mean_value = np.mean(values)
        expected_mean = (0.001 + 0.1) / 2
        # Allow 10% deviation due to randomness
        assert abs(mean_value - expected_mean) < expected_mean * 0.1

    def test_suggest_log_uniform_distribution(self):
        """Test log-uniform distribution sampling."""
        param_space = ParameterSpace(
            parameters=[
                ContinuousParameter(
                    name="lr",
                    min_value=Decimal("0.0001"),
                    max_value=Decimal("0.1"),
                    prior="log-uniform",
                ),
            ]
        )

        search_alg = RandomSearchAlgorithm(param_space, n_iter=1000, seed=42)

        # Sample many values
        values = []
        for _ in range(1000):
            params = search_alg.suggest()
            values.append(float(params["lr"]))
            search_alg.update(params, Decimal("1.0"))

        # Check all values in bounds
        assert all(0.0001 <= v <= 0.1 for v in values)

        # With log-uniform, samples should be distributed uniformly in log space
        # Count samples in logarithmic buckets: [0.0001, 0.001), [0.001, 0.01), [0.01, 0.1]
        bucket1 = sum(1 for v in values if 0.0001 <= v < 0.001)
        bucket2 = sum(1 for v in values if 0.001 <= v < 0.01)
        bucket3 = sum(1 for v in values if 0.01 <= v <= 0.1)

        # Each bucket spans 1 order of magnitude, should have roughly equal counts
        # Allow 50% variation due to randomness
        expected_per_bucket = 1000 / 3
        assert abs(bucket1 - expected_per_bucket) < expected_per_bucket * 0.5
        assert abs(bucket2 - expected_per_bucket) < expected_per_bucket * 0.5
        assert abs(bucket3 - expected_per_bucket) < expected_per_bucket * 0.5

    def test_suggest_log_uniform_negative_bounds_fails(self):
        """Test log-uniform with negative bounds raises error."""
        param_space = ParameterSpace(
            parameters=[
                ContinuousParameter(
                    name="lr",
                    min_value=Decimal("-0.1"),
                    max_value=Decimal("0.1"),
                    prior="log-uniform",
                ),
            ]
        )

        search_alg = RandomSearchAlgorithm(param_space, n_iter=10, seed=42)

        with pytest.raises(ValueError, match="log-uniform prior requires positive bounds"):
            search_alg.suggest()

    def test_suggest_normal_distribution(self):
        """Test normal distribution sampling (clipped to bounds)."""
        param_space = ParameterSpace(
            parameters=[
                ContinuousParameter(
                    name="lr",
                    min_value=Decimal("0.0"),
                    max_value=Decimal("1.0"),
                    prior="normal",
                ),
            ]
        )

        search_alg = RandomSearchAlgorithm(param_space, n_iter=1000, seed=42)

        # Sample many values
        values = []
        for _ in range(1000):
            params = search_alg.suggest()
            values.append(float(params["lr"]))
            search_alg.update(params, Decimal("1.0"))

        # Check all values in bounds (clipped)
        assert all(0.0 <= v <= 1.0 for v in values)

        # Check mean is approximately in the middle
        mean_value = np.mean(values)
        expected_mean = 0.5
        # Normal distribution should cluster around mean
        assert abs(mean_value - expected_mean) < 0.1

    def test_suggest_discrete_parameter(self):
        """Test suggesting discrete parameter values."""
        param_space = ParameterSpace(
            parameters=[
                DiscreteParameter(name="window", min_value=10, max_value=50, step=10),
            ]
        )

        search_alg = RandomSearchAlgorithm(param_space, n_iter=100, seed=42)

        # Sample many values
        values = []
        for _ in range(100):
            params = search_alg.suggest()
            values.append(params["window"])
            search_alg.update(params, Decimal("1.0"))

        # Check all values are valid
        assert all(v in [10, 20, 30, 40, 50] for v in values)

        # Check all values appear at least once (with 100 samples, should hit all 5)
        unique_values = set(values)
        assert len(unique_values) >= 4  # Allow some variation

    def test_suggest_categorical_parameter(self):
        """Test suggesting categorical parameter values."""
        param_space = ParameterSpace(
            parameters=[
                CategoricalParameter(name="opt", choices=["adam", "sgd", "rmsprop"]),
            ]
        )

        search_alg = RandomSearchAlgorithm(param_space, n_iter=100, seed=42)

        # Sample many values
        values = []
        for _ in range(100):
            params = search_alg.suggest()
            values.append(params["opt"])
            search_alg.update(params, Decimal("1.0"))

        # Check all values are valid choices
        assert all(v in ["adam", "sgd", "rmsprop"] for v in values)

        # Check all choices appear at least once
        unique_values = set(values)
        assert len(unique_values) == 3

    def test_suggest_multiple_parameters(self):
        """Test suggesting multiple parameters at once."""
        param_space = ParameterSpace(
            parameters=[
                ContinuousParameter(
                    name="lr",
                    min_value=Decimal("0.001"),
                    max_value=Decimal("0.1"),
                    prior="uniform",
                ),
                DiscreteParameter(name="window", min_value=10, max_value=50, step=10),
                CategoricalParameter(name="opt", choices=["adam", "sgd"]),
            ]
        )

        search_alg = RandomSearchAlgorithm(param_space, n_iter=10, seed=42)

        params = search_alg.suggest()

        assert len(params) == 3
        assert "lr" in params
        assert "window" in params
        assert "opt" in params

        # Validate against parameter space
        param_space.validate_params(params)

    def test_reproducibility_with_seed(self):
        """Test same seed produces identical sample sequence."""
        param_space = ParameterSpace(
            parameters=[
                ContinuousParameter(
                    name="lr",
                    min_value=Decimal("0.001"),
                    max_value=Decimal("0.1"),
                    prior="uniform",
                ),
                DiscreteParameter(name="window", min_value=10, max_value=50, step=10),
            ]
        )

        search_alg1 = RandomSearchAlgorithm(param_space, n_iter=10, seed=42)
        search_alg2 = RandomSearchAlgorithm(param_space, n_iter=10, seed=42)

        # Get suggestions from both
        for _ in range(10):
            params1 = search_alg1.suggest()
            params2 = search_alg2.suggest()

            # Should be identical
            assert params1 == params2

            search_alg1.update(params1, Decimal("1.0"))
            search_alg2.update(params2, Decimal("1.0"))

    def test_different_samples_without_seed(self):
        """Test random search produces different values without seed."""
        param_space = ParameterSpace(
            parameters=[
                ContinuousParameter(
                    name="lr",
                    min_value=Decimal("0.001"),
                    max_value=Decimal("0.1"),
                    prior="uniform",
                ),
            ]
        )

        # No seed provided - should use different seeds internally
        search_alg1 = RandomSearchAlgorithm(param_space, n_iter=5)
        search_alg2 = RandomSearchAlgorithm(param_space, n_iter=5)

        params1 = search_alg1.suggest()
        params2 = search_alg2.suggest()

        # Very unlikely to be exactly equal
        assert params1["lr"] != params2["lr"]

    def test_duplicate_prevention(self):
        """Test duplicate parameter combinations are prevented."""
        # Small parameter space to force duplicates
        param_space = ParameterSpace(
            parameters=[
                DiscreteParameter(name="x", min_value=1, max_value=3, step=1),
                CategoricalParameter(name="y", choices=["a", "b"]),
            ]
        )

        # Request more samples than possible combinations (3 * 2 = 6)
        search_alg = RandomSearchAlgorithm(param_space, n_iter=6, seed=42)

        seen_params = set()
        for _ in range(6):
            params = search_alg.suggest()
            params_tuple = (params["x"], params["y"])

            # Should not see duplicates
            assert params_tuple not in seen_params
            seen_params.add(params_tuple)

            search_alg.update(params, Decimal("1.0"))

        # Should have seen all 6 unique combinations
        assert len(seen_params) == 6

    def test_duplicate_prevention_warning(self):
        """Test warning when duplicate rate is high."""
        # Very small parameter space
        param_space = ParameterSpace(
            parameters=[
                DiscreteParameter(name="x", min_value=1, max_value=2, step=1),
            ]
        )

        # Request way more samples than possible (only 2 unique values)
        search_alg = RandomSearchAlgorithm(param_space, n_iter=10, seed=42, max_retries=5)

        # First 2 should succeed without warning
        for _ in range(2):
            params = search_alg.suggest()
            search_alg.update(params, Decimal("1.0"))

        # Next ones should trigger warning eventually
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            for _ in range(8):
                params = search_alg.suggest()
                search_alg.update(params, Decimal("1.0"))

            # Should have gotten at least one warning
            assert len(w) > 0
            assert "High duplicate rate" in str(w[0].message)

    def test_best_result_tracking(self):
        """Test tracking of best parameters and score."""
        param_space = ParameterSpace(
            parameters=[
                ContinuousParameter(
                    name="lr",
                    min_value=Decimal("0.001"),
                    max_value=Decimal("0.1"),
                    prior="uniform",
                ),
            ]
        )

        search_alg = RandomSearchAlgorithm(param_space, n_iter=5, seed=42)

        scores = [Decimal("1.5"), Decimal("2.0"), Decimal("1.8"), Decimal("2.5"), Decimal("1.9")]
        params_list = []

        for score in scores:
            params = search_alg.suggest()
            params_list.append(params)
            search_alg.update(params, score)

        # Best should be the one with score 2.5
        best_params, best_score = search_alg.get_best_result()
        assert best_score == Decimal("2.5")
        assert best_params == params_list[3]

        # get_best_params should return same
        assert search_alg.get_best_params() == params_list[3]

    def test_best_result_no_results_raises(self):
        """Test getting best result before any evaluations raises error."""
        param_space = ParameterSpace(
            parameters=[
                ContinuousParameter(
                    name="lr",
                    min_value=Decimal("0.001"),
                    max_value=Decimal("0.1"),
                    prior="uniform",
                ),
            ]
        )

        search_alg = RandomSearchAlgorithm(param_space, n_iter=5, seed=42)

        with pytest.raises(ValueError, match="No results available"):
            search_alg.get_best_params()

        with pytest.raises(ValueError, match="No results available"):
            search_alg.get_best_result()

    def test_get_results_sorted(self):
        """Test getting all results sorted by score."""
        param_space = ParameterSpace(
            parameters=[
                ContinuousParameter(
                    name="lr",
                    min_value=Decimal("0.001"),
                    max_value=Decimal("0.1"),
                    prior="uniform",
                ),
            ]
        )

        search_alg = RandomSearchAlgorithm(param_space, n_iter=5, seed=42)

        scores = [Decimal("1.5"), Decimal("2.0"), Decimal("1.8"), Decimal("2.5"), Decimal("1.9")]

        for score in scores:
            params = search_alg.suggest()
            search_alg.update(params, score)

        results = search_alg.get_results()

        # Should be sorted by score descending
        assert len(results) == 5
        assert results[0][1] == Decimal("2.5")
        assert results[1][1] == Decimal("2.0")
        assert results[2][1] == Decimal("1.9")
        assert results[3][1] == Decimal("1.8")
        assert results[4][1] == Decimal("1.5")

    def test_get_results_top_k(self):
        """Test getting top K results."""
        param_space = ParameterSpace(
            parameters=[
                ContinuousParameter(
                    name="lr",
                    min_value=Decimal("0.001"),
                    max_value=Decimal("0.1"),
                    prior="uniform",
                ),
            ]
        )

        search_alg = RandomSearchAlgorithm(param_space, n_iter=5, seed=42)

        scores = [Decimal("1.5"), Decimal("2.0"), Decimal("1.8"), Decimal("2.5"), Decimal("1.9")]

        for score in scores:
            params = search_alg.suggest()
            search_alg.update(params, score)

        top_3 = search_alg.get_results(top_k=3)

        # Should get top 3 results
        assert len(top_3) == 3
        assert top_3[0][1] == Decimal("2.5")
        assert top_3[1][1] == Decimal("2.0")
        assert top_3[2][1] == Decimal("1.9")

    def test_update_increments_iteration(self):
        """Test update increments iteration counter."""
        param_space = ParameterSpace(
            parameters=[
                ContinuousParameter(
                    name="lr",
                    min_value=Decimal("0.001"),
                    max_value=Decimal("0.1"),
                    prior="uniform",
                ),
            ]
        )

        search_alg = RandomSearchAlgorithm(param_space, n_iter=5, seed=42)

        assert search_alg.iteration == 0

        params = search_alg.suggest()
        search_alg.update(params, Decimal("1.5"))

        assert search_alg.iteration == 1

    def test_is_complete(self):
        """Test completion check."""
        param_space = ParameterSpace(
            parameters=[
                ContinuousParameter(
                    name="lr",
                    min_value=Decimal("0.001"),
                    max_value=Decimal("0.1"),
                    prior="uniform",
                ),
            ]
        )

        search_alg = RandomSearchAlgorithm(param_space, n_iter=3, seed=42)

        assert search_alg.is_complete() is False

        # Run 3 iterations
        for _ in range(3):
            params = search_alg.suggest()
            search_alg.update(params, Decimal("1.0"))

        assert search_alg.is_complete() is True

    def test_suggest_after_complete_raises(self):
        """Test suggesting after completion raises error."""
        param_space = ParameterSpace(
            parameters=[
                ContinuousParameter(
                    name="lr",
                    min_value=Decimal("0.001"),
                    max_value=Decimal("0.1"),
                    prior="uniform",
                ),
            ]
        )

        search_alg = RandomSearchAlgorithm(param_space, n_iter=2, seed=42)

        # Complete the trials
        for _ in range(2):
            params = search_alg.suggest()
            search_alg.update(params, Decimal("1.0"))

        # Should raise on next suggest
        with pytest.raises(ValueError, match="Random search is complete"):
            search_alg.suggest()

    def test_progress_property(self):
        """Test progress property returns correct ratio."""
        param_space = ParameterSpace(
            parameters=[
                ContinuousParameter(
                    name="lr",
                    min_value=Decimal("0.001"),
                    max_value=Decimal("0.1"),
                    prior="uniform",
                ),
            ]
        )

        search_alg = RandomSearchAlgorithm(param_space, n_iter=10, seed=42)

        assert search_alg.progress == 0.0

        # Run 5 iterations
        for _ in range(5):
            params = search_alg.suggest()
            search_alg.update(params, Decimal("1.0"))

        assert search_alg.progress == 0.5

        # Complete remaining
        for _ in range(5):
            params = search_alg.suggest()
            search_alg.update(params, Decimal("1.0"))

        assert search_alg.progress == 1.0

    def test_duplicate_rate_property(self):
        """Test duplicate_rate property calculation."""
        # Small space to force duplicates
        param_space = ParameterSpace(
            parameters=[
                DiscreteParameter(name="x", min_value=1, max_value=2, step=1),
            ]
        )

        search_alg = RandomSearchAlgorithm(param_space, n_iter=2, seed=42, max_retries=5)

        # First 2 samples should be unique
        for _ in range(2):
            params = search_alg.suggest()
            search_alg.update(params, Decimal("1.0"))

        # Duplicate rate should be low or zero
        assert search_alg.duplicate_rate >= 0.0

    def test_thread_safety_parallel_suggest_update(self):
        """Test thread-safe parallel execution."""
        param_space = ParameterSpace(
            parameters=[
                ContinuousParameter(
                    name="lr",
                    min_value=Decimal("0.001"),
                    max_value=Decimal("0.1"),
                    prior="uniform",
                ),
            ]
        )

        search_alg = RandomSearchAlgorithm(param_space, n_iter=20, seed=42)

        def run_trial():
            """Run single trial (suggest + update)."""
            try:
                params = search_alg.suggest()
                score = Decimal(str(float(params["lr"]) * 10))  # Some function of params
                search_alg.update(params, score)
                return True
            except ValueError:
                # Might complete during parallel execution
                return False

        # Run 20 trials in parallel with 4 workers
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(run_trial) for _ in range(20)]
            [f.result() for f in concurrent.futures.as_completed(futures)]

        # Should have completed exactly 20 trials
        assert search_alg.iteration == 20
        assert search_alg.is_complete()

        # Should have 20 results
        assert len(search_alg.get_results()) == 20

    def test_get_state(self):
        """Test getting algorithm state."""
        param_space = ParameterSpace(
            parameters=[
                ContinuousParameter(
                    name="lr",
                    min_value=Decimal("0.001"),
                    max_value=Decimal("0.1"),
                    prior="uniform",
                ),
            ]
        )

        search_alg = RandomSearchAlgorithm(param_space, n_iter=5, seed=42)

        # Run a few iterations
        for _ in range(3):
            params = search_alg.suggest()
            search_alg.update(params, Decimal("1.5"))

        state = search_alg.get_state()

        assert "iteration" in state
        assert "n_iter" in state
        assert "seed" in state
        assert "rng_state" in state
        assert "seen_params" in state
        assert "best_params" in state
        assert "best_score" in state
        assert "results" in state

        assert state["iteration"] == 3
        assert len(state["results"]) == 3

    def test_set_state(self):
        """Test restoring algorithm state."""
        param_space = ParameterSpace(
            parameters=[
                ContinuousParameter(
                    name="lr",
                    min_value=Decimal("0.001"),
                    max_value=Decimal("0.1"),
                    prior="uniform",
                ),
            ]
        )

        # Create and run original algorithm
        search_alg1 = RandomSearchAlgorithm(param_space, n_iter=5, seed=42)

        for _ in range(3):
            params = search_alg1.suggest()
            search_alg1.update(params, Decimal("1.5"))

        state = search_alg1.get_state()

        # Create new algorithm and restore state
        search_alg2 = RandomSearchAlgorithm(param_space, n_iter=10, seed=99)
        search_alg2.set_state(state)

        assert search_alg2.iteration == 3
        assert len(search_alg2.get_results()) == 3
        assert search_alg2.n_iter == 5
        assert search_alg2.seed == 42

    def test_state_round_trip_maintains_reproducibility(self):
        """Test state save/restore maintains reproducibility."""
        param_space = ParameterSpace(
            parameters=[
                ContinuousParameter(
                    name="lr",
                    min_value=Decimal("0.001"),
                    max_value=Decimal("0.1"),
                    prior="uniform",
                ),
            ]
        )

        # Original algorithm - run 3 iterations
        search_alg1 = RandomSearchAlgorithm(param_space, n_iter=10, seed=42)

        for _ in range(3):
            params = search_alg1.suggest()
            search_alg1.update(params, Decimal("1.0"))

        # Save state
        state = search_alg1.get_state()

        # Continue with first algorithm
        next_params1 = search_alg1.suggest()

        # Restore state to new algorithm
        search_alg2 = RandomSearchAlgorithm(param_space, n_iter=10)
        search_alg2.set_state(state)

        # Get next suggestion from restored algorithm
        next_params2 = search_alg2.suggest()

        # Should be identical
        assert next_params1 == next_params2


class TestRandomSearchPropertyBased:
    """Property-based tests for RandomSearchAlgorithm."""

    @given(n_iter=st.integers(min_value=1, max_value=100))
    def test_sample_count_invariant(self, n_iter):
        """Random search must generate exactly n_iter samples."""
        param_space = ParameterSpace(
            parameters=[
                ContinuousParameter(
                    name="x",
                    min_value=Decimal("0"),
                    max_value=Decimal("1"),
                    prior="uniform",
                )
            ]
        )

        rs = RandomSearchAlgorithm(param_space, n_iter=n_iter, seed=42)

        samples = []
        while not rs.is_complete():
            params = rs.suggest()
            samples.append(params)
            rs.update(params, Decimal("1.0"))

        assert len(samples) == n_iter

    @given(
        min_val=st.decimals(min_value=Decimal("0"), max_value=Decimal("1")),
        max_val=st.decimals(min_value=Decimal("1"), max_value=Decimal("10")),
    )
    def test_samples_within_bounds_invariant(self, min_val, max_val):
        """All samples must be within parameter bounds."""
        from hypothesis import assume

        # Ensure max_val > min_val (required by parameter validation)
        assume(max_val > min_val)

        param_space = ParameterSpace(
            parameters=[
                ContinuousParameter(name="x", min_value=min_val, max_value=max_val, prior="uniform")
            ]
        )

        rs = RandomSearchAlgorithm(param_space, n_iter=50, seed=42)

        for _ in range(50):
            params = rs.suggest()
            assert min_val <= params["x"] <= max_val
            rs.update(params, Decimal("1.0"))

    @given(seed=st.integers(min_value=0, max_value=10000))
    def test_seed_determinism_invariant(self, seed):
        """Same seed must produce identical sequences."""
        param_space = ParameterSpace(
            parameters=[
                ContinuousParameter(
                    name="x",
                    min_value=Decimal("0"),
                    max_value=Decimal("1"),
                    prior="uniform",
                )
            ]
        )

        rs1 = RandomSearchAlgorithm(param_space, n_iter=10, seed=seed)
        rs2 = RandomSearchAlgorithm(param_space, n_iter=10, seed=seed)

        samples1 = []
        samples2 = []

        for _ in range(10):
            p1 = rs1.suggest()
            p2 = rs2.suggest()
            samples1.append(p1)
            samples2.append(p2)
            rs1.update(p1, Decimal("1.0"))
            rs2.update(p2, Decimal("1.0"))

        assert samples1 == samples2
