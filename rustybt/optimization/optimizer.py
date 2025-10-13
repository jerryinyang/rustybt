"""Main optimizer orchestrator."""

import json
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import structlog

from rustybt.optimization.base import SearchAlgorithm
from rustybt.optimization.objective import ObjectiveFunction
from rustybt.optimization.parameter_space import ParameterSpace
from rustybt.optimization.result import OptimizationResult

logger = structlog.get_logger()


class Optimizer:
    """Main optimizer orchestrator coordinating search and execution."""

    def __init__(
        self,
        parameter_space: ParameterSpace,
        search_algorithm: SearchAlgorithm,
        objective_function: ObjectiveFunction,
        backtest_function: Callable[[dict[str, Any]], dict[str, Any]],
        max_trials: int,
        checkpoint_dir: Path | None = None,
        checkpoint_frequency: int = 10,
    ):
        """Initialize optimizer.

        Args:
            parameter_space: Parameter search space
            search_algorithm: Algorithm to use for parameter search
            objective_function: Metric extraction from backtest results
            backtest_function: Function that runs backtest given parameters
            max_trials: Maximum number of trials to run
            checkpoint_dir: Directory for checkpoint files (None disables checkpointing)
            checkpoint_frequency: Save checkpoint every N trials

        Raises:
            ValueError: If configuration is invalid
        """
        self.parameter_space = parameter_space
        self.search_algorithm = search_algorithm
        self.objective_function = objective_function
        self.backtest_function = backtest_function
        self.max_trials = max_trials
        self.checkpoint_dir = Path(checkpoint_dir) if checkpoint_dir else None
        self.checkpoint_frequency = checkpoint_frequency

        self.results: list[OptimizationResult] = []
        self.best_result: OptimizationResult | None = None
        self.current_trial = 0

        # Validation
        if max_trials <= 0:
            raise ValueError("max_trials must be positive")
        if checkpoint_frequency <= 0:
            raise ValueError("checkpoint_frequency must be positive")

        # Create checkpoint directory if needed
        if self.checkpoint_dir:
            self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def optimize(self) -> OptimizationResult:
        """Run optimization loop.

        Returns:
            Best optimization result found

        Raises:
            ValueError: If optimization fails completely
        """
        logger.info(
            "optimization_started",
            max_trials=self.max_trials,
            algorithm=self.search_algorithm.__class__.__name__,
        )

        try:
            while not self._should_stop():
                # Ask search algorithm for next parameters
                params = self.search_algorithm.suggest()

                # Validate parameters
                self.parameter_space.validate_params(params)

                # Run backtest with parameters
                result = self._evaluate_params(params)

                # Tell search algorithm the result
                self.search_algorithm.update(params, result.score)

                # Store result
                self.results.append(result)
                self.current_trial += 1

                # Update best result (only if successful)
                if result.is_success:
                    if self.best_result is None or result.score > self.best_result.score:
                        self.best_result = result
                        logger.info(
                            "new_best_result",
                            trial=self.current_trial,
                            score=str(result.score),
                            params=result.params,
                        )

                # Checkpoint if needed
                if self._should_checkpoint():
                    self._save_checkpoint()

            # Final validation
            if self.best_result is None:
                raise ValueError("Optimization completed but no successful trials found")

            logger.info(
                "optimization_completed",
                total_trials=self.current_trial,
                best_score=str(self.best_result.score),
                best_params=self.best_result.params,
            )

            return self.best_result

        except Exception as e:
            logger.error("optimization_failed", error=str(e))
            if self.checkpoint_dir:
                self._save_checkpoint()  # Save progress before failing
            raise

    def _should_stop(self) -> bool:
        """Check if optimization should terminate.

        Returns:
            True if should stop
        """
        if self.current_trial >= self.max_trials:
            return True
        return bool(self.search_algorithm.is_complete())

    def _should_checkpoint(self) -> bool:
        """Check if checkpoint should be saved.

        Returns:
            True if should checkpoint
        """
        if not self.checkpoint_dir:
            return False
        return self.current_trial % self.checkpoint_frequency == 0

    def _evaluate_params(self, params: dict[str, Any]) -> OptimizationResult:
        """Evaluate single parameter configuration.

        Args:
            params: Parameters to evaluate

        Returns:
            OptimizationResult with score or error
        """
        start_time = datetime.now()
        trial_id = self.current_trial

        try:
            # Run backtest
            backtest_result = self.backtest_function(params)

            # Extract objective metric
            score = self.objective_function.evaluate(backtest_result)

            duration = Decimal(str((datetime.now() - start_time).total_seconds()))

            result = OptimizationResult(
                trial_id=trial_id,
                params=params,
                score=score,
                timestamp=start_time,
                backtest_metrics=backtest_result.get("performance_metrics", {}),
                duration_seconds=duration,
            )

            logger.info(
                "trial_completed",
                trial_id=trial_id,
                score=str(score),
                duration_seconds=str(duration),
            )

            return result

        except Exception as e:
            logger.error("trial_failed", trial_id=trial_id, error=str(e), params=params)

            # Return failed result
            duration = Decimal(str((datetime.now() - start_time).total_seconds()))
            return OptimizationResult(
                trial_id=trial_id,
                params=params,
                score=Decimal("-Infinity"),
                timestamp=start_time,
                backtest_metrics={},
                error=str(e),
                duration_seconds=duration,
            )

    def _save_checkpoint(self) -> None:
        """Save optimization state to checkpoint file."""
        if not self.checkpoint_dir:
            return

        checkpoint_file = self.checkpoint_dir / f"checkpoint_trial_{self.current_trial}.json"

        # Convert algorithm state to JSON-serializable format
        algorithm_state = self._serialize_algorithm_state(self.search_algorithm.get_state())

        state = {
            "current_trial": self.current_trial,
            "results": [r.to_dict() for r in self.results],
            "best_result": self.best_result.to_dict() if self.best_result else None,
            "algorithm_state": algorithm_state,
            "timestamp": datetime.now().isoformat(),
        }

        with open(checkpoint_file, "w") as f:
            json.dump(state, f, indent=2)

        logger.info("checkpoint_saved", file=str(checkpoint_file), trial=self.current_trial)

    def _serialize_algorithm_state(self, state: dict[str, Any]) -> dict[str, Any]:
        """Convert algorithm state to JSON-serializable format.

        Args:
            state: Algorithm state dictionary

        Returns:
            JSON-serializable state dictionary
        """

        def convert_value(value):
            """Recursively convert Decimal to string."""
            if isinstance(value, Decimal):
                return str(value)
            elif isinstance(value, dict):
                return {k: convert_value(v) for k, v in value.items()}
            elif isinstance(value, (list, tuple)):
                return [convert_value(item) for item in value]
            else:
                return value

        import copy

        serialized = copy.deepcopy(state)

        # Recursively convert all Decimal values
        return convert_value(serialized)

    def _deserialize_algorithm_state(self, state: dict[str, Any]) -> dict[str, Any]:
        """Convert JSON-serialized state back to proper types.

        Args:
            state: JSON-deserialized state dictionary

        Returns:
            State dictionary with proper types
        """

        def convert_value(value):
            """Recursively convert numeric strings to Decimal where appropriate."""
            if isinstance(value, str):
                # Try to convert to Decimal if it looks like a number
                try:
                    # Check if it's a number by trying to parse it
                    if "." in value or "e" in value.lower():
                        return Decimal(value)
                except (ValueError, TypeError):
                    pass
                return value
            elif isinstance(value, dict):
                return {k: convert_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [convert_value(item) for item in value]
            else:
                return value

        import copy

        deserialized = copy.deepcopy(state)

        # Recursively convert numeric strings back to Decimal
        return convert_value(deserialized)

    def load_checkpoint(self, checkpoint_file: Path) -> None:
        """Load optimization state from checkpoint file.

        Args:
            checkpoint_file: Path to checkpoint file

        Raises:
            FileNotFoundError: If checkpoint file doesn't exist
            ValueError: If checkpoint is invalid
        """
        with open(checkpoint_file) as f:
            state = json.load(f)

        self.current_trial = state["current_trial"]
        self.results = [OptimizationResult.from_dict(r) for r in state["results"]]
        self.best_result = (
            OptimizationResult.from_dict(state["best_result"]) if state["best_result"] else None
        )

        # Deserialize algorithm state
        algorithm_state = self._deserialize_algorithm_state(state["algorithm_state"])
        self.search_algorithm.set_state(algorithm_state)

        logger.info(
            "checkpoint_loaded",
            file=str(checkpoint_file),
            resumed_at_trial=self.current_trial,
        )

    def get_history(self) -> list[OptimizationResult]:
        """Get complete optimization history.

        Returns:
            List of all optimization results
        """
        return self.results.copy()

    def get_best_params(self) -> dict[str, Any]:
        """Get best parameters found.

        Returns:
            Best parameter configuration

        Raises:
            ValueError: If no results available yet
        """
        if not self.best_result:
            raise ValueError("No successful results available yet")
        return self.best_result.params.copy()
