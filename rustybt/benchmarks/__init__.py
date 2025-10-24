"""
Performance benchmarking and optimization infrastructure for RustyBT.

This module provides comprehensive benchmarking tools for measuring and optimizing
the performance of backtesting workflows, including:

- Profiling infrastructure for identifying bottlenecks
- Baseline implementation comparisons
- Performance threshold evaluation
- Sequential optimization evaluation workflow

All benchmarking follows constitutional requirements:
- Decimal precision for all metrics (CR-001)
- No mocks or synthetic data (CR-002)
- Full type safety with mypy --strict (CR-004)
- 95%+ test coverage (CR-005)
- Polars/Parquet data architecture (CR-006)
"""

from . import comparisons, exceptions, models, profiling, sequential, threshold

__all__ = [
    "comparisons",
    "exceptions",
    "models",
    "profiling",
    "sequential",
    "threshold",
]
