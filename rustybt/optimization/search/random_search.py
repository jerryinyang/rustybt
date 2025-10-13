"""Random search algorithm implementation."""

import math
import warnings
from collections.abc import Hashable
from decimal import Decimal
from threading import Lock
from typing import Any

import numpy as np
import structlog

from rustybt.optimization.base import SearchAlgorithm
from rustybt.optimization.parameter_space import (
    CategoricalParameter,
    ContinuousParameter,
    DiscreteParameter,
    ParameterSpace,
)

logger = structlog.get_logger()


class RandomSearchAlgorithm(SearchAlgorithm):
    """Random search optimization algorithm.

    Samples parameter combinations randomly from specified distributions.
    More efficient than grid search for high-dimensional spaces (>5 params).

    Recommended for:
        - Initial exploration of parameter space
        - High-dimensional optimization (>5 parameters)
        - Limited computational budget
        - Continuous parameter ranges

    Research (Bergstra & Bengio, 2012):
        "Random search is more efficient than grid search for hyperparameter
        optimization when only a small number of hyperparameters effectively
        influence the final performance."

    Example:
        >>> from rustybt.optimization.parameter_space import (
        ...     ParameterSpace, ContinuousParameter, CategoricalParameter
        ... )
        >>> param_space = ParameterSpace(parameters=[
        ...     ContinuousParameter(name='lookback', min_value=10, max_value=100, prior='uniform'),
        ...     ContinuousParameter(name='threshold', min_value=0.001, max_value=0.1, prior='log-uniform')
        ... ])
        >>> random_search = RandomSearchAlgorithm(
        ...     parameter_space=param_space,
        ...     n_iter=100,
        ...     seed=42
        ... )
        >>> while not random_search.is_complete():
        ...     params = random_search.suggest()
        ...     result = run_backtest(**params)
        ...     random_search.update(params, result['sharpe_ratio'])
        >>> best_params = random_search.get_best_params()

    Args:
        parameter_space: Parameter space defining search domain
        n_iter: Number of random samples to generate
        seed: Random seed for reproducibility (None for random)
        max_retries: Maximum duplicate re-sampling attempts (default: 100)
    """

    def __init__(
        self,
        parameter_space: ParameterSpace,
        n_iter: int,
        seed: int | None = None,
        max_retries: int = 100,
    ):
        """Initialize random search algorithm.

        Args:
            parameter_space: Parameter space to search
            n_iter: Number of random samples to generate
            seed: Random seed for reproducibility (None for random)
            max_retries: Maximum attempts to avoid duplicates (default: 100)

        Raises:
            ValueError: If n_iter <= 0 or max_retries <= 0
        """
        super().__init__(parameter_space)

        if n_iter <= 0:
            raise ValueError("n_iter must be positive")
        if max_retries <= 0:
            raise ValueError("max_retries must be positive")

        self.n_iter = n_iter
        self.seed = seed
        self.max_retries = max_retries

        # Use numpy.random.Generator for better statistical properties
        self._rng = np.random.Generator(np.random.PCG64(seed))

        # Thread safety for parallel execution
        self._lock = Lock()

        # Duplicate prevention - track seen parameter combinations
        self._seen_params: set[tuple] = set()
        self._duplicate_count = 0

        # Best result tracking
        self._best_params: dict[str, Any] | None = None
        self._best_score: Decimal | None = None

        # Result storage
        self._results: list[tuple[dict[str, Any], Decimal]] = []

        self._is_initialized = True

    def suggest(self) -> dict[str, Any]:
        """Suggest next random parameter configuration.

        Returns:
            Dictionary mapping parameter names to random values

        Raises:
            ValueError: If optimization already complete
        """
        with self._lock:
            if not self._is_initialized:
                raise ValueError("Algorithm not initialized")

            if self.is_complete():
                raise ValueError("Random search is complete - reached n_iter samples")

            # Sample parameters with duplicate prevention
            for _retry in range(self.max_retries):
                params = self._sample_parameters()
                params_tuple = self._params_to_hashable(params)

                if params_tuple not in self._seen_params:
                    # New parameter combination
                    self._seen_params.add(params_tuple)
                    return params

                # Duplicate detected
                self._duplicate_count += 1

            # Max retries exceeded - log warning and return last sample
            duplicate_rate = self._duplicate_count / (
                len(self._seen_params) + self._duplicate_count
            )
            warnings.warn(
                f"High duplicate rate ({duplicate_rate:.1%}) after {self.max_retries} retries. "
                f"Allowing duplicate parameter combination. Consider increasing n_iter or "
                f"expanding parameter space.",
                UserWarning,
                stacklevel=2,
            )
            logger.warning(
                "duplicate_prevention_failed",
                duplicate_rate=duplicate_rate,
                max_retries=self.max_retries,
            )

            # Return last sample even if duplicate
            return params

    def _sample_parameters(self) -> dict[str, Any]:
        """Sample random parameter values from distributions.

        Returns:
            Dictionary of sampled parameters
        """
        params = {}

        for param in self.parameter_space.parameters:
            if isinstance(param, ContinuousParameter):
                params[param.name] = self._sample_continuous(param)
            elif isinstance(param, DiscreteParameter):
                params[param.name] = self._sample_discrete(param)
            elif isinstance(param, CategoricalParameter):
                params[param.name] = self._sample_categorical(param)

        self.validate_suggested_params(params)
        return params

    def _sample_continuous(self, param: ContinuousParameter) -> Decimal:
        """Sample from continuous parameter distribution.

        Args:
            param: Continuous parameter specification

        Returns:
            Sampled value as Decimal

        Raises:
            ValueError: If prior distribution is unsupported
        """
        min_val = float(param.min_value)
        max_val = float(param.max_value)

        if param.prior == "uniform":
            # Uniform distribution
            value = self._rng.uniform(min_val, max_val)

        elif param.prior == "log-uniform":
            # Log-uniform distribution (good for scale-variant parameters)
            if min_val <= 0:
                raise ValueError(f"log-uniform prior requires positive bounds, got min={min_val}")
            log_min = math.log(min_val)
            log_max = math.log(max_val)
            log_value = self._rng.uniform(log_min, log_max)
            value = math.exp(log_value)

        elif param.prior == "normal":
            # Normal distribution (clipped to bounds)
            mean = (min_val + max_val) / 2
            std = (max_val - min_val) / 4  # ~95% of samples within bounds
            value = self._rng.normal(mean, std)
            # Clip to bounds
            value = max(min_val, min(max_val, value))

        else:
            raise ValueError(f"Unsupported prior distribution: {param.prior}")

        return Decimal(str(value))

    def _sample_discrete(self, param: DiscreteParameter) -> int:
        """Sample from discrete parameter range.

        Args:
            param: Discrete parameter specification

        Returns:
            Sampled integer value
        """
        # Sample uniformly from discrete range
        n_steps = (param.max_value - param.min_value) // param.step
        step_idx = self._rng.integers(0, n_steps + 1)
        # Convert to Python int (numpy returns np.int64)
        return int(param.min_value + step_idx * param.step)

    def _sample_categorical(self, param: CategoricalParameter) -> Any:
        """Sample from categorical parameter choices.

        Args:
            param: Categorical parameter specification

        Returns:
            Randomly selected choice
        """
        # Sample uniformly from choices
        idx = self._rng.integers(0, len(param.choices))
        return param.choices[idx]

    def _params_to_hashable(self, params: dict[str, Any]) -> tuple:
        """Convert parameter dictionary to hashable tuple.

        Args:
            params: Parameter dictionary

        Returns:
            Hashable tuple representation for duplicate checking
        """
        # Sort items for consistent hashing
        items = []
        for key in sorted(params.keys()):
            value = params[key]
            # Convert Decimal to string for hashing
            if isinstance(value, Decimal):
                items.append((key, str(value)))
            elif isinstance(value, Hashable):
                items.append((key, value))
            else:
                # For non-hashable types, convert to string
                items.append((key, str(value)))

        return tuple(items)

    def update(self, params: dict[str, Any], score: Decimal) -> None:
        """Update algorithm with evaluation result.

        Args:
            params: Parameter configuration that was evaluated
            score: Objective function score (higher is better)

        Raises:
            ValueError: If params are invalid
        """
        with self._lock:
            # Validate params
            self.validate_suggested_params(params)

            # Store result
            self._results.append((params, score))
            self._iteration += 1

            # Update best result
            if self._best_score is None or score > self._best_score:
                self._best_score = score
                self._best_params = params.copy()
                logger.info(
                    "new_best_random_search",
                    iteration=self._iteration,
                    score=str(score),
                )

    def is_complete(self) -> bool:
        """Check if optimization should terminate.

        Returns:
            True if completed n_iter iterations
        """
        return self._iteration >= self.n_iter

    @property
    def progress(self) -> float:
        """Get optimization progress as ratio.

        Returns:
            Progress ratio between 0.0 and 1.0
        """
        if self.n_iter == 0:
            return 1.0
        return self._iteration / self.n_iter

    @property
    def duplicate_rate(self) -> float:
        """Get duplicate detection rate.

        Returns:
            Ratio of duplicate samples detected
        """
        total_attempts = len(self._seen_params) + self._duplicate_count
        if total_attempts == 0:
            return 0.0
        return self._duplicate_count / total_attempts

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

    def get_results(self, top_k: int | None = None) -> list[tuple[dict[str, Any], Decimal]]:
        """Get optimization results sorted by score.

        Args:
            top_k: Return only top K results (None returns all)

        Returns:
            List of (params, score) tuples sorted by score descending

        Raises:
            ValueError: If no results available
        """
        if not self._results:
            raise ValueError("No results available yet")

        # Sort by score descending (best first)
        sorted_results = sorted(self._results, key=lambda x: x[1], reverse=True)

        if top_k is not None:
            return sorted_results[:top_k]

        return sorted_results

    def get_state(self) -> dict[str, Any]:
        """Get serializable algorithm state for checkpointing.

        Returns:
            Dictionary containing all state needed to resume optimization
        """
        # Get numpy RNG state (bit_generator state)
        rng_state = self._rng.bit_generator.state

        return {
            "iteration": self._iteration,
            "n_iter": self.n_iter,
            "seed": self.seed,
            "max_retries": self.max_retries,
            "rng_state": rng_state,
            "seen_params": list(self._seen_params),
            "duplicate_count": self._duplicate_count,
            "best_params": self._best_params,
            "best_score": str(self._best_score) if self._best_score is not None else None,
            "results": [(params, str(score)) for params, score in self._results],
        }

    def set_state(self, state: dict[str, Any]) -> None:
        """Restore algorithm state from checkpoint.

        Args:
            state: State dictionary from previous get_state() call
        """
        self._iteration = state["iteration"]
        self.n_iter = state["n_iter"]
        self.seed = state["seed"]
        self.max_retries = state["max_retries"]

        # Restore numpy RNG state
        self._rng.bit_generator.state = state["rng_state"]

        # Restore duplicate tracking
        self._seen_params = set(state["seen_params"])
        self._duplicate_count = state["duplicate_count"]

        # Restore best result
        self._best_params = state["best_params"]
        self._best_score = Decimal(state["best_score"]) if state["best_score"] is not None else None

        # Restore results
        self._results = [(params, Decimal(score)) for params, score in state["results"]]

        self._is_initialized = True
