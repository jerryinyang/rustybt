"""Grid search optimization algorithm."""

from decimal import Decimal
from itertools import product
from threading import Lock
from typing import Any

from rustybt.optimization.base import SearchAlgorithm
from rustybt.optimization.parameter_space import (
    CategoricalParameter,
    ContinuousParameter,
    DiscreteParameter,
    ParameterSpace,
)


class GridSearchAlgorithm(SearchAlgorithm):
    """Exhaustive grid search optimization algorithm.

    Systematically evaluates all combinations in a parameter grid.
    Best for small parameter spaces (<100 combinations).

    Warning:
        Grid size grows exponentially: O(n^k) where k is parameter count.
        Not recommended for >5 parameters or >1000 total combinations.
        Consider RandomSearch or BayesianOptimizer for large spaces.

    Example:
        >>> from rustybt.optimization.parameter_space import (
        ...     ParameterSpace, DiscreteParameter, CategoricalParameter
        ... )
        >>> param_space = ParameterSpace(parameters=[
        ...     DiscreteParameter(name='lookback', min_value=10, max_value=30, step=10),
        ...     CategoricalParameter(name='threshold', choices=[0.01, 0.02])
        ... ])
        >>> grid = GridSearchAlgorithm(
        ...     parameter_space=param_space,
        ...     early_stopping_rounds=None
        ... )
        >>> while not grid.is_complete():
        ...     params = grid.suggest()
        ...     result = run_backtest(**params)
        ...     grid.update(params, result['sharpe_ratio'])
        >>> best_params = grid.get_best_params()

    Args:
        parameter_space: Parameter space defining the grid
        early_stopping_rounds: Stop if no improvement in last N rounds (None disables)
    """

    def __init__(
        self,
        parameter_space: ParameterSpace,
        early_stopping_rounds: int | None = None,
    ):
        """Initialize grid search algorithm.

        Args:
            parameter_space: Parameter space to search
            early_stopping_rounds: Stop if no improvement in last N rounds (None disables)
        """
        super().__init__(parameter_space)

        # Validate parameter space is suitable for grid search
        self._validate_parameter_space()

        # Generate all parameter combinations
        self._combinations = self._generate_grid()
        self._total_combinations = len(self._combinations)
        self._current_index = 0

        # Thread safety for parallel execution
        self._lock = Lock()

        # Progress tracking
        self._completed_count = 0

        # Early stopping
        self.early_stopping_rounds = early_stopping_rounds
        self._best_score: Decimal | None = None
        self._rounds_without_improvement = 0

        # Result storage
        self._results: list[tuple[dict[str, Any], Decimal]] = []

        self._is_initialized = True

    def _validate_parameter_space(self) -> None:
        """Validate parameter space is suitable for grid search.

        Raises:
            ValueError: If parameter space contains continuous parameters or is too large
        """
        # Check for continuous parameters
        for param in self.parameter_space.parameters:
            if isinstance(param, ContinuousParameter):
                raise ValueError(
                    f"GridSearch does not support continuous parameters. "
                    f"Parameter '{param.name}' is continuous. "
                    f"Use DiscreteParameter with appropriate step instead."
                )

        # Warn about large grid sizes
        cardinality = self.parameter_space.cardinality()
        if cardinality > 1000:
            import warnings

            warnings.warn(
                f"Grid search will evaluate {cardinality} combinations. "
                f"This may take a very long time. Consider using RandomSearch "
                f"or BayesianOptimizer for large parameter spaces.",
                UserWarning,
                stacklevel=2,
            )

    def _generate_grid(self) -> list[dict[str, Any]]:
        """Generate all parameter combinations via Cartesian product.

        Returns:
            List of parameter dictionaries representing all grid cells

        Raises:
            ValueError: If parameter space is empty or invalid
        """
        if not self.parameter_space.parameters:
            raise ValueError("Parameter space is empty")

        # Build list of (param_name, values_list) tuples
        param_values = []
        param_names = []

        for param in self.parameter_space.parameters:
            param_names.append(param.name)

            if isinstance(param, DiscreteParameter):
                # Generate discrete values: [min, min+step, min+2*step, ..., max]
                values = list(range(param.min_value, param.max_value + 1, param.step))
            elif isinstance(param, CategoricalParameter):
                # Use choices directly
                values = param.choices
            else:
                # Should be caught by _validate_parameter_space, but defensive check
                raise ValueError(f"Unsupported parameter type: {type(param).__name__}")

            param_values.append(values)

        # Generate Cartesian product of all parameter values
        combinations = []
        for combo in product(*param_values):
            param_dict = dict(zip(param_names, combo, strict=True))
            combinations.append(param_dict)

        return combinations

    def suggest(self) -> dict[str, Any]:
        """Suggest next parameter configuration to evaluate.

        Returns:
            Dictionary mapping parameter names to values

        Raises:
            ValueError: If optimization is complete
        """
        with self._lock:
            if not self._is_initialized:
                raise ValueError("Algorithm not initialized")

            if self.is_complete():
                raise ValueError("Grid search is complete - no more combinations to evaluate")

            # Get next combination
            params = self._combinations[self._current_index]
            self._current_index += 1

            return params

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
            self._completed_count += 1
            self._iteration += 1

            # Update best score and check for improvement
            if self._best_score is None or score > self._best_score:
                self._best_score = score
                self._rounds_without_improvement = 0
            else:
                self._rounds_without_improvement += 1

    def is_complete(self) -> bool:
        """Check if optimization should terminate.

        Returns:
            True if all combinations tested or early stopping triggered
        """
        # All combinations exhausted
        if self._current_index >= self._total_combinations:
            return True

        # Early stopping check
        return (
            self.early_stopping_rounds is not None
            and self._rounds_without_improvement >= self.early_stopping_rounds
        )

    @property
    def progress(self) -> float:
        """Get optimization progress as ratio.

        Returns:
            Progress ratio between 0.0 and 1.0
        """
        if self._total_combinations == 0:
            return 1.0
        return self._completed_count / self._total_combinations

    @property
    def total_combinations(self) -> int:
        """Get total number of combinations in grid.

        Returns:
            Total grid size
        """
        return self._total_combinations

    def get_best_params(self) -> dict[str, Any]:
        """Get parameters with best objective score.

        Returns:
            Best parameter configuration

        Raises:
            ValueError: If no results available
        """
        if not self._results:
            raise ValueError("No results available yet")

        best_params, _ = max(self._results, key=lambda x: x[1])
        return best_params.copy()

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
        return {
            "iteration": self._iteration,
            "current_index": self._current_index,
            "completed_count": self._completed_count,
            "best_score": str(self._best_score) if self._best_score is not None else None,
            "rounds_without_improvement": self._rounds_without_improvement,
            "results": [(params, str(score)) for params, score in self._results],
        }

    def set_state(self, state: dict[str, Any]) -> None:
        """Restore algorithm state from checkpoint.

        Args:
            state: State dictionary from previous get_state() call
        """
        self._iteration = state["iteration"]
        self._current_index = state["current_index"]
        self._completed_count = state["completed_count"]
        self._best_score = Decimal(state["best_score"]) if state["best_score"] is not None else None
        self._rounds_without_improvement = state["rounds_without_improvement"]
        self._results = [(params, Decimal(score)) for params, score in state["results"]]
