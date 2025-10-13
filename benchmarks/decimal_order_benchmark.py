"""Per-module benchmarks for DecimalOrder execution.

Measures performance overhead of DecimalOrder processing compared to float-based
order execution.

Run with: pytest benchmarks/decimal_order_benchmark.py --benchmark-only
"""

from collections import namedtuple
from decimal import Decimal

import pytest

from rustybt.assets import Equity
from rustybt.finance.decimal.commission import PerDollarCommission, PerShareCommission
from rustybt.finance.decimal.order import DecimalOrder

# Test fixture for exchange info
ExchangeInfo = namedtuple("ExchangeInfo", ["canonical_name", "name", "country_code"])
TEST_EXCHANGE = ExchangeInfo(
    canonical_name="NYSE", name="New York Stock Exchange", country_code="US"
)


@pytest.mark.benchmark(group="order-creation")
def test_order_creation_1000_orders(benchmark):
    """Benchmark creating 1000 DecimalOrder instances.

    Expected: ~50-100 milliseconds for 1000 orders
    Target (Epic 7): <30 milliseconds
    """

    def create_orders():
        orders = []
        for i in range(1, 1001):
            asset = Equity(sid=i, exchange_info=TEST_EXCHANGE, symbol=f"STOCK{i}")
            order = DecimalOrder(
                dt=None,
                asset=asset,
                amount=Decimal("100"),
                limit=Decimal(str(50.0 + i * 0.01)),
            )
            orders.append(order)
        return orders

    result = benchmark(create_orders)

    assert len(result) == 1000


@pytest.mark.benchmark(group="order-value")
def test_order_value_calculation_1000(benchmark):
    """Benchmark order value calculation (price × quantity).

    Expected: ~20-50 milliseconds for 1000 calculations
    Target (Epic 7): <15 milliseconds
    """
    orders = []
    for i in range(1, 1001):
        asset = Equity(sid=i, exchange_info=TEST_EXCHANGE, symbol=f"STOCK{i}")
        order = DecimalOrder(
            dt=None,
            asset=asset,
            amount=Decimal("100"),
            limit=Decimal(str(50.0 + i * 0.01)),
        )
        orders.append(order)

    def calculate_order_values():
        values = []
        for order in orders:
            value = abs(order.amount) * order.limit
            values.append(value)
        return values

    result = benchmark(calculate_order_values)

    assert len(result) == 1000
    assert all(isinstance(v, Decimal) for v in result)


@pytest.mark.benchmark(group="commission-per-share")
def test_per_share_commission_1000_orders(benchmark):
    """Benchmark per-share commission calculation for 1000 orders.

    Expected: ~60-120 milliseconds for 1000 commissions
    Target (Epic 7): <40 milliseconds
    """
    commission_model = PerShareCommission(rate=Decimal("0.005"), minimum=Decimal("1.00"))

    orders = []
    for i in range(1, 1001):
        asset = Equity(sid=i, exchange_info=TEST_EXCHANGE, symbol=f"STOCK{i}")
        order = DecimalOrder(
            dt=None,
            asset=asset,
            amount=Decimal("100"),
            limit=Decimal(str(50.0 + i * 0.01)),
        )
        orders.append(order)

    def calculate_commissions():
        commissions = []
        for order in orders:
            fill_price = order.limit
            fill_amount = order.amount
            commission = commission_model.calculate(order, fill_price, fill_amount)
            commissions.append(commission)
        return commissions

    result = benchmark(calculate_commissions)

    assert len(result) == 1000
    assert all(isinstance(c, Decimal) for c in result)


@pytest.mark.benchmark(group="commission-per-dollar")
def test_per_dollar_commission_1000_orders(benchmark):
    """Benchmark per-dollar commission calculation for 1000 orders.

    Expected: ~50-100 milliseconds for 1000 commissions
    Target (Epic 7): <35 milliseconds
    """
    commission_model = PerDollarCommission(rate=Decimal("0.0015"))

    orders = []
    for i in range(1, 1001):
        asset = Equity(sid=i, exchange_info=TEST_EXCHANGE, symbol=f"STOCK{i}")
        order = DecimalOrder(
            dt=None,
            asset=asset,
            amount=Decimal("100"),
            limit=Decimal(str(50.0 + i * 0.01)),
        )
        orders.append(order)

    def calculate_commissions():
        commissions = []
        for order in orders:
            fill_price = order.limit
            fill_amount = order.amount
            commission = commission_model.calculate(order, fill_price, fill_amount)
            commissions.append(commission)
        return commissions

    result = benchmark(calculate_commissions)

    assert len(result) == 1000
    assert all(isinstance(c, Decimal) for c in result)


@pytest.mark.benchmark(group="order-fill-value")
def test_fill_value_with_commission_1000(benchmark):
    """Benchmark complete order fill calculation (value + commission).

    Expected: ~80-150 milliseconds for 1000 orders
    Target (Epic 7): <50 milliseconds
    """
    commission_model = PerShareCommission(rate=Decimal("0.005"), minimum=Decimal("1.00"))

    orders = []
    for i in range(1, 1001):
        asset = Equity(sid=i, exchange_info=TEST_EXCHANGE, symbol=f"STOCK{i}")
        order = DecimalOrder(
            dt=None,
            asset=asset,
            amount=Decimal("100"),
            limit=Decimal(str(50.0 + i * 0.01)),
        )
        orders.append(order)

    def calculate_fill_costs():
        results = []
        for order in orders:
            fill_price = order.limit
            fill_amount = order.amount
            fill_value = abs(fill_amount) * fill_price
            commission = commission_model.calculate(order, fill_price, fill_amount)
            total_cost = fill_value + commission
            results.append(total_cost)
        return results

    result = benchmark(calculate_fill_costs)

    assert len(result) == 1000
    assert all(isinstance(cost, Decimal) for cost in result)


@pytest.mark.benchmark(group="order-fractional")
def test_fractional_quantity_orders_1000(benchmark):
    """Benchmark orders with fractional quantities (crypto use case).

    Tests precision handling for fractional shares/crypto.
    Expected: ~60-120 milliseconds for 1000 orders
    """

    def create_fractional_orders():
        orders = []
        for i in range(1, 1001):
            asset = Equity(sid=i, exchange_info=TEST_EXCHANGE, symbol=f"CRYPTO{i}")
            # Fractional quantities like 0.00000001 BTC
            order = DecimalOrder(
                dt=None,
                asset=asset,
                amount=Decimal("0.00000001") * i,
                limit=Decimal(str(50000.0 + i * 10)),
            )
            orders.append(order)
        return orders

    result = benchmark(create_fractional_orders)

    assert len(result) == 1000
    # Verify precision is maintained
    assert result[0].amount == Decimal("0.00000001")


@pytest.mark.benchmark(group="order-arithmetic")
def test_order_arithmetic_operations_10000(benchmark):
    """Benchmark basic Decimal arithmetic in order processing.

    Measures pure Decimal multiplication and addition overhead.
    Expected: ~10-30 milliseconds for 10000 operations
    Target (Epic 7): <5 milliseconds (Rust optimization)
    """

    def arithmetic_operations():
        results = []
        for i in range(1, 10001):
            price = Decimal(str(50.0 + i * 0.01))
            quantity = Decimal("100")
            commission_rate = Decimal("0.005")

            # Typical order calculations
            order_value = price * quantity
            commission = order_value * commission_rate
            total_cost = order_value + commission

            results.append(total_cost)
        return results

    result = benchmark(arithmetic_operations)

    assert len(result) == 10000
    assert all(isinstance(v, Decimal) for v in result)
