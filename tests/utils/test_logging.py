"""Tests for structured audit logging (Story 8.7).

This module tests the structlog integration for comprehensive trade-by-trade
audit logging with JSON output format.
"""

import json
import logging
import tempfile
from pathlib import Path

import pytest

from rustybt.utils.logging import configure_logging, get_logger, mask_sensitive_data


class TestLoggingConfiguration:
    """Test logging configuration and setup (AC: 1, 9)."""

    def test_configure_logging_creates_directory(self):
        """Test that configure_logging creates log directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "test_logs"
            assert not log_dir.exists()

            configure_logging(log_dir=log_dir, log_to_console=False)

            assert log_dir.exists()
            assert log_dir.is_dir()

    def test_configure_logging_default_level(self):
        """Test that configure_logging sets default log level to INFO."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "test_logs"
            configure_logging(log_dir=log_dir, log_to_console=False)

            # Check that root logger is at INFO level
            assert logging.root.level == logging.INFO

    def test_configure_logging_custom_level(self):
        """Test that configure_logging respects custom log level."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "test_logs"
            configure_logging(log_dir=log_dir, log_level="DEBUG", log_to_console=False)

            # Check that root logger is at DEBUG level
            assert logging.root.level == logging.DEBUG

    def test_configure_logging_invalid_level(self):
        """Test that configure_logging raises error for invalid log level."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "test_logs"

            with pytest.raises(ValueError, match="Invalid log level"):
                configure_logging(log_dir=log_dir, log_level="INVALID")

    def test_configure_logging_creates_log_file(self):
        """Test that configure_logging creates log file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "test_logs"
            configure_logging(log_dir=log_dir, log_to_console=False)

            log_file = log_dir / "rustybt.log"
            assert log_file.exists()

    def test_get_logger_returns_structlog_instance(self):
        """Test that get_logger returns structlog logger."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "test_logs"
            configure_logging(log_dir=log_dir, log_to_console=False)

            logger = get_logger("test")
            assert logger is not None
            # Structlog loggers have bind method
            assert hasattr(logger, "bind")


class TestJSONOutput:
    """Test JSON logging format (AC: 6, 9)."""

    def test_logs_in_json_format(self):
        """Test that logs are written in JSON format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "test_logs"
            configure_logging(log_dir=log_dir, log_to_console=False, log_level="INFO")

            logger = get_logger("test")
            logger.info("test_event", key="value", number=42)

            # Force flush
            logging.shutdown()

            # Read log file
            log_file = log_dir / "rustybt.log"
            with open(log_file) as f:
                log_content = f.read().strip()

            # Parse as JSON
            log_entry = json.loads(log_content)

            # Verify JSON structure
            assert log_entry["event"] == "test_event"
            assert log_entry["key"] == "value"
            assert log_entry["number"] == 42
            assert "timestamp" in log_entry
            assert "level" in log_entry

    def test_logs_include_timestamp(self):
        """Test that logs include ISO 8601 timestamp."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "test_logs"
            configure_logging(log_dir=log_dir, log_to_console=False)

            logger = get_logger("test")
            logger.info("test_timestamp")

            # Force flush
            logging.shutdown()

            # Read log file
            log_file = log_dir / "rustybt.log"
            with open(log_file) as f:
                log_content = f.read().strip()

            log_entry = json.loads(log_content)

            # Verify timestamp format (ISO 8601 UTC)
            assert "timestamp" in log_entry
            assert "T" in log_entry["timestamp"]
            assert log_entry["timestamp"].endswith("Z")

    def test_logs_include_log_level(self):
        """Test that logs include log level."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "test_logs"
            configure_logging(log_dir=log_dir, log_to_console=False)

            logger = get_logger("test")
            logger.info("test_info")

            # Force flush
            logging.shutdown()

            # Read log file
            log_file = log_dir / "rustybt.log"
            with open(log_file) as f:
                log_content = f.read().strip()

            log_entry = json.loads(log_content)

            # Verify log level
            assert "level" in log_entry
            assert log_entry["level"] == "info"


class TestSensitiveDataMasking:
    """Test sensitive data masking (AC: 8, 9)."""

    def test_mask_api_key(self):
        """Test that API keys are masked in logs."""
        event_dict = {"api_key": "secret123", "other_data": "visible"}
        masked = mask_sensitive_data(None, "info", event_dict)

        assert masked["api_key"] == "***MASKED***"
        assert masked["other_data"] == "visible"

    def test_mask_api_secret(self):
        """Test that API secrets are masked in logs."""
        event_dict = {"api_secret": "topsecret", "other_data": "visible"}
        masked = mask_sensitive_data(None, "info", event_dict)

        assert masked["api_secret"] == "***MASKED***"
        assert masked["other_data"] == "visible"

    def test_mask_password(self):
        """Test that passwords are masked in logs."""
        event_dict = {"password": "mypassword", "username": "user123"}
        masked = mask_sensitive_data(None, "info", event_dict)

        assert masked["password"] == "***MASKED***"
        assert masked["username"] == "user123"

    def test_mask_token(self):
        """Test that tokens are masked in logs."""
        event_dict = {"token": "bearer_token_xyz", "user_id": "123"}
        masked = mask_sensitive_data(None, "info", event_dict)

        assert masked["token"] == "***MASKED***"
        assert masked["user_id"] == "123"

    def test_mask_encryption_key(self):
        """Test that encryption keys are masked in logs."""
        event_dict = {"encryption_key": "aes256key", "data_id": "456"}
        masked = mask_sensitive_data(None, "info", event_dict)

        assert masked["encryption_key"] == "***MASKED***"
        assert masked["data_id"] == "456"

    def test_mask_multiple_sensitive_fields(self):
        """Test that multiple sensitive fields are masked."""
        event_dict = {
            "api_key": "key123",
            "password": "pass456",
            "token": "tok789",
            "user": "john",
        }
        masked = mask_sensitive_data(None, "info", event_dict)

        assert masked["api_key"] == "***MASKED***"
        assert masked["password"] == "***MASKED***"
        assert masked["token"] == "***MASKED***"
        assert masked["user"] == "john"

    def test_sensitive_data_not_logged(self):
        """Test that sensitive data is not written to log file (integration test)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "test_logs"
            configure_logging(log_dir=log_dir, log_to_console=False)

            logger = get_logger("test")
            logger.info(
                "user_login",
                username="john",
                password="secret123",
                api_key="myapikey",
            )

            # Force flush
            logging.shutdown()

            # Read log file
            log_file = log_dir / "rustybt.log"
            with open(log_file) as f:
                log_content = f.read()

            # Verify sensitive data is masked
            assert "secret123" not in log_content
            assert "myapikey" not in log_content
            assert "***MASKED***" in log_content
            assert "john" in log_content  # Non-sensitive data is visible


class TestLogRotation:
    """Test log rotation configuration (AC: 7, 9)."""

    def test_log_rotation_configured(self):
        """Test that log rotation handler is configured."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "test_logs"
            configure_logging(log_dir=log_dir, log_to_console=False)

            # Check that TimedRotatingFileHandler is configured
            root_logger = logging.root
            handlers = root_logger.handlers

            # At least one handler should be TimedRotatingFileHandler
            from logging.handlers import TimedRotatingFileHandler

            timed_handlers = [h for h in handlers if isinstance(h, TimedRotatingFileHandler)]

            assert len(timed_handlers) > 0

            # Verify rotation settings
            handler = timed_handlers[0]
            assert handler.when.upper() == "MIDNIGHT"
            assert handler.backupCount == 30  # Keep 30 days

    def test_large_log_creates_single_file(self):
        """Test that logs can handle large volume without immediate rotation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "test_logs"
            configure_logging(log_dir=log_dir, log_to_console=False)

            logger = get_logger("test")

            # Write many log entries
            for i in range(1000):
                logger.info(f"log_entry_{i}", index=i, data="x" * 100)

            # Force flush
            logging.shutdown()

            # Verify log file exists and contains data
            log_file = log_dir / "rustybt.log"
            assert log_file.exists()
            assert log_file.stat().st_size > 0


class TestContextualInformation:
    """Test contextual information in logs (AC: 5, 9)."""

    def test_logs_include_event_type(self):
        """Test that logs can include event_type for filtering."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "test_logs"
            configure_logging(log_dir=log_dir, log_to_console=False)

            logger = get_logger("test")
            logger.info(
                "order_submitted",
                event_type="order_submitted",
                order_id="order-123",
                asset="AAPL",
            )

            # Force flush
            logging.shutdown()

            # Read log file
            log_file = log_dir / "rustybt.log"
            with open(log_file) as f:
                log_content = f.read().strip()

            log_entry = json.loads(log_content)

            # Verify contextual fields
            assert log_entry["event_type"] == "order_submitted"
            assert log_entry["order_id"] == "order-123"
            assert log_entry["asset"] == "AAPL"
