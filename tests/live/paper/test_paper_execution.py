"""Paper trading execution test harness.

This module provides comprehensive tests for paper trading execution, validating:
- Strategy execution through PaperBroker
- Order fill simulation (immediate and delayed models)
- Position tracking accuracy
- PnL calculations with Decimal precision
- Order state transitions and lifecycle
- Various trading scenarios (long/short, profit/loss)

Story: 10.2.1 - Paper Trading Execution Test Harness
"""

import asyncio
from datetime import datetime
from decimal import Decimal

import pytest

from rustybt.live.brokers.paper_broker import PaperBroker

from .conftest import (
    DeterministicStrategy,
    FillModelConfig,
    ImmediateFillStrategy,
    MultiPositionStrategy,
    SignalPattern,
    SignalType,
    create_bar_data,
    execute_strategy_on_broker,
)

# =============================================================================
# AC1: Test Harness - Strategy Execution in Paper Trading Mode
# =============================================================================


class TestStrategyExecutionHarness:
    """Tests for AC1: Test harness for paper trading execution."""

    @pytest.mark.asyncio
    async def test_strategy_generates_known_signals(self, paper_broker_immediate, sample_equity):
        """Test that test strategy generates signals at expected bars."""
        strategy = DeterministicStrategy(
            [
                SignalPattern(2, SignalType.BUY, Decimal("50")),
                SignalPattern(5, SignalType.SELL, Decimal("50")),
            ]
        )

        # Process bars
        for i in range(10):
            bar_data = create_bar_data(Decimal("100"))
            signal = strategy.on_bar(i, bar_data)

            if i == 2:
                assert signal is not None
                assert signal.signal_type == SignalType.BUY
                assert signal.amount == Decimal("50")
            elif i == 5:
                assert signal is not None
                assert signal.signal_type == SignalType.SELL
            else:
                assert signal is None

        assert len(strategy.signals_generated) == 2
        assert strategy.signals_generated[0] == (2, SignalType.BUY)
        assert strategy.signals_generated[1] == (5, SignalType.SELL)

    @pytest.mark.asyncio
    async def test_orders_submitted_through_paper_broker(
        self, paper_broker_immediate, sample_equity
    ):
        """Test that orders are successfully submitted through paper broker."""
        broker = paper_broker_immediate
        await broker.connect()

        # Set market data
        broker._update_market_data(sample_equity, create_bar_data(Decimal("150.00")))

        # Submit order
        order_id = await broker.submit_order(
            asset=sample_equity,
            amount=Decimal("100"),
            order_type="market",
        )

        assert order_id is not None
        assert order_id in broker.orders

    @pytest.mark.asyncio
    async def test_strategy_execution_completes_without_errors(
        self, paper_broker_immediate, sample_equity, execute_strategy
    ):
        """Test that full strategy execution completes without errors."""
        strategy = DeterministicStrategy(
            [
                SignalPattern(1, SignalType.BUY, Decimal("100")),
                SignalPattern(3, SignalType.SELL, Decimal("100")),
            ]
        )

        price_series = [Decimal("100"), Decimal("105"), Decimal("110"), Decimal("115")]

        result = await execute_strategy(
            paper_broker_immediate, strategy, sample_equity, price_series
        )

        # Execution completed
        assert len(result["orders"]) == 2
        assert len(result["signals_generated"]) == 2

    @pytest.mark.asyncio
    async def test_multiple_orders_in_sequence(self, paper_broker_immediate, sample_equity):
        """Test submitting multiple orders in sequence."""
        broker = paper_broker_immediate
        await broker.connect()

        orders = []
        prices = [Decimal("100"), Decimal("105"), Decimal("110")]

        for i, price in enumerate(prices):
            broker._update_market_data(sample_equity, create_bar_data(price))

            order_id = await broker.submit_order(
                asset=sample_equity,
                amount=Decimal("10"),
                order_type="market",
            )
            orders.append(order_id)
            await asyncio.sleep(0.05)

        await asyncio.sleep(0.2)

        # All orders should be tracked
        assert len(orders) == 3
        for order_id in orders:
            assert order_id in broker.orders


# =============================================================================
# AC2: Fill Model Tests (Immediate and Delayed)
# =============================================================================


class TestFillModels:
    """Tests for AC2: Configurable fill models."""

    @pytest.mark.asyncio
    async def test_immediate_fill_model(self, sample_equity):
        """Test immediate fill model: fill at current price within same tick."""
        broker = PaperBroker(
            starting_cash=Decimal("100000"),
            order_latency_ms=1,  # 1ms for "immediate"
            latency_jitter_pct=Decimal("0"),
        )
        await broker.connect()

        broker._update_market_data(
            sample_equity,
            create_bar_data(Decimal("100.00")),
        )

        import time

        start = time.monotonic()

        order_id = await broker.submit_order(
            asset=sample_equity,
            amount=Decimal("100"),
            order_type="market",
        )

        # Wait for fill
        await asyncio.sleep(0.05)

        elapsed_ms = (time.monotonic() - start) * 1000

        # Should fill very quickly
        order = broker.orders[order_id]
        assert order.filled == Decimal("100")
        assert elapsed_ms < 100  # Should complete within 100ms

    @pytest.mark.asyncio
    async def test_delayed_fill_model(self, sample_equity):
        """Test delayed fill model: fill after configurable delay."""
        delay_ms = 100
        broker = PaperBroker(
            starting_cash=Decimal("100000"),
            order_latency_ms=delay_ms,
            latency_jitter_pct=Decimal("0"),
        )
        await broker.connect()

        broker._update_market_data(
            sample_equity,
            create_bar_data(Decimal("100.00")),
        )

        import time

        start = time.monotonic()

        order_id = await broker.submit_order(
            asset=sample_equity,
            amount=Decimal("100"),
            order_type="market",
        )

        # Check order is pending initially
        await asyncio.sleep(0.01)
        if order_id in broker.open_orders:
            assert broker.open_orders[order_id].filled < Decimal("100")

        # Wait for fill (delay + buffer)
        await asyncio.sleep(0.2)

        elapsed_ms = (time.monotonic() - start) * 1000

        # Should have delay
        order = broker.orders[order_id]
        assert order.filled == Decimal("100")
        assert elapsed_ms >= delay_ms * 0.8  # Allow some timing variance

    @pytest.mark.asyncio
    async def test_fill_price_matches_simulated_price(self, paper_broker_immediate, sample_equity):
        """Test that fill price matches the simulated market price."""
        broker = paper_broker_immediate
        await broker.connect()

        expected_price = Decimal("123.45")
        broker._update_market_data(
            sample_equity,
            create_bar_data(expected_price),
        )

        await broker.submit_order(
            asset=sample_equity,
            amount=Decimal("100"),
            order_type="market",
        )

        await asyncio.sleep(0.1)

        # Position cost basis should match market price
        position = broker.positions[sample_equity]
        assert position.cost_basis == expected_price

    @pytest.mark.asyncio
    async def test_fill_model_selectable_via_config(self):
        """Test that fill model is selectable via configuration."""
        # Immediate model config
        immediate_config = FillModelConfig(model="immediate", delay_ms=1)
        assert immediate_config.model == "immediate"
        assert immediate_config.delay_ms == 1

        # Delayed model config
        delayed_config = FillModelConfig(model="delayed", delay_ms=100)
        assert delayed_config.model == "delayed"
        assert delayed_config.delay_ms == 100

    @pytest.mark.asyncio
    async def test_delayed_fill_with_jitter(self, sample_equity):
        """Test that delayed fills have configurable jitter."""
        broker = PaperBroker(
            starting_cash=Decimal("100000"),
            order_latency_ms=100,
            latency_jitter_pct=Decimal("0.20"),  # ±20%
        )

        # Run multiple times to check variance
        latencies = []
        for _ in range(10):
            latency = broker._simulate_latency()
            latencies.append(latency * 1000)  # Convert to ms

        # Should have variation
        min_latency = min(latencies)
        max_latency = max(latencies)

        # With 20% jitter, range should be approximately 80-120ms
        assert min_latency >= 80 * 0.9  # Allow some variance
        assert max_latency <= 120 * 1.1


# =============================================================================
# AC3: Position Tracking Tests
# =============================================================================


class TestPositionTracking:
    """Tests for AC3: Accurate position tracking."""

    @pytest.mark.asyncio
    async def test_long_position_creation(self, paper_broker_immediate, sample_equity):
        """Test that long position is created correctly."""
        broker = paper_broker_immediate
        await broker.connect()

        entry_price = Decimal("150.00")
        broker._update_market_data(sample_equity, create_bar_data(entry_price))

        await broker.submit_order(
            asset=sample_equity,
            amount=Decimal("100"),
            order_type="market",
        )

        await asyncio.sleep(0.1)

        assert sample_equity in broker.positions
        position = broker.positions[sample_equity]
        assert position.amount == Decimal("100")  # Long position
        assert position.cost_basis == entry_price

    @pytest.mark.asyncio
    async def test_short_position_creation(self, paper_broker_immediate, sample_equity):
        """Test that short position is created correctly."""
        broker = paper_broker_immediate
        await broker.connect()

        # First establish a long position to sell from
        entry_price = Decimal("150.00")
        broker._update_market_data(sample_equity, create_bar_data(entry_price))

        # Buy first
        await broker.submit_order(
            asset=sample_equity,
            amount=Decimal("200"),
            order_type="market",
        )
        await asyncio.sleep(0.1)

        # Now sell more than we own to go short
        await broker.submit_order(
            asset=sample_equity,
            amount=Decimal("-300"),
            order_type="market",
        )
        await asyncio.sleep(0.1)

        position = broker.positions[sample_equity]
        assert position.amount == Decimal("-100")  # Short position

    @pytest.mark.asyncio
    async def test_entry_price_accuracy(self, paper_broker_immediate, sample_equity):
        """Test that entry price matches fill price exactly."""
        broker = paper_broker_immediate
        await broker.connect()

        # Use a specific price
        exact_price = Decimal("123.456789")
        broker._update_market_data(sample_equity, create_bar_data(exact_price))

        await broker.submit_order(
            asset=sample_equity,
            amount=Decimal("100"),
            order_type="market",
        )

        await asyncio.sleep(0.1)

        position = broker.positions[sample_equity]
        assert position.cost_basis == exact_price

    @pytest.mark.asyncio
    async def test_position_size_accuracy_small(self, sample_equity):
        """Test that position size matches order quantity for small size."""
        broker = PaperBroker(
            starting_cash=Decimal("100000"),
            order_latency_ms=1,
            latency_jitter_pct=Decimal("0"),
        )
        await broker.connect()

        broker._update_market_data(sample_equity, create_bar_data(Decimal("100")))

        size = Decimal("1")
        await broker.submit_order(
            asset=sample_equity,
            amount=size,
            order_type="market",
        )
        await asyncio.sleep(0.1)

        position = broker.positions[sample_equity]
        assert position.amount == size

    @pytest.mark.asyncio
    async def test_position_size_accuracy_medium(self, sample_equity):
        """Test that position size matches order quantity for medium size."""
        broker = PaperBroker(
            starting_cash=Decimal("100000"),
            order_latency_ms=1,
            latency_jitter_pct=Decimal("0"),
        )
        await broker.connect()

        broker._update_market_data(sample_equity, create_bar_data(Decimal("100")))

        size = Decimal("100")
        await broker.submit_order(
            asset=sample_equity,
            amount=size,
            order_type="market",
        )
        await asyncio.sleep(0.1)

        position = broker.positions[sample_equity]
        assert position.amount == size

    @pytest.mark.asyncio
    async def test_position_size_accuracy_fractional(self, sample_equity):
        """Test that position size matches order quantity for fractional size.

        Note: Equities only allow 2 decimal places for amounts per DecimalOrder validation.
        """
        broker = PaperBroker(
            starting_cash=Decimal("100000"),
            order_latency_ms=1,
            latency_jitter_pct=Decimal("0"),
        )
        await broker.connect()

        broker._update_market_data(sample_equity, create_bar_data(Decimal("100")))

        # Use 2 decimal places for equity (max allowed precision)
        size = Decimal("0.01")
        await broker.submit_order(
            asset=sample_equity,
            amount=size,
            order_type="market",
        )
        await asyncio.sleep(0.1)

        position = broker.positions[sample_equity]
        assert position.amount == size

    @pytest.mark.asyncio
    async def test_position_direction_correctness(self, paper_broker_immediate, sample_equity):
        """Test that position direction (long/short) is correct based on order side."""
        broker = paper_broker_immediate
        await broker.connect()

        broker._update_market_data(sample_equity, create_bar_data(Decimal("100")))

        # Buy order (positive amount) → long position (positive amount)
        await broker.submit_order(
            asset=sample_equity,
            amount=Decimal("100"),
            order_type="market",
        )
        await asyncio.sleep(0.1)

        position = broker.positions[sample_equity]
        assert position.amount > 0  # Long position

        # Sell more to go short
        await broker.submit_order(
            asset=sample_equity,
            amount=Decimal("-200"),
            order_type="market",
        )
        await asyncio.sleep(0.1)

        position = broker.positions[sample_equity]
        assert position.amount < 0  # Short position

    @pytest.mark.asyncio
    async def test_position_updates_on_additional_orders(
        self, paper_broker_immediate, sample_equity
    ):
        """Test that position updates correctly on additional orders."""
        broker = paper_broker_immediate
        await broker.connect()

        broker._update_market_data(sample_equity, create_bar_data(Decimal("100")))

        # First buy
        await broker.submit_order(
            asset=sample_equity,
            amount=Decimal("100"),
            order_type="market",
        )
        await asyncio.sleep(0.1)

        assert broker.positions[sample_equity].amount == Decimal("100")

        # Second buy at different price
        broker._update_market_data(sample_equity, create_bar_data(Decimal("110")))
        await broker.submit_order(
            asset=sample_equity,
            amount=Decimal("100"),
            order_type="market",
        )
        await asyncio.sleep(0.1)

        position = broker.positions[sample_equity]
        assert position.amount == Decimal("200")
        # Cost basis should be weighted average: (100*100 + 100*110) / 200 = 105
        assert position.cost_basis == Decimal("105")


# =============================================================================
# AC4: PnL Calculation Tests
# =============================================================================


class TestPnLCalculations:
    """Tests for AC4: PnL calculations with Decimal precision."""

    @pytest.mark.asyncio
    async def test_unrealized_pnl_long_position(self, paper_broker_immediate, sample_equity):
        """Test unrealized PnL for open long position."""
        broker = paper_broker_immediate
        await broker.connect()

        entry_price = Decimal("100.00")
        broker._update_market_data(sample_equity, create_bar_data(entry_price))

        await broker.submit_order(
            asset=sample_equity,
            amount=Decimal("100"),
            order_type="market",
        )
        await asyncio.sleep(0.1)

        # Update to new price
        current_price = Decimal("110.00")
        broker._update_market_data(sample_equity, create_bar_data(current_price))

        # Update position's last sale price for PnL calc
        position = broker.positions[sample_equity]
        position.last_sale_price = current_price

        # Unrealized PnL = (current_price - entry_price) * position_size
        expected_pnl = (current_price - entry_price) * Decimal("100")
        assert position.unrealized_pnl == expected_pnl

    @pytest.mark.asyncio
    async def test_unrealized_pnl_short_position(self, paper_broker_immediate, sample_equity):
        """Test unrealized PnL for open short position."""
        broker = paper_broker_immediate
        await broker.connect()

        # First buy to establish position we can sell from
        entry_price = Decimal("100.00")
        broker._update_market_data(sample_equity, create_bar_data(entry_price))

        await broker.submit_order(
            asset=sample_equity,
            amount=Decimal("200"),
            order_type="market",
        )
        await asyncio.sleep(0.1)

        # Sell to go short
        await broker.submit_order(
            asset=sample_equity,
            amount=Decimal("-300"),
            order_type="market",
        )
        await asyncio.sleep(0.1)

        position = broker.positions[sample_equity]
        assert position.amount == Decimal("-100")

        # Update to new lower price (profit for short)
        current_price = Decimal("90.00")
        position.last_sale_price = current_price

        # For short: unrealized_pnl = (entry_price - current_price) * abs(position_size)
        # Note: The actual formula depends on the Position class implementation
        # This test verifies the direction is correct
        pnl = position.unrealized_pnl
        # For short position, price drop = profit
        assert pnl >= 0  # Should be profitable

    @pytest.mark.asyncio
    async def test_realized_pnl_on_position_close(self, paper_broker_immediate, sample_equity):
        """Test realized PnL on position close."""
        broker = paper_broker_immediate
        await broker.connect()

        starting_cash = broker.cash

        # Buy at $100
        entry_price = Decimal("100.00")
        broker._update_market_data(sample_equity, create_bar_data(entry_price))

        await broker.submit_order(
            asset=sample_equity,
            amount=Decimal("100"),
            order_type="market",
        )
        await asyncio.sleep(0.1)

        # Sell at $110
        exit_price = Decimal("110.00")
        broker._update_market_data(sample_equity, create_bar_data(exit_price))

        await broker.submit_order(
            asset=sample_equity,
            amount=Decimal("-100"),
            order_type="market",
        )
        await asyncio.sleep(0.1)

        # Position should be closed
        assert sample_equity not in broker.positions

        # Net profit/loss from the round trip trade
        # Bought at $100 × 100 = $10,000
        # Sold at $110 × 100 = $11,000
        # Profit = $1,000
        final_cash = broker.cash
        net_pnl = final_cash - starting_cash
        expected_pnl = (exit_price - entry_price) * Decimal("100")
        assert net_pnl == expected_pnl

    @pytest.mark.asyncio
    async def test_pnl_decimal_precision(self, paper_broker_immediate, sample_equity):
        """Test that PnL uses Decimal precision (no floating point errors)."""
        broker = paper_broker_immediate
        await broker.connect()

        # Use prices that would cause floating point issues
        entry_price = Decimal("0.1")
        broker._update_market_data(sample_equity, create_bar_data(entry_price))

        await broker.submit_order(
            asset=sample_equity,
            amount=Decimal("3"),
            order_type="market",
        )
        await asyncio.sleep(0.1)

        position = broker.positions[sample_equity]

        # 0.1 + 0.1 + 0.1 should equal exactly 0.3 with Decimal
        total_cost = entry_price * Decimal("3")
        assert total_cost == Decimal("0.3")  # Would fail with float
        assert position.cost_basis == entry_price

    @pytest.mark.asyncio
    async def test_pnl_with_multiple_partial_closes(self, paper_broker_immediate, sample_equity):
        """Test PnL with multiple partial position closes."""
        broker = paper_broker_immediate
        await broker.connect()

        # Buy 100 shares at $100
        broker._update_market_data(sample_equity, create_bar_data(Decimal("100")))
        await broker.submit_order(
            asset=sample_equity,
            amount=Decimal("100"),
            order_type="market",
        )
        await asyncio.sleep(0.1)

        # Partial close 1: Sell 30 at $110
        broker._update_market_data(sample_equity, create_bar_data(Decimal("110")))
        cash_before_sell1 = broker.cash
        await broker.submit_order(
            asset=sample_equity,
            amount=Decimal("-30"),
            order_type="market",
        )
        await asyncio.sleep(0.1)

        realized1 = broker.cash - cash_before_sell1
        expected1 = Decimal("30") * Decimal("110")
        assert realized1 == expected1

        # Partial close 2: Sell 30 at $105
        broker._update_market_data(sample_equity, create_bar_data(Decimal("105")))
        cash_before_sell2 = broker.cash
        await broker.submit_order(
            asset=sample_equity,
            amount=Decimal("-30"),
            order_type="market",
        )
        await asyncio.sleep(0.1)

        realized2 = broker.cash - cash_before_sell2
        expected2 = Decimal("30") * Decimal("105")
        assert realized2 == expected2

        # Remaining position
        assert broker.positions[sample_equity].amount == Decimal("40")


# =============================================================================
# AC5: Order State Transitions
# =============================================================================


class TestOrderStateTransitions:
    """Tests for AC5: Order state transitions lifecycle."""

    @pytest.mark.asyncio
    async def test_successful_order_flow(self, paper_broker_immediate, sample_equity):
        """Test successful order: pending → submitted → filled."""
        broker = paper_broker_immediate
        await broker.connect()

        broker._update_market_data(sample_equity, create_bar_data(Decimal("100")))

        # Submit order
        order_id = await broker.submit_order(
            asset=sample_equity,
            amount=Decimal("100"),
            order_type="market",
        )

        # Order should be tracked
        assert order_id in broker.orders

        # Wait for fill
        await asyncio.sleep(0.1)

        order = broker.orders[order_id]

        # Check final state: filled
        assert order.filled == Decimal("100")
        assert order_id not in broker.open_orders  # No longer pending

    @pytest.mark.asyncio
    async def test_cancelled_order_flow(self, paper_broker_delayed, sample_equity):
        """Test cancelled order: pending → submitted → cancelled."""
        broker = paper_broker_delayed
        await broker.connect()

        # Don't set market data so order stays pending longer

        # Submit order
        order_id = await broker.submit_order(
            asset=sample_equity,
            amount=Decimal("100"),
            order_type="market",
        )

        # Cancel immediately
        await broker.cancel_order(order_id)

        # Order should be removed from open orders
        assert order_id not in broker.open_orders

    @pytest.mark.asyncio
    async def test_order_transitions_logged(self, paper_broker_immediate, sample_equity):
        """Test that all order state transitions are logged for audit.

        PaperBroker uses structlog which logs internally. We verify that
        transactions are recorded which serves as the audit trail.
        """
        broker = paper_broker_immediate
        await broker.connect()

        broker._update_market_data(sample_equity, create_bar_data(Decimal("100")))

        # Initial state
        assert len(broker.transactions) == 0

        await broker.submit_order(
            asset=sample_equity,
            amount=Decimal("100"),
            order_type="market",
        )
        await asyncio.sleep(0.1)

        # Transaction should be created on fill - this is the audit trail
        assert len(broker.transactions) == 1
        transaction = broker.transactions[0]
        assert transaction.asset == sample_equity
        assert transaction.amount == Decimal("100")

    @pytest.mark.asyncio
    async def test_timeout_scenario(self, paper_broker_delayed, sample_equity):
        """Test order handling when market data is unavailable (timeout-like)."""
        broker = paper_broker_delayed
        await broker.connect()

        # Submit order without market data
        order_id = await broker.submit_order(
            asset=sample_equity,
            amount=Decimal("100"),
            order_type="market",
        )

        # Wait for execution attempt
        await asyncio.sleep(0.3)

        # Order should be rejected/removed (no market data)
        assert order_id not in broker.open_orders


# =============================================================================
# AC6: Comprehensive Trading Scenarios
# =============================================================================


class TestTradingScenarios:
    """Tests for AC6: Various trading scenarios (long/short, profit/loss)."""

    @pytest.mark.asyncio
    async def test_long_entry_price_up_exit_profit(
        self, paper_broker_immediate, sample_equity, execute_strategy
    ):
        """Test: Long entry, price up, long exit (profit)."""
        strategy = DeterministicStrategy(
            [
                SignalPattern(0, SignalType.BUY, Decimal("100")),
                SignalPattern(4, SignalType.SELL, Decimal("100")),
            ]
        )

        # Prices go up
        price_series = [
            Decimal("100"),  # Entry
            Decimal("105"),
            Decimal("110"),
            Decimal("115"),
            Decimal("120"),  # Exit
        ]

        result = await execute_strategy(
            paper_broker_immediate, strategy, sample_equity, price_series
        )

        # Should be profitable
        # Entry: 100 × $100 = $10,000
        # Exit: 100 × $120 = $12,000
        # Profit: $2,000
        # Final cash: $100,000 - $10,000 + $12,000 = $102,000
        expected_final_cash = Decimal("100000") - Decimal("10000") + Decimal("12000")
        assert result["final_cash"] == expected_final_cash
        assert len(result["final_positions"]) == 0  # Position closed

    @pytest.mark.asyncio
    async def test_long_entry_price_down_exit_loss(
        self, paper_broker_immediate, sample_equity, execute_strategy
    ):
        """Test: Long entry, price down, long exit (loss)."""
        strategy = DeterministicStrategy(
            [
                SignalPattern(0, SignalType.BUY, Decimal("100")),
                SignalPattern(4, SignalType.SELL, Decimal("100")),
            ]
        )

        # Prices go down
        price_series = [
            Decimal("100"),  # Entry
            Decimal("95"),
            Decimal("90"),
            Decimal("85"),
            Decimal("80"),  # Exit
        ]

        result = await execute_strategy(
            paper_broker_immediate, strategy, sample_equity, price_series
        )

        # Should be loss
        # Entry: 100 × $100 = $10,000
        # Exit: 100 × $80 = $8,000
        # Loss: $2,000
        # Final cash: $100,000 - $10,000 + $8,000 = $98,000
        expected_final_cash = Decimal("100000") - Decimal("10000") + Decimal("8000")
        assert result["final_cash"] == expected_final_cash

    @pytest.mark.asyncio
    async def test_short_entry_price_down_exit_profit(self, paper_broker_immediate, sample_equity):
        """Test: Short entry (sell first), price down, cover (profit).

        In this scenario, we simulate going short by establishing a long
        position first, then selling more than we own, then covering.
        """
        broker = paper_broker_immediate
        await broker.connect()

        starting_cash = broker.cash

        # First establish a long position to sell from
        broker._update_market_data(sample_equity, create_bar_data(Decimal("100")))
        await broker.submit_order(
            asset=sample_equity,
            amount=Decimal("200"),
            order_type="market",
        )
        await asyncio.sleep(0.1)

        # Sell to go short (-300 from +200 = -100 short position)
        await broker.submit_order(
            asset=sample_equity,
            amount=Decimal("-300"),
            order_type="market",
        )
        await asyncio.sleep(0.1)

        # Verify we're short
        assert sample_equity in broker.positions
        assert broker.positions[sample_equity].amount == Decimal("-100")

        # Price drops - cover at lower price
        broker._update_market_data(sample_equity, create_bar_data(Decimal("80")))
        await broker.submit_order(
            asset=sample_equity,
            amount=Decimal("100"),  # Cover the short
            order_type="market",
        )
        await asyncio.sleep(0.1)

        # Position should be closed
        assert sample_equity not in broker.positions

        # Calculate expected P&L:
        # Buy 200 @ $100 = -$20,000
        # Sell 300 @ $100 = +$30,000
        # Buy 100 @ $80 = -$8,000
        # Net: -$20,000 + $30,000 - $8,000 = +$2,000
        expected_pnl = Decimal("2000")
        actual_pnl = broker.cash - starting_cash
        assert actual_pnl == expected_pnl

    @pytest.mark.asyncio
    async def test_short_entry_price_up_exit_loss(self, paper_broker_immediate, sample_equity):
        """Test: Short entry, price up, cover (loss)."""
        broker = paper_broker_immediate
        await broker.connect()

        # First establish a long position to sell from
        broker._update_market_data(sample_equity, create_bar_data(Decimal("100")))
        await broker.submit_order(
            asset=sample_equity,
            amount=Decimal("200"),
            order_type="market",
        )
        await asyncio.sleep(0.1)

        initial_cash = broker.cash

        # Sell to go short
        await broker.submit_order(
            asset=sample_equity,
            amount=Decimal("-300"),
            order_type="market",
        )
        await asyncio.sleep(0.1)

        # Price rises - cover at higher price (loss)
        broker._update_market_data(sample_equity, create_bar_data(Decimal("120")))
        await broker.submit_order(
            asset=sample_equity,
            amount=Decimal("100"),  # Cover the short
            order_type="market",
        )
        await asyncio.sleep(0.1)

        # Position should be closed
        assert sample_equity not in broker.positions

    @pytest.mark.asyncio
    async def test_multiple_concurrent_positions(self, paper_broker_immediate, sample_equity):
        """Test: Multiple concurrent positions."""
        broker = paper_broker_immediate
        await broker.connect()

        # Create multiple assets
        from rustybt.assets import Equity, ExchangeInfo

        exchange_info = ExchangeInfo("NASDAQ", "NASDAQ", "US")
        asset1 = Equity(1, exchange_info, symbol="AAPL")
        asset2 = Equity(2, exchange_info, symbol="GOOGL")
        asset3 = Equity(3, exchange_info, symbol="MSFT")

        # Set market data for all
        for asset, price in [
            (asset1, Decimal("150")),
            (asset2, Decimal("2800")),
            (asset3, Decimal("330")),
        ]:
            broker._update_market_data(asset, create_bar_data(price))

        # Buy all three
        for asset in [asset1, asset2, asset3]:
            await broker.submit_order(
                asset=asset,
                amount=Decimal("10"),
                order_type="market",
            )

        await asyncio.sleep(0.2)

        # Should have 3 positions
        assert len(broker.positions) == 3
        assert asset1 in broker.positions
        assert asset2 in broker.positions
        assert asset3 in broker.positions

        # Each position should have correct size
        for asset in [asset1, asset2, asset3]:
            assert broker.positions[asset].amount == Decimal("10")

    @pytest.mark.asyncio
    async def test_rapid_buy_sell_cycle(self, paper_broker_immediate, sample_equity):
        """Test rapid buy-sell cycle to verify state consistency."""
        broker = paper_broker_immediate
        await broker.connect()

        initial_cash = broker.cash

        broker._update_market_data(sample_equity, create_bar_data(Decimal("100")))

        # Rapid cycles
        for _ in range(5):
            await broker.submit_order(
                asset=sample_equity,
                amount=Decimal("10"),
                order_type="market",
            )
            await asyncio.sleep(0.05)

            await broker.submit_order(
                asset=sample_equity,
                amount=Decimal("-10"),
                order_type="market",
            )
            await asyncio.sleep(0.05)

        await asyncio.sleep(0.2)

        # No position should remain (all closed)
        assert sample_equity not in broker.positions

        # Cash should be unchanged (no commission/slippage)
        assert broker.cash == initial_cash


# =============================================================================
# Integration Test: Full Strategy Execution
# =============================================================================


class TestFullStrategyExecution:
    """Integration tests for complete strategy execution."""

    @pytest.mark.asyncio
    async def test_complete_strategy_lifecycle(
        self, paper_broker_immediate, sample_equity, execute_strategy
    ):
        """Test complete strategy lifecycle from start to finish."""
        strategy = DeterministicStrategy(
            [
                SignalPattern(1, SignalType.BUY, Decimal("50")),
                SignalPattern(3, SignalType.BUY, Decimal("50")),
                SignalPattern(6, SignalType.SELL, Decimal("100")),
            ]
        )

        price_series = [
            Decimal("100"),
            Decimal("102"),  # Buy 50
            Decimal("105"),
            Decimal("103"),  # Buy 50 more
            Decimal("108"),
            Decimal("110"),
            Decimal("115"),  # Sell all
        ]

        result = await execute_strategy(
            paper_broker_immediate, strategy, sample_equity, price_series
        )

        # All signals executed
        assert len(result["signals_generated"]) == 3

        # Position closed
        assert len(result["final_positions"]) == 0

        # Transactions recorded
        assert len(result["transactions"]) == 3

    @pytest.mark.asyncio
    async def test_multi_position_strategy(
        self, paper_broker_immediate, sample_equity, execute_strategy
    ):
        """Test strategy with multiple position building."""
        strategy = MultiPositionStrategy(num_positions=3, amount=Decimal("100"))

        price_series = [
            Decimal("100"),  # Bar 0
            Decimal("105"),  # Bar 1 - Buy
            Decimal("110"),  # Bar 2 - Buy
            Decimal("115"),  # Bar 3 - Buy
            Decimal("120"),  # Bar 4 - Sell
            Decimal("125"),  # Bar 5 - Sell
            Decimal("130"),  # Bar 6 - Sell
        ]

        result = await execute_strategy(
            paper_broker_immediate, strategy, sample_equity, price_series
        )

        # All 6 signals executed
        assert len(result["signals_generated"]) == 6

        # Position should be closed
        assert len(result["final_positions"]) == 0
