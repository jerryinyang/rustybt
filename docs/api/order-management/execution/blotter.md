# Blotter Architecture

Complete guide to RustyBT's order management and routing system.

## Overview

The Blotter is RustyBT's central order management system responsible for:

- Order validation and routing
- Order state management
- Fill processing and transaction creation
- Integration with brokers (live trading) or simulation (backtesting)

## Architecture

```
Strategy Algorithm
       │
       │ order(asset, amount, style)
       ▼
┌──────────────────────────────────┐
│        Blotter (Abstract)        │
│  ┌────────────────────────────┐  │
│  │ Order Validation           │  │
│  │ • Asset tradeable?         │  │
│  │ • Sufficient funds?        │  │
│  │ • Position limits OK?      │  │
│  └────────────────────────────┘  │
│  ┌────────────────────────────┐  │
│  │ Order State Management     │  │
│  │ • Track open orders        │  │
│  │ • Update order status      │  │
│  │ • Handle cancellations     │  │
│  └────────────────────────────┘  │
│  ┌────────────────────────────┐  │
│  │ Order Routing              │  │
│  │ • Route to broker/sim      │  │
│  │ • Process fills            │  │
│  │ • Apply costs              │  │
│  └────────────────────────────┘  │
└───────────┬──────────────────────┘
            │
    ┌───────┴─────────┐
    │                 │
    ▼                 ▼
┌─────────────┐  ┌─────────────┐
│ Simulation  │  │   Broker    │
│  Blotter    │  │  Adapter    │
│ (Backtest)  │  │ (Live)      │
└─────────────┘  └─────────────┘
```

## Blotter Interface

### Base Class

```python
from rustybt.finance.blotter import Blotter

class Blotter(ABC):
    """Abstract base class for order management."""

    def __init__(self, cancel_policy=None):
        """Initialize blotter.

        Parameters
        ----------
        cancel_policy : CancelPolicy, optional
            Policy for automatic order cancellation
        """
        self.cancel_policy = cancel_policy or NeverCancel()
        self.current_dt = None
        self.orders = {}  # All orders by ID
        self.open_orders = {}  # Open orders by asset

    @abstractmethod
    def order(self, asset, amount, style, order_id=None):
        """Place an order.

        Parameters
        ----------
        asset : Asset
            Asset to trade
        amount : int
            Quantity (positive=buy, negative=sell)
        style : ExecutionStyle
            Order execution style
        order_id : str, optional
            Custom order ID

        Returns
        -------
        order_id : str or None
            Order ID if accepted, None if rejected
        """
        raise NotImplementedError

    @abstractmethod
    def cancel(self, order_id, relay_status=True):
        """Cancel an order.

        Parameters
        ----------
        order_id : str
            Order ID to cancel
        relay_status : bool
            Whether to update order status
        """
        raise NotImplementedError

    @abstractmethod
    def execute_cancel_policy(self, event):
        """Execute cancellation policy.

        Parameters
        ----------
        event : Event
            Current simulation/market event
        """
        raise NotImplementedError
```

## SimulationBlotter

The SimulationBlotter implements the Blotter interface for backtesting.

### Initialization

```python
from rustybt.finance.blotter import SimulationBlotter
from rustybt.finance.slippage import VolumeShareSlippage
from rustybt.finance.commission import PerShare

# Create simulation blotter
blotter = SimulationBlotter(
    data_frequency='daily',
    slippage=VolumeShareSlippage(),
    commission=PerShare(cost=0.001, min_trade_cost=1.0)
)
```

### Order Processing Flow

```
1. order() called
      │
      ▼
2. Validate order
   ├─ Asset tradeable? ──NO──> REJECT
   ├─ Amount non-zero? ──NO──> REJECT
   └─ Funds sufficient? ──NO──> REJECT
      │ YES
      ▼
3. Create Order object
      │
      ▼
4. Check cancel policy
   └─ Auto-cancel previous? ──YES──> Cancel old orders
      │
      ▼
5. Add to open_orders
      │
      ▼
6. Return order_id
```

### Order Execution Flow (Per Bar)

```
handle_data() called
      │
      ▼
1. Process all open orders
      │
      ▼
2. For each order:
   ├─ Check triggers (stop/limit)
   │  └─ Update stop_reached/limit_reached
   ├─ If triggered:
   │  ├─ Get current price
   │  ├─ Apply slippage model
   │  ├─ Check volume constraints
   │  ├─ Create transaction(s)
   │  └─ Apply commission
   └─ Update order status
      │
      ▼
3. Update portfolio positions
```

## Order Validation

### Validation Checks

```python
class SimulationBlotter(Blotter):
    def validate_order(self, asset, amount, style):
        """Validate order before placement.

        Checks:
        - Asset exists and is tradeable
        - Amount is non-zero integer
        - Stop/limit prices are valid
        - Sufficient buying power (if enforced)

        Returns
        -------
        is_valid : bool
        rejection_reason : str or None
        """
        # Check asset tradeable
        if not self.is_asset_tradeable(asset):
            return False, f"Asset {asset.symbol} is not tradeable"

        # Check amount non-zero
        if amount == 0:
            return False, "Order amount cannot be zero"

        # Check prices valid
        if style.get_limit_price(amount > 0) is not None:
            if style.get_limit_price(amount > 0) <= 0:
                return False, "Limit price must be positive"

        if style.get_stop_price(amount > 0) is not None:
            if style.get_stop_price(amount > 0) <= 0:
                return False, "Stop price must be positive"

        return True, None
```

### Rejection Handling

```python
def order(self, asset, amount, style, order_id=None):
    # Validate order
    is_valid, rejection_reason = self.validate_order(asset, amount, style)

    if not is_valid:
        # Create rejected order for tracking
        order = Order(
            dt=self.current_dt,
            asset=asset,
            amount=amount,
            id=order_id
        )
        order.reject(rejection_reason)
        self.orders[order.id] = order

        logger.warning(f"Order rejected: {rejection_reason}")
        return None  # No order ID returned

    # ... continue with order placement
```

## Order State Management

### Tracking Open Orders

```python
class SimulationBlotter(Blotter):
    def add_order(self, order):
        """Add order to tracking."""
        # Add to all orders
        self.orders[order.id] = order

        # Add to open orders by asset
        if order.asset not in self.open_orders:
            self.open_orders[order.asset] = []
        self.open_orders[order.asset].append(order)

    def remove_order(self, order):
        """Remove order from open tracking."""
        if order.asset in self.open_orders:
            self.open_orders[order.asset].remove(order)

            # Clean up empty lists
            if not self.open_orders[order.asset]:
                del self.open_orders[order.asset]
```

### Order Status Updates

```python
def process_order_fills(self, order, current_bar):
    """Process fills for an order."""
    # Check if order triggered
    current_price = current_bar['close']
    order.check_triggers(current_price, self.current_dt)

    if not order.triggered:
        return  # Order not ready to execute

    # Calculate fill
    fill_price, fill_amount = self.calculate_fill(
        order, current_bar
    )

    if fill_amount > 0:
        # Create transaction
        transaction = self.create_transaction(
            order, fill_price, fill_amount
        )

        # Update order
        order.filled += fill_amount
        order.commission += transaction.commission

        # Update status
        if order.filled >= order.amount:
            order.status = ORDER_STATUS.FILLED
            self.remove_order(order)  # Remove from open orders
        else:
            order.status = ORDER_STATUS.PARTIALLY_FILLED
```

## Fill Processing

### Calculate Fill Amount

```python
def calculate_fill(self, order, current_bar):
    """Calculate how much of order can fill.

    Parameters
    ----------
    order : Order
        Order to fill
    current_bar : dict
        Current bar data (OHLCV)

    Returns
    -------
    fill_price : float
        Execution price after slippage
    fill_amount : int
        Number of shares filled
    """
    # Get base price
    if order.limit is not None:
        base_price = order.limit
    else:
        base_price = current_bar['close']

    # Apply slippage model
    fill_price, fill_amount = self.slippage_model.process_order(
        order=order,
        bar=current_bar,
        base_price=base_price
    )

    # Limit fill amount to available
    max_fill = min(order.open_amount, fill_amount)

    return fill_price, max_fill
```

### Create Transaction

```python
def create_transaction(self, order, price, amount):
    """Create transaction from order fill.

    Parameters
    ----------
    order : Order
        Order being filled
    price : float
        Fill price
    amount : int
        Shares filled

    Returns
    -------
    transaction : Transaction
        Created transaction object
    """
    # Calculate commission
    commission = self.commission_model.calculate(
        order=order,
        transaction_amount=amount,
        transaction_price=price
    )

    # Create transaction
    transaction = Transaction(
        asset=order.asset,
        amount=amount,
        dt=self.current_dt,
        price=price,
        order_id=order.id,
        commission=commission
    )

    return transaction
```

## Cancel Policy

Control automatic order cancellation.

### Never Cancel (Default)

```python
from rustybt.finance.cancel_policy import NeverCancel

# Orders remain open until filled or manually cancelled
blotter = SimulationBlotter(cancel_policy=NeverCancel())
```

### Cancel All Orders on Bar

```python
from rustybt.finance.cancel_policy import EODCancel

# Cancel all open orders at end of each day
blotter = SimulationBlotter(cancel_policy=EODCancel())
```

### Custom Cancel Policy

```python
from rustybt.finance.cancel_policy import CancelPolicy

class CustomCancelPolicy(CancelPolicy):
    def should_cancel(self, order, event):
        """Determine if order should be cancelled.

        Parameters
        ----------
        order : Order
            Order to check
        event : BarData
            Current event

        Returns
        -------
        should_cancel : bool
        """
        # Cancel orders older than 5 days
        if (event.dt - order.dt).days > 5:
            return True

        # Cancel stop orders if unreasonably far from current price
        if order.stop is not None:
            current_price = event.current(order.asset, 'close')
            if abs(order.stop - current_price) / current_price > 0.20:
                return True  # More than 20% away

        return False
```

## Batch Order Processing

Process multiple orders efficiently.

```python
def batch_order(self, order_arg_lists):
    """Place multiple orders at once.

    Parameters
    ----------
    order_arg_lists : list[tuple]
        List of (asset, amount, style) tuples

    Returns
    -------
    order_ids : list[str or None]
        Order IDs for each order
    """
    order_ids = []

    for asset, amount, style in order_arg_lists:
        order_id = self.order(asset, amount, style)
        order_ids.append(order_id)

    return order_ids

# Usage:
orders_to_place = [
    (asset1, 100, LimitOrder(150.0)),
    (asset2, -50, MarketOrder()),
    (asset3, 200, StopOrder(95.0))
]

order_ids = blotter.batch_order(orders_to_place)
```

## Integration with Strategy

### Accessing Blotter

```python
class MyStrategy(TradingAlgorithm):
    def handle_data(self, context, data):
        # Blotter available via context
        blotter = context.blotter

        # Get all open orders
        all_open = blotter.open_orders

        # Get orders for specific asset
        asset_orders = all_open.get(asset, [])

        # Check specific order
        order = blotter.orders.get(order_id)
```

### Manual Order Management

```python
def handle_data(self, context, data):
    # Place order through blotter directly
    order_id = context.blotter.order(
        asset=asset,
        amount=100,
        style=LimitOrder(150.0)
    )

    # Cancel order through blotter
    context.blotter.cancel(order_id)

    # Check order status
    order = context.blotter.orders.get(order_id)
    print(f"Order status: {order.status.name}")
```

## Performance Considerations

### Order Volume Limits

Configure slippage to respect volume constraints:

```python
from rustybt.finance.slippage import VolumeShareSlippage

# Limit to 2.5% of bar volume
blotter = SimulationBlotter(
    slippage=VolumeShareSlippage(
        volume_limit=0.025,
        price_impact=0.1
    )
)
```

### Batch Processing Optimization

```python
# Process all orders for a bar at once
def process_bar(self, bar_data):
    """Process all open orders for current bar."""
    orders_to_process = []

    # Collect all triggered orders
    for asset, orders in self.open_orders.items():
        for order in orders:
            if order.triggered:
                orders_to_process.append(order)

    # Process in batch
    for order in orders_to_process:
        self.process_order_fills(order, bar_data)
```

## Best Practices

### ✅ DO

1. **Use Cancel Policies**: Prevent stale orders from accumulating
2. **Monitor Open Orders**: Track order states actively
3. **Handle Rejections**: Log and respond to rejected orders
4. **Validate Before Submission**: Check order parameters
5. **Process Partial Fills**: Account for incomplete fills

### ❌ DON'T

1. **Bypass Blotter**: Always use blotter, don't manipulate orders directly
2. **Ignore Order Status**: Check status before assuming fills
3. **Place Duplicate Orders**: Check for existing orders first
4. **Forget Volume Limits**: Configure realistic slippage
5. **Skip Commission Modeling**: Always model transaction costs

## Troubleshooting

### Orders Not Filling

**Symptoms**:
- Orders remain in OPEN state
- No fills occurring

**Causes**:
- Limit/stop prices not reached
- Insufficient volume
- Order not triggered

**Solutions**:
```python
# Check order triggers
order = context.blotter.orders.get(order_id)
print(f"Stop reached: {order.stop_reached}")
print(f"Limit reached: {order.limit_reached}")
print(f"Triggered: {order.triggered}")

# Adjust prices or use market order
if not order.triggered:
    cancel_order(order)
    order(asset, amount, style=MarketOrder())
```

### Unexpected Rejections

**Symptoms**:
- Orders immediately rejected
- None returned from order()

**Causes**:
- Insufficient funds
- Invalid prices
- Position limits

**Solutions**:
```python
# Check rejected orders
for order in context.blotter.orders.values():
    if order.status == ORDER_STATUS.REJECTED:
        print(f"Rejection reason: {order.reason}")

# Adjust based on reason
if "INSUFFICIENT_FUNDS" in order.reason:
    # Reduce order size
elif "INVALID_PRICE" in order.reason:
    # Check stop/limit prices
```

## Related Documentation

- Simulation Blotter (Coming soon) - Backtesting execution details
- Fill Processing (Coming soon) - Fill calculation and transaction creation
- [Order Lifecycle](../workflows/order-lifecycle.md) - Order state transitions
- [Transaction Costs](../transaction-costs/slippage.md) - Cost modeling

## Next Steps

1. Study Simulation Blotter (Coming soon) for backtesting specifics
2. Review Fill Processing (Coming soon) for execution details
3. Explore [Transaction Costs](../transaction-costs/slippage.md) for realistic modeling
