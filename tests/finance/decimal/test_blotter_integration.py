"""Integration tests for DecimalBlotter with DecimalLedger.

These tests validate the complete order execution flow:
submit order → fill → verify ledger state

This ensures end-to-end integration maintains Decimal precision throughout
the order lifecycle including ledger updates.
"""

from datetime import datetime
from decimal import Decimal

import pytest

from rustybt.finance.decimal import (
    DecimalBlotter,
    DecimalLedger,
    FixedBasisPointsSlippage,
    FixedSlippage,
    PerShareCommission,
    PerTradeCommission,
)


@pytest.fixture
def ledger():
    """Create DecimalLedger with starting cash."""
    return DecimalLedger(starting_cash=Decimal("100000.00"))


@pytest.fixture
def blotter(ledger):
    """Create DecimalBlotter with commission and slippage models."""
    return DecimalBlotter(
        commission_model=PerShareCommission(rate=Decimal("0.005"), minimum=Decimal("1.00")),
        slippage_model=FixedBasisPointsSlippage(basis_points=Decimal("10")),  # 0.1%
    )


def test_market_order_execution_updates_ledger(blotter, ledger, equity_asset):
    """Test market order execution updates ledger with Decimal precision.

    Flow: submit order → fill → verify cash decreased and position created.
    """
    blotter.set_current_dt(datetime.now())

    # Initial state
    initial_cash = ledger.cash
    assert initial_cash == Decimal("100000.00")
    assert equity_asset not in ledger.positions

    # Submit buy order
    order_id = blotter.order(
        asset=equity_asset,
        amount=Decimal("100"),
        order_type="market",
    )

    order = blotter.get_order(order_id)
    assert order is not None

    # Execute order
    market_price = Decimal("150.00")
    transaction = blotter.process_order(order, market_price)

    assert transaction is not None

    # Calculate expected costs
    # Slippage: 0.1% = market_price * 1.001
    execution_price = Decimal("150.15")  # 150 * 1.001
    order_value = Decimal("100") * execution_price  # 15015.00
    commission = max(Decimal("100") * Decimal("0.005"), Decimal("1.00"))  # max(0.50, 1.00) = 1.00
    slippage_cost = (execution_price - market_price) * Decimal("100")  # 15.00

    total_cost = order_value + commission + slippage_cost

    # Verify transaction values
    assert transaction.price == execution_price
    assert transaction.amount == Decimal("100")
    assert transaction.commission == commission
    assert isinstance(transaction.total_cost, Decimal)

    # Update ledger manually (blotter doesn't auto-update in this impl)
    ledger.process_transaction(transaction)

    # Verify ledger state
    assert equity_asset in ledger.positions
    position = ledger.positions[equity_asset]
    assert position.amount == Decimal("100")

    # Cash should decrease by total cost
    expected_cash = initial_cash - total_cost
    assert ledger.cash == expected_cash


def test_partial_fills_update_ledger_incrementally(blotter, ledger, equity_asset):
    """Test partial fills update ledger with exact precision.

    Flow: submit order → partial fill 1 → partial fill 2 → verify cumulative ledger state.
    """
    blotter.set_current_dt(datetime.now())

    # Submit order for 100 shares
    order_id = blotter.order(
        asset=equity_asset,
        amount=Decimal("100"),
        order_type="limit",
        limit_price=Decimal("150.00"),
    )

    order = blotter.get_order(order_id)
    initial_cash = ledger.cash

    # First partial fill: 30 shares at $150.00
    txn1 = blotter.process_partial_fill(
        order,
        fill_amount=Decimal("30"),
        fill_price=Decimal("150.00"),
    )

    ledger.process_transaction(txn1)

    # Verify first fill
    assert equity_asset in ledger.positions
    assert ledger.positions[equity_asset].amount == Decimal("30")

    fill1_cost = Decimal("30") * Decimal("150.00") + txn1.commission
    assert ledger.cash == initial_cash - fill1_cost

    # Second partial fill: 70 shares at $150.50
    txn2 = blotter.process_partial_fill(
        order,
        fill_amount=Decimal("70"),
        fill_price=Decimal("150.50"),
    )

    ledger.process_transaction(txn2)

    # Verify cumulative state
    assert ledger.positions[equity_asset].amount == Decimal("100")

    fill2_cost = Decimal("70") * Decimal("150.50") + txn2.commission
    total_cost = fill1_cost + fill2_cost
    expected_cash = initial_cash - total_cost

    assert ledger.cash == expected_cash

    # Verify order is fully filled
    assert order.filled == Decimal("100")
    assert order.remaining == Decimal("0")


def test_buy_then_sell_updates_ledger_correctly(blotter, ledger, equity_asset):
    """Test buy followed by sell updates ledger position and cash.

    Flow: buy 100 shares → sell 100 shares → verify position closed and cash updated.
    """
    blotter.set_current_dt(datetime.now())

    # Buy 100 shares
    buy_order_id = blotter.order(
        asset=equity_asset,
        amount=Decimal("100"),
        order_type="market",
    )

    buy_order = blotter.get_order(buy_order_id)
    buy_txn = blotter.process_order(buy_order, Decimal("150.00"))

    ledger.process_transaction(buy_txn)

    # Verify buy
    assert ledger.positions[equity_asset].amount == Decimal("100")
    cash_after_buy = ledger.cash

    # Sell 100 shares
    sell_order_id = blotter.order(
        asset=equity_asset,
        amount=Decimal("-100"),  # Negative = sell
        order_type="market",
    )

    sell_order = blotter.get_order(sell_order_id)
    sell_txn = blotter.process_order(sell_order, Decimal("155.00"))

    ledger.process_transaction(sell_txn)

    # Verify sell
    assert ledger.positions[equity_asset].amount == Decimal("0")

    # Cash should increase by sell proceeds minus costs
    # (we don't verify exact amount due to commission/slippage complexity,
    # but we verify cash increased from after-buy state)
    assert ledger.cash > cash_after_buy


def test_insufficient_funds_prevents_order_execution(blotter, equity_asset):
    """Test that ledger prevents execution when insufficient funds.

    Note: This test validates ledger behavior, not blotter behavior.
    Blotter submits orders; ledger enforces cash constraints.
    """
    # Create ledger with limited cash
    small_ledger = DecimalLedger(starting_cash=Decimal("1000.00"))
    blotter.set_current_dt(datetime.now())

    # Submit order that exceeds cash
    order_id = blotter.order(
        asset=equity_asset,
        amount=Decimal("100"),  # 100 shares * $150 = $15,000
        order_type="market",
    )

    order = blotter.get_order(order_id)
    txn = blotter.process_order(order, Decimal("150.00"))

    # Blotter creates transaction, but ledger should reject it
    from rustybt.finance.decimal import InsufficientFundsError

    with pytest.raises(InsufficientFundsError):
        small_ledger.process_transaction(txn)


def test_commission_model_integration_with_ledger(ledger, equity_asset):
    """Test that different commission models integrate correctly with ledger."""
    # Test with PerTradeCommission (flat fee)
    flat_fee_blotter = DecimalBlotter(
        commission_model=PerTradeCommission(cost=Decimal("5.00")),
        slippage_model=FixedSlippage(slippage=Decimal("0.10")),
    )

    flat_fee_blotter.set_current_dt(datetime.now())

    order_id = flat_fee_blotter.order(
        asset=equity_asset,
        amount=Decimal("100"),
        order_type="market",
    )

    order = flat_fee_blotter.get_order(order_id)
    txn = flat_fee_blotter.process_order(order, Decimal("150.00"))

    # Verify commission is exactly $5
    assert txn.commission == Decimal("5.00")

    ledger.process_transaction(txn)

    # Verify ledger updated correctly
    assert equity_asset in ledger.positions


def test_multiple_assets_in_ledger_via_blotter(blotter, ledger, equity_asset, crypto_asset):
    """Test trading multiple assets updates ledger with separate positions."""
    blotter.set_current_dt(datetime.now())

    # Buy equity
    equity_order_id = blotter.order(
        asset=equity_asset,
        amount=Decimal("100"),
        order_type="market",
    )

    equity_order = blotter.get_order(equity_order_id)
    equity_txn = blotter.process_order(equity_order, Decimal("150.00"))
    ledger.process_transaction(equity_txn)

    # Buy crypto
    crypto_order_id = blotter.order(
        asset=crypto_asset,
        amount=Decimal("1.00"),
        order_type="market",
    )

    crypto_order = blotter.get_order(crypto_order_id)
    crypto_txn = blotter.process_order(crypto_order, Decimal("50000.00"))
    ledger.process_transaction(crypto_txn)

    # Verify both positions exist
    assert equity_asset in ledger.positions
    assert crypto_asset in ledger.positions

    assert ledger.positions[equity_asset].amount == Decimal("100")
    assert ledger.positions[crypto_asset].amount == Decimal("1.00")


def test_order_cancellation_does_not_update_ledger(blotter, ledger, equity_asset):
    """Test that cancelling an unfilled order doesn't affect ledger."""
    blotter.set_current_dt(datetime.now())

    initial_cash = ledger.cash

    # Submit order
    order_id = blotter.order(
        asset=equity_asset,
        amount=Decimal("100"),
        order_type="limit",
        limit_price=Decimal("150.00"),
    )

    # Cancel before fill
    blotter.cancel_order(order_id)

    # Verify ledger unchanged
    assert ledger.cash == initial_cash
    assert equity_asset not in ledger.positions


def test_limit_order_only_executes_at_favorable_price(blotter, ledger, equity_asset):
    """Test limit order respects price limits before ledger update."""
    blotter.set_current_dt(datetime.now())

    # Submit buy limit at $150
    order_id = blotter.order(
        asset=equity_asset,
        amount=Decimal("100"),
        order_type="limit",
        limit_price=Decimal("150.00"),
    )

    order = blotter.get_order(order_id)

    # Try to execute at $151 (above limit for buy)
    txn = blotter.process_order(order, Decimal("151.00"))

    # Should not execute (price above buy limit)
    assert txn is None

    # Try at $150 (at limit)
    txn = blotter.process_order(order, Decimal("150.00"))

    # Should execute
    assert txn is not None
    ledger.process_transaction(txn)

    # Verify ledger updated
    assert equity_asset in ledger.positions


def test_blotter_transaction_history_matches_ledger_updates(blotter, ledger, equity_asset):
    """Test that blotter's transaction history matches ledger's transaction log."""
    blotter.set_current_dt(datetime.now())

    # Execute multiple trades
    for i in range(3):
        order_id = blotter.order(
            asset=equity_asset,
            amount=Decimal("10") * (i + 1),
            order_type="market",
        )

        order = blotter.get_order(order_id)
        txn = blotter.process_order(order, Decimal("150.00") + i)
        ledger.process_transaction(txn)

    # Verify blotter and ledger have same transaction count
    blotter_txns = blotter.get_transactions()
    ledger_txns = ledger.get_transactions()

    assert len(blotter_txns) == len(ledger_txns) == 3

    # Verify transaction values match
    for b_txn, l_txn in zip(blotter_txns, ledger_txns, strict=False):
        assert b_txn.order_id == l_txn.order_id
        assert b_txn.amount == l_txn.amount
        assert b_txn.price == l_txn.price
        assert b_txn.commission == l_txn.commission
