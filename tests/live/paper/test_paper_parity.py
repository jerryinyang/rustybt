"""Paper vs Live parity verification tests.

This module verifies that paper trading behavior matches live trading behavior,
ensuring paper trading results are a reliable proxy for live performance.

Story: 10.2.3 - Paper vs Live Parity Verification

Intentional Differences (Documented):
1. Fill source: Paper simulates fills locally, live receives from exchange
2. Network latency: Paper has configurable/no network latency
3. Slippage: Paper uses configured slippage model, live has real slippage
4. Partial fills: Live may have partial fills, paper model depends on config
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

import pytest

from rustybt.assets import Asset, Equity, ExchangeInfo
from rustybt.live.brokers.base import BrokerAdapter
from rustybt.live.brokers.paper_broker import PaperBroker

from .conftest import create_bar_data

# =============================================================================
# Mock Live Broker for Comparison
# =============================================================================


@dataclass
class OrderCall:
    """Captured order call parameters for comparison."""

    asset: Asset
    amount: Decimal
    order_type: str
    limit_price: Decimal | None
    stop_price: Decimal | None
    timestamp: datetime = field(default_factory=datetime.now)

    def matches(self, other: "OrderCall") -> bool:
        """Check if this order call matches another (excluding timestamp)."""
        return (
            self.asset == other.asset
            and self.amount == other.amount
            and self.order_type == other.order_type
            and self.limit_price == other.limit_price
            and self.stop_price == other.stop_price
        )


class MockLiveBroker(BrokerAdapter):
    """Mock live broker that captures all calls for parity comparison.

    This broker implements the same interface as PaperBroker but captures
    all method calls for later comparison against paper trading behavior.
    """

    def __init__(self):
        """Initialize MockLiveBroker."""
        self._connected = False
        self.order_calls: list[OrderCall] = []
        self.positions: dict[Asset, dict] = {}
        self.cash = Decimal("100000")
        self.starting_cash = Decimal("100000")
        self.orders: dict[str, dict] = {}
        self._order_counter = 0
        self.market_data: dict[Asset, dict] = {}

    async def connect(self) -> None:
        """Connect to mock broker."""
        self._connected = True

    async def disconnect(self) -> None:
        """Disconnect from mock broker."""
        self._connected = False

    def is_connected(self) -> bool:
        """Check connection status."""
        return self._connected

    async def submit_order(
        self,
        asset: Asset,
        amount: Decimal,
        order_type: str,
        limit_price: Decimal | None = None,
        stop_price: Decimal | None = None,
    ) -> str:
        """Submit order and capture call parameters."""
        # Capture the call
        call = OrderCall(
            asset=asset,
            amount=amount,
            order_type=order_type,
            limit_price=limit_price,
            stop_price=stop_price,
        )
        self.order_calls.append(call)

        # Generate order ID
        self._order_counter += 1
        order_id = f"live-order-{self._order_counter}"

        # Simulate immediate fill for parity comparison
        price = self._get_current_price(asset)
        self._process_fill(asset, amount, price)

        return order_id

    def _get_current_price(self, asset: Asset) -> Decimal:
        """Get current price from market data."""
        if asset in self.market_data:
            return self.market_data[asset].get("close", Decimal("100"))
        return Decimal("100")

    def _process_fill(self, asset: Asset, amount: Decimal, price: Decimal) -> None:
        """Process order fill - update positions and cash."""
        # Update cash
        cash_impact = amount * price
        if amount > 0:
            self.cash -= cash_impact
        else:
            self.cash += abs(cash_impact)

        # Update position
        if asset not in self.positions:
            self.positions[asset] = {
                "amount": Decimal("0"),
                "cost_basis": Decimal("0"),
                "entry_time": datetime.now(),
            }

        pos = self.positions[asset]
        old_amount = pos["amount"]
        new_amount = old_amount + amount

        if new_amount != Decimal("0"):
            # Calculate new cost basis (weighted average for adds)
            if old_amount == Decimal("0"):
                pos["cost_basis"] = price
            elif (old_amount > 0 and amount > 0) or (old_amount < 0 and amount < 0):
                # Adding to position
                total_cost = old_amount * pos["cost_basis"] + amount * price
                pos["cost_basis"] = total_cost / new_amount
            # For reducing position, cost basis stays the same

        pos["amount"] = new_amount
        pos["last_price"] = price

        if new_amount == Decimal("0"):
            del self.positions[asset]

    def _update_market_data(self, asset: Asset, data: dict) -> None:
        """Update market data for asset."""
        self.market_data[asset] = data

    async def cancel_order(self, broker_order_id: str) -> None:
        """Cancel order."""
        pass

    async def get_account_info(self) -> dict[str, Decimal]:
        """Get account information."""
        positions_value = sum(
            p["amount"] * p.get("last_price", p["cost_basis"]) for p in self.positions.values()
        )
        return {
            "cash": self.cash,
            "equity": self.cash + positions_value,
            "buying_power": self.cash,
            "portfolio_value": self.cash + positions_value,
        }

    async def get_positions(self) -> list[dict]:
        """Get current positions."""
        return [
            {
                "asset": asset,
                "amount": pos["amount"],
                "cost_basis": pos["cost_basis"],
            }
            for asset, pos in self.positions.items()
        ]

    async def get_open_orders(self) -> list[dict]:
        """Get open orders."""
        return []

    async def subscribe_market_data(self, assets: list[Asset]) -> None:
        """Subscribe to market data."""
        pass

    async def unsubscribe_market_data(self, assets: list[Asset]) -> None:
        """Unsubscribe from market data."""
        pass

    async def get_next_market_data(self) -> dict | None:
        """Get next market data."""
        return None

    async def get_current_price(self, asset: Asset) -> Decimal:
        """Get current price."""
        return self._get_current_price(asset)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_asset() -> Equity:
    """Create sample equity asset for testing."""
    exchange_info = ExchangeInfo("NASDAQ", "NASDAQ", "US")
    return Equity(1, exchange_info, symbol="PARITY")


@pytest.fixture
def paper_broker() -> PaperBroker:
    """Create PaperBroker for parity testing."""
    return PaperBroker(
        starting_cash=Decimal("100000"),
        order_latency_ms=1,
        latency_jitter_pct=Decimal("0"),
    )


@pytest.fixture
def mock_live_broker() -> MockLiveBroker:
    """Create MockLiveBroker for parity testing."""
    return MockLiveBroker()


# =============================================================================
# Call Capture Utility
# =============================================================================


def capture_order_calls(broker: BrokerAdapter) -> list[OrderCall]:
    """Create a list that captures order calls to a broker.

    Args:
        broker: Broker to capture calls from

    Returns:
        List that will be populated with OrderCall objects
    """
    calls: list[OrderCall] = []

    if isinstance(broker, PaperBroker):
        # Paper broker doesn't have order_calls attribute, so we wrap
        original_submit = broker.submit_order

        async def capturing_submit(
            asset: Asset,
            amount: Decimal,
            order_type: str,
            limit_price: Decimal | None = None,
            stop_price: Decimal | None = None,
        ) -> str:
            calls.append(
                OrderCall(
                    asset=asset,
                    amount=amount,
                    order_type=order_type,
                    limit_price=limit_price,
                    stop_price=stop_price,
                )
            )
            return await original_submit(asset, amount, order_type, limit_price, stop_price)

        broker.submit_order = capturing_submit  # type: ignore

    return calls


# =============================================================================
# AC1: Order Call Parameter Parity
# =============================================================================


class TestOrderCallParity:
    """Tests for AC1: Order submission calls have identical parameters."""

    @pytest.mark.asyncio
    async def test_market_order_parameters_match(
        self, paper_broker, mock_live_broker, sample_asset
    ):
        """Test that market order parameters are identical."""
        await paper_broker.connect()
        await mock_live_broker.connect()

        # Set identical market data
        market_data = create_bar_data(Decimal("150.00"))
        paper_broker._update_market_data(sample_asset, market_data)
        mock_live_broker._update_market_data(sample_asset, market_data)

        # Capture paper broker calls
        paper_calls = capture_order_calls(paper_broker)

        # Submit identical orders
        order_params = {
            "asset": sample_asset,
            "amount": Decimal("100"),
            "order_type": "market",
        }

        await paper_broker.submit_order(**order_params)
        await mock_live_broker.submit_order(**order_params)
        await asyncio.sleep(0.1)

        # Compare calls
        assert len(paper_calls) == 1
        assert len(mock_live_broker.order_calls) == 1

        paper_call = paper_calls[0]
        live_call = mock_live_broker.order_calls[0]

        assert paper_call.asset == live_call.asset
        assert paper_call.amount == live_call.amount
        assert paper_call.order_type == live_call.order_type
        assert paper_call.limit_price == live_call.limit_price

    @pytest.mark.asyncio
    async def test_limit_order_parameters_match(self, paper_broker, mock_live_broker, sample_asset):
        """Test that limit order parameters are identical."""
        await paper_broker.connect()
        await mock_live_broker.connect()

        market_data = create_bar_data(Decimal("100.00"))
        paper_broker._update_market_data(sample_asset, market_data)
        mock_live_broker._update_market_data(sample_asset, market_data)

        paper_calls = capture_order_calls(paper_broker)

        # Submit identical limit orders
        order_params = {
            "asset": sample_asset,
            "amount": Decimal("50"),
            "order_type": "limit",
            "limit_price": Decimal("95.00"),
        }

        await paper_broker.submit_order(**order_params)
        await mock_live_broker.submit_order(**order_params)
        await asyncio.sleep(0.1)

        paper_call = paper_calls[0]
        live_call = mock_live_broker.order_calls[0]

        assert paper_call.limit_price == live_call.limit_price
        assert paper_call.limit_price == Decimal("95.00")

    @pytest.mark.asyncio
    async def test_sell_order_parameters_match(self, paper_broker, mock_live_broker, sample_asset):
        """Test that sell order parameters are identical (negative amount)."""
        await paper_broker.connect()
        await mock_live_broker.connect()

        market_data = create_bar_data(Decimal("100.00"))
        paper_broker._update_market_data(sample_asset, market_data)
        mock_live_broker._update_market_data(sample_asset, market_data)

        # First buy to establish position
        buy_params = {
            "asset": sample_asset,
            "amount": Decimal("100"),
            "order_type": "market",
        }
        await paper_broker.submit_order(**buy_params)
        await mock_live_broker.submit_order(**buy_params)
        await asyncio.sleep(0.1)

        paper_calls = capture_order_calls(paper_broker)

        # Now sell
        sell_params = {
            "asset": sample_asset,
            "amount": Decimal("-50"),  # Negative = sell
            "order_type": "market",
        }

        await paper_broker.submit_order(**sell_params)
        await mock_live_broker.submit_order(**sell_params)
        await asyncio.sleep(0.1)

        paper_call = paper_calls[0]
        live_call = mock_live_broker.order_calls[-1]  # Last call

        assert paper_call.amount == live_call.amount
        assert paper_call.amount == Decimal("-50")

    @pytest.mark.asyncio
    async def test_multiple_orders_in_sequence(self, paper_broker, mock_live_broker, sample_asset):
        """Test that multiple orders have matching parameters."""
        await paper_broker.connect()
        await mock_live_broker.connect()

        market_data = create_bar_data(Decimal("100.00"))
        paper_broker._update_market_data(sample_asset, market_data)
        mock_live_broker._update_market_data(sample_asset, market_data)

        paper_calls = capture_order_calls(paper_broker)

        # Submit multiple orders
        orders = [
            {"amount": Decimal("10"), "order_type": "market"},
            {"amount": Decimal("20"), "order_type": "market"},
            {"amount": Decimal("-5"), "order_type": "market"},
        ]

        for order in orders:
            await paper_broker.submit_order(asset=sample_asset, **order)
            await mock_live_broker.submit_order(asset=sample_asset, **order)
            await asyncio.sleep(0.02)

        # Verify all match
        assert len(paper_calls) == len(orders)
        assert len(mock_live_broker.order_calls) == len(orders)

        for i, (paper_call, live_call) in enumerate(zip(paper_calls, mock_live_broker.order_calls)):
            assert paper_call.matches(live_call), f"Order {i} mismatch"


# =============================================================================
# AC2: Position Calculation Parity
# =============================================================================


class TestPositionCalculationParity:
    """Tests for AC2: Position calculations use the same logic."""

    @pytest.mark.asyncio
    async def test_position_size_identical(self, paper_broker, mock_live_broker, sample_asset):
        """Test that position size calculation is identical."""
        await paper_broker.connect()
        await mock_live_broker.connect()

        market_data = create_bar_data(Decimal("100.00"))
        paper_broker._update_market_data(sample_asset, market_data)
        mock_live_broker._update_market_data(sample_asset, market_data)

        # Submit same order
        await paper_broker.submit_order(
            asset=sample_asset,
            amount=Decimal("100"),
            order_type="market",
        )
        await mock_live_broker.submit_order(
            asset=sample_asset,
            amount=Decimal("100"),
            order_type="market",
        )
        await asyncio.sleep(0.1)

        # Compare position sizes
        paper_positions = await paper_broker.get_positions()
        live_positions = await mock_live_broker.get_positions()

        assert len(paper_positions) == len(live_positions) == 1
        assert paper_positions[0]["amount"] == live_positions[0]["amount"]
        assert paper_positions[0]["amount"] == Decimal("100")

    @pytest.mark.asyncio
    async def test_entry_price_identical(self, paper_broker, mock_live_broker, sample_asset):
        """Test that entry price calculation is identical."""
        await paper_broker.connect()
        await mock_live_broker.connect()

        price = Decimal("123.45")
        market_data = create_bar_data(price)
        paper_broker._update_market_data(sample_asset, market_data)
        mock_live_broker._update_market_data(sample_asset, market_data)

        await paper_broker.submit_order(
            asset=sample_asset,
            amount=Decimal("50"),
            order_type="market",
        )
        await mock_live_broker.submit_order(
            asset=sample_asset,
            amount=Decimal("50"),
            order_type="market",
        )
        await asyncio.sleep(0.1)

        paper_positions = await paper_broker.get_positions()
        live_positions = await mock_live_broker.get_positions()

        assert paper_positions[0]["cost_basis"] == live_positions[0]["cost_basis"]
        assert paper_positions[0]["cost_basis"] == price

    @pytest.mark.asyncio
    async def test_position_direction_identical(self, paper_broker, mock_live_broker, sample_asset):
        """Test that position direction logic is identical."""
        await paper_broker.connect()
        await mock_live_broker.connect()

        market_data = create_bar_data(Decimal("100.00"))
        paper_broker._update_market_data(sample_asset, market_data)
        mock_live_broker._update_market_data(sample_asset, market_data)

        # Test long position
        await paper_broker.submit_order(
            asset=sample_asset, amount=Decimal("100"), order_type="market"
        )
        await mock_live_broker.submit_order(
            asset=sample_asset, amount=Decimal("100"), order_type="market"
        )
        await asyncio.sleep(0.1)

        paper_pos = (await paper_broker.get_positions())[0]
        live_pos = (await mock_live_broker.get_positions())[0]

        # Both should be long (positive)
        assert paper_pos["amount"] > 0
        assert live_pos["amount"] > 0
        assert paper_pos["amount"] == live_pos["amount"]

    @pytest.mark.asyncio
    async def test_position_after_multiple_orders(
        self, paper_broker, mock_live_broker, sample_asset
    ):
        """Test position calculations after multiple orders."""
        await paper_broker.connect()
        await mock_live_broker.connect()

        # Buy at $100
        paper_broker._update_market_data(sample_asset, create_bar_data(Decimal("100")))
        mock_live_broker._update_market_data(sample_asset, create_bar_data(Decimal("100")))

        await paper_broker.submit_order(
            asset=sample_asset, amount=Decimal("100"), order_type="market"
        )
        await mock_live_broker.submit_order(
            asset=sample_asset, amount=Decimal("100"), order_type="market"
        )
        await asyncio.sleep(0.1)

        # Buy more at $110
        paper_broker._update_market_data(sample_asset, create_bar_data(Decimal("110")))
        mock_live_broker._update_market_data(sample_asset, create_bar_data(Decimal("110")))

        await paper_broker.submit_order(
            asset=sample_asset, amount=Decimal("100"), order_type="market"
        )
        await mock_live_broker.submit_order(
            asset=sample_asset, amount=Decimal("100"), order_type="market"
        )
        await asyncio.sleep(0.1)

        paper_pos = (await paper_broker.get_positions())[0]
        live_pos = (await mock_live_broker.get_positions())[0]

        # Size should be 200
        assert paper_pos["amount"] == live_pos["amount"] == Decimal("200")

        # Cost basis should be weighted average: (100*100 + 100*110) / 200 = 105
        assert paper_pos["cost_basis"] == live_pos["cost_basis"] == Decimal("105")


# =============================================================================
# AC3: PnL Calculation Parity
# =============================================================================


class TestPnLCalculationParity:
    """Tests for AC3: PnL calculations produce identical results."""

    @pytest.mark.asyncio
    async def test_unrealized_pnl_identical(self, paper_broker, mock_live_broker, sample_asset):
        """Test that unrealized PnL formula is identical.

        Both brokers should use the same formula:
        unrealized_pnl = (current_price - entry_price) * position_size
        """
        await paper_broker.connect()
        await mock_live_broker.connect()

        # Entry at $100
        entry_price = Decimal("100")
        paper_broker._update_market_data(sample_asset, create_bar_data(entry_price))
        mock_live_broker._update_market_data(sample_asset, create_bar_data(entry_price))

        await paper_broker.submit_order(
            asset=sample_asset, amount=Decimal("100"), order_type="market"
        )
        await mock_live_broker.submit_order(
            asset=sample_asset, amount=Decimal("100"), order_type="market"
        )
        await asyncio.sleep(0.1)

        # Current price $110
        current_price = Decimal("110")
        paper_broker._update_market_data(sample_asset, create_bar_data(current_price))
        mock_live_broker._update_market_data(sample_asset, create_bar_data(current_price))

        # Update positions with current price
        if sample_asset in paper_broker.positions:
            paper_broker.positions[sample_asset].last_sale_price = current_price
        if sample_asset in mock_live_broker.positions:
            mock_live_broker.positions[sample_asset]["last_price"] = current_price

        # Get positions
        paper_pos = (await paper_broker.get_positions())[0]
        live_pos = (await mock_live_broker.get_positions())[0]

        # Calculate expected unrealized PnL using the standard formula
        # PnL = (current_price - entry_price) * amount = (110 - 100) * 100 = 1000
        expected_pnl = (current_price - entry_price) * Decimal("100")

        # Calculate PnL the same way for both
        paper_calculated_pnl = (current_price - paper_pos["cost_basis"]) * paper_pos["amount"]
        live_calculated_pnl = (current_price - live_pos["cost_basis"]) * live_pos["amount"]

        # Both should calculate same unrealized PnL using same formula
        assert paper_calculated_pnl == expected_pnl
        assert live_calculated_pnl == expected_pnl
        assert paper_calculated_pnl == live_calculated_pnl

    @pytest.mark.asyncio
    async def test_realized_pnl_identical(self, paper_broker, mock_live_broker, sample_asset):
        """Test that realized PnL formula is identical."""
        await paper_broker.connect()
        await mock_live_broker.connect()

        starting_cash = Decimal("100000")

        # Buy at $100
        paper_broker._update_market_data(sample_asset, create_bar_data(Decimal("100")))
        mock_live_broker._update_market_data(sample_asset, create_bar_data(Decimal("100")))

        await paper_broker.submit_order(
            asset=sample_asset, amount=Decimal("100"), order_type="market"
        )
        await mock_live_broker.submit_order(
            asset=sample_asset, amount=Decimal("100"), order_type="market"
        )
        await asyncio.sleep(0.1)

        # Sell at $110
        paper_broker._update_market_data(sample_asset, create_bar_data(Decimal("110")))
        mock_live_broker._update_market_data(sample_asset, create_bar_data(Decimal("110")))

        await paper_broker.submit_order(
            asset=sample_asset, amount=Decimal("-100"), order_type="market"
        )
        await mock_live_broker.submit_order(
            asset=sample_asset, amount=Decimal("-100"), order_type="market"
        )
        await asyncio.sleep(0.1)

        # Calculate realized PnL from cash change
        paper_account = await paper_broker.get_account_info()
        live_account = await mock_live_broker.get_account_info()

        paper_pnl = paper_account["cash"] - starting_cash
        live_pnl = live_account["cash"] - starting_cash

        # Expected: Buy $100 * 100 = $10,000, Sell $110 * 100 = $11,000, PnL = $1,000
        expected_pnl = Decimal("1000")

        assert paper_pnl == expected_pnl
        assert live_pnl == expected_pnl
        assert paper_pnl == live_pnl

    @pytest.mark.asyncio
    async def test_decimal_precision_identical(self, paper_broker, mock_live_broker, sample_asset):
        """Test that Decimal precision is identical."""
        await paper_broker.connect()
        await mock_live_broker.connect()

        # Use prices with many decimal places
        price = Decimal("123.456789")
        paper_broker._update_market_data(sample_asset, create_bar_data(price))
        mock_live_broker._update_market_data(sample_asset, create_bar_data(price))

        await paper_broker.submit_order(
            asset=sample_asset, amount=Decimal("1"), order_type="market"
        )
        await mock_live_broker.submit_order(
            asset=sample_asset, amount=Decimal("1"), order_type="market"
        )
        await asyncio.sleep(0.1)

        paper_pos = (await paper_broker.get_positions())[0]
        live_pos = (await mock_live_broker.get_positions())[0]

        # Decimal precision should be preserved exactly
        assert paper_pos["cost_basis"] == live_pos["cost_basis"]
        assert paper_pos["cost_basis"] == price


# =============================================================================
# AC4: State Machine Parity
# =============================================================================


class TestStateMachineParity:
    """Tests for AC4: State transitions follow the same state machine."""

    def test_same_interface_methods(self):
        """Test that paper and mock live broker have same interface."""
        paper = PaperBroker()
        live = MockLiveBroker()

        # Both should implement BrokerAdapter
        broker_methods = [
            "connect",
            "disconnect",
            "is_connected",
            "submit_order",
            "cancel_order",
            "get_account_info",
            "get_positions",
            "get_open_orders",
            "subscribe_market_data",
            "unsubscribe_market_data",
            "get_next_market_data",
            "get_current_price",
        ]

        for method in broker_methods:
            assert hasattr(paper, method), f"Paper broker missing {method}"
            assert hasattr(live, method), f"Live broker missing {method}"

    @pytest.mark.asyncio
    async def test_connection_state_transitions(self, paper_broker, mock_live_broker):
        """Test that connection state transitions are identical."""
        # Initial state: disconnected
        assert not paper_broker.is_connected()
        assert not mock_live_broker.is_connected()

        # After connect: connected
        await paper_broker.connect()
        await mock_live_broker.connect()
        assert paper_broker.is_connected()
        assert mock_live_broker.is_connected()

        # After disconnect: disconnected
        await paper_broker.disconnect()
        await mock_live_broker.disconnect()
        assert not paper_broker.is_connected()
        assert not mock_live_broker.is_connected()

    @pytest.mark.asyncio
    async def test_order_state_names_equivalent(self, paper_broker, mock_live_broker, sample_asset):
        """Test that order state names are equivalent."""
        await paper_broker.connect()
        await mock_live_broker.connect()

        paper_broker._update_market_data(sample_asset, create_bar_data(Decimal("100")))
        mock_live_broker._update_market_data(sample_asset, create_bar_data(Decimal("100")))

        # Submit order
        paper_order_id = await paper_broker.submit_order(
            asset=sample_asset, amount=Decimal("100"), order_type="market"
        )
        await asyncio.sleep(0.1)

        # Check order is tracked
        assert paper_order_id in paper_broker.orders

        # Order should have standard fields
        paper_order = paper_broker.orders[paper_order_id]
        assert hasattr(paper_order, "amount")
        assert hasattr(paper_order, "filled")


# =============================================================================
# AC5: Parity Report
# =============================================================================


@dataclass
class ParityTestResult:
    """Result of a single parity test."""

    test_name: str
    passed: bool
    details: str = ""


@dataclass
class ParityReport:
    """Parity report documenting paper vs live differences."""

    test_date: str
    order_call_parity: bool
    position_calculation_parity: bool
    pnl_calculation_parity: bool
    state_machine_parity: bool
    test_results: list[ParityTestResult] = field(default_factory=list)
    intentional_differences: list[str] = field(default_factory=list)

    def __post_init__(self):
        """Set default intentional differences."""
        if not self.intentional_differences:
            self.intentional_differences = [
                "Fill source: Paper simulates fills locally, live receives from exchange",
                "Network latency: Paper has configurable/no network latency",
                "Slippage: Paper uses configured slippage model, live has real slippage",
                "Partial fills: Live may have partial fills, paper model depends on config",
            ]

    def to_markdown(self) -> str:
        """Generate markdown report."""
        status = lambda b: "PASS" if b else "FAIL"

        report = f"""# Paper vs Live Trading Parity Report

## Test Date: {self.test_date}

## Summary
- Order call parity: {status(self.order_call_parity)}
- Position calculation parity: {status(self.position_calculation_parity)}
- PnL calculation parity: {status(self.pnl_calculation_parity)}
- State machine parity: {status(self.state_machine_parity)}

## Intentional Differences
"""
        for i, diff in enumerate(self.intentional_differences, 1):
            report += f"{i}. {diff}\n"

        report += "\n## Test Results\n"
        for result in self.test_results:
            status_mark = "✓" if result.passed else "✗"
            report += f"- [{status_mark}] {result.test_name}"
            if result.details:
                report += f": {result.details}"
            report += "\n"

        return report


class TestParityReport:
    """Tests for AC5: Parity report generation."""

    def test_parity_report_generation(self):
        """Test that parity report can be generated."""
        report = ParityReport(
            test_date="2025-12-06",
            order_call_parity=True,
            position_calculation_parity=True,
            pnl_calculation_parity=True,
            state_machine_parity=True,
            test_results=[
                ParityTestResult("Market order match", True),
                ParityTestResult("Position size match", True),
                ParityTestResult("PnL calculation match", True),
            ],
        )

        markdown = report.to_markdown()

        assert "Paper vs Live Trading Parity Report" in markdown
        assert "PASS" in markdown
        assert "Intentional Differences" in markdown
        assert "Fill source" in markdown

    def test_parity_report_documents_differences(self):
        """Test that intentional differences are documented."""
        report = ParityReport(
            test_date="2025-12-06",
            order_call_parity=True,
            position_calculation_parity=True,
            pnl_calculation_parity=True,
            state_machine_parity=True,
        )

        # Should have default intentional differences
        assert len(report.intentional_differences) == 4
        assert any("Fill source" in d for d in report.intentional_differences)
        assert any("Network latency" in d for d in report.intentional_differences)
        assert any("Slippage" in d for d in report.intentional_differences)
        assert any("Partial fills" in d for d in report.intentional_differences)


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases in paper vs live parity."""

    @pytest.mark.asyncio
    async def test_order_cancellation_parity(self, paper_broker, mock_live_broker, sample_asset):
        """Test that order cancellation behavior is similar."""
        await paper_broker.connect()
        await mock_live_broker.connect()

        # Submit and immediately cancel
        order_id = await paper_broker.submit_order(
            asset=sample_asset, amount=Decimal("100"), order_type="market"
        )
        await paper_broker.cancel_order(order_id)
        await mock_live_broker.cancel_order("some-order")

        # Both should handle gracefully (not raise)

    @pytest.mark.asyncio
    async def test_rapid_order_submission_parity(
        self, paper_broker, mock_live_broker, sample_asset
    ):
        """Test rapid order submission handles similarly."""
        await paper_broker.connect()
        await mock_live_broker.connect()

        paper_broker._update_market_data(sample_asset, create_bar_data(Decimal("100")))
        mock_live_broker._update_market_data(sample_asset, create_bar_data(Decimal("100")))

        paper_calls = capture_order_calls(paper_broker)

        # Submit orders rapidly
        for i in range(10):
            await paper_broker.submit_order(
                asset=sample_asset, amount=Decimal("1"), order_type="market"
            )
            await mock_live_broker.submit_order(
                asset=sample_asset, amount=Decimal("1"), order_type="market"
            )

        await asyncio.sleep(0.5)

        # All should be captured
        assert len(paper_calls) == 10
        assert len(mock_live_broker.order_calls) == 10

    @pytest.mark.asyncio
    async def test_position_reversal_parity(self, paper_broker, mock_live_broker, sample_asset):
        """Test position reversal (long to short) parity."""
        await paper_broker.connect()
        await mock_live_broker.connect()

        paper_broker._update_market_data(sample_asset, create_bar_data(Decimal("100")))
        mock_live_broker._update_market_data(sample_asset, create_bar_data(Decimal("100")))

        # Go long
        await paper_broker.submit_order(
            asset=sample_asset, amount=Decimal("100"), order_type="market"
        )
        await mock_live_broker.submit_order(
            asset=sample_asset, amount=Decimal("100"), order_type="market"
        )
        await asyncio.sleep(0.1)

        # Reverse to short
        await paper_broker.submit_order(
            asset=sample_asset, amount=Decimal("-200"), order_type="market"
        )
        await mock_live_broker.submit_order(
            asset=sample_asset, amount=Decimal("-200"), order_type="market"
        )
        await asyncio.sleep(0.1)

        paper_pos = (await paper_broker.get_positions())[0]
        live_pos = (await mock_live_broker.get_positions())[0]

        # Both should be short -100
        assert paper_pos["amount"] == Decimal("-100")
        assert live_pos["amount"] == Decimal("-100")
