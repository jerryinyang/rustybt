"""rustybt Validation Framework.

This module contains the core components of the validation framework used to
compare rustybt strategies against Backtrader reference implementations.
"""

from rustybt.validation.base_strategy import (
    VALID_LAYERS,
    RustyBTValidatedStrategy,
    ValidatedStrategyMixin,
    ValidatedTradingAlgorithm,
    ValidationLayer,
)
from rustybt.validation.coordinator import ExecutionResult, execute_dual
from rustybt.validation.decorators import log_broker, log_order, log_portfolio, log_signal
from rustybt.validation.log_parser import (
    VALID_LAYERS as LOG_VALID_LAYERS,
    ValidationResult,
    count_log_entries,
    validate_log_schema,
)
from rustybt.validation.models import (
    Discrepancy,
    Finding,
    HealthCheckResult,
    Session,
    SessionStage,
)
from rustybt.validation.runner import (
    DEFAULT_TIMEOUT,
    run_backtrader_strategy,
    run_rustybt_strategy,
)

__all__ = [
    "Session",
    "SessionStage",
    "Finding",
    "Discrepancy",
    "HealthCheckResult",
    "RustyBTValidatedStrategy",
    "ValidatedStrategyMixin",
    "ValidatedTradingAlgorithm",
    "ValidationLayer",
    "VALID_LAYERS",
    # Decorators
    "log_signal",
    "log_order",
    "log_portfolio",
    "log_broker",
    # Runner functions
    "run_rustybt_strategy",
    "run_backtrader_strategy",
    "DEFAULT_TIMEOUT",
    # Log parsing
    "ValidationResult",
    "validate_log_schema",
    "count_log_entries",
    "LOG_VALID_LAYERS",
    # Coordinator
    "ExecutionResult",
    "execute_dual",
]
