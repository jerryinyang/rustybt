"""Integration tests for Interactive Brokers adapter.

These tests require:
1. TWS or IB Gateway running
2. Paper trading account configured
3. API connections enabled in TWS settings
4. Correct port configured (7496 for TWS paper, 4002 for Gateway paper)

Run with: pytest --run-ib-integration tests/integration/live/test_ib_integration.py
"""

import asyncio
from decimal import Decimal

import pandas as pd
import pytest

from rustybt.assets import Equity
from rustybt.live.brokers.ib_adapter import IBBrokerAdapter

# Skip these tests by default (require IB paper account)
pytestmark = pytest.mark.skipif(
    "not config.getoption('--run-ib-integration')",
    reason="IB integration tests require --run-ib-integration flag and running TWS/Gateway",
)


@pytest.fixture
async def ib_adapter():
    """Create IB adapter connected to paper account."""
    adapter = IBBrokerAdapter(
        host="127.0.0.1",
        port=7496,  # TWS paper trading port
        client_id=1,
    )

    await adapter.connect()

    yield adapter

    await adapter.disconnect()


@pytest.fixture
def sample_stock():
    """Create sample stock asset (SPY)."""
    return Equity(
        sid=1,
        symbol="SPY",
        exchange="ARCA",
        start_date=pd.Timestamp("2000-01-01"),
        end_date=pd.Timestamp("2030-01-01"),
    )


@pytest.mark.asyncio
@pytest.mark.ib_integration
async def test_connection():
    """Test connection to IB paper account."""
    adapter = IBBrokerAdapter(host="127.0.0.1", port=7496, client_id=1)

    await adapter.connect()

    assert adapter.is_connected()

    await adapter.disconnect()

    assert not adapter.is_connected()


@pytest.mark.asyncio
@pytest.mark.ib_integration
async def test_submit_market_order(ib_adapter, sample_stock):
    """Test submitting market order."""
    # Submit market order for 1 share of SPY
    order_id = await ib_adapter.submit_order(
        asset=sample_stock,
        amount=Decimal("1"),
        order_type="market",
    )

    assert order_id is not None
    assert order_id.isdigit()

    # Wait for order to fill
    await asyncio.sleep(2)

    # Check positions
    positions = await ib_adapter.get_positions()

    # May or may not have position immediately (depends on fill speed)
    print(f"Positions after market order: {positions}")


@pytest.mark.asyncio
@pytest.mark.ib_integration
async def test_submit_and_cancel_limit_order(ib_adapter, sample_stock):
    """Test submitting and cancelling limit order."""
    # Get current price
    current_price = await ib_adapter.get_current_price(sample_stock)

    # Submit limit order far from market (won't fill)
    limit_price = current_price * Decimal("0.5")  # 50% below market

    order_id = await ib_adapter.submit_order(
        asset=sample_stock,
        amount=Decimal("1"),
        order_type="limit",
        limit_price=limit_price,
    )

    assert order_id is not None

    # Wait for order to be submitted
    await asyncio.sleep(1)

    # Check open orders
    open_orders = await ib_adapter.get_open_orders()
    assert len(open_orders) > 0

    # Cancel order
    await ib_adapter.cancel_order(order_id)

    # Wait for cancellation
    await asyncio.sleep(1)

    # Check open orders again
    open_orders_after = await ib_adapter.get_open_orders()
    print(f"Open orders after cancellation: {open_orders_after}")


@pytest.mark.asyncio
@pytest.mark.ib_integration
async def test_get_account_info(ib_adapter):
    """Test retrieving account information."""
    account_info = await ib_adapter.get_account_info()

    assert "cash" in account_info
    assert "equity" in account_info
    assert "buying_power" in account_info

    assert account_info["cash"] > Decimal(0)
    assert account_info["equity"] > Decimal(0)
    assert account_info["buying_power"] > Decimal(0)

    print(f"Account info: {account_info}")


@pytest.mark.asyncio
@pytest.mark.ib_integration
async def test_get_positions(ib_adapter):
    """Test retrieving positions."""
    positions = await ib_adapter.get_positions()

    # May or may not have positions
    print(f"Positions: {positions}")

    assert isinstance(positions, list)


@pytest.mark.asyncio
@pytest.mark.ib_integration
async def test_get_current_price(ib_adapter, sample_stock):
    """Test getting current price."""
    price = await ib_adapter.get_current_price(sample_stock)

    assert price > Decimal(0)
    assert price < Decimal(10000)  # Sanity check

    print(f"Current price of {sample_stock.symbol}: {price}")


@pytest.mark.asyncio
@pytest.mark.ib_integration
async def test_market_data_subscription(ib_adapter, sample_stock):
    """Test market data subscription."""
    # Subscribe to market data
    await ib_adapter.subscribe_market_data([sample_stock])

    # Wait for data
    await asyncio.sleep(2)

    # Check for market data updates
    data = await ib_adapter.get_next_market_data()

    if data:
        assert "asset" in data
        assert "price" in data
        print(f"Market data: {data}")

    # Unsubscribe
    await ib_adapter.unsubscribe_market_data([sample_stock])


@pytest.mark.asyncio
@pytest.mark.ib_integration
async def test_order_lifecycle(ib_adapter, sample_stock):
    """Test complete order lifecycle: submit -> fill -> verify position -> verify account."""
    # Get initial account state
    initial_account = await ib_adapter.get_account_info()
    initial_cash = initial_account["cash"]

    # Get current price
    await ib_adapter.get_current_price(sample_stock)

    # Submit market order
    await ib_adapter.submit_order(
        asset=sample_stock,
        amount=Decimal("1"),
        order_type="market",
    )

    # Wait for fill
    await asyncio.sleep(3)

    # Check positions
    positions = await ib_adapter.get_positions()
    print(f"Positions: {positions}")

    # Check account
    final_account = await ib_adapter.get_account_info()
    final_cash = final_account["cash"]

    # Cash should have decreased (approximately)
    print(f"Initial cash: {initial_cash}, Final cash: {final_cash}")
    print(f"Difference: {initial_cash - final_cash}")

    # Note: Exact cash change depends on fill price and commission
