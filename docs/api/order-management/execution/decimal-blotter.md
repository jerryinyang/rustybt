# DecimalBlotter: Order Management System

**Module**: `rustybt.finance.decimal.blotter`
**Source**: `rustybt/finance/decimal/blotter.py`
**Verified**: 2025-10-16

## Overview

`DecimalBlotter` is RustyBT's production-grade order management system with Decimal precision for financial calculations. It handles the complete order lifecycle from submission through execution, fill processing, and transaction creation.

**Key Responsibilities**:
- Accept and validate order submissions
- Track open and closed orders
- Execute orders against market data
- Calculate commission and slippage with Decimal precision
- Create transaction records
- Manage order cancellations

**Financial Integrity**: All calculations use Python's `Decimal` type to eliminate float rounding errors and ensure audit-compliant precision.

---

## Architecture

```
Strategy Algorithm
      │
      │ order(asset, amount, ...)
      ▼
┌────────────────────────────────────┐
│       DecimalBlotter               │
│                                    │
│  ┌──────────────────────────────┐ │
│  │  Order Submission            │ │
│  │  • Validate parameters       │ │
│  │  • Create DecimalOrder       │ │
│  │  • Track in open_orders      │ │
│  └──────────────────────────────┘ │
│                                    │
│  ┌──────────────────────────────┐ │
│  │  Order Processing            │ │
│  │  • Check triggers            │ │
│  │  • Apply slippage model      │ │
│  │  • Calculate commission      │ │
│  │  • Create transaction        │ │
│  └──────────────────────────────┘ │
│                                    │
│  ┌──────────────────────────────┐ │
│  │  Order Tracking              │ │
│  │  • Track fills               │ │
│  │  • Update order status       │ │
│  │  • Maintain history          │ │
│  └──────────────────────────────┘ │
└────────────────────────────────────┘
```

---

## DecimalBlotter Class

**Source**: `rustybt/finance/decimal/blotter.py:23`

### Initialization

```python
from decimal import Decimal
from rustybt.finance.decimal.blotter import DecimalBlotter
from rustybt.finance.decimal.commission import PerShareCommission
from rustybt.finance.decimal.slippage import FixedBasisPointsSlippage

blotter = DecimalBlotter(
    commission_model=PerShareCommission(Decimal("0.005")),
    slippage_model=FixedBasisPointsSlippage(Decimal("10")),
    config=None  # Uses default DecimalConfig
)
```

**Constructor Signature** (source line 45-60):

```python
def __init__(
    self,
    commission_model: DecimalCommissionModel | None = None,
    slippage_model: DecimalSlippageModel | None = None,
    config: DecimalConfig | None = None,
) -> None:
```

**Parameters**:
- `commission_model` (`DecimalCommissionModel | None`): Commission calculation model. Defaults to `NoCommission()` if not provided.
- `slippage_model` (`DecimalSlippageModel | None`): Slippage calculation model. Defaults to `NoSlippage()` if not provided.
- `config` (`DecimalConfig | None`): Decimal precision configuration. Uses `DecimalConfig.get_instance()` if not provided.

**Attributes** (source lines 62-71):

| Attribute | Type | Description |
|-----------|------|-------------|
| `commission_model` | `DecimalCommissionModel` | Commission calculation model |
| `slippage_model` | `DecimalSlippageModel` | Slippage calculation model |
| `config` | `DecimalConfig` | Decimal precision configuration |
| `open_orders` | `dict[Asset, list[DecimalOrder]]` | Open orders grouped by asset |
| `orders` | `dict[str, DecimalOrder]` | All orders indexed by order ID |
| `new_orders` | `list[DecimalOrder]` | Orders placed/updated since last check |
| `transactions` | `list[DecimalTransaction]` | Transaction history |
| `current_dt` | `datetime | None` | Current datetime for order processing |

### Example: Basic Initialization

```python
from decimal import Decimal
from rustybt.finance.decimal.blotter import DecimalBlotter
from rustybt.finance.decimal.commission import PerShareCommission, PerDollarCommission
from rustybt.finance.decimal.slippage import FixedBasisPointsSlippage, VolumeShareSlippage
from rustybt.finance.decimal.config import DecimalConfig

# Example 1: Simple blotter with default models
blotter_simple = DecimalBlotter()
print(blotter_simple)
# Output: DecimalBlotter(commission_model=NoCommission(), slippage_model=NoSlippage(), ...)

# Example 2: Realistic equity blotter
equity_blotter = DecimalBlotter(
    commission_model=PerShareCommission(cost_per_share=Decimal("0.005"), min_cost=Decimal("1.00")),
    slippage_model=FixedBasisPointsSlippage(basis_points=Decimal("5"))
)

# Example 3: Volume-aware blotter for large orders
institutional_blotter = DecimalBlotter(
    commission_model=PerDollarCommission(cost_per_dollar=Decimal("0.0001")),
    slippage_model=VolumeShareSlippage(
        volume_limit=Decimal("0.025"),  # 2.5% of bar volume
        price_impact=Decimal("0.1")
    )
)

# Example 4: Custom precision configuration
from rustybt.finance.decimal.config import DecimalConfig

config = DecimalConfig(
    price_precision=Decimal("0.01"),      # Penny increments
    quantity_precision=Decimal("1"),       # Whole shares
    commission_precision=Decimal("0.01")   # Penny commissions
)
custom_blotter = DecimalBlotter(config=config)
```

---

## Order Submission

### order()

Submit an order to the blotter for execution.

**Method Signature** (source lines 87-141):

```python
def order(
    self,
    asset: Asset,
    amount: Decimal,
    order_type: str = "market",
    limit_price: Decimal | None = None,
    stop_price: Decimal | None = None,
    order_id: str | None = None,
) -> str:
```

**Parameters**:
- `asset` (`Asset`): Asset to trade
- `amount` (`Decimal`): Order quantity (positive=buy, negative=sell)
- `order_type` (`str`): Order type - "market", "limit", "stop", "stop_limit". Default: "market"
- `limit_price` (`Decimal | None`): Limit price for limit/stop-limit orders. Required if `order_type="limit"` or `"stop_limit"`
- `stop_price` (`Decimal | None`): Stop price for stop/stop-limit orders. Required if `order_type="stop"` or `"stop_limit"`
- `order_id` (`str | None`): Optional custom order ID. Auto-generated UUID if not provided

**Returns**: `str` - Order ID

**Raises**:
- `InvalidQuantityError`: If `amount == Decimal("0")`
- `OrderError`: If order parameters are invalid (e.g., limit_price missing for limit order)

**Source Verification** (lines 113-114):
```python
if amount == Decimal("0"):
    raise InvalidQuantityError("Order amount cannot be zero")
```

### Example: Market Orders

```python
from decimal import Decimal
from rustybt.assets import Equity
from rustybt.finance.decimal.blotter import DecimalBlotter
from datetime import datetime

# Setup
blotter = DecimalBlotter()
blotter.set_current_dt(datetime(2024, 1, 15, 9, 30))
equity = Equity(1, exchange='NYSE', symbol='AAPL')

# Example 1: Simple buy market order
order_id = blotter.order(
    asset=equity,
    amount=Decimal("100")  # Buy 100 shares
)
print(f"Order placed: {order_id}")

# Example 2: Sell market order
sell_order_id = blotter.order(
    asset=equity,
    amount=Decimal("-50"),  # Sell 50 shares (negative amount)
    order_type="market"
)

# Example 3: Large institutional order
large_order_id = blotter.order(
    asset=equity,
    amount=Decimal("10000"),  # 10,000 shares
    order_id="INST_001"  # Custom order ID for tracking
)
```

### Example: Limit Orders

```python
# Example 1: Buy limit order
buy_limit_id = blotter.order(
    asset=equity,
    amount=Decimal("100"),
    order_type="limit",
    limit_price=Decimal("150.50")  # Buy at $150.50 or better
)

# Example 2: Sell limit order
sell_limit_id = blotter.order(
    asset=equity,
    amount=Decimal("-100"),
    order_type="limit",
    limit_price=Decimal("155.00")  # Sell at $155.00 or better
)

# Example 3: Tight limit order (day trading)
day_trade_id = blotter.order(
    asset=equity,
    amount=Decimal("500"),
    order_type="limit",
    limit_price=Decimal("149.99")  # Just below round number
)
```

### Example: Stop Orders

```python
# Example 1: Stop-loss order
stop_loss_id = blotter.order(
    asset=equity,
    amount=Decimal("-100"),  # Sell to close
    order_type="stop",
    stop_price=Decimal("145.00")  # Sell if price falls to $145
)

# Example 2: Buy stop (breakout strategy)
breakout_id = blotter.order(
    asset=equity,
    amount=Decimal("100"),
    order_type="stop",
    stop_price=Decimal("160.00")  # Buy if price breaks $160
)

# Example 3: Stop-limit order (controlled exit)
stop_limit_id = blotter.order(
    asset=equity,
    amount=Decimal("-100"),
    order_type="stop_limit",
    stop_price=Decimal("145.00"),  # Trigger at $145
    limit_price=Decimal("144.50")  # But only sell at $144.50 or better
)
```

### Example: Error Handling

```python
from rustybt.finance.decimal.order import InvalidQuantityError, OrderError

# Example 1: Zero quantity error
try:
    invalid_order = blotter.order(
        asset=equity,
        amount=Decimal("0")  # Invalid!
    )
except InvalidQuantityError as e:
    print(f"Order rejected: {e}")
    # Output: Order rejected: Order amount cannot be zero

# Example 2: Missing limit price
try:
    invalid_limit = blotter.order(
        asset=equity,
        amount=Decimal("100"),
        order_type="limit"
        # Missing limit_price parameter
    )
except OrderError as e:
    print(f"Order rejected: {e}")

# Example 3: Defensive order placement
def safe_order_submission(blotter, asset, amount, **kwargs):
    """Place order with comprehensive error handling."""
    try:
        # Validate amount
        if amount == Decimal("0"):
            raise ValueError("Amount cannot be zero")

        # Place order
        order_id = blotter.order(asset, amount, **kwargs)

        # Verify order was created
        order = blotter.get_order(order_id)
        if order is None:
            raise RuntimeError(f"Order {order_id} not found after placement")

        print(f"✓ Order {order_id} placed successfully")
        return order_id

    except (InvalidQuantityError, OrderError) as e:
        print(f"✗ Order validation failed: {e}")
        return None
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return None

# Usage:
order_id = safe_order_submission(
    blotter, equity, Decimal("100"),
    order_type="limit", limit_price=Decimal("150.00")
)
```

---

## Order Processing

### process_order()

Process order execution against current market data.

**Method Signature** (source lines 172-236):

```python
def process_order(
    self,
    order: DecimalOrder,
    market_price: Decimal,
    fill_amount: Decimal | None = None,
) -> DecimalTransaction | None:
```

**Parameters**:
- `order` (`DecimalOrder`): Order to process
- `market_price` (`Decimal`): Current market price
- `fill_amount` (`Decimal | None`): Amount to fill. If `None`, fills complete order

**Returns**: `DecimalTransaction | None` - Transaction if order filled, `None` if not triggered

**Raises**:
- `ValueError`: If `fill_amount` exceeds remaining order quantity

**Source Verification** (lines 200-202):
```python
if abs(fill_amount) > abs(order.remaining):
    raise ValueError(f"Fill amount {fill_amount} exceeds remaining {order.remaining}")
```

### Example: Basic Order Processing

```python
from decimal import Decimal
from rustybt.finance.decimal.blotter import DecimalBlotter
from datetime import datetime

# Setup blotter
blotter = DecimalBlotter()
blotter.set_current_dt(datetime(2024, 1, 15, 10, 0))

# Place market order
order_id = blotter.order(
    asset=equity,
    amount=Decimal("100")
)

# Get order object
order = blotter.get_order(order_id)

# Process order when market data arrives
market_price = Decimal("150.25")
transaction = blotter.process_order(
    order=order,
    market_price=market_price
)

if transaction:
    print(f"Order filled!")
    print(f"  Execution price: ${transaction.price}")
    print(f"  Amount: {transaction.amount}")
    print(f"  Commission: ${transaction.commission}")
    print(f"  Total cost: ${transaction.total_cost}")
else:
    print("Order not triggered (for stop/limit orders)")
```

### Example: Processing Limit Orders

```python
# Place limit order
limit_order_id = blotter.order(
    asset=equity,
    amount=Decimal("100"),
    order_type="limit",
    limit_price=Decimal("150.00")
)
limit_order = blotter.get_order(limit_order_id)

# Example 1: Market price below limit (buy order fills)
market_price = Decimal("149.50")
transaction = blotter.process_order(limit_order, market_price)
if transaction:
    print(f"Limit order filled at ${transaction.price}")

# Example 2: Market price above limit (buy order doesn't fill)
market_price = Decimal("151.00")
transaction = blotter.process_order(limit_order, market_price)
if transaction is None:
    print("Limit order not triggered - price above limit")
```

### Example: Processing Stop Orders

```python
# Place stop-loss order
stop_order_id = blotter.order(
    asset=equity,
    amount=Decimal("-100"),  # Sell
    order_type="stop",
    stop_price=Decimal("145.00")
)
stop_order = blotter.get_order(stop_order_id)

# Example 1: Stop not triggered
market_price = Decimal("150.00")
transaction = blotter.process_order(stop_order, market_price)
assert transaction is None  # Stop not hit

# Example 2: Stop triggered
market_price = Decimal("144.50")  # Price fell below stop
transaction = blotter.process_order(stop_order, market_price)
assert transaction is not None
print(f"Stop order triggered and filled at ${transaction.price}")
```

### process_partial_fill()

Process partial order fill.

**Method Signature** (source lines 238-287):

```python
def process_partial_fill(
    self,
    order: DecimalOrder,
    fill_amount: Decimal,
    fill_price: Decimal,
) -> DecimalTransaction:
```

**Parameters**:
- `order` (`DecimalOrder`): Order to fill partially
- `fill_amount` (`Decimal`): Amount to fill
- `fill_price` (`Decimal`): Execution price

**Returns**: `DecimalTransaction` - Transaction for the partial fill

**Raises**:
- `ValueError`: If `fill_amount` exceeds remaining quantity

### Example: Partial Fills

```python
from decimal import Decimal

# Place large order
large_order_id = blotter.order(
    asset=equity,
    amount=Decimal("1000")  # 1,000 shares
)
large_order = blotter.get_order(large_order_id)

# Partial fill 1: 300 shares at $150.00
txn1 = blotter.process_partial_fill(
    order=large_order,
    fill_amount=Decimal("300"),
    fill_price=Decimal("150.00")
)
print(f"Partial fill 1: {txn1.amount} @ ${txn1.price}")
print(f"Remaining: {large_order.remaining}")  # 700 shares

# Partial fill 2: 400 shares at $150.10
txn2 = blotter.process_partial_fill(
    order=large_order,
    fill_amount=Decimal("400"),
    fill_price=Decimal("150.10")
)
print(f"Partial fill 2: {txn2.amount} @ ${txn2.price}")
print(f"Remaining: {large_order.remaining}")  # 300 shares

# Final fill: 300 shares at $150.05
txn3 = blotter.process_partial_fill(
    order=large_order,
    fill_amount=Decimal("300"),
    fill_price=Decimal("150.05")
)
print(f"Final fill: {txn3.amount} @ ${txn3.price}")
print(f"Order fully filled: {large_order.remaining == Decimal('0')}")

# Weighted average fill price
print(f"Average fill price: ${large_order.filled_price}")
```

### Example: Partial Fill Error Handling

```python
# Place order
order_id = blotter.order(asset=equity, amount=Decimal("100"))
order = blotter.get_order(order_id)

try:
    # Attempt to overfill
    blotter.process_partial_fill(
        order=order,
        fill_amount=Decimal("150"),  # More than order amount!
        fill_price=Decimal("150.00")
    )
except ValueError as e:
    print(f"Error: {e}")
    # Output: Error: Fill amount 150 exceeds remaining 100
```

---

## Order Cancellation

### cancel_order()

Cancel an open order.

**Method Signature** (source lines 143-170):

```python
def cancel_order(self, order_id: str) -> None:
```

**Parameters**:
- `order_id` (`str`): Order ID to cancel

**Raises**:
- `KeyError`: If order not found

**Source Verification** (lines 152-153):
```python
if order_id not in self.orders:
    raise KeyError(f"Order {order_id} not found")
```

### Example: Order Cancellation

```python
from decimal import Decimal

# Place order
order_id = blotter.order(
    asset=equity,
    amount=Decimal("100"),
    order_type="limit",
    limit_price=Decimal("150.00")
)

# Cancel order before it fills
blotter.cancel_order(order_id)

# Verify cancellation
order = blotter.get_order(order_id)
assert order.status == "cancelled"
print(f"Order {order_id} cancelled")

# Check it's no longer in open orders
open_orders = blotter.get_open_orders(equity)
assert order_id not in [o.id for o in open_orders]
```

### Example: Cancellation Error Handling

```python
# Attempt to cancel non-existent order
try:
    blotter.cancel_order("non_existent_id")
except KeyError as e:
    print(f"Error: {e}")
    # Output: Error: Order non_existent_id not found

# Safe cancellation wrapper
def safe_cancel(blotter, order_id):
    """Cancel order with error handling."""
    try:
        blotter.cancel_order(order_id)
        print(f"✓ Order {order_id} cancelled")
        return True
    except KeyError:
        print(f"✗ Order {order_id} not found")
        return False

# Usage:
if safe_cancel(blotter, order_id):
    print("Cancellation successful")
```

### Example: Cancel and Replace Pattern

```python
from decimal import Decimal

# Original order
original_order_id = blotter.order(
    asset=equity,
    amount=Decimal("100"),
    order_type="limit",
    limit_price=Decimal("150.00")
)

# Market moved - cancel and replace with new limit
blotter.cancel_order(original_order_id)

new_order_id = blotter.order(
    asset=equity,
    amount=Decimal("100"),
    order_type="limit",
    limit_price=Decimal("149.50")  # More aggressive price
)

print(f"Replaced {original_order_id} with {new_order_id}")
```

---

## Order Tracking

### get_order()

Retrieve order by ID.

**Method Signature** (source lines 331-340):

```python
def get_order(self, order_id: str) -> DecimalOrder | None:
```

**Parameters**:
- `order_id` (`str`): Order ID

**Returns**: `DecimalOrder | None` - Order if found, `None` otherwise

### get_open_orders()

Retrieve open orders, optionally filtered by asset.

**Method Signature** (source lines 342-357):

```python
def get_open_orders(self, asset: Asset | None = None) -> list[DecimalOrder]:
```

**Parameters**:
- `asset` (`Asset | None`): Filter by asset. If `None`, returns all open orders

**Returns**: `list[DecimalOrder]` - List of open orders

### get_transactions()

Retrieve all transactions.

**Method Signature** (source lines 359-365):

```python
def get_transactions(self) -> list[DecimalTransaction]:
```

**Returns**: `list[DecimalTransaction]` - List of all transactions

### Example: Order Tracking

```python
from decimal import Decimal

# Place multiple orders
order1 = blotter.order(equity, Decimal("100"), order_type="market")
order2 = blotter.order(equity, Decimal("50"), order_type="limit", limit_price=Decimal("150.00"))
order3 = blotter.order(equity2, Decimal("200"), order_type="market")

# Get specific order
order = blotter.get_order(order1)
print(f"Order {order.id}: {order.amount} shares of {order.asset.symbol}")

# Get all open orders for an asset
equity_orders = blotter.get_open_orders(equity)
print(f"{len(equity_orders)} open orders for {equity.symbol}")
for order in equity_orders:
    print(f"  - {order.id}: {order.amount} @ {order.order_type}")

# Get all open orders (all assets)
all_open_orders = blotter.get_open_orders()
print(f"Total open orders: {len(all_open_orders)}")

# Get all transactions
transactions = blotter.get_transactions()
print(f"Total transactions: {len(transactions)}")
for txn in transactions:
    print(f"  - {txn.dt}: {txn.amount} shares @ ${txn.price}")
```

### Example: Order Status Monitoring

```python
from decimal import Decimal
from datetime import datetime

def monitor_order_status(blotter, order_id):
    """Monitor order status with details."""
    order = blotter.get_order(order_id)

    if order is None:
        print(f"Order {order_id} not found")
        return

    print(f"Order {order.id} Status:")
    print(f"  Asset: {order.asset.symbol}")
    print(f"  Type: {order.order_type}")
    print(f"  Amount: {order.amount}")
    print(f"  Filled: {order.filled}")
    print(f"  Remaining: {order.remaining}")
    print(f"  Status: {order.status}")
    print(f"  Commission: ${order.commission}")

    if order.filled_price:
        print(f"  Average fill price: ${order.filled_price}")

    if order.limit:
        print(f"  Limit price: ${order.limit}")
    if order.stop:
        print(f"  Stop price: ${order.stop}")

    print(f"  Open: {order.open}")
    print(f"  Triggered: {order.triggered}")

# Usage:
order_id = blotter.order(equity, Decimal("100"), order_type="limit", limit_price=Decimal("150.00"))
monitor_order_status(blotter, order_id)
```

---

## Complete Order Lifecycle Example

```python
from decimal import Decimal
from datetime import datetime
from rustybt.assets import Equity
from rustybt.finance.decimal.blotter import DecimalBlotter
from rustybt.finance.decimal.commission import PerShareCommission
from rustybt.finance.decimal.slippage import FixedBasisPointsSlippage

# 1. Setup blotter
blotter = DecimalBlotter(
    commission_model=PerShareCommission(cost_per_share=Decimal("0.005"), min_cost=Decimal("1.00")),
    slippage_model=FixedBasisPointsSlippage(basis_points=Decimal("5"))
)

# 2. Initialize with current time
blotter.set_current_dt(datetime(2024, 1, 15, 9, 30))

# 3. Create asset
aapl = Equity(1, exchange='NYSE', symbol='AAPL')

# 4. Place limit order
print("=" * 50)
print("PLACING LIMIT ORDER")
print("=" * 50)
order_id = blotter.order(
    asset=aapl,
    amount=Decimal("100"),
    order_type="limit",
    limit_price=Decimal("150.00")
)
print(f"Order placed: {order_id}")

# 5. Check open orders
open_orders = blotter.get_open_orders(aapl)
print(f"\nOpen orders for AAPL: {len(open_orders)}")

# 6. Get order details
order = blotter.get_order(order_id)
print(f"\nOrder Details:")
print(f"  Amount: {order.amount}")
print(f"  Type: {order.order_type}")
print(f"  Limit: ${order.limit}")
print(f"  Status: {order.status}")

# 7. Simulate market data - price above limit (no fill)
print("\n" + "=" * 50)
print("MARKET DATA: Price = $151.00 (above limit)")
print("=" * 50)
blotter.set_current_dt(datetime(2024, 1, 15, 10, 0))
market_price = Decimal("151.00")
transaction = blotter.process_order(order, market_price)
if transaction is None:
    print("✗ Order not filled - price above limit")

# 8. Simulate market data - price at limit (fills)
print("\n" + "=" * 50)
print("MARKET DATA: Price = $149.50 (below limit)")
print("=" * 50)
blotter.set_current_dt(datetime(2024, 1, 15, 10, 30))
market_price = Decimal("149.50")
transaction = blotter.process_order(order, market_price)

if transaction:
    print("✓ Order filled!")
    print(f"\nTransaction Details:")
    print(f"  Asset: {transaction.asset.symbol}")
    print(f"  Amount: {transaction.amount}")
    print(f"  Price: ${transaction.price}")
    print(f"  Commission: ${transaction.commission}")
    print(f"  Slippage: ${transaction.slippage}")
    print(f"  Total cost: ${transaction.total_cost}")

# 9. Verify order is no longer open
open_orders = blotter.get_open_orders(aapl)
print(f"\nOpen orders for AAPL: {len(open_orders)}")

# 10. Get transaction history
transactions = blotter.get_transactions()
print(f"\nTotal transactions: {len(transactions)}")

# 11. Final blotter state
print("\n" + "=" * 50)
print("FINAL BLOTTER STATE")
print("=" * 50)
print(blotter)
```

**Expected Output**:
```
==================================================
PLACING LIMIT ORDER
==================================================
Order placed: 123e4567-e89b-12d3-a456-426614174000

Open orders for AAPL: 1

Order Details:
  Amount: 100
  Type: limit
  Limit: $150.00
  Status: open

==================================================
MARKET DATA: Price = $151.00 (above limit)
==================================================
✗ Order not filled - price above limit

==================================================
MARKET DATA: Price = $149.50 (below limit)
==================================================
✓ Order filled!

Transaction Details:
  Asset: AAPL
  Amount: 100
  Price: $149.57
  Commission: $1.00
  Slippage: $0.75
  Total cost: $14958.00

Open orders for AAPL: 0

Total transactions: 1

==================================================
FINAL BLOTTER STATE
==================================================
DecimalBlotter(commission_model=PerShareCommission(...), slippage_model=FixedBasisPointsSlippage(...), open_orders=0, total_orders=1)
```

---

## Production Strategy Integration

### Example: Complete Trading Strategy

```python
from decimal import Decimal
from datetime import datetime
from rustybt.assets import Equity
from rustybt.finance.decimal.blotter import DecimalBlotter
from rustybt.finance.decimal.commission import PerShareCommission
from rustybt.finance.decimal.slippage import VolumeShareSlippage

class SimpleMovingAverageCrossover:
    """SMA crossover strategy using DecimalBlotter."""

    def __init__(self, short_window=50, long_window=200):
        # Initialize blotter
        self.blotter = DecimalBlotter(
            commission_model=PerShareCommission(
                cost_per_share=Decimal("0.005"),
                min_cost=Decimal("1.00")
            ),
            slippage_model=VolumeShareSlippage(
                volume_limit=Decimal("0.025"),
                price_impact=Decimal("0.1")
            )
        )

        self.short_window = short_window
        self.long_window = long_window
        self.position = Decimal("0")
        self.pending_orders = {}

    def handle_data(self, dt, asset, price, sma_short, sma_long):
        """Process market data and generate signals."""
        self.blotter.set_current_dt(dt)

        # Process any open orders
        self._process_open_orders(asset, price)

        # Generate signals
        if sma_short > sma_long and self.position == Decimal("0"):
            # Golden cross - buy signal
            order_id = self.blotter.order(
                asset=asset,
                amount=Decimal("100"),
                order_type="market"
            )
            self.pending_orders[order_id] = "BUY"
            print(f"{dt}: BUY signal - placed order {order_id}")

        elif sma_short < sma_long and self.position > Decimal("0"):
            # Death cross - sell signal
            order_id = self.blotter.order(
                asset=asset,
                amount=-self.position,  # Close position
                order_type="market"
            )
            self.pending_orders[order_id] = "SELL"
            print(f"{dt}: SELL signal - placed order {order_id}")

    def _process_open_orders(self, asset, price):
        """Process pending orders."""
        open_orders = self.blotter.get_open_orders(asset)

        for order in open_orders:
            transaction = self.blotter.process_order(order, price)

            if transaction:
                # Update position
                self.position += transaction.amount

                # Log fill
                signal = self.pending_orders.pop(order.id, "UNKNOWN")
                print(f"  ✓ {signal} order filled: {transaction.amount} @ ${transaction.price}")
                print(f"    Commission: ${transaction.commission}")
                print(f"    New position: {self.position}")

    def get_performance(self):
        """Calculate performance metrics."""
        transactions = self.blotter.get_transactions()

        if not transactions:
            return {"total_trades": 0}

        total_commission = sum(t.commission for t in transactions)
        total_slippage = sum(t.slippage for t in transactions)

        return {
            "total_trades": len(transactions),
            "total_commission": float(total_commission),
            "total_slippage": float(total_slippage),
            "current_position": float(self.position)
        }

# Usage:
strategy = SimpleMovingAverageCrossover()
aapl = Equity(1, exchange='NYSE', symbol='AAPL')

# Simulate market data
market_data = [
    (datetime(2024, 1, 15, 9, 30), Decimal("150.00"), Decimal("148.00"), Decimal("152.00")),  # Buy signal
    (datetime(2024, 1, 15, 10, 0), Decimal("151.00"), Decimal("149.00"), Decimal("152.00")),
    (datetime(2024, 1, 15, 10, 30), Decimal("149.00"), Decimal("150.00"), Decimal("149.50")),  # Sell signal
]

for dt, price, sma_short, sma_long in market_data:
    strategy.handle_data(dt, aapl, price, sma_short, sma_long)

# Get performance
performance = strategy.get_performance()
print("\nPerformance Summary:")
for key, value in performance.items():
    print(f"  {key}: {value}")
```

---

## Best Practices

### ✅ DO

1. **Set Current DateTime**: Always call `set_current_dt()` before processing orders
   ```python
   blotter.set_current_dt(datetime.now())
   ```

2. **Use Decimal for All Financial Values**: Never use float
   ```python
   # ✓ Correct
   amount = Decimal("100")
   price = Decimal("150.50")

   # ✗ Wrong
   amount = 100.0
   price = 150.5
   ```

3. **Handle Order Submission Errors**: Use try/except for order validation
   ```python
   try:
       order_id = blotter.order(asset, amount, ...)
   except InvalidQuantityError as e:
       logger.error(f"Invalid order: {e}")
   ```

4. **Check Order Status**: Verify orders are processed correctly
   ```python
   order = blotter.get_order(order_id)
   if order.open:
       # Still waiting to fill
   elif order.filled == order.amount:
       # Completely filled
   ```

5. **Track Transactions**: Maintain transaction history for analysis
   ```python
   transactions = blotter.get_transactions()
   total_cost = sum(t.total_cost for t in transactions)
   ```

### ❌ DON'T

1. **Don't Modify Orders Directly**: Use blotter methods
   ```python
   # ✗ Wrong
   order.filled = Decimal("50")

   # ✓ Correct
   blotter.process_partial_fill(order, Decimal("50"), price)
   ```

2. **Don't Process Orders Without Setting Time**: Always set current_dt
   ```python
   # ✗ Wrong
   transaction = blotter.process_order(order, price)

   # ✓ Correct
   blotter.set_current_dt(current_time)
   transaction = blotter.process_order(order, price)
   ```

3. **Don't Ignore Transaction Costs**: Configure realistic commission/slippage
   ```python
   # ✗ Wrong
   blotter = DecimalBlotter()  # No costs

   # ✓ Correct
   blotter = DecimalBlotter(
       commission_model=PerShareCommission(Decimal("0.005")),
       slippage_model=FixedBasisPointsSlippage(Decimal("5"))
   )
   ```

4. **Don't Cancel Already-Filled Orders**: Check order status first
   ```python
   # ✓ Correct
   order = blotter.get_order(order_id)
   if order and order.open:
       blotter.cancel_order(order_id)
   ```

5. **Don't Exceed Remaining Quantity in Partial Fills**: Validate fill amount
   ```python
   # ✓ Correct
   fill_amount = min(requested_fill, order.remaining)
   blotter.process_partial_fill(order, fill_amount, price)
   ```

---

## Related Documentation

- [Order Types](../order-types.md) - All supported order types (Market, Limit, Stop, etc.)
- [Latency Models](./latency-models.md) - Order execution latency simulation
- [Partial Fill Models](./partial-fills.md) - Realistic partial fill simulation
- [Commission Models](../transaction-costs/commissions.md) - Transaction commission calculation
- [Slippage Models](../transaction-costs/slippage.md) - Price slippage modeling

---

## Next Steps

1. Review [Order Types](../order-types.md) for complete order type documentation
2. Configure [Commission Models](../transaction-costs/commissions.md) for realistic cost modeling
3. Configure [Slippage Models](../transaction-costs/slippage.md) for realistic execution
4. Explore [Latency Models](./latency-models.md) for execution timing simulation
5. Study [Partial Fill Models](./partial-fills.md) for large order execution

---

## Summary

`DecimalBlotter` provides production-grade order management with:
- **Financial Integrity**: Decimal precision throughout
- **Complete Order Lifecycle**: Submission through fill processing
- **Realistic Execution**: Configurable commission and slippage
- **Transaction Tracking**: Complete history for analysis
- **Error Handling**: Comprehensive validation and error messages

All calculations use `Decimal` to eliminate float rounding errors and ensure audit-compliant precision for financial applications.
