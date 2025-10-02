"""Base classes for optimization framework."""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any

from rustybt.optimization.parameter_space import ParameterSpace


class SearchAlgorithm(ABC):
    """Abstract base class for parameter search algorithms."""

    def __init__(self, parameter_space: ParameterSpace, **kwargs):
        """Initialize search algorithm with parameter space.

        Args:
            parameter_space: Parameter space to search
            **kwargs: Algorithm-specific configuration
        """
        self.parameter_space = parameter_space
        self._iteration = 0
        self._is_initialized = False

    @abstractmethod
    def suggest(self) -> dict[str, Any]:
        """Suggest next parameter configuration to evaluate.

        Returns:
            Dictionary mapping parameter names to values

        Raises:
            ValueError: If algorithm not initialized or optimization complete
        """
        pass

    @abstractmethod
    def update(self, params: dict[str, Any], score: Decimal) -> None:
        """Update algorithm with evaluation result.

        Args:
            params: Parameter configuration that was evaluated
            score: Objective function score (higher is better)

        Raises:
            ValueError: If params don't match suggested parameters
        """
        pass

    @abstractmethod
    def is_complete(self) -> bool:
        """Check if optimization should terminate.

        Returns:
            True if optimization is complete, False otherwise
        """
        pass

    @abstractmethod
    def get_state(self) -> dict[str, Any]:
        """Get serializable algorithm state for checkpointing.

        Returns:
            Dictionary containing all state needed to resume optimization
        """
        pass

    @abstractmethod
    def set_state(self, state: dict[str, Any]) -> None:
        """Restore algorithm state from checkpoint.

        Args:
            state: State dictionary from previous get_state() call
        """
        pass

    @property
    def iteration(self) -> int:
        """Get current iteration number."""
        return self._iteration

    def validate_suggested_params(self, params: dict[str, Any]) -> None:
        """Validate suggested parameters against parameter space.

        Args:
            params: Parameters to validate

        Raises:
            ValueError: If parameters are invalid
        """
        self.parameter_space.validate_params(params)
