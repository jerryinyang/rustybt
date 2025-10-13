"""Tests for base data adapter framework."""

import time
from decimal import Decimal

import pandas as pd
import polars as pl
import pytest
from hypothesis import given
from hypothesis import strategies as st

from rustybt.data.adapters.base import (
    BaseDataAdapter,
    DataAdapterError,
    InvalidDataError,
    NetworkError,
    RateLimiter,
    RateLimitError,
    ValidationError,
    detect_outliers,
    validate_ohlcv_relationships,
    with_retry,
)

# ============================================================================
# Abstract Methods Tests
# ============================================================================


def test_abstract_methods_raise_not_implemented():
    """BaseDataAdapter abstract methods must be overridden."""
    # Cannot instantiate abstract class
    with pytest.raises(TypeError):

        class IncompleteAdapter(BaseDataAdapter):
            pass

        IncompleteAdapter(name="incomplete")


def test_concrete_adapter_can_be_instantiated():
    """Concrete adapter with all methods implemented can be instantiated."""

    class ConcreteAdapter(BaseDataAdapter):
        async def fetch(self, symbols, start_date, end_date, resolution):
            return pl.DataFrame()

        def validate(self, df):
            return True

        def standardize(self, df):
            return df

    adapter = ConcreteAdapter(name="concrete")
    assert adapter.name == "concrete"
    assert adapter.max_retries == 3
    assert adapter.initial_retry_delay == 1.0
    assert adapter.backoff_factor == 2.0


# ============================================================================
# OHLCV Validation Tests
# ============================================================================


def test_validate_ohlcv_relationships_with_valid_data():
    """Validation passes for valid OHLCV data."""
    valid_data = pl.DataFrame(
        {
            "timestamp": [pd.Timestamp("2023-01-01"), pd.Timestamp("2023-01-02")],
            "symbol": ["AAPL", "AAPL"],
            "open": [Decimal("100"), Decimal("101")],
            "high": [Decimal("105"), Decimal("106")],
            "low": [Decimal("98"), Decimal("99")],
            "close": [Decimal("102"), Decimal("103")],
            "volume": [Decimal("1000"), Decimal("1500")],
        }
    )

    assert validate_ohlcv_relationships(valid_data) is True


def test_validate_ohlcv_relationships_detects_high_less_than_low():
    """Validation detects high < low violations."""
    invalid_data = pl.DataFrame(
        {
            "timestamp": [pd.Timestamp("2023-01-01")],
            "symbol": ["AAPL"],
            "open": [Decimal("100")],
            "high": [Decimal("95")],  # Invalid: high < low
            "low": [Decimal("98")],
            "close": [Decimal("99")],
            "volume": [Decimal("1000")],
        }
    )

    with pytest.raises(ValidationError, match="Invalid OHLCV relationships"):
        validate_ohlcv_relationships(invalid_data)


def test_validate_ohlcv_relationships_detects_high_less_than_open():
    """Validation detects high < open violations."""
    invalid_data = pl.DataFrame(
        {
            "timestamp": [pd.Timestamp("2023-01-01")],
            "symbol": ["AAPL"],
            "open": [Decimal("100")],
            "high": [Decimal("99")],  # Invalid: high < open
            "low": [Decimal("95")],
            "close": [Decimal("98")],
            "volume": [Decimal("1000")],
        }
    )

    with pytest.raises(ValidationError, match="Invalid OHLCV relationships"):
        validate_ohlcv_relationships(invalid_data)


def test_validate_ohlcv_relationships_detects_high_less_than_close():
    """Validation detects high < close violations."""
    invalid_data = pl.DataFrame(
        {
            "timestamp": [pd.Timestamp("2023-01-01")],
            "symbol": ["AAPL"],
            "open": [Decimal("95")],
            "high": [Decimal("98")],  # Invalid: high < close
            "low": [Decimal("94")],
            "close": [Decimal("100")],
            "volume": [Decimal("1000")],
        }
    )

    with pytest.raises(ValidationError, match="Invalid OHLCV relationships"):
        validate_ohlcv_relationships(invalid_data)


def test_validate_ohlcv_relationships_detects_low_greater_than_open():
    """Validation detects low > open violations."""
    invalid_data = pl.DataFrame(
        {
            "timestamp": [pd.Timestamp("2023-01-01")],
            "symbol": ["AAPL"],
            "open": [Decimal("95")],
            "high": [Decimal("100")],
            "low": [Decimal("96")],  # Invalid: low > open
            "close": [Decimal("98")],
            "volume": [Decimal("1000")],
        }
    )

    with pytest.raises(ValidationError, match="Invalid OHLCV relationships"):
        validate_ohlcv_relationships(invalid_data)


def test_validate_ohlcv_relationships_detects_missing_columns():
    """Validation detects missing required columns."""
    invalid_data = pl.DataFrame(
        {
            "timestamp": [pd.Timestamp("2023-01-01")],
            "symbol": ["AAPL"],
            "open": [Decimal("100")],
            # Missing: high, low, close, volume
        }
    )

    with pytest.raises(ValidationError, match="Missing required columns"):
        validate_ohlcv_relationships(invalid_data)


def test_validate_ohlcv_relationships_detects_null_values():
    """Validation detects NULL values in required columns."""
    invalid_data = pl.DataFrame(
        {
            "timestamp": [pd.Timestamp("2023-01-01")],
            "symbol": ["AAPL"],
            "open": [None],  # NULL value
            "high": [Decimal("105")],
            "low": [Decimal("95")],
            "close": [Decimal("100")],
            "volume": [Decimal("1000")],
        }
    )

    with pytest.raises(ValidationError, match="NULL values found"):
        validate_ohlcv_relationships(invalid_data)


def test_validate_ohlcv_relationships_detects_unsorted_timestamps():
    """Validation detects unsorted timestamps."""
    invalid_data = pl.DataFrame(
        {
            "timestamp": [
                pd.Timestamp("2023-01-02"),
                pd.Timestamp("2023-01-01"),
            ],  # Unsorted
            "symbol": ["AAPL", "AAPL"],
            "open": [Decimal("100"), Decimal("101")],
            "high": [Decimal("105"), Decimal("106")],
            "low": [Decimal("98"), Decimal("99")],
            "close": [Decimal("102"), Decimal("103")],
            "volume": [Decimal("1000"), Decimal("1500")],
        }
    )

    with pytest.raises(ValidationError, match="Timestamps are not sorted"):
        validate_ohlcv_relationships(invalid_data)


def test_validate_ohlcv_relationships_detects_duplicate_timestamps():
    """Validation detects duplicate timestamps for same symbol."""
    invalid_data = pl.DataFrame(
        {
            "timestamp": [
                pd.Timestamp("2023-01-01"),
                pd.Timestamp("2023-01-01"),
            ],  # Duplicate
            "symbol": ["AAPL", "AAPL"],
            "open": [Decimal("100"), Decimal("101")],
            "high": [Decimal("105"), Decimal("106")],
            "low": [Decimal("98"), Decimal("99")],
            "close": [Decimal("102"), Decimal("103")],
            "volume": [Decimal("1000"), Decimal("1500")],
        }
    )

    with pytest.raises(ValidationError, match="Duplicate timestamps found"):
        validate_ohlcv_relationships(invalid_data)


# ============================================================================
# Outlier Detection Tests
# ============================================================================


def test_detect_outliers_identifies_price_spikes():
    """Outlier detection identifies price spikes exceeding threshold."""
    # Create data with steady prices and one large outlier
    # Normal prices with ~0.01% change,then a 50% spike which is well beyond any threshold
    data = pl.DataFrame(
        {
            "timestamp": [
                pd.Timestamp("2023-01-01"),
                pd.Timestamp("2023-01-02"),
                pd.Timestamp("2023-01-03"),
                pd.Timestamp("2023-01-04"),
                pd.Timestamp("2023-01-05"),
                pd.Timestamp("2023-01-06"),
                pd.Timestamp("2023-01-07"),
                pd.Timestamp("2023-01-08"),
            ],
            "symbol": ["AAPL"] * 8,
            "open": [Decimal("100")] * 8,
            "high": [Decimal("105")] * 8,
            "low": [Decimal("95")] * 8,
            "close": [
                Decimal("100.00"),
                Decimal("100.01"),
                Decimal("100.02"),
                Decimal("100.01"),
                Decimal("150.00"),  # Outlier: ~50% spike
                Decimal("100.03"),
                Decimal("100.02"),
                Decimal("100.01"),
            ],
            "volume": [Decimal("1000")] * 8,
        }
    )

    outliers = detect_outliers(data, threshold=3.0)

    # Should detect the spike at 2023-01-05
    assert len(outliers) >= 1
    assert pd.Timestamp("2023-01-05") in outliers["timestamp"].to_list()


def test_detect_outliers_returns_empty_for_normal_data():
    """Outlier detection returns empty DataFrame for normal data."""
    # Create data with small, normal price movements
    data = pl.DataFrame(
        {
            "timestamp": [
                pd.Timestamp("2023-01-01"),
                pd.Timestamp("2023-01-02"),
                pd.Timestamp("2023-01-03"),
            ],
            "symbol": ["AAPL"] * 3,
            "open": [Decimal("100")] * 3,
            "high": [Decimal("105")] * 3,
            "low": [Decimal("95")] * 3,
            "close": [Decimal("100"), Decimal("101"), Decimal("102")],
            "volume": [Decimal("1000")] * 3,
        }
    )

    outliers = detect_outliers(data, threshold=3.0)

    # Should detect no outliers
    assert len(outliers) == 0


# ============================================================================
# Rate Limiter Tests
# ============================================================================


@pytest.mark.asyncio
async def test_rate_limiter_allows_burst():
    """Rate limiter allows burst up to burst_size."""
    limiter = RateLimiter(requests_per_second=2, burst_size=3)

    start = time.time()
    await limiter.acquire()
    await limiter.acquire()
    await limiter.acquire()
    elapsed = time.time() - start

    # Should complete almost instantly (within burst)
    assert elapsed < 0.1


@pytest.mark.asyncio
async def test_rate_limiter_enforces_rate_limit():
    """Rate limiter blocks requests when limit exceeded."""
    limiter = RateLimiter(requests_per_second=2, burst_size=2)

    start = time.time()
    await limiter.acquire()  # Token 1
    await limiter.acquire()  # Token 2
    await limiter.acquire()  # Should block and wait
    elapsed = time.time() - start

    # Should wait approximately 0.5s for 3rd request (rate = 2/s)
    assert elapsed >= 0.4  # Allow some tolerance


@pytest.mark.asyncio
async def test_rate_limiter_tracks_statistics():
    """Rate limiter tracks requests_made and throttle_events."""
    limiter = RateLimiter(requests_per_second=2, burst_size=1)

    await limiter.acquire()
    await limiter.acquire()  # This should trigger throttle

    assert limiter.requests_made == 2
    assert limiter.throttle_events >= 1


# ============================================================================
# Retry Logic Tests
# ============================================================================


@pytest.mark.asyncio
async def test_retry_logic_succeeds_on_first_attempt():
    """Retry logic returns result on first successful attempt."""
    attempt_count = []

    @with_retry(max_retries=3, initial_delay=0.01, backoff_factor=2.0)
    async def successful_function():
        attempt_count.append(1)
        return "success"

    result = await successful_function()

    assert result == "success"
    assert len(attempt_count) == 1


@pytest.mark.asyncio
async def test_retry_logic_retries_on_network_error():
    """Retry logic retries on NetworkError."""
    attempt_times = []

    @with_retry(max_retries=3, initial_delay=0.05, backoff_factor=2.0)
    async def failing_function():
        attempt_times.append(time.time())
        if len(attempt_times) < 3:
            raise NetworkError("Temporary failure")
        return "success"

    result = await failing_function()

    # Should retry 3 times total
    assert len(attempt_times) == 3
    assert result == "success"


@pytest.mark.asyncio
async def test_retry_logic_performs_exponential_backoff():
    """Retry logic uses exponential backoff between attempts."""
    attempt_times = []

    @with_retry(max_retries=3, initial_delay=0.1, backoff_factor=2.0)
    async def failing_function():
        attempt_times.append(time.time())
        if len(attempt_times) < 3:
            raise NetworkError("Temporary failure")
        return "success"

    await failing_function()

    # Verify exponential backoff (delays approximately: 0.1s, 0.2s)
    # Allow tolerance for jitter (±20%)
    delay1 = attempt_times[1] - attempt_times[0]
    delay2 = attempt_times[2] - attempt_times[1]

    assert delay1 >= 0.08  # ~0.1s - 20% jitter
    assert delay2 >= 0.16  # ~0.2s - 20% jitter
    assert delay2 > delay1  # Second delay should be longer


@pytest.mark.asyncio
async def test_retry_logic_exhausts_retries_and_raises():
    """Retry logic raises exception after exhausting retries."""
    attempt_count = []

    @with_retry(max_retries=3, initial_delay=0.01, backoff_factor=2.0)
    async def always_failing_function():
        attempt_count.append(1)
        raise NetworkError("Permanent failure")

    with pytest.raises(NetworkError, match="Permanent failure"):
        await always_failing_function()

    # Should attempt exactly max_retries times
    assert len(attempt_count) == 3


@pytest.mark.asyncio
async def test_retry_logic_does_not_retry_validation_error():
    """Retry logic does not retry non-transient errors."""
    attempt_count = []

    @with_retry(max_retries=3, initial_delay=0.01, backoff_factor=2.0)
    async def validation_error_function():
        attempt_count.append(1)
        raise ValidationError("Invalid data")

    with pytest.raises(ValidationError, match="Invalid data"):
        await validation_error_function()

    # Should fail immediately without retries
    assert len(attempt_count) == 1


# ============================================================================
# Property-Based Tests
# ============================================================================


@given(
    ohlcv_data=st.lists(
        st.tuples(
            st.decimals(
                min_value=Decimal("1"),
                max_value=Decimal("1000"),
                allow_nan=False,
                allow_infinity=False,
                places=2,  # Limit decimal places to avoid precision issues
            ),  # low
            st.decimals(
                min_value=Decimal("1"),
                max_value=Decimal("1000"),
                allow_nan=False,
                allow_infinity=False,
                places=2,  # Limit decimal places to avoid precision issues
            ),  # high
        ).filter(
            lambda x: x[0] <= x[1]
        ),  # Ensure low <= high
        min_size=1,
        max_size=100,
    )
)
def test_standardized_data_preserves_ohlcv_invariants(ohlcv_data):
    """Standardized data must maintain valid OHLCV relationships."""
    # Create dataframe from property test data
    # Quantize decimals to avoid precision issues with Polars
    df = pl.DataFrame(
        {
            "timestamp": [
                pd.Timestamp("2023-01-01") + pd.Timedelta(days=i) for i in range(len(ohlcv_data))
            ],
            "symbol": ["TEST"] * len(ohlcv_data),
            "low": [low.quantize(Decimal("0.01")) for low, _ in ohlcv_data],
            "high": [high.quantize(Decimal("0.01")) for _, high in ohlcv_data],
            "open": [
                ((low + high) / Decimal("2")).quantize(Decimal("0.01")) for low, high in ohlcv_data
            ],  # midpoint
            "close": [
                ((low + high) / Decimal("2")).quantize(Decimal("0.01")) for low, high in ohlcv_data
            ],  # midpoint
            "volume": [Decimal("1000")] * len(ohlcv_data),
        }
    )

    # Validate should always pass for property-generated data
    assert validate_ohlcv_relationships(df) is True


# ============================================================================
# Exception Hierarchy Tests
# ============================================================================


def test_exception_hierarchy():
    """All adapter exceptions inherit from DataAdapterError."""
    assert issubclass(NetworkError, DataAdapterError)
    assert issubclass(RateLimitError, DataAdapterError)
    assert issubclass(InvalidDataError, DataAdapterError)
    assert issubclass(ValidationError, DataAdapterError)


def test_validation_error_stores_invalid_rows():
    """ValidationError can store invalid rows DataFrame."""
    invalid_rows = pl.DataFrame(
        {
            "timestamp": [pd.Timestamp("2023-01-01")],
            "symbol": ["AAPL"],
            "open": [Decimal("100")],
        }
    )

    error = ValidationError("Test error", invalid_rows=invalid_rows)

    assert error.invalid_rows is not None
    assert len(error.invalid_rows) == 1


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_concrete_adapter_full_workflow():
    """Test complete adapter workflow with all components."""

    class TestAdapter(BaseDataAdapter):
        async def fetch(self, symbols, start_date, end_date, resolution):
            # Simulate rate limiting
            await self.rate_limiter.acquire()

            # Create test data
            df = pl.DataFrame(
                {
                    "timestamp": [pd.Timestamp("2023-01-01")],
                    "symbol": symbols,
                    "open": [Decimal("100")],
                    "high": [Decimal("105")],
                    "low": [Decimal("95")],
                    "close": [Decimal("102")],
                    "volume": [Decimal("1000")],
                }
            )

            return self.standardize(df)

        def validate(self, df):
            return validate_ohlcv_relationships(df)

        def standardize(self, df):
            # Already in standard format
            return df

    adapter = TestAdapter(name="test", rate_limit_per_second=10)

    # Test fetch
    result = await adapter.fetch(
        symbols=["AAPL"],
        start_date=pd.Timestamp("2023-01-01"),
        end_date=pd.Timestamp("2023-01-31"),
        resolution="1d",
    )

    # Verify result
    assert len(result) == 1
    assert result["symbol"][0] == "AAPL"

    # Test validation
    assert adapter.validate(result) is True
