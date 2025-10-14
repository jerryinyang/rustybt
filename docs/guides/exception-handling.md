# RustyBT Exception Handling Guide

## Overview

RustyBT implements a comprehensive exception hierarchy that provides context-rich error handling across the entire framework. This guide explains the exception structure, when to use each exception type, and best practices for error handling.

## Exception Hierarchy

```
RustyBTError (base)
├── DataError
│   ├── DataNotFoundError
│   ├── DataValidationError
│   ├── LookaheadError
│   └── DataAdapterError
├── OrderError
│   ├── OrderRejectedError
│   ├── OrderNotFoundError
│   ├── InsufficientFundsError
│   └── InvalidOrderError
├── BrokerError
│   ├── BrokerConnectionError
│   ├── BrokerAuthenticationError
│   ├── BrokerRateLimitError
│   └── BrokerResponseError
├── StrategyError
│   ├── StrategyInitializationError
│   ├── StrategyExecutionError
│   └── InvalidSignalError
├── ValidationError
│   ├── ConfigValidationError
│   ├── AssetValidationError
│   └── ParameterValidationError
└── CircuitBreakerError
    ├── CircuitBreakerTrippedError
    └── AlignmentCircuitBreakerError
```

## Base Exception: RustyBTError

All RustyBT exceptions inherit from `RustyBTError`, which provides:

- **Context-rich error messages**: Attach structured context data to exceptions
- **Structured logging**: Automatic conversion to log-friendly dictionaries
- **Cause tracking**: Link exceptions to their underlying causes

### Basic Usage

```python
from rustybt.exceptions import BrokerConnectionError

# Simple exception
raise BrokerConnectionError("Failed to connect")

# With context
raise BrokerConnectionError(
    "Connection timeout",
    broker="Binance",
    context={"host": "api.binance.com", "timeout": 30}
)

# With cause
try:
    # Some operation
    pass
except Exception as e:
    raise BrokerConnectionError(
        "Connection failed",
        broker="Binance",
        cause=e
    )
```

### Context and Logging

All exceptions can be converted to structured log fields:

```python
import structlog
from rustybt.exceptions import OrderRejectedError

logger = structlog.get_logger(__name__)

try:
    # Submit order
    pass
except OrderRejectedError as exc:
    # Automatically includes all context
    logger.error("order_failed", **exc.to_log_fields())
```

## Exception Categories

### 1. Data Exceptions

Used for data acquisition and validation errors.

#### DataNotFoundError

Raised when requested data is not available.

```python
from rustybt.exceptions import DataNotFoundError

# Example usage
raise DataNotFoundError(
    "Price data not found",
    asset="AAPL",
    start="2023-01-01",
    end="2023-01-31"
)
```

**When to use:**
- Asset data not in database
- Historical data unavailable for requested timeframe
- Missing price information

#### DataValidationError

Raised when data fails validation checks.

```python
from rustybt.exceptions import DataValidationError

# Example usage
raise DataValidationError(
    "Invalid OHLCV data: high < low",
    invalid_rows=5,
    context={"symbol": "AAPL"}
)
```

**When to use:**
- OHLCV validation failures (high < low, etc.)
- Missing required columns
- Data type mismatches

#### LookaheadError

Raised when attempting to access future data (lookahead bias).

```python
from rustybt.exceptions import LookaheadError

# Example usage
raise LookaheadError(
    "Attempted to access future data",
    requested_dt="2023-01-02",
    current_dt="2023-01-01"
)
```

**When to use:**
- Accessing data beyond current simulation time
- Preventing lookahead bias in backtests

#### DataAdapterError

Raised when data adapter operations fail.

```python
from rustybt.exceptions import DataAdapterError

# Example usage
raise DataAdapterError(
    "API request failed",
    adapter="YFinanceAdapter",
    attempt=3,
    context={"symbol": "AAPL", "error_code": 404}
)
```

**When to use:**
- API request failures
- Network errors in data fetching
- Rate limit exceeded

### 2. Order Exceptions

Used for order submission and management errors.

#### OrderRejectedError

Raised when broker rejects an order.

```python
from rustybt.exceptions import OrderRejectedError

# Example usage
raise OrderRejectedError(
    "Order rejected by broker",
    order_id="ORD123",
    asset="AAPL",
    broker="Binance",
    reason="Insufficient margin"
)
```

**When to use:**
- Broker rejects order
- Margin requirements not met
- Invalid order parameters

#### InsufficientFundsError

Raised when account lacks sufficient funds.

```python
from rustybt.exceptions import InsufficientFundsError

# Example usage
raise InsufficientFundsError(
    "Insufficient funds for order",
    required="10000.00",
    available="5000.00",
    context={"asset": "BTC"}
)
```

**When to use:**
- Cash balance too low
- Margin insufficient
- Position limits exceeded

#### InvalidOrderError

Raised for invalid order parameters.

```python
from rustybt.exceptions import InvalidOrderError

# Example usage
raise InvalidOrderError(
    "Invalid limit price",
    parameter="limit_price",
    value="-150.00",
    context={"asset": "AAPL"}
)
```

**When to use:**
- Negative prices
- Invalid order types
- Quantity outside allowed range

### 3. Broker Exceptions

Used for broker API and connection errors.

#### BrokerConnectionError

Raised when unable to connect to broker.

```python
from rustybt.exceptions import BrokerConnectionError

# Example usage
raise BrokerConnectionError(
    "Connection timeout",
    broker="Binance",
    context={"host": "api.binance.com", "timeout": 30}
)
```

**When to use:**
- Network connectivity issues
- Broker API unreachable
- WebSocket connection failures

#### BrokerAuthenticationError

Raised when authentication fails.

```python
from rustybt.exceptions import BrokerAuthenticationError

# Example usage
raise BrokerAuthenticationError(
    "Invalid API credentials",
    broker="Kraken"
)
```

**When to use:**
- Invalid API keys
- Expired tokens
- Permission denied

#### BrokerRateLimitError

Raised when rate limit is exceeded.

```python
from rustybt.exceptions import BrokerRateLimitError

# Example usage
raise BrokerRateLimitError(
    "Rate limit exceeded",
    broker="Coinbase",
    reset_after=60.0
)
```

**When to use:**
- Too many requests per second
- Daily API quota exceeded
- Need to implement backoff

### 4. Strategy Exceptions

Used for strategy execution errors.

#### StrategyInitializationError

Raised when strategy initialization fails.

```python
from rustybt.exceptions import StrategyInitializationError

# Example usage
raise StrategyInitializationError(
    "Failed to load strategy config",
    context={"config_file": "strategy.yaml"}
)
```

#### StrategyExecutionError

Raised when strategy execution fails.

```python
from rustybt.exceptions import StrategyExecutionError

# Example usage
raise StrategyExecutionError(
    "Strategy crashed during handle_data",
    context={"asset": "AAPL", "timestamp": "2023-01-01"}
)
```

### 5. Validation Exceptions

Used for configuration and parameter validation.

#### ConfigValidationError

Raised for invalid configuration.

```python
from rustybt.exceptions import ConfigValidationError

# Example usage
raise ConfigValidationError(
    "Missing required field",
    field="api_key",
    context={"config_file": "config.yaml"}
)
```

## Error Handling Utilities

RustyBT provides utilities for common error handling patterns in `rustybt.utils.error_handling`.

### Retry with Exponential Backoff

Automatically retry operations on transient failures:

```python
from rustybt.utils.error_handling import retry_async
from rustybt.exceptions import BrokerConnectionError, BrokerRateLimitError

async def submit_order():
    # Your order submission logic
    pass

# Retry with exponential backoff
result = await retry_async(
    submit_order,
    retry_exceptions=(BrokerConnectionError, BrokerRateLimitError),
    max_attempts=5,
    base_delay=1.0,
    max_delay=30.0,
    backoff_factor=2.0,
    jitter=0.25,
    context={"operation": "submit_order", "asset": "AAPL"}
)
```

**Parameters:**
- `retry_exceptions`: Tuple of exceptions that should trigger retry
- `max_attempts`: Maximum retry attempts (including first try)
- `base_delay`: Initial delay in seconds
- `max_delay`: Maximum delay cap
- `backoff_factor`: Exponential multiplier (default: 2.0)
- `jitter`: Randomization factor (0.0-1.0)
- `context`: Additional logging context

### User vs. Developer Messages

Provide different messages for users and developers:

```python
from rustybt.utils.error_handling import render_user_message, render_developer_context
from rustybt.exceptions import BrokerConnectionError

try:
    # Connect to broker
    pass
except BrokerConnectionError as exc:
    # User sees clean message
    user_msg = render_user_message(exc)
    print(f"Error: {user_msg}")
    # Output: "Failed to connect"

    # Developer sees full context
    dev_context = render_developer_context(exc)
    logger.error("connection_failed", **dev_context)
    # Logs: {"error": "BrokerConnectionError", "broker": "Binance", ...}
```

### Structured Exception Logging

Log exceptions with full context:

```python
from rustybt.utils.error_handling import log_exception
from rustybt.exceptions import DataNotFoundError

try:
    # Fetch data
    pass
except DataNotFoundError as exc:
    log_exception(
        exc,
        level="warning",
        extra={"user_id": "user123", "session": "abc"}
    )
```

### Flatten Multiple Exceptions

Combine context from multiple exceptions:

```python
from rustybt.utils.error_handling import flatten_exceptions

errors = [
    BrokerConnectionError("Connection failed", broker="Binance"),
    DataNotFoundError("Data missing", asset="BTC"),
]

context = flatten_exceptions(errors)
logger.error("multiple_failures", **context)
# Output: {
#   "error_1": "BrokerConnectionError",
#   "error_1_broker": "Binance",
#   "error_2": "DataNotFoundError",
#   "error_2_asset": "BTC"
# }
```

## Best Practices

### 1. Always Provide Context

```python
# ❌ Bad: No context
raise BrokerConnectionError("Connection failed")

# ✅ Good: Rich context
raise BrokerConnectionError(
    "Connection failed",
    broker="Binance",
    context={"host": "api.binance.com", "error_code": "ETIMEDOUT"}
)
```

### 2. Use Specific Exceptions

```python
# ❌ Bad: Generic exception
raise BrokerError("Order rejected")

# ✅ Good: Specific exception
raise OrderRejectedError(
    "Order rejected",
    order_id="ORD123",
    reason="Insufficient margin"
)
```

### 3. Link Causes

```python
# ✅ Good: Preserve exception chain
try:
    response = requests.get(url)
except requests.RequestException as e:
    raise BrokerConnectionError(
        "Failed to connect",
        broker="Binance",
        cause=e
    )
```

### 4. Log Before Raising

```python
from rustybt.utils.error_handling import log_exception

try:
    # Operation
    pass
except BrokerConnectionError as exc:
    log_exception(exc, level="error")
    raise
```

### 5. Catch Specific, Raise Specific

```python
# ✅ Good: Catch and raise specific exceptions
try:
    data = fetch_data(asset)
except BrokerRateLimitError as e:
    logger.warning("rate_limited", **e.to_log_fields())
    # Wait and retry
    await asyncio.sleep(60)
    data = fetch_data(asset)
except BrokerConnectionError as e:
    logger.error("connection_failed", **e.to_log_fields())
    raise
```

### 6. Graceful Degradation

```python
from rustybt.utils.error_handling import log_exception

try:
    # Try primary data source
    data = fetch_from_primary(asset)
except DataAdapterError as exc:
    log_exception(exc, level="warning")
    # Fall back to secondary source
    data = fetch_from_fallback(asset)
```

## Testing Exception Handling

All exception handling should be thoroughly tested:

```python
import pytest
from rustybt.exceptions import OrderRejectedError

def test_order_rejection():
    """Test order rejection handling."""
    with pytest.raises(OrderRejectedError) as exc_info:
        submit_invalid_order()

    assert exc_info.value.context["order_id"] is not None
    assert "rejected" in str(exc_info.value).lower()
```

## Migration from Legacy Exceptions

If you have legacy code using standard Python exceptions, migrate gradually:

```python
# Old code
raise ValueError("Invalid order amount")

# New code
from rustybt.exceptions import InvalidOrderError
raise InvalidOrderError(
    "Invalid order amount",
    parameter="amount",
    value=-100
)
```

## See Also

- [User Guides](decimal-precision-configuration.md)
- [Examples & Tutorials](../examples/README.md)
