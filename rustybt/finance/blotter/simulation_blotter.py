#
# Copyright 2015 Quantopian, Inc.
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
import logging
from collections import defaultdict
from copy import copy

from rustybt.assets import Asset, Equity, Future
from rustybt.extensions import register
from rustybt.finance.commission import (
    DEFAULT_PER_CONTRACT_COST,
    FUTURE_EXCHANGE_FEES_BY_SYMBOL,
    PerContract,
    PerShare,
)
from rustybt.finance.execution import (
    BracketOrder,
    OCOOrder,
    TrailingStopOrder,
)
from rustybt.finance.order import Order
from rustybt.finance.slippage import (
    DEFAULT_FUTURE_VOLUME_SLIPPAGE_BAR_LIMIT,
    FixedBasisPointsSlippage,
    VolatilityVolumeShare,
)
from rustybt.utils.input_validation import expect_types

from .blotter import Blotter

log = logging.getLogger("Blotter")
warning_logger = logging.getLogger("AlgoWarning")


@register(Blotter, "default")
class SimulationBlotter(Blotter):
    def __init__(
        self,
        equity_slippage=None,
        future_slippage=None,
        equity_commission=None,
        future_commission=None,
        cancel_policy=None,
    ):
        super().__init__(cancel_policy=cancel_policy)

        # these orders are aggregated by asset
        self.open_orders = defaultdict(list)

        # keep a dict of orders by their own id
        self.orders = {}

        # holding orders that have come in since the last event.
        self.new_orders = []

        self.max_shares = int(1e11)

        self.slippage_models = {
            Equity: equity_slippage or FixedBasisPointsSlippage(),
            Future: future_slippage
            or VolatilityVolumeShare(
                volume_limit=DEFAULT_FUTURE_VOLUME_SLIPPAGE_BAR_LIMIT,
            ),
        }
        self.commission_models = {
            Equity: equity_commission or PerShare(),
            Future: future_commission
            or PerContract(
                cost=DEFAULT_PER_CONTRACT_COST,
                exchange_fee=FUTURE_EXCHANGE_FEES_BY_SYMBOL,
            ),
        }

    def __repr__(self):
        return """
{class_name}(
    slippage_models={slippage_models},
    commission_models={commission_models},
    open_orders={open_orders},
    orders={orders},
    new_orders={new_orders},
    current_dt={current_dt})
""".strip().format(
            class_name=self.__class__.__name__,
            slippage_models=self.slippage_models,
            commission_models=self.commission_models,
            open_orders=self.open_orders,
            orders=self.orders,
            new_orders=self.new_orders,
            current_dt=self.current_dt,
        )

    @expect_types(asset=Asset)
    def order(self, asset, amount, style, order_id=None):
        """Place an order.

        Parameters
        ----------
        asset : zipline.assets.Asset
            The asset that this order is for.
        amount : int
            The amount of shares to order. If ``amount`` is positive, this is
            the number of shares to buy or cover. If ``amount`` is negative,
            this is the number of shares to sell or short.
        style : zipline.finance.execution.ExecutionStyle
            The execution style for the order.
        order_id : str, optional
            The unique identifier for this order.

        Returns:
        -------
        order_id : str or None
            The unique identifier for this order, or None if no order was
            placed.

        Notes:
        -----
        amount > 0 :: Buy/Cover
        amount < 0 :: Sell/Short
        Market order:    order(asset, amount)
        Limit order:     order(asset, amount, style=LimitOrder(limit_price))
        Stop order:      order(asset, amount, style=StopOrder(stop_price))
        StopLimit order: order(asset, amount, style=StopLimitOrder(limit_price,
        stop_price))
        """
        # something could be done with amount to further divide
        # between buy by share count OR buy shares up to a dollar amount
        # numeric == share count  AND  "$dollar.cents" == cost amount

        if amount == 0:
            # Don't bother placing orders for 0 shares.
            return None
        elif amount > self.max_shares:
            # Arbitrary limit of 100 billion (US) shares will never be
            # exceeded except by a buggy algorithm.
            raise OverflowError("Can't order more than %d shares" % self.max_shares)

        is_buy = amount > 0

        # Handle TrailingStopOrder
        if isinstance(style, TrailingStopOrder):
            order = Order(
                dt=self.current_dt,
                asset=asset,
                amount=amount,
                stop=style.get_stop_price(is_buy),
                limit=style.get_limit_price(is_buy),
                trail_amount=style.trail_amount,
                trail_percent=style.trail_percent,
                id=order_id,
            )
        # Handle OCOOrder - creates two linked orders
        elif isinstance(style, OCOOrder):
            # Create first order
            order1 = Order(
                dt=self.current_dt,
                asset=asset,
                amount=amount,
                stop=style.order1_style.get_stop_price(is_buy),
                limit=style.order1_style.get_limit_price(is_buy),
                id=order_id,
            )
            # Create second order with new ID
            order2 = Order(
                dt=self.current_dt,
                asset=asset,
                amount=amount,
                stop=style.order2_style.get_stop_price(is_buy),
                limit=style.order2_style.get_limit_price(is_buy),
            )
            # Link the orders
            order1.linked_order_ids = [order2.id]
            order2.linked_order_ids = [order1.id]

            # Add both orders
            self.open_orders[order1.asset].append(order1)
            self.open_orders[order2.asset].append(order2)
            self.orders[order1.id] = order1
            self.orders[order2.id] = order2
            self.new_orders.append(order1)
            self.new_orders.append(order2)

            return order1.id  # Return first order ID as parent

        # Handle BracketOrder - creates entry, stop-loss, and take-profit
        elif isinstance(style, BracketOrder):
            # Create entry order
            entry_order = Order(
                dt=self.current_dt,
                asset=asset,
                amount=amount,
                stop=style.get_stop_price(is_buy),
                limit=style.get_limit_price(is_buy),
                id=order_id,
            )

            # Store bracket info in blotter for later processing
            # (Child orders created after entry fills)
            if not hasattr(self, "_bracket_orders"):
                self._bracket_orders = {}
            self._bracket_orders[entry_order.id] = {
                "stop_loss_price": style.stop_loss_price,
                "take_profit_price": style.take_profit_price,
                "amount": -amount,  # Reverse direction for exit orders
            }

            order = entry_order
        else:
            # Standard order (Market, Limit, Stop, StopLimit)
            order = Order(
                dt=self.current_dt,
                asset=asset,
                amount=amount,
                stop=style.get_stop_price(is_buy),
                limit=style.get_limit_price(is_buy),
                id=order_id,
            )

        self.open_orders[order.asset].append(order)
        self.orders[order.id] = order
        self.new_orders.append(order)

        return order.id

    def cancel(self, order_id, relay_status=True):
        if order_id not in self.orders:
            return

        cur_order = self.orders[order_id]

        if cur_order.open:
            order_list = self.open_orders[cur_order.asset]
            if cur_order in order_list:
                order_list.remove(cur_order)

            if cur_order in self.new_orders:
                self.new_orders.remove(cur_order)
            cur_order.cancel()
            cur_order.dt = self.current_dt

            if relay_status:
                # we want this order's new status to be relayed out
                # along with newly placed orders.
                self.new_orders.append(cur_order)

    def cancel_linked_orders(self, filled_order_id):
        """
        Cancel all orders linked to a filled order (OCO behavior).

        Parameters
        ----------
        filled_order_id : str
            ID of the order that filled
        """
        if filled_order_id not in self.orders:
            return

        filled_order = self.orders[filled_order_id]

        # Cancel all linked orders
        for linked_id in filled_order.linked_order_ids:
            if linked_id in self.orders:
                log.info(
                    f"Canceling linked order {linked_id} because "
                    f"order {filled_order_id} filled (OCO)"
                )
                self.cancel(linked_id, relay_status=True)

    def process_bracket_fill(self, entry_order_id):
        """
        Process bracket order entry fill by creating stop-loss and take-profit orders.

        Parameters
        ----------
        entry_order_id : str
            ID of the entry order that filled
        """
        if not hasattr(self, "_bracket_orders") or entry_order_id not in self._bracket_orders:
            return

        bracket_info = self._bracket_orders[entry_order_id]
        entry_order = self.orders[entry_order_id]

        # Create stop-loss order
        stop_loss_order = Order(
            dt=self.current_dt,
            asset=entry_order.asset,
            amount=bracket_info["amount"],
            stop=bracket_info["stop_loss_price"],
            parent_order_id=entry_order_id,
        )

        # Create take-profit order
        take_profit_order = Order(
            dt=self.current_dt,
            asset=entry_order.asset,
            amount=bracket_info["amount"],
            limit=bracket_info["take_profit_price"],
            parent_order_id=entry_order_id,
        )

        # Link as OCO pair
        stop_loss_order.linked_order_ids = [take_profit_order.id]
        take_profit_order.linked_order_ids = [stop_loss_order.id]

        # Add child orders
        self.open_orders[stop_loss_order.asset].append(stop_loss_order)
        self.open_orders[take_profit_order.asset].append(take_profit_order)
        self.orders[stop_loss_order.id] = stop_loss_order
        self.orders[take_profit_order.id] = take_profit_order
        self.new_orders.append(stop_loss_order)
        self.new_orders.append(take_profit_order)

        log.info(
            f"Bracket order {entry_order_id} filled. "
            f"Created stop-loss {stop_loss_order.id} and "
            f"take-profit {take_profit_order.id}"
        )

        # Remove from pending brackets
        del self._bracket_orders[entry_order_id]

    def cancel_all_orders_for_asset(self, asset, warn=False, relay_status=True):
        """
        Cancel all open orders for a given asset.
        """
        # (sadly) open_orders is a defaultdict, so this will always succeed.
        orders = self.open_orders[asset]

        # We're making a copy here because `cancel` mutates the list of open
        # orders in place.  The right thing to do here would be to make
        # self.open_orders no longer a defaultdict.  If we do that, then we
        # should just remove the orders once here and be done with the matter.
        for order in orders[:]:
            self.cancel(order.id, relay_status)
            if warn:
                # Message appropriately depending on whether there's
                # been a partial fill or not.
                if order.filled > 0:
                    warning_logger.warning(
                        f"Your order for {order.amount} shares of "
                        f"{order.asset.symbol} has been partially filled. "
                        f"{order.filled} shares were successfully "
                        f"purchased. {order.amount - order.filled} shares were not "
                        "filled by the end of day and "
                        "were canceled."
                    )
                elif order.filled < 0:
                    warning_logger.warning(
                        f"Your order for {order.amount} shares of "
                        f"{order.asset.symbol} has been partially filled. "
                        f"{-1 * order.filled} shares were successfully "
                        f"sold. {-1 * (order.amount - order.filled)} shares were not "
                        "filled by the end of day and "
                        "were canceled."
                    )
                else:
                    warning_logger.warning(
                        f"Your order for {order.amount} shares of "
                        f"{order.asset.symbol} failed to fill by the end of day "
                        "and was canceled."
                    )

        assert not orders
        del self.open_orders[asset]

    # End of day cancel for daily frequency
    def execute_daily_cancel_policy(self, event):
        if self.cancel_policy.should_cancel(event):
            warn = self.cancel_policy.warn_on_cancel
            for asset in copy(self.open_orders):
                orders = self.open_orders[asset]
                if len(orders) > 1:
                    order = orders[0]
                    self.cancel(order.id, relay_status=True)
                    if warn:
                        if order.filled > 0:
                            warning_logger.warn(
                                f"Your order for {order.amount} shares of "
                                f"{order.asset.symbol} has been partially filled. "
                                f"{order.filled} shares were successfully "
                                f"purchased. {order.amount - order.filled} shares were not "
                                "filled by the end of day and "
                                "were canceled."
                            )
                        elif order.filled < 0:
                            warning_logger.warn(
                                f"Your order for {order.amount} shares of "
                                f"{order.asset.symbol} has been partially filled. "
                                f"{-1 * order.filled} shares were successfully "
                                f"sold. {-1 * (order.amount - order.filled)} shares were not "
                                "filled by the end of day and "
                                "were canceled."
                            )
                        else:
                            warning_logger.warn(
                                f"Your order for {order.amount} shares of "
                                f"{order.asset.symbol} failed to fill by the end of day "
                                "and was canceled."
                            )

    def execute_cancel_policy(self, event):
        if self.cancel_policy.should_cancel(event):
            warn = self.cancel_policy.warn_on_cancel
            for asset in copy(self.open_orders):
                self.cancel_all_orders_for_asset(asset, warn, relay_status=False)

    def reject(self, order_id, reason=""):
        """
        Mark the given order as 'rejected', which is functionally similar to
        cancelled. The distinction is that rejections are involuntary (and
        usually include a message from a broker indicating why the order was
        rejected) while cancels are typically user-driven.
        """
        if order_id not in self.orders:
            return

        cur_order = self.orders[order_id]

        order_list = self.open_orders[cur_order.asset]
        if cur_order in order_list:
            order_list.remove(cur_order)

        if cur_order in self.new_orders:
            self.new_orders.remove(cur_order)
        cur_order.reject(reason=reason)
        cur_order.dt = self.current_dt
        # we want this order's new status to be relayed out
        # along with newly placed orders.
        self.new_orders.append(cur_order)

    def hold(self, order_id, reason=""):
        """
        Mark the order with order_id as 'held'. Held is functionally similar
        to 'open'. When a fill (full or partial) arrives, the status
        will automatically change back to open/filled as necessary.
        """
        if order_id not in self.orders:
            return

        cur_order = self.orders[order_id]
        if cur_order.open:
            if cur_order in self.new_orders:
                self.new_orders.remove(cur_order)
            cur_order.hold(reason=reason)
            cur_order.dt = self.current_dt
            # we want this order's new status to be relayed out
            # along with newly placed orders.
            self.new_orders.append(cur_order)

    def process_splits(self, splits):
        """
        Processes a list of splits by modifying any open orders as needed.

        Parameters
        ----------
        splits: list
            A list of splits.  Each split is a tuple of (asset, ratio).

        Returns:
        -------
        None
        """
        for asset, ratio in splits:
            if asset not in self.open_orders:
                continue

            orders_to_modify = self.open_orders[asset]
            for order in orders_to_modify:
                order.handle_split(ratio)

    def get_transactions(self, bar_data):
        """
        Creates a list of transactions based on the current open orders,
        slippage model, and commission model.

        Parameters
        ----------
        bar_data: zipline._protocol.BarData

        Notes:
        -----
        This method book-keeps the blotter's open_orders dictionary, so that
         it is accurate by the time we're done processing open orders.

        Returns:
        -------
        transactions_list: List
            transactions_list: list of transactions resulting from the current
            open orders.  If there were no open orders, an empty list is
            returned.

        commissions_list: List
            commissions_list: list of commissions resulting from filling the
            open orders.  A commission is an object with "asset" and "cost"
            parameters.

        closed_orders: List
            closed_orders: list of all the orders that have filled.
        """
        closed_orders = []
        transactions = []
        commissions = []

        if self.open_orders:
            for asset, asset_orders in self.open_orders.items():
                slippage = self.slippage_models[type(asset)]

                for order, txn in slippage.simulate(bar_data, asset, asset_orders):
                    commission = self.commission_models[type(asset)]
                    additional_commission = commission.calculate(order, txn)

                    if additional_commission > 0:
                        commissions.append(
                            {
                                "asset": order.asset,
                                "order": order,
                                "cost": additional_commission,
                            }
                        )

                    order.filled += txn.amount
                    order.commission += additional_commission

                    order.dt = txn.dt

                    transactions.append(txn)

                    if not order.open:
                        closed_orders.append(order)

        return transactions, commissions, closed_orders

    def prune_orders(self, closed_orders):
        """
        Removes all given orders from the blotter's open_orders list.

        Parameters
        ----------
        closed_orders: iterable of orders that are closed.

        Returns:
        -------
        None
        """
        # remove all closed orders from our open_orders dict
        for order in closed_orders:
            asset = order.asset
            asset_orders = self.open_orders[asset]
            try:
                asset_orders.remove(order)
            except ValueError:
                continue

        # now clear out the assets from our open_orders dict that have
        # zero open orders
        for asset in list(self.open_orders.keys()):
            if len(self.open_orders[asset]) == 0:
                del self.open_orders[asset]
