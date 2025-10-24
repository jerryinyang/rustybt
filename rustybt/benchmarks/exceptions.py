"""
Custom exceptions for benchmarking infrastructure.

All exceptions follow zero-mock enforcement (CR-002) - errors represent real
failure conditions, not simulated scenarios.
"""


class BenchmarkError(Exception):
    """Base exception for all benchmarking errors."""

    pass


class ProfilingError(BenchmarkError):
    """Raised when profiling execution fails."""

    pass


class ThresholdEvaluationError(BenchmarkError):
    """Raised when threshold evaluation cannot be performed."""

    pass


class FunctionalEquivalenceError(BenchmarkError):
    """
    Raised when optimized implementation produces different results than baseline.

    This is a BLOCKING error - functional consistency is mandatory before
    performance evaluation (per spec requirements).
    """

    pass


class InsufficientDataError(BenchmarkError):
    """Raised when insufficient benchmark runs for statistical validity."""

    pass


class BenchmarkDataError(BenchmarkError):
    """Raised when benchmark data is invalid or corrupted."""

    pass


class OptimizationComponentError(BenchmarkError):
    """Raised when optimization component implementation fails."""

    pass


class SequentialEvaluationError(BenchmarkError):
    """Raised when sequential evaluation workflow encounters an error."""

    pass
