"""Genetic algorithm optimization implementation using DEAP."""

# SECURITY FIX (Story 8.10): Use secure pickle with HMAC validation
import time
import warnings
from decimal import Decimal
from threading import Lock
from typing import Any

import numpy as np
import structlog
from deap import base, creator, tools

from rustybt.optimization.base import SearchAlgorithm
from rustybt.optimization.parameter_space import (
    CategoricalParameter,
    ContinuousParameter,
    DiscreteParameter,
    ParameterSpace,
)
from rustybt.utils.secure_pickle import SecurePickleError, secure_dumps, secure_loads

logger = structlog.get_logger()


class GeneticAlgorithm(SearchAlgorithm):
    """Genetic algorithm optimization using natural selection principles.

    Evolves population of candidate solutions using selection, crossover, and
    mutation operators. Excels on non-smooth, multimodal objective functions.

    Best for:
        - Non-smooth or discontinuous objectives
        - Multimodal landscapes (many local optima)
        - Mixed parameter types (continuous + categorical)
        - Cheap evaluations (GA needs 100s-1000s of evaluations)

    Don't use when:
        - Smooth, unimodal objectives → Bayesian faster
        - Expensive evaluations → Bayesian more sample-efficient
        - Very high dimensions (>50 params) → Curse of dimensionality

    Example:
        >>> from rustybt.optimization.parameter_space import (
        ...     ParameterSpace, ContinuousParameter
        ... )
        >>> param_space = ParameterSpace(parameters=[
        ...     ContinuousParameter(name='lookback', min_value=10, max_value=100),
        ...     ContinuousParameter(name='threshold', min_value=0.01, max_value=0.1)
        ... ])
        >>> ga = GeneticAlgorithm(
        ...     parameter_space=param_space,
        ...     population_size=50,
        ...     max_generations=100,
        ...     selection='tournament'
        ... )
        >>> while not ga.is_complete():
        ...     params = ga.suggest()
        ...     result = run_backtest(**params)
        ...     ga.update(params, result['sharpe_ratio'])
        >>> best_params = ga.get_best_params()

    Args:
        parameter_space: Parameter space defining search domain
        population_size: Number of individuals in population (default: 50)
        max_generations: Maximum generations (default: 100)
        selection: Selection operator - 'tournament', 'roulette', 'rank' (default: 'tournament')
        tournament_size: Tournament size for tournament selection (default: 3)
        crossover_prob: Crossover probability (default: 0.8)
        mutation_prob: Mutation probability (default: 0.2)
        elite_size: Number of elites to preserve (default: 10% of population)
        patience: Stop if no improvement for N generations (default: None = disabled)
        target_fitness: Stop if fitness >= target (default: None = disabled)
        max_time_seconds: Maximum optimization time in seconds (default: None = disabled)
        diversity_threshold: Warn if diversity below threshold (default: 0.01)
        seed: Random seed for reproducibility (default: None)
    """

    def __init__(
        self,
        parameter_space: ParameterSpace,
        population_size: int = 50,
        max_generations: int = 100,
        selection: str = "tournament",
        tournament_size: int = 3,
        crossover_prob: float = 0.8,
        mutation_prob: float = 0.2,
        elite_size: int | None = None,
        patience: int | None = None,
        target_fitness: Decimal | None = None,
        max_time_seconds: float | None = None,
        diversity_threshold: float = 0.01,
        seed: int | None = None,
    ):
        """Initialize genetic algorithm.

        Args:
            parameter_space: Parameter space to search
            population_size: Number of individuals (default: 50)
            max_generations: Max generations (default: 100)
            selection: Selection method (default: 'tournament')
            tournament_size: Tournament size (default: 3)
            crossover_prob: Crossover probability (default: 0.8)
            mutation_prob: Mutation probability (default: 0.2)
            elite_size: Elite count (default: 10% of population)
            patience: Early stopping patience (default: None)
            target_fitness: Target fitness for early stopping (default: None)
            max_time_seconds: Time limit (default: None)
            diversity_threshold: Diversity warning threshold (default: 0.01)
            seed: Random seed (default: None)

        Raises:
            ValueError: If parameters are invalid
        """
        super().__init__(parameter_space)

        # Validate parameters
        if population_size < 2:
            raise ValueError("population_size must be >= 2")
        if max_generations < 1:
            raise ValueError("max_generations must be >= 1")
        if not 0.0 <= crossover_prob <= 1.0:
            raise ValueError("crossover_prob must be in [0, 1]")
        if not 0.0 <= mutation_prob <= 1.0:
            raise ValueError("mutation_prob must be in [0, 1]")
        if selection not in {"tournament", "roulette", "rank"}:
            raise ValueError("selection must be 'tournament', 'roulette', or 'rank'")
        if tournament_size < 2:
            raise ValueError("tournament_size must be >= 2")

        self.population_size = population_size
        self.max_generations = max_generations
        self.selection_method = selection
        self.tournament_size = tournament_size
        self.crossover_prob = crossover_prob
        self.mutation_prob = mutation_prob
        self.elite_size = elite_size if elite_size is not None else max(1, population_size // 10)
        self.patience = patience
        self.target_fitness = target_fitness
        self.max_time_seconds = max_time_seconds
        self.diversity_threshold = diversity_threshold
        self.seed = seed

        # Random number generator
        self._rng = np.random.Generator(np.random.PCG64(seed))

        # Thread safety
        self._lock = Lock()

        # Initialize DEAP framework
        self._setup_deap()

        # Population state
        self._population: list[Any] = []
        self._current_generation = 0
        self._current_individual_idx = 0
        self._pending_individual: dict[str, Any] | None = None

        # Best result tracking
        self._best_params: dict[str, Any] | None = None
        self._best_score: Decimal | None = None
        self._generations_without_improvement = 0
        self._last_improvement_generation = 0

        # History tracking
        self._generation_best_scores: list[Decimal] = []
        self._generation_avg_scores: list[Decimal] = []
        self._diversity_history: list[float] = []

        # Timing
        self._start_time: float | None = None

        # Termination reason
        self._termination_reason: str | None = None

        # Initialize first population
        self._initialize_population()

        self._is_initialized = True

    def _setup_deap(self) -> None:
        """Setup DEAP creator and toolbox."""
        # Clean up any existing DEAP types
        if hasattr(creator, "FitnessMax"):
            del creator.FitnessMax
        if hasattr(creator, "Individual"):
            del creator.Individual

        # Create fitness and individual classes
        creator.create("FitnessMax", base.Fitness, weights=(1.0,))  # Maximize fitness
        creator.create("Individual", list, fitness=creator.FitnessMax)

        # Create toolbox
        self.toolbox = base.Toolbox()

        # Register parameter sampling
        self.toolbox.register("individual", self._create_individual)
        self.toolbox.register("population", tools.initRepeat, list, self.toolbox.individual)

        # Register genetic operators
        self._register_selection()
        self._register_crossover()
        self._register_mutation()

    def _register_selection(self) -> None:
        """Register selection operator."""
        if self.selection_method == "tournament":
            self.toolbox.register("select", tools.selTournament, tournsize=self.tournament_size)
        elif self.selection_method == "roulette":
            self.toolbox.register("select", tools.selRoulette)
        elif self.selection_method == "rank":
            # Use tournament selection with larger tournament size as rank-based alternative
            # This provides similar rank-based behavior while being more robust
            tournsize = min(5, self.population_size)
            self.toolbox.register("select", tools.selTournament, tournsize=tournsize)

    def _register_crossover(self) -> None:
        """Register crossover operator."""
        # Use blend crossover for continuous parameters
        self.toolbox.register("mate", self._crossover)

    def _register_mutation(self) -> None:
        """Register mutation operator."""
        self.toolbox.register("mutate", self._mutate)

    def _create_individual(self) -> Any:
        """Create random individual (genotype).

        Returns:
            DEAP Individual with random gene values
        """
        genes = []

        for param in self.parameter_space.parameters:
            if isinstance(param, ContinuousParameter):
                # Random float in [min, max]
                value = self._rng.uniform(float(param.min_value), float(param.max_value))
                genes.append(value)
            elif isinstance(param, DiscreteParameter):
                # Random integer in range
                n_steps = (param.max_value - param.min_value) // param.step
                step_idx = self._rng.integers(0, n_steps + 1)
                value = float(param.min_value + step_idx * param.step)
                genes.append(value)
            elif isinstance(param, CategoricalParameter):
                # Random choice index
                idx = self._rng.integers(0, len(param.choices))
                genes.append(float(idx))

        return creator.Individual(genes)

    def _initialize_population(self) -> None:
        """Initialize population with random individuals."""
        self._population = self.toolbox.population(n=self.population_size)
        self._current_generation = 0
        self._current_individual_idx = 0
        self._start_time = time.time()

        logger.info(
            "ga_population_initialized",
            population_size=self.population_size,
            n_params=len(self.parameter_space.parameters),
        )

    def _genotype_to_params(self, individual: list[float]) -> dict[str, Any]:
        """Convert genotype (list of floats) to parameter dict.

        Args:
            individual: DEAP individual (list of gene values)

        Returns:
            Parameter dictionary
        """
        params = {}

        for i, param in enumerate(self.parameter_space.parameters):
            gene_value = individual[i]

            if isinstance(param, ContinuousParameter):
                # Clip to bounds and convert to Decimal
                value = max(float(param.min_value), min(float(param.max_value), gene_value))
                params[param.name] = Decimal(str(value))

            elif isinstance(param, DiscreteParameter):
                # Round to nearest valid step
                value = round(gene_value)
                value = max(param.min_value, min(param.max_value, int(value)))
                # Snap to step
                n_steps = (value - param.min_value) // param.step
                value = param.min_value + n_steps * param.step
                params[param.name] = value

            elif isinstance(param, CategoricalParameter):
                # Convert index to choice
                idx = round(gene_value)
                idx = max(0, min(len(param.choices) - 1, int(idx)))
                params[param.name] = param.choices[idx]

        return params

    def _params_to_genotype(self, params: dict[str, Any]) -> list[float]:
        """Convert parameter dict to genotype (list of floats).

        Args:
            params: Parameter dictionary

        Returns:
            List of gene values
        """
        genes = []

        for param in self.parameter_space.parameters:
            value = params[param.name]

            if isinstance(param, (ContinuousParameter, DiscreteParameter)):
                genes.append(float(value))
            elif isinstance(param, CategoricalParameter):
                # Find index of choice
                idx = param.choices.index(value)
                genes.append(float(idx))

        return genes

    def _crossover(self, ind1: Any, ind2: Any) -> tuple[Any, Any]:
        """Blend crossover for two individuals.

        Args:
            ind1: First parent individual
            ind2: Second parent individual

        Returns:
            Tuple of two offspring individuals
        """
        alpha = 0.5  # Blend parameter

        for i in range(len(ind1)):
            # Check if this is a categorical parameter
            param = self.parameter_space.parameters[i]
            is_categorical = isinstance(param, CategoricalParameter)

            if is_categorical:
                # Uniform crossover for categorical
                if self._rng.random() < 0.5:
                    ind1[i], ind2[i] = ind2[i], ind1[i]
            else:
                # Blend crossover for continuous/discrete
                gamma = (1.0 + 2.0 * alpha) * self._rng.random() - alpha
                ind1[i] = (1.0 - gamma) * ind1[i] + gamma * ind2[i]
                ind2[i] = gamma * ind1[i] + (1.0 - gamma) * ind2[i]

                # Clip to parameter bounds
                if isinstance(param, ContinuousParameter):
                    min_val = float(param.min_value)
                    max_val = float(param.max_value)
                    ind1[i] = max(min_val, min(max_val, ind1[i]))
                    ind2[i] = max(min_val, min(max_val, ind2[i]))
                elif isinstance(param, DiscreteParameter):
                    ind1[i] = max(float(param.min_value), min(float(param.max_value), ind1[i]))
                    ind2[i] = max(float(param.min_value), min(float(param.max_value), ind2[i]))

        return ind1, ind2

    def _mutate(self, individual: Any) -> tuple[Any]:
        """Gaussian mutation for individual.

        Args:
            individual: Individual to mutate

        Returns:
            Tuple containing mutated individual
        """
        for i in range(len(individual)):
            param = self.parameter_space.parameters[i]

            if isinstance(param, CategoricalParameter):
                # Uniform mutation for categorical
                if self._rng.random() < self.mutation_prob:
                    individual[i] = float(self._rng.integers(0, len(param.choices)))

            elif isinstance(param, ContinuousParameter):
                # Gaussian mutation for continuous
                if self._rng.random() < self.mutation_prob:
                    min_val = float(param.min_value)
                    max_val = float(param.max_value)
                    sigma = (max_val - min_val) * 0.1  # 10% of range
                    individual[i] += self._rng.normal(0, sigma)
                    # Clip to bounds
                    individual[i] = max(min_val, min(max_val, individual[i]))

            elif isinstance(param, DiscreteParameter):
                # Integer mutation for discrete
                if self._rng.random() < self.mutation_prob:
                    range_size = param.max_value - param.min_value
                    sigma = max(1, range_size * 0.1)  # 10% of range
                    individual[i] += self._rng.normal(0, sigma)
                    # Clip to bounds
                    individual[i] = max(
                        float(param.min_value), min(float(param.max_value), individual[i])
                    )

        return (individual,)

    def suggest(self) -> dict[str, Any]:
        """Suggest next parameter configuration from current generation.

        Returns:
            Dictionary mapping parameter names to values

        Raises:
            ValueError: If optimization is complete
        """
        with self._lock:
            if not self._is_initialized:
                raise ValueError("Algorithm not initialized")

            if self.is_complete():
                raise ValueError(f"Genetic algorithm is complete: {self._termination_reason}")

            # Ensure index is valid (in case population changed)
            if self._current_individual_idx >= len(self._population):
                raise ValueError("Invalid individual index - population may have changed")

            # Get current individual from population
            individual = self._population[self._current_individual_idx]
            params = self._genotype_to_params(individual)

            # Store for update validation
            self._pending_individual = params.copy()

            self.validate_suggested_params(params)
            return params

    def update(self, params: dict[str, Any], score: Decimal) -> None:
        """Update algorithm with evaluation result.

        Args:
            params: Parameter configuration that was evaluated
            score: Objective function score (higher is better)

        Raises:
            ValueError: If params don't match pending individual
        """
        with self._lock:
            # Validate params match pending individual
            if self._pending_individual is None:
                raise ValueError("No pending individual to update")

            if params != self._pending_individual:
                raise ValueError("Updated params don't match suggested params")

            # Update fitness for current individual
            individual = self._population[self._current_individual_idx]
            individual.fitness.values = (float(score),)

            # Update best result
            if self._best_score is None or score > self._best_score:
                self._best_score = score
                self._best_params = params.copy()
                self._last_improvement_generation = self._current_generation
                self._generations_without_improvement = 0

                logger.info(
                    "new_best_ga",
                    generation=self._current_generation,
                    score=str(score),
                )
            else:
                self._generations_without_improvement = (
                    self._current_generation - self._last_improvement_generation
                )

            # Move to next individual
            self._current_individual_idx += 1
            self._pending_individual = None
            self._iteration += 1

            # Check if generation is complete
            if self._current_individual_idx >= self.population_size:
                self._evolve_population()

    def _evolve_population(self) -> None:
        """Evolve population to next generation."""
        # Record generation statistics
        fitnesses = [ind.fitness.values[0] for ind in self._population]
        best_fitness = max(fitnesses)
        avg_fitness = sum(fitnesses) / len(fitnesses)

        self._generation_best_scores.append(Decimal(str(best_fitness)))
        self._generation_avg_scores.append(Decimal(str(avg_fitness)))

        # Calculate and record diversity
        diversity = self._calculate_diversity()
        self._diversity_history.append(diversity)

        # Warn if diversity is low
        if diversity < self.diversity_threshold:
            warnings.warn(
                f"Low diversity detected ({diversity:.6f}) - premature convergence risk",
                UserWarning,
                stacklevel=2,
            )
            logger.warning(
                "low_diversity",
                generation=self._current_generation,
                diversity=diversity,
            )

        logger.info(
            "generation_complete",
            generation=self._current_generation,
            best_fitness=best_fitness,
            avg_fitness=avg_fitness,
            diversity=diversity,
        )

        # Move to next generation BEFORE checking termination
        self._current_generation += 1
        self._current_individual_idx = 0

        # Check if we should continue
        if self._current_generation >= self.max_generations:
            self._termination_reason = "max_generations_reached"
            return

        # Select elites
        elites = tools.selBest(self._population, self.elite_size)

        # Select parents for breeding
        offspring_size = self.population_size - self.elite_size

        # Ensure we have valid population for selection
        if offspring_size > 0 and len(self._population) > 0:
            parents = self.toolbox.select(self._population, offspring_size)

            # Clone parents
            offspring = [self.toolbox.clone(ind) for ind in parents]

            # Apply crossover
            for i in range(1, len(offspring), 2):
                if self._rng.random() < self.crossover_prob and i < len(offspring):
                    offspring[i - 1], offspring[i] = self.toolbox.mate(
                        offspring[i - 1], offspring[i]
                    )
                    del offspring[i - 1].fitness.values
                    del offspring[i].fitness.values

            # Apply mutation
            for mutant in offspring:
                if self._rng.random() < self.mutation_prob:
                    (mutant,) = self.toolbox.mutate(mutant)
                    del mutant.fitness.values

            # Replace population (elites + offspring)
            self._population = elites + offspring
        else:
            # If no offspring, just keep elites
            self._population = elites

        # Ensure population size is consistent
        while len(self._population) < self.population_size:
            # Add random individuals if needed
            self._population.append(self._create_individual())

    def _calculate_diversity(self) -> float:
        """Calculate population diversity.

        Returns:
            Average standard deviation across genes
        """
        if not self._population:
            return 0.0

        # Convert population to numpy array
        genes = np.array([ind[:] for ind in self._population])

        # Calculate std dev for each gene (parameter)
        std_devs = []
        for i, param in enumerate(self.parameter_space.parameters):
            std = np.std(genes[:, i])

            # Normalize by parameter range
            if isinstance(param, (ContinuousParameter, DiscreteParameter)):
                param_range = float(param.max_value - param.min_value)
            elif isinstance(param, CategoricalParameter):
                param_range = float(len(param.choices))
            else:
                param_range = 1.0

            if param_range > 0:
                normalized_std = std / param_range
                std_devs.append(normalized_std)

        return float(np.mean(std_devs)) if std_devs else 0.0

    def is_complete(self) -> bool:
        """Check if optimization should terminate.

        Returns:
            True if any termination criterion is met
        """
        if self._termination_reason is not None:
            return True

        # Check max generations
        if self._current_generation >= self.max_generations:
            self._termination_reason = "max_generations_reached"
            return True

        # Check patience (early stopping)
        if self.patience is not None and self._generations_without_improvement >= self.patience:
            self._termination_reason = f"no_improvement_for_{self.patience}_generations"
            return True

        # Check target fitness
        if (
            self.target_fitness is not None
            and self._best_score is not None
            and self._best_score >= self.target_fitness
        ):
            self._termination_reason = "target_fitness_reached"
            return True

        # Check time limit
        if self.max_time_seconds is not None and self._start_time is not None:
            elapsed = time.time() - self._start_time
            if elapsed >= self.max_time_seconds:
                self._termination_reason = "time_limit_exceeded"
                return True

        return False

    @property
    def current_generation(self) -> int:
        """Get current generation number."""
        return self._current_generation

    @property
    def progress(self) -> float:
        """Get optimization progress as ratio.

        Returns:
            Progress ratio between 0.0 and 1.0
        """
        if self.max_generations == 0:
            return 1.0
        return self._current_generation / self.max_generations

    def get_best_params(self) -> dict[str, Any]:
        """Get parameters with best objective score.

        Returns:
            Best parameter configuration

        Raises:
            ValueError: If no results available
        """
        if self._best_params is None:
            raise ValueError("No results available yet")
        return self._best_params.copy()

    def get_best_result(self) -> tuple[dict[str, Any], Decimal]:
        """Get best result found so far.

        Returns:
            Tuple of (best_params, best_score)

        Raises:
            ValueError: If no results available
        """
        if self._best_params is None or self._best_score is None:
            raise ValueError("No results available yet")
        return self._best_params.copy(), self._best_score

    def get_generation_history(self) -> dict[str, list]:
        """Get generation history for analysis.

        Returns:
            Dictionary containing generation statistics
        """
        return {
            "generation": list(range(len(self._generation_best_scores))),
            "best_fitness": self._generation_best_scores,
            "avg_fitness": self._generation_avg_scores,
            "diversity": self._diversity_history,
        }

    def get_state(self) -> dict[str, Any]:
        """Get serializable algorithm state for checkpointing.

        The returned state dictionary can be saved and later restored using
        set_state(). The population is serialized using pickle.

        SECURITY NOTE: Store checkpoint files securely with appropriate access
        controls. Only load checkpoints from trusted sources you control.
        See set_state() docstring for security warnings.

        Returns:
            Dictionary containing all state needed to resume optimization
        """
        # SECURITY FIX (Story 8.10): Use secure_dumps with HMAC signing
        population_bytes = secure_dumps(self._population)

        return {
            "iteration": self._iteration,
            "population_size": self.population_size,
            "max_generations": self.max_generations,
            "selection_method": self.selection_method,
            "tournament_size": self.tournament_size,
            "crossover_prob": self.crossover_prob,
            "mutation_prob": self.mutation_prob,
            "elite_size": self.elite_size,
            "patience": self.patience,
            "target_fitness": str(self.target_fitness) if self.target_fitness else None,
            "max_time_seconds": self.max_time_seconds,
            "diversity_threshold": self.diversity_threshold,
            "seed": self.seed,
            "rng_state": self._rng.bit_generator.state,
            "population": population_bytes,
            "current_generation": self._current_generation,
            "current_individual_idx": self._current_individual_idx,
            "pending_individual": self._pending_individual,
            "best_params": self._best_params,
            "best_score": str(self._best_score) if self._best_score else None,
            "generations_without_improvement": self._generations_without_improvement,
            "last_improvement_generation": self._last_improvement_generation,
            "generation_best_scores": [str(s) for s in self._generation_best_scores],
            "generation_avg_scores": [str(s) for s in self._generation_avg_scores],
            "diversity_history": self._diversity_history,
            "start_time": self._start_time,
            "termination_reason": self._termination_reason,
        }

    def set_state(self, state: dict[str, Any]) -> None:
        """Restore algorithm state from checkpoint.

        SECURITY WARNING: This method uses pickle.loads() to deserialize the
        population state. Only load checkpoints from trusted sources that you
        control. Never load checkpoint files from untrusted sources, as they
        could contain malicious code that executes during deserialization.

        Safe usage:
            - Checkpoints created by your own optimization runs
            - Files stored in secure, access-controlled locations
            - Files transferred over secure channels with integrity verification

        Unsafe usage:
            - Checkpoint files from unknown or untrusted sources
            - Files downloaded from public repositories without verification
            - Files that could have been tampered with by attackers

        Args:
            state: State dictionary from previous get_state() call.
                   Must be from a trusted source.

        Raises:
            ValueError: If state dictionary is malformed or contains invalid data
            pickle.UnpicklingError: If population data is corrupted
        """
        # Validate state dictionary structure before unpickling
        required_keys = {
            "iteration",
            "population_size",
            "max_generations",
            "selection_method",
            "population",
            "current_generation",
            "best_params",
            "best_score",
        }
        missing_keys = required_keys - set(state.keys())
        if missing_keys:
            raise ValueError(f"Invalid checkpoint state: missing required keys {missing_keys}")

        # Validate critical parameter ranges before unpickling
        if state["population_size"] <= 0 or state["population_size"] > 10000:
            raise ValueError(f"Invalid population_size in checkpoint: {state['population_size']}")
        if state["max_generations"] <= 0 or state["max_generations"] > 100000:
            raise ValueError(f"Invalid max_generations in checkpoint: {state['max_generations']}")
        if state["current_generation"] < 0:
            raise ValueError(
                f"Invalid current_generation in checkpoint: {state['current_generation']}"
            )

        self._iteration = state["iteration"]
        self.population_size = state["population_size"]
        self.max_generations = state["max_generations"]
        self.selection_method = state["selection_method"]
        self.tournament_size = state["tournament_size"]
        self.crossover_prob = state["crossover_prob"]
        self.mutation_prob = state["mutation_prob"]
        self.elite_size = state["elite_size"]
        self.patience = state["patience"]
        self.target_fitness = Decimal(state["target_fitness"]) if state["target_fitness"] else None
        self.max_time_seconds = state["max_time_seconds"]
        self.diversity_threshold = state["diversity_threshold"]
        self.seed = state["seed"]

        # Restore RNG state
        self._rng.bit_generator.state = state["rng_state"]

        # Reinitialize DEAP toolbox (cannot be pickled)
        self._setup_deap()

        # SECURITY FIX (Story 8.10): Use secure_loads with HMAC validation
        try:
            self._population = secure_loads(state["population"])
        except (SecurePickleError, EOFError, AttributeError, ImportError) as e:
            raise ValueError(
                f"Failed to restore population from checkpoint: {e}. "
                "Checkpoint may be corrupted, tampered with, or from incompatible version."
            ) from e

        # Post-unpickle validation: ensure population size matches
        if len(self._population) != self.population_size:
            raise ValueError(
                f"Population size mismatch: expected {self.population_size}, "
                f"got {len(self._population)} in checkpoint"
            )

        # Restore generation state
        self._current_generation = state["current_generation"]
        self._current_individual_idx = state["current_individual_idx"]
        self._pending_individual = state["pending_individual"]

        # Restore best result
        self._best_params = state["best_params"]
        self._best_score = Decimal(state["best_score"]) if state["best_score"] else None

        # Restore improvement tracking
        self._generations_without_improvement = state["generations_without_improvement"]
        self._last_improvement_generation = state["last_improvement_generation"]

        # Restore history
        self._generation_best_scores = [Decimal(s) for s in state["generation_best_scores"]]
        self._generation_avg_scores = [Decimal(s) for s in state["generation_avg_scores"]]
        self._diversity_history = state["diversity_history"]

        # Restore timing
        self._start_time = state["start_time"]
        self._termination_reason = state["termination_reason"]

        self._is_initialized = True
