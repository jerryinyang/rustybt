"""Tests for resilience patterns: retry, health checks, and timeouts."""

import json
import signal
import tempfile
import time
from pathlib import Path

import pytest

from rustybt.validation.health_checks import validate_log_integrity
from rustybt.validation.models import HealthCheckResult
from rustybt.validation.resilience import retry
from rustybt.validation.timeouts import ValidationTimeoutError, timeout


class TestRetryDecorator:
    """Test retry decorator with exponential backoff."""

    def test_retry_succeeds_after_transient_failure(self):
        """Test that retry succeeds after transient failures."""
        call_count = 0

        @retry(max_attempts=3, backoff_factor=1, exceptions=(ValueError,))
        def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Transient error")
            return "success"

        result = flaky_function()

        assert result == "success"
        assert call_count == 3  # Failed twice, succeeded on third attempt

    def test_retry_exhausts_and_raises(self):
        """Test that retry exhausts attempts and re-raises exception."""
        call_count = 0

        @retry(max_attempts=3, backoff_factor=1, exceptions=(ValueError,))
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("Permanent error")

        with pytest.raises(ValueError, match="Permanent error"):
            always_fails()

        assert call_count == 3  # Tried 3 times before giving up

    def test_exponential_backoff_timing(self):
        """Test that exponential backoff increases wait time correctly."""
        call_times = []

        @retry(max_attempts=3, backoff_factor=2, exceptions=(ValueError,))
        def timed_function():
            call_times.append(time.time())
            if len(call_times) < 3:
                raise ValueError("Transient error")
            return "success"

        result = timed_function()

        assert result == "success"
        assert len(call_times) == 3

        # Check backoff intervals (with some tolerance for timing)
        # Attempt 0 -> Attempt 1: ~1 second (2^0)
        # Attempt 1 -> Attempt 2: ~2 seconds (2^1)
        interval_1 = call_times[1] - call_times[0]
        interval_2 = call_times[2] - call_times[1]

        # Allow 20% tolerance for timing variability
        assert 0.8 <= interval_1 <= 1.2, f"First interval should be ~1s, got {interval_1}"
        assert 1.6 <= interval_2 <= 2.4, f"Second interval should be ~2s, got {interval_2}"

    def test_retry_only_catches_specified_exceptions(self):
        """Test that retry only catches specified exception types."""

        @retry(max_attempts=3, backoff_factor=1, exceptions=(ValueError,))
        def raises_different_exception():
            raise IOError("Not retryable")

        # Should not retry IOError, should raise immediately
        with pytest.raises(IOError, match="Not retryable"):
            raises_different_exception()

    def test_retry_succeeds_on_first_attempt(self):
        """Test that retry doesn't interfere when function succeeds immediately."""
        call_count = 0

        @retry(max_attempts=3, backoff_factor=2, exceptions=(ValueError,))
        def immediate_success():
            nonlocal call_count
            call_count += 1
            return "success"

        result = immediate_success()

        assert result == "success"
        assert call_count == 1  # Should only call once


class TestHealthChecks:
    """Test health check validation for log files."""

    def test_health_check_detects_missing_file(self):
        """Test that health check detects missing files."""
        result = validate_log_integrity(Path("/nonexistent/path.jsonl"))

        assert not result.passed
        assert result.diagnostics["file_exists"] is False
        assert result.diagnostics["file_readable"] is False

    def test_health_check_detects_corrupted_jsonl(self, tmp_path):
        """Test that health check detects corrupted JSONL format."""
        log_file = tmp_path / "corrupted.jsonl"
        log_file.write_text(
            '{"layer": "data", "event": "bar", "timestamp": "2020-01-01T09:30:00"}\n'
            'not valid json\n'  # Corrupted line
            '{"layer": "signals", "event": "signal", "timestamp": "2020-01-01T09:31:00"}\n'
        )

        result = validate_log_integrity(log_file)

        assert not result.passed
        assert result.diagnostics["file_exists"] is True
        assert result.diagnostics["file_readable"] is True
        assert result.diagnostics["valid_jsonl"] is False
        assert 2 in result.diagnostics["truncated_lines"]  # Line 2 is corrupted
        assert result.diagnostics["row_count"] == 2  # 2 valid records

    def test_health_check_detects_truncated_lines(self, tmp_path):
        """Test that health check detects truncated JSON lines."""
        log_file = tmp_path / "truncated.jsonl"
        log_file.write_text(
            '{"layer": "data", "event": "bar", "timestamp": "2020-01-01T09:30:00"}\n'
            '{"layer": "signals", "event": "signal", "times\n'  # Truncated
            '{"layer": "orders", "event": "order", "timestamp": "2020-01-01T09:32:00"}\n'
        )

        result = validate_log_integrity(log_file)

        assert not result.passed
        assert result.diagnostics["valid_jsonl"] is False
        assert 2 in result.diagnostics["truncated_lines"]

    def test_health_check_detects_missing_required_fields(self, tmp_path):
        """Test that health check detects missing required fields."""
        log_file = tmp_path / "missing_fields.jsonl"
        log_file.write_text(
            '{"layer": "data", "event": "bar", "timestamp": "2020-01-01T09:30:00"}\n'
            '{"layer": "signals", "event": "signal"}\n'  # Missing timestamp
            '{"event": "order", "timestamp": "2020-01-01T09:32:00"}\n'  # Missing layer
        )

        result = validate_log_integrity(log_file)

        assert not result.passed
        assert "timestamp" in result.diagnostics["missing_fields"]
        assert "layer" in result.diagnostics["missing_fields"]

    def test_health_check_detects_empty_file(self, tmp_path):
        """Test that health check detects empty log files."""
        log_file = tmp_path / "empty.jsonl"
        log_file.write_text("")

        result = validate_log_integrity(log_file)

        assert not result.passed
        assert result.diagnostics["row_count"] == 0
        assert "error" in result.diagnostics

    def test_health_check_passes_valid_log(self, tmp_path):
        """Test that health check passes for valid JSONL log."""
        log_file = tmp_path / "valid.jsonl"
        log_file.write_text(
            '{"layer": "data", "event": "bar", "timestamp": "2020-01-01T09:30:00", "asset": "AAPL"}\n'
            '{"layer": "signals", "event": "signal", "timestamp": "2020-01-01T09:31:00", "asset": "AAPL"}\n'
            '{"layer": "orders", "event": "order", "timestamp": "2020-01-01T09:32:00", "asset": "AAPL"}\n'
        )

        result = validate_log_integrity(log_file)

        assert result.passed
        assert result.diagnostics["file_exists"] is True
        assert result.diagnostics["file_readable"] is True
        assert result.diagnostics["valid_jsonl"] is True
        assert result.diagnostics["row_count"] == 3
        assert result.diagnostics["truncated_lines"] == []
        assert result.diagnostics["missing_fields"] == []

    def test_health_check_skips_empty_lines(self, tmp_path):
        """Test that health check ignores empty lines in JSONL."""
        log_file = tmp_path / "with_empty_lines.jsonl"
        log_file.write_text(
            '{"layer": "data", "event": "bar", "timestamp": "2020-01-01T09:30:00"}\n'
            '\n'  # Empty line
            '{"layer": "signals", "event": "signal", "timestamp": "2020-01-01T09:31:00"}\n'
            '\n'  # Another empty line
        )

        result = validate_log_integrity(log_file)

        assert result.passed
        assert result.diagnostics["row_count"] == 2  # Only counts non-empty lines


class TestTimeoutDecorator:
    """Test timeout decorator for hanging operations."""

    @pytest.mark.skipif(
        not hasattr(signal, "SIGALRM"),
        reason="signal.SIGALRM not available (Windows platform)",
    )
    def test_timeout_kills_slow_operation(self):
        """Test that timeout raises ValidationTimeoutError for slow operations."""

        @timeout(seconds=1)
        def slow_function():
            time.sleep(5)  # Will timeout after 1 second
            return "should not reach here"

        with pytest.raises(ValidationTimeoutError, match="exceeded 1s timeout"):
            slow_function()

    @pytest.mark.skipif(
        not hasattr(signal, "SIGALRM"),
        reason="signal.SIGALRM not available (Windows platform)",
    )
    def test_timeout_allows_fast_operation(self):
        """Test that timeout doesn't interfere with fast operations."""

        @timeout(seconds=5)
        def fast_function():
            time.sleep(0.1)
            return "success"

        result = fast_function()

        assert result == "success"

    @pytest.mark.skipif(
        not hasattr(signal, "SIGALRM"),
        reason="signal.SIGALRM not available (Windows platform)",
    )
    def test_timeout_cleans_up_alarm(self):
        """Test that timeout always cleans up alarm signal."""

        @timeout(seconds=2)
        def function_with_exception():
            raise ValueError("Test exception")

        # Timeout should clean up alarm even when function raises exception
        with pytest.raises(ValueError, match="Test exception"):
            function_with_exception()

        # Verify alarm was cancelled (alarm(0) returns remaining time)
        remaining = signal.alarm(0)
        assert remaining == 0  # No alarm should be active

    @pytest.mark.skipif(
        not hasattr(signal, "SIGALRM"),
        reason="signal.SIGALRM not available (Windows platform)",
    )
    def test_timeout_with_different_durations(self):
        """Test timeout with various duration settings."""

        @timeout(seconds=2)
        def medium_slow():
            time.sleep(1)
            return "success"

        # Should complete within 2 second timeout
        result = medium_slow()
        assert result == "success"

        @timeout(seconds=1)
        def too_slow():
            time.sleep(3)
            return "should not reach"

        # Should timeout
        with pytest.raises(ValidationTimeoutError):
            too_slow()


class TestResilienceIntegration:
    """Integration tests for combined resilience patterns."""

    def test_retry_with_timeout_success(self):
        """Test retry and timeout working together (success case)."""
        call_count = 0

        @retry(max_attempts=3, backoff_factor=1, exceptions=(ValueError,))
        @timeout(seconds=5)
        def flaky_but_fast():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Transient error")
            time.sleep(0.1)
            return "success"

        if hasattr(signal, "SIGALRM"):
            result = flaky_but_fast()
            assert result == "success"
            assert call_count == 2

    @pytest.mark.skipif(
        not hasattr(signal, "SIGALRM"),
        reason="signal.SIGALRM not available (Windows platform)",
    )
    def test_retry_with_timeout_failure(self):
        """Test that timeout can interrupt retry attempts."""

        @retry(max_attempts=5, backoff_factor=1, exceptions=(ValueError,))
        @timeout(seconds=2)
        def always_slow():
            time.sleep(3)  # Each attempt takes 3s, timeout is 2s
            raise ValueError("Should timeout before retry succeeds")

        # Timeout should trigger before retry exhausts attempts
        with pytest.raises(ValidationTimeoutError):
            always_slow()
