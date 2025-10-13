"""Bayesian optimization using Gaussian Process surrogate models."""

# SECURITY FIX (Story 8.10): Use secure pickle with HMAC validation
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Union

import numpy as np
import structlog
from skopt import Optimizer
from skopt.space import Categorical, Integer, Real

from rustybt.utils.secure_pickle import SecurePickleError, secure_dumps, secure_loads

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure

from rustybt.optimization.base import SearchAlgorithm
from rustybt.optimization.parameter_space import (
    CategoricalParameter,
    ContinuousParameter,
    DiscreteParameter,
    ParameterSpace,
)

logger = structlog.get_logger(__name__)


class BayesianOptimizer(SearchAlgorithm):
    """Bayesian optimization using Gaussian Process surrogate models.

    Uses a Gaussian Process to model the objective function and an acquisition
    function to balance exploration (uncertain regions) and exploitation
    (promising regions). More sample-efficient than grid/random search.

    Best for:
        - Expensive objective functions (minutes per evaluation)
        - Moderate parameter count (2-20 parameters)
        - Sequential optimization (not massively parallel)
        - Continuous parameter spaces

    Args:
        parameter_space: Parameter space to search
        n_iter: Maximum number of iterations
        acq_func: Acquisition function ('EI', 'PI', 'LCB')
        kappa: UCB exploration parameter (default: 1.96)
        xi: EI/PI exploration parameter (default: 0.01)
        initial_points: Prior knowledge - list of dicts with known good params
        initial_scores: Scores corresponding to initial_points
        convergence_threshold: Min improvement to continue (default: 1e-4)
        convergence_patience: Iterations without improvement to stop (default: 10)
        random_state: Random seed for reproducibility

    Example:
        >>> from rustybt.optimization.parameter_space import (
        ...     ParameterSpace, ContinuousParameter, CategoricalParameter
        ... )
        >>> space = ParameterSpace(parameters=[
        ...     ContinuousParameter(name='lookback', min_value=10, max_value=100),
        ...     ContinuousParameter(name='threshold', min_value=0.01, max_value=0.1,
        ...                        prior='log-uniform'),
        ...     CategoricalParameter(name='ma_type', choices=['ema', 'sma'])
        ... ])
        >>> optimizer = BayesianOptimizer(
        ...     parameter_space=space,
        ...     n_iter=50,
        ...     acq_func='EI',
        ...     initial_points=[{'lookback': 20, 'threshold': 0.02, 'ma_type': 'ema'}],
        ...     initial_scores=[Decimal('1.5')]
        ... )
        >>> while not optimizer.is_complete():
        ...     params = optimizer.suggest()
        ...     result = run_backtest(**params)
        ...     optimizer.update(params, result['sharpe_ratio'])
        >>> best_params = optimizer.get_best_params()
    """

    def __init__(
        self,
        parameter_space: ParameterSpace,
        n_iter: int = 50,
        acq_func: Literal["EI", "PI", "LCB"] = "EI",
        kappa: float = 1.96,
        xi: float = 0.01,
        initial_points: list[dict[str, Any]] | None = None,
        initial_scores: list[Decimal] | None = None,
        convergence_threshold: float = 1e-4,
        convergence_patience: int = 10,
        random_state: int | None = None,
    ):
        """Initialize Bayesian optimizer."""
        super().__init__(parameter_space)

        if n_iter <= 0:
            raise ValueError("n_iter must be positive")

        if initial_points and initial_scores and len(initial_points) != len(initial_scores):
            raise ValueError("initial_points and initial_scores must have same length")

        self.n_iter = n_iter
        self.acq_func = acq_func
        self.kappa = kappa
        self.xi = xi
        self.convergence_threshold = convergence_threshold
        self.convergence_patience = convergence_patience
        self.random_state = random_state

        # Convert parameter space to skopt Space
        self._space = self._convert_to_skopt_space()
        self._param_names = [p.name for p in parameter_space.parameters]

        # Initialize skopt Optimizer
        self._optimizer = Optimizer(
            dimensions=self._space,
            base_estimator="GP",
            acq_func=acq_func,
            acq_optimizer="auto",
            acq_func_kwargs={"kappa": kappa, "xi": xi},
            random_state=random_state,
        )

        # Track optimization state
        self._current_suggestion: dict[str, Any] | None = None
        self._evaluations: list[tuple[dict[str, Any], Decimal]] = []
        self._best_score: Decimal | None = None
        self._best_params: dict[str, Any] | None = None
        self._converged = False
        self._acq_values: list[float] = []

        # Seed with prior knowledge if provided
        if initial_points and initial_scores:
            for params, score in zip(initial_points, initial_scores, strict=True):
                x = self._params_to_list(params)
                y = -float(score)  # Negative for minimization
                self._optimizer.tell(x, y)
                self._evaluations.append((params, score))

                # Update best
                if self._best_score is None or score > self._best_score:
                    self._best_score = score
                    self._best_params = params

        logger.info(
            "bayesian_optimizer_initialized",
            n_iter=n_iter,
            acq_func=acq_func,
            n_params=len(parameter_space.parameters),
            initial_points_count=len(initial_points) if initial_points else 0,
        )

    def _convert_to_skopt_space(self) -> list[Real | Integer | Categorical]:
        """Convert ParameterSpace to skopt Space format."""
        space = []

        for param in self.parameter_space.parameters:
            if isinstance(param, ContinuousParameter):
                prior = "log-uniform" if param.prior == "log-uniform" else "uniform"
                space.append(
                    Real(
                        float(param.min_value),
                        float(param.max_value),
                        prior=prior,
                        name=param.name,
                    )
                )
            elif isinstance(param, DiscreteParameter):
                space.append(
                    Integer(
                        param.min_value,
                        param.max_value,
                        name=param.name,
                    )
                )
            elif isinstance(param, CategoricalParameter):
                space.append(
                    Categorical(
                        param.choices,
                        name=param.name,
                    )
                )
            else:
                raise ValueError(f"Unsupported parameter type: {type(param)}")

        return space

    def _params_to_list(self, params: dict[str, Any]) -> list[Any]:
        """Convert parameter dict to ordered list for skopt."""
        return [params[name] for name in self._param_names]

    def _list_to_params(self, values: list[Any]) -> dict[str, Any]:
        """Convert ordered list from skopt to parameter dict."""
        return dict(zip(self._param_names, values, strict=True))

    def suggest(self) -> dict[str, Any]:
        """Suggest next parameter configuration to evaluate.

        Returns:
            Dictionary mapping parameter names to values

        Raises:
            ValueError: If optimization is complete
        """
        if self.is_complete():
            raise ValueError("Optimization is complete")

        # Get next point from acquisition function
        x_next = self._optimizer.ask()
        params = self._list_to_params(x_next)

        # Round discrete parameters to match step constraints
        # skopt's Integer doesn't understand step, so we need to fix it
        for param_def in self.parameter_space.parameters:
            if isinstance(param_def, DiscreteParameter):
                value = params[param_def.name]
                # Round to nearest valid step
                min_val = param_def.min_value
                step = param_def.step
                rounded = int(round((value - min_val) / step) * step + min_val)
                # Ensure within bounds
                rounded = max(param_def.min_value, min(param_def.max_value, rounded))
                params[param_def.name] = rounded

        # Validate against parameter space
        self.validate_suggested_params(params)

        self._current_suggestion = params
        self._iteration += 1

        logger.debug(
            "suggested_params",
            iteration=self._iteration,
            params=params,
        )

        return params

    def update(self, params: dict[str, Any], score: Decimal) -> None:
        """Update algorithm with evaluation result.

        Args:
            params: Parameter configuration that was evaluated
            score: Objective function score (higher is better)

        Raises:
            ValueError: If params don't match current suggestion
        """
        if self._current_suggestion is None:
            raise ValueError("No suggestion pending - call suggest() first")

        if params != self._current_suggestion:
            raise ValueError(
                f"Update params {params} don't match suggestion {self._current_suggestion}"
            )

        # Store evaluation
        self._evaluations.append((params, score))

        # Update best
        if self._best_score is None or score > self._best_score:
            self._best_score = score
            self._best_params = params
            logger.info(
                "new_best_found",
                iteration=self._iteration,
                score=str(score),
                params=params,
            )

        # Tell optimizer (negate score for minimization)
        x = self._params_to_list(params)
        y = -float(score)
        result = self._optimizer.tell(x, y)

        # Track acquisition function value for convergence detection
        if hasattr(result, "func_vals") and len(result.func_vals) > 0:
            # Current best (minimum) in optimization
            current_best = float(np.min(result.func_vals))
            self._acq_values.append(current_best)

            # Check for convergence
            if len(self._acq_values) > self.convergence_patience:
                recent_values = self._acq_values[-self.convergence_patience :]
                improvement = np.max(recent_values) - recent_values[-1]

                if improvement < self.convergence_threshold:
                    self._converged = True
                    logger.info(
                        "optimization_converged",
                        iteration=self._iteration,
                        improvement=improvement,
                        threshold=self.convergence_threshold,
                    )

        self._current_suggestion = None

        logger.debug(
            "updated_optimizer",
            iteration=self._iteration,
            score=str(score),
            best_score=str(self._best_score),
        )

    def is_complete(self) -> bool:
        """Check if optimization should terminate.

        Returns:
            True if max iterations reached or converged, False otherwise
        """
        return self._iteration >= self.n_iter or self._converged

    def get_best_params(self) -> dict[str, Any] | None:
        """Get best parameters found so far."""
        return self._best_params

    def get_best_score(self) -> Decimal | None:
        """Get best score found so far."""
        return self._best_score

    def get_state(self) -> dict[str, Any]:
        """Get serializable algorithm state for checkpointing.

        Returns:
            Dictionary containing all state needed to resume optimization
        """
        # SECURITY FIX (Story 8.10): Use secure_dumps with HMAC signing
        optimizer_bytes = secure_dumps(self._optimizer)

        return {
            "n_iter": self.n_iter,
            "acq_func": self.acq_func,
            "kappa": self.kappa,
            "xi": self.xi,
            "convergence_threshold": self.convergence_threshold,
            "convergence_patience": self.convergence_patience,
            "random_state": self.random_state,
            "iteration": self._iteration,
            "current_suggestion": self._current_suggestion,
            "evaluations": [(params, str(score)) for params, score in self._evaluations],
            "best_score": str(self._best_score) if self._best_score else None,
            "best_params": self._best_params,
            "converged": self._converged,
            "acq_values": self._acq_values,
            "optimizer_pickle": optimizer_bytes,
            "param_names": self._param_names,
        }

    def set_state(self, state: dict[str, Any]) -> None:
        """Restore algorithm state from checkpoint.

        Args:
            state: State dictionary from previous get_state() call

        Raises:
            SecurePickleError: If HMAC signature validation fails (tampered data)

        Security:
            This method uses secure_loads() with HMAC signature validation
            to protect against malicious pickle payloads.
        """
        self.n_iter = state["n_iter"]
        self.acq_func = state["acq_func"]
        self.kappa = state["kappa"]
        self.xi = state["xi"]
        self.convergence_threshold = state["convergence_threshold"]
        self.convergence_patience = state["convergence_patience"]
        self.random_state = state["random_state"]
        self._iteration = state["iteration"]
        self._current_suggestion = state["current_suggestion"]
        self._evaluations = [(params, Decimal(score)) for params, score in state["evaluations"]]
        self._best_score = Decimal(state["best_score"]) if state["best_score"] else None
        self._best_params = state["best_params"]
        self._converged = state["converged"]
        self._acq_values = state["acq_values"]
        self._param_names = state["param_names"]

        # SECURITY FIX (Story 8.10): Use secure_loads with HMAC validation
        try:
            self._optimizer = secure_loads(state["optimizer_pickle"])
        except SecurePickleError as e:
            logger.error("pickle_signature_validation_failed", error=str(e))
            raise

        logger.info(
            "optimizer_state_restored",
            iteration=self._iteration,
            n_evaluations=len(self._evaluations),
        )

    def plot_convergence(self, save_path: str | Path | None = None) -> Union["Axes", "Figure"]:
        """Plot optimization convergence (objective value vs iterations).

        Args:
            save_path: Optional path to save plot

        Returns:
            Matplotlib Axes or Figure object

        Raises:
            ImportError: If matplotlib not installed
        """
        try:
            import matplotlib.pyplot as plt
            from skopt.plots import plot_convergence
        except ImportError as e:
            raise ImportError(
                "matplotlib required for plotting. Install with: pip install rustybt[optimization]"
            ) from e

        result = self._optimizer.get_result()
        ax = plot_convergence(result)

        if save_path:
            # Get the figure from the axes
            fig = ax.figure if hasattr(ax, "figure") else plt.gcf()
            fig.savefig(save_path, dpi=300, bbox_inches="tight")
            logger.info("convergence_plot_saved", path=str(save_path))

        return ax

    def plot_objective(self, save_path: str | Path | None = None) -> Union["Axes", "Figure"]:
        """Plot parameter importance and objective function.

        Args:
            save_path: Optional path to save plot

        Returns:
            Matplotlib Axes or Figure object

        Raises:
            ImportError: If matplotlib not installed
        """
        try:
            import matplotlib.pyplot as plt
            from skopt.plots import plot_objective
        except ImportError as e:
            raise ImportError(
                "matplotlib required for plotting. Install with: pip install rustybt[optimization]"
            ) from e

        result = self._optimizer.get_result()
        ax = plot_objective(result)

        if save_path:
            # Get the figure from the axes
            fig = ax[0, 0].figure if isinstance(ax, np.ndarray) else plt.gcf()
            fig.savefig(save_path, dpi=300, bbox_inches="tight")
            logger.info("objective_plot_saved", path=str(save_path))

        return ax

    def plot_evaluations(self, save_path: str | Path | None = None) -> Union["Axes", "Figure"]:
        """Plot parameter values vs objective for each evaluation.

        Args:
            save_path: Optional path to save plot

        Returns:
            Matplotlib Axes or Figure object

        Raises:
            ImportError: If matplotlib not installed
        """
        try:
            import matplotlib.pyplot as plt
            from skopt.plots import plot_evaluations
        except ImportError as e:
            raise ImportError(
                "matplotlib required for plotting. Install with: pip install rustybt[optimization]"
            ) from e

        result = self._optimizer.get_result()
        ax = plot_evaluations(result)

        if save_path:
            # Get the figure from the axes
            fig = ax[0, 0].figure if isinstance(ax, np.ndarray) else plt.gcf()
            fig.savefig(save_path, dpi=300, bbox_inches="tight")
            logger.info("evaluations_plot_saved", path=str(save_path))

        return ax
