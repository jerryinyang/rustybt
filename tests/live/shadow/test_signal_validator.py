"""Unit tests for SignalAlignmentValidator."""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
import pytz

from rustybt.assets import Equity, ExchangeInfo
from rustybt.live.shadow.config import ShadowTradingConfig
from rustybt.live.shadow.models import SignalAlignment, SignalRecord
from rustybt.live.shadow.signal_validator import SignalAlignmentValidator


@pytest.fixture
def config():
    """Create test configuration."""
    return ShadowTradingConfig(
        signal_match_rate_min=Decimal("0.95"),
        time_tolerance_ms=100,
    )


@pytest.fixture
def validator(config):
    """Create validator instance."""
    return SignalAlignmentValidator(config)


@pytest.fixture
def test_asset():
    """Create test asset."""
    exchange = ExchangeInfo("NASDAQ", "NASDAQ", "US")
    return Equity(1, exchange, symbol="TEST")


def test_exact_match(validator, test_asset):
    """Test exact match classification."""
    timestamp = datetime.utcnow()

    backtest_signal = SignalRecord(
        timestamp=timestamp,
        asset=test_asset,
        side="BUY",
        quantity=Decimal("100"),
        price=Decimal("50.00"),
        order_type="market",
        source="backtest",
    )

    live_signal = SignalRecord(
        timestamp=timestamp + timedelta(milliseconds=50),  # Within 100ms tolerance
        asset=test_asset,
        side="BUY",
        quantity=Decimal("100"),  # Exact quantity match
        price=Decimal("50.00"),
        order_type="market",
        source="live",
    )

    validator.add_backtest_signal(backtest_signal)
    result = validator.add_live_signal(live_signal)

    assert result is not None
    matched_signal, alignment = result
    assert alignment == SignalAlignment.EXACT_MATCH
    assert matched_signal == backtest_signal


def test_direction_match(validator, test_asset):
    """Test direction match with quantity difference."""
    timestamp = datetime.utcnow()

    backtest_signal = SignalRecord(
        timestamp=timestamp,
        asset=test_asset,
        side="BUY",
        quantity=Decimal("100"),
        price=Decimal("50.00"),
        order_type="market",
        source="backtest",
    )

    live_signal = SignalRecord(
        timestamp=timestamp + timedelta(milliseconds=50),
        asset=test_asset,
        side="BUY",
        quantity=Decimal("120"),  # 20% difference (within 50% threshold)
        price=Decimal("50.00"),
        order_type="market",
        source="live",
    )

    validator.add_backtest_signal(backtest_signal)
    result = validator.add_live_signal(live_signal)

    assert result is not None
    matched_signal, alignment = result
    assert alignment == SignalAlignment.DIRECTION_MATCH


def test_magnitude_mismatch(validator, test_asset):
    """Test magnitude mismatch with large quantity difference."""
    timestamp = datetime.utcnow()

    backtest_signal = SignalRecord(
        timestamp=timestamp,
        asset=test_asset,
        side="BUY",
        quantity=Decimal("100"),
        price=Decimal("50.00"),
        order_type="market",
        source="backtest",
    )

    live_signal = SignalRecord(
        timestamp=timestamp + timedelta(milliseconds=50),
        asset=test_asset,
        side="BUY",
        quantity=Decimal("200"),  # 100% difference (>50% threshold)
        price=Decimal("50.00"),
        order_type="market",
        source="live",
    )

    validator.add_backtest_signal(backtest_signal)
    result = validator.add_live_signal(live_signal)

    assert result is not None
    matched_signal, alignment = result
    assert alignment == SignalAlignment.MAGNITUDE_MISMATCH


def test_missing_signal(validator, test_asset):
    """Test missing signal detection."""
    timestamp = datetime.utcnow()

    live_signal = SignalRecord(
        timestamp=timestamp,
        asset=test_asset,
        side="BUY",
        quantity=Decimal("100"),
        price=Decimal("50.00"),
        order_type="market",
        source="live",
    )

    # No backtest signal added - should be missing
    result = validator.add_live_signal(live_signal)

    assert result is None
    divergence_breakdown = validator.get_divergence_breakdown()
    assert divergence_breakdown[SignalAlignment.MISSING_SIGNAL] == 1


def test_match_rate_calculation(validator, test_asset):
    """Test signal match rate calculation."""
    base_timestamp = datetime.utcnow().replace(tzinfo=pytz.UTC)

    # Add 10 backtest signals
    for i in range(10):
        backtest_signal = SignalRecord(
            timestamp=base_timestamp + timedelta(seconds=i),
            asset=test_asset,
            side="BUY",
            quantity=Decimal("100"),
            price=Decimal("50.00"),
            order_type="market",
            source="backtest",
        )
        validator.add_backtest_signal(backtest_signal)

    # Add 8 matching live signals
    for i in range(8):
        live_signal = SignalRecord(
            timestamp=base_timestamp + timedelta(seconds=i, milliseconds=50),
            asset=test_asset,
            side="BUY",
            quantity=Decimal("100"),
            price=Decimal("50.00"),
            order_type="market",
            source="live",
        )
        validator.add_live_signal(live_signal)

    # Calculate match rate
    match_rate = validator.calculate_match_rate(window_minutes=60)

    # Should be 8/10 = 0.8 (80%)
    assert match_rate == Decimal("0.8")


def test_time_tolerance(validator, test_asset):
    """Test time tolerance boundary."""
    timestamp = datetime.utcnow()

    backtest_signal = SignalRecord(
        timestamp=timestamp,
        asset=test_asset,
        side="BUY",
        quantity=Decimal("100"),
        price=Decimal("50.00"),
        order_type="market",
        source="backtest",
    )

    # Signal within tolerance (100ms)
    live_signal_within = SignalRecord(
        timestamp=timestamp + timedelta(milliseconds=99),
        asset=test_asset,
        side="BUY",
        quantity=Decimal("100"),
        price=Decimal("50.00"),
        order_type="market",
        source="live",
    )

    # Signal outside tolerance (101ms)
    live_signal_outside = SignalRecord(
        timestamp=timestamp + timedelta(milliseconds=101),
        asset=test_asset,
        side="BUY",
        quantity=Decimal("100"),
        price=Decimal("50.00"),
        order_type="market",
        source="live",
    )

    validator.add_backtest_signal(backtest_signal)

    # Within tolerance should match
    result_within = validator.add_live_signal(live_signal_within)
    assert result_within is not None

    # Reset and test outside tolerance
    validator.reset()
    validator.add_backtest_signal(backtest_signal)

    # Outside tolerance should not match (or get TIME_MISMATCH)
    result_outside = validator.add_live_signal(live_signal_outside)
    # May be None or TIME_MISMATCH depending on implementation
    if result_outside:
        _, alignment = result_outside
        assert alignment == SignalAlignment.TIME_MISMATCH
