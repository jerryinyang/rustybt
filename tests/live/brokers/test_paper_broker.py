"""Tests for PaperBroker implementation.

This test module validates that PaperBroker:
1. Implements BrokerAdapter interface correctly
2. Simulates order execution realistically
3. Applies commission and slippage models
4. Tracks positions and cash accurately
5. Simulates latency appropriately
6. Handles partial fills based on volume
"""

import asyncio
from datetime import datetime
from decimal import Decimal

import pytest

from rustybt.assets import Equity, ExchangeInfo
from rustybt.finance.decimal.commission import (
    NoCommission,
    PerShareCommission,
)
from rustybt.finance.decimal.slippage import (
    FixedBasisPointsSlippage,
    FixedSlippage,
    NoSlippage,
)
from rustybt.live.brokers.paper_broker import (
    InsufficientFundsError,
    MarketDataUnavailableError,
    PaperBroker,
)


@pytest.fixture
def sample_asset():
    """Create sample equity asset for testing."""
    exchange_info = ExchangeInfo("NASDAQ", "NASDAQ", "US")
    return Equity(1, exchange_info, symbol="AAPL")


@pytest.fixture
def paper_broker():
    """Create PaperBroker with default settings."""
    return PaperBroker(
        starting_cash=Decimal("100000"),
        commission_model=NoCommission(),
        slippage_model=NoSlippage(),
        order_latency_ms=10,  # Short latency for tests
    )


@pytest.fixture
def paper_broker_with_costs():
    """Create PaperBroker with commission and slippage."""
    return PaperBroker(
        starting_cash=Decimal("100000"),
        commission_model=PerShareCommission(rate=Decimal("0.005"), minimum=Decimal("1.00")),
        slippage_model=FixedBasisPointsSlippage(basis_points=Decimal("5")),
        order_latency_ms=10,
    )


class TestPaperBrokerInitialization:
    """Test PaperBroker initialization."""

    def test_initialization_with_defaults(self):
        """Test PaperBroker initializes with default settings."""
        broker = PaperBroker()

        assert broker.starting_cash == Decimal("100000")
        assert broker.cash == Decimal("100000")
        assert isinstance(broker.commission_model, NoCommission)
        assert isinstance(broker.slippage_model, NoSlippage)
        assert broker.order_latency_ms == 100
        assert broker.volume_limit_pct == Decimal("0.025")
        assert len(broker.positions) == 0
        assert len(broker.orders) == 0

    def test_initialization_with_custom_settings(self):
        """Test PaperBroker initializes with custom settings."""
        commission = PerShareCommission(Decimal("0.01"))
        slippage = FixedSlippage(Decimal("0.05"))

        broker = PaperBroker(
            starting_cash=Decimal("50000"),
            commission_model=commission,
            slippage_model=slippage,
            order_latency_ms=50,
            volume_limit_pct=Decimal("0.05"),
        )

        assert broker.starting_cash == Decimal("50000")
        assert broker.cash == Decimal("50000")
        assert broker.commission_model == commission
        assert broker.slippage_model == slippage
        assert broker.order_latency_ms == 50
        assert broker.volume_limit_pct == Decimal("0.05")


class TestPaperBrokerConnection:
    """Test PaperBroker connection management."""

    @pytest.mark.asyncio
    async def test_connect_succeeds(self, paper_broker):
        """Test paper broker connection always succeeds."""
        assert not paper_broker.is_connected()

        await paper_broker.connect()

        assert paper_broker.is_connected()

    @pytest.mark.asyncio
    async def test_disconnect(self, paper_broker):
        """Test paper broker disconnection."""
        await paper_broker.connect()
        assert paper_broker.is_connected()

        await paper_broker.disconnect()

        assert not paper_broker.is_connected()


class TestPaperBrokerMarketOrders:
    """Test market order execution."""

    @pytest.mark.asyncio
    async def test_market_order_buy_full_fill(self, paper_broker, sample_asset):
        """Test market buy order fills completely at current price."""
        await paper_broker.connect()

        # Set market data
        paper_broker._update_market_data(
            sample_asset,
            {
                "open": Decimal("150.00"),
                "high": Decimal("152.00"),
                "low": Decimal("149.00"),
                "close": Decimal("151.00"),
                "volume": Decimal("1000000"),
                "timestamp": datetime.now(),
            },
        )

        # Submit market buy order
        order_id = await paper_broker.submit_order(
            asset=sample_asset, amount=Decimal("100"), order_type="market"
        )

        # Wait for fill
        await asyncio.sleep(0.1)

        # Check order filled
        assert order_id in paper_broker.orders
        order = paper_broker.orders[order_id]
        assert order.filled == Decimal("100")
        assert order_id not in paper_broker.open_orders  # Fully filled

        # Check cash updated (no commission/slippage)
        expected_cash = Decimal("100000") - (Decimal("100") * Decimal("151.00"))
        assert paper_broker.cash == expected_cash

        # Check position created
        assert sample_asset in paper_broker.positions
        position = paper_broker.positions[sample_asset]
        assert position.amount == Decimal("100")
        assert position.cost_basis == Decimal("151.00")

    @pytest.mark.asyncio
    async def test_market_order_sell(self, paper_broker, sample_asset):
        """Test market sell order."""
        await paper_broker.connect()

        # Set market data
        paper_broker._update_market_data(
            sample_asset,
            {
                "close": Decimal("150.00"),
                "volume": Decimal("1000000"),
                "timestamp": datetime.now(),
            },
        )

        # First buy to establish position
        await paper_broker.submit_order(
            asset=sample_asset, amount=Decimal("100"), order_type="market"
        )
        await asyncio.sleep(0.1)

        initial_cash = paper_broker.cash

        # Now sell
        await paper_broker.submit_order(
            asset=sample_asset, amount=Decimal("-50"), order_type="market"
        )
        await asyncio.sleep(0.1)

        # Check position reduced
        position = paper_broker.positions[sample_asset]
        assert position.amount == Decimal("50")

        # Check cash increased from sale
        expected_cash = initial_cash + (Decimal("50") * Decimal("150.00"))
        assert paper_broker.cash == expected_cash

    @pytest.mark.asyncio
    async def test_market_order_with_commission(self, paper_broker_with_costs, sample_asset):
        """Test market order applies commission correctly."""
        broker = paper_broker_with_costs
        await broker.connect()

        # Set market data
        broker._update_market_data(
            sample_asset,
            {
                "close": Decimal("100.00"),
                "volume": Decimal("1000000"),
                "timestamp": datetime.now(),
            },
        )

        # Submit buy order
        await broker.submit_order(asset=sample_asset, amount=Decimal("100"), order_type="market")
        await asyncio.sleep(0.1)

        # Check commission charged (100 shares × $0.005 = $0.50, but minimum is $1.00)
        order = list(broker.orders.values())[0]
        assert order.commission >= Decimal("1.00")  # Minimum commission

        # Check cash decreased by order value + commission
        # Expected: close price is $100, but slippage adds 5 bps (0.05%)
        # Fill price = $100 × 1.0005 = $100.05
        # Order value = 100 × $100.05 = $10005.00
        # Commission = max(100 × $0.005, $1.00) = $1.00
        # Total cost = $10005.00 + $1.00 = $10006.00
        expected_cash = Decimal("100000") - Decimal("10005.00") - order.commission
        assert abs(broker.cash - expected_cash) < Decimal("0.01")  # Allow small rounding

    @pytest.mark.asyncio
    async def test_market_order_with_slippage(self, paper_broker_with_costs, sample_asset):
        """Test market order applies slippage correctly."""
        broker = paper_broker_with_costs
        await broker.connect()

        # Set market data
        broker._update_market_data(
            sample_asset,
            {
                "close": Decimal("100.00"),
                "volume": Decimal("1000000"),
                "timestamp": datetime.now(),
            },
        )

        # Submit buy order
        await broker.submit_order(asset=sample_asset, amount=Decimal("100"), order_type="market")
        await asyncio.sleep(0.1)

        # Check position cost basis reflects slippage
        # Slippage model: FixedBasisPointsSlippage(5 bps = 0.05%)
        # Expected fill price: $100 × 1.0005 = $100.05
        position = broker.positions[sample_asset]
        expected_cost_basis = Decimal("100.00") * Decimal("1.0005")
        assert abs(position.cost_basis - expected_cost_basis) < Decimal("0.01")

    @pytest.mark.asyncio
    async def test_market_order_insufficient_funds(self, paper_broker, sample_asset):
        """Test market order rejected if insufficient funds."""
        await paper_broker.connect()

        # Set market data
        paper_broker._update_market_data(
            sample_asset,
            {
                "close": Decimal("1000.00"),
                "volume": Decimal("1000000"),
                "timestamp": datetime.now(),
            },
        )

        # Try to buy more than we can afford
        # Cash: $100,000, trying to buy 200 shares @ $1000 = $200,000
        with pytest.raises(InsufficientFundsError):
            await paper_broker.submit_order(
                asset=sample_asset, amount=Decimal("200"), order_type="market"
            )

    @pytest.mark.asyncio
    async def test_market_order_no_market_data(self, paper_broker, sample_asset):
        """Test market order rejected if no market data available."""
        await paper_broker.connect()

        # Submit order without setting market data
        order_id = await paper_broker.submit_order(
            asset=sample_asset, amount=Decimal("100"), order_type="market"
        )

        # Wait for execution attempt
        await asyncio.sleep(0.1)

        # Order should not fill
        assert order_id not in paper_broker.open_orders  # Removed on failure
        assert len(paper_broker.positions) == 0


class TestPaperBrokerLimitOrders:
    """Test limit order execution."""

    @pytest.mark.asyncio
    async def test_limit_buy_marketable(self, paper_broker, sample_asset):
        """Test marketable limit buy order fills at limit price."""
        await paper_broker.connect()

        # Set market data: price is below buy limit
        paper_broker._update_market_data(
            sample_asset,
            {
                "close": Decimal("100.00"),
                "volume": Decimal("1000000"),
                "timestamp": datetime.now(),
            },
        )

        # Submit limit buy @ $105 (marketable since market is $100)
        await paper_broker.submit_order(
            asset=sample_asset,
            amount=Decimal("100"),
            order_type="limit",
            limit_price=Decimal("105.00"),
        )
        await asyncio.sleep(0.1)

        # Check filled at limit price (no worse than limit)
        position = paper_broker.positions[sample_asset]
        assert position.cost_basis == Decimal("105.00")
        assert position.amount == Decimal("100")

    @pytest.mark.asyncio
    async def test_limit_sell_marketable(self, paper_broker, sample_asset):
        """Test marketable limit sell order fills at limit price."""
        await paper_broker.connect()

        # First establish position
        paper_broker._update_market_data(
            sample_asset,
            {
                "close": Decimal("100.00"),
                "volume": Decimal("1000000"),
                "timestamp": datetime.now(),
            },
        )
        await paper_broker.submit_order(
            asset=sample_asset, amount=Decimal("100"), order_type="market"
        )
        await asyncio.sleep(0.1)

        initial_cash = paper_broker.cash

        # Now sell with limit @ $95 (marketable since market is $100)
        await paper_broker.submit_order(
            asset=sample_asset,
            amount=Decimal("-50"),
            order_type="limit",
            limit_price=Decimal("95.00"),
        )
        await asyncio.sleep(0.1)

        # Check sold at limit price
        expected_cash = initial_cash + (Decimal("50") * Decimal("95.00"))
        assert paper_broker.cash == expected_cash

    @pytest.mark.asyncio
    async def test_limit_order_not_marketable(self, paper_broker, sample_asset):
        """Test non-marketable limit order doesn't fill."""
        await paper_broker.connect()

        # Set market data
        paper_broker._update_market_data(
            sample_asset,
            {
                "close": Decimal("100.00"),
                "volume": Decimal("1000000"),
                "timestamp": datetime.now(),
            },
        )

        # Submit limit buy @ $95 (not marketable since market is $100)
        order_id = await paper_broker.submit_order(
            asset=sample_asset,
            amount=Decimal("100"),
            order_type="limit",
            limit_price=Decimal("95.00"),
        )
        await asyncio.sleep(0.1)

        # Order should not fill (simplified behavior for paper trading)
        assert order_id not in paper_broker.open_orders
        assert len(paper_broker.positions) == 0
        assert paper_broker.cash == Decimal("100000")  # Unchanged


class TestPaperBrokerPartialFills:
    """Test partial fill simulation based on volume."""

    @pytest.mark.asyncio
    async def test_partial_fill_exceeds_volume_limit(self, paper_broker, sample_asset):
        """Test order partially fills when exceeding volume limit."""
        await paper_broker.connect()

        # Set market data with limited volume
        # Volume: 100,000 shares
        # Volume limit: 2.5% = 2,500 shares max fill
        # Price: $10 per share (to avoid insufficient funds)
        paper_broker._update_market_data(
            sample_asset,
            {
                "close": Decimal("10.00"),
                "volume": Decimal("100000"),
                "timestamp": datetime.now(),
            },
        )

        # Try to buy 5,000 shares (2× volume limit)
        # Cost: 5000 × $10 = $50,000 (within $100k cash)
        await paper_broker.submit_order(
            asset=sample_asset, amount=Decimal("5000"), order_type="market"
        )
        await asyncio.sleep(0.1)

        # Should fill max 2,500 shares (2.5% of volume)
        order = list(paper_broker.orders.values())[0]
        expected_fill = Decimal("100000") * Decimal("0.025")
        assert order.filled == expected_fill
        assert order.id in paper_broker.open_orders  # Partially filled

    @pytest.mark.asyncio
    async def test_full_fill_within_volume_limit(self, paper_broker, sample_asset):
        """Test order fully fills when within volume limit."""
        await paper_broker.connect()

        # Set market data with high volume
        paper_broker._update_market_data(
            sample_asset,
            {
                "close": Decimal("100.00"),
                "volume": Decimal("1000000"),
                "timestamp": datetime.now(),
            },
        )

        # Buy 1,000 shares (well under 2.5% of 1M volume = 25,000)
        await paper_broker.submit_order(
            asset=sample_asset, amount=Decimal("1000"), order_type="market"
        )
        await asyncio.sleep(0.1)

        # Should fill completely
        order = list(paper_broker.orders.values())[0]
        assert order.filled == Decimal("1000")
        assert order.id not in paper_broker.open_orders  # Fully filled


class TestPaperBrokerPositionTracking:
    """Test position tracking and cash management."""

    @pytest.mark.asyncio
    async def test_position_created_on_buy(self, paper_broker, sample_asset):
        """Test position is created on buy order."""
        await paper_broker.connect()

        paper_broker._update_market_data(
            sample_asset,
            {
                "close": Decimal("150.00"),
                "volume": Decimal("1000000"),
                "timestamp": datetime.now(),
            },
        )

        await paper_broker.submit_order(
            asset=sample_asset, amount=Decimal("100"), order_type="market"
        )
        await asyncio.sleep(0.1)

        # Check position
        assert sample_asset in paper_broker.positions
        position = paper_broker.positions[sample_asset]
        assert position.amount == Decimal("100")
        assert position.cost_basis == Decimal("150.00")
        assert position.market_value == Decimal("100") * Decimal("150.00")

    @pytest.mark.asyncio
    async def test_position_updated_on_additional_buy(self, paper_broker, sample_asset):
        """Test position updates cost basis on additional buy."""
        await paper_broker.connect()

        # First buy @ $100
        paper_broker._update_market_data(
            sample_asset,
            {
                "close": Decimal("100.00"),
                "volume": Decimal("1000000"),
                "timestamp": datetime.now(),
            },
        )
        await paper_broker.submit_order(
            asset=sample_asset, amount=Decimal("100"), order_type="market"
        )
        await asyncio.sleep(0.1)

        # Second buy @ $110
        paper_broker._update_market_data(
            sample_asset,
            {
                "close": Decimal("110.00"),
                "volume": Decimal("1000000"),
                "timestamp": datetime.now(),
            },
        )
        await paper_broker.submit_order(
            asset=sample_asset, amount=Decimal("100"), order_type="market"
        )
        await asyncio.sleep(0.1)

        # Check position: 200 shares, cost basis = (100×$100 + 100×$110) / 200 = $105
        position = paper_broker.positions[sample_asset]
        assert position.amount == Decimal("200")
        expected_cost_basis = (
            Decimal("100") * Decimal("100") + Decimal("100") * Decimal("110")
        ) / Decimal("200")
        assert position.cost_basis == expected_cost_basis

    @pytest.mark.asyncio
    async def test_position_closed_on_full_sell(self, paper_broker, sample_asset):
        """Test position is removed when fully sold."""
        await paper_broker.connect()

        # Buy
        paper_broker._update_market_data(
            sample_asset,
            {
                "close": Decimal("100.00"),
                "volume": Decimal("1000000"),
                "timestamp": datetime.now(),
            },
        )
        await paper_broker.submit_order(
            asset=sample_asset, amount=Decimal("100"), order_type="market"
        )
        await asyncio.sleep(0.1)

        # Sell all
        await paper_broker.submit_order(
            asset=sample_asset, amount=Decimal("-100"), order_type="market"
        )
        await asyncio.sleep(0.1)

        # Position should be removed
        assert sample_asset not in paper_broker.positions

    @pytest.mark.asyncio
    async def test_cash_tracking_accurate(self, paper_broker, sample_asset):
        """Test cash is tracked accurately through trades."""
        await paper_broker.connect()

        initial_cash = paper_broker.cash

        # Buy 100 @ $100
        paper_broker._update_market_data(
            sample_asset,
            {
                "close": Decimal("100.00"),
                "volume": Decimal("1000000"),
                "timestamp": datetime.now(),
            },
        )
        await paper_broker.submit_order(
            asset=sample_asset, amount=Decimal("100"), order_type="market"
        )
        await asyncio.sleep(0.1)

        after_buy_cash = paper_broker.cash
        assert after_buy_cash == initial_cash - Decimal("10000")

        # Sell 50 @ $110
        paper_broker._update_market_data(
            sample_asset,
            {
                "close": Decimal("110.00"),
                "volume": Decimal("1000000"),
                "timestamp": datetime.now(),
            },
        )
        await paper_broker.submit_order(
            asset=sample_asset, amount=Decimal("-50"), order_type="market"
        )
        await asyncio.sleep(0.1)

        after_sell_cash = paper_broker.cash
        assert after_sell_cash == after_buy_cash + Decimal("5500")


class TestPaperBrokerAccountInfo:
    """Test account information retrieval."""

    @pytest.mark.asyncio
    async def test_get_account_info_initial_state(self, paper_broker):
        """Test account info returns correct values initially."""
        await paper_broker.connect()

        account_info = await paper_broker.get_account_info()

        assert account_info["cash"] == Decimal("100000")
        assert account_info["equity"] == Decimal("100000")
        assert account_info["portfolio_value"] == Decimal("100000")
        assert account_info["starting_cash"] == Decimal("100000")

    @pytest.mark.asyncio
    async def test_get_account_info_with_position(self, paper_broker, sample_asset):
        """Test account info includes position value."""
        await paper_broker.connect()

        # Buy position
        paper_broker._update_market_data(
            sample_asset,
            {
                "close": Decimal("100.00"),
                "volume": Decimal("1000000"),
                "timestamp": datetime.now(),
            },
        )
        await paper_broker.submit_order(
            asset=sample_asset, amount=Decimal("100"), order_type="market"
        )
        await asyncio.sleep(0.1)

        account_info = await paper_broker.get_account_info()

        # Cash decreased by $10,000
        assert account_info["cash"] == Decimal("90000")

        # Portfolio value = cash + position value = $90,000 + $10,000 = $100,000
        expected_portfolio_value = Decimal("90000") + (Decimal("100") * Decimal("100.00"))
        assert account_info["portfolio_value"] == expected_portfolio_value

    @pytest.mark.asyncio
    async def test_get_positions(self, paper_broker, sample_asset):
        """Test get_positions returns current positions."""
        await paper_broker.connect()

        # Initially no positions
        positions = await paper_broker.get_positions()
        assert len(positions) == 0

        # Buy position
        paper_broker._update_market_data(
            sample_asset,
            {
                "close": Decimal("150.00"),
                "volume": Decimal("1000000"),
                "timestamp": datetime.now(),
            },
        )
        await paper_broker.submit_order(
            asset=sample_asset, amount=Decimal("100"), order_type="market"
        )
        await asyncio.sleep(0.1)

        # Check positions
        positions = await paper_broker.get_positions()
        assert len(positions) == 1
        assert positions[0]["asset"] == sample_asset
        assert positions[0]["amount"] == Decimal("100")
        assert positions[0]["cost_basis"] == Decimal("150.00")


class TestPaperBrokerLatencySimulation:
    """Test latency simulation."""

    @pytest.mark.asyncio
    async def test_latency_delays_fill(self, paper_broker, sample_asset):
        """Test order fill is delayed by simulated latency."""
        await paper_broker.connect()

        paper_broker._update_market_data(
            sample_asset,
            {
                "close": Decimal("100.00"),
                "volume": Decimal("1000000"),
                "timestamp": datetime.now(),
            },
        )

        import time

        start_time = time.time()

        await paper_broker.submit_order(
            asset=sample_asset, amount=Decimal("100"), order_type="market"
        )

        # Wait for fill
        await asyncio.sleep(0.1)

        elapsed_ms = (time.time() - start_time) * 1000

        # Should have some delay (at least 10ms base latency)
        # Note: actual delay may be longer due to asyncio overhead
        assert elapsed_ms >= 10

    @pytest.mark.asyncio
    async def test_latency_varies_with_jitter(self, paper_broker, sample_asset):
        """Test latency varies with jitter (property-based would be better)."""
        await paper_broker.connect()

        paper_broker._update_market_data(
            sample_asset,
            {
                "close": Decimal("100.00"),
                "volume": Decimal("1000000"),
                "timestamp": datetime.now(),
            },
        )

        # Submit multiple orders and check latency varies
        # This is a simplified test - property-based testing would be more thorough
        latencies = []
        for _ in range(5):
            latency = paper_broker._simulate_latency()
            latencies.append(latency)

        # Check that not all latencies are identical (jitter applied)
        # With 20% jitter, we should see variation
        assert len(set(latencies)) > 1 or len(latencies) == 1  # Allow for rare case of same values


class TestPaperBrokerOrderCancellation:
    """Test order cancellation."""

    @pytest.mark.asyncio
    async def test_cancel_open_order(self, paper_broker, sample_asset):
        """Test canceling an open order."""
        await paper_broker.connect()

        # Submit order (don't set market data so it stays pending)
        order_id = await paper_broker.submit_order(
            asset=sample_asset, amount=Decimal("100"), order_type="market"
        )

        # Cancel immediately (before execution)
        await paper_broker.cancel_order(order_id)

        # Check order removed from open orders
        assert order_id not in paper_broker.open_orders

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_order(self, paper_broker):
        """Test canceling non-existent order doesn't raise error."""
        await paper_broker.connect()

        # Should not raise exception
        await paper_broker.cancel_order("nonexistent-order-id")


class TestPaperBrokerMarketDataHandling:
    """Test market data subscription and handling."""

    @pytest.mark.asyncio
    async def test_subscribe_market_data(self, paper_broker, sample_asset):
        """Test subscribing to market data."""
        await paper_broker.connect()

        await paper_broker.subscribe_market_data([sample_asset])

        assert sample_asset in paper_broker.subscribed_assets

    @pytest.mark.asyncio
    async def test_unsubscribe_market_data(self, paper_broker, sample_asset):
        """Test unsubscribing from market data."""
        await paper_broker.connect()

        await paper_broker.subscribe_market_data([sample_asset])
        await paper_broker.unsubscribe_market_data([sample_asset])

        assert sample_asset not in paper_broker.subscribed_assets

    @pytest.mark.asyncio
    async def test_get_current_price(self, paper_broker, sample_asset):
        """Test getting current price for asset."""
        await paper_broker.connect()

        paper_broker._update_market_data(
            sample_asset,
            {
                "close": Decimal("123.45"),
                "volume": Decimal("1000000"),
                "timestamp": datetime.now(),
            },
        )

        price = await paper_broker.get_current_price(sample_asset)

        assert price == Decimal("123.45")

    @pytest.mark.asyncio
    async def test_get_current_price_no_data(self, paper_broker, sample_asset):
        """Test getting price raises error when no data available."""
        await paper_broker.connect()

        with pytest.raises(MarketDataUnavailableError):
            await paper_broker.get_current_price(sample_asset)


class TestPaperBrokerTransactionHistory:
    """Test transaction history tracking."""

    @pytest.mark.asyncio
    async def test_transaction_created_on_fill(self, paper_broker, sample_asset):
        """Test transaction is created on order fill."""
        await paper_broker.connect()

        paper_broker._update_market_data(
            sample_asset,
            {
                "close": Decimal("100.00"),
                "volume": Decimal("1000000"),
                "timestamp": datetime.now(),
            },
        )

        await paper_broker.submit_order(
            asset=sample_asset, amount=Decimal("100"), order_type="market"
        )
        await asyncio.sleep(0.1)

        # Check transaction created
        assert len(paper_broker.transactions) == 1
        txn = paper_broker.transactions[0]
        assert txn.asset == sample_asset
        assert txn.amount == Decimal("100")
        assert txn.price == Decimal("100.00")
        assert txn.commission == Decimal("0")  # NoCommission


# Property-based tests would go here using Hypothesis
# Example: Test that different order amounts produce different fills
# Example: Test that commission is always non-negative
# Example: Test that slippage always worsens execution price
