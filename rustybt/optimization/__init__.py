"""Optimization framework for systematic strategy parameter tuning."""

from rustybt.optimization.base import SearchAlgorithm
from rustybt.optimization.monte_carlo import MonteCarloResult, MonteCarloSimulator
from rustybt.optimization.noise_infusion import (
    NoiseInfusionResult,
    NoiseInfusionSimulator,
)
from rustybt.optimization.objective import ObjectiveFunction, ObjectiveMetric
from rustybt.optimization.optimizer import Optimizer
from rustybt.optimization.parallel_optimizer import ParallelOptimizer
from rustybt.optimization.parameter_space import (
    CategoricalParameter,
    ContinuousParameter,
    DiscreteParameter,
    ParameterSpace,
)
from rustybt.optimization.result import OptimizationResult
from rustybt.optimization.sensitivity import (
    InteractionResult,
    SensitivityAnalyzer,
    SensitivityResult,
    calculate_stability_score,
)
from rustybt.optimization.walk_forward import (
    WalkForwardOptimizer,
    WalkForwardResult,
    WindowConfig,
    WindowData,
    WindowResult,
)

__all__ = [
    "CategoricalParameter",
    "ContinuousParameter",
    "DiscreteParameter",
    "InteractionResult",
    "MonteCarloResult",
    "MonteCarloSimulator",
    "NoiseInfusionResult",
    "NoiseInfusionSimulator",
    "ObjectiveFunction",
    "ObjectiveMetric",
    "OptimizationResult",
    "Optimizer",
    "ParallelOptimizer",
    "ParameterSpace",
    "SearchAlgorithm",
    "SensitivityAnalyzer",
    "SensitivityResult",
    "WalkForwardOptimizer",
    "WalkForwardResult",
    "WindowConfig",
    "WindowData",
    "WindowResult",
    "calculate_stability_score",
]
