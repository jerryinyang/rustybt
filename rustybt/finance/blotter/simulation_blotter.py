"""Simulation blotter for backtesting with realistic order execution.

This module provides the SimulationBlotter, which is the default blotter
implementation for backtesting in RustyBT. It simulates realistic order
execution by:

- Applying slippage models to orders based on market conditions
- Calculating commissions using configurable commission models
- Supporting advanced order types (bracket, OCO, trailing stop)
- Validating cash availability before executing buys
- Handling stock splits and corporate actions
- Managing order lifecycle from placement through execution

The SimulationBlotter supports multiple asset types (equities, futures,
crypto) and can be configured with different slippage and commission
models for each asset class.

Classes:
    - SimulationBlotter: Default blotter implementation for backtesting

Examples:
    Basic setup::

        from rustybt.finance.blotter import SimulationBlotter
        from rustybt.finance.slippage import VolumeShareSlippage
        from rustybt.finance.commission import PerShare

        blotter = SimulationBlotter(
            equity_slippage=VolumeShareSlippage(),
            equity_commission=PerShare(cost=0.005, min_trade_cost=1.0),
            enable_cash_validation=True,
            cash_validation_mode='reject'
        )

    Advanced configuration with cash validation::

        blotter = SimulationBlotter(
            equity_slippage=VolumeShareSlippage(volume_limit=0.025),
            equity_commission=PerShare(0.005, 1.0),
            enable_cash_validation=True,  # Prevent overdraft
            cash_validation_mode='reject',  # Reject invalid orders
            portfolio=portfolio,  # Required for cash validation
            data_portal=data_portal  # Required for price lookups
        )
"""

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
from rustybt.exceptions import InsufficientFundsError
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
    """Default blotter implementation for backtesting simulations.

    SimulationBlotter provides realistic order execution simulation by applying
    slippage and commission models, validating cash availability, and managing
    the complete order lifecycle. It supports multiple asset types with different
    execution models for each.

    Key Features:
        - Configurable slippage and commission models per asset type
        - Cash validation to prevent overdraft (optional)
        - Advanced order types: Bracket, OCO, Trailing Stop
        - Stock split handling
        - Realistic partial fills based on market volume
        - Support for equities, futures, and generic assets

    Args:
        equity_slippage: Slippage model for equity orders. Defaults to
            FixedBasisPointsSlippage() if not specified.
        future_slippage: Slippage model for futures orders. Defaults to
            VolatilityVolumeShare() if not specified.
        equity_commission: Commission model for equity orders. Defaults to
            PerShare() if not specified.
        future_commission: Commission model for futures orders. Defaults to
            PerContract() if not specified.
        cancel_policy: Policy for automatic order cancellation. Defaults to
            NeverCancel() if not specified.
        portfolio: Portfolio reference for cash validation (optional but
            required if enable_cash_validation=True).
        data_portal: DataPortal for price lookups (optional but required
            if enable_cash_validation=True).
        enable_cash_validation: If True, validate sufficient cash before
            placing buy orders. Defaults to True.
        cash_validation_mode: How to handle insufficient cash. Options:
            - "reject": Reject order and log warning (graceful)
            - "warn": Log warning but allow order (backward compatible)
            - "strict": Raise InsufficientFundsError (halt backtest)
            Defaults to "reject".

    Attributes:
        open_orders: Dictionary mapping assets to lists of open orders.
        orders: Dictionary mapping order IDs to order objects.
        new_orders: List of orders placed since last event.
        max_shares: Maximum shares allowed per order (100 billion).
        portfolio: Portfolio reference for cash validation.
        data_portal: DataPortal for market data access.
        enable_cash_validation: Whether cash validation is enabled.
        cash_validation_mode: How insufficient cash is handled.
        slippage_models: Dictionary mapping asset types to slippage models.
        commission_models: Dictionary mapping asset types to commission models.

    Examples:
        >>> blotter = SimulationBlotter(
        ...     equity_commission=PerShare(cost=0.005, min_trade_cost=1.0),
        ...     enable_cash_validation=True,
        ...     cash_validation_mode='reject'
        ... )
        >>> order_id = blotter.order(stock, 100, MarketOrder())

    Raises:
        ValueError: If cash_validation_mode is not one of: reject, warn, strict.
    """

    def __init__(
        self,
        equity_slippage=None,
        future_slippage=None,
        equity_commission=None,
        future_commission=None,
        cancel_policy=None,
        portfolio=None,
        data_portal=None,
        enable_cash_validation=True,
        cash_validation_mode="reject",
    ):
        super().__init__(cancel_policy=cancel_policy)

        # these orders are aggregated by asset
        self.open_orders = defaultdict(list)

        # keep a dict of orders by their own id
        self.orders = {}

        # holding orders that have come in since the last event.
        self.new_orders = []

        self.max_shares = int(1e11)

        # Cash validation support
        self.portfolio = portfolio
        self.data_portal = data_portal
        self.enable_cash_validation = enable_cash_validation

        # Cash validation mode: "reject", "warn", or "strict"
        # - "reject": Reject order, log warning, return None (graceful)
        # - "warn": Log warning but allow order (backward compatible)
        # - "strict": Raise InsufficientFundsError (crash backtest)
        if cash_validation_mode not in ("reject", "warn", "strict"):
            raise ValueError(
                f"cash_validation_mode must be 'reject', 'warn', or 'strict', "
                f"got {cash_validation_mode!r}"
            )
        self.cash_validation_mode = cash_validation_mode

        # Default slippage and commission for generic assets (crypto, etc.)
        default_asset_slippage = equity_slippage or FixedBasisPointsSlippage()
        default_asset_commission = equity_commission or PerShare()

        self.slippage_models = {
            Asset: default_asset_slippage,  # For generic assets like crypto
            Equity: default_asset_slippage,
            Future: future_slippage
            or VolatilityVolumeShare(
                volume_limit=DEFAULT_FUTURE_VOLUME_SLIPPAGE_BAR_LIMIT,
            ),
        }
        self.commission_models = {
            Asset: default_asset_commission,  # For generic assets like crypto
            Equity: default_asset_commission,
            Future: future_commission
            or PerContract(
                cost=DEFAULT_PER_CONTRACT_COST,
                exchange_fee=FUTURE_EXCHANGE_FEES_BY_SYMBOL,
            ),
        }

    def __repr__(self):
        """Return detailed string representation of the blotter state.

        Returns:
            str: Multi-line string showing blotter configuration and current state.
        """
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

    def set_portfolio_reference(self, portfolio, data_portal=None):
        """Set references to portfolio and data_portal for cash validation.

        This should be called after the algorithm is fully initialized.

        Parameters
        ----------
        portfolio : Portfolio
            The portfolio object to use for cash validation
        data_portal : DataPortal, optional
            The data portal for accessing current prices
        """
        self.portfolio = portfolio
        if data_portal is not None:
            self.data_portal = data_portal

    def _calculate_reserved_cash(self):
        """Calculate total cash reserved for pending unfilled buy orders.

        Returns
        -------
        float
            Total cash reserved for open buy orders
        """
        if not self.enable_cash_validation or self.data_portal is None:
            return 0.0

        reserved = 0.0
        for order in self.orders.values():
            if order.open and order.amount > 0:  # Only buy orders reserve cash
                try:
                    estimated_price = self._estimate_order_price(order)
                    reserved += abs(order.amount) * estimated_price
                except Exception as e:
                    # If we can't estimate price, skip this order
                    # Better to be permissive than to block valid orders
                    log.warning(
                        f"Could not estimate price for order {order.id}: {e}. "
                        "Skipping cash reservation for this order."
                    )
                    continue

        return reserved

    def _estimate_order_price(self, order):
        """Estimate order execution price for cash reservation.

        Parameters
        ----------
        order : Order
            The order to estimate price for

        Returns
        -------
        float
            Estimated execution price

        Raises
        ------
        ValueError
            If price cannot be estimated
        """
        # For limit orders, use limit price
        if order.limit is not None:
            return order.limit

        # For stop orders, use stop price as conservative estimate
        if order.stop is not None:
            return order.stop

        # For market orders, get current price from data portal
        if self.data_portal is not None:
            try:
                # Get current price for the asset
                price = self.data_portal.get_spot_value(
                    order.asset,
                    "close",
                    self.current_dt,
                    "daily",
                )
                return price
            except Exception:
                # If we can't get current price, raise error
                raise ValueError(
                    f"Cannot estimate market order price for {order.asset.symbol} "
                    "at current time. Data not available."
                )

        # No price available
        raise ValueError("Cannot estimate order price: no limit/stop price and no data portal")

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

        # Cash validation for buy orders
        if (
            is_buy
            and self.enable_cash_validation
            and self.portfolio is not None
            and self.data_portal is not None
        ):
            # Estimate the cost of this order
            try:
                if hasattr(style, "get_limit_price"):
                    estimated_price = style.get_limit_price(is_buy)
                elif hasattr(style, "get_stop_price"):
                    estimated_price = style.get_stop_price(is_buy)
                else:
                    # Market order - get current price
                    estimated_price = self.data_portal.get_spot_value(
                        asset,
                        "close",
                        self.current_dt,
                        "daily",
                    )

                if estimated_price is None:
                    # For market orders without price, get current price
                    estimated_price = self.data_portal.get_spot_value(
                        asset,
                        "close",
                        self.current_dt,
                        "daily",
                    )

                estimated_cost = abs(amount) * estimated_price

                # Calculate reserved cash from pending orders
                reserved_cash = self._calculate_reserved_cash()

                # Calculate available cash
                available_cash = self.portfolio.cash - reserved_cash

                # Check if we have sufficient cash
                if estimated_cost > available_cash:
                    error_msg = (
                        f"Insufficient cash for order: need ${estimated_cost:,.2f}, "
                        f"have ${available_cash:,.2f} available "
                        f"(${self.portfolio.cash:,.2f} total - ${reserved_cash:,.2f} reserved)"
                    )

                    if self.cash_validation_mode == "strict":
                        # Strict mode: Raise exception (crash backtest)
                        raise InsufficientFundsError(
                            error_msg,
                            required=estimated_cost,
                            available=available_cash,
                            context={
                                "asset": asset.symbol,
                                "amount": amount,
                                "estimated_price": estimated_price,
                                "total_cash": self.portfolio.cash,
                                "reserved_cash": reserved_cash,
                            },
                        )
                    elif self.cash_validation_mode == "reject":
                        # Reject mode: Log warning and reject order (graceful)
                        warning_logger.warning(
                            f"Order rejected - {error_msg}. "
                            f"Asset: {asset.symbol}, Amount: {amount}"
                        )
                        return None  # Order rejected, backtest continues
                    else:  # "warn" mode
                        # Warn mode: Log warning but allow order (backward compatible)
                        warning_logger.warning(
                            f"Order placed with insufficient cash - {error_msg}. "
                            f"Asset: {asset.symbol}, Amount: {amount}. "
                            "Order will be placed but may fail on execution."
                        )
                        # Continue to place order
            except InsufficientFundsError:
                # Re-raise InsufficientFundsError
                raise
            except Exception as e:
                # Log warning but allow order to proceed
                # This ensures we don't break existing behavior if price estimation fails
                log.warning(
                    f"Could not validate cash for order {asset.symbol}: {e}. "
                    "Proceeding with order placement."
                )

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
        """Cancel all orders linked to a filled order (OCO behavior).

        This implements One-Cancels-Other (OCO) order logic. When one order
        in a linked group fills, all other orders in that group are automatically
        canceled to prevent unintended positions.

        Args:
            filled_order_id: The unique ID of the order that was filled.

        Examples:
            >>> # OCO order placed: buy at $100 limit OR buy at $95 stop
            >>> # If the limit order fills, this automatically cancels the stop
            >>> blotter.cancel_linked_orders(limit_order_id)

        Note:
            This is automatically called when OCO or bracket orders fill.
            It's not typically called directly by user code.
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

        Notes
        -----
        Only creates orders for non-zero prices. If both prices are provided,
        orders are linked as an OCO pair. If only one price is provided,
        creates a single protective order.
        """
        if not hasattr(self, "_bracket_orders") or entry_order_id not in self._bracket_orders:
            return

        bracket_info = self._bracket_orders[entry_order_id]
        entry_order = self.orders[entry_order_id]

        created_orders = []
        stop_loss_order = None
        take_profit_order = None

        # Create stop-loss order only if price is valid (> 0)
        stop_loss_price = bracket_info["stop_loss_price"]
        if stop_loss_price > 0:
            stop_loss_order = Order(
                dt=self.current_dt,
                asset=entry_order.asset,
                amount=bracket_info["amount"],
                stop=stop_loss_price,
                parent_order_id=entry_order_id,
            )
            created_orders.append(stop_loss_order)

        # Create take-profit order only if price is valid (> 0)
        take_profit_price = bracket_info["take_profit_price"]
        if take_profit_price > 0:
            take_profit_order = Order(
                dt=self.current_dt,
                asset=entry_order.asset,
                amount=bracket_info["amount"],
                limit=take_profit_price,
                parent_order_id=entry_order_id,
            )
            created_orders.append(take_profit_order)

        # If both orders created, link as OCO pair
        if stop_loss_order and take_profit_order:
            stop_loss_order.linked_order_ids = [take_profit_order.id]
            take_profit_order.linked_order_ids = [stop_loss_order.id]

        # Add all created orders to blotter
        for order in created_orders:
            self.open_orders[order.asset].append(order)
            self.orders[order.id] = order
            self.new_orders.append(order)

        # Log what was created
        if stop_loss_order and take_profit_order:
            log.info(
                f"Bracket order {entry_order_id} filled. "
                f"Created stop-loss {stop_loss_order.id} and "
                f"take-profit {take_profit_order.id} (OCO pair)"
            )
        elif stop_loss_order:
            log.info(
                f"Bracket order {entry_order_id} filled. "
                f"Created stop-loss {stop_loss_order.id} only"
            )
        elif take_profit_order:
            log.info(
                f"Bracket order {entry_order_id} filled. "
                f"Created take-profit {take_profit_order.id} only"
            )
        else:
            log.warning(
                f"Bracket order {entry_order_id} filled but no valid prices "
                f"(stop_loss={stop_loss_price}, take_profit={take_profit_price}). "
                "No protective orders created."
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

    def get_transactions(self, bar_data, fractional_order_mode=None):
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

                # CRITICAL FIX: Pass fractional_order_mode to slippage simulation
                for order, txn in slippage.simulate(
                    bar_data, asset, asset_orders, fractional_order_mode
                ):
                    # Execution-time cash validation for buy orders
                    if (
                        self.enable_cash_validation
                        and self.portfolio is not None
                        and txn.amount > 0  # Buy transaction
                    ):
                        # Calculate transaction cost including commission
                        commission = self.commission_models[type(asset)]
                        estimated_commission = commission.calculate(order, txn)
                        transaction_cost = abs(txn.amount) * txn.price + estimated_commission

                        # Check if we have sufficient cash at execution time
                        if transaction_cost > self.portfolio.cash:
                            if self.cash_validation_mode == "strict":
                                # Strict mode: Raise exception
                                raise InsufficientFundsError(
                                    f"Insufficient cash to execute order {order.id}: "
                                    f"need ${transaction_cost:,.2f}, have ${self.portfolio.cash:,.2f}",
                                    required=transaction_cost,
                                    available=self.portfolio.cash,
                                    context={
                                        "asset": order.asset.symbol,
                                        "order_id": order.id,
                                        "transaction_amount": txn.amount,
                                        "transaction_price": txn.price,
                                    },
                                )
                            elif self.cash_validation_mode == "reject":
                                # Reject mode: Skip transaction, log warning
                                warning_logger.warning(
                                    f"Order {order.id} fill rejected at execution - "
                                    f"insufficient cash: need ${transaction_cost:,.2f}, "
                                    f"have ${self.portfolio.cash:,.2f}. "
                                    f"Asset: {order.asset.symbol}, Amount: {txn.amount}. "
                                    "Order remains open."
                                )
                                continue  # Skip this transaction
                            # else: "warn" mode - log warning but allow execution
                            else:
                                warning_logger.warning(
                                    f"Order {order.id} executed with insufficient cash: "
                                    f"need ${transaction_cost:,.2f}, have ${self.portfolio.cash:,.2f}. "
                                    f"Asset: {order.asset.symbol}, Amount: {txn.amount}"
                                )

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
