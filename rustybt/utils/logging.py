"""Structured audit logging for RustyBT.

This module provides comprehensive trade-by-trade audit logging using structlog
with JSON output for searchability and compliance.
"""

import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any

import structlog
from structlog.typing import EventDict, WrappedLogger


def mask_sensitive_data(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Mask sensitive data in logs.

    Args:
        logger: The logger instance
        method_name: The logging method name (info, error, etc.)
        event_dict: The event dictionary containing log data

    Returns:
        Modified event dictionary with sensitive fields masked
    """
    sensitive_keys = [
        "api_key",
        "api_secret",
        "password",
        "token",
        "encryption_key",
        "secret",
        "credentials",
        "private_key",
    ]

    for key in sensitive_keys:
        if key in event_dict:
            event_dict[key] = "***MASKED***"

    return event_dict


def configure_logging(
    log_dir: Path | None = None,
    log_level: str = "INFO",
    log_to_console: bool = True,
    log_to_file: bool = True,
) -> None:
    """Configure structured logging with JSON output.

    Args:
        log_dir: Directory for log files (defaults to ./logs)
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_console: Whether to log to console
        log_to_file: Whether to log to file

    Raises:
        ValueError: If log_level is invalid
        OSError: If log directory cannot be created
    """
    if log_dir is None:
        log_dir = Path("logs")

    # Validate log level
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    log_level_upper = log_level.upper()
    if log_level_upper not in valid_levels:
        raise ValueError(f"Invalid log level: {log_level}. Must be one of {valid_levels}")

    # Ensure log directory exists
    if log_to_file:
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise OSError(f"Failed to create log directory '{log_dir}': {e}") from e

    # Configure handlers
    handlers: list[logging.Handler] = []
    if log_to_file:
        handlers.append(
            TimedRotatingFileHandler(
                filename=log_dir / "rustybt.log",
                when="midnight",
                interval=1,
                backupCount=30,  # Keep 30 days
                encoding="utf-8",
            )
        )
    if log_to_console:
        handlers.append(logging.StreamHandler())

    # Configure standard library logging (structlog uses it as backend)
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level_upper),
        handlers=handlers,
        force=True,  # Override any existing configuration
    )

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,  # Include bound context
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            mask_sensitive_data,  # Custom processor to mask secrets
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, log_level_upper)),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> Any:
    """Get a structlog logger instance.

    Args:
        name: Optional logger name (typically __name__)

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)
