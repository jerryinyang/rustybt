#
# Copyright 2016 Quantopian, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Order management and tracking for trading operations.

This module provides the core Order class and related enumerations for managing
trading orders within RustyBT. It handles various order types including market,
limit, stop, and advanced order types like trailing stops, OCO (One-Cancels-Other),
and bracket orders.

The Order class uses __slots__ for memory efficiency since simulations can create
many order objects that persist in memory throughout the backtest.

Example:
    Creating a basic market order::

        order = Order(
            dt=pd.Timestamp('2023-01-01 10:30'),
            asset=Asset(symbol='AAPL'),
            amount=100,  # Positive for buy, negative for sell
        )

    Creating a limit order::

        order = Order(
            dt=pd.Timestamp('2023-01-01 10:30'),
            asset=Asset(symbol='AAPL'),
            amount=100,
            limit=150.00,  # Won't pay more than $150
        )

    Creating a trailing stop order::

        order = Order(
            dt=pd.Timestamp('2023-01-01 10:30'),
            asset=Asset(symbol='AAPL'),
            amount=-100,  # Sell order
            trail_percent=0.05,  # Trail by 5%
        )
"""
import math
import uuid
from enum import IntEnum

import rustybt.protocol as zp
from rustybt.assets import Asset
from rustybt.utils.input_validation import expect_types

ORDER_STATUS = IntEnum(
    "ORDER_STATUS",
    [
        "OPEN",  # Order placed but not yet filled
        "FILLED",  # Order completely filled
        "CANCELLED",  # Order cancelled by user or system
        "REJECTED",  # Order rejected by broker
        "HELD",  # Order held pending additional checks
        "TRIGGERED",  # Stop/limit price reached, order is active
        "PARTIALLY_FILLED",  # Order partially filled, remaining amount open
    ],
    start=0,
)

# Bit flags for order type categorization
SELL = 1 << 0  # Sell order flag
BUY = 1 << 1  # Buy order flag
STOP = 1 << 2  # Stop price specified
LIMIT = 1 << 3  # Limit price specified

# Fields to exclude when converting order to dict
ORDER_FIELDS_TO_IGNORE = {"type", "direction", "_status", "asset"}


class Order:
    """Represents a trading order with support for various order types.

    This class tracks the complete lifecycle of a trading order including creation,
    fills, cancellations, and advanced order features like trailing stops and
    order linking (OCO/bracket orders).

    The class uses __slots__ for memory efficiency since backtests can create and
    store thousands of order objects.

    Attributes:
        id: Unique identifier for the order
        dt: Timestamp when the order was last modified
        reason: Reason for rejection or hold status (if applicable)
        created: Timestamp when the order was created
        asset: Asset being traded
        amount: Number of shares/contracts (positive=buy, negative=sell)
        filled: Number of shares/contracts filled so far
        commission: Total commission paid on this order
        stop: Stop price (if stop order)
        limit: Limit price (if limit order)
        stop_reached: Whether stop price has been reached
        limit_reached: Whether limit price has been reached
        direction: Direction of the order (1=buy, -1=sell)
        type: Order type identifier
        broker_order_id: Broker-assigned order ID
        trail_amount: Absolute dollar amount for trailing stops
        trail_percent: Percentage (decimal) for trailing stops
        linked_order_ids: List of order IDs linked in OCO relationship
        parent_order_id: Parent order ID for bracket order children
        is_trailing_stop: Whether this is a trailing stop order
        trailing_highest_price: Highest price seen (for trailing sell stops)
        trailing_lowest_price: Lowest price seen (for trailing buy stops)

    Example:
        Creating a stop-limit order::

            order = Order(
                dt=pd.Timestamp('2023-01-01 10:30'),
                asset=stock,
                amount=100,
                stop=145.00,  # Activate when price >= $145
                limit=150.00,  # But don't pay more than $150
            )

        Creating OCO orders (handled by blotter)::

            # First order triggers at $160 (take profit)
            # Second order triggers at $140 (stop loss)
            # When one fills, the other cancels automatically
    """
    # using __slots__ to save on memory usage.  Simulations can create many
    # Order objects and we keep them all in memory, so it's worthwhile trying
    # to cut down on the memory footprint of this object.
    __slots__ = [
        "id",
        "dt",
        "reason",
        "created",
        "asset",
        "amount",
        "filled",
        "commission",
        "_status",
        "stop",
        "limit",
        "stop_reached",
        "limit_reached",
        "direction",
        "type",
        "broker_order_id",
        # Advanced order type fields
        "trail_amount",
        "trail_percent",
        "linked_order_ids",
        "parent_order_id",
        "is_trailing_stop",
        "trailing_highest_price",
        "trailing_lowest_price",
    ]

    @expect_types(asset=Asset)
    def __init__(
        self,
        dt,
        asset,
        amount,
        stop=None,
        limit=None,
        filled=0,
        commission=0,
        id=None,
        trail_amount=None,
        trail_percent=None,
        linked_order_ids=None,
        parent_order_id=None,
    ):
        """Initialize a new order.

        Args:
            dt: Timestamp when the order was placed
            asset: Asset to trade
            amount: Number of shares/contracts (positive=buy, negative=sell)
            stop: Stop price for stop orders
            limit: Limit price for limit orders
            filled: Number of shares already filled (default: 0)
            commission: Commission already paid on this order (default: 0)
            id: Unique order identifier (auto-generated if None)
            trail_amount: Absolute dollar amount for trailing stops
            trail_percent: Percentage (decimal 0-1) for trailing stops
            linked_order_ids: List of order IDs in OCO relationship
            parent_order_id: Parent order ID for bracket orders

        Example:
            Market order to buy 100 shares::

                order = Order(
                    dt=pd.Timestamp('2023-01-01 10:30'),
                    asset=stock,
                    amount=100,
                )

            Trailing stop to sell at 5% below peak::

                order = Order(
                    dt=pd.Timestamp('2023-01-01 10:30'),
                    asset=stock,
                    amount=-100,
                    trail_percent=0.05,
                )
        """
        # get a string representation of the uuid.
        self.id = self.make_id() if id is None else id
        self.dt = dt
        self.reason = None
        self.created = dt
        self.asset = asset
        self.amount = amount
        self.filled = filled
        self.commission = commission
        self._status = ORDER_STATUS.OPEN
        self.stop = stop
        self.limit = limit
        self.stop_reached = False
        self.limit_reached = False
        self.direction = math.copysign(1, self.amount)
        self.type = zp.DATASOURCE_TYPE.ORDER
        self.broker_order_id = None

        # Advanced order type fields
        self.trail_amount = trail_amount
        self.trail_percent = trail_percent
        self.linked_order_ids = linked_order_ids if linked_order_ids else []
        self.parent_order_id = parent_order_id
        self.is_trailing_stop = trail_amount is not None or trail_percent is not None
        self.trailing_highest_price = None
        self.trailing_lowest_price = None

    @staticmethod
    def make_id():
        """Generate a unique order ID.

        Returns:
            str: Hexadecimal UUID string
        """
        return uuid.uuid4().hex

    def to_dict(self):
        """Convert order to dictionary representation.

        Returns:
            dict: Order attributes as key-value pairs, excluding internal fields
                and including 'sid' for backward compatibility

        Example:
            >>> order.to_dict()
            {
                'id': '...',
                'dt': Timestamp('2023-01-01 10:30:00'),
                'asset': Asset(...),
                'amount': 100,
                'filled': 0,
                'status': ORDER_STATUS.OPEN,
                'sid': Asset(...),  # backward compatibility
                ...
            }
        """
        dct = {
            name: getattr(self, name)
            for name in self.__slots__
            if name not in ORDER_FIELDS_TO_IGNORE
        }

        if self.broker_order_id is None:
            del dct["broker_order_id"]

        # Adding 'sid' for backwards compatibility with downstream consumers.
        dct["sid"] = self.asset
        dct["status"] = self.status

        return dct

    @property
    def sid(self):
        """Get asset identifier (backward compatibility property).

        Returns:
            Asset: The order's asset

        Note:
            This property exists for backward compatibility with custom slippage
            models that expect a 'sid' attribute.
        """
        # For backwards compatibility because we pass this object to
        # custom slippage models.
        return self.asset

    def to_api_obj(self):
        """Convert order to API protocol object.

        Returns:
            zipline.protocol.Order: Protocol-compatible order object

        Note:
            Used for serialization and API compatibility.
        """
        pydict = self.to_dict()
        obj = zp.Order(initial_values=pydict)
        return obj

    def update_trailing_stop(self, current_price):
        """Update trailing stop price based on current market price.

        For sell orders (closing long positions), the stop trails below the highest
        price seen. For buy orders (closing short positions), the stop trails above
        the lowest price seen.

        Args:
            current_price: Current market price

        Returns:
            float: Updated stop price, or None if not a trailing stop order

        Example:
            Trailing stop that follows 5% below the high::

                order = Order(
                    dt=pd.Timestamp('2023-01-01'),
                    asset=stock,
                    amount=-100,  # Sell order
                    trail_percent=0.05,
                )
                # Price rises to $100
                order.update_trailing_stop(100.0)  # Stop now at $95.00
                # Price rises to $110
                order.update_trailing_stop(110.0)  # Stop now at $104.50
                # Price falls to $105
                order.update_trailing_stop(105.0)  # Stop stays at $104.50
        """
        if not self.is_trailing_stop:
            return self.stop

        is_buy = self.amount > 0

        if is_buy:
            # For buy/cover orders (closing short), track lowest price
            if self.trailing_lowest_price is None or current_price < self.trailing_lowest_price:
                self.trailing_lowest_price = current_price

            if self.trail_amount is not None:
                self.stop = self.trailing_lowest_price + self.trail_amount
            else:
                self.stop = self.trailing_lowest_price * (1 + self.trail_percent)
        else:
            # For sell orders (closing long), track highest price
            if self.trailing_highest_price is None or current_price > self.trailing_highest_price:
                self.trailing_highest_price = current_price

            if self.trail_amount is not None:
                self.stop = self.trailing_highest_price - self.trail_amount
            else:
                self.stop = self.trailing_highest_price * (1 - self.trail_percent)

        return self.stop

    def check_triggers(self, price, dt):
        """Update internal state based on price triggers.

        This method checks if stop/limit prices have been reached and updates the
        order's state accordingly. For trailing stops, it first updates the trailing
        stop price before checking triggers.

        Args:
            price: Current market price
            dt: Current timestamp

        Note:
            This method updates self.stop_reached, self.limit_reached, and self.dt
            if trigger states change.
        """
        # Update trailing stop price if applicable
        if self.is_trailing_stop:
            self.update_trailing_stop(price)

        (
            stop_reached,
            limit_reached,
            sl_stop_reached,
        ) = self.check_order_triggers(price)
        if (stop_reached, limit_reached) != (
            self.stop_reached,
            self.limit_reached,
        ):
            self.dt = dt
        self.stop_reached = stop_reached
        self.limit_reached = limit_reached
        if sl_stop_reached:
            # Change the STOP LIMIT order into a LIMIT order
            self.stop = None

    # TODO: simplify
    def check_order_triggers(self, current_price):
        """Check if order price triggers have been reached.

        Determines if stop and/or limit prices have been reached based on the
        current market price and order direction.

        Args:
            current_price: Current market price

        Returns:
            tuple: (stop_reached, limit_reached, sl_stop_reached) where:
                - stop_reached (bool): Stop price reached for stop orders
                - limit_reached (bool): Limit price reached for limit orders
                - sl_stop_reached (bool): Stop reached for stop-limit orders
                    (indicating conversion from stop-limit to limit order)

        Note:
            - Market orders: Returns (False, False, False)
            - Stop orders: limit_reached is always False
            - Limit orders: stop_reached is always False
            - Already triggered orders: Returns current trigger state

        Example:
            Buy stop order at $150 triggers when price rises to $150::

                # current_price = $145
                stop_reached, limit_reached, _ = order.check_order_triggers(145)
                # Returns (False, False, False)

                # current_price = $151
                stop_reached, limit_reached, _ = order.check_order_triggers(151)
                # Returns (True, False, False) - order is now active
        """
        if self.triggered:
            return (self.stop_reached, self.limit_reached, False)

        stop_reached = False
        limit_reached = False
        sl_stop_reached = False

        order_type = 0

        if self.amount > 0:
            order_type |= BUY
        else:
            order_type |= SELL

        if self.stop is not None:
            order_type |= STOP

        if self.limit is not None:
            order_type |= LIMIT

        if order_type == BUY | STOP | LIMIT:
            if current_price >= self.stop:
                sl_stop_reached = True
                if current_price <= self.limit:
                    limit_reached = True
        elif order_type == SELL | STOP | LIMIT:
            if current_price <= self.stop:
                sl_stop_reached = True
                if current_price >= self.limit:
                    limit_reached = True
        elif order_type == BUY | STOP:
            if current_price >= self.stop:
                stop_reached = True
        elif order_type == SELL | STOP:
            if current_price <= self.stop:
                stop_reached = True
        elif order_type == BUY | LIMIT:
            if current_price <= self.limit:
                limit_reached = True
        elif order_type == SELL | LIMIT:
            # This is a SELL LIMIT order
            if current_price >= self.limit:
                limit_reached = True

        return (stop_reached, limit_reached, sl_stop_reached)

    def handle_split(self, ratio):
        """Adjust order for a stock split.

        Updates the order amount, limit price, and stop price according to the
        split ratio to maintain economic equivalence.

        Args:
            ratio: Split ratio (e.g., 2.0 for a 2-for-1 split)

        Note:
            Split adjustments follow FINRA guidelines:
            - new_share_amount = old_share_amount / ratio
            - new_price = old_price * ratio

            For a 2-for-1 split (ratio=2.0):
            - 100 shares at $100 becomes 200 shares at $50
            - Limit/stop prices are also halved

        Example:
            2-for-1 split adjustment::

                order = Order(
                    dt=pd.Timestamp('2023-01-01'),
                    asset=stock,
                    amount=100,
                    limit=150.00,
                )
                order.handle_split(2.0)
                # Now: amount=50, limit=300.00
        """
        # update the amount, limit_price, and stop_price
        # by the split's ratio

        # info here: http://finra.complinet.com/en/display/display_plain.html?
        # rbid=2403&element_id=8950&record_id=12208&print=1

        # new_share_amount = old_share_amount / ratio
        # new_price = old_price * ratio

        self.amount = int(self.amount / ratio)

        if self.limit is not None:
            self.limit = round(self.limit * ratio, 2)

        if self.stop is not None:
            self.stop = round(self.stop * ratio, 2)

    @property
    def status(self):
        """Get the current order status.

        The status is computed dynamically based on fill state and trigger conditions.

        Returns:
            ORDER_STATUS: Current order status enum value

        Note:
            Status precedence:
            1. FILLED if completely filled
            2. PARTIALLY_FILLED if partially filled with amount remaining
            3. OPEN if held with fills
            4. TRIGGERED if stop/limit reached but not filled
            5. Otherwise, returns internal _status (CANCELLED, REJECTED, HELD, OPEN)
        """
        if not self.open_amount:
            return ORDER_STATUS.FILLED
        elif self.filled > 0 and self.open_amount > 0:
            return ORDER_STATUS.PARTIALLY_FILLED
        elif self._status == ORDER_STATUS.HELD and self.filled:
            return ORDER_STATUS.OPEN
        elif (
            self.triggered
            and self._status == ORDER_STATUS.OPEN
            and (self.stop is not None or self.limit is not None)
        ):
            # Only show TRIGGERED for stop/limit orders that have been triggered but not filled
            return ORDER_STATUS.TRIGGERED
        else:
            return self._status

    @status.setter
    def status(self, status):
        """Set the internal order status.

        Args:
            status: ORDER_STATUS enum value
        """
        self._status = status

    def cancel(self):
        """Cancel the order.

        Sets status to CANCELLED. Used when the user or system cancels an order.
        """
        self.status = ORDER_STATUS.CANCELLED

    def reject(self, reason=""):
        """Reject the order.

        Sets status to REJECTED. Used when the broker rejects an order due to
        validation failures, margin requirements, or other constraints.

        Args:
            reason: Explanation for rejection (default: "")

        Example:
            >>> order.reject("Insufficient buying power")
        """
        self.status = ORDER_STATUS.REJECTED
        self.reason = reason

    def hold(self, reason=""):
        """Put the order on hold.

        Sets status to HELD. Used when additional validation or review is needed
        before the order can be processed.

        Args:
            reason: Explanation for hold status (default: "")

        Example:
            >>> order.hold("Pending compliance review")
        """
        self.status = ORDER_STATUS.HELD
        self.reason = reason

    @property
    def open(self):
        """Check if the order is open.

        Returns:
            bool: True if status is OPEN or HELD, False otherwise
        """
        return self.status in [ORDER_STATUS.OPEN, ORDER_STATUS.HELD]

    @property
    def triggered(self):
        """Check if the order's price conditions have been met.

        An order is considered triggered when its stop/limit conditions allow it
        to attempt execution.

        Returns:
            bool: True if order conditions are met, False otherwise

        Note:
            - Market orders: Always True
            - Stop orders: True only if stop_reached
            - Limit orders: True only if limit_reached
            - Stop-limit orders: True only if both conditions met
        """
        if self.stop is not None and not self.stop_reached:
            return False

        if self.limit is not None and not self.limit_reached:
            return False

        return True

    @property
    def open_amount(self):
        """Get the remaining unfilled amount.

        Returns:
            int: Number of shares/contracts not yet filled (can be positive or negative)

        Example:
            >>> order = Order(..., amount=100, filled=30)
            >>> order.open_amount
            70
        """
        return self.amount - self.filled

    def __repr__(self):
        """Get string representation of the order.

        Returns:
            str: String representation showing order details
        """
        return "Order(%s)" % self.to_dict().__repr__()
