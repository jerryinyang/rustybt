"""Abstract blotter interface for order management and execution.

This module defines the Blotter abstract base class, which serves as the
interface for all order management systems in RustyBT. A blotter is responsible
for:
- Accepting and tracking orders
- Canceling orders based on policies
- Simulating order execution and generating transactions
- Managing open orders and their lifecycle

The blotter acts as the bridge between algorithm order requests and the
simulated (or real) execution environment.

Classes:
    - Blotter: Abstract base class defining the blotter interface

Examples:
    Blotters are typically instantiated and managed by the TradingAlgorithm::

        from rustybt.finance.blotter import SimulationBlotter
        from rustybt.finance.cancel_policy import EODCancel

        blotter = SimulationBlotter(
            cancel_policy=EODCancel(),
            enable_cash_validation=True
        )
"""
#
# Copyright 2018 Quantopian, Inc.
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
from abc import ABC, abstractmethod

from rustybt.extensions import extensible
from rustybt.finance.cancel_policy import NeverCancel


@extensible
class Blotter(ABC):
    """Abstract base class for order management and execution.

    The Blotter is responsible for managing the lifecycle of orders from
    placement through execution or cancellation. It maintains order state,
    applies cancellation policies, and coordinates with slippage and
    commission models to generate realistic transaction simulations.

    Attributes:
        cancel_policy: Policy determining when orders should be automatically canceled.
        current_dt: The current simulation datetime.

    Note:
        This is an abstract class. Use SimulationBlotter for backtesting or
        implement a custom blotter for live trading.
    """

    def __init__(self, cancel_policy=None):
        """Initialize the blotter.

        Args:
            cancel_policy: Order cancellation policy. Defaults to NeverCancel()
                which never automatically cancels orders.
        """
        self.cancel_policy = cancel_policy if cancel_policy else NeverCancel()
        self.current_dt = None

    def set_date(self, dt):
        """Set the current simulation datetime.

        Args:
            dt: The current datetime to set.
        """
        self.current_dt = dt

    @abstractmethod
    def order(self, asset, amount, style, order_id=None):
        """Place an order for an asset.

        Creates and registers a new order with the blotter. The order will
        be tracked and processed according to the blotter's execution logic,
        slippage model, and commission model.

        Args:
            asset: The asset to order. Must be a valid Asset object.
            amount: The number of shares/contracts to order. Positive values
                indicate buy orders, negative values indicate sell orders.
            style: The execution style (MarketOrder, LimitOrder, StopOrder, etc.)
                determining how the order should be executed.
            order_id: Optional unique identifier for this order. If not provided,
                one will be generated automatically.

        Returns:
            str or None: The unique order ID if the order was placed successfully,
                or None if the order was rejected (e.g., due to validation failures).

        Examples:
            >>> # Market order to buy 100 shares
            >>> order_id = blotter.order(asset, 100, MarketOrder())
            >>>
            >>> # Limit order to sell 50 shares at $100
            >>> order_id = blotter.order(asset, -50, LimitOrder(100.0))
            >>>
            >>> # Stop order to buy 200 shares if price reaches $50
            >>> order_id = blotter.order(asset, 200, StopOrder(50.0))

        Note:
            - amount > 0: Buy or cover short position
            - amount < 0: Sell or establish short position
            - amount = 0: No order is placed (typically returns None)
        """
        raise NotImplementedError("order")

    def batch_order(self, order_arg_lists):
        """Place multiple orders in a single batch.

        This method allows algorithms to submit multiple orders efficiently.
        It processes each order sequentially using the order() method.

        Args:
            order_arg_lists: An iterable of tuples, where each tuple contains
                the arguments to pass to order() (asset, amount, style, order_id).

        Returns:
            list[str or None]: A list of order IDs (or None for rejected orders)
                corresponding to each order in the input list, in the same order.

        Examples:
            >>> # Place multiple orders at once
            >>> orders = [
            ...     (stock1, 100, MarketOrder()),
            ...     (stock2, -50, LimitOrder(75.0)),
            ...     (stock3, 200, StopOrder(50.0))
            ... ]
            >>> order_ids = blotter.batch_order(orders)
            >>> # Returns: ['order-1', 'order-2', 'order-3'] or similar

        Note:
            This default implementation processes orders sequentially. Subclasses
            may override this to implement parallel or optimized batch processing.
        """
        return [self.order(*order_args) for order_args in order_arg_lists]

    @abstractmethod
    def cancel(self, order_id, relay_status=True):
        """Cancel a single order.

        Cancels an open order by ID. If the order has already been filled,
        canceled, or doesn't exist, this method should handle the case gracefully.

        Args:
            order_id: The unique identifier of the order to cancel.
            relay_status: If True, record the order's new status (canceled) so
                it can be relayed to the algorithm. If False, cancel silently
                without status updates. Defaults to True.

        Examples:
            >>> # Cancel an order
            >>> blotter.cancel('order-123')
            >>>
            >>> # Cancel without status update
            >>> blotter.cancel('order-123', relay_status=False)

        Note:
            This is an abstract method that must be implemented by subclasses.
        """
        raise NotImplementedError("cancel")

    @abstractmethod
    def cancel_all_orders_for_asset(self, asset, warn=False, relay_status=True):
        """Cancel all open orders for a specific asset.

        Cancels every open order associated with the given asset. This is
        useful when exiting a position or when an asset becomes untradeable.

        Args:
            asset: The asset whose orders should be canceled.
            warn: If True, log warnings for partially filled orders. Defaults to False.
            relay_status: If True, record order status changes. Defaults to True.

        Note:
            This is an abstract method that must be implemented by subclasses.
        """
        raise NotImplementedError("cancel_all_orders_for_asset")

    @abstractmethod
    def execute_cancel_policy(self, event):
        """Execute the blotter's cancellation policy.

        Applies the configured cancel policy (e.g., EODCancel) to determine
        which orders should be automatically canceled based on the event.

        Args:
            event: The event that may trigger order cancellations.

        Note:
            This is an abstract method that must be implemented by subclasses.
        """
        raise NotImplementedError("execute_cancel_policy")

    @abstractmethod
    def reject(self, order_id, reason=""):
        """Mark an order as rejected.

        Rejection is similar to cancellation but involuntary, typically
        occurring when a broker or exchange refuses an order. The reason
        usually includes why the order was rejected.

        Args:
            order_id: The unique identifier of the order to reject.
            reason: Optional explanation for why the order was rejected.

        Note:
            Rejections are involuntary (broker/exchange initiated) while
            cancellations are typically user-driven.
        """
        raise NotImplementedError("reject")

    @abstractmethod
    def hold(self, order_id, reason=""):
        """Mark an order as held.

        Held status is functionally similar to open but indicates the order
        is temporarily suspended. When a fill arrives, the status automatically
        changes back to open or filled as appropriate.

        Args:
            order_id: The unique identifier of the order to hold.
            reason: Optional explanation for why the order is being held.

        Note:
            This is used when an order needs to be temporarily suspended
            without canceling it entirely.
        """
        raise NotImplementedError("hold")

    @abstractmethod
    def process_splits(self, splits):
        """Process stock splits by adjusting open orders.

        When a stock split occurs, open orders need to be adjusted to reflect
        the new share price and quantity. This method applies those adjustments.

        Args:
            splits: List of (asset, ratio) tuples representing stock splits.
                For example, (asset, 2.0) represents a 2-for-1 split.

        Returns:
            None

        Examples:
            >>> # Process a 2-for-1 split
            >>> splits = [(stock, 2.0)]
            >>> blotter.process_splits(splits)
            >>> # Open orders for stock now have 2x quantity at 0.5x price

        Note:
            This is an abstract method that must be implemented by subclasses.
        """
        raise NotImplementedError("process_splits")

    @abstractmethod
    def get_transactions(self, bar_data):
        """Generate transactions by simulating execution of open orders.

        This is the core execution method that processes all open orders using
        the blotter's slippage and commission models to generate realistic
        transaction simulations. It updates order state and tracks which orders
        have closed.

        Args:
            bar_data: Current market data for all tradeable assets. Used to
                determine execution prices and volumes.

        Returns:
            tuple: A 3-tuple containing:
                - transactions_list (list): Transactions resulting from fills.
                    Empty list if no orders were filled.
                - commissions_list (list): Commission objects with 'asset' and
                    'cost' attributes for each transaction.
                - closed_orders (list): Orders that have been completely filled.

        Examples:
            >>> transactions, commissions, closed = blotter.get_transactions(bar_data)
            >>> for txn in transactions:
            ...     print(f"Filled {txn.amount} shares at ${txn.price}")
            >>> for comm in commissions:
            ...     print(f"Commission on {comm['asset']}: ${comm['cost']}")

        Note:
            This method updates the blotter's internal state (open_orders
            dictionary) to maintain accuracy throughout processing.
        """
        raise NotImplementedError("get_transactions")

    @abstractmethod
    def prune_orders(self, closed_orders):
        """Remove closed orders from the open orders list.

        After orders are filled and closed, this method removes them from
        the blotter's tracking to clean up the open orders list.

        Args:
            closed_orders: Iterable of Order objects that have been closed
                (fully filled, canceled, or rejected).

        Returns:
            None

        Examples:
            >>> closed_orders = [order1, order2, order3]
            >>> blotter.prune_orders(closed_orders)
            >>> # These orders are now removed from open_orders

        Note:
            This is typically called after get_transactions() to remove
            orders that have been completely filled.
        """
        raise NotImplementedError("prune_orders")
