"""Benchmark strategies for comprehensive performance testing.

This module contains deterministic strategies used for benchmarking:
- Simple: 1-2 indicators (SMA crossover)
- Medium: 3-5 indicators (Momentum + RSI + Volume + BB)
- Complex: 6+ indicators (Multi-indicator scoring system)

All strategies are deterministic (same inputs produce same results).
"""

from .momentum_strategy import MomentumStrategy
from .multi_indicator_strategy import MultiIndicatorStrategy
from .simple_sma_crossover import SimpleSMACrossover

__all__ = [
    "MomentumStrategy",
    "MultiIndicatorStrategy",
    "SimpleSMACrossover",
]
