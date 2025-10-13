"""Tests for genetic algorithm optimization."""

import time
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
from rustybt.optimization.search.genetic_algorithm import GeneticAlgorithm


@pytest.fixture
def simple_param_space() -> ParameterSpace:
    """Create simple 2D continuous parameter space."""
    return ParameterSpace(
        parameters=[
            ContinuousParameter(name="x", min_value=Decimal("-5"), max_value=Decimal("5")),
            ContinuousParameter(name="y", min_value=Decimal("-5"), max_value=Decimal("5")),
        ]
    )


@pytest.fixture
def mixed_param_space() -> ParameterSpace:
    """Create mixed parameter space with continuous, discrete, and categorical."""
    return ParameterSpace(
        parameters=[
            ContinuousParameter(name="alpha", min_value=Decimal("0.001"), max_value=Decimal("0.1")),
            DiscreteParameter(name="lookback", min_value=10, max_value=100, step=5),
            CategoricalParameter(name="method", choices=["sma", "ema", "wma"]),
        ]
    )


def sphere_function(params: dict[str, Decimal]) -> Decimal:
    """Sphere function: f(x,y) = -(x^2 + y^2), optimal at (0,0)."""
    x = params["x"]
    y = params["y"]
    return -(x**2 + y**2)


def rastrigin_function(params: dict[str, Decimal]) -> Decimal:
    """Rastrigin function (non-smooth, multimodal): optimal at (0,0)."""
    x = float(params["x"])
    y = float(params["y"])
    A = 10
    return Decimal(
        str(-(2 * A + (x**2 - A * np.cos(2 * np.pi * x)) + (y**2 - A * np.cos(2 * np.pi * y))))
    )


class TestGeneticAlgorithmInitialization:
    """Test genetic algorithm initialization."""

    def test_initialization_default_params(self, simple_param_space: ParameterSpace) -> None:
        """Test initialization with default parameters."""
        ga = GeneticAlgorithm(parameter_space=simple_param_space)

        assert ga.population_size == 50
        assert ga.max_generations == 100
        assert ga.selection_method == "tournament"
        assert ga.tournament_size == 3
        assert ga.crossover_prob == 0.8
        assert ga.mutation_prob == 0.2
        assert ga.elite_size == 5  # 10% of 50
        assert ga.patience is None
        assert ga.target_fitness is None
        assert ga.max_time_seconds is None
        assert not ga.is_complete()

    def test_initialization_custom_params(self, simple_param_space: ParameterSpace) -> None:
        """Test initialization with custom parameters."""
        ga = GeneticAlgorithm(
            parameter_space=simple_param_space,
            population_size=100,
            max_generations=50,
            selection="roulette",
            crossover_prob=0.7,
            mutation_prob=0.3,
            elite_size=15,
            patience=10,
            target_fitness=Decimal("-0.01"),
            seed=42,
        )

        assert ga.population_size == 100
        assert ga.max_generations == 50
        assert ga.selection_method == "roulette"
        assert ga.crossover_prob == 0.7
        assert ga.mutation_prob == 0.3
        assert ga.elite_size == 15
        assert ga.patience == 10
        assert ga.target_fitness == Decimal("-0.01")
        assert ga.seed == 42

    def test_invalid_population_size(self, simple_param_space: ParameterSpace) -> None:
        """Test that invalid population size raises error."""
        with pytest.raises(ValueError, match="population_size must be >= 2"):
            GeneticAlgorithm(parameter_space=simple_param_space, population_size=1)

    def test_invalid_max_generations(self, simple_param_space: ParameterSpace) -> None:
        """Test that invalid max_generations raises error."""
        with pytest.raises(ValueError, match="max_generations must be >= 1"):
            GeneticAlgorithm(parameter_space=simple_param_space, max_generations=0)

    def test_invalid_crossover_prob(self, simple_param_space: ParameterSpace) -> None:
        """Test that invalid crossover probability raises error."""
        with pytest.raises(ValueError, match="crossover_prob must be in"):
            GeneticAlgorithm(parameter_space=simple_param_space, crossover_prob=1.5)

    def test_invalid_mutation_prob(self, simple_param_space: ParameterSpace) -> None:
        """Test that invalid mutation probability raises error."""
        with pytest.raises(ValueError, match="mutation_prob must be in"):
            GeneticAlgorithm(parameter_space=simple_param_space, mutation_prob=-0.1)

    def test_invalid_selection_method(self, simple_param_space: ParameterSpace) -> None:
        """Test that invalid selection method raises error."""
        with pytest.raises(ValueError, match="selection must be"):
            GeneticAlgorithm(parameter_space=simple_param_space, selection="invalid")

    def test_population_initialized(self, simple_param_space: ParameterSpace) -> None:
        """Test that population is initialized on creation."""
        ga = GeneticAlgorithm(parameter_space=simple_param_space, population_size=20)
        assert len(ga._population) == 20


class TestGeneticAlgorithmSuggest:
    """Test parameter suggestion."""

    def test_suggest_returns_valid_params(self, simple_param_space: ParameterSpace) -> None:
        """Test that suggest returns valid parameters."""
        ga = GeneticAlgorithm(parameter_space=simple_param_space, seed=42)
        params = ga.suggest()

        assert "x" in params
        assert "y" in params
        assert Decimal("-5") <= params["x"] <= Decimal("5")
        assert Decimal("-5") <= params["y"] <= Decimal("5")

    def test_suggest_mixed_params(self, mixed_param_space: ParameterSpace) -> None:
        """Test suggest with mixed parameter types."""
        ga = GeneticAlgorithm(parameter_space=mixed_param_space, seed=42)
        params = ga.suggest()

        assert "alpha" in params
        assert "lookback" in params
        assert "method" in params
        assert Decimal("0.001") <= params["alpha"] <= Decimal("0.1")
        assert 10 <= params["lookback"] <= 100
        assert params["lookback"] % 5 == 0  # Must be multiple of step
        assert params["method"] in ["sma", "ema", "wma"]

    def test_suggest_when_complete_raises_error(self, simple_param_space: ParameterSpace) -> None:
        """Test that suggest raises error when optimization complete."""
        ga = GeneticAlgorithm(
            parameter_space=simple_param_space, population_size=2, max_generations=1, seed=42
        )

        # Evaluate entire population
        while not ga.is_complete():
            params = ga.suggest()
            ga.update(params, sphere_function(params))

        # Should raise error
        with pytest.raises(ValueError, match="complete"):
            ga.suggest()


class TestGeneticAlgorithmUpdate:
    """Test fitness update."""

    def test_update_tracks_best_result(self, simple_param_space: ParameterSpace) -> None:
        """Test that update tracks best result."""
        ga = GeneticAlgorithm(parameter_space=simple_param_space, seed=42)

        # Evaluate a few individuals
        for _ in range(5):
            params = ga.suggest()
            score = sphere_function(params)
            ga.update(params, score)

        best_params, best_score = ga.get_best_result()
        assert best_score is not None
        assert best_params is not None

    def test_update_with_mismatched_params_raises_error(
        self, simple_param_space: ParameterSpace
    ) -> None:
        """Test that update with wrong params raises error."""
        ga = GeneticAlgorithm(parameter_space=simple_param_space, seed=42)
        ga.suggest()

        # Try to update with different params
        wrong_params = {"x": Decimal("1.0"), "y": Decimal("2.0")}

        with pytest.raises(ValueError, match="don't match"):
            ga.update(wrong_params, Decimal("-5.0"))

    def test_update_increments_iteration(self, simple_param_space: ParameterSpace) -> None:
        """Test that update increments iteration counter."""
        ga = GeneticAlgorithm(parameter_space=simple_param_space, seed=42)

        assert ga.iteration == 0

        params = ga.suggest()
        ga.update(params, sphere_function(params))

        assert ga.iteration == 1


class TestGeneticAlgorithmSelectionOperators:
    """Test selection operators."""

    @pytest.mark.parametrize("selection", ["tournament", "roulette", "rank"])
    def test_selection_operators(self, simple_param_space: ParameterSpace, selection: str) -> None:
        """Test different selection operators complete successfully."""
        ga = GeneticAlgorithm(
            parameter_space=simple_param_space,
            population_size=20,
            max_generations=3,
            selection=selection,
            seed=42,
        )

        while not ga.is_complete():
            params = ga.suggest()
            score = sphere_function(params)
            ga.update(params, score)

        assert ga.is_complete()
        best_params, best_score = ga.get_best_result()
        assert best_score is not None


class TestGeneticAlgorithmCrossover:
    """Test crossover operator."""

    def test_crossover_preserves_bounds(self, simple_param_space: ParameterSpace) -> None:
        """Test that crossover respects parameter bounds."""
        ga = GeneticAlgorithm(parameter_space=simple_param_space, crossover_prob=1.0, seed=42)

        # Run for one generation
        for _ in range(ga.population_size):
            params = ga.suggest()
            ga.update(params, sphere_function(params))

        # Check all individuals in new generation respect bounds
        for _ in range(min(10, ga.population_size)):
            params = ga.suggest()
            assert Decimal("-5") <= params["x"] <= Decimal("5")
            assert Decimal("-5") <= params["y"] <= Decimal("5")
            ga.update(params, sphere_function(params))

    def test_crossover_mixes_genes(self, simple_param_space: ParameterSpace) -> None:
        """Test that crossover creates variation."""
        ga = GeneticAlgorithm(
            parameter_space=simple_param_space, crossover_prob=1.0, population_size=10, seed=42
        )

        # Collect first generation
        gen0_params = []
        for _ in range(ga.population_size):
            params = ga.suggest()
            gen0_params.append(params.copy())
            ga.update(params, sphere_function(params))

        # Collect second generation
        gen1_params = []
        for _ in range(ga.population_size):
            params = ga.suggest()
            gen1_params.append(params.copy())
            ga.update(params, sphere_function(params))

        # Second generation should be different (due to crossover/mutation)
        # At least some individuals should differ
        differences = sum(
            1
            for p0, p1 in zip(gen0_params, gen1_params, strict=False)
            if p0["x"] != p1["x"] or p0["y"] != p1["y"]
        )
        assert differences > 0


class TestGeneticAlgorithmMutation:
    """Test mutation operator."""

    def test_mutation_adds_variation(self, simple_param_space: ParameterSpace) -> None:
        """Test that mutation adds variation to population."""
        ga = GeneticAlgorithm(
            parameter_space=simple_param_space, mutation_prob=1.0, population_size=10, seed=42
        )

        # Run for two generations
        for _ in range(2 * ga.population_size):
            params = ga.suggest()
            ga.update(params, sphere_function(params))

        # With 100% mutation, all individuals should have been mutated
        # Population should show variation
        diversity = ga._calculate_diversity()
        assert diversity > 0.0

    def test_mutation_preserves_bounds(self, simple_param_space: ParameterSpace) -> None:
        """Test that mutation respects parameter bounds."""
        ga = GeneticAlgorithm(parameter_space=simple_param_space, mutation_prob=1.0, seed=42)

        # Run several generations
        for _ in range(3 * ga.population_size):
            params = ga.suggest()
            assert Decimal("-5") <= params["x"] <= Decimal("5")
            assert Decimal("-5") <= params["y"] <= Decimal("5")
            ga.update(params, sphere_function(params))


class TestGeneticAlgorithmElitism:
    """Test elitism."""

    def test_elitism_preserves_best_individuals(self, simple_param_space: ParameterSpace) -> None:
        """Test that elites are preserved across generations."""
        ga = GeneticAlgorithm(
            parameter_space=simple_param_space, population_size=20, elite_size=5, seed=42
        )

        # Evaluate first generation
        for _ in range(ga.population_size):
            params = ga.suggest()
            ga.update(params, sphere_function(params))

        gen0_best_score = ga.get_best_result()[1]

        # Evaluate second generation
        for _ in range(ga.population_size):
            params = ga.suggest()
            ga.update(params, sphere_function(params))

        gen1_best_score = ga.get_best_result()[1]

        # With elitism, best score should never decrease
        assert gen1_best_score >= gen0_best_score


class TestGeneticAlgorithmEvolution:
    """Test evolution and fitness improvement."""

    def test_fitness_improves_over_generations(self, simple_param_space: ParameterSpace) -> None:
        """Test that population fitness improves over generations."""
        ga = GeneticAlgorithm(
            parameter_space=simple_param_space,
            population_size=30,
            max_generations=10,
            seed=42,
        )

        generation_best = []

        while not ga.is_complete():
            params = ga.suggest()
            score = sphere_function(params)
            ga.update(params, score)

            # Record best at end of each generation
            if ga._current_individual_idx == 0 and ga.current_generation > 0:
                generation_best.append(ga.get_best_result()[1])

        # Fitness should improve (or stay same) over generations
        if len(generation_best) > 1:
            assert generation_best[-1] >= generation_best[0]

        # Should find near-optimal solution for simple sphere function
        final_best = ga.get_best_result()[1]
        assert final_best >= Decimal("-1.0")  # Close to optimum (0)

    def test_ga_on_nonsmooth_function(self, simple_param_space: ParameterSpace) -> None:
        """Test GA on non-smooth Rastrigin function."""
        ga = GeneticAlgorithm(
            parameter_space=simple_param_space,
            population_size=50,
            max_generations=20,
            seed=42,
        )

        while not ga.is_complete():
            params = ga.suggest()
            score = rastrigin_function(params)
            ga.update(params, score)

        best_params, best_score = ga.get_best_result()

        # Should find reasonable solution (Rastrigin optimal is 0)
        # GA should get closer than random search
        assert best_score >= Decimal("-20.0")


class TestGeneticAlgorithmTermination:
    """Test termination criteria."""

    def test_terminates_at_max_generations(self, simple_param_space: ParameterSpace) -> None:
        """Test termination at max generations."""
        ga = GeneticAlgorithm(
            parameter_space=simple_param_space, population_size=10, max_generations=2, seed=42
        )

        # Run until complete
        while not ga.is_complete():
            params = ga.suggest()
            ga.update(params, sphere_function(params))

        assert ga.is_complete()
        assert ga.current_generation == 2
        assert "max_generations" in ga._termination_reason

    def test_terminates_with_patience(self, simple_param_space: ParameterSpace) -> None:
        """Test early stopping with patience."""
        # Use target that won't be reached so patience triggers
        ga = GeneticAlgorithm(
            parameter_space=simple_param_space,
            population_size=10,
            max_generations=100,
            patience=3,
            seed=42,
        )

        # Manually set best score so it won't improve
        ga._best_score = Decimal("0.0")
        ga._last_improvement_generation = 0

        # Run several generations
        gen_count = 0
        while not ga.is_complete() and gen_count < 10:
            params = ga.suggest()
            # Give worse scores
            ga.update(params, Decimal("-100.0"))
            if ga._current_individual_idx == 0:
                gen_count += 1

        # Should terminate due to patience
        assert ga.is_complete()
        assert "no_improvement" in ga._termination_reason

    def test_terminates_at_target_fitness(self, simple_param_space: ParameterSpace) -> None:
        """Test termination when target fitness reached."""
        ga = GeneticAlgorithm(
            parameter_space=simple_param_space,
            population_size=10,
            max_generations=100,
            target_fitness=Decimal("-0.1"),
            seed=42,
        )

        while not ga.is_complete():
            params = ga.suggest()
            score = sphere_function(params)
            ga.update(params, score)

        # Should terminate before max generations
        assert ga.is_complete()
        if "target_fitness" in ga._termination_reason:
            assert ga.current_generation < 100

    def test_terminates_at_time_limit(self, simple_param_space: ParameterSpace) -> None:
        """Test termination at time limit."""
        ga = GeneticAlgorithm(
            parameter_space=simple_param_space,
            population_size=5,
            max_generations=1000,
            max_time_seconds=0.1,  # Very short time limit
            seed=42,
        )

        while not ga.is_complete():
            params = ga.suggest()
            ga.update(params, sphere_function(params))
            time.sleep(0.01)  # Add small delay

        assert ga.is_complete()
        assert ga.current_generation < 1000


class TestGeneticAlgorithmDiversity:
    """Test diversity tracking."""

    def test_diversity_tracked(self, simple_param_space: ParameterSpace) -> None:
        """Test that diversity is tracked across generations."""
        ga = GeneticAlgorithm(
            parameter_space=simple_param_space, population_size=20, max_generations=3, seed=42
        )

        while not ga.is_complete():
            params = ga.suggest()
            ga.update(params, sphere_function(params))

        history = ga.get_generation_history()
        assert "diversity" in history
        assert len(history["diversity"]) > 0

    def test_low_diversity_warning(self, simple_param_space: ParameterSpace) -> None:
        """Test warning when diversity is low."""
        ga = GeneticAlgorithm(
            parameter_space=simple_param_space,
            population_size=10,
            max_generations=5,
            diversity_threshold=0.5,  # High threshold to trigger warning
            seed=42,
        )

        with pytest.warns(UserWarning, match="Low diversity"):
            while not ga.is_complete():
                params = ga.suggest()
                ga.update(params, sphere_function(params))


class TestGeneticAlgorithmStateManagement:
    """Test state save/restore."""

    def test_get_set_state(self, simple_param_space: ParameterSpace) -> None:
        """Test state can be saved and restored."""
        ga1 = GeneticAlgorithm(parameter_space=simple_param_space, seed=42)

        # Run for a few iterations
        for _ in range(10):
            params = ga1.suggest()
            ga1.update(params, sphere_function(params))

        # Save state
        state = ga1.get_state()

        # Create new instance and restore state
        ga2 = GeneticAlgorithm(parameter_space=simple_param_space)
        ga2.set_state(state)

        # States should match
        assert ga2.iteration == ga1.iteration
        assert ga2.current_generation == ga1.current_generation
        assert ga2._current_individual_idx == ga1._current_individual_idx
        assert ga2.get_best_result()[1] == ga1.get_best_result()[1]

    def test_resume_after_restore(self, simple_param_space: ParameterSpace) -> None:
        """Test optimization can continue after restore."""
        ga1 = GeneticAlgorithm(
            parameter_space=simple_param_space, population_size=10, max_generations=5, seed=42
        )

        # Run for one generation
        for _ in range(ga1.population_size):
            params = ga1.suggest()
            ga1.update(params, sphere_function(params))

        # Save state
        state = ga1.get_state()

        # Restore and continue
        ga2 = GeneticAlgorithm(parameter_space=simple_param_space)
        ga2.set_state(state)

        # Continue optimization
        while not ga2.is_complete():
            params = ga2.suggest()
            ga2.update(params, sphere_function(params))

        assert ga2.is_complete()

    def test_set_state_validates_missing_keys(self, simple_param_space: ParameterSpace) -> None:
        """Test set_state rejects state with missing keys."""
        ga = GeneticAlgorithm(parameter_space=simple_param_space)

        # Create incomplete state (missing required key)
        incomplete_state = {
            "iteration": 0,
            "population_size": 50,
            # Missing other required keys
        }

        with pytest.raises(ValueError, match="missing required keys"):
            ga.set_state(incomplete_state)

    def test_set_state_validates_parameter_ranges(self, simple_param_space: ParameterSpace) -> None:
        """Test set_state rejects invalid parameter values."""
        ga1 = GeneticAlgorithm(parameter_space=simple_param_space)

        # Run briefly to get valid state
        for _ in range(5):
            params = ga1.suggest()
            ga1.update(params, sphere_function(params))

        state = ga1.get_state()

        # Test invalid population_size
        ga2 = GeneticAlgorithm(parameter_space=simple_param_space)
        invalid_state = state.copy()
        invalid_state["population_size"] = -10
        with pytest.raises(ValueError, match="Invalid population_size"):
            ga2.set_state(invalid_state)

        # Test invalid max_generations
        ga3 = GeneticAlgorithm(parameter_space=simple_param_space)
        invalid_state = state.copy()
        invalid_state["max_generations"] = 200000
        with pytest.raises(ValueError, match="Invalid max_generations"):
            ga3.set_state(invalid_state)

        # Test invalid current_generation
        ga4 = GeneticAlgorithm(parameter_space=simple_param_space)
        invalid_state = state.copy()
        invalid_state["current_generation"] = -5
        with pytest.raises(ValueError, match="Invalid current_generation"):
            ga4.set_state(invalid_state)


class TestGeneticAlgorithmGetters:
    """Test getter methods."""

    def test_get_best_params(self, simple_param_space: ParameterSpace) -> None:
        """Test get_best_params returns best parameters."""
        ga = GeneticAlgorithm(parameter_space=simple_param_space, seed=42)

        # Should raise before any evaluations
        with pytest.raises(ValueError, match="No results"):
            ga.get_best_params()

        # Run a few iterations
        for _ in range(5):
            params = ga.suggest()
            ga.update(params, sphere_function(params))

        best_params = ga.get_best_params()
        assert "x" in best_params
        assert "y" in best_params

    def test_get_generation_history(self, simple_param_space: ParameterSpace) -> None:
        """Test get_generation_history returns statistics."""
        ga = GeneticAlgorithm(
            parameter_space=simple_param_space, population_size=10, max_generations=3, seed=42
        )

        while not ga.is_complete():
            params = ga.suggest()
            ga.update(params, sphere_function(params))

        history = ga.get_generation_history()
        assert "generation" in history
        assert "best_fitness" in history
        assert "avg_fitness" in history
        assert "diversity" in history
        assert len(history["best_fitness"]) == 3  # 3 completed generations

    def test_progress_property(self, simple_param_space: ParameterSpace) -> None:
        """Test progress property returns correct ratio."""
        ga = GeneticAlgorithm(
            parameter_space=simple_param_space, population_size=10, max_generations=5, seed=42
        )

        assert ga.progress == 0.0

        # Run one generation
        for _ in range(ga.population_size):
            params = ga.suggest()
            ga.update(params, sphere_function(params))

        assert 0.0 < ga.progress < 1.0


class TestGeneticAlgorithmPropertyTests:
    """Property-based tests using Hypothesis."""

    @given(
        pop_size=st.integers(min_value=10, max_value=50),
        n_params=st.integers(min_value=2, max_value=5),
    )
    def test_all_individuals_respect_bounds(self, pop_size: int, n_params: int) -> None:
        """Test that all individuals respect parameter bounds."""
        params = [
            ContinuousParameter(name=f"x{i}", min_value=Decimal("0"), max_value=Decimal("1"))
            for i in range(n_params)
        ]
        param_space = ParameterSpace(parameters=params)

        ga = GeneticAlgorithm(parameter_space=param_space, population_size=pop_size, seed=42)

        # Check several individuals
        for _ in range(min(pop_size, 20)):
            suggested_params = ga.suggest()

            # All parameters should be in [0, 1]
            for i in range(n_params):
                value = suggested_params[f"x{i}"]
                assert Decimal("0") <= value <= Decimal("1")

            # Update with dummy score
            ga.update(suggested_params, Decimal("0.5"))

    @given(seed=st.integers(min_value=0, max_value=10000))
    def test_reproducibility_with_seed(self, seed: int) -> None:
        """Test that same seed produces same sequence."""
        param_space = ParameterSpace(
            parameters=[
                ContinuousParameter(name="x", min_value=Decimal("-1"), max_value=Decimal("1"))
            ]
        )

        ga1 = GeneticAlgorithm(parameter_space=param_space, population_size=5, seed=seed)
        ga2 = GeneticAlgorithm(parameter_space=param_space, population_size=5, seed=seed)

        # First few suggestions should match
        for _ in range(5):
            params1 = ga1.suggest()
            params2 = ga2.suggest()
            assert params1["x"] == params2["x"]

            ga1.update(params1, Decimal("0.0"))
            ga2.update(params2, Decimal("0.0"))
