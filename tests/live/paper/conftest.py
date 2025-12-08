"""Pytest fixtures for paper trading tests.

This module provides shared fixtures for paper trading execution tests,
including deterministic test strategies, configurable fill models, and
pre-configured paper brokers.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Literal

import pytest

from rustybt.assets import Equity, ExchangeInfo
from rustybt.finance.decimal.commission import NoCommission, PerShareCommission
from rustybt.finance.decimal.slippage import FixedBasisPointsSlippage, NoSlippage
from rustybt.live.brokers.paper_broker import PaperBroker

# =============================================================================
# Test Strategy Classes
# =============================================================================


class SignalType(str, Enum):
    """Trading signal types."""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class SignalPattern:
    """A signal to be generated at a specific bar index.

    Attributes:
        bar_index: The bar number at which to generate the signal
        signal_type: The type of signal (BUY, SELL, HOLD)
        amount: Optional amount for the order (default: 1.0)
    """

    bar_index: int
    signal_type: SignalType
    amount: Decimal = Decimal("1.0")


class DeterministicStrategy:
    """Deterministic test strategy with known signal patterns.

    This strategy generates predictable signals at specific bar indices,
    making it ideal for testing paper trading execution behavior.

    Example:
        >>> strategy = DeterministicStrategy([
        ...     SignalPattern(5, SignalType.BUY, Decimal("100")),
        ...     SignalPattern(10, SignalType.SELL, Decimal("100")),
        ... ])
        >>> signal = strategy.on_bar(5, {"close": Decimal("150.00")})
        >>> signal  # Returns SignalType.BUY
    """

    def __init__(self, signal_patterns: list[SignalPattern]) -> None:
        """Initialize DeterministicStrategy.

        Args:
            signal_patterns: List of SignalPattern objects defining when
                            signals should be generated
        """
        self.signal_patterns = signal_patterns
        self._pattern_map: dict[int, SignalPattern] = {p.bar_index: p for p in signal_patterns}
        self.bar_count = 0
        self.signals_generated: list[tuple[int, SignalType]] = []

    def on_bar(self, bar_index: int, bar_data: dict) -> SignalPattern | None:
        """Process a bar and potentially generate a signal.

        Args:
            bar_index: Current bar number
            bar_data: Bar data dict with keys: open, high, low, close, volume

        Returns:
            SignalPattern if a signal should be generated at this bar,
            None otherwise
        """
        self.bar_count += 1

        if bar_index in self._pattern_map:
            pattern = self._pattern_map[bar_index]
            self.signals_generated.append((bar_index, pattern.signal_type))
            return pattern

        return None

    def reset(self) -> None:
        """Reset strategy state for reuse."""
        self.bar_count = 0
        self.signals_generated.clear()


class ImmediateFillStrategy(DeterministicStrategy):
    """Test strategy that generates signals for immediate fill testing.

    Generates a BUY signal at bar 1 and a SELL signal at bar 2.
    """

    def __init__(self, amount: Decimal = Decimal("100")) -> None:
        super().__init__(
            [
                SignalPattern(1, SignalType.BUY, amount),
                SignalPattern(2, SignalType.SELL, amount),
            ]
        )


class MultiPositionStrategy(DeterministicStrategy):
    """Test strategy for testing multiple concurrent positions.

    Generates multiple BUY signals before any SELL signals.
    """

    def __init__(self, num_positions: int = 3, amount: Decimal = Decimal("100")) -> None:
        patterns = []
        # Buy signals at bars 1, 2, 3
        for i in range(num_positions):
            patterns.append(SignalPattern(i + 1, SignalType.BUY, amount))
        # Sell signals at bars num_positions+1, num_positions+2, ...
        for i in range(num_positions):
            patterns.append(SignalPattern(num_positions + i + 1, SignalType.SELL, amount))
        super().__init__(patterns)


# =============================================================================
# Fill Model Configuration
# =============================================================================


@dataclass
class FillModelConfig:
    """Configuration for fill model behavior.

    Attributes:
        model: Fill model type ("immediate" or "delayed")
        delay_ms: Fill delay in milliseconds (only for delayed model)
        partial_fill_probability: Future enhancement for partial fills
    """

    model: Literal["immediate", "delayed"] = "immediate"
    delay_ms: int = 100
    partial_fill_probability: float = 0.0


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_equity() -> Equity:
    """Create a sample equity asset for testing."""
    exchange_info = ExchangeInfo("NASDAQ", "NASDAQ", "US")
    return Equity(1, exchange_info, symbol="TEST")


@pytest.fixture
def sample_crypto_perp() -> Equity:
    """Create a sample crypto perpetual asset for testing.

    Note: Using Equity as a stand-in since the system may not have
    dedicated crypto asset types.
    """
    exchange_info = ExchangeInfo("CRYPTO", "FTX", "US")
    return Equity(2, exchange_info, symbol="BTC-PERP")


@pytest.fixture
def paper_broker_immediate() -> PaperBroker:
    """Create PaperBroker with immediate fill model (minimal latency)."""
    return PaperBroker(
        starting_cash=Decimal("100000"),
        commission_model=NoCommission(),
        slippage_model=NoSlippage(),
        order_latency_ms=1,  # Minimal latency for immediate fills
        latency_jitter_pct=Decimal("0"),  # No jitter
    )


@pytest.fixture
def paper_broker_delayed() -> PaperBroker:
    """Create PaperBroker with delayed fill model (100ms default)."""
    return PaperBroker(
        starting_cash=Decimal("100000"),
        commission_model=NoCommission(),
        slippage_model=NoSlippage(),
        order_latency_ms=100,
        latency_jitter_pct=Decimal("0.20"),
    )


@pytest.fixture
def paper_broker_with_costs() -> PaperBroker:
    """Create PaperBroker with realistic commission and slippage."""
    return PaperBroker(
        starting_cash=Decimal("100000"),
        commission_model=PerShareCommission(rate=Decimal("0.005"), minimum=Decimal("1.00")),
        slippage_model=FixedBasisPointsSlippage(basis_points=Decimal("5")),
        order_latency_ms=50,
    )


@pytest.fixture
def test_strategy_buy_sell() -> DeterministicStrategy:
    """Create a simple buy-then-sell test strategy."""
    return DeterministicStrategy(
        [
            SignalPattern(1, SignalType.BUY, Decimal("100")),
            SignalPattern(3, SignalType.SELL, Decimal("100")),
        ]
    )


@pytest.fixture
def test_strategy_long_profitable() -> DeterministicStrategy:
    """Strategy for long entry with price up, then exit (profit scenario)."""
    return DeterministicStrategy(
        [
            SignalPattern(1, SignalType.BUY, Decimal("100")),
            SignalPattern(5, SignalType.SELL, Decimal("100")),
        ]
    )


@pytest.fixture
def test_strategy_long_loss() -> DeterministicStrategy:
    """Strategy for long entry with price down, then exit (loss scenario)."""
    return DeterministicStrategy(
        [
            SignalPattern(1, SignalType.BUY, Decimal("100")),
            SignalPattern(5, SignalType.SELL, Decimal("100")),
        ]
    )


@pytest.fixture
def test_strategy_short_profitable() -> DeterministicStrategy:
    """Strategy for short entry with price down, then exit (profit scenario)."""
    return DeterministicStrategy(
        [
            SignalPattern(1, SignalType.SELL, Decimal("100")),
            SignalPattern(5, SignalType.BUY, Decimal("100")),
        ]
    )


@pytest.fixture
def test_strategy_short_loss() -> DeterministicStrategy:
    """Strategy for short entry with price up, then exit (loss scenario)."""
    return DeterministicStrategy(
        [
            SignalPattern(1, SignalType.SELL, Decimal("100")),
            SignalPattern(5, SignalType.BUY, Decimal("100")),
        ]
    )


# =============================================================================
# Helper Functions for Tests
# =============================================================================


def create_bar_data(
    close: Decimal,
    volume: Decimal = Decimal("1000000"),
    open_price: Decimal | None = None,
    high: Decimal | None = None,
    low: Decimal | None = None,
) -> dict:
    """Create a bar data dictionary for testing.

    Args:
        close: Closing price
        volume: Bar volume
        open_price: Opening price (defaults to close)
        high: High price (defaults to close)
        low: Low price (defaults to close)

    Returns:
        Dict with OHLCV data and timestamp
    """
    return {
        "open": open_price or close,
        "high": high or close,
        "low": low or close,
        "close": close,
        "volume": volume,
        "timestamp": datetime.now(),
    }


async def execute_strategy_on_broker(
    broker: PaperBroker,
    strategy: DeterministicStrategy,
    asset,
    price_series: list[Decimal],
    volume: Decimal = Decimal("1000000"),
) -> dict:
    """Execute a test strategy on a paper broker through a price series.

    Args:
        broker: The paper broker to use
        strategy: The test strategy with signal patterns
        asset: The asset to trade
        price_series: List of prices, one per bar
        volume: Volume per bar

    Returns:
        Dict with execution results:
        - orders: List of order IDs
        - fills: List of fill events
        - final_cash: Final cash balance
        - final_positions: Final positions
        - signals_generated: List of (bar_index, signal_type) tuples
    """
    await broker.connect()

    orders = []
    fills = []

    for bar_index, price in enumerate(price_series):
        # Update market data
        bar_data = create_bar_data(price, volume)
        broker._update_market_data(asset, bar_data)

        # Check for signal
        signal = strategy.on_bar(bar_index, bar_data)
        if signal:
            # Submit order based on signal
            if signal.signal_type == SignalType.BUY:
                order_id = await broker.submit_order(
                    asset=asset,
                    amount=signal.amount,
                    order_type="market",
                )
            elif signal.signal_type == SignalType.SELL:
                order_id = await broker.submit_order(
                    asset=asset,
                    amount=-signal.amount,
                    order_type="market",
                )
            else:
                continue

            orders.append(order_id)

        # Allow time for order processing
        await asyncio.sleep(0.05)

    # Wait for all orders to complete
    await asyncio.sleep(0.2)

    # Collect fill events
    while not broker.fill_events.empty():
        try:
            fill = broker.fill_events.get_nowait()
            fills.append(fill)
        except asyncio.QueueEmpty:
            break

    return {
        "orders": orders,
        "fills": fills,
        "final_cash": broker.cash,
        "final_positions": await broker.get_positions(),
        "signals_generated": strategy.signals_generated.copy(),
        "transactions": broker.transactions.copy(),
    }


@pytest.fixture
def execute_strategy():
    """Provide the execute_strategy_on_broker helper as a fixture."""
    return execute_strategy_on_broker
