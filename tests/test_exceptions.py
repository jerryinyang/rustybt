"""Tests for RustyBT exception hierarchy."""

from __future__ import annotations

import pytest

from rustybt.exceptions import (
    AlignmentCircuitBreakerError,
    AssetValidationError,
    BrokerAuthenticationError,
    BrokerConnectionError,
    BrokerError,
    BrokerRateLimitError,
    BrokerResponseError,
    CircuitBreakerError,
    CircuitBreakerTrippedError,
    ConfigValidationError,
    DataAdapterError,
    DataError,
    DataNotFoundError,
    DataValidationError,
    InsufficientFundsError,
    InvalidOrderError,
    InvalidSignalError,
    LookaheadError,
    OrderError,
    OrderNotFoundError,
    OrderRejectedError,
    ParameterValidationError,
    RustyBTError,
    StrategyError,
    StrategyExecutionError,
    StrategyInitializationError,
    ValidationError,
)


class TestRustyBTError:
    """Tests for base RustyBTError exception."""

    def test_default_initialization(self) -> None:
        """Test creating base exception with default message."""
        exc = RustyBTError("RustyBT encountered an error")
        assert str(exc) == "RustyBT encountered an error"
        assert exc.context == {}
        assert exc.cause is None

    def test_custom_message(self) -> None:
        """Test creating base exception with custom message."""
        exc = RustyBTError("Custom error message")
        assert str(exc) == "Custom error message"
        assert exc.message == "Custom error message"

    def test_with_context(self) -> None:
        """Test exception with context dictionary."""
        exc = RustyBTError("Error occurred", context={"asset": "AAPL", "amount": 100})
        assert exc.context == {"asset": "AAPL", "amount": 100}
        assert "asset='AAPL'" in str(exc)
        assert "amount=100" in str(exc)

    def test_with_cause(self) -> None:
        """Test exception with underlying cause."""
        cause = ValueError("Original error")
        exc = RustyBTError("Wrapper error", cause=cause)
        assert exc.cause is cause

    def test_context_filtering_none_values(self) -> None:
        """Test that None values are filtered from context."""
        exc = RustyBTError("Error", context={"valid": "value", "invalid": None, "also_valid": 123})
        assert exc.context == {"valid": "value", "also_valid": 123}
        assert "invalid" not in exc.context

    def test_repr(self) -> None:
        """Test repr includes message and context."""
        exc = RustyBTError("Test error", context={"key": "value"})
        repr_str = repr(exc)
        assert "RustyBTError" in repr_str
        assert "Test error" in repr_str
        assert "key" in repr_str

    def test_to_log_fields(self) -> None:
        """Test structured logging fields."""
        exc = RustyBTError("Test error", context={"asset": "AAPL", "price": 150.0})
        log_fields = exc.to_log_fields()

        assert log_fields["error"] == "RustyBTError"
        assert log_fields["message"] == "Test error"
        assert log_fields["asset"] == "AAPL"
        assert log_fields["price"] == 150.0

    def test_to_log_fields_with_cause(self) -> None:
        """Test log fields include cause information."""
        cause = ValueError("Root cause")
        exc = RustyBTError("Wrapper", cause=cause, context={"key": "value"})
        log_fields = exc.to_log_fields()

        assert "cause" in log_fields
        assert "ValueError" in log_fields["cause"]


class TestDataErrors:
    """Tests for data-related exceptions."""

    def test_data_error_default(self) -> None:
        """Test DataError with default message."""
        exc = DataError()
        assert str(exc) == "Data operation failed"

    def test_data_not_found_error(self) -> None:
        """Test DataNotFoundError with asset context."""
        exc = DataNotFoundError(
            "Price data not found", asset="AAPL", start="2023-01-01", end="2023-01-31"
        )
        assert exc.context["asset"] == "AAPL"
        assert exc.context["start"] == "2023-01-01"
        assert exc.context["end"] == "2023-01-31"

    def test_data_validation_error(self) -> None:
        """Test DataValidationError with invalid rows."""
        exc = DataValidationError("Invalid OHLCV data", invalid_rows=5)
        assert exc.context["invalid_rows"] == 5

    def test_lookahead_error(self) -> None:
        """Test LookaheadError with timestamp context."""
        exc = LookaheadError(
            "Accessed future data", requested_dt="2023-01-02", current_dt="2023-01-01"
        )
        assert exc.context["requested_dt"] == "2023-01-02"
        assert exc.context["current_dt"] == "2023-01-01"

    def test_data_adapter_error(self) -> None:
        """Test DataAdapterError with adapter context."""
        exc = DataAdapterError("API request failed", adapter="YFinanceAdapter", attempt=3)
        assert exc.context["adapter"] == "YFinanceAdapter"
        assert exc.context["attempt"] == 3


class TestOrderErrors:
    """Tests for order-related exceptions."""

    def test_order_rejected_error(self) -> None:
        """Test OrderRejectedError with full context."""
        exc = OrderRejectedError(
            "Order rejected by broker",
            order_id="ORD123",
            asset="AAPL",
            broker="Binance",
            reason="Insufficient margin",
        )
        assert exc.context["order_id"] == "ORD123"
        assert exc.context["asset"] == "AAPL"
        assert exc.context["broker"] == "Binance"
        assert exc.context["reason"] == "Insufficient margin"

    def test_order_not_found_error(self) -> None:
        """Test OrderNotFoundError."""
        exc = OrderNotFoundError("Order not found", order_id="ORD456")
        assert exc.context["order_id"] == "ORD456"

    def test_insufficient_funds_error(self) -> None:
        """Test InsufficientFundsError with balance context."""
        exc = InsufficientFundsError("Not enough balance", required="10000.00", available="5000.00")
        assert exc.context["required"] == "10000.00"
        assert exc.context["available"] == "5000.00"

    def test_invalid_order_error(self) -> None:
        """Test InvalidOrderError with parameter context."""
        exc = InvalidOrderError("Invalid order parameter", parameter="limit_price", value="-150.00")
        assert exc.context["parameter"] == "limit_price"
        assert exc.context["value"] == "-150.00"


class TestBrokerErrors:
    """Tests for broker-related exceptions."""

    def test_broker_connection_error(self) -> None:
        """Test BrokerConnectionError."""
        exc = BrokerConnectionError("Connection timeout", broker="Binance")
        assert exc.context["broker"] == "Binance"

    def test_broker_authentication_error(self) -> None:
        """Test BrokerAuthenticationError."""
        exc = BrokerAuthenticationError("Invalid API key", broker="Kraken")
        assert exc.context["broker"] == "Kraken"

    def test_broker_rate_limit_error(self) -> None:
        """Test BrokerRateLimitError with reset time."""
        exc = BrokerRateLimitError("Rate limit exceeded", broker="Coinbase", reset_after=60.0)
        assert exc.context["broker"] == "Coinbase"
        assert exc.context["reset_after"] == 60.0

    def test_broker_response_error(self) -> None:
        """Test BrokerResponseError with status code."""
        exc = BrokerResponseError("Invalid response", broker="Bybit", status_code=500)
        assert exc.context["broker"] == "Bybit"
        assert exc.context["status_code"] == 500


class TestStrategyErrors:
    """Tests for strategy-related exceptions."""

    def test_strategy_initialization_error(self) -> None:
        """Test StrategyInitializationError."""
        exc = StrategyInitializationError("Failed to initialize strategy")
        assert "failed to initialize strategy" in str(exc).lower()

    def test_strategy_execution_error(self) -> None:
        """Test StrategyExecutionError."""
        exc = StrategyExecutionError("Strategy crashed during execution")
        assert "execution" in str(exc).lower()

    def test_invalid_signal_error(self) -> None:
        """Test InvalidSignalError."""
        exc = InvalidSignalError("Signal value out of range")
        assert "signal" in str(exc).lower()


class TestValidationErrors:
    """Tests for validation-related exceptions."""

    def test_validation_error(self) -> None:
        """Test base ValidationError with field context."""
        exc = ValidationError("Validation failed", field="amount", value=-100)
        assert exc.context["field"] == "amount"
        assert exc.context["value"] == -100

    def test_config_validation_error(self) -> None:
        """Test ConfigValidationError."""
        exc = ConfigValidationError("Invalid configuration")
        assert "config" in str(exc).lower()

    def test_asset_validation_error(self) -> None:
        """Test AssetValidationError."""
        exc = AssetValidationError("Invalid asset symbol")
        assert "asset" in str(exc).lower()

    def test_parameter_validation_error(self) -> None:
        """Test ParameterValidationError."""
        exc = ParameterValidationError("Invalid parameter")
        assert "parameter" in str(exc).lower()


class TestCircuitBreakerErrors:
    """Tests for circuit breaker exceptions."""

    def test_circuit_breaker_tripped_error(self) -> None:
        """Test CircuitBreakerTrippedError."""
        exc = CircuitBreakerTrippedError("Circuit breaker is open")
        assert "open" in str(exc).lower()

    def test_alignment_circuit_breaker_error(self) -> None:
        """Test AlignmentCircuitBreakerError."""
        exc = AlignmentCircuitBreakerError("Backtest/live alignment error")
        assert "alignment" in str(exc).lower()


class TestExceptionHierarchy:
    """Tests for exception inheritance hierarchy."""

    def test_data_error_inherits_from_base(self) -> None:
        """Test DataError inherits from RustyBTError."""
        exc = DataError()
        assert isinstance(exc, RustyBTError)
        assert isinstance(exc, Exception)

    def test_data_not_found_inherits_from_data_error(self) -> None:
        """Test DataNotFoundError inherits from DataError."""
        exc = DataNotFoundError()
        assert isinstance(exc, DataError)
        assert isinstance(exc, RustyBTError)

    def test_order_error_inherits_from_base(self) -> None:
        """Test OrderError inherits from RustyBTError."""
        exc = OrderError()
        assert isinstance(exc, RustyBTError)

    def test_order_rejected_inherits_from_order_error(self) -> None:
        """Test OrderRejectedError inherits from OrderError."""
        exc = OrderRejectedError()
        assert isinstance(exc, OrderError)
        assert isinstance(exc, RustyBTError)

    def test_broker_error_inherits_from_base(self) -> None:
        """Test BrokerError inherits from RustyBTError."""
        exc = BrokerError()
        assert isinstance(exc, RustyBTError)

    def test_broker_connection_inherits_from_broker_error(self) -> None:
        """Test BrokerConnectionError inherits from BrokerError."""
        exc = BrokerConnectionError()
        assert isinstance(exc, BrokerError)
        assert isinstance(exc, RustyBTError)

    def test_strategy_error_inherits_from_base(self) -> None:
        """Test StrategyError inherits from RustyBTError."""
        exc = StrategyError()
        assert isinstance(exc, RustyBTError)

    def test_validation_error_inherits_from_base(self) -> None:
        """Test ValidationError inherits from RustyBTError."""
        exc = ValidationError()
        assert isinstance(exc, RustyBTError)

    def test_circuit_breaker_error_inherits_from_base(self) -> None:
        """Test CircuitBreakerError inherits from RustyBTError."""
        exc = CircuitBreakerError()
        assert isinstance(exc, RustyBTError)


class TestExceptionCatching:
    """Tests for exception catching patterns."""

    def test_catch_specific_data_error(self) -> None:
        """Test catching specific DataNotFoundError."""
        with pytest.raises(DataNotFoundError):
            raise DataNotFoundError("Data not found", asset="AAPL")

    def test_catch_broad_data_error(self) -> None:
        """Test catching DataError catches all data exceptions."""
        with pytest.raises(DataError):
            raise DataNotFoundError("Specific error")

    def test_catch_base_rustybt_error(self) -> None:
        """Test catching RustyBTError catches all custom exceptions."""
        with pytest.raises(RustyBTError):
            raise OrderRejectedError("Order rejected")

    def test_multiple_exception_handling(self) -> None:
        """Test handling multiple exception types."""

        def risky_operation(error_type: str) -> None:
            if error_type == "data":
                raise DataNotFoundError("Data error")
            elif error_type == "broker":
                raise BrokerConnectionError("Broker error")
            elif error_type == "order":
                raise OrderRejectedError("Order error")

        with pytest.raises(DataNotFoundError):
            risky_operation("data")

        with pytest.raises(BrokerConnectionError):
            risky_operation("broker")

        with pytest.raises(OrderRejectedError):
            risky_operation("order")
