"""Backtrader Strategy Implementations.

This package contains the Backtrader implementations of the validation strategies.

Note: Directory named bt_strategies to avoid shadowing the backtrader package.
"""

from tests.validation.strategies.bt_strategies.base_validated import (
    VALID_LAYERS,
    BacktraderValidatedStrategy,
    ValidationLayer,
)
from tests.validation.strategies.bt_strategies.mean_reversion import (
    MeanReversionStrategy,
)
from tests.validation.strategies.bt_strategies.momentum import MomentumStrategy
from tests.validation.strategies.bt_strategies.multi_factor import MultiFactorStrategy
from tests.validation.strategies.bt_strategies.simple_strategy import SimpleStrategy
from tests.validation.strategies.bt_strategies.sma_crossover import (
    SMACrossoverStrategy,
)

__all__ = [
    "BacktraderValidatedStrategy",
    "ValidationLayer",
    "VALID_LAYERS",
    "MeanReversionStrategy",
    "MomentumStrategy",
    "MultiFactorStrategy",
    "SimpleStrategy",
    "SMACrossoverStrategy",
]
