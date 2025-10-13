"""Simple paper trading example demonstrating PaperBroker usage.

This example shows how to use PaperBroker to simulate live trading
without risking real capital. It demonstrates:

1. PaperBroker initialization with commission/slippage models
2. Connecting to paper broker
3. Subscribing to market data
4. Submitting orders (market, limit)
5. Tracking positions and account balance
6. Transaction history

Usage:
    python examples/paper_trading_simple.py
"""

import asyncio
from datetime import datetime
from decimal import Decimal

from rustybt.assets import Equity, ExchangeInfo
from rustybt.finance.decimal.commission import PerShareCommission
from rustybt.finance.decimal.slippage import FixedBasisPointsSlippage
from rustybt.live.brokers import PaperBroker


async def main():
    """Run simple paper trading example."""
    print("=" * 80)
    print("RustyBT Paper Trading Example")
    print("=" * 80)
    print()

    # Create sample assets
    exchange = ExchangeInfo("NASDAQ", "NASDAQ", "US")
    aapl = Equity(1, exchange, symbol="AAPL")
    spy = Equity(2, exchange, symbol="SPY")

    # Initialize PaperBroker with realistic settings
    print("Initializing PaperBroker...")
    broker = PaperBroker(
        starting_cash=Decimal("100000"),  # Start with $100k
        commission_model=PerShareCommission(
            rate=Decimal("0.005"),  # $0.005 per share
            minimum=Decimal("1.00"),  # $1 minimum per order
        ),
        slippage_model=FixedBasisPointsSlippage(
            basis_points=Decimal("5")  # 5 bps (0.05%) slippage
        ),
        order_latency_ms=100,  # 100ms order latency
        volume_limit_pct=Decimal("0.025"),  # Max 2.5% of bar volume
    )
    print(f"  Starting cash: ${broker.starting_cash}")
    print("  Commission: PerShareCommission($0.005/share, $1 min)")
    print("  Slippage: FixedBasisPointsSlippage(5 bps)")
    print()

    # Connect to paper broker
    print("Connecting to paper broker...")
    await broker.connect()
    print("  Connected!")
    print()

    # Subscribe to market data
    print("Subscribing to market data...")
    await broker.subscribe_market_data([aapl, spy])
    print("  Subscribed to AAPL, SPY")
    print()

    # Simulate market data updates
    print("Simulating market data...")
    broker._update_market_data(
        aapl,
        {
            "open": Decimal("150.00"),
            "high": Decimal("152.00"),
            "low": Decimal("149.00"),
            "close": Decimal("151.00"),
            "volume": Decimal("50000000"),  # 50M shares volume
            "timestamp": datetime.now(),
        },
    )
    broker._update_market_data(
        spy,
        {
            "open": Decimal("450.00"),
            "high": Decimal("452.00"),
            "low": Decimal("449.00"),
            "close": Decimal("451.00"),
            "volume": Decimal("100000000"),  # 100M shares volume
            "timestamp": datetime.now(),
        },
    )
    print(f"  AAPL: ${await broker.get_current_price(aapl)}")
    print(f"  SPY: ${await broker.get_current_price(spy)}")
    print()

    # Example 1: Market buy order
    print("Example 1: Market buy order (AAPL)")
    print("-" * 40)
    order_id_1 = await broker.submit_order(
        asset=aapl,
        amount=Decimal("100"),  # Buy 100 shares
        order_type="market",
    )
    print("  Submitted market buy: 100 shares AAPL")
    print(f"  Order ID: {order_id_1}")

    # Wait for fill
    await asyncio.sleep(0.2)

    # Check account after first order
    account_info = await broker.get_account_info()
    print(f"  Cash after buy: ${account_info['cash']:.2f}")
    print(f"  Portfolio value: ${account_info['portfolio_value']:.2f}")

    # Check position
    positions = await broker.get_positions()
    if positions:
        pos = positions[0]
        print(f"  Position: {pos['amount']} shares @ ${pos['cost_basis']:.2f}")
        print(f"  Market value: ${pos['market_value']:.2f}")
        print(f"  Unrealized P&L: ${pos['unrealized_pnl']:.2f}")
    print()

    # Example 2: Limit buy order
    print("Example 2: Limit buy order (SPY)")
    print("-" * 40)
    order_id_2 = await broker.submit_order(
        asset=spy,
        amount=Decimal("50"),  # Buy 50 shares
        order_type="limit",
        limit_price=Decimal("452.00"),  # Limit at $452 (above current price)
    )
    print("  Submitted limit buy: 50 shares SPY @ $452")
    print(f"  Order ID: {order_id_2}")

    # Wait for fill
    await asyncio.sleep(0.2)

    # Check account after second order
    account_info = await broker.get_account_info()
    print(f"  Cash after buy: ${account_info['cash']:.2f}")
    print(f"  Portfolio value: ${account_info['portfolio_value']:.2f}")
    print()

    # Example 3: Sell part of position
    print("Example 3: Market sell order (AAPL)")
    print("-" * 40)

    # Update market price (simulate price increase)
    broker._update_market_data(
        aapl,
        {
            "close": Decimal("155.00"),  # Price increased
            "volume": Decimal("50000000"),
            "timestamp": datetime.now(),
        },
    )
    print(f"  AAPL price updated to: ${await broker.get_current_price(aapl)}")

    order_id_3 = await broker.submit_order(
        asset=aapl,
        amount=Decimal("-50"),  # Sell 50 shares
        order_type="market",
    )
    print("  Submitted market sell: 50 shares AAPL")
    print(f"  Order ID: {order_id_3}")

    # Wait for fill
    await asyncio.sleep(0.2)

    # Final account summary
    print()
    print("Final Account Summary")
    print("=" * 80)
    account_info = await broker.get_account_info()
    print(f"  Starting cash: ${broker.starting_cash:.2f}")
    print(f"  Current cash: ${account_info['cash']:.2f}")
    print(f"  Portfolio value: ${account_info['portfolio_value']:.2f}")
    print(f"  Total P&L: ${account_info['portfolio_value'] - broker.starting_cash:.2f}")
    print()

    # Show positions
    positions = await broker.get_positions()
    print("Current Positions:")
    for pos in positions:
        symbol = pos["asset"].symbol if hasattr(pos["asset"], "symbol") else str(pos["asset"])
        print(f"  {symbol}: {pos['amount']} shares @ ${pos['cost_basis']:.2f}")
        print(f"    Market value: ${pos['market_value']:.2f}")
        print(f"    Unrealized P&L: ${pos['unrealized_pnl']:.2f}")
    print()

    # Show transaction history
    print("Transaction History:")
    print(f"  Total transactions: {len(broker.transactions)}")
    for i, txn in enumerate(broker.transactions, 1):
        symbol = txn.asset.symbol if hasattr(txn.asset, "symbol") else str(txn.asset)
        side = "BUY" if txn.amount > Decimal("0") else "SELL"
        print(
            f"  {i}. {side} {abs(txn.amount)} {symbol} @ ${txn.price:.2f} (commission: ${txn.commission:.2f})"
        )
    print()

    # Disconnect
    await broker.disconnect()
    print("Disconnected from paper broker")
    print()
    print("=" * 80)
    print("Paper Trading Example Complete!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
