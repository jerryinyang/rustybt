# Finance API Reference

**Last Updated**: 2024-10-11

## Overview

The Finance module provides core financial modeling including commission models, slippage models, order management, and transaction costs. It supports both traditional (float) and Decimal-based arithmetic for financial accuracy.

---

## Commission Models

Commission models calculate transaction costs based on order execution.

### CommissionModel (Abstract Base Class)

Base class for all commission models.

```python
from rustybt.finance.commission import CommissionModel
```

#### Methods

##### `calculate(order, transaction) -> float`

Calculate commission for a transaction.

**Parameters**:
- `order`: Order object
- `transaction`: Transaction object

**Returns**: Commission amount in dollars

---

### NoCommission

Zero commission model (useful for testing).

```python
from rustybt.finance.commission import NoCommission

commission = NoCommission()
```

**Use Case**: Backtesting without transaction costs.

---

### PerShare

Commission based on number of shares traded.

```python
from rustybt.finance.commission import PerShare

commission = PerShare(
    cost=0.005,       # $0.005 per share
    min_trade_cost=1.0  # Minimum $1 per trade
)
```

**Constructor**:
```python
PerShare(
    cost: float = 0.001,           # Cost per share
    min_trade_cost: float = 0.0    # Minimum per trade
)
```

**Example**:
```python
# $0.01 per share, minimum $1 per trade
commission = PerShare(cost=0.01, min_trade_cost=1.0)

# 100 shares: $1.00 commission (100 * $0.01)
# 50 shares: $1.00 commission (minimum applies)
```

---

### PerContract

Commission for futures contracts.

```python
from rustybt.finance.commission import PerContract

commission = PerContract(
    cost=0.85,              # $0.85 per contract
    exchange_fee=1.50,      # $1.50 exchange fee
    min_trade_cost=0.0
)
```

**Constructor**:
```python
PerContract(
    cost: float = 0.85,             # Cost per contract
    exchange_fee: float = 0.0,      # Exchange/clearing fee
    min_trade_cost: float = 0.0     # Minimum per trade
)
```

---

### PerDollar

Commission as percentage of trade value.

```python
from rustybt.finance.commission import PerDollar

commission = PerDollar(
    cost=0.0015  # 0.15% of trade value
)
```

**Constructor**:
```python
PerDollar(
    cost: float = 0.0015  # Percentage of trade value (0.0015 = 0.15%)
)
```

**Example**:
```python
commission = PerDollar(cost=0.001)  # 0.1%

# $10,000 trade: $10 commission (10000 * 0.001)
# $1,000 trade: $1 commission (1000 * 0.001)
```

---

### PerTrade

Fixed commission per trade.

```python
from rustybt.finance.commission import PerTrade

commission = PerTrade(cost=10.0)  # $10 per trade
```

**Use Case**: Flat-fee brokers.

---

## Slippage Models

Slippage models determine fill prices and volumes for orders.

### SlippageModel (Abstract Base Class)

Base class for all slippage models.

```python
from rustybt.finance.slippage import SlippageModel
```

#### Methods

##### `process_order(data, order) -> tuple[float, int]`

Process order and return fill price and volume.

**Parameters**:
- `data`: BarData with current market data
- `order`: Order to process

**Returns**: Tuple of `(fill_price, fill_volume)`

---

### NoSlippage

Zero slippage model.

```python
from rustybt.finance.slippage import NoSlippage

slippage = NoSlippage()
```

**Behavior**: Orders fill at current price with no impact.

---

### FixedSlippage

Fixed percentage slippage.

```python
from rustybt.finance.slippage import FixedSlippage

slippage = FixedSlippage(spread=0.0001)  # 0.01% slippage
```

**Constructor**:
```python
FixedSlippage(
    spread: float = 0.0001  # Slippage as decimal (0.0001 = 0.01%)
)
```

**Behavior**:
- Buy orders: filled at `price * (1 + spread)`
- Sell orders: filled at `price * (1 - spread)`

---

### VolumeShareSlippage

Slippage based on order size relative to bar volume.

```python
from rustybt.finance.slippage import VolumeShareSlippage

slippage = VolumeShareSlippage(
    volume_limit=0.025,  # Max 2.5% of bar volume
    price_impact=0.1     # Price impact factor
)
```

**Constructor**:
```python
VolumeShareSlippage(
    volume_limit: float = 0.025,      # Max % of bar volume
    price_impact: float = 0.1         # Price impact coefficient
)
```

**Price Impact Formula**:
```
impact = price_impact * (volume_share ** 2)
fill_price = price * (1 + impact)  # for buys
fill_price = price * (1 - impact)  # for sells
```

**Example**:
```python
slippage = VolumeShareSlippage(volume_limit=0.1, price_impact=0.1)

# Bar volume: 1,000,000 shares
# Order: 50,000 shares (5% of volume)
# Volume share: 0.05
# Price impact: 0.1 * (0.05^2) = 0.00025 = 0.025%
```

---

### FixedBasisPointsSlippage

Fixed basis points slippage per side.

```python
from rustybt.finance.slippage import FixedBasisPointsSlippage

slippage = FixedBasisPointsSlippage(
    basis_points=5  # 5 basis points = 0.05%
)
```

**Constructor**:
```python
FixedBasisPointsSlippage(
    basis_points: float = 5  # Slippage in basis points (1 bp = 0.01%)
)
```

---

## Order Management

### Order

Represents a trading order.

```python
from rustybt.finance.order import Order
```

#### Constructor

```python
Order(
    dt: pd.Timestamp,
    asset: Asset,
    amount: int,
    stop: Optional[float] = None,
    limit: Optional[float] = None,
    filled: int = 0,
    commission: float = 0.0,
    trail_amount: Optional[float] = None,
    trail_percent: Optional[float] = None
)
```

**Parameters**:
- `dt`: Order creation timestamp
- `asset`: Asset to trade
- `amount`: Number of shares (positive=buy, negative=sell)
- `stop`: Stop price for stop orders
- `limit`: Limit price for limit orders
- `filled`: Shares already filled
- `commission`: Commission already paid
- `trail_amount`: Trailing stop dollar amount
- `trail_percent`: Trailing stop percentage

#### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `id` | `str` | Unique order ID (UUID) |
| `dt` | `pd.Timestamp` | Order creation time |
| `asset` | `Asset` | Asset being traded |
| `amount` | `int` | Total order quantity |
| `filled` | `int` | Quantity filled so far |
| `open_amount` | `int` | Remaining unfilled quantity |
| `status` | `ORDER_STATUS` | Current order status |
| `stop` | `Optional[float]` | Stop price |
| `limit` | `Optional[float]` | Limit price |
| `commission` | `float` | Commission paid |
| `direction` | `int` | Buy (1) or Sell (-1) |

#### Order Status

```python
from rustybt.finance.order import ORDER_STATUS

ORDER_STATUS.OPEN              # Order is open
ORDER_STATUS.FILLED            # Order completely filled
ORDER_STATUS.CANCELLED         # Order cancelled
ORDER_STATUS.REJECTED          # Order rejected
ORDER_STATUS.HELD              # Order held
ORDER_STATUS.TRIGGERED         # Stop order triggered
ORDER_STATUS.PARTIALLY_FILLED  # Order partially filled
```

#### Methods

##### `check_triggers(price: float, dt: pd.Timestamp) -> None`

Check if stop/limit triggers have been reached.

```python
order.check_triggers(price=150.50, dt=pd.Timestamp.now())
```

---

### Order Types

#### Market Order

```python
order = Order(
    dt=pd.Timestamp.now(),
    asset=asset,
    amount=100  # Buy 100 shares at market
)
```

#### Limit Order

```python
order = Order(
    dt=pd.Timestamp.now(),
    asset=asset,
    amount=100,
    limit=150.00  # Buy 100 shares at $150 or better
)
```

#### Stop Order

```python
order = Order(
    dt=pd.Timestamp.now(),
    asset=asset,
    amount=-100,  # Sell
    stop=145.00   # Sell if price drops to $145
)
```

#### Stop-Limit Order

```python
order = Order(
    dt=pd.Timestamp.now(),
    asset=asset,
    amount=-100,
    stop=145.00,   # Trigger at $145
    limit=144.00   # Sell at $144 or better
)
```

#### Trailing Stop Order

```python
# Dollar amount trailing stop
order = Order(
    dt=pd.Timestamp.now(),
    asset=asset,
    amount=-100,
    trail_amount=5.00  # Trail by $5
)

# Percentage trailing stop
order = Order(
    dt=pd.Timestamp.now(),
    asset=asset,
    amount=-100,
    trail_percent=0.05  # Trail by 5%
)
```

---

## Transaction

Represents an executed trade.

```python
from rustybt.finance.transaction import Transaction
```

#### Constructor

```python
Transaction(
    asset: Asset,
    amount: int,
    dt: pd.Timestamp,
    price: float,
    order_id: str,
    commission: Optional[float] = None
)
```

#### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `asset` | `Asset` | Asset traded |
| `amount` | `int` | Quantity traded |
| `dt` | `pd.Timestamp` | Execution timestamp |
| `price` | `float` | Execution price |
| `order_id` | `str` | Associated order ID |
| `commission` | `float` | Commission charged |

---

## Decimal Finance Module

For financial-grade precision, use Decimal-based models.

### Decimal Commission Models

```python
from rustybt.finance.decimal.commission import (
    DecimalPerShare,
    DecimalPerContract,
    DecimalPerDollar
)
from decimal import Decimal

# Decimal per-share commission
commission = DecimalPerShare(
    cost=Decimal("0.005"),
    min_trade_cost=Decimal("1.00")
)
```

### Decimal Slippage Models

```python
from rustybt.finance.decimal.slippage import (
    DecimalFixedSlippage,
    DecimalVolumeShareSlippage
)
from decimal import Decimal

slippage = DecimalFixedSlippage(
    spread=Decimal("0.0001")  # 0.01%
)
```

### Decimal Ledger

```python
from rustybt.finance.decimal.ledger import DecimalLedger
from decimal import Decimal

ledger = DecimalLedger(
    starting_cash=Decimal("100000.00")
)

# Record transaction
ledger.record_transaction(
    asset=asset,
    amount=Decimal("100"),
    price=Decimal("150.25"),
    commission=Decimal("0.50")
)

# Get account value
print(f"Cash: ${ledger.cash}")
print(f"Portfolio value: ${ledger.portfolio_value}")
```

---

## Costs Module

Additional transaction cost models.

### BorrowCost

Model short selling borrow costs.

```python
from rustybt.finance.costs import BorrowCost

borrow = BorrowCost(
    annual_rate=0.02  # 2% annual borrow rate
)
```

### OvernightFinancing

Model overnight financing costs for leveraged positions.

```python
from rustybt.finance.costs import OvernightFinancing

financing = OvernightFinancing(
    annual_rate=0.05,  # 5% annual rate
    apply_on_long=True,
    apply_on_short=True
)
```

---

## Position

Represents a position in an asset.

```python
from rustybt.finance.position import Position
```

#### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `asset` | `Asset` | Asset held |
| `amount` | `int` | Position size (positive=long, negative=short) |
| `cost_basis` | `float` | Average cost basis |
| `last_sale_price` | `float` | Latest price |
| `last_sale_date` | `pd.Timestamp` | Latest price timestamp |

#### Methods

##### `update(amount: int, price: float) -> None`

Update position with new transaction.

```python
position.update(amount=100, price=150.25)
```

##### `adjust_commission_cost_basis(commission: float) -> None`

Adjust cost basis for commission.

```python
position.adjust_commission_cost_basis(commission=0.50)
```

---

## Complete Example

```python
from rustybt import TradingAlgorithm
from rustybt.finance.commission import PerShare
from rustybt.finance.slippage import VolumeShareSlippage
from rustybt.finance.costs import BorrowCost, OvernightFinancing
from decimal import Decimal

class MyStrategy(TradingAlgorithm):
    def initialize(self):
        # Set commission model
        self.set_commission(
            PerShare(cost=0.005, min_trade_cost=1.0)
        )

        # Set slippage model
        self.set_slippage(
            VolumeShareSlippage(volume_limit=0.025, price_impact=0.1)
        )

        # Add borrow costs for shorts
        self.set_borrow_cost(
            BorrowCost(annual_rate=0.02)
        )

        # Add overnight financing
        self.set_overnight_financing(
            OvernightFinancing(annual_rate=0.05)
        )

    def handle_data(self, context, data):
        # Place orders - commission and slippage applied automatically
        self.order(self.symbol('AAPL'), 100)
```

---

## Best Practices

### Commission Selection

| Broker Type | Recommended Model | Example |
|-------------|-------------------|---------|
| Interactive Brokers | `PerShare` | 0.005/share, $1 min |
| TD Ameritrade | `PerTrade` | $0 flat |
| Futures Broker | `PerContract` | $0.85/contract |
| Crypto Exchange | `PerDollar` | 0.1% of value |

### Slippage Selection

| Strategy Type | Recommended Model | Settings |
|---------------|-------------------|----------|
| Low Frequency | `FixedSlippage` | 0.01% - 0.05% |
| High Frequency | `VolumeShareSlippage` | 2.5% volume limit |
| Large Orders | `VolumeShareSlippage` | Lower volume limit |
| Crypto | `FixedSlippage` | 0.05% - 0.1% |

### Decimal Precision

Use Decimal models when:
- High precision required (regulatory reporting)
- Large position sizes
- Long-running strategies
- Audit compliance needed

---

## See Also

- [Slippage Models Tutorial](../../examples/slippage_models_tutorial.py)
- [Borrow Cost Tutorial](../../examples/borrow_cost_tutorial.py)
- [Overnight Financing Tutorial](../../examples/overnight_financing_tutorial.py)
- [Decimal Precision Guide](../guides/decimal-precision-configuration.md)
